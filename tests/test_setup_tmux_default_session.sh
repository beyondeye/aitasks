#!/usr/bin/env bash
# test_setup_tmux_default_session.sh - `ait setup`'s tmux.default_session probe
# and writer (t1811).
#
#   * Probe: "already configured?" is answered by the same reader the session
#     resolvers use (lib/tmux_bootstrap.sh). The old grep|sed probe counted a
#     comment-only, `""`, `null` or `~` value as configured and skipped the
#     prompt. A value the resolvers cannot read is reported and left untouched.
#   * Writer: replaces only the direct child of the tmux block (a nested
#     `syncer: default_session:` survives), quotes names YAML would type or
#     split, never lets a name reach a sed replacement, preserves CRLF, and
#     writes nothing unless the result reads back as the name.
#   * Negative control: the pre-t1811 writer, inlined verbatim below, corrupts
#     or misreads each writer fixture — so the fixtures can tell the two apart.
#
# setup runs with a non-tty stdin, so the prompt takes the default "aitasks".
#
# Run: bash tests/test_setup_tmux_default_session.sh

set -e

SCRIPT_DIR_T="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR_T/.." && pwd)"

. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/t1811_setup_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# Scaffold: a project whose .aitask-scripts/lib holds the reader and what it
# sources; setup's SCRIPT_DIR points at it, so `$SCRIPT_DIR/..` is the project.
FAKE="$TMP/proj"
mkdir -p "$FAKE/.aitask-scripts/lib" "$FAKE/aitasks/metadata"
for f in tmux_bootstrap.sh tmux_exec.sh terminal_compat.sh; do
    cp "$PROJECT_DIR/.aitask-scripts/lib/$f" "$FAKE/.aitask-scripts/lib/"
done
CFG="$FAKE/aitasks/metadata/project_config.yaml"
LIB="$FAKE/.aitask-scripts/lib/tmux_bootstrap.sh"

# raw_read <project_root> — prints "<rc>|<value>" from the resolvers' reader.
raw_read() {
    local out rc=0
    out="$(bash -c 'source "$1"; _tmux_bootstrap_default_session_raw "$2"' _ "$LIB" "$1" 2>/dev/null)" || rc=$?
    printf '%s|%s' "$rc" "$out"
}

