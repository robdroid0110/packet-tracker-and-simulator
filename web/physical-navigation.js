/* vendor Help §16: Physical navigation tree and Move Object workflows.
   All writes go through /api/physical-workspace/action; no local-only relocations. */
(() => {
'use strict';
const byId=id=>document.getElementById(id);
const dialog=document.createElement('section');
dialog.id='ptPhysicalNavDialog';
dialog.hidden=true;
dialog.setAttribute('role','dialog');
dialog.setAttribute('aria-modal','true');
dialog.setAttribute('aria-labelledby','ptPhysicalNavTitle');
dialog.innerHTML=[
 '<div class="pt-physical-nav-window">',
 '<header><strong id="ptPhysicalNavTitle">Physical Workspace — Navigation</strong>',
 '<button id="ptNavRefresh">Refresh</button>',
 '<button id="ptNavClose" aria-label="Close navigation">×</button></header>',
 '<div class="pt-physical-nav-toolbar">',
 '<span id="ptNavPicked">Select a device or container to move.</span>',
 '<button id="ptNavExpand">Expand all</button>',
 '<button id="ptNavCollapse">Collapse all</button>',
 '<button id="ptNavUndo">Undo</button><button id="ptNavRedo">Redo</button></div>',
 '<div class="pt-physical-nav-tree" id="ptNavTree" aria-label="Physical locations and devices"></div>',
 '<footer><span id="ptNavStatus" role="status" aria-live="polite">',
 'Select one or more devices, then choose a destination.</span>',
 '<button id="ptNavDone">Close</button></footer></div>'
].join('');
document.body.append(dialog);
const hint=document.createElement('aside');
hint.id='ptMoveObjectHint';hint.hidden=true;
hint.innerHTML='<span>Move Object: click a device or container on the physical map to choose its destination.</span> <button type="button" id="ptMoveObjectCancel">Cancel</button>';
byId('workspace').append(hint);

let tree=null,selectedDevices=new Set(),selectedContainer=null;
let armed=false,focusReturn=null,busy=false;
const status=(message,error=false)=>{
 const box=byId('ptNavStatus');box.textContent=message;box.classList.toggle('error',error);
};
const selectSummary=()=>{
 const names=[...selectedDevices].join(', ');
 const label=selectedContainer?'Container '+selectedContainer:
    names?selectedDevices.size+' device(s): '+names:'Select devices or a container to relocate';
 byId('ptNavPicked').textContent=label;
};
function setArmed(value){
 armed=!!value;hint.hidden=!armed;document.body.classList.toggle('pt-move-object-armed',armed);
}
function close(){
 dialog.hidden=true;
 selectedContainer=null;selectedDevices.clear();setArmed(false);
 focusReturn?.focus?.();
}
function armMove(){
 if(!byId('ptPhysicalWorkspace')||byId('ptPhysicalWorkspace').hidden){
  document.querySelectorAll('.workspace-tab')[1]?.click();
 }
 setArmed(!armed);
}
async function request(path,options){
 const response=await fetch(path,options);
 const payload=await response.json();
 if(!response.ok||payload.ok===false)
  throw Error(payload.error||payload.output||'Physical Workspace request failed');
 return payload;
}
async function refresh(){
 if(busy)return;
 try{
  tree=(await request('/api/physical-workspace/tree')).tree;
  const locations=new Set();
  const devices=new Set();
  function walk(node){
   locations.add(node.id);for(const d of node.devices)devices.add(d.name);
   for(const child of node.children)walk(child);
  }
  walk(tree);
  selectedDevices=new Set([...selectedDevices].filter(n=>devices.has(n)));
  if(selectedContainer&&!locations.has(selectedContainer))selectedContainer=null;
  drawTree();selectSummary();
 }catch(error){status(error.message,true)}
}
function open(options={}){
 focusReturn=document.activeElement;
 dialog.hidden=false;setArmed(false);
 selectedDevices=new Set(options.device?[options.device]:[]);
 selectedContainer=options.container||null;
 status('Select a destination using Move here, or drag an object onto a location.');
 refresh().then(()=>byId('ptNavTree').querySelector('button')?.focus());
}
function chooseDevice(name,checked){
 if(checked){
  selectedContainer=null;selectedDevices.add(name);
 }else selectedDevices.delete(name);
 selectSummary();
}
function chooseContainer(id){
 selectedDevices.clear();selectedContainer=id;drawTree();selectSummary();
 status('Container selected. Choose a valid destination; self/child moves are blocked.');
}
function treeNode(node,level=0){
 const branch=document.createElement('details');
 branch.className='pt-nav-branch';branch.open=true;
 branch.dataset.location=node.id;
 const heading=document.createElement('summary');
 heading.className='pt-nav-location-row';
 heading.dataset.destination=node.id;
 heading.draggable=node.id!=='intercity';
 heading.title='Drag this container to another location to relocate it';
 const label=document.createElement('span');
 label.className='pt-nav-place-label';
 label.textContent=node.type.toUpperCase()+' · '+node.name;
 if(node.id===selectedContainer)heading.classList.add('selected');
 const focus=document.createElement('button');focus.textContent='Open';
 focus.dataset.focusLocation=node.id;focus.setAttribute('aria-label','Open '+node.name);
 const choose=document.createElement('button');
 choose.textContent='Select';choose.dataset.chooseLocation=node.id;
 choose.disabled=node.id==='intercity';choose.title='Select this container as the object to move';
 const dest=document.createElement('button');dest.textContent='Move here';
 dest.dataset.destinationButton=node.id;
 dest.title='Move the selected device(s) or container into '+node.name;
 heading.append(label,focus,choose,dest);
 branch.append(heading);
 if(level>20)return branch;
 for(const d of node.devices){
  const row=document.createElement('div');
  row.className='pt-nav-device-row';
  row.draggable=true;row.dataset.device=d.name;
  row.title='Drag onto a location row to move this device';
  const checkbox=document.createElement('input');
  checkbox.type='checkbox';checkbox.dataset.checkDevice=d.name;
  checkbox.checked=selectedDevices.has(d.name);
  checkbox.setAttribute('aria-label','Select '+d.name+' for physical relocation');
  const name=document.createElement('span');
  name.textContent=d.name+' · '+d.kind+' · '+d.surface+(d.powered?' (on)':' (off)');
  row.append(checkbox,name);
  branch.append(row);
 }
 for(const child of node.children)branch.append(treeNode(child,level+1));
 return branch;
}
function drawTree(){
 const host=byId('ptNavTree');
 host.replaceChildren(treeNode(tree));
}
async function mutate(action){
 if(busy)return false;
 busy=true;
 try{
  const data=await request('/api/physical-workspace/action',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify(action),
  });
  status(data.output||'Updated');
  await fetchState(); // Refresh the same authoritative lab used by the main GUI.
  return true;
 }catch(error){status(error.message,true);return false}
 finally{busy=false}
}
async function moveTo(location,explicit=null){
 if(!tree)return;
 const source=explicit||(
   selectedContainer?{type:'location',id:selectedContainer}:
   {type:'devices',names:[...selectedDevices]}
 );
 if(source.type==='location'){
  if(source.id==='intercity'){status('Intercity cannot be moved.',true);return}
  if(source.id===location){status('Choose a different destination.',true);return}
  if(await mutate({action:'relocate_location',location:source.id,parent:location})){
   selectedContainer=null;await refresh();
  }
 }else{
  const names=source.names||[];
  if(!names.length){status('Select one or more devices first.',true);return}
  if(await mutate({action:'move_devices',devices:names,location})){
   selectedDevices.clear();await refresh();
  }
 }
}
byId('ptNavClose').onclick=byId('ptNavDone').onclick=close;
byId('ptNavRefresh').onclick=refresh;
byId('ptNavExpand').onclick=()=>dialog.querySelectorAll('details.pt-nav-branch').forEach(n=>n.open=true);
byId('ptNavCollapse').onclick=()=>dialog.querySelectorAll('details.pt-nav-branch').forEach(n=>n.open=false);
byId('ptNavUndo').onclick=async()=>{if(await mutate({action:'undo'}))await refresh()};
byId('ptNavRedo').onclick=async()=>{if(await mutate({action:'redo'}))await refresh()};
byId('ptMoveObjectCancel').onclick=()=>setArmed(false);
document.querySelectorAll('.workspace-tab')[0]?.addEventListener('click',()=>setArmed(false));
const list=byId('ptNavTree');
list.addEventListener('change',event=>{
 const name=event.target.dataset?.checkDevice;
 if(name)chooseDevice(name,event.target.checked);
});
list.addEventListener('click',event=>{
 const button=event.target.closest('button');
 if(!button)return;
 event.preventDefault();event.stopPropagation();
 if(button.dataset.focusLocation){
  const location=button.dataset.focusLocation;
  close();window.dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location}}));
 }else if(button.dataset.chooseLocation){
  chooseContainer(button.dataset.chooseLocation);
 }else if(button.dataset.destinationButton){
  moveTo(button.dataset.destinationButton);
 }
});
list.addEventListener('dragstart',event=>{
 const row=event.target.closest('[data-device]');
 const loc=event.target.closest('summary[data-destination]');
 if(row){
  const name=row.dataset.device;
  const names=selectedDevices.has(name)?[...selectedDevices]:[name];
  event.dataTransfer.setData('application/x-pt-physical-move',
     JSON.stringify({type:'devices',names}));
 }else if(loc&&loc.dataset.destination!=='intercity'){
  event.dataTransfer.setData('application/x-pt-physical-move',
     JSON.stringify({type:'location',id:loc.dataset.destination}));
 }else{event.preventDefault()}
});
list.addEventListener('dragover',event=>{
 const row=event.target.closest('summary[data-destination]');
 if(!row||!event.dataTransfer.types.includes('application/x-pt-physical-move'))return;
 event.preventDefault();event.dataTransfer.dropEffect='move';
});
list.addEventListener('drop',event=>{
 const dest=event.target.closest('summary[data-destination]');if(!dest)return;
 let payload;
 try{payload=JSON.parse(event.dataTransfer.getData('application/x-pt-physical-move'))}
 catch{return}
 event.preventDefault();event.stopPropagation();
 if(payload?.type==='devices'||payload?.type==='location')moveTo(dest.dataset.destination,payload);
});
dialog.addEventListener('pointerdown',event=>{if(event.target===dialog)close()});
document.addEventListener('keydown',event=>{
 if(dialog.hidden)return;
 if(event.key==='Escape'){
  event.preventDefault();event.stopImmediatePropagation();close();return;
 }
 if(event.key==='Tab'){
  const focusable=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled])')]
   .filter(el=>el.getClientRects().length);
  if(!focusable.length)return;
  const first=focusable[0],last=focusable[focusable.length-1];
  if(event.shiftKey&&document.activeElement===first){event.preventDefault();last.focus()}
  else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first.focus()}
 }
},true);
window.PacketTrackerPhysicalNav={
 open,close,refresh,armMove,
 get armed(){return armed},
 get tree(){return tree},
 get selectedDevices(){return [...selectedDevices]},
 get selectedContainer(){return selectedContainer}
};
})();
