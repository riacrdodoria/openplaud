# Discovery — 2026-11-10

## Repository

Baseline commit: `5b14c73`. AGENTS.md and all three required documents existed and were read. README.md was missing. No application source, dependency manifest, CI or tests existed.

## Available host

Execution host identifies as Trycoo WO4, Ubuntu 24.04.5. Installed Codex CLI: 0.166.0; login reports ChatGPT. About 11.4 GiB RAM visible, 4.5 GiB available, 16 GiB swap with about 9 GiB in use. Root filesystem 402 GiB, 371 GiB used (94%), 27 GiB available. Do not infer the advertised 16 GB is fully available to this execution context.

Read-only Docker/network inventory found many running services: n8n, Postiz, Temporal, Mautic, Twenty, Metabase, Multica, and unrelated business applications. Multiple PostgreSQL and Redis instances, named volumes and separate bridge networks exist. No service, volume, network or production database was modified. No raw container environment or secrets were collected.

Occupied local ports include 3000, 3003, 3020, 4007, 4310, 4311, 4320, 5433, 5434, 5680, 7233, 8080, 9000, 9080 and 9082, plus other services. Candidate OpenPlaud ports 8766/8767 were unoccupied at inventory time; recheck before installation. Existing listeners on wildcard interfaces are outside this project's scope.

Tailscale daemon is active. The Pixel appeared offline in the inventory; device export behavior and location consent remain unverified. The user systemd manager reported degraded; do not rely on a login session for persistence. Selected system services should use a separate restricted account.

## Risks and gates

- Memory pressure and nearly full disk: no model downloads or heavy containers during discovery.
- Existing shared user credentials: persistent coding must run with a separate account and no production secrets.
- Production installation requires version validation and approval. Templates exist; no units have been installed.
- Tailscale changes require approval. No serve/funnel, firewall or SSH changes were made.
- Operator authorized subscription-only use, maximum ten 15-minute invocations. No paid API authorization.
- Actual reboot testing must use a disposable environment. Current tests cover process crash and durable reopen only.
