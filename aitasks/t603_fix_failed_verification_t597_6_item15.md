---
priority: medium
effort: medium
depends: [t597_6]
issue_type: bug
status: Implementing
labels: [verification, bug]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-21 07:48
updated_at: 2026-04-21 12:55
---

## Failed verification item from t597_6

> Agents & Models (per-agent, per-model, verified rankings)

### User observation

The **verified-ranking** pane renders, but the number of runs displayed is very small — this looks wrong against the current archived dataset. The per-agent and per-model panes in the same preset render normally. Investigate whether the verified-rankings data source is under-counting runs (e.g., wrong JOIN, filter, or double-counting as dedup), or whether the pane only considers a subset of tasks (e.g., manual-verification items).

### Source

- **Manual-verification task:** `aitasks/t597/t597_6_manual_verification.md` (item #15)
- **Origin feature task:** t597_6

### Commits that introduced the failing behavior

_(none detected — no commits matched (t597_6))_

### Files touched by those commits

_(none)_

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t597_6 item #15.
