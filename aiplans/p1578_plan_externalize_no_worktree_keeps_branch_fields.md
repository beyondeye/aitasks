---
Task: t1578_plan_externalize_no_worktree_keeps_branch_fields.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1578 — `--no-worktree` branch-field handling: correct the doc, pin the uncovered path

## Context

t1578 was spawned from t1560_1's Step 8b review as an **upstream defect**: it
reports that `aitask_plan_externalize.sh --no-worktree` "did not clear the stale
`Base branch:` / `Output branch:` frontmatter of an existing plan", contrary to
`plan-externalization.md`, which says the flag "clears any stale `Base branch:` /
`Output branch:` already present in a plan's frontmatter". It suggests the
per-field opt-in logic (`BASE_INTENT` / `OUTPUT_INTENT`) swallowed the clear path,
and that the test suite covers only the write path.

**Investigation disproved the premise.** The helper does act on both fields under
`--no-worktree` — it **overwrites them with the detected primary branch** rather
than deleting the lines. Verified by reproducing t1560_1's exact invocation in a
sandbox with stale non-primary values:

| path | source internal plan | stale header before | after `--no-worktree` |
|---|---|---|---|
| `build_header` (fresh header) | no frontmatter | `Base/Output: dev`, `Worktree: aiwork/…` | `Base/Output: main`, `Worktree:` removed |
| splice | has frontmatter | `Base/Output: dev` | `Base/Output: main` |

The observation in the task report — "the header still read `Base branch: main`" —
is an artifact of this repo's primary branch *being* `main`, which makes the
overwrite indistinguishable from a no-op.

Supporting evidence that the code is sound:

- `--no-worktree` sets `OUTPUT_INTENT=true` (`aitask_plan_externalize.sh:393`) and
  drives `BASE_INTENT=true` via `WORKTREE_MODE != true` (`:574`).
