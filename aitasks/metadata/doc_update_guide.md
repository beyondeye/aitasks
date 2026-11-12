# Doc-Update Guide — aitasks

Configured doc-update spec for **this** repository. When a code change lands,
use this to decide whether user-facing docs need updating, which files, and
how to write them. This is aitasks's own config, so real paths are used here.

## Doc landscape

Two doc surfaces:

1. **User-facing site** — `website/content/docs/`, a Hugo/Docsy site. Sections:
   - `concepts/` — mental-model / architecture explanations.
   - `workflows/` — task-oriented how-tos (one per workflow).
   - `skills/` — the skills / custom-command reference.
   - `tuis/` — one page per interactive TUI.
   - `commands/` — the `ait` CLI subcommand reference.
   - `installation/` — install, per-agent setup, known issues.
   - `development/` — the framework's public architecture, for users and
     integrators: task and plan file formats, where state lives, library
     scripts meant to be called; also a focused `advanced` reference page for
     a subject whose detail has no other page.
   - `getting-started.md`, `overview.md`, `_index.md` — landing/intro pages.
2. **Design docs** — `aidocs/` (e.g. `aidocs/framework/`, `aidocs/applink/`).
   Internal engineering references for people who change the framework, not
   the user-facing site. Update these when the change alters contributor-only
   detail (see "Reader levels"), but they are **not** the user-facing surface
   the gate primarily targets.

## Reader levels

Each page declares how much its reader already knows. Doc-review tooling reads
the list below to find this guide's level model: keep its labels
(`Level field:`, `Beginner level:`, `Personas:`) and the three level values
exactly as written; the persona sentences may be reworded.

- Level field: `depth`
- Beginner level: `main-concept`
- Personas:
  - `main-concept`: You know git and a terminal and have never heard of aitasks.
  - `intermediate`: You have taken a task from pick to archive and know the board.
  - `advanced`: You maintain a project's aitasks setup, edit its profiles and gates, and read framework scripts.

A page's reader level is its `depth` value. It decides which words and details
the page may use. Every leaf page sets it. A directory's `_index.md` sets it too
when it has content of its own, such as a TUI's overview page; one that is only
a list of links to its pages may leave it out.

Each level allows everything the level before it allows, plus what its entry
adds. Three kinds of detail are kept apart below. Behaviour detail is the exact
rules a user can observe or rely on. Public architecture is how the framework
is put together, as far as a user or an integrator needs it to understand,
configure or extend the framework: the data layout and file formats (which
fields exist and what they mean), where state lives, which component writes
what, the concurrency and atomicity
guarantees a reader of that state relies on, extension points, and the library
scripts and functions an integrator is meant to call. Contributor-only detail is
how the code achieves all of that, which only someone changing the framework
needs: internal loops and counters, how a guarantee is implemented, the exact
encoding of a derived value no integrator computes, private
helpers (every function no integrator is meant to call), code structure,
rejected alternatives and design history, and test strategy. Public architecture
goes to the site's `development/` section, at `advanced`. Contributor-only
detail goes to `aidocs/`, the engineering docs for contributors, and never onto
the site, whatever a page's level. A fact that mixes kinds is split, and each
part goes to its own owner: "the file is replaced atomically, so readers need no
lock" is public architecture; the lock and rename that do it are
contributor-only. Why a feature exists, as its user sees it, stays on its
concept page.

- `main-concept`: the reader is new. The page says what the thing is for before
  any detail. It drops every term the idea does not need and defines the rest at
  first use. It may name the command, skill or keyboard key that starts
  something. It names a field only when that one field is the page's subject.
  It leaves out exit codes, the `KEY:value` status lines scripts print, status
  vocabularies (fixed sets of tokens a script prints), internal file and branch
  paths, edge cases, outcome tables (tables that list each case and its
  result), config keys and timing values.
- `intermediate`: the reader knows the terms the `main-concept` pages define.
  The page adds flags, config keys, files the user edits, timing the user can
  see, and in prose the failure cases a user can run into. It still leaves out
  exit codes, status lines and vocabularies, internal paths and outcome tables.
