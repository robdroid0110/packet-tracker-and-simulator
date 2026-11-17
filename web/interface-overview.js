/* legacy network simulator Interface Overview: UI parity, separate from protocol simulation. */
(function(){
'use strict';
const get=id=>document.getElementById(id);
const parent=get('workspace'), bar=get('workspaceTabs'), nav=bar.querySelector('.workspace-right');
const STORE='packetTracker.overview.ui.v1';
function safeLoad(){try{return JSON.parse(localStorage.getItem(STORE))||{}}catch{return {}}}
const saved=safeLoad();
let mode='logical', level=0, currentCluster=null, selectedPduSource=null, pduKind='simple', simScenario=0;
let locations=Array.isArray(saved.locations)?saved.locations:[
 {id:'city0',type:'city',name:'Home City',parent:null},
 {id:'building0',type:'building',name:'Corporate Office',parent:'city0'},
 {id:'closet0',type:'closet',name:'Main Wiring Closet',parent:'building0'}
];
let shapes=Array.isArray(saved.shapes)?saved.shapes:[],clusters=Array.isArray(saved.clusters)?saved.clusters:[];
let currentLocation=null,drawKind='rectangle',drawStart=null,drawColor='#2587b8',selectedClusterDevice=null;
let pdus=Array.isArray(saved.pdus)?saved.pdus:[],scenarioNames=Array.isArray(saved.scenarioNames)?saved.scenarioNames:['Scenario 0'];
let scenarioDescriptions=Array.isArray(saved.scenarioDescriptions)?saved.scenarioDescriptions:[];
function persist(){localStorage.setItem(STORE,JSON.stringify({locations,shapes,clusters,pdus,scenarioNames,scenarioDescriptions}))}
function elem(tag,cls,text){const el=document.createElement(tag);if(cls)el.className=cls;if(text!=null)el.textContent=text;return el}
const layer=elem('div','pt-overview-overlay physical');layer.id='ptPhysicalWorkspace';layer.hidden=true;parent.appendChild(layer);
const art=elem('div','pt-overview-layer');art.id='ptLogicalArt';parent.appendChild(art);
const view=elem('div');view.id='ptViewport';view.hidden=true;parent.appendChild(view);
const menu=elem('div','pt-context-menu');menu.id='ptFullMenu';menu.hidden=true;document.body.appendChild(menu);
const drawMenu=elem('div');drawMenu.id='ptDrawingPalette';drawMenu.hidden=true;document.body.appendChild(drawMenu);
const tip=elem('div');tip.id='ptTooltip';tip.hidden=true;document.body.appendChild(tip);
const modal=elem('div','pt-mini-dialog');modal.id='ptOverviewDialog';modal.hidden=true;document.body.appendChild(modal);
function modalClose(){modal.hidden=true;modal.innerHTML=''}
function showDialog(title,fields,apply,explain){
 modal.hidden=false;modal.innerHTML='';
 const box=elem('section','pt-mini-window'),h=elem('header'),heading=elem('strong','',title),x=elem('button','','×');
 x.type='button';x.onclick=modalClose;h.append(heading,x);box.appendChild(h);
 const body=elem('div','pt-mini-body');fields.forEach(f=>{
  const row=elem('label','',f.label),input=document.createElement(f.choices?'select':f.multiline?'textarea':'input');
  input.dataset.field=f.key;
  if(f.choices)f.choices.forEach(([v,t])=>{const opt=elem('option','',t);opt.value=v;input.appendChild(opt)});
  if(!f.choices&&!f.multiline)input.type=f.type||'text';
  input.value=f.value||'';row.appendChild(input);body.appendChild(row);
 });
 if(explain)body.appendChild(elem('p','pt-memo',explain));box.appendChild(body);
 const actions=elem('footer','pt-mini-actions'),cancel=elem('button','','Cancel'),ok=elem('button','','OK');
 cancel.onclick=modalClose;ok.onclick=()=>{
  const data={};box.querySelectorAll('[data-field]').forEach(n=>data[n.dataset.field]=n.value);
  const result=apply(data);if(result!==false)modalClose();
 };actions.append(cancel,ok);box.appendChild(actions);modal.appendChild(box);
 body.querySelector('input,select,textarea')?.focus();
}
modal.addEventListener('pointerdown',e=>{if(e.target===modal)modalClose()});
function info(title,text){showDialog(title,[],()=>{},text)}
function labels(){return [...document.querySelectorAll('#menuBar .menu-item')]}
const actions={
 'Show Viewport':()=>window.PacketTrackerTools?.toggleViewport(),
 'Device Template Manager':()=>window.PacketTrackerTools?.open(),
 'Copy':()=>window.PacketTrackerWorkspace?.edit.copy(),
 'Paste':()=>window.PacketTrackerWorkspace?.edit.paste(),
 'Undo':()=>window.PacketTrackerWorkspace?.edit.undo(),
 'Redo':()=>window.PacketTrackerWorkspace?.edit.redo(),
 'Select All':()=>window.PacketTrackerWorkspace?.edit.selectAll(),
 'Delete':()=>window.PacketTrackerWorkspace?.edit.delete(),
 'Open Samples…':()=>window.PacketTrackerSamples?.open().catch(error=>statusText(error.message)),
 'New':()=>get('newBtn').click(),'Open…':()=>get('openBtn').click(),'Save':()=>get('saveBtn').click(),
 'Save As…':()=>get('saveBtn').click(),'Print…':()=>window.print(),'Preferences…':()=>document.querySelector('#ptOptionsMenu [data-option="prefs"]')?.click(),
 'User Profile…':()=>document.querySelector('#ptOptionsMenu [data-option="profile"]')?.click(),
 'Zoom In':()=>get('zoomIn').click(),'Zoom Reset':()=>get('zoomReset').click(),'Zoom Out':()=>get('zoomOut').click(),
 'Fit to Window':()=>get('fitBtn').click(),'Workspace List':()=>window.PacketTrackerList?.open(),'Logical Workspace':()=>setMode('logical'),'Physical Workspace':()=>setMode('physical'),
 'Simulation Mode':()=>get('simulationBtn').click(),'Realtime Mode':()=>get('realtimeBtn').click(),
 'Event List':()=>get('eventListBtn').click(),'Device Palette':()=>document.body.classList.toggle('pt-hide-bottom'),
 'Select':()=>setTool('select'),'Inspect':()=>setTool('inspect'),'Delete':()=>setTool('delete'),
 'Place Note':()=>setTool('note'),'Resize Shape':()=>setTool('shape-resize'),
 'Drawing Palette':()=>openDrawPalette(),'Add Simple PDU':()=>setPduTool('simple'),'Add Complex PDU':()=>setPduTool('complex'),
 'Agent Shell':()=>get('shellToggle').click(),
 'Full Screen':()=>{if(!document.fullscreenElement)document.documentElement.requestFullscreen?.();else document.exitFullscreen?.()},
 'Interface Overview':()=>window.open('/help/index.html?topic=interfaceOverview.htm','_blank','noopener'),
 'Help Contents':()=>window.open('/help/index.html?topic=index.htm','_blank','noopener'),
 'Keyboard Shortcuts':()=>window.open('/help/index.html?topic=keyboardShortcuts.htm','_blank','noopener'),
 'About':()=>info('About Packet Tracker and Simulator','Packet Tracker and Simulator — local simulator. Interface based on legacy network simulator help. Unsupported network features are not simulated.')
};
const menus={
 File:['New','Open…','Open Samples…','Save','Save As…','Save as Pkz…','—','Print…','—','Exit'],
 Edit:['Undo','Redo','—','Cut','Copy','Paste','Delete','Select All'],
 Options:['Preferences…','User Profile…'],
 View:['Zoom In','Zoom Reset','Zoom Out','Fit to Window','—','Logical Workspace','Physical Workspace','Workspace List','Show Viewport','Realtime Mode','Simulation Mode','Event List'],
 Tools:['Device Template Manager','Select','Inspect','Delete','Resize Shape','Place Note','Drawing Palette','Add Simple PDU','Add Complex PDU','Agent Shell'],
 Extensions:['Activity Wizard','Multiuser','Extensions Manager'],
 Window:['Full Screen','—','Main Workspace','Device Windows'],
 Help:['Help Contents','Interface Overview','Keyboard Shortcuts','About']
};
function openPkzUi(){
 showDialog('Save as Pkz — Select Files',[
  {key:'filename',label:'Package filename',value:'my-network.pkz'},
  {key:'files',label:'Additional files (optional)',type:'file',value:''}
 ],()=>{statusText('PKZ export is not implemented; use Save for native Packet Tracker and Simulator labs.');},'legacy network simulator packages a topology and custom images/backgrounds. This is a UI preview of the PKZ selection dialog, not a working PKZ exporter.');
}
function openActivityWizard(){
 showDialog('Activity Wizard',[
  {key:'pane',label:'Activity Wizard section',choices:[['instructions','Instructions'],['initial','Initial Network'],['answer','Answer Network'],['testing','Testing'],['settings','Settings']]},
  {key:'activityName',label:'Activity title',value:'New Activity'}
 ],()=>{statusText('Activity Wizard interface preview; assessment authoring is not implemented.');},'Activity Wizard entry point is present as documented. Activity creation, answer trees and grading are not implemented.');
}
function openMenu(name,b){
 const entries=menus[name]||[];menu.innerHTML='';
 entries.forEach(label=>{
  if(label==='—'){menu.appendChild(document.createElement('hr'));return}
  const row=elem('button','',label),fn=actions[label];
  if(label==='Delete'&&name==='Edit')row.onclick=()=>window.PacketTrackerWorkspace?.edit.delete();
  else if(label==='Save as Pkz…')row.onclick=openPkzUi;
  else if(label==='Activity Wizard')row.onclick=openActivityWizard;
  else if(label==='Main Workspace')row.onclick=()=>{modalClose();get('deviceDialog').classList.add('hidden')};
  else if(fn)row.onclick=fn;
  else{row.disabled=true;row.title='Requires functionality outside the Interface Overview UI milestone';}
  if(row.onclick)row.onclick=((original)=>()=>{menu.hidden=true;original()})(row.onclick);
  menu.appendChild(row);
 });
 const bounds=b.getBoundingClientRect();menu.style.left=Math.min(bounds.left,innerWidth-230)+'px';menu.style.top=bounds.bottom+'px';menu.hidden=false;
}
labels().forEach(button=>{
 const name=button.textContent.trim();
 if(name==='Options')return;
 button.onclick=e=>{e.stopPropagation();if(!menu.hidden&&button.dataset.menuOpen==='yes'){menu.hidden=true;button.dataset.menuOpen='no';return}
  labels().forEach(b=>b.dataset.menuOpen='no');button.dataset.menuOpen='yes';openMenu(name,button);
 };
 button.setAttribute('aria-haspopup','menu');
});
document.addEventListener('pointerdown',e=>{if(!menu.hidden&&!menu.contains(e.target)&&!e.target.closest('#menuBar')){menu.hidden=true;labels().forEach(b=>b.dataset.menuOpen='no')}});
function statusText(s){status(s)}
const navAssets='/assets/icons/toolbar/';
function navButton(label,title,icon,handler,disabled=false){
 const b=elem('button',icon?'':'pt-nav-text',icon?'':label);
 b.type='button';b.title=title||label;b.setAttribute('aria-label',title||label);
 if(icon){const img=document.createElement('img');img.src=navAssets+icon;b.appendChild(img)}
 b.disabled=disabled;if(!disabled)b.onclick=handler;
 return b;
}
function locationType(id){return locations.find(x=>x.id===id)}
function pathLocation(){
 const chain=[];let loc=locationType(currentLocation),safety=0;
 while(loc&&safety++<16){chain.unshift(loc);loc=locationType(loc.parent)}
 return chain;
}
function currentPlace(){return pathLocation().map(x=>x.name).join(' / ')||'Intercity'}
function updateNav(){
 nav.innerHTML='';
 const crumb=elem('span','pt-nav-crumb',mode==='physical'?currentPlace():currentCluster?('Root / '+currentCluster.name):'Root');
 crumb.title=crumb.textContent;nav.appendChild(crumb);
 if(mode==='physical'){
  nav.append(
   navButton('Back','Back to previous location','back.svg',()=>{currentLocation=locationType(currentLocation)?.parent||null;refresh()},!currentLocation),
   navButton('New City','Create New City',null,()=>addLocation('city')),
   navButton('New Building','Create New Building',null,()=>addLocation('building')),
   navButton('New Closet','Create New Closet',null,()=>addLocation('closet')),
   navButton('New Container','Create Generic Container',null,()=>addLocation('generic')),
   navButton('New ICP','Create Industrial Control Panel',null,()=>addICP(),locationType(currentLocation)?.type==='icp'),
   navButton('Dimensions','Container Dimensions (meters)',null,physicalDimensions,currentLocation===null),
   navButton('Relocate','Move Container to New Parent',null,physicalRelocate,currentLocation===null),
   navButton('New Shelf','Add Storage Shelf',null,physicalAddShelf,locationType(currentLocation)?.type!=='closet'),
   navButton('Navigation','Physical Navigation Tree',null,()=>window.PacketTrackerPhysicalNav?.open()),
   navButton('Accessible','Accessible Physical Navigation',null,()=>window.PacketTrackerAccessible?.open(currentLocation||'intercity')),
   navButton('Move','Move Object','4-way-nav.svg',()=>window.PacketTrackerPhysicalNav?.armMove()),
   navButton('Grid','Configure Physical Grid',null,()=>window.PacketTrackerPhysicalSettings?.openGrid()),
   navButton('Delete Location','Delete Current Physical Location',null,()=>window.PacketTrackerPhysicalSettings?.openDelete(currentLocation),currentLocation===null),
   navButton('Background','Set Background','image.svg',()=>window.PacketTrackerVisual?.openBackground(currentLocation||'intercity')),
   navButton('Working Closet','Go to Working Closet',null,()=>{currentLocation=(locations.find(x=>x.type==='closet')||{}).id||null;refresh()})
  );
 }else{
  nav.append(
   navButton('Back','Return to Parent Cluster','back.svg',()=>{currentCluster=currentCluster?.parent?clusters.find(c=>c.id===currentCluster.parent)||null:null;refresh()},!currentCluster),
   navButton('New Cluster','New Cluster','cloud.svg',addCluster),
   navButton('Move','Move Object','4-way-nav.svg',moveClusterObject),
   navButton('Background','Set Tiled Background','image.svg',backgroundDialog),
   navButton('Viewport','Viewport','viewport.svg',toggleViewport)
  );
 }
}
function setMode(next){
 mode=next;document.querySelectorAll('.workspace-tab').forEach(b=>b.classList.toggle('active',b.textContent.trim().toLowerCase()===mode));
 layer.hidden=mode!=='physical';get('wires').style.display=mode==='physical'?'none':'';
 get('nodes').style.display=mode==='physical'?'none':'';
 get('workspaceNotes')&&(get('workspaceNotes').style.display=mode==='physical'?'none':'');
 get('emptyHint').style.display='none';art.hidden=mode==='physical';
 get('statusBar').firstElementChild.textContent=mode==='physical'?'Physical Workspace':'Logical Workspace';
 view.hidden=true;refresh();statusText(mode==='physical'?'Physical Workspace: choose a location':'Logical Workspace');
}
document.querySelectorAll('.workspace-tab').forEach(b=>b.onclick=()=>setMode(b.textContent.trim().toLowerCase()));

async function createInPhysical(model,location,physicalX=null,physicalY=null){
 const spec=catalog.models[model];
 if(!spec)return statusText('Unknown device model');
 const prefix=spec.kind==='router'?'R':spec.kind==='switch'?'SW':spec.kind==='pc'?'PC':spec.kind==='server'?'Server':'DEV';
 let index=1;while(state.devices[prefix+index])index++;
 const name=prefix+index;
 const count=Object.keys(state.devices).length;
 const x=110+(count%7)*130,y=110+Math.floor(count/7)*110;
 const ok=await physicalRequest({action:'add_device',model,name,x,y,location,
  ...(physicalX!==null?{physical_x:Math.max(0,Math.round(physicalX)),physical_y:Math.max(0,Math.round(physicalY))}:{})});
 if(ok&&!window.ptPlacementLocked){placementType=null;renderPalette()}
 return ok?name:null;
}
layer.addEventListener('dragover',e=>{
 if(mode==='physical'&&e.dataTransfer?.types?.includes('application/x-packettracker-model')){
  e.preventDefault();e.dataTransfer.dropEffect='copy';
 }
});
layer.addEventListener('drop',e=>{
 if(mode!=='physical')return;
 const id=e.dataTransfer?.getData('application/x-packettracker-model');
 if(!id)return;
 e.preventDefault();e.stopPropagation();
 const target=e.target.closest('.pt-location');
 const map=e.target.closest('.pt-map-cards');
 const bounds=map?.getBoundingClientRect();
 const coords=target||!bounds?[]:[e.clientX-bounds.left,e.clientY-bounds.top];
 createInPhysical(id,target?.dataset.location||currentLocation||'intercity',...coords)
  .then(name=>{
    const pane=e.target.closest('.pt-icp-pane');
    if(name&&pane?.dataset.side==='door'){
      window.PacketTrackerICP?.placeNew(name,'door',e.clientX,e.clientY,pane);
    }
  });
});
layer.addEventListener('click',e=>{
 if(mode!=='physical'||!placementType)return;
 const target=e.target.closest('.pt-location');
 const surface=e.target.closest('.pt-physical-surface,.pt-icp-pane');
 const map=e.target.closest('.pt-map-cards');
 if(e.target!==layer&&!surface&&!map&&!target)return;
 const bounds=map?.getBoundingClientRect();
 const coords=target||!bounds?[]:[e.clientX-bounds.left,e.clientY-bounds.top];
 createInPhysical(placementType,target?.dataset.location||currentLocation||'intercity',...coords);
});

function addICP(){
 if(locationType(currentLocation)?.type==='icp')return;
 showDialog('New Industrial Control Panel',[
   {key:'name',label:'Panel name',value:'Control Panel'},
   {key:'size',label:'Preset size',choices:[['small','Small'],['medium','Medium'],['large','Large']],value:'medium'}
 ],d=>{
  window.PacketTrackerICP?.create(d.name.trim(),d.size,currentLocation||'intercity');
 },'Create an industrial cabinet with an opening door. DIN rails and wire conduits are physical layout fixtures only.');
}
function addLocation(type){
 const kind=locationType(currentLocation)?.type||'intercity';
 if(type==='city'&&kind!=='intercity')return info('New City','Return to Intercity to add a new city.');
 if(type==='building'&&!['intercity','city'].includes(kind))return info('New Building','Create buildings at the Intercity or City level.');
 if(type==='closet'&&!['intercity','city','building'].includes(kind))return info('New Closet','Create closets at the Intercity, City, or Building level.');
 if(type==='generic'&&kind==='generic'&&pathLocation().length>=8)return info('Container nesting','Maximum of eight nested containers in the UI.');

 const parentId=type==='city'?null:currentLocation;
 const title=type[0].toUpperCase()+type.slice(1);
 showDialog('New '+title,[{key:'name',label:title+' name',value:'New '+title}],data=>{
  const name=data.name.trim();if(!name)return false;
  physicalRequest({action:'add_location',kind:type,name,parent:parentId||'intercity'});
 });
}
async function physicalRequest(data){
 try{
  const response=await fetch('/api/physical-workspace/action',{method:'POST',
    headers:{'content-type':'application/json'},
    body:JSON.stringify({...data,view_location:currentLocation||'intercity'})});
  const payload=await response.json();
  if(!payload.ok){statusText(payload.output||payload.error||'Physical workspace operation failed');return false}
  state=payload.state;refresh();statusText(payload.output||'Physical workspace updated');return true;
 }catch(error){statusText('Physical API error: '+error.message);return false}
}
function physicalDimensions(){
 if(!currentLocation)return;
 const loc=locationType(currentLocation);if(!loc)return;
 showDialog('Physical Dimensions — '+loc.name,[
  {key:'width',label:'Width (meters)',type:'number',value:String(loc.width||20)},
  {key:'length',label:'Length (meters)',type:'number',value:String(loc.length||15)},
  {key:'height',label:'Height (meters)',type:'number',value:String(loc.height||4)}
 ],d=>{
  physicalRequest({action:'resize_location',location:loc.id,width:+d.width,length:+d.length,height:+d.height});
 },'Dimensions are stored in meters and constrain child containers. Cable length effects are not implemented yet.');
}
function physicalRelocate(){
 if(!currentLocation)return;
 const loc=locationType(currentLocation);if(!loc)return;
 const options=[['intercity','Intercity'],...locations.filter(x=>x.id!==loc.id).map(x=>[x.id,x.name+' ('+x.type+')'])];
 showDialog('Move Container — '+loc.name,[
  {key:'parent',label:'Parent location',choices:options,value:loc.parent||'intercity'}
 ],d=>physicalRequest({action:'relocate_location',location:loc.id,parent:d.parent}),
 'Parent type, volume and cycle validation are enforced by the shared API.');
}
function physicalAddShelf(){
 if(!currentLocation||locationType(currentLocation)?.type!=='closet')return;
 physicalRequest({action:'add_shelf',closet:currentLocation});
}
function physicalMountDevice(device){
 const loc=state.device_locations?.[device],entry=locationType(loc);
 if(!entry||entry.type!=='closet')return info('Mount Device','Move a device to a wiring closet to mount it.');
 const count=state.physical_shelves?.[loc]||0;
 const choices=[['rack','Rack'],['table','Table'],['floor','Floor'],
   ...Array.from({length:count},(_,i)=>['shelf:'+i,'Shelf '+(i+1)+' (storage)'])];
 const current=state.physical_device_details?.[device]||{surface:'floor',shelf:null};
 showDialog('Move Equipment — '+device,[
  {key:'surface',label:'Placement',choices,value:current.surface==='shelf'?'shelf:'+current.shelf:current.surface}
 ],d=>{
  const [surface,index]=d.surface.split(':');
  physicalRequest({action:'mount_device',device,surface,
    ...(surface==='shelf'?{shelf:Number(index)}:{})});
 },'Shelf storage requires power off and no cables. Rack and table arrangements are currently visual, not actual rack-unit models.');
}
function backgroundDialog(){
 window.PacketTrackerVisual?.openBackground('logical:'+(currentCluster?.id||'root'));
}
window.PacketTrackerLogicalContext=()=>({cluster:currentCluster?.id||'root',mode});
function locationMove(deviceName=''){
 const target=state.devices?.[deviceName]?deviceName:null;
 window.PacketTrackerPhysicalNav?.open(target?{device:target}:{});
}
window.addEventListener('pt-visuals-refresh',()=>refresh());
window.addEventListener('pt-physical-focus-location',event=>{
 const id=event.detail?.location;
 if(id!=='intercity'&&!locations.some(loc=>loc.id===id))return;
 currentLocation=id==='intercity'?null:id;
 if(mode!=='physical')setMode('physical');else refresh();
});
function placeArtwork(place){
 if(place.type==='icp')return '<svg viewBox="0 0 160 90" aria-hidden="true"><rect x="38" y="5" width="84" height="80" rx="4" fill="#687988" stroke="#2b3f4e" stroke-width="5"/><rect x="47" y="13" width="67" height="64" fill="#b8c8d3" stroke="#536d7e" stroke-width="2"/><path d="M102 35 v19" stroke="#294960" stroke-width="6"/><rect x="56" y="20" width="37" height="8" fill="#769daa"/><rect x="56" y="37" width="37" height="7" fill="#69828b"/><circle cx="66" cy="61" r="5" fill="#42b990"/></svg>';
 if(place.type==='generic')return '<svg viewBox="0 0 160 90" aria-hidden="true"><rect x="12" y="15" width="134" height="66" rx="6" fill="#a2c4bb" stroke="#3c7775" stroke-width="4"/><rect x="23" y="25" width="114" height="47" rx="3" fill="#d3e9dc"/><path d="M40 34h78M40 45h78M40 57h78" stroke="#548e78" stroke-width="3"/></svg>';
 if(place.type==='city')return '<svg viewBox="0 0 160 90" aria-hidden="true"><rect width="160" height="90" fill="#d4d6d9"/><path d="M8 10 43 5 48 27 30 40 11 36ZM56 4 98 3 111 24 85 30 53 27ZM116 5 153 13 151 37 113 34ZM8 46 34 43 43 72 9 84ZM45 39 78 36 93 57 74 83 47 83ZM99 38 148 43 157 80 104 86 85 62Z" fill="#b9bdc2" stroke="#fff" stroke-width="3"/><path d="M78 0 81 35 100 44 104 90" stroke="white" stroke-width="6" fill="none"/></svg>';
 if(place.type==='building')return '<svg viewBox="0 0 160 90" aria-hidden="true"><path d="M37 23 104 8 140 26 140 71 71 84 37 64Z" fill="#8d9baa" stroke="#536373" stroke-width="2"/><path d="M37 23 71 41 140 26M71 41 71 84" fill="none" stroke="#e5edf4" stroke-width="3"/><path d="M44 34 62 43M44 47 62 56M84 45 100 42M111 38 128 34M84 60 100 57M111 54 128 50" stroke="#dbe7f2" stroke-width="5"/></svg>';
 return '<svg viewBox="0 0 160 90" aria-hidden="true"><rect x="46" y="9" width="68" height="74" fill="#464e56" stroke="#202a32" stroke-width="5"/><path d="M53 20 H107 M53 33 H107 M53 46 H107 M53 59 H107 M53 72 H107" stroke="#8b959f" stroke-width="7"/><g fill="#6bdd87"><circle cx="101" cy="20" r="3"/><circle cx="101" cy="46" r="3"/><circle cx="101" cy="72" r="3"/></g></svg>';
}
function renderPhysicalBoundaryLinks(cards, location){
 // Read the authoritative server-side aggregation; logical links are untouched.
 fetch('/api/physical-workspace?location='+encodeURIComponent(location))
 .then(response=>response.ok?response.json():null).then(data=>{
  if(!data?.ok||!cards.isConnected||mode!=='physical'||
     (currentLocation||'intercity')!==location)return;
  const links=data.boundary_links||[];
  if(!links.length)return;
  const candidates=[...cards.querySelectorAll('.pt-location[data-location]')];
  const positions=new Map(candidates.map(node=>[node.dataset.location,{
   x:node.offsetLeft+node.offsetWidth/2,y:node.offsetTop+node.offsetHeight/2
  }]));
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
  svg.classList.add('pt-city-cables');
  svg.setAttribute('aria-label','Physical links between separate locations');
  svg.setAttribute('width',Math.max(cards.clientWidth,1));
  svg.setAttribute('height',Math.max(cards.clientHeight,1));
  for(const edge of links){
   const a=positions.get(edge.source),b=positions.get(edge.destination);
   if(!a||!b)continue;
   const line=document.createElementNS('http://www.w3.org/2000/svg','line');
   Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y}).forEach(([k,v])=>line.setAttribute(k,String(v)));
   line.setAttribute('stroke',edge.up?(edge.links===1?(edge.cables?.[0]?.color||'#24354b'):'#24354b'):'#9b5a4c');
   line.setAttribute('stroke-width',edge.links>1?'3':'2');
   if(!edge.up)line.setAttribute('stroke-dasharray','5 5');
   const desc=document.createElementNS('http://www.w3.org/2000/svg','title');
   desc.textContent=edge.links+' physical cable(s), '+edge.up+' operational between '+
    (data.locations[edge.source]?.name||edge.source)+' and '+
    (data.locations[edge.destination]?.name||edge.destination)+' · '+
    (edge.cables||[]).map(c=>c.endpoints.join(' → ')+': '+c.length_m+'m').join('; ')+
    ' (straight-line distances; curved cable routing not modeled)';
   line.appendChild(desc);svg.appendChild(line);
   const label=document.createElementNS('http://www.w3.org/2000/svg','text');
   label.setAttribute('x',String((a.x+b.x)/2));
   label.setAttribute('y',String((a.y+b.y)/2-7));
   label.setAttribute('text-anchor','middle');
   label.textContent=edge.links+' link'+(edge.links===1?'':'s');
   svg.appendChild(label);
  }
  cards.prepend(svg);
 }).catch(()=>{/* Source is optional for offline view; never invent link status. */});
}
function renderPhysicalWorkspace(){
 layer.dataset.location=currentLocation||'intercity';
 window.PacketTrackerTools?.renderViewport();
 layer.innerHTML='';
 if(mode!=='physical')return;
 const loc=locationType(currentLocation),kind=loc?.type||'intercity';
 const header=elem('div','pt-map-heading'),head=elem('strong','',loc?.name||'Intercity'),detail=elem('small','',kind==='closet'?'Rack and device view':'Select a location to enter it');
 header.append(head,detail);layer.appendChild(header);
 if(kind==='icp'){
  if(window.PacketTrackerICP)window.PacketTrackerICP.render(layer,currentLocation);
  return;
 }
 if(kind==='closet'){
  const layout=elem('div','pt-rack-layout pt-physical-furniture');
  const all=Object.values(state.devices||{});
  const values=all.filter(d=>(state.device_locations?.[d.name]||'intercity')===loc.id);
  const shelves=state.physical_shelves?.[loc.id]||0;
  function makeSurface(surface,label,shelf=null){
   const section=elem('section','pt-physical-surface surface-'+surface);
   section.appendChild(elem('h3','',label));
   section.dataset.surface=surface;
   if(shelf!==null)section.dataset.shelf=String(shelf);
   section.addEventListener('dragover',e=>{
    if(e.dataTransfer?.types?.includes('application/x-pt-device'))e.preventDefault();
   });
   section.addEventListener('drop',e=>{
    const name=e.dataTransfer?.getData('application/x-pt-device');
    if(!name)return;
    e.preventDefault();
    physicalRequest({action:'mount_device',device:name,surface,
     ...(shelf!==null?{shelf}:{})});
   });
   return section;
  }
  function populate(section,surface,shelf=null){
   const items=values.filter(d=>{
    const data=state.physical_device_details?.[d.name]||{surface:d.kind==='router'||d.kind==='switch'?'rack':'table'};
    return data.surface===surface&&(shelf===null||data.shelf===shelf);
   });
   items.sort((a,b)=>(state.physical_device_details?.[a.name]?.y||0)-(state.physical_device_details?.[b.name]?.y||0));
   if(!items.length)section.appendChild(elem('p','pt-physical-empty','Drop equipment here'));
   for(const d of items){
    const row=elem('div','pt-physical-equipped');
    row.draggable=true;
    row.title=d.name+' · Drag to another mounting surface. Storage shelves require device OFF and no cables.';
    row.addEventListener('dragstart',e=>e.dataTransfer.setData('application/x-pt-device',d.name));
    const spec=modelSpec(d),filename=catalog.icons?.[spec.icon];
    const open=elem('button','pt-rack-device');
    if(filename){const img=document.createElement('img');img.src='/assets/icons/device/'+encodeURIComponent(filename);img.alt='';open.appendChild(img)}
    open.appendChild(elem('span','',d.name));
    open.onclick=()=>{
      if(window.PacketTrackerPhysicalNav?.armed)locationMove(d.name);
      else openDevice(d.name);
    };
    const cables=state.links.filter(l=>l.a_device===d.name||l.b_device===d.name);
    const ports=elem('span','pt-rack-ports');
    ports.title=cables.length+' connected Ethernet port(s)';
    for(const link of cables.slice(0,10)){
     const good=link.up===true;
     const led=elem('span','pt-rack-port-light '+(good?'is-up':'is-down'));
     led.title=(link.a_device===d.name?link.a_if:link.b_if)+' — '+(good?'UP':'DOWN')+' · '+(link.status||'');
     ports.appendChild(led);
    }
    if(!cables.length)ports.textContent='No cables';
    const move=elem('button','pt-rack-move','Move…');move.title='Move '+d.name+' to rack, table, floor or storage shelf';
    move.onclick=()=>physicalMountDevice(d.name);
    row.append(open,ports,move);section.appendChild(row);
   }
  }
  const rack=makeSurface('rack','Rack');
  const table=makeSurface('table','Table');
  const floor=makeSurface('floor','Floor');
  populate(rack,'rack');populate(table,'table');populate(floor,'floor');
  layout.append(rack,table,floor);
  for(let i=0;i<shelves;i++){
   const shelf=makeSurface('shelf','Storage Shelf '+(i+1),i);
   populate(shelf,'shelf',i);
   layout.appendChild(shelf);
  }
  const child=locations.filter(x=>x.parent===loc.id);
  if(child.length){
   const box=elem('section','pt-physical-surface pt-closet-children');
   box.appendChild(elem('h3','','Containers in this Closet'));
   for(const c of child){
    const b=elem('button','pt-closet-container',c.name+' ('+c.type+')');
    b.dataset.location=c.id;
    b.onclick=()=>{
      if(window.PacketTrackerPhysicalNav?.armed)window.PacketTrackerPhysicalNav.open({container:c.id});
      else{currentLocation=c.id;refresh()}
    };
    box.appendChild(b);
   }
   layout.appendChild(box);
  }
  const note=elem('aside','pt-rack-note',
   'Devices in this closet: '+values.length+'. Cables are shown by port LEDs. Rack and table positions are visual; storage shelves enforce power-off/disconnect rules. Move equipment by dragging between areas or using Move…');
  const addShelf=elem('button','','Add Storage Shelf');
  addShelf.onclick=physicalAddShelf;
  note.appendChild(document.createElement('hr'));note.appendChild(addShelf);
  const moveButton=elem('button','','Move Device to Another Location…');
  moveButton.onclick=()=>locationMove(values[0]?.name||'');
  note.appendChild(moveButton);layout.appendChild(note);
  layer.appendChild(layout);
  if(window.PacketTrackerVisual){
   window.PacketTrackerVisual.currentLocation=currentLocation||'intercity';
   window.PacketTrackerVisual.renderPhysical();
  }
  window.PacketTrackerDistance?.render(currentLocation||'intercity');
  window.PacketTrackerCables?.render(currentLocation||'intercity');return;
 }
 const cards=elem('div','pt-map-cards'),child=locations.filter(x=>x.parent===(loc?.id||null));
 child.forEach((place,index)=>{
  const b=elem('button','pt-location'),icon=elem('span','pt-location-art');
  icon.innerHTML=placeArtwork(place);b.append(icon,elem('strong','',place.name),elem('small','',place.type==='city'?'City':place.type==='building'?'Building':place.type==='closet'?'Wiring Closet':place.type==='icp'?'Industrial Control Panel':'Generic Container'));
  b.style.left=(place.x??(28+index*205))+'px';b.style.top=(place.y??24)+'px';
  b.dataset.location=place.id;
  b.title='Click to enter; drag to move; right-click to rename '+place.name+' · '+(place.width||'?')+' × '+(place.length||'?')+' × '+(place.height||'?')+' meters';
  let pointer=null,suppressClick=false;
  b.addEventListener('pointerdown',e=>{if(e.button!==0)return;pointer={x:e.clientX,y:e.clientY,left:b.offsetLeft,top:b.offsetTop};b.setPointerCapture(e.pointerId)});
  b.addEventListener('pointermove',e=>{if(!pointer)return;const dx=e.clientX-pointer.x,dy=e.clientY-pointer.y;if(Math.abs(dx)+Math.abs(dy)>4)suppressClick=true;
   if(suppressClick){b.style.left=Math.max(0,pointer.left+dx)+'px';b.style.top=Math.max(0,pointer.top+dy)+'px'}});
  b.addEventListener('pointerup',()=>{
   if(pointer&&suppressClick){
    place.x=Math.round(b.offsetLeft);place.y=Math.round(b.offsetTop);
    physicalRequest({action:'move_location',location:place.id,x:place.x,y:place.y});
   }
   pointer=null;
  });
  b.onclick=e=>{
    if(suppressClick){suppressClick=false;return}
    if(place.type==='icp'&&e.shiftKey){
      currentLocation=place.id;refresh();
      window.PacketTrackerICP?.setPreview(place.id,true);
      return;
    }
    if(window.PacketTrackerPhysicalNav?.armed){window.PacketTrackerPhysicalNav.open({container:place.id});return}
    currentLocation=place.id;refresh();
  };
  b.oncontextmenu=e=>{
   e.preventDefault();
   const name=window.prompt('Rename '+place.type,place.name);
   if(name?.trim())physicalRequest({action:'rename_location',location:place.id,name:name.trim()});
  };
  cards.appendChild(b);
 });
 const present=Object.values(state.devices||{}).filter(d=>(state.device_locations?.[d.name]||'intercity')===(loc?.id||'intercity'));
 if(present.length){
  for(const d of present){
   const detail=state.physical_device_details?.[d.name]||{x:280,y:90};
   const card=elem('div','pt-physical-map-device');
   card.dataset.physicalDevice=d.name;
   card.style.left=(detail.x??280)+'px';card.style.top=(detail.y??90)+'px';
   const spec=modelSpec(d),filename=catalog.icons?.[spec.icon];
   const open=elem('button','pt-map-device-open',d.name);
   if(filename){
    const icon=document.createElement('img');
    icon.src='/assets/icons/device/'+encodeURIComponent(filename);icon.alt='';
    open.prepend(icon);
   }
   open.onclick=()=>{
    if(window.PacketTrackerPhysicalNav?.armed)locationMove(d.name);
    else openDevice(d.name);
   };
   const move=elem('button','pt-map-device-move','Move…');
   move.title='Change physical container for '+d.name;
   move.onclick=()=>locationMove(d.name);
   card.append(open,move);
   card.title='Physical position is saved separately from Logical workspace. Drag to position.';
   let grab=null,wasMoved=false;
   card.addEventListener('pointerdown',e=>{
    if(e.button!==0||e.target.closest('button'))return;
    grab={x:e.clientX,y:e.clientY,left:card.offsetLeft,top:card.offsetTop};
    card.setPointerCapture(e.pointerId);
   });
   card.addEventListener('pointermove',e=>{
    if(!grab)return;
    const dx=e.clientX-grab.x,dy=e.clientY-grab.y;
    if(Math.abs(dx)+Math.abs(dy)>4)wasMoved=true;
    if(wasMoved){card.style.left=Math.max(0,grab.left+dx)+'px';card.style.top=Math.max(0,grab.top+dy)+'px'}
   });
   card.addEventListener('pointerup',()=>{
    if(grab&&wasMoved){
     const x=Math.round(card.offsetLeft),y=Math.round(card.offsetTop);
     physicalRequest({action:'position_device',device:d.name,x,y});
    }
    grab=null;wasMoved=false;
   });
   cards.appendChild(card);
  }
 }
 if(!child.length&&!present.length)cards.appendChild(elem('p','pt-rack-note','Empty location. Add a device or create a location using the navigation bar.'));
 layer.appendChild(cards);
 if(window.PacketTrackerVisual){
  window.PacketTrackerVisual.currentLocation=currentLocation||'intercity';
  window.PacketTrackerVisual.renderPhysical();
 }
 window.PacketTrackerPhysicalSettings?.render(currentLocation||'intercity');
 renderPhysicalBoundaryLinks(cards,loc?.id||'intercity');
 window.PacketTrackerDistance?.render(currentLocation||'intercity');
 window.PacketTrackerCables?.render(currentLocation||'intercity');
}

