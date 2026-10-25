import { DatabaseSync } from 'node:sqlite';
import { randomUUID } from 'node:crypto';
import { mkdirSync, chmodSync } from 'node:fs';
import { dirname } from 'node:path';
const path=process.env.RESEARCH_DB || '../data/research.sqlite3';
mkdirSync(dirname(path),{recursive:true,mode:0o700});
const sql=new DatabaseSync(path); chmodSync(path,0o600);
sql.exec('PRAGMA journal_mode=WAL; CREATE TABLE IF NOT EXISTS records(collection TEXT,id TEXT,body TEXT,PRIMARY KEY(collection,id)); CREATE TABLE IF NOT EXISTS audit(id INTEGER PRIMARY KEY,at TEXT,action TEXT,payload TEXT);');
function audit(action:string,payload:unknown){sql.prepare('INSERT INTO audit(at,action,payload) VALUES(?,?,?)').run(new Date().toISOString(),action,JSON.stringify(payload));}
const update=(table:string,items:any[])=>items.map(({id,record})=>{sql.prepare('INSERT INTO records VALUES(?,?,?) ON CONFLICT(collection,id) DO UPDATE SET body=excluded.body').run(table,id,JSON.stringify(record));audit('update',{table,id,record});return true;});
export const db={
 async list(table:string,opts:any={}){const limit=Math.min(500,Math.max(1,opts.limit||100));const rows=sql.prepare('SELECT id,body FROM records WHERE collection=? ORDER BY rowid DESC LIMIT ?').all(table,limit+1);return {items:rows.slice(0,limit).map((r:any)=>({...JSON.parse(r.body),id:r.id})),nextToken:rows.length>limit?'MORE_RECORDS_EXIST':null};},
 async get(table:string,ids:string[]){return ids.map(id=>{const r:any=sql.prepare('SELECT body FROM records WHERE collection=? AND id=?').get(table,id);return r?{...JSON.parse(r.body),id}:null;});},
 async add(table:string,records:any[]){return records.map(record=>{const id=randomUUID();update(table,[{id,record}]);return id;});},
 async update(table:string,items:any[]){return update(table,items);},
 async delete(table:string,ids:string[]){return ids.map(id=>{const r=sql.prepare('DELETE FROM records WHERE collection=? AND id=?').run(table,id);audit('delete',{table,id});return !!r.changes;});},
 tx:{update:(table:string,items:any[])=>({table,items})},
 async transact(ops:any[]){sql.exec('BEGIN IMMEDIATE');try{const result=ops.map(op=>update(op.table,op.items));sql.exec('COMMIT');return result;}catch(e){sql.exec('ROLLBACK');throw e;}}
};
const allowed=['PARLAY_API_KEY','SHARPAPI_KEY','THE_ODDS_API_KEY','CLEARSPORTS_API_KEY','PUCKAPI_API_KEY','ODDS_BACKEND_URL','ODDS_BACKEND_READ_TOKEN'];
export const secrets={async listSecretNames(){return allowed.filter(k=>!!process.env[k]);},async readSecret(name:string){if(!allowed.includes(name)||!process.env[name])throw Error('Provider credential is not configured');return process.env[name]!;}};
export const json=(data:any,status=200)=>({status,data});
export const error=(message:string,status=400)=>({status,data:{error:message,message}});
export const auth={async getUser(event:any){return event?.user||null;}};
export const requireAuth=()=>async(ctx:any)=>ctx.user?undefined:error('Local workspace sign-in required',401);
export const router=(routes:any)=>({routes});
