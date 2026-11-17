/* Section 14: accessible Logical Workspace List.
   Every mutation uses POST /api/workspace-list/action, never local-only topology edits. */
(() => {
'use strict';
const g=id=>document.getElementById(id),safe=x=>esc(String(x??''));
let view=null,cluster='root',picked=null,linkId=null,busy=false,search='',linkSearch='',focusReturn=null;
const outer=document.createElement('div');
outer.id='ptWorkspaceList';outer.hidden=true;
outer.setAttribute('role','dialog');outer.setAttribute('aria-modal','true');
outer.setAttribute('aria-labelledby','ptWorkspaceListTitle');
outer.innerHTML=[
 '<section class="pt-wl-window">',
 '<header class="pt-wl-header"><strong id="ptWorkspaceListTitle">Workspace List — Logical Network</strong>',
 '<button id="wlUndo" type="button">Undo</button><button id="wlRedo" type="button">Redo</button>',
 '<button id="wlRefresh">Refresh</button><button id="wlClose" aria-label="Close Workspace List">×</button></header>',
 '<nav class="pt-wl-navigation" aria-label="Cluster path">',
 '<button id="wlParent" type="button">Show Parent Cluster</button><span id="wlPath">Root</span><span id="wlCounts"></span></nav>',
 '<main class="pt-wl-main">',
 '<section class="pt-wl-devices" aria-labelledby="wlDevicesTitle">',
 '<div class="pt-wl-bar"><h3 id="wlDevicesTitle">Devices &amp; Clusters</h3>',
 '<input id="wlSearch" placeholder="Filter devices" aria-label="Filter devices">',
 '<button id="wlAdd">Add Device</button><button id="wlRemove" disabled>Remove Device</button></div>',
 '<div class="pt-wl-table-wrap"><table class="pt-wl-table"><thead><tr>',
 '<th scope="col">Select</th><th scope="col">Device / Cluster</th>',
 '<th scope="col">Model</th><th scope="col">Power</th>',
 '<th scope="col">X</th><th scope="col">Y</th><th scope="col">Action</th>',
 '</tr></thead><tbody id="wlDevices"></tbody></table></div>',
 '<form class="pt-wl-form" id="wlAddForm" hidden>',
 '<strong>Add Device</strong>',
 '<label>Category<select id="wlCategory"></select></label>',
 '<label>Model<select id="wlModel"></select></label>',
 '<label>Device name<input id="wlName" required pattern="[A-Za-z][A-Za-z0-9_-]*" maxlength="31"></label>',
 '<label>X<input id="wlX" type="number" min="0" max="10000" required value="180"></label>',
 '<label>Y<input id="wlY" type="number" min="0" max="10000" required value="160"></label>',
 '<button type="submit">Add</button><button type="button" id="wlAddCancel">Cancel</button></form>',
 '<section class="pt-wl-modules" aria-labelledby="wlModulesTitle">',
 '<h3 id="wlModulesTitle">Physical Module Layout</h3><p id="wlModulesNote">Select a device.</p>',
 '<div class="pt-wl-table-wrap"><table class="pt-wl-table"><thead><tr>',
 '<th scope="col">Slot path</th><th scope="col">Installed module</th>',
 '<th scope="col">Interfaces</th></tr></thead><tbody id="wlModules"></tbody></table></div>',
 '</section></section>',
 '<section class="pt-wl-links" aria-labelledby="wlLinksTitle">',
 '<div class="pt-wl-bar"><h3 id="wlLinksTitle">Links</h3>',
 '<input id="wlLinkSearch" placeholder="Filter links" aria-label="Filter links">',
 '<button id="wlAddLink">Add Link</button><button id="wlRemoveLink" disabled>Remove Link</button></div>',
 '<div class="pt-wl-table-wrap"><table class="pt-wl-table"><thead><tr>',
 '<th scope="col">Select</th><th scope="col">Cable</th><th scope="col">Source device:port</th>',
 '<th scope="col">Destination device:port</th><th scope="col">Light</th>',
 '</tr></thead><tbody id="wlLinks"></tbody></table></div>',
 '<form class="pt-wl-form" id="wlLinkForm" hidden>',
 '<strong>Add Link</strong>',
 '<label>Cable<select id="wlCable"><option value="auto">Auto</option>',
 '<option value="copper-straight">Copper straight-through</option>',
 '<option value="copper-cross">Copper crossover</option></select></label>',
 '<label>Source<select id="wlSource"></select></label>',
 '<label>Source port<select id="wlSourcePort"></select></label>',
 '<label>Destination<select id="wlTarget"></select></label>',
 '<label>Destination port<select id="wlTargetPort"></select></label>',
 '<button type="submit">Connect</button><button type="button" id="wlLinkCancel">Cancel</button>',
 '<p>Choose compatible media on both ports. Console is control-only; serial DCE requires a clock rate.</p></form>',
 '</section></main>',
 '<footer class="pt-wl-footer"><span id="wlStatus" role="status" aria-live="polite">',
 'Select a device or link to edit.</span><button id="wlDone">Close</button></footer></section>'
].join('');
document.body.append(outer);
const tell=(text,err=false)=>{g('wlStatus').textContent=text;g('wlStatus').classList.toggle('error',err)};
function close(){
 outer.hidden=true;
 if(focusReturn?.isConnected)focusReturn.focus?.();
 else if(focusReturn?.classList?.contains('node'))window.PacketTrackerCanvas?.focus(focusReturn.dataset.name);
}
async function getJson(url,opts){
 const r=await fetch(url,opts),data=await r.json();
 if(!r.ok||data.ok===false)throw Error(data.error||data.output||'Workspace API error');
 return data;
}
async function refresh(syncState=false){
 try{
  if(syncState){state=await getJson('/api/state');render()}
  const query=new URLSearchParams({cluster});
  if(picked)query.set('device',picked);
  view=await getJson('/api/workspace-list?'+query.toString());
 }catch(e){
  if(picked){picked=null;return refresh(syncState)}
  tell(e.message,true);return;
 }
 draw();
}
async function edit(action){
 if(busy)return false;busy=true;
 try{
  const reply=await getJson('/api/workspace-list/action',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({...action,cluster,selected_device:picked})
  });
  state=reply.state;render();tell(reply.output||'Saved');
  if(action.action==='remove_device')picked=null;
  if(action.action==='remove_link')linkId=null;
  await refresh();return true;
 }catch(e){tell(e.message,true);return false}
 finally{busy=false}
}
function open(){
 focusReturn=document.activeElement;
 outer.hidden=false;cluster='root';picked=null;linkId=null;
 search=linkSearch='';g('wlSearch').value=g('wlLinkSearch').value='';
 g('wlAddForm').hidden=g('wlLinkForm').hidden=true;
 refresh(true).then(()=>g('wlSearch').focus());
}
function draw(){
 if(!view)return;
 g('wlParent').disabled=cluster==='root';
 g('wlCounts').textContent=view.devices.length+' devices · '+view.clusters.length+' clusters · '+view.links.length+' links';
 g('wlPath').innerHTML=view.path.map((p,i)=>
  (i?' / ':'')+'<button type="button" data-path="'+safe(p.id)+'"'+
   (p.id===cluster?' aria-current="page"':'')+'>'+safe(p.name)+'</button>'
 ).join('');
 drawDevices();drawModules();drawLinks();
}
function drawDevices(){
 const rows=[];
 for(const c of view.clusters){
  if(search&&!((c.name+' '+c.id).toLowerCase().includes(search)))continue;
  rows.push('<tr class="pt-wl-cluster"><td>—</td><th scope="row"><button data-enter="'+safe(c.id)+'">'+
   '▣ '+safe(c.name)+'</button></th><td>Cluster ('+c.count+')</td><td>—</td><td>—</td><td>—</td>'+
   '<td><button data-enter="'+safe(c.id)+'">Enter</button></td></tr>');
 }
 for(const d of view.devices){
  if(search&&!((d.name+' '+d.kind+' '+d.model).toLowerCase().includes(search)))continue;
  rows.push('<tr data-device-row="'+safe(d.name)+'" title="'+safe(d.name+' · '+d.model+' · '+d.kind+(d.powered?' · power on':' · power off'))+'"'+(picked===d.name?' class="selected"':'')+'>'+
   '<td><input type="radio" name="wlDevice" value="'+safe(d.name)+'"'+(picked===d.name?' checked':'')+
   ' aria-label="Select '+safe(d.name)+'"></td>'+
   '<th scope="row"><button data-open="'+safe(d.name)+'" title="Open device window">'+safe(d.name)+'</button></th>'+
   '<td>'+safe(catalog.models[d.model]?.label||d.model)+'</td>'+
   '<td><button data-power="'+safe(d.name)+'" aria-label="Power '+(d.powered?'off ':'on ')+safe(d.name)+'">'+
   (d.powered?'On':'Off')+'</button></td>'+
   '<td><input type="number" min="0" max="10000" data-coordinate="x" data-name="'+safe(d.name)+'" value="'+safe(d.x)+'" aria-label="X coordinate for '+safe(d.name)+'"></td>'+
   '<td><input type="number" min="0" max="10000" data-coordinate="y" data-name="'+safe(d.name)+'" value="'+safe(d.y)+'" aria-label="Y coordinate for '+safe(d.name)+'"></td>'+
   '<td><button data-pick="'+safe(d.name)+'">Select</button> <button data-open="'+safe(d.name)+'">Open</button></td></tr>');
 }
 g('wlDevices').innerHTML=rows.join('')||'<tr><td colspan="7">No visible devices or clusters.</td></tr>';
 g('wlRemove').disabled=!picked;
}
function drawModules(){
 const body=g('wlModules'),detail=view.selected;
 if(!detail){
  g('wlModulesNote').textContent='Select a device to see its slots.';
  body.innerHTML='<tr><td colspan="3">No device selected.</td></tr>';return;
 }
 g('wlModulesNote').textContent=detail.device+' · '+
  (detail.powered?'Power ON: turn off to modify modules':'Power OFF: expansion slots are editable');
 body.innerHTML=detail.slots.map(slot=>{
  let module=safe(slot.module||'Empty');
  if(slot.editable){
   const choices=[['','Empty'],...slot.available.map(k=>[k,k+' (simulated)'])];
   module='<select data-slot="'+safe(slot.slot)+'" aria-label="Module in '+safe(slot.slot)+
    '"'+(detail.powered?' disabled title="Power off the device before editing"':'')+'>'+
    choices.map(([val,label])=>'<option value="'+safe(val)+'"'+
     ((slot.module||'')===val?' selected':'')+'>'+safe(label)+'</option>').join('')+'</select>';
  }
  return '<tr><th scope="row">'+safe(slot.slot)+'</th><td>'+module+'</td><td>'+
   safe(slot.interfaces.join(', ')||'—')+'</td></tr>';
 }).join('');
 if(detail.slots.length===1)g('wlModulesNote').textContent+=' · No simulated expansion slots for this model.';
}
function drawLinks(){
 const rows=[];
 for(const l of view.links){
  if(linkSearch&&!((l.cable+' '+l.source+' '+l.destination+' '+l.status).toLowerCase().includes(linkSearch)))continue;
  rows.push('<tr'+(l.id===linkId?' class="selected"':'')+'>'+
   '<td><input type="radio" name="wlLink" value="'+safe(l.id)+'"'+(l.id===linkId?' checked':'')+
   ' aria-label="Select link '+safe(l.source)+' to '+safe(l.destination)+'"></td>'+
   '<td>'+safe(l.cable)+'</td><td>'+safe(l.source)+'</td><td>'+safe(l.destination)+'</td>'+
   '<td><i class="pt-wl-led '+(l.up?'up':'down')+'" aria-hidden="true"></i>'+
   (l.up?'Green (up)':'Red (down)')+'<small title="'+safe(l.status)+'">'+safe(l.status)+'</small></td></tr>');
 }
 g('wlLinks').innerHTML=rows.join('')||'<tr><td colspan="5">No visible links.</td></tr>';
 g('wlRemoveLink').disabled=!linkId;
}
function categoryModels(){
 const categories=[...new Set((catalog.groups||[]).filter(group=>group.models?.length).map(group=>group.category))];
 g('wlCategory').innerHTML=categories.map(c=>'<option value="'+safe(c)+'">'+safe(c)+'</option>').join('');
 selectModels();
}
function selectModels(){
 const category=g('wlCategory').value;
 const ids=[...new Set((catalog.groups||[]).filter(group=>group.category===category).flatMap(group=>group.models))];
 g('wlModel').innerHTML=ids.filter(id=>catalog.models?.[id]).map(id=>
  '<option value="'+safe(id)+'">'+safe(catalog.models[id].label)+
  (catalog.models[id].support==='engine'?'':' (catalog only)')+'</option>').join('');
 proposeName();
}
function proposeName(){
 const model=catalog.models?.[g('wlModel').value];if(!model)return;
 const prefix=model.kind==='router'?'R':model.kind==='switch'?'SW':model.kind==='pc'?'PC':model.kind==='server'?'Server':'DEV';
 let i=1;while(state.devices[prefix+i])i++;
 g('wlName').value=prefix+i;
 const n=Object.keys(state.devices).length;
 g('wlX').value=120+(n%7)*140;g('wlY').value=110+Math.floor(n/7)*100;
}
function openConnect(){
 if(view.devices.length<2)return tell('Two visible devices required to connect.',true);
 g('wlLinkForm').hidden=false;
 const options=view.devices.map(d=>'<option value="'+safe(d.name)+'">'+safe(d.name)+'</option>').join('');
 g('wlSource').innerHTML=options;g('wlTarget').innerHTML=options;
 g('wlTarget').selectedIndex=1;
 refreshPorts();g('wlSource').focus();
}
function refreshPorts(){
 const used=new Set((state.links||[]).flatMap(l=>[l.a_device+':'+l.a_if,l.b_device+':'+l.b_if]));
 for(const [devSelect,portSelect] of [['wlSource','wlSourcePort'],['wlTarget','wlTargetPort']]){
  const device=g(devSelect).value;
  const ports=Object.values(state.devices[device]?.interfaces||{}).filter(p=>!p.parent&&!used.has(device+':'+p.name));
  g(portSelect).innerHTML=ports.map(p=>'<option value="'+safe(p.name)+'">'+safe(p.name)+'</option>').join('');
 }
}
async function pick(name){picked=name;await refresh()}
g('wlClose').onclick=g('wlDone').onclick=close;
g('wlUndo').onclick=()=>edit({action:'undo'});
g('wlRedo').onclick=()=>edit({action:'redo'});
g('wlRefresh').onclick=()=>refresh(true);
g('wlParent').onclick=()=>{
 if(!view||view.cluster==='root')return;
 cluster=view.parent;picked=null;linkId=null;refresh();
};
g('wlPath').addEventListener('click',event=>{
 const button=event.target.closest('[data-path]');
 if(!button)return;cluster=button.dataset.path;picked=null;linkId=null;refresh();
});
g('wlSearch').oninput=event=>{search=event.target.value.toLowerCase();drawDevices()};
g('wlLinkSearch').oninput=event=>{linkSearch=event.target.value.toLowerCase();drawLinks()};
g('wlAdd').onclick=()=>{g('wlAddForm').hidden=false;categoryModels();g('wlName').focus()};
g('wlCategory').onchange=selectModels;g('wlModel').onchange=proposeName;
g('wlAddCancel').onclick=()=>{g('wlAddForm').hidden=true};
g('wlAddForm').onsubmit=async event=>{
 event.preventDefault();
 const name=g('wlName').value.trim(),x=g('wlX').valueAsNumber,y=g('wlY').valueAsNumber;
 if(!name||!Number.isFinite(x)||!Number.isFinite(y))return tell('Enter valid name and coordinates.',true);
 if(await edit({action:'add_device',name,model:g('wlModel').value,x,y})){
  g('wlAddForm').hidden=true;picked=name;refresh();
 }
};
g('wlRemove').onclick=async()=>{
 if(!picked)return;
 if(!confirm('Delete '+picked+' and all connected cables?'))return;
 await edit({action:'remove_device',device:picked});
};
g('wlDevices').addEventListener('click',event=>{
 const target=event.target.closest('button,input[type=radio]');
 if(!target){
  const row=event.target.closest('[data-device-row]');
  if(row&&!event.target.closest('input,select')){close();openDevice(row.dataset.deviceRow)}
  return;
 }
 if(target.dataset.enter){
  cluster=target.dataset.enter;picked=null;linkId=null;refresh();return;
 }
 if(target.dataset.open){const name=target.dataset.open;close();openDevice(name);return}
 if(target.dataset.pick){pick(target.dataset.pick);return}
 if(target.dataset.power){
  const device=target.dataset.power,entry=view.devices.find(d=>d.name===device);
  if(entry)edit({action:'power_device',device,powered:!entry.powered});
  return;
 }
 if(target.matches('input[type=radio]'))pick(target.value);
});
g('wlDevices').addEventListener('change',async event=>{
 const input=event.target.closest('[data-coordinate]');
 if(!input)return;
 const item=view.devices.find(x=>x.name===input.dataset.name);
 const value=input.valueAsNumber,axis=input.dataset.coordinate;
 if(!item||!Number.isFinite(value)||value<0||value>10000){
  tell('Coordinates must be between 0 and 10000.',true);drawDevices();return;
 }
 await edit({action:'move_device',device:item.name,
  x:axis==='x'?value:item.x,y:axis==='y'?value:item.y});
});
g('wlModules').addEventListener('change',async event=>{
 const input=event.target.closest('[data-slot]');
 if(!input||!picked)return;
 const before=view.selected?.slots.find(s=>s.slot===input.dataset.slot)?.module||'';
 const ok=await edit({action:'set_module',device:picked,slot:input.dataset.slot,module:input.value||null});
 if(!ok)input.value=before;
});
g('wlAddLink').onclick=openConnect;
g('wlLinkCancel').onclick=()=>{g('wlLinkForm').hidden=true};
g('wlSource').onchange=g('wlTarget').onchange=refreshPorts;
g('wlLinkForm').onsubmit=async event=>{
 event.preventDefault();
 const a_device=g('wlSource').value,a_if=g('wlSourcePort').value;
 const b_device=g('wlTarget').value,b_if=g('wlTargetPort').value;
 if(!a_if||!b_if)return tell('No free physical interface on one or both devices.',true);
 if(await edit({action:'add_link',a_device,a_if,b_device,b_if,cable:g('wlCable').value})){
  g('wlLinkForm').hidden=true;
 }
};
g('wlLinks').addEventListener('change',event=>{
 const input=event.target.closest('input[name=wlLink]');
 if(!input)return;linkId=input.value;drawLinks();
});
g('wlRemoveLink').onclick=async()=>{
 const link=view.links.find(l=>l.id===linkId);if(!link)return;
 if(!confirm('Disconnect '+link.source+' and '+link.destination+'?'))return;
 await edit({action:'remove_link',device:link.a_device,iface:link.a_if});
};
outer.addEventListener('pointerdown',event=>{if(event.target===outer)close()});
document.addEventListener('keydown',event=>{
 if(outer.hidden)return;
 if(event.key==='Escape'){
  event.preventDefault();event.stopImmediatePropagation();close();return;
 }
 if((event.ctrlKey||event.metaKey)&&!event.altKey&&
    !event.target.matches('input,textarea,select,[contenteditable]')){
  const key=event.key.toLowerCase();
  const action=key==='z'?(event.shiftKey?'redo':'undo'):(key==='y'?'redo':null);
  if(action){event.preventDefault();event.stopImmediatePropagation();edit({action});return}
 }
 if(event.key==='Tab'){
  const focusable=[...outer.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled])')]
   .filter(el=>!el.closest('[hidden]')&&el.getClientRects().length>0);
  if(!focusable.length)return;
  const first=focusable[0],last=focusable[focusable.length-1];
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
 }
},true);
const launcher=document.createElement('button');
launcher.id='ptWorkspaceListButton';
launcher.type='button';
launcher.title='Workspace List: keyboard accessible device and link tables';
launcher.textContent='Workspace List';
launcher.onclick=open;
document.querySelector('#workspaceTabs .workspace-left')?.append(launcher);
window.PacketTrackerList={open,close,refresh,edit,get view(){return view}};
})();
