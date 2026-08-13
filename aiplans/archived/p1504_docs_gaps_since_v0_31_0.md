---
Task: t1504_docs_gaps_since_v0_31_0.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# t1504 — Documentation gaps since v0.31.0

## Context

`/aitask-docs-gap` scanned `v0.31.0..HEAD` and recorded six shipped features
whose user-facing docs never landed. Verified: **all ten** shipping commits
named in the task touched zero files under `website/` —

| Commit | Feature | website/ touched |
|---|---|---|
| `16afd191d` `e7a071022` `0683e8791` | board groups (t1243_8/9/10) | none |
| `d8967df91` `876fbabf2` | workflow phase (t1420, t1479) | none |
| `afd1c5b2f` | shadow auto-recheck loop (t1159_2) | none |
| `fabd8e615` `9397077f9` | round metadata (t1159_1, t1493) | none |
| `d00e90e2e` | follow-up glyph (t1468_3) | none |
| `75ca90438` | gate skills ported (t635_23) | none |

So every gap is real. But **three of the six already have owner tasks**, which
is what shapes the scope below — writing all six here would duplicate or
pre-empt work another task is committed to.

Every claim written below was verified against **live source**, not against the
task text or the archived plans.

## Scope decisions (confirmed with the user)

1. **Gap 1 (board groups) — write the shipped half here, then narrow
   `t1243_13`.** Groups are only half-shipped: `boardgroup`, `GroupHeader`, `x`
   collapse, persisted collapse state and the match badge landed (t1243_8/9/10),
   while `G`, group formation, block moves and in-board membership commands
   (t1243_11/t1243_12) have not. `t1243_13` is `Ready` but `depends: [t1243_12]`,
   so it cannot run for a while. This repeats exactly what **t1432** did for
   marking / bulk-move: document what shipped, then narrow the blocked owner and
   cross-link both ways.
2. **Gaps 3 + 4 (shadow auto-recheck loop, concern-block rounds) — deferred
   entirely to `t1159_4`.** That task is `Ready` and blocked only on `t1159_3`,
   which is `Implementing` **right now**, so it unblocks imminently; it already
   owns the minimonitor page, `aidocs/framework/shadow_agent.md` and the `L` /
   `t` key docs. Writing them here would be overwritten within days and risks
   colliding with a live session. Phase 6 instead hands `t1159_4` the two
   surfaces its own file list is missing (the monitor pages and
   `workflows/shadow-agent.md`), so the deferral loses nothing.
3. **Gap 6 — write `/aitask-run-gates` and `/aitask-gate-docs-updated` pages;
   `aitask-gate-template` stays off the site.** It is an authoring scaffold, not
   a user command: it has no `**Usage:**` invocation block, unlike every other
   documented skill. `t635_18`'s Skills section still owns the wider gates docs
   sweep (concepts, workflows, gate-verifier authoring story).
4. **`boardgroup`'s non-website surfaces stay with `t1243_13`.** The gap names
   `website/content/docs/development/task-format.md`; the seed / `AGENTS.md` /
   `CLAUDE.md` / `.codex` / `.opencode` instruction mirrors are section B of
   `t1243_13` and involve an `ait setup` regeneration that does not belong in a
   docs-gap task. Phase 2 states that boundary explicitly.

## Corrections to the task's own text

- **Gap 2 says the phase is rendered "in the docked followed-agent panel".**
  True, and worth stating precisely: the panel takes the phase **and
  deliberately not the gate summary** (`minimonitor_app.py:1161-1167`), unlike
  the list rows where the two share one line. Documenting them as the same
  surface would be wrong.
- **Gap 1 says single-member groups render "as plain cards".** Correct, but the
  reason matters and belongs in the docs: `board_groups.build_column_units`
  **keeps** the slug (`board_groups.py:139-141`), so a member moving away never
  silently dissolves the group — only the header is withheld.
