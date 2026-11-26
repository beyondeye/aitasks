---
Task: t2258_10_audit_workflows_cross_project.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_*_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-26 12:10
---

# t2258_10: Workflows audit, Parallel group (cross-project and remote part)

## Context

Split from t2258_4 at its planning (2026-11-12). This child audits the last
three pages of the Parallel group in `website/content/docs/workflows/`
(`multi_project`, `cross_project_dependencies`, `claude-web`; 615 lines, all
`advanced`). It checks them against the level model in
`aitasks/metadata/doc_update_guide.md` and reviews them with
`aitask-docs-review`. The binding method is the task body's "Method
(binding)", which follows the parent plan's "Common audit method". This plan
reuses the t2258_9 method: parallel restructure agents on disjoint file sets
working from one brief, an independent review, and per-source survival agents.

## Verification of the existing plan (verify path, 2026-11-25, main @ 46b34ee2f)

The pending plan was a skeleton with the right steps, but it had no inventory
and no restructure design. Checked against the tree:

- **Shared-file gate at planning: all clean.** The three sources and every
  candidate destination are clean: `workflows/{_index,task-notes,
  implementation-trails,parallel-planning,repo-maintenance}`,
  `commands/{_index,task-management,note,lock}`,
  `tuis/trails/{reference,how-to,_index}`, `tuis/board/{reference,how-to}`,
  `skills/{aitask-pickweb,aitask-web-merge,aitask-pickrem}`,
  `concepts/cross-repo-references`, `development/task-format` and
  `aidocs/framework/cross_repo_references.md`. The only dirty site page is
  `tuis/sitrep/reference.md`, which is not in scope. The gate still runs again
  before every agent starts.
- **Note from t2258_4 (acknowledged, advisory):** renaming
  `multi_project#creating-a-task-in-a-sibling-project` means retargeting
  `workflows/task-notes.md:46`. The plan renames that heading (see Agent A).
  The `--help` texts of `aitask_find_by_file.sh` and `ait projects` also say
  "sibling", and `ait projects --help` uses real repo names (`aitasks_mobile`)
  in its examples. Those are script help texts, outside this documentation
  task. They are recorded in Final Implementation Notes as observations.
- **No `ait projects` reference page exists.** `commands/_index.md:54` links
  the command to `multi_project#the-ait-projects-command`. `ait projects
  --help` documents the `RESOLVED:` / `NOT_FOUND:` / `STALE:` output, so by the
  guide rule the contract is public architecture and belongs on an `advanced`
  reference page. For a CLI command that page is `commands/`. New page:
  `commands/projects.md`.
- **Ownership is inverted for trails.** `tuis/trails/reference.md` (L26, L84)
  and `tuis/board/reference.md` (L313, L316) send readers to the workflow page
  for rules (entry states, linked-trail search, jump). The rules move onto the
  trails reference. The reference pages then link to their own sections, and
  the how-to pages keep linking to the workflow.
- **The `ait update --project` claims are partly stale.** In
  `aitask_update.sh:310-324` the help text also lists `--deps` as allowed
  cross-repo, which the page omits. Check whether the allow-list is enforced,
  or only the refusals (L2503-2512).
- **The `claude-web` profile claims look stale.** The `/aitask-pickweb` stub
  resolves its profile with `aitask_skill_resolve_profile.sh pickweb`
  (`default_profiles.pickweb` in userconfig or project_config, else
  `default`). It does not use "a profile named `remote`, else the first
  alphabetically". The `NO_PROFILES` error lives in
  `task-workflow/execution-profile-selection-auto.md:58`. Agent C settles this
  in code before writing.
- **The web-merge archival is conditional, and both pages say it is not.**
  `.claude/skills/aitask-web-merge/SKILL.md` Step 5 first materializes the
  active gates from the marker's profile provenance, and stops before
  archival on `WEBMAT_INVALID` / `WEBMAT_FAIL` (Retry / Abort this branch;
  the merge stays committed and the task unarchived). Its `GATE_PENDING:`
  backstop leaves the task unarchived until a reviewer passes the gates and
  re-runs the skill. Push and branch deletion are Step 6. `claude-web` and
  `skills/aitask-web-merge` both present archival as unconditional, so
  Agent C covers this (how-to step plus reference section).
- **Inbound anchors** (they break silently if a heading is renamed):
  - `cross_project_dependencies#cross-repo-dependencies-in-implementation-trails`
    ×5: `tuis/board/how-to:256`, `tuis/board/reference:313`,
    `tuis/trails/how-to:34`, `tuis/trails/reference:84`,
    `workflows/implementation-trails:45`;
  - `cross_project_dependencies#jumping-to-a-linked-trail-in-another-project`
    ×4: `tuis/board/reference:316`, `tuis/trails/how-to:82`,
    `tuis/trails/_index:24`, `tuis/trails/reference:26`;
  - `cross_project_dependencies#planning-paired-work-across-two-repos` ×2:
    `workflows/multi_project:147`, `workflows/parallel-planning:54`;
  - `multi_project#the-project-registry`: `development/task-format:202`;
  - `multi_project#how-a-name-resolves-to-a-path`:
    `cross_project_dependencies:43`;
  - `multi_project#referring-to-cross-project-tasks-and-files`:
    `cross_project_dependencies:215`;
  - `multi_project#the-ait-projects-command`: `commands/_index:54` (retargeted
    to the new page);
  - `multi_project#creating-a-task-in-a-sibling-project`: `task-notes:46`
    (renamed and retargeted).

  **Rule:** keep each heading, or retarget every inbound link in the same
  change. Re-run the grep before editing.
- **No fresh-reader runs.** No page in scope is or becomes `main-concept`, so
  `--budget 0`.

## Inventory (measured at 46b34ee2f, before any edit)

rows = table rows, em = em dashes, bold = bold spans. Every page is a how-to
(it sits under `workflows/`). AP = Diátaxis anti-pattern.

| Page | Lines | rows/em/bold | depth before → after | Verdict | Violations |
|---|---|---|---|---|---|
| `cross_project_dependencies` | 236 | 25/14/18 | advanced → **intermediate** | **restructure** | AP5: three outcome tables (the trail entry states, the ghost status line, seven "could not search" problem lines) plus the four link rules with their dialog prefixes, the 30-second-per-project timeout, request coalescing, the jump's session-discovery steps and its failure notices. All of these are reference material for `tuis/trails/reference`, which currently defers to this page. The full `ait update --project` allow and refuse lists are reference material for `commands/task-management#ait-update`. 8 `###` subsections fragment the how-to. Fact error: "`ait ls` and `/aitask-pick` skip" a blocked task (L27); `ait ls` lists it after the unblocked tasks with its blocker shown. Level: `UNREACHABLE` and other status tokens, the `fwd-xdeps` prefix vocabulary. Prose: a run-up intro paragraph restating the page list, a bold admonition, "genuinely", "you do **not**", "deliberately", bold for emphasis (18 spans), em-dash connectors. |
| `multi_project` | 216 | 23/16/10 | advanced → **intermediate** | **restructure** | AP5: the identity-field table, the registry file format, its path and env override, the unreadable-registry rules, group fallback and the `-` marker semantics, the three-state resolution table with `resolve` output, and the 15-verb `ait projects` table. All of these are reference material for a command that has no reference page. "Why logical project names" repeats the concept page's why (guide growth sign). The closing Recipe repeats steps already listed (growth sign). Level: status vocabulary (`RESOLVED`/`NOT_FOUND`/`STALE`), registry path. Prose: "sibling" ×4 (L120, L132, L134, L149), example project `mobile` (L156, not one of the generic names), "intentionally **unchanged**" (current-state wording that implies history), bold emphasis. |
| `claude-web` | 163 | 9/7/4 | advanced → **intermediate** | **restructure** (condense) | AP5: the `.aitask-data-updated/` file table and the completion-marker JSON are reference material owned by `skills/aitask-pickweb#completion-and-merging` / `skills/aitask-web-merge#plan-file-handling`, which already state most of it. The profile key table duplicates `skills/aitask-pickweb#execution-profiles`. Growth signs: the comparison table, the ASCII diagram and two numbered lists all walk the same three stages, and Troubleshooting is a symptom→fix list. Level: internal directory and file schema, the exact git flags (`--no-ff --no-commit`, `git rm -rf`). Facts suspected stale: profile selection (see above), the pickweb step list (its real first step is the data-branch init). Links: relative `../../skills/…` paths, to become `relref`. Prose: "This guide covers…" (writing about the page), "simply". |

**Retags:** all three drop to `intermediate`, matching
`concepts/cross-repo-references` (`intermediate`). Their reader has taken
tasks from pick to archive and now links a second project or uses a cloud
sandbox, which is the `intermediate` persona. After the moves each page
contains only what `intermediate` allows: frontmatter fields and profile keys
the user edits, flags, keys and on-screen labels, and failure cases in prose.
Exact status tokens, outcome tables, internal paths and schemas move to the
`advanced` reference pages.

**Each retag is tied to the moves that make it true.** A page is retagged
only once the units that take its `advanced` detail away have landed:

| Page | Retag requires | If a required unit fell back |
|---|---|---|
| `multi_project` | U-A1 (the registry, state table and verb table leave). U-A1b is not required: the pointer section is plain prose | stays `advanced` |
| `cross_project_dependencies` | U-B1 (the outcome tables, prefix vocabulary and jump mechanics leave). U-B2 is not required: its lists are flags and failure cases, which `intermediate` allows | stays `advanced` |
| `claude-web` | U-C1 (the marker schema, file table, git flags and profile table leave) | stays `advanced` |

The retag is the last edit of the page's how-to rewrite (U-A3 / U-B3 /
U-C2), written once the agent knows which units landed. A page that stays
`advanced` is still rewritten as a how-to, and it is reviewed as `advanced`.
Its ledger entry records the retag it still owes, with the checks that
must re-run after it: review at `intermediate`, depth, links and survival.

## Steps

### Step 1: Shared-file gate, by change unit, against a per-file baseline

**Change units.** A unit is one source cut together with everything that
has to land with it: the destination additions, any heading rename or
removal, and every inbound-link retarget that rename needs. A unit lands
whole or not at all. Units share files (U-A1/U-A2/U-A3 all edit
`multi_project.md`), so the gate cannot compare against HEAD after this
task's first edit. Instead it compares each file against **the contents this
task last left in it**.

