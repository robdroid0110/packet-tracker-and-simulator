/* First lab: simulated DNS/HTTP Services and PC Web Browser. No external requests. */
(() => {
'use strict';
const oldServices=renderServices, oldTool=renderDesktopTool, history={};
const q=(root,selector)=>root.querySelector(selector);
const node=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n};
function makeRow(parent,label,value,placeholder){
 const wrap=node('div');wrap.className='pt-form-row';const l=node('label',label);
 const inp=node('input');inp.id=label==='Name'?'ptDnsName':label==='Address'?'ptDnsIp':'';inp.value=value||'';inp.placeholder=placeholder||'';wrap.append(l,inp);parent.append(wrap);return inp;
}
function serverPanel(body,title){
 const content=q(body,'.pt-services-body');content.textContent='';
 const section=node('section');section.className='pt-doc-section';
 const header=node('h3',title);section.append(header);content.append(section);return section;
}
function serviceToggle(section,service,enabled){
 const field=node('fieldset');field.className='pt-fieldset';
 const legend=node('legend',service+' Service');field.append(legend);
 for(const value of ['on','off']){
   const label=node('label');const radio=node('input');radio.type='radio';radio.name='firstlab'+service;radio.value=value;radio.checked=enabled===(value==='on');
   label.append(radio,document.createTextNode(' '+(value==='on'?'On':'Off')));field.append(label);
   radio.onchange=async()=>{const r=await command(service.toLowerCase()+'-service '+selected+' '+value,false);status(r.output)};
 }
 section.append(field);
}
renderServices=function(d,body){
 oldServices(d,body);
 if(d.kind!=='server'|| !['DNS','HTTP'].includes(ptServiceView))return;
 const section=serverPanel(body,ptServiceView);
 section.classList.add(ptServiceView==='DNS'?'pt-dns-form':'pt-http-form');
 serviceToggle(section,ptServiceView,ptServiceView==='DNS'?d.dns_enabled:d.http_enabled);
 if(ptServiceView==='DNS'){
   const name=makeRow(section,'Name','','www.firstlab.com'),address=makeRow(section,'Address','','192.168.0.105');
   const add=node('button','Add');section.append(add);
   const table=node('table');table.className='compact-table';const head=node('tr');
   for(const title of ['Name','Type','Address','Action'])head.append(node('th',title));
   table.append(head);
   for(const [host,ip] of Object.entries(d.dns_records||{})){
     const tr=node('tr');tr.append(node('td',host),node('td','A'),node('td',ip));
     const td=node('td'),del=node('button','Remove');del.onclick=async()=>{
       const r=await command('dns-delete '+selected+' '+host,false);if(r.ok)renderDialog();else status(r.output)
     };td.append(del);tr.append(td);table.append(tr);
   }
   section.append(table);
   add.onclick=async()=>{
     if(!name.value.trim()||!address.value.trim())return status('Domain name and IP required');
     const r=await command('dns-add '+selected+' '+name.value.trim()+' '+address.value.trim(),false);
     if(r.ok)renderDialog();else status(r.output);
   };
 }else{
   const sel=node('select');
   const files=Object.keys(d.http_pages||{'/':''});
   for(const file of files){const op=node('option',file==='/'?'index.html':file);op.value=file;sel.append(op)}
   const row=node('div');row.className='pt-form-row';row.append(node('label','File'),sel);section.append(row);
   const editor=node('textarea');editor.id='ptHtmlEditor';editor.spellcheck=false;
   sel.onchange=()=>{editor.value=d.http_pages?.[sel.value]||''};sel.onchange();
   section.append(node('label','HTML Content'),editor);
   const save=node('button','Save');section.append(save);
   section.append(node('p','Page is only served inside the simulated network; there is no real HTTP listener.'));
   save.onclick=async()=>{
     const result=await fetch('/api/http-page',{method:'POST',headers:{'content-type':'application/json'},
       body:JSON.stringify({server:selected,path:sel.value,html:editor.value})});
     const data=await result.json();
     if(!data.ok)return status(data.error||'Unable to save');
     state=data.state;status('Saved '+sel.value+' on '+selected);
   };
 }
};
document.addEventListener('packettracker:packet-step',e=>{
 for(const [name,pending] of Object.entries(history)){
   if(!pending.pending)continue;
   if(pending.job){
    const p=state.simulation?.pdus?.[pending.job];if(!p?.result)continue;
    const response=p.result.output||{};pending.pending=false;pending.html=response.html||'<p>'+esc(p.result.message||'Request completed')+'</p>';pending.status=p.status+' · '+(response.status||'');
   }else{
    if(e.detail.seq<pending.completeSeq)continue;
    pending.pending=false;pending.status=pending.finalStatus;
   }
   if(selected===name && desktopTool==='browser' && !document.querySelector('#deviceDialog').classList.contains('hidden')){
     const frame=document.querySelector('#ptWebFrame'),st=document.querySelector('.pt-web-status');
     if(frame)frame.srcdoc=sandbox(pending.html);
     if(st)st.textContent=pending.status;
   }
 }
});
function sandbox(html){
 const csp="<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; style-src 'unsafe-inline'; img-src data:; form-action 'none'\">";
 return '<!doctype html><html><head><meta charset="utf-8">'+csp+'</head><body>'+String(html||'')+'</body></html>';
}
renderDesktopTool=function(d,body){
 if(desktopTool!=='browser')return oldTool(d,body);
 const who=selected,h=history[who]||{};
 body.textContent='';
 const root=node('div');root.className='pt-web-browser';
 const top=node('header');top.className='pt-web-header';top.append(node('strong','Web Browser'));
 const close=node('button','×');close.onclick=()=>{desktopTool=null;renderDialog()};top.append(close);root.append(top);
 const form=node('form');form.id='ptWebForm';form.className='pt-web-navigation';const label=node('label','URL');
 const address=node('input');address.id='ptWebAddress';address.autocomplete='off';address.placeholder='www.firstlab.com';address.value=h.url||'';
 const go=node('button','Go');go.type='submit';form.append(label,address,go);root.append(form);
 const st=node('div',h.status||'Enter a simulated HTTP URL.');st.className='pt-web-status';root.append(st);
 const frame=node('iframe');frame.id='ptWebFrame';frame.title='Simulated HTTP page';frame.setAttribute('sandbox','');frame.referrerPolicy='no-referrer';root.append(frame);
 if(h.html)frame.srcdoc=sandbox(h.pending?'<p>Waiting for network events. Use Capture / Forward.</p>':h.html);
 body.append(root);
 form.onsubmit=async e=>{
   e.preventDefault();const url=address.value.trim();if(!url)return;
   st.textContent='Loading '+url+' through simulated network…';
   try{
     const response=await fetch('/api/web',{method:'POST',headers:{'content-type':'application/json'},
       body:JSON.stringify({source:who,url})});
     const data=await response.json();
     if(data.state){state=data.state;renderTopology();renderEvents()}
     if(!data.ok && response.status!==200)throw new Error(data.error||'Request failed');
     if(data.pending){history[who]={url,status:'Waiting for captured HTTP request…',html:'',pending:true,job:data.job};st.textContent=history[who].status;frame.srcdoc=sandbox('<p>Waiting for network events. Use Capture / Forward.</p>');return}
     if(data.management){
      const manage=node('button','Manage Device');manage.type='button';manage.onclick=async()=>{
       const username=prompt('Management username');if(username===null)return;const password=prompt('Management password')??'';
       try{const r=await fetch('/api/device-config/action',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({action:'management_login',device:who,server:data.resolved_ip,username,password,protocol:url.startsWith('https:')?'https':'http',setup:true})});const result=await r.json();if(!result.ok)throw Error(result.output||result.error);const login=JSON.parse(result.output);window.PacketTrackerDeviceConfig.open(login.device,'global',{remote:{source:who,token:login.token}})}catch(error){st.textContent=error.message}
      };root.append(manage);
     }
     const content=data.html||'<h1>Empty Response</h1>';
     const resolved='HTTP '+data.status+' · '+data.resolved_ip+' · '+data.server;
     if(simulationMode){
       const final=(state.packet_events||[]).filter(e=>e.protocol==='HTTP').at(-1);
       history[who]={url,status:'Waiting for HTTP packet in Simulation Mode…',html:content,pending:true,completeSeq:final?.seq||0,finalStatus:resolved};
       st.textContent=history[who].status;frame.srcdoc=sandbox('<p>Waiting for network events. Use Capture / Forward.</p>');
     }else{st.textContent=resolved;frame.srcdoc=sandbox(content);history[who]={url,status:resolved,html:content}}

   }catch(err){
     st.textContent=String(err.message||err);
     const content='<h3>'+esc(st.textContent)+'</h3>';
     frame.srcdoc=sandbox(content);history[who]={url,status:st.textContent,html:content};
   }
 };
};
})();