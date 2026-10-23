"""Synthetic contracts only; these tests establish correctness, never a betting edge."""
import copy,json,threading,unittest,urllib.error,urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timedelta,timezone
import test_app as fixtures
from engine import Store,now
from providers import OddsAPI,ProviderError,ProviderService,normalize_odds
from core import net_win_per_unit
from evaluation import evaluate
from server import build_handler,ThreadingHTTPServer

def at(seconds): return (datetime.now(timezone.utc)+timedelta(seconds=seconds)).isoformat()
def snapshot(markets=None):
    return {'id':'event1','sport_key':'sport_a','sport_title':'Synthetic sport','commence_time':at(3600),'home_team':'A','away_team':'B','bookmakers':[{'key':'book','title':'Test book','last_update':now(),'markets':markets if markets is not None else [{'key':'h2h','last_update':at(-2),'outcomes':[{'name':'A','price':2},{'name':'B','price':2}]}]}]}
def prediction():
    return dict(id='p',event_id='e',sport='test',market='moneyline',season=2025,prediction_at='2025-01-03T00:00:00Z',inputs_available_at='2025-01-02T00:00:00Z',odds_observed_at='2025-01-02T23:59:59Z',result_available_at='2025-01-04T00:00:00Z',outcome=1,settlement_type='binary',probability='0.6',baseline_probability='0.5',decimal_odds='3')

