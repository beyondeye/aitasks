---
Task: t2301_reclaim_guard_dirs_left_by_sigkilled_test_runs.md
Base branch: main
Output branch: main
---

# t2301 — Reclaim guard dirs left by SIGKILLed test runs

> **Status: DRAFT — not approved.** Saved on 2026-11-15 when the user stopped
> the session at plan approval ("save plan and abort"). The design, the risk
> evaluation and the mitigation dispositions were confirmed during planning.
> The plan as a whole still needs approval on the next pick. No
> `plan_approved` gate was recorded, and no mitigation task was created.

## Context

`tests/lib/tmpdir_guard.sh` (t2290) gives `tests/run_all_python_tests.sh` and
`tests/run_shell_test.sh` a private per-run `TMPDIR` (`ait_<label>_<pid>_XXXXXX`)
and removes it on a normal exit and on INT/TERM/HUP. A SIGKILLed guarding shell
runs no handler, so its dir stays. The phase's process group can outlive it and
keep writing there. Today `tmpdir_guard_begin` only **reports** such dirs.

Goal: reclaim them automatically, but only on **positive evidence** that
nothing can still use them. Anything unverifiable is kept and reported.

**User decision (planning, 2026-11-15):** a process whose cwd/fd/environ cannot
be read is a holder of unknown state, and its dir is kept. Process start time
does not rule out later file access or descriptor transfer, so it is not used to
excuse such a process. Any relaxation needs stronger evidence. Document the
limitation: on a non-root Linux host under systemd, `sd-pam` and other
non-dumpable or other-uid processes are always uninspectable, so there a
reclaim effectively happens only for a root run (CI containers, for example) or
on a host where every process is inspectable.

## Design

### Run metadata (writer side)

A file **inside** the guard dir: `$_TG_DIR/.ait_guard_meta`. Line-oriented,
strictly parsed:

```
ait_tmpdir_guard_meta 1
owner <pid> <kind> <token>        # from get_pid_identity "$$" (proc|bsdinfo|ps|none)
phase_start <seq>                 # appended by tmpdir_guard_run BEFORE the fork
phase <seq> <pgid>                # appended right AFTER the fork ($! == pgid under set -m)
```

