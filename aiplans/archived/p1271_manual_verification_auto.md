---
Task: aitasks/t1271_manual_verification_gates_sync_registry_live.md
Verifies: t635_34 (reconcile installed gate registries + early "no verifier" warning)
Base branch: main
Output branch: main
Mode: manual_verification / auto-execution (autonomous)
---

# t1271 — auto-execution record

## Target selection

t635_34's own live smoke ran against a **synthetic** stale install; this task
exists to run it against a real one. Survey of the four registered downstream
projects:

| project | framework | `verifier:` keys | comment lines | verdict |
|---|---|---|---|---|
| `aitasks_go` | — | 5 | 0 | already reconciled |
| `thinking_app` | — | 5 | 0 | already reconciled |
| `thinking_backend` | — | 5 | 0 | already reconciled |
| **`aitasks_mobile`** | **0.27.0** | **0** | **0** | **genuinely stale — chosen** |

`aitasks_mobile` is the real pre-t1147 shape: no `verifier:` / `kind:` /
`signal:` keys anywhere, `aitasks/` a **directory symlink** to
`.aitask-data/aitasks`, registry tracked and clean on the `aitask-data` branch.
Its installed 0.27.0 `.aitask-scripts` has **no `sync-registry` verb at all**,
so every run below invoked this repo's 0.30.0
`.aitask-scripts/aitask_gate.sh` with `cwd` set to the downstream project —
`SCRIPT_DIR` supplies the new code + reference, `TASK_DIR` resolves to the
downstream data. That *is* the "reconcile without upgrading" path the design
claims (plan deficiency #2), exercised end to end.

**Two surfaces, by user decision:** the registry items (1/2/3/6/7) ran
**in-place** on the real install; the task-mutating items (4/5) ran on an
**isolated byte-copy**. The copy's `.aitask-data` is a *linked git worktree*, so
`cp -a` alone would have routed every git write back into the original
`.git` — both `.aitask-data/.git` and `.git/worktrees/-aitask-data/gitdir` were
re-pointed at the copy first, and isolation was verified afterwards by
confirming the copy's archive commit is absent from the original
([[project_cp_copy_leaks_worktree_commits]]).

**Seeded state, and why.** Every downstream install here has **zero** comment
lines and **zero** local customization — the old `ait upgrade --force` →
`merge_yaml` → `yaml.safe_dump` path destroyed the comments, which is precisely
the deficiency `sync-registry` exists to avoid. Items 2 and 3 would therefore
have been **vacuous** on any of them as-found. Two realistic project-author
annotations were seeded into the real registry before the apply run — a 2-line
header comment, one in-block comment, and `verifier: our-custom-build` on
`build_verified` — so both checks discriminate
([[feedback_seed_state_before_asserting_cleanup]]). They were removed
afterwards and the registry re-reconciled cleanly.

## Execution Log

### Item 1 — dry-run report matches the applying run

- Approach: CLI invocation, real install, `cmp` on captured stdout.
- Action run:
  `cd aitasks_mobile && <repo>/.aitask-scripts/aitask_gate.sh sync-registry --dry-run` then the same without `--dry-run`.
- Output (pristine real registry, before seeding):
  ```
  FILLED:risk_evaluated.verifier=aitask-gate-risk
  FILLED:build_verified.verifier=aitask-gate-build
  FILLED:build_verified.max_retries=1
  FILLED:build_verified.timeout_seconds=600
  FILLED:review_approved.signal=file-touch
  FILLED:review_approved.signal_target=".aitask-gates/<task-id>/<gate>.signed"
  FILLED:merge_approved.signal=file-touch
  FILLED:merge_approved.signal_target=".aitask-gates/<task-id>/<gate>.signed"
  NEW_GATE:tests_pass
  NEW_GATE:lint
  NEW_GATE:docs_updated
  ```
  `risk_evaluated.max_retries` is correctly **not** filled (reference value 0 ==
  parser default — the semantic-no-op filter working).
- On the seeded registry, dry-run and apply stdout were **byte-identical**
  (`cmp -s` → identical), including the `CONFLICT:` line and the post-sync
  `PROFILE_UNKNOWN` union. Dry-run left the file cksum unchanged.
- Verdict: **pass**

### Item 2 — comment preservation, byte-for-byte

- Approach: `grep '^ *#'` snapshot before/after the apply, `cmp`.
- Result: 3 project comment lines before, all 3 **byte-identical** after
  (`diff` reported `3a4,16` — additions only). The 13 added lines are the
  in-block comments carried along by the `NEW_GATE` lexical copies of
  `tests_pass` / `lint` / `docs_updated`, which is the documented behaviour.
- Contrast with the path this replaces: `ait upgrade --force`'s `yaml.safe_dump`
  is what left all four of these installs at 0 comments in the first place.
- Verdict: **pass**

### Item 3 — local customization reported, never overwritten

- Approach: seed `verifier: our-custom-build` on `build_verified`, run apply.
- Output: `CONFLICT:build_verified.verifier:our-custom-build|aitask-gate-build`
  — and `build_verified.verifier` was **absent** from the `FILLED:` list, which
  it had been on the pristine run. On disk the value stayed
  `verifier: our-custom-build`, with its adjacent comment intact, while the
  *other* keys of the same gate (`max_retries`, `timeout_seconds`) were filled
  around it.
- Verdict: **pass**

### Item 4 — archival unblocks with no manual gate append

- Approach: isolated byte-copy; real task `t33_ktor_stream_client_self_release_on_loop_exit`
  which genuinely carries `gates: [risk_evaluated]`, under the project's real
  `fast.yaml` (`default_gates: [risk_evaluated]`).
- **Before** (pristine stale registry):
  ```
  $ aitask_run_gates.sh run 33
    risk_evaluated: blocked: no verifier configured (deferred)
  $ aitask_gate.sh archive-ready 33
  BLOCKED:risk_evaluated
  ```
  This is the t1147 trap verbatim, on a real task in a real install.
- **After** `sync-registry`: the verifier is genuinely **dispatched** rather than
  deferred — the first post-reconcile run produced a real verdict
  (`fail (attempt 1)`, ledger recording ``Verifier: `aitask-gate-risk` ``)
  because the task had no plan yet. With a plan carrying `## Risk` +
  `### Code-health risk` + `### Goal-achievement risk` and the two frontmatter
  risk levels written (the artifacts the verifier checks):
  ```
  $ aitask_run_gates.sh run 33
    risk_evaluated: pass (attempt 1)
  All gates satisfied. Task ready for archive (suggest status: Done — not auto-applied).
  $ aitask_gate.sh archive-ready 33
  ALL_PASS
  $ aitask_archive.sh 33
  ARCHIVED_TASK:aitasks/archived/t33_....md
  ARCHIVED_PLAN:aiplans/archived/p33_....md
  COMMITTED:f0f0822
  ```
  **Zero `aitask_gate.sh append` calls were made.** The ledger's pass entry is
  verifier-produced (`status=pass attempt=1 type=machine`,
  ``Verifier: `aitask-gate-risk` ``), not a hand-written correction.
- The plan and the two risk levels were fabricated **in the copy only** — the
  item under test is the gate/archival machinery, not the plan's content.
- Verdict: **pass**

### Item 5 — pick-time warning appears, then disappears

- Approach: the real pick-time site, `aitask_gate.sh materialize-active 33
  --profile aitasks/metadata/profiles/fast.yaml`, in the copy.
- **Before**, stdout `MATERIALIZED:risk_evaluated`, stderr:
  ```
  Warning: materialize-active: active gate 'risk_evaluated' has no verifier
  configured in aitasks/metadata/gates.yaml — it will block archival. Run
  `ait gates sync-registry` to reconcile the registry.
  ```
- Re-running (the `NOOP:unchanged` path) **still warns** — confirming t635_34's
  deviation (a) fix, and it is the path that matters most, since a task already
  sitting blocked is re-picked, not first-materialized.
- **After** the reconcile: stdout `NOOP:unchanged`, stderr **empty**.
- t635_33's contract held throughout: stdout was exactly one status line on
  every run.
- Verdict: **pass**

### Item 6 — second run is exactly NOOP, zero bytes changed

- On the real install with the seeded conflict **resolved**: stdout was exactly
  `NOOP` (1 line, string-equal), stderr empty, cksum identical before/after.
- Independent cross-check on a **second real install** (`thinking_backend`,
  already in sync): `NOOP`, exit 0.
- **Worth recording:** with the seeded CONFLICT still unresolved, the second run
  printed the `CONFLICT:` line and *not* `NOOP`. That is correct by design —
  `NOOP` is emitted only when a completed run produced zero other report lines,
  and an unresolved conflict is a standing report line that must keep being
  surfaced. The checklist item's "exactly NOOP" implicitly assumes a
  conflict-free registry; it was verified under that condition.
- Verdict: **pass**

### Item 7 — not auto-committed, hint names `./ait git add`

- After the apply, in the downstream's `aitask-data` worktree:
  `git status --porcelain` → ` M aitasks/metadata/gates.yaml`, `HEAD` still at
  `35ae670` (unmoved). Nothing staged, nothing committed.
- stderr: `Warning: registry updated but NOT committed — review it, then:
  ./ait git add aitasks/metadata/gates.yaml`.
- The hint was correctly **suppressed** on runs that changed nothing (the `NOOP`
  run's stderr was empty) — t635_34's other recorded deviation.
- Also observed for free, on the real deployed layout: the `aitasks/` **directory
  symlink survived** the write, the target file was updated in place, and no
  stray `.tmp` file was left behind (the `realpath`-before-atomic-replace claim,
  previously only fixture-tested).
- Verdict: **pass**

## Cleanup

- Isolated copy at `<scratch>/auto_verify_1271/mobile_copy` — removed.
- Captured stdout/stderr and registry snapshots under `<scratch>/auto_verify_1271` — removed.
- `aitasks_mobile`: seeded comments and `our-custom-build` removed; the registry
  was restored to its pristine bytes and then re-reconciled cleanly, so the
  working-tree change contains **no verification artifacts** — only the genuine
  fill/new-gate reconcile. Left **uncommitted by design** (item 7): the change is
  the user's to review and commit with
  `./ait git add aitasks/metadata/gates.yaml`.
- The original repo's git history was verified untouched (the copy's archive
  commit `f0f0822` is absent from it).

## Outcome

7/7 pass. t635_34's design holds on a real, un-upgraded downstream install —
including the two behaviours its own fixtures could only approximate: the
directory-symlink deployed layout, and reconciling a project whose installed
framework does not contain the verb.
