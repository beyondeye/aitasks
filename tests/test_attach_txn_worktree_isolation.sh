#!/usr/bin/env bash
# test_attach_txn_worktree_isolation.sh — the t1698 transaction boundary.
#
# `ait attach` / `ait artifact` stage whole paths, so a transaction whose paths
# are already dirty either ABSORBS the user's in-flight edit into an `ait:`
# commit (defect 1) or DESTROYS it on rollback (defect 2), and an abort after a
# mutation but before the commit leaves the ledger drifted (defect 3). This file
# pins the fix: a fail-closed dirty-path preflight, and a rollback that fires
# from every abort path and restores pre-transaction BYTES AND INDEX ENTRIES
# rather than HEAD.
#
# Invariant under test: a transaction either commits completely, or restores its
# own paths to their pre-transaction bytes and index entries.
#
# Sections:
#   L  — lock hygiene on the abort path (pre-phase characterization; passes
#        pre-fix, and fails the moment the new EXIT-trap chain leaks the lock)
#   P  — preflight refusals, and the narrowings that must still succeed
#   R  — abort-path rollback state, one pin per rollback-hook shape
#
# Fault injection uses the documented AIT_PYTHON override (python_resolve.sh
# resolution order, rung 1) with the passthrough shim t1675 introduced.
#
# ─── PRE-FIX CONTROL STATUS (measured, per pin) ──────────────────────────────
#
# Every pin was run against a pre-fix tree (`git archive HEAD` of the commit
# before t1698 landed). Recorded here because "it fails pre-fix" is a claim, and
# three pins do NOT — for two different and legitimate reasons.
#
#   DISCRIMINATING — fail pre-fix, pass post-fix:
#     P1a P1b P2 P3a P3b P4a P4b P5   the preflight refusals (no preflight existed)
#     R1 R2 R4 R5 R6 R7               post-mutation rollback state
#     R3                              gc's destructive rollback (see below)
#     D2                              the recorded defect-2 case
#     H1                              the forced hook-failure report
#     N1 N2                           (fail pre-fix only as fixture cascade — see below)
#
#   NON-DISCRIMINATING BY CONSTRUCTION — regression guards, not fix proofs:
#     R8   `artifact rm` faulted at referenced-hashes. Pre-fix that branch
#          ALREADY had an inline rollback (`task_git reset` + `checkout` from
#          HEAD), and on a clean fixture a HEAD restore and a snapshot restore
#          are byte-identical. Measured, both trees: `rc=1, manifest_exists=yes,
#          porcelain=[]`. It guards the txn_abort conversion of that branch; it
#          does not prove a defect fixed. Do not "strengthen" it with a dirty
#          path — the preflight refuses before the branch is reached.
#     N3 N4  The "must still succeed" narrowings. They cannot fail pre-fix
#          because pre-fix has no preflight to over-refuse. Their whole job is
#          to catch an over-refusal introduced BY this change.
#
# WHY THE WHOLE-FILE PRE-FIX RUN IS NOT THE CONTROL OF RECORD: the fixture is
# linear, so the first pre-fix pin that fails to refuse actually MUTATES state
# the later pins build on, and everything after it diverges. R3 "passed" that
# run for exactly that reason. Re-measured in an ISOLATED pre-fix fixture it
# discriminates sharply:
#
#     PRE-FIX  gc rc=1  blobs 2 -> 1  porcelain=[ D <blob>; D <meta>;]
#     FIXED    gc rc=1  blobs 2 -> 2  porcelain=[]
#
# i.e. pre-fix a blob is DELETED AND NOT RESTORED and the tree is left with
# uncommitted deletions — defect 3, live. A per-pin control belongs in a fresh
# fixture; a whole-file rerun is a smoke test, not evidence.
#
# Run: bash tests/test_attach_txn_worktree_isolation.sh
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ATT="$PROJECT_DIR/.aitask-scripts/aitask_attach.sh"
ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
REAL_PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"

TMP="$(mktemp -d)"
cleanup() { chmod -R u+w "$TMP" 2>/dev/null || true; rm -rf "$TMP"; }
trap cleanup EXIT

# `chmod a-w` is how the forced-failure pins below make a restore fail. Root
# ignores the write bit, so under a root runner that forcing silently does
# nothing and every such pin would pass VACUOUSLY. Skip them visibly instead.
CAN_FORCE_PERM=true
[[ "$(id -u)" -eq 0 ]] && CAN_FORCE_PERM=false

