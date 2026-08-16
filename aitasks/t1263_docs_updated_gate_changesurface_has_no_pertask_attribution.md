---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [gates]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 635
created_at: 2026-07-27 09:15
updated_at: 2026-08-16 10:21
boardidx: 48128
---

## Problem

`.claude/skills/aitask-gate-docs-updated/SKILL.md:78-84` gathers the task's
change surface with:

```bash
git log -F --grep="(t<task-id>)" ...   # committed — correctly task-scoped
git diff --name-only HEAD              # uncommitted — NOT task-scoped
git ls-files --others --exclude-standard
```

The committed half is attributed by the `(t<id>)` commit tag, but the
uncommitted half returns the **entire dirty tree** with no way to tell which
files belong to this task. Procedure gates deliberately run at Step 8 *before*
the review/commit, so the uncommitted half is the primary signal — exactly the
half that cannot be attributed.

Observed live during the t635_27 verification: the gather returned four
unrelated pre-existing dirty paths (`.claude/settings.local.json`,
`.antigravitycli/`, `.opencode/package-lock.json`, `aidocs/slack/`) belonging to
other work, plus (later in the session) a concurrent session's syncer edits.
They had to be filtered by agent judgement.

## Impact

On a shared or busy checkout the gate can infer doc obligations for **another
task's** change, and propose or apply doc edits unrelated to the task being
gated. The skill has no mechanism to notice this.

## Fix direction

Options, roughly in order of preference:
1. Have the dispatch seam pass the task's known change scope (e.g. the files the
   plan touched, or a baseline commit captured at claim time) so the skill can
   intersect against it.
2. Capture a `HEAD` snapshot at Step 4 claim time and diff against that, rather
   than the whole working tree.
3. At minimum, make the skill **present the gathered surface to the user for
   confirmation** when it contains paths outside the task's plan, instead of
   silently treating the whole dirty tree as in-scope.

The SKILL.md already ignores `aitasks/`, `aiplans/`, `.aitask-data/`; that
exclusion list is not a substitute for attribution.

## Verification

Fixture with two tasks' uncommitted changes in one tree; assert the gate's
inferred doc targets derive only from the gated task's files (or that it
escalates to the user).
