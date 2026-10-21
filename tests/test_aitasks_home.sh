#!/usr/bin/env bash
# test_aitasks_home.sh — the per-user framework root ($AITASKS_HOME), t1852_1 (M1.1),
# and the framework home report / migration verb, t1852_6 (M1.6).
#
# Pins the three things M1.1 promises: `lib/aitasks_home.sh` resolves the root
# (default `$HOME/.aitasks`, env override, `aitasks_engine_dir`, the home lock);
# `ait setup` creates `$AITASKS_HOME/engine/` (0755) from main() and prints the
# `AITASKS_HOME:<path>` token beside the `Python venv:` summary line; and no
# framework script OF THIS FEATURE names the legacy per-user root.
#
# M1.6 (cases H*): `ait engine home` reports both roots; `--migrate` runs a
# preflight that refuses with both trees byte-identical, moves the known tenant
# set, leaves the compatibility symlink, rolls back on any failed step or
# catchable signal, and reports a blocked rollback precisely.
#
# t1939 (cases I*, H-I2): `ait setup` migrates by default. The I cases run the
# INSTALLED tree's setup main() (after a real install.sh --dir) under setup's
# own `set -euo pipefail`, across the admission matrix, both opt-outs and every
# exit class of the verb, including a TERM to setup's whole process group
# (I13). install.sh never migrates; it only hints (H-I2).
# Every case runs on a scratch HOME — never the real legacy root.
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
# u+rwx first: H26 makes a directory unlistable, and an abort mid-case must
# not leave it behind.
trap 'chmod -R u+rwx "$SCRATCH" 2>/dev/null; rm -rf "$SCRATCH"' EXIT
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
# offline and prompt-free. $2 names one more function to stub (negative control);
# $3 names one more NOT to stub (the S cases keep report_home_legacy).
run_main() {
    HOME="${RUN_MAIN_HOME:-$SCRATCH/home}" AITASKS_HOME="$1" bash -c '
        source "$1" --source-only
        set +euo pipefail
        extra="$2" keep="$3"
        for fn in $(compgen -A function); do
            case "$fn" in
                main|setup_aitasks_home|info|success|warn|die)
                    [[ "$fn" == "$extra" ]] || continue ;;
            esac
            [[ -n "$keep" && "$fn" == "$keep" ]] && continue
            eval "$fn() { return 1; }"
        done
        main' _ "$SETUP" "${2:-}" "${3:-}" 2>&1
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
    ".aitask-scripts/lib/engine_install.sh"          # M1.5 — staging, verify, slot lock, publish
    ".aitask-scripts/aitask_test.sh"                 # M5.1
    ".aitask-scripts/aitask_gate_testmap_check.sh"   # M8.2
)
FEATURE_FUNCTIONS=(
    "aitask_setup.sh:setup_aitasks_home"             # M1.1
    "aitask_setup.sh:install_engine_binary"          # M1.5
    "aitask_setup.sh:_install_engine_tiers"          # M1.5 — install_engine_binary's source tiers
    "aitask_setup.sh:report_testmap_state"           # M1.5
    "aitask_setup.sh:report_home_legacy"             # M1.6 — the HOME_LEGACY: hint
    "aitask_setup.sh:migrate_home_legacy"            # t1939 — setup-driven migration
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

# =============================================================================
# M1.6 — `ait engine home [--migrate]` (t1852_6). Every case below builds its
# own scratch HOME; none touches the invoking user's legacy root.
# =============================================================================
ENG="$PROJECT_DIR/.aitask-scripts/aitask_engine.sh"
PY3="$(command -v python3 || true)"
KNOWN_ALL="bin,dev_tier,engine,pypy_venv,python,update_check,uv,venv"
KNOWN_7="bin,dev_tier,pypy_venv,python,update_check,uv,venv"

# mklegacy <home> [--no-engine] — a legacy root holding every known tenant, in
# the shapes setup leaves: a REAL venv (when python3 can make one), the
# python/<ver>/bin/python3 symlink, the bin/python3 wrapper that execs the venv
# by its $HOME-relative path, and plain files for the rest.
REAL_VENV=0
mklegacy() {
    local h="$1" l="$1/.aitask"
    mkdir -p "$l/pypy_venv/bin" "$l/python/3.x/bin" "$l/bin" "$l/uv"
    if [[ -n "$PY3" ]] && "$PY3" -m venv --without-pip "$l/venv" >/dev/null 2>&1; then
        REAL_VENV=1
    else
        mkdir -p "$l/venv/bin"
        printf '#!/bin/sh\necho 42\n' >"$l/venv/bin/python"
        chmod +x "$l/venv/bin/python"
    fi
    printf '#!/bin/sh\necho pypy\n' >"$l/pypy_venv/bin/python"
    chmod +x "$l/pypy_venv/bin/python"
    [[ -n "$PY3" ]] && ln -s "$PY3" "$l/python/3.x/bin/python3"
    printf '#!/usr/bin/env bash\nexec "$HOME/.aitask/venv/bin/python" "$@"\n' >"$l/bin/python3"
    chmod +x "$l/bin/python3"
    printf 'uv-binary\n' >"$l/uv/uv"
    printf 'dev tier installed\n' >"$l/dev_tier"
    printf '1700000000 0.0.1\n' >"$l/update_check"
    if [[ "${2:-}" != --no-engine ]]; then
        mkdir -p "$l/engine/v0.0.1"
        printf 'old engine\n' >"$l/engine/v0.0.1/ait-testmap"
    fi
}

# tree_sig <path> — a portable byte-identity signature: every file's cksum,
# every link's target, every directory; ABSENT / LINK:<target> for the path
# itself. Two equal signatures mean the trees are byte-identical.
tree_sig() {
    local d="$1" p
    if [[ -L "$d" ]]; then echo "LINK:$(readlink "$d")"; return; fi
    [[ -e "$d" ]] || { echo ABSENT; return; }
    [[ -d "$d" ]] || { echo "F $(cksum <"$d")"; return; }
    # NUL-separated and %q-printed, so a name holding a newline is one entry.
    (cd "$d" || exit 1; find . -print0 | LC_ALL=C sort -z | while IFS= read -r -d '' p; do
        if [[ -L "$p" ]]; then printf 'L %q -> %q\n' "$p" "$(readlink "$p")"
        elif [[ -d "$p" ]]; then printf 'D %q\n' "$p"
        else printf 'F %q %s\n' "$p" "$(cksum <"$p")"; fi
    done)
}

# home_eng <home> <aitasks_home | -> [args...] — run the verb ("-" leaves
# AITASKS_HOME unset, exercising the default). Sets out (stdout), err, rc.
# HOME_ENV (array) adds extra environment, e.g. the test hook.
HOME_ENV=()
home_eng() {
    local h="$1" ah="$2"; shift 2
    local envs=(HOME="$h")
    [[ "$ah" != - ]] && envs+=(AITASKS_HOME="$ah")
    out="$(env -u AITASKS_HOME "${envs[@]}" ${HOME_ENV[@]+"${HOME_ENV[@]}"} \
        bash "$ENG" home "$@" 2>"$SCRATCH/home_err" </dev/null)"
    rc=$?
    err="$(cat "$SCRATCH/home_err")"
}

# hline <prefix> — the lines of $out starting with <prefix>.
hline() { printf '%s\n' "$out" | grep -- "^$1" || true; }

# mkhook <name> <body…> — a test-seam hook. It is called as `<point> [entry]`
# and sees HOOK_L (the legacy root) and HOOK_AH (the new root).
mkhook() {
    local f="$SCRATCH/hook_$1.sh"; shift
    { echo '#!/usr/bin/env bash'; printf '%s\n' "$@"; } >"$f"
    chmod +x "$f"
    printf '%s\n' "$f"
}

# no_lock <root> <label> — the home lock (and its guard) is gone after a run.
no_lock() {
    TOTAL=$((TOTAL + 1))
    if [[ -e "$1/.home.lock" || -e "$1/.home.lock.gc" ]]; then
        FAIL=$((FAIL + 1)); echo "FAIL: $2 — home lock left behind under $1"
    else
        PASS=$((PASS + 1))
    fi
}

# --- H1: report with no legacy root ------------------------------------------
H="$SCRATCH/h1"; mkdir -p "$H"
home_eng "$H" "$SCRATCH/ah1"
assert_exit_zero_rc "H1 report exits 0" "$rc"
assert_eq "H1 HOME_ROOT" "HOME_ROOT:$SCRATCH/ah1" "$(hline HOME_ROOT:)"
assert_eq "H1 HOME_LEGACY:none" "HOME_LEGACY:none" "$(hline HOME_LEGACY:)"
assert_eq "H1 HOME_SYMLINK:none" "HOME_SYMLINK:none" "$(hline HOME_SYMLINK:)"
assert_eq "H1 HOME_NEXT:none|no-legacy-root" "HOME_NEXT:none|no-legacy-root" "$(hline HOME_NEXT:)"

# --- H2: report on a populated legacy root changes nothing ------------------
H="$SCRATCH/h2"; mklegacy "$H"
sig="$(tree_sig "$H/.aitask")"
home_eng "$H" "$SCRATCH/ah2"
assert_exit_zero_rc "H2 report exits 0" "$rc"
assert_eq "H2 HOME_LEGACY lists every tenant" "HOME_LEGACY:$H/.aitask|$KNOWN_ALL" "$(hline HOME_LEGACY:)"
assert_eq "H2 HOME_NEXT says what --migrate would do" "HOME_NEXT:migrate|8|$KNOWN_ALL" "$(hline HOME_NEXT:)"
assert_eq "H2 the report leaves the legacy root byte-identical" "$sig" "$(tree_sig "$H/.aitask")"
assert_dir_not_exists "H2 the report creates no root (and no lock)" "$SCRATCH/ah2"

# --- H3: report on a root --migrate would refuse ------------------------------
H="$SCRATCH/h3"; mklegacy "$H"; printf 'x\n' >"$H/.aitask/junk"
home_eng "$H" "$SCRATCH/ah3"
assert_eq "H3 HOME_NEXT:refuse names the reason" "HOME_NEXT:refuse|unknown-entry:junk" "$(hline HOME_NEXT:)"

# --- H4: --migrate with no legacy root ---------------------------------------
H="$SCRATCH/h4"; mkdir -p "$H"
home_eng "$H" "$SCRATCH/ah4" --migrate
assert_exit_zero_rc "H4 nothing to migrate exits 0" "$rc"
assert_eq "H4 HOME_SKIPPED:no-legacy-root" "HOME_SKIPPED:no-legacy-root" "$out"
assert_dir_not_exists "H4 nothing is created" "$SCRATCH/ah4"

# --- H5: destination-exists:engine — both trees byte-identical ---------------
H="$SCRATCH/h5"; AH="$SCRATCH/ah5"; mklegacy "$H"
mkdir -p "$AH/engine/v9"; printf 'new engine\n' >"$AH/engine/v9/ait-testmap"
sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$AH")"
home_eng "$H" "$AH" --migrate
assert_eq "H5 refusal exits 1" "1" "$rc"
assert_eq "H5 HOME_SKIPPED:destination-exists:engine" "HOME_SKIPPED:destination-exists:engine" "$out"
assert_eq "H5 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H5 new root byte-identical" "$sig_a" "$(tree_sig "$AH")"

# --- H6: unknown-entry ---------------------------------------------------------
H="$SCRATCH/h6"; mklegacy "$H"; mkdir "$H/.aitask/.cache"
sig_l="$(tree_sig "$H/.aitask")"
home_eng "$H" "$SCRATCH/ah6" --migrate
assert_eq "H6 refusal exits 1" "1" "$rc"
assert_eq "H6 HOME_SKIPPED:unknown-entry (dotfiles count)" "HOME_SKIPPED:unknown-entry:.cache" "$out"
assert_eq "H6 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_dir_not_exists "H6 the new root is not even created" "$SCRATCH/ah6"

# --- H7: a hostile pre-existing symlink -------------------------------------
H="$SCRATCH/h7"; mkdir -p "$H" "$SCRATCH/elsewhere7"; printf 'mine\n' >"$SCRATCH/elsewhere7/f"
ln -s "$SCRATCH/elsewhere7" "$H/.aitask"
sig_e="$(tree_sig "$SCRATCH/elsewhere7")"
home_eng "$H" "$SCRATCH/ah7" --migrate
assert_eq "H7 refusal exits 1" "1" "$rc"
assert_eq "H7 HOME_SKIPPED:foreign-symlink:<target>" "HOME_SKIPPED:foreign-symlink:$SCRATCH/elsewhere7" "$out"
assert_eq "H7 the link is untouched" "$SCRATCH/elsewhere7" "$(readlink "$H/.aitask")"
assert_eq "H7 its target is untouched" "$sig_e" "$(tree_sig "$SCRATCH/elsewhere7")"
home_eng "$H" "$SCRATCH/ah7"
assert_eq "H7 report: HOME_SYMLINK shows the foreign target" "HOME_SYMLINK:$SCRATCH/elsewhere7" "$(hline HOME_SYMLINK:)"

# --- H8: cross-device ----------------------------------------------------------
dev_of() { stat -L -c %d "$1" 2>/dev/null || stat -L -f %d "$1" 2>/dev/null; }
if [[ -d /dev/shm && -w /dev/shm && "$(dev_of /dev/shm)" != "$(dev_of "$SCRATCH")" ]]; then
    H="$SCRATCH/h8"; mklegacy "$H"; AH="/dev/shm/aitasks-home-test.$$"
    rm -rf "$AH"
    sig_l="$(tree_sig "$H/.aitask")"
    home_eng "$H" "$AH" --migrate
    assert_eq "H8 refusal exits 1" "1" "$rc"
    assert_eq "H8 HOME_SKIPPED:cross-device" "HOME_SKIPPED:cross-device" "$out"
    assert_eq "H8 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
    assert_dir_not_exists "H8 nothing created on the other filesystem" "$AH"
else
    echo "SKIP: H8 cross-device (no second writable filesystem at /dev/shm) — not counted" >&2
fi

# --- H9: busy — another migration holds the home lock -------------------------
H="$SCRATCH/h9"; AH="$SCRATCH/ah9"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"
rm -f "$SCRATCH/ready9"
bash -c 'warn() { echo "$*" >&2; }; . "$1"
    stale_lock_acquire "$2" 1 0 holder || exit 9
    : >"$3"; sleep 30' _ "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh" "$AH/.home.lock" "$SCRATCH/ready9" &
holder=$!
for _ in $(seq 1 100); do [[ -e "$SCRATCH/ready9" ]] && break; sleep 0.05; done
home_eng "$H" "$AH" --migrate
assert_eq "H9 busy exits 1" "1" "$rc"
assert_eq "H9 HOME_SKIPPED:busy" "HOME_SKIPPED:busy" "$out"
assert_eq "H9 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null

# --- H10: same-root / root-not-absolute ---------------------------------------
H="$SCRATCH/h10"; mklegacy "$H"
sig_l="$(tree_sig "$H/.aitask")"
home_eng "$H" "$H/.aitask" --migrate
assert_eq "H10 AITASKS_HOME = the legacy root → same-root" "HOME_SKIPPED:same-root" "$out"
home_eng "$H" "relative/root" --migrate
assert_eq "H10 relative AITASKS_HOME → root-not-absolute" "HOME_SKIPPED:root-not-absolute" "$out"
assert_eq "H10 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"

# --- H11: the full known set into an AITASKS_HOME override --------------------
H="$SCRATCH/h11"; AH="$SCRATCH/ah11/nested/root"; mklegacy "$H"
printf '#!%s\nprint("shebang ok")\n' "$H/.aitask/venv/bin/python" >"$SCRATCH/s11.py"
chmod +x "$SCRATCH/s11.py"
sig_l="$(tree_sig "$H/.aitask")"
home_eng "$H" "$AH" --migrate
assert_exit_zero_rc "H11 migration exits 0" "$rc"
assert_eq "H11 HOME_MIGRATED:8 (pypy_venv and engine included)" "HOME_MIGRATED:8" "$out"
assert_eq "H11 the legacy root is now a symlink to the override" "LINK:$AH" "$(tree_sig "$H/.aitask")"
assert_eq "H11 the override holds the legacy tree byte-identically" "$sig_l" "$(tree_sig "$AH")"
no_lock "$AH" "H11"
if [[ "$REAL_VENV" == 1 ]]; then
    assert_eq "H11 ~/.aitask/venv/bin/python still runs" "42" \
        "$(HOME="$H" "$H/.aitask/venv/bin/python" -c 'print(42)' 2>&1)"
    assert_eq "H11 an absolute ~/.aitask venv shebang still runs" "shebang ok" "$("$SCRATCH/s11.py" 2>&1)"
    assert_eq "H11 the bin/python3 wrapper still runs" "7" \
        "$(HOME="$H" "$H/.aitask/bin/python3" -c 'print(7)' 2>&1)"
    assert_eq "H11 the python/<ver> symlink tree still resolves" "8" \
        "$("$H/.aitask/python/3.x/bin/python3" -c 'print(8)' 2>&1)"
else
    echo "SKIP: H11 symlink-compatibility runs (python3 -m venv unavailable) — not counted" >&2
fi

# --- H12: the default AITASKS_HOME, then the report -----------------------------
H="$SCRATCH/h12"; mklegacy "$H" --no-engine
home_eng "$H" - --migrate
assert_exit_zero_rc "H12 migration into the default root exits 0" "$rc"
assert_eq "H12 HOME_MIGRATED:7" "HOME_MIGRATED:7" "$out"
assert_eq "H12 legacy root links to \$HOME/.aitasks" "LINK:$H/.aitasks" "$(tree_sig "$H/.aitask")"
home_eng "$H" -
assert_eq "H12 report: HOME_LEGACY:none" "HOME_LEGACY:none" "$(hline HOME_LEGACY:)"
assert_eq "H12 report: HOME_SYMLINK names the root" "HOME_SYMLINK:$H/.aitasks" "$(hline HOME_SYMLINK:)"
assert_eq "H12 report: HOME_NEXT:none|already-migrated" "HOME_NEXT:none|already-migrated" "$(hline HOME_NEXT:)"

# --- H13: idempotent re-run ------------------------------------------------------
sig_a="$(tree_sig "$H/.aitasks")"
home_eng "$H" - --migrate
assert_exit_zero_rc "H13 re-run exits 0" "$rc"
assert_eq "H13 HOME_SKIPPED:already-migrated" "HOME_SKIPPED:already-migrated" "$out"
assert_eq "H13 re-run changes nothing" "$sig_a" "$(tree_sig "$H/.aitasks")"

# --- H14: rmdir fails (a writer dropped a file in) → full rollback -------------
H="$SCRATCH/h14"; AH="$SCRATCH/ah14"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$AH")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h14 \
    '[[ "$1" == post-moves ]] && : >"$HOOK_L/stray"; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H14 exits 1" "1" "$rc"
assert_contains "H14 HOME_SKIPPED:legacy-root-not-empty:stray" "HOME_SKIPPED:legacy-root-not-empty:stray" "$out"
assert_contains "H14 HOME_ROLLED_BACK:8" "HOME_ROLLED_BACK:8" "$out"
assert_file_exists "H14 the writer's file is kept" "$H/.aitask/stray"
rm -f "$H/.aitask/stray"
assert_eq "H14 legacy tree restored byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H14 new root unchanged" "$sig_a" "$(tree_sig "$AH")"
no_lock "$AH" "H14"

# --- H15: the legacy root reappears before ln → no stray link, rollback --------
H="$SCRATCH/h15"; AH="$SCRATCH/ah15"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$AH")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h15 \
    '[[ "$1" == pre-link ]] && mkdir "$HOOK_L"; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H15 exits 1" "1" "$rc"
assert_contains "H15 HOME_SKIPPED:symlink-failed" "HOME_SKIPPED:symlink-failed" "$out"
assert_contains "H15 HOME_ROLLED_BACK:8" "HOME_ROLLED_BACK:8" "$out"
assert_eq "H15 legacy tree restored, no link left inside it" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H15 new root unchanged" "$sig_a" "$(tree_sig "$AH")"
no_lock "$AH" "H15"
# The same race with a trailing-slash AITASKS_HOME: the stray link ln put
# inside the recreated directory is still found and removed.
H="$SCRATCH/h15s"; AH="$SCRATCH/ah15s"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h15s \
    '[[ "$1" == pre-link ]] && mkdir "$HOOK_L"; exit 0')")
