---
Task: t2073_5_scratchpad_docs.md
Parent Task: aitasks/t2073_minimonitor_scratchpad_pane.md
Sibling Tasks: aitasks/t2073/t2073_1_scratchpad_store_and_archival.md, aitasks/t2073/t2073_2_scratchpad_app.md, aitasks/t2073/t2073_3_bound_helper_pane_rule.md, aitasks/t2073/t2073_4_minimonitor_scratchpad_key.md
Archived Sibling Plans: aiplans/archived/p2073/p2073_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-21 11:28
---

# t2073_5 — scratchpad_docs (verified plan)

## Context

t2073_1–4 have landed: the store helper, the `ait scratchpad` app, the bound-helper rule
and minimonitor `o`. t2088 (4da69fcfb) has also landed, so a pad now closes when its agent
is killed directly or its frozen record is dropped. This task writes the user-facing
website docs. Per `aidocs/framework/documentation_conventions.md` they describe the
current state only, use `{{< relref >}}` for internal links, and must pass
`check_links.py --build`. Full parent design: `aiplans/p2073_minimonitor_scratchpad_pane.md`.

The working tree was clean at planning time, and no other in-flight task edits these
pages. The work is docs only, on the current branch (profile `fast`).

## Facts verified against landed code (the source for every claim)

- **Open:** minimonitor `o` (binding label "Notes"). The `o:notes` hint goes on the
  `e/E:shadow` line (`minimonitor_app.py:1231`, `action_open_scratchpad` :3950).
  - It opens a vertical split of the **followed agent's** pane, in the agent's window,
    with that window selected.
  - With no followed agent the notification is "No followed agent for a scratchpad".
- **Task vs unsaved:** a window named `agent-(pick|qa|resume)-<id>`
  (`task_id_from_window_name`, `monitor_core.py:4514`) gets the task's persistent pad.
  Any other agent gets an unsaved pad, with the warning "Not a task agent — notes will
  not be saved". Success toasts: "Opened scratchpad for t<id>" or "Opened scratchpad
  (not saved)".
- **Duplicates:** one pad per task store **or** per agent pane. A second press gives
  "A scratchpad is already open for t<id>" (or "for this agent"). An unverifiable tmux
  query refuses with "Could not verify whether a scratchpad is already open — not
  opening". The backstop is a second editor on the same store (for example from a manual
  `ait scratchpad --task`), which opens read-only (`read-only: open elsewhere`), never
  saves and never promotes itself.
  - `match_scratchpad_pane` (`monitor_core.py`) matches on the stamped store key or
    target only, never on writability. A read-only pad opened by `o` therefore keeps
    blocking `o` after the writer closes, and a manual (unstamped) editor is invisible
    to the check.
  - In read-only mode `action_flush_quit` exits immediately
    (`scratchpad_app.py:486`).
  - An orphaned in-flight save keeps the flock until its write lands, so a reopen
    before then is read-only again.
- **Placement config** (`scratchpad_placement`, `monitor_core.py:4283`):
  - `tmux.scratchpad_position` is `top` or `bottom` (default `bottom`).
  - `tmux.scratchpad_height` is a whole number of rows >= 1 (default `12`).
  - An invalid value of either falls back to its default.
  - Both are editable in `ait settings` → Tmux tab (`settings_app.py:354-370`) and
    documented in `seed/project_config.yaml`.
- **Keys** (`scratchpad_app.py:295`, plus Textual `TextArea` defaults; probed):
  - `ctrl+s` saves now. `ctrl+q` makes one final save attempt and exits (the command
    palette Quit does the same).
  - `ctrl+c` copies the selection, or the whole buffer when nothing is selected. It uses
    OSC 52 and, inside tmux, the tmux paste buffer (`tui_clipboard.copy_to_system_clipboard`).
  - `ctrl+x` cuts (the line when nothing is selected) and goes to the same clipboard.
  - `ctrl+z` / `ctrl+y` are undo / redo.
  - `ctrl+v` pastes what was last copied or cut **in this pad** (Textual's
    `app.clipboard`). To paste from the system clipboard, use the terminal's own paste
    (bracketed paste) or the tmux paste buffer.
  - Every letter key types. There is no `?` editor binding in this app. The keys are
    rebindable from Settings → Shortcuts, scope `scratchpad` (`shortcut_scopes.py:61`);
    this is checked at implementation time (see Step 1).
