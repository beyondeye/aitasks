---
Task: t2299_2_sitrep_crash_detector_and_extraction.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_1_*.md, aitasks/t2299/t2299_3_*.md, aitasks/t2299/t2299_4_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-15 18:10
---

# Plan: crash detector and extraction (t2299_2)

## Context

This child adds the deterministic pass that classifies every locked or
Implementing task through ONE ordered decision table. For each stored category
it extracts source-tagged evidence and maintains one `recover:t<N>` item, using
t2299_1's atomic `recovery-apply`.

The task file carries the decision table, the episode-key rules, the strict
input rules, the evidence list, the output grammar and the full test list; that
spec is authoritative. This plan orders the work. t2299_1's archived plan
(`aiplans/archived/p2299/p2299_1_*.md`) defines the verb's results and the
two-key caller contract.

## Verification record (2026-11-15, HEAD 70e18f6f1)

Re-read every API the plan names. These still hold:
- `sitrep_harvest.py`: `canonical_root` :642, `Store` :707 (`run` / `retain` / `add`), `_context` :816, `_work` :1247.
- `aitask_sitrep_harvest.sh`: `with_harvest_lock`, `run_source`, `main()`.
- The writer header's `recovery-apply` contract (`ADDED / APPLIED / UNCHANGED / REOPENED / KEPT / STALE / ABSENT`, the two-key rule).
- `sitrep_todo`: `load_todo_for_read`, `context_incarnation`, `parse_recover_ref`, `MAX_*`.
- `gate_ledger`: `has_gate_markers`, `resume_point_from_text`, `read_task_gate_state` (`stale_signed`, `archive_pending`), `GateRun.fields["run"]`.
- `pid_anchor.sh::lock_holder_liveness`; `aitask_task_worktree.sh resolve`; `agent_sessions.load_safe`; `parallel_admission_collect.plan_path_for`.
- The lock YAML keys at `aitask_lock.sh:296-302`.

**Corrections to the earlier plan:**
1. **`classify_liveness` cannot be reused as-is.** For a non-Implementing task it
   folds both `alive` and `unknown` into `lock_only`, so rows 3 and 4 (live claim
   → done vs. unknown) would be indistinguishable. Instead:
   - reuse `parallel_admission_collect.lock_holder_liveness` (the pure shell-out);
   - re-state the host guard with the SAME rule (`host and host != "unknown" and host == local_host`, local host = `platform.node()`), citing `classify_liveness`;
   - add a unit test asserting the two guards agree on a host table.
2. **"No PID anchor"** (row 5) is decided AFTER the host guard and BEFORE
   liveness: `pid` absent or not a positive integer. `lock_holder_liveness`
   returns `unknown` for it, which would otherwise land on row 4. The host guard
   runs first: a foreign-host or `hostname: unknown` lock with an absent or
   invalid PID is row 2 (`other_host`, never stored), not row 5.
3. **`git ls-tree` is cwd-relative.** Run from a subdirectory, it lists only that
   prefix: an empty listing reads as "no locks", a silent false all-clear. Always
   run `git -C <root> ls-tree -z --full-tree <ref>`, and add a test that runs the
   CLI from a subdirectory.
4. **`with_harvest_lock` prints `HARVEST_FAILED:<src>|…`.** Its failure line moves
   into one `lock_failed <src> <reason>` helper, which prints `CRASH_FAILED:<reason>`
   when `LOCK_FAIL_STYLE=crash` and the unchanged harvest line otherwise.
   `test_sitrep_harvest.sh` pins that harvest output is unchanged.
5. **The `read_task_gate_state` registry argument must be a computed expression**
   (`os.path.join(root, "aitasks", "metadata", "gates.yaml")`). Per
   `tests/test_gate_ledger_only_surfaces.py`, a bare name is "undecidable" and is
   reported as a finding. `signal_target` witnesses resolve relative to the cwd, so
   the Python entry `os.chdir(root)`s first.
6. **The real `plan_approved` has no `signal_target`**, so `plan_signature` is
   never `stale` in this repo. It reads `valid` when the ledger passes (no witness
   ⇒ `absent`, accepted). The stale-signature test therefore uses a scratch
   `gates.yaml` that gives `plan_approved` a `signal_target`, plus a witness with
   a mismatched `code_digest`. `plan_approved` must also be in the task's active
   set (`gates: [plan_approved]`).
7. **Archived records are as strict as active ones.** `sitrep_refresh.TaskIndex._facts`
   does not validate status: a missing or invalid one (`''`, `Banana`) comes back
   as `found=archived` with no error. So `read_tasks` does NOT delegate archived
   records to it. For an id with no active file:
   - Call `archive_iter.find_archived_markdown_by_id(id, root/aitasks/archived, errors=errs)`.
   - A non-empty `errs` → error. This keeps archive read errors: a truncated bundle, a missing `zstd`, an unlistable dir.
   - A hit `(name, text)` → the SAME `_strict_meta(name, text)` as active files, which requires a valid `status:` and parseable frontmatter.
   - `None` → `TaskIndex(root).lookup(id)`, used only for its fold-scan (`fold_scan` / `missing` / `error`). If that lookup reports `archived` (the archive changed between the two reads), treat it as an error (`archive_changed_during_read`).
