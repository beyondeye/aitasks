---
Task: t835_add_agy_antigravity_cli_support.md
Base branch: main
plan_verified: []
---

# Plan: t835 — Add Antigravity CLI (`agy`) as a first-class supported code agent

## Context

t835 is the **inverse counterpart** of t812 (which removed `geminicli`).
Antigravity CLI (`agy`) is Google's replacement for `geminicli`, with a
sandboxed-execution model that closely mirrors **Codex CLI** (shared
`.agents/skills/` root, sandbox-based command approval). t834 (now
archived) added the agent-suffix mechanism to skill rendering, which
lets `codex` and `agy` co-exist in `.agents/skills/` without colliding.

The codebase verification confirms:
- All geminicli traces are removed (t812 complete).
- The t834 agent-suffix mechanism (`agent_shared_skills_root()`,
  `AGENT_SHARED_SKILLS_ROOT`, `<skill>-<profile>-<agent>-/` naming) is in
  place and ready to host `agy` alongside `codex`.
- Codex is the **closest analogue** and most agy changes can be modeled
  directly on the existing codex branch in each touchpoint.
- Two folded sub-concerns already in this parent (`835_1` model-id
  detection, `835_2` e2e verification — migrated from t345 / t401_3) need
  to be placed in the final child split.

The migration guide at `aidocs/geminicli_to_agy.md` is the source of
truth for agy-specific differences vs codex:
- Tool-name updates: `run_shell_command` → `run_command`, `web_fetch` →
  `read_url_content`.
- Global sandboxing via `~/.gemini/policies/` — framework MUST NOT install
  local policies.
- Markdown skills at `.agents/skills/<name>/SKILL.md` (shared with codex).

## Approach

Split this task into **6 child tasks**: 5 that mirror t812's 5-child
structure 1:1 (so future maintenance can read paired removal/addition
plans side-by-side), plus a 6th that uses the agy implementation as the
empirical evidence to **audit, reorganize, and surface
`aidocs/adding_a_new_codeagent.md`** so it becomes an accurate, up-to-date
reference for the next code-agent addition.

Each child plan will be written upfront (the parent planning pass) and
will explicitly reference its t812 counterpart as the inverse blueprint,
the current codex pattern as the structural model, and any
`aidocs/adding_a_new_codeagent.md` sections that apply.

After child creation, offer an aggregate **manual_verification sibling**
covering the e2e detection / launch flow (the natural home for the
`835_2` fold concern, since "actually launch agy" cannot be automated).

## Child task split

### t835_1 — Add agy agent infrastructure (inverse of t812_1)

**Inverse blueprint:** `aiplans/archived/p812/p812_1_remove_geminicli_agent_infrastructure.md`
(`### For t814 (add-agy): inverse instructions` subsection).

**Absorbed fold concern:** `t835_1` (model-id detection surface). This
child includes the work to pick a reliable model-id surface for agy
(candidates: `agy --version`, a `cli_info`/`cli_help` equivalent, or
`~/.gemini/settings.json` inspection — practical-test before committing)
and wire it into `aitask_resolve_detected_agent.sh` + the Model
Self-Detection Sub-Procedure (`.claude/skills/task-workflow/model-self-detection.md`).

**Files to touch (insert `agy` alongside `codex`):**
- `.aitask-scripts/lib/agent_string.sh` — `SUPPORTED_AGENTS` (L28),
  `get_cli_binary()` (L69-77, add `agy) echo "agy" ;;`),
  `get_model_flag()` (L80-88, add `agy) echo "-m" ;;` mirroring codex).
- `.aitask-scripts/aitask_resolve_detected_agent.sh` — `SUPPORTED_AGENTS`
  (L23) + new agy detection branch (chosen surface from research).
- `.aitask-scripts/aitask_codeagent.sh`:
  - Header comment listing agents.
  - `get_agent_coauthor_name()` (L197-231) — add agy branch modeled on
    codex (L203-209); if agy needs a custom label, add
    `format_agy_model_label()` above.
  - `get_agent_coauthor_email()` (L233-244) — add `agy) echo "agy@$domain" ;;`.
  - `build_invoke_command()` (L390-479) — add agy operation handlers
    modeled on codex (L432-458).
  - `--help` text examples (L542-551).
