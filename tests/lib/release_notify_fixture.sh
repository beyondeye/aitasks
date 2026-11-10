#!/usr/bin/env bash
# release_notify_fixture.sh - shared fixture for the release-notify tests
# (t2261_2): scenario-driven gh / glab stubs over a file-backed comment store,
# a hostname shim, and a legacy-mode repo with a bare origin and tags.
#
# Requires, from the sourcing test file:
#   PROJECT_DIR   repo root
#   TMP           a scratch directory the test owns and removes
#
# The stubs answer from files under $RNF_STATE, so a scenario is set up by
# writing files, and every call is logged (`printf '%q '` argv) to $STUB_LOG:
#
#   release/<tag>/<n>        gh release view: the n-th answer (JSON, or the
#                            word 404 / ERR); the last one repeats
#   runs/<tag>/<n>           gh run list: a JSON array of runs, stepped the same
#   assets/<tag>/<name>      gh/glab release download: the asset bytes
#   glab_release/<tag>/<n>   glab api projects/<p>/releases/<tag>: stepped
#   comments/<key>/<seq>     one comment body per file; <key> is
#                            <owner>_<repo>_<n> (GitHub) or <slug>_<iid>
#                            (GitLab, '/' -> '_')
#   fail_list                comment listing fails (unknown)
#   fail_post[_<n>]          posting fails (for every issue, or issue <n> only)
#
# JSON shapes follow real `gh` output (captured for t2261_2): `gh release view
# --json tagName,isDraft,assets` and `gh run list --json databaseId,headSha,
# headBranch,status,conclusion,createdAt` with headBranch = the tag. The stubs
# apply the caller's --jq expression with the real jq, so the code under test
# parses exactly what gh would hand it.

RNF_BIN="$TMP/bin"
RNF_STATE="$TMP/state"
STUB_LOG="$TMP/stub.log"
RNF_NOTIFY="$PROJECT_DIR/.aitask-scripts/aitask_release_notify.sh"
export STUB_LOG RNF_STATE

