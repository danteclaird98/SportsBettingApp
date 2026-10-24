"""EdgeBoard Next: single-user loopback research workspace, Python standard library."""
from __future__ import annotations
import argparse
import base64
import binascii
import atexit
import subprocess
import mimetypes
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
import os
from pathlib import Path
import secrets
import sqlite3
import sys
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parent))
from edgeodds.ingestion import IngestionStore
from edgeodds.integrations.edgeboard import edgeboard_contract


def now():
    return datetime.now(timezone.utc).isoformat()


def amount(value, *, positive=False):
    if isinstance(value, bool):
        raise ValueError('Invalid amount')
    try:
        n = Decimal(str(value))
        if not n.is_finite() or n < 0 or n > 10000000 or n != n.quantize(Decimal('.01')) or (positive and n == 0):
            raise ValueError('Use a valid amount with at most two decimal places')
        return int(n * 100)
    except InvalidOperation:
        raise ValueError('Invalid amount')


def text(value, label, limit=200):
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f'{label} is required (maximum {limit} characters)')
    return value.strip()


class Workspace:
    def __init__(self, path):
        self.path = str(path)
        Path(path).parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.connect() as db:
            db.executescript('''
            CREATE TABLE IF NOT EXISTS wagers(id INTEGER PRIMARY KEY, mode TEXT NOT NULL,
              book TEXT NOT NULL, external_id TEXT, selection TEXT NOT NULL, odds REAL NOT NULL,
              stake INTEGER NOT NULL, payout INTEGER, status TEXT NOT NULL DEFAULT 'open',
              created_at TEXT NOT NULL, settled_at TEXT);
            CREATE UNIQUE INDEX IF NOT EXISTS wager_external ON wagers(mode,book,external_id) WHERE external_id IS NOT NULL;
            CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY, at TEXT NOT NULL, action TEXT NOT NULL, payload TEXT NOT NULL);
            CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
            CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit BEGIN SELECT RAISE(ABORT,'immutable audit'); END;
            CREATE TABLE IF NOT EXISTS settings(id INTEGER PRIMARY KEY CHECK(id=1), bankroll INTEGER, daily_limit INTEGER, exposure_limit INTEGER);
            INSERT OR IGNORE INTO settings VALUES(1,100000,10000,20000);
            ''')
        os.chmod(self.path, 0o600)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        db.row_factory = sqlite3.Row
        try:
            with db:
                yield db
        finally:
            db.close()

    def state(self):
        with self.connect() as db:
            return {'wagers':[dict(r) for r in db.execute('SELECT * FROM wagers ORDER BY id DESC')],
                    'settings':dict(db.execute('SELECT * FROM settings').fetchone()),
                    'audit_count':db.execute('SELECT count(*) FROM audit').fetchone()[0],
                    'storage':'Local SQLite · single user'}

    def mutate(self, route, data):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            if route == '/api/settings':
                values = [amount(data.get(k),positive=True) for k in ('bankroll','daily_limit','exposure_limit')]
                db.execute('UPDATE settings SET bankroll=?,daily_limit=?,exposure_limit=? WHERE id=1',values)
            elif route == '/api/wagers':
                mode = data.get('mode')
                if mode not in ('paper','actual'):
                    raise ValueError('Choose paper or actual')
                book = text(data.get('book'),'Sportsbook',80).casefold()
                selection = text(data.get('selection'),'Selection')
                stake = amount(data.get('stake'),positive=True)
                odds = data.get('odds')
                if isinstance(odds,bool) or not isinstance(odds,(int,float)) or not math.isfinite(odds) or not 1 < odds <= 1000:
                    raise ValueError('Decimal odds must be greater than 1 and at most 1000')
                external = data.get('external_id')
                external = text(external,'Ticket ID',120) if mode == 'actual' else None
                settings = db.execute('SELECT * FROM settings').fetchone()
                daystake = db.execute("SELECT coalesce(sum(stake),0) FROM wagers WHERE mode=? AND substr(created_at,1,10)=?",(mode,now()[:10])).fetchone()[0]
                exposure = db.execute("SELECT coalesce(sum(stake),0) FROM wagers WHERE mode=? AND status='open'",(mode,)).fetchone()[0]
                if daystake+stake > settings['daily_limit'] or exposure+stake > settings['exposure_limit']:
                    raise ValueError('Daily stake or open exposure limit exceeded')
                db.execute('INSERT INTO wagers(mode,book,external_id,selection,odds,stake,created_at) VALUES(?,?,?,?,?,?,?)',(mode,book,external,selection,odds,stake,now()))
            elif route == '/api/settle':
                if data.get('confirmed') is not True:
                    raise ValueError('Confirm the settled total payout')
                if type(data.get('id')) is not int:
                    raise ValueError('Invalid wager ID')
                row = db.execute('SELECT * FROM wagers WHERE id=?',(data['id'],)).fetchone()
                if not row or row['status'] != 'open':
                    raise ValueError('Wager missing or already settled')
                status = data.get('status')
                if status not in ('win','loss','push','void'):
                    raise ValueError('Invalid settlement')
                payout = amount(data.get('payout'))
                if (status == 'loss' and payout != 0) or (status in ('push','void') and payout != row['stake']) or (status == 'win' and payout <= row['stake']):
                    raise ValueError('Payout does not match settlement. Enter total returned including stake.')
                db.execute('UPDATE wagers SET status=?,payout=?,settled_at=? WHERE id=?',(status,payout,now(),row['id']))
            else:
                raise ValueError('Unknown action')
            db.execute('INSERT INTO audit(at,action,payload) VALUES(?,?,?)',(now(),route,json.dumps(data,allow_nan=False)))
        return self.state()