- `tmpdir_guard_begin` writes the header and the owner line right after
  `mktemp -d`, before the stale-dir scan. If the write fails, it prints a
  one-line warning ("run metadata not recorded — if this run is killed its
  dir will be kept") and continues. Nothing else changes.
- `tmpdir_guard_run` (guarded mode only) bumps `_TG_PHASE_SEQ`. It appends
  `phase_start` before launching the phase and `phase <seq> <pgid>` after.
  The two-line protocol makes a phase whose pgid was never recorded detectable
  (owner killed between fork and write, or a failed append). The reader treats
  that as unverifiable instead of silently missing a group.
- `_tg_expected_entry` gains `.ait_guard_meta`, so a clean run still reports
  nothing. Case (b) already pins this.
- Owner identity reuses `get_pid_identity` and `lock_holder_liveness` from
  `.aitask-scripts/lib/pid_anchor.sh`. The guard sources it via
  `$(dirname BASH_SOURCE)/../../.aitask-scripts/lib/pid_anchor.sh`, which is
  idempotent and side-effect free. If the file is missing, the guard records
  `owner <pid> none -`, so the reader returns `owner-unverified` unless the pid
  is confirmed absent.

### Reclaim verdict (reader side)

Replace the report-only loop in `tmpdir_guard_begin` with
`_tg_stale_verdict <dir> <name_pid>`, which echoes one of `live`, `reclaim` or
`keep:<reason>`. The steps run in order, and the first verdict wins:

1. **Metadata.** If it is missing: `live` when `kill -0 <name_pid>` succeeds
   (silent, as today), else `keep:no-metadata` (pre-metadata dirs). An
   unreadable file, a bad header or version, an unknown line, a malformed
   field, or an owner pid ≠ the pid in the dir name gives
   `keep:metadata-unreadable`.
2. **Owner.** `lock_holder_liveness <pid> <token> <kind>`: `alive` → `live`
   (silent: a concurrent run); `unknown` → `keep:owner-unverified`; `dead`
   continues. A recycled pid fails the token match and reads `dead`, so it
   never counts as alive. A weak `ps` token never reads `alive`, and an
   existing pid with a weak token reads `unknown`, so the dir is kept.
3. **Phases.** A `phase_start` without its `phase` line gives
   `keep:phase-unrecorded`. For each pgid, `LC_ALL=C kill -0 -- -<pg>`:
   success or "not permitted" → `keep:pgid-live:<pg>`; "No such process"
   continues; anything else → `keep:pgid-unverified:<pg>`. This covers the
   dead-wrapper-with-surviving-writer case.
4. **Holders.** This step runs only for dirs that passed steps 1–3. One scan
   covers all such candidates.
   - **Linux (`$_TG_PROC_ROOT`, default `/proc`, has `[0-9]*` entries).** For
     each process: a zombie (stat state `Z`) holds nothing and is skipped, and
     a process gone mid-scan is skipped. The scan collects:
     - `readlink` of `task/*/cwd` and `fd/*` (fd dir must be `-r -x`; one
       retry on a transient failure),
     - `environ` and `cmdline` (via `mapfile -d ''`).

     If any candidate path occurs as a substring → `keep:held:<pid>`. If any of
     those reads fails while the process still exists, the process counts as
     uninspectable. After the loop, the scan also checks the `Path` column of
     `net/unix` → `keep:held:socket` (an unreadable `net/unix` counts as
     uninspectable). A candidate with no holder is reclaimed only when **zero**
     processes were uninspectable; otherwise
     `keep:holder-unverified:<n>`. "Held" takes precedence over "unverified"
     in the reason.
   - **Off Linux.** If euid is 0 and `lsof` is present, run
     `lsof -w -F p +D <dir>`: a `p` line → `keep:held:<pid>`; exit 1 with
     empty stdout and stderr → none; anything else → unverified. A non-root
     lsof cannot see other users' processes, so its negative is never
     accepted: `keep:holder-unverified:lsof-not-root`. With no lsof:
     `keep:no-holder-scan`.
5. **Reclaim.** `chmod -R u+w`, then `rm -rf`. A dir that still exists
   afterwards gives `keep:remove-failed`.

**Reporting** (stderr, warn-only, at most 5 names per line):
- `TMPDIR GUARD: reclaimed <n> guard dir(s) left by killed runs under <base> (owner, recorded process groups and every process verified gone): <names>`
- `TMPDIR GUARD: <n> guard dir(s) from earlier runs remain under <base> (kept — not provably unused; remove by hand once no process uses them): <name>(<reason>) …`

`_TG_PROC_ROOT` is a **shell variable** (test seam), not an env var, so it
never leaks into nested runs. Set it after sourcing.

**Known residual gaps** (documented in the header, not fixed):
- the TOCTOU window between the scan and the `rm`;
- threads with an unshared fd table (only `/proc/<pid>/fd` is scanned; cwd is
  scanned per thread);
- processes in another mount namespace whose paths differ;
- a process that later re-derives the path from nowhere it currently holds.

## Implementation steps

1. **`tests/lib/tmpdir_guard.sh`**
   - Source `pid_anchor.sh` (guarded by `-r`, as in Design).
   - Add globals `_TG_META` (the file name constant), `_TG_PHASE_SEQ=0`, and
     `_TG_PROC_ROOT="/proc"`.
   - Add `.ait_guard_meta` to `_tg_expected_entry`.
   - Add `_tg_meta_write_header`, called in begin after `mktemp`. Reset
     `_TG_PHASE_SEQ`.
   - Add `_tg_meta_parse <dir>`, which sets `_tg_m_owner_pid`, `_tg_m_kind`,
     `_tg_m_token` and `_tg_m_pgids[]`, and returns 0, 1 (missing) or 2
     (unreadable/malformed/phase-unrecorded, with the reason in a variable).
   - Add `_tg_pgid_state <pg>`, which returns `empty`, `live` or `unknown`.
   - Add `_tg_scan_holders <dir...>`, the Linux `/proc` scan plus `net/unix`.
     It fills an assoc array `dir → held:<pid>|held:socket` and an
     uninspectable count. Add `_tg_lsof_holders <dir>` for the off-Linux path.
   - Add `_tg_stale_verdict` and rework the begin loop into two passes: steps
     1–3 per dir, one holder scan for the survivors, then reclaim and report.
   - In `tmpdir_guard_run`, add the `phase_start` and `phase` appends when
     `_TG_DIR` is set and not done (`>> ... 2>/dev/null || true`).
   - Rewrite the header "NOT COVERED" block as a "KILLED RUNS" section:
     metadata, the evidence ladder, the strict-uninspectable rule with the
     systemd/non-root consequence, and the residual gaps.
2. **`tests/test_tmpdir_guard.sh`.** Keep case (f), now also asserting the
   `no-metadata` reason. Add a helper `make_stale <label> <name_pid>
   [meta-lines...]` that builds `$BASE/ait_probe_<pid>_<suffix>` with a data
   file, and a helper `fixture_proc <dir>` that builds a fake proc root: one
   readable process (stat state `S`, `task/<pid>/cwd → /`, `fd/0 →
   /dev/null`, unrelated environ and cmdline) plus a `net/unix` with an
   unrelated path. Each probe runs `bash -c '. lib; _TG_PROC_ROOT=…;
   tmpdir_guard_begin probe; tmpdir_guard_end'`. New cases:
   - **(n) metadata is written:** after begin, `$TMPDIR/.ait_guard_meta` has
     the header and `owner $$ …`. After `tmpdir_guard_run true`, it has
     `phase_start 1` and `phase 1 <n>`. A clean run still reports nothing.
   - **(o) reclaimed when fully dead:** dead owner (`dead_pid_fixture` from
     `tests/lib/proc_fixtures.sh`), a dead pgid, and the fixture proc root.
     Expect the dir gone and the "reclaimed" line naming it.
   - **(p) recycled owner pid:** the owner pid is a live `sleep` with a wrong
     token, so it reads dead. With the fixture proc root the dir is
     reclaimed. Control: the same live pid with its real token gives `live`,
     which is silent and leaves the dir untouched.
   - **(q) kept with a live pgid member, end to end:** run the real wrapper
     with the `writer` stub in the background and SIGKILL the wrapper. The
     writer survives in its group. The next guarded run (fixture proc root)
     keeps the dir with `pgid-live:<pg>`, and the data is intact. Then kill
     the writer group, and the following run reclaims the dir. This exercises
     the writer side to the reader side.
   - **(r) kept with a cwd holder (real /proc):** start a `sleep` with its cwd
     in the stale dir, with metadata, a dead owner and a dead pgid. Expect
     `held:<sleep_pid>` and the dir kept.
   - **(t) other holders via the fixture:** an fd symlink into the dir, an
     environ entry naming it, and a `net/unix` path under it each keep the dir
     (`held:<pid>`, `held:socket`).
   - **(u) uninspectable process keeps:** a fixture process whose `fd` dir is
     mode 000 gives `holder-unverified:1`. Skipped when euid is 0.
   - **(v) metadata problems keep:** a malformed header, a pid mismatch, and a
     `phase_start` without `phase` give `metadata-unreadable` and
     `phase-unrecorded`.

   Assertions run in the parent shell, with no `( … )` bodies, so the
   counters opt-in is not needed. Clean up every spawned pid through the
   existing `$WORK/pids` file.
3. **`CLAUDE.md`, "Hunting `/tmp` leaks" paragraph.** Add one sentence: guard
   dirs left by a killed run are reclaimed at the next guarded run only when
   provably unused; otherwise they are reported. See the header of
   `tests/lib/tmpdir_guard.sh`.
### Post-phase (risk mitigations)

1. [reclaim_guard_mutants] Run mutant controls in isolation. Copy
   `tests/lib/tmpdir_guard.sh`, `tests/test_tmpdir_guard.sh`,
   `tests/run_shell_test.sh`, `tests/lib/asserts.sh`,
   `tests/lib/proc_fixtures.sh` and `.aitask-scripts/lib/pid_anchor.sh` (plus
   anything else they source) into a scratch tree with the same relative
   layout. Never edit the worktree files. Then apply each mutant in turn with
   `sed` to the scratch `tmpdir_guard.sh` only, run the scratch
   `test_tmpdir_guard.sh`, and record the result:
   - M1: owner `alive` treated as `dead` → expect (p)-control to fail (the dir
     of a live owner is reclaimed);
   - M2: `_tg_pgid_state` always `empty` → expect (q) to fail;
   - M3: `held:` results ignored → expect (r) and (t) to fail;
   - M4: the uninspectable count ignored → expect (u) to fail (on non-root);
   - M5: `phase_start` without `phase` accepted → expect (v)'s
     phase-unrecorded assertion to fail.

   Each mutant must turn **only** its own target cases red. Every other case
   must stay green, which shows the signal is specific to that guard. Record
   the mutant/result table verbatim in the plan's Final Implementation Notes.
   If a mutant survives, add a test for it before committing.

4. **Step 9 (Post-Implementation):** commit
   `enhancement: Reclaim guard dirs left by SIGKILLed test runs (t2301)`
   with explicit paths only. Then archive via the workflow.

## Verification

- `bash tests/test_tmpdir_guard.sh`: all pass, including the new cases.
- `bash tests/run_shell_test.sh tests/test_claim_id.sh`: the guard still
  works, with no leftovers line for the meta file.
- `shellcheck tests/lib/tmpdir_guard.sh tests/test_tmpdir_guard.sh tests/run_shell_test.sh`
- `bash tests/run_all_python_tests.sh --test-dir <small dir>`, or the whole
  suite with `set -o pipefail`, to confirm the pyrun guard still begins, runs
  and ends cleanly. Read the last line for the verdict.
- Manual: SIGKILL a `run_shell_test.sh` with a writer stub under a scratch
  TMPDIR, and re-run to see the kept line with its reason.

## Risk

### Code-health risk: low
- A bug in the verdict ladder (owner, pgid or holder check) could delete a dir
  that a concurrent live run or an orphaned writer is still using. That breaks
  a parallel suite run with spurious ENOENT failures. · severity: low (residual: addressed by inline post-phase reclaim_guard_mutants, a per-guard mutant proof) · → mitigation: inline post-phase reclaim_guard_mutants
- When stale candidates pass steps 1–3, `tmpdir_guard_begin` gains a full
  `/proc` scan (about one fork per process, roughly 1s). This cost is only
  paid after a SIGKILL. · severity: low · → mitigation: none
- New coupling: a test library sources the framework's `pid_anchor.sh`. The
  source is guarded, and a missing file degrades to `owner-unverified`.
  · severity: low · → mitigation: none

### Goal-achievement risk: medium
- Under the user-chosen strict rule for uninspectable processes, reclaim
  practically never fires on a non-root systemd dev host (`sd-pam`), so the
  "reclaim automatically" goal is realized mainly for root/CI runs. The user
  accepted this knowingly, and it is documented. · severity: medium · → mitigation: stronger_holder_evidence_for_guard_reclaim
- The positive reclaim path is exercised against a fixture proc root, not the
  real `/proc`. The real-`/proc` cases only prove the keep directions.
  · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: reclaim_guard_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: Code-health — a verdict-ladder bug deleting an in-use dir | desc: Isolated scratch-copy mutants (owner, pgid, held, uninspectable, phase-unrecorded) must each turn only their own test cases red
- timing: after | name: stronger_holder_evidence_for_guard_reclaim | type: enhancement | priority: low | effort: medium | inline_risk: low | added_complexity: medium | addresses: Goal-achievement — reclaim practically inert on non-root systemd hosts under the strict uninspectable rule | desc: Research and prototype stronger evidence (per-run cgroup / systemd-run --user scope membership, or a narrowly privileged inspector) that would let a non-root host prove a guard dir unused without trusting process start time

## Post-Review Changes

### Change Request 1 (2026-11-19)
- **Requested by user:** six review findings, all verified CONFIRMED:
  1. both phase-metadata appends were best-effort — failing both left a valid
     header with zero pgids, so a killed run's surviving group was never checked;
  2. the holder scan trusted `/proc/[0-9]*` as complete — `hidepid=2/4` hides
     live processes from enumeration;
  3. the header writer used a truncating redirect on a derived sibling path — a
     planted symlink could redirect the write;
  4. the lsof fallback ran with `-w`, suppressing coverage warnings, then
     accepted exit 1 + empty output as "no holder";
  5. the unix-socket scan matched only full paths — a relative bind is listed
     by basename only (fd reads `socket:[inode]`), reproduced live;
  6. the owner token was accepted as any printable word — `proc invalid` makes a
     live owner compare unequal and read as recycled.
- **Changes made:**
  1. The `phase_start` intent line must be durable before the launch: a failed
     append (either one) runs `_tg_meta_invalidate` — `rm`, else `chmod 000`
     (needs neither space nor write permission) — and announces it. The reader
     additionally requires the metadata file and control dir to be owned by the
     user and the file to carry owner `rw` mode bits (checked with `find -perm`,
     not access(2), so root sees a chmod-000 invalidation too).
  2. `_tg_proc_view_complete`: the scan runs only when `<root>/mounts` lists the
     proc mount at the scan root with no `hidepid` other than `0/off/1/noaccess`;
     otherwise (or when unreadable) every candidate is `keep:proc-view-incomplete`.
  3. Metadata moved into a private control dir `<base>/.<dirname>.ait_guard_meta/`
     made by `mkdir -m 700` (exclusive, never follows a symlink), file `meta`.
     `_tg_meta_create` refuses any pre-existing path at that name.
  4. lsof runs without `-w`; any output other than a `p<pid>` line keeps the dir.
     `_TG_EUID` (shell variable) is the test seam for the root rule.
  5. `_tg_scan_unix_sockets` parses each `net/unix` row; a relative path or an
     unparseable row counts as uninspectable (keeps every candidate).
  6. `_tg_token_ok`: per-kind token shape (`proc` digits, `bsdinfo`
     `<sec>.<6 digits>`, `ps` `[A-Za-z0-9_:]+`, `none` `-`) on write and read.
  - Found while testing: a `while … done < file || return` loop's status is its
    last body command's, so a non-matching `[[ … ]] &&` read as a failed
    redirection; every such loop now ends its body with `:`.
- **Files affected:** `tests/lib/tmpdir_guard.sh`, `tests/test_tmpdir_guard.sh`
  (new: x/badtoken, x/badbsd, x/ctllink, x/metalink, x/mode000, x/readonly,
  x/livebad, v/relsock, v/badrow, (y) hidepid ×6 + noaccess control, (z) lsof
  ×4 with a fake lsof, (aa) both appends failing with a real SIGKILL ×2 modes,
  (ab) planted-symlink writer refusal ×2). 190/190 pass.
- **Mutants M6–M11** (one per finding), each in an isolated scratch copy, each
  turns its own cases red; M0 baseline green.

### Change Request 2 (2026-11-20)
- **Requested by user:** five further findings, all verified CONFIRMED:
  1. when the intent append AND both invalidation steps fail, the phase still
     launched inside the guard, and the surviving record (valid, zero pgids) was
     accepted;
  2. the reaper ran recursive chmod/rm without checking for mounts at or below
     a candidate (same-filesystem bind mounts included);
  3. `read`-based readers returned success on a read error after the open
     (environ/cmdline, metadata, net/unix, mounts);
  4. "@"-prefixed net/unix paths were treated as abstract — a FILE bound by the
     relative name "@x" prints identically (reproduced live);
  5. dropping `-w` leaves lsof warnings at the build default; pass `+w`.
- **Changes made:**
  1. `_TG_META_STATE` (ok / invalid / broken / none). A phase is launched inside
     the guard only when its intent is recorded or the record is confirmed
     invalid; `broken` (invalidation unconfirmed) runs this and every later
     phase OUTSIDE the guard (original TMPDIR), and `_TG_RAN_OUTSIDE` makes
     `tmpdir_guard_end` leave `_TG_LEFTOVER_COUNT` empty (strict fails it). The
     header write at begin routes a failure through the same invalidation.
  2. `_tg_mounts_under`: mount points (from `<proc-root>/mounts`, octal-escaped
     comparison; `mount` output off Linux) at or below the dir →
     `keep:mounted:<mp>`; unreadable/garbled table → `keep:mounts-unverified`;
     checked immediately before the recursive chmod/rm. `tmpdir_guard_end` also
     refuses to remove its own dir when a mount is found below it (only on a
     positive find, so an unreadable table keeps the old behaviour) — the same
     hazard existed there since t2290.
  3. `_tg_slurp` reads every file through `cat` (`&& printf x` sentinel), so a
     read error after the open fails; all parsers work on the slurped text.
  4. "@" rows count as unresolved, like relative rows.
  5. `lsof +w -F p +D`.
  - Performance: the line splitting moved to one `mapfile` per text
    (`_tg_lines`); peeling lines off a string was quadratic (1.4s for a
    1089-row net/unix → 0.08s). Full real-/proc scan here: 0.87s.
- **Tests:** v/atsock, v/sockdir, v/sockpartial, w/environdir, x/readerror,
  y/readerror, y/readpartial (selective `cat` fault injection via the probe's
  `P_PRELUDE`), z/+w, (ac) intent + both invalidations failing (normal run and
  real SIGKILL), (ad) mounts below/at/escaped-space/garbled + control + end().
  227/227 pass.
- **Mutants M12–M17** (outside-launch, reaper mount check, slurp error,
  "@"-as-abstract, `+w`, end() mount check) each red only their own cases;
  M1–M11 re-run on the final code, all still red; M0 green.