# ── The fault-injecting python shim (t1675; reused verbatim) ─────────────────
# Fails when argv names $AIT_FAULT_SCRIPT AND contains $AIT_FAULT_SUBCMD, on the
# $AIT_FAULT_NTH matching call (default 1); passes everything else through. The
# occurrence index is what lets a fault land AFTER earlier mutations in a loop,
# which is the only way to reach a rollback hook's non-trivial restore path.
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
            # Optional side effect, run at the INSTANT of the fault. The forced
            # hook-failure pin needs a directory to become unwritable BETWEEN a
            # sweep's delete and its restore; a chmod before the run would block
            # the delete itself and the hook would never be reached.
            [[ -n "\${AIT_FAULT_PRE_CMD:-}" ]] && eval "\$AIT_FAULT_PRE_CMD"
            echo "INJECTED FAULT: \$AIT_FAULT_SCRIPT \$AIT_FAULT_SUBCMD (call \$n)" >&2
            exit 3
        fi
    fi
fi
exec "$REAL_PY" "\$@"
EOF
chmod +x "$SHIM"

# run_faulted <script> <subcmd> <nth> -- <cmd...>
# $AIT_FAULT_PRE_CMD (optional, set by the caller) runs inside the shim at the
# moment the fault fires — see the shim comment.
run_faulted() {
    local script="$1" subcmd="$2" nth="$3"; shift 4   # shift past the "--"
    : > "$TMP/faultcount"
    RF_OUT="$(AIT_PYTHON="$SHIM" AIT_FAULT_SCRIPT="$script" AIT_FAULT_SUBCMD="$subcmd" \
              AIT_FAULT_NTH="$nth" AIT_FAULT_COUNT="$TMP/faultcount" \
              AIT_FAULT_PRE_CMD="${AIT_FAULT_PRE_CMD:-}" \
              "$@" 2>"$TMP/stderr")"
    RF_RC=$?
    RF_ERR="$(cat "$TMP/stderr")"
}

# run_clean -- the same shim with NO fault armed (passthrough control).
run_clean() {
    RF_OUT="$(AIT_PYTHON="$SHIM" "$@" 2>"$TMP/stderr")"
    RF_RC=$?
    RF_ERR="$(cat "$TMP/stderr")"
}

commits() { git rev-list --count HEAD; }

# ── Fixture: legacy-mode repo (no .aitask-data -> task_git is plain git) ─────
REPO="$TMP/repo"
mkdir -p "$REPO/aitasks/metadata"
cd "$REPO" || exit 1
git init -q; git config user.email t@t.t; git config user.name tester
mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s body.\n' \
        "$1" > "aitasks/$1.md"
}
for t in t5_demo t6_other t7_third t8_fourth t9_fifth t10_sixth t11_seventh t12_eighth; do
    mk_task "$t"
done
# One distinct payload per pin: a pre-existing local blob makes a commit stage
# nothing for that path, which is exactly how a pin stops discriminating.
i=0
for p in alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu; do
    i=$((i + 1)); printf '%s payload\n' "$p" > "p${i}.bin"
done
DIRSTORE="$TMP/dirstore"; mkdir -p "$DIRSTORE"
printf 'artifacts:\n  backends:\n    dir:\n      path: %s\n' "$DIRSTORE" \
    > aitasks/metadata/project_config.yaml
git add -A; git commit -q -m init

# Pure libs, for in-test hashing / shard paths.
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/terminal_compat.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_utils.sh"

meta_of() { printf 'attachments/meta/%s.json\n' "$(artifact_shard_path "$(artifact_sha256 "$1")")"; }
blob_of() { printf 'attachments/blobs/%s\n'     "$(artifact_shard_path "$(artifact_sha256 "$1")")"; }

echo "=== L — lock hygiene on the abort path ======================================"

# The global attach lock must be released when a transaction dies MID-BODY, not
# only when its callback returns. This passes on the pre-fix tree —
# registry_lock_acquire's own EXIT trap does it — and that is the point: the
# t1698 rollback CHAINS onto that same trap, and a bare `trap ... EXIT` inside a
# callback would replace the lock-release handler and leak the mutex on every
# aborted verb. Written before the change so it fails the moment the chain is
# wrong. tests/test_attach_local_backend.sh section I covers only the SUCCESS
# path, which no trap edit can break.
LOCKDIR="attachments/.attach.lock"

BEFORE="$(commits)"
run_faulted frontmatter_patch.py append 1 -- "$ATT" add 5 p1.bin --name p1.bin
assert_exit_nonzero_rc "L1: faulted attach add exits non-zero" "$RF_RC"
assert_dir_not_exists "L1: attach lock released after a mid-body die" "$LOCKDIR"

run_faulted frontmatter_patch.py append 1 -- \
    "$ART" create 6 p2.bin --kind report --name p2-report
assert_exit_nonzero_rc "L2: faulted artifact create exits non-zero" "$RF_RC"
assert_dir_not_exists "L2: attach lock released after a mid-body die (artifact)" "$LOCKDIR"

