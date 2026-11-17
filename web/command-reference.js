/* Read-only reference vocabulary and authoritative CLI execution. */
(()=>{
'use strict';
const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n};
const dialog=el('dialog');dialog.id='ptCommandReference';dialog.setAttribute('aria-label','Command Reference');dialog.style.cssText='width:min(800px,95vw);max-height:90vh;overflow:auto';document.body.append(dialog);
async function open(){
 const reference=await(await fetch('/api/command-reference')).json();dialog.replaceChildren(el('h2','Command Reference'),el('p',reference.notice));
 const profile=el('select');profile.setAttribute('aria-label','Reference profile');for(const record of reference.profiles){const option=el('option',record.section+' — '+record.profile);option.value=record.profile;profile.append(option)}
 const modes=el('pre'),link=el('a','Official command syntax');link.target='_blank';link.rel='noopener';
 profile.onchange=()=>{const record=reference.profiles.find(p=>p.profile===profile.value);link.href=record.url;modes.textContent=record.modes.map(m=>m.name+'\n'+m.command_roots.join(', ')).join('\n\n')};profile.onchange();
 const device=el('select');device.setAttribute('aria-label','CLI device');for(const name of Object.keys(state.devices)){const option=el('option',name);option.value=name;device.append(option)}if(selected)device.value=selected;
 const form=el('form'),input=el('input');input.setAttribute('aria-label','Command');input.placeholder='Command for the selected device';input.style.width='70%';const run=el('button','Run command');run.type='submit';const output=el('pre');output.setAttribute('role','status');output.style.whiteSpace='pre-wrap';
 form.append(device,input,run);form.onsubmit=async event=>{event.preventDefault();run.disabled=true;try{const d=state.devices[device.value];let result;if(['pc','server'].includes(d.kind)){result=await(await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({device:device.value,action:'host_command',command:input.value})})).json();if(result.state){state=result.state;render()}}else result=await command('ios '+device.value+' '+JSON.stringify(input.value),false);output.textContent=result.output||result.error||''}catch(error){output.textContent=error.message}finally{run.disabled=false}};
 const close=el('button','Close');close.onclick=()=>dialog.close();dialog.append(profile,link,modes,form,output,close);if(!dialog.open)dialog.showModal();profile.focus();
}
const button=el('button','Command Reference');button.id='ptCommandReferenceOpen';button.onclick=()=>open().catch(e=>status(e.message));document.querySelector('#toolRail').append(button);
window.PacketTrackerCommandReference={open};
})();
