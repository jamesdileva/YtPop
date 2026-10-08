# YtPop — Runbook (S14)

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

## 4. Packaged app

```powershell
npm run dist --workspace=apps/desktop        # release\win-unpacked\YtPop.exe
npm run dist:win --workspace=apps/desktop    # NSIS installer (slow)
```

The shell spawns `python -m uvicorn` on launch; Python + FFmpeg must be
on PATH (backend is not bundled — see roadmap future work).

## 5. Tests & migrations

```powershell
Set-Location apps/api
python -m pytest tests/ -q
python -m alembic upgrade head
python -m alembic downgrade -1; python -m alembic upgrade head
Set-Location ../..
npm run test --workspace=apps/desktop
```

## 6. Limits (configs/default.yaml + workers)

Concurrency: transcription 1, vision 1, editorial 1, render 1 — raise only
after measuring. Expensive order: transcribe → vision → LLM → render.
Cheap filters first; vision/large models on finalists only.

## 7. Common failures

| Symptom | Cause → fix |
|---|---|
| `DISCOVER` job FAILED "not configured" | No `YOUTUBE_API_KEY` — pipelines run on local DB only |
| `transcribe` empty segments | Sine/silence input — whisper needs speech; SAPI fixture in S5 logs |
| Render QA `resolution` fail | Preset mismatch — check `configs/render.yaml` vs source AR |
| `subtitles ... Invalid argument` | Absolute Windows path in filter — render runs `cwd=data/` + relative ASS (S9) |
| `drawtext fontfile` parse error | Drive-colon bug — card titles ride as caption events, no drawtext |
| faster-whisper `metadata_errors` | `av>=19` — pinned `av<19` in `pyproject.toml` |
| qwen `<think>` breaks JSON | `think:false` + think-strip in `ollama_service` (S10) |
| tsc `-p electron` TS18003 | Use `"files"` not `"include"` in `electron/tsconfig.json` |
| electron-builder version error | Pin exact `electron` version (hoisted workspace) |
| publish-check always false | `YTPOP_DEMO_MODE=true` default — flip after human review |
| `alembic` not recognized | Use `python -m alembic` (Scripts not on PATH) |
| stray `.js` next to `.ts` | `npm run build` emits in place — gitignored, harmless |

### Shared Ollama
This machine may run Ollama for other projects. When another consumer holds
the model, requests queue and can exceed short timeouts. The adapter now
defaults to **900s** with **one retry**, so pipelines wait rather than fail.
If you still time out, wait for the other project to finish or set
`YTPOP_OLLAMA_TIMEOUT_SECONDS` higher. Watch `ollama ps` for active models.
## 8. Data layout

`data/` is gitignored. Inspectable per stage: `raw/`, `media/`,
`transcripts/*.json`, `clips/`, `storyboards/`, `captions/`,
`renders/`, `database/mega_clipper.db`. Every artifact has a DB row.
Logs carry `[episode/job/source/stage]` correlation — grep those first.

## 9. Train the clip ranker (D4)

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
