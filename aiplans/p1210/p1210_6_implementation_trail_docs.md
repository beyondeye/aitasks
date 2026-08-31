---
Task: t1210_6_implementation_trail_docs.md
Parent Task: aitasks/t1210_brainstorm_durable_implementation_trail_skill_and_board_repo.md
Sibling Tasks: aitasks/t1210/t1210_7_manual_verification_implementation_trails.md
Archived Sibling Plans: aiplans/archived/p1210/p1210_1_trail_schema_library_and_validator.md, aiplans/archived/p1210/p1210_2_trail_gatherer_and_drift_helper.md, aiplans/archived/p1210/p1210_3_aitask_trail_skill.md, aiplans/archived/p1210/p1210_4_board_bytrail_view.md, aiplans/archived/p1210/p1210_5_trail_move_to_column_commands.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1210_6 — Implementation Trail documentation

## Context

The Implementation Trails feature (t1210) is fully shipped: children t1210_1–t1210_5
landed the schema library and validator, the gatherer/drift helper, the
`/aitask-trail` skill, the board By-Trail view, and the By-Trail move-to-column
commands. **None of it has a user-facing workflow page**, and the last child
(`f1dc4f23e`, t1210_5) shipped code and tests only — so the board reference now
actively contradicts the shipped behavior.

T6 is the documentation child. It closes the gap between what the code does and
what a user can read.

Two gaps found during exploration that are in scope but not in the task's file list:

1. **`tests/test_website_doc_lists.sh` is currently failing.** t1210_3 registered
   the `trail` codeagent operation in `SUPPORTED_OPERATIONS`
   (`.aitask-scripts/aitask_codeagent.sh:26`) but never added the row to
   `website/content/docs/commands/codeagent.md`. That guard asserts every
   canonical operation is documented.
2. **Stale board reference prose.** Three passages assert the absence of exactly
   what t1210_5 added.

User decisions taken during planning:
- **Add the `/aitask-trail` skills reference page** (every other skill has one; the
  same drift guard requires it be linked from `skills/_index.md`).
- **RFC sweep = status header + §14, keep §13's rationale.** `aidocs/` is internal
  design documentation; the alternatives table is expensive-to-reconstruct
  reasoning and stays.

## Ground truth (verified against the shipped tree, not the RFC)

- **There is no `ait trail` command.** `aitask_trail_gather.sh` is deliberately not
  wired into the dispatcher. Trails are reached via the `/aitask-trail` skill and
  the board; they are stored and inspected via `ait artifact`.
- Skill modes: create (bare / `<task_id>` / `--topics <csv>`), `--refresh <handle>`,
  `--show <handle>`. Depth `--deep` / `--lite`; **absence means lite**, including
  the board's `R`.
- By-Trail keys: `z` enter · `s` select · `r` local redraw · `d` freshness ·
  `R` agent re-author · `S` sync · `v` summary · `Enter` detail (`a` show all) ·
  `m` move task · `M` move wave. `T` creates a trail from other views.
- `m` gating in By-Trail: focused card, **not** a child, **not** a ghost.
  `M` gating: focused non-ghost card, deliberately **not** gated on `is_child`.
- `M` always reviews; preserves wave `position` order verbatim; dedupes repeated
  refs on first occurrence; reports which items were skipped, never bare counts.
- Classification glyphs (`TRAIL_CLASSIFICATION_GLYPHS`, `aitask_board.py:889`):
  `◆` hard_prerequisite · `▲` preferred_predecessor · `●` core ·
  `⇄` coordination_only · `○` optional.
- Board repaints are never drift — `boardidx` is unrepresentable in the digest, so
  moving cards does not stale a trail.
- Schema version `1.1.0`; canonical enums live in
  `.aitask-scripts/lib/implementation_trail.schema.json` (byte-identical twin of
  the `aidocs/` copy, pinned by a test).

## Acceptance map — TUI documentation surfaces

The task names Board, Monitor, Minimonitor, Codebrowser, Settings and Brainstorm as
the surrounding TUI surface. By-Trail is a **board base view, not a TUI**, so most of
that list needs no edit — but that is recorded as evidence, not assumed:

Expressed as an **inverted assertion**: a bare `grep` exits 1 when it correctly finds
nothing, so "no hits" would read as a failed check (and would abort under `set -e`).
This form exits 0 only when the surfaces are genuinely clean, and says so:

```bash
fail=0
for d in monitor minimonitor codebrowser settings brainstorm; do
  if grep -rqE "By-Topic|By-Trail|base view|base filter|implementation trail" \
       "website/content/docs/tuis/$d/"; then
    echo "UNEXPECTED HITS in $d"; fail=1
  fi
done
[ "$fail" -eq 0 ] && echo "OK: no board-view/trail references in the five surfaces"
```

