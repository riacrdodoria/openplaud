> Registro histórico do observador inicial. Para o produto atual, consulte [MVP_ACCEPTANCE.md](MVP_ACCEPTANCE.md) e [MVP_OPERATIONS.md](MVP_OPERATIONS.md). O observador foi parado a pedido do usuário de desenvolver interativamente.

# Development observer validation

2026-11-10, WO4. Not a production release or full-roadmap completion.

- Two new containers in their own `openplaud-dev` Compose project, no existing services restarted.
- Panel published on the host's specific Tailscale IPv4 address at port 8766; no public wildcard host binding, firewall/SSH/Tailscale changes or Funnel.
- Anonymous API access returned 401; bearer access returned 200 with 34 tasks, paused mode and a provisioning request.
- Restarted only these two containers and compared tasks, mode and approvals; identical persisted state.
- Docker restart policy `unless-stopped`; Docker daemon enabled at boot. Actual OS reboot/disconnect validation remains pending.
- Numeric non-root UID/GID 10001; read-only root filesystem; no capabilities or privilege escalation; no host credentials or Docker socket mounted.
- Executor container has no network, Codex or Git; therefore it cannot perform coding. Authentication for a properly isolated coding service remains required.
- Each container: 128 MiB RAM, 0.25 CPU, 32 processes; rotating Docker logs. Observed memory about 18 MiB panel and 11 MiB observer.
- Host free space later dropped below the 10 GiB execution threshold; code execution remains paused. No existing data was deleted to make room.
- Subscription execution allowance: ten calls, maximum 900 seconds each, no paid API. Zero real Codex invocations used in verification; offline fixture executable used for runner integration test.

Final automated suite: 23 tests passed. Includes real local HTTP authentication/control tests, synthetic WAV upload/dedup/Range tests, abrupt-process-exit recovery, concurrent task claiming, isolated Git attempt and before/after commits, privacy-before-provider-call checks and low-disk blocking. Browser visual/mobile QA and full reboot tests have not been performed. The API is tested locally, not deployed by the observer Compose file.

Do not mark later roadmap phases complete based on this foundation. Pending tasks include real transcription, summaries, Pixel/device integration, PostgreSQL/Redis, Calendar/location, semantic chat, Next.js PWA, sensitive-action execution, automated retries, log streaming/redaction, notifications and production hardening.
