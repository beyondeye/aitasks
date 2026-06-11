#!/usr/bin/env bash
# test_registry_reader_parity.sh — Pin the single registry-file reader authority
# (t970) byte-for-byte against the pre-change bash baseline.
#
# t970 collapsed three duplicate awk parsers of ~/.config/aitasks/projects.yaml
# into one Python authority (agent_launch_utils.py --list-registry /
# --resolve-index), with bash shelling out to it. This test freezes the exact
# output the *former* bash readers produced (captured before the migration) and
# asserts the Python CLI reproduces it, plus the data-loss regression guard: an
# add/remove/update round-trip must preserve git_remote + last_opened on the
# entries it doesn't touch.
#
# Run: bash tests/test_registry_reader_parity.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

RESOLVER="$PROJECT_DIR/.aitask-scripts/aitask_project_resolve.sh"
PROJECTS="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"
AGENT_LIB="$PROJECT_DIR/.aitask-scripts/lib/agent_launch_utils.py"

# Resolve the same interpreter the framework uses.
# shellcheck source=lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYBIN="$(resolve_python)"
if [[ -z "$PYBIN" ]]; then
    echo "SKIP: no Python interpreter resolved; registry reader requires Python."
    exit 0
fi

TMPROOT=$(mktemp -d)
trap 'rm -rf "$TMPROOT"' EXIT

# Isolate against any AITASKS_PROJECT_<name> process env contamination.
unset AITASKS_PROJECT_alpha AITASKS_PROJECT_realproj AITASKS_PROJECT_missing 2>/dev/null || true

py_list() { AITASKS_PROJECTS_INDEX="$1" "$PYBIN" "$AGENT_LIB" --list-registry; }
py_resolve_index() { AITASKS_PROJECTS_INDEX="$1" "$PYBIN" "$AGENT_LIB" --resolve-index "$2"; }

# --- Golden corpus: every grammar case in one fixture -------------------
# Covers: unquoted / double-quoted / single-quoted values; all-4-fields;
# name+path+remote (no last); name+path+last (no remote); a name-only entry
# (the emit-on-name divergence); comments + blank lines; and an indented bare
# `name:` line that flushes the current entry (hand-edited form).
FIX="$TMPROOT/corpus.yaml"
cat > "$FIX" <<'EOF'
# aitasks per-user project registry — managed by `ait projects`.
# Edit by hand at your own risk; use `ait projects add` instead.
projects:
  - name: alpha
    path: /tmp/reg/alpha
    git_remote: https://example.test/alpha.git
    last_opened: 2026-01-02
  - name: "beta quoted"
    path: "/tmp/reg/beta"
    git_remote: git@example.test:beta.git
  - name: 'gamma'
    path: '/tmp/reg/gamma'
    last_opened: 2026-03-04
  - name: nopath
  - name: stale
    path: /tmp/reg/gone
    git_remote: https://example.test/stale.git
    last_opened: 2026-05-06
  - name: delta
    path: /tmp/reg/delta
    name: delta_dup
    path: /tmp/reg/delta_dup
EOF

# Frozen baseline — captured from the pre-t970 bash `list_registry_entries`.
read -r -d '' GOLDEN_LIST <<'EOF' || true
alpha|/tmp/reg/alpha|https://example.test/alpha.git|2026-01-02
beta quoted|/tmp/reg/beta|git@example.test:beta.git|
gamma|/tmp/reg/gamma||2026-03-04
nopath|||
stale|/tmp/reg/gone|https://example.test/stale.git|2026-05-06
delta|/tmp/reg/delta||
delta_dup|/tmp/reg/delta_dup||
EOF

ACTUAL_LIST="$(py_list "$FIX")"
assert_eq "--list-registry byte-for-byte == pre-change bash baseline" \
    "$GOLDEN_LIST" "$ACTUAL_LIST"

# --- --resolve-index parity (frozen baseline from bash index_lookup_path) ---
assert_eq "resolve-index alpha"        "/tmp/reg/alpha"     "$(py_resolve_index "$FIX" alpha)"
assert_eq "resolve-index 'beta quoted'" "/tmp/reg/beta"     "$(py_resolve_index "$FIX" "beta quoted")"
assert_eq "resolve-index gamma"        "/tmp/reg/gamma"     "$(py_resolve_index "$FIX" gamma)"
assert_eq "resolve-index nopath (no path → empty)" "" "$(py_resolve_index "$FIX" nopath)"
assert_eq "resolve-index stale"        "/tmp/reg/gone"      "$(py_resolve_index "$FIX" stale)"
assert_eq "resolve-index delta"        "/tmp/reg/delta"     "$(py_resolve_index "$FIX" delta)"
assert_eq "resolve-index delta_dup"    "/tmp/reg/delta_dup" "$(py_resolve_index "$FIX" delta_dup)"
assert_eq "resolve-index missing (absent → empty)" "" "$(py_resolve_index "$FIX" missing)"

# --- AITASKS_PROJECTS_INDEX override honored ----------------------------
ALT="$TMPROOT/alt.yaml"
cat > "$ALT" <<'EOF'
projects:
  - name: solo
    path: /tmp/reg/solo
