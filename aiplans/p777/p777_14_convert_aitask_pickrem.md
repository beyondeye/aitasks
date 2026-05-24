---
Task: t777_14_convert_aitask_pickrem.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_27_recover_runtime_skills_and_parity_tests.md, aitasks/t777/t777_28_dedup_template_branches_common_proc_and_macros.md
Archived Sibling Plans: aiplans/archived/p777/p777_10_convert_aitask_fold.md, aiplans/archived/p777/p777_11_convert_aitask_qa.md, aiplans/archived/p777/p777_12_convert_aitask_pr_import.md, aiplans/archived/p777/p777_13_convert_aitask_revert.md, aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_23_swap_task_workflown_to_task_workflow.md, aiplans/archived/p777/p777_25_refactor_stubs_direct_helper_paths.md, aiplans/archived/p777/p777_26_template_completeness_and_resolver_key.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_6_convert_aitask_pick_template_and_stubs.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md, aiplans/archived/p777/p777_8_convert_aitask_explore.md, aiplans/archived/p777/p777_9_convert_aitask_review.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-24 17:40
---

# Plan: t777_14 — Convert `aitask-pickrem` to template + **pre-rendered**, committed variants

## Context

`aitask-pickrem` runs in headless environments (Claude Code Web) where `ait setup` has NOT been run by default — confirmed by the `aitask_init_data.sh:19` header. The framework venv with `minijinja>=2.0` lives only after `ait setup`; the system Python in those envs has no `minijinja`. Therefore the canonical stub pattern (§3b "stub calls `aitask_skill_render.sh`") **cannot work for pickrem** — the render command would fail at import time.

Verified mechanics:
- `aitask_setup.sh:574,655` installs `minijinja>=2.0,<3` only inside `$VENV_DIR` / `$PYPY_VENV_DIR`.
- `aitask_skill_render.sh:108-112` delegates to `lib/skill_template.py walk-write` which `import minijinja` at module load.
- The "no-op if fresh" check is performed inside `walk-write` — i.e., **after** minijinja import. Pre-committing renders alone does not save the call.

**Chosen approach (user decision):** templatize pickrem AND commit the pre-rendered variants for the **`remote` profile only** (it is the only profile marked for headless execution today). The 4 pickrem stubs use a **conditional Read pattern**: if a committed pre-rendered variant for the resolved profile exists, Read it directly (no minijinja needed); otherwise fall through to the canonical render step (works locally where `ait setup` has run).

This is a pickrem-specific divergence from the canonical §3b body. It is scoped exactly to skills that must run in environments without `ait setup`: pickrem now, pickweb (t777_15) later. All other converted skills (aitask-pick/-explore/-review/-fold/-qa/-pr-import/-revert) keep the canonical pattern unchanged — they run on operator laptops where `ait setup` is a precondition.

**Future-extension hook:** if more remote-mode profiles are added later (e.g., team-specific headless variants), they can join the pre-render set the same way `remote` does. A marker field on profile YAML (e.g., `headless: true`) could automate discovery — deferred as a follow-up, not in t777_14 scope.

## Critical Files

**Created / replaced (5 framework files — templating):**
- `.claude/skills/aitask-pickrem/SKILL.md.j2` *(new)* — entry-point template
- `.claude/skills/aitask-pickrem/SKILL.md` *(replace — Claude stub, **divergent body** — no render step)*
- `.agents/skills/aitask-pickrem/SKILL.md` *(replace — Codex stub, divergent)*
- `.gemini/commands/aitask-pickrem.toml` *(replace — Gemini stub, divergent)*
- `.opencode/commands/aitask-pickrem.md` *(replace — OpenCode stub, divergent)*

**Pre-rendered committed variants (4 files = remote profile × 4 agents — new):**
- `.claude/skills/aitask-pickrem-remote-/SKILL.md`
- `.agents/skills/aitask-pickrem-remote-/SKILL.md`
- `.gemini/skills/aitask-pickrem-remote-/SKILL.md`
- `.opencode/skills/aitask-pickrem-remote-/SKILL.md`

Plus the **transitive procedure files** that pickrem's closure pulls in *for the remote profile only*: `task-workflow-remote-/agent-attribution.md`, `task-workflow-remote-/planning.md`, `task-workflow-remote-/code-agent-commit-attribution.md` (and anything they transitively pull in) — under each of the 4 agent roots. The dep-walker handles discovery — the implementation step "render the closure and inspect outputs" will enumerate the actual transitive list before committing.

