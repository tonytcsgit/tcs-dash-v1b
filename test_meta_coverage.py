"""Synthetic credentials and responses only; no live APIs in this test module."""
import copy
import datetime as dt
import importlib
import importlib.util
import json
import unittest
from unittest.mock import patch

D = dt.date(2026, 9, 13)
A, B, C = ('EAA' + c * 32 for c in 'ABC')

class CoverageTests(unittest.TestCase):
    def test_failed_canonical_read_blocks_full_totals_even_when_local_pull_succeeds(self):
        m = importlib.import_module('main_sources')
        def fetch(url, headers=None):
            if '/me/adaccounts' in url:
                return {'data': [dict(id='act_1', currency='USD')]}
            return {'data': [dict(account_id='act_1', campaign_id='c', campaign_name='ILM', account_currency='USD', spend='8')]}
        src = m.MetaSpendSource([A], {'USD': 1}, fetch=fetch,
            token_pool_ledger={'complete': False, 'warnings': ['Canonical source unavailable']})
        src.prime(D, D)
        self.assertFalse(src.ledger['complete'])
        self.assertIsNone(src.spend('ILM')['spend'])
        self.assertEqual(src.spend('ILM')['observed_spend_usd'], 8)
        self.assertIn('Canonical source unavailable', src.ledger['warnings'])

    def test_union_recovers_accounts_once_and_keeps_historical_gaps_unknown(self):
        import inspect
        m = importlib.import_module('main_sources')
        self.assertIn('token_origins', inspect.signature(m.MetaSpendSource).parameters)
        calls = []
        def fetch(url, headers=None):
            token = headers['Authorization'].split(' ', 1)[1]
            calls.append(url)
            if '/me/adaccounts' in url:
                if token == B:
                    raise m.SourceError('HTTP 400')
                ids = ['act_1', 'act_2'] if token == C else ['act_1']
                return {'data': [dict(id=a, currency='USD') for a in ids]}
            aid = 'act_2' if '/act_2/' in url else 'act_1'
            row = dict(account_id=aid, campaign_id='c', campaign_name='ILM PPE CBO',
                       account_currency='USD', spend='4.5' if aid == 'act_2' else '8')
            return {'data': [row, row]}
        origins = {A: ['local'], B: ['local'], C: ['canonical_sheet']}
        src = m.MetaSpendSource([A, B, C], {'USD': 1}, fetch=fetch,
            token_origins=origins, token_pool_ledger={'complete': True}, expected_accounts=['act_3'])
        src.prime(D, D)
        self.assertEqual(src.ledger['accounts_total'], 2)
        self.assertEqual(src.ledger['local_accounts_total'], 1)
        self.assertEqual(src.ledger['canonical_accounts_total'], 2)
        self.assertEqual(src.ledger['accounts_added_by_canonical'], ['act_2'])
        self.assertEqual(src.ledger['unresolved_accounts'], ['act_3'])
        self.assertEqual(src.ledger['discovery_failures'], 1)
        self.assertFalse(src.ledger['complete'])
        self.assertIsNone(src.spend('ILM')['spend'])
        self.assertEqual(src.spend('ILM')['observed_spend_usd'], 12.5)
        self.assertEqual(sum('/act_1/insights' in x for x in calls), 1)
        self.assertEqual(sum('/act_2/insights' in x for x in calls), 1)
        self.assertEqual(len(src.rows), 2)
        added = next(a for a in src.ledger['account_coverage'] if a['account_id']=='act_2')
        self.assertEqual(added['insight_status'], 'ok')
        self.assertEqual(added['observed_bp_spend_usd']['ILM'], 4.5)
        for token in (A, B, C):
            self.assertNotIn(token, json.dumps(src.ledger))


