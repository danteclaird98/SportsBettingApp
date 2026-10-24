"""Disposable Docker smoke check: authentication, scoring, recovery and shutdown."""
import argparse
import os
import secrets
import subprocess
import time


PROBE=r'''
import base64,json,os,time
from datetime import datetime,timedelta,timezone
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen
base='http://127.0.0.1:10000'
api={'Authorization':'Bearer '+os.environ['WORKSPACE_API_KEY']}
basic={'Authorization':'Basic '+base64.b64encode(('owner:'+os.environ['WORKSPACE_PASSWORD']).encode()).decode()}
def call(path,body=None,headers=api,expected=200):
    try: response=urlopen(Request(base+path,data=body,headers=headers),timeout=3)
    except HTTPError as error: response=error
    with response:
        assert response.code==expected,(path,response.code,expected)
        raw=response.read()
        return json.loads(raw) if raw else {}
for attempt in range(50):
    try: call('/healthz',headers={}); break
    except (URLError,ConnectionError): time.sleep(.2)
else: raise AssertionError('Container startup did not become ready')
assert call('/healthz',headers={})=={'status':'ok'}
assert call('/api/system/readiness')['apiKeyConfigured'] is True
for path in ('/','/advanced/','/api/export','/api/receiving60/receipts'):
    call(path,headers={},expected=401)
with urlopen(Request(base+'/advanced/',headers=basic),timeout=3) as response:
    assert b'<html' in response.read().lower()
with urlopen(Request(base+'/receiving60.js',headers=basic),timeout=3) as response:
    assert b'configureReceiving60' in response.read()
now=datetime.now(timezone.utc).replace(microsecond=0)
stamp=lambda value:value.isoformat().replace('+00:00','Z')
payload={'request':{'playerId':'synthetic-player','gameId':'synthetic-future',
    'kickoffAt':stamp(now+timedelta(days=7)),'decisionAt':stamp(now),
    'league':'NFL','position':'WR','seasonType':'REG','period':'FULL_GAME',
    'stat':'receiving_yards','threshold':60,'comparison':'>='},'history':[
    {'playerId':'synthetic-player','gameId':f'past-{days}',
     'kickoffAt':stamp(now-timedelta(days=days)),
     'resolvedAt':stamp(now-timedelta(days=days)+timedelta(hours=3)),
     'observedAt':stamp(now-timedelta(days=days)+timedelta(hours=4)),
     'receivingYards':yards} for days,yards in [(21,-5),(14,60),(7,80)]]}
ready=call('/api/receiving60/readiness')
assert ready['artifactVerified'] is True
result=call('/api/receiving60/predict',json.dumps(payload).encode())
assert result['features']==[45,45,2/3,2/3,3]
assert result['estimateAvailable'] is True and 0<=result['probability']<=1
assert result['status']=='HOLD' and result['liveApproved'] is False
assert result['uncertainty'] is None and result['expectedValue'] is None
assert result['canonicalArtifactSha256']=='7852516f02ee5eaf6337feedaadaf41b930af5931ca6181614ff92794c0f54f8'
call('/api/receiving60/predict',b'{',expected=400)
assert call('/api/receiving60/predict',b'{}',expected=422)['probability'] is None
call('/api/receiving60/predict',b'{}',headers={'Authorization':'Bearer wrong'},expected=401)
before_invalid=len(call('/api/receiving60/receipts')['receipts'])
for yards in (9007199254740993,-9007199254740993):
    invalid=json.loads(json.dumps(payload)); invalid['history'][0]['receivingYards']=yards
    rejected=call('/api/receiving60/predict',json.dumps(invalid).encode(),expected=422)
    assert rejected['reason']=='INVALID_HISTORY_YARDAGE'
    envelope={'inputMode':'supplied','input':invalid,'expectedArtifactSha256':result['canonicalArtifactSha256']}
    rejected=call('/api/receiving60/receipts',json.dumps(envelope).encode(),expected=422)
    assert rejected['reason']=='INVALID_HISTORY_YARDAGE'
assert len(call('/api/receiving60/receipts')['receipts'])==before_invalid
records=call('/api/receiving60/receipts')['receipts']
if not records:
    envelope={'inputMode':'synthetic','input':payload,'expectedArtifactSha256':result['canonicalArtifactSha256']}
    record=call('/api/receiving60/receipts',json.dumps(envelope).encode(),expected=201)
    duplicate=call('/api/receiving60/receipts',json.dumps(envelope).encode())
    assert duplicate['id']==record['id']
    records=call('/api/receiving60/receipts')['receipts']
assert len(records)==1
saved=call('/api/receiving60/receipts/'+str(records[0]['id']))
assert saved['request']['history'][0]['receivingYards']==-5
assert saved['scoreReceipt']['status']=='HOLD'
assert saved['inputModeProvenance']=='CLIENT_DECLARED'
state=call('/api/bootstrap')['state']
if not state['wagers']:
    call('/api/wagers',json.dumps({'mode':'paper','book':'smoke',
        'selection':'Synthetic test','odds':2,'stake':'1'}).encode())
else: assert len(state['wagers'])==1
print('PASS: readiness, access, synthetic score, abstention, saved receipt and wager persistence')
'''

