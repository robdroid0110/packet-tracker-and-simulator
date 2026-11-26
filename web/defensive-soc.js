(() => {
  if (document.documentElement.classList.contains('pt-device-only')) return;
  const dialog = document.createElement('dialog');
  dialog.className = 'cyber-range-dialog defensive-soc-dialog';
  dialog.innerHTML = '<form method="dialog"><button class="cyber-close" aria-label="Close">×</button></form><h2>SOC · Modeled observations</h2><p>Local synthetic telemetry from the active simulator. Alerts are review prompts, not proof of compromise.</p><label>Kind <select id="socKind"><option value="">All</option><option>connectivity</option><option>scheduled</option><option>packet</option><option>health</option><option>service</option></select></label><label>Outcome <select id="socOutcome"><option value="">All</option><option>success</option><option>failure</option></select></label><button id="socRefresh">Refresh</button> <button id="socExport" disabled>Export view</button><p id="socStatus" role="status"></p><h3>Alerts</h3><ul id="socAlerts"></ul><h3>Event timeline (simulation time)</h3><div class="soc-table-wrap"><table><thead><tr><th>ID</th><th>Time (s)</th><th>Kind / protocol</th><th>Source</th><th>Destination</th><th>Outcome / reason</th></tr></thead><tbody id="socRows"></tbody></table></div>';
  document.body.append(dialog);
  const el = id => dialog.querySelector('#'+id);
  let current = null, generation = 0;
  async function refresh() {
    const token = ++generation;
    current = null; el('socExport').disabled = true; el('socStatus').textContent = 'Loading…';
    el('socRows').replaceChildren(); el('socAlerts').replaceChildren();
    const query = new URLSearchParams();
    if (el('socKind').value) query.set('kind',el('socKind').value);
    if (el('socOutcome').value) query.set('outcome',el('socOutcome').value);
    try {
      const response = await fetch('/api/cyber-range/soc?'+query);
      const data = await response.json();
      if (token !== generation) return;
      if (!response.ok || !data.ok) throw Error(data.error || 'Unable to load SOC evidence');
      current = data;
      el('socStatus').textContent = data.logs.length+' visible events · '+data.alerts.length+' alerts · '+data.retention.dropped+' older events evicted';
      for (const alert of data.alerts) {
        const item = document.createElement('li');
        item.textContent = alert.id+' · '+alert.severity+' · '+alert.title+' (event '+alert.event_id+')'+(alert.case_id?' · '+alert.case_id+(alert.acknowledged?' · acknowledged':''):'');
        el('socAlerts').append(item);
      }
      if (!data.alerts.length) {
        const item = document.createElement('li'); item.textContent = 'No alerts in this view.'; el('socAlerts').append(item);
      }
      for (const entry of [...data.logs].reverse()) {
        const row = document.createElement('tr');
        for (const value of [entry.id,entry.sim_time,entry.kind+' / '+entry.protocol,entry.source,entry.destination,entry.outcome+(entry.reason?' / '+entry.reason:'')]) {
          const cell = document.createElement('td'); cell.textContent = String(value); row.append(cell);
        }
        el('socRows').append(row);
      }
      el('socExport').disabled = false;
    } catch (error) { if(token===generation) el('socStatus').textContent = error.message; }
  }
  document.getElementById('defensiveSocBtn').onclick = () => { dialog.showModal(); refresh(); };
  el('socRefresh').onclick = refresh;
  el('socKind').onchange = refresh; el('socOutcome').onchange = refresh;
  el('socExport').onclick = () => {
    if (!current) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(current,null,2)],{type:'application/json'}));
    const a = document.createElement('a'); a.href=url; a.download='modeled-soc-evidence.json'; document.body.append(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),60000);
  };
})();
