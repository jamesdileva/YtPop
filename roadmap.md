# Automatic YouTube Mega Clipper — Roadmap

**Status:** Baseline / v0.1  
**Goal:** Progress from a manually controlled local clipper into an autonomous trend-to-episode media engine.

---

# 1. North Star

The long-term system should be able to operate like a small autonomous editorial team:

```text
                  INTERNET
                     │
                     ▼
              TREND DISCOVERY
                     │
                     ▼
              TOPIC DETECTION
                     │
                     ▼
              SOURCE ANALYSIS
                     │
                     ▼
               MOMENT FINDING
                     │
                     ▼
                RIGHTS GATE
                     │
                     ▼
             EDITORIAL PLANNING
                     │
                     ▼
              ORIGINAL CONTEXT
                     │
                     ▼
                  EDITING
                     │
                     ▼
                 RENDERING
                     │
                     ▼
                    QA
                     │
                     ▼
              HUMAN APPROVAL
                     │
                     ▼
             AUTHORIZED OUTPUT
```

The goal is not to eliminate humans immediately.

The goal is to make the human increasingly become:

> **editor-in-chief instead of video editor.**

---

# 2. Phase 0 — Architecture

## Goal

Create the foundation.

### Deliverables

- [ ] `architecture.md`
- [ ] `implementation-guide.md`
- [ ] `roadmap.md`
- [ ] Repository
- [ ] README
- [ ] Environment configuration
- [ ] Initial database design
- [ ] Initial API contract

### Exit criteria

The project can be handed to an implementation agent without requiring it to invent the architecture.

---

# 3. Phase 1 — Application Foundation

## Goal

Create the local desktop application.

### Tasks

- [ ] Electron
- [ ] React
- [ ] TypeScript
- [ ] Vite
- [ ] FastAPI
- [ ] SQLite
- [ ] SQLAlchemy
- [ ] Alembic
- [ ] Basic logging
- [ ] Health endpoint
- [ ] Dependency health endpoint

### UI

Create:

```text
Dashboard
Trends
Sources
Clips
Episodes
Review
Settings
```

### Exit criteria

```text
Electron
  ↓
React
  ↓
FastAPI
  ↓
SQLite
```

works reliably.

---

# 4. Phase 2 — Discovery Engine

## Goal

Find what is popular.

### Tasks

- [ ] YouTube API integration
- [ ] Region selection
- [ ] Category selection
- [ ] Most-popular discovery
- [ ] Search discovery
- [ ] Source metadata storage
- [ ] Historical snapshots
- [ ] API quota tracking
- [ ] Discovery scheduling

The YouTube Data API provides a `mostPopular` chart through `videos.list`, with optional region/category filtering. citeturn0search4

### Exit criteria

Dashboard displays:

```text
Trending now
Recently rising
Fastest growing
Top categories
```

---

# 5. Phase 3 — Trend Intelligence

## Goal

Stop thinking in individual videos.

Start thinking in **events/topics**.

### Tasks

- [ ] Embeddings
- [ ] Similarity
- [ ] Topic clustering
- [ ] Trend scoring
- [ ] Velocity calculation
- [ ] Cross-video relationships
- [ ] Trend history
- [ ] Topic summaries

### Example

Instead of:

```text
Video A
Video B
Video C
Video D
```

show:

```text
🔥 MAJOR GAME UPDATE
  12 videos
  +184% velocity
  4.2M combined views
```

### Exit criteria

System can identify a trend containing multiple related videos.

---

# 6. Phase 4 — Media Analysis

## Goal

Understand individual videos.

### Tasks

- [ ] Media ingestion
- [ ] FFmpeg probe
- [ ] Audio extraction
- [ ] Whisper transcription
- [ ] Scene detection
- [ ] Transcript indexing
- [ ] Thumbnail extraction
- [ ] Metadata normalization

### Exit criteria

Given a permitted test source:

```text
video
 ↓
transcript
 ↓
scenes
 ↓
searchable timeline
```

---

# 7. Phase 5 — Automatic Clip Finder

## Goal

Find interesting moments automatically.

### V1

Transcript-only:

```text
keywords
sentences
hooks
```

### V2

Semantic:

```text
embeddings
similarity
novelty
```

### V3

LLM:

```text
"Is this actually interesting?"
```

### V4

Vision:

```text
"What is happening visually?"
```

### V5

Combined:

```text
Transcript
+
Audio
+
Vision
+
Semantics
+
Historical feedback
```

### Exit criteria

System can produce:

```text
Top 10 moments
```

that a human considers useful more often than random selection.

---

# 8. Phase 6 — Clip Review

## Goal

Make human correction extremely fast.

### UI

```text
Candidate #1
───────────────
▶ Preview

Score: 91

Hook       █████████░ 90
Emotion    ██████████ 96
Novelty    ████████░░ 82
Context    █████████░ 91

[Reject] [Trim] [Approve]
```

### Tasks

- [ ] Clip preview
- [ ] Timeline trimming
- [ ] Approve/reject
- [ ] Notes
- [ ] Categories
- [ ] Score visibility
- [ ] Keyboard shortcuts

### Exit criteria

Human can review dozens of clips quickly.

---

# 9. Phase 7 — Manual Mega-Video

## Goal

Prove the basic product.

### Workflow

```text
Find videos
 ↓
Find clips
 ↓
Approve clips
 ↓
Drag into timeline
 ↓
Render
```

### Tasks

- [ ] Timeline
- [ ] Reordering
- [ ] Trimming
- [ ] Transitions
- [ ] Intro
- [ ] Outro
- [ ] Captions
- [ ] Audio normalization
- [ ] Rendering
- [ ] Preview

### Exit criteria

User can create a finished episode without external editing software.

---

# 10. Phase 8 — AI Editorial Engine

## Goal

Make the AI the editor.

### Tasks

- [ ] Story clustering
- [ ] Segment ordering
- [ ] Hook selection
- [ ] Context generation
- [ ] Transition generation
- [ ] Narrative planning
- [ ] Episode title generation
- [ ] Description generation
- [ ] Thumbnail concepts

### Core question

The AI should answer:

> "Why should these clips appear together?"

not merely:

> "Which clips have the highest score?"

### Exit criteria

AI can generate a plausible episode outline from approved candidate moments.

---

# 11. Phase 9 — Originality Layer

## Goal

Move from compilation toward genuine editorial production.

### Features

- [ ] AI-generated context
- [ ] Original narration
- [ ] Commentary
- [ ] Comparison segments
- [ ] Topic summaries
- [ ] Visual annotations
- [ ] Charts
- [ ] Timeline graphics
- [ ] Source cards

YouTube's current monetization guidance distinguishes meaningful transformation/commentary from minimally altered reused material. citeturn0search0turn0search3

This should therefore be a core product feature, not a last-minute patch.

---

# 12. Phase 10 — Rights System

## Goal

Prevent the application from treating discovered material as automatically publishable.

### Tasks

- [ ] Rights records
- [ ] Source owner
- [ ] License tracking
- [ ] Permission evidence
- [ ] Review state
- [ ] Commercial-use field
- [ ] Territory
- [ ] Expiration
- [ ] Human approval
- [ ] Publish blocker

### State machine

```text
UNKNOWN
 ↓
REVIEW_REQUIRED
 ├──→ APPROVED
 ├──→ REJECTED
 └──→ NEEDS_PERMISSION
```

Copyright and fair-use questions remain fact-specific; YouTube explicitly notes that adding material does not automatically establish fair use and that courts ultimately decide fair use. citeturn0search1

### Exit criteria

The application cannot accidentally represent an uncleared source as cleared.

---

# 13. Phase 11 — Autonomous Daily Episode

## Goal

One button becomes one episode.

```text
GENERATE TODAY'S EPISODE
```

Pipeline:

```text
Discover
 ↓
Rank
 ↓
Cluster
 ↓
Analyze
 ↓
Find moments
 ↓
Rights filter
 ↓
Editorial plan
 ↓
Generate context
 ↓
Build timeline
 ↓
Render
 ↓
QA
 ↓
Review
```

### Exit criteria

The system can produce a complete draft episode with minimal intervention.

---

# 14. Phase 12 — 24/7 Mode

## Goal

Make the system continuously observe the internet.

Scheduler:

```text
every 15 min
    ↓
trend scan

every 30 min
    ↓
source refresh

every hour
    ↓
topic clustering

continuous
    ↓
analysis queue
```

Priority should be dynamic.

Example:

```text
BREAKING TREND
    ↓
priority 100

RISING TREND
    ↓
priority 70

NORMAL
    ↓
priority 30

OLD
    ↓
priority 5
```

---

# 15. Phase 13 — Learning From the Editor

