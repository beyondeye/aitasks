---
Task: t594_7_docsy_labels_support.md
Parent Plan: aiplans/p594/p594_7_docsy_labels_support.md
Artifact type: label catalog (working doc, applied in Step 4)
---

# t594_7 — Docs label catalog

## Legend

- **maturity**: `experimental` (pre-stable / flagged / stub coverage), `stabilizing` (shipped, heavy recent churn), unlabeled = stable default.
- **depth**: `main-concept` (first-read foundation), `intermediate` (day-to-day past basics), `advanced` (deep integration / reference / low-level schema).
- Unlabeled cells (`—`) mean "no label on this axis".

## Heuristic signals summary

- Commit counts are for the underlying source paths (not the docs) since 2026-01-01 (~110 days).
- `codebrowser` (37 commits), `monitor` (34), `board` (33), `brainstorm` (40) and `settings` (25) dominate recent TUI churn → **stabilizing** candidates.
- `tuis/stats/` has only `_index.md` (no how-to, no reference) + stats_app.py has 2 commits dormant since 2026-03-07 → **experimental** (stub).
- `skills/aitask-add-model.md` source landed 2026-04-17 (1 commit) → **experimental** (just-landed).
- CLAUDE.md flags `diffviewer` as transitional, but per CLAUDE.md "omit from user-facing website docs" — so no page to label.
- `concepts/_index.md` already hand-marks 5 `depth: main-concept` pages: tasks, plans, parent-child, locks, task-lifecycle. Those five are the seed.

## Root (3 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Title shell, no signal. |
| `overview.md` | — | main-concept | Entry reading — sets up the whole framework. |
| `getting-started.md` | — | main-concept | Entry reading — first commands the user runs. |

## installation/ (5 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `windows-wsl.md` | — | intermediate | Platform-specific setup instructions. |
| `terminal-setup.md` | — | intermediate | Day-to-day terminal / tmux setup. |
| `known-issues.md` | — | intermediate | Troubleshooting reference readers reach for as needed. |
| `git-remotes.md` | — | advanced | Integration-level config (GitHub/GitLab/Bitbucket routing). |

## concepts/ (14 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `tasks.md` | — | main-concept | Current `*(Main concepts)*` seed. |
| `plans.md` | — | main-concept | Current `*(Main concepts)*` seed. |
| `parent-child.md` | — | main-concept | Current `*(Main concepts)*` seed. |
| `locks.md` | — | main-concept | Current `*(Main concepts)*` seed. |
| `task-lifecycle.md` | — | main-concept | Current `*(Main concepts)*` seed. |
| `folded-tasks.md` | — | intermediate | Common workflow concept but not required first-read. |
| `execution-profiles.md` | — | intermediate | Useful after first pick; not prerequisite. |
| `review-guides.md` | — | intermediate | Shows up once the user reaches code review. |
| `agent-attribution.md` | — | advanced | Meta/infrastructure — model-scoring internals. |
| `verified-scores.md` | — | advanced | Meta — scoring aggregation detail. |
| `agent-memory.md` | — | advanced | Meta concept — long-term archived-plan reuse. |
| `git-branching-model.md` | — | advanced | Deep integration — the separate task-data branch. |
| `ide-model.md` | — | advanced | Deep setup — tmux IDE mental model. |

## commands/ (10 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `task-management.md` | — | intermediate | `ait create`/`update` — daily commands. |
| `setup-install.md` | — | intermediate | One-time onboarding. |
| `sync.md` | — | intermediate | Daily sync between branches. |
| `lock.md` | — | intermediate | Recovery / diagnostic use. |
| `board-stats.md` | — | intermediate | TUI launch shortcuts. |
| `codeagent.md` | — | intermediate | Per-agent launch — daily. |
| `explain.md` | — | intermediate | File-history lookup — occasional. |
| `pr-import.md` | — | advanced | PR-integration flow — power-user. |
| `issue-integration.md` | — | advanced | Issue-tracker integration — integration-heavy. |

## skills/ (31 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `aitask-pick/_index.md` | — | main-concept | The entry skill — every user's first `/aitask-pick`. |
| `aitask-pick/build-verification.md` | — | advanced | Reference detail for Step 9. |
| `aitask-pick/commit-attribution.md` | — | advanced | Reference detail for Step 8. |
| `aitask-pick/execution-profiles.md` | — | advanced | Profile schema reference. |
| `aitask-pickrem.md` | stabilizing | intermediate | 20 commits since Jan 1, still evolving remote flow. |
| `aitask-pickweb.md` | stabilizing | intermediate | 14 commits, web flow still stabilizing. |
| `aitask-create.md` | — | intermediate | Daily create skill. |
| `aitask-explore.md` | stabilizing | intermediate | 24 commits — exploration flow still iterating. |
| `aitask-wrap.md` | — | intermediate | Retroactive-wrap — occasional daily. |
| `aitask-fold.md` | stabilizing | intermediate | 18 commits — fold semantics still being refined. |
| `aitask-review.md` | — | intermediate | Review launch skill. |
| `aitask-qa.md` | — | intermediate | QA follow-up skill. |
| `aitask-explain.md` | — | intermediate | File-evolution skill. |
| `aitask-stats.md` | experimental | intermediate | 2 commits, dormant since 2026-03-07; coverage minimal. |
| `aitask-changelog.md` | — | intermediate | Release-prep skill. |
| `aitask-revert.md` | — | advanced | Destructive — power-user. |
| `aitask-pr-import.md` | — | advanced | Integration skill. |
| `aitask-contribute.md` | — | advanced | Integration — opens issues to upstream. |
| `aitask-contribution-review.md` | — | advanced | Consumer-side of contribute flow. |
| `aitask-web-merge.md` | — | advanced | Complements pickweb — power flow. |
| `aitask-refresh-code-models.md` | — | advanced | Meta — model-config maintenance. |
| `aitask-add-model.md` | experimental | advanced | Landed 2026-04-17, single commit; infra-level. |
| `aitask-reviewguide-import.md` | — | advanced | Review-guide toolchain. |
| `aitask-reviewguide-classify.md` | — | advanced | Review-guide toolchain. |
| `aitask-reviewguide-merge.md` | — | advanced | Review-guide toolchain. |
| `verified-scores.md` | — | advanced | Meta — score calculation reference. |

