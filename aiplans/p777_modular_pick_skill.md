---
Task: t777_modular_pick_skill.md
Base branch: main
plan_verified: []
---

# t777 — Templated execution-profile redesign (all skills, all agents)

## Context

The aitasks framework drives skill behavior via runtime
"Profile check:" branches inside `SKILL.md` files. Profile YAML keys
(`skip_task_confirmation`, `default_email`, `plan_preference`, …) are
read at runtime by the LLM, which branches on them as it walks the
skill. Four chronic issues:

1. The LLM can drift on profile values across long contexts (hence
   the periodic "re-read the profile to refresh memory" workaround at
   `task-workflow/SKILL.md` Step 3b).
2. Several agents (notably Codex CLI) cannot show `AskUserQuestion`
   prompts outside plan mode, but the current skills depend on them
   as the fallback path.
3. Resolving and confirming the active profile is overhead on every
   skill invocation.
4. Profile-driven branches turn `SKILL.md` into a non-linear maze.

**Scope (user-confirmed):** the full redesign lands as children of
this parent task. Covers all nine skills (`aitask-pick`,
`aitask-explore`, `aitask-review`, `aitask-fold`, `aitask-qa`,
`aitask-pr-import`, `aitask-revert`, `aitask-pickrem`,
`aitask-pickweb`), all referenced shared `task-workflow/*.md`
procedures, and all four code agents (Claude Code, Codex CLI, Gemini
CLI, OpenCode). Also includes the per-run profile-editor UI in
`AgentCommandScreen` and extraction of the reusable profile-editor
widget.

## Approach

### Engine
`minijinja-py` — Rust-backed Python binding to `minijinja`,
Jinja2-compatible subset (sufficient for `{{ profile.key }}`,
`{% if %}/{% else %}/{% endif %}`, `{% include %}`). Installed into
`~/.aitask/venv` (and the optional PyPy venv) via the existing pip
lines in `.aitask-scripts/aitask_setup.sh`.

### Per-profile slash-command dispatch (race-free)

Two critical user-supplied constraints invalidated earlier drafts:

- **Skills are re-read during execution** — overwriting `SKILL.md`
  mid-session corrupts the running agent's view.
- **Skills are invoked from INSIDE live agent sessions** (typing
  `/aitask-pick 42` directly) — no wrapper script can intercept and
  render at that moment.

The design must therefore produce stable, on-disk SKILL.md files
that are never mutated while in use. Each `(skill, profile, agent)`
combination gets its own slash command and its own directory:

```
.claude/skills/aitask-pick/         # stub (committed; the "no-suffix" entry point)
  SKILL.md.j2                       # authoring source of truth (committed)
  SKILL.md                          # tiny human-authored stub (committed)
.claude/skills/aitask-pick-fast/    # gitignored, on-demand render
  SKILL.md
.claude/skills/aitask-pick-remote/  # gitignored, on-demand render
  SKILL.md
```

The no-suffix `/aitask-pick` slash command is a **stub** that
resolves the user's currently-active profile and dispatches. The
profile-suffixed `/aitask-pick-fast` etc. are the real workflows,
rendered on demand.

### The stub SKILL.md

The no-suffix `<agent>/skills/<skill>/SKILL.md` is a small, stable,
hand-authored file (committed) that instructs the agent to:

1. Run `ait skill resolve-profile <skill>` (bash) — returns the
   active profile name from the existing precedence chain
   (`userconfig.yaml.default_profiles.<skill>` →
   `project_config.yaml.default_profiles.<skill>` → `default`).
2. Run `ait skill render <skill> --profile <name> --agent <agent>`
   (bash) — renders `<agent>/skills/<skill>-<name>/SKILL.md`
   atomically (mv from tempfile) AND recursively renders any
   referenced shared procedures (e.g. `task-workflow-<name>/`).
   No-op if already up-to-date.
3. Invoke `/<skill>-<name> <forwarded args>` — the agent dispatches
   to the rendered, profile-specific slash command.

