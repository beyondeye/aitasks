#!/usr/bin/env bash
# test_note_doc_contract.sh - The task-note output codes are documented in two
# places, website/content/docs/commands/note.md and
# aidocs/framework/live_endpoint_resolution.md, and minted by three layers: the
# writer (aitask_note.sh), the resolver (aitask_live_endpoint.sh) and the
# per-agent adapters named in live_delivery/agents.txt. This test asserts, per
# layer, that the codes the pages attribute to that layer are exactly the codes
# that layer's source mints -- in both directions.
#
# WHAT IT BUYS: a code added, removed or renamed in any layer, or a code
# documented under the wrong layer, fails here, naming the layer and the token.
#
# WHAT IT DOES NOT BUY: it compares code-token SETS. It does not check that the
# prose describing a code is right, that exit statuses are right, or that the
# LIVE_PANE field layout still matches. Those stay covered by re-reading the
# --help texts at review time and by the behavioural suites
# tests/test_live_endpoint_degradation.sh and
# tests/test_note_with_live_composition.sh.
#
# THE DOCS FORMAT IS THE CONTRACT. Only table rows of the exact shape
#     | `<CODE>` | <writer|resolver|adapter> | ... |
# are read: a backticked code in the first cell, the minting layer in the
# second. Both pages declare this in an HTML comment at their tables. Prose is
# never parsed for intent.
#
# TOKEN GRAMMAR. A token is CODE or CODE:reason -- CODE is [A-Z][A-Z_]*, reason
# a concrete lowercase identifier. A <placeholder>, %s or $var after the colon
# is line-shape documentation, not a reason. Per layer, a code with at least one
# concrete reason contributes ONLY its reason tokens (LIVE_NONE:<reason> adds
# nothing beside LIVE_NONE:unlocked); a code with none contributes itself
# (NOTE_APPENDED:<note-id>|<path> -> NOTE_APPENDED). Both sides go through the
# same normalization, so they compare like with like.
#
# OWNERSHIP IS EXCLUSIVE, AND RESTATEMENT IS NOT OWNERSHIP. Each extraction
# looks only for the code families its layer mints. aitask_note.sh --help
# restates the resolver's LIVE_NONE reasons for its readers; the writer
# extraction never claims them, or the equality would double-count.
#
#   writer   the Output block of aitask_note.sh's show_help heredoc (NOTE_* and
#            READ_* lines), plus the concrete LIVE_ reasons the writer assigns
#            outside comments (LIVE_ERROR:resolver_unavailable).
#   resolver the resolver's emission sites -- its `echo "LIVE_..."` and
#            `printf 'LIVE_PANE:...'` lines. Its --help lists the LIVE_NONE
#            reasons but not the LIVE_ERROR ones, so --help alone would leave
#            documented codes outside the comparison.
#   adapter  every procedure agents.txt names, for LIVE_QUEUED and concrete
#            LIVE_NONE reasons. The manifest decides which adapters exist; the
#            walk mirrors the one in tests/test_live_endpoint_no_sendkeys.sh.
#
# SEAMS. NOTE_DOC_CONTRACT_{WRITER_SRC,RESOLVER_SRC,DELIVERY_DIR,NOTE_PAGE,
# ENDPOINT_PAGE} point the test at edited copies. They exist to prove the guard
# can fail -- a mutation run -- never to skip it.
#
# Run: bash tests/test_note_doc_contract.sh

set -u
export LC_ALL=C

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

WRITER_SRC="${NOTE_DOC_CONTRACT_WRITER_SRC:-.aitask-scripts/aitask_note.sh}"
RESOLVER_SRC="${NOTE_DOC_CONTRACT_RESOLVER_SRC:-.aitask-scripts/aitask_live_endpoint.sh}"
DELIVERY_DIR="${NOTE_DOC_CONTRACT_DELIVERY_DIR:-.aitask-scripts/live_delivery}"
NOTE_PAGE="${NOTE_DOC_CONTRACT_NOTE_PAGE:-website/content/docs/commands/note.md}"
ENDPOINT_PAGE="${NOTE_DOC_CONTRACT_ENDPOINT_PAGE:-aidocs/framework/live_endpoint_resolution.md}"
MANIFEST="$DELIVERY_DIR/agents.txt"
LAYERS="writer resolver adapter"

# --- Extraction: each function prints "<layer>\t<raw-token>" lines ----------

