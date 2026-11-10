---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [monitor, tmux]
gates: [risk_evaluated]
anchor: 2175
followup_kind: upstream_defect
created_at: 2026-11-10 12:42
updated_at: 2026-11-10 12:42
---

## Origin

Spawned from t2211_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/minimonitor_app.py:6011-6170` — `_submit_shadow_prompt`
  authorises each recheck Enter on `SHADOW_BUSY` alone. It never proves that the shadow
  composer holds exactly the recheck prompt, so text a user appended (or a draft typed
  after a submit that read BUSY) would be submitted. This is the same hazard class as the
  t2211_4 plan-review finding.

## Diagnostic context

t2211_4 built guarded request delivery from the sitrep TUI into the sitrep agent
(`.aitask-scripts/monitor/agent_request_delivery.py`, committed e16e440e4). Two
plan/implementation-review findings there apply equally to the minimonitor's
review-loop delivery into the SHADOW pane:

1. `shadow_state == SHADOW_BUSY` only says the composer holds SOME typed text. A search
   of the capture for "our" text cannot tell the composer from the transcript either.
   That design accepted (a) the request with user text appended, and (b) on a retry, the
   request echoed in history beside a foreign draft, so the retry Enter would submit the
   user's draft.
2. A BUSY read AFTER an Enter is a swallowed Enter only when the composer still holds
   exactly the text that was sent. Otherwise the text may already have been submitted,
   and reporting "not submitted" (or retrying) invites a duplicate.

The minimonitor path (`_fire_shadow_recheck` L5910-6009 writes the prompt with
`send_keys(..., literal=True)`; `_submit_shadow_prompt` L6011-6170 sends Enter):

- before each Enter it requires `before == SHADOW_BUSY` plus the t2001 mode gate, never
  that the BUSY composer holds exactly `prompt`;
- after an Enter, a BUSY read always `continue`s to a retry Enter, so a user typing into
  the shadow right after a real submit gets their draft submitted by the retry.

## Suggested fix

Reuse t2211_4's per-agent composer reader and matcher. Before every Enter (retries
included), require `payload_matches(review_loop.composer_payload(tail, agent, pane_width),
prompt)`. Treat a BUSY post-Enter read whose payload differs as "unverified" (hold or
warn), never as a swallowed Enter. The reader is
`review_loop.composer_payload` / `PAYLOAD_GRAMMAR_AGENTS`, and the matcher is
`agent_request_delivery.payload_matches`; both are measured and pinned by
`tests/sitrep_request_fixtures.py`. Mind that the recheck prompt is multi-word and may
wrap: `payload_matches` already handles justified wraps. Also check the prompt is single
spaced and one line (`agent_request_delivery.request_line_error`).

Coordinate with the `shared_agent_submit_helper` risk-mitigation follow-up of t2211_4,
which extracts one shared submit helper for both paths. Whichever lands first should
carry the payload proof, and the other should consume it instead of duplicating it.

Regression tests:
- a shadow composer holding the prompt plus appended user text gets no Enter;
- a BUSY post-Enter read showing a foreign draft gets no retry Enter;
- a pre-fix control showing the BUSY-only check accepting both.
