---
Task: t671_separate_heartbeat_freshness_from_agent_terminal_status.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: Separate heartbeat freshness from agent terminal status (t671)

## Context

Today, `<agent>_status.yaml`'s `status` field overloads two concepts:

1. **Agent-self-reported lifecycle:** `Running` / `Completed` / `Error` / `Aborted` (plus runner-managed pre-launch states `Waiting` / `Ready` / `Paused`).
2. **Runner-imposed heartbeat-staleness signal:** A two-step grace window where the runner flips `status: Running → MissedHeartbeat → Error` purely because `<agent>_alive.yaml`'s `last_heartbeat` is stale, even when the agent is still alive and just slow to ping.

This is the root cause behind two existing workarounds:
- `brainstorm_app.py:3520–3534` (`_poll_initializer` Error/Aborted branch) installs a 30 s slow-watcher fallback because a status of Error can't be trusted to mean "the agent failed."
- `brainstorm_session.py:267–301` (`n000_needs_apply`) gates on output-file delimiter content rather than `status: Completed` for the same reason.

The fix: status is **purely agent-self-reported** going forward. Heartbeat freshness stays in `<agent>_alive.yaml` (already its own file) — consumers that need it call `check_agent_alive()` / `get_stale_agents()` (already exist in `agentcrew_utils.py`). The runner stops touching `_status.yaml: status` on heartbeat events.

### Decisions confirmed with the user
1. **MissedHeartbeat is removed entirely** from `AGENT_STATUSES` and `AGENT_TRANSITIONS` — no soft-warning state, no legacy compatibility alias. Existing in-flight crews must be cleaned via `ait crew cleanup` (documented as part of the migration note).
2. **Heartbeat freshness stays in `<agent>_alive.yaml` only.** No mirroring into `<agent>_status.yaml`, no new `last_heartbeat_at` / `heartbeat_stale` field. Consumers read both files when freshness matters.
3. **Brainstorm `_poll_initializer` and `n000_needs_apply` are out of scope** for this task. A follow-up child task will revisit those workarounds once t671 has soaked. The slow-watcher and delimiter gate stay untouched.

### Out of scope
- Brainstorm TUI `_poll_initializer` simplification → follow-up task.
- `n000_needs_apply` → archived rationale (`aiplans/p670_*`) explicitly prefers content-based; leave alone.
- Adding `last_heartbeat_at` / `heartbeat_stale` to `_status.yaml`.
- Dashboard "Process dead but status not updated" warning (`agentcrew_dashboard.py:328`) — that gate uses OS-level `process_alive`, a different signal from heartbeat. Stays.

---

## Implementation steps

### Step 1 — Remove `MissedHeartbeat` from the state machine

**File:** `.aitask-scripts/agentcrew/agentcrew_utils.py`

- Lines 18–26 (`AGENT_STATUSES`): drop `"MissedHeartbeat"` from the list.
- Lines 28–43 (`AGENT_TRANSITIONS`):
  - Drop `"MissedHeartbeat": [...]` entry entirely.
  - In `"Running": [...]`, remove `"MissedHeartbeat"` from the targets so `Running` only transitions to `Completed | Error | Aborted | Paused`.
- Lines 100–136 (`compute_crew_status`): change the `active` set on line ~118 from `{"Running", "MissedHeartbeat"}` to `{"Running"}`. Audit the rest of the rollup logic for any other `MissedHeartbeat` reference and drop it.

### Step 2 — Remove the heartbeat → status write path

**File:** `.aitask-scripts/agentcrew/agentcrew_runner.py`

- Delete `mark_stale_as_missed_heartbeat()` (lines 291–309) entirely.
- Delete `process_missed_heartbeat_agents()` (lines 311–351) entirely.
- In `run_loop()` main iteration (lines 942–945), remove the three lines that call `get_stale_agents` + `mark_stale_as_missed_heartbeat` + `process_missed_heartbeat_agents`. The runner no longer mutates `_status.yaml` based on heartbeat.
  - Note: `get_stale_agents()` itself stays in `agentcrew_utils.py` — consumers still need it as a read-only freshness query.
- `count_running()` (lines 283–288): change the active set from `("Running", "MissedHeartbeat")` to just `"Running"`.

