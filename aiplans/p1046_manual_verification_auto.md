---
Task: t1046_manual_verification_brainstorm_crew_status_rollup_stale_foll.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1046 — Manual verification (auto-execution record)

Autonomous auto-verification of the 5-item checklist for **t1041** (derive-on-read
crew status/progress rollup). Every item was exercised against the **real** entry
points (`ait crew report`, `ait crew status`, `ait crew cleanup`, `ait crew
dashboard`) inside a throwaway fixture repo containing real crew worktrees, not
against unit-test doubles.

## Fixture

Built at `<scratchpad>/av1046/fixture` — a fresh `git init` repo with the real
`.aitask-scripts/` tree and the real `ait` dispatcher copied in (mirrors
`setup_test_repo` in `tests/test_crew_cleanup.sh`, plus `ait` so the checklist's
own `ait crew …` invocations are what actually runs).

Crews seeded via `ait crew init` + `ait crew addwork` (real worktrees), then the
member `*_status.yaml` and the aggregate `_crew_status.yaml` were forced apart to
simulate a dead runner that never rolled the aggregate forward:

| crew | member status | persisted `_crew_status.yaml` | purpose |
|---|---|---|---|
| `stale` | `Completed` | `Running` / 80 | items 1, 2, 3 |
| `killlive` | `Aborted` | `Killing` / 40 (+ `_runner_alive.yaml`) | item 4 |
| `aborted` | `Aborted` | `Running` / 80 | item 5 |
| `busy` | `Running` | `Completed` / 100 | negative control |
| `mixed` | `Completed`, `Aborted` | `Running` / 10 | negative control |

## Execution Log

### Item 1 — `ait crew report` derives Completed/100 from a stale aggregate
- **Item text:** In a real crew worktree with all member agents Completed but a stale `_crew_status.yaml` (Running/80), `ait crew report --crew <id>` shows Completed and 100%.
- **Approach:** CLI invocation against the fixture.
- **Action run:** `./ait crew report summary --crew stale`, `./ait crew report --batch summary --crew stale`, `./ait crew report --batch list`, `./ait crew status --crew stale get`.
- **Output (trimmed):**
  ```
  Crew: stale (Completed)
  Created: … | Progress: 100%

  CREW_ID:stale / CREW_STATUS:Completed / CREW_PROGRESS:100
  CREW:stale STATUS:Completed PROGRESS:100 AGENTS:1
  CREW_STATUS:Completed / CREW_PROGRESS:100
  ```
  Re-reading `_crew_status.yaml` after all four reads still shows `status: Running`
  / `progress: 80` — proving the value is **derived on read**, not silently
  rewritten.
- **Note on wording:** the checklist writes `ait crew report --crew <id>`; the real
  CLI requires the `summary` subcommand (`ait crew report summary --crew <id>`) —
  a bare `--crew` is rejected by argparse. Checklist shorthand, not a defect.
- **Verdict: pass**

### Item 2 — dashboard TUI derives in BOTH the list and the detail view
- **Item text:** `ait crew dashboard` (TUI) shows the derived status/progress in BOTH the crew list (CrewCard) and the detail view for that same stale crew.
- **Approach:** TUI interaction — real `ait crew dashboard` driven in a detached tmux session (200x45), pane captured with `capture-pane -p`.
- **Action run:** `tmux new-session -d -s av1046 -x 200 -y 45 … './ait crew dashboard'`; `send-keys Tab Tab Tab Enter` to focus the `stale` card and open its detail screen.
- **Output (trimmed):**
  ```
  crew list (CrewCard):
    stale  stale  Completed  ███████████████ 100%  Agents: 1  No runner

  detail view (CrewDetailScreen):
    stale  (stale)  Completed  ████████████████████ 100%
    ● worker (impl)  Completed  ░░░░░░░░░░ 0%
  ```
  Both surfaces agree, and both disagree with the persisted `Running`/80.
- **Interaction note:** `AgentCrewDashboard._refresh_data` remounts every `CrewCard`
  on its 5 s interval, which drops keyboard focus. `Tab` … `Enter` therefore has to
  land inside one 5 s window or `action_open_detail` finds no focused card. Not a
  rollup defect; recorded below.
- **Verdict: pass**

### Item 3 — cleanup ignores the stale aggregate and uses member state
- **Item text:** `ait crew cleanup --crew <id>` cleans a crew whose persisted status is stale-Running but whose member agents are all terminal.
- **Approach:** CLI invocation + filesystem assertion.
- **Action run:** `./ait crew cleanup --crew stale --batch` (persisted `Running`/80, member `Completed`).
- **Output (trimmed):** `CLEANED:stale`, rc=0; `.aitask-crews/crew-stale` removed.
- **Negative control:** crew `busy` — member `Running`, persisted lies `Completed`/100 →
  `NOT_TERMINAL:busy:members_not_terminal` (the exact stable third field from the
  t1041 plan), rc=1, worktree kept. So the predicate discriminates on member state
  in **both** directions and never trusts the persisted value.
- **Verdict: pass**

