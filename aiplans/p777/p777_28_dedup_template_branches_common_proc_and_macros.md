---
Task: t777_28_dedup_template_branches_common_proc_and_macros.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_18_*.md, aitasks/t777/t777_19_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Worktree: (current branch — fast profile, no separate worktree)
Branch: main
Base branch: main
---

# Plan: Dedup `.md.j2` branch text via Jinja macros + `{% from %}` (t777_28)

## Context

The t777 conversion siblings (t777_6..t777_13) each landed their own
`.claude/skills/<skill>/SKILL.md.j2`, producing two duplication shapes:

1. **Cross-skill** — the `explore_auto_continue` decision-point block
   appears nearly verbatim in `aitask-explore`, `aitask-fold`,
   `aitask-pr-import`, `aitask-revert` (~76 duplicated lines total).
2. **Within `aitask-pick`** — the `skip_task_confirmation` branch appears
   twice (parent-task vs child-task confirmation) with only the
   AskUserQuestion `Question:` string and indent depth differing.

Per the user's clarification, dedup happens **at the Jinja-render layer**
using macros, not via procedure-markdown extraction with agent-runtime
parameter substitution. Procedure-markdown is appropriate for long, lightly
parameterized procedures (the satisfaction-feedback shape); a 5-parameter
decision-point is a poor fit. Increasing Jinja usage in skills — including
extending the framework's dep-walker to track new Jinja constructs — is
explicitly endorsed scope.

Verified minijinja capabilities via smoke tests:
- `{% from "X" import macro_name %}` + macro call with kwargs and defaults ✓
- `{% import "X" as lib %}` + `{{ lib.macro_name(...) }}` ✓
- `{% macro %}` defined anywhere before its first call ✓

`t777_27` (recover runtime-check fixtures + parity tests) is **Done**, so
`tests/test_skill_parity_runtime_vs_rendered.sh` guards the `aitask-pick`
macro refactor against semantic drift.

## Approach

### Framework extension — track `{% from %}` and `{% import %}` for staleness

`.aitask-scripts/lib/skill_template.py:83` currently has:

```python
INCLUDE_RE = re.compile(r'\{%-?\s*include\s+["\']([^"\']+)["\']')
```

Only `{% include %}` is tracked in `_resolve_include_deps()` (lines 217–233),
which means editing a macro file imported via `{% from %}` would NOT
invalidate cached renders of consuming SKILL.md files.

Extend the scanner to also match `{% from %}` and `{% import %}`. Concretely:

```python
TEMPLATE_DEP_RES = [
    re.compile(r'\{%-?\s*include\s+["\']([^"\']+)["\']'),
    re.compile(r'\{%-?\s*from\s+["\']([^"\']+)["\']\s+import\b'),
    re.compile(r'\{%-?\s*import\s+["\']([^"\']+)["\']'),
]
```

Rename `_resolve_include_deps()` → `_resolve_template_deps()` (keep
backward-compatible behavior — `INCLUDE_RE` becomes part of the list) and
update its body to iterate the list. Call-site at line 293 stays the same.

The function's docstring mentions `{% include %}` specifically — update it
to "include/from/import directives".

#### Framework-extension test

Extend `tests/test_skill_render_uniform.sh` (currently at line ~279
"Touch the LEAF source (B) — closure-aware skip should detect staleness")
to cover the new constructs. Add a small test fixture pair:

- a macro file imported via `{% from %}` that bumps a counter
- assert that touching the macro file invalidates the rendered consumer

Alternative: rely on the integration coverage provided by the new
`_auto_continue_block.md` macro (touched by all 4 calling skills). If the
dep-walker fails to track `{% from %}`, the calling-skill render tests
will catch it via stale-golden mismatch after a macro-file edit. Keep
this minimal — one targeted test addition under the existing staleness
test block, mirroring the `{% include %}` case.

### Lever 1 — Cross-skill: shared Jinja macro imported via `{% from %}`

Add `.aitask-scripts/skill_templates/_auto_continue_block.j2` defining a
single macro:

