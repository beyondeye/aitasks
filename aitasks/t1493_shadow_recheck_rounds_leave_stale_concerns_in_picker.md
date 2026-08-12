---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [shadow, aitask_monitormini, tui]
gates: [risk_evaluated]
anchor: 1159
created_at: 2026-08-12 10:47
updated_at: 2026-08-12 10:47
---

After the shadow's first review round, later "refetch and recheck" rounds stop
emitting a concern block, so minimonitor's `c` picker keeps re-offering the FIRST
round's concerns — and shows them as **current**, because the staleness signal is
keyed on when the shadow last *looked*, not on when the block was *produced*.
Two independent defects, one visible symptom.

Coordinate with **t1159** (shadow review-loop automation): t1159_1 fixes only one
half of the producer defect, and t1159_2's automation makes the other half a
livelock. See "Coordination" below.

## Symptom, observed live (2026-08-11)

tmux session `thinking_back`, window `agent-pick-45_9`, repo
`/home/ddt/Work/thinking_backend`. Followed agent: Claude in pane `%178`; shadow:
**Codex CLI (gpt-5.6-terra)** in pane `%183`, bound via `@aitask_shadow_target`.

Ground truth from `tmux capture-pane -p -J -S -2000 -t %183` (1191 lines):

- Exactly **one** concern block in the whole scrollback — opening fence at line
  948, closing fence at line 1007 (an early plan-challenge round).
- After it, **three** `refetch and recheck` rounds ran. Each visibly re-entered
  the skill (`aitask_skill_resolve_profile.sh shadow` → `aitask_skill_render.sh
  aitask-shadow --profile default --agent codex` → `aitask_shadow_capture.sh`)
  and each answered in **prose only** — no fences, no items.
- One of those prose rounds carried a **real, new, actionable concern**: *"A
  too-broad CIDR such as 0.0.0.0/1 is not literally 0.0.0.0/0 but is effectively
  broad exposure. Require /32 IPv4 and /128 IPv6 by default … I'd approve the
  plan after adding the CIDR-specificity rule."* It never reached the picker.
- Pressing `c` therefore forwards the round-1 items, with **no** stale banner —
  each refetch had restamped `@aitask_shadow_analyzed_at` (`%183` =
  `1786458122`), clearing staleness.

## Defect 1 — the producer stops emitting the block after round 1

Two distinct causes, both in the Claude-tree shadow skill (the `.agents/` and
`.opencode/` trees carry only a `SKILL.md` wrapper, so a Codex shadow reads these
same files):

1. **Clean rounds emit nothing.** Every producer says *"Emit the block **only
   when you have at least one concern**. If the plan is genuinely clean, omit the
   block entirely"* (installed copy: `plan-challenge.md:100-101`,
   `impl-challenge.md:426-427`). Because `concern_parser` is **last-block-wins**,
   omitting does not clear anything — the previous round's block stays the newest
   one in the pane.
2. **Recheck rounds are unrouted.** `SKILL.md.j2` Step 3 ("Serve the request",
   lines 212-284) routes on the user's ask — "poke holes", "stress-test this",
   "review the implementation", … — and has **no entry at all** for a
   re-review / recheck / "look again after the plan changed" ask. `grep -in
   "recheck\|re-entry\|subsequent"` over `SKILL.md.j2` and every sub-procedure
   returns nothing. A recheck therefore reads as a conversational follow-up to
   the previous analysis, and the agent answers in prose without re-running the
   sub-procedure's emit step. This is what the live session shows, and it loses
   *new* concerns, not just clean-round bookkeeping.

## Defect 2 — "fresh" is keyed on the shadow's read stamp, not on the block

`compute_shadow_staleness` (`monitor_core.py:507-576`) compares the shadow pane's
`@aitask_shadow_analyzed_at` against `get_last_change_wall(followed_pane)`:
`return (last_change > analyzed_at + eps), analyzed_at` (`:576`). The stamp is
written by `aitask_shadow_capture.sh:344-355`, called **unconditionally after
every capture** (`main()`, `:420-422`) — `--deep` only widens the capture depth.

