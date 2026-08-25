#!/usr/bin/env bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/cross_repo_reexec.sh
source "$SCRIPT_DIR/lib/cross_repo_reexec.sh"
# shellcheck source=lib/followup_kinds_sh.sh
# Lazy + memoising: sourcing costs nothing until followup_kinds_pipe is called,
# which only happens when --followup-kind is actually supplied.
source "$SCRIPT_DIR/lib/followup_kinds_sh.sh"

TASK_DIR="aitasks"
TASK_TYPES_FILE="$TASK_DIR/metadata/task_types.txt"

# Cross-repo redirect (t832_1): if `--project <name>` appears anywhere in
# argv, resolve <name> to a sibling aitasks project root and re-exec the
# sibling's own aitask_ls.sh with `--project <name>` stripped. The
# forwarded argv keeps all other flags intact.
cross_repo_reexec_or_continue "aitask_ls.sh" "$@"
if [[ ${#CROSS_REPO_FORWARDED_ARGV[@]} -gt 0 ]]; then
    set -- "${CROSS_REPO_FORWARDED_ARGV[@]}"
else
    set --
fi

# --- Help Function ---
show_help() {
    cat << EOF
Usage: $(basename "$0") [OPTIONS] [NUMBER]

Scans the '$TASK_DIR' subdirectory for markdown task files (t<number>_<name>.md),
parses their metadata, and lists them ordered by:
  1. Status (Unblocked tasks first)
  2. Priority (High -> Low)
  3. Effort   (Low -> High)

ARGUMENTS:
  NUMBER        Return only the top N tasks.

OPTIONS:
  -v            Verbose mode. Displays metadata (Status, Priority, Effort)
                alongside the filename.
  -s, --status  Filter by status. Values: Ready, Editing, Implementing, Postponed, Done, Folded, all
                Default: Ready (only show Ready tasks)
  -l, --labels LABELS  Filter by labels (comma-separated). Only show tasks
                with at least one matching label.
  --type TYPE   Filter by issue type (see aitasks/metadata/task_types.txt).
                A task with no issue_type: field counts as 'feature'.
  --followup-kind KIND  Filter to auto-spawned follow-ups of one kind.
  --no-followup-kind    Only tasks that are NOT auto-spawned follow-ups
                (genuine new work). Mutually exclusive with --followup-kind.
  --plan-approved       Only tasks carrying plan_approved_at -- an approved
                plan whose implementation was deliberately deferred.
  --no-plan-approved    Only tasks WITHOUT that marker. Mutually exclusive
                with --plan-approved. Both filters work with or without -v;
                the marker itself is shown only in the -v line.
  -c, --children PARENT  List only children of specified parent task number.
  --all-levels  Show all tasks including children (flat list).
  --tree        Show hierarchical tree view with children indented.
  --project NAME  Re-exec this listing inside the sibling aitasks project
                NAME (resolved via the per-user registry at
                ~/.config/aitasks/projects.yaml). Must appear before any
                other flag/argument.
  -h, --help    Show this help message.

METADATA FORMAT:
  The file uses YAML front matter (lines between --- markers).
  Missing properties default to 'Medium'.

    ---
    priority: high|medium|low
    effort: high|medium|low
    depends: [1, 3, 5]
    issue_type: bug|chore|documentation|enhancement|feature|manual_verification|
                performance|refactor|style|test
    followup_kind: carry_over|docs_gap|manual_verification|qa_test_gap|
                review_finding|risk_mitigation|upstream_defect|verification_failure
                (absent = genuine new work, not an auto-spawned follow-up)
    status: Editing|Implementing|Postponed|Ready|Done|Folded
    plan_approved_at: 2026-02-01 14:30
                (absent = no approved-but-deferred plan)
    labels: [ui, backend]
    assigned_to: email@example.com
    created_at: 2026-02-01 14:30
    updated_at: 2026-02-01 15:45
    ---
EOF
}

# --- Argument Parsing ---
# If no arguments are provided, show help
if [ $# -eq 0 ]; then
    show_help
    exit 0
fi

VERBOSE=false
LIMIT=0
STATUS_FILTER="Ready"
LABELS_FILTER=""
TYPE_FILTER=""
FOLLOWUP_KIND_FILTER=""
NO_FOLLOWUP_KIND=false
PLAN_APPROVED_FILTER=false
NO_PLAN_APPROVED=false
CHILDREN_OF=""
ALL_LEVELS=false
TREE_VIEW=false

# Parse args
while [[ $# -gt 0 ]]; do
    case $1 in
        -v)
            VERBOSE=true
            shift
            ;;
        -s|--status)
            STATUS_FILTER="$2"
            shift 2
            ;;
        -l|--labels)
            LABELS_FILTER="$2"
            shift 2
            ;;
        --type)
            TYPE_FILTER="$2"
            shift 2
            ;;
        --followup-kind)
            FOLLOWUP_KIND_FILTER="$2"
            shift 2
            ;;
        --plan-approved)
            PLAN_APPROVED_FILTER=true
            shift
            ;;
        --no-plan-approved)
            NO_PLAN_APPROVED=true
            shift
            ;;
        --no-followup-kind)
            NO_FOLLOWUP_KIND=true
            shift
            ;;
        -c|--children)
            CHILDREN_OF="$2"
            shift 2
            ;;
        --all-levels)
            ALL_LEVELS=true
            shift
            ;;
        --tree)
            TREE_VIEW=true
            ALL_LEVELS=true
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *[0-9]*)
            if [[ "$1" =~ ^[0-9]+$ ]]; then
                LIMIT=$1
                shift
            else
                echo "Unknown argument: $1"
                show_help
                exit 1
            fi
            ;;
        *)
            echo "Unknown argument: $1"
            show_help
            exit 1
            ;;
    esac
