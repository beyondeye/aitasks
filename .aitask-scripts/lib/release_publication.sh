#!/usr/bin/env bash
# release_publication.sh - Is release <tag> verifiably published? (t2261_2)
#
# One shared check used by every entry point that posts release notices:
# `ait release-notify` (direct and recovery runs) and the framework's
# wait_release_and_notify.sh. It reads the project's publication POLICY from
# aitasks/metadata/project_config.yaml on every call, so no caller can pass a
# weaker policy than the project configured.
#
# Policy keys (all optional, top-level):
#   release_publication_workflow            GitHub workflow file whose run for
#                                           the tag + tagged commit must have
#                                           concluded `success`
#   release_publication_assets              asset-name templates; {tag} and
#                                           {version} (= tag minus a leading v)
#   release_publication_checksum_manifests  globs of sha256sum manifests; every
#                                           file a matching manifest lists must
#                                           itself be a published asset
#   release_notify_host                     the one machine that posts (read by
#                                           release_notify_designation)
# With none set, only the generic checks run: the remote tag matches, and the
# release exists, is not a draft, and is not upcoming.
#
# The policy is parsed with a real YAML parser (release_publication_policy.py)
# whenever the config file exists. Anything short of a successful parse is
# `unknown:policy_unreadable:<reason>` and never degrades to the generic policy.
#
# Requires lib/task_utils.sh (detect_platform_from_url); sources
# lib/python_resolve.sh itself.

[[ -n "${_AIT_RELEASE_PUBLICATION_LOADED:-}" ]] && return 0
_AIT_RELEASE_PUBLICATION_LOADED=1

_RP_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if ! declare -F resolve_python >/dev/null; then
    # shellcheck source=python_resolve.sh
    source "$_RP_LIB_DIR/python_resolve.sh"
fi

# Charsets, as tr(1) sets used under LC_ALL=C (byte ranges in every locale).
RP_NAME_CHARSET="A-Za-z0-9._+-"
RP_HOST_CHARSET="A-Za-z0-9._-"
RP_GLOB_CHARSET="A-Za-z0-9._+*?-"
RP_SLUG_CHARSET="A-Za-z0-9._/-"

# rp_charset_only <value> <tr-set> — non-empty and made only of those bytes.
# The `x` sentinel: $( ) strips trailing newlines, so a value whose only stray
# byte is a newline would otherwise pass.
rp_charset_only() {
    local v="${1-}" rest
    [[ -n "$v" ]] || return 1
    rest="$(printf '%s' "$v" | LC_ALL=C tr -d "$2"; printf x)"
    [[ "$rest" == "x" ]]
}

# rp_valid_tag <tag> — the release-tag rule shared with the ledger: it becomes
# a directory name, a marker and a URL path segment.
rp_valid_tag() {
    local v="${1-}"
    rp_charset_only "$v" "$RP_NAME_CHARSET" || return 1
    [[ "$v" != -* && "$v" != "." && "$v" != ".." ]]
}

rp_config_path() { printf '%s\n' "${TASK_DIR:-aitasks}/metadata/project_config.yaml"; }

# --- Policy ----------------------------------------------------------------
#
# release_publication_policy_load [config] — fill the RP_* policy globals.
#   rc 0  loaded (keys may all be absent: the generic policy)
#   rc 1  unreadable; RP_POLICY_ERR names the reason or the key
RP_POLICY_ERR=""
RP_WORKFLOW=""
RP_HOST=""
RP_ASSETS=()
RP_MANIFESTS=()