## Goal

The system learns what makes a good clip.

Capture:

```text
approved
rejected
trimmed
extended
reordered
deleted
promoted
```

Then learn:

```text
What clips does the editor like?
```

Potential features:

```text
duration
topic
speaker
emotion
hook
words
visual activity
source popularity
novelty
context length
```

Eventually:

```text
Candidate generator
        ↓
ranking model
        ↓
editor feedback
        ↓
training data
        ↓
better ranking
```

---

# 16. Phase 14 — Personalization

Allow users to create shows.

Example:

```text
My Shows

Gaming Daily
Tech Daily
Internet Chaos
AI News
OSRS
Funny Internet
```

Each show has:

```text
categories
channels
keywords
blocked topics
target duration
tone
caption style
intro
outro
```

---

# 17. Phase 15 — Multi-Format Publishing

Generate:

```text
20-minute YouTube episode
10-minute recap
5-minute recap
60-second Short
30-second teaser
```

One editorial graph:

```text
EPISODE
├── Segment A
├── Segment B
├── Segment C
├── Segment D
└── Segment E
```

can produce multiple derivatives.

---

# 18. Phase 16 — Advanced Intelligence

Potential future systems:

### Trend prediction

```text
"Likely to explode in next 6 hours"
```

### Cross-platform trend detection

```text
YouTube
TikTok
Reddit
X
Google Trends
News
```

### Story graph

```text
Event
 ├── original source
 ├── reactions
 ├── responses
 ├── counterarguments
 └── follow-ups
```

### Event timeline

```text
09:10 original video
10:02 reaction
11:31 response
12:15 viral clip
14:02 major creator response
```

This could eventually become much more powerful than a simple clipping engine.

---

# 19. Advanced Autonomous Editorial System

Long-term:

```text
                    TREND
                      │
              ┌───────┴───────┐
              │               │
           SOURCES         CONTEXT
              │               │
              └───────┬───────┘
                      ▼
                 STORY GRAPH
                      │
              ┌───────┴────────┐
              ▼                ▼
          MOMENTS          COMMENTARY
              │                │
              └───────┬────────┘
                      ▼
                EDITOR AGENT
                      │
                      ▼
                VIDEO AGENT
                      │
                      ▼
                 QA AGENT
                      │
                      ▼
               HUMAN REVIEW
```

At this stage the project starts behaving like an autonomous newsroom.

---

# 20. Agent Architecture — Future

Do not build this initially, but eventually the system can separate responsibilities.

```text
Scout Agent
   ↓
Trend Agent
   ↓
Research Agent
   ↓
Clip Agent
   ↓
Rights Agent
   ↓
Editor Agent
   ↓
Narrator Agent
   ↓
Video Agent
   ↓
QA Agent
```

Each agent should communicate through structured artifacts rather than free-form chat.

---

# 21. Potential Agent Loop

```text
SCOUT
 ↓
"I found something interesting."

RESEARCH
 ↓
"Here is what happened."

CLIPPER
 ↓
"These are the strongest moments."

RIGHTS
 ↓
"These sources are cleared/review-required."

EDITOR
 ↓
"Here is the story."

VIDEO
 ↓
"Here is the render."

QA
 ↓
"Pass."

HUMAN
 ↓
"Publish."
```

---

# 22. Metrics

The system needs metrics beyond views.

## Discovery

```text
trend detection accuracy
time-to-detection
false positives
```

## Clip quality

```text
approval rate
trim rate
rejection rate
average score
```

## Editorial

```text
episode approval rate
manual reorder rate
segment deletion rate
```

## Production

```text
render time
CPU utilization
GPU utilization
failed jobs
```

## Long-term

```text
viewer retention
CTR
watch time
subscriber conversion
```

---

# 23. Milestone Map (linked to Sprints in §26)

| Milestone | Sprints | Demo proof |
|---|---|---|
| M1 — "It Works" | S0, S1, S2 | App opens, health green, DB migrates |
| M2 — "It Finds Things" | S3, S11-partial | Dashboard shows Trending / Rising / Fastest |
| M3 — "It Clips" | S4, S5, S6, S7 | 1 permitted source → transcript → Top-10 → review |
| M4 — "It Edits" | S8, S9 | Manual timeline → rendered 1080p + captions, in-app playback |
| M5 — "It Thinks" | S10 | Approved moments → plausible JSON outline (Pydantic-valid) |
| M6 — "It Understands Trends" | S11 | Multi-video topic cluster with velocity |
| M7 — "It Produces Shows" | S10, S12, S13-partial | One-button draft episode to review queue |
| M8 — "It Runs Itself" | S13 | Scheduler + idempotent jobs + retry, Demo 3 pass |
| M9 — "It Learns" | S14 | Approval/reject/trim feedback stored, ranking improves |