The stub is per-agent (4 files per skill) because the slash-dispatch
syntax may differ slightly between Claude, Codex, Gemini, OpenCode.
Each stub is ~10–20 lines of natural-language instructions plus the
two bash commands.

### Render trigger paths (no pre-rendering, ever)

Renders are triggered ONLY by:

- **The stub SKILL.md** (when the agent invokes the no-suffix
  slash command from inside a session).
- **The wrapper `ait skillrun`** (when invoked from a shell or from
  the `AgentCommandScreen` TUI dialog before launching a new agent).

`ait setup` does NOT render anything proactively. Nothing renders
until first use of a given `(skill, profile, agent)` combination.
Per-profile dirs are gitignored: `.claude/skills/*-*/`,
`.agents/skills/*-*/`, `.gemini/skills/*-*/`, `.opencode/skills/*-*/`.

### Single template, per-agent render

One `.j2` source-of-truth per skill (and per templated shared
procedure), living in the Claude path per CLAUDE.md "Claude-first"
rule:

```jinja
{% if agent == "codex" %}
Use `request_user_input` (max 3 options per question).
{% elif agent == "claude" %}
Use `AskUserQuestion`.
{% else %}
Use the equivalent interactive prompt tool.
{% endif %}
```

Renderer takes `(template, profile, agent_name)` and writes the
rendered SKILL.md into the right per-profile directory under the
chosen agent's skill root.

### Wrapper and run-dialog integration

`ait skillrun <skill> [--profile <name>] [--agent <name>] [args…]`
is the wrapper, called by:

- Shell users who want a specific profile for one invocation.
- `AgentCommandScreen` when launching a new agent session — the
  dialog gains a "Profile: \<name\> (E)dit" row + sub-modal that
  reuses an extracted `lib/profile_editor.py` widget. Edits scope to
  the single launch (written to a one-shot override file consumed
  by the wrapper).

The wrapper renders the requested `(skill, profile, agent)` (and
referenced shared procs) into the per-profile dir, then `exec`s the
agent with `'/<skill>-<profile> <args>'`. This bypasses the stub
when the user has already committed to a specific profile.

### Source-of-truth + verifier

- `.claude/skills/<skill>/SKILL.md.j2` — authoring template
  (committed). One per skill and per templated shared procedure.
- `<agent>/skills/<skill>/SKILL.md` — per-agent stub (committed).
- `<agent>/skills/<skill>-<profile>/SKILL.md` — on-demand render
  (gitignored).

`ait skill verify` re-renders every `.j2` for every agent against
`default.yaml` and asserts the renderer raises no errors and
produces non-empty output (it does NOT diff against a committed
render, because no profile-suffixed renders are committed). Pre-commit
hook adopts the verifier.

### Cache invalidation on profile change

Lazy invalidation is built into the render script (t777_2): "skip-if-fresh"
compares the rendered SKILL.md mtime against BOTH the template AND
the profile YAML, re-rendering whenever the profile YAML is newer.

Eager invalidation (t777_20) runs in `ProfileEditScreen.on_save`
(the extracted widget from t777_16) — after any framework TUI
saves a modified profile YAML, all `<agent>/skills/*-<profile>/`
directories are deleted via `aitask_skill_invalidate.sh`. This is
belt-and-suspenders: surfaces stale-render issues immediately and
avoids confusion from old rendered content lingering on disk.

Per-run profile overrides (t777_17, written to `/tmp/ait-run-override-<pid>.yaml`)
do NOT trigger eager invalidation — they are one-shot and do not
modify the project profile YAML.

Pre-commit
hook adopts the verifier.

## Children (20 total)

Dependency chain: foundation (1–5) → pilot (6) → shared procs (7) →
per-skill (8–15) → run-dialog UI (16–17, 20) → docs (18) →
retrospective (19, blocked by 20). Children 8–15 can be implemented
in any order once 1–7 are done. **t777_20** (eager-invalidation
hook into the extracted profile-editor widget) was added after
initial approval and depends on t777_2 + t777_16.

### Foundation

