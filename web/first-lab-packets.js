/* Replay the deterministic simulated ICMP/DNS/HTTP packet traces. */
(() => {
'use strict';
let cursor=0,playing=null,visible=new Set(['ICMP','DNS','HTTP','TCP','UDP','ARP']),filterOpen=false,simStartSeq=0;
const eventPane=document.querySelector('#simulationEvents');
const capture=document.querySelector('#captureCount');
const speed=document.querySelector('.sim-speed');
const hud=document.createElement('div');hud.id='ptPacketEnvelope';hud.hidden=true;
hud.setAttribute('role','status');hud.setAttribute('aria-label','Current simulated packet');
document.querySelector('#workspace').append(hud);
const detail=document.createElement('div');detail.id='ptPacketDetails';detail.hidden=true;
detail.innerHTML='<div class="pt-packet-dialog"><header><strong>Packet Information</strong><button id="ptPacketClose">×</button></header><div id="ptPacketContent"></div></div>';
document.body.append(detail);detail.querySelector('#ptPacketClose').onclick=()=>detail.hidden=true;
function events(){return (state.packet_events||[]).filter(e=>visible.has(e.protocol)&&(!simulationMode||e.seq>simStartSeq))}
function viewPacket(e){
 if(!e){hud.hidden=true;return}
 const dev=state.devices[e.destination];
 if(!dev){hud.hidden=true;return}
 hud.hidden=false;hud.style.left=(dev.x+70)+'px';hud.style.top=(dev.y+1)+'px';
 hud.textContent='✉ '+e.protocol;hud.title=e.source+' → '+e.destination+': '+e.detail;
 hud.classList.toggle('failed',!e.ok);
}
function details(e){
 if(!e)return;
 detail.hidden=false;
 const body=detail.querySelector('#ptPacketContent');body.textContent='';
 const h=document.createElement('h3');h.textContent=e.protocol+' packet #'+e.seq;body.append(h);
 const layers=[
  ['Layer 7 Application',e.protocol==='HTTP'||e.protocol==='DNS'?e.protocol+' — '+e.detail:'No modeled application payload'],
  ['Layer 4 Transport',e.protocol==='HTTP'||e.protocol==='TCP'?'TCP':e.protocol==='DNS'||e.protocol==='UDP'?'UDP':'ICMP control'],
  ['Layer 3 Network','IPv4 route was computed by the simulator'],
  ['Layer 2 Data Link','Ethernet forwarding / ARP learning (simplified)'],
  ['Event',e.source+' → '+e.destination+' | '+e.detail]
 ];
 for(const [title,val] of layers){
   const section=document.createElement('div');section.className='pt-packet-layer';
   const strong=document.createElement('strong');strong.textContent=title;
   const p=document.createElement('p');p.textContent=val;section.append(strong,p);body.append(section);
 }
}
function renderPacketTimeline(){
 if(state.simulation)return; // Backend capture state is rendered by simulation-engine.js.
 if(!eventPane)return;
 const rows=events(),max=simulationMode?cursor:rows.length;
 cursor=Math.min(cursor,rows.length);
 eventPane.textContent='';
 if(!rows.length){const msg=document.createElement('div');msg.className='empty-small';msg.textContent='No packet events captured yet. Send a Simple PDU or browse a simulated server.';eventPane.append(msg)}
 for(let idx=0;idx<Math.min(max,rows.length);idx++){
   const e=rows[idx],el=document.createElement('button');el.className='sim-event-row pt-captured-row';
   if(idx===max-1)el.classList.add('current');
   for(const t of ['◉',Number(e.time||0).toFixed(3),e.source,e.destination,e.protocol]){
     const cell=document.createElement('span');cell.textContent=t;el.append(cell);
   }
   el.title=e.detail;el.onclick=()=>details(e);eventPane.append(el);
 }
 capture.textContent=simulationMode?String(Math.min(cursor,rows.length)):String(rows.length);
 if(simulationMode)viewPacket(rows[max-1]);else hud.hidden=true;
}
const oldRender=renderEvents;
renderEvents=function(){oldRender();renderPacketTimeline()};
function next(){
 const rows=events();if(cursor>=rows.length){stop();status('End of recorded packet trace');return}
 cursor++;renderPacketTimeline();const e=rows[cursor-1];
 clockRunning=false;clockOffset=Math.round((e.time||0)*1000);document.querySelector('#clock').textContent=formatClock(clockOffset);
 status('Packet '+e.seq+': '+e.protocol+' '+e.source+' → '+e.destination);
 document.dispatchEvent(new CustomEvent('packettracker:packet-step',{detail:e}));
}
function previous(){
 cursor=Math.max(0,cursor-1);renderPacketTimeline();const e=events()[cursor-1];
 clockRunning=false;clockOffset=Math.round((e?.time||0)*1000);
}
function stop(){if(playing!==null){clearInterval(playing);playing=null}}
const forward=document.querySelector('#stepForwardBtn'),back=document.querySelector('#stepBackBtn'),play=document.querySelector('#playBtn');
const prevForward=forward.onclick,prevBack=back.onclick,prevPlay=play.onclick;
forward.onclick=()=>simulationMode?next():prevForward();
back.onclick=()=>simulationMode?previous():prevBack();
play.onclick=()=>{
 if(!simulationMode)return prevPlay();
 if(playing!==null){stop();status('Packet playback paused');return}
 const tick=()=>next();
 tick();
 playing=setInterval(tick,Math.max(100,1200-(Number(speed.value)||55)*10));
};
const prevReset=document.querySelector('#resetSimulationBtn').onclick;
document.querySelector('#resetSimulationBtn').onclick=()=>{stop();cursor=0;hud.hidden=true;prevReset();renderPacketTimeline()};
const oldRealtime=document.querySelector('#realtimeBtn').onclick;
document.querySelector('#realtimeBtn').onclick=()=>{stop();oldRealtime();renderPacketTimeline()};
const oldSimulation=document.querySelector('#simulationBtn').onclick;
document.querySelector('#simulationBtn').onclick=()=>{stop();simStartSeq=(state.packet_events||[]).at(-1)?.seq||0;oldSimulation();cursor=0;clockRunning=false;clockOffset=0;renderPacketTimeline()};
speed.addEventListener('input',()=>{if(playing!==null){stop();play.onclick()}});
const filterRow=document.querySelector('.sim-filter-title'),filterArea=document.querySelector('.sim-filters');
filterRow.textContent='Event List Filters — Visible Events (ICMP, DNS, HTTP, TCP, UDP, ARP)';
function renderFilters(){
 filterArea.textContent='';
 for(const protocol of ['ICMP','DNS','HTTP','TCP','UDP','ARP']){
  const label=document.createElement('label'),checkbox=document.createElement('input');
  checkbox.type='checkbox';checkbox.checked=visible.has(protocol);
  checkbox.onchange=()=>{checkbox.checked?visible.add(protocol):visible.delete(protocol);cursor=0;renderPacketTimeline()};
  label.append(checkbox,document.createTextNode(protocol));filterArea.append(label);
 }
 filterArea.hidden=!filterOpen;
}
const buttons=document.querySelectorAll('.sim-filter-actions button');
if(buttons[0])buttons[0].onclick=()=>{filterOpen=!filterOpen;renderFilters()};
if(buttons[1])buttons[1].onclick=()=>{
 if(visible.size===0)for(const p of ['ICMP','DNS','HTTP','TCP','UDP','ARP'])visible.add(p);
 else visible.clear();
 cursor=0;renderFilters();renderPacketTimeline();
};
renderFilters();renderPacketTimeline();
})();
