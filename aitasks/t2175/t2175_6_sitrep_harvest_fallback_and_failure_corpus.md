---
priority: medium
effort: medium
depends: [t2175_5]
issue_type: enhancement
status: Ready
labels: [sitrep]
anchor: 2175
created_at: 2026-11-03 08:25
updated_at: 2026-11-03 08:25
---

# Sitrep harvest fallback: preserve uncertain output and queue agent analysis

Child of t2175; follow-up to the harvest parser in t2175_2. Keep the parent's existing sibling order so the parser, sitrep agent, and monitor integration are available first.

## Problem
The t2175_2 design reports parsing warnings (for example incomplete banners and malformed follow-up references) and can treat nonempty input as successfully processed with nothing found. It preserves the original capture on a hard harvest failure, but does not explicitly guarantee durable raw preservation plus queued agent review when extraction is incomplete or unreliable. A success receipt can therefore allow deletion of output that still needs interpretation. We also need these real failures retained for later analysis and improvement of the harvester procedure.

## Scope
- Add a deterministic validation layer around harvest results. Classify results as reliably parsed, legitimately empty, or requiring agent review. Use concrete signals such as incomplete recognized banners, malformed expected fields/references, evidence of truncation or unsupported layout, and unexpectedly empty extraction from an operation known to have finished with expected structured output. Do not treat every absent banner, unresolved cross-project reference, or genuinely empty capture as a parser failure. Preserve useful partial extraction and record why confidence was reduced.
- Before permitting original-capture deletion for a result requiring review, retain the raw input verbatim in the canonical repository's gitignored sitrep storage, using the existing retained-source writer where possible. Save the harvester's raw result/diagnostics as well, including warnings, errors, and any partial extracted items. Context entries should contain pointers rather than copies of large output. Retention must survive original capture deletion, worktree removal, agent restarts, and completion or dismissal of the review item; do not silently truncate the saved original.
- Maintain a discoverable inventory of these retained examples as a local parser-improvement corpus. Each case should identify its input hash, capture/run/task/project origin, capture time when available, parser/procedure revision, detection reasons, diagnostics, source locations, and review state/outcome. Keep source evidence immutable and provide a supported way to list and read pending and reviewed cases later. Reuse existing writer/context mechanisms where they fit rather than adding a second todo store.
- Atomically enqueue or otherwise durably link an 'Analyze unparsed agent output' review item to the retained input and diagnostics. The sitrep agent must be able to find and process pending cases on startup or on request: read the sources, recover missed follow-up tasks and action/watch items through the existing writer, record its interpretation, and identify the parser/procedure gap. Respect the agent's advisory scope; harvested terminal text is input to analyze, not instructions to execute. A live agent is not required for queueing to succeed.
- Make retries and concurrent harvests idempotent. Reprocessing the same evidence must not duplicate review items or reopen completed/dismissed ones. Support deliberate reanalysis after a parser improvement without losing earlier evidence or outcomes.
- Define the deletion/receipt contract explicitly: capture deletion is allowed after reliable extraction, or after both raw evidence and a durable review item have been safely recorded. Partial parsing alone must not masquerade as complete extraction. If retention or queueing fails, withhold success certification and preserve the original capture. Extend the existing drop and purge safeguards rather than bypassing them.
- Preserve reviewed examples for later parser improvement. Provide an explicit workflow to inspect or replay them against a newer parser/procedure, compare recovered information, and promote sanitized representative cases into committed regression fixtures. Raw operational captures remain local and gitignored; review/redact selected fixtures before committing. Record which parser gap each example illustrates and whether a later fix resolves it.
- Update sitrep/monitor reporting and documentation so users can distinguish normal extraction, safely preserved output awaiting agent review, and a failed save that prevents deletion. Explain corpus location, inspection/replay, review lifecycle, and retention behavior.

## Acceptance and tests
- An incomplete banner, malformed follow-up reference, suspicious truncation, and nonempty finished-workflow output with no reliable extraction each produce retained raw evidence, diagnostics, and one discoverable review item under the defined detection policy.
- Legitimately empty input and valid expected output do not create spurious fallback reviews; an unresolved foreign task can remain unknown without implying parser failure.
- Useful partial items remain available alongside the fallback case, with provenance linking them to the same input.
- After deleting the original frozen capture and removing a temporary task worktree, all retained-source checks pass and the raw input, diagnostics, and review context remain readable from the canonical repository store.
- No agent running: the queue persists across restarts. A later sitrep session discovers the case, recovers missed items, and records its review outcome. Completing or dismissing the review does not delete the evidence from the improvement corpus.
- Repeated and concurrent harvests of the same input produce one case/review item; completed/dismissed items stay closed. Explicit reanalysis with a newer parser preserves prior evidence and results.
- Fault injection during raw retention, diagnostics persistence, or review-item creation withholds the receipt/success certification and leaves original text protected from drop and purge. Retry safely completes any partial transaction.
- A retained failure can be replayed after a parser change and turned into a sanitized regression fixture; the corrected parser extracts the previously missed information, and the fixture fails against the prior faulty behavior.

