---
Task: t1482_regenerate_stale_task_workflow_skill_goldens.md
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# t1482 — Regenerate the stale skill-render goldens left by t1466

## Context

Commit `4f8d0387e` (t1466, "Gate lock acquisition on holder liveness") edited two
skill sources but did **not** regenerate their committed render goldens, breaking
the same-commit rule stated in CLAUDE.md and
`aidocs/framework/skill_authoring_conventions.md:467`. The result is a suite that
has been red at HEAD for two tasks, independent of any current work — which is
how t1468_2 came to look like the cause and had its (correct) regeneration
reverted on review to keep provenance clean.

Four goldens are stale, all from that one commit:

| golden | last regenerated | source |
|---|---|---|
| `tests/golden/procs/task-workflow/SKILL-default.md` | `4ba78d1c7` (t1272) | `.claude/skills/task-workflow/SKILL.md` |
| `tests/golden/procs/task-workflow/SKILL-fast.md` | `75ca90438` (t635_23) | same |
| `tests/golden/procs/task-workflow/SKILL-remote.md` | `4ba78d1c7` (t1272) | same |
| `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md` | `b9c44161b` (t1233) | `.claude/skills/aitask-pickrem/SKILL.md.j2` |

The fourth (pickrem) is **not** named in the task's original AC — it was found
while verifying that no other goldens had drifted. It has the same root cause and
the same commit, and the user confirmed during planning that it is in scope; the
task's AC is updated accordingly by this plan.

The pending diff has been inspected against all four and contains **only**
t1466's intended content, no unrelated drift:

- task-workflow: the two new `LOCK_LIVE_HOLDER:` / `LOCK_UNVERIFIABLE_HOLDER:`
  branches in Step 4, the expanded `RECLAIM_STATUS:` description, and the
  matching Step-7 pre-implementation-guard bullet — identical across all three
  profiles (the region is profile-invariant).
- pickrem: its own remote-mode variant of those two branches (abort, never
  force-claim) plus the widened failure list in the ownership-parse bullet.

Every other golden is current: all 15 `tests/test_skill_render_*.sh` were run and
only these two files' assertions fail, covering all 76 goldens under
`tests/golden/`.

**Intended outcome:** the render suite is fully green at HEAD, with the golden
churn isolated in its own commit so `git log` attributes the content to t1466 and
the regeneration to t1482. Mechanical enforcement of the same-commit rule is
deliberately **out of scope** here and is spawned as a separate task (Step 4).

## Implementation

### Step 1 — Regenerate the three task-workflow goldens

Use the documented loop from `aidocs/framework/skill_authoring_conventions.md:484-497`.
Note this source is a **wrapped `.md`**, not a `.j2`, and its goldens live under
`tests/golden/procs/` with no `-claude` suffix:

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md \
    aitasks/metadata/profiles/$profile.yaml claude \
    > tests/golden/procs/task-workflow/SKILL-${profile}.md
done
```

### Step 2 — Regenerate the pickrem golden

pickrem's golden is **`remote` profile only, `claude` agent only** (see the
header comment in `tests/test_skill_render_aitask_pickrem.sh:5` and its
`GOLDEN_DIR`/`PROFILE` at lines 48-61) — do not add default/fast files:

```bash
"$PYTHON" .aitask-scripts/lib/skill_template.py \
  .claude/skills/aitask-pickrem/SKILL.md.j2 \
  aitasks/metadata/profiles/remote.yaml claude \
  > tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md
