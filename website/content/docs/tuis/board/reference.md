---
title: "Feature Reference"
linkTitle: "Reference"
weight: 20
description: "Keyboard shortcuts, configuration, and technical details"
maturity: [stable]
depth: [advanced]
---

### Keyboard Shortcuts

#### Board Navigation

| Key | Action | Context |
|-----|--------|---------|
| `q` | Quit the application | Global |
| `Tab` | Toggle focus between search box and board | Global |
| `Escape` | Return to board from search / dismiss modal | Global |
| `Up` | Navigate to previous task in column | Board |
| `Down` | Navigate to next task in column | Board |
| `Left` | Navigate to previous column | Board |
| `Right` | Navigate to next column | Board |
| `Enter` | Open task detail dialog | Board (focused card) |
| `r` | Refresh board from disk | Board |
| `s` | Sync task data with remote | Board |
| `O` | Open board options/settings dialog | Board |
| `a` | Switch base filter to All (show all tasks) | Board |
| `l` | Switch base filter to Locked (busy tasks + context) | Board |
| `f` | Switch base filter to Free (tasks ready to pick) | Board |
| `i` | Switch base filter to In-Flight (action-grouped active work) | Board |
| `y` | Switch base filter to By-Topic (per-anchor swimlanes) | Board |
| `z` | Switch base filter to By-Trail (implementation-trail waves) | Board |
| `o` | Choose the By-Topic lane sort order (opens a picker) | By-Topic view |
| `s` | Choose which trail the view shows — re-scans, so a trail created since the board started is listed | By-Trail view |
| `r` | Re-read task files from disk and redraw the trail | By-Trail view |
| `d` | Re-check the trail's freshness against live task state | By-Trail view (trail selected) |
| `R` | Launch an agent to re-author the trail | By-Trail view (trail selected) |
| `S` | Sync task data with remote, then redraw the trail | By-Trail view |
| `v` | Open the trail's summary in a scrollable dialog | By-Trail view (trail has a summary) |
| `g` | Toggle Git add-on (intersect with git-linked tasks) | Board |
| `t` | Toggle Type add-on (intersect with selected issue types — opens picker dialog) | Board |

#### Task Operations

