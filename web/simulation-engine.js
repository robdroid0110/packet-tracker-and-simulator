/* §§33–40. Scheduling, scenarios and captured events belong to NetworkLab. */
(() => {
'use strict';
const by=id=>document.getElementById(id),el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg'),use=document.createElementNS(svg.namespaceURI,'use');svg.classList.add('control-icon');svg.setAttribute('aria-hidden','true');use.setAttribute('href','/control-icons.svg#'+name);svg.append(use);return svg}
let busy=false,timer=null,source=null;
async function act(body){
 const r=await fetch('/api/simulation/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}),data=await r.json();
 if(!data.ok)throw Error(data.output||data.error);state=data.state;render();return data;
}
function run(body){return act(body).catch(error=>status(error.message))}
const inspector=el('dialog');inspector.id='ptPduInspector';inspector.setAttribute('aria-label','PDU Information');document.body.append(inspector);
function inspect(event){
 inspector.replaceChildren(el('h2','PDU Information — '+event.protocol));
 const tabs=el('div');tabs.setAttribute('role','tablist');const content=el('div');
 for(const [name,value] of [['OSI Model',event.osi],['Inbound PDU Details',event.headers],['Outbound PDU Details',{...event.headers,forwarding:event.detail}],['Event',event]]){
  const b=el('button',name);b.setAttribute('role','tab');b.onclick=()=>{content.replaceChildren(el('pre',JSON.stringify(value,null,2)))};tabs.append(b);
 }
 inspector.append(tabs,content);tabs.firstChild.click();const close=el('button','Close');close.onclick=()=>inspector.close();inspector.append(close);if(!inspector.open)inspector.showModal();
}
const editor=el('dialog');editor.id='ptPduEditor';editor.setAttribute('aria-label','Create Complex PDU');document.body.append(editor);
function field(form,key,label,value,type='text',options=null){const row=el('label',label),input=el(options?'select':'input');input.name=key;if(!options)input.type=type;if(type==='number')input.step='any';
 if(options)for(const option of options){const item=el('option',option);item.value=option;input.append(item)}input.value=value;row.append(input);form.append(row);return input}
function editPdu(src,dst,record=null,complex=true){
 editor.replaceChildren(el('h2',record?'Edit PDU':complex?'Create Complex PDU':'Add Simple PDU'));
 const form=el('form');form.method='dialog';const p=record||{};
 const sourceField=field(form,'source','Source device',p.source||src,'text',Object.keys(state.devices));
 field(form,'destination','Destination device',p.destination||dst||'','text',['',...Object.keys(state.devices)]);
 field(form,'destination_ip','Destination IP (optional with device)',p.destination_ip||'');
 const protocolField=field(form,'protocol','Application',p.protocol||'ICMP','text',['ICMP','TCP','UDP','DNS','HTTP','HTTPS','FTP','SFTP','SMTP','POP3','IMAP','SNMP','SSH','TELNET','TFTP','FINGER','NETBIOS','OTHER']);
 if(complex){for(const [key,label,value] of [['ttl','TTL',32],['tos','ToS',0],['size','Size (bytes)',100],['sequence','Sequence',1],['source_port','Source Port',1025],['destination_port','Destination Port',0]])field(form,key,label,p[key]??value,'number');field(form,'source_ip','Source IP (optional)',p.source_ip||'');field(form,'interface','Source interface (optional)',p.interface||'','text',['',...Object.keys(state.devices[p.source||src]?.interfaces||{})]);field(form,'url','HTTP URL (optional)',p.url||'')}
 if(complex){const ports={ICMP:0,TCP:0,UDP:0,DNS:53,HTTP:80,HTTPS:443,FTP:21,SFTP:22,SMTP:25,POP3:110,IMAP:143,SNMP:161,SSH:22,TELNET:23,TFTP:69,FINGER:79,NETBIOS:137,OTHER:0};protocolField.onchange=()=>form.elements.destination_port.value=ports[protocolField.value];sourceField.onchange=()=>{const select=form.elements.interface;select.replaceChildren();for(const name of ['',...Object.keys(state.devices[sourceField.value]?.interfaces||{})]){const o=el('option',name);o.value=name;select.append(o)}}}
 field(form,'start','Send time (seconds)',p.start||0,'number');field(form,'interval','Period (0 = one shot)',p.interval||0,'number');field(form,'color','PDU color',p.color||'#17a2b8','color');
 const error=el('p');error.setAttribute('role','alert');form.append(error);const cancel=el('button','Cancel');cancel.type='button';cancel.onclick=()=>editor.close();const save=el('button','Save PDU');save.type='submit';form.append(cancel,save);
 form.onsubmit=async event=>{event.preventDefault();save.disabled=true;try{const body={action:record?'pdu_edit':'pdu_add',...(record?{id:record.id}:{})};for(const input of form.querySelectorAll('[name]'))body[input.name]=input.type==='number'?Number(input.value):input.value;await act(body);editor.close()}catch(exc){error.textContent=exc.message}finally{save.disabled=false}};
 editor.append(form);if(!editor.open)editor.showModal();
}
const previousClick=nodeClick;nodeClick=function(event,name){
 if(activeTool==='pdu-complex'){editPdu(name,null,null,true);return}
 if(activeTool==='pdu-simple'){
  if(!source){source=name;status('Choose PDU destination');return}
  const origin=source;source=null;run({action:'pdu_add',source:origin,destination:name,protocol:'ICMP'});return;
 }
 return previousClick(event,name);
};
const oldRealtime=by('realtimeBtn').onclick,oldSimulation=by('simulationBtn').onclick;
by('realtimeBtn').onclick=()=>{oldRealtime();run({action:'mode',mode:'realtime'})};
by('simulationBtn').onclick=()=>{oldSimulation();run({action:'mode',mode:'simulation'})};
by('stepForwardBtn').onclick=()=>run({action:'step'}).then(data=>{const event=data?.state?.simulation.last_event;if(event)document.dispatchEvent(new CustomEvent('packettracker:packet-step',{detail:event}))});
by('stepBackBtn').onclick=()=>run({action:'back'});
by('playBtn').onclick=()=>run({action:'play',enabled:!state.simulation.playing});
by('resetSimulationBtn').onclick=()=>run({action:'reset'});
const constant=document.querySelector('.sim-reset-row input[type=checkbox]');if(constant)constant.onchange=()=>run({action:'preferences',constant_delay:constant.checked});
const speed=document.querySelector('.sim-speed');if(speed)speed.onchange=()=>run({action:'preferences',speed:Number(speed.value)});
function speedFill(){if(speed)speed.style.setProperty('--sim-speed-progress',((Number(speed.value)-1)/99*100)+'%')}
if(speed)speed.addEventListener('input',speedFill);
document.querySelector('.sim-filter-title').replaceChildren(icon('filter'),el('span','Event List Filters — Visible Events'));
const scenarios=document.querySelector('#scenarioPane select');
scenarios.onchange=()=>run({action:'scenario_select',id:scenarios.value});
by('scenarioNewBtn').onclick=()=>{const name=prompt('Scenario name','New Scenario');if(name)run({action:'scenario_add',name})};
by('scenarioDeleteBtn').onclick=()=>run({action:'scenario_delete',id:state.simulation.active});
document.querySelector('#scenarioPane .info-button').onclick=()=>{const s=state.simulation.scenarios[state.simulation.active];const description=prompt('Scenario description',s.description);if(description!==null)run({action:'scenario_edit',id:state.simulation.active,name:s.name,description})};
let displaySignature='';
function display(){
 const s=state.simulation;if(!s)return;
 simulationMode=s.mode==='simulation';
 for(const [id,active] of [['realtimeBtn',!simulationMode],['simulationBtn',simulationMode]]){
  by(id).classList.toggle('active',active);by(id).setAttribute('aria-pressed',String(active));
 }
 by('playBtn').setAttribute('aria-pressed',String(s.playing));
 by('playBtn').setAttribute('aria-label',s.playing?'Pause':'Play');
 by('playBtn').title=s.playing?'Pause':'Play';
 by('playBtn').querySelector('use')?.setAttribute('href','/control-icons.svg#'+(s.playing?'pause':'play'));
 const panelPlay=document.querySelector('[data-sim-step="play"]');
 panelPlay.setAttribute('aria-pressed',String(s.playing));panelPlay.setAttribute('aria-label',s.playing?'Pause':'Play');panelPlay.title=s.playing?'Pause':'Play';
 panelPlay.querySelector('use').setAttribute('href','/control-icons.svg#'+(s.playing?'pause':'play'));
 by('eventListBtn').setAttribute('aria-expanded',String(!by('simulationPanel').classList.contains('hidden')));

 clockRunning=false;clockOffset=Math.round(s.master_time*1000);by('clock').textContent=formatClock(clockOffset);
 if(document.documentElement.classList.contains('pt-device-only'))return;
 const signature=JSON.stringify([s.mode,s.active,s.cursor,s.events.length,s.last_event?.seq,s.filters,s.speed,s.constant_delay,s.playing,s.pdus,s.scenarios]);
 if(signature===displaySignature)return;
 displaySignature=signature;
 scenarios.replaceChildren();for(const [id,scenario] of Object.entries(s.scenarios)){const option=el('option',scenario.name);option.value=id;scenarios.append(option)}scenarios.value=s.active;
 const host=by('eventList');host.replaceChildren();
 for(const [id,p] of Object.entries(s.pdus)){
  if(p.scenario!==s.active||p.user_created===false)continue;
  const row=el('div');row.className='pdu-row';
  for(const [text,fn] of [['▶',()=>run({action:'pdu_fire',id})],[p.status],[p.source],[p.destination||p.destination_ip],[p.protocol],[p.color,()=>{const color=prompt('PDU #RRGGBB color',p.color);if(color)run({action:'pdu_edit',id,color})}],[String(p.start)],[p.interval?'Y':'N'],[id],['Edit',()=>editPdu(p.source,p.destination,{id,...p})],['Delete',()=>run({action:'pdu_delete',id})]]){
   const cell=el(fn?'button':'span',text);if(fn)cell.onclick=fn;row.append(cell);
  }host.append(row);
 }
 const pane=by('simulationEvents');pane.replaceChildren();
 for(const event of s.events.slice(0,s.cursor)){
  if(!s.filters.includes(event.protocol))continue;
  const row=el('button');row.className='sim-event-row pt-captured-row';row.title=event.detail;row.style.borderLeft='4px solid '+event.color;
  for(const text of ['◉',event.time.toFixed(6),event.source,event.destination,event.protocol])row.append(el('span',text));row.onclick=()=>inspect(event);pane.append(row);
 }
 if(!pane.children.length){const empty=el('div');empty.className='sim-empty';empty.append(icon('info'),el('p',s.cursor?'No captured events match these filters.':'No packet events captured yet. Send a Simple PDU or browse a simulated server.'));pane.append(empty)}
 by('captureCount').textContent=String(s.cursor);
 document.querySelector('.sim-filter-summary').textContent=s.filters.length?'('+s.filters.join(', ')+')':'No protocols selected';
 const filters=document.querySelector('.sim-filters');filters.replaceChildren();
 for(const protocol of ['ARP','ICMP','TCP','UDP','DNS','HTTP','HTTPS','FTP','TFTP','SNMP','SSH','STP','OSPF','DHCP','RADIUS','TACACS','NTP','PTP','SYSLOG','CAPWAP','CIP','MODBUS','RIP','SMTP','POP3','IMAP','SFTP','TELNET','ICMPv6','DHCPv6']){const label=el('label'),check=el('input');check.type='checkbox';check.checked=s.filters.includes(protocol);check.onchange=()=>run({action:'preferences',filters:check.checked?[...s.filters,protocol]:s.filters.filter(p=>p!==protocol)});label.append(check,document.createTextNode(protocol));filters.append(label)}
 const hud=by('ptPacketEnvelope'),event=s.last_event;
 if(hud&&event&&simulationMode){const d=state.devices[event.destination];hud.hidden=!d;if(d){hud.style.left=(d.x+70)+'px';hud.style.top=(d.y+1)+'px';hud.textContent='✉ '+event.protocol;hud.style.color=event.color;hud.onclick=()=>inspect(event)}}
 if(constant)constant.checked=s.constant_delay;if(speed)speed.value=s.speed;speedFill();
}
const filterButtons=document.querySelectorAll('.sim-filter-actions button');
if(filterButtons[0]){filterButtons[0].id='editSimFiltersBtn';filterButtons[0].prepend(icon('edit'));filterButtons[0].setAttribute('aria-controls','simProtocolFilters');filterButtons[0].setAttribute('aria-expanded','false');filterButtons[0].onclick=()=>{const filters=document.querySelector('.sim-filters');filters.hidden=!filters.hidden;filterButtons[0].setAttribute('aria-expanded',String(!filters.hidden))}};
if(filterButtons[1]){filterButtons[1].id='allSimFiltersBtn';filterButtons[1].prepend(icon('eye'))}
if(filterButtons[1])filterButtons[1].onclick=()=>run({action:'preferences',filters:state.simulation.filters.length?[]:['ARP','ICMP','TCP','UDP','DNS','HTTP','HTTPS','FTP','TFTP','SNMP','SSH','STP','OSPF','DHCP','RADIUS','TACACS','NTP','PTP','SYSLOG','CAPWAP','CIP','MODBUS','RIP','SMTP','POP3','IMAP','SFTP','TELNET','ICMPv6','DHCPv6']});
const legend=el('button','PDU Color Legend');legend.id='simLegendBtn';legend.prepend(icon('layers'));legend.onclick=async()=>{const s=await (await fetch('/api/simulation')).json();inspector.replaceChildren(el('h2','PDU Color Legend'));for(const [protocol,color] of Object.entries(s.legend)){const row=el('p',protocol+' '+color);row.style.borderLeft='20px solid '+color;inspector.append(row)}const close=el('button','Close');close.onclick=()=>inspector.close();inspector.append(close);inspector.showModal()};document.querySelector('.sim-filter-actions').append(legend);
const oldRender=render;render=function(){oldRender();display()};
async function tick(){
 if(busy||document.hidden||document.documentElement.classList.contains('pt-device-only')||window.ptPointerActive)return;busy=true;
 try{
  if(state.simulation?.mode==='simulation'&&state.simulation.playing||state.simulation?.mode==='realtime'){
   const before=state.simulation?.last_event?.seq;const r=await fetch('/api/simulation'),s=await r.json();
   if(s.ok&&!window.ptPointerActive){state.simulation=s;if(s.last_event?.seq!==before){await fetchState();const event=state.simulation.last_event;if(event)document.dispatchEvent(new CustomEvent('packettracker:packet-step',{detail:event}))}else display()}
  }
 }catch(error){status(error.message)}finally{busy=false}
}
timer=setInterval(tick,300);window.addEventListener('beforeunload',()=>clearInterval(timer));
window.PacketTrackerSimulation={act,inspect,editPdu,display};display();
})();
