#!/usr/bin/env bash
# test_install_engine_binary.sh - the test map engine install (t1852_5, M1.5):
# install_engine_binary() / report_testmap_state() / setup_testmap_gitignore()
# in aitask_setup.sh, the install.sh flags and post-shim call, and
# `ait engine` (aitask_engine.sh).
#
#   I*  the REAL install.sh --dir <scratch> --local-tarball <this tree> flow
#   R*  the release tier, always through the real fetch helper (curl, file://)
#   D*  .dev protection, the per-slot publication lock, a fresh engine root
#   F*  failure handling under both call shapes (errexit on, and `|| true`)
#   P*  a directory where the binary or sidecar belongs, in every publish mode
#   S*  the source tier;  T*  TESTMAP: states;  W*  main() wiring;
#   G*  the gitignore rule;  E*  ait engine prune / build / test / usage
#
# Zero network except where a case says otherwise (none do): every release
# fetch is served from a file:// mirror, and HOME / AITASKS_HOME / SHIM_DIR are
# redirected into the scratch dir. S2 and E4 build the real engine and are
# skipped (SKIP: line) when Go is not installed.
#
# Run: bash tests/test_install_engine_binary.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0
. "$PROJECT_DIR/tests/lib/asserts.sh"
assert_counters_init

# The caller's environment must not steer any case.
unset AITASKS_HOME AIT_TESTMAP_FETCH AIT_TESTMAP_BIN AIT_ENGINE \
      AIT_ENGINE_RELEASE_URL AIT_ENGINE_TEST_PRE_PUBLISH_HOOK AIT_ENGINE_TEST_POST_UNLOCK_HOOK \
      ENGINE_SLOT_LOCK_RETRIES AITASKS_PROJECTS_INDEX

WORK="$(mktemp -d)"
HOLDER_PID=""
cleanup() {
    [[ -n "$HOLDER_PID" ]] && kill -9 "$HOLDER_PID" 2>/dev/null
    chmod -R u+w "$WORK" 2>/dev/null
    rm -rf "$WORK"
    rm -f "$AIT_ASSERT_COUNTER_FILE"
}
trap cleanup EXIT

export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@example.com \
       GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@example.com

V="$(<"$PROJECT_DIR/.aitask-scripts/VERSION")"
V="${V%$'\r'}"
SUFFIX="$(bash -c 'source "$1/.aitask-scripts/lib/platform_detect.sh"; platform_asset_suffix' _ "$PROJECT_DIR")"
ASSET="ait-testmap_${V}_${SUFFIX}"
SUMS="ait-testmap_${V}_SHA256SUMS.txt"

echo "=== test map engine install (t1852_5) — V=$V, platform $SUFFIX ==="

# --- fixtures -----------------------------------------------------------------

# mkengine <path> <version> [tag] — a fake engine answering `version` (text) and
# `version --json`; <tag> makes byte-distinguishable binaries.
mkengine() {
    local path="$1" ver="$2" tag="${3:-default}"
    mkdir -p "$(dirname "$path")"
    cat >"$path" <<EOF
#!/usr/bin/env bash
# fake ait-testmap, tag $tag
if [[ "\${1:-}" == version ]]; then
    if [[ "\${2:-}" == --json ]]; then
        printf '{"version":"%s","commit":"fake","contract":1,"engine":"%s"}\n' "$ver" "\$0"
    else
        printf 'VERSION:%s\nCOMMIT:fake\nCONTRACT:1\nENGINE:%s\n' "$ver" "\$0"
    fi
    exit 0
fi
echo "FAKE:$tag:\$*"
EOF
    chmod +x "$path"
}

# Portable digest and sums check (sha256sum, else shasum -a 256), as in production.
sha() {
    if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1"; else shasum -a 256 "$1"; fi | cut -d' ' -f1
}
sumcheck() {
    if command -v sha256sum >/dev/null 2>&1; then
        (cd "$1" && sha256sum -c "$2") 2>&1
    else
        (cd "$1" && shasum -a 256 -c "$2") 2>&1
    fi
}

# mkmirror <dir> [tag] — a release mirror: the host asset (+x on purpose: the
# fetch must still arrive non-executable) and a correct sums file.
mkmirror() {
    local dir="$1" tag="${2:-mirror}"
    mkengine "$dir/$ASSET" "$V" "$tag"
    printf '%s  %s\n' "$(sha "$dir/$ASSET")" "$ASSET" >"$dir/$SUMS"
}

MIR="$WORK/mirror"; mkmirror "$MIR"
MIRROR_URL="file://$MIR"
CUSTOM="$WORK/custom/ait-testmap"; mkengine "$CUSTOM" "$V" custom
CUSTOM2="$WORK/custom2/ait-testmap"; mkengine "$CUSTOM2" "$V" custom2
WRONG="$WORK/wrong/ait-testmap"; mkengine "$WRONG" "0.0.0-wrong" wrong

TARBALL="$WORK/release.tar.gz"
tar -czf "$TARBALL" -C "$PROJECT_DIR" .aitask-scripts ait packaging seed 2>/dev/null
if [[ ! -s "$TARBALL" ]]; then
    assert_record_fail
    echo "FAIL: could not build the release-layout fixture tarball"
    assert_counters_load
    echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
    exit 1
fi

# run_install <target> <home> <aitasks_home or ""> [install.sh args...]
# The REAL installer. Sets `rc` and `out`. An empty <aitasks_home> leaves it
# unset, so the default ($HOME/.aitasks) is what is exercised.
run_install() {
    local target="$1" home="$2" ah="$3"; shift 3
    mkdir -p "$target" "$home"
    local envs=(HOME="$home" SHIM_DIR="$WORK/bin")
    [[ -n "$ah" ]] && envs+=(AITASKS_HOME="$ah")
    out="$(cd "$PROJECT_DIR" && env "${envs[@]}" "${EXTRA_ENV[@]+"${EXTRA_ENV[@]}"}" \
        bash "$PROJECT_DIR/install.sh" --dir "$target" --local-tarball "$TARBALL" "$@" </dev/null 2>&1)"
    rc=$?
}
EXTRA_ENV=()

# insetup <aitasks_home> <code> [args...] — run <code> in a bash that sourced
# the INSTALLED tree's setup (the install.sh-delivered copy). Errexit is ON as
# in setup's own main(); a case wanting the install.sh shape writes `|| true`.
insetup() {
    local ah="$1" code="$2"; shift 2
    HOME="$WORK/home" AITASKS_HOME="$ah" \
    AIT_ENGINE_RELEASE_URL="${AIT_ENGINE_RELEASE_URL:-$MIRROR_URL}" T="$T" \
        bash -c 'source "$T/.aitask-scripts/aitask_setup.sh" --source-only; '"$code" _ "$@" 2>&1
}

# line <text> <prefix> — the lines of <text> starting with <prefix>.
line() { printf '%s\n' "$1" | grep -- "^$2" || true; }

slot_of() { printf '%s/engine/v%s' "$1" "$V"; }

# --- I: the real install.sh flow ------------------------------------------------
echo "--- I: install.sh --dir <scratch> --local-tarball <tree> ---"

