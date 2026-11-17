/* Isolated GUI/agent parity check; accepts PACKET_TRACKER_EXECUTABLE. */
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright');
const { spawn } = require('child_process');
const fs = require('fs'), os = require('os'), path = require('path');

(async () => {
  const folder = fs.mkdtempSync(path.join(os.tmpdir(), 'pt-connectivity-ui-'));
  const ready = path.join(folder, 'ready.json');
  const executable = process.env.PACKET_TRACKER_EXECUTABLE;
  const server = spawn(executable || 'python3', [
    ...(executable ? [] : ['desktop.py']), '--server', '--port', '0',
    '--state', path.join(folder, 'lab.json'), '--ready-file', ready
  ], { stdio: 'ignore' });
  let browser;
  try {
    for (let i = 0; i < 600 && !fs.existsSync(ready); i++) {
      if (server.exitCode !== null) throw Error('Isolated server exited');
      await new Promise(r => setTimeout(r, 50));
    }
    if (!fs.existsSync(ready)) throw Error('Isolated server did not start');
    const url = 'http://127.0.0.1:' + JSON.parse(fs.readFileSync(ready)).port;
    const post = async (endpoint, payload) => {
      const response = await fetch(url + endpoint, { method: 'POST',
        headers: { 'content-type': 'application/json' }, body: JSON.stringify(payload) });
      const body = await response.json();
      if (!response.ok) throw Error(JSON.stringify(body));
      return body;
    };
    browser = await chromium.launch({ headless: true, executablePath: '/usr/bin/chromium', args: ['--no-sandbox'] });
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    await page.goto(url);
    const chooser = page.waitForEvent('filechooser');
    await page.locator('#openBtn').click();
    const confirmation = page.waitForEvent('dialog');
    await (await chooser).setFiles(path.resolve('labs/audit/campus.json'));
    await (await confirmation).accept();
    await page.locator('.node[data-name="PC1"]').waitFor();
    const popup = page.waitForEvent('popup');
    await page.locator('.node[data-name="PC1"]').click();
    const device = await popup;
    await device.locator('#dialogTabs').waitFor();
    await device.locator('[data-tab="desktop"]').click();
    await device.locator('[data-desk="cmd"]').click();
    async function guiPing(expected) {
      await device.locator('#pcCmdIn').fill('ping 172.16.3.20');
      await device.locator('#pcCmdIn').press('Enter');
      await device.waitForFunction(text => document.querySelector('#pcCmdOut').textContent.includes(text), expected);
    }
    await guiPing('PING success');
    let result = await post('/api/v1/connectivity/ping', { source: 'PC1', destination_ip: '172.16.3.20' });
    if (result.result.reachable !== true) throw Error('Agent disagreed with GUI success');
    await post('/api/command', { command: 'down PC1 eth0' });
    await guiPing('PING failed');
    result = await post('/api/v1/connectivity/ping', { source: 'PC1', destination_ip: '172.16.3.20' });
    if (result.result.reachable !== false || result.result.reason.code !== 'no_source_route') {
      throw Error('Agent disagreed with GUI failure: ' + JSON.stringify(result));
    }
    console.log('PASS: GUI and typed API agree on successful and failed pings');
  } finally {
    if (browser) await browser.close();
    if (server.exitCode === null) {
      server.kill('SIGTERM');
      await new Promise(resolve => server.once('exit', resolve));
    }
    fs.rmSync(folder, { recursive: true, force: true });
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
