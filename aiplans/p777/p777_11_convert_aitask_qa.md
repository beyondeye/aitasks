---
Task: t777_11_convert_aitask_qa.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-20 11:14
---

# Plan: t777_11 — Convert `aitask-qa` to template + stubs (4 agents)

## Context

`aitask-qa` is the next per-skill conversion in the t777 templated-dispatch
refactor. Siblings t777_6 (pilot pick), t777_8 (explore), t777_9 (review),
t777_10 (fold) are all complete; the dep-walker (t777_22), shared-proc
templating (t777_7) and template-completeness rules (t777_26) all landed.
The conversion lets `aitask-qa` use baked-in profile values instead of
re-reading the profile YAML at runtime — eliminating the Step 0 (`--profile`
parse) + Step 0a "Select Execution Profile" round-trip.

**Verify-path finding — the thin pre-existing plan was wrong about scope.**
The committed p777_11 stub assumed all three profile checks (`qa_mode`,
`qa_run_tests`, `qa_tier`) live in `SKILL.md`. They do not. `aitask-qa` is
the **first conversion with its own procedure-file closure** (6 sibling `.md`
files), and the profile checks are spread across the entry-point template and
3 procedure files. A `grep` for `Profile check` found **4** wrap sites, not 3:

| Profile key | File | Site |
|---|---|---|
| `qa_tier` (enum q/s/e) | `SKILL.md` | Step 1c "Select QA Tier" |
| `qa_mode` (enum ask/create_task/implement/plan_only) | `test-plan-proposal.md` | Step 5b "Determine action" |
| `qa_run_tests` (bool) | `test-execution.md` | Step 4a profile check |
| `skip_task_confirmation` (bool) | `task-selection.md` | Step 1a "Confirm selection" |

`skip_task_confirmation` was missed by the original plan. It must be wrapped
too: after Step 0a is deleted, `active_profile` no longer exists as a runtime
variable, so any un-wrapped `**Profile check:**` block referencing it is dead
code. All 4 procedure files are part of the qa render closure (dep-walker
renders every reachable `.md`), so the profile checks in them must become
Jinja conditionals.

## Decision: direct conversion, not staged

Per pilot lesson #2 (`feedback_stage_under_parallel_name`), parallel-name
staging applies only when the conversion is driven by the skill being
converted. `aitask-qa` is **not** driving this conversion (`aitask-pick` is).
Editing in place is safe — same call as t777_8/t777_9/t777_10.

## Critical Files

**Created / replaced (5 framework files):**
- `.claude/skills/aitask-qa/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-qa/SKILL.md` *(replace — canonical Claude stub, `aidocs/stub-skill-pattern.md` §3b, `<agent_literal>=claude`)*
- `.agents/skills/aitask-qa/SKILL.md` *(replace — Codex stub §3b, `codex`)*
- `.gemini/commands/aitask-qa.toml` *(replace — Gemini stub §3c)*
- `.opencode/commands/aitask-qa.md` *(replace — OpenCode stub §3d)*

**Edited in place (3 procedure files — profile-check wraps):**
- `.claude/skills/aitask-qa/test-plan-proposal.md` — wrap `qa_mode` at Step 5b
- `.claude/skills/aitask-qa/test-execution.md` — wrap `qa_run_tests` at Step 4a
- `.claude/skills/aitask-qa/task-selection.md` — wrap `skip_task_confirmation` at Step 1a

