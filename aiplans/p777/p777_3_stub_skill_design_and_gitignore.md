---
Task: t777_3_stub_skill_design_and_gitignore.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_4_aitask_skill_verify_and_precommit.md, aitasks/t777/t777_5_aitask_skillrun_wrapper_dispatcher.md, aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md, aitasks/t777/t777_7_convert_task_workflow_shared_procs.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 15:43
---

# Plan: t777_3 — Stub design + foundational fixes + sibling description patches

This is a **verify-mode** plan. The external plan at `aiplans/p777/p777_3_stub_skill_design_and_gitignore.md` is the prior canonical, but it is superseded by this refinement because verification uncovered four foundational issues that block the rest of t777 unless fixed.

## Context

t777_3 is the design checkpoint of the t777 redesign. Verification surfaced that the original plan assumed a uniform per-agent skill-discovery model that does not match reality: only Claude auto-discovers skills, while Gemini and OpenCode auto-discover **commands** (which wrap skills). The original plan also has a broken gitignore strategy and a stub/default-render path collision.

t777_3's refined scope therefore covers (a) the foundational fixes to the t777_1/t777_2 helpers, (b) the canonical stub design doc that lives at `.claude/skills/task-workflow/stub-skill-pattern.md`, and (c) in-place patches to the descriptions of sibling tasks t777_4, t777_5, t777_6, t777_8..15, t777_17, t777_18, t777_20 so each child enters its own planning phase with a correct starting point. Per [[feedback_plan_split_in_scope_children]], surfacing these patches as a single in-scope deliverable is preferred to deferring them.

### Verification Findings (2026-05-17)

1. **Original gitignore strategy is broken.** `.claude/skills/*-*/` would hide all 26 authoring dirs because every skill name in the repo contains a hyphen. The `task-workflow → task_workflow` rename was a partial mitigation that did not address the root cause.

2. **Stub/default-render path collision in `agent_skill_dir`.** `agent_skills_paths.sh:30-39` returns the no-suffix path for both "no profile" and `default` profile. A render call with profile=default would overwrite the stub at the same path, violating [[feedback_skills_reread_during_execution]].

3. **Per-agent slash-dispatch validation is unnecessary.** Read-and-follow (already used pervasively in `task-workflow/SKILL.md → planning.md`, `execution-profile-selection.md`, etc.) is universally supported across all four agents.

4. **Skills-vs-commands per-agent discovery model differs.** Only Claude auto-discovers `.claude/skills/<skill>/SKILL.md` as a slash command. Gemini and OpenCode auto-discover `.gemini/commands/*.toml` and `.opencode/commands/*.md` respectively; their command wrappers today statically `@`-include `.claude/skills/<skill>/SKILL.md`. Codex has no slash commands; the user prompts pull in `.agents/skills/<skill>/SKILL.md` by instruction. The original t777 child plans (t777_6, t777_8..15) all assumed stubs at `.{gemini,opencode}/skills/<skill>/SKILL.md` — paths the agents never see.

### Design Decisions

**D1 — Stub-dispatch = Read-and-follow.** Stubs instruct the agent to Read the per-agent rendered SKILL.md and follow it. No slash-dispatch, no per-agent validation matrix.

**D2 — Rendered dirs always have a trailing hyphen.** `agent_skill_dir <agent> <skill> <profile>` returns `<root>/<skill>-<profile>-` for any non-empty profile (including `default`). The no-suffix path is reserved exclusively for the static stub. Examples:
- `agent_skill_dir claude aitask-pick fast`    → `.claude/skills/aitask-pick-fast-`
- `agent_skill_dir claude aitask-pick default` → `.claude/skills/aitask-pick-default-`
- `agent_skill_dir claude aitask-pick`         → `.claude/skills/aitask-pick`  (stub path; no profile arg)

**D3 — Single-glob gitignore per agent root.** Per [[feedback_recognizable_suffix_over_per_variant_gitignore]]:
```
.claude/skills/*-/
.agents/skills/*-/
.gemini/skills/*-/
.opencode/skills/*-/
```
4 lines total. Never grows. Authoring dirs never end with `-`, so they are safe.

