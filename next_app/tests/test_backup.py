import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from next_app.backup import create_backup, restore_backup, verify_backup
from next_app.server import Workspace


class BackupTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name); self.data=self.root/'data'; self.backup=self.root/'snapshot'
        self.workspace=Workspace(self.data/'workspace.sqlite3')

    def test_backup_includes_uncheckpointed_wal_and_restores_receipts(self):
        connection=sqlite3.connect(self.data/'workspace.sqlite3')
        self.addCleanup(connection.close)
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute("INSERT INTO audit(at,action,payload) VALUES('now','wal-test','{}')"); connection.commit()
        self.workspace.save_receiving60({'request':{'playerId':'p','gameId':'g'}},
            {'probability':.5,'status':'HOLD','modelVersion':'test'},'synthetic')
        manifest=create_backup(self.data,self.backup)
        self.assertEqual(manifest['missing'],['research.sqlite3','edgeodds.sqlite3'])
        self.assertEqual(verify_backup(self.backup),manifest)
        target=self.root/'restored'
        restore_backup(self.backup,target)
        restored=Workspace(target/'workspace.sqlite3')
        self.assertEqual(restored.state()['audit_count'],2)
        self.assertEqual(restored.receiving60_record(1),self.workspace.receiving60_record(1))
        self.assertEqual((target/'workspace.sqlite3').stat().st_mode & 0o777,0o600)
        # Subsequent source writes cannot change a completed snapshot.
        connection.execute("INSERT INTO audit(at,action,payload) VALUES('later','after-snapshot','{}')"); connection.commit()
        self.assertEqual(restored.state()['audit_count'],2)
        self.assertEqual(self.workspace.state()['audit_count'],3)

    def test_restore_rejects_tampering_and_never_overwrites(self):
        create_backup(self.data,self.backup)
        with self.assertRaises(FileExistsError): restore_backup(self.backup,self.data)
        before=(self.data/'workspace.sqlite3').read_bytes()
        with (self.backup/'workspace.sqlite3').open('ab') as target: target.write(b'changed')
        with self.assertRaisesRegex(ValueError,'checksum'): restore_backup(self.backup,self.root/'tampered')
        self.assertFalse((self.root/'tampered').exists())
        self.assertEqual((self.data/'workspace.sqlite3').read_bytes(),before)

    def test_manifest_paths_and_database_symlinks_are_rejected(self):
        create_backup(self.data,self.backup)
        path=self.backup/'manifest.json'; manifest=json.loads(path.read_text())
        manifest['databases'][0]['name']='../data/workspace.sqlite3'; path.write_text(json.dumps(manifest))
        with self.assertRaisesRegex(ValueError,'database name'): verify_backup(self.backup)
        manifest['databases'][0]['name']='workspace.sqlite3'; path.write_text(json.dumps(manifest))
        (self.backup/'workspace.sqlite3').unlink()
        (self.backup/'workspace.sqlite3').symlink_to(self.data/'workspace.sqlite3')
        with self.assertRaisesRegex(ValueError,'Missing backup'): verify_backup(self.backup)

    def test_missing_workspace_and_existing_backup_destination_fail(self):
        with self.assertRaisesRegex(ValueError,'required'): create_backup(self.root/'missing',self.backup)
        create_backup(self.data,self.backup)
        with self.assertRaises(FileExistsError): create_backup(self.data,self.backup)