**Untouched procedure files (identity-render passthrough):**
`change-analysis.md`, `test-discovery.md`, `follow-up-task-creation.md` — no
profile markers; rendered by the dep-walker as identity transforms.

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_qa.sh` *(new)* — adapted from `tests/test_skill_render_aitask_fold.sh`
- `tests/golden/skills/aitask-qa/SKILL-<profile>-<agent>.md` — 12 entry-point goldens (3 profiles × 4 agents)
- `tests/golden/procs/aitask-qa/<name>-<profile>.md` — 9 procedure goldens (3 profile-bearing files × 3 profiles, claude only)

**Read-only references:** `aiplans/archived/p777/p777_10_convert_aitask_fold.md`
(closest model), `.claude/skills/aitask-review/SKILL.md.j2` (multi-key/enum
reference), `aidocs/stub-skill-pattern.md` §3b–§3d/§3f/§3i/§3j,
`aidocs/skill_authoring_conventions.md` (Jinja-comment convention + golden
regen rule), `tests/test_skill_render_aitask_fold.sh`,
`tests/test_skill_render_task_workflow.sh` (procedure-golden loop pattern).

No change needed to `aitask_skill_verify.sh` — `_resolver_key_for()` already
maps `aitask-qa → qa` (line 73).

## Render-closure facts (verified)

- `aitask-qa → qa` resolver key already wired in `aitask_skill_verify.sh:73`.
- Entry-point `SKILL.md.j2` references `.claude/skills/task-workflow/satisfaction-feedback.md` (full-path) → rewritten per-agent ⇒ 12 distinct entry-point goldens.
- The 3 wrapped procedure files have no cross-skill (full-path) refs — only sibling refs to each other ⇒ agent-invariant ⇒ claude-only procedure goldens (matches the `task-workflow/` proc-golden precedent from t777_7).
- Profile-YAML state: `default.yaml` sets no qa keys; `fast.yaml` sets `qa_mode: ask` + `skip_task_confirmation: true`; `remote.yaml` sets `skip_task_confirmation: true`. Consequences:
  - `qa_mode`: all 3 profiles render the `{% else %}` (interactive) arm — `ask` and unset both fall through.
  - `qa_run_tests` / `qa_tier`: never set ⇒ `qa_run_tests` one-armed block renders empty; `qa_tier` renders the `{% else %}` (AskUserQuestion) arm.
  - `skip_task_confirmation`: `fast`/`remote` render the `{% if %}` (auto-confirm) arm; `default` renders the `{% else %}` arm — this key gets real golden coverage of both arms.

## Template authoring — `.claude/skills/aitask-qa/SKILL.md.j2`

Source: copy current `.claude/skills/aitask-qa/SKILL.md`, then apply:

1. **Frontmatter** — `name: aitask-qa-{{ profile.name }}`.

2. **Delete Step 0 "(pre-parse): Extract `--profile` argument"** (lines 9–17)
   and **Step 0a "Select Execution Profile"** (lines 19–25). Profile is baked
   in at render time (§3j); these are forbidden runtime profile-resolution
   sites. The `feedback_collected` initialisation currently in Step 0a is
   relocated to a one-line note at the start of Step 1 ("Initialize
   `feedback_collected` to `false`."). The satisfaction-feedback guard
   (`satisfaction-feedback.md:46`) already tolerates an undefined value, but
   relocating keeps the intent explicit. First surviving heading: `### Step 1`.

3. **Wrap Step 1c `qa_tier` check** — enum key, but the value passes straight
   through to the `tier` context variable, so use inline substitution (no
   `elif` chain needed):
   ```jinja
   {# ---------- qa_tier ---------- #}{% if profile.qa_tier is defined and profile.qa_tier %}
   - Display: "Profile '{{ profile.name }}': qa_tier={{ profile.qa_tier }}"
   - Set the `tier` context variable to `{{ profile.qa_tier }}`.
   {% else %}{# qa_tier: when unset — ask interactively #}
   Use `AskUserQuestion`:
   - Question: "Select QA analysis depth:"
   ... (existing options + the "Set the `tier` context variable" mapping block)
   {% endif %}{# ---------- end qa_tier ---------- #}
   ```

4. **`## Procedures` list** — remove the `execution-profile-selection.md`
   bullet (its only call site, Step 0a, is deleted). Keep the
   `satisfaction-feedback.md` bullet.

5. **Scan for stray `{{` / `{%`** outside Jinja directives; wrap any hits in
   `{% raw %}…{% endraw %}`. Pre-check: `grep -nE '\{\{|\{%' SKILL.md`.

The `[Tier: q,s,e]` step annotations and tier-skip prose stay as runtime
logic — only the `**Profile check:**` block at Step 1c is templated.

## Procedure-file wraps (stay `.md` per §3i file-extension contract)

**`test-plan-proposal.md` Step 5b — `qa_mode` (enum, `elif` chain):**
```jinja
{# ---------- qa_mode ---------- #}{% if profile.qa_mode is defined and profile.qa_mode == "create_task" %}
- Display: "Profile '{{ profile.name }}': qa_mode=create_task"
- Proceed to Step 6 (create follow-up test task).
{% elif profile.qa_mode is defined and profile.qa_mode == "implement" %}{# qa_mode: implement #}
- Display: "Profile '{{ profile.name }}': qa_mode=implement"
- Implement the proposed tests, commit them, then proceed to Step 7.
{% elif profile.qa_mode is defined and profile.qa_mode == "plan_only" %}{# qa_mode: plan_only #}
- Display: "Profile '{{ profile.name }}': qa_mode=plan_only"
- Write the test plan to `aiplans/qa_t<task_id>.md` and proceed to Step 7.
{% else %}{# qa_mode: "ask", unset, or empty — interactive #}
Use `AskUserQuestion`:
... (existing 4-option block + the "If ..." action lines)
{% endif %}{# ---------- end qa_mode ---------- #}
```
(`qa_mode == "ask"` correctly falls into the `{% else %}` interactive arm.)

