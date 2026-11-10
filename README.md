# OpenPlaud

Private, self-hosted audio intelligence, starting with recordings exported from Pixel Recorder.

**Status: development foundation, not a complete MVP or production installation.**

Implemented: durable development roadmap, authenticated private control panel, bounded Codex adapter, recovery records and isolated Git attempts; audio upload API, hash deduplication, local-only storage, filename search and HTTP Range playback. Audio jobs are queued but transcription is not configured. No paid AI calls are made by the application.

Read [product brief](docs/PRODUCT_BRIEF.md), [architecture](docs/ARCHITECTURE.md), [discovery](docs/DISCOVERY.md), [control-plane ADR](docs/adr/0001-control-plane.md) and [operations](docs/OPERATIONS.md).

## Development

Python 3.12 on Linux:

```sh
python3 -m venv .venv
.venv/bin/pip install -r requirements.lock
.venv/bin/python -m unittest discover -s tests -v
```

Generate separate random tokens of at least 32 characters and inject them through your secret manager or environment. Never put them in Git or command arguments. Set `OPENPLAUD_API_TOKEN` and `OPENPLAUD_PANEL_TOKEN` before launching:

```sh
.venv/bin/uvicorn openplaud.api:factory --factory --host 127.0.0.1 --port 8767
python3 -m openplaud.panel --state state --host 127.0.0.1 --port 8766
```

The library UI is on port 8767 and development control on 8766. No public binding. API upload accepts raw bytes with `Content-Type: application/octet-stream` and `POST /api/recordings?name=meeting.wav`. WAV, MP3, M4A, Ogg, FLAC and WebM container signatures are screened; this is not full decoder validation. Maximum 100 MiB/file and a provisional 100-recording UI/API capacity; production quotas and concurrent accounting remain pending. No pagination yet. Tokens stay in page memory; no persistent browser credential storage.

Seed the roadmap without invoking an agent (default is paused):

```sh
python3 -m openplaud.runner --repo . --state state --config executor.example.json --once
```

The usage configuration records the operator's authorization for at most **10 subscription invocations, 900 seconds each**, with no paid APIs. `isolated_account_verified` stays false until provisioning and isolation tests pass. Start paused; do not set it true just to bypass the provisioning gate.

## Boundaries

This release is for development. Multi-user auth, PostgreSQL migrations, Redis workers, transcribers, summaries, Calendar, Pixel synchronization, semantic search and PWA remain roadmap work. Neither systemd service has been installed by this change. A real reboot/disconnect test has not been performed. Browser visual/mobile QA has not been performed.

Reviewed task branches are not automatically integrated. Before enabling dependent tasks, inspect and integrate the accepted branch into the development checkout; the executor must remain paused during integration. Do not approve a task as DONE before its changes are integrated and its acceptance evidence has been inspected. Main is never merged automatically.
