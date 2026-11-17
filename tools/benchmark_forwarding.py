#!/usr/bin/env python3
"""Compare forwarding on two checkouts using disposable labs and servers.

Example: extract `git archive HEAD` into /tmp/pt-before, then run
  python3 tools/benchmark_forwarding.py --baseline /tmp/pt-before \
      --fixtures /tmp/packet-tracker-scale-fixtures --output /tmp/result.json
See research/FORWARDING_PERFORMANCE.md for fixture construction and caveats.
"""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from urllib.request import Request, urlopen

SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[1]


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def sample(fn):
    wall, cpu = time.perf_counter(), time.process_time()
    value = fn()
    return value, {'wall_ms': round((time.perf_counter() - wall) * 1000, 2),
                   'cpu_ms': round((time.process_time() - cpu) * 1000, 2)}


def worker(args):
    # Import the selected checkout, even when this script lives in another one.
    sys.path.insert(0, str(args.root))
    from netsim.model import NetworkLab
    from netsim.simulation import action

    def load(path):
        lab = NetworkLab()
        lab.load(str(path))
        return lab

    result = {'sizes': {}, 'pdu': None, 'http': None}
    for size in args.sizes:
        path = args.fixtures / f'{size}.json'
        measurements, checks = [], []
        for _ in range(args.repeat):
            lab = load(path)
            outcome, timing = sample(lambda: lab.ping('PC1', '172.16.3.20'))
            state = {n: {'arp': d.arp_table, 'mac': d.mac_table, 'nat': d.nat_sessions,
                         'config': d.config.get('ndp')} for n, d in lab.devices.items()}
            checks.append(digest({'outcome': outcome, 'tables': state}))
            measurements.append(timing)
        result['sizes'][str(size)] = {'devices': len(lab.devices), 'links': len(lab.links),
                                     'ping': measurements, 'result_hashes': checks}
        print(f'{args.root.name}: {len(lab.devices)} devices ping median '
              f'{statistics.median(m["wall_ms"] for m in measurements):.2f} ms', flush=True)
    lab = load(args.fixtures / '9.json')
    action(lab, {'action': 'mode', 'mode': 'simulation'})
    action(lab, {'action': 'pdu_add', 'id': 'benchmark-pdu', 'source': 'PC1', 'destination': 'WEB'})
    event, timing = sample(lambda: action(lab, {'action': 'step'}))
    result['pdu'] = {'devices': len(lab.devices), 'first_step': timing,
                     'result_hash': digest({'event': event, 'simulation': lab.simulation,
                                            'tables': {n: [d.arp_table, d.mac_table, d.nat_sessions]
                                                       for n, d in lab.devices.items()}})}
    print(f'{args.root.name}: PDU first step {timing["wall_ms"]:.2f} ms', flush=True)
    with tempfile.TemporaryDirectory(prefix='pt-forwarding-bench-') as tmp:
        tmp = Path(tmp)
        shutil.copyfile(args.fixtures / '18.json', tmp / 'state.json')
        ready = tmp / 'ready.json'
        server = subprocess.Popen([sys.executable, str(args.root / 'desktop.py'), '--server',
                                   '--port', '0', '--state', str(tmp / 'state.json'),
                                   '--ready-file', str(ready)], cwd=args.root,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(600):
                if ready.exists(): break
                if server.poll() is not None: raise RuntimeError('isolated server exited')
                time.sleep(.05)
            else: raise RuntimeError('isolated server did not start')
            url = 'http://127.0.0.1:' + str(json.loads(ready.read_text())['port']) + '/api/command'
            request = Request(url, data=json.dumps({'command': 'ping PC1 172.16.3.20'}).encode(),
                              headers={'Content-Type': 'application/json'})
            started = time.perf_counter()
            with urlopen(request, timeout=120) as response:
                raw = response.read()
            data = json.loads(raw)
            result['http'] = {'devices': len(data['state']['devices']),
                              'wall_ms': round((time.perf_counter() - started) * 1000, 2),
                              'response_bytes': len(raw), 'ok': data['ok'],
                              'output': data['output']}
            print(f'{args.root.name}: HTTP ping {result["http"]["wall_ms"]:.2f} ms', flush=True)
        finally:
            server.terminate()
            try: server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=10)
    args.worker_output.write_text(json.dumps(result, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path)
    parser.add_argument('--fixtures', type=Path, default=Path('/tmp/packet-tracker-scale-fixtures'))
    parser.add_argument('--sizes', type=int, nargs='+', default=[0, 3, 9, 18])
    parser.add_argument('--repeat', type=int, default=2)
    parser.add_argument('--output', type=Path, default=Path('/tmp/packet-tracker-forwarding.json'))
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    parser.add_argument('--root', type=Path, help=argparse.SUPPRESS)
    parser.add_argument('--worker-output', type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        worker(args)
        return
    if not args.baseline: parser.error('--baseline is required')
    if args.repeat < 1: parser.error('--repeat must be positive')
    data = {'environment': {'python': sys.version, 'platform': platform.platform(),
                            'processor': platform.processor()},
            'baseline': str(args.baseline.resolve()), 'candidate': str(ROOT),
            'fixtures': str(args.fixtures), 'repeat': args.repeat}
    with tempfile.TemporaryDirectory(prefix='pt-forwarding-results-') as temp:
        for label, root in [('before', args.baseline.resolve()), ('after', ROOT)]:
            output = Path(temp) / (label + '.json')
            cmd = [sys.executable, str(SCRIPT), '--worker', '--root', str(root),
                   '--fixtures', str(args.fixtures.resolve()), '--worker-output', str(output),
                   '--repeat', str(args.repeat), '--sizes'] + [str(n) for n in args.sizes]
            subprocess.run(cmd, check=True)
            data[label] = json.loads(output.read_text())
    for size in map(str, args.sizes):
        before, after = data['before']['sizes'][size], data['after']['sizes'][size]
        if len(set(before['result_hashes'] + after['result_hashes'])) != 1:
            raise AssertionError(f'forwarding result changed for fixture {size}')
    if data['before']['pdu']['result_hash'] != data['after']['pdu']['result_hash']:
        raise AssertionError('simulation event or state changed')
    if data['before']['http']['output'] != data['after']['http']['output']:
        raise AssertionError('HTTP ping output changed')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    print(f'Behavior matched; results saved to {args.output}')


if __name__ == '__main__':
    main()
