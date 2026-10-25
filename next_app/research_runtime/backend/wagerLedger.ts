/** Revision-bound writes in the existing local research database.
 * Legacy records are read in place; ambiguous duplicate legacy ledgers require review.
 */
import { DatabaseSync } from 'node:sqlite';
import { createHash, randomUUID } from 'node:crypto';
import { mkdirSync, chmodSync } from 'node:fs';
import { dirname } from 'node:path';
import { wagerLedgerPayload, validateWagers } from '../shared/ledgerInput';
const protocol = 'revision-receipt-v1' as const;
const collection = (owner: string) => 'wager_ledger:' + owner;
const validRevision = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
function database(owner: string) {
  if (typeof owner !== 'string' || !owner.trim() || owner.length > 200) throw Error('Authenticated ledger owner required');
  const path = process.env.RESEARCH_DB || '../data/research.sqlite3';
  mkdirSync(dirname(path), { recursive: true, mode: 0o700 });
  const sql = new DatabaseSync(path);
  try {
    chmodSync(path, 0o600);
    sql.exec(`PRAGMA busy_timeout=10000;
      CREATE TABLE IF NOT EXISTS records(collection TEXT,id TEXT,body TEXT,PRIMARY KEY(collection,id));
      CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT,action TEXT,payload TEXT);
      CREATE TABLE IF NOT EXISTS wager_write_receipts(owner TEXT,request_id TEXT,payload_hash TEXT,receipt TEXT,PRIMARY KEY(owner,request_id));
      CREATE TRIGGER IF NOT EXISTS wager_receipts_no_update BEFORE UPDATE ON wager_write_receipts BEGIN SELECT RAISE(ABORT,'append only'); END;
      CREATE TRIGGER IF NOT EXISTS wager_receipts_no_delete BEFORE DELETE ON wager_write_receipts BEGIN SELECT RAISE(ABORT,'append only'); END;`);
    return sql;
  } catch (failure) { sql.close(); throw failure; }
}
function readCurrent(sql: DatabaseSync, owner: string) {
  const rows = sql.prepare('SELECT id,body FROM records WHERE collection=? ORDER BY rowid DESC LIMIT 2').all(collection(owner)) as Array<{id:string;body:string}>;
  if (rows.length > 1) throw Error('Multiple legacy ledgers require review; no records were merged or removed');
  if (!rows.length) return { id: null, wagers: [] as Record<string,unknown>[], revision: 0, updatedAt: null as string|null };
  const stored = JSON.parse(rows[0].body);
  const revision = stored.revision === undefined ? 0 : stored.revision;
  if (!validRevision(revision)) throw Error('Stored ledger revision invalid; recovery required');
  return { id: rows[0].id, wagers: validateWagers(stored.wagers), revision, updatedAt: stored.updatedAt ?? null };
}
function canonical(value: unknown): string {
  if (Array.isArray(value)) return '[' + value.map(canonical).join(',') + ']';
  if (value && typeof value === 'object') return '{' + Object.keys(value).sort().map(key => JSON.stringify(key) + ':' + canonical((value as Record<string,unknown>)[key])).join(',') + '}';
  return JSON.stringify(value);
}
function request(owner: string, value: unknown) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error('Reload the ledger before saving: a revision-bound request is required');
  const body = value as Record<string,unknown>;
  if (Object.keys(body).some(key => !['action','owner','requestId','expectedRevision','wagers'].includes(key)) ||
      !['save','reconcile'].includes(body.action as string) || body.owner !== owner ||
      typeof body.requestId !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(body.requestId) ||
      !validRevision(body.expectedRevision) || body.expectedRevision === Number.MAX_SAFE_INTEGER) throw Error('Invalid revision-bound ledger request');
  const updatedAt = new Date().toISOString();
  const payload = wagerLedgerPayload(body.wagers, updatedAt);
  const hash = createHash('sha256').update(canonical({ expectedRevision:body.expectedRevision,wagers:payload.wagers })).digest('hex');
  return { action:body.action, requestId:body.requestId, expectedRevision:body.expectedRevision, payload, hash };
}
export async function getWagerLedger(owner: string) {
  const sql = database(owner);
  try { const current=readCurrent(sql,owner); return { wagers:current.wagers,updatedAt:current.updatedAt,authenticated:true,owner,protocol,revision:current.revision }; }
  finally { sql.close(); }
}
export async function saveWagerLedger(owner: string, input: unknown) {
  const write=request(owner,input), sql=database(owner);
  try {
    sql.exec('BEGIN IMMEDIATE');
    try {
      const saved=sql.prepare('SELECT payload_hash,receipt FROM wager_write_receipts WHERE owner=? AND request_id=?').get(owner,write.requestId) as {payload_hash:string;receipt:string}|undefined;
      if (saved) {
        if (saved.payload_hash !== write.hash) throw Error('Request ID already belongs to a different ledger update');
        const receipt=JSON.parse(saved.receipt);
        sql.exec('COMMIT'); return { status:'saved',receipt };
      }
      // Absence cannot authorize resubmission after an interrupted/unknown write.
      if (write.action === 'reconcile') { sql.exec('COMMIT'); return {status:'unknown',requestId:write.requestId}; }
      const current=readCurrent(sql,owner);
      if (current.revision !== write.expectedRevision) { sql.exec('COMMIT'); return { status:'conflict',currentRevision:current.revision }; }
      const revision=current.revision+1,id=current.id ?? randomUUID();
      const body={...write.payload,revision};
      const receipt={owner,requestId:write.requestId,expectedRevision:write.expectedRevision,revision,count:write.payload.wagers.length,payloadHash:write.hash,updatedAt:write.payload.updatedAt};
      sql.prepare('INSERT INTO records VALUES(?,?,?) ON CONFLICT(collection,id) DO UPDATE SET body=excluded.body').run(collection(owner),id,JSON.stringify(body));
      sql.prepare('INSERT INTO wager_write_receipts VALUES(?,?,?,?)').run(owner,write.requestId,write.hash,JSON.stringify(receipt));
      sql.prepare('INSERT INTO audit(at,action,payload) VALUES(?,?,?)').run(write.payload.updatedAt,'update',JSON.stringify({table:collection(owner),id,record:body,requestId:write.requestId}));
      sql.exec('COMMIT'); return { status:'saved',receipt };
    } catch (failure) { sql.exec('ROLLBACK'); throw failure; }
  } finally { sql.close(); }
}