**t777_1 — `minijinja` dep + renderer + agent-paths + active-profile resolver**

- Modify `.aitask-scripts/aitask_setup.sh`: add `'minijinja>=2.0,<3'`
  to both pip-install lines (CPython venv ~line 655, PyPy venv
  ~line 574).
- Create `.aitask-scripts/lib/skill_template.py`:
  - `render_skill(template_path, profile_dict, agent_name) -> str`
  - `keep_trailing_newline=True`, strict-undefined wrapped to produce
    a clear "missing key `<k>` in profile `<f>`" error, UTF-8 + LF.
  - Document the minijinja-vs-Jinja2 caveat (no `{% extends %}` with
    arbitrary Python, smaller filter set, no `do` extension).
- Create `.aitask-scripts/lib/agent_skills_paths.sh`:
  - `agent_skill_root <agent>` → `.claude/skills` / `.agents/skills`
    / `.gemini/skills` / `.opencode/skills` (verify at impl time
    whether Gemini has its own tree or routes through `.agents/`).
  - `agent_skill_dir <agent> <skill> [<profile>]` → full directory.
  - `agent_authoring_template <skill>` → `.claude/skills/<skill>/SKILL.md.j2`.
- Create `.aitask-scripts/aitask_skill_resolve_profile.sh`:
  - Args: `<skill>`. Mirrors the precedence in
    `task-workflow/execution-profile-selection.md`:
    `userconfig.yaml.default_profiles.<skill>` →
    `project_config.yaml.default_profiles.<skill>` → `default`.
  - Output: bare profile name to stdout. Single-line, scriptable.
- Add `tests/test_skill_template.sh`: renderer happy path, strict
  undefined, agent branching, resolve-profile precedence.

**t777_2 — `aitask_skill_render.sh` + `ait skill render` subcommand + whitelist**

- Create `.aitask-scripts/aitask_skill_render.sh`:
  - Args: `<skill> --profile <name> --agent <name> [--force]`.
  - Sources `lib/python_resolve.sh` (`require_ait_python`).
  - Source-of-truth template path:
    `agent_authoring_template <skill>`.
  - Reads the profile YAML via the existing `aitask_scan_profiles.sh`
    helper (handles `local/*.yaml` overrides).
  - Renders via `skill_template.py` into a tempfile, then atomic mv
    to `<agent>/skills/<skill>-<profile>/SKILL.md`. mkdir -p the
    target directory.
  - **Recursive include rendering:** statically scan the .j2 source
    for `{% include "<path>" %}` directives (regex sufficient; minijinja's
    parser is also accessible via Python if regex is too brittle).
    For each include that resolves to a shared procedure `.j2`,
    invoke `aitask_skill_render.sh` recursively with the same
    `(profile, agent)` to render under
    `<agent>/skills/<proc>-<profile>/SKILL.md`. Skip non-templated
    plain `.md` includes (they stay in their canonical location and
    referenced unchanged).
  - **Skip-if-fresh** optimization: if the rendered file's mtime is
    newer than both the template AND the profile YAML, skip render
    unless `--force`.
- Add `./ait` `skill)` case-entry with `render` subcommand
  (sub-dispatch pattern from `crew)`/`brainstorm)`).
- 5-touchpoint whitelist for `aitask_skill_render.sh` AND
  `aitask_skill_resolve_profile.sh`: `.claude/settings.local.json`,
  `.gemini/policies/aitasks-whitelist.toml`,
  `seed/claude_settings.local.json`,
  `seed/geminicli_policies/aitasks-whitelist.toml`,
  `seed/opencode_config.seed.json`.

**t777_3 — Stub design + .gitignore for per-profile dirs**

- Design the stub SKILL.md template body. Each stub:
  1. ~15-20 lines of natural-language instructions.
  2. Two bash commands the agent should run (`resolve-profile`,
     `render`).
  3. A slash-dispatch instruction to invoke `/<skill>-<profile>`
     with forwarded args.
