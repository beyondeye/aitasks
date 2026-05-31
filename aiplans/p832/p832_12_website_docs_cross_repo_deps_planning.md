---
Task: t832_12_website_docs_cross_repo_deps_planning.md
Parent Task: aitasks/t832_brainstorm_cross_repo_skills_retrieval_xdeps_parallel_planni.md
Sibling Tasks: aitasks/t832/t832_11_aitask_explore_cross_repo.md, aitasks/t832/t832_6_retrospective_dogfooding_evaluation.md
Archived Sibling Plans: aiplans/archived/p832/p832_10_aitask_create_interactive_cross_repo.md, aiplans/archived/p832/p832_1_cross_repo_retrieval_reexec_trio.md, aiplans/archived/p832/p832_2_explain_context_cross_repo.md, aiplans/archived/p832/p832_3_xdeps_parser_and_validation.md, aiplans/archived/p832/p832_4_xdeps_blocking_logic.md, aiplans/archived/p832/p832_5_parallel_cross_repo_planning_procedure.md, aiplans/archived/p832/p832_7_cross_repo_task_update.md, aiplans/archived/p832/p832_8_ait_board_cross_repo_support.md, aiplans/archived/p832/p832_9_manual_verification_auto.md
Base branch: main
plan_verified: []
---

# Plan: Website docs for cross-repo dependency/planning/data layer (t832_12)

## Context

Sibling t826_3 shipped `website/content/docs/workflows/multi_project.md`, which
documents the **registry layer** of cross-repo support (project identity, the
per-user registry, `ait projects`, `ait create --project`, and cross-repo
notation as an authoring convention). That page deliberately defers the
**second layer** that the t832 family added: cross-repo task *dependencies*,
cross-repo *data retrieval / mutation*, board surfacing, the interactive
create flow, and paired cross-repo *planning*.

This task documents that second layer as its own user-facing workflow page so
the website covers the full cross-repo surface. Per CLAUDE.md "Documentation
Writing": current-state only, no migration/version notes. Per project
convention: generic placeholder project names (`frontend` / `backend` /
`shared-lib`), never the author's real repos.

**Terminology rule (per user instruction):** never use "sister" repo
terminology. Use **cross-repo** or **linked repo / linked project** instead.
This applies to the new page (write it cross-repo/linked from the start) and
requires scrubbing the existing "sister" occurrences out of
`multi_project.md` (see modify item 5).

Shipped-surface facts were extracted from the archived t832 child plans
(`aiplans/archived/p832/p832_{1,2,3,4,5,7,8,10}_*`) and cross-checked against
`aidocs/cross_repo_references.md` and the t886 fix commit. Key corrections vs.
the original brainstorm wording:

- **Field names that shipped are `xdeps` (list) / `xdeprepo` (scalar)** — NOT
  `xdepends`/`xdependrepo`.
- **`xdeprepo` alone is valid** (intent-only mode, used by the planning
  trigger); only `xdeps` *without* `xdeprepo` is an error.
- **Blocking is `Done`-only**: a cross-repo dep is satisfied only when the
  sister task is `Done`; resolver failure (unregistered/STALE) → blocked +
  `UNREACHABLE` (STALE and NOT_FOUND collapse to one `UNREACHABLE` label).
- **The board picker keyboard-nav bug (t886) is FIXED** (commit `4c3b5df1`,
  status Done) — document the multi-ref popup picker as fully keyboard-navigable.
- `ait update --project` refuses `--status Implementing|Done|Folded` and
  `--name`, plus a lock-by-different-host refusal.

## Files to create / modify

### 1. CREATE `website/content/docs/workflows/cross_project_dependencies.md`

New Docsy workflow page. Frontmatter (mirrors `multi_project.md`):

```yaml
---
title: "Cross-Project Dependencies"
linkTitle: "Cross-Project Deps"
weight: 49        # free slot between multi_project.md (48) and claude-web.md (50)
description: "Block, read, update, and plan tasks across sibling aitasks projects with cross-repo dependencies and the --project flag"
depth: [advanced]
---
```