```jinja
{% macro auto_continue_block(question, continue_target, default_option="continue", save_pick_arg="<N>", save_filename_template="t<N>_<name>.md", feedback_skill_name="") -%}
{% if profile.explore_auto_continue is defined and profile.explore_auto_continue -%}
- Display: "Profile '{{ profile.name }}': continuing to implementation"
- Skip the AskUserQuestion below and proceed directly to {{ continue_target }}
{% else -%}
Use `AskUserQuestion`:
- Question: "{{ question }}"
- Header: "Proceed"
- Options:
{% if default_option == "save" -%}
  - "Save for later" (description: "Task saved — pick it up later with /aitask-pick {{ save_pick_arg }}")
  - "Continue to implementation" (description: "Proceed to {{ continue_target }}")
{% else -%}
  - "Continue to implementation" (description: "Start implementing the task now via the standard workflow")
  - "Save for later" (description: "Task saved — pick it up later with /aitask-pick {{ save_pick_arg }}")
{% endif %}

**If "Save for later":**
- Inform user: "Task {{ save_filename_template }} is ready. Run `/aitask-pick {{ save_pick_arg }}` when you want to implement it."
{% if feedback_skill_name -%}
- Execute the **Satisfaction Feedback Procedure** (see `.claude/skills/task-workflow/satisfaction-feedback.md`) with `skill_name` = `"{{ feedback_skill_name }}"`.
{% endif -%}
- End the workflow.

**If "Continue to implementation":**
- Proceed to {{ continue_target }}.
{% endif -%}
{%- endmacro %}
```

(Final wording polished to byte-match each prior rendered output once
parameters are substituted. Whitespace flags `{%- -%}` tuned via golden
diff.)

Note: `.j2` extension chosen because this file is purely Jinja machinery
(macro definitions), not a procedure-markdown file consumed by humans. The
dep-walker treats either extension uniformly via the include-search-dirs
loader.

#### Call-site replacement in each of the 4 skills

Replace the ~19-line `{% if profile.explore_auto_continue ... %}` block with
2 lines:

```jinja
{% from "_auto_continue_block.j2" import auto_continue_block %}
{{ auto_continue_block(question="Task created successfully. How would you like to proceed?", continue_target="the handoff below", feedback_skill_name="explore") }}
```

(The `{% from %}` line lives once at the top of each calling SKILL.md.j2 so
the macro is in scope at the call-site. Defaults in the macro signature
mean each call-site only passes the params that diverge from defaults.)

Per-skill macro call:

| Skill        | Macro call (kwargs) |
|--------------|---------------------|
| `explore`    | `auto_continue_block(question="Task created successfully. How would you like to proceed?", continue_target="the handoff below", feedback_skill_name="explore")` |
| `fold`       | `auto_continue_block(question="Tasks folded successfully into t<primary_id>. How would you like to proceed?", continue_target="the handoff below", save_pick_arg="<primary_id>", save_filename_template="t<primary_id>_<name>.md")` |
| `pr-import`  | `auto_continue_block(question="Task created successfully. How would you like to proceed?", continue_target="Step 7", default_option="save")` + a 1-line PR-import-specific "default is Save for later" prose note just below |
| `revert`     | `auto_continue_block(question="Revert task created successfully. How would you like to proceed?", continue_target="Step 6", save_filename_template="t<N>_revert_t<original_id>.md", feedback_skill_name="revert")` |

The PR-import "Default is Save for later — unlike aitask-explore…" prose
stays inline in PR-import's SKILL.md.j2 (it's PR-import commentary, not
part of the shared block).

### Lever 2 — Within `aitask-pick`: in-file `{% macro %}`

Define `confirm_task_selection(indent, summary)` as a `{% macro %}`
**immediately before `### Step 0b`** (not at the top of the file).
Co-locating the macro with its call-sites keeps the abstraction readable.

