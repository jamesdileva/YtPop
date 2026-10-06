# YtPop — Worklog

> Append-only. One `## S{N}` section per sprint, in order.
> Template per entry: Planned / Did / Verified / Next / Blockers / Commit.
> Paste test output + manual proof under Verified. Link commits by hash.

## S0 — 2026-10-05 — Repo & docs baseline (done)

### Planned
- Review `architecture.md`, `implementation-guide.md`, `roadmap.md`.
- Expand `roadmap.md` §26 with detailed S0–S14 sprints + exit goals + milestone linkage.
- Create `agents.md` (per-sprint ritual: plan+scope+implement+verify → worklog+commit+push).
- Create `worklog.md` (this file).
- `git init`, initial commit, `gh repo create YtPop --public`.

### Did
- [x] Docs reviewed (arch 1229 lines, impl 1315 lines, roadmap 1034 lines baseline).
- [x] `roadmap.md`: added milestone→sprint table (§23) + new §26 Sprint Plan S0–S14 with Goal/Scope/Tasks/Verification/Exit per sprint + dependency map.
- [x] `agents.md` created with sprint ritual, scoping/implementation rules, test matrix, DoD.
- [x] `worklog.md` created.

### Verified
- `Test-Path .git` → True, `git log --oneline -3` → `3b2e885 S0: chore(repo): init YtPop baseline docs`.
- `gh repo view --json name,visibility` → `YtPop`, public, `https://github.com/jamesdileva/YtPop`.
- `git status` → clean, `main` tracks `origin/main`.
- Manual: `roadmap.md` §26 + §23 table, `agents.md`, `worklog.md`, `README.md`, `.gitignore`, `.env.example` present.

### Next
- Start S1 (Foundation) per roadmap §26: `apps/api` health + Electron shell + tests.

### Blockers
- None.

### Commit
- `3b2e885 S0: chore(repo): init YtPop baseline docs` (8 files, 4285 insertions).
- Follow-up: `S0: docs(worklog): mark S0 done with repo evidence`.

## S1 — 2026-10-06 — Foundation: Electron + React + FastAPI health (done)

### Planned
- Backend: `apps/api` FastAPI + `/api/v1/health` + `/health/dependencies` + `pydantic-settings` + `structlog`.
- Frontend: `apps/desktop` Electron shell (spawns backend) + Vite React TS Dashboard with `useHealth()` badge.
- Tests: `pytest test_health.py`, `vitest App.test.tsx`, `tsc --noEmit`, live `uvicorn` curl proof.

### Did
- [x] `apps/api/{pyproject.toml,app/config.py,app/main.py,app/api/routes/health.py,tests/test_health.py}`
- [x] `apps/desktop/{package.json,vite.config.ts,vitest.config.ts,tsconfig.json,index.html,electron/{main,preload}.ts,renderer/src/{App,useHealth,main,test-setup}}`
- [x] Root `package.json` workspaces + `configs/default.yaml` (workers concurrency=1, clipping/episodes/render defaults)
- [x] `npm install` (249 pkgs), backend deps via pip

### Verified
- `pytest tests/test_health.py -v` → `2 passed` (test_health, test_health_dependencies_shape).
- `npm run test --workspace=apps/desktop` → `Test Files 1 passed, Tests 2 passed` (getHealthUrl + App badge, vitest v2.1.9).
- `npx tsc --noEmit -p tsconfig.json` → clean (exit True, no errors).
- Manual live: `uvicorn app.main:app --port 8000` → `GET /api/v1/health` = `{"status":"ok","version":"0.1.0"}`; `/health/dependencies` = api ok, others not_configured (expected S1).
- Frontend badge: mocked fetch test shows `API: ok (0.1.0)`; dev flow = Electron `main.ts` spawns backend + loads `http://127.0.0.1:5173`.

### Next
- S2 Database + Migrations per roadmap §26 (SQLAlchemy models, Alembic, test_source CRUD).

### Blockers
- None. Note: `npm install` pulls `electron` binary (~large) — expected; deprecation warnings for `whatwg-encoding`/Vite CJS are upstream noise.

### Commit
- `4a0923b S1: feat(api,desktop): foundation health loop` (27 files, Electron+React+FastAPI health).

## S2 — 2026-10-06 — Database + Migrations (done)

### Planned
- SQLAlchemy 2 models for 10 tables per `architecture.md` §6.
- Alembic from day one (up/down/up green, no manual schema edits).
- Minimal Sources API: `POST /sources`, `GET /sources`, `GET /sources/{id}`.
- `health/dependencies` probes real DB.

### Did
- [x] `apps/api/app/db/{base,models,database}.py` — Source, TrendEvent, TrendSource, Transcript, Moment, RightsRecord, Episode, EpisodeSegment, Render, Job
- [x] `database.py` resolves `data/database/mega_clipper.db` to repo root, `init_db()` creates dirs
- [x] `apps/api/{alembic.ini,alembic/env.py,alembic/script.py.mako}` + revision `deaadcfd8d2e s2 init core tables`
- [x] `apps/api/app/api/routes/sources.py` + registered in `main.py`; `pyproject.toml` += sqlalchemy, alembic
- [x] `apps/api/tests/test_db.py` (tables-exist + create/read + 404, isolated in-memory DB)

