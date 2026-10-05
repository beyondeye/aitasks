---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [website, concepts, documentation]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-10-05 14:50
updated_at: 2026-10-05 15:46
---

## Goal

Four website concept pages added by t1687 do not work as concept pages. A reader
who opens one does not learn what the thing is or why they would want it.
Rewrite them so each one explains the **main idea in simple, easy words**,
**why it is useful**, and **how to use it** (its use cases, or how the framework
uses it automatically). Leave the fine details to the reference pages linked
from "See also".

Pages in scope (and **only** these four; the other concept pages that drift are
out of scope by user decision):

- `website/content/docs/concepts/shadow-agent.md` (the worst case)
- `website/content/docs/concepts/implementation-trails.md`
- `website/content/docs/concepts/task-notes.md`
- `website/content/docs/concepts/cross-repo-references.md`

## The concept-page structure (the target)

The 14 original concept pages (April, e.g. `tasks.md`, `plans.md`,
`execution-profiles.md`, `folded-tasks.md`) plus `agentcrews.md` share one
structure, 28–80 lines each, in plain language:

1. `## What it is`: a plain definition a newcomer understands, in the opening
   sentences. No mechanism, no field names unless they are the thing itself.
2. `## Why it exists`: the problem the *feature* solves for the user. Not the
   rationale for an internal design choice.
3. `## How to use`: the use cases and entry points (skill / command / TUI key),
   or how the framework uses it automatically. Short; link out for steps.
4. `## See also`: reference links (workflow, command, skill, TUI pages) where
   the details live.
5. `**Next:**` footer (keep the existing reading chain unchanged).

No `###` deep-dive subsections under "What it is". Aim for the length of the
April pages.

## What is wrong today (exploration findings)

- **The definition is missing or deferred.** `shadow-agent`, `implementation-trails`,
  `task-notes` and `cross-repo-references` each open by sending the reader to
  the workflow page for what the thing *is*, then say "this page covers the
  model underneath". Most of each page is a run of `###` internals subsections.
- **"Why it exists" justifies a mechanism, not the feature.** In
  `shadow-agent.md` it explains why the tmux pane binding exists, not why
  you would want a shadow agent.
- **Root cause:** the t1687_4 plan
  (`aiplans/archived/p1687/p1687_4_concepts_trails_and_shadow_agent.md`) set a
  "strictly complementary" rule ("if a paragraph could be pasted into the
  workflow page… it belongs there, not here"). That rule pushed the plain
  definitions *out* of the concept pages. There is also no written rule for
  concept pages: `aidocs/framework/documentation_conventions.md` says nothing
  about them.

## Where the detailed content goes (user decision: move to the owning pages)

Detail is **relocated to the page that owns that behaviour**, not deleted. Before
cutting anything, check whether the owning page already covers it, and cut to a
link where it does. Mapping found during exploration:

- **Shadow agent:** the plain definition is in the intro of
  `docs/workflows/shadow-agent.md` (an advisory companion launched beside the
  followed agent that reads its terminal output and helps you reason about it,
  read-only). Bring a simple version of it to the concept page. Detail that
  exists **only** on the concept page: the `@aitask_shadow_target` pane-option
  binding, the capture reading that binding rather than a typed pane id,
  capture → context-fetch → skill, and "instructed, not sandboxed". The
  workflow page already has `## Advisory only`, which can absorb the
  "what keeps it advisory" facts. Planning decides whether the binding and
  capture detail gets a short section on the workflow page or is dropped
  (`aidocs/framework/shadow_agent.md` keeps the contributor version).
- **Implementation trails:** "kept, not re-derived" (a decision stored with its
  evidence) is the main idea, so keep it in plain words. Detail that exists
  **only** on the concept page: the owner task carries the `artifacts:` handle,
  no other member file is written, discovery scans active and archived
  frontmatter, an archived owner does not hide a trail, a fold copies the
  handle, one document gives several readings, nothing enforcing reads a
  trail. `workflows/implementation-trails.md` has no section on owners or
  storage. Give this a home there (e.g. a "Where a trail is stored" section),
  or put it in `skills/aitask-trail.md`, which already has a storage
  paragraph.
- **Task notes:** the definition (a block appended to the target task's
  `## Inbox`, durable, travels with the task) is good and should stay, in
  simpler words. Detail that exists **only** on the concept page: the `> | `
  body prefix that stops a note forging an acknowledgement or heading, and the
  failure-direction rules (a malformed ack is skipped, the note is kept and
  the ack discarded on a failed commit, the `rollback-failed` terminal case).
  These belong in `commands/note.md`, which already covers provenance,
  `dirty`, acknowledgement receipts and the `rollback-failed` output.
- **Cross-repo references:** most of the detail is already covered by
  `workflows/multi_project.md` (logical names, per-project identity, `STALE`,
  never auto-cloning) and `workflows/cross_project_dependencies.md`
  (`UNREACHABLE`, fail-closed blocking, `xdeprepo` intent-only, paired
  planning), so cut it to links. Check one point before dropping it: "a
  command that writes elsewhere checks every binding" (compare
  `commands/note.md` "Sending to another repository" and the
  `project-resolution-incomplete` row).

