---
Task: t986_5_minimonitor_trigger_spawn_config.md
Parent Task: aitasks/t986_shadow_agent.md
Sibling Tasks: aitasks/t986/t986_1_*.md, aitasks/t986/t986_2_*.md, aitasks/t986/t986_3_*.md, aitasks/t986/t986_4_*.md, aitasks/t986/t986_6_*.md
Archived Sibling Plans: aiplans/archived/p986/p986_*_*.md
Worktree: (none — current branch, profile 'fast')
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-14 23:39
---

# Plan: t986_5 — minimonitor trigger + spawn glue + settings/config

## Context

Final integration child of the shadow agent (t986). A minimonitor keybinding
(`e`) that, on the followed coding agent, spawns the `shadow` companion agent —
by default a new pane in the **same tmux window** — and passes it the followed
pane id so the t986_4 `/aitask-shadow` skill can self-capture the screen on
demand. Adds the supporting config: a `defaults.shadow` codeagent default and a
same-window-vs-new-window placement toggle.

Deps (both **LANDED**, verified against the current tree):
- **t986_1** — multi-agent-per-window substrate. The shadow pane is classified
  as a helper (excluded from agent lists) **iff** it carries the pane user
  option `@aitask_shadow_target` set to the followed agent's pane id. This
  option is the *authoritative* classifier (a same-window shadow shares the
  agent's window name, so the `agent-shadow-*` name only exists for the
  separate-window placement). It also drives `kill_agent_pane_smart` counting
  and the `aitask_companion_cleanup.sh` shadow auto-kill.
- **t986_4** — the `/aitask-shadow <followed_pane_id> [<task_id>]`
  user-invocable command + `aitask_shadow_capture.sh`. The launcher passes only
  the pane id (argv-safe); the skill captures on demand. Confirmed
  `user-invocable: true`, argv contract matches.

## Verification findings (refinements vs the original task notes)

1. **Config toggle lives in `TMUX_CONFIG_SCHEMA`, not `PROJECT_CONFIG_SCHEMA`.**
   `settings/settings_app.py` has a dedicated `TMUX_CONFIG_SCHEMA` (≈216–257,
   keys `default_session`/`default_split`/`prefer_tmux`/`git_tui`). The toggle
   belongs there as `shadow_same_window` (read at runtime as
   `tmux.shadow_same_window`).
2. **`launch_in_tmux()` returns `(pane_pid, error)` — NOT the new pane id.**
   It captures `#{pane_pid}` from `split-window -P` / `new-window -P`
   (agent_launch_utils.py:588–615). To set `@aitask_shadow_target` on the
   shadow pane I must resolve its `pane_id`. Do this read-only by matching the
   returned `pane_pid` against `list-panes -s -F '#{pane_id} #{pane_pid}'` —
   avoiding any change to `launch_in_tmux`'s shared 2-tuple signature (all
   callers unpack `_, err = launch_in_tmux(...)`; widening it is needless blast
   radius).
3. **The `pane-died` cleanup hook is wired today only in the git-TUI path**
   (`tui_switcher.py:1078–1087`). Normal agent+minimonitor launches
   (`_launch_pick_for_own`, `codebrowser.action_launch_agent`) do NOT set it.
   So the followed agent's pane has no hook, and the t986_1 cleanup script can
   only auto-kill the bound shadow when that hook fires. t986_5 must attach
   `remain-on-exit on` + the `pane-died → aitask_companion_cleanup.sh
   <agent_pane> <companion_pane>` hook to the followed agent pane (mirroring the
   git-TUI block).
4. **No existing `action_launch_*` in minimonitor.** Model the new
   `action_launch_shadow` on the in-app launch pattern in `_launch_pick_for_own`
   (minimonitor_app.py ≈905–935) + `codebrowser.action_launch_agent`
   (≈1367–1418), but **without** the interactive `AgentCommandScreen` modal —
   placement is config-driven, so build the command directly via
   `resolve_dry_run_command(root, "shadow", pane_id, task_id)` and call
   `launch_in_tmux` with a programmatic `TmuxLaunchConfig`.
5. **Binding key `e` is free** in minimonitor's BINDINGS (138–152). Use `e`.
6. **`shadow` op must be added to `SUPPORTED_OPERATIONS`** (aitask_codeagent.sh:28)
   AND get a per-agent dispatch case in `build_invoke_command` (≈412–490).

## Implementation steps

