#!/usr/bin/env python3
"""Repo-owned dashboard preview builder: no deployment or source-system writes.

Cost/Sign remains spend / signed per this repository's metric-definitions.md.
This is gross margin; no fees or net-profit reinterpretation.
"""
import datetime as dt
import json
from pathlib import Path

CONFIG_PATH = Path(__file__).with_name('dashboard_config.yaml')
PREVIEW_PATH = Path('/Users/andyoc/.hermes/reports/tcs-dashboard-repair/main-preview.json')
ROSTER = {'ILM', 'Hernia Mesh', 'SMA', 'Paraquat', 'PowerPort', 'Endoscopy', 'TVM', 'BM', 'WDC', 'Chlorpyrifos', 'Depo'}


def check_output_path(path):
    if Path(path).absolute() != PREVIEW_PATH or Path(path).is_symlink():
        raise ValueError('Preview-only builder: --out must be ' + str(PREVIEW_PATH))
    return PREVIEW_PATH


def _sum_known(rows, field):
    vals = [r.get(field) for r in rows]
    return sum(vals) if all(v is not None for v in vals) else None


def assemble(cfg, since, until, leads, costs, lp, ledger, comments, targets):
    from main_sources import utcnow
    torts, needs, stale = [], [], []
    for tort, spec in cfg['bp_torts'].items():
        lead = leads.get(tort)
        cost = costs.get(tort, {})
        row = tort_metrics(tort, lead, cost.get('spend') if cost.get('complete') is True else None, cfg, since)
        warnings = row['warnings']
        warnings.extend(cost.get('warnings', []))
        if cost.get('warning'):
            warnings.append(cost['warning'])
        row.update(spend_source=spec['src'], spend_caveat='; '.join(warnings) or None,
                   observed_spend_usd=cost.get('observed_spend_usd'),
                   lead_source=({k: lead.get(k) for k in ('fetched_at', 'cohort_max_date', 'source_tab')} if lead else
                                {'fetched_at': None, 'status': 'unavailable'}))
        torts.append(row)
    for tort, spec in cfg['nonbp_torts'].items():
        observed = lp.get(tort, {})
        warning = ('Non-BP buyer/payable/revenue and Meta buyer-cost mapping unverified; '
                   'legacy buyer assignment retained as unverified, no guessed buyer labels')
        row = tort_metrics(tort, None, None, cfg, since)
        row.update(total_leads=observed.get('leads'), observed_campaign_leads=observed.get('leads'),
                   spend_source='meta', spend_caveat=warning,
                   lead_source=observed, buyer_mapping_verified=False,
                   warnings=[warning] + observed.get('warnings', []))
        torts.append(row)
    for row in torts:
        note = comments.get('torts', {}).get(row['tort'], {})
        row.update(note=note.get('note'), note_author=note.get('author'), note_ts=note.get('ts'))
        stale.extend(row['tort'] + ': ' + w for w in row['warnings'])
        if row['status'] == 'red':
            reason = ('Gross margin %.1f%% — under 10%% floor' % row['margin_pct'] if row['margin_pct'] is not None
                      else 'Spend with zero payable leads')
            needs.append(dict(tort_or_buyer=row['tort'], level='red', reason=reason, owner=note.get('owner')))
        elif not row['data_ok']:
            needs.append(dict(tort_or_buyer=row['tort'], level='amber', reason=row['spend_caveat'] or 'Data gap', owner=note.get('owner')))
    # Preserve legacy company aggregate scope (BP only), but never add unknowns as zeros.
    bp = [r for r in torts if r['tort'] in cfg['bp_torts']]
    spend, revenue = _sum_known(bp, 'spend'), _sum_known(bp, 'revenue')
    sign, pay = _sum_known(bp, 'signed'), _sum_known(bp, 'payable_leads')
    gp = revenue - spend if revenue is not None and spend is not None else None
    company = dict(window_label='Week of Mon %s — Day %d of 7' % (since.strftime('%b %d'), (until-since).days+1),
        scope='BP torts only (preserved legacy company aggregate); non-BP finance unavailable',
        spend=round(spend, 2) if spend is not None else None,
        revenue=revenue, gross_profit=round(gp, 2) if gp is not None else None,
        margin_pct=round(gp/revenue*100, 1) if gp is not None and revenue else None,
        cost_per_sign=round(spend/sign, 0) if spend is not None and sign else None,
        payable_leads=pay, deltas={},
        known_revenue_components=sum(r['revenue'] for r in bp if r['revenue'] is not None),
        known_spend_components=sum(r['spend'] for r in bp if r['spend'] is not None),
        caveat='Unknown components withheld, not treated as zero; observed partial cost is not a complete financial total')
    quota_warning = ('BP quotas not currently verified (legacy file last verified %s); runway estimates/cap alerts disabled' % cfg['quota_verified'])
    stale.extend([quota_warning, 'SR not refreshed by this build', 'Retainers not refreshed by this build'])
    needs.append(dict(tort_or_buyer='Broughton', level='amber', reason=quota_warning, owner=None))
    buyers = []
    for buyer in cfg['buyers']:
        bc = comments.get('buyers', {}).get(buyer, {})
        active = list(cfg['bp_torts']) if buyer == 'Broughton' else [t for t, s in cfg['nonbp_torts'].items() if s['buyer'] == buyer]
        runway = []
        for tort in active:
            row = next(r for r in torts if r['tort'] == tort)
            cap = cfg['bp_quota'].get(tort) if buyer == 'Broughton' else targets.get(buyer, {}).get(tort)
            runway.append(dict(tort=tort, cap=None if buyer == 'Broughton' else cap,
                cap_unit='leads/wk' if buyer == 'Broughton' else 'cases',
                used=row['payable_leads'] if buyer == 'Broughton' else None,
                pct=None, est_days_left=None, last_known_cap=cap if buyer == 'Broughton' else None,
                verified=False))
        buyers.append(dict(buyer=buyer, status=bc.get('status', 'amber'),
            status_source='manual' if 'status' in bc else 'unverified', comment=bc.get('comment'), comment_ts=bc.get('ts'),
            runway=runway, active_torts=active, upcoming_torts=bc.get('upcoming', [])))
    torts.sort(key=lambda r: r['spend'] if r['spend'] is not None else -1, reverse=True)
    needs.sort(key=lambda n: n['level'] != 'red')
    return dict(contract_version=cfg['contract_version'], generated_at=utcnow(),
        window={'since': since.isoformat(), 'until': until.isoformat(), 'timezone': 'America/New_York'},
        preview_only=True, build_status='partial_sources', structurally_complete=True,
        financial_complete=all(r['data_ok'] for r in torts),
        data_freshness=dict(leads_spend_sr=None, retainers=None, sr=None,
            sr_status='not_refreshed', retainers_status='not_refreshed', stale_warnings=stale, sources=ledger),
        company=company, needs_attention=needs, andrew_priorities=comments.get('priorities', []),
        company_priorities=comments.get('company_priorities', []), andrew_note=comments.get('top_note', {}),
        pricing_provenance=cfg['pricing_provenance'], torts=torts, buyers=buyers)