```jinja
{% macro confirm_task_selection(indent, summary) -%}
{% if profile.skip_task_confirmation is defined and profile.skip_task_confirmation -%}
{{ indent }}- Display: "Profile '{{ profile.name }}': auto-confirming task selection"
{{ indent }}- Proceed directly to **Step 3** (Task Status Checks)
{% else -%}
{{ indent }}- Use `AskUserQuestion`:
{{ indent }}  - Question: "Is this the correct task? Brief summary: {{ summary }}"
{{ indent }}  - Header: "Confirm task"
{{ indent }}  - Options: "Yes, proceed" (description: "This is the correct task, continue with aitask-pick workflow") / "No, abort" (description: "Wrong task, cancel the selection")
{{ indent }}- If "Yes, proceed" → proceed to **Step 3** (Task Status Checks)
{{ indent }}- If "No, abort" → fall back to normal task selection (proceed to Step 1)
{% endif -%}
{%- endmacro %}
```

Replace the two ~11-line `{% if profile.skip_task_confirmation … %}` blocks
with single-line calls:

- Parent (currently lines 24–34, indent depth 6 spaces):
  ```jinja
  {{ confirm_task_selection("      ", "<1-2 sentence summary of the task>") }}
  ```
- Child (currently lines 53–63, indent depth 4 spaces):
  ```jinja
  {{ confirm_task_selection("    ", "<1-2 sentence summary of the child task> (Parent: <parent task name>)") }}
  ```

Whitespace flags tuned to match existing newlines — parity test catches
drift.

### Skip the `{% set has_X = … %}` cosmetic cleanup

Task description marks this "Optional / nice-to-have" with "Skip if it
churns goldens for no semantic reason." Skip.

### Lever 3 — Authoring documentation

Add a new section to `aidocs/skill_authoring_conventions.md` titled
**"Jinja templating in skills"**, placed after the existing "Jinja comment
conventions for profile-aware templates" section. It must cover:

1. **Macros — in-file vs. shared.**
   - **In-file `{% macro %}`** when two near-identical blocks within one
     template differ only by a few parameters (indent, summary, …). Define
     immediately before the first call-site, not at top of file. Example:
     the `confirm_task_selection(indent, summary)` macro in
     `aitask-pick/SKILL.md.j2` introduced by t777_28.
   - **Shared macro via `{% from "X" import Y %}`** when the same block is
     duplicated across multiple skills. Macro lives under
     `.aitask-scripts/skill_templates/_<topic>.j2` (leading underscore
     marks it as a fragment). Example: `_auto_continue_block.j2` consumed
     by 4 skills, introduced by t777_28.
   - When to use macros vs `{% include %}` vs procedure-markdown
     extraction. Rule of thumb (per [[feedback-expand-jinja-in-skills]]):
     macros for 1–N parameters, render-time substitution; procedure-markdown
     for genuinely long procedures with 0–2 well-named runtime parameters
     (the satisfaction-feedback shape).

2. **The `.aitask-scripts/skill_templates/` shared-fragment directory.**
   Cross-link from this section into `skill_templates/README.md` (and
   add a back-link the other direction). Note that the dep-walker tracks
   `{% include %}`, `{% from %}`, and `{% import %}` directives for
   staleness — touch a fragment and every consumer re-renders on next
   `aitask_skill_render.sh` run.

3. **Whitespace-control flags** (`{%-`, `-%}`, `{{-`, `-}}`).
   - One-line summary of strip semantics (strips one preceding /
     following whitespace block including newlines).
   - The render-neutrality rule from the comment-conventions section
     applies here too: any flag change should yield zero golden diff
     unless intended.
   - When tuning macro output, the golden diff is the authoritative
     check — predict, render, diff, adjust.

4. **minijinja caveats** (mirroring `skill_template.py:8-11`):
   > minijinja is NOT 100% Jinja2-compatible. Stick to: `{{ var }}`,
   > `{% if %}/{% else %}/{% endif %}`, `{% for %}`, `{% include %}`,
   > `{% from %}/{% import %}`, `{% macro %}/{% endmacro %}`,
   > `{% set %}`, `{% raw %}/{% endraw %}`. No `{% extends %}` with
   > arbitrary Python, smaller filter set, no `do` extension.

