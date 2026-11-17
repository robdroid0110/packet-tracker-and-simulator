/* Isolated headless Chromium benchmark. Run benchmark_scale.py first. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn,execFileSync}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
const root=path.resolve(__dirname,'..');
const fixtures=process.env.PT_FIXTURES||'/tmp/packet-tracker-scale-fixtures';
const output=process.env.PT_UI_OUTPUT||path.join(root,'research/performance/ui.json');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function treeMemory(pid){
 const lines=execFileSync('ps',['-eo','pid=,ppid=,rss=,args='],{encoding:'utf8'}).split('\n');
 const rows=lines.map(l=>l.trim().match(/^(\d+)\s+(\d+)\s+(\d+)\s+(.*)$/)).filter(Boolean)
  .map(m=>({pid:+m[1],parent:+m[2],rss:+m[3],cmd:m[4]}));
 const ids=new Set([pid]);let changed=true;
 while(changed){changed=false;for(const r of rows)if(ids.has(r.parent)&&!ids.has(r.pid)){ids.add(r.pid);changed=true}}
 const chrome=rows.filter(r=>ids.has(r.pid)&&r.cmd.includes('chromium'));
 let pssKiB=0,pssCount=0;for(const r of chrome){try{const m=fs.readFileSync(`/proc/${r.pid}/smaps_rollup`,'utf8').match(/^Pss:\s+(\d+) kB/m);if(m){pssKiB+=+m[1];pssCount++}}catch{}}
 return {sum_rss_mib:+(chrome.reduce((a,r)=>a+r.rss,0)/1024).toFixed(2),pss_mib:+(pssKiB/1024).toFixed(2),pss_processes:pssCount,chromium_processes:chrome.length};
}
(async()=>{
 const report={method:'Headless Chromium, one run per size; PSS apportions shared pages, summed RSS double counts them',runs:[],viewports:[]};
 for(const size of (process.env.PT_UI_SIZES||'0,3,9,18,28').split(',').map(Number)){
  const source=path.join(fixtures,size+'.json');if(!fs.existsSync(source)){report.runs.push({size,status:'fixture unavailable'});continue}
  const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-ui-bench-')),ready=path.join(dir,'ready'),state=path.join(dir,'state.json');fs.copyFileSync(source,state);
  const server=spawn('python3',[path.join(root,'desktop.py'),'--server','--port','0','--state',state,'--ready-file',ready],{stdio:'ignore'});
  let browser,context;
  try{
   for(let i=0;i<1200&&!fs.existsSync(ready);i++){if(server.exitCode!==null)throw Error('isolated server exited');await sleep(50)}
   if(!fs.existsSync(ready))throw Error('server readiness timeout');
   const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
   browser=await chromium.launch({headless:true,executablePath:process.env.CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox']});
   context=await browser.newContext({viewport:{width:1440,height:900}});const page=await context.newPage();page.setDefaultTimeout(90000);
   const failures=[];page.on('pageerror',e=>failures.push(e.message));
   const protocol=await context.newCDPSession(page);await protocol.send('Performance.enable');
   const begin=performance.now();await page.goto(url,{waitUntil:'domcontentloaded',timeout:90000});
   const expected=16+size*11;await page.waitForFunction(n=>document.querySelectorAll('#nodes .node').length===n,expected,{timeout:90000});
   const loadMs=performance.now()-begin;
   const browserSession=await browser.newBrowserCDPSession();
   const cpu=async()=>{const v=await browserSession.send('SystemInfo.getProcessInfo');return v.processInfo.reduce((a,p)=>a+p.cpuTime,0)};
   const cpuStart=await cpu(),idleStart=performance.now();await sleep(3000);const idleSeconds=(performance.now()-idleStart)/1000,idleCpu=await cpu()-cpuStart;
   const render=await page.evaluate(async()=>{
    const samples=[];for(let i=0;i<5;i++){
     const start=performance.now();renderTopology();document.querySelector('#nodes').getBoundingClientRect();
     await new Promise(requestAnimationFrame);await new Promise(requestAnimationFrame);samples.push(performance.now()-start)
    }return samples;
   });
   const heap=await protocol.send('Runtime.getHeapUsage');const dom=await protocol.send('Memory.getDOMCounters');
   const node=page.locator('.node[data-name="PC1"]');await node.scrollIntoViewIfNeeded();const box=await node.boundingBox();
   const before=await page.evaluate(()=>({x:state.devices.PC1.x,y:state.devices.PC1.y}));
   const dragStart=performance.now();await page.mouse.move(box.x+25,box.y+25);await page.mouse.down();await page.mouse.move(box.x+65,box.y+45,{steps:8});
   const preview=performance.now()-dragStart;const commit=page.waitForResponse(r=>r.url().endsWith('/api/command')&&r.request().method()==='POST');
   await page.mouse.up();const response=await commit;const moved=await response.json();if(!moved.ok||moved.state.devices.PC1.x===before.x)throw Error('drag did not persist');
   await page.waitForFunction(x=>state.devices.PC1.x!==x,before.x);const drag=performance.now()-dragStart;
   const entry={size,status:'completed',devices:expected,load_ms:+loadMs.toFixed(2),render_samples_ms:render.map(n=>+n.toFixed(2)),
    drag_preview_8_moves_ms:+preview.toFixed(2),drag_commit_total_ms:+drag.toFixed(2),js_heap_used_mib:+(heap.usedSize/1048576).toFixed(2),dom_nodes_including_detached:dom.nodes,
    browser_memory:treeMemory(process.pid),browser_idle_cpu_percent:+(idleCpu/idleSeconds*100).toFixed(1),page_errors:failures};
   report.runs.push(entry);console.log(JSON.stringify(entry));
   if(size===0){
    for(const width of [320,375,768,1024,1440,1920]){
     await page.setViewportSize({width,height:900});await sleep(100);
     const data=await page.evaluate(()=>{
      const buttons=[...document.querySelectorAll('button')].filter(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return s.display!=='none'&&s.visibility!=='hidden'&&r.width>0&&r.height>0});
      const name=e=>(e.getAttribute('aria-label')||e.getAttribute('title')||e.innerText||e.querySelector('img')?.alt||'').trim();
      const noName=buttons.filter(e=>!name(e)).map(e=>({id:e.id,outer:e.outerHTML.slice(0,180)}));
      const clipped=buttons.filter(e=>{const r=e.getBoundingClientRect();return (r.right>innerWidth+1||r.left < -1||r.bottom>innerHeight+1||r.top < -1)}).map(e=>name(e)||e.id).slice(0,30);
      const work=document.querySelector('#workspace').getBoundingClientRect();const node=document.querySelector('#nodes .node');
      return {width:innerWidth,document_scroll_width:document.documentElement.scrollWidth,workspace:{width:Math.round(work.width),height:Math.round(work.height)},
       visible_buttons:buttons.length,unnamed_buttons:noName,clipped_buttons:clipped,
       topology_node:{tag:node?.tagName,tabindex:node?.getAttribute('tabindex'),role:node?.getAttribute('role'),aria_label:node?.getAttribute('aria-label')}};
     });report.viewports.push(data);
     if([375,1440].includes(width))await page.screenshot({path:path.join(os.tmpdir(),`pt-audit-${width}.png`)});
    }
   }
  }catch(e){report.runs.push({size,status:'failed',error:String(e)});console.error(size,e)}
  finally{if(context)await context.close();if(browser)await browser.close();if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true});fs.mkdirSync(path.dirname(output),{recursive:true});fs.writeFileSync(output,JSON.stringify(report,null,2))}
 }
})().catch(e=>{console.error(e);process.exitCode=1});
