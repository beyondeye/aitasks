---
Task: t1957_5_docs_trail_cross_repo.md
Parent Task: aitasks/t1957_trail_cross_repo_blockers_and_linked_trails.md
Sibling Tasks: aitasks/t1957/t1957_1_*.md, aitasks/t1957/t1957_2_*.md, aitasks/t1957/t1957_3_*.md, aitasks/t1957/t1957_4_*.md
Archived Sibling Plans: aiplans/archived/p1957/p1957_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-14 19:11
---

# t1957_5 — Docs: cross-repo blockers on trail cards, `--trail`, `L` linked-trail jump

## Context

t1957_1–4 shipped three user-visible things that the website does not describe yet:

- **Cross-repo status on trail cards** (t1957_1). Covers the trail cards in the
  By-Trail view and in `ait trails`.
- **`ait trails --trail <handle>` and the running-instance focus mailbox**
  (t1957_2).
- **The `L` Linked Trails search and cross-session jump** (t1957_3 discovery,
  t1957_4 action). Since then, t1979 merges repeated `L` presses while a search
  is running.

This child writes the user docs, describing the current state only. The parent
plan is `aiplans/p1957_trail_cross_repo_blockers_and_linked_trails.md`.

## Verification of the existing plan (2026-10-14)

The existing plan was written before the siblings shipped and named the target
pages only. Every UI string below was checked against the current code (HEAD
`7f1d0614a`):

- **Card states:**
  - `board/board_trail_view.py`: `_xdep_member_display`, `_remote_status_text`,
    the ghost label `👻 cross-repo member — read-only`, and the
    `🌐 blocked (cross-repo)` / `↗ …` labels on `TrailTaskCard`.
  - `lib/cross_repo_deps.py` `classify_xdep_status`: only `Done` unblocks.
    `""` or `NOT_FOUND` give `(UNREACHABLE)` and block. Any other status shows
    as `[Status]` and blocks.
- **Linked trails:**
  - `board_trail_view.py`: `linked_scan_error_text` (7 kinds, verbatim), the
    `LinkedTrailsScreen` title and its two incomplete-search notes, the
    `LinkedTrailItem` row (`project · handle · name` plus at most 3
    `└ reason` lines), and the `TrailJumpConfirmScreen` buttons `Switch` /
    `Stay here`.
  - `board/board_trail_screen.py`: `Binding("L", "trail_linked",
    "Linked Trails")`, every notice in `action_trail_linked` and
    `_on_trail_links`, `prepare_linked_trail_jump` /
    `finish_linked_trail_jump` (including the manual
    `ait projects exec <p> -- ./ait trails --trail <h>`), and t1979's merging
    of repeated presses (`_trail_link_pending`).
  - Relation and reason prefixes come from
    `aiplans/archived/p1957/p1957_3_*.md` (`fwd-xdeps`, `fwd-member`,
    `rev-xdeps`, `rev-member`). Identity is by project root, and a third-repo
    member is not a link. Each project export has a 30 s timeout.
- **`--trail`:**
  - `board/trails_app.py` `main()`: a handle must match `art:<id>`, otherwise
    `parser.error`.
  - `_open_trail_by_handle`: an unknown handle triggers a rescan, then
    `Trail <h> not found in this project` and the selector.
  - The mailbox notices `Trail <h> opens when this dialog closes` and
    `Ignored a malformed trail request`.
  - `ait trails` passes `"$@"` through (`aitask_trails.sh`).
- **Footer order:** on the board, `trail_linked` comes right after
  `trail_summary_expand` (`aitask_board.py` ~2302), so the By-Trail footer
  reads `… v Summary   L Linked Trails   m Move to Col   M Move Wave`.
  `check_action` hides `L` unless a trail is loaded.
- **When checks run:** with the drift check, i.e. on trail open, `d`, board
  sync and view entry. `r` and tab switches reuse cached results (t1957_1
  note and Final Implementation Notes).

