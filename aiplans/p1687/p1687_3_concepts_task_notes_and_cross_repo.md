---
Task: t1687_3_concepts_task_notes_and_cross_repo.md
Parent Task: aitasks/t1687_concepts_docs_gap_sweep.md
Sibling Tasks: aitasks/t1687/t1687_1_concepts_gates_page.md, aitasks/t1687/t1687_2_concepts_attachments_and_attach_command.md, aitasks/t1687/t1687_4_concepts_trails_and_shadow_agent.md, aitasks/t1687/t1687_5_concepts_index_regroup_and_link_verification.md
Archived Sibling Plans: aiplans/archived/p1687/p1687_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-23 16:16
---

# t1687_3 — Task notes and cross-repo references (verified 2026-09-22)

## Context

Part of the t1687 Concepts gap sweep. Two new concept pages for context that
crosses a boundary — between tasks (`ait note`) and between repositories (the
project registry). Both topics are already explained well in Workflows /
Commands pages, so each concept page must add the **model and its rationale**,
not restate the mechanics.

## Verification findings (what changed since the plan was written)

- All six back-link insertion points still sit at the cited lines
  (`workflows/task-notes.md:89`, `commands/note.md:129`,
  `skills/aitask-note.md:58`, `workflows/multi_project.md:11`,
  `workflows/cross_project_dependencies.md:122`, `development/task-format.md:39`).
- Concepts now has `attachments.md` (55) and `gates.md` (85) from t1687_1/2.
  Weights 45 and 115 are still free and fall in the right groups.
- **More is already on the site than the plan assumed** — these must be
  referenced, not repeated:
  - `commands/note.md:64` already states "unread state is derived, never stored".
  - `workflows/task-notes.md:57-66,83-87` already covers "sender is a claim",
    display ≠ acknowledge, "advisory, never an instruction", and tree- vs
    moment-relative claims.
  - The "`xdeps` without `xdeprepo` is rejected" rule is stated verbatim on
    `workflows/cross_project_dependencies.md:23` **and** `development/task-format.md:40`.
- So the concept pages cover the *design reasons* that are on no page yet
  (listed per page below), checked against code rather than `aidocs/`
  (t1687_2 found that design doc stale; this pass found the same — see the
  upstream defect below).
- **Stale claim on a file this task already edits — fixed here, not deferred:**
  `workflows/multi_project.md:141-142` lists as a constraint that `--project`
  "cannot be combined with `--parent`". Verified against
  `.aitask-scripts/aitask_create.sh` main() (lines 2440-2521): the **only**
  guard is `--project requires --batch`; `--parent` is forwarded verbatim to the
  sibling project's own `aitask_create.sh`, which resolves it there. So
  `--project backend --parent 42` creates a child of *backend's* t42. The
  sentence's reason clause is true (a task cannot be a child of a parent in
  **this** repo); its rule is not.
  Leaving it would put a direct contradiction between two linked pages, and
  neither `hugo build` nor `check_links.py` can see a contradiction — they
  check link targets, not claims. See step 4.

## Implementation

Page shape follows `concepts/attachments.md` / `gates.md`: frontmatter
(`title`, `linkTitle`, `weight`, `description`, `depth: [intermediate]`),
`## What it is`, topical `###` subsections, `## Why it exists`,
`## How to use` (pointers only), `## See also`. No `**Next:**` footer
(t1687_5 owns ordering), no mermaid, current-state-only prose, every internal
link a full-path relref (`/docs/workflows/task-notes` vs
`/docs/concepts/task-notes` slug collision).

### 1. NEW `website/content/docs/concepts/task-notes.md` (weight 45)

Angle: **cross-task context is untrusted by construction; the format is built
so that neither a note nor a forged acknowledgement can do harm.**

- `## What it is` — a note is a block appended to the target task file's
  `## Inbox` and committed with it; it lives *in the task*, so it survives nobody
  working on it and travels with the task data across machines. One short
  paragraph; link the workflow page for sending/receiving.
