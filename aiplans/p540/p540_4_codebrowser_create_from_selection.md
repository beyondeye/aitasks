---
Task: t540_4_codebrowser_create_from_selection.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: (no archived parent plan)
Sibling Tasks: aitasks/t540/t540_5_*.md, aitasks/t540/t540_7_*.md
Archived Sibling Plans: aiplans/archived/p540/p540_1_*.md, aiplans/archived/p540/p540_2_*.md, aiplans/archived/p540/p540_3_*.md, aiplans/archived/p540/p540_6_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_4: codebrowser "create task from selection" (verified)

## Context

`ait codebrowser` already lets users view files, jump to lines, and launch the `explain` code-agent skill against a selection. What it cannot do is the inverse: create a fresh aitask whose `file_references` frontmatter already points at the currently focused file and line range. Today you have to memorize the path, remember the line numbers, run `ait create` in a separate terminal, and type the `--file-ref` by hand — exactly the tedium the t540 parent task set out to fix.

This child wires `n` ("new task" — the same shortcut the board uses at `aitask_board.py:2938` and the TUI switcher modal uses at `tui_switcher.py:242`) in the codebrowser to spawn `aitask_create.sh` (interactive) with `--file-ref <relpath>[:RANGE]` pre-seeded, so the user lands in the normal create flow and only has to supply the semantic task fields (description, priority, labels, …). It is the primary user-facing feature of t540.

**Dependency status (all landed on main):**
- t540_1 — `--file-ref` flag + `file_references` frontmatter + `get_file_references` helper.
- t540_2 — `_current_file_path`, `_project_root`, `_tmux_session`, `_open_file_by_path`, `action_refresh_explain` all already exist in `CodeBrowserApp` and are fully wired.
- t540_3 — `--auto-merge` flag on `aitask_create.sh`. Not used directly by this task, but the launched interactive flow still writes `file_references`, so auto-merge can be composed later by the user.
- t540_6 — label reuse. Not relevant here.

Not a dependency: t540_2's `launch_or_focus_codebrowser` helper is for *navigating into* the codebrowser, not for launching `aitask_create.sh`, and is NOT used here.

## Verification vs. the initial plan

The original plan in `aiplans/p540/p540_4_codebrowser_create_from_selection.md` was high-level. Verification against main surfaced three concrete points that must be corrected and one that simplifies the work substantially.

1. **Line numbers drifted** (t540_2 added ~200 lines to `codebrowser_app.py`):
   - `CodeBrowserApp.BINDINGS` is at `codebrowser_app.py:152-165`, not 130-143. Insert the new binding after `H` at line 164.
   - `code_viewer.get_selected_range()` is still at `code_viewer.py:394-399`, 1-indexed inclusive — unchanged.
   - Board `action_create_task` is still at `aitask_board.py:3722-3741` — unchanged.

2. **No launcher hoisting needed.** The initial plan proposed extracting the board's subprocess-launch helper to `lib/agent_launch_utils.py`. It is already done: `AgentCommandScreen` lives at `.aitask-scripts/lib/agent_command_screen.py` and both `aitask_board.py` and `codebrowser_app.py` already import it (`codebrowser_app.py:28`). `launch_in_tmux` + `find_terminal` + `maybe_spawn_minimonitor` + `resolve_dry_run_command` are all already exposed from `lib/agent_launch_utils.py` (`codebrowser_app.py:29`). Implementation step 1 from the initial plan collapses to a no-op.

3. **The exact template to mirror is `action_launch_agent`, not the board.** `codebrowser_app.py:967-1016` is 100% the pattern we need — it already reads `_current_file_path`, queries `CodeViewer#code_viewer`, calls `get_selected_range()`, composes a `path[:start-end]` arg, builds an `AgentCommandScreen`, wires a tmux/terminal callback, and provides a `_run_agent_command` worker for the direct-terminal path. The new action is a near-clone of this method with a different `full_cmd` and callback.

4. **Interactive `aitask_create.sh` currently ignores `--file-ref`.** `BATCH_FILE_REFS` is populated in `parse_args` regardless of mode, but `get_task_definition()` initializes `all_file_refs=()` on entry (line 1075) and never reads `BATCH_FILE_REFS`. So launching `./.aitask-scripts/aitask_create.sh --file-ref foo.py:10-20` today drops the ref silently. The cleanest fix (1–2 lines) is to seed `all_file_refs` from `BATCH_FILE_REFS` at the top of `get_task_definition`. This is a prerequisite for t540_4 to actually deliver the feature.

## Design

### Codebrowser side

Add **one binding** and **one action** on `CodeBrowserApp`. No new helpers, no state, no imports (everything needed is already imported at lines 22–29).

