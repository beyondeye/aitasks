# Adding a New Code Agent to the aitasks Framework

End-to-end checklist for wiring a new code agent (Claude Code, Codex CLI,
OpenCode, agy, …) into the aitasks framework. Each section covers one
architectural concern. Sections are independent and can be addressed in any
order, but the order presented here is the path of least friction (no
rework, no temporary inconsistency).

> **Scope.** This doc covers what is needed *inside the aitasks framework*
> to make a new agent first-class: skill discovery, rendering, command
> wrappers, prompt-pattern detection, model-stats config, etc. It does
> **not** cover installing the agent's CLI itself (that lives in the
> agent vendor's docs).

## Index

- [1. Writing skills for agents that share `.agents/skills/`](#1-writing-skills-for-agents-that-share-agentsskills)
- [2. Agent identity layer (registries, CLI binary, model flag)](#2-agent-identity-layer-registries-cli-binary-model-flag)
- [3. Model registry file (`models_<agent>.json`)](#3-model-registry-file-models_agentjson)
- [4. Model picker UI (settings TUI + launch dialog)](#4-model-picker-ui-settings-tui--launch-dialog)
- [5. Stats: display name, registry scan, canonical id, display label](#5-stats-display-name-registry-scan-canonical-id-display-label)
- [6. `ait codeagent` invocation block + coauthor metadata](#6-ait-codeagent-invocation-block--coauthor-metadata)
- [7. Monitor prompt-pattern detection](#7-monitor-prompt-pattern-detection)
- [8. Settings TUI: config-file description + auto-rerender loop](#8-settings-tui-config-file-description--auto-rerender-loop)
- [9. Review-env detection (`.<agent>/skills/` path matchers)](#9-review-env-detection-agentskills-path-matchers)
- [10. `aitask add-model` whitelist + help text](#10-aitask-add-model-whitelist--help-text)
- [11. Test fixtures and assertions](#11-test-fixtures-and-assertions)
- [12. Wrapper templates (`aitask_audit_wrappers.sh`)](#12-wrapper-templates-aitask_audit_wrapperssh)
- [13. Policy / whitelist touchpoints](#13-policy--whitelist-touchpoints)
- [14. Contribution-area registry (`aitask_contribute.sh`)](#14-contribution-area-registry-aitask_contributesh)
- [15. Codemap framework-dirs set](#15-codemap-framework-dirs-set)
- [16. Shared helper docs in `.agents/skills/`](#16-shared-helper-docs-in-agentsskills)
- [17. Setup CLI orchestration (`aitask_setup.sh`)](#17-setup-cli-orchestration-aitask_setupsh)
- [18. Install staging (`install.sh`)](#18-install-staging-installsh)
- [19. Release packaging (`.github/workflows/release.yml`)](#19-release-packaging-githubworkflowsreleaseyml)
- [20. Seed assets (`seed/<agent>_*`)](#20-seed-assets-seedagent_)
- [21. Helper-doc copy-loop fan-out (3 sites in lockstep)](#21-helper-doc-copy-loop-fan-out-3-sites-in-lockstep)
- [22. Per-agent runtime dotdir (gitignore-skip / framework-paths)](#22-per-agent-runtime-dotdir-gitignore-skip--framework-paths)
- [23. User-facing documentation & skill-closure files](#23-user-facing-documentation--skill-closure-files)

*(More sections to be added as the migration playbook expands.)*

---

## 1. Writing skills for agents that share `.agents/skills/`

Some agents target the same **physical skills directory** as another
existing agent. Today that is Codex CLI (`.agents/skills/`); when agy
lands (t814) it will share that root too. Without disambiguation, two
agents writing their rendered SKILL.md into the same directory would
overwrite each other.

The framework solves this by adding an **agent-id segment** to the
rendered-dir name for any agent declared as `shared_skills_root: true`.
Non-shared agents (claude, opencode) keep the simpler
`<skill>-<profile>-/` form unchanged.

### 1a. Rendered-path naming

| Agent | `agent_skill_root` | Shared? | Rendered SKILL.md path |
|-------|-------------------|---------|-----------------------|
| claude | `.claude/skills` | no | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| codex | `.agents/skills` | **yes** | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| opencode | `.opencode/skills` | no | `.opencode/skills/<skill>-<profile>-/SKILL.md` |
| *new shared-root agent* | (same as another) | **yes** | `<root>/<skill>-<profile>-<agent>-/SKILL.md` |

The trailing hyphen is preserved on both forms so the single `*-/`
gitignore glob per agent root still matches every rendered dir.

### 1b. Declare the shared-root flag

The "shared root" set is an **explicit per-agent property** (kept in
sync alongside `agent_skill_root` so adding a new agent is a single
diff in each file).

1. **Bash** — `.aitask-scripts/lib/agent_skills_paths.sh`: add the new
   agent to both `agent_skill_root()` and `agent_shared_skills_root()`.

   ```bash
   agent_skill_root() {
       case "$1" in
           claude)   echo ".claude/skills" ;;
           codex)    echo ".agents/skills" ;;
           agy)      echo ".agents/skills" ;;        # NEW
           opencode) echo ".opencode/skills" ;;
           *)        echo "agent_skill_root: unknown agent: $1" >&2; return 1 ;;
       esac
   }

   agent_shared_skills_root() {
       case "$1" in
           claude)   echo "false" ;;
           codex)    echo "true"  ;;
           agy)      echo "true"  ;;                 # NEW (shares .agents/skills)
           opencode) echo "false" ;;
           *)        echo "agent_shared_skills_root: unknown agent: $1" >&2; return 1 ;;
       esac
   }
   ```

2. **Python** — `.aitask-scripts/lib/skill_template.py`: add the
   matching entries to `AGENT_ROOTS` and `AGENT_SHARED_SKILLS_ROOT`.

   ```python
   AGENT_ROOTS = {
       "claude":   ".claude/skills",
       "codex":    ".agents/skills",
       "agy":      ".agents/skills",      # NEW
       "opencode": ".opencode/skills",
   }
   AGENT_SHARED_SKILLS_ROOT = {
       "claude":   False,
       "codex":    True,
       "agy":      True,                  # NEW
       "opencode": False,
   }
   ```

`_render_dir_name(skill, profile_name, agent)` consults
`AGENT_SHARED_SKILLS_ROOT` and automatically emits
`<skill>-<profile>-<agent>-` for shared-root agents,
`<skill>-<profile>-` otherwise — no other code path needs to special-case
the new agent.

### 1c. Update the renderer driver loop

`.aitask-scripts/aitask_skill_rerender.sh` iterates a hardcoded list of
agents. Add the new agent name to the `for agent in claude codex …`
loop. The script already picks the correct find-glob and suffix-strip
based on `agent_shared_skills_root` — no further changes inside the
loop body.

```bash
for agent in claude codex agy opencode; do   # NEW agent inserted
    ...
done
```

**Hardcoded agent enums to update in lockstep.** The renderer driver
loop is one of several places that hardcodes the full agent set. When
adding (or retiring) an agent, update every site below — there is no
single source of truth that all of them consult at runtime:

- `.aitask-scripts/aitask_skill_render.sh` — `--agent` help text (the
  list shown by `--help`).
- `.aitask-scripts/aitask_skillrun.sh` — per-agent `CMD` `case`
  controlling how each agent's CLI is invoked (binary, model flag,
  argv shape).
- `.aitask-scripts/aitask_skill_rerender.sh` — outer agent loop.
- `.aitask-scripts/aitask_skill_verify.sh` — `agents=(...)` array used
  for render/walk/stub validation, plus `_stub_path_for()` case that
  resolves the per-agent stub path.
- `.aitask-scripts/aitask_audit_wrappers.sh` — `cmd_discover()` trees
  enum and `wrapper_path()` / `cmd_render_wrapper()` cases.
- `.aitask-scripts/lib/skill_template.py` — `AGENT_ROOTS`,
  `AGENT_SHARED_SKILLS_ROOT`, the `FULL_PATH_REF_RE` regex alternation,
  and the parts-validity tuple in `_skill_name_from_source()`.
- `.aitask-scripts/lib/agent_skills_paths.sh` — `agent_skill_root()`
  and `agent_shared_skills_root()` cases (covered in §1b).

### 1d. Write the per-agent stub

Each skill needs a committed stub at the agent's authoring location
(see `aidocs/framework/stub-skill-pattern.md` §3g for the per-agent surface
table). For shared-root agents the stub MUST point at the
agent-suffixed Read path:

```markdown
3. **Dispatch via Read-and-follow.** Read the file at
   `.agents/skills/<skill>-<profile>-<agent>-/SKILL.md` and execute its
   instructions ...
```

For example, the agy stub at `.agents/skills/<skill>/SKILL.md` reads
from `.agents/skills/<skill>-<profile>-agy-/SKILL.md` and renders with
`--agent agy`. This keeps each agent's runtime invocation independent
of its sibling agents that share the same physical root.

> **Don't substitute runtime checks for prerendering.** It is tempting
> to write a single shared stub body with `{% if agent == "agy" %}` /
> `{% if agent == "codex" %}` branches. The framework explicitly
> rejected that approach during t812 planning (see the
> `feedback_shared_skill_path_extend_suffix` memory). The per-agent
> prerender is load-bearing — it is how each agent gets agent-specific
> tool names, paths, and workflow branches without conditional bloat in
> skill bodies. Extend the prerender mechanism; do not collapse to
> runtime checks.

### 1e. Pre-rendered headless variants (if applicable)

Skills that ship as headless (`prerender_for_headless: true` in the
`.j2`, paired with a `headless: true` profile — today: `aitask-pickrem`
and `aitask-pickweb` with the `remote` profile) get their rendered
output committed to git so they work on machines where `ait setup` has
not run.

When you add a new shared-root agent:

1. Render each headless `(skill, profile)` pair for the new agent
   ```bash
   ./.aitask-scripts/aitask_skill_render.sh aitask-pickrem --profile remote --agent <agent> --force
   ./.aitask-scripts/aitask_skill_render.sh aitask-pickweb --profile remote --agent <agent> --force
   ```
   The walker also writes the transitive `task-workflow-remote-<agent>-/`
   closure.

2. Add the new agent-suffixed dirs to `.gitignore`'s negation block:
   ```
   !.agents/skills/aitask-pickrem-remote-<agent>-/
   !.agents/skills/aitask-pickweb-remote-<agent>-/
   !.agents/skills/task-workflow-remote-<agent>-/
   ```

3. Commit the new directories.

`aitask_skill_verify.sh`'s `PRERENDER_FAIL` check composes the expected
path via `agent_skill_dir`, so the new agent is automatically validated
once it appears in `agent_skills_paths.sh`.

### 1f. Regenerate tests and goldens

Per `aidocs/framework/skill_authoring_conventions.md`, any change touching the
rendering pipeline must regenerate goldens in the **same commit** as the
source edit. Specifically:

- Walk-write goldens (Test 4 in each `tests/test_skill_render_*.sh`)
  capture the per-agent reference rewriting — adding a new agent means
  these tests need a new `assert_contains` line for the new agent's
  rewritten ref path (e.g.,
  `.agents/skills/task-workflow-fast-<agent>-/SKILL.md`).
- `tests/test_skill_template.sh` has explicit assertions for
  `agent_skill_dir`, `agent_shared_skills_root`, and `rewrite_ref` per
  agent — extend them with the new agent's expected values.
- Pre-rewrite goldens in `tests/fixtures/skills/**` are agent-invariant
  and do NOT change.

Run before committing:

```bash
./.aitask-scripts/aitask_skill_verify.sh
bash tests/test_skill_template.sh
bash tests/test_skill_render_uniform.sh
for t in tests/test_skill_render_aitask_*.sh tests/test_skill_render_task_workflow.sh; do bash "$t"; done
bash tests/test_skill_rerender.sh
bash tests/test_skill_verify.sh
bash tests/test_skill_parity_runtime_vs_rendered.sh
```

### 1g. Canonical reference

The full canonical pattern for stubs lives in
`aidocs/framework/stub-skill-pattern.md` — read it for the stub body templates per
agent surface, the resolver-key convention, the argument-forwarding
contract, and the reference-resolution rules for `.j2` cross-skill
refs. This section is the *adding-a-new-agent* checklist; that doc is
the *what each stub must look like* spec.

---

## 2. Agent identity layer (registries, CLI binary, model flag)

The "agent identity layer" is the single source of truth for what agent
names exist, which CLI binary each one shells out to, and which flag is
used to pass the model id. Adding a new agent here is the prerequisite
for everything below — `aitask_codeagent.sh`, `aitask_skillrun.sh`,
stats, the picker UI, and the verified/usage trackers all parse agent
strings through this layer.

### 2a. `lib/agent_string.sh` (canonical agent registry)

`.aitask-scripts/lib/agent_string.sh` is sourced by every script that
needs to translate `<agent>/<model>` into a CLI invocation. Three
locations need a new branch per agent:

```bash
# 1. The canonical list of supported agent names
SUPPORTED_AGENTS=(claudecode codex opencode <new-agent>)

# 2. CLI binary mapping (used by `ait codeagent invoke`)
get_cli_binary() {
    case "$1" in
        claudecode) echo "claude" ;;
        codex)      echo "codex"  ;;
        opencode)   echo "opencode" ;;
        <new-agent>) echo "<binary-name>" ;;        # NEW
        *) die "Unknown agent: '$1'" ;;
    esac
}

# 3. Model-selection flag (passed before the model id)
get_model_flag() {
    case "$1" in
        claudecode) echo "--model" ;;
        codex)      echo "-m"      ;;
        opencode)   echo "--model" ;;
        <new-agent>) echo "<flag>" ;;                # NEW
        *) die "Unknown agent: '$1'" ;;
    esac
}
```

If the agent string format diverges (e.g. accepts a different model-id
character set), update the regex in `parse_agent_string` too — but the
default `^[a-z]+/[a-z0-9_]+$` covers most real CLIs.

### 2b. Other `SUPPORTED_AGENTS` arrays (kept in lockstep)

`agent_string.sh` is the canonical list, but several scripts re-declare
`SUPPORTED_AGENTS` as a local array because they also call out to
`models_<agent>.json` and want a self-contained iteration list:

| File | What it iterates |
|------|------------------|
| `.aitask-scripts/aitask_resolve_detected_agent.sh` | Validates `--agent` flag, walks `models_<agent>.json` for cli_id → name resolution |
| `.aitask-scripts/aitask_verified_update.sh` | Rolling verifiedstats updates (`--agent NAME` help text + accept-list) |
| `.aitask-scripts/aitask_usage_update.sh` | Rolling usagestats updates (mirror of verified_update) |
| `.aitask-scripts/aitask_add_model.sh` | `add-json` / `promote-config` subcommand input validation |
| `.aitask-scripts/stats/stats_data.py` | `load_model_cli_ids()` and `load_verified_rankings()` / `load_usage_rankings()` agent loops |

Adding a new agent means adding it to **all** of these in the same
commit — the verifier (`./.aitask-scripts/aitask_skill_verify.sh`) does
not currently cross-check these arrays against each other; tests are
the safety net (see §11).

### 2c. The agent-string resolver

`./.aitask-scripts/aitask_resolve_detected_agent.sh` is the script every
code-agent attribution flow calls to convert raw runtime metadata
(`--agent claudecode --cli-id claude-opus-4-7`) into the canonical
agent string (`claudecode/opus4_7`). Beyond the `SUPPORTED_AGENTS`
update from §2b, no agent-specific branching exists — the script reads
`models_<agent>.json` and looks for an exact `cli_id` match. The only
opt-in agent-specific behavior today is **opencode suffix matching**
(stripping provider prefixes); document any new normalization rule the
new agent needs here if it deviates from the exact-match default.

---

## 3. Model registry file (`models_<agent>.json`)

Each first-class agent has a `aitasks/metadata/models_<agent>.json`
file listing the models the agent supports, along with `cli_id`,
`name`, optional `status`, `notes`, and per-skill `verifiedstats` /
`usagestats` rolling buckets.

When adding a new agent:

1. Seed the file with at least one entry. The lowest-friction path is
   `ait codeagent` won't crash on `list-models <agent>` if the file
   exists, even if empty.
2. The file is read by:
   - `lib/agent_string.sh::get_cli_model_id` (jq) — translates a `name`
     to the raw `cli_id` for invocation
   - `lib/agent_model_picker.py::MODEL_FILES` — UI picker registration
   - `stats/stats_data.py::load_model_cli_ids` and
     `load_verified_rankings` / `load_usage_rankings`
   - `aitask_add_model.sh` for `add-json` mutation
3. **Refresh flow:** `aitask-refresh-code-models` is the supported way
   to populate the file from upstream sources (opencode is currently
   provider-gated and discovered via the CLI; other agents are added
   manually via `aitask_add_model.sh add-json`). Decide which path your
   new agent uses and document it under "Supported agents" in
   `aitask_add_model.sh`'s help text (§10 below).

---

## 4. Model picker UI (settings TUI + launch dialog)

`.aitask-scripts/lib/agent_model_picker.py` is the shared Textual
modal screen used by the settings TUI and the launch dialog to choose
an `<agent>/<model>` pair.

Two places need a new entry per agent:

```python
# 1. MODEL_FILES — where to read the registry from
MODEL_FILES = {
    "claudecode": METADATA_DIR / "models_claudecode.json",
    "codex":      METADATA_DIR / "models_codex.json",
    "opencode":   METADATA_DIR / "models_opencode.json",
    "<new>":      METADATA_DIR / "models_<new>.json",   # NEW
}

# 2. AgentModelPickerScreen._MODES — per-agent fuzzy-list tab
_MODES: list[tuple[str, str]] = [
    ("top",        "Top verified models (recent)"),
    ("top_usage",  "Top by usage (recent)"),
    ("all",        "All models"),
    ("codex",      "All codex models"),
    ("opencode",   "All opencode models"),
    ("claudecode", "All Claude models"),
    ("<new>",      "All <Display> models"),             # NEW
]
```

Update the module docstring's mode-count line too (`...cycles through
seven modes...`).

---

## 5. Stats: display name, registry scan, canonical id, display label

`.aitask-scripts/stats/stats_data.py` is the canonical stats engine for
`ait stats` and the board's stats pane. Four touchpoints per agent:

```python
# 5a. AGENT_DISPLAY_NAMES — human-readable name (per-agent leaderboard,
#     CSV exports, board pane headers)
AGENT_DISPLAY_NAMES = {
    "claudecode": "Claude Code",
    "codex":      "Codex",
    "opencode":   "OpenCode",
    "<new>":      "<Display Name>",   # NEW
    "unknown":    "Unknown",
}

# 5b. load_model_cli_ids() agent loop
for agent in ("claudecode", "codex", "opencode", "<new>"):   # NEW
    ...

# 5c. load_verified_rankings() / load_usage_rankings() agent tuples
agents = ("claudecode", "codex", "opencode", "<new>")        # NEW (TWO sites)
```

If the new agent's `cli_id` format isn't slugified correctly by the
default `slugify_key`, add a regex branch in `canonical_model_id` and a
matching display branch in `model_display_from_cli_id`:

```python
# 5d. Optional: canonical_model_id branch (e.g. claude → opus4_7)
match = re.match(r"^<your-cli-id-shape>$", value)
if match:
    ...
    return f"<canonical_key>"

# 5d. Optional: model_display_from_cli_id branch
match = re.match(r"^<your-cli-id-shape>$", value)
if match:
    ...
    return "<Display Label>"
```

Only add these branches if the default behavior produces ugly or
ambiguous output — most agents do fine with the fallback.

---

## 6. `ait codeagent` invocation block + coauthor metadata

`.aitask-scripts/aitask_codeagent.sh` is the unified wrapper that
launches a code agent for an `<operation>` (pick, explain, qa, …).
Three sites need a new branch per agent:

```bash
# 6a. get_agent_coauthor_name() — used for Co-Authored-By trailers
case "$agent" in
    codex)
        cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
        if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
            echo "Codex/$(format_codex_model_label "$cli_id")"
        else
            echo "Codex/$model_name"
        fi
        ;;
    <new-agent>)                                            # NEW
        cli_id="$(lookup_cli_model_id_if_known "$agent" "$model_name")"
        if [[ -n "$cli_id" && "$cli_id" != "null" ]]; then
            echo "<Display>/$(format_<new>_model_label "$cli_id")"
        else
            echo "<Display>/$model_name"
        fi
        ;;
    ...
esac

# 6b. get_agent_coauthor_email() — Co-Authored-By email
case "$agent" in
    codex)      echo "codex@$domain"      ;;
    claudecode) echo "claudecode@$domain" ;;
    opencode)   echo "opencode@$domain"   ;;
    <new>)      echo "<new>@$domain"      ;;               # NEW
esac

# 6c. build_invoke_command() — how to launch the operation
case "$PARSED_AGENT" in
    claudecode) ... ;;
    codex)      ... ;;
    opencode)   ... ;;
    <new-agent>)                                            # NEW
        case "$operation" in
            pick)    CMD+=("/aitask-pick ${args[*]}") ;;
            explain) CMD+=("/aitask-explain ${args[*]}") ;;
            qa)      CMD+=("/aitask-qa ${args[*]}") ;;
            explore) CMD+=("/aitask-explore") ;;
            batch-review|raw) CMD+=("${args[@]}") ;;
        esac
        ;;
esac
```

If the new agent labels cli_ids using a non-trivial shape (similar to
how Claude has `format_claude_model_label`), add a
`format_<agent>_model_label()` helper above `get_agent_coauthor_name`
and call it from §6a. Skip the helper if the bare `cli_id` is already
human-readable.

Also touch:
- The header comment at the top of `aitask_codeagent.sh` — list the new
  agent in the "Supports Claude Code, …" sentence and the agent-string
  example.
- The `--help` text near the bottom (`Agent string format: …`) and the
  `Examples:` list.

### 6d. The dispatch wrapper (`aitask_skillrun.sh`)

`.aitask-scripts/aitask_skillrun.sh` dispatches `ait skillrun <skill>
--agent-string <a>/<m> -- <args>` to the right CLI invocation. Add a
new branch to the `case "$PARSED_AGENT"` block that builds the per-agent
launch command (mirror of §6c). The header docstring also lists the
recognized agents — keep it in sync.

---

## 7. Monitor prompt-pattern detection

`ait monitor` flags agents stuck on a confirmation prompt
("awaiting user input" rather than "idle"). The detection layer is
`.aitask-scripts/monitor/prompt_patterns.py`. Add an entry to
`PROMPT_PATTERNS_BY_AGENT`:

```python
PROMPT_PATTERNS_BY_AGENT: dict[str, list[PromptPattern]] = {
    "claude":   [...],
    "codex":    [...],
    "opencode": [],
    "<new>":    [],   # NEW — empty entry is fine for a first-pass add
    "all":      [],
}
```

The dict key is the **monitor-side agent shortname**, which is NOT
necessarily the `agent_string.sh` name. The mapping is informal today
(e.g. claude vs. claudecode) — pick the name that
matches existing usage in `ait monitor`'s codepath.

Patterns are populated when an agent's prompt wording is observed in
practice; an empty list is a valid no-op until you have a pattern to
add. See `aidocs/framework/monitor_idle_and_prompt_detection.md` for the pattern
authoring spec.

---

## 8. Settings TUI: config-file description + auto-rerender loop

Two sites in `.aitask-scripts/settings/settings_app.py`:

```python
# 8a. CONFIG_FILE_DESCRIPTIONS — shown during the import-config picker
CONFIG_FILE_DESCRIPTIONS: dict[str, str] = {
    ...
    "models_claudecode.json": "Claude Code model list and verification scores",
    "models_codex.json":      "Codex CLI model list and verification scores",
    "models_opencode.json":   "OpenCode model list and verification scores",
    "models_<new>.json":      "<Display Name> model list and verification scores",  # NEW
}

# 8b. pickrem auto-rerender loop — re-renders aitask-pickrem when the
#     remote.yaml profile changes. Two parallel sites:

#     The agent tuple (also update the "× N agents" message string)
for agent in ("claude", "codex", "opencode", "<new>"):    # NEW
    ...

#     The root_map in _pickrem_rendered_paths
root_map = {
    "claude":   ".claude/skills",
    "codex":    ".agents/skills",
    "opencode": ".opencode/skills",
    "<new>":    "<.new/skills>",                          # NEW
}
```

The auto-rerender loop uses the **agent name passed to
`aitask_skill_render.sh --agent`** (the short name like `claude`,
`codex`), NOT the canonical `agent_string.sh` name (`claudecode`,
`codex`, `opencode`). Match the convention used by the renderer.

---

## 9. Review-env detection (`.<agent>/skills/` path matchers)

`.aitask-scripts/aitask_review_detect_env.sh` boosts the "aiagents"
language score when the diff touches an agent config directory. Extend
the path-match conditional:

```bash
if [[ "$f" == .claude/skills/*   || "$f" == .claude/commands/*    \
   || "$f" == .opencode/skills/* || "$f" == .opencode/commands/*  \
   || "$f" == .codex/prompts/*   || "$f" == .agents/skills/*      \
   || "$f" == .<new>/skills/*    || "$f" == .<new>/commands/* ]]; then  # NEW
    add_score "aiagents" "$weight"
    found_aiagents_dir=true
fi
```

Also update the comment one line above (`# AI Agent config directories
(.claude/, …)`).

If the new agent shares a directory with an existing one (e.g. agy
shares `.agents/skills/` with codex), the existing `.agents/skills/*`
branch already covers it — no edit needed here.

---

## 10. `aitask add-model` whitelist + help text

`.aitask-scripts/aitask_add_model.sh` registers a known model in a
`models_<agent>.json`. Add the new agent to:

```bash
# 10a. Input-validation array
SUPPORTED_AGENTS=(claudecode codex <new>)   # NEW

# 10b. --help text "Supported agents:" line
Supported agents: claudecode, codex, <new>.
Use aitask-refresh-code-models for opencode (provider-gated, CLI-discovered).
```

Decide whether the new agent's models come from `aitask add-model`
(manual) or from `aitask-refresh-code-models` (automated discovery) and
document the choice in the help text alongside the existing opencode
note.

---

## 11. Test fixtures and assertions

Several test files assert per-agent behavior. After a new-agent add,
regenerate / extend:

| Test file | What needs updating |
|-----------|---------------------|
| `tests/test_agent_string.sh` | `get_cli_binary <new>` / `get_model_flag <new>` assertions |
| `tests/test_resolve_detected_agent.sh` | `=== Test: exact match <new> ===` block with a known `cli_id` → canonical name |
| `tests/test_codeagent.sh` | `models_<new>.json` fixture copy in `setup_test_env`, `list-agents shows <new>` assertion, `coauthor <new>/<model>` test block (mirror of the Codex/OpenCode tests) |
| `tests/test_add_model.sh` | `promote-default-agent-string` rejection test (uses a non-claudecode agent argument; any of the supported non-claudecode agents works) |
| `tests/test_stats_data.sh`, `tests/test_stats_verified_rankings.sh` | Both pass without changes if the agent is added to `AGENT_DISPLAY_NAMES` and the loader tuples; add explicit assertions only if the agent has special canonical-id rules |

Run after editing:

```bash
bash tests/test_agent_string.sh
bash tests/test_resolve_detected_agent.sh
bash tests/test_codeagent.sh
bash tests/test_add_model.sh
bash tests/test_stats_data.sh
bash tests/test_stats_verified_rankings.sh
```

### 11a. Skill-rendering test footprint

The §1 (skill rendering) layer carries an additional test footprint
that is hit on every agent add/remove:

**Per-skill render tests** — one file per user-invokable skill, each
hard-coding the full agent set:

```
tests/test_skill_render_aitask_explore.sh
tests/test_skill_render_aitask_fold.sh
tests/test_skill_render_aitask_pick.sh
tests/test_skill_render_aitask_pickrem.sh
tests/test_skill_render_aitask_pickweb.sh
tests/test_skill_render_aitask_pr_import.sh
tests/test_skill_render_aitask_qa.sh
tests/test_skill_render_aitask_review.sh
tests/test_skill_render_aitask_revert.sh
tests/test_skill_render_aitask_wrap.sh
tests/test_skill_render_task_workflow.sh
```

Each contains an `AGENTS=(claude codex opencode)` array, inner
per-agent loops (`for agent in codex opencode; …`), and a per-agent
stub block (today: only `.opencode/commands/<skill>.md` and
`.agents/skills/<skill>/SKILL.md` — see §1d). When adding a new agent,
extend `AGENTS=`, mirror the codex stub-assertion block, and add a
cross-agent rewrite assertion checking that refs from `.claude/skills`
are rewritten to the new agent's root.

**Framework-level skill tests** — touch the renderer / verifier itself:

```
tests/test_skill_template.sh           # agent_skill_root / _shared_skills_root / rewrite_ref
tests/test_skill_render.sh             # end-to-end render via aitask_skill_render.sh
tests/test_skill_render_uniform.sh     # cross-agent path-rewriting parity
tests/test_skill_rerender.sh           # AGENT_ROOTS array + per-agent rerender loop
tests/test_skill_verify.sh             # stub-pattern + render + closure walk
```

These need updates whenever the agent enum changes; some assert specific
agent root paths (e.g. `.opencode/skills`), others enumerate `AGENT_ROOTS`
or the stub-path mapping directly.

---

## 12. Wrapper templates (`aitask_audit_wrappers.sh`)

For agents that ship as **wrappers around the Claude Code source of
truth** (today: Codex CLI, OpenCode), `aitask_audit_wrappers.sh`
renders and applies the per-agent stub `SKILL.md` (or `.toml` /
`.md` command) from a template embedded in the script.

### 12a. Per-tree renderer functions

Each "tree" (output flavor) has its own renderer:

| Tree | Output path | Renderer function |
|------|-------------|-------------------|
| `agents` | `.agents/skills/<skill>/SKILL.md` | `render_agents_skill()` |
| `opencode-skill` | `.opencode/skills/<skill>/SKILL.md` | `render_opencode_skill()` |
| `opencode-command` | `.opencode/commands/<skill>.md` | `render_opencode_command()` |

Adding a new agent that needs its own wrapper tree (e.g., a
`gemini`-style `<agent>/commands/<skill>.toml` flavor) requires:

1. Add the tree name to the `tree in agents opencode-skill …` list in
   `cmd_discover()`.
2. Add a `wrapper_path()` case mapping the tree to its on-disk path.
3. Add a `render_<tree>_<kind>()` function emitting the stub body.
4. Add a `cmd_render_wrapper()` case routing the tree to the renderer.
5. Add the tree to the Trees table in `usage()`.

### 12b. Templated vs non-templated stubs

`render_agents_skill()` and `render_opencode_skill()` each branch on
`_skill_is_templated()`. Templated skills (those with a
`.claude/skills/<skill>/SKILL.md.j2` entry-point) emit a
profile-aware **stub** (resolve profile → run renderer → Read-and-follow
the per-profile rendered file). Non-templated skills emit a legacy
"Source of Truth" stub pointing at the Claude SKILL.md, with optional
per-agent "If you are <Agent> CLI: read <agent>_tool_mapping.md" lines.

When adding an agent, decide which template you need:

- **Shared-root agent with per-agent prerender** (codex pattern): the
  templated branch already emits `--agent <name>` and reads from
  `.agents/skills/<skill>-<profile>-<agent>-/SKILL.md`. Just point the
  renderer at the new agent name in the stub literal.
- **Non-templated wrapper** (legacy "Source of Truth"): if the new
  agent needs a per-agent tool-mapping prereq doc, add an "**If you
  are <Agent> CLI:** read `.agents/skills/<agent>_tool_mapping.md`"
  line in `render_agents_skill()` (mirroring how Codex is wired
  today) — see §16.

### 12c. Stub-refresh discipline

Editing any of the `render_*` functions affects **future renders only**
— stubs already committed to git keep their old content. After such a
change, re-apply each affected wrapper:

```bash
./.aitask-scripts/aitask_audit_wrappers.sh apply-wrapper <tree> <skill> --force
```

Non-templated skills hit this most often (the legacy "Source of Truth"
stub embeds per-agent prose); templated stubs are largely
self-contained but still need a refresh when the resolver-key or
agent suffix changes.

---

## 13. Policy / whitelist touchpoints

`aitask_audit_wrappers.sh::touchpoint_file()` enumerates the
permission/policy files that gate aitasks helper scripts across
supported agents. The numbering is **kept stable** even when
touchpoints are retired so callers that pass numeric IDs don't
silently shift to a different file.

Current touchpoints:

```
1 = .claude/settings.local.json                   (claudecode Bash permission)
3 = .codex/rules/default.rules                    (codex prefix_rule)
4 = seed/claude_settings.local.json               (seed mirror of #1)
6 = seed/codex_rules.default.rules                (seed mirror of #3)
7 = seed/opencode_config.seed.json                (opencode bash permission)
```

(IDs 2 and 5 were the gemini runtime/seed policies, retired in t812_2.)

When adding an agent:

1. Pick the next free numeric ID (do **not** reuse a retired ID — keep
   them stable too). Add the file path in `touchpoint_file()`.
2. Add a matching case to `helper_present_in_touchpoint()`.
3. Add the apply-side helper (e.g. a per-agent `insert_…_line()`) and
   route it in `cmd_apply_helper_whitelist()`.
4. Add the ID to the `for touchpoint in 1 3 4 6 7; do …` loops in
   `cmd_audit_helper_whitelist()` and `cmd_apply_helper_whitelist()`.
5. Update the Touchpoints table in `usage()`.

When **retiring** an agent's touchpoint(s): zero out the cases (no
reuse) and drop the IDs from the iteration loops only — leave the
numeric slots vacant.

---

## 14. Contribution-area registry (`aitask_contribute.sh`)

`aitask_contribute.sh` lets users file framework contributions against
a named area. Each area binds a name → directory roots → description.

```bash
AREAS=(
    "scripts|.aitask-scripts/|Core scripts (shell and Python)"
    "claude-skills|.claude/skills/|Claude Code skills"
    "codex|.agents/skills/|Codex CLI skills"
    "opencode|.opencode/skills/,.opencode/commands/|OpenCode skills and commands"
    "website|website/|Website documentation (clone/fork mode only)"
)
```

To register a new agent:

1. Add a `"<agent>|<comma-separated-paths>|<description>"` entry to
   `AREAS` at the alphabetical position alongside its siblings.
2. Update the `--area` choices in the help text (in `usage()`) to
   include the new name.

To retire an agent: delete the matching entry and update the help text.

---

## 15. Codemap framework-dirs set

`.aitask-scripts/aitask_codemap.py`'s `FRAMEWORK_DIRS` set declares
the top-level directories `ait codemap` excludes by default (unless
`--include-framework-dirs` is passed). Any per-agent root that lives
at the repo root must be listed here:

```python
FRAMEWORK_DIRS = {
    ".aitask-scripts",
    "aitasks",
    "aiplans",
    "aireviewguides",
    ".claude",
    ".agents",
    ".opencode",
    "seed",
}
```

When adding an agent with a root at the repo top level
(`<root>/skills/...`, `<root>/commands/...`), add the root path here.
Also update the same enumeration in the usage doc string of the bash
wrapper (`aitask_codemap.sh`) so `--help` stays in sync.

---

## 16. Shared helper docs in `.agents/skills/`

Non-templated wrappers for codex (and future shared-root agents) read
per-agent tool-mapping docs (and plan-mode prereq docs where an agent
needs them) from `.agents/skills/`:

- `.agents/skills/codex_tool_mapping.md` — codex-specific tool-name
  translations from the Claude source (e.g., what `Read` maps to).

`render_agents_skill()` emits "If you are <Agent> CLI: read
`.agents/skills/<agent>_tool_mapping.md`" lines for each such agent.

When adding an agent that needs per-agent prereqs:

1. Create `.agents/skills/<agent>_tool_mapping.md` (and
   `<agent>_planmode_prereqs.md` if applicable). Mirror the structure
   of `.agents/skills/codex_tool_mapping.md`.
2. Add the matching "If you are …" line to `render_agents_skill()`
   (and to `render_opencode_skill()` if the agent also lands in
   opencode's tree).
3. Re-apply every affected non-templated wrapper stub
   (`apply-wrapper agents <skill> --force`) so the new "If you are …"
   line lands in the committed stubs.

When retiring an agent: `./ait git rm` its helper doc(s), remove
the "If you are …" line(s), and re-apply every affected stub to flush
the now-dangling references.

## 17. Setup CLI orchestration (`aitask_setup.sh`)

`.aitask-scripts/aitask_setup.sh` runs `ait setup` for the user — it
detects which agent CLIs are installed on PATH and invokes a per-agent
`setup_<agent>_cli()` function for each one found. The canonical
worked example below is **`setup_codex_cli`** (codex has the lighter
footprint analogous to what agy will need: no policy install, no
global merge).

### 17a. `_is_agent_installed()` case branch

Near the top of the script (currently around line 100), the
`_is_agent_installed()` helper has a `case` block mapping agent name to
a `command -v <cli>` check:

```bash
_is_agent_installed() {
    case "$1" in
        claude)    command -v claude &>/dev/null ;;
        codex)     command -v codex &>/dev/null ;;
        opencode)  command -v opencode &>/dev/null ;;
        *)         return 1 ;;
    esac
}
```

Add a `<agent>)` clause whose body is `command -v <cli> &>/dev/null`.
The `<cli>` is the binary name the user invokes (e.g., `codex`,
`opencode`).

### 17b. `setup_<agent>_cli()`

Main per-agent installer. Resolves staging dirs under
`aitasks/metadata/<agent>_*`, copies them into the per-agent runtime
dirs (`.<agent>/skills`, `.<agent>/commands`, …), writes the assembled
Layer-2 instructions via `assemble_aitasks_instructions "$project_dir"
"<agent>"`, and (for agents that support policies) invokes the
optional policy helpers from §17c.

Use `setup_codex_cli` as the template if the new agent has no policy
support. Use a previously deleted `setup_<agent>_cli` (consult git
history of `aitask_setup.sh` for the closest analogue) only if the
agent needs per-project policy files — most modern agents do not.

### 17c. Optional policy helpers

Only required for agents that support per-project policy files (none
currently — the Gemini CLI variant was retired in t812_3). When
needed, mirror the deleted pattern:

- `merge_<agent>_policies(seed_file, dest_file)` — TOML/JSON
  rule-merge logic, deduplicating by tool/command identifier.
- `merge_<agent>_settings(seed_file, dest_file)` — settings.json
  merge (e.g., `policyPaths` list union).
- `install_<agent>_global_policy(source_policy)` — optional global
  policy sync into `$HOME/.<agent>/policies/`, guarded by an explicit
  user prompt.

Codex, OpenCode, and agy do **not** need these helpers (they use
global sandboxing or runtime-only policies).

### 17d. Orchestration block

Near the bottom of the script (currently around line 1960), the
"Other agents" block iterates each non-Claude agent:

```bash
if _is_agent_installed codex; then
    echo ""
    setup_codex_cli
fi
```

Add an analogous block for the new agent. Order is not significant.

### 17e. Helper-doc copy-loop tuple

If the new agent ships shared helper docs in
`.agents/skills/<agent>_*.md` (see §16 and §21), add them to the
`for doc in ...; do` tuple inside the codex `.agents/skills`
staging loop in `setup_codex_cli` (currently around line 1766). This
is **one of three lockstep sites** — see §21.

### 17f. Agent_type docstring comment

The `assemble_aitasks_instructions()` function (currently around
line 974) has a docstring comment listing valid `agent_type` values:

```bash
# agent_type: claude, codex, opencode (omit for shared-only)
```

Add the new agent to that enumeration so the docstring stays in sync.

### 17g. Framework-paths list (`commit_framework_files`)

`commit_framework_files()` (currently around line 2330) maintains a
`check_paths=(...)` array of repo-relative paths that are auto-staged
by `ait setup` at the end of the run. If the new agent has a
top-level runtime dotdir (e.g., `.codex/`, `.opencode/`) or a
root-level instructions file (e.g., `AGENTS.md`, `CLAUDE.md`), append
the corresponding entries here. This list is **duplicated in
`install.sh::commit_installed_files()`** — see §22.

## 18. Install staging (`install.sh`)

The top-level `install.sh` is what users run via `curl | bash`. It
unpacks the release tarball, then copies per-agent staging artifacts
into the user's `aitasks/metadata/<agent>_*` slots. `aitask_setup.sh`
(§17) consumes those slots later.

### 18a. `install_<agent>_staging()`

Pulls release-tarball staging dirs (`<agent>_skills/`,
`<agent>_commands/`, …) from `$INSTALL_DIR/` into
`aitasks/metadata/<agent>_*` and removes the originals. Mirror
`install_codex_staging` (or whichever staging function exists for an
agent with comparable structure). Skip clauses for assets the new
agent doesn't ship (e.g., no policies → no `<agent>_policies/`
clause).

### 18b. `install_seed_<agent>_config()`

Copies bundled seed files from `seed/<agent>_*` into
`aitasks/metadata/`. At minimum:
`seed/<agent>_instructions.seed.md` →
`aitasks/metadata/<agent>_instructions.seed.md`. Add seed entries
only for asset types the agent actually ships (see §20).

### 18c. Orchestration calls

In the main install flow (currently around line 980), add invocations
for both staging and seed functions:

```bash
info "Storing <Agent> staging files..."
install_<agent>_staging

info "Storing <Agent> config seeds..."
install_seed_<agent>_config
```

### 18d. Helper-doc copy-loop tuple

If the new agent ships helper docs (see §16, §21), add them to the
shared codex `codex_skills/` copy loop in
`install_codex_staging` (currently around line 482). This is **one
of three lockstep sites** — see §21.

### 18e. Framework-paths list (`commit_installed_files`)

`commit_installed_files()` (currently around line 695) maintains a
`check_paths=(...)` array that mirrors the one in
`aitask_setup.sh::commit_framework_files()` (§17g). Both arrays must
list the same paths — `install.sh` runs stand-alone via `curl|bash`
before extraction and cannot source a shared helper, so the
duplication is intentional. **If you change one, change the other.**

## 19. Release packaging (`.github/workflows/release.yml`)

The release workflow assembles the install tarball that `install.sh`
later consumes. For each per-agent staging asset that ends up in
`aitasks/metadata/<agent>_*` (§18a, §18b), a corresponding build step
must populate the matching staging dir at workflow-build time.

### 19a. "Build `<agent>` …" step

Modeled on the codex build step (currently around line 47, "Build
codex skills directory from .agents/skills"). For shared-root agents
(those whose `agent_shared_skills_root` returns `.agents/skills`),
the codex step already covers them — no additional step needed.

For agents with their own root (rare; current example: opencode):
add a dedicated step that mkdirs the staging dirs and copies from the
in-repo runtime tree.

### 19b. Helper-doc copy-loop tuple

The "Copy shared helper docs" loop inside the codex build step
(currently around line 57) is **one of three lockstep sites** — see
§21. Add the new agent's helper docs here if applicable.

### 19c. Tarball assembly

The "Create release tarball" step (currently around line 105) lists
all staging dirs that get bundled into
`aitasks-<version>.tar.gz`. If the new agent introduces new
top-level staging dirs (rare — most agents reuse `codex_skills/` via
the shared-root mechanism), add them to the `tar -czf ...` argument
list.

## 20. Seed assets (`seed/<agent>_*`)

Per-agent seed files ship in the framework repo under `seed/` and are
the source-of-truth defaults for first-run setup. The release tarball
includes `seed/` verbatim; `install.sh::install_seed_<agent>_config`
(§18b) copies them into `aitasks/metadata/`.

### 20a. `seed/<agent>_instructions.seed.md`

The Layer-2 system prompt / instructions block that
`setup_<agent>_cli` assembles together with the shared Layer-1
content (via `assemble_aitasks_instructions "$project_dir"
"<agent>"`) and writes to the user's per-agent instructions file
(e.g., `AGENTS.md` for codex, the agent's project-level
instructions file).

### 20b. `seed/models_<agent>.json`

Per-agent model registry seed consumed by the stats/picker code.
Also referenced in §3 (model registry), §4 (model picker), §5
(stats). The seed is copied into `aitasks/metadata/` during install
if absent.

### 20c. `seed/<agent>_settings.seed.json` *(optional)*

Settings defaults — only for agents that have a per-agent settings
file (`.claude/settings.local.json`, the retired
`.gemini/settings.json`). Codex and OpenCode use config files
(`config.toml`, `opencode.json`) handled by separate merge helpers,
not seed JSON.

### 20d. `seed/<agent>_policies/` *(optional)*

Policy seed directory — only for agents with policy support
(scoping mirrors §17c's `merge_<agent>_policies`). Currently no
agent ships one (the Gemini CLI variant was retired in t812_3).

## 21. Helper-doc copy-loop fan-out (3 sites in lockstep)

Shared helper docs in `.agents/skills/<agent>_tool_mapping.md` and
`.agents/skills/<agent>_planmode_prereqs.md` (see §16) are copied to
release staging by **three independent copy loops** that all carry
the same tuple. Adding a new agent that ships helper docs requires
editing **all three**; removing one requires the inverse.

| Site | Approx. line | Loop variable |
|------|--------------|---------------|
| `.aitask-scripts/aitask_setup.sh::setup_codex_cli()` | ~1766 | `for doc in codex_tool_mapping.md; do` |
| `install.sh::install_codex_staging()` | ~482 | (same tuple) |
| `.github/workflows/release.yml` (codex build step) | ~57 | (same tuple) |

Each loop has a preceding comment ("Copy shared helper docs (codex)")
that must be kept in sync with the tuple.

The three sites are intentionally independent — the workflow runs at
build time, the install script runs at install time, and `ait setup`
runs at user-setup time. None can source a shared helper.

## 22. Per-agent runtime dotdir (gitignore-skip / framework-paths)

If the new agent has a top-level runtime directory (e.g., `.codex/`,
`.opencode/`) that should be staged by `ait setup` / `install.sh`
and appear in user repos, two parallel `check_paths` arrays must
include `.<agent>/`:

- `.aitask-scripts/aitask_setup.sh::commit_framework_files()` (~ line
  2340) — see §17g.
- `install.sh::commit_installed_files()` (~ line 700) — see §18e.

If the agent also introduces a root-level instructions file
(`AGENTS.md`, `CLAUDE.md`, the retired `GEMINI.md`), add it to the
same two arrays.

**Agents that share `.agents/skills/` via the shared-root mechanism
in §1 typically do NOT need their own dotdir** — their rendered
skills live under `.agents/skills/<skill>-<profile>-<agent>-/` and
the `.agents/` entry already covers them. The dotdir convention is
for agents with their own private root (`.claude/`, `.codex/`,
`.opencode/`).

## 23. User-facing documentation & skill-closure files

Adding or retiring an agent touches a layer of **prose** that the
sections above do not — README/CLAUDE.md, the Hugo website, internal
`aidocs/` reference docs, and skill-closure `.md` files that enumerate
agent names. These do not break the framework if missed, but they
diverge from reality and confuse users. The first sweep (geminicli
removal in t812_4) revealed the pattern; codify it so future
adds/removes are mechanical.

### 23a. Top-level docs

- `README.md` — three current-state mentions of the supported-agent
  set (the tagline, the "Multi-agent support" feature blurb, and the
  Code Agent Skills documentation link). Use the **genericization
  rule** below.
- `CLAUDE.md` — "Working on Skills / Custom Commands" section. Three
  load-bearing references per agent:
  1. The `The framework also supports …` sentence listing the
     non-Claude agents.
  2. The bulleted **dotdir list** (`.codex/`, `.opencode/`, …) under
     that sentence — per-agent stub-surface description.
  3. The "Per-agent stub surface and rendered-variant location"
     table (4-column form: Agent / Stub location / Rendered variant
     / notes). One row per agent.
- `CHANGELOG.md` — append a new entry under the next pending release
  recording the add/remove. Do NOT rewrite historical entries.

### 23b. Genericization rule (load-bearing for prose stability)

When the supported-agent set appears in **marketing / introductory /
blurb prose** (README taglines, website overview / getting-started /
skills-index intros, in-paragraph examples), do **not** enumerate the
full list. Use the agent-set-agnostic phrasing instead:

- Preferred: `Claude Code and all other supported coding agents`
- Acceptable (when one or two anchors carry editorial weight):
  `Claude Code, Codex, and all other supported coding agents`

**Why:** every fixed enumeration in prose is a churn site each time the
agent set changes. Marketing-style enumerations have no normative
value — the agent set IS the documentation only when each agent
contributes an agent-specific code path / instruction.

Apply the literal-enumeration rule (NOT the genericization rule) where
the list IS the documentation:

- CLI mapping tables (`website/content/docs/commands/codeagent.md`'s
  Agent / CLI Binary / Model Flag table).
- Per-agent install instructions
  (`website/content/docs/installation/windows-wsl.md`'s `npm install`
  block).
- Per-agent known-issue sections
  (`website/content/docs/installation/known-issues.md`'s `## <Agent>`
  H2 sections).
- Add-model support tables
  (`website/content/docs/skills/aitask-add-model.md`).
- Wrapper-tree audit tables
  (`website/content/docs/development/skills/aitask-audit-wrappers.md`).
- Settings-TUI value enumerations
  (`website/content/docs/tuis/settings/*.md`).
- Skill-closure model-self-detection lists (see §23d).
- Touchpoint and stub-surface tables in `aidocs/`.

### 23c. Internal `aidocs/` reference docs

These describe the **current state of the codebase**; outdated entries
mislead readers and the dep-walker. Audit per-agent rows on every
add/remove:

| File | Surface | Edit on add/remove |
|---|---|---|
| `aidocs/framework/aitasks_extension_points.md` | Helper-script whitelist touchpoint table | Add/remove per-agent rows; renumber **only** by leaving retired slots vacant (numbering is stable). |
| `aidocs/framework/model_reference_locations.md` | Inventory tables (model registry, supported agents) | Add/remove rows for `aitasks/metadata/models_<agent>.json` and the seed mirror. |
| `aidocs/framework/stub-skill-pattern.md` | §3g per-agent surface table, §3b/§3d/§3e stub-form subsections, the "one stub per (skill, agent surface)" count, the dep-walker reference-resolution roots list | Add/remove a row, a subsection, and the bare agent-root reference (`.<agent>` literal). |
| `aidocs/issue_type_vocabulary_duplication.md` | "agent-identification only" seed file list | Add/remove the `seed/<agent>_instructions.seed.md` entry. |

### 23d. Skill-closure `.md` files (Claude-Code source, fan-out via rerender)

Non-templated procedure files inside `.claude/skills/` closures that
hardcode the agent enumeration must be edited at the **source**
(`.claude/skills/<skill>/`), then refreshed for every profile via
`./.aitask-scripts/aitask_skill_rerender.sh <profile>`. The rerender
fan-out applies the change to every per-profile, per-agent rendered
variant (`<.claude|.opencode|.agents>/skills/<skill>-<profile>-[<agent>-]/`).

Current sites (canonical list — re-grep `geminicli` / `gemini` after
this task to confirm none re-introduced):

- `.claude/skills/task-workflow/model-self-detection.md` — the
  "MUST be one of these exact strings" agent-identifier list.
- `.claude/skills/task-workflow/satisfaction-feedback.md` — same shape
  (Step 2 self-detection fallback).
- `.claude/skills/task-workflow/plan-externalization.md` — the
  "Other code agents (…) do not have an internal plan-mode file"
  enumeration.
- `.claude/skills/aitask-add-model/SKILL.md` — `--agent` validation
  list and the agent-options AskUserQuestion.
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — agent
  filename pattern example, the git-add command line listing each
  `models_<agent>.json`, the research-URL bullets, and the model-
  naming-convention examples.
- `.claude/skills/aitask-audit-wrappers/SKILL.md` — wrapper-tree
  enumeration, helper-whitelist touchpoint table, and the per-phase
  apply commands.

**Fan-out rule:** one source edit × 3 profiles × N agents = up to
`3 × N` closure refreshes per source edit (e.g., 9 for the current
claude/codex/opencode set). Always invoke the rerender driver —
never hand-edit a rendered `*-/` directory.

### 23e. Golden snapshots — closure-edit trigger

Per `aidocs/framework/skill_authoring_conventions.md` and the CLAUDE.md
"Regenerate goldens after any `.md.j2` or closure edit" rule, **any**
edit to a closure `.md` file requires regenerating its goldens in
the same commit. For each affected procedure:

```bash
PYTHON="$(./.aitask-scripts/lib/python_resolve.sh require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/<procedure>.md \
    aitasks/metadata/profiles/$profile.yaml claude \
    > tests/golden/procs/task-workflow/<procedure>-$profile.md
done
```

Confirm with `bash tests/test_skill_render_task_workflow.sh` — it
diffs every (procedure × profile) pair against its golden.

### 23f. Website docs sweep

The Hugo source tree under `website/content/docs/` carries the
largest single surface of agent enumerations. The current canonical
file set (as of t812_4) is:

- **Blurb / tagline prose** (genericize per §23b):
  `overview.md`, `getting-started.md`, `skills/_index.md`,
  `installation/_index.md`, `concepts/agent-attribution.md`,
  `concepts/verified-scores.md`,
  `skills/aitask-pick/commit-attribution.md`,
  `skills/aitask-refresh-code-models.md`.
- **Normative enumerations** (keep literal, add/remove a row per agent):
  `commands/codeagent.md`, `installation/known-issues.md`,
  `installation/updating-model-lists.md`,
  `installation/windows-wsl.md`,
  `skills/aitask-add-model.md`,
  `development/skills/aitask-audit-wrappers.md`,
  `tuis/settings/_index.md`, `tuis/settings/how-to.md`,
  `tuis/settings/reference.md`.

After any add/remove, build the site to catch broken cross-references:

```bash
cd website && hugo build --gc --minify
```

### 23g. Final grep sanity check

```bash
grep -rn '<old-agent>\|<old-agent-display-name>' \
  --include='*.md' --include='*.j2' --include='*.toml' \
  --include='*.json' . \
  | grep -v -E '^./(aitasks|aiplans)/archived/' \
  | grep -v '^./.claude/projects/'
```

Acceptable post-removal residue:
- `CHANGELOG.md` / `CHANGELOG_HUMANIZED.md` historical entries.
- Dated blog posts under `website/content/blog/`.
- `aidocs/<old-agent>_to_<new-agent>.md` migration guides retained
  for follow-up tasks.
- `seed/reviewguides/*/` / `aireviewguides/*/` `source_url:`
  provenance citations (NOT current-state framework prose).
- The new CHANGELOG entry recording the add/remove itself.

If the grep flags anything outside this list, the sweep is incomplete.
