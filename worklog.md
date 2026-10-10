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

## S5 — 2026-10-06 — Transcription (done)

### Planned
- faster-whisper adapter (word timings preserved), transcribe domain with sha-idempotency + `transcript.json` + TRANSCRIBE job row.
- Routes `POST /sources/{id}/transcribe`, `GET /sources/{id}/transcript`; whisper in health deps.
- Sources/transcript UI section; real-model test on SAPI speech; mocked route tests.

### Did
- [x] `pyproject.toml` += `faster-whisper`, `av<19` (pin — see blockers); `config.py` += whisper model/device/compute
- [x] `app/services/whisper_service.py` — lazy model, word-level segments, `TranscriptionError`
- [x] `app/domain/analysis/service.py` — wav lookup (audio asset or extract from raw), sha256 skip unless force, json artifact, COMPLETED job row
- [x] `Transcript.audio_sha256` + migration `695eeee506a4` (server_default for non-empty tables)
- [x] Routes + `get_whisper_service` injectable; request `model` override honored (was silently ignored — fixed, see verified)
- [x] Frontend `useSources`/`useTranscript` + Sources section with segment timeline
- [x] `tests/transcription/` — 7 tests (2 real tiny-model incl. word-timing + monotonic asserts, 5 fake-service incl. skip/force/404/400)

### Verified
- `pytest tests/ -q` → `39 passed`; `vitest` → `5 passed`; `tsc` clean.
- Migration down/up cycle green, head `695eeee506a4`.
- Live (:8004, SAPI speech muxed to mp4 as USER_OWNED stand-in): analyze 200 → transcribe 200 `{lang en, 2 segs, skipped False}` → GET shows words; re-POST → `skipped True`; artifact `transcripts/{id}.json` 1495B; deps `whisper:ok`. Override check (:8005): `{"model":"tiny"}` → response `tiny`. All seeds/files/rows cleaned.
- Design note: `analyze` on a bare wav correctly 400s (verify requires a+v source media) — transcribe derives its own wav from the raw asset.

### Next
- S6 Clip Detection V1 per roadmap §26 (transcript windows + keyword/semantic scoring, golden test).

### Blockers
- None. Notes: `faster-whisper 1.2.1 + av 19` breaks (`metadata_errors` kwarg removed) → pinned `av<19` (18.1.0 verified). `python -m alembic` required (exe not on PATH).

### Commit
- `1760f62 S5: feat(transcription): whisper + transcript pipeline` (17 files).

## S6 — 2026-10-06 — Clip Detection V1/V2 (done)

### Planned
- Sliding-window candidates (5–90s) + keyword scoring (V1) + embedding similarity (V2, MiniLM).
- `configs/scoring.yaml` weights (no hardcode), store ALL candidates, MMR selection.
- Routes `POST /sources/{id}/find-moments`, `GET /moments`, `GET /moments/{id}`.
- Golden test (±2s), determinism, human-useful top-10 check.

### Did
- [x] `pyproject.toml` += `sentence-transformers`, `pyyaml`; `config.py` += `clip_embeddings` flag
- [x] `configs/scoring.yaml` — windows/weights/lexicons/min_wps
- [x] `app/domain/clipping/service.py` — windows, keyword feats (hook/relevance/novelty/emotion/payoff/completeness/dead_air/dependency), `Embedder` (lazy, L2-normed), MMR `select_top`, `find_moments` (fresh replace, all stored)
- [x] Moments routes + registered; `GET` lists score-desc
- [x] `tests/clipping/` — 11 tests (golden ±2s, determinism, all-stored, weights-editable, fake-embed semantic, real-embedder shape, route 200/404/400)

### Verified
- `pytest tests/ -q` → `50 passed` (39 prior + 11 new).
- Golden: known 7-seg transcript → top starts ≈10s ("final boss" hook) within ±2s.
- Live (:8006, 47s 8-utterance SAPI fixture, real embeddings): 12 segs → 53 candidates; top-10 all hook/emotion-led (scores 56–83), filler ("bread and milk", "Um, well") absent from top.
- Human check (top-10 vs random-10, seed 7): top wins — every top window holds a question/payoff/emotion peak; random set has 3–4 filler-led windows. Exit holds.
- Tuning note (not blocking): top-10 has 5 near-dupe windows (5.7–28/31/33s); MMR redundancy (25 × sim) < score spread (~82 vs ~68), so overlap persists. S7/S10 fix: non-overlap suppression or higher redundancy weight. Late hook ("Warning…secret", ~40s) also missed top-10 — same cause.
- No migration (moments table from S2), no frontend changes. Seeds/files/rows cleaned.

### Next
- S7 Clip Review UI per roadmap §26 (preview/trim/approve/reject + feedback capture, `PATCH /moments/{id}`).

### Blockers
- None. Note: pip downgraded setuptools 84→81 (st dependency) — harmless.

### Commit
- `d446d7d S6: feat(clipping): windows + keyword/semantic scoring` (12 files).

## S7 — 2026-10-06 — Clip Review UI (done)

### Planned
- `moment_feedback` table + moment review fields, PATCH decisions, FFmpeg preview slices, CORS, list filters.
- Review UI: queue + filters, score bars, trim inputs, approve/reject, video preview, keyboard shortcuts.
- 20-clip review proof with feedback verification.

### Did
- [x] `Moment` += notes/category/is_best; new `MomentFeedback` (decision/reason/orig+adjusted/at); migration `bad99375cae3` (server_defaults for non-empty tables)
- [x] `app/domain/clipping/review.py` — `review_moment` (validates trim/status, always writes feedback), `build_preview` (ultrafast slice, cached, `preview` asset)
- [x] `PATCH /moments/{id}`, `POST /moments/{id}/preview` (rebuild), `GET /moments/{id}/preview` (FileResponse, builds if missing), list filters (status/type/min_score)
- [x] CORS for localhost/127.0.0.1 (fetch + future video) + preflight test
- [x] Frontend `useMoments` + `Review` (queue, filters, bars Score/Hook/Emotion/Novelty/Context, trim, reason, video `preload=none`); shortcuts A/R/J/K/Z/X/C/V; App renders Review
- [x] `tests/clipping/test_review_api.py` — 7 tests; `Review.test.tsx` — 5 tests (incl. keydown a/j)

