---
priority: high
effort: high
depends: []
issue_type: bug
status: Ready
labels: [git, bash_scripts, robustness, syncer]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
file_references: [.aitask-scripts/aitask_sync.sh:1269-1280, .aitask-scripts/syncer/syncer_app.py:2264-2273, .aitask-scripts/lib/sync_action_runner.py:75-82]
children_to_implement: [t1725_1, t1725_2, t1725_3, t1725_4, t1725_5, t1725_6]
anchor: 1599
created_at: 2026-09-07 10:58
updated_at: 2026-09-07 16:40
---

## Problem

When the pre-sync sweep cannot commit a dirty task-data file, `ait syncer`
shows a toast that says only `Sync deferred: protected_dirty (1 file(s) held
by other sessions)`. It does not say **which file**, **which task**, **which
session/pane holds it**, or **what would clear it** — even though the shell
side computes exactly that. On 2026-09-07 a single deferral of this shape took
a whole session of manual forensics to resolve, and along the way the wedged
worktree corrupted a live task's frontmatter and burned two duplicate task ids.

Every item below was reproduced live on `omg16` against a real
21-behind / 39-ahead divergence.

## Findings (with the code that produces each)

1. **The per-task report is computed and then thrown away at the TUI boundary.**
   `aitask_sync.sh` resolves each dirty file to its owning task, checks the
   lock holder's liveness, and appends a prescriptive line per file to
   `SKIP_REPORT` (`_protect`, line ~279; the live-lock line at ~709:
   `t1717 is locked by a LIVE session on omg16 — its files left dirty for that
   session to commit`; the ownerless line at ~641 names the exact command that
   clears it). `report_skipped()` (~862) prints that on **stderr** —
   deliberately, since stdout is the parsed status channel. The TUI's
   `STATUS_DEFERRED` branch (`syncer/syncer_app.py:2264-2273`) renders only
   `deferred_reason (deferred_detail)` and deliberately bypasses
   `_capture_failure`, so there is no failure screen with an output tail
   either. The report never reaches the user.

2. **The wire token is a lossy roll-up.** `live_lock`, `unknown_liveness`,
   `ownerless` and `ambiguous_rename` all collapse into
   `DEFERRED:protected_dirty:N file(s) held by other sessions`
   (`aitask_sync.sh:1186`, `:1279`; the roll-up is documented at
   `lib/sync_action_runner.py:75-82`). The detail text is a count. Board and
   minimonitor consumers of the batch protocol cannot do better than the TUI.

