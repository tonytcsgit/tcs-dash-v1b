"""Build integration tests; fixture source values are artificial, not real leads."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import build_bp_utm_data as builder
from bp_sheet_rows import RAW_RANGE

HM = next(t for t in builder.TORTS if t['id'] == 'hm')
HEADER = ['Created_Date', 'Status', 'Case_Type', 'placement', 'adId', 'adSetId']
STATUSES = ['Signed', "Rejected - Doesn't Meet Criteria", 'Pending - Contact',
            'Rejected - Failed Prequalification', 'Rejected - Wrong Number | Spam | Other',
            'Rejected - Existing Contact', 'Rejected - Do Not Contact', '']
RAW = [['report banner'], HEADER] + [
    ['2026-09-14', status, 'Hernia Mesh', 'Youtube', '800000000001', '900000000001']
    for status in STATUSES
] + [['2026-09-14', 'Signed', 'Breast Mesh', 'Meta', '', 'BM fixture']]


class FakeSheets:
    def __init__(self, raw=RAW):
        self.raw = raw
        self.requests = []

    def spreadsheets(self):
        return self

    def values(self):
        return self

    def get(self, **kwargs):
        self.requests.append(kwargs)
        self.result = self.raw if kwargs['range'] == RAW_RANGE else [
            ['Created_Date merged text', 'Status merged text']]
        return self

    def execute(self):
        return {'values': self.result}


class BuildTests(unittest.TestCase):
    def test_broken_raw_source_does_not_replace_last_good_artifact(self):
        fake = FakeSheets(raw=[['#ERROR!']])
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            dest = Path(tmp) / 'out.json'
            dest.write_text('last good artifact')
            with patch.object(builder, 'TORTS', [HM]), patch.object(builder, 'OUT_PATH', str(dest)), \
                 patch.object(builder.service_account.Credentials, 'from_service_account_file'), \
                 patch.object(builder, 'build', return_value=fake):
                with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                    builder.main()
            self.assertEqual(dest.read_text(), 'last good artifact')

    def test_live_builder_path_recovers_hm_and_preserves_payable_and_ad_rules(self):
        fake = FakeSheets()
        with tempfile.TemporaryDirectory(dir=Path(__file__).parent) as tmp:
            dest = Path(tmp) / 'out.json'
            with patch.object(builder, 'TORTS', [HM]), patch.object(builder, 'OUT_PATH', str(dest)), \
                 patch.object(builder.service_account.Credentials, 'from_service_account_file'), \
                 patch.object(builder, 'build', return_value=fake):
                builder.main()
            out = json.loads(dest.read_text())
        import datetime
        stamp = datetime.datetime.fromisoformat(out['generated_at'])
        self.assertIsNotNone(stamp.tzinfo, 'Build time must use an explicit timezone offset')
        self.assertEqual(len(out['torts']), 1, 'HM must not silently disappear')
        leads = out['torts'][0]['leads']
        self.assertEqual(len(leads), 5)  # exactly three non-payables, nothing else
        self.assertEqual(sum(r['signed'] for r in leads), 1)
        self.assertEqual({r['platform'] for r in leads}, {'YouTube'})
        self.assertEqual({r['label'] for r in leads}, {'800000000001'})
        self.assertTrue(all(r['spreadsheetId'] == builder.SRC_SHEET for r in fake.requests))


if __name__ == '__main__':
    unittest.main()