extract_writer() {
    awk '
        /^show_help\(\) \{/     { in_help = 1; next }
        in_help && /^EOF$/      { in_help = 0 }
        in_help && /^Output /   { in_out = 1 }
        in_help && /^Example:/  { in_out = 0 }
        in_help && in_out && /^[[:space:]]+(NOTE|READ)_[A-Z_]+/ {
            line = $0
            sub(/^[[:space:]]+/, "", line)
            sub(/[[:space:]].*$/, "", line)
            print "writer\t" line
        }
    ' "$WRITER_SRC"
    grep -vE '^[[:space:]]*#' "$WRITER_SRC" \
        | grep -oE 'LIVE_(ERROR|NONE):[a-z][a-z0-9_-]*' \
        | awk '{ print "writer\t" $0 }'
}

extract_resolver() {
    grep -E "(echo|printf)[[:space:]]+[\"']LIVE_" "$RESOLVER_SRC" \
        | grep -oE 'LIVE_[A-Z]+(:[a-z][a-z0-9_-]*)?' \
        | awk '{ print "resolver\t" $0 }'
}

extract_adapter() {
    local rel
    while read -r rel; do
        [[ -n "$rel" ]] || continue
        grep -oE 'LIVE_(QUEUED|NONE)(:[a-z][a-z0-9_-]*)?' "$DELIVERY_DIR/$rel" \
            | awk '{ print "adapter\t" $0 }'
    done < <(grep -vE '^[[:space:]]*(#|$)' "$MANIFEST" | awk '{ print $2 }')
}

# Rows of the declared shape only: | `<CODE>` | <layer> | ...
extract_page() {
    awk '
        match($0, /^\| `[^`]+` \| (writer|resolver|adapter) \|/) {
            row = substr($0, 1, RLENGTH)
            tok = row;   sub(/^\| `/, "", tok);            sub(/` \|.*$/, "", tok)
            layer = row; sub(/^\| `[^`]+` \| /, "", layer); sub(/ \|$/, "", layer)
            print layer "\t" tok
        }
    ' "$1"
}

# --- Normalization (see TOKEN GRAMMAR above) --------------------------------
# stdin "<layer>\t<raw>" -> stdout sorted "<layer>\t<token>". A raw value that
# does not begin with a CODE comes out as "MALFORMED\t<layer>\t<raw>".
normalize_tokens() {
    awk -F'\t' '
        {
            layer = $1; raw = $2
            if (match(raw, /^[A-Z][A-Z_]*/) == 0) { bad[layer "\t" raw] = 1; next }
            code = substr(raw, 1, RLENGTH)
            rest = substr(raw, RLENGTH + 1)
            if (substr(rest, 1, 1) == ":" && match(substr(rest, 2), /^[a-z][a-z0-9_-]*/)) {
                with_reason[layer SUBSEP code] = 1
                tok[layer "\t" code ":" substr(rest, 2, RLENGTH)] = 1
            } else {
                bare[layer SUBSEP code] = 1
            }
        }
        END {
            for (k in bare) {
                if (k in with_reason) continue
                split(k, p, SUBSEP)
                tok[p[1] "\t" p[2]] = 1
            }
            for (t in tok) print t
            for (b in bad) print "MALFORMED\t" b
        }
    ' | sort -u
}

# layer_set <normalized-lines> <layer>: that layer's tokens, sorted.
layer_set() {
    printf '%s\n' "$1" | awk -F'\t' -v l="$2" '$1 == l { print $2 }' | sort -u
}

# --- Probe guard -- run FIRST, and abort rather than continue ---------------
#
# Every assertion below compares two sets. If an extraction silently comes back
# empty -- a moved file, a reformatted heredoc, a renamed manifest -- a layer
# whose two sides are BOTH empty compares equal and passes while checking
# nothing. An empty side is therefore a hard stop, not a finding.

src_norm="$( { extract_writer; extract_resolver; extract_adapter; } | normalize_tokens)"
note_rows="$(extract_page "$NOTE_PAGE")"
endpoint_rows="$(extract_page "$ENDPOINT_PAGE")"
docs_norm="$(printf '%s\n%s\n' "$note_rows" "$endpoint_rows" | grep -v '^$' | normalize_tokens)"

vacant=""
[[ -n "$note_rows" ]]     || vacant="$vacant page:$NOTE_PAGE"
[[ -n "$endpoint_rows" ]] || vacant="$vacant page:$ENDPOINT_PAGE"
for layer in $LAYERS; do
    [[ -n "$(layer_set "$src_norm" "$layer")" ]]  || vacant="$vacant source:$layer"
    [[ -n "$(layer_set "$docs_norm" "$layer")" ]] || vacant="$vacant docs:$layer"
done
if [[ -n "$vacant" ]]; then
    echo "FATAL: extraction came back empty for:$vacant"
    echo "Every assertion below would compare an empty set and pass vacuously,"
    echo "so this run is aborted instead."
    echo
    echo "PASS: $PASS, FAIL: $((FAIL + 1)), TOTAL: $((TOTAL + 1))"
    exit 1
fi

# --- Test 1: every declared-shape row names a parseable code ----------------

malformed="$(printf '%s\n' "$docs_norm" \
    | awk -F'\t' '$1 == "MALFORMED" { print $2 ":" $3 }' | tr '\n' ' ')"
assert_eq "every declared-shape row names a parseable code" "" "${malformed% }"

# --- Test 2: per layer, the documented set equals the minted set ------------

for layer in $LAYERS; do
    src_set="$(layer_set "$src_norm" "$layer")"
    doc_set="$(layer_set "$docs_norm" "$layer")"
    undocumented="$(comm -23 <(printf '%s\n' "$src_set") <(printf '%s\n' "$doc_set") | tr '\n' ' ')"
    unminted="$(comm -13 <(printf '%s\n' "$src_set") <(printf '%s\n' "$doc_set") | tr '\n' ' ')"
    assert_eq "$layer: every code the $layer mints is documented" "" "${undocumented% }"
    assert_eq "$layer: every code documented as $layer is minted by it" "" "${unminted% }"
done

# --- Summary ---

echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ "$FAIL" -eq 0 ]]
