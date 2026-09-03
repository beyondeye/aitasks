#!/usr/bin/env bash
# test_attach_lock_callback_contract.sh — the t1675 callback contract.
#
# `with_attach_lock` runs its body as `"$@" || rc=$?`, and bash disables errexit
# for the ENTIRE invocation whose status is tested. So inside every attach /
# artifact transaction a failing command does not abort, and a later successful
# command overwrites its status — the wrapper returns 0 and the verb reports
# SUCCESS while having committed partial state. The full contract (including the
# four ways of restoring errexit that were measured and all fail) lives in
# lib/attachment_lock.sh under "CALLBACK CONTRACT".
#
# Two parts:
#
#   Part A — BEHAVIORAL. Inject a real fault into one mutating call inside a real
#     transaction and pin that the verb does not report success and commits
#     nothing. This is what the contract is FOR.
#   Part B/C — STATIC. Every `with_attach_lock` callback (and the same-file
#     helpers it calls) must status-check every known mutator, so a new callback
#     cannot reintroduce the bug silently. Part C proves the matcher itself
#     catches the shapes it claims to.
#
# NOT ASSERTED HERE, deliberately: the on-disk state left behind after a
# transaction aborts. These guards stop a failure being reported as SUCCESS;
# the residual working-tree drift, and the transaction-boundary defects around
# it, belong to t1698. Asserting a clean worktree here would silently require
# the rollback work that task owns.
#
# Fault injection uses the documented AIT_PYTHON override (python_resolve.sh
# resolution order, rung 1) with a passthrough shim that fails exactly one
# named script + subcommand, optionally only on its Nth call.
#
# Run: bash tests/test_attach_lock_callback_contract.sh
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
REAL_PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"

TMP="$(mktemp -d)"; trap 'rm -rf "$TMP"' EXIT

# ── The fault-injecting python shim ──────────────────────────────────────────
# Fails when argv names $AIT_FAULT_SCRIPT AND contains $AIT_FAULT_SUBCMD, on the
# $AIT_FAULT_NTH matching call (default 1); passes everything else through. The
# counter lives in a file because each invocation is its own process.
SHIM="$TMP/py_shim.sh"
cat > "$SHIM" <<EOF
#!/usr/bin/env bash
if [[ -n "\${AIT_FAULT_SCRIPT:-}" ]]; then
    script_hit=""; sub_hit=""
    for a in "\$@"; do
        case "\$a" in *"\$AIT_FAULT_SCRIPT") script_hit=1 ;; esac
        [[ "\$a" == "\$AIT_FAULT_SUBCMD" ]] && sub_hit=1
    done
    if [[ -n "\$script_hit" && -n "\$sub_hit" ]]; then
        n=0
        [[ -f "\$AIT_FAULT_COUNT" ]] && n="\$(cat "\$AIT_FAULT_COUNT")"
        n=\$(( n + 1 )); printf '%s' "\$n" > "\$AIT_FAULT_COUNT"
        if (( n == \${AIT_FAULT_NTH:-1} )); then
            echo "INJECTED FAULT: \$AIT_FAULT_SCRIPT \$AIT_FAULT_SUBCMD (call \$n)" >&2
            exit 3
        fi
    fi
fi
exec "$REAL_PY" "\$@"
EOF
chmod +x "$SHIM"

# run_faulted <script> <subcmd> <nth> -- <cmd...>
# Runs <cmd> with the fault armed. Sets RF_RC and RF_OUT; stderr is left in
# $TMP/stderr for a failing run to be inspected by hand.
run_faulted() {
    local script="$1" subcmd="$2" nth="$3"; shift 4   # shift past the "--"
    : > "$TMP/faultcount"
    RF_OUT="$(AIT_PYTHON="$SHIM" AIT_FAULT_SCRIPT="$script" AIT_FAULT_SUBCMD="$subcmd" \
              AIT_FAULT_NTH="$nth" AIT_FAULT_COUNT="$TMP/faultcount" \
              "$@" 2>"$TMP/stderr")"
    RF_RC=$?
}

# run_clean -- the same shim with NO fault armed (passthrough control).
run_clean() {
    RF_OUT="$(AIT_PYTHON="$SHIM" "$@" 2>"$TMP/stderr")"
    RF_RC=$?
}

commits() { git rev-list --count HEAD; }

