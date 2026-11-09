#!/usr/bin/env bash
# glab_contribution_stub.sh - deterministic `glab` and `curl` executables
# modelling how GitLab exposes contribution issues to aitask_contribution_check.sh
# and to the contribution-check CI job (t2241).
#
# Usage:
#   . "$PROJECT_DIR/tests/lib/glab_contribution_stub.sh"
#   glab_contribution_stub_install "$scratch_dir"   # writes fixtures + <dir>/bin/{glab,curl}
#   PATH="$scratch_dir/bin:$PATH"                   # caller prepends (and restores) PATH
#
# They are executables, not shell functions, so a separate shell (the CI job
# script) sees them too. Fixtures and call logs live in the install directory,
# whose path is baked into both executables.
#
# Modelled rules:
#   - GitLab silently drops labels supplied by authors who are not project
#     members, so the external contributions #100/#101 are open but unlabeled.
#   - `labels=contribution` (REST) and `glab issue list --label contribution`
#     are applied server-side: they return only labeled issues, which is what
#     the pre-t2241 code saw.
#   - Issues are served newest first: 100 NEWER ordinary issues (#200-#299)
#     fill page 1 (per_page=100), so a limit applied before filtering loses
#     every contribution.
#   - Page 2 holds the older issues: #101 and #100 unlabeled + metadata
#     touching the same file (pairwise score 8 = high), #15 labeled + metadata
#     on another file (score 5 = likely vs #100), #14 plain, #12 labeled
#     without metadata.
#   - `glab api --paginate` prints all pages as ONE merged JSON array (glab
#     1.126's documented json output); GLAB_STUB_PAGINATE_FORMAT=concat prints
#     one array per page instead (older glab).
#
# Env knobs read at call time:
#   GLAB_STUB_CURL_FAIL_PAGE=<n>   curl exits 22 (HTTP error under -f) on page n.
#   GLAB_STUB_CURL_REPEAT_PAGE=1   curl ignores page= and always serves page 1
#                                  (a server/proxy that drops the parameter).
#   GLAB_STUB_API_FAIL=1           `glab api` exits 1 with no output.
#   GLAB_STUB_CURL_REQUIRE_TOKEN=1 curl exits 22 unless a non-empty
#                                  PRIVATE-TOKEN header is sent (a private
#                                  project: no anonymous REST access).
#   GLAB_STUB_PAGINATE_FORMAT=concat
#   - Issue notes (t2247): #100 already carries an `<!-- overlap-results`
#     note, every other issue has none. Served by curl and by `glab api` at
#     .../issues/<iid>/notes, in the REST notes shape captured from GitLab CE
#     19.4.5 (notes_100.json).
# Recorded argv: curl URLs -> curl_calls, the --header values of each curl
# call (joined with " | ", "<none>" when absent) -> curl_auth, glab argv ->
# glab_calls.

_glab_stub_metadata() {
    # _glab_stub_metadata <file_path> -> an issue description with a v1 fingerprint
    printf '%s\n' "Contribution body." "" \
        "<!-- aitask-contribute-metadata" \
        "contributor: ext" \
        "contributor_email: ext@users.noreply.gitlab.com" \
        "based_on_version: 0.32.0" \
        "fingerprint_version: 1" \
        "areas: scripts" \
        "file_paths: $1" \
        "file_dirs: .aitask-scripts" \
        "change_type: bug" \
        "auto_labels: area:scripts" \
        "-->"
}

_glab_stub_notes() {
    # _glab_stub_notes -> the REST notes array of an issue that already has an
    # overlap-analysis comment: a real GET .../issues/:iid/notes response from
    # GitLab CE 19.4.5 (t2247 live check), newest first, re-pointed at #100
    # with dates, ids and URLs anonymised. Do not hand-edit its shape.
    cat <<'NOTES'
[{"id":2,"type":null,"body":"Thanks!","author":{"id":2,"username":"maint","public_email":null,"name":"maint","state":"active","locked":false,"avatar_url":null,"web_url":"https://gitlab.example/maint"},"created_at":"2099-01-01T00:00:00.000Z","updated_at":"2099-01-01T00:00:00.000Z","system":false,"noteable_id":100,"noteable_type":"Issue","project_id":7,"resolvable":false,"confidential":false,"internal":false,"imported":false,"imported_from":"none","noteable_iid":100,"commands_changes":{}},{"id":1,"type":null,"body":"<!-- overlap-results\noverlap_check_version: 1\n-->\n## Contribution Overlap Analysis","author":{"id":2,"username":"maint","public_email":null,"name":"maint","state":"active","locked":false,"avatar_url":null,"web_url":"https://gitlab.example/maint"},"created_at":"2099-01-01T00:00:00.000Z","updated_at":"2099-01-01T00:00:00.000Z","system":false,"noteable_id":100,"noteable_type":"Issue","project_id":7,"resolvable":false,"confidential":false,"internal":false,"imported":false,"imported_from":"none","noteable_iid":100,"commands_changes":{}}]
NOTES
}

