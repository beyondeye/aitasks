#!/usr/bin/env bash
# test_attach_meta.sh - per-blob metadata ledger (lib/attachment_meta.py) and
# frontmatter mutation (lib/frontmatter_patch.py) for t1030_2. No git required:
# these are pure-ish primitives (meta-dir + task file only).
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/yaml_utils.sh"

PY="$(resolve_python)"
META="$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.py"
FM="$PROJECT_DIR/.aitask-scripts/lib/frontmatter_patch.py"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT
MD="$TMP/meta"

H1="sha256:1111111111111111111111111111111111111111111111111111111111111111"
H2="sha256:2222222222222222222222222222222222222222222222222222222222222222"
H1_FILE="$MD/11/11111111111111111111111111111111111111111111111111111111111111.json"
H2_FILE="$MD/22/22222222222222222222222222222222222222222222222222222222222222.json"

meta() { "$PY" "$META" --meta-dir "$MD" "$@"; }
fm()   { "$PY" "$FM" "$@"; }

# ── attachment_meta.py: per-blob ledger ──────────────────────────────────────

meta incref "$H1" 10_2 mime=image/png size=12 backend=local
assert_eq "incref records the task ref" "10_2" "$(meta refs "$H1")"
assert_file_exists "meta file written at sharded path" "$H1_FILE"

meta incref "$H1" 10_2                      # idempotent re-apply (rebase-safe)
assert_eq "repeated incref keeps refs a size-1 set" "10_2" "$(meta refs "$H1")"

meta incref "$H1" 42
assert_eq "second task ref added (set-add)" "10_2,42" "$(meta refs "$H1" | paste -sd, -)"

meta decref "$H1" 42
meta decref "$H1" 42                        # no-op (idempotent)
assert_eq "decref removes ref; repeated is no-op" "10_2" "$(meta refs "$H1")"

# Schema is blob-intrinsic + refs only — display fields live in the frontmatter.
c="$(cat "$H1_FILE")"
assert_contains "meta has mime"     '"mime"'     "$c"
assert_contains "meta has size"     '"size"'     "$c"
assert_contains "meta has backend"  '"backend"'  "$c"
assert_not_contains "meta has NO name"     '"name"'     "$c"
assert_not_contains "meta has NO added_at" '"added_at"' "$c"

# zero-refcount lists blobs whose refs went empty (advisory GC candidates).
meta decref "$H1" 10_2
assert_contains "zero-refcount lists the emptied blob" "$H1" "$(meta zero-refcount)"

# Two UNRELATED attachments mutate DIFFERENT meta files (no shared hotspot).
meta incref "$H2" 5 mime=image/jpeg size=99 backend=local
assert_file_exists "unrelated blob writes its own meta file" "$H2_FILE"
assert_eq "unrelated blob has its own refs" "5" "$(meta refs "$H2")"

# Blob-intrinsic verify-don't-overwrite: a mismatched mime dies loudly.
assert_exit_nonzero "incref with mismatched mime dies" \
    "$PY" "$META" --meta-dir "$MD" incref "$H2" 6 mime=image/png

# rebind replaces a task across all meta files (fold support, t1030_3).
meta rebind 5 5_1
assert_eq "rebind replaces task id in refs" "5_1" "$(meta refs "$H2")"

# Atomic writes leave no temp files behind.
assert_eq "no .meta.* temp files left" "0" "$(find "$MD" -name '.meta.*' | wc -l | tr -d ' ')"

# ── frontmatter_patch.py: append / remove round-trip ─────────────────────────

mk_task() {
    printf -- '---\npriority: high\nstatus: Ready\nupdated_at: 2020-01-01 00:00\nlabels: [x, y]\n---\n\nBody paragraph one.\n\nBody paragraph two.\n' > "$1"
}

# Absent block -> append creates a well-formed block; unrelated keys + body kept.
t="$TMP/absent.md"; mk_task "$t"
fm append "$t" attachments hash="$H1" name=shot.png mime=image/png size=12 added_at="2026-06-29 10:00" backend=local --now "2026-06-29 11:00"
recs="$(read_yaml_mappings "$t" attachments)"
body="$(cat "$t")"
assert_contains "append: hash round-trips"  "hash=$H1"        "$recs"
assert_contains "append: name round-trips"  "name=shot.png"   "$recs"
assert_contains "append: backend round-trips" "backend=local" "$recs"
assert_contains "append bumps updated_at"   "updated_at: 2026-06-29 11:00" "$body"
assert_contains "append preserves body"     "Body paragraph two." "$body"
assert_contains "append preserves unrelated key" "priority: high" "$body"
assert_contains "append preserves other list key" "labels: [x, y]" "$body"

# Empty inline list -> first append converts to a valid block list.
t="$TMP/empty.md"; mk_task "$t"
# inject `attachments: []`
"$PY" - "$t" <<'PYEOF'
import sys
p = sys.argv[1]
s = open(p).read().replace("labels: [x, y]\n", "labels: [x, y]\nattachments: []\n")
open(p, "w").write(s)
PYEOF
fm append "$t" attachments hash="$H1" name=a.png --now x
assert_eq "empty-list append yields one record" "1" \
    "$(read_yaml_mappings "$t" attachments | grep -c '^hash=')"

# Hostile values round-trip exactly (writer quotes only when needed).
t="$TMP/quote.md"; mk_task "$t"
fm append "$t" attachments hash="$H1" name="bug #3.png" --now x       # whitespace-# -> quoted
fm append "$t" attachments hash="$H2" name="plain#3.png" --now x      # literal # -> bare
fm append "$t" attachments hash="sha256:3333333333333333333333333333333333333333333333333333333333333333" name="report: v2.png" --now x  # colon-space -> quoted
fm append "$t" attachments hash="sha256:4444444444444444444444444444444444444444444444444444444444444444" name="café ☕.png" --now x       # unicode -> bare
recs="$(read_yaml_mappings "$t" attachments)"
assert_contains "whitespace-# name round-trips" "name=bug #3.png"   "$recs"
assert_contains "literal-# name round-trips"    "name=plain#3.png"  "$recs"
assert_contains "colon-space name round-trips"  "name=report: v2.png" "$recs"
assert_contains "unicode name round-trips"      "name=café ☕.png"   "$recs"

# Multiple items: remove targets the right one and leaves siblings intact.
fm remove "$t" attachments --match-key hash --match-val "$H1" --now x
recs="$(read_yaml_mappings "$t" attachments)"
assert_not_contains "removed item's name is gone" "name=bug #3.png" "$recs"
assert_contains "sibling item survives removal"   "name=plain#3.png" "$recs"
assert_contains "other sibling survives removal"  "name=report: v2.png" "$recs"

# Removing a non-existent match fails loudly (caller bug).
assert_exit_nonzero "remove of missing hash dies" \
    "$PY" "$FM" remove "$t" attachments --match-key hash --match-val "$H1"

# Newline-in-name is rejected (out of scope per the reader contract).
t="$TMP/nl.md"; mk_task "$t"
assert_exit_nonzero "newline-in-name append dies" \
    "$PY" "$FM" append "$t" attachments hash="$H1" name="$(printf 'a\nb')"

echo ""
echo "test_attach_meta.sh: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
