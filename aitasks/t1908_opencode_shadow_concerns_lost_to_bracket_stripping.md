---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [shadow, aitask_monitormini, tui, opencode]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1892
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-06 23:18
updated_at: 2026-10-08 08:34
---

## Origin
Spawned from t1899 during Step 8b review.

## Upstream defect
- `.aitask-scripts/monitor/concern_parser.py:_MARKER_LIKE` — concern items from
  opencode shadows (1.18.34) are not parsed or forwarded.
  - Cause: opencode's markdown renderer strips the `[…]` brackets, so items
    render as `- p | r body`.
  - Effect: `parse_concerns` and `has_concern_block` find nothing, so the
    auto-offer never fires.
  - The report-only `_MARKER_LIKE` needs a `[`, so `unrecovered_markers` is
    blind to it too.
  - Only the manual `c` path warns (uncertified round, raw view).

## Diagnostic context
t1899 measured opencode 1.18.34 live, through the production shadow path:
- `ait codeagent invoke shadow`, bound with `@aitask_shadow_target`, given
  `>pc`, and captured with `aitask_shadow_capture.sh --deep --any-pane`;
- plus a controlled sample;
- each compared with the raw message text from `opencode export`.

**What survives.** The `-` glyph, `===AITASK-CONCERNS===`, the `Round:` header
and `===END-CONCERNS===`. The close fence gets +2 spaces of list-continuation
indent, which the parser tolerates.

**What breaks.** The renderer strips `[`/`]` from **every** bracket span, in
list items and in plain paragraphs alike.

| raw source | rendered |
|---|---|
| `- [medium \| Sample formatting] Step 1.6 requires …` | `- medium \| Sample formatting Step 1.6 requires an` |
| `- [high \| region one] First body.` | `- high \| region one First body.` |
| `- [low] Region-less body.` | `- low Region-less body.` |
| `Plain [bracket text] in a paragraph` | `Plain bracket text in a paragraph` |
| `\[escaped brackets\]` | `\[escaped brackets\]` (backslashes kept, so escaping does not help) |

**Parser result on the live capture.**

| call | result |
|---|---|
| `parse_concerns` | `[]` |
| `has_concern_block` | False |
| `unrecovered_markers` | `[]` |
| `parse_block_meta` | round 1 |
| `is_metadata_only_block` | False |

So the automatic paths (auto-offer, unparsed-marker warning) are silent. A
manual `c` in monitor or minimonitor reaches `uncertified_round_block_msg` and
the raw-block view, but nothing can be forwarded.

The measured facts are recorded in
`.claude/skills/aitask-shadow/concern-format.md`, "Measured renderers".

## Suggested fix
Two directions, not yet measured; a live opencode measurement must confirm
whichever is chosen.

1. **Producer-side encoding that survives opencode's renderer**, chosen per
   agent at shadow render time. Candidates (untested) are wrapping the whole
   block in an inline-safe construct, or a bracket glyph opencode does not
   treat as a link label.
2. **A consumer-side bracketless grammar**, accepted only for blocks that
   prove they were opencode-rendered. This must keep the collision guard: a
   bracketless `- p | r body` row is far easier to mistake for prose.

At minimum, `unrecovered_markers` (or a new diagnostic) should report
bracketless `- <priority> | …` rows, so the automatic paths stop being silent.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-08T05:34:50Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-08T09:27:14Z status=pass attempt=1 type=human
