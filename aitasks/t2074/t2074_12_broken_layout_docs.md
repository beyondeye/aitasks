---
priority: medium
effort: high
depends: [t2074_3, t2074_9]
issue_type: documentation
status: Ready
labels: [website, docs, documentation]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:33
updated_at: 2026-10-20 17:01
---

## Context

Part of t2074 (rescoped: **branch-mode layout hardening**; legacy mode stays
supported, and **its docs stay unchanged**). This task documents what the user
sees when a branch-mode layout is damaged and how to recover. Read the states,
the enforcement table and C4 in `aiplans/p2074_branch_mode_layout_hardening.md`.

Depends on t2074_3 (the final repair behaviour) and t2074_9 (the final refusal
text and `git-health` output). Follow
`aidocs/framework/documentation_conventions.md`: document current behaviour
only, with no version history.

## Deliverables

1. A website troubleshooting section for **damaged branch-mode layouts**. For
   each C1a and C1b state, give the exact refusal text, copied from the code,
   and its C4 recovery:
   - `stale_marker`, `foreign_repo`, `wrong_branch`;
   - the rebase and bisect wedged cases, which are valid, plus their
     recoveries `./ait git rebase --abort` and `./ait git bisect reset`;
   - `missing_storage`: case (A), restoring from a local or remote branch;
     case (B), with its preservation refusals and the interactive confirmation;
     the no-branch restore instructions; and the row-1 mixed case;
   - `indeterminate`;
   - `unlinked`, recovered with `--link-worktree`;
   - `misdirected`, `dangling` and `mixed`.

   State the rule plainly: setup never runs `git worktree prune`, and why.
2. State the **narrowed reader contract**. Only `ait ls`,
   `aitask_query_files.sh` and board startup refuse. Other read-only TUIs
   display whatever is on disk.
3. Link the section from the setup page (`commands/setup-install.md`) and the
   sync page (`commands/sync.md`) with `{{< relref >}}`.
4. Update the `git-health` output where `installation/_index.md` quotes it
   (:89), to match t2074_9's output.
5. Update the aidocs descriptions of detection, if they describe it:
   `aidocs/framework/aitasks_extension_points.md` and
   `aidocs/framework/tui_conventions.md`.
6. Leave the legacy-mode wording in place. Do not edit any page to remove
   legacy support.

## Verification

From `website/`:
- `hugo build --gc --minify` succeeds.
- `python3 check_links.py --build` must pass.
- Run `python3 check_link_relevance.py` and triage every hit, opening each
  target.
