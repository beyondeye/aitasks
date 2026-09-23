#!/usr/bin/env bash
# test_aitasks_home.sh — the per-user framework root ($AITASKS_HOME), t1852_1 (M1.1).
#
# Pins the three things M1.1 promises: `lib/aitasks_home.sh` resolves the root
# (default `$HOME/.aitasks`, env override, `aitasks_engine_dir`, the home lock);
# `ait setup` creates `$AITASKS_HOME/engine/` (0755) from main() and prints the
# `AITASKS_HOME:<path>` token beside the `Python venv:` summary line; and no
# framework script OF THIS FEATURE names the legacy per-user root.
#
# --- Grep guard scope (documented on purpose — a guard that overclaims is
# worse than one with a known boundary) --------------------------------------
#   * FEATURE_FILES — whole files owned by the test-map feature (the M1/M5/M8
#     bash pieces the proposal names). A path that has not landed yet is
#     reported `SKIP (not landed)` on stderr and not counted.
#   * FEATURE_FUNCTIONS — feature-owned functions inside SHARED files, given as
#     `<file>:<function>` and extracted with awk (`^name() {` … `^}`), so the
#     legitimate legacy-tenant lines elsewhere in that file (setup's venv, bin,
#     python, uv, dev_tier) neither trip the guard nor shield anything.
#     M1.5 registers `install_engine_binary` / `report_testmap_state` here.
#   * Exemptions are PER LINE, never per file: a trailing
#     `# legacy-root-ok: <reason>` marker exempts that one line — the sanctioned
#     way for M1.6's migration code to name the root it moves (its `engine`
#     entry and `destination-exists:engine` preflight included). There is no
#     file allowlist, so an unrelated legacy-path line in a mixed-purpose file
#     still fails. Pure-comment lines are dropped first.
#   * Pattern: `$HOME/.aitask`, `${HOME}/.aitask`, `~/.aitask` followed by `/`,
#     a quote, whitespace or end of line — so `.aitask-scripts`, `.aitask-data`
#     and `.aitask-testmap` never match.
#   * NOT scanned: `tests/`, docs, Python, and the legacy tenants themselves
#     (`aitask_path.sh`, `python_resolve.sh`, the rest of `aitask_setup.sh`).
#
# Run: bash tests/test_aitasks_home.sh
#
# shellcheck disable=SC2016  # the single-quoted `bash -c` snippets and fixture
#                            # lines below must NOT expand in this shell.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

LIB="$PROJECT_DIR/.aitask-scripts/lib/aitasks_home.sh"
SETUP="$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
mkdir -p "$SCRATCH/home"

# Octal mode of a path. `stat -c` is GNU, `stat -f` is BSD.
dir_mode() {
    stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || true
}

# Every scenario runs in a SUBPROCESS with an explicit environment; the
# assertions run here, in the main shell, so the counters are in-process.
# lib_eval <snippet> — source the lib in a fresh bash and run <snippet>.
# Callers set HOME / AITASKS_HOME on the command line.
lib_eval() {
    bash -c '. "$1" && eval "$2"' _ "$LIB" "$1"
}

# --- T1–T3: root resolution -------------------------------------------------
out="$(env -u AITASKS_HOME HOME="$SCRATCH/home" bash -c '. "$1"; printf "%s\n" "$AITASKS_HOME"' _ "$LIB")"
assert_eq "T1 default root is \$HOME/.aitasks" "$SCRATCH/home/.aitasks" "$out"

out="$(HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" lib_eval 'printf "%s\n" "$AITASKS_HOME"')"
assert_eq "T2 env override is honoured" "$SCRATCH/x" "$out"

out="$(HOME="$SCRATCH/home" AITASKS_HOME='' lib_eval 'printf "%s\n" "$AITASKS_HOME"')"
assert_eq "T3 empty override falls back to the default" "$SCRATCH/home/.aitasks" "$out"

# --- T4: the home lock ------------------------------------------------------
out="$(HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" lib_eval 'printf "%s\n" "$AITASKS_HOME_LOCK"')"
assert_eq "T4 AITASKS_HOME_LOCK is <root>/.home.lock" "$SCRATCH/x/.home.lock" "$out"

# --- T5: aitasks_engine_dir -------------------------------------------------
out="$(HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" lib_eval 'aitasks_engine_dir 1.2.3')"
assert_eq "T5 versioned slot, no trailing slash" "$SCRATCH/x/engine/v1.2.3" "$out"

out="$(HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" lib_eval 'aitasks_engine_dir dev')"
assert_eq "T5 dev slot" "$SCRATCH/x/engine/dev" "$out"

out="$(HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" lib_eval 'aitasks_engine_dir 2>"'"$SCRATCH"'/err"; echo "rc=$?"')"
assert_eq "T5 empty arg: rc=2, nothing on stdout" "rc=2" "$out"
assert_contains "T5 empty arg: usage on stderr" "usage: aitasks_engine_dir" "$(cat "$SCRATCH/err")"

