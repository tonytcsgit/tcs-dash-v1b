"""Resolve BP tab headers without guessing columns or using another data source.

load_raw_rows must read 'Leads Last 13 Months' from the SAME BP spreadsheet.
Returns [header, *data] for existing consumers. Never prints source cell values.
"""
RAW_TAB = 'Leads Last 13 Months'
RAW_RANGE = "'Leads Last 13 Months'!A1:AZ40000"
DATE_HEADERS = {'created_date', 'createddate', 'created', 'date'}


class BPSheetSchemaError(ValueError):
    """An unavailable source is not a zero-lead source."""


def _header_index(rows, require_case_type=False):
    for i, row in enumerate(rows[:8]):
        names = {str(c).strip().lower().replace(' ', '_') for c in row}
        if ('status' in names and names & DATE_HEADERS
                and (not require_case_type or 'case_type' in names)):
            return i
    return None


def select_bp_rows(tab, rows, load_raw_rows):
    """Prefer healthy tort rows; otherwise filter the canonical raw BP table."""
    header_i = _header_index(rows)
    if header_i is not None:
        return rows[header_i:]
    raw = load_raw_rows()
    raw_header_i = _header_index(raw, require_case_type=True)
    if raw_header_i is None:
        raise BPSheetSchemaError('BP raw source missing Status/Created_Date/Case_Type header')
    header = raw[raw_header_i]
    case_i = [str(c).strip().lower().replace(' ', '_') for c in header].index('case_type')
    matched = [r for r in raw[raw_header_i + 1:]
               if case_i < len(r) and str(r[case_i]).strip() == tab]
    if not matched:
        raise BPSheetSchemaError('BP raw source has no matching Case_Type; cannot establish zero')
    return [header] + matched
