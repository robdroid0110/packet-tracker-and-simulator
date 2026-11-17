/* Each device gets its own view while sharing the local simulator. */
(() => {
 const deviceName=new URLSearchParams(location.search).get('device');
 const originalOpen=openDevice;
 if(deviceName){
  document.title=deviceName+' — Packet Tracker and Simulator';
  Promise.resolve(window.ptInitialReady).then(()=>{if(state.devices[deviceName])originalOpen(deviceName);else{document.querySelector('#deviceDialog').classList.remove('hidden');document.querySelector('#dialogName').textContent='Device unavailable';document.querySelector('#dialogBody').textContent='This device no longer exists in the current lab.'}});
  document.querySelector('#dialogClose').onclick=()=>window.close();
  return;
 }
 openDevice=function(name){
  const url=new URL(location.href);url.search='';url.searchParams.set('device',name);
  const popup=window.open(url.toString(),'packet-tracker-device-'+name,'popup=yes,width=1000,height=750,resizable=yes');
  if(popup)popup.focus();else{status('Allow pop-up windows to open multiple devices');originalOpen(name)}
 };
})();

/* View-only panning leaves saved device coordinates untouched. */
(() => {
 const work=document.getElementById('workspace');
 window.ptPan={x:0,y:0};let gesture=null;
 const horizontal=document.createElement('div'),vertical=document.createElement('div');
 for(const [bar,kind,label] of [[horizontal,'horizontal','Scroll workspace horizontally'],[vertical,'vertical','Scroll workspace vertically']]){bar.className='workspace-scrollbar '+kind;bar.setAttribute('role','region');bar.setAttribute('aria-label',label);bar.tabIndex=0;bar.append(document.createElement('div'));work.append(bar)}
 horizontal.scrollLeft=10000;vertical.scrollTop=10000;
 const draw=()=>{for(const element of [document.getElementById('nodes'),document.getElementById('wires'),document.getElementById('workspaceNotes'),document.getElementById('ptLogicalArt')])if(element){element.style.transformOrigin='0 0';element.style.transform=`translate(${ptPan.x}px,${ptPan.y}px) scale(${zoom})`}};
 horizontal.addEventListener('scroll',()=>{ptPan.x=10000-horizontal.scrollLeft;draw()});
 vertical.addEventListener('scroll',()=>{ptPan.y=10000-vertical.scrollTop;draw()});
 const old=renderTopology;renderTopology=function(){old();draw()};
 work.addEventListener('pointerdown',e=>{if(activeTool!=='pan'||e.button!==0||e.target.closest('.workspace-scrollbar'))return;e.preventDefault();e.stopImmediatePropagation();gesture={x:e.clientX,y:e.clientY,px:ptPan.x,py:ptPan.y};work.setPointerCapture(e.pointerId);work.style.cursor='grabbing'},true);
 work.addEventListener('pointermove',e=>{if(!gesture)return;e.preventDefault();ptPan.x=Math.max(-10000,Math.min(10000,gesture.px+e.clientX-gesture.x));ptPan.y=Math.max(-10000,Math.min(10000,gesture.py+e.clientY-gesture.y));horizontal.scrollLeft=10000-ptPan.x;vertical.scrollTop=10000-ptPan.y;draw()},true);
 work.addEventListener('pointerup',e=>{if(!gesture)return;e.preventDefault();e.stopImmediatePropagation();gesture=null;work.style.cursor='';dragged=true},true);
})();
