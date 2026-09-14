"""Synthetic regression fixtures only; live validation is a separate CLI run."""
import datetime as dt
import importlib
import unittest

D = dt.date(2026, 9, 14)

class SheetsTests(unittest.TestCase):
    def test_broken_hm_uses_cached_exact_raw_and_preserves_eligibility(self):
        m = importlib.import_module('main_sources')
        calls = []
        raw = [['banner'], ['Created_Date', 'Case_Type', 'Status', 'Injury_Tier'],
               ['2026-09-14', 'Hernia Mesh', 'Signed', 'HQ'],
               ['2026-09-14', 'Hernia Mesh', 'DMC', ''],
               ['2026-09-14', 'Hernia Mesh', 'Pending', ''],
               ['2026-09-14', 'Hernia Mesh', 'Rejected - Existing Contact', ''],
               ['2026-09-14', 'Breast Mesh', 'Signed', '']]
        def reader(range_):
            calls.append(range_)
            return raw if 'Leads Last 13 Months' in range_ else [['Created_Date concatenated Status']]
        src = m.SheetsLeadSource('synthetic', reader=reader)
        result = src.tab_counts('Hernia Mesh', D, D)
        self.assertEqual((result['total_leads'], result['payable'], result['signed']), (4, 3, 1))
        self.assertEqual(result['source_tab'], 'Leads Last 13 Months')
        self.assertEqual(result['cohort_max_date'], '2026-09-14')
        self.assertIsNotNone(result['fetched_at'])
        src.tab_counts('Breast Mesh', D, D)
        self.assertEqual(sum('Leads Last 13 Months' in x for x in calls), 1)
        with self.assertRaises(m.SourceError):
            src.tab_counts('No such case', D, D)

class MetricTests(unittest.TestCase):
    def test_pricing_and_missing_finance_preserve_counts_and_cost_sign_definition(self):
        m = importlib.import_module('build_dashboard_data')
        cfg = m.load_config()
        self.assertEqual([cfg['payouts'][x] for x in ('SMA', 'PowerPort', 'Paraquat', 'ILM')], [70, 170, 315, 670])
        lead = dict(payable=3, signed=1, total_leads=4, billing_fields=[{}]*3)
        hm = m.tort_metrics('Hernia Mesh', lead, 90, cfg, D)
        self.assertEqual((hm['payable_leads'], hm['signed'], hm['revenue'], hm['margin_pct']), (3, 1, None, None))
        self.assertFalse(hm['data_ok'])
        pp = m.tort_metrics('PowerPort', lead, 90, cfg, D)
        self.assertEqual((pp['revenue'], pp['cost_per_sign']), (510, 90))
        broken = m.tort_metrics('PowerPort', None, None, cfg, D)
        self.assertIsNone(broken['payable_leads'])
        self.assertIsNone(broken['revenue'])
        missingcost = m.tort_metrics('PowerPort', lead, None, cfg, D)
        self.assertEqual(missingcost['revenue'], 510)
        self.assertIsNone(missingcost['margin_pct'])
        with self.assertRaises(ValueError):
            m.tort_metrics('PowerPort', lead, 90, cfg, dt.date(2026, 9, 6))
        with self.assertRaises(ValueError):
            m.validate_config(dict(cfg, bp_torts={'SMA': {'src': 'bq'}}))

class MetaTests(unittest.TestCase):
    def test_paginated_unique_accounts_insights_currencies_and_partial_failure(self):
        m = importlib.import_module('main_sources')
        calls = []
        def fetch(url, headers=None):
            calls.append(url)
            if '/me/adaccounts' in url:
                return {'data': [{'id': 'act_1', 'currency': 'NZD'}], 'paging': {'next': 'https://graph.facebook.com/v21.0/accounts2'}}
            if '/accounts2' in url:
                return {'data': [{'id': 'act_1', 'currency': 'NZD'}, {'id': 'act_2', 'currency': 'VND'}]}
            if '/act_1/insights' in url:
                return {'data': [{'campaign_id': 'c1', 'campaign_name': 'DD HM', 'spend': '10', 'account_currency': 'NZD'}], 'paging': {'next': 'https://graph.facebook.com/v21.0/insights2?access_token=SYNTHETIC'}}
            if '/insights2' in url:
                self.assertNotIn('access_token=', url)
                return {'data': [{'campaign_id': 'c1', 'campaign_name': 'DD HM', 'spend': '10', 'account_currency': 'NZD'}, {'campaign_id': 'c3', 'campaign_name': 'ILM BP', 'spend': '20', 'account_currency': 'NZD'}]}
            if '/act_2/insights' in url:
                return {'data': [{'campaign_id': 'c2', 'campaign_name': 'BP PQT', 'spend': '25000', 'account_currency': 'VND'}]}
            self.fail('Unexpected fixture URL')
        src = m.MetaSpendSource(['synthetic1', 'synthetic2'], {'USD': 1, 'NZD': .6, 'VND': .00004}, fetch=fetch)
        src.prime(D, D)
        self.assertEqual(src.ledger['accounts_total'], 2)
        self.assertEqual(src.ledger['accounts_queried'], 2)
        self.assertEqual(sum('/act_1/insights' in x for x in calls), 1)
        self.assertEqual(src.spend('Hernia Mesh')['spend'], 6)
        self.assertEqual(src.spend('ILM')['spend'], 12)
        self.assertEqual(src.spend('Paraquat')['spend'], 1)
        self.assertEqual(src.spend('SMA')['spend'], None)  # BP SMA is YouTube ONLY
        for name in ['Olympus HM', 'Pulaski ILM', 'Parker PP', 'Wagstaff PQT', 'Stinar SMA', 'ordinary mesh', 'chm sample']:
            self.assertIsNone(m.classify_bp(name), name)
        for name, tort in [('HM new', 'Hernia Mesh'), ('BP_ILM_CBO', 'ILM'), ('PQT', 'Paraquat'), ('PP new', 'PowerPort')]:
            self.assertEqual(m.classify_bp(name), tort)
        bad = m.MetaSpendSource(['synthetic'], {'USD': 1}, fetch=fetch)
        bad.prime(D, D)
        self.assertIsNone(bad.spend('Hernia Mesh')['spend'])
        self.assertFalse(bad.ledger['complete'])
        def failing(url, headers=None):
            if '/act_2/insights' in url:
                raise m.SourceError('synthetic failure')
            return fetch(url, headers)
        partial = m.MetaSpendSource(['synthetic'], {'NZD': .6, 'VND': .00004}, fetch=failing)
        partial.prime(D, D)
        self.assertIsNone(partial.spend('Hernia Mesh')['spend'])
        self.assertEqual(partial.spend('Hernia Mesh')['observed_spend_usd'], 6)