**Gate helper (scratchpad `gate.sh`, one state dir per file under
`scratchpad/gate/`).** Each file is resolved in its own git context: site
and `aidocs/` files through `git`; `aitasks/metadata/doc_update_guide.md`
through `./ait git`, because `aitasks/` is a symlink into the separate
`.aitask-data` checkout, which plain `git` cannot see.
- `claim <file>`: used the first time this task touches a file. The file
  must be clean in its own context (`diff --quiet HEAD` and an empty
  `status --short`). It stores `base` (the HEAD blob) and `last` (the
  current bytes), with state `existing`.
- `claim-new <file>`: the first touch of a file this task will create
  (`commands/projects.md`). The file must be absent and untracked. It
  stores state `expect-absent` and no `base` or `last`. A claim alone never
  makes a file "created".
- `check <file>`: run before every later edit. State `existing` or
  `created`: `cmp -s <file> last`, where a mismatch means another session
  changed the file since this task last wrote it. State `expect-absent`: it
  passes only while the file is still absent and untracked, and a file that
  appeared means another session created it.
- `record <file>`: run immediately after each successful edit or write. It
  stores the current bytes as `last`. On an `expect-absent` file it first
  verifies the file now exists, then switches the state to `created`. Only
  this transition puts a file on the created list.

A third-party change therefore still blocks the edit, and this task's own
earlier edits never do. Before a unit starts, `claim` / `claim-new` (first touch) or
`check` (later touch) runs on **every** file of the unit. If any of them
fails, the unit does not run. Its **fallback** below applies instead, so
every link target keeps working, and the unit goes into the
**skipped-page ledger** (unit id, files, the failing file(s), what changed:
dirty at HEAD, or diverged from `last`).

| Unit | Files | Content | Fallback when a file fails the gate |
|---|---|---|---|
| U-A1 | `multi_project.md`, new `commands/projects.md`, `aidocs/framework/cross_repo_references.md` | create `commands/projects.md`; move the registry/identity/group/resolution/verb-table reference into it; shrink `## The ait projects command` (heading kept, so `commands/_index:54` still resolves) to a two-sentence pointer to the new page | `multi_project` fails or `commands/projects.md` already exists → the unit does not run: no new page, the reference stays where it is. `aidocs/…` alone fails → run the unit, but keep contributor-only facts on the source until close-out |
| U-A1b | `commands/_index.md`, `multi_project.md` | retarget `commands/_index.md:54` to `commands/projects`, then remove the pointer section. Runs only if U-A1 landed | the pointer section stays and `_index` keeps its link |
| U-A2 | `multi_project.md`, `workflows/task-notes.md` | rename `#creating-a-task-in-a-sibling-project` → `#creating-a-task-in-a-linked-project`; retarget `task-notes.md:46` | keep the old heading text (and so its anchor); only the body prose drops "sibling" |
| U-A3 | `multi_project.md` | the how-to rewrite of the remaining sections (all kept anchors) | — (single file) |
| U-B1 | `cross_project_dependencies.md`, `tuis/trails/reference.md`, `tuis/board/reference.md` | move the trail-entry, linked-trail and jump rules to new trails-reference sections; retarget trails-reference L26/L84 and board-reference L313/L316 to them; board `↗` / `#` facts | `cross_project_dependencies` or `tuis/trails/reference` fails → the unit does not run. `tuis/board/reference` alone fails → run the unit without the board retarget and the board facts; its links keep working because the workflow anchors are kept, and the board facts stay on the source |
| U-B2 | `cross_project_dependencies.md`, `commands/task-management.md` | move the `ait update --project` lists into a new `### Updating a task in another project`; add `--project` / `--xdeps` constraints to `ait create` / `ait ls` | the lists stay on the source page |
| U-B3 | `cross_project_dependencies.md` | the how-to rewrite of the remaining sections | — |
| U-C1 | `claude-web.md`, `skills/aitask-pickweb.md`, `skills/aitask-web-merge.md` | the marker/table/profile moves, and the new `## When archival stops` reference section | the reference blocks stay on the source page; the how-to still gains the pause-and-recovery step, in plain words |
| U-C2 | `claude-web.md` | the how-to rewrite | — |
| U-D | `workflows/_index.md` | Parallel bullet text | leave the bullet; the frontmatter description is updated anyway |
| U-G | `aitasks/metadata/doc_update_guide.md` (task-data context) | the Step 3 lesson | the lesson goes to Final Implementation Notes for t2258_8 |

**Links into another unit's output are conditional.** A link to a page or
anchor that a unit creates (`commands/projects`,
`tuis/trails/reference#cross-repo-entries` / `#linked-trails-and-the-jump`,
`commands/task-management#updating-a-task-in-another-project`,
`skills/aitask-web-merge#when-archival-stops`) is written only once that
unit has landed. Otherwise the link points at where the content still is:
the kept section on the source page, such as
`multi_project#the-ait-projects-command`. So each agent runs its units in
table order and writes the how-to rewrite (U-A3, U-B3, U-C2) last, after it
knows which units landed. A unit that falls back is reported with the
lines that stay on the source, the links that point at them, and the checks
it still owes (review, links, survival, verification items). These go into
its ledger entry.

**Removing or renaming a heading re-checks its inbound links at that
moment.** The inbound-anchor list above is a planning snapshot. Other units
of this task (for example U-A3 linking to `#the-ait-projects-command` while
U-A1 is deferred) and other sessions can add links later. So the removal
step of U-A1b and the rename step of U-A2 (in the first pass and again in
the Step 7 late loop) each start with a fresh
`grep -rn '<page>[^)]*#<anchor>' website/content aidocs` and an in-page
`#<anchor>` grep. Every hit's file joins that unit and goes through the
gate. Every hit is retargeted in the same change. If any hit's file fails
the gate, the old heading (and so the anchor) stays, as the pointer
section or the old heading text. The unit goes to the ledger with the
blocking link listed. An anchor is removed only when the grep run right
before the removal finds no remaining link to it.

### Step 2: Restructure (three parallel agents on disjoint file sets, one brief)

A scratchpad `restructure_brief.md` summarises the rules for these pages:
- the level contracts (`intermediate` for the three sources, `advanced` for
  the destinations);
- how-to shape: goal, numbered steps, outcome; one procedure per job, with
  the example inside it;
- the moved-fact table format (source#section → fact → destination#anchor →
  `moved` / `already-stated` / `corrected` / `dropped(reason)`);
- check every moved fact in the code, with file:line;
- use `relref` for new and touched links;
- keep the inbound-anchor headings listed above;
- generic example names (frontend / backend / the docs site), no "sister"
  and no "sibling";
- no table rows in `development/task-format.md`;
- current-state only;
- write generated files directly, never through `tee | head`.

Each agent returns its files changed, its moved-fact rows, its code-verified
corrections and its open points. I review every diff before Step 3.

**Agent A: `multi_project.md`** (units U-A1, U-A1b, U-A2, then U-A3 last). It may edit or create: new
`commands/projects.md`, `commands/_index.md` (the `ait projects` row and its
L113 line only), `workflows/task-notes.md` (the L46 link only) and
`aidocs/framework/cross_repo_references.md` (contributor-only detail only).
- **New `commands/projects.md`** (`depth: [advanced]`, title "`ait
  projects`", weight placed among the other `commands/` pages, matching the
  shape of `commands/note.md`). Sections:
  - Usage and verbs: the full verb table, including `group` and the
    `resolve` output forms, checked against `ait projects --help` and the
    dispatcher. It also covers `exec` erroring out on `NOT_FOUND` / `STALE`.
  - Project identity: the `project_config.yaml` block and the field table
    (name rules, basename default, `git_remote` use, `project_group` slug
    regex).
  - The registry file: path, `AITASKS_PROJECTS_INDEX`, the YAML shape, not
    committed, and the unreadable-file rule (which verbs stop, the file left
    untouched, TUI discovery treating it as empty).
  - Project groups: the registry is authoritative, the config fallback, the
    `-` explicitly-ungrouped marker, `rename` merges, `sync` fills only
    missing groups.
  - Name resolution: the three sources in order (live tmux scan by project
    name, then session name; the registry; `AITASKS_PROJECT_<name>`), the
    state table with the LIVE / OK listing labels, and "never repaired, never
    cloned unless `doctor --clone`".
  - Examples.

  Every fact is checked in `aitask_projects.sh` (or the dispatcher it uses),
  `aitask_project_resolve.sh` and the registry library. Whatever is
  contributor-only (resolver internals, cache) goes to
  `aidocs/framework/cross_repo_references.md`, if that page does not already
  state it.
- **`multi_project.md` keeps** (how-to, `intermediate`):
  - an intro: the goal (refer to linked projects by name; each machine maps
    names to its own checkouts), linking `concepts/cross-repo-references` for
    why. Drop "Why logical project names".
  - `## Register a linked project`: one numbered procedure that merges the
    end Recipe: (1) give the project a name in `project_config.yaml`
    (`project.name`, defaults to the directory name); (2) `cd` there and run
    `ait projects add`; (3) back in your project, `ait projects list` shows
    it; (4) use it. Link `commands/projects` if U-A1 landed, else
    `#the-ait-projects-command`.
  - `## The project registry` (anchor kept): 2–3 plain sentences: one list
    per user and machine, never committed, managed with `ait projects`,
    linking `commands/projects#…` for the file (if U-A1 landed; else the
    kept reference text stays here).
  - `## How a name resolves to a path` (anchor kept): the three sources in
    plain words; a name that does not resolve is reported with the fix
    (`ait projects add` / `update`); nothing is cloned unless you ask
    (`ait projects doctor --clone`). Link the reference for the states.
  - `## Keep the registry current`: moved project → `update`; deleted →
    `prune` (`--dry-run` first); walk them all → `doctor`.
  - `## Group related projects`: what groups do (switcher and Stats TUI
    navigation), `group set` steps, and one sentence on `unset` / `rename` /
    `sync`, linking the reference.
  - `## Run a command in a linked project`: `ait projects exec`.
  - `## Creating a task in a linked project` (renamed; retarget
    `task-notes.md:46` in the same change): kept, with the `--parent`
    constraint and the "two parents" link.
  - `## Sending a note to a linked project's task`: kept; example project
    `backend`; the resolution caveat kept.
  - `## Referring to cross-project tasks and files` (anchor kept): kept.
  - `## Switching between projects`: kept; state the `ait monitor` scope
    positively ("shows only projects with a live tmux session").
  - See also (new: `commands/projects`, only if U-A1 landed).
- **Fact checks:** the resolver order and its match keys; "session discovery
  keeps working"; the name and slug rules; `doctor`'s per-entry options;
  `add` is idempotent; `update` keeps `git_remote`; the switcher's `(stale)`
  marker and its prune/repoint offer; the Stats TUI `[`/`]` exception; the
  note's every-source-checked / conflict-refuses rule (against
  `commands/note.md` and `aitask_note.sh`).