- **Header:** `t<id> · <state> · → <pane>`, or `scratch · …` for an unsaved pad. The
  states are `ST_*`, verbatim (`scratchpad_app.py:96-108`): opening…, saved, saving…,
  unsaved changes, NOT SAVED (no task), read-only: open elsewhere, not saved — task
  archived, not saved — no active task, not saved — store unavailable, save failed —
  retrying in {n}s, save stuck — waiting for the previous write to finish, saving before
  quit…, autosave stopped — error.
- **Autosave** (module docstring, quoted verbatim per the t2073_2 notes and the t2073_1
  inbox note):
  - A save is due at `min(last change + 1 s, first unsaved change + 3 s)`. Saves are
    serialized, and a failed save retries after 2 s.
  - SIGHUP (for example from a `kill-pane`) triggers a detached, best-effort flush.
  - Loss contract: "On a hard kill, changes not included in the latest successfully
    saved buffer may be lost, including edits queued during a pending save. Autosave
    targets starting within roughly three seconds when no save is pending; this is not a
    maximum loss window."
- **Storage:** `.aitask-scratchpad/<id>/notes.md` under the project root. It is
  gitignored (`ait setup` adds `.aitask-scratchpad/`), and `AITASK_SCRATCHPAD_DIR`
  overrides the root.
- **Persistence:** the store is keyed by task id, not by agent. Killing or freezing the
  agent and later re-picking (`agent-pick-<id>`), QA-ing or resuming the task, then
  pressing `o`, reopens the same notes.
- **Archival:** `aitask_archive.sh` `prune_scratchpad` deletes the store when the task
  is archived. This covers parent, child and auto-archived parent, and also folded tasks
  merged into it. A pad still open on an archived task shows "not saved — task archived".
  A task with no active task file shows "not saved — no active task".
- **Lifecycle:**
  - The pad never appears in monitor or minimonitor agent lists.
  - It closes when its agent pane exits (the `pane-died` cleanup hook), and also when the
    agent is killed directly with monitor/minimonitor `k` or its frozen record is
    dropped (t2088).
  - It stays open across freeze and restore, because the pane id survives
    `respawn-pane -k`.
  - It survives a sibling agent's death.
  - If the cleanup hook cannot be wired, the toast is "Scratchpad opened; auto-cleanup on
    agent exit could not be wired — close the scratchpad by hand when the agent exits".
- **CLI:** `ait scratchpad (--task <id> | --unsaved) [--target <pane>]`.
  - `--target` only labels the header.
  - An invalid task id prints `ait scratchpad: invalid task id: <x>` and exits 2;
    argparse usage errors also exit 2.
  - Missing Python packages makes the launcher die and tell you to run `ait setup`.
  - It is not in the TUI switcher (`tui_registry` `in_switcher=False`).

## Implementation steps

1. **Pre-write check.** Confirm the Settings → Shortcuts tab lists the `scratchpad`
   scope:
   `grep -n scratchpad .aitask-scripts/settings/*.py .aitask-scripts/lib/shortcut*.py`
   If it does not, drop the "rebindable" sentence.

2. **NEW `website/content/docs/tuis/scratchpad/_index.md`** (weight 18,
   title/linkTitle "Scratchpad", `maturity: [experimental]`,
   `depth: [main-concept]`). Model it on `tuis/frozenagent/_index.md`, with these
   sections:
   - what it is;
   - Opening (minimonitor `o`, the task pad vs the unsaved pad, a manual launch as an
     escape hatch, not in the switcher);
   - Layout (header + editor + footer; the header format);
   - Saving (autosave summary + the loss contract quoted verbatim);
   - Where notes live;
   - Lifecycle (persists per task, dropped at archival, closes with its agent, survives
     freeze/restore);
   - Next/Reference footer.