So a "refetch" restamps `analyzed_at` and the block's own age is never consulted:
staleness answers *"did the shadow look recently?"*, never *"was this block
produced by that look?"*. The user's phrasing: the recheck pass **refreshed** the
old concerns without **substituting** them.

Confirmed absent: **nothing anywhere converts `BlockMeta.reviewed_at` to a
time.** There is no `fromisoformat` / `strptime` under `.aitask-scripts/monitor/`.
All consumers of `parse_block_meta` are string-level — the dedup key
(`minimonitor_app.py:2362-2374`), the clean-round / "(round N)" toasts
(`:2251-2258`, `:2375`), the modal kwarg (`:2279`), and the display suffix
`format_block_meta` (`monitor_shared.py:2165-2181`, rendered by `_context_line()`
at `:2545`). `get_last_change_wall` has exactly **one** caller in the tree:
`compute_shadow_staleness`.

Related, on the same surface: minimonitor's `c` path reuses the tick-cached
`_shadow_feedback_stale` and collapses the tri-state `None` → `False`
(`minimonitor_app.py:2262-2264`), so "cannot tell" renders as "not stale". The
same collapse in `monitor_app.py:2926` / `:1118` is already recorded in
**t1461** — do not duplicate it; decide there or here, once.

## Coordination — t1159 (parent), and why this is not already fixed

**t1159_1** (`round_metadata_concern_block`, status `Implementing`, uncommitted
in the working tree at exploration time) adds the `Round: <N> @ <ts>` header, a
`BlockMeta` / `parse_block_meta` accessor, the dedup lift and the picker's round
display — and rewrites the producers to emit a **metadata-only block on a clean
round** (`plan-challenge.md`, both rule sites). That closes Defect 1 cause (1)
producer-side, and supplies the `(round, reviewed_at)` key this task needs.

It does **not** close:

- Defect 1 cause (2) — the router still has no recheck entry, so a recheck can
  still answer in prose and emit no block at all, clean or not.
- Defect 2 — no consumer-side freshness check exists; `reviewed_at` remains a
  display string.
- Any consumer-side defense for a producer that simply does not comply (older
  installs, other agents, a shadow that free-texts its way past the instruction).
  A prompt file is not an enforcement point.

**t1159_2** (`auto_recheck_loop`, `depends: [t1159_1]`) turns this into a
livelock rather than an annoyance: it injects *"refetch and recheck round N"* into
the shadow pane and derives `expected_round` from `parse_block_meta(prev
capture).round + 1`. If the recheck answers in prose, no new block ever appears —
the round never advances, and the loop keeps re-presenting round-1 concerns
indefinitely while the banner says they are current. **Land this task's producer
half before, or together with, t1159_2.**

Also observed and worth flagging to t1159_2 rather than fixing here: the live
shadow is **Codex**, while t1159_2's `SHADOW_READY_DETECTORS` ships `claude`-only,
so the loop would refuse to arm on exactly this setup.

Adjacent, deliberately **not** folded in:

- **t1448** (`shadow_concern_badge_currency`, `depends: [1159, 1420]`) — the `!`
  badge's clearing edge, keyed on workflow phase. Different surface, same family;
  keep the freshness rule this task lands in one place so t1448 can consume it.
- **t1461** (`monitor_tristate_and_sync_discovery_residue`) — owns the
  `bool(stale)` tri-state collapse bullet.

## Requirements

1. **A recheck round always re-emits the block.** Every review round the shadow
   runs — first, recheck, clean, or unchanged — produces a fenced block carrying
   that round's header. Route re-review asks explicitly in `SKILL.md.j2` Step 3
   (including the exact wording t1159_2 injects) so the emit step is re-entered
   rather than summarized conversationally.
