# Automatic YouTube Mega Clipper — Architecture

**Status:** Baseline / v0.1  
**Purpose:** Technical architecture for an automated system that discovers trending YouTube topics/videos, identifies high-value moments, assembles them into coherent highlight episodes, and prepares finished videos for human review and/or authorized publishing.

---

## 1. Product Definition

### 1.1 Core idea

The system is an autonomous media pipeline:

```text
Discover → Rank → Analyze → Find Moments → Rights Gate → Storyboard
→ Edit → Render → QA → Review → Publish/Export
```

The important distinction is that this is **not merely a video downloader + concatenator**.

The target product is an AI editorial engine that can answer:

- What is trending?
- Why is it trending?
- Which videos are relevant to the trend?
- What moments are actually interesting?
- Which moments are redundant?
- What order creates the best story?
- Where should context/commentary appear?
- What should the final episode be called?
- Which source material is permitted for the intended use?

### 1.2 Example output

> **THE INTERNET TODAY — August 29, 2026**
>
> 12 trending stories  
> 31 selected moments  
> 18:42 runtime  
> 7 topic clusters  
> 3 source clips per story on average

Possible episode formats:

- Daily internet highlights
- Gaming highlights
- Tech news moments
- Sports reactions
- Viral moments
- Creator drama/news
- Meme/event recap
- Category-specific daily shows
- Weekly mega-compilations

---

# 2. Design Principles

1. **Local-first**
2. **API-first**
3. **Asynchronous pipeline**
4. **Every stage produces inspectable artifacts**
5. **Idempotent jobs**
6. **Human review is always possible**
7. **Rights are first-class metadata**
8. **AI decisions are explainable**
9. **Rendering is deterministic**
10. **Cheap models first, expensive models only when justified**
11. **Source media is never treated as automatically reusable**
12. **The system should be able to run unattended**
13. **Every decision should be reproducible**
14. **The architecture should support multiple content providers later**

---

# 3. Recommended Stack

## 3.1 Application

| Layer | Technology | Reason |
|---|---|---|
| Desktop shell | Electron | Local-first desktop control center |
| Frontend | React + TypeScript | Mature UI ecosystem |
| Build | Vite | Fast development/build |
| Backend API | FastAPI | Python + async + excellent API tooling |
| ORM | SQLAlchemy 2 | Strong DB abstraction |
| Database | SQLite | Excellent local MVP database |
| Validation | Pydantic | API/domain validation |
| Job queue | SQLite-backed job table initially | Avoid Redis dependency |
| Media processing | FFmpeg | Industry-standard media pipeline |
| Transcription | faster-whisper | Local speech-to-text |
| Scene detection | PySceneDetect + FFmpeg | Useful deterministic baseline |
| AI inference | Ollama | Local model serving |
| Embeddings | sentence-transformers | Local semantic similarity |
| Vector search | SQLite vector extension / LanceDB later | Avoid premature infrastructure |
| Rendering | FFmpeg | Fast, scriptable, deterministic |
| Testing | pytest + Vitest | Python + frontend coverage |
| Logging | structlog | Structured logs |
| Config | pydantic-settings | Typed environment/config |
| Packaging | Electron Builder | Desktop distribution |

## 3.2 AI model strategy

The system should not depend on one giant model.

Use a model ladder:

```text
Cheap deterministic logic
        ↓
Small local LLM
        ↓
Medium local LLM
        ↓
Vision model
        ↓
Large/cloud model (optional)
```

Example responsibilities:

### Small model
- Classification
- Topic labels
- Clip descriptions
- Metadata cleanup
- Initial relevance scoring

### Medium model
- Story grouping
- Editorial summaries
- Clip ranking
- Narrative planning

### Vision model
- Scene understanding
- Visual event detection
- Face/speaker/layout awareness
- Thumbnail analysis

### Embedding model
- Duplicate detection
- Semantic similarity
- Topic clustering
- Source-to-source relationship detection

---

# 4. High-Level Architecture

