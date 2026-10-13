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

# Framework-appended sections: everything from the first of these headers on is
# ledger, not declared text. MUST recognize every header that
# plan_paths.cut_task_framework_sections cuts at (tests/test_fold_content.sh pins
# the parity), or folded history would read as task-declared paths.
FRAMEWORK_HEADER_ERE='^##[ \t]+(Inbox|Gate Runs|Folded History)[ \t]*$'
FOLDED_HISTORY_ERE='^##[ \t]+Folded History[ \t]*$'

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

# split_fw head|tail - the declared part of a body (before the first framework
# header) or the framework part (from it on).
split_fw() {
    awk -v part="$1" -v re="$FRAMEWORK_HEADER_ERE" '
        !cut && $0 ~ re { cut = 1 }
        (part == "head" && !cut) || (part == "tail" && cut)
    '
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

# split_history before|after - a framework tail split around the end of its
# "## Folded History" section: "before" runs through the section's last line,
# "after" starts at the next "## " header. No "## Folded History" -> all "after".
split_history() {
    awk -v part="$1" -v re="$FOLDED_HISTORY_ERE" '
        state == 0 && $0 ~ re { state = 1 }
        state == 1 && $0 !~ re && /^##[ \t]/ { state = 2 }
        state == 0 { if (part == "after") print; next }
        (state == 1 && part == "before") || (state == 2 && part == "after")
    '
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

primary_decl=$(split_fw head <<<"$primary_body")
primary_tail=$(split_fw tail <<<"$primary_body")

# Everything is built into a file and printed only once complete. Callers pipe
# this into `aitask_update.sh --desc-file -`, which REPLACES the description:
# a failure part-way must leave stdout empty (update then keeps the current
# body), never a truncated body that drops the primary's ledgers.
out_file=$(mktemp "${TMPDIR:-/tmp}/aitask_fold_content.XXXXXX")
trap 'rm -f "$out_file"' EXIT

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
        extract_body "$f" | split_fw head | neutralize_markers
        folded_refs+=("- **t${n}** (\`${base}\`)")

        tail=$(extract_body "$f" | split_fw tail | shift_headings | neutralize_markers)
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

    # Folded History, then the primary's own framework sections (kept terminal).
    # A primary that already carries a "## Folded History" (an earlier fold) gets
    # the new entries appended to that section rather than a second one.
    tail_before=$(split_history before <<<"$primary_tail")
    tail_after=$(split_history after <<<"$primary_tail")
    if [[ -n "$tail_before" ]]; then
        printf '\n%s\n' "$tail_before"
    elif [[ -n "$history" ]]; then
        printf '\n## Folded History\n\nReference only: the notes and gate history these tasks carried before they were folded. Their markers are neutralized, so none of it is part of this task'"'"'s inbox or gate ledger.\n'
    fi
    if [[ -n "$history" ]]; then
        printf '\n%s\n' "$history"
    fi
    if [[ -n "$tail_after" ]]; then
        printf '\n%s\n' "$tail_after"
    fi
} > "$out_file"

cat "$out_file"