# A second verb must still be able to acquire the lock afterwards — the property
# a leaked mutex actually breaks. Uses its own task and payload so it cannot
# depend on whether either pin above behaved as fixed or as broken.
run_clean "$ATT" add 7 p3.bin --name p3.bin
assert_exit_zero_rc "L3: a later verb still acquires the lock" "$RF_RC"
assert_contains "L3: and reports success" "Attached" "$RF_OUT"
assert_dir_not_exists "L3: no lock lingers after a successful op" "$LOCKDIR"

echo "=== P — the dirty-path preflight ==========================================="

# helpers -------------------------------------------------------------------
dirty() { printf 'USER EDIT IN FLIGHT\n' >> "$1"; }          # unstaged, plain text

# dirty_json -- dirt for a path the verb PARSES before it reaches the preflight.
# Appending prose to a meta/manifest JSON makes it malformed, so the verb dies
# on the parse instead ("invalid JSON ... repair or remove it") and the pin would
# be measuring the wrong refusal. A trailing newline is a real byte change that
# git sees, and every JSON parser tolerates it.
dirty_json() { printf '\n' >> "$1"; }

# reset FIRST, then checkout: `git checkout -- <path>` restores from the INDEX,
# so on a STAGED edit it copies the dirty version straight back and the file
# stays dirty for the next pin.
undirty() {
    git reset -q HEAD -- "$1" 2>/dev/null || true
    git checkout -q -- "$1" 2>/dev/null || true
}

# fp <path> -- byte fingerprint. Used instead of `$(cat …)` because command
# substitution strips trailing newlines, which is exactly the byte dirty_json
# adds — the comparison would then hold even if the file had been rewritten.
fp() { artifact_sha256 "$1"; }

# refuse <desc> <success-substring> <path-that-must-survive> -- the five
# properties of a refusal: non-zero, no success message, nothing committed, the
# dirty file byte-identical AND still in the same index state, and a message
# that names the path and the remedy. $BEFORE/$SNAP/$SNAP_PORC hold the
# pre-command state.
refuse() {
    local desc="$1" msg="$2" path="$3"
    assert_exit_nonzero_rc "$desc: refuses"                "$RF_RC"
    assert_not_contains    "$desc: prints no success"      "$msg" "$RF_OUT"
    assert_eq              "$desc: commits nothing"        "0" "$(( $(commits) - BEFORE ))"
    assert_eq              "$desc: the dirty file is byte-identical" "$SNAP" "$(fp "$path")"
    assert_eq              "$desc: and its index state is unchanged" \
        "$SNAP_PORC" "$(git status --porcelain -- "$path")"
    assert_contains        "$desc: names the path"         "$path" "$RF_ERR"
    assert_contains        "$desc: names the remedy"       "./ait git commit --" "$RF_ERR"
}

# snap_state <path> -- capture what `refuse` will compare against.
snap_state() { SNAP="$(fp "$1")"; SNAP_PORC="$(git status --porcelain -- "$1")"; BEFORE="$(commits)"; }

# ── P1. attach add, dirty task file — UNSTAGED then STAGED ──────────────────
"$ATT" add 5 p4.bin --name p4.bin >/dev/null 2>&1        # a real attachment first
dirty aitasks/t5_demo.md
snap_state aitasks/t5_demo.md
run_clean "$ATT" add 5 p5.bin --name p5.bin
refuse "P1a: attach add / dirty task file (unstaged)" "Attached" aitasks/t5_demo.md

git add aitasks/t5_demo.md                               # same edit, now STAGED
snap_state aitasks/t5_demo.md
run_clean "$ATT" add 5 p5.bin --name p5.bin
refuse "P1b: attach add / dirty task file (staged)" "Attached" aitasks/t5_demo.md
undirty aitasks/t5_demo.md

# ── P2. attach rm, dirty meta JSON ──────────────────────────────────────────
META4="$(meta_of p4.bin)"
dirty_json "$META4"
snap_state "$META4"
run_clean "$ATT" rm 5 p4.bin
refuse "P2: attach rm / dirty meta JSON" "Removed attachment" "$META4"
undirty "$META4"

# ── P3. artifact create / rm, dirty task file ───────────────────────────────
dirty aitasks/t9_fifth.md
snap_state aitasks/t9_fifth.md
run_clean "$ART" create 9 p6.bin --kind report --name p6-report
refuse "P3a: artifact create / dirty task file" "Created artifact" aitasks/t9_fifth.md
undirty aitasks/t9_fifth.md

"$ART" create 9 p6.bin --kind report --name p6-report >/dev/null 2>&1
dirty aitasks/t9_fifth.md
snap_state aitasks/t9_fifth.md
run_clean "$ART" rm 9 art:t9-report
refuse "P3b: artifact rm / dirty task file" "Removed artifact" aitasks/t9_fifth.md
undirty aitasks/t9_fifth.md

