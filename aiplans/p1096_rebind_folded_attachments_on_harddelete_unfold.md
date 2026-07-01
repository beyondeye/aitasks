---
Task: t1096_rebind_folded_attachments_on_harddelete_unfold.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# t1096 — Rebind folded-origin attachment refs to revived tasks on hard-delete unfold

## Context

When a primary task with `folded_tasks` is **hard-deleted** via `ait board`, the board
*revives* (unfolds) the folded tasks (status → Ready, `folded_into` cleared). t1093 landed
a **conservative guard**: `ait attach decref-deleted --protect-task <folded_id>...` **SKIPS**
decref'ing any primary-owned blob hash that a revived folded task still lists in its
frontmatter — so no blob is orphaned out from under a revived task (no data loss; the gc
cross-check keeps it blocked).

But the skip leaves a **stale ledger ref**: the blob's ref still points at the now-deleted
primary instead of the revived folded task that actually owns it. When that revived task is
later deleted, `decref-deleted` is a no-op for it (its id was never in `refs`), so the stale
primary ref persists forever → the exact orphaned-blob leak t1093 fixes, just deferred.

**Goal:** replace the skip with a proper **rebind-on-unfold** — *move* each folded-origin ref
from the doomed primary to the revived folded task(s) that list it (per-hash `incref survivor`
+ `decref primary`), under the existing attach lock, then stage/commit the touched meta.

## Approach (decided)

