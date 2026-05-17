#!/usr/bin/env bash
# aitask_skillrun.sh - Launch a code agent with a profile-aware aitask skill.
#
# Usage:
#   aitask_skillrun.sh <skill> [--profile <name>] [--agent-string <agent>/<model>]
#                              [--profile-override <yaml|->] [--dry-run] [-- <args>...]
#
# <skill> is the SHORT form (no aitask- prefix): pick, explore, review, qa, ...
# Wrapper synthesizes full_skill="aitask-<skill>" for slash command + profile lookup.
#
# --agent-string defaults to $DEFAULT_AGENT_STRING (from lib/agent_string.sh).
# Model resolution (symbolic name -> CLI ID) is performed by the lib's
# get_cli_model_id - single source of truth shared with aitask_codeagent.sh.
#
# Per-agent invocation (full_skill = "aitask-<skill>"; binary/model_flag/cli_id
# resolved from agent-string via lib/agent_string.sh):
#   claudecode -> exec claude --model <cli_id> "/<full_skill> --profile <profile> <args>"
#   geminicli  -> exec gemini -m <cli_id> "/<full_skill> --profile <profile> <args>"
#   opencode   -> exec opencode --model <cli_id> --prompt "/<full_skill> --profile <profile> <args>"
#   codex      -> python3 aitask_codex_plan_invoke.py --prompt "$<full_skill> --profile <profile> <args>" -- codex -m <cli_id>
#
# Does NOT use `claude -p` (per feedback_avoid_claude_p_for_skill_invocation).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=.aitask-scripts/lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=.aitask-scripts/lib/agent_string.sh
source "$SCRIPT_DIR/lib/agent_string.sh"

cd "$REPO_ROOT"

usage() {
    cat <<'EOF' >&2
Usage: ait skillrun <skill> [options] [-- <args>...]

Arguments:
  <skill>                    Skill short name (drop the 'aitask-' prefix): pick, explore, review, qa, ...

Options:
  --profile <name>           Execution profile (default: resolved via aitask_skill_resolve_profile.sh).
  --agent-string <a>/<m>     Agent and model in canonical form (e.g. claudecode/opus4_7_1m).
                             Defaults to $AIT_AGENT_STRING env var, then $DEFAULT_AGENT_STRING.
  --profile-override <file>  YAML file (or '-' for stdin) merged on top of the resolved profile.
                             In live mode, the merged YAML is written to
                             aitasks/metadata/profiles/local/_skillrun_<unique>.yaml and the
                             agent receives --profile _skillrun_<unique>. Tempfile is deleted
                             on exit. In --dry-run, the merged YAML is printed to stderr
                             (preview mode) and the tempfile is NOT created.
  --dry-run                  Print the synthesized launch command (DRY_RUN: ...) and exit;
                             do not invoke the agent.
  -h, --help                 Show this help.

Examples:
  ait skillrun pick                              # pick a task with the default profile + agent
  ait skillrun pick --profile fast 777_5         # explicit profile + skill arg
  ait skillrun pick --agent-string geminicli/gemini3pro --dry-run -- 777
  echo "skip_task_confirmation: false" | \
      ait skillrun pick --profile fast --profile-override - -- 777

Notes:
  - <skill> must be the SHORT form. Pass 'pick', not 'aitask-pick' - the wrapper synthesizes
    'aitask-pick' internally for the slash command.
  - Model resolution uses .aitask-scripts/lib/agent_string.sh, the same source of truth as
    'ait codeagent'. Run 'ait codeagent list-models <agent>' to see supported model names.
  - 'ait skillrun' always forwards '--profile <name>' to the slash command. Templated skills
    (those with .claude/skills/<skill>/SKILL.md.j2) parse it via the stub-dispatch flow
    (stub-skill-pattern.md). Non-templated skills generally ignore unknown leading args -
    skillrun therefore works as a universal launcher during the t777_6+ gradual conversion.
EOF
}

# --- Argument parsing ---

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
            echo "skillrun: unknown flag: $1" >&2; usage; exit 2 ;;
        *)
            if [[ -z "$skill" ]]; then
                skill="$1"; shift
            else
                args+=("$1"); shift
            fi ;;
    esac
done

[[ -z "$skill" ]] && { echo "skillrun: missing <skill>" >&2; usage; exit 2; }

# Reject the long-form name proactively so users don't end up looking for
# /aitask-aitask-pick (the synthesis would otherwise prepend aitask- twice).
case "$skill" in
    aitask-*) die "skillrun: pass the short skill name (drop the 'aitask-' prefix). Got: '$skill'" ;;
esac
full_skill="aitask-${skill}"

# --- Agent-string + per-CLI triple via lib ---

[[ -z "$agent_string" ]] && agent_string="${AIT_AGENT_STRING:-$DEFAULT_AGENT_STRING}"

