/* Real browser regression for split-screen, narrow, short and desktop windows. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'/tmp/pts-playwright-tests/node_modules/playwright-core');
const {spawn,spawnSync}=require('child_process');
const fs=require('fs'),path=require('path'),os=require('os'),assert=require('assert/strict');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pts-responsive-'));
 const ready=path.join(dir,'ready');
 // Generate the test fixture locally; never publish user-saved lab files.
 const fixture=String.raw`import sys
from netsim.model import NetworkLab
n=NetworkLab()
for kind,name,x,y in [
 ('router','R1',230,90),('router','R2',620,90),('router','R3',440,220),
 ('switch','S1',150,320),('switch','S2',735,320),('switch','S3',445,355),
 ('pc','P1',70,450),('pc','P2',240,450),('pc','P3',650,450),
 ('pc','P4',810,450),('pc','P5',360,480),('pc','P6',530,480)]:
 n.add_device(kind,name,x,y)
for a,ai,b,bi in [
 ('R1','g0/0','R2','g0/0'),('R2','g0/1','R3','g0/0'),
 ('R3','g0/1','R1','g0/1'),('R1','g0/2','S1','g0/1'),
 ('R2','g0/2','S2','g0/1'),('R3','g0/2','S3','g0/1'),
 ('P1','eth0','S1','fa0/1'),('P2','eth0','S1','fa0/2'),
 ('P3','eth0','S2','fa0/1'),('P4','eth0','S2','fa0/2'),
 ('P5','eth0','S3','fa0/1'),('P6','eth0','S3','fa0/2')]:
 n.connect(a,ai,b,bi)
n.save(sys.argv[1])`;
 const created=spawnSync('python3',['-c',fixture,path.join(dir,'lab.json')],
                         {cwd:process.cwd(),encoding:'utf8'});
 assert.equal(created.status,0,'Synthetic fixture generation: '+created.stderr);
 const proc=spawn('python3',['desktop.py','--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<400&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  assert(fs.existsSync(ready),'isolated backend starts');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1600,height:900}});
  page.setDefaultTimeout(11000);
  const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(url,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelectorAll('.diagram-edge').length>=10);
  const sizes=[[1920,1080],[1600,900],[1280,800],[1100,700],[1060,768],
   [1024,768],[900,700],[840,360],[740,750],[675,750],
   [600,600],[430,780],[375,667],[320,568],[1366,500],[700,400]];
  async function measure(){
   return page.evaluate(()=>{
    const box=selector=>{const n=document.querySelector(selector);if(!n)return null;const r=n.getBoundingClientRect();return {x:r.x,y:r.y,w:r.width,h:r.height,visible:getComputedStyle(n).display!=='none'}};
    const ww=innerWidth,hh=innerHeight;
    return{size:[ww,hh],compact:document.body.classList.contains('pt-compact-layout'),
      canvasFocus:document.body.classList.contains('pt-compact-canvas'),
      work:box('#workspace'),dock:box('#bottomDock'),time:box('#timeStrip'),
      palette:box('#paletteRow'),actions:box('.pt-compact-actions'),
      right:box('#rightDock'),footer:box('#statusBar'),
      zoom:document.querySelector('#zoomLabel')?.textContent,
      nodes:document.querySelectorAll('.node').length,
      bodyOverflow:document.body.scrollWidth>ww+3,
      shellVisibility:document.querySelector('#shellPane')?getComputedStyle(document.querySelector('#shellPane')).visibility:'none'
    };
   });
  }
  for(const [w,h] of sizes){
   await page.setViewportSize({width:w,height:h});
   await page.waitForTimeout(190);
   const m=await measure(),isCompact=w<=1060||h<=640;
   assert.equal(m.compact,isCompact,'compact breakpoint at '+w+'x'+h);
   assert.equal(m.nodes,12,'topology devices preserved');
   assert(!m.bodyOverflow,'body horizontal overflow at '+w+'x'+h);
   if(isCompact){
    const minCanvas=h>=650?Math.max(200,h*.39):Math.max(140,h*.35);
    assert(m.work.h>=minCanvas,'canvas too small at '+w+'x'+h+': '+m.work.h);
    assert(m.dock.h<=145,'dock too tall at '+w+'x'+h+': '+m.dock.h);
    assert(m.actions.visible,'compact controls visible');
    assert(m.shellVisibility==='hidden','closed shell must be hidden');
   }else{
    assert(m.work.h>h*.32,'desktop canvas too short at '+w+'x'+h);
    assert(!m.actions.visible,'compact buttons hidden in desktop');
    assert(!(await page.locator('#ptCompactClosePdu').isVisible()),'desktop view must not show compact PDU close button');
   }
   console.log('RESPONSIVE_OK',w+'x'+h,'canvas',Math.round(m.work.h),'dock',Math.round(m.dock.h),'zoom',m.zoom);
   if(w===675&&h===750)await page.screenshot({path:'/tmp/pts-responsive-fixed-675.png'});
  }
  await page.setViewportSize({width:675,height:750});
  await page.waitForTimeout(250);
  const initial=await measure();
  await page.getByRole('button',{name:'Maximize the topology canvas'}).click();
  await page.waitForTimeout(150);
  const focus=await measure();
  assert(focus.canvasFocus,'Canvas mode toggled');
  assert(focus.work.h>initial.work.h+110,'Canvas mode adds canvas height');
  assert(!focus.dock.visible,'Canvas mode hides dock');
  await page.getByRole('button',{name:'Show device categories and palette'}).click();
  await page.waitForTimeout(140);
  const restored=await measure();
  assert(!restored.canvasFocus&&restored.dock.visible,'Devices mode restores palette');
  await page.getByRole('button',{name:'Show packet event and scenario panels'}).click();
  await page.waitForTimeout(100);
  const expanded=await measure();
  assert(expanded.right.visible&&expanded.right.w>=500&&expanded.right.h>=210,'PDU panels accessible');
  assert(await page.locator('#scenarioPane').isVisible(),'PDU scenario accessible');
  assert(await page.locator('#pduPane').isVisible(),'PDU list accessible');
  await page.getByRole('button',{name:'Close packet event panels'}).click();
  assert(!(await measure()).right.visible,'PDU panels close');
  // Fit restores automatic framing after a user zooms the topology.
  const originalZoom=await page.evaluate(()=>zoom);
  await page.locator('#zoomIn').click();
  const zoomed=await page.evaluate(()=>zoom);
  assert(zoomed>originalZoom,'user zoom should increase the canvas scale');
  await page.getByRole('button',{name:'Fit the entire topology in the canvas'}).click();
  await page.waitForTimeout(130);
  assert((await page.evaluate(()=>zoom))<zoomed,'Fit restores adaptive canvas scale');
  // Honour the pre-existing hide-dock preference without deleting controls.
  await page.evaluate(()=>document.body.classList.add('pt-hide-bottom'));
  await page.waitForTimeout(90);
  assert(!(await measure()).dock.visible,'saved hide-dock preference respected');
  await page.evaluate(()=>document.body.classList.remove('pt-hide-bottom'));
  await page.waitForTimeout(90);
  assert((await measure()).dock.visible,'dock returns after preference is disabled');
  await page.locator('.category[data-category="end"]').click();
  assert(await page.locator('#deviceTray .palette-device').count()>0,'end device tray remains functional');
  await page.locator('.category[data-category="network"]').click();
  await page.getByRole('button',{name:'Show packet event and scenario panels'}).click();
  await page.keyboard.press('Escape');
  assert(!(await measure()).right.visible,'escape closes packet panel');
  // Test large-text user preferences.
  for(const scale of [1,1.25,1.5]){
   await page.evaluate(x=>document.documentElement.style.setProperty('--pt-global-scale',String(x)),scale);
   await page.waitForTimeout(140);
   const m=await measure();
   assert(m.work.h>300,'large type must not remove canvas');
   assert(m.dock.h<=145,'large type must not increase dock height');
   console.log('SCALE_OK',scale,'canvas',Math.round(m.work.h));
  }
  await page.evaluate(()=>document.documentElement.style.removeProperty('--pt-global-scale'));
  await page.setViewportSize({width:1600,height:900});
  await page.waitForTimeout(140);
  assert(!(await measure()).compact,'desktop restores naturally');
  assert.deepEqual(errors,[],'no browser JS errors');
  console.log('PASS: responsive viewports, controls, canvas focus, PDU drawer, device palette, keyboard escape, large-font modes');
 }finally{
  if(browser)await browser.close();
  if(proc.exitCode===null){proc.kill('SIGTERM');await new Promise(resolve=>proc.once('exit',resolve))}
  fs.rmSync(dir,{recursive:true,force:true});
 }
})().catch(e=>{console.error('RESPONSIVE_TEST_FAILED:',e.stack||e);process.exitCode=1});
