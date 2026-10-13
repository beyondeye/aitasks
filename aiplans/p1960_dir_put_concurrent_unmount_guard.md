---
Task: t1960_dir_put_concurrent_unmount_guard.md
Base branch: main
Output branch: main
---

# t1960 — Tie the dir backend's ops to the validated store directory

## Context

t1283 made `lib/artifact_backends/dir.sh` refuse a store root that is missing or
lacks the `.ait-artifact-store` marker, but that check is a one-time *pathname*
test at op entry. `artifact_dir_put` then re-resolves absolute paths for
`mkdir -p` / `mktemp` / `mv`, so a share unmounted between the check and those
writes plants a shard dir, temp file and possibly the blob in the persistent
mountpoint directory underneath. Same class on the read/rollback side: `head`
can answer a false "absent" (which the attach/artifact transactions turn into
`blob_pre=false` → rollback later deletes a blob other checkouts share), and
`delete` against the wrong tree reports a false success.

**Approach:** every op runs inside a subshell that `cd`s into the root **once**
and then validates the marker **through that cwd** (relative `[[ -f
.ait-artifact-store ]]`) and does all further work with relative paths. The
validation and every subsequent write then refer to the same directory object:
nothing is re-resolved by pathname. No pathname re-checks, no dev/inode
comparisons (explicitly out per the task).

What this means per window:
- share swapped **before** the cd → the cd lands on the empty mountpoint dir, the
  relative marker check fails → refusal, nothing written.
