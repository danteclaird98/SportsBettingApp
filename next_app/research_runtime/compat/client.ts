let token='';
let signedIn=sessionStorage.getItem('research-local-user')==='yes';
const user={userId:'local-owner',id:'local-owner',email:'local@localhost',name:'Local workspace owner'};
export const auth={isSignedIn:()=>signedIn,async getUser(){return signedIn?user:null;},async signIn(){signedIn=true;sessionStorage.setItem('research-local-user','yes');return user;},async signOut(){signedIn=false;sessionStorage.removeItem('research-local-user');}};
async function request(method:string,path:string,body?:unknown){
 if(!token){const r=await fetch('/api/bootstrap');token=(await r.json()).csrf;}
 const r=await fetch('/research-api'+path,{method,headers:{'Content-Type':'application/json','X-Workspace-Token':token,'X-Local-Research-User':signedIn?'local-owner':''},...(body===undefined?{}:{body:JSON.stringify(body)})});
 const data=await r.json();if(!r.ok)throw Error(data.error||data.message||'Research request failed');return {data,status:r.status};
}
export const api={get:(path:string)=>request('GET',path),post:(path:string,body?:unknown)=>request('POST',path,body),put:(path:string,body?:unknown)=>request('PUT',path,body),delete:(path:string)=>request('DELETE',path)};
