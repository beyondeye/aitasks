---
Task: t1427_1_rejection_store_helper.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_2_picker_reject_tristate.md, aitasks/t1427/t1427_3_producer_suppression_rule.md, aitasks/t1427/t1427_4_rejection_docs.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-05 19:03
---

# p1427_1 — Rejection store + `aitask_shadow_rejected.sh` helper

## Context

The concern picker (`c` in `ait monitor` / `ait minimonitor`) lets the user
forward shadow concerns to the followed code agent but offers **no way to reject
one**. Every re-review re-raises everything, so the user re-triages the same
dismissed items each round. Nothing in the pipeline can express "already
rejected": the picker is pure UI with zero persistence, dedup is per-block and
in-memory, `Concern` has no stable cross-round identity, and the shadow has no
round memory.

This is the **substrate spike** for t1427 — the durable per-task rejection store
and its single writer/reader helper. Sibling t1427_2 (picker tri-state) and
t1427_3 (producer suppression rule) both consume it; nothing user-visible ships
until they land. Parent plan
`aiplans/p1427_reject_shadow_concerns_suppress_next_round.md` "Architecture"
section is binding; this plan restates the needed parts so it is self-contained,
and flags each place where verification against current source required a
deviation.

## Verification pass (2026-08-05) — what changed from the original plan

The plan was written from exploration notes and never verified. Reading the
actual library sources, then a review round, surfaced eight corrections — all
folded into the steps below.

**From reading the library sources:**

1. **`ait_atomic_render` refuses a zero-byte result**
   (`lib/atomic_write.sh:168`, override `AIT_ATOMIC_ALLOW_EMPTY=1`). Removing
   the *last* rejection would render an empty store, so the render would fail
   and the entry would silently never be removed. Resolved by correction 5's
   persistent header, which keeps the file non-empty by construction.
2. **`die()` exits 1, not 2** (`lib/terminal_compat.sh:17`), which contradicts
   the stated `2 = usage` contract. The malformed-id refusal is pinned to
   **exit 2** with its own stderr helper rather than `die`.
3. **`task_utils.sh` must NOT be sourced.** It pulls in `lib/archive_utils.sh`,
   which claims the process-wide `EXIT` trap at source time
   (`archive_utils.sh:116`); `registry_lock_acquire` then clobbers that trap and
   `registry_lock_release` clears it with `trap - EXIT`. The helper needs
   nothing from `task_utils.sh` (id validation is a pure bash regex; `die`/`warn`
   live in `terminal_compat.sh`), and the cited model `aitask_agent_marks.sh`
   deliberately does not source it either. **Deviation from the parent plan's
   architecture line, taken on purpose.**
4. **`archive_child` releases *two* locks**, not one — the child at
   `aitask_archive.sh:456` and, when the last child completes, the parent at
   `:508`. Pruning only at the child site would strand the parent's store. Also,
   a raw prune call would fire under `--dry-run`. Both fixed by encapsulating
   the call in a `prune_shadow_rejections()` helper beside `release_lock()`.

**From the review round:**

5. **`r<N>` as "max existing + 1" reuses ids.** Remove the *highest* entry and
   the next `add` re-issues that id: `r1, r2` → `remove r2` → `add` → the new
   entry is `r2`. t1427_2 pre-fetches `list --machine` at picker-open time and
   the parent plan **explicitly descopes** stale-data conflict handling, so a
   second TUI session issuing `remove r2` against its stale view would
   un-reject a *different, newly rejected* concern. Because staleness handling
   was descoped, the id must be a stable identity. Fixed with a persistent
   never-decreasing high-water mark (see **Store format**).
6. **`prune` canonicalizes before checking absence.** GNU `realpath` tolerates
   one missing trailing component but fails on two — verified: `realpath
   /tmp/missing_a` → rc 0, `realpath /tmp/missing_a/missing_b` → rc 1. So
   `realpath "$SHADOW_DIR/<id>"` **fails** whenever `.aitask-shadow/` has never
   been created, and under `set -euo pipefail` the assignment kills the script
   instead of printing `PRUNED:absent`. That is the *normal first archive* in
   any repo. `aitask_explain_cleanup.sh:52` already uses the
   `realpath … 2>/dev/null || echo "$DIR"` fallback idiom; the plan had dropped
   it. Fixed by checking absence first **and** restoring the fallback.
7. **`add` has no empty-input path.** With empty or whitespace-only stdin no
   line fails validation, so it would acquire the lock and print a
   success-shaped `ADDED:0` having stored nothing. Fixed by requiring ≥1 valid
   marker and failing **before** the lock is taken.