- **Verify per-agent slash-dispatch support** (critical risk):
  - Claude Code: confirm a skill can instruct the agent to invoke
    another slash command. Test with a throwaway stub.
  - Codex CLI: same.
  - Gemini CLI: same.
  - OpenCode: same.
  - If any agent can't dispatch → degraded UX for that agent: the
    no-suffix slash command falls back to printing instructions
    ("Run `ait skillrun <skill> --profile <name>` from a shell").
    Document the limitation.
- Author 4 stub templates (one per agent) — they're nearly identical
  but allow per-agent dispatch-syntax tuning. Stubs are committed,
  not generated.
- Add to root `.gitignore`:
  ```
  # Per-profile rendered skill variants (on-demand, not committed)
  .claude/skills/*-*/
  .agents/skills/*-*/
  .gemini/skills/*-*/
  .opencode/skills/*-*/
  ```
  Note the glob: `aitask-pick/` is NOT matched (no hyphen-separator).
  `aitask-pick-fast/` IS matched. Author skills with non-hyphenated
  names where possible; for hyphenated authoring names (e.g.
  `task-workflow`), use a more specific gitignore entry or rename
  the authoring dir to avoid the glob conflict — verify at impl
  time. If glob is ambiguous, switch to an explicit allowlist or
  use a sentinel filename in each on-demand dir (e.g. `.generated`).

**t777_4 — `ait skill verify` + tests + pre-commit hook + whitelist**

- Create `.aitask-scripts/aitask_skill_verify.sh`:
  - Walks every `.j2` under `.claude/skills/<skill>/` (Claude
    authoring path).
  - For each `.j2`, renders against `default.yaml` for each of the
    4 agents — confirms no errors raised, output is non-empty.
  - Verifies every stub `<agent>/skills/<skill>/SKILL.md` references
    its skill's template and contains the expected bash commands.
  - Non-zero exit on any failure with a clear message.
- Add `./ait` `skill)` `verify` subcommand.
- Install or extend the pre-commit hook to run `ait skill verify`
  whenever any `.j2` or stub `SKILL.md` is staged.
- Extend `tests/test_skill_template.sh`: `ait skill verify` passes
  on clean checkout; rendering each profile for each agent produces
  output.
- 5-touchpoint whitelist for `aitask_skill_verify.sh`.

**t777_5 — `aitask_skillrun.sh` wrapper + `ait skillrun` + whitelist**

- Create `.aitask-scripts/aitask_skillrun.sh`:
  - Args: `<skill> [--profile <name>] [--agent <name>]
    [--profile-override <yaml>] [--dry-run] [args…]`.
  - `--agent` defaults to `$AIT_AGENT` env, else PATH-autodetect.
  - `--profile` defaults to `ait skill resolve-profile <skill>`.
  - `--profile-override <yaml>`: a one-shot override file produced
    by the `AgentCommandScreen` per-run editor (t777_17). Merged on
    top of the resolved profile before render. Override file is
    deleted after render.
  - Calls `ait skill render <skill> --profile <name> --agent <name>`.
  - `exec`s the agent CLI: `exec claude "/<skill>-<name> <args>"`
    (and similar for codex/gemini/opencode).
  - `--dry-run`: prints the render commands and the launch command,
    does not exec.
- Add `./ait` `skillrun)` case-entry.
- 5-touchpoint whitelist.

### Pilot

**t777_6 — Convert `aitask-pick` (template + 4 stubs)**

- Create `.claude/skills/aitask-pick/SKILL.md.j2`:
  - Copy current `.claude/skills/aitask-pick/SKILL.md` content.
  - Replace every "Profile check:" block (notably the
    `skip_task_confirmation` branches in Step 0b Format 1 and
    Format 2) with explicit `{% if profile.skip_task_confirmation %}
    … {% else %} … {% endif %}` whose branches contain only
    straight-line text.
  - Add `{% if agent == "..." %}` branches for tool mappings.
  - Scan for literal `{{` / `{%` and wrap in `{% raw %}…{% endraw %}`.
  - Frontmatter `name: aitask-pick-{{ profile.name }}` (so the
    rendered file has the correct name for the slash command).