**`.gitignore` update (1 file):**
- `.gitignore` — narrow un-ignore exceptions so only the `remote` pickrem renders are tracked. Bracket the block with TODO markers so t777_29's regenerator can replace it cleanly:
  ```gitignore
  # TODO(t777_29): replace this block with an auto-generated section managed by
  # aitask_regen_gitignore_prerender.sh (scans headless profiles × prerender-marked skills).
  # Pickrem (headless) — pre-rendered REMOTE profile committed so it works
  # in Claude Code Web where `ait setup` has not run. Other profiles still
  # render on demand locally.
  !.claude/skills/aitask-pickrem-remote-/
  !.agents/skills/aitask-pickrem-remote-/
  !.gemini/skills/aitask-pickrem-remote-/
  !.opencode/skills/aitask-pickrem-remote-/
  ```
  Transitive procs land under `task-workflow-remote-/` which is shared across skills; un-ignore only the *specific* proc files the pickrem closure transitively requires (not the whole `task-workflow-remote-/` tree). Concretely: enumerate after the first render and add explicit per-file un-ignores such as `!.claude/skills/task-workflow-remote-/agent-attribution.md`. This keeps other skills' shared task-workflow renders gitignored.

**Tooling update (2 files):**
- `.aitask-scripts/aitask_skill_verify.sh` — add `aitask-pickrem) echo "pickrem" ;;` to `_resolver_key_for()` (line 70 area). Annotate the new case-arm and the `if [[ "$skill" == "aitask-pickrem" ]]` block with `# TODO(t777_29): generalize via prerender marker`.
- `.aitask-scripts/settings/settings_app.py` — extend `save_profile()` (line 683) so that when the saved profile filename is `remote.yaml`, the TUI auto-runs `aitask_skill_render.sh aitask-pickrem --profile remote --agent <a>` for all 4 agents, then `git add`s the rendered outputs. Non-blocking on render failure (display a warning toast; the save itself still completes). Annotate the `if filename == "remote.yaml":` and `for agent in (...): ... "aitask-pickrem" ...` lines with `# TODO(t777_29): generalize — read headless flag from profile, walk prerender-marked skills`.

**Test infrastructure (created):**
- `tests/test_skill_render_aitask_pickrem.sh` *(new)* — adapted from `tests/test_skill_render_aitask_revert.sh`, scoped to the **remote profile only** (pickrem is not intended to run under default/fast). Includes a **committed-variant freshness assertion** that re-renders and diffs against the committed files (regression guard against the .j2 drifting).
- `tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md` *(new — single golden)* — only the remote profile is meaningful for pickrem; no default/fast goldens.

**Read-only references:** `.claude/skills/aitask-pick/SKILL.md.j2` (Jinja-comment convention model), `.claude/skills/aitask-revert/SKILL.md.j2` (recent precedent), `tests/test_skill_render_aitask_revert.sh` (test-script model), `aidocs/stub-skill-pattern.md` (§3b/§3c/§3d for the divergent stub bodies), `aidocs/skill_authoring_conventions.md`.

## Template authoring — `.claude/skills/aitask-pickrem/SKILL.md.j2`

Source: copy current `.claude/skills/aitask-pickrem/SKILL.md`, then apply:

### Edit 1 — Frontmatter

```yaml
---
name: aitask-pickrem-{{ profile.name }}
description: Pick and implement a task in remote/non-interactive mode. All decisions from execution profile - no AskUserQuestion calls.
---
```

### Edit 2 — Delete two Workflow sites (forbidden runtime profile-resolution)

- **Delete `### Step 0 (pre-parse): Extract --profile argument`** (lines 29-37) entirely. Also drop the matching "Optional `--profile <name>`" bullet inside `## Arguments`.
- **Delete `### Step 1: Load Execution Profile`** (lines 56-62) entirely — the call to `execution-profile-selection-auto.md` disappears with it.

First surviving Workflow heading: `### Step 0a: Initialize Data Branch`. Step 2 (Resolve Task File) is the next numeric heading. Numbering gap is intentional (matches aitask-pick precedent of mixed Step 0b/0c/etc.).

### Edit 3 — Cross-reference normalization (dep-walker requirement)

Rewrite relative refs to absolute paths so the dep-walker rewrites them per-agent:
- Line 287: `../task-workflow/agent-attribution.md` → `.claude/skills/task-workflow/agent-attribution.md`
- Line 347: `../task-workflow/code-agent-commit-attribution.md` → `.claude/skills/task-workflow/code-agent-commit-attribution.md`

Line 217 (`planning.md`) is already absolute — leave it.

### Edit 4 — Wrap 9 profile-conditional sites with `is defined and` guards

For every site below, use the **`is defined and`** guard pattern. Multi-value enums use `elif` chains terminating in `{% else %}` (the default branch). Each block uses the Jinja-comment convention from `aidocs/skill_authoring_conventions.md`:
- Separator `{# ---------- <label> ---------- #}` on the same line as `{% if %}`
- Inline `{# <label>: <triggering condition> #}` on each `{% elif %}` / `{% else %}`
- Inline `{# ---------- end <label> ---------- #}` on `{% endif %}`

**Wrap-site list:**