T="$WORK/t1"
run_install "$T" "$WORK/h1" "" --local-engine "$CUSTOM"
assert_exit_zero_rc "I1 install.sh --local-engine exits 0" "$rc"
DEF_SLOT="$WORK/h1/.aitasks/engine/v$V"
assert_file_exists "I1 extraction reached the target" "$T/.aitask-scripts/VERSION"
assert_contains "I1 TESTMAP_BINARY:installed …|local" "TESTMAP_BINARY:installed|$DEF_SLOT/ait-testmap|local" "$out"
assert_eq "I1 lands at the default \$HOME/.aitasks/engine/v<V>/" "same" \
    "$(cmp -s "$CUSTOM" "$DEF_SLOT/ait-testmap" && echo same || echo differs)"
assert_eq "I1 installed binary is executable" "yes" "$([[ -x "$DEF_SLOT/ait-testmap" ]] && echo yes || echo no)"
assert_file_exists "I1 a --local-engine slot is .dev-marked" "$DEF_SLOT/.dev"
assert_file_not_exists "I1 a .dev slot carries no release sidecar" "$DEF_SLOT/ait-testmap.sha256"
res="$(HOME="$WORK/h1" bash -c 'source "$1/.aitask-scripts/aitask_testmap.sh" --source-only; rc=0; testmap_resolve_engine || rc=$?; echo "$rc|$TESTMAP_ENGINE_BIN"' _ "$T" 2>/dev/null)"
assert_eq "I1 the installed tree's shim resolves the engine" "0|$DEF_SLOT/ait-testmap" "$res"
if [[ "$rc" -ne 0 ]]; then printf '%s\n' "$out" | tail -n 20 | sed 's/^/  | /'; fi

run_install "$WORK/t2" "$WORK/h2" "$WORK/ah2" --no-testmap
assert_exit_zero_rc "I2 install.sh --no-testmap exits 0" "$rc"
assert_eq "I2 TESTMAP_BINARY:skipped" "TESTMAP_BINARY:skipped" "$(line "$out" TESTMAP_BINARY:)"
assert_dir_not_exists "I2 no slot is created" "$(slot_of "$WORK/ah2")"

EXTRA_ENV=(AIT_TESTMAP_FETCH=0)
run_install "$WORK/t3" "$WORK/h3" "$WORK/ah3"
EXTRA_ENV=()
assert_exit_zero_rc "I3 install.sh with AIT_TESTMAP_FETCH=0 exits 0" "$rc"
assert_eq "I3 TESTMAP_BINARY:skipped" "TESTMAP_BINARY:skipped" "$(line "$out" TESTMAP_BINARY:)"

# I4: --local-tarball alone is an offline install — the engine is not fetched.
mkdir -p "$WORK/fakebin"
cat >"$WORK/fakebin/curl" <<EOF
#!/usr/bin/env bash
echo "curl \$*" >>"$WORK/curl.log"
exit 22
EOF
chmod +x "$WORK/fakebin/curl"
: >"$WORK/curl.log"
EXTRA_ENV=(PATH="$WORK/fakebin:$PATH")
run_install "$WORK/t4" "$WORK/h4" "$WORK/ah4"
EXTRA_ENV=()
assert_exit_zero_rc "I4 install.sh --local-tarball exits 0" "$rc"
assert_eq "I4 TESTMAP_BINARY:skipped (offline install)" "TESTMAP_BINARY:skipped" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "I4 no curl call at all on the --local-tarball path" "" "$(cat "$WORK/curl.log")"

for bad in "--local-engine" "--local-engine $WORK/nope" "--no-testmap --local-engine $CUSTOM"; do
    # shellcheck disable=SC2086  # the case's words are meant to split
    run_install "$WORK/t5" "$WORK/h5" "$WORK/ah5" $bad
    assert_exit_nonzero_rc "I5 install.sh refuses '$bad'" "$rc"
    assert_eq "I5 '$bad' is refused before extraction" "" "$(ls -A "$WORK/t5")"
done

run_install "$WORK/t6" "$WORK/h6" "$WORK/ah6" --local-engine "$WRONG"
assert_exit_zero_rc "I6 a wrong-version engine never fails the install" "$rc"
assert_eq "I6 self-check-failed names the found version" "TESTMAP_BINARY:self-check-failed|local|0.0.0-wrong" "$(line "$out" TESTMAP_BINARY:)"
assert_contains "I6 ENGINE_MISSING warning" "ENGINE_MISSING:$(slot_of "$WORK/ah6")/ait-testmap|" "$out"
assert_file_not_exists "I6 nothing installed" "$(slot_of "$WORK/ah6")/ait-testmap"
assert_file_not_exists "I6 no .dev marker left" "$(slot_of "$WORK/ah6")/.dev"

# --- R: the release tier --------------------------------------------------------
echo "--- R: release tier (file:// mirror, real fetch helper) ---"

out="$(bash -c 'warn(){ :; }; source "$1/.aitask-scripts/lib/engine_install.sh"; engine_fetch "file://$2" "$3" && echo fetched' \
    _ "$T" "$MIR/$ASSET" "$WORK/r0.bin" 2>&1)"
assert_eq "R0 engine_fetch over file:// succeeds" "fetched" "$out"
assert_eq "R0 the fetched file is NOT executable (mirror file is)" "no" "$([[ -x "$WORK/r0.bin" ]] && echo yes || echo no)"

AH="$WORK/r1"
assert_dir_not_exists "R1 precondition: a fresh root with no engine/.locks" "$AH/engine/.locks"
out="$(insetup "$AH" 'install_engine_binary; echo "AFTER rc=$?"')"
S="$(slot_of "$AH")"
assert_eq "R1 TESTMAP_BINARY:installed …|release" "TESTMAP_BINARY:installed|$S/ait-testmap|release" "$(line "$out" TESTMAP_BINARY:)"
assert_contains "R1 never fatal" "AFTER rc=0" "$out"
assert_eq "R1 the installed binary is the mirror's" "same" "$(cmp -s "$MIR/$ASSET" "$S/ait-testmap" && echo same || echo differs)"
assert_eq "R1 the sidecar verifies with sha256sum -c" "ait-testmap: OK" "$(sumcheck "$S" ait-testmap.sha256)"
assert_file_not_exists "R1 a release slot carries no .dev" "$S/.dev"
assert_eq "R1 staging is cleaned up" "" "$(ls -A "$AH/engine" | grep '^\.staging' || true)"

out="$(AIT_ENGINE_RELEASE_URL="file://$WORK/no-such-mirror" insetup "$AH" 'install_engine_binary')"
assert_eq "R2 an intact verified slot is present with no fetch" "TESTMAP_BINARY:present|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"

BADMIR="$WORK/badmirror"; mkmirror "$BADMIR" bad
printf '%064d  %s\n' 0 "$ASSET" >"$BADMIR/$SUMS"
out="$(AIT_ENGINE_RELEASE_URL="file://$BADMIR" insetup "$WORK/r3" 'install_engine_binary')"
assert_eq "R3 a wrong digest is refused" "TESTMAP_BINARY:checksum-mismatch|$ASSET" "$(line "$out" TESTMAP_BINARY:)"
assert_dir_not_exists "R3 nothing is published on a fresh root" "$(slot_of "$WORK/r3")"
cp -a "$AH" "$WORK/r3b"
out="$(AIT_ENGINE_RELEASE_URL="file://$BADMIR" insetup "$WORK/r3b" 'install_engine_binary --force-engine')"
assert_eq "R3 refused over an existing release too" "TESTMAP_BINARY:checksum-mismatch|$ASSET" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "R3 the existing binary is byte-identical" "same" "$(cmp -s "$MIR/$ASSET" "$(slot_of "$WORK/r3b")/ait-testmap" && echo same || echo differs)"
assert_contains "R3 the existing engine is reported kept" "was left in place" "$out"