- Replace `.claude/skills/aitask-pick/SKILL.md` with the new stub.
- Author the stub for Codex (`.agents/skills/aitask-pick/SKILL.md`),
  Gemini (`.gemini/skills/aitask-pick/SKILL.md`), OpenCode
  (`.opencode/skills/aitask-pick/SKILL.md`).
- **First implementation step:** verify Claude / Codex / Gemini /
  OpenCode only auto-discover the `SKILL.md` file and ignore
  `SKILL.md.j2`. If `.j2` is auto-discovered, rename to
  `SKILL.md.tmpl` or move under `_template/SKILL.md.j2`.
- Verify: `ait skill verify` passes; `ait skillrun pick --profile
  fast --dry-run 777` shows the render call + the `/aitask-pick-fast
  777` launch command; manual: invoking `/aitask-pick` inside Claude
  triggers the stub, renders, dispatches.

### Shared task-workflow templates

**t777_7 — Convert task-workflow shared procedures (4 agents)**

- Convert the `.claude/skills/task-workflow/*.md` procedures that
  actually branch on profile keys (verify at impl time by grepping
  for `profile`):
  - `SKILL.md` (Steps 3/3b/4/5/6 profile branches)
  - `planning.md` (Step 6.0/6.1/Checkpoint profile branches)
  - `satisfaction-feedback.md` (`enableFeedbackQuestions`)
  - `manual-verification.md` (any profile branches)
  - `manual-verification-followup.md` (`manual_verification_followup_mode`)
  - `remote-drift-check.md` (`base_branch`)
  - others as discovered
- Plain `.md` procedures (no profile branches) stay as-is and remain
  in `.claude/skills/task-workflow/` and other agents' equivalents.
  The render machinery treats them as static includes.
- For each templated proc:
  - `.j2` template lives in `.claude/skills/task-workflow/`
    (Claude authoring path).
  - Stub authored for each of the 4 agents:
    `<agent>/skills/task-workflow/<proc>.md` (the stub for shared
    procs is slightly different — it dispatches to
    `<proc>-<profile>.md` in the same task-workflow directory rather
    than a separate slash command, since shared procs are referenced
    via file paths inside skill SKILL.md, not via slash commands).
  - Alternative implementation that avoids stub-per-proc complexity:
    skill SKILL.md templates emit references with profile-suffixed
    paths directly (e.g. `task-workflow-fast/planning.md`). The
    rendered skill file points at the rendered shared proc, no
    runtime dispatch needed. **Prefer this approach** — surface this
    decision in t777_7's plan file.

### Per-skill conversions

Each child below: convert that skill's `SKILL.md` to a `.j2`
template with `{% if agent == "..." %}` branches; author 4 stub
SKILL.md files (one per agent); ensure `ait skill verify` passes;
smoke-test wrapper.

**t777_8 — Convert `aitask-explore`** — profile key `explore_auto_continue`.
**t777_9 — Convert `aitask-review`** — TBD profile keys.
**t777_10 — Convert `aitask-fold`** — TBD profile keys.
**t777_11 — Convert `aitask-qa`** — `qa_mode`, `qa_run_tests`, `qa_tier`.
**t777_12 — Convert `aitask-pr-import`** — TBD profile keys.
**t777_13 — Convert `aitask-revert`** — TBD profile keys.
**t777_14 — Convert `aitask-pickrem`** — `force_unlock_stale`,
`done_task_action`, `orphan_parent_action`, `complexity_action`,
`review_action`, `issue_action`, `abort_plan_action`,
`abort_revert_status`. Largest conversion.
**t777_15 — Convert `aitask-pickweb`** — TBD profile keys.

### Run-dialog UI

**t777_16 — Extract profile-editor widget to `lib/profile_editor.py`**

- Pull profile-field-editing screens out of
  `.aitask-scripts/settings/settings_app.py` (around line 1073
  `EditValueScreen` and surrounding field-edit infrastructure) into
  `.aitask-scripts/lib/profile_editor.py`.