def demo_board():
    # Deliberately fixed synthetic fixtures: never relabeled or refreshed as live.
    events=[]
    for i,(league,away,home,prices) in enumerate([
        ('NFL','Buffalo Bills','Kansas City Chiefs',[2.15,2.10,2.08]),
        ('NBA','Boston Celtics','New York Knicks',[1.91,1.95,1.89]),
        ('MLB','New York Yankees','Los Angeles Dodgers',[2.02,2.06,2.00]),
        ('NHL','Edmonton Oilers','Florida Panthers',[1.88,1.92,1.90])]):
        events.append({'event_id':f'demo-{i}','league':league,'away':away,'home':home,'starts_at':None,
            'quotes':[{'book':b,'selection':away,'family':'moneyline','line':None,'period':'full_game',
            'decimal':p,'source_updated_at':None,'rules_verified':False,'model_probability':None,
            'ev_per_unit':None,'status':'SYNTHETIC','reasons':['DEMO_ONLY','MODEL_UNAVAILABLE','RULES_UNVERIFIED']}
            for b,p in zip(['DraftKings','FanDuel','Caesars'],prices)]})
    return {'mode':'demo','events':events,'live_verified':False,'status':'SYNTHETIC FIXTURES · NOT CURRENT GAMES OR PRICES'}


def live_board(store):
    events=[]
    for event in store.events(mode='network',limit=100):
        eid=event['event_id']
        board=edgeboard_contract(store.edgeboard(eid,mode='network',limit=200))
        quotes=[]
        for q in board['quotes']:
            quotes.append({'book':q['book'],'selection':q['market']['selection'],'family':q['market']['family'],
              'line':q['market']['line'],'period':q['market']['period'],'decimal':q['price']['decimal'],
              'source_updated_at':q['timestamps']['quote_updated_at'],'rules_verified':q['market']['settlement_rules']['verified'],
              'model_probability':q['analysis']['model_probability'],'ev_per_unit':q['analysis']['ev_per_unit'],
              'status':q['analysis']['qualification'],'reasons':q['analysis']['exclusion_reasons'], 'evidence':q})
        events.append({**event,'away':event.get('away_id'),'home':event.get('home_id'),'quotes':quotes,'contract':board})
    return {'mode':'network','events':events,'live_verified':False,'status':'CAPTURED SOURCE DATA' if events else 'NO CAPTURED NETWORK QUOTES · SOURCE UNAVAILABLE',
            'coverage':'At most 100 events and 200 quotes per event; not a full-board scan.'}