release_publication_policy_load() {
    local config="${1:-$(rp_config_path)}" py out rc=0 line key val ok=0 t
    RP_POLICY_ERR=""
    RP_WORKFLOW=""
    RP_HOST=""
    RP_ASSETS=()
    RP_MANIFESTS=()

    # Proven absence: no file at all. Anything that exists is parsed.
    if [[ ! -e "$config" && ! -L "$config" ]]; then
        return 0
    fi
    if [[ ! -f "$config" || ! -r "$config" ]]; then
        RP_POLICY_ERR="read_error"
        return 1
    fi
    py="$(resolve_python 2>/dev/null || true)"
    if [[ -z "$py" ]]; then
        RP_POLICY_ERR="python_unavailable"
        return 1
    fi
    out="$("$py" -I "$_RP_LIB_DIR/release_publication_policy.py" "$config" 2>/dev/null)" || rc=$?
    while IFS= read -r line; do
        if [[ "$ok" == 1 ]]; then
            # Anything after OK means the protocol was not followed.
            RP_POLICY_ERR="reader_protocol"
            return 1
        fi
        case "$line" in
            OK) ok=1 ;;
            ERR$'\t'*)
                RP_POLICY_ERR="${line#ERR$'\t'}"
                return 1 ;;
            VAL$'\t'*$'\t'*)
                line="${line#VAL$'\t'}"
                key="${line%%$'\t'*}"
                val="${line#*$'\t'}"
                case "$key" in
                    release_publication_workflow) RP_WORKFLOW="$val" ;;
                    release_notify_host)          RP_HOST="$val" ;;
                    release_publication_assets)   RP_ASSETS+=("$val") ;;
                    release_publication_checksum_manifests) RP_MANIFESTS+=("$val") ;;
                    *) RP_POLICY_ERR="reader_protocol"; return 1 ;;
                esac ;;
            *)
                RP_POLICY_ERR="reader_protocol"
                return 1 ;;
        esac
    done <<< "$out"
    if [[ "$rc" != 0 || "$ok" != 1 ]]; then
        RP_POLICY_ERR="reader_failed"
        return 1
    fi

    # Value validation, after the parse.
    if [[ -n "$RP_WORKFLOW" ]] && ! rp_charset_only "$RP_WORKFLOW" "$RP_HOST_CHARSET"; then
        RP_POLICY_ERR="release_publication_workflow"
        return 1
    fi
    if [[ -n "$RP_HOST" ]] && ! rp_charset_only "$RP_HOST" "$RP_HOST_CHARSET"; then
        RP_POLICY_ERR="release_notify_host"
        return 1
    fi
    for t in "${RP_ASSETS[@]}"; do
        # Only {tag} and {version}; any other brace is an unknown placeholder.
        val="${t//\{tag\}/}"
        val="${val//\{version\}/}"
        # A template that is only placeholders ("{tag}") leaves nothing to
        # check here; its instantiation is checked by the expander.
        if ! rp_charset_only "${val:-x}" "$RP_NAME_CHARSET"; then
            RP_POLICY_ERR="release_publication_assets"
            return 1
        fi
    done
    for t in "${RP_MANIFESTS[@]}"; do
        if ! rp_charset_only "$t" "$RP_GLOB_CHARSET"; then
            RP_POLICY_ERR="release_publication_checksum_manifests"
            return 1
        fi
    done
    return 0
}

# release_publication_expand_assets <tag> — the required asset names, one per
# line, from the LOADED policy. The one template function: the contract test
# instantiates the framework policy through it. rc 1 on an invalid result.
release_publication_expand_assets() {
    local tag="$1" version t name
    version="${tag#v}"
    for t in "${RP_ASSETS[@]}"; do
        name="${t//\{tag\}/$tag}"
        name="${name//\{version\}/$version}"
        rp_charset_only "$name" "$RP_NAME_CHARSET" || return 1
        printf '%s\n' "$name"
    done
}

# --- Origin ----------------------------------------------------------------
#
# release_publication_origin — fill RP_PLATFORM, RP_ORIGIN_HOST, RP_SLUG from
# the origin remote (ssh scp-form, ssh://, and http(s):// URLs). rc 1 when the
# remote is missing, unparseable, or not GitHub / GitLab.
#
# Reads the CONFIGURED url (remote.origin.url), not `git remote get-url`, which
# applies url.<base>.insteadOf rewrites: a rewrite points git at a mirror or an
# auth proxy, while the release page lives at the configured address.
RP_PLATFORM=""
RP_ORIGIN_HOST=""
RP_SLUG=""

release_publication_origin() {
    local url rest host slug
    RP_PLATFORM=""
    RP_ORIGIN_HOST=""
    RP_SLUG=""
    url="$(git config --get remote.origin.url 2>/dev/null)" || return 1
    case "$url" in
        http://*|https://*|ssh://*)
            rest="${url#*://}"
            rest="${rest#*@}"          # user[:token]@
            host="${rest%%/*}"
            host="${host%%:*}"         # :port
            slug="${rest#*/}" ;;
        *@*:*)
            rest="${url#*@}"
            host="${rest%%:*}"
            slug="${rest#*:}" ;;
        *) return 1 ;;
    esac
    slug="${slug%/}"
    slug="${slug%.git}"
    rp_charset_only "$host" "$RP_HOST_CHARSET" || return 1
    rp_charset_only "$slug" "$RP_SLUG_CHARSET" || return 1
    [[ "$slug" == */* && "$slug" != /* && "$slug" != */ && "$slug" != *//* ]] || return 1
    case "$(detect_platform_from_url "$url")" in
        github) RP_PLATFORM=github ;;
        gitlab) RP_PLATFORM=gitlab ;;
        *) return 1 ;;
    esac
    RP_ORIGIN_HOST="$host"
    RP_SLUG="$slug"
}