NOLINE="$WORK/nolinemirror"; mkmirror "$NOLINE" noline
printf '%s  %s\n' "$(sha "$NOLINE/$ASSET")" "ait-testmap_${V}_plan9_mips" >"$NOLINE/$SUMS"
out="$(AIT_ENGINE_RELEASE_URL="file://$NOLINE" insetup "$WORK/r4" 'install_engine_binary')"
assert_eq "R4 an asset missing from the sums file is refused" "TESTMAP_BINARY:checksum-mismatch|$ASSET" "$(line "$out" TESTMAP_BINARY:)"

mkdir -p "$WORK/emptymirror"
out="$(AIT_ENGINE_RELEASE_URL="file://$WORK/emptymirror" insetup "$WORK/r5" 'install_engine_binary; echo "AFTER rc=$?"')"
assert_eq "R5 fetch-failed names the sums URL" "TESTMAP_BINARY:fetch-failed|file://$WORK/emptymirror/$SUMS" "$(line "$out" TESTMAP_BINARY:)"
assert_contains "R5 ENGINE_MISSING warning" "ENGINE_MISSING:$(slot_of "$WORK/r5")/ait-testmap|" "$out"
assert_contains "R5 never fatal" "AFTER rc=0" "$out"

mkdir -p "$WORK/plan9"
printf '#!/usr/bin/env bash\ncase "${1:-}" in -m) echo x86_64 ;; *) echo Plan9 ;; esac\n' >"$WORK/plan9/uname"
chmod +x "$WORK/plan9/uname"
out="$(PATH="$WORK/plan9:$PATH" insetup "$WORK/r6" 'install_engine_binary')"
assert_eq "R6 an off-matrix platform is reported" "TESTMAP_BINARY:platform-unsupported|Plan9|x86_64" "$(line "$out" TESTMAP_BINARY:)"
assert_dir_not_exists "R6 no slot is written" "$(slot_of "$WORK/r6")"

# --- H: engine_sha256 never hands the tool a file name ---------------------------
echo "--- H: engine_sha256 hashes from stdin (t1970) ---"

# sha256sum/shasum escape a name holding a newline or backslash ('\<hex>  …')
# and option-parse a leading '-'. The helper takes the first tool on PATH, so a
# PATH holding only one tool is the only way to reach the shasum fallback.
HELLO_HEX="5891b5b522d5df086d0ff0b110fbd9d21bb4fc7163af34d08286a2e846f6be03"
NL=$'\n'
HF="$WORK/hfix"
mkdir -p "$HF"
printf 'hello\n' >"$HF/hello"
printf 'hello\n' >"$HF/nl${NL}name.bin"
printf 'hello\n' >"$HF/trail.bin${NL}"
printf 'hello\n' >"$HF/back\\slash.bin"
printf 'hello\n' >"$HF/-dash.bin"
# hsum <bindir> <fn> <args…> — run an engine_install.sh function with PATH=<bindir>.
hsum() {
    bash -c 'warn(){ :; }; source "$1/.aitask-scripts/lib/engine_install.sh"; bin="$2"; shift 2; PATH="$bin" "$@"' \
        _ "$PROJECT_DIR" "$@"
}
for tool in sha256sum shasum; do
    tool_path="$(command -v "$tool" 2>/dev/null)" || tool_path=""
    if [[ -z "$tool_path" ]]; then
        echo "SKIP: H $tool not installed — backend not exercised"
        continue
    fi
    bin="$WORK/hbin_$tool"
    mkdir -p "$bin"
    ln -s "$tool_path" "$bin/$tool"
    assert_eq "H1 $tool: plain name hashes to the known vector" "$HELLO_HEX" "$(hsum "$bin" engine_sha256 "$HF/hello" 2>&1)"
    assert_eq "H2 $tool: name with an embedded newline" "$HELLO_HEX" "$(hsum "$bin" engine_sha256 "$HF/nl${NL}name.bin" 2>&1)"
    assert_eq "H3 $tool: name ending in a newline" "$HELLO_HEX" "$(hsum "$bin" engine_sha256 "$HF/trail.bin${NL}" 2>&1)"
    assert_eq "H4 $tool: name with a backslash" "$HELLO_HEX" "$(hsum "$bin" engine_sha256 "$HF/back\\slash.bin" 2>&1)"
    assert_eq "H5 $tool: relative name starting with '-'" "$HELLO_HEX" "$(cd "$HF" && hsum "$bin" engine_sha256 -dash.bin 2>&1)"
    assert_eq "H6 $tool: engine_file_matches accepts the newline name" "match" \
        "$(hsum "$bin" engine_file_matches "$HF/nl${NL}name.bin" "$HELLO_HEX" 2>&1 && echo match)"
    rc=0; out="$(hsum "$bin" engine_sha256 "$HF/no-such-file" 2>&1)" || rc=$?
    assert_eq "H7 $tool: a missing file fails" "1" "$rc"
    assert_eq "H7 $tool: … silently, printing nothing" "" "$out"
done

# --- D: .dev protection and the slot lock ----------------------------------------
echo "--- D: .dev protection, the publication lock, a fresh root ---"

AH="$WORK/d1"; S="$(slot_of "$AH")"
insetup "$AH" 'install_engine_binary --local-engine "$1"' "$CUSTOM" >/dev/null
out="$(insetup "$AH" 'install_engine_binary')"
assert_eq "D1 a release run leaves a .dev slot alone" "TESTMAP_BINARY:kept-dev|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "D1 the custom bytes are unchanged" "same" "$(cmp -s "$CUSTOM" "$S/ait-testmap" && echo same || echo differs)"

out="$(insetup "$AH" 'install_engine_binary --force-engine')"
assert_eq "D2 --force-engine replaces it with the release" "TESTMAP_BINARY:installed|$S/ait-testmap|release" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "D2 the release bytes are installed" "same" "$(cmp -s "$MIR/$ASSET" "$S/ait-testmap" && echo same || echo differs)"
assert_file_not_exists "D2 the .dev marker is gone" "$S/.dev"
assert_file_exists "D2 the sidecar is written" "$S/ait-testmap.sha256"

insetup "$AH" 'install_engine_binary --local-engine "$1"' "$CUSTOM" >/dev/null
out="$(insetup "$AH" 'install_engine_binary --local-engine "$1"' "$CUSTOM2")"
assert_eq "D3 --local-engine over a .dev slot is refused" "TESTMAP_BINARY:kept-dev|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "D3 the first custom build survives" "same" "$(cmp -s "$CUSTOM" "$S/ait-testmap" && echo same || echo differs)"
out="$(insetup "$AH" 'install_engine_binary --force-engine --local-engine "$1"' "$CUSTOM2")"
assert_eq "D3 … and replaced with --force-engine" "TESTMAP_BINARY:installed|$S/ait-testmap|local" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "D3 the second custom build is installed" "same" "$(cmp -s "$CUSTOM2" "$S/ait-testmap" && echo same || echo differs)"

