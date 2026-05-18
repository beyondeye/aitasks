---
Task: t786_minijinja_comments.md
Base branch: main
plan_verified: []
---

# t786 — Jinja block-comment conventions for profile-aware skill templates

## Context

The t777 family is replacing runtime "profile check" branches in skills with
minijinja templating that bakes profile values into per-profile rendered
snapshots. The first batch (t777_7, completed) wrapped 5 shared procedure files
in `.claude/skills/task-workflown/` with `{% if/elif/else/endif %}` blocks.

In practice these blocks are hard to scan: nested conditionals lose their
boundaries visually, `{% else %}` doesn't say which branch it covers, and
`{% endif %}` doesn't say which `{% if %}` it closes. Authors reading or
editing the file (or templated skills landing in t777_6, t777_8..15) cannot tell
at a glance where templated regions begin and end.

This task adds an aidocs-documented commenting convention, applies it
retroactively to the 5 wrapped files, ensures remaining t777 template-writing
siblings reference it, and re-runs golden tests to prove no semantic drift.

## Approach

### Convention to document

Use minijinja jinja-comment blocks (`{# ... #}`) with whitespace-control on the
**separator** so it does not change rendered bytes beyond what `{% if %}` already
produces. Three markers per conditional, sharing a short `<label>` so they pair
visually:

1. **Separator before `{% if %}`** — own line, with `-` whitespace stripping so
   it leaves no rendered trace:
   ```
   {#- ---------- <label> ---------- -#}
   {% if profile.foo is defined %}
   ```
2. **Inline comment on `{% elif %}` / `{% else %}`** — same line, plain comment
   (no `-` stripping needed since it lives where the tag already is):
   ```
   {% else %}{# ---------- <label>: <when this branch fires> ---------- #}
   ```
3. **Inline comment on `{% endif %}`** — same line, matching label:
   ```
   {% endif %}{# ---------- end <label> ---------- #}
   ```

`<label>` is a short slug describing the conditional — usually the profile key
under test, e.g. `default_email`, `create_worktree`, `plan_preference`,
`enableFeedbackQuestions`. For nested ifs each level gets its own label.

The shared `----------` dashes give a uniform visual ruler so `grep -n '\---'`
or eyeballing the file reveals every templated region in seconds.

### Files to change

**New / extended doc:**
- `aidocs/skill_authoring_conventions.md` — add `## Jinja comment conventions
  for profile-aware templates` section with the rules and one full nested
  example. Slot it after the existing `## Profile-aware skills require a stub
  + .md.j2 pair` section.

**Apply retroactively (5 files):**
- `.claude/skills/task-workflown/SKILL.md` — 3 conditionals (`default_email`
  with nested branches @ L98–114, `create_worktree` @ L195–208, `base_branch`
  @ L216–227)
- `.claude/skills/task-workflown/planning.md` — 4 conditionals
  (`plan_preference`/`plan_preference_child` @ L29–120 with nested branches,
  plus 3 more in the checkpoint region)
- `.claude/skills/task-workflown/manual-verification-followup.md` —
  1 conditional (`manual_verification_followup_mode` with nested branch)
- `.claude/skills/task-workflown/remote-drift-check.md` —
  1 conditional (`remote_drift_check`)
- `.claude/skills/task-workflown/satisfaction-feedback.md` —
  2 conditionals (`enableFeedbackQuestions` with nested, plus one more)

**Inform pending t777 siblings (9 task files):**
Add a short `## Jinja Comment Conventions` paragraph to each pending
template-writing sibling's description, pointing to the new aidocs section:
- `aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md`
- `aitasks/t777/t777_8_convert_aitask_explore.md`
- `aitasks/t777/t777_9_convert_aitask_review.md`
- `aitasks/t777/t777_10_convert_aitask_fold.md`
- `aitasks/t777/t777_11_convert_aitask_qa.md`
- `aitasks/t777/t777_12_convert_aitask_pr_import.md`
- `aitasks/t777/t777_13_convert_aitask_revert.md`
- `aitasks/t777/t777_14_convert_aitask_pickrem.md`
- `aitasks/t777/t777_15_convert_aitask_pickweb.md`

Skip non-template siblings (t777_16 widget extract, t777_17 per-run edit,
t777_18 docs update, t777_19 retrospective, t777_20 invalidation, t777_23 swap).

**Regenerate golden files (15 files):**
- `tests/golden/procs/task-workflown/*.md` — re-render each of the 5 wrapped
  files against `default.yaml`, `fast.yaml`, `remote.yaml` and overwrite the
  matching golden. Because the separator uses `{#- ... -#}` stripping, expected
  delta is **zero rendered-byte change** (the renderer drops separator entirely;
  inline comments on `{% else %}`/`{% endif %}` are on the same line as tags
  that already render to a blank line). Verify by diffing the regenerated
  goldens against the committed ones — diff should be empty. If any non-empty
  diff appears, the convention's whitespace handling is off and must be fixed
  before committing.

### Renderer behavior — verified

`skill_template.py:62-68` uses `keep_trailing_newline=True` with no
`trim_blocks`/`lstrip_blocks`. Minijinja default leaves the newline after a
block tag. `{#- ... -#}` strips leading + trailing whitespace including
newlines, so a separator on its own line vanishes from output. Inline
`{# ... #}` on the same line as `{% else %}` / `{% endif %}` produces no
output and the tag's existing newline behavior is unchanged.

### Implementation order

1. Write the aidocs section first (acts as the authoritative reference cited
   by all subsequent edits).
2. Apply the convention to the 5 task-workflown files. Run a quick render
   spot-check on one file per profile (e.g. `planning.md` × fast) to confirm
   bytes match the committed golden.
3. Regenerate all 15 goldens with a single loop:
   ```bash
   for f in SKILL planning manual-verification-followup remote-drift-check satisfaction-feedback; do
     for p in default fast remote; do
       .ait-venv/bin/python .aitask-scripts/lib/skill_template.py \
         .claude/skills/task-workflown/$f.md \
         aitasks/metadata/profiles/$p.yaml claude \
         > tests/golden/procs/task-workflown/$f-$p.md
     done
   done
   ```
   (Use `require_ait_python` path; the test does the same.)
   Then `git diff tests/golden/procs/task-workflown/` — must be empty.
4. Add the convention reference paragraph to the 9 pending t777 sibling task
   files. Use `./.aitask-scripts/aitask_update.sh --batch <id> --append-section`
   if it supports it; otherwise direct Edit (these are task description bodies).
   Update each sibling's `updated_at` field to today (2026-05-18).
5. Run the t777_7 regression tests plus the broader render/template suite:
   - `bash tests/test_skill_render_task_workflown.sh`
   - `bash tests/test_skill_render.sh`
   - `bash tests/test_skill_render_uniform.sh`
   - `bash tests/test_skill_template.sh`
   - `bash tests/test_skill_verify.sh`
6. Run `./ait skill verify` as the final sanity check.

## Verification

- `git diff tests/golden/procs/task-workflown/` is empty after step 3 (proves
  the new comments are render-neutral by design).
- All 5 test scripts in step 5 print `Tests: N, Passed: N, Failed: 0`.
- `./ait skill verify` exits 0.
- Manual spot-read of `.claude/skills/task-workflown/SKILL.md` confirms each
  templated region opens with a visible `---------- <label> ----------`
  separator, every `{% else %}` / `{% elif %}` carries a "when this fires"
  hint, and every `{% endif %}` names its label.
- Manual spot-read of one pending t777 sibling (e.g. t777_8) confirms the new
  conventions paragraph is present and points at the aidocs section.