3. **NEW `tuis/scratchpad/how-to.md`** (weight 20, "How-To",
   `depth: [intermediate]`). Sections:
   - **Take notes beside an agent:** `o`, placement, how to focus the pane.
   - **Copy notes into the agent:** `ctrl+c` with no selection copies everything; paste
     with the terminal or tmux paste.
   - **Paste into the pad:** terminal paste vs `ctrl+v`.
   - **Keep notes across a re-pick:** kill/freeze, re-pick, then `o`.
   - **Use a pad for a non-task agent:** unsaved, never written.
   - **Change where the pad opens:** the two config keys, plus `ait settings` → Tmux.
   - **When the header says read-only:** another editor holds the store, usually a manual
     `ait scratchpad --task <id>`. Minimonitor's duplicate check cannot see a manual
     editor, because it carries no pane stamps. The read-only pad is a snapshot taken
     when it opened. It never saves and never becomes writable, even after the other
     editor closes. While it is open it also blocks `o`: the duplicate check matches it
     by task store and by agent, and does not ask whether it is writable, so `o` only
     reports "A scratchpad is already open for t<id>". To recover:
     1. Close the writer with `ctrl+q` and let its final save finish.
     2. Close the read-only pad with `ctrl+q`. It exits at once, since it has nothing
        to save.
     3. Reopen with `o`, or rerun the same `ait scratchpad --task <id>` command for a
        manually launched pad.

     Reopening too early, while the writer's last save is still in flight, lands in
     read-only again.

4. **NEW `tuis/scratchpad/reference.md`** (weight 30, "Reference",
   `depth: [advanced]`). Sections:
   - Keybindings table;
   - Header states table (every `ST_*`, with its meaning);
   - Command line (forms, exit codes);
   - Configuration table (two keys, defaults, fallback);
   - Storage (path, gitignore, `AITASK_SCRATCHPAD_DIR`, pruned at archival including
     folded tasks);
   - Autosave timing (1 s debounce, 3 s maximum dirty age, 2 s retry, the verbatim loss
     contract, with the 5 s store lock wait described as a lock wait only);
   - Lifecycle rules: one pad per task store or agent pane, and the notifications. The
     duplicate check sees only pads opened with `o`. A pad that is open blocks `o`
     whether or not it is writable. A read-only pad is a non-refreshing snapshot that
     never saves or promotes, and `ctrl+q` closes it at once. Also the closing and
     surviving rules;
   - See also.

5. **`tuis/minimonitor/how-to.md`.** Add a `### How to Open a Scratchpad` section
   between "How to Launch a Shadow Agent" (:179) and "How to Pick Shadow Concerns"
   (:189). Give it a short body and link to `{{< relref "/docs/tuis/scratchpad" >}}`.
   Then add the quick-reference row
   `| \`o\` | Open a scratchpad notes pane beside the followed agent |` after the `E` row
   (:447).

6. **`tuis/minimonitor/_index.md`.** After "Launching a shadow agent" (:77-83), add a
   short `## Opening a scratchpad` paragraph naming `o`, with a link. Also add
   "a scratchpad" to the companion-pane list sentence at :39.

7. **`tuis/_index.md`.** Add a **[Scratchpad](scratchpad/)** (`ait scratchpad`) bullet
   after Frozen Agent. It is opened with minimonitor `o`, persists per task and is
   experimental. The switcher paragraph needs no change: the scratchpad is not in the
   switcher, and the "Minimonitor is not listed" sentence remains accurate.

8. **`commands/_index.md`.**
   - Add the TUI table row
     `| [\`ait scratchpad\`](../tuis/scratchpad/) | Notes editor bound to a code agent pane — usually opened with minimonitor \`o\` |`
     after the frozenagent row. Match the table's existing relative-link style.
   - Add the usage line `ait scratchpad --task 42 # Open task 42's notes editor`
     after `ait monitor` (:107).

9. **`tuis/monitor/reference.md`.** Add two rows after `tmux.syncer.autostart` in the
   tmux Configuration table (~:204):
   - `tmux.scratchpad_position` | string | `bottom` | …
   - `tmux.scratchpad_height` | int | `12` | …

   Each description says that an invalid value falls back to the default, and links to
   the scratchpad reference.

10. **`tuis/frozenagent/how-to.md`.** Add a short note, under "Bring an agent back" or at
    the end: a scratchpad bound to the agent stays open across freeze and restore, and
    closes when the record is dropped.

