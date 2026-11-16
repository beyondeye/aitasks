---
Task: t2299_3_sitrep_recovery_refresh_monitor_tui.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_1_*.md, aitasks/t2299/t2299_2_*.md, aitasks/t2299/t2299_4_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-16 11:32
---

# Plan: refresh, monitor tick and TUI routing for recovery items (t2299_3)

## Context

t2299_1 stores one `recover:t<N>` item per task, with the atomic `recovery-apply`
verb and the `incarnation` episode key. t2299_2 maintains those items from the
`harvest crashed` detector (`lib/sitrep_crash.py`, one ordered 9-row
`recovery_verdict`). This child:

- makes **refresh** re-check recovery items through that same verdict;
- runs the detector from the **monitor maintenance tick** and the **TUI `r`**;
- routes **`p`** on a crashed or orphan item to `/aitask-pick <N>`.

It is advisory only: nothing here reclaims, unlocks or edits task status.

## Verification record (2026-11-16, HEAD 41a72acd4)

- No target file is dirty. Since t2299_2, `sitrep_refresh.py` and `sitrep_crash.py` changed
  only in t2307 (TaskIndex status validation). All line anchors below were re-read.
- **Plan corrections (from the acknowledged t2299_2 note and re-reading the code):**
  1. There is no `read_tasks`. Use `read_locks(root)`, `read_active_tasks(root)` and
     `read_inactive_task(root, tid, TaskIndex(root))`. `recovery_verdict(lock, task,
     liveness)` takes `liveness_of(lock)` from the caller (`""` when there is no lock
     or the lock is an error).
  2. **User decision (2026-11-16): refresh follows the detector's rule.** A recovery
     item is written only when its state or outcome changes.
     - Row 1 (unreadable input), whole-input errors, check exceptions, timeouts and
       deadline-interrupted checks write **nothing**.
     - So `checked_at` stays "evidence last changed", and steady passes create no new
       revs.
     - This overrides the task file's "rows 1/2/4 → unknown" and "stamp every pass".
     - Rows 2 and 4 still map to `unknown`, exactly as the detector's `state_only` does.
  3. The outcome is `Verdict.outcome` (`format_outcome(category, evidence)`), the
     same string the detector writes. Alternating passes are therefore byte-stable by
     construction (detector precheck: `sitrep_crash.py:1225-1231`).
  4. **New-episode guard.** Suppose a stored row's freshly derived
     `episode_key(tid, lock, recorded)` differs from the item's recorded incarnation.
     Then the evidence belongs to a new claim whose context only the detector may
     write (`recovery-apply`). Refresh reports it `unverified` and writes nothing, so
     an outcome about claim B never sits on claim A's context.
  5. **Circular import.** `sitrep_crash` imports `sitrep_refresh` at module level,
     so refresh imports `sitrep_crash` lazily inside the recovery check, the same way
     `cmd_worker` imports `sitrep_harvest`. The TUI model also imports it lazily
     (it pulls in `gate_ledger`, `agent_sessions` and `pac`).
  6. **Shared timeout constant.** `HARVEST_CRASHED_TIMEOUT = 120.0` lives in
     `monitor/sitrep_close.py`, beside `HARVEST_ALL_TIMEOUT`, and both the monitor and
     the TUI import it. The measured cost is about 0.4 s per newly stored item cold and
     about 0.75 s steady, so 120 s covers about 250 new items in a single pass.
  7. **Fair progress without `checked_at` (user review 2026-11-16, blocking).**
     The problem: `order_targets` sorts by `checked_at`. A recovery item keeps its
     evidence stamp on unchanged, unverified and interrupted checks, so a stalled
     old recovery check would run first on every pass. It would starve every later
     target and break the PROGRESS guarantee (`sitrep_refresh.py:77-81`).

     **Fix: the refresh keeps its own attempt ledger for recovery targets.** It
     mirrors the PROGRESS rule exactly: every reached recovery target (finished or
     interrupted) gets the run's stamp, and ordering reads that stamp instead of
     `checked_at`. Task, push and trail targets keep `checked_at` unchanged.
     - The ledger is a scheduling hint, not store data, so it lives outside the
       store (one-writer rule):
       `<git common dir>/aitask-sitrep/refresh_attempts.json`.
     - It is advisory and loss-tolerant. A missing, unparseable or unwritable
       ledger means "never attempted", so the item goes first once and is then
       rewritten.
  8. **Partial verification is visible (user review 2026-11-16).** When a run
     verified fewer items than it reached, the parent prints
     `REFRESH_WARN:unverified|<n> not verified`. The TUI reads that line, and the
     existing `budget_exhausted` warning, as a partial result: it shows a
     "<n> not verified" verdict and a warning-severity notification. No final-line
     field is added.
  9. **Pick on stale locks.** `p` is admitted only for the `crashed` and `orphan`
     categories. A stale_lock item's How shows `ait lock --unlock <N>`, and nothing
     runs it. Pick is refused for stale_lock and unparseable outcomes, so a pick
     never lands on an archived or `Ready` task. `b` still works.

