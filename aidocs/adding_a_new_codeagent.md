# Adding a New Code Agent to the aitasks Framework

End-to-end checklist for wiring a new code agent (Claude Code, Codex CLI,
Gemini CLI, OpenCode, agy, …) into the aitasks framework. Each section
covers one architectural concern. Sections are independent and can be
addressed in any order, but the order presented here is the path of least
friction (no rework, no temporary inconsistency).

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

*(More sections to be added as the migration playbook expands: setup /
install (`aitask_setup.sh`), tool-mapping prereq files, whitelist /
permission setup, contributor docs, website docs, etc.)*

---

## 1. Writing skills for agents that share `.agents/skills/`

Some agents target the same **physical skills directory** as another
existing agent. Today that is Codex CLI (`.agents/skills/`); when agy
lands (t814) it will share that root too. Without disambiguation, two
agents writing their rendered SKILL.md into the same directory would
overwrite each other.

The framework solves this by adding an **agent-id segment** to the
rendered-dir name for any agent declared as `shared_skills_root: true`.
Non-shared agents (claude, gemini, opencode) keep the simpler
`<skill>-<profile>-/` form unchanged.

### 1a. Rendered-path naming

| Agent | `agent_skill_root` | Shared? | Rendered SKILL.md path |
|-------|-------------------|---------|-----------------------|
| claude | `.claude/skills` | no | `.claude/skills/<skill>-<profile>-/SKILL.md` |
| codex | `.agents/skills` | **yes** | `.agents/skills/<skill>-<profile>-codex-/SKILL.md` |
| gemini | `.gemini/skills` | no | `.gemini/skills/<skill>-<profile>-/SKILL.md` |
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
           gemini)   echo ".gemini/skills" ;;
           opencode) echo ".opencode/skills" ;;
           *)        echo "agent_skill_root: unknown agent: $1" >&2; return 1 ;;
       esac
   }

   agent_shared_skills_root() {
       case "$1" in
           claude)   echo "false" ;;
           codex)    echo "true"  ;;
           agy)      echo "true"  ;;                 # NEW (shares .agents/skills)
           gemini)   echo "false" ;;
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
       "gemini":   ".gemini/skills",
       "opencode": ".opencode/skills",
   }
   AGENT_SHARED_SKILLS_ROOT = {
       "claude":   False,
       "codex":    True,
       "agy":      True,                  # NEW
       "gemini":   False,
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
for agent in claude codex agy gemini opencode; do   # NEW agent inserted
    ...
done
```

### 1d. Write the per-agent stub

Each skill needs a committed stub at the agent's authoring location
(see `aidocs/stub-skill-pattern.md` §3g for the per-agent surface
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

Per `aidocs/skill_authoring_conventions.md`, any change touching the
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
`aidocs/stub-skill-pattern.md` — read it for the stub body templates per
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
(claude vs. claudecode, gemini vs. geminicli) — pick the name that
matches existing usage in `ait monitor`'s codepath.

Patterns are populated when an agent's prompt wording is observed in
practice; an empty list is a valid no-op until you have a pattern to
add. See `aidocs/monitor_idle_and_prompt_detection.md` for the pattern
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

---
