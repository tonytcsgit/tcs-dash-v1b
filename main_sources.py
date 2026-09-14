"""Read-only dashboard sources. No I/O at import, no raw lead persistence/logging."""
import datetime as dt
import json
import time
import urllib.parse
from bp_sheet_rows import select_bp_rows, RAW_RANGE, RAW_TAB, BPSheetSchemaError

SA_PATH = '/Users/andyoc/.hermes/gcp-service-account.json'
NONPAY = frozenset(('rejected - failed prequalification',
                   'rejected - wrong number | spam | other',
                   'rejected - existing contact'))

class SourceError(RuntimeError):
    pass

def utcnow():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')

class HttpClient:
    """Bounded read-only JSON transport; never emit URLs, headers or response bodies."""
    def __init__(self, budget=170):
        self.deadline = time.monotonic() + budget

    def __call__(self, url, headers=None):
        import requests
        for attempt in range(2):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise SourceError('Source deadline exhausted')
            try:
                r = requests.get(url, headers=headers or {}, timeout=(min(5, remaining), min(15, remaining)))
                if r.status_code in (429, 500, 502, 503, 504) and not attempt:
                    time.sleep(1)
                    continue
                if r.status_code != 200:
                    raise SourceError('HTTP %s' % r.status_code)
                d = r.json()
                if isinstance(d, dict) and 'error' in d:
                    raise SourceError('API returned error')
                return d
            except SourceError:
                raise
            except Exception:
                if attempt:
                    raise SourceError('Network/JSON read failed') from None
        raise SourceError('Retry budget exhausted')


def _word(name, terms):
    import re
    text = re.sub(r'[^a-z0-9]+', ' ', name.lower())
    return any(re.search(r'(?<![a-z0-9])' + re.escape(term) + r'(?![a-z0-9])', text) for term in terms)

OTHER_BUYERS = ('olympus', 'pulaski', 'parker', 'wagstaff', 'stinar', 'lannen', 'bryan', 'lca')
BP_WORDS = {'ILM': ('ilm', 'juvenile detention', 'jdc il'),
            'Hernia Mesh': ('hernia mesh', 'hm'), 'SMA': ('sma', 'social media addiction'),
            'PowerPort': ('powerport', 'power port', 'pp'), 'Paraquat': ('paraquat', 'pqt'),
            'Endoscopy': ('endoscopy',), 'TVM': ('tvm', 'transvaginal mesh'),
            'BM': ('bm', 'breast mesh')}

def classify_bp(name):
    if _word(name, OTHER_BUYERS):
        return None
    hits = [t for t, words in BP_WORDS.items() if _word(name, words)]
    return hits[0] if len(hits) == 1 else None


def fetch_fx(cfg, fetch=None):
    fetch = fetch or HttpClient(20)
    ledger = dict(source=cfg['fx_url'], fetched_at=None, rate_date=None,
                  convention='USD per 1 account currency unit; current observation, not historical booked FX')
    try:
        d = fetch(cfg['fx_url'])
        day = dt.date.fromisoformat(d['date'])
        age = (dt.datetime.now(dt.timezone.utc).date() - day).days
        if d.get('base') != 'USD' or not 0 <= age <= cfg.get('fx_max_age_days', 3):
            raise SourceError('FX date/base stale or invalid')
        rates = {'USD': 1.0}
        for curr in ('NZD', 'VND'):
            rate = float(d['rates'][curr])
            import math
            if not math.isfinite(rate) or rate <= 0:
                raise SourceError('FX rate invalid')
            rates[curr] = 1 / rate
        ledger.update(fetched_at=utcnow(), rate_date=day.isoformat(), usd_per_unit=rates, status='observed')
        return rates, ledger
    except Exception:
        ledger.update(status='unavailable', warning='Current FX unavailable; non-USD costs withheld')
        return {'USD': 1.0}, ledger


