---
Task: t1432_docs_gaps_since_v0_30_0.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# t1432 — Documentation gaps since v0.30.0

## Context

`/aitask-docs-gap` scanned the `v0.30.0..HEAD` window and found five shipped
changes whose user-facing documentation never landed. Confirmed against the
shipping commits — of the six commits named in the task, only two touched
`website/` at all:

| Commit | Feature | website/ touched |
|---|---|---|
| `29ad1ab78` | board multi-select marking (t1243_6) | none |
| `8b0e63a3e` | board bulk move-to-column (t1243_7) | none |
| `e2db6e3f6` | concern-picker unparsed view (t1293) | minimonitor/how-to.md only |
| `af3111dd9` | minimonitor other-pane section (t1382) | none |
| `4f6c0b319` | parallel test lane (t1354_3) | setup-install.md one-liner |
| `07e16b81a` | load-aware worker default (t1354_4) | none |

Two of these are worse than missing: `minimonitor/_index.md` and
`minimonitor/how-to.md` currently assert the **opposite** of shipped behavior.
The outcome is that every page a user would consult for these features either
omits them or misleads.

Every claim written below was verified against source, not against the task
text — which turned out to be stale in one place (see "Corrections" ).

## Scope decisions (confirmed with the user)

1. **Board docs are written here**, even though the still-`Ready`
   `aitasks/t1243/t1243_13_documentation.md` also scopes them. That task is
   `depends: [t1243_12]` and the whole group series (t1243_8…12) is
   unimplemented, so it cannot run for a while; marking and bulk-move ship
   today. After writing, `t1243_13` is narrowed to the group work with a
   cross-link back to t1432.
2. **`monitor/how-to.md:32-36` is corrected here.** It claims the pane list
   renders three categories including **TUIs**. Source disagrees:
   `monitor_app.py:1574-1577` appends only `AGENT` and `OTHER`, and
   `_rebuild_pane_list` mounts exactly two headers (`CODE AGENTS (N)` at
   `:1257`, `OTHER (N)` at `:1663`). TUI panes are classified but never
   rendered. This is load-bearing for gap 4: the minimonitor comparison row
   `Shows TUIs and other panes | Yes | No` is wrong in **both** columns, so
   fixing minimonitor forces a correct statement about monitor.

## Corrections to the task's own text

Gap 2 asserts `Binding("m", "move_to_column", "Move to Col", show=False)` and
tells us to document that `m` is "deliberately hidden from the footer" with
discovery via `?` and the palette. That is no longer true: `f8a4d7614` (t1418,
multi-row adaptive footer) removed the `show=False`, and
`aitask_board.py:6176` is now a plain `Binding("m", "move_to_column", "Move to
Col")` — footer-visible, like `Space` at `:6167`. Phase 6 rewrites that gap
paragraph in the task file so the acceptance criteria match reality rather than
silently deviating from them.

---

### Pre-phase (risk mitigations)

**verify-strings-at-source** — before writing any user-visible string, glyph,
binding label or threshold into a doc page, read it directly from the source
file named in that phase and confirm it verbatim. The `show=False` correction
above is the proof this is necessary: the task text was written from a plan,
and the plan aged out of agreement with the code. Applies to every phase; the
per-phase anchors below name exactly what to re-read.

**verify-the-verifier** — every grep in the Verification section was run
against the pre-change tree and its exit status recorded there, so a check that
passes vacuously (or errors with exit 2) is caught before it is trusted. Any
assertion added during implementation gets the same treatment; assert on
location and presence rather than on a pinned occurrence count, which breaks
whenever correct prose names a knob twice.

---

## Phase 1 — Board marking and bulk move (gaps 1, 2)

Source of truth: `.aitask-scripts/board/aitask_board.py`.

### 1a. `website/content/docs/tuis/board/reference.md`

Add two rows to the `#### Task Operations` table (lines 42–62), matching its
`| Key | Action | Context |` shape and its existing conditional-context idiom
(`Board (hidden in In-Flight and By-Trail views)` at line 57):

