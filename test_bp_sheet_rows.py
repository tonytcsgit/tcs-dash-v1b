"""PII-free fixtures; network is replaced only at the Sheets boundary."""
import importlib
import importlib.util
import unittest


class BPSheetRowsTests(unittest.TestCase):
    def test_healthy_tort_is_unchanged_and_does_not_fetch_raw(self):
        from bp_sheet_rows import select_bp_rows
        rows = [['Created_Date', 'Status'], ['2026-09-14', 'Signed']]
        self.assertEqual(select_bp_rows('Hernia Mesh', rows, self.fail), rows)

    def test_shifted_header_skips_banner_without_raw_fetch(self):
        from bp_sheet_rows import select_bp_rows
        rows = [['#ERROR!'], [], ['Created_Date', 'Status'], ['2026-09-14', 'Signed']]
        self.assertEqual(select_bp_rows('Hernia Mesh', rows, self.fail), rows[2:])

    def test_broken_or_missing_raw_schema_is_unknown_not_zero(self):
        from bp_sheet_rows import select_bp_rows, BPSheetSchemaError
        for raw in ([], [['#ERROR!']], [['Created_Date', 'Status']]):
            with self.subTest(raw=raw), self.assertRaises(BPSheetSchemaError):
                select_bp_rows('Hernia Mesh', [['#ERROR!']], lambda: raw)

    def test_absent_case_type_is_unknown_not_zero(self):
        from bp_sheet_rows import select_bp_rows, BPSheetSchemaError
        raw = [['Created_Date', 'Status', 'Case_Type'], ['2026-09-14', 'Signed', 'Breast Mesh']]
        with self.assertRaises(BPSheetSchemaError):
            select_bp_rows('Hernia Mesh', [], lambda: raw)

    def test_raw_fetch_failure_propagates(self):
        from bp_sheet_rows import select_bp_rows
        def unavailable():
            raise OSError('source unavailable')
        with self.assertRaises(OSError):
            select_bp_rows('Hernia Mesh', [], unavailable)

    def test_corrupt_query_header_falls_back_to_same_bp_raw_case_type(self):
        self.assertIsNotNone(importlib.util.find_spec('bp_sheet_rows'),
                             'Missing safe BP raw-source fallback')
        parser = importlib.import_module('bp_sheet_rows')
        raw = [[], ['Created_Date', 'Status', 'Case_Type', 'adSetId'],
               ['2026-09-14', 'Signed', 'Hernia Mesh', 'HM fixture'],
               ['2026-09-14', 'Signed', 'Breast Mesh', 'BM fixture'],
               ['2026-09-13', "Rejected - Doesn't Meet Criteria", 'Hernia Mesh', 'HM fixture']]
        corrupt = [['Created_Date merged text', 'Status merged text']]
        result = parser.select_bp_rows('Hernia Mesh', corrupt, lambda: raw)
        self.assertEqual(result, [raw[1], raw[2], raw[4]])


if __name__ == '__main__':
    unittest.main()
