#!/usr/bin/env bash
# aitask_plan_externalize.sh - Externalize a Claude Code internal plan file
# to the project's aiplans/ directory.
#
# Claude Code's EnterPlanMode writes the approved plan to an internal file
# at ~/.claude/plans/<random>.md. This script copies it to the canonical
# external path (aiplans/p<N>_<stem>.md for parent tasks, or
# aiplans/p<parent>/p<parent>_<child>_<stem>.md for child tasks) and
# prepends the required metadata header when missing.
#
# Usage:
#   aitask_plan_externalize.sh <task_id> [--internal <path>] [--force]
#                             [--profile <path>] [--base-branch <branch>]
#                             [--base-branch-file <path>]
#                             [--output-branch <branch>]
#                             [--output-branch-default <branch>]
#                             [--output-branch-default-file <path>] [--no-worktree]
#
# Arguments:
#   <task_id>            Task number (e.g. 16, t16) or child id (e.g. 16_2)
#   --internal <path>    Explicit internal plan file path (skips scan)
#   --force              Overwrite an existing external plan file
#                        (default: no-op, emits PLAN_EXISTS)
#   --profile <path>     Execution-profile YAML. Its `output_branch`,
#                        `base_branch` and `create_worktree` are read with a real
#                        YAML parser. Passing a PATH (not a branch value) keeps a
#                        user-authored branch name out of the caller's command
#                        line. Fails closed if missing/malformed/non-mapping.
#   --base-branch <b>    The Step-5 RESOLVED base branch. Recorded as
#                        `Base branch:` and used as the last-resort merge target
#                        ("output defaults to base"). Wins over the profile.
#   --base-branch-file <path>
#                        Same as --base-branch, but reads the value from a FILE so
#                        an interactively chosen branch name never has to be
#                        substituted into a command line ("release$(id -u)" would
#                        expand there). Preferred for any value that did not come
#                        from a profile. If both forms are given the FILE wins,
#                        whatever the argument order.
#   --output-branch <b>  Explicit merge target; wins over the profile.
#   --output-branch-default-file <path>
#                        Same as --output-branch-default, but via the file channel.
#   --output-branch-default <b>
#                        LEGACY, base-neutral merge-target default: used when the
#                        profile sets no `output_branch`, and deliberately does
#                        NOT change the recorded `Base branch:`. Superseded by
#                        --base-branch[-file], which the workflow passes instead;
#                        kept for callers that want a merge-target default without
#                        making any claim about the base branch.
#   --no-worktree        Step 5 created no worktree, so neither `base_branch` nor
#                        `output_branch` applies; both fall back to the detected
#                        primary branch.
#
# Resolution precedence (t1233 for output, t1277 for base):
#
#   Base branch:    --base-branch[-file] > profile base_branch > detected primary
#   Output branch:  --output-branch > profile output_branch
#                 > --output-branch-default[-file]
#                 > the resolved base (--base-branch[-file] / profile base_branch)
#                 > detected primary
#
# Outside worktree mode (--no-worktree / `create_worktree: false`) every derived
# value on BOTH chains is discarded and the detected primary is recorded.
#
# Both header fields are consumed by task-workflow -- `Output branch:` by Step 9's
# merge, `Base branch:` by Re-entry Routing (which resolves the branch context
# from the plan header alone) -- and both are applied on both header paths: built
# into a fresh header, and spliced into a source plan that already carries
# frontmatter.
#
# The splice is intent-gated per field: an invocation that supplies no base
# (--output-branch, --output-branch-default[-file], or a --profile whose YAML has
# no `base_branch`) leaves an existing `Base branch:` line alone rather than
# inventing the primary branch for it. See BASE_INTENT below.
#
# Environment:
#   AIT_PLAN_EXTERNALIZE_INTERNAL_DIR   Override internal plans dir
#                                        (default: ~/.claude/plans)
#   AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS   Max age for auto-discovered files
#                                        (default: 3600)
#
# Output lines (exit 0):
#   PLAN_EXISTS:<external_path>
#   EXTERNALIZED:<external_path>:<source>
#   OVERWRITTEN:<external_path>:<source>
#   MULTIPLE_CANDIDATES:<path1>|<path2>|...
#   NOT_FOUND:<reason>
#
# Reasons for NOT_FOUND:
#   no_internal_dir      ~/.claude/plans/ does not exist
#   no_internal_files    Directory empty or no files within age window
#   source_not_file      --internal path missing or not a regular file
#   no_task_file         Cannot resolve <task_id> to a task filename
#
# Encapsulation: SKILL.md should never mention ~/.claude/plans, mtime
# filtering, or internal plan file details. Those concerns live here.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/git_utils.sh
source "$SCRIPT_DIR/lib/git_utils.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