8. **Reuse `sitrep_harvest.Store`** (`load` / `run` / `retain`) and `_context` /
   `_title` / `_one_line`, rather than a second writer client. `Store.run` raises
   `HarvestFailure` on writer exits 2, 3 and 4. They map as follows:
   - `writer:lock_busy` and `writer:store_unusable:*` → `CRASH_FAILED:<reason>`; stop the pass.
   - `writer:request:*` → `CRASH_WARN:t<N>|writer_request:<detail>`; continue.
9. **Row 9 covers every non-Implementing status**, including `Editing`, which the
   table's list omits. Row 7 already reads "not Implementing".
10. **`CRASH_NONE:nothing_inflight`** requires all three: no lock entries, no
    Implementing active task, and no recover item in `open`/`unknown` state. An
    open recover item whose task has since landed must still be closed by row 9.
11. **Note from t2299_1 (acknowledged).**
    - A state-only verdict (`done` / `unknown`, no context) passes the item's
      RECORDED incarnation (`st.context_incarnation(todo.contexts[num])`).
    - Only a context-bearing apply passes the observed key.
    - `ABSENT:<ref>` maps to `CRASH_WARN:t<N>|absent`, and the next pass re-decides.
    - A recover item with no recorded incarnation, on a state-only verdict, gives
      `CRASH_WARN:t<N>|no_recorded_incarnation`, with no write.
12. **Row 1 never writes.** The task's table says an existing item → `unknown`
    "unreadable: …". Its strict-input rule and Verification list instead say that a
    per-task read failure gives `CRASH_WARN:t<N>|unreadable:<what>` and leaves the
    existing item byte-identical. The stricter rule wins. Row 1 emits only that warn
    line; an input-error verdict is excluded from the write loop whatever the item's
    state (`open`, `unknown`, `done`, dismissed). An unreadable input says nothing
    about the task, and an `unknown` write would still change its rev, outcome and
    checked_at. Tested with an existing `open` item and an existing `unknown` item.
13. **Scan idempotence: a time-only difference never writes.** The writer counts a
    changed `checked_at` as an update (`_apply`), and `retain` names a passage by
    its content hash. So `--checked-at now` plus a `lock_age` that ticks every
    minute would give `APPLIED` and a fresh source on every pass. Policy:
    - **Stored evidence holds only time-invariant facts.** The survey records
      `locked_at` (absolute) and `lock_age` as a coarse bucket against the clock
      seam `AITASK_SITREP_NOW`: `<1h`, `1h-1d`, `1d-7d`, `>7d`. A bucket crossing is
      a real evidence change and writes; minutes inside a bucket do not.
    - **Local no-op precheck before any retain or apply.**
      - Build the proposed `title / group / state / outcome` and the proposed
        context entry. Pointers are derived locally the way `op_retain` names
        them: `sources/<hex16>.txt#L1-L<n>`, with
        `n = count(\n) + (0 if data ends with \n else 1)`.
      - If the item exists, is not dismissed, and its fields and its context entry
        (compared as `ContextEntry.body_lines()`) are equal, then nothing is
        retained or applied, and the result is `unchanged`.
      - Otherwise: retain, then apply with `--checked-at now`.
      - A state-only verdict whose state and outcome already match → `unchanged`, no write.
      - A unit test pins the local pointer against the writer's real `RETAINED:` line.
    - **Consequence (documented in the header):** a recover item's `checked_at` is
      "evidence last changed", not "last scanned". The pass's own final line is the
      scan record.
    - **Verified with the clock advanced between passes:**
      - The lock is taken at `T-2h`.
      - Pass 1 runs at `NOW=T`; pass 2 at `NOW=T+3h` (same `1h-1d` bucket). Pass 2
        must report `unchanged`, with `todo.md` byte-identical and no new
        `sources/` file.
      - Pass 3 at `NOW=T+2d` → `applied`, with `lock_age: 1d-7d`.
      - A frozen-clock idempotence check alone would hide the conflict.
14. **Live survey (moment-relative, 2026-11-15 ~16:00).** The task's numbers are stale.
    - Crashed: 1555_2, 1576, 1697, 2199, 2216, 2264, 2285, 2287, 2289, 2291, 2292, 2293 (12).
    - Alive (skip): 1363, 1879, 1912_2, 2278, 2299_2.
    - Stale_lock: 259 (no PID anchor, Ready).
    - Orphans: 1699, 887.
    - 2284, 2286 and 2290 have landed and hold no lock.
    - Re-survey at step 9.

## Steps

