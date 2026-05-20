---
Task: t777_13_convert_aitask_revert.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-20 15:57
---

# Plan: t777_13 — Convert `aitask-revert` to template + stubs (4 agents)

## Context

`aitask-revert` is the next per-skill conversion in the t777 templated-dispatch
refactor. The refactor bakes execution-profile values into a rendered skill
variant *before* execution instead of re-reading the profile YAML at runtime —
eliminating the Step 0a "Select Execution Profile" round-trip and the
non-linear, ASK-dependent runtime flow.

Siblings t777_6 (pilot `pick`), t777_8 (`explore`), t777_9 (`review`),
t777_10 (`fold`), t777_11 (`qa`), t777_12 (`pr-import`) are all complete; the
deps for this task — t777_12, t777_7 (shared-proc templating), t777_22
(dep-walker), t777_26 (template-completeness/resolver-key rules) — are all
landed and archived.

**`aitask-revert` is a structural twin of `aitask-explore`** (not `pr-import`):
it references **both** `user-file-select` *and* `task-workflow`, has **no own
procedure files** (single `.claude/skills/aitask-revert/SKILL.md`), and has a
single `explore_auto_continue` profile wrap. `aitask-explore/SKILL.md.j2` is
the direct model.

## Verify-path findings (codebase confirmed; differences from the t777_12 model)

- **Two Step-0 sites to delete, not one.** `aitask-revert` has both
  `### Step 0 (pre-parse): Extract --profile argument` *and*
  `### Step 0a: Select Execution Profile`. (`explore`/`pr-import` had only
  Step 0a.) Both are deleted — `--profile` parsing is now owned by the stub.
- **The `## Arguments` section is KEPT (trimmed), not deleted.** It has 3
  bullets; only the 3rd (`--profile`) is removed. Bullets 1-2 (no-arg → Step 1
  discovery; numeric `42`/`t42` arg → Step 2) describe genuine runtime
  behavior that Step 1 implements and that the stub forwards. (Contrast
  `pr-import`, whose entire `## Arguments` section was `--profile`-only and was
  deleted.)
- **Single `**Profile check:**` wrap site:** Step 5 "Decision Point",
  `explore_auto_continue` (bool). Grep-confirmed — exactly one site.
- **`aitask-revert`'s "Save for later" branch DOES call Satisfaction
  Feedback** (current SKILL.md line 646) — preserved verbatim. (Contrast
  `pr-import`, whose "Save for later" branch did not.)
- `user-file-select` cross-ref (Step 1 Path B) is rewritten correctly by the
  dep-walker — verified in the live `aitask-explore-fast-` render
  (`.claude/skills/user-file-select-fast-/SKILL.md`).
- **No bare `SKILL.md` token in prose** — all `SKILL.md` mentions are
  full-path `.claude/skills/.../SKILL.md` refs, so the t777_11 dep-walker
  target-path collision cannot occur. (`grep -nE '(^|[^a-zA-Z/_.-])SKILL\.md'`
  → empty.)
- **No stray `{{` / `{%` in the source** — no `{% raw %}` wrapping needed.
- Resolver key `aitask-revert → revert` is already wired in
  `aitask_skill_verify.sh` (`aitask-revert) echo "revert" ;;`) — no script
  change. `aitask_skill_verify.sh` auto-discovers `SKILL.md.j2` via `find` —
  the new template needs no registration.

## Decision: direct conversion, not staged

Per pilot lesson (`feedback_stage_under_parallel_name`), parallel-name staging
applies only when the conversion is driven by the skill being converted.
`aitask-revert` is not driving this conversion (`aitask-pick` is). Editing in
place is safe — same call as t777_8/t777_9/t777_10/t777_11/t777_12.

## Critical Files