- Settings TUI imports it back. Behavior unchanged.
- Exposes `ProfileEditScreen(profile_data: dict, on_save:
  callable) -> ModalScreen`.

**t777_17 — Per-run profile (E)dit in `AgentCommandScreen` + wrapper integration**

- Modify `.aitask-scripts/lib/agent_command_screen.py`:
  - Add "Profile: \<name\> (E)dit" row above the existing "Agent"
    row.
  - Edit button pushes `ProfileEditScreen` from t777_16 with the
    current profile data.
  - Save in the sub-modal writes a one-shot override file
    (`/tmp/ait-run-override-<pid>.yaml`).
  - When an override is active, update `full_command` and
    `prompt_str` reactives to:
    `ait skillrun <skill> --profile-override <path> [args]`.
- Confirm the wrapper from t777_5 already handles
  `--profile-override`; if not, add it here.

**t777_20 — Profile-modification eager invalidation** *(added post-approval; depends on t777_2 + t777_16)*

- Create `.aitask-scripts/aitask_skill_invalidate.sh` — args
  `<profile_name>`; walks 4 agent skill roots and deletes any
  `*-<profile>/` directory. Idempotent. Emits
  `INVALIDATED:<count> ...`.
- Add `invalidate` subcommand under `skill)` case in `./ait`.
- Hook into `ProfileEditScreen.on_save` (extracted in t777_16):
  after profile-YAML write, shell out to the invalidator via
  `subprocess.run(..., check=False)`. Log failures to TUI but
  don't error the save.
- 5-touchpoint whitelist for `aitask_skill_invalidate.sh`.
- Belt-and-suspenders on top of t777_2's lazy mtime check
  (covers TUI-mediated profile edits; lazy covers hand-edits).
- Per-run overrides (t777_17 `/tmp/ait-run-override-*.yaml`)
  do NOT trigger invalidation — they don't modify the project
  YAML.

### Polish

**t777_18 — Documentation update**

- CLAUDE.md: new "Skill Template Authoring Conventions" section:
  `.j2` source vs stub `SKILL.md`, per-profile dir naming, the
  `{% if agent == … %}` pattern, `{% raw %}` for literal braces,
  `ait skill verify` contract, agent path table.
- Website (`website/content/docs/`): user-facing pages explaining
  `ait skillrun`, profile-driven behavior, per-run editor, the
  no-suffix-vs-suffixed slash command UX.
- README: brief `ait skillrun` mention.

**t777_19 — Retrospective evaluation**

- Per `feedback_plan_split_in_scope_children`: after t777_1..18
  archived, evaluate scope/grain.
- Specific checks:
  - Did the stub-dispatch approach work in all 4 agents, or did
    any agent require a fallback?
  - Did `{% if agent == … %}` branching scale, or push toward
    separate per-agent templates?
  - Did the per-skill grain (8 sibling children for skills) feel
    right?
  - Were any in-scope items silently deferred?
- File newly-discovered work as fresh top-level tasks. Update
  CLAUDE.md if new conventions emerged.

## Critical Files

**New files (top-level):**
- `.aitask-scripts/lib/skill_template.py`
- `.aitask-scripts/lib/agent_skills_paths.sh`
- `.aitask-scripts/lib/profile_editor.py` (t777_16)
- `.aitask-scripts/aitask_skill_resolve_profile.sh`
- `.aitask-scripts/aitask_skill_render.sh`
- `.aitask-scripts/aitask_skill_verify.sh`
- `.aitask-scripts/aitask_skillrun.sh`
- `tests/test_skill_template.sh`
- `.claude/skills/<each-skill>/SKILL.md.j2` × 9 skills + templated
  shared procs
- `<each-agent>/skills/<each-skill>/SKILL.md` × 9 skills × 4
  agents = 36 stub files (committed; replace existing SKILL.md
  files)

