# YtPop â€” Runbook (S14)

Local-first ops: one Windows machine, no cloud, no containers.

## 1. Prerequisites

```powershell
node --version   # 22+
python --version # 3.12+
ffmpeg -version; ffprobe -version
ollama --version # optional until S10+ flows (editorial/summaries)
```

Models are pulled on first use (whisper `base`, MiniLM, qwen per
`configs/default.yaml`). First transcribe/cluster/plan is slow once.

## 2. Configure

```powershell
Copy-Item .env.example .env
# set YOUTUBE_API_KEY for live discovery (S3), else pipelines run on local DB
# YTPOP_DEMO_MODE stays true until a human clears publishing (S12)
# YTPOP_SCHEDULER=true enables the 24/7 loop (S13)
```

## 3. Run (dev)

```powershell
# backend
Set-Location apps/api
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# frontend (second shell)
npm run dev --workspace=apps/desktop

# desktop shell
npm run electron:dev --workspace=apps/desktop
```

Health: `GET /api/v1/health` + `/api/v1/health/dependencies`
(api/database/youtube/whisper/ollama/ffmpeg).

## 3b. YouTube API key

Discovery (S3) is the only stage that needs a key. Without it, every
pipeline stage still works on locally seeded data; only `DISCOVER` fails
with `not configured`.

```powershell
Copy-Item .env.example .env      # then set YTPOP_YOUTUBE_API_KEY
```

Names carry the `YTPOP_` prefix (pydantic-settings `env_prefix`), so
`YTPOP_YOUTUBE_API_KEY`, not `YOUTUBE_API_KEY`. The backend reads the repo
`.env` on startup, and a **packaged** install also reads
`%APPDATA%\YtPop\data\.env` (that one wins), so you can configure an
installed app without touching the checkout.

## 3c. Live E2E (real YouTube)

Opt-in, skipped automatically when the key is missing:

```powershell
$env:YTPOP_YOUTUBE_API_KEY = "<key>"
npx playwright test e2e/live-discovery.spec.ts
```

Seeds an empty temp DB, calls `POST /sources/discover` for real (1 quota
unit), and asserts the dashboard sections fill from live snapshots.

## 4. Packaged app (win-unpacked)

```powershell
npm run dist --workspace=apps/desktop    # release\win-unpacked\YtPop.exe
```

- `--dir` (win-unpacked) is the primary artifact; `npm run dist:win`
  builds the NSIS installer for new machines.
- `extraResources` bundles `apps/api` + `configs/` into
  `release/win-unpacked/resources/`, so the exe runs the real backend itself.
- The shell picks a **free port** (8000 is frequently taken by other
  projects on this machine) and passes it to the renderer through the
  preload, so both dev and packaged builds use the same `dist/`.
- Packaged data lives in `%APPDATA%\YtPop\data` (never inside the read-only
  install dir); logs go to `%APPDATA%\YtPop\logs\electron.log` (and
  `%TEMP%\ytpop-main.log` while diagnosing startup).
- Requires `python` + FFmpeg on PATH (the backend is not bundled yet).

## 5. E2E (golden fixture + packaged exe)

```powershell
npm run test:e2e
```

`apps/desktop/e2e/` seeds a deterministic DB (no network, no LLM) and drives
the actual Electron app, asserting it is not blank and renders golden data
(topics, sources + rights badge, transcript, episode, ops). `packaged.spec.ts`
adds the same check against the built `.exe`; `app.spec.ts` runs the dev shell
against a fixture API. `YTPOP_SKIP_BACKEND=1` makes the shell adopt an
existing API instead of spawning one.

## 6. Tests & migrations

```powershell
Set-Location apps/api
python -m pytest tests/ -q
python -m alembic upgrade head
python -m alembic downgrade -1; python -m alembic upgrade head
Set-Location ../..
npm run test --workspace=apps/desktop
```

## 7. Limits (configs/default.yaml + workers)

Concurrency: transcription 1, vision 1, editorial 1, render 1 â€” raise only
after measuring. Expensive order: transcribe â†’ vision â†’ LLM â†’ render.
Cheap filters first; vision/large models on finalists only.

## 8. Common failures

| Symptom | Cause â†’ fix |
|---|---|
| `DISCOVER` job FAILED "not configured" | No `YOUTUBE_API_KEY` â€” pipelines run on local DB only |
| `transcribe` empty segments | Sine/silence input â€” whisper needs speech; SAPI fixture in S5 logs |
| Render QA `resolution` fail | Preset mismatch â€” check `configs/render.yaml` vs source AR |
| `subtitles ... Invalid argument` | Absolute Windows path in filter â€” render runs `cwd=data/` + relative ASS (S9) |
| `drawtext fontfile` parse error | Drive-colon bug â€” card titles ride as caption events, no drawtext |
| faster-whisper `metadata_errors` | `av>=19` â€” pinned `av<19` in `pyproject.toml` |
| qwen `<think>` breaks JSON | `think:false` + think-strip in `ollama_service` (S10) |
| tsc `-p electron` TS18003 | Use `"files"` not `"include"` in `electron/tsconfig.json` |
| electron-builder version error | Pin exact `electron` version (hoisted workspace) |
| publish-check always false | `YTPOP_DEMO_MODE=true` default â€” flip after human review |
| `alembic` not recognized | Use `python -m alembic` (Scripts not on PATH) |
| stray `.js` next to `.ts` | `npm run build` emits in place â€” gitignored, harmless |

### Shared Ollama
This machine may run Ollama for other projects. When another consumer holds
the model, requests queue and can exceed short timeouts. The adapter now
defaults to **900s** with **one retry**, so pipelines wait rather than fail.
If you still time out, wait for the other project to finish or set
`YTPOP_OLLAMA_TIMEOUT_SECONDS` higher. Watch `ollama ps` for active models.
## 9. Data layout

`data/` is gitignored. Inspectable per stage: `raw/`, `media/`,
`transcripts/*.json`, `clips/`, `storyboards/`, `captions/`,
`renders/`, `database/mega_clipper.db`. Every artifact has a DB row.
Logs carry `[episode/job/source/stage]` correlation â€” grep those first.

## 10. Train the clip ranker (D4)

Review decisions in the app produce labelled feature vectors
(`moments.features_json` + `moment_feedback`). Train locally, no GPU, no
extra dependencies:

```powershell
Set-Location apps/api
python -m app.domain.clipping.training --out data/models/ranker.json
# refuses to run with <10 labelled rows or only one class
```

Then enable it in `configs/scoring.yaml`:

```yaml
learned_ranking:
  enabled: true
  path: data/models/ranker.json
```

Rules the trainer follows (deliberately conservative):
- labels: APPROVED / PERMISSION_GRANTED / USER_OWNED / LICENSED /
  CREATIVE_COMMONS / PUBLIC_DOMAIN -> 1; REJECTED -> 0;
  TRIMMED / NOTED skipped (ambiguous about the window itself).
- features: the exact vector persisted at candidate creation (keyword feats,
  duration, wps, semantic/visual/llm scores), standardized with the mean/std
  stored in the weights file.
- logistic regression is pure Python, deterministic (no shuffling), L2
  penalty 0.01, 400 batch-GD iterations.
- inspect what the model thinks via `GET /api/v1/feedback/export?format=csv`
  before trusting weights.
