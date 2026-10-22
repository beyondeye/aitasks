---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1733
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-21 18:58
updated_at: 2026-10-22 09:23
---

## Origin

Spawned from t1747_4 during Step 8b review. t1747_4 fixed rows A9/A9b of
`aidocs/framework/failopen_git_probes.md` in `.aitask-scripts/aitask_setup.sh`
(commit 08c0ca972). `install.sh` is the stand-alone (`curl | bash`) twin of the
same pre-install dirty-baseline machinery, cannot source the setup helpers, and
was out of scope for that sweep (`.aitask-scripts/` only).

## Upstream defect

- `install.sh:1229 — the install-side VERSION-tracked probe uses the same \`ls-files --error-unmatch … &>/dev/null\` shape (A9b), conflating "untracked" (rc 1) with a git error (rc 128) ⇒ bootstrap commit-all; out of scope for this .aitask-scripts/ sweep`

Confirmed at Step 8b: the twin is wider than that one probe. Line numbers are
as of 08c0ca972 — grep the function names.

- `install.sh::_install_list_changes` (~:1267) — the three captures
  (`ls-files --others`, `ls-files --modified`, `diff --cached --no-renames`)
  are each `2>/dev/null)" || true`, so a failed probe yields an EMPTY list.
  Consumed as the **subtrahend** in `snapshot_pre_install_dirty` (~:1310 data,
  ~:1318 main) — an empty baseline ⇒ `commit_installed_files` /
  `commit_installed_data_files` sweep another session's uncommitted work into
  the install commit — and as the **minuend** in the committers (~:1388 and the
  data twin) ⇒ a false "already committed".
- `install.sh::_install_version_tracked` (~:1228) and `_install_is_worktree`,
  combined in `_install_commit_eligible` — the snapshot's eligibility gate and
  `commit_installed_files`' own check (~:1364). rc 128 reads as "untracked" ⇒
  bootstrap ⇒ empty baseline ⇒ commit-all.

## Diagnostic context

From the t1747_4 plan (`aiplans/archived/p1747/p1747_4_setup_dirty_baseline_probe.md`
once archived) — the fix shape that landed in aitask_setup.sh, to mirror here:

- the list helper captures each probe's rc and returns 2 with **empty stdout**
  before printing (a partial list is not a smaller dirty set); the trailing
  `grep -Ev … || true` stays — it is load-bearing for a legitimately empty list;
- a tri-state VERSION probe: 0 tracked / 1 untracked (bootstrap, unchanged) /
  2 unverified (`--error-unmatch` exits 1 vs 128 — measured);
- **two independent flags**, one per baseline (main, data), each read only by
  its own committer — the data baseline is gated on the data worktree alone
  (t1972), so a main-probe failure must not refuse the data commit or vice versa;
- a failed main `rev-parse --is-inside-work-tree` is unverified **without**
  keying on a local `.git` (subdirectory installs inside an ancestor repo have
  none);
- both committers **refuse** (warn, name the manual recovery, stage nothing) on
  their flag or on their own failed list probe. Refusal is the safe direction
  here: setup/install files left uncommitted are recoverable by re-running;
  someone else's work committed under a framework message is not.

Check also whether install.sh has a `.gitignore`-style consumer of the main
baseline (setup had `_ait_gitignore_predates_setup`, which the t1747_4 task body
missed) — enumerate every reader of `AIT_INSTALL_DIRTY_BASELINE` /
`AIT_INSTALL_DATA_DIRTY_BASELINE` and give each an explicit disposition.

## Suggested fix

Port the aitask_setup.sh shape into install.sh (inline — install.sh cannot
source the setup helpers; `tests/test_install_upgrade_dirty_baseline.sh` pins the
two path lists against each other). Test the same way as
`tests/test_setup_failopen_probes.sh`: argv-keyed PATH git shim per probe,
asserted precondition (unshimmed baseline names the foreign work), probe-only
`declare -f` mutants as negative controls, a nested-install case, a data
commit-time refusal case, and a call-site scan. Prove "red before fix" by
running the new test file against a `git archive HEAD` export.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-22T06:23:09Z status=pass attempt=1 type=human