done

# Validate filter VALUES before any scanning work. A silent zero-match is
# indistinguishable from "no such tasks", which is exactly what a typo produces,
# so both value-taking filters die on an unrecognised value. (This is a distinct
# error shape from the `show_help; exit 1` above, which rejects a bad flag NAME.)
if [[ -n "$FOLLOWUP_KIND_FILTER" && "$NO_FOLLOWUP_KIND" == true ]]; then
    die "--followup-kind and --no-followup-kind are mutually exclusive."
fi

if [[ "$PLAN_APPROVED_FILTER" == true && "$NO_PLAN_APPROVED" == true ]]; then
    die "--plan-approved and --no-plan-approved are mutually exclusive."
fi

if [[ -n "$FOLLOWUP_KIND_FILTER" ]]; then
    # Two distinct deaths: "cannot verify" is its own state, not a negative
    # result. --no-followup-kind deliberately needs no lookup, so it keeps
    # working when the Python vocabulary cannot be resolved.
    kinds="$(followup_kinds_pipe)" \
        || die "cannot resolve the follow-up kind vocabulary (lib/followup_kinds.py unreachable) — --followup-kind cannot be validated."
    is_valid_followup_kind "$FOLLOWUP_KIND_FILTER" \
        || die "Invalid follow-up kind: $FOLLOWUP_KIND_FILTER (must be one of: ${kinds//|/, })"
fi

if [[ -n "$TYPE_FILTER" ]]; then
    grep -qFx "$TYPE_FILTER" <(read_valid_task_types "$TASK_TYPES_FILE") \
        || die "Invalid type: $TYPE_FILTER (must be one of: $(read_valid_task_types "$TASK_TYPES_FILE" | tr '\n' ',' | sed 's/,$//'))"
fi

# Check if directory exists
if [ ! -d "$TASK_DIR" ]; then
    echo "Error: Directory '$TASK_DIR' not found."
    exit 1
fi

# --- Core Logic ---

# 1. Map existing task IDs (including child tasks)
existing_ids_file=$(mktemp)

# Add parent-level task IDs
ls "$TASK_DIR" 2>/dev/null | grep -E '^t[0-9]+_.*\.md$' | awk -F'_' '{print substr($1,2)}' > "$existing_ids_file"

# Add child task IDs (format: t1_2)
for child_dir in "$TASK_DIR"/t*/; do
    [ -d "$child_dir" ] || continue
    ls "$child_dir" 2>/dev/null | grep -E '^t[0-9]+_[0-9]+_.*\.md$' | grep -oE '^t[0-9]+_[0-9]+' >> "$existing_ids_file"