# ── P4. artifact update / move, dirty MANIFEST ──────────────────────────────
MAN9="artifacts/manifests/t9-report.json"
dirty_json "$MAN9"
snap_state "$MAN9"
run_clean "$ART" update art:t9-report p7.bin
refuse "P4a: artifact update / dirty manifest" "current is now" "$MAN9"

snap_state "$MAN9"
run_clean "$ART" move art:t9-report --to dir
refuse "P4b: artifact move / dirty manifest" "Moved" "$MAN9"
undirty "$MAN9"

# ── P5. attach gc, dirty meta JSON on a SWEEP CANDIDATE ─────────────────────
"$ATT" add 11 p8.bin --name p8.bin >/dev/null 2>&1
"$ATT" rm  11 p8.bin >/dev/null 2>&1                     # -> zero refs, orphaned
printf 'attachments_gc_grace: 0s\n' >> aitasks/metadata/project_config.yaml
git add aitasks/metadata/project_config.yaml; git commit -q -m "gc grace 0"
META8="$(meta_of p8.bin)"
dirty_json "$META8"
snap_state "$META8"
run_clean "$ATT" gc
refuse "P5: attach gc / dirty meta JSON on a sweep candidate" "swept" "$META8"
assert_file_exists "P5: and the blob was NOT deleted" "$(blob_of p8.bin)"
undirty "$META8"

echo "=== P (narrowings) — what must STILL succeed ================================"

# succeed <desc> <success-substring> <expected-commits> <bystander-path>
succeed() {
    local desc="$1" msg="$2" want="$3" path="${4:-}"
    assert_exit_zero_rc "$desc: succeeds"           "$RF_RC"
    assert_contains     "$desc: reports success"    "$msg" "$RF_OUT"
    assert_eq           "$desc: makes $want commit(s)" "$want" "$(( $(commits) - BEFORE ))"
    [[ -z "$path" ]] && return 0
    assert_eq "$desc: the dirty bystander is byte-identical" "$SNAP" "$(fp "$path")"
    assert_eq "$desc: and still dirty" "$SNAP_PORC" "$(git status --porcelain -- "$path")"
}

# ── N1/N2. update and move never stage a TASK file (the stable-handle split).
# Asserted, not assumed: checking a path the verb does not stage would refuse a
# valid operation.
dirty aitasks/t9_fifth.md
snap_state aitasks/t9_fifth.md
run_clean "$ART" update art:t9-report p7.bin
succeed "N1: artifact update with a dirty TASK file (manifest clean)" \
    "current is now" 1 aitasks/t9_fifth.md

snap_state aitasks/t9_fifth.md
run_clean "$ART" move art:t9-report --to dir
succeed "N2: artifact move with a dirty TASK file" "Moved" 1 aitasks/t9_fifth.md
undirty aitasks/t9_fifth.md

# ── N3. decref-deleted with two doomed tasks sharing ONE attachment — the
# dedup case. With a single `seen` set the second txn_require_clean would see
# the transaction's OWN first decref as dirt and refuse a valid operation.
"$ATT" add 11 p9.bin --name p9.bin >/dev/null 2>&1
"$ATT" add 12 p9.bin --name p9.bin >/dev/null 2>&1
BEFORE="$(commits)"
run_clean "$ATT" decref-deleted 11 12
succeed "N3: decref-deleted, two doomed tasks sharing one attachment" "DECREFED" 1
assert_eq "N3: both refs were released" "" "$(AIT_PYTHON="$SHIM" "$ATT" gc >/dev/null 2>&1; \
    "$REAL_PY" "$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.py" \
    --meta-dir attachments/meta refs "$(artifact_sha256 p9.bin)" 2>/dev/null)"

# ── N4. `ait fold` with attachments and its OWN dirty task files. Fold writes
# task files in Steps 4-5 and commits at Step 6, so at its Step 5b attach
# transaction they are LEGITIMATELY dirty with the fold's own work. It reaches
# _fold_attach_txn, never the eight verb paths — which is why the preflight
# lives at the verbs and never in the seam. A preflight in with_attach_lock,
# _attach_commit or the shared helpers would break `ait fold` outright.
"$ATT" add 6 p10.bin --name p10.bin >/dev/null 2>&1
BEFORE="$(commits)"
FOLD_OUT="$( "$PROJECT_DIR/.aitask-scripts/aitask_fold_mark.sh" \
    --commit-mode fresh 7 6 2>&1 )"; FOLD_RC=$?
assert_exit_zero_rc "N4: ait fold with attachments and its own dirty task files" "$FOLD_RC"
assert_contains "N4: the fold marked the folded task" "FOLDED:6" "$FOLD_OUT"
assert_eq "N4: and committed once" "1" "$(( $(commits) - BEFORE ))"

echo "=== R — abort-path rollback state, one pin per hook shape =================="