The plan's shape still holds. The real work is the content, set out below.
**Placement rule:** the full explanation lives in **one** place,
`workflows/cross_project_dependencies.md`. The trails and board pages get
their key rows, a short paragraph and a relref to it, so the error-line tables
and the relation rules are not copied across four pages.

Anchor names (Hugo slugs) used below:

- `#cross-repo-dependencies-in-implementation-trails`
- `#jumping-to-a-linked-trail-in-another-project`

## Implementation

### 1. `website/content/docs/workflows/cross_project_dependencies.md`

1. **Intro paragraph (line 9):** "see cross-repo links **on the board**" →
   "see cross-repo links **on the board** and **in implementation trails**,
   jump between linked trails,".
2. **New `## Cross-repo dependencies in implementation trails`**, placed after
   "Seeing cross-repo references on the board" and before "Reading another
   project's tasks and files". It applies to both the By-Trail view and
   `ait trails`, linked with relref to `/docs/workflows/implementation-trails`
   and `/docs/tuis/trails`.
   - `### Blocked members`: a live member with `xdeps` shows the same `↗` line
     as a board card. Example block:

     ```
     🌐 blocked (cross-repo)
     ↗ backend#42 [Implementing], backend#16_2
     ```

     A table gives each entry's form:
     - `backend#42`: Done;
     - `backend#42 [Implementing]`: not done;
     - `backend#42 (UNREACHABLE)`: the project cannot be resolved, or the task
       is missing;
     - `backend#42 (checking…)`: a check is running;
     - `backend#42 (not checked)`: nothing has checked it yet, typically an
       `xdeps` entry added on disk and then picked up with `r`.

     State the rule plainly. `🌐 blocked (cross-repo)` appears only when a
     **finished** check finds a linked task that is not `Done`, and an
     unreachable task counts as not `Done`. A check that is still running or
     has not run never marks a member blocked. The same rules as
     [How blocking works](#how-blocking-works) apply.
   - `### Members from another project`: a `backend#42` trail member is a
     ghost card (`👻 cross-repo member — read-only`) with one live status line.
     A table lists:
     - `📋 <Status>`;
     - `🌐 (UNREACHABLE)`;
     - `🌐 (checking…)`;
     - `🌐 (not checked)`.

     The card is marked landed (`✔`, struck through) only when its own project
     reports `Done`.
   - `### When the checks run`: checks run in the background with the trail's
     freshness check:
     - when a trail is opened;
     - on `d`;
     - in the board, on a sync and on entering the By-Trail view.

     `r` and tab switches start no check and reuse the last results.
3. **New `## Jumping to a linked trail in another project`**, right after the
   section above.
   - `### What makes two trails linked`: give the four rules, with trail B in
     `backend` and trail A in `frontend`:
     - a member of A has `xdeprepo: backend` and an `xdeps` entry that is a
       member of B;
     - A has a member `backend#<id>` that is a member of B;
     - and the two reverse rules.

     Projects are compared by their location on disk, not by name, so an alias
     still links. A task in a third project that both trails mention is not a
     link. The search covers every registered project, plus any project the
     trail's members name directly.
   - `### Finding a linked trail`:
     - Press **`L`** with a loaded trail, in the board's By-Trail view or in
       `ait trails`. The notice reads "Searching for linked trails in other
       projects…", and the search usually takes a second or two. Each project
       is searched in its own checkout and has 30 seconds.
     - A complete search with no links shows "No linked trails in other
       projects".
     - Otherwise the **Linked trails** dialog opens. Each row reads
       `<project> · <handle> · <name>`, with up to three `└` reason lines. Give
       an example block, then say what the prefixes mean: `fwd-…` comes from
       this trail and `rev-…` from the other one, matching the four rules.
     - Keys: ↑/↓ move, Enter jumps, Esc cancels.
     - **Incomplete search:** the dialog says "Some projects could not be fully
       searched — the list may be incomplete:", or "No linked trails found —
       the search was incomplete:" when it found nothing. It never claims
       "none" for an incomplete search. A table gives the seven error lines
       verbatim, with what each means or how to fix it: stale path →
       `ait projects update`; not registered → `ait projects add`. A
       `searched in part` project still has its links listed.
     - One sentence for each of these:
       - another `L` while a search runs does not start a second search; the
         newest request runs when the current one finishes;
       - switching tabs, closing the trail or leaving the view drops the
         result;
       - if the trail reloads with different content, you are asked to press
         `L` again.
   - `### What the jump does`: three numbered steps.
     1. Find that project's tmux session: any running session that belongs to
        it, preferring its default session name. When none is running, start
        one.
     2. Open the trail in that project's `ait trails`. If one is running, it
        switches to the trail; otherwise a new `trails` window runs
        `ait trails --trail <handle>`.
     3. Switch your terminal to that session.

     After that:
     - **Before-switch dialog:** a target on an older aitasks gets "run
       `ait upgrade` there; you land in its session without the trail
       opened". A session started under a fallback name because
       `tmux.default_session` was unusable is also reported here. The buttons
       are **Switch** / **Stay here**. The reason it comes first: once you
       have switched, a message left behind would go unseen.
     - **Outside the aitasks tmux server:** nothing starts or switches. The
       notice gives the command to run instead, shown as a `bash` block:
       `ait projects exec backend -- ./ait trails --trail art:…`.
     - **Session changed meanwhile:** "The tmux session for `<project>`
       changed before the jump — press L to try again".
     - **Ownership:** trails stay owned by their local task. The jump opens
       the other project's own `ait trails`, and a trail from another project
       is never shown inside this one.
4. **See also:** add [Implementation Trails] and [Trails] (relref).

### 2. `website/content/docs/tuis/trails/_index.md`

- In the Relationship table row "Trail keys (`s`, `r`, `d`, `R`, `v`,
  `Enter`)", add `L`.