### Verified
- `pytest tests/ -q` → `57 passed`; `vitest` → `10 passed`; `tsc` clean.
- Migration down/up cycle green, head `bad99375cae3`.
- Live (:8007, 20 seeded moments + lavfi media): queue 20 → 8 approve + 7 reject + 5 trim in 0.2s; filters return 8/7; preview serves 297KB mp4; **20 feedback rows** with decisions/reasons/adjusted times. Seeds/files/rows cleaned.
- Speed note: API-side review is instant; human speed comes from keyboard flow (A/R/J/K, no mouse per decision) + `preload=none` video. The <10min/20-clips bar is a UI-ergonomics claim covered by shortcut tests, not timed with a human.

### Next
- S8 Episode Builder per roadmap §26 (manual timeline: order/trim/intro-outro, persist order server-side).

### Blockers
- None.

### Commit
- `2ad9c63 S7: feat(review): queue UI + patch/preview/feedback` (12 files).

## S8 — 2026-10-07 — Episode Builder (done)

### Planned
- Episodes/segments CRUD, server-side order, duration roll-up + over/under, template stub.
- Timeline UI (add/reorder/delete, duration bar); 5-clip build/reorder/reload proof.

### Did
- [x] `configs/editorial.yaml` — daily_highlights/weekly_recap/shorts templates
- [x] `app/api/routes/episodes.py` — create (template intro/outro cards), list/get (roll-up), patch, add-segment (APPROVED-only moments, duration snapshot), patch/duplicate/delete segment, rebuild (exact-set reorder)
- [x] Frontend `useEpisodes` + `Episodes` (create, open timeline, up/down/delete, add-by-moment-id, over/under bar)
- [x] `tests/test_episodes.py` — 6 tests (template, 5-clip+reorder+reload, wrong-set 400, unapproved 400, trim/dup/delete, patch/404s)

### Verified
- `pytest tests/ -q` → `63 passed`; `vitest` → `13 passed`; `tsc` clean.
- Live (:8008): create → 2 cards; +5 clips → actual 49.0 (9+40), over/under −1151; reversed rebuild → reload order intact `[None,5,4,3,2,1,None]`. Seeds cleaned.
- Fixes during sprint: duplicate placed after next segment (sequence+1 + id tiebreak) → same-sequence + id tiebreak puts clone directly after original; frontend `req()` needs `ok:true` mocks.
- No migration (tables from S2).

### Next
- S9 Rendering + Captions per roadmap §26 (filter-graph render, presets, QA probe, in-app playback).

### Blockers
- None.

### Commit
- `ce2194c S8: feat(episodes): manual timeline builder` (10 files).

## S9 — 2026-10-07 — Rendering + Captions (done, M4 complete)

### Planned
- Filter-graph render (normalize+concat+loudnorm), 3 presets, ASS sidecar + burn-in, render QA, file serving, in-app playback.

### Did
- [x] `configs/render.yaml` — preview_720p/youtube_1080p/vertical_1080x1920
- [x] `app/domain/rendering/service.py` — `render_episode` (cards via color+aevalsrc, clips re-encoded to preset, concat, loudnorm, ASS burn), `build_ass`/`words_to_events` (card titles stand alone), `qa_render` (9 checks), FAILED rows + RENDER jobs recorded
- [x] Routes: `POST /episodes/{id}/render`, `GET /renders/{id}` (live QA), `GET .../file`, `GET /episodes/{id}/renders`, `POST .../cancel` (409 terminal)
- [x] `ffmpeg_service.run_cmd` += `cwd` param
- [x] Frontend: preset select + Render button + player + QA line + error surface (2 new tests)
- [x] `tests/rendering/` — 9 tests incl. full QA asserts, failure-recorded-then-retry, 404/400 paths

### Verified
- `pytest tests/ -q` → `72 passed`; `vitest` → `15 passed`; `tsc` clean. No migration (tables from S2).
- Live (:8009, 3×6s clips + intro/outro cards): render 200 in 2.3s, QA 9/9 green (22.0s, 1280x720, 30fps, captions, clean decode), 7.2MB mp4 served. Seeds/files/rows cleaned.
- M4 done: timeline → render → in-app playback path proven (player wired to `/renders/{id}/file`).
- Build quirks found by testing (all fixed + logged):
  1. drawtext `fontfile=C\:/...` fails to parse on this build → cards carry titles as caption events instead (no drawtext).
  2. subtitles filter rejects ANY absolute Windows path (quoted/escaped/relative-drive all fail; relative works) → render runs with `cwd=data/` + relative ASS path.
  3. concat needs interleaved `[v][a]` pairs, not all-v then all-a.
  4. Card audio input is a 2nd input (`[n+1:a]`), not `[n:a]`.
  5. `load_presets` used `parents[4]` from the deeper module → shared `repo_root()` (same S4 bug class).
  6. Failures must route through `fail()` or no FAILED row exists (retry test caught it).

### Next
- S10 Editorial AI per roadmap §26 (Ollama structured planning, Pydantic validation, ModelRouter).

### Blockers
- None.

### Commit
- `b84a219 S9: feat(rendering): timeline render + captions + QA` (14 files).

## S10 — 2026-10-07 — Editorial AI (done, M5 complete)

### Planned
- Ollama adapter (forced JSON), role→model routing, Pydantic-validated planning with repair retries, APPROVED-only eligibility.
- `POST /episodes/{id}/generate` applies plan to timeline + storyboard artifact; plan outline UI.

