# YtPop — Automatic YouTube Mega Clipper (local-first)

Local desktop pipeline: `Discover → Rank → Analyze → Moments → Rights Gate → Storyboard → Edit → Render → QA → Review`.

## Docs
- `architecture.md` — system design
- `implementation-guide.md` — build order + how-to
- `roadmap.md` — phases + §26 Sprint Plan S0–S14 (source of truth for exits)
- `agents.md` — per-sprint ritual (plan+scope+implement+verify → worklog+commit+push)
- `worklog.md` — append-only sprint log with test evidence

## Sprint workflow
See `agents.md` §2. One sprint at a time, direct to `main`:
`plan → scope → implement → verify → worklog → commit (S{N}: type(area): msg) → push`

## Quickstart (S0 baseline — app lands in S1+)
```powershell
gh auth status
git log --oneline -3
# S1+: pytest apps/api/tests/test_health.py -v
```

## Repo
Public: `YtPop`. MVP loop = S1–S9 (see `roadmap.md` §26 dependency map).
