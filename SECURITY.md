# Security policy

## Scope

Packet Tracker and Simulator is designed as a local network simulator. Its HTTP control API is intended for trusted clients on a local machine, not exposure to the public internet.

Do not bind the service to a public interface or port-forward it without adding proper authentication, authorization, request limits and transport security. Simulated credentials are not real-device secrets.

## Reporting

Until a private security contact has been designated, avoid posting live credentials or sensitive exploit details in public issues. Repository maintainers should configure GitHub private vulnerability reporting before enabling public distribution.

## Dependency and build trust

Build desktop applications from this repository's source using the documented build tool. Never include locally installed proprietary simulator artwork or binaries in release assets.
