/* Compact viewport controller. All device and network state stays untouched. */
(() => {
 'use strict';
 const body=document.body,work=document.getElementById('workspace');
 const tabs=document.getElementById('workspaceTabs');
 const dock=document.getElementById('bottomDock');
 const right=document.getElementById('rightDock');
 const media=window.matchMedia('(max-width:1060px), (max-height:640px)');
 const actions=document.createElement('div');
 actions.className='pt-compact-actions';
 actions.setAttribute('role','group');
 actions.setAttribute('aria-label','Compact workspace panels');
 const buttons={};
 for(const [key,label,description] of [
  ['canvas','Canvas','Maximize the topology canvas'],
  ['devices','Devices','Show device categories and palette'],
  ['events','PDU','Show packet event and scenario panels'],
  ['fit','Fit','Fit the entire topology in the canvas']
 ]){
  const button=document.createElement('button');
  button.type='button';button.textContent=label;button.title=description;
  button.setAttribute('aria-label',description);
  button.setAttribute('aria-pressed','false');
  actions.append(button);buttons[key]=button;
 }
 tabs.insertBefore(actions,tabs.querySelector('.workspace-right'));
 const close=document.createElement('button');
 close.id='ptCompactClosePdu';close.type='button';
 close.setAttribute('aria-label','Close packet event panels');
 close.title='Close packet event panels';
 close.textContent='×';
 right.append(close);
 let mode='devices',eventsOpen=false,manualZoom=false,wideZoom=1,userModeChosen=false;
 let compactWasActive=false,resizeScheduled=false;
 const compact=()=>media.matches;
 function syncButtons(){
  body.classList.toggle('pt-compact-layout',compact());
  body.classList.toggle('pt-compact-canvas',compact()&&mode==='canvas');
  body.classList.toggle('pt-compact-events',compact()&&eventsOpen);
  buttons.canvas.setAttribute('aria-pressed',String(mode==='canvas'));
  buttons.devices.setAttribute('aria-pressed',String(mode==='devices'));
  buttons.events.setAttribute('aria-pressed',String(eventsOpen));
  buttons.events.setAttribute('aria-expanded',String(eventsOpen));
  buttons.events.setAttribute('aria-controls','rightDock');
  right.setAttribute('aria-label','Packet events and scenarios');
 }
 function setMode(next){
  userModeChosen=true;mode=next;eventsOpen=false;syncButtons();
  scheduleFit();
 }
 function toggleEvents(){
  userModeChosen=true;
  if(mode==='canvas')mode='devices';
  eventsOpen=!eventsOpen;
  if(eventsOpen)right.classList.remove('pdu-hidden');
  syncButtons();scheduleFit();
 }
 buttons.canvas.addEventListener('click',()=>setMode('canvas'));
 buttons.devices.addEventListener('click',()=>setMode('devices'));
 buttons.events.addEventListener('click',toggleEvents);
 buttons.fit.addEventListener('click',()=>{manualZoom=false;scheduleFit()});
 close.addEventListener('click',()=>{eventsOpen=false;syncButtons()});
 document.addEventListener('keydown',event=>{
  if(event.key==='Escape'&&eventsOpen){eventsOpen=false;syncButtons()}
 });
 for(const id of ['zoomIn','zoomOut','zoomReset']){
  document.getElementById(id)?.addEventListener('click',()=>{manualZoom=true});
 }
 document.getElementById('fitBtn')?.addEventListener('click',()=>{
  manualZoom=false;scheduleFit();
 });
 function fitCanvas(){
  if(!compact()||manualZoom||window.ptPointerActive||window.ptPlacementLocked||
     typeof zoom!=='number'||typeof setZoom!=='function')return;
  const bounds=work.getBoundingClientRect();
  if(bounds.width<200||bounds.height<100)return;
  const devices=Object.values(state?.devices||{});
  if(!devices.length)return;
  if(window.PacketTrackerCanvasCamera){
   window.PacketTrackerCanvasCamera.fit();
   return;
  }
  const xmax=Math.max(...devices.map(d=>Number(d.x)||0))+98;
  const ymax=Math.max(...devices.map(d=>Number(d.y)||0))+74;
  const target=Math.max(.05,Math.min(1,(bounds.width-30)/Math.max(xmax,1),
                                (bounds.height-30)/Math.max(ymax,1)));
  if(Math.abs(zoom-target)>.012)setZoom(target);
 }
 function scheduleFit(){
  if(resizeScheduled)return;
  resizeScheduled=true;
  requestAnimationFrame(()=>{resizeScheduled=false;fitCanvas()});
 }
 function syncMode(){
  const next=compact();
  if(next&&!compactWasActive){
   if(!userModeChosen)mode=innerHeight<=440?'canvas':'devices';
   wideZoom=typeof zoom==='number'?zoom:1;
   manualZoom=false;
  }else if(!next&&compactWasActive&&!manualZoom&&typeof setZoom==='function'){
   setZoom(wideZoom);
  }
  compactWasActive=next;
  if(!next)eventsOpen=false;
  syncButtons();scheduleFit();
 }
 media.addEventListener('change',syncMode);
 window.addEventListener('resize',()=>{
  if(compact()&&!userModeChosen){
   mode=innerHeight<=440?'canvas':'devices';
   syncButtons();
  }
  scheduleFit();
 },{passive:true});
 new ResizeObserver(scheduleFit).observe(work);
 // Agent and manual device additions also update the automatic compact fit.
 const nodeLayer=document.getElementById('nodes');
 new MutationObserver(scheduleFit).observe(nodeLayer,{childList:true});
 if(window.ptInitialReady)window.ptInitialReady.then(scheduleFit).catch(()=>{});
 syncMode();
 window.PacketTrackerCompact={isActive:compact,mode:()=>mode,
  eventsOpen:()=>eventsOpen,showCanvas:()=>setMode('canvas'),
  showDevices:()=>setMode('devices'),showEvents:toggleEvents,fit:scheduleFit};
})();
