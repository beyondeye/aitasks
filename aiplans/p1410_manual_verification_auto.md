---
Task: t1410_manual_verification_shadow_pane_id_structural_binding_resolu.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1410 — Auto-executed manual verification of t1319

Autonomous auto-verification run (`/aitask-pick 1410`, profile `fast`) of the
six checklist items verifying **t1319 — Resolve the shadow's followed pane from
its binding** (commit `95d2ba36f`, 2026-08-04 13:28:38 +0300).

The run was unusually favourable: the machine already hosted a live framework
tmux server (`-L ait`) with 3 sessions, 13 code agents and **9 live shadow
panes** carrying real `@aitask_shadow_target` bindings, six of which had
captured their followed agent *after* the t1319 commit. Four of the six items
could therefore be verified against real, unstaged shadows rather than
fixtures. All fixtures that were needed lived on a throwaway socket
(`-L verify1410`), so the user's live agents were never written to.

**Result: 6 / 6 pass, 0 fail, 0 defer, 0 skip.**

## Execution Log

### Item 1 — first argument-free capture in a minimonitor-spawned shadow

- Item text: Spawn a real shadow from minimonitor (`e`) against a live agent;
  confirm its first argument-free `aitask_shadow_capture.sh` call resolves the
  bound followed pane with no error (the launch->stamp race at the real
  agent-CLI layer).
- Approach: observation of an existing *real* shadow rather than reproduction —
  strictly stronger evidence, since it is a genuine minimonitor `e` spawn
  against a genuine live agent at the real agent-CLI layer.
- Action run:
  ```bash
  tmux -L ait list-panes -a -F '#{pane_id}|…|tgt=#{@aitask_shadow_target}|an=#{@aitask_shadow_analyzed_at}'
  tmux -L ait capture-pane -p -J -t %210 -S -      # 124 lines: the whole session
  ```
- Output (trimmed): shadow `%210` is an OpenAI Codex agent launched as
  `$aitask-shadow %204 1409`. Its entire 124-line scrollback contains exactly
  two capture calls, and the **first** one is:
  ```
  • Ran ./.aitask-scripts/aitask_shadow_capture.sh
    └ resolved followed pane %204 from @aitask_shadow_target
       ▐▛███▜▌   Claude Code v2.1.221
      … +154 lines
  ```
  No `pane id required`, no `refusing to capture`, anywhere in the scrollback.
  All 9 live shadow panes carry an `@aitask_shadow_analyzed_at` stamp; six are
  post-commit (13:41–16:46 vs. the 13:28 commit).
- Verdict: **pass**. The no-argument form resolved the binding on the shadow's
  first call, so `SHADOW_BIND_WAIT_MS` covered the `spawn_shadow`
  launch→stamp window at real agent-startup latency.

### Item 2 — concern picker still finds concerns

- Item text: With that shadow running, open the concern picker; confirm concerns
  still appear — `capture_shadow_text` now passes `--any-pane`, and a regression
  here surfaces as a silent "no concerns" rather than an error.
- Approach: CLI/library invocation replicating `minimonitor_app.action_pick_
  concerns`' data path verbatim (`capture_shadow_text` → `parse_concerns` →
  `block_head_truncated` deep retry → `unrecovered_markers`), plus a live TUI
  run of `monitor_app`'s byte-identical picker path (item 3).
- Action run: `python3 pick_concerns_probe.py %138 %195 %190 %206 %210 %176 %40 %68 %196`
- Output (trimmed):
  ```
  %138: captured 12266 chars, 1 concerns, unrecovered=0
  %195: captured 15843 chars, 2 concerns, unrecovered=0
  %190: captured 15140 chars, 2 concerns, unrecovered=0
  %206: captured  7512 chars, 4 concerns, unrecovered=0
  %210: captured  3815 chars, 0 concerns, unrecovered=0
  %176: captured 16302 chars, 2 concerns, unrecovered=0
  %40:  captured 17894 chars, 1 concerns, unrecovered=0
  %68:  captured  2734 chars, 0 concerns, unrecovered=0
  %196: captured 17768 chars, 2 concerns, unrecovered=0
  ```
  Nine of nine captures succeeded (no `CAPTURE_FAILED`, which is what the
  regression would produce); seven yielded parsed concerns. The two zero-concern
  panes captured fine and genuinely carry no concern block.
