#!/usr/bin/env bash
# aitask_fold_content.sh - Build merged description body for a folded task set
#
# Prints the merged description to stdout in the structure documented in
# .claude/skills/task-workflow/task-fold-content.md:
#   1. Primary declared body (unchanged)
#   2. One "## Merged from t<N>: <name>" section per folded task (its declared body)
#   3. A "## Folded Tasks" reference section
#   4. "## Folded History" -- the folded tasks' own "## Inbox" / "## Gate Runs"
#      (and any earlier "## Folded History"), reference only: headings shifted
#      down two levels and ledger markers neutralized, so neither gate_ledger nor
#      note_inbox reads them as the primary's. Omitted when no folded task has any.
#   5. The primary's own framework sections, kept last (gate runs append at EOF)
#
# Declared text and framework sections are told apart by the declared-text
# reader's own partition (plan_paths.split_task_framework_sections), so a body
# laid out by the pre-t1962 script -- "## Merged from" sections AFTER its
# ledgers, gate runs appended under them -- is rewritten into the order above.
#
# The primary description can be read from a file (positional argument) or
# piped through stdin (--primary-stdin). Stdin may be a plain description or a
# whole task file; a recognizable, closed task frontmatter block is stripped.
#
# Usage:
#   aitask_fold_content.sh <primary_file> <folded1> [<folded2> ...]
#   aitask_fold_content.sh --primary-stdin <folded1> [<folded2> ...]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

usage() {
    cat <<EOF
Usage: $0 <primary_file> <folded1> [<folded2> ...]
       $0 --primary-stdin <folded1> [<folded2> ...]

Emits a merged description body to stdout. Frontmatter is stripped from all
input files, and from stdin when it starts with a recognizable task frontmatter
block. Folded tasks' ledgers land, inert, under "## Folded History". See
task-fold-content.md for the exact output structure.
EOF
    exit 1
}

use_stdin=false
primary_file=""
folded=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --primary-stdin)
            use_stdin=true
            shift
            ;;
        --help|-h)
            usage
            ;;
        -*)
            die "unknown flag: $1"
            ;;
        *)
            if [[ "$use_stdin" == false && -z "$primary_file" ]]; then
                primary_file="$1"
            else
                folded+=("$1")
            fi
            shift
            ;;
    esac
done

if [[ "$use_stdin" == false && -z "$primary_file" ]]; then
    die "need primary file (or --primary-stdin)"