# pin <desc> <expected-success-substring> -- assert the three contract
# properties: non-zero exit, no success message, nothing committed.
# $BEFORE must hold the pre-command commit count.
pin() {
    local desc="$1" success_msg="$2"
    assert_exit_nonzero_rc "$desc: exits non-zero" "$RF_RC"
    assert_not_contains "$desc: prints no success message" "$success_msg" "$RF_OUT"
    assert_eq "$desc: commits nothing" "0" "$(( $(commits) - BEFORE ))"
}

# ── Fixture: legacy-mode repo (no .aitask-data worktree) ─────────────────────
REPO="$TMP/repo"
mkdir -p "$REPO/aitasks/metadata"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' \
        "$1" > "aitasks/$1.md"
}
mk_task t5_demo; mk_task t6_other; mk_task t7_third; mk_task t8_fourth
mk_task t9_fifth; mk_task t10_sixth
printf 'alpha payload\n' > a.bin
printf 'beta payload\n'  > b.bin
printf 'gamma payload\n' > c.bin
printf 'delta payload\n' > d.bin
# Payloads reserved for the pins/controls that must NOT share a blob with any
# earlier attachment: a pre-existing local blob makes a `move`/`create` commit
# stage nothing for that path, which is exactly how a control stops being one.
printf 'epsilon payload\n' > e.bin
printf 'zeta payload\n'    > f.bin
printf 'eta payload\n'     > g.bin
printf 'theta payload\n'   > h.bin
git add -A; git commit -q -m init

# `dir` is registered as a SECOND backend, never as the default: with
# artifacts.default_backend absent, `create` still resolves to local for every
# other pin. attachments_gc_grace is written by the same helper so the two
# settings cannot clobber each other.
DIRSTORE="$TMP/dirstore"; mkdir -p "$DIRSTORE"
write_config() {   # write_config [gc-grace]
    { printf 'artifacts:\n  backends:\n    dir:\n      path: %s\n' "$DIRSTORE"
      [[ -n "${1:-}" ]] && printf 'attachments_gc_grace: %s\n' "$1"
    } > aitasks/metadata/project_config.yaml
    git add aitasks/metadata/project_config.yaml >/dev/null 2>&1
    git diff --cached --quiet -- aitasks/metadata/project_config.yaml 2>/dev/null \
        || git commit -q -m "config: register dir backend"
}
write_config

# Pure libs, for in-test hashing / shard paths.
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"

HA="$(artifact_sha256 a.bin)"
meta_of() { printf 'attachments/meta/%s.json\n' "$(artifact_shard_path "$1")"; }
blob_of() { printf 'attachments/blobs/%s\n'     "$(artifact_shard_path "$1")"; }

echo "=== Part A — behavioral pins (fault injection) ==============================="

# ── A1. attach add ← frontmatter_patch.py append ─────────────────────────────
# Pre-fix (measured): exit 0, "Attached ...", one commit, and NO attachments
# entry in the task file — a ledger ref nothing points to, which gc can never
# reclaim because refs is non-empty.
BEFORE="$(commits)"
run_faulted frontmatter_patch.py append 1 -- "$ATT" add 5 a.bin --name a.bin
pin "add/frontmatter-append" "Attached"
assert_not_contains "add/frontmatter-append: no attachments entry reaches HEAD" \
    "attachments:" "$(git show HEAD:aitasks/t5_demo.md)"
assert_file_not_exists "add/frontmatter-append: no ledger meta committed" \
    "$(git show HEAD --stat --name-only | grep -F "$(meta_of "$HA")" || true)"

# ── A2. attach rm ← attachment_meta.py decref (pre-mutation) ─────────────────
"$ATT" add 5 a.bin --name a.bin >/dev/null 2>&1        # real attachment first
BEFORE="$(commits)"
run_faulted attachment_meta.py decref 1 -- "$ATT" rm 5 a.bin
pin "rm/decref" "Removed attachment"
assert_contains "rm/decref: the attachment is still listed" "a.bin" "$("$ATT" ls 5 2>&1)"

# ── A3. attach rm ← frontmatter_patch.py remove (post-mutation) ──────────────
# The decref has ALREADY succeeded when the fault lands; pre-fix the pair still
# committed and rm reported success with the ledger decremented and the entry
# still present.
#
# Its OWN task and blob, deliberately. Sharing t5/a.bin with A2 made this pin
# vacuous: pre-fix A2's rm SUCCEEDS, so A3 then died on "no attachment matching"
# — non-zero for entirely the wrong reason, and the pin passed both pre- and
# post-fix. Every pin that mutates must be independent of whether an earlier pin
# behaved as fixed or as broken.
"$ATT" add 8 d.bin --name d.bin >/dev/null 2>&1
assert_contains "rm/frontmatter-remove: fixture attachment exists" "d.bin" "$("$ATT" ls 8 2>&1)"
BEFORE="$(commits)"
run_faulted frontmatter_patch.py remove 1 -- "$ATT" rm 8 d.bin
pin "rm/frontmatter-remove" "Removed attachment"

