/* Sample visible UI surfaces without submitting configuration changes. */
const {chromium}=require(process.env.PLAYWRIGHT_MODULE||'playwright');
const {spawn}=require('child_process');
const fs=require('fs'),os=require('os'),path=require('path');
(async()=>{
 const report={method:'Headless Chromium surface inventory: tab navigation and visible placeholders only; not a functional test of every control',labs:[]};
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
 try{
  for(const [lab,names] of [['campus',['R1','SW1','PC1','WEB']],['industrial',['WLC','AP','PLC','Phone1','WirelessClient']]]){
   const dir=fs.mkdtempSync(path.join(os.tmpdir(),'pt-surface-audit-')),ready=path.join(dir,'ready'),state=path.join(dir,'state.json');
   fs.copyFileSync(path.join('labs/audit',lab+'.json'),state);
   const server=spawn('python3',['desktop.py','--server','--port','0','--state',state,'--ready-file',ready],{stdio:'ignore'});
   const entry={lab,devices:[],page_errors:[],workspace:{}};report.labs.push(entry);
   try{
    for(let i=0;i<600&&!fs.existsSync(ready);i++)await new Promise(r=>setTimeout(r,50));
    const url='http://127.0.0.1:'+JSON.parse(fs.readFileSync(ready)).port;
    const page=await browser.newPage({viewport:{width:1440,height:900}});page.setDefaultTimeout(2500);page.on('pageerror',e=>entry.page_errors.push(e.message));
    await page.goto(url);await page.locator('.node').first().waitFor();
    for(const [label,selector] of [['physical','.workspace-tab:text-is("Physical")'],['logical','.workspace-tab:text-is("Logical")'],['simulation','#simulationBtn'],['realtime','#realtimeBtn']]){
     try{await page.locator(selector).click();entry.workspace[label]='clicked'}catch(e){entry.workspace[label]=String(e).slice(0,250)}
    }
    for(const name of names){
     console.log('Inspecting',lab,name);const d={name,tabs:[],desktop:[]};entry.devices.push(d);
     try{
      await page.goto(url+'/?device='+encodeURIComponent(name));await page.locator('#dialogTabs button').first().waitFor();
      const tabs=await page.locator('#dialogTabs button[data-tab]').evaluateAll(items=>items.map(x=>x.dataset.tab));
      for(const tab of tabs){
       try{
        await page.locator(`#dialogTabs [data-tab="${tab}"]`).click();
        const view=await page.locator('#dialogBody').evaluate(e=>({visible_text:e.innerText.slice(0,220),
         disabled_controls:e.querySelectorAll('button:disabled,input:disabled,select:disabled,textarea:disabled').length,
         placeholder:!!e.querySelector('.desktop-placeholder')}));
        d.tabs.push({tab,...view});
        if(tab==='desktop'){
         const tools=await page.locator('[data-desk]').evaluateAll(items=>items.map(x=>({id:x.dataset.desk,label:x.innerText.trim()})));
         for(const tool of tools){
          try{
           await page.locator(`#dialogTabs [data-tab="desktop"]`).click();await page.locator(`[data-desk="${tool.id}"]`).click();
           const body=await page.locator('#dialogBody').evaluate(e=>({placeholder:!!e.querySelector('.desktop-placeholder'),
             unsupported_text:/not implemented|not yet implemented|not available/i.test(e.innerText),text:e.innerText.slice(0,180)}));
           d.desktop.push({...tool,...body});
          }catch(e){d.desktop.push({...tool,error:String(e).slice(0,250)})}
         }
        }
       }catch(e){d.tabs.push({tab,error:String(e).slice(0,250)})}
      }
     }catch(e){d.error=String(e).slice(0,250)}
    }
    await page.close();
   }finally{if(server.exitCode===null){server.kill('SIGTERM');await new Promise(r=>server.once('exit',r))}fs.rmSync(dir,{recursive:true,force:true});fs.writeFileSync('research/performance/ui_surfaces.json',JSON.stringify(report,null,2))}
  }
 }finally{await browser.close()}
 console.log(JSON.stringify(report.labs.map(l=>({lab:l.lab,devices:l.devices.length,page_errors:l.page_errors.length,workspace:l.workspace}))));
})().catch(e=>{console.error(e);process.exitCode=1});
