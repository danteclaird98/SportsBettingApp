import {test} from 'node:test';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const dir=mkdtempSync(join(tmpdir(),'edgeboard-compat-'));
process.env.RESEARCH_DB=join(dir,'test.sqlite3');
const {db,requireAuth}=await import('./sdk.ts');
test('SQLite compatibility: CRUD, ownership scopes and atomic rollback',async()=>{
 const [id]=await db.add('owner-a',[{value:1}]);
 assert.equal((await db.get('owner-a',[id]))[0].value,1);
 assert.equal((await db.get('owner-b',[id]))[0],null);
 assert.equal((await db.list('owner-a',{limit:1})).items[0].id,id);
 const circular={};circular.self=circular;
 await assert.rejects(db.transact([db.tx.update('owner-a',[{id,record:{value:2}}]),db.tx.update('owner-a',[{id:'bad',record:circular}])]));
 assert.equal((await db.get('owner-a',[id]))[0].value,1);
 await db.transact([db.tx.update('owner-a',[{id,record:{value:3}}])]);
 assert.equal((await db.get('owner-a',[id]))[0].value,3);
 assert.equal((await requireAuth()({user:null})).status,401);
 assert.equal(await requireAuth()({user:{userId:'local-owner'}}),undefined);
 assert.deepEqual(await db.delete('owner-a',[id]),[true]);
 assert.equal((await db.get('owner-a',[id]))[0],null);
 rmSync(dir,{recursive:true,force:true});
});

test('stored odds routes retain authentication and explicit unavailable configuration',async()=>{
 const gatewayDir=mkdtempSync(join(tmpdir(),'edgeboard-gateway-runtime-'));
 process.env.RESEARCH_DB=join(gatewayDir,'gateway.sqlite3');
 delete process.env.ODDS_BACKEND_URL;
 delete process.env.ODDS_BACKEND_READ_TOKEN;
 try {
  const {handler}=await import('../build/backend.mjs');
  const routes=handler.routes;
  const result=await routes['GET /api/odds-backend/status'][0]({query:{},params:{}});
  assert.equal(result.status,200);
  assert.equal(result.data.state,'NOT_CONFIGURED');
  assert.equal(result.data.executionEnabled,false);
  for(const path of ['events','events/:id','events/:id/markets','latest','history','bookmakers']){
   const chain=routes['GET /api/odds-backend/'+path];
   assert.equal(chain.length,2);
   assert.equal((await chain[0]({user:null})).status,401);
   assert.equal(await chain[0]({user:{userId:'local-owner'}}),undefined);
   const response=await chain[1]({query:['latest','history'].includes(path)?{event_id:'1'}:{},params:{id:'1'}});
   assert.equal(response.status,503);
   assert.equal(response.data.state,'NOT_CONFIGURED');
  }
 } finally { rmSync(gatewayDir,{recursive:true,force:true}); }
});
