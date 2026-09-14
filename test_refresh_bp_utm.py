"""Offline-only publisher regressions. All payloads are synthetic, not business data."""
import copy
import contextlib
import io
import fcntl
import datetime as dt
import importlib
import json
import os
from pathlib import Path
import tempfile
import subprocess
import unittest
from unittest import mock

try:
    publisher = importlib.import_module('refresh_bp_utm')
except ModuleNotFoundError:
    publisher = None

IDS = ('sma', 'hm', 'end', 'pp', 'pqt', 'sil', 'jdc', 'talc', 'bm', 'tvm', 'chlor')


def payload(count=10):
    return {'generated_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'torts': [{'tort_id': tid, 'tort_name': 'SYNTHETIC', 'prefix': 'TEST',
                       'target_cvr': None,
                       'leads': [{'date': '2026-01-01', 'platform': 'Meta',
                                  'marketer': 'Untagged', 'label': 'SYNTHETIC',
                                  'campaign': 'SYNTHETIC', 'signed': i % 2}
                                 for i in range(count)]} for tid in IDS]}


class ValidationTests(unittest.TestCase):
    def test_complete_payload_counts_and_rejects_missing_or_duplicate_torts(self):
        self.assertTrue(callable(getattr(publisher, 'validate', None)), 'validator missing')
        good = payload()
        self.assertEqual(publisher.validate(good), {tid: (10, 5) for tid in IDS})
        for torts in (good['torts'][:-1], good['torts'][:-1] + [good['torts'][0]]):
            with self.subTest(torts=len(torts)), self.assertRaisesRegex(publisher.PublishError, 'torts'):
                publisher.validate(dict(good, torts=torts))

    def test_invalid_schema_dates_signed_and_empty_aggregates_fail_closed(self):
        bads = [None, {}, dict(payload(), extra='forbidden')]
        for field, value in [('date', '2026-02-30'), ('date', '20260101'),
                             ('signed', 2), ('signed', True), ('label', None),
                             ('email', 'synthetic@example.invalid')]:
            bad = payload()
            bad['torts'][0]['leads'][0][field] = value
            bads.append(bad)
        bads.extend([payload(0), dict(payload(), generated_at='2026-01-01 10:00 EST')])
        bad = payload()
        for tort in bad['torts']:
            for row in tort['leads']:
                row['signed'] = 0
        bads.append(bad)
        for bad in bads:
            with self.subTest(kind=type(bad).__name__), self.assertRaises(publisher.PublishError):
                publisher.validate(bad)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name).resolve()
        self.old = json.dumps(payload()).encode()
        (self.repo / 'bp_utm_data.json').write_bytes(self.old)
        (self.repo / 'data.json').write_bytes(b'UNVERIFIED FINANCIALS - DO NOT TOUCH')

    def builder(self, data=None, body=None):
        code = ('import json, os\nOUT_PATH = "MUST_BE_OVERRIDDEN"\n'
                'def main():\n'
                '    assert os.environ["HOME"] == "/Users/andyoc"\n')
        code += body or ('    with open(OUT_PATH, "w") as f:\n'
                         '        json.dump(' + repr(data) + ', f)\n')
        (self.repo / 'build_bp_utm_data.py').write_text(code)

    def test_private_candidate_build_preserves_old_files_on_every_failure(self):
        self.assertTrue(callable(getattr(publisher, 'build_candidate', None)), 'private builder missing')
        good = payload()
        self.builder(good)
        self.assertEqual(json.loads(publisher.build_candidate(self.repo, self.old)), good)
        bads = [payload(6), dict(payload(), torts=payload()['torts'][:-1]),
                dict(payload(), generated_at='2020-01-01T00:00:00+00:00'),
                dict(payload(), generated_at='2099-01-01T00:00:00+00:00')]
        for bad in bads:
            with self.subTest(kind='invalid output'):
                self.builder(bad)
                with self.assertRaises(publisher.PublishError):
                    publisher.build_candidate(self.repo, self.old)
        for body in ('    pass\n', '    raise RuntimeError("SENSITIVE SYNTHETIC DETAIL")\n',
                     '    open(OUT_PATH, "w").write("not json")\n'):
            self.builder(body=body)
            with self.assertRaises(publisher.PublishError) as error:
                publisher.build_candidate(self.repo, self.old)
            self.assertNotIn('SENSITIVE', str(error.exception))
        self.assertEqual((self.repo / 'bp_utm_data.json').read_bytes(), self.old)
        self.assertEqual((self.repo / 'data.json').read_bytes(), b'UNVERIFIED FINANCIALS - DO NOT TOUCH')
        self.assertFalse((self.repo / '__pycache__').exists())


class GitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.repo, self.remote = root / 'release', root / 'remote.git'
        self.repo.mkdir()
        self.env = dict(os.environ, HOME=str(root), GIT_CONFIG_GLOBAL=os.devnull,
                        GIT_CONFIG_NOSYSTEM='1', GIT_ALLOW_PROTOCOL='file',
                        GIT_TERMINAL_PROMPT='0')
        env_patch = mock.patch.dict(os.environ, self.env, clear=True)
        env_patch.start()
        self.addCleanup(env_patch.stop)
        for name, value in [('HOME', str(root)), ('RELEASE_REPO', self.repo),
                            ('ORIGIN', str(self.remote)), ('BRANCH', 'recovery/test')]:
            patcher = mock.patch.object(publisher, name, value, create=True)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.git('init', '--bare', str(self.remote))
        self.git('init')
        self.git('config', 'user.name', 'Synthetic Test')
        self.git('config', 'user.email', 'synthetic@example.invalid')
        self.git('checkout', '-b', 'recovery/test')
        self.old = json.dumps(payload()).encode()
        (self.repo / 'bp_utm_data.json').write_bytes(self.old)
        (self.repo / 'data.json').write_bytes(b'UNVERIFIED FINANCIALS')
        self.git('add', 'bp_utm_data.json', 'data.json')
        self.git('commit', '-m', 'synthetic baseline')
        self.git('remote', 'add', 'origin', str(self.remote))
        self.git('push', 'origin', 'HEAD:main')
        self.git('fetch', 'origin', 'main')

    def git(self, *args):
        # All Git, including publisher subprocesses, is confined to file:// transport.
        return subprocess.run(['git', *args], cwd=self.repo, env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout

    def test_unpublished_history_is_data_only_even_if_other_changes_reverted(self):
        (self.repo / 'data.json').write_bytes(b'UNSAFE AHEAD CHANGE')
        self.git('add', 'data.json')
        self.git('commit', '-m', 'unrelated unpublished change')
        self.git('revert', '--no-edit', 'HEAD')
        with self.assertRaisesRegex(publisher.PublishError, 'ahead|unpublished'):
            publisher.preflight(self.repo)

    def test_remote_ahead_fails_without_resetting_local_history(self):
        original = self.git('rev-parse', 'HEAD')
        self.git('commit', '--allow-empty', '-m', 'remote advance')
        self.git('push', 'origin', 'HEAD:main')
        self.git('checkout', '-B', 'recovery/test', original.decode().strip())
        with self.assertRaisesRegex(publisher.PublishError, 'ahead|ancestry'):
            publisher.preflight(self.repo)
        self.assertEqual(self.git('rev-parse', 'HEAD'), original)

    def test_failed_push_is_nonzero_and_clean_pending_commit_retried_without_build(self):
        self.assertTrue(callable(getattr(publisher, 'refresh', None)), 'publisher missing')
        good = payload(12)
        builder = self.repo / 'build_bp_utm_data.py'
        builder.write_text('import json\nOUT_PATH = "OVERRIDE_REQUIRED"\ndef main():\n'
                           '    with open(OUT_PATH, "w") as f: json.dump(' + repr(good) + ', f)\n')
        self.git('add', 'build_bp_utm_data.py')
        self.git('commit', '-m', 'reviewed synthetic builder')
        self.git('push', 'origin', 'HEAD:main')
        hook = self.remote / 'hooks' / 'pre-receive'
        hook.write_text('#!/bin/sh\nexit 1\n')
        hook.chmod(0o700)
        with mock.patch.object(publisher, 'verify_publication') as verify:
            with self.assertRaisesRegex(publisher.PublishError, 'push'):
                publisher.refresh(self.repo)
            verify.assert_not_called()
            pending = self.git('rev-parse', 'HEAD')
            self.assertEqual(self.git('status', '--porcelain'), b'')
            self.assertEqual(self.git('diff', '--name-only', 'origin/main..HEAD').strip(), b'bp_utm_data.json')
            hook.unlink()
            with mock.patch.object(publisher, 'build_candidate', side_effect=AssertionError('Pending must retry before rebuilding')):
                publisher.refresh(self.repo)
            self.assertEqual(self.git('rev-parse', 'HEAD'), pending)
            remote_head = self.git('--git-dir=' + str(self.remote), 'rev-parse', 'main')
            self.assertEqual(remote_head, pending)
            verify.assert_called_once_with(self.repo, pending.decode().strip(), (self.repo / 'bp_utm_data.json').read_bytes())
        self.assertEqual((self.repo / 'data.json').read_bytes(), b'UNVERIFIED FINANCIALS')

    def test_git_hooks_cannot_rebuild_financials(self):
        candidate = json.dumps(payload(12)).encode()
        hooks = self.repo / '.git' / 'hooks'
        hook = hooks / 'pre-commit'
        hook.write_text('#!/bin/sh\nprintf "UNSAFE HOOK" > data.json\n')
        hook.chmod(0o700)
        with mock.patch.object(publisher, 'build_candidate', return_value=candidate), mock.patch.object(publisher, 'verify_publication'):
            with self.assertRaisesRegex(publisher.PublishError, 'hook'):
                publisher.refresh(self.repo)
        self.assertEqual((self.repo / 'data.json').read_bytes(), b'UNVERIFIED FINANCIALS')

    def test_git_environment_redirection_rejected_before_commands(self):
        with mock.patch.dict(os.environ, {'GIT_WORK_TREE': str(self.remote)}), mock.patch.object(publisher, 'git') as run:
            with self.assertRaisesRegex(publisher.PublishError, 'environment'):
                publisher.preflight(self.repo)
            run.assert_not_called()

    def test_preflight_accepts_only_clean_release_canonical_remote(self):
        self.assertTrue(callable(getattr(publisher, 'preflight', None)), 'Git preflight missing')
        self.assertEqual(publisher.preflight(self.repo), self.old)
        self.git('remote', 'set-url', 'origin', str(self.remote) + '-wrong')
        with self.assertRaisesRegex(publisher.PublishError, 'origin'):
            publisher.preflight(self.repo)
        self.git('remote', 'set-url', 'origin', str(self.remote))
        for staged in (False, True):
            (self.repo / 'data.json').write_bytes(b'UNRELATED DIRTY FINANCIALS')
            if staged:
                self.git('add', 'data.json')
            with self.assertRaisesRegex(publisher.PublishError, 'dirty|staged'):
                publisher.preflight(self.repo)
        self.assertEqual((self.repo / 'bp_utm_data.json').read_bytes(), self.old)


class VerificationTests(unittest.TestCase):
    def test_deployment_requires_built_head_and_exact_public_sha256(self):
        self.assertTrue(callable(getattr(publisher, 'verify_publication', None)), 'verification missing')
        raw = b'SYNTHETIC PUBLIC BYTES'
        head = 'a' * 40
        cases = [({'status': 'built', 'commit': head}, raw, True),
                 ({'status': 'built', 'commit': 'b' * 40}, raw, False),
                 ({'status': 'building', 'commit': head}, raw, False),
                 ({'status': 'built', 'commit': head}, b'WRONG BYTES', False)]
        for info, served, passes in cases:
            def transport(command, **kwargs):
                if command[0] == 'gh':
                    return subprocess.CompletedProcess(command, 0, json.dumps(info).encode(), b'')
                if command[0] == 'curl':
                    return subprocess.CompletedProcess(command, 0, served, b'')
                self.fail('Unexpected command in offline verification test')
            with self.subTest(info=info, passes=passes), mock.patch.object(publisher.subprocess, 'run', side_effect=transport):
                if passes:
                    publisher.verify_publication(Path('/synthetic'), head, raw, timeout=0)
                else:
                    with self.assertRaisesRegex(publisher.PublishError, 'Pages|hash|verification'):
                        publisher.verify_publication(Path('/synthetic'), head, raw, timeout=0)


class EntryTests(unittest.TestCase):
    def test_cron_subprocess_environment_has_fixed_home_and_tool_paths(self):
        with mock.patch.dict(os.environ, {'HOME': '/invalid-cron-home', 'PATH': '/usr/bin:/bin'}):
            with mock.patch.object(publisher.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0, b'', b'')) as run:
                publisher.git(Path('/synthetic'), 'status')
            env = run.call_args.kwargs['env']
            self.assertEqual(env['HOME'], '/Users/andyoc')
            self.assertIn('/opt/homebrew/bin', env['PATH'].split(':'))
            self.assertEqual(env['GIT_TERMINAL_PROMPT'], '0')

    def test_private_nonblocking_lock_and_quiet_cli_error_exit(self):
        self.assertTrue(callable(getattr(publisher, 'main', None)), 'CLI missing')
        self.assertTrue(callable(getattr(publisher, 'publication_lock', None)), 'lock missing')
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(publisher, 'HOME', tmp):
            cache = Path(tmp) / '.cache' / 'tcs-bp-utm-publisher'
            with publisher.publication_lock():
                self.assertEqual(cache.stat().st_mode & 0o777, 0o700)
                with self.assertRaisesRegex(publisher.PublishError, 'running|lock'):
                    with publisher.publication_lock():
                        self.fail('concurrent publisher allowed')
            for quiet in (False, True):
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(publisher, 'refresh', return_value={'status': 'verified'}) as refresh, contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(publisher.main(['--quiet-success'] if quiet else []), 0)
                    refresh.assert_called_once_with(Path(publisher.__file__).resolve().parent)
                self.assertEqual(err.getvalue(), '')
                self.assertEqual(bool(out.getvalue()), not quiet)
            for failure in (publisher.PublishError('Git push failed; review existing auth.'),
                            RuntimeError('SENSITIVE SYNTHETIC CONTENT'),
                            publisher.PublishError('Publication verification failed: hash mismatch')):
                out, err = io.StringIO(), io.StringIO()
                with mock.patch.object(publisher, 'refresh', side_effect=failure), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    self.assertEqual(publisher.main(['--quiet-success']), 1)
                self.assertEqual(out.getvalue(), '')
                self.assertIn('failed', err.getvalue().lower())
                self.assertNotIn('SENSITIVE', err.getvalue())


if __name__ == '__main__':
    unittest.main()