Verified today: all five are clean (`fail=0`).

| Surface | Required edit | Evidence |
|---|---|---|
| `tuis/board/reference.md` | **Yes** — step 4 | three passages contradict t1210_5 |
| `tuis/board/how-to.md` | **Yes** — step 4 | By-Trail block predates the move commands |
| `tuis/board/_index.md` | None | `:33`, `:51` already list `z By-Trail`; verified correct |
| `tuis/_index.md` | **Yes** — step 4b | zero trail hits; the Board blurb (`:19`) claims "deciding what to implement next", which is exactly what a trail records |
| Monitor | None | zero hits (command above) |
| Minimonitor | None | zero hits |
| Codebrowser | None | zero hits |
| Settings | None | zero hits — the Shortcuts tab is described generically and enumerates no per-key bindings |
| Brainstorm | None | zero hits |

The five "None" rows are re-run as a grep in Verification, so the claim stays true
rather than being a one-time observation.

## Implementation

### 1. New — `website/content/docs/workflows/implementation-trails.md`

Front matter: `weight: 46`, `depth: [advanced]`, placing it beside
[Parallel Planning](weight 45) in the sidebar.

Sections, modelled on `work-report.md` / `manual-verification.md` (lead with the
problem, one bolded key insight, then a numbered walkthrough):

1. **Why a trail** — the task DAG and board order do not record *which tasks land
   next, in what waves, and why*. That analysis is expensive and otherwise lives in
   terminal scrollback.
2. **What a trail contains** — waves of ordered entries, each with a classification,
   a rationale, a confidence, and cited evidence; plus observations (facts that shape
   ordering without being members) and exclusions (work deliberately not blocking).
   Name the five classifications with their board glyphs. **Do not reproduce the full
   enum tables** — describe the five classifications a reader acts on, and carry an
   HTML-comment drift note for maintainers (the same device `workflows/_index.md`
   already uses for its t594_7 note). This satisfies the task's "derive, don't
   duplicate" rule without citing a framework-internal `aidocs/` path in
   reader-visible prose.

   **The note must name two sources, because the page documents two things that live
   apart** — verified: the schema files contain zero glyph characters.

   | Documented | Canonical source |
   |---|---|
   | the five classification names | `.aitask-scripts/lib/implementation_trail.schema.json` (`entry.classification` enum) |
   | the `◆ ▲ ● ⇄ ○` glyph mapping | `TRAIL_CLASSIFICATION_GLYPHS`, `.aitask-scripts/board/aitask_board.py:889` |

   A schema-only note would read as satisfied while a board glyph change silently
   falsified the page. If naming both sources proves unwieldy, the fallback is to
   drop the glyph column from the page rather than leave it half-guarded.
3. **Creating one** — board `T` on a focused task (By-Topic resolves the lane root),
   or `/aitask-trail` / `/aitask-trail <task_id>` / `--topics <csv>`. Read-only
   analysis → review → **one confirmed write**.
4. **Lite and deep** — absence means lite; deep adds observations, relations,
   exclusions and per-entry evidence. `--show` reports the stored depth; an
   unlabelled trail means "depth not recorded", never "deep".
5. **Reading it on the board** — `z`, `s`, wave columns, glyphs, summary pane, the
   entry-first detail screen and `a`.
6. **Keeping it current** — the refresh ladder cheapest-first (`r` → `d` → `S` → `R`),
   what counts as drift, and explicitly that board moves do not.
7. **Feeding a work report** — the passive bridge: `M` a wave into a column, then
   run the report on that column. State plainly that a trail never changes report
   membership by itself. Cross-link `work-report.md`.
8. **What a trail never does** — advisory only; never rewrites `depends`, `priority`,
   `boardidx` or `anchor`; no estimates, progress or commitments.
9. **Tips.**

Generic example project names throughout; no sibling-directory paths.

### 2. New — `website/content/docs/skills/aitask-trail.md`

Reference page in the house style: invocation grammar table (the shipped
create/refresh/show × lite/deep matrix), what each mode does, the single-write
invariant, and the storage note that trails live in `ait artifact`.

### 3. Hand-curated lists (both are drift-guarded)

- `workflows/_index.md` — add the bullet under **Parallel**, after Parallel Planning.
- `skills/_index.md` — add the `/aitask-trail` row. Under **Task Management** is the
  best fit. **Required** by `tests/test_website_doc_lists.sh`.

### 4. Fix the stale board reference — `website/content/docs/tuis/board/reference.md`

