---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [sitrep, crash_recovery]
created_at: 2026-11-15 11:50
updated_at: 2026-11-15 11:50
---

## Goal

Extend sitrep so it can **find crashed agents, extract what is known about each one, and keep that in the sitrep store** so the user can see the crashed work in one list and pick/resume it from there.

## Motivation

After a tmux / host crash, a repo is left with many tasks that are `status: Implementing` and still locked on the `aitask-locks` branch, with the agent process gone. On 2026-11-15 a manual survey found 17 such locks (t1555_2, t1576, t1697, t1912_2, t2199, t2216, t2264, t2284..t2287, t2289..t2293, plus one stale lock t259 on a `Ready` task). Today sitrep only harvests *finished/frozen* agents' wrap-ups; a crashed agent leaves no wrap-up, so nothing in sitrep records it. The only recovery path is re-running `/aitask-pick <id>` one task at a time and hoping the user remembers which ones were in flight.

## Scope

1. **Detection (deterministic, Part 1-style, no LLM).** A helper/verb (e.g. `aitask_sitrep_harvest.sh crashed`, or a new refresh target kind) that lists tasks where status is `Implementing` AND the lock's anchored PID is *provably* dead, reusing the existing liveness verdict from the lock code (`aitask_lock.sh --list --batch` gives `LOCK:<id>|<email>|<host>|<pid>|<starttime>|<kind>`; see `website/content/docs/workflows/crash-recovery.md` for dead / alive / unknown semantics). Must keep the rule "unknown is never rounded up to crashed". Other-host locks are reported as `LOCK_RECLAIM`-style, not as crashes. A lock with no PID anchor or a non-Implementing status is a **stale lock**, a separate category (cleanup candidate), not a crash.
2. **Extraction per crashed task.** Record, as one sitrep item per task: lock time, host, dead PID, task status, declared gates and the gate ledger state (`aitask_gate.sh status`, e.g. `plan_approved: pass`, `risk_evaluated` never run), whether a plan file exists / is approved, the `aiwork/<task>` worktree and its uncommitted-file survey (the same survey the Crash Recovery procedure prints), last commit on the task branch, and a brief description from the task file. Where a frozen/captured pane of the crashed agent still exists, retain a pointer/passage via the existing content-addressed `sources/` mechanism.
3. **Storage.** New item kind (or `kind` value) in the store, written ONLY through `aitask_sitrep_todo.sh` (mutex, CAS, backup), grouped under **Pick now** / **Waiting** as appropriate, with a Part 2 context entry that is a map, not a summary. Idempotent: re-running updates the existing item by task id; an item is retired (moved to Recently done) when the task is reclaimed, archived, or its lock released.
4. **Refresh.** `aitask_sitrep_refresh.sh` re-checks crashed items deterministically (still dead? lock released? task archived? status changed?) and the monitor maintenance tick runs the detection pass alongside `harvest all`.
5. **Pick/resume from sitrep.** The TUI's `pick` action on a crashed item must route to the real reclaim flow (`/aitask-pick <id>` -> `RECLAIM_CRASH` -> Crash Recovery procedure / `/aitask-resume` from the gate-ledger checkpoint). Sitrep stays advisory: it never reclaims, unlocks, edits task status or types into another pane on its own. Items that already have an approved plan should be ranked first ("cheapest to resume").
6. **Skill.** `/aitask-sitrep` (`.claude/skills/aitask-sitrep/SKILL.md.j2`) learns to triage crashed items: summarize situation text per theme, advise an order, and flag stale locks for cleanup. Claude Code first per CLAUDE.md; suggest separate follow-up tasks for Codex/OpenCode (see t2199).
7. **Docs.** `aidocs/framework/sitrep.md`, the website sitrep workflow / TUI reference pages and the Crash Recovery workflow page (cross-link, current-state wording only). Run `check_links.py` after editing website pages.

## Non-goals

- Automatic reclaiming, unlocking or cleaning stale locks (a separate, user-confirmed action).
- Changing the lock PID-anchor or liveness semantics.
- Inferring completion from idle/screen text.

## Open design points for the plan

- Item kind: reuse `task` items with a `crashed` marker vs. a new kind; check every consumer (TUI model, harvest receipts for `drop`/`purge`, refresh) per planning_conventions.
- Where detection lives: harvest-style pass vs. refresh target; both share the canonical-root rule (one store per repo, main worktree).
- Multi-host locks: report host, never claim a crash for a different host.
- Tests: fixture with a dead-PID lock, a live-PID lock, an unknown-liveness lock, a no-anchor stale lock and a Ready-status lock; negative controls for "unknown != crashed"; store-contract fixture update in `tests/fixtures/sitrep/`.

## Read first

`aidocs/framework/sitrep.md`, `website/content/docs/workflows/crash-recovery.md`, `.aitask-scripts/lib/sitrep_harvest.py`, `.aitask-scripts/lib/sitrep_refresh.py`, `.aitask-scripts/aitask_lock.sh` (`--list --batch`), `.aitask-scripts/aitask_gate.sh status`.