### 1. Codeagent `shadow` operation + default
- `aitask_codeagent.sh:28` — add `shadow` to `SUPPORTED_OPERATIONS`.
- `aitask_codeagent.sh` `build_invoke_command` (≈412–490) — add a `shadow`
  case under each agent, mirroring `pick`:
  - `claudecode`: `CMD+=("/aitask-shadow ${args[*]}")`
  - `opencode`: `CMD+=("--prompt" "/aitask-shadow ${args[*]}")`
  - `codex`: `prompt=$(build_skill_prompt "\$aitask-shadow" "${args[@]}")`
    (analysis-style — does NOT force plan mode). The Codex/OpenCode command
    *wrappers* themselves are the t988/t989 follow-ups; wiring the dispatch case
    here keeps the op uniform and is cheap.
- `aitasks/metadata/codeagent_config.json` **and** `seed/codeagent_config.json`
  — add `"shadow": "claudecode/opus4_8"` to `defaults`.
- `settings/settings_app.py` `OPERATION_DESCRIPTIONS` (≈113) — add a `"shadow"`
  entry (e.g. `"Model used for the shadow companion agent (launched via
  minimonitor 'e')"`). This is the **only** UI wiring needed: the "Agent
  Defaults" tab (`_populate_agent_tab`) is data-driven over the union of
  `defaults` keys, so `defaults.shadow` becomes editable in `ait settings`
  automatically (project setting + `.local` user override, with verified-score
  labels) — satisfying parent t986's "default agent+model configurable in
  settings" requirement. Without the description entry the row renders unlabeled.

### 2. Placement toggle in settings + seed
- `settings/settings_app.py` `TMUX_CONFIG_SCHEMA` — add a `shadow_same_window`
  entry (type `bool`, default `"true"`, summary/detail), following the
  `prefer_tmux` precedent.
- `seed/project_config.yaml` `tmux:` section (≈212–289) — add a commented
  `# shadow_same_window: true` example consistent with the other tmux keys.

### 3. minimonitor binding + `action_launch_shadow`
In `monitor/minimonitor_app.py`:
- Add `Binding("e", "launch_shadow", "Shadow")` to BINDINGS (138–152).
- Add `action_launch_shadow(self)`:
  1. `snap = self._find_own_agent_snapshot()`; if `None`, `self.notify(...)`
     and return.
  2. `followed_pane = snap.pane.pane_id`;
     `task_id = self._task_cache.get_task_id_for_pane(snap.pane)` (may be None).
  3. Build args: `[followed_pane]` plus `[task_id]` when non-None.
  4. `agent_string = resolve_agent_string(root, "shadow")`;
     `cmd = resolve_dry_run_command(root, "shadow", *args)`. On `None`, notify
     and return.
  5. Read `tmux.shadow_same_window` (default `True`) from
     `project_config.yaml` (reuse the existing yaml-read pattern already in
     `maybe_spawn_minimonitor`).
  6. Build `TmuxLaunchConfig`:
     - same-window: `new_window=False`, `window=<agent window>`,
       `split_direction` from tmux config default.
     - separate-window: `new_window=True`, `window=f"agent-shadow-{task_id or 'x'}"`.
  7. `pane_pid, err = launch_in_tmux(cmd, cfg)`; on `err`, notify and return.
  8. Resolve the shadow `pane_id` from `pane_pid` (step 4 helper).
  9. Set the authoritative binding via the gateway:
     `set-option -p -t <shadow_pane> @aitask_shadow_target <followed_pane>`.
  10. Attach the cleanup hook to the **followed agent** pane (step 5 helper):
      `remain-on-exit on` + `pane-died → aitask_companion_cleanup.sh
      <followed_pane> <companion_pane>`, where `<companion_pane>` is the
      minimonitor's own pane id (`os.environ.get("TMUX_PANE")`).
  11. `self.notify("Launched shadow agent")` and refresh.

### 4. Helper: resolve pane id from pane pid (agent_launch_utils.py)
Add `resolve_pane_id_by_pid(session: str, pid: int) -> str | None` — read-only
`list-panes -s -F '#{pane_id} #{pane_pid}'` through `_TMUX`, return the matching
`#{pane_id}`. Keep it a thin, importable unit (testable with a faked
`_TMUX.run`). minimonitor calls it after `launch_in_tmux`.