class MetaSpendSource:
    def __init__(self, tokens, rates, fetch=None, workers=10, budget=170,
                 token_origins=None, token_pool_ledger=None, expected_accounts=()):
        self.tokens = list(dict.fromkeys(t for t in tokens if t))
        self.token_origins = token_origins or {t: ['local'] for t in self.tokens}
        self.token_pool_ledger = token_pool_ledger
        self.expected_accounts = set(expected_accounts)
        self.rates, self.workers = rates, workers
        self.fetch = fetch or HttpClient(budget)
        self.rows, self.ledger = [], {}

    def pages(self, url, token):
        visited = set()
        out = []
        for _ in range(1000):
            parts = urllib.parse.urlsplit(url)
            if parts.scheme != 'https' or parts.hostname != 'graph.facebook.com':
                raise SourceError('Untrusted Meta pagination host')
            query = urllib.parse.urlencode([(k, v) for k, v in urllib.parse.parse_qsl(parts.query)
                                          if k.lower() != 'access_token'])
            url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, query, ''))
            if url in visited:
                raise SourceError('Meta pagination cycle')
            visited.add(url)
            d = self.fetch(url, headers={'Authorization': 'Bearer ' + token})
            if not isinstance(d.get('data'), list):
                raise SourceError('Meta page missing data array')
            out.extend(d['data'])
            url = d.get('paging', {}).get('next')
            if not url:
                return out
        raise SourceError('Meta pagination limit exceeded')

    def prime(self, since, until):
        from concurrent.futures import ThreadPoolExecutor
        if self.ledger:
            return
        base = 'https://graph.facebook.com/v21.0'
        accounts, failures, failed_tokens = {}, [], []
        coverage = {}
        def discover(token):
            try:
                return token, self.pages(base + '/me/adaccounts?fields=id,currency&limit=100', token), None
            except SourceError as e:
                return token, [], str(e)
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for token, rows, err in pool.map(discover, self.tokens):
                if err:
                    failures.append('Account discovery: ' + err)
                    failed_tokens.append(dict(token_ref='token-%02d' % (self.tokens.index(token) + 1),
                        origins=self.token_origins.get(token, []), error=err))
                for a in rows:
                    aid = a.get('id')
                    if not aid:
                        failures.append('Account identifier missing')
                        continue
                    entry = accounts.setdefault(aid, dict(currency=a.get('currency'), tokens=[], origins=set()))
                    entry['origins'].update(self.token_origins.get(token, []))
                    if entry['currency'] != a.get('currency'):
                        failures.append('Conflicting account currency')
                    if token not in entry['tokens']:
                        entry['tokens'].append(token)
        q = urllib.parse.urlencode(dict(level='campaign', limit=500,
            time_range=json.dumps(dict(since=since.isoformat(), until=until.isoformat())),
            fields='account_id,account_currency,campaign_id,campaign_name,spend,date_start,date_stop'))
        def insights(item):
            aid, account = item
            err = 'No usable account token'
            for token in account['tokens']:
                try:
                    return aid, self.pages(base + '/' + aid + '/insights?' + q, token), None
                except SourceError as e:
                    err = str(e)
            return aid, [], err
        queried = 0
        seen, currencies, fetched_times = set(), set(), []
        with ThreadPoolExecutor(max_workers=self.workers) as pool:
            for aid, rows, err in pool.map(insights, sorted(accounts.items())):
                coverage[aid] = dict(account_id=aid, currency=accounts[aid]['currency'],
                    origins=sorted(accounts[aid]['origins']), insight_status='error' if err else 'ok',
                    observed_campaigns=0, observed_bp_spend_usd={})
                if err:
                    failures.append('Account insights: ' + err)
                    coverage[aid]['error'] = err
                    continue
                queried += 1
                fetched_times.append(utcnow())
                for r in rows:
                    key = (aid, r.get('campaign_id'))
                    if not key[1]:
                        failures.append('Campaign identifier missing')
                        continue
                    if key in seen:
                        continue  # exactly once, never max() across duplicate tokens/pages
                    seen.add(key)
                    curr = r.get('account_currency')
                    currencies.add(curr or 'UNKNOWN')
                    usd = None
                    try:
                        raw = float(r['spend'])
                        import math
                        if not math.isfinite(raw) or raw < 0:
                            raise ValueError()
                        if not curr or curr != accounts[aid]['currency'] or curr not in self.rates:
                            raise ValueError()
                        usd = raw * self.rates[curr]
                    except (ValueError, KeyError, TypeError):
                        failures.append('Unconverted/missing/inconsistent account currency or spend')
                    self.rows.append(dict(account_id=aid, campaign_id=r['campaign_id'],
                        name=r.get('campaign_name', ''), spend_usd=usd, currency=curr,
                        date_start=r.get('date_start'), date_stop=r.get('date_stop')))
                    coverage[aid]['observed_campaigns'] += 1
                    tort = classify_bp(r.get('campaign_name', ''))
                    if tort and tort != 'SMA' and usd is not None:
                        totals = coverage[aid]['observed_bp_spend_usd']
                        totals[tort] = totals.get(tort, 0) + usd
        unresolved = sorted(self.expected_accounts - {a for a, c in coverage.items() if c['insight_status'] == 'ok'})
        if unresolved:
            failures.append('Historical account access unresolved; cannot infer retirement or zero spend')
        for c in coverage.values():
            c['observed_bp_spend_usd'] = {t: round(v, 2) for t, v in c['observed_bp_spend_usd'].items()}
        local_accounts = {a for a, r in accounts.items() if 'local' in r['origins']}
        canonical_accounts = {a for a, r in accounts.items() if 'canonical_sheet' in r['origins']}
        if self.token_pool_ledger is not None:
            if self.token_pool_ledger.get('complete') is not True:
                failures.extend(self.token_pool_ledger.get('warnings') or ['Canonical token inventory incomplete'])
        self.ledger = dict(accounts_total=len(accounts), accounts_queried=queried,
            token_pool=self.token_pool_ledger,
            local_accounts_total=len(local_accounts), canonical_accounts_total=len(canonical_accounts),
            accounts_added_by_canonical=sorted(canonical_accounts-local_accounts),
            unresolved_accounts=unresolved, historical_watchlist=sorted(self.expected_accounts),
            account_coverage=[coverage[a] for a in sorted(coverage)], failed_tokens=failed_tokens,
            tokens_total=len(self.tokens), discovery_failures=sum(x.startswith('Account discovery') for x in failures),
            campaigns_observed=len(self.rows), currencies=sorted(currencies),
            fetched_at=max(fetched_times) if fetched_times else None,
            first_response_at=min(fetched_times) if fetched_times else None,
            requested_since=since.isoformat(), requested_until=until.isoformat(),
            complete=bool(accounts) and not failures and queried == len(accounts),
            warnings=sorted(set(failures)), inventory_scope='unique accounts reachable through read-only token union plus explicit historical watchlist; no credential synchronization; not proof that unreachable accounts retired')

    def spend(self, tort):
        if tort == 'SMA':
            return dict(spend=None, observed_spend_usd=None, complete=False,
                        warning='BP SMA costs are YouTube ONLY; Meta SMA deliberately excluded')
        matched = [r for r in self.rows if classify_bp(r['name']) == tort]
        observed = sum(r['spend_usd'] for r in matched if r['spend_usd'] is not None)
        # If nothing matched, absence may be naming/mapping rather than genuine zero spend.
        complete = bool(matched) and self.ledger.get('complete', False)
        return dict(spend=round(observed, 2) if complete else None,
                    observed_spend_usd=round(observed, 2), complete=complete,
                    campaigns_matched=len(matched),
                    warning=None if complete else 'Meta inventory/currency incomplete or no verified matching campaign')


