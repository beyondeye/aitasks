---
Task: t1071_5_shadow_spawn_learn_skill.md
Parent Task: aitasks/t1071_shadow_error_diagnosis_and_learn_skill_command.md
Sibling Tasks: aitasks/t1071/t1071_6_*.md, aitasks/t1071/t1071_7_*.md
Archived Sibling Plans: aiplans/archived/p1071/p1071_1_*.md … p1071_4_*.md
Base branch: main
---

# Plan — t1071_5: shadow spawns a learner agent (`/aitask-learn-skill <followed_pane>`)

## Context

The `aitask-learn-skill` engine (t1071_2, landed) already accepts a tmux pane id
and does the read-only capture + analysis + skill generation itself. t1071_5 wires
the **shadow agent** to spawn a *dedicated learner* pointed at the followed agent's
pane — **without** running the learn itself (the shadow is advisory/read-only and a
learn run would occupy it). So this task reduces to "spawn the learner".

There is an exact in-tree precedent: **t986_5** ("shadow spawn glue") added a
`shadow` operation to `aitask_codeagent.sh` and the helper functions
`resolve_pane_id_by_pid()` / `attach_shadow_cleanup_hook()` in
`lib/agent_launch_utils.py`, consumed by minimonitor's `action_launch_shadow()`
(Python TUI). t1071_5 is the analogue, with one structural difference: the trigger
is the shadow **markdown skill**, which cannot call the Python `launch_in_tmux()`
directly — so the spawn needs a **bash-callable** path.

**Design decisions (confirmed with user):**
- **Spawn placement:** a new **tmux window** (full width), not a cramped split pane.
- **Lifecycle:** the learner is a **first-class agent, user-managed** — NO
  classifier pane option (so it shows in `ait monitor`), no pane-died cleanup hook;
  the user closes its window when the learn completes.
- **Spawn mechanism: reuse `agent_launch_utils.launch_in_tmux()`** (the same
  centralized launcher minimonitor's `action_launch_shadow()` and tui_switcher's
  `action_shortcut_explore()` use), via a small Python shim. *(Revised after review:
  a bash-only `ait_tmux new-window` would fork the launcher contract — cwd `-c`
  handling, exact-match targeting, pane-pid resolution, and future launcher defaults
  all live in `launch_in_tmux()`; a bash slice would silently drift from it.)*

## Guardrail (load-bearing)

The shadow stays **advisory-only w.r.t. the followed pane**: it *spawns* a learner
in a new window; it never sends keystrokes to the followed pane. The learner only
**reads** the followed pane (via `aitask_shadow_capture.sh` inside the learn skill).
Both sides are read-only against the followed agent — guardrail-safe by construction.

## Files

