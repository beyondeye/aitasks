---
Task: t914_audit_and_complete_ait_command_reference_docs.md
Base branch: main
plan_verified: []
---

# Plan: Audit & complete the `ait` command reference docs (t914)

## Context

The website command reference at `website/content/docs/commands/_index.md` is
titled "Command Reference" / "Complete CLI reference for all ait subcommands"
but is materially incomplete. Several stable, user-facing subcommands are
missing from the index, only mentioned in passing, or documented on workflow/TUI
pages that the canonical reference never links to. This task corrects the
reference for stable, user-facing commands, improves `zip-old` discoverability,
fixes an inaccurate `zip-old` archive-format description, and spins out two
follow-ups (agentcrew docs; migrate-archives relevance). Brainstorm docs are
intentionally left to the existing task t776.

Per the user's steer: rather than relocating `zip-old`'s reference, gather all
periodic-maintenance commands (changelog, zip-old, explain cleanup, git-health)
onto a **new "Repository Maintenance" workflow page**, and improve `zip-old`
discoverability by framing + cross-linking to it.

## Gaps confirmed during exploration

`ait` dispatcher subcommands missing/under-documented in the index:
- `ait projects` (+ list/add/remove/update/prune/doctor/resolve/exec) — documented
  in `workflows/multi_project.md` + `workflows/cross_project_dependencies.md`, but
  absent from the command reference.
- `ait monitor`, `ait minimonitor`, `ait applink`, `ait stats-tui` — have TUI
  pages under `tuis/` but are not linked from the index TUI table.
- `ait git-health` — only a passing mention in `installation/_index.md`; no
  reference section.
- `ait skillrun` — only a passing mention; **already fully documented** in
  `concepts/skill-templating.md` (Invocation paths), so the index just needs a
  row linking there.
- `ait zip-old` — already in the index Tools row + has a full reference in
  `commands/issue-integration.md`, but: (a) its reference prose is **wrong** — it
  says `tar.gz` / `old1.tar.gz`, but `aitask_zip_old.sh` actually produces
  `tar.zst` / `old1.tar.zst`; (b) no "periodic maintenance" framing.

## Changes

### 1. New page: `website/content/docs/workflows/repo-maintenance.md`
Title "Repository Maintenance". Current-state-only prose, generic example names.
Frames the recurring upkeep of an aitasks-integrated repo and links each command
to its existing reference:
- **Archiving completed work** — `ait zip-old` → `../../commands/issue-integration/#ait-zip-old`
  (run periodically / post-release; bundles old completed task & plan files into
  numbered `tar.zst` archives).
- **Pruning explain caches** — `ait explain-cleanup` / `ait explain-runs --cleanup-stale`
  → `../../commands/explain/`.
- **Changelog / release prep** — `ait changelog` → `../../commands/issue-integration/#ait-changelog`,
  cross-link to `releases/`.
- **Diagnosing task-data worktree** — `ait git-health` → `../../commands/sync/#ait-git-health`.
- **Upgrading the framework** — `ait upgrade` (move to the latest or a specific
  version) → `../../commands/setup-install/#ait-upgrade`. Use the "move to a
  newer version" verb framing (not "reinstall/repair" — that's `ait setup`).
- "See also" → `releases/`, `multi_project/`.

### 2. `website/content/docs/workflows/_index.md`
Add a bullet under the **Git** grouping (after Releases) — the index body is
hand-curated, sidebar auto-builds but the body does not:
- `[Repository Maintenance](repo-maintenance/) — Periodic upkeep: archiving old tasks, pruning explain caches, changelog/release prep, diagnosing the task-data worktree.`

### 3. `website/content/docs/commands/_index.md` (the core audit fix)
- **TUI table:** add rows — `ait monitor` → `../tuis/monitor/`, `ait minimonitor`
  → `../tuis/minimonitor/`, `ait applink` → `../tuis/applink/`, `ait stats-tui`
  → `../tuis/stats/`.