home_eng "$H" "$AH/" --migrate
HOME_ENV=()
assert_contains "H15 trailing slash: HOME_ROLLED_BACK:8" "HOME_ROLLED_BACK:8" "$out"
assert_eq "H15 trailing slash: no stray link left inside the legacy root" "$sig_l" "$(tree_sig "$H/.aitask")"
home_eng "$H" "$AH/" --migrate
assert_eq "H15 trailing slash: a re-run succeeds (no leftover unknown entry)" "HOME_MIGRATED:8" "$out"
assert_eq "H15 trailing slash: the link target is the normalized root" "LINK:$AH" "$(tree_sig "$H/.aitask")"

# --- H16: a destination appears AFTER the final check → nested mv recovered -----
H="$SCRATCH/h16"; AH="$SCRATCH/ah16"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h16 \
    'if [[ "$1:${2:-}" == pre-mv:venv ]]; then mkdir "$HOOK_AH/venv"; echo competitor >"$HOOK_AH/venv/marker"; fi; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H16 exits 1" "1" "$rc"
assert_contains "H16 HOME_SKIPPED:destination-exists:venv" "HOME_SKIPPED:destination-exists:venv" "$out"
assert_contains "H16 the nested move is recovered: HOME_ROLLED_BACK:8" "HOME_ROLLED_BACK:8" "$out"
assert_eq "H16 legacy tree restored byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H16 the competing venv is kept" "competitor" "$(cat "$AH/venv/marker" 2>/dev/null)"
assert_eq "H16 …alone (no nested venv/venv)" "marker" "$(ls -A "$AH/venv" | tr '\n' ' ' | sed 's/ $//')"
assert_eq "H16 nothing else left in the new root" "venv" "$(ls -A "$AH" | tr '\n' ' ' | sed 's/ $//')"
no_lock "$AH" "H16"
# Control: the same collision present BEFORE the run is the plain preflight
# refusal, with no rollback — so H16 above really exercised the recovery path.
H="$SCRATCH/h16c"; AH="$SCRATCH/ah16c"; mklegacy "$H"; mkdir -p "$AH/venv"
home_eng "$H" "$AH" --migrate
assert_eq "H16 control: preflight refusal" "HOME_SKIPPED:destination-exists:venv" "$out"
assert_not_contains "H16 control: no rollback happened" "HOME_ROLLED_BACK" "$out"

