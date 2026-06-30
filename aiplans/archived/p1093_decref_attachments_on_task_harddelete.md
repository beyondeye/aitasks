---
Task: t1093_decref_attachments_on_task_harddelete.md
Worktree: (none — profile 'fast', current branch)
Branch: (current)
Base branch: main
---

# t1093 — Decref attachments on task hard-delete

## Context

Explicit task **hard-delete** (via `ait board`'s delete action → `_do_delete`) `git rm`s
a task's files and commits **without touching the attachment ledger**. The deleted
task's id therefore stays in each referenced blob's `refs` set forever, so the blob
never reaches zero-refcount and `ait attach gc` can never reclaim it — a permanent
orphaned-blob leak. A parent delete that cascade-deletes children leaks each child's
attachments too.

This is the **third** attachment lifecycle case. The others are handled: **archival**
never decrefs (D4 — an archived task is a real referrer); **fold** `rebind`s refs to
the primary (`aitask_fold_mark.sh`). Hard-delete is the only case where a decref
*should* fire, and it is missing.

No generic CLI task-delete path exists (the only task-file deleters are
`aitask_archive.sh`'s folded-task cleanup — correctly delete-without-decref — and the
board), so the board's `_do_delete` is the sole consumer to fix. (AC said "any CLI
delete path"; recorded honestly — there is none today.)

## Approach

A **bash helper** (`ait attach decref-deleted`) the board shells out to (per the
encapsulate-bash-in-a-helper convention and the task's steer), mirroring `ait attach
rm`: decref under the global attach lock, **self-commit** path-limited via
`_attach_commit`, with full reset/checkout rollback on commit failure.

**Commit model (decided):** helper self-commits its decref as a separate, path-limited
commit *before* the board removes files — chosen over restructuring the board's subtle
bare commit. Two commits per delete. **Recovery:** the decref commit lands first and is
correct (deletion intent stands); if the board's later delete commit fails, re-running
the delete is safe (decref is idempotent, guarded against empty-commit). Premature `gc`
reclaim in that window is impractical: `_attach_gc_blocking_hashes` (`aitask_attach.sh:374`)
blocks while the task file is still on disk, and decref stamps a fresh `orphaned_at`,
so the 30d grace clock only just starts.

**Folded tasks (decided — guard now, split the fix):** fold merges folded tasks'
attachments into the primary and rebinds their refs to the primary; hard-delete
*revives* (unfolds) those tasks but does not restore attachment ownership. So the
helper must **skip** decref'ing any doomed-task hash that a revived folded task still
lists in its frontmatter — preventing orphaning / data loss (the blob stays blocked by
the revived task's frontmatter via the gc cross-check). This leaves a benign stale ref
(points at the deleted primary) until a **follow-up task** does the proper
rebind-on-unfold. The follow-up is created during implementation with a bidirectional
reference; its tests cover primary-owned duplicate hashes and multiple folded tasks
sharing a hash.

### 1. New `ait attach decref-deleted` subcommand — `.aitask-scripts/aitask_attach.sh`

```bash
# ── Verb: decref-deleted (internal — board hard-delete, t1093) ────────────────
# Usage: decref-deleted [--protect-task <id>]... <doomed-id> [<doomed-id>...]
cmd_decref_deleted() {
    local protect_ids=() args=()
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --protect-task) protect_ids+=( "${2#t}" ); shift 2 ;;
            *) args+=( "$1" ); shift ;;
        esac
    done
    [[ ${#args[@]} -ge 1 ]] || die "Usage: ait attach decref-deleted [--protect-task <id>]... <task-id>..."
    with_attach_lock _attach_decref_deleted_txn "${#protect_ids[@]}" \
        ${protect_ids[@]+"${protect_ids[@]}"} "${args[@]}"
}

_attach_decref_deleted_txn() {
    local n_protect="$1"; shift
    local -A protect_hash=()                 # folded-origin hashes to SKIP (guard)
    local i pf
    for (( i=0; i<n_protect; i++ )); do
        pf="$(resolve_task_file "$1" 2>/dev/null)" && \
            while IFS= read -r h; do [[ -n "$h" ]] && protect_hash["$h"]=1; done \
                < <(attach_task_hashes "$pf")
        shift
    done
    local now; now="$(date +%s)"
    local -A seen_relpath=(); local stage=() task_id task_file hash rel
    for task_id in "$@"; do
        task_id="${task_id#t}"
        # Doomed ids come from existing files -> unresolved is FATAL (fail-closed,
        # so the board aborts the delete rather than leak). (#3)
        task_file="$(resolve_task_file "$task_id" 2>/dev/null)" \
            || die "ait attach decref-deleted: cannot resolve doomed task t${task_id}"
        while IFS= read -r hash; do
            [[ -n "$hash" ]] || continue
            if [[ -n "${protect_hash[$hash]:-}" ]]; then
                printf 'SKIPPED:%s:%s:folded\n' "$task_id" "$hash"; continue
            fi
            attach_meta decref "$hash" "$task_id" "now=$now"   # per (task,hash)
            printf 'DECREFED:%s:%s\n' "$task_id" "$hash"
            rel="$(attach_meta_relpath "$hash")"
            [[ -z "${seen_relpath[$rel]:-}" ]] && { seen_relpath[$rel]=1; stage+=( "$rel" ); }  # dedup staging (#5)
        done < <(attach_task_hashes "$task_file")
    done
    if (( ${#stage[@]} > 0 )); then
        task_git add -- "${stage[@]}" >/dev/null 2>&1 \
            || die "ait attach decref-deleted: failed to stage meta files"
        # No-op guard: idempotent re-run stages identical bytes -> skip empty commit.
        if ! task_git diff --cached --quiet -- "${stage[@]}" 2>/dev/null; then
            if ! _attach_commit "ait: Decref attachments of deleted task(s): $*" "${stage[@]}"; then
                task_git reset  -q -- "${stage[@]}" >/dev/null 2>&1 || true   # rollback like _attach_rm_txn (#5)
                task_git checkout -- "${stage[@]}" >/dev/null 2>&1 || true
                die "ait attach decref-deleted: commit failed — rolled back"
            fi
        fi
    fi
    printf 'STAGED:%s\n' "${#stage[@]}"
}
```

Reuses `with_attach_lock`, `attach_meta decref … now=` / `attach_meta_relpath` /
`attach_task_hashes`, `resolve_task_file`, `_attach_commit` + `task_git`. Dispatch in
`main()`: `decref-deleted) shift; cmd_decref_deleted "$@" ;;`; one-line internal entry
in `show_help()`.

### 2. Call it from the board's hard-delete — `.aitask-scripts/board/aitask_board.py`

**(a)** Pure, unit-testable static id extractor — **root-based** classification
(`TASKS_DIR.name in Path(p).parts`), board's canonical `TaskCard._parse_filename` (no
bash id ambiguity):

```python
@staticmethod
def _doomed_attachment_ids(paths):
    """Bare task ids (parent + cascade children) whose attachments must be
    decref'd on hard-delete. Plan/non-task paths excluded by root. t1093"""
    ids = []
    for p in paths:
        if TASKS_DIR.name not in Path(p).parts:   # plan files live under aiplans/
            continue
        name = Path(p).name
        if not (name.startswith("t") and name.endswith(".md")):
            continue
        tid, _ = TaskCard._parse_filename(name)
        ids.append(tid.lstrip("t"))
    return ids
```

**(b)** Thin step returning a result (no `call_from_thread` inside → testable against
the real helper); `folded_ids` (already available in `_do_delete`) become
`--protect-task` so revived folded tasks' attachments are guarded:

```python
def _decref_doomed_attachments(self, paths, folded_ids):
    """Decref doomed task attachments via the helper. Returns (ok, msg). t1093"""
    ids = self._doomed_attachment_ids(paths)
    if not ids:
        return True, ""
    cmd = ["./.aitask-scripts/aitask_attach.sh", "decref-deleted"]
    for fid in folded_ids:
        cmd += ["--protect-task", fid]
    cmd += ids
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
    if r.returncode != 0:
        return False, (r.stderr.strip() or r.stdout.strip())
    return True, ""
```

**(c)** In `_do_delete`, call it **first in the `try`** — before unfold / remove-child
/ `git rm` (files must exist; cleanest fail-closed: abort before any mutation). On
helper error, notify and `return`; **do not** call `pop_screen` here — the existing
`finally` already pops the overlay (#1 — avoids the double-pop):

```python
ok, err = self._decref_doomed_attachments(paths, folded_ids)
if not ok:
    self.app.call_from_thread(
        self.notify,
        f"Attachment decref failed — task NOT deleted (retry): {err}",
        severity="error",
    )
    return                       # finally pops the LoadingOverlay; nothing deleted
# ... existing unfold / remove-child / git rm / bare commit follow unchanged ...
```

`paths` already includes parent + cascade-child task files; the no-attachments case
returns `STAGED:0` rc=0 and proceeds. Only a real ledger/lock/resolution error aborts.

### 3. Follow-up task (created during implementation)

`aitask_create.sh --batch` a `bug` task: **"Rebind folded-origin attachment refs to
revived tasks on hard-delete unfold"** — t1093 only guards (skips) folded-origin
hashes; this moves the ref from the deleted primary back to each revived folded task
(per-hash incref+decref). Add a bidirectional reference (t1093 plan ↔ follow-up task,
committed via `./ait git`). Specify its tests: primary-owned duplicate hashes; multiple
folded tasks sharing one hash.

### 4. Tests

**(a) Bash — `tests/test_attach_task_delete_decref.sh` (new)**, on the
`test_attach_archive_gc.sh` legacy-git fixture; calls `ait attach decref-deleted` as
the board does:
1. **Single attachment** → decref'd to zero, `orphaned-at` stamped, committed; `gc`
   past grace reclaims blob + meta.
2. **Shared blob** (2 tasks) → decref one → retained, other ref intact; `gc` no-op.
3. **Cascade** → `decref-deleted parent c1 c2` → all doomed refs gone (incl. a
   parent+child *shared* blob → zero), a non-doomed sibling's blob untouched; one
   commit; redundant re-run = clean no-op (idempotency/empty-commit guard).
4. **Folded guard** → `--protect-task <folded_id>` whose frontmatter shares a hash with
   the doomed primary → that hash is `SKIPPED`, blob **retained**; primary's own
   attachment still decref'd.
5. **Commit-failure rollback** → simulate a failing commit → assert meta files restored
   (no staged/dirty ledger edits) and nonzero exit.

**(b) Python — `tests/test_board_decref_doomed_attachments.py` (new)**, via the existing
board test-loader (`test_board_archived_relation_lookup.py`):
- `_doomed_attachment_ids` over a mixed `paths` list (parent, 2 children, parent plan
  `aiplans/p..`, child plans, stray path) → exactly parent + both child bare ids.
- `_decref_doomed_attachments` against a real fixture + real helper: success removes
  refs; a forced helper error returns `ok=False` (the fail-closed signal gating
  `git rm`).

### 5. Docs (light)

`aidocs/task_attachments_design.md` §8 ("Hard-delete") + `aidocs/attachment_metadata_bucketing.md`
§2/§2a: update prose from "gap" to the implemented `decref-deleted` flow; note the
folded-origin guard + its follow-up (current-source-of-truth rule).

## Concerns raised → resolution
- **#1 double-pop (high):** abort path just `return`s; existing `finally` pops once.
- **#2 folded tasks (med):** guard — skip folded-origin hashes via `--protect-task`
  (no orphaning/data-loss); proper rebind split to a follow-up task (your decision).
- **#3 fail-closed / unresolved (med):** unresolved doomed id is **fatal** in the
  helper → board aborts the delete.
- **#4 split commit (med):** helper self-commits first; two-commit recovery documented;
  board bare commit untouched (your decision).
- **#5 helper rollback (low):** reset+checkout on commit failure, mirroring
  `_attach_rm_txn`; staging paths deduped.

## Risk

### Code-health risk: low
- Additive subcommand + two small board methods; reuses existing lock/ledger/commit
  primitives; board bare-commit semantics untouched. · severity: low
- Two commits per delete (decref, then delete); decoupled and recoverable as above.
  · severity: low

### Goal-achievement risk: low
- Bash filename→id ambiguity **eliminated** (ids derived via `TaskCard._parse_filename`).
  · severity: low
- Folded-origin handling is a *guard*, not the full fix; explicitly split to a follow-up
  with no data-loss in the interim. · severity: low · → follow-up task

## Verification

- `bash tests/test_attach_task_delete_decref.sh` → all PASS (5 cases).
- `python3 -m pytest tests/test_board_decref_doomed_attachments.py -v` → PASS.
- `bash tests/test_attach_archive_gc.sh` + `bash tests/test_attach_local_backend.sh`
  + `bash tests/test_attach_fold_*` (if present) → still PASS (shared `attachment_meta.sh`).
- `shellcheck .aitask-scripts/aitask_attach.sh` → clean.
- Manual (board, MV follow-up): attach → delete → `gc` past grace reclaims; parent with
  attachment-bearing children cascades; forced helper failure leaves task undeleted;
  primary with a folded task sharing a hash → blob retained after delete.

## Post-Implementation

Steps 8–9: review/approval, commit (`bug: Decref attachments on task hard-delete (t1093)`),
follow-up task created + cross-linked, `risk_evaluated` gate, merge approval, archive.
Manual-verification follow-up offered at Step 8c.

## Final Implementation Notes

- **Actual work done:** Added the `ait attach decref-deleted [--protect-task <id>]...
  <doomed-id>...` verb to `.aitask-scripts/aitask_attach.sh` (decref under
  `with_attach_lock`, per-`(task,hash)` decref with `now=` orphan stamp, deduped
  staging, self-commit path-limited via `_attach_commit` with reset/checkout rollback,
  fatal-on-unresolved doomed id, folded-origin SKIP). Wired the board: static
  `_doomed_attachment_ids` (root-based filtering via `TASKS_DIR.name in parts`,
  canonical `TaskCard._parse_filename`) + `_decref_doomed_attachments` (builds
  `--protect-task` from `folded_ids`, returns `(ok, msg)`), called first in
  `_do_delete` with a **fail-closed** early `return` before any mutation (no explicit
  `pop_screen` — the existing `finally` handles it). Two new tests + doc updates.
- **Deviations from plan:** None of substance. Plan executed as approved (helper
  self-commit model + conservative folded guard). Follow-up created is **t1096** (a
  planned scope split, not an "after" risk mitigation).
- **Issues encountered:** Initial bash-test failures were test-only: (1) gc didn't
  reclaim until the doomed task *file* was also removed (the gc cross-check correctly
  blocks while the frontmatter still lists the blob — so the test now `git rm`s the
  file as the board does); (2) `assert_contains(desc, needle, haystack)` arg order was
  swapped. Both fixed; no production-code change needed.
- **Key decisions:** Helper self-commits separately (two commits per delete) rather
  than restructuring the board's subtle bare commit — decoupled, with documented
  two-commit recovery and the gc cross-check as the safety net. Folded-origin
  attachments are *guarded* (skipped), not rebound — proper rebind-on-unfold is
  **t1096** (depends on t1093). Both decisions were user-confirmed during planning.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** N/A (standalone parent task). t1096 (`depends: [1093]`)
  owns the folded-origin rebind-on-unfold; see its task body for the contract + tests.
