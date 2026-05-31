---
Task: t826_3_website_docs_multi_project_workflow.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/archived/t826/t826_1_*.md, aitasks/archived/t826/t826_2_*.md, aitasks/archived/t826/t826_7_*.md, aitasks/archived/t826/t826_8_*.md, aitasks/archived/t826/t826_9_*.md, aitasks/archived/t826/t826_10_*.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_*.md, p826_2_*.md, p826_7_*.md, p826_8_*.md, p826_9_*.md, p826_10_*.md
Worktree: (profile 'fast' — works on current branch, no worktree)
Branch: (profile 'fast' — current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-05-31 21:57
---

# Plan: Website docs — multi-project workflow page (t826_3)

## Context

t826_3 is the (originally) final step of t826: a user-facing Hugo/Docsy page
documenting cross-repo / multi-project work. The task was written against only
the t826_1 + t826_2 surface. Since then the cross-repo surface grew
substantially, so per the task's **IMPORTANT UPDATE** the scope was
re-evaluated against everything shipped.

**Re-evaluation outcome (verify pass).** The shipped cross-repo surface splits
into two families:

- **t826 family — registry / projects layer (this page's scope).** Per-project
  identity, the per-user registry, the `ait projects` subcommand — now **8
  verbs** (list/add/resolve/exec **+ remove/update/prune/doctor** from
  t826_7/8/9), `aitask_create.sh --project`, cross-repo notation as a *writing
  convention*, and TUI-switcher inactive/stale-project behavior (t826_2,
  t826_10). `ait monitor` unchanged.
- **t832 family — cross-repo deps / planning / data layer (deferred to a
  follow-up).** `xdeps`/`xdeprepo` dependencies, the notation parser +
  `ait board` cross-repo display/navigation, `--project` on read-side helpers,
  `aitask_update.sh --project`, interactive `ait create` cross-repo, and the
  parallel cross-repo planning procedure.

**Decisions (confirmed with user):**
1. This page documents the **full 8-verb** registry/projects surface (not just
   the original 4 core verbs).
2. A **child of t832 (t832_12)** documentation task is created to cover the
   t832-family features.

**Scan for forgotten cross-repo work (per task request):** the cross-repo task
family is t826_* (registry layer, all Done except this), t832_* (deps/planning,
mostly Done; t832_6 retrospective + t832_11 explore-dispatch still Ready), plus
t857 (manual-verify t832_10), t858 (aitask-create skill cross-repo), t872 /
t887 (manual-verify carry-overs), t886 (board picker keyboard-nav bug). All are
already tracked — the only *documentation* gap is t832's user-facing surface,
which t832_12 (created here) closes.

Doc-writing rules:
- CLAUDE.md "Documentation Writing": **current state only** — no "previously
  we…", no migration notes, no version history.
- **Generic example project names only.** Every example in the page uses
  generic placeholder project names (e.g. `frontend` / `backend` /
  `shared-lib`), never the author's actual sibling repos (`aitasks` /
  `aitasks_mobile`). "aitasks project" as the generic framework term is fine;
  concrete *example* project names must be made up.

## Files to change

### 1. New page: `website/content/docs/workflows/multi_project.md`

Frontmatter (mirror `manual-verification.md` conventions; weight 48 slots it in
the "Parallel" group between `parallel-planning` (45) and `claude-web` (50)):

```yaml
---
title: "Multi-Project Workflow"
linkTitle: "Multi-Project"
weight: 48
description: "Coordinate work across sibling aitasks projects with the project registry, ait projects, and cross-repo task creation"
depth: [advanced]
---
```

Section outline (plain markdown, ``` ```bash ``` code fences, standard tables,
relative links — no Docsy alert shortcodes, matching neighbors):

1. **Why** — `../aitasks/` path brittleness (other machines, cloud agents,
   re-clones); logical names resolved at call time.
2. **Per-project identity** — `project:` block in
   `aitasks/metadata/project_config.yaml` (`name`, `git_remote`; name defaults
   to directory basename). Schema table + example.
3. **The project registry** — `~/.config/aitasks/projects.yaml` schema (name /
   path / git_remote / last_opened) shown with generic example entries (e.g.
   `frontend`, `backend`), gitignored, managed by `ait projects add`,
   `AITASKS_PROJECTS_INDEX` override. Resolution order (live tmux scan →
   per-user index → `AITASKS_PROJECT_<name>` env var) and the
   `RESOLVED:` / `NOT_FOUND:` / `STALE:` status vocabulary (LIVE/OK/STALE).
4. **`ait projects` subcommand reference** — table of **all 8 verbs** with
   signatures + a usage example each:
   - Core: `list`, `add [<path>]`, `resolve <name>`, `exec <name> -- <cmd>`
   - Management: `remove <name> [--force]`, `update <name> <new_path>`,
     `prune [--dry-run] [--yes]`, `doctor [--clone]`
   Source of truth for wording = the help block in
   `.aitask-scripts/aitask_projects.sh` (lines 44–96) — quote signatures
   faithfully, condensed for users.
5. **Cross-repo task creation** — `ait create --batch --project <name>`
   walkthrough (requires `--batch`; cannot combine with `--parent`). Generic
   example: from one project (e.g. `frontend`), create a sister task in another
   (e.g. `backend`) with no `cd`.
6. **Cross-repo notation in plans / commits** — preferred `backend#835_3`
   (no `t`), accepted `backend#t835_3`; file notation `backend:path/to/file`
   (generic example names). Present as the canonical writing convention (the
   deeper tooling — board
   navigation, dependency parsing — is the t832_12 follow-up's scope; do **not**
   forward-reference that page until it exists).
7. **TUI switcher: inactive & stale projects** — registered-but-inactive
   projects appear in the switcher even with no live tmux session; selecting one
   spawns its tmux session and teleports. Stale entries render dimmed with a
   `(stale)` suffix and offer prune / repoint via a modal. **Explicit note:
   `ait monitor` is unchanged — its multi-project view stays scoped to live
   tmux sessions.**
8. **Recipe** — "Register a sister project and spawn a task there":
   copy-pasteable `ait projects add` → `ait projects list` →
   `ait create --batch --project <name> …` sequence.

### 2. Nav wiring: `website/content/docs/workflows/_index.md`

Sidebar is auto-discovered from `weight`, so no menu file edit is needed. But
`_index.md` carries a **manual** human-readable link list grouped into Tasks /
Parallel / Review & Quality / Git. Add one bullet under **## Parallel**:

```markdown
- [Multi-Project](multi_project/) — Coordinate work across sibling aitasks projects with the project registry and cross-repo task creation.
```

### 3. Cross-link + staleness fix: `aidocs/cross_repo_references.md`

- **Append the required cross-link** to the new website page (the task
  mandates this). Add a short "See also" pointer to
  `website/content/docs/workflows/multi_project.md`.
- **Correctness fix (co-located):** the "What is NOT in scope (planned for
  follow-ups)" list (lines 160–168) names several items that have since
  shipped — notation parser (`cross_repo_notation.py`), `ait projects remove` /
  `prune`, TUI switcher t826_2, website docs t826_3. Trim those to keep only
  genuinely-pending items (cross-project parent linkage, auto-clone). Keep this
  edit tight — it is the cross-link's immediate neighbor and leaving false
  "not-in-scope" claims would misinform future authors.

### 4. Follow-up task (created during implementation, not in plan mode): t832_12

`issue_type: documentation`, child of t832, `depends: [t826_3]`, priority
medium / effort medium. Created via:

```bash
./.aitask-scripts/aitask_create.sh --batch --parent 832 \
  --name website_docs_cross_repo_deps_planning --type documentation \
  --priority medium --effort medium --depends t826_3 \
  --desc-file <tmpfile> --commit
```

The `--desc` documents the **t832-family** surface for a future page (working
name `website/content/docs/workflows/cross_project_dependencies.md`):
`xdeps`/`xdeprepo` dependencies (frontmatter, blocking — only `Done` satisfies,
UNREACHABLE handling) · notation parser + `ait board` cross-repo display &
navigation · `--project` on read-side helpers (`ait ls --project`,
`ait explain --project`) + file notation `repo:path` · `ait update --project`
(cross-repo mutation guardrails) · interactive `ait create` cross-repo flow ·
parallel cross-repo planning (two parents per repo, `xdeps` edges; cross-link
the existing `parallel-planning.md`). It should cross-link back to
`multi_project.md` and `aidocs/cross_repo_references.md`.

## Verification

- `cd website && hugo build --gc --minify` — clean build, no warnings
  (run `npm install` first if deps are missing).
- `cd website && ./serve.sh` — visually inspect `multi_project.md`: renders,
  code blocks formatted, sidebar entry present under Parallel, the 8-verb table
  reads correctly.
- Confirm the new page appears in the workflows sidebar and the `_index.md`
  Parallel-group link resolves.
- Confirm the `aidocs/cross_repo_references.md` "See also" link points at the
  new page and the trimmed "not-in-scope" list is accurate.
- Confirm `t832_12` was created and added to t832's `children_to_implement`.

## Step 9 reference

After implementation and review (Step 8), follow the shared workflow's Step 9
(child-task archival of t826_3 to `aitasks/archived/t826/` and
`aiplans/archived/p826/`). Profile `fast` works on the current branch — no
worktree/branch to clean. `verify_build` (if configured) runs at archival.

## Final Implementation Notes

- **Actual work done:** Created `website/content/docs/workflows/multi_project.md`
  (weight 48, Parallel group) covering the full t826-family registry surface —
  Why / per-project identity / registry + resolution order + LIVE/OK/STALE
  states / **all 8 `ait projects` verbs** (list/add/resolve/exec +
  remove/update/prune/doctor) / `ait create --project` (with `--batch`-required
  and no-`--parent` constraints) / cross-project `#`/`:` notation / TUI switcher
  inactive+stale behavior with explicit "`ait monitor` unchanged" note /
  recipe. Added the nav bullet under **Parallel** in `_index.md`. In
  `aidocs/cross_repo_references.md`, appended a "See also" cross-link to the new
  page and trimmed the now-false "What is NOT in scope" bullets (notation
  parser, `remove`/`prune`, switcher t826_2, website docs t826_3 — all shipped
  or landing). Created follow-up **t832_12** (documentation, child of t832,
  `depends: [826_3]`) to document the t832-family surface.
- **Deviations from plan:** None of substance. All examples use generic
  placeholder project names (`frontend`/`backend`) per user feedback delivered
  at the first plan-approval prompt; the plan was revised to bake that rule in
  before approval.
- **Issues encountered:** None. `hugo build --gc --minify` is clean (201 pages);
  the two `.Language.LanguageDirection` / `.Site.AllPages` deprecation WARNs are
  pre-existing theme-level warnings, unrelated to this page.
- **Key decisions:** (1) Page scope = full 8-verb registry surface (user-chosen)
  rather than the originally-planned 4 core verbs, reflecting t826_7/8/9 +
  t826_10 shipping after the task was written. (2) Follow-up placed as a child
  of t832 (t832_12), not a standalone top-level task (user-chosen). (3) Did NOT
  forward-reference the (not-yet-existing) t832 deps page from the new page, per
  the current-state-only doc rule.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** The cross-repo doc surface is now split across two
  pages by design — `multi_project.md` (this task, the registry/projects layer)
  and the forthcoming `cross_project_dependencies.md` (t832_12, the deps /
  planning / data layer). t832_12 should cross-link back to this page rather
  than re-document the registry. Generic-example-project-names is now a standing
  doc convention (see the doc-writing rules in this plan's Context); apply it in
  t832_12. Source of truth for `ait projects` verb wording is the help block in
  `.aitask-scripts/aitask_projects.sh` (lines 44–96).