done

# Check for duplicate parent task IDs
duplicate_parent_ids=$(sort "$existing_ids_file" | uniq -d)
if [[ -n "$duplicate_parent_ids" ]]; then
    echo -e "\033[1;33mWarning: Duplicate task IDs detected: $duplicate_parent_ids\033[0m" >&2
    echo -e "\033[1;33mRun 'ait setup' to initialize the atomic task ID counter.\033[0m" >&2
fi

# Local dependency verdicts, decided ONCE for the whole tree (t1527).
#
# `ait ls`, the minimonitor picker and the board used to resolve `depends:` with
# three different policies, so they could disagree about the same task. The one
# decision core is `lib/dep_resolution.py`, reached here through
# `aitask_gate.sh deps-blocking-scan`: it resolves each dep against the active
# and loose-archived trees, applies the t635_3 gate-release rule, and returns the
# ids that still BLOCK — already rendered, `(UNRESOLVED)` marker and all. Nothing
# in this script decides any of that any more.
#
# ONE subprocess for the whole run (the t1472 amortization, preserved and
# tightened): the scan does one registry parse and at most one code_digest() for
# the entire tree, and this script no longer forks `grep` twice per dep edge.
#
# Lookup is fork-free and bash-3.2 safe — a substring scan over one variable, not
# an associative array (macOS system bash is 3.2; see sed_macos_issues.md).
dep_scan_keys=()
dep_scan_vals=()
dep_scan_state="unverified"
build_dep_blocking_map() {
    local gate_script="$SCRIPT_DIR/aitask_gate.sh" out rc=0 k v
    [[ -x "$gate_script" ]] || { dep_scan_state="failed"; return 0; }
    out=$(TASK_DIR="$TASK_DIR" "$gate_script" deps-blocking-scan) || rc=$?

    # The SCAN_OK trailer is what separates "nothing is blocked" from "the scan
    # never ran". Empty output alone cannot: treating a dead scan as an empty
    # result would silently list every dependent as Ready — fail-OPEN, and the
    # exact defect class t1527 removes. So the trailer is REQUIRED, and its
    # absence is its own state, never a conservative default.
    #
    # Require it as the EXACT FINAL LINE, not merely present somewhere in the
    # output. A `*"SCAN_OK"*` substring test also accepts `SCAN_OK: diagnostic`
    # from a damaged scanner, or a marker printed mid-stream before the scan
    # died partway — both exit 0, both then contribute no rows for the tasks
    # they never reached, and dependents silently read as Ready. The whole point
    # of a terminal marker is that it can only be written after the last row.
    local last_line="${out##*$'\n'}"
    if [[ "$rc" -ne 0 || "$last_line" != "SCAN_OK" ]]; then
        dep_scan_state="failed"
        warn "dependency scan failed (aitask_gate.sh deps-blocking-scan, exit $rc)"
        warn "  -> dependency state could not be verified; tasks with depends: are shown as Blocked [unverified]"
        return 0
    fi
    dep_scan_state="ok"
    while IFS=$'\t' read -r k v; do
        [[ -n "$k" && "$k" != "SCAN_OK" ]] || continue
        dep_scan_keys+=("$k")
        dep_scan_vals+=("$v")
    done <<< "$out"
}
build_dep_blocking_map

# Blocking ids for one task file, or non-zero when it has none.
#
# Two parallel INDEXED arrays with a linear scan — deliberately not an
# associative array (`declare -A` is bash 4+; macOS system bash is 3.2, see
# sed_macos_issues.md), and deliberately not a substring scan over one variable.
# That last shape looks cheapest and is a trap: bash's `${var#*"$key"}` over a
# 6 KB rows blob measured **15 s** for 451 lookups on this repo, because the glob
# matcher retries from every position. The array scan measures 0.094 s for the
# same work. Cost is O(tasks x BLOCKED tasks) — the arrays hold only the blocked
# ones, which is a small fraction of a real backlog.
lookup_dep_blocking() {
    local i
    for i in "${!dep_scan_keys[@]}"; do
        if [[ "${dep_scan_keys[i]}" == "$1" ]]; then
            printf '%s' "${dep_scan_vals[i]}"
            return 0
        fi
    done
    return 1
}