| Key | Action | Context |
|-----|--------|---------|
| `Shift+Right` | Move task to next column (skips collapsed) | Board (parent cards only) |
| `Shift+Left` | Move task to previous column (skips collapsed) | Board (parent cards only) |
| `Shift+Up` | Swap task with one above | Board (parent cards only) |
| `Shift+Down` | Swap task with one below | Board (parent cards only) |
| `Ctrl+Up` | Move task to top of column | Board (parent cards only) |
| `Ctrl+Down` | Move task to bottom of column | Board (parent cards only) |
| `m` | Move the marked task(s) — or the focused card — to a column | Board (parent cards only; hidden in In-Flight and By-Topic views) |
| `m` | Move the focused entry's task to a column | By-Trail view (focused card; not a child, not a ghost) |
| `M` | Move the focused wave's tasks to a column, in wave order | By-Trail view (focused live card) |
| `n` | Create a new task | Board |
| `x` | Toggle expand/collapse child tasks | Board (parent or child card) |
| `x` | Expand / collapse the focused task group | Board (focused group header) |
| `Space` | Mark / unmark the focused task (`✓` / `□`) | Board (parent cards only; hidden in In-Flight, By-Topic and By-Trail views) |
| `c` | Commit focused modified task | Board (shown when task is modified) |
| `C` | Commit all modified tasks | Board (shown when any task is modified; hidden in By-Trail view) |
| `p` | Pick the focused task (start implementation) | Board (context-dependent — shown when task is pickable) |
| `T` | Create an implementation trail from the focused task | Board (hidden in In-Flight and By-Trail views) |
| `w` | Draft a work report from selected columns | Board (context-dependent — column-scoped; hidden in In-Flight, By-Topic and By-Trail views) |
| `b` | Launch brainstorm for the focused task | Board (context-dependent — shown when task is brainstormable) |
| `g` | Resume the focused In-Flight task directly | In-Flight row — [refused on a Planned task](#in-flight-lanes-and-workflow-phases) |
| `s` | Sign off a pending human gate | In-Flight row with pending human gate — [refused on a Planned task](#in-flight-lanes-and-workflow-phases) |
| `f` | Fail a pending human gate | In-Flight row with pending human gate — [refused on a Planned task](#in-flight-lanes-and-workflow-phases) |

#### Column Operations

| Key | Action | Context |
|-----|--------|---------|
| `e` | Open the column management dialog (add, edit, delete, reorder, merge) | Board (not In-Flight / By-Topic / By-Trail) |
| `Shift+Up` | Move the focused column one position up (left on the board) | Column management dialog |
| `Shift+Down` | Move the focused column one position down (right on the board) | Column management dialog |
| `Enter` | Edit the focused column | Column management dialog |
| `Ctrl+Right` | Move column one position right | Board |
| `Ctrl+Left` | Move column one position left | Board |
| `X` (Shift+X) | Toggle collapse/expand for focused card's column | Board (focused card) |
| `Ctrl+Backslash` | Open command palette | Global |
| Click `▼` / `▶` | Toggle column collapse/expand | Column header |
| Click `✎` | Open column edit dialog | Column header |

#### Modal Navigation

| Key | Action | Context |
|-----|--------|---------|
| `Up` | Focus previous field | Inside modal dialogs |
| `Down` | Focus next field | Inside modal dialogs |
| `Left` | Cycle to previous option | On CycleField |
| `Right` | Cycle to next option | On CycleField |
| `Enter` | Activate focused button / navigate to linked task | Inside modal dialogs |
| `Escape` | Close the dialog | Inside modal dialogs |

### Task Card Anatomy

```
┌─────────────────────────────────┐  ← Border color = priority
│ ▲ □ t47 *  playlists support    │  ← Follow-up glyph (only on follow-up tasks), mark (✓ marked / □ unmarked), task number (cyan), * if modified (orange), title (bold)
│ 💪 medium | 🏷️ ui,api | GH | PR:GH | @alice │  ← Effort, labels, issue/PR indicator, contributor
│ 🔒 alice@example.com            │  ← Lock indicator (if locked)
│ 🚫 blocked | 👤 alice           │  ← Status/blocked, assigned to
│ 📋 Ready · Planned              │  ← Status, with `· Planned` when an approved plan awaits implementation
│ 🔗 t12, t15                     │  ← Blocking dependency links
│ 📎 folded into t42              │  ← Folded indicator (if applicable)
│ 👶 3 children                   │  ← Child task count (if parent)
└─────────────────────────────────┘
```

Not all lines are shown on every card — lines only appear when the corresponding data exists.

**The `· Planned` qualifier** marks a task whose plan was approved and whose implementation was
deliberately deferred (the "Approve and stop here" checkpoint), so it reads differently from a task
nobody has looked at yet. The card carries no timestamp — a card is a narrow surface — and the
approval time appears in the task detail dialog as `Plan approved: <YYYY-MM-DD HH:MM>` under
**Tracking & provenance**. Such a task also gets its own [In-Flight lane](#in-flight-lanes-and-workflow-phases).

### Group Header Anatomy

Tasks that share a `boardgroup` slug are drawn under a group header row inside their column:

```
▾ perf work (3) · 2 match · ▲2 ◈1
│ │          │        │       └─ Follow-up roll-up: a per-kind tally of the members' glyphs
│ │          │        └────────- Match count — only during a filter pass
│ │          └─────────────────- Member count
│ └────────────────────────────- Group title, humanized from the slug (perf_work → perf work)
└──────────────────────────────- ▾ expanded / ▸ collapsed
```

A group of a single member draws no header — it renders as a plain card, while keeping its slug. See [How to Group Tasks in a Column]({{< relref "/docs/tuis/board/how-to" >}}#how-to-group-tasks-in-a-column).

### Priority Color Coding

| Priority | Border Color |
|----------|-------------|
| High | Red |
| Medium | Yellow |
| Low / Normal | Gray |

The focused card always shows a double cyan border, regardless of priority.

### Follow-up Provenance Glyphs

A task carrying a [`followup_kind`]({{< relref "/docs/development/task-format" >}}#frontmatter-fields) — one that was auto-spawned by a workflow seam rather than created as new work — shows a coloured glyph at the start of its card:

| Glyph | Follow-up kind | Color |
|-------|----------------|-------|
| `◇` | Manual verification | Cyan |
| `▲` | Risk mitigation | Yellow |
| `▼` | Upstream defect | Red |
| `✗` | Verification failure | Red |
| `↻` | Carry-over | Cyan |
| `◐` | QA test gap | Magenta |
| `◈` | Review finding | Magenta |
| `▤` | Docs gap | Gray |
| `·` | Unrecognized kind | None |

Reading the glyphs:

- An ordinary task draws **nothing** — no glyph and no blank placeholder, so cards for genuine new work are unchanged.
- A task whose `followup_kind` is not one of the known kinds still renders, as the uncoloured `·`, rather than being dropped.
- A **group header** rolls up its members' kinds as a per-kind tally (`▲2 ◈1`), in the order of the table above with unrecognized kinds last. A collapsed group mounts no member cards, so the header is the only place that provenance can surface.
- A **trail ghost card** carries no glyph by design — a ghost is a referenced task with no local file, so there is nothing to classify.

#### Reading and changing the kind in Task Detail

The Task Detail dialog carries a **Follow-up** row directly below Type, showing the same glyph and colour as the card plus the kind's name — so the glyph on a card is decodable without leaving the board. A task that is not a follow-up shows `(none)`.

Press `Enter` on the row to open a picker listing every kind, plus a **(none) — not a follow-up** row at the top that *removes* the field.

- Choosing a kind writes it immediately and reloads the dialog — unlike Priority, Effort, Status and Type, it is not held until you press Save. Because of that, the row is **inert while those fields have unsaved edits**: it shows `(save or revert pending edits first)` and tells you so if you press `Enter`. Save or revert first, then set the kind.
- Clearing **removes** `followup_kind` from the task file rather than blanking it. There is no "empty" state to leave behind.
- `manual_verification` may only be set on a task whose `issue_type` is also `manual_verification`. Choosing it otherwise is refused, and the reason appears as an error notification.
- A task carrying an unrecognized value shows it verbatim beside the `·` glyph, and the picker names it and starts on **Cancel** — so a stray `Enter` cannot delete the value you opened the dialog to inspect.
- Archived and folded tasks show the row as a plain line, and only when a kind is set.

`ait ls` and the pick flow surface the same provenance in text form — see [Task Management]({{< relref "/docs/commands/task-management" >}}).

### Issue Platform Indicators

The board detects the issue tracking platform from the URL hostname:

| Platform | Indicator | Color |
|----------|-----------|-------|
| GitHub (`github` in hostname) | GH | Blue |
| GitLab (`gitlab` in hostname) | GL | Orange (#e24329) |
| Bitbucket (`bitbucket` in hostname) | BB | Blue |
| Other | Issue | Blue |

### PR Platform Indicators

Tasks created from pull requests (via `ait pr-import`) display a pull request indicator on the task card info line:

| Platform | Indicator | Color |
|----------|-----------|-------|
| GitHub (`github` in hostname) | PR:GH | Green |
| GitLab (`gitlab` in hostname) | MR:GL | Orange (#e24329) |
| Bitbucket (`bitbucket` in hostname) | PR:BB | Blue |
| Other | PR | Green |

GitLab uses "MR" (Merge Request) terminology, which the indicator reflects.

### View Filters

The View Selector widget at the top-left of the filter area renders as:

```
[a All | l Locked | f Free | i In-Flight | y By-Topic | z By-Trail]   g Git   t Type
```

It splits filtering into a **base radio** (mutually exclusive — exactly one is always active) and two **independent add-on toggles**. The active base and any active toggle are highlighted in bold cyan; inactive segments are dimmed. All filters compose with text search using AND logic.

#### Base filters (radio)

| Base | Key | Selector Label | Shows |
|------|-----|----------------|-------|
| All | `a` | `a All` | All tasks (default) |
| Locked | `l` | `l Locked` | Busy tasks: status `Implementing` **or** present in the lock list. When a *child* is busy, also includes its parent and all sibling children (context grouping). |
| Free | `f` | `f Free` | Tasks that are ready to pick: neither `Implementing` nor locked. Parents are hidden when any of their children is busy. |
| In-Flight | `i` | `i In-Flight` | Work already under way, in four lanes by what happens next: Planned, Needs your action, Agent can continue, and Blocked. Covers `Implementing` tasks **and** `Ready` tasks carrying an approved-but-deferred plan. Each card also shows a workflow-phase chip — see [In-Flight Lanes and Workflow Phases](#in-flight-lanes-and-workflow-phases). |
| By-Topic | `y` | `y By-Topic` | Tasks clustered into per-anchor swimlanes by their [topic key]({{< relref "/docs/concepts/topic-anchoring" >}}) (`anchor`, else a child's parent topic, else own id). A topic with two or more tasks gets its own lane (labelled by the root task); lone tasks collapse into one **Ungrouped** lane. |
| By-Trail | `z` | `z By-Trail` | The members of one **implementation trail**, laid out as wave columns (`W1 · …`). Each card carries its classification, confidence, and any drift marker; `Enter` opens the full narrative. A short pane below the columns shows the trail's summary. Press `s` to choose which trail is shown. |

Pressing the key for the currently active base is a no-op. Locked and Free are leaf-level inverses (`Locked ∪ Free = All`, `Locked ∩ Free = ∅`) — the Locked view additionally includes parent/sibling cards as context.

**By-Topic lanes:** The By-Topic view uses the task's `anchor` field when set;
otherwise a child falls back to its parent topic and a standalone task falls
back to its own id. If the root task is archived or not currently loaded, the
anchor id still remains the stable lane key. Topics with only one visible task
are collected in the trailing **Ungrouped** lane. See [Topic anchoring]({{< relref "/docs/concepts/topic-anchoring" >}}) for creation flags, inheritance rules, and when to use anchors instead of parent-child tasks or dependencies.

**By-Topic lane sort order:** Lanes are ordered most-recently-touched first by
default. In the By-Topic view, press `o` to open a picker and choose the lane
sort mode:

| Mode | Orders lanes by |
|------|-----------------|
| Recency (default) | newest member's `updated_at` / `created_at`, newest first |
| Topic id | root topic id, newest (highest) id first |
| Size | number of tasks in the lane, largest first |
| Alphabetical | lane label, case-insensitive |

The **Ungrouped** lane stays pinned last in every mode. The choice persists
per-user (in your local board settings), so it survives restarts without
affecting teammates.

#### By-Trail

An **implementation trail** is a durable, wave-structured record of how a group
of tasks should be sequenced, with the evidence behind that ordering. Trails are
created and re-authored by the [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}})
skill — on the board, focus a task
in a kanban or By-Topic view and press `T` to start one (`T` is hidden in In-Flight
and in By-Trail itself). The By-Trail view is a **read-only projection** of a stored
trail: it never writes the trail itself.

Press `z` to enter the view and `s` to choose which trail it shows. Each wave
becomes a column headed `W1 · <title>`, and each card shows the member's
classification glyph, its confidence, its task status, and any drift marker.
`Enter` opens the full narrative for that member. Members that are not live
tasks in this repository — cross-repo members, archived tasks, and tasks that
have gone missing — appear as read-only ghost cards.

**The summary pane.** A short pane below the wave columns carries the trail's
free-form summary — the prose answer to "what should land next, and why". It
appears only in By-Trail, and only when the trail has a summary to show; the
columns take the full height otherwise. Press `v` to open the same text in a
scrollable dialog when it is longer than the pane, and `Escape` to close.

**The depth label.** The view's subtitle states the trail's authoring depth when
the artifact records one — `· lite` or `· deep`. A trail written before depth was
recorded shows no label at all rather than being presented as either, so an
unlabelled trail means "depth not recorded", never "deep".

**Reading one card's context.** In the detail screen the focused member's own
material comes first: its entry, its wave, its drift reasons, and the
observations and evidence that concern it. The trail-wide sections that are not
about this card are withheld and summarized as a count; press `a` to reveal the
whole document, and `a` again to return. A card in a trail with no observations
or exclusions reads as complete rather than empty — there is nothing withheld
to reveal.

**Keeping the view current.** Five keys refresh different things, at very
different costs:

| Key | Refreshes | Cost |
|-----|-----------|------|
| `r` | Re-reads task files from disk and redraws the stored trail | Instant — no subprocess |
| `s` | Re-scans task files for trails, including any created since the board started | A second or two — one artifact read per trail |
| `d` | Re-checks the stored trail against live task state (freshness) | About half a second |
| `S` | Runs `ait sync`, then redraws | A full remote sync |
| `R` | Launches an agent to re-author the trail itself | The slowest by far — an agent run |

Reach for `r` when a task's status changed on this machine — it is free. Reach
for `s` when a **new trail** was created since the board started: the scan reads
task files from disk, so the new trail is listed without restarting the board
(leaving and re-entering the view with `z` re-scans too). Reach
for `S` when the change was made elsewhere: task data lives on the `aitask-data`
branch, so a status set by another machine or a remote agent only arrives in this
checkout through a sync. Use `d` to re-check drift without re-authoring anything;
it never modifies the stored trail. `R` is the heavyweight option — it hands the
trail to an agent, which rewrites it. After a refresh is launched, the view
watches for the new version and reloads on its own when it lands, giving up after
about half an hour.

`R` re-authors at the **lite** depth, which is the default for the trail skill.
A lite trail keeps the waves, entries, per-member rationale and the summary, and
omits the trail-wide observations, relations and exclusions along with the
per-member evidence citations — so it is much cheaper to produce and still
renders here with full lanes, badges, landed marks and drift markers. Because
the depths differ in what they store, pressing `R` on a trail authored at `deep`
replaces it with a lite version; the agent lists exactly what that discards and
asks before writing, and the previous version stays retrievable from the
artifact's history. To re-author at full depth, run the
[trail skill]({{< relref "/docs/skills/aitask-trail" >}}) directly
with its `--deep` flag rather than using `R`.

If the scan cannot read one of your task files — a task being rewritten at that
exact moment, or a malformed one — the view says so and leaves the trail list
alone rather than reporting that there are no trails. Press `s` again.

**Drift markers.** A trail records what it knew when it was written. When a
member's live state no longer matches that snapshot, the card shows an amber
marker:

```
⚠ status_changed: status 'Ready' -> 'Implementing'
```

Up to two reasons are shown per card, with `(+N more)` when there are others; the
complete list is in the detail screen. Common reasons are `status_changed`,
`task_completed`, `task_archived`, `task_folded`, `task_deleted`,
`dependency_changed`, `gate_state_changed`, and `plan_changed`. Drift is a signal
that the trail's sequencing advice may be out of date — `R` re-authors it.

##### Moving a wave into a column

The By-Trail view is read-only about the *trail*, but it can move the underlying
tasks onto the board. `m` moves the focused entry's task; `M` moves every task in
the focused wave.

`M` always shows the review dialog first, listing the tasks in **wave order** — not
board order — and that order is preserved through the move, so a wave dropped into
an empty column lands in the sequence the trail recommends. `m` on a single focused
card skips the review and goes straight to the destination picker.

Both report what they leave behind rather than a bare count:

- **Ghost members** — archived, cross-repo, or missing tasks — cannot move; there is
  no local task file behind them. `m` refuses outright on a ghost card, and `M` names
  the ghosts it skipped while moving the rest of the wave.
- **Child tasks** move with their parent, so `M` skips them and names them. `m` is
  withheld entirely on a focused child, while `M` stays available — a focused child
  still identifies a wave whose parents can move.
- A task appearing twice in one wave moves once, and the duplicate is reported.

If nothing in the wave can move, the board says so instead of opening a picker. The
move never writes to the trail: board column and position are not part of a trail's
freshness, so moving cards cannot make one stale.

**Keys that behave differently here.** The footer relabels itself per view, so it
always shows what the keys actually do. In By-Trail it reads:

```
r Refresh   R Agent Refresh   d Freshness   s Select Trail   S Sync   v Summary   m Move to Col   M Move Wave
```

`v Summary` is listed only while the shown trail actually has a summary — the
footer advertises the key when there is something behind it, not before.
`m Move to Col` and `M Move Wave` are gated differently, and the difference shows on
a focused **child** card: `M` needs any focused live card, while `m` additionally
requires that card not be a child — a child moves with its parent, but it still
identifies a wave whose parents can move. Both are withheld on a ghost card, which
has no local task file behind it.

`C` (commit all modified tasks) is **hidden** in this view. A trail is a reading
projection rather than a set of tasks you own, while "commit all" acts on every
modified task in the repository — so the key is withheld rather than silently
doing something wider than the view suggests. `T`, `w`, the reordering keys and
marking (`Space`) are hidden for the same reason: a wave lane is not a column, so
there is no position within it to reorder into.

**Moving tasks out of a trail is the exception**, because it is the one action
whose target *is* an ordinary board column. `m` moves the focused entry's task and
`M` moves the whole focused wave — see [Moving a wave into a column](#moving-a-wave-into-a-column)
below.

#### Add-on filters (toggle)

| Add-on | Key | Selector Label | Shows |
|--------|-----|----------------|-------|
| Git | `g` | `g Git` | Restricts the visible set to tasks with `issue` or `pull_request` metadata. |
| Type | `t` | `t Type` | Restricts the visible set to tasks whose `issue_type` is in the persisted selection. Turning the toggle on always opens the type-picker dialog so the selection can be reconfirmed or edited; turning it off requires no dialog. |

Add-ons compose with the active base. Example: `l + g` shows busy tasks linked to an issue/PR; `f + t` (with `bug` selected) shows free `bug` tasks ready to pick.

**Locked view auto-expansion:** When the base filter switches to Locked, parent tasks that have at least one busy child are automatically expanded (their child cards are displayed). When switching away, these auto-expanded parents are collapsed back unless they were manually expanded before entering the view.

### In-Flight Lanes and Workflow Phases

The In-Flight view describes work already under way along **two independent axes**:

- the **lane** (the column a card sits in) answers *what happens next*;
- the **phase chip** (a line on the card) answers *where the task sits in the workflow*.

**Every card sits in exactly one lane and carries exactly one chip.** Both are single values on
the card; there is no multi-membership.

"Independent" means **neither axis determines the other**. It does **not** mean a task appears
twice. The two pairs below are the worked examples — read both, because with only one of them the
chip looks like a restatement of the lane.

**Same phase, different lanes** — the lane is not derivable from the phase:

| # | Task | Status | Phase (chip) | Lane |
|---|------|--------|--------------|------|
| A | approve-and-stop | `Ready` + marker | `plan_approved` | **Planned** |
| B | in-flight, `resume_point == IMPLEMENT` | `Implementing` | `plan_approved` | **Agent can continue** |

**Same lane, different phases** — the phase is not derivable from the lane:

| # | Task | Lane | Phase (chip) |
|---|------|------|--------------|
| C | pending human gate | Needs your action | `awaiting_review` |
| D | `resume_point == POSTIMPL` | Needs your action | `post_impl` |

**`resume_point`** is the checkpoint a task's gate ledger says it would resume from, and it takes
three values: `PLAN` (nothing durable recorded yet), `IMPLEMENT` (the plan was approved, so the
next thing owed is code) and `POSTIMPL` (the review passed, so what remains is merge and
archival). **marker** is the [deferred-plan marker](#task-metadata-fields) — the frontmatter field
recording an approved plan whose implementation was deliberately put off.

A and B are two **different tasks**. They share a phase because an approve-and-stop task reverts
to `Ready` but keeps its gate ledger — the last thing recorded is still that the plan was
approved — while the lane splits them on the question the operator actually asks: one can be
handed to an agent, the other has not started.

#### The four lanes

In render order, with the card operations each offers:

| Lane | Holds | Card operations |
|------|-------|-----------------|
| **Planned** | `Ready` tasks carrying an approved-but-deferred plan; implementation never started | `[p pick]` only |
| **Needs your action** | a human gate is pending, failed, or needs re-signing; or every gate now passes | `[p pick] [g resume] [s sign-off] [f fail]` |
| **Agent can continue** | an agent can pick the work up unattended | `[p pick] [g resume]` |
| **Blocked** | unresolved dependencies | `[p pick]` |

Two rules that are not guessable from the lane names:

- **Blocked outranks every other lane.** A task with an approved plan *and* an unresolved
  dependency renders in Blocked, not Planned — the lane reports what can happen next, and the
  answer there is "nothing".
- **A Planned task offers `p` and nothing else, and the other keys are refused rather than
  merely hidden.** Pressing `g`, `s` or `f` on one — through the key, a rebinding, or the command
  palette — shows an explanation instead of acting. Resuming would start implementation without
  passing the planning checkpoint and its remote drift check, and signing off would approve a
  review of code that was never written.

#### The five workflow phases

| Phase | Chip label |
|-------|------------|
| `plan_approved` | `plan approved` |
| `implementing` | `implementing` |
| `awaiting_review` | `awaiting review` |
| `needs_attended_agent` | `needs attended agent` |
| `post_impl` | `post-implementation` |

`needs_attended_agent` exists because a gate can be machine-run and still need a person to launch
it: `docs_updated` is a machine gate whose work is a *procedure*, so the headless engine defers it
and only an attended agent can run it. A task whose review already passed can therefore still be
held back from archival, and reporting it as `post-implementation` would say "ready to archive"
about a task the archival guard will refuse.

The label above is the chip's stem. **The rendered form differs between the two surfaces** — the
card's chip is deliberately compact, and the task detail dialog carries the expanded one:

| How the phase was determined | On the card | In task detail |
|------------------------------|-------------|----------------|
| from the gate ledger, task has enforced gates | `<label> · <satisfied>/<enforced>` | same |
| from the gate ledger, task has no enforced gates | `<label>` | same |
| from the deferred-plan marker alone | `<label>` | `plan approved (from marker)` |
| ledger absent or unreadable | `<label>` | see [Honest degradation](#honest-degradation) |

The `(from marker)` qualifier belongs to a `Ready`-plus-marker task and is **detail-only**. The
marker outranks the ledger, so the chip does not claim there is no ledger — such a task usually
has one. The card omits every qualifier on purpose: its own action line already says what to do,
in plainer words than the ledger vocabulary.

#### Gate progress

Where a chip carries a fraction, it counts satisfied gates against enforced ones. Two rules read
as bugs unless you know them:

- **The denominator is the enforced active set, not the declared `gates:` list.** A gate your
  execution profile filters out is not counted at all — it is neither in the numerator nor in the
  denominator. A task declaring three gates under a profile that enforces one shows `x/1`.
- **A stale signature counts as not satisfied, even though the ledger says `pass`.** A human
  approval is bound to the code it approved; when that code changes the signature no longer binds,
  and the archival guard treats the gate as outstanding. The board matches the guard rather than
  the raw ledger, and such a card says `awaiting re-sign: <gate>` so the action is the *re*-signing
  rather than a first signature.

A skipped gate is the mirror case: `skip` is terminal — "not applicable" — so it **is** satisfied
and does count toward the numerator, even though it is not a pass.

#### Honest degradation

Under an execution profile that records no gates there is no ledger to read, so the view derives
what it can from the task's status, whether a plan file exists, and the deferred-plan marker — and
says which of those it used:

| State | Card chip | Card action line | Task detail |
|-------|-----------|------------------|-------------|
| no ledger, a plan file exists | `implementing` | `No gate information yet — pick/resume` | `No gate ledger — implementing (derived)` |
| no ledger, no plan file | `implementing` | `No gate information yet — pick/resume` | `No gate ledger — implementing (unknown)` |
| a ledger exists but could not be read | `implementing` | `gate state unavailable` | `Gate state unavailable`, with the reason |

**`unknown` means "we cannot tell how far it got", not "it has not started".** A task whose status
is `Implementing` has asserted that implementation began; with neither a ledger nor a plan the
board simply has no evidence of progress. No fraction is shown in that state — an absent fraction
is a different claim from `0/N`, and the board will not fabricate one.

#### Gates in Task Detail

Press `Enter` on a card to open the task detail dialog. When the task has gates or a ledger, it
carries a **Gates** section — the expanded counterpart of the card's chip, titled with the same
fraction, e.g. `Gates (2/3)`. It leads with the phase chip, then lists one row per enforced gate:

| Row | Meaning |
|-----|---------|
| `✓ <gate> — passed` | satisfied |
| `⊘ <gate> — skipped (not applicable)` | satisfied, but deliberately distinct from passed |
| `· <gate> — pending` | enforced and has not run yet — the ordinary state of a freshly picked task |
| `◈ <gate> — pending; needs attended agent` | a procedure gate the headless engine defers |
| `✗ <gate> — failed` | ran and failed |
| `⚠ <gate> — pass, signature stale; needs re-sign` | both facts at once: the ledger says `pass`, and the signature no longer binds the code |

Gates your profile filtered out are listed afterwards under a dimmed `filtered by profile (audit
only)` heading. They are shown so the difference between what a task declares and what is enforced
is visible, and they are counted in nothing.

The section is read-only; gates are signed from the In-Flight view with `s` / `f`, or from the
command line with [`ait gate`]({{< relref "/docs/commands/gates" >}}).

### Column Configuration

Columns are stored in `aitasks/metadata/board_config.json`:

```json
{
  "columns": [
    {"id": "now", "title": "Now", "color": "#FF5555"},
    {"id": "next", "title": "Next Week", "color": "#50FA7B"},
    {"id": "backlog", "title": "Backlog", "color": "#BD93F9"}
  ],
  "column_order": ["now", "next", "backlog"],
  "settings": {
    "auto_refresh_minutes": 0,
    "sync_on_refresh": false
  }
}
```

- **id** — Unique identifier (auto-generated from title on creation)
- **title** — Display name (can include emojis)
- **color** — Hex color code for the column header and border
- **column_order** — Controls left-to-right display order
- **settings.auto_refresh_minutes** — Interval in minutes for periodic board refresh (0 to disable, default 0)
- **settings.sync_on_refresh** — Enable automatic sync with remote on each auto-refresh interval (default false). Requires `.aitask-data` worktree (data branch mode). When enabled, the board subtitle shows "+ sync"
- **settings.collapsed_columns** — List of column IDs that are currently collapsed (default: empty). Collapsed columns show only their title and task count in a narrow strip. Tasks in collapsed columns are not rendered, which improves performance for boards with many tasks

The "Unsorted / Inbox" column is a special dynamic column (ID: `unordered`) that appears automatically when any task resolves to it. Two states do: a task with no `boardcol` assignment at all, and a task explicitly moved into this column — moving a card here writes `boardcol: unordered` verbatim, as does `ait update --boardcol unordered`. Both render in this one lane, and `ait ls --boardcol unordered` lists both.

### Color Palette

When adding or editing a column, you can choose from 8 predefined colors:

| Color | Hex Code | Name |
|-------|----------|------|
| ● | `#FF5555` | Red |
| ● | `#FFB86C` | Orange |
| ● | `#F1FA8C` | Yellow |
| ● | `#50FA7B` | Green |
| ● | `#8BE9FD` | Cyan |
| ● | `#BD93F9` | Purple |
| ● | `#FF79C6` | Pink |
| ● | `#6272A4` | Gray |

### Task Metadata Fields

The board reads and displays the following frontmatter fields from task files:

| Field | Type | Editable from Board | Description |
|-------|------|---------------------|-------------|
| `priority` | string | Yes (cycle) | `low`, `medium`, or `high` |
| `effort` | string | Yes (cycle) | `low`, `medium`, or `high` |
| `risk_code_health` | string | Yes (cycle) | `low`, `medium`, or `high` — shown only when set by the [risk-evaluation planning step]({{< relref "/docs/workflows/risk-evaluation" >}}); read-only for Done/Folded tasks |
| `risk_goal_achievement` | string | Yes (cycle) | `low`, `medium`, or `high` — shown only when set by the [risk-evaluation planning step]({{< relref "/docs/workflows/risk-evaluation" >}}); read-only for Done/Folded tasks |
| `status` | string | Yes (cycle) | `Ready`, `Editing`, `Implementing`, `Postponed`, `Done`, `Folded` |
| `issue_type` | string | Yes (cycle) | Loaded from `task_types.txt` (defaults: bug, chore, documentation, enhancement, feature, manual_verification, performance, refactor, style, test) |
| `labels` | list | Read-only | Tag list, displayed comma-separated |
| `depends` | list | Read-only* | Task IDs this task depends on. *Can remove stale references. |
| `assigned_to` | string | Read-only | Person assigned to the task |
| `issue` | string | Read-only | URL to external issue tracker |
| `pull_request` | string | Read-only | URL to external pull request / merge request (set by `ait pr-import`) |
| `contributor` | string | Read-only | PR author username, displayed as `@username` on the card |
| `contributor_email` | string | Read-only | PR author email (shown in detail dialog) |
| `implemented_with` | string | Read-only | Code agent and model used to implement the task (e.g., `claudecode/opus4_6`) |
| `plan_approved_at` | string | Read-only | Timestamp of a plan that was approved with implementation deliberately deferred. Written and cleared **exclusively by the task workflow** — the board renders it and offers no way to edit it. Surfaces as the card's `· Planned` qualifier, as an [In-Flight lane](#in-flight-lanes-and-workflow-phases), and as `Plan approved:` under Tracking & provenance. |
| `created_at` | string | Read-only | Creation timestamp (YYYY-MM-DD HH:MM) |
| `updated_at` | string | Auto-updated | Updated automatically on save |
| `children_to_implement` | list | Read-only | Child task IDs for parent tasks |
| `folded_tasks` | list | Read-only | Task IDs that were merged into this task |
| `folded_into` | string | Read-only | Task ID this task was folded into |
| `anchor` | string | Yes | Topic root used by the By-Topic view. Empty means the task is its own topic root. |
| `file_references` | list | Read-only | Pointers to source files / line ranges (e.g., `foo.py:10-20`). Pressing **Enter** on a focused row opens `ait codebrowser` at the referenced location. See [Creating Tasks from Code]({{< relref "/docs/workflows/create-tasks-from-code" >}}). |
| `boardcol` | string | Auto-managed | Column ID (set by board operations) |
| `boardidx` | integer | Auto-managed | Sort index within column (set by board operations) |
| `boardgroup` | string | Auto-managed | Group slug within the column (see [Group Header Anatomy](#group-header-anatomy)) |

### Board Data Fields

Three metadata fields are managed internally by the board:

- **`boardcol`** — The column ID where the task is placed (e.g., `"now"`, `"backlog"`, `"unordered"`). Tasks without this field appear in the "Unsorted / Inbox" column, as do tasks carrying an explicit `"unordered"` — the two states are one lane. A **non-string** value (e.g. `boardcol: 42`, which YAML parses as an integer) matches no column at all and renders nowhere.
- **`boardgroup`** — The group slug within the column. The slug **is** the group's identity — there is no group registry, no group ID and no stored title — so two spellings are two different groups, and `ait update --boardgroup` rejects a slug outside `[a-z0-9_]+` rather than normalizing one into the other. An explicit `""` means "deliberately ungrouped", which is not the same as the field being absent.
- **`boardidx`** — The sort index within a column. Lower values appear higher; ties are broken by filename. Values are widely spaced rather than consecutive, and may be negative — a movement writes only the moved task's file, placing it in the gap between its new neighbours rather than renumbering the column. Only the relative order is meaningful. When repeated moves into the same position exhaust a gap, that single column is re-spaced automatically.

These fields are always written last in the frontmatter and are updated using a reload-and-save mechanism that prevents overwriting other metadata fields changed externally.

### Lock Status Display

Lock information is not stored in task files -- it is fetched from the remote `aitask-locks` branch via `aitask_lock.sh --list` and maintained in memory as a lock map. The board refreshes the lock map on startup, on every manual/auto refresh, and after lock/unlock operations.

| Display Location | Locked | Unlocked |
|------------------|--------|----------|
| **Task card** | `🔒 user@example.com` (additional line) | No lock line shown |
| **Task detail** | `🔒 Locked: user@co on hostname since timestamp` | `🔓 Lock: Unlocked` (dimmed) |

Locks older than 24 hours show a `(may be stale)` warning in the detail view.

**Button states in detail dialog:**

| Button | Enabled when | Disabled when |
|--------|-------------|---------------|
| 🔒 Lock | Task is unlocked AND status is not Done/Folded AND not read-only | Task is already locked, or Done/Folded/read-only |
| 🔓 Unlock | Task is locked | Task is not locked |

For details on the underlying lock mechanism, see the [`ait lock` command reference]({{< relref "/docs/commands/lock" >}}).

### Modal Dialogs Reference

| Dialog | Trigger | Purpose |
|--------|---------|---------|
| **Task Detail** | `Enter` on card / double-click | View/edit task metadata (including [follow-up provenance](#reading-and-changing-the-kind-in-task-detail)), lock status, pull request link, contributor info, and content; access Pick, Lock, Unlock, Save, Revert, Edit, Delete, Close buttons |
| **Follow-up Kind** | `Enter` on the Follow-up row in Task Detail | Pick the task's follow-up kind, or remove it |
| **Column Manage** | `e` / command palette "Manage Columns" | List every column with its position, color, ID and task count; Add, Edit, Delete and Merge buttons, `Enter` to edit and `Shift+Up`/`Shift+Down` to reorder |
| **Column Edit** | Command palette "Add/Edit Column" / click `✎` in column header / Add or Edit in Column Manage | Set column title and color |
| **Column Select** | Command palette "Edit/Delete/Collapse/Expand Column" | Pick which column to act on |
| **Column Multi-Select (Merge from)** | "Merge" in Column Manage / command palette "Merge Columns" | Pick one or more source columns to merge (Unsorted / Inbox is offered only when it holds tasks) |
| **Column Select (Merge into)** | Confirming the merge sources | Pick the destination column (the chosen sources are omitted; Unsorted / Inbox is offered unless it is a source) |
| **Merge Confirm** | Confirming the destination | Names the source columns, the destination, and how many tasks will move |
| **Move Tasks to Column** | `m` with tasks marked / `M` in By-Trail / command palette "Move Tasks to Column" or "Move Wave to Column" | Review which tasks will move before a destination is chosen — in board order for a marked set, in wave order for `M` |
| **Column Select (Move to)** | Confirming the review, or `m` on a single focused card | Pick the destination column (collapsed columns and the column the whole selection already occupies are omitted) |
| **Delete Column Confirm** | After selecting column to delete | Confirm column deletion; warns about task count |
| **Commit Message** | `c` or `C` key | Enter commit message for modified task(s) |
| **Delete Confirm** | "Delete" button in task detail | Confirm task deletion; lists all files to be removed |
| **Dependency Picker** | `Enter` on Depends field (multiple deps) | Select which dependency to open |
| **Remove Dep Confirm** | `Enter` on missing dependency | Offer to remove stale dependency reference |
| **Child Picker** | `Enter` on Children field (multiple children) | Select which child task to open |
| **Folded Task Picker** | `Enter` on Folded Tasks field (multiple) | Select which folded task to view (read-only) |
| **Lock Email** | "🔒 Lock" button in task detail | Enter email for lock ownership; confirms to acquire lock via `aitask_lock.sh` |
| **Unlock Confirm** | "🔓 Unlock" button (when lock belongs to different user) | Shows lock details (who, where, when); offers "Force Unlock" or "Cancel" |
| **Sync Conflict** | Sync detects merge conflicts | Shows conflicted files; offers "Resolve Interactively" (opens terminal) or "Dismiss" |
| **Settings** | `O` key / command palette "Options" | Configure board settings (auto-refresh interval, sync on refresh) |

### Git Integration Details

The board auto-detects whether task data lives on a separate `aitask-data` branch (via the `.aitask-data/` worktree) or on the current branch (legacy mode). All git operations are routed through a worktree-aware helper, so the board works transparently in both modes.

**Modified file detection:**

The board queries `git status --porcelain -- aitasks/` on startup and after each refresh to identify modified `.md` files. Modified tasks show an orange asterisk (*) next to their task number. In branch mode, this targets the `aitask-data` worktree automatically.

**Commit workflow:**

1. Selected files are staged with `git add <filepath>`
2. A commit is created with the user-provided message
3. The board refreshes git status after commit

In branch mode, commits target the `aitask-data` branch, not the main code branch.

**Revert workflow:**

Runs `git checkout -- <filepath>` to discard local changes and restore the last committed version.

**Delete workflow:**

1. Files are removed with `git rm -f <filepath>` (falls back to `os.remove` for untracked files)
2. Empty child task/plan directories are cleaned up
3. An automatic commit is created: "Delete task t<N> and associated files"

### Configuration Files

| File | Format | Purpose |
|------|--------|---------|
| `aitasks/metadata/board_config.json` | JSON | Board column definitions, order, and settings (auto-refresh) |
| `aitasks/metadata/board_config.local.json` | JSON | User-local view state: which columns and which groups you have collapsed |
| `aitasks/metadata/task_types.txt` | Text (one per line) | Valid issue types for the Type cycle field |

These files are auto-created with defaults if they don't exist. The `.local.json` layer is yours alone — collapsing a column or a group changes only your view, never a teammate's.

### Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `EDITOR` | `nano` (Linux/macOS), `notepad` (Windows) | External editor opened by the "Edit" button |
| `TERMINAL` | Auto-detected | Terminal emulator for "New Task" and "Pick" actions |
| `PYTHON` | `python3` | Python interpreter (used by launcher if shared venv is unavailable) |

**Terminal auto-detection order:** `$TERMINAL`, then `x-terminal-emulator`, `xdg-terminal-exec`, `gnome-terminal`, `konsole`, `xfce4-terminal`, `lxterminal`, `mate-terminal`, `xterm`. If none found, the board suspends to run commands in the current terminal.

---

**Next:** [Monitor](../../monitor/) — the dashboard of every pane in your tmux session.
