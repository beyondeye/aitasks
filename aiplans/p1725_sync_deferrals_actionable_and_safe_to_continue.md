---
Task: t1725_sync_deferrals_actionable_and_safe_to_continue.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1725 — Sync deferrals: actionable, and safe to continue

### Pre-phase (risk mitigations)

These are phases of the named **children** (this parent has no numbered steps of its
own); each child's task body and plan carries its step verbatim.

1. [characterize_sync_paths_never_empty_stdout] — **child 3, before any restructure of
   `aitask_sync.sh`'s protection state:** add a forced-path harness to
   `tests/test_sync_deferral_and_quarantine.sh` (or a new `tests/test_sync_protect_paths.sh`)
   that drives every `_protect "<reason>"` literal — scanned from the source so a new
   reason cannot be missed — through `aitask_sync.sh --batch` under `set -u` (planted
   lock / unreadable lock branch / staged path / ownerless file / planted content
   change via the existing `pre_group_commit` seam) and asserts the run's stdout is
   **non-empty and starts with a recognised token** every time. Commit it green
   against the current script, then restructure.
2. [writer_entry_point_table] — **child 2, before adding the guard calls:** write
   `tests/test_task_data_writer_guard.sh` as a table: one row per task-data writer
   script (`aitask_update.sh`, `aitask_create.sh --batch --commit`, `aitask_note.sh`,
   `aitask_gate.sh record`, `aitask_archive.sh`, `aitask_plan_externalize.sh`) run
   against the planted-wedge fixture, asserting a non-zero exit, the guard's message,
   and unchanged file bytes; plus one row per **exempt** read-only script
   (`aitask_ls.sh`, `aitask_query_files.sh`, `aitask_lock.sh --check`) asserting it
   still runs. The table is the audit record — a writer missing from it is the hole.

## Context

When the pre-sync sweep (`aitask_sync.sh`, t1599_3) cannot commit a dirty task-data
file it emits `DEFERRED:protected_dirty:N file(s) held by other sessions` and the
TUIs render only that. The per-file, prescriptive report the shell already computes
(`SKIP_REPORT`) goes to stderr and never reaches the user. On 2026-09-07 one such
deferral — a single untracked plan file held by the user's *own* `claude` pane parked
on an AskUserQuestion — took a session of forensics, and along the way the workflow's
own `pull --rebase` wedged `.aitask-data` mid-rebase, a frontmatter writer edited the
stale checked-out base, and `ait create` retries burned two duplicate ids.

Seven findings, five acceptance criteria, four independent seams (bash sweep + Python
wire parser, the workflow's `_task_pull_rebase`, the frontmatter/create writers, two
TUIs). The user chose decomposition into **5 implementation children**; the planning
conventions add a **dedicated docs child** for the user-visible TUI surface
(`aidocs/framework/planning_conventions.md` — "docs are a plan deliverable").

**Non-goal (unchanged):** deferring on another live session's *modified tracked* file
is still the correct outcome. What changes: the user sees exactly why / who / what to
do, and the cases that do not actually block the rebase stop deferring.

### Overlap audit (in-flight tasks)

- **t1696** (`Implementing`, holder **dead** per `aitask_live_endpoint.sh`, lock stale):
  fixes the *hint wording* that points at `./ait sync` for a recovery `ait sync` cannot
  perform on a dirty shared worktree, and suggests "have `ait sync` run the converge
  seam on its `protected_dirty` path". **Child 3 below implements the sync-side half**
  (fast-forward when `ahead == 0` and the dirty files are untouched by incoming
  commits). t1696 keeps the hint-wording half (`task_utils.sh:732/734`,
  `verified_update_lib.sh:191`, satisfaction-feedback procedures + goldens). Step 7
  sends t1696 an `ait note` naming child 3 so the two cannot drift.
- **t1599_4** (Implementing, agent unknown) owns commit *scoping* in
  `aitask_create.sh` / `aitask_update.sh`. Child 2 adds a *pre-write guard* to the same
  files — different concern, no shared lines; noted in child 2's task body.
- t1676 (Done) already aborts the sweep's conflict loop mid-rebase; t1678 / t1715
  (Ready) are unaffected.

## Decomposition

Children are created post-approval (Step 7 funnel), each with a self-contained task
body and its own plan under `aiplans/p1725/`. Dependency shape (`--no-sibling-dep`
where noted):

