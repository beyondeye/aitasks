---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [brainstorm]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-20 01:36
updated_at: 2026-11-22 11:50
completed_at: 2026-11-22 11:50
---

## Origin

Spawned from t2278_5 during Step 8b review. Both were found while driving
the real TUIs on a sample project for the docs screenshots.

## Upstream defect

- `.aitask-scripts/brainstorm/brainstorm_session.py:154-157 — init builds the root node's description and the session brief from the first lines of the whole task file, frontmatter included, so they read "priority: medium | effort: medium"`
- `.aitask-scripts/lib/launch_modes_sh.sh:24 — falls back to a bare python3 from PATH and ignores AIT_PYTHON, so aitask_crew_init.sh fails under any HOME without ~/.aitask/venv even when AIT_PYTHON is set`

## Diagnostic context

- **Brainstorm root brief.** `aitask_brainstorm_init.sh` copies the whole task
  file into the spec (`cat "$TASK_FILE" > "$SPEC_FILE"`), and `init_session`
  takes the first non-empty lines that do not start with `---`. Those are YAML
  frontmatter lines. Visible in the Browse tab's root node and "Brief:" line
  (`website/static/imgs/aitasks_brainstorm_browse_tab.svg`; scene
  `brainstorm_browse_tab`). After the fix, regenerate that image with
  `/aitask-docs-screenshots brainstorm_browse_tab`.
- **Bare python3.** `ait brainstorm init` under a scratch `HOME` with
  `AIT_PYTHON` set failed with "failed to load launch_modes vocabulary":
  `launch_modes_sh.sh` uses `${_AIT_RESOLVED_PYTHON:-python3}`, and `python3`
  on PATH is the `~/.aitask/bin/python3` wrapper, which execs
  `$HOME/.aitask/venv/bin/python`. The screenshot tool works around it with a
  `python3` shim in its sample projects.

## Suggested fix

- Brainstorm: skip the frontmatter block when deriving the brief (or pass
  only the task body as the spec).
- launch_modes: honour `AIT_PYTHON` (or source `python_resolve.sh`) before
  falling back to `python3`.

The two are independent; split if that suits the work better.

## Not in scope here

The TUI switcher dialog being clipped in the 40-column minimonitor pane
(`.aitask-scripts/lib/tui_switcher.py:556`) is its own task, t2340: the clip
cuts actual hint-row text, so the user decided it must be fixed.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-22T08:47:33Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-22T09:46:40Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-22T09:50:21Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:ba740efe34c289bb

> **✅ gate:risk_evaluated** run=2026-11-22T09:50:21Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2339/risk_evaluated_2026-11-22T09:50:21Z-risk_evaluated-a1.log`
