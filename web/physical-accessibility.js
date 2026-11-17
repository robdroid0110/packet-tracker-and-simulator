/* legacy network simulator Help §21 — accessible Physical Workspace navigator.
 * Browser selection is ephemeral; all mutations use the authoritative agent API.
 */
(() => {
'use strict';
const dialog=document.createElement('section');
dialog.id='ptAccessiblePhysical';dialog.hidden=true;
dialog.setAttribute('role','dialog');dialog.setAttribute('aria-modal','true');
dialog.setAttribute('aria-labelledby','ptA11yTitle');
dialog.setAttribute('aria-describedby','ptA11yHelp');
dialog.innerHTML=[
 '<div class="pt-a11y-window">',
 '<header><h2 id="ptA11yTitle">Physical Workspace — Accessible Navigation</h2>',
 '<button id="ptA11yClose" aria-label="Close accessible navigation">×</button></header>',
 '<p id="ptA11yHelp">Tab or Shift+Tab moves between controls. Arrow Up/Down traverses location or device buttons,',
 ' Enter opens a location or selects a device. Arrow Right enters a focused location,',
 ' Arrow Left returns to the parent. Escape closes this dialog.</p>',
 '<div class="pt-a11y-main">',
 '<nav class="pt-a11y-nav" aria-label="Physical locations">',
 '<h3>Locations</h3><div id="ptA11yBreadcrumb"></div><div id="ptA11yTree"></div></nav>',
 '<div class="pt-a11y-content"><h3 id="ptA11yCurrent" tabindex="-1">Intercity</h3>',
 '<div id="ptA11yActions"></div><div id="ptA11yEquipment"></div>',
 '<div id="ptA11yConnections"></div></div></div>',
 '<footer><p id="ptA11yStatus" role="status" aria-live="polite" aria-atomic="true">Ready.</p>',
 '<button id="ptA11yRefresh">Refresh</button><button id="ptA11yDone">Close</button></footer></div>'
].join('');
document.body.append(dialog);
const by=id=>document.getElementById(id);
const e=(tag,text,cls)=>{
 const el=document.createElement(tag);
 if(text!==undefined)el.textContent=String(text);
 if(cls)el.className=cls;
 return el;
};
const b=(text,fn,cls='')=>{const el=e('button',text,cls);el.type='button';el.onclick=fn;return el};
let location='intercity',view=null,selectedDevice=null,sourcePort=null;
let focusReturn=null,hiddenRoots=[],sequence=0,busy=false;
function announce(text,error=false){
 const status=by('ptA11yStatus');status.textContent=text;
 status.classList.toggle('error',error);
}
function close(){
 if(dialog.hidden)return;
 ++sequence;dialog.hidden=true;
 for(const el of hiddenRoots)el.inert=false;
 hiddenRoots=[];
 const candidate=focusReturn?.isConnected&&!focusReturn.inert&&!dialog.contains(focusReturn)&&
  focusReturn!==document.body&&focusReturn.matches('button,a[href],input,select,textarea,[tabindex]')
  ?focusReturn:null;
 const fallback=document.querySelector('[title="Accessible Physical Navigation"]') ||
  document.querySelectorAll('.workspace-tab')[1];
 const returnTo=candidate||fallback;
 returnTo?.focus();
 setTimeout(()=>{
  if(dialog.hidden&&(dialog.contains(document.activeElement)||document.activeElement===document.body))
   returnTo?.focus();
 },0);
}
function open(next){
 if(!dialog.hidden){if(next)return load(next);close();return}
 focusReturn=document.activeElement;
 dialog.hidden=false;
 hiddenRoots=[...document.body.children].filter(x=>x!==dialog&&!x.inert);
 for(const el of hiddenRoots)el.inert=true;
 selectedDevice=null;sourcePort=null;
 load(next||by('ptPhysicalWorkspace')?.dataset.location||'intercity','first');
}
function treeNode(item,depth=0){
 const li=e('li'),button=b(item.name+' — '+item.type,()=>load(item.id),'pt-a11y-nav-btn');
 button.dataset.location=item.id;
 button.style.paddingLeft=(8+Math.min(depth,10)*14)+'px';
 button.setAttribute('aria-label','Enter '+item.type+' '+item.name);
 if(item.id===location){button.classList.add('current');button.setAttribute('aria-current','location')}
 li.append(button);
 if(item.children?.length){
  const nested=e('ul',undefined,'pt-a11y-list');
  for(const child of item.children)nested.append(treeNode(child,depth+1));
  li.append(nested);
 }
 return li;
}
function drawTree(){
 const tree=by('ptA11yTree');tree.replaceChildren();
 const ul=e('ul',undefined,'pt-a11y-list');
 ul.setAttribute('aria-label','Physical location hierarchy');
 if(view.tree)ul.append(treeNode(view.tree));tree.append(ul);
 const path=by('ptA11yBreadcrumb');path.replaceChildren();
 for(const [i,part] of view.path.entries()){
  if(i)path.append(e('span',' / '));
  const button=b(part.name,()=>load(part.id));
  if(part.id===location)button.setAttribute('aria-current','location');
  path.append(button);
 }
}
async function load(next,focus='heading'){
 const ticket=++sequence;
 try{
  const response=await fetch('/api/physical-accessibility?location='+encodeURIComponent(next),{cache:'no-store'});
  const result=await response.json();
  if(!response.ok||!result.ok)throw Error(result.error||'Accessibility view unavailable');
  if(dialog.hidden||ticket!==sequence)return;
  view=result;location=result.location;
  drawTree();drawCurrent();
  if(focus==='heading')by('ptA11yCurrent').focus();
  if(focus==='first')dialog.querySelector('.pt-a11y-nav-btn')?.focus();
  announce('Entered '+view.name+'. '+view.count.locations+' child locations, '+
   view.count.devices+' devices, '+view.count.links+' cables.');
 }catch(ex){if(ticket===sequence)announce(ex.message,true)}
}
async function action(payload){
 if(busy)return false;
 busy=true;
 try{
  const response=await fetch('/api/physical-accessibility/action',{
   method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
  const result=await response.json();
  if(!response.ok||!result.ok)throw Error(result.error||result.output||'Action failed');
  // Use the same model and state object as the standard GUI.
  if(typeof state!=='undefined')state=result.state;
  window.dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location}}));
  await load(location);
  announce(result.output);return true;
 }catch(ex){announce(ex.message,true);return false}
 finally{busy=false}
}
function addDevice(){
 const model=by('ptA11yModel')?.value;
 const name=by('ptA11yName')?.value.trim();
 if(!/^[A-Za-z][A-Za-z0-9_-]{0,30}$/.test(name||'')){
  announce('Name must start with a letter and contain 1–31 letters, digits, underscore or hyphen.',true);return;
 }
 action({action:'add_device',model,name,location,x:200,y:150});
}
async function placeHere(surface=null,shelf=null){
 const name=selectedDevice;
 if(!name){announce('First select a device using Take.',true);return}
 if(!view.devices.some(x=>x.name===name)){
  if(!await action({action:'move_device',device:name,location}))return;
 }
 let success=true;
 if(surface&&surface!=='cabinet'&&surface!=='door'){
  success=await action({action:'mount_device',device:name,surface,
   ...(surface==='shelf'?{shelf}:{})});
 }else if(surface){
  success=await action({action:'place_icp_device',device:name,side:surface,x:200,y:160});
 }
 if(success){selectedDevice=null;drawCurrent()}
}
function drawCurrent(){
 by('ptA11yCurrent').textContent=view.name+' — '+view.type;
 const actions=by('ptA11yActions');actions.replaceChildren();
 const card=e('section',undefined,'pt-a11y-card');
 card.append(e('h4','Location actions'));
 if(view.parent)card.append(b('Back to '+(view.path.at(-2)?.name||'Intercity'),()=>load(view.parent)));
 if(selectedDevice){
  const carrying=e('p','Selected to take: '+selectedDevice+
   '. The original device stays in place until you use Place.');carrying.id='ptA11yCarried';
  card.append(carrying,
   b('Place '+selectedDevice+' in '+view.name,()=>placeHere(), 'pt-a11y-place'),
   b('Cancel take',()=>{selectedDevice=null;drawCurrent();announce('Device selection cleared.')}));
 }
 if(view.type==='closet'){
  card.append(e('h4','Rack and equipment placement'),
   e('p','Rack is a mounting area; numbered rack-unit slots are not modeled.'));
  const group=e('div',undefined,'pt-a11y-surface-row');
  for(const surface of view.surfaces){
   const [type,index]=surface.id.split(':');
   const place=b('Place on '+surface.name+' ('+surface.count+')',
    ()=>placeHere(type,type==='shelf'?Number(index):null));
   place.setAttribute('aria-label','Place selected device on '+surface.name);
   group.append(place);
  }
  card.append(group,b('Add storage shelf',()=>action({action:'add_shelf',location})));
 }else if(view.type==='icp'&&selectedDevice){
  card.append(b('Place on ICP cabinet',()=>placeHere('cabinet')),
              b('Place on ICP door',()=>placeHere('door')));
 }
 const form=e('div',undefined,'pt-a11y-add-device');
 form.append(e('h4','Component box — add a device'));
 const model=e('select');model.id='ptA11yModel';model.setAttribute('aria-label','Device model');
 for(const [value,label] of [['pc','PC'],['router','Router'],['switch','Switch'],['server','Server']]){
  const option=e('option',label);option.value=value;model.append(option);
 }
 const name=e('input');name.id='ptA11yName';name.maxLength=31;name.placeholder='PC21';
 name.setAttribute('aria-label','New device name');
 form.append(model,name,b('Add device to '+view.name,addDevice));
 card.append(form);actions.append(card);
 const equipment=by('ptA11yEquipment');equipment.replaceChildren();
 equipment.append(e('h4','Equipment in '+view.name+' ('+view.devices.length+')'));
 if(!view.devices.length)equipment.append(e('p','No devices in this location.'));
 for(const device of view.devices){
  const pane=e('section',undefined,'pt-a11y-card pt-a11y-device');
  const name=device.name;
  const label=name+' — '+device.model+', '+(device.powered?'powered on':'powered off')+
   ', '+device.surface+(device.shelf!==null?' shelf '+(device.shelf+1):'');
  const select=b(label,()=>{selectedDevice=name;drawCurrent();
   dialog.querySelector('.pt-a11y-selected-device')?.focus()},
   'pt-a11y-device-button');
  if(name===selectedDevice)select.classList.add('pt-a11y-selected-device');
  pane.append(select);
  const controls=e('div',undefined,'pt-a11y-controls');
  controls.append(
   b('Take '+name,()=>{selectedDevice=name;drawCurrent();
    dialog.querySelector('.pt-a11y-selected-device')?.focus();
    announce('Selected '+name+'. Navigate to a destination then choose Place or a mounting surface.');}),
   b(device.powered?'Power off':'Power on',
     ()=>action({action:'power',device:name,enabled:!device.powered})),
   b('Open configuration dialog',()=>{
    if(typeof openDevice==='function'){close();openDevice(name)}
    else announce('Device dialog integration is unavailable.',true);
   })
  );
  pane.append(controls);
  const portArea=e('div',undefined,'pt-a11y-ports');
  portArea.append(e('h5','Network ports ('+device.ports.length+')'));
  if(!device.ports.length)portArea.append(e('p','No simulated Ethernet ports.'));
  for(const port of device.ports){
   const row=e('div',undefined,'pt-a11y-port-row');
   const description=name+' '+port.name+' — '+(port.connected?
    'connected to '+port.peer.device+' '+port.peer.interface+', '+(port.operational?'UP':'DOWN'):
    'unused');
   row.append(e('span',description));
   if(port.connected){
    row.append(b('Disconnect '+name+' '+port.name,
      ()=>action({action:'disconnect',device:name,interface:port.name})));
   }else if(sourcePort){
    row.append(b('Connect '+sourcePort.device+' '+sourcePort.interface+
      ' to '+name+' '+port.name,async()=>{
       if(sourcePort.device===name&&sourcePort.interface===port.name){
        announce('Choose a different port.',true);return;
       }
       const success=await action({action:'connect',
        a_device:sourcePort.device,a_if:sourcePort.interface,
        b_device:name,b_if:port.name,cable:'auto'});
       if(success){sourcePort=null;drawCurrent()}
      }));
   }else{
    row.append(b('Select cable start '+name+' '+port.name,()=>{
     sourcePort={device:name,interface:port.name};drawCurrent();
     announce('Cable started at '+name+' '+port.name+'. Choose an unused destination port.');
    }));
   }
   portArea.append(row);
  }
  pane.append(portArea);
  if(device.slots?.length){
   const modules=e('details'),summary=e('summary','Expansion module slots ('+device.slots.length+')');
   modules.append(summary);
   const ul=e('ul',undefined,'pt-a11y-list');
   for(const slot of device.slots){
    const li=e('li',String(slot.slot)+' — '+(slot.module||'empty'));
    if(slot.editable){
     const label=e('label',' Module choice for '+name+' '+slot.slot);
     const picker=e('select');
     picker.setAttribute('aria-label','Module for '+name+' '+slot.slot);
     for(const type of ['none',...(slot.available||[])]){
      const option=e('option',type);option.value=type;
      if(type===(slot.module||'none'))option.selected=true;
      picker.append(option);
     }
     label.append(picker);
     const apply=b('Apply module to '+name+' '+slot.slot,
      ()=>action({action:'set_module',device:name,slot:slot.slot,module:picker.value}));
     apply.disabled=device.powered;
     apply.title=device.powered?'Power off the device before changing modules':'Apply selected expansion module';
     li.append(label,apply);
     if(device.powered)li.append(e('small',' Power off the device before module changes.'));
    }
    ul.append(li);
   }
   modules.append(ul);pane.append(modules);
  }
  equipment.append(pane);
 }
 const cables=by('ptA11yConnections');cables.replaceChildren();
 cables.append(e('h4','Cables involving this location ('+view.links.length+')'));
 if(sourcePort){
  cables.append(e('p','Selected cable start: '+sourcePort.device+' '+sourcePort.interface+'.'));
  cables.append(b('Cancel cable selection',()=>{sourcePort=null;drawCurrent();
   announce('Cable selection cancelled.')}));
 }
 if(!view.links.length)cables.append(e('p','No cables in this location.'));
 for(const link of view.links){
  cables.append(e('p',link.a_device+' '+link.a_if+' to '+
   link.b_device+' '+link.b_if+' — '+(link.up?'link UP':'link DOWN')+', '+link.status));
 }
}
by('ptA11yClose').onclick=by('ptA11yDone').onclick=close;
by('ptA11yRefresh').onclick=()=>load(location);
dialog.addEventListener('keydown',event=>{
 if(event.key==='Escape'){event.preventDefault();close();return}
 if(event.key==='Tab'){
  const nodes=[...dialog.querySelectorAll('button:not([disabled]),input:not([disabled]),select:not([disabled])')]
   .filter(n=>n.getClientRects().length);
  const index=nodes.indexOf(event.target);
  if(event.shiftKey&&index===0){event.preventDefault();nodes.at(-1)?.focus()}
  else if(!event.shiftKey&&index===nodes.length-1){event.preventDefault();nodes[0]?.focus()}
  return;
 }
 if(event.key==='ArrowDown'||event.key==='ArrowUp'){
  const selector=event.target.matches('.pt-a11y-nav-btn')?'.pt-a11y-nav-btn':
    event.target.matches('.pt-a11y-device-button')?'.pt-a11y-device-button':null;
  if(!selector)return;
  event.preventDefault();
  const siblings=[...dialog.querySelectorAll(selector)];
  const index=siblings.indexOf(event.target);
  siblings[(index+(event.key==='ArrowDown'?1:-1)+siblings.length)%siblings.length]?.focus();
 }else if((event.key==='ArrowLeft'||event.key==='Backspace')&&
          event.target.matches('.pt-a11y-nav-btn')&&view?.parent){
  event.preventDefault();load(view.parent);
 }else if(event.key==='ArrowRight'&&event.target.matches('.pt-a11y-nav-btn')){
  event.preventDefault();load(event.target.dataset.location);
 }
});
document.addEventListener('keydown',event=>{
 if(event.altKey&&event.shiftKey&&event.code==='KeyA'&&!event.ctrlKey&&!event.metaKey){
  event.preventDefault();event.stopPropagation();
  if(dialog.hidden)open();else close();
 }
});
window.PacketTrackerAccessible={open,close,navigate:load,
 get location(){return location},get view(){return view}};
})();