## Steps

1. **Refresh target and dispatch** (`.aitask-scripts/lib/sitrep_refresh.py`).
   - `Target`:
     - add `incarnation: str = ""`;
     - the `check` comment becomes `task | push | trail | recovery`.
   - `select_targets` (:231-235): replace the `continue` with
     `out.append(Target(check="recovery", incarnation=st.context_incarnation(store.contexts.get(num)) or "", **base))`.
   - `Checker.check` (:706): an explicit branch per check, `task` / `push` / `trail` /
     `recovery`. Anything else → `Verdict("unknown", f"unsupported check {t.check}")`.
   - New pure module function
     `recovery_refresh_verdict(v, key, recorded, old_state, old_outcome) -> Verdict`.
     `v` is a `sitrep_crash.Verdict` and `key` is `None` for non-stored rows.
     Mapping:
     - `v.row == 1` → `Verdict("unverified", v.outcome)`.
     - `not recorded` → `unverified "no recorded incarnation"`. The detector warns
       and does not write in this case either.
     - `v.stored and key != recorded` → `unverified "new episode — the crash detector updates it"`.
     - Otherwise:
       - `state = "open"` for a stored row (5–8), else `v.item_state` (2 and 4 →
         `unknown`; 3 and 9 → `done`);
       - `outcome = v.outcome`.
       - If `(state, outcome) == (old_state, old_outcome)` → `Verdict("unchanged", outcome)`;
         otherwise `Verdict(state, outcome)`.
   - `Checker.check_recovery(t)`:
     - Lazy `import sitrep_crash as sc`.
     - Inputs are built once per worker run, on the first recovery target:
       `self._rec = (sc.read_locks(root), sc.read_active_tasks(root))`.
       An `sc.SourceError` (or any exception) is cached as `self._rec_err`, and every
       recovery target gets `unverified "inputs unreadable: <why>"`.
     - Per target:
       - `tid = st.parse_recover_ref(t.ref)`;
       - `lock = locks.get(tid)`;
       - `task = active.get(tid) or sc.read_inactive_task(root, tid, self.index(root))`;
       - `live = sc.liveness_of(lock) if lock is not None and lock.state == "ok" else ""`;
       - `v = sc.recovery_verdict(lock, task, live)`;
       - `key = sc.episode_key(tid, lock, t.incarnation) if v.stored else None`.
     - Return `recovery_refresh_verdict(...)`.
   - `cmd_worker` loop:
     - START's kind field is `"recovery"` for recovery targets and `t.kind` otherwise.
       This is the new kind value the task anticipated.
     - For a recovery target, `TimeoutExpired` and other exceptions map to
       `unverified` ("timed out" / "check error: <Type>") instead of `unknown`.
   - **Attempt ledger: worker side.**
     - Path helper: `attempts_path(root)`.
       - Run `git -C root rev-parse --path-format=absolute --git-common-dir`, bounded
         by `GIT_CAP`.
       - Result: `<common>/aitask-sitrep/refresh_attempts.json`, or `None` when the
         root is not git or the call fails.
     - After `ROOT:`, the worker emits `ATTEMPTS:<abs path>` when a path exists.
       This is a new protocol line: the whole remainder, before `TARGETS:`.
     - `read_attempts(path) -> {num: ts}`: strict JSON
       `{"version": 1, "attempts": {"<num>": "<YYYY-MM-DDTHH:MM:SSZ>"}}`. Any error or
       a wrong shape → `{}`. Malformed entries are dropped one by one.
   - **`order_targets(targets, attempts=None)`.**
     - Key: a recovery target uses `attempts.get(t.num, "never")`; every other
       target uses `t.checked_at`.
     - Sort: `(key != "never", key, num)`. That is the same rule as now, with only
       the recovery key's source changed.
     - With no ledger at all (a non-git root, where the detector cannot run either),
       recovery targets fall back to `checked_at`.
   - Test seam (test-only, documented in the docstring's seam list):
     `AITASK_SITREP_REFRESH_STALL_REF=<ref>` makes `check_recovery` sleep for an hour
     on that ref, so the deadline kill is exercised on a recovery target.
2. **Parent side** (same file).
   - `Stream.feed`:
     - VERDICT states `unchanged` and `unverified` are accepted only while the open
       START's kind is `recovery`; otherwise it raises `ProtocolError`;
     - `open` / `done` / `unknown` are unchanged.
   - `Stream.close`: an interrupted recovery target becomes `unverified` ("check did
     not finish within the Ns budget") rather than `unknown`.
   - `Line` gains `result: str = ""`.
   - `cmd_run`:
     - The batch is built only from lines whose state is `open`, `done` or
       `unknown`. If the batch is empty, the writer is not called.
     - A skipped line prints
       `REFRESH_ITEM:c<N>|recovery|<old>-><old>|unchanged|unverified|<outcome>`.
     - `checked` counts every line; `changed` and `unknown` count only written lines.
     - The `REFRESHED:` field set is unchanged (existing exact-string assertions hold).
     - `--dry-run` reports skip lines with their own word, not `dry_run`.
     - When `n = count(unverified) > 0`, print `REFRESH_WARN:unverified|<n> not verified`
       before `REFRESHED:`.
   - **Attempt ledger: parent side.**
     - `Stream.feed` accepts `ATTEMPTS:` once, after `ROOT:` and before `TARGETS:`.
     - Pure `merge_attempts(old, reached_nums, ts, max_age_days=7) -> dict`:
       - every reached recovery target gets `ts`, including interrupted ones;
       - entries older than 7 days are pruned. An entry pruned while its target is
         still starved reads "never" again, which puts that target first, so pruning
         can only help fairness.
     - The ledger is written only when the run got as far as the write step:
       - after a successful batch write, or when the batch was empty;
       - never on `--dry-run` or `REFRESH_FAILED`.

       This is the same condition under which today's stamps land.
     - Write path:
       - write atomically: `mkdir -p`, then `tempfile.mkstemp` in that directory, then `os.replace`;
       - the old content is re-read just before the merge;
       - concurrent runs: the last writer wins, and a lost stamp only makes a
         target look older.
     - A failure prints `REFRESH_WARN:attempts_unwritable|<reason>` and the exit
       code is unchanged.
     - The parent still runs no git: the worker resolved the path.
   - Module docstring, current state only:
     - TARGETS gains the `recover:` bullet;
     - EVIDENCE gains the recovery rule (shared table, no write on unverifiable, new-episode guard);
     - PROGRESS: a recovery item's `checked_at` changes only with its evidence; its
       turn comes from the refresh attempt ledger (path, format, prune rule,
       loss-tolerance), so fairness never depends on that stamp;
     - WORKER LINE PROTOCOL lists `ATTEMPTS:` and the two extra VERDICT states.
   - `aitask_sitrep_refresh.sh` header:
     - add the `recovery` kind and the `unchanged` / `unverified` result words;
     - add the `REFRESH_WARN:unverified|…` and `REFRESH_WARN:attempts_unwritable|…` lines;
     - add the ledger file;
     each with one line of meaning.
3. **Monitor** (`.aitask-scripts/monitor/monitor_shared.py`, `monitor/sitrep_close.py`).
   - `sitrep_close.py`: add `HARVEST_CRASHED_TIMEOUT = 120.0`, with a comment citing
     the measured cold and steady costs.
   - `monitor_shared.py`:
     - import it as `_SITREP_CRASH_TIMEOUT`;
     - add class defaults `_sitrep_crash_inflight = False` and `_sitrep_crash_due_at = 0.0` (beside :679-682);
     - initialise both in `_init_agent_marks` with `_MARKS_PURGE_STARTUP_GRACE`.
   - Add `async _maybe_detect_sitrep_crashes()`, modelled on `_maybe_refresh_sitrep`:
     - the same inflight, due and `finally` reschedule logic, at `_MARKS_PURGE_INTERVAL`;
     - roots come from `_sitrep_store_roots(...)`;
     - one `await self._run_sitrep_harvest(["crashed", "--root", root], timeout=_SITREP_CRASH_TIMEOUT)`
       per root. That is the existing `run_owned_group` seam: it kills the group,
       which holds the harvest mutex;
     - a failure is swallowed per root, so the other roots still run.
   - `_dispatch_refresh_maintenance`: harvest → detect → refresh, with the comment
     updated: detected items are refreshed in the same pass.
4. **TUI model** (`.aitask-scripts/sitrep_tui/sitrep_tui_model.py`).
   - `classify` (:313): inside `item.kind == "task"`, return `"recover"` first when
     `st.parse_recover_ref(item.ref)` matches. Only `open` items reach here; done,
     dismissed and unknown keep their current keys, and an unknown recover item
     reads "refresh re-checks it" because `refresh_checks` now lists `recovery`.
   - `recover_category(item) -> str`: lazy `from sitrep_crash import parse_outcome`.
     The label is returned when it is in `("crashed", "orphan", "stale_lock")`, else `""`.
   - Recover templates:
     - `NEXT_STEPS["recover"]` is the generic fallback. What:
       `Recover: {title}`. How: `{k_board}` to show it, `{k_ask}` to ask the agent.
     - `RECOVER_STEPS = {category: (what, how)}`. Every What is `Recover: {title}{outcome}`.
       The How texts:
       - **crashed:** "Resume: press  {k_pick}  to launch  /aitask-pick {pick_id}
         (reclaim → crash recovery survey). Do not git restore / git stash the tree."
       - **orphan:** "Resume or clean up: press  {k_pick}  to launch  /aitask-pick {pick_id} ."
       - **stale_lock:** "Check the holder, then release the lock yourself:
         ait lock --unlock {pick_id}  (shown, never run). Refresh ({k_refresh})
         marks it done once the lock is gone."
     - `next_step` picks `RECOVER_STEPS[cat]` when the key is `recover` and `cat` is
       set, and formats it with the same `fields` and effective keys.
   - `_fields`: `pick_id` also comes from `st.parse_recover_ref(ref)`.
   - `RefreshReport` (:1076):
     - new property `partial`: ok, plus any warn starting `unverified|` or
       `budget_exhausted|`;
     - `verdict()` appends ", <n> not verified" and/or ", <n> not reached", parsed
       from those warn lines.
   - `task_ref_id` (:1133): for `kind == "task"`, return the `_LOCAL_REF_RE` id, else
     `st.parse_recover_ref(item.ref)`. Its consumers are pick, board, trails and the
     Pri/Eff and Created columns. All of them want the task id.
5. **TUI actions** (`.aitask-scripts/sitrep_tui/sitrep_tui_actions.py`).
   - `summarize_crashed(rc, out) -> (ok, verdict, lines)`, the same shape as
     `summarize_harvest_all`:
     - `CRASHED:` → "Recovery: <a> crashed, <o> orphans, <s> stale locks (<n> new,
       <r> reopened)". Append ", <w> warned" when `w > 0`. All zero → "Recovery: nothing crashed".
     - `CRASH_NONE:` → "Recovery: nothing in flight".
     - `CRASH_FAILED:<r>`, a runner `ERROR:`, a non-zero rc or a missing final line →
       not ok, "Recovery check failed: <reason>".
     - Lines:
       - `CRASH_ITEM` added or reopened → `recovery: t<N> <category> (<word>)`;
       - `CRASH_WARN` → `recovery warning: t<N> <reason>`.
   - `_harvest_refresh` runs three steps. Each step's failure is independent, and
     refresh always runs:
     - `harvest all`;
     - `crashed --root self.root`, with `HARVEST_CRASHED_TIMEOUT`;
     - refresh.
     Then `ok = h_ok and c_ok and report.ok`. The verdicts become
     `[h_verdict, c_verdict, report.verdict()]`, and the lines are
     `h_lines + c_lines + refresh_lines(report)`. The automatic notify uses
     `warning` severity when `not ok or report.partial`. `_last_refresh` keeps its
     ok meaning: the refresh itself did run.
   - `_item_action_ok("pick_task")`: `(classify == "pick" or (classify == "recover"
     and model.recover_category(item) in ("crashed", "orphan"))) and task_ref_id(item)`.
     The dialog callback already re-checks through it.
6. **Tests.**
   - `tests/test_sitrep_refresh.py`:
     - The t2299_1 "skips a recover item" test becomes "routes it to `recovery` with
       its recorded incarnation".
     - A table test of `recovery_refresh_verdict` over rows 1–9 × old states
       `open` / `unknown`, plus the equal-verdict → `unchanged` case and the
       stored-row key mismatch → `unverified` case.
     - `check_recovery` with `read_locks` raising `SourceError` → `unverified`, never
       `done` or `unknown`.
     - `Stream` accepts `unchanged` / `unverified` only after a `recovery` START, and
       an interrupted recovery target → `unverified`.
     - The batch excludes skip lines, and an empty batch never spawns the writer
       (`AITASK_SITREP_REFRESH_BATCH_LOG`).
     - `order_targets` with a ledger:
       - recovery targets are keyed on attempts, the others on `checked_at`;
       - a missing entry sorts as `never`;
       - with no ledger, recovery falls back to `checked_at`.
     - `merge_attempts`: stamp, prune at 7 days, an interrupted target stamped.
     - `read_attempts`: garbage, a wrong version or a bad entry → dropped, never raises.
     - `Stream`: accepts `ATTEMPTS:` only between `ROOT:` and `TARGETS:`.
     - `cmd_run`: prints `REFRESH_WARN:unverified|<n> not verified` for an unverified line.
   - `tests/test_sitrep_refresh.sh`: a new section with lock helpers copied
     minimally from `tests/test_sitrep_crash.sh` (`publish`, `setlock`, `rawlock`,
     `unlock`, `dead_pid`, `live`). Items are created by the real `crashed` verb.
     - A crashed item, then refresh → `unchanged`. The recovery item's line and
       context are byte-identical (rev and checked_at unchanged). The store in this
       case holds only recovery items, so the whole of `todo.md` is byte-identical too.
     - Unlock with task `Ready` → row 9 `done`.
     - Live reclaim → row 3 `done`.
     - An archived task and a `Done` task under dead locks → `stale_lock`. Three
       alternations of refresh and `crashed`: `todo.md` cksum is stable after the
       first pass, and the outcome is byte-identical.
     - Released → `done`; further refresh and `crashed` passes leave it unchanged.
     - An unreadable lock blob → `unverified`, with the item line and context block
       byte-identical.
     - A new dead-pid lock (new key) → refresh `unverified` (new episode), then
       `crashed` → reopened or applied.
     - A dismissal during the `refresh:before_write` pause → `kept`.
     - **Bounded-budget fairness regression** (required by the user review).
       - Setup: one store with three recovery items, A (lowest num), B and C, and
         one ordinary task item T. Set `AITASK_SITREP_REFRESH_STALL_REF=recover:t<A>`.
       - Run `--budget 8` four times, with `AITASK_SITREP_NOW` advanced one minute
         per run.
       - **Expected rhythm under the specified rules.** Every reached target gets the
         same run stamp, and ties sort by item number, so passes alternate:
         - an A-only pass (A stalls, nothing else reached);
         - then a full pass (B, C and T, then A interrupted last).
       - **Assert eventual progress over the bounded sequence, not a fixed order:**
         - each of B, C and T gets a `REFRESH_ITEM` in at least one of runs 1–2 and
           at least one of runs 3–4, so no target waits more than one pass;
         - T's `checked_at` advances at least once in each pair.
       - Across all runs, A's item line and context block are byte-identical (never
         written). Each run reports A `unverified` with
         `REFRESH_WARN:unverified|1 not verified`.
       - **Negative control:** delete the ledger before each of runs 5 and 6. A sorts
         as `never`, so it goes first every time and B and C get no `REFRESH_ITEM` in
         either run. That proves the ledger is what lets the others through.
       - **Steady pass** with the stall removed and the clock advanced:
         - the recovery items' lines and their context blocks are byte-identical
           (unchanged evidence, no write);
         - the ledger stamps advance.

         T's line is excluded: an ordinary target updates `checked_at` by design.
   - `tests/test_monitor_sitrep_refresh.py`:
     - `_Host` also records `_run_sitrep_harvest`;
     - detect runs once per store root and not for a root with no store;
     - it is not due inside the grace window (`_init_agent_marks`) and is never stacked;
     - a raising root does not stop the others;
     - the class floors exist;
     - DispatchTests pins harvest < detect < refresh.
   - `tests/test_sitrep_tui_actions.py`:
     - `summarize_crashed` units;
     - `r` argv order with a recording runner is harvest all → crashed → refresh;
       refresh still runs after `CRASH_FAILED` and after a harvest failure;
       three verdicts.
     - `p` on a crashed recover item and on an orphan opens the pick screen for
       `/aitask-pick <N>`, with the item re-resolved by rev first.
     - `p` on a stale_lock item is refused; its How names `ait lock --unlock <N>`,
       and no runner call carries `lock`.
     - Recover items are built through the real writer's `recovery-apply`.
     - `parse_refresh_output` + `RefreshReport`:
       - an unverified item, then `REFRESHED:checked=1|changed=0|…` → `ok` and
         `partial`, and the verdict contains "1 not verified";
       - `budget_exhausted` → partial, "not reached";
       - the automatic `r` notify is warning-severity when partial.
   - `tests/test_sitrep_tui_app.py`: the What / How text for crashed, orphan,
     stale_lock and an unparseable outcome, with a remapped `p` key resolved in the text.

