/* Keyboard interaction for logical devices; persistent edits use existing commands. */
(() => {
'use strict';
const doc=document, host=doc.getElementById('nodes'), work=doc.getElementById('workspace');
const help=doc.createElement('p');
help.id='ptCanvasKeyboardHelp';help.className='pt-visually-hidden';
help.textContent='Use arrow keys to choose a device by direction. Control or Command plus an arrow cycles every device, including overlapping devices. Shift plus an arrow moves it 10 units; Control or Command plus Shift and an arrow moves it 50 units. Enter or Space uses the selected tool. Shift plus D focuses the device canvas. To add devices with a keyboard, use the Workspace List with Shift plus W.';
doc.body.append(help);
host.setAttribute('role','group');host.setAttribute('aria-label','Logical network devices');host.setAttribute('aria-describedby',help.id);
let current=null, moving=false, revealFrame=0, keyboardInput=true;
const pending=new Map();
const directions={ArrowLeft:[-1,0],ArrowRight:[1,0],ArrowUp:[0,-1],ArrowDown:[0,1]};
const quote=value=>"'"+String(value).replace(/'/g,"'\\''")+"'";
function nodes(){return [...host.querySelectorAll('.node[data-name]')];}
function visible(){return nodes().filter(node=>node.getClientRects().length>0);}
function describe(node){
 const name=node.dataset.name,device=state.devices[name];if(!device)return;
 const prefix=name+' — ',spec=modelSpec(device),connection=node.title?.startsWith(prefix)?node.title.slice(prefix.length):'unknown link status';
 node.setAttribute('aria-label',name+', '+spec.label+', '+connection+(linkSource===name?', connection source':''));
}
function setCurrent(node){
 const previous=host.querySelector('.node[tabindex="0"]');
 if(previous&&previous!==node)previous.tabIndex=-1;
 current=node.dataset.name;node.tabIndex=0;describe(node);
}
function update(){
 const all=nodes(),shown=all.filter(node=>node.getClientRects().length>0);
 const shownSet=new Set(shown);
 if(!shown.some(node=>node.dataset.name===current))current=shown[0]?.dataset.name||null;
 for(const node of all){
  if(!state.devices[node.dataset.name])continue;
  node.setAttribute('role','button');
  describe(node);
  node.setAttribute('aria-describedby',help.id);
  node.setAttribute('aria-keyshortcuts','Enter Space Shift+ArrowLeft Shift+ArrowRight Shift+ArrowUp Shift+ArrowDown Control+ArrowLeft Control+ArrowRight Control+ArrowUp Control+ArrowDown Meta+ArrowLeft Meta+ArrowRight Meta+ArrowUp Meta+ArrowDown');
  node.tabIndex=node.dataset.name===current&&shownSet.has(node)?0:-1;
 }
}
function reveal(node){
 cancelAnimationFrame(revealFrame);
 if(!keyboardInput)return;
 let passes=0;
 const adjust=()=>{
  revealFrame=0;
  if(!keyboardInput||doc.activeElement!==node||!node.isConnected)return;
  const r=node.getBoundingClientRect(),w=work.getBoundingClientRect(),pad=14;
  if(!w.width||!w.height)return;
  const dx=r.left<w.left+pad?w.left+pad-r.left:r.right>w.right-20?w.right-20-r.right:0;
  const dy=r.top<w.top+pad?w.top+pad-r.top:r.bottom>w.bottom-20?w.bottom-20-r.bottom:0;
  const horizontal=work.querySelector('.workspace-scrollbar.horizontal');
  const vertical=work.querySelector('.workspace-scrollbar.vertical');
  const oldX=horizontal?.scrollLeft,oldY=vertical?.scrollTop;
  if(horizontal&&dx)horizontal.scrollLeft-=dx;
  if(vertical&&dy)vertical.scrollTop-=dy;
  if(++passes<3&&(horizontal?.scrollLeft!==oldX||vertical?.scrollTop!==oldY))revealFrame=requestAnimationFrame(adjust);
 };
 revealFrame=requestAnimationFrame(adjust);
}
function focus(name){
 const node=host.querySelector('.node[data-name="'+CSS.escape(name)+'"]');
 if(!node||!node.getClientRects().length)return false;
 setCurrent(node);node.focus({preventScroll:true});reveal(node);return true;
}
function focusCanvas(){
 update();
 if(!current||!focus(current)){status('No visible devices in the logical workspace');return false}
 status('Device canvas: arrows navigate, Ctrl plus arrows cycle, Shift plus arrows move, Enter or Space activates');
 return true;
}
function nearest(node,key){
 const [vx,vy]=directions[key],source=state.devices[node.dataset.name];
 return visible().filter(other=>other!==node).map(other=>{
  const target=state.devices[other.dataset.name],dx=target.x-source.x,dy=target.y-source.y;
  const forward=dx*vx+dy*vy,side=Math.abs(dx*vy-dy*vx);
  return {other,forward,score:forward+side*2,distance:Math.hypot(dx,dy)};
 }).filter(item=>item.forward>0).sort((a,b)=>a.score-b.score||a.distance-b.distance||a.other.dataset.name.localeCompare(b.other.dataset.name))[0]?.other;
}
async function drainMoves(){
 if(moving||!pending.size)return;
 moving=true;
 const [name,delta]=pending.entries().next().value;pending.delete(name);
 try{
  const device=state.devices[name];
  if(!device){status(name+' is no longer available');return}
  const x=Math.max(0,Math.min(10000,device.x+delta.dx));
  const y=Math.max(0,Math.min(10000,device.y+delta.dy));
  if(x===device.x&&y===device.y){status(name+' is at the edge of the workspace');return}
  const result=await command('move '+quote(name)+' '+x+' '+y,false);
  if(!result.ok){status(result.output||'Unable to move '+name);return}
  status(name+' moved to x '+x+', y '+y);
 }catch(error){status('Unable to move '+name+': '+error.message)}
 finally{moving=false;if(pending.size)drainMoves();}
}
function move(name,dx,dy){
 const previous=pending.get(name)||{dx:0,dy:0};
 pending.set(name,{dx:Math.max(-10000,Math.min(10000,previous.dx+dx)),dy:Math.max(-10000,Math.min(10000,previous.dy+dy))});
 drainMoves();
}
const previousTopology=renderTopology;
renderTopology=function(...args){
 const active=doc.activeElement,wasFocused=doc.hasFocus()&&host.contains(active)&&active?.classList.contains('node');
 const name=wasFocused?active.dataset.name:null;
 const value=previousTopology.apply(this,args);update();
 if(name&&doc.activeElement===doc.body)focus(name);
 return value;
};
doc.addEventListener('pointerdown',()=>{keyboardInput=false;cancelAnimationFrame(revealFrame)},true);
doc.addEventListener('keydown',()=>{keyboardInput=true},true);
host.addEventListener('focusin',event=>{
 const node=event.target.closest('.node[data-name]');if(!node)return;
 setCurrent(node);reveal(node);
});
host.addEventListener('click',event=>{
 const node=event.target.closest('.node[data-name]');if(node&&event.isTrusted&&event.detail>0)setCurrent(node);
},true);
host.addEventListener('keydown',event=>{
 const node=event.target.closest('.node[data-name]');
 if(!node||window.ptPointerActive||window.PacketTrackerDiagram?.previewing())return;
 const name=node.dataset.name,offset=directions[event.key];
 if(offset&&!event.altKey){
  if(event.shiftKey){
   event.preventDefault();event.stopPropagation();
   if(activeTool!=='select'||placementType){status('Choose the Select tool to move a device');return}
   const step=event.ctrlKey||event.metaKey?50:10;move(name,offset[0]*step,offset[1]*step);return;
  }
  event.preventDefault();event.stopPropagation();
  if(event.ctrlKey||event.metaKey){
   const options=visible(),index=options.indexOf(node),step=(offset[0]||offset[1])<0?-1:1;
   if(options.length)focus(options[(index+step+options.length)%options.length].dataset.name);
   return;
  }
  const next=nearest(node,event.key);
  if(next)focus(next.dataset.name);else status('No device in that direction');
  return;
 }
 if((event.key==='Enter'||event.key===' ')&&!event.ctrlKey&&!event.metaKey&&!event.shiftKey&&!event.altKey){
  event.preventDefault();event.stopPropagation();dragged=false;
  const r=node.getBoundingClientRect();
  node.dispatchEvent(new MouseEvent('click',{bubbles:true,cancelable:true,clientX:r.left+r.width/2,clientY:r.top+r.height/2,detail:0}));
  if(node.isConnected)describe(node);
 }
});
doc.addEventListener('keydown',event=>{
 if(!event.shiftKey||event.ctrlKey||event.metaKey||event.altKey||event.key.toLowerCase()!=='d')return;
 if(event.target.closest('input,textarea,select,[contenteditable="true"]'))return;
 if([...doc.querySelectorAll('dialog[open],[role="dialog"]')].some(dialog=>!dialog.hidden&&!dialog.classList.contains('hidden')&&dialog.getClientRects().length))return;
 event.preventDefault();event.stopImmediatePropagation();focusCanvas();
},true);
// Keyboard activation of a cable option proceeds directly to the device canvas.
doc.addEventListener('click',event=>{
 if(!event.isTrusted||event.detail!==0||!event.target.closest('[data-connection]'))return;
 const original=event.target.closest('[data-connection]');
 setTimeout(()=>{
  if(activeTool==='cable'&&(doc.activeElement===doc.body||doc.activeElement===original))focusCanvas();
 },0);
},true);
window.PacketTrackerCanvas={focus,focusCanvas};
update();
})();