def youtube_summary(rows, cfg, since, until):
    """Google Ads ONLY; assert account/campaign/day uniqueness and whole calendar."""
    expected = {(since + dt.timedelta(days=i)).isoformat() for i in range((until-since).days+1)}
    seen, covered, warnings = set(), {a: set() for a in cfg['accounts']}, []
    observed = excluded = unattributed = 0.0
    for r in rows:
        key = (str(r['account_id']), str(r['campaign_id']), str(r['day']))
        if key in seen:
            warnings.append('Duplicate Google Ads account/campaign/day')
            continue
        seen.add(key)
        names = r.get('names') or []
        if not any(_word(n, BP_WORDS['SMA']) for n in names):
            continue
        if r.get('currencies') != ['USD'] or r.get('timezones') != ['America/New_York']:
            warnings.append('Google Ads currency/timezone not verified USD / America/New_York')
            continue
        cost = float(r['cost'])
        if any(_word(n, OTHER_BUYERS) for n in names):
            excluded += cost
            continue
        approved = (str(r['campaign_id']) in cfg.get('approved_bp_campaign_ids', []) and cfg.get('attribution_evidence'))
        if not approved and not all(_word(n, ('bp', 'broughton')) for n in names):
            unattributed += cost
            warnings.append('Generic SMA campaign attribution not verified as BP')
            continue
        if key[0] not in covered or key[2] not in expected:
            warnings.append('Unexpected Google Ads account/date')
            continue
        covered[key[0]].add(key[2])
        observed += cost
    missing = {a: sorted(expected-days) for a, days in covered.items() if expected-days}
    if missing:
        warnings.append('Missing BP SMA daily/account coverage; absent rows do not prove zero spend')
    return dict(spend=round(observed, 2) if not warnings else None,
                observed_spend_usd=round(observed, 2), excluded_other_buyer_usd=round(excluded, 2),
                unattributed_sma_usd=round(unattributed, 2), missing_dates_by_account=missing,
                complete=not warnings, warnings=sorted(set(warnings)),
                cohort_max_date=max((str(r['day']) for r in rows), default=None))


