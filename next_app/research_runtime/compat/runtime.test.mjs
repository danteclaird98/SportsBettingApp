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

test('real HTTP gateway dispatch preserves event parameters, authentication and filter boundaries',{timeout:10000},async()=>{
 const {spawn}=await import('node:child_process');
 const httpDir=mkdtempSync(join(tmpdir(),'edgeboard-gateway-http-'));
 const child=spawn(process.execPath,['runtime.mjs'],{cwd:new URL('..',import.meta.url),env:{...process.env,RESEARCH_DB:join(httpDir,'http.sqlite3'),RESEARCH_PORT:'0',ODDS_BACKEND_URL:'',ODDS_BACKEND_READ_TOKEN:''},stdio:['ignore','pipe','pipe']});
 try{
  const port=await new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>reject(Error('HTTP runtime did not start')),5000);
   child.once('error',e=>{clearTimeout(timer);reject(e);});
   let output='';child.stdout.on('data',chunk=>{output+=chunk;const match=output.match(/Research backend ready at (\d+)/);if(match){clearTimeout(timer);resolve(Number(match[1]));}});
   child.once('exit',code=>{clearTimeout(timer);reject(Error('HTTP runtime exited before readiness: '+code));});
  });
  const base='http://127.0.0.1:'+port;
  const status=await fetch(base+'/api/odds-backend/status');
  assert.equal(status.status,200);assert.equal((await status.json()).state,'NOT_CONFIGURED');
  assert.equal((await fetch(base+'/api/odds-backend/events/1')).status,401);
  const headers={'X-Local-Research-User':'local-owner'};
  for(const path of ['/api/odds-backend/events/1','/api/odds-backend/events/1/markets']){
   const response=await fetch(base+path,{headers});
   assert.equal(response.status,503,path);assert.equal((await response.json()).state,'NOT_CONFIGURED');
  }
  assert.equal((await fetch(base+'/api/receiving-forward?owner=local-owner')).status,401);
  assert.equal((await fetch(base+'/api/receiving-forward?owner=another-owner',{headers})).status,403);
  const history=await fetch(base+'/api/receiving-forward?owner=local-owner',{headers});
  assert.equal(history.status,200);
  const saved=await history.json();
  assert.equal(saved.owner,'local-owner');
  assert.equal(saved.executionEnabled,false);
  const invalidForecast=await fetch(base+'/api/receiving-forecast',{method:'POST',headers:{...headers,'Content-Type':'application/json'},body:'{}'});
  const blocked=await invalidForecast.json();
  assert.equal(blocked.executionEnabled,false);
  assert.equal(blocked.bettingDecision,'HOLD');
  const invalid=await fetch(base+'/api/odds-backend/events/invalid',{headers});
  assert.equal(invalid.status,400);assert.equal((await invalid.json()).error,'INVALID_EVENT_ID');
  assert.equal((await fetch(base+'/api/odds-backend/latest?event_id=1&event_id=2',{headers})).status,400);
  assert.equal((await fetch(base+'/api/odds-backend/events/1',{method:'POST',headers})).status,404);
 }finally{
  if(child.exitCode===null){const exited=new Promise(resolve=>child.once('exit',resolve));child.kill('SIGTERM');await exited;}
  rmSync(httpDir,{recursive:true,force:true});
 }
});
