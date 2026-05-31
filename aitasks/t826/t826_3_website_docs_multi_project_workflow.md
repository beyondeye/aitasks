---
priority: medium
effort: low
depends: [t826_2]
issue_type: documentation
status: Ready
labels: [website, docs, cross_repo]
assigned_to: ''
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-25 17:18
updated_at: 2026-05-31 10:21
---

## Context

Third (and currently-final) implementation step of t826. After t826_1
introduces the project registry + `ait projects` subcommand + `aitask_create.sh
--project` flag, and t826_2 surfaces inactive projects in the TUI switcher,
the user-facing Hugo/Docsy website needs a workflow page that explains
multi-project work end-to-end. Today the website has no content covering
cross-repo coordination because the framework had no first-class support
for it.

Depends on t826_1 and t826_2 — documentation should reflect the actually
shipped surface, not a forecasted design.

IMPORTANT UPDATE: Since we introduced this task we have implemented many additional features for cross-repo support (task 832), need to reevaluate the scope 
of this documentation task. and need to create an additional followup-task to document the additional features introduced in 832

## Key Files to Modify or Create

- **Check first:** scan `website/content/docs/workflows/` for any existing page covering multi-project work. If present, update it. If absent (likely), create `website/content/docs/workflows/multi_project.md` with the appropriate Docsy frontmatter (weight, description, etc.) — mirror the structure of an existing workflow page such as `manual-verification.md`.
- `website/data/menu.toml` or equivalent nav source (varies by Docsy version) — wire the new page into the workflows section if not auto-discovered.
- `aidocs/cross_repo_references.md` (authored in t826_1) — append a cross-link to the user-facing workflow page.

## Reference Files for Patterns

- `website/content/docs/workflows/manual-verification.md` — typical workflow page structure (frontmatter, headings, recipe blocks, screenshot/code-block conventions).
- `website/content/docs/` neighboring pages for sidebar/weight conventions.
- `aidocs/cross_repo_references.md` (created in sibling t826_1) — authoring-side reference; user-facing page should not duplicate but should link.

## Required Page Content

1. **Why** — cross-repo coordination pain, persistent project registry.
2. **Per-project identity** — `project:` block in `project_config.yaml` (schema + example).
3. **`ait projects` subcommand** — reference for `list` / `add` / `resolve` / `exec` (signatures + a usage example each).
4. **Cross-repo task creation** — `aitask_create.sh --project <name>` walkthrough (real example: from `aitasks_mobile`, create a sister task in `aitasks` without touching `cd`).
5. **Cross-repo notation in plans / commits** — preferred `aitasks#835_3` (no `t`), accepted `aitasks#t835_3` (with `t`); writing convention only (no parser yet).
6. **TUI switcher inactive-project behavior** — registered projects appear in the switcher even when their tmux session isn't running; selecting an inactive project spawns its tmux session and teleports. **Explicit note: `ait monitor` is unchanged** — its multi-project view stays scoped to live tmux sessions.
7. **Recipe: "How to register a sister project and spawn a task there"** — copy-pasteable command sequence.

Per CLAUDE.md "Documentation Writing": **current state only** — no "previously we…" prose, no migration notes, no version history.

## Implementation Plan

1. **Audit** — `ls website/content/docs/workflows/`; pick "update existing" or "create new".
2. **Draft** — write the page following the 7-section outline above.
3. **Nav wiring** — verify the page appears in the workflows section sidebar (Docsy auto-discovers most pages from frontmatter; explicit menu edits may be needed depending on the existing setup).
4. **Cross-links** — append the website URL/path to `aidocs/cross_repo_references.md`.
5. **Build verify** — `cd website && hugo build --gc --minify` clean build; `./serve.sh` and visually inspect the new page.

## Verification Steps

- `cd website && hugo build --gc --minify` — clean build, no warnings.
- `cd website && ./serve.sh` — visually inspect the new/updated page renders correctly, code blocks formatted, sidebar nav entry present.
- Click through cross-links from `aidocs/cross_repo_references.md` to the website page.
- Run `npm install` first if dev server complains about missing deps (per project README).

## Out of Scope

- Documentation of future-sibling features (cross-project parent linkage, notation parser, `ait projects remove`, auto-clone) — those get their own doc updates when they ship.
- Translating the page to non-English Docsy locales (if any exist).
- Changing the website's design system or navigation structure.

## References

- Parent plan: `aiplans/p826_brainstorm_cross_repo_project_references.md`
- Siblings (will be archived to `aiplans/archived/p826/` by the time this task runs):
  - `aiplans/archived/p826/p826_1_registry_resolver_projects_cmd_and_create_flag.md` — surface to document.
  - `aiplans/archived/p826/p826_2_tui_switcher_show_inactive_projects.md` — switcher behavior to document.
