(() => {
  if (document.documentElement.classList.contains('pt-device-only')) return;
  const button = document.getElementById('cyberRangeBtn');
  const dialog = document.createElement('dialog');
  dialog.className = 'cyber-range-dialog';
  dialog.innerHTML = '<form method="dialog"><button class="cyber-close" aria-label="Close">×</button></form><h2>Cyber Range · Preview</h2><p>Generate a separate simulated enterprise lab and synthetic incident evidence. Your current topology is unchanged.</p><label>Scenario <select id="cyberScenario"><option value="account-anomaly">Suspicious account activity</option><option value="service-outage">Service availability incident</option></select></label><label>Departments <input id="cyberDepartments" type="number" min="1" max="3" value="3"></label><label>Hosts per department <input id="cyberHosts" type="number" min="1" max="4" value="2"></label><button id="cyberGenerate">Generate exercise</button><p id="cyberStatus" role="status"></p><div id="cyberResult" hidden><h3>Investigation objectives</h3><ul id="cyberObjectives"></ul><h3>Synthetic evidence timeline</h3><pre id="cyberEvents"></pre><button id="cyberLabDownload">Download topology (.json)</button> <button id="cyberCaseDownload">Download case evidence (.json)</button><p>Open the downloaded topology using File → Open. Evidence is synthetic, not live telemetry. No VM or external traffic is started.</p></div>';
  document.body.append(dialog);
  const el = id => dialog.querySelector('#' + id);
  let result;
  button.onclick = () => dialog.showModal();
  function download(name, value) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], {type:'application/json'}));
    const a = document.createElement('a'); a.href = url; a.download = name; document.body.append(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 60000);
  }
  el('cyberLabDownload').onclick = () => result && download('cyber-range-topology.json', result.lab);
  el('cyberCaseDownload').onclick = () => result && download('cyber-range-case.json', result.case);
  el('cyberGenerate').onclick = async () => {
    el('cyberGenerate').disabled = true; el('cyberResult').hidden = true; result = null;
    el('cyberStatus').textContent = 'Generating…';
    try {
      const response = await fetch('/api/cyber-range/generate', {method:'POST', headers:{'content-type':'application/json'}, body:JSON.stringify({
        scenario:el('cyberScenario').value, departments:Number(el('cyberDepartments').value), hosts_per_department:Number(el('cyberHosts').value)
      })});
      const data = await response.json();
      if (!response.ok || !data.ok) throw new Error(data.error || 'Generation failed');
      result = data;
      el('cyberStatus').textContent = Object.keys(data.lab.devices).length + ' devices · ' + data.lab.links.length + ' links';
      el('cyberObjectives').replaceChildren(...data.case.objectives.map(text => {const li=document.createElement('li'); li.textContent=text; return li;}));
      el('cyberEvents').textContent = data.case.events.map(e => [e.id, '+'+e.offset_seconds+'s', e.severity.toUpperCase(), e.device, e.message].join(' | ')).join('\n');
      el('cyberResult').hidden = false;
    } catch (e) { el('cyberStatus').textContent = e.message; }
    finally {el('cyberGenerate').disabled=false;}
  };
})();