# --- H17: usage --------------------------------------------------------------------
home_eng "$SCRATCH/h1" "$SCRATCH/ah1" --bogus
assert_eq "H17 home --bogus → exit 64" "64" "$rc"
assert_contains "H17 … with USAGE:" "USAGE:" "$err"

# --- H18: destination aliasing / normalization / containment --------------------
H="$SCRATCH/h18"; mklegacy "$H"; mkdir -p "$SCRATCH/out18"
ln -s "$H/.aitask/venv" "$SCRATCH/out18/link"
sig_l="$(tree_sig "$H/.aitask")"
home_eng "$H" "$SCRATCH/out18/link/sub" --migrate
assert_eq "H18 an outside alias into the legacy tree is refused" "HOME_SKIPPED:root-inside-legacy" "$out"
assert_eq "H18 …exit 1" "1" "$rc"
assert_eq "H18 …before anything is created (legacy byte-identical)" "$sig_l" "$(tree_sig "$H/.aitask")"
home_eng "$H" "$SCRATCH/x18/../y18" --migrate
assert_eq "H18 a '..' component → root-not-normalized" "HOME_SKIPPED:root-not-normalized" "$out"
assert_dir_not_exists "H18 …and nothing created" "$SCRATCH/y18"
home_eng "$H" "$H" --migrate
assert_eq "H18 AITASKS_HOME=\$HOME → legacy-inside-root" "HOME_SKIPPED:legacy-inside-root" "$out"
assert_eq "H18 legacy tree still byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"