| File | Change |
|------|--------|
| `.aitask-scripts/aitask_codeagent.sh` | Add `learn` to `SUPPORTED_OPERATIONS`; add a `learn` case in `build_invoke_command()` for all three agents (claudecode / codex / opencode), emitting `/aitask-learn-skill <args>`. Update `show_help` "Operations:" line. |
| `aitasks/metadata/codeagent_config.json` + `seed/codeagent_config.json` | Add an explicit `"learn": "claudecode/opus4_8"` default to `defaults` in both. Without it `resolve learn` would silently fall back to the hardcoded `DEFAULT_AGENT_STRING` (every other op has an explicit default). opus4_8 = a capable model for skill authoring; adjustable per-project/per-user via the normal resolution chain. |
| `.aitask-scripts/lib/codex_plan_policy.sh` | Add `learn` to the relaxed (no-forced-plan-mode) set: `qa\|explain\|shadow\|learn) return 1`. Learn is interactive but not a task-planning skill — it should launch in Codex's default mode like `shadow`. |
| `.aitask-scripts/lib/agent_launch_utils.py` | Add a small public `pane_session(pane_id)` gateway helper (resolve a pane's session name via the cached `_TMUX` client) and a pure `unique_window_name(existing, base)` helper (counter suffix, mirrors `action_shortcut_explore`'s `agent-explore-{n}` loop). Both unit-testable without live tmux. |
| `.aitask-scripts/aitask_shadow_spawn_learner.py` | **NEW** executable Python launcher (shadow-facing). Reuses `resolve_dry_run_command()` + `TmuxLaunchConfig(new_window=True)` + `launch_in_tmux()` + `resolve_pane_id_by_pid()`. `--dry-run` = command resolution only (no tmux). |
| `.claude/skills/aitask-shadow/spawn-learn-skill.md` | **NEW** shadow sub-procedure: confirm → call the launcher → report the new window. Advisory-only note. |
| `.claude/skills/aitask-shadow/SKILL.md` | Add one Step 3 routing entry pointing at `spawn-learn-skill.md`. (Step 0 greeting auto-derives — do NOT hardcode.) |
| `tests/test_shadow_spawn_learner.sh` | **NEW** test, modeled on `tests/test_shadow_spawn_config.sh`: dry-run resolution of the `learn` op across agents + the launcher's `--dry-run` (no-tmux) output + the pure `unique_window_name()` helper. |

## Step-by-step

### 1. `aitask_codeagent.sh` — the `learn` operation
- Add `learn` to `SUPPORTED_OPERATIONS=(pick explain batch-review qa explore raw shadow learn)`.
- In `build_invoke_command()`:
  - **claudecode** case: `learn) CMD+=("/aitask-learn-skill ${args[*]}") ;;`
  - **codex** case: add `learn) prompt=$(build_skill_prompt "\$aitask-learn-skill" "${args[@]}") ;;`
    inside the skill-launch branch (the `codex_skill_forces_plan_mode` check then
    routes it to the default-mode direct invocation, see step 2).
  - **opencode** case: `learn) CMD+=("--prompt" "/aitask-learn-skill ${args[*]}") ;;`
- Update `show_help` "Operations:" line to include `learn`.
- Mirrors the existing `shadow` op exactly (which takes a `%pane [task]` argv).
- **Explicit default:** add `"learn": "claudecode/opus4_8"` to `defaults` in
  `aitasks/metadata/codeagent_config.json` and `seed/codeagent_config.json`, so
  `resolve learn` returns a configured default rather than falling back to
  `DEFAULT_AGENT_STRING` (matches how `shadow`/`pick`/etc. are configured).

### 2. `codex_plan_policy.sh` — relaxed mode for `learn`
- `case "${1#aitask-}" in qa|explain|shadow|learn) return 1 ;; …`. Without this,
  codex would force the `/plan` PTY wrapper (`aitask_codex_plan_invoke.py`) — wrong
  for an interactive non-planning skill. (The test asserts no wrapper for codex.)

### 3. `agent_launch_utils.py` — two small reusable helpers
- `pane_session(pane_id: str) -> str | None` — resolve a pane's session name via the
  cached `_TMUX` gateway (`display-message -p -t <pane> '#{session_name}'`). Keeps
  tmux access centralized in the launcher module (no raw tmux in the new script).
- `unique_window_name(existing: set[str], base: str) -> str` — pure: return `base`
  if free, else `base-2`, `base-3`, … Mirrors `action_shortcut_explore`'s
  `while f"agent-explore-{n}" in running: n += 1` (tui_switcher.py:1041). Pure ⇒
  unit-testable without tmux.

### 4. `aitask_shadow_spawn_learner.py` — NEW Python launcher (reuses `launch_in_tmux`)
Executable (`#!/usr/bin/env python3`); self-bootstraps `lib/` onto `sys.path` like
the other `.aitask-scripts/*.py`. Imports `resolve_dry_run_command`,
`TmuxLaunchConfig`, `launch_in_tmux`, `resolve_pane_id_by_pid`, `get_tmux_windows`,
`pane_session`, `unique_window_name` from `agent_launch_utils`.