def validate_contract(out):
    """Structural AND semantic validation; unknown metrics are valid only with warnings."""
    problems = []
    for key in ('generated_at', 'contract_version', 'company', 'needs_attention', 'buyers', 'data_freshness'):
        if key not in out:
            problems.append('Missing ' + key)
    buyer_rows = out.get('buyers', [])
    if len(buyer_rows) != 5 or {b.get('buyer') for b in buyer_rows} != {'Broughton', 'Pulaski', 'Bryan', 'Wagstaff', 'Parker'}:
        problems.append('Expected exactly the 5 dashboard buyers')
    for b in buyer_rows:
        if not all(k in b for k in ('status', 'comment', 'comment_ts', 'runway', 'active_torts', 'upcoming_torts')):
            problems.append('Buyer row missing contract fields')
    for key in ('spend', 'revenue', 'gross_profit', 'margin_pct', 'cost_per_sign', 'payable_leads', 'deltas'):
        if key not in out.get('company', {}):
            problems.append('Company missing ' + key)
    rows = out.get('torts', [])
    if len(rows) != 11 or {r.get('tort') for r in rows} != ROSTER:
        problems.append('Expected exactly the 11 dashboard torts')
    import math
    for row in rows:
        for key in ('spend', 'revenue', 'margin_pct', 'cpl', 'cost_per_sign', 'payable_leads', 'signed'):
            if key not in row or (row[key] is not None and
                    (not isinstance(row[key], (int, float)) or not math.isfinite(row[key]))):
                problems.append('Invalid nullable metric ' + key)
        if not row.get('data_ok') and (not row.get('warnings') or row.get('status') == 'green'):
            problems.append('Incomplete tort without warning/with green status')
        if row.get('spend') is None and (row.get('margin_pct') is not None or row.get('cost_per_sign') is not None):
            problems.append('Unknown cost leaked into financial ratios')
    f = out.get('data_freshness', {})
    if f.get('sr') is not None or f.get('retainers') is not None or f.get('leads_spend_sr') is not None:
        problems.append('Unfetched SR/retainers cannot be stamped fresh')
    if not out.get('financial_complete') and not f.get('stale_warnings'):
        problems.append('Incomplete finance must carry explicit warnings')
    return problems


