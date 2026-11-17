#!/usr/bin/env bash
# test_codex_questions_registration.sh - lib/codex_questions_registration.sh,
# the shared "does this Codex config register the aitask_questions server?"
# check behind ait setup and the attended-Codex approval guard (t2324).
#
# One row per decision step of the helper:
#   0 registered / 1 confirmed absent / 2 inspection failed.
# The verdict must come from the interpreter's printed token, never its exit
# status (1 is Python's own failure code), and the no-parser prefilter must be
# sound for keys spelled through \u escapes.
#
# Run: bash tests/test_codex_questions_registration.sh

set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"
if [[ -z "$PY" ]] || ! "$PY" -c 'import tomllib' 2>/dev/null && ! "$PY" -c 'import tomli' 2>/dev/null; then
    echo "SKIP: no TOML-capable python interpreter"
    exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_codex_qreg_XXXXXX")"
trap 'chmod -R u+rwx "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT
. "$PROJECT_DIR/tests/lib/run_tmpdir.sh"
run_tmpdir_init test_codex_qreg "$TMP"

# shellcheck source=../.aitask-scripts/lib/codex_questions_registration.sh
. "$PROJECT_DIR/.aitask-scripts/lib/codex_questions_registration.sh"

# Interpreter stubs.
printf '#!/bin/sh\necho "Traceback (most recent call last):" >&2\nexit 1\n' > "$TMP/crash"
printf '#!/bin/sh\nexit 0\n' > "$TMP/silent"
printf '#!/bin/sh\ncat >/dev/null\necho REG:noparser\n' > "$TMP/noparser"
printf '#!/bin/sh\ncat >/dev/null\necho REG:no\nexit 1\n' > "$TMP/no_exit1"
chmod +x "$TMP/crash" "$TMP/silent" "$TMP/noparser" "$TMP/no_exit1"

# verdict <config> [<candidate>...] -> "<rc>"
verdict() { local rc=0; codex_questions_registration "$@" || rc=$?; echo "$rc"; }
cfg() { printf '%s' "$2" > "$TMP/$1.toml"; echo "$TMP/$1.toml"; }

echo "--- step 1: the file ---"
assert_eq "missing config: confirmed absent" "1" "$(verdict "$TMP/nope.toml" "$PY")"
mkdir -p "$TMP/dir.toml"
assert_eq "a directory: inspection failed" "2" "$(verdict "$TMP/dir.toml" "$PY")"
f="$(cfg unreadable $'[mcp_servers.aitask_questions]\ncommand = "x"\n')"
chmod 000 "$f"
if [[ -r "$f" ]]; then
    echo "SKIP: unreadable-file row (running as a user that can read mode 000)"
else
    assert_eq "unreadable config: inspection failed" "2" "$(verdict "$f" "$PY")"
    codex_questions_registration "$f" "$PY"
    assert_contains "unreadable config: reason names it" "unreadable" "$CODEX_QUESTIONS_REG_REASON"
fi
chmod 600 "$f"
# A failed stat is not absence: behind an unsearchable directory the file may
# exist. Absence is proven only through a searchable (or non-directory) parent.
assert_eq "missing parent directory: confirmed absent" "1" "$(verdict "$TMP/nodir/sub/config.toml" "$PY")"
: > "$TMP/plainfile"
assert_eq "parent is a regular file: confirmed absent" "1" "$(verdict "$TMP/plainfile/config.toml" "$PY")"
mkdir -p "$TMP/locked/.codex"
printf '[mcp_servers."aitask_questions"]\ncommand = "x"\n' > "$TMP/locked/.codex/config.toml"
chmod 000 "$TMP/locked/.codex"
if [[ -x "$TMP/locked/.codex" ]]; then
    echo "SKIP: unsearchable-parent rows (running as a user that can search mode 000)"
else
    assert_eq "unsearchable parent: inspection failed, not absent" "2" \
        "$(verdict "$TMP/locked/.codex/config.toml" "$PY")"
    codex_questions_registration "$TMP/locked/.codex/config.toml" "$PY"
    assert_contains "unsearchable parent: reason names it" "cannot search the directory" "$CODEX_QUESTIONS_REG_REASON"
    assert_eq "missing file below an unsearchable grandparent: cannot tell" "2" \
        "$(verdict "$TMP/locked/.codex/sub/config.toml" "$PY")"
