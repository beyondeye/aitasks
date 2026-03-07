#!/usr/bin/env bash
# repo_fetch.sh — Multi-platform repository file fetching and directory listing
# Supports GitHub, GitLab, and Bitbucket URLs
#
# Public functions:
#   repo_detect_platform_from_url URL  — Returns: github|gitlab|bitbucket|""
#   repo_parse_url URL                 — Sets: _RF_PLATFORM, _RF_OWNER, _RF_REPO, _RF_BRANCH, _RF_PATH, _RF_TYPE
#   repo_fetch_file URL                — Prints raw file content to stdout
#   repo_list_md_files URL             — Prints .md filenames (one per line)

[[ -n "${_AIT_REPO_FETCH_LOADED:-}" ]] && return 0
_AIT_REPO_FETCH_LOADED=1

SCRIPT_DIR_RF="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR_RF}/terminal_compat.sh"

# --- Global state set by repo_parse_url ---
_RF_PLATFORM=""
_RF_OWNER=""
_RF_REPO=""
_RF_BRANCH=""
_RF_PATH=""
_RF_TYPE=""  # "file" or "directory"

# ============================================================
# INTERNAL HELPERS
# ============================================================

_rf_has_cmd() { command -v "$1" &>/dev/null; }

# Portable base64 decode (macOS: -D, Linux: -d)
_rf_base64_decode() {
    if [[ "$(uname -s)" == "Darwin" ]]; then
        base64 -D
    else
        base64 -d
    fi
}

# URL-encode forward slashes for GitLab API paths
_rf_url_encode_path() {
    local path="$1"
    echo "${path//\//%2F}"
}

# ============================================================
# PUBLIC FUNCTIONS
# ============================================================

# Detect platform from a repository URL
# Input: URL string
# Output: "github", "gitlab", "bitbucket", or "" (unknown)
repo_detect_platform_from_url() {
    local url="$1"
    if [[ "$url" == *"gitlab.com"* ]]; then
        echo "gitlab"
    elif [[ "$url" == *"bitbucket.org"* ]]; then
        echo "bitbucket"
    elif [[ "$url" == *"github.com"* ]]; then
        echo "github"
    else
        echo ""
    fi
}

# Parse a repository URL into components
# Sets global variables: _RF_PLATFORM, _RF_OWNER, _RF_REPO, _RF_BRANCH, _RF_PATH, _RF_TYPE
repo_parse_url() {
    local url="$1"

    _RF_PLATFORM=""
    _RF_OWNER=""
    _RF_REPO=""
    _RF_BRANCH=""
    _RF_PATH=""
    _RF_TYPE=""

    _RF_PLATFORM=$(repo_detect_platform_from_url "$url")
    [[ -z "$_RF_PLATFORM" ]] && die "Cannot detect platform from URL: $url"

    # Strip protocol and hostname
    local path_part
    case "$_RF_PLATFORM" in
        github)    path_part="${url#*github.com/}" ;;
        gitlab)    path_part="${url#*gitlab.com/}" ;;
        bitbucket) path_part="${url#*bitbucket.org/}" ;;
    esac

    # Extract owner and repo (first two path segments)
    _RF_OWNER="${path_part%%/*}"
    local after_owner="${path_part#*/}"
    _RF_REPO="${after_owner%%/*}"
    local after_repo="${after_owner#*/}"

    # Parse branch/path based on platform-specific URL patterns
    case "$_RF_PLATFORM" in
        github)
            if [[ "$after_repo" == blob/* ]]; then
                _RF_TYPE="file"
                local after_token="${after_repo#blob/}"
                _RF_BRANCH="${after_token%%/*}"
                _RF_PATH="${after_token#*/}"
            elif [[ "$after_repo" == tree/* ]]; then
                _RF_TYPE="directory"
                local after_token="${after_repo#tree/}"
                _RF_BRANCH="${after_token%%/*}"
                _RF_PATH="${after_token#*/}"
            else
                die "Cannot parse GitHub URL (expected /blob/ or /tree/): $url"
            fi
            ;;
        gitlab)
            if [[ "$after_repo" == -/blob/* ]]; then
                _RF_TYPE="file"
                local after_token="${after_repo#-/blob/}"
                _RF_BRANCH="${after_token%%/*}"
                _RF_PATH="${after_token#*/}"
            elif [[ "$after_repo" == -/tree/* ]]; then
                _RF_TYPE="directory"
                local after_token="${after_repo#-/tree/}"
                _RF_BRANCH="${after_token%%/*}"
                _RF_PATH="${after_token#*/}"
            else
                die "Cannot parse GitLab URL (expected /-/blob/ or /-/tree/): $url"
            fi
            ;;
        bitbucket)
            if [[ "$after_repo" == src/* ]]; then
                local after_token="${after_repo#src/}"
                _RF_BRANCH="${after_token%%/*}"
                _RF_PATH="${after_token#*/}"
                # Heuristic: if last path segment has a dot extension, it's a file
                local basename="${_RF_PATH##*/}"
                if [[ "$basename" == *.* ]]; then
                    _RF_TYPE="file"
                else
                    _RF_TYPE="directory"
                fi
            else
                die "Cannot parse Bitbucket URL (expected /src/): $url"
            fi
            ;;
    esac

    # Strip trailing slashes from path
    _RF_PATH="${_RF_PATH%/}"
}

# Fetch a single file's raw content to stdout
# Input: repository URL pointing to a file
repo_fetch_file() {
    local url="$1"
    repo_parse_url "$url"

    if [[ "$_RF_TYPE" != "file" ]]; then
        die "URL does not point to a file: $url"
    fi

    case "$_RF_PLATFORM" in
        github)  _rf_fetch_file_github ;;
        gitlab)  _rf_fetch_file_gitlab ;;
        bitbucket) _rf_fetch_file_bitbucket ;;
    esac
}