**D4 — Stub lives at each agent's actual entry point** (not at uniform `<agent_root>/skills/<skill>/SKILL.md`):

| Agent | Stub authoring location | Mechanism |
|-------|------------------------|-----------|
| Claude | `.claude/skills/<skill>/SKILL.md` | Replaces current static skill body |
| Gemini | `.gemini/commands/<skill>.toml` `prompt` field | Replaces current `@`-include to Claude SKILL.md |
| OpenCode | `.opencode/commands/<skill>.md` body | Replaces current `@`-include to Claude SKILL.md |
| Codex | `.agents/skills/<skill>/SKILL.md` | Replaces current "Source of Truth" reference body |

Each stub hardcodes its own `--agent <literal>` for the renderer invocation, then Reads-and-follows the rendered variant at `<agent_root>/<skill>-<profile>-/SKILL.md`. The rendered file is NOT expected to be a slash command in Gemini/OpenCode/Codex; in Claude it happens to be auto-discoverable as `/<skill>-<profile>-` but normal flow never uses that — the stub always Reads-and-follows.

**D5 — Stub supports both `--profile <name>` argument override and resolver default.** Stub bash:
```bash
# Parse ARGUMENTS for --profile X; fall through to resolver
profile=$(echo "$ARGUMENTS" | grep -oE -- '--profile [a-z_]+' | awk '{print $2}')
[[ -z "$profile" ]] && profile=$(./.aitask-scripts/aitask_skill_resolve_profile.sh <skill>)
./ait skill render <skill> --profile "$profile" --agent <agent_literal>
# Then: Read <agent_root>/<skill>-<profile>-/SKILL.md and follow it
```
The rendered variant strips the consumed `--profile X` from ARGUMENTS before continuing its own processing.

**D6 — Python TUIs and `ait skillrun` pass `--profile` through ARGUMENTS.** No TUI invokes the rendered slash command directly. They invoke the user-facing slash (`/<skill>`), optionally appending `--profile <name>` to ARGUMENTS. The stub handles the override. `ait skillrun --profile-override <yaml>` writes a tempfile under `aitasks/metadata/profiles/local/<unique>.yaml`, invokes the stub with `--profile <unique>`, deletes the tempfile after the agent process exits.

## Step Order

### Step 1 — Update `agent_skill_dir`

Edit `.aitask-scripts/lib/agent_skills_paths.sh`:

```bash
agent_skill_dir() {
    local agent="$1" skill="$2" profile="${3:-}"
    local root
    root="$(agent_skill_root "$agent")" || return 1
    # Rendered dirs end with a trailing hyphen — recognizable "generated"
    # marker so gitignore is a single `*-/` glob per agent root. The
    # no-profile-arg case returns the no-suffix path, reserved for the
    # committed stub SKILL.md.
    if [[ -n "$profile" ]]; then
        echo "$root/${skill}-${profile}-"
    else
        echo "$root/${skill}"
    fi
}
```

Update header comment block (lines 6-15) to reflect the trailing-hyphen convention and the reversal of t777_1's "default = no suffix" decision.

### Step 2 — Update tests

Edit `tests/test_skill_template.sh` lines 79-82:

```bash
assert_eq "agent_skill_dir claude pick (no profile)"  ".claude/skills/aitask-pick"          "$(agent_skill_dir claude aitask-pick)"
assert_eq "agent_skill_dir claude pick default"       ".claude/skills/aitask-pick-default-" "$(agent_skill_dir claude aitask-pick default)"
assert_eq "agent_skill_dir claude pick fast"          ".claude/skills/aitask-pick-fast-"    "$(agent_skill_dir claude aitask-pick fast)"
assert_eq "agent_skill_dir gemini pick fast"          ".gemini/skills/aitask-pick-fast-"    "$(agent_skill_dir gemini aitask-pick fast)"
```

Run `bash tests/test_skill_template.sh` — confirm 20/20 PASS.