8. **Archive integration was never actually covered.** "Existing archive suites
   still green" only proves non-perturbation. The fixture in
   `tests/test_archive_folded.sh:28-68` copies scripts into the temp repo
   **individually**, so an un-copied `aitask_shadow_rejected.sh` makes the hook
   a no-op that `|| true` swallows — every existing suite stays green whether
   the hook fires, omits a site, or passes the wrong id. Fixed with a dedicated
   per-site integration test (step 7).

One further correction lands in the test design: the original "prune own-root
refusal (negative control)" used a **crafted traversal id**, which the task-id
regex rejects *before* the realpath check ever runs — so it would prove nothing
about the own-root guard. Replaced with a reachable trigger (pre-phase 6).

## Store format

`.aitask-shadow/<task_id>/rejected.md` — bare task id (`1427`, `1427_2`; no `t`
prefix, mirroring `.aitask-gates/`), repo-root-relative, lazy `mkdir -p` by the
writer, git-ignored, never committed.

```markdown
<!-- next_id: 3 -->

### r1 | 2026-08-05T14:02:11Z | producer: plan-challenge
- [high | Step 7 guard] The guard double-commits when the lock was already held.

### r2 | 2026-08-05T14:02:11Z | producer: plan-challenge
- [medium | parser module] Multi-block accumulation is undefined.
```

The canonical marker line is stored verbatim — the shadow matches against the
full text. Its grammar is fixed by
`.claude/skills/aitask-shadow/concern-format.md`: `- [priority | region] body`,
with the leading `- ` mandatory.

**Entry ids never repeat (correction 5).** Line 1 is a machine header carrying a
**never-decreasing** high-water mark; `add` assigns from it and advances it,
`remove` preserves it verbatim and never lowers it. Keeping the counter *inside*
the store file rather than in a sibling file makes the id reservation and the
entry write **one atomic render** — a sibling counter would open a crash window
between the two writes and could be lost independently, reintroducing reuse.

Two consequences worth stating:

- **`list` (default) strips the leading `<!-- … -->` line** before printing.
  This is a deliberate, minimal deviation from the parent plan's "prints the
  store file verbatim": the header is a machine artifact and has no business in
  the shadow's prompt context. `--machine` output is unaffected.
- **A store emptied by `remove` keeps its header** rather than being deleted, so
  it is never zero-byte and `ait_atomic_render` needs no
  `AIT_ATOMIC_ALLOW_EMPTY` escape (correction 1). Emptiness is decided by
  **"no `^### r` entry headers"**, so such a store still reports
  `NO_REJECTIONS`.
- **Bootstrap when the header is absent** (a store written before this field, or
  a corrupted first line): `next_id = max(entry id) + 1`. Self-healing, and the
  degraded case is documented in the helper header comment — the header is the
  authority whenever present.

**Root override.** The store root is `${AITASK_SHADOW_DIR:-.aitask-shadow}`,
following `aitask_explain_cleanup.sh:11` (`AITASK_EXPLAIN_DIR`) and
`aitask_agent_marks.sh:47` (`AITASKS_AGENT_MARKS_FILE`, from which it derives
the lock dir at `:51`). Two reasons, both load-bearing: it makes the test suites
hermetic without `cd`-ing into a fake repo root, and it gives `prune`'s own-root
`realpath` base a single source shared with the data path — a base keyed to the
default while data went elsewhere would guard nothing.

## Steps

### Pre-phase (risk mitigations)

These land in `tests/test_shadow_rejected.sh` (step 6),
`tests/test_archive_shadow_prune.sh` (step 7), and — for
`archival_prune_nonblocking` — the helper's timeout constants (step 1) and the
archive hook (step 4). Each is name-labeled so the `## Risk` cross-references
resolve regardless of later reordering.