- share swapped/moved **after** the cd → our cwd is still the store directory, so
  every write lands in the store (a real non-lazy `umount` gets EBUSY because we
  hold a cwd there; `umount -l` detaches but writes still go to the share's fs).
  The op correctly *succeeds into the store*; the mountpoint gets nothing.
- store directory **gone** after the cd (forced unmount / ESTALE, simulated by
  deleting the held dir) → `mkdir -p` in the dead cwd fails → put dies with an
  actionable error; the mountpoint gets nothing.
- a dead held directory answers lookups with ENOENT exactly like a real
  absence, so every **negative** answer (head "absent", delete "removed", an
  empty listing) is qualified through the held cwd: ENOENT only (errno read
  under `LC_ALL=C`), and the held directory must still carry the marker
  afterwards — otherwise the op refuses (head/get/list) or returns 1 (delete).

`init` is deliberately left as-is: it has no marker to validate through the
cwd, so holding the directory would not change which directory gets marked —
it is a human-attended, explicit one-shot op (note this in the header).

## Implementation

### 1. `.aitask-scripts/lib/artifact_backends/dir.sh`

- **Replace** `_artifact_dir_check_root`, `_artifact_dir_require_root`,
  `_artifact_dir_blob_path` and `_ARTIFACT_DIR_ROOT_ERROR` with one helper:

  ```bash
  # _artifact_dir_held <cmd> [args...] -- run <cmd> in a SUBSHELL whose cwd IS
  # the store root, after validating the marker THROUGH that cwd. <cmd> uses
  # only paths relative to the root ... Exit status: <cmd>'s own, or
  # _ARTIFACT_DIR_UNUSABLE (3) with the cause on stderr when the root is unset,
  # cannot be entered, or the entered directory carries no marker. Everything
  # (incl. the unset check) is inside the subshell so delete can turn it into a
  # return instead of an exit.
  _ARTIFACT_DIR_UNUSABLE=3
  _artifact_dir_held() {
      (
          [[ -n "${ARTIFACT_DIR_ROOT:-}" ]] \
              || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: ARTIFACT_DIR_ROOT not set — activate via artifact_registry_activate dir"
          CDPATH='' cd -P -- "$ARTIFACT_DIR_ROOT" >/dev/null 2>&1 \
              || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: backend root not found: $ARTIFACT_DIR_ROOT (is the share mounted?)"
          [[ -f "$_ARTIFACT_DIR_MARKER" ]] \
              || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: $ARTIFACT_DIR_ROOT is not an initialized artifact store (no $_ARTIFACT_DIR_MARKER marker) — is the share mounted there? If this directory IS the share, run: ait artifact init-store dir"
          "$@"
      )
  }
  ```
  Messages are the existing ones verbatim (tests assert on "is the share
  mounted", "not an initialized artifact store", "ait artifact init-store dir").
  A die inside the subshell exits only the subshell and does not fire the
  caller's EXIT trap (verified), so each op propagates explicitly.

- **Negative answers are qualified through the held cwd.** A dead held
  directory (forced unmount / ESTALE / removed) answers every lookup with
  ENOENT, the same status as a real absence: `[[ -f ]]` returns 1, `rm -f`
  succeeds, and a glob comes back empty (probed). Two helpers, both called
  only inside a held subshell and both resolving **relative to the held cwd**:

  ```bash
  # _artifact_dir_still_held -- exit 0 iff the directory we hold still carries
  # the marker. Relative to the held cwd, so it can never be answered by a
  # different directory: it is NOT a pathname re-check of the root, and it never
  # authorizes a write (put relies on the held cwd alone). It only qualifies a
  # NEGATIVE answer (absent / deleted / empty listing) that a dead directory
  # would otherwise produce.
  _artifact_dir_still_held() { [[ -f "$_ARTIFACT_DIR_MARKER" ]]; }

  # _artifact_dir_lookup <rel> -- 0 = regular file present; 1 = genuinely
  # absent (ENOENT, and the held directory is still the store afterwards);
  # exits _ARTIFACT_DIR_UNUSABLE for anything else: a lookup error (EACCES,
  # EIO, ESTALE …), a non-regular file at the blob name, or a store that went
  # away. METADATA ONLY — never opens the entry: an open of a FIFO squatting
  # on the blob name blocks forever, stalling the transaction with its lock
  # held. `ls -ld` is one POSIX command that only lstat()s, reports the type
  # as the mode string's first character, and prints strerror on failure
  # (pinned to LC_ALL=C: the text is locale-dependent). `[[ -f ]]` / `test`
  # cannot tell ENOENT from EIO, and the GNU/BSD `stat -c || stat -f` chain
  # mixes two commands' stderr.
  _artifact_dir_lookup() {
      local rel="$1" out
      [[ -f "$rel" ]] && return 0
      if out="$(LC_ALL=C ls -ld -- "$rel" 2>&1)"; then
          [[ "${out:0:1}" == "-" ]] && return 0      # created between the two lookups
          die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: $rel in the store at $ARTIFACT_DIR_ROOT exists but is not a regular file (type '${out:0:1}') — remove it by hand"
      fi
      [[ "$out" == *"No such file or directory" ]] \
          || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: lookup of $rel failed in the store at $ARTIFACT_DIR_ROOT (${out##*: }) — is the share healthy?"
      _artifact_dir_still_held \
          || die_code "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: the store at $ARTIFACT_DIR_ROOT went away during the operation (share unmounted?) — cannot tell whether $rel is present"
      return 1
  }
  ```
  Probed under a de_DE parent locale with a 10 s bound: regular `-`, FIFO
  `p` (returns immediately), directory `d`, ENOENT for a missing blob and a
  missing shard, EACCES as "Permission denied". `[[ -f ]]` itself is a
  stat, so it does not block on a FIFO either.

- **Caller-relative arguments are made absolute before entering** (the subshell
  cd would otherwise break them; existing tests pass `a1.bin` / `a1.out`):
  `[[ "$src" == /* ]] || src="$PWD/$src"`; same for get's `dest` unless `-`.
  The shard path is derived once, outside: for put/get/head
  `rel="$(artifact_shard_path "$hash")" || die "artifact_dir_<op>: invalid hash: $hash"`
  (also closes the latent case where the old `printf root/$(shard)` swallowed a
  shard-path die). **delete never takes that path** — see below.

- **Ops** (each body is a small `_artifact_dir_<op>_held` function run via the
  helper; bodies use only `$rel`, `${rel%/*}` and relative temps):
  - `put`: outer checks `[[ -f "$src" ]]`, absolutizes, derives `rel`, then
    `_artifact_dir_held _artifact_dir_put_held "$hash" "$src" "$rel" || exit 1`.
    Held body keeps today's logic (content-verifying idempotent check — now
    `if _artifact_dir_lookup "$rel"; then …`, so a failed lookup refuses
    instead of being read as "absent" — + repair warning, cp-failure abort, staged-bytes hash verification, `mv -f`)
    with relative paths, and **checks `mkdir -p`** explicitly:
    `|| die "artifact_dir_put: could not create shard dir ${rel%/*} in the store at $ARTIFACT_DIR_ROOT — did the share go away during the operation? Nothing was installed."`
    Temp: `mktemp "${rel%/*}/.put.XXXXXX"`.
  - `head`: `_artifact_dir_held _artifact_dir_lookup "$rel"; rc=$?` → `0`
    present, `1` absent, anything else `exit 1`. "Absent" is answered only on
    ENOENT from a directory that is still the store, so the attach/artifact
    transactions' `blob_pre` can never be set false by an unusable store.
  - `get`: held body `_artifact_dir_lookup "$rel" || die "artifact_dir_get: blob
    not present: $hash"`; then `cat "$rel"` or `cp -- "$rel" "$dest"`; outer
    `|| exit 1`.
  - `delete` — must RETURN, never die (rollback hooks in the EXIT trap):
    `artifact_validate_hash "$1" || { warn "artifact_dir_delete: invalid hash: '$1'"; return 1; }`
    first, then `rel="$(artifact_shard_path "$1")" || return 1` (cannot fail
    after validation, but never `die`). Held body `_artifact_dir_delete_held`:
    `rm -f -- "$rel" || exit 1`, then `_artifact_dir_still_held || die_code
    "$_ARTIFACT_DIR_UNUSABLE" "artifact_dir: the store at … went away during the
    delete — cannot confirm $rel was removed"`. Outer
    `_artifact_dir_held _artifact_dir_delete_held "$rel" || return 1`.
  - `list`: held body `_artifact_dir_list_held` builds the listing in a variable
    (relative `*/` iteration, `sha256:<prefix><name>`), then
    `_artifact_dir_still_held || die_code …` and only then prints it — a dead
    directory never yields an empty "success". Outer `|| exit 1`.
- **Header comment:** replace the "VALIDATION BOUNDARY" paragraph with the
  current-state contract (validated through the held cwd; what each window
  yields; why `init` is not held). Update the comments above `put`/`delete`.

### 2. `aidocs/unified_artifact_design.md` (~line 296)

Replace "The root is validated at operation entry only — a share unmounted
mid-operation is not yet guarded." with the current-state statement: each op
enters the root once and validates the marker through that directory, so a
share unmounted mid-operation never redirects writes to the mountpoint
underneath (the op either completes in the store or fails).

### 3. `tests/test_artifact_dir_backend.sh` — new section F + D1 adjustment

- D1: the two `_artifact_dir_blob_path` assertions (helper removed) become:
  with `ARTIFACT_DIR_ROOT=""`, put dies with "ARTIFACT_DIR_ROOT not set" and
  writes nothing into the cwd (no `<2hex>` dir, no `.put.*`).
- **F. concurrent unmount (t1960)** — fresh marked store `$TMP/fstore` per
  probe; each probe in `( … )` so its shims die with it; shims call
  `command mkdir` / `builtin cd`:
  - **F1 moved after entry** (shim `mkdir`: on first call `mv store store.moved;
    command mkdir store`, i.e. an empty mountpoint left behind): put rc 0; the
    blob is in `store.moved/<shard>`; `find store -mindepth 1` is empty; no
    `.put.*` anywhere.
  - **F2 gone after entry** (shim `mkdir`: `rm -rf store; command mkdir store`):
    put rc≠0, message contains "did the share go away"; the mountpoint is empty;
    output never says CONTINUED (probe form `( op || true; echo CONTINUED )`).
  - **F3 swapped before entry** (shim `cd`: swap to empty dir, then `builtin cd
    "$@"`): put rc≠0, "not an initialized artifact store", mountpoint empty.
  - **F4 head/delete under F3's swap**: head dies (no false "absent", no
    CONTINUED); delete returns 1 (`DELETE_RC=1`), and the blob is still in the
    moved store.
  - **After-validation disappearance (F5–F7)** — the window between the held
    helper's marker validation and the op body. Test helper
    `wrap_after_validation <fn>` renames the body function via
    `eval "$(declare -f <fn> | sed '1s/^<fn>/_orig_<fn>/')"` and redefines
    `<fn>` to `command rm -rf "$FSTORE"; command mkdir "$FSTORE"` before
    calling the original — it runs as the helper's `"$@"`, i.e. after cd +
    validation, before any lookup. Store seeded with the blob first.
    - **F5 head** (wraps `_artifact_dir_lookup`): rc≠0, "went away", no
      CONTINUED — never a false "absent".
    - **F6 delete** (wraps `_artifact_dir_delete_held`): `DELETE_RC=1` and
      CONTINUED reached, cause "went away" on stderr.
    - **F7 list** (wraps `_artifact_dir_list_held`): rc≠0, no CONTINUED, no
      `sha256:` lines printed.
    - Each also asserts the recreated mountpoint stays empty.
  - **F8 lookup failure ≠ absence** (skipped when `EUID` is 0, where chmod
    does not deny): seed a blob, `chmod 000` its shard dir: head dies with
    "lookup of" (no CONTINUED); restore the mode.
  - **F10 FIFO at the blob name (bounded)**: `mkfifo "$FSTORE/<shard>"`, then
    source `tests/lib/proc_fixtures.sh` and run
    `run_bounded 10 "$TMP/fifo.head.out" bash -c '<source the libs>; artifact_backend_head "$1"; echo "HEAD_RC=$?"' _ "$HF"`
    (ARTIFACT_BACKEND / ARTIFACT_DIR_ROOT exported). Assert the status is
    not 124 (no hang) and non-zero, the output contains "not a regular file"
    and not `HEAD_RC=` (head refused, never "absent"). Same bounded probe for
    `artifact_backend_put "$HF" <file>`: not 124, non-zero, FIFO untouched
    (`[[ -p ]]`).
  - **F9 delete with an invalid hash**: `( artifact_backend_delete not-a-hash;
    echo "DELETE_RC=$?"; echo CONTINUED )` → contains `DELETE_RC=1`,
    `CONTINUED` and "invalid hash".