**Agent B: `cross_project_dependencies.md`** (units U-B1, U-B2, then U-B3 last). It may edit
`tuis/trails/reference.md`, `tuis/board/reference.md` (the By-Trail
"Work in other projects" paragraph and the card-anatomy region for `↗` and
the chip only), `commands/task-management.md` (new `--project` subsections
under `ait create`, `ait ls` and `ait update` only) and `tuis/trails/how-to.md`
(link retarget only, if needed).
- **The page keeps** (how-to, `intermediate`):
  - an intro: the goal, in one paragraph, with one sentence that the projects
    must be registered first (link `multi_project`). No bold admonition.
  - `## Block a task on another project's work`: the `xdeprepo` / `xdeps`
    YAML example; set them at creation (`ait create --batch --xdeps …
    --xdeprepo …`, IDs validated) or later (`ait update`); only `Done`
    unblocks; `ait ls` **keeps** a blocked task in the list, sorts it after
    the unblocked tasks, and with `-v` shows what blocks it (one
    `Blocked (by backend#42)` example); the pick workflow's behaviour is
    stated in its own sentence, as the code shows it (see the fact check
    below); `xdeprepo` alone records the intent
    and opts into paired planning; `xdeps` alone is refused; an
    unregistered or stale project keeps the task blocked, and how to fix it
    (links `multi_project#how-a-name-resolves-to-a-path`).
  - `## Seeing cross-repo references on the board`: the `↗` line, the
    `🌐 blocked (cross-repo)` chip, `#` opening the read-only popup.
  - `## Cross-repo dependencies in implementation trails` (anchor kept),
    written as prose, not `###`: trail cards carry the same `↗` line; a
    member from another project shows as a read-only ghost card with its
    live status; a member counts as blocked only after a finished check;
    checks run when a trail opens and on `d`, `r` reuses the last results.
    Link `tuis/trails/reference#…` for the entry states.
  - `## Jumping to a linked trail in another project` (anchor kept): one
    sentence on what links two trails (a member of one depends on, or is, a
    member of the other; compared by location on disk, not by name); then a
    numbered procedure: press `L` in By-Trail or `ait trails`; choose in the
    **Linked trails** dialog (`Enter`, `Esc`); answer **Switch** / **Stay
    here** if a notice is shown; an incomplete search is said so in the
    dialog; outside the aitasks tmux server, run the printed `ait projects
    exec … ait trails --trail …` command. Keep "a trail stays owned by its
    own project". Link the reference for the rules.
  - `## Reading another project's tasks and files`: kept (check that
    `aitask_explain_context.sh --project <name>:<path>` is the documented
    form, and whether an `ait` verb exists for it).
  - `## Updating a task in another project`: the goal, the example, and a
    plain summary: administrative fields only; starting or finishing work,
    folding and renames happen in that project; a task locked by someone
    else is refused. Link `commands/task-management#…` for the lists.
  - `## Declaring cross-repo links when creating a task`: kept (interactive
    steps and the batch example).
  - `## Planning paired work across two repos` (anchor kept): kept, prose
    fixed.
  - See also.
- **Moves:**
  - The entry-state table, the ghost status table, "when the checks run",
    the four link rules with the `fwd-`/`rev-` prefixes, search
    announcement and duration, 30 s per project, the incomplete-search
    headers and the seven problem lines, request coalescing and the
    drop-on-leave rules, the jump's three steps (session discovery with the
    default-name preference, the window start or switch, the client switch),
    the two pre-switch notices, outside-tmux behaviour and the
    session-changed message → new `tuis/trails/reference.md` sections
    `## Cross-repo entries` and `## Linked trails and the jump`. Check them
    against `board/trail_*` / `trails_app.py` and the link-search module,
    and merge with the existing "In the linked-trails dialog" / "In the jump
    confirmation" key tables rather than repeat them. Then retarget
    trails-reference L26/L84 and board-reference L313/L316 to the new
    reference sections. The how-to links (`tuis/*/how-to`, `tuis/trails/_index`,
    `workflows/implementation-trails`) stay on the workflow anchors.
  - The `↗` line and chip and the `#` popup behaviour (picker, Tab cycling,
    read-only, no lock) → `tuis/board/reference` card anatomy / key table,
    if not already stated.
  - The `ait update --project` allow and refuse lists, the lock refusal and
    the `--batch` requirement → `commands/task-management#ait-update`, new
    `### Updating a task in another project` (corrected with `--deps` if the
    code allows it). Also add `--project` / `--xdeps` / `--xdeprepo`
    constraints to `#ait-create` and `--project` to `#ait-ls` where missing.
- **Known correction:** the page says `ait ls` and `/aitask-pick` "skip" a
  task whose cross-repo dependencies are not all `Done`. `aitask_ls.sh`
  does not skip it: `calculate_blocked_status()` (L603-652) marks it
  blocked, the sort puts unblocked tasks first (L34), and `-v` prints
  `Blocked (by <project>#<id>)`. `tests/test_xdeps_blocking.sh` asserts the
  blocked task appears (L117-118, L137, L144, L215). Moved-fact row:
  `cross_project_dependencies#how-blocking-works` → `ait ls` listing →
  same page → **corrected**. The same correction goes into
  `commands/task-management#ait-ls` (U-B2) if that page also says skip.
- **Pick behaviour, checked separately:** what `/aitask-pick` does with such
  a task. Does Step 2's listing (it calls `aitask_ls.sh -v 15`) show it
  marked blocked, or filter it out? Does a direct `/aitask-pick <id>` of a
  blocked task refuse, warn or proceed? Check the pick skill and any
  dependency check in `aitask_pick_own.sh` / the workflow. State only what
  the code does, and record it `corrected` if it differs from "skip".
- **Fact checks:** "satisfied only when Done" and UNREACHABLE-as-blocked (in
  the ls/pick dependency code); `xdeps` without `xdeprepo` refused at
  create and update; the interactive create step offers only resolving
  projects; the paired-planning bullets (against
  `task-workflow/planning-cross-repo.md` and `cross-repo-child-assignment.md`,
  including the push-failure warning at L132-139).

**Agent C: `claude-web.md`** (U-C1, then U-C2 last). It may edit `skills/aitask-pickweb.md`
(§ Completion and Merging and § Execution Profiles only) and
`skills/aitask-web-merge.md` (§ Step-by-Step, a new § When archival stops,
and any other missing fact).
- **First, settle the profile facts in code:** how `/aitask-pickweb`
  chooses its profile (the stub's `aitask_skill_resolve_profile.sh pickweb`,
  then whatever the rendered skill does), whether `ait setup` installs
  `remote.yaml` (`seed/profiles/remote.yaml` exists), which keys pickweb
  reads, and the exact no-profile message. Correct both the workflow page
  and the skill page.
- **The page keeps** (how-to, `intermediate`):
  - an intro: what Claude Code Web can and cannot push, and the goal.
  - `## Run a task on Claude Code Web`: the three-stage diagram, then one
    numbered procedure:
    (1) lock the task locally with the board's lock button or `ait lock
    <id>`; this is recommended, and without it pickweb only warns;
    (2) in the web session, `/aitask-pickweb <id>` (or `42_2`); only plan
    approval asks; it commits the work and leaves the plan and a completion
    marker on the branch, which you push;
    (3) locally, `/aitask-web-merge`: it merges to main and files the plan.
    It then archives the task (and the parent when it is the last child),
    pushes, and deletes the remote branch. Several branches are offered one
    after another;
    (4) **when it stops before archiving:** the skill pauses in two cases:
    the completion marker's profile record does not check out, or the task
    has gates that are not passed yet. The code merge stays committed and
    the task stays unarchived. Fix the cause (correct the marker or profile,
    or get the pending gates passed, e.g. by a reviewer), then run
    `/aitask-web-merge` again to finish. Plain words only; the exact
    conditions and outputs go to the reference. **Check in code first**
    what happens to the push and the remote branch on each stop path, and
    what a re-run does with an already merged branch (Step 5 →
    Step 6 order, `materialize-gates.md` "Abort this branch", the
    `GATE_PENDING:` backstop, `aitask_web_merge.sh`). State only what the
    code guarantees.
  - `## The execution profile`: 2–3 sentences with the corrected selection
    rule, the two keys it reads, and a link to the skill page.
  - `## If something goes wrong`: branch not found (push it,
    `git fetch --all`, check the marker is on the branch); merge conflicts
    (resolve when prompted, or abort); task locked by someone else (warns
    and continues, so lock first); no profile (run `ait setup`, or create
    `remote.yaml`, minimal content kept).
  - See also, with `relref` links.
- **Moves:**
  - The comparison table → already-stated (the "Key differences" tables in
    `skills/aitask-pickweb`).
  - The `.aitask-data-updated/` table and the completion-marker JSON →
    `skills/aitask-pickweb#completion-and-merging`, with the JSON example
    checked field by field against the code that writes it.
  - The git-flag and plan-copy details → already-stated at
    `skills/aitask-web-merge#merge-strategy` / `#plan-file-handling`.
  - The profile key table → `skills/aitask-pickweb#execution-profiles`
    (already-stated, or corrected).
  - The pickweb step list → already-stated at `skills/aitask-pickweb#step-by-step`.
  - **New in the reference** (`skills/aitask-web-merge`, § Step-by-Step and a
    new `## When archival stops`): the active-gates materialization before
    archival, its `WEBMAT_SKIP` / `WEBMAT_OK` / `WEBMAT_INVALID` /
    `WEBMAT_FAIL` outcomes and the Retry / Abort-this-branch choice with its
    manual repair path, and the `GATE_PENDING:<csv>` backstop. On the
    backstop a reviewer passes the gates (`ait gate pass` for human gates,
    `ait gates run` for machine gates) and re-runs the skill, and the skill
    never passes a human gate itself. Also cover what is and is not pushed
    or deleted on each stop path. Correct the page's step list, which states
    archival as unconditional. Checked against
    `.claude/skills/aitask-web-merge/SKILL.md` Step 5–6, `materialize-gates.md`
    and `aitask_web_merge.sh`.
  - The completion-marker JSON is checked against the code that writes it.
    The current example omits fields the merge reads (`profile`,
    `profile_filename`, `implemented_with`), so it becomes `corrected`.
