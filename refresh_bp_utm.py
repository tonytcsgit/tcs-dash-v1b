#!/usr/bin/python3
"""Fail-closed BP UTM publisher. Never builds or stages main financial data.json."""
import argparse
from contextlib import contextmanager
import fcntl
import sys
import datetime as dt
import hashlib
import time
import json
import os
from pathlib import Path
import subprocess
import tempfile

ARTIFACT = 'bp_utm_data.json'
HOME = '/Users/andyoc'
PYTHON = '/usr/bin/python3'
RELEASE_REPO = Path('/Users/andyoc/tcs-dashboard-builds/v1b-release')
ORIGIN = 'https://github.com/tonytcsgit/tcs-dash-v1b.git'
BRANCH = 'recovery/bp-utm-layout-20260914'

EXPECTED_TORTS = frozenset(('sma', 'hm', 'end', 'pp', 'pqt', 'sil', 'jdc',
                            'talc', 'bm', 'tvm', 'chlor'))
LEAD_FIELDS = {'date', 'platform', 'marketer', 'label', 'campaign', 'signed'}
TORT_FIELDS = {'tort_id', 'tort_name', 'prefix', 'target_cvr', 'leads'}


class PublishError(RuntimeError):
    """Sanitized, operator-actionable failure; never include source rows or command output."""


def validate(data):
    try:
        if not isinstance(data, dict) or set(data) != {'generated_at', 'torts'}:
            raise ValueError()
        stamp = dt.datetime.fromisoformat(data['generated_at'].replace('Z', '+00:00'))
        if stamp.tzinfo is None:
            raise ValueError()
        torts = data['torts']
        if not isinstance(torts, list) or any(not isinstance(t, dict) for t in torts):
            raise ValueError()
        ids = [t.get('tort_id') for t in torts]
        if len(ids) != len(EXPECTED_TORTS) or set(ids) != EXPECTED_TORTS:
            raise PublishError('Validation: expected all 11 unique torts; inspect builder sources.')
        counts = {}
        for t in torts:
            if set(t) != TORT_FIELDS or not isinstance(t['leads'], list):
                raise ValueError()
            for r in t['leads']:
                if not isinstance(r, dict) or set(r) != LEAD_FIELDS:
                    raise ValueError()
                if any(not isinstance(r[k], str) for k in LEAD_FIELDS - {'signed'}):
                    raise ValueError()
                if dt.date.fromisoformat(r['date']).isoformat() != r['date']:
                    raise ValueError()
                if type(r['signed']) is not int or r['signed'] not in (0, 1):
                    raise ValueError()
            counts[t['tort_id']] = (len(t['leads']), sum(r['signed'] for r in t['leads']))
        if not sum(c[0] for c in counts.values()) or not sum(c[1] for c in counts.values()):
            raise ValueError()
        return counts
    except (KeyError, TypeError, ValueError, AttributeError):
        raise PublishError('Validation: invalid schema, ISO timestamp/date, signed flag or empty totals; inspect builder.') from None


def build_candidate(repo, baseline):
    """Import the reviewed builder without executing its __main__; redirect its only output."""
    started = dt.datetime.now(dt.timezone.utc)
    bootstrap = ('import importlib.util, sys; '
                 'sys.path.insert(0, sys.argv[1]); '
                 's=importlib.util.spec_from_file_location("bp_builder", sys.argv[1]+"/build_bp_utm_data.py"); '
                 'm=importlib.util.module_from_spec(s); s.loader.exec_module(m); '
                 'm.OUT_PATH=sys.argv[2]; m.main()')
    try:
        # No bytecode or builder logs are written into the public repository.
        with tempfile.TemporaryDirectory(prefix='bp-utm-candidate-') as tmp:
            candidate = Path(tmp) / ARTIFACT
            result = subprocess.run([PYTHON, '-B', '-c', bootstrap, str(repo), str(candidate)],
                                    cwd=tmp, env=dict(os.environ, HOME=HOME,
                                                     PYTHONDONTWRITEBYTECODE='1'),
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                    timeout=600)
            if result.returncode or not candidate.is_file() or candidate.is_symlink():
                raise PublishError('Build failed or produced no regular candidate; inspect BP source/builder privately. Old artifact preserved.')
            raw = candidate.read_bytes()
        data = json.loads(raw)
        counts = validate(data)
        previous = validate(json.loads(baseline))
        stamp = dt.datetime.fromisoformat(data['generated_at'].replace('Z', '+00:00'))
        if stamp < started - dt.timedelta(seconds=2) or stamp > dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=5):
            raise PublishError('Validation: stale/future generation timestamp; require a fresh ISO source observation.')
        for tid in EXPECTED_TORTS:
            if any(new * 5 < old * 4 for new, old in zip(counts[tid], previous[tid])):
                raise PublishError('Validation: per-tort lead/signed count drop exceeds 20%; review sources before publishing.')
        return raw
    except (OSError, ValueError, subprocess.TimeoutExpired):
        raise PublishError('Build/read failed or candidate JSON invalid; inspect builder privately. Old artifact preserved.') from None


