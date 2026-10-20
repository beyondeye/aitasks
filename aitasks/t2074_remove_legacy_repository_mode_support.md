---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [framework, remove_support, git, setup, test_infrastructure, website, docs]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2074_1, t2074_2, t2074_3, t2074_4, t2074_5, t2074_6, t2074_7, t2074_8, t2074_9, t2074_10, t2074_11, t2074_12, t2074_13]
created_at: 2026-10-20 10:15
updated_at: 2026-10-20 12:34
---

## Objective

Scan the entire aitasks framework for remaining support for legacy repositories that keep task data on the code branch without a separate `aitask-data` branch, then completely remove that support. The final supported model requires the dedicated data branch and data-worktree layout. This task includes implementation, tests, generated instructions, and a complete website documentation sweep; an inventory alone is not completion.

## User decision and context

The user explicitly requested removal of all legacy repository support during the t2070 shadow review, then explicitly requested a website documentation sweep. The review found another legacy-specific sync path, illustrating the maintenance cost of two repository models. This is a framework-wide product decision, not a request to expand t2070 with more legacy compatibility fixes.

Here, "legacy" means the repository storage model without an `aitask-data` branch. Other uses of that word (old task formats, model aliases, home-directory migration, older concern formats) are not automatically in scope. A repository with a local data branch but no network remote is a separate case.

## Required work

1. Audit all maintained execution paths, not only occurrences of `legacy`. Trace mode detection, absent-worktree/default-to-current-directory behavior, plain-git fallbacks for task data, configuration/CLI options, status tokens and consumers, setup/install/upgrade, linked worktrees, sync/drift checks, task/plan/metadata writers, snapshots, locks, artifacts/attachments, TUIs, engine implementations, and installed-project behavior. Record an evidence-backed inventory with each location's disposition.
2. Remove runtime branches and compatibility fallbacks that operate on task data in the code branch. Enforce the required layout consistently. Missing, broken, or unresolvable data layout must produce an actionable error before task-data writes, commits, pulls, or pushes can be routed to the code branch. Distinguish missing initialization from a broken existing layout.
3. Remove setup choices and flags that allow users to select or remain in legacy mode. Fresh setup must establish the required data branch/worktree. Define the transition for existing installations: any retained one-way conversion belongs to setup/migration only, preserves existing data, and does not leave a second supported runtime mode. Ordinary commands must not silently migrate or relocate user data.
4. Remove obsolete legacy result tokens and update producers and consumers together, including workflow skills and agent instructions. Edit canonical templates/seeds and regenerate variants with repository tooling. Update maintained/generated instructions that say `./ait git` passes through to plain git in legacy mode.
5. Convert positive-path tests and shared fixtures that depend on legacy layout to realistic data-branch fixtures, preserving their original behavioral assertions. Remove tests whose sole purpose is to guarantee retired behavior. Retain negative tests proving unsupported layouts are refused without modifying repository data. Do not merely delete broad suites or weaken unrelated assertions.
6. Perform the full website documentation sweep described below, plus corresponding maintained developer documentation, CLI help, examples, and release-facing compatibility guidance.
7. Review active backlog/manual-verification tasks that still require legacy behavior; identify obsolete criteria and reconcile them through the normal task workflow. Archived plans and historical changelog entries need not be rewritten as if legacy mode never existed.
8. Repeat the framework-wide scan after implementation. Account for all remaining relevant matches and implicit fallbacks, distinguishing historical context, rejection tests, and explicit one-way conversion from supported runtime behavior.

## Website documentation sweep (explicit deliverable)

Audit the entire website source, not only the sync page or files changed by implementation. Inspect getting-started/onboarding, installation and upgrades, repository structure, setup and configuration, command references, workflows, TUIs, troubleshooting/crash recovery, development/contribution guides, FAQs, examples, diagrams, snippets, navigation, and reusable/generated content.

Search both explicit terms (`legacy mode`, `LEGACY_MODE`, optional/separate data branch) and implicit promises: storing tasks on main/the code branch, declining data-branch setup, choosing between layouts, plain-git fallback, and instructions that omit the required layout or assume real task directories in the code checkout.

Update each affected page to describe the single supported model, required setup, unsupported-layout diagnostics, and the chosen upgrade/conversion procedure. Remove obsolete options and examples, repair links and navigation when pages/sections move, and revise screenshots/diagrams where they materially depict retired choices. Do not remove unrelated historical uses of "legacy" indiscriminately.

Record the pages/sections reviewed, changes made, and any retained historical references with justification. Build the website and run its link/documentation validation, including `python3 check_links.py --build` from `website/` where still applicable. Completion requires an explicit website sweep report and passing validation, not just a claim that docs were updated.

## Initial audit leads

Re-enumerate these at implementation time; this list is not exhaustive:

- `.aitask-scripts/lib/task_utils.sh`: layout detection, `ait_data_mode`, `_ait_data_git`, `task_git`, git-dir resolution, sync/push/convergence, and default-to-`.` branches.
- `.aitask-scripts/lib/data_symlinks.sh`, `lib/txn_snapshot.sh`, and `lib/task_automerge.sh`.
- `.aitask-scripts/aitask_setup.sh`, `aitask_init_data.sh`, and `install.sh`: optional data-branch setup, the "Use a separate branch for task data?" prompt, migration/upgrade, and legacy early exits.
- `.aitask-scripts/aitask_sync.sh`, `aitask_remote_drift_check.sh`, `aitask_lock_diag.sh`, and `board/board_task_manager.py`; audit other language implementations too.
- Canonical `.claude/skills/ait-git/` and `.claude/skills/task-workflow/`, pickrem/pickweb flows, all generated agent/profile variants, `seed/aitasks_agent_instructions.seed.md`, and maintained agent instructions.
- Tests for task Git, push, sync, initialization, setup, upgrades, artifacts/attachments/transactions, and shared fixtures under `tests/lib/`.
- All website sources; preliminary matches include sync, board, crash-recovery, development, and web-merge documentation. Also audit maintained `aidocs/` documents.
- Existing tasks t1619 (setup decline path), t1625 (LEGACY_MODE worktree handling), t1984 and t1678 (legacy assumptions), and t2070 (overlapping sync code). These are coordination references, not automatic dependencies or authorization to overwrite concurrent work.

## Acceptance criteria

- The inventory covers runtime code, setup/install/upgrade, tests/fixtures, canonical/generated skills and instructions, and documentation. Each legacy-support path has a recorded removal or explicit non-runtime disposition.
- Normal framework operations have no supported code-branch task-data mode and cannot silently fall back to it when the required data layout is absent or damaged.
- Fresh and repeat setup establish/use the required layout. Existing legacy installations receive documented conversion/refusal behavior without losing their task data.
- Primary checkouts, linked task worktrees, and installed projects use the correct data branch. A missing network remote is handled independently from a missing data branch.
- Negative tests prove unsupported/unresolved layouts cannot mutate, stage, commit, pull, or push task data through the code branch.
- Converted tests retain their original behavioral coverage. Relevant Bash/Python/Go tests and generated-wrapper checks pass as applicable.
- The full website sweep is documented; current pages, examples, navigation, and reusable content consistently describe the sole supported model. Website build/link checks pass.
- No current setup option, runtime status consumer, instruction, or documentation promises continued legacy repository support.

## Implementation planning

This is a broad removal with substantial fixture impact. Use the audit to split implementation into coherent child tasks if needed, retaining the complete-removal and website-sweep acceptance criteria on this parent. Sequence shared layout detection, setup transition, runtime consumers, fixture conversion, generated instructions, and documentation cleanup so temporary compatibility paths do not remain in the final design.
