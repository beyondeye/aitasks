#!/usr/bin/env bash
# aitask_add_model.sh - Register a known code-agent model and optionally
# promote it to the operational default.
#
# Companion to aitask-refresh-code-models. refresh-code-models discovers
# models via web research and only writes the registry; this helper skips
# web research, takes known inputs, and can additionally promote the new
# model to default across codeagent_config.json + DEFAULT_AGENT_STRING.
#
# Subcommands:
#   add-json                       Append model entry to models_<agent>.json + seed
#   promote-config                 Update codeagent_config.json defaults for ops
#                                  and record the model(s) the promotion
#                                  supersedes (lib/model_supersessions.json)
#   record-supersession            Record "<old> is superseded by <new>" alone
#                                  (e.g. the successor just registered by add-json);
#                                  the one subcommand that also accepts opencode,
#                                  whose lineages are declared, not registered
#   promote-default-agent-string   Update DEFAULT_AGENT_STRING in
#                                  lib/agent_string.sh + the resolution-chain
#                                  note in aitask_codeagent.sh (claudecode only)

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/atomic_write.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/atomic_write.sh"
# shellcheck source=lib/python_resolve.sh
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/python_resolve.sh"

REPO_ROOT="${AITASK_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

SUPPORTED_AGENTS=(claudecode codex)

# Framework-owned supersession table (t1910): "<old> is superseded by <new>",
# per agent. `ait upgrade` offers <new> to every op still configured with <old>.
SUPERSESSION_TABLE_REL=".aitask-scripts/lib/model_supersessions.json"

# --- Common helpers ---

require_jq() {
    command -v jq >/dev/null 2>&1 || die "jq is required. Install via your package manager."
}

# validate_agent <agent> [--allow-opencode]
# --allow-opencode is passed by record-supersession only: OpenCode models are
# CLI-discovered (aitask-refresh-code-models), so they are never registered or
# promoted here, but their lineages are declared like any other agent's.
validate_agent() {
    local a="$1" allow_opencode="${2:-}"
    [[ -z "$a" ]] && die "--agent is required"
    if [[ "$a" == "opencode" ]]; then
        [[ "$allow_opencode" == "--allow-opencode" ]] && return 0
        die "Agent 'opencode' is not supported. Use aitask-refresh-code-models for opencode (models are provider-gated and CLI-discovered)."
    fi
    local v
    for v in "${SUPPORTED_AGENTS[@]}"; do
        [[ "$a" == "$v" ]] && return 0
    done
    die "Unknown agent: '$a'. Supported: ${SUPPORTED_AGENTS[*]} (opencode → use aitask-refresh-code-models)."
}

validate_name() {
    local n="$1"
    [[ -z "$n" ]] && die "--name is required"
    [[ "$n" =~ ^[a-z][a-z0-9_]*$ ]] || die "Invalid model name: '$n'. Must match ^[a-z][a-z0-9_]*\$ (lowercase alphanumerics and underscores, starting with a letter)."
    # Reserved for aitask_resolve_detected_agent.sh fallbacks: a registered
    # unregistered_* name would let an unknown cli_id be credited to it.
    [[ "$n" != unregistered_* ]] || die "Invalid model name: '$n'. The 'unregistered_' prefix is reserved for agent-string fallbacks of unregistered models (see aitask_resolve_detected_agent.sh)."
}

validate_cli_id() {
    local id="$1"
    [[ -n "$id" ]] || die "--cli-id is required"
}

# Print a unified diff between `current` (pre-change) and the proposed content
# in `proposed`, labelled with the repo-relative `label` so users can spot it in
# dry-run output even though the proposed bytes sit in a tempfile. `current` is
# the resolved path: a label is relative to REPO_ROOT, not to the cwd, so
# testing the label itself would diff the wrong file whenever AITASK_REPO_ROOT
# points elsewhere.
print_diff() {
    local label="$1"
    local current="$2"
    local proposed="$3"
    if [[ -f "$current" ]]; then
        diff -u --label "a/$label" --label "b/$label" "$current" "$proposed" || true
    else
        diff -u --label "a/$label" --label "b/$label" /dev/null "$proposed" || true
    fi
}