1. **[contended_append_negative_control]** Add a two-writer contention test:
   fire two concurrent `add` invocations against the same task store
   (background jobs, distinct marker lines), `wait`, then assert **both**
   entries landed with **distinct** ids — no lost update. Dump per-contender
   stdout/stderr on an anomaly so a rare race is diagnosable rather than an
   anonymous flake (`test_agent_marks_concurrency.sh:58-64`).
   (Inherited from the t1427 decomposition plan.)

   **Negative control — fixture-local, never a runtime bypass, and
   deterministic.** Two properties this control must have:

   *(a) The shipped helper carries **no** mechanism that can skip the lock.*
   `lib/registry_lock.sh` states "Never proceed unlocked" as design invariant 1
   and "do NOT relax"; an env-gated no-op would let any externally set variable
   silently reintroduce lost updates in production. No existing test in this
   repo takes that shortcut — `tests/test_gate_lock_characterization.sh` and
   `tests/test_agent_marks_concurrency.sh` both drive lock behaviour purely
   from the fixture.

   *(b) The forced loss is **not** left to timing.* Two unsynchronized writers
   may serialize by luck on a quiet or loaded host, so "run it N times and hope
   for a collision" is a flaky assertion. The interleave is forced explicitly.

   Build the control as a **throwaway tree with two substituted libs**
   (`$TMP/negctrl/`):

   - Copy `aitask_shadow_rejected.sh` **unmodified**, plus
     `lib/terminal_compat.sh` **unmodified**.
   - Stub `lib/registry_lock.sh`: `registry_lock_acquire` returns 0 **without**
     creating the lock dir; `registry_lock_release` returns 0. Keep the
     `_AIT_REGISTRY_LOCK_LOADED` guard so sourcing semantics match.
   - Stand-in `lib/atomic_write.sh`: `source` the **real** library by absolute
     path (so nothing is duplicated), then redefine **only** `ait_atomic_render`
     to hit a barrier before doing exactly what the original does, reusing the
     real `ait_atomic_resolve` / `ait_atomic_tmp` / `ait_atomic_commit` /
     `ait_atomic_discard` primitives (all separately callable —
     `atomic_write.sh:69,100,119,141`). `ait_atomic_render` is the correct
     seam: `add` reads the store and computes the next id **before** calling
     it, so its first line is precisely "both writers have read, neither has
     committed".

   The barrier is a counted rendezvous on a fixture directory — each writer
   touches `$NEGCTRL_BARRIER_DIR/$$.ready`, then polls until two `.ready` files
   exist, with a **bounded** wait (~10s) that proceeds rather than hanging the
   suite:

   ```bash
   _negctrl_barrier_wait() {
       local d="${NEGCTRL_BARRIER_DIR:?}" deadline
       mkdir -p "$d"; : > "$d/$$.ready"
       deadline=$(( $(date +%s) + 10 ))
       while [ "$(find "$d" -maxdepth 1 -name '*.ready' | wc -l)" -lt 2 ]; do
           [ "$(date +%s)" -ge "$deadline" ] && return 0   # fail open, never hang
           sleep 0.02
       done
   }
   ```

   The helper resolves its libs via
   `SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"` +
   `source "$SCRIPT_DIR/lib/…"`, so the copy picks both substitutions up with
   **zero** edits to the helper, and nothing under `.aitask-scripts/` is
   modified — no restore step, and no path by which the control leaks into a
   normal run. (Correction 3's trimmed source list is what keeps this tree to
   four files.) The two substituted libs are two halves of **one** characterized
   condition — "unsynchronized concurrent read-modify-write" — not two
   independent mutations.

   **Assert the exact forced outcome, not merely a failure.** Against an empty
   store both writers read the same snapshot, both compute `next_id = 1`, and
   both render a one-entry file; the second `mv` wins. So the control must
   assert the store ends with **exactly one** `### r` entry, with id **`r1`**,
   and `<!-- next_id: 2 -->`. Also assert **both** `.ready` files exist
   afterwards, so a barrier that timed out and failed open cannot masquerade as
   a passing control. A bare non-zero exit is **not** accepted as the signal — a
   crash, a missing lib, or an unwritable temp would produce that too.

   **The real-lock side needs no barrier and no repetition.** Serialization is
   guaranteed by the mutex, not by timing: the second writer cannot read until
   the first has committed, so it necessarily sees `next_id = 2`. Assert
   **exactly two** entries with distinct ids `r1` and `r2`. (A barrier on this
   side would deadlock — B would block on the lock while A blocked on the
   barrier — which is itself the demonstration that the lock is doing the
   serializing.)

   Document the negative-control run in Final Implementation Notes.

2. **[entry_id_no_reuse]** Add the remove-then-add regression: seed `r1`+`r2`,
   `remove r2`, `add` a new marker, then assert the new entry's id is **`r3`,
   not `r2`**, and that `<!-- next_id:` reads `4`. Extend it across a full
   drain: remove **every** entry, add one more, assert the id still advances.
   Assert too that `remove` leaves the header untouched. This is the pin for
   correction 5 — without it a stale `remove` from a second TUI session
   un-rejects the wrong concern, and the parent plan descopes exactly the
   staleness handling that would otherwise catch it.

