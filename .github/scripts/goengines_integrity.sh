#!/usr/bin/env bash
# goengines_integrity.sh — the public goengines/ checks keyed on one signal:
# whether goengines/EXPORT.txt exists (t2138).
#
#   .github/scripts/goengines_integrity.sh <mode|check|drift> [--dir <goengines dir>]
#
# Without EXPORT.txt (legacy mode) goengines/ is developed in this repository
# and the go test / preflight / bench pipeline is the required validation;
# check and drift report that and do nothing. With EXPORT.txt (export mode)
# the tree is a generated export from the private aitasks_go repository: its
# tests ran there at the exported commit, and this script is the public
# validation. It lives outside goengines/ because after the cutover that tree
# holds only exported files plus README.md and .gitignore.
#
# | verb  | stdout                                                         | exit  |
# |-------|----------------------------------------------------------------|-------|
# | mode  | MODE:legacy / MODE:export (and mode=<m> appended to             | 0 / 1 |
# |       | $GITHUB_OUTPUT when set); MODE_ERROR:<why> for an EXPORT.txt    |       |
# |       | that is a symlink or not a regular file                         |       |
# | check | legacy: MODE:legacy, INTEGRITY_SKIPPED:<why>; export: MODE:export, | 0 / 1 |
# |       | one INTEGRITY_FAIL:<check>:<detail> per failure, else INTEGRITY_OK |    |
# | drift | legacy: DRIFT_SKIPPED:legacy; export: DRIFT:modified|missing|unlisted:<path> | 0 |
# |       | lines, then DRIFT_NONE or DRIFT_FOUND:<n>; DRIFT_UNCHECKED:<why> |       |
# |       | when the record cannot be read (check owns that failure)         |       |
#
# drift never fails: a drifted file is an emergency public fix not yet
# returned to aitasks_go (goengines/README.md, "Emergency fixes"), and
# emergency fixes must ship. Under GITHUB_ACTIONS=true each entry is also an
# ::warning annotation. Exit 64 is a usage error.
#
# check, export mode, in order (every go command runs in a scratch copy, so
# the checkout is never modified):
#   record             EXPORT.txt is a readable, valid format-1 record
#   matrix             the release matrix can be read from build.sh
#   copy               the tree can be copied into the scratch directory
#   gofmt              gofmt -l prints nothing
#   private-deps       no github.com/beyondeye/aitasks_go module in go.mod
#                      (require / replace), go.sum, go list -m all, or any
#                      package's import list on any release target; no local
#                      replace outside the tree (absolute or with a ..
#                      segment: a lexical, conservative rule). Structural
#                      checks only, so provenance labels (the generated
#                      header, EXPORT.txt, SourceCommit) pass. The checks
#                      stop here when any of the above failed: the ones below
#                      reach the module proxy and would only mask the reason.
#   independent-build  with no access to anything private: go mod tidy -diff
#                      clean, go build ./... on every release target, go vet
#   closure            on every release target, the non-std dependency
#                      closure of cmd/ait-testmap (and cmd/ait-monitord when
#                      present) stays inside the main module and the testmap
#                      allowlist, with no main-module tui/ package
#
# Every go command runs through run_go, under one independent environment
# (no go env file, no inherited GOFLAGS such as -modfile, GOWORK=off, no
# GOPRIVATE / GONOPROXY / GONOSUMDB, the public proxy only), so no inherited
# setting reaches one check and not another.
#
# Per-target checks run with the release build settings (CGO_ENABLED=0,
# GOOS/GOARCH from build.sh's MATRIX, no build tags): go list evaluates build
# constraints for one platform only, so a _darwin.go file is invisible to a
# check run on Linux.
set -euo pipefail

usage() {
    echo "USAGE:goengines_integrity.sh <mode|check|drift> [--dir <goengines dir>]" >&2
    exit 64
}