- **Fact checks:** the board lock button and its email prompt; the
  informational lock warning; web-merge conflict handling (prompt vs abort,
  in `aitask-web-merge/SKILL.md` and `aitask_web_merge.sh`); "deletes the
  remote branch"; archives the parent when all children are done.

**Me: `workflows/_index.md`.** Change a Parallel bullet only if a page's
description changes. Keep each page's position and the group's wording. Also
update each changed page's frontmatter `description`, so the two stay in sync.

### Step 3: Feed lessons into the guide (last planned guide change)

Add short additions to existing sections, only for what this group showed.
Candidates:
- in "How a subject spans levels": a CLI command's verb table and output
  contract go on that command's `commands/` page; create one when it is
  missing, rather than a `development/` page.
- in "How a subject spans levels": a reference page links to a how-to for
  steps, never for its own rules. When a reference page sends readers to a
  workflow page for its rules, move the rules onto the reference page (seen
  on the trails reference).

This is unit U-G: `gate.sh claim aitasks/metadata/doc_update_guide.md`
(task-data context) before the edit and `record` after it.
Keep the `## Reader levels` interface lines byte-identical and each
prose-rule bullet on a single line. Run
`bash tests/test_docs_review_contract.sh`. The guide lives on the task-data
branch, so commit it by path with `aitask_task_commit.sh`.

### Step 4: Review under the final guide

An independent agent runs `/aitask-docs-review <every edited or created
page> --caller audit --budget 0`. It covers the three sources, the new
`commands/projects.md` (if U-A1 landed) and the changed regions of each
destination. Fix the
findings within the skill's invariants. A cut fact gets a moved-fact row.
Re-review each page a fix changed. Record `level=… prose=… reader=…` and the
unresolved findings per page here.

### Step 5: depth

Every leaf page in the group has `depth:`. Record the output of
`grep -L '^depth:' website/content/docs/workflows/{multi_project,cross_project_dependencies,claude-web}.md`
(expected empty), each page's actual depth with the units it depends on
(the retag table under Inventory: `intermediate` only where those units
landed, otherwise `advanced` with a ledger entry), and the depths of the
edited destination pages (`commands/projects` = `advanced`, if created).

### Step 6: Links

- `cd website && python3 check_links.py --build` must exit 0.
- `python3 check_link_relevance.py`: open every reported target this child
  added or retargeted, and record a verdict for each.
- `bash tests/test_website_doc_lists.sh` (a page is added under `commands/`)
  and `bash tests/test_docs_vocabulary_coverage.sh` (`task-management`
  changes).
- Grep confirms that each inbound anchor above still resolves, or was
  retargeted.

### Post-phase (risk mitigations)