# List .md filenames in a directory (one per line)
# Input: repository URL pointing to a directory
repo_list_md_files() {
    local url="$1"
    repo_parse_url "$url"

    _rf_has_cmd jq || die "jq is required for directory listing. Install via your package manager."
    if [[ "$_RF_TYPE" != "directory" ]]; then
        die "URL does not point to a directory: $url"
    fi

    case "$_RF_PLATFORM" in
        github)  _rf_list_md_github ;;
        gitlab)  _rf_list_md_gitlab ;;
        bitbucket) _rf_list_md_bitbucket ;;
    esac
}

# ============================================================
# PLATFORM BACKENDS — File fetching
# ============================================================

_rf_fetch_file_github() {
    # Try gh CLI first
    if _rf_has_cmd gh && gh auth status &>/dev/null 2>&1; then
        local content
        content=$(gh api "repos/${_RF_OWNER}/${_RF_REPO}/contents/${_RF_PATH}?ref=${_RF_BRANCH}" --jq '.content' 2>/dev/null) && {
            echo "$content" | _rf_base64_decode
            return 0
        }
    fi
    # Fallback to curl on raw URL
    curl -fsSL "https://raw.githubusercontent.com/${_RF_OWNER}/${_RF_REPO}/${_RF_BRANCH}/${_RF_PATH}"
}

_rf_fetch_file_gitlab() {
    local encoded_path
    encoded_path=$(_rf_url_encode_path "$_RF_PATH")
    # Try glab CLI first
    if _rf_has_cmd glab && glab auth status &>/dev/null 2>&1; then
        glab api "projects/${_RF_OWNER}%2F${_RF_REPO}/repository/files/${encoded_path}/raw?ref=${_RF_BRANCH}" 2>/dev/null && return 0
    fi
    # Fallback to curl on raw URL
    curl -fsSL "https://gitlab.com/${_RF_OWNER}/${_RF_REPO}/-/raw/${_RF_BRANCH}/${_RF_PATH}"
}

_rf_fetch_file_bitbucket() {
    # Bitbucket has no dedicated CLI for file content — use curl directly
    curl -fsSL "https://bitbucket.org/${_RF_OWNER}/${_RF_REPO}/raw/${_RF_BRANCH}/${_RF_PATH}"
}

# ============================================================
# PLATFORM BACKENDS — Directory listing (.md files)
# ============================================================

_rf_list_md_github() {
    local json
    # Try gh CLI first
    if _rf_has_cmd gh && gh auth status &>/dev/null 2>&1; then
        json=$(gh api "repos/${_RF_OWNER}/${_RF_REPO}/contents/${_RF_PATH}?ref=${_RF_BRANCH}" 2>/dev/null) && {
            echo "$json" | jq -r '.[] | select(.name | endswith(".md")) | .name'
            return 0
        }
    fi
    # Fallback: no simple curl fallback for directory listing — require gh
    die "gh CLI is required for GitHub directory listing. Install: https://cli.github.com/"
}

_rf_list_md_gitlab() {
    local encoded_path json
    encoded_path=$(_rf_url_encode_path "$_RF_PATH")
    # Try glab CLI first
    if _rf_has_cmd glab && glab auth status &>/dev/null 2>&1; then
        json=$(glab api "projects/${_RF_OWNER}%2F${_RF_REPO}/repository/tree?path=${_RF_PATH}&ref=${_RF_BRANCH}&per_page=100" 2>/dev/null) && {
            echo "$json" | jq -r '.[] | select(.type == "blob") | select(.name | endswith(".md")) | .name'
            return 0
        }
    fi
    # Fallback: GitLab REST API is public for public repos
    json=$(curl -fsSL "https://gitlab.com/api/v4/projects/${_RF_OWNER}%2F${_RF_REPO}/repository/tree?path=${_RF_PATH}&ref=${_RF_BRANCH}&per_page=100" 2>/dev/null) && {
        echo "$json" | jq -r '.[] | select(.type == "blob") | select(.name | endswith(".md")) | .name'
        return 0
    }
    die "Failed to list GitLab directory: ${_RF_OWNER}/${_RF_REPO}/${_RF_PATH}"
}

_rf_list_md_bitbucket() {
    local json api_path
    api_path="${_RF_BRANCH}"
    [[ -n "$_RF_PATH" ]] && api_path="${api_path}/${_RF_PATH}"
    json=$(curl -fsSL "https://api.bitbucket.org/2.0/repositories/${_RF_OWNER}/${_RF_REPO}/src/${api_path}/?pagelen=100" 2>/dev/null) && {
        echo "$json" | jq -r '.values[] | select(.path | endswith(".md")) | .path | split("/") | last'
        return 0
    }
    die "Failed to list Bitbucket directory: ${_RF_OWNER}/${_RF_REPO}/${_RF_PATH}"
}