3. **[archival_prune_nonblocking]** Pin `PRUNE_LOCK_TIMEOUT=2` in
   `aitask_shadow_rejected.sh` (distinct from `MUTATE_LOCK_TIMEOUT=10`), and add
   a prune-vs-add coordination test: hold `$LOCK_DIR` with a live pid, assert
   `prune` prints `LOCK_BUSY`, exits **3**, leaves the store byte-identical
   (`cmp -s`), and returns in well under the mutation timeout. Together with
   pre-phase 5's dry-run case this pins that a contended or dry-run store can
   never stall or corrupt archival.

4. **[empty_store_removal_guard]** Add a test that `remove`-ing the **last**
   remaining entry exits 0, emits `REMOVED:`, leaves a non-zero-byte
   header-only file, and that a subsequent `list <id> --machine` reports
   `NO_REJECTIONS` while plain `list` prints nothing (header stripped). This is
   the regression pin for the `ait_atomic_render` zero-byte refusal
   (`atomic_write.sh:168`).

5. **[archive_hook_per_site]** Add `tests/test_archive_shadow_prune.sh` (step 7)
   covering **each of the three call sites in isolation** — plain parent
   archival, child archival, and the automatic parent archival that fires when
   the last child completes — plus `--dry-run` preservation. Each case seeds a
   store for the id under archival **and** an unrelated store that must
   survive, so a hook wired to the wrong id fails the test. Per-site isolation
   is the point: one combined assertion would pass while two of the three sites
   were missing.

6. **[own_root_guard_reachable_trigger]** Test prune's own-root refusal at the
   guard's real surface: symlink `$AITASK_SHADOW_DIR/9999` to a directory
   **outside** the root, seed a file in it, assert `prune 9999` refuses and the
   outside file **still exists**. Assert separately that the id regex rejects
   `../x` with exit 2. Two distinct guards, one test each — a crafted traversal
   id alone never reaches the `realpath` check and would prove nothing.

### Main implementation