1. **`lib/sitrep_crash.py` skeleton.**
   - Stdlib, plus lib imports: `sitrep_todo as st`, `sitrep_harvest as sh` (`Store`, `HarvestFailure`, `canonical_root`, `_work`, `_context`, `_title`), `sitrep_refresh` (`TaskIndex`), `gate_ledger as gl`, `task_yaml`, `agent_sessions`, `parallel_admission_collect as pac`.
   - Add the `sys.path` insert and the `__main__` → `sitrep_crash` registration, as in `sitrep_harvest`.
   - Dataclasses:
     - `LockRec(id, fields, state ok|error, why)`;
     - `TaskRec(id, path, rel, slug, status, where active|archived|fold_scan|missing|error, folded, meta, text, why)`;
     - `Facts(task_id, lock, task, liveness, same_host, anchored)`;
     - `Verdict(row, category, stored, item_state, outcome, key)`.
   - Constants: `STORED = ("crashed", "orphan", "stale_lock")`, `ROW_*`, `VALID_STATUSES`.
   - Module hooks for tests: `_LIVENESS = pac.lock_holder_liveness`, `_LOCAL_HOST = None`.
2. **Strict readers.**
   - `read_locks(root)`:
     - resolve the ref: `refs/remotes/origin/aitask-locks`, else `refs/heads/aitask-locks`, via `rev-parse --verify -q`. Never fetch.
     - Neither ref exists → `SourceError("no_lock_ref")`. In a project that never initialized locks, `plan` reports `CRASH_FAILED:no_lock_ref`; the task asks for strictness.
     - `git -C root ls-tree -z --full-tree <ref>` → `(mode, type, oid, name)`. A non-blob, or a name that does not match `t<id>_lock.yaml`, is ignored.
     - One `git cat-file --batch` fed every oid. Parse its `<oid> blob <size>\n<bytes>\n` framing strictly; a `missing` reply makes that lock an error.
     - Strict `key: value` parse of each blob. Missing `task_id` or `hostname`, a `task_id` ≠ the file name id, or a duplicate key → `LockRec(state=error)`.
     - A non-zero exit or a timeout of the ref/tree probe → `SourceError`.
   - `read_tasks(root, lock_ids)`:
     - Walk `aitasks/t*.md` (excluding child-pattern names) and `aitasks/t<P>/t<P>_<C>_*.md` with `os.scandir`. An `OSError` on the dir → `SourceError`.
     - For each file, read the UTF-8 text strictly and pass it to `_strict_meta(name, text)`.
     - `_strict_meta` uses `task_yaml.parse_frontmatter`. Each of these makes the task an **error** record: `OSError`, `UnicodeDecodeError`, `yaml.YAMLError`, no frontmatter, non-dict metadata, a missing `status:`, or a status not in the valid set.
     - `folded_into` set → folded.
     - For each lock id (and each recover-item id) with no active file, use the archive route in correction 7: `find_archived_markdown_by_id` + `_strict_meta`, else the `TaskIndex` fold-scan for `fold_scan` / `missing` / `error`.
3. **Classification.**
   - `liveness_of(lock)`, strictly in this order:
     1. host guard fails (a foreign host, `unknown`, or empty) → `("other_host", False)`, whatever the PID;
     2. no anchor → `("noanchor", True)`;
     3. otherwise `_LIVENESS(pid, starttime, kind)` → `alive` / `dead` / `unknown`.
   - `recovery_verdict(facts)` implements the 9 rows in order:
     - row 1: a lock error, or a task error;
     - row 2: other_host;
     - row 3: alive;
     - row 4: unknown;
     - row 5: noanchor;
     - rows 6 and 7: dead, split by Implementing;
     - rows 8 and 9: no lock, split by Implementing.

     Unknown is never rounded up to crashed, and the host guard always runs before dead.
   - `episode_key(task_id, lock, recorded)` follows the task file's three rules. Each rule hashes its fields joined by `\n` with a rule tag first (`anchored` / `unanchored` / `nolock`) and keeps the first 12 hex digits of the sha256. `locked_at` stays out of the anchored key.
   - `format_outcome(label, evidence)` → `"<label> · <evidence>"`: `_one_line`, `|` → `/`, ≤ `st.MAX_OUTCOME`. `parse_outcome(s)` → `(label, evidence)`.
   - Labels per row: `unreadable`, `other_host`, `alive`, `unknown`, `stale_lock`, `crashed`, `stale_lock`, `orphan`, `recovered`. Each row's evidence text is the one in the task table.
