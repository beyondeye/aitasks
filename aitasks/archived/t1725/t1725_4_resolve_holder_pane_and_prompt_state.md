---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: [t1725_3]
issue_type: feature
status: Done
labels: [bash_scripts, robustness, syncer, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
implemented_with: claudecode/opus5
created_at: 2026-09-07 16:39
updated_at: 2026-09-10 15:48
completed_at: 2026-09-10 15:48
---

## Context

Parent t1725, finding 3: the deferral could have said *"t1717: aiplans/p1717 —
agent in pane aitasks:4.1 is waiting on a question since 09-06 17:12"*, because
lock → pid → tmux pane → prompt state is all derivable. Depends on **t1725_3**, which
defines the per-file `DEFERRED_FILE:` record with two fields left empty for this
task: `pane` and `pane_state` (`^(waiting_[a-z0-9_]+|active|)$`), and the
`--require-waiting` re-probe hook in `_commit_group` that fails closed until the
probe exists.

Everything reads through existing seams: pid → pane is `resolve_pane_for_pid` in
`aitask_live_endpoint.sh` (t1657_4); prompt detection is the monitor's
`prompt_patterns.py` registry + `monitor_core.classify_content` (see
`aidocs/framework/monitor_idle_and_prompt_detection.md`). Nothing is reimplemented.

## Key files

- `.aitask-scripts/lib/tmux_exec.sh` — gateway; gains `ait_tmux_pane_for_pid`
- `.aitask-scripts/aitask_live_endpoint.sh` — `resolve_pane_for_pid` (~180-215) moves
  out; the script calls the gateway helper
- `.aitask-scripts/aitask_sync.sh` — fill `PROT_PANE` / `PROT_PANE_STATE` (t1725_3's
  arrays) and wire the `--require-waiting` re-probe in `_commit_group`; it already
  sources `lib/python_resolve.sh`
- new `.aitask-scripts/lib/pane_state_probe.py`
- `.aitask-scripts/monitor/prompt_patterns.py` (`all_patterns`, `PromptPattern`),
  `.aitask-scripts/monitor/monitor_core.py` (`classify_content` ~222,
  `_prompt_detection_text`, `strip_ansi`), `.aitask-scripts/lib/tmux_exec.py`
  (`tmux_socket_args`)
- `tests/test_no_raw_tmux.sh` (raw tmux allowed only in the gateway files),
  `tests/test_live_endpoint*.sh`, `tests/lib/tmux_isolation.sh`,
  `tests/test_prompt_detection.py` (snippet shapes for `claude_askuserquestion`)

## Implementation plan

1. Extract `resolve_pane_for_pid` into `lib/tmux_exec.sh` as
   `ait_tmux_pane_for_pid <pid>` — echo `<pane_id>\t<session>:<window_id>.<pane_id>`,
   ancestor walk bounded as today (`ANCESTOR_WALK_MAX=20`), only the gateway socket
   (`ait_tmux list-panes -a -F …`). `aitask_live_endpoint.sh` calls it; its comment
   block about pane_pid-first / window_id-not-index moves with the code.
2. `lib/pane_state_probe.py` — a CLI **and** an importable module.
   `pane_state_probe.py <pane_id>` prints exactly one line — `waiting_<kind>` /
   `active` / empty — and exits 0 always. Capture via `tmux_exec.tmux_socket_args()`
   + `capture-pane -p -e -t <id> -S -200`; classify with
   `prompt_patterns.all_patterns()` + `monitor_core.classify_content` (reuse the
   monitor's 6-line prompt window). **Verify at implementation** that importing
   `monitor_core` pulls no Textual App — if it does, import `strip_ansi` and
   `_prompt_detection_text` only and run the scoped pattern loop here.
   `waiting_<kind>` is the pattern `name` (grammar `[a-z0-9_]+`, what t1725_3's
   parser validates). `active` = no prompt detected right now; idle needs two samples
   over time and is deliberately not attempted.
3. `aitask_sync.sh`: for `live_lock` / `unknown_liveness` records on this host with a
   numeric pid, fill `PROT_PANE` from `ait_tmux_pane_for_pid` and `PROT_PANE_STATE`
   from the probe (via `python_resolve`) — both best-effort: empty on any failure,
   never block the sweep, bounded to one helper call + one probe per task, memoized
   across that task's paths. Both go through t1725_3's per-field `_pct_encode`.
4. Wire t1725_3's `--require-waiting` re-probe: in `_commit_group`, after the 5a.3
   state re-check and before the commit, resolve the pane and probe it; unless the
   result is `waiting_<kind>` → `_protect "holder_not_waiting"` with the observed state.
5. `shellcheck` the touched scripts; `bash tests/test_no_raw_tmux.sh`.

### Post-phase (risk mitigation `pane_unresolvable_degrades_to_pid`)

6. [pane_unresolvable_degrades_to_pid] Run the deferred sweep with a live lock whose
   pid is **not** a descendant of any gateway pane (the test shell itself, on the
   isolated socket) and assert the `DEFERRED_FILE:` record still emits with pid,
   email and host filled and both `pane` and `pane_state` empty. (The TUI half of
   this pin — a record with `pane=""` renders and offers no commit button — lands in
   t1725_5's `tests/test_sync_deferred_screen.py`.)

## Verification

- `tests/test_tmux_pane_for_pid.sh` on an isolated tmux socket
  (`tests/lib/tmux_isolation.sh`): the pane's own pid resolves; a child process of the
  pane resolves via the walk; an unrelated pid → exit 1; a session named `a|b`
  round-trips through t1725_3's encoding on the wire.
- `tests/test_pane_state_probe.py` with a captured-text seam (stub the capture):
  a `claude_askuserquestion` snippet → `waiting_claude_askuserquestion`; plain output
  → `active`; capture failure → `""`; the CLI form prints exactly one line and exits 0
  in all three.
- Sweep-level: a live lock anchored to a pane on the isolated socket whose screen
  shows the AskUserQuestion snippet → the record carries the pane target and
  `waiting_claude_askuserquestion`.
- `--require-waiting` end-to-end (the t1725_3 pin this task owns): the pane's screen
  is rewritten from the snippet to plain output *between* the first (deferred) sync
  and the retry with `--commit-for-task <id> --require-waiting` → `holder_not_waiting`,
  nothing committed; the same sequence with the screen left waiting → committed.
- `bash tests/test_live_endpoint*.sh`, `bash tests/test_no_raw_tmux.sh`,
  `bash tests/test_sync_deferral_and_quarantine.sh`,
  `bash tests/run_all_python_tests.sh --test-dir tests`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1731** id=2026-09-10T12:54:30Z.ed0c9589464acd0cc9f12fb3 from=t1731 from_verified=yes at=2026-09-10T12:54:29Z base=2f023c5949cddc06c78d11777a11edd8c2abfbbd base_branch=main dirty=yes host=omg16
>
> | t1731 (plan approved 2026-09-10) changes the outcome of the fixture shape your new live test relies on. Advisory; verify against the tree when you read this.
> | 
> | WHAT CHANGES. When `_rebase_blocked` blocks on a DIVERGED data branch (local_ahead>0 and remote_ahead>0) and a guarded merge is provably safe — the local and remote changed-file sets from the single merge base are disjoint (`--no-renames`), `git merge-tree --write-tree` is clean, and no protected or ignored path is among the paths the merge writes — `ait sync` now converges with a merge commit (built via commit-tree, advanced with `merge --ff-only --no-autostash --no-overwrite-ignore`), pushes, and emits the new bare status `MERGED`. It emits NO `DEFERRED:protected_dirty` line and NO `DEFERRED_FILE:` records in that case.
> | 
> | WHY IT HITS t1725_4. As of this moment `tests/test_sync_holder_pane_live.sh` is untracked in the shared checkout, so this is a moment-relative reading, not something the base SHA dates. Its `new_fixture` (~123-131 when I read it) builds: tracked t10_alpha.md edit + a local t20_beta.md commit + a pc2 advance touching only t30_gamma.md. That is exactly the disjoint diverged shape, so once t1731 lands every case reading deferral records (S1, S1a, S1c, S2, S3, E1a) would see `MERGED` instead.
> | 
> | SUGGESTED SHAPE. Make pc2 ALSO append to `t20_beta.md` (local and remote both change it -> overlap -> still defers; stderr names slug `sides_overlap`), or have the incoming commit touch `t10_alpha.md`. t1731 applies the same overlap reshape to test_sync_deferral_and_quarantine.sh Tests 1, 1b, 19, 31B, 33-33D and to the truth-table cell at test_sync_rebase_gate.sh:131.
> | 
> | FILE OVERLAP. t1731 edits aitask_sync.sh's main() gate, do_push's retry, `_load_incoming` (adds --no-renames), the header protocol block and show_help (a MERGED line, adjacent to — not inside — your uncommitted hunks near ~37-41 and ~154-157). It does NOT touch tests/lib/sync_fixture.sh or tests/test_sync_protect_paths.sh. If you land first, t1731 rebases onto your committed file; if not, t1731 commits only its own hunks and verifies that commit in an isolated worktree.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T11:56:18Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-10T12:40:43Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-09-10T12:48:20Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:9b55294d52f533bb

> **✅ gate:risk_evaluated** run=2026-09-10T12:48:20Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1725_4/risk_evaluated_2026-09-10T12:48:20Z-risk_evaluated-a1.log`
