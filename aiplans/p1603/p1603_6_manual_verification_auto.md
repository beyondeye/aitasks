---
task: t1603_6
parent: t1603
type: manual_verification
strategy: autonomous
created_at: 2026-09-02
---

# Auto-Verification Execution Record — t1603_6

Retroactive record of the autonomous auto-verification run for
`t1603_6` (manual verification of t1603_1…t1603_5: the board's
deferred-plan marker, workflow-phase model, Planned in-flight lane,
expanded gate surface, and website docs).

## Method

All render-level claims were verified **in a real terminal**, not
headless: a throwaway tmux server on a private socket
(`AITASKS_TMUX_SOCKET`) running `./ait board` against a **synthetic
fixture project** (`ait` + a `.aitask-scripts` symlink + its own
`aitasks/` tree), following the isolation pattern of
`tests/test_board_startup_focus_live.py`. No file under the real
repo's `aitasks/` or `aiplans/` was mutated except this task's own
checklist and this plan file.

Collapsible sections are not reachable by `Tab`/arrow in the detail
screen (the screen's single-letter bindings claim those keys), so they
were opened by injecting SGR mouse press/release sequences
(`ESC [ <0;COL;ROW M/m`) into the pane with `tmux send-keys -l`, with
the display column computed from the captured pane accounting for
double-width glyphs.

Fixture tasks (`t9001`–`t9011`) covered: marked / unmarked / blocked+marked
`Ready` tasks; `Implementing` with a pending procedure gate; `Implementing`
with neither ledger nor plan; `Implementing` declaring gates with no ledger;
a rich gate set (pass / skip / fail / stale-signed / profile-filtered); an
all-gates-pass task; a dependency-blocked in-flight task; and a
past-review (`post_impl`) task.

Two fixture facts had to be made **genuine** rather than hand-written,
because the board recomputes an active-gates tuple whose digest does not
validate, and staleness needs a real code-bound witness:

- the fixture was `git init`-ed and committed so `code_digest()` resolves;
- `aitask_gate.sh materialize-active --profile <fixture profile with a
  `rendered_gates` ceiling>` produced a real `active_gates` /
  `active_gates_filtered` tuple;
- `ait gate pass 9006 review_approved` wrote a real witness
  (`code_digest=3a4133a211c98161`), then a tracked source file was changed
  so the digest moved to `d7a30c4a0f61d63e` — making the signature
  genuinely stale.

Without those two steps the "filtered" and "stale" rows silently did not
appear and the checks would have passed vacuously.

## Corroboration

`bash tests/run_all_python_tests.sh` — **PYTHON SUITE: PASSED
(runner=pytest, exit=0)**, 6428 passed / 2 skipped.

## Execution Log

### Items 1, 2, 5 — card badge, seed and clear
- Approach: CLI invocation + live TUI render.
- Action: `./ait update --batch 9002 --plan-approved-at now`;
  `./ait update --batch 9001 --plan-approved-at ""`; board `r` refresh.
- Output: t9002 → `📋 Ready · Planned`; t9001 → `📋 Ready` (qualifier gone),
  rendered side by side in the same column.
- Verdict: pass / pass / pass.

### Item 3 — detail row present
- Action: `Enter` on t9001, mouse-click `Tracking & provenance (1)`.
- Output: `Plan approved: 2026-08-25 10:24`.
- Verdict: pass.

### Item 4 — detail row absent when unmarked
- Output: t9002's detail mounts no `Tracking & provenance` section at all
  (Dependencies → Lock & files); no blank row.
- Verdict: pass.

### Item 6 — blocked task keeps the qualifier
- Output: `🚫 blocked | 📋 Planned` (badge suppressed, `Planned` retained).
- Verdict: pass.

### Item 7 — docs_updated is not "Agent can continue"
- Output: t9004 lands in **Needs your action**, action line
  `needs an attended agent: docs_updated`, chip `needs attended agent · 1/2`.
- Verdict: pass.

### Items 8, 20 — honest degradation
- Output: card chip `implementing`, **no** fraction; detail Gates title
  `Gates` (no `0/2`), first row `No gate ledger — implementing (unknown)`,
  then `· risk_evaluated — pending`, `· tests_pass — pending`.
- Verdict: pass / pass.

### Items 9, 10, 11 — lanes, routing, chips
- Output: `Planned (1) | Needs your action (4) | Agent can continue (2) |
  Blocked (2)` in that order. Planned card offers `[p pick]` only.
  Every card carries a chip, Planned included (`plan approved`).
- Verdict: pass / pass / pass.

### Item 12 — chip fits the lane
- Output: widest chip observed `needs attended agent · 1/2` (26 cols) in a
  40-col card inside the 44-col lane; no wrap or overflow at 200 / 180 / 100
  columns. (Longest possible stem is `needs attended agent`, 20 cols.)
- Verdict: pass.

### Item 13 — narrow terminal
- Action: `resize-window -x 100`, then `Right` ×3.
- Output: the container scrolls horizontally; lanes keep width 44
  (`min_width: 34` never engages, as p1603_3 measured); the Blocked lane
  scrolls fully into view and every card stays legible.
- Verdict: pass.

### Item 14 — wide terminal (DEFERRED)
- Action: swept 176 → 182 columns, counting closed lane boxes on the header
  row.
- Output: each lane box is exactly 44 columns. Four boxes close only at
  **W=180**; at W=176–179 only three close and the Blocked lane is clipped.
  At W≥180 the rendered line caps at 180.
- The item says "`>=176 cols`". p1603_3's own measurement says the four-lane
  span is **181 columns** (`virtual_size == 45*4+1`) and "the view scrolls at
  any width below 181". So the board matches its measured contract and the
  checklist's 176 is a pre-measurement guess.
- Verdict: **defer** — behaviour is correct per the plan, the item's number is
  not; whether to correct the checklist or treat it as a defect is a human call.

### Items 15, 16, 17, 18 — expanded gate surface
- Output (t9006): `▶ Risk (2)` then collapsed `▶ Gates (2/4)`; expanded →
  `awaiting review · 2/4`, `✓ risk_evaluated — passed`,
  `⊘ tests_pass — skipped (not applicable)`, `✗ lint — failed`,
  `⚠ review_approved — pass, signature stale; needs re-sign`,
  `filtered by profile (audit only)`, `· build_verified`.
  The filtered gate is listed last and excluded from the 2/**4** total.
  (t9004 additionally yields `◈ docs_updated — pending; needs attended agent`.)
- Verdict: pass / pass / pass / pass.

### Item 19 — focus return
- Action: opened the detail from t9006, the **second** card in its lane.
- Output: `Escape` returned focus to t9006 (double border), not to the top.
- Verdict: pass.

### Items 21, 22 — website
- Action: `hugo build --gc --minify` (240 pages, clean); `./serve.sh` →
  `curl http://localhost:1313/docs/tuis/board/reference/` → HTTP 200.
- Output: the page carries the `In-Flight Lanes and Workflow Phases` section,
  the four lane titles, the five phase labels and all six gate glyphs; every
  in-page fragment resolves to a real `id=` in the minified HTML.
- Cross-checked verbatim against the running board: lane titles, phase names
  (`plan approved`, `implementing`, `awaiting review`, `needs attended agent`,
  `post-implementation`) and glyphs (`✓ ⊘ · ◈ ✗ ⚠`) all match.
- Verdict: pass / pass.

### Item 23 — arrow-key order
- Output: `Down` walks Priority → Effort → Status → Type → Follow-up,
  unchanged with the Gates section present; sections render in the order
  Risk → Gates → Dependencies & hierarchy → Tracking & provenance →
  Lock & files.
- Verdict: pass.

### Item 24 — kanban parity
- Output: columns with counts and `✎`, cards, `💪` effort, `🏷️` labels,
  `🚫`/`🔗` blocked chips, follow-up glyph `◇`, risk marker `*`; `Space`
  toggles the mark `□ ↔ ✓` in both directions. Only marked cards differ,
  by the intended `· Planned` qualifier.
- Verdict: pass.

## Result

23 pass, 1 defer (item 14), 0 fail.

## Cleanup

- tmux server on the throwaway per-process socket — `kill-server`.
- Fixture project and scratch files under the session scratchpad
  (`fixture/`, `hugo_out/`, `build_fixture.py`, `click.sh`, `serve.log`,
  `served.html`) — removed.
- `hugo server` started by `./serve.sh` — stopped.

## Final Implementation Notes

**Work done.** All 24 checklist items of t1603_6 reached a terminal state:
**24 pass, 0 fail, 0 skip, 0 defer**. No code was changed — this is a
manual-verification task, and every item passed, so no follow-up work was
spawned.

**Issues encountered and resolutions.**

1. *Collapsible sections are not keyboard-reachable in `TaskDetailScreen`.*
   `Tab` and arrow keys never land on a `Collapsible` title: the screen binds
   almost every single letter (`p`, `l`, `u`, `c`, `s`, `r`, `e`, `d`, `n`,
   `v`, …), and `Down` walks only the editable field widgets
   (Priority → Effort → Status → Type → Follow-up) before stopping. Resolved by
   injecting SGR mouse press/release sequences into the pane
   (`tmux send-keys -l $'\e[<0;COL;ROWM'`), computing the display column from
   the captured pane with east-asian-width accounting so double-width emoji do
   not shift the click. **This is the technique to reuse for any future live
   check of a board detail-screen section.**

2. *A hand-written `active_gates` tuple is silently ignored.* The board
   revalidates `active_gates_digest`; a fabricated digest fails, so the board
   recomputes the active set from `gates:` under the governing profile. The
   first fixture attempt therefore showed `build_verified` as an ordinary
   pending gate inside a 3/5 total — items 18 and 17 would have passed
   vacuously against the wrong rows. Resolved by `git init`-ing the fixture and
   using the real writer:
   `aitask_gate.sh materialize-active <id> --profile <profile with a
   rendered_gates ceiling>`.

3. *Staleness needs a real witness and a real digest move.* `stale_signed_gates`
   pre-filters on `_has_stamped_witness` and `code_digest()` returns `None`
   outside a git repo (unverifiable → accept), so a hand-written `.signed` file
   in a non-git fixture produces a clean `pass`. Resolved by
   `ait gate pass 9006 review_approved` (writes the code-bound witness) followed
   by a tracked-source edit that moved the digest
   `3a4133a211c98161` → `d7a30c4a0f61d63e`.

**Item 14 — the one deviation, and its resolution.** The item asserts all four
in-flight lanes are visible without horizontal scrolling at `>=176` columns.
Measured live across 176→182: each lane box is exactly 44 columns and all four
close only at **180 rendered columns**; at 176–179 the Blocked lane is clipped.
p1603_3's own sweep records the four-lane span as **181 columns**
(`virtual_size == 45*4+1`) and states the view scrolls at any width below 181 —
so the board matches its designed and measured contract, and the checklist's
`176` was a pre-measurement guess (4 × 44). Put to the user, who ruled
**"pass — checklist number stale"**: no defect, no follow-up task.

Note for anyone editing this surface: the 180/181-column threshold is recorded
in p1603_3 and now here, but is **not** stated on the website board reference.

**Useful for sibling tasks.** There are none — t1603_6 is the last child of
t1603, and t1603_1…t1603_5 are all archived.