## tuis/ (15 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `board/_index.md` | stabilizing | main-concept | Board is the Kanban hub; 33 commits on source. |
| `board/how-to.md` | stabilizing | intermediate | Day-to-day board actions. |
| `board/reference.md` | stabilizing | advanced | Keybinding table / per-screen reference. |
| `monitor/_index.md` | stabilizing | intermediate | 34 commits — home screen of the IDE. |
| `monitor/how-to.md` | stabilizing | intermediate | Day-to-day monitor actions. |
| `monitor/reference.md` | stabilizing | advanced | Keybinding reference. |
| `codebrowser/_index.md` | stabilizing | intermediate | 37 commits — highest churn TUI. |
| `codebrowser/how-to.md` | stabilizing | intermediate | Day-to-day. |
| `codebrowser/reference.md` | stabilizing | advanced | Keybinding reference. |
| `minimonitor/_index.md` | — | intermediate | Lower churn (11 commits); feature is solid. |
| `minimonitor/how-to.md` | — | intermediate | Day-to-day minimonitor usage. |
| `settings/_index.md` | stabilizing | intermediate | 25 commits — still adding tabs. |
| `settings/how-to.md` | stabilizing | intermediate | Day-to-day settings editing. |
| `settings/reference.md` | stabilizing | advanced | Settings schema reference. |
| `stats/_index.md` | experimental | intermediate | Only page in the stats section; 2 commits on source, dormant. |

## workflows/ (20 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `capturing-ideas.md` | — | intermediate | Capturing flow — everyday. |
| `create-tasks-from-code.md` | — | intermediate | `/aitask-explore` wrapping. |
| `exploration-driven.md` | — | intermediate | Exploration pattern. |
| `code-review.md` | — | intermediate | Review launch flow. |
| `qa-testing.md` | — | intermediate | QA follow-up workflow. |
| `task-decomposition.md` | — | intermediate | Parent/child decomposition. |
| `task-consolidation.md` | — | intermediate | Fold flow. |
| `follow-up-tasks.md` | — | intermediate | Sibling/follow-up pattern. |
| `retroactive-tracking.md` | — | intermediate | Wrap workflow. |
| `explain.md` | — | intermediate | Explain workflow. |
| `claude-web.md` | — | advanced | Claude Web remote agent flow. |
| `parallel-development.md` | — | advanced | Worktree-based parallel agents. |
| `parallel-planning.md` | — | advanced | Parallel plan production. |
| `issue-tracker.md` | — | advanced | GitHub/GitLab integration depth. |
| `pr-workflow.md` | — | advanced | PR lifecycle integration. |
| `revert-changes.md` | — | advanced | Destructive operation. |
| `releases.md` | — | advanced | Release-cut workflow. |
| `contribute-and-manage/_index.md` | — | — | Subsection landing. |
| `contribute-and-manage/contribution-flow.md` | — | advanced | Upstream contribution flow. |

## development/ (3 pages)

| Page | maturity | depth | Rationale |
|---|---|---|---|
| `_index.md` | — | — | Section landing. |
| `task-format.md` | — | advanced | Frontmatter schema reference — low-level. |
| `review-guide-format.md` | — | advanced | Review-guide schema reference. |

## Counts

- **main-concept:** 8 (overview, getting-started, tasks, plans, parent-child, locks, task-lifecycle, board/\_index, aitask-pick/\_index) — **9**
- **intermediate:** ~40
- **advanced:** ~35
- **experimental:** 3 (aitask-stats, aitask-add-model, tuis/stats/\_index)
- **stabilizing:** ~15 (TUI board/monitor/codebrowser/settings full sets, + 3 skills)
- **unlabeled:** ~12 (section landings + the title `_index`)

## Items to verify with the user

1. Should `overview.md` / `getting-started.md` carry `depth: main-concept` (expanded seed) or should main-concept stay tightly bounded to the 5 `concepts/` pages from the original marker text?
2. Should `board/_index.md` and `aitask-pick/_index.md` share `main-concept` with the 5 concepts pages, or is main-concept reserved exclusively for the `concepts/` section?
3. Is `aitask-stats.md` actually experimental, or just underused and otherwise stable? (Dormant ≠ experimental.)
4. Any feature the user knows is actively experimental that the heuristic missed (e.g., agent-crews — currently no docs page to label)?