**`test-execution.md` Step 4a — `qa_run_tests` (bool, one-armed):**
```jinja
{# ---------- qa_run_tests ---------- #}{% if profile.qa_run_tests is defined and not profile.qa_run_tests %}
**Profile '{{ profile.name }}': test execution disabled.** Skip this entire step (4a–4e) and proceed to Step 5.
{% endif %}{# ---------- end qa_run_tests ---------- #}
```
One-armed (no `{% else %}`): when the key is unset/true the block renders
empty and 4a continues normally. Exact blank-line placement tuned against
the golden diff during implementation.

**`task-selection.md` Step 1a — `skip_task_confirmation` (bool, two-armed):**
```jinja
{# ---------- skip_task_confirmation ---------- #}{% if profile.skip_task_confirmation is defined and profile.skip_task_confirmation %}
- Display: "Profile '{{ profile.name }}': auto-confirming task selection"
- Skip confirmation and proceed
{% else %}{# skip_task_confirmation: when false / unset #}
Use `AskUserQuestion`:
- Question: "Run QA analysis on this task? Summary: <brief summary>"
- Header: "Confirm task"
- Options: "Yes, proceed" / "No, select different task"
{% endif %}{# ---------- end skip_task_confirmation ---------- #}
```

**Cleanup in all 3 procedure files:** remove the now-stale
`` - `active_profile` — loaded execution profile (or null) `` line from each
file's "Input:" section (profile is baked in at render time).

All wraps follow the inline-comment convention from
`aidocs/skill_authoring_conventions.md` (separator on the `{% if %}` line,
inline labels on `{% elif %}`/`{% else %}`/`{% endif %}`, render-neutral).

## Stubs (4 files, canonical bodies §3b–§3d)

Copy from the `aitask-fold` stubs, substituting `aitask-fold`→`aitask-qa`,
resolver key `fold`→`qa`, and the description to
`Run QA analysis on any task — analyze changes, discover test gaps, run tests, and create follow-up test tasks`:
- `.claude/skills/aitask-qa/SKILL.md` ← Claude stub (`--agent claude`)
- `.agents/skills/aitask-qa/SKILL.md` ← Codex stub (`--agent codex`)
- `.gemini/commands/aitask-qa.toml` ← Gemini stub (`--agent gemini`)
- `.opencode/commands/aitask-qa.md` ← OpenCode stub (`--agent opencode`)

## Test script — `tests/test_skill_render_aitask_qa.sh`

Adapt `tests/test_skill_render_aitask_fold.sh`; add a procedure-golden loop
modelled on `tests/test_skill_render_task_workflow.sh`:

- **Test 1** — 12 entry-point golden diffs (3 profiles × 4 agents).
- **Test 1p** — 9 procedure golden diffs (`task-selection`, `test-execution`,
  `test-plan-proposal` × 3 profiles, claude). Also assert each renders
  byte-identical across all 4 agents (trivially true — no cross-skill refs).
- **Test 2** — profile-conditional sanity, per profile:
  - `qa_tier` else-arm fires (`Select QA analysis depth:`); if-arm absent (`': qa_tier=`).
  - `qa_mode` else-arm fires (`How would you like to proceed with the test plan?`); if-arms absent (`': qa_mode=create_task`, etc.).
  - `qa_run_tests` block empty for all 3 (forbidden: `test execution disabled`).
  - `skip_task_confirmation`: `fast`/`remote` contain `': auto-confirming task selection`; `default` contains `Run QA analysis on this task?`.
