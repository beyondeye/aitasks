---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: []
issue_type: documentation
status: Done
labels: [docs, web_site]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
followup_kind: docs_gap
implemented_with: claudecode/opus5
created_at: 2026-08-13 10:27
updated_at: 2026-08-13 11:49
completed_at: 2026-08-13 11:49
---

Documentation gaps found by /aitask-docs-gap for the release window v0.31.0..HEAD.
Each section below is self-contained and can become its own child task at
decomposition time.

46 tasks were analyzed: 17 documented, 19 not doc-relevant, 6 gaps.

## Gap: Board topic groups (t1243_8, t1243_9, t1243_10)

- **Target doc page(s):** `website/content/docs/tuis/board/how-to.md`,
  `website/content/docs/tuis/board/reference.md`,
  `website/content/docs/development/task-format.md`
- **What shipped:** A whole board grouping feature across three tasks.
  t1243_8 added the `boardgroup` frontmatter field (appended to `BOARD_KEYS`),
  a pure `lib/board_groups.py` with slug normalization, base-aware merge
  resolution for the field, and `--boardgroup` on `ait update` (update-only,
  reject-don't-coerce validation, `""` as a tombstone). t1243_9 added the
  `GroupHeader` focusable row, the focus-*unit* abstraction so arrow keys move
  over units rather than cards, single-member groups rendering as plain cards,
  collapsed groups rendering as the header alone, `x` toggling group collapse,
  and group-aware move dispatch. t1243_10 added the pure group-key algebra
  (`group_key` / `parse_group_key` / `remap_group_keys` / `column_remap`),
  collapse state persisted through `TaskManager.save_settings()` and remapped
  across column edit / delete / merge, orphan-collapse pruning on load, and
  per-group filter match counts on the header.
- **What to write:** The board pages currently do not mention groups at all —
  grep for `boardgroup` or "group" across `website/content/docs/` returns
  nothing board-related. `how-to.md` needs a "How to Group Tasks" section
  (what a group is, how `boardgroup` assigns membership, `x` to collapse and
  expand, how a collapsed group behaves during a filter pass and what the
  match count on the header means, that single-member groups render as plain
  cards). `reference.md` needs the `x` binding and the group-header row in its
  keybinding / anatomy tables. `development/task-format.md` needs a
  `boardgroup` row in the frontmatter field table — the file already gained a
  `followup_kind` row from t1468_1, so the table is the established home; note
  the update-only semantics and the `""` clearing form.
- **Sources:** `aiplans/archived/p1243/p1243_8_boardgroup_field_and_model.md`,
  `aiplans/archived/p1243/p1243_9_group_focus_and_rendering.md`,
  `aiplans/archived/p1243/p1243_10_group_collapse_and_filtering.md`;
  commits: 16afd191d, e7a071022, 0683e8791
- **PARTIAL — shipped half written here; rest owned by `t1243_13`.** Groups are
  half-shipped: t1243_8/9/10 landed, but `G`, group formation, block moves and
  in-board membership commands (t1243_11 / t1243_12) have not. t1504 documented
  only what shipped, and narrowed `t1243_13` accordingly. `boardgroup`'s
  non-website surfaces (seed, `AGENTS.md`, `CLAUDE.md`, `.codex` / `.opencode`
  mirrors) remain section B of `t1243_13`.

## Gap: Workflow-phase signal in the monitors (t1420, t1479)

- **Target doc page(s):** `website/content/docs/tuis/minimonitor/how-to.md`,
  `website/content/docs/tuis/minimonitor/_index.md`,
  `website/content/docs/tuis/monitor/how-to.md`,
  `website/content/docs/tuis/monitor/reference.md`
- **What shipped:** t1420 added the `lib/workflow_phase.py` seam — a
  `PhaseSignal` carrying phase / waiting / source / provenance, derived from an
  agent-neutral workflow-prompt table (Tier A), a per-agent native prompt map
  (Tier B), and the gate ledger's resume point. The phase is rendered on full-
  monitor agent cards, on minimonitor list rows, and in the docked followed-
  agent panel, and is stamped onto the shadow pane so the shadow skill can pick
  a default mode from it. t1479 then merged minimonitor's gate line and phase
  line into one width-budgeted row (`format_gate_phase_row`), with a label-free
  `render_phase_narrow` variant and per-cause UNKNOWN wording.
- **What to write:** Neither monitor page mentions a phase at all. The
  minimonitor `how-to.md` card-anatomy prose (around the "gate line" wording at
  line 49) needs updating to describe the merged gate+phase row, what each
  phase value means, and how the row degrades at narrow widths. The monitor
  pages need the phase on the agent card and in the docked panel. Explain what
  "waiting" means versus a phase name, and what an UNKNOWN phase indicates —
  it is a distinct "cannot tell" state, not "no phase".
- **Sources:** `aiplans/archived/p1420_advisory_workflow_phase_signal_for_shadow.md`,
  `aiplans/archived/p1479_merge_minimonitor_gates_and_phase_into_one_row.md`;
  commits: d8967df91, 876fbabf2

## Gap: Shadow auto-recheck loop (t1159_2)

- **Target doc page(s):** `website/content/docs/tuis/minimonitor/how-to.md`,
  `website/content/docs/workflows/shadow-agent.md`
- **What shipped:** A new minimonitor **L** binding arming a shadow auto-recheck
  loop, backed by a pure `monitor/review_loop.py` `ReviewLoopController`
  (DISARMED / WAITING / DELIVERING / FIRED). When armed, the loop watches the
  followed agent for classified work evidence, debounces over three ticks,
  honours a 45s cooldown that survives disarm and re-arm, waits for positive
  shadow-prompt readiness before delivering, and composes a recheck prompt whose
  round number is machine-derived from the previous block rather than guessed.
  Arming is refused with a message naming the shadow's agent when either side
  lacks the capability.
- **What to write:** `how-to.md` needs an "auto-recheck" section next to
  "How to Pick Shadow Concerns", plus an **L** row in the keybinding table
  (currently ends at `c`). Describe what arming does, that the loop only
  delivers when the shadow is idle and ready, that repeated deliveries are rate-
  limited, and when arming is refused. `workflows/shadow-agent.md` should cover
  it in the review-round narrative — the page already explains that every review
  round re-derives findings from scratch, which is the context this loop
  automates.
- **Sources:** `aiplans/archived/p1159/p1159_2_auto_recheck_loop.md`;
  commits: afd1c5b2f
- **DEFERRED — owned by `t1159_4`.** That sibling already scopes the minimonitor
  page, `aidocs/framework/shadow_agent.md` and the `L` / `t` key docs, and is
  blocked only on `t1159_3`. Writing it here would be rewritten within days.
  t1504 added the surfaces its file list was missing (the monitor pages and
  `workflows/shadow-agent.md`) to `t1159_4` instead.

## Gap: Concern-block round metadata (t1159_1, t1493)

- **Target doc page(s):** `website/content/docs/tuis/minimonitor/how-to.md`,
  `website/content/docs/tuis/monitor/how-to.md`,
  `website/content/docs/workflows/shadow-agent.md`
- **What shipped:** t1159_1 added a `Round: N @ <time>` header to every shadow
  concern block, parsed into `BlockMeta`. Minimonitor's dedup key became round-
  qualified so a fresh round re-offers, the toast gained a `(round N)` suffix,
  and the monitor learned to handle a clean round (an offer pass that clears the
  badge while retaining the signature). Blocks whose round header fails strict
  certification, or whose round value breaks the grammar, now warn and open the
  raw block inspect view in both `c` paths instead of reporting a false "no
  concerns" all-clear. t1493 then fixed recheck rounds leaving stale concerns in
  the picker.
- **What to write:** The docs describe the concern picker and the auto-offer
  toast in detail but say nothing about rounds beyond one passing mention of
  "later review rounds". Both monitor `how-to.md` pages need: what a round is
  and where the number comes from, that a new round re-offers concerns you have
  already seen, the `(round N)` toast suffix, and — importantly — that a block
  with an unusable round header warns and shows you the raw block rather than
  claiming there is nothing to pick. `workflows/shadow-agent.md` should tie the
  round number to the re-derive-from-scratch behavior it already documents.
- **Sources:** `aiplans/archived/p1159/p1159_1_round_metadata_concern_block.md`,
  the archived p1493 plan; commits: fabd8e615, 9397077f9
- **DEFERRED — owned by `t1159_4`**, together with gap 3 above (same pages, same
  owner). The monitor-side round prose and the `workflows/shadow-agent.md` tie-in
  were added to that task's key-files list by t1504.

## Gap: Follow-up-kind glyph on board cards (t1468_3)

- **Target doc page(s):** `website/content/docs/tuis/board/reference.md`
  (and the card-anatomy prose in `website/content/docs/tuis/board/how-to.md`)
- **What shipped:** A coloured glyph for the task's `followup_kind` on
  `TaskCard`, `InFlightTaskCard` and `TrailTaskCard`, plus a rollup of the
  member kinds on `GroupHeader`. `TrailGhostCard` deliberately carries no glyph.
  Unknown kinds render a distinct unknown glyph rather than being dropped.
- **What to write:** `followup_kind` reached the docs from its siblings —
  `development/task-format.md` has the field table row (t1468_1) and
  `commands/task-management.md` covers `ait ls` / pick surfacing (t1468_4) —
  but the board's own reference page never gained the glyph. Add the glyph to
  the card-anatomy / legend section: which kinds map to which glyph and colour,
  that the group header rolls up its members' kinds, and that a trail ghost card
  shows none.
- **Sources:** `aiplans/archived/p1468/p1468_3_board_card_followup_kind_glyph.md`;
  commits: d00e90e2e

## Gap: Gate skills missing from the skills reference (t635_23)

- **Target doc page(s):** `website/content/docs/skills/_index.md` plus new
  per-skill pages under `website/content/docs/skills/`
- **What shipped:** `aitask-run-gates`, `aitask-gate-template` and
  `aitask-gate-docs-updated` each gained their three wrapper surfaces
  (`.agents/skills/<skill>/SKILL.md`, `.opencode/skills/<skill>/SKILL.md`,
  `.opencode/commands/<skill>.md`), so all three are now available across every
  supported coding agent rather than in the Claude tree alone. The Claude-only
  prose was retired at its canonical sources.
- **What to write:** `website/content/docs/skills/` has a page for every other
  user-invocable skill but none for the gate skills, and `_index.md` does not
  list them. `commands/gates.md` documents the `ait gates` CLI, not the skills.
  Add reference pages for `/aitask-run-gates` (the conversational front of the
  gate orchestrator) and `/aitask-gate-docs-updated` (the `docs_updated`
  verifier procedure), list both in `_index.md`, and cross-link to
  `commands/gates.md`. `aitask-gate-template` is an authoring scaffold rather
  than a user command — decide whether it belongs on the site at all, and if so
  frame it for someone writing a new gate. Per the writing conventions, describe
  availability generically ("Claude Code and all other supported coding agents")
  rather than enumerating the agent trees.
- **Sources:** `aiplans/archived/p635/p635_23_port_gate_skills_codex_opencode.md`;
  commits: 75ca90438
- **PARTIAL — the two user-invocable skill pages written here.**
  `/aitask-run-gates` and `/aitask-gate-docs-updated` now have reference pages,
  listed under a new "Gates" category in `skills/_index.md` and cross-linked
  with `commands/gates.md`. **`aitask-gate-template` was deliberately left off
  the site**: it is an authoring scaffold with no invocation syntax, unlike
  every other documented skill. The wider gates docs sweep (concepts pages,
  workflow pages, the custom-gate authoring story) remains `t635_18`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-13T08:35:35Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-13T08:45:25Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-08-13T08:49:37Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:d09ade46c58b4950

> **✅ gate:risk_evaluated** run=2026-08-13T08:49:37Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1504/risk_evaluated_2026-08-13T08:49:37Z-risk_evaluated-a1.log`
