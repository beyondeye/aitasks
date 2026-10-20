---
Task: t2073_1_scratchpad_store_and_archival.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md, aitasks/t2073/t2073_5_scratchpad_docs.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-20 11:14
---

# t2073_1 — scratchpad_store_and_archival

## Context

Child of t2073 (minimonitor scratchpad pane). The scratchpad is a notes editor pane
bound to a followed code agent; for aitask agents its notes persist per task and are
dropped at archival. This child builds the **persistence layer only**: a bash store
helper, archival pruning and the setup gitignore rule. t2073_2 (the Textual app) and
t2073_4 (the minimonitor key) consume it. Full parent design:
`aiplans/p2073_minimonitor_scratchpad_pane.md` ("Store", "One writer per store",
"Store lifecycle").

## Verification notes (2026-10-20, verify pass)

- All target files are clean (`git status` empty for `aitask_archive.sh`,
  `aitask_setup.sh`, `.gitignore`, `tests/test_setup_git.sh`); none of the new files
  exist yet. No in-flight task touches them → no pre-edit gate needed.
- Line numbers confirmed: `prune_shadow_rejections` :208; call sites `archive_parent`
  :274, `archive_child` :516, parent auto-archive :569; `handle_folded_tasks` :322
  (dry-run `continue` at :388-391, `task_git rm "$folded_file"` :402);
  `setup_shadow_store_gitignore` :2903, registered in `main()` :5111;
  `.gitignore` `.aitask-shadow/` block :26-27; `test_setup_git.sh` HELPERS heredoc
  :834-841.
- Ordering premise holds: at all three archive sites `archive_move` of the task file
  precedes `prune_*`; in the folded path `task_git rm` removes the task file from the
  working tree before the planned prune.
- `registry_lock_acquire` installs its own EXIT trap and re-arms the archive sweep →
  not sourcing `task_utils.sh` remains correct. `tests/lib/test_scaffold.sh` already
  copies `terminal_compat.sh`, `atomic_write.sh`, `stale_lock.sh`, `registry_lock.sh`,
  so the new archive test only copies the new helper itself.