### Step 3 — Author `.claude/skills/task-workflow/stub-skill-pattern.md`

Sections:

#### 3a. Purpose
A stub is profile-agnostic dispatch logic that resolves the active profile, renders the per-(skill,profile,agent) variant, and Reads-and-follows it. Per-agent, the stub lives at the agent's actual entry point — for Claude/Codex this is a `SKILL.md`, for Gemini/OpenCode this is a command-wrapper file. Stubs are committed; rendered variants are gitignored.

#### 3b. Canonical stub body (Claude / Codex — SKILL.md form)

```markdown
---
name: <skill_short_name>
description: <copied from authoring template frontmatter>
---

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse ARGUMENTS for `--profile <name>`. If found,
   use that as `<profile>` and remove the `--profile <name>` pair from
   ARGUMENTS. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./ait skill render <skill_short_name> --profile <profile> --agent <agent_literal>`
   No-op if the per-profile SKILL.md is already up to date.

3. **Dispatch via Read-and-follow.** Read the file at
   `<agent_root>/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this skill, forwarding the (possibly
   stripped) ARGUMENTS unchanged.
```

#### 3c. Canonical stub body (Gemini — command TOML form)

`.gemini/commands/<skill_short_name>.toml`:

```toml
description = "<copied from authoring template frontmatter>"
prompt = """

@.agents/skills/geminicli_planmode_prereqs.md
@.agents/skills/geminicli_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse {{args}} for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>` pair
   from the forwarded args. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./ait skill render <skill_short_name> --profile <profile> --agent gemini`

3. **Dispatch via Read-and-follow.** Read the file at
   `.gemini/skills/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) args unchanged.

