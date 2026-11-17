/* §§41–73. Device forms and desktop utilities call the authoritative engine. */
(() => {
'use strict';
const by=id=>document.getElementById(id),e=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
const dialog=e('dialog');dialog.id='ptDeviceEngine';dialog.setAttribute('aria-labelledby','ptDeviceEngineTitle');document.body.append(dialog);
let device=null,data=null,contract=null,focusReturn=null,remoteContext=null,fieldDefaults={};
const titles={global:'Global settings',interface:'Interface settings',add_port:'Add physical port',module:'Install / remove module',power:'Device power',save_startup:'Save running configuration to startup',erase_startup:'Erase startup configuration',merge_running:'Merge configuration text',startup_import:'Import startup configuration text',boot:'Reboot / attempt boot',boot_image:'Select boot image',file_write:'Create simulated file',file_delete:'Delete simulated file',local_user:'Local login user',rip:'RIP routing network',vlan_delete:'Delete VLAN',console:'Console terminal',service:'Enable / configure server service',service_user:'Server account and permissions',dns_record:'DNS resource record',dhcp_pool_delete:'Remove DHCP pool',http_page_delete:'Remove HTTP page',aaa_client:'AAA client shared secret',transfer:'FTP / TFTP client',mail_send:'Send email',mail_receive:'Receive email',aaa_authenticate:'Test AAA login',clock_sync:'Synchronize device clock',snmp:'MIB Browser',logging:'Syslog destination',emit_log:'Generate log entry',firewall_rule:'Firewall rule',remote_cli:'Telnet / SSH client',wireless:'Access point / home router',associate:'PC Wireless',cloud_map:'Cloud / patch connection',controller:'Controller administrator setup',discover:'Discover network devices',provision:'Provision managed device',license:'Simulated license manager',industrial:'Industrial tags and collector',plc_program:'PLC function block program',plc_run:'Scan PLC program',historian_import:'Import historian CSV',historian_collect:'Collect historian samples',observer_scan:'Cyber Observer discovery and assurance',telephony:'Register telephone',call:'Telephone call',iox:'IOx application lifecycle',wlc_wlan:'WLC WLAN configuration',wlc_group:'WLC access point group'};
const bools=new Set(['enabled','delete','delete_process','auto_mdix','admin_up','dhcp','nat','ipv6_routing','clear','edge','setup']);
const nums=new Set(['class_id','instance_id','asn','segment','version','clock_rate','tx_ring_limit','mtu','privilege','ttl','range_m','channel','sequence','seconds','dlci_a','dlci_b','vlan','external_port','internal_port']);
const jsons=new Set(['identity','data','settings','tags','blocks','permissions','aps','wlans','macs','interfaces','dlcis','bookmarks']);
function fieldLabel(name){return ({ip:'IPv4 address / prefix',gateway:'Default gateway',dns_server:'DNS server IPv4',lan_ip:'LAN IPv4 / prefix',wan_ip:'Internet IPv4 / prefix',dhcp:'LAN DHCP server',nat:'NAT overload',macs:'MAC addresses (JSON array)',clock_rate:'Serial DCE clock rate',range_m:'Coverage radius (meters)',server:'Server name or IPv4',text:'Configuration text',csv:'device, tag, value, UTC timestamp',settings:'Provisioning / console settings (JSON)',blocks:'Function blocks (JSON array)',permissions:'Permissions (JSON array)',aps:'AP device names (JSON array)',wlans:'WLAN names (JSON array)'})[name]||name.replaceAll('_',' ').replace(/^./,c=>c.toUpperCase())}
async function act(body){const r=await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(remoteContext?{device:remoteContext.source,action:'management_apply',token:remoteContext.token,settings:body}:{device,...body})});const result=await r.json();if(!result.ok)throw Error(result.output||result.error);state=result.state;render();return result}
async function refresh(){const r=await fetch('/api/device-config?device='+encodeURIComponent(device));data=await r.json();if(!data.ok)throw Error(data.error)}
function options(action,key){
 if(key==='interface'||key==='port'&&action!=='add_port')return Object.keys(data.interfaces);
 if(key==='slot')return data.modules.map(m=>m.slot);
 if(key==='module')return ['none',...new Set(data.modules.flatMap(m=>m.available))];
 if(key==='media')return contract.hardware.media;
 if(key==='service')return ['http','https','dns','ftp','tftp','smtp','pop3','ntp','syslog','radius','tacacs','snmp','ssh','telnet','vpn','pppoe','capwap','historian','controller','telephony','modbus','cip'];
 if(key==='security')return ['open','wep','wpa-psk','wpa2-psk','wpa-enterprise','wpa2-enterprise'];
 if(key==='duplex')return ['auto','half','full'];if(key==='speed')return ['auto','10','100','1000','10000'];
 if(key==='type'&&action==='dns_record')return ['A','CNAME','NS','SOA'];
 if(key==='match')return ['source','destination','protocol','url'];
 if(key==='protocol')return action==='port_forward'?['tcp','udp','both']:action==='management_login'?['http','https']:action==='transfer'?['tftp','ftp']:action==='aaa_client'||action==='aaa_authenticate'?['radius','tacacs']:action==='clock_sync'?['ntp','ptp']:action==='host_firewall'?['ip','icmp','tcp','udp','ipv6','icmpv6']:['ssh','telnet'];
 if(key==='operation')return ({cip_request:['identity','get','set'],transfer:['list','get','put','delete','rename'],license:['status','issue','register'],iox:['list','install','activate','start','stop','deactivate','uninstall'],snmp:['get','set'],call:['dial','answer','hangup','note'],vpn:['connect','disconnect'],pppoe:['connect','disconnect'],dialup:['dial','disconnect']})[action];
 if(key==='note')return ['C','D','E'];return null;
}
function clean(value){if(Array.isArray(value))return value.map(clean);if(value&&typeof value==='object')return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,/password|secret|^key$|community/.test(k)?'[set]':clean(v)]));return value}
function build(action){
 const form=by('ptEngineForm');form.replaceChildren();
 const keys=contract.actions[action]||contract.services.actions[action]||contract.hardware.actions[action]||[];
 const addKeys=action==='wireless'?['lan_ip','wan_ip','gateway','dns_server','dhcp','nat','mac_mode','macs']:action==='associate'?['interface','ip','gateway','dhcp']:[];
 for(const key of [...new Set([...keys,...addKeys])]){
  if(key==='device'||key==='command'&&action==='console')continue;
  const row=e('label',fieldLabel(key)),list=options(action,key),input=e(list?'select':['text','content','csv','command'].includes(key)||jsons.has(key)?'textarea':'input');input.name=key;
  if(list){for(const value of list){const item=e('option',value);item.value=value;input.append(item)}}
  else if(input.tagName==='INPUT')input.type=bools.has(key)?'checkbox':nums.has(key)?'number':/password|secret|^key$/.test(key)?'password':'text';
  if(input.type==='number')input.step='any';
  if(bools.has(key))input.checked=['enabled','admin_up','dhcp','nat'].includes(key);
  if(jsons.has(key))input.value=['identity','data','tags','settings','bookmarks'].includes(key)?'{}':'[]';
  if(key==='hostname'||key==='display_name')input.value=data.settings[key]||device;
  if(key==='ttl')input.value='300';if(key==='channel')input.value='6';if(key==='seconds')input.value='.1';
  if(key==='permissions')input.value='["read","list"]';
  if(key in fieldDefaults){if(input.type==='checkbox')input.checked=fieldDefaults[key];else input.value=fieldDefaults[key]}
  row.append(input);form.append(row);
 }
 if(action==='console'){const row=e('label','IOS commands (one per line)'),input=e('textarea');input.name='command';row.append(input);form.append(row)}
 if(action==='interface'||action==='set_port'){
  const selector=form.querySelector('[name=interface],[name=port]');const fill=()=>{const current=data.interfaces[selector.value];for(const key of ['ip','speed','duplex','clock_rate','mac','mtu','tx_ring_limit','auto_mdix','admin_up']){const input=form.querySelector('[name='+key+']');if(input){input.disabled=key==='clock_rate'&&current.media!=='serial'||key==='auto_mdix'&&current.media!=='copper';if(input.type==='checkbox')input.checked=!!current[key];else input.value=current[key]??''}}};selector.onchange=fill;fill();
  const clear=e('button','Clear IPv4 address');clear.type='button';clear.onclick=async()=>{try{await act({action:'interface',interface:selector.value,ip:''});await refresh();build(action);inventory()}catch(error){by('ptEngineOutput').textContent=error.message}};form.append(clear);
 }
 if(['merge_running','startup_import','file_write','historian_import'].includes(action)){
  const row=e('label','Browse text file'),file=e('input');file.type='file';file.onchange=async()=>{const f=file.files[0];if(f&&f.size<=1000000){const input=form.querySelector('textarea[name=text],textarea[name=content],textarea[name=csv]');if(input)input.value=await f.text()}};row.append(file);form.append(row);
 }
 const apply=e('button','Apply');apply.type='submit';form.append(apply);
 form.onsubmit=async event=>{
  event.preventDefault();apply.disabled=true;const body={action};
  try{
   for(const input of form.querySelectorAll('[name]')){
    const key=input.name,value=input.value;if(input.disabled)continue;
    if(input.type==='checkbox')body[key]=input.checked;
    else if(nums.has(key)&&value!=='')body[key]=Number(value);
    else if(jsons.has(key))body[key]=JSON.parse(value||(['identity','data','tags','settings','bookmarks'].includes(key)?'{}':'[]'));
    else if(value!=='')body[key]=value;
   }
   if(body.module==='none')body.module=null;
   if(action==='dns_record'&&body.type==='SOA')body.value=JSON.parse(body.value);
   if(action==='snmp'&&body.operation==='set'&&body.oid?.startsWith('ifAdminStatus'))body.value=Number(body.value);
   const result=await act(body);by('ptEngineOutput').textContent=result.output;await refresh();inventory();
  }catch(error){by('ptEngineOutput').textContent=error.message}
  finally{apply.disabled=false}
 };
}
function inventory(){
 by('ptEngineInventory').textContent=JSON.stringify(clean({profile:data.profile,settings:data.settings,interfaces:data.interfaces,modules:data.modules,routes:data.routes}),null,2);
}
async function open(name=selected,preferred='global',initial={}){
 if(!name||!state.devices[name])return;
 device=name;remoteContext=initial.remote||null;fieldDefaults=initial.defaults||{};focusReturn=document.activeElement;
 try{
  if(!contract)contract=await (await fetch('/api/device-config/schema')).json();await refresh();
  dialog.replaceChildren();const title=e('h2','Device Configuration — '+name+' ('+data.profile+')');title.id='ptDeviceEngineTitle';dialog.append(title);
  const operation=e('select');operation.id='ptEngineOperation';operation.setAttribute('aria-label','Configuration operation');
  const all={...contract.actions,...contract.hardware.actions,...contract.services.actions};
  for(const action of Object.keys(all)){const item=e('option',titles[action]||action);item.value=action;operation.append(item)}
  operation.value=preferred in all?preferred:'global';operation.onchange=()=>build(operation.value);dialog.append(operation);
  const form=e('form');form.id='ptEngineForm';dialog.append(form);
  const output=e('pre');output.id='ptEngineOutput';output.setAttribute('role','status');output.setAttribute('aria-live','polite');dialog.append(output);
  const details=e('details');details.append(e('summary','Current configuration and results'));const inventory=e('pre');inventory.id='ptEngineInventory';details.append(inventory);dialog.append(details);
  for(const [text,fn] of [['Export running IOS text',()=>download(data.running_text,name+'-running.txt')],['Export complete running configuration',()=>download(JSON.stringify(data.running,null,2),name+'-running.json')],['Export startup configuration',()=>download(JSON.stringify(data.startup,null,2),name+'-startup.json')],['Close',()=>dialog.close()]]){const button=e('button',text);button.onclick=fn;dialog.append(button)}
  build(operation.value);window.PacketTrackerDeviceConfig.inventory();if(!dialog.open)dialog.showModal();operation.focus();
 }catch(error){status(error.message)}
}
function download(content,name){const a=e('a');a.href=URL.createObjectURL(new Blob([content],{type:'text/plain'}));a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),500)}
dialog.addEventListener('close',()=>{const target=focusReturn?.isConnected?focusReturn:by('dialogClose');target?.focus()});
const oldDialog=renderDialog;renderDialog=function(){oldDialog();if(!by('ptOpenDeviceEngine')){const b=e('button','Device Configuration');b.id='ptOpenDeviceEngine';b.onclick=()=>open(selected);by('dialogTabs').append(b)}};
runPcPrompt=async function(text){try{const r=await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({device:selected,action:'host_command',command:text})});const result=await r.json();if(result.state)state=result.state;pcPromptHistory+='C:\\> '+text+'\n'+result.output+'\n';render();}catch(error){status(error.message)}};
const priorServices=renderServices;renderServices=function(d,body){
 priorServices(d,body);
 const name=ptServiceView.toLowerCase(),protocol=name==='email'?'smtp':name==='aaa'?'radius':name;
 const supported=new Set(['ftp','tftp','smtp','pop3','radius','tacacs','ntp','syslog','snmp','https','controller','historian','observer','pppoe','vpn','ptp','cip']);
 const pane=body.querySelector('.pt-services-body');if(!pane)return;
 if(supported.has(protocol)){
  pane.replaceChildren(e('h3',ptServiceView));
  const launch=e('button','Configure '+ptServiceView);launch.onclick=()=>open(d.name,'service',{defaults:{service:protocol}});pane.append(launch);
  const actions=['service_user','file_write','file_delete'];
  for(const action of actions){const b=e('button',titles[action]);b.onclick=()=>open(d.name,action,{defaults:{service:protocol}});pane.append(b)}
  const records=e('pre',JSON.stringify(clean(d.config?.services?.[protocol]||{enabled:false}),null,2));pane.append(records);
 }
 const advanced=e('button','More service settings');advanced.onclick=()=>open(d.name,name==='dns'?'dns_record':name==='dhcp'?'dhcp_pool':name==='http'?'http_page':'service',{defaults:{service:protocol}});pane.append(advanced);
};
const priorConfig=renderConfig;renderConfig=function(d,body){priorConfig(d,body);const rip=body.querySelector('[data-pt-nav=rip]');if(rip){rip.disabled=false;rip.title='Configure RIP';rip.onclick=()=>open(d.name,'rip')}};
const oldDesktop=renderDesktopTool;renderDesktopTool=function(d,body){
 const actions={terminal:'console',vpn:'vpn',pppoe:'pppoe',dialup:'dialup',firewall:'host_firewall',ipv6fw:'host_firewall',wireless:'associate',email:'mail_send',mib:'snmp',ssh:'remote_cli',editor:'file_write',tftp:'service',iox:'iox',supervisory:'historian_query',iotmonitor:'industrial',iotid:'file_write',apps:'iox',phone:'call'};
 if(desktopTool==='traffic'){body.replaceChildren();const b=e('button','Create Complex PDU');b.onclick=()=>window.PacketTrackerSimulation.editPdu(d.name,null,null,true);body.append(b);return}
 if(actions[desktopTool]){body.replaceChildren();const back=e('button','← Desktop');back.onclick=()=>{desktopTool=null;renderDialog()};const launch=e('button',titles[actions[desktopTool]]||fieldLabel(actions[desktopTool]));const tool=desktopTool;launch.onclick=()=>open(d.name,actions[tool],tool==='ipv6fw'?{defaults:{version:6}}:{});body.append(back,launch);return}
 const result=oldDesktop(d,body);if(desktopTool==='ip'){const more=e('button','IPv6 / interface settings');more.onclick=()=>open(d.name,'interface');body.append(more)}return result;
};
// Reflect all supported cable media in the accessible list and main palette.
const cables=Object.keys({auto:1,'copper-straight':1,'copper-cross':1,'fiber-mm':1,'fiber-sm':1,'serial-dce':1,'serial-dte':1,console:1,phone:1,coax:1,octal:1,usb:1,ioe:1});
const cableSelect=by('wlCable');if(cableSelect)for(const type of cables){if(![...cableSelect.options].some(o=>o.value===type)){const o=e('option',type);o.value=type;cableSelect.append(o)}}
const priorDrawLink=drawLink;drawLink=function(link){priorDrawLink(link);const a=center(link.a_device),b=center(link.b_device);if(!a||!b)return;const ns='http://www.w3.org/2000/svg';for(const [index,light] of (link.lights||[]).entries()){const t=index?.88:.12,x=a.x+(b.x-a.x)*t,y=a.y+(b.y-a.y)*t;const n=document.createElementNS(ns,light.color==='green'||light.color==='red'?'polygon':'circle');if(n.tagName==='polygon')n.setAttribute('points',`${x-5},${y+4} ${x+5},${y+4} ${x},${y-5}`);else{n.setAttribute('cx',x);n.setAttribute('cy',y);n.setAttribute('r',4)}n.setAttribute('fill',({green:'#1cbd50',red:'#dc3b3b',amber:'#e4a521',black:'#111'})[light.color]);n.setAttribute('stroke','#fff');const title=document.createElementNS(ns,'title');title.textContent=light.device+':'+light.interface+' '+light.color+(light.dce?' (DCE clock source)':'');n.append(title);document.querySelector('#wires').append(n)}};
window.PacketTrackerDeviceConfig={open,act,refresh,inventory};
})();