- `Space` → "Mark / unmark the focused task (`☑` / `☐`)", context
  `Board (parent cards only; hidden in In-Flight, By-Topic and By-Trail views)`.
  Place next to `x` (line 53), the other per-card toggle.
- `m` → "Move the marked task(s) — or the focused card — to a column", same
  context string. Place with the movement block (lines 46–51).

Both are `show=True` and gated by `check_action` (`:6400-6422`), which returns
`False` in the three derived views so the footer hides them.

Add the two palette entries to the **Modal Dialogs Reference** table (lines
363–380), following its `Command palette "…"` trigger idiom:

- **Move Task Select** — trigger `m` with tasks marked / command palette
  "Move Tasks to Column"; purpose: review which marked tasks will move before
  choosing a destination.
- **Column Select (Move to)** — trigger: after the review step, or `m` on a
  single focused card; purpose: pick the destination column.

Add the mark glyph to the **Task Card Anatomy** ASCII diagram (lines 88–98) —
the title row becomes `│ ☐ t47 *  playlists support …` with an annotation
`← Mark (☑ marked / ☐ unmarked)`.

### 1b. `website/content/docs/tuis/board/_index.md`

In the card-anatomy bullet list ("From top to bottom, a card shows:"), add a
first bullet for the mark glyph — always present on parent cards, `☑` when
marked (bold yellow), `☐` when not, so rows never shift.

### 1c. `website/content/docs/tuis/board/how-to.md`

Two new `###` sections immediately after "How to Organize Tasks into Columns"
(ends line 27) and before "How to Customize Columns" (line 29), so
marking → bulk move reads as one pair adjacent to the single-card move docs.

**How to Mark Tasks** — `Space` toggles the mark on the focused parent card.
Cover: the always-on glyph (`☑`/`☐`, marked cards bold); parent-only, with the
verbatim refusal `Child tasks move with their parent — mark the parent
instead.`; marking is unavailable in the In-Flight, By-Topic and By-Trail views
(the key is hidden from the footer there); **marks survive a text search or a
Git/Type add-on toggle, so a marked card can be off-screen**, but switching the
base view clears them; and that a marked task which disappears on refresh is
dropped with a warning (`Unmarked N task(s) no longer on the board: …`) rather
than silently. Mention "Clear Selection" in the palette as the way to unmark
everything.

**How to Move Several Tasks at Once** — `m`. Cover the flow: mark cards → `m` →
review list → pick destination. Specifics to state:

- With nothing marked, `m` acts on the focused card and skips the review.
- With marks, the review **always** runs, because a marked card may be hidden
  by the active filter. Rows read `[Backlog] t47 playlists support` — source
  column, task number, title — in rendered board order; every row starts
  ticked; `Space` toggles, `Enter` confirms, `Esc` cancels.
- The destination list omits collapsed columns and, when the whole selection
  already sits in one column, that column. When nothing is left it says so:
  `Nowhere to move to — every other column is collapsed, and the selection
  already sits where it is.`
- Child cards refuse: `Child tasks move with their parent — move the parent
  instead.`
- Moved tasks land at the bottom of the destination in the reviewed order;
  focus follows the last one.

Also add a `Bulk move` row to the how-to's 4-column
`| Operation | Keyboard | Mouse | Command palette |` matrix (lines 35–42),
since that matrix is the closest thing the board docs have to a palette
listing.

## Phase 2 — Narrow `t1243_13` (forward half of the scope link)