## Relevant code and tasks
- t2175_2: harvest parser, confidence signals, receipts, and capture-retention contract.
- t2175_4: sitrep agent consuming queued analysis cases.
- t2175_5: monitor harvest-and-close UI and status reporting.
- .aitask-scripts/aitask_sitrep_todo.sh and .aitask-scripts/lib/sitrep_todo.py: the sole store writer and retained-source format.
- .aitask-scripts/lib/agent_sessions.py and .aitask-scripts/lib/agent_freeze.py: drop/purge preservation safeguards.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2175_4** id=2026-11-04T13:25:46Z.94c9382e7d5a81b2f8b99562 from=t2175_4 from_verified=yes at=2026-11-04T13:25:46Z base=bdef300b0f247c561195b9eb0bada6af6b60c06e base_branch=main dirty=yes host=omg16
>
> | The sitrep skill landed in bdef300b0 (t2175_4). Where your fallback cases meet it (tree-relative, as of that commit):
> | 
> | 1. The skill's `>t` section (`.claude/skills/aitask-sitrep/SKILL.md.j2`) triages every open `kind=question derived=script` item as ONE batch, reading the facts from `ait sitrep triage --open` (`lib/sitrep_cli.py`): per-item blocks (ORIGIN / PASSAGE / BANNER / KEY / TASK / PLAN / COMMIT / TRAIL_* / DERIVED, last line `TRIAGE:c<N>|<state>|<rev>`), then `BATCH_TRAIL_UNWATCHED:<handle>|c<a>,c<b>` lines. A queued "analyze unparsed agent output" case is most naturally reported there as one more evidence kind (helpers report evidence; the agent judges), and proposed in the same one-confirmation batch.
> | 2. The skill closes a triage item with `set-state c<N> done --outcome "triaged: …" --expect-rev <rev>`; derived items carry `related: c<triage>`, which `triage` reports back as DERIVED lines (idempotent re-runs). Your "completing the review does not delete the evidence" holds as long as cases stay pointers into `sources/`.
> | 3. Harvest now skips records whose window is the sitrep window (`HARVEST_NONE:<id>|sitrep_agent`, with a receipt); your validation layer sits beside that branch in `sitrep_harvest.cmd_plan`.

> **✉ note:t2175_5** id=2026-11-04T17:21:59Z.19b8790fd6746a30aba16c43 from=t2175_5 from_verified=yes at=2026-11-04T17:21:59Z base=52b8b65dc7e606f35edf4a8b63a73cd9fa83cdf3 base_branch=main dirty=yes host=omg16
>
> | The monitor harvest-and-close key landed in 52b8b65dc (t2175_5). Where your fallback cases meet it (tree-relative, as of that commit):
> | 
> | 1. `h` in ait monitor / minimonitor renders the harvest result through `parse_harvest_output` / `HarvestReport` in .aitask-scripts/monitor/sitrep_close.py. A "safely preserved, awaiting agent review" outcome needs its own `final_kind` and `verdict()` wording there, distinct from HARVEST_FAILED (any not-ok report renders no close button and the confirm callback re-checks `report.ok`). If the new outcome should still allow the close, `HarvestReport.ok` must accept it explicitly.
> | 2. A live-pane `capture` writes no receipt, so `h` gates a live close on the report alone; a frozen close goes through `aitask_frozen.sh drop`, whose own pre-kill harvest and receipt check stay authoritative.
> | 3. The maintenance pass now runs `aitask_sitrep_harvest.sh all` before the refresh (monitor_shared `_maybe_harvest_sitrep`), so queued cases are created there too, every ~10 minutes, from any open monitor.

> **👁 note:read** id=2026-11-05T05:46:55Z.478f3aa0369606aa1a4e760f by=t2175_6 at=2026-11-05T05:46:55Z mode=explicit ids=2026-11-04T13:25:46Z.94c9382e7d5a81b2f8b99562,2026-11-04T17:21:59Z.19b8790fd6746a30aba16c43