- **Test 3** — no Jinja markers leak (`{%`, `{{`) in entry-point or the 3 wrapped procedure files.
- **Test 3b** — §3j forbidden tokens absent (`aitask_scan_profiles.sh`, `Execute the Execution Profile Selection Procedure`, `Select Execution Profile`, `refresh execution profile`) across entry-point + procedure renders.
- **Test 4** — cross-agent ref rewrites via `aitask_skill_render.sh ... --force`: assert `<agent_root>/task-workflow-fast-/satisfaction-feedback.md` appears in each agent's rendered `aitask-qa-fast-/SKILL.md`.
- **Test 5** — 4 stubs contain canonical markers: `aitask_skill_resolve_profile.sh qa` (and NOT `... aitask-qa`), `aitask_skill_render.sh aitask-qa`, `Dispatch via Read-and-follow`, the correct `--agent` literal, and the per-agent rendered-variant path.

## Goldens (21 files)

Generate with the framework Python (`python_resolve.sh::require_ait_python`):
```bash
mkdir -p tests/golden/skills/aitask-qa tests/golden/procs/aitask-qa
for p in default fast remote; do
  for a in claude codex gemini opencode; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/aitask-qa/SKILL.md.j2 \
      aitasks/metadata/profiles/$p.yaml $a \
      > tests/golden/skills/aitask-qa/SKILL-$p-$a.md
  done
  for f in task-selection test-execution test-plan-proposal; do
    "$PYTHON" .aitask-scripts/lib/skill_template.py \
      .claude/skills/aitask-qa/$f.md \
      aitasks/metadata/profiles/$p.yaml claude \
      > tests/golden/procs/aitask-qa/$f-$p.md
  done
done
```
All 21 committed.

## Implementation Steps (execution order)

1. Author `.claude/skills/aitask-qa/SKILL.md.j2` (5 edits above). Smoke-render:
   `$PYTHON .aitask-scripts/lib/skill_template.py .claude/skills/aitask-qa/SKILL.md.j2 aitasks/metadata/profiles/fast.yaml claude | head -40`.
2. Wrap the 3 procedure files (`test-plan-proposal.md`, `test-execution.md`, `task-selection.md`) + remove the stale `active_profile` Input line in each.
3. Write the 4 stubs (overwrite existing per-agent surfaces).
4. Generate the 21 goldens (loop above).
5. Render the full closure for all 4 agents so live dispatch works:
   `for a in claude codex gemini opencode; do ./.aitask-scripts/aitask_skill_render.sh aitask-qa --profile fast --agent "$a" --force; done` (also `default`, `remote`).
6. Write `tests/test_skill_render_aitask_qa.sh`.
7. Run `bash tests/test_skill_render_aitask_qa.sh` and `./.aitask-scripts/aitask_skill_verify.sh` — both MUST be green.
8. Grep stragglers: `grep -rn 'aitask-qa' .claude/skills/aitask-qa/ .agents/skills/aitask-qa/ .gemini/commands/aitask-qa.toml .opencode/commands/aitask-qa.md tests/test_skill_render_aitask_qa.sh`.

## Verification

1. `bash tests/test_skill_render_aitask_qa.sh` — exits 0, all 21 golden diffs empty, branch/forbidden-token/stub assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0 (renders all 4 agents × 3 profiles, walk-checks the qa closure, validates the 4 stubs; template count now includes aitask-qa).
3. Forbidden-token scan on every rendered golden (entry-point + procedure) — clean.
4. Stub-dispatch dry-run (manual, post-merge): `/aitask-qa` reads the stub → renders → Read-and-follows the rendered variant.

## Step 9 (Post-Implementation)

Standard child-task archival. Code commit:
`refactor: Convert aitask-qa to template + stubs (t777_11)`. Plan commit via
`./ait git`. Archive: `./.aitask-scripts/aitask_archive.sh 777_11`. Push via
`./ait git push`. No linked issue. Profile `fast` → no worktree (work on
current branch); the Step 9 merge-approval gate is a no-op.

The 4 stubs cover all 4 agents in this same task — no separate
Codex/Gemini/OpenCode follow-up tasks are needed.

## Out of scope (deferred)

- Statically resolving the `[Tier: q,s,e]` step annotations / tier-skip prose
  from a baked-in `qa_tier` — that is a deeper restructure; this task only
  templates the 4 `**Profile check:**` blocks.
- Touching the 3 marker-free procedure files beyond identity passthrough.

## Notes for sibling tasks

`aitask-qa` is the first conversion with its **own procedure-file closure**.
The pattern: wrap profile checks wherever they live (entry-point *and*
sibling procedures), keep procedures as `.md`, golden the entry-point per
(profile × agent) and each profile-bearing procedure per profile (claude).
Subsequent skills with procedure files (pr-import / revert / pickrem /
pickweb) follow this layout.