# ── A4. attach gc ← attachment_meta.py orphaned-at (the destructive read) ────
# Orphan a blob, then fault the grace-window read. Unlike the refs read there is
# no second gate after it: "" is read as "age = infinite" -> eligible -> deleted.
git checkout -q -- aitasks/t5_demo.md 2>/dev/null || true
"$ATT" rm 5 a.bin >/dev/null 2>&1 || true               # refs -> [] , orphaned_at stamped
BEFORE="$(commits)"
run_faulted attachment_meta.py orphaned-at 1 -- "$ATT" gc
pin "gc/orphaned-at" "swept"
assert_file_exists "gc/orphaned-at: the blob was NOT deleted" "$(blob_of "$HA")"

# ── A5. attach gc ← attachment_meta.py zero-refcount (process substitution) ──
# Pre-fix the empty read made the loop a no-op: swept=0, no commit, and gc
# printed "gc: swept 0 orphaned attachment(s)" at exit 0 — a sweep that never
# ran, reported as a clean one.
BEFORE="$(commits)"
run_faulted attachment_meta.py zero-refcount 1 -- "$ATT" gc
pin "gc/zero-refcount" "swept"
assert_file_exists "gc/zero-refcount: the blob is untouched" "$(blob_of "$HA")"

# ── A6. attach decref-deleted ← attachment_meta.py refs (pipeline-in-if) ─────
# Pre-fix the failed read was indistinguishable from "no match", so the rebind
# branch was skipped and the ref orphaned onto the deleted task instead.
"$ATT" add 6 b.bin --name b.bin >/dev/null 2>&1
"$ATT" add 7 b.bin --name b.bin >/dev/null 2>&1
BEFORE="$(commits)"
run_faulted attachment_meta.py refs 1 -- "$ATT" decref-deleted --protect-task 7 6
assert_exit_nonzero_rc "decref-deleted/refs: exits non-zero" "$RF_RC"
assert_not_contains "decref-deleted/refs: no REBIND_NOOP misread" "REBIND_NOOP" "$RF_OUT"
assert_eq "decref-deleted/refs: commits nothing" "0" "$(( $(commits) - BEFORE ))"

# ── A7. attach decref-deleted ← decref, mid-loop (2nd doomed task) ───────────
# Task 6's release succeeds, task 7's fails. Pre-fix the partial release was
# committed and the verb exited 0.
BEFORE="$(commits)"
run_faulted attachment_meta.py decref 2 -- "$ATT" decref-deleted 6 7
assert_exit_nonzero_rc "decref-deleted/decref-2nd: exits non-zero" "$RF_RC"
assert_eq "decref-deleted/decref-2nd: commits nothing" "0" "$(( $(commits) - BEFORE ))"

# ── A8. artifact create ← frontmatter_patch.py append ────────────────────────
# The direct analogue of A1 on the artifact side: pre-fix the manifest + blob
# were committed at exit 0 while the task listed no artifact.
BEFORE="$(commits)"
run_faulted frontmatter_patch.py append 1 -- \
    "$ART" create 5 c.bin --kind report --name c-report
pin "artifact-create/frontmatter-append" "Created artifact"
assert_not_contains "artifact-create: no artifacts entry reaches HEAD" \
    "artifacts:" "$(git show HEAD:aitasks/t5_demo.md)"

# Fixture hygiene, and itself a demonstration of what t1698 owns: A8 aborted
# AFTER `artifact_manifest create` succeeded, so an uncommitted orphan manifest
# is left on disk. Nothing here rolls that back (t1675 stops the false success,
# not the drift), and leaving it would make A9's real create die on the
# handle-collision guard. Drop it explicitly rather than letting the next pin
# fail for an unrelated reason.
rm -f artifacts/manifests/t5-report.json