## M1 — "It Works" (exit: S2 done)

```text
Electron
+
React
+
FastAPI
+
SQLite
```

## M2 — "It Finds Things"

```text
YouTube discovery
+
trend scoring
```

## M3 — "It Clips"

```text
transcription
+
candidate detection
+
clip review
```

## M4 — "It Edits"

```text
timeline
+
rendering
+
captions
```

## M5 — "It Thinks"

```text
AI editorial engine
```

## M6 — "It Understands Trends"

```text
topic clustering
+
cross-source analysis
```

## M7 — "It Produces Shows"

```text
automated episode generation
```

## M8 — "It Runs Itself"

```text
24/7 scheduler
+
job system
+
autonomous pipeline
```

## M9 — "It Learns"

```text
editor feedback
+
ranking improvement
```

---

# 24. What Success Looks Like

The first success is **not**:

> "AI uploaded a video."

The first success is:

> "I gave the system a topic and it found the best moments better and faster than I could."

The next success:

> "I gave it today's trends and it produced a surprisingly good episode."

The long-term success:

> "I woke up and my AI newsroom had already researched what happened on the internet, assembled a coherent episode, generated derivatives, and left me a clean review queue."

---

# 25. Recommended Immediate Scope

Build only this first:

```text
Electron
React
FastAPI
SQLite
YouTube discovery
Source database
Whisper
FFmpeg
Moment detection
Clip review
Manual episode builder
Rendering
```

Then prove:

```text
TREND
 ↓
SOURCE
 ↓
TRANSCRIPT
 ↓
MOMENT
 ↓
CLIP
 ↓
EPISODE
 ↓
VIDEO
```

Once that loop works, everything else becomes an iteration on top of a working foundation.

---

# 26. Sprint Plan with Exit Goals (S0–S14)

> Source of truth for `worklog.md` and commit prefixes (`S0:`, `S1:`, …).
> Maps to: Roadmap Phases above, `implementation-guide.md` Sprints, `architecture.md` modules.
> Workflow per sprint: `plan → scope → implement → verify (tests) → worklog → commit → push` (see `agents.md`).
> Rule: do not start S{N+1} until S{N} exit criteria are met and logged.

## Sprint template (every sprint follows this)

```text
Goal / In scope / Out of scope
→ Tasks
→ Verification (exact pytest / vitest / manual checks)
→ Exit criteria (measurable DoD)
→ Worklog entry + commit
```

Global DoD for any code sprint (from `implementation-guide.md` §37):

```text
typed in/out, persisted result, idempotent, fails safely + retryable,
useful logs with correlation IDs, tests, inspectable artifacts,
no secrets in logs, no silent failure discards
```

---

### S0 — Repo & Docs Baseline (Maps to: Phase 0, Impl §3, M1-pre)

**Goal:** Git + docs + env baseline so an agent can implement without inventing architecture.

**In scope:**
- `git init`, `main` branch, `.gitignore` (Python/Node/Electron/`data/*`!`/configs/`/`.env`), `.env.example`
- `README.md` (what/why/quickstart), `docs/` move (arch/impl/roadmap), `agents.md`, `worklog.md`
- `gh repo create YtPop --public --source=. --push`

**Out of scope:** any app code, DB, API.

**Tasks:**
- [ ] `git init && git branch -M main`
- [ ] Add `.gitignore`, `README.md`, `.env.example`
- [ ] Add `agents.md`, `worklog.md`
- [ ] Initial commit + `gh repo create YtPop --public`
- [ ] Verify `gh repo view`, `git log`, `git status` clean

**Verification:**
```text
git status  # clean
git log --oneline -3
gh repo view --json name,visibility
Test-Path .git → True
```

**Exit criteria:**
- Repo exists locally + on GitHub (`YtPop`, public).
- Docs (`architecture.md`, `implementation-guide.md`, `roadmap.md`, `agents.md`, `worklog.md`, `README.md`) committed.
- New clone + `gh repo clone` path documented in `worklog.md` S0 entry.