- **Task Management table:** add `ait git-health` row → `sync/#ait-git-health`
  (near `ait git`), desc "Diagnose the `.aitask-data` worktree state".
- **New `### Cross-repo` section:** `ait projects` (+ subcommands) row →
  `../workflows/multi_project/` and `../workflows/cross_project_dependencies/`,
  desc covering list/add/remove/update/prune/doctor/resolve/exec.
- **Tools table:** add `ait skillrun` → `../concepts/skill-templating/` (desc
  "Launch a code agent with a profile-aware aitask skill"); keep the existing
  `ait zip-old` row but point/also-link it to the new maintenance workflow.
- Add a one-line pointer from the reference to the new
  `../workflows/repo-maintenance/` page (e.g. near the Tools/maintenance area).
- Add representative usage-example lines (`ait monitor`, `ait projects list`,
  `ait skillrun pick 42`, `ait git-health`) to the Usage Examples block.

### 4. `website/content/docs/commands/issue-integration.md` (fix + reframe `zip-old`)
- Correct the prose: `tar.gz` → `tar.zst`; path examples `old1.tar.gz` →
  `old1.tar.zst`, `old10.tar.gz` → `old10.tar.zst`; "compressed tar.gz archives"
  → "compressed `tar.zst` archives" (verified against `aitask_zip_old.sh:3-9,261`).
- Add a short note framing it as periodic maintenance, cross-linking
  `../workflows/repo-maintenance/`.

### 5. `website/content/docs/commands/sync.md` (give `ait git-health` a real home)
- Add a brief `## ait git-health` section (diagnose the `.aitask-data` worktree
  state; legacy-mode message). This is the link target for the index row + the
  maintenance page, satisfying "every entry links to a real reference page".

### 6. Two follow-up aitasks (created at Step 8c-style follow-up / during impl)
Via `aitask_create.sh --batch` (Batch Task Creation Procedure):
- **agentcrew docs** — concept page + `ait crew` subcommand reference
  (init/addwork/setmode/status/command/runner/report/cleanup/dashboard/logview).
  Substantial separate effort.
- **migrate-archives relevance** — evaluate whether to keep / hide / remove
  `ait migrate-archives` before deciding whether/how to document it.
- Brainstorm: **no new task** — reference existing **t776** in the maintenance/
  TUI context where relevant.

## Out of scope (per task)
- `ait brainstorm` docs (tracked by t776).
- agentcrew/migrate-archives actual documentation (only follow-ups created).
- No change to `tuis/_index.md` (already lists every TUI; the gap was the
  *command index* not linking them).

## Conventions to honor
- Current-state-only prose (no "previously/used to"); generic placeholder project
  names for cross-repo examples; no "sister" repo terminology.
- New workflows page requires the manual `_index.md` bullet (change 2).

## Verification
- `cd website && hugo build --gc --minify` — must build with no broken-ref
  errors (Hugo `relref`/`ref` fail the build on dangling links).
- `cd website && ./serve.sh` and spot-check: command index links for monitor /
  minimonitor / applink / stats-tui / projects / git-health / skillrun all
  resolve; the new Repository Maintenance page renders and appears in the
  Workflows sidebar + index body; `zip-old` section shows `tar.zst`.
- `grep -rn "tar.gz" website/content/docs/commands/issue-integration.md` returns
  nothing in the zip-old section.
- Confirm the two follow-up tasks exist via `ait ls`.

## Step 9 (post-implementation)
Standard cleanup/archival per task-workflow Step 9 (this profile works on the
current branch — no worktree/merge). Follow-up tasks created at Step 8 follow-up
gates.

## Risk

### Code-health risk: low
- Documentation-only change; no code, scripts, or config touched. New page +
  edits to existing Markdown. Worst case is a broken Hugo `relref` (caught by the
  `hugo build` verification step). · severity: low · → mitigation: none

