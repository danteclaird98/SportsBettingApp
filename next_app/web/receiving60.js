const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localTime = date => Number.isFinite(date.getTime()) ? new Date(date.getTime() - date.getTimezoneOffset()*60000).toISOString().slice(0,16) : '';
const utc = value => { const date=new Date(value); if (!value || !Number.isFinite(date.getTime())) throw Error('Enter valid kickoff and decision times'); return date.toISOString(); };
const fresh = () => ({playerId:'',gameId:'',position:'WR',kickoffAt:localTime(new Date(Date.now()+7*86400000)),decisionAt:localTime(new Date()),history:'[]'});
const state = {draft:fresh(),importText:'[]',inputMode:'supplied',busy:false,error:'',result:null,request:null,savedId:null,
  readiness:null,readinessError:'',receipts:[],nextCursor:null,receiptsError:'',openRecord:null};
let request, redraw;
const reasons={
  UNVERIFIED_SUPPLIED_HISTORY_REQUIRES_FORWARD_VALIDATION:'Estimate calculated from unverified history. Forward validation is still required.',
  INSUFFICIENT_HISTORY:'At least three prior games are required.',
  INVALID_REQUEST_SCHEMA:'The request does not match the supported player-history format.',
  UNSUPPORTED_TARGET:'This model supports NFL regular-season WR, RB and TE receiving yards of 60 or more.',
  INVALID_DECISION_CLOCK:'Use a valid decision time before a future kickoff.',
  FUTURE_DECISION_CLOCK:'The decision time cannot be in the future.',
  MODEL_NOT_AVAILABLE_AS_OF_DECISION:'The model was not available at this decision time.',
  INVALID_HISTORY_IDENTITY:'Check player IDs and game IDs. Prior games must be unique and exclude the target game.',
  HISTORY_NOT_AVAILABLE_AS_OF_DECISION:'Every prior game must resolve and be observed before the decision time. Yardage must be an integer.',
  ARTIFACT_INTEGRITY_FAILURE:'The installed model failed its integrity check. No estimate is available.'
};
export function configureReceiving60(options) { request=options.request; redraw=options.redraw; }
function invalidate() { state.result=null; state.request=null; state.savedId=null; state.error=''; }
async function loadReceipts(before=null) {
  try {
    const page=await request('/api/receiving60/receipts'+(before?'?before='+before:''));
    state.receipts=before?[...state.receipts,...page.receipts]:page.receipts;
    state.nextCursor=page.nextCursor; state.receiptsError='';
  } catch(error) { state.receiptsError=error.message; }
}
export async function loadReceiving60Readiness() {
  try { state.readiness=await request('/api/receiving60/readiness'); state.readinessError=''; }
  catch(error) { state.readiness=null; state.readinessError=error.message; }
  await loadReceipts();
  redraw();
}
export function receiving60View() {
  const d=state.draft, r=state.result;
  const field=(name,label,type='text')=>`<label>${label}<input name="${name}" type="${type}" value="${esc(d[name])}" ${type==='text'?'maxlength="160"':''} required></label>`;
  return `<div class="heading"><div><div class="eyebrow">NFL RESEARCH</div><h1>Receiving 60+ lab.</h1><p>Estimate full-game receiving yards of 60 or more from supplied history.</p></div><span class="tag amber">RESEARCH / HOLD</span></div>
  <div class="spacer"></div><div class="notice">Conditional on a recorded player row. Participation and current eligibility are unverified. No live approval, uncertainty interval or verified EV.</div><div class="spacer"></div>
  <div class="grid2"><section class="panel"><div class="panelhead"><h2>Player & game</h2><span class="tag ${state.inputMode==='synthetic'?'amber':''}">${state.inputMode==='synthetic'?'SYNTHETIC INPUT':'SUPPLIED / UNVERIFIED'}</span></div>
  <form id="receiving60-form" class="panelbody"><fieldset class="research-fields" ${state.busy?'disabled':''}><div class="formgrid">
    ${field('playerId','Player ID')}${field('gameId','Target game ID')}
    <label>Position<select name="position">${['WR','RB','TE'].map(p=>`<option ${p===d.position?'selected':''}>${p}</option>`).join('')}</select></label>
    <label>Target<input value="NFL · REG · full game · 60+ yards" readonly></label>
    ${field('kickoffAt','Scheduled kickoff (your local time)','datetime-local')}${field('decisionAt','Decision time (your local time)','datetime-local')}
  </div><div class="spacer"></div><h3>Prior games</h3><p id="history-help" class="subtle">Enter 3–500 prior games with unique game IDs. Use your local time for dates. Include the complete relevant recorded history; it is not fetched automatically. A game's final result must be observed before the decision time.</p>
  <div id="receiving60-games">${JSON.parse(d.history).map((row,i)=>`<section class="history-game"><div class="panelhead"><h3>Prior game ${i+1}</h3><button type="button" class="tiny" data-history-remove="${i}">Remove game ${i+1}</button></div><div class="formgrid panelbody">${[
    ['playerId','Player ID','text'],['gameId','Prior game ID','text'],['receivingYards','Receiving yards','number'],
    ['kickoffAt','Kickoff (local)','datetime-local'],['resolvedAt','Result finalized (local)','datetime-local'],['observedAt','First observed (local)','datetime-local']
  ].map(([key,label,type])=>`<label>${label}<input name="prior-${i}-${key}" data-history-index="${i}" data-history-field="${key}" type="${type}" ${type==='number'?'step="1"':''} value="${esc(type==='datetime-local'?localTime(new Date(row[key])):row[key])}" required></label>`).join('')}</div></section>`).join('') || '<p class="subtle">No prior games entered.</p>'}</div>
  <div class="actions"><button type="button" id="receiving60-add-game" ${JSON.parse(d.history).length>=500?'disabled':''}>Add prior game</button></div>
  <details class="history-import"><summary>Import history JSON</summary><p class="subtle">Paste a history array from the API format, then apply it to replace the games above. Timestamps must be UTC ending in Z.</p><label>History JSON<textarea name="history" spellcheck="false" rows="8">${esc(state.importText)}</textarea></label><div class="actions"><button type="button" id="receiving60-import">Apply imported history</button></div></details>
  <div class="actions"><button type="submit" class="primary">${state.busy?'Calculating…':'Calculate research estimate'}</button><button type="button" id="receiving60-sample">Load synthetic example</button><button type="button" id="receiving60-clear">Clear inputs</button></div></fieldset>
  ${state.error?`<div class="error" role="alert">${esc(state.error)}</div>`:''}
  <p class="subtle">Drafts stay in this tab until reload. Calculation does not save a record; use Save research receipt to keep the scored inputs on your server.</p></form></section>
  <section class="panel"><div class="panelhead"><h2>Research receipt</h2><span class="tag amber">HOLD</span></div><div class="panelbody">
  <div id="receiving60-result" aria-live="polite">${r?`<span class="tag ${state.inputMode==='synthetic'?'amber':''}">${state.inputMode==='synthetic'?'SYNTHETIC EXAMPLE':'UNVERIFIED SUPPLIED HISTORY'}</span>
    <div class="research-estimate">${r.estimateAvailable?`${(r.probability*100).toFixed(1)}%`:'No estimate'}</div><p>${r.estimateAvailable?'Conditional model estimate · 60+ receiving yards':'The model abstained from scoring these inputs.'}</p>
    <div class="statusbox"><strong>${esc(reasons[r.reason] || 'The model cannot score these inputs. Inspect the full receipt for the reason.')}</strong><br>${esc(r.interpretation)}</div>
    <div class="listrow"><span>Uncertainty interval</span><span>Unavailable</span></div><div class="listrow"><span>Expected value</span><span>Unavailable</span></div><div class="listrow"><span>Live approval</span><span>Not established</span></div>
    <details><summary>Inspect full score receipt</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>
    <div class="actions"><button id="receiving60-download" ${state.busy?'disabled':''}>Download research receipt ↓</button>${r.estimateAvailable?`<button id="receiving60-save" ${state.busy||state.savedId?'disabled':''}>${state.savedId?`Saved receipt #${state.savedId}`:state.busy?'Saving…':'Save research receipt'}</button>`:''}</div>`:'<p>Enter player history or load the clearly labeled synthetic example. Editing inputs clears the previous result.</p>'}</div>
  <div class="spacer"></div><h3>Installed model</h3><p class="subtle">${state.readiness?`Artifact integrity: ${state.readiness.artifactVerified?'verified':'failed'} · ${esc(state.readiness.modelVersion)}`:state.readinessError?`Readiness unavailable: ${esc(state.readinessError)}`:'Checking model readiness…'}</p>
  <p class="subtle">Calibration was selected in-sample. The 2025 diagnostic is consumed. A new forward validation period is required.</p></div></section></div>
  <section class="panel"><div class="panelhead"><h2>Saved research receipts</h2><button id="receiving60-refresh-records" ${state.busy?'disabled':''}>Refresh saved receipts</button></div><div class="panelbody"><p class="subtle">Append-only records, separate from wagers. Input labels are declared by the client. Saving does not verify player history or qualify a record as forward validation.</p>
  ${state.receiptsError?`<div class="error" role="alert">${esc(state.receiptsError)}</div>`:''}
  ${state.receipts.length?`<div class="tablewrap"><table><thead><tr><th>Player / game</th><th>Input / status</th><th>Saved time</th><th>Receipt</th></tr></thead><tbody>${state.receipts.map(item=>`<tr><td>${esc(item.playerId)}<br><small>${esc(item.gameId)}</small></td><td><span class="tag amber">${item.inputMode==='synthetic'?'SYNTHETIC':'SUPPLIED / UNVERIFIED'}</span><p>HOLD · ${(item.probability*100).toFixed(1)}%</p></td><td>${esc(new Date(item.recordedAt).toLocaleString())}</td><td><button data-receipt-id="${item.id}" ${state.busy?'disabled':''}>View receipt #${item.id}</button></td></tr>`).join('')}</tbody></table></div>`:'<p>No saved receipts loaded.</p>'}
  ${state.nextCursor?'<div class="actions"><button id="receiving60-more-records">Load older receipts</button></div>':''}
  ${state.openRecord?`<div class="statusbox"><h3>Saved receipt #${state.openRecord.id}</h3><p>This saved record is separate from the current form.</p><div class="actions"><button id="receiving60-download-saved">Download saved receipt #${state.openRecord.id}</button></div><details><summary>Inspect saved request and score</summary><pre>${esc(JSON.stringify(state.openRecord,null,2))}</pre></details></div>`:''}</div></section>`;
}
export function receiving60Input(target) {
  if (target.form?.id!=='receiving60-form' || state.busy) return;
  if (target.name==='history') { state.importText=target.value; return; }
  if (target.dataset.historyField) {
    const rows=JSON.parse(state.draft.history), key=target.dataset.historyField;
    const value=target.value;
    rows[Number(target.dataset.historyIndex)][key]=key==='receivingYards'?(value===''?null:Number(value)):key.endsWith('At')?(value?utc(value):''):value;
    state.draft.history=JSON.stringify(rows); state.importText=JSON.stringify(rows,null,2);
    const editor=document.querySelector('[name=history]'); if (editor) editor.value=state.importText;
  } else if (target.name in state.draft) state.draft[target.name]=target.value;
  else return;
  invalidate();
  // Keep focus and the caret in the input while immediately invalidating stale output.
  const result=document.querySelector('#receiving60-result');
  if (result) result.textContent='Inputs changed. Calculate again to obtain a matching receipt.';
  document.querySelector('#receiving60-form .error')?.remove();
}
function downloadReceipt(receipt,filename) {
  const url=URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'}));
  const a=document.createElement('a'); a.href=url; a.download=filename; a.click();
  setTimeout(()=>URL.revokeObjectURL(url),1000);
}
export async function receiving60Click(button) {
  if (state.busy) return;
  if (button.id==='receiving60-clear') { state.draft=fresh(); state.importText='[]'; state.inputMode='supplied'; invalidate(); redraw(); }
  if (button.id==='receiving60-add-game' || button.dataset.historyRemove!==undefined) {
    const rows=JSON.parse(state.draft.history);
    if (button.id==='receiving60-add-game' && rows.length<500) rows.push({playerId:state.draft.playerId,gameId:'',kickoffAt:'',resolvedAt:'',observedAt:'',receivingYards:null});
    else if (button.dataset.historyRemove!==undefined) rows.splice(Number(button.dataset.historyRemove),1);
    state.draft.history=JSON.stringify(rows); state.importText=JSON.stringify(rows,null,2); invalidate(); redraw();
  }
  if (button.id==='receiving60-import') {
    try {
      const rows=JSON.parse(state.importText);
      if (!Array.isArray(rows) || rows.length>500 || rows.some(row=>!row || typeof row!=='object' || Array.isArray(row))) throw Error('Import an array of up to 500 game objects');
      state.draft.history=JSON.stringify(rows); invalidate();
    } catch(error) { invalidate(); state.error=error.message; }
    redraw();
  }
  if (button.id==='receiving60-sample') {
    const now=new Date(), stamp=date=>date.toISOString();
    state.draft={...fresh(),playerId:'synthetic-player',gameId:'synthetic-future',history:JSON.stringify([21,14,7].map((days,i)=>({
      playerId:'synthetic-player',gameId:`synthetic-past-${days}`,kickoffAt:stamp(new Date(now-days*86400000)),
      resolvedAt:stamp(new Date(now-days*86400000+3*3600000)),observedAt:stamp(new Date(now-days*86400000+4*3600000)),receivingYards:[-5,60,80][i]})),null,2)};
    state.inputMode='synthetic'; state.importText=state.draft.history; invalidate(); redraw();
  }
  if (button.id==='receiving60-download' && state.result && state.request) {
    const receipt={exportedAt:new Date().toISOString(),inputMode:state.inputMode,request:state.request,readiness:state.readiness,
      scoreReceipt:state.result,note:'Research only. Supplied history is unverified. No EV or live approval.'};
    downloadReceipt(receipt,'edgeboard-receiving60-receipt.json');
  }
  if (button.id==='receiving60-save' && state.result?.estimateAvailable && state.request && !state.savedId) {
    state.busy=true; redraw();
    try {
      const record=await request('/api/receiving60/receipts',{inputMode:state.inputMode,input:state.request,expectedArtifactSha256:state.result.canonicalArtifactSha256});
      state.savedId=record.id; state.openRecord=record; await loadReceipts();
    } catch(error) { state.error=error.message; }
    finally { state.busy=false; redraw(); }
  }
  if (button.id==='receiving60-refresh-records' || button.id==='receiving60-more-records') {
    state.busy=true; redraw(); await loadReceipts(button.id==='receiving60-more-records'?state.nextCursor:null); state.busy=false; redraw();
  }
  if (button.dataset.receiptId) {
    state.busy=true; redraw();
    try { state.openRecord=await request('/api/receiving60/receipts/'+button.dataset.receiptId); }
    catch(error) { state.receiptsError=error.message; }
    finally { state.busy=false; redraw(); }
  }
  if (button.id==='receiving60-download-saved' && state.openRecord) downloadReceipt(state.openRecord,`edgeboard-receiving60-saved-${state.openRecord.id}.json`);
}
export async function submitReceiving60() {
  if (state.busy) return;
  invalidate();
  try {
    const d=state.draft;
    const history=JSON.parse(d.history);
    if (!Array.isArray(history)) throw Error('Prior game history must be a JSON array');
    const payload={request:{playerId:d.playerId,gameId:d.gameId,position:d.position,kickoffAt:utc(d.kickoffAt),decisionAt:utc(d.decisionAt),
      league:'NFL',seasonType:'REG',period:'FULL_GAME',stat:'receiving_yards',threshold:60,comparison:'>='},history};
    state.busy=true; redraw();
    try { state.result=await request('/api/receiving60/predict',payload); }
    catch(error) { if (error.payload?.apiVersion==='v1') state.result=error.payload; else throw error; }
    state.request=payload;
  } catch(error) { state.error=error.message; }
  finally { state.busy=false; redraw(); }
}