Section outline (covers the task's 6 required topics, ordered for reading flow;
uses `frontend` / `backend` / `shared-lib` placeholder names throughout):

1. **Intro** — one short lead: builds on the [Multi-Project](multi_project/)
   registry layer (logical names + `ait projects`); this page is the
   dependency / data / planning layer on top. **Open with an explicit
   prominent forward link to Multi-Project** so the two pages read as a pair —
   the reader should land here understanding the registry page is the
   prerequisite/companion. Link `multi_project/` for the registry background.

2. **`## Cross-repo task dependencies`** — the `xdeprepo` (scalar) / `xdeps`
   (list) frontmatter pair; example YAML (`xdeprepo: backend`,
   `xdeps: [42, 16_2]`); IDs use the sister repo's local `N` / `N_M` form.
   Blocking semantics: satisfied only when the sister task is `Done`; any other
   status blocks. The `xdeprepo`-alone intent-only case (sets up paired
   planning, see below). Note `xdeps` without `xdeprepo` is rejected.

3. **`### When the sister project can't be found`** (subsection) — `UNREACHABLE`:
   if the name is unregistered or STALE the dep stays blocked and `ait ls`
   shows `Blocked (by backend#42 (UNREACHABLE))`. Fix = register/repoint via
   `ait projects add` (cross-link multi_project's resolver states).

4. **`## Seeing cross-repo references on the board`** — `ait board` parses the
   `backend#42` notation in task bodies and the `xdeps` frontmatter; cards show
   a distinct `↗ backend#42 [Implementing]` line and a `🌐 blocked
   (cross-repo)` chip when a dep is unmet. Press `#` on a card with cross-repo
   refs to open the read-only reference popup; multiple refs open a
   keyboard-navigable picker (Tab cycles refs + Cancel). Read-only — no lock,
   no pick.

5. **`## Reading another project's tasks and files`** — the `--project <name>`
   read flag. `ait ls --project backend` lists the sister's table;
   `ait explain --project backend:path/to/file` (colon-separated pair, mention
   it's repeatable) and the inline `backend#path/to/file` positional token pull
   sister-project history. Note these resolve the name via the registry at call
   time (no `../` paths). Keep at user altitude — mention the underlying
   `aitask_query_files.sh --project … task-status` only as a one-liner if
   helpful, not a deep dive.

6. **`## Updating a task in another project`** — `ait update --batch --project
   backend <id> …`. Allowed administrative fields: `--priority`, `--effort`,
   `--xdeps`/`--xdeprepo`, `--add-label`, `--boardcol`/`--boardidx`,
   `--assigned-to`, `--status` (Ready/Editing/Postponed only). Guardrails:
   refuses `--status Implementing`, `--status Done`, `--status Folded` (those
   must go through the sister's own `/aitask-pick`), refuses `--name`, and
   refuses if the sister task is locked by a different host/owner. `--project`
   requires `--batch`.

7. **`## Declaring cross-repo links when creating a task`** — interactive
   `ait create` (no flags) now has a "Cross-repo project" fzf select; once a
   sibling is picked, two extra reference menu items appear ("Add cross-repo
   archived task reference" → appends `backend#42`, "Add cross-repo file
   reference" → appends `backend:src/foo.rs`). Note: interactive flow sets
   `xdeprepo` (intent) only — explicit `xdeps` stay batch-only
   (`--batch --xdeps 42,16_2 --xdeprepo backend`). Cross-link multi_project's
   notation section.

8. **`## Planning paired work across two repos`** — user-altitude summary of
   the paired-planning rule: a single parent's children never straddle two
   repos; instead you create **two parents (one per repo)** joined by
   cross-repo edges (`xdeps` + `xdeprepo`). When you `/aitask-pick` a task that
   has `xdeprepo` set, the planning phase offers to plan it as a paired
   cross-repo decomposition (lockstep child numbering, each repo's hierarchy
   locally complete, cross-repo commits land in each repo's own `./ait git`).
   Cross-link [Parallel Planning](parallel-planning/) for the in-repo
   decomposition mechanics.

9. **`## See also`** — links to Multi-Project, Parallel Planning, and a one-line
   pointer that the authoring-side reference is `aidocs/cross_repo_references.md`
   (internal). (Keep external/internal distinction: the See also lists the two
   sibling website pages; aidocs is a repo-internal note.)

### 2. UPDATE `website/content/docs/workflows/_index.md`

Add a bullet under the `## Parallel` group, right after the Multi-Project line
(line 31), linking the new page:

```markdown
- [Cross-Project Dependencies](cross_project_dependencies/) — Block, read, update, and plan tasks across sibling projects with cross-repo dependencies and the `--project` flag.
```

### 3. CROSS-LINK existing pages → new page

**Explicit bidirectional pairing of Multi-Project ↔ Cross-Project Dependencies
(per user instruction).** Each page must clearly point at the other:

- `multi_project.md` → new page: add a prominent forward-pointer. Best spot is
  the end of the "Referring to cross-project tasks and files" section (which
  introduces the `backend#835_3` / `backend:path` notation that the new page's
  dependency/data layer consumes) — a one-line link such as: *"Once names
  resolve, see [Cross-Project Dependencies](cross_project_dependencies/) to
  block, read, update, and plan tasks across those projects."* Optionally also
  surface it from the page intro so the pairing is visible up top.
- new page → `multi_project.md`: the intro forward link from section 1 above
  (and a See also entry) closes the loop.
- `parallel-planning.md` → new page: add a one-line note pointing at the new
  page's paired-planning section for the cross-repo variant of decomposition.

### 4. APPEND to `aidocs/cross_repo_references.md`

Add a bullet under the existing `## See also` section pointing at the new page
(the multi_project page is already linked there):

```markdown
- User-facing workflow guide:
  `website/content/docs/workflows/cross_project_dependencies.md` — cross-repo
  dependencies (`xdeps`/`xdeprepo`), `--project` data retrieval/mutation, board
  surfacing, and paired cross-repo planning, written for end users.
```

### 5. SCRUB "sister" from `website/content/docs/workflows/multi_project.md`

Replace the 3 "sister" occurrences (all in the Recipe section) with "linked":

- Line 134 `## Recipe: register a sister project and spawn a task in it`
  → `## Recipe: register a linked project and spawn a task in it`
- Line 137 `# 1. Make sure the sister project declares its identity`
  → `# 1. Make sure the linked project declares its identity`
- Line 148 `# 4. File a coordination task in the sister project`
  → `# 4. File a coordination task in the linked project`

(Pre-existing "sibling" usage is left as-is — only "sister" was flagged. The
new page itself uses cross-repo / linked terminology throughout.)

## Out of scope

- Registry / `ait projects` / `ait create --project` surface (already in
  `multi_project.md`).
- Non-English locales; website nav/design structural changes.

## Verification

1. `cd website && npm install` (if deps missing) `&& hugo build --gc --minify`
   — clean build, no warnings, no broken `relref`/relative links.
2. `cd website && ./serve.sh` — visually confirm: the page renders, code blocks
   format, the sidebar shows "Cross-Project Deps" under Parallel (right after
   Multi-Project), and cross-links between the new page, `multi_project.md`,
   `parallel-planning.md` all resolve.
3. Skim for the doc conventions: current-state-only phrasing, generic project
   names only (no `aitasks`/`aitasks_mobile`), accurate field names
   (`xdeps`/`xdeprepo`).

## Post-implementation

Follow task-workflow Step 8 (review) → Step 9 (archival of t832_12 child task
and plan). This is a child of t832; the archived plan becomes sibling context.