# t1675's pins assert exit status, the absence of a success message, and the
# commit count; none of them looks at what is left ON DISK (its header says so).
# So a rollback hook that restores the wrong thing — or nothing — passes that
# suite. Every pin below adds the state assertion: the worktree AND the backend
# store byte-identical to their pre-command condition.
#
# Two of these need an occurrence index or a multi-item fixture to reach the
# hook at all: a fault on the FIRST item aborts before any deletion, so the
# hook's non-trivial restore path is never entered and the pin passes vacuously.

new_task() { mk_task "$1"; git add "aitasks/$1.md"; git commit -q -m "fixture: $1"; }
payload()  { printf '%s payload for R\n' "$1" > "$1.bin"; }
dir_blob() { printf '%s/%s\n' "$DIRSTORE" "$(artifact_shard_path "$(artifact_sha256 "$1")")"; }
porc_all() { git status --porcelain; }

for t in t20_ra t21_rb t22_rc t23_rd t24_re t25_rf t26_rg t27_rh t28_ri; do new_task "$t"; done
for b in ra rb rc rd re rf rg rh ri rj rk; do payload "$b"; done
git add -A; git commit -q -m "fixture: R payloads"

# state <path...> -- fingerprint a set of paths plus the whole porcelain, so a
# pin catches a lost index entry as well as changed bytes.
state() { local f; for f in "$@"; do printf '%s ' "$(fp "$f" 2>/dev/null || echo MISSING)"; done; porc_all; }

# ── R1. attach add ← frontmatter_patch.py append (hook: local blob delete) ──
"$ATT" add 20 ra.bin --name ra.bin >/dev/null 2>&1        # committed baseline
R1_STATE="$(state aitasks/t20_ra.md)"; BEFORE="$(commits)"
run_faulted frontmatter_patch.py append 1 -- "$ATT" add 20 rb.bin --name rb.bin
assert_exit_nonzero_rc "R1: faulted attach add exits non-zero" "$RF_RC"
assert_not_contains "R1: prints no success" "Attached" "$RF_OUT"
assert_eq "R1: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_file_not_exists "R1: the blob it created is gone"     "$(blob_of rb.bin)"
assert_file_not_exists "R1: the meta JSON it created is gone" "$(meta_of rb.bin)"
assert_eq "R1: the task file and index are unchanged" "$R1_STATE" "$(state aitasks/t20_ra.md)"

# ── R2. attach rm ← frontmatter_patch.py remove (snapshot only, no blobs) ───
# The decref has ALREADY landed when the fault hits — this is defect 3, the
# residual ledger drift t1675 deliberately left behind.
META_RA="$(meta_of ra.bin)"
R2_STATE="$(state aitasks/t20_ra.md "$META_RA")"; BEFORE="$(commits)"
run_faulted frontmatter_patch.py remove 1 -- "$ATT" rm 20 ra.bin
assert_exit_nonzero_rc "R2: faulted attach rm exits non-zero" "$RF_RC"
assert_eq "R2: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_eq "R2: the decref was rolled back — meta JSON and task file unchanged" \
    "$R2_STATE" "$(state aitasks/t20_ra.md "$META_RA")"
assert_contains "R2: the attachment is still listed" "ra.bin" "$("$ATT" ls 20 2>&1)"

# ── R3. attach gc ← attachment_meta.py refs, NTH=2 (hook: HEAD blob restore) ─
# THE DESTRUCTIVE ONE. Two orphans, so candidate #1 is already deleted when the
# fault lands on #2 — a fault on the first would abort before any deletion and
# the hook's restore path would never run.
"$ATT" add 21 rc.bin --name rc.bin >/dev/null 2>&1
"$ATT" add 22 rd.bin --name rd.bin >/dev/null 2>&1
"$ATT" rm  21 rc.bin >/dev/null 2>&1
"$ATT" rm  22 rd.bin >/dev/null 2>&1
R3_STATE="$(state "$(blob_of rc.bin)" "$(blob_of rd.bin)" "$(meta_of rc.bin)" "$(meta_of rd.bin)")"
BEFORE="$(commits)"
run_faulted attachment_meta.py refs 2 -- "$ATT" gc
assert_exit_nonzero_rc "R3: faulted gc exits non-zero" "$RF_RC"
assert_not_contains "R3: prints no sweep summary" "swept" "$RF_OUT"
assert_eq "R3: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_file_exists "R3: the already-swept blob was restored"  "$(blob_of rc.bin)"
assert_file_exists "R3: the second blob is untouched"         "$(blob_of rd.bin)"
assert_eq "R3: every blob and meta is byte-identical, index clean" \
    "$R3_STATE" "$(state "$(blob_of rc.bin)" "$(blob_of rd.bin)" "$(meta_of rc.bin)" "$(meta_of rd.bin)")"