# --- H19: a signal mid-move cancels the migration -------------------------------
# The hook signals its parent (the verb) before `python` moves — after bin,
# dev_tier, engine and pypy_venv already have. Bash runs the trap as soon as
# the hook returns. INT is sent to the hook's own process too, as Ctrl-C does
# to the foreground group (bash acts on SIGINT only once the child died of it).
for sig in TERM INT; do
    H="$SCRATCH/h19$sig"; AH="$SCRATCH/ah19$sig"; mklegacy "$H"; mkdir -p "$AH"
    sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$AH")"
    if [[ "$sig" == INT ]]; then
        body='[[ "$1:${2:-}" == pre-mv:python ]] && { kill -INT "$PPID"; kill -INT $$; }; exit 0'
        want=130
    else
        body='[[ "$1:${2:-}" == pre-mv:python ]] && kill -TERM "$PPID"; exit 0'
        want=143
    fi
    HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook "h19$sig" "$body")")
    home_eng "$H" "$AH" --migrate
    HOME_ENV=()
    assert_eq "H19 $sig: exit $want" "$want" "$rc"
    assert_contains "H19 $sig: HOME_SKIPPED:interrupted:$sig" "HOME_SKIPPED:interrupted:$sig" "$out"
    assert_contains "H19 $sig: the 4 moved entries come back" "HOME_ROLLED_BACK:4" "$out"
    assert_eq "H19 $sig: legacy tree restored byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
    assert_eq "H19 $sig: new root unchanged" "$sig_a" "$(tree_sig "$AH")"
    no_lock "$AH" "H19 $sig"
done

# --- H20: a signal after rmdir, before the link ----------------------------------
H="$SCRATCH/h20"; AH="$SCRATCH/ah20"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$AH")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h20 \
    '[[ "$1" == pre-link ]] && kill -TERM "$PPID"; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H20 exit 143" "143" "$rc"
assert_contains "H20 HOME_SKIPPED:interrupted:TERM" "HOME_SKIPPED:interrupted:TERM" "$out"
assert_contains "H20 HOME_ROLLED_BACK:8" "HOME_ROLLED_BACK:8" "$out"
assert_eq "H20 legacy root recreated and restored byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H20 new root unchanged" "$sig_a" "$(tree_sig "$AH")"
no_lock "$AH" "H20"

# --- H21: a signal after the verified link keeps the completed migration ---------
H="$SCRATCH/h21"; AH="$SCRATCH/ah21"; mklegacy "$H"
sig_l="$(tree_sig "$H/.aitask")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h21 \
    '[[ "$1" == post-link ]] && kill -TERM "$PPID"; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H21 exit 143" "143" "$rc"
assert_eq "H21 reports the completed migration" "HOME_MIGRATED:8" "$out"
assert_eq "H21 the symlink is kept" "LINK:$AH" "$(tree_sig "$H/.aitask")"
assert_eq "H21 nothing undone" "$sig_l" "$(tree_sig "$AH")"
no_lock "$AH" "H21"

# --- H22: a blocked rollback is reported precisely and touches nothing foreign ----
H="$SCRATCH/h22"; AH="$SCRATCH/ah22"; mklegacy "$H"; mkdir -p "$AH"
declare -a before22=()
for e in bin dev_tier engine pypy_venv python update_check uv venv; do before22+=("$(tree_sig "$H/.aitask/$e")"); done
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h22 \
    'if [[ "$1" == post-moves ]]; then : >"$HOOK_L/stray"; mkdir "$HOOK_L/venv"; echo competitor >"$HOOK_L/venv/marker"; fi; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H22 exit 2" "2" "$rc"
assert_contains "H22 the cause" "HOME_SKIPPED:legacy-root-not-empty:stray,venv" "$out"
assert_contains "H22 HOME_FAILED:rollback|venv" "HOME_FAILED:rollback|venv" "$out"
assert_eq "H22 HOME_STRANDED names where it is and where it belongs" \
    "HOME_STRANDED:venv|$AH/venv|$H/.aitask/venv" "$(hline HOME_STRANDED:)"
restore22="$(hline 'HOME_RESTORE:venv|' | sed 's/^HOME_RESTORE:venv|//')"
assert_eq "H22 two restore steps, competitor aside first" "2" "$(printf '%s\n' "$restore22" | grep -c '^mv -- ')"
assert_contains "H22 the warning points at the steps" "HOME_RESTORE:venv" "$err"
i=0
for e in bin dev_tier engine pypy_venv python update_check uv; do
    assert_eq "H22 $e restored byte-identically" "${before22[$i]}" "$(tree_sig "$H/.aitask/$e")"
    i=$((i + 1))
done
assert_eq "H22 the original venv is intact where it now is" "${before22[7]}" "$(tree_sig "$AH/venv")"
assert_eq "H22 the competing venv is untouched" "competitor" "$(cat "$H/.aitask/venv/marker" 2>/dev/null)"
assert_file_exists "H22 the competing stray file is untouched" "$H/.aitask/stray"
assert_eq "H22 nothing else left in the new root" "venv" "$(ls -A "$AH" | tr '\n' ' ' | sed 's/ $//')"
no_lock "$AH" "H22"
# Following the printed steps verbatim restores the original AND keeps the
# competitor (a bare `mv <now> <legacy>` would nest it inside the competitor).
(set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore22")
assert_eq "H22 restore steps: the original venv is back at the legacy path" "${before22[7]}" "$(tree_sig "$H/.aitask/venv")"
assert_eq "H22 restore steps: the competitor is kept aside" "competitor" "$(cat "$H/.aitask/venv.competing/marker" 2>/dev/null)"
assert_dir_not_exists "H22 restore steps: nothing left in the new root" "$AH/venv"

# --- H23: a competitor appears during the ROLLBACK move → reported where it is ---
H="$SCRATCH/h23"; AH="$SCRATCH/ah23"; mklegacy "$H"; mkdir -p "$AH"
sig_v="$(tree_sig "$H/.aitask/venv")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h23 \
    'case "$1:${2:-}" in
       post-moves:) : >"$HOOK_L/stray" ;;
       pre-restore:venv) mkdir "$HOOK_L/venv"; echo competitor >"$HOOK_L/venv/marker" ;;
     esac; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H23 exit 2" "2" "$rc"
assert_eq "H23 HOME_STRANDED names the nested location it really has" \
    "HOME_STRANDED:venv|$H/.aitask/venv/venv|$H/.aitask/venv" "$(hline HOME_STRANDED:)"