## Inbound references that must be repaired in the same change

- **Anchor that will break:** `docs/workflows/multi_project.md:143` links
  `concepts/cross-repo-references#hierarchies-never-cross-a-repo-boundary`.
  Retarget it to wherever that rule ends up, or keep it as a short plain
  statement on the concept page under a heading with the same slug.
- **Link texts that describe the current mechanism focus** and will become
  wrong once the content moves. Re-read and adjust each one:
  - `docs/tuis/minimonitor/how-to.md:187` and `docs/tuis/monitor/how-to.md:184`:
    "for how it is bound to the followed agent, see the Shadow agent concept page"
  - `docs/workflows/shadow-agent.md:11`: "For how a shadow is bound… see the
    Shadow agent concept page"
  - `docs/commands/note.md:176`: "why verification is recorded only when proven…"
  - `docs/workflows/task-notes.md:103`, `docs/skills/aitask-note.md:63`
  - `docs/skills/aitask-trail.md:92`, `docs/concepts/topic-anchoring.md:137`,
    `docs/tuis/board/reference.md:253`
  - `docs/workflows/cross_project_dependencies.md:124`,
    `docs/workflows/multi_project.md:13`, `docs/development/task-format.md:39`
  - The `docs/concepts/_index.md` bullets for all four pages: their blurbs
    describe the internals focus ("A companion agent bound to the agent it
    follows…", "Why a sequencing recommendation is kept as…"). Rewrite them
    as plain definitions. Also update each page's front-matter `description:`
    to match.
- **Notes to pending tasks:** `t1231_3` and `t1647_6` both have inbox notes that
  point at the trails concept page's "One owner carries the handle" and "Found
  through its owner" sections. If those sections move, send each task a note
  (`/aitask-note`) naming where the content went. Say in the note that the
  move may still be uncommitted.

## Prevent recurrence

Add a short "Concept pages" section to
`aidocs/framework/documentation_conventions.md` that states the structure
above. It should say that the concept page carries the plain definition and
the "why", and that internals belong on the owning workflow / command page.
It should also say that "complementary to the workflow page" never means
moving the definition off the concept page.

## Verification

- `cd website && hugo build --gc --minify` succeeds.
- `cd website && python3 check_links.py --build` is clean. It is mandatory
  after editing `website/content/`, and it catches the broken `#fragment`
  that `hugo build` does not.
- Offer `python3 check_link_relevance.py`, since link targets are retargeted.
- Read each of the four rewritten pages: a newcomer should be able to say what
  the thing is, why they would use it, and how, without leaving the page.
- Every fact removed from a concept page is either present on an owning page
  (name it in the plan) or deliberately dropped with a stated reason.
- Follow the current-state-only rule in `documentation_conventions.md` (no
  "this used to…" prose).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-05T12:46:24Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-05T12:52:20Z status=pass attempt=1 type=human
