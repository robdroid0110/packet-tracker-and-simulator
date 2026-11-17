const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-time-controls-')),ready=path.join(dir,'ready');
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++){if(server.exitCode!==null)throw Error('Test server exited');await new Promise(r=>setTimeout(r,50))}
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1920,height:900}}),errors=[];page.on('pageerror',e=>errors.push(e.message));await page.goto(url);
  await page.locator('#powerCycleBtn').waitFor();
  const controls=['resetTimeBtn','stepBackBtn','playBtn','stepForwardBtn','powerCycleBtn','fastForwardBtn','eventListBtn','realtimeBtn','simulationBtn'];
  for(const width of [1920,1440,1024,800])for(const scale of [1,1.5]){
   await page.setViewportSize({width,height:900});await page.evaluate(s=>document.documentElement.style.setProperty('--pt-global-scale',s),String(scale));
   const failure=await page.evaluate(ids=>{
    const strip=document.querySelector('#timeStrip').getBoundingClientRect();
    for(const id of ids){const b=document.getElementById(id),r=b.getBoundingClientRect();if(r.left<strip.left||r.right>strip.right+1||r.top<strip.top||r.bottom>strip.bottom+1)return id+' clipped';if(!b.querySelector('svg use'))return id+' missing vector icon'}
    const play=document.querySelector('.play-controls');if(play.scrollWidth>play.clientWidth+1)return 'Playback scrolling';
    return null;
   },controls);if(failure)throw Error(width+'px / '+scale+': '+failure);
  }
  await page.setViewportSize({width:1920,height:900});await page.evaluate(()=>document.documentElement.style.setProperty('--pt-global-scale','1'));
  const before=await page.locator('#stepBackBtn').boundingBox();await page.evaluate(()=>document.querySelector('#clock').textContent='9999:59:59.999');const after=await page.locator('#stepBackBtn').boundingBox();if(before.x!==after.x)throw Error('Clock pushed playback buttons');
  await page.locator('#timeStrip').screenshot({path:'/tmp/packettracker-time-controls.png'});
  await page.locator('#simulationBtn').click();await page.waitForFunction(()=>state.simulation.mode==='simulation');
  if(await page.locator('#simulationBtn').getAttribute('aria-pressed')!=='true')throw Error('Mode state not reflected');
  const action=async(id,kind)=>{const response=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action===kind);await page.locator('#'+id).click();if(!(await(await response).json()).ok)throw Error(id+' failed')};
  await action('stepForwardBtn','step');await action('stepBackBtn','back');await action('fastForwardBtn','step');await action('playBtn','play');
  await page.locator('#realtimeBtn').click();await page.waitForFunction(()=>state.simulation.mode==='realtime');
  const hidden=await page.locator('#simulationPanel').evaluate(e=>e.classList.contains('hidden'));await page.locator('#eventListBtn').click();if(hidden===await page.locator('#simulationPanel').evaluate(e=>e.classList.contains('hidden')))throw Error('Event List did not toggle');
  page.once('dialog',d=>d.dismiss());await page.locator('#powerCycleBtn').click();
  page.once('dialog',d=>d.accept());const power=page.waitForResponse(r=>r.url().endsWith('/api/command')&&r.request().postDataJSON()?.command==='power-cycle');await page.locator('#powerCycleBtn').click();if(!(await(await power).json()).ok)throw Error('Power cycle failed');
  await page.emulateMedia({forcedColors:'active'});await page.keyboard.press('Tab');await page.locator('#playBtn').focus();if(await page.locator('#playBtn').evaluate(e=>getComputedStyle(e).outlineStyle)==='none')throw Error('Missing focus outline');
  if(errors.length)throw Error(errors.join('; '));console.log('PASS: control bar layout, stable clock, vector icons, modes, playback, event list and power-cycle confirmation');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