# ── A9. artifact update ← artifact_manifest.py set-current ───────────────────
# Pre-fix this printed "current is now <hash>" at exit 0 WITHOUT moving current.
"$ART" create 5 c.bin --kind report --name c-report >/dev/null 2>&1
# `versions` marks the current version with a leading '*' (there is no `current`
# verb); that starred line is the assertable "which version is current".
cur_of() { "$ART" versions "$1" 2>/dev/null | grep '^\*' || true; }
CUR_BEFORE="$(cur_of art:t5-report)"
assert_contains "artifact-update: fixture has a current version to move" "*" "$CUR_BEFORE"
printf 'gamma payload v2\n' > c2.bin
BEFORE="$(commits)"
run_faulted artifact_manifest.py set-current 1 -- "$ART" update art:t5-report c2.bin
pin "artifact-update/set-current" "current is now"
assert_eq "artifact-update: current did not move" "$CUR_BEFORE" "$(cur_of art:t5-report)"

# ── A10. artifact rm ← artifact_manifest.py get (command substitution) ───────
# Pre-fix the failed read yielded "", which took the stale-reference branch and
# dropped a LIVE frontmatter entry while orphaning its manifest.
BEFORE="$(commits)"
run_faulted artifact_manifest.py get 1 -- "$ART" rm 5 art:t5-report
pin "artifact-rm/manifest-get" "Removed"
assert_contains "artifact-rm: the artifact is still listed" \
    "art:t5-report" "$("$ART" ls 5 2>&1)"

# ── A11. artifact move (dir → local) ← artifact_manifest.py set-backend ──────
# Pre-fix this reported "Moved ... to backend 'local'" at exit 0 with the
# manifest still naming `dir`: the blobs were copied but the ledger never moved.
#
# The DIRECTION is load-bearing. Moving *to* dir stages no blob paths, so the
# pre-fix commit would be empty and `_artifact_commit` (which has no empty-commit
# guard) would fail on its own — the pin would then pass pre- and post-fix alike,
# which is exactly why two other move candidates were dropped as
# non-discriminating.
"$ART" create 10 e.bin --kind mockup --name e-mock --backend dir >/dev/null 2>&1
MOVE_MANIFEST="artifacts/manifests/t10-mockup.json"
assert_contains "artifact-move: fixture artifact is on the dir backend" \
    '"dir"' "$(git show "HEAD:$MOVE_MANIFEST")"
BEFORE="$(commits)"
run_faulted artifact_manifest.py set-backend 1 -- "$ART" move art:t10-mockup --to local
pin "artifact-move/set-backend" "Moved"
assert_contains "artifact-move: the manifest still names the source backend" \
    '"dir"' "$(git show "HEAD:$MOVE_MANIFEST")"

# ── A12. Negative controls: every verb above, unfaulted ──────────────────────
# Without these, every pin above could be passing because the fixture is broken
# rather than because the guard fired. Each control is the exact mirror of `pin`:
# exit 0, the success message present, and the expected number of commits — so a
# pin and its control can only both hold if the shim is a pure passthrough and
# the verb discriminates on the injected fault.
ctl() {   # ctl <desc> <expected-success-substring> <expected-commits>
    local desc="$1" msg="$2" want="$3"
    assert_exit_zero_rc "control/$desc: succeeds under the shim" "$RF_RC"
    assert_contains "control/$desc: reports success" "$msg" "$RF_OUT"
    assert_eq "control/$desc: makes $want commit(s)" "$want" "$(( $(commits) - BEFORE ))"
}

BEFORE="$(commits)"; run_clean "$ATT" add 6 a.bin --name a.bin
ctl "attach-add" "Attached" 1
BEFORE="$(commits)"; run_clean "$ATT" rm 6 a.bin
ctl "attach-rm" "Removed attachment" 1

# decref-deleted: give t6 a ref of its own to release, then release it.
"$ATT" add 6 f.bin --name f.bin >/dev/null 2>&1
BEFORE="$(commits)"; run_clean "$ATT" decref-deleted 6
ctl "attach-decref-deleted" "DECREFED" 1

# gc: orphan a blob of its OWN — h.bin, touched by no pin — then sweep it with
# zero grace. Three things this deliberately does not do:
#
#   * reuse a.bin: pre-fix, A1's swallowed failure leaves it a permanent stuck
#     ledger ref (the headline defect), so gc can never reclaim it and the
#     control would be measuring the bug rather than the fixture;
#   * reuse f.bin: `decref-deleted` clears only the ledger, so t6 still LISTS it
#     and gc's blocking-set scan correctly retains it;
#   * assert a global `swept N`: that count moves with unrelated orphans left by
#     earlier pins, and a bare `swept 1` did pass here on the wrong blob.
#
# So: a fresh blob, released with `rm` (which drops the ledger ref AND the
# frontmatter entry), and asserted by its concrete outcome. A `swept 0` run would
# otherwise be a success message for a sweep that never ran — the very shape A5
# pins as a failure.
HH="$(artifact_sha256 h.bin)"
"$ATT" add 9 h.bin --name h.bin >/dev/null 2>&1
"$ATT" rm  9 h.bin              >/dev/null 2>&1
assert_file_exists "control/attach-gc: the orphan exists before the sweep" "$(blob_of "$HH")"
write_config 0
BEFORE="$(commits)"; run_clean "$ATT" gc
ctl "attach-gc" "swept" 1
assert_file_not_exists "control/attach-gc: the orphaned blob was actually reclaimed" \
    "$(blob_of "$HH")"
