/* legacy network simulator Preferences: settings that have real Packet Tracker and Simulator behavior.
 * Unsupported vendor-specific activity/assessment features remain explicitly disabled.
 */
(function () {
'use strict';
const STORE = 'packetTracker.preferences.extra.v1';
const LOG = 'packetTracker.ios-log.v1';
const BASE = {
  theme:'classic', disableAutoCable:false, cliDefault:false, logIos:false,
  hidePhysical:false, hideConfig:false, hideCli:false, hideDesktop:false,
  hideServices:false, hideProgramming:false, hideAttributes:false,
  hideMultiuser:false, tooltipSize:12, tooltipFont:'Arial',
  cliFont:'Consolas', iosText:'#eaeaea', iosBg:'#050505',
  pcText:'#dddddd', pcBg:'#020202', backupMinutes:0
};
const doc = document;
const by = id => doc.getElementById(id);
function load(key) {try {const value=JSON.parse(localStorage.getItem(key));return value && typeof value==='object'?value:{};} catch {return {};}}
function clean(value) {
  const out={...BASE};
  for (const key of Object.keys(BASE)) {
    if (typeof BASE[key]==='boolean' && typeof value[key]==='boolean') out[key]=value[key];
    if (['theme','tooltipFont','cliFont'].includes(key) && typeof value[key]==='string' && value[key].length<40) out[key]=value[key];
    if (['iosText','iosBg','pcText','pcBg'].includes(key) && /^#[0-9a-fA-F]{6}$/.test(value[key]||'')) out[key]=value[key];
  }
  if (['classic','dark'].includes(value.theme)) out.theme=value.theme;
  else out.theme='classic';
  for (const key of ['tooltipFont','cliFont']) if (!['Arial','Tahoma','Verdana','Consolas','monospace'].includes(out[key])) out[key]=BASE[key];
  if (Number.isFinite(Number(value.tooltipSize))) out.tooltipSize=Math.min(24,Math.max(9,Number(value.tooltipSize)));
  if ([0,5,10,15,30,60].includes(Number(value.backupMinutes))) out.backupMinutes=Number(value.backupMinutes);
  return out;
}
let cfg=clean(load(STORE)), timer=null;
const mkCheck = (key,label) => '<label><input type="checkbox" data-ptex="'+key+'"> '+label+'</label>';
const mkSelect=(key,values) => '<select data-ptex="'+key+'">'+values.map(item=>'<option value="'+item[0]+'">'+item[1]+'</option>').join('')+'</select>';
const fontChoices=[['Arial','Arial'],['Tahoma','Tahoma'],['Verdana','Verdana'],['Consolas','Consolas'],['monospace','Monospace']];
function expand() {
  const p=doc.querySelector('[data-pref-page="interface"]');
  p.insertAdjacentHTML('beforeend',
   '<fieldset><legend>Additional Interface Settings</legend>'+
   '<label>Color Scheme '+mkSelect('theme',[['classic','Classic Light'],['dark','Dark']])+'</label>'+
   mkCheck('disableAutoCable','Disable Auto Cable (hide automatic connection from palette)')+
   mkCheck('cliDefault','Use CLI as Default Tab for Routers and Switches')+
   mkCheck('logIos','Enable IOS Command Logging (off by default)')+
   '<button type="button" id="ptXExportLog">Export IOS Command Log</button>'+
   '<p>IOS logging may capture sensitive commands. Logs stay in this browser until exported or cleared.</p>'+
   '<button type="button" id="ptXClearLog">Clear IOS Log</button>'+
   '<p>English is currently the only interface language. Sound, QoS stamps and multi-window taskbars require additional engines. Wireless protocol association and fading are not modeled.</p>'+
   '</fieldset>');
  p.querySelectorAll('.pt-prefs-disabled').forEach(el=>{if(el.textContent.includes('Disable Auto Cable'))el.remove()});
  doc.querySelector('[data-pref-page="font"]').insertAdjacentHTML('beforeend',
    '<fieldset><legend>CLI and Tooltip Fonts</legend>'+
    '<label>CLI Font '+mkSelect('cliFont',fontChoices)+'</label>'+
    '<label>Tooltip Font '+mkSelect('tooltipFont',fontChoices)+'</label>'+
    '<label>Tooltip Size <input type="number" data-ptex="tooltipSize" min="9" max="24" step="1"> px</label>'+
    '</fieldset><fieldset><legend>Terminal Colors</legend>'+
    '<label>Router IOS Text <input type="color" data-ptex="iosText"></label>'+
    '<label>Router IOS Background <input type="color" data-ptex="iosBg"></label>'+
    '<label>PC Console Text <input type="color" data-ptex="pcText"></label>'+
    '<label>PC Console Background <input type="color" data-ptex="pcBg"></label>'+
    '</fieldset>');
  doc.querySelector('[data-pref-page="administrative"]').innerHTML=
    '<h3>Administrative</h3><fieldset><legend>Choose Password (not supported)</legend>'+
    '<label>Password <input type="password" disabled placeholder="Requires administrative authentication backend"></label>'+
    '<label>Confirm <input type="password" disabled></label><button disabled>Enable Password</button> <button disabled>Disable Password</button></fieldset>'+
    '<fieldset><legend>Interface Locking (local only)</legend>'+
    mkCheck('hideMultiuser','Hide Multiuser device category in this browser')+
    '<p>Local visibility is not a security boundary. Password-protected global locking and external skills-assessment registration require a separate administrative backend.</p></fieldset>'+
    '<fieldset><legend>User Folder and Configuration</legend><p>Current simulator saves network state on the host in its configured autosave file. The browser cannot change the host User Folder.</p>'+
    '<button type="button" id="ptXSettingsExport">Export Preferences JSON</button> <button type="button" id="ptXSettingsReset">Reset Extra Settings</button></fieldset>'+
    '<fieldset><legend>legacy network simulator Skills Assessments</legend><p>Assessment registration is specific to legacy network simulator.</p><button disabled>Register</button></fieldset>'+
    '<fieldset><legend>Write Options to Installed Folder</legend><button disabled>Write</button></fieldset>'+
    '<p>Installation-wide PT.conf, assessment registration and administrative passwords are not supported.</p>';
  doc.querySelector('[data-pref-page="hide"]').innerHTML=
    '<h3>Hide Device Dialog Tabs</h3><fieldset><legend>Available tabs</legend>'+
    mkCheck('hidePhysical','Hide Physical tab')+
    mkCheck('hideConfig','Hide Config tab')+
    mkCheck('hideCli','Hide CLI tab')+
    mkCheck('hideDesktop','Hide Desktop tab')+
    mkCheck('hideServices','Hide Services tab')+
    mkCheck('hideProgramming','Hide Programming tab')+
    mkCheck('hideAttributes','Hide Attributes tab')+
    '<p>These controls hide tabs in this browser, including on existing devices. They are not secure activity restrictions; GUI/HTML GUI tabs are not currently modeled.</p></fieldset>';
  doc.querySelector('[data-pref-page="misc"]').innerHTML=
    '<h3>Miscellaneous</h3><fieldset><legend>Auto File Backup</legend>'+
    '<label>Backup Interval '+mkSelect('backupMinutes',[['0','Off'],['5','5 minutes'],['10','10 minutes'],['15','15 minutes'],['30','30 minutes'],['60','60 minutes']])+'</label>'+
    '<p>When this browser is open, Packet Tracker and Simulator creates separate host-side lab snapshots on the configured interval. The simulator already autosaves after each command. Backups are retained separately (maximum 24).</p>'+
    '<button type="button" id="ptXBackupNow">Back Up Now</button> <button type="button" id="ptXBackupRefresh">View Backups</button>'+
    '<div id="ptXBackups" aria-live="polite"></div></fieldset>'+
    '<fieldset><legend>Simulation / Network</legend>'+
    '<label class="pt-prefs-disabled"><input type="checkbox" disabled> Simulation - Buffer Full Action (event engine pending)</label>'+
    '<label class="pt-prefs-disabled"><input type="checkbox" disabled> External Network Access from Device Scripts (disabled)</label>'+
    '<p>Proxy Settings are not exposed because network requests currently use the browser and host defaults. No external script access is granted here.</p></fieldset>';
  doc.querySelector('[data-pref-page="answer"]').innerHTML=
    '<h3>Answer Tree</h3><p>legacy network simulator uses this panel to filter activity assessment nodes. Packet Tracker and Simulator does not yet have a grading engine or working Answer Tree.</p>'+
    '<fieldset><legend>Device Groups (not available)</legend>'+
    '<label class="pt-prefs-disabled"><input type="checkbox" checked disabled> Routers</label>'+
    '<label class="pt-prefs-disabled"><input type="checkbox" checked disabled> Switches</label>'+
    '<label class="pt-prefs-disabled"><input type="checkbox" checked disabled> End Devices</label>'+
    '<div class="pt-x-tree"><button disabled>Show All</button> <button disabled>Default</button> <button disabled>Router</button> <button disabled>Switch</button>'+
    '<p>Device → Interfaces → ACL → Routing → Protocol settings</p></div></fieldset>';
  doc.querySelector('[data-pref-page="custom"]').innerHTML=
    '<h3>Custom Interfaces</h3><fieldset><legend>Custom UI Templates</legend><p>third-party custom-device UI definitions are not currently supported. This panel is reserved for a future editor.</p><button disabled>Import Interface</button> <button disabled>Edit Interface</button></fieldset>';
  doc.querySelector('[data-pref-page="publishers"]').innerHTML=
    '<h3>Publishers</h3><fieldset><legend>Publishers</legend><p>Publisher authoring and registration are not implemented. No external publisher access is enabled.</p><button disabled>Add Publisher</button></fieldset>';
  doc.querySelector('[data-pref-page="images"]').innerHTML=
    '<h3>Image Cleanup</h3><p>Unused, embedded custom topology images can be removed here once Packet Tracker and Simulator supports importing and tracking them. Vendor device art is read-only and will never be deleted from this panel.</p>'+
    '<div class="pt-x-images">No embedded custom images are currently tracked.</div>'+
    '<button type="button" disabled>Delete Selected Images</button>';
}
function apply() {
  doc.body.classList.toggle('pt-theme-dark',cfg.theme==='dark');
  doc.body.classList.toggle('pt-hide-multiuser',cfg.hideMultiuser);
  doc.documentElement.style.setProperty('--pt-tip-size',cfg.tooltipSize+'px');
  doc.documentElement.style.setProperty('--pt-tip-font',cfg.tooltipFont+', Arial, sans-serif');
  doc.documentElement.style.setProperty('--pt-cli-family',cfg.cliFont+', Consolas, monospace');
  for(const key of ['iosText','iosBg','pcText','pcBg'])doc.documentElement.style.setProperty('--pt-'+key, cfg[key]);
  if (cfg.disableAutoCable && typeof selectedCableType!=='undefined' && selectedCableType==='auto') selectedCableType='copper-straight';
  if(typeof renderPalette==='function' && typeof catalog!=='undefined' && catalog.groups.length) renderPalette();
  if(typeof renderDialog==='function' && typeof selected!=='undefined' && selected && !by('deviceDialog').classList.contains('hidden')) renderDialog();
  if(timer!==null) clearInterval(timer);
  timer=cfg.backupMinutes?setInterval(()=>backup(false),cfg.backupMinutes*60000):null;
}
function fill() {
  doc.querySelectorAll('[data-ptex]').forEach(node=>{
    const key=node.dataset.ptex;
    if(node.type==='checkbox')node.checked=!!cfg[key];
    else node.value=cfg[key];
  });
}
function read() {
  const v={...cfg};
  doc.querySelectorAll('[data-ptex]').forEach(node=>{
    const key=node.dataset.ptex;
    v[key]=node.type==='checkbox'?node.checked:node.value;
  });
  cfg=clean(v);
  localStorage.setItem(STORE,JSON.stringify(cfg));
  apply();
}
function download(name,content,mime) {
  const blob=new Blob([content],{type:mime||'text/plain;charset=utf-8'});
  const url=URL.createObjectURL(blob),link=doc.createElement('a');
  link.href=url;link.download=name;link.click();
  setTimeout(()=>URL.revokeObjectURL(url),2000);
}
function getLog(){const v=load(LOG);return Array.isArray(v.entries)?v.entries:[];}
function logIos(line){
  if(!cfg.logIos||!line)return;
  const entries=getLog();
  entries.push(new Date().toISOString()+' '+String(selected||'device')+'# '+line);
  try{localStorage.setItem(LOG,JSON.stringify({entries:entries.slice(-2000)}));}catch{}
}
async function backup(announce) {
  try{
    const res=await fetch('/api/backups',{method:'POST'});
    const data=await res.json();
    if(!res.ok || !data.ok)throw Error(data.error||'Backup failed');
    if(announce)by('ptXBackups').textContent='Created backup: '+data.backup;
  }catch(e){
    if(announce)by('ptXBackups').textContent='Backup error: '+e.message;
    else console.warn('Scheduled Packet Tracker and Simulator backup failed:',e);
  }
}
async function listBackups(){
  const box=by('ptXBackups');box.textContent='Loading backups…';
  try{
    const res=await fetch('/api/backups'),data=await res.json();
    if(!res.ok)throw Error(data.error||'Cannot load backups');
    box.textContent='';
    if(!data.backups.length){box.textContent='No separate backups saved yet.';return;}
    const heading=doc.createElement('p');
    heading.textContent=data.backups.length+' saved backup(s), newest first:';
    box.append(heading);
    for(const item of data.backups){
      const row=doc.createElement('div');row.className='pt-x-backup-row';
      const label=doc.createElement('span');label.textContent=item.name+' ('+Math.ceil(item.bytes/1024)+' KB)';
      const button=doc.createElement('button');button.type='button';button.textContent='Restore';
      button.onclick=async()=>{
        if(!confirm('Replace the current topology with backup '+item.name+'? A pre-restore safety backup will be created.'))return;
        const res=await fetch('/api/backups/restore',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({name:item.name})});
        const result=await res.json();
        if(!res.ok||!result.ok){alert(result.error||'Restore failed');return;}
        if(typeof closeDevice==='function')closeDevice();
        if(typeof selected!=='undefined')selected=null;
        state=result.state;
        render();
        if(typeof status==='function')status('Restored topology from '+item.name);
        listBackups();
      };
      row.append(label,button);box.append(row);
    }
  }catch(e){box.textContent='Backup list unavailable: '+e.message;}
}
const dialog=by('ptPrefsDialog');
if(!dialog)return;
expand();
const profileTab=doc.querySelector('[data-pref-tab="profile"]');
if(profileTab)profileTab.hidden=true;
const oldTabs=window.tabsFor,oldRender=window.renderDialog,oldPalette=window.renderPalette,oldOpen=window.openDevice;
if(typeof oldOpen==='function'){
  window.openDevice=function(name){
    oldOpen(name);
    if(cfg.cliDefault && ['router','switch'].includes(state.devices[name]?.kind)){
      dialogTab='cli';renderDialog();
    }
  };
}
const hideMap={physical:'hidePhysical',config:'hideConfig',cli:'hideCli',desktop:'hideDesktop',services:'hideServices',programming:'hideProgramming',attributes:'hideAttributes'};
if(typeof oldTabs==='function' && typeof oldRender==='function'){
  window.tabsFor=function(d){
    const original=oldTabs(d),visible=original.filter(t=>!cfg[hideMap[t]]);
    return visible.length?visible:['attributes'];
  };
  window.renderDialog=function(){
    if(selected && state.devices[selected]){
      const allowed=window.tabsFor(state.devices[selected]);
      if(!allowed.includes(dialogTab))dialogTab=allowed[0];
    }
    return oldRender();
  };
}
if(typeof oldPalette==='function'){
  window.renderPalette=function(){
    const result=oldPalette();
    if(cfg.disableAutoCable)doc.querySelectorAll('[data-connection="auto"]').forEach(el=>el.remove());
    return result;
  };
}
by('ptPrefsApply').addEventListener('click',read);
by('ptPrefsOK').addEventListener('click',read);
by('ptPrefsRestore').addEventListener('click',()=>{
  doc.querySelectorAll('[data-ptex]').forEach(node=>{
    node.type==='checkbox'?node.checked=!!BASE[node.dataset.ptex]:node.value=BASE[node.dataset.ptex];
  });
});
new MutationObserver(()=>{if(!dialog.hidden)fill();}).observe(dialog,{attributes:true,attributeFilter:['hidden']});
doc.querySelectorAll('[data-pref-tab]').forEach(b=>b.addEventListener('click',()=>{
  if(b.dataset.prefTab==='misc')listBackups();
}));
by('ptXBackupNow').onclick=()=>backup(true);
by('ptXBackupRefresh').onclick=listBackups;
by('ptXExportLog').onclick=()=>download('packet-tracker-ios-log.txt',getLog().join('\n')+'\n');
by('ptXClearLog').onclick=()=>{if(confirm('Clear locally stored IOS command log?'))localStorage.removeItem(LOG);};
by('ptXSettingsExport').onclick=()=>download('packet-tracker-preferences.json',JSON.stringify({basic:load('packetTracker.preferences.v1'),extra:cfg},null,2),'application/json');
by('ptXSettingsReset').onclick=()=>{if(!confirm('Reset extra Preferences settings?'))return;cfg={...BASE};localStorage.setItem(STORE,JSON.stringify(cfg));apply();fill();};
doc.addEventListener('submit',e=>{
  if(e.target && e.target.id==='deviceCliForm')logIos(by('deviceCliIn')?.value.trim());
},true);
fill();
apply();
})();
