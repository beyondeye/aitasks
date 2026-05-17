---
Task: t777_5_aitask_skillrun_wrapper_dispatcher.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md, aitasks/t777/t777_7_convert_task_workflow_shared_procs.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-17 18:23
---

# Plan: t777_5 — `ait skillrun` wrapper + dispatcher + 5-touchpoint whitelist (VERIFIED 2026-05-17)

This is the **verify-mode** refinement of `aiplans/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md`. The original plan was written when the t777_3 stub design was still evolving and the codebase state has now stabilized; this version refines the per-agent launch commands and the dispatcher placement based on verification against the current code.

## Context

`ait skillrun` is the shell-side entry point for invoking a profile-aware aitasks skill against any of the 4 supported code agents. It is the cross-agent moral equivalent of the existing claude-only `claude '/<skill> <args>'` invocation: it picks the agent (autodetect or `--agent`), picks the profile (autodetect via `aitask_skill_resolve_profile.sh` or `--profile`), and `exec`s the agent CLI with the user-facing slash command form `/aitask-<skill> --profile <profile> <args>`. The stub at the no-suffix path (t777_3 design, `stub-skill-pattern.md` §3h) then dispatches to the rendered per-profile variant.

**Skill name convention (user-direction 2026-05-17):** `<skill>` is the **short form** without the `aitask-` prefix — `pick`, `explore`, `review`, `qa`, etc. The wrapper synthesizes the full skill name as `aitask-<skill>` internally. This matches the user-direction "drop the aitask- prefix and you have the short name" and matches the existing `default_profiles.<short>` keys in `project_config.yaml` (e.g. `default_profiles.pick: fast`).

