---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1595
followup_kind: upstream_defect
created_at: 2026-08-25 16:40
updated_at: 2026-08-25 16:48
---

## Origin

Spawned from t1601 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:1661` — `update_claudemd_git_section` is called
  unconditionally from `setup_data_branch` Step 8, and `insert_aitasks_instructions`
  takes its **append** branch on a markerless file. This repo's `CLAUDE.md` has 0
  `>>>aitasks` markers, and `aidocs/framework/aitasks_extension_points.md:96-97`
  documents it as hand-maintained with no markers — so a real `ait setup` reaching
  `setup_data_branch` would append a full marked block to `CLAUDE.md`, duplicating its
  "### Task File Format" YAML block and contradicting the documented contract.

## Diagnostic context

Noticed while resyncing the Codex/OpenCode instruction mirrors in t1601. That task
inventoried every `>>>aitasks` marker surface in the tree and found exactly three
(`AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md`). `CLAUDE.md` was
explicitly excluded as a fourth surface on the strength of the extension-points doc,
which calls it hand-maintained and markerless — and the working tree agrees
(`grep -c '>>>aitasks' CLAUDE.md` → 0).

But the code does not agree. Verified by reading the call chain:

- `.aitask-scripts/aitask_setup.sh:1660-1661` — `# --- Step 8: Update CLAUDE.md ---`
  followed by an unconditional `update_claudemd_git_section "$project_dir"`, inside
  `setup_data_branch()` (function starts at :1387).
- `update_claudemd_git_section` (:1352-1364) assembles the shared + `claude` layer and
  calls `insert_aitasks_instructions "$claudemd" "$content"`.
- `insert_aitasks_instructions` (:1319-1348) branches on
  `grep -qF ">>>aitasks" "$target"`. On a file WITHOUT the marker it takes the
  `else` branch and **appends** the marked block.

So the first `ait setup` run that reaches `setup_data_branch` Step 8 in this repo
would silently grow `CLAUDE.md` a duplicate task-format block. The two states
("hand-maintained, no markers" vs. "marker-managed") are both live: the file is in
state 1 and the code assumes it may move to state 2.

Note this is a different code path from the one t1601 fixed. t1601 covered the two
`_is_agent_installed`-gated mirrors; `update_claudemd_git_section` is ungated, like
`update_agentsmd`.

## Suggested fix

Decide which contract is real and make one side match the other:

- **If `CLAUDE.md` should stay hand-maintained** (the documented position, and the
  reason the framework's own `CLAUDE.md` carries far more than the seed block):
  stop calling `update_claudemd_git_section` for a markerless `CLAUDE.md`, or gate
  the call on the marker already being present so setup only *refreshes* an existing
  block and never creates one.
- **If `CLAUDE.md` should be marker-managed:** correct
  `aidocs/framework/aitasks_extension_points.md:96-97`, and reconcile what happens to
  the hand-written "### Task File Format" block that would then be duplicated.

Whichever way it goes, consider extending the t1601 drift guard
(`tests/test_agent_instructions.sh` T25-T37): it currently asserts the three marker
surfaces match the generator. A fourth assertion pinning `CLAUDE.md`'s intended state
— markers present and matching, or markers absent — would keep this decision from
drifting back.