# 2. Parsing Functions

# Global variables set by parse functions
p_score=2
e_score=2
blocked=0
# Set alongside `blocked` when the dependency scan could not run: the task has
# deps whose state is UNKNOWN, which is neither "blocked by X" nor "ready".
blocked_unverified=0
# Whether the task file carries a `depends:` key AT ALL — independent of whether
# this script's inline-only parser could read a value from it.
depends_key_present=0
# The task file currently being parsed — the key calculate_blocked_status uses
# to look up its pre-decided local-dependency verdict (t1527).
current_task_file=""
p_text="Medium"
# risk is display-only — NOT a sort dimension (no r_score). Empty = unset.
# Two independent dimensions: code-health and goal-achievement.
risk_code_health_text=""
risk_goal_achievement_text=""
e_text="Medium"
d_text="None"
issue_type_text="feature"
# Absent = "not an auto-spawned follow-up" (t1468_1's no-tombstone contract).
followup_kind_text=""
# Absent = "no approved-but-deferred plan" (t1595's no-tombstone contract).
plan_approved_at_text=""
status_text="Ready"
labels_text=""
children_to_implement_text=""
has_children=0
assigned_to_text=""
issue_text=""
pull_request_text=""
contributor_text=""

parse_yaml_frontmatter() {
    local file_path="$1"
    local in_frontmatter=false
    local line_num=0

    while IFS= read -r line; do
        ((line_num++))

        # First line should be ---
        if [[ $line_num -eq 1 ]]; then
            if [[ "$line" == "---" ]]; then
                in_frontmatter=true
                continue
            else
                return
            fi
        fi

        # End of front matter
        if [[ "$line" == "---" ]]; then
            break
        fi

        # Parse YAML key-value pairs
        if [[ "$line" =~ ^([a-z_]+):(.*)$ ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"
            # Trim leading/trailing whitespace
            value=$(echo "$value" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')

            case "$key" in
                priority)
                    case "$value" in
                        high)   p_score=1; p_text="High" ;;
                        medium) p_score=2; p_text="Medium" ;;
                        low)    p_score=3; p_text="Low" ;;
                    esac
                    ;;
                risk_code_health)
                    # Display only — deliberately NOT folded into p_score.
                    case "$value" in
                        high)   risk_code_health_text="High" ;;
                        medium) risk_code_health_text="Medium" ;;
                        low)    risk_code_health_text="Low" ;;
                    esac
                    ;;
                risk_goal_achievement)
                    # Display only — deliberately NOT folded into p_score.
                    case "$value" in
                        high)   risk_goal_achievement_text="High" ;;
                        medium) risk_goal_achievement_text="Medium" ;;
                        low)    risk_goal_achievement_text="Low" ;;
                    esac
                    ;;
                effort)
                    case "$value" in
                        low)    e_score=1; e_text="Low" ;;
                        medium) e_score=2; e_text="Medium" ;;
                        high)   e_score=3; e_text="High" ;;
                    esac
                    ;;
                depends)
                    # Presence is tracked separately from the parsed value: this
                    # parser reads INLINE lists only, so a YAML block list
                    #   depends:
                    #     - 999
                    # leaves d_text empty while the field really does declare a
                    # dependency. The scan (a real YAML parse) is what decides;
                    # this flag only says "do not skip asking it".
                    depends_key_present=1
                    d_text=$(parse_yaml_list "$value")
                    d_text=$(normalize_task_ids "$d_text")
                    ;;
                issue_type)
                    issue_type_text="$value"
                    ;;
                followup_kind)
                    followup_kind_text="$value"
                    ;;
                plan_approved_at)
                    plan_approved_at_text="$value"
                    ;;
                status)
                    status_text="$value"
                    ;;
                labels)
                    labels_text=$(parse_yaml_list "$value")
                    ;;
                children_to_implement)
                    children_to_implement_text=$(parse_yaml_list "$value")
                    children_to_implement_text=$(normalize_task_ids "$children_to_implement_text")
                    ;;
                assigned_to)
                    assigned_to_text="$value"
                    ;;
                issue)
                    issue_text="$value"
                    ;;
                pull_request)
                    pull_request_text="$value"
                    ;;
                contributor)
                    contributor_text="$value"
                    ;;
                xdeprepo)
                    xdeprepo_text="$value"
                    ;;
                xdeps)
                    xdeps_text=$(parse_yaml_list "$value")
                    xdeps_text=$(normalize_task_ids "$xdeps_text")
                    ;;
            esac
        fi
    done < "$file_path"
}