### 5. Helper: attach shadow-cleanup hook (agent_launch_utils.py)
Add `attach_shadow_cleanup_hook(agent_pane: str, companion_pane: str) -> None`
that sets `remain-on-exit on` and the pane-scoped `pane-died` hook on
`agent_pane`, factoring out the exact sequence currently inlined at
`tui_switcher.py:1078–1087` (gateway-only). Both call sites can share it (note
the tui_switcher de-dup as a sibling note; do not refactor it in this task
unless trivial). This keeps raw tmux out of the Python layer
(`test_no_raw_tmux.sh` stays green).

All tmux access in steps 3–5 goes through the `_TMUX` gateway.

## Verification

- **Config read-path test** (`tests/test_shadow_spawn_config.sh`, bash+jq /
  embedded python): `defaults.shadow` resolves through the agent-string chain
  (CLI → `.local` → `codeagent_config.json` → `DEFAULT_AGENT_STRING`) via
  `aitask_codeagent.sh --dry-run invoke shadow %5 986_5`, asserting the emitted
  command contains `/aitask-shadow %5 986_5`; assert `shadow` is in
  `SUPPORTED_OPERATIONS`.
- **Pane-id resolver unit test**: feed `resolve_pane_id_by_pid` a faked
  `list-panes` output and assert correct pid→pane_id match (and `None` on miss).
- `bash tests/test_no_raw_tmux.sh` stays green (spawn + option + hook via
  gateway / factored helper).
- `shellcheck .aitask-scripts/aitask_codeagent.sh` clean; `python -m py_compile`
  the edited `.py` files.
- **Settings surface:** `ait settings` → "Agent Defaults" tab shows an editable
  `shadow` row (project + local layers) with the new description label.
- **Manual (covered by t986_7):** press `e` in minimonitor on a followed agent →
  shadow spawns in the same window, the shadow pane does NOT appear in the agent
  list (carries `@aitask_shadow_target`), and killing the followed agent
  auto-kills the shadow.

## Risk

### Code-health risk: medium
- Attaching `remain-on-exit on` + a `pane-died` cleanup hook to the **followed
  agent pane** changes that pane's lifecycle: the minimonitor companion now
  also despawns when the agent dies (today, agent windows get no such hook, so
  the companion lingers). Beneficial and consistent with the git-TUI companion
  behavior, but it is a behavior change on a load-bearing pane — "what if
  someone edits the spawn flow unaware?" · severity: medium · → mitigation:
  in-scope (factor the hook into one shared helper so both call sites stay in
  lockstep; `test_no_raw_tmux.sh` + the t986_7 live verification cover it)
- Moderate, additive blast radius across 5 areas (minimonitor, agent_launch
  helpers, codeagent dispatch, two config files, settings schema); each edit
  mirrors an established pattern (pick dispatch, tui_switcher hook, tmux config
  keys) · severity: low · → mitigation: none needed
- Resolving the shadow pane id from `pane_pid` rather than widening
  `launch_in_tmux`'s shared return tuple keeps the change localized · severity:
  low · → mitigation: none needed

### Goal-achievement risk: medium
- The `@aitask_shadow_target` binding depends on a correct `pane_pid → pane_id`
  resolution; if it returns `None` (race / pid reuse), the option is unset and
  the shadow would be listed as an agent and never auto-killed · severity:
  medium · → mitigation: in-scope (deterministic match immediately after spawn;
  unit-tested; notify-on-failure so the user sees it)
- Correct dispatch routing and advisory-only behavior of the spawned skill are
  validated only by the live manual-verification sibling (t986_7), not an
  automated test · severity: medium · → mitigation: in-scope (t986_7)

_No `### Planned mitigations` subsection: both axes are mitigated in-scope (this
task's config + unit tests, `test_no_raw_tmux.sh`, and the t986_7 aggregate
manual-verification sibling). No separate before/after follow-up task would add
value._

## Coordination & follow-ups
- **t988 / t989** (Codex / OpenCode `/aitask-shadow` wrapper ports) — the
  dispatch case added in step 1 references the slash-command those wrappers will
  provide; no new coordination needed beyond the existing tasks.
- **tui_switcher.py** — its inlined hook block (1078–1087) becomes a candidate
  to switch to the new `attach_shadow_cleanup_hook` helper; note as a sibling
  cleanup, not required here.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9 (child-task path:
archive to `aitasks/archived/t986/` + `aiplans/archived/p986/`; parent t986
archives only when all children complete).

## Final Implementation Notes

