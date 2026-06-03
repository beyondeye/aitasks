---
priority: medium
effort: medium
depends: [878]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [878]
created_at: 2026-05-31 17:17
updated_at: 2026-05-31 17:17
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t878

## Verification Checklist

- [ ] In `ait brainstorm` on a session with nested component subsections (e.g. crew-brainstorm-635), open a `component_X` dimension from the node detail pane → the viewer lands on that component's own `### X` subsection heading, not the parent `## Components`.
- [ ] The proposal/plan minimap lists nested subsections, indented one level under their wrapper section.
- [ ] Selecting a nested subsection row in the minimap scrolls the body to that subsection's heading.
- [ ] Compare wizard / section picker now lists nested subsections as selectable targets — confirm no regression in selecting/launching a compare.
- [ ] Dimension badge count for a `component_X` key reflects both the wrapper (glob) and its own subsection (e.g. shows 2) — visual sanity check.
