/* Simulation sidebar: real packet workflows and responsive layout in a temporary lab. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-sim-panel-')),ready=path.join(dir,'ready');
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try {
  for(let i=0;i<600&&!fs.existsSync(ready);i++){if(server.exitCode!==null)throw Error('Isolated server exited');await new Promise(r=>setTimeout(r,50))}
  if(!fs.existsSync(ready))throw Error('Isolated server did not start');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  const post=async(endpoint,body)=>{const data=await(await fetch(url+endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})).json();if(!data.ok)throw Error(JSON.stringify(data));return data};
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1969,height:1080}}),errors=[];page.setDefaultTimeout(8000);
  page.on('pageerror',e=>errors.push(e.message));await page.goto(url);await page.locator('#simLegendBtn').waitFor({state:'attached'});
  await page.locator('#eventListBtn').click();await page.locator('#simulationPanel .sim-empty').waitFor();
  for(const [width,height] of [[1969,1080],[1920,900],[1440,900],[1024,768],[800,600],[375,812],[320,568]])for(const scale of [1,1.5]) {
   await page.setViewportSize({width,height});await page.evaluate(s=>document.documentElement.style.setProperty('--pt-global-scale',s),String(scale));
   await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   const failures=await page.evaluate(scale=>{
    const panel=document.querySelector('#simulationPanel'),p=panel.getBoundingClientRect(),w=document.querySelector('#workspace').getBoundingClientRect(),fail=[];
    if(p.left<w.left-1||p.right>w.right+1||p.top<w.top-1||p.bottom>w.bottom+1)fail.push('panel outside workspace');
    if(panel.scrollWidth>panel.clientWidth+1)fail.push('horizontal panel overflow');
    for(const n of panel.querySelectorAll('button,input,label,.sim-filter-title,.sim-filter-summary,.sim-filter-actions')) {
     if(!n.getClientRects().length)continue;const r=n.getBoundingClientRect();
     if(r.left<p.left-1||r.right>p.right+1)fail.push('clipped '+(n.id||n.className||n.tagName));
    }
    const title=panel.querySelector('.sim-filter-title').getBoundingClientRect(),summary=panel.querySelector('.sim-filter-summary').getBoundingClientRect(),actions=panel.querySelector('.sim-filter-actions').getBoundingClientRect();
    if(title.bottom>summary.top+1||summary.bottom>actions.top+1)fail.push('filter sections overlap');
    if(!document.body.classList.contains('pt-compact-layout'))for(const [id,h] of [['menuBar',24],['mainToolbar',39],['toolRail',39],['workspaceTabs',35]])if(Math.abs(document.getElementById(id).getBoundingClientRect().height-h*scale)>1)fail.push('top row size changed: '+id);
    return fail;
   },scale);
   if(failures.length)throw Error(width+'x'+height+' / '+scale+': '+failures.join('; '));
   if(scale===1&&[1969,800,375].includes(width))await page.screenshot({path:'/tmp/packettracker-simulation-'+width+'.png'});
  }
  // Ensure the last controls and the close button can both be reached in a short, enlarged window.
  await page.locator('#simLegendBtn').scrollIntoViewIfNeeded();await page.locator('#simLegendBtn').click();await page.locator('#ptPduInspector').getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#simPanelClose').scrollIntoViewIfNeeded();await page.locator('#simPanelClose').click();await page.locator('#simulationPanel').waitFor({state:'hidden'});
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>document.documentElement.style.setProperty('--pt-global-scale','1'));
  for(const command of ['add pc A 150 100','add pc B 350 100','connect A eth0 B eth0','ip A eth0 192.0.2.1/24','ip B eth0 192.0.2.2/24'])await post('/api/command',{command});
  await page.evaluate(()=>fetchState());await page.locator('#simulationBtn').click();await page.waitForFunction(()=>state.simulation.mode==='simulation');
  await post('/api/simulation/action',{action:'pdu_add',source:'A',destination:'B',protocol:'ICMP'});await page.evaluate(()=>fetchState());
  const action=async(selector,kind)=>{const response=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action===kind);await page.locator(selector).click();const value=await(await response).json();if(!value.ok)throw Error(selector+' failed');return value};
  await action('[data-sim-step="forward"]','step');await page.locator('#simulationEvents .sim-event-row').first().waitFor();
  const contrast=await page.locator('#simulationEvents .sim-event-row').first().evaluate(row=>{
   const style=getComputedStyle(row),rgb=text=>text.match(/[\d.]+/g).slice(0,3).map(Number);
   const luminance=color=>rgb(color).map(v=>{const s=v/255;return s<=.04045?s/12.92:((s+.055)/1.055)**2.4}).reduce((sum,v,i)=>sum+v*[.2126,.7152,.0722][i],0);
   const a=luminance(style.color),b=luminance(style.backgroundColor);return (Math.max(a,b)+.05)/(Math.min(a,b)+.05);
  });if(contrast<4.5)throw Error('Captured row text contrast too low: '+contrast);
  if(!Number(await page.locator('#captureCount').innerText()))throw Error('Capture counter did not update');
  await page.locator('#simulationEvents .sim-event-row').first().click();await page.locator('#ptPduInspector').getByRole('tab',{name:'OSI Model',exact:true}).click();await page.locator('#ptPduInspector').getByRole('button',{name:'Close',exact:true}).click();
  await page.locator('#editSimFiltersBtn').focus();await page.keyboard.press('Enter');if(await page.locator('#editSimFiltersBtn').getAttribute('aria-expanded')!=='true')throw Error('Filter editor state missing');
  const check=page.locator('#simProtocolFilters label').filter({hasText:/^ICMP$/}).locator('input');
  const preference=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action==='preferences');await check.uncheck();await preference;await page.waitForFunction(()=>!state.simulation.filters.includes('ICMP'));
  if(/\bICMP\b/.test(await page.locator('.sim-filter-summary').innerText()))throw Error('Filter summary stale');
  await page.locator('#editSimFiltersBtn').click();await page.locator('#simProtocolFilters').waitFor({state:'hidden'});
  await action('#allSimFiltersBtn','preferences');await page.locator('#simulationEvents .sim-empty').waitFor();if(!(await page.locator('.sim-filter-summary').innerText()).includes('No protocols'))throw Error('Empty filter state missing');
  for(let i=0;i<20&&await page.evaluate(()=>Object.values(state.simulation.pdus)[0].status!=='Successful');i++)await action('[data-sim-step="forward"]','step');
  if(!await page.evaluate(()=>Object.values(state.simulation.pdus)[0].status==='Successful'))throw Error('Filtering changed PDU delivery');
  await action('#allSimFiltersBtn','preferences');await page.locator('#simulationEvents .sim-event-row').first().waitFor();
  await page.evaluate(()=>fetchState());await page.locator('#simulationEvents .sim-event-row').first().waitFor();
  await page.locator('#simulationPanel').screenshot({path:'/tmp/packettracker-simulation-events.png'});
  await action('[data-sim-step="back"]','back');
  await action('[data-sim-step="play"]','play');await page.waitForFunction(()=>state.simulation.playing);if(await page.locator('[data-sim-step="play"]').getAttribute('aria-label')!=='Pause')throw Error('Panel pause indicator missing');
  await action('[data-sim-step="play"]','play');await page.waitForFunction(()=>!state.simulation.playing);
  const delay=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.constant_delay===false);await page.locator('.sim-reset-row input').uncheck();await delay;
  const speed=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.speed===75);await page.locator('.sim-speed').fill('75');await speed;
  await page.waitForFunction(()=>state.simulation.speed===75&&!state.simulation.constant_delay);
  await action('#resetSimulationBtn','reset');await page.waitForFunction(()=>document.querySelector('#captureCount').textContent==='0');await page.locator('#simulationEvents .sim-empty').waitFor();
  await page.emulateMedia({forcedColors:'active'});await page.keyboard.press('Tab');await page.locator('#editSimFiltersBtn').focus();if(await page.locator('#editSimFiltersBtn').evaluate(n=>getComputedStyle(n).outlineStyle)==='none')throw Error('Forced-colors focus missing');
  if(errors.length)throw Error(errors.join('; '));
  console.log('PASS: top row proportions, 320–1969px sidebar layout at 1x/1.5x, scrolling, close, real packet capture/inspection, filtering, playback, preferences, reset and legend');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
