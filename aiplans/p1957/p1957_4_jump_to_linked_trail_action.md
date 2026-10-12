---
Task: t1957_4_jump_to_linked_trail_action.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_5_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
---

Parent plan (decisions, linked-trail definition, risk record):
`aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.
The task file `aitasks/t1957/t1957_4_jump_to_linked_trail_action.md` carries the full context,
reference files and line anchors.


## t1957_4 — Jump action: pick a linked trail and switch to it

Files: `.aitask-scripts/board/board_trail_screen.py`,
`.aitask-scripts/board/board_trail_view.py` (modal),
`.aitask-scripts/board/trails_app.py`, `.aitask-scripts/board/aitask_board.py`,
`.aitask-scripts/lib/agent_launch_utils.py`, `.aitask-scripts/lib/tui_switcher.py`,
tests `tests/test_board_bytrail_view.py`, `tests/test_trails_app.py`,
`tests/test_trail_screen_host_protocol.py`.

1. Binding `Binding("L", "trail_linked", "Linked Trails")` added to
   `TRAIL_BINDINGS` (`L` is unbound on both App classes today — the board's
   `l`/`L` lock keys live on the detail *screen*; re-check at implementation). Declared on **both** hosts (same object): trails via
   `*TRAIL_BINDINGS`; board placed with `TRAIL_BINDING["trail_linked"]` among
   its rows. Implemented in the mixin, so supported on both — no capability
   entry needed. Footer only in By-Trail with an active trail (`check_action`).
2. `action_trail_linked`: captures the **origin** (`handle` of the active
   trail) and a fresh request stamp `self._trail_link_gen =
   self._bump_trail_gen()`, then starts `@work(thread=True)
   _trail_link_worker(gen, handle)` running `scan_linked_trails` (notice
   "Searching linked trails in N projects…"). Its UI-thread callback
   `_on_trail_links(gen, handle, scan)` **drops the result** unless all hold:
   `gen == self._trail_link_gen` (a newer search or a supersede bumped it),
   `self.base_filter == "bytrail"`, `self._trail_active` is not None and its
   `handle == origin`, and the origin session is still open. Invalidation
   points: a new `L` press (new gen), `_supersede_trail_workers` (leaving or
   re-entering By-Trail) resets `_trail_link_gen`, and `_switch_trail_session`
   / `_close_trail_session` / `_activate_trail` bump it (a search belongs to
   the trail it started from). A dropped result shows nothing.
   On a valid result push `LinkedTrailsScreen`: rows
   `project · handle · name · reasons`; each `ProjectScanError` as a disabled
   row (`<project>: could not search (stale path / not registered / export
   failed / timed out)`). Messages: links empty + `complete` → "No linked
   trails in other projects"; links empty + not `complete` → "No linked trails
   found — N project(s) could not be searched" with the error rows shown (never
   the definitive message).
3. On select → thread worker (guard at execution boundary): re-resolve root;
   `owned_lookup_session(root)`; if None → `bootstrap_project_session(root)`
   (new helper in `agent_launch_utils.py` holding the subprocess call now in
   `TuiSwitcherOverlay._ensure_session_live`, which is changed to call it and
   keeps its own result/STALE handling) then re-lookup; version-skew check
   (target `board/trails_app.py` lacks `--trail` → notify "<Y> runs an older
   aitasks; run `ait upgrade` there", still switch session);
   `launch_or_focus_trails(session, root, handle)`; then
   `switch-client -t =<session>` via gateway. Not in tmux →
   notify with the manual command `ait projects exec <Y> -- ait trails --trail <h>`.
4. Tests: binding identity on both hosts; modal rendering incl. incomplete-
   scan rows and both empty messages; **scan supersession**: search on A then
   switch to B / close A / leave By-Trail before the result lands → no modal;
   two searches completing out of order → only the newest opens; jump worker with
   stubbed resolver/gateway: live session, bootstrap path, bootstrap failure,
   not-in-tmux, version-skew; switcher `_ensure_session_live` regression
   (existing tests keep passing).

## Step 9 reference

After implementation and review, follow task-workflow Step 9 (merge if
applicable, archive this child; the parent t1957 archives automatically when its
last child is archived).
