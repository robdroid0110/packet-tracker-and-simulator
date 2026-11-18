/* Regression: every logical cable ends on the visible device icon, not labels. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const assert=require('assert/strict'),fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'pts-canvas-geometry-')),ready=path.join(tmp,'ready');
 const proc=spawn('python3',['desktop.py','--server','--port','0','--state',path.join(tmp,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<350&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  assert(fs.existsSync(ready),'isolated server ready');
  const base='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  const execute=async cmd=>{
   const r=await fetch(base+'/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command:cmd})});
   const v=await r.json();assert(v.ok,cmd+': '+(v.output||v.error));return v;
  };
  for(const cmd of [
   'add router R1 120 110','add switch S1 460 110','add pc P1 460 320',
   'add pc P2 680 320','add switch S2 760 110',
   'connect R1 g0/0 S1 fa0/1','connect S1 fa0/2 P1 eth0',
   'connect S1 fa0/3 P2 eth0','connect S1 fa0/4 S2 fa0/1',
   'connect S2 fa0/2 S1 fa0/5','connect S1 fa0/6 S2 fa0/3'
  ])await execute(cmd);
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelectorAll('.diagram-edge').length===6);
  async function inspect(name){
   const result=await page.evaluate(()=>{
    const scale=zoom;
    const bounds=device=>{
     const el=[...document.querySelectorAll('#nodes .node')].find(x=>x.dataset.name===device);
     if(!el||!el.querySelector('.device-icon'))return null;
     const b=el.getBoundingClientRect(),icon=el.querySelector('.device-icon').getBoundingClientRect();
     const w=icon.width/scale,h=icon.height/scale;
     const x=state.devices[device].x+(icon.left-b.left)/scale,y=state.devices[device].y+(icon.top-b.top)/scale;
     const ix=Math.min(5,w*.10),iy=Math.min(4,h*.10);
     return {l:x+ix,r:x+w-ix,t:y+iy,b:y+h-iy};
    };
    const mismatch=[];
    for(const edge of document.querySelectorAll('.diagram-edge')){
     const coords=edge.querySelector('.diagram-cable').getAttribute('d').match(/-?\d+(?:\.\d+)?/g).map(Number);
     for(const [device,p] of [[edge.dataset.a,coords.slice(0,2)],[edge.dataset.b,coords.slice(-2)]]){
      const b=bounds(device);if(!b)continue;
      const [x,y]=p;
      const inside=x>=b.l-.6&&x<=b.r+.6&&y>=b.t-.6&&y<=b.b+.6;
      const touch=Math.min(Math.abs(x-b.l),Math.abs(x-b.r),Math.abs(y-b.t),Math.abs(y-b.b))<.6;
      if(!inside||!touch)mismatch.push({device,inside,touch,point:p,bounds:b});
     }
    }
    return{wrong:mismatch,links:document.querySelectorAll('.diagram-edge').length,
      labelVisible:[...document.querySelectorAll('.diagram-label')].filter(x=>getComputedStyle(x).visibility==='visible').length,
      markerVisible:[...document.querySelectorAll('.diagram-port')].filter(x=>getComputedStyle(x).visibility==='visible').length
    };
   });
   assert.deepEqual(result.wrong,[],name+' anchor mismatch');
   assert.equal(result.links,6,name+' link count');
   console.log('CANVAS_CHECK',name,JSON.stringify({edges:result.links,labels:result.labelVisible,portMarkers:result.markerVisible}));
   return result;
  }
  await page.mouse.move(5,5);
  const at100=await inspect('normal');
  assert.equal(at100.labelVisible,0,'smart labels stay hidden until inspection at normal zoom');
  assert.equal(at100.markerVisible,0,'unfocused port markers remain hidden');
  await page.locator('.diagram-hit').first().focus();
  const focused=await inspect('focused');
  assert(focused.labelVisible>=2,'keyboard focused cable reveals interface labels');
  assert(focused.markerVisible>=2,'keyboard focused cable reveals port markers');
  await page.keyboard.press('Escape');
  for(const value of [.55,1.8]){await page.evaluate(v=>setZoom(v),value);await inspect('zoom-'+value)}
  await page.evaluate(()=>setZoom(1));
  const edge=page.locator('.diagram-edge[data-b="P1"] .diagram-cable');
  const oldPath=await edge.getAttribute('d'),node=page.locator('.node[data-name="P1"]'),box=await node.boundingBox();
  await page.mouse.move(box.x+24,box.y+15);await page.mouse.down();
  await page.mouse.move(box.x+68,box.y+42,{steps:4});
  assert.notEqual(await edge.getAttribute('d'),oldPath,'cable follows device during drag');
  await page.mouse.up();await page.waitForTimeout(250);
  await inspect('after-drag');
  const pair=await page.locator('.diagram-edge').evaluateAll(xs=>xs.filter(x=>['S1','S2'].includes(x.dataset.a)&&['S1','S2'].includes(x.dataset.b)).map(x=>x.querySelector('.diagram-cable').getAttribute('d')));
  assert.equal(new Set(pair).size,3,'parallel links stay distinct while attached to icons');
  assert.deepEqual(errors,[],'no page errors');
  console.log('PASS: icon-perimeter anchors, zoom, labels, port markers, dragging and parallel paths');
 }finally{
  if(browser)await browser.close();
  if(proc.exitCode===null){proc.kill('SIGTERM');await new Promise(r=>proc.once('exit',r))}
  fs.rmSync(tmp,{recursive:true,force:true});
 }
})().catch(e=>{console.error(e);process.exitCode=1});
