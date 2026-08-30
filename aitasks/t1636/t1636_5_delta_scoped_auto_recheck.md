---
priority: high
effort: high
depends: [t1636_4]
issue_type: enhancement
status: Ready
labels: [shadow, aitask_monitormini, concern_format]
gates: [risk_evaluated]
anchor: 1636
created_at: 2026-08-30 14:54
updated_at: 2026-08-30 14:54
---

## Context

Part of t1636 (shadow concern impact-vector model) — the convergence child.
`review_loop.compose_recheck_prompt` (`.aitask-scripts/monitor/review_loop.py:1242`)
injects "re-run the review sub-procedure end to end" every round, so each round
is a fresh unbounded search; reviews have been observed not to converge after
10 rounds. This child makes recheck rounds DELTA-SCOPED so the loop converges
by construction. Depends on t1636_3 (it extends the producers' re-review entry)
AND t1636_4 (it edits `monitor_shared.py`, which _4 also touches). Parent plan:
`aiplans/p1636_shadow_concern_impact_vector_model.md` — the t1636_5 section is
the binding spec; the highlights below are a summary, the plan text governs.

## The delta contract (from the parent plan — binding)

- Unresolved/regressed prior concerns are RE-EMITTED as ordinary items, body
  opening on status (`Unresolved from round <N-1>: …` / `Regressed: …`) — the
  block is never metadata-only while anything actionable is outstanding
  (`is_metadata_only_block` would certify a false clean otherwise).
- Resolved prior concerns are named in prose, not re-emitted.
- New concerns carry their TRUE rubric disposition — NEVER relabeled for
  control flow ("informational is never a parking slot",
  impl-review-angles.md:238). Convergence comes from SCOPE: a delta round
  hunts only prior-status + new obligation-touching concerns; the scope is
  machine-readable (`| scope: delta` in the round header) and one incidentally
  noticed non-obligation finding is still emitted with its true disposition.
- Clean (delta) = identity-verified round record consulted + all prior
  actionable resolved + scoped search found nothing new. Fail-safe: an
  unavailable/mismatched record forces a FULL review, no `scope: delta`
  token, and never a metadata-only block.

## Key Files to Modify

- `.aitask-scripts/monitor/review_loop.py` — `compose_recheck_prompt` states
  the delta contract and names the record identity (not "end to end").
- `.aitask-scripts/monitor/minimonitor_app.py` (~4041-4051, the fire path) —
  persist the prior-round record at fire time from the authoritative -J
  capture; asyncio subprocess seam with a BOUNDED timeout (a sync helper
  waiting on the registry mutex would freeze the TUI); timeout/LOCK_BUSY →
  fire with no record named (fail-safe full review, never a frozen UI).
  Head-truncated/incomplete capture → NO record written.
- NEW helper (e.g. `.aitask-scripts/aitask_shadow_round_record.sh`) — modeled
  on `aitask_shadow_rejected.sh` INCLUDING its write discipline:
  `lib/registry_lock.sh` mutex around the RMW AND
  `lib/atomic_write.sh` `ait_atomic_render` for the landing write ("Never an
  open-coded mktemp-then-mv", aitask_shadow_rejected.sh:41). Items-only —
  never a fence. Record at `.aitask-shadow/<task_id>/prior_round.md` carries
  `round`, `reviewed_at`, and a digest of the wrap-joined block region:
  IDENTITY-BOUND per the t1448 pair contract (concern_parser.py:219 — round
  alone aliases across restarted shadows / second monitors). Reader contract:
  identity-matching record / `NO_RECORD` / anything else (mismatch, malformed)
  = "could not consult". One file + verify-on-read (per-identity files would
  accumulate unboundedly). Wire archival pruning like the rejected store.
- `.aitask-scripts/monitor/concern_parser.py` — `_META_LINE` gains optional
  `| scope: delta`; `BlockMeta.scope: str = ""`. Two-field compatibility
  contract (binding, from the parent plan): legacy headers parse to unchanged
  round/reviewed_at with scope ""; two-arg construction preserved;
  `parse_reviewed_at_epoch` tested on scoped headers (scope group must never
  leak into the timestamp — the strict round-trip would silently return None);
  t1448 key stays the (round, reviewed_at) attribute pair; whole-tuple
  identity documented as NOT backward compatible.
- `.aitask-scripts/monitor/monitor_shared.py` — CENTRALIZED scope-aware
  labeling: one shared `clean_round_msg(meta)` replacing the duplicated
  literals at `monitor_app.py:3099` and `minimonitor_app.py:4245` (scope
  delta → "Clean delta review (round N) — prior concerns resolved, no new
  obligation concerns"); `format_block_meta` (line 2914) gains the scope in
  its suffix so picker context + toasts carry it.
- Producers (four docs) — the re-review entry adopts the delta contract +
  record reader + fail-safe, two-placement discipline, producer-rule guard.
- `.claude/skills/aitask-shadow/concern-format.md` — document the scope token
  and the round record.

## Verification (binding — from the parent plan's Verification section)

- Helper tests (mirror `tests/test_shadow_rejected.sh`): malformed record;
  truncated/fence-bearing input refused; failed/partial write leaves no record
  (`ait_atomic_render` refusal paths); concurrent writer → LOCK_BUSY (exit 3)
  nothing written; identity fields round-tripped exactly.
- Delivery tests: record written with the identity of the very block parsed;
  prompt names that identity; head-truncated capture writes NO record; helper
  timeout/LOCK_BUSY at fire time still fires with no record named and never
  blocks the event loop (fail-safe path, not an error).
- Surface tests: both apps' metadata-only messages, picker context line, and
  toast each show the scoped wording for a `scope: delta` block.
- The invariant end-to-end: an unavailable/mismatched/missing record forces a
  full review and can NEVER certify a clean round; negative control — a
  producer-doc mutation dropping the fail-safe rule trips the producer guard.
- `bash tests/run_all_python_tests.sh --test-dir tests` — read only the last
  line. `./.aitask-scripts/aitask_skill_verify.sh` for the doc changes.
