#!/usr/bin/env python3
"""Install the source-checkout desktop application for the current Linux user."""
import os,shutil,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def desktop_quote(value):
 # Desktop Entry Exec values are not interpreted by a shell.
 return '"'+str(value).replace('%','%%').replace('\\','\\\\').replace('"','\\"').replace('`','\\`').replace('$','\\$')+'"'

def install(data_home=None):
 if not sys.platform.startswith('linux'):raise RuntimeError('Linux desktop installation requires Linux')
 folder=Path(data_home or os.environ.get('XDG_DATA_HOME',Path.home()/'.local'/'share'))/'applications';folder.mkdir(parents=True,exist_ok=True)
 entry=folder/'packet-tracker-simulator.desktop'
 text='\n'.join(['[Desktop Entry]','Type=Application','Name=Packet Tracker and Simulator','Comment=Network simulator and agent workspace',
  'Exec='+desktop_quote(sys.executable)+' '+desktop_quote(ROOT/'desktop.py'),
  'Icon='+str(ROOT/'web'/'packet-tracker-simulator.svg'),'Terminal=false','Categories=Education;Network;','StartupNotify=true',''])
 entry.write_text(text,encoding='utf-8');entry.chmod(0o755)
 updater=shutil.which('update-desktop-database')
 if updater:os.spawnv(os.P_WAIT,updater,[updater,str(folder)])
 return entry
if __name__=='__main__':print('Installed:',install())
