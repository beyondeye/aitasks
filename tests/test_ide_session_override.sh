#!/usr/bin/env bash
# test_ide_session_override.sh - `ait ide --session` and the bash session
# resolver's unreadable-default_session contract (t1811).
#
#   * _tmux_bootstrap_session_for prints a --session override verbatim, so an
#     option-like name (-n, -e, -E, -neE) survives; bash's echo used to print
#     nothing for those, and `ait ide --session -n` resolved an empty session.
#   * aitask_ide.sh itself carries the override through: driven for real, with
#     a stub `tmux` first on PATH answering the one query the script makes
#     before it refuses to nest ("Already inside tmux session ..."). That
#     refusal prints the resolved session — no production seam is needed.
#   * An unreadable tmux.default_session: `ait ide` warns (structured sentinel)
#     and uses "aitasks"; `tmux_bootstrap.sh --create-only` (frozen-agent
#     restore) refuses with exit 44 before any tmux call; ensure mode falls back.
#
# No real tmux server is touched: every tmux call resolves to the stub
# (AIT_NO_SYSTEMD_RUN keeps the spawn off `systemd-run --user`, whose tmux
# would come from the user manager's PATH), on an isolated socket name, with
# the project registry redirected to a temp file.
#
# Run: bash tests/test_ide_session_override.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

LIB="$PROJECT_DIR/.aitask-scripts/lib/tmux_bootstrap.sh"
IDE="$PROJECT_DIR/.aitask-scripts/aitask_ide.sh"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/t1811_ide_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

STUB_BIN="$TMP/bin"
mkdir -p "$STUB_BIN"
cat > "$STUB_BIN/tmux" <<'STUB'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$STUB_LOG"
case " $* " in
    *" display-message "*) echo "${STUB_CURRENT_SESSION:-other}"; exit 0 ;;
    *" has-session "*) exit 1 ;;
    *" new-session "*) exit 0 ;;
esac
exit 1
STUB
chmod +x "$STUB_BIN/tmux"

# make_project <dir> <config body>
make_project() {
    mkdir -p "$1/aitasks/metadata"
    printf '%b' "$2" > "$1/aitasks/metadata/project_config.yaml"
}

# isolated <cmd...> — run with the stub tmux and every real-server path cut off.
isolated() {
    env -u TMUX PATH="$STUB_BIN:$PATH" STUB_LOG="$STUB_LOG" \
        AIT_NO_SYSTEMD_RUN=1 AITASKS_TMUX_SOCKET="t1811-test-$$" TMUX_TMPDIR="$TMP" \
        AITASKS_PROJECTS_INDEX="$TMP/projects.yaml" "$@"
}

# --- 1. library: the override is printed verbatim -----------------------------

make_project "$TMP/plain" 'tmux:\n  default_session: configured\n'

for v in -n -e -E -neE "a b"; do
    got="$(bash -c 'source "$1"; _tmux_bootstrap_session_for "$2" "$3"' _ "$LIB" "$TMP/plain" "$v")"
    assert_eq "session_for keeps override '$v' verbatim" "$v" "$got"
done

got="$(bash -c 'source "$1"; _tmux_bootstrap_session_for "$2" ""' _ "$LIB" "$TMP/plain")"
assert_eq "an empty override falls back to tmux.default_session" "configured" "$got"

# --- 2. the real entry point carries --session -n -----------------------------

STUB_LOG="$TMP/ide_override.log"
rc=0
err="$(cd "$TMP/plain" && isolated TMUX="$TMP/ait,1,0" AITASKS_TMUX_SOCKET=ait \
    bash "$IDE" --session -n 2>&1 >/dev/null)" || rc=$?
assert_eq "ait ide refuses to nest (exit 1)" "1" "$rc"
assert_contains "ait ide resolved --session -n to '-n'" \
    "configured session is '-n'" "$err"
assert_contains "the stub answered the nesting probe (the check really ran)" \
    "display-message" "$(cat "$STUB_LOG" 2>/dev/null)"

# --- 2b. --session refuses tmux target separators (t1825) ---------------------

