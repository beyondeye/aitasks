---
priority: medium
effort: medium
depends: [t832_10]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: ['832_10']
created_at: 2026-05-29 18:32
updated_at: 2026-05-29 18:32
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t832_10

## Verification Checklist

- [ ] `ait projects list` shows >=1 resolvable cross-repo entry
- [ ] `ait create` interactively shows the new "Cross-repo project" fzf prompt after deps/labels
- [ ] Picking a registered project surfaces "Add cross-repo archived task reference (from <name>)" in the file/task reference loop
- [ ] Picking a registered project surfaces "Add cross-repo file reference (from <name>)" in the file/task reference loop
- [ ] Selecting an archived task from the cross-repo project appends `<name>#<id>` to the description body
- [ ] Selecting a file from the cross-repo project appends `<name>:<relative/path>` to the description body
- [ ] Resulting draft frontmatter contains `xdeprepo: <name>` and no `xdeps:` line
- [ ] Resulting draft `file_references:` (if any) contains only local entries (cross-repo refs stay inline only)
- [ ] Finalizing the draft preserves the cross-repo frontmatter on the final task file under `aitasks/`
- [ ] Re-running with "None (single-repo)" produces a draft with no `xdeprepo:`/`xdeps:` lines and the cross-repo menu items are NOT offered
- [ ] TODO: verify .aitask-scripts/aitask_create.sh end-to-end in tmux (fzf interactive surface)
