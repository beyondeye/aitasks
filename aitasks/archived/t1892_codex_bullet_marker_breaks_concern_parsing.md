---
priority: high
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Done
labels: [shadow, aitask_monitormini, tui, codex]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
risk_mitigation_tasks: [1898, 1899]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 15:12
updated_at: 2026-10-05 23:43
completed_at: 2026-10-05 23:43
---

A Codex shadow agent's concern block is **never parseable**: Codex's markdown
renderer rewrites the mandatory `- ` item marker to `• ` (U+2022 BULLET), and
every marker pattern in the parser hard-requires a literal dash. Pressing `c`
in minimonitor therefore reports an unparseable/uncertified block and opens the
raw-text view instead of the concern picker, so no concern from a Codex shadow
can ever be forwarded to the followed agent.

## Observed

Reported by the user from `thinkingapp:4` / `agent-pick-486` (shadow pane
`%263`, Codex, 60 columns): pressing `c` in minimonitor shows unparsed text.

## Reproduced

Measured live on 2026-10-05 against code tree `8dbed4ea4` by capturing the
shadow pane through the production path and calling the parser directly:

```
./.aitask-scripts/aitask_shadow_capture.sh --deep --any-pane %263 > cap.txt
```

```
parse_concerns      : 0
unrecovered_markers : []
has_concern_block   : False
metadata_only       : False
block_meta          : BlockMeta(round=2, reviewed_at='2026-10-05T12:04:05Z')
invalid_round_header: False
head_truncated      : False
```

The captured block region (verbatim, note the leading glyph on the item):

```
  ===AITASK-CONCERNS===
  Round: 2 @ 2026-10-05T12:04:05Z

  • [high | lifecycle and retry] Implementation step 2 sets
```

`cat -A` confirms the glyph is `M-bM-^@M-"` = UTF-8 `E2 80 A2` = U+2022, not a
hyphen. The two ASCII sentinel fences and the `Round:` header survive the
renderer intact — **only the item markers are rewritten**.

## Root cause

All three marker patterns anchor on a literal dash
(`.aitask-scripts/monitor/concern_parser.py`, lines as of `8dbed4ea4`):

- `_ITEM` (~line 147) — `^\s*-\s+\[\s*(?P<priority>\w+)\s*\|\s*…`
- `_ITEM_NO_REGION` (~line 162) — `^\s*-\s+\[\s*(high|medium|low)\s*\]…`
- `_MARKER_START` (~line 169) — `^\s*-\s+\[`

A `• [high | region] body` row matches none of them, so `_scan_items` yields no
item and the row falls through to continuation handling.

## Second defect: the diagnostic is blind to this failure mode

Because `_MARKER_START` also requires the dash, `unrecovered_markers()` returns
`[]` — so the honest "N line(s) could not be parsed" report added by t1274 /
t1293 never fires for the exact failure it exists to describe. In
`action_pick_concerns` (`.aitask-scripts/monitor/minimonitor_app.py`, ~line
4819) control therefore reaches the `parse_block_meta` branch and the user gets
`uncertified_round_block_msg(2)` plus a `ConcernBlockInspectModal([], …)` with
an empty lost-marker list — a message that names the wrong cause. The same
blindness applies to the auto-offer path `_maybe_offer_concerns` (~line 4971),
which silently never badges a Codex shadow.

## Why this is in scope as a bug, not an unsupported setup

Codex is a first-class agent in this framework (`_resolve_shadow_agent_key`,
t1180, t1136, t1359) and is a sanctioned shadow agent. `concern-format.md`
already records that Codex's markdown renderer hard-wraps long rows (the t1167
split-marker recovery exists for it) but nowhere records that the same renderer
**replaces the list-marker glyph** — the more fundamental breakage.

## Fix direction (to be settled in planning, not prescribed here)

The cheap consumer-side option is to widen the three patterns to accept the
renderer's bullet glyph(s) alongside `- `. Two facts that make this attractive:

- The **collision-hardening invariant survives**: a soft-wrap or agent-hardwrap
  continuation row never begins `• [` either, because the renderer emits the
  bullet only at a list-item start. Widening to a closed set of
  list-marker glyphs does not weaken the guarantee the format rests on.
- It is **downstream-free**: `build_clipboard_payload` re-renders every forwarded
  concern canonically as `- [priority | region] body` from parsed fields
  (`concern_parser.py` ~line 916), so what reaches the followed agent is
  unchanged. `concern_block_signature` reads a raw non-joined capture and is
  likewise unaffected by the glyph.

A producer-side alternative (emit the block so the renderer cannot touch it) and
the question of which other agent TUIs rewrite markers (opencode, agy) should be
weighed in planning. Whatever is chosen, the **`_MARKER_START` blindness must be
fixed too** — otherwise the next renderer that rewrites the glyph degrades
silently again instead of being reported.

## Also observed (adjacent, do not fix blind)

The Codex pane runs an alternate-screen TUI, so tmux keeps no scrollback for it:
`capture-pane -S -2000` returns only the ~61 visible rows. `--deep` buys nothing
on such a pane, and at 60 columns the visible window started mid-first-item, so
the block was additionally truncated and the pane's own chrome
(`New activity · ↓ Back to bottom · esc`) landed inside the captured block
region. This is a separate limitation from the glyph defect; record it, decide in
planning whether it belongs here or in its own task.

## Acceptance criteria

1. With a captured Codex shadow block whose items are `• [priority | region] body`,
   `parse_concerns()` returns one `Concern` per emitted item, with `priority`,
   `region` and `body` equal to those parsed from the same block written with
   `- ` markers.
2. `has_concern_block()` returns `True` for that same complete Codex-rendered
   block, so the auto-offer badges it.
3. For a block whose items are malformed *beyond* the glyph (bad bracket,
   unknown shape), `unrecovered_markers()` counts them regardless of which
   list-marker glyph they carry — i.e. the lost-line report fires for a
   bullet-marked malformed row, not only a dash-marked one.
4. `build_clipboard_payload()` output for concerns parsed from a Codex-rendered
   block is byte-identical to the output for the same concerns parsed from the
   dash-marked block (canonical `- ` re-render preserved).
5. A red proof exists for each of 1–3: each assertion observed failing against
   the pre-change parser and passing after, with the fixture holding the real
   captured bullet bytes (`E2 80 A2`), not a hand-typed hyphen.
6. `.claude/skills/aitask-shadow/concern-format.md` records the renderer
   glyph-rewrite fact beside the existing hard-wrap note, and states the closed
   set of accepted marker glyphs.
7. The existing concern-parser test suite
   (`tests/test_concern_parser.py`, `tests/test_minimonitor_concern_action.py`,
   `tests/test_monitor_concern_action.py`, `tests/test_concern_picker_modal.py`)
   passes unchanged apart from added cases.

## Files

- `.aitask-scripts/monitor/concern_parser.py` — the three marker patterns, `_scan_items`
- `.aitask-scripts/monitor/minimonitor_app.py` — `action_pick_concerns`, `_maybe_offer_concerns`
- `.claude/skills/aitask-shadow/concern-format.md` — the format's single source of truth
- `tests/test_concern_parser.py` and the three consumer test files above

Line numbers above are relative to tree `8dbed4ea4` (2026-10-05) — re-locate by
symbol, not by line, when picking this up.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-05T13:57:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-05T20:27:51Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-05T20:43:20Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:f48ae3d641bc0a11

> **✅ gate:risk_evaluated** run=2026-10-05T20:43:20Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1892/risk_evaluated_2026-10-05T20:43:20Z-risk_evaluated-a1.log`
