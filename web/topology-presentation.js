/* Logical diagram projection. Persistent controls use workspace-tools actions. */
(() => {
 const ns='http://www.w3.org/2000/svg',work=document.getElementById('workspace');
 let focus=null,edgeFocus=null,preview=null,labels=[],routeCache=new Map(),geometryKey='',renderedNodes=new Map(),renderedRepresentatives=new Map();
 const settings=()=>state.workspace_tools?.diagram||{routing:true,labels:'smart',focus:true,semantic_zoom:true,groups:{}};
 const logical=()=>!window.PacketTrackerLogicalContext||window.PacketTrackerLogicalContext().mode==='logical';
 const svg=(tag,attrs={})=>{const n=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,v);return n};
 const button=(text,fn)=>{const b=document.createElement('button');b.textContent=text;b.type='button';b.onclick=fn;return b};
 async function mutate(body){const r=await(await fetch('/api/workspace-tools/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})).json();if(!r.ok)throw Error(r.output||r.error);await fetchState();return r}
 const safely=fn=>async()=>{try{await fn()}catch(e){status(e.message)}};
 const dialog=document.createElement('dialog');dialog.id='diagramOptions';dialog.setAttribute('aria-label','Topology display');document.body.append(dialog);
 function controls(){
  dialog.replaceChildren();const h=document.createElement('h2');h.textContent='Topology display';dialog.append(h);
  for(const [key,title]of [['routing','Separate parallel cables'],['focus','Highlight related connections'],['semantic_zoom','Show detail according to zoom']]){
   const label=document.createElement('label'),check=document.createElement('input');check.type='checkbox';check.checked=settings()[key];check.onchange=safely(()=>mutate({action:'diagram_preferences',[key]:check.checked}));label.append(check,title);dialog.append(label);
  }
  const label=document.createElement('label');label.textContent='Interface labels ';const select=document.createElement('select');select.setAttribute('aria-label','Interface label detail');for(const [value,text]of [['smart','Smart — avoid collisions'],['all','All'],['none','None']]){const o=document.createElement('option');o.value=value;o.textContent=text;select.append(o)}select.value=settings().labels;select.onchange=safely(()=>mutate({action:'diagram_preferences',labels:select.value}));label.append(select);dialog.append(label);
  dialog.append(button('Preview tidy layout',safely(tidy)),button('Group selected devices',safely(async()=>{
   const members=[...(window.PacketTrackerWorkspace?.selected||[])];if(!members.length)throw Error('Ctrl-click devices or drag a selection rectangle first');const name=prompt('Group name (site, department, VLAN or other label)');if(!name)return;await mutate({action:'diagram_group',name,members});controls();
  })));
  for(const [name,g]of Object.entries(settings().groups||{})){
   const row=document.createElement('div');row.className='diagram-group-row';const text=document.createElement('span');text.textContent=name+' · '+g.members.length+' devices';row.append(text,button(g.collapsed?'Expand':'Collapse',safely(async()=>{await mutate({action:'diagram_collapse',name,collapsed:!g.collapsed});controls()})),button('Ungroup',safely(async()=>{await mutate({action:'diagram_ungroup',name});controls()})));dialog.append(row);
  }
  const hint=document.createElement('p');hint.textContent='Select a cable to inspect both interfaces. Escape clears cable focus. Existing label visibility preferences still apply. Layouts and groups are saved with the lab and support Undo.';dialog.append(hint,button('Close',()=>dialog.close()));
 }
 const launcher=button('Topology display',()=>{controls();dialog.showModal()});launcher.id='topologyDisplayBtn';document.getElementById('toolRail').append(launcher);
 const banner=document.createElement('div');banner.id='diagramPreview';banner.hidden=true;work.append(banner);
 async function tidy(){
  if(!logical())throw Error('Open the Logical workspace first');
  const visible=[...document.querySelectorAll('#nodes .node')].filter(n=>n.style.display!=='none').map(n=>n.dataset.name);
  for(const [groupName,g] of Object.entries(settings().groups||{}))if(g.collapsed&&[...document.querySelectorAll('.diagram-group')].some(b=>b.dataset.group===groupName))for(const n of g.members)if(state.devices[n]&&!visible.includes(n))visible.push(n);
  const chosen=[...(window.PacketTrackerWorkspace?.selected||[])];const names=chosen.length?chosen:visible;
  const r=await(await fetch('/api/topology-layout?names='+encodeURIComponent(JSON.stringify(names)))).json();if(!r.ok)throw Error(r.error);preview=r;dialog.close();banner.replaceChildren(document.createTextNode('Layout preview · '+names.length+' devices '),button('Apply',safely(async()=>{await mutate({action:'layout_apply',names:r.names,signature:r.signature});preview=null;banner.hidden=true;renderTopology()})),button('Cancel',()=>{preview=null;banner.hidden=true;renderTopology()}));banner.hidden=false;renderTopology();banner.querySelector('button').focus();
 }
 const oldDraw=drawLink;drawLink=function(l){if(!logical())oldDraw(l)};
 const oldRender=renderTopology;
 renderTopology=function(){
  // Preview coordinates are never published into the authoritative client snapshot.
  const activeEdge=document.activeElement?.classList?.contains('diagram-hit')?document.activeElement.parentElement.dataset.key:null;
  const originals=[];if(preview&&logical())for(const [name,p]of Object.entries(preview.positions)){const d=state.devices[name];if(d){originals.push([d,d.x,d.y]);d.x=p.x;d.y=p.y}}
  try{oldRender();work.classList.toggle('diagram-logical',logical());if(logical())paint()}finally{for(const [d,x,y]of originals){d.x=x;d.y=y}}
  if(activeEdge&&document.activeElement===document.body){const g=[...document.querySelectorAll('.diagram-edge')].find(g=>g.dataset.key===activeEdge);g?.querySelector('.diagram-hit')?.focus({preventScroll:true})}
 };
 // Direct connections retain the original visual style. Only repeated device
 // pairs get parallel lanes; reversing a cable's endpoints does not merge lanes.
 function offsetAnchors(ar,br,offset=0){
  const [a,b]=anchors(ar,br),dx=b.x-a.x,dy=b.y-a.y,length=Math.hypot(dx,dy)||1;
  const x=-dy/length*offset,y=dx/length*offset;
  return [{x:a.x+x,y:a.y+y},{x:b.x+x,y:b.y+y}];
 }
 function anchors(ar,br){
  const a={x:ar.x+ar.w/2,y:ar.y+22},b={x:br.x+br.w/2,y:br.y+22};
  if(Math.abs(a.y-b.y)>Math.abs(a.x-b.x)){
   const down=b.y>a.y;a.y=ar.y+(down?ar.h:0);b.y=br.y+(down?0:br.h);
  }else{const right=b.x>a.x;a.x=ar.x+(right?ar.w:0);b.x=br.x+(right?0:br.w)}
  return [a,b];
 }
 const pathData=points=>points.map((p,i)=>(i?'L':'M')+p.x+' '+p.y).join(' ');
 function dragCables(members){
  if(!logical())return;if(!members){paint();return}
  const changed=new Set(members);
  for(const name of members){const r=renderedNodes.get(name),d=state.devices[name];if(r&&d){r.x=d.x;r.y=d.y}}
  for(const g of document.querySelectorAll('.diagram-edge')){
   if(!changed.has(g.dataset.a)&&!changed.has(g.dataset.b))continue;
   const ar=renderedNodes.get(renderedRepresentatives.get(g.dataset.a)||g.dataset.a),br=renderedNodes.get(renderedRepresentatives.get(g.dataset.b)||g.dataset.b);
   const original=routeCache.get(g.dataset.key);if(!ar||!br||!original)continue;
   const [a,b]=offsetAnchors(ar,br,Number(g.dataset.offset)||0),points=original.map(p=>({...p})),last=points.length-1;
   points[0]=a;points[last]=b;
   if(last>1){
    if(original[1].x===original[0].x)points[1].x=a.x;else points[1].y=a.y;
    if(original[last-1].x===original[last].x)points[last-1].x=b.x;else points[last-1].y=b.y;
   }
   for(const path of g.querySelectorAll('path'))path.setAttribute('d',pathData(points));
   const circles=g.querySelectorAll('circle'),texts=g.querySelectorAll('text');
   for(const [i,p] of [a,b].entries()){
    const dx=p.x-Number(circles[i].getAttribute('cx')),dy=p.y-Number(circles[i].getAttribute('cy'));
    circles[i].setAttribute('cx',p.x);circles[i].setAttribute('cy',p.y);
    texts[i].setAttribute('x',Number(texts[i].getAttribute('x'))+dx);texts[i].setAttribute('y',Number(texts[i].getAttribute('y'))+dy);
   }
  }
 }
 function paint(){
  labels=[];const prefs=settings(),nodes=new Map(),representative=new Map();
  work.classList.toggle('diagram-overview',!!prefs.semantic_zoom&&zoom<.65);work.classList.toggle('diagram-detail',!prefs.semantic_zoom||zoom>=1.1);
  document.querySelectorAll('#nodes .diagram-group,#nodes .diagram-group-frame').forEach(n=>n.remove());
  document.querySelectorAll('#nodes [data-diagram-hidden]').forEach(n=>{n.style.display='';delete n.dataset.diagramHidden});
  for(const n of document.querySelectorAll('#nodes .node'))if(n.style.display!=='none'){const d=state.devices[n.dataset.name];nodes.set(n.dataset.name,{x:d.x,y:d.y,w:88,h:64,element:n})}
  for(const [name,g]of Object.entries(prefs.groups||{}))if(g.collapsed){
   const members=g.members.filter(n=>nodes.has(n));if(!members.length)continue;
   const id=Symbol(name),x=members.reduce((v,n)=>v+nodes.get(n).x,0)/members.length,y=members.reduce((v,n)=>v+nodes.get(n).y,0)/members.length;
   const external=state.links.filter(l=>members.includes(l.a_device)!==members.includes(l.b_device)),down=external.filter(l=>!l.up).length;
   const b=button(name+'\n'+members.length+' devices · '+external.length+' uplinks'+(down?' · '+down+' down':''),safely(()=>mutate({action:'diagram_collapse',name,collapsed:false})));b.className='diagram-group';b.dataset.group=name;b.title='Expand '+name;b.style.left=x+'px';b.style.top=y+'px';document.getElementById('nodes').append(b);
   for(const member of members){nodes.get(member).element.dataset.diagramHidden='true';nodes.get(member).element.style.display='none';nodes.get(member).element.tabIndex=-1;representative.set(member,id);nodes.delete(member)}nodes.set(id,{x,y,w:150,h:64,element:b});
  }
  const shown=[...document.querySelectorAll('#nodes .node')].filter(n=>n.style.display!=='none');
  if(shown.length&&!shown.some(n=>n.tabIndex===0))shown[0].tabIndex=0;
  for(const [name,g]of Object.entries(prefs.groups||{}))if(!g.collapsed){
   const members=g.members.map(n=>nodes.get(n)).filter(Boolean);if(!members.length)continue;
   const x=Math.min(...members.map(r=>r.x))-12,y=Math.min(...members.map(r=>r.y))-28;
   const frame=document.createElement('div');frame.className='diagram-group-frame';
   Object.assign(frame.style,{left:x+'px',top:y+'px',width:(Math.max(...members.map(r=>r.x+r.w))-x+12)+'px',height:(Math.max(...members.map(r=>r.y+r.h))-y+12)+'px'});
   const collapse=button(name+' ▾',safely(()=>mutate({action:'diagram_collapse',name,collapsed:true})));collapse.title='Collapse '+name;frame.append(collapse);document.getElementById('nodes').prepend(frame);
  }
  const wires=document.getElementById('wires');wires.replaceChildren();const occupied=[...nodes.values()];
  const nodeIds=new Map([...nodes.keys()].map((name,i)=>[name,i])),pairs=new Map(),lanes=new Map();
  for(const l of state.links){
   const a=representative.get(l.a_device)||l.a_device,b=representative.get(l.b_device)||l.b_device;
   if(a===b||!nodes.has(a)||!nodes.has(b))continue;
   const ai=nodeIds.get(a),bi=nodeIds.get(b),pair=JSON.stringify([Math.min(ai,bi),Math.max(ai,bi)]);
   if(!pairs.has(pair))pairs.set(pair,[]);pairs.get(pair).push({link:l,sign:ai<bi?1:-1});
  }
  for(const entries of pairs.values())entries.forEach((entry,i)=>lanes.set(entry.link,prefs.routing?(i-(entries.length-1)/2)*14*entry.sign:0));
  const geometry=JSON.stringify([prefs.routing,[...nodes].map(([n,r])=>[String(n),r.x,r.y,r.w,r.h]),state.links.map(l=>[l.a_device,l.a_if,l.b_device,l.b_if])]);
  if(geometry!==geometryKey){routeCache.clear();geometryKey=geometry}
  for(const l of state.links){const an=representative.get(l.a_device)||l.a_device,bn=representative.get(l.b_device)||l.b_device;if(an===bn||!nodes.has(an)||!nodes.has(bn))continue;
   const ar=nodes.get(an),br=nodes.get(bn),offset=lanes.get(l)||0,[a,b]=offsetAnchors(ar,br,offset);
   const key=JSON.stringify([l.a_device,l.a_if,l.b_device,l.b_if]);
   let points=routeCache.get(key);if(!points){points=[a,b];routeCache.set(key,points)};
   const g=svg('g',{'class':'diagram-edge','data-a':l.a_device,'data-b':l.b_device,'data-key':key,'data-offset':offset});
   const path=svg('path',{d:pathData(points),fill:'none',stroke:l.up?'#288d67':'#c93d43','stroke-width':1.7,'stroke-dasharray':l.cable?.includes('cross')?'6 4':'','class':'diagram-cable'});g.append(path);
   const hit=path.cloneNode();hit.setAttribute('class','diagram-hit');hit.setAttribute('stroke','transparent');hit.setAttribute('stroke-width','12');hit.setAttribute('tabindex','0');hit.setAttribute('role','button');hit.setAttribute('aria-label',l.a_device+' '+l.a_if+' to '+l.b_device+' '+l.b_if+' · '+(l.cable||'auto')+' · '+(l.up?'up':'down: '+(l.status||'no carrier'))+(l.lights?.length?' · '+l.lights.map(light=>light.device+':'+light.interface+' '+light.color+(light.dce?' (DCE clock source)':'')).join('; '):''));
   const activate=e=>{e.stopPropagation();edgeFocus=key;focus=null;highlight();status(hit.getAttribute('aria-label'))};hit.onclick=activate;hit.onfocus=()=>{edgeFocus=key;focus=null;highlight()};hit.onkeydown=e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();activate(e)}};hit.onpointerenter=()=>{g.classList.add('diagram-hover');reveal(g)};hit.onpointerleave=()=>{g.classList.remove('diagram-hover');highlight()};const title=svg('title');title.textContent=hit.getAttribute('aria-label');hit.append(title);g.append(hit);
   for(const [i,p]of [a,b].entries()){const light=l.lights?.[i];g.append(svg('circle',{cx:p.x,cy:p.y,r:3.5,fill:({green:'#239358',red:'#c93d43',amber:'#e3a523',black:'#222'})[light?.color]||(l.up?'#239358':'#c93d43'),stroke:'#fff'}));
    const text=svg('text',{'class':'wire-label diagram-label','data-a':l.a_device,'data-b':l.b_device});text.textContent=i?l.b_if:l.a_if;let placed=false;
    for(const [dx,dy]of [[8,-9],[8,18],[-65,-9],[-65,18],[14,-26],[14,34]]){const rect={x:p.x+dx,y:p.y+dy-10,w:text.textContent.length*6+8,h:13};const overlap=r=>rect.x<r.x+r.w&&rect.x+rect.w>r.x&&rect.y<r.y+r.h&&rect.y+rect.h>r.y;if(!occupied.some(overlap)&&!labels.some(overlap)){text.setAttribute('x',rect.x);text.setAttribute('y',rect.y+10);labels.push(rect);placed=true;break}}
    if(!placed){text.setAttribute('x',p.x+8);text.setAttribute('y',p.y-9)}text.dataset.clear=String(placed);g.append(text);
   }wires.append(g);
  }renderedNodes=nodes;renderedRepresentatives=representative;highlight();
 }
 function reveal(g){if(settings().labels==='none')return;g.querySelectorAll('.diagram-label').forEach(n=>{n.style.visibility='visible';n.classList.add('pt-label-highlight')})}
 function highlight(){if(focus&&!state.devices[focus])focus=null;if(edgeFocus&&![...document.querySelectorAll('.diagram-edge')].some(g=>g.dataset.key===edgeFocus))edgeFocus=null;const p=settings(),selectedNames=window.PacketTrackerWorkspace?.selected||new Set(),active=focus?[focus]:edgeFocus?[]:[...selectedNames],related=new Set(active);for(const g of document.querySelectorAll('.diagram-edge')){const on=!!(edgeFocus===g.dataset.key||active.includes(g.dataset.a)||active.includes(g.dataset.b));if(on){related.add(g.dataset.a);related.add(g.dataset.b)}g.classList.toggle('diagram-dim',!!p.focus&&!!(active.length||edgeFocus)&&!on);g.classList.toggle('diagram-focused',p.focus&&on);g.querySelectorAll('.diagram-label').forEach(n=>{n.classList.remove('pt-label-highlight');n.style.visibility=p.labels==='all'||p.labels==='smart'&&n.dataset.clear==='true'&&(!p.semantic_zoom||zoom>=.9)?'visible':'hidden'});if(on||g.classList.contains('diagram-hover'))reveal(g)}for(const n of document.querySelectorAll('#nodes .node'))n.classList.toggle('diagram-dim',!!p.focus&&!!(active.length||edgeFocus)&&!related.has(n.dataset.name))}
 work.addEventListener('focusin',e=>{const n=e.target.closest('.node');if(n){focus=n.dataset.name;edgeFocus=null;highlight()}});
 work.addEventListener('pointerover',e=>{const n=e.target.closest('.node');if(n){focus=n.dataset.name;edgeFocus=null;highlight()}});
 work.addEventListener('pointerout',e=>{if(e.target.closest('.node')&&!e.relatedTarget?.closest?.('.node')){focus=null;highlight()}});
 work.addEventListener('click',e=>{if(e.target===work){focus=null;edgeFocus=null;highlight()}});
 document.addEventListener('keydown',e=>{if(e.key==='Escape'){if(preview){preview=null;banner.hidden=true;renderTopology()}edgeFocus=null;focus=null;highlight()}});
 // Block canvas edits during a preview; Apply is the only position mutation.
 for(const type of ['pointerdown','click','dblclick'])document.addEventListener(type,e=>{if(preview&&work.contains(e.target)&&!banner.contains(e.target)){e.preventDefault();e.stopImmediatePropagation()}},true);
 window.PacketTrackerDiagram={tidy,settings,previewing:()=>!!preview,refresh:()=>renderTopology(),drag:dragCables};
 if(window.ptInitialReady)window.ptInitialReady.then(()=>renderTopology());
})();
