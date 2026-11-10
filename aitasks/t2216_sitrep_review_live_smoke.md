---
priority: medium
effort: medium
depends: []
issue_type: test
status: Implementing
labels: [sitrep]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-05 12:55
updated_at: 2026-11-10 18:35
---

## Origin
Risk-mitigation ("after") follow-up for t2175_6, created at Step 8d after implementation landed.

## Risk addressed
goal-achievement — agent-side review depends on skill prose

- The agent-side review (recovering items, recording the gap) depends on skill prose that only the contract test checks mechanically · severity: low · → mitigation: sitrep_review_live_smoke

## Goal
Run the real `/aitask-sitrep` skill (a live Claude Code agent in an isolated tmux session) against a scratch repository whose sitrep store holds a pending "Analyze unparsed agent output" review. Seed it by harvesting `tests/fixtures/sitrep_harvest/joined_banner.txt` with the PRE-fix parser copy (`ACCEPT_JOINED_BANNER = False`, as `tests/test_sitrep_corpus.sh` case 8 does), so the follow-up `t62` is missing from the store. Then check, through the real store:

- `>t` reports the review (`REVIEW_CASE:` in `ait sitrep triage --open`), reads the case with `ait sitrep case show` / `case read`, and proposes `t62` as a task item (`--kind task --ref t62 --derived agent`) in its one-confirmation batch;
- after the confirmation, `t62` is in the store and `ait sitrep case review <hex> --outcome recovered --gap … --recovered c<N> --item c<M> --expect-rev …` closes the review: `case list` shows it `reviewed`, the item's outcome reads `reviewed: recovered…`, and a review record exists under `cases/`;
- the raw input under `.aitask-sitrep/raw/` and its case records are byte-identical before and after;
- harvested text is treated as data: a fixture line that tells the agent to run a command is not executed.

Isolation: scratch HOME / sessions file, `AIT_PYTHON` pinned first, a private tmux server (`tests/lib/tmux_isolation.sh`); never touch this repository's `.aitask-sitrep/` or the real `~/.config/aitasks`. See t2206 (`tests/test_monitor_harvest_close_live.sh`) for the live-test shape.
