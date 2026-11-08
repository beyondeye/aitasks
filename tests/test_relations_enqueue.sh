#!/usr/bin/env bash
# test_relations_enqueue.sh - aitask_relations_enqueue.sh's contract (t1981_3).
#
# The trigger helper must print NOTHING on stdout and exit 0 whatever happens:
# disabled, switched off, outside a repository, without arguments, without a
# Python interpreter, and when its detached part is killed. When it is enabled,
# the detached part enqueues and the worker produces a record.
#
# Scratch repos only; never ~/.aitask*. Assertions run in the main shell
# (commands are only captured through $( )), so the in-process counters are
# sufficient.
#
# Run: bash tests/test_relations_enqueue.sh
set -u

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=../.aitask-scripts/lib/python_resolve.sh
. "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"

PASS=0
FAIL=0
TOTAL=0

PY="$(resolve_python)"
export AIT_PYTHON="$PY"
HELPER="$PROJECT_DIR/.aitask-scripts/aitask_relations_enqueue.sh"
FIX="$PROJECT_DIR/tests/fixtures/relation_candidates"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/relations-enqueue-XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/home"
export HOME="$TMP/home" GIT_CONFIG_GLOBAL=/dev/null GIT_CONFIG_NOSYSTEM=1 GIT_TERMINAL_PROMPT=0
unset AITASKS_HOME AIT_RELATIONS TASK_DIR PLAN_DIR ARCHIVED_DIR ARCHIVED_PLAN_DIR

export REF_PROVIDER_SPEC="$TMP/provider.json" STUB_AGENT_SPEC="$TMP/agent.json"
export AIT_RELATIONS_CANDIDATES_CMD="$PY $FIX/reference_provider.py"
export AIT_RELATIONS_AGENT_CMD="$PY $FIX/stub_agent.py"
printf '{"candidates": []}\n' > "$REF_PROVIDER_SPEC"
printf '{"mode": "ok", "relations": [], "considered": []}\n' > "$STUB_AGENT_SPEC"

R="$TMP/repo"
git init -q "$R"
git -C "$R" config user.email t@example.com
git -C "$R" config user.name T
mkdir -p "$R/aitasks/metadata" "$R/aiplans"
printf -- '---\nstatus: Ready\ncreated_at: 2026-11-01 10:00\n---\n\nGoal.\n' > "$R/aitasks/t10_name.md"
git -C "$R" add -A
git -C "$R" commit -q -m init

config() {  # config <enabled:true|false|-> [extra yaml lines]
    {
        printf 'project:\n  name: aitasks\nrelations:\n'
        [[ "$1" != "-" ]] && printf '  enabled: %s\n' "$1"
        printf '  settle_s: 0\n'
        [[ -n "${2:-}" ]] && printf '%s\n' "$2"
    } > "$R/aitasks/metadata/project_config.yaml"
}

# run_helper <dir> <args...>: echo "<rc>|<stdout>"; the helper runs with cwd <dir>.
run_helper() {
    local dir="$1" out rc
    shift
    out="$(cd "$dir" && "$HELPER" "$@")"
    rc=$?
    printf '%s|%s' "$rc" "$out"
}

SPOOL="$R/.git/aitask-relations/spool"

wait_worker_idle() {
    local _
    for _ in $(seq 1 200); do
        if "$PY" -c "
import fcntl, os, sys
p = sys.argv[1]
if not os.path.exists(p): sys.exit(0)
fd = os.open(p, os.O_RDWR)
try:
    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
except OSError:
    sys.exit(1)
" "$SPOOL/worker.lock" && ! ls "$SPOOL/jobs/"*.json >/dev/null 2>&1 \
            && ! ls "$SPOOL/running/"*.json >/dev/null 2>&1; then
            return 0
        fi
        sleep 0.1
    done
    return 1
}

log_lines() { if [[ -f "$SPOOL/enqueue.log" ]]; then wc -l < "$SPOOL/enqueue.log"; else echo 0; fi; }

# enqueue_and_wait <dir> <args...>: run the helper, then wait until its detached
# part has logged its outcome (ENQUEUE...) and the worker is idle, so the next
# case cannot rewrite the config under a still-running detached part.
enqueue_and_wait() {
    local before res _
    before="$(log_lines)"
    res="$(run_helper "$@")"
    for _ in $(seq 1 200); do
        if [[ -f "$SPOOL/enqueue.log" ]] \
            && tail -n +"$((before + 1))" "$SPOOL/enqueue.log" | grep -q 'ENQUEUE'; then
            break
        fi
        sleep 0.05
    done
    wait_worker_idle
    printf '%s' "$res"
}

