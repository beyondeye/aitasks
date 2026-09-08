---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-07 18:14
updated_at: 2026-09-08 18:24
---

## Origin

Surfaced by t1599_4, which converted every unscoped `task_git commit` in
`.aitask-scripts/` to the path-scoped `task_git_commit_scoped` seam and added
`tests/test_no_unscoped_task_commit.sh` to keep them that way.

That guard deliberately scans **one** seam: `task_git commit`. A second seam with
the identical hazard was found during the sweep and left out of scope, because
neither file is owned by any t1599 child.

## Defect

Two sites commit through `./ait git` with no `--` pathspec, so they commit the
**entire index** — the same cross-session swallow the t1599 family exists to
close. On the shared task-data branch, whatever a concurrent session has staged
at that instant lands in a commit whose message names unrelated work.

- `.aitask-scripts/aitask_verification_followup.sh:251`
  `./ait git add "$origin_plan"` then
  `./ait git commit -m "ait: Back-reference manual-verification failure on t${origin}"`
- `.aitask-scripts/lib/verified_update_lib.sh:128`
  `./ait git add "$models_file"` then
  `run_git_quiet ./ait git commit -m "${_AIT_COMMIT_PREFIX} for ..."`

Both already stage exactly one explicit path, so both are the *latent* shape:
narrow staging, index-wide commit. Re-derive the current line numbers before
starting — t1599_4 found every number in its own task file had drifted.

## Suggested fix

Scope both commits to the path each one staged. `task_git_commit_scoped`
(`lib/task_utils.sh`) is the canonical seam for `task_git`; check whether it is
reachable from these two call sites, and if the `./ait git` route needs its own
equivalent rather than a reimplementation at each site.

Then decide — and record the decision either way — whether
`tests/test_no_unscoped_task_commit.sh` should grow a second pattern for
`./ait git commit`. Its header currently states that seam is outside its
detection scope; if the guard is extended, that paragraph must be updated in the
same change, and if it is not, the paragraph must say why not.

## Verification

- A negative control that fails against the pre-fix code, in the style of
  `tests/test_no_unscoped_task_commit.sh`'s controls: seed a foreign **staged**
  file, run the site, and assert it is absent from the resulting commit and still
  staged afterwards.
- `bash tests/test_no_unscoped_task_commit.sh` still passes.
- `bash tests/test_verification_followup.sh` and any `verified_update` suites.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-08T15:25:04Z status=pass attempt=1 type=human
