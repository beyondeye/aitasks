---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: high
depends: [1561, 1673]
issue_type: feature
status: Implementing
labels: [task-workflow, verification]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1673]
assigned_to: dario-e@beyond-eye.com
anchor: 1538
implemented_with: claudecode/opus5
created_at: 2026-09-01 15:18
updated_at: 2026-11-04 18:03
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1981** id=2026-11-04T15:00:10Z.bdd0bfd934fe2276bc8c211d from=t1981 at=2026-11-04T15:00:10Z base=c0a6bbd4015d48cca47bfd7b1deba187cfb4c66f base_branch=main dirty=yes host=omg16
>
> | From t1981's session (task relations and obsolescence). Advisory: a relevance and plan-coherence check the user asked for. Nothing here is a decision; re-verify it at pick time.
> | 
> | THE USER'S CONCERN
> | t1663 was planned on 2026-09-01. Is it still relevant, and is its plan still coherent with the code and with the implementation trail art:trail-task-relations-and-premise? That trail was refreshed on 2026-11-04 (deep, version sha256:304b689b) after t1981 decomposed into ten children.
> | 
> | WHAT A READ-ONLY CHECK FOUND
> | Code main at 5026118e2, 2026-11-04. Commit counts are relative to that tree. The inbox readings are moment-relative and may already be stale.
> | 
> | 1. The goal is still unmet, and another task now consumes it.
> |    - lib/task_premise.py and aitask_premise_stale.sh do not exist.
> |    - lib/roadmap_premise.py, the temporary stand-in, still exists.
> |    - t1981's committed design (aidocs/framework/task_relations.md, D9) consumes `aitask_premise_stale.sh check` as one evidence row in its obsolescence layer (t1981_6), shown as "unavailable" until this task lands. The boundary is unchanged: t1663 owns "needs refresh", and t1981 owns "still worth doing".
> |    - If this task changes the producer's output protocol (the DECISION/verdict lines), please note t1981_6.
> | 2. Your plan has never been verified.
> |    - p1663_1 was last committed on 2026-09-01. `aitask_plan_verified.sh decide` reports TOTAL:0 and DECISION:VERIFY, so the fast profile enters verify mode at pick.
> |    - The decision record aidocs/framework/task_premise_staleness.md was corrected by t1673 on 2026-09-02 (594c5875b: "Correct the Tier-B reachability and eligibility claims"). That is after your plan's last commit, so verify the plan against the corrected record.
> |    - `aitask_risk_mitigation_landed.sh` reports FORCE_VERIFY:0, so the automatic risk-mitigation re-verify will not point you at t1673. Read it deliberately.
> | 3. Your own inputs have not moved. roadmap_premise.py, followup_origin.py, tests/test_roadmap_premise.py and aitask_verification_stale.sh have no commits since 2026-09-01.
> | 4. Surfaces of later siblings have moved since 2026-09-01. Siblings plan from current code when picked, so this matters less for you, but it shapes the chain:
> |    - .claude/skills/task-workflow/SKILL.md (9 commits) and planning.md (4), for t1663_4;
> |    - aitask_create.sh (5), aitask_update.sh (4) and board/aitask_merge.py (3, now sharing the ## Inbox schema), for t1663_2 and t1663_3;
> |    - board/aitask_board.py (28; the board was split into a package of board_* modules).
> | 5. Unread notes on siblings, as of this writing:
> |    - t1663_2, from t1794_9 (the board split);
> |    - t1663_4, from t1981 (Step 3 Check 6 is already the Inbox check, and t1981_5 adds a related-work check after it);
> |    - t1663_5, from t1687.
> | 6. Stale prose. The t1663 parent body still says creation-time seeding uses --followup-of. t1673 and t1663_3 corrected that (seeding happens on --file-ref / --verifies only).
> | 7. Trail coherence. The trail's drift check sees only structure (status, depends, new tasks, plan hashes), and its t1663 rationales were carried over without being re-read. These are the claims about this chain to confirm or correct:
> |    - t1663_1 touches only new files and shares no edit surface (wave 1, beside t1981_1);
> |    - t1663_3 should land before t1981_4 (both edit aitask_create.sh's batch-commit sites);
> |    - t1663_4 should land before t1981_5 (both add a Step 3 check);
> |    - t1655 depends on the t1663 parent but needs only this task's engine. Narrowing that edge is the user's call.
> | 
> | SUGGESTED SEQUENCE (advisory)
> | Pick t1663_1. Let verify mode re-check p1663_1 against the current tree and the corrected decision record. Then refresh the trail with `/aitask-trail --refresh art:trail-task-relations-and-premise --deep`; the changed plan hash shows as drift and gets re-read.

> **👁 note:read** id=2026-11-04T16:03:32Z.303ed59467e929d9a1cd18ab by=t1663_1 at=2026-11-04T16:03:32Z mode=explicit ids=2026-11-04T15:00:10Z.bdd0bfd934fe2276bc8c211d

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-01T15:07:39Z status=pass attempt=1 type=human