5. **"How to read a profile-aware template" walkthrough.** A short worked
   example showing how to predict the rendered output of a representative
   block (e.g., the `{% if profile.skip_task_confirmation … %}` block from
   `aitask-pick`) under each of `default`/`fast`/`remote` profiles, by
   reading the template source alone. The goal: a coding agent editing
   the template can mentally render it and reason about behavior without
   running the renderer.

### NOT in scope

- `{% extends %}` / `{% block %}` (renderer note in `skill_template.py:8-11`
  recommends against).
- Procedure-markdown extraction with runtime parameter substitution (user
  rejected explicitly — too many params).
- Other skills' single-block duplications (`aitask-review`'s
  `review_default_modes`, etc.).
- Porting to `.codex/` / `.gemini/` / `.opencode/` — the walker writes
  per-agent sibling trees automatically.

## Files Touched

### Add (1 new file)

- `.aitask-scripts/skill_templates/_auto_continue_block.j2` — shared Jinja
  macro for Lever 1.

### Edit (8 files: 5 templates + 1 framework script + 2 docs)

- `.aitask-scripts/lib/skill_template.py` — extend `INCLUDE_RE` →
  `TEMPLATE_DEP_RES` list (`include`, `from`, `import`); update
  `_resolve_include_deps()` (rename to `_resolve_template_deps()`).
- `.claude/skills/aitask-explore/SKILL.md.j2` — replace lines 178–196 with
  macro call.
- `.claude/skills/aitask-fold/SKILL.md.j2` — same shape, lines 78–95.
- `.claude/skills/aitask-pr-import/SKILL.md.j2` — same shape, lines
  259–278; preserve PR-import-specific "default is Save for later" prose
  note.
- `.claude/skills/aitask-revert/SKILL.md.j2` — same shape, lines 613–631.
- `.claude/skills/aitask-pick/SKILL.md.j2` — define macro just before
  Step 0b; replace both call-sites.
- `aidocs/skill_authoring_conventions.md` — add new "Jinja templating in
  skills" section (Lever 3 content) after the existing "Jinja comment
  conventions for profile-aware templates" section.
- `.aitask-scripts/skill_templates/README.md` — add a brief back-link
  pointing at the new section in skill_authoring_conventions.md; expand
  the "Fragment naming and scope" list to include
  `_auto_continue_block.j2` once it lands.

### Regenerate goldens

- `tests/golden/skills/{aitask-explore,aitask-fold,aitask-pr-import,aitask-revert,aitask-pick}/SKILL-{default,fast,remote}-claude.md`
  (15 files — must be **byte-identical** to the pre-refactor goldens; any
  diff is a wording bug in the macro.)

### Tests

- Extend `tests/test_skill_render_uniform.sh` staleness block to cover
  `{% from %}` (touch macro → consumer re-renders). Minimal: one new
  assertion pair in the existing staleness block.
- No changes needed to `tests/test_skill_render_aitask_{explore,fold,pr_import,revert,pick}.sh`
  or `tests/test_skill_parity_runtime_vs_rendered.sh` — rendered output
  is byte-identical to pre-refactor, so "Test 2" sanity assertions all
  still match.

## Implementation Steps

1. **Extend the framework dep-walker.** Add `TEMPLATE_DEP_RES` list
   covering `include`/`from`/`import` to `skill_template.py`. Rename and
   update `_resolve_include_deps()`. Run
   `bash tests/test_skill_render_uniform.sh` to confirm no regression
   (existing `{% include %}` tests still pass).

2. **Add the staleness test for `{% from %}`.** Insert one assertion pair
   in `test_skill_render_uniform.sh`'s staleness block.

3. **Refactor `aitask-pick/SKILL.md.j2`** (Lever 2): define
   `confirm_task_selection` macro just before Step 0b; replace both
   call-sites. Run `bash tests/test_skill_render_aitask_pick.sh` —
   golden diff expected only in line count; regenerate and diff-review
   for semantic equivalence. Run
   `bash tests/test_skill_parity_runtime_vs_rendered.sh` — must pass
   (strongest semantic guarantee).