# D4: a concurrent writer marks the slot between our early check and our lock.
HOOK="$WORK/hook.sh"
cat >"$HOOK" <<EOF
#!/usr/bin/env bash
unset AIT_ENGINE_TEST_PRE_PUBLISH_HOOK
bash -c 'source "$T/.aitask-scripts/aitask_setup.sh" --source-only; install_engine_binary --local-engine "\$1"' _ "$CUSTOM" >"$WORK/hook.out" 2>&1
EOF
chmod +x "$HOOK"
AH="$WORK/d4"; S="$(slot_of "$AH")"
out="$(AIT_ENGINE_TEST_PRE_PUBLISH_HOOK="$HOOK" insetup "$AH" 'install_engine_binary')"
assert_contains "D4 the concurrent writer installed its custom build" "TESTMAP_BINARY:installed|$S/ait-testmap|local" "$(cat "$WORK/hook.out")"
assert_eq "D4 the release install sees the marker under the lock" "TESTMAP_BINARY:kept-dev|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
assert_eq "D4 the custom bytes survive" "same" "$(cmp -s "$CUSTOM" "$S/ait-testmap" && echo same || echo differs)"
assert_file_exists "D4 the .dev marker survives" "$S/.dev"

# Negative control: without the under-lock re-check the same race overwrites it.
cp -R "$T/.aitask-scripts/lib" "$WORK/mutlib"
grep -v 'under-lock .dev re-check (D4)' "$T/.aitask-scripts/lib/engine_install.sh" >"$WORK/mutlib/engine_install.sh"
removed="$(( $(wc -l <"$T/.aitask-scripts/lib/engine_install.sh") - $(wc -l <"$WORK/mutlib/engine_install.sh") ))"
assert_eq "D4 control: exactly the re-check line was removed" "1" "$removed"
AH="$WORK/d4c"; S="$(slot_of "$AH")"
out="$(AIT_ENGINE_TEST_PRE_PUBLISH_HOOK="$HOOK" insetup "$AH" 'source "$1/engine_install.sh"; install_engine_binary' "$WORK/mutlib")"
assert_eq "D4 control: the unguarded publish overwrites the custom build" "same" \
    "$(cmp -s "$MIR/$ASSET" "$S/ait-testmap" && echo same || echo differs)"

# D5: a live holder of the slot lock → slot-busy; a dead one is reclaimed.
AH="$WORK/d5"; S="$(slot_of "$AH")"
mkdir -p "$AH/engine/.locks"
bash -c 'warn(){ :; }; source "$1/stale_lock.sh"; stale_lock_acquire "$2" 5 0.1 holder || exit 1; touch "$3"; sleep 60' \
    _ "$T/.aitask-scripts/lib" "$AH/engine/.locks/v$V" "$WORK/held" &
HOLDER_PID=$!
for _ in $(seq 1 50); do [[ -f "$WORK/held" ]] && break; sleep 0.1; done
assert_file_exists "D5 the holder took the lock" "$WORK/held"
out="$(ENGINE_SLOT_LOCK_RETRIES=5 insetup "$AH" 'install_engine_binary; echo "AFTER rc=$?"')"
assert_eq "D5 a live holder → slot-busy" "TESTMAP_BINARY:slot-busy|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
assert_file_not_exists "D5 nothing was written" "$S/ait-testmap"
assert_contains "D5 never fatal" "AFTER rc=0" "$out"
kill -9 "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; HOLDER_PID=""
assert_dir_exists "D5 the dead holder's lock dir is still there" "$AH/engine/.locks/v$V"
out="$(ENGINE_SLOT_LOCK_RETRIES=20 insetup "$AH" 'install_engine_binary')"
assert_eq "D5 a dead holder's lock is reclaimed" "TESTMAP_BINARY:installed|$S/ait-testmap|release" "$(line "$out" TESTMAP_BINARY:)"

# D6: a lock dir that cannot be prepared is not contention.
AH="$WORK/d6"; S="$(slot_of "$AH")"
mkdir -p "$AH/engine" && : >"$AH/engine/.locks"
out="$(insetup "$AH" 'install_engine_binary; echo "AFTER rc=$?"')"
assert_eq "D6 .locks as a regular file → lock-unavailable (not slot-busy)" \
    "TESTMAP_BINARY:lock-unavailable|$AH/engine/.locks" "$(line "$out" TESTMAP_BINARY:)"
assert_file_not_exists "D6 nothing was published" "$S/ait-testmap"
assert_contains "D6 never fatal" "AFTER rc=0" "$out"

# --- F: failure handling, under both call shapes --------------------------------
echo "--- F: write failures (errexit on, and || true) ---"

MV_FAIL_BIN='mv() { case "${*: -1}" in */ait-testmap) return 1 ;; esac; command mv "$@"; }'
MV_FAIL_SUM='mv() { case "${*: -1}" in *.sha256) return 1 ;; esac; command mv "$@"; }'
BASE_RELEASE="$WORK/r1"   # a verified release slot from R1

for shape in plain or-true; do
    if [[ "$shape" == plain ]]; then call='install_engine_binary'; else call='install_engine_binary || true'; fi

    AH="$WORK/f1-$shape"; cp -a "$BASE_RELEASE" "$AH"; S="$(slot_of "$AH")"
    cp "$S/ait-testmap" "$WORK/f1.bin.before"; cp "$S/ait-testmap.sha256" "$WORK/f1.sum.before"
    NEWMIR="$WORK/newmirror"; rm -rf "$NEWMIR"; mkmirror "$NEWMIR" newer
    out="$(AIT_ENGINE_RELEASE_URL="file://$NEWMIR" insetup "$AH" "$MV_FAIL_BIN; ${call/install_engine_binary/install_engine_binary --force-engine}; echo AFTER")"
    assert_eq "F1[$shape] a failed binary rename → install-failed" "TESTMAP_BINARY:install-failed|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
    assert_not_contains "F1[$shape] no false success line" "TESTMAP_BINARY:installed" "$out"
    assert_eq "F1[$shape] the old binary is byte-identical" "same" "$(cmp -s "$WORK/f1.bin.before" "$S/ait-testmap" && echo same || echo differs)"
    assert_eq "F1[$shape] the old sidecar is byte-identical" "same" "$(cmp -s "$WORK/f1.sum.before" "$S/ait-testmap.sha256" && echo same || echo differs)"
    assert_file_not_exists "F1[$shape] no .dev appeared" "$S/.dev"
    assert_contains "F1[$shape] setup continues" "AFTER" "$out"

    AH="$WORK/f2-$shape"; cp -a "$BASE_RELEASE" "$AH"; S="$(slot_of "$AH")"
    out="$(insetup "$AH" "$MV_FAIL_BIN; ${call/install_engine_binary/install_engine_binary --local-engine \"\$1\"}; echo AFTER" "$CUSTOM")"
    assert_eq "F2[$shape] a failed marked install → install-failed" "TESTMAP_BINARY:install-failed|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
    assert_file_not_exists "F2[$shape] the .dev it created is rolled back" "$S/.dev"
    assert_eq "F2[$shape] the sidecar is restored" "same" "$(cmp -s "$BASE_RELEASE/engine/v$V/ait-testmap.sha256" "$S/ait-testmap.sha256" && echo same || echo differs)"
    assert_eq "F2[$shape] the old binary is intact" "same" "$(cmp -s "$MIR/$ASSET" "$S/ait-testmap" && echo same || echo differs)"
    assert_contains "F2[$shape] setup continues" "AFTER" "$out"

    if [[ "$(id -u)" -ne 0 ]]; then
        AH="$WORK/f3-$shape"; cp -a "$BASE_RELEASE" "$AH"; S="$(slot_of "$AH")"
        chmod 0555 "$S"
        out="$(insetup "$AH" "${call/install_engine_binary/install_engine_binary --local-engine \"\$1\"}; echo AFTER" "$CUSTOM")"
        chmod 0755 "$S"
        assert_eq "F3[$shape] a read-only slot → install-failed" "TESTMAP_BINARY:install-failed|$S/ait-testmap" "$(line "$out" TESTMAP_BINARY:)"
        assert_eq "F3[$shape] nothing changed" "same" "$(cmp -s "$MIR/$ASSET" "$S/ait-testmap" && echo same || echo differs)"
        assert_file_not_exists "F3[$shape] no .dev" "$S/.dev"
        assert_contains "F3[$shape] setup continues" "AFTER" "$out"
    else
        echo "SKIP: F3[$shape] (running as root: chmod 0555 does not restrict)"
    fi

    AH="$WORK/f4-$shape"; S="$(slot_of "$AH")"
    out="$(insetup "$AH" "$MV_FAIL_SUM; $call; echo AFTER")"
    assert_contains "F4[$shape] a failed sidecar write is reported" "TESTMAP_BINARY:sidecar-not-written|$S/ait-testmap.sha256" "$out"
    assert_contains "F4[$shape] … but the verified binary is installed" "TESTMAP_BINARY:installed|$S/ait-testmap|release" "$out"
    assert_file_not_exists "F4[$shape] no sidecar" "$S/ait-testmap.sha256"
    out="$(AIT_ENGINE_RELEASE_URL="file://$WORK/no-such-mirror" insetup "$AH" 'install_engine_binary')"
    assert_not_contains "F4[$shape] without a sidecar the next run is not 'present'" "TESTMAP_BINARY:present" "$out"
    assert_contains "F4[$shape] … and keeps the installed engine" "was left in place" "$out"
