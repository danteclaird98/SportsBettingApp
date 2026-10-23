"""Append-only SQLite snapshot store for normalized EdgeOdds quotes."""
from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path
from contextlib import contextmanager
from datetime import timezone,datetime
from typing import Iterable

from .models import NormalizedQuote


SCHEMA = """
CREATE TABLE IF NOT EXISTS odds_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    provider TEXT NOT NULL,
    bookmaker TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    source_market_id TEXT NOT NULL,
    event_id TEXT NOT NULL,
    market_type TEXT NOT NULL,
    selection TEXT NOT NULL,
    line REAL,
    period TEXT NOT NULL,
    settlement_rules_hash TEXT NOT NULL,
    decimal_price REAL NOT NULL,
    retrieved_at TEXT NOT NULL,
    source_updated_at TEXT,
    status TEXT NOT NULL,
    source_payload_hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_odds_event_time
ON odds_snapshots(event_id, retrieved_at DESC);
CREATE INDEX IF NOT EXISTS idx_odds_provider_book_time
ON odds_snapshots(provider, bookmaker, retrieved_at DESC);
"""


def _utc(value):
    return value.astimezone(timezone.utc).isoformat() if value else None


def _contract(values):
    return [values[k] for k in ['provider','bookmaker','event_id','market_type','selection','line','period','settlement_rules_hash']]


def _semantic(values):
    payload=_contract(values)+[values['source_event_id'],values['source_market_id'],float(values['decimal_price']),values['source_updated_at'],values['status']]
    if values['source_updated_at'] is None: payload.append(values['retrieved_at'])
    return _hash(payload)


def _hash(value):
    return hashlib.sha256(json.dumps(value,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()).hexdigest()


def _values(quote):
    if not isinstance(quote,NormalizedQuote): raise ValueError('Expected NormalizedQuote')
    return dict(provider=quote.provider,bookmaker=quote.bookmaker,source_event_id=quote.source_event_id,source_market_id=quote.source_market_id,event_id=quote.key.event_id,market_type=quote.key.market_type.value,selection=quote.key.selection,line=(float(quote.key.line) or 0.0) if quote.key.line is not None else None,period=quote.key.period,settlement_rules_hash=quote.key.settlement_rules_hash,decimal_price=quote.decimal_price,retrieved_at=_utc(quote.retrieved_at),source_updated_at=_utc(quote.source_updated_at),status=quote.status.value,source_payload_hash=quote.source_payload_hash)


def snapshot_fingerprint(quote: NormalizedQuote) -> str:
    """Economic source snapshot identity, independent of retrieval/envelope changes."""
    return _semantic(_values(quote))


class SnapshotStore:
    def __init__(self,path: str | Path) -> None:
        self.path=str(path)
        with self._connect() as db:
            db.executescript(SCHEMA)
            db.execute('BEGIN IMMEDIATE')
            columns={r['name'] for r in db.execute('PRAGMA table_info(odds_snapshots)')}
            for name,kind in [('contract_key','TEXT'),('source_time','REAL')]:
                if name not in columns: db.execute('ALTER TABLE odds_snapshots ADD COLUMN '+name+' '+kind)
            db.execute('CREATE TABLE IF NOT EXISTS semantic_snapshots(fingerprint TEXT PRIMARY KEY,snapshot_id INTEGER NOT NULL)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_odds_contract_source ON odds_snapshots(contract_key,source_time DESC)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_odds_event_page ON odds_snapshots(event_id,id)')
            db.execute('CREATE INDEX IF NOT EXISTS idx_odds_book_page ON odds_snapshots(bookmaker,id)')
            # Backfill without deleting duplicate legacy history or changing old IDs.
            for row in db.execute('SELECT * FROM odds_snapshots WHERE contract_key IS NULL').fetchall():
                values=dict(row)
                for key in ['retrieved_at','source_updated_at']:
                    if values[key]:values[key]=_utc(datetime.fromisoformat(values[key]))
                db.execute('UPDATE odds_snapshots SET contract_key=?,source_time=? WHERE id=?',(_hash(_contract(values)),datetime.fromisoformat(values['source_updated_at'] or values['retrieved_at']).timestamp(),row['id']))
                db.execute('INSERT OR IGNORE INTO semantic_snapshots VALUES(?,?)',(_semantic(values),row['id']))

    @contextmanager
    def _connect(self):
        db=sqlite3.connect(self.path,timeout=15);db.row_factory=sqlite3.Row
        try:
            with db: yield db
        finally:db.close()

    def _append(self,db,quote):
        values=_values(quote);fingerprint=_semantic(values)
        if db.execute('SELECT 1 FROM semantic_snapshots WHERE fingerprint=?',(fingerprint,)).fetchone():return False
        values.update(fingerprint=fingerprint,contract_key=_hash(_contract(values)),source_time=(quote.source_updated_at or quote.retrieved_at).timestamp())
        names=list(values)
        cur=db.execute('INSERT INTO odds_snapshots ('+','.join(names)+') VALUES ('+','.join('?' for _ in names)+')',list(values.values()))
        db.execute('INSERT INTO semantic_snapshots VALUES(?,?)',(fingerprint,cur.lastrowid))
        return True

    def append(self,quote: NormalizedQuote) -> bool:
        return bool(self.append_many([quote]))

    def append_many(self,quotes: Iterable[NormalizedQuote]) -> int:
        """A batch and its dedupe keys commit together; malformed input rolls it back."""
        with self._connect() as db:
            db.execute('BEGIN IMMEDIATE')
            return sum(self._append(db,quote) for quote in quotes)

    def _query(self,latest,event_id,bookmaker,limit,offset):
        if type(limit) is not int or not 1<=limit<=500 or type(offset) is not int or not 0<=offset<=1000000:raise ValueError('Invalid pagination')
        clauses=[];args=[]
        for key,value in [('event_id',event_id),('bookmaker',bookmaker)]:
            if value is not None:clauses.append('q.'+key+'=?');args.append(value)
        if latest:clauses.append('NOT EXISTS (SELECT 1 FROM odds_snapshots n WHERE n.contract_key=q.contract_key AND n.source_time>q.source_time)')
        sql='SELECT q.* FROM odds_snapshots q'+(' WHERE '+' AND '.join(clauses) if clauses else '')+' ORDER BY q.id DESC LIMIT ? OFFSET ?'
        with self._connect() as db:return [dict(r) for r in db.execute(sql,args+[limit,offset])]

    def latest(self,*,event_id=None,bookmaker=None,limit=100,offset=0):
        """Current source-time snapshot per contract; retain equal-time conflicts."""
        return self._query(True,event_id,bookmaker,limit,offset)

    def history(self,*,event_id=None,bookmaker=None,limit=100,offset=0):
        return self._query(False,event_id,bookmaker,limit,offset)
