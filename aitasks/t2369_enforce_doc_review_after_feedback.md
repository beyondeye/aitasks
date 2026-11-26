---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [doc_quality, workflow, skills]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2258
created_at: 2026-11-26 23:57
updated_at: 2026-11-27 00:00
---

## Problem

During the pre-commit review of t2258_10, the user manually added a preamble to forwarded shadow concerns asking the coding agent to treat them as findings to verify and to write any fixes under the documentation guide. The concern picker forwards editable text. The shared Step 8 **Need more changes** loop applies feedback and asks for review again, but it has no general requirement to audit the resulting documentation against its page-type and reader-level rules. A revision can therefore satisfy the wording of a concern while putting the detail on the wrong page, or reach **Commit changes** with a review of an earlier draft.

## Desired outcome

A documentation task follows the configured guide from the initial edit through every pre-commit review round. The task addresses each confirmed finding in a way that fits the page's type and declared `depth`, preserves valid facts when moving them, and presents the review results for the exact documentation revision being approved. This applies to forwarded shadow concerns and to feedback typed directly into the coding agent.

## Possible implementation directions

- **Make the shared Step 8 loop authoritative.** Resolve the project's configured doc guide and identify the documentation paths attributable to the task. For both the first review and any doc-changing iteration, verify factual claims against the implementation. Treat candidate wording as advisory unless the user explicitly requests exact text. Apply confirmed fixes on the owning page under the guide's page-type, reader-level, and prose rules. Preserve or record moved and corrected facts. Report how each concern was resolved, including evidence when it was already addressed or found incorrect and an explicit disposition for anything deferred.
- **Review the final revision before offering Commit changes.** Reuse `aitask-docs-review --caller audit` on affected live pages, including new or renamed pages and pages that receive moved details. The implementing agent applies the fixes and re-reviews affected pages after further edits. Record per-page level and prose results, reader-test status where applicable, and any unresolved findings. Consider a small review record bound to the canonical paths, file contents, and effective guide contents. Reuse it only while those inputs still match, and consider enforcing that match at the commit entry point alongside existing approval checks. A fingerprint establishes which revision was reviewed. The review procedure still judges accuracy and structure.
- **Make the shadow preamble a convenience.** When the receiving task or feedback is known to concern documentation, consider adding the instruction automatically to the concern payload: "Treat these as review findings to investigate. Verify factual claims against the implementation, then express confirmed fixes using the repo's rules for each page's type and reader level. Put details on the page that owns them. Re-review the final changed pages before asking to commit." Preserve the editable payload, ordinary forwarding, and the existing review path for direct feedback.
- **Reuse the draft review precedent where it fits.** The `docs_updated` gate already re-reviews revised drafts before applying them. Check whether that behavior can share a helper with the live-page audit. Adding the gate alone leaves a gap because Step 8 skips a procedure gate already recorded as pass or skip.

## Acceptance criteria

- On a documentation task, the first commit review and each review after doc edits account for the current task-owned documentation paths and the current guide.
- A forwarded factual concern or direct review request can fix the behavior description without copying proposed prose or placing reference detail in an intermediate how-to. The audit covers both the how-to and any receiving page.
- Editing, creating, renaming, or moving a relevant page after review, or changing the applicable guide, requires current review evidence before commit. A round with identical audited inputs can reuse its result. Unrelated edits in a shared checkout do not affect the task's reviewed set.
- An unresolved finding is visible before commit with an explicit disposition. The existing human commit approval remains in place.
- Verify both feedback paths, an old `docs_updated` pass followed by a new doc edit, and a task with no documentation changes.

## Starting points

- `.claude/skills/task-workflow/SKILL.md` § Step 8 and the corresponding generated agent variants
- `.claude/skills/aitask-docs-review/SKILL.md` § Procedure invariants and § Level and prose check
- `.claude/skills/aitask-gate-docs-updated/SKILL.md` §§ Review the drafts and Confirm with the user
- `.aitask-scripts/monitor/concern_parser.py` (`DEFAULT_PREAMBLE`, `build_clipboard_payload`)
- `aitasks/metadata/doc_update_guide.md` §§ Reader levels, Page types, and How a subject spans levels
