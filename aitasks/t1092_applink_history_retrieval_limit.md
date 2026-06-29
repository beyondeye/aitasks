---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: [applink, applink_dataplane]
gates: [risk_evaluated]
created_at: 2026-06-29 09:23
updated_at: 2026-06-29 09:23
---

Investigate (and relax where safe) the limit on how much terminal history the
applink "history" RPC can retrieve from the server. The history RPC landed
recently and works; this task verifies *why* retrieval is bounded and whether
the bound can be raised, treating the whole constraint chain — not just one
constant — as the subject.

## Background
The mobile companion (aitasks_mobile) fetches scrollback by sending a `history`
verb (pane_id, before_line, count); the server returns a history keyframe of
negative-row_id lines that the client merges above row 0.

## Coupled constraints to investigate (full chain)
1. **Request cap — `_MAX_HISTORY_ROWS = 1000`** in
   `.aitask-scripts/applink/router.py:43`, enforced at `router.py:378-379`
   (`count > 1000` → `BAD_PAYLOAD`). Single hardcoded constant; not negotiated
   or versioned. Landed with t1007 data-plane resource limits.
2. **Effective ceiling — tmux capture/scrollback depth (~200 lines).** Per
   `aidocs/applink/content_transport.md:220`, the server only retains roughly
   ~200 lines via `capture-pane -S -<capture_lines>`; a `before_line` past that
   buffer yields an **empty** history keyframe. This is very likely the *real*
   limiter the user is hitting — raising `_MAX_HISTORY_ROWS` alone would not
   increase retrievable history if capture depth stays ~200. Locate where
   `capture_lines` / the `-S` depth is set and whether it is configurable.
3. **Frame-size coupling — `MAX_PUSH_FRAME_BYTES = 2 MiB`** (`pusher.py:57`). A
   history keyframe exceeding this is dropped + audited (not sent), while the
   client already received an acceptance token (best-effort by design,
   `content_transport.md:212`). Any relaxation must keep a max-count, max-width
   keyframe comfortably under 2 MiB. Estimate the realistic encoded size of a
   dense N-row keyframe.

## Relevant code / handlers
- RPC verb `"history"` — router.py:75,374 (`IMPLEMENTED_COMMAND_VERBS`)
- `FrameRouter.handle()` — router.py:374-395 (validates count)
- `PushScheduler._drain_history()` — pusher.py:163-198 (encodes/sends)
- `content.history_rows()` — content.py:409-449 (negative row_ids)
- `Subscription.request_history()` — content.py:620-637 (per-pane coalescing)
- Docs: `aidocs/applink/security.md` (frame-size guard rationale),
  `aidocs/applink/content_transport.md` (count cap + ~200-line retention),
  `aidocs/applink/protocol.md`.
- Test: `tests/test_applink_router.sh:378-379` (history count>max → BAD_PAYLOAD).

## Acceptance criteria
- Document, in the task/plan, the authoritative reason for each of the three
  constraints above and which one actually bounds the user's retrievable
  history in practice.
- Decide and justify whether to raise `_MAX_HISTORY_ROWS` and/or the tmux
  capture depth, and to what value, with the 2 MiB frame ceiling respected
  (include a size estimate). If a limit is raised, update the enforcing
  constant(s), the security/transport docs that cite the value, and the
  router test that asserts the cap.
- If the conclusion is "do not relax" (e.g. genuine DoS/decode-bomb risk),
  record that decision explicitly with rationale rather than silently leaving
  it. No silent acceptance-criteria deviation.
- Note any negotiation/per-session-override design as an explicit out-of-scope
  follow-up if not implemented here.

## Related
- t1088 (applink history coordinate-verify) — manual verification of the
  just-landed history RPC; coordinate so this investigation does not conflict.
- Paired follow-up in aitasks_mobile: add a loading indicator while the history
  RPC is in flight (tracked as a separate cross-repo task).