calculate_blocked_status() {
    blocked=0
    blocked_unverified=0
    local blocking_info=""

    # Local dependencies: the scan already decided them (t1527). Only the ids
    # that actually BLOCK are listed — the pre-t1527 form printed every dep of a
    # blocked task, including satisfied ones, which read as "these are holding
    # you up" when they were not. The `(UNRESOLVED)` marker on an id that
    # resolves to no task file is rendered by the core, so this surface and the
    # two TUIs cannot spell the same state three ways.
    if [[ "$dep_scan_state" == "ok" ]]; then
        local scan_hit
        # Only a task that declares a `depends:` KEY can appear in the scan
        # output, so skip the lookup for the ~75% that declare none. Key
        # presence, never the parsed value: gating on d_text skipped every
        # block-list task, because this script's parser reads inline lists only
        # — and the cross-surface parity test caught exactly that.
        if [[ "$depends_key_present" -eq 1 ]] \
                && scan_hit=$(lookup_dep_blocking "$current_task_file"); then
            blocked=1
            blocking_info="$scan_hit"
        fi
    elif [[ "$depends_key_present" -eq 1 ]]; then
        # The scan could not run, so nothing is known about these deps. That is
        # its OWN state, not "nothing is blocked": listing a dependent as Ready
        # here would fail OPEN. Show it as blocked and say the verdict is
        # unverified (the stderr warning names the failing verb).
        blocked=1
        blocked_unverified=1
        # d_text can be empty here even though the key is present (block-list
        # syntax), so name the field rather than printing an empty list.
        if [[ "$d_text" != "None" && -n "$d_text" ]]; then
            blocking_info="$d_text"
        else
            blocking_info="depends:"
        fi
    fi

    # Check cross-repo dependencies (xdeps + xdeprepo)
    if [[ -n "$xdeps_text" && -n "$xdeprepo_text" ]]; then
        IFS=',' read -ra XDEPS <<< "$xdeps_text"
        for xdep_id in "${XDEPS[@]}"; do
            local xdep_status display_id
            display_id="${xdep_id#t}"
            xdep_status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status \
                --project "$xdeprepo_text" "$xdep_id" 2>/dev/null | \
                sed -n 's/^STATUS://p')
            if [[ -z "$xdep_status" || "$xdep_status" == "NOT_FOUND" ]]; then
                blocked=1
                blocking_info="${blocking_info:+$blocking_info,}${xdeprepo_text}#${display_id} (UNREACHABLE)"
                break
            elif [[ "$xdep_status" != "Done" ]]; then
                blocked=1
                blocking_info="${blocking_info:+$blocking_info,}${xdeprepo_text}#${display_id}"
                break
            fi
        done
    fi

    # Track if task has children (for display purposes only, doesn't affect blocking/sorting)
    if [[ -n "$children_to_implement_text" ]]; then
        has_children=1
    fi

    # Update d_text for display
    if [[ "$blocked" -eq 1 && -n "$blocking_info" ]]; then
        d_text="$blocking_info"
    fi
}

parse_task_metadata() {
    local file_path="$1"
    # Squeeze `//`: the child loops glob `"$TASK_DIR"/t*/` (trailing slash) and
    # then append `/t*_*_*.md`, so a child path arrives as `aitasks//t9/t9_1.md`.
    # The scan emits os.path.join'd paths with single separators, and the lookup
    # is an exact substring match — an unsqueezed key silently never matches, and
    # every child would list as Ready.
    current_task_file="${file_path//\/\///}"

    # Reset to defaults
    depends_key_present=0
    p_score=2; p_text="Medium"
    risk_code_health_text=""
    risk_goal_achievement_text=""
    e_score=2; e_text="Medium"
    blocked=0; d_text="None"
    issue_type_text="feature"
    followup_kind_text=""
    plan_approved_at_text=""
    status_text="Ready"
    labels_text=""
    children_to_implement_text=""
    has_children=0
    assigned_to_text=""
    issue_text=""
    pull_request_text=""
    contributor_text=""
    xdeps_text=""
    xdeprepo_text=""

    # Parse YAML front matter
    parse_yaml_frontmatter "$file_path"

    # Calculate blocked status from dependencies
    calculate_blocked_status
}