# release_publication_release_url <tag> — the release page (after
# release_publication_origin).
release_publication_release_url() {
    case "$RP_PLATFORM" in
        github) printf 'https://%s/%s/releases/tag/%s\n' "$RP_ORIGIN_HOST" "$RP_SLUG" "$1" ;;
        gitlab) printf 'https://%s/%s/-/releases/%s\n' "$RP_ORIGIN_HOST" "$RP_SLUG" "$1" ;;
        *) return 1 ;;
    esac
}

# Percent-encode a path segment (slug or tag): every byte outside the
# unreserved set. Inputs are already charset-validated.
rp_urlenc() {
    local s="$1" out="" i c
    for (( i = 0; i < ${#s}; i++ )); do
        c="${s:i:1}"
        case "$c" in
            [ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._~-]) out+="$c" ;;
            *) out+="$(printf '%%%02X' "'$c")" ;;
        esac
    done
    printf '%s\n' "$out"
}

_rp_gh_repo() {
    if [[ "$RP_ORIGIN_HOST" == "github.com" ]]; then
        printf '%s\n' "$RP_SLUG"
    else
        printf '%s/%s\n' "$RP_ORIGIN_HOST" "$RP_SLUG"
    fi
}

# glab's -R takes GROUP/NAMESPACE/REPO for gitlab.com and a full URL otherwise.
_rp_glab_repo() {
    if [[ "$RP_ORIGIN_HOST" == "gitlab.com" ]]; then
        printf '%s\n' "$RP_SLUG"
    else
        printf 'https://%s/%s\n' "$RP_ORIGIN_HOST" "$RP_SLUG"
    fi
}

_rp_glab_host_args() {
    RP_GLAB_HOST_ARGS=()
    if [[ "$RP_ORIGIN_HOST" != "gitlab.com" ]]; then
        RP_GLAB_HOST_ARGS=(--hostname "$RP_ORIGIN_HOST")
    fi
}

# --- The check -------------------------------------------------------------

# _rp_out <line> <rc> — print the one result line and return its rc.
_rp_out() { printf 'PUBLICATION:%s\n' "$1"; return "$2"; }

# _rp_csv_add <var> <name> — append a name to a csv variable, once.
_rp_csv_add() {
    local -n _csv="$1"
    case ",$_csv," in *",$2,"*) return 0 ;; esac
    _csv="${_csv:+$_csv,}$2"
}