1. **`.aitask-scripts/aitask_shadow_rejected.sh`** (new; `#!/usr/bin/env bash`,
   `set -euo pipefail` — read `aidocs/framework/shell_conventions.md` first).

   Sources **`lib/terminal_compat.sh`, `lib/registry_lock.sh`,
   `lib/atomic_write.sh` only** (see correction 3 — no `task_utils.sh`).

   - **Paths.** `SHADOW_DIR="${AITASK_SHADOW_DIR:-.aitask-shadow}"`;
     `store_dir="$SHADOW_DIR/$task_id"`; `store_file="$store_dir/rejected.md"`;
     `LOCK_DIR="${store_file}.lockd"` (derived from the data path, per
     `aitask_agent_marks.sh:51`).
   - **Task-id validation**, mirroring `aitask_shadow_context.sh:75-86`: strip a
     leading `t`, require `^[0-9]+(_[0-9]+)?$`. On failure print
     `Error: invalid task id: '<arg>' (expected N, tN, N_M, or tN_M)` to stderr
     and **exit 2** — the one hard error. Do **not** call `die` (exit 1).
   - **Exit codes** (copy `aitask_agent_marks.sh:31-34`): `0` ok, `2` usage /
     malformed id / no valid input, `3` `LOCK_BUSY` (nothing written), `4`
     error.
   - **Lock-or-busy wrapper**, modeled on `aitask_agent_marks.sh:74-84`:
     `mkdir -p "$store_dir"` first (`registry_lock_acquire` uses a plain
     `mkdir "$dir"`, so the parent must exist), then
     `registry_lock_acquire "$LOCK_DIR" "$timeout" || { echo LOCK_BUSY; exit 3; }`.
     Release rides the acquire-installed `EXIT` trap
     (`registry_lock.sh:69`); `atomic_write.sh` installs no trap of its own
     (deliberately — see its header), so there is no contention.
   - **Lock timeouts:** `MUTATE_LOCK_TIMEOUT=10` for `add`/`remove`;
     `PRUNE_LOCK_TIMEOUT=2` — prune runs inside `aitask_archive.sh`, and
     archival must never stall behind a contended shadow store.
   - **Header helpers.** `_read_next_id <file>` → the `<!-- next_id: N -->`
     value, falling back to `max(entry id)+1` (and to `1` for an absent store).
     `_render_header <n>` emits the header line plus a blank line. Both used by
     `add` and `remove` so the header has exactly one writer shape.

   Subcommands:

   - **`add <task_id> [--producer <name>]`** — read **all** of stdin first,
     discard blank / whitespace-only lines, and validate each remaining line
     against `^- \[` (the loose marker shape; full parsing is
     `concern_parser.py`'s job). **Fail before taking the lock** (correction 7):
     a non-conforming line, or **zero valid lines** (empty or whitespace-only
     stdin), prints an explanatory stderr message and exits **2**, having
     acquired nothing and written nothing. Sanitize `--producer` **at the write
     site**: strip/reject `|` and newlines (delimited encoding is undecidable
     on read); empty/absent → `unknown`.

     Then the locked RMW: acquire → read current file (missing = empty) →
     `next=$(_read_next_id …)` → assign `r$next … r$((next+n-1))` → render the
     **entire** new content (header advanced to `next+n`, old body, new blocks)
     through `ait_atomic_render`. The header advance and the entry write are one
     render, so an id is never handed out twice. Renderer guards every fallible
     command with `|| return 1` and uses an explicit `if`, never
     `[[ … ]] && echo` as its last command (`aitask_gate_pass.sh:99-106`;
     renderers must not rely on `set -e`). Output `ADDED:<n>`.

   - **`list <task_id> [--machine]`** — **no lock** (atomic rename gives
     whole-old-or-whole-new reads). Default: print the store body with the
     leading `<!-- … -->` header line (and the blank line after it) stripped.
     `--machine`: one `REJECTED:<id>|<ts>|<producer>|<marker line>` per entry —
     **marker line last**, because it contains `|`; consumers parse with
     `split('|', 3)`. Emptiness is decided by **"no `^### r` entry headers"**,
     so a header-only store still reports the `NO_REJECTIONS` sentinel. All
     resolution outcomes **exit 0** (`aitask_shadow_context.sh` line-protocol
     convention).

   - **`remove <task_id> <id>...`** — locked RMW; drop the named entry blocks.
     Ids accepted with or without the `r` prefix; normalize. Emits
     `REMOVED:<csv>` for found ids and `NOT_FOUND:<csv>` for missing ones (both
     lines may appear). **The header is carried through verbatim and never
     lowered**, so removing the highest entry cannot free its id for reuse
     (correction 5). A store emptied of all entries keeps its header and is
     therefore never zero-byte — no `AIT_ATOMIC_ALLOW_EMPTY` needed, and no
     file deletion (which would drop the high-water mark). TUI-invoked
     machinery, not a documented user-facing CLI.

   - **`prune <task_id>`** — lock-coordinated delete of the task's store dir.
     **Order matters** (correction 6):
     1. **Absence check first, before any `realpath`:**
        `[[ -d "$store_dir" ]] || { echo "PRUNED:absent"; exit 0; }`. This is
        the normal first-archive path in a repo that has never created
        `.aitask-shadow/`, where canonicalizing a two-level-missing path fails
        and `set -e` would abort.
     2. **Own-root check** (pattern `aitask_explain_cleanup.sh:78-84`), using
        the repo's fallback idiom from `:52` so a canonicalization failure
        degrades instead of aborting:
        `base=$(realpath "$SHADOW_DIR" 2>/dev/null || echo "$SHADOW_DIR")`,
        `canonical=$(realpath "$store_dir" 2>/dev/null || echo "$store_dir")`;
        refuse (stderr + exit 4) unless `canonical == "$base"/<task_id>`.
     3. Acquire the same registry lock with `PRUNE_LOCK_TIMEOUT`. Busy →
        `LOCK_BUSY`, exit 3, **deleting nothing**.
     4. Under the lock, remove the dir's regular files —
        `find "$store_dir" -maxdepth 1 -type f -exec rm -f {} +`. `-type f`
        skips the held `.lockd` (a directory) and also sweeps any stale
        `.rejected.md.XXXXXX` staging temp left by a crashed writer, which a
        bare `rm -f rejected.md` would strand and which would then defeat the
        `rmdir` in step 6.
     5. `registry_lock_release "$LOCK_DIR"` (removes the `.lockd`).
     6. Finish with plain `rmdir "$store_dir" 2>/dev/null || true` — **never
        `rm -rf`** — so a concurrent waiter's freshly re-created lock survives;
        the dir is then simply left behind and is re-prunable.
     Output `PRUNED:<task_id>`. A post-prune `add` lazily recreating the dir is
     accepted and documented in the helper header comment: prune runs at
     archival, any later prune finishes the job, and resurrection is bounded to
     explicitly re-added entries.

   **Scope note for the header comment:** the own-root guard protects `prune`.
   `add`/`remove` write through `ait_atomic_resolve`, which follows a file
   symlink chain by design (`atomic_write.sh:69-87`) — the store is local-only
   and git-ignored, so a symlinked `rejected.md` is out of scope, not a hole to
   plug here.

2. **`.aitask-scripts/aitask_setup.sh`** — add `setup_shadow_store_gitignore()`
   immediately after `setup_gate_logs_gitignore` (which spans 1959–1986; insert
   at 1987), same shape: `grep -qxF ".aitask-shadow/"` idempotence, rationale
   comment `# Shadow concern-rejection store (per-task, local-only; pruned at archive)`,
   `info`/`success` messages, best-effort `git add .gitignore && git commit … || true`.
   Call it in the main sequence directly after `setup_gate_logs_gitignore`
   (line 3719), separated by `echo ""`.
   Read `aidocs/framework/aitasks_extension_points.md` before touching the
   install flow.

3. **Repo-root `.gitignore`** — add the comment + `.aitask-shadow/` line
   adjacent to the existing `.aitask-gates/` rule (line 19) in the same commit.
   The setup function only installs into *other* projects and fresh clones;
   `.gitignore` is not regenerated wholesale, so this repo's line is added
   deliberately.

4. **`.aitask-scripts/aitask_archive.sh`** — add a helper directly after
   `release_lock()` (which ends at line 192), mirroring its DRY_RUN-aware,
   best-effort shape:

   ```bash
   # --- Helper: prune shadow rejection store (best-effort, idempotent) ---
   prune_shadow_rejections() {
       local task_id="$1"

       if [[ "$DRY_RUN" == true ]]; then
           info "[dry-run] Would prune shadow rejection store for t$task_id"
           return
       fi

       "$SCRIPT_DIR/aitask_shadow_rejected.sh" prune "$task_id" >/dev/null 2>&1 || true
   }
   ```

   Call it immediately after **each** of the three `release_lock` sites
   (correction 4): `archive_parent` line 248 (`"$task_num"`), `archive_child`
   line 456 (`"$task_id"`, already `<parent>_<child>`), and the auto-parent
   archival at line 508 (`"$parent_num"`). Archival never blocks on it — a
   `LOCK_BUSY` prune leaves the store for a later prune.

5. **Whitelist** — `./.aitask-scripts/aitask_audit_wrappers.sh
   apply-helper-whitelist aitask_shadow_rejected.sh`, then
   `audit-helper-whitelist aitask_shadow_rejected.sh` must report no `MISSING`.
   Verified: all 5 touchpoints (1, 3, 4, 6, 7) are currently missing;
   alphabetical insertion lands after `aitask_shadow_context.sh`.

6. **`tests/test_shadow_rejected.sh`** (new) — self-contained bash test modeled
   closely on `tests/test_agent_marks_concurrency.sh`: `set -uo pipefail`,
   source `tests/lib/asserts.sh`, `PASS`/`FAIL`/`TOTAL` counters, `mktemp -d` +
   `trap cleanup EXIT`, `Results: N/M passed` summary, `exit 1` on any failure.
   Isolation is via `export AITASK_SHADOW_DIR="$TMP/shadow"` — no `cd`, so the
   real `.aitask-shadow/` is never touched.

   Main body (the six **Pre-phase (risk mitigations)** cases are written into
   this same suite — see that block, which is their single source of truth):

   - **add/list round-trip** — add two markers, `list` prints them without the
     header; ids `r1`/`r2` assigned in order.
   - **`--machine` protocol with `|`-laden bodies** — a body containing `|`
     round-trips intact when parsed with a 3-way split; the marker line is last.
   - **`NO_REJECTIONS` sentinel** — missing store, and a header-only store, both
     report it and **exit 0**.
   - **remove found/not-found** — `REMOVED:` and `NOT_FOUND:` both emitted for a
     mixed id list; ids accepted with and without the `r` prefix.
   - **add input validation** — a line not matching `^- \[` exits **2**;
     **empty stdin** and **whitespace-only stdin** each exit **2**, print no
     `ADDED:`, and leave the store byte-identical (correction 7). Assert the
     lock dir does not exist afterwards, proving the refusal happened before
     acquisition.
   - **malformed-id refusal** — `abc`, `1_2_3` each exit **2** and write
     nothing.
   - **LOCK_BUSY path** — hold `$LOCK_DIR` with a *live* pid
     (`test_agent_marks_concurrency.sh:104-108`; `registry_lock.sh` steals only
     a provably-dead holder), assert `add` prints `LOCK_BUSY`, exits **3**, and
     leaves the store byte-identical (`cmp -s`, not `md5sum` — macOS ships
     `md5`).
   - **prune happy path** — on a populated store: exit 0, `PRUNED:<id>`, dir
     gone. On a missing store dir: `PRUNED:absent`, exit 0. **With
     `$AITASK_SHADOW_DIR` itself absent**: `PRUNED:absent`, exit 0 — the
     first-archive case from correction 6, which must not abort.
   - **lock dir released** after every normal exit (`assert_dir_not_exists`).

   Each regression assertion must be proven able to exit 1 — flip one expected
   value during development, confirm the suite fails, revert the flip. Do not
   commit a flip.

7. **`tests/test_archive_shadow_prune.sh`** (new) — the per-site archive
   integration suite for `[archive_hook_per_site]`. Reuse the temp-repo fixture
   shape from `tests/test_archive_folded.sh:28-68` (`setup_fake_aitask_repo`
   from `tests/lib/test_scaffold.sh`, bare remote + clone, per-script `cp` into
   `.aitask-scripts/`). **Copy `aitask_shadow_rejected.sh` and its three sourced
   libs** (`terminal_compat.sh`, `registry_lock.sh`, `atomic_write.sh`) into the
   fixture — the hook is `|| true`, so an un-copied helper would silently make
   every case vacuous. Guard against exactly that with a fixture pre-check
   asserting the helper is present and executable before the first case runs.

   Four cases, each seeding the store for the id under archival **and** a
   decoy store for an unrelated id that must survive:
   - **parent archival** (`aitask_archive.sh 30`) → `.aitask-shadow/30/` gone,
     decoy intact.
   - **child archival, parent still has siblings** (`… 10_1` with
     `children_to_implement: [t10_1, t10_2]`) → `.aitask-shadow/10_1/` gone,
     **`.aitask-shadow/10/` still present** (the parent did not archive).
   - **automatic parent archival** (`… 20_1` as the last child) → **both**
     `.aitask-shadow/20_1/` and `.aitask-shadow/20/` gone.
   - **`--dry-run`** → the store survives untouched and the output carries the
     `[dry-run] Would prune` line.

   The second and third cases are what distinguish a hook wired at only one of
   the three sites; the decoy is what distinguishes a hook passing the wrong id.

## Reference patterns (read before writing code)

- `.aitask-scripts/aitask_agent_marks.sh:31-84` — exit codes, lock-dir
  derivation, lock-or-busy wrapper, `mkdir -p` of the lock parent.
- `.aitask-scripts/aitask_gate_pass.sh:99-108` — `ait_atomic_render` renderer
  shape (explicit `if`, never `[[ … ]] && echo` last).
- `.aitask-scripts/lib/registry_lock.sh:39-88` — acquire/steal/release (mkdir
  mutex, owner token, dead-PID-only steal, EXIT trap installed at :69).
- `.aitask-scripts/lib/atomic_write.sh` header + `:159-174` — reader-visible
  atomicity is NOT writer serialization (hence the lock), the
  renderers-must-not-rely-on-`set -e` rule, and the zero-byte refusal.
- `.aitask-scripts/aitask_explain_cleanup.sh:11, 51-52, 78-84` — env-overridable
  root, the `realpath … || echo` fallback idiom, and the own-root prefix guard.
- `.aitask-scripts/aitask_shadow_context.sh:75-86` — task-id validation and the
  exit-0 line-protocol convention.
- `tests/test_agent_marks_concurrency.sh` — the contention / LOCK_BUSY /
  dead-holder test shapes step 6 mirrors.
- `tests/test_gate_lock_characterization.sh` — the repo precedent that lock
  negative controls are driven **from the fixture** (pre-held real locks),
  never by a bypass compiled into the shipped script.
- `tests/test_archive_folded.sh:28-68` + `tests/lib/test_scaffold.sh` — the
  temp-repo archive fixture step 7 reuses.
- `.claude/skills/aitask-shadow/concern-format.md` — the canonical marker
  grammar (`- [priority | region] body`; leading `- ` mandatory).
- `aidocs/framework/aitasks_extension_points.md` — before touching
  `aitask_setup.sh` / the install flow.
- `aidocs/framework/shell_conventions.md` — shebang, `set -euo pipefail`, error
  helpers, platform encapsulation.

## Verification

- `bash tests/test_shadow_rejected.sh` — all green; summary printed; each
  regression proven able to exit 1.
- `bash tests/test_archive_shadow_prune.sh` — all four per-site cases green.
- `shellcheck .aitask-scripts/aitask_shadow_rejected.sh` clean.
- `shellcheck .aitask-scripts/aitask_archive.sh .aitask-scripts/aitask_setup.sh`
  — no new findings.
- `bash tests/test_archive_folded.sh` and the other `tests/test_archive_*.sh`
  suites still green — the prune hook must not perturb them.
- `./.aitask-scripts/aitask_audit_wrappers.sh audit-helper-whitelist
  aitask_shadow_rejected.sh` — no `MISSING` lines.
- Manual smoke from the repo root:
  `echo '- [high | test region] body' | ./.aitask-scripts/aitask_shadow_rejected.sh add 9999 --producer manual`,
  then `list 9999`, `list 9999 --machine`, `remove 9999 r1`, re-`add`, confirm
  the new id is `r2` (not a reused `r1`), then `prune 9999`; confirm
  `git status --porcelain` stays empty throughout (i.e. `.aitask-shadow/` is
  genuinely ignored).

## Risk

### Code-health risk: medium

- `aitask_archive.sh` is a load-bearing path and gains a new call at three
  sites; a prune that blocks or deletes under `--dry-run` would damage
  archival · severity: medium · → mitigation: inline pre-phase
  archival_prune_nonblocking
- The hook could be wired at one site and silently omitted at the other two —
  `|| true` plus a per-script test fixture hides it from every existing suite ·
  severity: medium · → mitigation: inline pre-phase archive_hook_per_site
- The `ait_atomic_render` zero-byte refusal makes "remove the last entry" fail
  **silently** — the command reports success shape while the entry survives ·
  severity: medium · → mitigation: inline pre-phase empty_store_removal_guard
- A concurrent second writer (`ait monitor` and `ait minimonitor` both open on
  the same followed agent) could lose an append if the lock/atomic-write
  composition is wrong · severity: medium · → mitigation: inline pre-phase
  contended_append_negative_control
- Whitelist/gitignore edits span 6 config files; mechanical, but a partial
  application leaves the helper unusable from a skill · severity: low ·
  → mitigation: covered by Verification (`audit-helper-whitelist` reports no
  MISSING)

### Goal-achievement risk: medium

- Reusable entry ids break the store's identity contract: a stale `remove` from
  a second TUI session un-rejects a *different* concern, and the parent plan
  explicitly descopes the staleness handling that would otherwise catch it ·
  severity: high · → mitigation: inline pre-phase entry_id_no_reuse
- The own-root `realpath` guard is shadowed by the task-id regex, so the
  originally-specified negative control would pass without ever exercising it —
  a guard believed tested but not · severity: medium · → mitigation: inline
  pre-phase own_root_guard_reachable_trigger
- `prune` aborting on the first archive in a fresh repo, and `add` reporting
  success on empty input, are both silent-wrong-behavior paths the original
  spec left undefined · severity: medium · → mitigation: specified in step 1
  (absence-check-first; pre-lock input validation) and pinned by the step 6
  cases

### Planned mitigations
- timing: pre-phase | name: contended_append_negative_control | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: concurrent-writer lost update | desc: two-writer contention test asserting exactly two entries with distinct ids, plus a fixture-local negative control in a throwaway tree that stubs the lock library and injects a rendezvous barrier at ait_atomic_render to force the interleave deterministically — asserting the exact one-entry r1 outcome; the shipped script carries no runtime lock bypass
- timing: pre-phase | name: entry_id_no_reuse | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: reusable entry ids letting a stale remove un-reject the wrong concern | desc: remove-then-add regression asserting the next id advances past the removed one and the never-decreasing header is preserved, including a full-drain case
- timing: pre-phase | name: archival_prune_nonblocking | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: prune stalling or deleting inside the archival path | desc: pin PRUNE_LOCK_TIMEOUT=2 and test that a contended prune exits 3 fast deleting nothing
- timing: pre-phase | name: empty_store_removal_guard | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: silent remove failure on the last entry | desc: test that removing the last entry succeeds leaving a header-only store that reports NO_REJECTIONS, pinning the ait_atomic_render zero-byte behaviour
- timing: pre-phase | name: archive_hook_per_site | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: low | addresses: prune hook missing or mis-wired at one of three archive call sites | desc: new tests/test_archive_shadow_prune.sh covering parent, child, auto-parent and dry-run in isolation with a decoy store and a fixture pre-check that the helper was copied
- timing: pre-phase | name: own_root_guard_reachable_trigger | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: own-root guard shadowed by the id regex | desc: reach the realpath guard via a symlinked store dir outside the root and assert prune refuses; assert the id regex separately

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