# 3. Process Files
DELIM=$'\t'

# Helper function to process a single task file
process_task_file() {
    local file_path="$1"
    local indent_prefix="${2:-}"
    local task_type="${3:-parent}"  # parent or child

    [ -e "$file_path" ] || return

    local filename
    filename=$(basename "$file_path")

    # Parse metadata (sets global variables)
    parse_task_metadata "$file_path"

    # Apply status filter
    if [[ "$STATUS_FILTER" != "all" ]]; then
        if [[ "$status_text" != "$STATUS_FILTER" ]]; then
            return
        fi
    fi

    # Apply labels filter
    if [[ -n "$LABELS_FILTER" ]]; then
        local match_found=false
        IFS=',' read -ra FILTER_LABELS <<< "$LABELS_FILTER"
        IFS=',' read -ra TASK_LABELS <<< "$labels_text"
        for filter_label in "${FILTER_LABELS[@]}"; do
            for task_label in "${TASK_LABELS[@]}"; do
                if [[ "$filter_label" == "$task_label" ]]; then
                    match_found=true
                    break 2
                fi
            done
        done
        if [[ "$match_found" == false ]]; then
            return
        fi
    fi

    # Apply issue-type filter. Note a file with no issue_type: at all matches
    # `--type feature`, because the parser defaults to it (documented in --help).
    if [[ -n "$TYPE_FILTER" && "$issue_type_text" != "$TYPE_FILTER" ]]; then
        return
    fi

    # Apply follow-up-kind filters (mutually exclusive; values validated at
    # parse time). An absent kind means "not a follow-up" — never compared
    # against a None/unset sentinel.
    if [[ -n "$FOLLOWUP_KIND_FILTER" && "$followup_kind_text" != "$FOLLOWUP_KIND_FILTER" ]]; then
        return
    fi
    if [[ "$NO_FOLLOWUP_KIND" == true && -n "$followup_kind_text" ]]; then
        return
    fi

    # Apply deferred-approved-plan filters (t1595; mutually exclusive, checked
    # at parse time). These are the NON-VERBOSE affordance for the marker: the
    # plain listing stays filename-only by contract, so narrowing the list is
    # how the state is reached without -v.
    if [[ "$PLAN_APPROVED_FILTER" == true && -z "$plan_approved_at_text" ]]; then
        return
    fi
    if [[ "$NO_PLAN_APPROVED" == true && -n "$plan_approved_at_text" ]]; then
        return
    fi

    # Determine display status string
    local display_status
    if [ "$blocked" -eq 1 ]; then
        display_status="Blocked (by $d_text)"
        # "could not check" is a third state, never folded into either verdict.
        if [[ "$blocked_unverified" -eq 1 ]]; then
            display_status="$display_status [unverified]"
        fi
    elif [ "$has_children" -eq 1 ]; then
        display_status="Has children"
    elif [[ "$status_text" != "Ready" ]]; then
        display_status="$status_text"
    else
        display_status="Ready"
    fi

    # Construct Output
    local display
    if [ "$VERBOSE" = true ]; then
        local assigned_info=""
        if [[ -n "$assigned_to_text" ]]; then
            assigned_info=", Assigned: $assigned_to_text"
        fi
        local issue_info=""
        if [[ -n "$issue_text" ]]; then
            issue_info=", Issue: $issue_text"
        fi
        local pr_info=""
        if [[ -n "$pull_request_text" ]]; then
            pr_info=", PR: $pull_request_text"
        fi
        local contributor_info=""
        if [[ -n "$contributor_text" ]]; then
            contributor_info=", Contributor: $contributor_text"
        fi
        local risk_info=""
        if [[ -n "$risk_code_health_text" ]]; then
            risk_info="${risk_info}, CH-risk: $risk_code_health_text"
        fi
        if [[ -n "$risk_goal_achievement_text" ]]; then
            risk_info="${risk_info}, GA-risk: $risk_goal_achievement_text"
        fi
        # Type is always shown (the parser defaults it, so there is no "absent"
        # state); Follow-up appears only when the field is present. The raw
        # canonical token is printed, not a human label, so it can be pasted
        # straight into --followup-kind. Display only — NOT a sort dimension.
        local type_info=""
        if [[ -n "$issue_type_text" ]]; then
            type_info=", Type: $issue_type_text"
        fi
        local followup_info=""
        if [[ -n "$followup_kind_text" ]]; then
            followup_info=", Follow-up: $followup_kind_text"
        fi
        # An approved plan whose implementation was deliberately deferred
        # (t1595). Verbose-only by contract: no metadata has ever appeared in
        # the plain listing, which every script consumer parses as a bare
        # filename list -- --plan-approved is the non-verbose affordance.
        local plan_info=""
        if [[ -n "$plan_approved_at_text" ]]; then
            plan_info=", Plan: approved $plan_approved_at_text"
        fi
        display="${indent_prefix}$filename [Status: $display_status, Priority: $p_text${risk_info}, Effort: $e_text${type_info}${followup_info}${plan_info}${assigned_info}${issue_info}${pr_info}${contributor_info}]"
    else
        display="${indent_prefix}$filename"
    fi

    echo "$blocked $p_score $e_score $DELIM$display"
}

