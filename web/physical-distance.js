/* vendor Physical Workspace Distance Measurements (§17).
 * All distances and radio coverage come from the authoritative Python engine.
 * Visual overlays are only a projection; no wireless protocol association is
 * claimed or created by these controls.
 */
(() => {
'use strict';
const host=document.getElementById('ptPhysicalWorkspace');
let generation=0,lastLocation='intercity',showGrid=false;
function setting(){
 try{
  const prefs=JSON.parse(localStorage.getItem('packetTracker.preferences.v1'))||{};
  return prefs.showWirelessGrid===true;
 }catch{return false}
}
showGrid=setting();
const fmt=value=>Number.isFinite(value)?Number(value).toFixed(value>=100?1:2):'—';
const el=(tag,klass,text)=>{
 const node=document.createElement(tag);
 if(klass)node.className=klass;
 if(text!==undefined)node.textContent=String(text);
 return node;
};
function coverageLayer(map,data){
 map.querySelector('.pt-distance-cover')?.remove();
 if(!data.radios?.length)return;
 const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');
 svg.classList.add('pt-distance-cover');
 svg.setAttribute('width',String(Math.max(map.clientWidth,1000)));
 svg.setAttribute('height',String(Math.max(map.clientHeight,700)));
 svg.setAttribute('viewBox','0 0 '+Math.max(map.clientWidth,1000)+' '+Math.max(map.clientHeight,700));
 svg.setAttribute('aria-label','Geometric wireless range circles (not protocol associations)');
 svg.hidden=!showGrid;
 for(const radio of data.radios){
  if(!radio.powered)continue;
  const circle=document.createElementNS('http://www.w3.org/2000/svg','ellipse');
  const centerX=radio.x+(radio.location===lastLocation?52:0);
  const centerY=radio.y+(radio.location===lastLocation?42:0);
  // Don't construct off-screen geometry with unbounded radius.
  const rx=Math.max(0,Math.min(100000,radio.radius_x_px));
  const ry=Math.max(0,Math.min(100000,radio.radius_y_px));
  if(centerX+rx<0||centerY+ry<0||centerX-rx>map.clientWidth||centerY-ry>map.clientHeight)continue;
  circle.setAttribute('cx',String(centerX));
  circle.setAttribute('cy',String(centerY));
  circle.setAttribute('rx',String(rx));
  circle.setAttribute('ry',String(ry));
  circle.classList.add('pt-radio-'+radio.medium);
  circle.dataset.radioDevice=radio.device;
  const title=document.createElementNS('http://www.w3.org/2000/svg','title');
  title.textContent=radio.device+' · '+radio.medium+' radius '+fmt(radio.radius_m)+' m (coverage estimate, not associated)';
  circle.appendChild(title);
  svg.appendChild(circle);
 }
 map.prepend(svg);
}
function panel(data){
 host.querySelector('#ptDistancePanel')?.remove();
 const section=el('details','pt-distance-panel');
 section.id='ptDistancePanel';
 const sum=el('summary','',
  'Distances · '+data.links.length+' cables · '+data.radios.length+' radios');
 section.appendChild(sum);
 const body=el('div','pt-distance-content');
 body.appendChild(el('p','pt-distance-caption',
  'Calibrated 2D straight-line estimates, in metres. Ethernet 100 m limit '+(data.cable_length_effects?'ENFORCED':'not enforced')+'.'));
 const frame=data.geometry;
 body.appendChild(el('small','pt-distance-caption',
  'Map scale: '+fmt(frame.meters_per_x)+' m/x-unit; '+fmt(frame.meters_per_y)+' m/y-unit.'));
 const linkHeading=el('h4','','Cables (entire lab)');
 body.appendChild(linkHeading);
 const wireList=el('div','pt-distance-scroll');
 for(const cable of data.links.slice(0,75)){
  const entry=el('div','pt-distance-row '+(cable.operational?'pt-distance-up':'pt-distance-down'));
  const first=el('span','',
    cable.a_device+':'+cable.a_if+' → '+cable.b_device+':'+cable.b_if);
  const second=el('strong','',
    fmt(cable.total_length_m)+' m · '+(cable.operational?'UP':'DOWN'));
  entry.title='Cable segment and total '+fmt(cable.total_length_m)+' m (straight-line projection). '+cable.status+
   '. Physical bends/slack/pegboards not modeled.';
  entry.append(first,second);wireList.appendChild(entry);
 }
 if(data.links.length>75)wireList.append(el('p','','Showing first 75 cables. Use GET /api/physical-distance for all '+data.links.length+'.'));
 if(!data.links.length)wireList.append(el('p','','No cables in this lab.'));
 body.appendChild(wireList);
 body.appendChild(el('h4','','Wireless coverage (geometry only)'));
 const radioList=el('div','pt-distance-scroll');
 for(const radio of data.radios.slice(0,50)){
  const row=el('div','pt-radio-range-row');
  const name=el('label','',radio.device+' · '+radio.medium);
  const input=el('input','');
  input.type='number';input.min='0.1';input.max='100000';input.step='0.1';
  input.value=String(radio.radius_m);
  input.setAttribute('aria-label','Range radius in metres for '+radio.device);
  const button=el('button','','Set range');
  button.title='Update saved simulated wireless radius via API; no RF association engine';
  button.onclick=async()=>{
   const value=Number(input.value);
   if(!Number.isFinite(value)||value<0.1||value>100000){
    status.textContent='Range must be between 0.1 and 100000 m';return;
   }
   button.disabled=true;
   try{
    const response=await fetch('/api/physical-distance/action',{
     method:'POST',headers:{'content-type':'application/json'},
     body:JSON.stringify({action:'radio_range',device:radio.device,radius_m:value})});
    const result=await response.json();
    if(!response.ok||!result.ok)throw Error(result.error||result.output||'Range update failed');
    if(typeof fetchState==='function')await fetchState();
    status.textContent=radio.device+' radius set to '+fmt(value)+' m';
    render(lastLocation);
   }catch(error){status.textContent=error.message}
   finally{button.disabled=false}
  };
  row.append(name,input,button);radioList.append(row);
 }
 if(data.radios.length>50)radioList.append(el('p','','Showing first 50 radios; the API returns all.'));
 if(!data.radios.length)radioList.append(el('p','','No recognized wireless sources in this lab.'));
 body.appendChild(radioList);
 const pairs=data.radio_pairs||[];
 const inRange=pairs.filter(p=>p.within_range);
 body.appendChild(el('p','pt-distance-caption',
  inRange.length+' of '+pairs.length+' source-to-client range checks are within radius. Wi-Fi/Bluetooth/cellular association and packet forwarding are NOT modeled.'));
 const display=el('label','pt-distance-presentation');
 const gridCheck=el('input','');gridCheck.type='checkbox';gridCheck.checked=showGrid;
 gridCheck.onchange=()=>{
  showGrid=gridCheck.checked;
  try{
   const value=JSON.parse(localStorage.getItem('packetTracker.preferences.v1'))||{};
   value.showWirelessGrid=showGrid;
   localStorage.setItem('packetTracker.preferences.v1',JSON.stringify(value));
  }catch{}
  const overlay=host.querySelector('.pt-distance-cover');if(overlay)overlay.hidden=!showGrid;
  const pref=document.getElementById('ptPrefWirelessGrid');
  if(pref)pref.checked=showGrid;
 };
 display.append(gridCheck,document.createTextNode(' Show wireless grid'));
 body.append(display);
 body.append(el('p','pt-distance-caption',
   'Range circles are visual estimates only. Height, walls, attenuation, cell handoff and cable bending are not yet implemented.'));
 const status=el('p','pt-distance-status');
 status.setAttribute('role','status');status.setAttribute('aria-live','polite');
 body.append(status);section.append(body);
 host.append(section);
}
async function render(location='intercity'){
 lastLocation=location;
 const ticket=++generation;
 if(host.hidden)return;
 try{
  const response=await fetch('/api/physical-distance?location='+encodeURIComponent(location));
  const data=await response.json();
  if(ticket!==generation||!data.ok||host.hidden)return;
  const map=host.querySelector('.pt-map-cards');
  if(map)coverageLayer(map,data);
  panel(data);
 }catch(error){
  if(ticket===generation){console.warn('Physical measurements unavailable:',error.message)}
 }
}
window.addEventListener('pt-physical-presentation',event=>{
 showGrid=event.detail?.showWirelessGrid===true;
 const overlay=host.querySelector('.pt-distance-cover');
 if(overlay)overlay.hidden=!showGrid;
 const check=document.querySelector('#ptDistancePanel input[type=checkbox]');
 if(check)check.checked=showGrid;
});
window.addEventListener('pt-physical-distance-refresh',()=>render(lastLocation));
window.PacketTrackerDistance={render,get showWirelessGrid(){return showGrid}};
})();
