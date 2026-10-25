import {createServer} from 'node:http';
import {handler} from './build/backend.mjs';
const routes=handler.routes;
createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');const route=routes[req.method+' '+url.pathname];
 const send=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
 if(!route)return send(404,{error:'Unknown research route'});
 try{
 let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>1048576)return send(413,{error:'Request too large'});}
 let body={};try{body=raw?JSON.parse(raw):{};}catch{return send(400,{error:'Invalid JSON request'});}
 const user=req.headers['x-local-research-user']==='local-owner'?{userId:'local-owner'}:null;
 const ctx={query:Object.fromEntries(url.searchParams),body,user,event:{user}};
 for(const fn of route){const result=await fn(ctx);if(result)return send(result.status||200,result.data);}
 send(204,null);
 }catch(e){send(500,{error:e.message||'Research failed'});}
}).listen(Number(process.env.RESEARCH_PORT||8091),'127.0.0.1',()=>console.log('Research backend ready'));