BACKUP=r'''
from pathlib import Path
from next_app.backup import create_backup,verify_backup,restore_backup
from next_app.server import Workspace
snapshot=Path('/var/data/backups/smoke')
create_backup('/var/data',snapshot)
verify_backup(snapshot)
restore_backup(snapshot,'/var/data/restored-smoke')
restored=Workspace('/var/data/restored-smoke/workspace.sqlite3')
assert len(restored.receiving60_records()['receipts'])==1
assert len(restored.state()['wagers'])==1
print('PASS: online backup, checksum verification and isolated receipt restore')
'''

KILL_RESEARCH=r'''
from pathlib import Path
import os,signal
for item in Path('/proc').iterdir():
    if not item.name.isdigit(): continue
    try: command=(item/'cmdline').read_bytes().split(b'\0')
    except (OSError,PermissionError): continue
    if b'runtime.mjs' in command and command[0].endswith(b'node'):
        os.kill(int(item.name),signal.SIGKILL)
        break
else: raise AssertionError('Research process not found')
'''


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',default='edgeboard-render:local')
    args=parser.parse_args()
    env=dict(os.environ,WORKSPACE_USER='owner',WORKSPACE_PASSWORD=secrets.token_urlsafe(32),WORKSPACE_API_KEY=secrets.token_urlsafe(32))
    for key in ('DOCKER_HOST','DOCKER_CONTEXT','DOCKER_TLS','DOCKER_TLS_VERIFY','DOCKER_CERT_PATH'): env.pop(key,None)
    prefix=['docker','--host=unix:///var/run/docker.sock']
    name='edgeboard-check-'+secrets.token_hex(4); volume=name+'-data'
    def docker(*arguments,script=None):
        result=subprocess.run(prefix+list(arguments),env=env,input=script,capture_output=True,text=True,timeout=60)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)
        return result.stdout.strip()
    def execute(script): print(docker('exec','-i',name,'python','-',script=script),flush=True)
    try:
        docker('volume','create',volume)
        docker('run','-d','--name',name,'-v',volume+':/var/data','-e','WORKSPACE_USER',
            '-e','WORKSPACE_PASSWORD','-e','WORKSPACE_API_KEY',args.image)
        execute(PROBE)
        docker('restart',name)
        execute(PROBE)
        execute(BACKUP)
        execute(KILL_RESEARCH)
        for attempt in range(30):
            if docker('inspect','--format','{{.State.Running}}',name)=='false': break
            time.sleep(.2)
        else: raise AssertionError('Workspace did not stop after research failure')
        assert docker('inspect','--format','{{.State.ExitCode}}',name)=='1'
        docker('restart',name); execute(PROBE)
        print('PASS: research failure stops service; restart recovers original saved data',flush=True)
    except Exception:
        try: print(docker('logs',name),flush=True)
        except RuntimeError: pass
        raise
    finally:
        try: docker('rm','-f',name)
        finally: docker('volume','rm',volume)


if __name__=='__main__': main()