# run_setup — setup_tmux_default_session against the scaffold; prints its output.
run_setup() {
    bash -c 'source "$1/.aitask-scripts/aitask_setup.sh" --source-only
             SCRIPT_DIR="$2/.aitask-scripts"
             setup_tmux_default_session' _ "$PROJECT_DIR" "$FAKE" </dev/null 2>&1 \
        | sed $'s/\x1b\\[[0-9;]*m//g'
}

# run_writer <name> — _set_tmux_default_session_config on the scaffold config.
run_writer() {
    bash -c 'source "$1/.aitask-scripts/aitask_setup.sh" --source-only
             SCRIPT_DIR="$2/.aitask-scripts"
             _set_tmux_default_session_config "$3" "$4"' _ "$PROJECT_DIR" "$FAKE" "$CFG" "$1" \
        </dev/null >/dev/null 2>&1
}

# The pre-t1811 writer, verbatim (only the function name changed).
old_writer() {
    local config_file="$1" value="$2"
    local tmpf
    tmpf=$(mktemp)
    if grep -qE '^[[:space:]]*default_session:' "$config_file"; then
        sed "s/^\([[:space:]]*\)default_session:.*/\1default_session: $value/" "$config_file" > "$tmpf" \
            && cat "$tmpf" > "$config_file" && rm "$tmpf"
    elif grep -qE '^tmux:[[:space:]]*$' "$config_file"; then
        awk -v val="$value" '
            /^tmux:[[:space:]]*$/ { print; print "  default_session: " val; next }
            { print }
        ' "$config_file" > "$tmpf" && cat "$tmpf" > "$config_file" && rm "$tmpf"
    else
        { cat "$config_file"; printf '\ntmux:\n  default_session: %s\n' "$value"; } > "$tmpf" \
            && cat "$tmpf" > "$config_file" && rm "$tmpf"
    fi
}

set_cfg() { printf '%b' "$1" > "$CFG"; }

# --- probe: unset spellings now prompt and write the default --------------------

for spec in 'comment-only| # note' 'empty double quotes| ""' 'null| null' 'tilde| ~'; do
    label="${spec%%|*}"; value="${spec#*|}"
    set_cfg "tmux:\n  default_session:${value}\n  default_split: horizontal\n"
    out="$(run_setup)"
    assert_contains "probe: $label prompts and configures the default" \
        "tmux default_session configured: aitasks" "$out"
    assert_eq "probe: $label now reads back as aitasks" "0|aitasks" "$(raw_read "$FAKE")"
done

# --- probe: a configured value is left alone ------------------------------------

for value in mysess 'team#1'; do
    set_cfg "tmux:\n  default_session: ${value}\n"
    cp "$CFG" "$TMP/before"
    out="$(run_setup)"
    assert_contains "probe: '$value' counts as configured" \
        "already configured: ${value}" "$out"
    if cmp -s "$TMP/before" "$CFG"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: probe: '$value' config was modified"; fi
done

# --- probe: an unreadable value is reported and left byte-identical -------------

for spec in 'block scalar|tmux:\n  default_session: >-\n    x\n|block_scalar' \
            'flow mapping|tmux: {default_session: flowsess}\n|flow_mapping' \
            'tab before comment|tmux:\n  default_session: mysess\t# c\n|tab_or_control' \
            'unknown tag on the tmux header|tmux: !foo\n  default_session: mysess\n|invalid_block' \
            'DEL on another line (t1825)|tmux:\n  default_session: mysess\n# \0177\n|non_printable' \
            'invalid UTF-8 on another line (t1825)|tmux:\n  default_session: mysess\n# \0377\n|encoding'; do
    label="${spec%%|*}"; rest="${spec#*|}"; body="${rest%|*}"; shape="${rest##*|}"
    set_cfg "$body"
    cp "$CFG" "$TMP/before"
    out="$(run_setup)"
    assert_contains "probe: $label reports its shape" \
        "DEFAULT_SESSION_UNREADABLE:${shape}:" "$out"
    assert_contains "probe: $label is left untouched" "leaving it untouched" "$out"
    if cmp -s "$TMP/before" "$CFG"; then assert_record_pass; else
        assert_record_fail; echo "FAIL: probe: $label config was modified"; fi
done

# --- writer ----------------------------------------------------------------------

# check_writer <label> <config body> <name> <expected raw_read> [grep -F needle kept]
check_writer() {
    local label="$1" body="$2" name="$3" want="$4" keep="${5:-}"
    set_cfg "$body"
    run_writer "$name" || true
    assert_eq "writer: $label reads back" "$want" "$(raw_read "$FAKE")"
    if [[ -n "$keep" ]]; then
        assert_contains "writer: $label keeps unrelated content" "$keep" "$(cat "$CFG")"
    fi
    # Negative control: the old writer on the same fixture.
    set_cfg "$body"
    old_writer "$CFG" "$name" 2>/dev/null || true
    local old_read old_keep=1
    old_read="$(raw_read "$FAKE")"
    if [[ -n "$keep" ]] && ! grep -qF -- "$keep" "$CFG"; then old_keep=0; fi
    if [[ "$old_read" != "$want" || $old_keep -eq 0 ]]; then assert_record_pass; else
        assert_record_fail; echo "FAIL: writer control: the old writer also passes '$label' — fixture does not discriminate"; fi
}

check_writer "nested-only key" 'tmux:\n  syncer:\n    default_session: keep\n' \
    x "0|x" "    default_session: keep"
check_writer "name with a slash" 'tmux:\n  default_session: old\n' 'my/sess' "0|my/sess"
check_writer "name with an ampersand" 'tmux:\n  default_session: old\n' 'a&b' "0|a&b"
check_writer "name YAML reads as a bool" 'tmux:\n  default_session: old\n' yes "0|yes"
check_writer "name YAML reads as null" 'tmux:\n  default_session: old\n' null "0|null"
check_writer "4-space block" 'tmux:\n    default_split: h\n' four "0|four" "    default_split: h"

# Cases the old writer happened to handle: pinned for the new one, no control.
for spec in "hash in name|tmux:\n  default_session: old\n|team#1" \
            "apostrophe in name|tmux:\n  default_session: old\n|it's"; do
    label="${spec%%|*}"; rest="${spec#*|}"; body="${rest%|*}"; name="${rest##*|}"
    set_cfg "$body"
    run_writer "$name" || true
    assert_eq "writer: $label reads back" "0|$name" "$(raw_read "$FAKE")"
done

set_cfg 'other: 1\n'
run_writer appended || true
assert_eq "writer: no tmux block appends one" "0|appended" "$(raw_read "$FAKE")"
assert_contains "writer: no tmux block keeps the rest" "other: 1" "$(cat "$CFG")"

set_cfg 'tmux:\r\n  default_split: h\r\n'
run_writer crlf || true
assert_eq "writer: CRLF config reads back" "0|crlf" "$(raw_read "$FAKE")"
if grep -q $'default_session: crlf\r$' "$CFG" && ! grep -qv $'\r$' "$CFG"; then
    assert_record_pass
else
    assert_record_fail; echo "FAIL: writer: CRLF line endings were not preserved"
fi

set_cfg 'tmux:\n  default_session: old\n'
cp "$CFG" "$TMP/before"
rc=0; run_writer "a'b\"c" || rc=$?
assert_eq "writer: an unwritable name is refused" "1" "$rc"
if cmp -s "$TMP/before" "$CFG"; then assert_record_pass; else
    assert_record_fail; echo "FAIL: writer: an unwritable name modified the config"; fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