| Line | Current (wrong) | Change |
|---|---|---|
| 53 | `m` … "hidden in In-Flight, By-Topic and By-Trail views" | drop By-Trail; add the By-Trail gating (focused, non-child, non-ghost) |
| ~341 | "`T`, `w`, and the card-move keys are hidden for the same reason." | keep `T`/`w`; remove the card-move claim |
| 327–334 | pinned footer string | add `m Move to Col` and `M Move Wave` |
| new row | — | `M` = Move the focused wave's tasks to a column, in wave order |
| ~470 | modal table | note the wave-move entry path into Column Select |

`how-to.md:82` (marking) and `:142` (column management) stay correct — verified, not
assumed. Add a short By-Trail move walkthrough to `how-to.md` next to the existing
By-Trail block, covering the review step, wave-order preservation, and ghost refusal.

### 4b. `website/content/docs/tuis/_index.md`

Extend the Board blurb (`:19`) with a clause naming the By-Trail view and linking the
new workflow page. This is the only non-Board TUI surface that needs a change, per the
acceptance map above.

### 5. `website/content/docs/commands/codeagent.md`

Add the missing Operations row: `` `trail` `` | Creating and refreshing implementation
trails | `claudecode/opus5` (verified from both live and seed `codeagent_config.json`).
This repairs the failing drift guard.

### 6. Cross-references

- `workflows/work-report.md:35` — add By-Trail to the list of views where `w` is
  hidden, and cross-link the passive bridge.
