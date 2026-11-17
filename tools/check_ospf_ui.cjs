/* Isolated area-aware OSPF GUI/API integration check. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-ospf-ui-')),ready=path.join(dir,'ready');
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  if(!fs.existsSync(ready))throw Error('server did not start');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  const command=async text=>{const r=await fetch(url+'/api/command',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({command:text})});const data=await r.json();if(!data.ok)throw Error(text+': '+data.output);return data};
  for(const text of ['add router R1 150 120','add router R2 400 120','add pc PC 650 120','connect R1 g0/0 R2 g0/0','connect R2 g0/1 PC eth0','ip R1 g0/0 10.0.0.1/30','ip R2 g0/0 10.0.0.2/30','ip R2 g0/1 192.168.2.1/24','ip PC eth0 192.168.2.2/24','gateway PC 192.168.2.1'])await command(text);
  const read=async name=>(await(await fetch(url+'/api/ospf?device='+encodeURIComponent(name))).json());
  browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}});await page.goto(url);await page.locator('.node[data-name="R1"]').waitFor();
  const open=async name=>{const wait=page.waitForEvent('popup');await page.locator(`.node[data-name="${name}"]`).click();const child=await wait;await child.locator('#dialogTabs [data-tab="config"]').click();await child.locator('[data-pt-nav="ospf"]').click();return child};
  const r1=await open('R1');
  const configure=async (p,network,area)=>{await p.locator('#ptOspfNetwork').fill(network);await p.locator('#ptOspfArea').fill(String(area));await p.locator('#ptOspfEnable').click();await p.waitForFunction(({network,area})=>state.devices[selected]?.ospf_areas?.[network]===area,{network,area});await p.locator('[data-ospf-remove="'+network+'"]').waitFor()};
  await configure(r1,'10.0.0.0/30',7);
  if((await read('R1')).networks[0].area!==7)throw Error('GUI area did not reach backend');
  await command('ospf R2 enable 10.0.0.0/30 area 8');
  if((await read('R1')).neighbors.length)throw Error('mismatched areas became neighbors');
  const r2=await open('R2');await configure(r2,'10.0.0.0/30',7);await configure(r2,'192.168.2.0/24',7);
  await r2.waitForFunction(()=>document.querySelector('#ptOspfNeighbors')?.textContent.includes('R1'));
  if((await read('R1')).neighbors[0]?.area!==7)throw Error('matching areas did not become neighbors');
  if(!(await command('ping R1 192.168.2.2')).output.includes('PING success'))throw Error('OSPF route did not forward');
  await r2.locator('[data-ospf-remove="10.0.0.0/30"]').click();
  await r2.waitForFunction(()=>!document.querySelector('[data-ospf-remove="10.0.0.0/30"]'));
  if((await read('R1')).neighbors.length)throw Error('removing network did not withdraw neighbor');
  await command('undo');if((await read('R1')).neighbors[0]?.area!==7)throw Error('undo did not restore neighbor');
  await r1.locator('#ptOspfDisable').click();await r1.waitForFunction(()=>document.querySelector('.pt-doc-section strong')?.textContent==='Disabled');
  if((await read('R1')).enabled)throw Error('GUI did not disable OSPF');
  await r1.locator('#ptOspfEnable').click();await r1.waitForFunction(()=>document.querySelector('.pt-doc-section strong')?.textContent==='Enabled');
  if((await read('R1')).networks[0]?.area!==7)throw Error('re-enabling did not preserve area');
  const running=(await command('ios R2 show running-config')).output;
  if(!running.includes('network 10.0.0.0 0.0.0.3 area 7'))throw Error('IOS omitted area configuration');
  await r1.close();await r2.close();console.log('PASS: OSPF GUI config, area mismatch/match, neighbor inspection, ping, remove/undo, disable/enable, and IOS output');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(error=>{console.error(error);process.exitCode=1});
