/* Isolated browser layout checks; see DESKTOP_APPLICATIONS.md for dependencies. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-layout-')),ready=path.join(dir,'ready'),executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||process.env.PYTHON||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));if(!fs.existsSync(ready))throw Error('Test server did not start');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  await fetch(url+'/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command:'add router R1 200 150'})});
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage();await page.goto(url);await page.locator('.node[data-name="R1"]').waitFor();
  for(const width of [1440,1024,800])for(const scale of [1,1.5]){
   await page.setViewportSize({width,height:900});await page.evaluate(scale=>document.documentElement.style.setProperty('--pt-global-scale',scale),String(scale));
   const overlap=await page.evaluate(()=>{const a=document.querySelector('#timeStrip .play-controls').getBoundingClientRect(),b=document.querySelector('#timeStrip .mode-toggle').getBoundingClientRect();return a.left<b.right&&a.right>b.left&&a.top<b.bottom&&a.bottom>b.top});
   if(overlap)throw Error(`Playback controls overlap at ${width}px / ${scale} scale`);
  }
  const device=await browser.newPage({viewport:{width:700,height:550}});await device.goto(url+'/?device=R1');await device.locator('#dialogTabs [data-tab="cli"]').click();await device.waitForFunction(()=>document.activeElement?.id==='deviceCliIn');
  const terminal=await device.locator('#deviceCliScreen').boundingBox(),body=await device.locator('#dialogBody').boundingBox();if(Math.abs(terminal.height-body.height)>2)throw Error('Terminal does not fill device window');
  await device.keyboard.type('enable');await device.keyboard.press('Enter');await device.waitForFunction(()=>document.querySelector('#deviceCliForm span')?.textContent.includes('R1#'));await device.waitForFunction(()=>document.activeElement?.id==='deviceCliIn');
  const fallback=await browser.newPage();await fallback.route('**/vendor/**',route=>route.abort());await fallback.goto(url);await fallback.waitForFunction(()=>document.querySelector('#newBtn img')?.naturalWidth>0);const chooser=fallback.waitForEvent('filechooser');await fallback.locator('#openBtn').click();await chooser;
  console.log('PASS: no control overlap at 800/1024/1440px and 1x/1.5x scale; full-height CLI retains prompt/focus; Open works with original bundled icons');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
