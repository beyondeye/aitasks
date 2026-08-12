---
Task: t1498_live_recheck_round_positive_control.md
Base branch: main
plan_verified: []
---

# Plan: t1498 — Manual-verification auto-execution (live recheck-round positive control)

## Context

t1498 is the risk-mitigation "after" follow-up for t1493. t1493's **producer**
half is an LLM instruction — a Step 3 routing entry in
`.claude/skills/aitask-shadow/SKILL.md.j2` — whose only automated guard
(`tests/test_concern_parser.py::TestRouterRoutesRechecks`) proves the routing
*text* exists, never that a live shadow *obeys* it. This run drove a real
multi-pane session end to end to settle that.

Auto-verification was run autonomously (Step 1.5, autonomous strategy) before
the interactive loop; all 10 items reached a terminal state, so the interactive
loop had nothing left to ask.

## Live fixtures used

Two, both on the framework tmux socket (`-L ait`), session `aitasks`.

**Fixture A — the real pairing (item 1).** Window `aitasks:8`, the session this
verification itself ran in: followed pane `%270` = a genuine **Claude Code
(opus5)** agent, companion minimonitor `%271`. Pressing `e` spawned `%272`
running `codex -m gpt-5.6-terra $aitask-shadow %270 1498`. This reproduces the
task's preferred pairing — a **Codex shadow of a Claude pane** — which is the
configuration the original defect was seen in (`ait codeagent resolve shadow`
→ `codex/gpt5_6_terra`).

**Fixture B — the controlled fixture (items 3–10).** Window `aitasks:9`
(`agent-pick-1498`, 200x55), created because fixture A's followed pane is *this
agent*, which emits output continuously and therefore can never satisfy item
3's precondition ("the block is genuinely current"). Fixture B's followed pane
`%273` is a quiet shell displaying a deliberately flawed implementation plan,
so its last-change time is under test control. `classify_pane` categorises a
pane as AGENT purely on the `agent-` window-name prefix
(`monitor_core.py:1667-1670`) and the shadow only ever reads *captured text*,
so the mechanism under test is identical. Companion minimonitor `%276`, shadow
`%277` (again codex/gpt-5.6-terra, `@aitask_shadow_target=%273`).

Fixture B also supplied the deterministic synchronisation point that the
shadow's own round-1 review asked for (see "Shadow critique adopted" below).

## Execution Log

### Item 1 — bind a shadow via `e`
- Item text: Bind a shadow to a followed agent (`e` in `ait minimonitor`), recording the pairing.
- Approach: TUI interaction on the live server.
- Action run: `tmux -L ait send-keys -t %271 e`
- Output (trimmed): new pane `%272`, `pane_current_command=node`;
  `ps` → `codex -m gpt-5.6-terra $aitask-shadow %270 1498`;
  `show-options -p -t %272 -v @aitask_shadow_target` → `%270`.
- Verdict: **pass** — pairing recorded: Codex `gpt-5.6-terra` shadow of a
  Claude Code (opus5) followed pane.

### Item 2 — plan review emits `Round: 1 @ <ISO>`
- Approach: TUI interaction (fixture A).
- Action run: `send-keys -l 'poke holes in this plan'` + `Enter` into `%272`.
- Output (trimmed): shadow read `plan-challenge.md`, then emitted a fenced
  block whose first inner line was `Round: 1 @ 2026-08-12T14:09:06Z`, 3
  concerns, closed by `===END-CONCERNS===`.
- Verdict: **pass**.

### Item 3 — picker current, no stale banner
- Approach: TUI interaction (fixture B). Round 1 there was
  `Round: 1 @ 2026-08-12T14:13:12Z` with 6 concerns; `%273` last changed
  ~14:11, i.e. **before** the block, so the block is genuinely current.
- Action run: `send-keys -t %276 c`, then `capture-pane -p -t %276`.
- Output (trimmed): `Concerns` / `6 concern(s) · forward or reject ·
  round 1, 14:13:12Z` + all six rows. `grep -c '⚠'` → `0`; no
  `stale` / `moved on` / `cannot tell` text anywhere in the modal.
- Verdict: **pass**.

### Item 4 — advance the followed pane's last-change
- Action run: `send-keys -t %273 -l "echo '>>> AGENT PROGRESS ...'; date -u"` at
  `14:14:43Z`.
- Output (trimmed): pane shows the progress line and
  `Wed Aug 12 02:14:43 PM UTC 2026` — last-change now past `reviewed_at`
  (14:13:12Z).
- Verdict: **pass**.

### Item 5 — stale banner before any recheck
- Approach: TUI interaction + headless probe of the real `MiniMonitorApp`.
- Action run: `send-keys -t %276 c`; `capture-pane -pe -t %276`.
- Output (trimmed) — picker half, **as specified**:
  `⚠ These concerns may be stale — the agent has moved on — round 1 was
  produced 1m33s before the agent's latest change`, rendered `[1m]` bold in
  `38;2;185;60;91` (the `$error` red). It names the round *and* the lag.
- Output — `#mini-shadow-stale` half: **no banner, in any state**. Neither
  minimonitor pane (`%271`, `%276`) ever showed a `⚠`, and the unconditional
  session-bar text was equally absent.