- `advanced`: the reader wants every behaviour detail: validation, resolution
  order, failure cases, every field and exit status. The page adds exit codes,
  status lines and vocabularies, internal paths and outcome tables.

Example at `intermediate`. Before: "On every refresh cycle it checks the panes in
its own tmux window; the first refresh after the agent pane has gone … triggers
an `exit()` and the minimonitor pane closes. A 5-second grace period after
startup prevents premature exit on cold launch. … a new one will spawn with the
next agent you launch." After: "minimonitor closes itself after it is left alone
in its window, and a new one opens with the next agent you launch." Each cut
fact moves to the page that owns its kind of detail. Behaviour detail goes to
the TUI's reference page: the agent list refreshes every
`tmux.monitor.refresh_seconds` (3 seconds by default); minimonitor closes only
after two refreshes in a row each find it alone in its window; a check that
fails or still sees another pane starts the count again, and repeated failures
never close it; it makes no check in its first 5 seconds, so a slow start
cannot close it. Contributor-only detail (the tmux query, the counter, the
`exit()` call) goes to `aidocs/`. The Before also gets the timing wrong: one refresh is never
enough. State timing only as far as the code guarantees it; this code gives no
deadline.

## Page types

A page's shape depends on what its reader came for. Ask two questions: does the
reader want to do something or understand something, and are they learning
(away from the work) or working (in the middle of it)?

| | Learning | Working |
|---|---|---|
| Do | tutorial | how-to |
| Understand | explanation | reference |

Where a page sits gives its type, so there is no frontmatter field for it. The
first matching row wins:

| Pages | Type |
|---|---|
| a TUI's `_index` / `how-to` / `reference` | overview / how-to / reference |
| any other directory's `_index.md` | overview |
| `concepts/`, `overview.md` | explanation |
| `workflows/`, `installation/` | how-to |
| `commands/`, `skills/`, `development/` | reference |
| `getting-started.md` | tutorial |

An overview is a short explanation that says what a directory or TUI is for and
links to its pages. A page in no listed place takes the type the two questions
give. When a page's content answers the questions differently from where it
sits, reshape the content to the page's type, or move it to a page of the right
type.

How-to and reference pages assume the reader knows what they want, so they never
turn into lessons. A `main-concept` page of any type still defines each term in
a clause at first use; `intermediate` and `advanced` pages link to the page that
defines it, and define it in place only when no page does.

Signs that a how-to has grown into a lesson or a reference page: a walkthrough
that repeats steps the page already listed (write the steps once, as one
numbered procedure, and keep the example inside it), several walkthroughs that
differ only in their example, and a table of config keys, error messages or
symptoms with their fixes. Each table is reference material for the command's
reference page; the how-to keeps the few keys and fixes its steps need and links
to the rest. Two more signs: an opening that argues again for the feature
when its concept page already says why it exists (link to the concept page and
start with the goal), and a table of keys, shortcodes or refresh costs that a
TUI or skill reference page already lists (keep the one or two the steps use).

## How a subject spans levels

Give each page type its own page, and let each page set its own `depth`. The TUI
pages show the pattern: the `_index` overview says what the TUI is for, usually
at `main-concept` or `intermediate`; `how-to` walks through jobs at
`intermediate`; `reference` lists every keyboard key, setting and rule at
`intermediate` or `advanced`. A concept page states the idea and links to the
pages that own the detail.

The page that owns a detail is the page about the detail's subject that allows
its kind: the feature's workflow page for steps, its reference page for
behaviour detail, a `development/` page for public architecture, and `aidocs/`
for contributor-only detail. Every fact survives a cut: move it to its owning
page, or link there if that page already states it. A single behaviour fact
whose feature has no reference page goes on the closest reference page. When a
substantial block of behaviour detail or public architecture has no suitable
page, create a focused `advanced` reference page for it in `development/` and
link it from the pages that lead there. A fact found to be wrong is corrected, or dropped with a
note in the review saying why. Moving a fact is the time to check it against the code: a fact
that sat on a page nobody read closely is often out of date, and copying it
to its owning page would make it look authoritative.

