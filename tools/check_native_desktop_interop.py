#!/usr/bin/env python3
"""Qt WebEngine desktop acceptance: imported PKA, instructions, progress, export.

This runs a real native QWebEngineView (not Chromium Playwright/web tests).
It uses only an isolated local simulator and temporary output files.
"""
from pathlib import Path
import json
import sys
import os

from PyQt6.QtCore import QTimer,QUrl
from PyQt6.QtWidgets import QApplication,QMainWindow
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWebEngineCore import QWebEnginePage

BASE=os.environ.get("PTS_DESKTOP_ACTIVITY_URL", "http://127.0.0.1:8768")
EXPECTED_DEVICES=int(os.environ.get("PTS_EXPECTED_DEVICES", "31"))
EXPECTED_LINKS=int(os.environ.get("PTS_EXPECTED_LINKS", "41"))
EXPECTED_PAGES=int(os.environ.get("PTS_EXPECTED_PAGES", "10"))
OUTPUT=Path("/tmp/pts-native-export-test.pkt")
SCREEN=Path("/tmp/pts-native-activity-test.png")
VIEW=Path("/tmp/pts-native-activity-topology.png")

class TestPage(QWebEnginePage):
    def javaScriptConfirm(self,url,msg):
        print("NATIVE_JS_CONFIRM",str(msg)[:80],flush=True)
        return True
    def javaScriptAlert(self,url,msg):
        print("NATIVE_JS_ALERT",str(msg)[:160],flush=True)

app=QApplication(sys.argv[:1])
window=QMainWindow()
window.setWindowTitle("Packet Tracker Desktop Native Acceptance")
view=QWebEngineView()
page=TestPage(view)
view.setPage(page)
window.setCentralWidget(view)
window.resize(1340,850)
window.show()
failures=[]
results={}

def fail(msg):
    print("NATIVE_FAIL",msg,flush=True)
    failures.append(msg);QTimer.singleShot(0,app.quit)

def evaluate(script,callback):
    page.runJavaScript(script,lambda value:callback(value))

def inspect_start(ok):
    if not ok:
        return fail("desktop failed to load")
    QTimer.singleShot(1500,inspect_activity)

def inspect_activity():
    evaluate("""({
      nativeUi:Boolean(window.PacketTrackerActivity),
      loaded:Boolean(state.activity),
      pageCount:state.activity?.pages?.length,
      deviceCount:Object.keys(state.devices).length,
      linkCount:state.links.length,
      exportBtn:Boolean(document.querySelector('#savePktBtn'))
    })""",begin_activity)

def begin_activity(result):
    print("NATIVE_DESKTOP_BOOT",result,flush=True)
    if not result or not result.get("nativeUi") or result.get("deviceCount")!=EXPECTED_DEVICES or result.get("linkCount")!=EXPECTED_LINKS or result.get("pageCount")!=EXPECTED_PAGES:
        return fail("desktop did not load the expected activity")
    page.runJavaScript("window.PacketTrackerActivity.open();")
    QTimer.singleShot(1200,verify_dialog)

def verify_dialog():
    evaluate("""({
       open:document.querySelector('#ptActivity').open,
       pageButtons:document.querySelectorAll('#ptActivityPages button').length,
       textLen:document.querySelector('#ptActivityText').textContent.length,
       checkText:document.querySelector('#ptActivityCheckCount').textContent,
       originalTextInjected:document.querySelector('#ptActivityText html')!==null,
       canvasHeight:Math.round(document.querySelector('#workspace').getBoundingClientRect().height),
      linkSignals:document.querySelectorAll('.diagram-signal').length,
      signalUp:document.querySelectorAll('.diagram-signal[fill="#279550"]').length
    })""",activity_dialog_status)

def activity_dialog_status(status):
    print("NATIVE_ACTIVITY_DIALOG",status,flush=True)
    if not status or not status.get("open") or status.get("pageButtons")!=EXPECTED_PAGES or status.get("textLen",0)<20 or status.get("originalTextInjected"):
        return fail("native activity dialog or text safety not correct")
    view.grab().save(str(SCREEN))
    page.runJavaScript("""(() => {const el=document.querySelector('#ptActivityReview');
       el.checked=true;el.dispatchEvent(new Event('change',{bubbles:true}));return true;})()""")
    QTimer.singleShot(1000,verify_review)

def verify_review():
    evaluate("""document.querySelector('#ptActivityReviewed').textContent""",reviewed)

def reviewed(status):
    print("NATIVE_PROGRESS_REVIEWED",status,flush=True)
    if "1 reviewed" not in (status or ""):return fail("activity page review did not persist")
    page.runJavaScript("""(() => {const el=document.querySelector('#ptActivityReview');
      el.checked=false;el.dispatchEvent(new Event('change',{bubbles:true}));
      window.PacketTrackerActivity.close();return true;})()""")
    QTimer.singleShot(550,check_layout)

def check_layout():
    window.resize(675,750)
    QTimer.singleShot(500,verify_compact)

def verify_compact():
    evaluate("""({
       workspaceHeight:document.querySelector('#workspace').getBoundingClientRect().height,
       compact:document.body.classList.contains('pt-compact-layout'),
       fitZoom:Math.round(zoom*100),
       connectedVisible:[...document.querySelectorAll('#nodes .node')].filter(n=>{
        const r=n.getBoundingClientRect(),w=document.querySelector('#workspace').getBoundingClientRect();
        const device=state.devices[n.dataset.name];
        return state.links.some(l=>l.a_device===n.dataset.name||l.b_device===n.dataset.name)&&
          r.left>=w.left&&r.right<=w.right&&r.top>=w.top&&r.bottom<=w.bottom;
       }).length,
       activityButton:!document.querySelector('#activityBtn').hidden,
       exportButton:Boolean(document.querySelector('#savePktBtn'))
    })""",compact_status)

def compact_status(info):
    print("NATIVE_COMPACT",info,flush=True)
    if not info or not info.get("compact") or info.get("workspaceHeight",0)<250 or not info.get("activityButton"):
        return fail("native split-screen layout failed")
    view.grab().save(str(VIEW))
    window.resize(1340,850)
    QTimer.singleShot(550,export_button)

def save_download(item):
    item.setDownloadDirectory("/tmp")
    item.setDownloadFileName(OUTPUT.name)
    item.accept()
    print("NATIVE_DESKTOP_DOWNLOAD",item.downloadFileName(),flush=True)

page.profile().downloadRequested.connect(save_download)

def export_button():
    page.runJavaScript("document.querySelector('#savePktBtn').click();")
    QTimer.singleShot(4500,verify_export)

def verify_export():
    if not OUTPUT.is_file() or OUTPUT.stat().st_size<=100:
        return fail("native desktop did not save a .pkt file")
    print("NATIVE_EXPORTED_PKT_BYTES",OUTPUT.stat().st_size,flush=True)
    QTimer.singleShot(0,app.quit)

page.loadFinished.connect(inspect_start)
view.setUrl(QUrl(BASE))
QTimer.singleShot(30000,lambda:fail("native desktop acceptance timeout"))
app.exec()
if failures:raise SystemExit(2)
print("PASS: native PyQt desktop activity instructions, review tracking, split-screen and .pkt Save",flush=True)
