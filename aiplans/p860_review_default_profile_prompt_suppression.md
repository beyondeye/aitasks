---
Task: t860_review_default_profile_prompt_suppression.md
Base branch: main
plan_verified: []
---

# t860 — Review default-profile prompt suppression

## Context

The `default` execution profile (`aitasks/metadata/profiles/default.yaml`)
describes itself as *"Standard interactive workflow - all questions asked
normally"*, yet it sets two keys that **suppress** up-front prompts:

- `manual_verification_followup_mode: never` — skips the Step 8c
  manual-verification follow-up offer entirely.
- `manual_verification_mode: autonomous` — skips the Manual Verification
  Step 1.5 up-front prompt and auto-runs the checklist.

These contradict the profile's own framing. This task is to decide the
intended behavior and make config + description consistent.

### Decision: remove both keys (the profile should ask everything)

The evidence is one-sided — the keys are **drift**, not intent:

1. **The seed is clean.** `seed/profiles/default.yaml` contains only `name` +
   `description`, no suppression keys. A fresh `ait setup` installs a `default`
   that asks everything. The live profile drifted away from the seed.
2. **p843 explicitly said "No change."** Its plan
   (`aiplans/archived/p843_*.md:118`) lists
   `aitasks/metadata/profiles/default.yaml` as *"No change — omitting the key
   means 'ask + approve'."* and its validation (`:466`) expected the new Step
   1.5 prompt to **fire** under the default profile (which requires the key
   absent).
3. **p859 flagged it as a pre-existing inconsistency**, not a bug it seeded:
   `aiplans/archived/p859_*.md:193-198` is the "Upstream defects identified"
   bullet that spawned this very task.
4. **Docs already match "ask everything."** The CHANGELOG (`:489`) attributes
   the skipped prompt to "fast/remote profiles" (not default); no user-facing
   doc claims `default` sets these keys.

Therefore: **remove both keys** from the live profile. The description then
becomes accurate as-is (no description edit needed), and the profile re-aligns
with the seed and with the parity test's design intent (the `default` rows are
deliberately the key-absent fixtures).

## Changes

### 1. `aitasks/metadata/profiles/default.yaml` (task data — use `./ait git`)

Delete the two suppression lines, leaving:

```yaml
name: default
description: Standard interactive workflow - all questions asked normally
```

Commit via `./ait git` (this path is a symlink onto the `aitask-data`
branch): `./ait git add aitasks/metadata/profiles/default.yaml` then
`./ait git commit -m "ait: ..."`. The `default.yaml` change is administrative
task-data, committed separately from the code/test changes below.

### 2. Regenerate the two affected goldens (code-tree — plain `git`)

Render mechanism (from `tests/test_skill_render_task_workflow.sh:75,103`):
`skill_template.py <file> <profile.yaml> claude`. Regenerate **only** these
two goldens — the per-(file,profile) command is scoped, so no other golden is
touched:

```bash
PYTHON=$(source .aitask-scripts/lib/python_resolve.sh; require_ait_python)
$PYTHON .aitask-scripts/lib/skill_template.py \
  .claude/skills/task-workflow/manual-verification.md \
  aitasks/metadata/profiles/default.yaml claude \
  > tests/golden/procs/task-workflow/manual-verification-default.md
$PYTHON .aitask-scripts/lib/skill_template.py \
  .claude/skills/task-workflow/manual-verification-followup.md \
  aitasks/metadata/profiles/default.yaml claude \
  > tests/golden/procs/task-workflow/manual-verification-followup-default.md
```

Confirmed diffs (previewed against a synthetic key-absent profile):
- `manual-verification-default.md`: the `autonomous` skip text is replaced by
  the interactive "Auto-verify" `AskUserQuestion` block (the `{% else %}` arm).
- `manual-verification-followup-default.md`: the resolved `never` text is
  replaced by the key-absent fallback prose ("If the active profile has
  `manual_verification_followup_mode` set to `"never"`… If the key is unset or
  `"ask"`… continue").

### 3. `tests/test_skill_parity_runtime_vs_rendered.sh:168` (code-tree)

The `default` row for `manual_verification_followup_mode` was corrected in
t859 to expect the resolved `never` branch. Revert it to the **key-absent
fallback** expectation, matching its sibling `default` rows (which all assert
the key-absent prose). New row:

- `PRESENT` → ``If the active profile has `manual_verification_followup_mode` set to `"never"` `` (key-absent fallback line)
- `ABSENT`  → ``Profile 'default' sets `manual_verification_followup_mode: never` `` (the regression token — must not reappear)

No `manual_verification_mode` parity row exists or needs adding; that key's
key-absent rendering is already covered by the full-golden diff (Test 1) for
`manual-verification-default.md`.

### Not changing
- `seed/profiles/default.yaml` — already clean (this change makes the live
  profile match it).
- Website docs / CHANGELOG — already consistent (describe keys generically /
  attribute suppression to fast/remote only).
- The `default` profile `description` — becomes accurate once the keys are gone.

## Isolation note (in-flight work present)

The working tree has unrelated uncommitted changes from a parallel
feature (`SKILL.md`/`planning.md` + their goldens, shortcuts/keybinding libs,
`parallel-cross-repo-planning.*`). The two goldens and the parity test I touch
are **clean** in the current tree. Stage only my specific paths — never
`git add -A` — to avoid sweeping in-flight work into my commits.

## Verification

```bash
# Parity test (not modified by in-flight work) — should pass clean:
bash tests/test_skill_parity_runtime_vs_rendered.sh

# Render test — confirm my two regenerated goldens diff clean. (Note: this
# suite also exercises the in-flight SKILL/planning/parallel-cross-repo
# goldens; focus on the manual-verification-* Test 1 lines being PASS.)
bash tests/test_skill_render_task_workflow.sh

# Sanity: default render now shows the interactive prompts
$PYTHON .aitask-scripts/lib/skill_template.py \
  .claude/skills/task-workflow/manual-verification.md \
  aitasks/metadata/profiles/default.yaml claude | grep -c "Auto-verify"   # expect >=1
```

Commit split (per CLAUDE.md): code/test files (`tests/...`) via plain `git`
with `chore: ... (t860)`; the `default.yaml` profile change via `./ait git`
with an `ait:` administrative message. Then Step 8 review → 8b/8c follow-ups →
Step 9 archival.
