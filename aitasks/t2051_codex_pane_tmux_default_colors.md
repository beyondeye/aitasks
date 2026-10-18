---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Postponed
labels: [codex, tmux, codeagent]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
created_at: 2026-10-18 12:33
updated_at: 2026-10-18 18:55
---

## Problem

In tmux, the Codex CLI "Working" shimmer animation is almost invisible. Observed in a live Codex pane: the shimmer text is drawn as `38;2;0;0;0` (pure black) on a dark `48;2;30;30;30` background.

## Root cause (verified)

Codex builds the shimmer by blending the terminal's default foreground and background, which it learns by querying OSC 10 / OSC 11. Inside tmux those queries are answered by tmux, and with no pane style set tmux replies `rgb:0000/0000/0000` for **both** (probed in a throwaway tmux window). Black blended with black is black.

Ruled out: truecolor (panes have `COLORTERM=truecolor`, `TERM=tmux-256color`, `terminal-overrides *:RGB`, Codex emits `38;2;…`), tmux dimming (`window-style` / `window-active-style` are `default`), `tui.theme` (syntax highlighting only), anything in `.aitask-scripts/`.

Verified fix mechanism: after `tmux select-pane -t <pane> -P 'fg=#cdd6f4,bg=#1e1e2e'`, the same probe returns `rgb:cdcd/d6d6/f4f4` and `rgb:1e1e/1e1e/2e2e`, i.e. tmux answers OSC 10/11 from the pane style. (An earlier probe appeared to show no effect; that was a shell-quoting error in the probe, not tmux.)

## Constraint

The solution must NOT be tied to a specific outer terminal (no Alacritty/Ghostty/kitty-specific logic).

## Proposed approach

When the framework launches a Codex pane inside tmux, give that pane an explicit pane style so tmux answers Codex's colour query with real values. Apply it through the tmux gateway (`lib/tmux_exec.py` / `lib/tmux_exec.sh`; read `aidocs/framework/tmux_gateway.md`) from the launch path in `.aitask-scripts/lib/agent_launch_utils.py`. Scope it to Codex panes (agent type codex, including shadow panes); other agents are unaffected.

Where the colours come from, in order of preference:
1. Query the outer terminal for its real default fg/bg with the standard OSC 10/11 sequences and use those. This is generic xterm behaviour, not a terminal-specific feature.
2. If nothing answers within a short timeout, fall back to a fixed readable dark pair, so the failure mode is "readable" rather than "invisible".
3. Check whether the TUIs already carry theme colours that can be reused before adding new machinery.

Open design point: a pane style paints the pane background and forces the default foreground. Decide whether to set bg at all or only fg, and check how that looks on a light outer theme.

## Acceptance

- In a Codex pane launched by the framework under tmux, an OSC 10/11 probe returns non-black, distinct fg and bg.
- The "Working" shimmer is visibly legible on a dark theme (capture with `tmux capture-pane -e -p` while a turn is running and confirm the RGB is not `0;0;0`).
- Non-Codex agent panes are unchanged (negative control).
- A test covers the style being applied only to Codex panes, and the fallback path when the outer terminal does not answer.

## Notes

Probe used: write `ESC ] 10 ; ? ESC \` and `ESC ] 11 ; ? ESC \` to the pane tty in raw mode and read the replies; it needs a real tty, so run it via `tmux new-window` rather than the Bash tool.