### Post-phase (risk mitigations)

1. [refresh_recovery_mutants] Run the mutant checks in an isolated copy.
   - **Setup.** `git worktree add --detach <scratch> HEAD`, then copy this task's
     uncommitted files in. Never touch the shared tree. Apply each mutant on its own
     to `lib/sitrep_refresh.py`:
     - (a) `recovery_refresh_verdict` maps row 1 to `unknown`;
     - (b) `cmd_run` puts `unchanged` / `unverified` lines back into the batch, with
       state = old state;
     - (c) the outcome is `v.evidence` instead of `v.outcome`;
     - (d) the new-episode guard (`key != recorded`) is removed;
     - (e) `Stream.feed` accepts `unchanged` / `unverified` for any kind;
     - (f) `order_targets` ignores the ledger and keys recovery on `checked_at`;
     - (g) `merge_attempts` stamps only finished targets, not interrupted ones;
     - (h) the `REFRESH_WARN:unverified` line is not printed.
   - **Run** `tests/test_sitrep_refresh.py` and `tests/test_sitrep_refresh.sh` against
     each mutant. Each must fail at least one assertion that is specific to it:
     - (a) the unreadable-lock byte-identical item;
     - (b) the `unchanged` pass with `todo.md` byte-identical;
     - (c) the alternated refresh/`crashed` cksum stability;
     - (d) the new-episode `unverified` case;
     - (e) the `Stream` kind-gating unit test;
     - (f) and (g) the bounded-budget fairness regression: B, C and T are reached in
       each pair of runs;
     - (h) the unverified-warn unit test and the TUI partial-verdict test.
   - **Record** the per-mutant failing-assertion counts (unit / e2e) in Final
     Implementation Notes, then remove the scratch worktree.