| # | Key | Site (line) | Pattern |
|---|-----|-------------|---------|
| 1 | `done_task_action` | Step 4 Check 1 (113-117) | enum:archive(default)/skip — `{% if … == "skip" %}…{% else %}…archive default…{% endif %}` |
| 2 | `orphan_parent_action` | Step 4 Check 2 (125-128) | same as #1 |
| 3 | `default_email` | Step 5 sub-bullets (140-144) | enum:userconfig(default)/first/literal-email — `{% if … is defined and … == "first" %}…{% elif … is defined and … != "userconfig" %}…use literal …{% else %}…userconfig default …{% endif %}` |
| 4 | `force_unlock_stale` | Step 5 LOCK_FAILED branch (160-167) | bool — `{% if … is defined and … %}force-unlock branch{% else %}error branch (default false){% endif %}` |
| 5 | `plan_preference` | Step 7.0 (193-198) | enum:use_current(default)/verify/create_new |
| 6 | `issue_action` (×3 sites) | Step 10 (392-422) | enum:close_with_notes(default)/comment_only/close_silent/skip — `if … == "comment_only" / elif "close_silent" / elif "skip" / else close_with_notes`. Three sites: `ISSUE:`, `PARENT_ISSUE:` ("Same handling as ISSUE" prose preserved unchanged — no wrap), `FOLDED_ISSUE:` |
| 7 | `abort_plan_action` | Abort step 1 (441-443) | enum:keep(default)/delete |

**Simplifying decisions:**

- `post_plan_action` (line 265-268) has only one value (`start_implementation`) — drop the "Read … from profile" prose; keep the action unconditional. No wrap.
- `review_action` (line 313) has only one value (`commit`) — drop the prose; keep the body unconditional. No wrap.
- `abort_revert_status` (line 445) is interpolated into a single shell command. Use `{{ profile.abort_revert_status | default("Ready") }}` inline instead of an `{% if/else %}` block — verified minijinja 2.x supports `default()` filter.
- `complexity_action` is documented in the schema table but no conditional uses it. No wrap.

### Edit 5 — Pre-save sanity check

`grep -nE '\{\{|\{%' .claude/skills/aitask-pickrem/SKILL.md.j2` — only intended Jinja directives from edits 1, 4 (wraps), and inline `abort_revert_status` interpolation should appear.

## Stubs — **conditional Read** (4 files; keep render fallback for non-remote profiles)

The canonical §3b stub body has 3 steps: resolve profile → render → Read-and-follow. For pickrem, **step 2 (render) becomes conditional**: skip if a committed pre-rendered variant exists; otherwise render and Read. This way the `remote` profile (committed) works without minijinja, and `default` / `fast` (not committed) still work locally where minijinja is available.

### Claude stub (`.claude/skills/aitask-pickrem/SKILL.md`)

```markdown
---
name: aitask-pickrem
description: Pick and implement a task in remote/non-interactive mode. All decisions from execution profile - no AskUserQuestion calls.
---

This is a profile-aware skill stub. Pre-rendered variants for headless
profiles (currently `remote`) are committed to the repo so the skill works in
environments where the rendering toolchain (minijinja) is unavailable —
e.g., Claude Code Web. Other profiles render on demand. Execute these steps
in order, then stop:

1. **Resolve active profile.** Parse ARGUMENTS for `--profile <name>`. If
   found, use that as `<profile>` and remove the `--profile <name>` pair
   from ARGUMENTS. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh pickrem`
   and use the single-line stdout as `<profile>`.

2. **Render only if needed.** If the committed pre-rendered file at
   `.claude/skills/aitask-pickrem-<profile>-/SKILL.md` already exists, skip
   this step. Otherwise run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile <profile> --agent claude`
   (requires `ait setup` to have installed minijinja).

3. **Dispatch via Read-and-follow.** Read the file at
   `.claude/skills/aitask-pickrem-<profile>-/SKILL.md` and execute its
   instructions as if they were this skill, forwarding the (possibly
   stripped) ARGUMENTS unchanged.
```

### Codex stub (`.agents/skills/aitask-pickrem/SKILL.md`)

Identical shape with `--agent codex` in step 2 and `.agents/skills/aitask-pickrem-<profile>-/SKILL.md` in steps 2 and 3.

### Gemini stub (`.gemini/commands/aitask-pickrem.toml`)

```toml
description = "Pick and implement a task in remote/non-interactive mode. All decisions from execution profile - no AskUserQuestion calls."
prompt = """

@.agents/skills/geminicli_planmode_prereqs.md
@.agents/skills/geminicli_tool_mapping.md

This is a profile-aware skill stub. Pre-rendered variants for headless
profiles (currently `remote`) are committed to the repo. Execute these steps
in order, then stop:

1. **Resolve active profile.** Parse {{args}} for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair from the forwarded args. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh pickrem`
   and use the single-line stdout as `<profile>`.

2. **Render only if needed.** If the committed file at
   `.gemini/skills/aitask-pickrem-<profile>-/SKILL.md` already exists, skip
   this step. Otherwise run:
   `./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile <profile> --agent gemini`