[[ $# -ge 1 ]] || usage
verb="$1"
shift
case "$verb" in mode|check|drift) ;; *) usage ;; esac
dir=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --dir) [[ $# -ge 2 && -n "$2" ]] || usage; dir="$2"; shift 2 ;;
        *) usage ;;
    esac
done
[[ -n "$dir" ]] || dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/goengines"
if [[ ! -d "$dir" ]]; then
    echo "MODE_ERROR:no goengines directory at $dir"
    exit 1
fi
dir="$(cd "$dir" && pwd)"

readonly PRIVATE_RE='^github\.com/beyondeye/aitasks_go(/|$)'
# The ait-testmap (and ait-monitord) dependency allowlist. It restates
# allowedDeps in goengines/guards_test.go for a module that may also hold
# ait-tui; tests/test_goengines_export_integrity.sh pins the two lists equal
# while that file exists.
readonly CLOSURE_ALLOWED_MODULES=(
    gopkg.in/yaml.v3
    github.com/bmatcuk/doublestar/v4
    golang.org/x/sync
)
# The only files under goengines/ an export never writes.
readonly PUBLIC_MAINTAINED=(README.md .gitignore)
# No access to anything private: the module proxy only, no credential prompt.
# GOENV=off drops the user's go env file: go treats an empty variable as unset
# and falls back to that file, so GOFLAGS= / GOPRIVATE= alone would not clear
# a `go env -w GOFLAGS=-modfile=…`. GOFLAGS is cleared before any per-call
# value (env applies assignments in order, the last one wins).
readonly INDEPENDENT_ENV=(GOENV=off GOFLAGS= GOWORK=off GOPRIVATE= GONOPROXY= GONOSUMDB= GOPROXY=https://proxy.golang.org GIT_TERMINAL_PROMPT=0)

MODE=""
detect_mode() {
    local rec="$dir/EXPORT.txt"
    if [[ -L "$rec" ]]; then
        echo "MODE_ERROR:EXPORT.txt is a symlink"
        return 1
    fi
    if [[ -e "$rec" ]]; then
        if [[ ! -f "$rec" ]]; then
            echo "MODE_ERROR:EXPORT.txt is not a regular file"
            return 1
        fi
        MODE="export"
    else
        MODE="legacy"
    fi
}

sha256_of() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum -- "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 -- "$1" | awk '{print $1}'
    else
        echo "neither sha256sum nor shasum is available" >&2
        return 1
    fi
}

public_maintained() {
    local m
    for m in "${PUBLIC_MAINTAINED[@]}"; do
        [[ "$1" == "$m" ]] && return 0
    done
    return 1
}

# A record path: the shell-safe subset, relative, canonical (no empty, . or ..
# segment, no trailing slash).
safe_path() {
    [[ "$1" =~ ^[A-Za-z0-9._/@+-]+$ ]] || return 1
    case "/$1/" in
        //*|*//*|*/./*|*/../*) return 1 ;;
    esac
    return 0
}

# EXPORT.txt format 1: blank lines, # comments and `key: value` lines.
# format and source are required once; file is `<sha256> <path>`; unknown
# keys are tolerated so the exporter can add fields (format is the version
# gate). Sets REC_ERRORS, REC_PATHS, REC_HASHES and REC_SEEN (a newline-framed
# path list for lookups). An unreadable record is the error `cannot be read`,
# never an errexit exit: drift must stay non-blocking.
parse_record() {
    REC_ERRORS=() REC_PATHS=() REC_HASHES=()
    REC_SEEN=$'\n'
    local n=0 formats=0 sources=0 line key val h p
    # A failed redirection fails this one command, and inside an if condition
    # errexit does not apply.
    if ! parse_record_lines <"$dir/EXPORT.txt" 2>/dev/null; then
        REC_ERRORS+=("cannot be read")
        return 0
    fi
    [[ "$formats" -eq 1 ]] || REC_ERRORS+=("expected exactly one 'format:' line, found $formats")
    [[ "$sources" -eq 1 ]] || REC_ERRORS+=("expected exactly one 'source:' line, found $sources")
    return 0
}

# The line loop of parse_record, reading stdin; it sets parse_record's locals.
parse_record_lines() {
    while IFS= read -r line || [[ -n "$line" ]]; do
        n=$((n + 1))
        if [[ "$line" == *[[:cntrl:]]* ]]; then
            REC_ERRORS+=("line $n: control character")
            continue
        fi
        [[ -z "$line" || "$line" == \#* ]] && continue
        if [[ ! "$line" =~ ^([a-z][a-z0-9-]*):\ (.*)$ ]]; then
            REC_ERRORS+=("line $n: not a 'key: value' line")
            continue
        fi
        key="${BASH_REMATCH[1]}"
        val="${BASH_REMATCH[2]}"
        case "$key" in
            format)
                formats=$((formats + 1))
                [[ "$val" == 1 ]] || REC_ERRORS+=("line $n: unsupported format '$val' (this checker reads format 1)")
                ;;
            source)
                sources=$((sources + 1))
                [[ "$val" =~ ^beyondeye/aitasks_go@([0-9a-f]{40}|[0-9a-f]{64})$ ]] ||
                    REC_ERRORS+=("line $n: malformed source '$val'")
                ;;
            file)
                if [[ ! "$val" =~ ^([0-9a-f]{64})\ (.+)$ ]]; then
                    REC_ERRORS+=("line $n: a file line is '<64 hex sha256> <path>'")
                    continue
                fi
                h="${BASH_REMATCH[1]}"
                p="${BASH_REMATCH[2]}"
                if ! safe_path "$p"; then
                    REC_ERRORS+=("line $n: unsafe path '$p'")
                elif [[ "$p" == EXPORT.txt ]] || public_maintained "$p"; then
                    REC_ERRORS+=("line $n: '$p' is never part of an export")
                elif [[ "$REC_SEEN" == *$'\n'"$p"$'\n'* ]]; then
                    REC_ERRORS+=("line $n: duplicate path '$p'")
                else
                    REC_SEEN+="$p"$'\n'
                    REC_PATHS+=("$p")
                    REC_HASHES+=("$h")
                fi
                ;;
        esac
    done
    return 0
}