# Install validated staged content onto its destination, preserving the
# destination's own current mode.
#
# The staging temps live in $TMPDIR and must NOT be `mv`d into place: mktemp
# creates 0600 and the rename hands that mode to the destination, silently
# narrowing files whose read bits git does not track (t1684). A `mv` from
# $TMPDIR also degrades into a non-atomic copy across filesystems, and a `mv`
# REPLACES a symlinked destination instead of writing through it.
#
# ait_atomic_render stages a temp beside the *resolved* destination, chmods it
# to that destination's current mode, and renames it in — so a symlinked
# destination keeps its link and its backing file is the one updated, matching
# what the `cat > "$dest"` in promote-default-agent-string already did.
#
# `cat "$src"` is a single-command renderer, so its status IS the renderer's
# status and ait_atomic_render tests it — the "guard every fallible command"
# rule at the top of lib/atomic_write.sh needs no extra `|| return 1` here.
commit_staged() {
    local src="$1" dest="$2"
    ait_atomic_render "$dest" cat "$src"
}

# --- Subcommand: add-json ---

cmd_add_json() {
    local agent="" name="" cli_id="" notes="" dry_run=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --name)    name="$2"; shift 2 ;;
            --cli-id)  cli_id="$2"; shift 2 ;;
            --notes)   notes="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            *) die "Unknown argument to add-json: '$1'" ;;
        esac
    done

    validate_agent "$agent"
    validate_name "$name"
    validate_cli_id "$cli_id"

    local metadata_rel="aitasks/metadata/models_${agent}.json"
    local seed_rel="seed/models_${agent}.json"
    local metadata_file="$REPO_ROOT/$metadata_rel"
    local seed_file="$REPO_ROOT/$seed_rel"

    [[ -f "$metadata_file" ]] || die "Model registry not found: $metadata_rel"

    if jq -e --arg n "$name" 'any(.models[]?; .name == $n)' "$metadata_file" >/dev/null; then
        die "Model '$name' already exists in $metadata_rel"
    fi

    local tmp_metadata
    tmp_metadata=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_meta_XXXXXX.json")
    jq \
        --arg name "$name" \
        --arg cli_id "$cli_id" \
        --arg notes "$notes" \
        '.models += [{
            "name": $name,
            "cli_id": $cli_id,
            "notes": $notes,
            "verified": {},
            "verifiedstats": {}
        }]' \
        "$metadata_file" > "$tmp_metadata"
    jq . "$tmp_metadata" >/dev/null || { rm -f "$tmp_metadata"; die "Produced JSON is invalid for $metadata_rel"; }

    local tmp_seed=""
    if [[ -f "$seed_file" ]]; then
        if jq -e --arg n "$name" 'any(.models[]?; .name == $n)' "$seed_file" >/dev/null; then
            rm -f "$tmp_metadata"
            die "Model '$name' already exists in $seed_rel"
        fi
        tmp_seed=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_seed_XXXXXX.json")
        jq \
            --arg name "$name" \
            --arg cli_id "$cli_id" \
            --arg notes "$notes" \
            '.models += [{
                "name": $name,
                "cli_id": $cli_id,
                "notes": $notes,
                "verified": {},
                "verifiedstats": {}
            }]' \
            "$seed_file" > "$tmp_seed"
        jq . "$tmp_seed" >/dev/null || { rm -f "$tmp_metadata" "$tmp_seed"; die "Produced JSON is invalid for $seed_rel"; }
    fi

    if $dry_run; then
        print_diff "$metadata_rel" "$metadata_file" "$tmp_metadata"
        [[ -n "$tmp_seed" ]] && print_diff "$seed_rel" "$seed_file" "$tmp_seed"
        rm -f "$tmp_metadata" "$tmp_seed"
        return 0
    fi

    commit_staged "$tmp_metadata" "$metadata_file" \
        || { rm -f "$tmp_metadata" "$tmp_seed"; die "Failed to write $metadata_rel"; }
    if [[ -n "$tmp_seed" ]]; then
        commit_staged "$tmp_seed" "$seed_file" \
            || { rm -f "$tmp_metadata" "$tmp_seed"; die "Failed to write $seed_rel"; }
    fi
    rm -f "$tmp_metadata" "$tmp_seed"
    info "Added model $agent/$name to $metadata_rel${tmp_seed:+ (+ $seed_rel)}"
}

