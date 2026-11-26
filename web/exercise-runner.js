(() => {
  if (document.documentElement.classList.contains('pt-device-only')) return;
  const dialog=document.createElement('dialog');
  dialog.className='cyber-range-dialog defensive-soc-dialog';
  dialog.innerHTML='<form method="dialog"><button class="cyber-close" aria-label="Close">×</button></form><h2>Defensive SOC Training</h2><p>Guided availability exercise in a separate modeled network. No real traffic or changes to your active topology. Training path: CLIENT → ACCESS → APP (modeled HTTP).</p><button id="exerciseRefresh">Refresh</button> <button id="exerciseRestart" hidden>Restart attempt</button> <button id="exerciseExport" disabled>Export report</button><p id="exerciseStatus" role="status"></p><section id="exerciseContent"><label>Exercise <select id="exerciseTemplate"></select></label><p id="exerciseStage"></p><p id="exerciseScore"></p><h3>Observed evidence</h3><div class="soc-table-wrap"><table><thead><tr><th>Phase</th><th>Event ID</th><th>Check</th><th>Source → target</th><th>Sim. time (s)</th><th>Outcome</th><th>Reason / HTTP status</th></tr></thead><tbody id="exerciseRows"></tbody></table></div><p id="exerciseCase"></p><ul id="exerciseCriteria"></ul><div id="exerciseInputs"></div><button id="exerciseNext">Start exercise</button><h3>Training progress</h3><p id="exerciseProgress"></p><ul id="exerciseGroups"></ul><label>Archived report <select id="exerciseArchive"></select></label><button id="exerciseArchiveExport" disabled>Export selected report</button><h3>Enterprise training library</h3><p>DNS availability and redundant DNS resilience · multi-department analyst assessments</p><button id="enterpriseLibraryLaunch">Open enterprise lab</button> <button id="enterpriseHistoryRefresh">Refresh history</button><p id="enterpriseHistoryStatus" role="status"></p><label>Enterprise report retention <input id="enterpriseHistoryLimit" type="number" min="1" max="24" value="12"></label><button id="enterpriseHistorySave" disabled>Apply retention</button><div id="enterpriseHistoryGroups"></div><label>Completed enterprise report <select id="enterpriseHistorySelect"></select></label><button id="enterpriseHistoryExport" disabled>Export enterprise report</button></section>';
  document.body.append(dialog);
  const el=id=>dialog.querySelector('#'+id);
  const phases={idle:'Ready to start',baseline_verified:'Baseline verified',fault_observed:'Availability fault observed',acknowledged:'Incident acknowledged',assessed:'Assessment recorded',restored:'Service restored; verify recovery evidence',recovery_monitored:'Three recovery samples collected',recovery_verified:'Recovery verified',completed:'Exercise completed'};
  const labels={start:'Start exercise',inject_fault:'Introduce modeled availability fault',acknowledge:'Acknowledge observed incident',assess:'Submit evidence-backed assessment',restore:'Restore modeled component and run checks',monitor_recovery:'Run 10-second simulated recovery monitoring',verify_recovery:'Verify latest recovery observations',complete:'Complete and resolve'};
  const roles=()=>current.assessment_roles||{};
  let current=null,busy=false;
  function options(select,entries){
    for(const [value,label] of entries){const o=document.createElement('option');o.value=value;o.textContent=label;select.append(o);}
  }
  function field(parent,id,label,entries){
    const wrapper=document.createElement('label');wrapper.htmlFor=id;wrapper.textContent=label+' ';
    const select=document.createElement('select');select.id=id;options(select,[['','Choose evidence…'],...entries]);wrapper.append(select);parent.append(wrapper);return select;
  }
  function evidenceOptions(checks,includeRecovery){
    const entries=[];
    for(const [phase,c] of Object.entries(checks)){
      if(phase.startsWith('recovery')&&!includeRecovery)continue;
      for(const kind of [c.component?'component':'interface','icmp','http']){
        const event=c[kind];entries.push([String(event.id),phase+' · E'+event.id+' · '+event.protocol+' · '+event.source+' → '+event.destination+' · '+event.outcome]);
      }
    }
    return entries;
  }
  function render(){
    const report=current.report, checks=report?.observations||{};
    const template=el('exerciseTemplate'), chosen=template.value;template.replaceChildren();options(template,current.library.map(t=>[t.id,t.title+' · '+t.difficulty]));template.value=current.library.some(t=>t.id===chosen)?chosen:(report?.template||current.library[0].id);
    const p=current.progress;el('exerciseProgress').textContent=p.retained+' completed reports retained · '+p.evicted+' evicted';el('exerciseGroups').replaceChildren();for(const g of p.by_template){const li=document.createElement('li');li.textContent=g.template+' / rubric v'+g.version+' · '+g.completed+' attempts · best '+g.best+' · latest '+g.latest+' · change '+(g.change>=0?'+':'')+g.change;el('exerciseGroups').append(li);}
    const archive=el('exerciseArchive'),old=archive.value;archive.replaceChildren();options(archive,[['','Select report…'],...p.attempts.slice().reverse().map(r=>[r.run_id,'Attempt '+r.attempt+' · '+r.template+' · '+r.points+'/100'])]);if(p.attempts.some(r=>r.run_id===old))archive.value=old;el('exerciseArchiveExport').disabled=!archive.value;
    el('exerciseStage').textContent=(current.attempt?'Attempt '+current.attempt+' · ':'')+(phases[current.status]||current.status)+(report?' · '+report.template:'')+(report?.monitoring?.passed?' · '+report.monitoring.span_simulated_seconds+' simulated seconds sampled':'');
    el('exerciseScore').textContent=report?'Assessment: '+report.score.points+' / '+report.score.maximum+(report.complete?' · final':' · provisional'):'';
    el('exerciseRestart').hidden=!report;
    el('exerciseExport').disabled=!report;
    el('exerciseRows').replaceChildren();
    for(const [phase,c] of Object.entries(checks)){
      for(const kind of [c.component?'component':'interface','icmp','http']){
        const e=c[kind], row=document.createElement('tr');
        for(const value of [phase,'E'+e.id,e.protocol,e.source+' → '+e.destination,Number(e.sim_time.toFixed(3)),e.outcome,e.reason||(kind==='http'&&c.http_status!==null?'HTTP '+c.http_status:'—')]){
          const cell=document.createElement('td');cell.textContent=String(value);row.append(cell);
        }
        el('exerciseRows').append(row);
      }
    }
    const incident=report?.incidents.cases[0];
    el('exerciseCase').textContent=incident?'Incident '+incident.id+' · '+incident.status+' · '+(incident.ack_event_id?'acknowledged':'not acknowledged'):'No incident yet.';
    el('exerciseCriteria').replaceChildren();
    if(report)for(const criterion of report.score.criteria){
      const li=document.createElement('li');li.textContent=(criterion.met?'Met: ':'Pending / not met: ')+criterion.id.replaceAll('_',' ')+' ('+criterion.points+')';el('exerciseCriteria').append(li);
    }
    const inputs=el('exerciseInputs');inputs.replaceChildren();
    if(current.next_action==='assess'){
      field(inputs,'exerciseDiagnosis','Diagnosis',Object.entries(current.diagnoses));
      const choices=evidenceOptions(checks,false);
      for(const [role,label] of Object.entries(roles()))field(inputs,'exerciseRef-'+role,label,choices);
      const label=document.createElement('label');label.htmlFor='exerciseNote';label.textContent='Analyst note (linked to the failed check)';inputs.append(label);
      const note=document.createElement('textarea');note.id='exerciseNote';note.maxLength=500;note.rows=3;inputs.append(note);
    }
    if(current.next_action==='verify_recovery'){
      const choices=evidenceOptions(checks,true);
      field(inputs,'exerciseRecoveryIcmp','Recovery connectivity',choices);
      field(inputs,'exerciseRecoveryHttp','Recovery HTTP health',choices);
    }
    const next=el('exerciseNext');next.hidden=!current.next_action;next.textContent=labels[current.next_action]||'';
  }
  async function request(body){
    if(busy)return;
    busy=true;el('exerciseContent').inert=true;el('exerciseRestart').disabled=true;el('exerciseRefresh').disabled=true;el('exerciseExport').disabled=true;
    el('exerciseStatus').textContent='Working…';
    try{
      const response=await fetch(body?'/api/cyber-range/exercises/action':'/api/cyber-range/exercises',body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:{});
      const result=await response.json();
      if(!response.ok||!result.ok){
        if(result.exercise&&(!current||result.exercise.run_id!==current.run_id||result.exercise.step!==current.step)){current=result.exercise;render();}
        throw Error(result.output||result.error||'Exercise request failed');
      }
      current=body?result.exercise:result;render();el('exerciseStatus').textContent='Ready';
    }catch(e){
      if(!body){current=null;el('exerciseContent').hidden=true;el('exerciseRestart').hidden=true;el('exerciseArchiveExport').disabled=true;}
      el('exerciseStatus').textContent=e.message;
    }finally{
      busy=false;el('exerciseContent').inert=false;el('exerciseRefresh').disabled=false;el('exerciseRestart').disabled=false;
      el('exerciseExport').disabled=!current?.report;
      if(current)el('exerciseContent').hidden=false;
    }
  }
  function context(action){return action==='start'?{action}:{action,run_id:current.run_id,step:current.step};}
  el('exerciseNext').onclick=()=>{
    if(!current?.next_action)return;
    const action=current.next_action,body=context(action),checks=current.report?.observations;
    if(action==='acknowledge')body.event_id=current.primary_failure_event_id;
    if(action==='start')body.template=el('exerciseTemplate').value;
    if(action==='assess'){
      body.diagnosis=el('exerciseDiagnosis').value;body.note=el('exerciseNote').value.trim();
      body.references=Object.fromEntries(Object.keys(roles()).map(role=>[role,Number(el('exerciseRef-'+role).value)]));
      if(!body.diagnosis||!body.note||Object.values(body.references).some(v=>!v)){el('exerciseStatus').textContent='Choose a diagnosis, fill every evidence role and enter a note.';return;}
    }
    if(action==='verify_recovery'){
      body.icmp_event_id=Number(el('exerciseRecoveryIcmp').value);body.http_event_id=Number(el('exerciseRecoveryHttp').value);
      if(!body.icmp_event_id||!body.http_event_id){el('exerciseStatus').textContent='Select both recovery evidence IDs.';return;}
    }
    request(body);
  };
  el('exerciseRestart').onclick=()=>{if(current?.report&&confirm(current.report.complete?'Start the selected exercise? Your completed report is archived.':'Replace this incomplete attempt?'))request({...context('restart'),template:el('exerciseTemplate').value});};
  el('exerciseRefresh').onclick=()=>request();
  el('exerciseArchive').onchange=()=>{el('exerciseArchiveExport').disabled=!el('exerciseArchive').value;};
  el('exerciseArchiveExport').onclick=async()=>{const id=el('exerciseArchive').value;if(!id||busy)return;try{const response=await fetch('/api/cyber-range/exercises/report?run_id='+encodeURIComponent(id));const result=await response.json();if(!response.ok||!result.ok)throw Error(result.error||'Report unavailable');download(result.report);}catch(e){el('exerciseStatus').textContent=e.message;}};
  function download(report){const url=URL.createObjectURL(new Blob([JSON.stringify(report,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='soc-exercise-'+report.run_id+(report.complete?'-final':'-progress')+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);}
  el('exerciseExport').onclick=()=>{if(current?.report)download(current.report);};
  let enterpriseHistory=null,historyBusy=false;
  function renderEnterpriseHistory(){
    const h=enterpriseHistory;
    el('enterpriseHistoryStatus').textContent=h.retained+' completed assessments retained · '+h.evicted+' evicted · comparison by configuration and rubric';
    el('enterpriseHistoryLimit').value=h.limit;
    const groups=el('enterpriseHistoryGroups');groups.replaceChildren();
    for(const g of h.groups){
      const details=document.createElement('details'),summary=document.createElement('summary');
      summary.textContent=g.template+' · '+g.config.departments+' departments × '+g.config.hosts_per_department+' clients · rubric v'+g.version+' · '+g.completed+' attempts · first '+g.first+' · latest '+g.latest+' · best '+g.best+' · change '+(g.change>=0?'+':'')+g.change;
      details.append(summary);
      const list=document.createElement('ul');
      for(const c of g.criteria){const li=document.createElement('li');li.textContent=c.id.replaceAll('_',' ')+' · met '+c.met_count+'/'+g.completed+' · first '+(c.first_met?'met':'not met')+' → latest '+(c.latest_met?'met':'not met')+' · change '+(c.change>=0?'+':'')+c.change;list.append(li);}
      details.append(list);groups.append(details);
    }
    const select=el('enterpriseHistorySelect'),old=select.value;select.replaceChildren();
    options(select,[['','Select completed assessment…'],...h.attempts.slice().reverse().map(r=>[r.run_id,'#'+r.sequence+' · '+r.template+' · '+r.config.departments+'×'+r.config.hosts_per_department+' · '+r.points+'/100 · '+(r.completed_at||'date unavailable')])]);
    if(h.attempts.some(r=>r.run_id===old))select.value=old;
  }
  async function historyRequest(body){
    if(historyBusy)return;historyBusy=true;
    for(const id of ['enterpriseHistorySave','enterpriseHistoryRefresh','enterpriseHistoryExport','enterpriseHistoryLimit','enterpriseHistorySelect'])el(id).disabled=true;
    el('enterpriseHistoryStatus').textContent='Loading enterprise history…';
    try{
      if(body){
        const response=await fetch('/api/cyber-range/enterprise/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}),data=await response.json();
        if(!response.ok||!data.ok)throw Error(data.output||data.error||'Retention update failed');
      }
      const response=await fetch('/api/cyber-range/enterprise/archive'),data=await response.json();
      if(!response.ok||!data.ok)throw Error(data.error||'Enterprise history unavailable');
      enterpriseHistory=data;renderEnterpriseHistory();
    }catch(e){enterpriseHistory=null;el('enterpriseHistoryGroups').replaceChildren();el('enterpriseHistorySelect').replaceChildren();el('enterpriseHistoryStatus').textContent=e.message;}
    finally{historyBusy=false;el('enterpriseHistoryRefresh').disabled=false;el('enterpriseHistoryLimit').disabled=!enterpriseHistory;el('enterpriseHistorySave').disabled=!enterpriseHistory;el('enterpriseHistorySelect').disabled=!enterpriseHistory;el('enterpriseHistoryExport').disabled=!enterpriseHistory||!el('enterpriseHistorySelect').value;}
  }
  el('enterpriseLibraryLaunch').onclick=()=>{dialog.close();document.getElementById('enterpriseTrainingBtn').click();};
  el('enterpriseHistoryRefresh').onclick=()=>historyRequest();
  el('enterpriseHistorySave').onclick=()=>{
    if(!enterpriseHistory||historyBusy)return;
    const value=Number(el('enterpriseHistoryLimit').value);
    if(!Number.isInteger(value)||value<1||value>24){el('enterpriseHistoryStatus').textContent='Retention must be a whole number from 1 to 24.';return;}
    const remove=Math.max(0,enterpriseHistory.retained-value);
    if(remove&&!confirm('Evict '+remove+' oldest enterprise report(s)? Export them first if needed.'))return;
    historyRequest({action:'set_retention',limit:value,expected_limit:enterpriseHistory.limit});
  };
  el('enterpriseHistorySelect').onchange=()=>{el('enterpriseHistoryExport').disabled=historyBusy||!el('enterpriseHistorySelect').value;};
  el('enterpriseHistoryExport').onclick=async()=>{
    if(historyBusy||!enterpriseHistory)return;
    const id=el('enterpriseHistorySelect').value;if(!id)return;
    try{
      const response=await fetch('/api/cyber-range/enterprise/report?run_id='+encodeURIComponent(id)),data=await response.json();
      if(!response.ok||!data.ok)throw Error(data.error||'Report unavailable');
      const url=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'})),a=document.createElement('a');
      a.href=url;a.download='enterprise-'+id+'-final.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
    }catch(e){el('enterpriseHistoryStatus').textContent=e.message;}
  };
  document.getElementById('exerciseRunnerBtn').onclick=()=>{dialog.showModal();request();historyRequest();};
})();
