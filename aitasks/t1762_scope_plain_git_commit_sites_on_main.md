---
priority: medium
effort: medium
depends: [1748]
issue_type: bug
status: Implementing
labels: [git, bash_scripts, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-09 13:00
updated_at: 2026-09-10 10:30
---

## Origin

Spawned from t1748 during Step 8b review. t1748 closed the unscoped
`./ait git commit` defect at the instruction layer, on the **task-data** branch.

## Upstream defect

The same index-wide shape exists on **`main`**, through plain `git`, and t1748's
scope (`./ait git` on the task-data branch) deliberately excluded it. A
`git add <path> && git commit -m "..."` pair commits the whole main-branch index,
so a concurrent session's staged code lands in a commit whose message names
unrelated work. `main` is shared by every session on the machine exactly as
`.aitask-data` is.

Known instruction sites (re-derive before starting — t1748's line numbers went
stale within the session):

- `.claude/skills/aitask-add-model/SKILL.md` — "Seed sync (main branch)":
  `git add seed/models_<agent>.json` (+ `seed/codeagent_config.json` in promote
  mode) then a bare `git commit`.
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — the seed-file commit.
- `aidocs/framework/model_reference_locations.md` — `git add seed/models_<agent>.json`
  and `git commit -m "ait: Sync <agent>/<name> to seed template"`.
- `aidocs/issue_type_vocabulary_duplication.md` §7 — "2. `git commit` — the other
  31 files", which is index-wide by construction.
- Sweep for more; t1748's own site list was a third of the real count.

## Suggested fix

`aitask_task_commit.sh` is **not** the cure here — it refuses anything outside
`aitasks/`/`aiplans/` and commits on the data branch. Options to weigh:

1. Add `-- <paths>` to each instructed `git commit`. Minimal, no new surface,
   but leaves the `git add` shared-index hazard (an `add` of a tracked path
   replaces the entry another session staged).
2. A main-branch analogue of the t1702 seam. Larger; check first whether one
   already exists before writing a second one.

Note the asymmetry deliberately: a task/plan commit has a bounded, enumerable
path set, while a code commit often does not — `aidocs/issue_type_vocabulary_duplication.md`'s
"the other 31 files" is the hard case, and any fix must say what it does for it
rather than quietly assuming every site can name its paths.

## Guard

`tests/test_no_unscoped_task_commit.sh` deliberately does **not** match plain
`git commit` — the pattern would fire on every legitimate code commit in the
tree. Decide whether a guard is feasible at all here and record the decision
either way; "no guard, and here is why" is an acceptable outcome, as it was for
the markdown-scan question in t1748.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T07:30:09Z status=pass attempt=1 type=human
