/* Logical workspace notes: same state and commands as agent shell. */
(() => {
'use strict';
const host=document.getElementById('nodes'),layer=document.createElement('div');
layer.id='workspaceNotes';
host.insertAdjacentElement('afterend',layer);
let dragging=null;
function renderNotes(){
 layer.innerHTML='';
 layer.style.transform='scale('+zoom+')';
 layer.style.transformOrigin='0 0';
 const data=state.notes||{};
 document.getElementById('emptyHint').style.display=Object.keys(state.devices).length||Object.keys(data).length?'none':'grid';
 for(const [id,record] of Object.entries(data)){
  const note=document.createElement('div');
  note.className='workspace-note';note.dataset.noteId=id;
  note.style.left=record.x+'px';note.style.top=record.y+'px';note.title='Double-click to edit; drag to move; Delete tool to remove';
  note.textContent=record.text;
  note.addEventListener('pointerdown',e=>{
   if(activeTool!=='select'||e.button!==0)return;
   e.stopPropagation();
   const rect=workspace.getBoundingClientRect();
   dragging={id,dx:(e.clientX-rect.left-(window.ptPan?.x||0))/zoom-record.x,dy:(e.clientY-rect.top-(window.ptPan?.y||0))/zoom-record.y,moved:false};
   note.setPointerCapture(e.pointerId);
  });
  note.addEventListener('pointermove',e=>{
   if(!dragging||dragging.id!==id)return;
   const rect=workspace.getBoundingClientRect();
   record.x=Math.round((e.clientX-rect.left-(window.ptPan?.x||0))/zoom-dragging.dx);
   record.y=Math.round((e.clientY-rect.top-(window.ptPan?.y||0))/zoom-dragging.dy);
   note.style.left=record.x+'px';note.style.top=record.y+'px';dragging.moved=true;
  });
  note.addEventListener('pointerup',e=>{
   if(!dragging||dragging.id!==id)return;
   const moved=dragging.moved;dragging=null;
   if(note.hasPointerCapture(e.pointerId))note.releasePointerCapture(e.pointerId);
   if(moved)command('note move '+id+' '+record.x+' '+record.y,false);
  });
  note.addEventListener('click',e=>{
   e.stopPropagation();
   if(activeTool==='delete')command('note delete '+id,false);
  });
  note.addEventListener('dblclick',e=>{
   e.stopPropagation();
   if(activeTool!=='select')return;
   const updated=window.prompt('Edit workspace note',record.text);
   if(updated!==null&&updated.trim()&&updated!==record.text)command('note edit '+id+' '+JSON.stringify(updated),false);
  });
  layer.appendChild(note);
 }
}
const oldTopology=renderTopology;
renderTopology=function(){oldTopology();renderNotes()};
workspace.addEventListener('click',e=>{
 if(activeTool!=='note'||e.target!==workspace)return;
 const text=window.prompt('Place note (1-800 characters)','');
 if(!text||!text.trim())return;
 const rect=workspace.getBoundingClientRect();
 const x=Math.round((e.clientX-rect.left-(window.ptPan?.x||0))/zoom),y=Math.round((e.clientY-rect.top-(window.ptPan?.y||0))/zoom);
 command('note add '+x+' '+y+' '+JSON.stringify(text),false);
});
})();