After this step, the runner's only writes to `<agent>_status.yaml: status` are: (a) Waiting → Ready → Running gating in `launch_agent` (still legitimate, runner-managed pre-launch), (b) Paused / Resume / Reset commands, (c) launch-failure Error (genuinely terminal — the agent process never started). Nothing flips Running to Error from heartbeat alone.

### Step 3 — Update non-brainstorm consumers that filter on `MissedHeartbeat`

Audit and update these specific filters identified in the consumer inventory:

- **`.aitask-scripts/agentcrew/agentcrew_process_stats.py:142`** — `get_running_processes` filter `status not in ("Running", "Paused", "MissedHeartbeat")`: drop `"MissedHeartbeat"`.
- **`.aitask-scripts/agentcrew/agentcrew_dashboard.py`** — the `ProcessCard.render()` color-coding around lines 302–309 currently has a `MissedHeartbeat` branch; drop it (a `Running` agent with stale heartbeat will now be color-coded by the existing `process_alive` inference logic on line 328, which stays).
- **`.aitask-scripts/agentcrew/agentcrew_report.py`** (lines 113, 117–127, 175): no `MissedHeartbeat` filter changes required — already keyed on `Waiting` / `Running` / `Completed`. Verify with grep, no edit unless found.

**Audit step (must run before declaring complete):**
```bash
grep -rn "MissedHeartbeat" .aitask-scripts/ tests/ aitasks/ aiplans/ 2>/dev/null
```
Every remaining hit must be either (a) inside a test fixture being rewritten in Step 4, or (b) inside an archived plan / task file (which we leave alone — historical record). Live code under `.aitask-scripts/` must show zero hits after this step.

### Step 4 — Tests

**File:** `tests/test_crew_runner.sh`

- Existing tests around lines 661–722 exercise the `MissedHeartbeat → Error` grace-window transition. Rewrite these:
  - The "stale heartbeat" test: assert the agent's `status` stays `Running` even after `hb_timeout * 2` seconds of staleness; `get_stale_agents()` returns the agent; `<agent>_alive.yaml: last_heartbeat` is unchanged.
  - The "heartbeat recovery" test: assert that after the agent resumes heartbeats, no status mutation occurred at any point (the agent was always `Running`).
  - Drop the "grace expiry → Error" test entirely; it's no longer reachable.
- Other tests at lines 212, 237, 425, 481, 511, 551, 617, 627, 634, 672, 679, 704, 715, 722 that reference `MissedHeartbeat` in fixtures / assertions: rewrite to reflect the new state machine. Use `grep -n MissedHeartbeat tests/test_crew_runner.sh` to enumerate.

**Add two new tests:**

1. **Genuine Error self-report:** Spin up a Running agent, have it call `ait crew status ... set --status Error --message "boom"`. Assert `status: Error`, `error_message: "boom"`, `completed_at` populated. (Likely already exists in some form — extend / verify.)
2. **Slow-but-completing agent:** Simulate a Running agent whose heartbeats stop (`<agent>_alive.yaml: last_heartbeat` static for `2 * hb_timeout` seconds), then later writes `status: Completed` directly via the `cmd_set` CLI. Assert: `status` transitions `Running → Completed` with no intermediate `Error` and no transition rejected by `validate_agent_transition`.

### Step 5 — Migration documentation

Add a short note in the t671 plan's Final Implementation Notes (added during Step 8 plan consolidation) covering:

- In-flight `<agent>_status.yaml` files written by the prior runner may have `status: MissedHeartbeat`. These files become invalid after this refactor — the value isn't in `AGENT_STATUSES` and `validate_agent_transition` will reject mutations from it.
- Mitigation: existing crews must be cleaned via `ait crew cleanup --crew <id>` after upgrading. Document this in the commit message body so users searching the changelog find the upgrade hint.
- No code-level compatibility shim is added (per the user's "Remove entirely" decision).

### Step 6 — Create follow-up task for the brainstorm workarounds

After Step 8 commit but before Step 9 archival, create a follow-up task documenting the two deferred workarounds:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --name revisit_brainstorm_status_distrust_after_t671 \
  --type refactor \
  --priority low \
  --effort medium \
  --labels ait_brainstorm,agentcrew \
  --depends 671 \
  --desc-file -
```

The follow-up task description should reference:
- `brainstorm_app.py:3520–3534` (`_poll_initializer` slow-watcher fallback) — now that status is trustworthy, evaluate whether the 30 s slow-watcher and `_try_apply_initializer_if_needed()` retry can be removed or kept as belt-and-suspenders.
- `brainstorm_session.py:267–301` (`n000_needs_apply` four-delimiter gate) — re-evaluate whether the gate can simplify to `status == "Completed"` (archived `aiplans/p670_*` previously rejected this; the rejection rationale changes once t671 lands).
- The follow-up should soak this task for at least 1–2 weeks of real brainstorm usage before deciding either way.

---

## Critical files (summary)

| File | Change type |
|------|------|
| `.aitask-scripts/agentcrew/agentcrew_utils.py` | Edit (state machine) |
| `.aitask-scripts/agentcrew/agentcrew_runner.py` | Delete two functions, edit main loop and `count_running` |
| `.aitask-scripts/agentcrew/agentcrew_process_stats.py` | Edit one filter |
| `.aitask-scripts/agentcrew/agentcrew_dashboard.py` | Drop `MissedHeartbeat` color-coding branch |
| `tests/test_crew_runner.sh` | Rewrite stale-heartbeat tests; add two new tests |

Reused (no edits):
- `agentcrew_utils.py: get_stale_agents()` — already correct, returns agents with stale heartbeat without mutating status.
- `agentcrew_utils.py: check_agent_alive()` — heartbeat freshness check, used by `get_stale_agents`.
- `<agent>_alive.yaml: last_heartbeat` — heartbeat source of truth; schema unchanged.

---

## Verification

End-to-end sanity check after implementation:

1. **State machine audit:** `grep -rn "MissedHeartbeat" .aitask-scripts/ tests/` returns zero hits in live code; only archived plan files (`aiplans/archived/`, `aitasks/archived/`) may contain historical references and are left untouched.

2. **Run the full test suite for crew runner:**
   ```bash
   bash tests/test_crew_runner.sh
   ```
   All assertions pass, including the two new tests added in Step 4.

3. **Lint:**
   ```bash
   shellcheck tests/test_crew_runner.sh
   # (no python lint configured project-wide; rely on tests for the .py edits)
   ```

4. **Live smoke test (manual, optional but recommended):**
   - Start a brainstorm session that exercises the agent-crew runner.
   - During an agent's `Running` phase, deliberately make its heartbeat stale (kill the agent's heartbeat-emitting process or pause it for `> heartbeat_timeout_minutes`).
   - Observe: `<agent>_status.yaml: status` stays `Running` (does NOT flip to `MissedHeartbeat` or `Error`); `get_stale_agents()` reports the agent; `agentcrew_report.py` output shows the stale heartbeat alongside the still-`Running` status.
   - Resume the agent: `status` is still `Running`, agent eventually self-reports `Completed`.

5. **Archival readiness:** plan file consolidated with Final Implementation Notes per Step 9.

---

## Step 9 reference

After verification passes:
- Step 8: review changes, get user approval, commit code (`refactor: Separate heartbeat freshness from agent terminal status (t671)`) and plan file separately.
- Step 8c: manual-verification follow-up offer (the live smoke test in Verification §4 is a strong manual-verification candidate — accept the offer if prompted).
- Step 9: archive task + plan via `./.aitask-scripts/aitask_archive.sh 671`. Task `assigned_to` clears, status flips to `Done`, `git push`. Then create the follow-up task per Step 6.

---

## Final Implementation Notes

- **Actual work done:**
  - Removed `MissedHeartbeat` from `AGENT_STATUSES`, `AGENT_TRANSITIONS`, the bash mirror constant `AGENT_STATUS_MISSED_HEARTBEAT`, and from the `active` set in both `compute_crew_status` and `get_group_status` in `agentcrew_utils.py`.
  - Deleted `mark_stale_as_missed_heartbeat()` and `process_missed_heartbeat_agents()` (≈70 lines) from `agentcrew_runner.py`.
  - Simplified `count_running()` and `enforce_type_limits()` filters from `("Running", "MissedHeartbeat")` to just `"Running"`.
  - Replaced the heartbeat-driven status write path in `run_loop` with a read-only log line: `Stale heartbeat (status unchanged): ...`. `get_stale_agents()` is still called every iteration so the runner observes staleness, but it no longer mutates `_status.yaml`.
  - Dropped the MissedHeartbeat color from `agentcrew_dashboard.py`'s `STATUS_COLORS` map.
  - Dropped MissedHeartbeat from two filters in `agentcrew_process_stats.py` (`get_running_processes` and the dead-process self-correction routine).
  - Rewrote `tests/test_crew_runner.sh` Tests 16/17/18 to assert: stale heartbeat does NOT mutate status; staleness + recovery leaves status untouched; a heartbeat-stale Running agent self-reporting Completed transitions cleanly. Added a regression-guard assertion that `MissedHeartbeat not in AGENT_STATUSES`.
  - Rewrote `tests/test_crew_status.sh` Tests 2 (transitions), 3 (rollup), and 15 (Status CLI) to reflect the trimmed namespace and to assert the CLI rejects `--status MissedHeartbeat` as an unknown status.

- **Deviations from plan:**
  - Plan said dashboard's MissedHeartbeat branch was at lines 302–309; the actual location was the `STATUS_COLORS` map at line 71. Same outcome — dropped the entry.
  - Plan only named `test_crew_runner.sh` for test rewrites; the audit also turned up MissedHeartbeat assertions in `tests/test_crew_status.sh` Tests 2/3/15 that needed parallel updates. Both files now agree on the trimmed state machine.
  - The plan suggested asserting `error_message` recorded on a self-reported `set --status Error`. The CLI does not accept `--message` for `set` (only for `heartbeat`), so the assertion was reduced to verifying `completed_at` is stamped on the terminal Error self-report. The `error_message` write path remains exercised via the runner's launch-error path elsewhere.
  - Plan's "create follow-up task" step (Step 6) is deferred to the post-archival phase below — surfaced as a runtime offer rather than executed unconditionally.

- **Issues encountered:**
  - First-pass test ran exit code 2 due to an unsupported `--message` flag on `agentcrew_status.py set`; rewrote the assertion to check `completed_at` instead.
  - `tests/test_crew_groups.sh`, `tests/test_crew_report.sh`, and `tests/test_brainstorm_cli.sh` Test 1 (`session status is init`) all fail. Verified by running each on a pristine checkout of HEAD (pre-t671): they fail identically. **These are pre-existing flakes unrelated to t671** and are out of scope for this task. Worth tracking separately.

- **Key decisions:**
  - Per the user's "Stay in `_alive.yaml` only" answer, no new schema fields were added to `<agent>_status.yaml`. Heartbeat freshness consumers must call `get_stale_agents()` / `check_agent_alive()` (already present) — not read a mirrored field.
  - Per the user's "Remove entirely" answer, no compatibility alias was added. In-flight crews with `status: MissedHeartbeat` must be cleaned via `ait crew cleanup --crew <id>` after upgrading. Documented in commit message body.
  - Brainstorm `_poll_initializer` slow-watcher and `n000_needs_apply` four-delimiter gate were left untouched — out of scope per the "Defer to follow-up task" answer.

- **Migration:**
  - `<agent>_status.yaml` files written by the prior runner may have `status: MissedHeartbeat`. After this change `MissedHeartbeat` is not in `AGENT_STATUSES`, so the CLI rejects mutations from it and `validate_agent_transition` returns `False` for any source value of `MissedHeartbeat`.
  - Mitigation: clean in-flight crews with `ait crew cleanup --crew <id>` before resuming work. No code-level shim added (per user direction).

- **Follow-up task to create after archival:**
  - `revisit_brainstorm_status_distrust_after_t671` (low priority, medium effort, depends on 671). Re-evaluates whether the brainstorm `_poll_initializer` 30s slow-watcher (`brainstorm_app.py:3520-3534`) and `n000_needs_apply` four-delimiter gate (`brainstorm_session.py:267-301`) can be simplified now that `status` is trustworthy. Should soak for 1–2 weeks of real brainstorm usage before deciding.