4. **Evidence extractors** (only for stored categories). Each returns `(value, source_tags)`.
   - `phase_of(task)`:
     - `gl.has_gate_markers(text)` false → `unknown`.
     - Otherwise `gl.resume_point_from_text`: `PLAN` → `planning`, `IMPLEMENT` → `implementing`, `POSTIMPL` → `post_impl`.
     - A parse exception → `error`.
     - For `post_impl`: `gl.read_task_gate_state(task.path, registry_file=os.path.join(root, "aitasks", "metadata", "gates.yaml"), current_digest=memo)`, where `memo` is a per-pass callable that caches `gl.code_digest(root)`. That gives `pending_gates`.
     - Also record `phase_provenance`.
   - `plan_of(task)`:
     - Find the file with `pac.plan_path_for(root, id)`.
     - `plan`: `approved` when the ledger's `plan_approved` current run is `pass`, or the frontmatter has `plan_approved_at`; `draft` when only the file exists; else `none`.
     - `plan_signature`: from the same `read_task_gate_state` call (made once per task when the ledger has markers): `stale` if `plan_approved` is in `stale_signed`, `valid` if it passed, else `none`.
     - `plan_fresh`:
       - Referenced files = `file_references:` plus the tokens of the plan/task text that are in the per-pass `git ls-files -z` set. Tokens are backticked spans plus bare path-like words, with a trailing `:<line>` and punctuation stripped.
       - Baseline = `premise_baseline` (the sha before ` @ `), else `git rev-list -1 --before=<approval ts> HEAD`, where the ts is the `plan_approved` run's `run=` field or `plan_approved_at`.
       - Commit count = `git log --format=%H <base>..HEAD -- <files>`.
       - In the shared tree only, dirty files = referenced files ∩ the per-pass `git status`.
       - No file list → `unknown:no_files`. No baseline → `unknown:no_baseline`. A git failure → `unknown:git`.
   - `work_of(task, shared_status)`:
     - `aitask_task_worktree.sh resolve <task_name>`, keeping its exit status.
       - `USABLE p` → `git -C p status --porcelain -z`, all of it attributed `[worktree]`.
       - `NONE` → shared tree.
       - Any other state, or a non-zero exit or empty output → reported in `worktree:` with no attribution.
     - Shared tree: a path in the per-pass `git status --porcelain -z` is attributed to a task only when its plan or task text names it (`[plan]` / `[task]`).
     - `unattributed` = the shared dirty paths no stored task names.
     - Overlaps = paths named by ≥2 Implementing tasks (live or crashed); the names are computed for all Implementing tasks once per pass.
     - Commits: `git log --format=%H%x09%s --since=<locked_at> --grep "(t<N>)" -F`, excluding `ait:` subjects.
     - Branch head: `git rev-parse -q --verify refs/heads/aitask/<task_name>`.
     - Any survivor → the `warning: do not git restore / git stash / checkout the tree` line.
   - `pane_of(task)`:
     - `agent_sessions.load_safe()` records with `task_id == N` and `realpath(root) == canonical root`.
     - Choose the newest record.
     - If its `capture_txt` is readable, its tail (≤ 200 lines and ≤ 32 KiB) becomes a `capture:` source.
     - `agent_string` and `pane_id` → origin `agent=` / `pane=`.
5. **Rendering.**
   - `survey_passage(...)`: deterministic `key: value` lines, starting with `SITREP_RECOVERY_SURVEY v1`, keys in the task file's order.
   - `title_of`: `Recover t<N> <slug> (<category>): <phase>, <plan> plan (<fresh>), <k> files[, overlaps t<M>]`, via `sh._title`, ≤200. The slug is the filename stem after `t<N>_`.
   - `rank_of` / `group_of`: ranks 1–2 → `now`, 3–4 → `next`; orphan → `next`; stale_lock → `waiting`.
   - `context_of`:
     - background, one static line per category, ≤400;
     - origin `task=t<N> incarnation=<key>` plus `agent=` / `pane=`;
     - sources: `task:`, `plan:`, the retained survey `capture:`, the pane-tail `capture:`, and `commit:` lines for the last ≤5 shas.
     - Built through `sh._context`. Assert ≤ `st.MAX_CONTEXT_BYTES`; when it is over, drop commit sources from the end.
6. **Apply loop** (`run_pass(root, dry_run)`).
   1. Do one `Store.load()`: items by recover ref → `(num, rev, state, recorded incarnation)`.
   2. Run the readers once, then classify every id in (lock ids ∪ Implementing ids ∪ ids of existing recover items).
   3. For each task:
      - **Row 1 (any input error):** `CRASH_WARN:t<N>|unreadable:<what>` and nothing else: no retain, no apply, the item byte-identical in every state (correction 12).
      - **A stored category:**
        - Dismissed item with key == recorded → `kept_dismissed`, with no write (the writer would say KEPT).
        - Existing non-dismissed item whose proposed fields and context equal the recorded ones (the correction 13 precheck) → `unchanged`, with no write.
        - Otherwise, unless `dry_run`: `retain` the survey and the pane tail, then ONE `recovery-apply`:
          - `--ref recover:t<N>`;
          - `--expect-rev absent|<rev>`;
          - `--incarnation <observed key>`;
          - `--state open`;
          - `--outcome`, `--title`, `--group`;
          - `--checked-at now`;
          - `--context-file -` with the context.
      - **A done/unknown row (rows 2–4, 9) with an existing item that is not dismissed:**
        - state and outcome already equal → `unchanged`, no write;
        - otherwise a state-only apply with the **recorded** incarnation, no context, and `--checked-at now`.
      - **A done/unknown row with no item, or a dismissed item:** no write. Rows 2–4 print `CRASH_SKIP:`.
   4. Reply mapping:
      - `ADDED` → `added`;
      - `APPLIED` → `applied`;
      - `UNCHANGED` → `unchanged`;
      - `REOPENED` → `reopened`;
      - `KEPT` → `kept_dismissed`;
      - `STALE` → `CRASH_WARN:t<N>|stale`;
      - `ABSENT` → `CRASH_WARN:t<N>|absent`.

      With `--dry-run`, the result word is `dry_run`.
   5. Fault seam `AITASK_SITREP_CRASH_FAULT=before_apply|after_retain` raises at that point, which ends the pass with `CRASH_FAILED:fault:<point>`, exit 1.
   6. Final line: `CRASHED:crashed=…|orphans=…|stale_locks=…|skipped=…|added=…|reopened=…|warned=…`.