3. **Dispatch via Read-and-follow.** Read the file at
   `.gemini/skills/aitask-pickrem-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) args unchanged.

Forwarded args: {{args}}
"""
```

### OpenCode stub (`.opencode/commands/aitask-pickrem.md`)

Same shape as Gemini's, with OpenCode include syntax (`@.opencode/skills/...`) and `$ARGUMENTS` variable.

### Verify-script implications

`aitask_skill_verify.sh` lines 130-145 currently check the stub for `aitask_skill_render.sh <skill>` and `--agent <agent>` literals. Pickrem's conditional-render body STILL contains these substrings (in the "Otherwise run" branch), so the existing checks pass without modification. **The only verify-script change needed is the resolver-key map entry** (`aitask-pickrem → pickrem`). No new "stub kind" abstraction required — the conditional-Read pattern is a superset of the canonical pattern.

**Additional optional assertion:** check that the committed `.<root>/aitask-pickrem-remote-/SKILL.md` file exists. Acceptable to add as a small follow-up check inside the existing verify loop (4 paths to test).

## Tooling update — resolver key + settings TUI auto-render hook

### `.aitask-scripts/aitask_skill_verify.sh`

1. Add `aitask-pickrem) echo "pickrem" ;;` to `_resolver_key_for()`.
2. (Small additional check) For `aitask-pickrem`, after the existing per-stub assertions, verify that the committed pre-rendered remote variant exists at `<root>/aitask-pickrem-remote-/SKILL.md` for each agent root. Failure mode: clear "committed pre-rendered remote variant missing" message. Implementation is a few extra lines guarded by `if [[ "$skill" == "aitask-pickrem" ]]`.

### `.aitask-scripts/settings/settings_app.py` — auto-render hook on profile save

Extend `save_profile(self, filename, data, layer="project")` (line 683). After the existing YAML write:

```python
def save_profile(self, filename: str, data: dict, layer: str = "project"):
    # ... existing YAML write ...
    self._maybe_rerender_pickrem(filename)

def _maybe_rerender_pickrem(self, filename: str) -> None:
    """If filename matches a headless profile (currently `remote.yaml`), re-render
    aitask-pickrem for all 4 agents and stage the outputs. Non-blocking on failure."""
    if filename != "remote.yaml":
        return
    # Guard: skip if pickrem template doesn't exist yet (during early bootstrap or
    # if pickrem hasn't been converted in this repo).
    template_path = Path(".claude/skills/aitask-pickrem/SKILL.md.j2")
    if not template_path.exists():
        return
    rendered_outputs: list[str] = []
    for agent in ("claude", "codex", "gemini", "opencode"):
        proc = subprocess.run(
            ["./.aitask-scripts/aitask_skill_render.sh",
             "aitask-pickrem", "--profile", "remote", "--agent", agent, "--force"],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            # Surface as a non-blocking toast; the YAML save still succeeded.
            self.notify(
                f"Auto-rerender of aitask-pickrem failed for agent={agent}: "
                f"{proc.stderr.strip()[:200]}",
                severity="warning", timeout=8,
            )
            return
        rendered_outputs.extend(self._rendered_paths_for_agent(agent))
    # git add the outputs so they're staged for the user's next commit.
    if rendered_outputs:
        subprocess.run(["git", "add", "--", *rendered_outputs],
                       capture_output=True, text=True)
        self.notify(
            f"Re-rendered aitask-pickrem (remote × 4 agents) and staged "
            f"{len(rendered_outputs)} file(s).",
            severity="information", timeout=5,
        )

def _rendered_paths_for_agent(self, agent: str) -> list[str]:
    root_map = {
        "claude":   ".claude/skills",
        "codex":    ".agents/skills",
        "gemini":   ".gemini/skills",
        "opencode": ".opencode/skills",
    }
    root = Path(root_map[agent]) / "aitask-pickrem-remote-"
    if not root.exists():
        return []
    return [str(p) for p in root.rglob("*.md")]
```

**Coverage:** captures profile edits made via the TUI (the canonical workflow). Direct YAML edits in an external editor (or .j2 edits) bypass this hook and are caught downstream by the verify-script drift test (Test 6) — surfacing as a test failure that the author manually resolves with `aitask_skill_render.sh ... --force`.

**No new infrastructure:** no git hooks, no CI changes, no opt-in/opt-out config. Uses only standard `subprocess.run` and `Path` already imported in settings_app.py.

## `.gitignore` update

Append after existing `*-/` ignore rules:

```gitignore
# Pickrem (headless) — pre-rendered REMOTE profile committed so it works in
# Claude Code Web where `ait setup` has not run. Other pickrem profiles
# (default/fast) still render on demand locally.
!.claude/skills/aitask-pickrem-remote-/
!.agents/skills/aitask-pickrem-remote-/
!.gemini/skills/aitask-pickrem-remote-/
!.opencode/skills/aitask-pickrem-remote-/
```

