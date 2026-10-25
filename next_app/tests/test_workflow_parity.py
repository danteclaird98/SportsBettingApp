"""Synthetic workflow contracts; source-level UI checks are not browser verification."""
import base64
import json
from http.server import ThreadingHTTPServer
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from next_app.server import Workspace, make_handler
from edgeodds.ingestion import IngestionStore

ROOT=Path(__file__).resolve().parents[1]

class WorkflowParityTests(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name)
        self.workspace=Workspace(root/'workspace.sqlite3')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.workspace,IngestionStore(root/'odds.sqlite3'),'csrf',('owner','synthetic-test-password-at-least-24')))
        Thread(target=self.server.serve_forever,daemon=True).start()
        self.addCleanup(self.server.server_close);self.addCleanup(self.server.shutdown)
        self.headers={'Authorization':'Basic '+base64.b64encode(b'owner:synthetic-test-password-at-least-24').decode(),'X-Workspace-Token':'csrf'}
    def call(self,path,data=None):
        req=Request(f'http://127.0.0.1:{self.server.server_port}'+path,headers=self.headers,data=None if data is None else json.dumps(data).encode())
        try: response=urlopen(req,timeout=3)
        except HTTPError as error: response=error
        with response:
            raw=response.read()
            return response.code,json.loads(raw) if raw else None
    def wager(self,mode='paper',ticket='ticket-qa'):
        return dict(mode=mode,book='Synthetic QA',external_id=ticket,selection='Synthetic exact market',odds=2,stake='10')
    def test_actual_requires_ticket_and_paper_never_becomes_actual(self):
        self.assertEqual(self.call('/api/wagers',self.wager('actual',''))[0],400)
        self.assertEqual(self.call('/api/wagers',self.wager())[0],200)
        status,state=self.call('/api/bootstrap')
        self.assertEqual(status,200)
        self.assertEqual([w['mode'] for w in state['state']['wagers']],['paper'])
        self.assertEqual(state['state']['audit_count'],1)
    def test_settlement_confirmation_duplicate_and_financial_mode_separation(self):
        self.assertEqual(self.call('/api/wagers',self.wager('actual'))[0],200)
        self.assertEqual(self.call('/api/wagers',self.wager('actual'))[0],409)
        self.assertEqual(self.call('/api/wagers',self.wager())[0],200)
        self.assertEqual(self.call('/api/settle',dict(id=1,status='win',payout='20'))[0],400)
        code,state=self.call('/api/settle',dict(id=1,status='win',payout='20',confirmed=True))
        self.assertEqual(code,200)
        actual=next(row for row in state['wagers'] if row['mode']=='actual')
        paper=next(row for row in state['wagers'] if row['mode']=='paper')
        self.assertEqual(actual['payout']-actual['stake'],1000)
        self.assertEqual(paper['status'],'open')
    def test_demo_and_provider_observations_do_not_create_wagers_or_network_prices(self):
        self.assertTrue(self.call('/api/board?mode=demo')[1]['events'])
        row=dict(provider='synthetic',event_id='synthetic:1',event='Away @ Home',league='NFL',bookmaker='qa',selection='Home',period='full_game',rules='unknown',market='moneyline',decimal_price=2,starts_at='2026-11-01T20:00:00Z')
        code,receipt=self.call('/api/provider-imports',dict(request_id='parity-test-import',format='normalized',payload=[row]))
        self.assertEqual(code,200);self.assertFalse(receipt['execution_enabled'])
        self.assertEqual(self.call('/api/board?mode=network')[1]['events'],[])
        self.assertEqual(self.workspace.state()['wagers'],[])
    def test_unsupported_financial_actions_reject_without_side_effects(self):
        for path in ('/api/place-bet','/api/cashout','/api/transfer','/api/ticket-screenshot'):
            with self.subTest(path=path):self.assertEqual(self.call(path,{})[0],400)
        self.assertEqual(self.workspace.state()['audit_count'],0)
    def test_separate_ledger_scope_is_visible_in_both_user_interfaces(self):
        root=(ROOT/'web/app.js').read_text()
        advanced=(ROOT/'research_runtime/src/WagerTracker.tsx').read_text()
        self.assertIn('Workspace records only',root)
        self.assertIn('research ledger has separate records and totals',root)
        self.assertIn('Research records only',advanced)
        self.assertIn('workspace wager ledger has separate records and totals',advanced)
        self.assertIn('placed-order drawdown',advanced)
    def test_research_save_requires_confirmation_before_clearing_draft(self):
        source=(ROOT/'research_runtime/src/WagerTracker.tsx').read_text()
        self.assertIn('if (!(await updateWagers([created, ...wagers]))) return;',source)
        self.assertIn('Your draft and request are retained. Reconcile pending save before editing.',source)
        self.assertIn('persistPendingLedgerWrite(write)',source)
        self.assertIn('savingRef.current = true',source)
        self.assertNotIn('No changes were applied',source)

if __name__=='__main__':unittest.main()