| # | Child | Depends on | Findings / AC |
|---|-------|-----------|---------------|
| 1 | `abort_conflicted_pull_rebase_in_task_utils` | — | F5 · AC3 |
| 2 | `refuse_task_data_writes_on_wedged_worktree_and_create_id_burn` | — (`--no-sibling-dep`) | F6, F7 · AC4, AC5 |
| 3 | `sweep_per_file_deferral_record_tree_state_gate_and_wire` | — (`--no-sibling-dep`) | F1(shell), F2, F3, F4 · AC1(wire), AC2 |
| 4 | `resolve_holder_pane_and_prompt_state` | 3 | F3 (pane / "waiting on a question") |
| 5 | `syncer_and_board_deferral_screen_with_commit_on_behalf` | 4 | F1 (TUI) · AC1 (syncer) |
| 6 | `document_actionable_sync_deferrals` | 5 | docs deliverable |

After the six are created, the manual-verification sibling is offered
(`planning.md` post-child-creation) — recommended **yes** (TUI flows in child 5).

---

## Child 1 — abort a conflicted `pull --rebase` in `_task_pull_rebase` (F5, AC3)

**Where:** `.aitask-scripts/lib/task_utils.sh` — `_task_pull_rebase()` (~787), shared by
`task_sync()` (~606, run by `aitask_pick_own.sh` at every pick / `--sync` / Step 7
ownership guard) and `task_push()`'s retry loop (~745, run after every claim,
`aitask_pick_own.sh:498`). Today it is a bare `_ait_data_git pull --rebase --quiet`:
on a conflict the rebase stays in progress, and every later `./ait git` write dies at
`assert_data_worktree_clean`. (The batch sync, `aitask_sync.sh:do_pull_rebase`,
already aborts — this is the one framework path that does not.)

**Change:**
1. Add `_data_wedge_state()` (echo `rebase-merge|rebase-apply|""` for the data git-dir
   via `_ait_data_gitdir`, legacy fallback `git rev-parse --git-dir`) — one helper,
   reused by `assert_data_worktree_clean` (replace its inline loop over
   `AIT_GIT_INPROGRESS_STATES` only if identical; otherwise leave that loop alone).
2. `_task_pull_rebase`: snapshot the wedge state **before** the pull. On failure, if
   there was no wedge before and there is one now, run
   `_ait_data_git rebase --abort >/dev/null 2>&1 || true` and print
   `aitask: rebase aborted after conflict - worktree restored, local commits kept`
   to stderr (callers capture `2>&1`, so it lands in `rebase_err`). If a wedge
   **pre-existed**, touch nothing and print
   `aitask: a rebase is already in progress in the data worktree` instead.
   Return the pull's exit status unchanged.
3. `_task_push_classify`: new arm **before** the CONFLICT arm matching the
   pre-existing sentinel → reason `rebase_in_progress`. `rebase_conflict` keeps
   matching the conflict text.
4. `_task_push_reason_hint`:
   - `rebase_conflict` → "rebase hit conflicts and was aborted (nothing left in
     progress); local and remote diverge — reconcile with 'ait syncer' or './ait sync'"
   - `rebase_in_progress` → "a rebase is already in progress in the data worktree;
     './ait git rebase --abort' discards only the partially replayed remote commits
     (your committed work stays on the branch), or resolve and './ait git rebase
     --continue'"
   - `assert_data_worktree_clean`'s die text gains the same one-line "what --abort
     discards" sentence.
5. Crew scripts (`aitask_crew_setmode.sh:125`, `aitask_crew_addwork.sh:328`) run the same
   bare `git pull --rebase --quiet || true` on crew worktrees: on failure add
   `git rebase --abort 2>/dev/null || true` (same pre-existing-wedge check is not
   needed there — the worktree is crew-private).

