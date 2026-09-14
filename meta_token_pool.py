"""Read canonical Meta credentials into memory only. Never sync, log or persist tokens."""
import re


def load_meta_token_pool(local_accounts, cfg, reader=None):
    from main_sources import SheetsLeadSource, utcnow
    origins = {}
    def add(token, source):
        if isinstance(token, str) and token.strip():
            token = token.strip()
            sources = origins.setdefault(token, [])
            if source not in sources:
                sources.append(source)
    for value in local_accounts.values():
        add(value.get('access_token') if isinstance(value, dict) else value, 'local')
    local_count = len(origins)
    warnings, sheet_tokens, fetched_at = [], set(), None
    try:
        read = reader or SheetsLeadSource(cfg['meta_token_sheet']).reader
        rows = read(cfg['meta_token_range'])
        fetched_at = utcnow()
        if len(rows) >= 2000:
            warnings.append('Canonical token sheet reached row cap; completeness unknown')
        for row in rows:
            if not isinstance(row, list):
                raise ValueError('Invalid sheet row')
            for cell in row:
                value = cell.strip() if isinstance(cell, str) else ''
                if re.fullmatch(r'EAA[A-Za-z0-9]{20,}', value):
                    sheet_tokens.add(value)
                elif value.startswith('EAA'):
                    warnings.append('Malformed credential cell in canonical token sheet')
        if not sheet_tokens:
            warnings.append('Canonical token sheet yielded no usable credentials')
    except Exception:
        warnings.append('Canonical token sheet unavailable or invalid; local observations only')
    for token in sorted(sheet_tokens):
        add(token, 'canonical_sheet')
    ledger = dict(source='Canonical Meta token Sheet + local cache; read-only in-memory union',
                  sheet_id=cfg.get('meta_token_sheet'), range=cfg.get('meta_token_range'),
                  fetched_at=fetched_at, complete=not warnings, warnings=sorted(set(warnings)),
                  local_unique_tokens=local_count, canonical_unique_tokens=len(sheet_tokens),
                  union_unique_tokens=len(origins))
    return list(origins), origins, ledger