assert_eq "H23 the original survives intact there" "$sig_v" "$(tree_sig "$H/.aitask/venv/venv")"
assert_eq "H23 the competitor is kept" "competitor" "$(cat "$H/.aitask/venv/marker" 2>/dev/null)"
restore23="$(hline 'HOME_RESTORE:venv|' | sed 's/^HOME_RESTORE:venv|//')"
(set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore23")
assert_eq "H23 restore steps recover the original from inside the competitor" "$sig_v" "$(tree_sig "$H/.aitask/venv")"
assert_eq "H23 …and keep the competitor aside" "competitor" "$(cat "$H/.aitask/venv.competing/marker" 2>/dev/null)"
no_lock "$AH" "H23"

# --- H24: a name holding a newline is ONE unknown entry, refused before any move --
H="$SCRATCH/h24"; AH="$SCRATCH/ah24"; mklegacy "$H"
printf 'x\n' >"$H/.aitask/venv"$'\n'
sig_l="$(tree_sig "$H/.aitask")"
home_eng "$H" "$AH"
assert_eq "H24 report: refused, the name shown escaped" "HOME_NEXT:refuse|unknown-entry:\$'venv\\n'" "$(hline HOME_NEXT:)"
home_eng "$H" "$AH" --migrate
assert_eq "H24 --migrate exits 1" "1" "$rc"
assert_eq "H24 HOME_SKIPPED:unknown-entry, no rollback" "HOME_SKIPPED:unknown-entry:\$'venv\\n'" "$out"
assert_eq "H24 nothing moved" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_dir_not_exists "H24 nothing created" "$AH"

# --- H25: relative symlinks that leave the tree are refused; inner ones move ------
H="$SCRATCH/h25"; AH="$SCRATCH/ah25/deeper"; mklegacy "$H"; mkdir -p "$SCRATCH/h25/external/bin"
rm -rf "$H/.aitask/pypy_venv"; ln -s ../external "$H/.aitask/pypy_venv"
ln -s ../../../external/bin "$H/.aitask/uv/out"
sig_l="$(tree_sig "$H/.aitask")"
home_eng "$H" "$AH" --migrate
assert_eq "H25 exit 1" "1" "$rc"
assert_contains "H25 a top-level relative link out of the root is refused" "HOME_SKIPPED:relative-symlink:pypy_venv" "$out"
assert_contains "H25 a nested one is refused too" "HOME_SKIPPED:relative-symlink:uv/out" "$out"
assert_eq "H25 nothing moved" "$sig_l" "$(tree_sig "$H/.aitask")"
# Relative links that stay inside the root keep resolving after the move
# (the real venv's lib64 -> lib is one; add a cross-tenant one too).
rm -f "$H/.aitask/pypy_venv" "$H/.aitask/uv/out"
ln -s venv "$H/.aitask/pypy_venv"
home_eng "$H" "$AH" --migrate
assert_eq "H25 inner relative links migrate" "HOME_MIGRATED:8" "$out"
assert_eq "H25 …and still resolve through the legacy path" "$(tree_sig "$AH/venv")" "$(tree_sig "$H/.aitask/pypy_venv/")"

# --- H26: an incomplete link scan refuses (an unreadable directory hides links) ---
if [[ "$(id -u)" != 0 ]]; then
    H="$SCRATCH/h26"; AH="$SCRATCH/ah26/deeper"; mklegacy "$H"; mkdir -p "$H/external"
    mkdir -p "$H/.aitask/venv/hidden"
    ln -s ../../../external "$H/.aitask/venv/hidden/interp"
    chmod 0311 "$H/.aitask/venv/hidden"          # searchable, not listable
    home_eng "$H" "$AH" --migrate
    assert_eq "H26 exit 1" "1" "$rc"
    assert_contains "H26 HOME_SKIPPED:scan-incomplete" "HOME_SKIPPED:scan-incomplete" "$out"
    assert_not_contains "H26 nothing migrated" "HOME_MIGRATED" "$out"
    assert_dir_not_exists "H26 nothing created" "$AH"
    assert_eq "H26 the hidden link is still where it was" "../../../external" "$(readlink "$H/.aitask/venv/hidden/interp")"
    home_eng "$H" "$AH"
    assert_contains "H26 report: refuse|scan-incomplete" "HOME_NEXT:refuse|scan-incomplete" "$out"
    chmod 0755 "$H/.aitask/venv/hidden"
else
    echo "SKIP: H26 unreadable-directory scan (running as root) — not counted" >&2
fi

# --- H27: the legacy root itself is obstructed during rollback ---------------------
H="$SCRATCH/h27"; AH="$SCRATCH/ah27"; mklegacy "$H"; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h27 \
    '[[ "$1" == pre-link ]] && echo obstruction >"$HOOK_L"; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H27 exit 2" "2" "$rc"
assert_contains "H27 HOME_FAILED:rollback names every entry" "HOME_FAILED:rollback|" "$out"
assert_eq "H27 the obstruction is untouched" "obstruction" "$(cat "$H/.aitask" 2>/dev/null)"
restore27="$(hline 'HOME_RESTORE:' | sed 's/^HOME_RESTORE:[^|]*|//')"
assert_contains "H27 first step sets the obstruction aside" "mv -- $H/.aitask $H/.aitask.competing" "$(printf '%s\n' "$restore27" | head -n1)"
assert_contains "H27 second step recreates the directory" "mkdir -- $H/.aitask" "$(printf '%s\n' "$restore27" | sed -n 2p)"
(set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore27")
assert_eq "H27 following the steps restores the legacy tree byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H27 …and keeps the obstruction aside" "obstruction" "$(cat "$H/.aitask.competing" 2>/dev/null)"
assert_eq "H27 …leaving the new root empty" "" "$(ls -A "$AH")"
no_lock "$AH" "H27"

# --- H29: the legacy root cannot be recreated during rollback (absent, not obstructed)
if [[ "$(id -u)" != 0 ]]; then
    H="$SCRATCH/h29"; AH="$SCRATCH/ah29"; mklegacy "$H"; mkdir -p "$AH"
    sig_l="$(tree_sig "$H/.aitask")"
    HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h29 \
        '[[ "$1" == pre-link ]] && chmod a-w "${HOOK_L%/*}"; exit 0')")
    home_eng "$H" "$AH" --migrate
    HOME_ENV=()
    chmod u+w "$H"
    assert_eq "H29 exit 2" "2" "$rc"
    assert_contains "H29 HOME_FAILED:rollback" "HOME_FAILED:rollback|" "$out"
    assert_eq "H29 the originals are intact in the new root" "$sig_l" "$(tree_sig "$AH")"
    restore29="$(hline 'HOME_RESTORE:' | sed 's/^HOME_RESTORE:[^|]*|//')"
    assert_contains "H29 the first step recreates the directory (nothing to set aside)" \
        "mkdir -- $H/.aitask" "$(printf '%s\n' "$restore29" | head -n1)"
    assert_not_contains "H29 no set-aside step for an absent root" ".competing" "$restore29"
    assert_contains "H29 the warning says it is missing, not obstructed" "is missing and could not be recreated" "$err"
    (set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore29")
    assert_eq "H29 once writable, the steps restore the legacy tree byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
    assert_eq "H29 …leaving the new root empty" "" "$(ls -A "$AH")"
    no_lock "$AH" "H29"
else
    echo "SKIP: H29 unwritable-parent rollback (running as root) — not counted" >&2
fi

# --- H30: per-entry restore when the legacy path is free vs occupied ----------------
# A writer drops a new update_check in and the legacy directory turns read-only:
# rmdir fails, and no entry can move back. update_check has a competitor (two
# steps); every other entry's legacy path is free (one step each).
if [[ "$(id -u)" != 0 ]]; then
    H="$SCRATCH/h30"; AH="$SCRATCH/ah30"; mklegacy "$H"; mkdir -p "$AH"
    sig_l="$(tree_sig "$H/.aitask")"
    HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h30 \
        'if [[ "$1" == post-moves ]]; then echo competitor >"$HOOK_L/update_check"; chmod a-w "$HOOK_L"; fi; exit 0')")
    home_eng "$H" "$AH" --migrate
    HOME_ENV=()
    chmod u+w "$H/.aitask"
    assert_eq "H30 exit 2" "2" "$rc"
    assert_eq "H30 every entry is stranded" "HOME_FAILED:rollback|venv,uv,update_check,python,pypy_venv,engine,dev_tier,bin" "$(hline HOME_FAILED:)"
    assert_eq "H30 a free legacy path gets ONE restore step" "1" "$(hline 'HOME_RESTORE:venv|' | grep -c .)"
    assert_eq "H30 an occupied one gets two (aside first)" "2" "$(hline 'HOME_RESTORE:update_check|' | grep -c .)"
    assert_contains "H30 the warning tells a failed move from a competitor" "the move failed" "$err"
    assert_contains "H30 …and still names the competitor case" "something else now occupies $H/.aitask/update_check" "$err"
    restore30="$(hline 'HOME_RESTORE:' | sed 's/^HOME_RESTORE:[^|]*|//')"
    (set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore30"); src=$?
    assert_exit_zero_rc "H30 every printed step runs" "$src"
    assert_eq "H30 the competing update_check is kept aside" "competitor" "$(cat "$H/.aitask/update_check.competing" 2>/dev/null)"
    rm -f "$H/.aitask/update_check.competing"
    assert_eq "H30 the steps restore the legacy tree byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"
    assert_eq "H30 …leaving the new root empty" "" "$(ls -A "$AH")"
    no_lock "$AH" "H30"
else
    echo "SKIP: H30 read-only legacy rollback (running as root) — not counted" >&2
fi

# --- H28: a signal right after ln (before the phase advanced) keeps the migration ---
H="$SCRATCH/h28"; AH="$SCRATCH/ah28"; mklegacy "$H"
sig_l="$(tree_sig "$H/.aitask")"
HOME_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook h28 \
    '[[ "$1" == post-ln ]] && kill -TERM "$PPID"; exit 0')")
home_eng "$H" "$AH" --migrate
HOME_ENV=()
assert_eq "H28 exit 143" "143" "$rc"
assert_eq "H28 reports the completed migration, not a rollback" "HOME_MIGRATED:8" "$out"
assert_eq "H28 the symlink is kept" "LINK:$AH" "$(tree_sig "$H/.aitask")"
assert_eq "H28 nothing undone" "$sig_l" "$(tree_sig "$AH")"
no_lock "$AH" "H28"

# --- H-I: through a real install.sh --dir ---------------------------------------
# The installed tree's `ait engine home --migrate`, against the real
# $HOME/.aitasks/engine/v<V>/ a --local-engine install publishes.
V="$(<"$PROJECT_DIR/.aitask-scripts/VERSION")"; V="${V%$'\r'}"
FAKE="$SCRATCH/fake/ait-testmap"; mkdir -p "$(dirname "$FAKE")"
cat >"$FAKE" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == version && "\${2:-}" == --json ]]; then
    printf '{"version":"%s","commit":"fake","contract":1}\n' "$V"; exit 0
