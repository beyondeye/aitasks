---
Task: t1030_3_archive_gc_fold_rebind.md
Parent Task: aitasks/t1030_task_attachments_support.md
Sibling Tasks: aitasks/t1030/t1030_1_frontmatter_cli_scaffold.md, aitasks/t1030/t1030_2_local_backend_cache_index.md
Archived Sibling Plans: aiplans/archived/p1030/p1030_1_frontmatter_cli_scaffold.md, aiplans/archived/p1030/p1030_2_local_backend_cache_index.md
Worktree: (none — profile 'fast' works on the current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-30 09:22
---

# Plan — t1030_3 Attachment lifecycle: retention-safe GC + fold re-bind

## Context

Third and final child of **t1030** (file attachments, content-addressed by
SHA-256). t1030_1 landed the headless primitives + `ait attach ls`; t1030_2
landed the storage core (`add/get/rm`) over the **per-blob metadata ledger**
(`attachments/meta/<2>/<62>.json` via `lib/attachment_meta.py`), the global
`attachments/.attach.lock` (`with_attach_lock`), and the `attachment_backend_*`
adapter seam. This task closes the **lifecycle** so blobs are never deleted out
from under a task that still references them — live **or archived**:

1. **`ait attach gc`** — opt-in orphan sweep with a **grace knob**.
2. **Fold re-bind** — when A folds into B, B inherits A's attachments
   (frontmatter + refcount).

> **Two plans-of-record predated this work and must be reconciled:** the on-disk
> `p1030_3` described the superseded `attachment_index.py`/`index.json` model
> (t1030_2 replaced it with per-blob `attachment_meta.py`), and the task file's
> AC #1 ("decref attachment hashes on archival") is **intentionally dropped**
> here (see decision D4). Four design decisions below were confirmed with the
> user during verify-mode planning.

Design refs: `aidocs/task_attachments_design.md` §8 (lifecycle/GC), §10 Q6
(fold), §8 "archive retention" open question (resolved by D4).

## Confirmed design decisions

- **D4 — Archiving never decrefs; `refs` = *all* referrers (active + archived).**
  Archiving a task is a status change, not a dereference: the archived task still
  references its attachments (browsable history), so its file stays a real
  referrer until it is actually deleted/bundled. Therefore **`aitask_archive.sh`
  needs no ledger changes** — a blob referenced only by an archived task keeps a
  non-empty `refs` and is never a GC candidate. The grace knob then governs only
  **fully-orphaned** blobs (every referrer did `ait attach rm`, or the task file
  was deleted). This resolves the design §8 retention open-question toward
  permanent keep. *(Deviation from task AC #1 "decref on archival" — recorded,
  not silent: the AC + design §8 are updated in Step 5.)*
- **D1 — Fold transfers attachments fully (frontmatter + refcount).** Rebinding
  the `refs` set alone leaves the blob absent from B's `attachments:`
  frontmatter: inaccessible via `ait attach ls/get B`, and (under D4) pinned in
  the ledger forever yet invisible — a soft storage leak. So fold **merges A's
  frontmatter entries into B AND rebinds refs**. Deterministic collisions:
  **skip** a folded entry whose `hash` is already on B (rebind still drops A);
  **rename** a same-`name`/different-`hash` entry uniquely (Step 4).
- **D2 — Orphan age = an epoch `orphaned_at` field in the meta file.** Git does
  not preserve filesystem mtimes across checkout/clone on the shared
  `.aitask-data` branch, so mtime/`git log` are unreliable. `attachment_meta.py`
  records `orphaned_at` (integer epoch) when `decref` (from `ait attach rm`)
  empties `refs`, clears it on `incref`. Compared as `now - orphaned_at >=
  grace_seconds` (pure integer math — no `date` parsing). Caller supplies
  `now=<epoch>` for testability.
- **D3 — Extract `lib/attachment_meta.sh`.** The meta-dir / python-invoke /
  relpath / task-hash-reader helpers currently live as private `_attach_*`
  functions in `aitask_attach.sh`. Move them to a sourceable lib (with a unit
  test) so `aitask_attach.sh` and `aitask_fold_mark.sh` share one implementation
  (and `gc` itself). `aitask_attach.sh` is refactored to consume it (existing
  `test_attach_local_backend.sh` + `test_attach_meta.sh` guard the add/rm
  regression).

## Step 1 — `lib/attachment_meta.py`: `orphaned_at` + getter + rebind reporting (Python)

- **`decref <hash> <task> [now=<epoch>]`** — stamp `orphaned_at` **only on a true
  non-empty→empty transition, and never re-stamp** (review concern 1). After
  discarding `task`: `if not rec["refs"] and "orphaned_at" not in rec:
  rec["orphaned_at"] = int(now)` (default `int(time.time())` when `now` absent).
  This preserves an existing `orphaned_at` on any retry/rebase/partial-failure
  re-run (a re-`decref` of an already-orphaned blob keeps the original orphan
  time — it cannot be pushed back inside the grace window). Accept the optional
  trailing `now=` kv (relax the `len(rest) != 2` guard).
- **`incref`** — when adding a ref, `pop("orphaned_at", None)` (a resurrected
  blob is no longer an orphan; the next genuine orphaning re-stamps freshly).
- **New `orphaned-at <hash>`** — print the blob's `orphaned_at` (epoch) or
  nothing. Lets `gc` read the age without parsing JSON.
- **`rebind <old> <new>` now reports changed blobs** (review concern 2):
  `cmd_rebind` prints each changed blob's `hash` (one per line) so the shell can
  stage exactly those meta files (`incref`/`decref` act on a known hash, so only
  the whole-tree-scanning `rebind` needs reporting).
- `zero-refcount` / `refs` unchanged. Schema note: `orphaned_at` is set-once-per-
  orphan-episode → idempotent/rebase-safe; pre-feature zero-ref blobs have no
  `orphaned_at` → treated as immediately eligible (age = ∞) by `gc`.

## Step 2 — `lib/attachment_meta.sh` (NEW, sourceable) + refactor (D3)

Move out of `aitask_attach.sh` (and re-source there):
- `attach_meta_dir`, `attach_meta <subcmd...>`, `attach_meta_relpath <hash>`
  (from the existing `_attach_meta_dir` / `_attach_meta` / `_attach_meta_relpath`).
- `attach_task_hashes <task_file>` — print each attachment `hash` from a task's
  `attachments:` frontmatter (new; built on `read_yaml_mappings`, mirrors the
  parse loop in `_attach_records`). Used by `gc`'s blocking-ref scan.
- `parse_duration_to_seconds <str>` — `30d`/`24h`/`90m`/`120s`/bare-int → seconds;
  `die` on garbage (new; for the grace knob).

Requires `python_resolve.sh` + `yaml_utils.sh` (already transitively available).
`aitask_attach.sh` keeps `with_attach_lock` from `attachment_lock.sh`; drop its
now-duplicated private copies and call the lib.

## Step 3 — `ait attach rm` stamps the orphan clock; archive is untouched

- **`aitask_attach.sh` `_attach_rm_txn`:** change the decref call to pass the
  clock — `attach_meta decref "$hash" "$task_id" "now=$(date +%s)"` — so an `rm`
  that empties `refs` records `orphaned_at` for the grace knob. (Small change to
  the working rm path; covered by `test_attach_local_backend.sh`.)
- **`aitask_archive.sh`: NO changes (D4).** Archiving never decrefs — the
  archived task remains a real referrer. (This is the deliberate departure from
  task AC #1; documented in Step 5.)

## Step 4 — `ait attach gc` (`aitask_attach.sh` `cmd_gc`)

Replace the `gc` stub. Entire sweep under **one** `with_attach_lock`:
1. `grace=$(parse_duration_to_seconds "$(_attach_gc_grace)")`; `now=$(date +%s)`.
2. Build the **blocking-ref** hash set (review concerns 3 + the high archive
   concern): scan task frontmatter across **both** the active tree
   (`aitasks/t*.md`, `aitasks/t*/t*.md`) **and `aitasks/archived/**`** — archived
   tasks are real referrers (D4) and MUST block GC — but **skip any file whose
   `read_task_status` is `Folded`** (pending-deletion; its refs were rebound to
   the primary). Union `attach_task_hashes` over the rest. This is the
   belt-and-suspenders cross-check against ledger drift; under D4 the ledger
   `refs` already includes archived ids, so this scan only ever *adds* safety.
3. For each `attach_meta zero-refcount` candidate: **re-read `refs`** under the
   held lock and confirm still empty (advisory→authoritative); skip if the hash
   is in the blocking set; read `orphaned-at` and **skip if `now - orphaned_at <
   grace`** (missing `orphaned_at` ⇒ eligible). Otherwise
   `attachment_backend_delete <hash>` + `rm -f` the meta file + stage both
   deletions.
4. Commit swept deletions (`_attach_commit "ait: GC N orphaned attachment(s)"`,
   explicit blob+meta relpaths). **On commit failure** (review concern 5) restore
   the just-deleted tracked files — `task_git reset -q -- <paths>` + `task_git
   checkout -- <paths>` — so a failed commit leaves no deleted-on-disk-but-
   uncommitted split-brain. Print a **swept-vs-retained** summary. **Opt-in
   only.**
- `_attach_gc_grace` reads `attachments_gc_grace` from
  `aitasks/metadata/project_config.yaml` (default `30d`), mirroring
  `_attach_size_cap_bytes`'s `read_yaml_field` pattern.
- Update `show_help` (`gc` no longer "(not yet implemented)") + drop `gc` from the
  `NOT_YET` stub path in `main`.
- *Known limitation (documented, not fixed):* archived tasks bundled into
  `aitasks/archived/**/old.tar.zst` are not frontmatter-scannable; their blobs
  rely on the ledger `refs` (which still lists them under D4) to stay pinned —
  the scan is only a secondary guard, so bundling does not orphan them.

## Step 5 — Fold re-bind + frontmatter merge (`aitask_fold_mark.sh`)

For each folded task (direct `folded_ids` **and** `transitive_ids` — both have
their files deleted at archival, so both must transfer first). All of the below
runs under **one** `with_attach_lock` so the ledger mutations and the frontmatter
merge are one transaction:
- **Rebind refs:** `attach_meta rebind <folded_id> <primary_id>`; **capture its
  printed changed hashes** (Step 1) → the set of meta files to stage (review
  concern 2).
- **Merge frontmatter (D1):** seed `seen_hashes`/`seen_names` from the primary's
  current `attachments:`. For each entry in the folded task's `attachments:`
  (read via `read_yaml_mappings`): **skip** if `hash ∈ seen_hashes`; else compute
  a unique name — if `name ∈ seen_names`, set `name=<stem>~<first8hex><ext>` and,
  **while still colliding, lengthen the hex suffix** (8 → 16 → … → full 64), then
  if somehow still present append `-<n>` (review concern 4 — deterministic *and*
  guaranteed unique). Then `frontmatter_patch.py append <primary_file>
  attachments hash=… name=… mime=… size=… added_at=… backend=…`; add `hash`/`name`
  to the seen sets.
- Source `attachment_lock.sh` + `attachment_meta.sh` + `python_resolve.sh`.
- **Staging:** Step 6 `fresh`/`amend` currently `task_git add aitasks/` (covers
  the modified primary `.md`). Add `task_git add -- <reported meta relpaths>`
  (rebind-reported hashes → `attach_meta_relpath`). Explicit paths only.
- **Commit-failure rollback — WHOLE fold transaction (review concern 6).** The
  fold mutates many task files in-place *before* the commit (deletion only
  happens later at archival), so all are HEAD-restorable: the **primary** file;
  every **direct folded** file (status=`Folded`, `folded_into`,
  `risk_mitigation_tasks=""`); every **transitive** file (`folded_into`); the
  **parent** file of each folded *child* id (the `--remove-child`
  `children_to_implement` edit); and the **rebound meta** files. Collect this
  full explicit path set as the fold proceeds (the script already resolves
  `primary_file`, `folded_files`, `transitive_files`; add the resolved parent
  files for child folds + the rebind-reported meta relpaths). Replace Step 6's
  current `task_git commit … || true` (which silently proceeds and even prints an
  empty `COMMITTED:` hash on failure) with: capture the commit exit status, and
  on failure `task_git reset -q -- <full set>` + `task_git checkout -- <full
  set>` then `die "fold commit failed — rolled back"`. Applies to the `fresh` and
  `amend` commit modes (`none` does not commit). This makes the whole fold
  atomic — a partial rollback that reverted only primary+meta would leave the
  folded/transitive/parent files in a half-folded state (the split-brain the
  reviewer flagged), which is worse than the current all-or-nothing-uncommitted
  behavior.

## Step 6 — Grace-knob config + doc-sync

- **Config doc:** document `attachments_gc_grace` (default `30d`, read from
  `aitasks/metadata/project_config.yaml`) in the project-config table in
  `.claude/skills/task-workflow/SKILL.md`, alongside `verify_build`/`test_command`.
  Define it as "grace period before a **fully-orphaned** attachment (no active
  *or archived* task references it) is reclaimed by `ait attach gc`". Add a
  commented example to `seed/` `project_config.yaml` if present.
  (Closure changes auto-render to other agent trees; no port task.)
- **Design doc-sync (no silent deviation):** update
  `aidocs/task_attachments_design.md` §8 — "Archival" no longer decrefs; state
  that archiving keeps references (browsable history) and GC reclaims only
  zero-ref blobs past grace; resolve the §8 "archive retention" open question
  (permanent keep). Commit with **plain `git`** (code-branch content).
- **Task-AC sync (no silent deviation):** update
  `aitasks/t1030/t1030_3_archive_gc_fold_rebind.md` — drop the "decref on
  archival" / `handle_attachment_deref` requirement, replace with the D4 model.
  Commit with **`./ait git`** (task data; separate commit from code/docs).

## Step 7 — Tests

- **`tests/test_attach_meta.sh` (extend)** — `decref` to empty stamps
  `orphaned_at` (assert passed `now`); `incref` clears it; `orphaned-at` getter;
  **no-restamp invariant (concern 1)** — a second `decref` with a later `now`
  keeps the original; an `incref`+`decref` cycle *does* re-stamp; **rebind prints
  the changed hash(es) (concern 2)** and is silent when `old` is unreferenced.
- **`tests/test_attachment_meta_lib.sh` (NEW, D3)** — `parse_duration_to_seconds`
  (`30d`/`24h`/`90m`/`120s`/`45`/garbage→die); `attach_task_hashes`;
  `attach_meta_relpath` shape.
- **`tests/test_attach_archive_gc.sh` (NEW)** — fixture data-branch repo
  (`setup_fake_aitask_repo`):
  - **Archive retention (D4 / high concern):** add attachment → archive the task
    → blob retained, `refs` still lists the archived task; **`gc` does NOT sweep
    it even past the grace window** (archived task is a blocking ref).
  - **Orphan reclaim:** `ait attach rm` (last ref) → `orphaned_at` stamped →
    within grace `gc` retains; past grace `gc` sweeps blob+meta.
  - **Shared blob:** 2 tasks reference it; rm/archive one → retained.
  - **Folded exclusion (concern 3):** a `Folded`-status task's frontmatter does
    NOT block GC of an otherwise-orphaned blob.
  - **gc-commit-failure rollback (concern 5):** force the commit to fail → the
    deleted blob/meta are restored from HEAD.
  - swept/retained summary printed.
- **`tests/test_attach_fold_rebind.sh` (NEW)** — fold A→B: B's frontmatter gains
  A's entry, refs now `[B]`, blob survives A's deletion **and survives B's
  archival** (D4, no decref); **dup hash** on B → skipped, refs single `[B]`;
  **same-name/different-hash** → renamed, **and when `<stem>~<8hex><ext>` already
  exists the suffix lengthens until unique (concern 4)**; transitive A←X, A→B →
  X's blob rebinds to B; **fold-commit-failure rollback — whole transaction
  (concern 6)** → force the commit to fail and assert **every** touched file is
  restored to its pre-fold state: primary frontmatter, rebound meta, the direct
  folded file's status (NOT left `Folded`), a transitive file's `folded_into`,
  and a folded *child*'s parent `children_to_implement` (child NOT removed) — and
  the command `die`s (no empty `COMMITTED:`).

## Verification

- `shellcheck` clean on all modified `.sh`; `py_compile` on `attachment_meta.py`.
- `bash` each test above + `test_attach_local_backend.sh` (D3-refactor + rm-now
  regression) — all PASS.
- `./.aitask-scripts/aitask_skill_verify.sh` (SKILL.md doc edit).
- Manual smoke in a scratch data-branch repo: add → archive (blob kept, **still
  referenced**) → `ait attach gc` (kept: archived-referenced + in-grace; swept:
  rm'd past grace) → fold a task carrying an attachment → `ait attach ls B` shows
  it.

## Risk

### Code-health risk: medium
- **Rebind / `gc` racing a concurrent `add`/`rm`.** A metadata mutation outside
  the attach lock could drop/clobber a ref → live blob GC'd, or a fold lost ·
  severity: medium · → mitigation: every mutation (fold rebind, `gc`) runs under
  the **same global `with_attach_lock`**; `attachment_meta.py` stays the
  lock-free primitive (caller owns the lock, no nesting); `gc` re-reads `refs`
  under the held lock before any delete — tested.
- **D3 refactor regresses the working `add`/`rm` path.** Extracting shared
  helpers + the rm `now=` change touch a shipped transaction · severity: medium ·
  → mitigation: pure move + one-arg addition; `test_attach_local_backend.sh` (28)
  + `test_attach_meta.sh` (33) re-run as regression — in-task.
- **`gc` deletes a still-referenced blob (esp. an archived task's).** · severity:
  medium · → mitigation: ledger `refs` includes archived ids (D4) so it is never
  even a candidate; plus the independent active+archived frontmatter blocking
  scan + grace window; asserted by the archive-retention test — in-task.
- **Commit-failure split-brain (fold/gc commit fails after ledger mutation).** ·
  severity: medium · → mitigation: touched paths are HEAD-restorable (fold
  modifies task files in-place + pre-existing meta; gc-deleted files were
  tracked) → `reset` + `checkout --` of the **whole** fold transaction's explicit
  path set (primary + direct/transitive folded files + child-fold parents + meta)
  on failure, replacing fold's prior silent `|| true`; fold- and gc-commit-failure
  rollback tests assert every touched file reverts — in-task.
- **Frontmatter merge corrupts the primary task file.** · severity: medium · →
  mitigation: reuse the proven byte-preserving `frontmatter_patch.py append`;
  deterministic, unit-tested collision handling — in-task.
- **Staging sweeps a concurrent writer's edits on `.aitask-data`.** · severity:
  low · → mitigation: explicit data-root-relative paths only (never blanket
  `attachments/`), matching the t1030_2 `_attach_commit` convention — in-task.

### Goal-achievement risk: low
- **Lifecycle/retention correctness** (archive keeps refs; gc reclaims only true
  orphans; fold transfers fully) is the whole point · severity: low · →
  mitigation: the archive-retention + orphan-reclaim + fold round-trip tests
  assert it — in-task.
- **D4 deviates from task AC #1 + design §8.** Left unsynced it would mislead the
  next picker · severity: low · → mitigation: Step 6 updates design §8 + the task
  file in this task (separate code/`ait git` commits) — in-task.
- **`orphaned_at` schema addition** to a t1030_2 primitive · severity: low · →
  mitigation: additive/backward-compatible (missing = eligible); set-once +
  caller-supplied `now` keeps it idempotent/testable — in-task.
- **Whole-tree scans** (`zero-refcount`, active+archived blocking scan, `rebind`)
  are O(attachments)/O(tasks) per call · severity: low · → mitigation: explicitly
  accepted for v1 (gc opt-in/infrequent) — no task.

**Planned mitigations:** None — every risk is mitigated **in-task** (single
global attach lock on all mutations + `gc` re-check, pure-move refactor guarded
by the existing add/rm tests, proven frontmatter patcher with deterministic
unit-tested collision handling, explicit-path staging, HEAD-restore rollback,
in-task doc/AC sync). No before/after follow-up tasks warranted.

## Step 9 (Post-Implementation)

Standard per `task-workflow` Step 9. This is the **last child** of t1030 by
number, but the parent's `children_to_implement: [t1030_3, t1030_4, t1030_5]`
still lists t1030_4 (manual-verify) and t1030_5 (evaluate-bucketed) — so
archiving t1030_3 will **not** auto-archive the parent (archival fires only when
`children_to_implement` empties). Final Notes MUST record: the **D4 model**
(archiving never decrefs; `refs` = all referrers; archived refs block GC; grace =
fully-orphaned reclaim window) and the AC/design-§8 sync; the `orphaned_at`
epoch field + clear-on-incref + no-restamp semantics; `attachments_gc_grace`
home + the duration parser; the fold-rebind + frontmatter-merge collision rules
and that rebind reports changed hashes; and flag for **t1076_1** that
version-aware GC must replace the simple zero-refcount test when per-blob meta
becomes the artifact manifest.