- **A live drift, not in the task text:** `minimonitor/how-to.md:125-128`
  asserts "The one thing on the pinned card that *does* change is its
  prioritized mark". t1420 made that untrue — the advisory phase repaints there
  too (`_refresh_own_live_state`, `minimonitor_app.py:1192-1219`). Phase 3 fixes
  it; leaving it would be a page actively contradicting shipped behavior.

### Pre-phase (risk mitigations)

1. `[commit_only_named_paths]` Before the first edit, capture the working tree's
   pre-existing dirty set and keep it for the commit step:
   ```bash
   git status --porcelain > /tmp/claude-1000/-home-ddt-Work-aitasks/7debf3b0-a005-43e0-a256-bf01751802b6/scratchpad/t1504_pre_edit_status.txt
   ```
   Every path in that snapshot belongs to someone else — unrelated local work
   and whatever the concurrent `t1159_3` session is touching. At Step 8, stage
   **only** the paths this plan names and commit them by path, never by index:
   `git commit -o -- <path> …` for code/doc files and `./ait git` for the
   `aitasks/` files. Re-run `git status --porcelain` before committing and
   confirm the diff against the snapshot contains only this task's files;
   if it does not, stop and report rather than committing.

## Phase 1 — Board groups, shipped half (gap 1)

### 1a. `website/content/docs/development/task-format.md`

Insert a `boardgroup` row after `boardidx` (line 47), matching the terse
`boardcol`/`boardidx` row density rather than the long `followup_kind` row:

| `boardgroup` | slug `[a-z0-9_]+`, or `""` | In-column board group membership. Update-only (`ait update --boardgroup`); an invalid slug is **rejected, not coerced**. `""` is an explicit "ungrouped" tombstone — distinct from the field being absent. |

### 1b. `website/content/docs/tuis/board/reference.md`

- **Task Operations table** — add a second `x` row after line 54 (the table
  already repeats keys across differing `Context` values):
  `| `x` | Expand / collapse the focused task group | Board (focused group header) |`
- **Task Card Anatomy** (92-106) — add a group-header line block after the card
  diagram, transcribed from `GroupHeader._label` (`aitask_board.py:2711-2737`):
  ```
  ▾ perf work (3) · 2 match · ▲2 ◈1
  ```
  with a legend: `▾`/`▸` expanded/collapsed · title humanized from the slug
  (`perf_work` → `perf work`) · member count · match count during a filter pass
  · follow-up roll-up (Phase 4 defines the glyphs).
- **Task Metadata Fields table** — add a `boardgroup` row (`string`,
  `Auto-managed`) beside `boardcol`/`boardidx` at 337-338.
- **Board Data Fields** (340-347) — "Two metadata fields" → "Three", plus a
  `boardgroup` bullet: identity **is** the slug (no registry, no group ids), so
  two spellings are two groups and the CLI refuses to normalize one into the
  other.
- **Configuration Files table** (422-427) — add
  `aitasks/metadata/board_config.local.json` (JSON — user-local view state:
  collapsed columns and collapsed groups). Fix the trailing "Both files are
  auto-created" → "These files are auto-created".

### 1c. `website/content/docs/tuis/board/how-to.md`

New `### How to Group Tasks in a Column`, inserted after "How to Organize Tasks
into Columns" (ends line 28) — groups are the in-column organization concept, so
it reads directly after columns. Follow the established section shape (heading →
one-sentence context → bold sub-labels → short lists → a `> **Note:**` callout).
Content, all source-verified:

- **What a group is** — a named cluster of tasks inside one column. Membership
  lives in the task file's `boardgroup` field; the slug **is** the identity.
- **Assigning membership** — `ait update --batch <id> --boardgroup perf_work`;
  `--boardgroup ""` explicitly ungroups. An invalid slug is rejected, because
  silently lowercasing or re-separating one would merge two distinct groups —
  and merging groups is destructive (`aitask_update.sh:2328-2338`).
