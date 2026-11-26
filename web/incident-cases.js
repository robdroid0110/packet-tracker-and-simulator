(() => {
  if (document.documentElement.classList.contains('pt-device-only')) return;
  const dialog=document.createElement('dialog');
  dialog.className='cyber-range-dialog defensive-soc-dialog';
  dialog.innerHTML='<form method="dialog"><button class="cyber-close" aria-label="Close">×</button></form><h2>Incident Investigation</h2><p>Cases are based on modeled connectivity observations, not evidence of an attack.</p><button id="incidentRefresh">Refresh</button> <button id="incidentExport" disabled>Export cases</button><p id="incidentStatus" role="status"></p><label>Case <select id="incidentSelect"></select></label><section id="incidentDetail" hidden><h3 id="incidentHeading"></h3><p id="incidentScore"></p><ul id="incidentCriteria"></ul><div class="soc-table-wrap"><table><thead><tr><th>ID</th><th>Time (s)</th><th>Source</th><th>Destination</th><th>Outcome / reason</th></tr></thead><tbody id="incidentRows"></tbody></table></div><p id="incidentMeta"></p><button id="incidentAck">Acknowledge latest failure</button> <button id="incidentVerify">Verify observed recovery</button> <button id="incidentResolve">Resolve case</button><h3>Analyst notes</h3><ul id="incidentNotes"></ul><label>Evidence <select id="incidentEvidence"></select></label><label for="incidentNoteText">Note</label><textarea id="incidentNoteText" maxlength="500" rows="3" placeholder="Record an observation or hypothesis tied to evidence."></textarea><button id="incidentNoteAdd">Save note</button> <button id="incidentNoteRemove">Remove note for selected event</button></section>';
  document.body.append(dialog);
  const el=id=>dialog.querySelector('#'+id);
  let data=null,selected=null,busy=false;
  const status=msg=>{el('incidentStatus').textContent=msg;};
  const current=()=>data?.cases.find(c=>c.id===selected);
  function item(parent,text){const li=document.createElement('li');li.textContent=text;parent.append(li);}
  function option(parent,value,text){const o=document.createElement('option');o.value=value;o.textContent=text;parent.append(o);}
  function render(){
    const list=el('incidentSelect');list.replaceChildren();
    for(const c of [...data.cases].reverse())option(list,c.id,c.id+' · '+c.status+' · '+c.evidence[0].source+' → '+c.evidence[0].destination);
    if(!current())selected=data.cases.at(-1)?.id||null;
    if(selected)list.value=selected;
    const c=current();el('incidentDetail').hidden=!c;el('incidentExport').disabled=false;
    if(!c)return;
    const failure=[...c.evidence].reverse().find(e=>e.outcome==='failure'), latest=c.evidence.at(-1), locked=c.status==='resolved';
    el('incidentHeading').textContent=c.id+' · '+c.status;
    el('incidentScore').textContent='Workflow score: '+c.score.points+' / '+c.score.maximum+' — not a grade of note accuracy.';
    el('incidentCriteria').replaceChildren();for(const criterion of c.score.criteria)item(el('incidentCriteria'),(criterion.met?'Met: ':'Pending: ')+criterion.id.replaceAll('_',' ')+' ('+criterion.points+')');
    el('incidentRows').replaceChildren();
    const evidence=el('incidentEvidence'), previous=evidence.value;evidence.replaceChildren();
    for(const e of c.evidence){
      const row=document.createElement('tr');
      for(const value of [e.id,e.sim_time,e.source,e.destination,e.outcome+(e.reason?' / '+e.reason:'')]){const cell=document.createElement('td');cell.textContent=String(value);row.append(cell);}
      el('incidentRows').append(row);option(evidence,e.id,'Event '+e.id+' · '+e.outcome);
    }
    evidence.value=c.evidence.some(e=>String(e.id)===previous)?previous:String(failure.id);
    el('incidentMeta').textContent='Latest failure: '+failure.id+' · Acknowledged: '+(c.ack_event_id??'no')+' · Verified recovery: '+(c.recovery_event_id??'no')+' · Older unpinned evidence omitted: '+c.omitted;
    el('incidentAck').disabled=locked||c.ack_event_id===failure.id;
    el('incidentVerify').disabled=locked||latest.outcome!=='success'||c.recovery_event_id===latest.id;
    el('incidentResolve').disabled=locked||c.status!=='recovered'||c.ack_event_id!==failure.id||!c.notes.some(n=>n.event_id===failure.id);
    el('incidentNotes').replaceChildren();
    for(const n of c.notes)item(el('incidentNotes'),'Event '+n.event_id+': '+n.text);
    el('incidentNoteAdd').disabled=locked;el('incidentNoteRemove').disabled=locked;el('incidentNoteText').disabled=locked;
  }
  async function request(body){
    if(busy)return;
    busy=true;dialog.setAttribute('aria-busy','true');el('incidentSelect').disabled=true;el('incidentDetail').inert=true;
    try{
      const response=await fetch(body?'/api/cyber-range/incidents/action':'/api/cyber-range/incidents',body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:{});
      const result=await response.json();
      if(!response.ok||!result.ok){if(result.incidents){data=result.incidents;render();}throw Error(result.output||result.error||'Incident request failed');}
      data=body?result.incidents:result;render();
      status(data.cases.length+' cases · '+data.skipped+' additional case openings skipped at capacity');
      if(body?.action==='add_note')el('incidentNoteText').value='';
    }catch(e){if(!body){data=null;selected=null;el('incidentDetail').hidden=true;el('incidentExport').disabled=true;el('incidentSelect').replaceChildren();}status(e.message);}finally{busy=false;dialog.removeAttribute('aria-busy');el('incidentSelect').disabled=false;el('incidentDetail').inert=false;}
  }
  function send(action,event_id,extra={}){if(!current())return;request({action,case_id:selected,...(event_id===undefined?{}:{event_id}),...extra});}
  document.getElementById('incidentCasesBtn').onclick=()=>{dialog.showModal();request();};
  el('incidentRefresh').onclick=()=>request();
  el('incidentSelect').onchange=()=>{selected=el('incidentSelect').value;el('incidentNoteText').value='';render();};
  el('incidentAck').onclick=()=>send('acknowledge',[...current().evidence].reverse().find(e=>e.outcome==='failure').id);
  el('incidentVerify').onclick=()=>send('verify_recovery',current().evidence.at(-1).id);
  el('incidentResolve').onclick=()=>send('resolve');
  el('incidentEvidence').onchange=()=>{el('incidentNoteText').value=current()?.notes.find(n=>String(n.event_id)===el('incidentEvidence').value)?.text||'';};
  el('incidentNoteAdd').onclick=()=>send('add_note',Number(el('incidentEvidence').value),{note:el('incidentNoteText').value.trim()});
  el('incidentNoteRemove').onclick=()=>send('remove_note',Number(el('incidentEvidence').value));
  el('incidentExport').onclick=()=>{
    if(!data)return;const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));
    const a=document.createElement('a');a.href=url;a.download='modeled-incident-cases.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
  };
})();
