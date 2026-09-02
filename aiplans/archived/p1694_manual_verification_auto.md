---
Task: t1694_manual_verification_park_code_agents_tristate_mark_and_visib.md
Verifies: t1685
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# Auto-Verification Execution Log — t1694

Autonomous whole-list auto-verification of the t1694 checklist, which verifies
t1685 (`feature: Park code agents with a tristate mark and a visibility
toggle`).

## Harness

Live tmux throughout — every visibility claim below is a `capture-pane` read of
a real terminal, not a headless `run_test` assertion.

- **Isolated server.** `TMUX_TMPDIR=/tmp/claude-1000/t1694tmux` (short, to stay
  under the ~104-byte socket-path limit) on the framework's default `ait`
  socket, launched with `env -u TMUX -u TMUX_PANE` so the developer's ambient
  pane never leaks in.
- **Two fixture projects.** `projA` / `projB`, each a copy of `ait` beside a
  **symlink** to the real `.aitask-scripts` (never a `cp -r`, so probes ran the
  committed code), plus `aitasks/metadata/project_config.yaml` so
  `discover_aitasks_sessions()` treats the sessions as aitasks-like, and
  `models_*.json` copied in for the shadow-launch resolution.
- **Fake agents** are tmux windows named `agent-*` running `sleep` / `tail -f`
  — `classify_pane` keys on the window name, so no real code agent was started.
  A `bash` stub named `claude` was placed ahead of `$PATH` for the one item that
  spawns a shadow, so no real agent session was ever launched.
- **Mark store redirected** via `AITASKS_AGENT_MARKS_FILE` into the fixture —
  the user's real `~/.config/aitasks/agent_marks.json` was never read or
  written.
- **Keys** driven with `send-keys` (`-l ' '` for `space`; SGR mouse sequences
  for clicks, since a click is the only way to restore focus after item 4's
  defect).

## Execution Log

### Item 1 — space cycles unmarked → ★ → P → unmarked

- Approach: TUI interaction.
- Action: `Down` to focus the first card, then three `send-keys -l ' '`.
- Output: row read `☆ …` → `★ …` → `P 1:agent-t101-claudecode (1)  parked` →
  `☆ …`; the mark store went `[]` → `kind: priority` → `kind: parked` → `[]`.
- Verdict: **pass**. The parked glyph is ASCII `P` (U+0050) rendered bold white,
  so font coverage is not at risk on any terminal.

### Item 2 — parked row shows only P, name, dim `parked`

- Approach: TUI interaction + `capture-pane -pe` for styling.
- Output: `P 1:agent-t101-claudecode (1)  parked` — no state dot, no `≈` compare
  glyph, no status, no gate summary. Unfocused, `parked` renders `#999999`
  against `#e0e0e0` body text; focused, `#6c4611` against the `#fea62b` focus
  ground — a dim shade in both.
- Verdict: **pass**.

### Item 3 — `N parked` term beside the live counters

- Approach: TUI interaction.
- Output: session bar read `2 idle  1 parked`. Parking the awaiting-input agent
  dropped `1 awaiting` from the bar entirely (`1 idle  2 parked`), so parked
  agents leave the live buckets rather than being double-counted.
- Verdict: **pass**.

### Item 4 — `P` hides parked agents, `P` again shows them

- Approach: TUI interaction.
- Output: **FAIL.** The hide works, but when the focused card is the parked
  agent being hidden, focus is stranded and the app stops responding to *every*
  keyboard binding — `P`, `Space`, `?`, arrows. `capture-pane -pe` showed zero
  focus highlights and the preview still rendered `This agent is parked — press
  Space to unpark it.`, i.e. `_focused_pane_id` was still the hidden pane. Only
  a mouse click on a visible card restored input.
  Reproduced 3/3 from a cold `ait monitor` (`Down`, `space`, `space`, `P`); does
  **not** reproduce on a warm app (11/11 clean), nor when focus is on a card
  other than the one being hidden (11/11 clean: the list shrank and grew as
  specified).
- Verdict: **fail** → follow-up **t1697**, which carries the full repro.

### Item 5 — parking the focused card with the filter ON

- Approach: TUI interaction.
- Output: with the filter on, `space`×2 on the focused visible card removed its
  row; exactly one focus highlight remained, on a visible card, and `?` still
  opened the Keys modal — so focus landed on a card, not on the preview column
  and not nowhere.
- Verdict: **pass**.

### Item 6 — parking the ONLY visible agent with the filter ON

- Approach: TUI interaction.
- Output: pane list emptied with no stray rows, session bar read `3 parked`,
  preview showed its empty state (`Focus an agent or pane to see its output`),
  and `P` from that empty state revealed all three parked rows.
- Verdict: **pass**.

### Item 7 — preview text for a focused parked card, filter OFF

- Approach: TUI interaction.
- Output: preview read exactly `This agent is parked — press Space to unpark
  it.`
- Verdict: **pass**.

### Item 8 — the parking toast names the route back

- Approach: TUI interaction, captured within the toast's 6s window.
- Output: `Parked agent-t103-claudecode — hidden. Press P to show parked
  agents, then Space to unpark.`
- Verdict: **pass**.

### Item 9 — auto-switch never targets a parked agent