# ── R4. decref-deleted ← attachment_meta.py decref, NTH=2 ───────────────────
"$ATT" add 23 re.bin --name re.bin >/dev/null 2>&1
"$ATT" add 24 rf.bin --name rf.bin >/dev/null 2>&1
R4_STATE="$(state "$(meta_of re.bin)" "$(meta_of rf.bin)")"; BEFORE="$(commits)"
run_faulted attachment_meta.py decref 2 -- "$ATT" decref-deleted 23 24
assert_exit_nonzero_rc "R4: faulted decref-deleted exits non-zero" "$RF_RC"
assert_eq "R4: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_eq "R4: the first task's decref was rolled back" \
    "$R4_STATE" "$(state "$(meta_of re.bin)" "$(meta_of rf.bin)")"

# ── R5. artifact create ← frontmatter_patch.py append ───────────────────────
R5_STATE="$(state aitasks/t25_rf.md)"; BEFORE="$(commits)"
run_faulted frontmatter_patch.py append 1 -- \
    "$ART" create 25 rg.bin --kind report --name rg-report
assert_exit_nonzero_rc "R5: faulted artifact create exits non-zero" "$RF_RC"
assert_eq "R5: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_file_not_exists "R5: the manifest it created is gone" "artifacts/manifests/t25-report.json"
assert_file_not_exists "R5: the blob it created is gone"     "attachments/blobs/$(artifact_shard_path "$(artifact_sha256 rg.bin)")"
assert_eq "R5: the task file and index are unchanged" "$R5_STATE" "$(state aitasks/t25_rf.md)"

# ── R6. artifact update on a NON-LOCAL backend ← set-current ────────────────
# The pin that catches the dropped `&& backend == local` gate: `create` and
# `move` delete a transaction-created blob on ANY backend, `update` used to
# delete only on `local`, so a dir-backend abort leaked the version blob it had
# just stored while reporting "rolled back".
"$ART" create 26 rh.bin --kind mockup --name rh-mock --backend dir >/dev/null 2>&1
MAN26="artifacts/manifests/t26-mockup.json"
R6_STATE="$(state "$MAN26")"; BEFORE="$(commits)"
run_faulted artifact_manifest.py set-current 1 -- "$ART" update art:t26-mockup ri.bin
assert_exit_nonzero_rc "R6: faulted artifact update exits non-zero" "$RF_RC"
assert_not_contains "R6: prints no success" "current is now" "$RF_OUT"
assert_eq "R6: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_file_not_exists "R6: the new version blob is gone from the DIR store" "$(dir_blob ri.bin)"
assert_file_exists     "R6: the pre-existing version blob stays"             "$(dir_blob rh.bin)"
assert_eq "R6: the manifest is byte-identical" "$R6_STATE" "$(state "$MAN26")"

# ── R7. artifact move dir → local ← set-backend (hook: new_hashes loop) ─────
# Direction is load-bearing (t1675 A11): moving *to* dir stages no blob paths,
# so the commit would fail on its own and the pin would stop discriminating.
R7_STATE="$(state "$MAN26")"; BEFORE="$(commits)"
run_faulted artifact_manifest.py set-backend 1 -- "$ART" move art:t26-mockup --to local
assert_exit_nonzero_rc "R7: faulted artifact move exits non-zero" "$RF_RC"
assert_not_contains "R7: prints no success" "Moved" "$RF_OUT"
assert_eq "R7: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_file_not_exists "R7: the blob this move copied to the target is gone" \
    "attachments/blobs/$(artifact_shard_path "$(artifact_sha256 rh.bin)")"
assert_file_exists "R7: the SOURCE blob is not deleted" "$(dir_blob rh.bin)"
assert_contains "R7: the manifest still names the source backend" '"dir"' "$(cat "$MAN26")"
assert_eq "R7: the manifest is byte-identical" "$R7_STATE" "$(state "$MAN26")"

# ── R8. artifact rm ← artifact_manifest.py referenced-hashes ────────────────
# The mid-transaction abort that is NOT a commit failure: the task file is
# already patched and the manifest already deleted when the tree scan dies.
"$ART" create 27 rj.bin --kind report --name rj-report >/dev/null 2>&1
MAN27="artifacts/manifests/t27-report.json"
R8_STATE="$(state aitasks/t27_rh.md "$MAN27")"; BEFORE="$(commits)"
run_faulted artifact_manifest.py referenced-hashes 1 -- "$ART" rm 27 art:t27-report
assert_exit_nonzero_rc "R8: faulted artifact rm exits non-zero" "$RF_RC"
assert_eq "R8: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_file_exists "R8: the deleted manifest was restored" "$MAN27"
assert_eq "R8: the task file and manifest are byte-identical" \
    "$R8_STATE" "$(state aitasks/t27_rh.md "$MAN27")"
assert_contains "R8: the artifact is still listed" "art:t27-report" "$("$ART" ls 27 2>&1)"

echo "=== R (defect 2) — the recorded regression case ============================="

