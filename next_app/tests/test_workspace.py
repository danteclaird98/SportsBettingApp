import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.server import ThreadingHTTPServer

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from next_app.server import Workspace, make_handler, demo_board, live_board
from edgeodds.ingestion import IngestionStore
from edgeodds.tests.test_ingestion import binding, raw, NOW

class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.workspace=Workspace(Path(self.tmp.name)/'workspace.sqlite3')
    def wager(self,**overrides):
        return {'mode':'actual','book':'Example','external_id':'ticket-one','selection':'Team A moneyline','odds':2.0,'stake':'10',**overrides}
    def test_persistence_and_confirmed_accounting(self):
        self.workspace.mutate('/api/wagers',self.wager())
        with self.assertRaises(ValueError): self.workspace.mutate('/api/settle',{'id':1,'status':'win','payout':'20'})
        state=self.workspace.mutate('/api/settle',{'id':1,'status':'win','payout':'20','confirmed':True})
        self.assertEqual(state['wagers'][0]['payout']-state['wagers'][0]['stake'],1000)
        self.assertEqual(Workspace(self.workspace.path).state(),state)
        with self.assertRaises(ValueError): self.workspace.mutate('/api/settle',{'id':1,'status':'loss','payout':'0','confirmed':True})
    def test_duplicate_normalized_ticket(self):
        self.workspace.mutate('/api/wagers',self.wager(book='Example'))
        with self.assertRaises(sqlite3.IntegrityError): self.workspace.mutate('/api/wagers',self.wager(book=' example '))
        self.assertEqual(self.workspace.state()['audit_count'],1)
    def test_limits_modes_and_utc_daily_stakes(self):
        self.workspace.mutate('/api/settings',{'bankroll':'1000','daily_limit':'15','exposure_limit':'20'})
        self.workspace.mutate('/api/wagers',self.wager())
        self.workspace.mutate('/api/wagers',self.wager(mode='paper'))
        with self.assertRaises(ValueError): self.workspace.mutate('/api/wagers',self.wager(stake='6',external_id='two'))
        self.workspace.mutate('/api/settle',{'id':1,'status':'push','payout':'10','confirmed':True})
        with self.assertRaises(ValueError): self.workspace.mutate('/api/wagers',self.wager(stake='6',external_id='two'))
    def test_malformed_financial_values_and_settlements(self):
        for value in ['NaN','Infinity','-1','0','1.001',True]:
            with self.subTest(value=value), self.assertRaises(ValueError): self.workspace.mutate('/api/wagers',self.wager(stake=value))
        for odds in [float('nan'),float('inf'),True,1,-2,'2']:
            with self.subTest(odds=odds), self.assertRaises(ValueError): self.workspace.mutate('/api/wagers',self.wager(odds=odds))
        self.workspace.mutate('/api/wagers',self.wager())
        for status,payout in [('loss','1'),('push','0'),('void','11'),('win','10')]:
            with self.assertRaises(ValueError): self.workspace.mutate('/api/settle',{'id':1,'status':status,'payout':payout,'confirmed':True})
    def test_immutable_audit(self):
        self.workspace.mutate('/api/wagers',self.wager())
        with self.workspace.connect() as db:
            with self.assertRaises(sqlite3.IntegrityError): db.execute('DELETE FROM audit')
    def test_network_and_fixture_separation_and_contract(self):
        store=IngestionStore(Path(self.tmp.name)/'odds.sqlite3')
        store.ingest(raw(),binding(),retrieved_at=NOW,mode='fixture')
        self.assertEqual(live_board(store)['events'],[])
        store.ingest(raw(),binding(),retrieved_at=NOW,mode='network')
        board=live_board(store)
        self.assertFalse(board['live_verified'])
        self.assertEqual(len(board['events'][0]['quotes']),6)
        for q in board['events'][0]['quotes']:
            self.assertIsNone(q['model_probability']); self.assertIsNone(q['ev_per_unit'])
            self.assertIn('SOURCE_QUOTE_TIMESTAMP_UNAVAILABLE',q['reasons'])
        for event in demo_board()['events']:
            self.assertIsNone(event['starts_at'])
            self.assertTrue(all(q['status']=='SYNTHETIC' for q in event['quotes']))
    def test_http_boundary(self):
        store=IngestionStore(Path(self.tmp.name)/'odds.sqlite3')
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.workspace,store,'test-token'))
        thread=Thread(target=server.serve_forever,daemon=True); thread.start()
        self.addCleanup(server.server_close); self.addCleanup(server.shutdown)
        base=f'http://127.0.0.1:{server.server_port}'
        def request(path,body=None,token=None):
            headers={'X-Workspace-Token':token} if token else {}
            return urlopen(Request(base+path,data=json.dumps(body).encode() if body is not None else None,headers=headers))
        with request('/api/bootstrap') as response: self.assertEqual(json.load(response)['csrf'],'test-token')
        with self.assertRaises(HTTPError) as error: request('/api/wagers',self.wager())
        self.assertEqual(error.exception.code,403)
        with request('/api/wagers',self.wager(),token='test-token') as response: self.assertEqual(len(json.load(response)['wagers']),1)
        with self.assertRaises(HTTPError) as error: request('/api/board?mode=invalid')
        self.assertEqual(error.exception.code,400)
        with self.assertRaises(HTTPError) as error: request('/server.py')
        self.assertEqual(error.exception.code,404)

if __name__=='__main__': unittest.main()
