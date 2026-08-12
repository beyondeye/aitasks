---
priority: high
effort: medium
depends: []
issue_type: manual_verification
status: Ready
labels: [shadow, aitask_monitormini, tui]
anchor: 1159
followup_kind: risk_mitigation
created_at: 2026-08-12 16:41
updated_at: 2026-08-12 16:41
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

- [ ] Bind a shadow to a followed agent (`e` in `ait minimonitor`). Record which
      code agent each side is running — the original defect was seen with a
      **Codex** shadow of a Claude pane, so prefer reproducing that pairing;
      note the pairing used either way.
- [ ] Ask the shadow for a plan review (e.g. "poke holes in this plan"). Confirm
      a fenced block appears with a `Round: 1 @ <ISO-8601 UTC>` header.
- [ ] Press `c` in minimonitor. Confirm the picker opens with the round-1
      concerns and **no** stale banner (the block is genuinely current).
- [ ] Let the followed agent produce new output, so its last-change advances
      past the block's `reviewed_at`.
- [ ] **Before** sending any recheck: press `c` again. Confirm the picker now
      shows the red stale banner, and that it names the round and how far the
      block predates the change. Confirm `#mini-shadow-stale` also warns.
- [ ] Send the canonical phrase into the SHADOW pane, verbatim:
      `refetch and recheck round 2`
- [ ] Confirm the shadow **re-enters the review sub-procedure** rather than
      answering conversationally: it should refetch, re-run the review, and emit
      a **new fenced block** whose header reads `Round: 2 @ <newer ISO-8601>`.
      A prose-only answer with no fences is the defect and must be recorded as a
      FAIL with the pane capture attached.
- [ ] Confirm a **clean** recheck also emits: if round 2 finds nothing, it must
      still emit the metadata-only block (two fences, header only) and
      minimonitor must toast `Clean review (round 2) — no concerns`.
- [ ] After round 2 lands, press `c`. Confirm the picker shows round 2's
      concerns and reports them **current** again (banner cleared).
- [ ] Negative-control the wording: try one non-canonical phrasing from the
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
