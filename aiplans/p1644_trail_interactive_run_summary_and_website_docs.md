---
Task: t1644_trail_interactive_run_summary_and_website_docs.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1644 — Trail interactive run summary + website docs

## Context

Implementation trails have two entry points, but only the board one is treated as
real in the product surface.

**The interactive run ends thin.** `## Run summary print` in
`.claude/skills/aitask-trail/SKILL.md.j2:675` is deliberately two lines (depth +
`narrative.overview`), shared by create (2e.5), refresh (3.7) and show (1.4). Its
own rationale is "so the user can decide what to pick next without opening the
board" — but it carries none of the structure the agent just authored, and never
mentions that the artifact has a rich board view.

**The standalone skill was undocumented — and mostly is no longer.** While this
plan was being written, `t1210_6` landed (commit `27102e76e`) with
`website/content/docs/skills/aitask-trail.md`, the `_index.md` row, the
`codeagent.md` `trail` operation row, and `docs/workflows/implementation-trails.md`.
Part B is therefore rescoped to the two acceptance criteria that commit did not
close — the §By-Trail sentence in `docs/tuis/board/reference.md:246` still names
the skill as bare code rather than a link, and the page does not mention
conversational invocation — plus the docs the enriched summary itself makes
necessary.

Outcome: someone who invokes `/aitask-trail` conversationally gets a prose blurb
and is never told the artifact is viewable on the board.

## Decisions taken during planning

These answer the task's "decide explicitly" constraints.

**1. The recap is compact, not a re-render.** A real trail in this repo
(`art:trail-gates-framework-landing`) has 41 entries across 8 waves and 56
relations; one line per entry plus one per relation is ~100 lines. The recap
prints one block per wave with the entry refs inline, and relations grouped by
type — a count line plus the endpoint pairs, wrapped.

**1a. Endpoints are listed for every relation type, not just the sequencing
pair.** The schema permits five (`hard_depends`, `advisory_precedes`,
`coordinates_with`, `verifies`, `informs`) and real trails use all of them:
the 56-relation trail is 12/16/6/5/17, and `art:trail-shadow-review-loop` is
22 `hard_depends` / 10 `verifies` / 4 `advisory_precedes`. Listing only the
first two would silently reduce half of the largest trail — including every
`verifies` edge, which is how a manual-verification task's coverage is
recorded — to an aggregate number. Measured cost of listing all five with
refs printed verbatim and provenance-labelled groups (decision 1c):
**30 lines on that worst case**, ~7 on a typical 13-relation trail.
Compactness survives, so nothing is withheld.

**1b. Refs are printed verbatim, never shortened.** `aitasks#635_27`, not
`635_27`. A task ref is an identity key (`<project>#<id>`), and stripping the
project segment collides cross-repo members with local ones.

**1c. Every relation group carries its `provenance`.** Type does not imply it:
only `hard_depends` (`fact`) and `advisory_precedes` (`advisory`) are pinned by
the authoring rules; `coordinates_with`, `verifies` and `informs` carry either,
and real trails use both. Without the label a reader cannot separate a recorded
constraint from the trail's own recommendation — the anti-fabrication line.

**2. Create and refresh get the recap; `--show` does not.** Show's Step 1.2
*already* renders every wave, entry, observation, exclusion and the full
narrative — a recap after it prints the same structure twice in one reply. Create
and refresh need it for the opposite reason: create's 2d render is of the
*proposal*, and refresh's 3.4 summary is a **diff**. Neither is a picture of the
artifact as it now stands. Show keeps the depth + summary core and the board
pointer; only the structural recap is withheld.

**3. Headless needs no rule.** Create and refresh STOP before their write in a
headless session (Overview headless guard), so neither ever reaches its recap.
`--show` runs normally headless. The recap is interactive-only *by construction*
— no profile check is added, and the template keeps its single Jinja gate
(`profile.headless`), preserving the agent-invariance pin in
`tests/test_skill_render_aitask_trail.sh` Test 1b.

**4. Words, not glyphs; refs, not badges.** The recap carries wave titles and
entry task refs — not classification, confidence or status. Those are per-card
board material, and their glyph vocabulary is owned by
`TRAIL_CLASSIFICATION_GLYPHS` (`aitask_board.py:889`); restating it in skill
prose would be a second copy that drifts.

