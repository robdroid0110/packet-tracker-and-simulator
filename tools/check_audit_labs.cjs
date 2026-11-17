/* Build labs first with tools/audit_networks.py. All browser state is isolated. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-lab-ui-')),ready=path.join(dir,'ready');
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try{
  for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1440,height:900}});
  const open=async(name)=>{const promise=page.waitForEvent('popup');await page.locator(`.node[data-name="${name}"]`).click();const child=await promise;await child.waitForLoadState('domcontentloaded');await child.locator('#dialogTabs').waitFor();return child};
  for(const [lab,count] of [['campus',16],['branch',11],['industrial',10]]){
   const file=path.resolve(process.env.AUDIT_LABS||'labs/audit',lab+'.json');
   await page.goto(url);
   const chooser=page.waitForEvent('filechooser');await page.locator('#openBtn').click();
   const dialog=page.waitForEvent('dialog');await(await chooser).setFiles(file);const confirmation=await dialog;if(confirmation.type()!=='confirm')throw Error(confirmation.message());await confirmation.accept();
   await page.waitForFunction(n=>document.querySelectorAll('.node').length===n,count);
   if(lab==='campus'){
    const pc=await open('PC1');await pc.locator('[data-tab="desktop"]').click();await pc.locator('[data-desk="browser"]').click();await pc.locator('#ptWebAddress').fill('http://campus.lab/');await pc.locator('#ptWebAddress').press('Enter');await pc.frameLocator('#ptWebFrame').getByText('Campus service works').waitFor();
    await pc.locator('[data-tab="desktop"]').click();await pc.locator('[data-desk="cmd"]').click();
    await pc.locator('#pcCmdIn').fill('ping 172.16.3.20');await pc.locator('#pcCmdIn').press('Enter');await pc.waitForFunction(()=>document.querySelector('#pcCmdOut').textContent.includes('PING success'));
    if(!await pc.locator('#pcCmdIn').evaluate(e=>e===document.activeElement))throw Error('PC command prompt loses keyboard focus after command');
    await pc.keyboard.type('ipconfig');await pc.keyboard.press('Enter');await pc.waitForFunction(()=>document.querySelector('#pcCmdOut').textContent.includes('ipconfig'));
    const r1=await open('R1'),r2=await open('R2');
    for(const child of [r1,r2]){if(await child.locator('#workspaceShell').isVisible())throw Error('Device popup includes whole project');await child.locator('[data-tab="cli"]').click();await child.locator('#deviceCliIn').fill('enable');await child.locator('#deviceCliIn').press('Enter');await child.waitForFunction(()=>document.querySelector('#deviceCliForm span').textContent.includes('#'))}
    await r1.close();await r2.close();await pc.close();
   }else if(lab==='branch'){
    await page.locator('[data-category="end"]').click();
    for(const [x,y] of [[700,80],[900,80]]){await page.locator('[data-model="pc-pt"]').click();await page.locator('#workspace').click({position:{x,y}})}
    await page.locator('.node[data-name="PC2"]').waitFor();
    await page.locator('[data-category="connections"]').click();await page.locator('[data-connection="auto"]').click({modifiers:['Control']});
    for(const name of ['PC1','PC2']){await page.locator(`.node[data-name="${name}"]`).click();await page.locator('.node[data-name="LAN"]').click();await page.waitForFunction(n=>state.links.some(l=>l.a_device===n||l.b_device===n),name)}
    await page.keyboard.press('Escape');
    const added=await open('PC1');await added.locator('[data-tab="desktop"]').click();await added.locator('[data-desk="ip"]').click();
    await added.locator('#ptIpv4Address').fill('10.20.0.90');await added.locator('#ptIpv4Mask').fill('255.255.255.0');await added.locator('#ptIpv4Gateway').fill('10.20.0.1');await added.locator('#ptIpApply').click();
    await added.locator('[data-tab="desktop"]').click();await added.locator('[data-desk="cmd"]').click();await added.locator('#pcCmdIn').fill('ping 203.0.113.10');await added.locator('#pcCmdIn').press('Enter');await added.waitForFunction(()=>document.querySelector('#pcCmdOut').textContent.includes('PING success'));await added.close();
    const pc=await open('Branch1');await pc.locator('[data-tab="desktop"]').click();await pc.locator('[data-desk="ip"]').click();await pc.locator('#ptIpv4Address').fill('10.20.0.91');await pc.locator('#ptIpApply').click();
    await pc.waitForFunction(()=>document.querySelector('#ptIpv4Address').value==='10.20.0.91');
    const state=await(await fetch(url+'/api/state')).json();if(state.devices.Branch1.interfaces.eth0.ip!=='10.20.0.91/24')throw Error('GUI IP setting did not reach backend');
    await pc.locator('[data-tab="desktop"]').click();await pc.locator('[data-desk="cmd"]').click();await pc.locator('#pcCmdIn').fill('ping 203.0.113.10');await pc.locator('#pcCmdIn').press('Enter');await pc.waitForFunction(()=>document.querySelector('#pcCmdOut').textContent.includes('PING success'));await pc.close();
   }else{
    const plc=await open('PLC');await plc.locator('[data-tab="attributes"]').click();await plc.getByText('alarm',{exact:false}).first().waitFor();await plc.close();
   }
   console.log('PASS GUI:',lab);
  }
 }finally{if(browser)await browser.close();server.kill('SIGTERM');await new Promise(r=>server.once('exit',r));fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