- Update the file header's coverage summary.

### Post-phase (risk mitigations)

1. [negative_control_prefix_dirsh] Copy `git show HEAD:.aitask-scripts/lib/artifact_backends/dir.sh`
   into the scratchpad and run section F's probes with that pre-fix copy
   sourced in place of the new one (a scratch copy of the test that re-sources
   it after `artifact_backend.sh`; the committed test is not modified). F1 and F2
   must FAIL there: the shard dir, temp file or blob must land in the left-behind
   mountpoint directory. Then confirm they PASS against the new `dir.sh`. Report
   both outcomes. If F1/F2 pass on the old code, the probes do not reach the
   window, so fix them before going on.

## Verification

- `bash tests/test_artifact_dir_backend.sh` and
  `bash tests/test_artifact_share_resolution.sh` (incl. J1–J5 rollback/lock
  release through delete) — all PASS.
- `shellcheck .aitask-scripts/lib/artifact_backends/dir.sh tests/test_artifact_dir_backend.sh`.
- Other artifact/attach tests that exercise dir: `grep -l "backend dir\|ARTIFACT_BACKEND=dir" tests/*.sh` and run them.

## Step 9

Post-implementation: commit code (`bug: … (t1960)`), plan via `./ait git`,
archive per task-workflow Step 9.