# The measured defect-2 scenario: an in-flight edit on a transaction path, and a
# commit forced to fail so the EXISTING commit-failure rollback runs. Pre-fix
# that rollback was `git checkout -- <path>` (restore from HEAD) and it SILENTLY
# DESTROYED the edit.
#
# The observable property pinned here is the one that matters — the user's line
# survives — not which mechanism saves it. Post-fix it is the PREFLIGHT that
# does: the verb refuses before mutating anything, so the commit is never
# reached. That is the intended design (a rollback can only preserve a dirty
# path it snapshotted, and every staged path is now checked first), and the
# assertion fails on the pre-fix tree either way.
"$ATT" add 28 rk.bin --name rk.bin >/dev/null 2>&1
printf 'USER EDIT IN FLIGHT\n' >> aitasks/t28_ri.md
D2_BEFORE="$(grep -c 'USER EDIT IN FLIGHT' aitasks/t28_ri.md)"
printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit; chmod +x .git/hooks/pre-commit
BEFORE="$(commits)"
run_clean "$ATT" rm 28 rk.bin
rm -f .git/hooks/pre-commit
assert_exit_nonzero_rc "D2: the operation fails" "$RF_RC"
assert_eq "D2: commits nothing" "0" "$(( $(commits) - BEFORE ))"
assert_eq "D2: the user's in-flight edit SURVIVES" \
    "$D2_BEFORE" "$(grep -c 'USER EDIT IN FLIGHT' aitasks/t28_ri.md)"
undirty aitasks/t28_ri.md

echo "=== R (forced hook failure) — a failed BLOB restore is loud ================="

if [[ "$CAN_FORCE_PERM" != true ]]; then
    echo "SKIP: needs an unwritable directory to make a blob restore fail;"
    echo "      running as root, where the write bit is ignored and the forcing"
    echo "      would silently do nothing (the pin would pass vacuously)."
else
    # Every R pin above exercises a hook that SUCCEEDS. This one makes gc's blob
    # restore fail: the blob is deleted by the sweep and cannot be put back, so
    # the rollback is INCOMPLETE and must say so instead of announcing that
    # every mutation was rolled back.
    "$ATT" add 21 rc.bin --name rc.bin >/dev/null 2>&1     # re-ref, then orphan again
    "$ATT" rm  21 rc.bin >/dev/null 2>&1
    "$ATT" add 22 rd.bin --name rd.bin >/dev/null 2>&1
    "$ATT" rm  22 rd.bin >/dev/null 2>&1
    # Make BOTH shard dirs unwritable at the moment the fault fires: whichever
    # blob was candidate #1 has been deleted by then, and its restore now fails.
    # Both, because `attach_meta zero-refcount` fixes the sweep order and the pin
    # must not depend on which one that is.
    SHARD_RC="$(dirname "$(blob_of rc.bin)")"
    SHARD_RD="$(dirname "$(blob_of rd.bin)")"
    BEFORE="$(commits)"
    AIT_FAULT_PRE_CMD="chmod a-w '$SHARD_RC' '$SHARD_RD'" \
        run_faulted attachment_meta.py refs 2 -- "$ATT" gc
    chmod u+w "$SHARD_RC" "$SHARD_RD"
    assert_exit_nonzero_rc "H1: the faulted sweep still exits non-zero" "$RF_RC"
    assert_eq "H1: commits nothing" "0" "$(( $(commits) - BEFORE ))"
    assert_contains "H1: the report says the rollback did not fully restore" \
        "did NOT fully restore" "$RF_ERR"
    assert_contains "H1: it names the blob that did not come back" \
        "attachments/blobs/" "$RF_ERR"
    assert_contains "H1: with its recovery instruction" \
        "git checkout HEAD --" "$RF_ERR"
    assert_not_contains "H1: and NEVER claims a full rollback" \
        "rolled back every mutation" "$RF_ERR"
    git checkout -q -- attachments 2>/dev/null || true
fi

echo "=== F — unchecked filesystem mutations inside a transaction ================="

# The two direct `rm -f`s in the transaction bodies (the manifest delete in
# _artifact_rm_txn, the ledger-meta delete in _attach_gc_txn) run with errexit
# SUPPRESSED, so an unchecked failure did not abort — it fell through to the
# commit. Measured before the guard existed:
#
#   ait artifact rm: rc=0, "Removed artifact ... (manifest deleted)", ONE commit,
#   manifest still on disk AND still in HEAD, task no longer listing it — an
#   orphan manifest no task references and `ait attach gc` can never see past.
#
# That is the t1675 false-success class reappearing INSIDE the t1698 boundary,
# which is why both are `|| die`: dying hands the armed trap the restore.

if [[ "$CAN_FORCE_PERM" != true ]]; then
    echo "SKIP: F needs an unwritable directory to make a delete fail; running as"
    echo "      root, where the write bit is ignored and both cases would pass"
    echo "      vacuously."