After the first render, enumerate the transitive `task-workflow-remote-/` procs pickrem pulls in and add explicit per-file un-ignores (e.g., `!.claude/skills/task-workflow-remote-/agent-attribution.md`) — NOT a directory-wide un-ignore, to keep other skills' shared task-workflow renders gitignored.

## Test script — `tests/test_skill_render_aitask_pickrem.sh`

Adapt `tests/test_skill_render_aitask_revert.sh`. Key differences:
- Skill slug `aitask-pickrem`, resolver key `pickrem`.
- **All profile loops collapse to a single profile: `remote`.** pickrem is not intended to run under default/fast — testing those profiles adds no signal. `PROFILES=(remote)` (or drop the loop entirely).
- **Test 1 (golden diff):** single golden `SKILL-remote-claude.md` × claude render.
- **Test 1b (agent invariance):** remote profile only — assert claude/codex/gemini/opencode renders are byte-identical.
- **Test 2 (profile-conditional sanity):** assert the remote-profile rendered body contains the expected branches (e.g., `force_unlock` enabled, `done_task_action: archive` default fires) and does NOT contain the unused enum branches.
- **Test 3 / 3b (no Jinja markers / forbidden tokens):** remote × 4 agents (4 combos), same assertions as siblings.
- **Test 4 (cross-agent ref rewrite):** remote profile, all 4 agents — assert `task-workflow-remote-/SKILL.md` rewrites land in pickrem's rendered output.
- **Test 5 stub-marker assertions:** unchanged from canonical (the conditional-Read body keeps `aitask_skill_render.sh aitask-pickrem` and `--agent <literal>` substrings inside the "Otherwise run" branch).
- **NEW Test 6 — Committed remote-variant freshness:** render `aitask-pickrem --profile remote` for each of the 4 agents via `aitask_skill_render.sh ... --force`; diff the workspace output at `<root>/aitask-pickrem-remote-/SKILL.md` against `git show HEAD:<path>`. Any drift fails (catches "edited .j2 but forgot to re-commit renders"). If needed, copy committed file to a tmpdir before re-render and diff afterwards.
- **NEW Test 7 — Zero-AskUserQuestion assertion** for `remote` profile across all 4 agents: `! grep -q AskUserQuestion <rendered_file>`.
- **NEW Test 8 — Committed remote-variant existence:** simple `[[ -f <path> ]]` check for all 4 agent paths. Catches the case where someone removed the committed files without updating the stub.

## Golden (1 file, claude canonical, remote profile only)

`tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md`. Other profiles (default/fast) are not goldened because pickrem only runs under remote. Generation:

```bash
mkdir -p tests/golden/skills/aitask-pickrem
PYTHON="$HOME/.aitask/venv/bin/python"
"$PYTHON" .aitask-scripts/lib/skill_template.py \
  .claude/skills/aitask-pickrem/SKILL.md.j2 \
  aitasks/metadata/profiles/remote.yaml claude \
  > tests/golden/skills/aitask-pickrem/SKILL-remote-claude.md
```

## Implementation Steps (execution order)

1. Author `.claude/skills/aitask-pickrem/SKILL.md.j2` (edits 1-5). Smoke-render: render under `remote.yaml` and grep for `AskUserQuestion` (must be 0); grep for forbidden tokens (must be empty).
2. Write the 4 conditional-Read stubs.
3. Edit `aitask_skill_verify.sh`: add resolver-key entry; (optional) add committed-variant existence check for pickrem.
4. Render the **remote** closure for all 4 agents (= 4 main outputs + transitive procs):
   ```bash
   for a in claude codex gemini opencode; do
     ./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile remote --agent "$a" --force
   done
   ```
5. Enumerate generated transitive proc paths (`find .claude/skills/task-workflow-remote-/ .agents/skills/task-workflow-remote-/ .gemini/skills/task-workflow-remote-/ .opencode/skills/task-workflow-remote-/ -name '*.md' -newer .claude/skills/aitask-pickrem/SKILL.md.j2`).
6. Update `.gitignore` with un-ignore lines for `aitask-pickrem-remote-/` AND the specific transitive proc files identified in step 5.
7. Generate the single remote-profile golden (claude canonical). No default/fast goldens — pickrem is not run under those profiles.
8. Write `tests/test_skill_render_aitask_pickrem.sh`.
9. Run `bash tests/test_skill_render_aitask_pickrem.sh` AND `./.aitask-scripts/aitask_skill_verify.sh` — both MUST be green.
10. Grep stragglers: `grep -rn 'aitask-pickrem' .claude/skills/aitask-pickrem/ .agents/skills/aitask-pickrem/ .gemini/commands/aitask-pickrem.toml .opencode/commands/aitask-pickrem.md tests/test_skill_render_aitask_pickrem.sh` — confirm intentional only.
11. Render under `remote.yaml` for claude; `grep -c AskUserQuestion` MUST be `0`.

## Verification