- **Reading a group** — a group of 2+ draws a header row; a group with a single
  member renders as a plain card while **keeping** its slug.
- **Collapsing** — focus the header, press **x**. A collapsed group renders as
  the header alone. Note that `x` is context-sensitive: on a card it toggles
  child tasks, on a header the group.
- **Navigation** — arrow keys move over *units*, so a collapsed group is one
  stop rather than N.
- **Filtering** — during a filter pass the header shows `· N match`: how many
  members would show if it were expanded. A collapsed group therefore says it
  still holds matches instead of looking empty.
- **Persistence** — collapse state is **per-user** (`board_config.local.json`),
  not shared; entries naming a column or group that no longer exists are pruned
  on load, and collapse follows a column through rename / merge / delete.

Do **not** document `G`, group creation, block moves or membership commands —
unshipped, and owned by `t1243_13` (Scope decision 1).

## Phase 2 — Narrow `t1243_13` (reciprocal half of the scope link)

Edit `aitasks/t1243/t1243_13_documentation.md`, extending the existing
"**Scope narrowed.**" callout it already carries from t1432, to record that
t1504 wrote the shipped half. Remaining scope for that child: `G`, group
formation and block moves, in-board membership commands, `x`-on-header parity
once those land, and **all of section B's non-website `boardgroup` surfaces**
(seed, AGENTS.md regeneration, `CLAUDE.md`, the `.codex`/`.opencode` mirrors) —
explicitly still owned there. Build on the group prose now on the board pages
rather than re-introducing it. Commit with `./ait git`.

## Phase 3 — Workflow-phase signal in the monitors (gap 2)

The rendered strings, verbatim from `workflow_phase.py:506-560`: phase values
are `PLAN` / `IMPLEMENT` / `POSTIMPL` / an `unknown (…)` variant; ` ⏸` is
appended when the agent is waiting on input; the full monitor prefixes
`phase: `, minimonitor does not. When there is nothing honest to say the phase
renders as **empty** and the surface omits it.

### 3a. `website/content/docs/tuis/minimonitor/how-to.md`

- Add a bullet to the agent-card list (41-47) for the merged row: for agents
  with a task, a third dimmed line carrying the **workflow phase and the gate
  summary together** — `IMPLEMENT ⏸ · 1/4 1p 1f`. Either half may be empty; the
  row is omitted only when both are. Note line 49's existing "no gate line"
  claim about *other* panes stays correct.
- Explain the values: `PLAN` / `IMPLEMENT` / `POSTIMPL` are where the task
  sits in the workflow; ` ⏸` means the agent is waiting on you; `unknown (…)`
  is a distinct **"cannot tell"** state naming its cause (`rec off` — gate
  recording is off for that profile; `ledger` — only the ledger could be read,
  no live prompt markers; `unknown ⏸` — waiting, phase unresolved). No row at
  all means the task is ungated and no phase resolved — not "no phase".
- State that at narrow widths the row sheds detail in a fixed order: the gate
  summary abbreviates (`1/4 pass, 1 pending` → `1/4 1p`), then the phase clips,
  then the phase drops entirely — the counts are what survive
  (`minimonitor_app.py:204-218`).
- **Fix the drift** at 118-128: the pinned card's live half is now the mark
  **and** the advisory phase. Keep the note's point (no status badge, identity
  frozen) and add that the panel carries the phase and deliberately not the
  gate summary.
- Add nothing to the key table — the phase is not a binding.

### 3b. `website/content/docs/tuis/minimonitor/_index.md`

Add the phase to the `## Relationship to monitor` comparison (24-41), so the
two monitors' cards are described consistently.

### 3c. `website/content/docs/tuis/monitor/how-to.md`

In the agent-card anatomy (39-74), add a bullet: for agent panes carrying a task
ID the status row ends with the gate summary and then the advisory phase in its
labelled form — `gates: 1/4 pass  phase: IMPLEMENT`
(`monitor_app.py:1616-1636`). Cross-link the minimonitor how-to for the value
vocabulary rather than repeating it.