# --- Supersession recording (t1910) ---

# Compute the supersession-table change for one promotion or declaration into
# <output>, via `aitask_model_supersession.py record` (one guarded edge-adder for
# both callers). Prints the helper's RECORDED:/RECORDED_SIBLING:/SKIPPED:/WARN:/
# BLOCKED:/NOTE: lines. Returns the helper's status: 0 ok, 3 blocked, else error.
supersession_record() {
    local agent="$1" output="$2" source="$3"
    shift 3
    local python
    python="$(require_ait_python)" || return 1
    "$python" "$SCRIPT_DIR/aitask_model_supersession.py" record \
        --table "$REPO_ROOT/$SUPERSESSION_TABLE_REL" \
        --output "$output" \
        --models "$REPO_ROOT/aitasks/metadata/models_${agent}.json" \
        --agent "$agent" \
        --source "$source" \
        "$@"
}

SUPERSESSION_BLOCKED_HELP="Resolve the BLOCKED line(s) above, then re-run:
  - partial:       the old model is still another seed op's default — add those ops to --ops,
                   or promote with --no-supersession (declare the lineage later with
                   'record-supersession' once no seed default uses the old model);
  - unregistered:  register the new model first (add-json);
  - conflict/cycle/seed_invariant: the table already says otherwise — promote with
                   --no-supersession, and fix .aitask-scripts/lib/model_supersessions.json by hand
                   only if the existing edge is wrong.
Nothing was written."

# --- Subcommand: promote-config ---

