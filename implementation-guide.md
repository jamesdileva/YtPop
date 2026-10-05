# Automatic YouTube Mega Clipper — Implementation Guide

**Status:** Baseline / v0.1  
**Companion:** `architecture.md`

---

# 1. Implementation Philosophy

Build the system as a sequence of boring, testable pipelines before attempting full autonomy.

The correct progression is:

```text
Manual control
    ↓
Automated individual stages
    ↓
Automated pipeline
    ↓
AI-assisted decisions
    ↓
AI-controlled editorial pipeline
    ↓
24/7 autonomous operation
```

Do not begin with the autonomous version.

---

# 2. Development Environment

Recommended:

```text
Windows 11
Node.js LTS
Python 3.12/3.13
FFmpeg
Git
Ollama
VS Code
```

Install:

```text
Node
Python
FFmpeg
Ollama
```

Python dependencies should eventually include:

```text
fastapi
uvicorn
sqlalchemy
pydantic
pydantic-settings
alembic
httpx
pytest
structlog
numpy
opencv-python
pyscenedetect
faster-whisper
sentence-transformers
```

Frontend:

```text
react
react-dom
react-router
typescript
vite
zustand
```

---

# 3. Bootstrap the Repository

Create:

```text
youtube-mega-clipper/
```

Initialize:

```text
git init
```

Create:

```text
apps/
packages/
data/
configs/
docs/
scripts/
tests/
```

Start with one application and expand only when boundaries become real.

---

# 4. Build Order

Use this order:

```text
Sprint 1  Foundation
Sprint 2  Database
Sprint 3  YouTube Discovery
Sprint 4  Media Ingestion
Sprint 5  Transcription
Sprint 6  Clip Detection
Sprint 7  Clip Review UI
Sprint 8  Episode Builder
Sprint 9  Rendering
Sprint 10 Editorial AI
Sprint 11 Trend Intelligence
Sprint 12 Rights Workflow
Sprint 13 Automation
Sprint 14 QA / Packaging
```

---

# 5. Sprint 1 — Foundation

## Goal

Get Electron + React + FastAPI communicating.

### Backend

Create:

```text
apps/api/app/main.py
```

Endpoints:

```http
GET /api/v1/health
GET /api/v1/health/dependencies
```

Response:

```json
{
  "status": "ok",
  "version": "0.1.0"
}
```

### Electron

Electron launches:

```text
FastAPI
React
```

Development flow:

```text
Electron
 ├── starts FastAPI
 └── opens Vite frontend
```

Eventually:

```text
Electron
 ├── starts packaged backend
 └── serves packaged frontend
```

### Verification

- App opens
- Backend responds
- Frontend displays backend status

---

# 6. Sprint 2 — Database

Create SQLite database:

```text
data/database/mega_clipper.db
```

Create SQLAlchemy models.

First tables:

```text
sources
trend_events
trend_sources
transcripts
moments
episodes
episode_segments
jobs
rights_records
renders
```

Use Alembic from the beginning.

Do not manually modify the production schema.

### Verification

- Database initializes
- Migration succeeds
- Tables exist
- API can create/read a test source

---

# 7. Sprint 3 — YouTube Discovery

Implement:

```text
YouTubeService
```

Responsibilities:

```text
get_most_popular()
get_video()
get_channel()
search_videos()
get_categories()
```

The official Data API supports `videos.list` with `chart=mostPopular`, including region/category filtering. citeturn0search4

Store a snapshot every time metadata is retrieved.

Example:

```text
source
   │
   ├── snapshot 10:00
   ├── snapshot 10:30
   ├── snapshot 11:00
   └── snapshot 11:30
```

This allows velocity calculations.

### Do not

- Hammer the API
- Re-fetch unchanged metadata unnecessarily
- Assume "most popular" means "fastest trending"

API quota must be treated as a finite resource. citeturn0search12

---

# 8. Sprint 4 — Media Ingestion

For development, use:

```text
USER_OWNED
LICENSED
CREATIVE_COMMONS
PUBLIC_DOMAIN
```

