import {createServer} from 'node:http';
import {handler} from './build/backend.mjs';
const routes=handler.routes;
function resolveRoute(method,pathname){
 const exact=routes[method+' '+pathname];
 if(exact)return {route:exact,params:{}};
 const actual=pathname.split('/');
 for(const [key,route] of Object.entries(routes)){
  const separator=key.indexOf(' '),verb=key.slice(0,separator),template=key.slice(separator+1).split('/');
  if(verb!==method||template.length!==actual.length)continue;
  const params={};let matches=true;
  for(let i=0;i<template.length;i++){
   if(/^:[A-Za-z][A-Za-z0-9_]*$/.test(template[i])){
    const value=decodeURIComponent(actual[i]);
    if(!value||value.includes('/')||value.includes('\0'))throw Error('Invalid route parameter');
    params[template[i].slice(1)]=value;
   }else if(template[i]!==actual[i]){matches=false;break;}
  }
  if(matches)return {route,params};
 }
 return null;
}
const server=createServer(async(req,res)=>{
 const url=new URL(req.url,'http://localhost');
 const send=(status,data)=>{res.writeHead(status,{'Content-Type':'application/json','Cache-Control':'no-store'});res.end(JSON.stringify(data));};
 let resolved;
 try{resolved=resolveRoute(req.method,url.pathname);}catch{return send(400,{error:'Invalid route parameter'});}
 if(!resolved)return send(404,{error:'Unknown research route'});
 if(url.pathname.startsWith('/api/odds-backend/')){
  const keys=[...url.searchParams.keys()];
  if(new Set(keys).size!==keys.length)return send(400,{error:'Duplicate filter'});
 }
 try{
 let raw='';for await(const chunk of req){raw+=chunk;if(Buffer.byteLength(raw)>1048576)return send(413,{error:'Request too large'});}
 let body={};try{body=raw?JSON.parse(raw):{};}catch{return send(400,{error:'Invalid JSON request'});}
 const user=req.headers['x-local-research-user']==='local-owner'?{userId:'local-owner'}:null;
 const ctx={query:Object.fromEntries(url.searchParams),params:resolved.params,body,user,event:{user}};
 for(const fn of resolved.route){const result=await fn(ctx);if(result)return send(result.status||200,result.data);}
 send(204,null);
 }catch(e){send(500,{error:e.message||'Research failed'});}
});
server.listen(Number(process.env.RESEARCH_PORT||8091),'127.0.0.1',()=>console.log('Research backend ready at '+server.address().port));
