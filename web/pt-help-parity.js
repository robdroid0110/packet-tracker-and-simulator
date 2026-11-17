/* legacy network simulator 9 help-informed device UI. All mutations call Packet Tracker and Simulator commands. */
let ptConfigView='global',ptServiceView='DHCP',ptRecentCommands=[];
const ptOldOpen=openDevice,ptOldConfig=renderConfig,ptOldCommand=command;
openDevice=function(name){ptConfigView='global';ptServiceView='DHCP';ptRecentCommands=[];ptOldOpen(name)};
const ptDocPage={pc:'config_PCs.htm',server:'config_servers.htm',router:'config_routers.htm',switch:'config_switches.htm',generic:'devicesAndModules.htm'};
function ptOpenHelp(file){window.open('/help/index.html?topic='+encodeURIComponent(file),'_blank','noopener')}
function ptNavItem(title,key,disabled){return '<button type="button" data-pt-nav="'+esc(key)+'" class="pt-config-nav-item '+(ptConfigView===key?'active':'')+'" '+(disabled?'disabled title="Not yet implemented"':'')+'>'+esc(title)+'</button>'}
function ptTree(d){
 let html='<div class="pt-nav-group"><strong>GLOBAL</strong>'+ptNavItem('Settings','global',false)+ptNavItem('Algorithm Settings','algorithm',true)+'</div>';
 if(d.kind==='router'||d.kind==='switch')html+='<div class="pt-nav-group"><strong>ROUTING</strong>'+ptNavItem('Static','static',d.kind==='switch')+ptNavItem('RIP','rip',true)+ptNavItem('OSPF','ospf',d.kind!=='router')+'</div>';
 if(d.kind==='switch')html+='<div class="pt-nav-group"><strong>SWITCHING</strong>'+ptNavItem('VLAN Database','vlan',false)+ptNavItem('Spanning Tree','stp',false)+'</div>';
 html+='<div class="pt-nav-group"><strong>INTERFACE</strong>';
 for(const name of Object.keys(d.interfaces||{}))if(!d.interfaces[name].parent)html+=ptNavItem(name,'interface:'+name,false);
 html+='</div>';
 if(d.kind==='router')html+='<div class="pt-nav-group"><strong>ADVANCED</strong>'+ptNavItem('ACL / NAT','advanced',false)+'</div>';
 return html;
}
function ptConsole(d){return d.kind==='router'||d.kind==='switch'?'<section class="pt-command-log"><div>Equivalent IOS Commands <small>(recent actions)</small></div><pre id="ptCommandOutput">'+esc(ptRecentCommands.join('\n')||'Select a setting or interface to configure the device.')+'</pre></section>':''}
function ptWireNav(body){
 body.querySelectorAll('[data-pt-nav]').forEach(b=>b.onclick=()=>{ptConfigView=b.dataset.ptNav;if(ptConfigView.startsWith('interface:'))dialogIface=ptConfigView.slice(10);renderDialog()});
}
function ptFrame(d,body,content,legacy){
 if(legacy){
  const layout=body.querySelector('.device-layout');if(!layout)return;
  const side=layout.querySelector('.device-sidebar');side.classList.add('pt-tree');side.innerHTML=ptTree(d);
  const main=layout.querySelector('.device-main');main.classList.add('pt-main-panel');
  const sections=Array.from(main.querySelectorAll(':scope > .config-section'));
  sections.forEach((section,i)=>{section.style.display=ptConfigView==='advanced'?(d.kind==='router'&&i===0?'none':''):ptConfigView==='stp'?(i===1?'':'none'):(i===0?'':'none')});
  const frame=document.createElement('div');frame.className='pt-config-frame';layout.replaceWith(frame);layout.classList.add('pt-doc-layout');frame.appendChild(layout);frame.insertAdjacentHTML('beforeend',ptConsole(d));
 }else{
  body.innerHTML='<div class="pt-config-frame"><div class="device-layout pt-doc-layout"><aside class="device-sidebar pt-tree">'+ptTree(d)+'</aside><main class="device-main pt-main-panel">'+content+'</main></div>'+ptConsole(d)+'</div>';
 }
 ptWireNav(body);
}
function ptForm(label,id,value,placeholder,disabled){return '<div class="pt-form-row"><label for="'+esc(id)+'">'+esc(label)+'</label><input id="'+esc(id)+'" value="'+esc(value||'')+'" placeholder="'+esc(placeholder||'')+'" '+(disabled?'disabled':'')+'></div>'}
renderConfig=function(d,body){
 if(d.kind==='generic'){ptOldConfig(d,body);return}
 if(ptConfigView.startsWith('interface:')||ptConfigView==='advanced'||ptConfigView==='stp'){
  if(ptConfigView.startsWith('interface:'))dialogIface=ptConfigView.slice(10);
  ptOldConfig(d,body);ptFrame(d,body,'',true);return;
 }
 let main='';
 if(ptConfigView==='global'){
  const host=d.kind==='pc'||d.kind==='server';
  main='<div class="pt-doc-section"><h3>Global Settings</h3>'+ptForm('Display Name','ptDisplayName',d.name,'',false);
  if(!host)main+=ptForm('Hostname','ptHostname',d.config?.hostname||d.name,'',false)+'<fieldset class="pt-fieldset"><legend>NVRAM / Configuration</legend><p class="pt-doc-note">Save running configuration before rebooting to restore it on startup.</p><button type="button" id="ptStartupErase">Erase</button> <button type="button" id="ptStartupSave">Save</button> <button type="button" id="ptStartupLoad">Load</button> <button type="button" id="ptStartupExport">Export</button></fieldset>';
  else main+='<fieldset class="pt-fieldset"><legend>Gateway / DNS IPv4</legend>'+ptForm('Default Gateway','ptGlobalGateway',d.default_gateway||'','192.168.1.1',false)+ptForm('DNS Server','ptGlobalDns',d.dns_server||'','192.168.0.105',false)+'</fieldset>';
  main+='<div class="pt-actions"><button id="ptGlobalApply">Apply Settings</button></div></div>';
  ptFrame(d,body,main,false);
  $('#ptGlobalApply').onclick=async()=>{
   const name=$('#ptDisplayName').value.trim(),hostname=$('#ptHostname')?.value.trim(),gateway=$('#ptGlobalGateway')?.value.trim(),dns=$('#ptGlobalDns')?.value.trim();
   if(!name)return status('Device name required');
   if(name!==selected){const r=await command('rename '+selected+' '+name,false);if(!r.ok)return status(r.output);selected=name;$('#deviceDialog').classList.remove('hidden')}
   if(hostname&&hostname!==(state.devices[selected].config?.hostname||selected)){const response=await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({device:selected,action:'global',hostname})});const result=await response.json();if(!result.ok)return status(result.output||result.error);state=result.state}
   if(gateway){const r=await command('gateway '+selected+' '+gateway,false);if(!r.ok)return status(r.output)}
   if(dns!==undefined){const r=await command('dns-client '+selected+' '+(dns||'none'),false);if(!r.ok)return status(r.output)}
   status('Global settings applied');renderDialog();
  };
  if(!host){
   for(const [id,action] of [['ptStartupSave','save_startup'],['ptStartupErase','erase_startup']])$('#'+id).onclick=async()=>{const r=await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({device:selected,action})});const data=await r.json();if(data.state)state=data.state;status(data.ok?'Configuration '+(action==='save_startup'?'saved':'erased'):data.output||data.error);render()};
   $('#ptStartupLoad').onclick=()=>window.PacketTrackerDeviceConfig.open(selected,'startup_import');$('#ptStartupExport').onclick=()=>window.PacketTrackerDeviceConfig.open(selected,'global');
  }
  return;
 }
 if(ptConfigView==='static'){
  const rows=(d.routes||[]).filter(r=>r.source==='static').map(r=>'<tr><td>'+esc(r.network)+'</td><td>'+esc(r.next_hop||r.interface||'')+'</td></tr>').join('');
  main='<div class="pt-doc-section"><h3>Static Routes</h3>'+ptForm('Network / Prefix','ptStaticNet','','192.168.10.0/24',false)+ptForm('Next Hop','ptStaticHop','','10.0.0.2',false)+'<div class="pt-actions"><button id="ptStaticAdd">Add</button></div><h4>Network Address</h4><table class="compact-table"><thead><tr><th>Network</th><th>Next Hop</th></tr></thead><tbody>'+(rows||'<tr><td colspan="2">No static routes</td></tr>')+'</tbody></table></div>';
  ptFrame(d,body,main,false);
  $('#ptStaticAdd').onclick=async()=>{const a=$('#ptStaticNet').value.trim(),b=$('#ptStaticHop').value.trim();if(!a||!b)return status('Network and next hop required');const r=await command('route '+selected+' '+a+' via '+b,false);status(r.output);renderDialog()};
  return;
 }
 if(ptConfigView==='vlan'){
  const rows=Array.from(d.vlans||[1]).sort((a,b)=>a-b).map(v=>'<tr><td>'+v+'</td><td>active</td></tr>').join('');
  main='<div class="pt-doc-section"><h3>VLAN Database</h3>'+ptForm('VLAN Number','ptVlanInput','','10',false)+'<div class="pt-actions"><button id="ptVlanAdd">Add</button></div><h4>Configured VLANs</h4><table class="compact-table"><thead><tr><th>VLAN</th><th>Status</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
  ptFrame(d,body,main,false);$('#ptVlanAdd').onclick=async()=>{const v=$('#ptVlanInput').value.trim();if(!v)return;const r=await command('vlan '+selected+' '+v,false);status(r.output);renderDialog()};
  return;
 }
 if(ptConfigView==='ospf'){
  const rows=(d.ospf_networks||[]).map(n=>'<tr><td>'+esc(n)+'</td><td>'+esc(d.ospf_areas?.[n]??0)+'</td><td><button type="button" data-ospf-remove="'+esc(n)+'" aria-label="Remove OSPF network '+esc(n)+'">Remove</button></td></tr>').join('');
  main='<div class="pt-doc-section"><h3>OSPF</h3><p>Process '+esc(d.ospf_process_id||1)+': <strong>'+(d.ospf_enabled?'Enabled':'Disabled')+'</strong> — '+(d.ospf_auto?'all other interfaces in area 0':'explicit networks only')+'</p>'+ptForm('Network / Prefix','ptOspfNetwork','','10.0.0.0/24',false)+ptForm('Area ID','ptOspfArea','0','0',false)+'<div class="pt-actions"><button id="ptOspfEnable">Add / Enable</button> <button id="ptOspfAuto">Enable All in Area 0</button> <button id="ptOspfDisable">Disable</button></div><h4>Network Statements</h4><table class="compact-table"><thead><tr><th>Network</th><th>Area</th><th>Action</th></tr></thead><tbody>'+(rows||'<tr><td colspan="3">No explicit networks</td></tr>')+'</tbody></table><h4>Modeled Neighbors</h4><p id="ptOspfNeighbors">Loading…</p><p class="pt-doc-note">Area-aware, hop-based simulation. Hellos, cost and detailed neighbor election are not modeled.</p></div>';
  ptFrame(d,body,main,false);
  const apply=async text=>{const r=await command(text,false);status(r.output||r.error);renderDialog()};
  $('#ptOspfEnable').onclick=async()=>{const n=$('#ptOspfNetwork').value.trim(),area=$('#ptOspfArea').value.trim()||'0';if(!n&&area!=='0')return status('Enter a network when specifying an area');await apply('ospf '+selected+' enable'+(n?' '+n+' area '+area:''))};
  $('#ptOspfAuto').onclick=()=>apply('ospf '+selected+' auto');
  $('#ptOspfDisable').onclick=()=>apply('ospf '+selected+' disable');
  body.querySelectorAll('[data-ospf-remove]').forEach(button=>button.onclick=()=>apply('ospf '+selected+' remove '+button.dataset.ospfRemove));
  const deviceName=d.name,neighbors=body.querySelector('#ptOspfNeighbors');
  fetch('/api/ospf?device='+encodeURIComponent(deviceName)).then(r=>r.json()).then(data=>{if(!neighbors.isConnected)return;neighbors.textContent=data.ok?(data.neighbors.length?data.neighbors.map(n=>n.device+' — '+n.local_interface+' → '+n.ip+' (area '+n.area+')').join('; '):'No modeled neighbors'):data.error||'Could not load neighbors'}).catch(()=>{if(neighbors.isConnected)neighbors.textContent='Could not load neighbors'});
  return;
 }
 ptFrame(d,body,'<div class="pt-doc-section"><h3>'+esc(ptConfigView)+'</h3><p>Reserved for a future implementation.</p></div>',false);
};
const ptServiceList=['HTTP','DHCP','DHCPv6','TFTP','DNS','SYSLOG','AAA','NTP','EMAIL','FTP','IoT','VM Management','RADIUS EAP'];
renderServices=function(d,body){
 const navigation=ptServiceList.map(s=>'<button class="pt-service-button '+(s===ptServiceView?'active':'')+'" data-pt-service="'+esc(s)+'">'+esc(s)+'</button>').join('');
 let contents='';
 if(ptServiceView==='DHCP'){
  const rows=Object.values(d.dhcp_pools||{}).map(p=>'<tr><td>'+esc(p.name)+'</td><td>'+esc(p.network)+'</td><td>'+Object.keys(p.leases||{}).length+'</td></tr>').join('');
  contents='<div class="pt-doc-section"><h3>DHCP</h3><p>Service: <strong>On</strong></p>'+ptForm('Pool Name','ptPoolName','','LAN',false)+ptForm('Network / Prefix','ptPoolNetwork','','192.168.1.0/24',false)+ptForm('Default Gateway','ptPoolGateway','','192.168.1.1',false)+ptForm('Start IP Address','ptPoolStart','','192.168.1.100',false)+ptForm('End IP Address','ptPoolEnd','','192.168.1.199',false)+ptForm('DNS Server','ptPoolDns','','Optional',false)+'<div class="pt-actions"><button id="ptPoolAdd">Add Pool</button></div><h4>Configured Pools</h4><table class="compact-table"><thead><tr><th>Name</th><th>Network</th><th>Leases</th></tr></thead><tbody>'+(rows||'<tr><td colspan="3">No DHCP pools configured</td></tr>')+'</tbody></table></div>';
 }else contents='<div class="pt-doc-section"><h3>'+esc(ptServiceView)+'</h3><p class="pt-doc-note">The location matches legacy network simulator; the '+esc(ptServiceView)+' service backend is not yet implemented.</p><p>Service: <input type="radio" disabled> On <input type="radio" disabled> Off</p></div>';
 body.innerHTML='<div class="pt-services-doc"><aside class="pt-services-tree"><strong>SERVICES</strong>'+navigation+'</aside><main class="pt-services-body">'+contents+'</main></div>';
 body.querySelectorAll('[data-pt-service]').forEach(b=>b.onclick=()=>{ptServiceView=b.dataset.ptService;renderDialog()});
 if(ptServiceView==='DHCP')$('#ptPoolAdd').onclick=async()=>{const vals=['ptPoolName','ptPoolNetwork','ptPoolGateway','ptPoolStart','ptPoolEnd','ptPoolDns'].map(id=>$('#'+id).value.trim());if(vals.slice(0,5).some(v=>!v))return status('DHCP pool fields are required');const r=await command('dhcp-pool '+selected+' '+vals.filter(Boolean).join(' '),false);status(r.output);renderDialog()};
};
function ptEquivalent(cmd){
 const p=cmd.split(/\s+/);
 if(p[0]==='rename')return 'hostname '+p[2];
 if(p[0]==='route'){const [ip,prefix]=p[2].split('/');return 'ip route '+ip+' '+ptSubnetMask(prefix)+' '+p[4]}
 if(p[0]==='vlan')return 'vlan '+p[2];
 if(p[0]==='ospf'){
  const id=state.devices[p[1]]?.ospf_process_id||1;
  if(p[2]==='clear')return 'no router ospf '+id;
  if(p[2]==='disable')return 'Packet Tracker and Simulator: OSPF disabled (statements retained)';
  if(p[2]==='remove')return 'Packet Tracker and Simulator: removed OSPF network '+p[3];
  if(p[2]==='auto')return 'router ospf '+id+'\n network 0.0.0.0 255.255.255.255 area 0';
  if(p[3]){const [ip,prefix='32']=p[3].split('/'),mask=ptSubnetMask(prefix);if(!mask)return cmd;const wildcard=mask.split('.').map(n=>255-Number(n)).join('.');return 'router ospf '+id+'\n network '+ip+' '+wildcard+' area '+(p[5]||'0')}
  return 'router ospf '+id;
 }
 if(p[0]==='gateway')return 'ip default-gateway '+p[2];
 if(p[0]==='up'||p[0]==='down')return 'interface '+p[2]+'\n '+(p[0]==='up'?'no shutdown':'shutdown');
 if(p[0]==='ip'){const [ip,prefix]=p[3].split('/');return 'interface '+p[2]+'\n ip address '+ip+' '+ptSubnetMask(prefix)}
 if(p[0]==='switchport'){return 'interface '+p[2]+'\n switchport mode '+p[3]+(p[3]==='access'?'\n switchport access vlan '+p[4]:'\n switchport trunk allowed vlan '+p[4])}
 return cmd;
}
command=async function(cmd,echo=true){
 const result=await ptOldCommand(cmd,echo);
 if(result.ok&&!$('#deviceDialog').classList.contains('hidden')&&/^(rename|route|vlan|ospf|gateway|up|down|ip|switchport|native-vlan|portfast|stp|channel|acl|nat-)/.test(cmd)){
  ptRecentCommands.push(ptEquivalent(cmd));ptRecentCommands=ptRecentCommands.slice(-24);
  const pre=$('#ptCommandOutput');if(pre){pre.textContent=ptRecentCommands.join('\n');pre.scrollTop=pre.scrollHeight}
 }
 return result;
};
const ptHelpKinds={pc:'config_PCs.htm',server:'config_servers.htm',router:'config_routers.htm',switch:'config_switches.htm',generic:'devicesAndModules.htm'};
const ptDialogHelp=$('#dialogHelp');if(ptDialogHelp)ptDialogHelp.onclick=()=>ptOpenHelp(ptHelpKinds[state.devices[selected]?.kind]||'index.htm');
const ptGlobalHelp=$('#globalHelpBtn');if(ptGlobalHelp)ptGlobalHelp.onclick=()=>ptOpenHelp('index.htm');
document.querySelectorAll('#menuBar .menu-item').forEach(b=>{if(b.textContent.trim()==='Help')b.onclick=()=>ptOpenHelp('index.htm')});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'&&!$('#deviceDialog').classList.contains('hidden')){closeDevice();return}
 if(e.ctrlKey&&!e.altKey&&!e.shiftKey){
  const map={n:'newBtn',o:'openBtn',s:'saveBtn',i:'zoomIn',t:'zoomReset',u:'zoomOut'},id=map[e.key.toLowerCase()];
  if(id){e.preventDefault();$('#'+id)?.click();return}
 }
 const tag=(e.target?.tagName||'').toUpperCase();
 if(e.shiftKey&&!e.ctrlKey&&!e.altKey&&tag!=='INPUT'&&tag!=='TEXTAREA'){
  if(e.key.toLowerCase()==='r')$('#realtimeBtn').click();
  if(e.key.toLowerCase()==='s')$('#simulationBtn').click();
 }
 if(e.ctrlKey&&e.shiftKey&&e.key.toLowerCase()==='b'){e.preventDefault();document.body.classList.toggle('pt-hide-bottom')}
});