fi
echo "FAKE:\$*"
EOF
chmod +x "$FAKE"
TARBALL="$SCRATCH/release.tar.gz"
tar -czf "$TARBALL" -C "$PROJECT_DIR" .aitask-scripts ait packaging seed 2>/dev/null
H="$SCRATCH/hI"; T="$SCRATCH/tI"; mkdir -p "$H" "$T" "$SCRATCH/binI"
ires="$(cd "$PROJECT_DIR" && env -u AITASKS_HOME HOME="$H" SHIM_DIR="$SCRATCH/binI" \
    bash "$PROJECT_DIR/install.sh" --dir "$T" --local-tarball "$TARBALL" --local-engine "$FAKE" </dev/null 2>&1)"
irc=$?
assert_exit_zero_rc "H-I install.sh --dir --local-engine exits 0" "$irc"
if [[ "$irc" -ne 0 ]]; then printf '%s\n' "$ires" | tail -n 20; fi
assert_file_exists "H-I the install published a real engine slot" "$H/.aitasks/engine/v$V/ait-testmap"
mklegacy "$H"
sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$H/.aitasks")"
out="$(cd "$T" && env -u AITASKS_HOME HOME="$H" "$T/ait" engine home --migrate 2>/dev/null)"; rc=$?
assert_eq "H-I installed verb refuses the engine collision" "HOME_SKIPPED:destination-exists:engine" "$out"
assert_eq "H-I …exit 1" "1" "$rc"
assert_eq "H-I legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "H-I installed root byte-identical" "$sig_a" "$(tree_sig "$H/.aitasks")"
rm -rf "$H/.aitask/engine"
out="$(cd "$T" && env -u AITASKS_HOME HOME="$H" "$T/ait" engine home --migrate 2>/dev/null)"; rc=$?
assert_exit_zero_rc "H-I after removing the collision the migration exits 0" "$rc"
assert_eq "H-I HOME_MIGRATED:7" "HOME_MIGRATED:7" "$out"
assert_eq "H-I legacy root links to the installed root" "LINK:$H/.aitasks" "$(tree_sig "$H/.aitask")"
assert_file_exists "H-I the engine slot is untouched" "$H/.aitasks/engine/v$V/ait-testmap"
if [[ "$REAL_VENV" == 1 ]]; then
    assert_eq "H-I ~/.aitask/venv/bin/python still runs" "42" \
        "$(HOME="$H" "$H/.aitask/venv/bin/python" -c 'print(42)' 2>&1)"
fi

# --- H-I2: the upgrade path (install.sh) never migrates; it only hints ------------
H="$SCRATCH/hI2"; T2="$SCRATCH/tI2"; mkdir -p "$T2" "$SCRATCH/binI2"; mklegacy "$H" --no-engine
sig_l="$(tree_sig "$H/.aitask")"
ires="$(cd "$PROJECT_DIR" && env -u AITASKS_HOME -u AIT_HOME_MIGRATE HOME="$H" SHIM_DIR="$SCRATCH/binI2" \
    bash "$PROJECT_DIR/install.sh" --dir "$T2" --local-tarball "$TARBALL" --local-engine "$FAKE" </dev/null 2>&1)"
irc=$?
assert_exit_zero_rc "H-I2 install.sh over a populated legacy root exits 0" "$irc"
if [[ "$irc" -ne 0 ]]; then printf '%s\n' "$ires" | tail -n 20; fi
assert_eq "H-I2 install.sh never migrates (legacy byte-identical)" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_contains "H-I2 install.sh prints the HOME_LEGACY: hint" "HOME_LEGACY:$H/.aitask|$KNOWN_7" "$ires"
assert_contains "H-I2 the hint points at ait setup" "'ait setup'" "$ires"
assert_not_contains "H-I2 no migration protocol from install.sh" "HOME_MIGRATED:" "$ires"

# --- I1-I12: setup migrates by default — the INSTALLED setup, production options ---
# setup_strict <setup.sh> <home> <aitasks_home | -> [main args…] — run that
# setup's main() under its OWN `set -euo pipefail` (production, unlike
# run_main's `set +euo pipefail`). Every function except the home path is
# stubbed `return 0`, so main() runs to the end offline and prompt-free and the
# tier probes answer "yes": the REAL call sites of setup_python_venv,
# setup_pypy_venv and setup_dev_deps are reached, where SETUP_EVAL can install
# tenant writers. SETUP_ENV (array) adds environment. Sets out (stdout+stderr), rc.
SETUP_ENV=(); SETUP_EVAL=""
STRICT_BODY='
    source "$1" --source-only
    shift
    keep=" main info success warn die detect_os setup_aitasks_home migrate_home_legacy report_home_legacy "
    for fn in $(compgen -A function); do
        [[ "$keep" == *" $fn "* ]] && continue
        eval "$fn() { return 0; }"
    done
    eval "$SETUP_EVAL"
    main "$@"'
setup_strict() {
    local script="$1" h="$2" ah="$3"; shift 3
    local envs=(HOME="$h")
    [[ "$ah" != - ]] && envs+=(AITASKS_HOME="$ah")
    out="$(env -u AITASKS_HOME -u AIT_HOME_MIGRATE "${envs[@]}" ${SETUP_ENV[@]+"${SETUP_ENV[@]}"} \
        SETUP_EVAL="$SETUP_EVAL" bash -c "$STRICT_BODY" _ "$script" "$@" </dev/null 2>&1)"
    rc=$?
}

# setup_strict_pg — setup_strict, but setup leads its OWN process group (job
# control in a subshell) and writes to a file, not a pipe, so a hook can signal
# the whole group — setup, the verb and the hook — the way a terminal's
# TERM/HUP does, without signalling this test.
setup_strict_pg() {
    local script="$1" h="$2" ah="$3"; shift 3
    local envs=(HOME="$h")
    [[ "$ah" != - ]] && envs+=(AITASKS_HOME="$ah")
    ( set -m
      env -u AITASKS_HOME -u AIT_HOME_MIGRATE "${envs[@]}" ${SETUP_ENV[@]+"${SETUP_ENV[@]}"} \
          SETUP_EVAL="$SETUP_EVAL" bash -c "$STRICT_BODY" _ "$script" "$@" \
          </dev/null >"$SCRATCH/pg_out" 2>&1 &
      wait "$!" ) 2>/dev/null
    rc=$?
    out="$(cat "$SCRATCH/pg_out")"
}

# Tenant writers: the shapes setup_python_venv (venv, python, uv, bin),
# setup_pypy_venv and setup_dev_deps leave in $HOME/.aitask — idempotent, so a
# re-run through the symlink rewrites identical bytes.
TENANTS="$SCRATCH/tenants.sh"
cat >"$TENANTS" <<'EOF'
setup_python_venv() {
    local l="$HOME/.aitask"
    mkdir -p "$l/python/3.x/bin" "$l/uv" "$l/bin"
    if [[ ! -e "$l/venv/bin/python" ]]; then
        if [[ -z "${TEN_PY3:-}" ]] || ! "$TEN_PY3" -m venv --without-pip "$l/venv" >/dev/null 2>&1; then
            mkdir -p "$l/venv/bin"
            printf '#!/bin/sh\necho 42\n' >"$l/venv/bin/python"
            chmod +x "$l/venv/bin/python"
        fi
    fi
    if [[ -n "${TEN_PY3:-}" ]]; then ln -sfn "$TEN_PY3" "$l/python/3.x/bin/python3"; fi
    printf 'uv-binary\n' >"$l/uv/uv"
    printf '#!/usr/bin/env bash\nexec "$HOME/.aitask/venv/bin/python" "$@"\n' >"$l/bin/python3"
    chmod +x "$l/bin/python3"
}
setup_pypy_venv() {
    mkdir -p "$HOME/.aitask/pypy_venv/bin"
    printf '#!/bin/sh\necho pypy\n' >"$HOME/.aitask/pypy_venv/bin/python"
    chmod +x "$HOME/.aitask/pypy_venv/bin/python"
}
setup_dev_deps() { printf 'dev tier installed\n' >"$HOME/.aitask/dev_tier"; }
EOF
WRITERS='source "'"$TENANTS"'"'
ISETUP="$T/.aitask-scripts/aitask_setup.sh"
DONE="Setup complete!"

