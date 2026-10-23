"""Loopback-only application. Authentication tokens are configured server-side."""
import argparse, hashlib, hmac, json, os, sqlite3, logging, threading, time
from urllib.parse import urlsplit,parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from engine import Store, coverage
from providers import ProviderService
from evaluation import evaluate

def strict_json(raw):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise ValueError('Duplicate JSON key')
            result[key]=value
        return result
    def constant(value): raise ValueError('Nonfinite JSON number')
    return json.loads(raw,object_pairs_hook=pairs,parse_constant=constant)

class BoundedServer(ThreadingHTTPServer):
    """Bound concurrent socket handlers, including slow unauthenticated clients."""
    def __init__(self,*args,**kwargs):
        self.slots=threading.BoundedSemaphore(32)
        super().__init__(*args,**kwargs)
    def process_request(self,request,address):
        if not self.slots.acquire(blocking=False):
            request.close();return
        try: super().process_request(request,address)
        except BaseException: self.slots.release();raise
    def process_request_thread(self,request,address):
        try: super().process_request_thread(request,address)
        finally: self.slots.release()

def build_handler(store,tokens,providers=None):
    providers=providers or ProviderService(store)
    if not isinstance(tokens,dict) or not tokens or any(not isinstance(u,str) or not u.strip() or not isinstance(t,str) or len(t)<32 for u,t in tokens.items()) or len(set(tokens.values()))!=len(tokens): raise ValueError('Invalid authentication configuration')
    rate_lock=threading.Lock();rate_buckets={}
    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup();self.connection.settimeout(15)
        def log_message(self,*args): pass
        def rate_allowed(self):
            key=self.client_address[0];instant=time.monotonic()
            with rate_lock:
                start,count=rate_buckets.get(key,(instant,0))
                if instant-start>=60: start,count=instant,0
                rate_buckets[key]=(start,count+1)
                return count<240
        def request_error(self,status,message):
            logging.warning('request_failed status=%s',status)
            return self.send(status,{'error':message})
        def send(self,status,data,content='application/json',next_offset=None):
            body=data.encode() if isinstance(data,str) else json.dumps(data,allow_nan=False).encode()
            self.send_response(status);
            if next_offset is not None: self.send_header('X-Next-Offset',str(next_offset))
            self.send_header('Referrer-Policy','no-referrer');self.send_header('Content-Type',content);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff');self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'");self.end_headers();self.wfile.write(body)
        def user(self):
            auth=self.headers.get('Authorization','')
            for user,token in tokens.items():
                if hmac.compare_digest(auth.encode('utf-8'),('Bearer '+token).encode('utf-8')): return user
            return None
        def local_request(self):
            host=self.headers.get('Host','')
            allowed={'127.0.0.1:'+str(self.server.server_port),'localhost:'+str(self.server.server_port)}
            return host in allowed and self.headers.get('Origin','http://'+host)=='http://'+host
        def do_GET(self):
            if not self.rate_allowed(): return self.request_error(429,'Local request rate exceeded; retry in one minute')
            if not self.local_request(): return self.send(403,{'error':'Loopback origin required'})
            if self.path in ['/', '/ui.js','/style.css']:
                file={'/':'index.html','/ui.js':'ui.js','/style.css':'style.css'}[self.path]
                try: return self.send(200,(Path(__file__).parent/'web'/file).read_text(),{'/':'text/html','/ui.js':'text/javascript','/style.css':'text/css'}[self.path])
                except OSError: return self.request_error(503,'Application assets unavailable')
            user=self.user()
            if not user: return self.send(401,{'error':'Authentication required'})
            routes={'/api/research':lambda:store.board(user),'/api/wagers':lambda:store.rows(user,'wagers'),'/api/performance':lambda:store.report(user),'/api/audit':lambda:store.audit(user),'/api/states':lambda:store.rows(user,'states'),'/api/limits':lambda:store.rows(user,'limits'),'/api/coverage':lambda:providers.coverage(user) or coverage(),'/api/providers':lambda:{'health':providers.health(),'catalog':providers.catalog(user)},'/api/health':lambda:{'providers':providers.health(),'models':[],'execution':'disabled','latency':'unknown'}}
            routes['/api/settings']=lambda:store.settings(user)
            try:
                parsed=urlsplit(self.path);query=parse_qs(parsed.query,keep_blank_values=True,strict_parsing=True,max_num_fields=8)
                if any(len(v)!=1 for v in query.values()): raise ValueError('Duplicate query parameter')
                allowed={'limit','offset','event_id','sportsbook','after','before'}
                if set(query)-allowed: raise ValueError('Unknown query parameter')
                params={k:v[0] for k,v in query.items()}
                limit=int(params.pop('limit',100));offset=int(params.pop('offset',0))
                path=parsed.path
                if path in ['/odds/latest','/odds/history','/api/research']:
                    result=store.odds_page(user,latest=path!='/odds/history',limit=limit,offset=offset,**params)
                    return self.send(200,result if path.startswith('/odds/') else result['items'],next_offset=result['next_offset'])
                if params: raise ValueError('Filters only supported on odds endpoints')
                collections={'/api/wagers':'wagers','/api/audit':'audit','/api/states':'states','/api/limits':'limits','/api/event_maps':'event_maps','/api/aliases':'aliases','/api/provider_failures':'provider_failures'}
                if path in collections:
                    result=store.record_page(user,collections[path],limit,offset)
                    return self.send(200,result['items'],next_offset=result['next_offset'])
                if path not in routes: return self.send(404,{'error':'Not found'})
                result=routes[path]()
                if isinstance(result,list):
                    if not 1<=limit<=500 or not 0<=offset<=1000000: raise ValueError('Invalid pagination')
                    return self.send(200,result[offset:offset+limit],next_offset=offset+limit if len(result)>offset+limit else None)
                self.send(200,result)
            except (ValueError,KeyError,TypeError): self.request_error(400,'Invalid request or query parameters')
            except sqlite3.Error: self.request_error(503,'Storage temporarily unavailable; retry the same request')
        def do_POST(self):
            if not self.rate_allowed(): return self.request_error(429,'Local request rate exceeded; retry in one minute')
            if not self.local_request(): return self.send(403,{'error':'Loopback origin required'})
            user=self.user()
            if not user: return self.send(401,{'error':'Authentication required'})
            routes={'/api/quotes':store.import_quote,'/api/quote_batch':store.bulk_quotes,'/api/states':store.state,'/api/wagers':store.wager,'/api/settle':store.settle,'/api/limits':store.limits,'/api/provider':providers.action,'/api/evaluate':lambda user,d:evaluate(d['rows'],d['train_end'],d['validation_end'])}
            routes['/api/settings']=store.configure
            routes['/api/event_maps']=store.event_mapping
            routes['/api/aliases']=store.alias
            if self.path not in routes: return self.send(403,{'error':'Unsupported action; real-money execution is disabled'})
            try:
                size=int(self.headers.get('Content-Length','0'))
                if size<=0 or size>1000000: raise ValueError('Invalid request size')
                if self.headers.get('Content-Type','').split(';')[0]!='application/json': raise ValueError('JSON content type required')
                data=strict_json(self.rfile.read(size))
                if not isinstance(data,dict): raise ValueError('Expected a JSON object')
                if self.path=='/api/quote_batch': data=data['quotes']
                if self.path in ['/api/quotes','/api/quote_batch']:
                    for q in data if isinstance(data,list) else [data]:
                        if not isinstance(q,dict): raise ValueError('Expected quote object')
                        q['provenance']='manual_unverified';q['rules_verified']=False
                if self.path=='/api/states': data['mode']='manual'
                self.send(200,routes[self.path](user,data))
            except (ValueError,KeyError,TypeError) as e: self.send(400,{'error':str(e)})
            except sqlite3.Error: self.request_error(503,'Storage temporarily unavailable; retry the same request')
            except (OSError,TimeoutError): self.request_error(408,'Request timed out or connection failed')
    return Handler

def main():
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);p.add_argument('--db',default='research.sqlite3');args=p.parse_args()
    tokens=json.loads(os.environ.get('BETTING_USERS','{}'))
    if not tokens or any(not isinstance(t,str) or len(t)<32 for t in tokens.values()) or len(set(tokens.values()))!=len(tokens): raise SystemExit('Set BETTING_USERS to distinct user tokens of at least 32 characters. See README.')
    os.umask(0o077)
    logging.basicConfig(level=logging.WARNING,format='%(levelname)s %(message)s')
    BoundedServer(('127.0.0.1',args.port),build_handler(Store(args.db),tokens)).serve_forever()
if __name__=='__main__': main()