7. **CLI.**
   - Python entry `sitrep_crash.py plan|apply|dry-run --root <abs>` (apply also takes `--root-canonical`):
     - `plan` → `canonical_root`, then the cheap emptiness test (step 6.1 + the readers) → `CRASH_NONE:nothing_inflight` or `WORK:<root>`.
     - `apply` and `dry-run` → `run_pass`.
     - All three `os.chdir(root)` first.
   - `aitask_sitrep_harvest.sh crashed [--root <abs>] [--dry-run]`:
     - `--root` defaults to `$PWD`; it must be absolute and pass `no_dotdot`.
     - `need_python`.
     - `--dry-run` → exec `dry-run` without the lock.
     - Otherwise: `plan` → `WORK:` → `LOCK_FAIL_STYLE=crash with_harvest_lock crash <work> "$PY" "$CRASH" apply --root-canonical <work>`.
   - Add the `main()` case, the usage line and the header contract: verb, wire lines, exit codes 0/1/2, `AITASK_SITREP_CRASH_FAULT`.
   - The skill-facing allow-list is unchanged (the verb lives in an already-listed script).
8. **Tests.**
   - `tests/test_sitrep_crash.py` (units):
     - every decision row, table-driven via the `_LIVENESS` / `_LOCAL_HOST` hooks;
     - host precedence: a foreign-host lock and a `hostname: unknown` lock, each with the PID absent, `0`, `-` and `abc`, are all row 2 `other_host` and never stored. `_LIVENESS` is asserted NOT called for them;
     - host-guard agreement with `pac.classify_liveness`, over anchored AND unanchored locks;
     - `_strict_meta` over loose and bundled archived records (missing status, `Banana`, unparseable) → error. Control: archived `Done` → ok;
     - the local retain pointer equals the writer's `RETAINED:` line for single-line, multi-line and no-trailing-newline passages;
     - the `lock_age` buckets at their boundaries;
     - episode keys: anchored stable under a `locked_at` change, unanchored, carried forward, the `nolock` seed;
     - the outcome round trip and the 200 cap;
     - the strict readers given corrupt blobs, a missing `task_id`, a mismatched id, a duplicate key and a chmod-000 task file (skipped as root);
     - plan freshness in a scratch git repo: no baseline, N commits, dirty shared vs. worktree, the stale-signature registry and witness;
     - attribution, overlap, and the unattributed control.
   - `tests/test_sitrep_crash.sh` (end to end, real writer):
     - Scratch repos are built with `new_root`-style helpers, and lock blobs are committed on an orphan branch: `git hash-object -w`, `mktree`, `commit-tree`, `update-ref refs/remotes/origin/aitask-locks`.
     - A dead PID comes from `sleep 0 & p=$!; wait $p`. A live PID comes from `sleep 300 &`, with its starttime captured via `get_pid_identity` from `pid_anchor.sh`.
     - Every scenario in the task's Verification list:
       - **Precedence:** 3-pass stability; release → done; a live claim → done; archived under a dead lock → stale_lock, same key.
       - **Strict inputs:** byte-identical items on `CRASH_WARN`, for an existing `open` item AND an existing `unknown` item (todo.md and its rev unchanged). This covers an unreadable blob, a malformed lock, an unreadable active task file, a missing `status:`, and archived records (loose and in a `_b0/old0.tar.zst` bundle) with a missing or invalid status under a dead lock. Also: `CRASH_FAILED` with no writes; the absent-means-no-lock control; and a foreign-host lock with no PID → `CRASH_SKIP:…|other_host:<host>`, no item.
       - **Episodes:** a metadata edit kept; lock removal kept; a live claim untouched, then reopened when it dies; a self-refresh gives the same key; done → crashed reopened.
       - **Atomicity:** the fault seam; a dismissal between the read and the write → `STALE`, then the next pass gives `kept_dismissed`.
       - **Idempotence:**
         - Real clock advance via `AITASK_SITREP_NOW`. Pass 2 at `T+3h` is `unchanged`, with todo.md byte-identical and the `sources/` listing unchanged. Pass 3 at `T+2d` is `applied` with `lock_age: 1d-7d`.
         - A state-only `done` item stays `unchanged` across an advanced clock.
         - `--dry-run` writes nothing.
     - Run from a subdirectory (correction 3).
     - Harvest-failure prefix for crashed (`CRASH_FAILED:harvest_lock_busy`, held via the mutex).
     - Every body runs in the main shell, so the plain counters are enough.
9. **Live dry run** in this repo (read-only): `./.aitask-scripts/aitask_sitrep_harvest.sh crashed --root "$PWD" --dry-run`. Re-survey first (the loop behind correction 14), compare, and record both in Final Implementation Notes.

### Post-phase (risk mitigations)

