# Operations and remaining installation gate

## Before activation

Review the PR, verify all tests, inspect the service templates and reserve 8766/8767 again. Provision a dedicated `openplaud-dev` account with no sudo, Docker socket access, production credentials or access to unrelated application directories. Install a verified Codex 0.166.0 binary at `/usr/local/bin/codex`; current interactive-user installation is not accessible through ProtectHome. Authenticate that dedicated account interactively with the approved ChatGPT subscription; do not copy the current user's whole Codex home or expose tokens.

The account needs a checkout at `/srv/openplaud/repo`, its own writable `/srv/openplaud` and `/var/lib/openplaud-dev`, configuration at `/etc/openplaud/executor.json`, and a mode-0600 environment file `/etc/openplaud/panel.env` containing a separately generated panel token. Apply the 10-invocation/900-second ceiling. The executor database is the lifetime invocation ledger; never delete/reseed it to reset allowance.

Units under deploy/ are templates for review, not an installer. Verify `ProtectHome`, sandbox nesting, account permissions and filesystem isolation in a disposable machine before installation. ProtectHome alone does not hide arbitrary world-readable production directories outside home: audit ACLs/mount namespace. Do not mark `isolated_account_verified` until this is proven.

`systemd-analyze verify deploy/openplaud-executor.service deploy/openplaud-panel.service` checks unit syntax, not runtime sandbox compatibility. Templates include restart limits, CPU, memory, process limits and a 64 MiB per-file executor limit. Disk quota and log retention are still required before unattended activation. The runner's free-space check is only a starting gate.

The panel template binds loopback. Android access needs a reviewed binding to the host's specific Tailscale address or a separately approved Tailscale HTTPS proxy. Never bind an administrative panel to 0.0.0.0 or enable Funnel. Existing Tailscale configuration must remain unchanged until approved.

## Recovery and review

A process interruption persists the task and run; next startup marks unfinished work BLOCKED/INTERRUPTED. Inspect the preserved worktree and before SHA before deciding whether to recover changes. No blind rerun of side effects. A failed attempt is terminal until operator review; automatic repair/retry scheduling is pending. The attempt counter and ceiling prevent accidental duplicate scheduling.

Pause prevents new claims but lets the current attempt finish. Stop likewise stops scheduling and leaves the process available for inspection. systemd stop kills the whole control group; next startup recovers interrupted metadata. Runtime maximum bounds both Codex and suite invocations. Failed authentication never switches providers. Generic tests only move a task to REVIEW. Verify acceptance and integrate its branch while paused before marking DONE. Instructions are audit records awaiting implementation review, not immediately injected into agents.

Sensitive requests are persisted in the approvals table. This version deliberately has no endpoint that executes an approved sensitive action: inspect and execute exact approved changes through a separately reviewed maintenance workflow. Do not interpret the ordinary task acceptance button as authorization for deployment, paid APIs, credentials or host changes.

## Backup / rollback

Pause, wait for no RUNNING/TESTING task, stop the dedicated services, and use SQLite's backup API for both databases. Back up audio objects and task worktrees together with configuration and version SHA. Encrypt backups, restrict access, and store secrets separately. Verify restore into an empty temporary directory and compare SHA-256 of audio files. Never copy a live SQLite file alone without WAL handling.

Rollback: stop only OpenPlaud services, preserve state and worktrees, restore the reviewed prior code version and its matching state snapshot, verify tests, then restart paused. Do not delete unrelated volumes or run docker prune. No production schema migration exists in this foundation.

## Validation still required

Disposable reboot, SSH disconnect independence, runtime service-account containment, remote Android access, log redaction/retention, notifications, automated sensitive approvals, multi-role authorization, and mobile browser QA. No assertion of 24/7 operation is made until those tests pass.

## Isolated development observer (no AI credentials)

`compose.control.yml` provides a lightweight observer deployment, distinct from the future coding executor service. It contains no Codex CLI, Git executable, host credentials, Docker socket or production mounts. Its executor has no network; its filesystem is read-only apart from its own state and 16 MiB temporary space. Each container is capped at 128 MiB RAM, 0.25 CPU and 32 processes; Docker logs rotate at 2 × 5 MiB. A container listener on 0.0.0.0 is explicitly permitted only inside this isolated deployment; the host port must bind loopback or the exact Tailscale address, never wildcard.

Prepare `state/control` owned by numeric UID/GID 10001, `state/control/executor.json` with `isolated_account_verified:false`, and `state/panel.env` with a fresh secret at mode 0600. The Compose env file is deliberately untracked and never printed by operational checks. Start only this Compose project. Docker must be enabled at boot; `restart:unless-stopped` restarts services after daemon/host restart. Verify using `docker compose -f compose.control.yml restart` and database state readback. This tests container restart, not an actual OS reboot.

This observer does **not** perform autonomous coding. It preserves roadmap/control state, exposes the private authenticated panel and records the provisioning block. Enabling coding requires the separate isolation/authentication gate; changing a flag in this image is insufficient because Git/Codex are absent. Stop or rollback only `openplaud-dev` containers; preserve `state/`. The host-mounted state has no hard disk quota yet and must be monitored.