write_config

BEFORE="$(commits)"; run_clean "$ART" create 9 g.bin --kind report --name g-report
ctl "artifact-create" "Created artifact" 1
printf 'eta payload v2\n' > g2.bin
BEFORE="$(commits)"; run_clean "$ART" update art:t9-report g2.bin
ctl "artifact-update" "current is now" 1
BEFORE="$(commits)"; run_clean "$ART" rm 9 art:t9-report
ctl "artifact-rm" "Removed artifact" 1

# move, unfaulted — the control for A11, and the one that proves its direction
# actually commits: dir → local stages the copied blobs plus the manifest.
"$ART" create 10 f.bin --kind report --name f-report --backend dir >/dev/null 2>&1
BEFORE="$(commits)"; run_clean "$ART" move art:t10-report --to local
ctl "artifact-move" "Moved" 1
assert_contains "control/artifact-move: the manifest now names the target backend" \
    '"local"' "$(git show HEAD:artifacts/manifests/t10-report.json)"

cd "$PROJECT_DIR" || exit 1

echo "=== Part B — static contract guard ==========================================="

# MUTATORS — the closed set of helpers that report failure by RETURNING non-zero
# (so errexit suppression swallows them). Anything that `die`s internally is
# safe by construction and is deliberately NOT listed:
#   attach_meta            thin front over attachment_meta.py; returns its status
#   artifact_manifest      thin front over artifact_manifest.py; returns its status
#   frontmatter_patch.py   invoked directly as `"$py" .../frontmatter_patch.py ...`
#   artifact_backend_put   dispatches to a backend put; local's cp/mv are unchecked
#   artifact_backend_delete  same dispatch; can die on an unknown backend
MUTATORS=(
  'attach_meta'
  'artifact_manifest'
  'frontmatter_patch\.py'
  'artifact_backend_put'
  'artifact_backend_delete'
)

# ALLOWLIST — `<file>:<line>` sites exempted from the rule, seven of them.
#
# This is the guard's ONE judgement seam, and it is deliberately per-site rather
# than a widened ACCEPT_RE: every form below is one the matcher cannot verify, so
# broadening the rule to admit them would admit the unsafe cases too (an
# `if ! m; then warn; fi` alongside the one that dies; a swallowing `|| true`
# alongside a rollback's). Each entry therefore names its evidence.
#
# The bar for adding one: refactor to a recognized form FIRST if you can — that
# is what aitask_fold_mark.sh's `attach_meta rebind` did, trading `|| rc=$?` plus
# a next-line check for `|| die "... $?"`. Only when the shape genuinely cannot
# propagate (a best-effort rollback, a pipeline head, a tail call) does an entry
# belong here, and it must cite why the failure is either carried or harmless.
#
# Note what an entry costs: it pins a LINE NUMBER, so it silently stops matching
# if the file shifts. That is intentional — a stale entry re-exposes its site to
# the guard rather than quietly exempting whatever moved into that line.
ALLOWLIST=(
  # ── Best-effort blob deletes on an already-failing path ────────────────────
  # Each runs inside a rollback, at most a line or two before `die`: there is
  # nothing left to abort, and a blob left behind is unreferenced and reclaimed
  # by `ait attach gc`. Every one carries an explicit `|| true` in the source, so
  # the intent reads as a decision rather than as the t1675 swallow. `|| true` is
  # deliberately NOT an accepted form globally — it neither terminates nor
  # propagates — so each site is exempted individually and visibly here.
  ".aitask-scripts/aitask_attach.sh:315"      # _attach_rollback_add
  ".aitask-scripts/aitask_artifact.sh:324"    # _artifact_rollback_create
  ".aitask-scripts/aitask_artifact.sh:386"    # _artifact_update_txn, commit-failure branch
  ".aitask-scripts/aitask_artifact.sh:480"    # _artifact_move_txn, commit-failure branch

  # Pipeline HEAD, not a swallow: every script here runs under `set -o pipefail`,
  # so the pipeline's status carries this failure to the function's return value,
  # and both callers of _artifact_manifest_backend check it with `|| die`. The
  # guard cannot see a non-final pipeline position — its documented blind spot.
  ".aitask-scripts/aitask_artifact.sh:163"

  # TAIL position: this is the last command of _attach_gc_blocking_hashes, so its
  # status IS the function's return value, and the sole caller checks it —
  # `blocking="$(_attach_gc_blocking_hashes)" || die` in _attach_gc_txn, whose
  # comment records that the `|| die` is load-bearing for exactly this reason.
  ".aitask-scripts/aitask_attach.sh:576"

  # `if ! remaining="$(artifact_manifest referenced-hashes)"; then` — the ONE
  # `if !` in the tree. Its branch is genuinely terminating: it restores the task
  # file and manifest from HEAD and then dies (aitask_artifact.sh:580-584), so
  # the failure is handled, not observed. `if !` is NOT an accepted form: the
  # guard cannot see whether a branch ends in `die` or in a bare `warn`, and the
  # bare-warn version is exactly the t1675 bug. Exempted here, by line, so the
  # verification stays a human-checked citation instead of a blanket rule.
  ".aitask-scripts/aitask_artifact.sh:572"
)

