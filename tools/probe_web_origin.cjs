/* Verify cross-origin mutation against disposable state only. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path'),http=require('http');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-origin-probe-')),ready=path.join(dir,'ready');
 const server=spawn('python3',['desktop.py','--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 const other=http.createServer((req,res)=>{res.writeHead(200,{'Content-Type':'text/html'});res.end('<!doctype html><title>Untrusted origin probe</title>')});
 let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  const port=JSON.parse(fs.readFileSync(ready)).port;
  await new Promise(r=>other.listen(0,'127.0.0.1',r));const origin='http://127.0.0.1:'+other.address().port;
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage();await page.goto(origin);
  const result=await page.evaluate(async target=>{
   try{const r=await fetch(target+'/api/command',{method:'POST',mode:'no-cors',headers:{'content-type':'text/plain'},body:JSON.stringify({command:'add pc CrossOriginProbe'})});return {response_type:r.type}}
   catch(e){return {error:String(e)}}
  },'http://127.0.0.1:'+port);
  await page.route('https://attacker.example/**',route=>route.fulfill({status:200,contentType:'text/html',body:'<!doctype html><title>synthetic remote page</title>'}));
  await page.goto('https://attacker.example/');
  const remoteResult=await page.evaluate(async target=>{
   try{const r=await fetch(target+'/api/command',{method:'POST',mode:'no-cors',headers:{'content-type':'text/plain'},body:JSON.stringify({command:'add pc RemoteOriginProbe'})});return {response_type:r.type}}
   catch(e){return {error:String(e)}}
  },'http://127.0.0.1:'+port);
  const state=await(await fetch('http://127.0.0.1:'+port+'/api/state')).json();
  const report={case:'cross_origin_page_mutation',target:'isolated localhost server',
   localhost:{source_origin:origin,fetch:result,device_created:!!state.devices.CrossOriginProbe},
   synthetic_https:{source_origin:'https://attacker.example',fetch:remoteResult,device_created:!!state.devices.RemoteOriginProbe},
   scope:'Chromium no-cors text/plain POST; HTTPS page content intercepted by Playwright; other browser privacy and network settings may differ'};
  fs.writeFileSync('research/performance/web_origin.json',JSON.stringify(report,null,2));console.log(JSON.stringify(report));
 }finally{if(browser)await browser.close();other.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