---

### S1 — Foundation: Electron + React + FastAPI Health (Phase 1, Impl §5, M1)

**Goal:** `Electron → React → FastAPI` communicating locally.

**In scope:**
- `apps/api/app/main.py`, `config.py` (`pydantic-settings`), `structlog` baseline
- `GET /api/v1/health`, `GET /api/v1/health/dependencies`
- `apps/desktop/electron/{main,preload}.ts`, `apps/desktop/renderer/` (Vite+React+TS, health badge page)
- `pyproject.toml`, `package.json`, `pytest` + `vitest` scaffolds

**Out of scope:** DB, YouTube, media, jobs.

**Tasks:**
- [ ] FastAPI app + versioned router (`/api/v1`)
- [ ] Health endpoints returning `{"status":"ok","version":"0.1.0"}`
- [ ] Electron launches backend + opens Vite frontend (dev mode)
- [ ] Frontend `useHealth()` hook + Dashboard status card
- [ ] Backend test `tests/test_health.py`, frontend smoke test

**Verification:**
```powershell
pytest apps/api/tests/test_health.py -v
npm run test --workspace=apps/desktop
# manual: app opens, badge shows "API: ok"
```

**Exit criteria:**
- App opens locally, backend responds <500ms on localhost.
- `pytest` + `vitest` green, evidence pasted in `worklog.md`.
- No hardcoded ports/secrets; config via env.

---

### S2 — Database + Migrations (Phase 1, Impl §6, M1)

**Goal:** Versioned SQLite schema for all core entities.

**In scope:**
- `data/database/mega_clipper.db` (gitignored, created at runtime)
- SQLAlchemy 2 models: `sources, trend_events, trend_sources, transcripts, moments, episodes, episode_segments, jobs, rights_records, renders`
- Alembic init + first migration, `db/database.py` session factory
- `POST /sources` (test create) + `GET /sources/{id}` minimal read

**Out of scope:** YouTube logic, transcription, full CRUD UI.

**Tasks:**
- [ ] Models with types/constraints matching `architecture.md` §6
- [ ] `alembic revision --autogenerate`, `alembic upgrade head`, downgrade check
- [ ] Seed/test-source round-trip test
- [ ] DB path via config, `data/` dirs with `.gitkeep`

**Verification:**
```powershell
alembic upgrade head; alembic downgrade -1; alembic upgrade head
pytest apps/api/tests/test_db.py -v  # asserts 10 tables exist + CRUD
```

**Exit criteria:**
- Migrate up/down/up clean, no manual schema edits.
- API can create/read a test source; tables verified in `worklog.md`.
- M1 done when S0+S1+S2 exits all hold.

---

### S3 — YouTube Discovery (Phase 2, Impl §7, M2-start)

**Goal:** Find what's popular without burning quota.

**In scope:**
- `services/youtube_service.py`: `get_most_popular(), search_videos(), get_video(), get_channel(), get_categories()`
- `POST /sources/discover`, `POST /trends/discover`, `GET /sources`, `GET /trends`, quota-tracking table/fields
- Snapshot history per source (for velocity), region/category filters, scheduler stub (manual trigger only)

**Out of scope:** clustering, transcription, auto-scheduling.

**Tasks:**
- [ ] Thin YouTube Data API adapter (`videos.list chart=mostPopular`, `search.list`, `channels.list`, `videoCategories.list`)
- [ ] Persist `sources` + snapshot rows on every fetch
- [ ] Quota counter + aggressive cache (no re-fetch unchanged metadata)
- [ ] Dashboard lists: Trending now / Recently rising / Fastest growing / Top categories
- [ ] Mocked adapter tests (no live quota in CI)

**Verification:**
```powershell
pytest apps/api/tests/discovery/ -v  # mock adapter, quota guard, velocity math
# manual with key: discover US/gaming → 20+ sources in DB
```

**Exit criteria:**
- Dashboard renders 4 discovery sections from DB.
- Snapshots enable velocity calc; quota usage visible in logs/UI.
- No live API calls in automated tests.

---

### S4 — Media Ingestion (Phase 4-part, Impl §8, M3-start)

**Goal:** Permitted local media → normalized assets.

**In scope:**
- `services/ffmpeg_service.py` + `MediaIngestionService.probe/normalize/extract_audio/extract_thumbnail/verify_media`
- `data/{raw,media,thumbnails,logs}/` artifacts + DB linkage
- `POST /sources/{id}/analyze` (probe only)

