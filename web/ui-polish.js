/* Keep controls identifiable when local vendor artwork is unavailable. */
(() => {
 const symbols={newBtn:'＋',openBtn:'↗',saveBtn:'↓',zoomIn:'⊕',zoomOut:'⊖',zoomReset:'1:1',fitBtn:'▣',resetTimeBtn:'↺',stepBackBtn:'◀',playBtn:'▶',stepForwardBtn:'▶|',dialogHelp:'?',globalHelpBtn:'?',dialogClose:'×'};
 const categories={network:'NET',end:'PC',components:'I/O',connections:'↯',misc:'…',multiuser:'MU'};
 const tools={select:'↖',pan:'✋',inspect:'⌕',delete:'×',note:'≡',cable:'↯',pdu:'✉'};
 function fallback(img){
  const button=img.closest('button');
  if(!button||img.closest('.device-icon,.desktop-app')||button.querySelector('.pt-fallback-icon'))return;
  const icon=document.createElement('span');icon.className='pt-fallback-icon';icon.setAttribute('aria-hidden','true');
  const model=button.dataset.model,kind=catalog.models?.[model]?.kind;
  icon.textContent=symbols[button.id]||categories[button.dataset.category]||tools[button.dataset.tool]||(model?({router:'R',switch:'SW',pc:'PC',server:'SV'}[kind]||'◇'):(button.title?.split(' ').map(word=>word[0]).join('').slice(0,3)||'◇'));
  img.hidden=true;button.prepend(icon);
 }
 document.addEventListener('error',event=>{if(event.target.tagName==='IMG')fallback(event.target)},true);
 for(const img of document.querySelectorAll('button img'))if(img.complete&&!img.naturalWidth)fallback(img);
})();