### Verified
- `python -m alembic downgrade -1` → only `alembic_version` left; `upgrade head` → all 10 tables back (`sources, trend_events, trend_sources, transcripts, moments, episodes, episode_segments, jobs, rights_records, renders`); DB 98304 bytes.
- `pytest tests/test_db.py tests/test_health.py -v` → `5 passed`.
- Live (port 8001, real DB): `/health/dependencies` → `database:ok`; `POST /sources` → id 1 `DISCOVERED`; `GET /sources/1` round-trips; scratch row deleted after (`remaining: 0`).
- `git status` shows DB file ignored (not staged) — `.gitignore` holds.

### Next
- S3 YouTube Discovery per roadmap §26 (adapter + snapshots + quota guard, mocked tests).

### Blockers
- None. Note: `alembic` exe not on PATH in this shell — use `python -m alembic`.

### Commit
- `91a41fc S2: feat(db,api): versioned schema + sources CRUD` (15 files).

## S3 — 2026-10-06 — YouTube Discovery (done)

### Planned
- Thin YouTube Data API adapter (mostPopular/search/video/channel/categories) with quota costs.
- `source_snapshots` + `discovery_runs` tables, velocity math, quota guard, trend scoring.
- Routes: `POST /sources/discover`, `POST /sources/search`, `POST /trends/discover`, `GET /trends`, `GET /trends/{id}`.
- Dashboard renders Trending now / Recently rising / Fastest growing / Top categories.
- All tests mocked (no live quota in CI).

### Did
- [x] `app/config.py` += `youtube_api_key`, `youtube_quota_daily_budget` (env `YTPOP_*`); `httpx` → runtime dep
- [x] `app/db/models.py` += `SourceSnapshot`, `DiscoveryRun`; migration `2eaa7f7b18a5` (chains on `deaadcfd8d2e`)
- [x] `app/services/youtube_service.py` — normalize, ISO8601 duration, costs (search=100, rest=1), `YouTubeAPIError`
- [x] `app/domain/discovery/service.py` — upsert+snapshot, velocity (views/hr), `compute_trend_score`, quota guard (429), 4 sections
- [x] `app/api/routes/trends.py` + registered; `get_youtube_service` injectable for tests
- [x] Frontend `hooks/useTrends.ts` + 4 Dashboard sections; `App.test.tsx` routes fetch by URL + `cleanup` fix
- [x] `tests/discovery/` — 17 tests (adapter 7, domain 7, routes 3)

### Verified
- `pytest tests/ -q` → `22 passed` (5 prior + 17 new).
- `vitest` → `4 passed`; `tsc --noEmit` clean.
- Migration: `downgrade -1` drops 2 tables, `upgrade head` restores; head `2eaa7f7b18a5`.
- Live (port 8002, real DB, seeded 25 sources × 2 snapshots, no API key used): `GET /trends` → 4 sections, top `s3live24`, categories 9/8/8; `POST /trends/discover` → updated 25; deps `database:ok`. Seed cleaned (`remaining: 0`). No `YTPOP_YOUTUBE_API_KEY` set — live-API discover untested, adapter covered by mocks.

### Next
- S4 Media Ingestion per roadmap §26 (FFmpeg probe/normalize/audio/thumb, `USER_OWNED` fixtures only).

### Blockers
- None.

### Commit
- `9f24b2b S3: feat(discovery): mostPopular + quota guard + trends` (19 files).

## S4 — 2026-10-06 — Media Ingestion (done)

### Planned
- FFmpeg adapter (arg-arrays only, path guard to `data/`), probe/normalize/16kHz-audio/thumb.
- `media_assets` table + migration, `POST /sources/{id}/analyze` (probe-only) with rights-basis gate.
- `ffmpeg` in `health/dependencies` via `shutil.which`.
- Tests on tiny lavfi fixtures; negatives for traversal/corrupt/bad-basis.

### Did
- [x] `app/services/ffmpeg_service.py` — `run_cmd` (shell=False), `resolve_data_path`, `probe`, `normalize`, `extract_audio`, `extract_thumbnail`
- [x] `app/services/media_ingestion.py` — `check_basis` (USER_OWNED/LICENSED/CC/PD), `verify_media`, `probe_source`, `ingest_source` (4 assets + rights row)
- [x] `MediaAsset` model + migration `0de9da1a452c` (chains on `2eaa7f7b18a5`)
- [x] `POST /sources/{id}/analyze` (400 traversal/corrupt/basis, 404 missing source); ffmpeg health probe
- [x] `tests/test_ingestion.py` — 10 tests incl. metachar-filename (arg-array proof) + repo-root regression test

### Verified
- `pytest tests/ -q` → `32 passed` (22 prior + 10 new).
- Migration: `downgrade -1` drops `media_assets`, `upgrade head` restores; head `0de9da1a452c`.
- Live (:8003, lavfi fixture as USER_OWNED stand-in): analyze 200 `{duration 3.0, 320x240, a+v, asset 1}`; traversal → 400; deps `ffmpeg:ok database:ok`. Seed + fixture cleaned.
- Bug found by live proof: `repo_data_dir()` used `parents[3]` → wrote to `apps/data/`. Fixed to share `repo_root()` from `database.py` + regression test; stray tree removed, DB rows cleaned.

### Next
- S5 Transcription per roadmap §26 (faster-whisper → segments + `transcript.json`, word timings preserved).

### Blockers
- None. ffmpeg N-124616 + ffprobe present on PATH.

### Commit
- `ef18187 S4: feat(ingestion): ffmpeg probe/normalize + analyze` (9 files).