2. **Consumer-side block-age freshness.** The picker and the auto-offer must be
   able to tell that the newest block predates the followed agent's current
   state, *independently of* `@aitask_shadow_analyzed_at`. The material now
   exists: parse `reviewed_at` to an epoch and compare against
   `get_last_change_wall(followed_pane)`.
3. **Tri-state discipline, fail-safe direction.** Unparseable / absent
   `reviewed_at` (every pre-t1159_1 block) ⇒ "cannot tell" ⇒ **preserve** the
   existing warning, never clear it. Never suppress a concern the user might
   still need; a false "stale" is cheaper than a false "current".
4. **Do not conflate the two signals.** `concern-format.md:328-337` and
   `shadow_agent.md:322-361` both state that block-content identity
   (`concern_block_signature`) and read-recency (`compute_shadow_staleness`) are
   different questions. Block **age** is a third. Whatever lands must name all
   three and say which surface uses which — update both docs.
5. Keep the shadow advisory-only: this task changes what the shadow *emits* and
   what minimonitor *displays*, never who drives the followed pane.

## Direction to assess at planning (not decided)

- Producer half: a routing entry + a per-round emit directive at both rule sites
  (the two-placement pattern `TestProducerRoundHeaderRule` /
  `TestProducerRejectionSuppressionRule` already guard) versus a lighter "state
  the round in every review answer" rule. Weigh against prompt-file drift: this
  is the third rule duplicated across four producers.
- Consumer half: whether block-age staleness *replaces* the read-stamp signal in
  the picker banner, ORs with it, or renders as a distinct message ("these
  concerns are from round 1, N minutes before the agent's last change"). Note
  the picker's banner is currently a bare boolean with no age
  (`monitor_shared.py:2565-2571`), while minimonitor's own `#mini-shadow-stale`
  banner does carry "analyzed Ns ago".
- Whether a metadata-only (clean) newest block should actively **clear** the
  picker rather than merely fail `has_concern_block` — i.e. can `c` still reach
  an older block through the forgiving `parse_concerns` path once a clean round
  has superseded it? Check `_last_block_region(require_close=False)` semantics
  against the observed capture window before deciding.
- Clock trust: `reviewed_at` is the shadow's own shell-sourced UTC (same host as
  the monitor), so a direct epoch comparison is sound — state that assumption
  explicitly rather than leaving it implicit.

## Verification pointers

- `tests/test_concern_parser.py` — the producer-text drift guards live here
  (`TestProducerShortRegionRule`, `TestProducerRejectionSuppressionRule`,
  `TestProducerRoundHeaderRule` from t1159_1); a per-round re-emit rule needs the
  same treatment, and the negative half (no producer retains "omit the block
  entirely" wording).
- `tests/test_minimonitor_concern_action.py` — `_FakeMon` + spy fixtures for the
  auto-offer / `c` path; drive a stale-block scenario: block at T0, followed pane
  changes at T1, shadow re-captures at T2 > T1 with no new block ⇒ must still
  report stale.
- `tests/test_concern_picker_modal.py` — banner/context-line rendering.
- Negative control required for requirement 3: a pre-header block (no
  `reviewed_at`) must not silently read as "current".
- `bash tests/run_all_python_tests.sh` — read only the final stderr verdict line.

## Out of scope

- The auto-recheck loop itself (t1159_2), the spin-off arm (t1159_3), the badge
  currency rule (t1448), and the tri-state residue sweep (t1461).
- Changing the concern-block grammar or the `[priority | region]` bracket (the
  t1167 split-marker drop hazard) — this task adds no marker fields.
- Porting to the `.agents/` / `.opencode/` shadow trees: the sub-procedures are
  shared `.md` files consumed through the shared root, so a port is likely a
  no-op — confirm, and only spawn follow-ups if those trees carry their own
  copies.