or other material for which the project has a legitimate basis to process.

Do not make arbitrary downloading of YouTube videos the core ingestion mechanism.

Create:

```text
MediaIngestionService
```

Responsibilities:

```text
probe()
normalize()
extract_audio()
extract_thumbnail()
verify_media()
```

FFmpeg commands should be constructed by code rather than concatenated shell strings.

---

# 9. Sprint 5 — Transcription

Use:

```text
faster-whisper
```

Pipeline:

```text
media
 ↓
audio extraction
 ↓
Whisper
 ↓
segments
 ↓
database
 ↓
transcript.json
```

Store:

```json
{
  "language": "en",
  "segments": [
    {
      "start": 10.3,
      "end": 14.9,
      "text": "..."
    }
  ]
}
```

Do not throw away word timing if available.

It will be useful later for:

- Captions
- Clip boundaries
- Highlight words
- Search
- Speaker timing

---

# 10. Sprint 6 — Clip Detection

Start without a vision model.

Use:

```text
transcript
+
sentence boundaries
+
keyword scoring
+
semantic similarity
```

Candidate generation:

```text
5–90 second windows
```

Score:

```text
hook
relevance
novelty
emotion
payoff
context completeness
```

Store all candidates.

Do not immediately delete low-scoring candidates.

The scoring algorithm will change repeatedly.

---

# 11. Sprint 7 — Clip Review UI

Build a review page.

Layout:

```text
┌───────────────────────────────────────────────────────────┐
│ Source                                                   │
├──────────────────────┬────────────────────────────────────┤
│ Video Preview        │ Candidate Information              │
│                      │                                    │
│                      │ Score: 87                          │
│                      │ Hook: 92                           │
│                      │ Novelty: 84                        │
│                      │ Context: 78                        │
├──────────────────────┴────────────────────────────────────┤
│ [Reject] [Trim] [Approve]                                │
└───────────────────────────────────────────────────────────┘
```

The user should be able to:

- Preview
- Change start
- Change end
- Approve
- Reject
- Add notes
- Assign category
- Mark "best"

This interface becomes the training data collection point later.

---

# 12. Sprint 8 — Episode Builder

Create:

```text
Episode
EpisodeSegment
```

The first version should be manual.

Drag:

```text
Clip A
Clip B
Clip C
Clip D
```

into:

```text
Episode Timeline
```

Support:

- Reordering
- Trim
- Delete
- Duplicate
- Preview
- Intro/outro
- Title card

Do not implement AI storytelling yet.

---

# 13. Sprint 9 — Rendering

Build:

```text
RenderService
```

Input:

```json
{
  "episode_id": 1,
  "preset": "youtube_1080p"
}
```

Pipeline:

```text
episode
 ↓
generate ffmpeg filter graph
 ↓
render
 ↓
probe output
 ↓
QA
 ↓
render record
```

QA must verify:

```text
video exists
audio exists
duration > 0
resolution correct
codec correct
no obvious encode failure
```

---

# 14. Sprint 10 — Editorial AI

Now introduce Ollama.

Create:

```text
EditorialService
```

Prompt the model with structured data, not giant raw transcripts.

Example input:

```json
{
  "trend": "...",
  "sources": [],
  "candidate_moments": [],
  "target_duration": 1200,
  "format": "daily_highlights"
}
```

Request:

```text
Generate:
1. opening hook
2. story clusters
3. segment order
4. transitions
5. context requirements
6. ending
```

Force structured JSON output.

Validate with Pydantic.

Never trust raw model output.

---

# 15. Sprint 11 — Trend Intelligence

Build topic clustering.

Pipeline:

```text
sources
 ↓
embeddings
 ↓
similarity
 ↓
clusters
 ↓
topic summaries
 ↓
trend events
```

Example:

```text
Videos:

A: "Major game update announced"
B: "Developers reveal new update"
C: "Players react to update"
D: "Streamer tests update"

            ↓

Topic:

"Game X Update"

            ↓

Trend Score: 91
```

This is more powerful than simply sorting videos by views.