```
Usage: aitask_shadow_spawn_learner.py [--dry-run] <followed_pane_id> [<source_task_id>]
```
1. Validate `<followed_pane_id>` non-empty.
2. `project_root` = repo root (parent of `.aitask-scripts`). Resolve the learn
   command: `cmd = resolve_dry_run_command(project_root, "learn", followed_pane)`
   (this internally shells `aitask_codeagent.sh --dry-run invoke learn` — **no live
   tmux**). Print `SPAWN_FAILED:resolve` and exit non-zero if `None`.
3. `base = "agent-learn-" + task_id` if a task id was passed, else `"agent-learn"`.
4. **`--dry-run`** (the no-tmux seam): print `DRY_RUN_SPAWN: window=<base> cmd=<cmd>`
   and exit 0 — does **not** call `pane_session`/`get_tmux_windows`/`launch_in_tmux`,
   so it works in CI even when `<followed_pane_id>` does not exist. (Separates
   command-resolution proof from live session targeting — concern from review.)
5. **Live:** `sess = pane_session(followed_pane)`; `SPAWN_FAILED:no_session` if None.
   `existing = {name for _, name in get_tmux_windows(sess)}`;
   `window = unique_window_name(existing, base)`. Build
   `TmuxLaunchConfig(session=sess, window=window, new_session=False,
   new_window=True, cwd=str(project_root))` and call `launch_in_tmux(cmd, cfg)` →
   `(pane_pid, err)`. On `err`, print `SPAWN_FAILED:<err>`. Else
   `pane_id = resolve_pane_id_by_pid(sess, pane_pid)`; print
   `LEARNER_SPAWNED:<pane_id> WINDOW:<window>`.

The `agent-learn-*` window name keeps the learner visible/recognized as a normal
agent in `ait monitor` (first-class, per the lifecycle decision). NO
`@aitask_shadow_target`, NO cleanup hook (it is not a shadow companion).

Rejected alternatives: a bash-only `ait_tmux new-window` (forks the centralized
launcher contract — review concern); split-pane placement (cramped for a working
agent); a classifier+cleanup-hook lifecycle (would hide a legitimate working agent
from monitor).

### 5. `spawn-learn-skill.md` — NEW shadow sub-procedure
- Header + "advisory-only" note (spawns a learner in a NEW window; never drives the
  followed pane).
- **Inputs:** the followed pane id (shadow arg `<followed_pane_id>`); optional
  `<source_task_id>` for the window label.
- Procedure: (1) briefly confirm with `AskUserQuestion` that the user wants to spawn
  a learner pointed at the followed agent's workflow; (2) on confirmation run
  `./.aitask-scripts/aitask_shadow_spawn_learner.py <followed_pane_id> [<task_id>]`;
  (3) parse `LEARNER_SPAWNED:` / `SPAWN_FAILED:` and tell the user the learner is
  running in its own window (it will capture the followed pane and walk them through
  multi-part selection + generalization), and that the shadow remains free to keep
  advising. On-request only — never auto-spawn.

### 6. `aitask-shadow/SKILL.md` — Step 3 routing entry
- Add under "Structured analyses": **"Learn a skill from what the followed agent
  just did"** ("learn a skill from this", "capture this workflow as a skill") →
  read and follow `spawn-learn-skill.md`. The Step 0 greeting derives from Step 3
  automatically (single source of truth — do not hardcode a copy).

### 7. Cross-agent note (no port task needed)
- `aitask_codeagent.sh` + `codex_plan_policy.sh` are **shared** dispatcher helpers
  (already multi-agent) — the `learn` op serves all three agents in one place.
- The shadow `spawn-learn-skill.md` sub-procedure and the `SKILL.md` Step 3 entry
  are **Claude-tree only**: per `aidocs/framework/shadow_agent.md`, Codex/OpenCode
  shadow are thin SKILL.md wrappers redirecting into the Claude tree, so shadow
  sub-procedure edits are Claude-only. **No cross-agent port follow-up.**

