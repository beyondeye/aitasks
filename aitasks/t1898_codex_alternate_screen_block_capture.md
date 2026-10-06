---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [shadow, aitask_monitormini, tui, codex]
gates: [risk_evaluated]
anchor: 1892
followup_kind: risk_mitigation
created_at: 2026-10-05 23:42
updated_at: 2026-10-05 23:42
---

## Origin

Risk-mitigation ("after") follow-up for t1892, created at Step 8d after implementation landed.

## Risk addressed

viewport-truncated Codex block parsed to EOF with chrome in the last concern (goal-achievement)

- Planning reproduced the user's actual observed capture (`%263`), and the
  block in it is **viewport-truncated**. Codex runs on the alternate screen, so
  tmux keeps no scrollback and `--deep` buys nothing. Once markers parse, `c` on
  such a capture opens a picker whose last item carries Codex chrome
  (`New activity · ↓ Back to bottom`, composer, footer) via the forgiving
  parse-to-EOF, where today it shows the raw view. The ACs are met, but that
  live scenario is only clean when the whole block is on screen.
  · severity: medium · → mitigation: codex_alternate_screen_block_capture

## Goal

Codex shadow panes run on the **alternate screen**, where tmux keeps no
scrollback. `capture-pane -S -2000` (and the minimonitor's `--deep` / 1500-line
retry) therefore return only the ~60 visible rows. What the concern parser sees
is whatever Codex currently has on screen. That depends on the user's scroll
position inside Codex's own transcript view, and Codex's chrome lands inside an
unclosed block region (`New activity · ↓ Back to bottom · esc`, the
`› Ask Codex to do anything` composer, the model/footer line).

Two live shapes were observed during t1892:

- **Tail-truncated** (block head on screen, rest scrolled out): the forgiving
  `parse_concerns` reads to EOF and folds the chrome into the last concern's
  body. `c` would then forward pane chrome as concern text.
- **Head-truncated** (a newer round's opening fence scrolled off, items and
  closing fence on screen): `block_head_truncated` fires, and the deeper
  retry cannot help on an alternate-screen pane.

Define a capture strategy for scrollback-less (alternate-screen) shadow panes
and how an unclosed or truncated block is presented on `c`, so that pane
chrome is never forwarded as concern body.

### Acceptance criterion (user requirement, 2026-10-05)

**Scrolling the Codex shadow window must not change the latest review's concern
list or its freshness verdict.** Both must refer to the **same latest completed
review**, independently of the visible screen.

Things to weigh in planning, none of them prescribed here:

- a source of the latest completed review that does not depend on the
  viewport. One example is persisting the block when it is first seen
  complete; another is a producer-side artifact. Today the freshness
  (`compute_block_age_staleness`, `parse_block_meta`) and the concern list are
  both derived from the visible capture.
- detecting the alternate screen (`#{alternate_on}`) so that "no scrollback"
  is known rather than inferred.
- what `c` shows for an unclosed block on such a pane: the raw view, a
  warning, or the last persisted complete round.

## References

- t1892 plan: `aiplans/archived/p1892_codex_bullet_marker_breaks_concern_parsing.md`
  (Risk section, Final Implementation Notes).
- `.aitask-scripts/monitor/minimonitor_app.py` (`action_pick_concerns`,
  `_maybe_offer_concerns`), `.aitask-scripts/monitor/monitor_app.py`,
  `.aitask-scripts/monitor/monitor_shared.py` (freshness/staleness),
  `.aitask-scripts/aitask_shadow_capture.sh`, and the "Capture-window contract"
  in `.claude/skills/aitask-shadow/concern-format.md`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1900** id=2026-10-06T05:55:44Z.c71edcbb2a38c43ced71b6be from=t1900 at=2026-10-06T05:55:44Z base=3b82c14cbcc93f1a6249ef4443ef9ad10afba865 base_branch=main dirty=yes host=omg16
>
> | Advisory note from an explore session (2026-10-06). The user postponed this task in favour of a simpler fix tracked by t1900 (codex_shadow_inline_launch_mode).
> | 
> | Measured root cause: codex-cli 0.160.0 runs its TUI on the alternate screen by default. 0.154.0 ran inline (tmux list-panes: 0.154 shadows alt=0, hist 104/545; 0.160 shadows alt=1, hist 0). 0.160 adds `--no-alt-screen` (inline mode, preserving scrollback). So the "Codex runs on the alternate screen, no scrollback" premise in this task is a launch-mode regression, not an inherent property.
> | 
> | t1900 launches Codex shadows (only) in inline mode, so the existing --deep capture reads scrollback again. That should satisfy this task's acceptance criterion (scrolling must not change the concern list or the freshness verdict), because tmux copy-mode scrolling does not alter capture-pane output. This has not been verified live yet.
> | 
> | Residual cases t1900 does NOT address and that may justify reviving this task: a block longer than the 400-line deep window, and chrome folding into an unclosed block while a review is still streaming. Re-scope against those once t1900 lands.