# shellcheck source=lib/atomic_write.sh
source "$SCRIPT_DIR/lib/atomic_write.sh"
TASK_DIR="${TASK_DIR:-aitasks}"
PLAN_DIR="${PLAN_DIR:-aiplans}"
ARCHIVED_PLAN_DIR="${ARCHIVED_PLAN_DIR:-aiplans/archived}"

INTERNAL_PLANS_DIR="${AIT_PLAN_EXTERNALIZE_INTERNAL_DIR:-$HOME/.claude/plans}"
MAX_AGE_SECS="${AIT_PLAN_EXTERNALIZE_MAX_AGE_SECS:-3600}"

usage() {
    cat <<'EOF'
Usage: aitask_plan_externalize.sh <task_id> [--internal <path>] [--force]
                                  [--profile <path>] [--base-branch <branch>]
                                  [--base-branch-file <path>]
                                  [--output-branch <branch>]
                                  [--output-branch-default <branch>]
                                  [--output-branch-default-file <path>] [--no-worktree]

Externalize a Claude Code internal plan file to aiplans/.

Arguments:
  <task_id>            Task number (e.g. 16, t16) or child id (e.g. 16_2)
  --internal <path>    Explicit internal plan file path (skips auto-scan)
  --force              Overwrite an existing external plan file
                       (default: no-op, emits PLAN_EXISTS)
  --profile <path>     Execution-profile YAML; output_branch / base_branch /
                       create_worktree are read from it with a real YAML parser.
                       Fails closed if missing, malformed or not a mapping.
  --base-branch <b>    The Step-5 resolved base branch: recorded as
                       `Base branch:` and used as the last-resort merge target.
  --base-branch-file <path>
                       Read the base branch from a file (safe channel for
                       interactively chosen values). Wins over --base-branch.
  --output-branch <b>  Explicit merge target; wins over the profile.
  --output-branch-default-file <path>
                       Read the legacy fallback branch from a file.
  --output-branch-default <b>
                       LEGACY base-neutral merge-target default, used when the
                       profile sets no output_branch. Does not change the
                       recorded `Base branch:` field; superseded by
                       --base-branch[-file].
  --no-worktree        No worktree was created, so base_branch and output_branch
                       are both ignored.

Precedence:
  Base branch:   --base-branch[-file] > profile base_branch > detected primary
  Output branch: --output-branch > profile output_branch
               > --output-branch-default[-file]
               > resolved base > detected primary

Output (exit 0):
  PLAN_EXISTS:<path>                  Already externalized (no-op)
  EXTERNALIZED:<path>:<source>        Copied successfully
  OVERWRITTEN:<path>:<source>         Existing file replaced (--force)
  MULTIPLE_CANDIDATES:<p1>|<p2>|...   Ambiguous; caller disambiguates
  NOT_FOUND:<reason>                  Could not externalize
EOF
}

# --- Arg parsing ---

