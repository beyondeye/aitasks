# Stub Skill / Command Pattern (Canonical Authoring Reference)

This document describes the canonical "stub" pattern that every templated skill in the aitasks framework uses to dispatch to its per-profile rendered variant. Referenced by t777_6 (pilot conversion) and t777_8..t777_15 (other per-skill conversions).

## 3a. Purpose

A **stub** is the small, profile-agnostic dispatch logic that the agent reads when the user invokes a skill (e.g., `/aitask-pick`). It performs three steps:

1. Resolve the active execution profile (via `--profile <name>` argument override OR the resolver default).
2. Render the per-(skill, profile, agent) variant on demand (no-op if already up to date).
3. Read-and-follow the rendered variant — execute its instructions as if they were the skill body.

The stub is committed to git. The rendered variants live in trailing-hyphen directories (e.g., `.claude/skills/aitask-pick-fast-/`) that are gitignored via the single `*-/` glob per agent root.

**Shared-root agents (t834).** When two agents target the same physical root (today: codex + future agy under `.agents/skills/`), the rendered-dir name carries an additional `-<agent>-` segment to avoid collisions: `.agents/skills/aitask-pick-fast-codex-/` and `.agents/skills/aitask-pick-fast-agy-/`. The trailing hyphen is preserved so the `*-/` gitignore glob still works. The "shared root" set is the single source of truth `agent_shared_skills_root` in `.aitask-scripts/lib/agent_skills_paths.sh` (mirror: `AGENT_SHARED_SKILLS_ROOT` in `.aitask-scripts/lib/skill_template.py`). Non-shared agents (claude, opencode) keep the `<skill>-<profile>-/` naming.

**Per-agent, the stub lives at the agent's actual entry point** — not at a uniform path. Claude auto-discovers skill SKILL.md files; Codex loads SKILL.md by instruction reference; OpenCode auto-discovers **command wrappers**, not skills. The stub therefore takes different file shapes per agent (SKILL.md for Claude/Codex; command-wrapper file for OpenCode). See §3g for the canonical mapping.

## 3b. Canonical stub body (Claude / Codex — `SKILL.md` form)

This goes at `.claude/skills/<skill_short_name>/SKILL.md` (Claude) and `.agents/skills/<skill_short_name>/SKILL.md` (Codex). The two files are identical except for the `<agent_literal>` substitution in Step 2.

```markdown
---
name: <skill_short_name>
description: <copied from authoring template frontmatter>
---

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse ARGUMENTS for `--profile <name>`. If
   found, use that as `<profile>` and remove the `--profile <name>` pair
   from ARGUMENTS. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <resolver_key>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./.aitask-scripts/aitask_skill_render.sh <skill_short_name> --profile <profile> --agent <agent_literal>`
   No-op if the per-profile SKILL.md is already up to date.

3. **Dispatch via Read-and-follow.** Read the file at
   `<agent_root>/<rendered_dir>/SKILL.md` and execute its instructions as
   if they were this skill, forwarding the (possibly stripped) ARGUMENTS
   unchanged.
```

Substitutions per stub:
- `<skill_short_name>` — the skill slug, e.g., `aitask-pick` (matches the
  dir name, the `name:` frontmatter, and the slash command).
- `<resolver_key>` — the **task-workflow short name** the rendered body
  uses to look up `userconfig.default_profiles.<key>`. For
  `aitask-pick` this is `pick`. Distinct from
  `<skill_short_name>`. See §3f for the full convention.
- `<agent_literal>` — `claude` for the Claude stub; `codex` for the Codex stub.
- `<agent_root>` — `.claude/skills` for Claude; `.agents/skills` for Codex.
- `<rendered_dir>` — `<skill_short_name>-<profile>-` for non-shared roots
  (Claude). For shared roots (Codex today; +agy in t814) it carries the
  agent segment: `<skill_short_name>-<profile>-<agent_literal>-`. See §3g
  for the per-agent surface table.

## 3d. Canonical stub body (OpenCode — command MD form)

This goes at `.opencode/commands/<skill_short_name>.md`, replacing the current static `@`-include to the Claude SKILL.md.

```markdown
---
description: <copied from authoring template frontmatter>
---

@.opencode/skills/opencode_planmode_prereqs.md
@.opencode/skills/opencode_tool_mapping.md

This is a profile-aware skill stub. Execute these steps in order, then stop:

1. **Resolve active profile.** Parse $ARGUMENTS for `--profile <name>`.
   If found, use that as `<profile>` and remove the `--profile <name>`
   pair. Otherwise run:
   `./.aitask-scripts/aitask_skill_resolve_profile.sh <resolver_key>`
   and use the single-line stdout as `<profile>`.

2. **Render per-profile variant.** Run:
   `./.aitask-scripts/aitask_skill_render.sh <skill_short_name> --profile <profile> --agent opencode`

3. **Dispatch via Read-and-follow.** Read the file at
   `.opencode/skills/<skill_short_name>-<profile>-/SKILL.md` and execute its
   instructions as if they were this command, forwarding the (possibly
   stripped) $ARGUMENTS unchanged.
```

The OpenCode stub hardcodes `--agent opencode` in Step 2.

## 3e. Why Read-and-follow, not slash-dispatch

The stub's Step 3 instructs the agent to **Read** the rendered file and follow it — not to invoke `/<skill>-<profile>-` as a nested slash command.

- Read-and-follow works in **all four agents** (every agent supports file reads). No per-agent validation matrix is required, and no fallback case is needed for agents that cannot programmatically slash-dispatch.
- Read-and-follow mirrors an idiom already used pervasively in the framework, e.g., `task-workflow/SKILL.md` instructing the agent to read `planning.md`, `execution-profile-selection.md`, etc.
- Slash-dispatch from within a SKILL.md is unverified for Codex / Gemini / OpenCode and would require a per-agent fallback that prints a shell-command hint and aborts.

Slash-dispatch may be added as a follow-up optimization in a separate task once empirically validated across all four agents.

## 3f. Stub authoring conventions (checklist for converters)

When converting a skill in t777_6 (pilot) or t777_8..15 (others), each conversion produces **4 stubs** plus 1 authoring template. The checklist:

- **Stub frontmatter `name:` / TOML `description=` / OpenCode frontmatter `description:` match the no-suffix slash command** (e.g., `aitask-pick`, NOT `aitask-pick-fast-`).
- **Stubs are committed to git.** Rendered variants (trailing-hyphen dirs) are gitignored.
- **One stub per (skill, agent surface)** — 3 stubs total per skill:
  1. Claude SKILL.md (per §3b)
  2. Codex SKILL.md (per §3b)
  3. OpenCode command MD (per §3d)
- **Stub body is profile-agnostic** — it never embeds profile-specific content or branches on profile keys. All profile-conditional logic belongs in the authoring template (`.claude/skills/<skill>/SKILL.md.j2`).
- **Stub MUST NOT modify state** beyond the resolve + render bash calls. No git operations, no task-file edits, no lock changes.
- **Authoring dir names MUST NOT end with `-`** — load-bearing for the `*-/` gitignore convention. Verified by the one-shot audit in t777_3 Step 5; future renames or new authoring skills must respect this hard rule.
- **Resolver key uses the task-workflow short name** (`pick`, `explore`, `qa`, `fold`, `review`, `pr-import`, `revert`, …), NOT the full skill slug. The short name MUST match the `skill_name` value that the body passes to `execution-profile-selection.md`, so the stub and the rendered body resolve the same `userconfig.default_profiles.<key>` entry. Without this match, the stub picks one profile and the body silently overrides to another at runtime. Mapping is stable per skill: `aitask-pick` → `pick`, `aitask-explore` → `explore`, `aitask-qa` → `qa`, `aitask-fold` → `fold`, `aitask-review` → `review`, `aitask-pr-import` → `pr-import`, `aitask-revert` → `revert`.

## 3g. Per-agent surface table (canonical reference)

| Agent | Stub authoring location | `<agent_literal>` | Rendered variant location |
|-------|------------------------|-------------------|----------------------|
| Claude | `.claude/skills/<skill>/SKILL.md` | `claude` | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| Codex | `.agents/skills/<skill>/SKILL.md` | `codex` | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| OpenCode | `.opencode/commands/<skill>.md` body | `opencode` | `.opencode/skills/<skill>-<profile>-/SKILL.md` |

The codex row's extra `-codex-` segment is gated by `agent_shared_skills_root codex == true` in `.aitask-scripts/lib/agent_skills_paths.sh` (mirror: `AGENT_SHARED_SKILLS_ROOT["codex"] == True` in `.aitask-scripts/lib/skill_template.py`). The same rule applies to any future agent whose `agent_skill_root` collides with another agent's (e.g., agy in t814 → `.agents/skills/<skill>-<profile>-agy-/SKILL.md`).

Notes:
- In Claude, the rendered variant at `<skill>-<profile>-/SKILL.md` is technically auto-discoverable as a slash command (`/aitask-pick-fast-`). The stub flow never invokes that path; the trailing-hyphen slash command is a side effect of the dir naming and is not part of the normal invocation flow.
- In Codex, the rendered variant at `.agents/skills/<skill>-<profile>-/SKILL.md` is reached via the stub's Read instruction. Codex does not auto-discover slash commands.
- In OpenCode, the rendered variant lives under `.opencode/skills/`, NOT under `.opencode/commands/`. The command wrapper is the stub; the rendered file is the dispatch target reached via Read-and-follow.

## 3h. Argument forwarding contract

The stub's Step 1 parses `ARGUMENTS` (Claude/Codex) or `$ARGUMENTS` (OpenCode) for the optional `--profile <name>` pair. If found:
- Use the captured `<name>` as the active profile (overrides resolver).
- Remove the `--profile <name>` pair from the forwarded args before Step 3.

This mirrors today's `/aitask-pick --profile fast 16` user-facing convention: the user (or a Python TUI like `AgentCommandScreen`'s per-run editor, t777_17) supplies an override, the stub honors it, and the rendered variant receives the cleaned args (`16` only — no `--profile fast` residue).

Argument forwarding from `ait skillrun` (t777_5) and Python TUIs uses the same contract: append `--profile <name>` to the ARGUMENTS that get passed to the user-facing slash command (`/<skill>`). No TUI invokes the rendered slash command directly. The override path through ARGUMENTS is the **single** mechanism for non-default profile selection at invocation time.

## 3i. Reference resolution (for the t777_22 dep-walker)

Authoring templates (`SKILL.md.j2`) and shared `.md` procedures may use any of three reference shapes when linking to another procedure file. The dep-walker discovers all three and renders the targets into the per-profile sibling tree.

| Shape | Example | Resolution |
|-------|---------|-----------|
| Full path | `.claude/skills/task-workflow/planning.md` | Direct path under the source agent root (`.claude/skills/`, the SoT per t777_1). Ref strings may name any of the supported agent roots (`.claude`, `.agents`, `.opencode`); the walker normalises to `.claude/skills/` for resolution. |
| Sibling | `planning.md` | Relative to the **current source file's parent dir**. |
| Skill-relative | `task-workflow/planning.md` (one `/`, no leading `.claude/...`) | Relative to the source agent root (`.claude/skills/`). |

After rendering, references inside the rendered output are rewritten:

- **Full-path** → `<target_root>/<dir>-<profile>[-<agent>]-/<file>.md`, where `<target_root>` comes from `--agent` (`.claude/skills` for `claude`, `.agents/skills` for `codex`, `.opencode/skills` for `opencode`). The `-<agent>-` segment appears only when `<target_root>` is shared (t834; today: codex; +agy in t814).
- **Sibling** → unchanged. The sibling file is rendered into the SAME per-profile dir, so the bare-filename reference still resolves correctly when the agent reads the rendered file.
- **Skill-relative** → rewritten to full-path form: `<target_root>/<dir>-<profile>[-<agent>]-/<file>.md`. (Without rewriting, a one-`/` reference would otherwise resolve against the per-profile dir and fail.)

If a candidate path does not resolve to a real source file under `.claude/skills/`, the walker silently skips it. Prose mentions of filenames in narrative text are therefore safe — false positives (e.g., "edit the planning.md file") are filtered by the existence check.

**Cycle handling.** The walker maintains a visited set keyed on the source absolute path. References that point at an already-visited source are still rewritten in the calling file, but are not enqueued for a second render.

**File-extension contract.** Only `SKILL.md.j2` (entry-point templates) carry the `.j2` extension. All referenced procedures keep the plain `.md` extension even if they grow Jinja markers in a later conversion. The walker treats every reachable `.md` as a Jinja template and falls through to an identity transform when no Jinja markers are present.

## 3j. Template completeness — rendered body must not re-resolve profile

The point of templated dispatch is that the rendered variant has the profile baked in at render time. The rendered body must therefore NEVER re-resolve the profile at runtime. In particular, the following procedures must NOT appear in the source templates (and consequently must not appear in any rendered output):

- Step 0 / Step 0a "Select Execution Profile" — would re-run `aitask_scan_profiles.sh`.
- task-workflow Step 3b "refresh execution profile" — would re-read the profile YAML.
- Any equivalent "Execute the Execution Profile Selection Procedure" hand-off inside the rendered closure.

Profile is mandatory at render time — `skill_template.py::render_skill` always passes a non-empty `profile` binding. The no-profile fallback is dead code and must be **deleted outright** from source templates, not wrapped in `{% if not profile %}…{% endif %}` guards (which just preserves dead documentation in the rendered output).

**Forbidden tokens.** The following strings must NOT appear in any rendered output:

- `aitask_scan_profiles.sh`
- `Execute the Execution Profile Selection Procedure`
- `Select Execution Profile`
- `refresh execution profile`

The two render tests (`tests/test_skill_render_aitask_pick.sh`, `tests/test_skill_render_task_workflow.sh`) enforce this with `assert_not_contains` over all rendered combos. New per-skill conversions (t777_8..15) MUST extend the same assertions to their entry-point and procedure goldens.

## Pilot findings (t777_6)

The pilot conversion of `aitask-pick` (t777_6, completed 2026-05-19)
established five patterns that subsequent per-skill conversions
(t777_8..15) should follow:

1. **Uniform recursive rendering works end-to-end.**
   `aitask_skill_render.sh`'s walk-write traversed the 22-file
   `task-workflow/` closure across 12 (profile × agent) renders without
   manual intervention. The reference-rewrite regex (`FULL_PATH_REF_RE`
   in `lib/skill_template.py`) and BFS visited-set are the supported
   public interface — do not reinvent them per skill. Per-skill work
   only authors the entry-point `.j2` and writes goldens.

2. **Stage under `<skill>n` for in-use skills.** The live `aitask-pick`
   ran every step of this task's own workflow. Editing it in place would
   have wedged mid-pick. The parallel-name stage (`aitask-pickn` →
   atomic rename to `aitask-pick`) gave a full golden + manual-verification
   cycle before the swap. This is the canonical procedure for any future
   conversion of a skill that drives an active workflow. Canonical memory:
   `feedback_stage_under_parallel_name`.

3. **Golden-file tests are mandatory.** `./ait skill verify` and "renders
   without error" catch fewer regressions than committed goldens; the
   template engine can silently shift output (whitespace, comment
   placement, conditional bodies). 12 goldens caught the t777_26
   profile-resolution mismatch the moment it landed. Canonical memory:
   `feedback_golden_file_tests_for_template_engines`.

   **Operational rule:** goldens must be regenerated and committed
   alongside *any* edit to a `.md.j2` or closure file — not just at
   conversion time. A template-only commit ships with stale goldens
   and silently fails Test 1 on the next test run. See
   "Regenerate goldens after any `.md.j2` or closure edit" in
   `aidocs/framework/skill_authoring_conventions.md` for the regenerate command
   and the same-commit rule.

   **Golden dimensionality (t809 refinement):** entry-point goldens are
   `claude`-only — the basic stdout render performs no per-agent reference
   rewriting (that is a walk-write property, covered by Test 4), so the
   `codex`/`opencode` renders are byte-identical to `claude`.
   Likewise a profile-invariant procedure (its profile conditional
   activated by no committed profile) keeps one canonical `-default`
   golden. Both pruned dimensions are guarded by a cheap byte-equality
   **Test 1b** invariance assertion that fails LOUDLY if a template later
   introduces a real `{% if agent %}` gate or a profile divergence — at
   which point the pruned goldens are re-added surgically for that skill.

4. **Entry-point templates use `.md.j2`; referenced procedures keep
   `.md`.** The walk-write infrastructure assumes a single `.md.j2`
   per skill at the entry point. Referenced procedures
   (`manual-verification.md`, `planning.md`, etc.) MUST be plain `.md`
   files — even when their bodies contain `{% if profile.… %}` wraps.
   The render closure handles both shapes; a double-suffix `.md.j2` on a
   procedure file confuses the walker (it would attempt to render the
   procedure as a separate entry point).

5. **Per-agent tool mapping lives in prereq files, never in the template
   body.** Resist the temptation to add
   `{% if agent == "claude" %} AskUserQuestion … {% elif agent == "codex" %} request_user_input … {% endif %}`
   branches inside the entry-point template body. They balloon the
   template and obscure intent. Keep per-agent tool-name mapping in
   per-agent prereq files (e.g., `codex_tool_mapping.md`,
   `opencode_tool_mapping.md`) that the rendered body Reads-and-follows.