# ACCEPTED status handlers — forms whose failure handling is visible in the line
# ITSELF: it either terminates, propagates, or opens an explicit failure branch.
#
#   `|| die ...`  `|| { ...; die; }`   terminates
#   `|| return $?`  `|| return <1-9..>`  propagates a non-zero status
#
# Everything else is rejected, and each rejection is the same failure mode —
# execution continues past a failed mutator and a later command returns success:
#   `&&`, a bare `if m; then`     the failure path is simply unwritten
#   `|| <var>=$?`                 the check, if any, is on another line
#   `|| return "$anyvar"`         `rc=0; m || return "$rc"` returns SUCCESS
#   `|| return 0`                 a pervasive idiom elsewhere in this tree
#   `|| true`                     an explicit swallow — see the ALLOWLIST
#   `if ! m; then ...; fi`        `if ! m; then warn "failed"; fi` branches on
#                                 failure and STILL continues; the guard cannot
#                                 see whether the branch terminates, so it must
#                                 not assume it does. The tree's single `if !`
#                                 site is allowlisted individually, with the
#                                 line numbers of the die that ends its branch.
# PYTHON regex syntax (guard_scan compiles it with `re`) — do NOT use POSIX
# classes like [[:space:]] here: Python reads that as a nested set, matches
# nothing, and the guard then flags every correctly-guarded line in the tree.
ACCEPT_RE='\|\|\s*(\{[^}]*)?die|\|\|\s*return\s+(\$\?|[1-9][0-9]*)\s*$'

