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
#                             [--profile <path>] [--output-branch <branch>]
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
#   --output-branch <b>  Explicit merge target; wins over the profile.
#   --output-branch-default-file <path>
#                        Same as --output-branch-default, but reads the value
#                        from a FILE so an interactively supplied branch name
#                        never has to be substituted into a command line
#                        ("release$(id -u)" would expand there). Preferred for
#                        any value that did not come from a profile.
#   --output-branch-default <b>
#                        Merge target used when the profile sets no
#                        `output_branch` -- i.e. the Step-5 resolved base branch,
#                        which is the documented "defaults to base_branch"
#                        behaviour. Does NOT change the recorded `Base branch:`.
#   --no-worktree        Step 5 created no worktree, so `output_branch` does not
#                        apply and is ignored.
#
# The `Output branch:` header field is consumed by task-workflow Step 9 and is
# applied on both header paths: built into a fresh header, and spliced into a
# source plan that already carries frontmatter.
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
                                  [--profile <path>] [--output-branch <branch>]
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
  --output-branch <b>  Explicit merge target; wins over the profile.
  --output-branch-default-file <path>
                       Read the fallback branch from a file (safe channel for
                       interactively supplied values).
  --output-branch-default <b>
                       Merge target when the profile sets no output_branch
                       (the Step-5 resolved base branch). Does not change the
                       recorded `Base branch:` field.
  --no-worktree        No worktree was created, so output_branch is ignored.

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
OUTPUT_BRANCH_OVERRIDE=""
OUTPUT_BRANCH_DEFAULT=""
OUTPUT_BRANCH_DEFAULT_FILE=""
PROFILE_FILE=""
WORKTREE_MODE=true
OUTPUT_INTENT=false

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
if [[ -n "$OUTPUT_BRANCH_DEFAULT_FILE" ]]; then
    [[ -f "$OUTPUT_BRANCH_DEFAULT_FILE" ]] \
        || die "--output-branch-default-file: no such file: '$OUTPUT_BRANCH_DEFAULT_FILE'"
    # Read the COMPLETE logical value: head -n1 would silently turn an invalid
    # multi-line file into a different branch name instead of rejecting it.
    _obd_lines=()
    mapfile -t _obd_lines < "$OUTPUT_BRANCH_DEFAULT_FILE"
    [[ ${#_obd_lines[@]} -eq 1 ]] \
        || die "--output-branch-default-file: '$OUTPUT_BRANCH_DEFAULT_FILE' must contain exactly one branch name (found ${#_obd_lines[@]} line(s))"
    OUTPUT_BRANCH_DEFAULT="${_obd_lines[0]}"
    [[ -n "$OUTPUT_BRANCH_DEFAULT" ]] \
        || die "--output-branch-default-file: '$OUTPUT_BRANCH_DEFAULT_FILE' is empty"
    validate_branch_name "$OUTPUT_BRANCH_DEFAULT" "--output-branch-default-file"
fi

# Resolve the merge target. Precedence:
#   1. --output-branch            explicit override
#   2. profile output_branch      only in worktree mode (ignored otherwise)
#   3. --output-branch-default    the Step-5 resolved base branch
#   4. profile base_branch        when Step 5 took it straight from the profile
#   5. detected primary branch    (the pre-existing default)
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
    if [[ -z "$OUTPUT_BRANCH_OVERRIDE" && -z "$OUTPUT_BRANCH_DEFAULT" \
          && "$WORKTREE_MODE" == true && -n "$_p_base" ]]; then
        validate_branch_name "$_p_base" "profile base_branch"
        OUTPUT_BRANCH_DEFAULT="$_p_base"
    fi
fi
# Outside worktree mode there is no merge at Step 9, so no derived target applies.
[[ "$WORKTREE_MODE" == true ]] || { OUTPUT_BRANCH_OVERRIDE=""; OUTPUT_BRANCH_DEFAULT=""; }
[[ -n "$OUTPUT_BRANCH_OVERRIDE" ]] || OUTPUT_BRANCH_OVERRIDE="$OUTPUT_BRANCH_DEFAULT"

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
    local primary
    primary=$(detect_primary_branch)

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

    if [[ -n "$current_branch" && "$current_branch" != "$primary" ]]; then
        echo "Branch: $current_branch"
    fi

    echo "Base branch: $primary"
    echo "Output branch: ${OUTPUT_BRANCH_OVERRIDE:-$primary}"
    echo "plan_verified: []"
    echo "---"
    echo ""
}

# Record `Output branch:` inside a plan file that ALREADY carries frontmatter.
# build_header() is skipped for such sources, so without this the flag would be
# accepted and silently dropped and Step 9 would merge somewhere else.
# Replaces an existing field, else inserts before the closing `---`, keeping the
# `---` count at 2. No-op when the file does not open with `---`.
splice_output_branch() {
    local file="$1" branch="$2"
    [[ "$(head -n 1 "$file" 2>/dev/null || true)" == "---" ]] || return 0
    # Renderer contract (lib/atomic_write.sh): a single `awk`, so the renderer's
    # exit status IS awk's — no extra guard needed. Routing it through
    # ait_atomic_render also fixes the old `awk … > "$tmp" && mv …` form, which
    # left the temp behind whenever awk failed.
    _ait_splice_output_branch_body() {
        awk -v br="$branch" '
            NR == 1                             { print; next }
            done_fm                             { print; next }
            /^Output branch:/                   { print "Output branch: " br; seen = 1; next }
            $0 == "---" {
                if (!seen) print "Output branch: " br
                done_fm = 1; print; next
            }
                                                { print }
        ' "$file"
    }
    ait_atomic_render "$file" _ait_splice_output_branch_body \
        || die "could not splice Output branch into: $file"
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

# Sources that already had frontmatter bypassed build_header(), so the
# `Output branch:` field has to be spliced into their existing block. Only when
# the caller asked for one — never silently rewrite an existing plan.
# Splice whenever the caller expressed ANY intent about the output branch --
# not only when a value was resolved. Otherwise a plan whose frontmatter already
# carries a stale `Output branch:` keeps it, and Step 9 merges to the old target.
if [[ "$has_frontmatter" == true && "$OUTPUT_INTENT" == true ]]; then
    splice_output_branch "$EXTERNAL_PLAN" "${OUTPUT_BRANCH_OVERRIDE:-$(detect_primary_branch)}"
fi

if [[ "$EXISTED_BEFORE" == true ]]; then
    echo "OVERWRITTEN:${EXTERNAL_PLAN}:${SOURCE}"
else
    echo "EXTERNALIZED:${EXTERNAL_PLAN}:${SOURCE}"
fi