def run_live(cfg, since, until):
    from concurrent.futures import ThreadPoolExecutor
    from main_sources import (SheetsLeadSource, MetaSpendSource, YouTubeSpendSource,
                              LPLeadSource, SourceError, fetch_fx)
    # Credentials only read in execution; no token sync or credential writes.
    with open(cfg['secrets_path']) as f:
        secrets = json.load(f)
    from meta_token_pool import load_meta_token_pool
    tokens, token_origins, token_ledger = load_meta_token_pool(secrets.get('META_ACCOUNTS', {}), cfg)
    def meta_pull():
        rates, fx_ledger = fetch_fx(cfg)
        src = MetaSpendSource(tokens, rates, workers=cfg['meta_max_workers'], budget=cfg['meta_budget_seconds'],
            token_origins=token_origins, token_pool_ledger=token_ledger,
            expected_accounts=cfg.get('meta_expected_accounts', []))
        src.prime(since, until)
        return src, fx_ledger
    def sheet_pull():
        src = SheetsLeadSource(cfg['bp_sheet'])
        results, errors = {}, {}
        for tort, spec in cfg['bp_torts'].items():
            try:
                results[tort] = src.tab_counts(spec['tab'], since, until)
            except SourceError as e:
                results[tort] = None
                errors[tort] = str(e)
        return results, errors
    def lp_pull():
        src = LPLeadSource(secrets.get('LEADSPROSPER_API_KEY') or secrets.get('LEADSPROSPER'))
        out = {}
        for tort, spec in cfg['nonbp_torts'].items():
            try:
                out[tort] = src.lead_count(spec['lp'], since, until)
            except SourceError as e:
                out[tort] = dict(leads=None, fetched_at=None, warnings=[str(e)])
        return out
    with ThreadPoolExecutor(max_workers=4) as pool:
        mf = pool.submit(meta_pull)
        sf = pool.submit(sheet_pull)
        yf = pool.submit(YouTubeSpendSource(cfg['youtube']).spend, since, until)
        lf = pool.submit(lp_pull)
        leads, sheet_errors = sf.result()
        meta, fx_ledger = mf.result()
        yt, lp = yf.result(), lf.result()
    costs = {t: meta.spend(t) for t in cfg['bp_torts'] if t != 'SMA'}
    costs['SMA'] = yt
    for tort, error in sheet_errors.items():
        costs[tort].setdefault('warnings', []).append(error)
    # No raw lead fields leave this function; billing label *counts* are non-PII evidence.
    sheet_ledger = {t: ({k: r.get(k) for k in ('source_tab', 'fetched_at', 'cohort_max_date', 'total_leads', 'payable', 'signed', 'billing_label_counts')} if r else
                         dict(fetched_at=None, status='unavailable', warning=sheet_errors[t])) for t, r in leads.items()}
    ledger = dict(bp_sheets=sheet_ledger, meta=meta.ledger, fx=fx_ledger, bp_sma_youtube=yt, leadprosper=lp)
    return leads, costs, lp, ledger, [t for t in tokens if t] + [secrets.get('LEADSPROSPER_API_KEY') or '']


