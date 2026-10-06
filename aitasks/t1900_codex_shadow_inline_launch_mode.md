---
priority: high
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, codex, codeagent]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1892
created_at: 2026-10-06 08:55
updated_at: 2026-10-06 08:56
---

## Symptom

Since the codex-cli upgrade to 0.160.0, minimonitor's concern parsing for a
**Codex shadow** sees only what is currently on the shadow pane's screen, not
the pane's history. A concern block that has scrolled partly off screen parses
truncated. Codex chrome can fold into the last concern. Scrolling the Codex
view changes what `c` offers.

## Root cause (measured live, 2026-10-06)

codex-cli 0.160.0 runs its TUI on the **alternate screen** by default. 0.154.0
ran inline. On the alternate screen tmux keeps no scrollback, so
`aitask_shadow_capture.sh --deep` (`-S -400`) and minimonitor's 1500-line retry
return only the ~61 visible rows.

`tmux list-panes -F '#{alternate_on} #{history_size}'` on the same box:

| pane | codex binary | alternate_on | history_size |
|---|---|---|---|
| thinking_back %77, %72 (shadows) | 0.154.0 | 0 | 104 / 545 |
| aitasks %296, %313, %314, %315 (shadows) | 0.160.0 | 1 | 0 |

0.160.0 adds `--no-alt-screen` ("Disable alternate screen mode. Runs the TUI in
inline mode, preserving terminal scrollback history."). 0.154.0 had no such
flag. The 0.160.0 binary also carries an `alternate_screen` config-key string,
so a `-c tui.alternate_screen=…` form probably exists. Its key path and value
vocabulary are not yet measured.

The defect is a launch-mode regression, not a parser bug. t1897 (split-join
edge case) and t1899 (glyph measurement for opencode/agy) are unrelated. t1898
designed heavier machinery for the same symptom (persisting the block, a
producer-side artifact). It is postponed in favour of this simpler fix.

## Goal

Launch **Codex, only when used as a shadow agent**, in inline (non-alternate-
screen) mode, so its pane keeps tmux scrollback. The existing `--deep` capture
then sees the whole concern block again. Do not change other Codex launches
(pick, explore, qa, raw, …) or other agents.

## Fix site

`.aitask-scripts/aitask_codeagent.sh`, `codex)` branch of the command builder.
The skill-launch arm builds
`CMD=("$binary" "${CODEX_TUI_OVERRIDES[@]}" "$model_flag" "$cli_id" "$prompt")`
for every operation, `shadow` included. Add the inline-mode switch for
`operation == shadow` only. Do NOT put it in `CODEX_TUI_OVERRIDES`, which every
Codex launch carries.

## Things planning must settle

- **Flag vs config form / version compatibility.** An unknown CLI flag is a hard
  clap error, so `--no-alt-screen` would break a shadow launch on a codex older
  than 0.160 (0.154.0 has no such flag). Unknown `-c tui.*` keys are ignored
  (measured on 0.154.0, see the `CODEX_TUI_OVERRIDES` comment). Measure whether a
  `-c tui.alternate_screen=<value>` override exists on 0.160.0 and what disables
  it. Prefer it if it does, and record the measurement in a comment like t1797's.
  If only the flag works, decide between gating it on the detected codex version
  and requiring >= 0.160.
- **Restored / resumed shadows.** A frozen shadow restored through
  `invoke raw --resume <sid>` takes the `batch-review|raw` arm, not the shadow
  arm, so it would come back on the alternate screen. Check whether shadow
  panes are ever restored this way and, if so, carry the mode there too, still
  scoped to shadows only.
- **Stale "every agent runs on the alternate screen" assumptions.** The
  `monitor_core.capture_raw_tail` docstring (t1520) and the `_CAPTURE_LINES`
  comment in `lib/pane_state_probe.py` both claim it. That is already false for
  Claude Code (alt=0, with history), and it becomes false for Codex shadows.
  `capture-pane -S -N` on an inline pane returns N history rows plus the visible
  pane. Check the consumers that read a Codex **shadow** pane through that
  assumption: the review loop's shadow-readiness detector (`capture_raw_tail`),
  the staleness / freshness path (`compute_block_age_staleness`,
  `parse_block_meta`), and the codex prompt patterns in
  `monitor/prompt_patterns.py`. Many of those patterns were measured on the
  inline 0.154 renderer. Fix any wording or behaviour that depends on the pane
  having no scrollback.
- **Docs.** Update the "Capture-window contract" in
  `.claude/skills/aitask-shadow/concern-format.md` and
  `aidocs/framework/shadow_agent.md` where they describe the capture window for
  a Codex shadow.

## Tests

- `tests/test_codeagent.sh` (dry-run): `invoke shadow` with a codex agent string
  carries the inline-mode switch. `invoke pick` / `explore` / `raw` with codex do
  not. Claude/opencode shadow launches are unchanged.
- If a version gate is added, test both sides of it.

## Verification (live)

Spawn a Codex shadow from minimonitor and confirm:

1. `tmux display -p -t <shadow> '#{alternate_on} #{history_size}'` reports
   `0` and a growing history.
2. After a plan-review block longer than the pane height, `c` offers the full
   concern list with no Codex chrome in the last item.
3. Scrolling the Codex shadow pane (tmux copy-mode) does not change the concern
   list or the freshness verdict. This is the acceptance criterion t1898
   recorded.