Edit `aitasks/t1243/t1243_13_documentation.md` section A ("Board feature
docs"): delete the **Marking** and **Bulk move** bullets, then add this line
immediately below the remaining bullets:

> Marking (`space`, `☑`/`☐`) and bulk move-to-column (`m`) were documented by
> **t1432**; this child covers only task groups, `G`, the group palette
> entries, `x`-on-header, and the `boardgroup` frontmatter surfaces.

The reciprocal half lives in Phase 6, and **both task files land in one
`./ait git` commit** described there — do not commit this file on its own, or a
failure between the two phases leaves a one-way reference.

## Phase 3 — Monitor concern-picker parity (gap 3) + category fix

Source of truth: `.aitask-scripts/monitor/monitor_shared.py`, `monitor_app.py`.

### 3a. `website/content/docs/tuis/monitor/how-to.md`

In "How to Pick Shadow Concerns" (lines 184–200), insert two paragraphs after
line 194 (the paragraph that already introduces the unparsed-lines warning) and
before line 196 — the same position they occupy on the minimonitor page.

Adapt minimonitor's wording to monitor's conventions: "the selected agent" /
"the pane list", not "the followed agent"; and **do not** carry over "narrow
companion panes". The width tier is keyed on the picker's own measured width
(`_apply_width_tier` at `monitor_shared.py:1635-1654` reads `self.size.width`,
explicitly *not* the caller's `narrow` hint), so it applies to a full monitor
running in a narrow terminal. Phrase it that way.

Content to state: **u** opens a read-only view of the exact marker lines the
parser could not use plus the raw block they came from; when *nothing* parsed
there is no checklist to hang the warning on, so that view opens straight away;
`q` / `Esc` returns to the checklist with ticks intact. Then: at 30 columns and
below the picker drops its OK/Cancel buttons for a compact key hint (`Enter`
confirms, `Esc` cancels); 24 columns is the narrowest supported width.

### 3b. `website/content/docs/tuis/monitor/reference.md`

Extend the `c` row (line 35) with the same parenthetical minimonitor carries:
`(inside the picker, `u` shows any lines that could not be parsed)`. Keep the
3-column `| Key | Action | Context |` shape — the existing `Pane list zone`
context is unchanged.

### 3c. `website/content/docs/tuis/monitor/how-to.md` — category correction

Rewrite lines 32–36. The pane list renders **two** sections, `CODE AGENTS (N)`
and `OTHER (N)`. Keep the agent-prefix explanation. State that windows matching
the configured TUI names are classified as TUIs and are **not** listed, and
that companion panes (minimonitor, shadow) never appear either. Do not touch
`monitor/reference.md`'s "Pane Classification" table (lines 77–85) — it
describes classification, which is accurate as written.

## Phase 4 — Minimonitor corrections (gap 4)

Source of truth: `.aitask-scripts/monitor/minimonitor_app.py`,
`monitor_core.py:1497-1505`.

### 4a. `website/content/docs/tuis/minimonitor/_index.md`

- **Line 10** — drop "no TUI/other pane categories" from the intro. Minimonitor
  does list non-agent panes. Keep "no preview panel" (still true). Re-state the
  contrast as: agents first, other panes in their own compact section, no
  preview.
- **Line 30** — replace the row `Shows TUIs and other panes | Yes | No`. Split
  into an accurate row, e.g. `Shows non-agent panes` → monitor: `Yes, under an
  OTHER (N) header`; minimonitor: `Yes, under a ── other (n) ── header`. TUI
  windows are listed by neither.
- **Line 71** — "For a full dashboard with previews, pane classification, and
  kill/switch controls" — reword so "pane classification" no longer reads as a
  monitor-only capability; previews and the kill/switch controls still are.

### 4b. `website/content/docs/tuis/minimonitor/how-to.md`

- **Line 37** — delete "TUIs, shells, and other panes are deliberately filtered
  out". Replace with: agents come first; any non-agent pane in view appears
  under a bold `── other (n) ──` header (lowercase, unlike monitor's
  `OTHER (N)`); TUI windows and companion panes (shadow, other minimonitors)
  are not listed.
- After the agent-card anatomy bullets (lines 39–45), add a short paragraph for
  the reduced **other** row: `○ name  cmd` — no status dot, no mark, no task
  title, no gate line, because none of those mean anything for a
  non-agent pane (`_other_card_text`, `minimonitor_app.py:768-806`). Session
  dividers still apply inside each section.
- **Lines 110 and 172** — both say the pinned card sits under `── this agent
  ──`. Make the header conditional: it reads `── this agent ──` when the
  followed pane is classified as an agent, and `── this window ──` when it is
  not, so an uncategorized window is legible rather than invisible.
- **Line 176** — currently correct but incomplete. Keep the "no mark at all"
  statement (`_own_mark_state = None` for a non-agent window) and add that the
  panel *is* still built for such a window, while `k` / `n` / `e` / `E` / `I`
  keep refusing — that refusal is the point of renaming a window off the
  prefix. Note the panel is one-shot: renaming a window *after* it is built
  does not change the header or name; only the mark glyph repaints per tick.

## Phase 5 — Parallel test lane (gap 5)

Source of truth: `tests/run_all_python_tests.sh`, `.aitask-scripts/aitask_setup.sh`.

Home is `website/content/docs/development/_index.md` "Testing Changes" (lines
168–178), which today lists only shell checks and does not mention the Python
suite at all. `setup-install.md:31-34` already covers `--with-dev` adequately,
so it gains only a cross-link — no duplicated prose.

### 5a. `setup-install.md` cross-link (explicit edit)

Append to the end of the `--with-dev` bullet at **line 34**, after
"…without them":

> ` — see [Testing Changes]({{< relref "/docs/development" >}}#testing-changes)
> for the lane's environment knobs and how to opt out`

`{{< relref "/docs/development" >}}` is the established form for this page
(`content/docs/commands/crew.md:246`,
`content/docs/development/skills/_index.md:34`); the `#testing-changes` anchor
is Hugo's slug for the existing `## Testing Changes` heading. Hugo fails the
build on an unresolved relref, so Verification step 1 catches a typo here.

### 5b. Rewrite "Testing Changes"

Cover, in this order:

1. The existing shell one-liners (unchanged).
2. Bash tests: run individually, no runner.
3. The Python suite: `bash tests/run_all_python_tests.sh`, narrowed with
   `--test-dir <dir>`. Two backends — pytest when importable, else
   `unittest discover`. **Read only the last line for the verdict**:
   `PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`. It goes to stderr, and
   piping discards the exit status — use `set -o pipefail` or `${PIPESTATUS[0]}`.
4. An `### Environment Variables` H3 with the house 3-column table
   (`| Variable | Default | Purpose |`, matching `board/reference.md:417-425`):

   - `AIT_TEST_WORKERS` — default: auto (4 or 2) — worker count for the
     parallel lane. The default is load-aware: 4 when the box has ≥4 CPUs and
     1-minute load ≤ cpus/2, otherwise 2. An explicit value always wins.
   - `AIT_TEST_PARALLEL` — default `1` — set to `0` to run the suite serially.

   Then a bolded follow-up paragraph below the table (house style keeps nuance
   out of cells). Be precise about **what actually switches the lane on**, and
   keep installation and runtime condition distinct:

   - The runner resolves its interpreter through `require_ait_python` — the
     `ait setup` venv at `~/.aitask/venv/`, not bare `python3`
     (`run_all_python_tests.sh:62`). It then picks pytest when `import pytest`
     succeeds there, and enables the parallel lane when `import xdist` also
     succeeds (`:149`, `:160`).
   - `ait setup --with-dev` is the **supported way to install** `pytest` and
     `pytest-xdist` into that venv, and it records `~/.aitask/dev_tier` so later
     plain `ait setup` runs revalidate and repair the tier.
   - The runner **never reads that marker**. Phrase the lane's condition as
     "whenever `pytest-xdist` is importable by the suite's interpreter", so a
     contributor who installed the packages into that venv another way is not
     told their setup is unsupported or broken. What removing the marker costs
     is setup's revalidation and repair — not the lane.
   - Consequently the two opt-outs are **independent, not two halves of one
     action**: `AIT_TEST_PARALLEL=0` disables the lane (leaving the packages
     installed); `rm ~/.aitask/dev_tier` stops `ait setup` reinstalling or
     repairing the tier (leaving the lane running). Fully removing it means
     both, plus uninstalling the two packages from the venv.
   - A positional test path *widens* the run and disables the lane
     (`has_path_selector`, `:99-108`, `:161-164`), so use `--test-dir` to
     narrow.

Do **not** document `AIT_TEST_NCPU` / `AIT_TEST_LOADAVG` — `run_all_python_tests.sh:123`
marks them explicitly as test seams, not user knobs. Per the current-state-only
convention, carry the 24-core measurements if useful but drop the `(t1354_4)`
citation and every other task-ID provenance marker that appears in `CLAUDE.md`
and the source comments.

## Phase 6 — Task-file edits (reciprocal half + stale gap text)

Two edits to `aitasks/t1432_docs_gaps_since_v0_30_0.md`:

**6a — stale gap text.** Rewrite the "What shipped" / "What to write" sentences
of the **Gap: Board bulk move-to-column command** section so they describe `m`
as footer-visible (label `Move to Col`, hidden only in the In-Flight, By-Topic
and By-Trail views via `check_action`), and delete the instruction to document
"that it is not shown in the footer and why discovery is via `?` / the palette".

**6b — reciprocal scope pointer** (the other half of Phase 2). Append to that
same board bulk-move section:

> Scope: this task documents board marking and bulk move; the remaining board
> documentation (task groups, `G`, `x`-on-header, `boardgroup` frontmatter
> surfaces) stays with **t1243_13**, which was narrowed to match.

**Commit both task files together**, this one and Phase 2's, in a single
`./ait git` commit so the two pointers can never land apart:

```bash
./ait git add aitasks/t1432_docs_gaps_since_v0_30_0.md \
              aitasks/t1243/t1243_13_documentation.md
./ait git commit -m "ait: Narrow t1243_13 scope and correct t1432 gap text"
```

---

## Verification

1. **Build the site** — `cd website && hugo build --gc --minify`. Catches a
   malformed `{{< relref >}}` (Hugo fails the build on an unresolved ref),
   which is the one way these edits can break something.
2. **No stale-claim residue** — grep the touched pages for the corrected
   phrases; each must return nothing:
   `grep -rn 'no TUI/other pane categories\|Shows TUIs and other panes\|deliberately filtered out\|three categories' website/content/docs/tuis/`
3. **Knob accuracy.** Assertions are on *location and presence*, never on a
   pinned occurrence count — the follow-up paragraph legitimately names
   `AIT_TEST_PARALLEL=0` a second time, so a "exactly once" check would fail on
   correct content. All three currently exit 1 (verified pre-change):

   ```bash
   # test seams must stay undocumented — expect no output, exit 1
   grep -rn 'AIT_TEST_NCPU\|AIT_TEST_LOADAVG' website/

   # both knobs documented, and confined to the development page —
   # expect exactly: website/content/docs/development/_index.md
   grep -rl 'AIT_TEST_WORKERS\|AIT_TEST_PARALLEL' website/content/docs/

   # each knob is actually present there — expect a non-zero count for both
   grep -c 'AIT_TEST_WORKERS'  website/content/docs/development/_index.md
   grep -c 'AIT_TEST_PARALLEL' website/content/docs/development/_index.md
   ```

   (`grep` exits 1 for "no match" and 2 for a real error — treat 2 as a broken
   check, not a passing one.)
4. **Cross-links resolve** — `grep -n 'relref "/docs/development"'
   website/content/docs/commands/setup-install.md` returns the Phase 5a line;
   `grep -n 't1432' aitasks/t1243/t1243_13_documentation.md` and
   `grep -n 't1243_13' aitasks/t1432_docs_gaps_since_v0_30_0.md` each return
   their pointer, proving the link is bidirectional; `git show --stat HEAD`
   on the task-file commit lists **both** task files.
5. **Spot-check rendering** — `cd website && ./serve.sh`, then read the board
   how-to, monitor how-to, minimonitor index/how-to and development pages to
   confirm tables render and the new sections sit where intended.
6. Step 9 (Post-Implementation) handles cleanup, archival and merge.

## Out of scope

- `minimonitor/reference.md` — does not exist; minimonitor's keybinding table
  lives inside `how-to.md`. Not creating one here.
- Task groups, `G`, `x`-on-header, `boardgroup` — unshipped; they stay with
  `t1243_13`.
- `monitor/reference.md` "Pane Classification" (lines 77–85) — accurate as
  written.
- `ait setup --help` — `aitask_setup.sh` has no help handler at all, so there
  is no CLI help text to update. Adding one is a separate change.

---

## Risk

### Code-health risk: low
- Documentation-only edits to markdown under `website/`, plus two task-file
  edits. No executable code, no framework script, no test touched — the blast
  radius is the rendered site. · severity: low · → mitigation: inline pre-phase verify-strings-at-source
- A malformed `{{< relref >}}` shortcode would break the Hugo build rather than
  degrade silently. · severity: low · → mitigation: Verification step 1 (`hugo build`)

### Goal-achievement risk: medium
- The task's own gap descriptions are derived from plans and have already been
  shown to drift from the code (`m`'s `show=False` was removed by t1418). Any
  other paragraph written from the task text rather than from source risks
  shipping a second wrong claim. · severity: medium · → mitigation: inline pre-phase verify-strings-at-source
- Several board internals below were established via subagent report rather
  than direct reading, so line anchors and verbatim strings are second-hand
  ground truth. · severity: medium · → mitigation: inline pre-phase verify-strings-at-source
- Correcting `minimonitor/_index.md`'s comparison row requires a true statement
  about `ait monitor`, which pulled a second page into scope. If monitor's
  rendering were to differ from the two-header reading, both pages would land
  wrong together. Verified directly at `monitor_app.py:1574-1577` and
  `:1600-1665`. · severity: low · → mitigation: none needed — verified at source

---

## Final Implementation Notes

- **Actual work done:** All five documented gaps landed, plus the two approved
  scope additions. Nine files under `website/` changed (137 insertions, 15
  deletions):
  - *Gap 1 (board marking)* — `board/reference.md`: `Space` row in Task
    Operations, mark glyph added to the Task Card Anatomy diagram;
    `board/_index.md`: a leading **Mark** bullet in the card-anatomy list;
    `board/how-to.md`: new "How to Mark Tasks" section.
  - *Gap 2 (board bulk move)* — `board/reference.md`: `m` row, plus **Move
    Tasks to Column** and **Column Select (Move to)** rows in Modal Dialogs
    Reference; `board/how-to.md`: new "How to Move Several Tasks at Once"
    section and a bulk-move row in the 4-column palette matrix.
  - *Gap 3 (monitor concern picker)* — `monitor/how-to.md`: the "Seeing what
    was lost" and narrow-width paragraphs, adapted to monitor's wording;
    `monitor/reference.md`: `c` row extended with the `u` parenthetical.
  - *Gap 4 (minimonitor)* — `minimonitor/_index.md`: intro clause, comparison
    row, a new TUI/companion-pane sentence, and the line-71 reword;
    `minimonitor/how-to.md`: list intro, an "other"-card anatomy paragraph,
    the conditional pinned-card header, and the renamed-window paragraph.
  - *Gap 5 (test lane)* — `development/_index.md`: new "Bash tests" and
    "Python tests" subsections, an `#### Environment Variables` table and three
    follow-up paragraphs; `setup-install.md`: cross-link on the `--with-dev`
    bullet.
  - *Approved addition* — `monitor/how-to.md` lines 32–36 rewritten from three
    categories to the two rendered sections.
  - *Task files (separate commit `e6e441e90`)* — `t1243_13` narrowed,
    `t1432` gap text corrected, both with reciprocal scope pointers.

- **Deviations from plan:** None in substance. Two small judgement calls during
  execution: (1) the plan proposed splitting the minimonitor comparison row and
  noting the TUI exclusion "after the table" — implemented as a dedicated
  sentence above the existing "The two can coexist…" paragraph, which reads
  better than a trailing note; (2) `how-to.md:180` (the marking section's
  `── this agent ──` reference) was left unchanged after checking the source:
  `_own_mark_state` is `None` for a non-agent window, so marking genuinely only
  applies to the agent case and that sentence is already correct. The header
  variant is documented at its own site (the `I` section) and in the
  renamed-window paragraph instead.

- **Issues encountered:**
  - *Stale acceptance criteria.* The task's Gap 2 text specified
    `Binding("m", …, show=False)` and asked for prose explaining why `m` is
    hidden from the footer. Source disagreed: `f8a4d7614` (t1418) removed
    `show=False`, and `aitask_board.py:6176` carries a source comment saying so
    explicitly. Documented the current state and rewrote the task's gap
    paragraph rather than deviating silently.
  - *Working directory persistence.* `cd website && hugo build` left the shell
    in `website/`, which made a subsequent `ls -d website/public` and a
    `aitask_gate.sh` invocation resolve against the wrong root. The `public/`
    check was re-run from the repo root: the directory does exist after a build
    and is gitignored, so nothing untracked reaches a commit.
  - *Concurrent session.* An unrelated session had `trail_gather.py`, the
    `aitask-trail` skill template, three trail goldens, `test_trail_gather.py`
    and `aidocs/implementation_trail_design.md` modified in the worktree
    throughout. The index was verified empty before staging, and only the nine
    website paths were staged explicitly.

- **Key decisions:**
  - *Board docs written here rather than deferred to `t1243_13`* (user-confirmed).
    That child is `depends: [t1243_12]` behind an unimplemented group series, so
    deferring would have left shipped features undocumented indefinitely. It was
    narrowed in the same session, with pointers in both directions committed
    together so the halves cannot separate.
  - *`monitor/how-to.md` category correction pulled into scope* (user-confirmed).
    Writing an accurate minimonitor comparison row forces a claim about monitor;
    `monitor_app.py:1574-1577` appends only `AGENT` and `OTHER`, so the page's
    "three categories" claim was false and would have contradicted the very row
    being fixed. `monitor/reference.md`'s Pane Classification table was left
    alone — it describes classification, not rendering, and is accurate.
  - *Test-lane knobs on `development/_index.md`, not `setup-install.md`.* The
    command page already covered `--with-dev` adequately; duplicating the knobs
    there would have created a second source to drift. It gained a cross-link.
  - *Installation path vs runtime condition kept distinct.* The lane activates
    on `import xdist` in the resolved venv interpreter and never reads
    `~/.aitask/dev_tier`, so the docs say "whenever `pytest-xdist` is importable"
    and present the two opt-outs as independent actions. `AIT_TEST_NCPU` /
    `AIT_TEST_LOADAVG` are marked test seams in source and stay undocumented.
  - *Verification asserts location and presence, not occurrence counts.* A
    pinned "exactly once" check would have failed on correct content —
    `AIT_TEST_PARALLEL` legitimately appears twice on the page (confirmed: the
    final count is 2).

- **Upstream defects identified:** None.

  The `monitor/how-to.md` three-categories error was a documentation defect, not
  a code defect, and was fixed within this task rather than deferred.

## Verification results

| Check | Result |
|---|---|
| `hugo build --gc --minify` | PASS — 232 pages, exit 0; only pre-existing `.Language.LanguageDirection` / `.Site.AllPages` deprecation warnings. Also proves the new relref resolves, since Hugo fails the build on an unresolved ref. |
| Stale-claim grep across `tuis/` | PASS — exit 1, no matches |
| Test seams absent from `website/` | PASS — exit 1, no matches |
| Knobs confined to one page | PASS — only `website/content/docs/development/_index.md` |
| Knob presence | PASS — `AIT_TEST_WORKERS` ×1, `AIT_TEST_PARALLEL` ×2 |
| Bidirectional task pointers | PASS — `t1243_13:43` → t1432, `t1432:36` → t1243_13; commit `e6e441e90` lists both files |
| `setup-install.md` cross-link | PASS — present at line 34 |
