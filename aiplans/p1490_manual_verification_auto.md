# Plan: t1490 — Manual verification (auto-execution) of the t1486 Textual markup fixes

Task: aitasks/t1490_manual_verification_textual_markup_structure_defects_followu.md
Task ID: 1490
Verifies: t1486 (commit 5718ff0fb)
Base branch: main
Output branch: main
Working directory: /home/ddt/Work/aitasks
Strategy: autonomous auto-verification (retroactive record)

## Scope

t1486 fixed three Textual **markup structure** defects — brackets Textual read
as tags — plus a logview startup-focus defect found while pinning them:

- `board/aitask_board.py` — GitLab indicators closed with `[/e24329]`, a tag
  never opened (`[#e24329]` opens `#e24329`). `MarkupError` crashed the
  compositor for any task whose `issue:` / `pull_request:` URL pointed at a
  GitLab host. Now closed with `[/]`.
- `monitor/monitor_app.py` — `[AUTO]` eaten as an unknown tag; now `\[AUTO]`.
- `logview/logview_app.py` — `[{state}]`, ` [raw]`, `[size: N]` escaped.
- `logview/logview_app.py` — `on_mount` now focuses the RichLog first, on both
  paths, so single-key bindings fire without a prior mouse click.

All seven checklist items were driven live in tmux; nothing was deferred.

## Environment

Isolated tmux server `-L av1490` (the user's live `-L ait` server was never
touched — re-checked after teardown). Scratch root:
`…/scratchpad/auto_verify_1490/`.

Board items ran against a **mutation-safe fixture project** built per the
`ait`-cds-to-its-own-dir recipe: `ait` + `.aitask-scripts/` + a synthetic
`aitasks/` with eight tasks, one per issue/PR indicator branch. The real repo
was never driven.

## Execution Log

### Item 1 — logview header states + startup focus

- Item text: `ait logview <a log file with content>`: header shows `[live]` at
  launch; press `r` with NO prior mouse click → `[raw]` alongside `[live]`;
  press `p` → `[paused]`.
- Approach: TUI interaction (tmux send-keys + capture-pane).
- Note on the command: there is **no top-level `ait logview`** — the dispatcher
  routes `logview` only under `ait crew` (`ait:250`). Ran the real entry point,
  `./ait crew logview --path <file>`, which tails by default.
- Action run:
  ```
  tmux -L av1490 new-session -d -s fix -x 160 -y 45 -c /home/ddt/Work/aitasks
  tmux send-keys "./ait crew logview --path <scratch>/full.log" Enter   # 200 lines
  tmux send-keys r ; tmux send-keys p
  ```
- Output (trimmed):
  ```
  File: …/full.log  [size: 4292]  [live]
  File: …/full.log  [size: 4292]  [live] [raw]      # after r
  File: …/full.log  [size: 4292]  [paused] [raw]    # after p
  ```
- Verdict: **pass**. `[live]`, `[raw]`, `[paused]` and `[size: N]` all survive
  the markup parser. `r` fired its binding with no prior click, so the
  RichLog — not the hidden `#search-box` Input — held focus at startup.

### Item 2 — empty log file, `r` (known defect t1489)

- Item text: `ait logview <an EMPTY log file>`: press `r` → header is EXPECTED
  to stay `[live]` until another key is pressed. Known defect t1489, not a
  t1486 regression.
- Approach: TUI interaction.
- Action run: `./ait crew logview --path <scratch>/empty.log`, then `r`, `G`, `p`.
- Output (trimmed):
  ```
  File: …/empty.log  [size: 0]  [live]          # launch
  File: …/empty.log  [size: 0]  [live]          # after r  — stale, as expected
  File: …/empty.log  [size: 0]  [live]          # after G  — still stale
  File: …/empty.log  [size: 0]  [paused] [raw]  # after p  — repaint catches up
  ```
- Verdict: **pass** (behaved exactly as the item documents). The header is
  stale, not wrong: `[raw]` appears as soon as a header-updating key repaints
  it. Consistent with t1489; no t1486 regression.

### Item 3 — `--no-tail` static header

- Approach: TUI interaction.
- Action run: `./ait crew logview --path <scratch>/full.log --no-tail`
- Output: `File: …/full.log  [size: 4292]  [static]`
- Verdict: **pass**.

### Item 4 — monitor AUTO indicators

- Item text: `ait monitor`: toggle auto-switch → session bar shows a bold-yellow
  `[AUTO]` and the CODE AGENTS header shows the separate `⟳ AUTO` indicator;
  toggle back → both disappear.
- Approach: TUI interaction, isolated socket.
- Fixture notes: the monitor pane's command was prefixed with
  `env AITASKS_TMUX_SOCKET=av1490` so the app queried the fixture server rather
  than the shared `ait` socket. `_agents_header_text` only renders once at least
  one agent pane exists, and `classify_pane` keys off the **window name** —
  a window named `agent-t1490demo` was created to populate `CODE AGENTS (1)`.
  The monitor pane also needed full window height; a leftover split collapsed
  the pane-list container to its two border rows.
