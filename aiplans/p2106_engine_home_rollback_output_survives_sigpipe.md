---
Task: t2106_engine_home_rollback_output_survives_sigpipe.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2106 — `ait engine home --migrate`: recovery output survives a dead stdout reader

## Context

`home_rollback` and `home_on_signal` in `.aitask-scripts/aitask_engine.sh`
ignore INT/TERM/HUP during recovery but leave SIGPIPE at its default. If the
verb's stdout reader is gone (`… | head`, a buffering caller killed by the same
process-group signal), the verb finishes the rollback moves and then **dies on
its first `echo`** (exit 141). Consequences:

- the `HOME_SKIPPED` / `HOME_FAILED:rollback` / `HOME_STRANDED` /
  `HOME_RESTORE` lines are lost — on a blocked rollback they are the only
  record of where a stranded entry is and how to restore it;
- the stderr warnings that follow are never written;
- the EXIT trap (`home_release_lock`) does not run (death by a default-action
  signal skips it), so `$AITASKS_HOME/.home.lock` is left behind;
- the exit status is 141 instead of 2 / 128+signo.

Ignoring PIPE alone keeps the verb alive, but the lines still go into a dead
pipe — so the task's second suggestion (a durable record) is what actually
preserves the restore steps. Both are done here, pinned by a test.

Current-branch mode (profile `fast`): no worktree.

## Implementation

### 1. `.aitask-scripts/aitask_engine.sh`

a. **Ignore PIPE in recovery.** `home_rollback` and `home_on_signal`:
   `trap '' INT TERM HUP` → `trap '' INT TERM HUP PIPE`. Update the comment
   ("Recovery itself must not be cut short by a further signal — nor by a dead
   stdout reader: the moves are done by the time anything is printed").
   With PIPE ignored, a write to a dead pipe returns EPIPE. Inside
   `home_rollback` errexit is already suppressed (both call sites are
   `… || rc=$?` / `|| true`), but **`home_on_signal` itself is a trap handler
   running under `set -e`**: its `linked` branch (`echo "HOME_MIGRATED:…"`) and
   its `*)` branch (`echo "HOME_SKIPPED:interrupted:$sig"`) would make bash exit
   1 on EPIPE before `exit "$code"` — losing the 128+signo status. Every
   protocol write in `home_on_signal` therefore goes through `home_emit`
   (below), which never fails.

b. **Durable record of a blocked rollback.** New global, set in `cmd_home`
   after the trailing-slash normalisation (so it uses the one spelling of the
   root): `HOME_RECORD="$AITASKS_HOME/.home_restore"`, plus
   `HOME_RECORD_TMP=""`. (A dotfile: not a known tenant name, so preflight's
   `destination-exists` check never sees it.)

   New helpers next to `home_rollback`, with **write failure tracked across
   the whole record** (`HOME_RECORD_OK`):
   - `home_record_open` — `HOME_RECORD_TMP="$HOME_RECORD.tmp"` (a fixed name is
     safe: only the lock holder writes it; a leftover from a SIGKILLed run is
     truncated). Write (truncate) a header comment into it
     (`# <date> ait engine home --migrate: rollback blocked — run the
     HOME_RESTORE commands in order`). `HOME_RECORD_OK=1` on success, `0` on
     failure. The record is **one current, actionable block**: no earlier
     block is carried over (replaying an obsolete block's steps alongside new
     ones can nest and mis-restore entries).
   - `home_emit <line>` — when recording, `home_hook pre-record-append "$1"`
     (test seam), then append the line to the tmp; a failed append sets
     `HOME_RECORD_OK=0`. Then `printf '%s\n'` it to stdout. **Always returns
     0** — so it is safe under errexit in the signal handler.
   - `home_record_close` — only when `HOME_RECORD_OK=1` **and** `mv -f` onto
     `$HOME_RECORD` succeeds: print `HOME_RECORD:<path>` and `warn` that the
     steps are also saved there and that `ait engine home` shows the file
     until a later migration completes. The `mv` is the atomic replacement of
     any previous record, and it happens only after every new write
     succeeded. Otherwise remove the tmp, print **no** `HOME_RECORD:` line (an
     incomplete record is never published as complete), and `warn` that the
     restore steps could NOT be saved, so the `HOME_RESTORE` lines in the
     output are the only copy; when a previous `$HOME_RECORD` exists it is
     left untouched and the warning says explicitly that it describes an
     EARLIER attempt, not this one. Never changes the rollback's return value
     (still 2).

   In `home_rollback`, the stranded branch only (a full rollback prints and
   records nothing new — it still `echo`s `HOME_SKIPPED` + `HOME_ROLLED_BACK`):
   move the `HOME_SKIPPED:$reason` echo below the stranded check, then
   `home_record_open`, and route `HOME_SKIPPED`, `HOME_FAILED`, every
   `HOME_STRANDED`, and every `HOME_RESTORE` line through `home_emit`, then
   `home_record_close`, `return 2`. In `home_restore_steps` /
   `home_restore_root_steps` the `printf 'HOME_RESTORE:…%q…\n'` calls become
   `home_emit "$(printf 'HOME_RESTORE:…%q…' …)"` (%q never yields a raw
   trailing newline, so `$( )` loses nothing). Line order on stdout and the
   per-entry warnings are unchanged.

c. **Clear the record when a migration completes.** Both places that print
   `HOME_MIGRATED:` (normal finish and `home_on_signal`'s `linked` branch)
   first `rm -f -- "$HOME_RECORD"` — the layout it describes no longer exists,
   and following its steps through the new symlink would be wrong. In
   `home_on_signal` both the `linked` and the `*)` writes use `home_emit`
   (outside a recording, it is just a never-failing stdout write).

d. **Surface it in the report.** `home_report` prints
   `HOME_RECORD:<path>` when the file exists (read-only, after
   `HOME_SYMLINK`).

e. **Contract table** in the header: add the `HOME_RECORD:<path>` shape
   (class-2 `--migrate`, after the `HOME_RESTORE` lines, and in the report;
   removed by a completed migration), pinned by H22/H31; mention in the
   `HOME_FAILED` row that it is followed by `HOME_RECORD`.

`aitask_setup.sh` is **not** touched (dirty in the shared worktree from another
session; setup already lets the verb write to its own fds, and an extra
`HOME_RECORD:` line passes through verbatim).

### 2. `tests/test_aitasks_home.sh`

- **H22** (stdout visible): assert `hline HOME_RECORD:` =
  `HOME_RECORD:$AH/.home_restore`, and that the record's `^HOME_` lines equal
  stdout's `HOME_` lines minus the `HOME_RECORD:` line (record == what was
  printed). "nothing else left in the new root" becomes `.home_restore venv`.
- **H27 / H29 / H30**: "…leaving the new root empty" → the root holds only
  `.home_restore`.
- **New H31 — dead reader**, two variants (`rollback`: H22's post-moves stray +
  competitor → `legacy-root-not-empty`, want exit 2; `signal`: same competitor
  plus `kill -TERM "$PPID"` at post-moves → `home_on_signal`, want 143).
  Deterministic dead reader, no timing race: the verb runs as
  `bash "$ENG" home --migrate … | { exec 0<&-; : >"$gone"; }` — the reader
  closes its read end *before* creating the marker, and the post-moves hook
  waits (bounded, 200×0.05s) for the marker before returning, so every
  protocol write hits EPIPE. `rc=${PIPESTATUS[0]}`. Assert:
  - exit is 2 / 143 (not 141);
  - original venv intact at `$AH/venv`, competitor untouched, the other seven
    entries restored (`ls "$AH"` = `venv`), `no_lock` (EXIT trap ran);
  - `$AH/.home_restore` holds `HOME_FAILED:rollback|venv`,
    `HOME_STRANDED:venv|$AH/venv|$H/.aitask/venv` and two `HOME_RESTORE:venv`
    steps; stderr names the record path;
  - `ait engine home` reports `HOME_RECORD:$AH/.home_restore`;
  - running the record's steps restores the venv and keeps the competitor aside;
  - after removing the stray and the set-aside competitor, `--migrate` prints
    `HOME_MIGRATED:8`, the record is gone, and the report has no `HOME_RECORD:`.
- **H31 `linked` variant** — dead reader + `kill -TERM "$PPID"` at the
  `post-link` hook (after the reader is gone): exit **143** (not 1, not 141),
  the migrated layout is kept (`$H/.aitask` is `LINK:$AH`, the new root holds
  the original tree byte-identically), `no_lock`.
- **New H32 — a record append fails mid-way** (non-root only, SKIP otherwise,
  like H29/H30): H22's blocked-rollback scenario, plus a hook that on
  `pre-record-append HOME_STRANDED:*` does `chmod a-w "$HOOK_AH/.home_restore.tmp"`
  (header, `HOME_SKIPPED`, `HOME_FAILED` written; the rest fail). Assert: exit
  2, the stdout protocol lines are complete (`HOME_STRANDED`, two
  `HOME_RESTORE:venv`), **no** `HOME_RECORD:` line, no leftover `.tmp`,
  stderr says the steps could not be saved, tree state as in H22, `no_lock`.
  The case seeds `$AH/.home_restore` with an older record first: it must be
  byte-identical afterwards, and stderr must say it describes an earlier
  attempt.
- **H22 extension — an earlier record is replaced, not accumulated:** seed
  `$AH/.home_restore` with an older record before the run; afterwards the
  record holds only this run's header and lines (the record == stdout
  assertion above already pins that).