class Expansion(unittest.TestCase):
    setUp=fixtures.Workflow.setUp
    tearDown=fixtures.Workflow.tearDown
    def test_atomic_import_rolls_back_quotes_and_audit(self):
        q=fixtures.quote();bad=copy.deepcopy(q);bad.update(id='bad',decimal_odds=1)
        with self.assertRaises(ValueError):self.s.bulk_quotes('a',[q,bad])
        self.assertEqual(self.s.rows('a','quotes'),[]);self.assertEqual(self.s.audit('a'),[])
    def test_cross_store_transaction_limits(self):
        stores=[Store(self.s.path) for _ in range(4)]
        self.s.limits('a',dict(currency='USD',max_open=10,max_group=10,max_daily=100))
        def enter(i):
            w=fixtures.wager();w.update(id=str(i),mode='actual')
            try:stores[i].wager('a',w);return 1
            except ValueError:return 0
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sum(pool.map(enter,range(4))),1)
    def test_same_book_alias_external_import_duplicate(self):
        w=fixtures.wager();w.update(sportsbook='Test Book',external_id='x');self.s.wager('a',w)
        w.update(id='w2',sportsbook='  TEST   book ')
        with self.assertRaisesRegex(ValueError,'Duplicate external'):self.s.wager('a',w)
    def test_props_different_metrics_never_compare(self):
        q=fixtures.quote();q.update(market='player_prop',participant_id='p',selection='Over',line='2.5',market_key='player_points',rules_verified=True,provenance='authorized_import')
        self.s.import_quote('a',q);q.update(id='q2',sportsbook='other',market_key='player_assists',decimal_odds=9);self.s.import_quote('a',q)
        self.assertEqual(self.s.board('a')[0]['best_observed_decimal'],2.1)
    def test_market_metric_required(self):
        q=fixtures.quote();q['market']='game_prop'
        with self.assertRaises(ValueError):self.s.import_quote('a',q)
        w=fixtures.wager();w['market']='player_prop'
        with self.assertRaises(ValueError):self.s.wager('a',w)
    def test_missing_line_and_participant_cannot_be_comparable(self):
        q=fixtures.quote();q.update(market='total')
        with self.assertRaisesRegex(ValueError,'Exact line'):self.s.import_quote('a',q)
        q.update(market='player_prop',market_key='player_points',line='2.5',selection='Over')
        with self.assertRaisesRegex(ValueError,'participant_id'):self.s.import_quote('a',q)
    def test_same_book_multivendor_not_independent(self):
        q=fixtures.quote();q.update(provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        q.update(id='q2',provider='other',sportsbook='  BOOK ');self.s.event_mapping('a',dict({k:q[k] for k in ['provider','provider_event_id','event_id','sport','league','start_at']},status='active',revision=1,reason='Fixture explicit shared event'));self.s.import_quote('a',q)
        self.assertEqual(self.s.board('a')[0]['independent_book_count'],1)
    def test_unknown_time_invalidates_old_fresh_snapshot(self):
        q=fixtures.quote();q.update(observed_at=at(-5),retrieved_at=at(-4),provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        q.update(id='q2',observed_at=None,retrieved_at=now());self.s.import_quote('a',q)
        self.assertTrue(all(r['best_observed_decimal'] is None for r in self.s.board('a')))
    def test_live_state_reference_expires_on_update(self):
        s=dict(id='s1',event_id='e',source_at=at(-2),retrieved_at=at(-1),period='1',clock='10:00',score='0-0',connected=True,mode='polling',source_ref='synthetic')
        q=fixtures.quote();q['start_at']=at(-3600);s.update(sport=q['sport'],league=q['league'],start_at=q['start_at'],status='live');self.s.state('a',s);q.update(scope='live',state_id='s1',state_period='1',observed_at=s['source_at'],latency_seconds=1,provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        self.assertEqual(self.s.board('a')[0]['best_observed_decimal'],2.1)
        s.update(id='s2',source_at=now(),retrieved_at=now(),score='1-0');self.s.state('a',s)
        self.assertIsNone(self.s.board('a')[0]['best_observed_decimal'])
    def test_manual_live_state_and_period_mismatch_rejected(self):
        s=dict(id='s',event_id='e',source_at=at(-1),retrieved_at=now(),period='2',clock='10:00',score='0-0',connected=True,mode='manual',source_ref='synthetic');self.s.state('a',s)
        q=fixtures.quote();q.update(scope='live',state_id='s',state_period='1',latency_seconds=1,provenance='authorized_import',rules_verified=True);self.s.import_quote('a',q)
        row=self.s.board('a')[0];self.assertIsNone(row['best_observed_decimal']);self.assertIn('Live state period mismatched',row['exclusion_reasons'])
    def test_shared_parlay_leg_exposure(self):
        self.s.limits('a',dict(currency='USD',max_open=100,max_group=15,max_daily=100));w=fixtures.wager();w.update(mode='actual',exposure_group='one');self.s.wager('a',w)
        w.update(id='combo',event_id='different',exposure_group='two',market='parlay',legs=[dict(event_id='e',market='total',selection='Over',line='1.5',period='full',rules='rule',status='open')])
        with self.assertRaisesRegex(ValueError,'max_group'):self.s.wager('a',w)
    def test_timezone_limit_and_validation(self):
        with self.assertRaises(ValueError):self.s.limits('a',dict(currency='USD',max_open=100,max_group=100,max_daily=10,timezone='Invalid/Test'))
        self.s.limits('a',dict(currency='USD',max_open=100,max_group=100,max_daily=10,timezone='America/Los_Angeles'));self.assertEqual(self.s.rows('a','limits')[0]['timezone'],'America/Los_Angeles')
    def test_freshness_settings_isolated_and_applied(self):
        q=fixtures.quote();q.update(observed_at=at(-30));self.s.import_quote('a',q);self.assertTrue(self.s.board('a')[0]['price_fresh'])
        self.s.configure('a',{'pregame_quote_age_seconds':10});self.assertFalse(self.s.board('a')[0]['price_fresh']);self.assertEqual(self.s.settings('b')['pregame_quote_age_seconds'],300)
        for value in [-1,True,float('nan'),90000]:
            with self.assertRaises(ValueError):self.s.configure('a',{'live_quote_age_seconds':value})
    def test_simultaneous_settlements_do_not_create_false_drawdown(self):
        w=fixtures.wager();self.s.wager('a',w);w.update(id='w2');self.s.wager('a',w)
        t=now();s=fixtures.settlement();s.update(fees=0,settled_at=t);self.s.settle('a',s);s.update(id='w2',status='loss',payout=0);self.s.settle('a',s)
        self.assertEqual(float(self.s.report('a')[0]['drawdown']),0)

class ProviderTests(unittest.TestCase):
    setUp=fixtures.Workflow.setUp
    tearDown=fixtures.Workflow.tearDown
    def test_child_timestamp_and_unknown_availability(self):
        p=snapshot();p['bookmakers'][0]['markets'][0].pop('last_update');q=normalize_odds(p,now())['quotes'][0]
        self.assertIsNone(q['observed_at']);self.assertEqual(q['status'],'unknown');self.assertFalse(q['rules_verified']);self.assertEqual(q['availability'],'unknown')
    def test_complete_three_way_benchmark(self):
        p=snapshot();p['bookmakers'][0]['markets'][0]['outcomes'].append(dict(name='Draw',price=3))
        rows=normalize_odds(p,now())['quotes'];self.assertEqual(rows[0]['market'],'moneyline_3way');self.assertAlmostEqual(sum(q['benchmark_probability'] for q in rows),1)
    def test_explicit_three_way_missing_draw_not_normalized(self):
        p=snapshot();p['bookmakers'][0]['markets'][0]['key']='h2h_3_way'
        rows=normalize_odds(p,now())['quotes'];self.assertEqual(rows[0]['market'],'moneyline_3way');self.assertTrue(all(r['benchmark_probability'] is None for r in rows))
    def test_tennis_set_and_period_total_contracts(self):
        p=snapshot([dict(key='totals_s1',last_update=at(-2),outcomes=[dict(name='Over',price=2,point=9.5),dict(name='Under',price=2,point=9.5)])]);q=normalize_odds(p,now())['quotes'][0];self.assertEqual(q['market'],'period');self.assertEqual(q['period'],'provider_market:totals_s1');self.assertEqual(q['benchmark_probability'],.5)
    def test_incomplete_and_futures_have_no_benchmark(self):
        for market,outcomes in [('h2h',[dict(name='A',price=2)]),('outrights',[dict(name='A',price=2),dict(name='B',price=2)])]:
            p=snapshot([dict(key=market,last_update=at(-2),outcomes=outcomes)])
            self.assertTrue(all(q['benchmark_probability'] is None for q in normalize_odds(p,now())['quotes']))
    def test_complementary_alternate_lines_only(self):
        p=snapshot([dict(key='alternate_spreads',last_update=at(-2),outcomes=[dict(name='A',point=1.5,price=2),dict(name='B',point=-2.5,price=2)])])
        self.assertTrue(all(q['benchmark_probability'] is None for q in normalize_odds(p,now())['quotes']))
    def test_props_retain_metrics_participants_and_lines(self):
        p=snapshot([dict(key='player_points',last_update=at(-2),outcomes=[dict(name='Over',description='Player A',point=20.5,price=2),dict(name='Under',description='Player A',point=20.5,price=2)])]);q=normalize_odds(p,now())['quotes'][0]
        self.assertEqual((q['market_key'],q['participant_id'],q['line']),('player_points','Player A','20.5'));self.assertEqual(q['benchmark_probability'],.5)
    def test_snapshot_duplicate_and_coverage_unverified(self):
        service=ProviderService(self.s);d=dict(provider='the_odds_api',action='import_snapshot',payload=snapshot(),retrieved_at=now());self.assertEqual(service.action('a',d)['imported'],2);self.assertEqual(service.action('a',d)['duplicates'],2)
        observed=self.s.rows('a','provider_coverage');self.assertFalse(observed[0]['source_observed']);self.assertFalse(observed[0]['live_research_verified']);self.assertEqual(service.catalog('b'),[])
    def test_schema_failure_atomic(self):
        p=snapshot();p['bookmakers'][0]['markets'][0]['outcomes'][1]['price']=float('nan')
        with self.assertRaises(ValueError):ProviderService(self.s).action('a',dict(provider='the_odds_api',action='import_snapshot',payload=p,retrieved_at=now()))
        self.assertEqual(self.s.rows('a','quotes'),[])
    def test_provider_response_identity_checked(self):
        a=OddsAPI(key='secret',transport=lambda *_:(snapshot(),{}))
        with self.assertRaises(ProviderError):a.odds('sport_b',['h2h'])
        with self.assertRaises(ProviderError):a.odds('sport_a',['h2h'],event='different')
        with self.assertRaises(ValueError):a.odds('sport_a',['player_points'])
    def test_rate_limit_redaction_cooldown_recovery(self):
        calls=[]
        def transport(path,params):
            calls.append(path)
            if len(calls)==1:raise urllib.error.HTTPError('https://host?apiKey=secret',429,'secret',{},None)
            return [],{'X-Requests-Remaining':'20'}
        a=OddsAPI(key='secret',transport=transport)
        with self.assertRaises(ProviderError) as error:a.sports()
        self.assertNotIn('secret',str(error.exception));self.assertNotIn('secret',json.dumps(a.health()))
        with self.assertRaisesRegex(ProviderError,'cooldown'):a.sports()
        self.assertEqual(len(calls),1);a.retry_at=datetime.now(timezone.utc)-timedelta(seconds=1);self.assertEqual(a.sports(),[]);self.assertEqual(a.health()['last_result'],'response_received')
    def test_resumable_scan_reaches_all_sports_and_extra_markets(self):
        calls=[]
        stable=snapshot()
        def transport(path,params):
            calls.append((path,params))
            if path=='/v4/sports':return [dict(key='sport_'+x,title=x,group='synthetic',active=True,has_outrights=False) for x in ['a','b']],{}
            sport=path.split('/')[3]
            if path.endswith('/events'):return [dict(id='event1',sport_key=sport,commence_time=at(3600))],{}
            p=copy.deepcopy(stable);p['sport_key']=sport
            if path.endswith('/markets'):p['bookmakers'][0]['markets']=[dict(key='player_points'),dict(key='totals_q1')];return p,{}
            if 'event1' in path:p['bookmakers'][0]['markets']=[dict(key='player_points',last_update=at(-2),outcomes=[dict(name='Over',description='Player',point=3.5,price=2),dict(name='Under',description='Player',point=3.5,price=2)])]
            return p if 'event1' in path else [p],{}
        service=ProviderService(self.s,OddsAPI(key='test',transport=transport));d=dict(provider='the_odds_api',action='scan_all',max_requests=3)
        result=service.action('a',d);self.assertLessEqual(result['provider_requests'],3);self.assertFalse(result['cycle_complete'])
        for _ in range(4):
            result=service.action('a',d)
            if result['cycle_complete']:break
        self.assertTrue(result['cycle_complete']);self.assertEqual({q['league'] for q in self.s.rows('a','quotes')},{'sport_a','sport_b'});self.assertTrue(any(q['market_key']=='player_points' for q in self.s.rows('a','quotes')))
        self.assertEqual(len([c for c in calls if c[0]=='/v4/sports']),1)

class HistoricalTests(unittest.TestCase):
    def audit(self,r):return evaluate([r],'2024-01-01T00:00:00Z','2024-12-01T00:00:00Z')
    def test_numeric_strings_normalized(self):self.assertAlmostEqual(self.audit(prediction())['test']['probability']['brier'],.16)
    def test_boolean_and_selection_strings_rejected(self):
        for key,value in [('outcome',True),('selected','false'),('executable',1)]:
            r=prediction();r[key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):self.audit(r)
    def test_execution_prices_not_prediction_prices(self):
        r=prediction();r.update(selected=True,executable=True,execution_at='2025-01-03T00:00:02Z',price_available_until='2025-01-03T00:00:05Z',execution_odds_observed_at='2025-01-03T00:00:01Z',execution_decimal_odds='2',stake='10',fees='1')
        self.assertEqual(self.audit(r)['test']['profit'],9)
        r['execution_at']='2025-01-05T00:00:00Z'
        with self.assertRaises(ValueError):self.audit(r)
    def test_labels_unavailable_at_fit_cutoff_rejected(self):
        r=prediction()
        with self.assertRaisesRegex(ValueError,'Label unavailable'):evaluate([r],'2025-01-03T01:00:00Z','2025-02-01T00:00:00Z')
    def test_future_fitted_artifact_rejected(self):
        r=prediction();r['calibration_fitted_at']='2025-01-05T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'Future fitted'):self.audit(r)
    def test_commission_negative_net_dead_heat(self):
        self.assertAlmostEqual(net_win_per_unit(1.8,dead_heat_fraction=.5,commission_on_profit=.05),-.1)
        self.assertAlmostEqual(net_win_per_unit(1.8,dead_heat_fraction=.5,commission_on_profit=.05,commission_basis='winning_fraction'),-.12)
        self.assertAlmostEqual(net_win_per_unit(3,dead_heat_fraction=.5,commission_on_profit=.05),.475)

class HttpSecurity(unittest.TestCase):
    setUp=fixtures.Workflow.setUp
    tearDown=fixtures.Workflow.tearDown
    def test_configuration_rejects_shared_short_or_empty_users(self):
        for cfg in [{},{'':'a'*32},{'a':'short'},{'a':'x'*32,'b':'x'*32}]:
            with self.assertRaises(ValueError):build_handler(self.s,cfg)
    def test_origin_host_json_and_provider_auth(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),build_handler(self.s,{'a':'a'*32}));t=threading.Thread(target=server.serve_forever,daemon=True);t.start();base='http://127.0.0.1:'+str(server.server_port)
        def status(path,raw=None,headers=None):
            h={'Authorization':'Bearer '+'a'*32,'Content-Type':'application/json'};h.update(headers or {})
            try:
                with urllib.request.urlopen(urllib.request.Request(base+path,data=raw,headers=h)) as r:return r.status
            except urllib.error.HTTPError as e:return e.code
        try:
            self.assertEqual(status('/api/health',headers={'Origin':'https://evil.test'}),403)
            self.assertEqual(status('/api/health',headers={'Host':'evil.test'}),403)
            self.assertEqual(status('/api/providers',headers={'Authorization':'bad'}),401)
            self.assertEqual(status('/api/wagers',b'{"stake":NaN}'),400)
            self.assertEqual(status('/api/wagers',b'{"id":"x","id":"y"}'),400)
            self.assertEqual(status('/api/wagers',b'{}',{'Content-Type':'text/plain'}),400)
            self.assertEqual(status('/api/quote_batch',b'{"quotes":[]}'),200)
        finally:server.shutdown();server.server_close();t.join()
