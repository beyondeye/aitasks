---
priority: medium
effort: medium
depends: [808]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [808]
followup_kind: manual_verification
created_at: 2026-05-20 07:57
updated_at: 2026-08-13 23:07
boardcol: manual_verifications
boardidx: 140
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t808

## Verification Checklist

- [ ] Launch a brainstorm session and run a patcher agent; confirm the patcher output auto-applies via the TUI poll loop (_try_apply_patcher_if_needed) and the DAG refreshes with the new patched node.
- [ ] Confirm an IMPACT_FLAG patcher result populates the patcher impact banner with the IMPACT block text verbatim.
- [ ] Trigger a patcher apply failure (malformed _output.md) and confirm the error banner shows the `ait brainstorm apply-patcher ...` retry hint.
- [ ] Press ctrl+shift+r to force-retry a failed patcher apply; confirm it re-applies and clears the impact/error banner.
- [ ] Confirm explorer and synthesizer auto-apply still create nodes and merge NEW_DIMENSIONS correctly after the shared-core refactor.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1879** id=2026-11-15T16:13:22Z.9e44bc0c89db56fca296bf39 from=t1879 from_verified=yes at=2026-11-15T16:13:22Z base=57b660ff0c0fa2d3eaf836a353acbae7849414c6 base_branch=main dirty=yes host=omg16
>
> | Advisory (from t1879, which documented the brainstorm apply/delete subcommands). Claims are about the tree at this note's base commit; re-check before relying on them.
> | 
> | Some checklist items in this task use `ait brainstorm apply-patcher ...` and Ctrl+Shift+R. In this tree neither exists:
> | - no `aitask_brainstorm_apply_patcher*` script under `.aitask-scripts/`, and no `apply-patcher` case in the `brainstorm)` dispatcher in `ait` (it lists init, status, list, archive, apply-initializer, apply-explorer, apply-synthesizer, delete);
> | - no `ctrl+shift+r` binding in `.aitask-scripts/brainstorm/brainstorm_app.py` (a source comment near line 2349 says the Ctrl+Shift retry chords were removed in t1018_2).
> | 
> | Current apply-retry routes: `i` on a Running-tab group row (re-applies the group's Completed agents; explore/synthesize/compare groups), Ctrl+R on the Running tab for the initializer, and `ait brainstorm apply-initializer|apply-explorer|apply-synthesizer` on the command line.
> | 
> | Before running those items, check whether the patcher apply path still exists at all; the items may need rewriting or skipping.
