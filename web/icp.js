/* legacy network simulator Help §20 — Industrial Control Panel.
 * Authoritative persistence and 20-unit snapping live in netsim/icp.py.
 * DIN/WIC strips are layout fixtures, NOT electrical wiring.
 */
(() => {
'use strict';
const host=document.getElementById('ptPhysicalWorkspace');
if(!host)return;
const cell=(tag,cls,text)=>{
 const n=document.createElement(tag);
 if(cls)n.className=cls;
 if(text!==undefined)n.textContent=String(text);
 return n;
};
let current=null,activeDrag=null,pending=false;
const STEP=20;
function message(text,fail=false){
 const el=document.getElementById('ptIcpFeedback');
 if(el){el.textContent=text;el.classList.toggle('error',fail)}
 const bar=document.getElementById('statusText');
 if(bar)bar.textContent=text;
}
function findPanel(id=current){return state.icp_panels?.[id]}
function refresh(id=current){
 if(!id)return;
 window.dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location:id}}));
}
async function mutate(payload,id=current){
 if(pending)return null;
 pending=true;
 try{
  const r=await fetch('/api/icp/action',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify(payload)});
  const d=await r.json();
  if(!r.ok||!d.ok)throw Error(d.error||d.output||'ICP operation failed');
  state=d.state;
  if(id)refresh(id);
  message(d.output);
  return d;
 }catch(error){message(error.message,true);return null}
 finally{pending=false}
}
const isReadOnly=()=>!!findPanel()?.workspace_mode;
async function create(name,size,parent){
 if(!name?.trim())return message('Give the ICP a name.',true);
 const result=await mutate({action:'create',name:name.trim(),size,parent},null);
 if(result){
  // Keep view in containing location so user can locate the new ICP icon.
  refresh(parent);
 }
 return result;
}
function setPreview(location,enabled){
 return mutate({action:'preview',location,enabled},location);
}
function setDoor(location,closed){
 return mutate({action:'door',location,closed},location);
}
function snap(n){
 return Math.max(0,Math.min(1000,Math.round(n/STEP)*STEP));
}
function percent(n){return Math.max(0,Math.min(100,Number(n)/10))+'%'}
function xy(event,pane){
 const box=pane.getBoundingClientRect();
 const x=snap((event.clientX-box.left)/Math.max(1,box.width)*1000);
 const y=snap((event.clientY-box.top)/Math.max(1,box.height)*1000);
 return {x,y};
}
function xyAt(clientX,clientY,pane){
 const box=pane.getBoundingClientRect();
 return {x:snap((clientX-box.left)/Math.max(1,box.width)*1000),
         y:snap((clientY-box.top)/Math.max(1,box.height)*1000)};
}
function tool(label,onClick,title=''){
 const b=cell('button','pt-icp-tool',label);
 b.type='button';b.onclick=onClick;
 if(title)b.title=title;
 return b;
}
function toParent(id){
 const parent=state.physical_locations?.[id]?.parent||'intercity';
 window.dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location:parent}}));
}
function mountNear(device,id,pointer){
 const panel=findPanel(id);
 if(!panel)return;
 const din=Object.values(panel.fixtures).filter(f=>f.kind==='din');
 const nearest=din.map(f=>({f,dist:Math.hypot(f.x-pointer.x,f.y-pointer.y)}))
  .sort((a,b)=>a.dist-b.dist)[0];
 if(nearest?.dist<65){
  return mutate({action:'mount',device,fixture:nearest.f.id},id);
 }
}
function startDeviceDrag(node,device,event,side){
 if(isReadOnly()||event.button!==0)return;
 if(event.target.closest('button')&&!event.target.classList.contains('pt-icp-device-open'))return;
 event.preventDefault();event.stopPropagation();
 const startX=event.clientX,startY=event.clientY;
 const panel=findPanel();
 let anchor=panel.anchors?.[device.device]??device.anchor??0;
 let moved=false,lastEvent=event;
 node.setPointerCapture(event.pointerId);
 node.classList.add('dragging');
 const onKey=e=>{
  if(e.key==='Tab'){
   e.preventDefault();
   anchor=(anchor+1)%6;
   node.dataset.snapAnchor=String(anchor);
   const indicator=node.querySelector('.pt-icp-snap-indicator');
   if(indicator)indicator.textContent='Anchor '+(anchor+1)+'/6';
  }
 };
 document.addEventListener('keydown',onKey,true);
 const move=e=>{
  lastEvent=e;
  if(Math.hypot(e.clientX-startX,e.clientY-startY)<3&&!moved)return;
  moved=true;
  const dest=e.shiftKey?
   (document.elementFromPoint(e.clientX,e.clientY)?.closest('.pt-icp-pane')||node.closest('.pt-icp-pane')):
   node.closest('.pt-icp-pane');
  if(dest){
   const p=xy(e,dest);
   node.style.left=percent(p.x);
   node.style.top=percent(p.y);
  }
 };
 const up=async e=>{
  node.removeEventListener('pointermove',move);
  node.removeEventListener('pointerup',up);
  node.removeEventListener('pointercancel',cancel);
  document.removeEventListener('keydown',onKey,true);
  node.classList.remove('dragging');
  if(!moved)return;
  const dest=(e.shiftKey?
   document.elementFromPoint(e.clientX,e.clientY)?.closest('.pt-icp-pane'):
   null)||node.closest('.pt-icp-pane');
  const targetSide=e.shiftKey&&dest?.dataset.side?dest.dataset.side:side;
  const pane=host.querySelector('.pt-icp-pane[data-side="'+targetSide+'"]');
  if(!pane)return refresh(current);
  const location=current;
  const p=xyAt(e.clientX,e.clientY,pane);
  const changed=await mutate({action:'device_move',device:device.device,side:targetSide,
   x:p.x,y:p.y,anchor,detach:!!e.ctrlKey},location);
  if(changed&&targetSide==='cabinet'&&!device.mount&&!e.ctrlKey)await mountNear(device.device,location,p);
 };
 const cancel=()=>{
  node.removeEventListener('pointermove',move);
  node.removeEventListener('pointerup',up);
  document.removeEventListener('keydown',onKey,true);
  node.classList.remove('dragging');
  refresh(current);
 };
 node.addEventListener('pointermove',move);
 node.addEventListener('pointerup',up,{once:true});
 node.addEventListener('pointercancel',cancel,{once:true});
}
function fixtureInteraction(node,item,loc){
 if(isReadOnly())return;
 node.addEventListener('pointerdown',event=>{
  if(event.button!==0||event.target.closest('button'))return;
  event.preventDefault();event.stopPropagation();
  node.setPointerCapture(event.pointerId);
  const sx=event.clientX,sy=event.clientY;
  let moved=false;
  const onMove=e=>{
   if(Math.hypot(e.clientX-sx,e.clientY-sy)>3)moved=true;
   if(moved){
    const pane=node.closest('.pt-icp-pane');
    const p=xy(e,pane);
    node.style.left=percent(p.x);node.style.top=percent(p.y);
   }
  };
  const onUp=async e=>{
   node.removeEventListener('pointermove',onMove);
   node.removeEventListener('pointerup',onUp);
   if(!moved)return;
   const pane=node.closest('.pt-icp-pane');
   const p=xyAt(e.clientX,e.clientY,pane);
   const updated=await mutate({action:'fixture_move',location:loc,fixture:item.id,x:p.x,y:p.y,detach:!!e.ctrlKey},loc);
   if(!updated||e.ctrlKey)return;
   const panel=findPanel(loc);
   const other=Object.values(panel?.fixtures||{}).find(f=>
     f.id!==item.id&&f.kind===item.kind&&f.orientation===item.orientation&&
     Math.hypot(f.x-p.x,f.y-p.y)<90&&!f.group);
   if(other)await mutate({action:'fixture_join',location:loc,fixture:item.id,other:other.id},loc);
  };
  node.addEventListener('pointermove',onMove);
  node.addEventListener('pointerup',onUp,{once:true});
 });
}
function addFixture(kind,orientation){
 if(isReadOnly())return;
 const count=Object.keys(findPanel()?.fixtures||{}).length;
 const x=120+(count%5)*150,y=150+Math.floor(count/5)*130;
 mutate({action:'fixture_add',location:current,kind,orientation,x,y});
}
async function placeNew(name,side,clientX,clientY){
 const pane=host.querySelector('.pt-icp-pane[data-side="'+side+'"]');
 const p=pane?xyAt(clientX,clientY,pane):{x:200,y:160};
 return mutate({action:'device_move',device:name,side,x:p.x,y:p.y,anchor:0,detach:false});
}
function fixtureElement(item,loc,previewMode){
 const cls='pt-icp-fixture pt-icp-fixture-'+item.kind+' '+item.orientation+
           (item.group?' grouped':'');
 const f=cell('div',cls);
 f.dataset.fixture=item.id;
 f.style.left=percent(item.x);f.style.top=percent(item.y);
 const label=cell('span','',item.kind.toUpperCase()+(item.group?' · joined':''));
 f.append(label);
 if(!previewMode){
  if(item.group)f.append(tool('Split',e=>mutate({action:'fixture_split',location:loc,fixture:item.id},loc)));
  f.append(tool('×',e=>mutate({action:'fixture_delete',location:loc,fixture:item.id},loc),'Remove fixture without deleting mounted devices'));
 }
 f.title=item.kind.toUpperCase()+' · '+item.orientation+
  (item.group?' · group '+item.group:'')+(previewMode?'':' · drag to position; Ctrl-drag splits connected strips');
 fixtureInteraction(f,item,loc);
 return f;
}
function deviceElement(device,loc,side,readOnly,doorOpen){
 const n=cell('div','pt-icp-device');
 n.dataset.device=device.device;n.dataset.snapAnchor=String(device.anchor);
 if(device.mount)n.classList.add('mounted');
 n.style.left=percent(device.x);n.style.top=percent(device.y);
 const face=cell('button','pt-icp-device-open',
   (side==='door'&&doorOpen?'↶ ':'')+device.device);
 face.type='button';face.title='Open device '+device.device+' (double-click)';
 face.addEventListener('dblclick',e=>{
  e.stopPropagation();
  if(typeof openDevice==='function')openDevice(device.device);
 });
 const detail=cell('small','',device.model||'device');
 const indicator=cell('small','pt-icp-snap-indicator',
  device.mount?'DIN '+device.mount:'Anchor '+(device.anchor+1)+'/6');
 n.append(face,detail,indicator);
 if(device.powered)n.classList.add('powered');
 n.title=device.device+(device.mount?' · DIN mounted':'')+
  ' · '+side+(readOnly?' · preview (read-only)':' · drag, Shift=other side, Ctrl=detach, Tab=snap anchor');
 if(!readOnly)startDeviceDragSetter(n,device,side);
 return n;
}
function startDeviceDragSetter(node,device,side){
 node.addEventListener('pointerdown',event=>startDeviceDrag(node,device,event,side));
}
function renderCables(wrapper,loc,readOnly){
 const locals=Object.keys(state.devices||{}).filter(n=>state.device_locations?.[n]===loc);
 const links=state.links.filter(l=>locals.includes(l.a_device)||locals.includes(l.b_device));
 const section=cell('section','pt-icp-network');
 section.append(cell('strong','', 'Cabinet Network Connections · '+links.length));
 const note=cell('p','pt-icp-cable-hint',
  'These are real simulated Ethernet links. DIN rails and WIC conduits do not carry electrical signals.');
 section.append(note);
 const listing=cell('div','pt-icp-link-list');
 for(const link of links){
  const row=cell('div','pt-icp-link '+(link.up?'online':'offline'));
  const label=cell('span','',link.a_device+':'+link.a_if+' ↔ '+link.b_device+':'+link.b_if+
   ' · '+(link.up?'UP':'DOWN')+(link.status&&link.status!=='operational'?' · '+link.status:''));
  row.append(label);
  if(!readOnly){
   const remove=tool('Disconnect',async()=>{
    const cmd='disconnect '+link.a_device+' '+link.a_if;
    if(!window.confirm('Disconnect '+link.a_device+':'+link.a_if+' from '+link.b_device+':'+link.b_if+'?'))return;
    await networkCommand(cmd,loc);
   });
   remove.setAttribute('aria-label','Disconnect '+link.a_device+' from '+link.b_device);
   row.append(remove);
  }
  listing.append(row);
 }
 if(!links.length)listing.append(cell('p','pt-icp-cable-hint','No network cables attached to devices in this ICP.'));
 section.append(listing);
 if(!readOnly&&locals.length>1){
  const form=cell('div','pt-icp-connect-form');
  const source=cell('select'),target=cell('select'),sourcePort=cell('select'),targetPort=cell('select');
  for(const name of locals){
   const left=cell('option','',name);left.value=name;source.append(left);
   const right=cell('option','',name);right.value=name;target.append(right);
  }
  if(locals.length>1)target.value=locals[1];
  const assigned=new Set(state.links.flatMap(l=>[l.a_device+':'+l.a_if,l.b_device+':'+l.b_if]));
  function fillPorts(select,deviceName){
   select.replaceChildren();
   const dev=state.devices[deviceName];
   for(const iface of Object.values(dev?.interfaces||{})){
    if(iface.parent||assigned.has(deviceName+':'+iface.name))continue;
    const op=cell('option','',iface.name);op.value=iface.name;select.append(op);
   }
  }
  const update=()=>{
   fillPorts(sourcePort,source.value);fillPorts(targetPort,target.value);
  };
  source.onchange=update;target.onchange=update;update();
  for(const [select,name] of (([[source,'First device'],[sourcePort,'First port'],[target,'Second device'],[targetPort,'Second port']]))){
   select.setAttribute('aria-label',name);
   const label=cell('label','',name);label.append(select);form.append(label);
  }
  const link=tool('Connect Auto Ethernet',async()=>{
   if(!source.value||!target.value||!sourcePort.value||!targetPort.value||source.value===target.value)
    return message('Choose two different devices with unused Ethernet ports.',true);
   await networkCommand('connect '+source.value+' '+sourcePort.value+' '+target.value+' '+targetPort.value+' auto',loc);
  });
  form.append(link);section.append(form);
 }
 wrapper.append(section);
}
async function networkCommand(command,loc){
 if(pending)return;
 pending=true;
 try{
  const resp=await fetch('/api/command',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify({command})});
  const result=await resp.json();
  if(!resp.ok||!result.ok)throw Error(result.error||result.output||'Network action failed');
  state=result.state;
  refresh(loc);
  message(result.output);
 }catch(error){message(error.message,true)}
 finally{pending=false}
}
function render(layer,loc){
 current=loc;
 const info=state.physical_locations?.[loc],panel=findPanel(loc);
 if(!info||!panel){layer.append(cell('p','pt-icp-error','Industrial panel state unavailable'));return}
 const readOnly=panel.workspace_mode,doorOpen=!panel.door_closed;
 const wrapper=cell('div','pt-icp-workspace'+(readOnly?' preview-mode':'')+(doorOpen?' door-open':' door-closed'));
 wrapper.dataset.icp=loc;
 const titlebar=cell('section','pt-icp-toolbar');
 titlebar.append(
  cell('strong','',info.name+' · '+panel.size+' ICP'),
  tool(doorOpen?'Close Door':'Open Door',()=>setDoor(loc,doorOpen),'Click rectangular door handle to toggle'),
  tool(readOnly?'Exit Preview':'Preview Closed Door',()=>setPreview(loc,!readOnly)),
  tool('Back',()=>toParent(loc),'Return to containing Physical Workspace')
 );
 if(!readOnly){
  const menu=cell('select','pt-icp-addmenu');
  const options=[
    ['','Add DIN / Wire Conduit…'],
    ['din:horizontal','DIN Rail · Horizontal'],
    ['wic:horizontal','Wire Conduit · Horizontal'],
    ['wic:vertical','Wire Conduit · Vertical']
  ];
  for(const [value,label] of options){
   const option=cell('option','',label);
   option.value=value;menu.append(option);
  }
  menu.setAttribute('aria-label','Add DIN rail or wire conduit');
  menu.onchange=()=>{if(menu.value){const [kind,orientation]=menu.value.split(':');addFixture(kind,orientation);menu.value=''}};
  titlebar.prepend(menu);
 }
 wrapper.append(titlebar);
 const hint=cell('p','pt-icp-instructions',readOnly?
   'ICP Workspace Mode · closed-door preview, editing disabled. Double-click an accessible door device to open it. Click the door handle to enter the cabinet.':
   'Drag equipment to position it. Shift+drag transfers between cabinet and door; Tab during drag cycles six snap anchors. Ctrl+drag detaches a DIN-mounted device or strip. 20-unit dot-grid snapping is model-backed.');
 wrapper.append(hint);
 const surface=cell('div','pt-icp-panels');
 const door=cell('section','pt-icp-pane pt-icp-door');
 door.dataset.side='door';
 door.setAttribute('aria-label','Industrial control panel door');
 const cabinet=cell('section','pt-icp-pane pt-icp-cabinet');
 cabinet.dataset.side='cabinet';
 cabinet.setAttribute('aria-label','Industrial control cabinet');
 door.append(cell('h3','',doorOpen?'Door · back side':'Door · front side'));
 cabinet.append(cell('h3','','Cabinet · DIN rails / conduits'));
 const handle=tool('▯',event=>{
  if(event.shiftKey){
   setPreview(loc,!readOnly).then(()=>{if(readOnly)toParent(loc)});
  }else if(readOnly)setDoor(loc,false);
  else setDoor(loc,doorOpen);
 },'Door handle; click to open/close, Shift-click to toggle workspace preview');
 handle.className='pt-icp-handle';
 handle.setAttribute('aria-label',readOnly?'Open door and exit preview':'Toggle ICP door');
 door.append(handle);
 if(readOnly){
  door.addEventListener('click',e=>{
   if(e.target===door)setDoor(loc,false);
  });
 }
 for(const f of Object.values(panel.fixtures)){
  cabinet.append(fixtureElement(f,loc,readOnly));
 }
 for(const [name,d] of Object.entries(state.devices||{})){
  if(state.device_locations?.[name]!==loc)continue;
  const detail=state.physical_device_details?.[name]||{};
  const side=detail.surface==='door'?'door':'cabinet';
  const item={device:name,model:d.model||d.kind,powered:d.powered,
   side,x:detail.x??200,y:detail.y??160,
   anchor:panel.anchors?.[name]??0,mount:panel.mounts?.[name]||null};
  const n=deviceElement(item,loc,side,readOnly,doorOpen);
  (side==='door'?door:cabinet).append(n);
 }
 const rail=cell('p','pt-icp-noelectrical',
  'DIN/WIC are positioning fixtures only. Devices keep their ordinary network ports and cables.');
 cabinet.append(rail);
 surface.append(door,cabinet);wrapper.append(surface);
 renderCables(wrapper,loc,readOnly);
 const feedback=cell('p','pt-icp-feedback');feedback.id='ptIcpFeedback';
 feedback.setAttribute('role','status');feedback.setAttribute('aria-live','polite');
 wrapper.append(feedback);
 layer.append(wrapper);
 // Device-model palette Drop is handled by the parent Physical Workspace.
 // No front-panel electrical simulation or industrial PLC control is invented.
}
window.PacketTrackerICP={create,setPreview,setDoor,placeNew,render,
 get currentLocation(){return current},get panel(){return findPanel()}};
})();