## Verification

- `python3 -m pytest tests/test_sitrep_refresh.py tests/test_monitor_sitrep_refresh.py tests/test_monitor_sitrep_harvest_close.py tests/test_sitrep_tui_actions.py tests/test_sitrep_tui_app.py tests/test_sitrep_crash.py -q`
- `bash tests/test_sitrep_refresh.sh`, `bash tests/test_sitrep_crash.sh`,
  `bash tests/test_sitrep_harvest.sh`, `bash tests/test_sitrep_todo.sh`,
  `bash tests/test_sitrep_skill_contract.sh`
- The rest of the sitrep suite in `aidocs/framework/sitrep.md` "Tests", plus
  `bash tests/test_no_lib_to_tui_import.sh`.
- `cd .aitask-scripts && shellcheck -x aitask_sitrep_refresh.sh`
- Live, read-only: `./.aitask-scripts/aitask_sitrep_refresh.sh --root "$PWD" --dry-run`
  in this repo. Then `ait sitrep tui`: press `r`, confirm the recovery verdict line
  and the items, press `p` on a crashed item, and **cancel** the dialog.

## Risk

### Code-health risk: medium
- The refresh worker/parent protocol is load-bearing for every refresh kind. This plan extends it with new VERDICT states, the `recovery` START kind and skipped batch lines, so a slip could regress task/push/trail refresh or the deadline path. · severity: low (residual: kind-gated `Stream` validation, unchanged `REFRESHED:` fields, existing suites, and proven by inline post-phase refresh_recovery_mutants) · → mitigation: inline post-phase refresh_recovery_mutants
- Monitor tick cost: a cold `crashed` pass holds the harvest mutex per root (~0.4 s per new item; ~9 s for 20), which delays a concurrent `h` harvest. · severity: low · → mitigation: none (measured by t2299_2; same 600 s cadence as harvest; owned-group timeout of 120 s; steady pass ~0.75 s)
- Fair progress: a recovery item's `checked_at` no longer moves on unchanged, unverified or interrupted checks. Ordering on it would retry a stalled old recovery check first forever and starve every later target, breaking PROGRESS (user review). · severity: low (residual: the attempt ledger mirrors the PROGRESS stamp rule, proven by the bounded-budget fairness regression with its delete-the-ledger negative control, and by mutants (f) and (g) of inline post-phase refresh_recovery_mutants) · → mitigation: inline post-phase refresh_recovery_mutants
- The attempt ledger is new runtime state outside the store (`<git common dir>/aitask-sitrep/refresh_attempts.json`). A lost or corrupt ledger, or concurrent last-writer-wins, makes targets look older, never newer, and the ledger is pruned at 7 days. · severity: low · → mitigation: none (advisory and loss-tolerant by design; the garbage-ledger unit test)
- Partial verification could hide behind a green summary (user review). · severity: low (residual: `REFRESH_WARN:unverified`, `RefreshReport.partial`, warning-severity notify; mutant (h)) · → mitigation: inline post-phase refresh_recovery_mutants
- The circular `sitrep_crash` ↔ `sitrep_refresh` import is resolved by lazy imports in the worker and the TUI model. · severity: low · → mitigation: none (the same pattern as `cmd_worker`'s `sitrep_harvest` import; the suites exercise both paths)

### Goal-achievement risk: low
- Refresh and the detector could fight over a recover item (ping-pong writes, churned revs) if any field derivation differs or the new-episode guard leaks. · severity: low (residual: shared `recovery_verdict` / `format_outcome`, the alternated-pass cksum test, and proven by inline post-phase refresh_recovery_mutants) · → mitigation: inline post-phase refresh_recovery_mutants
- Under the new-episode guard, an item can show claim A's evidence until the detector next runs. · severity: low · → mitigation: none (detect runs immediately before refresh in both the monitor tick and the TUI `r`)

### Planned mitigations
- timing: post-phase | name: refresh_recovery_mutants | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: refresh/detector fight, protocol-extension regression, recovery starvation, hidden partial verification | desc: eight isolated mutants (row-1 write, stamping unchanged lines, raw evidence outcome, no new-episode guard, kind-agnostic Stream, ledger-ignoring order, finished-only attempt stamps, missing unverified warn) must each fail a guard-specific assertion

## Step 8e note

After the tests pass, send t2299_4 a note with `/aitask-note`. It records the
refresh grammar additions:
- the `recovery` kind;
- the `unchanged` / `unverified` result words;
- that recovery items are written only on change;
- the new-episode guard;
- the refresh attempt ledger (its path, and that it is advisory);
- `REFRESH_WARN:unverified` and the TUI's partial verdict;
- the TUI `r` order, now harvest → crashed → refresh;
- pick admitted for crashed and orphan only.

t2299_4 owns the docs that describe them.

## Step 9

Post-implementation: commit only this task's paths (`feature: … (t2299_3)`), then
archive through Step 9. Never `git restore` / `git stash` / checkout: the shared
tree holds other tasks' uncommitted work.
