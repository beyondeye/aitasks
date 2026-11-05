#!/usr/bin/env bash
# test_file_refs_yaml.sh - file_references: is YAML end to end (t2209).
#
# Differential tests against PyYAML (both yaml.SafeLoader and task_yaml's own
# loader) for the shell side of the field:
#   A. format_yaml_path_list -- every corpus entry, alone and as one list, reads
#      back as the identical str; identical bytes under LC_ALL=C and a UTF-8
#      locale; code points YAML cannot carry literally are escaped (with a
#      negative control showing a literal U+0085 really is folded).
#   B. get_file_references / read_file_references_batch -- byte-exact
#      round-trip, fail-closed on non-path entries / unparseable frontmatter /
#      no PyYAML, and all-or-nothing framing (one mutant per guard).
#   C. the quote-aware flow scanner behind join_yaml_flow_lists,
#      read_yaml_list and yaml_field_block -- record extents agree with
#      PyYAML's top-level keys; a disabled-scanner mutant fails the case.
#   D. validate_file_ref -- locale-independent byte checks.
#
# Skips (exit 0, printed reason) when no Python with PyYAML is available: the
# file is about agreement with that parser.
#
# Run: bash tests/test_file_refs_yaml.sh

set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
LIB="$PROJECT_DIR/.aitask-scripts/lib"

. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0
FAIL=0
TOTAL=0

# shellcheck disable=SC2034  # read by task_utils.sh when sourced
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$LIB/task_utils.sh"

PY="$(resolve_python)"
if [[ -z "$PY" ]] || ! "$PY" -c 'import yaml' 2>/dev/null; then
    echo "SKIP: no Python with PyYAML available (resolved: '${PY:-none}')"
    exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/t2209_refs.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

UTF8_LOCALE=""
for _l in C.UTF-8 C.utf8 en_US.UTF-8 en_US.utf8; do
    if locale -a 2>/dev/null | grep -qx "$_l"; then UTF8_LOCALE="$_l"; break; fi
done

# The oracle: argv[1] = mode, rest per mode. Isolated (-I) and lib appended.
cat > "$TMP/oracle.py" <<'PY'
import sys, json, yaml
sys.path.append(sys.argv[1])
import task_yaml
mode = sys.argv[2]

def loads(text):
    return [yaml.load(text, Loader=L) for L in (yaml.SafeLoader, task_yaml._TaskSafeLoader)]

if mode == "corpus":
    # The corpus, hex-encoded UTF-8, one entry per line.
    c = [",", "[", "]", "{", "}", ":", "#", "?", "&", "*", "!", "|", ">", "%", "@", "`",
         "on", "On", "ON", "off", "null", "Null", "NULL", "~", "y", "n", "Y", "yes", "no",
         "true", "False", "010", "0x1f", "0b11", "1.5", ".5", ".inf", ".NaN", ".gitignore",
         "1:30", "2026-01-01", "85_2", "+1", "-1", "-x", "x-", "_x", "/abs/p.py",
         " lead.py", "trail.py ", "a b.py", 'say "hi"', "back\\slash", "it's", "'q'",
         "a,b.py", "docs/a[bc].md", ":12", "foo:", "a: b", "a #b", "a#b", "a:b", "x?y",
         "{a}", "é.py", " nbsp", "\U0001F600.py", "﷐x", "a^b:1-2^3-4",
         "foo.py", "bar.py:10-20", "foo.py:10-20^30-40^89-100", "=", "<<", "a<<b"]
    for lead in ",[]{}:#?&*!|>%@`'\"-":
        c += [lead + "x.py", "x" + lead + "y.py", "x.py" + lead]
    for i in list(range(1, 32)) + [127]:
        if i in (10, 13):
            continue
        c.append("a%sb.py" % chr(i))
    for i in range(0x80, 0xA0):
        c.append("a%sb.py" % chr(i))
    c += ["a b.py", "a b.py", "a﻿b.py", "a￾b.py", "a￿b.py"]
    seen = set(); out = []
    for e in c:
        if e not in seen:
            seen.add(e); out.append(e)
    for e in out:
        print(e.encode("utf-8").hex())