## Risk

### Code-health risk: medium
- Every dir op (incl. `delete` on the EXIT-trap rollback path and `head` feeding `blob_pre`) moves into a subshell with new exit-status plumbing; a mis-propagated status would turn a refusal into a silent continue · severity: medium · → mitigation: none (covered by existing E/J4/J5 tests plus the CONTINUED probes in F)
- Caller-relative `src`/`dest` must be absolutized before the cd; a miss breaks puts/gets from relative paths · severity: low · → mitigation: none (existing §A tests use relative paths)
- Absence classification parses `ls`'s strerror text, pinned to `LC_ALL=C` (probed under a de_DE parent locale). A platform whose C-locale ENOENT text differs would fail closed (refuse, never report a false absence) · severity: low · → mitigation: none (F8, F10 and the existing "head misses after delete" pin each branch)
- `artifact_sha256` / `cat` / `cp` still open the blob after `_artifact_dir_lookup` reported it regular. A FIFO swapped in at that moment would block; that is an adversarial replacement inside the store, already present before this change and not widened by it · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The tests simulate an unmount with `mv`/`rm -rf` of the held directory; real `umount` (EBUSY) and `umount -l` (detached fs) are argued, not exercised · severity: medium · → mitigation: dir_backend_real_unmount_probe
- The simulated-swap probes might not reach the actual validation→write window, which would make them pass vacuously · severity: low (residual — addressed by inline post-phase negative_control_prefix_dirsh) · → mitigation: inline post-phase negative_control_prefix_dirsh
- Acceptance says the op "fails with an actionable error"; for a store merely moved after entry the held-cwd design correctly *succeeds into the store* — only a gone store fails. The plan tests both outcomes · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: negative_control_prefix_dirsh | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: simulated-swap probes might not reach the window | desc: Run section F against the pre-fix dir.sh and require F1/F2 to fail there
- timing: after | name: dir_backend_real_unmount_probe | type: manual_verification | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: real umount / umount -l semantics are argued, not exercised | desc: On a real tmpfs/loop mount (root), umount and umount -l the dir store mid-put and confirm EBUSY / detached-fs behaviour leaves the mountpoint empty