1. `bash tests/test_skill_render_aitask_pickrem.sh` exits 0 — all goldens, invariance, profile-branch, forbidden-token, ref-rewrite, stub-marker, freshness, and zero-AskUserQuestion assertions pass.
2. `./.aitask-scripts/aitask_skill_verify.sh` exits 0 — renders all 4 agents × `default.yaml`, walks closure, validates the 4 pickrem stubs via the new `prerendered` stub-kind path.
3. `git status` shows the 4 pickrem `*-remote-/SKILL.md` files staged (plus any transitive procs in `task-workflow-remote-/`).
4. Forbidden-token scan on the remote-profile rendered output × 4 agents — clean (4 forbidden strings × 4 agents = 0 hits).
5. Manual stub-dispatch dry-run (post-commit): `/aitask-pickrem 1` with `remote` profile should read the Claude stub → resolve profile → skip render (file exists) → Read-and-follow the committed pre-rendered file. With `fast` or `default` profile, should fall through to the canonical render step.

## Out of scope (deferred)

- **`aitask-pickweb` (t777_15)** will follow this same "pre-rendered stub" pattern. NOT bundled into this task — the user separately split it as a sibling. When t777_15 lands, both pickrem and pickweb will benefit from the t777_29 generalization (see Follow-up Task Design below).
- General "pre-render all skills and commit renders" mode for the framework — not adopted; this divergence is scoped to the headless-only skills.
- Cleanup of `aitask-scripts/settings/settings_app.py:284-325` (TUI labels referencing pickrem profile fields) — labels still accurate, no touch needed.
- **The `headless: true` profile-flag mechanism and the per-skill pre-render registry** — designed below as Follow-up Task t777_29. Within t777_14 we accept hardcoded references to `"remote.yaml"` and `"aitask-pickrem"` in the three integration sites (TUI hook, `.gitignore`, verify script). Each hardcode is annotated with `# TODO(t777_29):` so the generalization sweep finds them.

---

## Follow-up Task Design — t777_29: Generalize headless-profile / pre-rendered-skill marker mechanism

**Why this is a follow-up, not part of t777_14:** t777_14 has to land the pickrem conversion *and* prove the pre-rendered-commit mechanism works end-to-end. Adding the declarative marker layer in the same task doubles the scope and the surface area for regressions, while only paying off when a second consumer (pickweb t777_15) is converted. Better to ship pickrem with explicit hardcodes (clearly marked), then refactor once two consumers exist.

### Task name (proposed)

`t777_29_headless_profile_marker_and_prerender_registry`

### Goals

1. Replace every hardcoded `"remote.yaml"` / `"remote"` profile check with a lookup against a declarative `headless: true` flag in profile YAML.
2. Replace every hardcoded `"aitask-pickrem"` skill check with a lookup against a declarative pre-render marker on the skill (j2 frontmatter field or central registry).
3. Auto-maintain `.gitignore` un-ignore lines for `(headless profile × pre-render-marked skill × 4 agents)` combinations via a helper script.
4. Make adding a new headless profile (e.g., `headless_team_a.yaml`) or a new pre-render-marked skill (e.g., a third pickweb-style skill) a **pure-data change** — no code edits to settings_app.py, no .gitignore hand-edits, no verify-script changes.

### Component 1 — Profile marker

**Schema addition:** add `headless: true` (boolean, default `false` / absent) to profile YAML.

- `aitasks/metadata/profiles/remote.yaml` → set `headless: true`.
- Future remote-mode profiles set the same flag.

**Helper:** extend `aitask_scan_profiles.sh` with a `--headless` filter mode that emits only profiles where `headless: true`. Single line of `awk` against the existing scan output.

**Settings TUI label/help:** add the field to the profile-edit UI (probably under "Advanced") with description: "When true, this profile's pre-rendered skill outputs are committed to the repo so the skill runs in environments without `ait setup` (e.g., Claude Code Web)."

### Component 2 — Skill marker

**Choice between two designs:**

- **Option 2a (frontmatter marker — preferred):** add an optional Jinja-time-resolvable field to each skill's `SKILL.md.j2` frontmatter, e.g.:
  ```yaml
  ---
  name: aitask-pickrem-{{ profile.name }}
  description: ...
  prerender_for_headless: true
  ---
  ```
  The `prerender_for_headless` field is read by tooling (renderer, verify script, settings TUI) by parsing the j2 frontmatter — does NOT need template evaluation (front-of-file YAML pre-parse). Pro: data lives next to the skill it describes; trivially discoverable. Con: requires tooling to parse j2 frontmatter without rendering.

- **Option 2b (central registry):** add `aitasks/metadata/prerendered_skills.txt` (one skill slug per line). Pro: simple to read from bash. Con: separate from the skill, easy to forget to update.

**Recommendation: 2a.** A small Python helper `aitask_skill_meta.sh --is-prerender-marked <skill>` (or similar) reads the j2 frontmatter via `lib/skill_template.py`'s YAML parser (no Jinja eval).

