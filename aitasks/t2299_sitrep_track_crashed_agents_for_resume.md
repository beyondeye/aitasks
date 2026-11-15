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

## Added findings: phase, plan and staleness classification (2026-11-15 survey)

A manual survey of the 17 crashed tasks showed that "crashed" alone is not enough to decide what to do next. Detection must also classify **which phase the agent died in**, **whether a plan exists**, and **whether that plan is stale**, plus how much uncommitted work survives.

### 1. Phase at crash (planning / implementing / post_impl)

Derive from the gate ledger, reusing `aitask_gate.sh resume-point` / `workflow-phase` and `board/board_workflow_phase.py` `derive_workflow_phase` (do not reimplement the ladder):

- `planning` — `Implementing`, no `plan_approved` recorded (resume point PLAN). NOTE: `status: Implementing` is set at claim time, before planning, so the status alone does not mean implementation had begun. Today 14 of 17 are in this bucket, 2 of them with a plan file (t1912_2, t2285).
- `implementing` — `plan_approved: pass`, resume point IMPLEMENT (t2284, t2286, t2290). Accepted limitation: the ledger records nothing between `plan_approved` and `review_approved`, so "barely started" and "almost done" look the same. Corroborate with the uncommitted-work survey (item 3).
- `post_impl` — `review_approved: pass` (resume point POSTIMPL), or a `needs_attended_agent` / `awaiting_review` state. None of the 17 is here today, so the detector needs a fixture that makes it reachable.
- Provenance (`ledger` / `marker` / `derived` / `unknown` / `error`) is stored with the phase; an unreadable ledger is `error`, never folded into "planning". With no ledger the phase is `unknown`, not a guess.

### 2. Plan presence and plan staleness

- **Plan exists:** the `aiplans/p<N>.md` (or `aiplans/p<parent>/p<N>_<M>_*.md`) probe; reuse `_resolve_plan_path_for_task`. Report separately whether it is **approved** (`plan_approved` pass in the ledger, or the deferred-plan marker `plan_approved_at`). Observed: 5 of 17 have a plan file, 3 of those approved.
- **Plan stale:** a plan is stale when the premise it was written against has moved. Use the existing premise machinery (`premise_baseline: <sha> @ <ts>` in frontmatter; `ait update --premise-baseline`) and the gate ledger's code-bound signature (`gate_ledger` stale-signature demotion, t1416): compare the baseline commit with HEAD for the plan's referenced files (`file_references:` / paths named in the plan). Also flag a plan whose approval is older than commits that touched those files, and an approved plan on a task whose lock is long dead (age of crash is a signal, e.g. t1555_2 locked 2026-08-18). Staleness is **advisory evidence, never a verdict**: it downgrades the resume suggestion ("re-verify the plan first") and never auto-discards a plan. When there is no baseline or no file list, report `staleness: unknown`, not `fresh`.
- Output per task: `plan: none | draft | approved` and `plan_fresh: fresh | stale:<why> | unknown`.

### 3. Surviving work

Per-task `aiwork/<task>` worktrees may not exist: in this repo (profile `fast`) every crashed task ran in the shared main checkout and none had a worktree. The survey must therefore:

- handle the worktree case AND the shared-tree case;
- in the shared tree, attribute uncommitted files to a task only by evidence (files named in the task's plan / task text, the task's own `ait:` commits), reporting source-tagged evidence and an `unattributed` bucket instead of guessing (CLAUDE.md memory: helpers report evidence, the agent judges);
- flag overlaps where two crashed tasks touch the same file (t2284 and t2286 both touch `aitask_create.sh`) so resuming one does not clobber the other's hunks;
- count commits referencing the task `(tNN)` (0 for all 17 today: only `ait:` bookkeeping commits exist);
- carry a loud "do not `git restore` / `git stash` / checkout the tree" warning on any item with uncommitted work.

### 4. Reference data: the 2026-11-15 survey (use as test fixtures / acceptance cases)

| Task | Phase | Plan | Uncommitted work |
|---|---|---|---|
| t2284 | implementing (plan_approved 2026-11-12) | approved, has unsaved edit in aitask-data | ~13 files: `aitask_create.sh` anchor walk, `gate_orchestrator.py`, tests, docs, website |
| t2286 | implementing (plan_approved 2026-11-12) | approved | ~8 files: chatlink daemon / live_check / wizard test / docs |
| t2290 | implementing (plan_approved 2026-11-13) | approved | ~12 modified + 3 untracked test-infra files (`tmpdir_guard.sh`, `run_shell_test.sh`, `test_tmpdir_guard.sh`) |
| t1912_2, t2285 | planning (no ledger) | file exists, never approved | none |
| t1555_2, t1576, t1697, t1699, t1912_2, t2199, t2216, t2264, t2287, t2289, t2291, t2292, t2293 | planning / unknown (no ledger) | none | none attributable |
| t259 | not a crash | n/a | stale lock on a `Ready` task, no PID anchor |
| t1699 | orphan | none | `Implementing` with no lock at all |

### 5. Acceptance additions

- The detector emits, per crashed task: `phase`, `phase_provenance`, `plan` (none/draft/approved), `plan_fresh`, `uncommitted_files` (attributed count + unattributed count), `overlaps`, `lock_age`.
- Suggested resume ranking: implementing-with-approved-fresh-plan and surviving work first; then approved-but-stale (re-verify plan); then plan-exists-unapproved; then planning/no-plan. `post_impl` crashes rank by what remains (review / procedure gates / archive), not by implementation.
- Tests: a ledger fixture per phase (including a reachable `post_impl`), a stale-plan fixture (baseline behind HEAD on a referenced file), a no-baseline fixture (must read `unknown`, not `fresh`), an unreadable-ledger fixture (must read `error`), a shared-tree fixture with two tasks touching one file, and negative controls for "unknown liveness is not crashed" and "unattributed is not attributed".

## Before planning: re-verify these findings

The "Added findings" section above was written on 2026-11-15 against commit af0dca45c. It is tree- and moment-relative, so **re-verify it before writing the plan** and regenerate the survey table from fresh output rather than trusting it:

1. Re-run the lock liveness check (`aitask_lock.sh --list --batch`) and `aitask_gate.sh resume-point` / `workflow-phase` per task. Crashed tasks may since have been reclaimed, archived or unlocked.
2. Re-check the uncommitted-file attribution. The `git status` it used was a snapshot; t2284, t2286 and t2290 may have committed or changed files since.
3. Re-confirm which tasks have plan files and `plan_approved` ledger entries.
4. Confirm no sibling task has built crash tracking into sitrep in the meantime.