def git(repo, *args):
    try:
        result = subprocess.run(['git', *args], cwd=repo,
                                env=dict(os.environ, HOME=HOME, GIT_TERMINAL_PROMPT='0',
                                         PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
                                         GIT_ASKPASS='/usr/bin/false', SSH_ASKPASS='/usr/bin/false'),
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
    except (OSError, subprocess.TimeoutExpired):
        raise PublishError('Git command unavailable/timed out; check Git and existing authentication privately.') from None
    if result.returncode:
        raise PublishError('Git ' + args[0] + ' failed; inspect repository/authentication privately and retry (no reset/force).')
    return result.stdout


def preflight(repo):
    if any(key in os.environ for key in ('GIT_DIR', 'GIT_WORK_TREE', 'GIT_INDEX_FILE',
                                        'GIT_COMMON_DIR', 'GIT_OBJECT_DIRECTORY',
                                        'GIT_ALTERNATE_OBJECT_DIRECTORIES', 'GIT_CONFIG_COUNT')):
        raise PublishError('Unsafe Git environment override; clear repository redirection before refresh.')
    if Path(repo).resolve() != RELEASE_REPO.resolve():
        raise PublishError('Repository is not the approved release worktree; do not run from original worktree.')
    hooks = Path(git(repo, 'rev-parse', '--git-path', 'hooks').decode().strip())
    if not hooks.is_absolute():
        hooks = Path(repo) / hooks
    if hooks.is_dir() and any(p.is_file() and not p.name.endswith('.sample') and os.access(p, os.X_OK) for p in hooks.iterdir()):
        raise PublishError('Executable Git hook requires review before automated publication; hooks are not bypassed.')
    if git(repo, 'branch', '--show-current').decode().strip() != BRANCH:
        raise PublishError('Wrong release branch; operator review required.')
    for args in (('remote', 'get-url', '--all', 'origin'),
                 ('remote', 'get-url', '--push', '--all', 'origin')):
        if git(repo, *args).decode().splitlines() != [ORIGIN]:
            raise PublishError('Noncanonical origin/push URL; operator must review remote configuration.')
    if git(repo, 'diff', '--name-only', '-z') or git(repo, 'diff', '--cached', '--name-only', '-z'):
        raise PublishError('Repository has dirty/staged tracked files; preserve and review before refresh.')
    git(repo, 'fetch', '--no-tags', 'origin', 'refs/heads/main:refs/remotes/origin/main')
    try:
        git(repo, 'merge-base', '--is-ancestor', 'refs/remotes/origin/main', 'HEAD')
    except PublishError:
        raise PublishError('Remote main is ahead/diverged or ancestry unavailable; operator review required, never reset.') from None
    for commit in git(repo, 'rev-list', 'refs/remotes/origin/main..HEAD').decode().splitlines():
        if len(git(repo, 'rev-list', '--parents', '-n', '1', commit).split()) != 2:
            raise PublishError('Unpublished merge/root commit rejected; only linear data-only ahead commits allowed.')
        changed = set(git(repo, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z',
                          '--no-renames', commit).split(b'\0')) - {b''}
        if changed - {ARTIFACT.encode()}:
            raise PublishError('Unpublished ahead commit touches other files; parent must publish reviewed code separately.')
    return git(repo, 'show', 'refs/remotes/origin/main:' + ARTIFACT)


def verify_publication(repo, head, raw, timeout=180):
    """Success means both GitHub Pages built HEAD and the CDN serves its exact bytes."""
    deadline = time.monotonic() + timeout
    expected_hash = hashlib.sha256(raw).digest()
    reason = 'GitHub Pages has not built this HEAD'
    while True:
        try:
            env = dict(os.environ, HOME=HOME, GH_PROMPT_DISABLED='1', GH_NO_UPDATE_NOTIFIER='1')
            info = subprocess.run(['gh', 'api', '--hostname', 'github.com',
                                   'repos/tonytcsgit/tcs-dash-v1b/pages/builds/latest'],
                                  cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                  timeout=max(0.01, min(20, deadline - time.monotonic())))
            build = json.loads(info.stdout) if info.returncode == 0 else {}
            if build.get('status') == 'built' and build.get('commit') == head:
                reason = 'public artifact hash has not matched the committed bytes'
                remaining = max(0.01, min(20, deadline - time.monotonic()))
                served = subprocess.run(['curl', '--fail', '--silent', '--show-error',
                                         '--location', '--proto', '=https', '--proto-redir', '=https',
                                         '--max-time', str(remaining), '-H', 'Cache-Control: no-cache',
                                         'https://tonytcsgit.github.io/tcs-dash-v1b/' + ARTIFACT + '?refresh=' + head],
                                        cwd=repo, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                        timeout=remaining)
                if served.returncode == 0 and hashlib.sha256(served.stdout).digest() == expected_hash:
                    return
        except (OSError, ValueError, AttributeError, subprocess.TimeoutExpired):
            reason = 'Pages/public verification request failed; check gh auth and connectivity privately'
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise PublishError('Publication verification failed: ' + reason + '; retry without force/reset.')
        time.sleep(min(5, remaining))


def refresh(repo):
    baseline = preflight(repo)
    head = git(repo, 'rev-parse', 'HEAD').decode().strip()
    pending = bool(git(repo, 'rev-list', 'refs/remotes/origin/main..HEAD').strip())
    if pending:
        # Retry previously committed data BEFORE a new source pull, even if sources are now down.
        raw = git(repo, 'show', 'HEAD:' + ARTIFACT)
        counts, old_counts = validate(json.loads(raw)), validate(json.loads(baseline))
        for tid in EXPECTED_TORTS:
            if any(new * 5 < old * 4 for new, old in zip(counts[tid], old_counts[tid])):
                raise PublishError('Pending data count drop exceeds 20%; operator review required.')
    else:
        raw = build_candidate(repo, baseline)
        if preflight(repo) != baseline or git(repo, 'rev-parse', 'HEAD').decode().strip() != head:
            raise PublishError('Repository changed during build; candidate not installed, retry after review.')
        if raw != git(repo, 'show', 'HEAD:' + ARTIFACT):
            # Private temporary directory; os.replace fails closed on cross-device moves.
            with tempfile.TemporaryDirectory(prefix='bp-utm-install-') as tmp:
                candidate = Path(tmp) / ARTIFACT
                with candidate.open('wb') as handle:
                    handle.write(raw)
                    handle.flush()
                    os.fsync(handle.fileno())
                candidate.chmod(0o644)
                os.replace(candidate, repo / ARTIFACT)
            git(repo, 'add', '--', ARTIFACT)
            staged = set(git(repo, 'diff', '--cached', '--name-only', '-z').split(b'\0')) - {b''}
            if staged != {ARTIFACT.encode()}:
                raise PublishError('Unexpected staged files after build; do not commit, review index privately.')
            git(repo, 'commit', '--only', '-m', 'data: refresh BP UTM only', '--', ARTIFACT)
    # Unchanged fresh bytes and clean pending commits still reach the push boundary.
    preflight(repo)
    head = git(repo, 'rev-parse', 'HEAD').decode().strip()
    if git(repo, 'show', 'HEAD:' + ARTIFACT) != raw:
        raise PublishError('Committed artifact differs from validated bytes; refuse push, review locally.')
    git(repo, 'push', 'origin', 'HEAD:refs/heads/main')
    verify_publication(repo, head, raw)
    return {'commit': head, 'sha256': hashlib.sha256(raw).hexdigest(),
            'status': 'pending_commit_published' if pending else 'fresh_published'}


@contextmanager
def publication_lock():
    cache = Path(HOME) / '.cache' / 'tcs-bp-utm-publisher'
    cache.mkdir(parents=True, exist_ok=True, mode=0o700)
    if cache.is_symlink():
        raise PublishError('Unsafe cache symlink; review private publisher lock directory.')
    cache.chmod(0o700)
    fd = os.open(str(cache / 'refresh.lock'), os.O_CREAT | os.O_RDWR | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'w') as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise PublishError('Refresh already running (private lock held); retry after it completes.') from None
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quiet-success', action='store_true', help='Suppress verified success; failures still exit nonzero.')
    args = parser.parse_args(argv)
    try:
        with publication_lock():
            receipt = refresh(Path(__file__).resolve().parent)
        if not args.quiet_success:
            print(json.dumps(receipt, sort_keys=True))
        return 0
    except PublishError as error:
        print('BP UTM refresh failed: ' + str(error), file=sys.stderr)
    except Exception:
        print('BP UTM refresh failed unexpectedly; inspect local files, permissions and environment privately before retrying.', file=sys.stderr)
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