- Verdict: **pass**.
- Deviation: minimonitor's *modal* was not driven — a minimonitor only picks up
  the agent in its own tmux window, which cannot be arranged from a foreign
  socket without inserting a pane into the user's live windows. Its data path
  was replicated line-for-line instead, and `monitor`'s identical picker was
  driven end-to-end through the real TUI (item 3).

### Item 3 — cross-server `ait monitor`

- Item text: Run `ait monitor` from a personal tmux session on a different
  socket than `-L ait`; confirm the shadow preview column and the concern picker
  still work (the cross-server case the `--any-pane` opt-out exists for).
- Approach: TUI interaction — real `ait monitor` on a throwaway socket, driven
  with `send-keys` and read back with `capture-pane`.
- Action run:
  ```bash
  env -u TMUX -u TMUX_PANE tmux -L verify1410 new-session -d -s v -x 200 -y 50 \
      -c /home/ddt/Work/aitasks "./ait monitor"
  tmux -L verify1410 send-keys -t v Down   # focus 2:agent-pick-1377 (%116)
  tmux -L verify1410 send-keys -t v c      # concern picker
  ```
- Output (trimmed):
  - Header: `tmux Monitor — 3 sessions · 16 panes · multi (attached: aitasks)`,
    `CODE AGENTS (13)` — cross-server discovery works.
  - Shadow column header: `Shadow (%138 ← %116)`, rendering the live shadow's
    text; staleness banner `Shadow raised 1 concern(s) — press 'c' to pick
    (⚠ STALE — agent moved on)`.
  - Picker modal: `1 concern(s) · select to forward`, showing
    `☐ MED t1377_4 I/O atomicity  The merge's all-or-nothing guarantee …`.
  - `Escape` dismissed it cleanly.
- Verdict: **pass**. Both the preview column and the picker work from a
  different socket, which is `--any-pane`'s reason for existing in
  `capture_shadow_text`.
- Note: a first attempt piped the launch through `tee` for logging; that made
  stdout a non-TTY, Textual fell back to 80×24 and the agent list rendered
  empty. Re-run without the pipe. Never instrument a TUI through a pipe.

### Item 4 — wrong-pane refusal from inside a bound pane

- Item text: From inside a live shadow pane, run
  `./.aitask-scripts/aitask_shadow_capture.sh <a-wrong-pane-id>`; confirm it
  exits 2, names both the requested and the bound pane, and captures nothing.
- Approach: fixture pane stamped exactly as `spawn_shadow` stamps a shadow, on
  the throwaway socket with `AITASKS_TMUX_SOCKET=verify1410` so the gateway and
  `$TMUX` agree — i.e. the *same-server, conflicting binding* branch of
  `shadow_self_target`, identical to a real shadow on `-L ait`. The "wrong" id
  was `%0`, a **real, live, capturable** pane: the exact truncation hazard.
- Action run: `item4_fixture.sh %1 %0` (bound `%1`, wrong `%0`).
- Output (trimmed):
  ```
  wrong_explicit     argv=[%0]              rc=2  stdout_bytes=0
    Error: refusing to capture %0: this pane is bound to %1 via
    @aitask_shadow_target. If %0 is a mistyped or truncated id, re-run with NO
    argument to capture the bound pane; pass --any-pane to capture %0 deliberately.
  wrong_with_anypane argv=[--any-pane %0]   rc=0  stdout_bytes=11663
  correct_explicit   argv=[%1]              rc=0
  noarg              argv=[]                rc=0
    resolved followed pane %1 from @aitask_shadow_target
  ```
- Verdict: **pass**. Exit 2, both ids named, zero bytes on stdout. The
  `--any-pane` run is the negative control: it returned 11663 bytes from the
  same id, proving the pane *was* capturable and that the refusal — not an
  unreadable target — is what prevented the wrong capture.

### Item 5 — manual invocation from outside the framework's tmux server

- Item text: Invoke `/aitask-shadow %<id>` manually from OUTSIDE the framework's
  tmux server; confirm the agent follows the split recovery (ask the user to
  confirm the pane, then re-run with `--any-pane`) and does NOT livelock between
  the no-arg and explicit forms.