- In Purpose (the read-only paragraph), add: "`L` searches other projects for
  linked trails and can start a tmux session for one and open the trail in its
  own `ait trails`. It writes nothing either", with a relref to
  `…/cross_project_dependencies#jumping-to-a-linked-trail-in-another-project`.
- In Launching, add the bullet "`ait trails --trail <handle>` opens that trail
  directly instead of the selector (`<handle>` is `art:<id>`)", with a pointer
  to the reference page.

### 3. `website/content/docs/tuis/trails/how-to.md`

- **How to Open a Trail:** add a paragraph on `ait trails --trail art:<id>`.
  An unknown handle opens the selector with "Trail `<handle>` not found in this
  project".
- **How to Read the Waves and the Summary:** after the ghost-card sentence,
  add one sentence about `↗` / `🌐 blocked (cross-repo)` and the live status
  of cross-repo ghosts, with a relref to
  `#cross-repo-dependencies-in-implementation-trails`.
- **How to Keep a Trail Current:**
  - `r` bullet: add "…and it does not re-check cross-repo dependencies".
  - `d` bullet: add "…and the members' cross-repo statuses".
- **New `### How to Jump to a Linked Trail in Another Project`**, after "How
  to Pick a Member". Four short steps:
  1. Press **L**.
  2. Read the list and its reason lines.
  3. Press Enter on one.
  4. Confirm the dialog if one appears.

  Then one line on the outside-tmux manual command and a relref to the
  workflow section for the link rules and error lines.

### 4. `website/content/docs/tuis/trails/reference.md`

- **Keybindings table:** after `v`, add `| L | Search other projects for
  trails linked to the active trail, and jump to one | Trail loaded (hidden
  while it loads or after it failed to load) |`.
- **New `### In the linked-trails dialog`** (`Up`/`Down`, `Enter` jump,
  `Escape` close) and `### In the jump confirmation` (`Switch`, `Stay here`,
  `Escape` = stay). Same table style as the existing selector and detail
  tables.