- Action run: `tmux send-keys A` (toggle on), capture, `A` again (toggle off).
- Output (trimmed, `capture-pane -pe`):
  ```
  # ON — session bar (bar-wide ESC[1m bold already set, then pure yellow):
  …multi (attached: fix)  1 idle  ESC[38;2;255;255;0m[AUTO]ESC[38;2;221;237;249m…
  # ON — CODE AGENTS header:
  ESC[1mESC[38;2;160;160;160mCODE AGENTS (1)  ESC[38;2;255;255;0m⟳ AUTOESC[38;2;160;160;160m…
  # OFF — plain capture, grep -c AUTO => 0
  tmux Monitor — 1 session · 1 pane · multi (attached: fix)  1 idle  Tab: switch panel
  │ CODE AGENTS (1)  (● active ● prompt ● idle ● done)                          │
  ```
- Verdict: **pass**. Both indicators render bold yellow, are separate, and both
  disappear on the second toggle.

### Item 5 — board GitLab badges, the crash case

- Item text: `ait board` with a task whose `issue:` frontmatter is a GitLab
  issue URL → row renders a `GL` badge in GitLab orange (#e24329) and the board
  does NOT crash. Repeat with a GitLab merge-request URL → `MR:GL`.
- Approach: TUI interaction against the isolated fixture project.
- Fixture note: `_pr_indicator` is fed by the **`pull_request:`** field, not
  `issue:` (`aitask_board.py:3046-3049`), so the MR URL was seeded there.
- Action run: `./ait board` in a 200x50 tmux pane over the 8-task fixture.
- Output (trimmed, `capture-pane -pe`):
  ```
  │ ☐ t1 gitlab issue │  💪 low | ESC[38;2;226;67;41mGL
  │ ☐ t2 gitlab mr    │  💪 low | ESC[38;2;226;67;41mMR:GL
  ```
  `38;2;226;67;41` is exactly #e24329. Board rendered fully; no crash.
- **Negative control** (one mutation, isolated copy): the fixture was copied and
  *only* the two closing tags reverted to the pre-t1486 `[/e24329]`. That board
  crashed on launch:
  ```
  textual.markup.MarkupError: closing tag '[/e24329]' does not match any open tag
  ```
  So the fixture genuinely exercises the crash path, and the fix is what
  prevents it.
- Verdict: **pass**.

### Item 6 — sibling branches after the closing-tag change

- Item text: GitHub → `GH` / `PR:GH`, Bitbucket → `BB` / `PR:BB`, a
  non-platform URL → `Issue` / `PR`.
- Approach: same fixture, same board instance.
- Output (unique SGR-prefixed badges from `capture-pane -pe`):
  ```
  ESC[38;2;0;0;255m   GH      ESC[38;2;0;0;255m   BB
  ESC[38;2;0;0;255m   Issue   ESC[38;2;0;0;255m   PR:BB
  ESC[38;2;0;128;0m PR:GH   ESC[38;2;0;128;0m PR
  ESC[38;2;226;67;41m GL     ESC[38;2;226;67;41m MR:GL
  ```
  All eight branches render; blue/green/orange match the source.
- Verdict: **pass**.

### Item 7 — board end-to-end in tmux

- Item text: TODO: verify `.aitask-scripts/board/aitask_board.py` end-to-end in
  tmux.
- Approach: satisfied by items 5–6 — the real board binary was launched in a
  live 200x50 tmux pane against tasks covering every indicator branch, plus a
  crashing negative control on the same surface.
- Verdict: **pass**.

## Final Implementation Notes

- **Actual work done:** All 7 checklist items driven live in an isolated tmux
  server; all 7 pass. No follow-up bug tasks created for t1486.
- **Deviations from plan:** items 1–2 name a command (`ait logview`) that does
  not exist; the real entry point is `ait crew logview --path <file>`, which was
  used instead. This is checklist wording, not a defect.
- **Issues encountered:** three fixture gotchas cost time and are worth
  remembering — the monitor needed `AITASKS_TMUX_SOCKET` in the pane command,
  an `agent-`-prefixed **window** name to populate CODE AGENTS, and full pane
  height before the pane-list container rendered anything at all.
- **Key decisions:** ran the board against a copied fixture project rather than
  the live repo, and added a one-mutation negative control so "did not crash"
  is a real result rather than a fixture that never reached the code.
- **Upstream defects identified:**
  - `.aitask-scripts/board/aitask_board.py` — relaunching `ait board` in the
    same shell/pane after quitting with `q` renders the column headers with
    correct counts (`Now ⚡ (6)`, `Next Week 📅 (2)`) but **zero task cards**;
    every column shows `(empty)`. Reproduced 3/3 across three independent tmux
    sessions; a first launch in a fresh shell always renders correctly, and a
    terminal resize does not repair it. No error output on either stream. Data
    loading is evidently fine (the counts are right), so this is a card-mount /
    teardown-state defect, unrelated to t1486's markup change.
    **Spawned as t1491** (`followup_kind: upstream_defect`).

## Cleanup

- `tmux -L av1490 kill-server` — done; the user's live `-L ait` server verified
  intact afterwards.
- Scratch fixtures under `…/scratchpad/auto_verify_1490/` (session-scoped, left
  in place for reference).