- **Actual work done:** All 5 plan steps implemented.
  - `aitask_codeagent.sh`: `shadow` added to `SUPPORTED_OPERATIONS`; dispatch
    cases for claudecode (`/aitask-shadow ${args[*]}`), opencode (`--prompt
    /aitask-shadow ...`), and codex (`build_skill_prompt "$aitask-shadow"`).
  - `lib/codex_plan_policy.sh`: `shadow` added to the relaxed (default-mode)
    skill set alongside `qa|explain` — the shadow is advisory/read-only, so it
    must NOT be routed through the `/plan` PTY wrapper.
  - `lib/agent_launch_utils.py`: new `resolve_pane_id_by_pid(session, pid)`
    (matches the pid `launch_in_tmux` returns to the new pane's id) and
    `attach_shadow_cleanup_hook(agent_pane, companion_pane)` (factors out the
    `remain-on-exit on` + `pane-died → aitask_companion_cleanup.sh` wiring that
    was inlined in `tui_switcher`). Both gateway-only.
  - `monitor/minimonitor_app.py`: `Binding("e", "launch_shadow", ...)` +
    `action_launch_shadow()` — resolves followed pane + task id, builds the
    `shadow` command via `resolve_dry_run_command`, launches same-window (split)
    by default or separate-window (`agent-shadow-<id>`) per
    `tmux.shadow_same_window`, stamps `@aitask_shadow_target` on the resolved
    shadow pane, and attaches the cleanup hook. Imports `SHADOW_TARGET_OPTION`,
    `resolve_pane_id_by_pid`, `attach_shadow_cleanup_hook`.
  - `settings/settings_app.py`: `OPERATION_DESCRIPTIONS["shadow"]` (labels the
    auto-rendered Agent-Defaults row) + `TMUX_CONFIG_SCHEMA["shadow_same_window"]`
    (bool, default true).
  - `codeagent_config.json` (seed + project) `defaults.shadow`; seed
    `project_config.yaml` commented `shadow_same_window` example.
  - `tests/test_shadow_spawn_config.sh` (15 assertions): per-agent dry-run
    resolution, op support, codex-plan-policy relaxation, and the
    `resolve_pane_id_by_pid` unit (faked gateway).
- **Deviations from plan:** (1) Plan said the toggle went in `PROJECT_CONFIG_SCHEMA`;
  the verify pass corrected this to the dedicated `TMUX_CONFIG_SCHEMA` (done).
  (2) The project-level `defaults.shadow` was set to `claudecode/sonnet4_6` (the
  seed default remains `claudecode/opus4_8`) — a lighter model suits the
  advisory companion; both layers are valid since project config overrides seed.
  (3) Added the `OPERATION_DESCRIPTIONS` entry (surfaced during the plan-review
  Q on settings configurability) so the data-driven settings row is labeled.
- **Issues encountered:** None. `launch_in_tmux` returns `pane_pid` (not the new
  `pane_id`), so the `@aitask_shadow_target` stamp needs `resolve_pane_id_by_pid`
  — anticipated in the plan and implemented as a read-only pid→pane_id match,
  avoiding a blast-radius change to `launch_in_tmux`'s shared return tuple.
- **Key decisions:** (1) Codex shadow runs in default/analysis mode, not plan
  mode. (2) The pane-died cleanup hook is attached to the *followed agent* pane
  at shadow-spawn time (the agent had none before — only the git-TUI path wired
  it); this also makes the agent's minimonitor companion despawn on agent death,
  a beneficial side effect consistent with git-TUI behavior. (3) The hook logic
  is factored into `attach_shadow_cleanup_hook` so the new call site and the
  existing `tui_switcher` block can share one implementation.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **t986_6 (docs):** document `/aitask-shadow` launch via minimonitor `e`, the
    `tmux.shadow_same_window` toggle, and the `defaults.shadow` agent+model
    config (editable in `ait settings` → Agent Defaults, project + local layers).
  - **t986_7 (manual verification):** live-verify `e` spawns the shadow in the
    same window, the shadow pane is absent from the agent list (carries
    `@aitask_shadow_target`), and killing the followed agent auto-kills the shadow.
  - **t988 / t989:** the codeagent dispatch already emits the opencode/codex
    `/aitask-shadow` command; those tasks add the actual command-wrapper skills.
  - **tui_switcher.py** can now switch its inlined `remain-on-exit`/`pane-died`
    block (≈1078–1087) to `attach_shadow_cleanup_hook` — small dedup, not done
    here to keep this task's blast radius tight.