**5. Board keys verified against live bindings** (`aitask_board.py`, App-level
`BINDINGS`): `z` → `view_bytrail` (8654), `s` → `trail_select` (8599, the
duplicate that `check_action` makes live inside By-Trail), `v` →
`trail_summary_expand` (8603, gated on the trail having a summary), `enter` →
`view_details` (8576).

**6. Scope boundary with t1210_6 — now a landed fact, not a plan.** `t1210_6`
(same anchor, 1210) landed the skill page, the workflow page and the index rows
in commit `27102e76e`. This task therefore **creates no new docs page**: it
closes the two open acceptance criteria on the landed page and on
`board/reference.md`, and adds the prose the Part A change makes necessary. Per
`documentation_conventions.md` ("delete X / integrate into Y means redirect
cross-refs now"), the §By-Trail prose stays in `board/reference.md` — that
documents the *view*; the skill page documents the *skill* — and the two
cross-link.

## Part A — Enrich the run summary

### A1. `.claude/skills/aitask-trail/SKILL.md.j2` — rewrite `## Run summary print`

Split the section into **three parts, printed in this order**:

| Part | Printed by | Content |
|---|---|---|
| 1. Core | all three flows | the depth line, then the summary line |
| 2. Structural recap | create + refresh only | waves, entries, relations |
| 3. Board pointer | all three flows, always last | the `ait board` line |

The pointer is its own part, **not** a trailing item of the recap: show omits
the recap but still prints the pointer, which is the whole point of telling a
show user the artifact has a board view.

The core keeps the existing prose *verbatim* — the depth line, the
`narrative.overview` → `narrative.recommendation_summary` fallback, and the
"surrounding whitespace stripped" wording — because it is pinned three ways in
`tests/test_trail_skill_contract.sh` block (s) and must stay byte-parity with
`trail_summary_text()` (`aitask_board.py:1055`). The recap is added *around* that
line, never folded into it.

Part 2, the recap, in print order:

1. `Waves (<N>):` then one block per wave in `ordinal` order — `W<ordinal> ·
   <title>` followed by its entries in `position` order as `<position>. <task>`,
   the `task` ref copied exactly as stored. Title only; `purpose` / `why_now`
   belong to the full render.
2. `Relations (<N>):` — a per-type count line for the types present, then the
   endpoint pairs `<from> → <to>` for **every** type present, grouped by
   `(type, provenance)` and headed `<type> · <provenance>:`, in schema order
   (`hard_depends`, `advisory_precedes`, `coordinates_with`, `verifies`,
   `informs`) with `fact` before `advisory` within a type. Pairs wrap within a
   group rather than taking one line each. Refs are printed exactly as stored
   — never shortened, never re-prefixed.

   No type is reduced to a count only: a `verifies` or `informs` edge is as
   much a recorded relation as a `hard_depends` one, and the reader cannot see
   an omitted group's affected tasks.

   **`provenance` is on the group header, not inferred from the type.** It is
   schema-required on every relation and only two of the five types have it
   pinned by the authoring rules (`hard_depends` → `fact`,
   `advisory_precedes` → `advisory`); the other three carry either.
   `art:trail-gates-framework-landing` proves the split is live — its
   `informs` edges are 16 `fact` / 1 `advisory` and its `verifies` edges are
   4 `fact` / 1 `advisory` — and `coordinates_with` is `advisory` there but
   `fact` in `art:trail-mobile-shadow-driving-deep`. Printing type and
   endpoints alone would let a reader take the trail's own recommendation for
   a recorded constraint, which is exactly what the anti-fabrication
   invariant forbids. The label is uniform (applied even where the type pins
   it) so there is no conditional to get wrong, and it costs **one line** on
   the 56-relation worst case: 30 rather than 29.

   Two distinct degradations, which must not share wording:
   - **key absent** → `Relations: none recorded at this depth (lite trails omit
     them).` A lite trail is *required* to omit the key (`lite_shape` in
     `.aitask-scripts/lib/trail_schema.py:375`), so absence means the depth
     carries none — never that the tasks are independent.
   - **key present and empty** (deep only) → `Relations (0): none recorded.`
   Never print a bare `Relations (0):` heading on a lite trail.

Part 3, the board pointer — printed by **every** flow, always last. Copy this
literal exactly, `ait board` in inline code and no escaping:

```
Also viewable in `ait board`: press z (By-Trail), s (choose trail), v (full summary), Enter (member detail).
```

Plus two explicit-decision paragraphs recording decisions 2 and 3 above, and one
recording decision 4 (why the recap carries no badges).

The recap reads back from the JSON already on disk — the create tmpfile, the
refresh tmpfile — so **no new command is introduced in any flow**. The
anti-fabrication invariant applies unchanged.

### A2. Update the three call sites

- **1.4 (show, line ~299)** — parts 1 and 3 (depth, summary, pointer); part 2,
  the recap, is skipped — say why (Step 2 rendered the document in full). Keep
  the existing "stored depth" sentence.
- **2e.5 (create, line ~487)** — all three parts.
- **3.7 (refresh, line ~672)** — all three parts; add that 3.4 showed only what
  *changed*, so this is the run's only picture of the resulting trail.

### A3. `## Notes` — one bullet recording that the pointer names the live
By-Trail bindings and where they are declared.

### A4. Extend `tests/test_trail_skill_contract.sh` block (s)

Keep the three existing `assert_contains` calls untouched; add assertions (run
per profile over all three goldens) that the recap exists, is scoped to
create/refresh, states the lite degradation, excludes `--show` with a reason,
records the headless decision, names `z` / `s` / `v` / `Enter` in the pointer,
names **all five** relation types as groups that get endpoint pairs (the pin
that stops a later edit quietly narrowing the recap back to the sequencing
pair), requires the `<type> · <provenance>:` group header, and pins that the
board pointer is part 3 — printed by show as well, so a later edit cannot fold
it back into the create/refresh-only recap. The task's
acceptance criterion asks for "the recorded dependency relations"; listing
every type with its provenance is a superset of that, not a deviation.

### A5. Regenerate goldens in the same commit

```bash
./.aitask-scripts/aitask_skill_rerender.sh   # or per-profile aitask_skill_render.sh
```
Then refresh all three committed goldens:
`tests/golden/skills/aitask-trail/SKILL-{default,fast,remote}-claude.md`.

**No Codex/OpenCode follow-up task is needed.** The rendered variants under
`.agents/` and `.opencode/` are not committed (`git ls-files` returns nothing for
them), the template carries no `{% if agent %}` gate, and Test 1b pins renders as
byte-identical across the three agents — so the `.j2` edit reaches every agent
for free.

## Part B — Website documentation (rescoped: t1210_6 landed most of it)

**Re-verified against commit `27102e76e` ("documentation: Document
implementation trails and fix stale board prose (t1210_6)"), which landed while
this plan was being written.** It created
`website/content/docs/skills/aitask-trail.md` (81 lines, weight 63, stable /
advanced), the `_index.md` row, the `codeagent.md` `trail` operation row, the
`docs/workflows/implementation-trails.md` workflow page, and board
reference/how-to updates. Verified now: `tests/test_website_doc_lists.sh` is
**45/45** (it was 44/45 before that commit).

So the following planned items are **already done and are dropped**: creating
the skill page (B1), the `_index.md` row (B2), the `codeagent.md` `trail` row
(B4), and the `## Workflows` link — the landed page links the workflow page from
line 12 and its `## Related` list.

Two acceptance criteria are **still open**, plus one new gap that Part A itself
creates.

### B1. `docs/tuis/board/reference.md:246` — link the skill (AC, still open)

The §By-Trail paragraph still names the skill as bare inline code, not a link:

> `created and re-authored by the` **``/aitask-trail``** ` skill`

Make it `` [`/aitask-trail`]({{< relref "/docs/skills/aitask-trail" >}}) ``.
This is the AC "§By-Trail links to the new skill page", and it is the one
sentence on the site that frames the skill as a board affordance. Do the same
for "the trail skill" in the `--deep` paragraph further down the section, and
for the two mentions in `docs/tuis/board/how-to.md` (the `T` step and the
`--deep` sentence).

### B2. `docs/skills/aitask-trail.md` — conversational invocation (AC, still open)

The AC requires the page to describe "invoking it conversationally". The landed
page documents only the slash form. Add a short paragraph after the `**Usage:**`
block saying the skill is also reached by asking your coding agent for an
implementation trail in plain language — it resolves to the same flow, with the
same confirmation before the single write. Genericize the agent reference per
`documentation_conventions.md` (no enumeration of the supported agents).

### B3. `docs/skills/aitask-trail.md` — describe the enriched run summary (new, created by Part A)

Step 5 currently ends "…and prints the run summary", which after Part A no
longer describes what the user sees. Expand it to state that the summary reports
the authoring depth, the trail's prose overview, the wave/entry structure with
the recorded relations and their provenance, and a pointer to the board's
By-Trail view — and that `--show` omits **only the structural recap**, because
it has already rendered the whole document in full; it still prints the depth,
the overview and the board pointer. Without this the page documents a summary
that Part A has made obsolete, and stating it as "depth and overview only"
would document the new behaviour wrongly on day one.

Also tighten the existing back-link in `## Related` to the section anchor:
`` [Board reference]({{< relref "/docs/tuis/board/reference" >}}#by-trail) ``.

### B4. `docs/workflows/implementation-trails.md` — one sentence (new, created by Part A)

`## Creating a Trail` ends with the write; the page never mentions that the
terminal run itself now shows the resulting structure. Add one sentence after
that paragraph noting the agent prints the resulting waves and relations plus a
pointer to By-Trail, so a trail created from the agent needs no board
round-trip to read. Current-state prose only; no "now also" framing.

### Post-phase (risk mitigations)

1. `[guard_board_pointer_keys]` Add a drift guard asserting that the run
   summary's board pointer names the live By-Trail bindings. Read the
   App-level `BINDINGS` in `.aitask-scripts/board/aitask_board.py` for the
   actions `view_bytrail`, `trail_select`, `trail_summary_expand` and
   `view_details`, extract each one's key, and assert the rendered skill
   golden's pointer line names exactly those four keys. Fails if a key is
   rebound without updating the skill prose. Place it beside the existing
   By-Trail resolver tests in `tests/test_board_bytrail_view.py`, which
   already imports the board module.

## Verification

```bash
bash tests/test_trail_skill_contract.sh          # existing pins + new recap pins
bash tests/test_skill_render_aitask_trail.sh     # golden diff × 3 profiles, agent invariance
./.aitask-scripts/aitask_skill_verify.sh         # render + closure + stub surfaces
bash tests/test_website_doc_lists.sh             # 45/45 today; must stay 45/45
bash tests/run_all_python_tests.sh --test-dir tests   # incl. test_board_bytrail_view.py parity pins
cd website && hugo build --gc --minify           # clean build, no broken relref
```

Manual read-through: render the `fast` variant and confirm the recap section
reads correctly against a real artifact —
`./.aitask-scripts/aitask_artifact.sh get art:trail-gates-framework-landing`
(8 waves / 41 entries / 56 relations across all five types, depth unrecorded) is
the stress case — confirm the relation block stays around 30 lines, that no type
is missing a group, and that its two mixed-provenance types split into separate
groups (`verifies` 4 fact / 1 advisory, `informs` 16 fact / 1 advisory).
`art:trail-mobile-shadow-driving` (lite, `relations` key absent) is the
honest-degradation case, and `art:trail-shadow-review-loop` (36 relations, 10 of
them `verifies`) confirms a non-sequencing type is listed rather than counted.

## Risk

### Code-health risk: low
- The skill edit is prose in one `.md.j2` section plus three call-site
  sentences; the docs edits are additive. The only executable surfaces touched
  are test assertions and committed goldens, both regenerated in the same
  commit. · severity: low · → mitigation: TBD
- The board pointer duplicates four key letters that live in
  `aitask_board.py`'s `BINDINGS`; if a key is rebound the prose goes stale
  silently. · severity: low · → mitigation: inline post-phase guard_board_pointer_keys

### Goal-achievement risk: low
- The recap format is fixed by the approved preview, and every acceptance
  criterion maps to a named edit. The one open judgement — how much detail per
  entry — was decided by the user during planning. · severity: low ·
  → mitigation: TBD
- The recap is agent-executed prose, not code, so nothing mechanically enforces
  that a run actually prints it; only the contract test pins that the
  *instruction* exists. · severity: medium · → mitigation: TBD
- Part B now edits pages another task authored hours earlier; a Part A wording
  change that is not mirrored into `docs/skills/aitask-trail.md` leaves the
  landed page describing a run summary that no longer exists. · severity:
  medium · → mitigation: Part B step B3, which mirrors the Part A wording into
  the landed page in the same commit

### Planned mitigations
- timing: post-phase | name: guard_board_pointer_keys | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — board pointer duplicates four key letters owned by aitask_board.py BINDINGS | desc: Drift guard asserting the run summary's board pointer names the live view_bytrail / trail_select / trail_summary_expand / view_details keys.

## Step 9 (Post-Implementation)

Standard: commit, merge to `main` (current-branch mode under profile `fast`),
archive `t1644` and its plan.

## Final Implementation Notes

- **Actual work done:** Rewrote `## Run summary print` in
  `.claude/skills/aitask-trail/SKILL.md.j2` into three parts (core / structural
  recap / board pointer), updated the three call sites (1.4, 2e.5, 3.7), added a
  `## Notes` bullet recording the pointer↔BINDINGS coupling, extended
  `tests/test_trail_skill_contract.sh` block (s) with 57 new per-profile
  assertions, regenerated all three goldens, added the
  `RunSummaryBoardPointerTests` drift guard to
  `tests/test_board_bytrail_view.py`, and made the four docs edits.

- **Deviations from plan:** Part B was rescoped mid-plan and re-verified after
  `t1210_6` landed (commit `27102e76e`) — it had already created the skill page,
  the `_index.md` row, the `codeagent.md` `trail` row and the workflow page, so
  three of the four originally planned Part B items were dropped as done and two
  new ones were added (describing the enriched summary on both landed pages).
  The `trail_workflow_page_footer` "after" mitigation was dropped for the same
  reason: the workflow page it was waiting on now exists and is already linked.

- **Issues encountered:**
  - The first golden regeneration used `aitask_skill_render.sh` output, which is
    not byte-identical to what `test_skill_render_aitask_trail.sh` compares
    against (that test renders via `lib/skill_template.py` to stdout). Three
    golden diffs failed until the goldens were regenerated with the test's own
    renderer. **The renderer that writes a golden must be the renderer the test
    reads it with.**
  - The `Relations: none recorded at this depth (lite trails omit them).`
    literal initially wrapped across two lines in the template, so its contract
    pin matched nothing. Reflowed the bullet so the whole literal sits on one
    rendered line — a wrapped pin guards nothing.
  - The board-pointer guard failed on its first run against `view_details`:
    Textual's key name is `enter` but user-facing prose capitalises it. Resolved
    by comparing single-character keys case-sensitively (this board binds `s`
    and `S` to *different* actions, so folding case there would let the pointer
    name the wrong one) and named keys case-insensitively.
  - The full Python suite reports 2 failures in
    `tests/test_board_dialog_run_dispatch.py::ResumeBranchTests`. These are
    **not** from this task: another concurrent session has ~289 uncommitted
    lines in `.aitask-scripts/board/aitask_board.py`, and its diff is squarely
    about `resume_point` / gate-resume — exactly what those tests cover. This
    task touched no board source. Commit was made with `git commit -o --` over
    an explicit path list so that session's work was left untouched.

- **Key decisions:**
  - **All five relation types get endpoint groups, not just the sequencing
    pair.** Measured on `art:trail-gates-framework-landing` (56 relations):
    listing only `hard_depends`/`advisory_precedes` would have reduced 28 of 56
    edges — including every `verifies` edge, which is how a manual-verification
    task's coverage is recorded — to a bare count. Full listing costs 30 lines
    on that worst case versus 21, so compactness survives.
  - **Groups are keyed on `(type, provenance)`, not type alone.** Provenance is
    schema-required but only pinned by the authoring rules for two of the five
    types; the same document holds `informs` 16 fact / 1 advisory and `verifies`
    4 fact / 1 advisory. Type alone therefore cannot be used to infer it, and an
    unlabelled pair lets a reader take the trail's own recommendation for a
    recorded constraint. Cost: one extra line on the worst case.
  - **Refs print verbatim.** A task ref is an identity key (`<project>#<id>`);
    shortening it would collide a cross-repo member with a local one.
  - **The board pointer is its own part, printed by `--show` too.** Only the
    structural recap is create/refresh-only. Folding the pointer into the recap
    would leave the show user — the one reading a stored trail — never told the
    board renders it.
  - **No profile check for headless.** Create and refresh stop before their
    write in a headless session, so neither reaches the recap by construction.
  - **The recap carries no classification glyphs.** That vocabulary is owned by
    `TRAIL_CLASSIFICATION_GLYPHS` in the board; restating it in skill prose
    would be a second copy that drifts.
  - **No Codex/OpenCode port task needed.** The rendered variants under
    `.agents/` and `.opencode/` are not committed, the template has no
    `{% if agent %}` gate, and Test 1b pins renders byte-identical across the
    three agents — so the `.j2` edit reaches every agent for free.

- **Upstream defects identified:** None

- **Follow-ups created:** t1654 (manual verification of the enriched run summary
  and the board pointer keys).