TASK_ID=""
INTERNAL_OVERRIDE=""
FORCE=false
BASE_BRANCH_OVERRIDE=""
BASE_BRANCH_FILE=""
OUTPUT_BRANCH_OVERRIDE=""
OUTPUT_BRANCH_DEFAULT=""
OUTPUT_BRANCH_DEFAULT_FILE=""
PROFILE_FILE=""
WORKTREE_MODE=true
OUTPUT_INTENT=false
# Derived after the profile is parsed -- see the BASE_INTENT block below.
BASE_INTENT=false

# Validate a branch name against a shell-safe subset. Git itself accepts refs
# like 'dev$(id)', 'dev`id`' and "dev'x"; this value is persisted into the plan
# header and later consumed by an agent, so anything outside the safe subset is
# rejected here rather than being quoted downstream (quoting does not help --
# "dev$(id)" still executes inside double quotes).
validate_branch_name() {
    local b="$1" src="$2"
    [[ "$b" =~ ^[A-Za-z0-9._/-]+$ ]] \
        || die "$src: unsafe branch name '$b' (allowed: A-Z a-z 0-9 . _ / -)"
    git check-ref-format --branch "$b" >/dev/null 2>&1 \
        || die "$src: not a valid git branch name: '$b'"
}

# Read a single branch name out of a value FILE. Shared by --base-branch-file and
# --output-branch-default-file so the one-line / empty / unsafe rejections live in
# one place.
#
# Returns the value in the global BRANCH_VALUE_FILE_RESULT rather than on stdout:
# `die` inside a $( ) would only kill the command-substitution subshell, so a
# printing helper would report its error and then let the caller carry on with an
# empty value. Each call site MUST copy the result into its own variable before
# the next call runs -- both flags may be supplied in one invocation.
BRANCH_VALUE_FILE_RESULT=""
read_branch_value_file() {
    local path="$1" flag="$2"
    local _lines=()
    [[ -f "$path" ]] || die "$flag: no such file: '$path'"
    # Read the COMPLETE logical value: head -n1 would silently turn an invalid
    # multi-line file into a different branch name instead of rejecting it.
    mapfile -t _lines < "$path"
    [[ ${#_lines[@]} -eq 1 ]] \
        || die "$flag: '$path' must contain exactly one branch name (found ${#_lines[@]} line(s))"
    [[ -n "${_lines[0]}" ]] || die "$flag: '$path' is empty"
    validate_branch_name "${_lines[0]}" "$flag"
    BRANCH_VALUE_FILE_RESULT="${_lines[0]}"
}

# Read the branch-relevant fields out of a profile YAML with a real parser, as
# three `key=value` lines. A naive `sed` on the right-hand side would return raw
# scalar text, so the equally valid `output_branch: "dev"`, `'dev'` and
# `dev # comment` forms would all carry YAML syntax into the value.
# FAILS CLOSED: a missing, unreadable, malformed or non-mapping profile is an
# error, never a silent fallback to the primary branch -- silently discarding a
# configured merge target is exactly the failure this field exists to prevent.
read_profile_branch_fields() {
    local profile="$1" py
    py="$(require_ait_python)" || die "--profile: no usable Python to parse '$profile'"
    "$py" -c '
import sys, yaml
path = sys.argv[1]
try:
    with open(path) as fh:
        data = yaml.safe_load(fh)
except FileNotFoundError:
    sys.stderr.write("not found\n"); sys.exit(3)
except Exception as exc:
    sys.stderr.write("unparseable: %s\n" % exc); sys.exit(4)
if data is None:
    data = {}
if not isinstance(data, dict):
    sys.stderr.write("not a YAML mapping\n"); sys.exit(5)
import re
SAFE = re.compile(r"^[A-Za-z0-9._/-]+$")
for key in ("output_branch", "base_branch"):
    v = data.get(key)
    if v is None:
        continue
    if isinstance(v, bool) or not isinstance(v, (str, int, float)):
        sys.stderr.write("%s: expected a branch name, got %s\n" % (key, type(v).__name__))
        sys.exit(6)
    v = str(v).strip()
    # Validate BEFORE serialising. This protocol is newline-delimited
    # key=value records, so a scalar containing a newline (valid YAML via
    # "dev\nbase_branch=release") would otherwise inject a second record and
    # be accepted -- the record split happens before any downstream charset
    # check could see it.
    if not SAFE.match(v):
        sys.stderr.write("%s: unsafe branch name %r (allowed: A-Z a-z 0-9 . _ / -)\n" % (key, v))
        sys.exit(7)
    print("%s=%s" % (key, v))
cw = data.get("create_worktree")
if cw is not None:
    print("create_worktree=%s" % ("true" if cw else "false"))
' "$profile"
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --internal)
            [[ $# -ge 2 ]] || die "--internal requires a path argument"
            INTERNAL_OVERRIDE="$2"
            shift 2
            ;;
        --force)
            FORCE=true
            shift
            ;;
        --profile)
            [[ $# -ge 2 ]] || die "--profile requires a path argument"
            PROFILE_FILE="$2"
            OUTPUT_INTENT=true
            shift 2
            ;;
        --base-branch)
            # The Step-5 RESOLVED base branch. Unlike --output-branch-default this
            # DOES change the recorded `Base branch:` -- it is the same value, and
            # recording the detected primary instead is the t1277 bug.
            [[ $# -ge 2 ]] || die "--base-branch requires a branch argument"
            validate_branch_name "$2" "--base-branch"
            BASE_BRANCH_OVERRIDE="$2"
            OUTPUT_INTENT=true
            shift 2
            ;;
        --base-branch-file)
            # Path only; the read is deferred past the already-externalized
            # short-circuit, exactly as for --output-branch-default-file, so a
            # no-op Step 8 call whose scratch file is gone still emits PLAN_EXISTS.
            [[ $# -ge 2 ]] || die "--base-branch-file requires a path argument"
            BASE_BRANCH_FILE="$2"
            OUTPUT_INTENT=true
            shift 2
            ;;
        --output-branch-default)
            # The Step-5 RESOLVED base branch, used as the merge target when the
            # profile sets no output_branch (the documented "defaults to
            # base_branch" contract). Deliberately does NOT change the recorded
            # `Base branch:` field -- that remains the detected primary branch.
            [[ $# -ge 2 ]] || die "--output-branch-default requires a branch argument"
            validate_branch_name "$2" "--output-branch-default"
            OUTPUT_BRANCH_DEFAULT="$2"
            OUTPUT_INTENT=true
            shift 2
            ;;
        --output-branch-default-file)
            # Reads the value from a FILE so an interactively supplied branch
            # name never has to be substituted into a command line, where
            # "release$(id -u)" would expand before this script could validate
            # anything. Write the file with a non-shell tool.
            [[ $# -ge 2 ]] || die "--output-branch-default-file requires a path argument"
            # Record the path only. Reading and validating it is deferred until
            # after the already-externalized short-circuit, so a no-op Step 8
            # call still returns PLAN_EXISTS when the scratch file is gone.
            OUTPUT_BRANCH_DEFAULT_FILE="$2"
            OUTPUT_INTENT=true
            shift 2
            ;;
        --no-worktree)
            # Step 5 did not create a worktree, so there is no merge at Step 9 and
            # the profile's output_branch does not apply (it is documented as
            # ignored outside worktree mode).
            WORKTREE_MODE=false
            OUTPUT_INTENT=true
            shift
            ;;
        --output-branch)
            [[ $# -ge 2 ]] || die "--output-branch requires a branch argument"
            validate_branch_name "$2" "--output-branch"
            OUTPUT_BRANCH_OVERRIDE="$2"
            OUTPUT_INTENT=true
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        -*)
            die "Unknown flag: $1"
            ;;
        *)
            [[ -n "$TASK_ID" ]] && die "Unexpected extra argument: $1"
            TASK_ID="$1"
            shift
            ;;
    esac
done

[[ -n "$TASK_ID" ]] || { usage >&2; die "Missing <task_id> argument"; }

TASK_ID="${TASK_ID#t}"
TASK_ID="${TASK_ID#p}"

# --- Resolve task file + compute external plan path ---

PARENT_NUM=""
CHILD_NUM=""
IS_CHILD=false

if [[ "$TASK_ID" =~ ^([0-9]+)_([0-9]+)$ ]]; then
    PARENT_NUM="${BASH_REMATCH[1]}"
    CHILD_NUM="${BASH_REMATCH[2]}"
    IS_CHILD=true
elif [[ "$TASK_ID" =~ ^[0-9]+$ ]]; then
    PARENT_NUM="$TASK_ID"
else
    die "Invalid task id: '$TASK_ID' (expected N or N_M)"
fi

TASK_FILE=""
if [[ "$IS_CHILD" == true ]]; then
    for f in "$TASK_DIR"/t"${PARENT_NUM}"/t"${PARENT_NUM}"_"${CHILD_NUM}"_*.md; do
        [[ -e "$f" ]] || continue
        TASK_FILE="$f"
        break
    done
else
    for f in "$TASK_DIR"/t"${PARENT_NUM}"_*.md; do
        [[ -e "$f" ]] || continue
        TASK_FILE="$f"
        break
    done
fi

if [[ -z "$TASK_FILE" ]]; then
    echo "NOT_FOUND:no_task_file"
    exit 0
fi

TASK_BASENAME=$(basename "$TASK_FILE")
PLAN_BASENAME="p${TASK_BASENAME#t}"

if [[ "$IS_CHILD" == true ]]; then
    EXTERNAL_PLAN="$PLAN_DIR/p${PARENT_NUM}/${PLAN_BASENAME}"
else
    EXTERNAL_PLAN="$PLAN_DIR/${PLAN_BASENAME}"
fi

# --- No-op if already externalized (unless --force) ---

EXISTED_BEFORE=false
if [[ -f "$EXTERNAL_PLAN" ]]; then
    if [[ "$FORCE" != true ]]; then
        echo "PLAN_EXISTS:$EXTERNAL_PLAN"
        exit 0
    fi
    EXISTED_BEFORE=true
fi

# Resolution inputs are read here -- AFTER the short-circuit above -- so a
# no-op call whose scratch value file has already been cleaned up still returns
# PLAN_EXISTS instead of failing on an input it would never have used.
# Each read copies the shared result IMMEDIATELY -- batching the reads and
# deferring the copies would let one file supply both branches.
if [[ -n "$BASE_BRANCH_FILE" ]]; then
    read_branch_value_file "$BASE_BRANCH_FILE" "--base-branch-file"
    BASE_BRANCH_OVERRIDE="$BRANCH_VALUE_FILE_RESULT"
fi
if [[ -n "$OUTPUT_BRANCH_DEFAULT_FILE" ]]; then
    read_branch_value_file "$OUTPUT_BRANCH_DEFAULT_FILE" "--output-branch-default-file"
    OUTPUT_BRANCH_DEFAULT="$BRANCH_VALUE_FILE_RESULT"
fi

# Resolve the base branch and the merge target. Precedence:
#
#   Base branch:
#     1. --base-branch[-file]     the Step-5 resolved base (file wins over flag)
#     2. profile base_branch      only in worktree mode
#     3. detected primary branch
#
#   Output branch:
#     1. --output-branch          explicit override
#     2. profile output_branch    only in worktree mode (ignored otherwise)
#     3. --output-branch-default[-file]   legacy, base-neutral default
#     4. the resolved base        the documented "output defaults to base"
#     5. detected primary branch  (the pre-existing default)
#
# The caller passes a profile PATH rather than a branch value, so a
# user-authored name never reaches its command line.
if [[ -n "$PROFILE_FILE" ]]; then
    _fields="$(read_profile_branch_fields "$PROFILE_FILE")" \
        || die "--profile: cannot read branch settings from '$PROFILE_FILE'"
    _p_output=""; _p_base=""
    while IFS='=' read -r _k _v; do
        case "$_k" in
            output_branch)   _p_output="$_v" ;;
            base_branch)     _p_base="$_v" ;;
            create_worktree) [[ "$_v" == "false" ]] && WORKTREE_MODE=false ;;
        esac
    done <<< "$_fields"

    if [[ -z "$OUTPUT_BRANCH_OVERRIDE" && "$WORKTREE_MODE" == true && -n "$_p_output" ]]; then
        validate_branch_name "$_p_output" "profile output_branch"
        OUTPUT_BRANCH_OVERRIDE="$_p_output"
    fi
    # The profile's base_branch feeds the BASE chain; the output chain then picks
    # it up at its own rung 4 below, which is why there is no separate
    # `_p_base -> OUTPUT_BRANCH_DEFAULT` assignment here any more (t1277).
    if [[ -z "$BASE_BRANCH_OVERRIDE" && "$WORKTREE_MODE" == true && -n "$_p_base" ]]; then
        validate_branch_name "$_p_base" "profile base_branch"
        BASE_BRANCH_OVERRIDE="$_p_base"
    fi
fi
# Outside worktree mode nothing is cut and nothing is merged, so no derived value
# on either chain applies.
[[ "$WORKTREE_MODE" == true ]] \
    || { OUTPUT_BRANCH_OVERRIDE=""; OUTPUT_BRANCH_DEFAULT=""; BASE_BRANCH_OVERRIDE=""; }
[[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$OUTPUT_BRANCH_DEFAULT"
[[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$BASE_BRANCH_OVERRIDE"

PRIMARY_BRANCH="$(detect_primary_branch)"
BASE_BRANCH_RESOLVED="${BASE_BRANCH_OVERRIDE:-$PRIMARY_BRANCH}"

# BASE_INTENT gates the `Base branch:` splice into a plan that ALREADY carries
# frontmatter. It is DERIVED, not flag-enumerated: true iff a base was actually
# supplied (--base-branch[-file] or a profile that really sets base_branch), or the
# caller positively asserted there is no fork (--no-worktree / create_worktree:
# false, where the primary is the right answer and a stale value must go).
#
# The asymmetry with OUTPUT_INTENT is deliberate. A profile with no output_branch
# still DETERMINES the merge target (it falls back to base/primary), so --profile
# alone is a complete claim about that field. A profile with no base_branch
# determines nothing -- Step 5 asked the user, and the answer arrives separately
# via --base-branch-file. So --profile alone, --output-branch and
# --output-branch-default[-file] must leave an existing `Base branch:` line alone:
# overwriting it with the primary would invent a value for the very field
# Re-entry Routing reads to decide where the work is cut from.
if [[ -n "$BASE_BRANCH_OVERRIDE" || "$WORKTREE_MODE" != true ]]; then
    BASE_INTENT=true
fi

# --- Locate source internal plan ---

SOURCE=""

if [[ -n "$INTERNAL_OVERRIDE" ]]; then
    if [[ ! -f "$INTERNAL_OVERRIDE" ]]; then
        echo "NOT_FOUND:source_not_file"
        exit 0
    fi
    SOURCE="$INTERNAL_OVERRIDE"
else
    if [[ ! -d "$INTERNAL_PLANS_DIR" ]]; then
        echo "NOT_FOUND:no_internal_dir"
        exit 0
    fi

    get_mtime() {
        local f="$1"
        local m
        if m=$(stat -c %Y "$f" 2>/dev/null); then
            echo "$m"
        elif m=$(stat -f %m "$f" 2>/dev/null); then
            echo "$m"
        else
            echo ""
        fi
    }

    now=$(date +%s)
    cutoff=$(( now - MAX_AGE_SECS ))

    candidates=()
    shopt -s nullglob
    for f in "$INTERNAL_PLANS_DIR"/*.md; do
        [[ -f "$f" ]] || continue
        mt=$(get_mtime "$f")
        [[ -n "$mt" ]] || continue
        if (( mt >= cutoff )); then
            candidates+=("${mt}|${f}")
        fi
    done
    shopt -u nullglob

    if [[ ${#candidates[@]} -eq 0 ]]; then
        echo "NOT_FOUND:no_internal_files"
        exit 0
    fi

    if [[ ${#candidates[@]} -gt 1 ]]; then
        sorted=$(printf '%s\n' "${candidates[@]}" | sort -t'|' -k1,1nr)
        paths=()
        while IFS='|' read -r _ p; do
            paths+=("$p")
        done <<< "$sorted"
        joined=""
        for p in "${paths[@]}"; do
            if [[ -n "$joined" ]]; then
                joined="${joined}|${p}"
            else
                joined="$p"
            fi
        done
        echo "MULTIPLE_CANDIDATES:$joined"
        exit 0
    fi

    SOURCE="${candidates[0]#*|}"
fi

# --- Build external plan file with metadata header if missing ---

mkdir -p "$(dirname "$EXTERNAL_PLAN")"

has_frontmatter=false
first_line=$(head -n 1 "$SOURCE" 2>/dev/null || true)
if [[ "$first_line" == "---" ]]; then
    has_frontmatter=true
fi

build_header() {
    local current_branch=""
    current_branch=$(git symbolic-ref --short HEAD 2>/dev/null || echo "")

    echo "---"
    echo "Task: $TASK_BASENAME"

    if [[ "$IS_CHILD" == true ]]; then
        local parent_file=""
        for f in "$TASK_DIR"/t"${PARENT_NUM}"_*.md; do
            [[ -e "$f" ]] || continue
            parent_file="$f"
            break
        done
        [[ -n "$parent_file" ]] && echo "Parent Task: $parent_file"

        local siblings=()
        for f in "$TASK_DIR"/t"${PARENT_NUM}"/t"${PARENT_NUM}"_*_*.md; do
            [[ -e "$f" ]] || continue
            [[ "$f" == "$TASK_FILE" ]] && continue
            siblings+=("$f")
        done
        if [[ ${#siblings[@]} -gt 0 ]]; then
            local joined=""
            for s in "${siblings[@]}"; do
                if [[ -n "$joined" ]]; then
                    joined="${joined}, ${s}"
                else
                    joined="$s"
                fi
            done
            echo "Sibling Tasks: $joined"
        fi

        local archived_plans=()
        for f in "$ARCHIVED_PLAN_DIR"/p"${PARENT_NUM}"/p"${PARENT_NUM}"_*_*.md; do
            [[ -e "$f" ]] || continue
            archived_plans+=("$f")
        done
        if [[ ${#archived_plans[@]} -gt 0 ]]; then
            local joined=""
            for s in "${archived_plans[@]}"; do
                if [[ -n "$joined" ]]; then
                    joined="${joined}, ${s}"
                else
                    joined="$s"
                fi
            done
            echo "Archived Sibling Plans: $joined"
        fi
    fi

    local task_name="${TASK_BASENAME%.md}"
    [[ -d "aiwork/${task_name}" ]] && echo "Worktree: aiwork/${task_name}"

    if [[ -n "$current_branch" && "$current_branch" != "$PRIMARY_BRANCH" ]]; then
        echo "Branch: $current_branch"
    fi

    echo "Base branch: $BASE_BRANCH_RESOLVED"
    echo "Output branch: ${OUTPUT_BRANCH_OVERRIDE:-$PRIMARY_BRANCH}"
    echo "plan_verified: []"
    echo "---"
    echo ""
}

# Record `Base branch:` / `Output branch:` inside a plan file that ALREADY carries
# frontmatter. build_header() is skipped for such sources, so without this the
# flags would be accepted and silently dropped -- Step 9 would merge somewhere
# else, and Re-entry Routing would resolve the wrong fork point.
#
# Each field is independently opt-in: an EMPTY argument means "the caller made no
# claim about this field", and the existing line (if any) is left untouched. That
# is what keeps --output-branch / --output-branch-default[-file] base-neutral.
#
# Replaces an existing field, else inserts before the closing `---` in
# build_header order (Base, then Output), keeping the `---` count at 2. No-op when
# the file does not open with `---` or when neither field was claimed.
splice_header_branches() {
    local file="$1" base="$2" out="$3"
    [[ -n "$base" || -n "$out" ]] || return 0
    [[ "$(head -n 1 "$file" 2>/dev/null || true)" == "---" ]] || return 0
    # Renderer contract (lib/atomic_write.sh): a single `awk`, so the renderer's
    # exit status IS awk's — no extra guard needed. Both fields go through ONE
    # render, so the file is never left half-updated. Routing it through
    # ait_atomic_render also fixes the old `awk … > "$tmp" && mv …` form, which
    # left the temp behind whenever awk failed.
    _ait_splice_header_branches_body() {
        awk -v base="$base" -v out="$out" '
            NR == 1                 { print; next }
            done_fm                 { print; next }
            /^Base branch:/         { if (base != "") { print "Base branch: " base; seen_base = 1; next } }
            /^Output branch:/       { if (out  != "") { print "Output branch: " out; seen_out  = 1; next } }
            $0 == "---" {
                if (base != "" && !seen_base) print "Base branch: " base
                if (out  != "" && !seen_out)  print "Output branch: " out
                done_fm = 1; print; next
            }
                                    { print }
        ' "$file"
    }
    ait_atomic_render "$file" _ait_splice_header_branches_body \
        || die "could not splice branch fields into: $file"
}

# Renderer contract (lib/atomic_write.sh): `cat` and `build_header` can both
# fail on their own, so each carries an explicit `|| return 1` — the calling
# context has errexit disabled, and without the guards a failed build_header
# followed by a successful `cat` would commit a plan with no metadata header.
_ait_externalize_body() {
    if [[ "$has_frontmatter" == true ]]; then
        cat "$SOURCE" || return 1
    else
        build_header || return 1
        cat "$SOURCE" || return 1
    fi
}
# ait_atomic_tmp mkdir -p's the destination directory, which matters here: this
# is also the path that CREATES aiplans/p<N>_*.md on a first externalize.
ait_atomic_render "$EXTERNAL_PLAN" _ait_externalize_body \
    || die "could not write external plan: $EXTERNAL_PLAN"

# Sources that already had frontmatter bypassed build_header(), so the branch
# fields have to be spliced into their existing block. Only for the fields the
# caller actually claimed — never silently rewrite the other one.
# Splice whenever the caller expressed intent about a field, not only when a value
# was resolved: otherwise a plan whose frontmatter already carries a stale
# `Output branch:` keeps it, and Step 9 merges to the old target.
if [[ "$has_frontmatter" == true ]]; then
    _splice_base=""
    _splice_out=""
    if [[ "$BASE_INTENT" == true ]]; then
        _splice_base="$BASE_BRANCH_RESOLVED"
    fi
    if [[ "$OUTPUT_INTENT" == true ]]; then
        _splice_out="${OUTPUT_BRANCH_OVERRIDE:-$PRIMARY_BRANCH}"
    fi
    splice_header_branches "$EXTERNAL_PLAN" "$_splice_base" "$_splice_out"
fi

if [[ "$EXISTED_BEFORE" == true ]]; then
    echo "OVERWRITTEN:${EXTERNAL_PLAN}:${SOURCE}"
else
    echo "EXTERNALIZED:${EXTERNAL_PLAN}:${SOURCE}"
fi
