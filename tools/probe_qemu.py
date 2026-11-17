#!/usr/bin/env python3
"""Boot a local kernel with no disks, initramfs, network or external resources.

This checks QEMU acceleration and startup overhead, not a network appliance.
"""
import argparse
import json
from pathlib import Path
import socket
import subprocess
import tempfile
import time
import psutil


def probe(accel,kernel):
    with tempfile.TemporaryDirectory(prefix='pt-qemu-probe-') as folder:
        qmp=Path(folder)/'qmp.sock';console=Path(folder)/'serial.log'
        command=['qemu-system-x86_64','-machine',f'pc,accel={accel}','-m','512','-smp','1',
                 '-kernel',str(kernel),'-append','console=ttyS0 panic=-1',
                 '-display','none','-monitor','none','-serial','stdio','-nic','none','-no-reboot',
                 '-qmp',f'unix:{qmp},server=on,wait=off']
        start=time.perf_counter();rss=0;cpu=0;error=None;handshake={}
        with console.open('wb') as log:
            process=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT)
            proc=psutil.Process(process.pid)
            try:
                for _ in range(200):
                    if qmp.exists() or process.poll() is not None:break
                    time.sleep(.05)
                if qmp.exists():
                    with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                        client.settimeout(3);client.connect(str(qmp));stream=client.makefile('rwb',buffering=0)
                        greeting=json.loads(stream.readline());stream.write(b'{"execute":"qmp_capabilities"}\n');json.loads(stream.readline())
                        stream.write(b'{"execute":"query-kvm"}\n');response=json.loads(stream.readline());handshake=response.get('return',{})
                for _ in range(600):
                    if process.poll() is not None:break
                    try:
                        rss=max(rss,proc.memory_info().rss);t=proc.cpu_times();cpu=t.user+t.system
                    except psutil.NoSuchProcess:break
                    time.sleep(.05)
                if process.poll() is None:error='30 second timeout';process.terminate()
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:process.kill();process.wait()
            finally:
                if process.poll() is None:process.kill();process.wait()
        data=console.read_text(errors='replace')
        return {'accelerator':accel,'qmp_kvm':handshake,'elapsed_s':round(time.perf_counter()-start,2),
                'cpu_seconds_sampled':round(cpu,2),'peak_process_rss_mib_sampled':round(rss/1048576,2),
                'guest_ram_configured_mib':512,'vcpu':1,'serial_has_linux_banner':'Linux version' in data,
                'serial_has_expected_root_panic':'Kernel panic' in data,'exit_code':process.returncode,'error':error,
                'serial_tail':data[-1500:]}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--kernel',type=Path,default=Path('/boot/vmlinuz-linux'))
    p.add_argument('--output',type=Path,default=Path('research/performance/qemu.json'));args=p.parse_args()
    results=[probe(accel,args.kernel) for accel in ('kvm','tcg')]
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(results,indent=2));print(json.dumps(results,indent=2))
