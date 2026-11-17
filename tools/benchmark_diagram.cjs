/* PT_CANVAS_FIXTURE points to an isolated generated lab, never a live lab. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'pt-diagram-bench-')),ready=path.join(folder,'ready');
 fs.copyFileSync(process.env.PT_CANVAS_FIXTURE,path.join(folder,'lab.json'));
 const server=spawn('python3',['desktop.py','--server','--port','0','--state',path.join(folder,'lab.json'),'--ready-file',ready],{stdio:'ignore'});let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}});await page.goto(url);
  await page.waitForFunction(()=>document.querySelectorAll('.diagram-edge').length>0);
  const result=await page.evaluate(()=>{
   const time=fn=>{const t=performance.now();fn();return +(performance.now()-t).toFixed(2)};
   const cached=[],changed=[],drag=[];
   for(let i=0;i<6;i++)cached.push(time(()=>renderTopology()));
   for(let i=0;i<6;i++){state.devices.S0.x+=1;changed.push(time(()=>PacketTrackerDiagram.drag()))}
   for(let i=0;i<6;i++){state.devices.S0.x+=1;drag.push(time(()=>PacketTrackerDiagram.drag(['S0'])))}
   return {devices:Object.keys(state.devices).length,links:state.links.length,cached_full_render_ms:cached,changed_geometry_only_ms:changed,incident_drag_ms:drag};
  });console.log(JSON.stringify(result));
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(folder,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