# --- T6: double-source guard ------------------------------------------------
out="$(HOME="$SCRATCH/home" AITASKS_HOME="$SCRATCH/x" bash -c '
    . "$1"; a="$AITASKS_HOME|$AITASKS_HOME_LOCK"
    . "$1"; b="$AITASKS_HOME|$AITASKS_HOME_LOCK"
    [[ "$a" == "$b" ]] && declare -F aitasks_engine_dir >/dev/null && echo SAME' _ "$LIB")"
assert_eq "T6 sourcing twice is a no-op" "SAME" "$out"

# --- T7: setup_aitasks_home() ----------------------------------------------
# setup_fn <AITASKS_HOME> — source setup without running main, call the step.
setup_fn() {
    HOME="$SCRATCH/home" AITASKS_HOME="$1" bash -c '
        umask 077
        source "$1" --source-only
        set +euo pipefail
        setup_aitasks_home' _ "$SETUP" 2>&1
}
out="$(setup_fn "$SCRATCH/x")"
assert_dir_exists "T7 engine root created" "$SCRATCH/x/engine"
assert_eq "T7 engine root is 0755 even under umask 077" "755" "$(dir_mode "$SCRATCH/x/engine")"
assert_contains "T7 step prints the AITASKS_HOME: token" "AITASKS_HOME:$SCRATCH/x" "$out"

out="$(setup_fn "$SCRATCH/x")"
assert_contains "T7 re-run is idempotent and still prints the token" "AITASKS_HOME:$SCRATCH/x" "$out"

mkdir -p "$SCRATCH/w" && mkdir -m 700 "$SCRATCH/w/engine"
setup_fn "$SCRATCH/w" >/dev/null
assert_eq "T7 an existing engine dir is never chmod'ed" "700" "$(dir_mode "$SCRATCH/w/engine")"

# --- T8: main() wiring, bounded ---------------------------------------------
# Every function setup defines is stubbed as `return 1` — which also makes the
# opt-in tier probes answer "no" — except main, the step under test and the
# four loggers. Nothing in main() consumes a stub's output, so the run is
# offline and prompt-free. $2 names one more function to stub (negative control).
run_main() {
    HOME="$SCRATCH/home" AITASKS_HOME="$1" bash -c '
        source "$1" --source-only
        set +euo pipefail
        extra="$2"
        for fn in $(compgen -A function); do
            case "$fn" in
                main|setup_aitasks_home|info|success|warn|die)
                    [[ "$fn" == "$extra" ]] || continue ;;
            esac
            eval "$fn() { return 1; }"
        done
        main' _ "$SETUP" "${2:-}" 2>&1
}
out="$(run_main "$SCRATCH/y")"
assert_dir_exists "T8 main() creates the engine root" "$SCRATCH/y/engine"
assert_eq "T8 engine root from main() is 0755" "755" "$(dir_mode "$SCRATCH/y/engine")"
token_count="$(printf '%s\n' "$out" | grep -c "AITASKS_HOME:$SCRATCH/y")"
assert_eq "T8 token printed twice (step + summary)" "2" "$token_count"
n_venv="$(printf '%s\n' "$out" | grep -n 'Python venv:' | head -n1 | cut -d: -f1)"
n_home="$(printf '%s\n' "$out" | grep -n 'AITASKS_HOME:' | tail -n1 | cut -d: -f1)"
assert_eq "T8 summary AITASKS_HOME: is the line right after Python venv:" "$((n_venv + 1))" "$n_home"

run_main "$SCRATCH/z" setup_aitasks_home >/dev/null
assert_dir_not_exists "T8 negative: with the step stubbed, main() creates nothing" "$SCRATCH/z/engine"

# --- T9: the no-legacy-root grep guard ---------------------------------------
FEATURE_FILES=(
    ".aitask-scripts/lib/aitasks_home.sh"            # M1.1 — this lib
    ".aitask-scripts/aitask_testmap.sh"              # M1.4 — the shim
    ".aitask-scripts/lib/platform_detect.sh"         # M1.4
    ".aitask-scripts/aitask_engine.sh"               # M1.5 / M1.6 — mixed: mark migration lines
    ".aitask-scripts/aitask_test.sh"                 # M5.1
    ".aitask-scripts/aitask_gate_testmap_check.sh"   # M8.2
)
FEATURE_FUNCTIONS=(
    "aitask_setup.sh:setup_aitasks_home"             # M1.1 (M1.5 adds its two)
)
LEGACY_RE='(\$HOME|\$\{HOME\}|~)/\.aitask(/|["'"'"'[:space:]]|$)'
MARKER_RE='#[[:space:]]*legacy-root-ok:'

# filter_hits LABEL — stdin is "<lineno>:<text>"; emit "LABEL:<lineno>:<text>"
# for every line naming the legacy root, minus pure comments and marked lines.
filter_hits() {
    local label="$1"
    grep -E "$LEGACY_RE" \
        | grep -vE '^[0-9]+:[[:space:]]*#' \
        | grep -vE "$MARKER_RE" \
        | sed "s|^|$label:|"
}