**Tests** (`tests/test_task_push.sh`, extend with the existing `setup_branch_mode`
fixture; new file only if it grows past the file's shape):
- forced conflict (same line edited locally + remotely) via `task_sync` → returns 0,
  `TASK_SYNC_STATUS=failed`, `TASK_SYNC_REASON=rebase_conflict`, **no** `rebase-merge` /
  `rebase-apply` under the data git-dir, and a subsequent `task_git commit` on a new
  file succeeds (the AC3 "next `./ait git commit` succeeds").
- same via `task_push` retry loop.
- end-to-end AC3: `aitask_pick_own.sh --sync` with the forced conflict prints
  `SYNC_FAILED:rebase_conflict` and leaves no wedge.
- **negative control:** a *planted* `rebase-merge` dir before the call is left in place
  (`rebase_in_progress`, the dir still exists) — proves the abort only undoes its own
  rebase.
- hint text pinned for both reasons (`feedback_guard_message_is_part_of_the_guard`).

## Child 2 — refuse task-data writes on a wedged worktree; stop `create` burning ids (F6, F7, AC4, AC5)

**Precondition that makes F6 reproducible:** the data worktree is mid-rebase, so the
checked-out file is origin's version, not the branch tip. No writer checks this
before `sed`-ing. The general "writer carries its last-known base SHA" contract is
**not** attempted (it would be a new field on every writer); the wedge is the one
production-reachable way the checked-out base differs from what the writer last
committed, and refusing there is the AC's "refused, not applied blind".

**Change:**
1. `task_utils.sh`: `assert_task_data_writable()` — honors
   `AIT_GIT_SKIP_STATE_CHECK=1`; if `_data_wedge_state` (child 1's helper; if child 1
   has not landed, add it here and child 1 reuses it) is non-empty, `die` with:
   "Data worktree (.aitask-data) is mid-<state>: the checked-out task files are not
   the branch tip, so writing now would land on stale content. If a sync is running
   right now, retry in a few seconds. Otherwise: ./ait git rebase --abort (discards
   only the partially replayed remote commits; your committed work stays) or resolve
   and ./ait git rebase --continue. './ait git-health' shows the full state."
2. Call it at every writer entry that mutates `aitasks/` or `aiplans/` content:
   `aitask_update.sh` (`run_batch_mode` before `resolve_task_file`, and
   `run_interactive_mode`), `aitask_create.sh` (the `--batch --commit` branch **before**
   `claim_unique_parent_id` / `acquire_child_lock`, `finalize_draft`, and the
   interactive commit path), `lib/ledger_block.sh` (covers `aitask_gate.sh` ledger
   appends and `aitask_note.sh`), `aitask_archive.sh`, `aitask_plan_externalize.sh`.
   Enumerate with `grep -ln 'sed_inplace\|>> *"\$\|write_task_file\|mv ' .aitask-scripts/*.sh`
   and list the audited-but-not-guarded ones (read-only or metadata-only) in the plan.
3. `aitask_create.sh` commit failure after the file is written (index lock, hook, …):
   do **not** `die`. Keep the file, print the path on stdout exactly as on success
   (the `--silent` contract), warn on stderr:
   "task file written but NOT committed (<first git line>) — it will be swept into the
   next sync's auto-commit under its own task id; do not re-run create". Skip
   `run_auto_merge_if_needed` on that branch. Same for the child-task branch (release
   the child lock first).

**Tests** (new `tests/test_task_data_writer_guard.sh`, fixture from
`tests/test_task_git.sh` ~868 which plants `rebase-merge` in the data git-dir, and the
bare-remote + claim-id scaffold from `tests/test_create_silent_stdout.sh`):
- F6 reproduction: local commit sets `status: Implementing` + `active_gates`, planted
  wedge with the checked-out file at the stale `Ready` version →
  `aitask_update.sh --batch <id> --risk-code-health low` exits non-zero, message names
  retry/abort, file bytes unchanged (md5), nothing committed.
- negative control: same update on a clean worktree succeeds.
- F7: wedge → `aitask_create.sh --batch --commit` exits non-zero **before** claiming:
  `aitask_claim_id.sh --peek` unchanged before/after, no file written.
- F7: planted `index.lock` → create prints the path, exit 0, stderr carries "NOT
  committed", `--peek` advanced by exactly one; remove the lock, run
  `aitask_sync.sh --batch` → the file is committed under
  `ait: Auto-commit t<id> task data before sync` (owner derivable). A second create
  is never needed — pinned by the peek delta.
- t1599_4 overlap note goes into this child's task body (`## Notes for sibling tasks`).

## Child 3 — per-file deferral record, tree-state-aware rebase gate, wire + parser, `--commit-for-task` (F1 shell, F2, F3, F4; AC1 wire, AC2)

**Where:** `.aitask-scripts/aitask_sync.sh` (`_protect` ~279, `_lock_snapshot` ~394,
`_holder_verdict` ~424, `_sweep_dirty` ~599, `_commit_group` ~753, `report_skipped`
~856, `do_push` ~1152, `main` ~1221), `.aitask-scripts/lib/sync_action_runner.py`,
`tests/test_sync_deferral_and_quarantine.sh`, `tests/test_sync_action_runner.py`,
`tests/lib/sync_fixture.sh`.

**3a. Per-file record.** Replace `PROTECTED_DIRTY=()` (reasons only) with parallel
arrays `PROT_REASON PROT_TASK PROT_PATH PROT_STATE PROT_HOLDER PROT_HOST PROT_PID
PROT_EMAIL PROT_ACTION` (+ `PROT_PANE`, empty until child 4). `_protect` takes
`<reason> <task> <path> <tree_state> <human line>`; per-task protections (`live_lock`,
`unknown_liveness`, `locks_unavailable`, `staged_elsewhere`, `content_changed`,
`commit_failed`, `unverifiable`, `lock_acquired_during_scan`) call it once per path of
that task; path-less ones (`scan_failed`, `lock_contended`) record an empty path with
`tree_state=unknown`. `tree_state` comes from the porcelain `XY` already parsed in
`_sweep_dirty`: `??` → `untracked`, anything else → `tracked`. `_lock_snapshot` keeps
`LOCK_EMAIL[$tid]` (it currently discards `lemail`).

**3b. Holder classification** (`_holder_class <tid>`). `self` **only** when every
identity is present and verified: `LOCK_EMAIL[$tid]` non-empty, `get_user_email()`
non-empty, the two equal, `LOCK_HOST[$tid]` non-empty and not `unknown`, `hostname`
resolvable and equal to it. Any missing or malformed identity yields `unverified`
(never `self`, never eligible for `--commit-for-task`) — an empty local email must
not equal an empty lock email. `other` = same verified host, different non-empty
email; `remote` = a different host; `none` = unlocked. Pinned: missing userconfig
email → `unverified`; lock blob with no `locked_by:` → `unverified`; both present and
equal → `self`. The human line and `PROT_ACTION` per class:
- self: "t<id>: <path> — held by YOUR OWN live session on this host (pid <pid>[, pane
  <pane>]) — finish or answer that session; or commit on its behalf:
  ./ait sync --commit-for-task <id>"