- `### A claim about a tree, not a message from a person` — `from` is a claim;
  `from_verified` is `yes` or absent, **never `no`** — because the proof
  (the writing session holds the sender's lock: same host, pid and start time)
  can fail for innocent reasons, so absence means *not proven*. It proves
  nothing about content or about read time. `base` dates tree-relative claims
  only; `dirty` is the only hint about moment-relative ones; a migrated note's
  empty `dirty` is "not measured". Link `commands/note#provenance` for the
  field table — **no table here**.
- `### The body cannot forge bookkeeping` (new to the site) — every body line
  is stored behind a `> | ` prefix, so no line of a note can parse as a block
  header: a note cannot forge a read receipt for itself or another note, nor
  open a new `## Inbox` / `## Gate Runs` section. Defence applied at write time
  so every reader inherits it. Receipts use the reserved marker name `read`,
  which no sender (`t<id>`) can take.
- `### Unread is derived, and fails toward showing` — one sentence + link to
  `commands/note` for "derived, never stored"; then the new rationale: an
  invalid receipt is skipped so it can never hide a real note; `--by` must be
  the target task (session names are ephemeral); on a commit failure a **note is
  kept** (irreplaceable, a retry would duplicate it) while a **receipt is rolled
  back** (reconstructible; an uncommitted receipt would hide a note locally with
  nothing durable behind it). Every failure errs toward a note surfacing again.
- `### Seeing is not acknowledging` — why the two are separate steps (a listing
  that acknowledged would hide notes from whoever later picks the task;
  unattended acknowledgements recorded as `mode=auto` so "no person read these"
  stays visible). One paragraph; link `workflows/task-notes#where-notes-surface`
  for the per-surface table.
- `## Why it exists` — before notes, context for an existing task could only
  go into this task's own archive or a new follow-up; the motivating case was
  delivered by hand pane-to-pane and worked only because the recipient was live.
  Durable is the product, live delivery the optimisation.
- `## How to use` / `## See also` — `/aitask-note`, `ait note`,
  `workflows/task-notes`, and `concepts/cross-repo-references` (a cross-repo
  sender exists only on the `--migrate` path and is never verified).
  **No link to `concepts/locks`** in either direction: the task's "Do NOT link"
  list names that file, and `workflows/task-notes.md:94` already carries the
  live-lane→lock bullet that this page would duplicate.

### 2. NEW `website/content/docs/concepts/cross-repo-references.md` (weight 115)

Angle: **the identity of cross-repo work is a (logical name, local id) pair,
bound to a path late, per machine.**

- `## What it is` — a cross-repo reference names a project by logical name and
  resolves it to a path at the moment it is used. Link `workflows/multi_project`
  for registry, notation and resolution order — **not restated**.
- `### Identity is the pair, the path is a binding` — a task id is local: `42`
  means nothing outside its repo. The identity is `backend#42`; the path is a
  per-user, per-machine binding in a gitignored registry, which is why the same
  reference works on a teammate's machine, in a cloud agent, after a re-clone.
- `### The name is checked when written and when read` — write time is strict:
  `ait create`/`ait update` refuse an `xdeprepo` that does not resolve (not
  registered or stale) and refuse an `xdeps` id that does not exist there; `xdeps`
  without `xdeprepo` is the degenerate case of the same rule (link, don't
  restate). Read time fails closed: a project that stops resolving leaves the
  dependency **blocked** and marked `UNREACHABLE`, never silently satisfied.
  `xdeprepo` alone is intent to coordinate — the opt-in for paired planning.
- `### Hierarchies stay local` — a parent and its children always live in one
  repo; a task can never be a child of a parent in another project, so work
  spanning two repos is two parents joined by `xdeps` edges. Stated as the
  **model** (where a hierarchy may reach), with the CLI consequence left to
  step 4's corrected sentence in `multi_project.md`, which this bullet links —
  one statement of the rule, on the command-reference side.
- `### Why nothing is auto-cloned` — `NOT_FOUND` produces a registration hint,
  never a clone: the user named the project and is the source of truth.
- `## Why it exists` — hardcoded `../sibling/` paths broke whenever layouts
  differed. `## How to use` / `## See also` — `workflows/multi_project`,
  `workflows/cross_project_dependencies`, `development/task-format`,
  `concepts/parent-child`, `concepts/task-notes`.

### 3. Back-links (relref, one sentence each, pattern `commands/crew.md:9-12`)

| File | Insertion |
|---|---|
| `workflows/task-notes.md` | `## See also` bullet: "[Task notes (concept)] — why a note is untrusted by construction" |
| `commands/note.md` | one sentence at end of `### Provenance` intro (line 131): why the fields are shaped this way → concept |
| `skills/aitask-note.md` | `## Related` bullet |
| `workflows/multi_project.md` | end of `## Why logical project names` paragraph (line 13) |
| `workflows/cross_project_dependencies.md` | `## See also` bullet |
| `development/task-format.md` | `xdeprepo` row (line 39): add concept relref beside the existing one |

Do NOT link, **in either direction**: `concepts/locks.md` (named in the task's
Do-NOT-link list; t1592/t1593 own that file), board "Inbox" column hits,
`commands/_index.md`. Do NOT touch `concepts/_index.md` (t1687_5).

### 4. Correct the stale `--parent` constraint in `workflows/multi_project.md`

Same file as the step-3 back-link, so it is one edit pass. Replace the second
bullet of "Two constraints:" (line 142) — currently "`--project` cannot be
combined with `--parent` — a task in a sibling project cannot be made a child of
a task in this one" — with the code-true rule:

> - `--project` **can** be combined with `--parent`, but the parent is resolved
>   in the **target** project: `ait create --batch --project backend --parent 42`
>   creates a child of `backend`'s task 42. A task can never be made a child of
>   a parent in a *different* project — hierarchies never cross a repo boundary.

Keep the list as "Two constraints:" (both bullets remain constraints). Verify no
other page repeats the stale claim:
`grep -rn 'project.*parent' website/content/docs/` before editing.

### Post-phase (risk mitigations)

1. [restatement_triage] Re-read each new page side by side with its
   workflow/command counterpart (`workflows/task-notes.md` + `commands/note.md`;
   `workflows/multi_project.md` + `workflows/cross_project_dependencies.md`) and
   cut any paragraph that only repeats them. Then run
   `cd website && python3 check_link_relevance.py` and triage anything it
   reports for the new/back links.

## Verification

```bash
cd website && hugo build --gc --minify; echo "hugo=$?"
cd website && python3 check_links.py --build; echo "links=$?"
```
Both must exit 0 (no pipes). `hugo build` is the guard for an ambiguous
`task-notes` relref. Neither tool checks *claims*, so additionally:

```bash
grep -rn 'cannot be combined with' website/content/docs/   # no stale --parent rule left
```

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge. `risk_evaluated` gate must pass.

## Risk

### Code-health risk: low
- Docs-only; a bare `task-notes` relref would fail the build — caught by the
  mandatory `hugo build` · severity: low · → mitigation: none

### Goal-achievement risk: low
- Concept pages drift into restating the workflow/command pages (more of the
  rationale is already on the site than the original plan assumed) · severity:
  low (residual — addressed by inline post-phase restatement_triage) ·
  → mitigation: inline post-phase restatement_triage
- Claims drafted from `aidocs/` may not match code (already observed once:
  `--project`/`--parent`) · severity: low · addressed by sourcing each claim
  from code in this plan · → mitigation: none
- A new page asserting a code-true rule that a linked existing page contradicts
  would leave the site self-contradictory, and neither `hugo build` nor
  `check_links.py` can detect it (they check link targets, not claims) ·
  severity: low (residual — the contradicting sentence is corrected in step 4
  and the rule is stated once, on the command-reference side) ·
  → mitigation: none

### Planned mitigations
- timing: post-phase | name: restatement_triage | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: concept pages restating workflow/command pages | desc: Side-by-side re-read against counterparts, cut repeats, run check_link_relevance.py and triage
