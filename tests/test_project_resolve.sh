#!/usr/bin/env bash
# test_project_resolve.sh - Cover aitask_project_resolve.sh's three
# resolution paths (per-user index, process env var, STALE) plus
# NOT_FOUND, and the `candidates` mode (t1869), whose tmux tier runs against a
# private tmux server. The named resolve's own live-tmux scan is exercised by
# manual end-to-end checks rather than mocked here.
#
# Run: bash tests/test_project_resolve.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Shared assertion helpers (see tests/lib/asserts.sh).
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0


# --- Setup: build two fake projects + an isolated index file -----------

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

REGISTRY_FILE="$TMPROOT/projects.yaml"
export AITASKS_PROJECTS_INDEX="$REGISTRY_FILE"

# Two fake aitasks projects (just the marker file is enough for the
# resolver's STALE / valid check).
mkdir -p "$TMPROOT/projects/alpha/aitasks/metadata"
touch "$TMPROOT/projects/alpha/aitasks/metadata/project_config.yaml"
mkdir -p "$TMPROOT/projects/beta/aitasks/metadata"
touch "$TMPROOT/projects/beta/aitasks/metadata/project_config.yaml"
# A path we'll reference but not back with the marker file (drives STALE).
mkdir -p "$TMPROOT/projects/gone"

# Hand-write a registry: alpha exists, gone is registered but its
# metadata is missing.
cat > "$REGISTRY_FILE" <<EOF
projects:
  - name: alpha
    path: $TMPROOT/projects/alpha
    git_remote: https://example.test/alpha.git
  - name: gone
    path: $TMPROOT/projects/gone
EOF

RESOLVER="$PROJECT_DIR/.aitask-scripts/aitask_project_resolve.sh"

# Isolate the env-var path against contamination from the live shell.
unset AITASKS_PROJECT_alpha AITASKS_PROJECT_beta AITASKS_PROJECT_gone \
      AITASKS_PROJECT_envonly AITASKS_PROJECT_missing 2>/dev/null || true

# --- Tests --------------------------------------------------------------

# 1. resolve-by-index → RESOLVED:<root>
out=$("$RESOLVER" alpha)
assert_eq "resolve-by-index: alpha resolves to fake root" \
    "RESOLVED:$TMPROOT/projects/alpha" "$out"

# 2. STALE → registered but path missing the marker file
out=$("$RESOLVER" gone)
assert_eq "STALE: gone points at missing aitasks marker" \
    "STALE:gone:$TMPROOT/projects/gone" "$out"

# 3. NOT_FOUND → not in registry and no env var
out=$("$RESOLVER" missing)
assert_eq "NOT_FOUND: missing project name" \
    "NOT_FOUND:missing" "$out"

# 4. Process env-var fallback → RESOLVED via AITASKS_PROJECT_envonly
export AITASKS_PROJECT_envonly="$TMPROOT/projects/beta"
out=$("$RESOLVER" envonly)
assert_eq "env-var fallback: AITASKS_PROJECT_envonly resolves" \
    "RESOLVED:$TMPROOT/projects/beta" "$out"
unset AITASKS_PROJECT_envonly

# 5. Process env-var pointing at a non-aitasks dir → STALE
export AITASKS_PROJECT_envonly="$TMPROOT/projects/gone"
out=$("$RESOLVER" envonly)
assert_eq "env-var fallback: stale path → STALE" \
    "STALE:envonly:$TMPROOT/projects/gone" "$out"
unset AITASKS_PROJECT_envonly

# 6. Registry hit takes precedence over a (would-be) env var fallback
export AITASKS_PROJECT_alpha="$TMPROOT/projects/beta"
out=$("$RESOLVER" alpha)
assert_eq "precedence: registry beats process env var" \
    "RESOLVED:$TMPROOT/projects/alpha" "$out"
unset AITASKS_PROJECT_alpha

# --- candidates <name> (t1869) -------------------------------------------
#
# Every match in every tier, plus a completeness verdict. The tmux tier runs
# against a PRIVATE server (own TMUX_TMPDIR + socket name) so the user's live
# `ait` server can never contribute a candidate or be touched.