# guard_scan ROOT — emit "<relpath>:<line>:<text>" for each unguarded mutator
# inside a with_attach_lock callback closure under ROOT/.aitask-scripts.
#
# Detection scope, stated because a guard that overclaims is worse than one with
# a known boundary:
#   * Callbacks are discovered from `with_attach_lock <fn>` call sites, then the
#     closure is grown to a FIXPOINT over same-file functions named in an
#     in-closure body — that is what reaches the transitively-called helper shape
#     that caused t1668 (_fold_merge_one, three frames below the callback).
#   * A logical line is a physical line plus its `\`-continuations, so the
#     accepted handler may sit on the continuation.
#   * NOT covered: a mutator reached through a function defined in ANOTHER file;
#     a mutator not in MUTATORS; and a mutator in a non-final pipeline position,
#     whose failure reads as an empty result rather than a non-zero status. That
#     last one is exactly why aitask_attach.sh's `attach_meta refs | grep -qxF`
#     was hoisted out of its `if` by hand rather than left to this guard.
guard_scan() {
  python3 - "$1" "${MUTATORS[*]}" "$ACCEPT_RE" "${ALLOWLIST[*]:-}" <<'PY'
import os, re, sys

root, mutators_s, accept_re, allow_s = sys.argv[1:5]
mutators = mutators_s.split()
accept = re.compile(accept_re)
allow = set(allow_s.split())
mutator_re = re.compile(r'(?<![A-Za-z0-9_.])(' + '|'.join(mutators) + r')(?![A-Za-z0-9_])')
func_def_re = re.compile(r'^([A-Za-z_][A-Za-z0-9_]*)\s*\(\)\s*\{')
call_re = re.compile(r'^\s*with_attach_lock\s+([A-Za-z_][A-Za-z0-9_]*)')

def logical_lines(lines):
    """Yield (1-based start line, joined text) folding `\\` continuations."""
    i = 0
    while i < len(lines):
        start, buf = i, lines[i].rstrip('\n')
        while buf.endswith('\\') and i + 1 < len(lines):
            i += 1
            buf = buf[:-1] + ' ' + lines[i].rstrip('\n')
        yield start + 1, buf
        i += 1

def functions(lines):
    """name -> (start_idx, end_idx) for `name() {` ... column-0 `}`."""
    out, cur, start = {}, None, None
    for i, ln in enumerate(lines):
        m = func_def_re.match(ln)
        if m and cur is None:
            cur, start = m.group(1), i
        elif cur is not None and ln.rstrip('\n') == '}':
            out[cur] = (start, i)
            cur = None
    return out

violations = []
scripts = os.path.join(root, '.aitask-scripts')
for dirpath, _, names in os.walk(scripts):
    for name in sorted(names):
        if not name.endswith('.sh'):
            continue
        path = os.path.join(dirpath, name)
        rel = os.path.relpath(path, root)
        with open(path, encoding='utf-8', errors='replace') as fh:
            lines = fh.readlines()

        seeds = {m.group(1) for ln in lines for m in [call_re.match(ln)] if m}
        if not seeds:
            continue
        funcs = functions(lines)
        # Fixpoint: add any same-file function named inside an in-closure body.
        closure = {f for f in seeds if f in funcs}
        changed = True
        while changed:
            changed = False
            for f in list(closure):
                a, b = funcs[f]
                body = ''.join(lines[a:b + 1])
                for cand in funcs:
                    if cand in closure:
                        continue
                    if re.search(r'(?<![A-Za-z0-9_])' + re.escape(cand) + r'(?![A-Za-z0-9_])', body):
                        closure.add(cand)
                        changed = True

        for f in sorted(closure):
            a, b = funcs[f]
            for lineno, text in logical_lines(lines[a:b + 1]):
                lineno += a
                stripped = text.strip()
                if stripped.startswith('#'):
                    continue
                if not mutator_re.search(text):
                    continue
                if f'{rel}:{lineno}' in allow:
                    continue
                # A mutator inside a $( ) within [[ ]] has its status DISCARDED,
                # even on a line that carries `|| die`. Flag it regardless.
                in_test_subst = re.search(r'\[\[.*\$\(.*(' + '|'.join(mutators) + r')', text)
                if in_test_subst or not accept.search(text):
                    violations.append(f'{rel}:{lineno}:{stripped}')

for v in violations:
    print(v)
PY
}

# --- B1: the real tree is clean ---------------------------------------------
violations="$(guard_scan "$PROJECT_DIR")"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
  PASS=$((PASS + 1))
else
  FAIL=$((FAIL + 1))
  echo "FAIL: unguarded mutator(s) inside a with_attach_lock callback:"
  printf '  UNGUARDED: %s\n' "$violations"
  echo "  -> add an explicit '|| die \"...\"' (errexit is suppressed in there;"
  echo "     see the CALLBACK CONTRACT in lib/attachment_lock.sh)."
fi

echo "=== Part C — negative controls (the matcher itself) =========================="

