# Automatic YouTube Mega Clipper - Roadmap

**Status:** MVP complete (S0-S14 shipped, tag `v0.1.0-mvp`) - debt items D1-D7 done
**Goal:** Progress from a manually controlled local clipper into an autonomous trend-to-episode media engine.

## Current state

- Sprints S0-S14 and debt items D1-D7 are implemented and verified; see
  `worklog.md` for the evidence trail (live demos, test counts, commits).
- Gates: `pytest -q` 159 - `vitest` 40 - `playwright` 4/4 passed, including
  **live discovery** against the real YouTube API via `YTPOP_YOUTUBE_API_KEY`
  in `.env`.
- Checked boxes below mean implemented *and* verified. Unchecked boxes mean
  not built yet.

## Remaining work

- [x] Live discovery E2E with a YouTube key (the adapter itself is covered by mocks).
- [ ] NSIS installer smoke test (the `--dir` win-unpacked build is verified).
- [ ] Scene detection (S4 scope item, never built).
- [ ] Phase 9 Originality layer: AI context, narration, commentary,
      comparisons, visual annotations, charts, timeline graphics, source cards.
- [ ] Shrink the packaged build (~720MB, dominated by the local shared ffmpeg).
- [ ] Retraining cadence for the learned ranker (D4 trains on demand).
---

# 1. North Star


The long-term system should be able to operate like a small autonomous editorial team:



```text

                  INTERNET

                     â”‚

                     â–¼

              TREND DISCOVERY

                     â”‚

                     â–¼

              TOPIC DETECTION

                     â”‚

                     â–¼

              SOURCE ANALYSIS

                     â”‚

                     â–¼

               MOMENT FINDING

                     â”‚

                     â–¼

                RIGHTS GATE

                     â”‚

                     â–¼

             EDITORIAL PLANNING

                     â”‚

                     â–¼

              ORIGINAL CONTEXT

                     â”‚

                     â–¼

                  EDITING

                     â”‚

                     â–¼

                 RENDERING

                     â”‚

                     â–¼

                    QA

                     â”‚

                     â–¼

              HUMAN APPROVAL

                     â”‚

                     â–¼

             AUTHORIZED OUTPUT

```



The goal is not to eliminate humans immediately.



The goal is to make the human increasingly become:



> **editor-in-chief instead of video editor.**



---



# 2. Phase 0 â€” Architecture



## Goal



Create the foundation.



### Deliverables



- [x] `architecture.md`

- [x] `implementation-guide.md`

- [x] `roadmap.md`

- [x] Repository

- [x] README

- [x] Environment configuration

- [x] Initial database design

- [x] Initial API contract

### Exit criteria



The project can be handed to an implementation agent without requiring it to invent the architecture.



---



# 3. Phase 1 â€” Application Foundation



## Goal



Create the local desktop application.



### Tasks



- [x] Electron

- [x] React

- [x] TypeScript

- [x] Vite

- [x] FastAPI

- [x] SQLite

- [x] SQLAlchemy

- [x] Alembic

- [x] Basic logging

- [x] Health endpoint

- [x] Dependency health endpoint

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

  â†“

React

  â†“

FastAPI

  â†“

SQLite

```



works reliably.



---



# 4. Phase 2 â€” Discovery Engine



## Goal



Find what is popular.



### Tasks



- [x] YouTube API integration

- [x] Region selection

- [x] Category selection

- [x] Most-popular discovery

- [x] Search discovery

- [x] Source metadata storage

- [x] Historical snapshots

- [x] API quota tracking

- [x] Discovery scheduling

The YouTube Data API provides a `mostPopular` chart through `videos.list`, with optional region/category filtering. îˆ€citeîˆ‚turn0search4îˆ



### Exit criteria



Dashboard displays:



```text

Trending now

Recently rising

Fastest growing

Top categories

```



---



# 5. Phase 3 â€” Trend Intelligence



## Goal



Stop thinking in individual videos.



Start thinking in **events/topics**.



### Tasks



- [x] Embeddings

- [x] Similarity

- [x] Topic clustering

- [x] Trend scoring

- [x] Velocity calculation

- [x] Cross-video relationships

- [x] Trend history

- [x] Topic summaries

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

ðŸ”¥ MAJOR GAME UPDATE

  12 videos

  +184% velocity

  4.2M combined views

```