## Risk

### Code-health risk: low
- New surface is one Python launcher + two small helpers in `agent_launch_utils.py`
  + one markdown sub-procedure + a one-line routing entry; the `learn` codeagent op
  and the `codex_plan_policy` line mirror the existing `shadow` op exactly. The
  launcher reuses `launch_in_tmux()` (no raw tmux), so `test_no_raw_tmux.sh` stays
  green and the change does not fork the launcher contract. · severity: low · →
  mitigation: TBD
- Reuses landed machinery (`launch_in_tmux` / `resolve_dry_run_command` /
  `resolve_pane_id_by_pid` in the launcher module; `aitask_codeagent.sh` resolution
  chain; `aitask_shadow_capture.sh` inside the learn skill); no new code paths in
  load-bearing modules. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- The heavy lifting (capture / analyze / generate) already lives in the t1071_2
  learn skill; this task only resolves a command and opens a window. Command
  resolution and the window-name targeting logic are deterministic and unit-tested
  without tmux (`--dry-run` + the pure `unique_window_name()`). · severity: low · →
  mitigation: TBD
- The live `launch_in_tmux` spawn itself is runtime-behavioral and not exercised by
  unit tests (only its no-tmux seams are). · severity: low · → mitigation: queue a
  manual-verification follow-up (Step 8c) for the live shadow→learner spawn.

No before/after risk-mitigation tasks needed (`risk_mitigations_planned = false`).

## Verification

- `bash tests/test_shadow_spawn_learner.sh` — new test passes:
  - `learn` resolves via `--dry-run invoke learn %5 [task]` for claude / codex /
    opencode and emits `/aitask-learn-skill` + the pane id; codex does NOT route
    through `aitask_codex_plan_invoke` (relaxed mode); unknown op still errors.
  - `aitask_codeagent.sh resolve learn` returns the explicit configured default
    (`AGENT_STRING:claudecode/opus4_8` from `codeagent_config.json`), proving the
    `learn` default is wired and not a silent `DEFAULT_AGENT_STRING` fallback.
  - `aitask_shadow_spawn_learner.py --dry-run %5 1071_5` prints `DRY_RUN_SPAWN:`
    with the resolved learn command + base window name, touching **no tmux** —
    asserted to succeed even when `%5` does not exist (proves command-resolution is
    independent of live session targeting).
  - `unique_window_name()` returns `agent-learn` / `agent-learn-2` / `agent-learn-3`
    for an accumulating `existing` set (pure, no tmux) — the multi-launcher
    uniqueness contract.
- `bash tests/test_shadow_spawn_config.sh` and `bash tests/test_codeagent.sh` still
  pass (no regression to the `shadow` op / resolution chain).
- `bash tests/test_no_raw_tmux.sh` passes (the launcher reuses `launch_in_tmux`;
  the new `pane_session` gateway call lives in the launcher module, not the script).
- `shellcheck .aitask-scripts/aitask_codeagent.sh` and
  `python3 -m py_compile .aitask-scripts/aitask_shadow_spawn_learner.py .aitask-scripts/lib/agent_launch_utils.py`.
- `./.aitask-scripts/aitask_skill_verify.sh` passes (shadow SKILL.md + new
  sub-procedure are static markdown).
- Manual (live, deferred to MV follow-up): from a running shadow, ask it to learn a
  skill → a new `agent-learn-*` window opens running `/aitask-learn-skill <followed
  pane>`; the shadow stays responsive; the followed pane is never written to;
  launching a second learner produces a distinct `agent-learn-2` window.

## Post-implementation

Follow shared workflow **Step 8** (review/commit) and **Step 9** (post-implementation:
gate verification, child-plan completeness, archival, merge). The task is risk-gated
(`risk_evaluated`) — the gate is recorded post-approval (Step 7) and verified at Step 9.

