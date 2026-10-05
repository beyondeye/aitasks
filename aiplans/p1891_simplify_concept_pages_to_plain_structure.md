---
Task: t1891_simplify_concept_pages_to_plain_structure.md
Base branch: main
Output branch: main
---

# t1891 — Simplify four concept pages to the plain concept-page structure

## Context

t1687 added four website concept pages (`shadow-agent`, `implementation-trails`,
`task-notes`, `cross-repo-references`) that do not work as concept pages. Each one
sends the reader to the workflow page for what the thing *is*, then spends the rest
of the page on a run of `###` internals. A newcomer finishes the page without learning
what the feature is or why they would want it. The cause was the t1687_4 "strictly
complementary" rule, which pushed the plain definitions off the concept pages, and
the fact that no written rule for concept pages exists.

The intended outcome: each page follows the April structure (What it is / Why it
exists / How to use / See also / Next), in plain words, 28–80 lines, with no `###`
subsections. Detail is **relocated** to the page that owns the behaviour, or cut to a
link where that page already has it (user decision). A "Concept pages" rule in
`aidocs/framework/documentation_conventions.md` prevents a repeat.

Mode: current branch (`fast` profile), no worktree.

## Decisions taken during planning

- **Shadow binding / capture internals are dropped from the website.** The pane
  option `@aitask_shadow_target`, stamp-or-kill, the capture reading the binding,
  and the same-server check are contributor mechanism. They are already in
  `aidocs/framework/shadow_agent.md` (pipeline §L27, binding §L215–223, capture
  §L236–254, cleanup §L291). The user-visible effects (never listed as an agent,
  closes with its agent, one per agent) are already on `workflows/shadow-agent.md:24`.
  The "instructed, not sandboxed" fact is **not** in aidocs and is user-relevant, so
  it moves to the workflow page's `## Advisory only`.
- **Trails storage gets a new `## Where a Trail Is Stored` section** on
  `workflows/implementation-trails.md` (it has no storage section today). The skill
  page's `## Storage` paragraph links to it.
- **Task-notes internals go to `commands/note.md`**, which already covers provenance,
  receipts and `rollback-failed`. New there: a short `### How the inbox is stored`
  section (the `> | ` prefix, the reserved `read` name, malformed receipts skipped).
- **Cross-repo detail is cut to links.** `multi_project.md`,
  `cross_project_dependencies.md` and `commands/note.md` already cover nearly all
  of it. Two gaps get filled: "never auto-clones" (new paragraph on `multi_project.md`)
  and write-time refusal of a stale `xdeprepo` (one sentence on
  `cross_project_dependencies.md`). Verified in source: `validate_xdeps_pair`
  (`lib/task_utils.sh:2032–2068`, shared by create and update) refuses STALE and
  NOT_FOUND. The only clone path is the opt-in `ait projects doctor --clone`
  (`aitask_projects.sh:578–626`).
- **Two small adjacent fixes in `multi_project.md`, made because those lines are
  being edited anyway:** line 29's `git_remote` cell says "reserved for future
  auto-clone". That is stale, since `doctor --clone` already uses it, and it
  contradicts the relocated "never auto-clones" fact. Line 13's "used to hardcode"
  is version history, which the current-state-only rule forbids.
- The `**Next:**` reading chain, titles, `linkTitle`, `weight` and `depth` stay
  unchanged. Only `description:` changes.

## Implementation steps

### 1. Concept-page rule — `aidocs/framework/documentation_conventions.md`

Insert a new `## Concept pages` section after "Current-state-only…":

```markdown
## Concept pages (`website/content/docs/concepts/`)

A concept page answers three questions for a newcomer, in plain words: what the
thing is, why they would want it, and how to use it. The details live on the
pages it links to. Model: `tasks.md`, `plans.md`, `folded-tasks.md`,
`execution-profiles.md` (28–80 lines each).

Sections, in this order:

1. `## What it is` — a plain definition in the opening sentences. No mechanism,
   and no field names unless the field is the thing itself.
2. `## Why it exists` — the problem the **feature** solves for the user, not the
   rationale for an internal design choice.