- `.aitask-scripts/aitask_verified_update.sh` (L12, L42 help-text) +
  `aitask_usage_update.sh` (L12, L43 help-text) — add `agy` to
  `SUPPORTED_AGENTS` and help.
- `.aitask-scripts/lib/agent_model_picker.py`:
  - `MODEL_FILES` dict (L37-41) — add `"agy": METADATA_DIR / "models_agy.json"`.
  - `_MODES` tuple (L277-284) — add `("agy", "All Agy models")`.
  - Docstring (L10) — mode-count "six" → "seven".
- `.aitask-scripts/stats/stats_data.py`:
  - `AGENT_DISPLAY_NAMES` (L56-61) — add `"agy": "Agy"`.
  - Agent tuples at L250 (`load_model_cli_ids`), L275
    (`load_verified_rankings`), L450 (`load_usage_rankings`) — add `"agy"`.
  - Verify no new regex branches needed in `canonical_model_id` /
    `model_display_from_cli_id` (codex doesn't have one; agy likely
    won't either — its cli_id format depends on surface chosen above).
- `.aitask-scripts/monitor/prompt_patterns.py` (L25-40) —
  `PROMPT_PATTERNS_BY_AGENT` add `"agy": []` (empty until wording is
  observed in real use).
- `.aitask-scripts/settings/settings_app.py`:
  - `MODEL_FILES` (L37-41) — add agy entry.
  - `CONFIG_FILE_DESCRIPTIONS` (L126-134) — add `"models_agy.json"`.
  - Pickrem auto-rerender loop and `_pickrem_rendered_paths::root_map`
    — **decide per-touchpoint** whether agy needs an entry: the loop
    uses agent canonical names (codex already covered, but agy is a
    distinct canonical name); root_map uses renderer short names
    (`codex` already covers the shared `.agents/skills/` root). Update
    `× N agents` message string accordingly.
- `.aitask-scripts/aitask_add_model.sh` (L24 `SUPPORTED_AGENTS`, L285
  help-text) — add agy.
- `aitasks/metadata/models_agy.json` — **new file**, stub entry only;
  populated by `/aitask-refresh-code-models` in t835_5.
- `.claude/skills/task-workflow/model-self-detection.md` — add agy
  detection branch using the chosen surface.

**Verification:** Run `bash tests/test_*.sh` for agent-string and
codeagent tests; verify `aitask_codeagent.sh list-agents` shows agy;
verify `aitask_resolve_detected_agent.sh --agent agy --cli-id <known_id>`
returns `AGENT_STRING:agy/<name>`.

---

### t835_2 — Add agy to skill rendering pipeline (inverse of t812_2)

**Inverse blueprint:** `aiplans/archived/p812/p812_2_remove_geminicli_skill_rendering.md`
(`### For t814 (add-agy): inverse instructions` subsection).

Layered on **t834**: agy maps to `.agents/skills` (same as codex), and
the agent-suffix mechanism (`<skill>-<profile>-agy-/SKILL.md`) handles
the collision. Tool-name references in agy-rendered skills must be
updated per `aidocs/geminicli_to_agy.md`.

**Files to touch:**
- `.aitask-scripts/lib/skill_template.py`:
  - `FULL_PATH_REF_RE` (L37-41) — already matches `.agents`; verify no
    edit needed (codex shares the same root).
  - `AGENT_ROOTS` (L50-55) — add `"agy": ".agents/skills"`.
  - `AGENT_SHARED_SKILLS_ROOT` (L59-63) — add `"agy": True`.
  - `_skill_name_from_source()` (L134-148) parts-validity tuple — verify
    no edit needed (already accepts `.agents` paths).
- `.aitask-scripts/lib/agent_skills_paths.sh`:
  - Doc comment (L14-34) — drop "+agy in t814" placeholder, mark as
    landed.
  - `agent_skill_root()` (L38-45) — add `agy) echo ".agents/skills" ;;`.
  - `agent_shared_skills_root()` (L50-57) — add `agy) echo "true" ;;`.
- `.aitask-scripts/aitask_skill_render.sh` (L37 `--agent` usage text) —
  add agy.
- `.aitask-scripts/aitask_skillrun.sh`:
  - Header comment (L17-19) and per-agent CMD case (L227-238) — add agy
    branch (likely modeled on codex; if agy needs a special invoker
    similar to `aitask_codex_plan_invoke.py`, add `aitask_agy_invoke.py`
    or reuse codex's if compatible).
  - `--help` examples (L62).
- `.aitask-scripts/aitask_skill_rerender.sh` (L39 outer agent loop) —
  add agy.
- `.aitask-scripts/aitask_skill_verify.sh` — `_stub_path_for()` case
  and `agents=(...)` array — add agy.
- `.aitask-scripts/aitask_audit_wrappers.sh`:
  - Touchpoint table: **claim next free IDs** (after gemini removal IDs
    2 and 5 are vacant; per t812_2 plan **do not reuse** — start from
    the next free ID after the current max — likely 8 onwards).
  - `wrapper_path()` case + `cmd_discover()` trees enum + helper
    whitelist loop tuples — add agy entries.
  - `render_agents_skill()` — the codex line stays; verify whether the
    "Codex CLI skill wrapper" intro should be widened to "Codex CLI
    and Antigravity CLI skill wrapper" (yes — both consume
    `.agents/skills/`).
  - Usage text (touchpoints, trees, subcommands).
- `.aitask-scripts/aitask_contribute.sh` (L49 `AREAS`, L711 `--area`
  help) — add `agy|.agents/skills/|Antigravity CLI skills`.
- `.aitask-scripts/aitask_codemap.py` (`FRAMEWORK_DIRS` set, L18) +
  `aitask_codemap.sh` (L56 usage doc) — add agy if it ships any
  agy-specific dir (per `aidocs/geminicli_to_agy.md` it does not — the
  shared `.agents/skills/` root suffices, so likely **no edit needed**;
  verify).
- **Tool-name updates** in shared `.agents/skills/` content: per
  `aidocs/geminicli_to_agy.md`, agy-rendered skills must say
  `run_command` not `run_shell_command`, and `read_url_content` not
  `web_fetch`. Since codex+agy share the rendered output, decide
  **per-skill** whether to:
  (a) keep both tool names side-by-side in source (e.g., "use
  `run_command` (agy) / `run_shell_command` (codex)"), or
  (b) introduce a Jinja conditional `{% if agent == "agy" %}` in
  `.md.j2` sources (must be added to
  `aidocs/agent_runtime_guards_audit.md`).
  **Recommend (b)** when the tool-name divergence affects executable
  instructions (skills that tell the agent to run a specific tool).
- **Regenerate goldens** for any touched `.j2` source per CLAUDE.md
  ("Regenerate goldens after any `.md.j2` or closure edit").

**Verification:** Run `./.aitask-scripts/aitask_skill_verify.sh`; render
a sample skill with `--agent agy` and confirm the output dir is
`.agents/skills/<skill>-<profile>-agy-/SKILL.md`; run
`./.aitask-scripts/aitask_skill_rerender.sh fast` and verify codex and
agy outputs co-exist without overwriting.

---

### t835_3 — Add agy setup, install, release, tests (inverse of t812_3)

**Inverse blueprint:** `aiplans/archived/p812/p812_3_remove_geminicli_setup_install_release_tests.md`
(`### For t814 (add-agy): inverse instructions`).

**Files to touch:**
- `.aitask-scripts/aitask_setup.sh`:
  - `_is_agent_installed()` (L103) — add `agy) command -v agy &>/dev/null ;;`.
  - `assemble_aitasks_instructions()` docstring (L~974) —
    `agent_type:` enum add agy.
  - `update_agentsmd()` doc comment (L~1053).
  - "Other agents" orchestration (L~1960) — add
    `if _is_agent_installed agy; then setup_agy_cli; fi`.
  - `commit_framework_files()::check_paths` (L~2340) — usually NO
    `.agy/` dotdir needed (shared root); confirm per
    `aidocs/geminicli_to_agy.md`.
  - **New function `setup_agy_cli()`** modeled on `setup_codex_cli()`
    (L1718-1793). **Lighter** than codex: no policy install (agy reads
    `~/.gemini/policies/` globally per migration guide), so skip the
    equivalents of `merge_codex_settings()` and `merge_codex_rules()`.
    Copy any agy-specific helper docs (e.g. `agy_tool_mapping.md`,
    `agy_planmode_prereqs.md` — only if they exist; t835_2 may decide
    whether to create them or reuse codex's).
- `install.sh`:
  - **New `install_agy_staging()`** modeled on `install_codex_staging()`
    (L466-489). Likely no separate `agy_skills/` staging dir is needed
    if agy reuses `codex_skills/` via shared root — verify in t835_2;
    if agy is shipped from the same staged dir, this function may be a
    no-op stub or just copy any agy-only helper docs.
  - **New `install_seed_agy_config()`** modeled on
    `install_seed_codex_config()` (L530-548). Copies
    `seed/agy_instructions.seed.md` and `seed/models_agy.json`. Skip
    `agy_config.seed.toml` / `agy_rules.default.rules` (agy doesn't use
    them — global sandboxing).
  - Orchestration in main install flow (L969-972) — add agy calls.
  - `commit_installed_files()::check_paths` (L700) — usually mirror
    setup; agy share-root means probably no `.agy/` entry.
- `.github/workflows/release.yml`:
  - Codex build step (L47-94): the helper-doc copy loop (L57) — add agy
    helper doc names IF agy ships per-agent helper docs distinct from
    codex's. If agy reuses `codex_tool_mapping.md` content unchanged,
    skip. Tarball args (L94) usually do NOT need a new `agy_skills/`
    entry (shared root).
- `seed/`:
  - **New `seed/agy_instructions.seed.md`** — adapt codex's
    instructions seed (or geminicli's prior seed if more applicable),
    apply the tool-name updates (`run_shell_command` → `run_command`,
    `web_fetch` → `read_url_content`) per `aidocs/geminicli_to_agy.md`.
  - **New `seed/models_agy.json`** — stub with a single placeholder
    entry; will be replaced by `/aitask-refresh-code-models` output in
    t835_5.
  - Skip `seed/agy_settings.seed.json` and `seed/agy_policies/` per the
    migration guide.
- **New `tests/test_agy_setup.sh`** modeled on `tests/test_codex_setup.sh`
  (or whatever the codex setup-test file is named). At minimum: verify
  `setup_agy_cli()` is idempotent, creates expected dirs/files, exits
  non-zero on agy-absent if invoked directly.

**Verification:** Run `bash tests/test_agy_setup.sh`; run
`./ait setup --reinstall` in a throwaway dir and confirm agy is
detected when `agy` binary is on PATH; run `install.sh` end-to-end in a
clean dir to confirm install flow does not regress.

---

### t835_4 — Add agy to documentation (inverse of t812_4)

**Inverse blueprint:** `aiplans/archived/p812/p812_4_remove_geminicli_documentation.md`
(`### For t814 (add-agy): inverse instructions`).

**Files to touch:**

*Top-level prose:*
- `README.md`, `CLAUDE.md` — add `Antigravity CLI (agy)` to
  agent-enumeration prose, modeled on codex's row position. Apply
  CLAUDE.md's existing genericization rule: if a tagline already says
  "Claude Code and all other supported coding agents", leave it alone.
- `CHANGELOG.md` — add a new entry under the next pending release
  describing agy support.

*Skill closure sources (3 task-workflow + 3 standalone):*
- `.claude/skills/task-workflow/model-self-detection.md`
- `.claude/skills/task-workflow/satisfaction-feedback.md`
- `.claude/skills/task-workflow/plan-externalization.md`
- `.claude/skills/aitask-add-model/SKILL.md` (or `SKILL.md.j2` if
  templated)
- `.claude/skills/aitask-refresh-code-models/SKILL.md`
- `.claude/skills/aitask-audit-wrappers/SKILL.md`

*Website docs — normative enumerations (must add agy row):*
- `website/content/docs/commands/codeagent.md` (CLI mapping table and
  list-agents/list-models output examples).
- `website/content/docs/installation/known-issues.md` — add `## Antigravity CLI`
  H2 section modeled on Codex's section structure.
- `website/content/docs/installation/updating-model-lists.md` — add
  `agy` to agent list.
- `website/content/docs/installation/windows-wsl.md` — add `agy` to
  install instructions.
- `website/content/docs/skills/aitask-add-model.md` — new row in
  Supported Agents table.
- `website/content/docs/development/skills/aitask-audit-wrappers.md` —
  wrapper-tree + touchpoint tables (use IDs claimed in t835_2; do NOT
  reuse retired Gemini IDs 2 and 5).
- `website/content/docs/tuis/settings/{_index,how-to,reference}.md` —
  TUI value enumerations.

*Website docs — genericized surfaces (leave intact unless agy carries
editorial weight):* `_index.md`, `about/_index.md`, `docs/overview.md`,
`docs/getting-started.md`, `docs/skills/_index.md`,
`docs/installation/_index.md`, `docs/concepts/agent-attribution.md`,
`docs/concepts/verified-scores.md`,
`docs/skills/aitask-pick/commit-attribution.md`,
`docs/skills/aitask-refresh-code-models.md`,
`docs/tuis/board/how-to.md` — only edit if the enumeration is
normative.

*aidocs:*
- `aitasks_extension_points.md` — touchpoint table; add agy rows with
  IDs claimed in t835_2.
- `model_reference_locations.md` — model registry + supported-agents
  tables; add agy as `yes (limited)` (mirror codex's row).
- `issue_type_vocabulary_duplication.md` — add `seed/agy_instructions.seed.md`
  to the agent-identification note.
- `stub-skill-pattern.md` — §3g table row; bump "one stub per (skill,
  agent surface)" count from 3 to 4 stubs per skill.

*Regenerate goldens:*
After all source edits, run
`./.aitask-scripts/aitask_skill_rerender.sh <profile>` for each of
default/fast/remote, then regenerate
`tests/golden/procs/task-workflow/satisfaction-feedback-*.md` (and any
other affected goldens) **in the same commit** per CLAUDE.md.

**Optional:** Blog post under `website/content/blog/` announcing agy
support (defer-able to t835_5 or its own follow-up).

**Verification:** `cd website && ./serve.sh` and visually inspect each
edited page; `./.aitask-scripts/aitask_skill_verify.sh` for skill
stub/render consistency; `bash tests/test_*goldens*.sh` for golden
checks.

---

### t835_5 — agy cleanup, model refresh, and e2e verification (inverse of t812_5)

**Inverse blueprint:** `aiplans/archived/p812/p812_5_cleanup_pending_geminicli_aitasks.md`
(`### For t814 (add-agy): inverse instructions`).

**Absorbed fold concern:** `t835_2` (end-to-end agy detection
verification). Naturally lives here since it requires agy actually
running.

**Scope:**

1. **Run `/aitask-refresh-code-models` for agy** to replace the stub
   `seed/models_agy.json` + `aitasks/metadata/models_agy.json` with the
   real model catalogue. Commit the refreshed registries.

2. **Manual end-to-end verification** (the `t835_2` fold concern):
   - Launch agy: `agy` from the project root.
   - Invoke a workflow that triggers model self-detection (e.g.
     `/aitask-pick` on a test task).
   - Verify `./.aitask-scripts/aitask_parse_detected_agent.sh --agent
     agy --cli-id <model_id>` returns the expected
     `AGENT_STRING:agy/<name>`.
   - Verify `implemented_with` is written correctly to task
     frontmatter on completion.
   - If detection fails, loop back to t835_1's surface choice and
     adjust.

3. **Delete consumed reference doc:** `git rm aidocs/geminicli_to_agy.md`.
   The migration guide has been fully consumed by t835_1-4; the
   `### For t814 (add-agy): inverse instructions` subsections in the
   archived t812 plans are the durable load-bearing reference going
   forward. Per the parent task description, this file should be
   removed (not archived) at this point.

4. **Sanity grep:** confirm `agy` appears in all expected touchpoints
   (mirror of t812_5's "grep for geminicli to confirm clean removal").

**Verification:** Steps 1-3 above are themselves verifications; step 4
acts as a final coverage check.

---

---

### t835_6 — Audit, reorganize, and surface `adding_a_new_codeagent.md`

**Rationale (per user instruction):** Use the agy addition as
empirical ground truth to **audit and refresh
`aidocs/adding_a_new_codeagent.md`** so the next code-agent addition
has an accurate, well-ordered reference. This child runs **last**
(depends on t835_1-5) so it can compare the doc against the actual
implementation paths taken in those children.

The doc today has 23 sections (1339 lines) in roughly the order
sections were written, not the order an implementer should follow.
The agy implementation produces a known-good ordering: identity →
rendering → setup/install/release → user-facing docs → cleanup. This
child reshapes the doc to match.

**Files to touch:**
- `aidocs/adding_a_new_codeagent.md` — main audit + reorg target.
- `website/content/docs/development/` — new page or section linking
  to the aidocs reference (see step 4 below).
- `CLAUDE.md` — verify the `**Read `aidocs/adding_a_new_codeagent.md`**`
  pointer is still accurate and up-to-date.

**Scope:**

1. **Cross-reference against actual t835 implementation.** For each of
   sections 1-23 in `adding_a_new_codeagent.md`, walk the
   corresponding edits made in t835_1-5 (use `git log
   aiplans/archived/p835/` and the diffs against `main` since this
   parent task started). For each section:
   - Mark **accurate** sections that matched what we actually did.
   - Mark **stale** sections where line numbers, function names, or
     file paths drifted.
   - Mark **missing** touchpoints — anything t835 had to touch that
     isn't in the doc (e.g. a touchpoint discovered only at
     implementation time).
   - Mark **dead** content — references to retired agents (geminicli)
     that are now purely historical and should be moved to a "History"
     appendix or removed.

2. **Reorganize into logical implementation order.** Target order
   matches the t835 child split (this is the proven path):
   - **Phase A: Agent identity** (current §§2, 2a-2c, 3, 4, 5, 6, 7,
     8, 10) — the registries and dispatch surfaces.
   - **Phase B: Skill rendering** (current §§1, 1a-1g, 9, 12, 13, 14,
     15, 16) — render pipeline, audit-wrappers, contribute,
     codemap, helper docs, review-env.
   - **Phase C: Setup, install, release** (current §§17-22) — runtime
     install + packaging.
   - **Phase D: User-facing documentation** (current §23 + golden
     regen reminders).
   - **Phase E: Cleanup & verification** (new — distill the t835_5
     pattern: refresh model list, manual e2e verification, archive
     consumed reference docs).
   - **Phase F: Tests** (current §11 — cross-cuts all phases; either
     keep at the end as a checklist or split per-phase reminders).
   Section numbers may be renumbered; an "Implementation order"
   diagram at the top should map old → new IDs so external
   references in plan files still resolve.

3. **Deduplicate content.** Known duplications to consolidate:
   - The "helper-doc copy-loop tuple" is described in §17e, §18d,
     §19b, and again in §21 (the explicit fan-out section). Collapse
     to a single canonical description in §21 and replace the three
     in-line copies with cross-refs.
   - The `SUPPORTED_AGENTS` lockstep across 5 files is in §2b; verify
     no other section re-enumerates them.
   - The `× N agents` message string is in §8b's pickrem loop block
     and may be repeated in §17/§18; deduplicate.
   - Any other pattern duplicated 3+ times (per
     `aidocs/planning_conventions.md`).

4. **Surface in website docs.** Add a reference to
   `adding_a_new_codeagent.md` from the website so the doc is
   discoverable beyond an internal `aidocs/` grep:
   - **Recommended:** add a new page at
     `website/content/docs/development/adding-a-new-code-agent.md` (or
     under `docs/development/` if the section exists; create one if
     not). Page is a thin Hugo wrapper: short blurb explaining what
     the doc is for, who it is for (framework contributors adding a
     new code agent), and a link to the canonical aidocs file —
     **do not duplicate the aidocs content into the page**, per
     CLAUDE.md doc-conventions and DRY.
   - Add a sidebar/index link from `website/content/docs/development/_index.md`
     (or whichever index page lists per-development topics).
   - The aidocs file remains the source of truth; the website page
     is a discoverability surface.

5. **Verify against agent_runtime_guards_audit.md** if t835_2
   introduced any new `{% if agent == "agy" %}` Jinja gates — update
   that audit file too per CLAUDE.md.

**Verification:**
- Walk the reorganized doc top-to-bottom mentally executing each
  section against the agy diffs in `git log --oneline main..HEAD --
  .aitask-scripts/ seed/ install.sh .github/workflows/release.yml
  website/`. Every code change in those paths should map cleanly to
  exactly one section in the reorganized doc.
- `cd website && ./serve.sh` and confirm the new
  adding-a-new-code-agent page renders and links resolve.
- Open `aidocs/adding_a_new_codeagent.md` in a fresh context and
  read top-to-bottom as if planning a hypothetical "add the X agent"
  task — note any remaining clarity gaps and either fix them or log
  as follow-up.

---

## Aggregate manual-verification sibling (post-child-creation prompt)

After the 5 child plans are committed, the planning workflow will offer
to create an aggregate manual-verification sibling. **Recommended:
accept** with all 5 children selected. agy support is heavily
runtime-behavior (CLI launch, sandbox invocation, model detection,
prompt-pattern recognition) and unit tests cannot cover the full
loop. The seeded checklist will pull verification bullets from each
child's plan file.

## Critical files modified (parent plan summary)

The full file list is in each child plan above. The most impactful
single-file edits per touchpoint family:

- Identity: `.aitask-scripts/lib/agent_string.sh`,
  `.aitask-scripts/aitask_codeagent.sh`,
  `.aitask-scripts/lib/agent_model_picker.py`,
  `.aitask-scripts/stats/stats_data.py`.
- Rendering: `.aitask-scripts/lib/skill_template.py`,
  `.aitask-scripts/lib/agent_skills_paths.sh`,
  `.aitask-scripts/aitask_skill_rerender.sh`,
  `.aitask-scripts/aitask_audit_wrappers.sh`.
- Install: `.aitask-scripts/aitask_setup.sh`, `install.sh`,
  `.github/workflows/release.yml`.
- Docs: `README.md`, `CLAUDE.md`, the 14 website docs listed in t835_4,
  and 6 skill-closure sources.
- Reference: `aidocs/adding_a_new_codeagent.md` (reorg in t835_6) and
  a new website page that links to it.

## Child dependency graph

- t835_1 (identity) — depends on parent only.
- t835_2 (rendering) — depends on t835_1 (needs models_agy.json file
  path exposed in renderer surfaces).
- t835_3 (setup/install/release) — depends on t835_1 + t835_2 (needs
  skill rendering and identity in place to package).
- t835_4 (documentation) — depends on t835_1 + t835_2 + t835_3 (docs
  describe surfaces from earlier children).
- t835_5 (cleanup + verify) — depends on t835_1 through t835_4.
- t835_6 (aidocs reorg + website cross-ref) — depends on **all** prior
  children; runs last so the audit reflects the actual paths taken.

## Verification (parent-level, after all children complete)

End-to-end smoke per child:
- `./.aitask-scripts/aitask_codeagent.sh list-agents` shows agy.
- `./.aitask-scripts/aitask_skill_render.sh aitask-pick --profile fast
  --agent agy` produces `.agents/skills/aitask-pick-fast-agy-/SKILL.md`
  without colliding with codex.
- `./ait setup` detects agy when binary is on PATH and runs
  `setup_agy_cli()` cleanly.
- `agy` CLI session can pick a task end-to-end with correct
  `implemented_with` attribution (the aggregate manual-verification
  sibling covers this).
- All bash tests pass: `for f in tests/test_*.sh; do bash "$f"; done`.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.

## Step 9 reference

After all children archive, this parent task archives via the standard
Step 9 (Post-Implementation) flow in
`.claude/skills/task-workflow-fast-/SKILL.md`: merge approval,
verify_build (if configured), branch/worktree cleanup, archive script,
push. Per fast profile no separate branch was created here (working on
current branch).
