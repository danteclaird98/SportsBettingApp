from http.server import ThreadingHTTPServer
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from next_app.server import Workspace, make_handler, system_readiness, wait_for_research
from edgeodds.ingestion import IngestionStore


class ReadinessTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.workspace=Workspace(self.root/'workspace.sqlite3')

    def test_storage_and_verified_model_are_both_required(self):
        def response(**changes):
            return BytesIO(json.dumps({'artifactVerified':True,'status':'HOLD','liveApproved':False,**changes}).encode())
        with patch('next_app.server.urlopen',return_value=response()):
            self.assertTrue(system_readiness(self.workspace)['ready'])
        with patch('next_app.server.urlopen',return_value=response(artifactVerified=False)):
            self.assertFalse(system_readiness(self.workspace)['ready'])
        with patch('next_app.server.urlopen',side_effect=URLError('offline')):
            result=system_readiness(self.workspace)
            self.assertFalse(result['ready']); self.assertTrue(result['workspaceStorageReadable'])
        with sqlite3.connect(self.workspace.path) as db: db.execute('DROP TABLE settings')
        with patch('next_app.server.urlopen',return_value=response()):
            self.assertFalse(system_readiness(self.workspace)['ready'])

    def test_failed_research_startup_does_not_claim_readiness(self):
        with self.assertRaisesRegex(RuntimeError,'exited'):
            wait_for_research(Mock(poll=Mock(return_value=1)),self.workspace,timeout=.01)
        with patch('next_app.server.system_readiness',return_value={'ready':False}):
            with self.assertRaisesRegex(RuntimeError,'failed'):
                wait_for_research(Mock(poll=Mock(return_value=None)),self.workspace,timeout=.01)

    def test_public_probe_is_minimal_and_diagnostics_require_login(self):
        server=ThreadingHTTPServer(('127.0.0.1',0),make_handler(self.workspace,
            IngestionStore(self.root/'odds.sqlite3'),'csrf',('owner','long-test-password-for-health'), 'secret-test-app-key'))
        thread=Thread(target=server.serve_forever,daemon=True); thread.start()
        base=f'http://127.0.0.1:{server.server_port}'
        try:
            for ready,status in ((True,200),(False,503)):
                with patch('next_app.server.system_readiness',return_value={'ready':ready,'privateDetail':'not-public'}):
                    try: response=urlopen(base+'/healthz',timeout=3)
                    except HTTPError as error: response=error
                    with response:
                        self.assertEqual(response.code,status)
                        self.assertEqual(json.load(response),{'status':'ok' if ready else 'unavailable'})
            with self.assertRaises(HTTPError) as error: urlopen(base+'/api/system/readiness',timeout=3)
            self.assertEqual(error.exception.code,401); error.exception.close()
            with patch('next_app.server.system_readiness',return_value={'ready':True}):
                with urlopen(Request(base+'/api/system/readiness',headers={'Authorization':'Bearer secret-test-app-key'}),timeout=3) as response:
                    result=json.load(response)
                    self.assertTrue(result['apiKeyConfigured']); self.assertTrue(result['browserAuthenticationConfigured'])
                    self.assertNotIn('secret-test-app-key',json.dumps(result))
        finally: server.shutdown(); server.server_close(); thread.join()