### Component 3 — Settings TUI generalization

Replace the hardcoded `if filename == "remote.yaml":` in `save_profile` with:

```python
def _maybe_rerender_for_headless(self, filename: str) -> None:
    """If filename is a headless profile, re-render every pre-render-marked
    skill for all 4 agents and stage outputs."""
    profile_name = filename.removesuffix(".yaml")
    if not _profile_has_flag(profile_name, "headless"):
        return
    skills_to_render = _list_prerender_marked_skills()  # scans j2 frontmatter
    for skill in skills_to_render:
        for agent in ("claude", "codex", "gemini", "opencode"):
            subprocess.run([
                "./.aitask-scripts/aitask_skill_render.sh",
                skill, "--profile", profile_name, "--agent", agent, "--force",
            ], ...)
        # stage outputs
```

`_profile_has_flag` and `_list_prerender_marked_skills` are small helpers (parse profile YAML; glob `.claude/skills/*/SKILL.md.j2` and inspect frontmatter).

### Component 4 — `.gitignore` regenerator

**New helper:** `./.aitask-scripts/aitask_regen_gitignore_prerender.sh`

- Reads list of headless profiles (`aitask_scan_profiles.sh --headless`).
- Reads list of pre-render-marked skills (`aitask_skill_meta.sh --list-prerender-marked`).
- Computes the cross product × 4 agent roots.
- Emits a block to `.gitignore` between markers:
  ```gitignore
  # BEGIN AUTO-GENERATED aitasks-prerendered (managed by aitask_regen_gitignore_prerender.sh)
  !.claude/skills/aitask-pickrem-remote-/
  !.agents/skills/aitask-pickrem-remote-/
  ...
  # END AUTO-GENERATED aitasks-prerendered
  ```
- Idempotent: re-running replaces the block in place.
- Called by: `ait setup`, settings TUI on save of any headless-marked profile, and a pre-commit assertion in `aitask_skill_verify.sh` that the block is fresh.

### Component 5 — Transitive proc un-ignore

Pre-render-marked skills' transitive `task-workflow-<headless>-/<proc>.md` files also need un-ignoring (currently handled manually in t777_14). The `aitask_regen_gitignore_prerender.sh` helper performs a closure walk (via the existing dep-walker) for each `(headless profile × marked skill × agent)` triple, collects the transitive proc paths, and emits explicit per-file un-ignore lines. Idempotent.

### Component 6 — Verify-script generalization

Replace `if [[ "$skill" == "aitask-pickrem" ]]` in the verify loop with a check against the skill marker — for every pre-render-marked skill × every headless profile × 4 agents, assert the committed rendered file exists AND matches a fresh render.

### Migration steps (when t777_29 lands)