**Created / replaced (5 framework files):**
- `.claude/skills/aitask-revert/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-revert/SKILL.md` *(replace — canonical Claude stub, `aidocs/stub-skill-pattern.md` §3b, `--agent claude`)*
- `.agents/skills/aitask-revert/SKILL.md` *(replace — Codex stub §3b, `--agent codex`)*
- `.gemini/commands/aitask-revert.toml` *(replace — Gemini stub §3c, `--agent gemini`)*
- `.opencode/commands/aitask-revert.md` *(replace — OpenCode stub §3d, `--agent opencode`)*

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_revert.sh` *(new)* — adapted from `tests/test_skill_render_aitask_explore.sh`
- `tests/golden/skills/aitask-revert/SKILL-<profile>-claude.md` — 3 entry-point goldens (default/fast/remote, claude canonical)

**Left untouched (out of scope):**
- `.opencode/skills/aitask-revert/SKILL.md` — orphaned legacy OpenCode
  wrapper. `aitask-explore`/`aitask-qa`/`aitask-pr-import` all left their
  equivalents in place; following that precedent. A framework-wide sweep of
  these orphans is a candidate follow-up, not a per-skill task.

**Read-only references:** `.claude/skills/aitask-explore/SKILL.md.j2` (direct
model), the 4 `aitask-explore` stubs, `aiplans/archived/p777/p777_8_*.md` and
`p777_12_*.md`, `tests/test_skill_render_aitask_explore.sh`,
`aidocs/stub-skill-pattern.md`, `aidocs/skill_authoring_conventions.md`
(Jinja-comment convention + golden regen rule).

## Template authoring — `.claude/skills/aitask-revert/SKILL.md.j2`

Source: copy current `.claude/skills/aitask-revert/SKILL.md`, then apply:

1. **Frontmatter** — `name: aitask-revert-{{ profile.name }}`; keep the
   `description:` line **verbatim** (`Revert changes associated with completed
   tasks — fully or partially`, no trailing period — the Claude SKILL.md
   canonical); **drop `user-invocable: true`**.

2. **`## Arguments` section** — remove only the 3rd bullet (the
   `Optional --profile <name>` line). Keep the no-arg and numeric-arg bullets.

3. **Delete `### Step 0 (pre-parse): Extract --profile argument`** entirely
   (lines 15-23) — `--profile` parsing is owned by the stub (§3h).

4. **Delete `### Step 0a: Select Execution Profile`** entirely (lines 25-29) —
   forbidden runtime profile-resolution site (§3j). Its
   `execution-profile-selection.md` cross-ref disappears with it. First
   surviving Workflow heading: `### Step 1: Task Discovery`.

5. **Wrap Step 5 "Decision Point" `explore_auto_continue` check** — bool key,
   two-armed, modelled exactly on `aitask-explore/SKILL.md.j2` Step 4:
   ```jinja
   {# ---------- explore_auto_continue ---------- #}{% if profile.explore_auto_continue is defined and profile.explore_auto_continue %}
   - Display: "Profile '{{ profile.name }}': continuing to implementation"
   - Skip the AskUserQuestion below and proceed directly to the handoff
   {% else %}{# explore_auto_continue: when false / undefined #}
   Use `AskUserQuestion`:
   - Question: "Revert task created successfully. How would you like to proceed?"
   ... (existing options + both **If "..."** action blocks, verbatim —
       including the Satisfaction Feedback call in the "Save for later" block)
   {% endif %}{# ---------- end explore_auto_continue ---------- #}
   ```
   The `**Default when explore_auto_continue is not defined:** false` prose
   line is dropped — the `is defined and` guard makes it implicit. **Behavior
   preserved exactly:** the `{% else %}` arm keeps `aitask-revert`'s current
   option ordering ("Continue to implementation" / "Save for later") and its
   Satisfaction Feedback Procedure call in the "Save for later" branch.

6. **Step 6 handoff context variables** — replace the two runtime-resolved
   lines with baked-in values (mirrors `aitask-explore` Step 5):
   ```
   - **active_profile**: `{ name: {{ profile.name }} }` (baked in at render time)
   - **active_profile_filename**: `{{ profile.name }}.yaml`
   ```

7. **Keep verbatim** the `.claude/skills/user-file-select/SKILL.md` ref
   (Step 1 Path B) and the `.claude/skills/task-workflow/` full-path refs
   (`task-creation-batch.md` Step 4, `satisfaction-feedback.md` Step 5,
   `SKILL.md` Step 6 + Notes) — the dep-walker rewrites them per-agent to
   `<root>/...-<profile>-/`.

8. **Pre-check before save:** `grep -nE '\{\{|\{%' SKILL.md.j2` — only the
   intended Jinja directives from steps 1/5/6 should appear.

## Stubs (4 files, canonical bodies §3b–§3d)

Copy from the `aitask-explore` stubs, substituting `aitask-explore` →
`aitask-revert`, resolver key `explore` → `revert`, and the `description` to
`Revert changes associated with completed tasks — fully or partially` (no
trailing period — matches the Claude SKILL.md canonical; this also normalizes
the current minor inconsistency where the Codex/Gemini/OpenCode wrappers carry
a trailing period):
- `.claude/skills/aitask-revert/SKILL.md` ← Claude stub (`--agent claude`)
- `.agents/skills/aitask-revert/SKILL.md` ← Codex stub (`--agent codex`)
- `.gemini/commands/aitask-revert.toml` ← Gemini stub (`--agent gemini`)
- `.opencode/commands/aitask-revert.md` ← OpenCode stub (`--agent opencode`)

