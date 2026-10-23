import sqlite3,unittest
from tempfile import TemporaryDirectory
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from dataclasses import replace
from test_edgeodds import quote,NOW
from edgeodds.store import SnapshotStore,SCHEMA,_values
from edgeodds.models import MarketKey,MarketType,MarketStatus,evaluate_freshness
from edgeodds.identity import AliasRegistry,AliasRecord,EventResolver,CanonicalEventRef,ProviderEvent,UnresolvedIdentity

class LaunchTests(unittest.TestCase):
    def setUp(self):self.tmp=TemporaryDirectory();self.path=self.tmp.name+'/db';self.store=SnapshotStore(self.path)
    def tearDown(self):self.tmp.cleanup()
    def test_retry_retrieval_envelope_timezone_and_restart(self):
        self.assertTrue(self.store.append(quote()))
        later=quote(retrieved_at=NOW+timedelta(seconds=1),source_payload_hash='new envelope')
        self.assertFalse(SnapshotStore(self.path).append(later));self.assertEqual(len(self.store.history()),1)
    def test_latest_uses_source_time_not_arrival(self):
        self.store.append(quote());self.store.append(quote(decimal_price=2,source_updated_at=NOW-timedelta(seconds=30),retrieved_at=NOW+timedelta(seconds=1)))
        self.assertEqual(self.store.latest()[0]['decimal_price'],1.91)
    def test_suspension_and_equal_time_conflicts_retained(self):
        self.store.append(quote());self.store.append(quote(status=MarketStatus.SUSPENDED,source_updated_at=NOW))
        self.assertEqual(self.store.latest()[0]['status'],'suspended')
        self.store.append(quote(status=MarketStatus.OPEN,source_updated_at=NOW,decimal_price=3))
        self.assertEqual(len(self.store.latest()),2)
    def test_batch_rolls_back_after_invalid_row(self):
        with self.assertRaises(ValueError):self.store.append_many([quote(),None])
        self.assertEqual(self.store.history(),[])
    def test_concurrent_replays_insert_once(self):
        def append(i):return SnapshotStore(self.path).append(quote(retrieved_at=NOW+timedelta(seconds=i)))
        with ThreadPoolExecutor(max_workers=4) as pool:self.assertEqual(sum(pool.map(append,range(8))),1)
    def test_bad_price_and_limits(self):
        for value in [True,1e308]:
            with self.assertRaises(ValueError):quote(decimal_price=value)
        with self.assertRaises(ValueError):self.store.latest(limit=True)
        with self.assertRaises(ValueError):self.store.history(limit=501)
        self.assertFalse(evaluate_freshness(quote(retrieved_at=NOW+timedelta(hours=1)),now=NOW,max_age_seconds=60).eligible)
    def test_indexes_and_connections_close(self):
        with self.store._connect() as db:
            plan=str(db.execute('EXPLAIN QUERY PLAN SELECT * FROM odds_snapshots WHERE contract_key=? ORDER BY source_time DESC LIMIT 1',('x',)).fetchall()[0][3])
            self.assertIn('idx_odds_contract_source',plan)
        with self.assertRaises(sqlite3.ProgrammingError):db.execute('SELECT 1')
    def test_legacy_database_migrates_without_resetting_ids(self):
        path=self.tmp.name+'/legacy'
        values=_values(quote());values['fingerprint']='legacy-fingerprint'
        with sqlite3.connect(path) as db:
            db.executescript(SCHEMA)
            db.execute('INSERT INTO odds_snapshots ('+','.join(values)+') VALUES ('+','.join('?' for _ in values)+')',list(values.values()))
        migrated=SnapshotStore(path)
        self.assertFalse(migrated.append(quote()))
        self.assertEqual(migrated.history()[0]['id'],1)
    def test_neutral_swapped_participants_require_explicit_flags(self):
        aliases=AliasRegistry([AliasRecord('LA Lakers','nba:lal','p','fixture'),AliasRecord('Los Angeles Lakers','nba:lal','p','fixture'),AliasRecord('Celtics','nba:bos','p','fixture')])
        event=CanonicalEventRef('game','nba','nba:lal','nba:bos',NOW,neutral_site=True)
        source=ProviderEvent('p','native','nba','Celtics','LA Lakers',NOW,neutral_site=True)
        self.assertEqual(EventResolver(aliases,[event]).resolve(source).event.event_id,'game')
        with self.assertRaises(UnresolvedIdentity):EventResolver(aliases,[event]).resolve(replace(source,neutral_site=False))
        with self.assertRaises(UnresolvedIdentity):EventResolver(aliases,[event]).resolve(replace(source,starts_at=NOW+timedelta(days=1)))