**Modified files:**
- `.aitask-scripts/aitask_setup.sh` (pip-install lines)
- `./ait` (case-statement: `skillrun)` and `skill)` entries)
- `.aitask-scripts/lib/agent_command_screen.py` (t777_17)
- `.aitask-scripts/settings/settings_app.py` (t777_16 extraction)
- `.gitignore` (per-profile dir glob)
- Five whitelist files × 3 helpers (t777_2, t777_4, t777_5)
- CLAUDE.md + website docs (t777_18)

## End-to-End Verification

1. `bash .aitask-scripts/aitask_setup.sh` succeeds;
   `~/.aitask/venv/bin/python -c "import minijinja"` works.
2. `bash tests/test_skill_template.sh` passes.
3. `shellcheck .aitask-scripts/aitask_skill*.sh
   .aitask-scripts/aitask_skillrun.sh` clean.
4. `ait skill verify` exits 0.
5. `ait skill render pick --profile fast --agent claude` creates
   `.claude/skills/aitask-pick-fast/SKILL.md` with rendered content
   (auto-confirm branch present).
6. `ait skillrun pick --profile fast --dry-run 777` shows render
   call + `claude '/aitask-pick-fast 777'` launch command.
7. End-to-end (manual): `ait skillrun pick --profile fast 777`
   launches `claude`, agent walks rendered skill without re-asking
   the auto-confirm question. Repeat for codex / gemini / opencode.
8. **Stub-dispatch test:** inside a running `claude` session, type
   `/aitask-pick 777` — the stub triggers, renders, dispatches to
   `/aitask-pick-<active-profile>`. Repeat for the other 3 agents.
9. `ait settings` profile-editing UI still works.
10. AgentCommandScreen shows Profile row + (E)dit button; editing
    produces a per-run override that the wrapper honors.

## Pitfalls and conventions

- **`minijinja` ≠ Jinja2 100%** — no `{% extends %}` with arbitrary
  Python, smaller filter set, no `do` extension. Stick to `{{ }}`,
  `{% if %}/{% else %}/{% endif %}`, `{% include %}`,
  `{% raw %}/{% endraw %}`.
- **Critical risk — slash-dispatch from inside a skill** — verify in
  t777_3 that each of the 4 agents allows a SKILL.md to programmatically
  invoke another slash command. Fallback path (print shell hint) is
  documented if any agent doesn't.
- **Literal `{{` and `{%`** in SKILL.md content — scan before
  converting; wrap matches in `{% raw %}` blocks.
- **File encoding** — UTF-8 read/write, `newline="\n"`,
  `keep_trailing_newline=True`. Atomic mv on render to avoid torn
  reads during agent execution (the user-confirmed re-read-during-
  execution behavior makes atomic writes essential).
- **Strict-undefined** — desired; wrap raw `UndefinedError` with
  the offending key + profile filename.
- **`.gitignore` glob ambiguity** — `task-workflow/` contains a
  hyphen; the proposed glob `<agent>/skills/*-*/` would match it.
  Resolution surfaced in t777_3 (rename authoring dir, use sentinel
  filename, or switch to allowlist-style ignore).
- **Skill-loader auto-discovery** — verify each agent only picks up
  `SKILL.md` (not `*.md` or `*.j2`). First step of t777_6.
- **Single source of truth for cross-script constants** (per memory
  `feedback_single_source_of_truth_for_versions`): the per-agent
  skill-path table lives in `agent_skills_paths.sh` only.
- **5-touchpoint whitelist** (CLAUDE.md "Adding a New Helper Script")
  applies to every new helper script. Codex exempt.
- **Concurrent edits to profile YAML during a live session** — the
  next `/aitask-pick` invocation will re-render with the new
  profile values; any running skill execution reading from the
  same per-profile file mid-execution may see torn content. Mitigate
  via atomic mv and document the limitation.
- **CLAUDE.md "Claude-first" rule** — the authoring `.j2` lives in
  `.claude/skills/<name>/`; the renderer writes to the other three
  agents' per-profile directories. Editing a Codex/Gemini/OpenCode
  `.md` stub directly is allowed (stubs are per-agent), but the
  template `.j2` is single-source.
