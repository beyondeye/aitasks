---
priority: medium
effort: medium
depends: [t1957_4]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [t1957_4]
assigned_to: dario-e@beyond-eye.com
anchor: 1957
followup_kind: manual_verification
created_at: 2026-10-14 12:18
updated_at: 2026-10-14 16:41
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1957_4

## Verification Checklist

- [x] From `ait trails` in this repo, press `L` on a trail with cross-repo members: the Linked Trails dialog lists the `aitasks_mobile` linked trail, with error rows for thinking_app / thinking_backend (still incomplete, t1978) and the note "Some projects could not be fully searched — the list may be incomplete:" — PASS 2026-10-14 16:36 auto: isolated tmux server + pty client; L on art:trail-mobile-shadow-driving lists linked trails with reasons, thinking_app/thinking_backend 'searched in part' rows and the exact incomplete note. aitasks_mobile substituted by fixture project verify_ymob: aitasks_mobile is on framework 0.27.0 (no ait artifact) so it holds no trails and no aitasks_mobile link can exist
- [x] Enter on that row switches the tmux client to the aitasks_mobile session, with the trail focused in its `ait trails` (the running instance, or a new `trails` window) — PASS 2026-10-14 16:36 auto: existing vf_ymob session -- (a) running trails pane (same pid) re-focused the trail after ^w closed its tab; (b) killed trails window -> new 'trails' window './ait trails --trail art:trail-vf-ymob' in the same session; client switched both times, no duplicate session
- [x] Stop the aitasks_mobile tmux session, then repeat the jump: its session is started first (bootstrap), then the client switches and the trail opens — PASS 2026-10-14 16:36 auto: no vf_ymob session -> Enter bootstrapped it (monitor window), launched trails --trail, switched the pty client; trail shown focused
- [x] Same `L` flow from `ait board` in the By-Trail view (`z`); `L` is absent from the footer in the other views and while no trail is loaded — PASS 2026-10-14 16:41 auto: ait board By-Trail (z): L absent with no trail loaded and in views a/l/f/i/y; present once a trail is loaded; L lists the same links + incomplete note; Enter switched the pty client to vf_ymob and re-focused its running trails pane
- [x] Version-skew warning visibility: register a scratch copy of an aitasks project whose `.aitask-scripts/board/trails_app.py` lacks `--trail`, with a trail linked to the current one. `L` → pick it → the upgrade warning shows in a dialog in THIS TUI before anything switches. "Stay here" leaves the client in place; "Switch" lands in that project's session with no trail opened. Afterwards run `ait projects remove` on the copy — PASS 2026-10-14 16:41 auto: fixture verify_zold (trails_app.py with --trail stripped): warning 'verify_zold runs an older aitasks without trail jumps -- run ait upgrade there…' shown in the source TUI before any switch; Stay here kept client on aitasks; Switch landed in vf_zold with only its monitor window (no trails launched); then ait projects remove verify_zold (fixture registry via AITASKS_PROJECTS_INDEX -- real registry untouched)
- [x] From a terminal outside the aitasks tmux server, the jump only shows the manual command `ait projects exec <project> -- ./ait trails --trail <handle>` and starts no session — PASS 2026-10-14 16:41 auto: both cases -- TMUX/TMUX_PANE unset, and gateway socket naming a different (absent) server: notice 'Not in an aitasks tmux session -- open the trail with: ait projects exec verify_ymob -- ./ait trails --trail art:trail-vf-ymob'; no session started (vf_ymob was killed beforehand and stayed absent)
