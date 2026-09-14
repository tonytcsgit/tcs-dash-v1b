#!/usr/bin/python3
"""Scheduler entry: require a public-verified receipt; only failures notify chat."""
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parent
STATE=Path('/Users/andyoc/.cache/tcs-bp-utm-publisher/receipts')

def main():
    try:
        STATE.mkdir(parents=True,exist_ok=True,mode=0o700)
        STATE.chmod(0o700)
        result=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'refresh_bp_utm.py')],
            cwd=ROOT,env=dict(os.environ,HOME='/Users/andyoc',
                PATH='/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin',
                PYTHONDONTWRITEBYTECODE='1'),capture_output=True,text=True,timeout=1800)
        log=STATE/'last-run.log'
        fd=os.open(log,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as out:
            out.write(dt.datetime.now(dt.timezone.utc).isoformat()+'\n'+result.stdout+'\n'+result.stderr)
        if result.returncode:
            raise ValueError('Publisher failed; '+result.stderr.strip()[:500])
        receipt=json.loads(result.stdout)
        if (receipt.get('status') not in {'fresh_published','pending_commit_published'}
            or not re.fullmatch('[a-f0-9]{40}',receipt.get('commit',''))
            or not re.fullmatch('[a-f0-9]{64}',receipt.get('sha256',''))):
            raise ValueError('Publisher returned no valid public-verification receipt')
        receipt['verified_at']=dt.datetime.now(dt.timezone.utc).isoformat()
        temp=STATE/'last-success.json.tmp'
        fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
        with os.fdopen(fd,'w') as out:
            json.dump(receipt,out,indent=2);out.flush();os.fsync(out.fileno())
        os.replace(temp,STATE/'last-success.json')
        return 0
    except subprocess.TimeoutExpired:
        print('BP UTM refresh FAILED: publisher timed out. Check GitHub Pages, source access and private publisher lock before retrying. Main financial refresh remains paused.')
    except Exception as error:
        detail=str(error) if isinstance(error,ValueError) and str(error).startswith(('Publisher failed;','Publisher returned')) else 'Missing/invalid receipt or local runner failure'
        print('BP UTM refresh FAILED: '+detail+'. Diagnostics: '+str(STATE/'last-run.log')+'. Main financial refresh remains paused.')
    return 1

if __name__=='__main__':raise SystemExit(main())