FX="$TMP/fx"; mkdir -p "$FX/.aitask-scripts"
cat > "$FX/.aitask-scripts/probe.sh" <<'SH'
#!/usr/bin/env bash
# Accepted forms — must NOT be flagged.
_ok_die() {
    attach_meta incref "$h" "$id" || die "boom"
}
_ok_die_block() {
    artifact_manifest create "$h" "$x" || { rollback; die "boom"; }
}
_ok_return_status() {
    attach_meta decref "$h" "$id" || return $?
}
_ok_return_literal() {
    artifact_backend_put "$h" "$f" || return 1
}
_ok_continuation() {
    attach_meta incref "$h" "$id" \
        || die "boom on a continuation line"
}
# Rejected forms — MUST be flagged.
_bad_bare() {
    attach_meta incref "$h" "$id"
}
_bad_andand() {
    attach_meta incref "$h" "$id" && log_ok
}
_bad_if_then() {
    if artifact_manifest create "$h" "$x"; then record_metadata; fi
}
# Branches on failure and STILL continues — the reason `if !` is not an accepted
# form. A guard that trusted `if !` would wave this through while the callback
# runs on to a false success, which is t1675's bug verbatim.
_bad_if_not_warn() {
    if ! attach_meta incref "$h" "$id"; then warn "failed"; fi
}
_bad_return_var() {
    rc=0
    attach_meta incref "$h" "$id" || return "$rc"
}
_bad_return_zero() {
    attach_meta decref "$h" "$id" || return 0
}
_bad_capture_no_check() {
    refs="$(attach_meta refs "$h")" || rc=$?
}
_bad_test_subst() {
    [[ -z "$(artifact_manifest get "$handle")" ]] || die "exists"
}
# Reached only transitively from the callback — the t1668 shape.
_bad_transitive() {
    "$py" "$SCRIPT_DIR/lib/frontmatter_patch.py" append "$tf" attachments "hash=$h"
}
_probe_txn() {
    _ok_die
    _ok_die_block
    _ok_return_status
    _ok_return_literal
    _ok_continuation
    _bad_bare
    _bad_andand
    _bad_if_then
    _bad_if_not_warn
    _bad_return_var
    _bad_return_zero
    _bad_capture_no_check
    _bad_test_subst
    _bad_transitive
}
# NOT reachable from any callback — must NOT be flagged.
_unreachable() {
    attach_meta incref "$h" "$id"
}
with_attach_lock _probe_txn
SH

neg="$(guard_scan "$FX")"

# Every REJECTED shape must appear; every ACCEPTED shape must not. The violation
# text is the stripped logical line, so asserting on a distinctive fragment of
# each fixture line pins exactly which shape was (or was not) matched.
assert_eq "control: exactly the 9 rejected shapes are flagged" \
  "9" "$(printf '%s\n' "$neg" | grep -c 'probe\.sh' || true)"

assert_contains "control: '&& log_ok' is flagged"                  '&& log_ok'             "$neg"
assert_contains "control: 'if mutator; then' is flagged"           'record_metadata'       "$neg"
assert_contains "control: 'if ! mutator; then warn' is flagged"    'then warn "failed"'    "$neg"
assert_contains "control: '|| return \$rc' is flagged"             'return "$rc"'          "$neg"
assert_contains "control: '|| return 0' is flagged"                'return 0'              "$neg"
assert_contains "control: '|| rc=\$?' without a check is flagged"  'refs="$(attach_meta refs "$h")" || rc=$?' "$neg"
assert_contains "control: \$( ) inside [[ ]] is flagged"           '[[ -z "$(artifact_manifest get' "$neg"
assert_contains "control: a transitively-called helper is flagged" \
  'frontmatter_patch.py" append "$tf"' "$neg"

assert_not_contains "control: '|| die' is accepted"                '|| die "boom"'         "$neg"
assert_not_contains "control: '|| { ...; die; }' is accepted"      '{ rollback; die'       "$neg"
assert_not_contains "control: '|| return \$?' is accepted"         'return $?'             "$neg"
assert_not_contains "control: '|| return 1' is accepted"           'return 1'              "$neg"
assert_not_contains "control: a die on a continuation line is accepted" \
  'boom on a continuation line' "$neg"

# _bad_bare and _unreachable are byte-identical lines, so only the LINE NUMBER
# distinguishes "flagged because it is in the closure" from "not flagged because
# nothing reaches it". Assert on file:line, not on text.
bare_ln="$(grep -n 'attach_meta incref "\$h" "\$id"$' "$FX/.aitask-scripts/probe.sh" | head -1 | cut -d: -f1)"
unreach_ln="$(grep -n 'attach_meta incref "\$h" "\$id"$' "$FX/.aitask-scripts/probe.sh" | tail -1 | cut -d: -f1)"
assert_contains "control: the bare mutator inside the closure is flagged" \
  "probe.sh:${bare_ln}:" "$neg"
assert_not_contains "control: the identical line outside the closure is NOT flagged" \
  "probe.sh:${unreach_ln}:" "$neg"

# --- C2: the allowlist suppresses exactly one line, not a shape --------------
ALLOWLIST=( ".aitask-scripts/probe.sh:${bare_ln}" )
neg_allow="$(guard_scan "$FX")"
assert_eq "control: an allowlist entry removes exactly one violation" \
  "8" "$(printf '%s\n' "$neg_allow" | grep -c 'probe\.sh' || true)"
assert_not_contains "control: the allowlisted line itself is gone" \
  "probe.sh:${bare_ln}:" "$neg_allow"
assert_contains "control: the same shape one line away is still flagged" \
  '&& log_ok' "$neg_allow"
ALLOWLIST=()

echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