class YouTubeSpendSource:
    """The only BQ adapter: read-only raw Google Ads daily BP SMA costs."""
    def __init__(self, cfg):
        self.cfg = cfg

    def spend(self, since, until):
        from google.cloud import bigquery
        from google.oauth2.service_account import Credentials
        import re
        cfg = self.cfg
        parts = [cfg['project'], cfg['dataset']] + cfg['accounts']
        if not all(re.fullmatch(r'[a-zA-Z0-9_-]+', x) for x in parts):
            raise SourceError('Invalid configured Google Ads identifier')
        client = bigquery.Client(project=cfg['project'], credentials=Credentials.from_service_account_file(SA_PATH))
        union = []
        for account in cfg['accounts']:
            base = cfg['project'] + '.' + cfg['dataset'] + '.p_ads_'
            # Historical campaign dimension is reduced BEFORE joining cost. Customer too.
            union.append("""SELECT '%s' account_id, CAST(s.campaign_id AS STRING) campaign_id,
                CAST(s.day AS STRING) day, s.cost, c.names, u.currencies, u.timezones
                FROM (SELECT campaign_id, segments_date day, SUM(metrics_cost_micros)/1e6 cost
                      FROM `%sCampaignBasicStats_%s`
                      WHERE segments_date BETWEEN @since AND @until GROUP BY 1,2) s
                LEFT JOIN (SELECT campaign_id, ARRAY_AGG(DISTINCT campaign_name IGNORE NULLS) names
                           FROM `%sCampaign_%s` GROUP BY 1) c USING(campaign_id)
                CROSS JOIN (SELECT ARRAY_AGG(DISTINCT customer_currency_code IGNORE NULLS) currencies,
                            ARRAY_AGG(DISTINCT customer_time_zone IGNORE NULLS) timezones
                            FROM `%sCustomer_%s`) u""" % (account, base, account, base, account, base, account))
        query = ' UNION ALL '.join(union)
        try:
            job = client.query(query, job_config=bigquery.QueryJobConfig(
                maximum_bytes_billed=2_000_000_000,
                query_parameters=[bigquery.ScalarQueryParameter('since', 'DATE', since),
                                  bigquery.ScalarQueryParameter('until', 'DATE', until)]),
                timeout=15, retry=None, job_retry=None)
            rows = [dict(r) for r in job.result(timeout=45, retry=None)]
            result = youtube_summary(rows, cfg, since, until)
            result.update(fetched_at=utcnow(), source='BQ raw Google Ads CampaignBasicStats + deduplicated Campaign/Customer',
                          accounts=cfg['accounts'], requested_since=since.isoformat(), requested_until=until.isoformat())
            return result
        except Exception as e:
            return dict(spend=None, observed_spend_usd=None, complete=False, fetched_at=None,
                        warnings=['BP SMA YouTube read failed: ' + type(e).__name__],
                        source='BQ raw Google Ads only', accounts=cfg['accounts'])


class LPLeadSource:
    """Observed raw campaign leads, NOT payable or buyer-attributed revenue."""
    def __init__(self, key, fetch=None):
        self.key = key
        self.fetch = fetch or HttpClient(65)

    def lead_count(self, campaign, since, until):
        from zoneinfo import ZoneInfo
        if not self.key:
            raise SourceError('No LP read credential configured')
        cursor, seen, cursors, days = None, set(), set(), []
        pages = 0
        while pages < 1000:
            params = dict(campaign=campaign, start_date=since.isoformat(), end_date=until.isoformat())
            if cursor:
                params['search_after'] = cursor
            d = self.fetch('https://api.leadprosper.io/public/leads?' + urllib.parse.urlencode(params),
                           headers={'Authorization': 'Bearer ' + self.key, 'Accept': 'application/json'})
            pages += 1
            if not isinstance(d.get('leads'), list):
                raise SourceError('LP missing leads array')
            leads = d['leads']
            for lead in leads:
                if not lead.get('id'):
                    raise SourceError('LP lead identity missing')
                try:
                    day = dt.datetime.fromtimestamp(int(lead['lead_date_ms']) / 1000, ZoneInfo('America/New_York')).date()
                except (KeyError, ValueError, TypeError):
                    raise SourceError('LP intake date missing/unparseable') from None
                if since <= day <= until:
                    seen.add(str(lead['id']))
                    days.append(day.isoformat())
            cursor = d.get('search_after')
            if not leads or not cursor:
                return dict(leads=len(seen), fetched_at=utcnow(), cohort_max_date=max(days) if days else None,
                            pages=pages, campaign_id=campaign, definition='Observed unique campaign leads; buyer/payable mapping unverified')
            if str(cursor) in cursors:
                raise SourceError('LP pagination cycle')
            cursors.add(str(cursor))
            time.sleep(.15)
        raise SourceError('LP page limit exhausted')