glab_contribution_stub_install() {
    local dir="$1"
    mkdir -p "$dir/bin"
    : > "$dir/curl_calls"
    : > "$dir/curl_auth"
    : > "$dir/glab_calls"

    local shared other
    shared=$(_glab_stub_metadata ".aitask-scripts/aitask_contribute.sh")
    other=$(_glab_stub_metadata ".aitask-scripts/aitask_other.sh")

    jq -n --arg meta "$shared" --arg other "$other" '
        def issue($iid; $title; $desc; $labels):
            {iid: $iid, title: $title, description: $desc, labels: $labels,
             state: "opened", updated_at: "2099-01-01T00:00:00Z",
             web_url: "https://gitlab.example/o/r/-/issues/\($iid)"};
        [range(299; 199; -1) | issue(.; "Ordinary issue \(.)"; "Nothing to see."; [])]
        + [ issue(101; "[Contribution] external B"; $meta; []),
            issue(100; "[Contribution] external A"; $meta; []),
            issue(15; "[Contribution] labeled control"; $other; ["contribution"]),
            issue(14; "Plain docs issue"; "No metadata here."; []),
            issue(12; "Labeled without metadata"; "Hand-written."; ["contribution"]) ]' \
        > "$dir/all.json"
    _glab_stub_notes > "$dir/notes_100.json"

    # --- curl: the GitLab REST server ---
    cat > "$dir/bin/curl" <<EOF
#!/usr/bin/env bash
D='$dir'
EOF
    cat >> "$dir/bin/curl" <<'EOF'
url="" hdrs=() prev=""
for a in "$@"; do
    case "$a" in http://*|https://*) url="$a" ;; esac
    [[ "$prev" == "--header" || "$prev" == "-H" ]] && hdrs+=("$a")
    prev="$a"
done
printf '%s\n' "$url" >> "$D/curl_calls"
if [[ ${#hdrs[@]} -eq 0 ]]; then
    echo "<none>" >> "$D/curl_auth"
else
    (IFS='|'; printf '%s\n' "${hdrs[*]}" | sed 's/|/ | /g') >> "$D/curl_auth"
fi
path="${url%%\?*}"
query=""
[[ "$url" == *\?* ]] && query="${url#*\?}"
labels="" page=1 per_page=20 since=""
IFS='&' read -r -a kv <<< "$query"
for p in "${kv[@]}"; do
    case "$p" in
        labels=*) labels="${p#labels=}" ;;
        page=*) page="${p#page=}" ;;
        per_page=*) per_page="${p#per_page=}" ;;
        updated_after=*) since="${p#updated_after=}" ;;
    esac
done
if [[ "${GLAB_STUB_CURL_REQUIRE_TOKEN:-}" == 1 ]]; then
    tok_ok=0
    for h in "${hdrs[@]}"; do [[ "$h" == "PRIVATE-TOKEN: "?* ]] && tok_ok=1; done
    [[ "$tok_ok" == 1 ]] || exit 22
fi
if [[ -n "${GLAB_STUB_CURL_FAIL_PAGE:-}" && "$page" == "$GLAB_STUB_CURL_FAIL_PAGE" ]]; then
    exit 22
fi
[[ "${GLAB_STUB_CURL_REPEAT_PAGE:-}" == 1 ]] && page=1
case "$path" in
    */issues/*/notes)
        iid="${path%/notes}"; iid="${iid##*/}"
        if [[ -f "$D/notes_$iid.json" ]]; then cat "$D/notes_$iid.json"; else echo '[]'; fi
        ;;
    */labels)
        echo '[{"name":"contribution"},{"name":"area:scripts"}]'
        ;;
    */issues)
        jq -c --arg l "$labels" --arg s "$since" --argjson p "$page" --argjson n "$per_page" '
            [ .[] | select($l == "" or any(.labels[]; . == $l))
                  | select($s == "" or .updated_at > $s) ]
            | .[(($p - 1) * $n):($p * $n)]' "$D/all.json"
        ;;
    */issues/*)
        jq -ce --argjson i "${path##*/}" '.[] | select(.iid == $i)' "$D/all.json" || exit 22
        ;;
    *) exit 22 ;;
esac
EOF

    # --- glab ---
    cat > "$dir/bin/glab" <<EOF
#!/usr/bin/env bash
D='$dir'
EOF
    cat >> "$dir/bin/glab" <<'EOF'
printf '%s\n' "$*" >> "$D/glab_calls"
case "${1:-} ${2:-}" in
    "auth status") exit 0 ;;
    "issue list")
        # Only the label-filtered listing exists here: nothing unlabeled reaches it.
        jq -c '[.[] | select(any(.labels[]; . == "contribution"))]' "$D/all.json"
        ;;
    "issue view")
        jq -ce --argjson i "$3" '.[] | select(.iid == $i)' "$D/all.json" || exit 1
        ;;
    api*)
        [[ "${GLAB_STUB_API_FAIL:-}" == 1 ]] && exit 1
        if [[ "${2:-}" == */issues/*/notes* ]]; then
            p="${2%%\?*}"; iid="${p%/notes}"; iid="${iid##*/}"
            if [[ -f "$D/notes_$iid.json" ]]; then cat "$D/notes_$iid.json"; else echo '[]'; fi
            exit 0
        fi
        paginate=0
        for a in "$@"; do [[ "$a" == "--paginate" ]] && paginate=1; done
        if [[ "$paginate" == 0 ]]; then
            jq -c '.[0:100]' "$D/all.json"
        elif [[ "${GLAB_STUB_PAGINATE_FORMAT:-}" == concat ]]; then
            jq -c '.[0:100]' "$D/all.json"
            jq -c '.[100:200]' "$D/all.json"
        else
            jq '.' "$D/all.json"
        fi
        ;;
    *) exit 0 ;;
esac
EOF
    chmod +x "$dir/bin/curl" "$dir/bin/glab"
}
