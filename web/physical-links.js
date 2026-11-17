/* legacy network simulator help: physical link/media selection, ports and device power. */
(() => {
'use strict';

const types={auto:'Automatically Choose Connection Type','copper-straight':'Copper Straight-Through','copper-cross':'Copper Cross-Over',console:'Console','fiber-mm':'Fiber Multi-mode','fiber-sm':'Fiber Single-mode','serial-dce':'Serial DCE','serial-dte':'Serial DTE',phone:'Phone',coax:'Coaxial',octal:'Octal',usb:'USB',ioe:'IoE Custom Cable'};
const media={auto:['copper','fiber-mm','fiber-sm','serial'], 'copper-straight':['copper'],'copper-cross':['copper'],console:['console','rs232'],'fiber-mm':['fiber-mm'],'fiber-sm':['fiber-sm'],'serial-dce':['serial'],'serial-dte':['serial'],phone:['modem'],coax:['coax'],octal:['async','console'],usb:['usb'],ioe:['ioe']};
const menu=document.createElement('div');menu.id='ptPortDialog';menu.className='pt-port-picker hidden';menu.setAttribute('role','dialog');menu.setAttribute('aria-label','Choose interface');document.body.append(menu);
let source=null,sourcePort=null,anchor=null,busy=false,keyboardReturn=null;
const quote=value=>"'"+String(value).replace(/'/g,"'\\''")+"'";
const preview=document.createElementNS('http://www.w3.org/2000/svg','line');preview.id='ptCablePreview';preview.setAttribute('stroke','#333');preview.setAttribute('stroke-width','2');preview.setAttribute('stroke-dasharray','5 4');preview.style.pointerEvents='none';
function clear(){source=null;sourcePort=null;anchor=null;linkSource=null;keyboardReturn=null;menu.classList.add('hidden');preview.remove()}
function ports(name){
 const used=new Set(state.links.flatMap(l=>[...(l.a_device===name?[l.a_if]:[]),...(l.b_device===name?[l.b_if]:[])]));
 return Object.values(state.devices[name]?.interfaces||{}).filter(p=>!p.parent&&!used.has(p.name)&&(media[selectedCableType||'auto']||[]).includes(p.media)).filter(p=>!sourcePort||selectedCableType!=='console'||p.media!==state.devices[source].interfaces[sourcePort].media);
}
function choose(name,event){
 const keyboard=event.detail===0;keyboardReturn=keyboard?name:null;
 menu.setAttribute('aria-label',name+' — Select an interface');
 const available=ports(name);menu.replaceChildren();const title=document.createElement('strong');title.textContent=name+' — Select an interface';menu.append(title);
 if(!available.length){const message=document.createElement('p');message.textContent='No free compatible interfaces';menu.append(message)}
 for(const port of available){const button=document.createElement('button');button.type='button';button.textContent=port.name+' ('+port.media+')';button.onclick=async()=>{
  menu.classList.add('hidden');
  if(!source){source=name;sourcePort=port.name;linkSource=name;anchor=center(name);preview.setAttribute('x1',anchor.x);preview.setAttribute('y1',anchor.y);preview.setAttribute('x2',anchor.x);preview.setAttribute('y2',anchor.y);wires.append(preview);if(keyboard)window.PacketTrackerCanvas?.focus(name);status('Choose the destination device and interface');return}
  if(source===name){status('Choose a different device');return}
  const a=source,ap=sourcePort,cable=selectedCableType||'auto';clear();
  if(keyboard)window.PacketTrackerCanvas?.focus(name);
  const result=await command('connect '+[a,ap,name,port.name,cable].map(quote).join(' '),false);
  if(!result.ok){status(result.output);return}
  const link=state.links.find(l=>l.a_device===a&&l.a_if===ap&&l.b_device===name&&l.b_if===port.name);
  if(!window.ptCableLocked)setTool('select');
  status((types[cable]||cable)+' connected: '+(link?.up?'link UP':'link DOWN — '+(link?.status||'no carrier')));
 };menu.append(button)}
 const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Cancel connection';cancel.onclick=()=>{clear();setTool('select');if(keyboard)window.PacketTrackerCanvas?.focus(name)};menu.append(cancel);
 menu.style.left=Math.max(4,Math.min(event.clientX,window.innerWidth-230))+'px';menu.style.top=Math.max(4,Math.min(event.clientY,window.innerHeight-240))+'px';menu.classList.remove('hidden');menu.querySelector('button')?.focus();
}
const previousNodeClick=nodeClick;
nodeClick=function(e,name){
 if(activeTool!=='cable')return previousNodeClick(e,name);
 if(dragged){dragged=false;return}
 if(busy)return;
 if(source===name){status('Choose a different destination device');return}
 if(selectedCableType==='auto'){
  if(!source){
   source=name;linkSource=name;anchor=center(name);renderTopology();
   preview.setAttribute('x1',anchor.x);preview.setAttribute('y1',anchor.y);preview.setAttribute('x2',anchor.x);preview.setAttribute('y2',anchor.y);wires.append(preview);
   status('Choose the destination device');return;
  }
  const a=source;clear();busy=true;
  command('auto-connect '+quote(a)+' '+quote(name),false).then(result=>{
   if(!result.ok){status(result.output);return}
   const link=[...state.links].reverse().find(l=>l.a_device===a&&l.b_device===name);
   if(!window.ptCableLocked)setTool('select');
   status(result.output+(link?' — '+(link.up?'link UP':'link DOWN: '+link.status):''));
  }).catch(error=>status('Connection failed: '+error.message)).finally(()=>{busy=false});
  return;
 }
 choose(name,e);
};
window.addEventListener('pointermove',event=>{if(!source||activeTool!=='cable'||!anchor)return;const rect=workspace.getBoundingClientRect();preview.setAttribute('x2',(event.clientX-rect.left-(window.ptPan?.x||0))/zoom);preview.setAttribute('y2',(event.clientY-rect.top-(window.ptPan?.y||0))/zoom);if(!preview.isConnected)wires.append(preview)});
const previousSetTool=setTool;setTool=function(tool){if(tool!=='cable'||source||!menu.classList.contains('hidden'))clear();return previousSetTool(tool)};
document.addEventListener('keydown',event=>{if(event.key==='Escape'&&(source||!menu.classList.contains('hidden'))){const back=keyboardReturn;clear();setTool('select');if(back)window.PacketTrackerCanvas?.focus(back);event.stopImmediatePropagation()}});
document.addEventListener('pointerdown',event=>{if(!menu.classList.contains('hidden')&&!menu.contains(event.target)&&!event.target.closest('.node'))menu.classList.add('hidden')});

const previousPhysical=renderPhysical;
renderPhysical=function(device,body){
 previousPhysical(device,body);
 const stage=body.querySelector('.pt-physical-stage');
 if(!stage)return;
 const powered=device.powered!==false;
 const power=document.createElement('button');
 power.id='ptDevicePower';
 power.className='pt-device-power'+(powered?' on':' off');
 power.type='button';
 power.setAttribute('aria-label',powered?'Power off '+device.name:'Power on '+device.name);
 power.title=powered?'Power OFF (physical device)':'Power ON (physical device)';
 power.innerHTML='<span class="pt-power-glyph">⏻</span><span>'+(powered?'ON':'OFF')+'</span>';
 stage.appendChild(power);
 stage.classList.toggle('pt-device-is-off',!powered);
 power.onclick=async()=>{
  const result=await command('power '+selected+' '+(powered?'off':'on'),false);
  status(result.output);
  if(result.ok)renderDialog();
 };
 const description=body.querySelector('#ptModuleDesc');
 if(description)description.textContent=
  'Power '+(powered?'ON':'OFF')+' — Use the module controls below to install or remove supported modules. Power off first.';
 const deviceName=device.name;
 fetch('/api/device-config?device='+encodeURIComponent(deviceName)).then(r=>r.json()).then(data=>{
  if(!stage.isConnected||selected!==deviceName||dialogTab!=='physical'||!data.ok||!data.modules.length)return;
  const section=document.createElement('section');section.className='pt-physical-slots';const heading=document.createElement('strong');heading.textContent='Module slots';section.append(heading);
  for(const slot of data.modules){const row=document.createElement('label');row.textContent=slot.slot+' ';const select=document.createElement('select');select.setAttribute('aria-label','Module in '+slot.slot);
   for(const type of ['none',...slot.available]){const option=document.createElement('option');option.value=type;option.textContent=type;option.selected=(slot.module||'none')===type;select.append(option)}
   const apply=document.createElement('button');apply.type='button';apply.textContent='Apply';apply.disabled=powered;apply.onclick=async()=>{const r=await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({device:deviceName,action:'module',slot:slot.slot,module:select.value==='none'?null:select.value})});const value=await r.json();if(value.state)state=value.state;status(value.ok?'Module updated':value.output||value.error);render()};row.append(select,apply);section.append(row)}
  body.querySelector('.pt-physical-content')?.append(section);
 }).catch(error=>status(error.message));
};
})();
