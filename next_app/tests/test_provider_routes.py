"""Exercise manual imports through real HTTP authentication and CSRF boundaries."""
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

class ProviderRouteTests(unittest.TestCase):
    def test_auth_csrf_replay_and_board_separation(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            workspace=Workspace(root/'workspace.sqlite3')
            handler=make_handler(workspace,IngestionStore(root/'odds.sqlite3'),'csrf',('owner','test-password-at-least-24-characters'))
            server=ThreadingHTTPServer(('127.0.0.1',0),handler)
            Thread(target=server.serve_forever,daemon=True).start()
            auth='Basic '+base64.b64encode(b'owner:test-password-at-least-24-characters').decode()
            def call(path='/api/provider-imports',data=None,headers=None):
                request=Request(f'http://127.0.0.1:{server.server_port}'+path,data=None if data is None else json.dumps(data).encode(),headers=headers or {})
                try: response=urlopen(request,timeout=3)
                except HTTPError as error: response=error
                with response:
                    raw=response.read()
                    return response.code,json.loads(raw) if raw else {}
            try:
                self.assertEqual(call()[0],401)
                self.assertEqual(call(data={})[0],401)
                self.assertEqual(call(data={},headers={'Authorization':auth})[0],403)
                headers={'Authorization':auth,'X-Workspace-Token':'csrf'}
                self.assertEqual(call(data={},headers={**headers,'Sec-Fetch-Site':'cross-site'})[0],403)
                payload={'request_id':'route-test-001','format':'normalized','payload':[{'provider':'synthetic','event_id':'synthetic:123','event':'Away @ Home','league':'NFL','bookmaker':'example','selection':'Home','period':'full_game','rules':'unknown','market':'moneyline','decimal_price':2.0,'starts_at':'2026-11-01T20:00:00Z','source_market_id':'native-id','status':'open'}]}
                status,first=call(data=payload,headers=headers)
                self.assertEqual(status,200)
                self.assertEqual(call(data=payload,headers=headers)[1],first)
                summary=call(headers=headers)[1]
                self.assertEqual(summary['observation_count'],1)
                self.assertEqual(summary['verification'],'UNVERIFIED')
                self.assertFalse(summary['execution_enabled'])
                self.assertIsNone(summary['observations'][0]['updated_at'])
                self.assertEqual(call('/api/board?mode=network',headers=headers)[1]['events'],[])
                self.assertEqual(workspace.state()['wagers'],[])
                payload['payload'][0]['decimal_price']=3
                self.assertEqual(call(data=payload,headers=headers)[0],400)
            finally:
                server.shutdown();server.server_close()