### Goal-achievement risk: low
- The audit could miss a stable subcommand, or a link could point to the wrong
  anchor. Bounded and self-correcting: the task's Findings table enumerates the
  exact gaps, and `hugo build` fails on dangling refs. · severity: low ·
  → mitigation: none

No risks warrant before/after mitigation follow-up tasks.

## Post-Review Changes

### Change Request 1 (2026-06-02)
- **Requested by user:** Place the Repository Maintenance page in its own
  "Maintenance" section in the workflows index, not under the "Git" grouping.
- **Changes made:** Moved the `repo-maintenance` bullet out of `## Git` into a
  new `## Maintenance` section in `workflows/_index.md`; updated the t594_7
  taxonomy comment from "four groupings … / Git" to "five groupings … / Git /
  Maintenance". (Page weight unchanged — sidebar ordering is weight-driven and
  independent of the manual index-body grouping.)
- **Files affected:** `website/content/docs/workflows/_index.md`

### Change Request 2 (2026-06-02)
- **Requested by user:** The new Maintenance section's intro paragraph
  duplicated the single bullet's description — keep only the bullet.
- **Changes made:** Removed the Maintenance section intro sentence, leaving the
  `## Maintenance` heading + the `repo-maintenance` bullet.
- **Files affected:** `website/content/docs/workflows/_index.md`

### Change Request 3 (2026-06-02)
- **Requested by user:** Mention that after `ait upgrade` it is best to also run
  `ait setup`.
- **Changes made:** Expanded the "Upgrading the framework" section of
  `repo-maintenance.md` to recommend running `ait setup` after `ait upgrade`
  (populates newly added scripts/skills/dependencies), keeping the
  upgrade-vs-setup verb distinction from CLAUDE.md.
- **Files affected:** `website/content/docs/workflows/repo-maintenance.md`

### Change Request 4 (2026-06-02)
- **Requested by user:** Drop the trailing upgrade-vs-setup sentence ("Use
  `ait upgrade` to move to a newer version, and `ait setup` to reinstall...").
- **Changes made:** Removed that sentence from the "Upgrading the framework"
  section, leaving the recommendation to run `ait setup` after `ait upgrade`.
- **Files affected:** `website/content/docs/workflows/repo-maintenance.md`

## Final Implementation Notes
- **Actual work done:** Audited the `ait` dispatcher against the docs tree and
  completed the command reference: added TUI rows (monitor, minimonitor,
  applink, stats-tui), a `git-health` row, a new Cross-repo section
  (`ait projects`), and a `skillrun` row to `commands/_index.md`; added a brief
  `## ait git-health` reference section to `commands/sync.md`; fixed the
  inaccurate `tar.gz`→`tar.zst` prose in the `zip-old` reference and added
  periodic-maintenance framing; created a new `workflows/repo-maintenance.md`
  page (zip-old, explain cleanup, changelog, git-health, `ait upgrade`) and
  wired it into the workflows index under a new Maintenance section.
- **Deviations from plan:** zip-old discoverability handled via the new
  maintenance workflow page (per user steer) rather than relocating the
  reference. Repository Maintenance placed in its own index section (CR1) rather
  than the Git grouping.
- **Issues encountered:** None. Confirmed `aitask_zip_old.sh` produces `tar.zst`
  (script lines 3-9, 261), making the prior `tar.gz` doc prose a genuine error.
- **Key decisions:** Command-reference uses plain markdown links (not Hugo
  `relref`), which `hugo build` does NOT validate — so every new plain link's
  target page + heading anchor was verified directly in the built HTML under
  `public/`. All resolved.
- **Upstream defects identified:** None.
- **Follow-ups created:** t917 (agentcrew docs — concept page + `ait crew`
  reference), t918 (evaluate `ait migrate-archives` relevance). Brainstorm docs
  intentionally left to existing t776.
