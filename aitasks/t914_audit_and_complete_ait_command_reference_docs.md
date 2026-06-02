---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-06-02 13:37
updated_at: 2026-06-02 16:41
boardidx: 30
---

## Context

The website command reference at `website/content/docs/commands/_index.md` is
titled "Command Reference" with description "Complete CLI reference for all ait
subcommands" — but it is materially incomplete. An audit of the `ait`
dispatcher against the docs tree found that several stable, user-facing
subcommands are either missing from the command index, only mentioned in
passing, or documented elsewhere (workflow pages) but not discoverable from the
canonical command reference.

This task corrects the command reference for **stable, user-facing** commands.
The brainstorm TUI, agentcrew, and `migrate-archives` are explicitly carved out
(see Deferred follow-ups).

## Findings (gaps to close)

The `commands/_index.md` reference tables omit or under-document:

| Subcommand | Current state | Desired |
|---|---|---|
| `ait projects` (+ list/add/remove/update/prune/doctor/resolve/exec) | Documented in `workflows/multi_project.md` + `workflows/cross_project_dependencies.md`, but **absent from the command reference index** | Add to the command reference (new "Cross-repo" / projects section or row), linking to the existing workflow pages. The index claims to be complete; cross-repo `projects` must be findable from it. |
| `ait monitor` | Full page at `tuis/monitor/`, **not linked** from command index TUI table | Add a TUI-table row linking to `../tuis/monitor/` |
| `ait minimonitor` | Page at `tuis/minimonitor/`, not linked | Add TUI-table row → `../tuis/minimonitor/` |
| `ait applink` | Full page at `tuis/applink/`, not linked | Add TUI-table row → `../tuis/applink/` |
| `ait stats-tui` | Page at `tuis/stats/`, not linked | Add row (Reporting/TUI) → `../tuis/stats/` |
| `ait git-health` | Passing mention only (`installation/_index.md`) | Add a brief reference entry (diagnose the `.aitask-data` worktree state); link from the Task Management / sync area near `ait git` |
| `ait skillrun` | Passing mention only (`concepts/skill-templating.md`) | Add a brief reference entry (launch a code agent with a profile-aware aitask skill); Tools section |

## zip-old discoverability + framing

`ait zip-old` IS documented (`commands/issue-integration.md#ait-zip-old`, full
reference) but:

- It lives under "issue-integration.md", an unintuitive home for an
  archival/cleanup command — hard to discover.
- The operational guidance the maintainer cares about — that it should be run
  **periodically** to keep completed task/plan files tidy — only appears as a
  post-release step in `workflows/releases.md`. There is no general "maintenance
  you run from time to time" framing.

Action: improve discoverability (consider relocating the `zip-old` reference
to a more fitting section, or at minimum cross-linking it from the Tools
section near the explain-cleanup entries) and add a short note framing it as
periodic maintenance. Verify the prose accurately describes its effect
(archives old completed task/plan files into numbered tar.zst bundles).

NOTE: `ait explain-cleanup` was reviewed and found **adequately documented**
(`commands/explain.md`, full reference alongside `explain-runs`, including the
auto-cleanup relationship). No change needed there beyond ensuring the index
links remain correct.

## Out of scope — Deferred follow-ups

These are intentionally NOT part of this task:

1. **`ait brainstorm` docs** — already tracked by existing task
   **t776** (`brainstorm_tui_user_facing_docs`, gated behind t749_8
   verification). Do not document brainstorm here; reference t776.
2. **agentcrew / `ait crew` docs** — the entire agent-crews concept is
   undocumented and should be, but that is a substantial separate effort.
   **Create a new follow-up documentation task** for it (concept page + crew
   subcommand reference: init/addwork/setmode/status/command/runner/report/
   cleanup/dashboard/logview). Do not attempt it here.
3. **`ait migrate-archives` relevance** — uncertain this should remain an `ait`
   subcommand at all; archive-format migration (tar.gz → tar.zst) was a
   one-time past concern that may no longer be relevant to end users. **Create
   a separate follow-up** to evaluate whether to keep, hide, or remove it
   before deciding whether/how to document it. Do NOT document it in this task.

## Acceptance

- `commands/_index.md` accurately reflects all stable user-facing subcommands,
  with every entry linking to a real reference/TUI/workflow page.
- Cross-repo `projects` is discoverable from the command reference.
- `zip-old` is discoverable and framed as periodic maintenance with accurate
  prose.
- Two follow-up tasks created (agentcrew docs; migrate-archives relevance);
  brainstorm references t776.
- Docs follow project conventions (current-state-only prose; generic example
  project names for any cross-repo examples; no "sister" repo terminology).