- Approach: two independent checks — (a) the mechanism, scripted; (b) a **real
  agent**, launched exactly as `aitask_codeagent.sh` launches one.
- Action run (a): `item5_fixture.sh %116` from a pane on `-L verify1410` with
  `AITASKS_TMUX_SOCKET` unset, so the gateway addresses `-L ait`:
  ```
  explicit_id    argv=[%116]              rc=2  (cross-server refusal, names --any-pane only)
  noarg          argv=[]                  rc=1  (pane id required … (cross-server))
  anypane        argv=[--any-pane %116]   rc=0  stdout_bytes=17759
  anypane_again  argv=[--any-pane %116]   rc=0  stdout_bytes=17759
  ```
  The ladder is a DAG, not a cycle: each error names a *different* next rung
  (`noarg → explicit → --any-pane`), and the terminal rung is a fixed point.
  Note the cross-server exit-2 text deliberately does **not** repeat the
  bound-to branch's "re-run with NO argument" suggestion — that asymmetry is
  what forecloses the bounce.
- Action run (b):
  ```bash
  env -u TMUX -u TMUX_PANE tmux -L verify1410 new-window -d -t v -n shadowmanual \
      -c /home/ddt/Work/aitasks "claude '/aitask-shadow %116'"
  ```
- Output (trimmed) — the real agent made exactly three capture calls:
  ```
  ● Bash(./.aitask-scripts/aitask_shadow_capture.sh)
    ⎿ Error: Exit code 1 … (cross-server) …
  ● Not running in a bound shadow pane — falling back to the explicit id you gave.
  ● Bash(./.aitask-scripts/aitask_shadow_capture.sh %116)
    ⎿ Error: Exit code 2 … different tmux server … Pass --any-pane …
  ● I'm on a different tmux server than %116, so the helper can't verify that id
    … I need you to confirm before I override.
    [AskUserQuestion] "Is %116 the pane you want me to shadow?"
  ● Bash(./.aitask-scripts/aitask_shadow_capture.sh --any-pane %116)   → success
  ```
  After confirmation it produced a full advisory summary of the followed agent.
- Verdict: **pass**. The agent followed the split recovery verbatim, stopped to
  ask before overriding, and never returned to the no-arg form. Three calls,
  terminating.

### Item 6 — `monitor_core.py` end-to-end in tmux

- Item text: TODO: verify `.aitask-scripts/monitor/monitor_core.py` end-to-end
  in tmux (interactive surface touched by this task).
- Approach: covered by the live TUI run in item 3 plus the shadow-fleet
  observation in item 1.
- Evidence:
  - `capture_shadow_text` — the sole `monitor_core` change in t1319 (adding
    `--any-pane`) — exercised through the real monitor's Shadow column and
    concern picker, cross-server, where the pre-change code would have returned
    `None` and shown a silent "no concerns".
  - `find_shadow_pane_async` / `match_shadow_pane` — the header
    `Shadow (%138 ← %116)` is the reverse lookup resolving correctly.
  - `compute_shadow_staleness` — the `⚠ STALE — agent moved on` banner.
  - `spawn_shadow`'s `@aitask_shadow_target` stamping — 9 live shadow panes,
    every one correctly bound, and `%210` proving the stamp landed before its
    shadow's first capture.
- Verdict: **pass**.

## Cleanup

- `tmux -L verify1410 kill-server` — the throwaway socket only (5 windows:
  monitor, spare, fixture, xserver, shadowmanual). **Done**; `-L ait` verified
  intact afterwards (3 sessions). The framework socket was never a kill target.
- Scratch fixtures and probe scripts under the session scratchpad
  (`av1410/`): `pick_concerns_probe.py`, `item4_fixture.sh`,
  `item5_fixture.sh`, and their `item{4,5}_*.out/.err/report.txt`. Left in the
  session scratchpad; nothing was written under `aitasks/` or `aiplans/` other
  than this plan and the checklist itself.
- No live agent pane was ever written to: every interaction with the `-L ait`
  server was a read (`list-panes`, `capture-pane`, `display-message`).