3. `## How to use` — use cases and entry points (skill, command, TUI key), or how
   the framework uses it automatically. Short; link out for steps.
4. `## See also` — the workflow, command, skill and TUI pages where details live.
5. `**Next:**` footer — keep the reading chain intact.

No `###` deep-dive subsections under "What it is".

Keep the page on what the feature is, why it is useful and how to use it. Leave
exact validation, resolution and failure rules to the reference pages; a
concept page states the idea, not the rules that enforce it.

**Internals belong on the page that owns the behaviour**: the workflow, command
or skill page, or `aidocs/` for contributor-only mechanism. Before cutting a
fact from a concept page, check whether the owning page already states it. Link
to it if so, and move the fact there if not.

**"Complementary to the workflow page" never means moving the definition off the
concept page.** A concept page may restate the plain definition the workflow
page opens with; that overlap is intended. What it must not repeat is the
workflow's steps and reference detail.
```

### 2. Shadow agent

**2a. Rewrite `website/content/docs/concepts/shadow-agent.md`** (~45 lines). `description:` "A second coding agent you open beside a working agent, to explain what it is doing and help you make its decisions — advice only."

- *What it is*: a second coding agent you open beside the agent you are watching
  (the *followed agent*). It reads what that agent shows on screen, looks up its task
  and plan when needed, and answers your questions in plain words. It is an adviser,
  not a second worker: it explains, suggests and reviews, but never types into the
  followed agent's pane. You still answer every prompt and approve every plan.
- *Why it exists*: an agent at work produces dense output. Its plan may assume
  background you lack, a question may refer to output that has scrolled away, and
  whether the finished code matches the plan is hard to judge while the agent keeps
  going. Stopping the agent to ask interrupts it. A shadow gives you a second
  opinion on the side, without interrupting the agent.
- *How to use*: press **e** on an agent in minimonitor or `ait monitor` (**E** first
  picks agent and model). It greets you and waits for a plain-language request.
  Common uses as a bullet list: explain what the agent is doing; help answer the
  question it is waiting on; explain or challenge a plan before you approve it;
  review the code once implemented; diagnose an error from a skill or helper. Its
  concerns can be picked with **c** and copied to your clipboard, never sent
  directly. It closes when the followed agent exits. Keep the two per-TUI how-to links.
- *See also*: the workflow ("everything a shadow can do, its shortcodes and
  settings, and what keeps it advisory"), Minimonitor, Monitor. The Framework
  session link is dropped: it only supported the removed binding section.

**2b. `website/content/docs/workflows/shadow-agent.md`**
- L11: replace the "For how a shadow is bound…" sentence (and its hand-written
  `../../concepts/shadow-agent/` link) with: "What keeps it that way, and what that
  does and does not guarantee, is under [Advisory only](#advisory-only); for the
  idea in brief, see the [Shadow agent]({{< relref "/docs/concepts/shadow-agent" >}})
  concept page."
- L33 bullet: "**It reads the followed agent's current screen, and can re-read it
  any time.**" → "**It reads a copy of the followed agent's screen, and can re-read
  it any time.** It never joins that agent's session, so what it knows is only as
  current as its last read." The rest of the bullet is unchanged.
- `## Advisory only` (L186): keep the existing paragraph, then append:

```markdown
Two separate facts keep it advisory, and neither should be read as the other:

- **What the framework runs for the shadow only reads.** It reads the followed
  agent's screen, and that agent's task and plan files. Forwarding concerns goes
  through minimonitor or monitor, which copy the concerns you pick to your
  clipboard; you do the pasting. Nothing the framework runs on the shadow's behalf
  types into the followed pane.
- **The shadow is instructed, not sandboxed.** It is an ordinary coding agent with
  its usual tools, and no sandbox makes typing into the followed pane impossible.
  Never doing so is a rule in the shadow's own skill: the contract it is built to
  honour, not an isolation boundary.
```

### 3. Implementation trails

**3a. Rewrite `website/content/docs/concepts/implementation-trails.md`** (~50 lines). `description:` "A saved, versioned recommendation of which tasks should land next, in what order, and why — kept with the evidence behind it."