else
    # ── F1. artifact rm ← the manifest delete fails ─────────────────────────
    new_task t30_fa
    payload fa
    git add -A; git commit -q -m "fixture: F1"
    "$ART" create 30 fa.bin --kind report --name fa-report >/dev/null 2>&1
    F1_STATE="$(state aitasks/t30_fa.md artifacts/manifests/t30-report.json)"
    BEFORE="$(commits)"
    chmod a-w artifacts/manifests
    run_clean "$ART" rm 30 art:t30-report
    chmod u+w artifacts/manifests
    assert_exit_nonzero_rc "F1: a failed manifest delete aborts the removal" "$RF_RC"
    assert_not_contains "F1: and never claims the manifest was deleted" \
        "manifest deleted" "$RF_OUT"
    assert_eq "F1: commits nothing" "0" "$(( $(commits) - BEFORE ))"
    assert_contains "F1: the artifact is still listed on the task" \
        "art:t30-report" "$("$ART" ls 30 2>&1)"
    assert_eq "F1: the task file and manifest are byte-identical" \
        "$F1_STATE" "$(state aitasks/t30_fa.md artifacts/manifests/t30-report.json)"

    # ── F2. attach gc ← the ledger-meta delete fails ────────────────────────
    # The BLOB delete is checked and succeeds first, so this exercises the
    # rollback restoring a blob the sweep had already removed.
    new_task t31_fb
    payload fb
    git add -A; git commit -q -m "fixture: F2"
    "$ATT" add 31 fb.bin --name fb.bin >/dev/null 2>&1
    "$ATT" rm  31 fb.bin >/dev/null 2>&1
    META_FB="$(meta_of fb.bin)"
    F2_STATE="$(state "$(blob_of fb.bin)" "$META_FB")"
    BEFORE="$(commits)"
    chmod a-w "$(dirname "$META_FB")"
    run_clean "$ATT" gc
    chmod u+w "$(dirname "$META_FB")"
    assert_exit_nonzero_rc "F2: a failed meta delete aborts the sweep" "$RF_RC"
    assert_not_contains "F2: and never reports a sweep" "swept" "$RF_OUT"
    assert_eq "F2: commits nothing" "0" "$(( $(commits) - BEFORE ))"
    assert_file_exists "F2: the already-deleted blob was restored" "$(blob_of fb.bin)"
    assert_eq "F2: blob and meta are byte-identical, index clean" \
        "$F2_STATE" "$(state "$(blob_of fb.bin)" "$META_FB")"
fi

echo "=== F (no-op leak) — a transaction that returns must not strand state ======"

# A callback that `return`s never reaches txn_end, and with_attach_lock's
# release CLEARS the EXIT trap — so a txn_begin placed above a no-op return
# leaks its mktemp snapshot directory on every such call. Both no-op returns
# (`update` when the hash is already current, `move` when the backend already
# matches) must therefore sit ABOVE their txn_begin.
#
# A private TMPDIR is what makes this assertable: the shared /tmp is full of
# other runs' directories.
new_task t32_fc
payload fc
git add -A; git commit -q -m "fixture: no-op"
"$ART" create 32 fc.bin --kind report --name fc-report >/dev/null 2>&1
NOOP_TMP="$TMP/nooptmp"; mkdir -p "$NOOP_TMP"

BEFORE="$(commits)"
RF_OUT="$(TMPDIR="$NOOP_TMP" AIT_PYTHON="$SHIM" "$ART" move art:t32-report --to local 2>&1)"; RF_RC=$?
assert_exit_zero_rc "no-op move succeeds" "$RF_RC"
assert_contains "no-op move reports nothing to do" "nothing to do" "$RF_OUT"
assert_eq "no-op move strands no snapshot directory" "0" \
    "$(find "$NOOP_TMP" -maxdepth 1 -name 'ait_txn_snap_*' | wc -l | tr -d ' ')"

# Clear it first, so this pin is discriminating on its OWN call rather than
# inheriting whatever the move above may have stranded.
rm -rf "$NOOP_TMP"; mkdir -p "$NOOP_TMP"
RF_OUT="$(TMPDIR="$NOOP_TMP" AIT_PYTHON="$SHIM" "$ART" update art:t32-report fc.bin 2>&1)"; RF_RC=$?
assert_exit_zero_rc "no-op update succeeds" "$RF_RC"
assert_contains "no-op update reports already current" "already current" "$RF_OUT"
assert_eq "no-op update strands no snapshot directory" "0" \
    "$(find "$NOOP_TMP" -maxdepth 1 -name 'ait_txn_snap_*' | wc -l | tr -d ' ')"
assert_eq "neither no-op committed anything" "0" "$(( $(commits) - BEFORE ))"

echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
  echo "ALL TESTS PASSED"
else
  echo "SOME TESTS FAILED"
  exit 1
fi