has_record() {  # has_record <tid>: 0 when the store holds records/t<tid>.json
    PROJECT_LIB="$PROJECT_DIR/.aitask-scripts/lib" "$PY" -c '
import os, sys
sys.path.insert(0, os.environ["PROJECT_LIB"])
import relations_store as rst
store = rst.Store(sys.argv[1])
sys.exit(0 if "records/t%s.json" % sys.argv[2] in store.read(no_fetch=True).files else 1)
' "$R" "$1"
}

# --- disabled: silent, exit 0, nothing queued -----------------------------------
config false
assert_eq "disabled: no stdout, exit 0" "0|" "$(enqueue_and_wait "$R" relations created 10)"
assert_eq "disabled: no job queued" "" "$(ls "$SPOOL/jobs" 2>/dev/null)"
assert_contains "disabled: the skip is logged" "SKIPPED:disabled" "$(cat "$SPOOL/enqueue.log")"

# --- absent key = disabled -------------------------------------------------------
config -
assert_eq "absent key: no stdout, exit 0" "0|" "$(enqueue_and_wait "$R" relations created 10)"
assert_eq "absent key: no job queued" "" "$(ls "$SPOOL/jobs" 2>/dev/null)"

# --- per-trigger switch and the host kill switch --------------------------------
config true '  triggers:
    created: false'
assert_eq "trigger off: no stdout, exit 0" "0|" "$(enqueue_and_wait "$R" relations created 10)"
assert_contains "trigger off: skipped" "SKIPPED:trigger_off:created" "$(cat "$SPOOL/enqueue.log")"
config true
export AIT_RELATIONS=0
assert_eq "AIT_RELATIONS=0: no stdout, exit 0" "0|" "$(enqueue_and_wait "$R" relations created 10)"
unset AIT_RELATIONS
assert_contains "AIT_RELATIONS=0: skipped" "SKIPPED:host_off" "$(cat "$SPOOL/enqueue.log")"

# --- bad invocations ------------------------------------------------------------
assert_eq "no arguments: no stdout, exit 0" "0|" "$(run_helper "$R")"
mkdir -p "$TMP/norepo"
assert_eq "outside a repository: no stdout, exit 0" "0|" "$(run_helper "$TMP/norepo" relations created 10)"
assert_eq "unknown op: no stdout, exit 0" "0|" "$(enqueue_and_wait "$R" obsolescence landed 10)"
assert_contains "obsolescence is reserved, not implemented" "SKIPPED:op_unimplemented" "$(cat "$SPOOL/enqueue.log")"

# --- no Python interpreter ------------------------------------------------------
# A PATH with the basic tools but no python, and a HOME with no venv.
mkdir -p "$TMP/nopy-bin"
for tool in dirname git mkdir date nohup cat sed grep env; do
    ln -sf "$(command -v "$tool")" "$TMP/nopy-bin/$tool"
done
before="$(log_lines)"
out="$(cd "$R" && env -u AIT_PYTHON PATH="$TMP/nopy-bin" /bin/bash "$HELPER" relations created 10)"
rc=$?
assert_eq "no python: no stdout, exit 0" "0|" "$rc|$out"
assert_contains "no python: logged" "ENQUEUE_ERROR: no python interpreter" \
    "$(tail -n +"$((before + 1))" "$SPOOL/enqueue.log")"

# --- the detached part is killed ------------------------------------------------
cat > "$TMP/killed_python" <<'EOF'
#!/bin/sh
kill -9 $$
EOF
chmod +x "$TMP/killed_python"
assert_eq "killed detached part: no stdout, exit 0" "0|" \
    "$(AIT_PYTHON="$TMP/killed_python" run_helper "$R" relations created 10)"

# --- the detached part fails ----------------------------------------------------
cat > "$TMP/failing_python" <<'EOF'
#!/bin/sh
echo "noise on stdout" ; echo "noise on stderr" >&2 ; exit 7
EOF
chmod +x "$TMP/failing_python"
assert_eq "failing detached part: no stdout, exit 0" "0|" \
    "$(AIT_PYTHON="$TMP/failing_python" run_helper "$R" relations created 10)"

# --- enabled: the detached part enqueues and the worker analyses ----------------
config true
assert_eq "enabled: no stdout, exit 0" "0|" "$(enqueue_and_wait "$R" relations created 10)"
if has_record 10; then
    assert_eq "enabled: the worker wrote the record" "yes" "yes"
else
    assert_eq "enabled: the worker wrote the record" "yes" "no ($(tail -5 "$SPOOL/enqueue.log"))"
fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
