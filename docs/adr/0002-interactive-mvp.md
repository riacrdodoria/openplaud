# ADR 0002: Interactive development and a resource-bounded local MVP

2026-11-10. Supersedes the autonomous-development requirement in ADR 0001 by explicit operator instruction: development continues in this chat directly on the WO4. No background coding agent, isolated Codex login or invocation allowance is required for this workflow. Existing development controller remains paused; it is not the product worker.

Deliver the single-user local MVP incrementally using the existing SQLite adapter, a single OS-locked Python audio worker, FastAPI and a responsive browser client. This avoids adding PostgreSQL/Redis/Next.js services while host capacity is constrained. Product worker durability uses atomic claims, bounded attempts, persisted results and restart recovery; no code-generation subprocesses. PostgreSQL/pgvector, Redis and a Next.js client remain scale-out work, not prerequisites for single-user audio processing.

Local transcription: faster-whisper base, CPU int8, two threads, one worker, no cloud fallback and no runtime model downloads. Models are provisioned separately. The model/provider and language are recorded. Diarization/voice identification is optional and remains outside this baseline; do not invent speaker identities.

Use evidence-linked extractive analysis as a deterministic fallback. Optional local Ollama analysis may improve summaries but must validate every cited segment and never invent ownership as a confirmed fact. Cloud providers are not enabled. Real OAuth/device configuration may require the operator; document these gates without treating mock integrations as live.

Original MVP criteria remain the reference. Delivering the core audio loop does not prove real Pixel export or Google OAuth integration. Account/device setup must be stated separately in release evidence.
