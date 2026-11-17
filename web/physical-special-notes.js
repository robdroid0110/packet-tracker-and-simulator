/* Help §22: metric physical grids and undoable equipment-preserving deletion. */
(() => {
'use strict';
const root=document.getElementById('ptPhysicalWorkspace');
const dialog=document.createElement('dialog');dialog.id='ptPhysicalSettings';
dialog.setAttribute('aria-labelledby','ptPhysicalSettingsTitle');
document.body.append(dialog);
let generation=0,returnFocus=null;
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
async function request(path,body){
 const response=await fetch(path,body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:undefined);
 const data=await response.json();
 if(!response.ok||data.ok===false)throw Error(data.error||data.output||'Physical workspace request failed');
 return data;
}
function current(){return root.dataset.location||'intercity'}
function open(title){
 returnFocus=document.activeElement;
 dialog.replaceChildren(el('h2',title));dialog.firstChild.id='ptPhysicalSettingsTitle';
 const form=el('form');form.method='dialog';
 const body=el('div');body.className='pt-physical-settings-fields';
 const message=el('p');message.setAttribute('role','status');message.setAttribute('aria-live','polite');
 const footer=el('footer'),cancel=el('button','Cancel'),apply=el('button','Apply');
 cancel.type='button';cancel.onclick=()=>dialog.close();apply.type='submit';
 footer.append(cancel,apply);form.append(body,message,footer);dialog.append(form);dialog.showModal();
 return {form,body,message,apply};
}
function restoreFocus(){
 const target=returnFocus?.isConnected&&returnFocus!==document.body&&
  returnFocus.matches('button,a[href],input,select,textarea,[tabindex]')
  ?returnFocus:document.querySelector('[title="Configure Physical Grid"]');
 target?.focus();
}
dialog.addEventListener('close',restoreFocus);
dialog.addEventListener('cancel',event=>{event.preventDefault();dialog.close();restoreFocus()});
function field(body,label,input){const row=el('label',label);row.append(input);body.append(row);return input}
async function write(body){
 const result=await request('/api/physical-workspace/action',body);
 await fetchState();return result;
}
async function openGrid(){
 let data;
 try{data=await request('/api/physical-workspace?location='+encodeURIComponent(current()))}
 catch(error){status(error.message);return}
 const ui=open('Physical Grid');
 const type=el('select');type.id='ptGridType';
 for(const kind of Object.keys(data.grid_profiles)){
  const option=el('option',kind);option.value=kind;type.append(option);
 }
 type.value=data.grid.supported?data.grid.container_type:'generic';
 field(ui.body,'Container type',type);
 const enabled=el('input');enabled.type='checkbox';enabled.id='ptGridEnabled';field(ui.body,'Show grid',enabled);
 const spacing=el('input');spacing.type='number';spacing.min='0.01';spacing.max='1000000';spacing.step='any';spacing.required=true;spacing.id='ptGridSpacing';field(ui.body,'Grid spacing (meters)',spacing);
 const color=el('input');color.type='color';color.id='ptGridColor';field(ui.body,'Grid line color',color);
 ui.body.append(el('p','Settings apply to every container of this type and are saved in the lab. Grid spacing follows container dimensions. Closets and ICPs use their own furniture or panel views. Lines below 4 canvas units are hidden to avoid an unreadable grid.'));
 function fill(){const p=data.grid_profiles[type.value];enabled.checked=p.enabled;spacing.value=p.spacing_m;color.value=p.color}
 type.onchange=fill;fill();
 ui.form.onsubmit=async event=>{
  event.preventDefault();ui.apply.disabled=true;
  try{
   await write({action:'set_grid',container_type:type.value,enabled:enabled.checked,spacing_m:Number(spacing.value),color:color.value});
   dialog.close();status('Physical grid saved');
  }catch(error){ui.message.textContent=error.message}
  finally{ui.apply.disabled=false}
 };
 type.focus();
}
async function openDelete(location){
 let data;
 try{data=await request('/api/physical-workspace?location='+encodeURIComponent(location))}
 catch(error){status(error.message);return}
 if(!data.delete_preview){status('Intercity cannot be deleted');return}
 const plan=data.delete_preview,ui=open('Delete '+data.current.name+'?');
 const destination=data.locations[plan.destination]?.name||'Intercity';
 ui.body.append(el('p','Remove '+plan.removed_locations.length+' container(s). Extract '+plan.extracted_devices.length+' device(s) onto the floor of '+destination+'. Network configurations and cables are preserved. Undo restores the entire operation.'));
 const details=el('details'),summary=el('summary','Affected containers and equipment');details.append(summary);
 const list=el('ul');
 for(const id of plan.removed_locations)list.append(el('li','Container: '+data.locations[id].name));
 for(const name of plan.extracted_devices)list.append(el('li','Device: '+name));
 details.append(list);ui.body.append(details);
 ui.apply.textContent='Delete location';ui.apply.dataset.deleteLocation=location;
 ui.form.onsubmit=async event=>{
  event.preventDefault();ui.apply.disabled=true;
  try{
   await write({action:'delete_location',location});dialog.close();
   window.dispatchEvent(new CustomEvent('pt-physical-focus-location',{detail:{location:plan.destination}}));
   status('Location deleted; equipment extracted to '+destination);
  }catch(error){ui.message.textContent=error.message}
  finally{ui.apply.disabled=false}
 };
 ui.form.querySelector('button').focus();
}
async function render(location){
 const ticket=++generation;
 if(root.hidden)return;
 try{
  const data=await request('/api/physical-workspace?location='+encodeURIComponent(location));
  if(ticket!==generation||root.hidden)return;
  const map=root.querySelector('.pt-map-cards');if(!map)return;
  map.querySelector('.pt-metric-grid')?.remove();
  delete map.dataset.gridDensity;delete map.dataset.gridSpacingX;delete map.dataset.gridSpacingY;
  const g=data.grid;map.dataset.gridEnabled=String(g.supported&&g.enabled);
  if(!g.supported||!g.enabled)return;
  map.dataset.gridSpacingX=String(g.spacing_x_px);map.dataset.gridSpacingY=String(g.spacing_y_px);
  if(Math.min(g.spacing_x_px,g.spacing_y_px)<4){
   map.dataset.gridDensity='hidden';return;
  }
  map.dataset.gridDensity='visible';
  const ns='http://www.w3.org/2000/svg',svg=document.createElementNS(ns,'svg');
  svg.classList.add('pt-metric-grid');svg.setAttribute('aria-hidden','true');
  const defs=document.createElementNS(ns,'defs'),pattern=document.createElementNS(ns,'pattern');
  pattern.id='ptMetricGridPattern';pattern.setAttribute('patternUnits','userSpaceOnUse');
  pattern.setAttribute('width',g.spacing_x_px);pattern.setAttribute('height',g.spacing_y_px);
  const path=document.createElementNS(ns,'path');
  path.setAttribute('d',`M ${g.spacing_x_px} 0 H 0 V ${g.spacing_y_px}`);
  path.setAttribute('fill','none');path.setAttribute('stroke',g.color);path.setAttribute('stroke-width','1');
  pattern.append(path);defs.append(pattern);
  const rect=document.createElementNS(ns,'rect');rect.setAttribute('width','100%');rect.setAttribute('height','100%');rect.setAttribute('fill','url(#ptMetricGridPattern)');
  svg.append(defs,rect);map.prepend(svg);
 }catch(error){console.warn('Physical grid unavailable:',error.message)}
}
root.addEventListener('click',event=>{
 if(activeTool!=='delete')return;
 const target=event.target.closest('[data-location]');
 if(target&&target!==root){
  event.preventDefault();event.stopImmediatePropagation();openDelete(target.dataset.location);
 }
},true);
window.PacketTrackerPhysicalSettings={openGrid,openDelete,render};
})();