for v in a.b a:b .lead trail:; do
    rc=0
    bash -c 'source "$1"; _tmux_bootstrap_session_name_ok "$2"' _ "$LIB" "$v" || rc=$?
    assert_eq "session_name_ok rejects '$v'" "1" "$rc"
done
for v in ok -n "a b" my_proj-2; do
    rc=0
    bash -c 'source "$1"; _tmux_bootstrap_session_name_ok "$2"' _ "$LIB" "$v" || rc=$?
    assert_eq "session_name_ok accepts '$v'" "0" "$rc"
done

for v in a.b a:b; do
    STUB_LOG="$TMP/ide_illegal.log"
    : > "$STUB_LOG"
    rc=0
    err="$(cd "$TMP/plain" && isolated TMUX="$TMP/ait,1,0" AITASKS_TMUX_SOCKET=ait \
        bash "$IDE" --session "$v" 2>&1 >/dev/null)" || rc=$?
    assert_eq "ait ide --session '$v' exits 1" "1" "$rc"
    assert_contains "ait ide --session '$v' names the invalid chars" \
        "Session name contains invalid chars (. or :): $v" "$err"
    assert_not_contains "ait ide --session '$v' never reaches the nesting check" \
        "configured session is" "$err"
    assert_eq "ait ide --session '$v' makes no tmux call" "" "$(cat "$STUB_LOG")"
done

# --- 2c. a CONFIGURED illegal name is refused by the readers too (t1828) ------
#
# t1825 covered only the name a user types. A hand-edited `default_session: a.b`
# was read by every resolver and handed to `tmux new-session -s a.b`, creating a
# session that can never be addressed.

make_project "$TMP/dotted" 'tmux:\n  default_session: a.b\n'

rc=0
raw_err="$(bash -c 'source "$1"; _tmux_bootstrap_default_session_raw "$2"' \
    _ "$LIB" "$TMP/dotted" 2>&1 >/dev/null)" || rc=$?
assert_eq "raw reader exits 2 on a configured illegal name" "2" "$rc"
assert_contains "raw reader reports the illegal_tmux_name sentinel" \
    "DEFAULT_SESSION_UNREADABLE:illegal_tmux_name:" "$raw_err"
assert_contains "the warning says the name cannot be addressed" \
    "is a name tmux cannot address" "$raw_err"
assert_not_contains "the warning does not claim a YAML-form problem" \
    "single-line plain or quoted value" "$raw_err"

got="$(bash -c 'source "$1"; _tmux_bootstrap_resolve_session "$2"' _ "$LIB" "$TMP/dotted" 2>/dev/null)"
assert_eq "resolve_session falls back to 'aitasks'" "aitasks" "$got"

# Control: the same reader still returns a legal name with other punctuation.
make_project "$TMP/legal" 'tmux:\n  default_session: my_proj-2\n'
got="$(bash -c 'source "$1"; _tmux_bootstrap_resolve_session "$2"' _ "$LIB" "$TMP/legal" 2>/dev/null)"
assert_eq "resolve_session keeps a legal name" "my_proj-2" "$got"

STUB_LOG="$TMP/ide_dotted.log"
: > "$STUB_LOG"
rc=0
err="$(cd "$TMP/dotted" && isolated TMUX="$TMP/ait,1,0" AITASKS_TMUX_SOCKET=ait \
    bash "$IDE" 2>&1 >/dev/null)" || rc=$?
assert_eq "ait ide on a dotted config still reaches the nesting refusal" "1" "$rc"
assert_contains "ait ide falls back to 'aitasks', not 'a.b'" \
    "configured session is 'aitasks'" "$err"

# --create-only must refuse rather than create an unaddressable session.
STUB_LOG="$TMP/create_only_dotted.log"
: > "$STUB_LOG"
rc=0
out="$(isolated bash "$LIB" --create-only "$TMP/dotted" 2>"$TMP/create_only_dotted.err")" || rc=$?
err="$(cat "$TMP/create_only_dotted.err")"
assert_eq "--create-only exits 44 on a configured illegal name" "44" "$rc"
assert_contains "--create-only reports the refusal" \
    "BOOTSTRAP_FAILED:default_session_unreadable:illegal_tmux_name" "$err"