- other: "held by <email>'s live session on <host> (pid <pid>) — left for that session"
- remote: "held on <host> (liveness cannot be verified from here) — left for that host"
- ownerless / ambiguous_rename / staged_elsewhere / … keep their existing prescriptive
  text. "held by other sessions" is removed everywhere.

**3c. Rebase gate** (`_rebase_blocked`, replaces both `(( ${#PROTECTED_DIRTY[@]} ))
&& remote_ahead > 0` sites — `main` ~1279 and `do_push` ~1186). Inputs: `local_ahead`,
`remote_ahead`, `incoming=$(task_git diff --name-only HEAD..@{u})` (computed once after
`do_fetch`). Blocked when any record has: `tree_state=unknown`; or `tracked` **and**
`local_ahead > 0` (a rebase needs a clean tree); or `tracked`/`untracked` **and** its
path is in `incoming` (checkout would overwrite it). Otherwise not blocked. The
comment at ~1269 ("`git pull --rebase` refuses with unstaged changes") is rewritten to
state the three-way rule. Then in `main`: not blocked and `local_ahead == 0` →
`task_git merge --ff-only --quiet @{u}` (the t1658_1 `task_data_converge` rule — a
fast-forward never conflicts; the sweep's `did_pull=true` on success); not blocked and
`local_ahead > 0` → `do_pull_rebase` as today (only untracked protected files remain,
and none is incoming).

**The push-retry path re-gates on fresh inputs.** `do_push`'s rejection branch
(~1190) fetches again — the remote may have advanced *after* main's gate ran, and a
newly arrived commit can create exactly the protected untracked path the gate
allowed. After the retry fetch: recompute `local_ahead`, `remote_ahead`, `incoming`;
re-run `_rebase_blocked`; if blocked, emit the same `protected_dirty` deferral
(status line + `DEFERRED_FILE:` records, return 2); otherwise route the rebase
through `do_pull_rebase` (abort-safe, reports `CONFLICT:` / `ERROR:` itself) — the
bare `task_git pull --rebase --quiet` at ~1198 is removed. Pinned by a marker-gated
`pre_push` seam (same `_sync_test_seam` mechanism as `pre_commit_phase`): the hook
advances the remote from `pc2` with a commit that creates the protected untracked
path → the push is rejected → the retry gate blocks → `DEFERRED:protected_dirty`,
no `ERROR:push_rebase_failed`, the local untracked file's bytes unchanged.
Negative control: the same seam advancing an unrelated path → the retry rebases and
`PUSHED`.

**3d. Wire.** First line keeps its shape and the closed reason set (three reasons,
`DEFERRED_REASONS` unchanged): `DEFERRED:protected_dirty:<N> file(s) block the
rebase: live_lock=<k> ownerless=<m> …` (sub-reason counts, no "held by other
sessions"). Then, **after** the status line, one continuation line per record via a
new `batch_detail()` (stdout, batch mode only — deliberately not `batch_out`, so the
`_emitted_tokens` scan in `test_sync_action_runner.py` does not read it as a status):
`DEFERRED_FILE:<sub_reason>|<task>|<path>|<tree_state>|<holder>|<email>|<host>|<pid>|<pane>|<pane_state>|<action>`
— the record is the **complete per-file snapshot**: everything any consumer renders
(holder identity, where it runs, what it is doing, what clears it) is on the wire,
so no TUI re-derives locks, pane state or files (mitigation
`wire_fields_cover_screen`). **Every textual field is `_pct_encode`d** (`|`, `%`,
newline): `path`, `action`, `email`, `host`, `pane` — the pane target embeds
`#{session_name}`, which tmux lets contain `|` and a newline, and `hostname` /
`locked_by` are user-controlled too. The closed/numeric fields stay bare and are
validated by the parser: `sub_reason` (closed set), `task` (`^[0-9]+(_[0-9]+)?$`),
`tree_state` (`tracked|untracked|unknown`), `holder`
(`self|other|remote|unverified|none`), `pid` (`^[0-9]*$`), `pane_state`
(`^(waiting_[a-z0-9_]+|active|)$` — `waiting_<kind>` carries the monitor's prompt
pattern name, `active` = no prompt detected, empty = not probed / unresolvable).
Child 3 emits `pane` and `pane_state` empty; child 4 fills both **from the sweep**.
The stderr `report_skipped` stays (interactive `ait sync` and the failure-screen
tail).

**3e. Parser** (`sync_action_runner.py`): `DeferredFile` dataclass with one field
per wire column (`sub_reason, task, path, tree_state, holder, email, host, pid,
pane, pane_state, action`); `SyncResult.deferred_files: list[DeferredFile]`;
`DEFERRED_FILE_REASONS` closed set
(the `_protect "<reason>"` literals — a new scan test mirrors
`test_every_emitted_deferred_reason_is_declared` over `_protect\s+"([a-z_]+)"`);
`parse_sync_output` collects `DEFERRED_FILE:` lines only when the first line parsed as
`DEFERRED`; an unknown sub-reason or a malformed line fails closed to `STATUS_ERROR`
(same rule as an unknown reason); a `DEFERRED_FILE:` line **as first line** is
`unknown status` (pinned). Percent-decoding mirrors `_pct_decode` order (`%25` last)
and is applied to every encoded field. Pinned hostile round trips: a path containing
`|`, a pane target from a session named `a|b`, an email containing `|`, a host
containing `%7C` literally (must not double-decode); a `pane_state` outside its
grammar fails closed.

**3f. `--commit-for-task <id>[,<id>…]`** (new flag, documented in `show_help`). The
override is evaluated **inside `_holder_verdict`**, i.e. at *both* lock snapshots
(the pre-scan one and the 5a.2 CAS re-enumeration): a listed task gets `free` only if
its class is `self` *at that evaluation*; if the lock changes hands between the two
snapshots the verdicts differ and the group is skipped as
`lock_acquired_during_scan`. Any class other than `self` (including `unverified`)
is refused with a stderr line naming who holds it, verdict unchanged. The override
does **not** bypass 5a.3 (state re-check right before the commit) or 5a.4 (the
publication guard), so content that moves during the commit window is still
skipped or quarantined — pinned by driving the `pre_group_commit` seam under
`--commit-for-task`. What the sweep **cannot** see is whether the owning session is
mid-edit but momentarily quiet, so the CLI prints an explicit warning when it
commits on behalf: "t<id>'s session is live — its uncommitted edits were committed
as they stand now". The *waiting-on-a-prompt* gate is applied by the TUI (child 5)
from the record's `pane_state`; the CLI flag is the operator escape, never automatic.
**`--expect-path <pct-encoded path>`** (repeatable; only meaningful with
`--commit-for-task`) — one argument per path, never a CSV: a comma is a legal path
character and `_pct_encode` deliberately leaves it alone, so a joined list would
split a legal path and fail every scope check. The caller states the exact path set
it showed the user; when the task's dirty group
at commit time differs (any extra or missing path), the group is skipped as
`_protect "commit_scope_changed"` with the delta in the record's action text.
Pinned: group grown by one file after the confirmation → skipped, nothing committed;
identical set → committed; a path containing a comma (`aiplans/p10_a,b.md`) round-trips
and matches.
**`--require-waiting`** (only meaningful with `--commit-for-task`; the TUI always
passes it): the sweep **re-probes the holder's pane immediately before releasing the
group** — in `_commit_group`, after the 5a.3 state re-check and before the commit —
via child 4's `ait_tmux_pane_for_pid` + `pane_state_probe.py`; unless the result is
`waiting_<kind>` the group is skipped as `_protect "holder_not_waiting"` with the
observed state (`active`, or `unresolvable`) in the record's action text. The flag
fails **closed** when the probe is unavailable (child 3 lands before child 4: no
probe → not waiting → refused), so the TUI path can never commit on a stale
snapshot; the bare CLI `--commit-for-task` without the flag stays the explicit
operator escape with its warning. Pinned in child 4 (which owns the probe): a
lock anchored to a pane on the isolated socket whose screen is rewritten from the
AskUserQuestion snippet to plain output *between* the first (deferred) sync and the
retry with `--commit-for-task <id> --require-waiting` → `holder_not_waiting`,
nothing committed; the same sequence with the screen left waiting → committed.

**Tests:**
- `tests/test_sync_deferral_and_quarantine.sh`: AC2 both directions — (i) untracked
  `aiplans/p10_x.md` + live lock on t10 + remote ahead (no incoming touch) → no
  `DEFERRED`, remote commit pulled, local pushed; (ii) tracked modified `t10_alpha.md`
  same position → `DEFERRED:protected_dirty`; (iii) untracked but an incoming commit
  creates the same path → deferred (the one untracked case that blocks); (iv)
  `local_ahead == 0` + tracked dirty untouched by incoming → fast-forwarded, no
  deferral (t1696's scenario). Existing Tests 1–3 keep passing (Test 3's asymmetry).
- wire: the deferred run's stdout carries `DEFERRED_FILE:live_lock|10|…|tracked|self|
  other%40x.com|testhost|<pid>|||…` (email encoded, pane and pane_state empty) with
  `TEST_HOSTNAME` + a userconfig email matching the planted lock; `other`, `remote`
  and `unverified` rows via `lock_yaml_live … otherhost` / a different email / no
  userconfig email.
- `--commit-for-task 10` with class `self` → the group commits (`ait: Auto-commit t10…`)
  and the run pushes, stderr carries the live-session warning; with class `other` →
  refused, still deferred (negative control); with class `unverified` (no userconfig
  email) → refused; under the `pre_group_commit` seam rewriting the file → the group is
  skipped / quarantined exactly as without the flag (the override bypasses no guard).
- push-retry race: the `pre_push` seam test described in 3c (blocked → deferred; unrelated
  advance → `PUSHED`).
- `tests/test_sync_action_runner.py`: continuation parsing, pct-decoding of a `|` in a
  path, unknown sub-reason fails closed, first-line `DEFERRED_FILE:` is an error, the
  closed-set scan.
- `docs` are child 6; this child updates only inline `show_help`.

## Child 4 — resolve the holder's pane and prompt state (F3)

1. Extract `resolve_pane_for_pid` from `aitask_live_endpoint.sh` into
   `lib/tmux_exec.sh` as `ait_tmux_pane_for_pid <pid>` (echo `<pane_id>\t<target>`,
   ancestor walk bounded as today; only the gateway socket). `aitask_live_endpoint.sh`
   calls it (its `tests/test_live_endpoint*.sh` stay green; `tests/test_no_raw_tmux.sh`
   allows the gateway file).
2. `aitask_sync.sh`: for `live_lock` / `unknown_liveness` records on this host with a
   numeric pid, fill `PROT_PANE` from the helper, then `PROT_PANE_STATE` from the
   probe in step 3 (both best-effort: empty on any failure, never block the sweep;
   bounded to one helper call + one probe per task, memoized across that task's
   paths). Both values go through child 3's per-field `_pct_encode` — a session named
   `a|b` must round-trip (pinned here with the isolated-socket fixture).
3. `lib/pane_state_probe.py` — a CLI **and** importable module:
   `pane_state_probe.py <pane_id>` prints exactly one line, `waiting_<kind>` /
   `active` / empty, exit 0 always (the sweep invokes it through
   `lib/python_resolve.sh`, which `aitask_sync.sh` already sources). Capture via
   `tmux_exec.tmux_socket_args()` + `capture-pane -p -e -t <id> -S -200`, classify with
   `prompt_patterns.all_patterns()` and `monitor_core.classify_content` (reuse the
   monitor's 6-line prompt window; verify at implementation that importing
   `monitor_core` pulls no Textual App — if it does, import `strip_ansi` +
   `_prompt_detection_text` only). `waiting_<kind>` is the pattern `name` with the
   grammar the parser validates (`[a-z0-9_]+`). Idle needs two samples over time —
   deliberately not attempted; `active` means "no prompt detected right now".
4. Tests: `tests/test_tmux_pane_for_pid.sh` on an isolated tmux socket
   (`tests/lib/tmux_isolation.sh`): the pane's own pid resolves, a child process of the
   pane resolves via the walk, an unrelated pid → exit 1. `tests/test_pane_state_probe.py`
   with a captured-text seam (stub the capture): `claude_askuserquestion` snippet →
   `waiting_claude_askuserquestion`, plain output → `active`, capture failure → `""`;
   the CLI form prints exactly one line and exits 0 in all three. Sweep-level: a live
   lock anchored to a pane on the isolated socket whose screen shows the
   AskUserQuestion snippet → the `DEFERRED_FILE:` record carries the pane target and
   `waiting_claude_askuserquestion`. This child also wires child 3's
   `--require-waiting` re-probe (`_commit_group` → helper + probe) and pins the
   waiting→active transition between the deferred sync and the retry (3f).

## Child 5 — syncer + board deferral screen with commit-on-behalf (F1 TUI, AC1)

1. `sync_action_runner.py`: `SyncDeferredScreen(ModalScreen)` (shared like
   `SyncConflictScreen`): title `Sync deferred: <reason> — <N> file(s)`, one row per
   `DeferredFile`: `t<task>  <path>  <holder text>  <state>  <action>`; holder text:
   `you · pid <pid> · pane <pane> · <pane_state>` for `self`, `<email> on <host> · pid
   <pid>` for `other`, `<host> (unverified)` for `remote`, `identity unverified` for
   `unverified` — every value read from the parsed record. Buttons: **Commit t<id> on
   my behalf** — offered **only** for a `self` task whose parsed `pane_state` is
   `waiting_<kind>`; a `self` task whose record says `active` or `""` renders the row
   with the note "session is active — commit on its behalf is offered only while it
   waits on a prompt" and **no** button. Nothing is probed or looked up by the screen:
   it renders the parsed snapshot only. Pressing the button opens a **scope
   confirmation** that enumerates the task id and **every path in that task's group**
   (all `DeferredFile`s sharing the `task`, tree state shown per path) plus the CLI's
   live-session warning; confirming runs
   `run_sync_batch(extra_args=["--commit-for-task", id, *["--expect-path", p_encoded
   for each listed path], "--require-waiting"])` and re-dispatches the result
   through the same handler. The sweep (child 3, 3f) honours both: `--expect-path`
   skips the group as `commit_scope_changed` if the task's dirty set at retry time is
   not exactly what was displayed, and `--require-waiting` re-probes the pane right
   before the commit and skips as `holder_not_waiting` unless it is still on a prompt
   — the record's `pane_state` gates the *offer*, the re-probe gates the *commit*, so
   neither a grown group nor a resumed session can be committed on a stale snapshot.
   A `commit_scope_changed` / `holder_not_waiting` result re-opens the screen with the
   fresh records (the same `STATUS_DEFERRED` path). **Dismiss**.
   `run_sync_batch` / `sync_batch_command` gain `extra_args`.
2. `syncer_app.py` `_on_data_sync_done` `STATUS_DEFERRED`: keep the toast, push the
   screen when `deferred_files` is non-empty (`_capture_failure` still bypassed — a
   deferral is not a failure).
3. `aitask_board.py` `_run_sync`: push the screen only for the explicit `s` action
   (`show_overlay=True`); the `sync_on_refresh` background path keeps toast-only.
4. Tests: `tests/test_sync_deferred_screen.py` (`App.run_test`, per
   `aidocs/framework/testing_conventions.md` — await workers): rows render task/path/
   holder/email/host/pid/pane/state/action from records built only by
   `parse_sync_output`; the commit button appears only for `self` rows whose parsed
   `pane_state` is `waiting_*` — an `active` or `""` `self` row has no button (the
   "active holder cannot be silently committed" pin, both states on the wire); the
   scope confirmation lists exactly the paths of every record sharing that task, and
   the mocked `run_sync_batch` receives `--commit-for-task <id> --expect-path <each
   listed path, encoded> --require-waiting` (displayed scope == passed scope, pinned by
   comparing the two lists; the flag pinned present); a mocked retry result carrying
   `holder_not_waiting` / `commit_scope_changed` re-opens the screen with the new
   records; board background path does not push a screen. `tests/test_syncer_rows.py`
   untouched.

## Child 6 — documentation

`website/content/docs/commands/sync.md`: the `DEFERRED_FILE:` continuation contract,
the sub-reason closed set, the three-way rebase rule (tracked+ahead / incoming-touched
/ fast-forward when not ahead), the full `DEFERRED_FILE:` column list (incl. `email`,
`pane`, `pane_state` and its grammar), `--commit-for-task` + repeated `--expect-path` +
`--require-waiting` and the `commit_scope_changed` / `holder_not_waiting` skips, the
"your own session" wording,
and the writer-guard / create behaviours (children 1–2) under a new "Wedged worktree"
paragraph; `tuis/syncer/_index.md` (deferral screen + commit-on-behalf, the modal
table); `tuis/board/reference.md` (modal row); `aidocs/framework/` gets no new file —
the sync contract lives in the website page. Run `python3 check_links.py --build`.

### Post-phase (risk mitigations)

1. [pane_unresolvable_degrades_to_pid] — **child 4, after the pane/probe helpers
   land:** in `tests/test_sync_deferral_and_quarantine.sh` (or the child's own test
   file) run the deferred sweep with a live lock whose pid is **not** a descendant of
   any gateway pane (the test shell itself, on the isolated socket) and assert the
   `DEFERRED_FILE:` record still emits with pid, email and host filled and both
   `pane` and `pane_state` empty; in `tests/test_sync_deferred_screen.py` (child 5 may
   own the file — then this step lands there) assert a `DeferredFile` with `pane=""`,
   `pane_state=""` renders pid / host / action without raising and offers no commit
   button.
2. [wire_fields_cover_screen] — **child 5, after the screen is wired:** a test that
   builds `SyncDeferredScreen` from a `DeferredFile` constructed **only** from
   `parse_sync_output` on a literal `DEFERRED_FILE:` line and asserts every rendered
   cell maps to a dataclass field (no TUI-side lookups of locks, files or git); if a
   needed field is missing, extend child 3's record and parser in the same commit and
   update `website/content/docs/commands/sync.md`'s field list (child 6 re-checks).

---

## Verification (parent)

- Each child's own tests (bash files run individually; Python via
  `bash tests/run_all_python_tests.sh --test-dir tests`).
- `shellcheck .aitask-scripts/aitask_*.sh .aitask-scripts/lib/task_utils.sh`.
- Composed acceptance after children 1–5: on a real branch-mode checkout with a live
  `claude` pane holding a task and its plan untracked, remote ahead: `./ait sync`
  fast-forwards/rebases and pushes; with the plan file modified-tracked it defers and
  `ait syncer`'s `s` shows task id, path, `you · pid · pane · waiting: …`, and the
  commit-on-behalf button. Recorded by the manual-verification sibling.

## Step 9 (Post-Implementation)

Parent: after the last child archives, the parent is archived via the standard Step 9
(no code of its own; the `## Risk` levels below are written at Step 7 as usual). The
t1696 note is sent at Step 7 of **this** session (see Context).

## Risk

### Code-health risk: medium
- Child 3 restructures `aitask_sync.sh`'s protection state (parallel arrays replace a
  flat reason list) in a script whose every non-zero exit surfaces as
  `ERROR: empty output` to two TUIs · severity: medium · → mitigation: inline pre-phase characterize_sync_paths_never_empty_stdout
- Child 2's write guard touches every task-data writer; a missed entry path leaves the
  hole, an over-broad one blocks legitimate writes during a transient sync rebase ·
  severity: medium · → mitigation: inline pre-phase writer_entry_point_table

### Goal-achievement risk: medium
- The pane / prompt-state fields (child 4) depend on the gateway tmux socket and the
  monitor's regex registry; on a box where the agent runs outside the gateway the
  deferral degrades to pid-only and AC1's "pane" is empty · severity: medium ·
  → mitigation: inline post-phase pane_unresolvable_degrades_to_pid
- Six sequential children over a shared script: a later child can find child 3's
  record shape insufficient (e.g. pane per file vs per task) · severity: low ·
  → mitigation: inline post-phase wire_fields_cover_screen

### Planned mitigations
- timing: pre-phase | name: characterize_sync_paths_never_empty_stdout | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health 1 (sweep restructure → empty stdout) | desc: forced-path harness drives every `_protect` reason under `set -u` and pins non-empty batch stdout before the record restructure lands (child 3 pre-phase)
- timing: pre-phase | name: writer_entry_point_table | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health 2 (missed / over-broad write guard) | desc: table-driven test: every task-data writer refuses under the planted-wedge fixture, every exempt read-only script still runs (child 2 pre-phase)
- timing: post-phase | name: pane_unresolvable_degrades_to_pid | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal 1 (pane depends on gateway socket) | desc: off-gateway pid yields an empty pane field while the record still emits and the TUI still renders pid/host/action (child 4 post-phase)
- timing: post-phase | name: wire_fields_cover_screen | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal 2 (record shape insufficient for a later child) | desc: assert every field the deferral screen renders comes from the wire record; extend child 3's record inside child 5 if one is missing (child 5 post-phase)

Post-inline reassessment (single pass): the four inline phases bound each concern
with a pinned test but do not shrink the blast radius; both levels stay **medium**.
