---
priority: high
effort: medium
depends: []
issue_type: manual_verification
status: Implementing
labels: [shadow, aitask_monitormini, tui]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-12 16:41
updated_at: 2026-08-12 17:28
---

## Origin

Risk-mitigation ("after") follow-up for t1493, created at Step 8d after implementation landed.

## Risk addressed

Goal-achievement risk, severity high: *the producer half is unverifiable by
automated test.* t1493's producer fix is a routing entry in
`.claude/skills/aitask-shadow/SKILL.md.j2` Step 3 — an **LLM instruction**. Its
drift guard (`tests/test_concern_parser.py::TestRouterRoutesRechecks`) proves
only that the routing text is present in the template and in the rendered
variant; nothing proves a live shadow *obeys* it. The observed defect was
precisely an agent choosing prose over the procedure, so text-presence is the
one thing that cannot settle it.

The consumer half (block-age staleness) is independently unit-tested and
delivers the user-visible goal even if the producer never complies — so this
verification is about confirming the *producer* half actually works, not about
whether stale concerns are flagged.

## Goal

Confirm live, in a real multi-pane session, that a recheck round now re-emits a
concern block, and that before it does the picker reports the previous round as
stale rather than current.

## Checklist

- [x] Bind a shadow to a followed agent (`e` in `ait minimonitor`). Record which — PASS 2026-08-12 17:08 auto: pressed 'e' in live minimonitor %271 (aitasks:8); shadow pane %272 spawned running 'codex -m gpt-5.6-terra $aitask-shadow %270 1498' with @aitask_shadow_target=%270. Pairing: Codex gpt-5.6-terra shadow of a Claude Code (opus5) followed pane -- the preferred reproduction pairing.
      code agent each side is running — the original defect was seen with a
      **Codex** shadow of a Claude pane, so prefer reproducing that pairing;
      note the pairing used either way.
- [x] Ask the shadow for a plan review (e.g. "poke holes in this plan"). Confirm — PASS 2026-08-12 17:10 auto: sent 'poke holes in this plan' to shadow pane %272; it routed to plan-challenge.md and emitted a fenced block, first inner line 'Round: 1 @ 2026-08-12T14:09:06Z', 3 concerns, closed with ===END-CONCERNS===.
      a fenced block appears with a `Round: 1 @ <ISO-8601 UTC>` header.
- [x] Press `c` in minimonitor. Confirm the picker opens with the round-1 — PASS 2026-08-12 17:14 auto: pressed 'c' in fixture minimonitor %276; picker opened 'Concerns / 6 concern(s) · forward or reject · round 1, 14:13:12Z' listing all 6 round-1 items. Zero warning glyphs and no stale/moved-on/cannot-tell text in the modal; live #mini-shadow-stale line was empty.
      concerns and **no** stale banner (the block is genuinely current).
- [x] Let the followed agent produce new output, so its last-change advances — PASS 2026-08-12 17:15 auto: sent an echo+date into followed pane %273 at 14:14:43Z; pane now shows '>>> AGENT PROGRESS ...' + 'Wed Aug 12 02:14:43 PM UTC 2026', i.e. last-change advanced past the round-1 block reviewed_at of 14:13:12Z.
      past the block's `reviewed_at`.
- [fail] **Before** sending any recheck: press `c` again. Confirm the picker now — FAIL 2026-08-12 17:21 follow-up t1499
      shows the red stale banner, and that it names the round and how far the
      block predates the change. Confirm `#mini-shadow-stale` also warns.
- [x] Send the canonical phrase into the SHADOW pane, verbatim: — PASS 2026-08-12 17:22 auto: sent the canonical phrase verbatim into SHADOW pane %277 at 14:21:54Z via 'tmux send-keys -l' (literal, no shell mangling): refetch and recheck round 2
      `refetch and recheck round 2`
- [x] Confirm the shadow **re-enters the review sub-procedure** rather than — PASS 2026-08-12 17:23 auto: shadow re-entered the review sub-procedure end-to-end -- ran aitask_shadow_capture.sh --deep (re-resolved %273), re-ran plan-challenge, printed 'Round 2 reran the plan challenge', and emitted a NEW fenced block 'Round: 2 @ 2026-08-12T14:22:08Z' (newer than round 1's 14:13:12Z). Not prose-only; two full blocks now on the pane.
      answering conversationally: it should refetch, re-run the review, and emit
      a **new fenced block** whose header reads `Round: 2 @ <newer ISO-8601>`.
      A prose-only answer with no fences is the defect and must be recorded as a
      FAIL with the pane capture attached.
- [x] Confirm a **clean** recheck also emits: if round 2 finds nothing, it must — PASS 2026-08-12 17:26 auto: forced a clean round via the documented suppression route -- rejected all 4 round-3 concerns through the picker's 'r' key (persisted to the rejection store as r1-r4), then sent 'refetch and recheck round 4'. Shadow printed 'Suppressed 4 previously-rejected concern(s).' and emitted a metadata-only block: exactly '===AITASK-CONCERNS===' / 'Round: 4 @ 2026-08-12T14:25:55Z' / '===END-CONCERNS==='. Pressing 'c' toasted verbatim 'Clean review (round 4) - no concerns'.
      still emit the metadata-only block (two fences, header only) and
      minimonitor must toast `Clean review (round 2) — no concerns`.
- [x] After round 2 lands, press `c`. Confirm the picker shows round 2's — PASS 2026-08-12 17:23 auto: after round 2 landed, pressed 'c' -> picker header 'round 2, 14:22:08Z' with round 2's 6 concerns; zero warning glyphs and no stale text. Banner cleared, so the stale->current transition is pinned in both directions within one live session (round 1 stale at 17:21, round 2 current at 17:24).
      concerns and reports them **current** again (banner cleared).
- [x] Negative-control the wording: try one non-canonical phrasing from the — PASS 2026-08-12 17:28 auto: negative control with non-canonical wording 'look again' (no round number named, so the shadow had to self-count). Shadow replied '"Look again" routes to a full recheck. I'm rerunning the plan challenge as round 5', ran aitask_shadow_capture.sh --deep (re-resolved %273), and emitted a full block 'Round: 5 @ 2026-08-12T14:27:12Z' with 6 concerns -- later timestamp than round 4's 14:25:55Z. Not prose-only.
      routing entry (e.g. "look again" or "is it fixed now") and confirm it also
      routes to a full round rather than prose.

## Notes

- The canonical injected phrase is pinned in
  `aidocs/framework/shadow_agent.md` ("Block age vs read recency") because
  t1159_2's `compose_recheck_prompt` must align with it. If this verification
  shows a different phrasing is needed, update that doc and t1159_2 together.
- t1159_2's `SHADOW_READY_DETECTORS` ships `claude`-only, so an automated
  recheck loop would refuse to arm on a Codex shadow. That is t1159_2's scope,
  not this task's — but it is why this verification is driven **by hand**.