def report_catalog():
    return [{'id':p.name,'report':json.loads(p.read_text())} for p in sorted((ROOT/'reports').glob('*.json'))]


def access_credentials(host):
    username = os.environ.get('WORKSPACE_USER', '')
    password = os.environ.get('WORKSPACE_PASSWORD', '')
    if bool(username) != bool(password):
        raise ValueError('Set both WORKSPACE_USER and WORKSPACE_PASSWORD')
    if username and (':' in username or len(password) < 24):
        raise ValueError('Use a username without colons and a password of at least 24 characters')
    if host not in ('127.0.0.1', 'localhost', '::1') and not password:
        raise ValueError('External binding requires WORKSPACE_USER and WORKSPACE_PASSWORD; place behind HTTPS')
    return (username, password) if password else None


def make_handler(workspace, store, token, credentials=None, api_key=None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args): pass
        def authorized(self):
            self.api_authenticated = False
            path = urlsplit(self.path).path
            if api_key and path.startswith(('/api/', '/research-api/')):
                supplied = self.headers.get('Authorization', '')
                scheme, _, value = supplied.partition(' ')
                if scheme.lower() == 'bearer' and secrets.compare_digest(value.encode('utf-8'), api_key.encode('utf-8')):
                    self.api_authenticated = True
                    return True
            if credentials is None and not (api_key and path.startswith(('/api/', '/research-api/'))):
                return True
            try:
                scheme, encoded = self.headers.get('Authorization', '').split(' ', 1)
                if scheme.lower() != 'basic':
                    raise ValueError('Unsupported authorization')
                supplied = base64.b64decode(encoded, validate=True)
                expected = (credentials[0] + ':' + credentials[1]).encode('utf-8') if credentials else b''
                if credentials and secrets.compare_digest(supplied, expected):
                    return True
            except (ValueError, binascii.Error):
                pass
            self.send_response(401)
            self.send_header('WWW-Authenticate', 'Basic realm="EdgeBoard private workspace", charset="UTF-8"')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()
            self.close_connection = True
            return False
        def reply(self,status,data,kind='application/json; charset=utf-8'):
            body=json.dumps(data,allow_nan=False).encode() if kind.startswith('application/json') else data
            self.send_response(status)
            for k,v in {'Content-Type':kind,'Content-Length':str(len(body)),'Cache-Control':'no-store',
                'X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer',
                'Content-Security-Policy':"default-src 'self'; style-src 'self'; script-src 'self'; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"}.items(): self.send_header(k,v)
            self.end_headers(); self.wfile.write(body)
        def research_proxy(self):
            if not self.api_authenticated and not secrets.compare_digest(self.headers.get('X-Workspace-Token',''),token):
                return self.reply(403,{'error':'Reload workspace before using research'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 <= length <= 1048576: raise ValueError('Request too large')
                body=self.rfile.read(length) if length else None
                target='http://127.0.0.1:8091'+self.path.removeprefix('/research-api')
                owner='local-owner' if self.api_authenticated else self.headers.get('X-Local-Research-User','')
                request=Request(target,data=body,method=self.command,headers={'Content-Type':'application/json','X-Local-Research-User':owner})
                try:
                    with urlopen(request,timeout=180) as response:
                        return self.reply(response.status,json.load(response))
                except HTTPError as exc:
                    return self.reply(exc.code,json.load(exc))
            except (URLError,TimeoutError): self.reply(503,{'error':'Research runtime is unavailable. Start using next_app/server.py.'})
            except (ValueError,TypeError): self.reply(400,{'error':'Invalid research request'})

        def do_GET(self):
            if not self.authorized(): return
            parsed=urlsplit(self.path)
            if parsed.path.startswith('/research-api/'):
                return self.research_proxy()
            if parsed.path == '/advanced' or parsed.path.startswith('/advanced/'):
                relative=parsed.path.removeprefix('/advanced').lstrip('/') or 'index.html'
                root=(ROOT/'research_runtime/dist').resolve()
                target=(root/relative).resolve()
                if not target.is_relative_to(root) or not target.is_file():
                    return self.reply(404,{'error':'Build research runtime with npm run build first'})
                return self.reply(200,target.read_bytes(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
            try:
                if parsed.path == '/api/bootstrap':
                    return self.reply(200,{'csrf':token,'state':workspace.state(),'sources':json.loads((ROOT/'sources.json').read_text())})
                if parsed.path == '/api/board':
                    mode=parse_qs(parsed.query).get('mode',['network'])[0]
                    if mode not in ('network','demo'): raise ValueError('Invalid mode')
                    return self.reply(200,demo_board() if mode=='demo' else live_board(store))
                if parsed.path == '/api/health': return self.reply(200,store.health(credential_configured=bool(os.environ.get('SPORTRADAR_API_KEY'))))
                if parsed.path == '/api/models': return self.reply(200,{'models':report_catalog(),'live_approved':False})
                if parsed.path == '/api/export': return self.reply(200,{'exported_at':now(),**workspace.state(),'models':report_catalog(),'sources':json.loads((ROOT/'sources.json').read_text())})
                files={'/':'index.html','/app.js':'app.js','/style.css':'style.css'}
                if parsed.path in files:
                    name=files[parsed.path]; kind='text/html; charset=utf-8' if name.endswith('html') else 'text/javascript; charset=utf-8' if name.endswith('js') else 'text/css; charset=utf-8'
                    return self.reply(200,(ROOT/'web'/name).read_bytes(),kind)
                self.reply(404,{'error':'Not found'})
            except (ValueError,KeyError) as exc: self.reply(400,{'error':str(exc)})
            except (OSError,sqlite3.Error): self.reply(503,{'error':'Storage unavailable'})
        def do_POST(self):
            if not self.authorized(): return
            if self.headers.get('Sec-Fetch-Site') == 'cross-site': return self.reply(403,{'error':'Cross-site request rejected'})
            if urlsplit(self.path).path.startswith('/research-api/'):
                return self.research_proxy()
            if not self.api_authenticated and not secrets.compare_digest(self.headers.get('X-Workspace-Token',''),token): return self.reply(403,{'error':'Reload this workspace before saving'})
            if self.headers.get('Sec-Fetch-Site') == 'cross-site': return self.reply(403,{'error':'Cross-site request rejected'})
            try:
                length=int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 65536: raise ValueError('Request too large or empty')
                data=json.loads(self.rfile.read(length))
                if not isinstance(data,dict): raise ValueError('Expected an object')
                self.reply(200,workspace.mutate(urlsplit(self.path).path,data))
            except sqlite3.IntegrityError: self.reply(409,{'error':'This sportsbook ticket ID is already recorded'})
            except (ValueError,TypeError,KeyError) as exc: self.reply(400,{'error':str(exc)})
            except sqlite3.Error: self.reply(503,{'error':'Storage unavailable'})
    return Handler


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',type=int,default=8080)
    parser.add_argument('--host',default='127.0.0.1',help='External binding requires password protection and an HTTPS reverse proxy')
    parser.add_argument('--data-dir',type=Path,default=ROOT/'data')
    parser.add_argument('--odds-db',type=Path,help='Existing EdgeOdds ingestion SQLite database')
    args=parser.parse_args()
    try:
        credentials=access_credentials(args.host)
        api_key=os.environ.get('WORKSPACE_API_KEY') or None
        if api_key and len(api_key) < 32:
            raise ValueError('WORKSPACE_API_KEY must contain at least 32 characters')
    except ValueError as exc:
        parser.error(str(exc))
    workspace=Workspace(args.data_dir/'workspace.sqlite3')
    store=IngestionStore(args.odds_db or args.data_dir/'edgeodds.sqlite3')
    runtime=ROOT/'research_runtime'
    if (runtime/'build/backend.mjs').is_file():
        env=dict(os.environ,RESEARCH_DB=str((args.data_dir/'research.sqlite3').resolve()))
        child=subprocess.Popen(['node','runtime.mjs'],cwd=runtime,env=env)
        atexit.register(child.terminate)
    server=ThreadingHTTPServer((args.host,args.port),make_handler(workspace,store,secrets.token_urlsafe(32),credentials,api_key))
    print(f'EdgeBoard Next: http://{args.host}:{args.port}',flush=True)
    server.serve_forever()

if __name__=='__main__': main()