### Item 4 — Killing preserved only while the runner is live, then rolls forward
- **Item text:** A Killing crew with a live runner still shows Killing in the dashboard; once the runner stops (or heartbeat goes stale), it rolls forward to the derived terminal state.
- **Approach:** TUI interaction in tmux + targeted mutation of `_runner_alive.yaml`, with `f5` refresh between states.
- **Action run / state table** (crew `killlive`: persisted `Killing`/40, member `Aborted`):

  | `_runner_alive.yaml` | list (CrewCard) | detail view |
  |---|---|---|
  | `running`, heartbeat now | `Killing … 40%` | `Killing ████████░░ 40%` |
  | `running`, heartbeat −10 min | — | `Aborted ░░░░ 0%` |
  | `running`, heartbeat now (restored) | — | `Killing ████████░░ 40%` |
  | `stopped`, heartbeat now | `Aborted … 0%` | `Aborted ░░░░ 0%` |

- **Why this discriminates:** the member is `Aborted` (terminal) throughout, so
  without `runner_is_live` the crew would read `Aborted` in every row. The gate is
  also shown to be **bidirectional** — restoring a fresh heartbeat brings `Killing`
  back — so it is not a one-way latch. Both the `status != running` path and the
  `>RUNNER_LIVE_STALE_SECONDS` heartbeat path independently release the
  preservation, matching `agentcrew_utils.runner_is_live`.
- **Verdict: pass**

### Item 5 — all-aborted is Aborted (not Completed) and cleanup-eligible
- **Item text:** An all-aborted crew is reported as Aborted (not Completed) and is cleanup-eligible.
- **Approach:** CLI invocation + filesystem assertion.
- **Action run:** `./ait crew report --batch summary --crew aborted`; `./ait crew cleanup --crew aborted --batch`.
- **Output (trimmed):** `CREW_STATUS:Aborted` (persisted said `Running`/80); `CLEANED:aborted`, worktree removed.
- **Negative control:** crew `mixed` (members `Completed` + `Aborted`) →
  `CREW_STATUS:Completed`, `CREW_PROGRESS:50`. So `Aborted` is applied only when
  *every* member aborted, exactly per the all-terminal rule — the check is not
  vacuously reporting `Aborted` for any terminal set.
- **Verdict: pass**

## Live confirmation on the crew that motivated t1041

The real repo still carries `.aitask-crews/crew-brainstorm-1017` — the exact
worktree whose stale aggregate was observed while diagnosing t1020 and which
prompted t1041. Verified read-only (no cleanup run against the user's worktree):

```
persisted _crew_status.yaml : status: Running   progress: 80   (updated 2026-06-17)
members                     : comparator_001 Completed, explorer_001a/b/c Completed,
                              synthesizer_001 Aborted
ait crew report --batch summary --crew brainstorm-1017
                            : CREW_STATUS:Completed  CREW_PROGRESS:80  RUNNER_STATUS:stopped
crew_is_terminal(...)  [bash]: TRUE  -> cleanup-eligible
```

The originally-reported symptom (`Running` on a settled crew) is gone on the
original artifact. `progress: 80` is correct here rather than stale — 4 of 5
members reached `Completed` — and the mixed `Completed`+`Aborted` member set
resolves to `Completed` per the all-terminal rule, matching the `mixed` negative
control above.

## Corroborating automated suites (re-run at verification time)

- `bash tests/test_crew_cleanup.sh` → 6/6 passed
- `bash tests/test_crew_report.sh` → 7 tests, ALL TESTS PASSED
- `bash tests/test_crew_status.sh` → 5/5 passed
- `~/.aitask/venv/bin/python -m pytest tests/test_agentcrew_rollup.py -q` → 18 passed

## Upstream defects identified

- `.aitask-scripts/agentcrew/agentcrew_runner_control.py:59` — `get_runner_info`
  derives `stale` **only** from heartbeat age (`RUNNER_STALE_SECONDS = 120`) and
  ignores the file's own `status:` field. A runner that wrote `status: stopped`
  with a fresh heartbeat is therefore rendered as `Runner active (<host>, 5s ago)`
  by `CrewCard` / the detail runner bar. Observed directly in item 4's last row:
  the card read `killlive … Aborted … Runner active (omg16, 5s ago)` while the
  runner file said `stopped`. This is a second, divergent definition of "runner
  liveness" alongside `agentcrew_utils.runner_is_live`
  (`status == "running"` **and** heartbeat ≤ `RUNNER_LIVE_STALE_SECONDS = 180`) —
  two predicates, two thresholds, one concept. Pre-existing (t1041 added
  `runner_is_live`; it did not touch `get_runner_info`), display-only, and it does
  **not** affect the crew status rollup, so it did not fail any item.
- `.aitask-scripts/agentcrew/agentcrew_dashboard.py:984` — `_refresh_data` calls
  `remove_children()` and remounts every `CrewCard` on the 5 s interval, discarding
  keyboard focus. `Enter` / `r` / `k` / `d` all resolve their target through
  `_get_focused_crew_id()`, so any of them pressed more than ~5 s after the last
  `Tab` silently degrades to the `"No crew selected"` notification. Pre-existing
  and unrelated to t1041.

## Cleanup

- Removed fixture repo `<scratchpad>/av1046/fixture` (including its crew worktrees
  via `git worktree prune`) and the helper scripts `setup.sh` / `seed.sh`.
- Killed tmux session `av1046`.
- No files outside the scratchpad were mutated except this plan and the t1046
  checklist itself.
