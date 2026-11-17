/* Isolated real-backend coverage for diagram projection and saved layout controls. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-diagram-')),ready=path.join(dir,'ready');
 const exe=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(exe||'python3',[...(exe?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  assert(fs.existsSync(ready),'Server started');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  async function api(route,body){const r=await fetch(url+route,body?{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)}:{});const v=await r.json();assert(v.ok!==false,JSON.stringify(v));return v}
  const command=command=>api('/api/command',{command});
  for(const c of ['add router R1 120 120','add switch S1 450 120','add pc P1 450 340','add pc P2 700 340','add pc Obstacle 270 120','connect R1 g0/0 S1 fa0/1','connect S1 fa0/2 P1 eth0','connect S1 fa0/3 P2 eth0','ip R1 g0/0 192.0.2.1/24'])await command(c);
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(10000);
  await page.goto(url);await page.waitForFunction(()=>document.querySelectorAll('.diagram-edge').length===3);
  assert.equal(await page.locator('.diagram-label').count(),6);
  assert.equal((await page.locator('.diagram-cable').first().getAttribute('d')).split('L').length,2,'Single connections stay straight');
  // Focus from keyboard reveals only related links and preserves normal node interaction.
  await page.locator('.node[data-name="P1"]').focus();
  assert.equal(await page.locator('.diagram-focused').count(),1);
  assert.equal(await page.locator('.diagram-edge.diagram-dim').count(),2);
  await page.mouse.move(5,5);await page.locator('.diagram-hit').first().focus();await page.keyboard.press('Enter');
  assert.equal(await page.locator('.diagram-focused').count(),1);
  const before=await api('/api/state');
  await page.locator('#topologyDisplayBtn').click();await page.getByRole('button',{name:'Preview tidy layout',exact:true}).click();
  await page.locator('#diagramPreview').waitFor();
  assert.equal((await api('/api/state')).devices.R1.x,before.devices.R1.x);
  assert.notEqual(await page.locator('.node[data-name="R1"]').evaluate(n=>parseFloat(n.style.left)),before.devices.R1.x);
  let previewPopups=0;const countPopup=()=>previewPopups++;page.on('popup',countPopup);
  const previewNode=await page.locator('.node[data-name="R1"]').boundingBox();
  await page.mouse.move(previewNode.x+20,previewNode.y+20);await page.mouse.down();await page.mouse.move(previewNode.x+80,previewNode.y+30);await page.mouse.up();
  assert.equal((await api('/api/state')).devices.R1.x,before.devices.R1.x);
  assert.equal(previewPopups,0);page.off('popup',countPopup);
  assert.equal(await page.evaluate(()=>PacketTrackerWorkspace.selected.size),0);
  await page.locator('#diagramPreview').getByRole('button',{name:'Cancel'}).click();
  assert.equal(await page.locator('.node[data-name="R1"]').evaluate(n=>parseFloat(n.style.left)),before.devices.R1.x);
  await page.locator('#topologyDisplayBtn').click();await page.getByRole('button',{name:'Preview tidy layout',exact:true}).click();
  await page.locator('#diagramPreview').getByRole('button',{name:'Apply',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('#diagramPreview').hidden);
  assert.notEqual((await api('/api/state')).devices.R1.x,before.devices.R1.x);
  assert.equal((await api('/api/state')).devices.R1.interfaces['g0/0'].ip,'192.0.2.1/24');
  await command('undo');await page.evaluate(()=>fetchState());
  assert.equal((await api('/api/state')).devices.R1.x,before.devices.R1.x);
  // Create group using actual multi-selection and dialog controls.
  await page.locator('.node[data-name="P1"]').click({modifiers:['Control']});
  await page.locator('.node[data-name="S1"]').click({modifiers:['Control']});
  await page.locator('#topologyDisplayBtn').click();
  page.once('dialog',d=>d.accept('Office'));
  await page.getByRole('button',{name:'Group selected devices',exact:true}).click();
  await page.getByRole('button',{name:'Collapse',exact:true}).click();
  await page.waitForFunction(()=>document.querySelector('.diagram-group'));
  await page.locator('#diagramOptions').getByRole('button',{name:'Close',exact:true}).click();
  assert.equal(await page.locator('.node[data-name="P1"]').isVisible(),false);
  assert.equal(await page.locator('#nodes .node[tabindex="0"]:visible').count(),1);
  assert.equal(await page.locator('.diagram-edge').count(),2); // Internal S1-P1 hidden; R1-S1 and S1-P2 retained.
  assert((await api('/api/state')).workspace_tools.diagram.groups.Office.collapsed);
  await page.reload();await page.locator('.diagram-group').waitFor();
  assert.equal(await page.locator('.node[data-name="P1"]').isVisible(),false);
  assert.equal(await page.locator('#nodes .node[tabindex="0"]:visible').count(),1);
  await page.locator('.diagram-group').click();await page.waitForFunction(()=>!document.querySelector('.diagram-group'));
  assert(await page.locator('.node[data-name="P1"]').isVisible());
  await page.evaluate(()=>{PacketTrackerWorkspace.selected.clear();document.activeElement.blur();setZoom(.5)});
  await page.mouse.move(5,5);await page.keyboard.press('Escape');
  assert.equal(await page.locator('.diagram-label').evaluateAll(ns=>ns.filter(n=>getComputedStyle(n).visibility==='visible').length),0);
  await page.locator('#topologyDisplayBtn').click();await page.getByLabel('Interface label detail').selectOption('all');
  await page.waitForFunction(()=>state.workspace_tools.diagram.labels==='all');
  assert.equal(await page.locator('.diagram-label').evaluateAll(ns=>ns.filter(n=>getComputedStyle(n).visibility==='visible').length),6);
  await page.getByLabel('Interface label detail').selectOption('none');
  await page.waitForFunction(()=>state.workspace_tools.diagram.labels==='none');
  assert.equal(await page.locator('.diagram-label').evaluateAll(ns=>ns.filter(n=>getComputedStyle(n).visibility==='visible').length),0);
  await page.getByLabel('Separate parallel cables').uncheck();
  await page.waitForFunction(()=>!state.workspace_tools.diagram.routing);
  assert.equal((await page.locator('.diagram-cable').first().getAttribute('d')).split('L').length,2);
  await page.getByLabel('Separate parallel cables').check();
  await page.getByLabel('Interface label detail').selectOption('smart');
  await page.locator('#diagramOptions').getByRole('button',{name:'Close',exact:true}).click();
  await page.evaluate(()=>{setZoom(1);PacketTrackerWorkspace.selected.clear();});await page.keyboard.press('Escape');
  // An actual pointer drag updates the drawn cable before release, then saves its endpoint.
  const node=page.locator('.node[data-name="P1"]'),box=await node.boundingBox();
  const old=await page.locator('.diagram-edge[data-b="P1"] .diagram-cable').getAttribute('d');
  await page.mouse.move(box.x+25,box.y+15);await page.mouse.down();await page.mouse.move(box.x+85,box.y+35,{steps:3});
  assert.notEqual(await page.locator('.diagram-edge[data-b="P1"] .diagram-cable').getAttribute('d'),old);
  await page.mouse.up();await page.waitForFunction(()=>state.devices.P1.x===510);
  // Smaller screens still expose the control through the horizontally scrollable toolbar.
  for(const width of [1024,768]){await page.setViewportSize({width,height:768});await page.locator('#topologyDisplayBtn').click();assert(await page.locator('#diagramOptions').isVisible());await page.locator('#diagramOptions').getByRole('button',{name:'Close',exact:true}).click()}
  await page.setViewportSize({width:1440,height:900});await page.screenshot({path:process.env.PT_DIAGRAM_SCREENSHOT||'/tmp/pt-diagram.png'});
  for(const c of ['add switch S2 900 200','connect S1 fa0/5 S2 fa0/1','connect S2 fa0/2 S1 fa0/6','connect S1 fa0/7 S2 fa0/3'])await command(c);
  await page.evaluate(()=>fetchState());
  const paths=()=>page.locator('.diagram-edge').evaluateAll(gs=>gs.filter(g=>g.dataset.a==='S2'||g.dataset.b==='S2').map(g=>g.querySelector('.diagram-cable').getAttribute('d')).map(d=>{const v=d.match(/-?[\d.]+/g).map(Number);return [[v[0],v[1]],[v[2],v[3]]].sort((a,b)=>a[0]-b[0]||a[1]-b[1]).flat().join(',')}));
  assert.equal(new Set(await paths()).size,3,'Opposite-direction parallel links have distinct straight lanes');
  const s2=await page.locator('.node[data-name="S2"]').boundingBox();
  await page.mouse.move(s2.x+25,s2.y+15);await page.mouse.down();await page.mouse.move(s2.x+65,s2.y+45,{steps:3});
  assert.equal(new Set(await paths()).size,3,'Parallel lanes remain distinct during drag');
  await page.mouse.up();await page.waitForFunction(()=>state.devices.S2.x===940);
  await page.reload();await page.waitForFunction(()=>document.querySelectorAll('.diagram-edge').length===6);
  assert.equal(new Set(await paths()).size,3,'Parallel lanes survive reload');
  await page.locator('#topologyDisplayBtn').click();await page.getByRole('button',{name:'Collapse',exact:true}).click();
  await page.waitForFunction(()=>document.querySelectorAll('.diagram-edge').length===5);
  assert.equal(new Set(await paths()).size,3,'Collapsed groups retain distinct external cable lanes');
  assert.deepEqual(errors,[]);
  console.log('PASS: API-backed preferences, layout preview/cancel/apply/undo, configuration preservation, groups/reload/expand, focus, zoom, live cable dragging and responsive controls');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