3. **"Held by other sessions" is wrong when the holder is this user.** All
   13 locks on the branch belonged to the same user, 12 on the same host; the
   blocking session was a `claude /aitask-pick 1717` pane parked on an
   AskUserQuestion for 16 hours. Lock → pid → tmux pane → prompt state is all
   derivable (`lib/pid_anchor.sh`, the monitor's prompt detection), so the
   deferral could have said *"t1717: aiplans/p1717 — agent in pane aitasks:4.1
   is waiting on a question since 09-06 17:12"*.

4. **An untracked file needlessly defers the whole rebase.** The gate at
   `aitask_sync.sh:1269-1280` defers on `${#PROTECTED_DIRTY[@]} > 0 &&
   remote_ahead > 0`, with the comment "`git pull --rebase` refuses with
   unstaged changes". That is true for *modified tracked* files and false for
   *untracked* ones: git rebase ignores an untracked path unless an incoming
   commit creates the same path. `p1717` was `??` and no origin-only commit
   touched it, yet sync did fetch-then-nothing. The sweep does not distinguish
   the two states when deciding whether the rebase is blocked.

5. **The workflow's own sync can leave the worktree wedged.** One second after
   t1717 committed `plan_approved`, its workflow ran `pull --rebase --quiet`
   (reflog), hit a trivial frontmatter conflict on `t1705_….md`
   (`updated_at` vs `boardcol`/`boardidx` — bodies identical) and stopped
   mid-rebase with 13 picks remaining. The batch sync path aborts on conflict;
   whichever path this was did not. From then on every `./ait git` write in
   that agent failed with `stuck mid-rebase-merge`, and the agent decided to
   carry on with plain git on `main`.

6. **Frontmatter writers edit whatever base is checked out.** Because the
   rebase stopped *before* replaying t1717's own three commits, the
   checked-out t1717 file was origin's stale `status: Ready` version with no
   `active_gates`/`assigned_to`/`implemented_with`. At 09:12:06 the agent wrote
   its risk-gate result onto **that** file. Had it been committed, t1717 would
   have flipped back to `Ready` and lost its materialized gates. No writer
   checks that the file it is about to `sed` is at the base it last committed.

7. **`ait create` retries burn duplicate ids under a wedged worktree.**
   `t1722`, `t1723` (untracked, 08:53) and `t1724` (committed, 09:00) are
   byte-identical apart from timestamps — one follow-up spawned three times in
   seven minutes; the first two create-and-commit attempts left their files
   behind and each retry claimed a fresh id.

(5)–(7) may be split into their own tasks at planning; they are recorded here
because they are consequences of the same deferral being invisible, and a fix
to (1)–(4) that leaves them in place still lets one parked prompt escalate
into data corruption.

## Goal

Make a deferral **actionable** and support **safe retry / automatic
continuation** where the blocker is provably not a rebase blocker:

- A deferral names, per file: the path, the owning task, the holder
  (host, pid, tmux pane if resolvable, and whether that pane is idle / waiting
  on a prompt / running), and the exact action that clears it — in the syncer
  TUI, and in a form the batch protocol consumers can render.
- The batch protocol carries the sub-reason, not the roll-up, without breaking
  `parse_sync_output`'s first-line contract or the closed `DEFERRED_REASONS`
  set pinned in `tests/test_sync_action_runner.py`.
- "Held by other sessions" is never shown for a file whose holder is this
  user on this host; for that case the syncer offers the concrete next step
  (answer the prompt in pane X; or commit on that session's behalf, as an
  explicit, per-file user choice — never automatic).
- Untracked files that no incoming commit touches do not defer the rebase;
  the tree-state distinction (modified-tracked vs untracked) is made where the
  rebase gate is decided.
- A conflict reached by any framework-driven `pull --rebase` (workflow,
  syncer, board) either resolves or **aborts** — never leaves `rebase-merge`
  behind for the next writer to trip over. Where a wedge is nevertheless
  found, the "stuck mid-rebase" error names what to run and what it will
  discard.

## Explicit non-goal

This task does **not** promise that a sync can never be deferred while
concurrent live tasks hold files. Deferring on another live session's
modified file is the correct outcome (t1599_3) and stays. What changes is
that the user can see exactly why, who, and what to do — and that the cases
where nothing actually blocks the rebase stop deferring.

## Acceptance criteria

- With one file held by a live-locked task on this host, `ait syncer`'s
  deferral shows task id, path, holder host/pid/pane, and the clearing action;
  the same run's batch stdout carries the sub-reason and per-file detail in a
  form `parse_sync_output` accepts and the existing status tests still pin.
- With only an **untracked** file held by a live task and remote ahead, sync
  rebases and pushes; with a **modified tracked** file in the same position it
  still defers. Both directions pinned.
- A forced conflict during the workflow's post-`plan_approved` sync leaves no
  `rebase-merge` directory and the task's next `./ait git commit` succeeds.
- A frontmatter write against a file whose committed base differs from the
  writer's last-known base is refused or reconciled, not applied blind —
  pinned with a fixture that reproduces finding 6.
- A create-and-commit attempt that fails after the draft is written does not
  claim a new id on retry — pinned, or split out with the finding attached.

## Key files

- `.aitask-scripts/aitask_sync.sh` — `_protect` / `_note_skip` /
  `report_skipped` (~279, ~862), the live-lock and ownerless lines (~641,
  ~709), the rebase gate (~1269-1280), `do_push` deferral (~1185)
- `.aitask-scripts/lib/sync_action_runner.py` — `DEFERRED_REASONS`,
  `parse_sync_output`, `SyncResult.deferred_*`
- `.aitask-scripts/syncer/syncer_app.py` — `STATUS_DEFERRED` branch
  (~2264-2273), `_capture_failure`, `sync_failure_screen.py`
- `.aitask-scripts/lib/task_utils.sh` — `assert_data_worktree_clean` (~291),
  `task_sync` (~601), the recovery allowlist
- `.aitask-scripts/lib/pid_anchor.sh` — lock holder liveness; the monitor's
  prompt-pattern detection for "waiting on a question"
- `tests/test_sync_action_runner.py`, `tests/test_sync_*.sh`

## Related

- t1599_3 (the sweep's never-commit-another-session's-file contract), t1676
  (conflict loop dying mid-rebase), t1678 (data index lock adoption, Ready),
  t1715 (stale lock reaping, Ready — 3 of the 13 locks seen were months old),
  t1724 (the drift-check false positive that parked t1717 in the first place)