### Did
- [x] `configs/default.yaml` += models (classifier/summarizer qwen3:4b, editor qwen3.5:9b, vision qwen2.5vl:3b) + ollama host/timeout; `config.py` += ollama_host/editor_model
- [x] `app/services/ollama_service.py` — `chat_json` (format=json, think=false, temp 0), `ping`, `model_for` router
- [x] `app/domain/editorial/service.py` — `EpisodePlan` schema (clusters/order/transitions/context/ending/titles), `plan()` (structured summaries in, ≤2 repairs, unknown-id rejection), `apply_plan()` (replaces clips, keeps cards, intro context card + ending card, title set, storyboard json + asset row)
- [x] `POST /episodes/{id}/generate` (model override honored, 404/400 paths) + ollama in health deps
- [x] Frontend: Generate plan button + outline (title/clusters/order) in Timeline
- [x] `tests/editorial/` — 15 tests (adapter incl. think-strip, repair-then-ok, garbage-exhaustion, apply/skip, route 200/404/400)

### Verified
- `pytest tests/ -q` → `87 passed`; `vitest` → `16 passed`; `tsc` clean. No migration.
- Live (:8010, real qwen3:4b, 3 approved moments): 200 in 41s with **1 repair** → valid plan ("Score Tricks: The 30-Second Secret", cluster + order [1,2] + transition commentary applied, episode retitled). Seeds/artifact/rows cleaned.
- Real-behavior finds (both fixed before commit):
  1. qwen3 emits `<think>` blocks → `format=json` content unparseable. Fix: `"think": false` in request + `parse_json_content` strips think blocks with `{...}` fallback (Pydantic still validates).
  2. Request `model` override was silently ignored with default DI (same S5 bug class) → route builds the override service; proven (`tiny` check pattern reused).
- M5 done: approved moments → plausible outline → applied timeline, no manual ordering needed.

### Next
- S11 Trend Intelligence per roadmap §26 (embeddings → clusters → trend_events, velocity from S3 snapshots).

### Blockers
- None. Note: default editor model qwen3.5:9b is configured but live proof used qwen3:4b for speed; 9b path untested — same adapter, model name only.

### Commit
- `e2edfa4 S10: feat(editorial): ollama planning + generate` (16 files).

## S11 — 2026-10-07 — Trend Intelligence (done, M2+M6 complete)

### Planned
- Embeddings → single-link clusters → trend_events with 6-component velocity score; LLM topic summaries with offline fallback.
- `POST /trends/cluster`, `GET /trend-events`, Dashboard topic cards; weights in yaml.

### Did
- [x] `configs/default.yaml` += trends (threshold 0.55, min_sources 2, weights .25/.15/.15/.20/.15/.10, caps, half-life)
- [x] `app/domain/discovery/clustering.py` — cosine single-link clustering, score_cluster (views/eng velocity from snapshots, recency decay, cross-source, 3-snapshot momentum else neutral 50, novelty vs ACTIVE trends), overlap-50% trend update (no dupes), CLUSTER_TRENDS job row
- [x] Routes: cluster (summarize flag → Ollama summarizer, default keyword fallback), trend-events list with member counts + combined views
- [x] Frontend `useTopics` + topic cards (`🔥 topic · N videos · +V/h · M views · score`)
- [x] `tests/trends/` — 9 tests (A–E grouping, rerun-update, determinism, weights validation, singletons, real-embedding API grouping, empty DB)

### Verified
- `pytest tests/ -q` → `96 passed`; `vitest` → `17 passed`; `tsc` clean. No migration (tables from S2).
- Live (:8011, 20 seeded sources, real MiniLM + qwen3:4b summaries): 2 topics in 24s — 'Game Update Unveiled' (11 vids, +1.3M/h, 26M, 92.5) + 'Sourdough Mastery' (7 vids, +70.5k/h, 1.4M, 92.5). Seeds/rows cleaned.
- Honest observations (tuning debt, not blocking):
  1. Both topics scored exactly 92.5 — caps saturate (any velocity > cap = 100), hiding magnitude differences. Future: log-scale or higher caps.
  2. 18/20 sources assigned; 2 singletons fell below the 0.55 threshold and were ignored by design (threshold tunable).
- M2+M6 done: multi-video trends identified from DB, visible on Dashboard.

### Next
- S12 Rights Workflow per roadmap §26 (state machine server-side, publish blocker, evidence, research/demo-only mode).

### Blockers
- None.

### Commit
- `0c27802 S11: feat(trends): embedding clustering + velocity scoring` (10 files).

## S12 — 2026-10-07 — Rights Workflow (done)

### Planned
- Server-side state machine, reviewer-required approvals, expiry, evidence fields, publish blocker (source + episode), demo-mode default-deny, rights badge UI.

### Did
- [x] Migration `5c6fefe72545`: rights_records += reviewer, expires_at
- [x] `config.py` += `demo_mode=True` (YTPOP_DEMO_MODE); publishing blocked unless flipped by a human operator
- [x] `app/domain/rights/service.py` — transitions (UNKNOWN→REVIEW_REQUIRED/REJECTED→APPROVED/NEEDS_PERMISSION→PERMISSION_GRANTED; APPROVED↔REVIEW_REQUIRED/REJECTED; S4 bases as approved leaves), reviewer-required approvals, expiry, per-source + per-episode verdicts
- [x] Routes: GET/PATCH/review/publish-check + episode publish-check (404/400 paths)
- [x] Frontend: rights badge + "Rights basis: human review required." banner + Request-review button (stateful mock test)
- [x] `tests/rights/` — 9 tests (lifecycle, illegal jump, permission flow, revoke/reopen, expiry, demo-deny, S4-basis compat, episode block)

### Verified
- `pytest tests/ -q` → `105 passed`; `vitest` → `18 passed`; `tsc` clean; migration down/up green, head `5c6fefe72545`.
- Grep: no "fair use confirmed"/cleared-for-publish strings anywhere in app code.
- Live two-mode proof (:8012 default demo, :8013 demo-off):
  - Default UNKNOWN → blocked (demo + no-record reasons); review 200; UNKNOWN→APPROVED direct → 400 with allowed list.
  - Demo-off: approve (reviewer ed) → publishable True, zero reasons; episode with 1/2 cleared → blocked [id2]. Seeds/rows cleaned.
