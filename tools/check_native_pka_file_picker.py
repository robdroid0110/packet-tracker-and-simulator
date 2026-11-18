#!/usr/bin/env python3
"""Real Qt WebEngine file-picker acceptance for a private user-supplied activity."""
import os,sys,json,time
from pathlib import Path
from PyQt6.QtCore import QUrl,QTimer,QPoint,Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication,QMainWindow
from PyQt6.QtWebEngineCore import QWebEnginePage
from PyQt6.QtWebEngineWidgets import QWebEngineView

if not os.environ.get('PTS_TEST_PKA'):
    raise SystemExit('Set PTS_TEST_PKA to a PRIVATE local activity file (not committed).')
p=Path(os.environ['PTS_TEST_PKA'])
assert p.is_file()
url=os.environ.get('PTS_TEST_BASE','http://127.0.0.1:8769')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from netsim.lab_import import import_pkt
expected,_=import_pkt(p.read_bytes(),p.name)
assert expected.activity is not None, 'The selected file is not a supported learning activity'
EXPECTED_DEVICES=len(expected.devices)
EXPECTED_LINKS=len(expected.links)
EXPECTED_PAGES=len(expected.activity['pages'])
app=QApplication(sys.argv[:1]);window=QMainWindow();view=QWebEngineView()
class Page(QWebEnginePage):
    def chooseFiles(self, mode, oldFiles, acceptedMimeTypes):
        print('NATIVE_FILE_PICKER',mode,','.join(acceptedMimeTypes),'returned file basename:',p.name,flush=True)
        return [str(p)]
    def javaScriptConfirm(self,url,msg):
        print('NATIVE_CONFIRM',msg[:170].replace('\n','; '),flush=True)
        return True
    def javaScriptAlert(self,url,msg):
        print('NATIVE_ALERT',str(msg)[:200],flush=True)
page=Page(view);view.setPage(page);window.setCentralWidget(view);window.resize(1380,900);window.show()
state={'started':False,'checked':0,'success':False}
start=time.monotonic()
def finish(status):
    print('NATIVE_OPEN_RESULT',status,round(time.monotonic()-start,2),'s',flush=True)
    state['success']=bool(status)
    app.quit()
def status(data):
    if not data: return
    state['checked']+=1
    if state['checked']%8==0:print('WAITING',data,flush=True)
    if state['started']:return
    if data.get('activity') and data.get('devices')==EXPECTED_DEVICES and data.get('links')==EXPECTED_LINKS and data.get('pages')==EXPECTED_PAGES:
        state['started']=True
        print('IMPORTED_PKA_IN_NATIVE_VIEW',json.dumps(data),flush=True)
        page.runJavaScript("window.PacketTrackerActivity.open()")
        QTimer.singleShot(900,check_dialog)
def check_dialog():
    page.runJavaScript("""({
      open:document.querySelector('#ptActivity')?.open,
      sections:document.querySelectorAll('#ptActivityPages button').length,
      textLength:document.querySelector('#ptActivityText')?.textContent?.length,
      linkSignals:document.querySelectorAll('.diagram-signal').length,
      nativeFileInput:document.querySelector('input[type=file]')?.accept
     })""",check_result)
def check_result(v):
    print('NATIVE_FILE_OPEN_DIALOG',v,flush=True)
    if v and v.get('open') and v.get('sections')==EXPECTED_PAGES and v.get('textLength',0)>30 and v.get('linkSignals')>=EXPECTED_LINKS:
        view.grab().save('/tmp/pts-native-direct-pka-open.png')
        finish(True)
    else:finish(False)
def poll():
    if state['success']:return
    page.runJavaScript("""({
      activity:!!state?.activity,
      devices:Object.keys(state?.devices||{}).length,
      links:state?.links?.length||0,
      pages:state?.activity?.pages?.length||0
     })""",status)
def loaded(ok):
    print('NATIVE_LOADED',ok,flush=True)
    if not ok:finish(False);return
    def tap_button(box):
        if not box or not box.get("x"):finish(False);return
        x=round(box["x"]+box["width"]/2);y=round(box["y"]+box["height"]/2)
        print("QT_ACTUAL_MOUSE_CLICK",x,y,flush=True)
        widget=view.focusProxy() or view
        point=widget.mapFrom(view,QPoint(x,y)) if widget is not view else QPoint(x,y)
        print("QT_PROXY",widget.metaObject().className(),"geometry",widget.geometry(),"click",point,flush=True)
        QTest.mouseClick(widget,Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
    page.runJavaScript("(() => {const x=document.querySelector('#openBtn')?.getBoundingClientRect();return x?{x:x.x,y:x.y,width:x.width,height:x.height}:null})()",tap_button)
    polling.start()
polling=QTimer();polling.setInterval(650);polling.timeout.connect(poll)
page.loadFinished.connect(loaded)
view.setUrl(QUrl(url))
QTimer.singleShot(55000,lambda:finish(False))
app.exec()
raise SystemExit(0 if state['success'] else 2)