elif mode == "check_lists":
    # argv[3] = corpus hex file, argv[4] = formatted file (one flow list per
    # entry, then the whole-corpus list last). Prints one FAIL line per mismatch.
    corpus = [bytes.fromhex(l.strip()).decode("utf-8") for l in open(sys.argv[3]) if l.strip()]
    lines = open(sys.argv[4], encoding="utf-8").read().split("\n")
    bad = 0
    for i, e in enumerate(corpus):
        try:
            got = loads(lines[i])
        except Exception as ex:
            got = ["ERROR " + type(ex).__name__]
        for g in got:
            if g != [e] or not isinstance(g[0], str):
                print("FAIL entry %r written %r read %r" % (e, lines[i], g)); bad += 1; break
    try:
        whole = loads(lines[len(corpus)])
    except Exception as ex:
        whole = ["ERROR " + type(ex).__name__]
    for g in whole:
        if g != corpus:
            print("FAIL whole-corpus list does not round-trip"); bad += 1; break
    print("CHECKED %d" % len(corpus))
elif mode == "load_one":
    # argv[3] = a YAML flow list on one line; prints the ascii() of what loads.
    print(ascii(yaml.load(open(sys.argv[3], encoding="utf-8").read(), Loader=task_yaml._TaskSafeLoader)))
elif mode == "keys":
    # argv[3] = frontmatter text file; prints its top-level keys, one per line.
    d = yaml.load(open(sys.argv[3], encoding="utf-8").read(), Loader=task_yaml._TaskSafeLoader)
    for k in d:
        print(k)
PY

oracle() { "$PY" -I "$TMP/oracle.py" "$LIB" "$@"; }