## Verification

- `cd website && hugo build --gc --minify`
- `cd website && python3 check_links.py --build` (mandatory; must exit 0)
- Optionally run `python3 check_link_relevance.py` for the new links (a report only).
- Re-grep each verbatim string the docs quote (the ST_* states, the notification texts,
  the loss contract) against the code, so that no quote drifts.

## Step 9 (Post-Implementation)

Standard child archival via task-workflow Step 9 (current branch, no merge).

## Risk

### Code-health risk: low
None identified. Documentation only: no code or test changes, and every page edit is
additive.

### Goal-achievement risk: low
- Docs could describe planned rather than landed behaviour · severity: low ·
  → mitigation: none needed. Every claim above was re-verified against the landed code
  and t2088 during planning, the quoted strings are re-grepped at implementation, and
  `check_links.py --build` runs.

## Post-Review Changes

### Change Request 1 (2026-10-21 12:05)
- **Requested by user:** the lifecycle promises (closes with its agent, survives freeze/restore, never listed as an agent) were stated unqualified while the page also documents manual CLI launches. A manual pad carries no `@aitask_scratchpad_target` stamp (`--target` only labels the header), so it falls through the helper filter — listed as an agent inside an `agent-…` window — and gets no cleanup binding. Verified: only `monitor_core.spawn_scratchpad` stamps and calls `attach_companion_cleanup_hook`; the app spawns no tmux.
- **Changes made:** `_index.md` adds a manual-launch caveat under Opening and a lead-in limiting the three binding rules to pads opened with `o`. `reference.md` adds a "Binding comes only from o" lifecycle rule and links the `--target` sentence to it.
- **Files affected:** `website/content/docs/tuis/scratchpad/_index.md`, `website/content/docs/tuis/scratchpad/reference.md`

## Final Implementation Notes
- **Actual work done:** New `website/content/docs/tuis/scratchpad/{_index,how-to,reference}.md` (weights 18/20/30, experimental). Cross-references: minimonitor how-to ("How to Open a Scratchpad" + `o` quick-reference row), minimonitor `_index.md` ("Opening a scratchpad" + companion-pane list), `tuis/_index.md` (Available TUIs bullet), `commands/_index.md` (TUI table row + usage line), `monitor/reference.md` (two tmux config rows), `frozenagent/how-to.md` (pad stays across freeze/restore; drop closes it, notes stay until archival). `hugo build --gc --minify` and `check_links.py --build` pass.
- **Deviations from plan:**
  - The frozenagent note claims the pad persists only across a restore that reuses the pane. Whether re-pick reuses the pane was not confirmed, so the note tells the user to press `o` wherever the agent comes back.
  - Rebinding is documented for `ctrl+s`/`ctrl+q`/`ctrl+c` only. Those are in the `scratchpad` scope; `ctrl+x/z/y/v` are Textual `TextArea` bindings outside it.
  - Two overclaims in the first draft were corrected before review. The SIGHUP flush is "best-effort". The 3 s figure is when a save starts, not a maximum dirty age.
- **Issues encountered:**
  - The plan review caught a wrong read-only recovery: `match_scratchpad_pane` blocks `o` regardless of writability, and a read-only pad never promotes. It was fixed in the plan before implementation.
  - The code review caught unqualified lifecycle promises for hand-launched pads (Change Request 1).
  - t2088 landed during planning, so the known kill-pane gap is not documented.
- **Key decisions:**
  - The loss contract is quoted verbatim from the `scratchpad_app.py` module docstring.
  - Every quoted notification and state string was re-grepped against the code. `ctrl+v` is documented as an in-pad paste only (Textual `app.clipboard`), with terminal/tmux paste for the system clipboard.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - The minimonitor `_index.md` "Auto-despawn" paragraph ("exits when no pane other than itself remains") was checked and is accurate. `_check_auto_close` (`minimonitor_app.py` ~:1816) counts every pane in the window, helpers included. A bound pad is reaped separately by the companion cleanup hook.
  - The website settings reference still doesn't list `shadow_pane_width` (noted by t2073_4).
