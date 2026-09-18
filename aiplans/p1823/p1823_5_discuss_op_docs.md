---
Task: t1823_5_discuss_op_docs.md
Parent Task: aitasks/t1823_brainstorm_discuss_proposals_interactive_agent.md
Sibling Tasks: aitasks/t1823/t1823_1_*.md, aitasks/t1823/t1823_2_*.md, aitasks/t1823/t1823_3_*.md, aitasks/t1823/t1823_4_*.md
Archived Sibling Plans: aiplans/archived/p1823/p1823_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-18 12:57
---

# t1823_5 — Website docs for the brainstorm Discuss operation

## Context

t1823_1..4 shipped a **Discuss** row in the `ait brainstorm` Operations dialog. It
launches an interactive, advisory-only (read-only) code agent running the
`aitask-brainstorm-discuss` skill over the cursor node or the space-marked set. The
website does not document it yet; the `codeagent.md` `discuss` row already landed
with t1823_3. This task documents **what shipped**, verified against the source
(not the plans).

Verified facts from the landed code and the archived sibling plans:
- The row is labelled "Discuss" and sits **last** in the Operations dialog. It is
  enabled for any selection size ≥1, including the root node. The dialog only
  opens in init/active, non-read-only sessions (the existing gate).
- It never goes through the wizard. It opens the shared agent-launch dialog (agent/model,
  profile, launch mode). The default is a new tmux window `agent-discuss-<N>`
  (plus minimonitor); without tmux it falls back to a terminal. It creates
  **no node** and no crew agent (nothing on the Running tab). `H` on the row
  shows its help.
- Skill invocation: `/aitask-brainstorm-discuss <task_num> <node_id> [<node_id>...]`,
  with at least one node id. The profile resolver key is `brainstorm-discuss`, and the
  codeagent operation is `discuss`.
- Shortcodes: `>c` (compare in simple words), `>cd` (compare in depth), `>e`
  (explain one proposal simply but fully), `>q` (Q&A), `>f` (structural
  flaw & risk check), `>h` (how a proposal evolved, using lineage), `>?`
  (reprint the menu). The `>` is required. Operands are handles `A`, `B`, … (in argv order)
  or node ids. Plain-language asks also work.
- Fast start: with **two or more** proposals, the skill lists them (handle,
  node id, short title) and shows the menu. With **exactly one** (the common
  cursor-only path), it skips the list and handles. It names the proposal in one
  sentence ("Discussing `<node_id>` — <title>.") and then shows the menu. A node
  whose proposal cannot be found is listed as `(proposal not found)` and left out
  of later requests. It does no upfront analysis;
  other context (node metadata, the task
  file, lineage) is fetched only when a request needs it.
- Availability: `_open_operations_dialog` (`brainstorm_app.py:2875`) refuses
  a read-only session ("Session is read-only — no operations available.") and
  any session whose status is not `init`/`active` (for example paused or finalized).
  In those sessions it shows a warning and the dialog does not open, so Discuss
  is unavailable there too.
- Guardrail: it never edits proposal files, node YAML or session state, and it
  never runs a mutating `ait brainstorm` command.

Rules: `aidocs/framework/documentation_conventions.md`. Pages describe only the current
behavior (no version history), and agent wording stays generic. Do not mention
`diffviewer`. Use `{{< relref "/docs/..." >}}` for internal links.

## Steps

1. **`website/content/docs/tuis/brainstorm/reference.md`**
   - "Operations dialog and wizard" (~:59): add a sentence saying that **Discuss**
     (the last row) skips the wizard and opens the agent-launch dialog instead,
     with a relref link to the new how-to anchor.
   - "Operations and agents" (~:132): add a sentence after the table plus a small
     table or paragraph for **Discuss**. It is an *interactive advisory* agent,
     not a background crew agent. It is not a design operation, creates no node,
     has no badge color, and does not appear on the Running tab. Its model default
     comes from the codeagent `discuss` operation (relref to
     `/docs/commands/codeagent`), not from a `brainstorm-<type>` key. Link to the
     skill page.
2. **`website/content/docs/tuis/brainstorm/how-to.md`**
   - Qualify the intro claim "All operations run background agents" so that it
     excludes Discuss.
   - Add a new `### How to Discuss Proposals with an Agent` section after "How to
     Compare and Synthesize Nodes". It covers:
     0. an **availability note** at the start of the section: Discuss, like every
        operation in the dialog, needs a session that is not read-only and is
        initializing or active. A read-only, paused or finalized session shows a
        warning instead of opening the dialog. Resume a paused session first;
     1. target selection: the cursor node alone, or the marked set (`space`);
     2. `A` → **Discuss** (last row; `H` for help);
     3. the agent dialog: pick the agent/model, profile and launch mode. The default
        is a new tmux window `agent-discuss-<N>`, with a terminal fallback outside tmux;
     4. what the agent shows first. **Both branches**: one proposal is named in
        a single sentence with no handles. Two or more are listed as `A`, `B`, …
        with node id and title. The menu follows in both cases. After that comes a
        shortcode table (`>c`, `>cd`, `>e`, `>q`, `>f`, `>h`, `>?`) with
        notes on plain-language asks and handles vs node ids;
     5. the read-only guarantee (no node, no file change). To act on an insight,
        run Explore/Synthesize yourself.
   - The tmux-integration paragraph can mention switching to the discuss window
     with `j`. Keep this light.
3. **NEW `website/content/docs/skills/aitask-brainstorm-discuss.md`**. Use the
   `aitask-note.md` shape. Frontmatter: title/linkTitle `/aitask-brainstorm-discuss`,
   weight ~110, description, `maturity: [stabilizing]`, `depth: [intermediate]`.
   Sections: intro; Usage (argument block, plus a note that it is normally launched from
   the brainstorm TUI, and that the TUI's Discuss row needs a non-read-only
   init/active session); Step-by-Step (resolve paths → one proposal: a single
   naming sentence, or several: a handle list `A`, `B`, … → menu → wait; also
   the `(proposal not found)` case); Capabilities (shortcode table + the shortcode rules); Context on demand;
   Advisory-only contract; Profiles (the `brainstorm-discuss` key under
   `default_profiles`, relref to execution-profiles `#resolution-order` if that
   anchor exists, otherwise the page); Related (the brainstorm how-to, reference,
   and codeagent).
4. **`website/content/docs/skills/_index.md`**: add a new `### Design` section
   before "Configuration & Reporting" with one row linking `](aitask-brainstorm-discuss/)`
   (the form `tests/test_website_doc_lists.sh` Test 2 requires).
5. **`website/content/docs/tuis/_index.md`** (:25): the brainstorm blurb lists
   operations ("compare and synthesize them"), so add "discuss them with an
   advisory agent".

## Verification

- `cd website && python3 check_links.py --build` passes (mandatory)
- `hugo build --gc --minify` in `website/` succeeds
- `bash tests/test_website_doc_lists.sh` passes
- Offer `python3 check_link_relevance.py` (a report, not a gate)

## Post-implementation

Step 9 of the task workflow (commit, archive t1823_5; t1823_6 manual
verification remains).

## Risk

### Code-health risk: low
None identified. The change is docs-only in four existing pages and one new page, and
the link checker and doc-list test gate it.

### Goal-achievement risk: low
None identified. Every documented behavior was checked against the landed skill
template (including its single-proposal branch) and the
`_open_operations_dialog` availability gate, not only against the plans.
