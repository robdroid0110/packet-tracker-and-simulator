/* Large-lab keyboard regression using an isolated copy of a generated fixture. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');
(async () => {
 const fixture=process.env.PT_CANVAS_FIXTURE || '/tmp/packet-tracker-scale-fixtures/18.json';
 const folder=fs.mkdtempSync(path.join(os.tmpdir(),'pt-keyboard-scale-')),ready=path.join(folder,'ready.json');
 const expected=Object.keys(JSON.parse(fs.readFileSync(fixture)).devices).length;
 fs.copyFileSync(fixture,path.join(folder,'lab.json'));
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(folder,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++){
   if(server.exitCode!==null)throw Error('Isolated server exited');
   await new Promise(resolve=>setTimeout(resolve,50));
  }
  if(!fs.existsSync(ready))throw Error('Isolated server did not start');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.goto(url);
  await page.waitForFunction(count=>document.querySelectorAll('#nodes .node[role="button"]').length===count,expected);
  if(await page.locator('#nodes .node[tabindex="0"]').count()!==1)throw Error('Expected exactly one device Tab stop');
  await page.keyboard.press('Shift+D');
  const start=performance.now();
  for(let i=0;i<30;i++)await page.keyboard.press('Control+ArrowRight');
  const elapsed=performance.now()-start;
  const focused=await page.evaluate(()=>document.activeElement?.dataset.name);
  if(!focused)throw Error('Keyboard navigation lost focus');
  const before=await page.evaluate(name=>state.devices[name].x,focused);
  await page.keyboard.press('Shift+ArrowRight');
  await page.waitForFunction(({name,x})=>state.devices[name].x===x+10,{name:focused,x:before});
  const actual=await(await fetch(url+'/api/state')).json();
  if(actual.devices[focused].x!==before+10)throw Error('Keyboard move was not saved');
  if(await page.evaluate(()=>document.activeElement?.dataset.name)!==focused)throw Error('Focus lost after large-lab edit');
  if(errors.length)throw Error('Browser errors: '+errors.join('; '));
  console.log('PASS: '+expected+'-device keyboard traversal, saved movement and focus; 30 key presses '+elapsed.toFixed(1)+' ms');
 }finally{
  if(browser)await browser.close();
  if(server.exitCode===null){server.kill('SIGTERM');await new Promise(resolve=>server.once('exit',resolve));}
  fs.rmSync(folder,{recursive:true,force:true});
 }
})().catch(error=>{console.error(error);process.exitCode=1});
