import {test} from 'node:test';
import assert from 'node:assert/strict';
import {build} from 'esbuild';
import {mkdtempSync,rmSync,writeFileSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {spawn} from 'node:child_process';
import {DatabaseSync} from 'node:sqlite';
const result=await build({entryPoints:[new URL('../../backend/wagerLedger.ts',import.meta.url).pathname],bundle:true,platform:'node',format:'esm',write:false});
const code=result.outputFiles[0].text;
const ledger=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'));
const wager=id=>({id,mode:'paper',status:'open',betType:'single',stake:10,decimalOdds:2,payout:0,fees:0,event:'Synthetic fixture',sportsbook:'QA',selection:'Home',currency:'USD',placedAt:'2026-10-25T20:00:00Z',settlementConfirmed:false,history:[]});
const request=(requestId,expectedRevision,wagers,owner='alice')=>({action:'save',owner,requestId,expectedRevision,wagers});
async function isolated(run){const dir=mkdtempSync(join(tmpdir(),'ledger-revision-'));process.env.RESEARCH_DB=join(dir,'research.sqlite3');try{await run(dir);}finally{rmSync(dir,{recursive:true,force:true});}}
test('stale writes conflict and replay survives later updates without replacing them',()=>isolated(async()=>{
 const first=request('first',0,[wager('a')]);const saved=await ledger.saveWagerLedger('alice',first);
 assert.equal(saved.status,'saved');assert.equal(saved.receipt.revision,1);
 assert.deepEqual(await ledger.saveWagerLedger('alice',request('stale',0,[wager('b')])),{status:'conflict',currentRevision:1});
 await ledger.saveWagerLedger('alice',request('second',1,[wager('a'),wager('c')]));
 assert.deepEqual(await ledger.saveWagerLedger('alice',first),saved);
 assert.equal((await ledger.getWagerLedger('alice')).revision,2);
 assert.deepEqual((await ledger.getWagerLedger('alice')).wagers.map(w=>w.id),['a','c']);
 await assert.rejects(ledger.saveWagerLedger('alice',{...first,wagers:[wager('different')]}),/different ledger update/);
}));
test('two independent processes at the same revision cannot both overwrite the ledger',()=>isolated(async dir=>{
 const module=join(dir,'ledger.mjs');writeFileSync(module,code);await ledger.getWagerLedger('alice');
 function child(body){return new Promise((resolve,reject)=>{const p=spawn(process.execPath,['--input-type=module','-e',`const m=await import(${JSON.stringify(module)});console.log(JSON.stringify(await m.saveWagerLedger('alice',JSON.parse(process.argv[1]))));`,JSON.stringify(body)],{env:{...process.env},stdio:['ignore','pipe','pipe']});let out='',err='';p.stdout.on('data',x=>out+=x);p.stderr.on('data',x=>err+=x);p.once('error',reject);p.once('exit',c=>c===0?resolve(JSON.parse(out)):reject(Error(err)));});}
 const outcomes=await Promise.all([child(request('process-a',0,[wager('a')])),child(request('process-b',0,[wager('b')]))]);
 assert.deepEqual(outcomes.map(x=>x.status).sort(),['conflict','saved']);assert.equal((await ledger.getWagerLedger('alice')).wagers.length,1);
}));
test('read-only reconciliation recovers lost acknowledgements and never resubmits unknown requests',()=>isolated(async dir=>{
 const write=request('stable-request',0,[wager('a')]);const acknowledged=await ledger.saveWagerLedger('alice',write);
 // Fresh process/module use is equivalent to resuming after transport loss.
 const restored=await import('data:text/javascript;base64,'+Buffer.from(code+'\n// restarted').toString('base64'));
 assert.deepEqual(await restored.saveWagerLedger('alice',{...write,action:'reconcile'}),acknowledged);
 assert.deepEqual(await restored.saveWagerLedger('alice',{...write,requestId:'never-submitted',action:'reconcile'}),{status:'unknown',requestId:'never-submitted'});
 assert.equal((await ledger.getWagerLedger('alice')).revision,1);
 assert.deepEqual((await ledger.getWagerLedger('bob')).wagers,[]);
 await assert.rejects(ledger.saveWagerLedger('bob',{...write,action:'reconcile'}),/Invalid revision-bound/);
}));
test('failed receipt insertion rolls back ledger, revision and audit together',()=>isolated(async()=>{
 await ledger.getWagerLedger('alice');const sql=new DatabaseSync(process.env.RESEARCH_DB);
 try{sql.exec("CREATE TRIGGER force_receipt_failure BEFORE INSERT ON wager_write_receipts BEGIN SELECT RAISE(ABORT,'synthetic receipt failure'); END;");
 await assert.rejects(ledger.saveWagerLedger('alice',request('fails',0,[wager('a')])));
 assert.equal((await ledger.getWagerLedger('alice')).revision,0);assert.equal(sql.prepare('SELECT count(*) AS n FROM records').get().n,0);assert.equal(sql.prepare('SELECT count(*) AS n FROM audit').get().n,0);
 }finally{sql.close();}
}));
test('valid legacy records remain in place; duplicate legacy collections require explicit recovery',()=>isolated(async()=>{
 await ledger.getWagerLedger('alice');const sql=new DatabaseSync(process.env.RESEARCH_DB);const old=JSON.stringify({wagers:[wager('old')],updatedAt:'2026-10-25T20:00:00Z'});
 try{sql.prepare('INSERT INTO records VALUES(?,?,?)').run('wager_ledger:alice','old-record-id',old);
 assert.equal((await ledger.getWagerLedger('alice')).revision,0);assert.equal(sql.prepare('SELECT body FROM records').get().body,old);
 await ledger.saveWagerLedger('alice',request('upgrade',0,[wager('old'),wager('new')]));assert.equal(sql.prepare('SELECT id FROM records').get().id,'old-record-id');
 sql.prepare('INSERT INTO records VALUES(?,?,?)').run('wager_ledger:alice','second-legacy-id',old);
 await assert.rejects(ledger.getWagerLedger('alice'),/Multiple legacy/);await assert.rejects(ledger.saveWagerLedger('alice',request('blocked',1,[])),/Multiple legacy/);
 assert.equal(sql.prepare('SELECT count(*) AS n FROM records').get().n,2);
 }finally{sql.close();}
}));
test('malformed field types and legacy unversioned writes never change saved state',()=>isolated(async()=>{
 for(const field of ['mode','status','betType'])await assert.rejects(ledger.saveWagerLedger('alice',request('bad-'+field,0,[{...wager('bad'),[field]:['open']}])));
 await assert.rejects(ledger.saveWagerLedger('alice',[wager('legacy')]),/revision-bound/);
 assert.equal((await ledger.getWagerLedger('alice')).revision,0);
}));