TMX="$(mktemp -d /tmp/ait_rc_XXXXXX)"
export TMUX_TMPDIR="$TMX" AITASKS_TMUX_SOCKET="rt_$$"
priv_tmux() { tmux -L "rt_$$" "$@"; }
cleanup_cand() { priv_tmux kill-server >/dev/null 2>&1 || true; rm -rf "$TMX"; }
trap 'cleanup_cand; rm -rf "$TMPROOT"' EXIT

# 7. No tmux server at all is a DEFINITE empty tier, not an incomplete one.
out=$("$RESOLVER" candidates alpha)
assert_eq "candidates: registry hit, no tmux server → complete" \
    "CANDIDATE:registry:RESOLVED:$TMPROOT/projects/alpha
CANDIDATES_COMPLETE" "$out"

# 8. Stale entries are reported with their status, never dropped.
out=$("$RESOLVER" candidates gone)
assert_eq "candidates: stale registry entry kept as STALE" \
    "CANDIDATE:registry:STALE:$TMPROOT/projects/gone
CANDIDATES_COMPLETE" "$out"

# 9. Unknown name → no candidates, still complete.
out=$("$RESOLVER" candidates missing)
assert_eq "candidates: unknown name → complete, empty" "CANDIDATES_COMPLETE" "$out"

# 10. Duplicate registry names are listed separately (the named resolve would
#     silently return the first one).
DUP_REG="$TMPROOT/dup.yaml"
cat > "$DUP_REG" <<EOF
projects:
  - name: alpha
    path: $TMPROOT/projects/alpha
  - name: alpha
    path: $TMPROOT/projects/beta
EOF
out=$(AITASKS_PROJECTS_INDEX="$DUP_REG" "$RESOLVER" candidates alpha)
assert_eq "candidates: duplicate registry names both listed" \
    "CANDIDATE:registry:RESOLVED:$TMPROOT/projects/alpha
CANDIDATE:registry:RESOLVED:$TMPROOT/projects/beta
CANDIDATES_COMPLETE" "$out"
out=$(AITASKS_PROJECTS_INDEX="$DUP_REG" "$RESOLVER" alpha)
assert_eq "named resolve unchanged by the new mode (first hit)" \
    "RESOLVED:$TMPROOT/projects/alpha" "$out"

# 11. env tier listed alongside the registry — no precedence applied.
out=$(AITASKS_PROJECT_alpha="$TMPROOT/projects/beta" "$RESOLVER" candidates alpha)
assert_eq "candidates: env tier listed alongside registry" \
    "CANDIDATE:registry:RESOLVED:$TMPROOT/projects/alpha
CANDIDATE:env:RESOLVED:$TMPROOT/projects/beta
CANDIDATES_COMPLETE" "$out"

# 12. A missing registry FILE is definite, not incomplete.
out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/nope.yaml" "$RESOLVER" candidates alpha)
assert_eq "candidates: missing registry file → complete" "CANDIDATES_COMPLETE" "$out"

# 13. Forced enumeration failures fail closed, per tier.
out=$(AIT_PROJECT_RESOLVE_ENUM_FAIL=registry "$RESOLVER" candidates alpha)
assert_eq "candidates: registry enumeration failure → incomplete" \
    "CANDIDATES_INCOMPLETE:registry" "$out"
out=$(AIT_PROJECT_RESOLVE_ENUM_FAIL=tmux "$RESOLVER" candidates alpha)
assert_eq "candidates: tmux failure → incomplete despite a registry hit" \
    "CANDIDATE:registry:RESOLVED:$TMPROOT/projects/alpha
CANDIDATES_INCOMPLETE:tmux" "$out"

# 13b. A REAL unreadable registry (not the forced seam): the permissive reader
#      would fold it into "no entries" and report the tier complete — with an
#      env candidate present that was CANDIDATES_COMPLETE, hiding a conflicting
#      registered root. Both modes must say INCOMPLETE.
if [[ "$(id -u)" != 0 ]]; then
    UNREAD="$TMPROOT/unreadable.yaml"
    cp "$REGISTRY_FILE" "$UNREAD"; chmod 000 "$UNREAD"
    out=$(AITASKS_PROJECTS_INDEX="$UNREAD" AITASKS_PROJECT_alpha="$TMPROOT/projects/beta" \
        "$RESOLVER" candidates alpha)
    assert_eq "candidates: unreadable registry → incomplete, even with an env hit" \
        "CANDIDATE:env:RESOLVED:$TMPROOT/projects/beta