# hint_after_home — 0 when the HOME_LEGACY: hint is the line right after the
# summary's AITASKS_HOME: line in $out.
hint_after_home() {
    local n_home n_hint
    n_home="$(printf '%s\n' "$out" | grep -n 'AITASKS_HOME:' | tail -n1 | cut -d: -f1)"
    n_hint="$(printf '%s\n' "$out" | grep -n 'HOME_LEGACY:' | head -n1 | cut -d: -f1)"
    [[ -n "$n_home" && "$n_hint" == "$((n_home + 1))" ]]
}

# I1 — fresh install: the tenant writers run at their real call sites, then the
# migration at the end of main() moves what they wrote. This is the ordering
# pin: a migration placed before setup_python_venv finds no legacy root and
# leaves a legacy tree behind.
H="$SCRATCH/i1"; mkdir -p "$H"
SETUP_ENV=(TEN_PY3="$PY3"); SETUP_EVAL="$WRITERS"
setup_strict "$ISETUP" "$H" -
SETUP_ENV=(); SETUP_EVAL=""
assert_exit_zero_rc "I1 fresh install: setup exits 0" "$rc"
if [[ "$rc" -ne 0 ]]; then printf '%s\n' "$out" | tail -n 20; fi
assert_contains "I1 completes" "$DONE" "$out"
assert_eq "I1 HOME_MIGRATED:6 (venv python uv bin pypy_venv dev_tier)" "HOME_MIGRATED:6" "$(hline HOME_MIGRATED:)"
assert_eq "I1 the legacy root is a link to the default root" "LINK:$H/.aitasks" "$(tree_sig "$H/.aitask")"
assert_dir_exists "I1 the venv lives in the new root" "$H/.aitasks/venv"
assert_eq "I1 the venv runs through ~/.aitask" "42" "$(HOME="$H" "$H/.aitask/venv/bin/python" -c 'print(42)' 2>&1)"
assert_eq "I1 the PyPy venv runs through ~/.aitask" "pypy" "$(HOME="$H" "$H/.aitask/pypy_venv/bin/python" 2>&1)"
assert_not_contains "I1 no hint" "HOME_LEGACY:" "$out"

# I2 — an existing legacy root with a working venv and PyPy venv.
H="$SCRATCH/i2"; mklegacy "$H" --no-engine
SETUP_ENV=(TEN_PY3="$PY3"); SETUP_EVAL="$WRITERS"
setup_strict "$ISETUP" "$H" -
assert_exit_zero_rc "I2 setup exits 0" "$rc"
assert_contains "I2 completes" "$DONE" "$out"
assert_eq "I2 HOME_MIGRATED:7" "HOME_MIGRATED:7" "$(hline HOME_MIGRATED:)"
assert_eq "I2 the legacy root is a link" "LINK:$H/.aitasks" "$(tree_sig "$H/.aitask")"
if [[ "$REAL_VENV" == 1 ]]; then
    assert_eq "I2 the real venv runs through ~/.aitask" "42" "$(HOME="$H" "$H/.aitask/venv/bin/python" -c 'print(42)' 2>&1)"
fi
assert_eq "I2 the bin/python3 wrapper runs" "42" "$(HOME="$H" "$H/.aitask/bin/python3" -c 'print(42)' 2>&1)"
assert_eq "I2 the PyPy venv runs" "pypy" "$(HOME="$H" "$H/.aitask/pypy_venv/bin/python" 2>&1)"
assert_not_contains "I2 no hint" "HOME_LEGACY:" "$out"

# I3 — re-run setup after migrating: no re-migration, no hint, nothing changed.
sig_a="$(tree_sig "$H/.aitasks")"
setup_strict "$ISETUP" "$H" -
SETUP_ENV=(); SETUP_EVAL=""
assert_exit_zero_rc "I3 re-run exits 0" "$rc"
assert_contains "I3 completes" "$DONE" "$out"
assert_not_contains "I3 no re-migration" "HOME_MIGRATED:" "$out"
assert_not_contains "I3 no hint" "HOME_LEGACY:" "$out"
assert_eq "I3 the link is unchanged" "LINK:$H/.aitasks" "$(tree_sig "$H/.aitask")"
assert_eq "I3 the new root is byte-identical" "$sig_a" "$(tree_sig "$H/.aitasks")"
assert_eq "I3 the tenants still resolve" "pypy" "$(HOME="$H" "$H/.aitask/pypy_venv/bin/python" 2>&1)"

# I4 — a hostile pre-existing symlink: refused, setup carries on, nothing touched.
H="$SCRATCH/i4"; mkdir -p "$H" "$SCRATCH/elsewhereI4"; printf 'mine\n' >"$SCRATCH/elsewhereI4/f"
ln -s "$SCRATCH/elsewhereI4" "$H/.aitask"
sig_e="$(tree_sig "$SCRATCH/elsewhereI4")"
setup_strict "$ISETUP" "$H" -
assert_exit_zero_rc "I4 a refusal never fails setup" "$rc"
assert_contains "I4 completes" "$DONE" "$out"
assert_eq "I4 HOME_SKIPPED:foreign-symlink:<target>" "HOME_SKIPPED:foreign-symlink:$SCRATCH/elsewhereI4" "$(hline HOME_SKIPPED:)"
assert_eq "I4 the link is untouched" "$SCRATCH/elsewhereI4" "$(readlink "$H/.aitask")"
assert_eq "I4 its target is untouched" "$sig_e" "$(tree_sig "$SCRATCH/elsewhereI4")"

# I5 — cross-device: refused, setup carries on.
if [[ -d /dev/shm && -w /dev/shm && "$(dev_of /dev/shm)" != "$(dev_of "$SCRATCH")" ]]; then
    H="$SCRATCH/i5"; mklegacy "$H" --no-engine; AH="/dev/shm/aitasks-home-i5.$$"
    rm -rf "$AH"
    sig_l="$(tree_sig "$H/.aitask")"
    setup_strict "$ISETUP" "$H" "$AH"
    rm -rf "$AH"
    assert_exit_zero_rc "I5 cross-device refusal never fails setup" "$rc"
    assert_contains "I5 completes" "$DONE" "$out"
    assert_eq "I5 HOME_SKIPPED:cross-device" "HOME_SKIPPED:cross-device" "$(hline HOME_SKIPPED:)"
    assert_eq "I5 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
else
    echo "SKIP: I5 cross-device (no second writable filesystem at /dev/shm) — not counted" >&2
fi

# I6 — a destination collision: refused with both trees byte-identical; the
# summary keeps the hint right after AITASKS_HOME:.
H="$SCRATCH/i6"; AH="$SCRATCH/ah_i6"; mklegacy "$H"; mkdir -p "$AH/engine"
sig_l="$(tree_sig "$H/.aitask")"; sig_a="$(tree_sig "$AH")"
setup_strict "$ISETUP" "$H" "$AH"
assert_exit_zero_rc "I6 a collision never fails setup" "$rc"
assert_contains "I6 completes" "$DONE" "$out"
assert_eq "I6 HOME_SKIPPED:destination-exists:engine" "HOME_SKIPPED:destination-exists:engine" "$(hline HOME_SKIPPED:)"
assert_eq "I6 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_eq "I6 new root byte-identical" "$sig_a" "$(tree_sig "$AH")"
TOTAL=$((TOTAL + 1))
if hint_after_home; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: I6 the hint is the line after AITASKS_HOME:"; fi

