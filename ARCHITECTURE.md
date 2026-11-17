# Architecture

`netsim/model.py` is the source of truth. The GUI never owns network state.

`netsim/cli.py` exposes stable agent-oriented textual commands. The browser terminal and external agents both call the same parser.

`netsim/ios.py` provides stateful IOS-like per-device sessions that translate familiar CCNA commands into the same simulator state.

`server.py` provides `/api/state` and `/api/command`. It binds to `127.0.0.1` by default so agent control remains local to the workstation.

`web/` is a zero-build visual client. It can be replaced later by Qt/Tauri without changing the simulator API.

## Design direction

For deterministic CCNA study, model common protocols in Python. For features where real protocol behavior matters, add an optional backend using Linux network namespaces, veth bridges and FRRouting. The UI/API stays the same while individual devices can choose either simulated or real protocol engines.