- *What it is*: a saved recommendation for the order in which a group of tasks
  should land. It splits them into **waves** (groups that land together before the
  next starts) and records why each task sits where it does: a real blocker,
  something cheaper to do first, a task that only shares a file with another, or
  optional related work. The key idea is that a trail is **kept, not worked out
  again**. It stores the recommendation with the evidence it was based on (task
  statuses, work in progress, a failing test suite). A refresh stores a new version
  beside the old one, so each earlier recommendation stays readable against its own
  evidence. It is advice only: it never changes your tasks. (The "nothing that
  enforces reads a trail" rule goes to the workflow's "Never Does" list only.)
- *Why it exists*: working out what should land next among many tasks is expensive.
  Without a trail the answer stays in a terminal session and is lost when the window
  closes. Next time it is worked out again, against different evidence, maybe with a
  different answer and no record of what changed. A trail keeps the answer, the
  reasoning and the evidence together, so you can re-open it later, see whether it
  is stale, and read it on the board.
- *How to use* bullets: **Create** with `/aitask-trail` or **T** on a task in the
  board's kanban or By-Topic view. **Read** in By-Trail (**z**) or `ait trails`.
  **Keep it current**: a `⚠ stale` badge means the evidence moved, so re-author it.
  **Act on it**: move a wave into a board column, then run a work report
  (`{{< relref "/docs/workflows/work-report" >}}`) on it. One sentence: worth it when
  the ordering question is hard, not for a few tasks with obvious dependencies.
- *See also*: unchanged targets. The workflow line becomes "…, and where it is
  stored"; the Topic anchoring line becomes "a task belongs to one topic, but can
  appear in several trails".

**3b. `website/content/docs/workflows/implementation-trails.md`**: insert before
`## What a Trail Never Does` (L129):

```markdown
## Where a Trail Is Stored

A trail is one structured document, stored as a versioned artifact under a
handle that **one task owns**: the handle is an entry in that task's
`artifacts:` frontmatter (see the [field shape]({{< relref "/docs/development/task-format" >}}#nested-fields-artifacts-and-attachments)).
No other task file is written. Which tasks belong to the trail is recorded
inside the document, never as a field on the member tasks, so a task can appear
in any number of trails without its own file changing.

- **Who owns it.** A trail scoped to one task or one topic is owned by that task
  or that topic's root. A trail spanning several topics, or an ad-hoc set of
  tasks, has no natural owner, so `/aitask-trail` asks you to choose one. No
  extra task is created just to hold a trail.
- **How it is found.** Trails are found by scanning task frontmatter, active
  **and archived**. Archiving the owner therefore does not hide a trail: it stays
  listed and readable, and the trail view notes that its owner is archived. That
  note is about the owner, not about freshness. A trail goes stale when the tasks
  it recorded as inputs change, and a chosen owner need not be one of them.
- **When the owner is folded.** Folding the owner copies its `artifacts:` entry
  to the primary task, so the trail keeps an owner. Until the folded task's file
  is deleted when the primary is archived, two task files point at the same
  trail. It is still listed once, preferring an active, unfolded owner.
- **One document, several views.** The By-Trail view, `ait trails` and the
  summary `/aitask-trail` prints are all read from that one document. None of
  them is stored as a second copy that could disagree with it.

To list, fetch or delete stored versions, see
[Storage]({{< relref "/docs/skills/aitask-trail" >}}#storage) on the `/aitask-trail` page.
```

- `## What a Trail Never Does`: add the bullet "Nothing that enforces anything reads
  it: gate checks, dependency checks and archival never consult a trail, so a trail
  can never block or unblock a task."
- L138: "…and [Implementation trails] (concept) for why a trail is stored the way it
  is." → "…and [Where a Trail Is Stored](#where-a-trail-is-stored) for why appearing
  in a trail never changes a task's file."

**3c. `website/content/docs/skills/aitask-trail.md`**
- L85 `## Storage`: "owned by a task" → "owned by a task (see [Where a trail is
  stored]({{< relref "/docs/workflows/implementation-trails" >}}#where-a-trail-is-stored))".
- L92 Related: "— why a trail is a versioned, task-owned artifact" → "— the concept:
  what a trail is and why it is kept".

### 4. Task notes

**4a. Rewrite `website/content/docs/concepts/task-notes.md`** (~45 lines). `description:` "A short message one task leaves on another existing task, so whoever works on that task next learns something it needs."

- *What it is*: a short message left on an existing task for whoever works on it
  next. It is added to a `## Inbox` section in that task's file and committed with it.
  Because it lives inside the task, it survives with no agent running, travels with
  the task data to every machine, and is shown each time the task is picked until
  someone acknowledges it. It carries **context, not work** (a moved line number, a
  wider blast radius, a decision made elsewhere). If the content is work, create a
  task instead. It is **advice, not an order**: one session's claim about a repository
  that may have moved, never acted on automatically.
- *Why it exists*: while working on one task you learn something another task
  needs. Without notes the options are poor: rewrite its description (which changes
  its requirements instead of adding context), create a task (wrong when there is no
  new work), or tell the agent working on it right now (works only if one happens to
  be running at that moment). A note removes that dependence on timing. Use the
  user's wording verbatim: "The note is saved in the task first. It may also reach
  an agent currently working on it." No lock/host/live-lane detail. The old "the case that
  prompted the mailbox was delivered by hand" history is dropped under the
  current-state-only rule.
- *How to use* bullets: **Send** with `/aitask-note` (name the target, or let it
  suggest relevant tasks); the workflow also offers to send one after implementation
  review, during QA, and during code review. **Script** with `ait note` (durable
  write only). **Another repository**: `--project <name>`, linking
  `{{< relref "/docs/workflows/task-notes" >}}#a-task-in-another-repository`.
  **Receive**: shown with its source when you pick the task, then acknowledge or
  keep unread.
- *See also*: Task Notes workflow; `ait note` ("…, what each note records, and how
  the inbox is stored"); `/aitask-note`; Cross-repo references ("how a task in
  another project is named").

**4b. `website/content/docs/commands/note.md`**
- L119 paragraph: append "If removing the receipt fails too, the receipt stays on
  disk, uncommitted, hiding the note on this machine. No automatic step can settle
  that, so it is reported on its own as `READ_ERROR:rollback-failed:`, and stderr
  names the block: remove it from the task file, or commit it." (Matches the message
  at `aitask_note.sh:747–753`.)
- Insert before `### Output` (L121):

```markdown
### How the inbox is stored

Notes and read receipts share one `## Inbox` section in the task file.
Everything in that section is written by the framework except a note's body,
which is free text from another session: the one part an untrusted writer
controls. It is stored so that it cannot pass for anything else:

- **Every body line is stored behind a `> | ` prefix.** A block header is
  recognised only at the start of a line, so no line of a note body can parse as
  one. A note therefore cannot forge a read receipt, for itself or for any other
  note in the file, and cannot open a new section heading that would swallow what
  follows it. The prefix is added when the note is written, so every reader is
  protected without doing anything.
- **Receipts use the reserved name `read`.** A note's header always names its
  sender's task, so no note can take that name.
- **A receipt that does not validate is skipped**, so a malformed receipt can
  never hide a real note. The read-only `inbox` query reports any block that
  failed validation as `INBOX_MALFORMED:`, so it is not silently ignored either.

Change the section only through `ait note`.
```

  Sources: `aitask_note.sh:443` (prefix), `note_inbox.py:50` (reserved name),
  `note_inbox.py:241` (skip), `note_inbox.py:369` (malformed report).
- Output table, `READ_ERROR:rollback-failed` row Meaning: append "stderr names the
  block: remove it, or commit it." Keep the first two cells untouched, because the
  contract test reads them.
- L176: delete the second sentence ("For why the fields are shaped this way… see
  Task notes"). The table directly below now says it.
- Provenance table, `from_verified=yes` row: after "never written as `no`", add
  "(the proof also fails for innocent reasons, such as a sending session that holds
  no task)", which carries over the concept page's "innocent reasons" point.

**4c. Link texts**: `workflows/task-notes.md:103` → "— what a note is and why it
exists, in brief". `skills/aitask-note.md:63` → "— the concept: what a note is and
why you would send one".

### 5. Cross-repo references

**5a. Rewrite `website/content/docs/concepts/cross-repo-references.md`** (~50 lines). `description:` "Pointing at a task or file in another aitasks project by the project's name, which each machine maps to its own copy of that project."

- *What it is*: points at a task or file in another aitasks project by the
  project's **name**, not its location. Show a `text` block with `backend#42` /
  `backend:src/protocol.rs` and comments. Each machine keeps its own list mapping a
  name to where that project is checked out there, and the name is looked up only
  when the reference is used. So one reference works on your machine, a teammate's
  and in a cloud agent. The project name is part of a task's identity: every project
  has its own task 42. (The parent/child-stays-in-one-project rule, write-time
  refusals, `UNREACHABLE`, binding checks and the no-auto-clone rule are **not**
  stated here; they live on the reference pages per the user's direction.)
- *Why it exists*: a path like `../backend/` records one machine's folder layout in
  a file every machine shares. It breaks as soon as the project is somewhere else,
  and a broken path looks like a reference that was always wrong. A name that does
  not resolve is a clear problem you can fix: register the project on this machine.
- *How to use* bullets: **Register** with `ait projects add` and check with
  `ait projects list`. **Write** `backend#42` / `backend:path` in tasks, plans and
  commits. **Work there from here**: `ait create --batch --project backend`,
  `ait ls --project backend`, or send a note (link to
  `workflows/task-notes#a-task-in-another-repository`). **Wait for its work**:
  `xdeprepo` + `xdeps`, linking Cross-Project Dependencies, which also covers
  planning a change across two repos (stated as a use case, without the rule).
- *See also*: same five targets. The Task notes line becomes "sending context to a
  task in another project".

**5b. `website/content/docs/workflows/multi_project.md`**
- L13: "Cross-repo coordination used to hardcode sibling paths like `../backend/`.
  That breaks…" → "Hardcoding a sibling path like `../backend/` breaks the moment
  the on-disk layout differs — … A per-user registry maps a logical name (`backend`)
  to a path instead, and every cross-repo command resolves the name at call time
  rather than trusting a recorded path. For the idea in brief, see [Cross-repo
  references]."
- L29 `git_remote` Notes: "Canonical clone URL. Shown in listings, and used by
  `ait projects doctor --clone` to re-clone a stale project."
- After the state table (after L86), add: "A name that does not resolve is
  reported, never repaired for you. A command that needs it stops and prints how to
  register the project (`cd /path/to/backend && ait projects add`). Nothing clones a
  repository to make a reference resolve: you named the project, and only you know
  which checkout it means. Cloning happens only when you ask for it, with
  `ait projects doctor --clone`."
- L143: replace the `#hierarchies-never-cross-a-repo-boundary` link with: "A task
  can never be made a child of a parent in a *different* project: a parent and its
  children always live in one project, and a change that spans two repos is [two
  parents, one per repo]({{< relref "/docs/workflows/cross_project_dependencies" >}}#planning-paired-work-across-two-repos)."

**5c. `website/content/docs/workflows/cross_project_dependencies.md`**
- L22: "It must resolve through the registry." → "It must resolve through the
  registry when the task is created or updated: an unregistered name, or one whose
  registered path is stale, is refused rather than recorded."
- L37: after "…marked `UNREACHABLE`", add the reason before the code block: "not
  knowing whether the other project's work is done is treated as not done, so you
  never start on a prerequisite that may still be open".
- L124 See also: "— the concept: what a cross-repo reference is, and why it names a
  project instead of a path."

**5d. `website/content/docs/development/task-format.md:39`**: "for the identity
model" → "for what a cross-repo reference is".

### 6. Remaining inbound link texts

- `tuis/minimonitor/how-to.md:187`, `tuis/monitor/how-to.md:184`: "for how it is
  bound to the followed agent, see the Shadow agent concept page" → "for what a
  shadow is and why you would use one, see the Shadow agent concept page".
- `tuis/minimonitor/_index.md:79`: not in the task's list, but found by grep. "for
  how the shadow is bound to the agent it follows" → "for what a shadow is and why
  you would use one".
- `concepts/topic-anchoring.md:137`: "- why a trail is kept as a versioned,
  task-owned artifact" → "- what a trail is and why it is kept".
- `tuis/board/reference.md:253`: "(why it is stored that way: [Implementation
  trails])" → "(the idea in brief: [Implementation trails])".

### 7. `website/content/docs/concepts/_index.md` bullets (plain definitions, matching each new `description:`)

- Task notes: "A short message left on an existing task, so whoever works on it next learns something it needs."
- Shadow agent: "A second coding agent beside a working agent that explains what it is doing and helps you decide — advice only."
- Implementation trails: "A saved, versioned recommendation of which tasks should land next, in what order, and why."
- Cross-repo references: "Pointing at a task or file in another project by the project's name, which each machine maps to its own checkout."

### 8. Notes to pending tasks (via `/aitask-note`, `--from 1891`)

- **t1231_3**: its t1687 inbox note asks to link `concepts/artifacts.md` from the
  trails concept page's "One owner carries the handle" section. That section has
  moved, with its `task-format#nested-fields-artifacts-and-attachments` link, to
  `workflows/implementation-trails.md` § "Where a Trail Is Stored"
  (`#where-a-trail-is-stored`), now the natural home for an artifacts link. The
  concept page's See also still exists. Hedge: the move may still be uncommitted.
- **t1647_6**: its inbox points at the "Found through its owner" section (fold
  copies the handle, discovery lists one handle once). That text moved to the same
  workflow section, in the "When the owner is folded" bullet. A merge line belongs
  there, not on the concept page. Same hedge.

Send these at the end of implementation, before the Step 8 review.

### Post-phase (risk mitigations)

1. [newcomer_readthrough] For each of the four rewritten concept pages, spawn a
   fresh subagent that receives **only that page's markdown text** (no repo access
   instructions, no other pages) and ask it to state, in its own words: (a) what the
   thing is, (b) why someone would want it, (c) how they would use it, and (d) any
   sentence it could not understand without another page. Compare (a)–(c) with the
   intended definition in this plan. Revise any page whose answer is wrong or whose
   (d) list names a term the page should have explained, then re-run steps 1–2 of
   Verification. Record the four answers briefly in the plan's Final Implementation
   Notes.

## Fact disposition (every fact removed from a concept page)

| Page | Fact | Lands on |
|---|---|---|
| shadow | binding is pane option `@aitask_shadow_target`, its three jobs, recycled-id safety | dropped from website (contributor mechanism); `aidocs/framework/shadow_agent.md` binding section; user-visible effects already at workflow L24 |
| shadow | stamp failure kills the new pane | dropped; aidocs L220–223 |
| shadow | capture reads binding, same-server check, waits for stamp | dropped; aidocs L236–254 |
| shadow | capture → context-fetch → skill; not attached; only as current as last capture | workflow L33 bullet (edited); aidocs L27 |
| shadow | framework path read-only; forward via picker → clipboard | workflow `## Advisory only` (new) |
| shadow | instructed, not sandboxed | workflow `## Advisory only` (new) |
| shadow | "Why": binding rationale | dropped (internal design rationale) |
| trails | kept not re-derived; new version beside old | concept (plain) + workflow L109 |
| trails | owner carries `artifacts:` handle; no other file; field-shape link; membership inside the document | workflow "Where a Trail Is Stored" (new) |
| trails | default owner for task/topic scope; chosen owner otherwise; no container task | new section |
| trails | discovery scans active + archived; archived owner noted; freshness ≠ owner | new section |
| trails | fold copies handle; listed once | new section |
| trails | one document, several readings | new section |
| trails | nothing enforcing reads a trail | workflow "Never Does" (new bullet) |
| trails | "Why": not a field on every member | new section (no-file-change sentence) |
| trails | "Why": not markdown+parser / two stored forms | dropped (internal format rationale); "no second copy" kept |
| trails | "Why": not ownerless | new section ("asks you to choose") |
| notes | Inbox block, durable, travels | concept (plain) |
| notes | `from_verified` yes-or-absent, innocent failures | note.md Provenance row (enriched) + workflow L73 |
| notes | proves identity only, not content | note.md L181 (existing) |
| notes | commit dates tree, not moment; `dirty` | note.md L197 + workflow L98 (existing) |
| notes | migrated empty `dirty` = never measured | note.md L211 (existing) |
| notes | cross-repo qualified sender, same verification, recipient-tree provenance | note.md L70, L183, L193 (existing) |
| notes | `> | ` body prefix, applied at write | note.md "How the inbox is stored" (new) |
| notes | reserved `read` name | new section |
| notes | malformed receipt skipped | new section |
| notes | unread is derived | note.md L109 (existing) |
| notes | `--by` = target task | note.md L104 (existing) |
| notes | failed commit: note kept, receipt discarded | note.md L119 (existing) |
| notes | rollback-failed needs a person: remove or commit | note.md L119 + Output row (enriched) |
| notes | seeing ≠ acknowledging; list shows count only; unattended ack recorded | workflow L76, L91, L93; note.md L96, L106 (existing) |
| notes | "Why": hand-delivery origin story | dropped (version history); problem restated plainly |
| xrepo | identity = pair; registry per-user, resolved at use | concept (plain) + multi_project L13, L36–86 |
| xrepo | valid reference may not resolve here | multi_project state table (existing) |
| xrepo | write-time refusal | cross_project_dependencies L22 (strengthened), L33, L98 |
| xrepo | read-time fail-closed `UNREACHABLE` | cross_project_dependencies L35–43 (+ reason sentence) |
| xrepo | `xdeprepo` alone = intent | cross_project_dependencies L33 (existing) |
| xrepo | hierarchies never cross a repo | cross_project_dependencies L111 (existing); multi_project L143 retargeted |
| xrepo | a writer checks every binding | note.md L68, L79; multi_project L155–158 (existing) |
| xrepo | never auto-clones | multi_project new paragraph; L29 fixed |
| xrepo | "Why": late resolution changes what a failure is | concept "Why" (plain) |

## Verification

1. `cd website && hugo build --gc --minify` succeeds.
2. `cd website && python3 check_links.py --build` is clean (mandatory; catches the
   retargeted `#planning-paired-work-across-two-repos`, the new
   `#where-a-trail-is-stored` and `#a-task-in-another-repository`).
3. `grep -rn 'hierarchies-never-cross-a-repo-boundary' website/content` → no hits.
4. `grep -n '^###' website/content/docs/concepts/{shadow-agent,implementation-trails,task-notes,cross-repo-references}.md`
   → no hits; `wc -l` on the four → each within ~28–80.
5. `bash tests/test_note_doc_contract.sh` passes (note.md Output tables).
6. `python3 -m pytest tests/test_shadow_disposition_surfaces.py -q` (or unittest)
   passes (shadow workflow headings).
7. Offer `cd website && python3 check_link_relevance.py` (report only), since links
   were retargeted.
8. Re-read each rewritten page: a newcomer can say what, why and how without leaving
   it. No "used to" / history prose on any edited line.
9. Walk the fact-disposition table: each "existing"/"new" destination contains the fact.

## Step 9 reference

Post-implementation follows task-workflow Step 8 (review, commit
`documentation: … (t1891)` naming only the changed paths), then Step 9: no branch to
merge (current-branch mode), gate orchestrator, `aitask_archive.sh 1891`.

## Risk

### Code-health risk: low
- A rewritten or retargeted link could point at a dead `#fragment` (`hugo build` does not catch it) · severity: low · → mitigation: none (check_links.py --build is a mandatory verification step)
- Doc-contract tests pin `note.md` Output tables and `shadow-agent.md` headings · severity: low · → mitigation: none (both tests run in Verification)

### Goal-achievement risk: low
- "Plain and newcomer-readable" is a judgement: the rewrites may still read as too technical, or leave out something a reader needs to understand the idea · severity: low (residual — addressed by inline post-phase newcomer_readthrough) · → mitigation: inline post-phase newcomer_readthrough
- A fact removed from a concept page could land nowhere · severity: low · → mitigation: none (fact-disposition table + Verification step 9)

### Planned mitigations
- timing: post-phase | name: newcomer_readthrough | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — rewritten pages may not read plainly to a newcomer | desc: Fresh-context subagent reads each rewritten concept page alone and restates what/why/how; revise pages that fail