**Binding** (insert between the `H` binding and the closing `]` at `codebrowser_app.py:164`). `n` is currently free in `CodeBrowserApp.BINDINGS` and is NOT shadowed by `TuiSwitcherMixin.SWITCHER_BINDINGS` (which only contains `j` — verified at `tui_switcher.py:471-473`). This matches the cross-TUI convention: the board binds `n` to `action_create_task` at `aitask_board.py:2938` and the TUI switcher modal binds `n` to `shortcut_create` at `tui_switcher.py:242`.
```python
Binding("n", "create_task", "New task"),
```

**Action** — append new method at the bottom of the class, right before `main()` at line 1032 (i.e., immediately after `_run_agent_command` finishes at line 1029). The method is a lightly-adapted clone of `action_launch_agent`:

```python
def action_create_task(self) -> None:
    """Launch aitask_create.sh with --file-ref pre-populated from the current file and selection."""
    if not self._current_file_path:
        self.notify("No file selected", severity="warning")
        return
    if not self._project_root:
        self.notify("Project root not resolved", severity="warning")
        return

    rel_path = self._current_file_path.relative_to(self._project_root)
    code_viewer = self.query_one("#code_viewer", CodeViewer)
    selected = code_viewer.get_selected_range()

    if selected and selected[0] != selected[1]:
        ref_arg = f"{rel_path}:{selected[0]}-{selected[1]}"
        title = f"Create task — {rel_path} (lines {selected[0]}-{selected[1]})"
    elif selected:
        # Single-line selection collapses to `path:N`.
        ref_arg = f"{rel_path}:{selected[0]}"
        title = f"Create task — {rel_path} (line {selected[0]})"
    else:
        # No selection: fall back to the cursor line (1-indexed from 0-indexed store).
        line_1indexed = code_viewer._cursor_line + 1
        ref_arg = f"{rel_path}:{line_1indexed}"
        title = f"Create task — {rel_path} (line {line_1indexed})"

    create_script = str(self._project_root / ".aitask-scripts" / "aitask_create.sh")
    full_cmd = f"{create_script} --file-ref {shlex.quote(ref_arg)}"
    prompt_str = f"ait create --file-ref {ref_arg}"

    window_name = f"create-{rel_path.name}"

    screen = AgentCommandScreen(
        title, full_cmd, prompt_str,
        default_window_name=window_name,
    )

    def on_result(result):
        if result == "run":
            self._run_create_from_selection(ref_arg)
        elif isinstance(result, TmuxLaunchConfig):
            _, err = launch_in_tmux(screen.full_command, result)
            if err:
                self.notify(err, severity="error")

    self.push_screen(screen, on_result)
```

`shlex` is **not** currently imported in `codebrowser_app.py` (stdlib imports at lines 19-25 are `asyncio os shutil subprocess sys time pathlib`). Add `import shlex` alongside them.

**Direct-terminal worker** — append after `action_create_task`:

```python
@work(exclusive=True)
async def _run_create_from_selection(self, ref_arg: str) -> None:
    """Launch aitask_create.sh in a terminal (or via suspend), then refresh annotations."""
    create_script = str(self._project_root / ".aitask-scripts" / "aitask_create.sh")
    terminal = _find_terminal()
    if terminal:
        subprocess.Popen(
            [terminal, "--", create_script, "--file-ref", ref_arg],
            cwd=str(self._project_root),
        )
        # Popen doesn't wait — no automatic refresh on this path. User
        # presses `r` when the new task is committed.
    else:
        with self.suspend():
            subprocess.call(
                [create_script, "--file-ref", ref_arg],
                cwd=str(self._project_root),
            )
        # We know the subprocess has returned; refresh annotations so the
        # newly-created task's gutter entry shows up immediately.
        self.action_refresh_explain()
```

**Why no post-refresh on the tmux / terminal-Popen paths?** Both fire subprocesses that run concurrently with the TUI, so calling `action_refresh_explain()` right after `launch_in_tmux` / `Popen` would refresh *before* the task is created and commit the refresh to stale data. Matching the current `action_launch_agent` behavior (no auto-refresh) keeps the code simple; the user presses `r` when done. The one path where we *can* cleanly refresh is the suspend path (no terminal available), and we do.

### aitask_create.sh side — seed interactive from `BATCH_FILE_REFS`

`get_task_definition()` at `aitask_create.sh:1067-1166` is the interactive collector. Change line 1075 from:
```bash
local -a all_file_refs=()
```
to:
```bash
local -a all_file_refs=()
if [[ ${#BATCH_FILE_REFS[@]} -gt 0 ]]; then
    all_file_refs=("${BATCH_FILE_REFS[@]}")
    info "Pre-populated file references: ${all_file_refs[*]}" >&2
fi
```

That's the whole change on the create side. Why it's enough:

- The existing marker-based emit loop at lines 1158-1165 iterates `all_file_refs[@]` and prints each entry after the `__FILE_REFS_MARKER__` line. The outer `run_draft_interactive` at line 1755 already dedup's and forwards them to `create_draft_file` via the `deduped_file_refs` positional arg.
- `create_draft_file` + `finalize_draft` already emit `file_references:` frontmatter from that positional arg (t540_1 landed this).
- `BATCH_FILE_REFS` is populated by `parse_args` at line 146 regardless of whether `--batch` is set, so the seed works transparently for both batch and interactive modes.
- The `${#BATCH_FILE_REFS[@]} -gt 0` guard avoids a `set -u` edge case if someone's environment misbehaves, and only prints the info banner when there is something to announce.

One interaction worth noting: the interactive flow's "Remove file reference" option only surfaces entries in `current_round_refs` (session-round-scoped local array), not `all_file_refs`. So pre-seeded entries cannot be removed via the UI. That is acceptable — the codebrowser-initiated flow commits the user to the selected range; if they change their mind they cancel (`ESC` on the AgentCommandScreen) before the create flow even starts.

### Why NOT write a new helper in `agent_launch_utils.py`

The plan's original step 1 proposed hoisting the board's launcher. It's already hoisted. The extant codebrowser already has `AgentCommandScreen` + `launch_in_tmux` + `_find_terminal` imported, and `action_launch_agent` demonstrates the exact pattern. A new helper would be one wrapper around three already-shared calls, and would need a module to live in (board or codebrowser or lib). Direct use keeps symmetry with `action_launch_agent` and avoids ceremony.

## Key files to modify

1. **`.aitask-scripts/codebrowser/codebrowser_app.py`**
   - Line 164 area: add `Binding("n", "create_task", "New task"),` to the `BINDINGS` list.
   - After the existing `_run_agent_command` worker (line 1029): append `action_create_task` and `_run_create_from_selection` as shown in the Design section.
   - Stdlib imports at lines 19-25: add `import shlex` (verified absent on verification read).

2. **`.aitask-scripts/aitask_create.sh`**
   - Line 1075: extend the local `all_file_refs=()` init to seed from `BATCH_FILE_REFS` (see Design section snippet). No other lines change.

3. **`tests/test_file_references.sh`** (extend)
   - Add one case that exercises the new interactive-seed path via a scripted interactive run. The simplest form: run `aitask_create.sh` in a subshell with a here-string feeding the minimum number of prompts (description, "Done with files", "Done - create task", priority, effort, issue type, status, labels "Done adding labels", no deps, a task name, "Finalize now"), with `--file-ref foo.py:10-20` on the command line. Assert that the finalized task file contains `file_references: [foo.py:10-20]`.
   - Rationale for piggy-backing on the existing test rather than a new file: the harness bootstrap is expensive, and `test_file_references.sh` already covers every other aspect of this field. The interactive seed is a single additional assertion.
   - If piloting the interactive path via here-strings proves too fragile (fzf requires a TTY), fall back to a direct unit-style harness that sources `aitask_create.sh` just to call `get_task_definition` with `BATCH_FILE_REFS=(foo.py:10-20)` pre-set, capture its stdout, and assert the marker section contains the expected line. That validates the seed mechanics without depending on fzf.

4. No new test for the codebrowser binding itself. The codebrowser TUI doesn't have an existing python test harness (Textual's snapshot testing isn't set up in this repo), so verification is manual smoke test. This matches how t540_2's focus mechanism was verified.

## Reference files for patterns

- `.aitask-scripts/codebrowser/codebrowser_app.py:967-1029` — `action_launch_agent` + `_run_agent_command`. Primary template. The new methods differ only in: (a) full_cmd string, (b) the callback's "run" branch calls `_run_create_from_selection`, and (c) single-line fallback uses the cursor when there's no selection (explain omits the fallback and passes path-only).
- `.aitask-scripts/board/aitask_board.py:3722-3753` — `action_create_task` + `_run_create_in_terminal`. Alternative template. Similar shape but doesn't pre-seed a file ref and uses a simpler title.
- `.aitask-scripts/aitask_create.sh:1067-1166` — `get_task_definition`. Only one-line change site.
- `.aitask-scripts/aitask_create.sh:1720-1768` — `run_draft_interactive`. Read-only reference; no change.
- `aiplans/archived/p540/p540_2_codebrowser_focus_mechanism.md:370-464` — t540_2 Final Implementation Notes. Documents `_current_file_path`, `_project_root`, and selection-state mutation — all already in place for this task.
- `aiplans/archived/p540/p540_1_foundation_file_references_field.md:150-191` — t540_1 Final Implementation Notes. The locked-in `file_references` entry format we must emit.

## Implementation sequence