Forwarded args: {{args}}
"""
```

(Note: `geminicli_planmode_prereqs.md` and `geminicli_tool_mapping.md` are now `@`-included BEFORE the stub body, mirroring the current command-wrapper pattern. They are not duplicated into the rendered variant.)

#### 3d. Canonical stub body (OpenCode — command MD form)

`.opencode/commands/<skill_short_name>.md`:

```markdown
---
description: <copied from authoring template frontmatter>
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>` pair.
   Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <skill_short_name>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./ait skill render <skill_short_name> --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
```

#### 3e. Why Read-and-follow, not slash-dispatch
Read-and-follow works in all four agents (every agent supports file reads); slash-dispatch from within a skill is unverified for codex/gemini/opencode. Mirrors `task-workflow/SKILL.md → planning.md` idiom already used pervasively.

#### 3f. Stub authoring conventions (checklist for t777_6 and t777_8..15)
- Stub frontmatter `name:` (Claude/Codex) and TOML `description=` / OpenCode frontmatter `description:` match the no-suffix slash command (e.g., `aitask-pick`).
- Stubs are committed; rendered variants are gitignored.
- One stub per (skill, agent surface) — 4 stubs per skill total: 1 Claude SKILL.md, 1 Codex SKILL.md, 1 Gemini command TOML, 1 OpenCode command MD.
- Stub body is profile-agnostic — it never embeds profile-specific content.
- Stub MUST NOT modify state beyond the resolve + render bash calls.
- Authoring dir names MUST NOT end with `-` — load-bearing for the gitignore convention.

#### 3g. Per-agent surface table (canonical reference)

| Agent | Stub at | `--agent` literal | Rendered variant at |
|-------|---------|-------------------|--------------------|
| Claude | `.claude/skills/<skill>/SKILL.md` | `claude` | `.claude/skills/<skill>-<profile>-/SKILL.md` (auto-discovered as `/<skill>-<profile>-` but unused) |
| Codex | `.agents/skills/<skill>/SKILL.md` | `codex` | `.agents/skills/<skill>-<profile>-/SKILL.md` |
| Gemini | `.gemini/commands/<skill>.toml` `prompt` field | `gemini` | `.gemini/skills/<skill>-<profile>-/SKILL.md` (not slash-discoverable; reached via stub Read) |
| OpenCode | `.opencode/commands/<skill>.md` body | `opencode` | `.opencode/skills/<skill>-<profile>-/SKILL.md` (not slash-discoverable; reached via stub Read) |

### Step 4 — Update `.gitignore`

Append:

```
# Per-profile rendered skill variants (on-demand, not committed)
# Convention: rendered dirs end with a trailing hyphen. Authoring dirs
# never end with a hyphen, so they are safe.
.claude/skills/*-/
.agents/skills/*-/
.gemini/skills/*-/
.opencode/skills/*-/
```

### Step 5 — Authoring-dir audit (one-shot check)

Run `ls .claude/skills/ .agents/skills/ .gemini/skills/ .opencode/skills/ 2>/dev/null | grep -- '-$' | head` — expect zero results. Confirms no existing authoring dir ends with `-`.

### Step 6 — Patch sibling task descriptions

Update the following sibling task `.md` files in `aitasks/t777/` to reflect the corrected architecture. Each patch keeps the original section structure; the wording specifies the new behavior. Commit all patches together via `./ait git`.

#### 6a. Patch `aitasks/t777/t777_4_aitask_skill_verify_and_precommit.md`
Update "Key Files to Modify" and "Implementation Plan" sections to reflect that the verifier scans BOTH skill files AND command files for stub-pattern compliance:
- For Claude/Codex stubs: scan `<agent_skills_root>/<skill>/SKILL.md` (unchanged).
- For Gemini stubs: scan `.gemini/commands/<skill>.toml` `prompt` field.
- For OpenCode stubs: scan `.opencode/commands/<skill>.md` body.
- Render check: render each `.j2` against `default.yaml` for each agent into the trailing-hyphen path (unchanged in spirit; path naming now reflects D2).

#### 6b. Patch `aitasks/t777/t777_5_aitask_skillrun_wrapper_dispatcher.md`
- Drop the `/${skill}-${profile} ${args}` launch form. The wrapper instead invokes the user-facing slash form `/<skill> --profile <profile> <args>` (Claude/Gemini/OpenCode) and lets the stub handle the override. For Codex (no slash commands) the wrapper writes a one-shot instruction prefix and launches Codex.
- `--profile-override <yaml>` mechanism: write a tempfile under `aitasks/metadata/profiles/local/<unique>.yaml` (auto-discovered by `aitask_scan_profiles.sh`), invoke the stub with `--profile <unique>`, register an EXIT trap to delete the tempfile after the agent process exits.

#### 6c. Patch `aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md`
- "Key Files to Modify": correct the per-agent stub paths to:
  - `.claude/skills/aitask-pick/SKILL.md` (Claude stub)
  - `.agents/skills/aitask-pick/SKILL.md` (Codex stub)
  - `.gemini/commands/aitask-pick.toml` (Gemini stub — `prompt` field)
  - `.opencode/commands/aitask-pick.md` (OpenCode stub — body)
- Remove the `.gemini/skills/aitask-pick/SKILL.md` and `.opencode/skills/aitask-pick/SKILL.md` entries (these are not entry points for those agents).
- Add: "Reuses the stub bodies from `task-workflow/stub-skill-pattern.md` (Steps 3b–3d)."

#### 6d. Patch `aitasks/t777/t777_8_convert_aitask_explore.md` through `aitasks/t777/t777_15_convert_aitask_pickweb.md` (8 files)
Apply the same per-agent stub-path correction as t777_6 (6c above), substituting the skill name. Concretely:
- t777_8 (aitask-explore), t777_9 (aitask-review), t777_10 (aitask-fold), t777_11 (aitask-qa), t777_12 (aitask-pr-import), t777_13 (aitask-revert), t777_14 (aitask-pickrem), t777_15 (aitask-pickweb)
- Same 4-entry "Key Files to Modify" list, substituting `aitask-<skill>` in the paths.

#### 6e. Patch `aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md`
Add a clarification: the per-run editor passes the chosen profile through ARGUMENTS as `--profile <name>` rather than rendering a custom slash command. The stub honors the override. No changes to the rendered-slash-command naming are needed in the AgentCommandScreen launch path.

#### 6f. Patch `aitasks/t777/t777_18_docs_update_claudemd_and_website.md`
Update the documentation deliverable to describe the per-agent stub locations (D4 table from this plan), the trailing-hyphen rendered-dir convention, and the `--profile <name>` argument override.

#### 6g. Patch `aitasks/t777/t777_20_profile_modification_invalidation.md`
- Update the `find ... -name "*-${profile}"` glob in `aitask_skill_invalidate.sh` snippet to `*-${profile}-` (trailing hyphen).
- Update the "Pitfalls" section: the trailing-hyphen convention eliminates the original concern about accidentally matching authoring directories.

#### 6h. Commit
Commit all sibling-description patches together via `./ait git add aitasks/t777/ && ./ait git commit -m "ait: Patch t777 sibling descriptions per t777_3 design (t777_3)"`. Keep this commit separate from the code-changes commit.

### Step 7 — Final Implementation Notes
Add to the plan file's "Final Implementation Notes" (loud, prominent):
- Reversal of t777_1's `agent_skill_dir` default-suffix convention.
- Trailing-hyphen convention for rendered dirs (binding for all later children).
- Per-agent stub-surface table (D4).
- `--profile <name>` ARGUMENTS override convention (D5).

## Critical Files

**Modify (foundational):**
- `.aitask-scripts/lib/agent_skills_paths.sh` — `agent_skill_dir` body and header comment
- `tests/test_skill_template.sh` — 3 assertion updates (lines 80-82)
- `.gitignore` — append 5 lines

**Create (foundational):**
- `.claude/skills/task-workflow/stub-skill-pattern.md` — canonical stub design doc

**Modify (sibling-description patches, ~9 files):**
- `aitasks/t777/t777_4_aitask_skill_verify_and_precommit.md`
- `aitasks/t777/t777_5_aitask_skillrun_wrapper_dispatcher.md`
- `aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md`
- `aitasks/t777/t777_8_convert_aitask_explore.md`
- `aitasks/t777/t777_9_convert_aitask_review.md`
- `aitasks/t777/t777_10_convert_aitask_fold.md`
- `aitasks/t777/t777_11_convert_aitask_qa.md`
- `aitasks/t777/t777_12_convert_aitask_pr_import.md`
- `aitasks/t777/t777_13_convert_aitask_revert.md`
- `aitasks/t777/t777_14_convert_aitask_pickrem.md`
- `aitasks/t777/t777_15_convert_aitask_pickweb.md`
- `aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md`
- `aitasks/t777/t777_18_docs_update_claudemd_and_website.md`
- `aitasks/t777/t777_20_profile_modification_invalidation.md`

**NOT in scope (deferred):**
- Per-agent porting of `stub-skill-pattern.md` to `.agents/skills/task-workflow/` etc. (Claude-first per CLAUDE.md).
- The `.j2` auto-discovery validation (t777_6 Step 1).
- Pre-commit hook for `ait skill verify` (t777_4).
- Actual stub authoring per skill (t777_6 pilot; t777_8..15 for the rest).
- Whitelist touchpoints — no new invokable helper is added in t777_3.
- Patching `aitasks/t777/t777_7_convert_task_workflow_shared_procs.md` — `task-workflow` is `user-invocable: false` (no slash command, no stub at any agent's entry point); its content is reached only via `{% include %}` and `Read` from other skills. The trailing-hyphen convention still applies to `task-workflow-<profile>-/` rendered dirs; t777_7's existing plan handles this correctly once Step 1 of t777_3 lands.

## Pitfalls

- **Reverses t777_1's `agent_skill_dir` default convention.** Document loudly in Final Implementation Notes so t777_5+ planners read the updated helper + this plan's design doc as canonical.
- **Slash command trailing hyphen is unusual.** `/aitask-pick-fast-` is technically discoverable in Claude but the stub Read-and-follow path never invokes it. Mostly invisible to end users.
- **`.gemini/skills/` is empty today.** The per-agent gemini rendered dirs do not exist; they are created on-demand by `ait skill render`. Stubs for Gemini live in `.gemini/commands/`, NOT in `.gemini/skills/`.
- **Sibling-description patches must commit via `./ait git`** per CLAUDE.md ("Git Operations on Task/Plan Files"). Two commits total: one for code changes (`agent_skills_paths.sh`, `test_skill_template.sh`, `.gitignore`, `stub-skill-pattern.md`) via `git`; one for sibling-description patches via `./ait git`.
- **Trailing-hyphen audit is load-bearing.** Future skill renames or new authoring skills MUST NOT end with `-`. Documented in stub-skill-pattern.md §3f as a hard rule.

## Verification

1. **`agent_skill_dir` behavior.**
   ```bash
   source .aitask-scripts/lib/agent_skills_paths.sh
   agent_skill_dir claude aitask-pick           # → .claude/skills/aitask-pick
   agent_skill_dir claude aitask-pick default   # → .claude/skills/aitask-pick-default-
   agent_skill_dir claude aitask-pick fast      # → .claude/skills/aitask-pick-fast-
   agent_skill_dir gemini aitask-pick fast      # → .gemini/skills/aitask-pick-fast-
   ```

2. **Test suite.** `bash tests/test_skill_template.sh` — 20/20 PASS.

3. **Gitignore matrix.**
   ```bash
   # Ignored:
   git check-ignore -v .claude/skills/aitask-pick-fast-/SKILL.md
   git check-ignore -v .claude/skills/aitask-pick-default-/SKILL.md
   git check-ignore -v .agents/skills/aitask-pick-fast-/SKILL.md
   git check-ignore -v .opencode/skills/task-workflow-fast-/SKILL.md

   # NOT ignored (exit 1 expected):
   git check-ignore -v .claude/skills/aitask-pick/SKILL.md
   git check-ignore -v .claude/skills/task-workflow/SKILL.md
   git check-ignore -v .claude/skills/user-file-select/SKILL.md
   git check-ignore -v .claude/skills/ait-git/SKILL.md
   ```

4. **Authoring-dir audit.** `ls .claude/skills/ .agents/skills/ .gemini/skills/ .opencode/skills/ 2>/dev/null | grep -- '-$' | head` — zero matches.

5. **shellcheck.** `shellcheck -x .aitask-scripts/lib/agent_skills_paths.sh` — clean.

6. **Stub document.** `.claude/skills/task-workflow/stub-skill-pattern.md` exists and contains all 7 subsections (3a–3g).

7. **Sibling-description patches.** `git log --stat --oneline -1` on the `./ait git` commit shows ~9 patched files. Open one (e.g., `aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md`) and confirm the Gemini stub now points to `.gemini/commands/aitask-pick.toml`, not `.gemini/skills/aitask-pick/SKILL.md`.

## Step 9 (Post-Implementation)

Standard child-task archival via `./.aitask-scripts/aitask_archive.sh 777_3`. Final Implementation Notes (in the archived plan) MUST loudly document:
- Reversal of t777_1's default-suffix convention.
- Trailing-hyphen convention for rendered dirs.
- D4 per-agent stub-surface table.
- D5 `--profile <name>` argument-override convention.
- D6 Python TUI / `ait skillrun` invocation convention (pass `--profile` through ARGUMENTS; never invoke rendered slash command directly).

## Final Implementation Notes

- **Actual work done:**
  - Foundational code changes (committed via plain `git`):
    - `.aitask-scripts/lib/agent_skills_paths.sh` — `agent_skill_dir` body changed to always append the profile suffix AND a trailing hyphen when a non-empty profile is given. Header comment block expanded with the trailing-hyphen rationale and explicit notice that this REVERSES t777_1's "default = no suffix" convention.
    - `tests/test_skill_template.sh` — 3 assertion updates (default and fast and gemini cases) for the new trailing-hyphen paths. 20/20 PASS.
    - `tests/test_skill_render.sh` — 6 path updates across test cases 1 (`$SK1-fast-/`), 4 (`$SK1-${SCRATCH_PROFILE_NAME}-/`), 6 (`$SK_A-fast-/` + `$SK_B-fast-/`), 7 (within-skill include target `$SK_S-fast-/` + spurious-dir check `_partial-fast-`), 8 (`$SK_MD-fast-/`). 32/32 PASS.
    - `.gitignore` — appended 5 lines (1 comment header + 4 trailing-hyphen globs).
    - `.claude/skills/task-workflow/stub-skill-pattern.md` — new canonical design doc with 8 subsections (3a Purpose, 3b Claude/Codex SKILL.md form, 3c Gemini TOML form, 3d OpenCode MD form, 3e Why Read-and-follow not slash-dispatch, 3f Stub authoring conventions, 3g Per-agent surface table, 3h Argument forwarding contract).
  - Sibling task description patches (captured by the auto-commit-before-sync hook into commit `522fead6`, message "ait: Auto-commit task changes before sync"):
    - t777_3 description (this task's own description; minor edits picked up by the auto-commit).
    - t777_4 — verifier scans Claude/Codex SKILL.md AND Gemini command TOML AND OpenCode command MD; pre-commit hook glob expanded to include `.gemini/commands/` and `.opencode/commands/`.
    - t777_5 — wrapper invokes user-facing `/<skill> --profile <profile> <args>` (not `/<skill>-<profile>-`); `--profile-override` writes to `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` with EXIT-trap cleanup.
    - t777_6 — pilot's per-agent stub paths corrected (4 surfaces, with Gemini and OpenCode stubs in command files, not skill files); Verification Steps updated for trailing-hyphen rendered paths and `--profile <name>` override test.
    - t777_8..15 — uniform patch via Python script (8 conversion tasks): per-agent surface correction, trailing-hyphen rendered paths, frontmatter `name: aitask-<X>-{{ profile.name }}-`.
    - t777_17 — per-run editor writes override under `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` (NOT /tmp); ARGUMENTS-based override convention reinforced.
    - t777_18 — docs section expanded with per-agent surface table, trailing-hyphen convention, `--profile <name>` override, authoring-dir-naming rule.
    - t777_20 — `find ... -name "*-<profile>-"` (trailing hyphen); Pitfalls updated.

- **Deviations from plan:** None significant. The plan's Step 6h ("Commit all sibling-description patches together via `./ait git` … `ait: Patch t777 sibling descriptions per t777_3 design (t777_3)`") was preempted by the project's pre-existing auto-commit-before-sync hook, which produced commit `522fead6` with the generic message "Auto-commit task changes before sync". The diff itself is fully correct; only the commit message wording differs. Not amending (per project convention — no force-push / no destructive ops).

- **Issues encountered:**
  - `tests/test_skill_render.sh` had 6 path references that needed updating from `<skill>-<profile>/` to `<skill>-<profile>-/`. Initial run after the helper update produced 3 FAILs, which surfaced these stale assertions; updated each in turn and re-ran to 32/32 PASS. The within-skill-include spurious-dir check at line 226 also needed updating (`_partial-fast-` instead of `_partial-fast`) — easy to miss because it's a negative assertion ("dir should NOT exist"), so a stale name would silently pass for the wrong reason.
  - Test framework leaks scratch skill dirs (`_t777_2_test_basic-fast-`, etc.) under `.claude/skills/` during test runs — Claude auto-discovers them via the SKILL.md scan even though they're gitignored. Cleaned manually after each run. NOT a regression of t777_3 (the leak predates this change). Flagged as an upstream defect below.

- **Key decisions:**
  - **Trailing hyphen for rendered dirs (D2).** User explicitly preferred a single-glob gitignore over per-profile entries ("per profile suffix gitignore require a lot of mantainance"). The trailing-hyphen marker is the simplest cross-agent rendering of "this is generated content" that avoids per-profile maintenance and avoids touching the authoring-dir naming.
  - **`agent_skill_dir` default-suffix reversal.** Reverses t777_1's "Notes for sibling tasks": "Resolver returns 'default' as a literal string when nothing else applies — t777_5+ should treat that as 'use the unmodified Claude authoring template' (path agent_skill_dir <agent> <skill> with no profile suffix)." That t777_1 decision was incompatible with the stub model (the stub at the no-suffix path would be overwritten by every default-profile render). t777_3 reserves the no-suffix path exclusively for the committed stub.
  - **Read-and-follow over slash-dispatch (D1).** Avoids the 4-agent validation matrix and the fallback design. Mirrors `task-workflow/SKILL.md → planning.md` idiom already in production. Slash-dispatch may be revisited as an optimization in a separate task once validated.
  - **Per-agent stub surfaces (D4).** Stubs at `.gemini/commands/<skill>.toml` `prompt` field and `.opencode/commands/<skill>.md` body (NOT under `<agent_root>/skills/`). Gemini and OpenCode never auto-discover skills — they discover commands; the command wrappers ARE the stubs after t777_6+ conversions land.
  - **`--profile <name>` ARGUMENTS override + `profiles/local/_skillrun_*.yaml` for per-run overrides (D5/D6).** Single mechanism for non-default profile selection at invocation time. Python TUIs and `ait skillrun` append `--profile <name>` to forwarded args; stub parses, strips, dispatches. Per-run override (AgentCommandScreen edit) writes a tempfile under the auto-discovered `profiles/local/` dir and references it by name through the same `--profile` channel.
  - **Sibling-patch scope.** All 14 sibling task descriptions patched in t777_3 per [[feedback_plan_split_in_scope_children]]. Avoids the cost of every sibling's verify-mode planning re-deriving the t777_3 design.

- **Upstream defects identified:**
  - `tests/test_skill_render.sh:148` — EXIT trap `cleanup_with_profile` does not remove the scratch skill dirs (`_t777_2_test_basic-fast-`, `_t777_2_test_basic-_t777_2_test_profile-`, etc.) under `.claude/skills/`. After test run, these dirs are left on disk and get auto-discovered by Claude Code as skills (visible in the skills list). Pre-existed t777_3. Recommended fix: extend `cleanup()` to `rm -rf .claude/skills/${TEST_SKILL_PREFIX}*` in addition to the existing scratch-profile YAML cleanup.

- **Notes for sibling tasks:**
  - **`agent_skill_dir` contract update (binding for t777_4, t777_5, t777_6, t777_8..15, t777_17, t777_20):** Calling `agent_skill_dir <agent> <skill> default` now returns `<root>/<skill>-default-` (trailing hyphen), not `<root>/<skill>`. Calling `agent_skill_dir <agent> <skill>` (no profile arg) is the stub path; this remains `<root>/<skill>`. Subsequent children must read `lib/agent_skills_paths.sh` + this plan's design doc as canonical; do NOT consult t777_1's archived plan for the default-profile convention.
  - **`stub-skill-pattern.md` is the single source of truth** for stub authoring. t777_6 (pilot) reads §3b–§3d for the 4 canonical bodies. t777_8..15 follow the same. t777_4 verifier scans the 4 surfaces from §3g.
  - **Trailing-hyphen audit (load-bearing rule):** `ls .claude/skills/ .agents/skills/ .gemini/skills/ .opencode/skills/ 2>/dev/null | grep -- '-$'` MUST return empty after every change that touches skill dir names. Future renames or new authoring skills MUST NOT end with `-`. Documented in `stub-skill-pattern.md` §3f.
  - **Gitignore is `*-/` per agent root, never `*-<profile>/`** per the user's explicit preference. New profiles do NOT require gitignore updates.
  - **`--profile <name>` ARGUMENTS forwarding** is the SOLE mechanism for non-default profile selection at invocation time. No TUI, no wrapper, no command should construct or invoke `/<skill>-<profile>-` directly. The rendered slash command is technically auto-discoverable in Claude only; never rely on it.
  - **Per-run override YAMLs live under `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml`** so `aitask_scan_profiles.sh` picks them up via the existing `local/*.yaml` resolution. NOT under `/tmp/`. t777_5 and t777_17 must use this path.