cmd_promote_config() {
    local agent="" name="" ops_csv="" dry_run=false
    local no_supersession=false assume_registered=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --name)    name="$2"; shift 2 ;;
            --ops)     ops_csv="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            --no-supersession)   no_supersession=true; shift ;;
            --assume-registered) assume_registered=true; shift ;;
            *) die "Unknown argument to promote-config: '$1'" ;;
        esac
    done

    validate_agent "$agent"
    validate_name "$name"
    [[ -z "$ops_csv" ]] && die "--ops is required (comma-separated)"
    # A preview of a model `add-json --dry-run` has not written yet. An apply
    # always validates against the real registry: add-json runs first.
    if $assume_registered && ! $dry_run; then
        die "--assume-registered is only valid with --dry-run"
    fi

    local metadata_rel="aitasks/metadata/codeagent_config.json"
    local seed_rel="seed/codeagent_config.json"
    local metadata_file="$REPO_ROOT/$metadata_rel"
    local seed_file="$REPO_ROOT/$seed_rel"
    local table_file="$REPO_ROOT/$SUPERSESSION_TABLE_REL"

    [[ -f "$metadata_file" ]] || die "Config not found: $metadata_rel"

    local new_value="${agent}/${name}"
    local ops_json
    ops_json=$(printf '%s' "$ops_csv" | jq -R -c 'split(",")')

    # Only patch keys that already exist. Missing keys are silently skipped
    # per-file — e.g. seed has only the canonical 6 ops, so brainstorm-* keys
    # are skipped in seed without failing the command.
    local tmp_metadata
    tmp_metadata=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_cfg_XXXXXX.json")
    jq \
        --argjson ops "$ops_json" \
        --arg new_value "$new_value" \
        '
        reduce $ops[] as $op (.;
            if (.defaults // {}) | has($op) then .defaults[$op] = $new_value else . end
        )
        ' "$metadata_file" > "$tmp_metadata"
    jq . "$tmp_metadata" >/dev/null || { rm -f "$tmp_metadata"; die "Produced JSON is invalid for $metadata_rel"; }

    local tmp_seed=""
    if [[ -f "$seed_file" ]]; then
        tmp_seed=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_cfg_seed_XXXXXX.json")
        jq \
            --argjson ops "$ops_json" \
            --arg new_value "$new_value" \
            '
            reduce $ops[] as $op (.;
                if (.defaults // {}) | has($op) then .defaults[$op] = $new_value else . end
            )
            ' "$seed_file" > "$tmp_seed"
        jq . "$tmp_seed" >/dev/null || { rm -f "$tmp_metadata" "$tmp_seed"; die "Produced JSON is invalid for $seed_rel"; }
    fi

    # Supersession (t1910): the seed's old values of the promoted ops are the
    # framework defaults downstream projects still carry; recording them lets
    # `ait upgrade` offer the new model. Computed BEFORE any write, so a refusal
    # or a Python failure leaves every file untouched.
    local tmp_table="" record_out="" record_rc=0 recorded=false
    if ! $no_supersession; then
        if [[ -z "$tmp_seed" ]]; then
            echo "SKIPPED:no_seed"
        else
            tmp_table=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_supersession_XXXXXX.json")
            local record_args=(--new "$name" --seed-before "$seed_file" --seed-after "$tmp_seed")
            $assume_registered && record_args+=(--assume-registered)
            record_out=$(supersession_record "$agent" "$tmp_table" \
                "promote-config $(date +%Y-%m-%d)" "${record_args[@]}") || record_rc=$?
            [[ -n "$record_out" ]] && printf '%s\n' "$record_out"
            if [[ "$record_rc" -ne 0 && "$record_rc" -ne 3 ]]; then
                rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"
                die "Supersession recording failed (exit $record_rc) — nothing was written"
            fi
            if [[ "$record_rc" -eq 3 ]] && ! $dry_run; then
                rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"
                die "Promotion refused: the supersession it implies cannot be recorded.
$SUPERSESSION_BLOCKED_HELP"
            fi
            grep -q '^RECORDED' <<< "$record_out" && recorded=true
        fi
    fi

    if $dry_run; then
        print_diff "$metadata_rel" "$metadata_file" "$tmp_metadata"
        [[ -n "$tmp_seed" ]] && print_diff "$seed_rel" "$seed_file" "$tmp_seed"
        $recorded && print_diff "$SUPERSESSION_TABLE_REL" "$table_file" "$tmp_table"
        rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"
        return 0
    fi

    commit_staged "$tmp_metadata" "$metadata_file" \
        || { rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"; die "Failed to write $metadata_rel"; }
    if [[ -n "$tmp_seed" ]]; then
        commit_staged "$tmp_seed" "$seed_file" \
            || { rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"; die "Failed to write $seed_rel"; }
    fi
    if $recorded; then
        commit_staged "$tmp_table" "$table_file" \
            || { rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"; die "Failed to write $SUPERSESSION_TABLE_REL"; }
    fi
    rm -f "$tmp_metadata" "$tmp_seed" "$tmp_table"
    info "Promoted $new_value for ops: $ops_csv"
    if $recorded; then
        echo "NOTE: commit $SUPERSESSION_TABLE_REL (supersession recorded)"
    fi
}

# --- Subcommand: record-supersession ---

# Declare "<agent>/<old> is superseded by <agent>/<new>" on its own — the
# successor of a model registered in the same run (add-json, then this), a
# lineage a partial promotion could not record (promote-config
# --no-supersession) once no seed default uses <old> any more, or any lineage
# declared later. Same guards as promote-config. --assume-registered (dry-run
# only) previews a <new> that add-json has not written yet; an apply always
# validates against the real registry.
cmd_record_supersession() {
    local agent="" old="" new="" dry_run=false assume_registered=false
    local variant_change="" has_variant_change=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --old)     old="$2"; shift 2 ;;
            --new)     new="$2"; shift 2 ;;
            --variant-change) variant_change="$2"; has_variant_change=true; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            --assume-registered) assume_registered=true; shift ;;
            *) die "Unknown argument to record-supersession: '$1'" ;;
        esac
    done

    validate_agent "$agent" --allow-opencode
    validate_name "$old"
    validate_name "$new"
    if $assume_registered && ! $dry_run; then
        die "--assume-registered is only valid with --dry-run"
    fi
    if $has_variant_change && [[ -z "$variant_change" ]]; then
        die "--variant-change needs a non-empty reason"
    fi

    local seed_rel="seed/codeagent_config.json"
    local seed_file="$REPO_ROOT/$seed_rel"
    local table_file="$REPO_ROOT/$SUPERSESSION_TABLE_REL"
    [[ -f "$seed_file" ]] || die "record-supersession needs $seed_rel: supersession is recorded in the framework source repository"

    local tmp_table record_out="" record_rc=0
    local record_args=(--new "$new" --old "$old" --seed "$seed_file")
    $assume_registered && record_args+=(--assume-registered)
    $has_variant_change && record_args+=(--variant-change "$variant_change")
    tmp_table=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_supersession_XXXXXX.json")
    record_out=$(supersession_record "$agent" "$tmp_table" \
        "record-supersession $(date +%Y-%m-%d)" "${record_args[@]}") || record_rc=$?
    [[ -n "$record_out" ]] && printf '%s\n' "$record_out"
    if [[ "$record_rc" -eq 3 ]]; then
        rm -f "$tmp_table"
        die "Refused: the supersession cannot be recorded (see the BLOCKED line(s) above). Nothing was written."
    fi
    if [[ "$record_rc" -ne 0 ]]; then
        rm -f "$tmp_table"
        die "Supersession recording failed (exit $record_rc) — nothing was written"
    fi
    if ! grep -q '^RECORDED' <<< "$record_out"; then
        rm -f "$tmp_table"
        info "Nothing to record for $agent/$old -> $agent/$new"
        return 0
    fi

    if $dry_run; then
        print_diff "$SUPERSESSION_TABLE_REL" "$table_file" "$tmp_table"
        rm -f "$tmp_table"
        return 0
    fi
    commit_staged "$tmp_table" "$table_file" \
        || { rm -f "$tmp_table"; die "Failed to write $SUPERSESSION_TABLE_REL"; }
    rm -f "$tmp_table"
    info "Recorded $agent/$old -> $agent/$new in $SUPERSESSION_TABLE_REL"
    echo "NOTE: commit $SUPERSESSION_TABLE_REL (supersession recorded)"
}