---

# 16. Sprint 12 — Rights Workflow

Implement before serious publishing automation.

Every source starts:

```text
UNKNOWN
```

The system must require a valid state before an episode can enter:

```text
READY_TO_PUBLISH
```

Example:

```text
UNKNOWN
 ↓
REVIEW_REQUIRED
 ↓
APPROVED
```

or:

```text
UNKNOWN
 ↓
REJECTED
```

Store evidence.

YouTube notes that copyright owners generally control use/distribution of original videos, while permitted routes can include authorization, applicable copyright exceptions, Creative Commons, or public domain; none is an automatic guarantee against claims. citeturn0search2

The system should therefore never display:

> "Fair use confirmed."

It should display:

> "Rights basis: human review required."

---

# 17. Sprint 13 — Automation

Once every individual component works:

Create:

```text
PipelineOrchestrator
```

Example:

```text
06:00
 ↓
discover
 ↓
cluster
 ↓
rank
 ↓
analyze
 ↓
generate candidates
 ↓
rights filter
 ↓
editorial plan
 ↓
render preview
 ↓
QA
 ↓
review
```

Each stage produces a job.

---

# 18. Job Orchestration

Example:

```python
job = {
    "type": "GENERATE_CLIPS",
    "payload": {
        "source_id": 123
    }
}
```

Worker:

```text
claim job
 ↓
mark RUNNING
 ↓
execute
 ↓
write artifacts
 ↓
update DB
 ↓
mark COMPLETE
```

Failure:

```text
RUNNING
 ↓
FAILED
 ↓
retry
```

Use exponential backoff.

---

# 19. AI Model Router

Create:

```text
ModelRouter
```

Example:

```text
classification → small model
summarization → small/medium
story planning → medium
visual analysis → vision model
complex editorial decision → strongest available model
```

The application should not hard-code one model everywhere.

Configuration:

```yaml
models:
  classifier: qwen-small
  summarizer: qwen-medium
  editor: qwen-medium
  vision: vision-model
```

---

# 20. Clip Scoring Evolution

### V1

```text
keywords
```

### V2

```text
embeddings
```

### V3

```text
LLM scoring
```

### V4

```text
LLM + vision + historical performance
```

### V5

```text
learned ranking model
```

Eventually the user's approval/rejection behavior becomes training data.

---

# 21. Feedback Loop

Every review action should be stored.

```text
candidate
 ↓
user approves
 ↓
feedback = positive
```

or:

```text
candidate
 ↓
user rejects
 ↓
feedback = negative
```

Store:

```text
moment_id
decision
reason
timestamp
user_adjusted_start
user_adjusted_end
```

This eventually enables:

```text
AI proposes
 ↓
human corrects
 ↓
system learns
 ↓
AI improves
```

---

# 22. Vision Analysis

Add vision only after transcript scoring works.

Analyze sampled frames:

```text
every 1–3 seconds
```

Detect:

- Major scene changes
- Faces
- Screens
- Text
- Reactions
- Explosions/events
- Gameplay moments
- Visual punchlines
- Camera changes

Avoid sending every frame to a large model.

Use a cheap detector first.

---

# 23. Narrative Assembly

The editorial engine should optimize for:

```text
HOOK
 ↓
CONTEXT
 ↓
ESCALATION
 ↓
VARIATION
 ↓
PAYOFF
 ↓
CLOSING
```

Avoid:

```text
clip
clip
clip
clip
clip
```

Instead:

```text
Topic A
 ├── setup
 ├── first reaction
 └── strongest moment

Topic B
 ├── context
 └── escalation

Topic C
 ├── comparison
 └── payoff
```

---

# 24. Audio Pipeline

Normalize source audio.

Support:

```text
dialogue
music
SFX
narration
ambient
```

Mix:

```text
voice
 ↓
duck music
 ↓
normalize
 ↓
limiter
```

The exact loudness target should be configurable rather than hard-coded.

---

# 25. Captions

Pipeline:

```text
Whisper
 ↓
word timings
 ↓
caption formatter
 ↓
ASS/WebVTT
 ↓
FFmpeg
```