/* Physical device view: use the locally imported vendor illustrations. */
let ptPhysicalScale=1;
function ptPhysicalImage(d){
 const model=d.model||'';
 if(d.kind==='pc')return model.includes('laptop')?'iRealLaptop.png':'iRealWorkstation.png';
 if(d.kind==='server')return 'iRealServer.png';
 if(d.kind==='switch'){
  if(model.includes('3560'))return 'iRealSwitch3560.png';
  if(model.includes('2960'))return 'iRealSwitch2960_24TT.png';
  return 'iPTRealSwitch.png';
 }
 if(d.kind==='router'){
  const mapped={'isr4331':'iRealRouter4331.png','isr4321':'iRealRouter4321.png','1941':'iRealRouter1941Back.png','2901':'iRealRouter2901.png','2911':'iRealRouter2911.png','2811':'iRealRouter2811.png','1841':'iRealRouter1841.png'};
  return mapped[model]||'iPTRealRouter.png';
 }
 return 'GenericIoE.png';
}
renderPhysical=function(d,body){
 const routerNames=['PT-ROUTER-NM-1CE','PT-ROUTER-NM-1CFE','PT-ROUTER-NM-1CGE','PT-ROUTER-NM-1FFE','PT-ROUTER-NM-1FGE','PT-ROUTER-NM-1S','PT-ROUTER-NM-1SS','PT-ROUTER-NM-1W','PT-ROUTER-NM-COVER'];
 const switchNames=['PT-SWITCH-NM-1CE','PT-SWITCH-NM-1CFE','PT-SWITCH-NM-1CGE','PT-SWITCH-NM-1FFE','PT-SWITCH-NM-1FGE','PT-SWITCH-NM-COVER'];
 const pcNames=['PT-HOST-NM-1CE','PT-HOST-NM-1CFE','PT-HOST-NM-1CGE','PT-HOST-NM-1FFE','PT-HOST-NM-1FGE','PT-HOST-NM-1W','WMP300N'];
 const laptopNames=['WPC300N','PT-LAPTOP-NM-1AM','PT-LAPTOP-NM-1CE','PT-LAPTOP-NM-1CFE','PT-LAPTOP-NM-1CGE','PT-LAPTOP-NM-1FFE','PT-LAPTOP-NM-1FGE','PT-LAPTOP-NM-1W'];
 const modules=d.kind==='router'?routerNames:d.kind==='switch'?switchNames:(d.model||'').includes('laptop')?laptopNames:pcNames;
 body.innerHTML='<div class="pt-physical-view"><div class="pt-physical-header">Physical Device View</div><aside class="pt-module-tree"><strong>MODULES</strong>'+modules.map(m=>'<button class="pt-module-btn" data-pt-module="'+esc(m)+'" title="Show module description">'+esc(m)+'</button>').join('')+'</aside><div class="pt-physical-content"><div class="pt-physical-zoom"><button data-pt-zoom="in">Zoom In</button><button data-pt-zoom="reset">Original Size</button><button data-pt-zoom="out">Zoom Out</button></div><div class="pt-physical-stage"><img id="ptPhysicalPhoto" src="/assets/icons/physical-devices/'+encodeURIComponent(ptPhysicalImage(d))+'" alt="'+esc(d.name)+' device hardware" onload="this.nextElementSibling.style.display=\'none\'" onerror="this.style.display=\'none\'"><span class="pt-hardware-placeholder">'+esc(d.name)+'</span></div><div class="pt-physical-customize"><button disabled>Customize Icon in Physical View</button><button disabled>Customize Icon in Logical View</button></div><div class="pt-module-description" id="ptModuleDesc">Select a module to view its description. Select an available slot and module below.</div></div></div>';
 const image=$('#ptPhysicalPhoto');
 function applyZoom(){image.style.transform='scale('+ptPhysicalScale+')'}
 applyZoom();
 body.querySelectorAll('[data-pt-zoom]').forEach(b=>b.onclick=()=>{const type=b.dataset.ptZoom;ptPhysicalScale=type==='reset'?1:Math.max(.6,Math.min(2,ptPhysicalScale+(type==='in'?.2:-.2)));applyZoom()});
 body.querySelectorAll('[data-pt-module]').forEach(b=>b.onclick=()=>{body.querySelectorAll('[data-pt-module]').forEach(x=>x.classList.remove('active'));b.classList.add('active');$('#ptModuleDesc').textContent=b.dataset.ptModule+' — see available slots below. Power off before changing modules.'});
};
/* PC Desktop IP Configuration closely follows the documented IP Config utility. */
const ptOldDesktopTool=renderDesktopTool;
function ptSubnetMask(bits){
 const p=Number(bits);if(!Number.isInteger(p)||p<0||p>32)return '';if(p===0)return '0.0.0.0';
 const as=(0xffffffff << (32-p)) >>> 0;
 return [24,16,8,0].map(shift=>(as>>>shift)&255).join('.');
}
function ptMaskPrefix(mask){
 const pieces=mask.split('.');if(pieces.length!==4)return null;
 const nums=pieces.map(Number);if(nums.some(n=>!Number.isInteger(n)||n<0||n>255))return null;
 const bits=nums.map(n=>n.toString(2).padStart(8,'0')).join('');
 return /^1*0*$/.test(bits)?bits.indexOf('0')===-1?32:bits.indexOf('0'):null;
}
renderDesktopTool=function(d,body){
 if(desktopTool!=='ip')return ptOldDesktopTool(d,body);
 const iface=dialogIface&&d.interfaces[dialogIface]?dialogIface:Object.keys(d.interfaces)[0],intf=d.interfaces[iface],parts=(intf.ip||'').split('/'),ip=parts[0]||'',mask=parts[1]?ptSubnetMask(parts[1]):'';
 body.innerHTML='<section class="pt-ip-config"><div class="pt-ip-title">IP Configuration <button id="ptIpClose" title="Close">X</button></div><div class="pt-ip-choose"><label>Interface</label><select id="ptIpIface">'+Object.keys(d.interfaces).map(name=>'<option value="'+esc(name)+'" '+(name===iface?'selected':'')+'>'+esc(name)+'</option>').join('')+'</select></div><fieldset class="pt-ip-fieldset"><legend>IP Configuration</legend><div class="pt-ip-radios"><label><input name="ptIpMethod" type="radio" value="dhcp"> DHCP</label><label><input name="ptIpMethod" type="radio" value="static" checked> Static</label></div>'+ptForm('IPv4 Address','ptIpv4Address',ip,'192.168.1.10',false)+ptForm('Subnet Mask','ptIpv4Mask',mask,'255.255.255.0',false)+ptForm('Default Gateway','ptIpv4Gateway',d.default_gateway||'','192.168.1.1',false)+ptForm('DNS Server','ptIpv4Dns',d.dns_server||'','192.168.0.105',false)+'</fieldset><fieldset class="pt-ip-fieldset"><legend>IPv6 Configuration</legend><div class="pt-ip-radios"><label><input type="radio" disabled> Automatic</label><label><input type="radio" disabled> Static</label></div>'+ptForm('IPv6 Address','ptIpv6Address','','IPv6 not yet implemented',true)+ptForm('Link Local Address','ptIpv6Link','','',true)+ptForm('Default Gateway','ptIpv6Gateway','','',true)+ptForm('DNS Server','ptIpv6Dns','','',true)+'</fieldset><fieldset class="pt-ip-fieldset"><legend>802.1X</legend><p><label><input type="checkbox" disabled> Use 802.1X Security</label></p>'+ptForm('Authentication','pt802Auth','','Not implemented',true)+ptForm('Username','pt802Name','','',true)+ptForm('Password','pt802Pass','','',true)+'</fieldset><div class="pt-ip-actions"><button id="ptIpApply">Apply IPv4 Settings</button></div></section>';
 $('#ptIpClose').onclick=()=>{desktopTool=null;renderDialog()};
 $('#ptIpIface').onchange=()=>{dialogIface=$('#ptIpIface').value;renderDialog()};
 body.querySelectorAll('[name=ptIpMethod]').forEach(r=>r.onchange=()=>{const enabled=r.value==='static'?r.checked:!r.checked;for(const id of ['ptIpv4Address','ptIpv4Mask','ptIpv4Gateway'])$('#'+id).disabled=!enabled});
 $('#ptIpApply').onclick=async()=>{
  const current=$('#ptIpIface').value;
  if(body.querySelector('[name=ptIpMethod]:checked').value==='dhcp'){const r=await command('dhcp '+selected+' '+current,false);status(r.output);renderDialog();return}
  const address=$('#ptIpv4Address').value.trim(),mask=$('#ptIpv4Mask').value.trim(),gw=$('#ptIpv4Gateway').value.trim(),prefix=ptMaskPrefix(mask);
  if(!address||prefix===null)return status('Enter a valid IPv4 address and contiguous subnet mask');
  let r=await command('ip '+selected+' '+current+' '+address+'/'+prefix,false);if(!r.ok)return status(r.output);
  if(gw){r=await command('gateway '+selected+' '+gw,false);if(!r.ok)return status(r.output)}
  const dns=$('#ptIpv4Dns').value.trim();
  r=await command('dns-client '+selected+' '+(dns||'none'),false);
  if(!r.ok)return status(r.output);
  status(selected+' IPv4 configuration saved');renderDialog();
 };
};