done

# --- P: a directory at a publication destination ----------------------------------
echo "--- P: directory destinations are refused, in every publish mode ---"

# mv onto a directory nests the source inside it and succeeds; each case asserts
# the refusal, that nothing landed inside the directory, and unchanged metadata.
AH="$WORK/p1"; S="$(slot_of "$AH")"; mkdir -p "$S/ait-testmap" && : >"$S/ait-testmap/keep"
out="$(insetup "$AH" 'install_engine_binary; echo AFTER')"
assert_contains "P1 release onto a directory → slot-invalid" "TESTMAP_BINARY:slot-invalid|$S" "$out"
assert_not_contains "P1 no false success line" "TESTMAP_BINARY:installed" "$out"
assert_eq "P1 nothing nested inside the directory" "keep" "$(ls -A "$S/ait-testmap")"
assert_file_not_exists "P1 no sidecar written" "$S/ait-testmap.sha256"
assert_contains "P1 setup continues" "AFTER" "$out"

AH="$WORK/p2"; S="$(slot_of "$AH")"; mkdir -p "$S/ait-testmap" && : >"$S/.dev"
out="$(insetup "$AH" 'install_engine_binary --force-engine')"
assert_contains "P2 a forced release onto a directory → slot-invalid" "TESTMAP_BINARY:slot-invalid|$S" "$out"
assert_file_exists "P2 … and the .dev marker is NOT cleared" "$S/.dev"
assert_eq "P2 nothing nested inside the directory" "" "$(ls -A "$S/ait-testmap")"

AH="$WORK/p3"; S="$(slot_of "$AH")"; mkdir -p "$S/ait-testmap"
out="$(insetup "$AH" 'install_engine_binary --local-engine "$1"' "$CUSTOM")"
assert_contains "P3 a marked (local) install onto a directory → slot-invalid" "TESTMAP_BINARY:slot-invalid|$S" "$out"
assert_file_not_exists "P3 no .dev marker was created" "$S/.dev"
assert_eq "P3 nothing nested inside the directory" "" "$(ls -A "$S/ait-testmap")"

AH="$WORK/p4"; S="$(slot_of "$AH")"; mkdir -p "$S" "$WORK/p4-target" && ln -s "$WORK/p4-target" "$S/ait-testmap"
out="$(insetup "$AH" 'install_engine_binary --local-engine "$1"' "$CUSTOM")"
assert_contains "P4 a symlink to a directory → slot-invalid" "TESTMAP_BINARY:slot-invalid|$S" "$out"
assert_eq "P4 nothing landed in the link's target" "" "$(ls -A "$WORK/p4-target")"
AH="$WORK/p4b"; S="$(slot_of "$AH")"; mkdir -p "$S/ait-testmap.sha256"
out="$(insetup "$AH" 'install_engine_binary')"
assert_contains "P4 a directory where the sidecar belongs → slot-invalid" "TESTMAP_BINARY:slot-invalid|$S" "$out"
assert_file_not_exists "P4 … and the binary was not published" "$S/ait-testmap"

AH="$WORK/p5"; mkdir -p "$AH/engine/dev/ait-testmap"; cp "$CUSTOM" "$WORK/p5.staged"
res="$(AITASKS_HOME="$AH" bash -c 'warn(){ :; }; source "$1/.aitask-scripts/lib/engine_install.sh"; rc=0; engine_publish_locked devslot "$2" "$AITASKS_HOME/engine/dev" 0 || rc=$?; echo "$rc"' _ "$T" "$WORK/p5.staged" 2>/dev/null)"
assert_eq "P5 the dev slot refuses a directory too (rc 3)" "3" "$res"
assert_eq "P5 nothing nested inside the directory" "" "$(ls -A "$AH/engine/dev/ait-testmap")"

# P6: a slot on a different filesystem from the staging dir is refused — made
# deterministic with a stat() override that reports another device for the slot.
AH="$WORK/p6"; S="$(slot_of "$AH")"
FAKE_STAT='stat() { case "${*: -1}" in */engine/v*) echo 4242 ;; *) command stat "$@" ;; esac; }'
out="$(insetup "$AH" "$FAKE_STAT; install_engine_binary; echo AFTER")"
assert_eq "P6 a cross-device slot → slot-cross-device" "TESTMAP_BINARY:slot-cross-device|$S" "$(line "$out" TESTMAP_BINARY:)"
assert_file_not_exists "P6 nothing was published" "$S/ait-testmap"
assert_contains "P6 setup continues" "AFTER" "$out"
out="$(insetup "$AH" 'stat() { return 1; }; install_engine_binary --local-engine "$1"' "$CUSTOM")"
assert_eq "P6 an unknowable device id is refused too (fail closed)" "TESTMAP_BINARY:slot-cross-device|$S" "$(line "$out" TESTMAP_BINARY:)"
assert_file_not_exists "P6 … with no .dev created" "$S/.dev"

# P7: the same with a REAL second filesystem, when one is writable here.
OTHER_FS=""
for cand in /dev/shm "${TMPDIR:-/tmp}" /tmp /var/tmp "$HOME"; do
    [[ -d "$cand" && -w "$cand" ]] || continue
    if [[ "$(stat -c %d "$cand" 2>/dev/null || stat -f %d "$cand")" != "$(stat -c %d "$WORK" 2>/dev/null || stat -f %d "$WORK")" ]]; then
        OTHER_FS="$cand"; break
    fi
done
if [[ -n "$OTHER_FS" ]]; then
    XDIR="$(mktemp -d "$OTHER_FS/ait-engine-xdev.XXXXXX")"
    AH="$WORK/p7"; mkdir -p "$AH/engine" && ln -s "$XDIR" "$AH/engine/v$V"
    out="$(insetup "$AH" 'install_engine_binary')"
    assert_eq "P7 a slot linked onto another filesystem is refused" "TESTMAP_BINARY:slot-cross-device|$AH/engine/v$V" "$(line "$out" TESTMAP_BINARY:)"
    assert_eq "P7 nothing landed on the other filesystem" "" "$(ls -A "$XDIR")"
    rm -rf "$XDIR"