# release_publication_check <tag> — one non-waiting check. Prints exactly one
# line and returns:
#   PUBLICATION:published|<run-id or ->       rc 0
#   PUBLICATION:pending:<reason>              rc 10
#   PUBLICATION:failed:<reason>               rc 11
#   PUBLICATION:unknown:<reason>              rc 12
# Runs in a subshell so no helper's die or global can escape into the caller.
release_publication_check() (
    local tag="${1-}" tag_sha remote_lines remote_sha peeled direct line
    local -a assets=() required=() manifest_names=()
    local -A asset_state=() asset_size=()
    local missing="" run_id="-" err out rc name glob st sz m listed
    local tmp

    rp_valid_tag "$tag" || _rp_out "unknown:invalid_tag" 12 || exit $?
    release_publication_policy_load \
        || { _rp_out "unknown:policy_unreadable:$RP_POLICY_ERR" 12; exit $?; }

    # 1. The remote tag must point at the local tag's commit.
    tag_sha="$(git rev-parse --verify --quiet "refs/tags/${tag}^{commit}" 2>/dev/null)" \
        || { _rp_out "failed:remote_tag_missing" 11; exit $?; }
    remote_lines="$(git ls-remote --tags origin "refs/tags/${tag}" "refs/tags/${tag}^{}" 2>/dev/null)" \
        || { _rp_out "unknown:api_error" 12; exit $?; }
    peeled=""
    direct=""
    while IFS=$'\t' read -r remote_sha line; do
        [[ -n "$remote_sha" ]] || continue
        if [[ "$line" == "refs/tags/${tag}^{}" ]]; then peeled="$remote_sha"
        elif [[ "$line" == "refs/tags/${tag}" ]]; then direct="$remote_sha"; fi
    done <<< "$remote_lines"
    remote_sha="${peeled:-$direct}"
    [[ -n "$remote_sha" ]] || { _rp_out "failed:remote_tag_missing" 11; exit $?; }
    [[ "$remote_sha" == "$tag_sha" ]] || { _rp_out "failed:tag_mismatch" 11; exit $?; }

    # 2. Platform and repository from origin.
    release_publication_origin || { _rp_out "unknown:platform" 12; exit $?; }

    tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_relpub_XXXXXX")" \
        || { _rp_out "unknown:api_error" 12; exit $?; }
    trap 'rm -rf "$tmp"' EXIT  # archive-sweep: subshell-local

    if [[ "$RP_PLATFORM" == github ]]; then
        command -v gh >/dev/null 2>&1 || { _rp_out "unknown:cli_missing" 12; exit $?; }
        # 3. The release object.
        rc=0
        out="$(gh release view "$tag" -R "$(_rp_gh_repo)" --json tagName,isDraft,assets \
            --jq '"R\t\(.tagName)\t\(.isDraft)", (.assets[] | "A\t\(.name)\t\(.state)\t\(.size)")' \
            2>"$tmp/err")" || rc=$?
        if [[ "$rc" != 0 ]]; then
            err="$(cat "$tmp/err" 2>/dev/null)"
            if [[ "$err" == *"release not found"* ]]; then
                _rp_out "pending:no_release" 10; exit $?
            fi
            _rp_out "unknown:api_error" 12; exit $?
        fi
        line="$(printf '%s\n' "$out" | sed -n '1p')"
        [[ "$line" == R$'\t'* ]] || { _rp_out "unknown:unparseable" 12; exit $?; }
        line="${line#R$'\t'}"
        [[ "${line%%$'\t'*}" == "$tag" ]] || { _rp_out "failed:tag_mismatch" 11; exit $?; }
        case "${line#*$'\t'}" in
            false) ;;
            true) _rp_out "pending:draft" 10; exit $? ;;
            *) _rp_out "unknown:unparseable" 12; exit $? ;;
        esac
        while IFS=$'\t' read -r m name st sz; do
            [[ "$m" == A ]] || continue
            assets+=("$name")
            asset_state["$name"]="$st"
            asset_size["$name"]="$sz"
        done < <(printf '%s\n' "$out" | sed '1d')

        # 5. The workflow run for this tag and this commit.
        if [[ -n "$RP_WORKFLOW" ]]; then
            local best_id="" best_status="" best_conc="" id sha br status conc
            rc=0
            out="$(gh run list -R "$(_rp_gh_repo)" --workflow "$RP_WORKFLOW" --event push \
                --branch "$tag" --limit 50 \
                --json databaseId,headSha,headBranch,status,conclusion,createdAt \
                --jq '.[] | "\(.databaseId)\t\(.headSha)\t\(.headBranch)\t\(.status)\t\(.conclusion)"' \
                2>/dev/null)" || rc=$?
            [[ "$rc" == 0 ]] || { _rp_out "unknown:api_error" 12; exit $?; }
            while IFS=$'\t' read -r id sha br status conc; do
                [[ -n "$id" ]] || continue
                [[ "$id" =~ ^[0123456789]+$ ]] || { _rp_out "unknown:unparseable" 12; exit $?; }
                [[ "$br" == "$tag" && "$sha" == "$tag_sha" ]] || continue
                if [[ -z "$best_id" ]] || (( id > best_id )); then
                    best_id="$id"; best_status="$status"; best_conc="$conc"
                fi
            done <<< "$out"
            [[ -n "$best_id" ]] || { _rp_out "pending:run_not_found" 10; exit $?; }
            [[ "$best_status" == completed ]] || { _rp_out "pending:run_in_progress" 10; exit $?; }
            [[ "$best_conc" == success ]] \
                || { _rp_out "failed:workflow_failed:${best_conc:-none}" 11; exit $?; }
            run_id="$best_id"
        fi
    else
        command -v glab >/dev/null 2>&1 || { _rp_out "unknown:cli_missing" 12; exit $?; }
        command -v jq >/dev/null 2>&1 || { _rp_out "unknown:cli_missing" 12; exit $?; }
        [[ -z "$RP_WORKFLOW" ]] || { _rp_out "unknown:workflow_unsupported" 12; exit $?; }
        _rp_glab_host_args
        rc=0
        out="$(glab api "${RP_GLAB_HOST_ARGS[@]}" \
            "projects/$(rp_urlenc "$RP_SLUG")/releases/$(rp_urlenc "$tag")" 2>"$tmp/err")" || rc=$?
        if [[ "$rc" != 0 ]]; then
            err="$(cat "$tmp/err" 2>/dev/null)"
            if [[ "$err" == *"404"* ]]; then
                _rp_out "pending:no_release" 10; exit $?
            fi
            _rp_out "unknown:api_error" 12; exit $?
        fi
        out="$(printf '%s' "$out" | jq -r \
            '"R\t\(.tag_name)\t\(.upcoming_release // false)", (.assets.links[]? | "A\t\(.name)")' \
            2>/dev/null)" || { _rp_out "unknown:unparseable" 12; exit $?; }
        line="$(printf '%s\n' "$out" | sed -n '1p')"
        [[ "$line" == R$'\t'* ]] || { _rp_out "unknown:unparseable" 12; exit $?; }
        line="${line#R$'\t'}"
        [[ "${line%%$'\t'*}" == "$tag" ]] || { _rp_out "failed:tag_mismatch" 11; exit $?; }
        case "${line#*$'\t'}" in
            false) ;;
            true) _rp_out "pending:upcoming" 10; exit $? ;;
            *) _rp_out "unknown:unparseable" 12; exit $? ;;
        esac
        while IFS=$'\t' read -r m name; do
            [[ "$m" == A ]] || continue
            assets+=("$name")
            # GitLab links carry no upload state or size: presence is the rule.
            asset_state["$name"]="uploaded"
            asset_size["$name"]="1"
        done < <(printf '%s\n' "$out" | sed '1d')
    fi

    # 6. Required assets.
    mapfile -t required < <(release_publication_expand_assets "$tag") \
        || true
    if (( ${#RP_ASSETS[@]} )) && (( ${#required[@]} != ${#RP_ASSETS[@]} )); then
        _rp_out "unknown:policy_unreadable:release_publication_assets" 12; exit $?
    fi
    _rp_asset_ok() {
        [[ -n "${asset_state[$1]+x}" && "${asset_state[$1]}" == uploaded ]] || return 1
        [[ "${asset_size[$1]}" =~ ^[0123456789]+$ ]] && (( ${asset_size[$1]} > 0 ))
    }
    for name in "${required[@]}"; do
        _rp_asset_ok "$name" || _rp_csv_add missing "$name"
    done

    # Checksum manifests: every file a manifest lists must be published too.
    for glob in "${RP_MANIFESTS[@]}"; do
        manifest_names=()
        for name in "${assets[@]}"; do
            # shellcheck disable=SC2053  # $glob IS the pattern, by design
            [[ "$name" == $glob ]] && manifest_names+=("$name")
        done
        if (( ${#manifest_names[@]} == 0 )); then
            _rp_out "pending:manifest_missing:$glob" 10; exit $?
        fi
        for m in "${manifest_names[@]}"; do
            rp_charset_only "$m" "$RP_NAME_CHARSET" || { _rp_out "unknown:unparseable" 12; exit $?; }
            if ! _rp_asset_ok "$m"; then
                _rp_csv_add missing "$m"
                continue
            fi
            rm -rf "$tmp/dl"; mkdir -p "$tmp/dl"
            rc=0
            if [[ "$RP_PLATFORM" == github ]]; then
                gh release download "$tag" -R "$(_rp_gh_repo)" -p "$m" -O "$tmp/dl/$m" \
                    >/dev/null 2>&1 || rc=$?
            else
                glab release download "$tag" -R "$(_rp_glab_repo)" -n "$m" -D "$tmp/dl" \
                    >/dev/null 2>&1 || rc=$?
            fi
            [[ "$rc" == 0 && -f "$tmp/dl/$m" ]] || { _rp_out "unknown:api_error" 12; exit $?; }
            while IFS= read -r line || [[ -n "$line" ]]; do
                line="${line%$'\r'}"
                [[ -n "${line//[[:space:]]/}" ]] || continue
                if [[ "$line" =~ ^[0123456789abcdef]{64}[\ ][\ *](.+)$ ]]; then
                    listed="${BASH_REMATCH[1]}"
                    rp_charset_only "$listed" "$RP_NAME_CHARSET" \
                        || { _rp_out "unknown:unparseable" 12; exit $?; }
                    _rp_asset_ok "$listed" || _rp_csv_add missing "$listed"
                else
                    _rp_out "unknown:unparseable" 12; exit $?
                fi
            done < "$tmp/dl/$m"
        done
    done

    if [[ -n "$missing" ]]; then
        _rp_out "pending:assets_missing:$missing" 10; exit $?
    fi
    _rp_out "published|$run_id" 0
)