hex_to_bytes() {   # <hex> -> raw bytes on stdout (no newline)
    local h="$1" esc="" i
    for (( i = 0; i < ${#h}; i += 2 )); do esc+="\\x${h:i:2}"; done
    printf '%b' "$esc"
}

# =========================================================================
echo "=== A. format_yaml_path_list vs PyYAML ==="
oracle corpus > "$TMP/corpus.hex"
n_corpus=$(grep -c . "$TMP/corpus.hex")
: > "$TMP/formatted.txt"
: > "$TMP/all_entries"
locale_mismatch=0
while IFS= read -r h; do
    e="$(hex_to_bytes "$h"; printf x)"; e="${e%x}"
    printf '%s\n' "$e" >> "$TMP/all_entries"
    c_out="$(LC_ALL=C format_yaml_path_list "$e")"
    if [[ -n "$UTF8_LOCALE" ]]; then
        u_out="$(LC_ALL="$UTF8_LOCALE" format_yaml_path_list "$e")"
        [[ "$c_out" == "$u_out" ]] || { locale_mismatch=$((locale_mismatch + 1)); echo "  locale mismatch for hex $h: C=[$c_out] UTF8=[$u_out]"; }
    fi
    printf '%s\n' "$c_out" >> "$TMP/formatted.txt"
done < "$TMP/corpus.hex"
whole_c="$(LC_ALL=C format_yaml_path_list < "$TMP/all_entries")"
printf '%s\n' "$whole_c" >> "$TMP/formatted.txt"
if [[ -n "$UTF8_LOCALE" ]]; then
    whole_u="$(LC_ALL="$UTF8_LOCALE" format_yaml_path_list < "$TMP/all_entries")"
    [[ "$whole_c" == "$whole_u" ]] || locale_mismatch=$((locale_mismatch + 1))
    assert_eq "formatter output is byte-identical under LC_ALL=C and $UTF8_LOCALE" "0" "$locale_mismatch"
else
    echo "  (UTF-8 locale half skipped: neither C.UTF-8 nor en_US.UTF-8 is installed)"
fi
check="$(oracle check_lists "$TMP/corpus.hex" "$TMP/formatted.txt")"
assert_contains "oracle checked the whole corpus" "CHECKED $n_corpus" "$check"
assert_not_contains "every entry (and the whole list) reads back as the identical str in both loaders" "FAIL" "$check"
[[ "$check" == *FAIL* ]] && echo "$check" | grep FAIL | head -20

# Pinned shapes: plain stays plain, the rest is quoted.
assert_eq "plain paths stay plain" "[foo.py, bar.py:10-20, .gitignore, /abs/p.py]" \
    "$(format_yaml_path_list $'foo.py\nbar.py:10-20\n.gitignore\n/abs/p.py')"
assert_eq "comma / bracket / YAML words are quoted" '["a,b.py", "docs/a[bc].md", "on", "null", "010"]' \
    "$(format_yaml_path_list $'a,b.py\ndocs/a[bc].md\non\nnull\n010')"
assert_eq "U+0085 is written as \\x85" '["a\x85b.py"]' "$(LC_ALL=C format_yaml_path_list $'a\xc2\x85b.py')"
assert_eq "empty input -> []" "[]" "$(format_yaml_path_list "")"
cr_rc=0; format_yaml_path_list $'a\rb' >/dev/null 2>&1 || cr_rc=$?
assert_eq "an entry holding CR is refused" "1" "$cr_rc"

# Negative control: a LITERAL U+0085 inside "..." is folded by PyYAML, so the
# probe above really can see the corruption the escape prevents.
printf '["a\xc2\x85b.py"]' > "$TMP/literal_nel.txt"
assert_eq "control: literal U+0085 in a quoted scalar reads as a space" "['a b.py']" \
    "$(oracle load_one "$TMP/literal_nel.txt")"

# =========================================================================
echo "=== B. get_file_references: round-trip and fail-closed ==="
{ echo "---"; echo "status: Ready"; echo "file_references: $whole_c"; echo "labels: [x]"; echo "---"; echo "body"; } > "$TMP/whole.md"
got="$(get_file_references "$TMP/whole.md"; printf x)"; got="${got%x}"
want="$(cat "$TMP/all_entries"; printf x)"; want="${want%x}"
assert_eq "whole corpus round-trips byte-for-byte through the reader" "$want" "$got"

mk() { printf -- '---\nstatus: Ready\nfile_references: %s\n---\nbody\n' "$2" > "$TMP/$1.md"; }
run_rc() { local rc=0; out="$( "$@" )" || rc=$?; echo "$rc|$out"; }
mk plain '[a.py, "a,b.py", lib/x.py:3-5]'
assert_eq "quoted comma entry is ONE path" "0|a.py
a,b.py
lib/x.py:3-5" "$(run_rc get_file_references "$TMP/plain.md")"
mk words '[on, 010]'
assert_eq "unquoted on/010 are not paths -> exit 2, nothing printed" "2|" "$(run_rc get_file_references "$TMP/words.md")"
mk glob '[docs/a[bc].md]'
assert_eq "unquoted [docs/a[bc].md] is invalid YAML -> exit 2" "2|" "$(run_rc get_file_references "$TMP/glob.md")"
printf -- '---\nstatus: [a\nfile_references: [a.py]\n---\n' > "$TMP/broken.md"
assert_eq "unparseable frontmatter -> exit 2" "2|" "$(run_rc get_file_references "$TMP/broken.md")"
printf 'no frontmatter at all\n' > "$TMP/nofm.md"
assert_eq "no frontmatter -> no references, exit 0" "0|" "$(run_rc get_file_references "$TMP/nofm.md")"
printf -- '---\nstatus: Ready\n---\n' > "$TMP/nofield.md"
assert_eq "absent field -> exit 0, empty" "0|" "$(run_rc get_file_references "$TMP/nofield.md")"
mk nl '["a\nb.py"]'
assert_eq "an entry holding a newline is not a path -> exit 2" "2|" "$(run_rc get_file_references "$TMP/nl.md")"

# No usable PyYAML: an interpreter without site-packages.
printf '#!/bin/sh\nexec "%s" -S "$@"\n' "$PY" > "$TMP/py_nosite"; chmod +x "$TMP/py_nosite"
# shellcheck disable=SC2034  # AIT_PYTHON is read by resolve_python in this shell
assert_eq "no PyYAML -> exit 3, nothing printed" "3|" \
    "$( (unset _AIT_RESOLVED_PYTHON; AIT_PYTHON="$TMP/py_nosite"; run_rc get_file_references "$TMP/plain.md") )"

# Framing mutants: a stub that corrupts the real glue's output in one way each.
mutant() {   # <name> <sed-script>
    printf '#!/bin/sh\n"%s" "$@" | sed %s\n' "$PY" "'$2'" > "$TMP/py_$1"; chmod +x "$TMP/py_$1"
    # shellcheck disable=SC2034  # AIT_PYTHON is read by resolve_python in this shell
    ( unset _AIT_RESOLVED_PYTHON; AIT_PYTHON="$TMP/py_$1"; run_rc read_file_references_batch "$TMP/plain.md" "$TMP/nofield.md" )
}
assert_eq "control: an identity stub passes framing" "0" "$(mutant ident 's/^//' | head -n1 | cut -d'|' -f1)"
assert_eq "mutant: one REF line dropped -> exit 2, nothing printed" "2|" "$(mutant noref '0,/^REF:/{/^REF:/d}')"
assert_eq "mutant: an END line dropped -> exit 2" "2|" "$(mutant noend '0,/^END:/{/^END:/d}')"
assert_eq "mutant: DONE dropped -> exit 2" "2|" "$(mutant nodone '/^DONE:/d')"
assert_eq "mutant: DONE count wrong -> exit 2" "2|" "$(mutant baddone 's/^DONE:.*/DONE:7/')"
assert_eq "mutant: blocks out of order -> exit 2" "2|" "$(mutant order 's/^FILE:1$/FILE:0/')"
assert_eq "mutant: a stray line -> exit 2" "2|" "$(mutant stray '/^DONE:/i\
NOISE:1')"
assert_eq "mutant: a line after DONE -> exit 2" "2|" "$(mutant after '/^DONE:/a\
REF:x')"

assert_eq "union reads all files, dedupes, newline-separated" "a.py
a,b.py
lib/x.py:3-5" "$(union_file_references "$TMP/plain.md" "$TMP/nofield.md" "$TMP/plain.md")"
assert_eq "union refuses a non-path source" "2|" "$(run_rc union_file_references "$TMP/plain.md" "$TMP/words.md")"

# =========================================================================
echo "=== C. flow scanner extents vs PyYAML ==="
tail_lines=$'verification_baseline: abc @ 2026-01-01 10:00\nlabels: [x]'
scanner_case() {   # <name> <field block (physical lines)>
    local name="$1" block="$2" fm keys_bash keys_py
    fm="status: Ready"$'\n'"$block"$'\n'"$tail_lines"
    printf '%s\n' "$fm" > "$TMP/fm_$name.yaml"
    printf -- '---\n%s\n---\nbody\n' "$fm" > "$TMP/fm_$name.md"
    keys_bash="$(printf '%s\n' "$fm" | join_yaml_flow_lists | sed -nE 's/^([A-Za-z0-9_]+):.*/\1/p')"
    keys_py="$(oracle keys "$TMP/fm_$name.yaml")"
    assert_eq "[$name] joiner record keys == PyYAML keys" "$keys_py" "$keys_bash"
    assert_eq "[$name] read_yaml_field verification_baseline" "abc @ 2026-01-01 10:00" \
        "$(read_yaml_field "$TMP/fm_$name.md" verification_baseline)"
    assert_eq "[$name] read_yaml_list labels" "x" "$(read_yaml_list "$TMP/fm_$name.md" labels)"
}
scanner_case dq_bracket 'file_references: ["a[.py"]'
scanner_case sq_escaped "file_references: ['it''s [']"
scanner_case dq_escaped 'file_references: ["a\"[", b]'
scanner_case apostrophe $'file_references: [it\'s, x]'
scanner_case comment 'file_references: [a] # [x'
scanner_case wrapped_comment $'file_references: [a, # note [\n  "b]", c]'
scanner_case dq_multiline $'file_references: ["a\n  [b"]'
scanner_case plain_title 'title: a [b'
scanner_case block_item $'items:\n  - name: x [y'
scanner_case wrapped_plain $'file_references: [a.py,\n  b.py, c.py]'
# Valid quoted continuations that LOOK like a key or a delimiter (review
# finding): the record must run to the closing quote, never stop early.
scanner_case dq_dashdash $'file_references: ["a\n---suffix.py"]'
scanner_case dq_keylike $'file_references: ["a\nname: part.py"]'
scanner_case sq_keylike $'file_references: [\'a\nname: part.py\']'

# Malformed (PyYAML rejects it): a quote that never closes falls back to the
# plain-count extent at end of input, or at an exact `---` delimiter -- so it
# can neither swallow the following keys nor run on into the body.
assert_eq "an unterminated quote: plain extent at end of input" $'il: ["]\nstatus: Ready' \
    "$(printf '%s\n' 'il: ["]' 'status: Ready' | join_yaml_flow_lists)"
printf '%s\n' '---' 'il: ["]' 'status: Ready' '---' 'body says "x"]' 'more' > "$TMP/malformed_body.md"
assert_eq "an unterminated quote never runs past the closing ---" $'---\nil: ["]\nstatus: Ready\n---\nbody says "x"]\nmore' \
    "$(join_yaml_flow_lists < "$TMP/malformed_body.md")"
assert_eq "read_yaml_list keeps the lone-quote item (t1609 tolerance)" '"' "$(read_yaml_list "$TMP/malformed_body.md" il)"
assert_eq "read_yaml_field after the malformed record" "Ready" "$(read_yaml_field "$TMP/malformed_body.md" status)"
assert_eq "yaml_field_block: malformed record -> plain extent" 'il: ["]' \
    "$(printf '%s\n' 'il: ["]' 'status: Ready' | yaml_field_block il)"
# Valid and lenient: a column-0 continuation of an open list still joins.
assert_eq "a column-0 continuation without an open quote still joins" $'labels: [a, b]\nx: 1' \
    "$(printf '%s\n' 'labels: [a,' 'b]' 'x: 1' | join_yaml_flow_lists)"

field_block() { printf '%s\n' "$1" | yaml_field_block file_references; }
assert_eq "yaml_field_block: flow block, original lines" $'file_references: [a,\n  "b]", c]' \
    "$(field_block $'x: 1\nfile_references: [a,\n  "b]", c]\nlabels: [x]')"