else
    echo "SKIP: P7 (no writable second filesystem found)"
fi

# --- S: the source tier ----------------------------------------------------------
echo "--- S: --engine-from-source ---"

out="$(AIT_TESTMAP_FETCH=0 insetup "$WORK/s1" 'install_engine_binary --engine-from-source')"
assert_eq "S1 no Go source in an installed project" "TESTMAP_BINARY:no-source|$T/goengines/build.sh" "$(line "$out" TESTMAP_BINARY:)"

if command -v go >/dev/null 2>&1; then
    AH="$WORK/s2"; S="$(slot_of "$AH")"
    out="$(HOME="$WORK/home" AITASKS_HOME="$AH" AIT_TESTMAP_FETCH=0 \
        bash -c 'source "$1/.aitask-scripts/aitask_setup.sh" --source-only; install_engine_binary --engine-from-source' _ "$PROJECT_DIR" 2>&1)"
    assert_eq "S2 a framework checkout builds from source" "TESTMAP_BINARY:installed|$S/ait-testmap|source" "$(line "$out" TESTMAP_BINARY:)"
    assert_eq "S2 the real engine reports the framework version" "VERSION:$V" "$("$S/ait-testmap" version 2>/dev/null | head -n1)"
    assert_file_exists "S2 a source build is .dev-marked" "$S/.dev"
else
    echo "SKIP: S2 (go not installed)"
fi

# --- T: TESTMAP:<state> ----------------------------------------------------------
echo "--- T: report_testmap_state ---"

out="$(insetup "$WORK/t-empty" 'report_testmap_state')"
assert_eq "T1 no engine → TESTMAP:engine-missing" "TESTMAP:engine-missing" "$(line "$out" TESTMAP:)"
assert_contains "T1 the resolver's diagnostic is shown" "ENGINE_MISSING:$(slot_of "$WORK/t-empty")/ait-testmap|" "$out"
out="$(insetup "$WORK/r1" 'report_testmap_state')"
assert_eq "T2 engine but no aitestmap/config.yaml → absent" "TESTMAP:absent|run /aitask-testmap-onboard" "$(line "$out" TESTMAP:)"
mkdir -p "$T/aitestmap" && echo "contract: 1" >"$T/aitestmap/config.yaml"
out="$(insetup "$WORK/r1" 'report_testmap_state')"
rm -rf "$T/aitestmap"
assert_eq "T3 aitestmap/config.yaml → onboarded" "TESTMAP:onboarded" "$(line "$out" TESTMAP:)"

# --- W: main() wiring, bounded ----------------------------------------------------
echo "--- W: main() parses the flags and calls the two steps in order ---"

# Every setup function is stubbed `return 1` (offline, prompt-free) except main,
# the loggers and three logging stubs. Cf. tests/test_aitasks_home.sh T8.
run_main() {
    HOME="$WORK/home" AITASKS_HOME="$WORK/w" AIT_INVOCATION_PWD="$WORK/inv" T="$T" bash -c '
        source "$T/.aitask-scripts/aitask_setup.sh" --source-only
        set +euo pipefail
        for fn in $(compgen -A function); do
            case "$fn" in main|info|success|warn|die) continue ;; esac
            eval "$fn() { return 1; }"
        done
        install_global_shim()   { echo "CALL:install_global_shim"; }
        install_engine_binary() { echo "CALL:install_engine_binary:$*"; }
        report_testmap_state()  { echo "CALL:report_testmap_state"; }
        main "$@"' _ "$@" 2>&1
}
mkdir -p "$WORK/inv" && : >"$WORK/inv/rel-engine"
out="$(run_main --local-engine rel-engine --force-engine)"
assert_eq "W1 the flags reach install_engine_binary, the path made absolute" \
    "CALL:install_engine_binary:--local-engine $WORK/inv/rel-engine --force-engine" "$(line "$out" CALL:install_engine_binary)"
n_shim="$(printf '%s\n' "$out" | grep -n '^CALL:install_global_shim' | cut -d: -f1)"
n_eng="$(printf '%s\n' "$out" | grep -n '^CALL:install_engine_binary' | cut -d: -f1)"
n_rep="$(printf '%s\n' "$out" | grep -n '^CALL:report_testmap_state' | cut -d: -f1)"
assert_eq "W1 order: shim < engine < report" "yes" \
    "$([[ -n "$n_shim" && "$n_shim" -lt "$n_eng" && "$n_eng" -lt "$n_rep" ]] && echo yes || echo no)"
out="$(run_main --no-testmap --local-engine rel-engine)"
assert_contains "W2 --no-testmap with --local-engine dies" "--no-testmap cannot be combined" "$out"
assert_not_contains "W2 … before any step runs" "CALL:" "$out"
out="$(run_main --local-engine missing-file)"
assert_contains "W2 a missing --local-engine file dies" "no such file: missing-file" "$out"
out="$(run_main)"
assert_eq "W3 no flags → a bare call" "CALL:install_engine_binary:" "$(line "$out" CALL:install_engine_binary)"

# --- G: the .aitask-testmap/ gitignore rule ----------------------------------------
echo "--- G: setup_testmap_gitignore ---"

G="$WORK/g"
mkdir -p "$G/.aitask-scripts"
git -C "$G" init -q && : >"$G/seed" && git -C "$G" add seed && git -C "$G" commit -qm seed
: >"$G/other.txt" && git -C "$G" add other.txt
gsetup() { HOME="$WORK/home" T="$T" bash -c 'source "$T/.aitask-scripts/aitask_setup.sh" --source-only; SCRIPT_DIR="$1/.aitask-scripts"; setup_testmap_gitignore' _ "$G" >/dev/null 2>&1; }
gsetup
assert_eq "G1 the rule is added once" "1" "$(grep -cxF '.aitask-testmap/' "$G/.gitignore")"
assert_eq "G1 the commit names only .gitignore" ".gitignore" "$(git -C "$G" show --name-only --format= HEAD)"
assert_eq "G1 a pre-staged foreign file stays staged, uncommitted" "other.txt" "$(git -C "$G" diff --cached --name-only)"
head_before="$(git -C "$G" rev-parse HEAD)"
gsetup
assert_eq "G1 a re-run is a no-op (still one line)" "1" "$(grep -cxF '.aitask-testmap/' "$G/.gitignore")"
assert_eq "G1 a re-run commits nothing" "$head_before" "$(git -C "$G" rev-parse HEAD)"

# --- E: ait engine ------------------------------------------------------------------
echo "--- E: aitask_engine.sh ---"

ENG="$T/.aitask-scripts/aitask_engine.sh"
TNAME="$(basename "$T")"
# mkproject <dir> <framework VERSION content> [root VERSION] — a registered project.
mkproject() {
    mkdir -p "$1/aitasks/metadata" "$1/.aitask-scripts"
    : >"$1/aitasks/metadata/project_config.yaml"
    printf '%s' "$2" >"$1/.aitask-scripts/VERSION"
    [[ -n "${3:-}" ]] && printf '%s\n' "$3" >"$1/VERSION"
    return 0
}
REG="$WORK/projects.yaml"
printf 'projects:\n  - name: alpha\n    path: %s\n  - name: gone\n    path: %s\n' "$WORK/pa" "$WORK/missing" >"$REG"
mkproject "$WORK/pa" $'1.0.0\n'
# mkslots <AH> — v1.0.0, v2.0.0, v3.0.0 (.dev), v<current V>, dev/.
mkslots() {
    local s
    for s in v1.0.0 v2.0.0 v3.0.0 "v$V" dev; do mkdir -p "$1/engine/$s" && echo "$s" >"$1/engine/$s/ait-testmap"; done
    : >"$1/engine/v3.0.0/.dev"
}
eng() { local ah="$1"; shift; AITASKS_HOME="$ah" AITASKS_PROJECTS_INDEX="$REG" bash "$ENG" "$@" 2>&1; }
slots() { (cd "$1/engine" && ls -d v* dev 2>/dev/null | LC_ALL=C sort | tr '\n' ' '); }