- Approach: TUI interaction with a live negative control. Auto-switch only
  re-targets across a pane-list rebuild, so a rebuild was forced by adding /
  killing a window.
- Control (nothing parked): focus on an Active agent, `A` armed, rebuild forced
  → focus moved to the awaiting-input agent. The mechanism is live and the probe
  can see it move.
- Test (the idle agent and the awaiting-input agent both parked): same setup →
  focus stayed on the Active agent and never landed on either parked row, even
  though the awaiting-input agent would have won the unparked contest.
- Verdict: **pass**.

### Item 10 — parked followed agent keeps its docked panel live

- Approach: minimonitor split into a window that already held a pane (it
  auto-closes as a solitary pane). Followed window `agent-pick-101` with a
  fixture task carrying a `## Gate Runs` ledger, so the phase line renders a
  real value whose `⏸` half is derived from the **live capture**.
- Control (unparked): pushing a prompt to the bottom of the followed pane
  flipped the phase `IMPLEMENT?` → `IMPLEMENT ⏸?`.
- Test: after `space`×2 the panel read `P agent-pick-101`, and while parked the
  phase flipped `IMPLEMENT ⏸?` → `IMPLEMENT?` → `IMPLEMENT ⏸?` as the followed
  pane's content changed — both directions, proving the pane goes on capturing
  the agent it follows.
- Verdict: **pass**.

### Item 11 — L / c / e still work on a parked followed agent

- Approach: minimonitor interaction; toasts read from the pane.
- `L`: `Auto-recheck unavailable for 'tail' — the recheck loop supports claude,
  codex, opencode`. It resolved the followed agent's snapshot (it names the
  pane's command) and refused only on agent capability — not on parking, which
  would have read `Auto-recheck unavailable: no followed agent pane`.
- `c`: `No shadow agent running — press 'e' to launch one`.
- `e`: spawned a new pane stamped `@aitask_shadow_target=%10`, running the
  stubbed agent command `/aitask-shadow …`.
- Verdict: **pass**.

### Item 12 — `P` in the minimonitor, and the key hints row

- Approach: minimonitor interaction.
- Output: the three `P … parked` rows left the scrollable list on `P` and
  rejoined on the second `P`; the key hints row shows `P:parked`.
- Verdict: **pass**.

### Item 13 — cross-project propagation

- Approach: two projects, each with its own session and its own `ait monitor`.
- Output: parking `projB`'s agent from **`projA`'s** monitor showed up as
  `P 1:agent-t201-claudecode (1)  parked` in `projB`'s own monitor on the first
  poll; unparking it from `projA`'s monitor cleared it in `projB`'s in ~3s.
  Both directions, one refresh cycle.
- Verdict: **pass**.

### Item 14 — a parked pane genuinely stops being captured

- Approach: a `tmux` wrapper first on `$PATH` logging every argv before
  `exec`ing the real binary — direct evidence rather than an inference from the
  rendered frame. (Steady-state captures run over the control-mode client; the
  boot round is what this log sees, and the boot round is exactly the claim
  t1685 makes.)
- Control boot (nothing parked): `capture-pane` issued for `%0 %6 %7 %10 %13`.
- Test boot (`%0` and `%6` parked beforehand): `capture-pane` issued for
  `%10 %13 %7` only — **never once** for `%0` or `%6`.
- Runtime: `SECRET-AFTER-PARK-QQQ` written into a parked pane appeared in that
  pane but never anywhere in the monitor over ~12s; after unparking, the same
  marker appeared in the preview immediately.
- Verdict: **pass**.

### Item 15 — renaming the followed window while parked

- Approach: `rename-window` on the followed window with its agent parked, then
  flipping the followed pane's content in both directions.
- Output: the docked panel kept updating (`IMPLEMENT ⏸?` ↔ `IMPLEMENT?`), so
  the identity-confirmation fail-safe did not subtract the wrong pair and
  freeze the panel. The identity text stayed `agent-pick-101` (the panel's
  documented one-shot contract) and the mark glyph correctly fell back to `☆`,
  since a mark keys on the old window name.
- Verdict: **pass**.

### Item 16 — a pre-t1685 v1 store still shows every star

- Approach: hand-written v1 store (`"version": 1`, no `kind` key) with four
  records across both fixture projects.
- Output: `aitask_agent_marks.sh list` reported all four as `|priority`; the
  monitor rendered `★` on all four rows, while the one agent absent from the
  store rendered dim `☆` (negative control). The on-disk file was still
  `version: 1` after the read — the migration is read-side only and did not
  rewrite the user's file.
- Verdict: **pass**.

## Result

15 pass, 1 fail, 0 deferred. The failure is item 4, tracked as **t1697**.

## Cleanup

- tmux sessions `aitA` / `aitB` on `TMUX_TMPDIR=/tmp/claude-1000/t1694tmux`
  (whole server killed).
- `/tmp/claude-1000/t1694tmux` and the fixture tree under the session
  scratchpad (`projA`, `projB`, `marks.json`, `marks_v1.json`, `stubbin`,
  `wrapbin`, `tmuxcalls.log`).
- No file under the repo's `aitasks/` or `aiplans/` was touched except this
  plan, the t1694 checklist itself, and the t1697 follow-up.