1. [verdict_mutant_checks] Copy the checkout to a scratch directory (`git worktree add` of HEAD plus the uncommitted t2299_2 files copied in; never touch the shared tree). Then apply each mutant on its own to `lib/sitrep_crash.py`:
   - (a) run `_LIVENESS` before the host guard in `liveness_of`;
   - (b) map row 4 (`unknown`) to `crashed`;
   - (c) add `locked_at` to the anchored `episode_key`;
   - (d) move the no-anchor branch above the host guard;
   - (e) let row 1 write `unknown` to an existing item;
   - (f) drop `lock_age` bucketing (store the exact age).

   Run `tests/test_sitrep_crash.py` and `tests/test_sitrep_crash.sh` against each mutant. Each mutant must fail at least one assertion that is specific to it:
   - (a) the other-host negative control;
   - (b) the unknown-liveness control;
   - (c) the "self-refreshed lock → same key" test;
   - (d) the foreign-host/no-PID precedence test;
   - (e) the byte-identical open/unknown item on `CRASH_WARN`;
   - (f) the advanced-clock `unchanged` pass.

   Record the failing-assertion counts in Final Implementation Notes, then remove the scratch worktree.
2. [pass_cost_probe] Time the live `crashed --dry-run` (`/usr/bin/time -v` wall clock). Also build a scratch repo with 20 crashed tasks (dead PIDs) and time a real `crashed` apply on it, counting subprocesses with `strace -f -e trace=execve -o <scratch>` (or a PATH shim counter if strace is absent). Record both in Final Implementation Notes. If either pass exceeds 10 s, send t2299_3 a note with the numbers (`./ait note 2299_3 --from 2299_2 --file -`), because it owns the monitor-tick budget.

## Verification

- `python3 -m pytest tests/test_sitrep_crash.py -q`
- `bash tests/test_sitrep_crash.sh`
- `bash tests/test_sitrep_harvest.sh` (verb dispatch and the `HARVEST_FAILED` lines unchanged)
- `bash tests/test_sitrep_todo.sh`
- `python3 -m pytest tests/test_sitrep_harvest.py tests/test_sitrep_refresh.py -q`
- `cd .aitask-scripts && shellcheck -x aitask_sitrep_harvest.sh`
- `bash tests/test_no_lib_to_tui_import.sh`
- `python3 -m pytest tests/test_gate_ledger_only_surfaces.py -q`: the new call passes a computed registry, so it is not a finding and nothing is registered.
- `./.aitask-scripts/aitask_sitrep_harvest.sh crashed --root "$PWD" --dry-run`

## Risk

### Code-health risk: medium
- The pass shells out per task. A stored task costs 2 retains + 1 apply in writer calls, plus `resolve` and 2–3 git calls, so a repo with ~15 crashed tasks makes ~100 subprocesses and the monitor tick (t2299_3) could be slow. · severity: low (residual: measured by inline post-phase pass_cost_probe; t2299_3 gets a note if a pass exceeds 10 s) · → mitigation: inline post-phase pass_cost_probe
- A classification slip produces a false crash claim about a live agent: the host guard runs after liveness, `unknown` is rounded up to `crashed`, or `locked_at` leaks into the key so a self-refreshing session reopens its own dismissed item. The table-driven tests are written by the same hand as the code. · severity: low (residual: proven by inline post-phase verdict_mutant_checks) · → mitigation: inline post-phase verdict_mutant_checks
- The no-op precheck re-derives the writer's retain pointer locally. If the two derivations drift, every pass writes, or a real change is skipped. · severity: low · → mitigation: none (a unit test pins the local pointer against the real `RETAINED:` line, and the clock-advance e2e test catches both directions)
- Moving `with_harvest_lock`'s failure line into a helper touches every harvest verb. · severity: low · → mitigation: none (`test_sitrep_harvest.sh` pins the unchanged `HARVEST_FAILED:` lines)

### Goal-achievement risk: medium
- The path-naming attribution heuristic can mis-attribute shared-tree files, and plan-token extraction can match prose. · severity: medium · → mitigation: none (by design the evidence is source-tagged and advisory, it is intersected with `git ls-files`, unattributed files stay separate, and a control test covers it)
- `plan_signature` can never be `stale` in this repo, because `plan_approved` has no `signal_target`. It reads `valid` from the ledger alone. · severity: low · → mitigation: none (reported honestly; the stale path is proven with a scratch registry)
- The live survey is moment-relative, so the acceptance numbers will differ at implementation time. · severity: low · → mitigation: none (re-survey at step 9, record both)

### Planned mitigations
- timing: post-phase | name: verdict_mutant_checks | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: false crash claim from a classification slip | desc: six isolated mutants (guard order, unknown→crashed, locked_at in key, no-anchor before host, row-1 write, exact lock age) must each fail a guard-specific assertion
- timing: post-phase | name: pass_cost_probe | type: performance | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: per-task subprocess cost | desc: time the live dry-run and a 20-task scratch apply, count subprocesses, note t2299_3 if over 10 s

## Step 9

Post-implementation: commit this task's paths only (`feature: … (t2299_2)`); archive via Step 9.
Never `git restore` / `git stash` / checkout in this repo: the shared tree holds crashed tasks' uncommitted work.

## Post-Review Changes