- `concepts/topic-anchoring.md` — one sentence stating the orthogonality in **both**
  directions, plus a See-also link. Each clause is traced to source, not to the RFC:

  | Claim | Source |
  |---|---|
  | a task has exactly one topic | `topic_key()` in `.aitask-scripts/lib/topic_semantics.py:57` returns a single key per task (anchor → parent's key → own id) |
  | a task may appear in several trails | `compute_trail_overlaps()` in `.aitask-scripts/board/aitask_board.py:1080` builds "also in" notes for refs shared with another discovered trail |
  | one trail may span topics | `scope.kind` enum includes `multi_topic` in `implementation_trail.schema.json` |

  These three claims are added to the `claims_audit` post-phase, so the sentence is
  verified alongside the board behavior rather than being the one unaudited assertion.

### 7. RFC sync — `aidocs/implementation_trail_design.md`

- **Header (L3–5)** — replace "proposed design … nothing in this document is shipped
  code yet" with a shipped-state status naming the landed surfaces.
- **§14** — convert the copy-ready T1–T7 decomposition into a map of shipped
  components → files.
- **§14 D-list — rewritten, not kept.** A "deferred items with dispositions" backlog
  reads as an active implementation plan inside a shipped-state document, and the
  `Conditional` / `Documented-only` disposition column is planning vocabulary. Replace
  it with a **Current limitations** list phrased as present behavior, dropping the
  entries that are only rejected alternatives or are already stated elsewhere:

  | D-list entry | Disposition |
  |---|---|
  | CAS (`update --expect-current`) | **Keep** as a limitation — the artifact CLI has no CAS; concurrent refresh is bounded by the §8.3 pre-write re-read guard |
  | Advisory → `depends`/priority conversion | **Keep** as a limitation — trails never mutate `depends`, `priority`, `boardidx` or `anchor` |
  | Trail-aware auto-creation of follow-ups | **Keep** as a limitation — refresh may propose candidates; creation stays user-confirmed |
  | By-Topic overlay/badges | **Drop** — a rejected alternative, already recorded in §13-A5 |
  | Explicit `--trail` report mode | **Drop** — §10 already states the passive-bridge contract |
  | Cross-repo artifact resolution | **Drop** — §11 already records the substrate limitation |

  Net effect: nothing in the RFC still reads as scheduled-but-unbuilt work, and no
  genuine limitation is lost — each retained one is restated as what the system does
  today rather than as a future task.
- **§9 L414–415** — the `base_filter` enumeration omits `bytrail`; add it.
- **§9.1 L419–420** — "concrete key chosen at implementation time" → `z`.
- Future-tense fixes at L92, L242, L322, L412.
- **Keep §13** (user decision) and **§16** (its "23 checks" is still accurate —
  verified: `grep -c "def test"` returns 23).

## Verification

```bash
bash tests/test_website_doc_lists.sh          # must pass — currently FAILING
bash tests/test_trail_skill_contract.sh
bash tests/test_codeagent_trail.sh
python3 -m unittest tests.test_implementation_trail_design -v   # RFC-adjacent guard
cd website && hugo build --gc --minify        # clean build, no broken relrefs
```

Grep checks:
- new page linked from `workflows/_index.md`; skill page linked from `skills/_index.md`
- no `../aitasks/` sibling-directory paths, no `aidocs/` paths in reader-visible prose
- no `ait trail` string anywhere in the new pages (the command does not exist)
- re-run the acceptance-map assertion (inverted-grep form above) over the five
  non-Board TUI doc dirs; it must print `OK:` and exit 0
- the workflow page's drift comment names both the schema enum and
  `TRAIL_CLASSIFICATION_GLYPHS`
- no `Conditional` / `Documented-only` disposition vocabulary left in the RFC

Baseline note: capture `tests/test_website_doc_lists.sh` failing **before** the
codeagent.md edit, so the fix is demonstrated rather than assumed.

## Risk

### Code-health risk: low
- Documentation-only change across 10 markdown files; no runtime code touched. No
  test pins the RFC prose — the design-contract guard covers
  `aidocs/implementation_trail.schema.json` and the fixtures, not the document body
  (verified by reading `tests/test_implementation_trail_design.py`). · severity: low · → mitigation: none needed
- Restating schema enumerations in prose would create a second source of truth that
  drifts. · severity: medium · → mitigation: inline post-phase `enum_drift_note`
- The classification names and their board glyphs have **different** canonical homes
  (schema enum vs `TRAIL_CLASSIFICATION_GLYPHS`), so a single-source drift note would
  guard only half of what the page states. · severity: medium · → mitigation: inline post-phase `enum_drift_note` (two-source form)

### Goal-achievement risk: medium
- Highest risk in a docs task is asserting behavior the code does not have — the
  `m`/`M` gating asymmetry (`M` stays live on a focused child, `m` does not) and the
  ghost refusals are easy to state backwards, and the RFC cannot be trusted as the
  source since it describes design intent. · severity: medium · → mitigation: inline post-phase `claims_audit`
- Inventing an `ait trail` command is a live trap: every neighbouring feature has a
  dispatcher verb and this one deliberately does not. · severity: medium · → mitigation: inline post-phase `claims_audit`
- The board docs already cover By-Trail from t1210_4, so a careless pass could
  duplicate rather than correct. · severity: low · → mitigation: covered by step 4's line-targeted table
- Rewriting the RFC D-list drops three entries as redundant. If §10/§11/§13 do not in
  fact still state them, a real limitation would vanish. · severity: low · → mitigation: re-read the three cross-referenced sections before deleting each entry; drop only on a confirmed hit

### Planned mitigations

Both confirmed **inline** (user decision) — nothing is spawned as a separate task.
Reassessed against the augmented plan: code-health stays **low**; goal-achievement
stays **medium** — the audit meaningfully reduces the wrong-claims risk but the
surface is broad (10 files, many precise behavioral claims), so the residual is
bounded rather than eliminated.

- timing: post-phase | name: claims_audit | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: wrong-behavior claims and the invented-CLI trap | desc: after drafting, re-read aitask_board.py's By-Trail check_action gates and both move actions, and confirm every keybinding, gating and refusal sentence against the source rather than the RFC
- timing: post-phase | name: enum_drift_note | type: documentation | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: prose duplicating the schema enums | desc: keep reader-visible enum prose to the five classifications, and carry an HTML-comment drift note naming the canonical schema file for maintainers

### Post-phase (risk mitigations)

Run after the drafting steps, before the verification block:

- **`claims_audit`** — two parts, both against source rather than the RFC:
  1. *Board behavior* — re-read `check_action`'s By-Trail arms, `action_move_to_column`
     and `action_trail_move_wave` in `.aitask-scripts/board/aitask_board.py`; verify
     every keybinding, gating condition and refusal message stated in the new and
     edited pages. Grep the new pages for `ait trail` and confirm zero hits.
  2. *Topic/trail relationship* — verify the `concepts/topic-anchoring.md` sentence
     against `topic_key()` (`lib/topic_semantics.py`), `compute_trail_overlaps()`
     (`aitask_board.py`) and the `scope.kind` enum, per the trace table in step 6.
     If any clause cannot be traced to source, drop that clause rather than soften it.
- **`enum_drift_note`** — confirm the workflow page names only the five
  classifications in reader-visible prose, and that its maintainer drift comment names
  **both** canonical sources: the schema's `entry.classification` enum *and*
  `TRAIL_CLASSIFICATION_GLYPHS` in `aitask_board.py`. Assert the glyph half is not
  self-satisfying — grep the schema for the glyph characters and confirm zero hits, so
  the note is provably guarding something the schema does not define.
