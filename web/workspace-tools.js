/* Help §§24–32: shared viewport, templates and accessible browser controls. */
(() => {
'use strict';
const by=id=>document.getElementById(id),e=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
async function mutate(body){
 const r=await fetch('/api/workspace-tools/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}),data=await r.json();
 if(!data.ok)throw Error(data.output||data.error);await fetchState();return data;
}
function context(){const c=window.PacketTrackerLogicalContext?.()||{mode:'logical',cluster:'root'};return {workspace:c.mode,location:c.mode==='physical'?(by('ptPhysicalWorkspace').dataset.location||'intercity'):c.cluster}}
const trigger=e('button','Workspace Tools');trigger.title='Viewport, Templates and Accessibility';trigger.id='ptWorkspaceToolsButton';document.querySelector('.secondary-toolbar').append(trigger);
const dialog=e('dialog');dialog.id='ptWorkspaceToolsDialog';dialog.setAttribute('aria-labelledby','ptToolsTitle');document.body.append(dialog);
function button(parent,text,fn){const b=e('button',text);b.type='button';b.onclick=async()=>{try{await fn()}catch(error){message.textContent=error.message}};parent.append(b);return b}
const message=e('p');message.setAttribute('role','status');
function field(parent,label,tag='input',options=[]){const row=e('label',label),input=e(tag);for(const v of options){const o=e('option',v);o.value=v;input.append(o)}row.append(input);parent.append(row);return input}
function open(){
 if(dialog.open)return;
 dialog.replaceChildren();const h=e('h2','Workspace Tools');h.id='ptToolsTitle';dialog.append(h);
 const a=e('fieldset');a.append(e('legend','Accessibility'));dialog.append(a);
 const contrast=field(a,'Contrast','select',['auto','high','normal']);contrast.id='ptContrast';contrast.value=state.workspace_tools.accessibility.contrast;
 const scale=field(a,'Application scale');scale.id='ptApplicationScale';scale.type='number';scale.min=1;scale.max=2;scale.step=.1;scale.value=state.workspace_tools.accessibility.scale;
 button(a,'Apply accessibility',()=>mutate({action:'accessibility',contrast:contrast.value,scale:Number(scale.value)}));
 const t=e('fieldset');t.append(e('legend','Device Template Manager'));dialog.append(t);
 const kind=field(t,'Source type','select',['device','cluster','physical']),source=field(t,'Source','select');source.id='ptTemplateSource';
 function fill(){source.replaceChildren();const entries=kind.value==='device'?Object.keys(state.devices):Object.keys(kind.value==='cluster'?state.clusters:state.physical_locations);for(const id of entries){const o=e('option',id);o.value=id;source.append(o)}}
 kind.onchange=fill;fill();kind.id='ptTemplateKind';
 const name=field(t,'Template name');name.id='ptTemplateName';name.maxLength=64;
 const description=field(t,'Description');description.maxLength=500;
 button(t,'Add template',async()=>{await mutate({action:'template_capture',name:name.value,description:description.value,kind:kind.value,source:source.value});refreshTemplates()});
 const saved=field(t,'Saved templates','select');saved.id='ptSavedTemplates';
 function refreshTemplates(){saved.replaceChildren();for(const n of Object.keys(state.workspace_tools.templates)){const o=e('option',n);o.value=n;saved.append(o)}}refreshTemplates();
 button(t,'Create from template',async()=>{const c=context();await mutate({action:'template_instantiate',name:saved.value,cluster:c.workspace==='logical'?c.location:'root',location:c.workspace==='physical'?c.location:'intercity',x:200,y:160});message.textContent='Template created; addressing is copied. Adjust duplicate IP addresses before connecting instances.'});
 button(t,'Remove template',async()=>{await mutate({action:'template_delete',name:saved.value});refreshTemplates()});
 button(t,'Export template',()=>{const data=state.workspace_tools.templates[saved.value];if(!data)throw Error('Select a template');const a=e('a');a.href=URL.createObjectURL(new Blob([JSON.stringify(data,null,2)],{type:'application/json'}));a.download=saved.value+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
 const upload=field(t,'Import template JSON');upload.type='file';upload.accept='.json,application/json';
 upload.onchange=async()=>{try{const f=upload.files[0];if(f.size>16000000)throw Error('Template exceeds 16MB');await mutate({action:'template_import',name:name.value||f.name.replace(/\.json$/,''),template:JSON.parse(await f.text())});refreshTemplates()}catch(error){message.textContent=error.message}};
 dialog.append(e('p','Shift+D: focus devices; arrows choose by direction; Ctrl/Cmd+arrows cycle devices; Shift+arrows move one; Ctrl/Cmd+Shift+arrows move farther; Enter/Space uses the selected tool. Shift+W: logical list; Shift+N: physical navigation; Shift+V: viewport; Ctrl/Cmd+F6: leave terminal focus. Native Tab/Shift+Tab navigates controls.'));
 button(dialog,'Accessible simulation events',()=>{dialog.close();openEvents()});
 dialog.append(message);button(dialog,'Close',()=>dialog.close());dialog.showModal();contrast.focus();
}
function openEvents(){
 const d=e('dialog');d.setAttribute('aria-label','Simulation packet events');d.append(e('h2','Simulation packet events'));
 const table=e('table'),caption=e('caption','Saved packet trace from the authoritative simulator');table.append(caption);
 const head=e('tr');for(const label of ['Event','Protocol','Source','Destination','Details']){const th=e('th',label);th.scope='col';head.append(th)}
 const thead=e('thead');thead.append(head);table.append(thead);const body=e('tbody');
 for(const item of state.packet_events||[]){const row=e('tr');for(const key of ['seq','protocol','source','destination'])row.append(e('td',item[key]||''));
 const td=e('td'),details=e('details');details.append(e('summary','Inspect event'),e('pre',JSON.stringify(item,null,2)));td.append(details);row.append(td);body.append(row)}
 table.append(body);d.append(table);button(d,'Close',()=>d.close());d.addEventListener('close',()=>{d.remove();trigger.focus()});document.body.append(d);d.showModal();
}
trigger.onclick=open;dialog.addEventListener('close',()=>trigger.focus());
let ticket=0;
async function renderViewport(){
 const root=by('ptViewport');if(!root||!state.workspace_tools)return;
 const v=state.workspace_tools.viewport;root.hidden=!v.visible;if(root.hidden)return;
 const seq=++ticket,c=context();
 const r=await fetch('/api/workspace-tools?'+new URLSearchParams({...c,mode:v.mode})),data=await r.json();if(seq!==ticket||!data.ok)return;
 root.replaceChildren();root.append(e('strong','Workspace Viewport'));
 const mode=e('select');mode.setAttribute('aria-label','Viewport mode');for(const value of ['contents','workspace']){const o=e('option',value);o.value=value;mode.append(o)}mode.value=v.mode;mode.onchange=()=>mutate({action:'viewport',mode:mode.value});root.append(mode);
 button(root,'×',()=>mutate({action:'viewport',visible:false})).setAttribute('aria-label','Close viewport');
 const map=e('div');map.className='pt-viewport-map';map.tabIndex=0;map.setAttribute('role','group');map.setAttribute('aria-label','Viewport navigation; use arrow keys to pan');
 const b=data.bounds,w=b.right-b.x,h=b.bottom-b.y;
 const background=state.location_backgrounds?.[c.workspace==='physical'?c.location:'logical:'+c.location];
 if(v.mode==='workspace'&&background?.asset_id){map.style.backgroundImage='url(/api/visuals/assets/'+background.asset_id+')';map.style.backgroundSize=background.tiled?'auto':'100% 100%'}
 let showRadio=false;try{showRadio=JSON.parse(localStorage.getItem('packetTracker.preferences.v1'))?.showWirelessGrid===true}catch{}
 if(showRadio)for(const radio of data.radios||[]){const circle=e('span');circle.className='pt-viewport-radio';Object.assign(circle.style,{left:(radio.x-b.x-radio.radius_x_px)/w*100+'%',top:(radio.y-b.y-radio.radius_y_px)/h*100+'%',width:radio.radius_x_px*2/w*100+'%',height:radio.radius_y_px*2/h*100+'%'});circle.title=radio.device+' geometric radio coverage';map.append(circle)}
 for(const item of data.items){const dot=e('span');dot.className='pt-viewport-dot';dot.title=item.label;dot.style.left=(item.x-b.x)/w*100+'%';dot.style.top=(item.y-b.y)/h*100+'%';map.append(dot)}
 const pane=c.workspace==='physical'?by('ptPhysicalWorkspace'):by('workspace'),factor=c.workspace==='physical'?1:zoom;
 const visible=e('span');visible.className='pt-viewport-visible';Object.assign(visible.style,{left:Math.max(0,(pane.scrollLeft/factor-b.x)/w*100)+'%',top:Math.max(0,(pane.scrollTop/factor-b.y)/h*100)+'%',width:Math.min(100,pane.clientWidth/factor/w*100)+'%',height:Math.min(100,pane.clientHeight/factor/h*100)+'%'});map.append(visible);
 async function pan(x,y){await mutate({action:'viewport',...c,x:Math.max(0,Math.min(10000,x)),y:Math.max(0,Math.min(10000,y))});pane.scrollTo({left:Math.max(0,x*factor-pane.clientWidth/2),top:Math.max(0,y*factor-pane.clientHeight/2)})}
 map.onclick=event=>{const rect=map.getBoundingClientRect();pan(b.x+(event.clientX-rect.left)/rect.width*w,b.y+(event.clientY-rect.top)/rect.height*h).catch(error=>status(error.message))};
 map.onkeydown=event=>{const offsets={ArrowLeft:[-100,0],ArrowRight:[100,0],ArrowUp:[0,-100],ArrowDown:[0,100]};if(offsets[event.key]){event.preventDefault();const [dx,dy]=offsets[event.key];pan(v.x+dx,v.y+dy).catch(error=>status(error.message))}};
 root.append(map);
}
async function toggleViewport(){await mutate({action:'viewport',visible:!state.workspace_tools.viewport.visible})}
let templatePalette=false,pendingTemplate=null;
function renderTemplatePalette(){
 const templates=state.workspace_tools?.templates||{};if(!Object.keys(templates).length)return;
 const subtypes=by('subtypes');if(!subtypes||by('ptTemplatePaletteButton'))return;
 const b=e('button','Custom Templates');b.id='ptTemplatePaletteButton';b.className='subtype';b.title='Custom Made Devices and Containers';subtypes.append(b);
 function draw(){
  const tray=by('deviceTray');tray.replaceChildren();
  for(const [name,t] of Object.entries(templates)){
   const item=e('button',name);item.className='palette-device';item.dataset.template=name;item.title=t.description||t.kind+' template';item.draggable=true;
   item.onclick=()=>{pendingTemplate=name;placementType=null;setTool('select');status('Place template '+name+': click workspace or drop on a physical container')};
   item.ondragstart=event=>event.dataTransfer.setData('application/x-pt-template',name);tray.append(item);
  }
 }
 b.onclick=()=>{templatePalette=true;draw()};if(templatePalette)draw();
}
const previousPalette=renderPalette;renderPalette=function(){previousPalette();renderTemplatePalette()};
document.addEventListener('click',event=>{if(event.target.closest('.category,.subtype')?.id!=='ptTemplatePaletteButton'&&event.target.closest('.category,.subtype')){templatePalette=false;pendingTemplate=null}},true);
async function placeTemplate(name,event){
 const c=context(),rect=by('workspace').getBoundingClientRect();
 const destination=c.workspace==='physical'?(event.target.closest('.pt-location')?.dataset.location||c.location):'intercity';
 await mutate({action:'template_instantiate',name,location:destination,cluster:c.workspace==='logical'?c.location:'root',x:Math.max(0,Math.min(10000,(event.clientX-rect.left+by('workspace').scrollLeft-(window.ptPan?.x||0))/zoom)),y:Math.max(0,Math.min(10000,(event.clientY-rect.top+by('workspace').scrollTop-(window.ptPan?.y||0))/zoom))});
 pendingTemplate=null;
}
by('workspace').addEventListener('click',event=>{if(!pendingTemplate||event.target.closest('#ptViewport'))return;event.preventDefault();event.stopImmediatePropagation();placeTemplate(pendingTemplate,event).catch(error=>status(error.message))},true);
by('workspace').addEventListener('dragover',event=>{if(event.dataTransfer.types.includes('application/x-pt-template'))event.preventDefault()});
by('workspace').addEventListener('drop',event=>{const name=event.dataTransfer.getData('application/x-pt-template');if(!name)return;event.preventDefault();event.stopImmediatePropagation();placeTemplate(name,event).catch(error=>status(error.message))},true);
function presentation(){
 const a=state.workspace_tools?.accessibility;if(!a)return;renderTemplatePalette();
 document.body.classList.toggle('pt-high-contrast',a.contrast==='high');document.body.classList.toggle('pt-normal-contrast',a.contrast==='normal');
 let base=1;try{base=(JSON.parse(localStorage.getItem('packetTracker.preferences.v1'))?.uiSize||12)/12}catch{}
 document.documentElement.style.setProperty('--pt-global-scale',String(a.scale*base));
 renderViewport().catch(error=>status(error.message));
}
window.PacketTrackerTools={open,mutate,toggleViewport,renderViewport};
window.PacketTrackerWorkspace.updateViewport=renderViewport;
const previousRender=render;render=function(){previousRender();presentation()};
// Labels and keyboard semantics for existing, dynamically generated widgets.
function semantics(){
 for(const b of document.querySelectorAll('button'))if(!b.textContent.trim()&&!b.getAttribute('aria-label'))b.setAttribute('aria-label',b.title||b.querySelector('img')?.alt||b.dataset.tool||'Application control');
 for(const input of document.querySelectorAll('input,select,textarea'))if(!input.labels?.length&&!input.getAttribute('aria-label'))input.setAttribute('aria-label',input.placeholder||input.id||'Input');
 const d=by('deviceDialog');d.setAttribute('role','dialog');d.setAttribute('aria-modal','true');d.setAttribute('aria-labelledby','dialogName');
 by('statusText').setAttribute('role','status');by('statusText').setAttribute('aria-live','polite');
 by('menuBar').setAttribute('role','menubar');
 for(const group of document.querySelectorAll('#dialogTabs,#workspaceTabs')){group.setAttribute('role','tablist');for(const b of group.querySelectorAll('#dialogTabs button,.workspace-tab')){b.setAttribute('role','tab');b.setAttribute('aria-selected',String(b.classList.contains('active')))}}
 for(const log of document.querySelectorAll('.cli-screen,.pc-command-screen')){log.setAttribute('role','log');log.setAttribute('aria-label','Device terminal output')}
 by('termOut').setAttribute('role','log');by('termOut').setAttribute('aria-label','Agent shell output');
 for(const n of document.querySelectorAll('.menu-item')){n.tabIndex=0;n.setAttribute('role','menuitem')}
 for(const f of document.querySelectorAll('iframe'))if(!f.title)f.title='Embedded page';
}
let scheduled=false;new MutationObserver(records=>{if(!scheduled&&records.some(r=>[...r.addedNodes].some(n=>n.nodeType===1))){scheduled=true;requestAnimationFrame(()=>{scheduled=false;semantics()})}}).observe(document.body,{childList:true,subtree:true});semantics();
document.addEventListener('keydown',event=>{
 const typing=event.target.closest('input,textarea,select,[contenteditable=true]');
 if((event.ctrlKey||event.metaKey)&&event.key==='F6'){event.preventDefault();event.stopImmediatePropagation();(event.target.closest('[role=dialog]')?.querySelector('button')||trigger).focus();return}
 if(event.target.matches('[role=tab],.category,.subtype')&&['ArrowLeft','ArrowRight'].includes(event.key)){
  event.preventDefault();const items=[...event.target.parentElement.querySelectorAll('[role=tab],.category,.subtype')];const index=items.indexOf(event.target);const next=items[(index+(event.key==='ArrowRight'?1:-1)+items.length)%items.length];const label=next?.textContent.trim();next?.focus();next?.click();requestAnimationFrame(()=>{[...document.querySelectorAll('[role=tab],.category,.subtype')].find(n=>n.textContent.trim()===label)?.focus()});return;
 }
 const modal=[...document.querySelectorAll('dialog[open],[role=dialog]')].reverse().find(n=>n.getClientRects().length&&!n.hidden&&!n.classList.contains('hidden'));
 if(modal){
  if(event.key==='Tab'&&modal.tagName!=='DIALOG'){
   const controls=[...modal.querySelectorAll('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),a[href],[tabindex="0"]')].filter(n=>n.getClientRects().length);
   const first=controls[0],last=controls.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus()}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus()}
  }
  return;
 }
 if(event.target.closest('#ptFullMenu,#ptOptionsMenu')&&['ArrowDown','ArrowUp'].includes(event.key)){event.preventDefault();const buttons=[...event.target.parentElement.querySelectorAll('button:not(:disabled)')];const index=buttons.indexOf(event.target);buttons[(index+(event.key==='ArrowDown'?1:-1)+buttons.length)%buttons.length]?.focus();return}
 if(event.target.matches('.menu-item')&&['Enter',' ','ArrowLeft','ArrowRight'].includes(event.key)){
  event.preventDefault();if(event.key==='Enter'||event.key===' ')event.target.click();else{const items=[...document.querySelectorAll('.menu-item')],index=items.indexOf(event.target);items[(index+(event.key==='ArrowRight'?1:-1)+items.length)%items.length].focus()}return;
 }
 if(typing)return;
 const k=event.key.toLowerCase(),ctrl=event.ctrlKey||event.metaKey;
 const clickTitle=title=>document.querySelector('[title="'+title+'"]')?.click();
 if(event.altKey&&!ctrl){
  const names={f:'File',e:'Edit',o:'Options',v:'View',t:'Tools',x:'Extensions',h:'Help'};
  if(names[k]){event.preventDefault();[...document.querySelectorAll('.menu-item')].find(n=>n.textContent.trim()===names[k])?.click();document.querySelector('#ptFullMenu button:not(:disabled),#ptOptionsMenu button:not(:disabled)')?.focus();return}
 }
 if(ctrl&&!event.shiftKey&&!event.altKey){
  const targets={n:'newBtn',o:'openBtn',s:'saveBtn',i:'zoomIn',t:'zoomReset',u:'zoomOut'};
  if(targets[k]){event.preventDefault();by(targets[k])?.click();return}
 }
 if(!ctrl&&!event.altKey&&event.shiftKey){
  const titles={c:'Create New City',b:'Create New Building',f:'Create Generic Container',j:'Create New Closet',h:'Go to Working Closet',u:'New Cluster',m:'Move Object',i:'Set Tiled Background'};
  if(titles[k]){event.preventDefault();clickTitle(titles[k]);return}
  if(k==='r'||k==='s'){event.preventDefault();by(k==='r'?'realtimeBtn':'simulationBtn').click();return}
 }
 if(ctrl&&event.shiftKey&&k==='d'){event.preventDefault();event.stopImmediatePropagation();open();return}
 if(!ctrl&&!event.altKey&&event.shiftKey){
  const actions={v:toggleViewport,n:()=>window.PacketTrackerAccessible.open(),w:()=>window.PacketTrackerList?.open?.(),l:()=>document.querySelectorAll('.workspace-tab')[0].click(),p:()=>document.querySelectorAll('.workspace-tab')[1].click(),g:()=>window.PacketTrackerPhysicalSettings.openGrid()};
  if(actions[k]){event.preventDefault();event.stopImmediatePropagation();Promise.resolve(actions[k]()).catch(error=>status(error.message))}
 }
},true);
window.addEventListener('pt-physical-presentation',()=>presentation());
presentation();
})();