Provide:

```text
standard
bold
highlight
vertical
minimal
```

as styles.

---

# 26. Episode Templates

Do not hard-code one show.

Create:

```text
templates/
├── daily_highlights
├── weekly_recap
├── gaming
├── tech
├── viral
└── shorts
```

Template controls:

```text
target duration
intro
outro
segment count
caption style
transition style
narration style
```

---

# 27. Testing

Every service should have tests.

Example:

```text
tests/
├── discovery/
├── scoring/
├── transcription/
├── clipping/
├── editorial/
├── rendering/
├── rights/
└── api/
```

Critical golden test:

```text
known input
→ known transcript
→ candidate extraction
→ expected candidate ranges
```

---

# 28. Debugging

Every pipeline execution should have a correlation ID.

Example:

```text
episode: 81
job: 1842
source: youtube:abc123
```

Logs:

```text
[episode=81]
[stage=editorial]
[model=local-medium]
```

This makes failures traceable.

---

# 29. Performance Strategy

The expensive operations are:

```text
transcription
vision inference
LLM inference
video rendering
```

Optimize in that order.

Use:

```text
metadata filters
 ↓
cheap scoring
 ↓
transcript
 ↓
semantic scoring
 ↓
vision only for finalists
 ↓
large model only for finalists
```

Never process everything with the largest model.

---

# 30. Local Hardware Strategy

For a modest PC:

```text
CPU
 ├── API
 ├── SQLite
 ├── FFmpeg
 └── background jobs

GPU
 └── Ollama / Whisper / vision
```

Limit concurrency.

Example:

```yaml
workers:
  transcription: 1
  vision: 1
  editorial: 1
  render: 1
```

Increase only after measuring.

---

# 31. First End-to-End Demo

The first major milestone should be:

```text
User starts app
 ↓
Click "Discover"
 ↓
System finds popular videos
 ↓
User selects one permitted source
 ↓
Transcription runs
 ↓
AI finds 5 moments
 ↓
User approves 3
 ↓
Episode Builder creates episode
 ↓
Render
 ↓
Play finished mega-video
```

Do not proceed to full automation until this works reliably.

---

# 32. Second End-to-End Demo

Then:

```text
Discover
 ↓
Automatically cluster trends
 ↓
Automatically analyze 20 sources
 ↓
Automatically produce 50 candidate clips
 ↓
User approves 15
 ↓
AI assembles episode
 ↓
Render
```

---

# 33. Third End-to-End Demo

Finally:

```text
Scheduled run
 ↓
Trend discovery
 ↓
Trend clustering
 ↓
Clip discovery
 ↓
Rights filtering
 ↓
Editorial planning
 ↓
Narration/context
 ↓
Rendering
 ↓
QA
 ↓
Human approval queue
```

That is the first version that feels like an autonomous media engine.

---

# 34. Do Not Build Yet

Avoid initially:

- Cloud infrastructure
- Kubernetes
- Redis
- PostgreSQL
- Multi-user authentication
- Mobile app
- Browser extension
- Complex recommendation algorithms
- Custom ML training
- Automatic public publishing
- Full autonomous rights decisions

Build the core loop first.

---

# 35. First Coding Task

The first implementation task should be:

```text
Create repository
 ↓
Electron
 ↓
React
 ↓
FastAPI
 ↓
SQLite
 ↓
Health endpoint
 ↓
Database migration
 ↓
Basic dashboard
```

Only after that should YouTube discovery be added.

---

# 36. Implementation Rule

For every feature:

```text
Implement
 ↓
Run
 ↓
Verify
 ↓
Document
 ↓
Commit
 ↓
Move forward
```

Do not stack five unverified architectural changes together.

---

# 37. Definition of Production-Ready Pipeline

A pipeline stage is production-ready when:

- It has a typed input
- It has a typed output
- It persists its result
- It is idempotent
- It can fail safely
- It can be retried
- It logs useful information
- It has tests
- Its artifacts are inspectable
- It does not silently discard failures