```text
┌───────────────────────────────────────────────────────────────┐
│                         ELECTRON APP                          │
│                                                               │
│ Dashboard | Trends | Sources | Clips | Episodes | Review     │
└───────────────────────────────┬───────────────────────────────┘
                                │ HTTP
                                ▼
┌───────────────────────────────────────────────────────────────┐
│                         FASTAPI                               │
│                                                               │
│ Discovery │ Analysis │ Clips │ Rights │ Episodes │ Rendering  │
└───────────────────────────────┬───────────────────────────────┘
                                │
              ┌─────────────────┼──────────────────┐
              ▼                 ▼                  ▼
        SQLite Database     Job Runner        Artifact Store
              │                 │                  │
              │                 ▼                  │
              │          AI/Media Workers          │
              │                 │                  │
              │       ┌─────────┼─────────┐        │
              │       ▼         ▼         ▼        │
              │    Ollama   Whisper    FFmpeg       │
              │                                      │
              └──────────────────────────────────────┘
```

---

# 5. Repository Structure

```text
youtube-mega-clipper/
│
├── apps/
│   ├── desktop/
│   │   ├── electron/
│   │   │   ├── main.ts
│   │   │   ├── preload.ts
│   │   │   └── ipc/
│   │   └── renderer/
│   │       ├── src/
│   │       │   ├── components/
│   │       │   ├── pages/
│   │       │   │   ├── Dashboard/
│   │       │   │   ├── Trends/
│   │       │   │   ├── Sources/
│   │       │   │   ├── Clips/
│   │       │   │   ├── Episodes/
│   │       │   │   ├── Review/
│   │       │   │   └── Settings/
│   │       │   ├── hooks/
│   │       │   ├── services/
│   │       │   ├── stores/
│   │       │   ├── types/
│   │       │   └── App.tsx
│   │       └── index.html
│   │
│   └── api/
│       ├── app/
│       │   ├── main.py
│       │   ├── config.py
│       │   ├── dependencies.py
│       │   │
│       │   ├── api/
│       │   │   ├── routes/
│       │   │   │   ├── health.py
│       │   │   │   ├── trends.py
│       │   │   │   ├── sources.py
│       │   │   │   ├── clips.py
│       │   │   │   ├── rights.py
│       │   │   │   ├── episodes.py
│       │   │   │   ├── renders.py
│       │   │   │   ├── jobs.py
│       │   │   │   └── settings.py
│       │   │
│       │   ├── db/
│       │   │   ├── database.py
│       │   │   ├── models/
│       │   │   └── migrations/
│       │   │
│       │   ├── domain/
│       │   │   ├── discovery/
│       │   │   ├── analysis/
│       │   │   ├── clipping/
│       │   │   ├── rights/
│       │   │   ├── editorial/
│       │   │   ├── rendering/
│       │   │   └── publishing/
│       │   │
│       │   ├── workers/
│       │   │   ├── discovery_worker.py
│       │   │   ├── transcription_worker.py
│       │   │   ├── clip_worker.py
│       │   │   ├── editorial_worker.py
│       │   │   └── render_worker.py
│       │   │
│       │   └── services/
│       │       ├── youtube_service.py
│       │       ├── ollama_service.py
│       │       ├── whisper_service.py
│       │       ├── ffmpeg_service.py
│       │       └── embedding_service.py
│       │
│       └── tests/
│
├── packages/
│   ├── shared-types/
│   ├── media-core/
│   └── editorial-core/
│
├── data/
│   ├── database/
│   ├── raw/
│   ├── media/
│   ├── transcripts/
│   ├── clips/
│   ├── episodes/
│   ├── renders/
│   ├── thumbnails/
│   └── logs/
│
├── configs/
│   ├── default.yaml
│   ├── categories.yaml
│   ├── scoring.yaml
│   └── editorial.yaml
│
├── scripts/
├── docs/
├── tests/
├── .env.example
├── pyproject.toml
├── package.json
└── README.md
```

---

# 6. Core Data Model

## sources

Represents discovered videos.

```text
id
provider
external_id
url
title
channel_id
channel_name
published_at
duration
view_count
like_count
comment_count
category
description
thumbnail_url
trend_score
discovered_at
last_checked_at
status
```

## trend_events

```text
id
topic
description
score
velocity
region
category
first_detected_at
last_detected_at
status
```

## trend_sources

```text
trend_id
source_id
relevance_score
relationship_type
```