def main(argv=None):
    import argparse
    import os
    import tempfile
    from zoneinfo import ZoneInfo
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out', required=True, help='Must be the private main-preview.json path')
    ap.add_argument('--config', default=str(CONFIG_PATH))
    ap.add_argument('--since')
    ap.add_argument('--until')
    ap.add_argument('--comments')
    ap.add_argument('--targets')
    a = ap.parse_args(argv)
    output = check_output_path(a.out)
    cfg = load_config(a.config)
    if bool(a.since) != bool(a.until):
        raise ValueError('--since and --until must be supplied together')
    today = dt.datetime.now(ZoneInfo('America/New_York')).date()
    since = dt.date.fromisoformat(a.since) if a.since else today-dt.timedelta(days=today.weekday())
    until = dt.date.fromisoformat(a.until) if a.until else today
    if since < dt.date.fromisoformat(cfg['pricing_not_before']) or until < since or until > today:
        raise ValueError('Invalid/pre-rate/future reporting window; historical policy required before 2026-09-07')
    def sidecar(path):
        if not Path(path).exists():
            return {}
        with open(path) as f:
            return json.load(f)
    comments = sidecar(a.comments or cfg['comments_path'])
    targets = sidecar(a.targets or cfg['targets_path'])
    leads, costs, lp, ledger, secrets = run_live(cfg, since, until)
    out = assemble(cfg, since, until, leads, costs, lp, ledger, comments, targets)
    problems = validate_contract(out)
    if problems:
        raise ValueError('Contract validation failed: ' + '; '.join(problems))
    raw = json.dumps(out, indent=2, allow_nan=False)
    if any(token and token in raw for token in secrets):
        raise ValueError('Security scan failed; output not written')
    output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(output.parent, 0o700)
    fd, temp = tempfile.mkstemp(prefix='.main-preview-', dir=str(output.parent))
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(raw + '\n')
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, output)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    with open(output) as f:
        if validate_contract(json.load(f)):
            raise ValueError('Written preview failed read-back validation')
    print('WROTE PREVIEW ONLY ' + str(output))
    print('11 torts / 5 buyers; structurally complete; financial_complete=' + str(out['financial_complete']))
    for r in out['torts']:
        print(json.dumps({k: r.get(k) for k in ('tort', 'total_leads', 'payable_leads', 'signed', 'revenue', 'spend', 'observed_spend_usd', 'data_ok')}))
    print('SOURCE GAPS: ' + str(len(out['data_freshness']['stale_warnings'])))
    return 0

def load_config(path=CONFIG_PATH):
    import yaml
    with open(path) as f:
        cfg = yaml.safe_load(f)
    validate_config(cfg)
    return cfg

def validate_config(cfg):
    for tort, spec in cfg['bp_torts'].items():
        expected = 'bp_sma_youtube' if tort == 'SMA' else 'meta'
        if spec.get('src') != expected:
            raise ValueError('Unsupported/disallowed BP source dispatch: ' + tort)
    if len(cfg['bp_torts']) != 8 or len(cfg['nonbp_torts']) != 3:
        raise ValueError('Dashboard must retain 8 BP and 3 non-BP torts')

def status_of(margin, data_ok, spend, payable):
    if not data_ok:
        return 'amber'
    if spend and spend > 0 and payable == 0:
        return 'red'
    if margin is None:
        return 'amber'
    return 'red' if margin < 10 else 'amber' if margin <= 25 else 'green'

def tort_metrics(tort, lead, spend, cfg, since):
    if since < dt.date.fromisoformat(cfg['pricing_not_before']):
        raise ValueError('Historical pre-rate window blocked: needs documented dated pricing policy')
    pay = lead['payable'] if lead is not None else None
    sign = lead['signed'] if lead is not None else None
    warnings = []
    revenue = None
    if lead is not None:
        if tort == 'Hernia Mesh':
            mapping = cfg.get('hm_billing_tier_map', {})
            tiers = []
            if cfg.get('hm_billing_mapping_evidence') and mapping:
                for fields in lead['billing_fields']:
                    matched = {mapping[k][v] for k, v in fields.items() if k in mapping and v in mapping[k]}
                    tiers.append(next(iter(matched)) if len(matched) == 1 else None)
            if len(tiers) == pay and all(x in cfg['hm_tier_rates'] for x in tiers) and mapping:
                revenue = sum(cfg['hm_tier_rates'][x] for x in tiers)
            else:
                warnings.append('HM revenue unknown: verify Injury_Tier / Criteria_Assignment / Intake_Source_Type billing mapping; no campaign-name inference')
        elif tort in cfg['payouts']:
            revenue = pay * cfg['payouts'][tort]
    if lead is None:
        warnings.append('Lead source unavailable: counts and revenue unknown, not zero')
    if spend is None:
        warnings.append('Cost coverage unavailable/incomplete: spend and margin withheld')
    margin = (revenue - spend) / revenue * 100 if revenue and spend is not None else None
    ok = lead is not None and spend is not None and revenue is not None
    return dict(tort=tort, spend=spend, revenue=revenue,
                margin_pct=round(margin, 1) if margin is not None else None,
                cpl=round(spend / pay, 0) if spend is not None and pay else None,
                cost_per_sign=round(spend / sign, 0) if spend is not None and sign else None,
                payable_leads=pay, signed=sign, total_leads=lead.get('total_leads') if lead else None,
                data_ok=ok, status=status_of(margin, ok, spend, pay), warnings=warnings)


if __name__ == '__main__':
    import sys
    try:
        sys.exit(main())
    except Exception as exc:
        # Avoid traceback locals / token-bearing URLs in CLI logs.
        print('PREVIEW BUILD FAILED: ' + type(exc).__name__, file=sys.stderr)
        sys.exit(2)