4. **Write the shared `_auto_continue_block.j2` macro.** Iteratively tune
   whitespace flags against `aitask-explore`'s golden (the largest /
   most representative case). Once `aitask-explore` golden diff is byte-
   identical post-refactor, move to the other three skills.

5. **Refactor the four `*_auto_continue` skills** (Lever 1) one at a
   time; regenerate per-skill golden after each; diff-review for
   semantic equivalence; run that skill's render test.

6. **Regenerate all 15 goldens and confirm byte-identical:**
   ```bash
   for skill in aitask-pick aitask-explore aitask-fold aitask-pr-import aitask-revert; do
     for p in default fast remote; do
       python3 .aitask-scripts/lib/skill_template.py \
         .claude/skills/$skill/SKILL.md.j2 \
         aitasks/metadata/profiles/$p.yaml claude \
         > tests/golden/skills/$skill/SKILL-$p-claude.md
     done
   done
   git diff tests/golden/  # expected: all empty (byte-identical)
   ```

7. **Write the docs** (Lever 3): add the new "Jinja templating in
   skills" section to `aidocs/skill_authoring_conventions.md` with the
   five sub-topics. Use the concrete `_auto_continue_block.j2` and
   `confirm_task_selection` macros as canonical examples. Add the
   back-link in `skill_templates/README.md`.

8. **Run full verification suite** (see Verification below).

9. **Line-count check:** confirm ≥60-line net reduction across the 5
   SKILL.md.j2 files. Approximate budget:
   - Lever 1: 4 × (~19 − ~2) = ~68 lines saved (2-line call-sites)
   - Lever 2: 2 × (~11 − ~1) − ~12 (macro def) = ~8 lines saved
   - Total: ~76 lines saved, well above the ≥60 target

## Verification

Run from repo root (`/home/ddt/Work/aitasks/`):

```bash
# Per-skill template render tests (all expected PASS, no golden churn)
bash tests/test_skill_render_aitask_pick.sh
bash tests/test_skill_render_aitask_explore.sh
bash tests/test_skill_render_aitask_fold.sh
bash tests/test_skill_render_aitask_pr_import.sh
bash tests/test_skill_render_aitask_revert.sh

# Closure walker / uniform render (also covers new {% from %} staleness)
bash tests/test_skill_render_uniform.sh

# task-workflow render (touched indirectly)
bash tests/test_skill_render_task_workflow.sh

# Parity guard against pre-rewrite fixtures (t777_27)
bash tests/test_skill_parity_runtime_vs_rendered.sh

# Full verify pass — renders every closure, validates stubs, no leaks
./.aitask-scripts/aitask_skill_verify.sh

# Bash lint
shellcheck .aitask-scripts/aitask_*.sh

# Confirm net line-count drop ≥60 across 5 SKILL.md.j2 files
git diff --stat HEAD -- .claude/skills/aitask-{pick,explore,fold,pr-import,revert}/SKILL.md.j2
```

The strongest correctness guarantees:
- `bash tests/test_skill_parity_runtime_vs_rendered.sh` — diffs
  aitask-pick's rendered output against the t777_27-recovered pre-rewrite
  runtime fixtures.
- Empty `git diff tests/golden/skills/` after regeneration — confirms
  byte-identical rendered output across all 15 (skill × profile) pairs.

## Reference to Step 9 (Post-Implementation)

Cleanup, archival, and merge handled by task-workflow Step 9. This is a
child task — archived plan must end with comprehensive Final Implementation
Notes (per `task-workflow-fast-/SKILL.md` Step 8 child-task requirement)
covering:

- Final wording polish that made each rendered output byte-match prior
  goldens (whitespace flags, default_option option-ordering, the PR-import
  "default is Save for later" note placement).
- Confirmation that the dep-walker extension to `{% from %}` / `{% import %}`
  works end-to-end (touch macro → consumer re-renders) and adds no new
  failure modes for the existing `{% include %}` consumers.
- Whether the macro-default-parameter strategy was clean enough that
  call-sites only mention diverging params, or whether keyword passing was
  too noisy in practice.