Before calling a script's output, status line or flag contributor-only, check
whether a site page tells readers to run that script and whether its `--help`
documents the output for callers. Either one makes it public architecture: its
contract goes on an `advanced` reference page, and the how-to links there.

Outside `concepts/`, a short page may end with one section headed "Details",
written one level above the rest; the page's `depth` is the level of everything
before that section. Split the page once the details section is longer than the
rest.

## Concept pages

Pages under `concepts/` each explain one idea: what it is, why the reader would
want it, and how to start using it. Most are at `main-concept`; one about
something only experienced users meet may be `intermediate` or `advanced` and
keeps the same sections. Use these headings, in this order:

1. `## What it is`: a plain definition in the opening sentences, with no
   mechanism and no `###` subsections.
2. `## Why it exists`: the problem the feature solves for the user.
3. `## How to use`: use cases and entry points (skill, command, TUI keyboard
   key), or how aitasks uses it on its own. Short; link out for steps.
4. `## See also`: the workflow, command, skill and TUI pages that hold the
   details.
5. A `**Next:**` footer linking to the page that follows it in the list on
   `concepts/_index.md`. The last page in that list has none.

Behaviour detail and the reasons behind internal design choices go to their
owning pages (see "How a subject spans levels"). A concept page may repeat the
plain definition its workflow page opens with; the workflow's steps and
reference details stay on their own pages.

Signs that a concept page has grown into a reference page: `###` subsections,
tables that list cases and their results, headings named after a mechanism
("How the key is stored", "Operation leases"), script paths and status lines.
Each one marks detail to move. Set a concept page's `depth` by who meets the
idea, not by the detail it carries: a page tagged `advanced` only because of
its mechanism usually drops to `intermediate` or `main-concept` once that
mechanism has moved to its owning page.

`tasks.md`, `plans.md`, `folded-tasks.md` and `execution-profiles.md` (about
30–40 lines each) show the section order and length. Copy their structure only.
`tasks.md`, for example, breaks two `main-concept` rules: it lists eight
frontmatter field names on a page about tasks, and it never explains "YAML
frontmatter".

## Prose rules

Apply these to every page at every level. The patterns to avoid after them are
taken from our own pages.