# I7 — the AITASKS_HOME override: the link points at it, the default root is untouched.
H="$SCRATCH/i7"; AH="$SCRATCH/custom_i7"; mklegacy "$H" --no-engine
setup_strict "$ISETUP" "$H" "$AH"
assert_exit_zero_rc "I7 setup exits 0" "$rc"
assert_eq "I7 HOME_MIGRATED:7" "HOME_MIGRATED:7" "$(hline HOME_MIGRATED:)"
assert_eq "I7 the legacy root links to the override" "LINK:$AH" "$(tree_sig "$H/.aitask")"
assert_dir_exists "I7 the tenants are in the override" "$AH/venv"
assert_dir_not_exists "I7 no default root was created" "$H/.aitasks"

# I8 / I9 — both opt-outs: the legacy tree is untouched and the hint stays.
H="$SCRATCH/i8"; mklegacy "$H" --no-engine
sig_l="$(tree_sig "$H/.aitask")"
setup_strict "$ISETUP" "$H" - --no-home-migration
assert_exit_zero_rc "I8 --no-home-migration: setup exits 0" "$rc"
assert_contains "I8 completes" "$DONE" "$out"
assert_contains "I8 names the flag" "skipped (--no-home-migration)" "$out"
assert_eq "I8 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
assert_not_contains "I8 the verb never ran" "HOME_MIGRATED:" "$out"
TOTAL=$((TOTAL + 1))
if hint_after_home; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: I8 the hint is the line after AITASKS_HOME:"; fi

H="$SCRATCH/i9"; mklegacy "$H" --no-engine
sig_l="$(tree_sig "$H/.aitask")"
SETUP_ENV=(AIT_HOME_MIGRATE=0)
setup_strict "$ISETUP" "$H" -
SETUP_ENV=()
assert_exit_zero_rc "I9 AIT_HOME_MIGRATE=0: setup exits 0" "$rc"
assert_contains "I9 completes" "$DONE" "$out"
assert_contains "I9 names the env var" "skipped (AIT_HOME_MIGRATE=0)" "$out"
assert_eq "I9 legacy tree byte-identical" "$sig_l" "$(tree_sig "$H/.aitask")"
TOTAL=$((TOTAL + 1))
if hint_after_home; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: I9 the hint is the line after AITASKS_HOME:"; fi

# I10 — class 1, rolled back: reported, setup completes (under errexit).
H="$SCRATCH/i10"; AH="$SCRATCH/ah_i10"; mklegacy "$H" --no-engine
sig_l="$(tree_sig "$H/.aitask")"
SETUP_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook i10 \
    '[[ "$1" == post-moves ]] && : >"$HOOK_L/stray"; exit 0')")
setup_strict "$ISETUP" "$H" "$AH"
SETUP_ENV=()
assert_exit_zero_rc "I10 a rollback never fails setup" "$rc"
assert_contains "I10 completes" "$DONE" "$out"
assert_eq "I10 HOME_ROLLED_BACK:7" "HOME_ROLLED_BACK:7" "$(hline HOME_ROLLED_BACK:)"
rm -f "$H/.aitask/stray"
assert_eq "I10 legacy tree restored byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"

# I11 — class 2, rollback blocked: setup stops (exit 2) and the protocol lines
# are verbatim — the HOME_RESTORE commands copied from SETUP's output restore it.
H="$SCRATCH/i11"; AH="$SCRATCH/ah_i11"; mklegacy "$H" --no-engine
venv_sig="$(tree_sig "$H/.aitask/venv")"
SETUP_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook i11 \
    'if [[ "$1" == post-moves ]]; then : >"$HOOK_L/stray"; mkdir "$HOOK_L/venv"; echo competitor >"$HOOK_L/venv/marker"; fi; exit 0')")
setup_strict "$ISETUP" "$H" "$AH"
SETUP_ENV=()
assert_eq "I11 setup stops with exit 2" "2" "$rc"
assert_not_contains "I11 setup does not complete" "$DONE" "$out"
assert_contains "I11 says setup stopped" "Setup stopped before completion" "$out"
assert_eq "I11 HOME_FAILED:rollback|venv at line start" "HOME_FAILED:rollback|venv" "$(hline HOME_FAILED:)"
assert_eq "I11 HOME_STRANDED verbatim" "HOME_STRANDED:venv|$AH/venv|$H/.aitask/venv" "$(hline HOME_STRANDED:)"
restore11="$(hline 'HOME_RESTORE:venv|' | sed 's/^HOME_RESTORE:venv|//')"
assert_eq "I11 two restore steps" "2" "$(printf '%s\n' "$restore11" | grep -c '^mv -- ')"
(set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore11")
assert_eq "I11 setup's restore steps put the original venv back" "$venv_sig" "$(tree_sig "$H/.aitask/venv")"
assert_eq "I11 …and keep the competitor aside" "competitor" "$(cat "$H/.aitask/venv.competing/marker" 2>/dev/null)"

# I12 — interrupted (128+signo): setup stops with the verb's status.
H="$SCRATCH/i12"; AH="$SCRATCH/ah_i12"; mklegacy "$H" --no-engine; mkdir -p "$AH"
sig_l="$(tree_sig "$H/.aitask")"
SETUP_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook i12 \
    '[[ "$1:${2:-}" == pre-mv:python ]] && kill -TERM "$PPID"; exit 0')")
setup_strict "$ISETUP" "$H" "$AH"
SETUP_ENV=()
assert_eq "I12 setup stops with exit 143" "143" "$rc"
assert_not_contains "I12 setup does not complete" "$DONE" "$out"
assert_contains "I12 HOME_SKIPPED:interrupted:TERM" "HOME_SKIPPED:interrupted:TERM" "$out"
assert_contains "I12 HOME_ROLLED_BACK" "HOME_ROLLED_BACK:" "$out"
assert_eq "I12 legacy tree restored byte-identically" "$sig_l" "$(tree_sig "$H/.aitask")"

# I13 — TERM to the WHOLE process group (setup + verb) after the moves, with a
# competitor blocking the rollback. The verb's HOME_FAILED / HOME_STRANDED /
# HOME_RESTORE lines are the only record of where the venv is; they must reach
# setup's output even though setup received the TERM too, and setup must
# outlive it to report and stop with 143. A $( )-buffered verb loses them.
H="$SCRATCH/i13"; AH="$SCRATCH/ah_i13"; mklegacy "$H" --no-engine
venv_sig="$(tree_sig "$H/.aitask/venv")"
SETUP_ENV=(HOOK_L="$H/.aitask" HOOK_AH="$AH" AIT_HOME_TEST_HOOK="$(mkhook i13 \
    'if [[ "$1" == post-moves ]]; then' \
    '    mkdir "$HOOK_L/venv"; echo competitor >"$HOOK_L/venv/marker"' \
    '    kill -TERM -- "-$(ps -o pgid= -p $$ | tr -d " ")"' \
    'fi; exit 0')")
setup_strict_pg "$ISETUP" "$H" "$AH"
SETUP_ENV=()
assert_eq "I13 setup stops with exit 143" "143" "$rc"
assert_not_contains "I13 setup does not complete" "$DONE" "$out"
assert_contains "I13 setup outlived the TERM and reports it" "Per-user root migration interrupted (exit 143)" "$out"
assert_eq "I13 HOME_SKIPPED:interrupted:TERM" "HOME_SKIPPED:interrupted:TERM" "$(hline HOME_SKIPPED:)"
assert_eq "I13 HOME_FAILED:rollback|venv survives" "HOME_FAILED:rollback|venv" "$(hline HOME_FAILED:)"
assert_eq "I13 HOME_STRANDED survives" "HOME_STRANDED:venv|$AH/venv|$H/.aitask/venv" "$(hline HOME_STRANDED:)"
restore13="$(hline 'HOME_RESTORE:venv|' | sed 's/^HOME_RESTORE:venv|//')"
assert_eq "I13 both restore steps survive" "2" "$(printf '%s\n' "$restore13" | grep -c '^mv -- ')"
(set -e; while IFS= read -r cmd; do eval "$cmd"; done <<<"$restore13")
assert_eq "I13 the surviving steps put the original venv back" "$venv_sig" "$(tree_sig "$H/.aitask/venv")"
assert_eq "I13 …and keep the competitor aside" "competitor" "$(cat "$H/.aitask/venv.competing/marker" 2>/dev/null)"

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