Each stub: §3b/§3c/§3d canonical body, profile-agnostic, resolver call
`aitask_skill_resolve_profile.sh revert`, render call
`aitask_skill_render.sh aitask-revert --profile <profile> --agent <literal>`,
Read target `<root>/aitask-revert-<profile>-/SKILL.md`.

## Test script — `tests/test_skill_render_aitask_revert.sh`

Adapt `tests/test_skill_render_aitask_explore.sh` (no procedure-golden loop —
`aitask-revert` has no own procedure files):

- **Test 1** — 3 entry-point golden diffs (default/fast/remote, claude render).
- **Test 1b** — agent-dimension invariance: codex/gemini/opencode stdout
  renders byte-identical to claude (no `{% if agent %}` gate).
- **Test 2** — profile-conditional sanity: all 3 profiles render the
  `{% else %}` arm — assert `Revert task created successfully. How would you
  like to proceed?` present, assert `': continuing to implementation` absent.
- **Test 3** — no Jinja markers (`{%`, `{{`) leak into any rendered entry-point.
- **Test 3b** — §3j forbidden tokens absent (`aitask_scan_profiles.sh`,
  `Execute the Execution Profile Selection Procedure`, `Select Execution
  Profile`, `refresh execution profile`) across all profile × agent renders.
- **Test 4** — cross-agent ref rewrite via `aitask_skill_render.sh ... --force`:
  for each agent assert **both** `<root>/task-workflow-fast-/SKILL.md` **and**
  `<root>/user-file-select-fast-/SKILL.md` appear in the rendered
  `aitask-revert-fast-/SKILL.md`. (The `user-file-select` assertion is the one
  addition beyond the explore-test model — `aitask-revert` references that
  closure and the rewrite must be verified.)
- **Test 5** — 4 stubs contain canonical markers:
  `aitask_skill_resolve_profile.sh revert` (and NOT `... aitask-revert`),
  `aitask_skill_render.sh aitask-revert`, `Dispatch via Read-and-follow`, the
  correct `--agent` literal, and the per-agent rendered-variant Read path.

## Goldens (3 files)

Generate with the framework Python (`python_resolve.sh::require_ait_python`):
```bash
mkdir -p tests/golden/skills/aitask-revert
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-revert/SKILL.md.j2 \
    aitasks/metadata/profiles/$p.yaml claude \
    > tests/golden/skills/aitask-revert/SKILL-$p-claude.md
done
```
All 3 committed (claude-only — the basic stdout render does no per-agent
rewriting, so codex/gemini/opencode are byte-identical and covered by Test 1b).

## Implementation Steps (execution order)

1. Author `.claude/skills/aitask-revert/SKILL.md.j2` (edits 1-8 above).
   Smoke-render: `$PYTHON .aitask-scripts/lib/skill_template.py .claude/skills/aitask-revert/SKILL.md.j2 aitasks/metadata/profiles/fast.yaml claude | head -40`.
2. Write the 4 stubs (overwrite existing per-agent surfaces).
3. Generate the 3 goldens (loop above).
4. Render the full closure for all 4 agents × 3 profiles so live dispatch works:
   `for a in claude codex gemini opencode; do for p in default fast remote; do ./.aitask-scripts/aitask_skill_render.sh aitask-revert --profile $p --agent "$a" --force; done; done`.
5. Write `tests/test_skill_render_aitask_revert.sh`.
6. Run `bash tests/test_skill_render_aitask_revert.sh` and
   `./.aitask-scripts/aitask_skill_verify.sh` — both MUST be green.
7. Grep stragglers: `grep -rn 'aitask-revert' .claude/skills/aitask-revert/ .agents/skills/aitask-revert/ .gemini/commands/aitask-revert.toml .opencode/commands/aitask-revert.md tests/test_skill_render_aitask_revert.sh`.

## Verification

1. `bash tests/test_skill_render_aitask_revert.sh` — exits 0, all 3 golden
   diffs empty, invariance / profile-branch / forbidden-token / ref-rewrite /
   stub assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0 (renders all 4 agents
   × default profile, walk-checks the revert closure incl. the `task-workflow`
   and `user-file-select` subtrees, validates the 4 stubs).
3. Forbidden-token scan on every rendered golden — clean.
4. Stub-dispatch dry-run (manual, post-merge): `/aitask-revert` reads the stub
   → renders → Read-and-follows the rendered variant.

## Out of scope (deferred)

- `.opencode/skills/aitask-revert/SKILL.md` orphan cleanup — left in place per
  the `aitask-explore`/`aitask-qa`/`aitask-pr-import` precedent. Framework-wide
  orphan sweep is a candidate follow-up across all converted skills.