# --- Subcommand: promote-default-agent-string ---

cmd_promote_default_agent_string() {
    local agent="" name="" dry_run=false
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --agent)   agent="$2"; shift 2 ;;
            --name)    name="$2"; shift 2 ;;
            --dry-run) dry_run=true; shift ;;
            *) die "Unknown argument to promote-default-agent-string: '$1'" ;;
        esac
    done

    validate_agent "$agent"
    validate_name "$name"

    if [[ "$agent" != "claudecode" ]]; then
        die "promote-default-agent-string only supports agent 'claudecode' (got '$agent'). Other agents do not have a hardcoded DEFAULT_AGENT_STRING."
    fi

    local new_value="${agent}/${name}"

    # DEFAULT_AGENT_STRING lives in lib/agent_string.sh as a parameter-expansion
    # default: DEFAULT_AGENT_STRING="${DEFAULT_AGENT_STRING:-<value>}" (callers
    # may pre-set it to override). The resolution-chain help note still lives
    # in aitask_codeagent.sh, so this subcommand patches two files.
    local lib_rel=".aitask-scripts/lib/agent_string.sh"
    local note_rel=".aitask-scripts/aitask_codeagent.sh"
    local lib_file="$REPO_ROOT/$lib_rel"
    local note_file="$REPO_ROOT/$note_rel"
    [[ -f "$lib_file" ]]  || die "Source file not found: $lib_rel"
    [[ -f "$note_file" ]] || die "Source file not found: $note_rel"

    # --- Patch 1: DEFAULT_AGENT_STRING in lib/agent_string.sh ---
    # Preserve the ${DEFAULT_AGENT_STRING:-...} parameter-expansion shape so the
    # caller-override capability survives; only swap the default value.
    local tmp_lib
    tmp_lib=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_lib_XXXXXX.sh")
    cp "$lib_file" "$tmp_lib"
    sed_inplace "s|^DEFAULT_AGENT_STRING=\"\${DEFAULT_AGENT_STRING:-.*}\"|DEFAULT_AGENT_STRING=\"\${DEFAULT_AGENT_STRING:-${new_value}}\"|" "$tmp_lib"
    if ! grep -q "^DEFAULT_AGENT_STRING=\"\${DEFAULT_AGENT_STRING:-${new_value}}\"\$" "$tmp_lib"; then
        rm -f "$tmp_lib"
        die "Failed to update DEFAULT_AGENT_STRING in $lib_rel (anchor pattern did not match)"
    fi

    # --- Patch 2: resolution-chain note in aitask_codeagent.sh ---
    local tmp_note
    tmp_note=$(mktemp_suffixed "${TMPDIR:-/tmp}/aitask_add_model_note_XXXXXX.sh")
    cp "$note_file" "$tmp_note"
    sed_inplace "s|^\(  4\. Hardcoded default: \).*|\1${new_value}|" "$tmp_note"
    if ! grep -q "^  4\. Hardcoded default: ${new_value}\$" "$tmp_note"; then
        rm -f "$tmp_lib" "$tmp_note"
        die "Failed to update resolution-chain note in $note_rel (anchor pattern did not match)"
    fi

    if $dry_run; then
        print_diff "$lib_rel" "$lib_file" "$tmp_lib"
        print_diff "$note_rel" "$note_file" "$tmp_note"
        rm -f "$tmp_lib" "$tmp_note"
        return 0
    fi

    # The `cat "$tmp" > "$file"` this replaces already preserved each file's
    # mode, but it truncated the destination before writing a byte — the
    # reader-visible window lib/atomic_write.sh exists to close. commit_staged
    # keeps the mode preservation and the follow-the-symlink behaviour, and
    # adds atomic visibility.
    commit_staged "$tmp_lib" "$lib_file" \
        || { rm -f "$tmp_lib" "$tmp_note"; die "Failed to write $lib_rel"; }
    commit_staged "$tmp_note" "$note_file" \
        || { rm -f "$tmp_lib" "$tmp_note"; die "Failed to write $note_rel"; }
    rm -f "$tmp_lib" "$tmp_note"
    info "Updated DEFAULT_AGENT_STRING to $new_value in $lib_rel (resolution-chain note in $note_rel)"
}

