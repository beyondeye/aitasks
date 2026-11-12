---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation, web_site, doc_quality]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
followup_kind: upstream_defect
created_at: 2026-11-12 08:47
updated_at: 2026-11-12 09:04
---

## Origin

Spawned from t2258_3 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_create.sh:108`: the `--followup-of` help says
  "Flattened — never chains". But `resolve_anchor()` (line 246) anchors a
  follow-up of an anchorless child to the parent id, even when that parent has
  an anchor of its own.
- `.aitask-scripts/lib/gate_orchestrator.py:467`: `_force_one` dispatches a
  `kind: procedure` gate's verifier as a command. `resolve_verifier` then gives
  `aitask_gate_docs_updated.sh`, which does not exist, and an `error` is
  recorded. The unforced path defers the gate instead.
- `aidocs/framework/skill_authoring_conventions.md:4`: still describes
  `.gemini/` trees and four agents. `agent_runtime_guards_audit.md:27` does the
  same. The conventions doc also says the verify script renders every profile,
  but `aitask_skill_verify.sh` renders the default profile for three agents.
- `website/content/docs/development/task-format.md:47`: the `archived_reason`
  row names `ait archive --superseded/--obsolete`. There is no `ait archive`
  dispatcher verb; the flags belong to `.aitask-scripts/aitask_archive.sh`.
- `website/content/docs/workflows/crash-recovery.md:71`: says a session
  re-claiming its own lock refreshes it silently. But
  `aitask_pick_own.sh:782-806` still emits `RECLAIM_STATUS` for this session's
  own refreshed lock when the task is already `Implementing`, so a same-session
  re-pick is not silent. Not run end to end.

## Diagnostic context

All five were found while t2258_3 audited and restructured the concept pages:
facts moved to their owner pages were checked against the code.

- The anchor rule came from `concepts/topic-anchoring.md`. Its "never chains"
  claim was corrected on `commands/task-management.md`, but the
  `aitask_create.sh` help still makes it.
- The forced procedure gate was confirmed in the Step 8 user review. The
  concept page and `development/gates.md` now say that forcing a procedure gate
  records `error`, and that the attended workflow re-runs it. Resolving this
  bug would let those docs be simplified.
- The Gemini and verify-script descriptions came up when the skill-templating
  concept page was restructured. The site pages were fixed; the aidocs were
  not.
- The crash-recovery wording is a docs issue in the workflows section (audited
  by t2258_4), and the `ait archive` row belongs to task-format.

## Suggested fix

- Either make the create help match `resolve_anchor()`, or flatten
  `resolve_anchor()` and then fix the docs.
- Make a forced `kind: procedure` gate report "needs an agent" (deferred), as
  the unforced path does, instead of recording `error`.
- Update the two aidocs to the current agent set and the verify script's
  actual scope.
- Doc wording: name `./.aitask-scripts/aitask_archive.sh` in task-format. In
  crash-recovery, say that the lock is refreshed silently but the pick still
  asks the anomaly question for an `Implementing` task.
