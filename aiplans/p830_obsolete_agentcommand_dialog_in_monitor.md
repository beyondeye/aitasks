---
Task: t830_obsolete_agentcommand_dialog_in_monitor.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Plan: Propagate per-run profile edit to all skill-launching TUIs (t830)

## Context

Task t777_17 added a Profile row + (E)dit button to `AgentCommandScreen`
(`.aitask-scripts/lib/agent_command_screen.py`). The feature is gated by
`if self.skill_name:` — the Profile row renders only when both
`skill_name` and `default_profile` are passed to the constructor.

The feature was wired up only in `ait board`'s two pick call sites. Every
other call site that launches a profile-aware Claude skill still omits
those constructor params, so the user cannot edit the per-run profile
when launching from those TUIs. The task description specifically calls
out:
- `ait monitor` "n" shortcut (pick next sibling)
- `codebrowser` explain

There is no duplicated dialog code — the class is already shared. The
bug is purely missing arguments at the call sites.

## Scope: which call sites need the fix

Audited call sites of `AgentCommandScreen(...)`:

| File:Line | Operation | Profile-aware skill? | Action |
|-----------|-----------|----------------------|--------|
| `board/aitask_board.py:3900` | pick | yes | already done (t777_17) |
| `board/aitask_board.py:4003` | pick | yes | already done (t777_17) |
| `board/aitask_board.py:4046` | brainstorm | no (TUI launcher, not a rendered skill) | skip |
| `board/aitask_board.py:4204` | create | no (uses `aitask_create.sh` directly) | skip |
| `monitor/monitor_app.py:1706` | pick | yes | **FIX** |
| `monitor/monitor_app.py:1784` | pick (restart) | yes | **FIX** |
| `codebrowser/codebrowser_app.py:1385` | explain | yes (`aitask-explain` skill) | **FIX** |
| `codebrowser/codebrowser_app.py:1457` | create | no (uses `aitask_create.sh` directly) | skip |
| `codebrowser/history_screen.py:391` | qa | yes (`aitask-qa` skill) | **FIX** |
| `syncer/syncer_app.py:490` | raw | no (raw prompt, no skill rendering) | skip |

Four call sites to fix. Skipped ones do not invoke profile-rendered
skills — `aitask_create.sh` is a bash entry point, brainstorm is its own
TUI, and `raw` is a free-form prompt.

## Design

### Step 1 — Extract shared profile resolver

Today `aitask_board.py:4162` defines `_resolve_pick_profile()` as a
hardcoded-to-"pick" subprocess wrapper around
`./.aitask-scripts/aitask_skill_resolve_profile.sh`. Promote it to a
module-level helper in the shared lib so every TUI uses the same logic
(timeout, "default" fallback, error handling).

**New helper:** `.aitask-scripts/lib/agent_command_screen.py` — add at
module scope, near the top, after imports:

```python
def resolve_skill_profile(
    skill_name: str,
    project_root: Path | str = ".",
) -> str:
    """Resolve the active profile name for a given skill.

    Returns the profile name (e.g., "fast") on success, or "default"
    on any error (missing script, timeout, non-zero exit). The default
    ensures the launch dialog still opens — the Profile row will just
    show "default".
    """
    script = Path(project_root) / ".aitask-scripts" / "aitask_skill_resolve_profile.sh"
    try:
        result = subprocess.run(
            [str(script), skill_name],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip() or "default"
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        pass
    return "default"
```

Place it alongside `AgentCommandScreen` so every caller that already
imports `from agent_command_screen import AgentCommandScreen` can do
`from agent_command_screen import AgentCommandScreen, resolve_skill_profile`.

Imports needed inside `agent_command_screen.py`: `import subprocess`
and `from pathlib import Path` — both are likely already imported
(verify during implementation, add if missing).

### Step 2 — Update `aitask_board.py` to use the shared helper

Replace `_resolve_pick_profile` body (line 4162) with a single
delegation call, so the public method survives but the logic lives in
the lib:

```python
def _resolve_pick_profile(self) -> str:
    return resolve_skill_profile("pick")
```

Add `resolve_skill_profile` to the existing `from agent_command_screen
import AgentCommandScreen` line. No behaviour change — this is just
unifying the source of truth.

