import copy
import hashlib
from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from next_app.server import Workspace, make_handler
from edgeodds.ingestion import IngestionStore


INPUT={'request':{'playerId':'p1','gameId':'g1'},'history':[]}
SCORE={'status':'HOLD','probability':.25,'estimateAvailable':True,'modelVersion':'receiving60-logistic-v1',
       'canonicalArtifactSha256':'a'*64,'liveApproved':False,'productionEnabled':False,
       'executionEnabled':False,'verifiedPositiveEv':False}


class ReceiptStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.path=Path(self.tmp.name)/'workspace.sqlite3'
        self.workspace=Workspace(self.path)

    def test_immutable_deduplicated_records_survive_reopen(self):
        record,created=self.workspace.save_receiving60(INPUT,SCORE,'synthetic')
        self.assertTrue(created)
        duplicate,created=self.workspace.save_receiving60(INPUT,SCORE,'synthetic')
        self.assertFalse(created); self.assertEqual(record,duplicate)
        self.assertEqual(Workspace(self.path).receiving60_record(record['id']),record)
        self.assertEqual(self.workspace.state()['audit_count'],1)
        self.assertEqual(self.workspace.state()['wagers'],[])
        content={key:value for key,value in record.items() if key not in ('id','recordedAt','contentSha256')}
        digest=hashlib.sha256(json.dumps(content,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
        self.assertEqual(record['contentSha256'],digest)
        self.assertEqual(record['inputModeProvenance'],'CLIENT_DECLARED')
        with self.workspace.connect() as db:
            for statement in ('UPDATE receiving60_receipts SET body=\'{}\'', 'DELETE FROM receiving60_receipts'):
                with self.assertRaises(sqlite3.IntegrityError): db.execute(statement)

    def test_cursor_pagination_has_no_gaps_and_excludes_large_inputs(self):
        for i in range(52):
            payload=copy.deepcopy(INPUT); payload['request']['gameId']=f'g{i}'
            self.workspace.save_receiving60(payload,SCORE,'supplied')
        first=self.workspace.receiving60_records()
        self.assertEqual(len(first['receipts']),50)
        second=self.workspace.receiving60_records(first['nextCursor'])
        self.assertEqual(len(second['receipts']),2); self.assertIsNone(second['nextCursor'])
        ids=[row['id'] for row in first['receipts']+second['receipts']]
        self.assertEqual(ids,list(range(52,0,-1)))
        self.assertNotIn('request',first['receipts'][0])

    def test_audit_failure_rolls_back_the_record(self):
        with self.workspace.connect() as db:
            db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit BEGIN SELECT RAISE(ABORT,'test audit failure'); END")
        with self.assertRaises(sqlite3.IntegrityError):
            self.workspace.save_receiving60(INPUT,SCORE,'supplied')
        self.assertEqual(self.workspace.receiving60_records()['receipts'],[])


class ReceiptHttpTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.workspace=Workspace(Path(self.tmp.name)/'workspace.sqlite3')
        self.server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.workspace,
            IngestionStore(Path(self.tmp.name)/'odds.sqlite3'),'csrf',('owner','password-longer-than-24-characters'),'app-key-longer-than-32-characters'))
        self.thread=Thread(target=self.server.serve_forever,daemon=True); self.thread.start()
        self.addCleanup(self.stop)
        self.base=f'http://127.0.0.1:{self.server.server_port}'
        self.body={'inputMode':'synthetic','input':INPUT,'expectedArtifactSha256':'a'*64}

    def stop(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join()

    def request(self,path='/api/receiving60/receipts',body=None,headers=None):
        headers=headers if headers is not None else {'Authorization':'Bearer app-key-longer-than-32-characters'}
        data=json.dumps(body).encode() if body is not None else None
        try:
            with urlopen(Request(self.base+path,headers=headers,data=data),timeout=3) as response:
                return response.status,json.load(response)
        except HTTPError as error:
            with error:
                return error.code,json.loads(error.read() or b'{}')

    @staticmethod
    def upstream(score=SCORE):
        response=BytesIO(json.dumps(score).encode()); response.status=200
        return response

    def test_server_scores_before_saving_then_lists_and_retrieves(self):
        with patch('next_app.server.urlopen',side_effect=lambda *args,**kwargs:self.upstream()) as scorer:
            status,record=self.request(body=self.body)
            self.assertEqual(status,201); self.assertEqual(record['scoreReceipt'],SCORE)
            forwarded=scorer.call_args.args[0]
            self.assertEqual(json.loads(forwarded.data),INPUT)
            self.assertIsNone(forwarded.get_header('Authorization'))
            status,duplicate=self.request(body=self.body)
            self.assertEqual(status,200); self.assertEqual(record['id'],duplicate['id'])
        self.assertEqual(self.request()[1]['receipts'][0]['id'],record['id'])
        self.assertEqual(self.request('/api/receiving60/receipts/'+str(record['id']))[1],record)
        self.assertEqual(self.request('/api/receiving60/receipts/999')[0],404)
        for path in ('/api/receiving60/receipts/not-an-id','/api/receiving60/receipts?before=-1',
                     '/api/receiving60/receipts?before=9223372036854775808'):
            self.assertEqual(self.request(path)[0],400)

    def test_forged_scores_clock_failures_and_artifact_changes_are_not_saved(self):
        with patch('next_app.server.urlopen') as scorer:
            self.assertEqual(self.request(body={**self.body,'scoreReceipt':SCORE})[0],400)
            scorer.assert_not_called()
            scorer.return_value=self.upstream()
            self.assertEqual(self.request(body={**self.body,'expectedArtifactSha256':'b'*64})[0],409)
            scorer.return_value=self.upstream({**SCORE,'liveApproved':True})
            self.assertEqual(self.request(body=self.body)[0],503)
            scorer.side_effect=HTTPError('http://localhost',422,'Unprocessable',{},BytesIO(b'{"reason":"INVALID_DECISION_CLOCK"}'))
            status,response=self.request(body=self.body)
            self.assertEqual(status,422); self.assertEqual(response['reason'],'INVALID_DECISION_CLOCK')
        self.assertEqual(self.workspace.receiving60_records()['receipts'],[])

    def test_authentication_and_cross_site_checks_precede_scoring(self):
        with patch('next_app.server.urlopen') as scorer:
            self.assertEqual(self.request(headers={})[0],401)
            self.assertEqual(self.request(body=self.body,headers={})[0],401)
            self.assertEqual(self.request(body=self.body,headers={'Authorization':'Bearer app-key-longer-than-32-characters','Sec-Fetch-Site':'cross-site'})[0],403)
            scorer.assert_not_called()