# Collect output in a temp file
output_file=$(mktemp)

# Mode 1: List children of a specific parent
if [[ -n "$CHILDREN_OF" ]]; then
    child_dir="$TASK_DIR/t${CHILDREN_OF}"
    if [[ -d "$child_dir" ]]; then
        for file_path in "$child_dir"/t${CHILDREN_OF}_*_*.md; do
            process_task_file "$file_path" "" "child"
        done >> "$output_file"
    fi

# Mode 2: Tree view (parents with indented children)
elif [[ "$TREE_VIEW" = true ]]; then
    for file_path in "$TASK_DIR"/t*_*.md; do
        [ -e "$file_path" ] || continue

        # Get parent task number
        task_num=$(basename "$file_path" | grep -oE '^t[0-9]+' | sed 's/t//')

        # Process parent
        process_task_file "$file_path" "" "parent" >> "$output_file"

        # Process children if they exist
        child_dir="$TASK_DIR/t${task_num}"
        if [[ -d "$child_dir" ]]; then
            for child_path in "$child_dir"/t${task_num}_*_*.md; do
                [ -e "$child_path" ] || continue
                process_task_file "$child_path" "  └─ " "child" >> "$output_file"
            done
        fi
    done

# Mode 3: All levels (flat list of parents and children)
elif [[ "$ALL_LEVELS" = true ]]; then
    # Parents first
    for file_path in "$TASK_DIR"/t*_*.md; do
        process_task_file "$file_path" "" "parent"
    done >> "$output_file"

    # Then children
    for child_dir in "$TASK_DIR"/t*/; do
        [ -d "$child_dir" ] || continue
        for file_path in "$child_dir"/t*_*_*.md; do
            process_task_file "$file_path" "" "child"
        done
    done >> "$output_file"

# Mode 4: Normal (parents only, default)
else
    for file_path in "$TASK_DIR"/t*_*.md; do
        process_task_file "$file_path" "" "parent"
    done >> "$output_file"
fi

# Sort and limit output (skip sorting for tree view to preserve hierarchy)
if [[ "$TREE_VIEW" = true ]]; then
    cat "$output_file" | awk -F"$DELIM" '{print $2}' | {
        if [ "$LIMIT" -gt 0 ]; then
            head -n "$LIMIT"
        else
            cat
        fi
    }
else
    cat "$output_file" | sort -k1,1n -k2,2n -k3,3n | awk -F"$DELIM" '{print $2}' | {
        if [ "$LIMIT" -gt 0 ]; then
            head -n "$LIMIT"
        else
            cat
        fi
    }
fi

rm -f "$existing_ids_file" "$output_file"
