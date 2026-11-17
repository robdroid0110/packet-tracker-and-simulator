/* Original practice labs: all mutations and checks use the shared backend. */
(()=>{
'use strict';
const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
const dialog=el('dialog');dialog.id='ptSamples';dialog.setAttribute('aria-labelledby','ptSamplesTitle');dialog.style.cssText='width:min(780px,95vw);max-height:90vh;overflow:auto;padding:20px';document.body.append(dialog);
let language='eng',items=[],current=null;
async function action(kind){
 const r=await fetch('/api/samples/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:kind,id:current})});const data=await r.json();if(!data.ok)throw Error(data.output||data.error);
 if(kind==='load'){state=data.state;render();return data.output}
 const result=JSON.parse(data.output);return (result.passed?'Passed':'Not yet passed')+'\n'+result.checks.map(x=>x.source+' → '+(x.target||'?')+': '+(x.passed?'PASS':'FAIL')+'\n'+x.detail).join('\n');
}
async function open(){
 let response=await fetch('/api/samples?language='+encodeURIComponent(language));let data=await response.json();if(!data.ok)throw Error(data.error);items=data.samples;
 dialog.replaceChildren();const title=el('h2','Sample Labs');title.id='ptSamplesTitle';dialog.append(title,el('p','Choose a practice lab. Loading replaces the current workspace; Undo restores it. Checks test a copy of the current network.'));
 const locale=el('select');locale.setAttribute('aria-label','Sample language');for(const lang of data.languages){const option=el('option',lang.name);option.value=lang.id;locale.append(option)}locale.value=language;locale.onchange=()=>{language=locale.value;open().catch(e=>status(e.message))};dialog.append(locale);
 const selector=el('select');selector.id='ptSampleSelect';selector.setAttribute('aria-label','Sample lab');for(const item of items){const option=el('option',item.category+' — '+item.title);option.value=item.id;selector.append(option)}selector.value=items.some(x=>x.id===current)?current:items[0].id;
 const instructions=el('p'),output=el('pre');instructions.dir=language==='ara'?'rtl':'auto';output.id='ptSampleResult';output.style.whiteSpace='pre-wrap';output.setAttribute('role','status');
 selector.onchange=()=>{current=selector.value;instructions.textContent=items.find(x=>x.id===current).instructions;output.textContent=''};selector.onchange();dialog.append(selector,instructions);
 for(const [kind,label] of [['load','Load sample'],['check','Check current lab']]){const button=el('button',label);button.type='button';button.onclick=async()=>{button.disabled=true;try{output.textContent=await action(kind)}catch(error){output.textContent=error.message}finally{button.disabled=false}};dialog.append(button)}
 const close=el('button','Close');close.type='button';close.onclick=()=>dialog.close();dialog.append(close,output);if(!dialog.open)dialog.showModal();selector.focus();
}
window.PacketTrackerSamples={open};
})();