## Implementation notes

- Implemented as planned in `dir.sh` (`_artifact_dir_held`, `_artifact_dir_still_held`,
  `_artifact_dir_lookup` via `LC_ALL=C ls -ld`, held bodies per op). Small addition:
  `_artifact_dir_abs` makes caller-relative `src`/`dest` absolute before entry.
- Tests: D1's `_artifact_dir_blob_path` assertions replaced by an empty-root put probe
  (nothing written into the cwd); section F covers F1–F10 plus positive controls for
  the qualified negative answers on a healthy store. `cd` shims use `|| return`
  (SC2164). 142/142 pass.
- **Post-phase [negative_control_prefix_dirsh] done:** with HEAD's pre-fix `dir.sh`
  sourced over the new one (scratch copy of the test), 29 assertions fail. F1 and F2
  fail as required, with the shard dir landing in the left-behind mountpoint, and F8
  shows the old head answering "absent" (rc 1) on EACCES. F3–F7 failures on the old code
  are weaker evidence (the old code has no `cd` / body functions for those shims to
  hook). F9 passes by accident on the old code (`rm -f root/` fails on a directory);
  F10 sources the libraries fresh, so it always exercises the new code — it guards the
  open()-based lookup hazard raised in review.
- Other dir-exercising suites green: test_artifact_share_resolution (98), test_artifact_cli
  (182), test_attach_txn_worktree_isolation (149), test_attach_lock_callback_contract (92),
  test_txn_snapshot (46).

## Post-Review Changes

### Change Request 1 (2026-10-13 11:23)
- **Requested by user:** (1) `_artifact_dir_abs` used command substitution, stripping trailing-newline path bytes — a get to "requested\n" wrote "requested" (could overwrite another file), a put from "source\n" failed; (2) an empty get destination became "$PWD/", copying the blob into the cwd with rc 0.
- **Changes made:** removed `_artifact_dir_abs`; put/get absolutize by plain assignment (`[[ "$src" == /* ]] || src="$PWD/$src"`); get dies on an empty destination before absolutizing. New test section G: put from a newline-terminated source, get to a newline-terminated destination (exact name, sibling without the newline untouched; bytes compared with `cmp` because `artifact_sha256` cannot hash a newline-named file), and an empty destination that dies without writing into the cwd. 151/151.
- **Files affected:** .aitask-scripts/lib/artifact_backends/dir.sh, tests/test_artifact_dir_backend.sh

## Final Implementation Notes
- **Actual work done:** Every `dir` backend op except `init` runs in a subshell that enters the store root once (`_artifact_dir_held`), validates the marker through that held cwd, and works with root-relative paths only. Negative answers (head "absent", delete "removed", a listing) are qualified through the held cwd: `_artifact_dir_lookup` reads errno via `LC_ALL=C ls -ld` (metadata only, so a FIFO cannot block it) and requires `_artifact_dir_still_held` afterwards. put checks `mkdir -p` explicitly; delete returns (never dies) on an invalid hash, an unusable store, or a store that went away mid-delete. Design doc §6 paragraph and the dir.sh header describe the held-root contract. Tests: section F (F1–F10) and section G, plus D1's empty-root probe.
- **Deviations from plan:** two plan-review rounds before approval: negative answers are qualified (head/delete/list after-validation window, delete's returning invalid-hash path), and the lookup became metadata-only (`ls -ld`, not an open()). Post-review: caller-relative paths are absolutized by plain assignment (`$( )` stripped trailing-newline bytes), and get rejects an empty destination (it used to become `$PWD/`).
- **Issues encountered:** a scratch copy of the test needed `PROJECT_DIR` pinned to run the negative control. `artifact_sha256` cannot hash a file whose name contains a newline (openssl's `NAME= hex` output gets split), so G compares bytes with `cmp`.
- **Key decisions:** `init` is not held, because it has no marker to validate through the cwd. The relative-to-cwd marker post-check is not a pathname re-check of the root and never authorizes a write; it only qualifies negative answers. An after-entry move of the store is a success *into the store* (the held directory), not a failure. Only a dead store fails.
- **Upstream defects identified:** None