### 3d. `website/content/docs/tuis/monitor/reference.md`

Add the phase to the card-anatomy / status-row reference so the reference page
does not contradict the how-to.

Throughout: say **advisory** — the phase never gates a key, a spawn, or
anything else.

## Phase 4 — Follow-up-kind glyph on board cards (gap 5)

`website/content/docs/tuis/board/reference.md` only. (`how-to.md` has no
card-anatomy prose — that content lives entirely in `reference.md`, so the gap's
parenthetical target does not exist.)

- New `### Follow-up Provenance Glyphs` after "Priority Color Coding" (ends
  116), mirroring the existing `| … | Indicator | Color |` legend shape.
  Transcribe the mapping from its single canonical source,
  `.aitask-scripts/lib/followup_kinds.py:29-51`, in declaration order:
  `◇` cyan manual verification · `▲` yellow risk mitigation · `▼` red upstream
  defect · `✗` red verification failure · `↻` cyan carry-over · `◐` magenta QA
  test gap · `◈` magenta review finding · `▤` grey docs gap · `·` uncoloured
  for an unrecognized kind.
- State the rules: an ordinary task draws **nothing** (no glyph, not a blank);
  an unrecognized value still renders, as the uncoloured `·`; a group header
  rolls up its members' kinds (`▲2 ◈1`) because a collapsed group mounts no
  member cards, so the header is the only place that provenance can surface; a
  **trail ghost card carries no glyph by design** — a ghost has no local file
  and nothing to classify.
- Add the glyph to the Task Card Anatomy diagram's first card line (it is
  prepended before the mark and task number).
- Cross-link the `followup_kind` row in
  `development/task-format.md` and the `ait ls` surfacing in
  `commands/task-management.md`, both of which already exist (t1468_1/t1468_4).

## Phase 5 — Gate skills reference pages (gap 6)

Two net-new pages; neither skill is mentioned anywhere under `website/content/`
today. Match the established per-skill template exactly: front matter of
`title`/`linkTitle` (both `/aitask-<name>`), `weight`, `description`,
`maturity`, `depth`; body opens with a 1-2 sentence summary, a `**Usage:**`
fenced block, the standard root-directory `> **Note:**`, then H2 sections.

### 5a. `website/content/docs/skills/aitask-run-gates.md` (weight 16)

Sits beside `/aitask-resume` (weight 14). Cover: the conversational front of the
same engine `ait gates run` drives — it never forks the logic; `/aitask-run-gates
<task-id> [--gate <name>] [--dry-run]`; `--gate` force-runs one gate past its
retry budget when predecessors are satisfied; `--dry-run` reports the decision
tree and writes nothing to the ledger. What it reports: all-satisfied → suggests
archiving but **never** sets `status: Done`; a pending human gate → explains the
next human action and **never creates the signal itself**; exhausted → points at
`ait gate log`. Advisory and orchestration only: no frontmatter edits, no
merging, no archiving. Cross-link `commands/gates.md` anchors and
`/aitask-resume`.

### 5b. `website/content/docs/skills/aitask-gate-docs-updated.md` (weight 17)

Cover: the verifier for the `docs_updated` gate, a **procedure-backed** gate —
work an agent must do, so the headless engine defers it and reports `needs
agent`; it runs from the attended workflow (task-workflow Step 8 / aitask-resume)
so its doc edits land in the same reviewed commit as the code. It reads *how* to
update docs from the project's own configured `doc_update.guide`, never a
framework-internal document, and confirms with the user before applying.
Terminal results: `pass` (did the work, or confirmed the docs were already
right), `skip` (no doc-relevant surface), `fail` (docs were needed and the user
declined) — and a `fail` blocks archival. Per the conventions, describe
availability generically ("Claude Code and all other supported coding agents"),
never by enumerating agent trees.

### 5c. Index and cross-links