assert_not_contains "--create-only claims no creation" "BOOTSTRAP_CREATED:" "$out"
assert_eq "--create-only makes no tmux call at all" "" "$(cat "$STUB_LOG")"

# Control: ensure mode falls back and creates `aitasks`, never `a.b`.
STUB_LOG="$TMP/ensure_dotted.log"
: > "$STUB_LOG"
rc=0
isolated bash "$LIB" "$TMP/dotted" >/dev/null 2>"$TMP/ensure_dotted.err" || rc=$?
assert_eq "ensure mode exits 0 on a dotted config" "0" "$rc"
assert_contains "ensure mode creates the fallback session" \
    "new-session" "$(cat "$STUB_LOG")"
assert_not_contains "ensure mode never names 'a.b' to tmux" "a.b" "$(cat "$STUB_LOG")"

# --- 3. ait ide with an unreadable default_session ----------------------------

make_project "$TMP/block" 'tmux:\n  default_session: >-\n    blocksess\n'
STUB_LOG="$TMP/ide_block.log"
rc=0
err="$(cd "$TMP/block" && isolated TMUX="$TMP/ait,1,0" AITASKS_TMUX_SOCKET=ait \
    bash "$IDE" 2>&1 >/dev/null)" || rc=$?
assert_eq "ait ide on an unreadable config still reaches the nesting refusal" "1" "$rc"
assert_contains "ait ide reports the structured sentinel" \
    "DEFAULT_SESSION_UNREADABLE:block_scalar:" "$err"
assert_contains "ait ide falls back to 'aitasks', not the '>-' indicator" \
    "configured session is 'aitasks'" "$err"

# --- 4. --create-only refuses before any tmux call ----------------------------

STUB_LOG="$TMP/create_only_block.log"
: > "$STUB_LOG"
rc=0
out="$(isolated bash "$LIB" --create-only "$TMP/block" 2>"$TMP/create_only_block.err")" || rc=$?
err="$(cat "$TMP/create_only_block.err")"
assert_eq "--create-only exits 44 on an unreadable default_session" "44" "$rc"
assert_contains "--create-only reports the sentinel" \
    "DEFAULT_SESSION_UNREADABLE:block_scalar:" "$err"
assert_contains "--create-only reports the refusal" \
    "BOOTSTRAP_FAILED:default_session_unreadable:block_scalar" "$err"
assert_not_contains "--create-only claims no creation" "BOOTSTRAP_CREATED:" "$out"
assert_eq "--create-only makes no tmux call at all" "" "$(cat "$STUB_LOG")"

# Control: ensure mode on the same config falls back and creates `aitasks`.
STUB_LOG="$TMP/ensure_block.log"
: > "$STUB_LOG"
rc=0
isolated bash "$LIB" "$TMP/block" >/dev/null 2>"$TMP/ensure_block.err" || rc=$?
err="$(cat "$TMP/ensure_block.err")"
assert_eq "ensure mode exits 0 on the same config" "0" "$rc"
assert_contains "ensure mode still reports the sentinel" \
    "DEFAULT_SESSION_UNREADABLE:block_scalar:" "$err"
assert_contains "ensure mode says it uses 'aitasks'" \
    "using tmux session 'aitasks' instead" "$err"
assert_contains "ensure mode creates the fallback session" \
    "new-session -d -s aitasks" "$(cat "$STUB_LOG")"

# Control: --create-only on a readable config creates and claims it.
STUB_LOG="$TMP/create_only_plain.log"
: > "$STUB_LOG"
rc=0
out="$(isolated bash "$LIB" --create-only "$TMP/plain" 2>"$TMP/create_only_plain.err")" || rc=$?
assert_eq "--create-only on a readable config exits 0" "0" "$rc"
assert_contains "--create-only on a readable config claims its session" \
    "BOOTSTRAP_CREATED:configured" "$out"
assert_not_contains "a readable config carries no sentinel" \
    "DEFAULT_SESSION_UNREADABLE" "$(cat "$TMP/create_only_plain.err")"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -gt 0 ]]; then
    exit 1
fi
echo "ALL TESTS PASSED"
