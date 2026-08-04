---
priority: medium
effort: medium
depends: [t1405_7]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1405_1, 1405_2, 1405_3, 1405_4, 1405_5, 1405_6, 1405_7]
anchor: 1405
created_at: 2026-08-04 16:49
updated_at: 2026-08-04 16:49
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1405_2] Every claim re-verified before promotion; UNVERIFIABLE items are structurally ineligible and are listed as dropped in the Final Implementation Notes.
- [ ] [t1405_2] Every cited source path in the edited doc(s) still exists (the dead-reference check in the task file — it exits 1, not merely prints).
- [ ] [t1405_2] `bash tests/test_aidocs_pointer_parity.sh` passes.
- [ ] [t1405_2] Every ruling journalled `state=done`; each PROMOTE/MERGE row carries a verbatim, single-line, tab-free excerpt of **≥40 characters** taken from the text actually written, and that excerpt is findable inside the journalled section's span.
- [ ] [t1405_2] `MEMORY.md` lines removed by matching the line's link target **after re-reading the file** — never by regenerating the index from a remembered list, because a concurrent writer may have added lines.
- [ ] [t1405_3] Every claim re-verified before promotion; UNVERIFIABLE items are structurally ineligible and are listed as dropped in the Final Implementation Notes.
- [ ] [t1405_3] Every cited source path in the edited doc(s) still exists (the dead-reference check in the task file — it exits 1, not merely prints).
- [ ] [t1405_3] `bash tests/test_aidocs_pointer_parity.sh` passes.
- [ ] [t1405_3] Every ruling journalled `state=done`; each PROMOTE/MERGE row carries a verbatim, single-line, tab-free excerpt of **≥40 characters** taken from the text actually written, and that excerpt is findable inside the journalled section's span.
- [ ] [t1405_3] `MEMORY.md` lines removed by matching the line's link target **after re-reading the file** — never by regenerating the index from a remembered list, because a concurrent writer may have added lines.
- [ ] [t1405_4] Every claim re-verified before promotion; UNVERIFIABLE items are structurally ineligible and are listed as dropped in the Final Implementation Notes.
- [ ] [t1405_4] Every cited source path in the edited doc(s) still exists (the dead-reference check in the task file — it exits 1, not merely prints).
- [ ] [t1405_4] `bash tests/test_aidocs_pointer_parity.sh` passes.
- [ ] [t1405_4] Every ruling journalled `state=done`; each PROMOTE/MERGE row carries a verbatim, single-line, tab-free excerpt of **≥40 characters** taken from the text actually written, and that excerpt is findable inside the journalled section's span.
- [ ] [t1405_4] `MEMORY.md` lines removed by matching the line's link target **after re-reading the file** — never by regenerating the index from a remembered list, because a concurrent writer may have added lines.
- [ ] [t1405_5] Every claim re-verified before promotion; UNVERIFIABLE items are structurally ineligible and are listed as dropped in the Final Implementation Notes.
- [ ] [t1405_5] Every cited source path in the edited doc(s) still exists (the dead-reference check in the task file — it exits 1, not merely prints).
- [ ] [t1405_5] `bash tests/test_aidocs_pointer_parity.sh` passes.
- [ ] [t1405_5] Every ruling journalled `state=done`; each PROMOTE/MERGE row carries a verbatim, single-line, tab-free excerpt of **≥40 characters** taken from the text actually written, and that excerpt is findable inside the journalled section's span.
- [ ] [t1405_5] `MEMORY.md` lines removed by matching the line's link target **after re-reading the file** — never by regenerating the index from a remembered list, because a concurrent writer may have added lines.
- [ ] [t1405_6] Every claim re-verified before promotion; UNVERIFIABLE items are structurally ineligible and are listed as dropped in the Final Implementation Notes.
- [ ] [t1405_6] Every cited source path in the edited doc(s) still exists (the dead-reference check in the task file — it exits 1, not merely prints).
- [ ] [t1405_6] `bash tests/test_aidocs_pointer_parity.sh` passes.
- [ ] [t1405_6] Every ruling journalled `state=done`; each PROMOTE/MERGE row carries a verbatim, single-line, tab-free excerpt of **≥40 characters** taken from the text actually written, and that excerpt is findable inside the journalled section's span.
- [ ] [t1405_6] `MEMORY.md` lines removed by matching the line's link target **after re-reading the file** — never by regenerating the index from a remembered list, because a concurrent writer may have added lines.
- [ ] [t1405_1] tests/test_aidocs_pointer_parity.sh passes, and its negative control exits 1 naming the removed doc.
- [ ] [t1405_1] tests/test_agent_instructions.sh still passes (T21 out-of-marker prose survival).
- [ ] [t1405_1] `./ait setup` then `git diff --stat AGENTS.md .codex/instructions.md .opencode/instructions.md` — the appendices survive regeneration.
- [ ] [t1405_1] `grep -c "aidocs/framework" AGENTS.md` is no longer 0.
- [ ] [t1405_1] Every DISCARD ruling is journalled state=done and the file is gone from both disk and MEMORY.md.
- [ ] [t1405_7] `.aitask-memtriage/t1405_accept.sh` prints "t1405 ACCEPTANCE: PASSED" and exits 0.
- [ ] [t1405_7] All six acceptance negative-control runs exited as specified — baseline 0, five mutations each exiting 1 naming that specific mutation.
- [ ] [t1405_7] Every rewritten wikilink destination resolves: the doc exists and the heading is present.
- [ ] [t1405_7] MEMORY.md is <= 10 KB, or an approved `.aitask-memtriage/size_override_approved` records the user's decision.
- [ ] [cross-agent] Launch a real Codex CLI session in this repo and confirm it surfaces the aidocs/framework pointer appendix from AGENTS.md — grep proves the text is present, not that the agent reads it.
- [ ] [cross-agent] Launch a real OpenCode session and confirm the same for its instructions surface.
- [ ] [readability] Read each edited aidocs/framework doc end to end: promoted entries must read as coherent conventions, not ~110 disconnected fragments. Flag any section whose rule is no longer actionable after condensation.
- [ ] [context-load] Start a fresh Claude Code session in this repo and confirm MEMORY.md loads cleanly at its new size with no compaction hook firing.
