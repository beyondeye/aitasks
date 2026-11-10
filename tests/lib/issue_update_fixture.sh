#!/usr/bin/env bash
# issue_update_fixture.sh - shared fixture for the aitask_issue_update.sh tests
# (t2261_1): PATH stubs for gh / glab / bkt that log their exact argv, a scratch
# legacy-mode repo holding a GitHub and a GitLab task, and a runner.
#
# Requires, from the sourcing test file:
#   PROJECT_DIR   repo root
#   TMP           a scratch directory the test owns and removes
#
# Every stub call appends ONE line to $STUB_LOG: `printf '%q '` of the command
# name and its argv. A multi-line comment body therefore stays on one line and
# the comparison is byte-exact. Render expectations with ifx_render, which uses
# the same encoding.
#
# Stub behaviour:
#   `<cli> auth status`        exits 0
#   STUB_FAIL=<subcommand>     `<cli> issue <subcommand> …` exits 1
#   anything else              exits 0

IFX_UPDATE="$PROJECT_DIR/.aitask-scripts/aitask_issue_update.sh"
IFX_BIN="$TMP/bin"
STUB_LOG="$TMP/stub.log"
export STUB_LOG

ifx_write_stubs() {
    local cli
    mkdir -p "$IFX_BIN"
    for cli in gh glab bkt; do
        cat > "$IFX_BIN/$cli" <<'EOF'
#!/usr/bin/env bash
{ printf '%q ' "$(basename "$0")" "$@"; printf '\n'; } >> "${STUB_LOG:?}"
if [[ "${1:-}" == "auth" ]]; then exit 0; fi
if [[ -n "${STUB_FAIL:-}" && "${2:-}" == "$STUB_FAIL" ]]; then exit 1; fi
exit 0
EOF
        chmod +x "$IFX_BIN/$cli"
    done
    : > "$STUB_LOG"
}

# ifx_task <repo> <task_id> <issue_url> — write aitasks/t<id>_x.md.
ifx_task() {
    printf -- '---\nstatus: Done\nissue: %s\n---\nTask %s.\n' "$3" "$2" \
        > "$1/aitasks/t${2}_x.md"
}

# ifx_make_repo <dir> — a legacy-mode repo (no .aitask-data, no origin) with
# t10 → a GitHub issue, t20 → a gitlab.com issue, and one `(tN)` code commit
# for each, so the comment body has an "Associated Commits" section.
ifx_make_repo() {
    local d="$1"
    mkdir -p "$d/aitasks"
    git -C "$d" init -q -b main
    git -C "$d" config user.email t@example.com
    git -C "$d" config user.name Test
    git -C "$d" config commit.gpgsign false
    ifx_task "$d" 10 "https://github.com/o/r/issues/7"
    ifx_task "$d" 20 "https://gitlab.com/g/p/-/issues/9"
    git -C "$d" add -A
    git -C "$d" commit -qm "ait: Add tasks"
    echo x > "$d/x.txt"
    git -C "$d" add x.txt
    git -C "$d" commit -qm "feature: x (t10)"
    echo y > "$d/y.txt"
    git -C "$d" add y.txt
    git -C "$d" commit -qm "feature: y (t20)"
}

# ifx_render <argv…> — the stub log encoding of one call (no trailing newline).
ifx_render() { printf '%q ' "$@"; }

# ifx_body <repo> <task_id> — the comment body build_comment_body produces for
# a task with no plan file: header, blank line, then the commit block. Command
# substitution strips the trailing newlines exactly as the script's own
# `comment_body=$(build_comment_body …)` does.
ifx_body() {
    local commits body
    commits="$(git -C "$1" log --oneline --all --grep="(t${2})")"
    body="## Resolved via aitask t${2}"$'\n'
    body+=$'\n'"### Associated Commits"$'\n'
    body+=$'\n''```'
    body+=$'\n'"$commits"
    body+=$'\n''```'$'\n'
    printf '%s' "$body"
}

# ifx_run <repo> <args…> — run the REAL script with cwd = <repo> and the stubs
# first on PATH. Resets the stub log first. Sets IFX_RC, IFX_OUT, IFX_ERR.
ifx_run() {
    local repo="$1"; shift
    : > "$STUB_LOG"
    IFX_RC=0
    ( cd "$repo" && PATH="$IFX_BIN:$PATH" "$IFX_UPDATE" "$@" ) \
        > "$TMP/ifx.out" 2> "$TMP/ifx.err" || IFX_RC=$?
    IFX_OUT="$(cat "$TMP/ifx.out")"
    IFX_ERR="$(cat "$TMP/ifx.err")"
}

# ifx_log_line <n> — line n of the stub log ("" when absent).
ifx_log_line() { sed -n "${1}p" "$STUB_LOG"; }

# ifx_log_count — number of stub calls since the last ifx_run.
ifx_log_count() { wc -l < "$STUB_LOG" | tr -d ' '; }