function clusterSelections(){
 const names=[...(window.PacketTrackerWorkspace?.selected||[])].filter(n=>state.devices[n]);
 if(!names.length&&selected&&state.devices[selected])names.push(selected);
 return names;
}
function addCluster(){
 if(mode!=='logical')return;
 const defaults=clusterSelections().join(',');
 showDialog('New Cluster',[
  {key:'name',label:'Cluster name',value:'Cluster'+clusters.length},
  {key:'device',label:'Device names, comma separated (optional)',value:defaults}
 ],data=>{
  const name=data.name.trim(),members=data.device.split(',').map(n=>n.trim()).filter(Boolean);
  if(!name)return false;
  if(members.some(n=>!state.devices[n])){statusText('Select valid devices from the topology');return false}
  command('cluster add '+JSON.stringify(name)+' '+(members.join(',')||'none')+(currentCluster?' '+currentCluster.id:''),false)
    .then(r=>{statusText(r.output);if(r.ok)refresh()});
 },'The cluster is saved in the network lab. Select several devices first to group them. Nested clusters can be created from inside any cluster.');
}
function moveClusterObject(){
 const choices=[['root','Root'],...clusters.map(c=>[c.id,c.name])];
 const names=Object.keys(state.devices||{});
 if(!names.length)return info('Move Object','Create a device before moving it into a cluster.');
 showDialog('Move Object',[
  {key:'device',label:'Device name',choices:names.map(n=>[n,n]),value:selected&&state.devices[selected]?selected:names[0]},
  {key:'cluster',label:'Destination cluster',choices,value:currentCluster?.id||'root'}
 ],data=>{
  command('cluster place '+data.device+' '+data.cluster,false).then(r=>{
   statusText(r.output);if(r.ok)refresh();
  });
 },'Moves a device between saved logical clusters. Addresses, physical location, and network links do not change.');
}
function renderClusters(){
 art.innerHTML='';
 if(mode==='physical')return;
 const membership=new Map();
 for(const c of clusters)for(const d of c.devices)membership.set(d,c.id);
 const currentId=currentCluster?.id||null;
 const showDevice=name=>currentId ? membership.get(name)===currentId : !membership.has(name);
 document.querySelectorAll('#nodes .node').forEach(n=>{
  n.style.display=showDevice(n.dataset.name)&&!n.dataset.diagramHidden?'':'none';
 });
 (state.links||[]).forEach((link,i)=>{
  const show=showDevice(link.a_device)&&showDevice(link.b_device);
  const line=get('wires').querySelectorAll('line')[i];
  if(line)line.style.display=show?'':'none';
  const labels=get('wires').querySelectorAll('text:not(.diagram-label)');
  if(labels[i])labels[i].style.display=show?'':'none';
 });
 const children=clusters.filter(c=>(c.parent||null)===currentId);
 children.forEach((c,i)=>{
  const card=elem('div','pt-cluster-card');
  card.dataset.clusterId=c.id;
  card.style.left=(36+(i%5)*165)+'px';card.style.top=(45+Math.floor(i/5)*112)+'px';
  const strong=elem('strong','',c.name),n=elem('small','',c.devices.length+' device(s)');
  strong.title='Double-click to rename cluster';
  strong.ondblclick=e=>{
   e.stopPropagation();
   const name=window.prompt('Rename '+c.name,c.name);
   if(name?.trim())command('cluster rename '+c.id+' '+JSON.stringify(name.trim()),false).then(r=>{
    statusText(r.output);if(r.ok)refresh();
   });
  };
  const customize=elem('button','','Customize Icon');customize.onclick=()=>window.PacketTrackerVisual?.openClusterIcon(c.id);
  const iconId=state.cluster_icons?.[c.id];
  if(iconId){const image=elem('img');image.src='/api/visuals/assets/'+iconId;image.alt='';image.width=45;image.height=31;card.append(image)}
  card.append(customize);
  const open=elem('button','','Open Cluster');
  open.onclick=()=>{if(activeTool==='delete'){
     command('cluster delete '+c.id,false).then(r=>{statusText(r.output);if(r.ok)refresh()});return;
   }currentCluster=c;refresh()};
  card.title='Open cluster; double-click name to rename; Delete tool then Open to uncluster';
  card.append(strong,n,open);art.appendChild(card);
 });
 renderShapes();
}
function renderShapes(){
 shapes.forEach(s=>{
  if(s.cluster!==(currentCluster?.id||null))return;
  const shape=elem('div','pt-shape '+s.kind);shape.dataset.shapeId=s.id;
  Object.assign(shape.style,{left:s.x+'px',top:s.y+'px',width:s.w+'px',height:s.h+'px',borderColor:s.color});
  if(s.kind==='line')shape.style.background=s.color;
  if(activeTool==='shape-resize')shape.title='Drag lower-right handle to resize; changes save on release';
  if(activeTool==='delete')shape.title='Click to delete shape';
  shape.addEventListener('click',e=>{e.stopPropagation();if(activeTool==='delete'){shapes=shapes.filter(x=>x.id!==s.id);persist();refresh()}});
  shape.addEventListener('pointerup',()=>{if(activeTool!=='shape-resize')return;
   s.w=Math.round(shape.getBoundingClientRect().width/zoom);s.h=Math.round(shape.getBoundingClientRect().height/zoom);persist()});
  art.appendChild(shape);
 });
 document.body.classList.toggle('pt-resizing-shape',activeTool==='shape-resize');
}
function openDrawPalette(){
 drawMenu.hidden=false;drawMenu.innerHTML='';
 ['rectangle','ellipse','line'].forEach(label=>{
  const btn=elem('button',drawKind===label?'active':'',label[0].toUpperCase()+label.slice(1));
  btn.onclick=()=>{drawKind=label;setTool('draw');drawMenu.hidden=true;statusText('Draw '+label+': drag over empty workspace')};drawMenu.appendChild(btn);
 });
 const color=document.createElement('input');color.type='color';color.value=drawColor;color.title='Shape color';color.oninput=()=>drawColor=color.value;drawMenu.appendChild(color);
}
const toolRail=get('toolRail');
const resizeButton=[...toolRail.querySelectorAll('.tool')].find(b=>b.title.includes('Resize'));
if(resizeButton){resizeButton.dataset.tool='shape-resize';resizeButton.title='Resize Shape';}
const drawBtn=elem('button','tool');drawBtn.id='ptDrawBtn';drawBtn.title='Drawing Palette';
const drawIcon=document.createElement('img');drawIcon.className='tool-icon';drawIcon.src='/assets/icons/toolbar/notes.svg';drawIcon.alt='';drawBtn.appendChild(drawIcon);
const placeNote=[...toolRail.querySelectorAll('.tool')].find(b=>b.dataset.tool==='note');
toolRail.insertBefore(drawBtn,placeNote||null);
drawBtn.onclick=()=>openDrawPalette();
const originalSetTool=setTool;
setTool=function(tool){originalSetTool(tool);document.body.classList.toggle('pt-resizing-shape',tool==='shape-resize');refresh()};
parent.addEventListener('pointerdown',e=>{
 if(mode!=='logical'||activeTool!=='draw'||e.target!==parent)return;
 const r=parent.getBoundingClientRect();
 drawStart={x:(e.clientX-r.left-(window.ptPan?.x||0))/zoom,y:(e.clientY-r.top-(window.ptPan?.y||0))/zoom};
});
parent.addEventListener('pointerup',e=>{
 if(!drawStart)return;
 const r=parent.getBoundingClientRect(),x=(e.clientX-r.left-(window.ptPan?.x||0))/zoom,y=(e.clientY-r.top-(window.ptPan?.y||0))/zoom,start=drawStart;drawStart=null;
 const w=Math.abs(start.x-x),h=Math.abs(start.y-y);
 if(w<4&&h<4)return;
 shapes.push({id:'shape_'+Date.now(),kind:drawKind,x:Math.round(Math.min(x,start.x)),y:Math.round(Math.min(y,start.y)),w:Math.round(Math.max(10,w)),h:Math.round(Math.max(10,h)),color:drawColor,cluster:currentCluster?.id||null});
 persist();refresh();
});
function toggleViewport(){
 if(window.PacketTrackerTools){window.PacketTrackerTools.toggleViewport();return}
 view.hidden=!view.hidden;
 if(!view.hidden)window.PacketTrackerWorkspace?.updateViewport?.();
}
function refresh(){
 if(state?.clusters){
  clusters=Object.values(state.clusters);
  if(currentCluster)currentCluster=clusters.find(c=>c.id===currentCluster.id)||null;
 }
 if(state?.physical_locations){
  locations=Object.values(state.physical_locations);
  if(currentLocation&&!state.physical_locations[currentLocation])currentLocation=null;
 }
 updateNav();renderPhysicalWorkspace();
 if(mode==='logical'){renderTopology();renderClusters();}
}
const previousTopology=renderTopology;
renderTopology=function(){
 previousTopology();
 if(mode==='logical')renderClusters();
 else{get('nodes').style.display='none';get('wires').style.display='none';}
};
function inspectDevice(name){
 const d=state.devices[name];if(!d)return;
 showDialog('Inspect — '+name,[],()=>{},'View the current simulated device tables.');
 const body=document.querySelector('#ptOverviewDialog .pt-mini-body');
 body.textContent='';
 const choose=document.createElement('select');
 const types=[['arp','ARP Table'],['mac','MAC Address Table'],['routes','Routing Table'],['interfaces','Interfaces']];
 for(const [id,title] of types){const option=document.createElement('option');option.value=id;option.textContent=title;choose.append(option)}
 const pre=document.createElement('pre');pre.className='pt-inspect-data';
 const renderTable=()=>{
  const d=state.devices[name];if(!d)return;
  if(choose.value==='arp')pre.textContent='IPv4 Address               MAC Address\n'+
   (Object.entries(d.arp_table||{}).map(([ip,mac])=>ip.padEnd(26)+mac).join('\n')||'(ARP table empty)');
  else if(choose.value==='mac')pre.textContent='VLAN:MAC                     Port\n'+
   (Object.entries(d.mac_table||{}).map(([mac,port])=>mac.padEnd(28)+port).join('\n')||'(MAC address table empty)');
  else if(choose.value==='routes')pre.textContent='Prefix                     Next hop / Interface\n'+
   ((d.routes||[]).map(r=>r.network.padEnd(27)+(r.next_hop||r.interface||r.source)).join('\n')||'(no static or learned routes)');
  else pre.textContent='Port                   IPv4                    Status\n'+
   Object.values(d.interfaces||{}).map(i=>i.name.padEnd(23)+(i.ip||'unassigned').padEnd(24)+(i.admin_up?'up':'down')).join('\n');
 };
 choose.onchange=renderTable;body.append(choose,pre);renderTable();
}
const previousNodeClick=nodeClick;
nodeClick=function(e,name){
 if(mode!=='logical')return;
 if(activeTool==='inspect'){inspectDevice(name);return;}
 if(activeTool==='pdu-simple'||activeTool==='pdu-complex'){
  if(!selectedPduSource){selectedPduSource=name;statusText('Choose PDU destination');return}
  const source=selectedPduSource;selectedPduSource=null;if(source===name)return;
  openPduEditor(source,name,pduKind);return;
 }
 return previousNodeClick(e,name);
};
function setPduTool(kind){
 pduKind=kind;selectedPduSource=null;setTool('pdu-'+kind);
 statusText('Add '+kind+' PDU: select source, then destination');
}
toolRail.querySelectorAll('[data-tool="pdu"]').forEach((b,i)=>{
 b.title=i?'Add Complex PDU':'Add Simple PDU';b.dataset.tool=i?'pdu-complex':'pdu-simple';
 b.addEventListener('click',e=>{e.stopImmediatePropagation();setPduTool(i?'complex':'simple')},true);
});
async function firePdu(p){
 if(p.protocol!=='ICMP'){
  p.status='Unsupported';statusText('Only ICMP PDU transmission is implemented');persist();renderPduWindow();return;
 }
 const r=await command('pdu '+p.source+' '+p.destination,false);
 p.status=r.output.includes('Successful')?'Successful':'Failed';
 persist();renderPduWindow();
 statusText('ICMP PDU '+p.status+' ('+p.source+' → '+p.destination+')');
}
function openPduEditor(src,dst,kind,existing){
 const record=existing||{};
 const fields=[
  {key:'source',label:'Source',value:record.source||src},
  {key:'destination',label:'Destination',value:record.destination||dst},
  {key:'protocol',label:'Protocol',choices:[['ICMP','ICMP'],['TCP','TCP'],['UDP','UDP']],value:record.protocol||'ICMP'},
  {key:'time',label:'Time (sec)',type:'number',value:String(record.time||'0')},
  {key:'color',label:'PDU color',type:'color',value:record.color||'#17a2b8'}
 ];
 if(kind==='complex')fields.push({key:'periodic',label:'Period (sec, 0 for single fire)',type:'number',value:String(record.periodic||0)});
 showDialog((existing?'Edit ':'Add ')+(kind==='complex'?'Complex':'Simple')+' PDU',fields,data=>{
  if(!state.devices[data.source]||!state.devices[data.destination]){statusText('Select source/destination devices currently in topology');return false}
  if(!Number.isFinite(+data.time)||+data.time<0)return false;
  const entry={id:existing?.id||'pdu_'+Date.now(),source:data.source,destination:data.destination,
    protocol:data.protocol,time:+data.time,color:data.color,periodic:+(data.periodic||0),scenario:simScenario,kind,status:'Not sent'};
  if(existing){pdus=pdus.map(p=>p.id===entry.id?entry:p)}else pdus.push(entry);
  persist();renderPduWindow();statusText('PDU '+entry.protocol+' created');if(!existing&&kind==='simple')firePdu(entry);
 },'Simple ICMP PDUs are backed by simulated network reachability. TCP/UDP PDU types remain UI-only. Simulation mode replays the generated trace.');
}
function renderPduWindow(){
 if(state.simulation)return;
 const host=get('eventList');if(!host)return;
 host.innerHTML='';
 const entries=pdus.filter(x=>x.scenario===simScenario&&state.devices[x.source]&&state.devices[x.destination]);
 if(!entries.length){host.appendChild(elem('div','empty-small','No user-created PDUs. Use Add Simple or Complex PDU.'));return}
 entries.forEach((p,i)=>{
  const row=elem('div','pdu-row');row.title='ICMP test messages use simulated network reachability; other protocol PDUs are not yet modeled';
  const cells=[
   ['Fire','▶',()=>firePdu(p)],
   ['Last Status',p.status||'Not sent'],['Source',p.source],['Destination',p.destination],
   ['Type',p.protocol],['Color','■',()=>showDialog('PDU Color',[{key:'color',label:'Color',type:'color',value:p.color}],d=>{p.color=d.color;persist();renderPduWindow()})],
   ['Time(sec)',String(p.time)],['Periodic',p.periodic?'Y':'N'],['Num',String(i+1)],
   ['Edit','✎',()=>openPduEditor(p.source,p.destination,p.kind,p)],
   ['Delete','×',()=>{pdus=pdus.filter(x=>x.id!==p.id);persist();renderPduWindow()}]
  ];
  cells.forEach(([title,label,onclick])=>{
   const cell=elem('span','',null);cell.title=title;
   if(onclick){const btn=elem('button','pt-pdu-action',label);btn.onclick=onclick;cell.appendChild(btn)}
   else cell.textContent=label;
   if(title==='Color')cell.style.color=p.color;
   row.appendChild(cell);
  });host.appendChild(row);
 });
}
const previousEvents=renderEvents;
renderEvents=function(){if(state.simulation)return;previousEvents();renderPduWindow()};
function renderScenarioSelect(){
 const select=document.querySelector('.scenario-row select');if(!select)return;
 select.innerHTML='';
 scenarioNames.forEach((name,i)=>{const opt=elem('option','',name);opt.value=i;select.appendChild(opt)});
 simScenario=Math.min(simScenario,scenarioNames.length-1);
 select.value=simScenario;
}
renderScenarioSelect();
document.querySelector('.scenario-row select').onchange=e=>{simScenario=+e.target.value;renderPduWindow()};
get('scenarioNewBtn').onclick=()=>{scenarioNames.push('Scenario '+scenarioNames.length);simScenario=scenarioNames.length-1;persist();renderScenarioSelect();renderPduWindow()};
get('scenarioDeleteBtn').onclick=()=>{
 if(scenarioNames.length===1)return info('Delete Scenario','The default Scenario 0 cannot be deleted.');
 const id=simScenario;pdus=pdus.filter(p=>p.scenario!==id);pdus.forEach(p=>{if(p.scenario>id)p.scenario--});
 scenarioNames.splice(id,1);scenarioDescriptions.splice(id,1);simScenario=0;persist();renderScenarioSelect();renderPduWindow();
};
document.querySelector('.info-button').onclick=()=>showDialog('Scenario Information',[
 {key:'name',label:'Scenario name',value:scenarioNames[simScenario]},
 {key:'description',label:'Description',multiline:true,value:scenarioDescriptions[simScenario]||''}
],data=>{scenarioNames[simScenario]=data.name.trim()||scenarioNames[simScenario];scenarioDescriptions[simScenario]=data.description;persist();renderScenarioSelect();});
const pduPane=get('pduPane'),originalParent=pduPane.parentNode;
const float=elem('section');float.id='ptPduWindow';float.hidden=true;
const floatHeader=elem('header','',null),floatTitle=elem('strong','','User Created Packet Window');
const redock=elem('button','','Dock ↙');redock.title='Return Protocol Data Units List to lower-right panel';
floatHeader.append(floatTitle,redock);float.appendChild(floatHeader);document.body.appendChild(float);
let detached=false;
function setDetached(next){
 detached=next;float.hidden=!detached;
 if(detached){float.appendChild(pduPane);get('rightDock').classList.add('pdu-undocked');get('rightDock').classList.remove('pdu-hidden')}
 else{originalParent.appendChild(pduPane);get('rightDock').classList.remove('pdu-undocked');}
 get('pduToggleBtn').textContent=detached?'Dock PDU List Window':'Toggle PDU List Window';
}
get('pduToggleBtn').onclick=()=>setDetached(!detached);redock.onclick=()=>setDetached(false);
const rightHandle=get('rightColumnSplitter'),rightChevron=rightHandle.querySelector('span');
let panelStart=null;
rightHandle.title='Drag to resize; click to collapse or expand User Created Packet Window';
rightHandle.addEventListener('pointerdown',e=>{panelStart=e.clientX});
rightHandle.addEventListener('pointerup',e=>{
 if(panelStart===null)return;
 const still=Math.abs(e.clientX-panelStart)<3;panelStart=null;
 if(!still)return;
 document.body.classList.toggle('pt-ucpw-hidden');
 rightChevron.textContent=document.body.classList.contains('pt-ucpw-hidden')?'◀':'▶';
 statusText(document.body.classList.contains('pt-ucpw-hidden')?'User Created Packet Window collapsed':'User Created Packet Window expanded');
});
const strip=document.querySelector('#timeStrip .play-controls'),extra=elem('div','pt-time-extra');
const powerBtn=elem('button','','Power Cycle Devices'),fastBtn=elem('button','','Fast Forward Time');
powerBtn.title='Power Cycle Devices (requires explicit confirmation)';
fastBtn.title='Fast Forward Time';
powerBtn.id='powerCycleBtn';fastBtn.id='fastForwardBtn';
for(const [button,icon] of [[powerBtn,'power'],[fastBtn,'fast']]){
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.classList.add('control-icon');svg.setAttribute('aria-hidden','true');
 const use=document.createElementNS('http://www.w3.org/2000/svg','use');use.setAttribute('href','/control-icons.svg#'+icon);svg.append(use);button.prepend(svg);
}
powerBtn.onclick=async()=>{
 if(!confirm('Power cycle every simulated device? IP configuration stays, but ARP/MAC and packet history are cleared.'))return;
 const r=await command('power-cycle',false);
 statusText(r.output);
};
fastBtn.onclick=()=>get('stepForwardBtn').click();
extra.append(powerBtn,fastBtn);strip.append(extra);
const printBtn=[...get('mainToolbar').querySelectorAll('button')].find(b=>b.title==='Print');
if(printBtn){printBtn.disabled=false;printBtn.onclick=()=>window.print()}
const tooltipSelectors='button[title],.node[title],.palette-device[title],.subtype[title],.pt-location[title]';
let timer;
document.addEventListener('pointerover',e=>{
 const n=e.target.closest?.(tooltipSelectors);
 clearTimeout(timer);tip.hidden=true;if(!n?.title)return;
 timer=setTimeout(()=>{const r=n.getBoundingClientRect();tip.textContent=n.title;tip.style.left=Math.max(0,Math.min(innerWidth-300,r.left))+'px';tip.style.top=Math.min(innerHeight-50,r.bottom+5)+'px';tip.hidden=false},700);
});
document.addEventListener('pointerout',()=>{clearTimeout(timer);tip.hidden=true});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'){
  menu.hidden=true;drawMenu.hidden=true;if(!modal.hidden){modalClose();e.stopImmediatePropagation()}
  if(activeTool!=='select'&&!e.target.matches('input,textarea'))setTool('select');
 }
});
const originalInitState=fetchState;
fetchState=async function(){await originalInitState();refresh();renderPduWindow()};
const originalCommand=command;
command=async function(cmd,echo=true){const result=await originalCommand(cmd,echo);if(result?.ok)refresh();return result;};
refresh();renderPduWindow();
})();