**Out of scope:** downloading arbitrary YouTube videos as core flow; transcription.

**Tasks:**
- [ ] FFmpeg via arg-arrays (never shell-concat), path restricted to `data/`
- [ ] Probe → normalize (1080p/mezzanine) → 16kHz wav → thumb jpg
- [ ] `verify_media` (streams, duration>0, audio present)
- [ ] Accept only `USER_OWNED/LICENSED/CC/PUBLIC_DOMAIN` test material with basis recorded

**Verification:**
```powershell
pytest apps/api/tests/test_ingestion.py -v  # fixture mp4 → probe/normalize/audio/thumb
# negative: path traversal rejected, corrupt file fails safely
```

**Exit criteria:**
- Fixture video produces inspectable artifacts + DB record.
- Corrupt/evil paths fail with clear error, no crash, no shell injection.

---

### S5 — Transcription (Phase 4, Impl §9, M3)

**Goal:** Audio → timestamped searchable transcript.

**In scope:**
- `services/whisper_service.py` (`faster-whisper`), `POST /sources/{id}/transcribe`, `GET /sources/{id}/transcript`
- `transcripts` table + `data/transcripts/{source_id}.json` (preserve word timings)
- Job type `TRANSCRIBE` (sync first, queue-ready payload)

**Out of scope:** scoring, diarization perfection.

**Tasks:**
- [ ] `media → wav → whisper → segments[{start,end,text,confidence}] → DB + json`
- [ ] Language + model name stored; idempotent re-run (skip if hash match)
- [ ] Concurrency=1 default (see `configs/default.yaml`)

**Verification:**
```powershell
pytest apps/api/tests/transcription/ -v  # 60s fixture → segments schema valid, timings monotonic
```

**Exit criteria:**
- Given permitted test source: `video → transcript → searchable timeline` viewable in Sources page.
- Word timings preserved for captions/boundaries later.

---

### S6 — Clip Detection V1 (Phase 5-V1/V2, Impl §10, M3)

**Goal:** Transcript → ranked candidate moments (no vision yet).

**In scope:**
- `domain/clipping/` candidate generator (5–90s windows) + scorer (`hook/relevance/novelty/emotion/payoff/completeness - redundancy/dead_air/dependency`)
- `moments` table (all score columns), `POST /sources/{id}/find-moments`, `GET /moments`
- `configs/scoring.yaml` weights (not hardcoded)

**Out of scope:** vision, LLM judge (V3+), auto-publish.