- `website/content/docs/skills/_index.md` — the body listing is **hand-curated**
  (no generator exists). Neither page fits the six existing categories, so add a
  new `### Gates` group after "Task Implementation" with a two-row table and a
  one-line intro, following the group pattern exactly.
- `website/content/docs/commands/gates.md` — add cross-links to both new pages
  (it currently links out to no skill page at all), so the CLI reference and the
  skill reference point at each other.

## Phase 6 — Hand gaps 3 + 4 to `t1159_4`

Edit `aitasks/t1159/t1159_4_docs_and_integration.md` to add the two surfaces its
current file list omits, so the deferral costs nothing:

- `website/content/docs/tuis/monitor/how-to.md` — the monitor's own concern
  picker and auto-offer toast prose (185-211) needs the `(round N)` suffix and
  the uncertified-round behavior, exactly as the minimonitor page does.
- `website/content/docs/workflows/shadow-agent.md` — tie the round number to the
  "every review round re-derives findings from scratch" passage (102-104) that
  page already carries.

Also record there that a block whose round header fails certification **warns and
opens the raw block** rather than reporting a false all-clear — the single most
misleading thing an undocumented round could cause.

Then add a short note to `aitasks/t1504_docs_gaps_since_v0_31_0.md` under gaps 3
and 4 recording that `t1159_4` owns them, so the two tasks point at each other.
Commit both with `./ait git`.

### Post-phase (risk mitigations)

1. `[verify_transcribed_value_sets]` Run each value-fidelity check as a command
   whose failure is visible, and report the hit count for every one — a silent
   zero-match is a FAIL, not a pass:
   - **Glyphs:** extract the glyph/colour pairs from the new
     `### Follow-up Provenance Glyphs` table and diff them against
     `FOLLOWUP_KINDS` in `.aitask-scripts/lib/followup_kinds.py`. All nine rows
     (eight kinds + the `·` unknown fallback) must match, `▤`/`#808080`
     included.
   - **Phase strings:** for each documented string (`PLAN`, `IMPLEMENT`,
     `POSTIMPL`, `unknown (rec off)`, `unknown (ledger)`, `unknown ⏸`, the
     `phase: ` prefix, the ` ⏸` waiting suffix), grep
     `.aitask-scripts/lib/workflow_phase.py` and require ≥1 hit each.
   - **Binding:** `grep -n 'Binding("x"' .aitask-scripts/board/aitask_board.py`
     must return exactly the two rows the docs now describe (child toggle and
     group toggle).
   - **Group header format:** the documented
     `▾ perf work (3) · 2 match · ▲2 ◈1` shape matches `GroupHeader._label`.
   Run these under `set -o pipefail` so a piped check cannot report a false
   success, and state each result explicitly in the Final Implementation Notes.

## Verification

- **Key drift:** every key documented here exists in the live bindings —
  `x`/`action_toggle_group` in `KanbanApp.BINDINGS`. Report the grep hit count,
  never a silent zero-match.
- **Glyph fidelity:** each glyph/colour pair in the new legend matches
  `followup_kinds.py` `FOLLOWUP_KINDS` exactly, including `▤` grey `#808080` and
  the `·` unknown fallback. Diff the transcribed table against the dict.
- **Phase strings:** every phase string documented (`PLAN`, `IMPLEMENT`,
  `POSTIMPL`, ` ⏸`, `unknown (rec off)`, `unknown (ledger)`, `unknown ⏸`,
  `phase: ` prefix) appears in `workflow_phase.py`.
- **`boardgroup` reaches its website surfaces:** grep `task-format.md` and both
  board pages explicitly and report per-file hit counts.
- **No stale claim survives:** grep the minimonitor page for the "one thing …
  that *does* change" wording and confirm it is gone.
- **Build:** `cd website && hugo build --gc --minify` succeeds (Hugo
  v0.164.0+extended confirmed present). Check the output for new WARN lines
  about broken `relref` targets — every cross-link added here is a `relref`.
