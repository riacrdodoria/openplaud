# ADR 0001: Development control plane separate from audio product

Accepted for development, 2026-11-10.

Use Python stdlib + SQLite WAL for a single-host roadmap controller. Serialize execution with flock and claim with BEGIN IMMEDIATE. systemd system services under a dedicated account provide persistence independent of login. tmux alone does not satisfy reboot recovery. No existing Docker database or network is reused.

Codex CLI 0.166.0 installed on the host supports exec, --json and --sandbox workspace-write. Official documentation: https://learn.chatgpt.com/docs/non-interactive-mode . Authentication currently uses a ChatGPT subscription. Operator authorized at most ten 900-second invocations, no paid APIs. This is an invocation/time allowance, not a guarantee about subscription quotas. Authentication expiry or quota errors fail the attempt; never switch to a paid API or disable sandbox/approvals.

Start paused. AI requires verified isolated account and explicit usage configuration. Each attempt gets a Git branch/worktree and before/after SHA. Interrupted attempts become BLOCKED for inspection rather than being blindly replayed. A successful generic suite moves to REVIEW, never DONE. Acceptance review must verify task-specific evidence. No automatic merge to main. No remote arbitrary-command endpoint.

Current limitations: automatic repair retries, safe application of sensitive approvals, redacted streamed Codex logs, notification delivery, memory sampling, log retention, automatic integration of reviewed commits, and reboot validation are not complete. Raw Codex logs may contain private data and are not exposed by the panel. The panel records sensitive requests; it cannot execute them. Instructions are recorded as audit entries, not executed as commands. REVIEW acceptance is a single-operator capability, not multi-role authorization.

Product architecture remains FastAPI + PostgreSQL/pgvector + Redis + Next.js. SQLite audio-domain prototype is a development adapter pending migrations. No borrowed application source. No local model downloads on the resource-constrained host during discovery.