1. **Add `import shlex`** to `codebrowser_app.py` stdlib imports (verified absent at lines 19-25).
2. **`aitask_create.sh`** seed: change line 1075 to the 4-line seeded version. `bash -n` sanity check; `shellcheck` clean.
3. **`codebrowser_app.py`** — add the `n` binding to `BINDINGS`; append `action_create_task` + `_run_create_from_selection`. Python syntax check with `python -c "import ast; ast.parse(open('.aitask-scripts/codebrowser/codebrowser_app.py').read())"`.
4. **Extend `tests/test_file_references.sh`** with the interactive-seed case (preferred: unit-style sourcing of `get_task_definition` — see Key files §3).
5. **Run tests:** `bash tests/test_file_references.sh` (all cases including new one). `bash tests/test_verified_update_flags.sh` (no regression on the nearest neighbor). `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/lib/task_utils.sh`.
6. **Manual smoke test** — Verification section below.

## Verification

- **Syntax checks:**
  - `bash -n .aitask-scripts/aitask_create.sh`
  - `python -c "import ast; ast.parse(open('.aitask-scripts/codebrowser/codebrowser_app.py').read())"`
  - `shellcheck .aitask-scripts/aitask_create.sh` — no new warnings.
- **Automated:**
  - `bash tests/test_file_references.sh` — all cases PASS, including the new interactive-seed case.
- **Manual smoke test — core flow:**
  1. `./ait codebrowser` — TUI opens normally, no regression.
  2. Navigate to a file with `tab` / arrow keys / `/`, scroll to a region, press shift+down several times to select lines e.g. 10-20.
  3. Press `n`. `AgentCommandScreen` opens with title `Create task — <relpath> (lines 10-20)` and full command `./.aitask-scripts/aitask_create.sh --file-ref '<relpath>:10-20'`.
  4. Choose the **Direct / Run in terminal** option (or the tmux option on a tmux setup).
  5. `aitask_create.sh` launches interactively. Near the top it prints `Pre-populated file references: <relpath>:10-20`.
  6. Walk through the flow: description, skip file refs, labels, priority, effort, issue type, status, task name, Finalize.
  7. Inspect the newly created task file. Frontmatter must contain `file_references: [<relpath>:10-20]`.
- **Manual smoke test — single-line fallback:**
  1. In the codebrowser, move the cursor to a line *without* selecting a range, then press `n`.
  2. The screen title shows `line N`, the command contains `--file-ref '<relpath>:N'` (single line).
  3. The finalized task has `file_references: [<relpath>:N]`.
- **Manual smoke test — 1-line selection vs point cursor equivalence:**
  - Selecting exactly one line (start == end) is treated as the single-line case (`path:N`, not `path:N-N`). Verify this in the screen title and the resulting frontmatter.
- **Regression checks for existing `BINDINGS`:** `q tab g e r t d D h H escape` all still work; the only addition is `n`. Also check the focus mechanism from t540_2 still works (`--focus path:10-20` CLI + tmux env var).
- **Interactive seed without the codebrowser:** run `./.aitask-scripts/aitask_create.sh --file-ref foo.py:5-7` from a bare shell. The pre-populated banner prints, the flow continues normally, the finalized task has `file_references: [foo.py:5-7]`. This proves the seed works independently of the codebrowser.

## Out of scope

- **Post-subprocess annotation refresh on async paths** (tmux and terminal-Popen). Only the suspend path gets automatic `action_refresh_explain()`; for tmux/Popen the user presses `r`. A follow-up task could add a polling mechanism similar to `_consume_and_apply_focus` if this becomes friction.
- **Auto-merge prompt inside the codebrowser.** `aitask_create.sh --auto-merge` exists (t540_3) but must be passed on the command line. This task does NOT add an "auto-merge existing matches" confirmation in the codebrowser itself — the user can edit the command string on the AgentCommandScreen to add `--auto-merge` if they want.
- **Field drift across frontmatter writers / board widget.** That is t540_5 / t540_7. This task only emits `file_references` via the existing t540_1 machinery.
- **Codebrowser `n` behavior while a modal is already open.** There's no explicit guard; if the user presses `n` with e.g. the go-to-line modal open, Textual will queue or drop the action — matching how `action_launch_agent` handles it. Out of scope to tighten.
- **Seeding `current_round_refs`** so the interactive "Remove file reference" menu can delete the pre-seeded entry. Pragmatically the codebrowser flow commits the user to the range; if they change their mind they cancel before the create flow starts. Not worth the complexity.

## Post-implementation (Step 9 reference)

Run `./.aitask-scripts/aitask_archive.sh 540_4` per task-workflow Step 9. The archived plan file will serve as primary reference for t540_5 (board field widget), which may want to mirror the "launch a helper command with a file ref pre-seeded" pattern.

## Implementation Notes template (fill in during Step 8)

- **Actual work done:** …
- **Deviations from plan:** …
- **Issues encountered:** …
- **Key decisions:** …
- **Notes for sibling tasks:** …