AH="$WORK/e1"; mkslots "$AH"
out="$(eng "$AH" prune --dry-run)"; rc=$?
assert_exit_zero_rc "E1 --dry-run exits 0" "$rc"
assert_eq "E1 --dry-run would remove only the unused v2.0.0" "PRUNE_WOULD:$AH/engine/v2.0.0" "$(line "$out" PRUNE_WOULD:)"
assert_eq "E1 --dry-run removes nothing" "dev v$V v1.0.0 v2.0.0 v3.0.0 " "$(slots "$AH")"
assert_contains "E1 v1.0.0 kept for the registered project" "PRUNE_KEPT:$AH/engine/v1.0.0|alpha" "$out"
assert_contains "E1 v<V> kept for the current project" "PRUNE_KEPT:$AH/engine/v$V|$TNAME" "$out"
assert_contains "E1 v3.0.0 kept as a custom build" "PRUNE_KEPT:$AH/engine/v3.0.0|dev-marked" "$out"
out="$(eng "$AH" prune)"
assert_eq "E1 prune removes exactly v2.0.0" "PRUNED:$AH/engine/v2.0.0" "$(line "$out" PRUNED:)"
assert_eq "E1 the rest survive" "dev v$V v1.0.0 v3.0.0 " "$(slots "$AH")"
out="$(eng "$AH" prune --force)"
assert_eq "E1 --force also removes the unused .dev slot" "PRUNED:$AH/engine/v3.0.0" "$(line "$out" PRUNED:)"
assert_eq "E1 dev/ and the kept versions remain" "dev v$V v1.0.0 " "$(slots "$AH")"

AH="$WORK/e2"; mkslots "$AH"
out="$(AITASKS_HOME="$AH" AITASKS_PROJECTS_INDEX="$WORK/no-registry.yaml" bash "$ENG" prune 2>&1)"; rc=$?
assert_exit_nonzero_rc "E2 no registry → exit 1" "$rc"
assert_eq "E2 no registry → PRUNE_REFUSED:no-registry" "PRUNE_REFUSED:no-registry|$WORK/no-registry.yaml" "$(line "$out" PRUNE_REFUSED:)"
for c in "unreadable:" "invalid:" "invalid:1 2" $'invalid:\r'; do
    kind="${c%%:*}"; body="${c#*:}"
    if [[ "$kind" == unreadable ]]; then rm -f "$WORK/pa/.aitask-scripts/VERSION"; else printf '%s' "$body" >"$WORK/pa/.aitask-scripts/VERSION"; fi
    out="$(eng "$AH" prune --force)"; rc=$?
    assert_exit_nonzero_rc "E2 version-$kind ($(printf '%q' "$body")) → exit 1" "$rc"
    assert_eq "E2 version-$kind ($(printf '%q' "$body")) is refused" "PRUNE_REFUSED:version-$kind|$WORK/pa/.aitask-scripts/VERSION" "$(line "$out" PRUNE_REFUSED:)"
    assert_eq "E2 version-$kind ($(printf '%q' "$body")): nothing removed" "dev v$V v1.0.0 v2.0.0 v3.0.0 " "$(slots "$AH")"
done
mkproject "$WORK/pa" $'1.0.0\n' "9.9.9"

AH="$WORK/e2b"; mkdir -p "$AH/engine/v1.0.0" "$AH/engine/v9.9.9"
out="$(eng "$AH" prune)"
assert_eq "E2b the root VERSION (9.9.9) never keeps a slot" "PRUNED:$AH/engine/v9.9.9" "$(line "$out" PRUNED:)"
assert_contains "E2b .aitask-scripts/VERSION (1.0.0) does" "PRUNE_KEPT:$AH/engine/v1.0.0|alpha" "$out"

AH="$WORK/e5"; mkslots "$AH"
assert_dir_not_exists "E5 precondition: no .locks on this root" "$AH/engine/.locks"
mkdir -p "$AH/engine/.locks"
bash -c 'warn(){ :; }; source "$1/stale_lock.sh"; stale_lock_acquire "$2" 5 0.1 holder || exit 1; touch "$3"; sleep 60' \
    _ "$T/.aitask-scripts/lib" "$AH/engine/.locks/v2.0.0" "$WORK/held5" &
HOLDER_PID=$!
for _ in $(seq 1 50); do [[ -f "$WORK/held5" ]] && break; sleep 0.1; done
out="$(ENGINE_SLOT_LOCK_RETRIES=5 eng "$AH" prune --force)"
assert_contains "E5 a held slot is kept as busy" "PRUNE_KEPT:$AH/engine/v2.0.0|busy" "$out"
assert_dir_exists "E5 … and survives" "$AH/engine/v2.0.0"
assert_contains "E5 an unheld unused slot is still pruned" "PRUNED:$AH/engine/v3.0.0" "$out"
kill -9 "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; HOLDER_PID=""
AH="$WORK/e5b"; mkdir -p "$AH/engine/v2.0.0"
out="$(eng "$AH" prune)"
assert_eq "E5 a fresh root (no .locks/) prunes" "PRUNED:$AH/engine/v2.0.0" "$(line "$out" PRUNED:)"

# E6: removal is verified UNDER the lock. A publisher recreating the slot right
# after the lock is released must not turn a successful prune into a failure.
cat >"$WORK/recreate.sh" <<'EOF2'
#!/usr/bin/env bash
mkdir -p "$(dirname "$(dirname "$1")")/$(basename "$1")"
EOF2
chmod +x "$WORK/recreate.sh"
AH="$WORK/e6"; mkdir -p "$AH/engine/v2.0.0"
out="$(AIT_ENGINE_TEST_POST_UNLOCK_HOOK="$WORK/recreate.sh" eng "$AH" prune)"; rc=$?
assert_exit_zero_rc "E6 a slot recreated after the unlock is not a prune failure" "$rc"
assert_eq "E6 … the slot is reported PRUNED" "PRUNED:$AH/engine/v2.0.0" "$(line "$out" PRUNED:)"
assert_dir_exists "E6 (the hook really did recreate it)" "$AH/engine/v2.0.0"
# Negative control: verifying after the unlock reports the false failure.
cp "$ENG" "$WORK/eng-late-check.sh"
python3 - "$WORK/eng-late-check.sh" "$T/.aitask-scripts" <<'EOF2'
import re, sys
p = sys.argv[1]; s = open(p).read()
# The copy lives outside the tree: point it back at the installed scripts.
s = re.sub(r'(?m)^SCRIPT_DIR=.*$', lambda m: 'SCRIPT_DIR="%s"' % sys.argv[2], s, count=1)
old = """        rm -rf -- "$dir" 2>/dev/null || true
        if [[ -e "$dir" ]]; then
            engine_slot_unlock
"""
new = """        rm -rf -- "$dir" 2>/dev/null || true
        engine_slot_unlock
        if [[ -e "$dir" ]]; then
"""
assert s.count(old) == 1
open(p, "w").write(s.replace(old, new))
EOF2
AH="$WORK/e6c"; mkdir -p "$AH/engine/v2.0.0"
out="$(AITASKS_HOME="$AH" AITASKS_PROJECTS_INDEX="$REG" AIT_ENGINE_TEST_POST_UNLOCK_HOOK="$WORK/recreate.sh" bash "$WORK/eng-late-check.sh" prune 2>&1)"
assert_contains "E6 control: a check after the unlock reports PRUNE_FAILED" "PRUNE_FAILED:$AH/engine/v2.0.0|not-removed" "$out"