## Step 9 (Post-Implementation)

Standard child-task archival. Code commit:
`refactor: Convert aitask-revert to template + stubs (t777_13)`. Plan commit
via `./ait git`. Archive: `./.aitask-scripts/aitask_archive.sh 777_13`. Push
via `./ait git push`. No linked issue. Profile `fast` → no worktree (work on
current branch); the Step 9 merge-approval gate is a no-op.

The 4 stubs cover all 4 agents in this same task — no separate
Codex/Gemini/OpenCode follow-up tasks are needed.

## Notes for sibling tasks

`aitask-revert` confirmed the `aitask-explore` single-template pattern (no own
procedure files; references both `user-file-select` and `task-workflow`).
`aitask-pickrem` (t777_14) / `aitask-pickweb` (t777_15) should each first grep
their skill dir for sibling procedure files to choose between the `aitask-qa`
(t777_11, procedure-closure) and `aitask-explore` (single-template) patterns.

## Final Implementation Notes

- **Actual work done:** Authored `.claude/skills/aitask-revert/SKILL.md.j2`
  from the existing `aitask-revert/SKILL.md` (frontmatter
  `name: aitask-revert-{{ profile.name }}`, dropped `user-invocable: true`;
  removed the `--profile` bullet from `## Arguments` while keeping the no-arg /
  numeric-arg bullets; deleted both `### Step 0 (pre-parse): Extract --profile
  argument` and `### Step 0a: Select Execution Profile`; wrapped the single
  Step 5 `explore_auto_continue` profile check as a two-armed
  `{% if %}`/`{% else %}`; baked `active_profile` / `active_profile_filename`
  into the Step 6 handoff). Replaced all 4 per-agent surfaces with canonical
  stubs (resolver key `revert`): `.claude/skills/aitask-revert/SKILL.md`,
  `.agents/skills/aitask-revert/SKILL.md`,
  `.gemini/commands/aitask-revert.toml`, `.opencode/commands/aitask-revert.md`.
  Generated 3 entry-point goldens
  (`tests/golden/skills/aitask-revert/SKILL-<profile>-claude.md`). Authored
  `tests/test_skill_render_aitask_revert.sh` (122 assertions across Tests
  1/1b/2/3/3b/4/5).
- **Deviations from plan:** None. The conversion matched the planned
  `aitask-explore` model exactly.
- **Issues encountered:** None. `aitask_skill_verify.sh` auto-discovered the
  new `SKILL.md.j2` (now 7 templates), the resolver key `revert` was already
  wired, and the dep-walker rendered the full closure (incl. both the
  `task-workflow` and `user-file-select` subtrees) for all 4 agents without
  intervention. `bash tests/test_skill_render_aitask_revert.sh` → 122/122;
  `./.aitask-scripts/aitask_skill_verify.sh` → OK.
- **Key decisions:**
  - Direct in-place conversion (not staged under `aitask-revertn`):
    `aitask-pick` drives this conversion, not `aitask-revert` — same call as
    t777_8/.../t777_12.
  - The `## Arguments` section was **kept (trimmed)**, not deleted: its no-arg
    and numeric-arg bullets describe genuine runtime behavior implemented by
    Step 1; only the `--profile` bullet (now owned by the stub) was removed.
    This differs from `pr-import`, whose entire `## Arguments` section was
    `--profile`-only and was deleted.
  - `aitask-revert`'s "Save for later" branch (which calls the Satisfaction
    Feedback Procedure, unlike `pr-import`'s) was preserved verbatim inside the
    `{% else %}` arm — mechanical conversion does not change behavior.
  - Test 4 extended beyond the `aitask-explore` test model with explicit
    `user-file-select` ref-rewrite assertions — `aitask-revert` references
    that closure (Step 1 Path B) and the per-agent rewrite must be verified.
  - 3 goldens, claude-only — the basic stdout render does no per-agent
    rewriting, so codex/gemini/opencode are byte-identical (Test 1b).
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** `aitask-revert` is a structural twin of
  `aitask-explore` — no own procedure files, single `explore_auto_continue`
  wrap, references both `user-file-select` and `task-workflow`. Two carryover
  observations for a framework-wide follow-up (not per-skill): (1) the
  orphaned legacy `.opencode/skills/aitask-revert/SKILL.md` wrapper, left in
  place per the explore/qa/pr-import precedent; (2) the 3 non-Claude wrappers
  previously carried a trailing-period `description` while the Claude
  SKILL.md did not — the 4 new stubs normalize all 4 to the no-period
  canonical.
