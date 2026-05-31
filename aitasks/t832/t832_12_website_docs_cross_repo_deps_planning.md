---
priority: medium
effort: medium
depends: [t826_3]
issue_type: documentation
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-31 22:10
updated_at: 2026-05-31 22:46
---

## Context

Sibling t826_3 shipped the user-facing website page
`website/content/docs/workflows/multi_project.md` covering the **registry /
projects layer** of cross-repo support (project identity, the per-user
registry, the `ait projects` subcommand, `ait create --project`, cross-repo
notation as a writing convention, and the TUI switcher's inactive/stale-project
behavior).

That page deliberately defers the **cross-repo dependency / planning / data
layer** introduced by task 832. This task documents that second layer as its
own user-facing workflow page so the website covers the full cross-repo
surface.

Per CLAUDE.md "Documentation Writing": current state only — no migration notes,
no version history. Per project convention, use **generic placeholder project
names** in examples (e.g. `frontend` / `backend` / `shared-lib`), never the
author's actual sibling repos.

## Key Files to Modify or Create

- **Create** `website/content/docs/workflows/cross_project_dependencies.md`
  (working name) — a new workflow page. Pick a non-colliding `weight` near
  `multi_project.md` (48) — e.g. 49 — so it sits beside the multi-project page
  in the "Parallel" group. Mirror the Docsy frontmatter + structure of
  `multi_project.md` and `manual-verification.md`.
- **Update** `website/content/docs/workflows/_index.md` — add a bullet under
  the **## Parallel** group linking the new page.
- **Cross-link** the existing `website/content/docs/workflows/parallel-planning.md`
  and `multi_project.md` to/from the new page where relevant.
- **Append** a "See also" cross-link in `aidocs/cross_repo_references.md`
  pointing at the new page (the multi_project page is already linked there).

## Required Page Content (the t832-family surface)

1. **Cross-repo task dependencies (`xdeps` / `xdeprepo`)** — frontmatter schema
   (`xdeprepo: <name>` scalar, `xdeps: [N, N_M, ...]` list referencing the
   sister project's task IDs); how blocking works (a cross-repo dep is
   satisfied only when the sister task is `Done`, mirroring local `depends:`);
   and the UNREACHABLE behavior when the sister repo cannot be resolved
   (NOT_FOUND / STALE).
2. **Cross-repo notation parsing + `ait board`** — the `aitasks#835_3` /
   `<proj>:path` notation is now parsed (`.aitask-scripts/lib/cross_repo_notation.py`),
   surfaced on board task cards, and navigable via a read-only cross-repo
   reference popup. (Note the known board picker keyboard-nav bug is tracked
   separately as t886 — do not document it as working until fixed.)
3. **Cross-repo data retrieval (`--project <name>`)** — read-side helpers
   accept `--project <name>` to query a sibling project:
   `ait ls --project`, `ait explain --project` (and the underlying
   `aitask_query_files.sh` / `aitask_find_by_file.sh`). Include the cross-repo
   file notation `<proj>:path/to/file` consumed by `ait explain`.
4. **Cross-repo task mutation (`ait update --project`)** — symmetric to
   `ait create --project`; lets you set the back-edge on a sister task. Document
   the guardrails: it refuses when the sister task is locked by a different
   host/email, and only an administrative subset of fields is allowed
   (`--xdeps`, `--xdeprepo`, `--labels`, `--priority`, `--effort`, `--depends`,
   `--postpone`, `--assigned-to`); it refuses `--status Implementing` and
   `--status Done`.
5. **Interactive `ait create` cross-repo flow** — the fzf-driven interactive
   creator can declare `xdeprepo` and add cross-repo task/file references in the
   description.
6. **Parallel cross-repo planning** — the planning rule that a single parent's
   children never straddle two repos; instead you create **two parents (one per
   repo)** joined by cross-repo edges (`xdeps:` + `xdeprepo:`). Summarize the
   lockstep numbering and commit ordering at a user-appropriate altitude and
   cross-link the existing Parallel Planning page. The procedure lives at
   `.claude/skills/task-workflow/parallel-cross-repo-planning.md`.

## Reference Files for Patterns

- `website/content/docs/workflows/multi_project.md` (sibling t826_3) — the
  registry-layer page; match its structure, tone, and generic-example
  convention; cross-link it for the registry/`ait projects` background.
- `website/content/docs/workflows/manual-verification.md` — typical workflow
  page structure.
- `aidocs/cross_repo_references.md` — authoring-side reference (registry +
  notation). Source of truth for notation patterns.
- Source of truth for shipped behavior (read the archived plans before
  drafting): `aiplans/archived/p832/p832_3_*` (xdeps parser/schema),
  `p832_4_*` (blocking logic), `p832_7_*` (`update --project` guardrails),
  `p832_8_*` (board display/navigation), `p832_2_*` (`explain --project`),
  `p832_5_*` (parallel cross-repo planning), `p832_10_*` (interactive create).

## Implementation Plan

1. Read the archived t832 child plans listed above to capture the actually
   shipped behavior (including any Final Implementation Notes deviations).
2. Draft `cross_project_dependencies.md` following the 6-section outline.
3. Wire the nav bullet in `_index.md`; add cross-links to/from
   `multi_project.md` and `parallel-planning.md`.
4. Append the "See also" cross-link in `aidocs/cross_repo_references.md`.
5. Build-verify.

## Verification Steps

- `cd website && hugo build --gc --minify` — clean build, no warnings
  (run `npm install` first if deps are missing).
- `cd website && ./serve.sh` — visually inspect the new page renders, code
  blocks format, and the sidebar entry appears under Parallel.
- Click through cross-links between the new page, `multi_project.md`,
  `parallel-planning.md`, and `aidocs/cross_repo_references.md`.

## Out of Scope

- The registry / `ait projects` / `ait create --project` surface — already
  documented in `multi_project.md` (t826_3).
- Fixing the board cross-repo picker keyboard-nav bug (tracked as t886).
- Non-English locale translations; website design/nav structural changes.