parse_agent_string "$agent_string"
binary="$(get_cli_binary "$PARSED_AGENT")"
model_flag="$(get_model_flag "$PARSED_AGENT")"
cli_id="$(get_cli_model_id "$PARSED_AGENT" "$PARSED_MODEL")"

# --- Profile autodetection ---

if [[ -z "$profile" ]]; then
    profile="$("$SCRIPT_DIR/aitask_skill_resolve_profile.sh" "$skill")"
fi
[[ -z "$profile" ]] && die "skillrun: could not resolve profile for skill '$skill'"

# --- Profile-override merge ---

override_tempfile=""
cleanup_override() {
    [[ -n "$override_tempfile" && -f "$override_tempfile" ]] && rm -f "$override_tempfile"
}

stdin_tempfile=""
cleanup_stdin_tempfile() {
    [[ -n "$stdin_tempfile" && -f "$stdin_tempfile" ]] && rm -f "$stdin_tempfile"
}

if [[ -n "$profile_override" ]]; then
    # Resolve base profile YAML via aitask_scan_profiles.sh
    _scan="$("$SCRIPT_DIR/aitask_scan_profiles.sh")"
    base_filename="$(echo "$_scan" \
        | awk -F'|' -v n="$profile" '$1=="PROFILE" && $3==n {print $2; exit}')"
    [[ -z "$base_filename" ]] && die "skillrun: base profile '$profile' not found"
    base_path="$REPO_ROOT/aitasks/metadata/profiles/$base_filename"

    # If override is "-", capture stdin to a tempfile BEFORE invoking python.
    # The python heredoc below redirects stdin to the script source, so
    # sys.stdin would otherwise be empty.
    override_input_path="$profile_override"
    if [[ "$profile_override" == "-" ]]; then
        stdin_tempfile="$(mktemp)"
        trap cleanup_stdin_tempfile EXIT INT TERM
        cat > "$stdin_tempfile"
        override_input_path="$stdin_tempfile"
    fi

    PYTHON="$(require_ait_python)"

    if [[ "$dry_run" == true ]]; then
        # Preview merged YAML to stderr; no tempfile, no profile name change.
        {
            echo "--- merged profile preview (--profile-override --dry-run) ---"
            "$PYTHON" - "$base_path" "$override_input_path" <<'PYEOF'
import sys, yaml
base_path, override_path = sys.argv[1:3]
with open(base_path) as f:
    base = yaml.safe_load(f) or {}
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

        "$PYTHON" - "$base_path" "$override_input_path" "$override_tempfile" "$new_profile_name" <<'PYEOF'
import sys, yaml
base_path, override_path, out_path, new_name = sys.argv[1:5]
with open(base_path) as f:
    base = yaml.safe_load(f) or {}
with open(override_path) as f:
    override = yaml.safe_load(f) or {}
merged = {**base, **override}
merged["name"] = new_name
merged.setdefault("description", (base.get("description") or "") + " (per-run override)")
with open(out_path, "w") as f:
    yaml.safe_dump(merged, f, sort_keys=False)
PYEOF

        # Combined cleanup for both tempfiles. The trap is reinstalled here
        # to ensure both are removed regardless of which was created.
        trap 'cleanup_override; cleanup_stdin_tempfile' EXIT INT TERM
        profile="$new_profile_name"
    fi
fi

# --- Synthesize forwarded args: --profile <profile> <skill-args> ---

forwarded_args=("--profile" "$profile")
[[ ${#args[@]} -gt 0 ]] && forwarded_args+=("${args[@]}")
forwarded="${forwarded_args[*]}"

# --- Construct launch CMD per agent ---

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
        # Codex prompt syntax uses '$' prefix (mirroring aitask_codeagent.sh).
        PYTHON="$(require_ait_python)"
        codex_prompt="\$${full_skill} ${forwarded}"
        CMD=("$PYTHON" "$SCRIPT_DIR/aitask_codex_plan_invoke.py" "--prompt" "$codex_prompt" "--" "$binary" "$model_flag" "$cli_id")
        ;;
esac

# --- Dry-run: print and exit ---

if [[ "$dry_run" == true ]]; then
    printf 'DRY_RUN:'
    printf ' %q' "${CMD[@]}"
    printf '\n'
    exit 0
fi

# --- Exec the agent ---
#
# When --profile-override created a tempfile, we MUST fork (not exec) so the
# EXIT trap fires after agent termination. Bash semantics: exec replaces the
# shell before the EXIT trap can run.

if [[ -n "$override_tempfile" ]]; then
    "${CMD[@]}"
    rc=$?
    cleanup_override
    cleanup_stdin_tempfile
    exit "$rc"
else
    exec "${CMD[@]}"
fi