# --- Main dispatcher ---

usage() {
    cat <<'EOF'
Usage: aitask_add_model.sh <subcommand> [options]

Subcommands:
  add-json                     --agent <a> --name <n> --cli-id <id> --notes <s> [--dry-run]
  promote-config               --agent <a> --name <n> --ops <csv>             [--dry-run]
                               [--no-supersession] [--assume-registered]
  record-supersession          --agent <a> --old <n> --new <n>                [--dry-run]
                               [--assume-registered] [--variant-change <reason>]
  promote-default-agent-string --agent <a> --name <n>                         [--dry-run]

Supported agents: claudecode, codex; record-supersession also accepts opencode.
Use aitask-refresh-code-models to register opencode models (provider-gated,
CLI-discovered).

--dry-run prints a unified diff and exits without writing any file.

promote-config also records the seed model(s) the promotion replaces as
superseded by the new one (.aitask-scripts/lib/model_supersessions.json), so
`ait upgrade` offers the new model to projects still using the old one. A
supersession is global, so a promotion that leaves the old model as another
seed op's default is refused (BLOCKED:partial) unless --no-supersession is
given; record-supersession declares it later. record-supersession also
declares the successor of a model that was never a default. --assume-registered
(dry-run only, on promote-config and record-supersession) previews a model that
add-json has not written yet.

An opencode lineage stays within one provider and model line, and within one
variant (mini, pro, flash ...) unless --variant-change records why the edge
changes tier; --old must be registered in models_opencode.json (any status).

The AITASK_REPO_ROOT env var overrides the repo root used for file
resolution (defaults to the parent dir of .aitask-scripts). This is used
by tests to run against isolated fixtures.
EOF
}

main() {
    require_jq
    local cmd="${1:-}"
    shift || true
    case "$cmd" in
        add-json)                     cmd_add_json "$@" ;;
        promote-config)               cmd_promote_config "$@" ;;
        record-supersession)          cmd_record_supersession "$@" ;;
        promote-default-agent-string) cmd_promote_default_agent_string "$@" ;;
        ""|help|-h|--help)            usage ;;
        *)                            die "Unknown subcommand: '$cmd' (see --help)" ;;
    esac
}

main "$@"