- Negative exit holds: no path represents uncleared material as cleared (UNKNOWN/no-record/expired/wrong-status/demo all block with explicit reasons).

### Next
- S13 Automation per roadmap §26 (PipelineOrchestrator, SQLite job queue + scheduler, one-button episode, Demo 3).

### Blockers
- None. Note: live-script console needed ASCII-safe printing (cp1252 vs →); app messages unaffected.

### Commit
- `5e034a6 S12: feat(rights): state machine + publish blocker` (13 files).

## S13 — 2026-10-07 — Automation (done, M7+M8 complete)

### Planned
- SQLite job queue (claim/run/retry/cancel/backoff/dedupe/priority bands), 8 stage handlers, daily-episode orchestrator, interval scheduler + background loop, jobs/pipeline routes, ops UI.

### Did
- [x] Migration `e56ee47295f0`: jobs.next_run_at (backoff)
- [x] `app/workers/queue.py` — enqueue (dedupe), atomic claim_next, complete/fail (exp backoff), retry, cancel, priority_for_velocity (100/70/30/5)
- [x] `app/workers/handlers.py` — REFRESH_SCORES/CLUSTER/DISCOVER/TRANSCRIBE/FIND_MOMENTS/DRAIN_ANALYSIS/GENERATE/RENDER + sync run_job; injectable Ctx (offline tests)
- [x] `app/workers/orchestrator.py` — scores→cluster→analysis→rights-filter→generate→render→QA→review, every stage a job, abort names the stage
- [x] `app/workers/scheduler.py` — 15/30/60m tick, self-healing (FAILED doesn't block), daemon loop behind YTPOP_SCHEDULER (lifespan)
- [x] Routes: jobs CRUD/run/retry/cancel, pipeline/daily-episode (model override), scheduler tick/status; `config.py` += scheduler flag; `default.yaml` += scheduler; `.env.example` documents DEMO_MODE/SCHEDULER
- [x] Frontend Ops: queue depth/failures, Generate-today's-episode button + stages, jobs list (2 tests)
- [x] `tests/test_jobs.py` (11) + `tests/test_pipeline.py` (3, incl. full fake-LLM + real-ffmpeg run)

### Verified
- `pytest tests/ -q` → `119 passed`; `vitest` → `20 passed`; `tsc` clean; migration cycle green.
- Demo 3 (:8014, all-real except pre-seeded approvals): 200 in 90s — refresh→cluster→TRANSCRIBE (real whisper on SAPI)→FIND_MOMENTS (real embeddings)→GENERATE (real qwen3:4b)→RENDER (real ffmpeg); draft episode + COMPLETED render; publishable False (demo gate holds); tick right after correctly enqueued only DRAIN_ANALYSIS (intervals honored, no dupes). All seeds/artifacts/rows cleaned.
- Scheduler loop (:8015, YTPOP_SCHEDULER=true): `scheduler_started` + tick enqueued all 3 in logs; its 3 QUEUED rows cleaned after.
- Known wart (not blocking): service-level TRANSCRIBE/RENDER rows duplicate queue rows (S5/S9 pattern predates the queue) — double counts job types in ops. Follow-up: services skip own row when run under a queue job.

### Next
- S14 QA / Packaging / Learning prep per roadmap §26 (full gate, Demos 1–3 sign-off, Electron Builder, feedback export, v0.1.0-mvp tag).

### Blockers
- None.

### Commit
- `34fc0ba S13: feat(automation): job queue + orchestrator + scheduler` (20 files).

## S14 — 2026-10-07 — QA / Packaging / Learning prep (done, MVP LOOP COMPLETE)

### Planned
- Feedback dataset export, scoring V3–V5 flags + cheap vision detector, packaging, runbook, full gate, Demo 1/2 sign-off, `v0.1.0-mvp` tag.

### Did
- [x] `GET /feedback/export` (json/csv) — one row per review action with scores + decisions for the future learned ranker
- [x] `app/domain/clipping/vision.py` — finalists-only luma-motion/interest detector (ffmpeg gray frames ×1fps + Pillow-free pure math)
- [x] `app/domain/clipping/ranker.py` — file-backed learned weights; identity passthrough until a weights file exists
- [x] `find_moments` += `vision` / `llm_scoring` / `learned_ranking` flags (all default **off**, V1/V2 path unchanged) + finalist-only execution
- [x] `configs/scoring.yaml` flags; `RUNNING` → `COMPLETED` for moments list visual score; review UI unaffected
- [x] Packaging: `electron-builder` config (appId/productName/win nsis), `dist` + `dist:win` scripts; electron tsconfig fix (`"files"` + esModuleInterop) so build no longer breaks packaging
- [x] `runbook.md` (prereqs/config/run/package/tests/limits/failures/data layout) + shared-Ollama note
- [x] `.env.example` updated; `runbook` linked from README
- [x] Tests: `tests/clipping/test_scoring_evolution.py` (7) + 2 ollama retry tests → **128 backend**, 20 frontend

### Verified
- Full gate: `pytest -q` → `128 passed`; `vitest` → `20 passed`; `tsc` clean; migration chain 11 deep, down/up green; no fair-use claim strings.
- **Demo 1** (live, permitted fixture): analyze 31s → transcribe 8 segs → 25 candidates → approve 3 → 3-clip episode → render 11s QA 9/9 → 29.7MB playback. PASS.
- **Demo 2** (live, 20 sources): cluster 2 topics → 60 candidates → approve top-15 → qwen3:4b assembled "Game Update Frenzy: The Secret Code Challenge" (11 clips) → render QA ok 126s. PASS (resume run after fixing shared-Ollama handling).
- **Demo 3** (S13): one-button pipeline 6/6 stages, real whisper/embeddings/qwen/ffmpeg. PASS.
- Packaging smoke: `YtPop.exe` (unpacked, 180MB) launches and stays alive; NSIS wired.
- Shared-Ollama finding (user-flagged): qwen3:4b took **551s** while other projects queued. Fixed with 900s default timeout + 1 retry (retry now surfaced as `ollama_timeout_retry`), configurable via `YTPOP_OLLAMA_TIMEOUT_SECONDS`; runbook documents waiting on the other consumer.
- Build artifact fix: `npm run build`'s `tsc` emitted `.js` next to `.ts` sources — gitignored via `apps/desktop/**/*.js`, cleaned from tree.

### Next (post-MVP)
- Post-MVP tuning (documented debt): non-overlapping clip windows, log-scale trend caps, dedupe service vs queue job rows, backend bundling in the installer, feedback→weights training.

### Blockers
- None.

### Commit
- `d5d5b7b S14: chore(qa): feedback export, packaging, runbook` (15 files).
- Tag: `v0.1.0-mvp` (pushed) — MVP loop S1–S14 complete, Demos 1–3 signed off.

## D1 - 2026-10-08 - non-overlapping clip windows (done, post-MVP debt)

### Planned
- Stop near-duplicate time windows crowding top-k (S6 debt): greedy score-ordered
  selection with overlap suppression, driven by config.

### Did
- [x] `app/domain/clipping/service.py` - split `select_top` into `_mmr_order` +
  `_overlap_ratio` + `_suppress_overlaps`; `select_top` now applies suppression
- [x] `configs/scoring.yaml` - `windows.non_overlap: true`, `windows.max_overlap: 0.5`
- [x] Tests: suppression unit (heavy overlap), flag-off equivalence, near-duplicate
  guarantee under forced short clips, end-to-end distinctness on a 12-segment
  transcript, all-candidates-still-stored
- [x] Updated two expectations that assumed top_k is always filled exactly

### Verified
- `pytest tests/clipping` -> 31 passed; full gate `pytest -q` -> 134 passed;
  `vitest` -> 20 passed. No migration.
- Live (52s SAPI clip, 8 utterances, real whisper + MiniLM, 55 candidates):
  heavy-overlap pairs went 37 -> 5, near-duplicate (>0.9) pairs 0, distinct
  picks 5 for a requested 10 on a short clip; the 6.3-28/31/33/37 and 0-28/31
  duplicate families are gone.
- Policy (tests document it): strict `max_overlap`, then a single relaxation to
  0.9; never relax to accept-all, so short clips return fewer distinct
  candidates instead of padding with copies.
- Note: config keys sit in `windows.non_overlap/max_overlap`, so the flag is
  runtime-tunable without code changes (agents.md config-over-code rule).

### Next
- Log-scale trend caps (D2), service vs queue job rows (D3).

### Blockers
- None.

### Commit
- `D1: feat(clipping): non-overlapping top-k selection`

## D2 - 2026-10-08 - trend scores stop saturating (done, post-MVP debt)

### Planned
- S11 debt: linear caps made every fast topic tie at 92.5 (component hits 100
  as soon as it reaches the cap, so magnitude differences vanish). Keep config
  knobs, keep determinism, let distinct magnitudes rank differently.

### Did
- [x] `app/domain/discovery/clustering.py` - `_component()` with `log_scale`
  switch: saturating `100*v/(v+cap)` (cap = half-saturation: cap -> 50, 9x -> 90,
  never ties) vs legacy linear `100*min(v/cap, 1)`
- [x] `configs/default.yaml` + defaults - `trends.log_scale: true`; applied to
  views_velocity, engagement_velocity and cross_source
- [x] Tests: curve semantics (0/50/90/monotonic), legacy-linear parity, and an
  end-to-end "big vs small" seed showing different scores

### Verified
- `pytest tests/trends` -> 13 passed; full gate `pytest -q` -> 138 passed;
  `vitest` -> 20 passed. No migration.
- Live (12 gaming + 8 cooking, real MiniLM clustering): 'Game Update Major'
  85.95 (+1.3M/h, views component 99.24) vs 'Sourdough Bread Baking' 79.34
  (+70.5k/h, 87.58) - distinct scores, and ordering unchanged.
- Ranking was not distorted: the #1 topic is still the fast one; only the
  magnitude gap is now visible (85.95 vs 79.34 instead of 92.5 vs 92.5).
- Before that run I tried `100*log1p(v/cap)/log(101)`; it mislabeled cap as the
  midpoint (cap scored 15, not 50) and pushed scores down ~7 points, so the
  final curve is algebraic saturation with an honest docstring.

### Next
- Service-level rows duplicating queue job rows (the item I called D3; the
  trend caps were D2).

### Blockers
- None.

### Commit
- `D2: feat(trends): saturating component curve` 

## D3 - 2026-10-08 - one job row per stage (done, post-MVP debt)

### Planned
- S13 wart: services wrote their own TRANSCRIBE/RENDER job rows even when the
  queue already owned one, so the ops view double-counted stages (a daily
  pipeline showed TRANSCRIBE x2, RENDER x2).

### Did
- [x] `app/workers/context.py` - contextvar `active_job_id` (+ set/reset tokens)
- [x] `app/workers/handlers.py` - `run_job` installs the job id for the handler
  call and resets it in `finally` (exception-safe, no leaks across runs)
- [x] `app/domain/analysis/service.py` - skips its TRANSCRIBE row when running
  under a job; direct calls keep writing their own row
- [x] `app/domain/rendering/service.py` - reuses the queue row under a job;
  the Render domain record is always created (one per render call)
- [x] `POST /jobs/{id}/run` now maps handler failures to 400 (was 409, which
  read as a state conflict); only "not QUEUED" stays 409
- [x] Tests: queue-run TRANSCRIBE/RENDER produce exactly one row each, contextvar
  does not leak, direct transcribe still writes its row, run-route status codes

### Verified
- `pytest -q` -> 141 passed; `vitest` -> 20 passed. No migration.
- Live (:8021): seeded source + approved moment + episode, then queue-ran
  TRANSCRIBE, FIND_MOMENTS and RENDER. Ops view: `{RENDER: 1, FIND_MOMENTS: 1,
  TRANSCRIBE: 1}`, `queue_depth = {COMPLETED: 3}`. Seeds/files/rows cleaned.
- Render domain rows remain per render call (2 after two renders), which is the
  intended history - only the duplicate *job* rows are gone.

### Next
- Backend bundling in the installer, then feedback-data to weights.

### Blockers
- None.

### Commit
- `D3: fix(workers): services reuse the queue job row`

## D4 - 2026-10-08 - feedback to learned weights (done, post-MVP debt)

### Planned
- Close the learning loop: review decisions -> trained ranker weights, with no
  new dependencies (packaging stays lean) and no silent auto-training.

### Did
- [x] Migration `83e435e70b31`: `moments.features_json TEXT DEFAULT ''` - the
  candidate feature vector now survives to the DB (only 5 of 14 features were
  recoverable before, which would have made training a guess)
- [x] `find_moments` persists the full vector (keyword feats + duration + wps +
  semantic/visual/llm scores) at candidate creation
- [x] `app/domain/clipping/training.py` - dataset builder, pure-Python logistic
  regression (batch GD, standardized, L2 0.01, 400 iters, deterministic), weight
  writer, CLI: `python -m app.domain.clipping.training --out <file>`
- [x] `ranker.apply` honors standardized weights (features/coefficients/bias +
  mean/std) and stays passthrough otherwise
- [x] `configs/scoring.yaml` `learned_ranking.path` defaults to
  data/models/ranker.json (still `enabled: false` - opt-in); `data/models/`
  gitignored with a .gitkeep
- [x] runbook section 9 documents the loop, label policy and caveats
- [x] `tests/clipping/test_training.py` - 7 tests (separable-signal fit,
  determinism, label mapping incl. TRIMMED/NOTED skipped, thin/single-class
  refusals, weights round-trip + apply ordering, missing-file safety,
  find_moments persistence)

### Verified
- `pytest -q` -> 148 passed; `vitest` -> 20 passed; migration down/up green.
- Live clean run (SAPI 90s clip, real tiny whisper + MiniLM, 39 candidates):
  editor policy "tight <=20s" -> 29 approved / 10 rejected -> export 39 rows ->
  trained (pos 29, neg 10) -> strongest learned feature `duration -4.31` (the
  policy), then apply: tight clip 41.8 vs long clip 26.1 with equal base scores.
  Seeds/files/weights cleaned.
- Two live-only lessons: (1) a crash before cleanup leaves rows behind, so the
  earlier double-counted export (78 for 39) was stale state, not a code bug -
  re-ran from a clean DB to confirm 39; (2) my first assertion guessed the wrong
  dominant feature, so the check now asserts the policy (duration sign + ordering)
  instead of a specific feature's sign.

### Next
- Packaging focus: win-unpacked (`--dir`) as the primary artifact, NSIS optional.

### Blockers
- None.

### Commit
- `D4: feat(clipping): train ranker from review feedback`

## D5 - 2026-10-08 - packaging (win-unpacked) + golden-fixture e2e (done)

### Planned
- Make win-unpacked the primary artifact, ship the real backend inside it, and
  prove the packaged app is not a blank screen with a deterministic e2e.

### Did
- [x] `repo_root()` / `repo_data_dir()` honor `YTPOP_ROOT` / `YTPOP_DATA_DIR`
  so a packaged shell can point the backend at bundled and writable files
  (`tests/test_paths.py`)
- [x] electron-builder `extraResources` bundles `apps/api` + `configs` into
  `resources/`; `files` unchanged; `win.target` = `["dir", "nsis"]` (dir first)
- [x] `electron/main.ts`: resolves bundled vs dev backend, picks a FREE port
  (8000 is taken by another project on this machine), hands it to the renderer
  at runtime via preload, health-gates logs, writes to a file instead of
  stdout (a GUI app writing to a closed pipe throws EPIPE and pops a dialog),
  `YTPOP_SKIP_BACKEND=1` to adopt an external API
- [x] `app.setName("YtPop")` + explicit `userData` - the scoped npm name sent
  data to `Roaming/@ytpop/desktop` (this was the "healthy but empty" bug)
- [x] packaged installs use `%APPDATA%\YtPop\data` for DB/artifacts, never the
  read-only install dir
- [x] vite `base: "./"` - Vite's default `/assets/...` 404s under `file://`,
  which was the actual blank screen
- [x] `useHealth` retries for ~30s so a cold backend no longer sticks on
  "API: checking"; renderer resolves the API base from the preload at runtime
- [x] `@playwright/test` e2e: `e2e/seed_golden.py` (deterministic DB, no
  network/LLM), `e2e/app.spec.ts` (dev shell vs fixture API) and
  `e2e/packaged.spec.ts` (the real `.exe`, seeds/restores userData)
- [x] runbook sections 4 + 4b; root `dev:ui` / `test:e2e` scripts

### Verified
- `pytest -q` -> 151 passed; `vitest` -> 40 passed; `tsc` clean
- `npx playwright test` -> 2 passed: dev shell and the packaged `.exe` both
  show `API: ok`, the golden topic (score 91.5 / 2.5M views), the source with
  its rights banner, the transcript, the golden episode and ops `done: 1`
- Live packaged run (manual): window opens, backend healthy on an ephemeral
  port, reads the seeded DB from `%APPDATA%\YtPop\data`
- Bugs found by the packaged-path work and fixed: Vite absolute `/assets`
  (blank screen), unregistered preload (renderer hit port 8000 = the other
  project), port collision + silent backend death, EPIPE crash dialog,
  scoped-name userData (empty data), stale `tsc`/`dist` reuse in e2e.

### Next
- Remaining known debt: bundle the Python backend itself (currently needs
  python + FFmpeg on PATH), NSIS installer icon/description metadata.

### Blockers
- None.

### Commit
- `D5: feat(packaging): win-unpacked + backend bundling + golden e2e`

## D6 - 2026-10-08 - youtube key wiring + live discovery e2e (done)

### Did
- [x] Backend now loads a repo `.env` (python-dotenv) and, for packaged
  installs, `%APPDATA%\YtPop\data\.env` (which wins), so the desktop shell
  gets keys without a checkout
- [x] Fixed `.env.example`: names carry the `YTPOP_` prefix - it previously
  said `YOUTUBE_API_KEY`, which would silently never be read
- [x] `e2e/live-discovery.spec.ts` - opt-in live E2E (skips without a key):
  real `POST /sources/discover` on an empty temp DB, asserts 10 rows imported
  for 1 quota unit, provider/external_id/status, score refresh, and the
  dashboard sections filling from live snapshots
- [x] runbook: YouTube key section (where to put it, packaged path), live E2E
  instructions, renumbered headings

### Verified
- `pytest -q` -> 151 passed (config change is import-safe with no .env)
- `vitest` -> 40 passed
- `npx playwright test e2e/live-discovery.spec.ts` -> 1 skipped (no key set),
  which is the correct guard behaviour
- Run it with a key via `$env:YTPOP_YOUTUBE_API_KEY = "<key>"` then the spec
  above (1 quota unit per run).

### Notes
- The packaged app currently needs `python` + FFmpeg on PATH because the
  backend is spawned as `python -m uvicorn ...` rather than embedded;
  bundling the Python runtime itself remains the last packaging gap.

### Commit
- `D6: feat(discovery): .env key wiring + live discovery e2e`

## D7 - 2026-10-09 - packaged app needs nothing on PATH (done)

### Planned
- Close the last packaging gap: freeze the backend (python + deps + ffmpeg)
  into the win-unpacked build so the app runs on a bare Windows machine.

### Did
- [x] `apps/api/api_backend.py` + `api_backend.spec` - PyInstaller freeze of
  the API (`--host/--port`, uvicorn workers=1). Excludes torch /
  sentence_transformers (they only back MiniLM); bundles the whole ffmpeg bin
  dir (exes + DLLs, since the local build is shared)
- [x] `app/services/embedding_service.py` - embedder resolution: MiniLM ->
  Ollama (`/api/embed`, nomic-embed-text, normalized) -> None. `clipping`
  and `clustering` use it and fail loudly when nothing is available; the S6
  `Embedder` class stays as a thin alias
- [x] `app/routes/moments.get_embedder` now returns the resolved embedder
  (it used to construct the torch-backed class directly - this was the frozen
  build's 500)
- [x] `app/db/database.ensure_schema()` - creates missing tables from model
  metadata; called only from the frozen entry point so a first run on a fresh
  data dir works without shipping Alembic (dev/tests keep Alembic)
- [x] `electron-builder` bundles `apps/api/dist-frozen/api-backend` as
  `resources/backend`; `main.ts` prefers that exe (prepending its dir to PATH)
  and falls back to `python -m uvicorn` only from a checkout
- [x] Root `npm run pack:backend` / `npm run dist`; apps/api workspace +
  gitignore for freeze artifacts
- [x] Tests: `tests/clipping/test_embedding_service.py` (8) + frozen-path
  regression `e2e/packaged.spec.ts` "needs nothing on PATH"; runbook �4

### Verified
- `pytest -q` -> 159 passed; `vitest` -> 40 passed; `npx playwright test` ->
  3 passed + 1 skipped (live discovery still awaits a YouTube key)
- Frozen exe alone (PATH = System32 only): health 200, deps ffmpeg/whisper/
  database `ok`, and a real analyze -> transcribe (2 segments, ~5s,
  ctranslate2 inside the freeze) -> find-moments (Ollama embeddings) run
- Packaged exe with PATH stripped: boots, `API: ok`, golden sources visible -
  both from a manual launch and the new e2e regression test
- Size: ~720MB freeze (ffmpeg shared build dominates) - documented as the
  known trade-off with a trimming path

### Next
- Live discovery e2e once a YouTube key is added to `.env`
  (YTPOP_YOUTUBE_API_KEY).

### Commit
- `D7: feat(packaging): freeze backend + ffmpeg, no PATH required`

## D8 - 2026-10-09 - reconcile roadmap/architecture checkboxes with reality (done)

### Did
- [x] Ticked 132 roadmap boxes + all 14 `architecture.md` SS29 boxes that are
  implemented AND verified (traced to worklog evidence, not assumption)
- [x] Left unchecked on purpose: Scene detection (never built), the Phase 9
  Originality items, the NSIS installer smoke test, and a new "Remaining work"
  list (live discovery E2E, installer smoke, scene detection, originality
  layer, build size, ranker retraining cadence)
- [x] Roadmap header now states MVP complete + tag, the three gates with
  counts, and the skipped live-discovery test with the reason

### Verified
- Box counts: roadmap 132 ticked / 16 not-built; architecture SS29 14/14 ticked
- Tooling scripts were one-off and removed; no code changed, so the gates stay
  green as recorded in D7

### Commit
- `D8: docs: reconcile roadmap + architecture with shipped state`

## D9 - 2026-10-09 - live discovery e2e with a real youtube key (done)

### Planned
- Add the key to `.env`, make the live spec read it, and run the real
  discovery end to end (1 quota unit).

### Did
- [x] `e2e/live-discovery.spec.ts` loads the repo `.env` itself so the live
  spec sees `YTPOP_YOUTUBE_API_KEY` (an actual env var still wins)
- [x] The spec migrates its temp DB with Alembic before starting the API
  (previously it ran against a schema-less DB -> 500 on the first query)
- [x] `afterAll` cleanup tolerates a still-locked sqlite file
- [x] playwright.config also dotenv-loads for consistency; `dotenv` declared
- [x] Roadmap: live-discovery box ticked, gates line now 4/4, stale
  "skipped test" note removed

### Verified
- Direct probe with the key: real mostPopular data (3 items, 1 quota unit)
- `npx playwright test e2e/live-discovery.spec.ts` -> 1 passed
- Full suites: `pytest -q` 159 passed, `vitest` 40 passed,
  `npx playwright test` -> 4 passed (golden dev, golden packaged, no-PATH
  packaged, live discovery)
- `.env` remains gitignored; key never printed or committed

### Commit
- `D9: feat(e2e): live discovery with real youtube key`

## D10 - 2026-10-09 - scene detection (done)

### Planned
- S4's unchecked "Scene detection", cheap-first: real hard cuts, persisted
  and inspectable, and used by the clip boundary engine.

### Did
- [x] `app/services/scene_service.py` - ffmpeg `select=scene,metadata=print`
  parser (no PySceneDetect, no torch -> keeps the freeze lean)
- [x] `Scene` model + migration `decd4fcade07`; `data/scenes/{id}.json`
  artifact; `app/domain/analysis/scenes.py` (idempotent replace)
- [x] Routes `POST /sources/{id}/detect-scenes`, `GET /sources/{id}/scenes`
- [x] Clipping integration: `cuts_inside`, `snap_to_cuts`,
  `apply_scene_scoring`; `find_moments(..., cuts=[...])` + DB lookup
- [x] `configs/default.yaml` `scenes:` (threshold, max_scenes, penalty_weight,
  snap, snap_tolerance_s)
- [x] `tests/test_scenes.py` (10 tests incl. route commit + round-trip)
- [x] runbook section 9; roadmap "Scene detection" ticked

### Verified
- `pytest -q` -> 169 passed; `vitest` -> 40 passed; `playwright` -> 4 passed
- Live: 4-shot fixture -> 3 cuts detected at 5.0/10.0/15.0s, persisted
  (GET confirms), and the candidate window spanning two cuts dropped exactly
  67.29 -> 55.29 (= 2 cuts x 6.0 weight); ranking changed accordingly
- Two bugs found by the live run and fixed: the detect route never committed
  (nothing persisted), and the fixture needed high-contrast cuts because the
  ffmpeg scene metric is luma-based (colour-only changes scored 0.13-0.19)

### Notes
- Scene coverage is quantified honestly in the runbook: colour-only cuts may
  sit below the threshold; lower `threshold` for such media.

### Commit
- `D10: feat(scenes): ffmpeg scene detection + clip boundary penalty`

## D11 - 2026-10-09 - phase 9 originality overlay pack (done)

### Planned
- The 8 remaining Phase 9 boxes as one coherent slice: original overlay
  content that is actually rendered into the episode, not stubs.

### Did
- [x] `app/services/graphics_service.py` - Pillow bar chart + proportional
  timeline strip (deterministic, no matplotlib, no fonts beyond default)
- [x] `app/domain/editorial/overlays.py` - overlay pack with all 8 kinds:
  context, commentary, source, comparison, chart, timeline, annotation and a
  narration script (text + timing); cards are appended as real segments
  (idempotent via transition_type=overlay) and persisted to
  `data/overlays/{id}.json` + media_assets rows
- [x] `app/domain/rendering/service.py` - image cards (`-loop 1` +
  `aevalsrc`) render with asset-missing errors, and card inputs are
  normalized to `format=yuv420p` (concatenation used to die on rgb24 image
  inputs); annotations burn in through the subtitle channel
- [x] Routes `POST/GET /episodes/{id}/overlays` (plan JSON accepted, else the
  stored storyboard)
- [x] `configs/editorial.yaml` `overlays:` durations + toggles
- [x] `tests/editorial/test_overlays.py` (7 tests: graphics determinism, all
  kinds, idempotency, render burn-in, missing-asset failure, route commit)
- [x] runbook section 9b; all 8 roadmap Phase 9 boxes ticked

### Verified
- `pytest -q` -> 176 passed; `vitest` -> 40 passed; `playwright` -> 4 passed
- Live: 2 clips (24.9s) -> overlay pack (chart PNG 21.9KB, 7 items, 4 narration
  lines) -> render QA ok at 52.0s, i.e. the overlay cards extended the
  episode by 27s and the chart card is in the output
- Two bugs the live run caught (both fixed with tests): the overlays route
  never committed (cards silently missing), and the `model` field was being
  abused to carry plan JSON -> now a proper `plan` field

### Known limits (documented, not hidden)
- Narration is a script, not spoken audio: no TTS stage exists yet.
- Chart/timeline are static Pillow art, not interactive/HTML.

### Commit
- `D11: feat(editorial): originality overlay pack + original graphics`

## D12 - 2026-10-09 - trim packaged build 718MB -> 432MB (done)

### Planned
- The last size item: cut the packaged freeze without losing functionality.
- Order vs ranker cadence: cadence adds no deps (trainer is pure Python),
  so it cannot change the trim; trim first was correct.

### Did
- [x] `api_backend.spec` bundles only what our pipeline links (ffmpeg/ffprobe +
  avcodec/avformat/avfilter/avutil/swresample/swscale/avdevice) - drops
  ffplay.exe (-17MB); excludes onnxruntime/pyarrow/scipy/av/... (-136MB)
- [x] `whisper_service.load_audio` decodes the 16kHz mono wav with stdlib
  `wave`+numpy and feeds the array to faster-whisper, so PyAV (~60MB) is not
  needed at runtime
- [x] `_ensure_av_shim()` stands in `av` when PyAV is absent (faster-whisper
  imports it at module load) and raises loudly if the unused decoder path is
  ever hit
- [x] Tests: `tests/transcription/test_audio_decode.py` (decoder semantics +
  array-decode call + shim install + real-PyAV passthrough)
- [x] runbook: real numbers + the ffmpeg-build dead end (static = 161MB per
  exe, shared = ~210MB regardless of version, so swapping does not help)

### Verified
- Frozen backend alone (PATH = System32 only): health 200, analyze, real
  transcribe (2 segments, 3s, ctranslate2 inside the freeze), find-moments
  via Ollama embeddings
- `pytest -q` -> 182 passed; `vitest` -> 40 passed; `playwright` -> 4 passed
  (incl. "needs nothing on PATH" against the rebuilt package)
- Size: frozen backend 717.7MB -> 432MB (-40%); win-unpacked ~700MB total,
  of which ~258MB is Electron itself
- Dead end documented: downloaded static (161MB/exe) and stable-shared
  (210MB) ffmpeg builds - both are worse than the local build, so no swap

### Commit
- `D12: chore(packaging): trim freeze 718MB to 432MB`
