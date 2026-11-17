/* Preferences: legacy network simulator 9 bundled Help, preferences.htm and fontPreference.htm. */
(() => {
'use strict';
const KEY='packetTracker.preferences.v1',PROFILE='packetTracker.profile.v1';
const initial={deviceLabels:true,linkLights:true,alignment:true,portLabels:'always',animations:true,uiSize:12,cliSize:12,uiFont:'Arial',showWirelessGrid:false};
const fonts=['Arial','Tahoma','Verdana','Consolas','monospace'];
const $p=id=>document.getElementById(id);
function load(key){try{return JSON.parse(localStorage.getItem(key))||{}}catch{return {}}}
function validate(v){
 if(!v||typeof v!=='object')v={};
 const out={...initial};
 for(const k of ['deviceLabels','linkLights','alignment','animations','showWirelessGrid'])if(typeof v[k]==='boolean')out[k]=v[k];
 if(['always','hover','off'].includes(v.portLabels))out.portLabels=v.portLabels;
 for(const [k,min,max] of [['uiSize',10,18],['cliSize',10,20]])if(Number.isFinite(Number(v[k]))&&v[k]!=null)out[k]=Math.max(min,Math.min(max,Number(v[k])));
 if(fonts.includes(v.uiFont))out.uiFont=v.uiFont;
 return out;
}
let current=validate(load(KEY)),page='interface';
function apply(v){
 current=validate(v);
 const root=document.documentElement,body=document.body;
 root.style.setProperty('--pt-ui-size',current.uiSize+'px');
 root.style.setProperty('--pt-global-scale',String(Math.round((current.uiSize/12)*100)/100));
 root.style.setProperty('--pt-cli-size',current.cliSize+'px');
 root.style.setProperty('--pt-ui-font',current.uiFont+', Arial, sans-serif');
 for(const [cls,on] of [
  ['pt-hide-device-labels',!current.deviceLabels],
  ['pt-hide-link-lights',!current.linkLights],
  ['pt-align-enabled',current.alignment],
  ['pt-port-labels-off',current.portLabels==='off'],
  ['pt-port-labels-hover',current.portLabels==='hover'],
  ['pt-no-animation',!current.animations]])body.classList.toggle(cls,on);
 try{localStorage.setItem(KEY,JSON.stringify(current))}catch{}
 window.dispatchEvent(new CustomEvent('pt-physical-presentation',{detail:{showWirelessGrid:current.showWirelessGrid}}));
}
apply(current);
const markup=[
'<div id="ptOptionsMenu" class="pt-options-menu" role="menu" hidden>',
'<button data-option="prefs" role="menuitem">Preferences… <span>Ctrl+R</span></button>',
'<button data-option="profile" role="menuitem">User Profile…</button>',
'<button data-option="help" role="menuitem">Preferences Help</button></div>',
'<div id="ptPrefsDialog" class="pt-prefs-overlay" hidden role="dialog" aria-modal="true" aria-labelledby="ptPrefsTitle">',
'<div class="pt-prefs-window"><header class="pt-prefs-title"><strong id="ptPrefsTitle">Preferences</strong><button id="ptPrefsClose" aria-label="Close preferences">×</button></header>',
'<nav class="pt-prefs-tabs" aria-label="Preferences sections">',
...[
['interface','Interface'],['administrative','Administrative'],['hide','Show/Hide'],['font','Font'],['misc','Miscellaneous'],
['answer','Answer Tree'],['custom','Custom Interfaces'],['publishers','Publishers'],['images','Image Cleanup'],['profile','User Profile']
].map(([id,label])=>'<button type="button" data-pref-tab="'+id+'">'+label+'</button>'),
'</nav><div class="pt-prefs-body">',
'<div data-pref-page="interface" class="pt-prefs-page"><fieldset><legend>Workspace Presentation</legend>',
'<label><input type="checkbox" id="ptPrefDeviceLabels"> Show Device Labels</label>',
'<label><input type="checkbox" id="ptPrefLinkLights"> Show Link Lights</label>',
'<label><input type="checkbox" id="ptPrefAlignment"> Show Alignment Guides (snap to nearby devices)</label>',
'<label>Port Labels <select id="ptPrefPortLabels"><option value="always">Always show</option><option value="hover">On mouse over</option><option value="off">Hide</option></select></label>',
'<label><input type="checkbox" id="ptPrefAnimation"> Animation</label>',
'<label><input type="checkbox" id="ptPrefCableEffects"> Enable Cable Length Effects (100 m Ethernet limit)</label>',
'<label><input type="checkbox" id="ptPrefWirelessGrid"> Show Wireless Grid (range visualization only)</label>',
'<p id="ptPrefPhysicsError" role="alert" aria-live="assertive"></p>',
'</fieldset><fieldset><legend>Not yet supported</legend>',
...[
'Sound (no sound engine)','Show QoS Stamps (packet simulation pending)',
'Disable Auto Cable (media validation pending)','Show Device Dialog Taskbar (multi-window pending)'
].map(s=>'<label class="pt-prefs-disabled"><input type="checkbox" disabled> '+s+'</label>'),
'</fieldset><p>Presentation is stored in this browser; cable-length effects are stored in the shared lab and affect actual Ethernet connectivity.</p></div>',
'<div data-pref-page="font" class="pt-prefs-page" hidden><fieldset><legend>Application Font</legend>',
'<label>Font family <select id="ptPrefUiFont">'+fonts.map(s=>'<option>'+s+'</option>').join('')+'</select></label>',
'<label>Application Global Size <output id="ptPrefUiSizeOutput"></output><input type="range" id="ptPrefUiSize" min="10" max="18" step="1"></label>',
'</fieldset><fieldset><legend>CLI Font</legend>',
'<label>CLI text size <output id="ptPrefCliSizeOutput"></output><input type="range" id="ptPrefCliSize" min="10" max="20" step="1"></label>',
'</fieldset><p>Application Global Size scales menu/toolbar/palette controls and their icons; topology coordinates stay unchanged. Native browser tooltips and operating-system display scaling are managed separately.</p></div>',
'<div data-pref-page="profile" class="pt-prefs-page" hidden><fieldset><legend>Local User Profile</legend>',
'<label>Name <input id="ptProfileName" maxlength="80"></label>',
'<label>E-mail <input id="ptProfileEmail" type="email" maxlength="160"></label>',
'<label>Additional Info <textarea id="ptProfileInfo" maxlength="500"></textarea></label>',
'</fieldset><p>Stored locally; activity-assessment and Multiuser integrations are not implemented.</p></div>',
...[
['administrative','Administrative','Interface locks, assessment registration, user folders and preferences passwords are not yet supported.'],
['hide','Hide','Restricting device tabs for graded activities is not yet implemented.'],
['misc','Miscellaneous','Auto backup, simulation-buffer actions, proxy and external networking settings require supporting simulator functionality. External network access is not enabled.'],
['answer','Answer Tree','Assessment tree filtering requires an Activity Wizard implementation.'],
['custom','Custom Interfaces','third-party custom user interfaces are not yet implemented.'],
['publishers','Publishers','Publisher integrations are not yet implemented.'],
['images','Image Cleanup','Cleaning embedded topology images is not yet implemented.']
].map(([id,label,info])=>'<div data-pref-page="'+id+'" class="pt-prefs-page" hidden><h3>'+label+'</h3><p>'+info+'</p></div>'),
'</div><footer class="pt-prefs-footer"><button id="ptPrefsHelp">Help</button><div class="pt-prefs-spacer"></div>',
'<button id="ptPrefsRestore">Restore Defaults</button><button id="ptPrefsCancel">Cancel</button>',
'<button id="ptPrefsApply">Apply</button><button id="ptPrefsOK">OK</button></footer></div></div>'
].join('');
document.body.insertAdjacentHTML('beforeend',markup);
const menu=$p('ptOptionsMenu'),dialog=$p('ptPrefsDialog');
const options=Array.from(document.querySelectorAll('#menuBar .menu-item')).find(b=>b.textContent.trim()==='Options');
function closeMenu(){menu.hidden=true;options?.setAttribute('aria-expanded','false')}
function openMenu(){
 if(!options)return;const r=options.getBoundingClientRect();
 menu.style.left=r.left+'px';menu.style.top=r.bottom+'px';menu.hidden=false;
 options.setAttribute('aria-expanded','true');
}
if(options){
 options.setAttribute('aria-haspopup','menu');options.setAttribute('aria-expanded','false');
 options.addEventListener('click',e=>{e.stopPropagation();menu.hidden?openMenu():closeMenu()});
}
document.addEventListener('pointerdown',e=>{if(!menu.hidden&&!menu.contains(e.target)&&e.target!==options)closeMenu()});
function setPage(id){
 page=id;
 document.querySelectorAll('[data-pref-tab]').forEach(b=>{
  const active=b.dataset.prefTab===id;b.classList.toggle('active',active);b.setAttribute('aria-selected',String(active));
 });
 document.querySelectorAll('[data-pref-page]').forEach(el=>el.hidden=el.dataset.prefPage!==id);
}
function labels(){
 $p('ptPrefUiSizeOutput').textContent=$p('ptPrefUiSize').value+' px';
 $p('ptPrefCliSizeOutput').textContent=$p('ptPrefCliSize').value+' px';
}
function fill(){
 $p('ptPrefDeviceLabels').checked=current.deviceLabels;
 $p('ptPrefLinkLights').checked=current.linkLights;
 $p('ptPrefAlignment').checked=current.alignment;
 $p('ptPrefPortLabels').value=current.portLabels;
 $p('ptPrefAnimation').checked=current.animations;
 $p('ptPrefWirelessGrid').checked=current.showWirelessGrid;
 $p('ptPrefCableEffects').checked=typeof state!=='undefined'&&!!state.cable_length_effects;
 $p('ptPrefPhysicsError').textContent='';
 $p('ptPrefUiFont').value=current.uiFont;
 $p('ptPrefUiSize').value=current.uiSize;
 $p('ptPrefCliSize').value=current.cliSize;
 labels();
 const profile=load(PROFILE);
 $p('ptProfileName').value=typeof profile.name==='string'?profile.name:'';
 $p('ptProfileEmail').value=typeof profile.email==='string'?profile.email:'';
 $p('ptProfileInfo').value=typeof profile.info==='string'?profile.info:'';
}
function open(id='interface'){closeMenu();fill();setPage(id);dialog.hidden=false;$p('ptPrefsClose').focus()}
function close(){dialog.hidden=true}
async function save(){
 const desiredCableEffects=$p('ptPrefCableEffects').checked;
 $p('ptPrefPhysicsError').textContent='';
 apply({
 deviceLabels:$p('ptPrefDeviceLabels').checked,linkLights:$p('ptPrefLinkLights').checked,alignment:$p('ptPrefAlignment').checked,
 portLabels:$p('ptPrefPortLabels').value,animations:$p('ptPrefAnimation').checked,
 showWirelessGrid:$p('ptPrefWirelessGrid').checked,
 uiSize:Number($p('ptPrefUiSize').value),cliSize:Number($p('ptPrefCliSize').value),uiFont:$p('ptPrefUiFont').value
 });
 const profile={name:$p('ptProfileName').value.trim(),email:$p('ptProfileEmail').value.trim(),info:$p('ptProfileInfo').value.trim()};
 try{localStorage.setItem(PROFILE,JSON.stringify(profile))}catch{}
 if(typeof state!=='undefined'&&desiredCableEffects!==!!state.cable_length_effects){
  try{
   const response=await fetch('/api/physical-distance/action',{
    method:'POST',headers:{'content-type':'application/json'},
    body:JSON.stringify({action:'cable_effects',enabled:desiredCableEffects})});
   const result=await response.json();
   if(!response.ok||!result.ok)throw Error(result.error||result.output||'Unable to change cable effects');
   state=result.state;
   if(typeof render==='function')render();
   window.dispatchEvent(new Event('pt-physical-distance-refresh'));
  }catch(error){
   $p('ptPrefPhysicsError').textContent='Cable effects not applied: '+error.message;
   $p('ptPrefCableEffects').checked=!!state.cable_length_effects;
   return false;
  }
 }
 return true;
}
document.querySelectorAll('[data-option]').forEach(b=>b.onclick=()=>{
 if(b.dataset.option==='help'){closeMenu();window.open('/help/index.html?topic=preferences','_blank','noopener')}
 else open(b.dataset.option==='profile'?'profile':'interface');
});
document.querySelectorAll('[data-pref-tab]').forEach(b=>b.onclick=()=>setPage(b.dataset.prefTab));
for(const id of ['ptPrefUiSize','ptPrefCliSize'])$p(id).addEventListener('input',labels);
$p('ptPrefsClose').onclick=$p('ptPrefsCancel').onclick=close;
$p('ptPrefsApply').onclick=()=>save();
$p('ptPrefsOK').onclick=async()=>{if(await save())close()};
$p('ptPrefsRestore').onclick=()=>{
 $p('ptPrefDeviceLabels').checked=initial.deviceLabels;
 $p('ptPrefLinkLights').checked=initial.linkLights;
 $p('ptPrefAlignment').checked=initial.alignment;
 $p('ptPrefPortLabels').value=initial.portLabels;
 $p('ptPrefAnimation').checked=initial.animations;
 $p('ptPrefWirelessGrid').checked=initial.showWirelessGrid;
 $p('ptPrefCableEffects').checked=false;
 $p('ptPrefUiFont').value=initial.uiFont;
 $p('ptPrefUiSize').value=initial.uiSize;
 $p('ptPrefCliSize').value=initial.cliSize;labels();
};
$p('ptPrefsHelp').onclick=()=>window.open('/help/index.html?topic='+(page==='font'?'font':'preferences'),'_blank','noopener');
dialog.addEventListener('pointerdown',e=>{if(e.target===dialog)close()});
document.addEventListener('keydown',e=>{
 if(e.key==='Escape'&&!dialog.hidden){e.preventDefault();close();return}
 if(e.key==='Escape'&&!menu.hidden){e.preventDefault();closeMenu();return}
 if((e.ctrlKey||e.metaKey)&&!e.shiftKey&&!e.altKey&&e.key.toLowerCase()==='r'){
  e.preventDefault();open();
 }
});
})();