#!/usr/bin/env python3
"""Build a self-contained executable on the target operating system."""
import argparse,os,shutil,subprocess,sys,tempfile,importlib.util
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--dist',type=Path,default=ROOT/'dist');args=parser.parse_args()
 with tempfile.TemporaryDirectory(prefix='packet-tracker-build-') as temporary:
  temp=Path(temporary);web=temp/'web';shutil.copytree(ROOT/'web',web,ignore=shutil.ignore_patterns('vendor','__pycache__'))
  args.dist.mkdir(parents=True,exist_ok=True)
  command=[sys.executable,'-m','PyInstaller','--noconfirm','--onefile','--windowed','--name','PacketTrackerSimulator',
   '--distpath',str(args.dist.resolve()),'--workpath',str(temp/'work'),'--specpath',str(temp),
   '--paths',str(ROOT),'--collect-submodules','netsim','--add-data',str(web)+':web',
   '--add-data',str(ROOT/'netsim'/'data')+':netsim/data']
  if importlib.util.find_spec('lxml') is None:
   raise SystemExit('Desktop builds supporting malformed .pka activities require lxml. Install lxml in the build environment first.')
  command+=['--collect-submodules','lxml']
  command+=[str(ROOT/'desktop.py')]
  subprocess.run(command,cwd=ROOT,check=True,env={**os.environ,'PYINSTALLER_CONFIG_DIR':str(temp/'cache')})
 print('Built',args.dist/('PacketTrackerSimulator.exe' if os.name=='nt' else 'PacketTrackerSimulator'))
if __name__=='__main__':main()