out="$(eng "$WORK/e3" bogus)"; rc=$?
assert_eq "E3 unknown verb → exit 64" "64" "$rc"
assert_contains "E3 unknown verb is named" "UNKNOWN_VERB:bogus" "$out"
mkdir -p "$WORK/e3home"
out="$(HOME="$WORK/e3home" eng "$WORK/e3" home)"; rc=$?
assert_exit_zero_rc "E3 'home' is a verb (M1.6) → exit 0" "$rc"
assert_contains "E3 … and reports the root" "HOME_ROOT:$WORK/e3" "$out"
out="$(HOME="$WORK/e3home" eng "$WORK/e3" home --bogus)"; rc=$?
assert_eq "E3 'home' with a bad argument → exit 64" "64" "$rc"
out="$(eng "$WORK/e3" build)"; rc=$?
assert_eq "E3 build without goengines/ → exit 3" "3" "$rc"
assert_contains "E3 … ENGINE_SOURCE_MISSING" "ENGINE_SOURCE_MISSING:" "$out"

if command -v go >/dev/null 2>&1; then
    AH="$WORK/e4"
    out="$(AITASKS_HOME="$AH" bash "$PROJECT_DIR/.aitask-scripts/aitask_engine.sh" build 2>/dev/null)"; rc=$?
    assert_exit_zero_rc "E4 ait engine build exits 0" "$rc"
    assert_contains_re "E4 ENGINE_BUILT with a <V>-dev+<40 hex> version" "^ENGINE_BUILT:$AH/engine/dev/ait-testmap[|]${V//./[.]}-dev[+][0-9a-f]{40}$" "$out"
    res="$(AITASKS_HOME="$AH" AIT_ENGINE=dev bash -c 'source "$1/.aitask-scripts/aitask_testmap.sh" --source-only; rc=0; testmap_resolve_engine || rc=$?; echo "$rc"' _ "$PROJECT_DIR" 2>/dev/null)"
    assert_eq "E4 the dev slot passes the shim's dev handshake" "0" "$res"
else
    echo "SKIP: E4 (go not installed)"
fi

# E7: `ait engine test` runs the hang-guard preflight alone, between vet and
# the suite, and a failing preflight never starts the suite (t1998). go is a
# stub that logs its directory and arguments; preflight.sh is the real one.
E7="$WORK/e7"
mkdir -p "$E7/goengines/ci" "$E7/bin"
cp -R "$T/.aitask-scripts" "$E7/.aitask-scripts"
: >"$E7/goengines/build.sh"
cp -p "$PROJECT_DIR/goengines/ci/preflight.sh" "$E7/goengines/ci/preflight.sh"
cat >"$E7/bin/go" <<'EOF'
#!/usr/bin/env bash
printf '%s|%s\n' "$PWD" "$*" >>"$E7_LOG"
[[ -n "${E7_FAIL_PREFLIGHT:-}" && "$*" == *TestIsolationTripwire* ]] && exit 1
exit 0
EOF
chmod +x "$E7/bin/go"
G="$(cd "$E7/goengines" && pwd)"
want="$G|vet ./...
$G|test -count=1 -run ^TestIsolationTripwire(Catches|Imports)?\$ ./internal/testsupport/hangguard/
$G|test ./... -short"
out="$(E7_LOG="$E7/log" PATH="$E7/bin:$PATH" bash "$E7/.aitask-scripts/aitask_engine.sh" test -short 2>&1)"; rc=$?
assert_exit_zero_rc_out "E7 ait engine test exits 0 when every step passes" "$rc" "$out"
assert_eq "E7 vet, then the preflight alone, then the suite with the caller's args" "$want" "$(cat "$E7/log" 2>/dev/null)"
rm -f "$E7/log"
out="$(E7_LOG="$E7/log" E7_FAIL_PREFLIGHT=1 PATH="$E7/bin:$PATH" bash "$E7/.aitask-scripts/aitask_engine.sh" test 2>&1)"; rc=$?
assert_exit_nonzero_rc "E7 a failing preflight fails ait engine test" "$rc"
assert_contains "E7 … the preflight ran" "TestIsolationTripwire" "$(cat "$E7/log" 2>/dev/null)"
assert_not_contains "E7 … and the suite never started" "|test ./..." "$(cat "$E7/log" 2>/dev/null)"

# E7b: with goengines/EXPORT.txt (export mode) `ait engine test` runs the
# export integrity check, then the drift report, and never the preflight or
# the suite, which are not in an exported tree (t2138). The integrity script
# is a stub that logs its verb.
E7B="$WORK/e7b"
mkdir -p "$E7B/goengines" "$E7B/.github/scripts" "$E7B/bin"
cp -R "$T/.aitask-scripts" "$E7B/.aitask-scripts"
: >"$E7B/goengines/build.sh"
: >"$E7B/goengines/EXPORT.txt"
cat >"$E7B/.github/scripts/goengines_integrity.sh" <<'EOF'
#!/usr/bin/env bash
printf 'integrity|%s\n' "$*" >>"$E7_LOG"
[[ -n "${E7B_FAIL_CHECK:-}" && "$1" == check ]] && exit 1
exit 0
EOF
cp "$E7/bin/go" "$E7B/bin/go"
G="$(cd "$E7B/goengines" && pwd)"
want="integrity|check --dir $G
integrity|drift --dir $G"
out="$(E7_LOG="$E7B/log" PATH="$E7B/bin:$PATH" bash "$E7B/.aitask-scripts/aitask_engine.sh" test 2>&1)"; rc=$?
assert_exit_zero_rc_out "E7b ait engine test exits 0 in export mode when the checks pass" "$rc" "$out"
assert_eq "E7b export mode: the integrity check, then the drift report, and no go invocation" "$want" "$(cat "$E7B/log" 2>/dev/null)"
rm -f "$E7B/log"
out="$(E7_LOG="$E7B/log" PATH="$E7B/bin:$PATH" bash "$E7B/.aitask-scripts/aitask_engine.sh" test -short 2>&1)"; rc=$?
assert_contains "E7b go test arguments are reported as ignored" "ignoring go test arguments in export mode: -short" "$out"
assert_not_contains "E7b … and never reach go" "|test" "$(cat "$E7B/log" 2>/dev/null)"
rm -f "$E7B/log"
out="$(E7_LOG="$E7B/log" E7B_FAIL_CHECK=1 PATH="$E7B/bin:$PATH" bash "$E7B/.aitask-scripts/aitask_engine.sh" test 2>&1)"; rc=$?
assert_exit_nonzero_rc "E7b a failing integrity check fails ait engine test" "$rc"
assert_not_contains "E7b … and the drift report does not run after it" "integrity|drift" "$(cat "$E7B/log" 2>/dev/null)"

# --- footer ---------------------------------------------------------------------
assert_counters_load
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
