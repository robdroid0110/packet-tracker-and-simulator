(() => {
  if(document.documentElement.classList.contains('pt-device-only'))return;
  const dialog=document.createElement('dialog');
  dialog.className='cyber-range-dialog defensive-soc-dialog';
  dialog.innerHTML='<form method="dialog"><button class="cyber-close" aria-label="Close">×</button></form><h2>Enterprise availability lab</h2><p>Private modeled topology. One shared DNS dependency, with direct IP checks as independent controls. No host network changes.</p><button id="enterpriseRefresh">Refresh</button> <button id="enterpriseHistoryLink">Training library / history</button> <button id="enterpriseExport" disabled>Export report</button><p id="enterpriseStatus" role="status"></p><section id="enterpriseContent"><label>Exercise <select id="enterpriseMode"><option value="assessment">DNS outage assessment</option><option value="resilience">Redundant DNS resilience</option></select></label><label>Departments <select id="enterpriseDepartments"><option>2</option><option selected>3</option></select></label><label>Workstations per department <select id="enterpriseHosts"><option>1</option><option selected>2</option></select></label><button id="enterpriseRestart" hidden>Restart / apply configuration</button><h3 id="enterpriseStage">Ready</h3><p id="enterpriseTopology"></p><ul id="enterpriseSegments"></ul><h3>Service dependencies</h3><p id="enterpriseDependencies"></p><h3>Impact and recovery</h3><p id="enterpriseComponent"></p><p id="enterpriseImpact"></p><p id="enterpriseMonitoring"></p><h3>Correlated incident</h3><p id="enterpriseParent"></p><p id="enterpriseCases"></p><ul id="enterpriseChildren"></ul><div class="soc-table-wrap"><table><thead><tr><th>Phase</th><th>Client</th><th>DNS resolution</th><th>Portal by name</th><th>Direct HTTP</th><th>App ICMP</th></tr></thead><tbody id="enterpriseRows"></tbody></table></div><h3 id="enterpriseAssessmentTitle" hidden>Analyst assessment</h3><p id="enterpriseScore"></p><ul id="enterpriseCriteria"></ul><div id="enterpriseInputs"></div><p id="enterpriseConclusion"></p><p id="enterpriseNote"></p><button id="enterpriseNext">Start and verify baseline</button></section>';
  document.body.append(dialog);
  const el=id=>dialog.querySelector('#'+id);
  const labels={observe_failover:'Observe primary outage and failover',observe_interruption:'Observe secondary interruption',observe_partial:'Observe partial recovery',monitor_unstable:'Monitor intermittent relapse',start:'Start and verify baseline',inject_fault:'Introduce modeled DNS interface outage',restore:'Restore DNS interface and check dependencies',verify_recovery:'Sample recovery at +5s and +10s',complete:'Close parent incident and complete',acknowledge:'Acknowledge parent incident',assess:'Submit analyst assessment',resolve:'Resolve parent with recovery evidence'};
  const stages={failover_observed:'Failover observed',interruption_observed:'Both resolvers unavailable',partial_recovery:'Partial recovery observed',unstable_recovery:'Unstable recovery detected',idle:'Ready to start',baseline_verified:'Baseline verified',fault_observed:'Dependency failure observed',acknowledged:'Parent acknowledged',assessed:'Assessment submitted',restored:'Initial recovery observed',recovery_verified:'Recovery samples passed',completed:'Exercise completed'};
  let current=null,busy=false,configuredRun=null;
  const config=()=>({departments:Number(el('enterpriseDepartments').value),hosts_per_department:Number(el('enterpriseHosts').value)});
  function select(parent,id,label,options){
    const wrapper=document.createElement('label');wrapper.textContent=label+' ';
    const field=document.createElement('select');field.id=id;wrapper.append(field);parent.append(wrapper);
    for(const [value,text] of [['','Choose…'],...options]){const o=document.createElement('option');o.value=value;o.textContent=text;field.append(o);}
    return field;
  }
  function evidenceChoices(r,phases){
    const options=[];
    for(const phase of phases){const c=r.observations[phase];if(!c)continue;
      for(const e of [c.component,...c.clients.flatMap(x=>[x.dns,x.named_http.event,x.direct_http.event,x.app_icmp])]){
        options.push([String(e.id),phase+' · E'+e.id+' · '+e.source+' → '+e.destination+' · '+e.protocol+' · '+e.outcome]);
      }
    }return options;
  }
  function group(parent,title){const h=document.createElement('h4');h.textContent=title;parent.append(h);const div=document.createElement('div');parent.append(div);return div;}
  function check(parent,id,label){const l=document.createElement('label'),x=document.createElement('input');x.type='checkbox';x.id=id;l.append(x,document.createTextNode(' '+label));parent.append(l);return x;}
  function analystForm(r){
    const a=r?.analyst,area=el('enterpriseInputs');area.replaceChildren();
    el('enterpriseAssessmentTitle').hidden=!a;el('enterpriseScore').textContent=a?'Score: '+a.score.points+' / 100'+(r.complete?' · final':' · provisional'):'';
    el('enterpriseCriteria').replaceChildren();
    if(a)for(const c of a.score.criteria){const li=document.createElement('li');li.textContent=(c.met?'Met: ':'Not met / pending: ')+c.id.replaceAll('_',' ')+' ('+c.points+')';el('enterpriseCriteria').append(li);}
    el('enterpriseConclusion').textContent=a?.assessment?'Submitted diagnosis: '+a.assessment.diagnosis.replaceAll('_',' ')+' · claimed departments: '+(a.assessment.impact_departments.join(', ')||'none')+' · claimed workstations: '+a.assessment.impact_clients.length:'';
    el('enterpriseNote').textContent=a?.assessment?'Analyst note (E'+a.assessment.note_event_id+'): '+a.assessment.note:'';
    if(!a)return;
    const op=current.next_action,choices=evidenceChoices(r,['baseline','fault']);
    if(op==='acknowledge')select(area,'enterpriseAck','Shared fault event',choices);
    if(op==='assess'){
      select(area,'enterpriseDiagnosis','Root cause',[['dns_interface_down','Shared DNS server interface unavailable'],['app_service_down','Application service unavailable'],['routing_failure','Application routing unavailable'],['insufficient_evidence','Insufficient evidence']]);
      for(const [key,label] of Object.entries({component:'Failed component',dns:'DNS failure',direct_http:'Healthy direct HTTP control'}))select(area,'enterpriseRoot-'+key,label,choices);
      const dep=group(area,'Affected departments');for(const d of r.inventory.segments.filter(x=>x.name!=='SERVICES'))check(dep,'enterpriseDep-'+d.name,d.name);
      const clients=group(area,'Affected workstations and supporting evidence');
      for(const c of r.inventory.clients){
        const line=document.createElement('div');clients.append(line);
        const selected=check(line,'enterpriseClient-'+c.device,c.device);
        const base=select(line,'enterpriseBase-'+c.device,'Baseline portal',choices),fault=select(line,'enterpriseFault-'+c.device,'Fault portal',choices);
        base.disabled=fault.disabled=true;selected.onchange=()=>{base.disabled=fault.disabled=!selected.checked;};
      }
      select(area,'enterpriseNoteEvent','Note evidence',choices);
      const l=document.createElement('label');l.textContent='Analyst note';l.htmlFor='enterpriseNoteText';area.append(l);
      const note=document.createElement('textarea');note.id='enterpriseNoteText';note.maxLength=500;note.rows=3;area.append(note);
    }
    if(op==='resolve'){
      const recovery=evidenceChoices(r,['recovery','recovery_5s','recovery_10s']);
      select(area,'enterpriseDependencyRecovery','Latest dependency recovery',recovery);
      for(const c of r.inventory.clients){
        const row=group(area,c.device);
        select(row,'enterpriseRecoveryDns-'+c.device,'Latest DNS recovery',recovery);
        select(row,'enterpriseRecoveryHttp-'+c.device,'Latest portal recovery',recovery);
      }
    }
  }
  function render(){
    const r=current.report;
    if(r&&configuredRun!==r.run_id){
      el('enterpriseMode').value=r.version===3?'resilience':'assessment';
      el('enterpriseDepartments').value=String(r.config.departments);el('enterpriseHosts').value=String(r.config.hosts_per_department);configuredRun=r.run_id;
    }
    el('enterpriseStage').textContent=stages[current.status]||current.status;
    el('enterpriseRestart').hidden=!r;el('enterpriseExport').disabled=!r;
    el('enterpriseNext').hidden=!current.next_action;el('enterpriseNext').textContent=labels[current.next_action]||'';
    if(r?.version===3){renderResilience(r);return;}
    el('enterpriseRows').closest('table').querySelector('thead').innerHTML='<tr><th>Phase</th><th>Client</th><th>DNS resolution</th><th>Portal by name</th><th>Direct HTTP</th><th>App ICMP</th></tr>';
    el('enterpriseTopology').textContent=r?r.topology.devices+' modeled devices · '+r.topology.links+' links · '+r.inventory.segments.length+' routed segments':'Choose a configuration, then verify the baseline.';
    el('enterpriseSegments').replaceChildren();
    if(r)for(const s of r.inventory.segments){const li=document.createElement('li');li.textContent=s.name+' · '+s.network+' · '+s.members.map(m=>m.device).join(', ');el('enterpriseSegments').append(li);}
    el('enterpriseDependencies').textContent=r?'Workstations → '+r.inventory.hostname+' → DNS-SERVER and APP-SERVER. Direct application IP checks distinguish DNS failure from application failure.':'';
    el('enterpriseComponent').textContent=r?Object.entries(r.observations).map(([phase,c])=>phase+': DNS interface '+c.component.outcome+' (E'+c.component.id+')').join(' · '):'';
    const i=r?.impact;
    el('enterpriseImpact').textContent=i?i.affected_count+'/'+i.total_clients+' workstations affected · '+i.affected_departments.join(', ')+' · direct app controls '+(i.app_ip_controls_healthy?'healthy':'not healthy')+' · '+i.recovered_clients.length+' recovered':'No observed fault yet.';
    const m=r?.monitoring;
    el('enterpriseMonitoring').textContent=m?.samples.length?m.samples.length+' recovery samples · '+m.span_simulated_seconds+' simulated seconds · '+(m.passed?'passed':'awaiting verification'):'';
    const parent=r?.parent_incident;
    el('enterpriseParent').textContent=parent?'Parent '+parent.id+' · '+parent.status+' · '+(parent.acknowledged?'acknowledged · ':'')+'shared '+parent.dependency+' · E'+parent.fault_event_id+' · '+parent.verified_clients+'/'+parent.affected_clients+' clients verified · '+(parent.closure_ready?'recovery gate passed':'closure blocked'):'No correlated incident yet.';
    el('enterpriseCases').textContent=r?r.incidents.cases.length+' child service cases · recovery verified, not individually analyst-resolved. '+r.soc.retention.dropped+' SOC events evicted; phase evidence retained.':'';
    el('enterpriseChildren').replaceChildren();
    if(parent)for(const child of parent.children){const li=document.createElement('li');li.textContent=child.client+' · '+child.department+' · '+child.case_id+' · fault E'+child.failure_event_id+' · '+child.recovery_samples.filter(s=>s.healthy).length+'/3 healthy samples · '+(child.recovery_verified?'verified':'pending');el('enterpriseChildren').append(li);}
    el('enterpriseNext').disabled=['complete','resolve'].includes(current.next_action)&&!parent?.closure_ready;
    analystForm(r);
    el('enterpriseRows').replaceChildren();
    if(r)for(const [phase,c] of Object.entries(r.observations))for(const x of c.clients){
      const tr=document.createElement('tr');
      for(const v of [phase,x.client,...[x.dns,x.named_http.event,x.direct_http.event,x.app_icmp].map(e=>e.outcome+' · E'+e.id)]){const td=document.createElement('td');td.textContent=v;tr.append(td);}
      el('enterpriseRows').append(tr);
    }
  }
  const resilienceRoles={primary_failure:'Primary DNS failure',secondary_success:'Secondary DNS success',failover_portal:'Portal success during failover',partial_portal:'Portal success during partial recovery',partial_secondary_failure:'Secondary failure during partial recovery',relapse_portal_failure:'Portal failure during relapse',healthy_app_control:'Healthy direct app during relapse'};
  function resilienceChoices(r){
    const choices=[];
    for(const [phase,c] of Object.entries(r.observations)){
      for(const e of [...Object.values(c.components),...c.clients.flatMap(x=>[...Object.values(x.attempts),x.portal.event,x.direct.event])]){
        choices.push([String(e.id),phase+' · E'+e.id+' · '+e.source+' → '+e.destination+' · '+e.protocol+' · '+e.outcome]);
      }
    }
    return choices;
  }
  function renderResilience(r){
    const parent=r.parent_incident,m=r.monitoring,a=r.analyst,op=current.next_action;
    el('enterpriseTopology').textContent=r.topology.devices+' modeled devices · '+r.inventory.segments.length+' segments · two DNS resolvers';
    el('enterpriseSegments').replaceChildren();
    for(const seg of r.inventory.segments){const li=document.createElement('li');li.textContent=seg.name+' · '+seg.network+' · '+seg.members.map(x=>x.device).join(', ');el('enterpriseSegments').append(li);}
    el('enterpriseDependencies').textContent='Ordered primary / secondary DNS selection in the private simulator. Both resolvers share the services subnet.';
    el('enterpriseComponent').textContent=Object.entries(r.observations).map(([p,c])=>p+': primary '+c.components.primary.outcome+' (E'+c.components.primary.id+'), secondary '+c.components.secondary.outcome+' (E'+c.components.secondary.id+')').join(' · ');
    el('enterpriseImpact').textContent=parent?parent.affected_clients.length+' clients experienced portal interruption: '+parent.affected_clients.join(', '):'No interruption observed.';
    el('enterpriseMonitoring').textContent=(m.partial_recovery_detected?'Partial recovery detected · ':'')+(m.relapse_detected?'Relapse detected · ':'')+m.samples.length+'/3 stable samples · '+m.span_simulated_seconds.toFixed(2)+' simulated seconds · '+(m.passed?'passed':'closure blocked');
    el('enterpriseParent').textContent=parent?'Parent '+parent.id+' · '+parent.status+' · '+(parent.closure_ready?'closure ready':'closure blocked'):'No resilience incident yet.';
    el('enterpriseCases').textContent='Phase evidence is retained independently of the SOC journal. '+r.soc.retention.dropped+' SOC events evicted.';
    el('enterpriseChildren').replaceChildren();
    const table=el('enterpriseRows').closest('table');table.querySelector('thead').innerHTML='<tr><th>Phase</th><th>Client</th><th>Primary DNS</th><th>Secondary DNS</th><th>Selected resolver</th><th>Portal</th><th>Direct HTTP</th></tr>';
    el('enterpriseRows').replaceChildren();
    for(const [phase,c] of Object.entries(r.observations))for(const x of c.clients){
      const row=document.createElement('tr'),fmt=e=>e.outcome+' · E'+e.id;
      for(const v of [phase,x.client,fmt(x.attempts.primary),fmt(x.attempts.secondary),x.selected||'none',fmt(x.portal.event),fmt(x.direct.event)]){const td=document.createElement('td');td.textContent=v;row.append(td);}el('enterpriseRows').append(row);
    }
    el('enterpriseAssessmentTitle').hidden=false;el('enterpriseScore').textContent='Score: '+a.score.points+' / 100'+(r.complete?' · final':' · provisional');
    el('enterpriseCriteria').replaceChildren();
    for(const c of a.score.criteria){const li=document.createElement('li');li.textContent=(c.met?'Met: ':'Not met / pending: ')+c.id.replaceAll('_',' ')+' ('+c.points+')';el('enterpriseCriteria').append(li);}
    el('enterpriseConclusion').textContent=a.assessment?'Submitted diagnosis: '+a.assessment.diagnosis.replaceAll('_',' ')+' · affected clients: '+a.assessment.affected_clients.length:'';
    el('enterpriseNote').textContent=a.assessment?'Analyst note (E'+a.assessment.note_event_id+'): '+a.assessment.note:'';
    const area=el('enterpriseInputs');area.replaceChildren();const choices=resilienceChoices(r);
    if(op==='assess'){
      select(area,'resilienceDiagnosis','Diagnosis',[['redundancy_degraded','Intermittent DNS redundancy loss'],['app_outage','Application outage'],['routing_failure','Application routing failure'],['insufficient_evidence','Insufficient evidence']]);
      for(const [k,label] of Object.entries(resilienceRoles))select(area,'resilienceRef-'+k,label,choices);
      const affected=group(area,'Clients affected by interruption');for(const c of r.inventory.clients)check(affected,'resilienceClient-'+c.device,c.device);
      select(area,'resilienceNoteEvent','Note evidence',choices);
      const note=document.createElement('textarea');note.id='resilienceNote';note.rows=3;note.maxLength=500;area.append(note);
    }
    if(op==='resolve'){
      for(const role of ['primary','secondary'])select(area,'resilienceResolver-'+role,'Latest '+role+' component',choices);
      for(const c of r.inventory.clients){const row=group(area,c.device);for(const role of ['primary','secondary','portal'])select(row,'resilienceRecovery-'+c.device+'-'+role,'Latest '+role+' recovery',choices);}
    }
    if(op==='restore')el('enterpriseNext').textContent='Restore both modeled resolvers';
    if(op==='verify_recovery')el('enterpriseNext').textContent='Verify both resolvers across three samples';
    el('enterpriseNext').disabled=op==='resolve'&&!parent?.closure_ready;
  }
  function resiliencePayload(b,r){
    const n=id=>Number(el(id).value);
    if(b.action==='assess'){
      b.diagnosis=el('resilienceDiagnosis').value;b.references=Object.fromEntries(Object.keys(resilienceRoles).map(k=>[k,n('resilienceRef-'+k)]));
      b.affected_clients=r.inventory.clients.filter(c=>el('resilienceClient-'+c.device).checked).map(c=>c.device);
      b.note=el('resilienceNote').value.trim();b.note_event_id=n('resilienceNoteEvent');
    }
    if(b.action==='resolve'){
      b.resolver_refs=Object.fromEntries(['primary','secondary'].map(k=>[k,n('resilienceResolver-'+k)]));
      b.client_refs=Object.fromEntries(r.inventory.clients.map(c=>[c.device,Object.fromEntries(['primary','secondary','portal'].map(k=>[k,n('resilienceRecovery-'+c.device+'-'+k)]))]));
    }
    return b;
  }
  async function request(body){
    if(busy)return;
    busy=true;el('enterpriseContent').inert=true;el('enterpriseRefresh').disabled=true;el('enterpriseExport').disabled=true;el('enterpriseStatus').textContent='Working…';
    try{
      const response=await fetch(body?'/api/cyber-range/enterprise/action':'/api/cyber-range/enterprise',body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:{});
      const result=await response.json();
      if(!response.ok||!result.ok){
        if(result.enterprise&&(!current||result.enterprise.run_id!==current.run_id||result.enterprise.step!==current.step)){current=result.enterprise;render();}
        throw Error(result.output||result.error||'Enterprise request failed');
      }
      current=body?result.enterprise:result;render();el('enterpriseStatus').textContent='Ready';
    }catch(e){if(!body){current=null;el('enterpriseContent').hidden=true;}el('enterpriseStatus').textContent=e.message;}
    finally{busy=false;el('enterpriseContent').inert=false;el('enterpriseRefresh').disabled=false;el('enterpriseExport').disabled=!current?.report;if(current)el('enterpriseContent').hidden=false;}
  }
  function context(action){return {action,run_id:current.run_id,step:current.step};}
  el('enterpriseNext').onclick=()=>{
    const op=current?.next_action;if(!op)return;
    const b=op==='start'?{action:op,mode:el('enterpriseMode').value,config:config()}:context(op),r=current.report;
    if(r?.version===3){request(resiliencePayload(b,r));return;}
    const n=id=>Number(el(id).value);
    if(op==='acknowledge')b.event_id=n('enterpriseAck');
    if(op==='assess'){
      b.diagnosis=el('enterpriseDiagnosis').value;
      b.root_refs=Object.fromEntries(['component','dns','direct_http'].map(k=>[k,n('enterpriseRoot-'+k)]));
      b.impact_clients=r.inventory.clients.filter(c=>el('enterpriseClient-'+c.device).checked).map(c=>c.device);
      b.impact_departments=r.inventory.segments.filter(d=>d.name!=='SERVICES'&&el('enterpriseDep-'+d.name).checked).map(d=>d.name);
      b.impact_refs=Object.fromEntries(b.impact_clients.map(c=>[c,{baseline:n('enterpriseBase-'+c),fault:n('enterpriseFault-'+c)}]));
      b.note=el('enterpriseNoteText').value.trim();b.note_event_id=n('enterpriseNoteEvent');
    }
    if(op==='resolve'){
      b.dependency_event_id=n('enterpriseDependencyRecovery');
      b.recovery_refs=Object.fromEntries(r.inventory.clients.map(c=>[c.device,{dns:n('enterpriseRecoveryDns-'+c.device),http:n('enterpriseRecoveryHttp-'+c.device)}]));
    }
    request(b);
  };
  el('enterpriseRestart').onclick=()=>{if(current?.report&&confirm(current.report.complete&&current.report.version>=2?'Start another assessment? The completed report is archived.':'Replace this run? Export it first if needed.'))request({...context('restart'),mode:el('enterpriseMode').value,config:config()});};
  el('enterpriseRefresh').onclick=()=>request();
  el('enterpriseHistoryLink').onclick=()=>{dialog.close();document.getElementById('exerciseRunnerBtn').click();};
  el('enterpriseExport').onclick=()=>{if(!current?.report)return;const r=current.report,url=URL.createObjectURL(new Blob([JSON.stringify(r,null,2)],{type:'application/json'}));const a=document.createElement('a');a.href=url;a.download='enterprise-'+r.run_id+'.json';document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);};
  document.getElementById('enterpriseTrainingBtn').onclick=()=>{dialog.showModal();request();};
})();
