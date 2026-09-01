---
priority: medium
effort: high
depends: [1561]
issue_type: feature
status: Implementing
labels: [task-workflow, verification]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1538
implemented_with: claudecode/opus5
created_at: 2026-09-01 15:18
updated_at: 2026-09-01 18:07
---

Build the premise-staleness verdict engine: the pure core `lib/task_premise.py` and the impure git-facing producer `.aitask-scripts/aitask_premise_stale.sh`.

## Context

First child of t1663 (advisory task premise staleness). Design fixed in `aidocs/framework/task_premise_staleness.md` — read it first. The core generalizes `lib/roadmap_premise.py`'s `baseline_for` + `check` so that t1655 can later swap the roadmap onto it and delete that module; the producer generalizes `.aitask-scripts/aitask_verification_stale.sh`'s shape to ordinary tasks.

## Key files

- `lib/task_premise.py` (new) — pure: no `os`/`time`/`subprocess`/I/O; add to `PURE_MODULES` in `tests/test_parallel_admission_purity.py`. Keeps `metadata_only` ≠ `unknown_history`, `SKIP` fail-open and silent, `UNKNOWN`-drives-verdict (one evidence list, verdict = emptiness test). Public surface frozen with `__all__` + a PublicSurfaceTests-style pin (model: `tests/test_roadmap_premise.py`).
- `.aitask-scripts/aitask_premise_stale.sh` (new) — verb `check <task_file>`; always exit 0 for content states, `die` on CLI misuse (precedent: `aitask_verification_stale.sh:26-32`). Emits: `BASELINE:<sha>|<ts>` or `BASELINE:NONE`; `CHECKED:<sha>` (HEAD at check time — the sha any later baseline advance must write); `FINGERPRINT:<digest>` (canonicalized tuple: baseline source+sha, scope tier, sorted scope paths, resolved origin ids); `FILES:<n>`; `CHANGED:<path>|<n_commits>|<task_ids>`; `DELETED:<path>|<culprit_task>|<subject>`; `UNKNOWN:<path>|<reason>`; `DISPLAY:...`; `DECISION:<FRESH|ASK_STALE|SKIP>`.
- Scope resolution: Tier A = `file_references:` via `get_file_references()` (`lib/task_utils.sh:1417`), ranges stripped; Tier B = origin via `lib/followup_origin.py` (quality `exact` only) → origin landed file surface. Baseline: stored `premise_baseline:` only (v1 no-go on computed baselines — see the record). `issue_type: manual_verification` tasks are out of scope for this helper's callers, but the helper itself just checks what it is given.

## Reference files for patterns

- `.aitask-scripts/aitask_verification_stale.sh` — the structural template: ordered evaluation, `:(literal)` pathspec guard, `%`-then-`|` `_enc()` encoding, committed-trees-only probes (`git cat-file -e "<rev>:<path>"`, `git log "<sha>..<rev>" -- ":(literal)<path>"`), `merge-base --is-ancestor` rewrite guard (exit 1 and 128 both → SKIP), `-C "$repo_root"` on every git call, empty-after-range-strip → `UNKNOWN:<raw>|invalid_reference`.
- `lib/roadmap_premise.py` — the pure-core template (do NOT modify it; t1655 deletes it later).
- `tests/test_verification_stale.sh` — the test shape (26 functions incl. dirty-worktree, baseline-advance, glob-chars).

## Verification (this child owns these cases; pinned outcomes)

- clean scope → `FRESH`; changed scope file → `ASK_STALE` with `CHANGED:`; deleted scope file → `ASK_STALE` with `DELETED:`; uncheckable entry → `UNKNOWN:` drives `ASK_STALE`.
- No baseline and/or no scope → silent `SKIP`; **empty scope with resolved baseline → `SKIP`, never `FRESH`**.
- Tier matrix: stored baseline × (curated scope | derived origin scope); no stored baseline → `SKIP` (the v1 no-go shape).
- **History rewrite**: baseline not an ancestor of the checked revision → `SKIP`, never an error (both exit-1 and exit-128 arms).
- **Dirty worktree**: an uncommitted edit to a scope file emits no `CHANGED:` and flips no verdict.
- **Fingerprint canonicalization**: identical inputs → identical digest; changing any tuple element (baseline sha, tier, any path, origin ids) → different digest.
- Negative controls: forced failure per scope tier (a deliberately broken input must NOT read `FRESH`).
- Purity: module import with `subprocess` poisoned + AST scan (existing purity-suite pattern).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T15:07:39Z status=pass attempt=1 type=human