**Universal behavior across templated and non-templated skills (user-direction 2026-05-17):** Skillrun **always** forwards `--profile <name>` to the slash command, regardless of whether the target skill has a `.j2` authoring template + stub. Rationale: gradual porting. During the t777_6..t777_15 conversion window:
- For **templated** skills (e.g., `aitask-pick` post-t777_6): the stub's Step 1 parses `--profile` from ARGUMENTS, strips it, and dispatches to the rendered variant. `--profile` is meaningful.
- For **non-templated** skills (everything pre-conversion): the skill body sees `--profile <name>` as an unknown leading arg. Most skills today simply ignore unrecognized args (the slash command's ARGUMENTS string is interpreted by the skill body, which already has lenient parsing). The friction surfaces the need to convert that skill — but does NOT break the launcher.

This means skillrun is the universal launcher today and continues working unchanged as each skill gets its stub. No `.j2`-detection branch needed; no special-case errors. `--profile-override` likewise always applies (the tempfile is created, the profile name flips to `_skillrun_<unique>`, the override YAML controls the resolved profile — works identically for templated and non-templated skills, modulo whether the skill body actually reacts to profile keys).

The wrapper is the entry point for shell users today, and will be the entry point for the `AgentCommandScreen` TUI (t777_17) tomorrow. Per the user feedback memory `feedback_avoid_claude_p_for_skill_invocation`, it MUST NOT use `claude -p` — it always launches the agent in interactive mode.

It also supports `--profile-override <yaml>` for the per-run profile editor in t777_17: an override YAML is merged on top of the resolved profile, written under `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` (auto-discovered by `aitask_scan_profiles.sh` via the `local/` prefix), the stub is invoked with `--profile _skillrun_<unique>`, and an EXIT trap deletes the tempfile after the agent process exits.

## Verification Findings (2026-05-17)

1. **Plan's per-agent launch table is partially wrong.** The original plan listed:
   ```bash
   claude)   exec claude   "/${skill} ${forwarded}" ;;
   gemini)   exec gemini   "/${skill} ${forwarded}" ;;
   opencode) exec opencode "/${skill} ${forwarded}" ;;
   codex)    exec codex    "/${skill} ${forwarded}" ;;
   ```
   Verified against `aitask_codeagent.sh:528-619` (the canonical "build the agent invocation" reference):
   - **claude**: positional `'/<skill> <args>'` — correct as listed.
   - **gemini**: positional `'/<skill> <args>'` — correct as listed.
   - **opencode**: requires `--prompt '/<skill> <args>'` — **plan is wrong**, opencode does NOT accept positional slash commands.
   - **codex**: does NOT support slash-command syntax directly; the framework drives Codex via `aitask_codex_plan_invoke.py` (pexpect-based PTY wrapper that types `/plan` + the prompt into Codex's composer). The prompt form there uses `$aitask-pick` (dollar prefix) per `aitask_codeagent.sh:577,583,588,592`. **Plan's `exec codex "/${skill} ..."` is wrong.**

2. **Codex profile-override interaction is the same as other agents.** The `--profile` argument forwarding contract from `stub-skill-pattern.md` §3h applies to all 4 agents — the stub strips `--profile <name>` from the forwarded args before dispatching. Codex's prompt form just uses a different prefix character (`$` instead of `/`); the `--profile <name>` portion still goes through ARGUMENTS unchanged.

3. **Dispatcher placement: `skillrun)` is a top-level command, not a `skill` subcommand.** Per the plan: "Add near `settings)`, before `setup)`". Verified `ait:185-191` — `settings)` is at line 185, `setup)` is at line 191. `skillrun)` goes between them as a top-level case. Update `show_usage` to mention `skillrun` under a new "Skill Invocation" or extend the existing "Task Management" / "Tools" section.

4. **`aitask_skill_resolve_profile.sh` exists and is the canonical resolver** — produces a single-line stdout value matching exactly the value the plan needs to pass to `--profile`. No further parsing required.

5. **`aitask_scan_profiles.sh` returns `local/<file>.yaml`** for user-local overrides (verified `aitask_scan_profiles.sh:13-14, 69`). So writing the override tempfile to `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` IS auto-discovered — the plan's `--profile _skillrun_<unique>` pass-through is correct because `aitask_skill_resolve_profile.sh` and `aitask_skill_render.sh` both eventually call `aitask_scan_profiles.sh` which finds `local/_skillrun_<unique>.yaml` by name match on the `name:` field inside the YAML, not by filename. Therefore the override YAML's `name:` field MUST be set to `_skillrun_<unique>` (matching the basename minus `.yaml`).

6. **Pre-warming render is optional and skipped.** The stub itself runs `ait skill render` on every invocation; skip-if-fresh (`aitask_skill_render.sh:111-119`) makes a redundant pre-warming render a no-op. Pre-warming would add complexity (race conditions if the stub's render and a pre-warm collide; what to render when `--profile-override` is in play). Drop it.

7. **No `.j2` authoring templates exist yet** (verified: `find .claude/skills -name 'SKILL.md.j2'` returns nothing). The skillrun wrapper is therefore not directly end-to-end testable today — only `--dry-run` and `--profile-override` tempfile lifecycle can be validated until t777_6 lands the first `.j2` (pilot conversion of aitask-pick). The plan's verification steps 2 and 3 ("end-to-end" cases) are de-facto deferred to t777_6 sibling testing; the wrapper itself is shippable today.

8. **5-touchpoint whitelist precedent confirmed.** `aitask_skill_render.sh` (t777_2) and `aitask_skill_verify.sh` (t777_4) are both whitelisted in all 5 touchpoints. The skillrun wrapper mirrors that pattern exactly — single new entry per file, adjacent to the existing skill_render / skill_verify entries.

## Refinements over Original Plan

- **R1 — Fix per-agent launch table.** Use the correct CLI invocation for each agent (where `full_skill = "aitask-${skill}"`):
  - `claude`: `exec claude [<model_flag> <model_id>] "/${full_skill} ${forwarded}"`
  - `gemini`: `exec gemini [<model_flag> <model_id>] "/${full_skill} ${forwarded}"`
  - `opencode`: `exec opencode [<model_flag> <model_id>] --prompt "/${full_skill} ${forwarded}"`
  - `codex`: route through `aitask_codex_plan_invoke.py` with `$${full_skill} ${forwarded}` (mirroring `aitask_codeagent.sh:577`). The wrapper synthesizes the prompt and calls `python3 .aitask-scripts/aitask_codex_plan_invoke.py --prompt "$prompt" -- codex [<model_flag> <model_id>]`.
- **R2 — Drop pre-warming render.** The stub renders on every invocation; skip-if-fresh handles freshness; pre-warming adds complexity for no benefit.
- **R3 — Override YAML's `name:` MUST match its basename.** Tempfile basename `_skillrun_<unique>.yaml` and YAML `name: _skillrun_<unique>` so `aitask_scan_profiles.sh` finds it.
- **R4 — Override merge semantics.** Merge override YAML on top of the resolved-profile YAML; for each key in the override, replace the value at the same key in the base. Non-overridden keys keep the base value. Output the merged YAML to the tempfile. Implementation: a small Python one-liner via `require_ait_python` (PyYAML is available in the framework venv).
- **R5 — `--dry-run` semantics.** Print the synthesized launch command (the exact argv that would be `exec`ed), do NOT exec, do NOT write the override tempfile. When `--profile-override` is set, ALSO print the merged YAML preview to stderr (for the t777_17 TUI preview path).
- **R6 — Short skill names** (user direction 2026-05-17). `<skill>` is the short form (no `aitask-` prefix). Wrapper synthesizes `full_skill = "aitask-${skill}"` for all downstream lookups (`aitask_skill_resolve_profile.sh`, scan_profiles match if needed, slash-command construction).
- **R7 — `--agent-string <agent>/<model>` with single-source-of-truth lib extraction** (user direction 2026-05-17). Skillrun accepts the **canonical framework form** `--agent-string claudecode/opus4_7_1m` (NOT a raw CLI ID). Model resolution (symbolic name → CLI-native ID via `models_<agent>.json`) is delegated to a new sourceable helper. **No `--agent` or `--model` flags** in v1 — folded into `--agent-string`. This eliminates the parallel-convention risk (two ways to specify a model) flagged during planning.

  The model-resolution helpers currently inlined at `aitask_codeagent.sh:46-94` (`parse_agent_string`, `get_cli_binary`, `get_cli_model_id`, `get_model_flag`) plus the constants (`SUPPORTED_AGENTS`, `DEFAULT_AGENT_STRING`) are extracted into a new `.aitask-scripts/lib/agent_string.sh` with a `_AIT_AGENT_STRING_LOADED` double-source guard. Both `aitask_codeagent.sh` and `aitask_skillrun.sh` source it. Matches `feedback_single_source_of_truth_for_versions`.

## Critical Files

**Create:**
- `.aitask-scripts/lib/agent_string.sh` — sourceable lib housing `parse_agent_string`, `get_cli_binary`, `get_cli_model_id`, `get_model_flag` + `SUPPORTED_AGENTS`, `DEFAULT_AGENT_STRING` constants (extracted from `aitask_codeagent.sh`)
- `.aitask-scripts/aitask_skillrun.sh` — the wrapper
- `tests/test_agent_string.sh` — unit tests for the extracted lib (`parse_agent_string` validation, `get_cli_binary` mapping, `get_model_flag` mapping)

**Modify:**
- `.aitask-scripts/aitask_codeagent.sh` — source the new lib; delete the now-extracted helper functions and constants (in-place refactor, no behavior change)
- `ait` — add `skillrun)` case between `settings)` (line 185) and `setup)` (line 191); add `skillrun` to update-check skip-list (`ait:167-170`); update `show_usage` to mention `skillrun`
- `.claude/settings.local.json` — +1 whitelist entry for `aitask_skillrun.sh`
- `.gemini/policies/aitasks-whitelist.toml` — +1 `[[rule]]` block for `aitask_skillrun.sh`
- `seed/claude_settings.local.json` — +1 whitelist entry mirror
- `seed/geminicli_policies/aitasks-whitelist.toml` — +1 `[[rule]]` block mirror
- `seed/opencode_config.seed.json` — +1 allow entry for `aitask_skillrun.sh`

Codex exempt per CLAUDE.md "Adding a New Helper Script".

**Note on lib/agent_string.sh whitelist:** Sourced lib files are NOT executed as scripts, so they don't need 5-touchpoint whitelist entries. Only the executable wrappers (`aitask_codeagent.sh`, `aitask_skillrun.sh`) need whitelisting — both already have entries (or will, for skillrun). Verify no whitelist regression after extraction.

## Step Order

### Step 0 — Extract `.aitask-scripts/lib/agent_string.sh`

Create the new sourceable lib by moving (cut, not copy) the functions + constants out of `aitask_codeagent.sh`. The lib's body:

```bash
#!/usr/bin/env bash
# agent_string.sh — Single source of truth for agent-string parsing and
# model/binary/flag resolution. Sourceable from any aitask script that
# needs to translate "<agent>/<model>" into the per-CLI invocation triple
# (binary, model_flag, cli_id).
#
# Provides:
#   SUPPORTED_AGENTS           (array of canonical agent names)
#   DEFAULT_AGENT_STRING       (claudecode/opus4_7_1m at time of writing)
#   parse_agent_string <s>     (sets PARSED_AGENT, PARSED_MODEL; dies on bad input)
#   get_cli_binary <agent>     (e.g. claudecode → claude)
#   get_model_flag <agent>     (e.g. claudecode → --model)
#   get_cli_model_id <agent> <model>  (reads models_<agent>.json via jq)

[[ -n "${_AIT_AGENT_STRING_LOADED:-}" ]] && return 0
_AIT_AGENT_STRING_LOADED=1

# shellcheck source=terminal_compat.sh
source "$(dirname "${BASH_SOURCE[0]}")/terminal_compat.sh"

DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-claudecode/opus4_7_1m}"
SUPPORTED_AGENTS=(claudecode geminicli codex opencode)

# --- Parsed agent string (set by parse_agent_string) ---
PARSED_AGENT=""
PARSED_MODEL=""

parse_agent_string() {
    # ... verbatim copy from aitask_codeagent.sh lines 46-64 ...
}

get_cli_binary() {
    # ... verbatim copy from aitask_codeagent.sh lines 65-76 ...
}

get_model_flag() {
    # ... verbatim copy from aitask_codeagent.sh lines 77-88 ...
}

get_cli_model_id() {
    # ... verbatim copy from aitask_codeagent.sh lines 89-... ...
}
```

**Cut-not-copy:** delete the source lines in `aitask_codeagent.sh` and replace with `source "$SCRIPT_DIR/lib/agent_string.sh"` near the existing `source` line for `python_resolve.sh` (verify the existing source pattern in aitask_codeagent.sh first; SCRIPT_DIR may need to be defined before sourcing).

**Verify after extraction:**
- `./ait codeagent resolve pick` produces identical output before and after the refactor (diff before/after).
- `./ait codeagent check claudecode/opus4_7_1m` works.
- `./ait codeagent list-models claudecode` works.
- `aitask_codeagent.sh` still passes shellcheck.

### Step 0b — Write `tests/test_agent_string.sh`

Unit tests for the extracted lib. Pattern-match `tests/test_skill_template.sh`: inline `assert_eq` / `assert_contains`, PASS/FAIL counters, EXIT-trap cleanup.

| # | Case | Mechanism |
|---|------|-----------|
| 1 | `parse_agent_string "claudecode/opus4_7_1m"` sets PARSED_AGENT=claudecode, PARSED_MODEL=opus4_7_1m | Sourced + asserted |
| 2 | `parse_agent_string "bogus"` dies (no slash) | Subshell + `! ... 2>/dev/null` |
| 3 | `parse_agent_string "fakeagent/x"` dies (unknown agent) | Subshell |
| 4 | `get_cli_binary claudecode` → `claude` | `assert_eq` |
| 5 | `get_cli_binary geminicli` → `gemini` | `assert_eq` |
| 6 | `get_cli_binary codex` → `codex` | `assert_eq` |
| 7 | `get_cli_binary opencode` → `opencode` | `assert_eq` |
| 8 | `get_model_flag claudecode` → `--model` | `assert_eq` |
| 9 | `get_model_flag geminicli` → `-m` | `assert_eq` |
| 10 | `get_model_flag codex` → `-m` | `assert_eq` |
| 11 | `get_model_flag opencode` → `--model` | `assert_eq` |
| 12 | Sourcing the lib twice is a no-op (double-source guard works) | Source once, set sentinel, source again, assert sentinel survives |

### Step 1 — Write `.aitask-scripts/aitask_skillrun.sh`

Standard header (mirrors `aitask_skill_render.sh` / `aitask_skill_verify.sh`):

```bash
#!/usr/bin/env bash
# aitask_skillrun.sh — Launch a code agent with a profile-aware aitask skill.
#
# Usage:
#   aitask_skillrun.sh <skill> [--profile <name>] [--agent-string <agent>/<model>]
#                               [--profile-override <yaml|->] [--dry-run] [-- <args>...]
#
# <skill> is the SHORT form (no aitask- prefix): pick, explore, review, qa, ...
# Wrapper synthesizes full_skill="aitask-<skill>" for slash command + profile lookup.
#
# --agent-string defaults to $DEFAULT_AGENT_STRING (from lib/agent_string.sh,
# currently "claudecode/opus4_7_1m"). Model resolution (symbolic name → CLI ID)
# is performed by the lib's get_cli_model_id — single source of truth shared
# with aitask_codeagent.sh.
#
# Per-agent invocation (full_skill = "aitask-<skill>", binary/model_flag/cli_id
# resolved from agent-string):
#   claudecode → exec claude --model <cli_id> "/<full_skill> --profile <profile> <args>"
#   geminicli  → exec gemini -m <cli_id> "/<full_skill> --profile <profile> <args>"
#   opencode   → exec opencode --model <cli_id> --prompt "/<full_skill> --profile <profile> <args>"
#   codex      → python3 aitask_codex_plan_invoke.py --prompt "$<full_skill> --profile <profile> <args>" -- codex -m <cli_id>
#
# Does NOT use `claude -p` (per feedback_avoid_claude_p_for_skill_invocation).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=.aitask-scripts/lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=.aitask-scripts/lib/agent_string.sh
source "$SCRIPT_DIR/lib/agent_string.sh"

cd "$REPO_ROOT"
```

**Argument parsing** (positional skill + flags + `--` passthrough for skill args):

```bash
skill=""
profile=""
agent_string=""
profile_override=""
dry_run=false
args=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --profile)
            [[ $# -lt 2 ]] && { echo "skillrun: --profile requires a value" >&2; exit 2; }
            profile="$2"; shift 2 ;;
        --agent-string)
            [[ $# -lt 2 ]] && { echo "skillrun: --agent-string requires a value" >&2; exit 2; }
            agent_string="$2"; shift 2 ;;
        --profile-override)
            [[ $# -lt 2 ]] && { echo "skillrun: --profile-override requires a YAML path or '-'" >&2; exit 2; }
            profile_override="$2"; shift 2 ;;
        --dry-run)
            dry_run=true; shift ;;
        --help|-h)
            usage; exit 0 ;;
        --)
            shift; args=("$@"); break ;;
        --*)
            echo "skillrun: unknown flag: $1" >&2; exit 2 ;;
        *)
            if [[ -z "$skill" ]]; then
                skill="$1"; shift
            else
                args+=("$1"); shift
            fi ;;
    esac
done

[[ -z "$skill" ]] && { echo "skillrun: missing <skill>" >&2; exit 2; }
# Reject the long-form name proactively so users don't end up looking for
# /aitask-aitask-pick (the synthesis would otherwise prepend aitask- twice).
case "$skill" in
    aitask-*) die "skillrun: pass the short skill name (drop the 'aitask-' prefix). Got: '$skill'" ;;
esac
full_skill="aitask-${skill}"
```

**Agent-string resolution + per-CLI triple via the lib:**

```bash
[[ -z "$agent_string" ]] && agent_string="${AIT_AGENT_STRING:-$DEFAULT_AGENT_STRING}"

# parse_agent_string dies on bad input; sets PARSED_AGENT and PARSED_MODEL.
parse_agent_string "$agent_string"

binary="$(get_cli_binary "$PARSED_AGENT")"
model_flag="$(get_model_flag "$PARSED_AGENT")"
cli_id="$(get_cli_model_id "$PARSED_AGENT" "$PARSED_MODEL")"
```

`$DEFAULT_AGENT_STRING` comes from the lib (`claudecode/opus4_7_1m` at time of writing). The env var `AIT_AGENT_STRING` lets users override the default without touching the CLI; mirrors how `AIT_AGENT` was historically used. Both `aitask_codeagent.sh` and `aitask_skillrun.sh` honor it via the same lib constant.

**Per-skill agent-string defaults (future enhancement, NOT in this task):** Today `aitask_codeagent.sh resolve <op>` reads `userconfig.yaml:code_agent.<op>` and `project_config.yaml:code_agent.<op>` to select an agent string per operation. Skillrun could leverage this once `<skill>` is generalized to any operation. For v1 of skillrun we stay simple — `--agent-string` explicit or fall through to `DEFAULT_AGENT_STRING`. Document this in the wrapper's `--help`.

**Profile autodetection** (via `aitask_skill_resolve_profile.sh`):

Note: `aitask_skill_resolve_profile.sh` looks up `default_profiles.<short>` in userconfig/project_config. Pass the short name (`$skill`), not the full name, because `project_config.yaml` keys this on `pick`, `explore`, etc. — verified `project_config.yaml`:

```bash
if [[ -z "$profile" ]]; then
    profile="$("$SCRIPT_DIR/aitask_skill_resolve_profile.sh" "$skill")"
fi
[[ -z "$profile" ]] && die "skillrun: could not resolve profile for skill '$skill'"
```

(Model flag is now resolved above via `get_model_flag` from the lib — no per-agent case statement needed in skillrun.)

**Profile-override merge** (only when `--profile-override` is set):

In `--dry-run`, the merge runs but writes the merged YAML to stderr instead of the tempfile (user direction 2026-05-17: dry-run is a true preview mode for the t777_17 TUI). In live mode, the merge writes to `aitasks/metadata/profiles/local/_skillrun_<unique>.yaml` and the profile name flips to `_skillrun_<unique>` so the stub resolves the override-merged variant.

```bash
override_tempfile=""
cleanup_override() {
    [[ -n "$override_tempfile" && -f "$override_tempfile" ]] && rm -f "$override_tempfile"
}

if [[ -n "$profile_override" ]]; then
    # Resolve base profile YAML via aitask_scan_profiles.sh
    _scan="$("$SCRIPT_DIR/aitask_scan_profiles.sh")"
    base_filename="$(echo "$_scan" \
        | awk -F'|' -v n="$profile" '$1=="PROFILE" && $3==n {print $2; exit}')"
    [[ -z "$base_filename" ]] && die "skillrun: base profile '$profile' not found"
    base_path="$REPO_ROOT/aitasks/metadata/profiles/$base_filename"

    PYTHON="$(require_ait_python)"

    if [[ "$dry_run" == true ]]; then
        # Preview merged YAML to stderr; no tempfile, no profile name change.
        {
            echo "--- merged profile preview (--profile-override --dry-run) ---"
            "$PYTHON" - "$base_path" "$profile_override" <<'PYEOF'
import sys, yaml
base_path, override_path = sys.argv[1:3]
with open(base_path) as f:
    base = yaml.safe_load(f) or {}
if override_path == "-":
    override = yaml.safe_load(sys.stdin) or {}
else:
    with open(override_path) as f:
        override = yaml.safe_load(f) or {}
merged = {**base, **override}
print(yaml.safe_dump(merged, sort_keys=False), end="")
PYEOF
            echo "--- end preview ---"
        } >&2
    else
        # Live mode: write tempfile + set profile name to its stem.
        unique="$(date +%s%N)_$$"
        new_profile_name="_skillrun_${unique}"
        override_dir="$REPO_ROOT/aitasks/metadata/profiles/local"
        mkdir -p "$override_dir"
        override_tempfile="$override_dir/${new_profile_name}.yaml"

        "$PYTHON" - "$base_path" "$profile_override" "$override_tempfile" "$new_profile_name" <<'PYEOF'
import sys, yaml
base_path, override_path, out_path, new_name = sys.argv[1:5]
with open(base_path) as f:
    base = yaml.safe_load(f) or {}
if override_path == "-":
    override = yaml.safe_load(sys.stdin) or {}
else:
    with open(override_path) as f:
        override = yaml.safe_load(f) or {}
merged = {**base, **override}
merged["name"] = new_name
merged.setdefault("description", base.get("description", "") + " (per-run override)")
with open(out_path, "w") as f:
    yaml.safe_dump(merged, f, sort_keys=False)
PYEOF

        trap cleanup_override EXIT INT TERM
        profile="$new_profile_name"
    fi
fi
```

**Synthesize forwarded args**: `--profile <profile> <skill-args>`.

```bash
forwarded_args=("--profile" "$profile")
[[ ${#args[@]} -gt 0 ]] && forwarded_args+=("${args[@]}")
forwarded="${forwarded_args[*]}"
```

**Construct launch CMD per agent** (using `$binary`, `$model_flag`, `$cli_id` resolved from the lib):

```bash
CMD=()
case "$PARSED_AGENT" in
    claudecode)
        CMD=("$binary" "$model_flag" "$cli_id" "/${full_skill} ${forwarded}")
        ;;
    geminicli)
        CMD=("$binary" "$model_flag" "$cli_id" "/${full_skill} ${forwarded}")
        ;;
    opencode)
        CMD=("$binary" "$model_flag" "$cli_id" --prompt "/${full_skill} ${forwarded}")
        ;;
    codex)
        # Codex doesn't accept slash commands directly; drive via pexpect helper.
        # Codex prompt syntax uses '$' prefix (mirroring aitask_codeagent.sh:577).
        PYTHON="$(require_ait_python)"
        codex_prompt="\$${full_skill} ${forwarded}"
        CMD=("$PYTHON" "$SCRIPT_DIR/aitask_codex_plan_invoke.py" "--prompt" "$codex_prompt" "--" "$binary" "$model_flag" "$cli_id")
        ;;
esac
```

The model triple (`$binary`, `$model_flag`, `$cli_id`) is always populated — no conditional skip path, no empty-array gotcha. If the user wants the framework default, they omit `--agent-string` and the lib fills in `DEFAULT_AGENT_STRING`.

**`--dry-run` branch**: print and exit.

```bash
if [[ "$dry_run" == true ]]; then
    printf 'DRY_RUN:'
    printf ' %q' "${CMD[@]}"
    printf '\n'
    exit 0
fi
```

**Exec the agent**. On normal exit, the EXIT trap cleans up the override tempfile. On `exec`, the trap is inherited only via process-substitution caveats; since `exec` replaces the shell, the trap fires before exec (bash semantics: EXIT trap does not fire on `exec`). To ensure the tempfile is deleted, fork instead:

```bash
if [[ -n "$override_tempfile" ]]; then
    # Fork the agent and reap, so the EXIT trap fires after agent termination
    "${CMD[@]}"
    rc=$?
    cleanup_override
    exit "$rc"
else
    exec "${CMD[@]}"
fi
```

### Step 2 — Add `skillrun)` to `./ait` dispatcher

Insert between `settings)` (line 185) and `setup)` (line 191), with the existing comma-style line shape:

```bash
    skillrun)     shift; exec "$SCRIPTS_DIR/aitask_skillrun.sh" "$@" ;;
```

Also bypass the update check for `skillrun` (it's a frequently-called wrapper; the check would interleave output with the agent launch). Add `skillrun` to the case-statement at `ait:167-170`:

```bash
case "${1:-help}" in
    help|--help|-h|--version|-v|upgrade|setup|git|sync|lock|codeagent|crew|brainstorm|settings|monitor|minimonitor|ide|syncer|skillrun) ;;
    *) check_for_updates ;;
esac
```

**Update `show_usage`**: add a single line under a sensible section. Since `skillrun` straddles "Task Management" and "Tools", put it as the last line under "Tools" (between `migrate-archives` and `zip-old`), or add it to the new section "Skill Invocation" if creating a new section is too disruptive. Recommended: add at the end of the existing TUI/Task block:

```
  skillrun       Launch a code agent with a profile-aware aitask skill
```

(Exact placement TBD at edit time; the existing `show_usage` already has a flexible structure.)

### Step 3 — Whitelist `aitask_skillrun.sh` in 5 touchpoints

Mirror the t777_2 / t777_4 pattern exactly.

| File | Entry | Position hint |
|------|-------|---------------|
| `.claude/settings.local.json` | `"Bash(./.aitask-scripts/aitask_skillrun.sh:*)"` in `permissions.allow` | Adjacent to `aitask_skill_render.sh:*` and `aitask_skill_verify.sh:*` entries |
| `.gemini/policies/aitasks-whitelist.toml` | `[[rule]]` block with `commandPrefix = "./.aitask-scripts/aitask_skillrun.sh"`, `decision = "allow"`, `priority = 100` | Adjacent to existing skill_render / skill_verify blocks |
| `seed/claude_settings.local.json` | Mirror of Claude runtime entry | Same neighborhood |
| `seed/geminicli_policies/aitasks-whitelist.toml` | Mirror of Gemini runtime block | Same neighborhood |
| `seed/opencode_config.seed.json` | `"./.aitask-scripts/aitask_skillrun.sh *": "allow"` | Same neighborhood |

Codex exempt per CLAUDE.md "Adding a New Helper Script".

## Pitfalls

- **Lib extraction must be byte-identical at the call sites.** The refactor of `aitask_codeagent.sh` (Step 0) is a pure move — function bodies, signatures, error messages, and return values must be unchanged. The verification 1 (before/after diff of `./ait codeagent resolve`) is load-bearing: any divergence indicates a copy/paste error.
- **`get_cli_model_id` depends on `$METADATA_DIR` + `jq`.** Today `aitask_codeagent.sh:20` sets `METADATA_DIR="${TASK_DIR:-aitasks}/metadata"` — a relative path that works because `ait` always `cd`s to the repo root before invoking scripts. The lib must keep this convention with the same defensive default so it works for any caller (`aitask_codeagent.sh` AND `aitask_skillrun.sh`):
  ```bash
  METADATA_DIR="${METADATA_DIR:-${TASK_DIR:-aitasks}/metadata}"
  ```
  The `:-` ensures a caller that already set `METADATA_DIR` (i.e., aitask_codeagent.sh post-refactor) keeps its value. Test by running `cd /tmp && bash -c 'cd /home/ddt/Work/aitasks && ./.aitask-scripts/aitask_skillrun.sh pick --dry-run'` — must work because the wrapper `cd`s to `$REPO_ROOT` before invoking the lib functions.
- **EXIT trap does NOT fire on `exec`.** Bash semantics: `exec` replaces the shell, no EXIT trap runs. Therefore when `--profile-override` is set, the wrapper MUST fork the agent (`"${CMD[@]}"`) and `wait` for it, then run cleanup explicitly. Only the no-override path can use bare `exec`.
- **Override tempfile name uniqueness.** Use `$$_$(date +%s%N)` (PID + ns timestamp) or `mktemp` to avoid collisions when the same agent launches multiple skills in parallel. Don't write under `$TMPDIR` — the tempfile MUST live under `aitasks/metadata/profiles/local/` to be auto-discovered by `aitask_scan_profiles.sh`.
- **Override YAML `name:` field must match basename minus `.yaml`.** `aitask_scan_profiles.sh` resolves profiles by the YAML's `name:` field, not by filename. Forcing `merged["name"] = new_name` after the merge is load-bearing.
- **Codex prompt prefix is `$`, not `/`.** `aitask_codex_plan_invoke.py` types the prompt into Codex's composer; Codex parses `$aitask-pick` as its in-app skill alias. Use `"\$${skill} ${forwarded}"` exactly, with the `$` escaped to keep bash from variable-expanding it.
- **No `claude -p`.** Per `feedback_avoid_claude_p_for_skill_invocation` — always launch interactively. The wrapper has zero `-p` paths.
- **`require_ait_python` is the canonical one-shot interpreter resolver.** Per CLAUDE.md "TUI Conventions": one-shot CLIs use `require_ait_python`, not `require_ait_python_fast` (no Textual-class TUI here).
- **PyYAML availability.** The framework venv installs PyYAML (verified — `aitask_settings.sh` and others import it). The override-merge Python heredoc relies on this. If a future change drops PyYAML, the merge must fall back to a simpler YAML-flat-key parser.
- **Bypass update check.** `check_for_updates` (`ait:101-164`) prints "[ait] Update available" lines that would interleave with the agent's startup output. Add `skillrun` to the skip-list at `ait:167-170`.
- **5-touchpoint whitelist drift risk.** Per CLAUDE.md "Adding a New Helper Script", a missing entry causes every user of the corresponding agent to be prompted forever. Audit all 5 touchpoints; do not skip any.

## Verification Steps

**Refactor sanity (Step 0):**

1. **codeagent behavior unchanged after lib extraction:**
   ```bash
   ./ait codeagent resolve pick      # before refactor: capture output
   ./ait codeagent check claudecode/opus4_7_1m
   ./ait codeagent list-models claudecode
   # Run the same three after refactor; assert byte-identical output.
   ```

2. **`bash tests/test_agent_string.sh`** — all 12 cases PASS.

3. **`shellcheck -x .aitask-scripts/lib/agent_string.sh .aitask-scripts/aitask_codeagent.sh`** — clean.

**Skillrun behavior:**

4. **Dry-run (no agent launch required):**
   ```bash
   ./ait skillrun pick --profile fast --dry-run -- 777
   ```
   Expected stdout: `DRY_RUN: claude --model claude-opus-4-7-... /aitask-pick\ --profile\ fast\ 777` (with whatever `cli_id` the lib resolves for `opus4_7_1m`).

5. **Dry-run for each agent via `--agent-string`:**
   ```bash
   ./ait skillrun pick --profile fast --agent-string claudecode/opus4_7_1m --dry-run -- 777
   ./ait skillrun pick --profile fast --agent-string geminicli/gemini3pro --dry-run -- 777
   ./ait skillrun pick --profile fast --agent-string codex/gpt5codex --dry-run -- 777
   ./ait skillrun pick --profile fast --agent-string opencode/openai-gpt5 --dry-run -- 777
   ```
   Expected: each prints the synthesized argv with the correct binary, model flag, and CLI ID resolved from the lib. (Model names must exist in the respective `models_<agent>.json`; pick existing entries before running.)

6. **`AIT_AGENT_STRING` env override:**
   ```bash
   AIT_AGENT_STRING=geminicli/gemini3pro ./ait skillrun pick --profile fast --dry-run -- 777
   ```
   Expected: dry-run output uses gemini.

7. **Profile autodetect:**
   ```bash
   ./ait skillrun pick --dry-run -- 777
   ```
   Expected: dry-run output uses `--profile fast` (the configured `default_profiles.pick: fast` in `project_config.yaml`).

8. **`--profile-override` dry-run preview:**
   ```bash
   echo "skip_task_confirmation: false" | ./ait skillrun pick \
       --profile fast --profile-override - --dry-run -- 777
   ```
   Expected: stdout shows the DRY_RUN line (with `--profile fast`, NOT a `_skillrun_*` name); stderr shows the merged YAML preview with `skip_task_confirmation: false` overriding the base. No tempfile created.

9. **Long-form skill rejection:**
   ```bash
   ./ait skillrun aitask-pick --profile fast --dry-run 2>&1 | head -1
   ```
   Expected: `skillrun: pass the short skill name (drop the 'aitask-' prefix). Got: 'aitask-pick'`.

10. **Bad agent-string rejection:**
    ```bash
    ./ait skillrun pick --agent-string bogus --dry-run 2>&1 | head -1
    ./ait skillrun pick --agent-string fakeagent/x --dry-run 2>&1 | head -1
    ```
    Expected: both die with the lib's parse_agent_string error messages (validates the source-of-truth is being exercised).

11. **`--profile-override` live mode** (post-t777_6 only — current state has no `.j2` for pick):
    ```bash
    echo "skip_task_confirmation: false" | ./ait skillrun pick \
        --profile fast --profile-override - -- 777
    # Confirm: tempfile created at aitasks/metadata/profiles/local/_skillrun_<unique>.yaml
    # Confirm: agent picks up the new profile (skip_task_confirmation: false)
    # Confirm: tempfile deleted after agent exits
    ```

12. **`shellcheck .aitask-scripts/aitask_skillrun.sh`** — clean.

13. **5 whitelist files contain exactly one `aitask_skillrun.sh` entry each:**
    ```bash
    for f in .claude/settings.local.json .gemini/policies/aitasks-whitelist.toml \
             seed/claude_settings.local.json seed/geminicli_policies/aitasks-whitelist.toml \
             seed/opencode_config.seed.json; do
        echo "$f: $(grep -c aitask_skillrun "$f")"
    done
    ```
    Expected: each file shows `1`.

14. **`./ait --help`** mentions `skillrun`.

15. **`./ait skillrun --help`** prints usage and exits 0.

16. **Update-check bypass**: confirm `./ait skillrun --help` does NOT spawn the background curl in `check_for_updates`.

## Reference Files (for the implementer)

- `.aitask-scripts/aitask_skill_render.sh` — template for arg parsing, `mkdir -p` + atomic-mv, `require_ait_python` usage, scan_profiles parsing
- `.aitask-scripts/aitask_skill_verify.sh` — template for the `set -euo pipefail` + `source python_resolve.sh` + `cd $REPO_ROOT` header
- `.aitask-scripts/aitask_codeagent.sh:512-619` — canonical "build agent invocation" reference for all 4 agents
- `.aitask-scripts/aitask_codex_plan_invoke.py` — the pexpect helper that drives Codex; called from the codex branch
- `.aitask-scripts/aitask_skill_resolve_profile.sh` — profile resolver
- `.aitask-scripts/aitask_scan_profiles.sh` — profile enumerator (returns `local/<file>.yaml` for user-local overrides)
- `.claude/skills/task-workflow/stub-skill-pattern.md` §3h — argument forwarding contract (the user-facing `/<skill> --profile <name> <args>` form)
- `ait:167-170` — update-check skip-list
- `ait:185-191` — dispatcher insertion point

## Step 9 (Post-Implementation)

Standard child-task archival via `./.aitask-scripts/aitask_archive.sh 777_5`. Final Implementation Notes (in the archived plan) MUST document:
- Per-agent launch command shapes (for siblings t777_6..t777_15 to verify against when their stubs land).
- Override-tempfile lifecycle decisions (`mktemp` vs `$$_$(date +%s%N)`).
- Whether the codex `$<full_skill>` prefix needed any additional escaping when piped through `aitask_codex_plan_invoke.py`'s `--prompt`.
- The skip-list update at `ait:167-170` (so future `./ait <new-subcommand>` additions know to consider whether they should also skip update-check).
- Confirm `--model` flag works end-to-end with at least one agent (smoke test in dry-run is sufficient until siblings produce real `.j2` content).
- Note for sibling tasks t777_6..t777_15: when authoring stubs, verify the stub's `--profile` parse strips the pair from forwarded ARGUMENTS so the rendered variant doesn't see a duplicated/contradictory profile arg.

## Reuse Notes

- `aitask_skill_resolve_profile.sh` is the single source of truth for profile autodetection — never re-implement the userconfig/project_config precedence.
- `aitask_scan_profiles.sh` is the canonical profile enumerator (returns `name|description|filename` for every profile, including `local/*.yaml` overrides). Used for base profile resolution in `--profile-override`.
- `aitask_codex_plan_invoke.py` is the canonical Codex driver — owns the pexpect dance, the `/plan` prefix, and the prompt-submission timing. Do not reimplement Codex launch logic.
- `aitask_codeagent.sh:80-83` is the authoritative per-agent model-flag table (`--model` for claude/opencode, `-m` for gemini/codex). Mirror it; do NOT introduce a third source of truth (per `feedback_single_source_of_truth_for_versions`). If sibling tasks add new agents, update both files together.
- The 5-touchpoint whitelist precedent from t777_2 / t777_4 is documented in CLAUDE.md "Adding a New Helper Script" — follow that checklist verbatim for `aitask_skillrun.sh`.