rnf_write_stubs() {
    mkdir -p "$RNF_BIN" "$RNF_STATE"
    cat > "$RNF_BIN/hostname" <<'EOF'
#!/usr/bin/env bash
echo "${TEST_HOSTNAME:-testhost}"
EOF
    cat > "$RNF_BIN/gh" <<'EOF'
#!/usr/bin/env bash
{ printf '%q ' gh "$@"; printf '\n'; } >> "${STUB_LOG:?}"
S="${RNF_STATE:?}"
# step <dir> — print the path of this call's answer file (the counter advances
# once per call; the last answer repeats).
step() {
    local d="$1" n=1 max
    [[ -d "$d" ]] || return 1
    [[ -f "$d/.count" ]] && n=$(( $(cat "$d/.count") + 1 ))
    echo "$n" > "$d/.count"
    max="$(ls "$d" | grep -E '^[0-9]+$' | sort -n | tail -1)"
    (( n > max )) && n="$max"
    printf '%s\n' "$d/$n"
}
jqexpr=""
args=("$@")
for (( i = 0; i < ${#args[@]}; i++ )); do
    [[ "${args[i]}" == --jq ]] && jqexpr="${args[i+1]}"
done
case "$1 ${2:-}" in
    "auth status") exit 0 ;;
    "release view")
        tag="$3"
        f="$(step "$S/release/$tag")" || { echo "release not found" >&2; exit 1; }
        case "$(cat "$f")" in
            404) echo "release not found" >&2; exit 1 ;;
            ERR) echo "HTTP 502: Bad Gateway" >&2; exit 1 ;;
        esac
        jq -r "$jqexpr" < "$f" ;;
    "run list")
        tag=""
        for (( i = 0; i < ${#args[@]}; i++ )); do
            [[ "${args[i]}" == --branch ]] && tag="${args[i+1]}"
        done
        f="$(step "$S/runs/$tag")" || { echo '[]' | jq -r "$jqexpr"; exit 0; }
        [[ "$(cat "$f")" == ERR ]] && { echo "HTTP 502" >&2; exit 1; }
        jq -r "$jqexpr" < "$f" ;;
    "release download")
        tag="$3" name="" outp=""
        for (( i = 0; i < ${#args[@]}; i++ )); do
            [[ "${args[i]}" == -p ]] && name="${args[i+1]}"
            [[ "${args[i]}" == -O ]] && outp="${args[i+1]}"
        done
        [[ -f "$S/assets/$tag/$name" ]] || { echo "no assets match" >&2; exit 1; }
        cp "$S/assets/$tag/$name" "$outp" ;;
    "api --paginate"|"api --hostname")
        [[ -f "$S/fail_list" ]] && { echo "HTTP 502" >&2; exit 1; }
        path="${args[${#args[@]}-3]}"
        [[ "$path" =~ ^repos/([^/]+)/([^/]+)/issues/([0-9]+)/comments$ ]] || exit 1
        d="$S/comments/${BASH_REMATCH[1]}_${BASH_REMATCH[2]}_${BASH_REMATCH[3]}"
        for c in $(ls "$d" 2>/dev/null | sort -n); do cat "$d/$c"; printf '\n'; done ;;
    "issue comment")
        url="$3" body=""
        for (( i = 0; i < ${#args[@]}; i++ )); do
            [[ "${args[i]}" == --body ]] && body="${args[i+1]}"
        done
        [[ "$url" =~ ^https?://[^/]+/([^/]+)/([^/]+)/issues/([0-9]+)$ ]] || exit 1
        n="${BASH_REMATCH[3]}"
        [[ -f "$S/fail_post" || -f "$S/fail_post_$n" ]] && { echo "HTTP 502" >&2; exit 1; }
        d="$S/comments/${BASH_REMATCH[1]}_${BASH_REMATCH[2]}_$n"
        mkdir -p "$d"
        seq=$(( $(ls "$d" | wc -l) + 1 ))
        printf '%s' "$body" > "$d/$seq" ;;
    *) exit 0 ;;
esac
EOF
    cat > "$RNF_BIN/glab" <<'EOF'
#!/usr/bin/env bash
{ printf '%q ' glab "$@"; printf '\n'; } >> "${STUB_LOG:?}"
S="${RNF_STATE:?}"
step() {
    local d="$1" n=1 max
    [[ -d "$d" ]] || return 1
    [[ -f "$d/.count" ]] && n=$(( $(cat "$d/.count") + 1 ))
    echo "$n" > "$d/.count"
    max="$(ls "$d" | grep -E '^[0-9]+$' | sort -n | tail -1)"
    (( n > max )) && n="$max"
    printf '%s\n' "$d/$n"
}
args=("$@")
case "$1 ${2:-}" in
    "auth status") exit 0 ;;
    api\ *)
        path="${args[${#args[@]}-1]}"
        if [[ "$path" =~ ^projects/([^/]+)/releases/(.+)$ ]]; then
            tag="$(printf '%b' "${BASH_REMATCH[2]//%/\\x}")"
            f="$(step "$S/glab_release/$tag")" || { echo "404 Not Found" >&2; exit 1; }
            case "$(cat "$f")" in
                404) echo "404 Not Found" >&2; exit 1 ;;
                ERR) echo "502 Bad Gateway" >&2; exit 1 ;;
            esac
            cat "$f"
        elif [[ "$path" =~ ^projects/([^/]+)/issues/([0-9]+)/notes ]]; then
            [[ -f "$S/fail_list" ]] && { echo "502" >&2; exit 1; }
            slug="$(printf '%b' "${BASH_REMATCH[1]//%/\\x}")"
            d="$S/comments/${slug//\//_}_${BASH_REMATCH[2]}"
            python3 -c 'import json,os,sys
d=sys.argv[1]
fs=sorted(os.listdir(d),key=int) if os.path.isdir(d) else []
print(json.dumps([{"body":open(os.path.join(d,f)).read()} for f in fs]))' "$d"
        else
            exit 1
        fi ;;
    "issue note")
        iid="$3" body="" slug=""
        for (( i = 0; i < ${#args[@]}; i++ )); do
            [[ "${args[i]}" == -m ]] && body="${args[i+1]}"
            [[ "${args[i]}" == -R ]] && slug="${args[i+1]}"
        done
        [[ -f "$S/fail_post" || -f "$S/fail_post_$iid" ]] && { echo "502" >&2; exit 1; }
        d="$S/comments/${slug//\//_}_$iid"
        mkdir -p "$d"
        seq=$(( $(ls "$d" | wc -l) + 1 ))
        printf '%s' "$body" > "$d/$seq" ;;
    "release download")
        tag="$3" name="" dir=""
        for (( i = 0; i < ${#args[@]}; i++ )); do
            [[ "${args[i]}" == -n ]] && name="${args[i+1]}"
            [[ "${args[i]}" == -D ]] && dir="${args[i+1]}"
        done
        [[ -f "$S/fail_glab_download" ]] && { echo "502" >&2; exit 1; }
        [[ -f "$S/assets/$tag/$name" ]] || { echo "not found" >&2; exit 1; }
        cp "$S/assets/$tag/$name" "$dir/$name" ;;
    *) exit 0 ;;
esac
EOF
    chmod +x "$RNF_BIN/hostname" "$RNF_BIN/gh" "$RNF_BIN/glab"
    : > "$STUB_LOG"
}

# rnf_commit <repo> <subject> — one code commit.
rnf_commit() {
    local f
    f="$1/code_$(git -C "$1" rev-list --count HEAD 2>/dev/null || echo 0)_$RANDOM.txt"
    echo "$2" > "$f"
    git -C "$1" add -- "$f"
    git -C "$1" commit -qm "$2"
}

# rnf_make_repo <dir> [origin-url] — a legacy-mode repo at <dir>/repo whose
# origin is <origin-url> (default https://github.com/o/r.git) rewritten through
# url.<path>.insteadOf to a local bare repo, so the configured URL names the
# platform while fetch / ls-remote / push stay local. History:
#   v1.0.0: (t10)                 v1.1.0: (t20) (t30_1) (t40)
#   v1.2.0: (t50) (t60)           after v1.2.0: (t70)
rnf_make_repo() {
    local d="$1" url="${2:-https://github.com/o/r.git}" repo
    repo="$d/repo"
    git init -q --bare "$d/origin.git"
    git init -q -b main "$repo"
    git -C "$repo" config user.email t@example.com
    git -C "$repo" config user.name Test
    git -C "$repo" config commit.gpgsign false
    git -C "$repo" config tag.gpgsign false
    git -C "$repo" remote add origin "$url"
    git -C "$repo" config "url.$d/origin.git.insteadOf" "$url"
    mkdir -p "$repo/aitasks/metadata"
    printf 'release_notify_host: testhost\n' > "$repo/aitasks/metadata/project_config.yaml"
    git -C "$repo" add -A
    git -C "$repo" commit -qm "ait: init"
    rnf_commit "$repo" "feature: a (t10)"
    git -C "$repo" tag v1.0.0
    rnf_commit "$repo" "feature: b (t20)"
    rnf_commit "$repo" "feature: c (t30_1)"
    rnf_commit "$repo" "bug: d (t40)"
    git -C "$repo" tag v1.1.0
    rnf_commit "$repo" "feature: e (t50)"
    rnf_commit "$repo" "feature: f (t60)"
    git -C "$repo" tag v1.2.0
    rnf_commit "$repo" "feature: g (t70)"
    git -C "$repo" push -q origin main --tags 2>/dev/null
    printf '%s\n' "$repo"
}

# rnf_config <repo> <yaml text> — replace project_config.yaml and commit it.
rnf_config() {
    printf '%s' "$2" > "$1/aitasks/metadata/project_config.yaml"
    git -C "$1" add -- aitasks/metadata/project_config.yaml
    git -C "$1" commit -qm "ait: config" -- aitasks/metadata/project_config.yaml >/dev/null 2>&1 || true
}

# rnf_record <repo> <task_id> <issue_url> [platform] — write AND commit one
# pending record through the real writer (ril_record).
rnf_record() {
    local platform="${4:-github}"
    ( cd "$1" && SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts" \
        && . "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" \
        && . "$PROJECT_DIR/.aitask-scripts/lib/release_issue_ledger.sh" \
        && ril_record "$2" "$3" "$platform" closed ) > "$TMP/rec.out" 2>&1
    grep -q '^RELEASE_LEDGER:recorded:' "$TMP/rec.out" || { cat "$TMP/rec.out" >&2; return 1; }
    sed -n 's/^RELEASE_LEDGER:recorded://p' "$TMP/rec.out"
}

# rnf_release <tag> <step> <draft:true|false> [name:state:size ...] — a gh
# release view answer.
rnf_release() {
    local tag="$1" n="$2" draft="$3" a first=1
    shift 3
    mkdir -p "$RNF_STATE/release/$tag"
    {
        printf '{"tagName":"%s","isDraft":%s,"assets":[' "$tag" "$draft"
        for a in "$@"; do
            [[ "$first" == 1 ]] || printf ','
            first=0
            IFS=: read -r an as az <<< "$a"
            printf '{"name":"%s","state":"%s","size":%s,"contentType":"application/octet-stream"}' "$an" "$as" "$az"
        done
        printf ']}\n'
    } > "$RNF_STATE/release/$tag/$n"
}

rnf_release_raw() { mkdir -p "$RNF_STATE/release/$1"; printf '%s\n' "$3" > "$RNF_STATE/release/$1/$2"; }

# rnf_runs <tag> <step> ["<id> <sha> <branch> <status> <conclusion>" ...]
rnf_runs() {
    local tag="$1" n="$2" r first=1 id sha br st co
    shift 2
    mkdir -p "$RNF_STATE/runs/$tag"
    {
        printf '['
        for r in "$@"; do
            [[ "$first" == 1 ]] || printf ','
            first=0
            read -r id sha br st co <<< "$r"
            printf '{"databaseId":%s,"headSha":"%s","headBranch":"%s","event":"push","status":"%s","conclusion":"%s","createdAt":"2026-11-10T10:00:00Z"}' \
                "$id" "$sha" "$br" "$st" "$co"
        done
        printf ']\n'
    } > "$RNF_STATE/runs/$tag/$n"
}

rnf_asset() { mkdir -p "$RNF_STATE/assets/$1"; printf '%s' "$3" > "$RNF_STATE/assets/$1/$2"; }

# rnf_reset_state — forget every scenario answer and every comment.
rnf_reset_state() { rm -rf "$RNF_STATE"; mkdir -p "$RNF_STATE"; : > "$STUB_LOG"; }
rnf_reset_steps() { find "$RNF_STATE" -name .count -delete 2>/dev/null || true; }

# rnf_comment_count <key> — comments stored for one issue.
rnf_comment_count() { ls "$RNF_STATE/comments/$1" 2>/dev/null | wc -l | tr -d ' '; }

# rnf_run <repo> <args…> — run the REAL consumer with cwd = <repo> and the
# stubs first on PATH. Sets RNF_RC, RNF_OUT, RNF_ERR.
rnf_run() {
    local repo="$1"; shift
    RNF_RC=0
    ( cd "$repo" && PATH="$RNF_BIN:$PATH" "$RNF_NOTIFY" "$@" ) \
        > "$TMP/rnf.out" 2> "$TMP/rnf.err" || RNF_RC=$?
    RNF_OUT="$(cat "$TMP/rnf.out")"
    RNF_ERR="$(cat "$TMP/rnf.err")"
}

rnf_log_count() { grep -c -- "$1" "$STUB_LOG" 2>/dev/null || true; }

# rnf_lib <repo> <command…> — run a ledger-lib function with cwd = <repo>.
rnf_lib() {
    local repo="$1"; shift
    ( cd "$repo" && SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts" \
        && . "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" \
        && . "$PROJECT_DIR/.aitask-scripts/lib/release_issue_ledger.sh" \
        && "$@" )
}