FAILED=0
fail() {
    echo "INTEGRITY_FAIL:$1:$2"
    FAILED=1
}

# The first line of a command's output, for a one-line failure detail.
first_line() {
    printf '%s\n' "$1" | sed -n '/./{p;q;}'
}

# go in the scratch copy, under the independent environment plus the given
# extra assignments. Every go command goes through here: an inherited GOWORK,
# GOFLAGS or proxy setting must never reach one check and not another.
work=""
run_go() {
    (cd "$work" && env "${INDEPENDENT_ENV[@]}" "$@")
}

check_matrix() {
    local line t
    TARGETS=()
    if ! line="$(sed -n 's/^readonly MATRIX=(\(.*\))[[:space:]]*$/\1/p' "$dir/build.sh" 2>/dev/null | head -n1)"; then
        fail matrix "cannot read build.sh"
        return 0
    fi
    for t in $line; do
        if [[ ! "$t" =~ ^[a-z0-9]+_[a-z0-9]+$ ]]; then
            fail matrix "build.sh MATRIX entry '$t' is not <os>_<arch>"
            return 0
        fi
        TARGETS+=("$t")
    done
    [[ ${#TARGETS[@]} -gt 0 ]] || fail matrix "cannot read the release matrix (readonly MATRIX=(…)) from build.sh"
    return 0
}

check_gofmt() {
    local gofmt out f
    if ! gofmt="$(run_go go env GOROOT)"; then
        fail gofmt "go env GOROOT failed"
        return 0
    fi
    gofmt="$gofmt/bin/gofmt"
    if ! out="$(cd "$work" && "$gofmt" -l . 2>&1)"; then
        fail gofmt "gofmt failed: $(first_line "$out")"
        return 0
    fi
    while IFS= read -r f; do
        [[ -n "$f" ]] && fail gofmt "needs gofmt: $f"
    done <<<"$out"
    return 0
}

check_private_deps() {
    local json out kind a b c t pkg imp
    if ! json="$(run_go go mod edit -json 2>&1)"; then
        fail private-deps "go mod edit -json failed: $(first_line "$json")"
        return 0
    fi
    if ! out="$(printf '%s' "$json" | python3 -c '
import json, sys
m = json.load(sys.stdin)
for r in m.get("Require") or []:
    print("require\t" + r["Path"])
for r in m.get("Replace") or []:
    print("replace\t%s\t%s\t%s" % (r["Old"]["Path"], r["New"]["Path"], r["New"].get("Version", "")))
' 2>&1)"; then
        fail private-deps "cannot parse go mod edit -json: $(first_line "$out")"
        return 0
    fi
    while IFS=$'\t' read -r kind a b c; do
        case "$kind" in
            require)
                [[ "$a" =~ $PRIVATE_RE ]] && fail private-deps "go.mod requires $a"
                ;;
            replace)
                [[ "$a" =~ $PRIVATE_RE ]] && fail private-deps "go.mod replaces $a"
                [[ "$b" =~ $PRIVATE_RE ]] && fail private-deps "go.mod replaces $a with $b"
                if [[ -z "$c" ]]; then
                    case "/$b/" in
                        //*) fail private-deps "go.mod replaces $a with the absolute path $b" ;;
                        */../*) fail private-deps "go.mod replaces $a with $b, outside the tree" ;;
                    esac
                fi
                ;;
        esac
    done <<<"$out"
    if [[ -f "$work/go.sum" ]]; then
        while IFS= read -r a; do
            [[ -n "$a" ]] && fail private-deps "go.sum lists $a"
        done < <(awk '{print $1}' "$work/go.sum" | grep -E "$PRIVATE_RE" | sort -u || true)
    fi
    # The listings below need a module graph: skip them when go.mod / go.sum
    # already failed (the fix is the same, and they would reach the proxy).
    [[ "$FAILED" -eq 0 ]] || return 0
    if ! out="$(run_go GOFLAGS=-mod=readonly go list -m all 2>&1)"; then
        fail private-deps "go list -m all failed: $(first_line "$out")"
        return 0
    fi
    while IFS= read -r a; do
        a="${a%% *}"
        [[ "$a" =~ $PRIVATE_RE ]] && fail private-deps "the module graph contains $a"
    done <<<"$out"
    for t in "${TARGETS[@]}"; do
        if ! out="$(run_go GOFLAGS=-mod=readonly CGO_ENABLED=0 GOOS="${t%%_*}" GOARCH="${t#*_}" \
            go list -e -deps -f '{{.ImportPath}}:{{range .Imports}} {{.}}{{end}}' ./... 2>&1)"; then
            fail private-deps "$t: go list -deps failed: $(first_line "$out")"
            continue
        fi
        while IFS= read -r a; do
            pkg="${a%%:*}"
            for imp in ${a#*:}; do
                [[ "$imp" =~ $PRIVATE_RE ]] && fail private-deps "$t: $pkg imports $imp"
            done
        done <<<"$out"
    done
    return 0
}

check_independent_build() {
    local out t
    if ! out="$(run_go GOFLAGS=-mod=mod go mod tidy -diff 2>&1)"; then
        fail independent-build "go mod tidy -diff is not clean: $(first_line "$out")"
    fi
    for t in "${TARGETS[@]}"; do
        if ! out="$(run_go GOFLAGS=-mod=mod CGO_ENABLED=0 GOOS="${t%%_*}" GOARCH="${t#*_}" go build ./... 2>&1)"; then
            fail independent-build "$t: go build ./... failed: $(first_line "$out")"
        fi
    done
    if ! out="$(run_go GOFLAGS=-mod=mod go vet ./... 2>&1)"; then
        fail independent-build "go vet ./... failed: $(first_line "$out")"
    fi
    return 0
}

allowed_module() {
    local m
    for m in "${CLOSURE_ALLOWED_MODULES[@]}"; do
        [[ "$1" == "$m" ]] && return 0
    done
    return 1
}

check_closure() {
    local main out t bin pkg mod
    if ! main="$(run_go GOFLAGS=-mod=mod go list -m 2>&1)"; then
        fail closure "cannot read the main module path: $(first_line "$main")"
        return 0
    fi
    local bins=(ait-testmap)
    [[ -d "$work/cmd/ait-testmap" ]] || { fail closure "cmd/ait-testmap is missing"; return 0; }
    [[ -d "$work/cmd/ait-monitord" ]] && bins+=(ait-monitord)
    for t in "${TARGETS[@]}"; do
        for bin in "${bins[@]}"; do
            if ! out="$(run_go GOFLAGS=-mod=mod CGO_ENABLED=0 GOOS="${t%%_*}" GOARCH="${t#*_}" \
                go list -deps -f '{{if not .Standard}}{{.ImportPath}}{{"\t"}}{{with .Module}}{{.Path}}{{end}}{{end}}' \
                "./cmd/$bin" 2>&1)"; then
                fail closure "$t:$bin: go list -deps failed: $(first_line "$out")"
                continue
            fi
            while IFS=$'\t' read -r pkg mod; do
                [[ -n "$pkg" ]] || continue
                if [[ -z "$mod" ]]; then
                    fail closure "$t:$bin:$pkg belongs to no module"
                elif [[ "$mod" == "$main" ]]; then
                    [[ "$pkg" == "$main/tui" || "$pkg" == "$main/tui/"* ]] &&
                        fail closure "$t:$bin:$pkg is a TUI package"
                elif ! allowed_module "$mod"; then
                    fail closure "$t:$bin:$pkg is from $mod, not on the allowlist (${CLOSURE_ALLOWED_MODULES[*]})"
                fi
            done <<<"$out"
        done
    done
    return 0
}

cmd_check() {
    detect_mode || exit 1
    echo "MODE:$MODE"
    if [[ "$MODE" == legacy ]]; then
        echo "INTEGRITY_SKIPPED:legacy mode — goengines/ is developed here; gofmt, vet, the preflight, go test and the bench are its validation"
        return 0
    fi
    local e
    parse_record
    for e in "${REC_ERRORS[@]+"${REC_ERRORS[@]}"}"; do
        fail record "EXPORT.txt $e"
    done
    TARGETS=()
    check_matrix
    # toolchain: the checks need go and python3 (go mod edit -json is parsed
    # with python3's json module).
    command -v go >/dev/null 2>&1 || { fail toolchain "go not found on PATH"; exit 1; }
    command -v python3 >/dev/null 2>&1 || { fail toolchain "python3 not found on PATH"; exit 1; }
    work="$(mktemp -d)"
    trap 'rm -rf "$work"' EXIT
    if ! cp -R "$dir/." "$work/" 2>/dev/null; then
        fail copy "cannot copy the tree into a scratch directory (an unreadable file?)"
        exit 1
    fi
    rm -rf "$work/dist" "$work/ait-testmap"
    check_gofmt
    check_private_deps
    if [[ "$FAILED" -ne 0 ]]; then
        exit 1
    fi
    check_independent_build
    check_closure
    [[ "$FAILED" -eq 0 ]] || exit 1
    echo "INTEGRITY_OK"
}

# Every file in the tree, relative to it and NUL-terminated (git C-quotes a
# name holding a quote or a backslash even with core.quotepath=off): git's view
# (tracked + untracked, ignored files excluded) inside a work tree, else find.
tree_files() {
    if git -C "$dir" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        (cd "$dir" && git ls-files -z -co --exclude-standard -- .)
    else
        (cd "$dir" && find . -type f -print0)
    fi
}

# A path for a line-protocol record: as is, or %q-quoted when it holds a
# control character (a newline would split the record).
show_path() {
    if [[ "$1" == *[[:cntrl:]]* ]]; then
        printf '%q' "$1"
    else
        printf '%s' "$1"
    fi
}

# GitHub workflow-command escaping: the message, then a property value.
gh_escape_data() {
    local v="${1//%/%25}"
    v="${v//$'\r'/%0D}"
    printf '%s' "${v//$'\n'/%0A}"
}
gh_escape_prop() {
    local v
    v="$(gh_escape_data "$1")"
    v="${v//:/%3A}"
    printf '%s' "${v//,/%2C}"
}

drift_entry() {
    local kind="$1" p="$2" why
    echo "DRIFT:$kind:$(show_path "$p")"
    if [[ "${GITHUB_ACTIONS:-}" == true ]]; then
        case "$kind" in
            modified) why="differs from the export record" ;;
            missing) why="is in the export record but absent" ;;
            *) why="is not in the export record" ;;
        esac
        echo "::warning file=$(gh_escape_prop "goengines/$p"),title=goengines drift::$(gh_escape_data "goengines/$p $why — an emergency public fix not yet returned to aitasks_go? See goengines/README.md (Emergency fixes).")"
    fi
    DRIFTS=$((DRIFTS + 1))
}

cmd_drift() {
    if ! detect_mode; then
        echo "DRIFT_UNCHECKED:mode"
        return 0
    fi
    if [[ "$MODE" == legacy ]]; then
        echo "DRIFT_SKIPPED:legacy"
        return 0
    fi
    parse_record
    if [[ ${#REC_ERRORS[@]} -gt 0 ]]; then
        if [[ "${REC_ERRORS[0]}" == "cannot be read" ]]; then
            echo "DRIFT_UNCHECKED:EXPORT.txt cannot be read"
        else
            echo "DRIFT_UNCHECKED:EXPORT.txt is malformed (see the check verb)"
        fi
        return 0
    fi
    DRIFTS=0
    local i p h
    for ((i = 0; i < ${#REC_PATHS[@]}; i++)); do
        p="${REC_PATHS[$i]}"
        if [[ ! -f "$dir/$p" ]]; then
            drift_entry missing "$p"
        elif ! h="$(sha256_of "$dir/$p")"; then
            echo "DRIFT_UNCHECKED:cannot hash $p"
            return 0
        elif [[ "$h" != "${REC_HASHES[$i]}" ]]; then
            drift_entry modified "$p"
        fi
    done
    while IFS= read -r -d '' p; do
        p="${p#./}"
        [[ -n "$p" && -f "$dir/$p" ]] || continue
        if [[ "$p" == EXPORT.txt ]] || public_maintained "$p"; then
            continue
        fi
        # A record path is always safe_path (no newline), so only such a name
        # can match REC_SEEN: a name with an embedded newline could otherwise
        # span two adjacent record entries.
        if safe_path "$p" && [[ "$REC_SEEN" == *$'\n'"$p"$'\n'* ]]; then
            continue
        fi
        drift_entry unlisted "$p"
    done < <(tree_files)
    if [[ "$DRIFTS" -eq 0 ]]; then
        echo "DRIFT_NONE"
    else
        echo "DRIFT_FOUND:$DRIFTS"
    fi
}

case "$verb" in
    mode)
        detect_mode || exit 1
        echo "MODE:$MODE"
        if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
            printf 'mode=%s\n' "$MODE" >>"$GITHUB_OUTPUT"
        fi
        ;;
    check) cmd_check ;;
    drift) cmd_drift ;;
esac