- **No permission-whitelist touchpoints**: the helper is called only by
  `aitask_archive.sh` and (later) the Python app via subprocess, never from a skill
  closure (`aidocs/framework/aitasks_extension_points.md` "This whitelist applies ONLY
  to helpers invoked from a skill").
- Existing archive suites that do not copy the new helper stay green: the hook is
  `>/dev/null 2>&1 || true`, so a missing script is a silent no-op.
- **Refinements found in verification** (folded into the steps below):
  1. `path` must also drop `.` and empty (`//`, trailing `/`) segments before the walk,
     otherwise a root such as `pad/./x` or `pad//x` yields a different key before
     creation (string tail kept verbatim) than after (canonicalized by `pwd -P`).
  2. Prune also refuses (exit 4) a store path that is itself a symlink (`-L`) —
     `-d` on a dangling or file symlink would otherwise report `PRUNED:absent`.
  3. The pause seam needs a "reached" signal so tests know the verb is parked inside
     the lock: the seam writes `<point>` to `${AITASK_SCRATCHPAD_PAUSE_FIFO}.reached`
     before blocking on the fifo.
  4. Negative controls are built as **isolated mutant copies** of the helper
     (temp dir with a `lib` symlink to the real lib dir), each produced by one `sed`
     whose effect is asserted (the mutant differs from the original) before use.
  5. `tests/test_setup_git.sh` :843-845 says "one helper stands for all six" — the
     new HELPERS row makes it seven; update that prose count.
  6. **Root validation runs first, for every verb** (review concern, confirmed): the
     earlier draft refused a `..` root only inside `_canonical_key`, which `open` ran
     *after* creating `.locks/`, the store and `.holder.lock`, and which `save` /
     `prune` never ran — so `pad/../other` reached mutations. Its
     `OPENED:$(_canonical_key …)/notes.md` print also masked a failing substitution
     (errexit does not fire inside a command-substitution argument; probed: it prints
     `OPENED:/notes.md` and exits 0). Fixed in step 1: `validate_root` is a direct
     call (no subshell) right after `resolve_task_id` in every verb, before any
     filesystem access, and the key is captured into a variable with an explicit
     failure branch before any mutation.
  7. **The 5 s figure is a lock-wait budget, not a save deadline** (review concern,
     confirmed): `registry_lock_acquire` spends `timeout` only on acquisition. The
     stdin read before it and the render/rename after it have no deadline. The helper
     header and this plan now say so. No absolute save-duration bound is claimed;
     that would need a separate deadline-and-cancellation design, which is out of scope.
  8. **The loss boundary is content-based** (review concerns, confirmed): serialized
     saves queue later edits behind a pending one, so "last 3 s plus one in-flight
     save" is wrong while a save stalls. "Since the last `SAVED:`" is also wrong: it
     ties protection to completion time rather than to the captured buffer, and a
     write can commit before its response arrives. Step 5 states the boundary as
     "changes not included in the latest successfully saved buffer may be lost", with
     the 3 s as a start target only. It edits the parent and sibling plans and sends
     advisory notes for the two task bodies that repeat the old wording.

## Shared design decisions (from the parent plan, unchanged)

- **Store:** gitignored `${AITASK_SCRATCHPAD_DIR:-.aitask-scratchpad}/<id>/notes.md`
  (bare id), written only through `aitask_scratchpad_store.sh` (registry lock +
  `ait_atomic_render`), modelled on `aitask_shadow_rejected.sh`.
- **One writer per store:** the app (t2073_2) holds `fcntl.flock` on
  `<store>/.holder.lock`, opened `O_RDWR` **without `O_CREAT`**; only `open` creates
  that file, inside its locked critical section.
- **Store lifecycle is serialized by one per-task lock OUTSIDE the store dir**
  (`$SCRATCHPAD_DIR/.locks/<id>.lockd`), so no verb has to `mkdir` the store to lock it.
  `open` refuses `NO_TASK` once the task file moved; `save` refuses `ARCHIVED` / `ABSENT`
  and never `mkdir`s; `prune` does every check under the lock except the root-absent
  early exit.
- `path <id>` prints the canonical absolute store dir — the value t2073_4 stamps into
  `@aitask_scratchpad_store` (per-project identity; bare task ids collide across
  projects on one tmux server).

## Implementation

### 1. New `.aitask-scripts/aitask_scratchpad_store.sh`

Header comment in the style of `aitask_shadow_rejected.sh` (purpose, layout, lifecycle
lock, why `task_utils.sh` is not sourced, verbs, exit codes). `set -euo pipefail`;
source `lib/terminal_compat.sh`, `lib/registry_lock.sh`, `lib/atomic_write.sh`.

Globals: `SCRATCHPAD_DIR="${AITASK_SCRATCHPAD_DIR:-.aitask-scratchpad}"`,
`LOCK_TIMEOUT=5` — the **lock-wait budget** for every verb, passed to
`registry_lock_acquire`, which spends it on acquisition only. The header states the
consequence plainly: a verb waits at most ~5 s for the lock, but the work it does
once it holds the lock (render, rename, `find`/`rmdir`) has no deadline, so no verb's
total duration is bounded by this value. `TASK_ID STORE_DIR STORE_FILE HOLDER_FILE
LOCKS_DIR LOCK_DIR STORE_KEY`.

Exit codes: 0 ok · 2 usage / bad id / `..` in root · 3 `LOCK_BUSY` · 4 `ERROR`.

Functions:
- `usage`, `err_usage` — copied.
- `resolve_task_id` — copied verbatim (`^[0-9]+(_[0-9]+)?$`, strips `t`).
- `validate_root` — called **directly** (never in `$( )`, so `exit 2` propagates)
  as the second statement of every verb, right after `resolve_task_id` and before
  `store_paths_for` or any filesystem access: `case "/$SCRATCHPAD_DIR/" in */../*)
  err_usage "scratchpad root '…' contains a '..' segment" ;; esac`. This is the only
  `..` refusal; it happens before anything is created, modified or deleted.
- `capture_key` — `STORE_KEY` setter with an explicit failure branch, run before any
  mutation: `if ! STORE_KEY="$(_canonical_key "$STORE_DIR")" || [[ "$STORE_KEY" != /* ]];
  then printf 'Error: cannot canonicalize …' >&2; exit 4; fi` (a plain assignment
  carries the substitution's status; no `local x=$( )` masking).
- `store_paths_for` — `STORE_DIR="$SCRATCHPAD_DIR/$TASK_ID"`,
  `STORE_FILE="$STORE_DIR/notes.md"`, `HOLDER_FILE="$STORE_DIR/.holder.lock"`,
  `LOCKS_DIR="$SCRATCHPAD_DIR/.locks"`, `LOCK_DIR="$LOCKS_DIR/$TASK_ID.lockd"`.
- `lock_or_busy` — the shadow version minus its `mkdir -p "$STORE_DIR"`: instead
  `mkdir -p "$LOCKS_DIR"` (failure → exit 4) and `-w "$LOCKS_DIR"` check; keep the
  symlink / non-directory lock-path refusals (exit 4); `registry_lock_acquire
  "$LOCK_DIR" "$LOCK_TIMEOUT"` or `LOCK_BUSY` exit 3.
- `task_is_active` — parent id `N`: any `${TASK_DIR:-aitasks}/tN_*.md` exists; child
  `P_C`: any `${TASK_DIR:-aitasks}/tP/tP_C_*.md` exists (glob loop with `-e`, no `ls`).
  `aitasks/archived/` is never matched.
- `_pause_seam <point>` — no-op unless `AITASK_SCRATCHPAD_PAUSE_FIFO` is set; then
  `printf '%s\n' "$point" > "${AITASK_SCRATCHPAD_PAUSE_FIFO}.reached"` and
  `read -r _ < "$AITASK_SCRATCHPAD_PAUSE_FIFO"`. Documented as test-only.
- `_canonical_key <dir>` — the shared normalization used by `path` and `open`:
  1. absolute: as-is if it starts with `/`, else `"$PWD/$dir"`;
  2. split on `/`, drop empty and `.` segments; a `..` segment → `return 2`
     (defensive only — `validate_root` already refused it; callers go through
     `capture_key`, which turns any non-zero return into exit 4);
  3. walk prefixes from `/` while each is an existing directory (`-d`), stop at the
     first missing one; canonicalize the deepest existing prefix with
     `(cd "$prefix" && pwd -P)`;
  4. append the remaining segments joined with `/` (handle a canonical `/`).
  Creates nothing.

Verbs (each holds the lock across its whole critical section and releases with
`registry_lock_release` before printing the result):
- `open <id>` — `capture_key` first (before `lock_or_busy`, so a canonicalization
  failure leaves nothing behind; the key is stable across creation, which case 14
  asserts); `lock_or_busy`; `task_is_active` fails → release, `NO_TASK`, exit 0;
  `_pause_seam open:after_task_check`; `mkdir -p "$STORE_DIR"` (failure → exit 4);
  `: >> "$HOLDER_FILE"` (failure → exit 4); release; `echo "OPENED:$STORE_KEY/notes.md"`
  — a plain variable, no command substitution in the success print.
- `save <id>` — read stdin before the lock, preserving trailing newlines
  (`buf="$(cat; printf x)"; buf="${buf%x}"`; NUL bytes are not supported — say so in
  the header). Then `lock_or_busy`; `task_is_active` fails → `ARCHIVED` (exit 0,
  even when the dir survives); `[[ -d "$STORE_DIR" ]]` fails → `ABSENT` (exit 0);
  `_pause_seam save:after_exists_check`; empty buffer → `rm -f "$STORE_FILE"` →
  `SAVED:empty`; else `ait_atomic_render "$STORE_FILE" _save_body` (body:
  `printf '%s' "$buf"`), failure → exit 4; `SAVED:<bytes>` with the byte count from
  `LC_ALL=C` `${#buf}`. Never `mkdir`.
- `path <id>` — `capture_key`, `echo "$STORE_KEY"`; no lock, no side effects.
- `prune <id>` — `[[ -d "$SCRATCHPAD_DIR" ]]` fails → `PRUNED:absent` (the only
  pre-lock exit: every lifecycle verb creates `<root>/.locks` before locking, so no
  critical section can be in flight). Otherwise `lock_or_busy`, then under it:
  `-L "$STORE_DIR"` → refuse exit 4; not `-d` → `PRUNED:absent`; own-root guard
  `(cd "$STORE_DIR" && pwd -P)` must equal `$(cd "$SCRATCHPAD_DIR" && pwd -P)/$TASK_ID`
  else exit 4; `find "$STORE_DIR" -maxdepth 1 -type f -exec rm -f {} +` (sweeps
  `notes.md`, `.holder.lock`, stale atomic-write temps); `rmdir "$STORE_DIR"`
  (failure tolerated — never `rm -rf`); release; `PRUNED:<id>`.
- `main` dispatch on `open|save|path|prune|-h|--help`.

### 2. `.aitask-scripts/aitask_archive.sh`

- Add `prune_scratchpad <id>` right after `prune_shadow_rejections` (same shape;
  dry-run → `info "[dry-run] Would prune scratchpad for t$task_id"`; else
  `"$SCRIPT_DIR/aitask_scratchpad_store.sh" prune "$task_id" >/dev/null 2>&1 || true`),
  with a short comment: notes are scoped to the task, the store's lifecycle lock makes
  an open/save racing archival either finish before the move or refuse after it.
- Call `prune_scratchpad` directly after `prune_shadow_rejections` at :274, :516, :569.
- `handle_folded_tasks`: in the dry-run branch (:388) call `prune_scratchpad
  "$folded_id"` before `continue`; in the live branch call it right after
  `echo "FOLDED_DELETED:…"` (after the task/plan `task_git rm`). Comment: the folded
  task file is deleted here, so its scratchpad goes with it; shadow pruning for folded
  tasks stays out of scope.

### 3. `.aitask-scripts/aitask_setup.sh` and `.gitignore`

- `setup_scratchpad_gitignore` cloned from `setup_shadow_store_gitignore` (rule
  `.aitask-scratchpad/`, comment `# Scratchpad notes (per-task, local-only; pruned at
  archive)`, commit message `ait: Add .aitask-scratchpad/ to .gitignore (scratchpad
  notes)`), placed right after it with a `# --- … (t2073_1) ---` header comment;
  register it in `main()` right after `setup_shadow_store_gitignore` + `echo ""`.
- Repo `.gitignore`: add the same comment + `.aitask-scratchpad/` after the
  `.aitask-shadow/` block.

### 4. Tests

**NEW `tests/test_scratchpad_store.sh`** — `set -uo pipefail`, `asserts.sh`, temp dir,
exported `AITASK_SCRATCHPAD_DIR="$TMP/pad"` and `TASK_DIR="$TMP/aitasks"`, a
`mk_task <id>` / `archive_task <id>` pair (create / move the task file into
`$TASK_DIR/archived/`), `hold_lock`/`release_held_lock` adapted to
`$AITASK_SCRATCHPAD_DIR/.locks/<id>.lockd`, a `wait_reached <file>` bounded poll
(≤5 s) and a `make_mutant <name> <sed-expr>` builder that asserts the mutant differs
from the original. No assertions inside subshells (background jobs write to files;
assertions run in the main shell), so the in-process counters are sufficient. Cases:
1. `open` with no task file → `NO_TASK`, no store dir; with a task → `OPENED:<abs>/notes.md`,
   store dir + `.holder.lock` exist, no `notes.md`.
2. `save` round trip (multi-line, trailing newline preserved byte-exact, `SAVED:<n>`
   equals `wc -c`); empty save → `SAVED:empty`, `notes.md` gone, dir kept.
3. `save` before any `open` → `ABSENT`, no dir created.
4. Ids: `../evil` and `1x` → exit 2 for every verb.
5. Own-root guard: `$AITASK_SCRATCHPAD_DIR/9999` symlinked to an outside dir → prune
   exit 4, outside dir untouched; a symlink to a file → exit 4.
6. Externally held lock → `prune` prints `LOCK_BUSY`, exit 3, store files intact
   (one deliberate 5 s wait; no timeout env knob is added for tests).
7. Saves serialized: `save A` paused at `save:after_exists_check` (fifo), `save B`
   started without the seam → still running after 0.5 s and `notes.md` not yet B;
   release A → A then B land, final content B. **Control:** the same sequence against
   a mutant with `lock_or_busy` removed from `cmd_save` → B finishes while A is parked.
8. open-vs-prune: `open` paused at `open:after_task_check` on an existing store, task
   archived, `prune` started → still running after 0.5 s; release → prune
   `PRUNED:<id>`, store dir absent.
9. **First open vs archive:** no root at all, `open` paused before its `mkdir`, task
   archived, `prune` started → waits, then removes the freshly created store.
   **Control:** mutant with the store-absence check hoisted above `lock_or_busy` in
   `cmd_prune` → prune returns `PRUNED:absent` immediately and the store survives.
10. save-vs-prune: `save` paused after its existence check, task archived, `prune`
    waits; release → `SAVED`, then `PRUNED`, store absent; a following `save` →
    `ARCHIVED`, no dir recreated.
11. prune first, then `save` with the seam set → `ARCHIVED`, `.reached` never written.
12. Surviving dir: task archived, store dir left in place → `save` → `ARCHIVED`,
    `notes.md` unchanged.
13. Holder vs prune: after prune, `python3 -c 'os.open(p, os.O_RDWR)'` (no `O_CREAT`)
    fails with `FileNotFoundError`, store dir still absent.
14. `path` stability: identical output before and after `open` for (a) a relative root
    (`cd "$TMP"`, `AITASK_SCRATCHPAD_DIR=rel/pad`), (b) a nonexistent absolute root,
    (c) a root under a symlinked ancestor, (d) a root spelled with `./` and `//`
    segments; `open`'s `OPENED:` equals `path` + `/notes.md`; `..` in the root → exit 2.
15. `prune` on a never-created root → `PRUNED:absent` and the root is still absent.
16. **Invalid root refused before any mutation, every verb.** Seed
    `$TMP/other/42/notes.md` (+ its `.holder.lock`) and `$TMP/pad/`; snapshot the
    tree (`find "$TMP" | LC_ALL=C sort` plus `cksum` of every regular file). For each
    of `open`, `save` (with stdin), `path`, `prune` and for both
    `AITASK_SCRATCHPAD_DIR="$TMP/pad/../other"` and the relative `pad/../other`
    (from `cd "$TMP"`): exit 2, no `OPENED:`/`SAVED:`/`PRUNED:` line on stdout, and the
    snapshot is byte-identical afterwards (no `.locks/` created, `other/42` not
    modified or deleted).
17. **Canonicalization failure propagates.** Mutant whose `_canonical_key` starts with
    `return 4` (sed-applied, diff asserted): `open` → exit 4, stdout carries no
    `OPENED:` line, and neither `.locks/` nor the store dir was created; `path` →
    exit 4, empty stdout. (Without the explicit branch this is the masked
    `OPENED:/notes.md`, exit 0 shape.)

**NEW `tests/test_archive_scratchpad_prune.sh`** — cloned from
`test_archive_shadow_prune.sh` (fake repo + bare remote, `setup_fake_aitask_repo`,
copy `aitask_scratchpad_store.sh`; fixture pre-check `prune 999999` → `PRUNED:absent`;
stores seeded through the real helper `open` + `save` under the default
`.aitask-scratchpad/`; decoy store id 41 in every case). Cases: parent archival,
child archival, last-child auto-archives parent (both stores pruned), folded task
pruned when its primary archives, `--dry-run` leaves the store byte-identical and
prints `Would prune scratchpad`.

**`tests/test_setup_git.sh`** — HELPERS row `setup_scratchpad_gitignore|.aitask-scratchpad/`;
"all six" → "all seven" in the comment at :843-845.

### 5. Align the dependent loss-window promise

The stated loss window, "at most the last 3 s of edits, plus the edits carried by one
in-flight save (bounded by the helper's 5 s timeout); everything older is on disk", is
wrong twice:
- **5 s:** the helper's 5 s bounds only its lock wait (step 1), not the save.
- **3 s + one save:** saves are serialized, and a change made during a pending save
  waits for it to return. Take a save that captures the buffer at t=3 s and stalls
  until t=20 s. An edit typed at t=4 s is still queued, so a kill at t=15 s loses an
  11-second-old edit that is neither in the last 3 s nor carried by the pending save.

**Corrected contract** (a content-based boundary, used verbatim wherever the window
is stated): *On a hard kill, changes not included in the latest successfully saved
buffer may be lost, including edits queued during a pending save. Autosave targets
starting within roughly three seconds when no save is pending; this is not a maximum
loss window.* Where a sentence about the helper is needed, add: *The helper's 5 s
figure bounds only its lock wait; no save duration is bounded.*

The boundary is the **captured buffer**, not completion time or the `SAVED:`
response. A save that captured at t=3 s and returned at t=20 s does not cover an edit
typed at t=4 s. And a write can commit before its response is read, so an
unconfirmed change is "may be lost", never "is lost".

Edits (plan files only; this resolves the issue through wording, with no deadline
mechanism):
- **Shared paragraph:** in `aiplans/p2073_minimonitor_scratchpad_pane.md` (:85-87)
  and `aiplans/p2073/p2073_{2,3,4,5}_*.md` (:77-79), replace the bold sentence
  starting `**Stated loss window on a hard kill:` and ending `everything older is on
  disk.**` with the corrected contract. Its first clause stays bold.
- **Risk bullets** that repeat the narrow promise: parent plan :341 (`a hard kill
  loses at most the last 3 s of edits (max dirty age) plus one in-flight save`) and
  `p2073_2` :167 (`within the stated window (last 3 s of edits + one in-flight save)`).
  Reword both to "a hard kill may lose changes not included in the latest successfully
  saved buffer, including edits queued during a pending save; the ~3 s autosave start
  target (no save pending) is not a maximum loss window".
- **3 s test target:** parent :254 and `p2073_2` :142 `produces a save within 3 s of
  the first edit`. Append "while no save is pending (a start target, not a maximum
  loss window)".

The replacement is multiline-aware: a small `python3 -I` script with exact old
strings asserts exactly one match per site before the change and none after. Commit
the five plan files with `./.aitask-scripts/aitask_task_commit.sh` (named paths).

**Task bodies are left to their owners, through advisory notes.** The t2073_2 body
:85 (`Stated loss window: at most the last 3 s of edits plus one in-flight save.`) and
the t2073_5 body :22 (`last 3 s of edits plus one in-flight save`) repeat the narrow
promise. Send one note to each (`/aitask-note` → `./ait note <id> --from 2073_1
--with-live --file -`). Each note quotes the stale line and gives the corrected
content-based contract verbatim. It adds the queued-edit counterexample (capture at
3 s, return at 20 s, an edit at 4 s not covered), says that an unconfirmed write may
still have landed, and says the 5 s is a lock-wait budget only. It cites the commit
SHA of the plan edits and notes that the wording applies to t2073_2's hard-kill test
statement and t2073_5's docs. Both notes are advisory context, not instructions.

### Post-phase (risk mitigations)

1. [archive_stall_bound] In `tests/test_archive_scratchpad_prune.sh` add a case: seed
   a store for a standalone task, hold `.aitask-scratchpad/.locks/<id>.lockd` with a
   live-pid holder (the `hold_lock` shape from `test_shadow_rejected.sh`), run
   `aitask_archive.sh <id>` and time it. Assert: exit 0, task file moved to
   `aitasks/archived/` and committed (`git log -1 --name-only` names it), elapsed
   ≤ 5 s prune timeout + 5 s slack, store dir and `notes.md` still present. Then
   release the holder and run `aitask_scratchpad_store.sh prune <id>` → `PRUNED:<id>`,
   store absent.

## Verification

- `bash tests/test_scratchpad_store.sh`
- `bash tests/test_archive_scratchpad_prune.sh`
- `bash tests/test_setup_git.sh`, `bash tests/test_shadow_rejected.sh`,
  `bash tests/test_archive_shadow_prune.sh` (and any other `tests/test_archive*.sh`)
- `shellcheck .aitask-scripts/aitask_scratchpad_store.sh .aitask-scripts/aitask_archive.sh .aitask-scripts/aitask_setup.sh`

## Step 9 (Post-Implementation)

Standard child archival via task-workflow Step 9.

## Risk

### Code-health risk: low
- New self-contained helper modelled on a tested sibling; archive hooks are best-effort one-liners next to existing ones · severity: low · → mitigation: none
- A contended scratchpad lock can now delay archival by up to the 5 s prune timeout per pruned id (the shadow prune uses 2 s) · severity: low (residual — bound proven by inline post-phase archive_stall_bound) · → mitigation: inline post-phase archive_stall_bound

### Goal-achievement risk: medium
- Lifecycle races between open/save and archival prune could resurrect an archived store · severity: medium · → mitigation: none (external lifecycle lock, all prune checks under it, save's active-task check, pause-fifo interleaving tests with mutant controls)
- The `path` identity key must be stable across store creation, or t2073_4's one-per-store duplicate lookup misses a live pad · severity: low · → mitigation: none (segment normalization + case 14)
- A malformed root (`..` segment) or a failed canonicalization reaching a mutation or a success-shaped print · severity: low (residual — `validate_root` first in every verb, explicit `capture_key` failure branch, cases 16–17) · → mitigation: none
- Sibling plans/docs promising a loss window the design does not deliver (an absolute in-flight-save bound; "3 s + one save" while a stalled save queues later edits) · severity: low (residual — contract restated in the helper header and the parent/sibling plans in step 5; task bodies corrected by their owners via advisory notes) · → mitigation: none

### Planned mitigations
- timing: post-phase | name: archive_stall_bound | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — contended scratchpad lock delays archival | desc: Archive with a held scratchpad lock completes within the prune timeout, keeps the store, and a later prune removes it