## Final Implementation Notes

- **Actual work done:** Added a `learn` operation to `aitask_codeagent.sh`
  (claudecode / codex / opencode argv → `/aitask-learn-skill <pane>`, plus the
  `show_help` line); added `learn` to the relaxed set in `codex_plan_policy.sh`;
  added explicit `"learn": "claudecode/opus4_8"` defaults to
  `aitasks/metadata/codeagent_config.json` and `seed/codeagent_config.json`; added
  two reusable helpers to `lib/agent_launch_utils.py` — `pane_session()` (gateway
  lookup of a pane's session) and the pure `unique_window_name()` (counter-suffix,
  mirrors tui_switcher's `agent-explore-{n}` loop); created the executable launcher
  `aitask_shadow_spawn_learner.py` that reuses `resolve_dry_run_command` +
  `TmuxLaunchConfig(new_window=True)` + `launch_in_tmux` + `resolve_pane_id_by_pid`;
  created the shadow sub-procedure `aitask-shadow/spawn-learn-skill.md` and a Step 3
  routing entry in `aitask-shadow/SKILL.md` (greeting auto-derives). New test
  `tests/test_shadow_spawn_learner.sh` (20 assertions): per-agent `learn` dry-run
  resolution, explicit-default resolution, op support, codex relaxed-mode, the
  launcher `--dry-run` (no live tmux — passes even when the pane does not exist),
  and the pure `unique_window_name()`.
- **Deviations from plan:** none. Implemented the post-review-revised plan as
  written (Python shim reusing `launch_in_tmux`; `--dry-run` command-resolution
  seam independent of live tmux; counter-based unique window naming; explicit
  `learn` config defaults).
- **Issues encountered:** A concurrent **t1093** session ran `./ait git add
  aitasks/` mid-implementation and swept my uncommitted
  `aitasks/metadata/codeagent_config.json` edit into its commit `3e316526a`
  ("Declare gates + risk fields for t1093 from profile"). The `learn` default still
  landed in the data branch (verified present in HEAD) — just under another
  session's commit message. Documented shared-data-branch concurrent-writer
  behavior; reconciliation left to the syncer. No data lost. Only the eight
  main-branch code files were committed by this task, staged by explicit path.
- **Key decisions:** (1) Reuse the centralized `launch_in_tmux()` via a Python shim
  rather than a bash `ait_tmux new-window`, so the change does not fork the launcher
  contract (cwd / targeting / pane-pid). (2) Learner = **first-class, user-managed
  agent** — `agent-learn-*` window (visible in `ait monitor`), NO
  `@aitask_shadow_target` classifier, NO pane-died cleanup hook. (3) `--dry-run`
  proves command resolution with zero tmux access; live session targeting is
  exercised only by the deferred MV.
- **Upstream defects identified:** `tests/test_shadow_spawn_config.sh:31-33 — stale
  default-agent assertion: the test asserts `defaults.shadow → claudecode` ("default
  shadow resolves to claude"), but the project
  `aitasks/metadata/codeagent_config.json` sets `shadow: codex/gpt5_5`, so 2
  assertions fail. Pre-existing (predates this task; this change does not touch the
  shadow default) and out of scope here — the fix (update the test's default-agent
  expectation, or pin the test to an explicit `--agent-string`) belongs in its own
  task.
- **Notes for sibling tasks:** t1071_7 (website docs) should document the
  shadow→learner spawn: the `aitask_shadow_spawn_learner.py` launcher, the
  `spawn-learn-skill.md` routing, and the `agent-learn-*` first-class-agent
  lifecycle (visible in monitor, user-closed). The live shadow→learner spawn is
  runtime-behavioral and was NOT executed here (static checks only: `--dry-run` +
  pure unit tests + `test_no_raw_tmux`); it is queued as a manual-verification
  follow-up at Step 8c.