class SheetsLeadSource:
    def __init__(self, sheet_id, reader=None):
        self.sheet_id = sheet_id
        self.reader = reader or self._read_live
        self.cache = {}
        self.session = None
        self.deadline = time.monotonic() + 100

    def _read_live(self, range_):
        if time.monotonic() >= self.deadline:
            raise SourceError('Sheets phase deadline exhausted')
        if self.session is None:
            from google.oauth2.service_account import Credentials
            from google.auth.transport.requests import AuthorizedSession
            creds = Credentials.from_service_account_file(SA_PATH,
                scopes=['https://www.googleapis.com/auth/spreadsheets.readonly'])
            self.session = AuthorizedSession(creds, refresh_timeout=15)
        url = ('https://sheets.googleapis.com/v4/spreadsheets/' + self.sheet_id +
               '/values/' + urllib.parse.quote(range_, safe=''))
        for attempt in range(2):
            try:
                r = self.session.get(url, timeout=(5, 20))
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(attempt + 1)
                    continue
                if r.status_code != 200:
                    raise SourceError('Sheets HTTP %s' % r.status_code)
                return r.json().get('values', [])
            except SourceError:
                raise
            except Exception:
                if attempt:
                    raise SourceError('Sheets read/authorization failed') from None
        raise SourceError('Sheets retry budget exhausted')

    def read(self, range_):
        if range_ not in self.cache:
            self.cache[range_] = (self.reader(range_), utcnow())
        return self.cache[range_][0]

    def tab_counts(self, tab, since, until):
        range_ = "'%s'!A1:AZ40000" % tab
        try:
            try:
                rows = self.read(range_)
            except SourceError:
                rows = []
            fallback = []
            def raw():
                fallback.append(True)
                return self.read(RAW_RANGE)
            selected = select_bp_rows(tab, rows, raw)
        except (SourceError, BPSheetSchemaError):
            raise SourceError('BP tab and same-sheet raw fallback unavailable/schema invalid') from None
        hdr = {str(c).strip().lower().replace(' ', '_'): i for i, c in enumerate(selected[0])}
        di = next((hdr[k] for k in ('created_date', 'createddate', 'created', 'date') if k in hdr), None)
        si = hdr['status']
        total = signed = payable = invalid = 0
        dates, billing, all_dates = [], [], []
        labels = {k: {} for k in ('injury_tier', 'criteria_assignment', 'intake_source_type')}
        for row in selected[1:]:
            if not any(row):
                continue
            try:
                day = dt.date.fromisoformat(str(row[di])[:10])
            except (ValueError, IndexError, TypeError):
                invalid += 1
                continue
            all_dates.append(day)
            if not since <= day <= until:
                continue
            total += 1
            status = str(row[si]).strip().lower() if si < len(row) else ''
            if status in NONPAY:
                continue
            payable += 1
            signed += status == 'signed'
            dates.append(day.isoformat())
            fields = {k: str(row[hdr[k]]).strip() if k in hdr and hdr[k] < len(row) else '' for k in labels}
            billing.append(fields)
            for k, v in fields.items():
                labels[k][v] = labels[k].get(v, 0) + 1
        actual_range = RAW_RANGE if fallback else range_
        if len(self.read(actual_range)) >= 40000:
            raise SourceError('BP sheet reached row limit; completeness unknown')
        if invalid:
            raise SourceError('BP sheet contains %d undated rows; window completeness unknown' % invalid)
        return dict(total_leads=total, payable=payable, signed=signed,
                    per_lead_dates=dates, billing_fields=billing, billing_label_counts=labels,
                    source_tab=RAW_TAB if fallback else tab,
                    fetched_at=self.cache[actual_range][1],
                    cohort_max_date=max(all_dates).isoformat() if all_dates else None)
