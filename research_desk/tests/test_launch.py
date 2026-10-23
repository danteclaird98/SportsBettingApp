"""Launch regressions: adversarial identities, persistence, concurrency and HTTP contracts."""
import copy,json,multiprocessing,sqlite3,subprocess,sys,tempfile,threading,unittest,urllib.request,urllib.error
from datetime import datetime,timedelta,timezone
from pathlib import Path
import test_app as f
from test_expansion import snapshot,at,prediction
from engine import Store,now
from providers import normalize_odds,ProviderService,OddsAPI,ProviderError
from core import american_to_decimal,fractional_to_decimal,implied_probability
from server import build_handler,BoundedServer

def enter_worker(path,number,gate,result):
    store=Store(path);w=f.wager();w.update(id=str(number),mode='actual')
    gate.wait()
    try: store.wager('a',w);result.put(True)
    except ValueError: result.put(False)

def quote_worker(path,quote,number,gate,result):
    store=Store(path);quote=dict(quote,id='worker:'+str(number),retrieved_at=now())
    gate.wait()
    result.put(store.import_quote('a',quote)['duplicate'])

class Launch(unittest.TestCase):
    setUp=f.Workflow.setUp
    tearDown=f.Workflow.tearDown
    def test_semantic_dedupe_changed_envelope_and_restart(self):
        q=f.quote();self.s.import_quote('a',q)
        q.update(id='retry',retrieved_at=now(),source_payload_hash='different envelope')
        result=Store(self.s.path).import_quote('a',q)
        self.assertTrue(result['duplicate']);self.assertEqual(result['id'],'q')
        self.assertEqual(len(self.s.rows('a','quotes')),1)
    def test_changed_price_same_observation_is_conflict(self):
        q=f.quote();q.update(provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        q.update(id='conflict',decimal_odds=3);self.s.import_quote('a',q)
        self.assertTrue(all(r['best_observed_decimal'] is None for r in self.s.board('a')))
        self.assertEqual(len(self.s.odds_page('a')['items']),2)
    def test_same_teams_different_dates_cannot_reuse_mapping(self):
        q=f.quote();self.s.import_quote('a',q)
        q.update(id='tomorrow',start_at=at(90000))
        with self.assertRaisesRegex(ValueError,'mapping conflict'): self.s.import_quote('a',q)
        q.update(event_id='tomorrow',provider_event_id='other');self.s.import_quote('a',q)
        self.assertEqual(len(self.s.odds_page('a')['items']),2)
    def test_explicit_postponement_and_reschedule_invalidate_old(self):
        q=f.quote();q.update(provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        mapping=dict({k:q[k] for k in ['provider','provider_event_id','event_id','sport','league','start_at']},revision=2,status='postponed',reason='Fixture postponement')
        self.s.event_mapping('a',mapping);self.assertIsNone(self.s.board('a')[0]['best_observed_decimal'])
        mapping.update(start_at=at(90000),revision=3,status='active');self.s.event_mapping('a',mapping)
        q.update(id='rescheduled',start_at=mapping['start_at']);self.s.import_quote('a',q)
        self.assertEqual(self.s.board('a')[-1]['best_observed_decimal'],2.1)
        self.assertIsNone(self.s.board('a')[0]['best_observed_decimal'])
    def test_neutral_site_uses_source_id_not_home_away_title(self):
        p=snapshot();p['home_team']='Los Angeles Lakers';p['away_team']='Boston Celtics'
        p['bookmakers'][0]['markets'][0]['outcomes']=[dict(name=t,price=2) for t in [p['home_team'],p['away_team']]]
        result=normalize_odds(p,now());self.s.bulk_quotes('a',result['quotes'])
        p['home_team'],p['away_team']=p['away_team'],p['home_team']
        self.s.bulk_quotes('a',normalize_odds(p,now())['quotes'])
        self.assertEqual(len({q['event_id'] for q in self.s.rows('a','quotes')}),1)
    def test_team_book_alias_is_explicit_and_scoped(self):
        self.s.alias('a',dict(kind='team',league='test',source='LA Lakers',target='Los Angeles Lakers'))
        self.s.alias('a',dict(kind='book',league='test',source='DK',target='DraftKings'))
        q=f.quote();q.update(selection='LA Lakers',sportsbook='DK');self.s.import_quote('a',q)
        saved=self.s.rows('a','quotes')[0];self.assertEqual(saved['selection'],'Los Angeles Lakers');self.assertEqual(saved['sportsbook'],'DraftKings')
    def test_cross_provider_merge_requires_explicit_mapping(self):
        q=f.quote();self.s.import_quote('a',q);q.update(id='q2',provider='other')
        with self.assertRaisesRegex(ValueError,'explicit cross-provider'):self.s.import_quote('a',q)
    def test_price_format_errors_and_fractional_math(self):
        for value in [True,0,1,-1,99,-99]:
            with self.assertRaises(ValueError):american_to_decimal(value)
        self.assertEqual(fractional_to_decimal('5/2'),3.5)
        self.assertAlmostEqual(implied_probability(3.5,'decimal'),2/7)
        for value in ['1/0','0/1','-1/2',True]:
            with self.assertRaises(ValueError):fractional_to_decimal(value)
        for value in [1e308,True,0,float('nan')]:
            q=f.quote();q['decimal_odds']=value
            with self.assertRaises(ValueError): self.s.import_quote('a',q)
    def test_latest_and_history_have_bounded_pages_and_filters(self):
        q=f.quote();q['observed_at']=at(-5);self.s.import_quote('a',q)
        q.update(id='new',observed_at=at(-1),decimal_odds=3);self.s.import_quote('a',q)
        self.assertEqual([r['id'] for r in self.s.odds_page('a')['items']],['new'])
        page=self.s.odds_page('a',latest=False,limit=1,event_id='e',sportsbook='BOOK')
        self.assertEqual(len(page['items']),1);self.assertEqual(page['next_offset'],1)
        self.assertEqual(self.s.odds_page('a',latest=False,limit=1,offset=1)['items'][0]['id'],'new')
        self.assertEqual(self.s.odds_page('b')['items'],[])
        with self.assertRaises(ValueError):self.s.odds_page('a',limit=501)
    def test_best_price_uses_other_books_outside_page(self):
        q=f.quote();q.update(provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        q.update(id='other',sportsbook='other',decimal_odds=3);self.s.import_quote('a',q)
        self.assertEqual(self.s.odds_page('a',limit=1)['items'][0]['best_observed_decimal'],3)
    def test_sql_query_indexes(self):
        with sqlite3.connect(self.s.path) as c:
            plan=' '.join(str(r) for r in c.execute('EXPLAIN QUERY PLAN SELECT * FROM audit WHERE user=? ORDER BY sequence',('a',)))
            self.assertIn('audit_user_sequence',plan)
            plan=' '.join(str(r) for r in c.execute('EXPLAIN QUERY PLAN SELECT * FROM quote_lookup WHERE user=? AND event_id=? ORDER BY seq LIMIT 100',('a','e')))
            self.assertIn('quote_event_history',plan)
    def test_multiprocess_limits_are_atomic(self):
        self.s.limits('a',dict(currency='USD',max_open=10,max_group=10,max_daily=100))
        context=multiprocessing.get_context('spawn');gate=context.Event();results=context.Queue()
        processes=[context.Process(target=enter_worker,args=(self.s.path,n,gate,results)) for n in range(3)]
        for process in processes:process.start()
        gate.set()
        for process in processes:process.join(20);self.assertEqual(process.exitcode,0)
        self.assertEqual(sum(results.get(timeout=2) for _ in processes),1)
    def test_multiprocess_snapshot_replay_is_atomic(self):
        context=multiprocessing.get_context('spawn');gate=context.Event();results=context.Queue();quote=f.quote()
        processes=[context.Process(target=quote_worker,args=(self.s.path,quote,n,gate,results)) for n in range(3)]
        for process in processes:process.start()
        gate.set()
        for process in processes:process.join(20);self.assertEqual(process.exitcode,0)
        self.assertEqual(sum(not results.get(timeout=2) for _ in processes),1)
        self.assertEqual(len(self.s.rows('a','quotes')),1)
    def test_read_page_uses_consistent_snapshot(self):
        with self.s.connect() as connection:
            connection.execute('BEGIN')
            self.s.local.connection=connection
            try:
                self.s.odds_page('a');self.assertIs(self.s.local.connection,connection)
            finally:self.s.local.connection=None
    def test_live_missing_or_wrong_identity_never_comparable(self):
        q=f.quote();q.update(scope='live',provenance='authorized_import',rules_verified=True,latency_seconds=1,state_id='s',state_period='1')
        state=dict(id='s',event_id='e',source_at=q['observed_at'],retrieved_at=now(),period='1',clock='1:00',score='0-0',connected=True,mode='polling',source_ref='fixture',sport='wrong',league=q['league'],start_at=q['start_at'],status='unknown')
        self.s.state('a',state);self.s.import_quote('a',q)
        self.assertIsNone(self.s.board('a')[0]['best_observed_decimal'])
    def test_provider_retry_dedupes_new_retrieval(self):
        p=snapshot();service=ProviderService(self.s,OddsAPI(key='fixture',transport=lambda *a:(p,{})))
        request=dict(provider='the_odds_api',action='odds',sport='sport_a',markets=['h2h'])
        self.assertEqual(service.action('a',request)['imported'],2)
        self.assertEqual(service.action('a',request)['duplicates'],2)
        self.assertEqual(len(self.s.rows('a','quotes')),2)
    def test_provider_timeout_malformed_and_recovery(self):
        def broken(*args):raise TimeoutError('secret')
        adapter=OddsAPI(key='secret',transport=broken)
        with self.assertRaises(ProviderError) as error:adapter.sports()
        self.assertNotIn('secret',str(error.exception));self.assertIsNotNone(adapter.retry_at)
        adapter.retry_at=datetime.now(timezone.utc)-timedelta(seconds=1);adapter.transport=lambda *a:([],{})
        self.assertEqual(adapter.sports(),[])
        service=ProviderService(self.s,adapter)
        with self.assertRaises(ValueError):service.action('a',dict(provider='the_odds_api',action='import_snapshot',payload={'bad':1},retrieved_at=now()))
        self.assertEqual(self.s.rows('a','quotes'),[])
        self.assertEqual(adapter.health()['last_result'],'schema_or_identity_rejected')
    def test_cli_compatible_and_refuses_overwrite(self):
        path=Path(self.tmp.name);history=path/'history.jsonl';history.write_text(json.dumps(prediction())+'\n')
        command=[sys.executable,'evaluate.py',str(history),'--train-end','2024-01-01T00:00:00Z','--validation-end','2024-12-01T00:00:00Z','--output',str(path/'out.json')]
        result=subprocess.run(command,capture_output=True);self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('dataset_sha256',json.loads((path/'out.json').read_text()))
        self.assertNotEqual(subprocess.run(command,capture_output=True).returncode,0)

class LaunchHTTP(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name+'/db')
        self.server=BoundedServer(('127.0.0.1',0),build_handler(self.store,{'a':'a'*32}))
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base='http://127.0.0.1:'+str(self.server.server_port)
    def tearDown(self):self.server.shutdown();self.server.server_close();self.thread.join();self.tmp.cleanup()
    def request(self,path,body=None,token='a'*32):
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        return urllib.request.urlopen(req)
    def test_latest_history_auth_and_query_injection(self):
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/odds/latest',token='bad')
        self.assertEqual(error.exception.code,401)
        for path in ['/odds/latest?limit=501','/odds/latest?limit=1&limit=2','/odds/history?event_id=x%27%20OR%201=1--&limit=1']:
            try:
                with self.request(path) as response:self.assertEqual(json.load(response)['items'],[])
            except urllib.error.HTTPError as error:self.assertEqual(error.code,400)
    def test_manual_import_cannot_self_verify(self):
        q=f.quote();q.update(provenance='authorized_import',rules_verified=True)
        with self.request('/api/quotes',q):pass
        with self.request('/odds/latest') as response:row=json.load(response)['items'][0]
        self.assertEqual(row['provenance'],'manual_unverified');self.assertIsNone(row['best_observed_decimal'])
    def test_database_failure_has_retryable_json_response(self):
        self.store.odds_page=lambda *a,**k:(_ for _ in ()).throw(sqlite3.OperationalError('private path'))
        with self.assertRaises(urllib.error.HTTPError) as error:self.request('/odds/latest')
        self.assertEqual(error.exception.code,503);self.assertNotIn('private path',error.exception.read().decode())