class OtherSourceTests(unittest.TestCase):
    def test_youtube_daily_dedup_attribution_and_calendar_not_max_date(self):
        m = importlib.import_module('main_sources')
        cfg = {'accounts': ['a'], 'approved_bp_campaign_ids': [], 'attribution_evidence': None}
        rows = [dict(account_id='a', campaign_id='c', day='2026-09-14', names=['BP SMA', 'BP SMA renamed'], cost=100, currencies=['USD'], timezones=['America/New_York'])]
        r = m.youtube_summary(rows, cfg, D, D)
        self.assertEqual(r['spend'], 100)
        self.assertIsNone(m.youtube_summary(rows, cfg, D-dt.timedelta(days=1), D)['spend'])
        self.assertIsNone(m.youtube_summary(rows+rows, cfg, D, D)['spend'])
        generic = [dict(rows[0], names=['SMA generic'])]
        self.assertIsNone(m.youtube_summary(generic, cfg, D, D)['spend'])
        other = [dict(rows[0], names=['Pulaski SMA'])]
        self.assertEqual(m.youtube_summary(other, cfg, D, D)['excluded_other_buyer_usd'], 100)
        self.assertIsNone(m.youtube_summary([dict(rows[0], currencies=['VND'])], cfg, D, D)['spend'])

class LPTests(unittest.TestCase):
    def test_partial_pages_use_response_cursor_and_dedup_not_last_id(self):
        m = importlib.import_module('main_sources')
        calls = []
        def fetch(url, headers=None):
            calls.append(url)
            lead = {'id': 'l1', 'lead_date_ms': 1789390800000}
            if 'search_after=cursor2' in url:
                return {'leads': [lead, dict(lead, id='l2')]}
            return {'leads': [lead], 'search_after': 'cursor2'}
        r = m.LPLeadSource('synthetic', fetch=fetch).lead_count(35624, D, D)
        self.assertEqual(r['leads'], 2)
        self.assertEqual(len(calls), 2)
        self.assertIn('search_after=cursor2', calls[1])
        self.assertIsNotNone(r['fetched_at'])

class AssemblyTests(unittest.TestCase):
    def test_shape_partial_counts_no_false_freshness_caps_or_profit(self):
        m = importlib.import_module('build_dashboard_data')
        cfg = m.load_config()
        lead = dict(payable=3, signed=1, total_leads=4, billing_fields=[{}]*3,
                    fetched_at='2026-09-14T01:00:00+00:00', cohort_max_date='2026-09-14', source_tab='test')
        leads = {t: lead for t in cfg['bp_torts']}
        costs = {t: {'spend': None, 'observed_spend_usd': 5, 'complete': False} for t in cfg['bp_torts']}
        out = m.assemble(cfg, D, D, leads, costs, {}, {}, {}, {})
        self.assertEqual(len(out['torts']), 11)
        self.assertEqual(len(out['buyers']), 5)
        self.assertIsNone(out['data_freshness']['leads_spend_sr'])
        self.assertIsNone(out['data_freshness']['retainers'])
        self.assertIsNone(out['data_freshness']['sr'])
        self.assertIsNone(out['company']['revenue'])
        self.assertIsNone(out['company']['spend'])
        self.assertIsNone(out['company']['gross_profit'])
        self.assertEqual(out['company']['payable_leads'], 24)
        self.assertFalse(out['financial_complete'])
        self.assertTrue(out['data_freshness']['stale_warnings'])
        self.assertFalse(m.validate_contract(out))
        for buyer in out['buyers']:
            for runway in buyer['runway']:
                self.assertIsNone(runway['pct'])
        with self.assertRaises(ValueError):
            m.check_output_path('/tmp/data.json')
        with self.assertRaises(ValueError):
            m.check_output_path(str(m.CONFIG_PATH.with_name('data.json')))
        # A partial adapter result cannot smuggle a number into a complete financial row.
        costs['ILM'] = {'spend': 10, 'observed_spend_usd': 10, 'complete': False}
        partial = m.assemble(cfg, D, D, leads, costs, {}, {}, {}, {})
        self.assertIsNone(next(r for r in partial['torts'] if r['tort']=='ILM')['spend'])
        import copy
        invalid_buyers = copy.deepcopy(out)
        invalid_buyers['buyers'].pop()
        self.assertTrue(m.validate_contract(invalid_buyers))
        out['torts'].pop()
        self.assertTrue(m.validate_contract(out))

