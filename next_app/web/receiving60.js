const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const localTime = date => new Date(date.getTime() - date.getTimezoneOffset()*60000).toISOString().slice(0,16);
const utc = value => { const date=new Date(value); if (!value || !Number.isFinite(date.getTime())) throw Error('Enter valid kickoff and decision times'); return date.toISOString(); };
const fresh = () => ({playerId:'',gameId:'',position:'WR',kickoffAt:localTime(new Date(Date.now()+7*86400000)),decisionAt:localTime(new Date()),history:'[]'});
const state = {draft:fresh(),inputMode:'supplied',busy:false,error:'',result:null,request:null,readiness:null,readinessError:''};
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
function invalidate() { state.result=null; state.request=null; state.error=''; }
export async function loadReceiving60Readiness() {
  try { state.readiness=await request('/api/receiving60/readiness'); state.readinessError=''; }
  catch(error) { state.readiness=null; state.readinessError=error.message; }
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
    <label class="full">Prior game history (JSON array)<textarea name="history" spellcheck="false" rows="12" required aria-describedby="history-help">${esc(d.history)}</textarea></label>
  </div><p id="history-help" class="subtle">Supply 3–500 prior games for this player, with unique game IDs and integer receivingYards. Each row needs kickoffAt, resolvedAt and observedAt in UTC ending in Z. Observed time must precede the decision. Include the complete relevant recorded history; it is not fetched automatically.</p>
  <div class="actions"><button type="submit" class="primary">${state.busy?'Calculating…':'Calculate research estimate'}</button><button type="button" id="receiving60-sample">Load synthetic example</button><button type="button" id="receiving60-clear">Clear inputs</button></div></fieldset>
  ${state.error?`<div class="error" role="alert">${esc(state.error)}</div>`:''}
  <p class="subtle">Inputs stay in this tab until you reload. They are sent to your app to score and are not entered into a server ledger.</p></form></section>
  <section class="panel"><div class="panelhead"><h2>Research receipt</h2><span class="tag amber">HOLD</span></div><div class="panelbody">
  <div id="receiving60-result" aria-live="polite">${r?`<span class="tag ${state.inputMode==='synthetic'?'amber':''}">${state.inputMode==='synthetic'?'SYNTHETIC EXAMPLE':'UNVERIFIED SUPPLIED HISTORY'}</span>
    <div class="research-estimate">${r.estimateAvailable?`${(r.probability*100).toFixed(1)}%`:'No estimate'}</div><p>${r.estimateAvailable?'Conditional model estimate · 60+ receiving yards':'The model abstained from scoring these inputs.'}</p>
    <div class="statusbox"><strong>${esc(reasons[r.reason] || 'The model cannot score these inputs. Inspect the full receipt for the reason.')}</strong><br>${esc(r.interpretation)}</div>
    <div class="listrow"><span>Uncertainty interval</span><span>Unavailable</span></div><div class="listrow"><span>Expected value</span><span>Unavailable</span></div><div class="listrow"><span>Live approval</span><span>Not established</span></div>
    <details><summary>Inspect full score receipt</summary><pre>${esc(JSON.stringify(r,null,2))}</pre></details>
    <div class="actions"><button id="receiving60-download">Download research receipt ↓</button></div>`:'<p>Enter player history or load the clearly labeled synthetic example. Editing inputs clears the previous result.</p>'}</div>
  <div class="spacer"></div><h3>Installed model</h3><p class="subtle">${state.readiness?`Artifact integrity: ${state.readiness.artifactVerified?'verified':'failed'} · ${esc(state.readiness.modelVersion)}`:state.readinessError?`Readiness unavailable: ${esc(state.readinessError)}`:'Checking model readiness…'}</p>
  <p class="subtle">Calibration was selected in-sample. The 2025 diagnostic is consumed. A new forward validation period is required.</p></div></section></div>`;
}
export function receiving60Input(target) {
  if (target.form?.id!=='receiving60-form' || state.busy || !(target.name in state.draft)) return;
  state.draft[target.name]=target.value;
  invalidate();
  // Keep focus and the caret in the input while immediately invalidating stale output.
  const result=document.querySelector('#receiving60-result');
  if (result) result.textContent='Inputs changed. Calculate again to obtain a matching receipt.';
  document.querySelector('#receiving60-form .error')?.remove();
}
export function receiving60Click(button) {
  if (state.busy) return;
  if (button.id==='receiving60-clear') { state.draft=fresh(); state.inputMode='supplied'; invalidate(); redraw(); }
  if (button.id==='receiving60-sample') {
    const now=new Date(), stamp=date=>date.toISOString();
    state.draft={...fresh(),playerId:'synthetic-player',gameId:'synthetic-future',history:JSON.stringify([21,14,7].map((days,i)=>({
      playerId:'synthetic-player',gameId:`synthetic-past-${days}`,kickoffAt:stamp(new Date(now-days*86400000)),
      resolvedAt:stamp(new Date(now-days*86400000+3*3600000)),observedAt:stamp(new Date(now-days*86400000+4*3600000)),receivingYards:[-5,60,80][i]})),null,2)};
    state.inputMode='synthetic'; invalidate(); redraw();
  }
  if (button.id==='receiving60-download' && state.result && state.request) {
    const receipt={exportedAt:new Date().toISOString(),inputMode:state.inputMode,request:state.request,readiness:state.readiness,
      scoreReceipt:state.result,note:'Research only. Supplied history is unverified. No EV or live approval.'};
    const url=URL.createObjectURL(new Blob([JSON.stringify(receipt,null,2)],{type:'application/json'}));
    const a=document.createElement('a'); a.href=url; a.download='edgeboard-receiving60-receipt.json'; a.click();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
  }
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