1. [moved_fact_survival_check] The claim-level survival check, before the
   commit (the task's method step 8):
   a. A scratchpad `removed_blocks.py` splits each file's stored **`base`**
      (from `scratchpad/gate/`, captured at `claim` time in that file's own
      git context) and its working text into blocks (paragraph, list item,
      table row, admonition, code block). It lists every `base` block that is
      missing from the working version (whitespace-collapsed exact match)
      and writes its output files directly. The file list is driven by **recorded
      edits**. A file is in it when its gate state has `last` ≠ `base`,
      which means this task edited it, in either checkout. A claimed file
      that a fallen-back unit never edited has `last` = `base` and is left
      out. A file in state `created` (a recorded write after `claim-new`) goes on a
      separate **created** list. It has no removed blocks, but it is
      reviewed (Step 4) and given to the survival agent as a destination. A
      file still in state `expect-absent` (its unit fell back before
      writing it) is on neither list. If it now exists, it was created by
      someone else and is investigated, never committed. That covers the three sources **and** every edited
      destination: `tuis/trails/reference` (where the key tables are
      consolidated), `tuis/board/reference`, `commands/task-management`,
      `commands/_index`, `workflows/task-notes`, `skills/aitask-pickweb`,
      `skills/aitask-web-merge`, `aidocs/framework/cross_repo_references.md`,
      `workflows/_index`, and **`aitasks/metadata/doc_update_guide.md`**. The
      guide is tracked in the `.aitask-data` checkout, so its `base` comes
      from `./ait git show HEAD:aitasks/metadata/doc_update_guide.md`, and a
      plain `git diff` would silently omit it.
      **The git lists are used to investigate, not as an assertion.** Run
      `git status --porcelain` and `./ait git status --porcelain` (these
      include untracked files, unlike `git diff --name-only HEAD`) and
      intersect each with the unit file list. Two cases are investigated
      before the survival run continues: a unit path that git shows changed
      but the tracker has no edit for (a foreign or unrecorded change, so run
      `gate.sh check` on it and show the diff), and an edited or created path
      that git does not show (a lost edit). Every other path is outside this
      task and is ignored.
   b. One fresh sub-agent per agent file set (A, B, C, plus mine, which
      includes the guide), never the editor. Each gets the removed blocks of **every** file in its set
      verbatim, sources and destinations alike, plus the full current text
      of every file in the set. It classifies every claim (rule, condition,
      exception, consequence, scope, default, key or shortcut) as
      `preserved` (quote + page#section), `weakened` or `missing`. A claim
      removed from a destination section counts like a source claim, so a
      condition or key that was already documented there and vanished in a
      consolidation is caught.
   c. Fix every `weakened` / `missing` claim, or record it `corrected` (with
      code evidence) or `dropped(reason)`.
   d. Re-run once on the fixed claims. Record per file (sources and
      destinations): claims, preserved, fixed, corrected, dropped, and the
      run-2 result.
   e. A page changed in (c) goes back through Steps 4 and 6.

### Step 7: Ledger close-out

Re-check each ledger entry, **as a whole unit**, with the Step 1 gate
(`claim` for files this task has not touched, `check` for files it has):
- **Every file of the unit passes** → run the unit here, through the
  full late loop: the Step 1 gate on all of its files, the unit's edits
  (including the renames and retargets its fallback held back, and removing
  any fallback pointer). Then **apply any retag the late move made
  eligible** (retag table under Inventory: for example, `claude-web.md` →
  `intermediate` once U-C1 lands at close-out, even though U-C2 ran
  earlier and kept `advanced`). The retag is a gated edit like the others
  (`check`, edit, `record`), and the page's body is re-read for anything
  left above the new level. Then run the Step 4 review of every page it changed, the
  Step 5 depth check, the Step 6 links (`check_links.py --build` over the
  whole site, plus the anchor grep), and post-phase runs 1 and 2 on its
  files. A page changed by a fix goes back through Steps 4 and 6. No page
  reaches the commit on checks that ran before it was edited.
- **A file this task already edited has diverged from `last`** (another
  session changed it after this task's edit) → stop and ask the user. The
  file now mixes both sessions' changes, so no gate result is valid for it.
- **Any file still fails the gate** → leave the unit's fallback in place. The site
  stays consistent, because the fallback keeps every link target. Create a
  child of t2258 with `--no-sibling-dep`, named
  `audit_deferred_pages_workflows_cross_project`. It carries each pending
  unit: the files, the dirty file, the cut it still owes, the rename and
  retargets it must land together (with the blocking inbound links found by
  the fresh grep), any retag it still owes (retag table) with the checks to
  re-run after it, and the inventory row and design from this plan.

**Commit gate:** no unit is committed half-applied, and nothing from
another session is committed under this task's message. Before the commit,
for every **edited or created** file in `scratchpad/gate/` (state `existing`
with `last` ≠ `base`, or state `created`; an `expect-absent` file must still be
absent or is investigated;
a claimed file that was never edited is not committed, and another
session's later change to it only means its unit stays in fallback):
1. `gate.sh check <file>` must pass. A file that diverged from `last` has
   been changed by someone else since this task's final edit. Stop, show
   the foreign change, and do not commit that file until it is resolved
   (wait for the other session, or treat the units on it as fallen back).
2. Diff the file against its stored `base` (not against HEAD: HEAD of the
   task-data branch may have moved, and so may the code branch). Each
   unit's edits must be either all present, or absent with its fallback
   present. A unit that is neither is completed, or undone by hand with
   Edit, never `git restore` in this shared worktree.
3. Commit by path only, in each file's own context: `git commit -- <site
   files>` for the code branch, and `aitask_task_commit.sh` for the guide
   and plan.

Final Implementation Notes record each entry's outcome (`audited` /
`follow-up t2258_<n>`), or "ledger empty".

## Skipped-page ledger

| Unit | Files | Dirty file(s) and reason | Dirty state seen | Fallback applied |
|---|---|---|---|---|
| (none at planning) | | | | |

**Close-out (Step 7):** ledger empty. Every unit (U-A1, U-A1b, U-A2, U-A3, U-B1 incl. the board part, U-B2, U-B3, U-C1, U-C2, U-D, U-G) landed on the first pass; no gate failure, no fallback.

## Moved-fact table

(source#section → fact → destination#anchor →
`moved` / `already-stated` / `corrected` / `dropped(reason)`; filled from the
agents' reports and the survival check.)

### `multi_project.md` (Agent A; P = aitask_projects.sh, R = aitask_project_resolve.sh, ALU = lib/agent_launch_utils.py)

| source#section | fact | destination | outcome |
|---|---|---|---|
| #intro | frontend/backend goal; names vs ../ paths | multi_project intro | moved |
| #why-logical-project-names | paths break; names resolved at use | concepts/cross-repo-references#why-it-exists (linked) | already-stated |
| #per-project-identity | project: YAML block | commands/projects#project-identity | moved |
| #per-project-identity | name defaults to dir basename (P:196-202) | commands/projects#project-identity; multi_project step 1 | moved |
| #per-project-identity | name "lowercase [a-z0-9_-], unique" | commands/projects#project-identity | corrected: add does not check it (P:196-202,360); unique only because add replaces same-name entry (P:392-402); charset enforced by readers (aitask_note.sh:965, lib/note_inbox.py:65, lib/cross_repo_notation.py:21) |
| #per-project-identity | git_remote shown in list, used by doctor --clone (P:330-331,658) | commands/projects | moved |
| #per-project-identity | project_group fallback slug regex (ALU:782) | commands/projects#project-identity/#project-groups | moved; + add/group sync stop on invalid slug (P:385-386,934-936), TUIs ignore it (ALU:849-850) |
| #per-project-identity | add reads the block, basename fallback | commands/projects#project-identity | moved |
| #the-project-registry | path, AITASKS_PROJECTS_INDEX (P:47), YAML | commands/projects#the-registry-file | moved |
| #the-project-registry | "gitignored" | commands/projects; multi_project | corrected: lives in ~/.config outside every repo |
| #the-project-registry | manage with ait projects | same | moved; + writes rebuild from five fields, dropping hand comments/keys (P:247-267) |
| #the-project-registry | unreadable file stops list/add/remove/update/prune/doctor/group, file unchanged (P:222-239) | commands/projects#the-registry-file | moved; + resolve/exec keep working (R:122,189) |
| #the-project-registry | TUI discovery treats unreadable registry as empty (ALU:853-885) | commands/projects | moved |
| #project-groups | used by switcher and Stats TUI | commands/projects; multi_project#group-related-projects | moved |
| #project-groups | registry wins, config fallback, `-` = explicitly ungrouped (ALU:1027-1050, P:773-789) | commands/projects#project-groups | moved |
| #project-groups | CLI example block | multi_project#group-related-projects; commands/projects#verbs | moved |
| #project-groups | rename merges (P:813-836) | commands/projects; multi_project | moved; + config-only groups not renamed; renaming an empty group is an error |
| #project-groups | sync fills only missing (P:914-947) | commands/projects | moved |
| #how-a-name-resolves-to-a-path | three sources in order | commands/projects#name-resolution; multi_project (plain) | moved |
| #how-a-name-resolves-to-a-path | tmux scan "by project name, then session name" | same | corrected: matches project directory basename (ALU:232,1525; R:165-173) |
| #how-a-name-resolves-to-a-path | env var override (R:236-242) | same | moved; + a stale registry hit stops the search, hiding the env var (R:433-440) |
| #how-a-name-resolves-to-a-path | state table, LIVE/OK labels | commands/projects#name-resolution | moved (LIVE rule exact, P:274-309) |
| #how-a-name-resolves-to-a-path | never repaired, add hint, no cloning except doctor --clone | commands/projects; multi_project | moved |
| #the-ait-projects-command | verb table | commands/projects#verbs | moved + additions (rm alias, -y, doctor answers, exec optional --, [STALE] in group list, Error:/exit 1, 10 s registry lock) |
| #the-ait-projects-command | add idempotent | commands/projects; multi_project step 2 | moved; + same-name replacement, re-add keeps group (P:372-390) |
| #the-ait-projects-command | update keeps git_remote (P:516-524) | commands/projects; multi_project#keep-the-registry-current | moved; also keeps group |
| #the-ait-projects-command | resolve output forms | commands/projects | moved; always exits 0 (R:396-455) |
| #the-ait-projects-command | exec | commands/projects; multi_project#run-a-command-in-a-linked-project | moved |
| #the-ait-projects-command | examples | commands/projects; multi_project | moved; aitask_ls.sh -v 5 → ./ait ls -v 5 |
| #creating-a-task-in-a-sibling-project | --batch required, --parent in target, two-parents link (aitask_create.sh:2650-2725) | multi_project#creating-a-task-in-a-linked-project | moved |
| #sending-a-note-to-a-sibling-projects-task | every source checked, conflict refuses, other project commits | multi_project#sending-a-note…; commands/projects#name-resolution | moved; mobile → backend; + unreadable source refuses (aitask_note.sh:983-1015) |
| #referring-to-cross-project-tasks-and-files | notation | same | moved (kept) |
| #switching-between-projects | inactive projects listed, spawn session (tui_switcher.py:1729-1737), (stale) dimmed (L1097-1104) | same | moved; labels Prune / Repoint (stale_entry_modal.py:99-102) |
| #switching-between-projects | Left/Right, [/] (tui_switcher.py:668-671) | same | moved |
| #switching-between-projects | Stats TUI group nav "on session-aware panes" | same | corrected: [/] change group on every pane except agent ranking panes, when ≥2 projects shown (stats_app.py:207,516-524) |
| #switching-between-projects | ait monitor "intentionally unchanged" | same | moved, current-state: shows only projects with a running tmux session (monitor_core.py:3238) |
| #recipe | identity, add, list/resolve, create | multi_project#register-a-linked-project / #creating-a-task… | moved |
| (code) | ait ide registers the project best-effort (lib/tmux_bootstrap.sh:731-732, aitask_ide.sh:137) | commands/projects; multi_project step 2 | added |
| commands/_index L54 | verb list omitted group | same | corrected |

aidocs additions: registry mutex `${REGISTRY_FILE}.lockd` (10 s), strict re-read, full rebuild, atomic write; why (t1073, t2163, t2164); remove locks after its prompt; bootstrap swallows lock timeout; single-name lookup is an awk reader (why resolve/exec/create --project work on a registry the strict reader refuses); first name wins, a stale hit skips the env tier.

Added by survival run 1 (unlisted, correct → **corrected**): `commands/projects#name-resolution` NOT_FOUND = "No source knows the name" (was "No registered project matched") and STALE = "The name is known…" (was "registered"): `aitask_project_resolve.sh` main() prints NOT_FOUND only after all three tiers miss, and the env tier can return STALE.

### `cross_project_dependencies.md` (Agent B; S = source, TR = tuis/trails/reference, BR = tuis/board/reference, TM = commands/task-management)

Every source section was moved and survival run 1 classified all 137 claims (125 preserved, 9 listed corrections, 2 unlisted-but-correct, 1 minor missing rationale restored in TM#cross-repo-options). Destinations: S (rewritten how-to), TR#blocked-members / #members-from-another-project / #when-the-checks-run / #what-links-two-trails / #the-search / #the-jump, BR#task-card-anatomy (`↗` line, **Cross-repo lines**) and #task-operations (`#` row), TM#cross-repo-options / #listing-another-projects-tasks / #updating-a-task-in-another-project / #cross-repo-dependencies-in-the-listing. Corrected rows (code evidence):

1. ait ls keeps blocked tasks, sorted after unblocked, `Blocked (by …)` under -v (aitask_ls.sh:34-36, 642-658, 812-814; tests/test_xdeps_blocking.sh:117,137,144,215). TM#ait-ls never said skip.
2. /aitask-pick: Step 2 uses aitask_ls.sh -v 15, filters nothing (aitask-pick/SKILL.md.j2:212-221) → blocked task listed after unblocked, may fall outside top 15; direct /aitask-pick <id> runs no dependency check (Step 0b, j2:91-136; none in aitask_pick_own.sh or task-workflow).
3. Chip carries no (UNREACHABLE); the marker is on the ↗ entry (board_widgets.py:430-431,450-451; lib/cross_repo_deps.py:28-38).
4. A 10 s timeout also shows (UNREACHABLE) (lib/cross_repo_deps.py:50-60).
5. ait update --project allow-list not enforced; only --name, --status Implementing|Done|Folded, --batch, resolution and lock checked (aitask_update.sh:2470-2524,1905-1929); --deps in help list (:316), was missing from page.
6. aitask_explain_context.sh needs --max-plans N, else exits 0 silently (:18,312-314); example corrected; no ait verb.
7. Interactive ait create asks cross-repo project after Dependencies; Labels come before both (aitask_create.sh:2846-2858); offers only resolving projects excluding this one, skipped when none (:1311-1352). Menu labels end in "(from <project>)" (:1898,1927,1941).
8. Paired planning creates one new parent (current task becomes this repo's parent; counterpart created in the other repo); children created one by one in dependency order, labels resolved to real IDs, rare back-fill; no lockstep numbering (cross-repo-child-assignment.md Steps 1-4).
9. Stale-path problem line also covers a path that is not an aitasks project (lib/trail_links.py:546-554).
Also: Folded also blocks (test_xdeps_blocking.sh:113); "usually takes a second or two" dropped (no guaranteed duration; 30 s per-project bound kept, up to four at a time trail_links.py:74,436-444,505); many TR additions from code (new messages, sort order, (+N more), per-project-and-kind dedupe, session-ownership re-check, stop notices) — see the TR diff.
Unlisted, correct (survival run 1, → **corrected**): TR problem line "not registered" → "names a project that does not resolve" (lib/trail_links.py:398-416, 567-568); the TR#blocked-members example entry `backend#16_2` → `backend#16_2 (not checked)` (example only).
Fix pass: "Projects are compared by where they live on disk… registry alias" → TR#what-links-two-trails in plain words (any name that resolves to the same checkout: `project.name`, registry name or tmux session name; lib/trail_links.py:14-21). Folding/renaming are not done "through `/aitask-pick`" (review round 2, corrected).

### `claude-web.md` (Agent C)

| source#section | fact | destination | outcome |
|---|---|---|---|
| #intro | Web pushes only its own branch | claude-web intro (links concepts/git-branching-model) | moved (kept) |
| #intro | "This guide covers…" | — | dropped (writes about the page) |
| #standard-vs-claude-web-workflow | comparison table + "standard workflow…" line | skills/aitask-pickweb#key-differences-* | already-stated |
| same | three-stage diagram | claude-web#run-a-task-on-claude-code-web | moved (kept) |
| #step-1 | board Lock button + email prompt | step 1 | moved (board_detail_screen.py:1889,2133-2146,1339-1366; key l at 1474) |
| #step-1 | ait lock <id> | step 1 | moved (aitask_lock.sh:8) |
| #step-1 | pre-lock optional; pickweb warns and proceeds | step 1, If something goes wrong | moved (pickweb-remote SKILL.md:117-130); warns only when someone else holds a lock |
| #step-2 | /aitask-pickweb <id> / 42_2; only plan approval waits | step 2 | moved (`--profile remote` added) |
| #step-2 | 7-item step list | skills/aitask-pickweb#step-by-step | already-stated; "Loads the remote profile" was wrong |
| (new) | pickweb commits, does not push | step 2; pickweb#completion-and-merging | corrected (rendered SKILL.md:280-343; scan remote-only aitask_web_merge.sh:271) |
| #step-3 | scan, merge w/o dir, plan copy, delete remote branch, sequential branches | web-merge #step-by-step/#merge-strategy/#plan-file-handling/#multiple-branches | already-stated (skip list aitask_web_merge.sh:219-229) |
| #step-3 | archives task (+parent when last child) | web-merge step 6, #when-archival-stops | corrected: conditional (SKILL.md:136-162; aitask_archive.sh:91,844) |
| #step-3 | pushes main and aitask-data | web-merge step 7 | corrected: only after archival (SKILL.md:172-184) — SEE OPEN POINT: skill does not state Step 6 is skipped on GATE_PENDING |
| #the-aitask-data-updated-directory | file table | pickweb#completion-and-merging | moved (when each file is written; rendered SKILL.md:201-222,307-343) |
| same | marker JSON | pickweb#completion-and-merging | corrected: + implemented_with, profile, profile_filename (j2:322-336; rendered:317-332); example now a child task |
| same | git rm -rf exclusion, plan copy | web-merge #merge-strategy/#plan-file-handling | already-stated |
| #execution-profile | "remote, else first alphabetically" | pickweb#execution-profiles; claude-web#the-execution-profile | corrected |
| same | remote.yaml shared with pickrem; extra fields ignored | pickweb#execution-profiles | already-stated (+ description ignored) |
| same | key table | pickweb#execution-profiles | corrected: post_plan_action has no effect |
| #troubleshooting | branch not detected; conflicts prompt/abort; locked by someone else | claude-web#if-something-goes-wrong | moved (conflict prompt SKILL.md:72-79) |
| same | "Web workflow requires an execution profile" | pickweb#execution-profiles | corrected: unreachable |
| same | "ait setup creates one automatically" | pickweb#execution-profiles | corrected: the installer does it |
| same | minimal remote.yaml content | — | dropped: omits rendered_gates: [] so web-merge would materialize a wider gate set (aitask_gate.sh:1095-1096; seed/profiles/remote.yaml:4); committed remote variant doesn't read remote.yaml on Web; replaced by "restore the shipped file, then Retry" |
| #see-also | 4 links | See also | moved (relref; ait lock link added) |
| (code) materialize-gates.md:11-37, aitask_web_merge.sh:99-216 | gates step, WEBMAT_* outcomes, reasons, Retry/Abort, manual repair, never self-record | web-merge step 5, #the-enforced-gates-step-fails | moved (new) |
| (code) SKILL.md:157-162, aitask_archive.sh:1117-1127 | GATE_PENDING backstop, ait gate pass / ait gates run, re-run, never self-signal | web-merge #the-archive-script-reports-pending-gates | moved (new) |
| (code) SKILL.md:24-28,172-184 | re-run re-reads remote marker; same-run push carries a stopped branch's commits | web-merge #re-running-after-a-stop | moved (new) |
| (code) SKILL.md:57-64,145-149,205-207 | diverged-pull prompt, attribution, satisfaction feedback | web-merge #step-by-step | moved (new) |


1. pickweb profile: --profile arg → default_profiles.pickweb (userconfig, then project_config) → default (stub SKILL.md:12-16; aitask_skill_resolve_profile.sh:7-10,68-72); runs aitask-pickweb-<profile>-/SKILL.md, rendering if missing (stub:18-27); only the remote variant is committed (.gitignore:67,83); values fixed at render time (j2:167-173,331-332).
2. NO_PROFILES message unreachable for pickweb; real failure `skill_render: profile '<name>' not found` (aitask_skill_render.sh:81-86).
3. remote.yaml installed by the installer (install.sh:617-633,1859-1860; merge_seed:581-591); ait setup copies seed profiles only when creating a data branch from seed/ (aitask_setup.sh:2616-2638).
4. Only plan_preference changes behaviour (j2:167-173); name → marker profile; post_plan_action no effect (j2:228-230); description never shown.
5. web-merge reads implemented_with (SKILL.md:30,145-149), validates profile pair (aitask_web_merge.sh:113-194).
6. Archival conditional: WEBMAT_INVALID/FAIL (materialize-gates.md:24-34), GATE_PENDING (SKILL.md:157-162); push/delete after (Step 6, :172-190).
7. pickweb pushes nothing (rendered:280-343).
8. pickweb § Completion list said "Move the plan"/"Clean up the dir": plan copied; dir left out of the merge, goes away with the deleted remote branch.
9. Stop paths: Abort → merge committed, task unarchived, Step 6 not reached, remote branch stays (materialize-gates.md:33); re-run re-reads marker from origin/<branch> (SKILL.md:24-28); GATE_PENDING → doc says keep remote branch (scan needs it, aitask_web_merge.sh:256-262).
Fix pass (O1, **corrected**): the web-merge skill does not state that Step 6 (push, `git push origin --delete`) is skipped after `GATE_PENDING` (`.claude/skills/aitask-web-merge/SKILL.md:157-190`), so neither page promises it; `skills/aitask-web-merge#the-archive-script-reports-pending-gates` gives the by-hand finish (`ait gate pass` / `ait gates run`, `aitask_archive.sh <id>`, `./ait git push`, `ait issue-update`). pickweb profile row and step list (`--profile`, then `default_profiles.pickweb`, then `default`, chosen before the data-branch init) → **corrected**; pickweb lock check warns on any lock, the reader's own included (`aitask-pickweb-remote-/SKILL.md:117-130`) → **corrected**.

## Step results

- **Step 1 (gate):** helper `scratchpad/gate.sh` (claim / claim-new / check / record, per-file base + last, task-data files through `./ait git`). Every unit's files claimed clean. One slip each by Agent B (an unrecorded fix-up between two writes on TR, seconds apart) and by me (round-2 fixes applied before `check`): in both cases the diff against `last` was confirmed to be only this task's own edits before `record`. Final commit-gate `check`: 15/15 OK; git status vs tracker: nothing to investigate.
- **Step 2 (restructure):** all units landed (see ledger). Lines: multi_project 216 → ~150, cross_project_dependencies 236 → ~140, claude-web 163 → ~60. New page `commands/projects.md` (`advanced`, weight 39, title "Projects" to match the other `commands/` pages).
- **Step 3 (guide):** two paragraphs added to "How a subject spans levels": an `ait` command's contract goes on its own `commands/` page (an `advanced` page, or its Details section when the page is `intermediate`; create one when missing); a reference page links to a how-to for steps, never for its own rules. `test_docs_review_contract.sh` 71/71.
- **Step 4 (review):** round 1 (independent agent, `--caller audit --budget 0`): level 7 / prose 24 findings over 9 pages, 3 FACT corrections, 5 author decisions. Round 2 after the fix pass: every round-1 item resolved; 8 new minor findings (1 factual), applied by me using the reviewer's wording, then link-checked (no round 3). Final per page: multi_project `level=ok prose=ok reader=not-run(not-beginner)`; cross_project_dependencies `level=ok prose=ok reader=not-run(not-beginner)` with one accepted finding (R-CP1: the `aitask_explain_context.sh` command stays; it needs an `advanced` reference page, owner t2258_7); claude-web, commands/projects, tuis/trails/reference, commands/task-management, skills/aitask-pickweb (now `advanced`), skills/aitask-web-merge `level=ok prose=ok reader=not-run(not-beginner)`; tuis/board/reference no findings. Unresolved: 0 besides R-CP1.
- **Step 5 (depth):** `grep -L '^depth:'` over the three pages is empty. multi_project, cross_project_dependencies and claude-web are `intermediate` (U-A1, U-B1, U-C1 landed); commands/projects and skills/aitask-pickweb are `advanced`; other destinations unchanged (trails/board reference and web-merge `advanced`, task-management `intermediate`).
- **Step 6 (links):** `check_links.py --build` SWEEP PASSED (after every pass); `check_link_relevance.py` reports one link, `workflows/risk-evaluation.md:38` → `tuis/board/reference#task-metadata-fields`, neither added nor retargeted here (outside this child); no link this child added or retargeted is reported. `test_website_doc_lists.sh` 63/63, `test_docs_vocabulary_coverage.sh` 32/32, `check_screenshots.py` PASSED. Inbound anchors: all kept or retargeted in the same unit (`commands/_index:54` → `commands/projects`, `task-notes:46` → `#creating-a-task-in-a-linked-project`; re-greps before removal found no other link).
- **Post-phase (moved_fact_survival_check):** run 1 (one independent agent per file set, removed blocks of sources **and** destinations, guide via `./ait git`): A 115 claims (99 preserved, 0 weakened, 3 example-only missing, 11 listed / 2 unlisted-correct changes); B 165 claims (153 preserved, 0 weakened, 1 minor missing rationale, 9 listed / 2 unlisted-correct); C 110 claims (79 preserved, 7 weakened, 0 missing, 24 listed); D (index + guide) all preserved. Fix pass restored the 7 weakened claims and the missing rationale. Run 2 (fix-pass cuts + 11 newly removed base blocks): 45 claims, 34 preserved, 10 deliberate corrections, 1 weakened (claude-web no longer said the plan is archived; fixed), 0 missing; all 7 run-1 weakened claims confirmed restored.

## Verification

- This plan holds the inventory, the moved-fact table, the survival-check
  counts and the ledger outcomes.
- `check_links.py --build` exits 0. `test_docs_review_contract.sh`,
  `test_website_doc_lists.sh` and `test_docs_vocabulary_coverage.sh` pass.
- Every leaf page in the group has `depth:`. Each page is `intermediate`
  exactly when its required units landed (retag table), and `advanced`
  with a ledger entry otherwise.
- Every inbound anchor listed above resolves, or its links were retargeted in
  the same change. `task-notes.md:46` points at the renamed heading.
- **If U-A1 landed:** `commands/projects.md` exists at `advanced`, it was
  reviewed, link-checked and survival-checked, and every link to it
  resolves. **If U-A1b also landed**, `commands/_index.md` links to it, and
  the pointer section is gone. Otherwise the pointer section (or, when U-A1
  did not run, the full original section) is still there, and `_index:54`
  still resolves to it.
- **If U-A1 did not land:** no page links to `commands/projects`, the
  reference content is still on `multi_project`, and the ledger entry lists
  the outstanding checks for the follow-up child. The same conditional rule
  applies to every unit-created anchor (Step 1).
- The guide change (U-G) appears in the survival counts with its task-data
  `base`.
- No "sibling" or "sister" wording remains on the three pages (except a
  heading held back by the U-A2 fallback, recorded in the ledger).
- Every unit is either fully applied or fully in its fallback (the Step 7
  commit gate).
- The survival counts cover every edited destination file, not only the
  three sources.
- `claude-web` and `skills/aitask-web-merge` describe the archival stop
  paths and their recovery. Neither page states archival as unconditional.

## Post-implementation

Step 9:
- review;
- commit the website (and any `aidocs/`) files as
  `documentation: Audit and restructure the cross-project and remote workflow pages (t2258_10)`;
- commit the guide and plan by path with `aitask_task_commit.sh`;
- archive.

Step 8e notes, sent if the facts still hold at the end:
- t2258_5: the new `tuis/trails/reference` sections and the
  `tuis/board/reference` edits;
- t2258_6: the new `commands/projects.md` (or, if U-A1 fell back, the
  pending follow-up), the `--project` subsections in
  `commands/task-management.md`, and the `skills/aitask-pickweb` /
  `aitask-web-merge` corrections;
- t2258_7: the `commands/_index.md` row retarget.

## Risk

### Code-health risk: medium
- Restructuring could lose a rule, condition or exception while about 300
  lines of reference detail move onto five other pages (one of them new) ·
  severity: low (residual, addressed by inline post-phase
  moved_fact_survival_check) · → mitigation: inline post-phase
  moved_fact_survival_check
- A renamed heading breaks an inbound anchor silently (12 inbound anchor
  links). This is bounded by the keep-or-retarget rule, the Step 6 grep and
  the link check · severity: low · → mitigation: none
- A rename or move could land without its dependent link edit when only one
  of its files is dirty from another session. This is bounded by the
  per-unit gate with defined fallbacks and the Step 7 whole-unit commit
  gate · severity: low · → mitigation: none
- A consolidation inside a destination (the trails key tables, the
  skill-page rewrites) could drop a claim that page already stated. This is
  covered by including destination removed blocks in the survival check ·
  severity: low (residual, addressed by inline post-phase
  moved_fact_survival_check) · → mitigation: inline post-phase
  moved_fact_survival_check
- The edits land on pages later siblings own (t2258_5 TUIs, t2258_6
  commands and skills). This is bounded by the shared-file gate, the
  region-limited edit permissions and the Step 8e notes · severity: low ·
  → mitigation: none

### Goal-achievement risk: medium
- Moved facts may be stale. Two suspected-stale claims were already found at
  planning (the pickweb profile selection, the `ait update --project` list).
  Copying a wrong fact to an `advanced` reference page makes it look
  authoritative. Each moved fact is checked in code and recorded `corrected`
  when wrong · severity: medium (residual: the survival check confirms
  preservation, and only the per-fact code check confirms correctness) ·
  → mitigation: inline post-phase moved_fact_survival_check
- Three retags to `intermediate` are a judgement call. They rest on the
  concept page's `intermediate` and the guide's "depth by who meets the
  idea", and the user reviews them at plan approval · severity: low ·
  → mitigation: none
- A new `commands/projects.md` adds a page that later siblings must account
  for (t2258_6 audits `commands/`). It is announced by note · severity: low
  · → mitigation: none

Reassessment after the inline post-phase: both levels stay **medium**. Code
health stays there for its blast radius (a new page plus eight edited
destinations). Goal achievement stays there because stale facts are only as
good as the per-fact code checks.

### Planned mitigations
- timing: post-phase | name: moved_fact_survival_check | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: low | addresses: code-health restructure fact loss (sources and destination consolidations); goal-achievement stale moved facts | desc: claim-level comparison of every removed block (sources and edited destinations) with the current file set by an independent sub-agent, before commit

## Post-Review Changes

### Change Request 1 (2026-11-26)
- **Requested by user:** six fact-check concerns on the reworked pages (treat as fact checks, not verbatim fixes):
  1. claude-web / web-merge promised that a re-run finishes archival after a stop, though the branch may already be deleted after `GATE_PENDING` and a re-run's Step 3d commit fails after an `Already up to date` merge (user fixture: exit 1).
  2. cross_project_dependencies / task-management described registry membership as mandatory and said update refuses `--xdeps` without a new `--xdeprepo`; validation uses the resolver (tmux / registry / env) and update validates against the stored `xdeprepo` (user fixture).
  3. commands/projects: "every error prints `Error:` and exits 1" ignored `exec`'s passthrough status (fixture: exit 7); the resolution table paired `RESOLVED` with `LIVE`/`OK` though env-only names have no registry row.
  4. skills/aitask-pickweb: "plan approval is always interactive" — with an existing plan and `use_current` the remote variant goes straight to implementation (`aitask-pickweb-remote-/SKILL.md` Step 5 → unconditional checkpoint).
  5. Docs-review coverage: not every edited page was reviewed, and round-2 fixes were only link-checked.
  6. relref anchors placed inside the shortcode on added lines, against `aidocs/framework/documentation_conventions.md:69-72`.
- **Verified:** all six confirmed in code (`.claude/skills/aitask-web-merge/SKILL.md` Step 3d unconditional `git commit`, L157-190; `lib/task_utils.sh` `validate_xdeps_pair` uses `aitask_project_resolve.sh`; `aitask_update.sh` ~L2110-2131 builds the pair from stored values; `aitask_projects.sh` `classify_registry_entry` L274-288 classifies registry entries only; `aitask-pickweb-remote-/SKILL.md` L155-226). Also found: Retry re-uses the marker read at the start of the run (`materialize-gates.md`), so a marker fix does not reach Retry.
- **Changes made:**
  1. claude-web: the stop bullets and closing paragraph now send the reader to the manual finish (web-merge reference) for both stops; a re-run is stated as not dependable, with why. web-merge: Abort-this-branch repair no longer offers "re-run later" as equal; the pending-gates manual finish works whether or not the branch exists (archive, push `main` and task data, delete the branch if still there, issue update); "Re-running after a stop" states the conditional rediscovery and the Step 3 commit failure; Retry vs marker fix corrected.
  2. "registered" → "resolves" (tmux, registry or `AITASKS_PROJECT_<name>`) on cross_project_dependencies and task-management; `ait update` accepts `--xdeps` alone when the task has an `xdeprepo`.
  3. projects: error claim scoped to `ait projects`' own refusals; `list` status described separately from `resolve` output, and env/tmux-only names are not listed.
  4. pickweb intro, key-differences row, step 6, plan-file row, `post_plan_action` row and claude-web step 2: approval only when a plan is written or re-checked.
  5. Final review of all 13 edited/created site pages (see the final review result below).
  6. 20 relref fragments on added lines moved outside the shortcode.
- **Files affected:** workflows/claude-web.md, skills/aitask-web-merge.md, workflows/cross_project_dependencies.md, commands/task-management.md, commands/projects.md, skills/aitask-pickweb.md, tuis/trails/reference.md, workflows/multi_project.md.
- **Final review (all 13 edited/created site pages, independent agent, `--caller audit --budget 0`):** items 1–4 confirmed against the code; no relref fragment left inside the shortcode on a changed line. Findings applied: claude-web lock sentence (no false "so"), "skill variant" defined, gates bullet and closing paragraph reworded; multi_project "registered" → "linked"/"resolves", "Two constraints apply:" run-up cut; cross_project_dependencies intro "names must resolve first"; task-management `ait ls --project` resolution wording (same three-source resolver, `lib/cross_repo_reexec.sh`); pickweb Profile row de-duplicated and intro link → relref; web-merge Abort repair now writes `implemented_with` and handles `ISSUE:` lines, Retry/marker claim narrowed, three "the skill text says" sentences rewritten as behaviour, `<marker_json>` placeholder unified. Final per page: all 13 `level=ok prose=ok reader=not-run(not-beginner)` after these fixes (the two `_index` pages are link-list indexes without `depth`, allowed by the guide). `check_links.py --build` PASSED, vocabulary 32/32, doc lists 63/63.
- **Upstream (from this round):** `.claude/skills/aitask-web-merge/materialize-gates.md:33` — the Abort-this-branch manual repair skips the `implemented_with` write and the issue update, and offers "re-run (no-op merge)" although Step 3d's commit fails after an `Already up to date` merge.

### Change Request 2 (2026-11-27)
- **Requested by user:** two fact-check concerns (not verbatim edits; level and language rules stay in force):
  1. web-merge recovery said every declared gate must pass; the guard reads the enforced active set and accepts `pass` and `skip`.
  2. task-management (intermediate) carried literal `Blocked (by …)` / `UNREACHABLE` status text and the blocker order, and cross_project_dependencies (intermediate) showed the literal CLI status line; the guide reserves status lines and vocabularies for `advanced`.
- **Verified:** `lib/gate_ledger.py` `archive_status_from_text` reads the ENFORCED active set ("a profile-filtered gate can never block archival"), `SATISFIED_STATUSES = {pass, skip}` (L99, `_gate_satisfied` L1340-1346), and `archive_status` adds code-stale `ait gate pass` signatures to the blocked list (`stale_signed_gates`, L1878-1903); `tests/test_gate_orchestrator_registry.py` asserts skip satisfies. `aitask_ls.sh` L618-672: local blockers first, then the first unmet cross-repo dep, joined by `,` with no space; `(UNREACHABLE)` when the status read is empty or `NOT_FOUND`.
- **Changes made:** web-merge pending-gates paragraph states the exact rule (enforced set, latest `pass`/`skip`, stale signatures block, filtered gates never block); pickweb "an enforced gate that is not yet satisfied"; claude-web "gates that the task's profile enforces are still pending". cross_project_dependencies step 2 and task-management "Cross-repo dependencies in the listing" describe the blocker in words; the literal format, order, separator and `(UNREACHABLE)` cases moved to a closing `## Details` section of `commands/task-management.md` (the guide's one-level-up section; `ait ls` has no `advanced` page).
- **Files affected:** skills/aitask-web-merge.md, skills/aitask-pickweb.md, workflows/claude-web.md, workflows/cross_project_dependencies.md, commands/task-management.md.
- **Review of the Change Request 2 regions (independent agent, `--caller audit --budget 0`):** one factual error fixed (the enforced set is the one the gates step writes, or, after `WEBMAT_SKIP:no-profile`, the task's existing `active_gates` or its `gates:` field when that tuple is missing or stale; `aitask_web_merge.sh` L151-155, `gate_ledger.py` `read_active_tuple_from_text` L692-710); the stale-signature rule worded as the one exception; "pending" used throughout; claude-web says who runs machine gates; cross_project_dependencies names "the first linked task it still waits on"; task-management Details gains `<id> (UNRESOLVED)` and the `[unverified]` scan-failure form (`aitask_ls.sh` L626-640, L815-819; `dep_resolution.py` L129-144). No leftover CLI status text on the intermediate pages. Links PASSED, vocabulary 32/32.

### Change Request 3 (2026-11-27)
- **Requested by user:** two fact checks: (1) web-merge's `WEBMAT_SKIP:no-profile` row said the task's `gates:` field governs, contradicting the archival rule (the skip leaves the gate set unchanged; a valid existing `active_gates` still applies — user fixture: legacy marker + declared gate + valid empty active set → `WEBMAT_SKIP:no-profile`, `NO_GATES`); (2) task-management Details promised a stderr warning whenever the scan cannot run, but a missing/non-executable `aitask_gate.sh` sets the failed state without warning (user fixture).
- **Verified:** `aitask_web_merge.sh` L151-155 (returns without writing); `aitask_ls.sh` `build_dep_blocking_map` L337-357 (`[[ -x "$gate_script" ]] || { dep_scan_state="failed"; return 0; }` precedes the warn branch, which fires only on non-zero exit or a missing `SCAN_OK` final line).
- **Changes made:** the `WEBMAT_SKIP` row says the gate set is left unchanged and archival uses the existing enforced set (linked to the archival rule); the Details paragraph scopes the warning to a scanner that ran and failed or returned incomplete output, and says no warning is printed when the script is missing or not executable.
- **Files affected:** skills/aitask-web-merge.md, commands/task-management.md.

## Final Implementation Notes
- **Actual work done:**
  - **Inventory and verdicts** for the three pages (measured at 46b34ee2f).
  - **Three restructures into how-tos**, all retagged `advanced` → `intermediate` because the units that removed their `advanced` detail landed:
    - `workflows/multi_project.md`: the `ait projects` contract (verbs, identity fields, registry file, groups, name resolution, `resolve` output, `list` status) moved to a **new `commands/projects.md`** (`advanced`); `commands/_index.md:54` retargeted to it; `#creating-a-task-in-a-sibling-project` renamed to `#creating-a-task-in-a-linked-project` with `task-notes.md:46` retargeted.
    - `workflows/cross_project_dependencies.md`: trail entry states, link rules, search and jump moved to new `tuis/trails/reference.md` sections (`#cross-repo-entries`, `#linked-trails-and-the-jump`), whose links now point at their own sections (ownership was inverted); board `↗`/`#` facts to `tuis/board/reference.md`; `--project`/`--xdeps`/`--xdeprepo` rules to `commands/task-management.md` (new subsections plus a closing `## Details` section holding the exact `ait ls` blocked-status format).
    - `workflows/claude-web.md`: one 3-stage procedure; the marker schema and profile rules moved to `skills/aitask-pickweb.md` (retagged `advanced`); a new `skills/aitask-web-merge.md#when-archival-stops` documents the gates step, the pending-gates guard, Retry/Abort, the manual finish and why a re-run is not dependable.
  - **Contributor detail** (registry write path, lock, awk single-name lookup) added to `aidocs/framework/cross_repo_references.md`, whose stale "gitignored" and "reserved for future auto-clone" lines were corrected.
  - **Guide lesson** (task-data branch): an `ait` command's contract goes on its own `commands/` page (advanced, or its Details section when intermediate); a reference page links to a how-to for steps, never for its own rules.
  - **Checks:** review rounds 1, 2, a final all-pages round and a Change-Request-2 regions round; survival runs 1 and 2 (sources and destinations, guide via `./ait git`) ending at 0 missing / 0 weakened; links PASSED, doc lists 63/63, vocabulary 32/32, docs-review contract 71/71, screenshots PASSED.
- **Deviations from plan:**
  - Agent B retargeted `tuis/trails/how-to.md` L34/L82 to the trails reference (the plan kept how-to links on the workflow anchors): their link text promises "every state" / "every line the dialog can show", which only the reference lists now.
  - `commands/projects.md` is titled "Projects" with an `## ait projects` heading, matching the other `commands/` pages, not "`ait projects`".
  - `skills/aitask-pickweb.md` was retagged `advanced` (review R-PW1) and three untouched lines on it (profile row, step 2, suggested workflow) were corrected because they contradicted the corrected profile rule on the same page.
  - The `ait ls` blocked-status format went to a `## Details` section of the intermediate `commands/task-management.md` (Change Request 2), since `ait ls` has no `advanced` page.
  - Three user change requests (fact checks) after the first review prompt; see Post-Review Changes.
- **Issues encountered:**
  - Subagents could not write report files; their hand-backs were saved to the scratchpad by the orchestrator.
  - Two gate-discipline slips (Agent B: an unrecorded fix-up write; me: round-2 and relref edits applied before `check`); each was resolved by diffing against `last` and confirming only this task's own edits before `record`. Final commit gate 15/15 OK, no foreign change.
  - Several facts were wrong in the old pages and some in the first rewrite (all corrected from code): `ait ls`/`/aitask-pick` do not skip cross-repo-blocked tasks; names must resolve (tmux / registry / env), not be registered; the pickweb profile rule; plan approval is skipped with an existing plan under `use_current`; web-merge archival is conditional and a re-run after a stop is not a dependable finish; the archive guard reads the enforced set and accepts `pass`/`skip`.
- **Key decisions:**
  - All three workflow pages are `intermediate`, matching `concepts/cross-repo-references`; status lines, outcome tables and internal paths live on `advanced` reference pages or in a Details section.
  - R-CP1 accepted: the single `aitask_explain_context.sh --max-plans N --project <name>:<path>` command stays on cross_project_dependencies (it was there before); it needs an `advanced` reference page (owner: t2258_7).
  - The web-merge pages document the manual finish as the dependable recovery, because the skill neither skips Step 6 after `GATE_PENDING` nor skips Step 3d's commit after an `Already up to date` re-merge.
- **Upstream defects identified:**
  - `.claude/skills/aitask-web-merge/SKILL.md:157-190` — the `GATE_PENDING` backstop does not say to skip Step 6, so the run can push and `git push origin --delete` the branch the prescribed re-run needs.
  - `.claude/skills/aitask-web-merge/SKILL.md:87-101` — on a re-run after a stop the merge is `Already up to date` and the unconditional Step 3d `git commit` fails; no skip rule (confirmed by the user's fixture, exit 1).
  - `.claude/skills/aitask-web-merge/materialize-gates.md:33` — the Abort-this-branch repair text offers "re-run (no-op merge)" and omits the `implemented_with` write and the linked-issue update.
  - `.aitask-scripts/aitask_archive.sh:106-108` — exit 2 also covers VERIFICATION_PENDING / VERIFICATION_DEFERRED, but web-merge handles only `GATE_PENDING`.
  - `.claude/skills/aitask-pickweb/SKILL.md:12-16` — the profile is resolved before the data-branch init, so on a fresh Claude Code Web clone of a data-branch repo `default_profiles.pickweb` is invisible and `default` (not committed, cannot render there) is chosen; pickweb fails without `--profile remote`.
  - `.claude/skills/aitask-pickweb/SKILL.md.j2:376-385` — the Profile Schema says `name`/`description` are "shown during profile load" and `post_plan_action` is used at the checkpoint; neither is true.
  - `.claude/skills/aitask-pickweb-remote-/SKILL.md:134-147` — Done / orphaned-parent tasks are told to use aitask-web-merge locally, which only handles marker-bearing remote branches.
  - `.claude/skills/task-workflow/execution-profile-selection-auto.md:4-5` — claims pickweb's Step 1 references it; pickweb has no such step.
  - `.aitask-scripts/aitask_update.sh:311-324` — help says only administrative fields are allowed cross-repo, but `main()` (L2470-2524) enforces only the refusals, so any other flag is applied in the other project.
  - `.aitask-scripts/lib/task_utils.sh:3017-3019` — `validate_xdeps_pair` says "is not registered" for any `NOT_FOUND`, though resolution also covers tmux and the env tier.
  - `.aitask-scripts/aitask_create.sh:133-135` — help says `--xdeps`/`--xdeprepo` are "required together"; `--xdeprepo` alone is accepted.
  - `.aitask-scripts/aitask_ls.sh:68-71` — help says `--project` must come first; `lib/cross_repo_reexec.sh:35-56` accepts it anywhere.
  - `.aitask-scripts/aitask_explain_context.sh:312-314` — without `--max-plans` it exits 0 silently although its help calls the flag required.
  - `.aitask-scripts/aitask_projects.sh:222-237` — with no Python, `list` blames the registry file ("Cannot read the project registry … Fix or remove it").
  - `.aitask-scripts/aitask_project_resolve.sh:89` — `--help` still says NOT_FOUND means "No registered project matched".
  - `seed/project_config.yaml:444` — says the profile fallback is "interactive selection / auto-select"; the resolver falls back to `default`.
- **Notes for sibling tasks:**
  - **Method:** three restructure agents on disjoint file sets with one brief, a per-file snapshot gate (`claim` / `claim-new` / `check` / `record`, task-data files via `./ait git`), one independent review agent plus one survival agent per file set (removed blocks of sources AND destinations), one fix agent, then round 2. Re-create `scratchpad/gate.sh` and `scratchpad/removed_blocks.py` from the plan's Step 1 and post-phase descriptions.
  - **Expect fact errors in "how the skill recovers" claims.** Read the skill's stop paths, and test re-run paths (a no-op re-merge fails at commit). Do not document recovery the skill text does not guarantee.
  - **Check "registered" vs "resolves"** wherever a page talks about cross-repo names: every consumer uses `aitask_project_resolve.sh` (tmux, registry, env).
  - **Status lines on intermediate pages:** describe in words; put the literal format on an `advanced` page or in a closing Details section.
  - **Leftovers by owner:**
    - **t2258_5:** the new `tuis/trails/reference` sections and `tuis/board/reference` additions; unchecked whether `#` works in `ait trails` (no `#` row in its key table).
    - **t2258_6:** the new `commands/projects.md`; `commands/note.md` L22/L56/L59 still say "sibling project" and use `mobile`; `skills/aitask-pickrem.md:39,55` and `commands/lock.md:150` keep the old pickweb/pickrem profile wording; `skills/aitask-pickweb.md` "Suggested Workflow" repeats the claude-web diagram and its intro keeps bold emphasis and relative links; the `ait update` option table has no `--xdeps`/`--xdeprepo` rows.
    - **t2258_7:** `aitask_explain_context.sh --project` needs an `advanced` reference page (R-CP1); `concepts/cross-repo-references` See also could link `commands/projects`; `commands/_index.md` still uses relative links elsewhere.
- **Ledger outcomes:** ledger empty (every unit landed on the first pass).