## transcripts

```text
id
source_id
language
model
text
segments_json
created_at
```

Each segment should contain:

```json
{
  "start": 124.42,
  "end": 131.88,
  "text": "...",
  "speaker": "unknown",
  "confidence": 0.91
}
```

## moments

```text
id
source_id
start_time
end_time
transcript_excerpt
moment_type
semantic_score
emotion_score
novelty_score
visual_score
editorial_score
final_score
status
```

## rights_records

```text
id
source_id
status
basis
owner
license
permission_reference
restrictions
territory
commercial_allowed
notes
verified_at
```

Possible statuses:

```text
UNKNOWN
REVIEW_REQUIRED
PERMISSION_GRANTED
LICENSED
CREATIVE_COMMONS
PUBLIC_DOMAIN
USER_OWNED
EDITORIAL_EXCEPTION_REVIEW
REJECTED
```

## episodes

```text
id
title
format
theme
target_duration
actual_duration
status
created_at
updated_at
```

## episode_segments

```text
id
episode_id
moment_id
sequence
duration
transition_type
commentary_text
context_text
```

## renders

```text
id
episode_id
preset
resolution
fps
codec
path
status
created_at
completed_at
error
```

## jobs

```text
id
type
status
priority
payload_json
progress
attempts
error
created_at
started_at
completed_at
```

---

# 7. API Design

Base:

```text
/api/v1
```

## Health

```http
GET /health
GET /health/dependencies
```

## Discovery

```http
POST /trends/discover
GET  /trends
GET  /trends/{id}

POST /sources/discover
GET  /sources
GET  /sources/{id}
POST /sources/{id}/analyze
```

## Transcription

```http
POST /sources/{id}/transcribe
GET  /sources/{id}/transcript
```

## Moments

```http
POST /sources/{id}/find-moments
GET  /moments
GET  /moments/{id}
PATCH /moments/{id}
POST /moments/{id}/preview
```

## Rights

```http
GET  /rights/{source_id}
POST /rights/{source_id}/review
PATCH /rights/{source_id}
```

## Episodes

```http
POST /episodes
GET  /episodes
GET  /episodes/{id}
POST /episodes/{id}/generate
POST /episodes/{id}/rebuild
PATCH /episodes/{id}
```

## Rendering

```http
POST /episodes/{id}/render
GET  /renders/{id}
POST /renders/{id}/cancel
```

## Jobs

```http
GET /jobs
GET /jobs/{id}
POST /jobs/{id}/retry
POST /jobs/{id}/cancel
```

---

# 8. YouTube Integration

The primary discovery integration should use the official YouTube Data API.

The API supports `videos.list` with `chart=mostPopular`, optionally filtered by region and category. citeturn0search4turn0search8

Initial integration:

```text
YouTube Data API
    │
    ├── videos.list
    │     └── mostPopular
    │
    ├── search.list
    │
    ├── channels.list
    │
    ├── playlistItems.list
    │
    └── videoCategories.list
```

Important: YouTube API usage is quota-based. Google documents a default daily quota allocation and notes that API requests consume quota, so discovery should cache aggressively and avoid unnecessary repeated calls. citeturn0search12

The system should therefore store historical snapshots rather than repeatedly querying the same metadata.

---

# 9. Trend Detection

A source's raw popularity is not enough.

Calculate:

```text
trend_score =
    popularity_score
  + velocity_score
  + engagement_score
  + recency_score
  + cross_source_score
  + topic_momentum_score
  + novelty_score
```

Example:

```python
trend_score = (
    views_velocity * 0.25
    + engagement_velocity * 0.15
    + recency * 0.15
    + cross_source_frequency * 0.20
    + topic_momentum * 0.15
    + novelty * 0.10
)
```

Weights must be configurable rather than hard-coded permanently.

---

# 10. Clip Detection Pipeline

A video should pass through several increasingly expensive stages.

```text
Video
 ↓
Metadata filter
 ↓
Transcript
 ↓
Candidate sentence windows
 ↓
Semantic scoring
 ↓
Emotion/novelty scoring
 ↓
Scene detection
 ↓
Visual analysis
 ↓
Boundary refinement
 ↓
Clip candidate
```

