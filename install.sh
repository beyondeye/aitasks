#!/usr/bin/env bash
set -euo pipefail

# install.sh - Curl-friendly bootstrap installer for the aitask framework
# Usage: curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash
#   or:  bash install.sh [--force] [--dir PATH] [--local-tarball PATH]

REPO="beyondeye/aitasks"
INSTALL_DIR="."
FORCE=false
# true when this run overwrites an existing install (the `ait upgrade` path).
EXISTING_INSTALL=false
LOCAL_TARBALL=""
# Explicit release version to install (no leading 'v'). Set by --version or the
# AIT_TARGET_VERSION env var (the latter is how `ait upgrade` threads the
# resolved version through). Empty => resolve the latest release.
TARGET_VERSION=""
# Test map engine flags, passed through to install_engine_binary() from
# aitask_setup.sh (t1852_5). --local-engine is resolved to an absolute path here.
ENGINE_ARGS=()
ENGINE_NO_TESTMAP=false
ENGINE_OTHER_FLAG=false

# --- Color helpers ---
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BLUE='\033[0;34m'; NC='\033[0m'
info()    { echo -e "${BLUE}[ait]${NC} $1"; }
success() { echo -e "${GREEN}[ait]${NC} $1"; }
warn()    { echo -e "${YELLOW}[ait]${NC} $1"; }
die()     { echo -e "${RED}[ait] Error:${NC} $1" >&2; exit 1; }

# --- Usage ---
usage() {
    cat <<EOF
Usage: install.sh [OPTIONS]

Install the aitask framework into a project directory.

Options:
  --force             Overwrite existing framework files (preserves data dirs)
  --dir PATH          Install to PATH instead of current directory
  --version VERSION   Install a specific release (e.g. 0.26.1) directly from the
                      release-assets CDN — no GitHub REST API call. Defaults to
                      the latest release when omitted.
  --local-tarball PATH  Use a local tarball instead of downloading from GitHub
                      (an offline install: the test map engine is not fetched)
  --local-engine PATH Install this ait-testmap binary as the test map engine
  --engine-from-source
                      If no release engine can be fetched, build one from the Go
                      source (aitasks framework checkout only; needs Go)
  --force-engine      Replace an engine slot marked as a custom build (.dev)
  --no-testmap        Skip the test map engine install
  --help              Show this help message

Examples:
  curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash
  bash install.sh --dir ~/my-project
  bash install.sh --force
  bash install.sh --version 0.26.1
  bash install.sh --local-tarball ./aitasks-0.1.0.tar.gz
EOF
    exit 0
}

# --- Argument parsing ---
while [[ $# -gt 0 ]]; do
    case "$1" in
        --force)
            FORCE=true
            shift
            ;;
        --source-only)
            # Sourced for tests (to reach functions like
            # cleanup_packaging_leftover) — stop parsing here. Function
            # definitions below still load; the guard before `main "$@"`
            # returns before the installer runs. Leave $1 set so that guard matches.
            break
            ;;
        --dir)
            [[ $# -ge 2 ]] || die "--dir requires a path argument"
            INSTALL_DIR="$2"
            shift 2
            ;;
        --version)
            [[ $# -ge 2 ]] || die "--version requires a version argument"
            TARGET_VERSION="$2"
            shift 2
            ;;
        --local-tarball)
            [[ $# -ge 2 ]] || die "--local-tarball requires a path argument"
            LOCAL_TARBALL="$2"
            shift 2
            ;;
        --local-engine)
            [[ $# -ge 2 && -n "$2" ]] || die "--local-engine requires a path argument"
            [[ -f "$2" ]] || die "--local-engine: no such file: $2"
            ENGINE_ARGS+=(--local-engine "$(cd "$(dirname "$2")" && pwd)/$(basename "$2")")
            ENGINE_OTHER_FLAG=true
            shift 2
            ;;
        --engine-from-source)
            ENGINE_ARGS+=(--engine-from-source); ENGINE_OTHER_FLAG=true; shift
            ;;
        --force-engine)
            ENGINE_ARGS+=(--force-engine); ENGINE_OTHER_FLAG=true; shift
            ;;
        --no-testmap)
            ENGINE_ARGS+=(--no-testmap); ENGINE_NO_TESTMAP=true; shift
            ;;
        --help|-h)
            usage
            ;;
        *)
            die "Unknown option: $1. Use --help for usage."
            ;;
    esac
done

if [[ "$ENGINE_NO_TESTMAP" == true && "$ENGINE_OTHER_FLAG" == true ]]; then
    die "--no-testmap cannot be combined with --local-engine, --engine-from-source or --force-engine"
fi

# Resolve INSTALL_DIR to absolute path
INSTALL_DIR="$(cd "$INSTALL_DIR" 2>/dev/null && pwd)" || die "Directory does not exist: $INSTALL_DIR"

# --- Prerequisites check ---
check_prerequisites() {
    if ! command -v tar &>/dev/null; then
        die "tar is required but not found. Install it and try again."
    fi

    DOWNLOAD_CMD=""
    if command -v curl &>/dev/null; then
        DOWNLOAD_CMD="curl"
    elif command -v wget &>/dev/null; then
        DOWNLOAD_CMD="wget"
    fi

    if [[ -z "$LOCAL_TARBALL" && -z "$DOWNLOAD_CMD" ]]; then
        die "curl or wget is required for downloading. Install one and try again."
    fi
}

# --- Safety check ---
check_existing_install() {
    if [[ -f "$INSTALL_DIR/ait" || -d "$INSTALL_DIR/.aitask-scripts" ]]; then
        if $FORCE; then
            warn "Existing installation found. --force specified, overwriting framework files..."
            EXISTING_INSTALL=true
            return
        fi

        # Existing install detected and --force was NOT passed.
        # If running in an interactive terminal, offer to overwrite.
        # Otherwise (curl|bash and similar non-TTY invocations), die with
        # a message that spells out all three recovery paths.
        if [[ -t 0 ]]; then
            warn "Existing aitasks installation found in $INSTALL_DIR (found ait or .aitask-scripts/)."
            info "  Recommended for existing installs: 'ait upgrade latest'"
            printf "  Overwrite framework files anyway? [y/N] "
            local answer
            read -r answer
            case "${answer:-N}" in
                [Yy]*)
                    FORCE=true
                    EXISTING_INSTALL=true
                    warn "Proceeding with overwrite (FORCE=true)..."
                    ;;
                *)
                    info "Aborted. To upgrade an existing install, run: ait upgrade latest"
                    exit 0
                    ;;
            esac
        else
            die "aitasks already installed in $INSTALL_DIR (found ait or .aitask-scripts/).
  To upgrade an existing install (recommended), run:
      ait upgrade latest
  To force a fresh re-install via curl-pipe:
      curl -fsSL https://raw.githubusercontent.com/$REPO/main/install.sh | bash -s -- --force
  To force a fresh re-install from a local file:
      bash install.sh --force"
        fi
    fi
}

# --- Interactive confirmation ---
confirm_install() {
    # When piped (curl | bash), stdin is not a terminal — skip prompt
    if [[ -t 0 ]]; then
        echo ""
        info "Will install aitasks framework to: $INSTALL_DIR"

        # Check if this looks like a git repo root
        if git -C "$INSTALL_DIR" rev-parse --is-inside-work-tree &>/dev/null; then
            local git_root
            git_root="$(git -C "$INSTALL_DIR" rev-parse --show-toplevel 2>/dev/null)" || true
            if [[ -n "$git_root" && "$git_root" != "$INSTALL_DIR" ]]; then
                warn "You are inside a git repository, but not at its root."
                info "  Git root: $git_root"
                info "  Current:  $INSTALL_DIR"
                info "aitasks should be installed at the git repository root."
                printf "  Continue installing here anyway? [y/N] "
                read -r answer
                case "${answer:-N}" in
                    [Yy]*) ;;
                    *) info "Aborted. Re-run from: $git_root"; exit 0 ;;
                esac
                return
            fi
        else
            warn "No git repository found in $INSTALL_DIR"
            info "aitasks is tightly integrated with git — task IDs, locking, and"
            info "sync all require a git repository. You should install aitasks at"
            info "the root of the project where you want to manage tasks."
            info ""
            info "If this is a new project, 'ait setup' will offer to run 'git init'."
        fi

        printf "  Install here? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi
}

# --- Download a URL to a file (follow redirects, fail on HTTP error) ---
# Returns the downloader's exit status so callers can fall back. The curl `-f`
# is load-bearing: without it curl exits 0 on a 404 and writes the error page to
# $dest, which would defeat the fallback logic in download_tarball(). `-L`
# follows the release CDN's 302 redirect. wget already exits non-zero on HTTP
# errors and follows redirects by default.
download_url() {
    local url="$1" dest="$2"
    if [[ "$DOWNLOAD_CMD" == "curl" ]]; then
        curl -fsSL --max-time 120 "$url" -o "$dest"
    else
        wget -q --timeout=120 "$url" -O "$dest"
    fi
}

# --- Bounded `git ls-remote` (mirror of lib/github_release.sh, t1244) ---
# These two helpers are install.sh's private copy of the bounded runner in
# .aitask-scripts/lib/github_release.sh. They carry DISTINCT names on purpose:
# tests/test_install_tarball_download.sh sources install.sh and then the library,
# bash resolves function calls dynamically, and a later definition wins — with
# shared names the library's copy would silently replace this one and the
# installer's own code would never be exercised.
_install_kill_descendants() {
    local pid="$1" child
    for child in $(pgrep -P "$pid" 2>/dev/null || true); do
        _install_kill_descendants "$child"
        kill "$child" 2>/dev/null || true
    done
}

# Process group first — it needs no external binary and reaches the whole tree.
# `pgrep` alone is not enough: minimal systems ship no procps, and there the
# walk silently degrades to a depth-1 kill that leaves every descendant running.
_install_kill_process_tree() {
    local pid="$1"
    kill -- "-$pid" 2>/dev/null || true
    _install_kill_descendants "$pid"
    kill "$pid" 2>/dev/null || true
}

