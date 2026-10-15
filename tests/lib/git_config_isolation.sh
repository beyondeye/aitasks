#!/usr/bin/env bash
# git_config_isolation.sh - keep developer git config out of a test (t1792, t1987).
#
# Side-effect free: sourcing defines functions only, so a test that needs the
# isolation without the rest of tests/lib/sync_fixture.sh (its mktemp base, EXIT
# trap and tmux socket export) can source this file alone.

# Developer git config never reaches a sweep (t1792): a merge.autoStash /
# rebase.autoStash (or a core.hooksPath, an excludesFile, ...) in the global or
# system config would run under every sync test, and can both hide a defect and
# invent one. setup_repo's per-repo user.* settings are repository config and
# still apply. Call it INSIDE the subshell that runs aitask_sync.sh — every
# wrapper that runs the script directly does, not only run_sync — or at file
# scope, before the first fixture, to isolate a whole test file.
sync_isolate_git_config() {
    export GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1
}

# assert_git_config_isolated — prove THIS shell's isolation holds against a
# global and a system config the check plants itself, so the verdict does not
# depend on what the developer's machine happens to carry. Each probe is paired
# with a control showing the planted file IS read once that one isolation
# variable is removed for that one command; only the probe commands carry the
# HOME / XDG_CONFIG_HOME / GIT_CONFIG_SYSTEM overrides, so no fixture changes.
#
# Requires tests/lib/asserts.sh, and must run AFTER the file's PASS/FAIL/TOTAL
# initialisation: an assertion made before it is erased, and the footer's FAIL
# guard would then pass a failed probe. Run it from a directory outside any
# repository (enter_scratch_cwd), so `git config --get` reads only the system,
# global and environment scopes. GIT_CONFIG_SYSTEM needs git >= 2.32.
assert_git_config_isolated() {
    local d
    d="$(mktemp -d "${TMPDIR:-/tmp}/ait_gitiso_XXXXXX")" \
        || { assert_eq "git isolation probe: mktemp" "ok" "failed"; return 0; }
    mkdir -p "$d/home"
    printf '[aitTripwire]\n\tglobal = visible\n' > "$d/home/.gitconfig"
    printf '[aitTripwire]\n\tsystem = visible\n' > "$d/sysconfig"
    assert_eq "git isolation control: a planted global config is read without isolation" "visible" \
        "$(env -u GIT_CONFIG_GLOBAL HOME="$d/home" XDG_CONFIG_HOME="$d/xdg" git config --get aitTripwire.global 2>/dev/null)"
    assert_eq "git isolation: a planted global config never reaches this file" "" \
        "$(HOME="$d/home" XDG_CONFIG_HOME="$d/xdg" git config --get aitTripwire.global 2>/dev/null)"
    assert_eq "git isolation control: a planted system config is read without isolation" "visible" \
        "$(env -u GIT_CONFIG_NOSYSTEM GIT_CONFIG_SYSTEM="$d/sysconfig" git config --get aitTripwire.system 2>/dev/null)"
    assert_eq "git isolation: a planted system config never reaches this file" "" \
        "$(GIT_CONFIG_SYSTEM="$d/sysconfig" git config --get aitTripwire.system 2>/dev/null)"
    rm -rf "$d"
}