# scan_root ROOT — hits for every feature file and feature function under ROOT.
scan_root() {
    local root="$1" rel f entry file fn body
    for rel in "${FEATURE_FILES[@]}"; do
        f="$root/$rel"
        [[ -f "$f" ]] || { echo "SKIP (not landed): $rel" >&2; continue; }
        awk '{print NR":"$0}' "$f" | filter_hits "$rel"
    done
    for entry in "${FEATURE_FUNCTIONS[@]}"; do
        file="${entry%%:*}"; fn="${entry#*:}"; f="$root/.aitask-scripts/$file"
        [[ -f "$f" ]] || { echo "SKIP (not landed): $entry" >&2; continue; }
        body="$(awk -v fn="$fn" '
            $0 ~ "^"fn"\\(\\) \\{" {p=1}
            p {print NR":"$0}
            p && /^}/ {p=0}' "$f")"
        # A registered function that is not in the file is a coverage hole,
        # not a clean result — a rename must not silently drop the scan.
        [[ -n "$body" ]] || { echo "MISSING_FUNCTION:$entry"; continue; }
        printf '%s\n' "$body" | filter_hits "$file::$fn()"
    done
}

violations="$(scan_root "$PROJECT_DIR")"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: T9 legacy per-user root named by a script of this feature:"
    printf '  LEGACY ROOT: %s\n' "$violations"
    echo "  -> resolve the path through lib/aitasks_home.sh (\$AITASKS_HOME), or,"
    echo "     if the line genuinely operates on the legacy root (migration),"
    echo "     mark THAT line with '# legacy-root-ok: <reason>'."
fi

# Negative controls in a temp tree.
T="$SCRATCH/tree/.aitask-scripts"
mkdir -p "$T/lib"
# (a) rogue feature file → flagged
printf '%s\n' '#!/usr/bin/env bash' 'bin="$HOME/.aitask/bin"' >"$T/aitask_testmap.sh"
# (b) the same line, marked → not flagged
printf '%s\n' '#!/usr/bin/env bash' 'bin="$HOME/.aitask/bin"  # legacy-root-ok: test control' >"$T/lib/platform_detect.sh"
# (c) mixed-purpose file: marked migration line + UNMARKED engine line → one hit
printf '%s\n' '#!/usr/bin/env bash' \
    'ln -s "$AITASKS_HOME" ~/.aitask # legacy-root-ok: migration leaves the symlink' \
    'old="$HOME/.aitask/engine/v1"' >"$T/aitask_engine.sh"
# (d) function scope: legacy ref outside the function is out of scope, inside is in
printf '%s\n' '#!/usr/bin/env bash' 'VENV_DIR="$HOME/.aitask/venv"' \
    'setup_aitasks_home() {' '    x="$HOME/.aitask/x"' '}' \
    'other() {' '    y="$HOME/.aitask/y"' '}' >"$T/aitask_setup.sh"
# (e) comment-only mention and a .aitask-scripts path → not flagged
printf '%s\n' '#!/usr/bin/env bash' '# see ~/.aitask/ for the legacy tenants' \
    'd="$HOME/.aitask-scripts/x"; e="$HOME/.aitask-data"' >"$T/aitask_test.sh"
# (f) the ${HOME} spelling → flagged
printf '%s\n' '#!/usr/bin/env bash' 'uv="${HOME}/.aitask/uv"' >"$T/aitask_gate_testmap_check.sh"

neg="$(scan_root "$SCRATCH/tree" 2>/dev/null)"
assert_contains "T9(a) rogue feature file is flagged" "aitask_testmap.sh:2:" "$neg"
assert_not_contains "T9(b) a marked line is not flagged" "platform_detect.sh" "$neg"
engine_hits="$(printf '%s\n' "$neg" | grep -c 'aitask_engine.sh:')"
assert_eq "T9(c) mixed file: exactly one hit" "1" "$engine_hits"
assert_contains "T9(c) …and it is the unmarked engine line" "aitask_engine.sh:3:" "$neg"
setup_hits="$(printf '%s\n' "$neg" | grep -c 'aitask_setup.sh::setup_aitasks_home():')"
assert_eq "T9(d) function scope: exactly one hit" "1" "$setup_hits"
assert_contains "T9(d) …the line inside the function" "setup_aitasks_home():4:" "$neg"
assert_not_contains "T9(d) …never the tenant line outside it" ":2:VENV_DIR" "$neg"
assert_not_contains "T9(e) comment / .aitask-scripts lines are not flagged" "aitask_test.sh" "$neg"
assert_contains "T9(f) the \${HOME} spelling is flagged" "aitask_gate_testmap_check.sh:2:" "$neg"
# A registered function that vanished must surface, not read as clean.
rm "$T/aitask_setup.sh"; printf '%s\n' '#!/usr/bin/env bash' 'noop() { :; }' >"$T/aitask_setup.sh"
neg2="$(scan_root "$SCRATCH/tree" 2>/dev/null)"
assert_contains "T9(g) a missing registered function is reported" "MISSING_FUNCTION:aitask_setup.sh:setup_aitasks_home" "$neg2"

# --- T10: the lib itself never spells the legacy path --------------------------
assert_eq "T10 lib/aitasks_home.sh has no '.aitask/'" "0" "$(grep -c '\.aitask/' "$LIB")"

# --- Summary -----------------------------------------------------------------
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