### Exit criteria



System can identify a trend containing multiple related videos.



---



# 6. Phase 4 â€” Media Analysis



## Goal



Understand individual videos.



### Tasks



- [x] Media ingestion

- [x] FFmpeg probe

- [x] Audio extraction

- [x] Whisper transcription

- [ ] Scene detection

- [x] Transcript indexing

- [x] Thumbnail extraction

- [x] Metadata normalization

### Exit criteria



Given a permitted test source:



```text

video

 â†“

transcript

 â†“

scenes

 â†“

searchable timeline

```



---



# 7. Phase 5 â€” Automatic Clip Finder



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



# 8. Phase 6 â€” Clip Review



## Goal



Make human correction extremely fast.



### UI



```text

Candidate #1

â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

â–¶ Preview



Score: 91



Hook       â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘ 90

Emotion    â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆ 96

Novelty    â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘â–‘ 82

Context    â–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–ˆâ–‘ 91



[Reject] [Trim] [Approve]

```



### Tasks



- [x] Clip preview

- [x] Timeline trimming

- [x] Approve/reject

- [x] Notes

- [x] Categories

- [x] Score visibility

- [x] Keyboard shortcuts

### Exit criteria



Human can review dozens of clips quickly.



---



# 9. Phase 7 â€” Manual Mega-Video



## Goal



Prove the basic product.



### Workflow



```text

Find videos

 â†“

Find clips

 â†“

Approve clips

 â†“

Drag into timeline

 â†“

Render

```



### Tasks



- [x] Timeline

- [x] Reordering

- [x] Trimming

- [x] Transitions

- [x] Intro

- [x] Outro

- [x] Captions

- [x] Audio normalization

- [x] Rendering

- [x] Preview

### Exit criteria



User can create a finished episode without external editing software.



---



# 10. Phase 8 â€” AI Editorial Engine



## Goal



Make the AI the editor.



### Tasks



- [x] Story clustering

- [x] Segment ordering

- [x] Hook selection

- [x] Context generation

- [x] Transition generation

- [x] Narrative planning

- [x] Episode title generation

- [x] Description generation

- [x] Thumbnail concepts

### Core question



The AI should answer:



> "Why should these clips appear together?"



not merely:



> "Which clips have the highest score?"



### Exit criteria



AI can generate a plausible episode outline from approved candidate moments.



---



# 11. Phase 9 â€” Originality Layer



## Goal



Move from compilation toward genuine editorial production.



### Features



- [ ] AI-generated context

- [ ] Original narration

- [ ] Commentary

- [ ] Comparison segments

- [x] Topic summaries

- [ ] Visual annotations

- [ ] Charts

- [ ] Timeline graphics

- [ ] Source cards



YouTube's current monetization guidance distinguishes meaningful transformation/commentary from minimally altered reused material. îˆ€citeîˆ‚turn0search0îˆ‚turn0search3îˆ



This should therefore be a core product feature, not a last-minute patch.



---



# 12. Phase 10 â€” Rights System



## Goal



Prevent the application from treating discovered material as automatically publishable.



### Tasks



- [x] Rights records

- [x] Source owner

- [x] License tracking

- [x] Permission evidence

- [x] Review state

- [x] Commercial-use field

- [x] Territory

- [x] Expiration

- [x] Human approval

- [x] Publish blocker

### State machine



```text

UNKNOWN

 â†“

REVIEW_REQUIRED

 â”œâ”€â”€â†’ APPROVED

 â”œâ”€â”€â†’ REJECTED

 â””â”€â”€â†’ NEEDS_PERMISSION

```



Copyright and fair-use questions remain fact-specific; YouTube explicitly notes that adding material does not automatically establish fair use and that courts ultimately decide fair use. îˆ€citeîˆ‚turn0search1îˆ



### Exit criteria



The application cannot accidentally represent an uncleared source as cleared.



---



# 13. Phase 11 â€” Autonomous Daily Episode



## Goal



One button becomes one episode.



```text

GENERATE TODAY'S EPISODE

```



Pipeline:



```text

Discover

 â†“

Rank

 â†“

Cluster

 â†“

Analyze

 â†“

Find moments

 â†“

Rights filter

 â†“

Editorial plan

 â†“

Generate context

 â†“

Build timeline

 â†“

Render

 â†“

QA

 â†“

Review

```



### Exit criteria



The system can produce a complete draft episode with minimal intervention.



---



# 14. Phase 12 â€” 24/7 Mode



## Goal



Make the system continuously observe the internet.



Scheduler:



```text

every 15 min

    â†“

trend scan



every 30 min

    â†“

source refresh



every hour

    â†“

topic clustering



continuous

    â†“

analysis queue

```



Priority should be dynamic.



Example:



```text

BREAKING TREND

    â†“

priority 100



RISING TREND

    â†“

priority 70



NORMAL

    â†“

priority 30



OLD

    â†“

priority 5

```



---



# 15. Phase 13 â€” Learning From the Editor



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

        â†“

ranking model

        â†“

editor feedback

        â†“

training data

        â†“

better ranking

```



---



# 16. Phase 14 â€” Personalization



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



# 17. Phase 15 â€” Multi-Format Publishing



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

â”œâ”€â”€ Segment A

â”œâ”€â”€ Segment B

â”œâ”€â”€ Segment C

â”œâ”€â”€ Segment D

â””â”€â”€ Segment E

```



can produce multiple derivatives.



---



# 18. Phase 16 â€” Advanced Intelligence



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

 â”œâ”€â”€ original source

 â”œâ”€â”€ reactions

 â”œâ”€â”€ responses

 â”œâ”€â”€ counterarguments

 â””â”€â”€ follow-ups

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

                      â”‚

              â”Œâ”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”

              â”‚               â”‚

           SOURCES         CONTEXT

              â”‚               â”‚

              â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”˜

                      â–¼

                 STORY GRAPH

                      â”‚

              â”Œâ”€â”€â”€â”€â”€â”€â”€â”´â”€â”€â”€â”€â”€â”€â”€â”€â”

              â–¼                â–¼

          MOMENTS          COMMENTARY

              â”‚                â”‚

              â””â”€â”€â”€â”€â”€â”€â”€â”¬â”€â”€â”€â”€â”€â”€â”€â”€â”˜

                      â–¼

                EDITOR AGENT

                      â”‚

                      â–¼

                VIDEO AGENT

                      â”‚

                      â–¼

                 QA AGENT

                      â”‚

                      â–¼

               HUMAN REVIEW

```



At this stage the project starts behaving like an autonomous newsroom.



---



# 20. Agent Architecture â€” Future



Do not build this initially, but eventually the system can separate responsibilities.



```text

Scout Agent

   â†“

Trend Agent

   â†“

Research Agent

   â†“

Clip Agent

   â†“

Rights Agent

   â†“

Editor Agent

   â†“

Narrator Agent

   â†“

Video Agent

   â†“

QA Agent

```



Each agent should communicate through structured artifacts rather than free-form chat.



---



# 21. Potential Agent Loop



```text

SCOUT

 â†“

"I found something interesting."



RESEARCH

 â†“

"Here is what happened."



CLIPPER

 â†“

"These are the strongest moments."



RIGHTS

 â†“

"These sources are cleared/review-required."



EDITOR

 â†“

"Here is the story."



VIDEO

 â†“

"Here is the render."



QA

 â†“

"Pass."



HUMAN

 â†“

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



# 23. Milestone Map (linked to Sprints in Â§26)



| Milestone | Sprints | Demo proof |

|---|---|---|

| M1 â€” "It Works" | S0, S1, S2 | App opens, health green, DB migrates |

| M2 â€” "It Finds Things" | S3, S11-partial | Dashboard shows Trending / Rising / Fastest |

| M3 â€” "It Clips" | S4, S5, S6, S7 | 1 permitted source â†’ transcript â†’ Top-10 â†’ review |

| M4 â€” "It Edits" | S8, S9 | Manual timeline â†’ rendered 1080p + captions, in-app playback |

| M5 â€” "It Thinks" | S10 | Approved moments â†’ plausible JSON outline (Pydantic-valid) |

| M6 â€” "It Understands Trends" | S11 | Multi-video topic cluster with velocity |

| M7 â€” "It Produces Shows" | S10, S12, S13-partial | One-button draft episode to review queue |

