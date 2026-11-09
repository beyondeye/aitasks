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
#   - Issue comments (t2252): `gh issue view <n> --json comments` serves
#     comments_<n>.json, else {"comments":[]}. #100 already carries an overlap
#     analysis: a real `gh issue view --json comments` capture (gh 2.102.1, an
#     issue with an analysis and an owner reply), anonymised and re-pointed at
#     o/r #100. `--jq` is applied with jq -r, as gh prints raw strings. gh pages
#     through every comment itself, so the stub serves them all at once.
#     Variants derived from the capture by jq, oldest first as gh orders them:
#       large  the analysis first, then 40 owner comments of ~20 KB (SIGPIPE)
#       many   150 comments, the analysis at index 110 (past gh's first 100)
#   - `gh issue view <n>` otherwise serves issue<n>.json, else issue100.json;
#     issue14.json is the plain issue without metadata.
#
# Env knobs read at call time:
#   GH_STUB_API_FAIL=1          `gh api` exits 1 with no output.
#   GH_STUB_REPO_URL=<url>      what `gh repo view --json url` reports
#                               (default https://github.com/o/r).
#   GH_STUB_REPO_LABELS=<json>  `gh label list --json name` output (default []).
#   GH_STUB_COMMENTS=<variant>  serve comments_<n>.<variant>.json.
#   GH_STUB_VIEW_FAIL=1         `gh issue view --json comments` exits 1, no output.
#   GH_STUB_COMMENT_FAIL=1      `gh issue comment` exits 1 (after logging it).
# Recorded argv: `gh api` -> api_calls, `gh repo view` -> repo_calls,
# `gh issue edit` -> edit_calls, `gh issue comment` -> comment_calls (all
# under "$GH_STUB_DIR").
#
# A separate `bash <script>` process sees the stub after
# `export -f gh _gh_stub_log` (GH_STUB_DIR is exported by the install).

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

_gh_stub_comments() {
    # _gh_stub_comments -> #100's comments: a real `gh issue view --json
    # comments` response (gh 2.102.1, t2252) — an overlap analysis posted by
    # the workflow and an owner reply — with ids, urls, logins, dates and the
    # table row anonymised. Key set and value types are the capture's. Do not
    # hand-edit its shape.
    cat <<'COMMENTS'
{"comments":[{"id":"IC_stub1","author":{"login":"github-actions"},"authorAssociation":"NONE","body":"## Contribution Overlap Analysis\n\n| Issue | Score | Overlap | Detail |\n|-------|-------|---------|--------|\n| [#101](https://github.com/o/r/issues/101) | 8 (high) | [Contribution] external B | files- .aitask-scripts/aitask_contribute.sh (+3); dirs- .aitask-scripts (+2); areas- scripts (+2); change_type- bug (+1) |\n\n<!-- overlap-results top_overlaps: 101:8 overlap_check_version: 1 -->","createdAt":"2099-01-01T00:00:00Z","includesCreatedEdit":false,"isMinimized":false,"minimizedReason":"","reactionGroups":[],"url":"https://github.com/o/r/issues/100#issuecomment-1","viewerDidAuthor":false},{"id":"IC_stub2","author":{"login":"maint"},"authorAssociation":"OWNER","body":"Thanks!","createdAt":"2099-01-01T00:00:00Z","includesCreatedEdit":false,"isMinimized":false,"minimizedReason":"","reactionGroups":[],"url":"https://github.com/o/r/issues/100#issuecomment-2","viewerDidAuthor":true}]}
COMMENTS
}

# _gh_stub_log <file> <argv...> — space-joined argv, whatever the caller's IFS
# (main() sets IFS=',' around its label loop).
_gh_stub_log() {
    local file="$1" IFS=' '
    shift
    printf '%s\n' "$*" >> "$file"
}

gh_contribution_stub_install() {
    export GH_STUB_DIR="$1"
    mkdir -p "$GH_STUB_DIR"
    : > "$GH_STUB_DIR/api_calls"
    : > "$GH_STUB_DIR/repo_calls"
    : > "$GH_STUB_DIR/edit_calls"
    : > "$GH_STUB_DIR/comment_calls"

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
    jq -n '{number: 14, title: "Plain docs issue", body: "No metadata here.",
            labels: [], url: "https://github.com/o/r/issues/14"}' \
        > "$GH_STUB_DIR/issue14.json"

    # Comments: the capture and its variants. .comments[0] is the analysis,
    # .comments[1] the owner reply; ids and urls are renumbered in order.
    echo '{"comments":[]}' > "$GH_STUB_DIR/no_comments.json"
    _gh_stub_comments > "$GH_STUB_DIR/comments_100.json"
    local pad
    pad=$(printf '%*s' 20000 '' | tr ' ' 'x')
    # shellcheck disable=SC2016  # $v, $pad, $overlap, $reply are jq variables
    local variants='
        def renumber: to_entries | map(.value + {id: "IC_stub\(.key + 1)",
            url: "https://github.com/o/r/issues/100#issuecomment-\(.key + 1)"});
        .comments[0] as $overlap | .comments[1] as $reply
        | {comments: (
            if $v == "large" then [$overlap] + [range(40) | $reply | .body += "\n" + $pad]
            else [range(110) | $reply] + [$overlap] + [range(39) | $reply] end
            | renumber)}'
    local v
    for v in large many; do
        jq -c --arg v "$v" --arg pad "$pad" "$variants" "$GH_STUB_DIR/comments_100.json" \
            > "$GH_STUB_DIR/comments_100.$v.json"
    done

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
                    view)
                        local json="" jqexpr="" prev="" a f
                        for a in "$@"; do
                            [[ "$prev" == "--json" ]] && json="$a"
                            [[ "$prev" == "--jq" ]] && jqexpr="$a"
                            prev="$a"
                        done
                        if [[ ",$json," == *,comments,* ]]; then
                            [[ "${GH_STUB_VIEW_FAIL:-}" == 1 ]] && return 1
                            f="$GH_STUB_DIR/comments_${3:-}${GH_STUB_COMMENTS:+.$GH_STUB_COMMENTS}.json"
                            [[ -f "$f" ]] || f="$GH_STUB_DIR/no_comments.json"
                            if [[ -n "$jqexpr" ]]; then jq -r "$jqexpr" "$f"; else cat "$f"; fi
                        else
                            f="$GH_STUB_DIR/issue${3:-}.json"
                            [[ -f "$f" ]] || f="$GH_STUB_DIR/issue100.json"
                            cat "$f"
                        fi
                        ;;
                    list) echo "[]" ;;   # label-filtered listing: nothing reaches it
                    edit) _gh_stub_log "$GH_STUB_DIR/edit_calls" "$@" ;;
                    comment)
                        _gh_stub_log "$GH_STUB_DIR/comment_calls" "$@"
                        [[ "${GH_STUB_COMMENT_FAIL:-}" == 1 ]] && return 1
                        return 0
                        ;;
                    *) return 0 ;;
                esac
                ;;
            label) echo "${GH_STUB_REPO_LABELS:-[]}" ;;
            auth) return 0 ;;
            *) return 0 ;;
        esac
    }
}
