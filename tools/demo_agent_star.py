#!/usr/bin/env python3
"""Reproducible 97-device, eight-arm star built through the live agent API.

This demo is an example of agent-generated command execution. It uses only
synthetic devices and addresses. It refuses non-local URLs and nonempty labs.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import math
import time
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

ARM_COUNT = 8
PC_PER_SWITCH = 4
EXPECTED_DEVICES = 1 + ARM_COUNT * (1 + 2 + 8 + 1)
EXPECTED_LINKS = ARM_COUNT * (1 + 2 + 8 + 1)


def positions(arm: int):
    # Start at the top and work clockwise, like an agent growing a star.
    theta = -math.pi / 2 + (arm - 1) * (2 * math.pi / ARM_COUNT)
    rx, ry = math.cos(theta), math.sin(theta)
    tx, ty = -ry, rx
    cx, cy = 1360, 1050
    def at(r, t=0):
        return round(cx + rx * r + tx * t), round(cy + ry * r + ty * t)
    return at


def topology_plan():
    """Yield (section, exact simulator command); only real supported commands."""
    yield "CORE", "add switch CORE-STAR 1360 1050"
    for arm in range(1, ARM_COUNT + 1):
        at = positions(arm)
        router = f"R{arm:02d}"
        a, b = f"SW{arm:02d}A", f"SW{arm:02d}B"
        x, y = at(400)
        yield f"ARM {arm:02d} / DEVICES", f"add router {router} {x} {y}"
        for which, sw, side in ((1, a, -155), (2, b, 155)):
            x, y = at(670, side)
            yield f"ARM {arm:02d} / DEVICES", f"add switch {sw} {x} {y}"
            for j in range(1, PC_PER_SWITCH + 1):
                name = f"PC{arm:02d}{which}{j}"
                x, y = at(890, side + (j - 2.5) * 67)
                yield f"ARM {arm:02d} / DEVICES", f"add pc {name} {x} {y}"
        x, y = at(770, 255)
        yield f"ARM {arm:02d} / DEVICES", f"add server SRV{arm:02d} {x} {y}"
        yield f"ARM {arm:02d} / LINKS", f"connect CORE-STAR fa0/{arm} {router} g0/0"
        yield f"ARM {arm:02d} / LINKS", f"connect {router} g0/1 {a} g0/1"
        yield f"ARM {arm:02d} / LINKS", f"connect {router} g0/2 {b} g0/1"
        for which, sw in ((1, a), (2, b)):
            for j in range(1, PC_PER_SWITCH + 1):
                yield f"ARM {arm:02d} / LINKS", f"connect {sw} fa0/{j} PC{arm:02d}{which}{j} eth0"
        yield f"ARM {arm:02d} / LINKS", f"connect {b} fa0/5 SRV{arm:02d} eth0"

    # Every arm has two separate /24 LANs, and all routers share one OSPF
    # transit segment across the central L2 switch.
    for arm in range(1, ARM_COUNT + 1):
        router = f"R{arm:02d}"
        yield "CONFIGURE ROUTING", f"ip {router} g0/0 10.254.0.{arm + 10}/24"
        yield "CONFIGURE ROUTING", f"ip {router} g0/1 10.11.{arm}.1/24"
        yield "CONFIGURE ROUTING", f"ip {router} g0/2 10.12.{arm}.1/24"
        yield "CONFIGURE ROUTING", f"ospf {router} enable"
        for which in (1, 2):
            for j in range(1, PC_PER_SWITCH + 1):
                name = f"PC{arm:02d}{which}{j}"
                ip = f"10.{10 + which}.{arm}.{9 + j}/24"
                yield "CONFIGURE HOSTS", f"ip {name} eth0 {ip}"
                yield "CONFIGURE HOSTS", f"gateway {name} 10.{10 + which}.{arm}.1"
        yield "CONFIGURE HOSTS", f"ip SRV{arm:02d} eth0 10.12.{arm}.50/24"
        yield "CONFIGURE HOSTS", f"gateway SRV{arm:02d} 10.12.{arm}.1"


def get(url, path):
    with urlopen(url + path, timeout=12) as response:
        return json.load(response)


def command(url, text):
    payload = json.dumps({"command": text}).encode()
    request = Request(url + "/api/command", data=payload, method="POST",
                      headers={"content-type": "application/json"})
    with urlopen(request, timeout=20) as response:
        result = json.load(response)
    if not result.get("ok", False) or str(result.get("output", "")).startswith("ERROR:"):
        raise RuntimeError(f"Command failed: {text!r} -- {str(result)[:450]}")
    return result


def verify(url):
    state = get(url, "/api/state")
    assert len(state["devices"]) == EXPECTED_DEVICES, (
        len(state["devices"]), EXPECTED_DEVICES
    )
    assert len(state["links"]) == EXPECTED_LINKS, (
        len(state["links"]), EXPECTED_LINKS
    )
    print("STAR_TOPOLOGY_VERIFIED",
          json.dumps({"devices": len(state["devices"]),
                      "links": len(state["links"]),
                      "kinds": dict(Counter(d["kind"] for d in state["devices"].values()))}),
          flush=True)
    for source, destination in (("PC0111", "10.11.2.10"),
                                ("PC0211", "10.12.7.11"),
                                ("PC0814", "10.12.5.50")):
        data = json.dumps({"source": source, "destination_ip": destination}).encode()
        req = Request(url + "/api/v1/connectivity/ping", data=data,
                      headers={"content-type": "application/json"})
        with urlopen(req, timeout=15) as response:
            reply = json.load(response)
        outcome = reply.get("result", reply)
        if outcome.get("reachable") is not True:
            raise RuntimeError(f"Cross-arm connectivity failed: {source} -> {destination}")
        print("CROSS_BRANCH_PING_OK", source, "to", destination, flush=True)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8767")
    parser.add_argument("--delay", type=float, default=0.06,
                        help="Pause between commands for visual live rendering")
    args = parser.parse_args()
    parsed = urlsplit(args.url)
    if (parsed.scheme != "http" or parsed.hostname not in ("127.0.0.1", "localhost")
            or parsed.username or parsed.password or not parsed.port
            or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
        parser.error("Only explicit localhost HTTP server URLs may be used")
    if args.delay < 0 or args.delay > 3:
        parser.error("--delay must be between 0 and 3 seconds")
    initial = get(args.url, "/api/state")
    if initial.get("devices") or initial.get("links"):
        parser.error("Target lab is not empty; refusing to overwrite any work")
    total = 0
    for section, operation in topology_plan():
        command(args.url, operation)
        total += 1
        if total % 8 == 0:
            print(f"{section:25s} {total:03d}  {operation}", flush=True)
        time.sleep(args.delay)
    verify(args.url)
    print("DONE: 97 devices in an eight-arm agent-built star", flush=True)


if __name__ == "__main__":
    main()