- Don't assume the reader knows what you know. Choose the page's `depth` and type before drafting, make sure each term the reader may not know is defined or linked where it first appears (which one depends on the page's level; see "Page types"), say what a thing is for before how it works, and open a section longer than a few paragraphs with one sentence about its subject (never "This section covers…") in words its heading does not already use.
- Be concrete. Name the actual items instead of writing "factors", "aspects" or "considerations". Don't repeat a table's values in the prose around it. Keep figures such as sizes, timings and limits out of a page's opening paragraph.
- Use plain words first. Pick the everyday word when it says the same thing. Keep a technical term when it is the name of the thing, and define or link it as the page's level requires.
- Use one term per thing. Once something is the "task lock", don't call it a "claim" or a "reservation" later for variety.

Example at `main-concept`. Before: "aitasks uses two locks, and they exclude
different things. The task lock answers "who owns this task ID". The merge mutex
answers a narrower question — which task may run its end-of-task merge right
now — because that merge … runs in the shared repository root." After: "When an
agent starts work on a task, aitasks takes a task lock on it, so no other
agent can take the same task. A second lock, the merge mutex, lets only one
finished task at a time merge its changes back through aitasks, because those
merges all run in the same main copy of the repository." The task ID and the
name "end-of-task merge" are terms the idea does not need, so the After drops
them.

Avoid these patterns. Each "before" is quoted from our pages unless marked
constructed. Each "after" drops only the rhetoric: it keeps the before's facts,
replaces a vague claim with the concrete fact behind it, and adds only facts the
same page states nearby.

- Staged contrast ("not X but Y", "X is about A; Y is about B"). Before: "Parking is a signal to *you*: the agent keeps working and the monitors stop showing it. Freezing is a decision about the *agent*: you are done with it as a process, and you want its results readable." After: "Parking hides an agent from the monitors while it keeps working. Freezing ends the agent's process and keeps its output readable."
- A closing line that restates the point. Before: "The mutex serializes the merges that take it; it does not police the repository." After: cut it; the note it ends already says which merges take the mutex and that merges you run by hand are not held back.
- A run-up that announces a point before making it. Before: "Two ways back, and the obvious one is usually not the cheaper one:" After: "There are two ways to bring a frozen agent back. Re-picking the task usually costs less than restoring it:"
- A saying that sounds deep. Before: "What you trade a code agent for is that viewer: a small terminal app that reads a file." After: "In the agent's place runs the viewer, a small terminal app that reads the saved output from a file."
- Arguing with no one. Before: "Running several agent panes against one checkout under a single email is a normal way to use aitasks, so "same user" is not treated as "same worker"." After: "Each lock belongs to one agent session, so several agents in one checkout under the same email still exclude each other."
- A forced list of three (constructed). Before: "Profiles make runs faster, simpler and more predictable." After: "A profile answers the workflow's routine questions for you, so a run stops less often."
- Repeated openings. Before: "The process behind that screen is still running, still holding its context, still costing you memory and a share of the machine." After: "The process behind that screen keeps running and holds its context, memory and a share of the machine."
- An em dash (—) as the default connector. Before: "Ten or twenty panes, each holding a code agent that has finished its task — and what you actually want from most of them is the last screen". After: "You may have ten or twenty panes, each with an agent that has finished its task. From most of them, what you actually want is the last screen". Keep the em dash for a real aside.
- Inflated importance. Before: "This is particularly powerful for parent tasks with children, where you can revert entire feature slices." After: "On a parent task, a partial revert can undo whole child tasks and keep the others."
- A trailing "-ing" clause that adds a vague effect. Before: "The wrapper sets the `AITASK_AGENT_STRING` environment variable with the correct agent string, ensuring accurate `implemented_with` metadata." After: "The wrapper sets the `AITASK_AGENT_STRING` environment variable to the correct agent string, so the task's `implemented_with` field records the right one."
- Dodging "is", "are" and "has". Before: "The subdirectory name serves as a strong hint for the `environment` field value." After: "The subdirectory name is a strong hint for the `environment` field."
- Bold for emphasis in running text. Before: "The lock excludes **sessions**, not just people." After: "The lock tells agent sessions apart, so two sessions of the same person exclude each other." Keep bold for a term where it is defined and for keyboard keys and on-screen labels.
- A first sentence that repeats the heading. Before: the heading "When the checks run" followed by "The checks run in the background, alongside the trail's freshness check: …" After: "Opening a trail starts them, as do `d` and, in the board, a sync or entering the By-Trail view; they run in the background alongside the trail's freshness check."
- Writing about the page instead of the subject. Before: "This page tracks current workflow issues by code agent. Issues are grouped by agent below." After: cut it; the page title and the per-agent headings already say this.
- A closing summary (constructed). Before: "In short, freezing saves resources while keeping results available." After: cut it; end on the last new fact.

## Sources and credits

These rules adapt published work. Keep the credits when you edit them.

- Page types and their two questions come from Diátaxis by Daniele Procida (https://diataxis.fr/), written here in our own words.
- The main prose rules and parts of the avoid list are adapted and reworded from yzhao062/agent-style (https://github.com/yzhao062/agent-style), whose rules are licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/): RULE-01 (tacit knowledge), RULE-03 (concrete language), RULE-06 (jargon), RULE-07 (X-not-Y), RULE-B (dashes), RULE-E (closing summaries) and RULE-F (one term per thing).
- The avoid list also draws ideas from blader/humanizer (https://github.com/blader/humanizer, MIT), and "every fact survives" from the plain-language skills mdskills `plain-language` and shihyuho/skills `plain`. No text was copied from them.
- keithpatton/diataxis-agent-skill is licensed CC BY-SA 4.0. Its compass and anti-pattern list informed these rules, and none of its text appears here. Never paste its text into this guide: its share-alike terms would then cover the guide.
- Doc review's fresh-reader test (a reviewer who has read only the page answers questions a real reader would ask) follows the reader-testing method of anthropics/skills `doc-coauthoring` (method only).

## Change-kind → doc-area map

| Code change | Doc to update |
|---|---|
| TUI change (`.aitask-scripts/…` — board, monitor, minimonitor, codebrowser, settings, brainstorm) | matching `website/content/docs/tuis/<name>.md` (or its dir) |
| Skill / custom-command change (`.claude/skills/…`, ported `.agents/`, `.opencode/`) | `website/content/docs/skills/` |
| `ait` subcommand added/changed (`.aitask-scripts/aitask_*.sh` behavior, new flags) | `website/content/docs/commands/` |
| Workflow behavior change (task/plan/gate/review flow) | matching `website/content/docs/workflows/<name>.md` |
| Concept / architecture change | matching `website/content/docs/concepts/<name>.md` |
| New frontmatter field / install-flow / framework internal | relevant `aidocs/framework/…` design doc |
| NEW `website/content/docs/workflows/*.md` page | the page **plus** a hand-curated bullet in `website/content/docs/workflows/_index.md` |

### Known footgun: the workflows `_index.md` body list

The sidebar/navigation auto-builds from the files, but the **body** of
`website/content/docs/workflows/_index.md` is a hand-curated grouped list
(Tasks / Parallel / Review & Quality / Git). Adding a new workflows page
requires **manually** adding its bullet to the correct group in that index
body. This is easy to miss because the sidebar looks complete without it.

## Writing conventions (distilled from `aidocs/framework/`)

Sourced from `aidocs/framework/documentation_conventions.md` and
`adding_a_new_codeagent.md` §23b. Apply all of these:

- **Current-state-only.** User-facing docs describe the current state. No
  "previously…", "this used to be…", "this corrects an earlier…". State correct
  behavior positively; version history lives in git and PR descriptions, not in
  doc bodies. (Internal `aiplans/` files may record deviations; user-facing docs
  may not.)
- **"Delete X, integrate into Y" = redirect cross-refs now.** Read Y first. If Y
  already covers the content, "integrate" collapses to updating cross-references
  from X to Y; defer wholesale prose migration as a follow-up and call out the
  redirects explicitly (they break silently).
- **"Autonomous", not "auto-execution".** In manual-verification prose (the
  whole-checklist offer, the per-item `auto` verb, the `manual_verification_mode`
  knob), use "autonomous" — an AI agent runs the mechanically-checkable items and
  leaves human-only checks (visual rendering, UX) for the interactive loop. Keep
  literal code/config tokens verbatim (`auto`, `autonomous`,
  `autonomous_with_plan`, `…_manual_verification_auto.md`, `## Execution Log`).
  Canonical heading: `## Autonomous verification`.
- **Genericize the supported-agent set in blurb prose.** In marketing / intro /
  in-paragraph examples, do NOT enumerate all agents — write "Claude Code and all
  other supported coding agents" (or, when an anchor carries weight, "Claude Code,
  Codex, and all other supported coding agents"). Keep literal enumerations ONLY
  where the list IS the documentation: the CLI mapping table in
  `commands/codeagent.md`, per-agent install blocks in `installation/`, per-agent
  known-issue sections, and model-self-detection lists.
- **Generic example project names.** User-facing docs use invented placeholder
  names (frontend / backend / the docs site), never the author's real repos
  (never "aitasks" / "aitasks_mobile" in examples), and never the framework's
  own scripts or modules as the reader's code (a walkthrough that "fixes a bug
  in `aitask_ls.sh`").
- **Never say "sister" repo.** Use "cross-repo" or "linked repo/project", and
  scrub any existing "sister" wording on pages you touch.

## TUI list caveat: diffviewer is transitional

The `diffviewer` TUI is transitional (to be folded into `brainstorm`). Omit it
from user-facing TUI lists and `docs/tuis/`. Document these TUIs: **board,
monitor, minimonitor, codebrowser, settings, brainstorm**. (`diffviewer` stays
switchable in the framework code but is not documented on the site.)

## Terminal outcomes

- **PASS** — doc work performed, or docs inspected and already correct.
- **SKIP** — evaluated; no doc-relevant user-facing surface needed review/update
  (e.g. a pure refactor, test, or internal-only change).
- **FAIL** — docs needed updating but the user rejected the proposed update.
