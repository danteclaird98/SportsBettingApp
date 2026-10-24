import base64
from http.server import ThreadingHTTPServer
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from next_app.server import Workspace, access_credentials, make_handler
from edgeodds.ingestion import IngestionStore


class AccessTests(unittest.TestCase):
    def test_external_binding_fails_closed(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(access_credentials('127.0.0.1'))
            with self.assertRaises(ValueError):
                access_credentials('0.0.0.0')
        for values in ({'WORKSPACE_USER': 'owner'},
                       {'WORKSPACE_USER': 'owner', 'WORKSPACE_PASSWORD': 'short'}):
            with patch.dict(os.environ, values, clear=True):
                with self.assertRaises(ValueError):
                    access_credentials('0.0.0.0')

    def test_all_interfaces_require_authentication(self):
        credentials = ('owner', 'test-password-at-least-24-characters')
        with TemporaryDirectory() as directory:
            root = Path(directory)
            server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(
                Workspace(root/'workspace.db'), IngestionStore(root/'odds.db'), 'csrf', credentials,
                'test-app-key-that-is-at-least-32-characters'))
            thread = Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f'http://127.0.0.1:{server.server_port}'
                for route in ('/', '/advanced/', '/api/bootstrap', '/api/export', '/research-api/status'):
                    for authorization in ('', 'Basic !!!', 'Basic '+base64.b64encode(b'owner:wrong').decode()):
                        with self.subTest(route=route, authorization=authorization):
                            with self.assertRaises(HTTPError) as error:
                                urlopen(Request(base+route, headers={'Authorization': authorization}), timeout=3)
                            self.assertEqual(error.exception.code, 401)
                            self.assertIn('Basic', error.exception.headers['WWW-Authenticate'])
                            error.exception.close()
                authorization = 'Basic '+base64.b64encode(':'.join(credentials).encode()).decode()
                with urlopen(Request(base+'/api/bootstrap', headers={'Authorization': authorization}), timeout=3) as response:
                    self.assertEqual(response.status, 200)
                bearer = {'Authorization': 'Bearer test-app-key-that-is-at-least-32-characters'}
                with urlopen(Request(base+'/api/models', headers=bearer), timeout=3) as response:
                    self.assertEqual(response.status, 200)
                    self.assertNotIn(b'test-app-key', response.read())
                with urlopen(Request(base+'/api/settings', headers=bearer,
                    data=b'{"bankroll":"1000","daily_limit":"10","exposure_limit":"20"}'), timeout=3) as response:
                    self.assertEqual(response.status, 200)
                for route in ('/', '/advanced/', '/api/models'):
                    headers = bearer if route != '/api/models' else {'Authorization': 'Bearer wrong'}
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base+route, headers=headers), timeout=3)
                    self.assertEqual(error.exception.code, 401)
                    error.exception.close()
                for headers, expected in (({'X-Workspace-Token': 'csrf'}, 401),
                    ({'Authorization': authorization, 'X-Workspace-Token': 'csrf', 'Sec-Fetch-Site': 'cross-site'}, 403)):
                    with self.assertRaises(HTTPError) as error:
                        urlopen(Request(base+'/research-api/status', data=b'{}', headers=headers), timeout=3)
                    self.assertEqual(error.exception.code, expected)
                    error.exception.close()
            finally:
                server.shutdown()
                server.server_close()
                thread.join()