- Root cause (localised): `MiniMonitorApp.compose` docks **three** siblings to
  the same edge — `#mini-session-bar`, `#mini-shadow-stale`, `#mini-own-agent`
  (`minimonitor_app.py:470-474`, CSS `:275-299`). Under Textual 8.2.7 sibling
  widgets docked to one edge do not stack: all three receive the identical
  `Region(0,0,W,1)` and only the **last in DOM order** composites. A minimal
  three-`dock: top` Textual app reproduces it exactly (`y=0` renders `'CCC'`
  only). So the banner's *state machine* is correct and its *surface* is dead.
  Not a t1493 regression — t1493 added a signal to an already-invisible widget.
- Verdict: **fail** → follow-up **t1499** (high / low effort).

### Item 6 — send the canonical phrase verbatim
- Action run: `send-keys -t %277 -l 'refetch and recheck round 2'` + `Enter`
  at `14:21:54Z` (`-l` = literal, so no shell or key-name mangling).
- Verdict: **pass**.

### Item 7 — recheck re-enters the sub-procedure (**the task's core question**)
- Output (trimmed): shadow announced *"running a fresh round-2 plan challenge
  from the agent's latest screen and will emit a new concern block even if the
  findings are unchanged"*; ran `aitask_shadow_capture.sh --deep` (re-resolved
  `%273`), re-ran the challenge, printed *"Round 2 reran the plan challenge"*,
  and emitted a **new** fenced block `Round: 2 @ 2026-08-12T14:22:08Z` —
  strictly newer than round 1's `14:13:12Z`.
- Verdict: **pass**. The FAIL condition (a prose-only answer with no fences)
  did not occur.

### Item 9 — picker current again after round 2
- Action run: `send-keys -t %276 c`.
- Output (trimmed): `6 concern(s) · forward or reject · round 2, 14:22:08Z`;
  `grep -c '⚠'` → `0`, no stale text.
- Verdict: **pass**. Run before item 8 on purpose, so the assertion happens
  while `%273` is still untouched since 14:14:43Z. Together with item 5 this
  pins the banner in **both** directions inside one live session
  (stale → cleared).

### Item 8 — clean round still emits
- Approach: the plan's own wording ("if round 2 finds nothing") is not
  arrangeable against a live adversarial reviewer — round 2, and a round 3
  against a hand-written "clean" plan, both found real concerns. Used the other
  documented clean route instead: `concern-format.md` defines a clean round as
  "zero concerns **or whose concerns were all suppressed**".
- Action run: rejected all 4 round-3 concerns through the picker's real `r`
  key (persisted as `r1`–`r4`, `producer: picker`, verified via
  `aitask_shadow_rejected.sh list 1498`), then
  `send-keys -t %277 -l 'refetch and recheck round 4'`.
- Output (trimmed): prose `Suppressed 4 previously-rejected concern(s).`, then
  exactly:
  `===AITASK-CONCERNS===` / `Round: 4 @ 2026-08-12T14:25:55Z` /
  `===END-CONCERNS===` — two fences, header only. Pressing `c` toasted
  verbatim `Clean review (round 4) — no concerns`.
- Verdict: **pass** (producer and consumer halves both).

### Item 10 — negative control on the wording
- Action run: restored the flawed plan to `%273` (so a routed round has real
  work to find), then `send-keys -t %277 -l 'look again'` — non-canonical, and
  naming **no** round, so the shadow had to self-count.
- Output (trimmed): *"'Look again' routes to a full recheck. I'm rerunning the
  plan challenge as round 5 and will produce a fresh block."*; ran
  `aitask_shadow_capture.sh --deep`; emitted
  `Round: 5 @ 2026-08-12T14:27:12Z` with 6 concerns, later than round 4's
  `14:25:55Z`.
- Verdict: **pass**. Oracle was a *fresh round header with a later timestamp*,
  not the announcement — see below.

## Shadow critique adopted

The round-1 review in fixture B raised three concerns about this very
checklist. All three were acted on rather than noted:

1. *Clean-round coverage is unarrangeable as written* — round 2 reviews the
   same plan and will repeat its findings, leaving the metadata-only path
   untested. → Item 8 switched to the suppression route.
2. *The negative control has no fresh success oracle* — with round 2 already on
   the pane, "look again" could return prose and still look complete. → Item 10
   required a new `Round: 5` header with a later ISO timestamp **plus** an
   observed `--deep` refetch.
3. *The stale assertion races minimonitor's snapshot propagation.* → Item 4/5
   were separated by an explicit wait, and item 9 was executed before item 8 so
   the "current again" assertion runs against an untouched followed pane.

## Outcome

Rounds 1–5 all produced fenced blocks with monotonically increasing round
numbers and timestamps. **The producer half of t1493 is confirmed working
live**, in the Codex-shadow-of-Claude pairing the original defect was seen in,
for the canonical phrase, for an externally-named round, for a self-counted
round, and for a clean round.

One defect found, in the consumer half's live surface: **t1499**.

## Cleanup

- Fixture B window `aitasks:9` (panes `%273`, `%276`, `%277`) — killed.
- Fixture A shadow pane `%272` — killed (`%270`/`%271` are the live session and
  were left running).
- Scratch dir
  `/tmp/claude-1000/-home-ddt-Work-aitasks/<session>/scratchpad/t1498/`
  (fixture plans + Textual dock probes) — session-scoped, not in the repo.
- `aitask_shadow_rejected.sh` entries `r1`–`r4` for task 1498 — removed, since
  they were fabricated for item 8 rather than being real user rejections.