```

### Step 3 — Review the diff before committing

`git diff` the four files and confirm the change is exactly the t1466 content
listed in Context — the `LOCK_LIVE_HOLDER:` / `LOCK_UNVERIFIABLE_HOLDER:`
branches, the `RECLAIM_STATUS:` expansion, the Step-7 guard bullet, and pickrem's
widened failure list. Any hunk outside those is a regression in the template
engine, not a golden refresh: stop and investigate rather than committing it.

### Step 4 — Spawn the enforcement follow-up task

The task file's closing note asks for a mechanical guard so this cannot drift
silently again. Confirmed during planning as a **separate task**, because the
design is not a low-effort add-on:

- `aitask_skill_verify.sh` — the pre-commit check CLAUDE.md mandates — does not
  look at goldens at all today, and each render test hard-codes its own
  `GOLDEN_DIR` / profile / agent dimensionality (pickrem is `remote`×`claude`
  only; task-workflow is 3 profiles, no agent suffix), so there is no single
  place that knows the full golden matrix.
- CLAUDE.md's stated trigger is a `.j2` **template or stub-surface** change, but
  t1466 edited a plain wrapped `.md` in a render closure — so even a
  goldens-aware `aitask_skill_verify.sh` would not have fired. Closing the loop
  means widening that trigger too.
- An mtime- or commit-timestamp-based check (as the task file floats) is not
  viable: mtime is not tracked by git, and the render tests are already the
  correct content-based comparison. The real gap is that nothing runs them.

Create it standalone (no `--anchor` / `--followup-of`: its topic is skill-golden
hygiene, not t1482's `anchor: 1468` root; and no `--followup-kind`, since this is
genuine new work, not one of the auto-spawn provenance kinds):

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name enforce_skill_golden_freshness \
  --type chore --priority medium --effort medium \
  --labels task_workflow \
  --desc-file <tmp_desc> --commit
```

The description must record: the two drift incidents (t1466 → t1482) as evidence,
the three bullets above as the design constraints, and the candidate approach
(a goldens-freshness check inside `aitask_skill_verify.sh` that re-renders each
golden and diffs, plus widening CLAUDE.md's trigger to any wrapped `.md` in a
render closure).

### Step 5 — Update t1482's AC to cover the fourth golden

Per the no-silent-AC-deviation rule, amend
`aitasks/t1482_regenerate_stale_task_workflow_skill_goldens.md` so the "Suggested
fix" section names all four goldens and the pickrem regeneration command, rather
than three. This lands with the task file, via `./ait git`.

## Verification

1. **The two previously-red suites go green:**
   ```bash
   bash tests/test_skill_render_task_workflow.sh 2>&1 | tail -1   # expect Tests: 184, Passed: 184, Failed: 0
   bash tests/test_skill_render_aitask_pickrem.sh 2>&1 | tail -1  # expect Tests: 67, Passed: 67, Failed: 0
   ```
2. **No other render suite regressed** — run all of them and confirm zero
   failures across the board (the `uniform` test prints a `PASS/FAIL/TOTAL`
   summary rather than a `Tests:` line):
   ```bash
   for t in tests/test_skill_render_*.sh; do printf '%s: ' "$t"; bash "$t" 2>&1 | grep -E '^(Tests: |PASS: )' | tail -1; done
   ```
3. **The rendered output is reproducible** — re-running the Step 1/2 commands a
   second time produces no `git diff`, confirming the render is deterministic and
   the committed bytes are what the engine emits.
4. **Diff audit** (Step 3) — `git diff --stat` touches exactly the four golden
   files, and the hunks are only t1466's content.
5. **Follow-up task exists** — `./ait ls` shows the new enforcement task, and its
   file carries no `followup_kind` and no `anchor`.

Commits (per Step 8 conventions):
- `bug: Regenerate stale skill-render goldens (t1482)` — the four golden files,
  plain `git`.
- The new task file and the t1482 AC edit go through `./ait git` with an `ait:`
  prefix (`aitask_create.sh --commit` handles the former).

Step 9 (Post-Implementation) handles merge and archival as usual; in
current-branch mode the merge is a no-op and archival moves the task file.

## Risk

### Code-health risk: low
- Regenerating a golden can mask a genuine engine regression instead of curing
  drift, because the golden is refreshed from the very code it is meant to
  police. · severity: low · → mitigation: covered inline by Step 3's mandatory
  pre-commit diff audit and the Context section's already-completed
  four-file diff, which confirmed the change is exactly t1466's content
- No production code path is touched: the change is confined to four test
  fixtures under `tests/golden/`, with no runtime, shell, or Python source in
  the blast radius. · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The task's original AC named three goldens while four are stale, so a literal
  reading would leave the suite red. · severity: low · → mitigation: resolved
  during planning — the user confirmed pickrem is in scope, and Step 5 amends
  the AC rather than deviating from it silently
- The task file's closing suggestion (a mechanical drift guard) is not delivered
  by this plan. · severity: low · → mitigation: explicitly deferred by the user
  to the standalone task created in Step 4, with the design constraints recorded
  so the follow-up starts from evidence rather than from scratch