# _install_ls_remote_tags <url>
# Time-bounded `git ls-remote`; prints nothing on timeout, always returns 0.
# A background job plus a polling watchdog rather than `timeout(1)` (macOS ships
# none, and the tests stub `git` as a shell function), writing to a temp file
# rather than a pipe so a surviving `git-remote-https` grandchild cannot keep a
# reader blocked. AIT_GIT_LSREMOTE_TIMEOUT overrides the 10s default; anything
# empty, zero, negative or non-numeric normalizes back to it — see the library
# copy for the full rationale.
_install_ls_remote_tags() {
    local url="$1"
    local timeout_s tmp pid deadline timed_out=0

    timeout_s="${AIT_GIT_LSREMOTE_TIMEOUT:-10}"
    if [[ "$timeout_s" =~ ^[0-9]+$ ]] && (( 10#$timeout_s > 0 )); then
        timeout_s=$(( 10#$timeout_s ))
    else
        timeout_s=10
    fi

    tmp="$(mktemp "${TMPDIR:-/tmp}/ait_lsremote.XXXXXX" 2>/dev/null)" || return 0

    # Job control for the launch only — it is what gives the job its own process
    # group, which is what makes the group kill above reach every descendant.
    local had_monitor=0
    case "$-" in *m*) had_monitor=1 ;; esac
    set -m
    GIT_TERMINAL_PROMPT=0 \
    GIT_HTTP_LOW_SPEED_LIMIT=1 \
    GIT_HTTP_LOW_SPEED_TIME="$timeout_s" \
    git ls-remote --tags --refs "$url" 'v*' >"$tmp" 2>/dev/null &
    pid=$!
    [[ "$had_monitor" -eq 1 ]] || set +m

    deadline=$(( SECONDS + timeout_s ))
    while kill -0 "$pid" 2>/dev/null && (( SECONDS < deadline )); do
        sleep 0.2 2>/dev/null || sleep 1
    done
    if kill -0 "$pid" 2>/dev/null; then
        timed_out=1
        _install_kill_process_tree "$pid"
    fi
    wait "$pid" 2>/dev/null || true

    if [[ "$timed_out" -eq 0 ]]; then
        cat "$tmp" 2>/dev/null || true
    fi
    rm -f "$tmp"
    return 0
}

# Resolve the latest release version from git tags — NO GitHub REST API call
# (the git protocol is exempt from the REST rate limit). install.sh runs
# standalone via `curl | bash`, so it CANNOT source
# .aitask-scripts/lib/github_release.sh (the lib is not on disk until we extract
# the tarball). This mirrors github_latest_tag_version() in that file — keep the
# two in sync, INCLUDING the time bound: without it a wedged network (a
# connection that blackholes instead of refusing) hangs the installer forever.
# Portable: ERE sed/grep + numeric sort, no GNU-isms (see
# aidocs/framework/sed_macos_issues.md). Prints the highest version (no 'v'), or
# nothing if git is unavailable, the lookup times out, or no tag matches.
resolve_latest_version_gittags() {
    command -v git &>/dev/null || return 0
    _install_ls_remote_tags "https://github.com/$REPO" \
        | sed -E 's#.*refs/tags/v?##' \
        | grep -E '^[0-9]+(\.[0-9]+)*$' \
        | sort -t. -k1,1n -k2,2n -k3,3n \
        | tail -1 || true
}

# Discover the release tarball URL via the GitHub REST API. This is the
# rate-limited LAST RESORT (only reached when the deterministic CDN download
# fails on the resolve-latest path). Honors $GH_TOKEN / $GITHUB_TOKEN, which
# raises the unauthenticated 60/hour cap to 5000/hour. Prints the URL, or
# nothing.
github_api_tarball_url() {
    local tok="${GH_TOKEN:-${GITHUB_TOKEN:-}}"
    local api_url="https://api.github.com/repos/$REPO/releases/latest"
    local api_response=""
    if [[ "$DOWNLOAD_CMD" == "curl" ]]; then
        local -a auth=()
        [[ -n "$tok" ]] && auth=(-H "Authorization: Bearer $tok")
        api_response="$(curl -sS --max-time 15 "${auth[@]+"${auth[@]}"}" "$api_url" 2>/dev/null)" || true
    else
        local -a auth=()
        [[ -n "$tok" ]] && auth=(--header="Authorization: Bearer $tok")
        api_response="$(wget -qO- --timeout=15 "${auth[@]+"${auth[@]}"}" "$api_url" 2>/dev/null)" || true
    fi

    [[ -z "$api_response" ]] && return 0
    printf '%s' "$api_response" \
        | grep '"browser_download_url".*\.tar\.gz"' \
        | head -1 \
        | sed 's/.*"\(http[^"]*\)".*/\1/'
}

# --- Download tarball ---
# Strategy (rate-limit-resilient — see t1075):
#   1. --local-tarball       -> copy it (unchanged)
#   2. explicit version      -> deterministic release-assets CDN URL, NO REST API
#   3. no version            -> resolve latest via git tags, then the CDN URL
#   4. CDN download fails     -> REST API last resort, EXCEPT when an explicit
#                               version was requested (then die — never silently
#                               install a different version).
download_tarball() {
    local dest="$1"

    if [[ -n "$LOCAL_TARBALL" ]]; then
        [[ -f "$LOCAL_TARBALL" ]] || die "Local tarball not found: $LOCAL_TARBALL"
        cp "$LOCAL_TARBALL" "$dest"
        return
    fi

    # An explicit target version (--version flag or AIT_TARGET_VERSION env, the
    # latter set by `ait upgrade`). The flag wins over the env var.
    local requested_version="${TARGET_VERSION:-${AIT_TARGET_VERSION:-}}"
    requested_version="${requested_version#v}"
    if [[ -n "$requested_version" \
          && ! "$requested_version" =~ ^[0-9]+\.[0-9]+(\.[0-9]+)?$ ]]; then
        die "Invalid version: $requested_version (expected X.Y.Z)"
    fi

    local version="$requested_version"
    if [[ -z "$version" ]]; then
        # Standalone curl|bash with no version: resolve latest via git tags
        # (exempt from the REST rate limit).
        info "Resolving latest aitasks release..."
        version="$(resolve_latest_version_gittags)" || true
    fi

    # The release asset name is deterministic (release.yml builds
    # aitasks-v<tag>.tar.gz) and lives on the release-assets CDN, NOT
    # api.github.com — so this path is not subject to the REST rate limit.
    if [[ -n "$version" ]]; then
        local cdn_url="https://github.com/$REPO/releases/download/v${version}/aitasks-v${version}.tar.gz"
        info "Downloading aitasks v${version}: $cdn_url"
        if download_url "$cdn_url" "$dest"; then
            return
        fi
        # An explicitly requested version that won't download must NOT silently
        # degrade to "latest" — that is exactly the defect this fix removes.
        if [[ -n "$requested_version" ]]; then
            die "Could not download aitasks v${version} from:
  $cdn_url
  Verify the version exists: https://github.com/$REPO/releases"
        fi
        warn "Direct download of v${version} failed — falling back to the GitHub API..."
    fi

    # Last resort: discover the URL via the (rate-limited) REST API.
    info "Fetching latest release via the GitHub API..."
    local tarball_url=""
    tarball_url="$(github_api_tarball_url)"

    if [[ -z "$tarball_url" ]]; then
        die "Could not find release tarball. Download manually from: https://github.com/$REPO/releases"
    fi

    info "Downloading: $tarball_url"
    download_url "$tarball_url" "$dest" || die "Download failed."
}

# --- Install skills ---
install_skills() {
    if [[ ! -d "$INSTALL_DIR/skills" ]]; then
        warn "No skills/ directory in tarball — skipping skill installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/.claude/skills"

    for skill_dir in "$INSTALL_DIR/skills"/*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/.claude/skills/$skill_name"
        cp -r "$skill_dir". "$INSTALL_DIR/.claude/skills/$skill_name/"
        info "  Installed skill: $skill_name"
    done

    # Clean up staging directory
    rm -rf "$INSTALL_DIR/skills"
}

# --- Prepare one data root that may be a dangling symlink ---
# In branch mode `aitasks/` and `aiplans/` are symlinks into the .aitask-data/
# worktree. When the target is absent the link DANGLES and `mkdir -p` through it
# fails ("File exists") — under `set -e` that aborts the whole install. Every
# step below create_data_dirs writes through these roots, so warn-and-skip would
# only move the abort downstream. Repair ONLY provably-leftover state; a link
# that looks like a real branch-mode layout is a hard error, never an unlink.
ensure_data_root() {
    local name="$1"
    local root="$INSTALL_DIR/$name"
    [[ -L "$root" && ! -e "$root" ]] || return 0

    # Only the exact form setup_data_branch() writes is recognized. Anything
    # else (absolute, ../…, custom) is user state we do not own — never touched,
    # so no unvalidated readlink target can reach an `mkdir` or an `rm`.
    #
    # That form is emitted by ait_data_link_target() in
    # .aitask-scripts/lib/data_symlinks.sh — the canonical writer. This check is
    # its only out-of-tree reader, and install.sh runs before that lib is usable,
    # so the literal below is duplicated on purpose. Change both together;
    # tests/test_init_data.sh Test 22 pins the emitted target (t1616).
    local target
    target="$(readlink "$root")"
    if [[ "$target" != ".aitask-data/$name" ]]; then
        die "$root is a dangling symlink to an unrecognized target ($target).
     Remove or repoint it, then re-run the install."
    fi

    local data_dir="$INSTALL_DIR/.aitask-data"
    local has_marker=false
    [[ -d "$data_dir/.git" || -f "$data_dir/.git" ]] && has_marker=true

    # Live worktree: the link is right, its target just is not materialized yet.
    # Create the path we construct ourselves, never the readlink output.
    if [[ "$has_marker" == true ]] \
       && git -C "$data_dir" rev-parse --is-inside-work-tree &>/dev/null; then
        mkdir -p "$data_dir/$name" 2>/dev/null || \
            die "Cannot create $data_dir/$name (target of $root)"
        return 0
    fi

    # Not live. Refuse to unlink if ANY signal says this repo really uses the
    # data branch — a stale/corrupt marker, a registered worktree, or the branch
    # ref itself. Deleting the link there would silently redirect framework
    # metadata into a real, gitignored dir that is NOT the data branch.
    if [[ "$has_marker" == true ]] \
       || git -C "$INSTALL_DIR" worktree list --porcelain 2>/dev/null \
            | grep -qE '^worktree .*/\.aitask-data$' \
       || git -C "$INSTALL_DIR" show-ref --verify --quiet refs/heads/aitask-data \
            2>/dev/null; then
        die "$root points at the aitask-data worktree, but .aitask-data/ is missing or unusable.
     Restore it, then re-run the install:
       git worktree prune && git worktree add .aitask-data aitask-data"
    fi

    # No data branch anywhere: the link resolves nowhere and nothing can be
    # written through it (e.g. a hand-built tarball that captured the repo's own
    # gitignored symlinks). Leftover state — replace it with a real directory.
    warn "Replacing dangling symlink $root -> $target with a real directory"
    rm -f "$root" || \
        die "Cannot replace dangling symlink $root — check directory permissions"
}

# --- Create data directories ---
create_data_dirs() {
    ensure_data_root aitasks
    ensure_data_root aiplans

    local d
    for d in aitasks/metadata aitasks/metadata/profiles aitasks/archived \
             aiplans/archived aireviewguides; do
        mkdir -p "$INSTALL_DIR/$d" 2>/dev/null || \
            die "Cannot create $INSTALL_DIR/$d — check for a broken symlink or permissions"
    done
}

# --- Merge seed file into destination (preserve existing user values) ---
# Usage: merge_seed <mode> <src> <dest> <label>
# Modes: yaml | json | json-models | text-union
# - If dest is missing: straight copy.
# - If dest exists and FORCE=true: merge via aitask_install_merge.py (existing
#   dest values win, new seed keys are added).
# - If dest exists and FORCE!=true: keep existing dest untouched.
merge_seed() {
    local mode="$1" src="$2" dest="$3" label="$4"
    if [[ ! -f "$dest" ]]; then
        mkdir -p "$(dirname "$dest")"
        cp "$src" "$dest"
        info "  Installed $label"
        return
    fi
    if [[ "$FORCE" != true ]]; then
        info "  $label exists (kept)"
        return
    fi
    # Pre-setup invocation. lib/python_resolve.sh is not yet usable here —
    # no AIT-resolved Python exists. System python3 only needs pyyaml, which
    # install.sh ensures via earlier prerequisites.
    if python3 "$INSTALL_DIR/.aitask-scripts/aitask_install_merge.py" "$mode" "$src" "$dest" 2>/dev/null; then
        info "  Merged $label (kept existing values, added new seed keys)"
    else
        warn "  Merge failed for $label — leaving existing file untouched"
    fi
}

# --- Install scoped .aitask-scripts/.gitignore ---
# Framework-owned gitignore that prevents Python cache artifacts from leaking
# into downstream project repos. Unconditionally overwritten each install.
install_seed_aitask_scripts_gitignore() {
    local src="$INSTALL_DIR/seed/aitask_scripts_gitignore.seed"
    local dest="$INSTALL_DIR/.aitask-scripts/.gitignore"
    if [[ ! -f "$src" ]]; then
        warn "No seed/aitask_scripts_gitignore.seed in tarball — skipping"
        return
    fi
    cp "$src" "$dest"
    info "  Installed .aitask-scripts/.gitignore"
}

# --- Install seed profiles ---
install_seed_profiles() {
    if [[ ! -d "$INSTALL_DIR/seed/profiles" ]]; then
        warn "No seed/profiles/ directory in tarball — skipping profile installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/profiles"

    for profile in "$INSTALL_DIR/seed/profiles"/*.yaml; do
        [[ -f "$profile" ]] || continue
        local bname
        bname="$(basename "$profile")"
        local dest="$INSTALL_DIR/aitasks/metadata/profiles/$bname"
        merge_seed yaml "$profile" "$dest" "profile: $bname"
    done

}

# --- Install seed task types ---
install_seed_task_types() {
    local src="$INSTALL_DIR/seed/task_types.txt"
    local dest="$INSTALL_DIR/aitasks/metadata/task_types.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/task_types.txt in tarball — skipping task types installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "task types: task_types.txt"
}

# --- Install seed project config ---
install_seed_project_config() {
    local src="$INSTALL_DIR/seed/project_config.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/project_config.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No seed/project_config.yaml in tarball — skipping project config installation"
        return
    fi

    merge_seed yaml "$src" "$dest" "project config: project_config.yaml"
}

# --- Install gate registry (t635_1) ---
# Source is the canonical reference under .aitask-scripts/ (t1147) — NOT seed/ —
# so upgrades of installed projects (where seed/ is deleted) can also reach it.
install_seed_gates_registry() {
    local src="$INSTALL_DIR/.aitask-scripts/gates_reference.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/gates.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No .aitask-scripts/gates_reference.yaml in tarball — skipping gate registry installation"
        return
    fi

    merge_seed yaml "$src" "$dest" "gate registry: gates.yaml"
}

# --- Install chatlink gateway config (t1120_2) ---
install_seed_chatlink_config() {
    local src="$INSTALL_DIR/seed/chatlink_config.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/chatlink_config.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No seed/chatlink_config.yaml in tarball — skipping chatlink config installation"
        return
    fi

    merge_seed yaml "$src" "$dest" "chatlink config: chatlink_config.yaml"
}

# --- Install AgentCrew runner config template (t1196) ---
# Copy-if-absent rather than merge_seed: the template carries NO active keys, so
# a --force `merge_seed yaml` would safe_dump an empty mapping and rewrite the
# file to a bare `{}`, destroying the documentation that is its entire purpose.
# Same shape as install_seed_doc_update_guide().
install_seed_crew_runner_config() {
    local src="$INSTALL_DIR/seed/crew_runner_config.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/crew_runner_config.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No seed/crew_runner_config.yaml in tarball — skipping crew runner config installation"
        return
    fi

    if [[ -f "$dest" ]]; then
        info "  Crew runner config exists (kept): crew_runner_config.yaml"
        return
    fi

    cp "$src" "$dest"
    info "  Installed crew runner config: crew_runner_config.yaml"
}

# --- Install starter tmux.conf template ---
install_seed_tmux_conf() {
    local src="$INSTALL_DIR/seed/tmux.conf"
    local dest_dir="$INSTALL_DIR/.aitask-scripts/templates"
    local dest="$dest_dir/tmux.conf"
    if [[ ! -f "$src" ]]; then
        warn "No seed/tmux.conf in tarball — skipping starter tmux.conf"
        return
    fi
    mkdir -p "$dest_dir"
    cp "$src" "$dest"
    info "  Installed starter tmux.conf template"
}

# --- Install seed review types ---
install_seed_reviewtypes() {
    local src="$INSTALL_DIR/seed/reviewguides/reviewtypes.txt"
    local dest="$INSTALL_DIR/aireviewguides/reviewtypes.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewguides/reviewtypes.txt in tarball — skipping review types installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "review types: reviewtypes.txt"
}

# --- Install seed review labels ---
install_seed_reviewlabels() {
    local src="$INSTALL_DIR/seed/reviewguides/reviewlabels.txt"
    local dest="$INSTALL_DIR/aireviewguides/reviewlabels.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewguides/reviewlabels.txt in tarball — skipping review labels installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "review labels: reviewlabels.txt"
}

# --- Install seed review environments ---
install_seed_reviewenvironments() {
    local src="$INSTALL_DIR/seed/reviewguides/reviewenvironments.txt"
    local dest="$INSTALL_DIR/aireviewguides/reviewenvironments.txt"

    if [[ ! -f "$src" ]]; then
        warn "No seed/reviewguides/reviewenvironments.txt in tarball — skipping review environments installation"
        return
    fi

    merge_seed text-union "$src" "$dest" "review environments: reviewenvironments.txt"
}

# --- Install seed review guides ---
# Review guides are user-editable prose. Never overwrite an existing guide, even
# on --force: only install guides whose destination does not yet exist.
install_seed_reviewguides() {
    if [[ ! -d "$INSTALL_DIR/seed/reviewguides" ]]; then
        warn "No seed/reviewguides/ directory in tarball — skipping review guide installation"
        return
    fi

    mkdir -p "$INSTALL_DIR/aireviewguides"

    while IFS= read -r -d '' mode_file; do
        local rel_path="${mode_file#$INSTALL_DIR/seed/reviewguides/}"
        local dest="$INSTALL_DIR/aireviewguides/$rel_path"
        mkdir -p "$(dirname "$dest")"
        if [[ -f "$dest" ]]; then
            info "  Review guide exists (kept): $rel_path"
        else
            cp "$mode_file" "$dest"
            info "  Installed review guide: $rel_path"
        fi
    done < <(find "$INSTALL_DIR/seed/reviewguides" -name "*.md" -type f -print0 2>/dev/null)

    local src_ignore="$INSTALL_DIR/seed/reviewguides/.reviewguidesignore"
    local dest_ignore="$INSTALL_DIR/aireviewguides/.reviewguidesignore"
    if [[ -f "$src_ignore" ]]; then
        if [[ -f "$dest_ignore" ]]; then
            info "  Filter file exists (kept): .reviewguidesignore"
        else
            cp "$src_ignore" "$dest_ignore"
            info "  Installed filter file: .reviewguidesignore"
        fi
    fi
}

# --- Install seed code areas map (t1194) ---
# Project-owned content (/aitask-contribute maintains areas:, aitask_codemap.sh
# refuses to write over it) — never overwrite an existing map, even on --force.
# A yaml merge would round-trip the file through yaml.safe_dump and destroy the
# format documentation in its header while adding nothing. Mirrors
# install_seed_reviewguides.
install_seed_code_areas() {
    local src="$INSTALL_DIR/seed/code_areas.yaml"
    local dest="$INSTALL_DIR/aitasks/metadata/code_areas.yaml"

    if [[ ! -f "$src" ]]; then
        warn "No seed/code_areas.yaml in tarball — skipping code areas installation"
        return
    fi

    if [[ -f "$dest" ]]; then
        info "  Code areas map exists (kept): code_areas.yaml"
        return
    fi

    cp "$src" "$dest"
    info "  Installed code areas map: code_areas.yaml"
}

# --- Install generic doc-update guide (t1194) ---
# The docs_updated gate resolves aitasks/metadata/doc_update_guide.md at runtime
# (seed/ is gone by then), so the tarball flow must install it. User-editable
# prose — never overwrite an existing guide, even on --force.
install_seed_doc_update_guide() {
    local src="$INSTALL_DIR/seed/doc_update_guide.md"
    local dest="$INSTALL_DIR/aitasks/metadata/doc_update_guide.md"

    if [[ ! -f "$src" ]]; then
        warn "No seed/doc_update_guide.md in tarball — skipping doc-update guide installation"
        return
    fi

    if [[ -f "$dest" ]]; then
        info "  Doc-update guide exists (kept): doc_update_guide.md"
        return
    fi

    cp "$src" "$dest"
    info "  Installed doc-update guide: doc_update_guide.md"
}

# --- Install seed code agent configuration ---
install_seed_codeagent_config() {
    local src="$INSTALL_DIR/seed/codeagent_config.json"
    local dest="$INSTALL_DIR/aitasks/metadata/codeagent_config.json"

    if [[ ! -f "$src" ]]; then
        warn "No seed/codeagent_config.json in tarball — skipping"
        return
    fi

    merge_seed json "$src" "$dest" "code agent config: codeagent_config.json"
}

# --- Install seed model configuration files ---
install_seed_models() {
    local found=false

    for src in "$INSTALL_DIR/seed"/models_*.json; do
        [[ -f "$src" ]] || continue
        found=true
        local bname
        bname="$(basename "$src")"
        local dest="$INSTALL_DIR/aitasks/metadata/$bname"
        merge_seed json-models "$src" "$dest" "model config: $bname"
    done

    if [[ "$found" == false ]]; then
        warn "No seed/models_*.json files in tarball — skipping model installation"
    fi
}

# --- Install seed Claude Code permissions ---
install_seed_claude_settings() {
    local src="$INSTALL_DIR/seed/claude_settings.local.json"
    local dest="$INSTALL_DIR/aitasks/metadata/claude_settings.seed.json"

    if [[ ! -f "$src" ]]; then
        warn "No seed/claude_settings.local.json in tarball — skipping"
        return
    fi

    cp "$src" "$dest"
    info "  Stored Claude Code permissions seed at aitasks/metadata/claude_settings.seed.json"
}

# --- Install seed Claude Code SessionStart hook ---
# Kept separate from the permissions seed above: the hook is framework
# infrastructure gated by its own consent prompt in `ait setup`, not a
# permission grant. NOTE: aitask_setup.sh's ensure_agent_config_seeds() carries
# the source-tree half of this manifest; tests/test_seed_manifest_drift.sh
# fails when the two sides disagree.
install_seed_claude_hooks() {
    local src="$INSTALL_DIR/seed/claude_settings.hooks.json"
    local dest="$INSTALL_DIR/aitasks/metadata/claude_settings.hooks.json"

    if [[ ! -f "$src" ]]; then
        warn "No seed/claude_settings.hooks.json in tarball — skipping"
        return
    fi

    cp "$src" "$dest"
    info "  Stored Claude Code session hook seed at aitasks/metadata/claude_settings.hooks.json"
}

# --- Report a missing Claude Code session hook (upgrade path only) ---
# install_seed_claude_hooks above only STAGES the hook seed; merging it into
# .claude/settings.json is `ait setup`'s job, behind its own consent prompt. A
# project that was only ever upgraded therefore never got the hook, and its
# Claude Code agents freeze into records that cannot be restored. Say so --
# never install it from here. Fresh installs are skipped: their closing banner
# already sends the user to `ait setup`. Non-fatal in every branch.
report_claude_session_hook() {
    [[ "$EXISTING_INSTALL" == true ]] || return 0
    local lib="$INSTALL_DIR/.aitask-scripts/lib/claude_hook_status.sh"
    [[ -f "$lib" ]] || return 0
    # shellcheck source=.aitask-scripts/lib/claude_hook_status.sh
    source "$lib" || return 0
    case "$(claude_session_hook_status "$INSTALL_DIR")" in
        MISSING)
            echo ""
            warn "$(claude_session_hook_hint)"
            ;;
        INVALID)
            echo ""
            warn "$(claude_session_hook_invalid_hint)"
            ;;
    esac
    return 0
}

# --- Store Codex CLI staging files ---
install_codex_staging() {
    if [[ ! -d "$INSTALL_DIR/codex_skills" ]]; then
        return
    fi

    mkdir -p "$INSTALL_DIR/aitasks/metadata/codex_skills"

    for skill_dir in "$INSTALL_DIR/codex_skills"/*/; do
        [[ -d "$skill_dir" ]] || continue
        local skill_name
        skill_name="$(basename "$skill_dir")"
        mkdir -p "$INSTALL_DIR/aitasks/metadata/codex_skills/$skill_name"
        cp -r "$skill_dir". "$INSTALL_DIR/aitasks/metadata/codex_skills/$skill_name/"
    done

    # Copy shared helper docs (codex)
    for doc in codex_tool_mapping.md; do
        if [[ -f "$INSTALL_DIR/codex_skills/$doc" ]]; then
            cp "$INSTALL_DIR/codex_skills/$doc" "$INSTALL_DIR/aitasks/metadata/codex_skills/$doc"
        fi
    done

    rm -rf "$INSTALL_DIR/codex_skills"
    info "  Stored Codex CLI skills staging at aitasks/metadata/codex_skills/"
}

# --- Store OpenCode staging files ---
install_opencode_staging() {
    if [[ ! -d "$INSTALL_DIR/opencode_skills" && ! -d "$INSTALL_DIR/opencode_commands" ]]; then
        return
    fi

    if [[ -d "$INSTALL_DIR/opencode_skills" ]]; then
        mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills"

        for skill_dir in "$INSTALL_DIR/opencode_skills"/*/; do
            [[ -d "$skill_dir" ]] || continue
            local skill_name
            skill_name="$(basename "$skill_dir")"
            mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name"
            cp -r "$skill_dir". "$INSTALL_DIR/aitasks/metadata/opencode_skills/$skill_name/"
        done

        # Copy shared OpenCode helper docs
        if [[ -f "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" ]]; then
            cp "$INSTALL_DIR/opencode_skills/opencode_tool_mapping.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_tool_mapping.md"
        fi
        if [[ -f "$INSTALL_DIR/opencode_skills/opencode_planmode_prereqs.md" ]]; then
            cp "$INSTALL_DIR/opencode_skills/opencode_planmode_prereqs.md" "$INSTALL_DIR/aitasks/metadata/opencode_skills/opencode_planmode_prereqs.md"
        fi

        rm -rf "$INSTALL_DIR/opencode_skills"
        info "  Stored OpenCode skills staging at aitasks/metadata/opencode_skills/"
    fi

    if [[ -d "$INSTALL_DIR/opencode_commands" ]]; then
        mkdir -p "$INSTALL_DIR/aitasks/metadata/opencode_commands"
        cp -r "$INSTALL_DIR/opencode_commands/." "$INSTALL_DIR/aitasks/metadata/opencode_commands/"
        rm -rf "$INSTALL_DIR/opencode_commands"
        info "  Stored OpenCode commands staging at aitasks/metadata/opencode_commands/"
    fi
}

# --- Prune retired skill surfaces (upgrade migration) ---
# install_skills(), setup_codex() and setup_opencode() are additive
# `mkdir -p` + `cp` loops — none of them removes a wrapper that DISAPPEARED
# upstream. Without this step an upgraded project keeps a discoverable slash
# command whose authoring template no longer exists.
#
# The helper decides ownership by CONTENT HASH, so a user-modified or
# user-authored file at a retired path is preserved and reported, never
# deleted; its stderr warning flows straight through to the user.
#
# Its deletions need no special staging here: commit_framework_files() and
# commit_installed_data_files() both discover changes with
# `git ls-files --modified`, which reports deleted files.
prune_retired_skills() {
    _prune_retired "retired_skills_manifest.txt" "skill" "Retired-skill" \
        "No retired skill surfaces present."
}

# --- Prune retired framework scripts (upgrade migration) ---
# The tarball extraction above is just as additive: a file the framework
# deleted or MOVED out of .aitask-scripts/ survives every upgrade and stays
# committed in the project. A moved Python module can then shadow its
# replacement — t1217's board/task_yaml.py → lib/task_yaml.py left a stale
# board/ copy that crashed every fresh `ait board`. Same helper, same
# content-hash ownership, its own manifest.
prune_retired_scripts() {
    _prune_retired "retired_scripts_manifest.txt" "script" "Retired-script" \
        "No retired framework scripts present."
}

# _prune_retired <manifest> <noun> <failure-prefix> <none-msg>
_prune_retired() {
    local manifest="$1" noun="$2" fail_prefix="$3" none_msg="$4"
    local helper="$INSTALL_DIR/.aitask-scripts/aitask_prune_retired_skills.sh"
    [[ -f "$helper" ]] || return 0

    local out pruned kept
    if ! out="$(bash "$helper" --dir "$INSTALL_DIR" \
            --manifest "$INSTALL_DIR/.aitask-scripts/$manifest" --label "$noun")"; then
        warn "  $fail_prefix prune failed — nothing was removed."
        return 0
    fi

    pruned="$(printf '%s\n' "$out" | grep -c '^PRUNED:')" || pruned=0
    kept="$(printf '%s\n' "$out" | grep -c '^KEPT:')" || kept=0

    if [[ "$pruned" -gt 0 ]]; then
        info "  Removed $pruned retired $noun path(s):"
        printf '%s\n' "$out" | grep '^PRUNED:' | sed 's/^PRUNED:/    /'
    fi
    if [[ "$kept" -gt 0 ]]; then
        info "  Kept $kept retired path(s) — see the warning above for cleanup."
    fi
    if [[ "$pruned" -eq 0 && "$kept" -eq 0 ]]; then
        info "  $none_msg"
    fi
}

# --- Store Codex CLI config and instructions seeds ---
install_seed_codex_config() {
    local src dest

    src="$INSTALL_DIR/seed/codex_config.seed.toml"
    dest="$INSTALL_DIR/aitasks/metadata/codex_config.seed.toml"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Codex CLI config seed"
    fi

    src="$INSTALL_DIR/seed/codex_rules.default.rules"
    dest="$INSTALL_DIR/aitasks/metadata/codex_rules.default.rules"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Codex CLI rules seed"
    fi

    src="$INSTALL_DIR/seed/codex_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/codex_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored Codex CLI instructions seed"
    fi

    src="$INSTALL_DIR/seed/aitasks_agent_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/aitasks_agent_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored shared agent instructions seed"
    fi
}

# --- Store OpenCode config and instructions seeds ---
install_seed_opencode_config() {
    local src dest

    src="$INSTALL_DIR/seed/opencode_config.seed.json"
    dest="$INSTALL_DIR/aitasks/metadata/opencode_config.seed.json"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored OpenCode config seed"
    fi

    src="$INSTALL_DIR/seed/opencode_instructions.seed.md"
    dest="$INSTALL_DIR/aitasks/metadata/opencode_instructions.seed.md"
    if [[ -f "$src" ]]; then
        cp "$src" "$dest"
        info "  Stored OpenCode instructions seed"
    fi
}

# --- Show changelog between versions (upgrade only) ---
show_upgrade_changelog() {
    local tarball_path="$1"
    local install_dir="$2"

    # Only relevant during upgrade (existing install + --force)
    if [[ "$FORCE" != true ]]; then
        return 0
    fi

    local current_version=""
    # .aitask-scripts/VERSION is authoritative from v0.3.0 on; the root VERSION
    # is only the pre-v0.3.0 fallback. Reading the root file first would take a
    # project's own VERSION (preserved across installs, t1772) for the
    # framework's, and compute the wrong changelog range on every upgrade.
    if [[ -f "$install_dir/.aitask-scripts/VERSION" ]]; then
        current_version="$(cat "$install_dir/.aitask-scripts/VERSION")"
    elif [[ -f "$install_dir/VERSION" ]]; then
        current_version="$(cat "$install_dir/VERSION")"
    else
        # Explicit 0: a bare `return` here would inherit the failed `[[ -f ]]`
        # test's status 1 and, under `set -euo pipefail`, abort the whole
        # installer silently right after the download (t1414).
        return 0  # Can't determine current version, skip
    fi

    # Extract VERSION and CHANGELOG.md from tarball into temp dir
    local tmpextract
    tmpextract="$(mktemp -d)"

    tar -xzf "$tarball_path" -C "$tmpextract" .aitask-scripts/VERSION 2>/dev/null || true
    tar -xzf "$tarball_path" -C "$tmpextract" CHANGELOG.md 2>/dev/null || true

    local new_version=""
    if [[ -f "$tmpextract/.aitask-scripts/VERSION" ]]; then
        new_version="$(cat "$tmpextract/.aitask-scripts/VERSION")"
    fi

    if [[ -z "$new_version" || "$current_version" == "$new_version" ]]; then
        rm -rf "$tmpextract"
        return 0
    fi

    info "Upgrading: v${current_version} → v${new_version}"

    if [[ -f "$tmpextract/CHANGELOG.md" ]]; then
        echo ""
        info "Changelog:"
        echo ""

        # Print all version sections newer than current_version
        local in_range=false
        while IFS= read -r line; do
            if [[ "$line" =~ ^##\ v ]]; then
                local heading_version
                heading_version="${line#\#\# v}"
                if [[ "$heading_version" == "$current_version" ]]; then
                    break  # Stop before current version's section
                fi
                in_range=true
            fi
            if $in_range; then
                echo "  $line"
            fi
        done < "$tmpextract/CHANGELOG.md"

        echo ""
    else
        warn "No CHANGELOG.md in release (changelog display requires aitasks >= next release)"
    fi

    rm -rf "$tmpextract"

    # Ask for confirmation (only when stdin is a terminal)
    if [[ -t 0 ]]; then
        printf "  Proceed with upgrade? [Y/n] "
        read -r answer
        case "${answer:-Y}" in
            [Yy]*|"") ;;
            *) info "Aborted."; exit 0 ;;
        esac
    fi
}

# --- Set permissions ---
set_permissions() {
    chmod +x "$INSTALL_DIR/ait"
    chmod +x "$INSTALL_DIR"/.aitask-scripts/*.sh
    # Shared libraries in lib/ (sourced, not executed, but keep +x for consistency)
    find "$INSTALL_DIR/.aitask-scripts/lib" -name '*.sh' -exec chmod +x {} + 2>/dev/null || true
}

# --- Pre-install dirty baseline ---
# The upgrade cannot tell "the installer wrote this file" from "the developer
# has uncommitted work here" by inspecting the tree at commit time. It can by
# looking twice: snapshot the dirty framework-path set BEFORE extraction, then
# commit only (changed-at-commit-time − baseline). Files in the baseline are
# left alone and reported, never committed — if the upgrade rewrites a file
# that was already dirty, that file's update goes uncommitted rather than
# sweeping the developer's edit into the framework commit.
#
# Mirrors snapshot_pre_setup_dirty / commit_framework_files in
# .aitask-scripts/aitask_setup.sh. The helpers are duplicated here because the
# snapshot runs before extraction, when the new aitask_setup.sh is not on disk
# (and install.sh runs stand-alone via curl|bash).
AIT_INSTALL_DIRTY_BASELINE=""
AIT_INSTALL_DATA_DIRTY_BASELINE=""
AIT_INSTALL_BASELINE_ARMED=0
# ARMED means "a snapshot ran"; UNVERIFIED means "it ran but could not read the
# dirty state", so its empty baseline is unknown rather than clean and the
# matching committer refuses. One flag per baseline, each read only by that
# baseline's committer (t2116). Keep these separate from ARMED.
AIT_INSTALL_BASELINE_UNVERIFIED=0
AIT_INSTALL_DATA_BASELINE_UNVERIFIED=0

# Print the framework pathspecs that exist in <dir>, one per line. With
# <include_absent>=1, print every pathspec: the baseline needs that, because a
# tracked framework file the user deleted (staged or not) is absent on disk yet
# is exactly a pre-existing change. `git add` rejects an unmatched pathspec, so
# the commit side stays existence-filtered.
# NOTE: duplicated in .aitask-scripts/aitask_setup.sh _ait_framework_paths(),
# which additionally lists install.sh and the CI files setup may install
# (install never commits those). If you change one, change the other.
_install_framework_paths() {
    local dir="$1" include_absent="${2:-0}" p
    local check_paths=(
        ".aitask-scripts/"
        "aitasks/metadata/"
        "aireviewguides/"
        "ait"
        ".claude/skills/"
        ".claude/settings.json"
        ".agents/"
        ".codex/"
        ".opencode/"
        ".gitignore"
        ".github/workflows/"
        "CLAUDE.md"
        "AGENTS.md"
        "opencode.json"
    )
    for p in "${check_paths[@]}"; do
        if [[ "$include_absent" == "1" || -e "$dir/$p" ]]; then
            printf '%s\n' "$p"
        fi
    done
    return 0
}

# Data-branch framework pathspecs (framework-owned config only — never task or
# plan content), with the same <include_absent> switch.
_install_data_framework_paths() {
    local dir="$1" include_absent="${2:-0}" p
    for p in "aitasks/metadata/" "aireviewguides/"; do
        if [[ "$include_absent" == "1" || -e "$dir/$p" ]]; then
            printf '%s\n' "$p"
        fi
    done
    return 0
}

# The main-repo commit eligibility: a work tree with .aitask-scripts/VERSION in
# the index. snapshot_pre_install_dirty and commit_installed_files test the SAME
# two predicates: a snapshot skipped in a state the committer acts in would
# leave it committing against an empty baseline. No HEAD is required —
# `ls-files --error-unmatch` reads the index, so a repository with no first
# commit and a staged VERSION is eligible.
_install_is_worktree() {
    git -C "$1" rev-parse --is-inside-work-tree &>/dev/null
}

# Is .aitask-scripts/VERSION in <dir>'s index? 0 = tracked, 1 = genuinely
# untracked (the project does not track the framework), 2 = unverified.
# `--error-unmatch` exits 1 for an untracked path and 128 for a git error, so
# the two are separable (t2116).
_install_version_tracked() {
    local rc=0
    git -C "$1" ls-files --error-unmatch -- .aitask-scripts/VERSION >/dev/null 2>&1 || rc=$?
    case $rc in 0) return 0 ;; 1) return 1 ;; *) return 2 ;; esac
}

# Data-worktree eligibility, shared by the data snapshot and
# commit_installed_data_files. Deliberately independent of the main repo's
# state: the data commit has no main-repo guard.
_install_data_worktree_present() {
    [[ -d "$1/.git" || -f "$1/.git" ]] && _install_is_worktree "$1"
}

# Regex excluding data-branch paths from the main worktree's change list in
# branch mode (they are committed by commit_installed_data_files). In branch
# mode `aitasks/` and `aiplans/` are symlinks into the `.aitask-data`
# worktree; `git ls-files` USUALLY skips pathspecs beyond such a symlink, but
# when the target is inside the worktree and the symlink is tracked it can
# walk through it. In legacy mode `aitasks/metadata/` lives on the main branch
# and must NOT be filtered.
_install_data_branch_exclude_re() {
    if [[ -d "$1/.aitask-data/.git" || -f "$1/.aitask-data/.git" ]]; then
        printf '%s' '^(aitasks|aiplans)/'
    fi
    return 0
}

# Emit the untracked + modified + staged set under <paths...> in <workdir>,
# deduplicated, minus interpreter caches and <extra_exclude_re> (empty = none).
# The staged term is load-bearing: a fully staged edit is invisible to both
# `ls-files --others` and `ls-files --modified`. `diff --cached` with no commit
# argument lists every staged path on an unborn HEAD, so staged content in a
# repository with no first commit still counts. --no-renames: with rename detection a staged rename lists
# only its destination, and the source — gone from the index, so invisible to
# `ls-files --modified` too — would miss the baseline; extraction recreates it
# and the commit would turn the user's pending rename into an addition.
# Mirrors _ait_list_framework_changes in aitask_setup.sh.
# Returns 0 when the list is verified; 2 when any probe failed, with stdout
# empty — an unreadable worktree is not a clean one (t2116).
_install_list_changes() {
    local workdir="$1" extra_exclude_re="$2"
    shift 2
    local exclude_re='(^|/)__pycache__/|\.py[co]$|\.pyd$'
    if [[ -n "$extra_exclude_re" ]]; then
        exclude_re="$exclude_re|$extra_exclude_re"
    fi
    local untracked modified staged probe_rc=0
    untracked="$(git -C "$workdir" ls-files --others --exclude-standard \
        -- "$@" 2>/dev/null)" || probe_rc=1
    modified="$(git -C "$workdir" ls-files --modified -- "$@" 2>/dev/null)" || probe_rc=1
    staged="$(git -C "$workdir" diff --cached --name-only --no-renames \
        -- "$@" 2>/dev/null)" || probe_rc=1
    # A partial list is not a smaller dirty set: print nothing on failure.
    (( probe_rc == 0 )) || return 2
    printf '%s\n%s\n%s\n' "$untracked" "$modified" "$staged" \
        | sed '/^$/d' | sort -u | { grep -Ev "$exclude_re" || true; }
}

# Print stdin lines NOT present in the newline-joined set $1 (exact match).
_install_subtract() {
    if [[ -z "$1" ]]; then cat; return 0; fi
    grep -Fxv -f <(printf '%s\n' "$1") || true
}

# Print stdin lines present in the newline-joined set $1 (exact match).
_install_intersect() {
    if [[ -z "$1" ]]; then cat >/dev/null; return 0; fi
    grep -Fx -f <(printf '%s\n' "$1") || true
}

# Refuse a framework commit whose pre-install dirty state could not be read:
# the upgrade's own files left uncommitted are recoverable by hand, someone
# else's work committed under the upgrade message is not (t2116). The recovery
# is a path-scoped manual commit, not a re-run: a re-run's snapshot would find
# the files this run left dirty and leave them alone as pre-existing changes,
# and a commit without paths would sweep anything else already staged (t2120).
_install_refuse_unverified_commit() {
    local what="$1" recovery="$2"
    warn "Could not read the uncommitted state of $what — the framework update was NOT committed."
    warn "Committing without it could sweep someone else's uncommitted work into the upgrade commit."
    info "Once git works again, review 'git status' and commit only the framework files you reviewed, naming each path: $recovery — a commit without paths also commits anything else already staged."
}

# Snapshot the pre-install dirty framework-path state. main() MUST call this
# before extraction — nothing earlier writes into INSTALL_DIR. Each baseline is
# gated only on its own committer's eligibility, so neither commit can ever act
# with a baseline that was skipped.
#
# Unverified: a failed git probe yields no list, and an empty baseline would
# read as "nothing was dirty" — the commit-all sweep. Instead it sets that
# baseline's UNVERIFIED flag and its committer refuses (t2116). The data and
# main flags are independent, like the baselines themselves.
snapshot_pre_install_dirty() {
    local data_dir="$INSTALL_DIR/.aitask-data" p
    AIT_INSTALL_BASELINE_ARMED=1
    AIT_INSTALL_BASELINE_UNVERIFIED=0
    AIT_INSTALL_DATA_BASELINE_UNVERIFIED=0
    AIT_INSTALL_DIRTY_BASELINE=""
    AIT_INSTALL_DATA_DIRTY_BASELINE=""

    # The data worktree's own predicate (_install_data_worktree_present), split
    # so that a present .git which git cannot read is an unverified baseline,
    # not a missing one.
    if [[ -d "$data_dir/.git" || -f "$data_dir/.git" ]]; then
        if ! _install_is_worktree "$data_dir"; then
            AIT_INSTALL_DATA_BASELINE_UNVERIFIED=1
        else
            local data_paths=() data_rc=0
            while IFS= read -r p; do data_paths+=("$p"); done \
                < <(_install_data_framework_paths "$data_dir" 1)
            # unverified: flag the data baseline; commit_installed_data_files refuses.
            AIT_INSTALL_DATA_DIRTY_BASELINE="$(_install_list_changes "$data_dir" "" \
                "${data_paths[@]}")" || data_rc=$?
            (( data_rc == 0 )) || AIT_INSTALL_DATA_BASELINE_UNVERIFIED=1
        fi
    fi

    # A failed rev-parse is unverified whether or not $INSTALL_DIR/.git exists:
    # --dir may name a subdirectory of an ancestor repository, which has no
    # local .git. With truly no repository the flag is inert —
    # commit_installed_files bails on its own repo check before reading it.
    if ! _install_is_worktree "$INSTALL_DIR"; then
        AIT_INSTALL_BASELINE_UNVERIFIED=1
        return 0
    fi

    # Framework not tracked → no main baseline; commit_installed_files skips too.
    local vrc=0
    # unverified: flag the main baseline; commit_installed_files refuses.
    _install_version_tracked "$INSTALL_DIR" || vrc=$?
    case $vrc in
        0) ;;
        1) return 0 ;;
        *) AIT_INSTALL_BASELINE_UNVERIFIED=1; return 0 ;;
    esac

    local fw_paths=() main_rc=0
    while IFS= read -r p; do fw_paths+=("$p"); done \
        < <(_install_framework_paths "$INSTALL_DIR" 1)
    # unverified: flag the main baseline; commit_installed_files refuses.
    AIT_INSTALL_DIRTY_BASELINE="$(_install_list_changes "$INSTALL_DIR" \
        "$(_install_data_branch_exclude_re "$INSTALL_DIR")" "${fw_paths[@]}")" || main_rc=$?
    (( main_rc == 0 )) || AIT_INSTALL_BASELINE_UNVERIFIED=1
    return 0
}

# Print up to 20 of the arguments, indented, plus an overflow line. Positional
# indexing, not `printf | head` (SIGPIPE under pipefail + errexit) and not a
# nameref (`local -n` needs bash 4.3; curl|bash may run macOS's bash 3.2).
_install_print_list() {
    local _n=0 _item
    for _item in "$@"; do
        _n=$((_n + 1))
        [[ $_n -le 20 ]] && printf '    %s\n' "$_item"
    done
    if [[ $# -gt 20 ]]; then
        info "    ... and $(($# - 20)) more"
    fi
    return 0
}

# --- Commit installed files to git (safety net) ---
# Runs after extraction — commits framework files if this project has opted
# into tracking them (heuristic: .aitask-scripts/VERSION is git-tracked).
# No interactive prompt (stdin may not be a terminal when piped).
# Non-fatal: warns on failure instead of aborting. Never pushes.
#
# Commits only (changed − AIT_INSTALL_DIRTY_BASELINE): framework files that
# were already dirty before extraction are reported and left alone. Unarmed
# (snapshot_pre_install_dirty never ran) means an empty baseline — acceptable
# only for direct test invocation.
#
# Branch-mode safety: discovers changed files via `git ls-files`, then stages
# them individually. `git ls-files` silently skips paths beyond symbolic links,
# so symlinked `aitasks/metadata/` (data-branch worktree) drops out cleanly
# instead of triggering `fatal: pathspec ... is beyond a symbolic link` and
# aborting the entire `git add`. Data-worktree changes are committed by
# commit_installed_data_files() below.
commit_installed_files() {
    if ! _install_is_worktree "$INSTALL_DIR"; then
        return
    fi

    # Only auto-commit if the previous framework version was committed. We use
    # .aitask-scripts/VERSION as the sentinel: projects that want framework
    # files tracked commit it, projects that don't leave it untracked.
    local vrc=0
    # unverified: refuse — skipping is safe, but "not git-tracked" would be false.
    _install_version_tracked "$INSTALL_DIR" || vrc=$?
    case $vrc in
        0) ;;
        1) info "  .aitask-scripts/VERSION is not git-tracked — skipping auto-commit of framework update."
           return ;;
        *) _install_refuse_unverified_commit "the framework paths" "'git add -- <path>...' / 'git commit -- <path>...'"
           return ;;
    esac

    if [[ "$AIT_INSTALL_BASELINE_ARMED" != "1" ]]; then
        warn "commit_installed_files: baseline not armed — committing without pre-install dirty protection" >&2
    fi
    if [[ "$AIT_INSTALL_BASELINE_UNVERIFIED" == "1" ]]; then
        _install_refuse_unverified_commit "the framework paths" "'git add -- <path>...' / 'git commit -- <path>...'"
        return
    fi

    local version="unknown"
    if [[ -f "$INSTALL_DIR/.aitask-scripts/VERSION" ]]; then
        version="$(cat "$INSTALL_DIR/.aitask-scripts/VERSION")"
    fi

    local paths_to_add=() p
    while IFS= read -r p; do paths_to_add+=("$p"); done \
        < <(_install_framework_paths "$INSTALL_DIR")

    if [[ ${#paths_to_add[@]} -eq 0 ]]; then
        return
    fi

    local data_branch_re all_changes list_rc=0
    data_branch_re="$(_install_data_branch_exclude_re "$INSTALL_DIR")"
    # unverified: refuse — an empty list would report a false "already committed".
    all_changes="$(_install_list_changes "$INSTALL_DIR" "$data_branch_re" \
        "${paths_to_add[@]}")" || list_rc=$?
    if (( list_rc != 0 )); then
        _install_refuse_unverified_commit "the framework paths" "'git add -- <path>...' / 'git commit -- <path>...'"
        return
    fi

    local changed_files=() excluded_files=() changed_file
    while IFS= read -r changed_file; do
        [[ -n "$changed_file" ]] || continue
        changed_files+=("$changed_file")
    done < <(printf '%s\n' "$all_changes" | _install_subtract "$AIT_INSTALL_DIRTY_BASELINE")
    while IFS= read -r changed_file; do
        [[ -n "$changed_file" ]] || continue
        excluded_files+=("$changed_file")
    done < <(printf '%s\n' "$all_changes" | _install_intersect "$AIT_INSTALL_DIRTY_BASELINE")

    if [[ ${#excluded_files[@]} -gt 0 ]]; then
        warn "Pre-existing uncommitted changes under framework paths — left alone (not committed by the upgrade):"
        _install_print_list "${excluded_files[@]}"
        info "Review and commit them yourself when ready."
    fi

    # One-time cleanup: drop any __pycache__ paths that were tracked before
    # the scoped .aitask-scripts/.gitignore landed.
    local cached_pycache
    cached_pycache="$(git -C "$INSTALL_DIR" ls-files '.aitask-scripts/*/__pycache__/*' 2>/dev/null || true)"

    if [[ ${#changed_files[@]} -eq 0 && -z "$cached_pycache" ]]; then
        if [[ ${#excluded_files[@]} -eq 0 ]]; then
            success "Framework files already committed to git (v${version})"
        else
            info "No other framework changes to commit (v${version})"
        fi
        return
    fi

    # Pathspec for the finalize diff-guard and commit: the framework changes
    # PLUS any stale __pycache__ paths we are about to `git rm --cached` (those
    # are filtered out of changed_files but their staged deletion must still be
    # committed). Path-scoping both the guard and the commit is what stops a
    # bare `git commit` from sweeping a foreign pre-staged index on a dirty
    # curl|bash upgrade (mirrors commit_framework_files in aitask_setup.sh).
    local commit_paths=(${changed_files[@]+"${changed_files[@]}"})

    info "Committing framework update (v${version}) to git (${#changed_files[@]} files)..."

    if [[ -n "$cached_pycache" ]]; then
        local pycache_path
        while IFS= read -r pycache_path; do
            [[ -n "$pycache_path" ]] || continue
            commit_paths+=("$pycache_path")
        done <<< "$cached_pycache"
        # shellcheck disable=SC2086 # intentional word splitting on newline-delimited list
        (cd "$INSTALL_DIR" && echo "$cached_pycache" | xargs git rm --cached --quiet 2>/dev/null) || true
    fi

    if [[ ${#changed_files[@]} -gt 0 ]]; then
        local add_output
        if ! add_output=$(cd "$INSTALL_DIR" && git add -- "${changed_files[@]}" 2>&1); then
            warn "git add failed:"
            printf '%s\n' "$add_output" | awk '{print "    " $0}'
            warn "Framework files NOT committed. Review 'git status' and commit only the framework files you reviewed, naming each path: 'git add -- <path>...' / 'git commit -- <path>...' — re-running 'ait setup' would leave them alone as pre-existing changes."
            return
        fi
    fi

    if [[ ${#commit_paths[@]} -gt 0 ]] && \
       ! (cd "$INSTALL_DIR" && git diff --cached --quiet -- "${commit_paths[@]}" 2>/dev/null); then
        local commit_output
        if ! commit_output=$(cd "$INSTALL_DIR" && \
            git commit -m "ait: Update aitasks framework to v${version}" -- "${commit_paths[@]}" 2>&1); then
            warn "git commit failed:"
            printf '%s\n' "$commit_output" | awk '{print "    " $0}'
            warn "Framework files staged but NOT committed. Commit them yourself naming each path — 'git commit -- <path>...'; a commit without paths also commits anything else already staged."
            return
        fi
        success "Framework update v${version} committed to git"
    fi

    # Post-commit verification: anything still untracked under the framework
    # paths indicates a gitignore rule, pathspec quirk, or a new file produced
    # between the list and the commit. Apply the same data-branch filter as
    # above — those files belong on the aitask-data branch, not master — and
    # subtract the baseline: a pre-existing untracked file is deliberately left
    # behind, not a commit failure.
    local post_exclude_re='(^|/)__pycache__/|\.py[co]$|\.pyd$'
    if [[ -n "$data_branch_re" ]]; then
        post_exclude_re="$post_exclude_re|$data_branch_re"
    fi
    local still_untracked
    still_untracked="$(git -C "$INSTALL_DIR" ls-files --others --exclude-standard \
        -- "${paths_to_add[@]}" 2>/dev/null | { grep -Ev "$post_exclude_re" || true; } \
        | _install_subtract "$AIT_INSTALL_DIRTY_BASELINE")" || true
    if [[ -n "$still_untracked" ]]; then
        warn "Some framework files remain untracked after commit:"
        printf '%s\n' "$still_untracked" | awk 'NR<=20 {print "    " $0}'
        warn "Run 'git status' to investigate, then commit only the listed files you intend, naming each path: 'git add -- <path>...' / 'git commit -- <path>...'."
    fi
}

# --- Commit data-branch framework files (branch-mode only) ---
# When the project uses a separate `aitask-data` branch (worktree at
# .aitask-data/), framework metadata that lives there — aitasks/metadata/ and
# (when symlinked) aireviewguides/ — is written through symlinks during install
# but never reaches the master worktree's index. Commit those changes inside
# the data worktree so install.sh and `ait setup` are symmetric.
#
# Commits only (changed − AIT_INSTALL_DATA_DIRTY_BASELINE): concurrent
# sessions routinely have in-progress work in the data worktree, and it must
# never ride into the framework-data commit.
#
# Inline data-worktree detection (install.sh runs stand-alone via curl|bash so
# it cannot source .aitask-scripts/lib/task_utils.sh). Mirrors
# _ait_detect_data_worktree() in that file.
commit_installed_data_files() {
    local data_dir="$INSTALL_DIR/.aitask-data"

    # Legacy mode (no separate data worktree) — nothing to do.
    if ! _install_data_worktree_present "$data_dir"; then
        return
    fi

    if [[ "$AIT_INSTALL_BASELINE_ARMED" != "1" ]]; then
        warn "commit_installed_data_files: baseline not armed — committing without pre-install dirty protection" >&2
    fi
    if [[ "$AIT_INSTALL_DATA_BASELINE_UNVERIFIED" == "1" ]]; then
        _install_refuse_unverified_commit "the aitask-data framework paths" \
            "'git -C .aitask-data add -- <path>...' / 'git -C .aitask-data commit -- <path>...'"
        return
    fi

    local version="unknown"
    if [[ -f "$INSTALL_DIR/.aitask-scripts/VERSION" ]]; then
        version="$(cat "$INSTALL_DIR/.aitask-scripts/VERSION")"
    fi

    local data_paths=() p
    while IFS= read -r p; do data_paths+=("$p"); done \
        < <(_install_data_framework_paths "$data_dir")

    if [[ ${#data_paths[@]} -eq 0 ]]; then
        return
    fi

    local all_changes list_rc=0
    # unverified: refuse — an empty list would hide the update behind a silent no-op.
    all_changes="$(_install_list_changes "$data_dir" "" "${data_paths[@]}")" || list_rc=$?
    if (( list_rc != 0 )); then
        _install_refuse_unverified_commit "the aitask-data framework paths" \
            "'git -C .aitask-data add -- <path>...' / 'git -C .aitask-data commit -- <path>...'"
        return
    fi

    local changed_files=() excluded_files=() changed_file
    while IFS= read -r changed_file; do
        [[ -n "$changed_file" ]] || continue
        changed_files+=("$changed_file")
    done < <(printf '%s\n' "$all_changes" | _install_subtract "$AIT_INSTALL_DATA_DIRTY_BASELINE")
    while IFS= read -r changed_file; do
        [[ -n "$changed_file" ]] || continue
        excluded_files+=("$changed_file")
    done < <(printf '%s\n' "$all_changes" | _install_intersect "$AIT_INSTALL_DATA_DIRTY_BASELINE")

    if [[ ${#excluded_files[@]} -gt 0 ]]; then
        warn "Pre-existing uncommitted changes on the aitask-data branch — left alone (not committed by the upgrade):"
        _install_print_list "${excluded_files[@]}"
        info "Review and commit them yourself when ready."
    fi

    if [[ ${#changed_files[@]} -eq 0 ]]; then
        return
    fi

    info "Committing framework data update (v${version}) to aitask-data branch (${#changed_files[@]} files)..."

    local add_output
    if ! add_output=$(git -C "$data_dir" add -- "${changed_files[@]}" 2>&1); then
        warn "git add failed (data branch):"
        printf '%s\n' "$add_output" | awk '{print "    " $0}'
        warn "Framework data files NOT committed."
        return
    fi

    # Path-scoped diff guard and commit — a bare `git commit` would sweep a
    # foreign pre-staged index on the data worktree (mirrors
    # commit_framework_data_files in aitask_setup.sh).
    if ! git -C "$data_dir" diff --cached --quiet -- "${changed_files[@]}" 2>/dev/null; then
        local commit_output
        if ! commit_output=$(git -C "$data_dir" \
            commit -m "ait: Update aitasks framework data to v${version}" -- "${changed_files[@]}" 2>&1); then
            warn "git commit failed (data branch):"
            printf '%s\n' "$commit_output" | awk '{print "    " $0}'
            return
        fi
        success "Framework data update v${version} committed to aitask-data branch"
    fi
}

# --- Offer newer models for superseded code-agent defaults (t1910) ---
# merge_seed keeps every existing codeagent_config.json default, so a model the
# framework has since replaced would otherwise stay the default forever. The
# helper offers, per superseded model and config layer, to switch the ops that
# use it (.aitask-scripts/lib/model_supersessions.json records what replaced
# what); custom, non-superseded choices are never touched.
#
# - Runs AFTER commit_installed_files/commit_installed_data_files: the framework
#   update is already committed, so an interrupted prompt cannot strand it, and
#   an accepted switch gets its own path-scoped commit.
# - Interactive only on a tty. Otherwise it only reports, with stdin closed:
#   under `curl | bash` stdin IS this script, and nothing may read from it.
# - resolve_python comes from aitask_setup.sh, which main() sources before this
#   runs (the venv interpreter first, system python3 last). Never fatal.
# - A fresh install's config is the seed, which is never superseded: skip it.
check_superseded_model_defaults() {
    [[ "$EXISTING_INSTALL" == true ]] || return 0
    local helper="$INSTALL_DIR/.aitask-scripts/aitask_model_supersession.py"
    [[ -f "$helper" ]] || return 0
    local rerun="run 'ait codeagent check-superseded' after 'ait setup' to review superseded model defaults"
    if ! declare -F resolve_python >/dev/null; then
        warn "  Skipped the superseded-model check (Python resolver not loaded) — $rerun."
        return 0
    fi
    local py
    py="$(resolve_python)"
    if [[ -z "$py" ]]; then
        warn "  Skipped the superseded-model check (no Python found) — $rerun."
        return 0
    fi

    # Ctrl-C at a prompt must stop the prompt, not the installer.
    local prev_int_trap
    prev_int_trap="$(trap -p INT)"
    trap ':' INT
    local rc=0
    if [[ -t 0 ]]; then
        "$py" "$helper" check --root "$INSTALL_DIR" --interactive || rc=$?
    else
        "$py" "$helper" check --root "$INSTALL_DIR" </dev/null || rc=$?
    fi
    if [[ -n "$prev_int_trap" ]]; then
        eval "$prev_int_trap"
    else
        trap - INT
    fi
    if [[ "$rc" -ne 0 ]]; then
        warn "  The superseded-model check did not complete (exit $rc) — $rerun."
    fi
    return 0
}

# Remove the framework-release packaging/ tooling left behind after the shim is
# consumed. The release tarball bundles packaging/ only so install_global_shim
# can copy packaging/shim/ait; nothing under it has a runtime role in a consumer
# project. Mirrors the `rm -rf "$INSTALL_DIR/seed"` cleanup.
#
# Blast-radius guard: the aitasks framework repo IS an aitasks project and tracks
# packaging/ as source. `ait upgrade` runs install.sh over that working tree, so
# an unguarded rm would delete the framework's own build tooling. Only remove an
# UNTRACKED packaging/ (tracked => this is the framework source repo; leave it).
cleanup_packaging_leftover() {
    local dir="$1"
    [[ -d "$dir/packaging" ]] || return 0
    if git -C "$dir" ls-files --error-unmatch packaging >/dev/null 2>&1; then
        info "packaging/ is git-tracked (framework source repo) — leaving it in place."
        return 0
    fi
    rm -rf "$dir/packaging"
}

# --- Main ---
main() {
    echo ""
    info "aitask framework installer"
    echo ""

    check_prerequisites
    check_existing_install
    confirm_install

    # Temp directory with cleanup
    local tmpdir
    tmpdir="$(mktemp -d)"
    # shellcheck disable=SC2064  # Intentional: expand $tmpdir now, not at signal time
    trap "rm -rf '$tmpdir'" EXIT

    local tarball_path="$tmpdir/aitasks.tar.gz"

    download_tarball "$tarball_path"

    # Show changelog and confirm (upgrade path only)
    show_upgrade_changelog "$tarball_path" "$INSTALL_DIR"

    # The release tarball carries a root CHANGELOG.md purely so
    # show_upgrade_changelog can display the framework changelog before an
    # upgrade — and that function extracts its own copy into a private temp
    # dir, never reading INSTALL_DIR. A consumer project owns the root
    # CHANGELOG.md at that path (`ait changelog` writes it), so the extraction
    # must not clobber it and the cleanup must not delete it (t1772).
    local preserve_dir="$tmpdir/preserve"
    mkdir -p "$preserve_dir"

    # A root VERSION is a pre-v0.3.0 framework artefact ONLY when this is an
    # existing install whose version has not yet migrated to
    # .aitask-scripts/VERSION. Probed here because extraction creates that
    # file. Anything else at that path belongs to the project.
    local legacy_root_version=false
    if [[ -f "$INSTALL_DIR/VERSION" && -d "$INSTALL_DIR/.aitask-scripts" \
          && ! -f "$INSTALL_DIR/.aitask-scripts/VERSION" ]]; then
        legacy_root_version=true
    fi

    local f
    for f in CHANGELOG.md VERSION; do
        if [[ -f "$INSTALL_DIR/$f" ]]; then
            cp -p "$INSTALL_DIR/$f" "$preserve_dir/$f"
        fi
    done

    # Baseline of the user's uncommitted framework-path work, taken before the
    # first write into INSTALL_DIR. commit_installed_files and
    # commit_installed_data_files commit only what changed beyond it.
    snapshot_pre_install_dirty

    info "Extracting to $INSTALL_DIR..."
    tar -xzf "$tarball_path" -C "$INSTALL_DIR"

    # Put back what the project owned; remove what only the tarball supplied.
    for f in CHANGELOG.md VERSION; do
        if [[ -f "$preserve_dir/$f" ]]; then
            cp -p "$preserve_dir/$f" "$INSTALL_DIR/$f"
        else
            rm -f "$INSTALL_DIR/$f"
        fi
    done
    if [[ "$legacy_root_version" == true ]]; then
        rm -f "$INSTALL_DIR/VERSION"     # migrated to .aitask-scripts/VERSION
    fi

    info "Installing Claude Code skills..."
    install_skills

    info "Installing .aitask-scripts/.gitignore..."
    install_seed_aitask_scripts_gitignore

    info "Creating data directories..."
    create_data_dirs

    info "Installing execution profiles..."
    install_seed_profiles

    info "Installing seed task types..."
    install_seed_task_types

    info "Installing project config..."
    install_seed_project_config

    info "Installing gate registry..."
    install_seed_gates_registry

    info "Installing chatlink gateway config..."
    install_seed_chatlink_config

    info "Installing crew runner config..."
    install_seed_crew_runner_config

    info "Installing starter tmux.conf template..."
    install_seed_tmux_conf

    info "Installing review types..."
    install_seed_reviewtypes

    info "Installing review labels..."
    install_seed_reviewlabels

    info "Installing review environments..."
    install_seed_reviewenvironments

    info "Installing review guides..."
    install_seed_reviewguides

    info "Installing code areas map..."
    install_seed_code_areas

    info "Installing doc-update guide..."
    install_seed_doc_update_guide

    info "Installing code agent configuration..."
    install_seed_codeagent_config

    info "Installing model configuration files..."
    install_seed_models

    info "Storing Claude Code permissions seed..."
    install_seed_claude_settings

    info "Storing Claude Code session hook seed..."
    install_seed_claude_hooks

    info "Storing Codex CLI staging files..."
    install_codex_staging

    info "Storing Codex CLI config seeds..."
    install_seed_codex_config

    info "Storing OpenCode staging files..."
    install_opencode_staging

    info "Storing OpenCode config seeds..."
    install_seed_opencode_config

    info "Pruning retired skill surfaces..."
    prune_retired_skills

    info "Pruning retired framework scripts..."
    prune_retired_scripts

    # Clean up seed directory after all seed installers have run
    rm -rf "$INSTALL_DIR/seed"

    info "Setting permissions..."
    set_permissions

    info "Installing global shim..."
    # Source the setup script (without running main) to reuse install_global_shim()
    # shellcheck source=.aitask-scripts/aitask_setup.sh
    source "$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only
    install_global_shim

    # The test map engine for this framework version. Never fatal: the function
    # reports every outcome as a TESTMAP_BINARY: line. A --local-tarball install
    # is an offline one, so only the network tier is switched off there.
    info "Installing test map engine..."
    if [[ -n "$LOCAL_TARBALL" ]]; then
        AIT_TESTMAP_FETCH=0 install_engine_binary ${ENGINE_ARGS[@]+"${ENGINE_ARGS[@]}"} || true
    else
        install_engine_binary ${ENGINE_ARGS[@]+"${ENGINE_ARGS[@]}"} || true
    fi

    # Drop the framework-release packaging/ tooling now that the shim is copied.
    cleanup_packaging_leftover "$INSTALL_DIR"

    # Upgrade never runs setup, so this is the only route by which an
    # upgraded-only project gets the t1711 symlink-safe data entries. It
    # commits nothing itself: it MUST run after snapshot_pre_install_dirty and
    # immediately before commit_installed_files, which commits the rewritten
    # .gitignore only when it was clean before the upgrade. The declare -F
    # guard: `--version` can pair this installer with an older tarball whose
    # aitask_setup.sh predates the function, and under errexit an unknown
    # command would abort the install after extraction, before the commit.
    if [[ "$EXISTING_INSTALL" == true ]] && \
       declare -F setup_data_gitignore_symlink_safe >/dev/null; then
        info "Checking .gitignore data entries..."
        setup_data_gitignore_symlink_safe
    fi

    commit_installed_files
    commit_installed_data_files

    if [[ "$EXISTING_INSTALL" == true ]]; then
        info "Checking for superseded code-agent model defaults..."
        check_superseded_model_defaults
    fi

    # The upgrade path never migrates the legacy per-user root (t1939): that is
    # a layout repair, which `ait setup` owns. Surface the read-only hint
    # instead. The declare -F guard: `--version` can pair this installer with
    # an older aitask_setup.sh that predates the function.
    if declare -F report_home_legacy >/dev/null; then
        report_home_legacy
    fi

    # Upgrade never repairs Python deps (setup owns pip); surface venv spec drift
    # read-only so an upgraded-only machine learns it needs `ait setup` (t2133).
    # Same declare -F guard as above, for the same older-tarball reason.
    if declare -F report_venv_dep_drift >/dev/null; then
        report_venv_dep_drift
    fi

    report_claude_session_hook

    echo ""
    echo "=== aitasks installed successfully ==="
    echo ""
    if [[ ":$PATH:" == *":$HOME/.local/bin:"* ]]; then
        info "Next step: run 'ait setup' to install dependencies and configure Claude Code permissions."
    else
        info "Next step: restart your shell (or run 'source ~/.zshrc'), then run 'ait setup'."
        info "Or run immediately with: ./ait setup"
    fi
    echo ""
    echo "Quick start:"
    echo "  ait setup      # Install dependencies and configure permissions"
    echo "  ait create     # Create a new task"
    echo "  ait ls -v 15   # List top 15 tasks"
    echo "  ait board      # Open task board"
    echo ""
    echo "Claude Code skills installed to .claude/skills/"
    echo ""
}

# When sourced with --source-only (tests), return before running the installer.
# Outside a sourced context `return` fails harmlessly (|| true).
[[ "${1:-}" == "--source-only" ]] && return 0 2>/dev/null || true

main "$@"