EOF
assert_eq "override: alt index resolved (not the corpus)" "/tmp/reg/solo" "$(py_resolve_index "$ALT" solo)"
assert_eq "override: corpus name absent in alt index" "" "$(py_resolve_index "$ALT" alpha)"
assert_eq "missing index file → empty list" "" "$(py_list "$TMPROOT/does_not_exist.yaml")"

# --- Bash ≡ Python through the public resolver surface ------------------
# Build a real marker project so the resolver's STALE/RESOLVED branches and the
# bash index_lookup_path agree with the Python authority.
mkdir -p "$TMPROOT/projects/realproj/aitasks/metadata"
touch "$TMPROOT/projects/realproj/aitasks/metadata/project_config.yaml"
REG2="$TMPROOT/reg2.yaml"
cat > "$REG2" <<EOF
projects:
  - name: realproj
    path: $TMPROOT/projects/realproj
    git_remote: https://example.test/realproj.git
    last_opened: 2026-04-04
  - name: deadproj
    path: $TMPROOT/projects/gone
    git_remote: https://example.test/dead.git
    last_opened: 2026-04-05
EOF

# resolve <name> wraps the bash index_lookup_path (after a tmux-scan miss).
RES_REAL=$(AITASKS_PROJECTS_INDEX="$REG2" "$RESOLVER" realproj)
assert_eq "resolver RESOLVED uses bash index path == python authority" \
    "RESOLVED:$TMPROOT/projects/realproj" "$RES_REAL"
assert_eq "python --resolve-index agrees with bash resolve path" \
    "$TMPROOT/projects/realproj" "$(py_resolve_index "$REG2" realproj)"

RES_DEAD=$(AITASKS_PROJECTS_INDEX="$REG2" "$RESOLVER" deadproj)
assert_eq "resolver STALE for missing-marker path (bash index)" \
    "STALE:deadproj:$TMPROOT/projects/gone" "$RES_DEAD"

RES_MISS=$(AITASKS_PROJECTS_INDEX="$REG2" "$RESOLVER" missing)
assert_eq "resolver NOT_FOUND for absent name" "NOT_FOUND:missing" "$RES_MISS"

# --- cmd_list (`resolve.sh list`) now python-backed ---------------------
LIST_OUT=$(AITASKS_PROJECTS_INDEX="$REG2" "$RESOLVER" list)
assert_contains "list: RESOLVED row for marker-backed project" \
    "PROJECT:realproj:$TMPROOT/projects/realproj:RESOLVED" "$LIST_OUT"
assert_contains "list: STALE row for missing-marker project" \
    "PROJECT:deadproj:$TMPROOT/projects/gone:STALE" "$LIST_OUT"

# --- Round-trip: git_remote + last_opened survive a mutation -----------
# THE data-loss regression guard. Add a new project, then remove another;
# assert the untouched entry keeps its remote + last_opened byte-for-byte.
mkdir -p "$TMPROOT/projects/newproj/aitasks/metadata"
cat > "$TMPROOT/projects/newproj/aitasks/metadata/project_config.yaml" <<'EOF'
project:
  name: newproj
  git_remote: https://example.test/newproj.git
EOF

REG3="$TMPROOT/reg3.yaml"
cp "$REG2" "$REG3"

AITASKS_PROJECTS_INDEX="$REG3" "$PROJECTS" add "$TMPROOT/projects/newproj" >/dev/null
assert_contains "round-trip(add): realproj git_remote preserved" \
    "git_remote: https://example.test/realproj.git" "$(cat "$REG3")"
assert_contains "round-trip(add): realproj last_opened preserved" \
    "last_opened: 2026-04-04" "$(cat "$REG3")"
assert_contains "round-trip(add): deadproj git_remote preserved" \
    "git_remote: https://example.test/dead.git" "$(cat "$REG3")"
assert_contains "round-trip(add): new entry registered" \
    "name: newproj" "$(cat "$REG3")"

AITASKS_PROJECTS_INDEX="$REG3" "$PROJECTS" remove deadproj --force >/dev/null
REG3_AFTER="$(cat "$REG3")"
assert_not_contains "round-trip(remove): deadproj gone" "name: deadproj" "$REG3_AFTER"
assert_contains "round-trip(remove): realproj git_remote still intact" \
    "git_remote: https://example.test/realproj.git" "$REG3_AFTER"
assert_contains "round-trip(remove): realproj last_opened still intact" \
    "last_opened: 2026-04-04" "$REG3_AFTER"

# update repoints realproj; git_remote must survive, last_opened refreshes.
mkdir -p "$TMPROOT/projects/realproj2/aitasks/metadata"
touch "$TMPROOT/projects/realproj2/aitasks/metadata/project_config.yaml"
AITASKS_PROJECTS_INDEX="$REG3" "$PROJECTS" update realproj "$TMPROOT/projects/realproj2" >/dev/null
REG3_UPD="$(cat "$REG3")"
assert_contains "round-trip(update): realproj git_remote kept across repoint" \
    "git_remote: https://example.test/realproj.git" "$REG3_UPD"
assert_contains "round-trip(update): realproj path repointed" \
    "path: $TMPROOT/projects/realproj2" "$REG3_UPD"

# --- Summary ------------------------------------------------------------
echo
echo "=========================================="
echo "Tests: $TOTAL  Passed: $PASS  Failed: $FAIL"
echo "=========================================="

[[ "$FAIL" -eq 0 ]]