- **What each refresh reads:** after the table, add one sentence: cross-repo
  dependency statuses are checked with the freshness check, when a trail opens
  and on `d`; `r` and the tab keys reuse the last results.
- **Launch and environment:**
  - New row `ait trails --trail <handle>`: opens that trail at launch. A
    handle that is not `art:<id>` is refused before the TUI starts. An unknown
    handle opens the selector with the not-found notice.
  - New bullet **Jump target**: inside the aitasks tmux server, a running
    `ait trails` accepts a trail sent by an `L` jump from another project and
    switches to it. When several run in that session, the first in window
    order receives it. With a dialog open, the trail opens when the dialog
    closes ("Trail `<handle>` opens when this dialog closes"). An open trail
    selector is closed instead.
  - **Read-only** bullet: add `L`, which may start a tmux session for another
    project and open its `ait trails`, but writes nothing.

### 5. `website/content/docs/tuis/board/reference.md`

- **Keyboard Shortcuts (Board Navigation):** after the `v` row, add `| L |
  Search other projects for trails linked to the shown trail, and jump to one
  | By-Trail view (trail loaded) |`.
- **By-Trail section:** after the ghost-card sentence ("…appear as read-only
  ghost cards."), add a short paragraph:
  - blocked members carry `↗` / `🌐 blocked (cross-repo)`;
  - cross-repo ghosts show their live status;
  - `L` finds and jumps to linked trails in other projects;
  - relref to `/docs/workflows/cross_project_dependencies` and its two
    anchors.
- **Keeping the view current:**
  - `d` row: add "and the members' cross-repo statuses".
  - In the "Reach for `r`" sentence, note that `r` reuses the last cross-repo
    results.
- **Footer literal:** insert `L Linked Trails` after `v Summary`. Extend the
  next sentence: "`L Linked Trails` only while a trail is loaded."

### 6. `website/content/docs/tuis/board/how-to.md` (By-Trail steps)

Add step 6: work in other projects. A member blocked by another project shows
`🌐 blocked (cross-repo)`, and **L** lists the linked trails in other projects
and jumps to the chosen one. Relref to the workflow section.

### 7. `website/content/docs/workflows/implementation-trails.md` (Reading a Trail on the Board)

After the ghost-card sentence (line 88), add one sentence. It says that a
cross-repo member shows its live status from its own project, that a member
blocked by another project's work is marked, and that **`L`** finds linked
trails in other projects. Relref to the workflow anchors. This keeps the
card-anatomy prose on this page current. It is a pointer, not a copy.

## Verification

- Every quoted UI string still matches the code. Grep each string written into
  the docs (the notices, dialog notes, error-line stems, ghost label, footer
  label, and the `--trail` error/notice) against
  `.aitask-scripts/board/board_trail_screen.py`, `board_trail_view.py` and
  `trails_app.py`. Expect one hit each.
- `cd website && python3 check_links.py --build` must pass (mandatory).
- `cd website && hugo build --gc --minify` must succeed.
- Links were added, so offer `python3 check_link_relevance.py` as a report.

## Step 9 reference

Current-branch mode, so nothing is merged. After review, commit the docs
(`documentation: … (t1957_5)`) and the plan separately, then archive this child
with `aitask_archive.sh 1957_5`. Parent t1957 archives automatically, because
this is its last child.

## Risk

### Code-health risk: low
- Docs-only change across 7 pages. The new internal links could be broken
  (a wrong anchor slug or a hand-written relative path) · severity: low ·
  → mitigation: none (addressed in-plan: relref plus a
  `check_links.py --build` gate in Verification)

### Goal-achievement risk: low
- Quoted UI strings or the footer order could drift from what shipped, which
  would be documentation that misleads · severity: low · → mitigation: none
  (addressed in-plan: every string was verified against HEAD during planning,
  and the Verification step re-greps each one)