## Candidate scoring

```text
clip_score =
    semantic_relevance
  + hook_strength
  + novelty
  + emotional_intensity
  + visual_interest
  + narrative_usefulness
  - redundancy
  - dead_air
  - context_dependency
```

---

# 11. Clip Boundary Engine

Do not simply cut at sentence boundaries.

The system should determine:

```text
pre_context
    ↓
setup
    ↓
payoff
    ↓
reaction
    ↓
exit
```

Then trim dead space while preserving comprehension.

Example:

```text
Raw:
02:14.2 ───────────── 02:31.7

AI:
02:18.4 ───────────── 02:29.8
       setup → payoff → reaction
```

---

# 12. Editorial Engine

This is the feature that differentiates the project.

The editorial engine converts a collection of clips into a story.

Inputs:

```text
trend
source metadata
candidate moments
transcripts
topic relationships
rights status
target duration
episode format
```

Outputs:

```text
episode outline
segment order
transitions
context
commentary
opening hook
closing
```

Example:

```json
{
  "episode": "Today's Biggest Gaming Moments",
  "segments": [
    {
      "type": "hook",
      "moment_id": 81
    },
    {
      "type": "context",
      "text": "..."
    },
    {
      "type": "clip",
      "moment_id": 21
    },
    {
      "type": "comparison",
      "moment_ids": [31, 44]
    }
  ]
}
```

---

# 13. Originality / Transformation Layer

The system should not be designed around simply stitching together other creators' videos.

YouTube states that reused content without significant original commentary, substantive modification, or meaningful educational/entertainment value can be ineligible for monetization. YouTube explicitly gives examples such as critical review, reaction with commentary, and edited footage with added storyline/commentary as potentially acceptable forms of transformed content. citeturn0search0turn0search3

Therefore the architecture should support:

- Original narration
- Context cards
- Editorial analysis
- Comparisons
- Commentary
- On-screen explanations
- Topic summaries
- Visual annotations
- Original graphics
- Story structure

This is not a legal guarantee.

Copyright and fair-use analysis are separate from YouTube's monetization rules. YouTube notes that fair use is case-specific and ultimately determined by courts. citeturn0search1turn0search2

---

# 14. Rights Gate

No source should silently move from:

```text
DISCOVERED
```

to:

```text
PUBLISHABLE
```

Required transition:

```text
DISCOVERED
    ↓
RIGHTS_UNKNOWN
    ↓
REVIEW
    ↓
┌──────────────┬───────────────┬──────────────┐
↓              ↓               ↓
AUTHORIZED   LICENSED      LEGAL REVIEW
    ↓              ↓               ↓
        APPROVED FOR USE
```

The rights engine should record:

- Source owner
- Permission
- License
- License URL/reference
- Restrictions
- Territory
- Commercial-use permission
- Date verified
- Evidence
- Human reviewer

The product should also support a **"research/demo only"** mode where the system can analyze locally available material without treating it as cleared for publishing.

---

# 15. Media Pipeline

FFmpeg should be the core media engine.

```text
Input
 ↓
Probe
 ↓
Normalize
 ↓
Transcode if needed
 ↓
Clip
 ↓
Crop/reframe
 ↓
Captions
 ↓
Graphics
 ↓
Audio normalization
 ↓
Mix
 ↓
Concat
 ↓
Final encode
 ↓
QA
```

Keep intermediate files.

Never make the final render the only artifact.

---

# 16. Rendering Presets

Initial presets:

```text
youtube_1080p
youtube_4k
youtube_shorts
vertical_1080x1920
square_1080x1080
preview_720p
```

Each preset defines:

```text
resolution
fps
video codec
audio codec
bitrate
caption style
safe zones
aspect ratio
```

---

# 17. Caption System

Captions should be generated from Whisper segments.

Features:

- Word-level timing
- Sentence grouping
- Speaker labels where available
- Highlight words
- Configurable font
- Safe-area enforcement
- Vertical layout mode

Caption output should be a separate artifact so it can be regenerated without reprocessing the entire episode.

---

# 18. Thumbnail Engine

Inputs:

```text
episode topic
selected moments
faces
visual salience
title
trend information
```

Outputs:

```text
thumbnail candidates
thumbnail score
title candidates
```

The system should generate multiple candidates rather than one "AI thumbnail."

---

# 19. Job System

The initial system does not need Redis.

Use SQLite:

```text
jobs
-----
id
type
status
priority
payload
progress
attempts
worker
created_at
started_at
completed_at
```

Worker states:

```text
QUEUED
RUNNING
PAUSED
COMPLETED
FAILED
CANCELLED
```

Every worker must be:

- Idempotent
- Restartable
- Observable
- Checkpointed

---

# 20. Artifact Strategy

Each pipeline stage creates an artifact.

```text
data/
├── raw/
├── normalized/
├── transcripts/
├── scenes/
├── moments/
├── clips/
├── storyboards/
├── audio/
├── captions/
├── thumbnails/
├── episodes/
├── renders/
└── reports/
```

Every artifact should have a database record.

---

# 21. Configuration

Example:

```yaml
discovery:
  regions:
    - US
  categories:
    - gaming
    - entertainment
    - technology
  scan_interval_minutes: 30

clipping:
  min_duration: 4
  max_duration: 90
  target_candidates_per_video: 10

episodes:
  target_duration_minutes: 20
  max_sources: 30

render:
  resolution: 1920x1080
  fps: 30
```

---

# 22. Observability

Dashboard should show:

```text
Discovery
├── videos scanned
├── trends found
├── new topics
└── API quota

Analysis
├── videos transcribed
├── clips discovered
├── processing queue
└── AI inference time

Editorial
├── episodes building
├── candidate segments
└── review queue

Rendering
├── active renders
├── completed
└── failures
```

---

# 23. Security

Local application assumptions:

- Bind FastAPI to localhost by default
- Do not expose the API publicly by default
- Store API keys in environment/configuration
- Never log secrets
- Sanitize FFmpeg arguments
- Never execute model-generated shell commands directly
- Restrict file paths to configured data directories
- Validate all uploaded/imported media
- Keep publishing credentials separate from analysis credentials

---

# 24. Testing Strategy

### Unit

- Trend scoring
- Clip scoring
- Timecode math
- Rights state transitions
- Episode ordering
- Configuration

### Integration

- YouTube API adapter
- Whisper
- Ollama
- FFmpeg
- SQLite
- Job runner

### Golden tests

Given a known source:

```text
input video
+
transcript
+
configuration
=
expected candidate clips
```

### Render tests

Verify:

- Output exists
- Duration correct
- Audio exists
- Video stream exists
- Resolution correct
- FPS correct
- Captions present
- No corrupt frames

---

# 25. MVP Definition

MVP should **not** attempt the entire autonomous media company.

MVP:

```text
1. Discover popular videos
2. Store metadata
3. Download/import permitted test material
4. Transcribe
5. Find candidate moments
6. Generate clips
7. Manually select clips
8. Assemble mega-video
9. Render
10. Review
```

Then add autonomy.

---

# 26. Phase 2

```text
Trend clustering
Automatic clip ranking
Automatic episode storyboard
Automatic captions
Automatic title generation
Automatic thumbnail generation
Review dashboard
```

---

# 27. Phase 3

```text
Autonomous editorial selection
Original narration
Topic comparison
Automated QA
Scheduled episodes
Rights workflow
Publishing integration
```

---

# 28. Future Architecture

Potential evolution:

```text
SQLite
   ↓
PostgreSQL

Local job table
   ↓
Redis / Temporal

Local files
   ↓
S3-compatible object storage

Ollama
   ↓
Hybrid local/cloud model router

Single machine
   ↓
Worker pool
```

Do not introduce these until the MVP demonstrates the need.

---

# 29. Initial Definition of Done

The first usable version is complete when:

- [ ] App launches
- [ ] API starts automatically
- [ ] YouTube discovery works
- [ ] Sources are persisted
- [ ] Trends can be viewed
- [ ] Source can be transcribed
- [ ] Candidate moments are generated
- [ ] Moments can be previewed
- [ ] User can approve moments
- [ ] Approved moments can form an episode
- [ ] Episode can render
- [ ] Render can be played in-app
- [ ] Failed jobs can be retried
- [ ] Every stage leaves inspectable artifacts
