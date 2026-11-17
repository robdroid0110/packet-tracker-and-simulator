/* legacy simulator Physical Workspace §19 — editable cable bend/group points.
 * All actions are persisted via the same agent API as the shell.
 */
(() => {
'use strict';
const root=document.getElementById('ptPhysicalWorkspace');
if(!root)return;
const ns='http://www.w3.org/2000/svg';
const node=(name,cls,text)=>{
 const n=document.createElement(name);if(cls)n.className=cls;
 if(text!==undefined)n.textContent=String(text);return n;
};
const svgNode=name=>document.createElementNS(ns,name);
let activeView='intercity',last=null,seq=0,menu=null,busy=false;
let sourceSelection=null;
const selectedTool=()=>typeof activeTool!=='undefined'?activeTool:'select';
function closeMenu(){menu?.remove();menu=null}
function status(msg){const target=document.getElementById('ptCableFeedback');if(target)target.textContent=msg;const bar=document.getElementById('statusText');if(bar)bar.textContent=msg}
function ensureMenu(){
 closeMenu();menu=node('aside','pt-cable-menu');
 menu.setAttribute('role','menu');document.body.append(menu);
 return menu;
}
function menuButton(title,handler){
 const b=node('button','',title);b.type='button';b.onclick=()=>{
  closeMenu();handler();
 };menu.append(b);return b;
}
function showMenu(x,y){
 menu.style.left=Math.max(5,Math.min(window.innerWidth-230,x))+'px';
 menu.style.top=Math.max(5,Math.min(window.innerHeight-230,y))+'px';
}
async function mutate(payload){
 if(busy)return null;
 busy=true;
 try{
  const response=await fetch('/api/physical-cables/action',{
   method:'POST',headers:{'content-type':'application/json'},
   body:JSON.stringify(payload)});
  const data=await response.json();
  if(!response.ok||!data.ok)throw Error(data.error||data.output||'Cable action failed');
  state=data.state;render();closeMenu();
  window.dispatchEvent(new Event('pt-physical-cables-update'));
  status(data.output||'Cable updated');
  return data;
 }catch(err){status(err.message);return null}
 finally{busy=false}
}
const endpoint=c=>({device:c.a_device,interface:c.a_if});
function afterFor(c,segment){
 return segment===0?'start':c.points[segment]?.id||null;
}
function worldFromPixel(x,y,data){
 const f=data.geometry,origin=data.world_origin_m;
 return {x_m:Number((origin.x_m+x*f.meters_per_x).toFixed(5)),
         y_m:Number((origin.y_m+y*f.meters_per_y).toFixed(5))};
}
function locationPixel(e,map){
 const bounds=map.getBoundingClientRect();
 return {x:e.clientX-bounds.left,y:e.clientY-bounds.top};
}
function openLineMenu(c,segment,event,map,data){
 event.preventDefault();event.stopPropagation();
 const xy=locationPixel(event,map);
 const world=worldFromPixel(xy.x,xy.y,data);
 ensureMenu();
 menu.append(node('strong','',c.a_device+':'+c.a_if+' → '+c.b_device+':'+c.b_if));
 menu.append(node('small','',c.length.total_length_m+' m · '+(c.up?'UP':'DOWN')));
 menuButton('Create BendPoint',()=>mutate({action:'add_bend',...endpoint(c),
    x_m:world.x_m,y_m:world.y_m,after:afterFor(c,segment)}));
 menuButton('Color Cable',()=>openColor(c,event.clientX,event.clientY));
 menuButton('Reset Cable Color',()=>mutate({action:'set_color',...endpoint(c),color:'#24354b'}));
 showMenu(event.clientX||100,event.clientY||100);
}
function openColor(c,x,y){
 ensureMenu();
 menu.append(node('strong','','Select Color — Cable'));
 const input=node('input');input.type='color';input.value=c.color;input.setAttribute('aria-label','Cable colour');
 menu.append(input);
 menuButton('Apply Color',()=>mutate({action:'set_color',...endpoint(c),color:input.value}));
 menuButton('Reset to Default',()=>mutate({action:'set_color',...endpoint(c),color:'#24354b'}));
 showMenu(x,y);input.focus();
}
function openPointMenu(c,p,event){
 event.preventDefault();event.stopPropagation();
 ensureMenu();
 menu.append(node('strong','',p.group?'GroupPoint (yellow)':'BendPoint (black)'));
 menu.append(node('small','',c.a_device+':'+c.a_if));
 if(p.group){
  menuButton('Ungroup this cable',()=>mutate({action:'ungroup',group:p.group,...endpoint(c)}));
  menuButton('Ungroup all cables',()=>mutate({action:'ungroup',group:p.group}));
 }
 menuButton('Delete BendPoint (keep cable)',()=>mutate({action:'delete_bend',...endpoint(c),bend:p.id}));
 showMenu(event.clientX||100,event.clientY||100);
}
function pointerHandle(c,p,circle,map,data){
 let start=null,didDrag=false;
 circle.addEventListener('pointerdown',event=>{
  if(event.button!==0)return;
  event.stopPropagation();
  if(selectedTool()==='delete'){
   openPointMenu(c,p,event);return;
  }
  start={x:event.clientX,y:event.clientY};
  didDrag=false;circle.setPointerCapture(event.pointerId);
 });
 circle.addEventListener('pointermove',event=>{
  if(!start)return;
  if(Math.hypot(event.clientX-start.x,event.clientY-start.y)>4)didDrag=true;
  if(didDrag){
   const point=locationPixel(event,map);
   if(p.group){circle.setAttribute('x',point.x-8);circle.setAttribute('y',point.y-8)}
   else{circle.setAttribute('cx',point.x);circle.setAttribute('cy',point.y)}
  }
 });
 circle.addEventListener('pointerup',event=>{
  if(!start)return;
  start=null;
  if(!didDrag)return;
  event.preventDefault();event.stopPropagation();
  const point=locationPixel(event,map);
  let other=null;
  for(const cable of data.cables){
   if(cable.key===c.key)continue;
   for(const candidate of cable.points){
    if(candidate.type!=='bend')continue;
    if(Math.hypot(point.x-candidate.x,point.y-candidate.y)<18){
     other={cable,point:candidate};break;
    }
   }
   if(other)break;
  }
  if(other){
   mutate({action:'group_bends',...endpoint(c),bend:p.id,
     other_device:other.cable.a_device,other_interface:other.cable.a_if,
     other_bend:other.point.id});
  }else{
   const world=worldFromPixel(point.x,point.y,data);
   mutate({action:p.group?'move_group':'move_bend',
     ...(p.group?{group:p.group}:{...endpoint(c),bend:p.id}),
     ...world});
  }
 });
 circle.addEventListener('click',event=>{
  event.stopPropagation();
  if(didDrag){didDrag=false;return}
  openPointMenu(c,p,event);
 });
 circle.addEventListener('contextmenu',event=>openPointMenu(c,p,event));
}
function drawSvg(map,data){
 const svg=svgNode('svg');svg.classList.add('pt-cable-routes');
 const width=Math.max(1000,map.scrollWidth,map.clientWidth);
 const height=Math.max(700,map.scrollHeight,map.clientHeight);
 svg.setAttribute('width',width);svg.setAttribute('height',height);
 svg.setAttribute('viewBox','0 0 '+width+' '+height);
 svg.setAttribute('aria-label','Editable physical cable routes');
 let count=0;
 for(const c of data.cables){
  for(let idx=0;idx<c.points.length-1;idx++){
   const a=c.points[idx],b=c.points[idx+1];
   const seg=c.segments[idx];
   const line=svgNode('line');
   for(const [key,value] of Object.entries({
    x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:seg.color,
    'stroke-width':c.up?3:2,'stroke-linecap':'round'}))line.setAttribute(key,value);
   if(!c.up)line.setAttribute('stroke-dasharray','5 5');
   line.classList.add('pt-physical-cable-segment');
   const title=svgNode('title');
   title.textContent=c.a_device+':'+c.a_if+' ↔ '+c.b_device+':'+c.b_if+
     ' · segment '+seg.length_m+'m / total '+c.length.total_length_m+'m'+
     ' · '+c.reason;
   line.append(title);
   svg.append(line);
   const hit=svgNode('line');
   for(const [key,value] of Object.entries({x1:a.x,y1:a.y,x2:b.x,y2:b.y}))
    hit.setAttribute(key,value);
   hit.classList.add('pt-cable-hit');
   hit.setAttribute('stroke','transparent');
   hit.onclick=event=>openLineMenu(c,idx,event,map,data);
   hit.oncontextmenu=event=>openLineMenu(c,idx,event,map,data);
   svg.append(hit);count++;
  }
 }
 // Points must render last, on top of the routed cable strokes.
 const seenGroups=new Set();
 for(const c of data.cables)for(const p of c.points){
  if(p.type!=='bend')continue;
  if(p.group&&seenGroups.has(p.group))continue;
  if(p.group)seenGroups.add(p.group);
  const dot=p.group?svgNode('rect'):svgNode('circle');
  const radius=p.group?8:5;
  if(p.group){
   dot.setAttribute('x',p.x-8);dot.setAttribute('y',p.y-8);
   dot.setAttribute('width',16);dot.setAttribute('height',16);
  }else{
   dot.setAttribute('cx',p.x);dot.setAttribute('cy',p.y);dot.setAttribute('r',radius);
  }
  dot.classList.add(p.group?'pt-cable-group-point':'pt-cable-bend-point');
  dot.setAttribute('role','button');dot.setAttribute('tabindex','0');
  dot.setAttribute('aria-label',(p.group?'GroupPoint':'BendPoint')+' '+p.id);
  dot.onkeydown=event=>{
   if(event.key==='Enter'||event.key===' '){event.preventDefault();openPointMenu(c,p,event)}
   if(event.key==='Delete'){event.preventDefault();mutate({action:'delete_bend',...endpoint(c),bend:p.id})}
  };
  pointerHandle(c,p,dot,map,data);
  svg.append(dot);
 }
 map.prepend(svg);
 return count;
}
function panel(data){
 root.querySelector('#ptCablePanel')?.remove();
 const details=node('details','pt-cable-panel');
 details.id='ptCablePanel';
 const summary=node('summary','', 'Cable Manipulation · '+data.cables.length+' local cables · '+data.group_count+' groups');
 details.append(summary);
 const body=node('div','pt-cable-panel-body');
 body.append(node('p','pt-cable-note','Click a cable to create bends or change its colour. Drag black dots to route. Drag one dot onto another cable dot to group. Yellow squares move grouped cables.'));
 const feed=node('p');feed.id='ptCableFeedback';feed.setAttribute('role','status');
 body.append(feed);
 for(const c of data.cables){
  const item=node('section','pt-cable-panel-item');
  const line=node('span','',c.a_device+':'+c.a_if+' ↔ '+c.b_device+':'+c.b_if);
  const length=node('strong','',c.length.total_length_m+'m '+(c.up?'UP':'DOWN'));
  item.append(line,length);
  const add=node('button','','Add Bend');
  add.title='Add a BendPoint near the cable midpoint';
  add.onclick=()=>{
   const a=c.points[0],b=c.points[c.points.length-1];
   mutate({action:'add_bend',...endpoint(c),
     x_m:(a.x_m+b.x_m)/2,y_m:(a.y_m+b.y_m)/2+1});
  };
  const color=node('button','','Color');
  color.onclick=e=>openColor(c,e.clientX||window.innerWidth/2,e.clientY||100);
  item.append(add,color);
  if(c.points.length>2){
   for(const p of c.points.filter(p=>p.type==='bend')){
    const point=node('button','pt-bend-list-item',p.group?'Ungroup '+p.id.slice(-6):'Delete '+p.id.slice(-6));
    point.onclick=()=>p.group?mutate({action:'ungroup',group:p.group,...endpoint(c)}):
      mutate({action:'delete_bend',...endpoint(c),bend:p.id});
    item.append(point);
   }
  }
  body.append(item);
 }
 if(!data.cables.length)body.append(node('p','pt-cable-note','No cables entirely within this physical location. Open a location containing both endpoints or move devices here.'));
 const buttons=node('div','pt-cable-undo-controls');
 const undo=node('button','','Undo');undo.onclick=()=>mutate({action:'undo'});
 const redo=node('button','','Redo');redo.onclick=()=>mutate({action:'redo'});
 buttons.append(undo,redo);body.append(buttons);
 details.append(body);root.append(details);
}
async function render(location='intercity'){
 activeView=location;
 const ticket=++seq;
 if(root.hidden)return;
 try{
  const res=await fetch('/api/physical-cables?location='+encodeURIComponent(location));
  const data=await res.json();
  if(ticket!==seq||!data.ok||root.hidden)return;
  last=data;
  const map=root.querySelector('.pt-map-cards');
  map?.querySelector('.pt-cable-routes')?.remove();
  if(map)drawSvg(map,data);
  panel(data);
 }catch(err){console.warn('Cable management view unavailable',err)}
}
document.addEventListener('pointerdown',e=>{
 if(menu&&!menu.contains(e.target)&&!e.target.closest('.pt-physical-cable-segment,.pt-cable-bend-point,.pt-cable-group-point'))closeMenu();
});
window.addEventListener('pt-physical-cables-update',()=>render(root.dataset.location||activeView));
window.PacketTrackerCables={render,get data(){return last},get menu(){return menu}};
})();
