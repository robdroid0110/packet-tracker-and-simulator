#!/usr/bin/env python3
"""Packet Tracker and Simulator desktop launcher and isolated local server."""
from __future__ import annotations
import argparse,json,os,socket,subprocess,sys,tempfile,time,webbrowser
from pathlib import Path
from urllib.request import urlopen

ROOT=Path(__file__).resolve().parent

def default_state():
 override=os.environ.get('PACKETTRACKER_STATE')
 if override:return Path(override).expanduser()
 # A source checkout uses the same lab as the existing development web server.
 if not getattr(sys,'frozen',False) and (ROOT/'labs'/'autosave.json').exists():return ROOT/'labs'/'autosave.json'
 base=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData'/'Local')) if os.name=='nt' else Path(os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))
 return base/'PacketTracker'/'autosave.json'

def health(url):
 try:
  with urlopen(url+'/api/health',timeout=.7) as r:data=json.load(r)
  return data.get('service')=='packet-tracker' and data.get('ok') is True
 except (OSError,ValueError):return False

def serve(port,state,ready_file=None):
 state=Path(state).expanduser().resolve();os.environ['PACKETTRACKER_STATE']=str(state)
 os.environ.setdefault('PACKETTRACKER_BACKUPS',str(state.parent/'backups'))
 # Never start with an empty lab if an existing saved lab cannot be loaded.
 if state.exists():
  from netsim.model import NetworkLab
  candidate=NetworkLab();candidate.load(str(state))
 import server
 from http.server import ThreadingHTTPServer
 httpd=ThreadingHTTPServer(('127.0.0.1',port),server.Handler)
 actual=httpd.server_address[1]
 if ready_file:Path(ready_file).write_text(json.dumps({'port':actual,'pid':os.getpid()}))
 if sys.stdout:print('Packet Tracker and Simulator running at http://127.0.0.1:'+str(actual),flush=True)
 try:httpd.serve_forever()
 except KeyboardInterrupt:pass
 finally:
  with server.LOCK:server.save_state()
  httpd.server_close()

def launch_server(state,port):
 # An isolated readiness file ensures we never attach to another service.
 with tempfile.TemporaryDirectory(prefix='packet-tracker-desktop-') as folder:
  ready=Path(folder)/'ready.json'
  args=[sys.executable] if getattr(sys,'frozen',False) else [sys.executable,str(Path(__file__).resolve())]
  args+=['--server','--port',str(port),'--state',str(state),'--ready-file',str(ready)]
  kwargs={'stdin':subprocess.DEVNULL,'stdout':subprocess.DEVNULL,'stderr':subprocess.DEVNULL}
  if os.name=='nt':kwargs['creationflags']=subprocess.CREATE_NEW_PROCESS_GROUP|subprocess.DETACHED_PROCESS
  else:kwargs['start_new_session']=True
  process=subprocess.Popen(args,**kwargs)
  for _ in range(150):
   if ready.exists():
    data=json.loads(ready.read_text());url='http://127.0.0.1:'+str(data['port'])
    if health(url):return url
   if process.poll() is not None:raise RuntimeError('Packet Tracker and Simulator server could not start; check the saved lab and port')
   time.sleep(.1)
  process.terminate();raise RuntimeError('Packet Tracker and Simulator server startup timed out')