fi
chmod 700 "$TMP/locked/.codex"
# Symlinked parents: -d cannot tell "not a directory" from "behind an
# unsearchable directory", so an unresolved link is followed, never trusted.
mkdir -p "$TMP/sym/proj" "$TMP/sym/private/codex" "$TMP/sym/open/codex" "$TMP/sym/dang"
printf '[mcp_servers."aitask_questions"]\ncommand = "x"\n' > "$TMP/sym/private/codex/config.toml"
printf '[mcp_servers."aitask_questions"]\ncommand = "x"\n' > "$TMP/sym/open/codex/config.toml"
ln -s ../private/codex "$TMP/sym/proj/hidden"
ln -s ../open/codex "$TMP/sym/proj/visible"
ln -s ../nowhere/codex "$TMP/sym/proj/dangling"
ln -s loop "$TMP/sym/proj/loop"
assert_eq "symlinked parent, reachable target: registered" "0" "$(verdict "$TMP/sym/proj/visible/config.toml" "$PY")"
assert_eq "dangling symlinked parent: confirmed absent" "1" "$(verdict "$TMP/sym/proj/dangling/config.toml" "$PY")"
assert_eq "symlink loop parent: cannot tell" "2" "$(verdict "$TMP/sym/proj/loop/config.toml" "$PY")"
chmod 000 "$TMP/sym/private"
if [[ -x "$TMP/sym/private" ]]; then
    echo "SKIP: symlink-through-unsearchable rows (running as a user that can search mode 000)"
else
    assert_eq "symlinked parent through an unsearchable dir: inspection failed, not absent" "2" \
        "$(verdict "$TMP/sym/proj/hidden/config.toml" "$PY")"
fi
chmod 755 "$TMP/sym/private"

echo "--- step 2: the literal header needs no interpreter ---"
f="$(cfg literal $'[mcp_servers.aitask_questions]\ncommand = "x"\n')"
assert_eq "literal table, no candidates: registered" "0" "$(verdict "$f")"

echo "--- step 3: sound no-parser prefilter ---"
f="$(cfg other $'model = "m"\n\n[mcp_servers.other]\ncommand = "o"\n')"
assert_eq "server not named, no candidates: confirmed absent" "1" "$(verdict "$f")"
assert_eq "server not named, crashing candidate: confirmed absent" "1" "$(verdict "$f" "$TMP/crash")"
f="$(cfg named $'[mcp_servers."aitask_questions"]\ncommand = "x"\n')"
assert_eq "named, no candidates: inspection failed" "2" "$(verdict "$f")"
codex_questions_registration "$f"
assert_contains "named, no candidates: reason says no parser" "no working TOML parser" "$CODEX_QUESTIONS_REG_REASON"
# The quoted key spells its final s as a \u0073 escape, so the literal
# substring is absent: the prefilter must still hand it to the parser. The
# backslash is passed as a printf ARGUMENT (BS) so no tool or editor along
# the way can decode the escape into a plain s.
BS=$(printf '\134')
f="$TMP/escaped.toml"
printf '[mcp_servers."aitask_question%su0073"]\ncommand = "x"\n' "$BS" > "$f"
grep -q 'aitask_questions' "$f"
assert_eq "escaped key fixture really lacks the literal name" "1" "$?"
assert_eq "\\u-escaped quoted key: registered" "0" "$(verdict "$f" "$PY")"
assert_eq "\\u-escaped quoted key, no candidates: inspection failed (not absent)" "2" "$(verdict "$f")"

echo "--- step 4: parsed spellings and token-only verdicts ---"
f="$(cfg quoted $'[mcp_servers."aitask_questions"]\ncommand = "x"\n')"
assert_eq "quoted table: registered" "0" "$(verdict "$f" "$PY")"
f="$(cfg dotted $'model = "m"\nmcp_servers.aitask_questions.command = "x"\n')"
assert_eq "dotted keys: registered" "0" "$(verdict "$f" "$PY")"
f="$(cfg inline $'mcp_servers = { aitask_questions = { command = "x" } }\n')"
assert_eq "inline table: registered" "0" "$(verdict "$f" "$PY")"
f="$(cfg commented $'# [mcp_servers."aitask_questions"]\nx = 1\n')"
assert_eq "commented-out table: confirmed absent" "1" "$(verdict "$f" "$PY")"
f="$(cfg invalid $'[mcp_servers."aitask_questions"\nthis is = = not toml\n')"
assert_eq "invalid TOML: confirmed absent (Codex starts nothing)" "1" "$(verdict "$f" "$PY")"
f="$(cfg quoted2 $'[mcp_servers."aitask_questions"]\ncommand = "x"\n')"
assert_eq "crashing candidate first: falls back to a working one" "0" "$(verdict "$f" "$TMP/crash" "$PY")"
assert_eq "silent exit-0 candidate is no verdict: falls back" "0" "$(verdict "$f" "$TMP/silent" "$PY")"
assert_eq "noparser candidate: falls back" "0" "$(verdict "$f" "$TMP/noparser" "$PY")"
assert_eq "missing candidate is skipped" "0" "$(verdict "$f" "$TMP/does-not-exist" "" "$PY")"
assert_eq "the token decides, not the exit status" "1" "$(verdict "$f" "$TMP/no_exit1" "$PY")"

echo "--- step 5: no candidate produced a verdict ---"
assert_eq "only failing candidates: inspection failed" "2" \
    "$(verdict "$f" "$TMP/crash" "$TMP/silent" "$TMP/noparser")"
codex_questions_registration "$f" "$TMP/crash" "$TMP/silent"
assert_contains "the reason lists what was tried" "$TMP/crash, $TMP/silent" "$CODEX_QUESTIONS_REG_REASON"

echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "All tests PASSED"