**Tasks:**
- [ ] Keyword + sentence-window baseline, then embedding similarity (`sentence-transformers`)
- [ ] Store **all** candidates (don't delete low scores)
- [ ] Golden fixture: `known transcript + config = expected ranges`

**Verification:**
```powershell
pytest apps/api/tests/clipping/ -v  # golden ranges ±2s, scoring determinism
```

**Exit criteria:**
- System outputs `Top 10 moments` a human rates useful > random (log 10-sample check in worklog).
- Scoring weights editable without code change.

---

### S7 — Clip Review UI (Phase 6, Impl §11, M3-done)

**Goal:** Human correction extremely fast + feedback capture.

**In scope:**
- Review page (`Clips/`): preview, waveform/timeline trim, Approve/Reject/Trim, notes, category, Best flag, score breakdown, shortcuts (`J/L`, `I/O`, `A/R`)
- `PATCH /moments/{id}`, `POST /moments/{id}/preview` (FFmpeg slice)
- Feedback rows (`decision, reason, adjusted_start/end, at`) for future learning

**Out of scope:** auto-editing, rendering.

**Tasks:**
- [ ] Candidate queue + filters (score/type/status)
- [ ] Trim persisted, preview regenerable
- [ ] Every action writes feedback record

**Verification:**
```powershell
pytest apps/api/tests/test_moments_api.py -v
npm run test --workspace=apps/desktop
# manual: review 20 clips in <10 min
```

**Exit criteria:**
- M3 done: transcribe → candidates → preview → approve flows in-app with feedback stored.
- Keyboard-only review possible.

---

### S8 — Episode Builder, Manual (Phase 7, Impl §12, M4-start)

**Goal:** Prove basic product: human-assembled mega-video plan.

**In scope:**
- `episodes`, `episode_segments` CRUD: `POST /episodes`, `PATCH /episodes/{id}`, `POST /episodes/{id}/rebuild`
- Timeline UI: drag/reorder/trim/delete/duplicate, intro/outro/title cards, target vs actual duration
- Episode templates stub (`configs/editorial.yaml`, `templates/daily_highlights`)

**Out of scope:** AI story planning, narration, rendering.

**Tasks:**
- [ ] Segment `{moment_id, sequence, transition_type, context_text}`
- [ ] Duration roll-up + over/under indicator
- [ ] Persist order server-side (not local-only)

**Verification:**
```powershell
pytest apps/api/tests/test_episodes.py -v  # reorder persistence, duration math
```

**Exit criteria:**
- User builds 5-clip episode, reorders, saves, reloads intact.
- No AI required to reach this point.

---

### S9 — Rendering + Captions (Phase 7, Impl §13, M4-done)

**Goal:** Episode → finished video file playable in-app.

**In scope:**
- `RenderService`: episode → FFmpeg filter-graph → `youtube_1080p / preview_720p / vertical_1080x1920` presets
- Captions: Whisper words → ASS/WebVTT → burn-in (styles: standard/bold/highlight/vertical/minimal)
- `POST /episodes/{id}/render`, `GET /renders/{id}`, `POST /renders/{id}/cancel`, loudness normalize
- QA probe: exists, duration, audio+video streams, res/fps/codec, captions present, no corrupt frames

**Out of scope:** 4K perf tuning, thumbnail AI.

**Tasks:**
- [ ] Deterministic filter-graph builder + job `RENDER`
- [ ] Keep intermediates; final is not the only artifact
- [ ] Render record `{preset,res,fps,codec,path,status,error}`

**Verification:**
```powershell
pytest apps/api/tests/rendering/ -v  # fixture 3-clip episode → mp4 + QA asserts
# manual: play render in Episodes page
```

**Exit criteria:**
- M4 done: timeline → render → in-app playback, QA green logged.
- Failed render retryable with error surfaced.

---

### S10 — Editorial AI (Phase 8, Impl §14, M5)

**Goal:** AI proposes story, human disposes.

**In scope:**
- `domain/editorial/EditorialService` + `ModelRouter` (Ollama: classifier→small, planner→medium, vision→later) via `configs/default.yaml`
- `POST /episodes/{id}/generate` in: `{trend, sources, candidate_moments, rights, target_duration, format}` out: `{hook, clusters, order, transitions, context_reqs, ending, titles}`
- Strict JSON + Pydantic validation, never trust raw output

**Out of scope:** 24/7 autonomy, narration audio.

**Tasks:**
- [ ] Prompt with structured summaries (not giant raw transcripts)
- [ ] Validate/repair loop (max 2 retries, then fail job clearly)
- [ ] Episode title/description/thumbnail-concept outputs

**Verification:**
```powershell
pytest apps/api/tests/editorial/ -v  # mocked LLM: valid plan accepted, malformed rejected
```

**Exit criteria:**
- Core question answered: "Why do these clips belong together?" (cluster + rationale per segment).
- Invalid model JSON never corrupts episode (job fails safely).

---

### S11 — Trend Intelligence (Phase 3, Impl §15, M6 + M2-done)

**Goal:** Think in events/topics, not videos.

**In scope:**
- `embeddings → similarity → clusters → topic summaries → trend_events` pipeline
- `trend_score = views_vel*.25 + eng_vel*.15 + recency*.15 + xsource*.20 + momentum*.15 + novelty*.10` (weights in yaml)
- `trend_sources {relevance, relationship_type}`, velocity from S3 snapshots

**Out of scope:** cross-platform (YT-only), prediction.

**Tasks:**
- [ ] `sentence-transformers` local embeddings, cosine similarity, threshold clustering
- [ ] Trend history + status, Trends page topic cards (e.g. `🔥 GAME UPDATE · 12 vids · +184% · 4.2M`)
- [ ] Job `CLUSTER_TRENDS`

**Verification:**
```powershell
pytest apps/api/tests/test_trends.py -v  # A/B/C/D fixture → 1 topic, score≈91
```

**Exit criteria:**
- M2+M6 done: multi-video trend identified from DB, visible on Dashboard.
- Weights tunable without redeploy.

---

### S12 — Rights Workflow (Phase 10, Impl §16, M7-gate)

**Goal:** Never treat discovered material as publishable by default.

**In scope:**
- `rights_records` full fields (`status/basis/owner/license/ref/restrictions/territory/commercial/notes/verified_at/reviewer`)
- States: `UNKNOWN → REVIEW_REQUIRED → APPROVED/REJECTED/NEEDS_PERMISSION` (+ `LICENSED/CC/PUBLIC_DOMAIN/USER_OWNED` as approved bases)
- `GET /rights/{source_id}`, `POST /rights/{source_id}/review`, `PATCH /rights/{source_id}`, publish blocker (`READY_TO_PUBLISH` requires approved basis)

**Out of scope:** auto fair-use verdicts, public publishing.

**Tasks:**
- [ ] State-machine enforced server-side + UI banner ("Rights basis: human review required")
- [ ] Evidence attachments/URLs, expiry checks
- [ ] Research/demo-only mode flag (analyze locally ≠ cleared)

**Verification:**
```powershell
pytest apps/api/tests/rights/ -v  # illegal transition rejected, publish blocked when UNKNOWN
```

**Exit criteria:**
- App cannot represent uncleared source as cleared (negative test logged).
- No UI string claims "Fair use confirmed".

---

### S13 — Automation: Daily Episode + Scheduler (Phases 11–12, Impl §17–18, M7+M8)

**Goal:** One button → draft episode; then scheduled.

**In scope:**
- `PipelineOrchestrator`: `discover → rank → cluster → analyze → candidates → rights-filter → plan → context → timeline → render → QA → review`
- SQLite `jobs {type/status/priority/payload/progress/attempts}` worker (`QUEUED/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED`), claim→run→artifact→DB→complete, exp-backoff retry
- Intervals: trend-scan 15m, source-refresh 30m, clustering 60m, analysis-queue continuous; priority `BREAKING 100 / RISING 70 / NORMAL 30 / OLD 5`
- Jobs UI (`GET /jobs`, retry/cancel)

**Out of scope:** multi-machine pool, learning ranker.

**Tasks:**
- [ ] Each stage = job with idempotency key + checkpoint
- [ ] `GENERATE TODAY'S EPISODE` button + overnight dry-run
- [ ] Dashboard ops view (queue depth, quota, failures)

**Verification:**
```powershell
pytest apps/api/tests/test_jobs.py -v  # claim/run/fail/retry ordering
# manual Demo 3: scheduled run → review queue with draft
```

**Exit criteria:**
- M7+M8 done: minimal-intervention draft episode end-to-end, failures retryable, scheduler logs show intervals honored.

---

### S14 — QA / Packaging / Learning Prep (Phases 13–16 bridges, Impl §19–33, M9)

**Goal:** Ship local MVP + instrument learning for future.

**In scope:**
- Feedback store (`moment_id, decision, reason, adj_start/end, at`) → future ranker dataset export
- Clip Scoring V3–V5 stubs behind flags (LLM/vision/learned), vision sampling 1–3s (cheap detector first)
- Electron Builder packaging, startup API spawn, `health/dependencies` (YT/Whisper/Ollama/FFmpeg/SQLite) checks
- Docs: runbooks, hardware limits (`transcription:1, vision:1, editorial:1, render:1`), perf order (transcribe→vision→LLM→render)

**Out of scope:** PostgreSQL/Redis/S3/multi-user/auth/cloud, auto-publish, custom ML training (log data only).

**Tasks:**
- [ ] `tests/{discovery,scoring,transcription,clipping,editorial,rendering,rights,api}/` green + golden + render QA suites
- [ ] Demos 1→2→3 sign-off (impl-guide §31–33) recorded in worklog
- [ ] Release tag `v0.1.0-mvp`, packaged installer smoke test

**Verification:**
```powershell
pytest -q
npm run test --workspaces
# Demo 1 script: Discover → select permitted → transcribe → 5 moments → approve 3 → render → play
```

**Exit criteria:**
- M9-seed done: Demo 1 reliable, feedback export exists, packaged app installs/launches.
- `Initial Definition of Done` (arch §29, 14 boxes) all checked with evidence links to worklog commits.

---

### Sprint dependency map

```text
S0 → S1 → S2 → S3 → S4 → S5 → S6 → S7 → S8 → S9 (= MVP loop, Demo 1)
S9 → S10 → S11 → S12 → S13 → S14 (= autonomy + ship)
S3 snapshots required for S11 velocity. S12 must gate S13 publish.
S7 feedback required for S14 learning dataset.
```