CANDIDATES_INCOMPLETE:registry" "$out"
    out=$(AITASKS_PROJECTS_INDEX="$UNREAD" "$RESOLVER" bindings "$TMPROOT/projects/alpha")
    assert_eq "bindings: unreadable registry → incomplete" \
        "BINDINGS_INCOMPLETE:registry" "$out"
    chmod 644 "$UNREAD"
else
    echo "SKIP 13b: running as root, chmod 000 does not deny reads"
fi
# A registry inside a directory this process may not SEARCH: exists()/lexists()
# and `[[ -e ]]` all answer "absent" there, so absence must be proven with a
# call that raises. Both modes must say INCOMPLETE, env hit or not.
if [[ "$(id -u)" != 0 ]]; then
    mkdir -p "$TMPROOT/locked"; cp "$REGISTRY_FILE" "$TMPROOT/locked/projects.yaml"
    chmod 000 "$TMPROOT/locked"
    out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/locked/projects.yaml" \
        AITASKS_PROJECT_alpha="$TMPROOT/projects/beta" "$RESOLVER" candidates alpha)
    assert_eq "candidates: unsearchable parent dir → incomplete, even with an env hit" \
        "CANDIDATE:env:RESOLVED:$TMPROOT/projects/beta
CANDIDATES_INCOMPLETE:registry" "$out"
    out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/locked/projects.yaml" \
        "$RESOLVER" bindings "$TMPROOT/projects/alpha")
    assert_eq "bindings: unsearchable parent dir → incomplete" \
        "BINDINGS_INCOMPLETE:registry" "$out"
    chmod 755 "$TMPROOT/locked"
fi
# A dangling symlink at the registry path is not proof of absence either.
ln -s "$TMPROOT/does-not-exist.yaml" "$TMPROOT/dangling.yaml"
out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/dangling.yaml" "$RESOLVER" candidates alpha)
assert_eq "candidates: dangling registry symlink → incomplete" \
    "CANDIDATES_INCOMPLETE:registry" "$out"

# A directory at the registry path exists but is not a readable registry.
mkdir -p "$TMPROOT/regdir.yaml"
out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/regdir.yaml" "$RESOLVER" candidates alpha)
assert_eq "candidates: a directory at the registry path → incomplete" \
    "CANDIDATES_INCOMPLETE:registry" "$out"
out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/regdir.yaml" "$RESOLVER" bindings "$TMPROOT/projects/alpha")
assert_eq "bindings: a directory at the registry path → incomplete" \
    "BINDINGS_INCOMPLETE:registry" "$out"
out=$("$RESOLVER" bindings "$TMPROOT/projects/alpha")
assert_eq "bindings: readable registry names the declared binding" \
    "BINDING:registry:alpha
BINDINGS_COMPLETE" "$out"
out=$(AITASKS_PROJECTS_INDEX="$TMPROOT/nope.yaml" "$RESOLVER" bindings "$TMPROOT/projects/alpha")
assert_eq "bindings: missing registry file is definite" "BINDINGS_COMPLETE" "$out"

# 14. Live tmux tier: TWO sessions matching the name, rooted in different
#     projects, are both listed (session-name match and project-name match).
if command -v tmux >/dev/null 2>&1; then
    priv_tmux new-session -d -s alpha -c "$TMPROOT/projects/beta" 'sleep 60'
    priv_tmux new-session -d -s other -c "$TMPROOT/projects/alpha" 'sleep 60'
    out=$("$RESOLVER" candidates alpha | sort)
    expected=$(printf '%s\n' \
        "CANDIDATE:registry:RESOLVED:$TMPROOT/projects/alpha" \
        "CANDIDATE:tmux:RESOLVED:$TMPROOT/projects/alpha" \
        "CANDIDATE:tmux:RESOLVED:$TMPROOT/projects/beta" \
        "CANDIDATES_COMPLETE" | sort)
    assert_eq "candidates: every matching live session listed" "$expected" "$out"
    priv_tmux kill-server >/dev/null 2>&1 || true
else
    echo "SKIP 14: tmux not installed"
fi

# --- Summary ------------------------------------------------------------

echo
echo "===================="
echo "Passed: $PASS / $TOTAL"
[[ "$FAIL" -gt 0 ]] && echo "Failed: $FAIL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