fi
[[ ${#folded[@]} -eq 0 ]] && die "need at least one folded task file"

# Extract the description body (everything after the closing frontmatter ---).
# Reads stdin when no file is given. Uses awk for macOS portability (no GNU sed
# features).
extract_body() {
    awk '
        BEGIN { in_fm = 0; seen_open = 0 }
        {
            if ($0 == "---") {
                if (seen_open == 0) { seen_open = 1; in_fm = 1; next }
                else if (in_fm == 1) { in_fm = 0; next }
            }
            if (seen_open == 1 && in_fm == 0) print
        }
    ' "${1:--}"
}

# Exit 0 iff stdin starts with a recognizable, CLOSED task frontmatter block:
# line 1 is "---", a closing "---" follows, every line between is blank, a
# "key:" line, indented, a "- " item or a YAML comment, and at least one is a
# core task key. Anything else -- a description that opens with a horizontal
# rule, or prose between two rules -- is not frontmatter and is kept verbatim.
is_task_frontmatter() {
    awk '
        NR == 1 { if ($0 != "---") { bad = 1; exit } next }
        $0 == "---" { closed = 1; exit }
        /^(status|priority|effort|issue_type):/ { core = 1 }
        /^[ \t]*$/ || /^[A-Za-z_][A-Za-z0-9_]*:$/ || /^[A-Za-z_][A-Za-z0-9_]*:[ \t]/ \
            || /^[ \t]/ || /^- / || /^#/ { next }
        { bad = 1; exit }
        END { if (bad || !closed || !core) exit 1; exit 0 }
    '
}

# split_fw <decl_file> <tail_file> [<live_file>] - write stdin's declared part
# and its framework part (ledger sections and ledger blocks, wherever they sit),
# via plan_paths.split_task_framework_sections: the partition every
# declared-text reader uses, so the two cannot disagree. With <live_file>, the
# framework part is split again by plan_paths.split_folded_history: its inert
# "## Folded History" text goes to <tail_file> and every live section and record,
# in order, to <live_file> -- so emitting history first never reorders a live
# record. Text naming no framework header and holding no "**" has no framework
# part and needs no python. The names, not "## <name>", are matched because the
# partition accepts any spacing after "##" (tests/test_fold_content.sh pins the
# parity).
split_fw() {
    local text=""
    IFS= read -r -d '' text || true
    if [[ "$text" != *Inbox* && "$text" != *'Gate Runs'* \
          && "$text" != *'Folded History'* && "$text" != *'**'* ]]; then
        printf '%s' "$text" > "$1"
        : > "$2"
        if [[ -n "${3:-}" ]]; then : > "$3"; fi
        return 0
    fi
    [[ -n "$PY" ]] || die "python3 is required to split ledger sections from folded task text (run 'ait setup')"
    printf '%s' "$text" | "$PY" -c '
import sys
sys.path.insert(0, sys.argv[1])
import plan_paths
data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
parts = plan_paths.split_task_framework_sections(data)
if len(sys.argv) > 4:
    parts = (parts[0],) + plan_paths.split_folded_history(parts[1])
for path, part in zip(sys.argv[2:], parts):
    with open(path, "wb") as handle:
        handle.write(part.encode("utf-8", "surrogateescape"))
' "$SCRIPT_DIR/lib" "$@"
}

# Make every ledger marker (any namespace) inert, via ledger_block's own
# grammar and line splitting -- an awk copy would miss forms the parser accepts
# (U+00A0 as \s, U+2028 as a line break). Input without "**" cannot hold a
# marker and passes through untouched, so ordinary folds need no python.
neutralize_markers() {
    local text=""
    IFS= read -r -d '' text || true
    if [[ "$text" != *'**'* ]]; then
        printf '%s' "$text"
        return 0
    fi
    [[ -n "$PY" ]] || die "python3 is required to neutralize folded ledger markers (run 'ait setup')"
    printf '%s' "$text" | "$PY" -c '
import sys
sys.path.insert(0, sys.argv[1])
import ledger_block
data = sys.stdin.buffer.read().decode("utf-8", "surrogateescape")
sys.stdout.buffer.write(
    ledger_block.neutralize_markers(data).encode("utf-8", "surrogateescape"))
' "$SCRIPT_DIR/lib"
}

# Shift every markdown heading down two levels (capped at ######), so a folded
# task's "## Inbox" becomes "#### Inbox" under its "### t<N>" history entry and
# no bare framework header survives.
shift_headings() {
    awk '
        /^#+[ \t]/ {
            match($0, /^#+/)
            lvl = RLENGTH + 2
            if (lvl > 6) lvl = 6
            $0 = substr("######", 1, lvl) substr($0, RLENGTH + 1)
        }
        { print }
    '
}

PY=$(resolve_python)

if [[ "$use_stdin" == true ]]; then
    primary_raw=$(cat)
    # Here-strings, not pipes: the predicate exits early, and under pipefail a
    # writer killed by SIGPIPE would turn a real frontmatter into a "no".
    if is_task_frontmatter <<<"$primary_raw"; then
        primary_body=$(extract_body <<<"$primary_raw")
    else
        primary_body=$primary_raw
    fi
else
    primary_body=$(extract_body "$primary_file")
fi

# Everything is built into a file and printed only once complete. Callers pipe
# this into `aitask_update.sh --desc-file -`, which REPLACES the description:
# a failure part-way must leave stdout empty (update then keeps the current
# body), never a truncated body that drops the primary's ledgers.
work_dir=$(mktemp -d "${TMPDIR:-/tmp}/aitask_fold_content.XXXXXX")
trap 'rm -rf "$work_dir"' EXIT
out_file="$work_dir/out"

printf '%s' "$primary_body" | split_fw "$work_dir/primary_decl" \
    "$work_dir/primary_history" "$work_dir/primary_live"
primary_decl=$(cat "$work_dir/primary_decl")
primary_history=$(cat "$work_dir/primary_history")
primary_live=$(cat "$work_dir/primary_live")

{
    # Emit primary declared body unchanged.
    printf '%s\n' "$primary_decl"

    # Parse each folded file's filename into a numeric ID and a human-readable
    # name, emit the "## Merged from t<N>: <name>" section, and collect a
    # reference list and the folded task's framework sections as a history entry.
    folded_refs=()
    history=""
    for f in "${folded[@]}"; do
        [[ -f "$f" ]] || die "folded file not found: $f"
        base=$(basename "$f")
        stem="${base#t}"
        stem="${stem%.md}"

        if [[ "$stem" =~ ^([0-9]+)_([0-9]+)_(.+)$ ]]; then
            n="${BASH_REMATCH[1]}_${BASH_REMATCH[2]}"
            name="${BASH_REMATCH[3]}"
        elif [[ "$stem" =~ ^([0-9]+)_(.+)$ ]]; then
            n="${BASH_REMATCH[1]}"
            name="${BASH_REMATCH[2]}"
        else
            die "cannot parse filename: $base"
        fi

        display_name="${name//_/ }"
        printf '\n## Merged from t%s: %s\n\n' "$n" "$display_name"
        extract_body "$f" | split_fw "$work_dir/folded_decl" "$work_dir/folded_tail"
        neutralize_markers < "$work_dir/folded_decl"
        folded_refs+=("- **t${n}** (\`${base}\`)")

        tail=$(shift_headings < "$work_dir/folded_tail" | neutralize_markers)
        if [[ -n "$tail" ]]; then
            if [[ -n "$history" ]]; then history+=$'\n\n'; fi
            history+="### t${n}: ${display_name}"$'\n\n'"${tail}"
        fi
    done

    # Emit the Folded Tasks reference section.
    printf '\n## Folded Tasks\n\nThe following existing tasks have been folded into this task. Their requirements are incorporated in the description above. These references exist only for post-implementation cleanup.\n\n'
    for ref in "${folded_refs[@]}"; do
        printf '%s\n' "$ref"
    done

    # Folded History, then the primary's own live sections and records (kept
    # terminal, in their original order). A primary that already carries a
    # "## Folded History" (an earlier fold) gets the new entries appended to
    # that section rather than a second one.
    if [[ -n "$primary_history" ]]; then
        printf '\n%s\n' "$primary_history"
    elif [[ -n "$history" ]]; then
        printf '\n## Folded History\n\nReference only: the notes and gate history these tasks carried before they were folded. Their markers are neutralized, so none of it is part of this task'"'"'s inbox or gate ledger.\n'
    fi
    if [[ -n "$history" ]]; then
        printf '\n%s\n' "$history"
    fi
    if [[ -n "$primary_live" ]]; then
        printf '\n%s\n' "$primary_live"
    fi
} > "$out_file"

cat "$out_file"
