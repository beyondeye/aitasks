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

## Moved-fact table

(source#section → fact → destination#anchor →
`moved` / `already-stated` / `corrected` / `dropped(reason)`; filled from the
agents' reports and the survival check.)

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
