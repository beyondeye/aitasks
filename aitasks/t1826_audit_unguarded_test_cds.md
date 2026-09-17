---
priority: low
risk_code_health: medium
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [trails, python]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1794
followup_kind: risk_mitigation
implemented_with: claudecode/opus5
created_at: 2026-09-17 09:44
updated_at: 2026-09-17 12:57
---

## Origin

Risk-mitigation ("after") follow-up for t1815, created at Step 8d after implementation landed.

## Risk addressed

unguarded cd in other tests can leak fixtures into the live tree (and may explain the 2026-09-02 t1_alpha.md truncation)

- The 2026-09-02 truncation of `t1_alpha.md` happened after the guards landed and remains unexplained. If some process other than this test file writes that name, deleting the files is temporary and the toast returns · severity: medium · → mitigation: audit_unguarded_test_cds
- Other test files have unguarded `cd` lines (about 435 across `tests/*.sh`). Most are harmless (`set -e`, or nothing written), but any one that writes relative paths after a failed `cd` can leak the same way · severity: low · → mitigation: audit_unguarded_test_cds

## Goal

Audit `tests/*.sh` for the leak shape t1815 found in `tests/test_data_branch_setup.sh`: a `cd` into a fixture directory with no `|| exit 1` / `|| return`, followed by relative-path writes or `git add` / `git commit` / `git push`. When that `cd` fails, the subshell keeps the caller's cwd, which is usually the live repo root. There, the writes land in the real `aitasks/` (through the symlink into `.aitask-data`) and the git commands mutate real history. t1815 has git-history proof that this happened: three `ait: Add remote task` commits appear in the main checkout's reflog on 2026-08-27.

A rough grep (`^\s*\(?\s*cd "?\$VAR` with no `||`/`&&` on the line) finds about 435 candidate lines. Most are harmless: the file runs under `set -e`, nothing is written after the `cd`, or the paths written are absolute. Triage them, and fix each real hit in one of two ways:
- guard the `cd` (`|| exit 1` inside a subshell, `|| return 1` inside a function), or
- for a file with many sites, adopt t1815's file-level backstop. That backstop sits right after the `asserts.sh` source in `tests/test_data_branch_setup.sh`. It moves the process into a `mktemp -d` scratch directory, but only after `git -C <dir> rev-parse --git-dir` fails, and it cleans up with an EXIT trap. It fails closed when `TMPDIR` or `GIT_DIR` would place the directory inside a repository.

Secondary goal: t1815 could not explain a truncation of `aitasks/t1_alpha.md` at 2026-09-02 09:09:18. By then Test 11's `cd` was already guarded, and no other file in `tests/` or `.aitask-scripts/` writes that name. If the audit finds a test (bash or Python) that writes `t1_alpha.md` or truncates arbitrary task files under the live `aitasks/`, record it, since that would identify the second leak source.

Verification bar, per file you fix: add a negative control, not only a green run. Remove the guard or force the setup step to fail, run from a throwaway sentinel git repo as cwd, and show the leak without the fix and none with it. Copies must pin `PROJECT_DIR`, because the test files locate the repo from their own path.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1823_2** id=2026-09-17T12:26:12Z.74583159c52104150ac68cf4 from=t1823_2 from_verified=yes at=2026-09-17T12:26:12Z base=ec482eaec324d282648c3db72181eff3a1fbbf8c base_branch=main dirty=yes host=omg16
>
> | Two new bash tests landed on main in ec482eaec (t1823_2), after your cwd sweep was probably generated:
> | 
> | - tests/test_skill_render_aitask_brainstorm_discuss.sh
> | - tests/test_brainstorm_discuss_skill_contract.sh
> | 
> | Every `cd` in them is `cd "$PROJECT_DIR" || exit 1` or a `$(cd … && …)` subshell. Neither calls `enter_scratch_cwd`, because tests/lib/scratch_cwd.sh was still untracked when they were committed. If test_cd_guard_lint.sh requires that call for cwd-changing tests, these two files need it added (right after PROJECT_DIR, like your edits to test_skill_render_aitask_shadow.sh). The contract test also writes only under a mktemp -d root, removed by an EXIT trap.
> | 
> | Advisory: check the files against your lint before relying on this.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-17T09:57:47Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-17T19:40:22Z status=pass attempt=1 type=human