def desktop_window(url,smoke_test=False):
 if os.name!='nt':
  try:
   from PyQt6.QtCore import QUrl,QTimer
   from PyQt6.QtGui import QIcon
   from PyQt6.QtWidgets import QApplication,QMainWindow,QFileDialog,QMessageBox
   from PyQt6.QtWebEngineWidgets import QWebEngineView
   from PyQt6.QtWebEngineCore import QWebEngineSettings
   class BrowserView(QWebEngineView):
    def createWindow(self,kind):
     child=BrowserView(window);child.setWindowFlag(__import__('PyQt6.QtCore',fromlist=['Qt']).Qt.WindowType.Window,True)
     child.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,True)
     child.resize(1000,750);child.setWindowTitle('Packet Tracker and Simulator device');children.add(child)
     child.titleChanged.connect(child.setWindowTitle)
     child.setWindowIcon(window.windowIcon())
     child.page().windowCloseRequested.connect(child.close)
     child.destroyed.connect(lambda:children.discard(child));child.show();return child
   class MainWindow(QMainWindow):
    def closeEvent(self,event):
     choice=QMessageBox.question(self,'Save project?', 'Changes are autosaved. Save a separate project file before closing?', QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel, QMessageBox.StandardButton.Save)
     if choice==QMessageBox.StandardButton.Cancel:event.ignore();return
     if choice==QMessageBox.StandardButton.Save:
      path,_=QFileDialog.getSaveFileName(self,'Save project','packet-tracker-lab.json','Packet Tracker and Simulator lab (*.json)')
      if not path:event.ignore();return
      try:
       with urlopen(url+'/api/state',timeout=10) as response: data=json.load(response)
       Path(path).write_text(json.dumps(data,indent=2),encoding='utf-8')
      except Exception as error:
       QMessageBox.critical(self,'Save failed',str(error));event.ignore();return
     for child in list(children):child.close()
     event.accept()
   app=QApplication(sys.argv[:1]);children=set();window=MainWindow();window.setWindowTitle('Packet Tracker and Simulator')
   window.setWindowIcon(QIcon(str(ROOT/'web'/'packet-tracker-simulator.svg')))
   view=BrowserView();view.settings().setAttribute(QWebEngineSettings.WebAttribute.JavascriptCanOpenWindows,True);window.setCentralWidget(view);window.resize(1440,900);window.show()
   def download(item):
    path,_=QFileDialog.getSaveFileName(window,'Save lab',item.downloadFileName(),'Packet Tracker and Simulator lab (*.json);;All files (*)')
    if path:
     destination=Path(path);item.setDownloadDirectory(str(destination.parent));item.setDownloadFileName(destination.name);item.accept()
    else:item.cancel()
   view.page().profile().downloadRequested.connect(download)
   if smoke_test:
    timer=QTimer();timer.setSingleShot(True);timer.timeout.connect(lambda:app.exit(2));timer.start(20000)
    def loaded(ok):
     if not ok:app.exit(1);return
     view.page().runJavaScript("Boolean(document.querySelector('#workspace'))",lambda result:app.exit(0 if result else 1))
    view.loadFinished.connect(loaded)
   view.setUrl(QUrl(url));return app.exec()
  except ImportError:
   if smoke_test:raise RuntimeError('Qt WebEngine is required for the desktop smoke test')
 if os.name=='nt':
  # Edge is part of supported modern Windows installations; its app window
  # uses the same Web UI and remains isolated from the browser's normal tabs.
  for base in (os.environ.get('PROGRAMFILES(X86)',''),os.environ.get('PROGRAMFILES','')):
   edge=Path(base)/'Microsoft'/'Edge'/'Application'/'msedge.exe'
   if base and edge.is_file():subprocess.Popen([str(edge),'--app='+url]);return 0
 webbrowser.open(url);return 0

def main():
 parser=argparse.ArgumentParser(description='Packet Tracker and Simulator desktop application')
 parser.add_argument('--server',action='store_true');parser.add_argument('--port',type=int,default=8765)
 parser.add_argument('--state');parser.add_argument('--ready-file');parser.add_argument('--url');parser.add_argument('--smoke-test',action='store_true')
 args=parser.parse_args()
 state=Path(args.state) if args.state else default_state()
 if args.server:return serve(args.port,state,args.ready_file)
 url=args.url or 'http://127.0.0.1:'+str(args.port)
 if not args.url and (args.state is not None or not health(url)):
  with socket.socket() as probe:occupied=probe.connect_ex(('127.0.0.1',args.port))==0
  url=launch_server(state,0 if occupied else args.port)
 return desktop_window(url,args.smoke_test)

if __name__=='__main__':
 try:raise SystemExit(main())
 except Exception as error:
  message='Packet Tracker and Simulator could not start: '+str(error)
  if sys.stderr:print(message,file=sys.stderr)
  if os.name=='nt':
   import ctypes
   ctypes.windll.user32.MessageBoxW(None,message,'Packet Tracker and Simulator',0x10)
  else:
   import shutil
   if shutil.which('zenity'):subprocess.run(['zenity','--error','--text',message],check=False)
  raise SystemExit(1)