- The script's own contract already states the real behavior (`:58-59`, `:77-79`),
  as does `planning.md` ("In current-branch mode … record the detected primary
  branch in both fields, and omit `Worktree:`").
- The clear path **is** tested: `tests/test_plan_externalize.sh:506`, `:605`, and
  Test 14c's intent matrix (`:934-948`), whose `--no-worktree` row pins
  `stale → main` for *both* fields alongside genuine negative-control rows where a
  base-neutral flag leaves `Base branch: stale` untouched. Baseline: 255/255 pass.

So the defect is real but it is **documentation drift**, not a code fault:
`plan-externalization.md` says "clears", which reads as "removes the lines".
Deleting them would be a regression — Re-entry Routing treats an absent
`Base branch:` as `legacy plan, no Base branch field`, and Step 7 then raises a
user confirmation before cutting, so every resumed current-branch task would start
prompting. The user reviewed both options and chose to correct the doc.

**Outcome:** the doc states what the helper does; the one genuinely uncovered
path (the shape the reporter exercised) gets a named regression test; no behavior
changes.

## What is actually tracked (drives the commit allowlist and verification)

Rendered skill dirs are gitignored (`.gitignore:52-54`), with `!` un-ignore rules
only for the **remote** variants (`:71-73`). So `plan-externalization.md` exists in
**11 places on disk but only 4 are tracked**:

```
.claude/skills/task-workflow/plan-externalization.md              ← canonical source
.claude/skills/task-workflow-remote-/plan-externalization.md      ← tracked render
.agents/skills/task-workflow-remote-codex-/plan-externalization.md
.opencode/skills/task-workflow-remote-/plan-externalization.md
```

The six `default-` / `fast-` renders are ignored and regenerated on demand; they
still get refreshed so this workspace is consistent, but they are not committed.
`.claude/skills/task-workflow-_skillrun_416236_1779701547729-/` is a stale
ephemeral render predating the entire branch-flags section — it contains neither
the old nor the new wording, is untracked, and is excluded from all checks below.
`tests/fixtures/skills/task-workflow/plan-externalization.md.pre-rewrite` is a
frozen snapshot pinned to commit `c46366fc` for
`test_skill_parity_runtime_vs_rendered.sh` — leave it untouched; this change adds
no profile conditionals, so that test is unaffected.

## Implementation

### 1. Correct the canonical procedure doc

Edit `.claude/skills/task-workflow/plan-externalization.md` only. The rendered
copies are byte-identical to it (verified by `diff`) and are refreshed in step 3.

**Site A — the `--no-worktree` bullet (line 27).** Replace the trailing clause:

```markdown
- `--no-worktree` — when Step 5 worked on the current branch. Neither `base_branch`
  nor `output_branch` applies outside worktree mode, since nothing is cut and
  nothing is merged; both fields are therefore **overwritten with the detected
  primary branch**, so a stale value from an earlier worktree-mode run cannot
  survive for a later session to consume. The lines are **not removed** — an
  absent `Base branch:` is what Re-entry Routing reads as a legacy plan, and
  Step 7 then confirms the guessed base with the user before cutting. `Worktree:`
  is the one field this flag genuinely deletes.
```

**Site B — the "Current-branch mode **always** includes `--no-worktree`" paragraph
(line 47).** Change "it is also what clears a stale `Output branch:` left in a
plan's frontmatter by an earlier run" to "it is also what **resets** a stale
`Output branch:` left in a plan's frontmatter by an earlier run **to the detected
primary branch**".

### 2. Correct the stale code comment

`.aitask-scripts/aitask_plan_externalize.sh:823` reads "Mirrors `--no-worktree`
clearing the branches." — the same inaccuracy, and the comment that most likely
seeded it. Replace with a note that the branches are handled *differently*: they
are overwritten with the primary rather than removed, because an absent
`Base branch:` reads as a legacy plan downstream; `Worktree:` is the only field
actually deleted. Comment only — no logic change.

### 3. Re-render the rendered skill surfaces

Per-profile, one call each (the sanctioned driver; it loops `claude`, `codex`,
`opencode` internally):

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

Then `./.aitask-scripts/aitask_skill_verify.sh`.

**Commit path allowlist.** The driver refreshes every skill closure for a profile,
so `git status` may surface unrelated files. Stage only the 4 tracked doc paths
listed above plus `aitask_plan_externalize.sh` and `tests/test_plan_externalize.sh`,
via `git commit -o -- <paths>`. Any unrelated churn is pre-existing drift — report
it, do not fold it into this commit.

No separate port tasks are needed for Codex/OpenCode: their copies render from the
canonical file this change edits.

### 4. Add the missing regression test

`tests/test_plan_externalize.sh` — insert **Test 7t** after Test 7s (before
Test 8), following the file's existing `new_sandbox` / `run_externalize` idiom.
**9 new assertions.**

The gap it closes: every existing `--no-worktree` assertion seeds the stale value
in the **source internal plan's** frontmatter, exercising the *splice*. Nothing
pins the shape t1560_1 actually hit — a stale pair living in the **pre-existing
external plan**, with a **frontmatter-less** internal source, under `--force`,
which goes through `build_header` and rebuilds the file wholesale.

Stale values are **non-primary** (`dev`) on purpose: `main → main` asserts nothing,
which is precisely why the original report read the overwrite as a no-op.

```bash
# --- Test 7t: --force rebuild replaces a stale external header ---
# The t1578 shape: the stale pair lives in the EXISTING EXTERNAL plan and the
# internal source has NO frontmatter, so the header is rebuilt by build_header()
# rather than spliced. Every other --no-worktree test seeds the stale value in the
# SOURCE frontmatter and therefore only exercises the splice.
#
# The contract is REPLACEMENT with the detected primary, not deletion: only
# `Worktree:` is actually removed. The final block characterizes the asymmetry the
# corrected doc states -- on this path build_header() writes both fields
# unconditionally, so the per-field intent gating never applies and a bare --force
# replaces them just as thoroughly. It is expected to pass with the same value;
# the real negative controls for intent gating live in Test 14c.
echo "--- Test 7t: --force rebuild replaces a stale external header ---"
TMPDIR7T=$(new_sandbox)
mkdir -p "$TMPDIR7T/prof"
printf 'name: fast\ncreate_worktree: false\n' > "$TMPDIR7T/prof/fast.yaml"
write_stale_external_7t() {
    cat > "$TMPDIR7T/aiplans/p999_sandbox_task.md" <<'EOF'
---
Task: t999_sandbox_task.md
Worktree: aiwork/t999_sandbox_task
Base branch: dev
Output branch: dev
---

# old body
EOF
}
write_stale_external_7t
make_fresh_internal "$TMPDIR7T/fakehome/.claude/plans/one-recent.md"
result=$(run_externalize "$TMPDIR7T" "$TMPDIR7T/fakehome/.claude/plans" 999 --force \
    --profile "$TMPDIR7T/prof/fast.yaml" --no-worktree)
plan="$TMPDIR7T/aiplans/p999_sandbox_task.md"
assert_contains "7t: existing external plan is OVERWRITTEN" "OVERWRITTEN:" "$result"
assert_eq "7t: stale base replaced by the primary" "Base branch: main" \
    "$(grep '^Base branch:' "$plan" || true)"
assert_eq "7t: stale output replaced by the primary" "Output branch: main" \
    "$(grep '^Output branch:' "$plan" || true)"
assert_eq "7t: stale Worktree line removed" "0" \
    "$(grep -c '^Worktree:' "$plan" || true)"
assert_eq "7t: exactly one base line" "1" "$(grep -c '^Base branch:' "$plan" || true)"
assert_eq "7t: exactly one output line" "1" "$(grep -c '^Output branch:' "$plan" || true)"
assert_eq "7t: frontmatter block intact" "2" "$(grep -c '^---$' "$plan" || true)"

write_stale_external_7t
run_externalize "$TMPDIR7T" "$TMPDIR7T/fakehome/.claude/plans" 999 --force >/dev/null 2>&1
assert_eq "7t: bare --force rebuild also replaces the stale base" "Base branch: main" \
    "$(grep '^Base branch:' "$plan" || true)"
assert_eq "7t: bare --force rebuild also replaces the stale output" "Output branch: main" \
    "$(grep '^Output branch:' "$plan" || true)"
rm -rf "$TMPDIR7T"
```

## Verification

1. **Test suite** — `bash tests/test_plan_externalize.sh`; expect 255 existing +
   9 new = **264 passed, 0 failed**.

2. **Prove the new assertions are reachable and live — scoped to Test 7t.**
   `assert_eq` records and continues rather than aborting, so a mutation in the
   production script would fail dozens of earlier assertions and prove nothing
   specific about 7t. Instead mutate **only Test 7t's expectations**: change its
   two branch expectations from `Base branch: main` / `Output branch: main` to
   `dev`, re-run, and confirm the result is exactly **2 failed**, named
   `7t: stale base replaced by the primary` and
   `7t: stale output replaced by the primary`, with every other assertion still
   passing. That proves the block executes and both assertions compare live
   output — so any actual value other than the primary would fail them. Restore
   the expectations immediately and re-run to 264/0.

3. **Lint** — `shellcheck .aitask-scripts/aitask_plan_externalize.sh`.

4. **Render integrity** — `./.aitask-scripts/aitask_skill_verify.sh`, then check
   propagation over **tracked files only** (stable; excludes the ignored transient
   `_skillrun_` dir and the `.pre-rewrite` fixture, which the exact basename
   pattern does not match):

   ```bash
   git ls-files -- '*plan-externalization.md' | wc -l                  # expect 4
   git ls-files -- '*plan-externalization.md' \
     | xargs grep -L 'overwritten with the detected primary branch'    # expect no output
   git ls-files -- '*plan-externalization.md' \
     | xargs grep -l 'clears any stale'                                # expect no output
   ```

   Then confirm the ignored `default-` / `fast-` renders were refreshed too:
   ```bash
   grep -L 'overwritten with the detected primary branch' \
     .claude/skills/task-workflow-{default,fast}-/plan-externalization.md \
     .agents/skills/task-workflow-{default,fast}-codex-/plan-externalization.md \
     .opencode/skills/task-workflow-{default,fast}-/plan-externalization.md  # expect no output
   ```

5. **Live behavioral check** — re-run the sandbox repro from the Context table and
   confirm `dev` → `main` on both fields with `Worktree:` removed, matching the
   corrected wording. This is the behavioral evidence that step 2's expectation
   flip deliberately does not attempt to provide.

6. **Commit hygiene** — `git status` before staging; `git commit -o --` against the
   explicit path list from step 3 only.

## Risk

### Code-health risk: low
- The only executable-file edit is a comment; behavior is unchanged and the
  existing 255 assertions act as the regression net. · severity: low · → mitigation: none needed
- The re-render driver sweeps every skill closure per profile, so unrelated stale
  renders could appear in `git status`. Already handled by the path-scoped
  `git commit -o --` step, which CLAUDE.md requires for this repo anyway.
  · severity: low · → mitigation: inline, plan step 3

### Goal-achievement risk: low
- The deliverable inverts the task's stated fix (doc, not code). The user was
  shown the evidence and both options and explicitly chose this direction, so the
  goal is the corrected one. · severity: low · → mitigation: none needed
- Residual: the conclusion rests on the empirical repro. Both header paths
  (`build_header` and the splice) and the intent-gating derivation were checked
  directly, so a third path where `--no-worktree` genuinely leaves a stale value
  would have to be outside this helper. · severity: low · → mitigation: none needed

## Step 9 (Post-Implementation)

Current-branch mode — nothing is cut and nothing is merged, so Step 9's merge
block does not run. Archive t1578 and its plan normally.
