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
updated_at: 2026-10-20 12:34
---

## Context

This task is part of t2074, which removes legacy repository mode. The user
explicitly asked for a **full website documentation sweep** as its own
deliverable. Inventorying the pages is not enough: the work counts as done only
with a written sweep report and passing validation.

It depends on t2074_3 (the final setup, migration, repair and upgrade-notice
behaviour) and t2074_9 (the final refusal diagnostics and the `git-health`
output). Read `aiplans/p2074_remove_legacy_repository_mode_support.md`
sections C0, C1 and C4 (states, recovery matrix) and "Unrelated legacy
(exclude)". Follow `aidocs/framework/documentation_conventions.md`: state only
current behaviour, keep version history out of doc bodies, and redirect
cross-references when content moves.

## Scope: audit ALL of website/content/

Look at every section: getting-started, installation and upgrades, repository
structure, setup and configuration, command references, workflows, TUIs,
troubleshooting and crash recovery, development and contribution, examples,
diagrams, snippets, navigation, and reusable content.

Search for two kinds of text:
- **Explicit terms:** `legacy mode`, `LEGACY_MODE`, an optional or separate
  data branch.
- **Implicit promises:**
  - tasks stored on main or on the code branch;
  - declining data-branch setup;
  - a choice between layouts;
  - a plain-git fallback;
  - instructions that omit the required layout or assume real task
    directories in the code checkout.

Known hits to start from (not exhaustive):
- `overview.md:48`
- `installation/_index.md` :60-62, :89 (quotes the old `git-health` output) and
  :98-104
- `commands/setup-install.md`. Add:
  - the required data-branch step;
  - migration of an existing legacy project, where declining aborts and
    changes nothing;
  - broken-layout repair;
  - the upgrade notice.
- `commands/sync.md` :148, :206-218 and :386-394
- `concepts/git-branching-model.md:29`
- `development/_index.md` :124-133
- `workflows/parallel-development.md` :16 and :24;
  `workflows/repo-maintenance.md:56`
- `tuis/board/how-to.md:484`; `tuis/board/reference.md` :594 and :704-716
- `tuis/syncer/_index.md` :277 and :289. Keep this row only as an
  unconverted-destination refusal.
- `skills/aitask-pickrem.md:38` and `skills/aitask-pickweb.md:54`
- Add a new section, **"Unsupported or damaged layouts"**: a table of each
  state and reason from C1a/C1b, the exact refusal text, the C4 recovery for
  each, and the conversion procedure.

Leave the blog posts alone (`blog/v070-*`, `blog/v0181-*`). They are history.
Keep unrelated uses of "legacy": PID-less locks in `crash-recovery.md:52`, tmux
legacy sockets, archive formats, and the others listed in the parent plan.

Revise any screenshots or diagrams that show the retired choice. Repair links
and navigation wherever pages or sections move. Prefer `{{< relref >}}`.

**aidocs:** `aidocs/framework/aitasks_extension_points.md` :122-125 and
`aidocs/framework/tui_conventions.md:476` (refusal row wording). Also check
every other maintained aidocs file that mentions the optional data branch.

## Deliverable: website sweep report

Put the report in this task's Final Implementation Notes, in three parts:
- every page and section reviewed;
- the change made in each, or "no change needed" with the reason;
- every retained reference, with its justification.

## Verification

Run from `website/`:
- `hugo build --gc --minify`
- `python3 check_links.py --build`. This must pass.
- `python3 check_link_relevance.py`. Triage every reported link by opening each
  target, as the "link triage = every target opened" memory requires.