1. Add `headless: true` to `remote.yaml`.
2. Add `prerender_for_headless: true` to `.claude/skills/aitask-pickrem/SKILL.md.j2` (and pickweb's once t777_15 has shipped).
3. Author `aitask_skill_meta.sh`, `aitask_regen_gitignore_prerender.sh`, and the helper Python.
4. Rewrite the `save_profile` hook in settings_app.py to use the helpers.
5. Rewrite the `.gitignore` block as auto-generated.
6. Rewrite the verify-script branch to use the helpers.
7. Sweep all `# TODO(t777_29):` markers planted in t777_14 and replace with the new lookups.
8. Add tests: `tests/test_headless_profile_marker.sh` covering the cross-product enumeration and the gitignore regenerator's idempotency.

### Out of scope for t777_29

- Allowing pre-rendered commits for non-headless profiles (e.g., committing the `fast` renders for offline use). Possible future extension; keep the marker boolean for now.
- A TUI for adding/removing the `prerender_for_headless` marker on skills (devs edit the j2 frontmatter directly).

### Pre-task seeding for t777_29

When t777_14 is archived, surface this design in the task description by running:

```bash
./.aitask-scripts/aitask_create.sh --batch --parent 777 \
  --name headless_profile_marker_and_prerender_registry \
  --priority medium --effort medium --issue-type refactor \
  --depends t777_14,t777_15 \
  --description "$(cat aiplans/archived/p777/p777_14_*.md | sed -n '/Follow-up Task Design/,/Pre-task seeding/p')"
```

(Exact command tuned to the t777_14 archival step; the description block is the "Follow-up Task Design" section verbatim. Concrete creation can happen in t777_14's Step 8 / Step 8b — but only after pickweb t777_15 also lands, since two consumers is the trigger for generalizing.)

## Step 9 (Post-Implementation)

Standard child-task archival. Profile `fast` → no worktree (work on current branch); the Step 9 merge-approval gate is a no-op. Commits:
- Code commit: `refactor: Convert aitask-pickrem to template + pre-rendered remote variants (t777_14)` — includes 5 framework files, 4 pre-rendered remote SKILL.md files + transitive procs, 2 tooling files (verify script + settings TUI), 1 test file, 1 remote-profile golden, 1 .gitignore.
- Plan commit via `./ait git`: `ait: Update plan for t777_14`.
- Archive: `./.aitask-scripts/aitask_archive.sh 777_14`.
- Push via `./ait git push`.

The 4 stubs cover all 4 agents in this same task — no separate Codex/Gemini/OpenCode follow-up tasks needed.

## Final Implementation Notes

- **Actual work done:** Implementation followed the approved plan verbatim. Authored `.claude/skills/aitask-pickrem/SKILL.md.j2` (462-line render under remote.yaml, down from 507-line source), replaced 4 stub files (Claude/Codex/Gemini/OpenCode) with the conditional-Read pattern, added `aitask-pickrem)` resolver-key entry and committed-variant existence check to `aitask_skill_verify.sh`, hooked `_maybe_rerender_pickrem` into the settings TUI's `_save_profile`, narrowed the `.gitignore` un-ignore to `aitask-pickrem-remote-/` + `task-workflow-remote-/` per agent root, generated the single remote-profile golden, and rendered the closure for 4 agents × remote profile (96 committed files total: 4 pickrem SKILL.md + 88 transitive task-workflow-remote- procs).
- **Deviations from plan:** None of material substance. Minor scope adjustments during implementation:
  - The `.gitignore` un-ignore landed at directory-level (`!<root>/task-workflow-remote-/`) rather than per-file enumeration, because the dep-walker emits 22 transitive procs per agent root for pickrem's closure and per-file un-ignores would balloon the .gitignore. Directory-level un-ignore is also cleaner for the t777_29 generalization (one un-ignore per `(skill, profile)` × agent root rather than per-file).
  - Plan said "pickrem references three task-workflow procs" but the dep-walker pulls in 22 procs transitively (planning.md alone references task-creation-batch.md, contributor-attribution.md, etc.). Committed the full closure.
- **Issues encountered:** None blocking.
  - First smoke render showed 6 `AskUserQuestion` mentions in the rendered output — investigation confirmed all 6 are descriptive prose ("no AskUserQuestion calls", "AskUserQuestion does not work"), not invocations. Test 7 was written to grep for the invocation marker `Use \`AskUserQuestion\`` instead of the bare token.
  - The first `aitask_plan_externalize.sh` call returned `MULTIPLE_CANDIDATES` because an older internal plan file existed alongside the new one — passed `--internal <path>` explicitly to disambiguate.
- **Key decisions:**
  - Used `{% if profile.<key> is defined and ... %}` guards consistently (matches `aitask-pick/SKILL.md.j2:24` precedent). This is what allows `aitask_skill_verify.sh` to render pickrem under `default.yaml` without strict-undefined errors despite `default.yaml` defining only `name` and `description`.
  - Inlined `{{ profile.abort_revert_status | default("Ready") }}` for the single-string `abort_revert_status` interpolation rather than wrapping it in `{% if/else %}` — minijinja 2.x supports `default()` (used elsewhere in the codebase).
  - Dropped the `post_plan_action` and `review_action` "Read … from profile" prose entirely since those keys have a single supported value each. No wrap needed.
  - The conditional-Read stub pattern (`If <committed path> exists, skip render; else render`) is a strict superset of the canonical §3b body — it preserves `aitask_skill_render.sh aitask-pickrem` and `--agent <literal>` substrings in the "Otherwise run" branch, so the existing verify-script grep markers all match without special-casing.
  - Settings TUI hook attached to the App-level `_save_profile` method (line 2502) rather than `ConfigManager.save_profile` (line 447) because the App method has access to `self.notify` for user-facing toasts.
- **Test results:** `bash tests/test_skill_render_aitask_pickrem.sh` → 72/72 pass. `./.aitask-scripts/aitask_skill_verify.sh` → OK (8 templates × 4 agents verified, plus the pickrem-specific committed-variant existence check). Sibling regression `bash tests/test_skill_render_aitask_revert.sh` → 122/122 pass.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t777_15 (`aitask-pickweb`)** can follow this same conditional-Read + committed-remote-variant pattern with three additional considerations: (a) pickweb has stricter sandboxing (no cross-branch ops, stores state in `.aitask-data-updated/`), so its closure may diverge from pickrem's task-workflow refs; (b) the same `.gitignore` un-ignore block can be extended with `aitask-pickweb-remote-/` lines; (c) the same `_maybe_rerender_pickrem` settings hook should be generalized to iterate over a list of headless skills (already TODO-marked for t777_29).
  - **t777_29 (Follow-up: headless marker generalization)** is fully designed in the plan body's "Follow-up Task Design" section. Four `TODO(t777_29):` markers planted at: `aitask_skill_verify.sh` (resolver-key entry + committed-variant block), `.gitignore` (entire un-ignore block), `settings_app.py` (`_maybe_rerender_pickrem` body). Generalization should land after t777_15 ships (two consumers is the trigger).

