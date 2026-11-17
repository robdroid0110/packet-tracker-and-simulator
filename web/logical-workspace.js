/* Section 13 Logical Workspace: select, marquee, group drag, copy/paste and undo/redo.
 * Every persistent edit goes through the same agent command processor.
 */
(() => {
'use strict';
const chosen=new Set();
let copied=[],pasteCounter=0,gesture=null,marquee=null;
const doc=document,work=document.getElementById('workspace'),strip=document.getElementById('toolRail');
const layer=document.createElement('div');layer.id='ptSelectionRect';layer.hidden=true;work.append(layer);
const snapX=document.createElement('div'),snapY=document.createElement('div');
snapX.id='ptAlignmentVertical';snapY.id='ptAlignmentHorizontal';
snapX.className=snapY.className='pt-alignment-guide';snapX.hidden=snapY.hidden=true;work.append(snapX,snapY);
function clearGuides(){snapX.hidden=true;snapY.hidden=true;}
const notice=document.createElement('span');notice.id='ptSelectionCount';notice.title='Selected topology devices';
document.querySelector('#workspaceTabs .workspace-left').append(notice);
const toolButton=title=>[...document.querySelectorAll('#mainToolbar button')].find(b=>b.title===title);
const selectors={copy:toolButton('Copy'),paste:toolButton('Paste'),undo:toolButton('Undo'),redo:toolButton('Redo')};
for(const b of Object.values(selectors))if(b)b.disabled=false;
function visibleNames(){return Object.keys(state.devices||{}).filter(n=>doc.querySelector('#nodes .node[data-name="'+CSS.escape(n)+'"]')?.style.display!=='none')}
function saneSelection(){
 for(const name of [...chosen])if(!state.devices[name])chosen.delete(name);
 notice.textContent=chosen.size?chosen.size+' selected':'';
 for(const node of doc.querySelectorAll('#nodes .node')){
  node.classList.toggle('pt-multi-selected',chosen.has(node.dataset.name));
  node.classList.toggle('selected',chosen.has(node.dataset.name));
 }
}
const prevTopology=renderTopology;
renderTopology=function(){prevTopology();saneSelection();window.PacketTrackerWorkspace?.updateViewport?.()};
function selectNames(names){
 chosen.clear();for(const name of names)if(state.devices[name])chosen.add(name);
 saneSelection();
}
function focusedInput(){
 const a=doc.activeElement;
 return a && (a.matches('input,textarea,select,[contenteditable="true"]') || a.closest('[contenteditable="true"]'));
}
function editingAllowed(){return !window.PacketTrackerDiagram?.previewing() && !focusedInput() && !doc.querySelector('#ptWorkspaceList:not([hidden]),#ptPrefsDialog:not([hidden]),#ptOverviewDialog:not([hidden]),#ptPortDialog:not(.hidden),#deviceDialog:not(.hidden)')}
function copy(){
 copied=[...chosen].filter(n=>state.devices[n]);
 if(!copied.length && selected && state.devices[selected])copied=[selected];
 pasteCounter=0;
 status(copied.length?copied.length+' device(s) copied to topology clipboard':'Select one or more devices to copy');
}
async function paste(){
 const names=copied.filter(n=>state.devices[n]);
 if(!names.length){status('Copy devices first');return}
 pasteCounter++;
 const dx=110+(pasteCounter-1)*25,dy=75+(pasteCounter-1)*25;
 const response=await command('duplicate '+names.join(',')+' '+dx+' '+dy,false);
 if(!response.ok){status(response.output);return}
 const match=[...response.output.matchAll(/([A-Za-z0-9_-]+) -> ([A-Za-z0-9_-]+)/g)];
 const next=match.map(m=>m[2]);
 if(next.length)selectNames(next);
 status(response.output+' (configuration copied; review duplicate IP addresses)');
 renderTopology();
}
async function undoRedo(which){
 const r=await command(which,false);
 if(r.ok){saneSelection();renderTopology();status(r.output)}
}
async function deleteSelection(){
 const targets=[...chosen].filter(n=>state.devices[n]);
 if(!targets.length){status('No devices selected');return}
 if(!confirm('Delete '+targets.length+' selected device(s) and attached links?'))return;
 const result=await command('remove-group '+targets.join(','),false);
 if(!result.ok)return status(result.output);
 chosen.clear();saneSelection();status('Deleted '+targets.length+' device(s) — undo is available');
}
const edit={copy,paste,undo:()=>undoRedo('undo'),redo:()=>undoRedo('redo'),
  selectAll:()=>{selectNames(visibleNames());status(chosen.size+' device(s) selected')},
  delete:deleteSelection};
function updateViewport(){
 const root=document.getElementById('ptViewport');
 if(!root||root.hidden)return;
 root.textContent='';
 const header=document.createElement('strong');header.textContent='Workspace Viewport';
 root.append(header);
 const map=document.createElement('div');map.className='pt-viewport-map';
 const items=Object.values(state.devices||{});
 if(!items.length){map.textContent='No devices';root.append(map);return}
 const maxX=Math.max(300,...items.map(d=>d.x+90)),maxY=Math.max(240,...items.map(d=>d.y+70));
 for(const d of items){
  const dot=document.createElement('button');dot.className='pt-viewport-node';
  dot.classList.toggle('selected',chosen.has(d.name));
  dot.title=d.name+' ('+d.kind+')';
  dot.setAttribute('aria-label','Select '+d.name);
  dot.style.left=Math.max(0,Math.min(97,d.x/maxX*96))+'%';
  dot.style.top=Math.max(0,Math.min(88,d.y/maxY*86))+'%';
  dot.onclick=()=>{selectNames([d.name]);selected=d.name;renderTopology();status(d.name+' selected from viewport')};
  map.append(dot);
 }
 root.append(map);
}
window.PacketTrackerWorkspace={edit,selected:chosen,updateViewport};
if(selectors.copy)selectors.copy.onclick=copy;
if(selectors.paste)selectors.paste.onclick=paste;
if(selectors.undo)selectors.undo.onclick=edit.undo;
if(selectors.redo)selectors.redo.onclick=edit.redo;
// Node clicks are routed through the existing cable, inspect and PDU tools.
const priorClick=nodeClick;
nodeClick=function(e,name){
 if(dragged){dragged=false;return}
 if(activeTool==='select'){
  if(e?.ctrlKey||e?.metaKey||e?.shiftKey){
   chosen.has(name)?chosen.delete(name):chosen.add(name);
  }else if(!chosen.has(name)||chosen.size!==1){
   chosen.clear();chosen.add(name);
  }
  selected=name;
  saneSelection();
  status(chosen.size+' device(s) selected');
  if(!e?.ctrlKey&&!e?.metaKey&&!e?.shiftKey)openDevice(name);
  return;
 }
 return priorClick(e,name);
};
// Prevent legacy single-device drag pipeline from mutating state without undo history.
dragStart=function(e){
 if(activeTool!=='select'||e.button!==0)return;
 e.preventDefault(); // Keep the browser's native image drag from cancelling device movement.
 dragged=false;
 const name=e.currentTarget.dataset.name;
 const clone=e.ctrlKey||e.metaKey;
 if(!chosen.has(name)&&!clone){
  if(!e.shiftKey)chosen.clear();
  chosen.add(name);
 }
 saneSelection();
 const members=(clone&&!chosen.has(name)?[name]:[...chosen]).filter(n=>state.devices[n]);
 gesture={name,members,clone,origin:{},x:e.clientX,y:e.clientY,moved:false};
 window.ptPointerActive=true;
 e.currentTarget.setPointerCapture(e.pointerId);
 for(const n of members)gesture.origin[n]={x:state.devices[n].x,y:state.devices[n].y};
 // Window-level pointer events survive topology DOM redraws during dragging.
};
work.addEventListener('pointerdown',e=>{
 if(e.button!==0||activeTool!=='select'||placementType ||e.target!==work)return;
 marquee={startX:e.clientX,startY:e.clientY,active:false};
 layer.hidden=true;
},true);
function workspaceRect(){return work.getBoundingClientRect()}
function previewMovement(members){
 const changed=new Set(members);
 for(const name of members){
  const element=doc.querySelector('#nodes .node[data-name="'+CSS.escape(name)+'"]');
  const device=state.devices[name];
  if(element&&device){element.style.left=device.x+'px';element.style.top=device.y+'px'}
 }
 if(window.PacketTrackerDiagram){window.PacketTrackerDiagram.drag(members);return}
 const lines=[...doc.querySelectorAll('#wires line')];
 const labels=[...doc.querySelectorAll('#wires text')];
 (state.links||[]).forEach((link,i)=>{
  if(!changed.has(link.a_device)&&!changed.has(link.b_device))return;
  const a=center(link.a_device),b=center(link.b_device);
  if(!a||!b)return;
  if(lines[i]){
   lines[i].setAttribute('x1',a.x);lines[i].setAttribute('y1',a.y);
   lines[i].setAttribute('x2',b.x);lines[i].setAttribute('y2',b.y);
  }
  if(labels[i]){labels[i].setAttribute('x',(a.x+b.x)/2+4);labels[i].setAttribute('y',(a.y+b.y)/2-4)}
 });
}
window.addEventListener('pointermove',e=>{
 if(gesture){
  const g=gesture,dx=(e.clientX-g.x)/zoom,dy=(e.clientY-g.y)/zoom;
  g.travelled=Math.max(g.travelled||0,Math.hypot(e.clientX-g.x,e.clientY-g.y));
  if(!g.moved&&Math.hypot(e.clientX-g.x,e.clientY-g.y)<6)return;
  g.moved=true;
  const minX=Math.min(...g.members.map(n=>g.origin[n].x)),minY=Math.min(...g.members.map(n=>g.origin[n].y));
  let clampedX=Math.max(-minX,dx),clampedY=Math.max(-minY,dy);
  clearGuides();
  if(document.body.classList.contains('pt-align-enabled')){
   const peer=Object.values(state.devices).filter(d=>!g.members.includes(d.name));
   const anchor=g.origin[g.name];
   let bestX=10,bestY=10,xAlign=null,yAlign=null;
   for(const d of peer){
    const gapX=Math.abs(d.x-(anchor.x+clampedX)),gapY=Math.abs(d.y-(anchor.y+clampedY));
    if(gapX<bestX){bestX=gapX;xAlign=d.x;}
    if(gapY<bestY){bestY=gapY;yAlign=d.y;}
   }
   if(xAlign!==null){clampedX+=xAlign-(anchor.x+clampedX);snapX.hidden=false;snapX.style.left=xAlign*zoom+'px'}
   if(yAlign!==null){clampedY+=yAlign-(anchor.y+clampedY);snapY.hidden=false;snapY.style.top=yAlign*zoom+'px'}
  }
  g.delta={dx:clampedX,dy:clampedY};
  for(const n of g.members){
   state.devices[n].x=g.origin[n].x+clampedX;
   state.devices[n].y=g.origin[n].y+clampedY;
  }
  previewMovement(g.members);
  return;
 }
 if(!marquee||activeTool!=='select')return;
 const m=marquee;
 if(!m.active&&Math.hypot(e.clientX-m.startX,e.clientY-m.startY)<4)return;
 m.active=true;
 const r=workspaceRect(),x1=Math.min(m.startX,e.clientX)-r.left,y1=Math.min(m.startY,e.clientY)-r.top;
 const x2=Math.max(m.startX,e.clientX)-r.left,y2=Math.max(m.startY,e.clientY)-r.top;
 layer.hidden=false;
 Object.assign(layer.style,{left:x1+'px',top:y1+'px',width:(x2-x1)+'px',height:(y2-y1)+'px'});
},true);
window.addEventListener('pointerup',async e=>{
 window.ptPointerActive=false;
 if(gesture){
  const g=gesture;gesture=null;clearGuides();
  if(!g.moved){if(g.travelled>=6)dragged=true;return;}
  dragged=true; // Suppress click following drag.
  const dx=g.delta?.dx||0,dy=g.delta?.dy||0;
  for(const n of g.members){state.devices[n].x=g.origin[n].x;state.devices[n].y=g.origin[n].y}
  const group=g.members.join(',');
  const instruction=g.clone?'duplicate '+group+' '+dx+' '+dy:g.members.length===1?
   'move '+g.members[0]+' '+(g.origin[g.members[0]].x+dx)+' '+(g.origin[g.members[0]].y+dy):
   'move-group '+group+' '+dx+' '+dy;
  if(Math.abs(dx)+Math.abs(dy)>0.01){
   const r=await command(instruction,false);status(r.output);
   if(g.clone&&r.ok){const next=[...r.output.matchAll(/([A-Za-z0-9_-]+) -> ([A-Za-z0-9_-]+)/g)].map(m=>m[2]);selectNames(next)}
  }
  if(Math.abs(dx)+Math.abs(dy)<=0.01)renderTopology();
 }
 if(marquee){
  const m=marquee;marquee=null;layer.hidden=true;
  if(m.active){
   dragged=true;
   const x1=Math.min(m.startX,e.clientX),x2=Math.max(m.startX,e.clientX);
   const y1=Math.min(m.startY,e.clientY),y2=Math.max(m.startY,e.clientY);
   const matches=[...doc.querySelectorAll('#nodes .node')].filter(n=>{
    const r=n.getBoundingClientRect();
    return r.left<x2&&r.right>x1&&r.top<y2&&r.bottom>y1 && n.style.display!=='none';
   }).map(n=>n.dataset.name);
   if(!e.ctrlKey&&!e.metaKey)chosen.clear();
   for(const n of matches)chosen.add(n);
   saneSelection();status(chosen.size+' device(s) selected');
  }else if(e.target===work&&activeTool==='select'){
   chosen.clear();saneSelection();
  }
 }
},true);
doc.addEventListener('click',e=>{if(dragged&&e.target.closest('#workspace')){e.preventDefault();e.stopImmediatePropagation();dragged=false}},true);
doc.addEventListener('pointerdown',()=>{dragged=false},true);
window.addEventListener('pointercancel',()=>{
 window.ptPointerActive=false;
 if(gesture){for(const n of gesture.members){state.devices[n].x=gesture.origin[n].x;state.devices[n].y=gesture.origin[n].y}gesture=null;clearGuides();renderTopology()}
 if(marquee){marquee=null;layer.hidden=true}
});
doc.addEventListener('keydown',e=>{
 if(!editingAllowed())return;
 const ctrl=e.ctrlKey||e.metaKey;
 if(e.key==='Escape'&&(placementType||activeTool==='cable')){
  e.preventDefault();e.stopImmediatePropagation();
  window.ptPlacementLocked=false;window.ptCableLocked=false;
  setTool('select');placementType=null;renderPalette();
  status('Placement canceled');return;
 }
 let fn=null;
 if(ctrl&&!e.altKey){
  if(e.key.toLowerCase()==='a')fn=edit.selectAll;
  else if(e.key.toLowerCase()==='c')fn=copy;
  else if(e.key.toLowerCase()==='v')fn=paste;
  else if(e.key.toLowerCase()==='z')fn=e.shiftKey?edit.redo:edit.undo;
  else if(e.key.toLowerCase()==='y')fn=edit.redo;
 }else if((e.key==='Delete'||e.key==='Backspace')&&chosen.size && activeTool==='select')fn=deleteSelection;
 if(fn){e.preventDefault();e.stopImmediatePropagation();fn()}
},true);
const beforeFetch=fetchState;
fetchState=async function(){await beforeFetch();saneSelection()};
})();
