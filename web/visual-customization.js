/* Physical Workspace — Custom Icons & Backgrounds (§18).
   PNG/JPEG/GIF data lives in the exported lab, not browser-local cache.
*/
(() => {
'use strict';
const get=id=>document.getElementById(id);
const overlay=document.createElement('div');
overlay.id='ptVisualDialog';overlay.hidden=true;
overlay.setAttribute('role','dialog');overlay.setAttribute('aria-modal','true');
overlay.setAttribute('aria-labelledby','ptVisualHeading');
overlay.innerHTML=[
 '<section class="pt-visual-window">',
 '<header><strong id="ptVisualHeading">Customize Image</strong>',
 '<button type="button" id="ptVisualClose" aria-label="Close">×</button></header>',
 '<div class="pt-visual-body">',
 '<p class="pt-visual-hint" id="ptVisualHint"></p>',
 '<label>Existing Image<select id="ptVisualImages"></select></label>',
 '<label>Browse PNG/JPEG/GIF <input id="ptVisualFile" type="file" accept="image/png,image/jpeg,image/gif,.png,.jpg,.jpeg,.gif"></label>',
 '<div class="pt-visual-preview">',
 '<img id="ptVisualPreview" alt="Selected background or device icon preview" hidden>',
 '<span id="ptVisualDefault">Default image</span></div>',
 '<div id="ptVisualBackgroundOptions">',
 '<label><input id="ptVisualTiled" type="checkbox"> Display Tiled Background Image</label>',
 '<label>Background Colour <input id="ptVisualColor" type="color" value="#e7e7e7"></label>',
 '<p>Scale (read-only): <output id="ptVisualScale">Loading…</output></p>',
 '<p class="pt-visual-hint">Scale uses Packet Tracker and Simulator metric coordinates, not the identical vendor per-pixel defaults.</p>',
 '</div><p id="ptVisualError" role="alert" aria-live="assertive"></p></div>',
 '<footer><button type="button" id="ptVisualReset">Reset</button>',
 '<button type="button" id="ptVisualDelete">Delete Unused Image</button>',
 '<button type="button" id="ptVisualCancel">Cancel</button>',
 '<button type="button" id="ptVisualApply">Apply</button></footer>',
 '</section>'
].join('');
document.body.append(overlay);
const imageSelect=get('ptVisualImages'),fileInput=get('ptVisualFile');
const preview=get('ptVisualPreview'),placeholder=get('ptVisualDefault');
const error=get('ptVisualError');
let context=null,selection=null,lastFocused=null,locked=false;
const imageUrl=id=>id?'/api/visuals/assets/'+id:null;
function renderPreview(){
 preview.hidden=!selection;placeholder.hidden=!!selection;
 if(selection)preview.src=imageUrl(selection);
 else preview.removeAttribute('src');
}
function refreshImages(){
 const assets=Object.values(state.visual_assets||{});
 imageSelect.replaceChildren();
 const opt=document.createElement('option');opt.value='';opt.textContent='Default Image';
 imageSelect.append(opt);
 for(const a of assets){
  const option=document.createElement('option');option.value=a.id;
  option.textContent=(a.label||'Custom Image')+' · '+a.width+'×'+a.height+
    ' · '+Math.ceil(a.bytes/1024)+' KB';
  imageSelect.append(option);
 }
 imageSelect.value=selection||'';renderPreview();
}
function close(){
 if(locked)return;
 overlay.hidden=true;context=null;selection=null;fileInput.value='';
 lastFocused?.focus?.();
}
function status(message){error.textContent=message}
function setLock(value){
 locked=!!value;
 for(const input of overlay.querySelectorAll('button,select,input'))input.disabled=locked;
}
async function mutate(payload){
 const response=await fetch('/api/visuals/action',{
  method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(payload)});
 const result=await response.json();
 if(!response.ok||!result.ok)throw Error(result.error||result.output||'Visual API request failed');
 state=result.state;
 if(typeof render==='function')render();
 window.dispatchEvent(new Event('pt-visuals-refresh'));
 return result;
}
async function uploadFile(file){
 if(!['image/png','image/jpeg','image/gif'].includes(file.type))
  throw Error('Only PNG and JPEG images are supported.');
 if(file.size<1||file.size>1000000)throw Error('Image must be 1MB or smaller.');
 const data=await new Promise((resolve,reject)=>{
  const reader=new FileReader();
  reader.onerror=()=>reject(Error('Could not read image file'));
  reader.onload=()=>resolve(String(reader.result).split(',')[1]||'');
  reader.readAsDataURL(file);
 });
 const result=await mutate({action:'upload_image',mime:file.type,
  data_base64:data,label:file.name.slice(0,80)});
 return result.asset_id;
}
async function open(kind,object,view='physical'){
 if(!state.visual_assets){status('Visual assets unavailable');return}
 lastFocused=document.activeElement;context={kind,object,view};
 fileInput.value='';status('');
 get('ptVisualBackgroundOptions').hidden=kind!=='background';
 get('ptVisualHeading').textContent=kind==='background'?
   'Set Background — '+(object==='intercity'?'Intercity':state.physical_locations?.[object]?.name||object):
   'Customize Icon in '+(view==='logical'?'Logical':'Physical')+' View — '+object;
 get('ptVisualHint').textContent=kind==='background'?
  'Choose a PNG/JPEG/GIF for this location. Images are embedded in exported lab JSON.':
  'Choose a PNG/JPEG/GIF icon (45 × 31 pixels recommended). Logical and Physical icons are independent.';
 const existing=kind==='background'?state.location_backgrounds?.[object]:kind==='cluster'?state.cluster_icons?.[object]:
   state.device_icons?.[object]?.[view];
 selection=(kind==='background'?existing?.asset_id:existing)||null;
 get('ptVisualTiled').checked=!!existing?.tiled;
 get('ptVisualColor').value=existing?.color||'#e7e7e7';
 refreshImages();overlay.hidden=false;get('ptVisualClose').focus();
 if(kind==='background'&&object.startsWith('logical:'))get('ptVisualScale').textContent='Logical canvas coordinates';
 if(kind==='background'&&!object.startsWith('logical:')){
  try{
   const response=await fetch('/api/physical-distance?location='+encodeURIComponent(object));
   const data=await response.json();if(!data.ok)throw Error(data.error||'scale unavailable');
   if(context?.object===object)get('ptVisualScale').textContent=
    Number(data.geometry.meters_per_x).toFixed(5)+'m per X canvas unit; '+
    Number(data.geometry.meters_per_y).toFixed(5)+'m per Y canvas unit';
  }catch(err){get('ptVisualScale').textContent=err.message}
 }
}
async function applyChange(reset=false){
 if(!context)return;
 setLock(true);status('');
 try{
  const target={...context};
  const payload=target.kind==='background'?
   {action:'set_background',location:target.object,asset_id:reset?null:selection,
    tiled:reset?false:get('ptVisualTiled').checked,
    color:reset?'#e7e7e7':get('ptVisualColor').value}:
   target.kind==='cluster'?{action:'set_cluster_icon',cluster:target.object,asset_id:reset?null:selection}:
   {action:'set_device_icon',device:target.object,view:target.view,asset_id:reset?null:selection};
  await mutate(payload);
  setLock(false);close();
 }catch(err){status(err.message);setLock(false)}
}
get('ptVisualClose').onclick=get('ptVisualCancel').onclick=close;
get('ptVisualApply').onclick=()=>applyChange(false);
get('ptVisualReset').onclick=()=>applyChange(true);
get('ptVisualDelete').onclick=async()=>{
 if(!selection){status('Choose an uploaded image to delete.');return}
 setLock(true);status('');
 try{
  await mutate({action:'delete_image',asset_id:selection});
  selection=null;refreshImages();status('Unused image deleted from the lab.');
 }catch(err){status(err.message)}
 finally{setLock(false)}
};
imageSelect.onchange=()=>{selection=imageSelect.value||null;renderPreview();status('')};
fileInput.onchange=async()=>{
 const file=fileInput.files?.[0];if(!file||!context)return;
 setLock(true);
 try{
  selection=await uploadFile(file);
  refreshImages();status('Image saved in lab. Click Apply to use it.');
 }catch(err){status(err.message)}
 finally{setLock(false);fileInput.value=''}
};
overlay.addEventListener('pointerdown',e=>{if(e.target===overlay)close()});
document.addEventListener('keydown',e=>{
 if(!overlay.hidden&&e.key==='Escape'){
  e.preventDefault();e.stopImmediatePropagation();close();
 }
},true);
function renderLogical(){
 const context=window.PacketTrackerLogicalContext?.();
 if(context?.mode==='logical'){
  const background=state.location_backgrounds?.['logical:'+context.cluster]||{};
  const workspace=get('workspace');
  workspace.style.backgroundColor=background.color||'';
  workspace.style.backgroundImage=background.asset_id?'url("'+imageUrl(background.asset_id)+'")':'';
  workspace.style.backgroundRepeat=background.tiled?'repeat':'no-repeat';
  workspace.style.backgroundSize=background.tiled?'auto':'cover';
 }

 for(const node of document.querySelectorAll('#nodes .node[data-name]')){
  const id=state.device_icons?.[node.dataset.name]?.logical;if(!id)continue;
  const icon=node.querySelector('.device-icon');if(!icon)continue;
  let img=icon.querySelector('img');
  if(!img){img=document.createElement('img');icon.prepend(img)}
  img.src=imageUrl(id);img.alt='';
  const fallback=icon.querySelector('span');if(fallback)fallback.style.display='none';
  img.onerror=()=>{img.remove();if(fallback)fallback.style.display=''};
 }
}
function renderPhysical(){
 const root=get('ptPhysicalWorkspace');if(!root)return;
 const location=window.PacketTrackerVisual.currentLocation||'intercity';
 const background=state.location_backgrounds?.[location]||{};
 const image=background.asset_id?'url("'+imageUrl(background.asset_id)+'")':'';
 root.style.backgroundColor=background.color||'';
 for(const map of root.querySelectorAll('.pt-map-cards,.pt-physical-furniture')){
  map.style.backgroundColor=background.color||'';
  map.style.backgroundImage=image;
  map.style.backgroundRepeat=background.tiled?'repeat':'no-repeat';
  map.style.backgroundSize=background.tiled?'auto':'cover';
  map.style.backgroundPosition='center';
 }
 const icons=state.device_icons||{};
 for(const card of root.querySelectorAll('[data-physical-device]')){
  const id=icons[card.dataset.physicalDevice]?.physical;if(!id)continue;
  const button=card.querySelector('.pt-map-device-open');if(!button)continue;
  let img=button.querySelector('img');
  if(!img){img=document.createElement('img');button.prepend(img)}
  img.src=imageUrl(id);img.alt='';
 }
 for(const row of root.querySelectorAll('.pt-physical-equipped')){
  const name=row.querySelector('button.pt-rack-device span')?.textContent;
  const id=icons[name]?.physical;if(!id)continue;
  const button=row.querySelector('.pt-rack-device');
  let img=button.querySelector('img');
  if(!img){img=document.createElement('img');button.prepend(img)}
  img.src=imageUrl(id);img.alt='';
 }
}
const oldPhysical=window.renderPhysical;
if(typeof oldPhysical==='function'){
 window.renderPhysical=function(device,body){
  oldPhysical(device,body);
  const controls=body.querySelectorAll('.pt-physical-customize button,.physical-icons button');
  for(const button of controls){
   button.disabled=false;
   const view=button.textContent.includes('Logical')?'logical':'physical';
   button.onclick=()=>open('icon',device.name,view);
  }
 };
}
const oldTopology=window.renderTopology;
if(typeof oldTopology==='function'){
 window.renderTopology=function(){oldTopology();renderLogical()};
}
window.PacketTrackerVisual={
 openClusterIcon:cluster=>open('cluster',cluster,'logical'),
 openBackground:location=>open('background',location),
 openIcon:(name,view='physical')=>open('icon',name,view),
 renderPhysical,renderLogical,
 get currentLocation(){return this._location||'intercity'},
 set currentLocation(id){this._location=id}
};
})();