- Update the file header's case summary to mention H31.

## Verification

1. `bash tests/test_aitasks_home.sh` — all pass.
2. **Red proof (negative control):** copy `.aitask-scripts/` to the scratchpad,
   run H31's pipeline against (i) the unmodified HEAD engine and (ii) a mutant
   of the new engine with `PIPE` removed from both traps → exit 141, no
   `.home_restore`, lock left behind — i.e. H31 fails without the fix. Also
   mutants for the two review findings: (iii) `home_on_signal`'s `linked`
   write as a bare `echo` → the H31 `linked` variant exits 1, not 143;
   (iv) `home_record_close` ignoring `HOME_RECORD_OK` → H32 sees a published
   `HOME_RECORD:` line.
3. `shellcheck .aitask-scripts/aitask_engine.sh tests/test_aitasks_home.sh`.
4. `bash tests/test_install_engine_binary.sh` (other `aitask_engine.sh` verbs
   share the file).

## Step 9 (Post-Implementation)

Current branch — no merge; archive via `aitask_archive.sh 2106` after review
and commit.

## Risk

### Code-health risk: low
- New protocol line `HOME_RECORD:` and a new dotfile in `$AITASKS_HOME`; any consumer enumerating the root or matching every `HOME_` line could be surprised (setup only branches on exit class; tests updated) · severity: low · → mitigation: none
- Ignored PIPE is inherited by the `mv`/hook children of recovery; harmless (none write to pipes) · severity: low · → mitigation: none
- The record is replaced by each blocked rollback and removed only by a completed migration, so a user who restores by hand and then opts out of migration keeps seeing a stale record in the report · severity: low · → mitigation: none

### Goal-achievement risk: low
- None identified.
