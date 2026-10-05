# YtPop — agents.md

> Operating contract for any agent (human or AI) working in this repo.
> Companions: `architecture.md`, `implementation-guide.md`, `roadmap.md` (§26 sprints), `worklog.md`.

## 1. Project snapshot

- Local-first desktop: Electron + React + TS + Vite → FastAPI → SQLite + jobs + `data/` artifacts.
- Pipeline: `Discover → Rank → Analyze → Moments → Rights Gate → Storyboard → Edit → Render → QA → Review`.
- Current phase: S0 baseline → S1 foundation. Do not jump to autonomy until MVP loop (S1–S9) is green.

## 2. Per-sprint ritual (mandatory)

Every sprint `S{N}` follows this exact order — no skipping:

```text
1. plan      → read roadmap §26 S{N} + arch/impl sections, list files to touch
2. scope     → confirm In scope / Out of scope; check S{N-1} exit is logged
3. implement → small vertical slices, one concern per commit
4. verify    → run tests (see §5) + manual check, paste evidence
5. worklog   → append to worklog.md under ## S{N} (Planned/Did/Verified/Next/Blockers/Commit)
6. commit    → conventional message, e.g. S1: feat(api): add health endpoints
7. push      → git push origin main (direct-to-main agreed)
```

Rules:
- Exactly one sprint `in_progress` at a time.
- Do not start `S{N+1}` if `S{N}` exit criteria fail.
- Never stack >1 unverified architectural change.
- Every commit must leave `pytest -q` (or affected subset) passing or explicitly logged as blocked.

## 3. Scoping rules

- Respect `roadmap.md` §26 Out of scope per sprint (e.g. no Redis/Postgres/K8s, no auto-publish, no arbitrary YT downloading as core flow).
- Config over code: weights/regions/intervals in `configs/*.yaml` + `pydantic-settings`, never hardcoded.
- Cheap-first: deterministic → small local LLM → medium → vision → cloud-optional. Vision/large models only for finalists.
- Rights-first: default `UNKNOWN`; never display "Fair use confirmed"; publish requires approved basis + human review.

## 4. Implementation rules

- Typed in/out per stage, persisted result, idempotent + retryable jobs, checkpointed artifacts under `data/` with DB record.
- Correlation IDs in every log: `[episode=..] [job=..] [source=..] [stage=..]`.
- FFmpeg via arg-arrays only — never shell-concat, never exec model-generated shell.
- LLM output: force structured JSON, validate with Pydantic, max 2 repair retries, then fail job clearly.
- DB: Alembic only, never manual prod schema edits. Paths restricted to configured `data/` dirs; reject traversal.
- Secrets in env/`.env` (gitignored); never log secrets; FastAPI binds localhost by default.
- Preserve word timings from Whisper; store all clip candidates (don't delete low scores — scoring will change).
- Frontend: hooks/services/stores/types separation per `architecture.md` §5; backend: routes/db/domain/workers/services separation.

## 5. Verification (tests)

Run the narrowest green check per sprint, plus full suite before tagging:

```powershell
# backend (per sprint)
pytest apps/api/tests/test_health.py -v   # S1
pytest apps/api/tests/test_db.py -v       # S2
pytest apps/api/tests/discovery/ -v       # S3
pytest apps/api/tests/test_ingestion.py -v
pytest apps/api/tests/transcription/ -v
pytest apps/api/tests/clipping/ -v        # includes golden transcript→ranges
pytest apps/api/tests/test_moments_api.py -v
pytest apps/api/tests/test_episodes.py -v
pytest apps/api/tests/rendering/ -v       # render QA asserts
pytest apps/api/tests/editorial/ -v
pytest apps/api/tests/test_trends.py -v
pytest apps/api/tests/rights/ -v
pytest apps/api/tests/test_jobs.py -v
pytest -q                                 # S14 full gate

# frontend
npm run test --workspace=apps/desktop

# migrations
alembic upgrade head; alembic downgrade -1; alembic upgrade head
```

Render QA must assert: file exists, duration>0, audio+video streams, res/fps/codec correct, captions present, no corrupt frames.
Golden test: `known input + transcript + config = expected candidate ranges ±2s`.

## 6. Worklog + commit conventions

Worklog entry template (append under `## S{N}`):

```md
## S{N} — YYYY-MM-DD — title
### Planned
### Did
### Verified (paste test output + manual proof)
### Next
### Blockers
### Commit (hash + message)
```

Commit format: `S{N}: <type>(<area>): <msg>` — types: `feat|fix|chore|docs|test|refactor`. Example: `S3: feat(discovery): add mostPopular + quota guard`.
Push: `git push origin main`. Tag MVP: `v0.1.0-mvp` after S14 Demo 1 passes.

## 7. File ownership

```text
apps/api/app/api/routes/   → endpoints, thin, validated
apps/api/app/domain/        → discovery/analysis/clipping/rights/editorial/rendering logic
apps/api/app/services/      → youtube/ollama/whisper/ffmpeg/embedding adapters
apps/api/app/workers/       → idempotent job handlers
apps/desktop/               → Electron main/preload + React pages
configs/*.yaml              → discovery/clipping/episodes/render/models weights
data/                       → gitignored artifacts (keep .gitkeep only)
tests/ + apps/api/tests/    → unit/integration/golden/render suites
docs/                       → architecture/implementation/roadmap (mirrors root during S0)
```

Do not commit: `data/database/*.db`, `data/media/*`, `data/renders/*`, `.env`, `node_modules/`, `dist/`.

## 8. Definition of Done (per sprint)

- [ ] Roadmap §26 tasks checked
- [ ] Tests listed in §5 green (or blocker logged)
- [ ] Manual proof done (screenshot/log/DB row noted)
- [ ] Artifacts inspectable + DB-linked
- [ ] Logs contain correlation IDs, no secrets
- [ ] `worklog.md` updated with evidence
- [ ] Committed + pushed (`git log --oneline -3` noted in worklog)

## 9. Do Not Build Yet

Cloud/K8s, Redis, Postgres, S3, multi-user auth, mobile, browser ext, custom ML training, auto public publishing, full auto rights decisions. See `implementation-guide.md` §34.