assert_eq "yaml_field_block: one-line quoted bracket" 'file_references: ["a[.py"]' \
    "$(field_block $'file_references: ["a[.py"]\nverification_baseline: v')"
assert_eq "yaml_field_block: block sequence" $'file_references:\n- a.py\n- b.py' \
    "$(field_block $'file_references:\n- a.py\n- b.py\nlabels: [x]')"
assert_eq "yaml_field_block: absent -> nothing" "" "$(field_block $'labels: [x]')"
assert_eq "yaml_field_block: quoted continuation that looks like ---" $'file_references: ["a\n---suffix.py"]' \
    "$(field_block $'file_references: ["a\n---suffix.py"]\nlabels: [x]')"
assert_eq "yaml_field_block: quoted continuation that looks like a key" $'file_references: ["a\nname: part.py"]' \
    "$(field_block $'file_references: ["a\nname: part.py"]\nlabels: [x]')"

# Mutant: the pre-t2209 plain bracket count. The dq_bracket case must FAIL
# under it, proving the scanner is what that case exercises.
mutant_keys="$(
    # shellcheck disable=SC2329  # invoked by join_yaml_flow_lists below
    _yaml_flow_advance() {
        local s="$1" opens closes
        opens="${s//[^\[]/}"; closes="${s//[^\]]/}"
        _yfs_depth=$(( _yfs_depth + ${#opens} - ${#closes} ))
    }
    printf '%s\n' "status: Ready" 'file_references: ["a[.py"]' "$tail_lines" \
        | join_yaml_flow_lists | sed -nE 's/^([A-Za-z0-9_]+):.*/\1/p'
)"
assert_eq "mutant: a plain bracket count swallows the following keys" $'status\nfile_references' "$mutant_keys"

# =========================================================================
echo "=== D. validate_file_ref is locale-independent ==="
vrc() {   # <locale> <ref> -> exit status of validate_file_ref
    ( export LC_ALL="$1"; validate_file_ref "$2" ) >/dev/null 2>&1; echo $?
}
locales=(C)
[[ -n "$UTF8_LOCALE" ]] && locales+=("$UTF8_LOCALE")
for loc in "${locales[@]}"; do
    assert_eq "[$loc] accepts a,b.py" 0 "$(vrc "$loc" 'a,b.py')"
    assert_eq "[$loc] accepts é.py" 0 "$(vrc "$loc" $'\xc3\xa9.py')"
    assert_eq "[$loc] accepts a<U+0085>b.py" 0 "$(vrc "$loc" $'a\xc2\x85b.py')"
    assert_eq "[$loc] accepts docs/a[bc].md:3-4" 0 "$(vrc "$loc" 'docs/a[bc].md:3-4')"
    assert_eq "[$loc] rejects a newline" 1 "$(vrc "$loc" $'a\nb')"
    assert_eq "[$loc] rejects a tab" 1 "$(vrc "$loc" $'a\tb')"
    assert_eq "[$loc] rejects DEL" 1 "$(vrc "$loc" $'a\x7fb')"
    assert_eq "[$loc] rejects invalid UTF-8" 1 "$(vrc "$loc" $'a\xffb')"
    assert_eq "[$loc] rejects a truncated sequence" 1 "$(vrc "$loc" $'a\xc2')"
    assert_eq "[$loc] rejects an encoded surrogate" 1 "$(vrc "$loc" $'a\xed\xa0\x80b')"
done

# --- Summary ---
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
