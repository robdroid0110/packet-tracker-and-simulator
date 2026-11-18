/* Local .pka activity mode. Instruction text is inert; no teacher HTML executes. */
(() => {
 'use strict';
 const button=document.getElementById('activityBtn');
 const exportButton=document.getElementById('savePktBtn');
 const frame=document.createElement('dialog');
 frame.id='ptActivity';
 frame.setAttribute('aria-label','Learning activity');
 frame.innerHTML=[
  '<div class="pt-activity-header"><div><strong id="ptActivityTitle">Learning activity</strong>',
  '<small id="ptActivityVersion"></small></div>',
  '<button id="ptActivityClose" aria-label="Close learning activity">×</button></div>',
  '<div class="pt-activity-counts"><span id="ptActivityPageCount"></span>',
  '<span id="ptActivityReviewed"></span><span id="ptActivityCheckCount"></span></div>',
  '<div class="pt-activity-body"><nav id="ptActivityPages" aria-label="Instruction pages"></nav>',
  '<section class="pt-activity-reading"><h3 id="ptActivityHeading"></h3>',
  '<pre id="ptActivityText"></pre>',
  '<label class="pt-activity-reviewed"><input id="ptActivityReview" type="checkbox" />',
  ' Mark this section reviewed</label><div class="pt-activity-actions">',
  '<button id="ptActivityPrevious">Previous</button>',
  '<button id="ptActivityNext">Next</button>',
  '<button id="ptActivityCheck">Check supported fields</button></div>',
  '<p id="ptActivityCaution">Independent supported-field checks only.',
  ' This is not the official activity assessment or grading system.',
  ' Save native JSON to retain study progress.</p></section></div>'
 ].join('');
 document.body.append(frame);
 const get=id=>frame.querySelector('#'+id);
 let index=0,report=null,busy=false;
 const endpoint=async(path,body)=>{
  const response=await fetch(path,body?{
   method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)
  }:undefined);
  const result=await response.json();
  if(!response.ok||result.ok===false)throw Error(result.error||'Learning activity operation failed');
  return result;
 };
 function refresh(){
  const active=!!state?.activity;
  button.hidden=!active;button.disabled=!active;
  exportButton.title=active?'Export network only; activity study progress requires native JSON':'Export network-only PKT';
  return active;
 }
 function statusText(){
  if(!report)return;
  get('ptActivityTitle').textContent=report.title;
  get('ptActivityVersion').textContent=report.source_version?'Format '+report.source_version:'';
  get('ptActivityPageCount').textContent=report.total_pages+' instruction section(s)';
  get('ptActivityReviewed').textContent=report.reviewed_pages+' reviewed';
  get('ptActivityCheckCount').textContent=report.supported_passed+'/'+report.supported_checks+' supported checks matched';
 }
 function render(){
  if(!report)return;
  index=Math.max(0,Math.min(index,report.pages.length-1));
  statusText();
  const nav=get('ptActivityPages');nav.replaceChildren();
  report.pages.forEach((page,i)=>{
   const item=document.createElement('button');item.type='button';
   item.textContent=(report.completed_pages.includes(i)?'✓ ':'')+(i+1)+'. '+page.title;
   item.classList.toggle('active',i===index);
   item.setAttribute('aria-current',i===index?'step':'false');
   item.onclick=()=>{index=i;render()};
   nav.append(item);
  });
  const page=report.pages[index];
  get('ptActivityHeading').textContent=page?.title||'No instruction pages';
  get('ptActivityText').textContent=page?.text||'This activity has no readable instruction pages.';
  get('ptActivityText').scrollTop=0;
  get('ptActivityReview').disabled=!page||busy;
  get('ptActivityReview').checked=report.completed_pages.includes(index);
  get('ptActivityPrevious').disabled=index===0;
  get('ptActivityNext').disabled=index>=report.pages.length-1;
 }
 async function load(){
  const result=await endpoint('/api/activity');
  report=result.activity;
  if(!report)throw Error('No learning activity loaded');
  render();
 }
 async function open(){
  if(!refresh())return;
  await load();
  if(!frame.open)frame.showModal();
 }
 button.onclick=()=>open().catch(err=>alert(err.message));
 get('ptActivityClose').onclick=()=>frame.close();
 get('ptActivityPrevious').onclick=()=>{index--;render()};
 get('ptActivityNext').onclick=()=>{index++;render()};
 get('ptActivityReview').onchange=async()=>{
  if(busy)return;busy=true;
  try{
   const result=await endpoint('/api/activity/action',
    {action:'mark_page',page:index,reviewed:get('ptActivityReview').checked});
   report=result.activity;
   render();
  }catch(err){alert(err.message);render()}finally{busy=false}
 };
 get('ptActivityCheck').onclick=async()=>{
  try{
   const result=await endpoint('/api/activity/action',{action:'check_work'});
   report=result.activity;render();
  }catch(err){alert(err.message)}
 };
 exportButton.onclick=async()=>{
  try{
   const message=state?.activity
    ?'Exports network only. Your instructions and study progress will NOT be included in .pkt. Save native JSON to preserve them. Exported .pkt compatibility with official Cisco Packet Tracer is NOT verified. Continue?'
    :'Export the network as an experimental legacy .pkt file? Official Cisco Packet Tracer compatibility is NOT verified; it may refuse to open this file. Keep a native JSON copy.';
   if(!confirm(message))return;
   const result=await endpoint('/api/lab/export',{format:'pkt'});
   const decoded=atob(result.data);
   const bytes=new Uint8Array(decoded.length);
   for(let i=0;i<decoded.length;i++)bytes[i]=decoded.charCodeAt(i);
   const blob=new Blob([bytes],{type:'application/octet-stream'});
   const url=URL.createObjectURL(blob);
   const anchor=document.createElement('a');
   anchor.href=url;anchor.download='packet-tracker-export.pkt';
   document.body.append(anchor);anchor.click();anchor.remove();
   setTimeout(()=>URL.revokeObjectURL(url),60000);
   status('Experimental network-only PKT exported; retain native JSON.');
   if(result.warnings?.length)alert(result.warnings.slice(0,8).join('\n'));
  }catch(error){alert('PKT export failed: '+error.message)}
 };
 if(window.ptInitialReady)window.ptInitialReady.then(refresh).catch(()=>{});
 setInterval(refresh,1500);
 window.PacketTrackerActivity={open,refresh,progress:()=>report,close:()=>frame.close()};
})();
