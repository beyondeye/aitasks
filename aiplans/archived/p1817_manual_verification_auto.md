---
Task: t1817_manual_verification_fix_trail_gather_linked_worktree_plan_co.md
Base branch: main
Output branch: main
---

# t1817 — Manual verification of t1809 (auto-execution record)

Strategy: autonomous (profile `fast`, "Yes, autonomous"). Verified at HEAD
`c1a9e5843` (the t1809 commit). The board's By-Trail banner is a direct render
of the first stdout token of `aitask_trail_gather.sh drift --trail <handle>`
(`board_trail_view.run_trail_drift` → `aitask_board.py` `_refresh_subtitle`), so
each item was checked at the CLI across all 9 stored trails and at the TUI on
one CURRENT trail. A pre-fix control worktree at `c1a9e5843^` was used to prove
the environment actually reproduces the bug.

Trails with `plan_file` refs (so the check is not vacuous): e.g.
`trail-backlog-roadmap` 11, `trail-mobile-shadow-driving` 6,
`trail-frozen-codeagents` 2.

## Execution Log

### Item 1
- Item text: Start `ait board` from a linked worktree and confirm the By-Trail banner no longer reads "(drift unavailable: ref_outside_project)" for a trail that is CURRENT in the primary checkout
- Approach: CLI + TUI (tmux, private `-L av1817` server)
- Action run: `git worktree add --detach <scratch>/wt1817 HEAD` + `aitask_init_data.sh --link-worktree` (`aiplans` realpaths to the primary's `.aitask-data/aiplans`, outside the worktree root); drift for all 9 trails; `ait board` → `z` → `s` → Enter on "Mobile shadow-agent driving over applink — landing order". Control: same in a `c1a9e5843^` worktree.
- Output (trimmed):
  - fixed worktree CLI: 5 CURRENT, 4 STALE, 0 errors
  - pre-fix worktree CLI: all 9 → `ERROR:ref_outside_project:aitasks:aiplans/...`
  - fixed worktree banner: `By-Trail: "Mobile shadow-agent driving over applink — landing order" · lite`
  - pre-fix banner: `By-Trail: "Mobile shadow-agent driving over applink — landing order" (drift unavailable: ref_outside_project) · lite`
- Verdict: pass

### Item 2
- Item text: Confirm the same trail's By-Trail drift verdict in the linked worktree matches what the primary checkout shows (same verdict, not merely "no error")
- Approach: CLI output diff + TUI banner comparison
- Action run: `cmp` of full drift stdout (verdict, `DRIFT:` reasons, `DIGEST:`) primary vs linked worktree, all 9 trails
- Output (trimmed): IDENTICAL ×9 (e.g. `trail-frozen-codeagents`: STALE, 2 × `status_changed`, same digest `375ae634dd732a5c`); banners identical for the TUI-checked trail
- Verdict: pass

### Item 3
- Item text: Start `ait board` in the primary checkout and confirm By-Trail drift still renders normally (control)
- Approach: CLI + TUI
- Action run: drift for all 9 trails in the primary; `ait board` → `z` → `s` → Enter on the same trail
- Output (trimmed): 5 CURRENT, 4 STALE, exit 0 each; banner `By-Trail: "Mobile shadow-agent driving over applink — landing order" · lite`
- Verdict: pass

### Item 4
- Item text: Pick a task under a worktree-mode profile (create_worktree: true) and confirm drift/roadmap checks work inside the created aiwork/ worktree
- Approach: reproduced the task-workflow Step 7 "Deferred worktree fork" layout exactly, WITHOUT claiming a real task (a real pick would lock and move an unrelated task to Implementing)
- Action run: `git worktree add -b aitask/t1817_verify_scratch aiwork/t1817_verify_scratch main` + `aitask_init_data.sh --link-worktree aiwork/t1817_verify_scratch`; inside it: drift for all 9 trails; `aitask_backlog_roadmap.sh --owner 'aitasks#1817' --out <scratch>` then `drift --trail <generated file>`; same roadmap round trip in the primary as control
- Output (trimmed): drift byte-identical to primary ×9; generated roadmap has 52 inputs / 11 `plan_file` refs, inputs identical to the primary-generated one; drift → CURRENT in both
- Verdict: pass (caveat: the fork was replicated by its documented commands rather than driven through a live `/aitask-pick` under a worktree profile)

## Cleanup

- tmux server `-L av1817` killed
- worktrees removed: `<scratch>/wt1817`, `<scratch>/wt1817_prefix`, `aiwork/t1817_verify_scratch`
- branch `aitask/t1817_verify_scratch` deleted