### Step 3 — Fix the 4 missing call sites

Append two arguments to each of the four `AgentCommandScreen(...)`
constructor calls:

```python
skill_name="<op>",
default_profile=resolve_skill_profile("<op>", target_root),
```

Use the call-site's existing project-root variable (`target_root` in
monitor, `self._project_root` in codebrowser) so the helper looks up the
right `aitask_skill_resolve_profile.sh`.

Per-file changes:

- `.aitask-scripts/monitor/monitor_app.py`
  - Add `resolve_skill_profile` to the existing import on line 44.
  - Line 1706 (`action_pick_next_sibling` callback): add
    `skill_name="pick"`, `default_profile=resolve_skill_profile("pick", target_root)`.
  - Line 1784 (`_on_restart_confirmed`): same two args, using `target_root`.

- `.aitask-scripts/codebrowser/codebrowser_app.py`
  - Add `resolve_skill_profile` to the existing import on line 31.
  - Line 1385 (`action_explain` callback): add
    `skill_name="explain"`, `default_profile=resolve_skill_profile("explain", self._project_root)`.

- `.aitask-scripts/codebrowser/history_screen.py`
  - Add `resolve_skill_profile` to the existing import on line 11.
  - Line 391 (QA launch): add
    `skill_name="qa"`, `default_profile=resolve_skill_profile("qa", self._project_root)`.

Skill-name strings match what `AgentCommandScreen` already expects
internally — they are the names accepted by
`aitask_skill_resolve_profile.sh` (the script that lives at
`.aitask-scripts/aitask_skill_resolve_profile.sh` and reads
`.aitask-scripts/aitask_skill_render.sh`).

## Critical files to modify

1. `.aitask-scripts/lib/agent_command_screen.py` — add `resolve_skill_profile()` helper.
2. `.aitask-scripts/board/aitask_board.py` — delegate `_resolve_pick_profile` to the new helper; update import.
3. `.aitask-scripts/monitor/monitor_app.py` — 2 call-site fixes + import.
4. `.aitask-scripts/codebrowser/codebrowser_app.py` — 1 call-site fix + import.
5. `.aitask-scripts/codebrowser/history_screen.py` — 1 call-site fix + import.

## Out of scope

- **`brainstorm` / `create` / `raw`**: these launch non-skill flows
  (TUIs, bash scripts, free-form prompts). They do not have rendered
  profile variants and so do not benefit from per-run profile editing.
  If desired later, they would each need their own design (probably a
  separate task) since the override path is skill-specific.
- **Refactoring the broader AgentCommandScreen API**: no signature
  changes; only adding two existing optional kwargs at call sites.

## Verification

1. **Targeted shellcheck/lint:** `python -m py_compile` on each
   modified `.py` file.
2. **`ait board` regression:** launch `ait board`, pick a task with
   the `p` (pick) shortcut, confirm the Profile row still appears with
   the resolved profile name and the (E)dit button works (no
   regression from the helper-extraction refactor).
3. **`ait monitor` — primary user-reported case:** launch `ait
   monitor`, focus an agent pane, press `n`, select a sibling task in
   the NextSiblingDialog, confirm the AgentCommandScreen now shows the
   Profile row with the resolved profile, and that pressing `e` opens
   the ProfileEditScreen sub-modal. Save a modified profile and verify
   `full_command` updates to include `--profile-override <path>`.
4. **`ait monitor` restart path:** focus an idle agent pane, press
   `r` (restart), confirm AgentCommandScreen now shows Profile row.
5. **`ait codebrowser` explain:** open codebrowser, navigate to a
   file, press the explain shortcut, confirm Profile row shows. Save
   a modified profile and verify command updates.
6. **`ait codebrowser` QA from history screen:** trigger the QA
   action, confirm Profile row shows.
7. **No-regression spot-check** on call sites that we intentionally
   did NOT change (board brainstorm, board create, codebrowser create,
   syncer raw): the Profile row should NOT appear — these launch
   non-skill flows.

## Step 9 — Post-Implementation

Follow the shared task-workflow Step 9 (commit, push, archive). No
worktree to clean up because profile 'fast' is working on `main`
directly. Verify build (if configured in `project_config.yaml`) runs
clean.