class SafetyTests(unittest.TestCase):
    def test_sheet_phase_budget_stops_before_network(self):
        m = importlib.import_module('main_sources')
        src = m.SheetsLeadSource('synthetic')
        calls = []
        class Session:
            def get(self, *a, **k):
                calls.append(True)
                raise TimeoutError('synthetic')
        src.session = Session()
        src.deadline = 0
        with self.assertRaisesRegex(m.SourceError, 'deadline'):
            src._read_live('synthetic')
        self.assertEqual(calls, [])

    def test_import_has_no_source_reads_env_changes_or_network(self):
        import subprocess, sys
        code = """import sys, os, builtins, socket
before=dict(os.environ)
def forbidden(*a, **k): raise AssertionError('import attempted I/O')
builtins.open=forbidden
socket.socket=forbidden
import build_dashboard_data, main_sources
assert dict(os.environ)==before
"""
        from pathlib import Path
        p = subprocess.run([sys.executable, '-B', '-c', code], capture_output=True,
                           text=True, cwd=Path(__file__).resolve().parent)
        self.assertEqual(p.returncode, 0, p.stderr)

    def test_fx_provenance_staleness_and_nonfinite_values(self):
        m = importlib.import_module('main_sources')
        cfg = importlib.import_module('build_dashboard_data').load_config()
        today = dt.datetime.now(dt.timezone.utc).date().isoformat()
        rates, ledger = m.fetch_fx(cfg, fetch=lambda url: {'base': 'USD', 'date': today, 'rates': {'NZD': 2, 'VND': 25000}})
        self.assertEqual(rates['NZD'], .5)
        self.assertEqual(rates['VND'], .00004)
        self.assertEqual(ledger['rate_date'], today)
        self.assertIsNotNone(ledger['fetched_at'])
        rates, ledger = m.fetch_fx(cfg, fetch=lambda url: {'base': 'USD', 'date': '2000-01-01', 'rates': {'NZD': 2, 'VND': 25000}})
        self.assertEqual(rates, {'USD': 1.0})
        rates, ledger = m.fetch_fx(cfg, fetch=lambda url: {'base': 'USD', 'date': today, 'rates': {'NZD': float('nan'), 'VND': 25000}})
        self.assertEqual(rates, {'USD': 1.0})

    def test_hm_explicit_evidence_only_and_health_boundaries(self):
        m = importlib.import_module('build_dashboard_data')
        cfg = m.load_config()
        cfg.update(hm_billing_tier_map={'criteria_assignment': {'verified-label': 'hq', 'verified-standard': 'non_hq'}}, hm_billing_mapping_evidence='SYNTHETIC TEST EVIDENCE ONLY')
        lead = {'payable': 2, 'signed': 1, 'total_leads': 2, 'billing_fields': [{'criteria_assignment': 'verified-label'}, {'criteria_assignment': 'verified-standard'}]}
        self.assertEqual(m.tort_metrics('Hernia Mesh', lead, 50, cfg, dt.date(2026,9,7))['revenue'], 230)
        cfg['hm_billing_mapping_evidence'] = None
        self.assertIsNone(m.tort_metrics('Hernia Mesh', lead, 50, cfg, D)['revenue'])
        self.assertEqual([m.status_of(x, True, 1, 1) for x in (9,10,25,26)], ['red','amber','amber','green'])
        self.assertEqual(m.status_of(None, True, 10, 0), 'red')
        self.assertEqual(m.status_of(90, False, 10, 1), 'amber')

    def test_meta_pagination_loop_and_failed_second_page_fail_closed(self):
        m = importlib.import_module('main_sources')
        def fetch(url, headers=None):
            return {'data': [], 'paging': {'next': url}}
        src = m.MetaSpendSource(['synthetic'], {'USD': 1}, fetch=fetch)
        with self.assertRaises(m.SourceError):
            src.pages('https://graph.facebook.com/v21.0/me/adaccounts', 'synthetic')
        with self.assertRaises(m.SourceError):
            src.pages('https://example.com/steal', 'synthetic')
        src.prime(D,D)
        self.assertFalse(src.ledger['complete'])
        self.assertIsNone(src.spend('ILM')['spend'])

if __name__ == '__main__':
    unittest.main()