| M8 â€” "It Runs Itself" | S13 | Scheduler + idempotent jobs + retry, Demo 3 pass |

| M9 â€” "It Learns" | S14 | Approval/reject/trim feedback stored, ranking improves |



## M1 â€” "It Works" (exit: S2 done)



```text

Electron

+

React

+

FastAPI

+

SQLite

```



## M2 â€” "It Finds Things"



```text

YouTube discovery

+

trend scoring

```



## M3 â€” "It Clips"



```text

transcription

+

candidate detection

+

clip review

```



## M4 â€” "It Edits"



```text

timeline

+

rendering

+

captions

```



## M5 â€” "It Thinks"



```text

AI editorial engine

```



## M6 â€” "It Understands Trends"



```text

topic clustering

+

cross-source analysis

```



## M7 â€” "It Produces Shows"



```text

automated episode generation

```



## M8 â€” "It Runs Itself"



```text

24/7 scheduler

+

job system

+

autonomous pipeline

```



## M9 â€” "It Learns"



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

 â†“

SOURCE

 â†“

TRANSCRIPT

 â†“

MOMENT

 â†“

CLIP

 â†“

EPISODE

 â†“

VIDEO

```



Once that loop works, everything else becomes an iteration on top of a working foundation.



---



# 26. Sprint Plan with Exit Goals (S0â€“S14)



> Source of truth for `worklog.md` and commit prefixes (`S0:`, `S1:`, â€¦).

> Maps to: Roadmap Phases above, `implementation-guide.md` Sprints, `architecture.md` modules.

> Workflow per sprint: `plan â†’ scope â†’ implement â†’ verify (tests) â†’ worklog â†’ commit â†’ push` (see `agents.md`).

> Rule: do not start S{N+1} until S{N} exit criteria are met and logged.



## Sprint template (every sprint follows this)



```text

Goal / In scope / Out of scope

â†’ Tasks

â†’ Verification (exact pytest / vitest / manual checks)

â†’ Exit criteria (measurable DoD)

â†’ Worklog entry + commit

```



Global DoD for any code sprint (from `implementation-guide.md` Â§37):



```text

typed in/out, persisted result, idempotent, fails safely + retryable,

useful logs with correlation IDs, tests, inspectable artifacts,

no secrets in logs, no silent failure discards