- **Conventions:** no version-history prose; no passage enumerating agent trees
  where generic phrasing belongs; `diffviewer` not added to any TUI list.
- **Reciprocity:** `t1243_13` and `t1159_4` each name t1504, and t1504 names
  both.

## Out of scope

- Gaps 3 and 4 (deferred to `t1159_4`, Phase 6).
- `G`, group formation, block moves, membership commands (`t1243_13`).
- `boardgroup`'s seed / `AGENTS.md` / `CLAUDE.md` / `.codex` / `.opencode`
  mirrors (`t1243_13` section B).
- An `aitask-gate-template` page, and the wider gates concepts/workflows sweep
  (`t635_18`).

## Post-implementation

Standard **Step 9** cleanup applies: no worktree was created (current-branch
profile), so there is no branch to merge — the merge target recorded in this
plan's header is `main`, the branch the work lands on directly. Step 9 then runs
the `risk_evaluated` gate (this task's only active gate) and archives t1504 with
its plan. The two task files edited in Phases 2 and 6 belong to **other** tasks
and are not archived here.

## Risk

### Code-health risk: low

- Documentation-only: no source file is modified, so no runtime behavior can
  regress. The four task-file edits are additive prose. · severity: low · → mitigation: none needed
- A concurrent session holds `t1159_3` in `Implementing` and the working tree
  already carries unrelated uncommitted changes (`stale_lock.sh`, gate/test
  files). A broad `git add` would sweep another session's work into this
  commit. · severity: medium · → mitigation: inline pre-phase commit_only_named_paths

### Goal-achievement risk: medium

- Board groups are half-shipped. Prose written now for the shipped half could be
  contradicted by `t1243_11`/`t1243_12` — most sharply "how do I put a task in a
  group", which becomes an in-board command. · severity: medium · → mitigation: none needed (bounded by Scope decision 1: the how-to covers only reading, collapsing and field-based membership, and Phase 2 hands the in-board commands to `t1243_13`)
- Ten doc surfaces transcribe values from source (glyph/colour pairs, phase
  strings, the header format). A transcription slip produces a page that is
  confidently wrong, which is worse than the current silence. · severity: medium · → mitigation: inline post-phase verify_transcribed_value_sets

### Planned mitigations
- timing: pre-phase | name: commit_only_named_paths | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — concurrent-session git contamination | desc: Snapshot the pre-existing dirty tree and commit only this plan's named paths by path, never by index.
- timing: post-phase | name: verify_transcribed_value_sets | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — transcription slip in the documented value sets | desc: Run the glyph, phase-string, binding and header-format fidelity checks as commands that can fail, reporting each hit count.

**Dropped at design time:** `followup_glyph_doc_drift_guard` (an "after" task
adding a test pinning the docs glyph table to `FOLLOWUP_KINDS`) — proposed and
declined; the inline post-phase check covers this task's own correctness, and no
standing guard is added.

**Reassessment after inlining:** code-health stays **low** (both additions are
process steps, not code). Goal-achievement stays **medium** — the post-phase
check removes the transcription risk, but the half-shipped-groups exposure is
inherent to the scope decision rather than something a check can retire.

## Final Implementation Notes

- **Actual work done:** All six phases executed as planned. Four of the six
  documented gaps were written (1 partial, 2, 5, 6); gaps 3 and 4 were deferred
  to `t1159_4` per the confirmed scope decision. Nine website pages modified and
  two created (142 insertions), plus three task files edited for the scope
  handovers. Concretely:
  - **Gap 1 (partial):** `boardgroup` row in `development/task-format.md`; in
    `board/reference.md` a second `x` row (group-header context), a new "Group
    Header Anatomy" block, a `boardgroup` row in Task Metadata Fields, a third
    bullet in Board Data Fields, and `board_config.local.json` in Configuration
    Files; in `board/how-to.md` a new "How to Group Tasks in a Column" section.
  - **Gap 2:** merged gate+phase row bullet, a six-row phase-value table and the
    narrow-width shed order in `minimonitor/how-to.md`; a comparison row in
    `minimonitor/_index.md`; a status-row bullet in `monitor/how-to.md`; a new
    "Agent Card Status Row" section in `monitor/reference.md`.
  - **Gap 5:** "Follow-up Provenance Glyphs" legend in `board/reference.md`,
    the glyph added to the card diagram, plus the roll-up and ghost-card rules.
  - **Gap 6:** `skills/aitask-run-gates.md` (weight 16) and
    `skills/aitask-gate-docs-updated.md` (weight 17), a new "Gates" category in
    `skills/_index.md`, and a reciprocal callout in `commands/gates.md`.

- **Deviations from plan:** None material. One planned target did not exist:
  the gap text pointed at card-anatomy prose in `board/how-to.md` for the
  follow-up glyph, but that page has no card-anatomy section — the content lives
  entirely in `board/reference.md`, so Phase 4 landed there alone (the plan had
  already anticipated this).

- **Issues encountered:**
  - **A stale claim in shipped docs**, not listed in the task:
    `minimonitor/how-to.md` asserted "The one thing on the pinned card that
    *does* change is its prioritized mark". t1420 made that untrue — the
    advisory phase repaints there too. Rewritten to state both live elements and
    to record that the panel deliberately carries the phase but *not* the gate
    summary that shares that line on the list rows.
  - **A verification command that was wrong, not the content.** The first
    anchor-existence check grepped for `id="…"` and reported zero hits for every
    anchor. Hugo's `--minify` emits unquoted attributes (`<h3
    id=how-to-group-tasks-in-a-column>`), so the check was inert. Re-run against
    the emitted form: all 8 anchors PASS. Worth remembering — a zero-match from
    a grep is only evidence once the grep is known to match something.

- **Key decisions:**
  - **Three of six gaps had pre-existing owner tasks.** Rather than writing all
    six, each was routed: gap 1 written as the shipped half with `t1243_13`
    narrowed (the t1432 precedent); gaps 3+4 deferred wholesale to `t1159_4`,
    which was blocked only on the then-`Implementing` `t1159_3`; gap 6 written
    as the two user-invocable skill pages with the wider sweep left to
    `t635_18`.
  - **`aitask-gate-template` deliberately left off the site.** It has no
    invocation syntax and reads as an authoring scaffold, unlike every other
    documented skill.
  - **`boardgroup`'s non-website surfaces were not swept.** The gap named
    `task-format.md`; the seed / `AGENTS.md` / `CLAUDE.md` / `.codex` /
    `.opencode` mirrors are section B of `t1243_13` and need an `ait setup`
    regeneration that does not belong in a docs-gap task. Stated explicitly in
    both task files.
  - **Reciprocal links written in both directions** for both handovers, so
    neither deferral can be lost.

- **Verification results:**
  - Glyph table vs `FOLLOWUP_KINDS`: **9/9 rows match**. The check was
    negative-controlled — a single injected colour flip (`Gray`→`Cyan` on
    `docs_gap`) was correctly caught, so the pass is not vacuous.
  - Phase strings: all 7 found in `workflow_phase.py` (hits 5/2/3/1/1/1/4).
  - `Binding("x"` count: exactly **2** (`toggle_children`, `toggle_group`).
  - Group header format matched `GroupHeader._label` (glyphs at :2727, match
    badge at :2732).
  - `boardgroup` hit counts: task-format 1, board/reference 3, board/how-to 3.
  - Stale pinned-card wording: **0 hits** remaining.
  - `diffviewer`: not introduced anywhere.
  - `hugo build --gc --minify`: **RC=0**, 235 pages. The two WARN lines are
    pre-existing theme deprecations (`.Language.LanguageDirection`,
    `.Site.AllPages`), unrelated to this change. All 8 new cross-link anchors
    resolve in the built HTML.

- **Upstream defects identified:** None.