### Change Request 1 (2026-11-15 18:45)
- **Requested by user:** four review findings, all verified as real:
  1. `named_paths` stripped the leading dot from hidden-directory paths (`.aitask-scripts/…`).
  2. Ownership matching ignored named untracked files.
  3. A failed `git status` and an unreadable plan silently became empty evidence.
  4. Unattributed shared-tree edits did not raise the tree warning.
- **Changes made:**
  - `named_paths` now normalizes only explicit `./` prefixes and trailing `.`/`/`.
  - Ownership matching runs over tracked ∪ dirty paths: `git status --untracked-files=all`, with the task-data pathspecs `aitasks/**`, `aiplans/**` and `.aitask-data/**` excluded as `code_digest` excludes them. Commit history runs only over tracked files.
  - A failed `ls-files` or `status` raises `CRASH_FAILED:tracked_files_unreadable` / `shared_status_unreadable`. Both are read up front in `run()`, before any write.
  - An unreadable plan:
    - is recorded in `plan_errors`;
    - makes its own task `CRASH_WARN:…|unreadable: plan …` with no write;
    - shows as `overlap: ? t<M>(plan_unreadable)` in other tasks' surveys.
  - A failed commit log or worktree status is recorded as `incomplete` (`commits: unknown`).
  - `Survey.warning()` warns on own survivors, else on unattributed shared-tree edits, else on incomplete evidence. `survivors`, which ranks the item, is unchanged.
- **Files affected:** `.aitask-scripts/lib/sitrep_crash.py`, `tests/test_sitrep_crash.py`, `tests/test_sitrep_crash.sh`
- **Tests added:**
  - a hidden-dir exact path (unit and survey);
  - a named untracked file, plus the unnamed-untracked control;
  - task data never in the dirty set;
  - a failed status (unit: corrupt index; e2e: a git shim failing only `status`, so `check-ignore` still works);
  - an unreadable plan (own task: warn with the item byte-identical; other task: `?` overlap);
  - the unattributed and incomplete-evidence warnings.

### Change Request 2 (2026-11-15 18:55)
- **Requested by user:** `named_paths` sent `file_references:` entries and backticked spans through the bare-word tokenizer, so a path with a space (`src/my file.py`) was never matched. That lost its attribution and let `plan_fresh` read `fresh`. Verified as real.
- **Changes made:**
  - `named_paths(text, universe, idx, explicit=…)` matches explicit metadata entries and backticked spans as COMPLETE paths first. `_whole` strips only a trailing line reference (`:12`, `:12-30`, `#L12-L30`), and `_match_path` normalizes only `./` and trailing `.`/`/`.
  - The bare-word scan runs after them as the fallback.
  - `Pass.names` passes `file_references:` as explicit entries instead of joining them into text.
- **Files affected:** `.aitask-scripts/lib/sitrep_crash.py`, `tests/test_sitrep_crash.py`
- **Tests added:**
  - `NamesWhole`: explicit entries with a line suffix; backticked spans with `#L`/`:` suffixes; a control showing bare prose never reassembles a spaced name.
  - A survey test that a dirty spaced filename, named by `file_references` and by a backtick span, is attributed and gives `stale:dirty_referenced:1`.

## Final Implementation Notes
- **Actual work done:**
  - New `.aitask-scripts/lib/sitrep_crash.py`:
    - strict lock and task readers;
    - the ordered 9-row `recovery_verdict`, with `liveness_of` running host guard → no-anchor → liveness;
    - `episode_key`, `format_outcome` / `parse_outcome`, `age_bucket` and `retain_pointer`;
    - the evidence extractors: phase, plan / signature / freshness, work (worktree or shared tree), overlaps, commits, branch head, pane tail;
    - survey/title/group/context rendering;
    - the `Pass` apply loop, with the local no-op precheck and one `recovery-apply` per task;
    - CLI `plan | apply | dry-run`.
  - `aitask_sitrep_harvest.sh` gained the `crashed [--root] [--dry-run]` verb, its header contract, and the `lock_failed` helper (`LOCK_FAIL_STYLE=crash` gives `CRASH_FAILED:<reason>`; harvest output is unchanged).
  - New tests: `tests/test_sitrep_crash.py` (46 units) and `tests/test_sitrep_crash.sh` (119 e2e assertions, with the real writer, real lock refs, and real dead and live PIDs).
- **Deviations from plan:**
  - The test seam `AITASK_SITREP_CRASH_PAUSE_FIFO` (at `before_apply`) was added for the read-vs-dismiss race test. It reads the fifo one byte at a time: a buffered `readline` swallowed the next pause's line and hung the suite.
  - Overlaps count only paths named by this task AND another Implementing task that are dirty in the shared tree. Only uncommitted work can collide on a restore or stash, and listing every commonly named file would be noise.
  - Done or dismissed recover items with no lock and no active file are skipped without reading the archive. They can only land on row 9 or on row 1, which never writes, so old items cost no bundle read per pass.
  - `CRASH_ITEM` uses `-` for c<M> when no item exists yet (dry-run). Non-stored rows print a `CRASH_ITEM` line only when they write.
  - Review rounds (see Post-Review Changes):
    - hidden-dir and spaced path matching;
    - untracked named files, with task data excluded;
    - fail-closed `ls-files`/`status`/plan reads;
    - the tree warning for unattributed edits and incomplete evidence.