```



---



### S0 â€” Repo & Docs Baseline (Maps to: Phase 0, Impl Â§3, M1-pre)



**Goal:** Git + docs + env baseline so an agent can implement without inventing architecture.



**In scope:**

- `git init`, `main` branch, `.gitignore` (Python/Node/Electron/`data/*`!`/configs/`/`.env`), `.env.example`

- `README.md` (what/why/quickstart), `docs/` move (arch/impl/roadmap), `agents.md`, `worklog.md`

- `gh repo create YtPop --public --source=. --push`



**Out of scope:** any app code, DB, API.



**Tasks:**

- [x] `git init && git branch -M main`

- [x] Add `.gitignore`, `README.md`, `.env.example`

- [x] Add `agents.md`, `worklog.md`

- [x] Initial commit + `gh repo create YtPop --public`

- [x] Verify `gh repo view`, `git log`, `git status` clean



**Verification:**

```text

git status  # clean

git log --oneline -3

gh repo view --json name,visibility

Test-Path .git â†’ True

```



**Exit criteria:**

- Repo exists locally + on GitHub (`YtPop`, public).

- Docs (`architecture.md`, `implementation-guide.md`, `roadmap.md`, `agents.md`, `worklog.md`, `README.md`) committed.

- New clone + `gh repo clone` path documented in `worklog.md` S0 entry.



---



### S1 â€” Foundation: Electron + React + FastAPI Health (Phase 1, Impl Â§5, M1)



**Goal:** `Electron â†’ React â†’ FastAPI` communicating locally.



**In scope:**

- `apps/api/app/main.py`, `config.py` (`pydantic-settings`), `structlog` baseline

- `GET /api/v1/health`, `GET /api/v1/health/dependencies`

- `apps/desktop/electron/{main,preload}.ts`, `apps/desktop/renderer/` (Vite+React+TS, health badge page)

- `pyproject.toml`, `package.json`, `pytest` + `vitest` scaffolds



**Out of scope:** DB, YouTube, media, jobs.



**Tasks:**

- [x] FastAPI app + versioned router (`/api/v1`)

- [x] Health endpoints returning `{"status":"ok","version":"0.1.0"}`

- [x] Electron launches backend + opens Vite frontend (dev mode)

- [x] Frontend `useHealth()` hook + Dashboard status card

- [x] Backend test `tests/test_health.py`, frontend smoke test



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



### S2 â€” Database + Migrations (Phase 1, Impl Â§6, M1)



**Goal:** Versioned SQLite schema for all core entities.



**In scope:**

- `data/database/mega_clipper.db` (gitignored, created at runtime)

- SQLAlchemy 2 models: `sources, trend_events, trend_sources, transcripts, moments, episodes, episode_segments, jobs, rights_records, renders`

- Alembic init + first migration, `db/database.py` session factory

- `POST /sources` (test create) + `GET /sources/{id}` minimal read



**Out of scope:** YouTube logic, transcription, full CRUD UI.



**Tasks:**

- [x] Models with types/constraints matching `architecture.md` Â§6

- [x] `alembic revision --autogenerate`, `alembic upgrade head`, downgrade check

- [x] Seed/test-source round-trip test

- [x] DB path via config, `data/` dirs with `.gitkeep`

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



### S3 â€” YouTube Discovery (Phase 2, Impl Â§7, M2-start)



**Goal:** Find what's popular without burning quota.



**In scope:**

- `services/youtube_service.py`: `get_most_popular(), search_videos(), get_video(), get_channel(), get_categories()`

- `POST /sources/discover`, `POST /trends/discover`, `GET /sources`, `GET /trends`, quota-tracking table/fields

- Snapshot history per source (for velocity), region/category filters, scheduler stub (manual trigger only)



**Out of scope:** clustering, transcription, auto-scheduling.



**Tasks:**

- [x] Thin YouTube Data API adapter (`videos.list chart=mostPopular`, `search.list`, `channels.list`, `videoCategories.list`)

- [x] Persist `sources` + snapshot rows on every fetch

- [x] Quota counter + aggressive cache (no re-fetch unchanged metadata)

- [x] Dashboard lists: Trending now / Recently rising / Fastest growing / Top categories

- [x] Mocked adapter tests (no live quota in CI)

**Verification:**

```powershell

pytest apps/api/tests/discovery/ -v  # mock adapter, quota guard, velocity math

# manual with key: discover US/gaming â†’ 20+ sources in DB

```



**Exit criteria:**

- Dashboard renders 4 discovery sections from DB.

- Snapshots enable velocity calc; quota usage visible in logs/UI.

- No live API calls in automated tests.



---



### S4 â€” Media Ingestion (Phase 4-part, Impl Â§8, M3-start)



**Goal:** Permitted local media â†’ normalized assets.



**In scope:**

- `services/ffmpeg_service.py` + `MediaIngestionService.probe/normalize/extract_audio/extract_thumbnail/verify_media`

- `data/{raw,media,thumbnails,logs}/` artifacts + DB linkage

- `POST /sources/{id}/analyze` (probe only)



**Out of scope:** downloading arbitrary YouTube videos as core flow; transcription.



**Tasks:**

- [x] FFmpeg via arg-arrays (never shell-concat), path restricted to `data/`

- [x] Probe â†’ normalize (1080p/mezzanine) â†’ 16kHz wav â†’ thumb jpg

- [x] `verify_media` (streams, duration>0, audio present)

- [x] Accept only `USER_OWNED/LICENSED/CC/PUBLIC_DOMAIN` test material with basis recorded



**Verification:**

```powershell

pytest apps/api/tests/test_ingestion.py -v  # fixture mp4 â†’ probe/normalize/audio/thumb

# negative: path traversal rejected, corrupt file fails safely

```



**Exit criteria:**

- Fixture video produces inspectable artifacts + DB record.

- Corrupt/evil paths fail with clear error, no crash, no shell injection.



---



### S5 â€” Transcription (Phase 4, Impl Â§9, M3)



**Goal:** Audio â†’ timestamped searchable transcript.



**In scope:**

- `services/whisper_service.py` (`faster-whisper`), `POST /sources/{id}/transcribe`, `GET /sources/{id}/transcript`

- `transcripts` table + `data/transcripts/{source_id}.json` (preserve word timings)

- Job type `TRANSCRIBE` (sync first, queue-ready payload)



**Out of scope:** scoring, diarization perfection.



**Tasks:**

- [x] `media â†’ wav â†’ whisper â†’ segments[{start,end,text,confidence}] â†’ DB + json`

- [x] Language + model name stored; idempotent re-run (skip if hash match)

- [x] Concurrency=1 default (see `configs/default.yaml`)



**Verification:**

```powershell

pytest apps/api/tests/transcription/ -v  # 60s fixture â†’ segments schema valid, timings monotonic

```



**Exit criteria:**

- Given permitted test source: `video â†’ transcript â†’ searchable timeline` viewable in Sources page.

- Word timings preserved for captions/boundaries later.



---



### S6 â€” Clip Detection V1 (Phase 5-V1/V2, Impl Â§10, M3)



**Goal:** Transcript â†’ ranked candidate moments (no vision yet).



**In scope:**

- `domain/clipping/` candidate generator (5â€“90s windows) + scorer (`hook/relevance/novelty/emotion/payoff/completeness - redundancy/dead_air/dependency`)

- `moments` table (all score columns), `POST /sources/{id}/find-moments`, `GET /moments`

- `configs/scoring.yaml` weights (not hardcoded)



**Out of scope:** vision, LLM judge (V3+), auto-publish.



**Tasks:**

- [x] Keyword + sentence-window baseline, then embedding similarity (`sentence-transformers`)

- [x] Store **all** candidates (don't delete low scores)

- [x] Golden fixture: `known transcript + config = expected ranges`

**Verification:**

```powershell

pytest apps/api/tests/clipping/ -v  # golden ranges Â±2s, scoring determinism

```



**Exit criteria:**

- System outputs `Top 10 moments` a human rates useful > random (log 10-sample check in worklog).

- Scoring weights editable without code change.



---



### S7 â€” Clip Review UI (Phase 6, Impl Â§11, M3-done)



**Goal:** Human correction extremely fast + feedback capture.



**In scope:**

- Review page (`Clips/`): preview, waveform/timeline trim, Approve/Reject/Trim, notes, category, Best flag, score breakdown, shortcuts (`J/L`, `I/O`, `A/R`)

- `PATCH /moments/{id}`, `POST /moments/{id}/preview` (FFmpeg slice)

- Feedback rows (`decision, reason, adjusted_start/end, at`) for future learning



**Out of scope:** auto-editing, rendering.



**Tasks:**

- [x] Candidate queue + filters (score/type/status)

- [x] Trim persisted, preview regenerable

- [x] Every action writes feedback record

**Verification:**

```powershell

pytest apps/api/tests/test_moments_api.py -v

npm run test --workspace=apps/desktop

# manual: review 20 clips in <10 min

```



**Exit criteria:**

- M3 done: transcribe â†’ candidates â†’ preview â†’ approve flows in-app with feedback stored.

- Keyboard-only review possible.



---



### S8 â€” Episode Builder, Manual (Phase 7, Impl Â§12, M4-start)



**Goal:** Prove basic product: human-assembled mega-video plan.



**In scope:**

- `episodes`, `episode_segments` CRUD: `POST /episodes`, `PATCH /episodes/{id}`, `POST /episodes/{id}/rebuild`

- Timeline UI: drag/reorder/trim/delete/duplicate, intro/outro/title cards, target vs actual duration

- Episode templates stub (`configs/editorial.yaml`, `templates/daily_highlights`)



**Out of scope:** AI story planning, narration, rendering.



**Tasks:**

- [x] Segment `{moment_id, sequence, transition_type, context_text}`

- [x] Duration roll-up + over/under indicator

- [x] Persist order server-side (not local-only)



**Verification:**

```powershell

pytest apps/api/tests/test_episodes.py -v  # reorder persistence, duration math

```



**Exit criteria:**

- User builds 5-clip episode, reorders, saves, reloads intact.

- No AI required to reach this point.



---



### S9 â€” Rendering + Captions (Phase 7, Impl Â§13, M4-done)



**Goal:** Episode â†’ finished video file playable in-app.



**In scope:**

- `RenderService`: episode â†’ FFmpeg filter-graph â†’ `youtube_1080p / preview_720p / vertical_1080x1920` presets

- Captions: Whisper words â†’ ASS/WebVTT â†’ burn-in (styles: standard/bold/highlight/vertical/minimal)

- `POST /episodes/{id}/render`, `GET /renders/{id}`, `POST /renders/{id}/cancel`, loudness normalize

- QA probe: exists, duration, audio+video streams, res/fps/codec, captions present, no corrupt frames



**Out of scope:** 4K perf tuning, thumbnail AI.



**Tasks:**

- [x] Deterministic filter-graph builder + job `RENDER`

- [x] Keep intermediates; final is not the only artifact

- [x] Render record `{preset,res,fps,codec,path,status,error}`



**Verification:**

```powershell

pytest apps/api/tests/rendering/ -v  # fixture 3-clip episode â†’ mp4 + QA asserts

# manual: play render in Episodes page

```



**Exit criteria:**

- M4 done: timeline â†’ render â†’ in-app playback, QA green logged.

- Failed render retryable with error surfaced.



---



### S10 â€” Editorial AI (Phase 8, Impl Â§14, M5)



**Goal:** AI proposes story, human disposes.



**In scope:**

- `domain/editorial/EditorialService` + `ModelRouter` (Ollama: classifierâ†’small, plannerâ†’medium, visionâ†’later) via `configs/default.yaml`

- `POST /episodes/{id}/generate` in: `{trend, sources, candidate_moments, rights, target_duration, format}` out: `{hook, clusters, order, transitions, context_reqs, ending, titles}`

- Strict JSON + Pydantic validation, never trust raw output



**Out of scope:** 24/7 autonomy, narration audio.



**Tasks:**

- [x] Prompt with structured summaries (not giant raw transcripts)

- [x] Validate/repair loop (max 2 retries, then fail job clearly)

- [x] Episode title/description/thumbnail-concept outputs



**Verification:**

```powershell

pytest apps/api/tests/editorial/ -v  # mocked LLM: valid plan accepted, malformed rejected

```



**Exit criteria:**

- Core question answered: "Why do these clips belong together?" (cluster + rationale per segment).

- Invalid model JSON never corrupts episode (job fails safely).



---



### S11 â€” Trend Intelligence (Phase 3, Impl Â§15, M6 + M2-done)



**Goal:** Think in events/topics, not videos.



**In scope:**

- `embeddings â†’ similarity â†’ clusters â†’ topic summaries â†’ trend_events` pipeline

- `trend_score = views_vel*.25 + eng_vel*.15 + recency*.15 + xsource*.20 + momentum*.15 + novelty*.10` (weights in yaml)

- `trend_sources {relevance, relationship_type}`, velocity from S3 snapshots



**Out of scope:** cross-platform (YT-only), prediction.



**Tasks:**

- [x] `sentence-transformers` local embeddings, cosine similarity, threshold clustering

- [x] Trend history + status, Trends page topic cards (e.g. `ðŸ”¥ GAME UPDATE Â· 12 vids Â· +184% Â· 4.2M`)

- [x] Job `CLUSTER_TRENDS`

**Verification:**

```powershell

pytest apps/api/tests/test_trends.py -v  # A/B/C/D fixture â†’ 1 topic, scoreâ‰ˆ91

```



**Exit criteria:**

- M2+M6 done: multi-video trend identified from DB, visible on Dashboard.

- Weights tunable without redeploy.



---



### S12 â€” Rights Workflow (Phase 10, Impl Â§16, M7-gate)



**Goal:** Never treat discovered material as publishable by default.



**In scope:**

- `rights_records` full fields (`status/basis/owner/license/ref/restrictions/territory/commercial/notes/verified_at/reviewer`)

- States: `UNKNOWN â†’ REVIEW_REQUIRED â†’ APPROVED/REJECTED/NEEDS_PERMISSION` (+ `LICENSED/CC/PUBLIC_DOMAIN/USER_OWNED` as approved bases)

- `GET /rights/{source_id}`, `POST /rights/{source_id}/review`, `PATCH /rights/{source_id}`, publish blocker (`READY_TO_PUBLISH` requires approved basis)



**Out of scope:** auto fair-use verdicts, public publishing.



**Tasks:**

- [x] State-machine enforced server-side + UI banner ("Rights basis: human review required")

- [x] Evidence attachments/URLs, expiry checks

- [x] Research/demo-only mode flag (analyze locally â‰  cleared)



**Verification:**

```powershell

pytest apps/api/tests/rights/ -v  # illegal transition rejected, publish blocked when UNKNOWN

```



**Exit criteria:**

- App cannot represent uncleared source as cleared (negative test logged).

- No UI string claims "Fair use confirmed".



---



### S13 â€” Automation: Daily Episode + Scheduler (Phases 11â€“12, Impl Â§17â€“18, M7+M8)



**Goal:** One button â†’ draft episode; then scheduled.



**In scope:**

- `PipelineOrchestrator`: `discover â†’ rank â†’ cluster â†’ analyze â†’ candidates â†’ rights-filter â†’ plan â†’ context â†’ timeline â†’ render â†’ QA â†’ review`

- SQLite `jobs {type/status/priority/payload/progress/attempts}` worker (`QUEUED/RUNNING/PAUSED/COMPLETED/FAILED/CANCELLED`), claimâ†’runâ†’artifactâ†’DBâ†’complete, exp-backoff retry

- Intervals: trend-scan 15m, source-refresh 30m, clustering 60m, analysis-queue continuous; priority `BREAKING 100 / RISING 70 / NORMAL 30 / OLD 5`

- Jobs UI (`GET /jobs`, retry/cancel)



**Out of scope:** multi-machine pool, learning ranker.



**Tasks:**

- [x] Each stage = job with idempotency key + checkpoint

- [x] `GENERATE TODAY'S EPISODE` button + overnight dry-run

- [x] Dashboard ops view (queue depth, quota, failures)

**Verification:**

```powershell

pytest apps/api/tests/test_jobs.py -v  # claim/run/fail/retry ordering

# manual Demo 3: scheduled run â†’ review queue with draft

```



**Exit criteria:**

- M7+M8 done: minimal-intervention draft episode end-to-end, failures retryable, scheduler logs show intervals honored.



---



### S14 â€” QA / Packaging / Learning Prep (Phases 13â€“16 bridges, Impl Â§19â€“33, M9)



**Goal:** Ship local MVP + instrument learning for future.



**In scope:**

- Feedback store (`moment_id, decision, reason, adj_start/end, at`) â†’ future ranker dataset export

- Clip Scoring V3â€“V5 stubs behind flags (LLM/vision/learned), vision sampling 1â€“3s (cheap detector first)

- Electron Builder packaging, startup API spawn, `health/dependencies` (YT/Whisper/Ollama/FFmpeg/SQLite) checks

- Docs: runbooks, hardware limits (`transcription:1, vision:1, editorial:1, render:1`), perf order (transcribeâ†’visionâ†’LLMâ†’render)



**Out of scope:** PostgreSQL/Redis/S3/multi-user/auth/cloud, auto-publish, custom ML training (log data only).



**Tasks:**

- [x] `tests/{discovery,scoring,transcription,clipping,editorial,rendering,rights,api}/` green + golden + render QA suites

- [x] Demos 1â†’2â†’3 sign-off (impl-guide Â§31â€“33) recorded in worklog

- [ ] Release tag `v0.1.0-mvp`, packaged installer smoke test



**Verification:**

```powershell

pytest -q

npm run test --workspaces

# Demo 1 script: Discover â†’ select permitted â†’ transcribe â†’ 5 moments â†’ approve 3 â†’ render â†’ play

```



**Exit criteria:**

- M9-seed done: Demo 1 reliable, feedback export exists, packaged app installs/launches.

- `Initial Definition of Done` (arch Â§29, 14 boxes) all checked with evidence links to worklog commits.



---



### Sprint dependency map



```text

S0 â†’ S1 â†’ S2 â†’ S3 â†’ S4 â†’ S5 â†’ S6 â†’ S7 â†’ S8 â†’ S9 (= MVP loop, Demo 1)

S9 â†’ S10 â†’ S11 â†’ S12 â†’ S13 â†’ S14 (= autonomy + ship)

S3 snapshots required for S11 velocity. S12 must gate S13 publish.

S7 feedback required for S14 learning dataset.

```

