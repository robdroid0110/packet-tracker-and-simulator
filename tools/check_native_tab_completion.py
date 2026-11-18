#!/usr/bin/env python3
"""Native Qt/QWebEngine Tab-key acceptance for router, switch, PC, server CLI.

Starts against an isolated local server with synthetic network devices. Unlike
DOM event simulation, this sends real Qt keyboard events to the desktop view.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.request import Request, urlopen
import json
import subprocess
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from netsim.model import NetworkLab

from PyQt6.QtCore import QEventLoop, QTimer, QUrl, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView

# Fresh private simulator for each run: no existing labs or console modes touched.
ROOT = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory(prefix="pts-native-tab-")
LAB_PATH = Path(TEMP.name) / "lab.json"
READY_PATH = Path(TEMP.name) / "ready.json"
lab = NetworkLab()
for kind, name in (("router", "R1"), ("switch", "SW1"),
                   ("pc", "PC1"), ("server", "SRV1")):
    lab.add_device(kind, name)
lab.save(str(LAB_PATH))
SERVER = subprocess.Popen(
    [sys.executable, str(ROOT / "desktop.py"), "--server", "--port", "0",
     "--state", str(LAB_PATH), "--ready-file", str(READY_PATH)],
    cwd=ROOT, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
for _ in range(100):
    if READY_PATH.exists():
        break
    if SERVER.poll() is not None:
        raise RuntimeError("Temporary simulator exited before readiness")
    time.sleep(.1)
else:
    raise RuntimeError("Temporary simulator never became ready")
BASE = "http://127.0.0.1:" + str(json.loads(READY_PATH.read_text())["port"])
print("PRIVATE_TEST_SIMULATOR", BASE, flush=True)
print("QT_START QApplication", flush=True)
app = QApplication(sys.argv[:1])
print("QT_READY QApplication", flush=True)
win = QMainWindow()
win.setWindowTitle("Packet Tracker Native Console Tab Completion Acceptance")
print("QT_START WebEngineView", flush=True)
view = QWebEngineView()
print("QT_READY WebEngineView", flush=True)
win.setCentralWidget(view)
win.resize(1360, 850)
print("QT_START show", flush=True)
win.show()
print("QT_READY show", flush=True)
page = view.page()
status = {"finished": False, "passed": False}


def javascript(expression):
    loop = QEventLoop()
    data = []
    def received(value):
        data.append(value)
        loop.quit()
    page.runJavaScript(expression, received)
    timer = QTimer()
    timer.setSingleShot(True)
    timer.timeout.connect(loop.quit)
    timer.start(8000)
    loop.exec()
    timer.stop()
    if not data:
        raise TimeoutError("Qt JavaScript evaluation timed out")
    return data[0]


def press_key(key):
    QTest.qWait(60)
    widget = view.focusProxy() or view
    QTest.keyClick(widget, key)
    QTest.qWait(280)


def tab_in(selector, typed, expected, *, candidates=None):
    expression = """(() => {
      const e=document.querySelector(%s);
      if(!e)return false;
      e.value='';e.focus();e.dispatchEvent(new Event('input',{bubbles:true}));
      return document.activeElement===e;
    })()""" % json.dumps(selector)
    assert javascript(expression), "console input not focused: " + selector
    QTest.qWait(50)
    widget = view.focusProxy() or view
    QTest.keyClicks(widget, typed)
    QTest.qWait(80)
    before = javascript("""(() => {
      const e=document.querySelector(%s);
      return {value:e?.value,focused:document.activeElement===e};
    })()""" % json.dumps(selector))
    assert before and before["value"] == typed, f"Native typing failed: {before!r}, wanted {typed!r}"
    assert before["focused"], "Input lost focus before native Tab"
    press_key(Qt.Key.Key_Tab)
    after = javascript("""(() => {
      const e=document.querySelector(%s);
      return {value:e?.value,focused:document.activeElement===e,
       hint:e?.closest('form')?.nextElementSibling?.textContent||''};
    })()""" % json.dumps(selector))
    assert after and after["value"] == expected, f"Tab completion: {typed!r} -> {after!r}, expected {expected!r}"
    assert after["focused"], f"Tab moved focus away from {selector}"
    if candidates:
        assert all(c in after["hint"] for c in candidates), f"Suggestions missing: {after!r}"
    print("NATIVE_TAB_PASS", selector, repr(typed), "=>", repr(expected),
          "suggestions:", (after["hint"][:80] if candidates else "none"), flush=True)


def prepare_device(name, tab):
    if tab == "cli":
        selector = "#deviceCliIn"
        command = """(() => {
          selected=%s;
          dialogTab='cli';desktopTool=null;
          dialogIface=Object.keys(state.devices[selected].interfaces)[0]||null;
          cliHistory=selected+'> ';
          document.querySelector('#deviceDialog').classList.remove('hidden');
          renderDialog();
          return Boolean(document.querySelector('#deviceCliIn'));
        })()""" % json.dumps(name)
    else:
        selector = "#pcCmdIn"
        command = """(() => {
          selected=%s;
          dialogTab='desktop';desktopTool='cmd';
          dialogIface=Object.keys(state.devices[selected].interfaces)[0]||null;
          pcPromptHistory='Packet Tracker simulated PC Command Prompt'+String.fromCharCode(10);
          document.querySelector('#deviceDialog').classList.remove('hidden');
          renderDialog();
          return Boolean(document.querySelector('#pcCmdIn'));
        })()""" % json.dumps(name)
    assert javascript(command), f"Cannot open {tab} for {name}"
    QTest.qWait(150)
    return selector


def send_ios_command(text):
    assert javascript("""(() => {
      const e=document.querySelector('#deviceCliIn');if(!e)return false;
      e.value='';e.focus();return true;
    })()"""), "IOS input missing"
    widget = view.focusProxy() or view
    QTest.keyClicks(widget, text)
    press_key(Qt.Key.Key_Return)
    # The command re-renders the dialog and IOSSession mode changes server-side.
    QTest.qWait(250)
    assert javascript("Boolean(document.querySelector('#deviceCliIn'))"), "CLI tab disappeared"


def probe_mode(name):
    payload = json.dumps({"device": name, "text": "sh", "cursor": 2}).encode()
    request = Request(BASE + "/api/ios/complete", payload,
                      headers={"content-type": "application/json"})
    with urlopen(request, timeout=6) as response:
        result = json.load(response)
    return result["mode"]


def run_tests():
    try:
        for _ in range(20):
            if javascript("Object.keys(state.devices||{}).length") >= 4:
                break
            QTest.qWait(180)
        else:
            raise AssertionError("Synthetic lab failed to load")

        router = prepare_device("R1", "cli")
        tab_in(router, "sh", "show")
        tab_in(router, "show ip int", "show ip interface")
        tab_in(router, "show ip ", "show ip ", candidates=["interface", "route"])
        # Verify Tab cannot execute a command: the session is still unprivileged.
        assert probe_mode("R1") == "user", "Completion unexpectedly altered IOS privilege"
        send_ios_command("enable")
        send_ios_command("configure terminal")
        assert probe_mode("R1") == "config", "Router did not enter configuration mode"
        tab_in(router, "int", "interface")
        tab_in(router, "int g0/", "int g0/", candidates=["g0/0", "g0/1"])
        send_ios_command("interface g0/0")
        assert probe_mode("R1") == "interface"
        tab_in(router, "shut", "shutdown")
        tab_in(router, "no sh", "no shutdown")
        # Leave the router port enabled; completion is read-only.

        switch = prepare_device("SW1", "cli")
        send_ios_command("enable")
        send_ios_command("configure terminal")
        send_ios_command("interface g0/1")
        assert probe_mode("SW1") == "interface"
        tab_in(switch, "switchport mode tr", "switchport mode trunk")
        tab_in(switch, "no sh", "no shutdown")

        pc = prepare_device("PC1", "cmd")
        tab_in(pc, "ipco", "ipconfig")
        tab_in(pc, "trac", "tracer", candidates=["tracert", "traceroute"])

        server = prepare_device("SRV1", "cmd")
        tab_in(server, "ar", "arp")
        tab_in(server, "arp -", "arp -a")

        # Global shell is also a real console; it shares the same Tab UX.
        assert javascript("""(() => {
          document.querySelector('#deviceDialog').classList.add('hidden');
          document.querySelector('#shellPane').classList.remove('closed');
          return Boolean(document.querySelector('#termIn'));
        })()""")
        tab_in("#termIn", "show topo", "show topology")

        print("NATIVE_DESKTOP_TAB_COMPLETE_PASS: IOS modes, real interfaces, router, "
              "switch, PC, server, ambiguous suggestions, global shell", flush=True)
        status["passed"] = True
    except Exception as error:
        import traceback
        traceback.print_exc()
        status["passed"] = False
    finally:
        status["finished"] = True
        app.quit()


def loaded(ok):
    if not ok:
        print("NATIVE_LOAD_FAILED", flush=True)
        status["finished"] = True
        app.quit()
        return
    QTimer.singleShot(350, run_tests)


page.loadFinished.connect(loaded)
print("QT_START URL", flush=True)
view.setUrl(QUrl(BASE))
print("QT_READY URL", flush=True)
QTimer.singleShot(55000, lambda: (print("NATIVE_TEST_TIMEOUT", flush=True), app.quit()))
print("QT_START exec", flush=True)
app.exec()
print("QT_DONE exec", flush=True)
SERVER.terminate()
try:
    SERVER.wait(timeout=5)
except subprocess.TimeoutExpired:
    SERVER.kill()
    SERVER.wait(timeout=5)
TEMP.cleanup()
raise SystemExit(0 if status["passed"] else 2)