**Extend `decref-deleted` in place; change `--protect-task` behaviour from SKIP to REBIND.**
Chosen over a second verb because the board **already** passes each revived `folded_id` as
`--protect-task` and already calls `decref-deleted` first in `_do_delete`, before unfold and
`git rm` (`aitask_board.py:6579`). So the board wiring needs **no functional change** — only
comment/docstring updates. A single verb keeps it one lock transaction / one commit / no
cross-helper ordering. Rejected alternatives: a new `rebind-unfold` verb (more surface, second
board call, second commit, no benefit); reusing the `rebind <old> <new>` ledger verb wholesale
(it moves *every* ref from the primary to the survivor, wrongly handing over the primary's own
non-folded blobs — the move must be **per-hash**, keyed on the survivor's frontmatter hashes).

Flag kept as `--protect-task` (not renamed) to hold blast radius to the helper: the name stays
accurate (it protects the survivor's blobs) and the board call site + its Python contract test
are untouched. The **output token changes** `SKIPPED:…:folded` →
`REBOUND:<doomed_id>:<hash>:<survivor_ids_csv>`; no production code parses these tokens
(verified: only the board — which checks the exit code only — and the two test files).

Two correctness rules, both driven by the review of an earlier draft:

- **Rule A — rebind only a ledger ref the doomed task actually holds** (drift/retry safety).
  The task says "for each of its frontmatter hashes **currently referenced by the primary**".
  Keying only on frontmatter is unsafe: if the ledger is drifted, or a retry has already moved
  the ref, `decref primary` is a harmless no-op but a blind `incref survivor` would **resurrect
  an orphaned blob** (it clears `orphaned_at`, `attachment_meta.py:117`) or **grant ownership
  that was never the primary's to give**. So before rebinding, confirm the doomed id is in the
  ledger `refs` for that hash. This also makes the op self-correcting across the board's
  two-commit retry: fresh state (`refs={30}`) → rebind; already-done (`refs={31}`) → skip, no
  spurious incref; partially-done (`refs={30,31}` after an incref-then-crash) → complete it.

- **Rule B — unresolved `--protect-task` id is FATAL** (fail-closed under rebind semantics).
  Under the old guard, an unresolvable protected id merely dropped a hash from the guard set.
  Under rebind the protected id **is the intended new owner**; if the board hands us a revived
  `folded_id` whose file cannot be read, silently skipping it would decref/orphan the
  primary-owned hashes as if no survivor existed — the very data-loss t1096 prevents. The board
  revives (does not delete) these tasks, so their files MUST exist at decref time; an
  unresolvable one is an anomaly → `die`, so the board aborts the delete (fail-closed),
  mirroring the existing fatal treatment of unresolved *doomed* ids (`aitask_attach.sh:412`).

**Ordering / no spurious orphan:** for a rebound hash, `incref` **all** survivors FIRST, then
`decref` the doomed id — so `refs` never transiently empties and `decref` never stamps a
spurious `orphaned_at` (`attachment_meta.py:134`). `incref` with no k=v args only adds the ref
and clears `orphaned_at`; it never clobbers blob-intrinsic mime/size/backend
(`attachment_meta.py:97-118`).

## Files to modify

### 1. `.aitask-scripts/aitask_attach.sh` — core change

**`_attach_decref_deleted_txn` (lines ~388-446):** replace the protect-hash *set* with a
map from hash → the survivor task id(s) that list it, make protected-id resolution fatal
(Rule B), and swap the SKIP branch for a ledger-gated rebind (Rule A):

```bash
_attach_decref_deleted_txn() {
    local n_protect="$1"; shift
    # Map each folded-origin hash -> the revived task(s) that still list it, so a
    # doomed ref can be REBOUND to the survivor(s) instead of orphaned (t1096). A
    # hash listed by >1 revived folded task -> ALL become referrers. An unresolved
    # protected id is FATAL: it is the intended new owner, so silently dropping it
    # would orphan a primary-owned blob (fail-closed, Rule B).
    local -A protect_ids_for_hash=()
    local i pid pf h
    for (( i=0; i<n_protect; i++ )); do
        pid="${1#t}"
        pf="$(resolve_task_file "$pid" 2>/dev/null)" \
            || die "ait attach decref-deleted: cannot resolve protected (revived) task t${pid}"
        while IFS= read -r h; do
            [[ -n "$h" ]] || continue
            case " ${protect_ids_for_hash[$h]:-} " in
                *" $pid "*) : ;;                                   # de-dup pid per hash
                *) protect_ids_for_hash["$h"]="${protect_ids_for_hash[$h]:+${protect_ids_for_hash[$h]} }$pid" ;;
            esac
        done < <(attach_task_hashes "$pf")
        shift
    done

    local now; now="$(date +%s)"
    local -A seen_relpath=()
    local stage=() task_id task_file hash rel survivors sid
    for task_id in "$@"; do
        task_id="${task_id#t}"
        task_file="$(resolve_task_file "$task_id" 2>/dev/null)" \
            || die "ait attach decref-deleted: cannot resolve doomed task t${task_id}"
        while IFS= read -r hash; do
            [[ -n "$hash" ]] || continue
            survivors="${protect_ids_for_hash[$hash]:-}"
            # REBIND only a ledger ref the doomed task actually holds (Rule A) — a
            # blind incref on a drifted/retry state would resurrect an orphan or
            # grant unearned ownership.
            if [[ -n "$survivors" ]] && attach_meta refs "$hash" | grep -qxF "$task_id"; then
                for sid in $survivors; do
                    attach_meta incref "$hash" "$sid"        # survivors FIRST -> no orphan stamp
                done
                attach_meta decref "$hash" "$task_id" "now=$now"
                printf 'REBOUND:%s:%s:%s\n' "$task_id" "$hash" "${survivors// /,}"
            elif [[ -n "$survivors" ]]; then
                # Survivor lists it but the doomed id no longer references it in the
                # ledger -> nothing to move (already rebound / never owned). No incref.
                printf 'REBIND_NOOP:%s:%s\n' "$task_id" "$hash"
                continue                                     # unchanged bytes -> do NOT stage
            else
                attach_meta decref "$hash" "$task_id" "now=$now"
                printf 'DECREFED:%s:%s\n' "$task_id" "$hash"
            fi
            rel="$(attach_meta_relpath "$hash")"
            if [[ -z "${seen_relpath[$rel]:-}" ]]; then
                seen_relpath["$rel"]=1; stage+=( "$rel" )
            fi
        done < <(attach_task_hashes "$task_file")
    done
    # staging / no-op-guard / commit / rollback block UNCHANGED, except the commit
    # message generalized:  "ait: Release/rebind attachments of deleted task(s): $*"
    ...
}
```

The idempotency / empty-commit guard and reset+checkout rollback are preserved verbatim. The
`REBIND_NOOP` `continue` skips staging so an already-rebound re-run stages nothing → the
existing no-op guard keeps re-runs commit-free.

**Header comment (lines ~357-371)** and the **`show_help()` internal line (line 59)**: reword
from "…is SKIPPED (not decref'd)…conservative no-data-loss guard…proper rebind…a follow-up" to
describe the implemented rebind-on-unfold (incref survivor + decref primary, gated on current
primary ownership; unresolved protected id fatal).

### 2. `.aitask-scripts/board/aitask_board.py` — comments only (no code change)

- `_decref_doomed_attachments` docstring (lines ~6530-6532): "skips decref'ing any blob a
  revived task still references (conservative no-data-loss guard)" → "**rebinds** each blob a
  revived task still lists from the deleted primary to that revived task (t1096)".
- **Inline `_do_delete` comment (lines ~6577-6578):** "folded_ids are revived by the unfold
  below, so they are **protected from decref**. t1093" → "…so they are passed as
  `--protect-task`; the helper **rebinds** each blob they still list from the primary to them
  (t1096)." (Concern 5 — keep the mental model at the deletion site correct.)

**Observed pre-existing gap (out of scope, flag as upstream-defect candidate at Step 8b):** the
board's unfold loop (`aitask_board.py:6589-6594`) ignores the `aitask_update.sh` return codes.
This is not a t1096 data-loss risk — after rebind the revived task owns the ledger ref, and even
if its unfold fails leaving it `Folded`, the blob is retained via that non-empty ref (gc's
zero-refcount check), independent of the `Folded`-excluding frontmatter cross-check. Recording
it as a defect bullet for the follow-up offer, not fixing it here.

### 3. Tests

**(a) `tests/test_attach_task_delete_decref.sh`** — rewrite case **D** (currently asserts
`SKIPPED` + ref retained on the primary) to the rebind outcome, and add the remaining required
scenarios + an end-to-end board-sequence case. Fixture additions mirror the existing
`mk_task` / `attach add` style (legacy-git mode): a `t32_folded2` task and `a_multi.bin` /
`a_nd.bin` blobs.

- **D — Primary-owned duplicate hash → rebind to revived task** (required test 1): `HFO`
  listed by both `t30` (own/merged) and `t31` (folded), ledger `refs={30}` (simulated fold
  rebind, as the existing fixture already does). After `decref-deleted --protect-task 31 30`:
  output contains `REBOUND:30:<HFO>:31`; `meta_refs HFO == "31"` (moved to revived, **not**
  orphaned, **not** on the deleted primary); `orphaned "$HFO"` is empty (Rule-A ordering);
  primary's OWN blob `HEO` decref'd to `""`. Then `gc` past grace: `HFO` blob **retained**,
  `HEO` reclaimable.
- **G — Multiple folded tasks sharing one hash** (required test 2): `t31` and `t32` both list
  `HMULTI`, `refs={30}`. `decref-deleted --protect-task 31 --protect-task 32 30` →
  `meta_refs HMULTI == "31,32"` (exact assert is stable: `cmd_refs` **sorts**,
  `attachment_meta.py:150`); the `REBOUND` line asserted by **membership** (contains `31` and
  `32`), not exact CSV order — the CSV follows `--protect-task` arg order, not part of the
  contract (Concern 4). Blob retained by `gc`.
- **H — Revived hash NOT referenced by the primary (defensive no-op)** (required test 3): `t31`
  lists `HND` but `t30` does not. `decref-deleted --protect-task 31 30` → no `REBOUND`/`DECREFED`
  line for `HND`, `meta_refs HND` unchanged (`"31"`), exit 0.
- **I — Ledger-drift / retry idempotency** (Rule A): starting from the *already-rebound* state
  (`refs={31}`), re-run `decref-deleted --protect-task 31 30` → emits `REBIND_NOOP` for `HFO`,
  `refs` stays `"31"`, **no** empty commit created (`HEAD` unchanged), exit 0. Proves a blind
  incref cannot resurrect/duplicate ownership on retry.
- **J — End-to-end board unfold sequence** (Concern 3): replay the exact subprocess sequence
  `_do_delete` runs, with real files: (1) `decref-deleted --protect-task 31 30` *while both
  files still exist*; (2) unfold t31 via `aitask_update.sh --batch 31 --status Ready
  --folded-into ""` (the board's literal call); (3) `git rm` t30 + commit. Assert t31 is now
  `Ready` and `meta_refs HFO == "31"`. Then **delete the revived task**: `decref-deleted 31` +
  `git rm t31` + commit → `HFO` reaches zero refs, `orphaned_at` stamped, and `gc` past grace
  **reclaims** the blob. This is the load-bearing proof that the deferred leak is actually
  closed end-to-end (not just that the helper moved a ref).

Cases A/B/C/E (pure decref / cascade / rollback, no `--protect-task`) are unchanged and must
still pass — the plain-decref path is untouched.

**(b) `tests/test_board_decref_doomed_attachments.py`** — no behavioural change needed (the
board still assembles `--protect-task <folded_id>` and fails closed on non-zero exit; the
existing contract tests still pass). Update the module docstring / comments to say "rebinds"
rather than "skips/guards" so the file matches the new semantics.

**Why not a `_do_delete` worker-level test:** `_do_delete` is a Textual `@work(thread=True)`
worker driven through `call_from_thread`; invoking it in isolation fights the worker/event-loop
machinery and would test the harness, not the logic. Case **J** instead exercises the real
operation *sequence* against real files (which is what the board performs), and the existing
`test_nonzero_exit_fails_closed` proves `_decref_doomed_attachments` returns `ok=False` on
helper failure — the signal the reviewed-in-place 3-line guard at `aitask_board.py:6580-6586`
consumes to `return` before any unfold / `git rm`.

### 4. Docs (current-source-of-truth)

- `aidocs/task_attachments_design.md` §Hard-delete (lines ~250-255): replace the "skipped …
  conservative guard … tracked follow-up (t1096)" prose with the implemented rebind (each blob
  a revived task lists, and that the primary currently references, is **rebound** to the
  revived task — incref survivor + decref primary — keeping the ref with the surviving
  referrer; unresolved revived id is fatal / fail-closed).
- `aidocs/attachment_metadata_bucketing.md` §2a (lines ~79-82) and Tracked-follow-ups
  (lines ~218-219): mark rebind-on-unfold **resolved (t1096)**; drop the "skipped/guard" wording.

## Risk

### Code-health risk: low
- Change is contained to one bash transaction function + comment/doc edits; reuses existing
  `attach_meta incref/decref/refs`, `attach_task_hashes`, `attach_meta_relpath`, the lock, and
  the staging/commit/rollback block verbatim. Board runtime path unchanged. · severity: low
- Semantic change to `--protect-task` (skip→rebind), a new fatal path (unresolved protected id),
  and the output token (`SKIPPED`→`REBOUND`/`REBIND_NOOP`): blast radius verified minimal — no
  production consumer parses the tokens; only the board (exit-code only) and two test files use
  the helper. · severity: low

### Goal-achievement risk: low
- All three task-mandated scenarios (primary-owned duplicate, multiple folded sharing a hash,
  defensive no-op) plus drift/retry (I) and full board sequence (J) are covered by explicit
  bash cases against the real helper, invoked as the board invokes it. · severity: low
- Rule A (ledger-ownership gate) + incref-before-decref ordering provably prevent orphan
  resurrection and spurious `orphaned_at`; Rule B fails closed on an unreadable new-owner.
  Asserted directly (D: `orphaned` empty; I: `REBIND_NOOP` + no commit). · severity: low

## Verification

- `bash tests/test_attach_task_delete_decref.sh` → all PASS (A/B/C/E + rewritten D + new G/H/I/J).
- `python3 -m pytest tests/test_board_decref_doomed_attachments.py -v` → PASS (unchanged contract).
- `bash tests/test_attach_archive_gc.sh` + `bash tests/test_attach_fold_rebind.sh` +
  `bash tests/test_attachment_meta_lib.sh` → still PASS (shared `attachment_meta` libs untouched).
- `shellcheck .aitask-scripts/aitask_attach.sh` → clean.
- Manual (board): a primary with a folded task sharing a blob → hard-delete → the revived task
  now **owns** the blob's ref; deleting the revived task later reaches zero-refcount and `gc`
  past grace reclaims the blob (no residual stale primary ref).

## Post-Implementation (Step 8–9)

Review/approval (NON-SKIPPABLE), commit `bug: Rebind folded-origin attachment refs to revived
tasks on hard-delete unfold (t1096)`, plan commit via `./ait git`, `risk_evaluated` gate,
merge approval, archive. `depends: [1093]` — t1093 already landed. Step 8b upstream-defect
follow-up: offer to file the board unfold-return-code gap noted above.
