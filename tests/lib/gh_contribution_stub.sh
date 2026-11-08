#!/usr/bin/env bash
# gh_contribution_stub.sh - a deterministic `gh` function stub modelling how
# GitHub exposes contribution issues to aitask_contribution_check.sh (t2235).
#
# Usage:
#   . "$PROJECT_DIR/tests/lib/gh_contribution_stub.sh"
#   gh_contribution_stub_install "$scratch_dir"     # writes fixtures, defines gh()
#   ... exercise github_list_contribution_issues / main / cmd_list_issues ...
#   unset -f gh
#
# Modelled rules:
#   - `gh api <path>` returns page 1 only; with --paginate it prints page 1 and
#     then page 2 as consecutive JSON arrays (gh's real --paginate output).
#   - Labels from authors without push access were silently dropped, so the
#     external contributions #100/#101 are open but unlabeled.
#   - Page 1 is 100 NEWER ordinary issues (#200-#299) plus a pull request (#300)
#     whose body carries the metadata marker: a limit applied before filtering
#     loses every contribution, and a PR must never count as an issue.
#   - Page 2 holds the older issues: #15 labeled + metadata (control), #14 plain,
#     #12 labeled without metadata, #100 and #101 unlabeled + metadata touching
#     the same file (pairwise score 8 = high; each scores 5 = likely vs #15).
#
# Env knobs read at call time:
#   GH_STUB_API_FAIL=1          `gh api` exits 1 with no output.
#   GH_STUB_REPO_URL=<url>      what `gh repo view --json url` reports
#                               (default https://github.com/o/r).
#   GH_STUB_REPO_LABELS=<json>  `gh label list --json name` output (default []).
# Recorded argv: `gh api` -> api_calls, `gh repo view` -> repo_calls,
# `gh issue edit` -> edit_calls (all under "$GH_STUB_DIR").

_gh_stub_metadata() {
    # _gh_stub_metadata <file_path> -> an issue body with a v1 fingerprint
    printf '%s\n' "Contribution body." "" \
        "<!-- aitask-contribute-metadata" \
        "contributor: ext" \
        "contributor_email: ext@users.noreply.github.com" \
        "based_on_version: 0.32.0" \
        "fingerprint_version: 1" \
        "areas: scripts" \
        "file_paths: $1" \
        "file_dirs: .aitask-scripts" \
        "change_type: bug" \
        "auto_labels: area:scripts" \
        "-->"
}

# _gh_stub_log <file> <argv...> — space-joined argv, whatever the caller's IFS
# (main() sets IFS=',' around its label loop).
_gh_stub_log() {
    local file="$1" IFS=' '
    shift
    printf '%s\n' "$*" >> "$file"
}

gh_contribution_stub_install() {
    GH_STUB_DIR="$1"
    mkdir -p "$GH_STUB_DIR"
    : > "$GH_STUB_DIR/api_calls"
    : > "$GH_STUB_DIR/repo_calls"
    : > "$GH_STUB_DIR/edit_calls"

    local shared other
    shared=$(_gh_stub_metadata ".aitask-scripts/aitask_contribute.sh")
    other=$(_gh_stub_metadata ".aitask-scripts/aitask_other.sh")

    jq -n --arg meta "$shared" '
        [range(299; 199; -1) | {number: ., title: "Ordinary issue \(.)",
            body: "Nothing to see.", labels: [],
            html_url: "https://github.com/o/r/issues/\(.)"}]
        + [{number: 300, title: "A pull request", body: $meta, labels: [],
            pull_request: {url: "https://api.github.com/repos/o/r/pulls/300"},
            html_url: "https://github.com/o/r/pull/300"}]' \
        > "$GH_STUB_DIR/page1.json"

    jq -n --arg meta "$shared" --arg other "$other" '
        [ {number: 101, title: "[Contribution] external B", body: $meta, labels: [],
           html_url: "https://github.com/o/r/issues/101"},
          {number: 100, title: "[Contribution] external A", body: $meta, labels: [],
           html_url: "https://github.com/o/r/issues/100"},
          {number: 15, title: "[Contribution] labeled control", body: $other,
           labels: [{name: "contribution", color: "0e8a16"}],
           html_url: "https://github.com/o/r/issues/15"},
          {number: 14, title: "Plain docs issue", body: "No metadata here.",
           labels: [], html_url: "https://github.com/o/r/issues/14"},
          {number: 12, title: "Labeled without metadata", body: "Hand-written.",
           labels: [{name: "contribution"}],
           html_url: "https://github.com/o/r/issues/12"} ]' \
        > "$GH_STUB_DIR/page2.json"

    jq -n --arg meta "$shared" '
        {number: 100, title: "[Contribution] external A", body: $meta,
         labels: [], url: "https://github.com/o/r/issues/100"}' \
        > "$GH_STUB_DIR/issue100.json"

    gh() {
        case "${1:-}" in
            api)
                shift
                _gh_stub_log "$GH_STUB_DIR/api_calls" "$@"
                [[ "${GH_STUB_API_FAIL:-}" == 1 ]] && return 1
                local a paginate=0
                for a in "$@"; do [[ "$a" == "--paginate" ]] && paginate=1; done
                cat "$GH_STUB_DIR/page1.json"
                [[ "$paginate" == 1 ]] && cat "$GH_STUB_DIR/page2.json"
                return 0
                ;;
            repo)
                _gh_stub_log "$GH_STUB_DIR/repo_calls" "$@"
                echo "${GH_STUB_REPO_URL:-https://github.com/o/r}"
                ;;
            issue)
                case "${2:-}" in
                    view) cat "$GH_STUB_DIR/issue100.json" ;;
                    list) echo "[]" ;;   # label-filtered listing: nothing reaches it
                    edit) _gh_stub_log "$GH_STUB_DIR/edit_calls" "$@" ;;
                    *) return 0 ;;
                esac
                ;;
            label) echo "${GH_STUB_REPO_LABELS:-[]}" ;;
            auth) return 0 ;;
            *) return 0 ;;
        esac
    }
}
