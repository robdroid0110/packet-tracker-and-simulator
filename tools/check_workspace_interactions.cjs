/* Run with PLAYWRIGHT_MODULE=/path/to/playwright-core node tools/check_workspace_interactions.cjs. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-pointer-check-')),ready=path.join(dir,'ready');
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||process.env.PYTHON||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(resolve=>setTimeout(resolve,50));
  if(!fs.existsSync(ready))throw Error('Test server did not start');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  for(const command of ['add router R1 200 150','add router R2 500 150']){
   const response=await fetch(url+'/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command})});
   const data=await response.json();if(!data.ok)throw Error(data.output);
  }
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}});await page.goto(url);
  const r1=page.locator('.node[data-name="R1"]');await r1.waitFor();
  await page.evaluate(()=>{window.savedFilter=document.querySelector('.sim-filters').firstElementChild});
  await page.waitForTimeout(1200);
  if(!await page.evaluate(()=>savedFilter===document.querySelector('.sim-filters').firstElementChild))throw Error('Idle simulation rebuilt its controls');
  const a=await r1.boundingBox();let popup=page.waitForEvent('popup');
  await page.mouse.move(a.x+20,a.y+20);await page.mouse.down();await page.mouse.move(a.x+22,a.y+21);await page.mouse.up();
  let child=await popup;await child.waitForLoadState('domcontentloaded');
  if(await child.locator('#workspaceShell').isVisible())throw Error('Device popup exposes project');await child.close();
  let data=await(await fetch(url+'/api/state')).json();if(data.devices.R1.x!==200)throw Error('Click jitter moved router');
  let opened=0;const onPopup=()=>opened++;page.on('popup',onPopup);
  await page.evaluate(()=>{window.nativeImageDrags=0;document.addEventListener('dragstart',()=>nativeImageDrags++)});
  await page.mouse.move(a.x+44,a.y+20);await page.mouse.down();await page.mouse.move(a.x+124,a.y+80);await page.mouse.up();
  await page.waitForTimeout(200);data=await(await fetch(url+'/api/state')).json();
  if(opened||Math.abs(data.devices.R1.x-280)>1||Math.abs(data.devices.R1.y-210)>1)throw Error('Immediate click-and-drag failed');
  if(await page.evaluate(()=>nativeImageDrags))throw Error('Native image dragging interfered with the device');
  const start=await r1.boundingBox(),b=await page.locator('.node[data-name="R2"]').boundingBox();
  await page.mouse.move(start.x+20,start.y+20);await page.mouse.down();await page.waitForTimeout(220);await page.mouse.move(b.x+20,b.y+20,{steps:8});await page.mouse.up();
  await page.waitForFunction(()=>!window.ptPointerActive);await page.waitForTimeout(200);
  data=await(await fetch(url+'/api/state')).json();if(opened||data.devices.R1.x===200)throw Error('Hold-drag opened a window or failed to move');page.off('popup',onPopup);
  popup=page.waitForEvent('popup');await page.locator('.node[data-name="R2"]').click();child=await popup;await child.close();
  await page.evaluate(async()=>{await command('move R1 320 280',false);setZoom(1.5);document.querySelector('.workspace-scrollbar.horizontal').scrollLeft-=70});await page.waitForTimeout(100);
  data=await(await fetch(url+'/api/state')).json();
  const before=data.devices.R1,scaled=await r1.boundingBox();
  page.on('popup',onPopup);await page.mouse.move(scaled.x+20,scaled.y+20);await page.mouse.down();await page.mouse.move(scaled.x+110,scaled.y+65);await page.mouse.up();await page.waitForTimeout(200);
  data=await(await fetch(url+'/api/state')).json();if(opened||Math.abs(data.devices.R1.x-before.x-60)>1||Math.abs(data.devices.R1.y-before.y-30)>1)throw Error('Zoomed, scrolled drag failed');
  console.log('PASS: click jitter opens only; immediate and held drags move only; zoomed/scrolled drag preserves coordinates; next click opens; idle controls stay mounted');
 }finally{
  if(browser)await browser.close();server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));fs.rmSync(dir,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