- **Issues encountered:**
  - `git ls-tree` is cwd-relative: run from a subdirectory it lists nothing. Fixed with `--full-tree`, plus a test from a subdirectory.
  - The scratch `HOME` hides the framework Python, so the e2e test exports `AIT_PYTHON` first, as `test_sitrep_refresh.sh` does.
  - A corrupt index makes `check-ignore` fail in the wrapper before `status` runs, so the e2e status failure uses a git shim that fails only `status`.
  - The TaskIndex fold scan fails closed: one unparseable record anywhere makes "missing" unprovable, so the result is `error`. The test pins this.
- **Key decisions:**
  - Row 1 never writes. This is stricter than the task's table, per its strict-input rule.
  - `classify_liveness` is not reused (it folds alive/unknown into `lock_only`). The host guard is restated with the same rule, and a test checks the two agree.
  - Archived records are validated with the same `strict_meta` as active ones. `TaskIndex` is used only for its fold-scan answer.
  - Idempotence: stored evidence holds only time-invariant facts (absolute `locked_at`, bucketed `lock_age`). An equal proposal writes nothing, so a recover item's `checked_at` means "evidence last changed".
  - The `read_task_gate_state` registry is a computed `os.path.join(...)`, so the ledger-only guard has nothing to register. The Python entry `chdir`s to the root because witnesses resolve relative to the cwd.
- **Verification:**
  - **Suites:**
    - `test_sitrep_crash.py`: 46 passed.
    - `test_sitrep_crash.sh`: 119 passed.
    - `test_sitrep_harvest.sh`: 139/139.
    - `test_sitrep_todo.sh`: all passed.
    - pytest over the harvest, refresh and gate-ledger-only-surfaces modules: 135 passed.
    - `test_no_lib_to_tui_import.sh`: passed.
    - `shellcheck -x`: clean.
  - **Live dry run** (2026-11-15 ~18:55):
    - Crashed: 1555_2, 1576, 1697, 2199, 2216, 2264, 2285, 2287, 2289, 2291, 2292, 2293 (12).
    - Orphans: 887, 1699.
    - Stale_lock: 259.
    - Skipped (alive): 2275, 2278_1, 2299_2, 2305 and later others; the count is moment-relative.

    It wrote nothing; the real store has no `recover:` items.
- **Post-phase verdict_mutant_checks** (an isolated `git worktree --detach` copy, removed afterwards). Failing assertions per mutant, unit / e2e, on the final code:
  - (a) liveness before the host guard: 2 / 2;
  - (b) unknown → crashed: 2 / 3;
  - (c) `locked_at` in the anchored key: 1 / 4;
  - (d) no-anchor before the host guard: 1 / 5;
  - (e) row 1 writes `unknown`: 0 / 13;
  - (f) exact lock age: 1 / 5.

  Each was caught by its guard-specific test: the other-host control, the unknown control, the self-refresh key, the foreign-host/no-PID precedence, the byte-identical open/unknown item on `CRASH_WARN`, and the advanced-clock `unchanged` pass.
- **Post-phase pass_cost_probe:** strace and `/usr/bin/time` are absent, so it used a PATH git shim and bash `time`.
  - Live `--dry-run`: 0.69 s wall.
  - Scratch repo with 20 crashed tasks, cold apply: 8.9 s wall, 134 git calls plus 40 writer calls (20 retains + 20 applies).
  - The steady-state second pass: 0.75 s (20 `unchanged`, nothing written).

  Under the 10 s threshold, so no note was sent. The cold cost is linear in newly stored tasks, at about 0.4 s per item (2 writer calls).
- **Upstream defects identified:**
  - `.aitask-scripts/lib/sitrep_refresh.py:271-275 — TaskIndex._facts accepts a missing or invalid status: an archived record with status '' or 'Banana' comes back as found=archived with no error, so refresh classifies unvalidated records`
- **Notes for sibling tasks:**
  - **t2299_3 (refresh / monitor / TUI):**
    - Call `sitrep_crash.Pass(root, dry_run).run()`, or the wrapper verb, under the harvest mutex. Do not re-implement the table: `recovery_verdict(lock, task, liveness_of(lock))` is the shared decision.
    - Refresh's `check="recovery"` should read through `read_locks`, `read_active_tasks` and `read_inactive_task`, the strict readers.
    - A cold pass costs about 0.4 s per newly stored item; a steady pass is about 0.75 s. Budget the monitor tick accordingly; a first pass on a repo with many crashes is the slow case.
    - `checked_at` on recover items is "evidence last changed".
    - TUI pick routing: `st.parse_recover_ref(item.ref)` gives the task id.
  - **t2299_4 (skill / docs):**
    - The wire grammar is in the `aitask_sitrep_harvest.sh` header, and the decision table, episode key, evidence and idempotence rules are in `lib/sitrep_crash.py`'s header.
    - Row 1 never writes (stricter than the original table).
    - The tree warning has three forms: surviving work, unattributed shared-tree edits, and incomplete evidence.
    - Nothing is ever reclaimed or restored.
    - The skill that calls `crashed` needs no new allow-list entry; the verb lives in an already-listed script.