class IntegrationTests(unittest.TestCase):
    def test_live_builder_dispatch_uses_sheet_union_and_scans_all_credentials_for_leaks(self):
        from unittest.mock import mock_open
        m = importlib.import_module('build_dashboard_data')
        cfg = m.load_config()
        cfg.update(meta_token_sheet='fixture', meta_token_range="'Sheet1'!A1:Z2000", meta_expected_accounts=[])
        class Sheet:
            def __init__(self, sheet_id):
                self.reader = lambda _: [['new token', C]]
            def tab_counts(self, *args):
                return dict(total_leads=0, payable=0, signed=0, billing_fields=[])
        def fetch(url, headers=None):
            token = (headers or {})['Authorization'].split(' ', 1)[1]
            if '/me/adaccounts' in url:
                return {'data': [dict(id='act_2' if token == C else 'act_1', currency='USD')]}
            aid = 'act_2' if '/act_2/' in url else 'act_1'
            return {'data': [dict(account_id=aid, campaign_id='c', campaign_name='ILM', account_currency='USD', spend='8')]}
        local = {'META_ACCOUNTS': {'one': {'access_token': A}}}
        with patch('builtins.open', mock_open(read_data=json.dumps(local))), \
             patch('main_sources.SheetsLeadSource', Sheet), \
             patch('main_sources.HttpClient', return_value=fetch), \
             patch('main_sources.fetch_fx', return_value=({'USD': 1}, {})), \
             patch('main_sources.YouTubeSpendSource') as yt, patch('main_sources.LPLeadSource') as lp:
            yt.return_value.spend.return_value = {'spend': None, 'complete': False}
            lp.return_value.lead_count.return_value = {'leads': 0}
            leads, costs, lps, ledger, sensitive = m.run_live(cfg, D, D)
        self.assertEqual(ledger['meta']['accounts_added_by_canonical'], ['act_2'])
        self.assertEqual(costs['ILM']['observed_spend_usd'], 16)
        self.assertIn(C, sensitive)
        self.assertNotIn(C, json.dumps(ledger))


class TokenPoolTests(unittest.TestCase):
    def test_unavailable_empty_truncated_or_malformed_sheet_cannot_claim_complete(self):
        m = importlib.import_module('meta_token_pool')
        cfg = {'meta_token_sheet': 'fixture', 'meta_token_range': "'Sheet1'!A1:Z2000"}
        def failed(_):
            raise RuntimeError('sensitive test error ' + C)
        for reader in (failed, lambda _: [], lambda _: [['note']] * 2000,
                       lambda _: [['token', C], ['bad', 'EAA corrupted token']]):
            with self.subTest(reader=reader):
                tokens, origins, ledger = m.load_meta_token_pool({'one': {'access_token': A}}, cfg, reader)
                self.assertFalse(ledger['complete'])
                self.assertTrue(ledger['warnings'])
                self.assertIn(A, tokens)
                self.assertNotIn(C, json.dumps(ledger))

    def test_readonly_union_preserves_local_entries_and_deduplicates_sheet_tokens(self):
        self.assertIsNotNone(importlib.util.find_spec('meta_token_pool'), 'read-only pool loader missing')
        m = importlib.import_module('meta_token_pool')
        local = {'one': {'access_token': A}, 'repeat': {'access_token': A}, 'two': {'access_token': B}, 'no_token': {}}
        before = copy.deepcopy(local)
        rows = [['Label', 'Access Token'], ['existing', A], ['new', C], ['ordinary note'], ['duplicate', C]]
        calls = []
        def reader(range_):
            calls.append(range_)
            return rows
        tokens, origins, ledger = m.load_meta_token_pool(local, {'meta_token_sheet': 'fixture', 'meta_token_range': "'Sheet1'!A1:Z2000"}, reader)
        self.assertEqual(set(tokens), {A, B, C})
        self.assertEqual(local, before)
        self.assertEqual(len(calls), 1)
        self.assertEqual(set(origins[A]), {'local', 'canonical_sheet'})
        self.assertEqual(origins[C], ['canonical_sheet'])
        self.assertEqual((ledger['local_unique_tokens'], ledger['canonical_unique_tokens'], ledger['union_unique_tokens']), (2, 2, 3))
        self.assertTrue(ledger['complete'])
        self.assertIsNotNone(ledger['fetched_at'])
        for token in (A, B, C):
            self.assertNotIn(token, json.dumps(ledger))
