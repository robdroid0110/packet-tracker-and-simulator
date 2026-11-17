/* Responsive palette/PDU workflows against an isolated temporary lab. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-bottom-dock-')),ready=path.join(dir,'ready');
 const executable=process.env.PACKET_TRACKER_EXECUTABLE;
 const server=spawn(executable||'python3',[...(executable?[]:['desktop.py']),'--server','--port','0','--state',path.join(dir,'lab.json'),'--ready-file',ready],{stdio:'ignore'});
 let browser;
 try {
  for(let i=0;i<600&&!fs.existsSync(ready);i++){if(server.exitCode!==null)throw Error('Isolated server exited');await new Promise(r=>setTimeout(r,50))}
  if(!fs.existsSync(ready))throw Error('Isolated server did not start');
  const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
  const post=async(endpoint,body)=>{const data=await(await fetch(url+endpoint,{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify(body)})).json();if(!data.ok)throw Error(JSON.stringify(data));return data};
  browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
  const page=await browser.newPage({viewport:{width:1920,height:1080}}),errors=[];
  page.on('pageerror',e=>errors.push(e.message));await page.goto(url);await page.locator('#deviceTray [data-model]').first().waitFor();
  const geometry=[];
  for(const [width,height] of [[2172,1080],[1920,1080],[1440,900],[1280,720],[1024,768],[800,600],[600,800],[375,812],[320,568]])for(const scale of [1,1.5]) {
   await page.setViewportSize({width,height});await page.evaluate(s=>document.documentElement.style.setProperty('--pt-global-scale',s),String(scale));
   // Wait for ResizeObserver and subsequent grid layout, without a timing-based sleep.
   await page.evaluate(()=>new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r))));
   const result=await page.evaluate(()=>{
    const rect=id=>document.getElementById(id).getBoundingClientRect(),dock=rect('bottomDock'),row=rect('paletteRow'),status=rect('statusBar'),time=rect('timeStrip');
    const failures=[];
    if(dock.left<0||dock.right>innerWidth+1||status.bottom>innerHeight+1)failures.push('dock outside viewport');
    if(row.top<time.bottom-1||status.top<dock.bottom-1)failures.push('bars overlap');
    if(document.getElementById('paletteRow').scrollWidth>document.getElementById('paletteRow').clientWidth+1)failures.push('horizontal dock overflow');
    if(rect('workspace').height<60)failures.push('no usable canvas height');
    for(const node of document.querySelectorAll('#timeStrip button')){const r=node.getBoundingClientRect();if(r.left<time.left-1||r.right>time.right+1||r.top<time.top-1||r.bottom>time.bottom+1)failures.push('time control clipped: '+node.id)}
    if(row.height<90)failures.push('palette scroll area collapsed');
    for(const id of ['categoryColumn','subPalette','rightDock']){const r=rect(id);if(r.left<row.left-1||r.right>row.right+1)failures.push(id+' clipped horizontally')}
    const scenario=document.getElementById('scenarioPane');
    for(const node of scenario.querySelectorAll('button,select')){const r=node.getBoundingClientRect(),s=scenario.getBoundingClientRect();if(r.left<s.left-1||r.right>s.right+1||r.top<s.top-1||r.bottom>s.bottom+1)failures.push('scenario control clipped: '+node.textContent)}
    const cat=rect('categoryColumn'),tray=rect('subPalette'),right=rect('rightDock');
    if(innerWidth>740&&Math.abs(cat.top-right.top)>1)failures.push('desktop panels not aligned');
    if(innerWidth<=740&&right.top<tray.bottom-1)failures.push('small screen PDU panel not stacked');
    if(innerWidth>=1280&&getComputedStyle(document.documentElement).getPropertyValue('--pt-global-scale')==='1'&&time.height>50)failures.push('time bar oversized');
    return {failures,dock:{left:dock.left,right:dock.right,top:dock.top,bottom:dock.bottom},status:{top:status.top,bottom:status.bottom},width:innerWidth,height:innerHeight,barHeight:Math.round(time.height),dockHeight:Math.round(dock.height),canvasHeight:Math.round(rect('workspace').height)};
   });
   if(result.failures.length)throw Error(width+'x'+height+' / '+scale+': '+JSON.stringify(result));geometry.push({...result,scale});
   if(scale===1&&[1920,800,375].includes(width))await page.locator('body').screenshot({path:'/tmp/packettracker-dock-'+width+'.png'});
  }
  await page.setViewportSize({width:1440,height:900});await page.evaluate(()=>document.documentElement.style.setProperty('--pt-global-scale','1'));
  // Extreme old saved sizes must stay within the current window.
  await page.evaluate(()=>{for(const [k,v] of [['paletteLeft',420],['pduWidth',900],['bottomHeight',145]])localStorage.setItem('packetTracker.'+k,String(v))});await page.reload();await page.locator('#deviceTray [data-model]').first().waitFor();
  const over=await page.locator('#paletteRow').evaluate(e=>e.scrollWidth>e.clientWidth+1);if(over)throw Error('Restored dock widths overflow');
  // Start resizing from the measured panel, so clamped/default widths never jump.
  const resize=async(id,dx,dy,target,dimension,reverse=false)=>{
   const handle=await page.locator('#'+id).boundingBox(),before=await page.locator('#'+target).boundingBox();
   await page.mouse.move(handle.x+handle.width/2,handle.y+handle.height/2);await page.mouse.down();await page.mouse.move(handle.x+handle.width/2+dx,handle.y+handle.height/2+dy);await page.mouse.up();
   const after=await page.locator('#'+target).boundingBox();if(Math.abs(after[dimension]-before[dimension]-(dimension==='height'?-dy:reverse?-dx:dx))>3)throw Error(id+' resize jumped');
  };
  await resize('leftColumnSplitter',-25,0,'categoryColumn','width');
  await resize('rightColumnSplitter',25,0,'rightDock','width',true);
  await resize('bottomResizeHandle',0,-25,'bottomDock','height');
  await page.locator('#paletteSearch').fill('4331');
  if(!await page.locator('#deviceTray [data-model]').count())throw Error('Device filter returned no routers');
  for(const title of await page.locator('#deviceTray [data-model]').evaluateAll(nodes=>nodes.map(n=>n.title)))if(!title.includes('4331'))throw Error('Device filter ignored');
  await page.locator('#deviceTray [data-model]').first().click();
  const addition=page.waitForResponse(r=>r.url().endsWith('/api/command')&&r.request().postDataJSON()?.command.startsWith('add-model '));
  await page.locator('#workspace').click({position:{x:140,y:120}});if(!(await(await addition).json()).ok)throw Error('Palette placement failed');
  await page.waitForFunction(()=>Object.keys(state.devices).length===1);
  await page.locator('[data-category="connections"]').click();await page.locator('#paletteSearch').fill('');await page.locator('[data-connection="auto"]').click();
  if(!await page.locator('[data-connection="auto"]').evaluate(e=>e.classList.contains('selected')))throw Error('Auto cable selection lost');
  await page.locator('[data-category="end"]').click();if(!await page.locator('#deviceTray [data-model]').count())throw Error('End device category failed');
  const drop=page.waitForResponse(r=>r.url().endsWith('/api/command')&&r.request().postDataJSON()?.command.startsWith('add-model '));
  await page.locator('#deviceTray [data-model]').first().dragTo(page.locator('#workspace'),{targetPosition:{x:340,y:220}});
  if(!(await(await drop).json()).ok)throw Error('Palette drag/drop failed');await page.waitForFunction(()=>Object.keys(state.devices).length===2);
  for(const command of ['add pc A 150 100','add pc B 350 100','connect A eth0 B eth0','ip A eth0 192.0.2.1/24','ip B eth0 192.0.2.2/24'])await post('/api/command',{command});
  await page.evaluate(()=>fetchState());
  page.once('dialog',d=>d.accept('Dock workflow'));
  const newScenario=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action==='scenario_add');await page.locator('#scenarioNewBtn').click();await newScenario;
  await page.waitForFunction(()=>document.querySelector('#scenarioPane select').options.length===2);await page.locator('#scenarioPane select').selectOption({label:'Dock workflow'});await page.waitForFunction(()=>state.simulation.scenarios[state.simulation.active]?.name==='Dock workflow');
  await post('/api/simulation/action',{action:'pdu_add',source:'A',destination:'B',protocol:'ICMP'});await page.evaluate(()=>fetchState());
  await page.locator('#eventList .pdu-row').waitFor();
  await page.evaluate(()=>fetchState()); // A state refresh must not replace backend PDUs with legacy rows.
  await page.locator('#eventList .pdu-row').waitFor();
  if(!(await page.locator('#eventList').innerText()).includes('Successful'))throw Error('PDU results missing');
  const row=page.locator('#eventList .pdu-row');
  const fire=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action==='pdu_fire');await row.locator('button').first().click();await fire;
  await page.locator('#pduPane').evaluate(e=>e.scrollLeft=e.scrollWidth);
  await row.getByRole('button',{name:'Edit',exact:true}).click();await page.getByRole('dialog',{name:'Create Complex PDU'}).waitFor();await page.locator('#ptPduEditor').getByRole('button',{name:'Cancel'}).click();
  await page.locator('#pduToggleBtn').click();await page.locator('#ptPduWindow #pduPane').waitFor();await page.locator('#ptPduWindow header button').click();await page.locator('#rightDock #pduPane').waitFor();
  const deletion=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action==='pdu_delete');await row.getByRole('button',{name:'Delete',exact:true}).click();await deletion;
  await page.waitForFunction(()=>document.querySelector('#eventList').children.length===0);
  const scenarioDeletion=page.waitForResponse(r=>r.url().endsWith('/api/simulation/action')&&r.request().postDataJSON()?.action==='scenario_delete');await page.locator('#scenarioDeleteBtn').click();await scenarioDeletion;
  await page.waitForFunction(()=>document.querySelector('#scenarioPane select').options.length===1);
  // Tiny/high-scale windows keep both stacked sections reachable by scrolling the dock.
  await page.setViewportSize({width:320,height:568});await page.evaluate(()=>document.documentElement.style.setProperty('--pt-global-scale','1.5'));
  await page.locator('[data-category="network"]').click();await page.locator('#scenarioNewBtn').scrollIntoViewIfNeeded();
  await page.locator('#scenarioPane select').scrollIntoViewIfNeeded();if(!await page.locator('#scenarioPane select').isVisible())throw Error('Small-screen scenario controls unreachable');
  await page.locator('#playBtn').scrollIntoViewIfNeeded();if(!await page.locator('#playBtn').isVisible())throw Error('Small-screen playback unreachable');
  await page.emulateMedia({forcedColors:'active'});await page.keyboard.press('Tab');await page.locator('#paletteSearch').focus();if(await page.locator('#paletteSearch').evaluate(e=>getComputedStyle(e).outlineStyle)==='none')throw Error('Palette focus invisible');
  if(errors.length)throw Error(errors.join('; '));
  console.log(JSON.stringify(geometry));console.log('PASS: responsive dock, compact time bar, stored sizes/resizing, filtering/placement, category/cable selection, scenario/PDU fire/edit/delete and undock/redock');
 }finally{if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true})}
})().catch(e=>{console.error(e);process.exitCode=1});
