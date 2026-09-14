"""Offline tests of scheduler receipt validation and failure alerts."""
import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import importlib

class CronReceiptTests(unittest.TestCase):
 def test_success_requires_verified_publisher_receipt_and_stays_quiet(self):
  try: runner=importlib.import_module('cron_bp_utm')
  except ModuleNotFoundError: runner=None
  self.assertTrue(callable(getattr(runner,'main',None)),'cron receipt validator missing')
  from subprocess import CompletedProcess
  receipt={'status':'fresh_published','commit':'a'*40,'sha256':'b'*64}
  with tempfile.TemporaryDirectory() as tmp, patch.object(runner,'STATE',Path(tmp)):
   for text,code,expected in [(json.dumps(receipt),0,0),('',0,1),('{"status":"built_locally"}',0,1),('',1,1)]:
    out=io.StringIO()
    with patch.object(runner.subprocess,'run',return_value=CompletedProcess([],code,text,'sanitized error')),contextlib.redirect_stdout(out):
     self.assertEqual(runner.main(),expected)
    self.assertEqual(bool(out.getvalue()),bool(expected))
   saved=json.loads((Path(tmp)/'last-success.json').read_text())
   self.assertEqual(saved['commit'],receipt['commit'])
   self.assertEqual((Path(tmp)/'last-success.json').stat().st_mode & 0o777,0o600)
 def test_timeout_alerts_not_success(self):
  runner=importlib.import_module('cron_bp_utm')
  import subprocess
  with tempfile.TemporaryDirectory() as tmp, patch.object(runner,'STATE',Path(tmp)),patch.object(runner.subprocess,'run',side_effect=subprocess.TimeoutExpired('publisher',1800)),contextlib.redirect_stdout(io.StringIO()) as out:
   self.assertEqual(runner.main(),1)
   self.assertIn('FAILED',out.getvalue())

if __name__=='__main__':unittest.main()
