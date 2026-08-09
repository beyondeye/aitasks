---
Task: t1427_4_rejection_docs.md
Parent Task: aitasks/t1427_reject_shadow_concerns_suppress_next_round.md
Sibling Tasks: aitasks/t1427/t1427_5_manual_verification_reject_shadow_concerns_suppress_next_rou.md
Archived Sibling Plans: aiplans/archived/p1427/p1427_*_*.md
Worktree: . (current directory — profile 'fast', no worktree)
Branch: main (current branch)
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-09 10:25
---

# p1427_4 — Documentation for concern rejection + suppression

Documents the t1427 concern-rejection feature across the website and `aidocs/`.
Siblings t1427_1..3 have landed and archived. **This plan documents CURRENT
SOURCE** — every key, glyph, and output string below was re-verified against the
landed implementation during the verification pass recorded next.

## Context

The shadow's concern picker gained a per-row rejection disposition (t1427_2), a
durable per-task rejection store (t1427_1), and a producer-side suppression rule
that drops previously-rejected concerns from the next review round (t1427_3).
None of that appears in any user-facing page. Worse, the existing pages still
describe the `a` / `A` bulk keys that t1427_2 **removed outright**, so today's
docs instruct users to press keys that do nothing.

## Verification pass (2026-08-09) — what changed from the original plan

Five corrections; the plan below already incorporates them.

1. **All `aidocs/framework/shadow_agent.md` line anchors shifted.** t1451
   (`627f828cc`) edited that file after this plan was written. Current truth:
   `## Feedback freshness` content ends at **:350**, `## Configuration` starts at
   **:352** (plan said ~:341), the Step 2 bullet is at **:110** (plan said ~:107),
   the sub-procedure list is **:111-144** (plan said ~:110-142), and the
   no-gating principle is `## Phase detection (deferred)` at **:377-401** (plan
   said ~:366-390). Re-derive rather than trusting any number here.

2. **A fifth doc surface exists that neither the task nor the plan listed:**
   `website/content/docs/tuis/minimonitor/_index.md:79` is a standalone
   concern-picker summary paragraph. It carries no `a`/`A`, but it describes the
   picker as pure copy-to-clipboard and omits rejection entirely. Added to the
   scope below as Step 5 — leaving it would make it the one surface that
   contradicts the other four.

3. **The plan's stale-content grep would have missed half the defect.** The two
   stale passages use *different wording*: minimonitor says "**a** (select all)
   … **A** (copy all)", monitor says "**a** selects or clears only the actionable
   ones, while **A** takes everything". A `grep "copy all\|toggle all"` matches
   only the first. The verification section below uses a pattern proven against
   both, run as a positive control before editing.

4. **`r` and `R` must NOT be added to the global keybinding tables.** `ait
   monitor` already binds them globally to different actions —
   `reference.md:45` `r` = refresh, `reference.md:33` `R` = restart task — and
   `reference.md:49` binds `a` to auto-switch mode. The picker's `r`/`R` are
   **modal-scoped**; Textual does not dispatch App-level bindings under a
   `ModalScreen`. Document them inside the picker prose and the existing `c`
   row's parenthetical, exactly as `u` is already documented.

5. **Plan-review rounds (4 concerns raised, all verified valid, all addressed).**
   - *`R` was documented as a single happy path.* `action_show_rejected`
     (`monitor_shared.py:2610-2633`) has **three** outcomes; the two no-modal
     ones read as a broken shortcut if undocumented. Now specified in "Verified
     source facts", Steps 1-3, and Verification check 2b.
   - *`anchor_integrity` required a link no step created.* The check demanded
     the new workflow section be linked from a TUI page, but no step added one —
     making the check unsatisfiable-by-construction. Steps 2 and 3 now add an
     explicit `{{< relref … >}}#reject-a-concern-so-it-does-not-come-back` deep
     link (the pattern already exists in-tree, e.g. `#review-the-implementation`
     from `settings/reference.md:147`).
   - *The rejected list's `Enter` was described as applying the un-rejection.*
     It does not: `action_confirm` (:2346-2347) only dismisses with the marked
     ids, which the picker accumulates; the `remove` call happens only after the
     **picker** is confirmed, and `Esc` on the picker discards both staged sets.
     Now specified as an explicit two-stage flow in "Verified source facts",
     Steps 1-3, Verification check 2c, and the `keys_match_source` post-phase.
   - *The stale sweep searched only three paths.* Now a whole-tree sweep over
     `website/content/docs/`, `aidocs/` and `README.md`, with an explicit
     classify-the-residual step — the ~25 unrelated `a`/`A` bindings in board /
     brainstorm / settings / syncer / codebrowser / monitor-auto-switch are
     recorded as intentional residual rather than assumed away.

6. **The `a`/`A` scrub is website-only.** t1427_3 already fixed the two skill-tree
   occurrences (`concern-format.md`, `impl-challenge.md`); `aidocs/` has zero
   hits. Exactly **two** literal stale passages remain (minimonitor/how-to.md:165,
   monitor/how-to.md:195) plus **one indirect** ("left out of the select-all key",
   shadow-agent.md:100).

## Verified source facts to document

Re-checked directly in the landed source — do not paraphrase these.

**Picker keys** (`monitor_shared.py:2394-2401` BINDINGS + `_ConcernRow.on_key`,
canonical help string `_CONCERN_HELP_FULL:2124-2127`):
`Space` forward · `r` reject · `R` rejected list · `u` unparsed · `Enter`/OK
confirm · `Esc` cancel. `Space` and `r` are per-row, mutually exclusive.

**Row glyphs** (`_CONCERN_MARKS:1907-1911`): `☐` none · `☑` forward (bold yellow)
· `✗` rejected (red, row dims).

**Rejected-store view** (`RejectedStoreModal:2281-2350`): opened with `R`, header
`Rejected concerns (N)`, per-row `Space` marks for un-reject, `Enter` returns
the marked ids to the picker (binding label: "Un-reject marked" — but see the
two-stage note below; it writes nothing), `q`/`Esc` cancels. It opens *over* the
picker and accumulates across visits.

**Nothing is written until the *picker* is confirmed — a two-stage flow.** The
rejected-list modal's `Enter` (labelled "Un-reject marked") only
`dismiss(self._marked_ids())` (`:2346-2347`); `_on_rejected_view_closed`
(:2635-2644) accumulates the ids into the picker's `_unreject_ids`, and
`_result()` (:2603-2608) carries them out as `ConcernPickResult.unrejected`. The
store is touched **only** by `apply_concern_pick_result`, which returns
immediately on `result is None` (:674-675) — the Esc/Cancel signal. So:

- `r` marks and `R`-modal un-reject marks are both **staged**, not applied.
- Confirming the picker (`Enter`/OK) is what writes `add` and `remove`.
- Cancelling the picker (`Esc`) discards **both** staged sets silently.

Documenting `Enter` in the rejected list as "applies the un-rejection" without
this would set up a real failure: mark → `Enter` → cancel the picker → the user
expects the concerns restored, and they are not. Say "marks them for
un-rejection; the change is written when you confirm the picker".

**`R` has three outcomes, not one** (`action_show_rejected:2610-2633`) — the
docstring states the two empty cases are reported differently *on purpose*:

| condition | result |
|---|---|
| store has entries | the list modal opens over the picker |
| store read, genuinely empty | no modal; notice `No previously rejected concerns for this task` |
| pane has no task id (`_store_unavailable`) | no modal; **warning** `No task id for this pane — rejection store unavailable` |

Undocumented, the latter two read as a broken shortcut. The third is
deliberately surfaced *before* confirming — it means any rejection made in this
session will be refused — and is **distinct** from the post-confirm warning
`Rejections not persisted — no task id for this pane` (`:690-693`), which fires
after the user confirms rejections. Document both, and say which comes when.

**Store** (`aitask_shadow_rejected.sh:86,132-136`):
`.aitask-shadow/<task_id>/rejected.md`, bare task id (no `t`), git-ignored
(`.gitignore:22`, installed by `setup_shadow_store_gitignore()` in
`aitask_setup.sh:1993-2020`), pruned at archive by `prune_shadow_rejections()`
(`aitask_archive.sh:199-208`, three call sites after `release_lock`).
Subcommands `add` / `list` / `remove` / `prune`; exit codes 0 / 2 / 3 (LOCK_BUSY)
/ 4 (unusable).

**Suppression report line** (identical in all four producers, verbatim):
`Suppressed N previously-rejected concern(s).`

**Fail-open**: unsure whether a fresh concern matches a rejected one ⇒ **keep it
and say why**. Unresolvable task id or unreadable store ⇒ emit everything and
state that suppression was skipped; an error is never read as "nothing rejected".

**User-visible toasts** (`monitor_shared.py:681-732`):
`N concern(s) rejected — suppressed next round` · `N concern(s) un-rejected` ·
`Rejections not persisted — no task id for this pane` (warning) ·
`Rejection store busy — try again` (warning) · `Rejection store unusable — not
retrying (…)` (error).

## Steps

### Pre-phase (risk mitigations)

1. `[stale_sweep_positive_control]` **Before editing any file**, run the
   **whole-docs-tree** sweep from Verification check 1 (all of
   `website/content/docs/`, `aidocs/`, and `README.md` — *not* the three picker
   paths) and record the full hit list in the plan.
   - It MUST report `website/content/docs/tuis/minimonitor/how-to.md:165`,
     `website/content/docs/tuis/monitor/how-to.md:195`, and
     `website/content/docs/workflows/shadow-agent.md:100`. If it misses any of
     the three, fix the pattern and re-run until it catches all three — only
     then start editing. A pattern not proven to match pre-edit makes the
     post-edit result unfalsifiable.
   - Then **classify every other hit** as picker-related or not, one line each,
     and record the classification. The tree carries ~25 unrelated `a`/`A`
     bindings (board All-filter, brainstorm Operations, settings Agent-Defaults
     tab, syncer failure-modal, codebrowser QA-agent, monitor auto-switch at
     `monitor/how-to.md:234` and `monitor/reference.md:49`). These are
     **intentional residual** — do not touch them. Any hit that classifies as
     picker-related is in scope and must be added to the Main-implementation
     steps before proceeding.

### Main implementation

1. **`website/content/docs/workflows/shadow-agent.md`**
   - Fix the indirect stale clause on **:100**: "grouped in their own dimmed
     section and left out of the select-all key" → re-word to the current
     behaviour (informational findings are dimmed and grouped; every disposition
     is set per row).
   - Add a new `### Reject a concern so it does not come back` subsection
     **after :100, before `## Advisory only` (:102)** — Hugo slug
     `#reject-a-concern-so-it-does-not-come-back`, which Steps 2 and 3 link to.
     Cover: `r` marks a row rejected (`✗`, mutually exclusive with forwarding);
     `R` opens the rejected list where `Space` marks entries for un-rejection
     and `Enter` returns them to the picker (**staged, not written** — the
     two-stage flow above: confirming the picker writes, cancelling it discards
     both staged rejections and staged un-rejections), and its two no-modal
     outcomes (empty store ⇒ "No previously rejected concerns
     for this task"; no task id ⇒ the warning that the store is unavailable and
     rejections made here will not be kept); rejections persist per task in a
     local, git-ignored store that is pruned when the task archives; the next
     review round drops substantively-matching rejected concerns *even when
     reworded* and reports `Suppressed N previously-rejected concern(s).`;
     fail-open (unsure ⇒ kept with a reason); an unresolvable task id ⇒
     suppression skipped and everything emitted, plus the distinct post-confirm
     "Rejections not persisted" refusal in the TUI.
   - **Do not rename** `### Forward concerns to the followed agent` — no inbound
     anchors, but keep it as the sibling heading.

2. **`website/content/docs/tuis/minimonitor/how-to.md`**
   - Rewrite the stale sentence in **:165** removing `a` / `A` entirely.
   - Add rejection prose to the `### How to Pick Shadow Concerns` section
     (:156-178): the tri-state and its glyphs, `r`, `R` + `Space`/`Enter`, the
     **two-stage flow** (marks are staged; confirming the picker writes,
     cancelling discards), what persists, the next-round suppression, `R`'s two
     no-modal outcomes (empty store vs. no task id — so neither reads as a dead
     key), and the distinct post-confirm "Rejections not persisted" refusal.
   - **Add the deep link** that makes the new workflow section reachable:
     `[…]({{< relref "/docs/workflows/shadow-agent" >}}#reject-a-concern-so-it-does-not-come-back)`
     in that new prose. This page already relrefs the workflow page at :154 and
     already uses relref-with-fragment elsewhere, so the pattern is established.
   - Extend the keybinding-table `c` row (**:276**) parenthetical from
     "(inside the picker, `u` shows …)" to also name `r` and `R` as picker-internal.
   - **Do not rename** `### How to Pick Shadow Concerns` — four inbound anchor
     links target `#how-to-pick-shadow-concerns`.

3. **`website/content/docs/tuis/monitor/how-to.md`**
   - Rewrite the stale sentence in **:195** removing `a` / `A`.
   - Add the equivalent rejection prose to `### How to Pick Shadow Concerns`
     (:185-205), including the **two-stage flow**, `R`'s two no-modal outcomes,
     and the distinct post-confirm "Rejections not persisted" refusal.
   - **Add the same deep link** to
     `{{< relref "/docs/workflows/shadow-agent" >}}#reject-a-concern-so-it-does-not-come-back`
     (this page already relrefs the workflow page at :183).
   - Add an explicit note that the picker's `r` / `R` are modal-scoped and do not
     collide with monitor's global `r` (refresh) / `R` (restart) — this is the one
     page where a reader can hit that confusion.
   - **Do not rename** the heading (`:63` and `shadow-agent.md:100` link to it).

4. **`website/content/docs/tuis/monitor/reference.md`**
   - Extend the `c` row (**:35**) parenthetical to name `r` / `R` as
     picker-internal keys, mirroring minimonitor.
   - **Add no new global rows.** Leave `:33` (`R` restart), `:45` (`r` refresh),
     `:49` (`a` auto-switch) untouched.

5. **`website/content/docs/tuis/minimonitor/_index.md`** (scope addition — see
   verification-pass item 2)
   - Add one clause to the picker summary at **:79** so it names rejection and
     points at the how-to anchor, instead of describing the picker as
     copy-only.

6. **`aidocs/framework/shadow_agent.md`**
   - New `## Concern rejection store` section inserted **between :350 and :352**
     (after Feedback freshness, before Configuration). Cover: store path and
     record format, the helper's subcommands as *internal machinery* invoked by
     the TUIs and producers, the TUI write path (staged in the modals and
     written only on picker confirm: `add … --producer picker`, the `remove`
     un-reject path, the 2/3/4 exit-code vocabulary and its toasts), the
     producer consult path (plain `list`, the three-outcome contract, fail-open,
     the `Suppressed N …` report), and archive-time pruning.
   - **Frame it as producer-side filtering, never a gate.** The file's own
     no-gating principle (`## Phase detection (deferred)`, :377-401 — "Anything
     that inspects the followed agent's state to decide whether the user may
     proceed is the shape this rule forbids") must not be contradicted:
     suppression removes items from the shadow's *own* output; it never decides
     whether the user may proceed, and the store can never become a block (`add`
     only accepts `- [` marker lines, so no fence can be stored).
   - Add one sentence to the **Step 2** bullet (:110) and one to the
     sub-procedure list (:111-144) noting that every emitting sub-procedure
     consults the rejection store before emitting a block.

### Post-phase (risk mitigations)

1. `[keys_match_source]` After the edits, check every key, glyph, and quoted
   string written into the six pages against current source: `_CONCERN_HELP_FULL`
   (`monitor_shared.py:2124-2127`), `ConcernPickerModal.BINDINGS` (:2394-2401),
   `_CONCERN_MARKS` (:1907-1911), `RejectedStoreModal` BINDINGS and footer
   (:2299-2303, :2331-2334), the toast strings (:681-732), and the
   `Suppressed N previously-rejected concern(s).` line in
   `.claude/skills/aitask-shadow/concern-format.md`. Include the **conditional**
   surfaces, not just the happy path: `action_show_rejected`'s three outcomes
   (:2610-2633) and the post-confirm refusal (:690-693) must each match their
   source string. Also re-walk the **write path** —
   `RejectedStoreModal.action_confirm` (:2346-2347) →
   `_on_rejected_view_closed` (:2635-2644) → `_result()` (:2603-2608) →
   `apply_concern_pick_result` (:674-701) — and confirm no page claims a store
   write happens before the picker itself is confirmed. Additionally confirm
   `website/content/docs/tuis/monitor/reference.md` gained **no** new `r` / `R`
   row and its lines 33 / 45 / 49 are byte-identical to HEAD
   (`git diff HEAD -- website/content/docs/tuis/monitor/reference.md`). Any
   divergence is a doc defect to fix here, not a source defect.

2. `[anchor_integrity]` After the edits, confirm both
   `### How to Pick Shadow Concerns` headings are unrenamed and that all four
   inbound links still target `#how-to-pick-shadow-concerns`
   (`website/content/docs/workflows/shadow-agent.md:100` ×2,
   `website/content/docs/tuis/minimonitor/_index.md:79`,
   `website/content/docs/tuis/monitor/how-to.md:63`). Then confirm the **new**
   anchor is reachable: Step 1's `### Reject a concern so it does not come back`
   must produce the Hugo slug `reject-a-concern-so-it-does-not-come-back`, and
   the two deep links added by Steps 2 and 3 must target exactly that slug. If
   the generated slug differs from the assumed one, update the two links to
   match the heading — never rename the heading to match a link.

## Verification

1. **Stale sweep — whole docs tree, positive control first, then classify.**
   The pattern must catch both prose wordings *and* table rows, across the whole
   tree rather than the three picker paths:
   ```bash
   grep -rniE '\*\*a\*\*|\*\*A\*\*|select-all|select all|copy all|toggle all|\| `a` \|| `A` \|' \
     website/content/docs/ aidocs/ README.md
   ```
   **Proven during planning:** it returns the three picker lines to fix
   (`shadow-agent.md:100`, `monitor/how-to.md:195`,
   `minimonitor/how-to.md:165`) plus ~25 unrelated `a`/`A` bindings in other
   TUIs. Post-edit, re-run the **same** command and diff against the pre-edit
   list: the only permitted change is the disappearance of those three lines.
   Every surviving hit must already appear in the pre-phase classification as
   non-picker. **Do not expect an empty result** — an empty result would mean
   the pattern broke, not that the docs are clean.

2. **Anchor integrity** — the `### How to Pick Shadow Concerns` headings in both
   how-to pages are unchanged, and the four inbound links
   (`shadow-agent.md:100` ×2, `minimonitor/_index.md:79`, `monitor/how-to.md:63`)
   still name `#how-to-pick-shadow-concerns`. Plus the two **new** deep links
   from the TUI how-to pages resolve to the new workflow-page section's actual
   generated slug.

2b. **`R`'s three outcomes are all documented** on both how-to pages and the
   workflow page: list opens · empty store notice · no-task-id warning; and the
   no-task-id warning is stated as distinct from the post-confirm "Rejections
   not persisted" refusal. A page documenting only the happy path fails this
   check.

2c. **The two-stage flow is stated wherever `Enter` is described.** No page may
   say the rejected list's `Enter` un-rejects, applies, or persists anything on
   its own. Each must say the marks are staged and written only when the picker
   itself is confirmed, and that cancelling the picker discards both staged
   rejections and staged un-rejections. Grep the edited pages for `un-reject`
   and `Enter` and read every hit.

3. **No global-table contamination** — `reference.md` gained no `r` / `R` row,
   and its existing `a` / `r` / `R` rows are byte-identical to HEAD.

4. **Build** — `cd website && hugo build --gc --minify` completes clean.

5. **Read-through** — re-read all six edited passages end-to-end against the
   "Verified source facts" list above for coherence and current-state-only prose
   (no "previously", no version history), per
   `aidocs/framework/documentation_conventions.md`.

## Risk

Levels below are the **post-inline reassessment**: they describe the plan as
approved, with the three confirmed inline phases included.

### Code-health risk: low

- Renaming a picker heading would silently break four inbound anchor links —
  Hugo does not validate fragments, so the breakage ships invisibly · severity:
  low (residual — addressed by inline post-phase anchor_integrity) ·
  → mitigation: inline post-phase anchor_integrity
- Documenting the picker's `r` / `R` as global keys would contradict monitor's
  real global bindings (`r` refresh, `R` restart) and mislead users · severity:
  low (residual — addressed by inline post-phase keys_match_source, which also
  pins reference.md lines 33/45/49 byte-identical) ·
  → mitigation: inline post-phase keys_match_source

### Goal-achievement risk: low

- An incomplete stale sweep: the two stale passages are worded differently, so a
  naive grep reports a false clean · severity: low (residual — the pre-phase
  proves the pattern matches all three known passages before any edit) ·
  → mitigation: inline pre-phase stale_sweep_positive_control
- The surface list proved incomplete once already (a fifth page surfaced during
  verification), so other pages may still describe the picker · severity: low
  (residual — the proven sweep pattern is run over whole directories, not the
  enumerated file list) · → mitigation: inline pre-phase
  stale_sweep_positive_control
- Documented keys / strings could drift from source if paraphrased · severity:
  low (residual — every documented key, glyph and quoted string is checked
  against current source) · → mitigation: inline post-phase keys_match_source
- Documenting only a key's happy path makes its conditional outcomes read as a
  broken shortcut — `R` opens no modal when the store is empty or the pane has
  no task id · severity: low (residual — Verification check 2b requires all
  three `R` outcomes plus the distinct post-confirm refusal on every page that
  documents `R`) · → mitigation: inline post-phase keys_match_source
- Describing the rejected list's `Enter` (labelled "Un-reject marked") as
  applying the change would misstate a two-stage flow, so a user who marks,
  presses `Enter`, then cancels the picker would wrongly believe the concerns
  were restored · severity: low (residual — Verification check 2c forbids any
  page from claiming a write before the picker is confirmed, and
  keys_match_source re-walks the write path) · → mitigation: inline post-phase
  keys_match_source

### Planned mitigations
- timing: pre-phase | name: stale_sweep_positive_control | type: documentation | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — differently-worded stale passages defeat a naive sweep, and the surface list has already proved incomplete | desc: prove the sweep pattern matches all three known stale passages before any edit, and run it over whole directories
- timing: post-phase | name: keys_match_source | type: documentation | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — picker r/R misdocumented as global keys; goal-achievement — paraphrased key/string drift | desc: check every documented key, glyph and quoted string — including R's three conditional outcomes and the post-confirm refusal — against current source, and confirm reference.md gained no new global rows
- timing: post-phase | name: anchor_integrity | type: documentation | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a renamed heading silently breaks four inbound anchor links | desc: confirm both picker headings are unrenamed and all four inbound anchors still resolve

## Pre-phase execution record (`stale_sweep_positive_control`)

Run before any edit. The whole-tree pattern returned **28 hits**, including all
three required targets — positive control satisfied:

- `website/content/docs/tuis/minimonitor/how-to.md:165` — **picker (fix)**
- `website/content/docs/tuis/monitor/how-to.md:195` — **picker (fix)**
- `website/content/docs/workflows/shadow-agent.md:100` — **picker (fix, indirect)**

Classification of the other 25 — all **intentional residual**, none picker-related:

| count | surface | binding |
|---|---|---|
| 6 | brainstorm (`_index`, `how-to` ×3, `reference` ×3 → 6 total) | `A`/`a` Operations dialog |
| 5 | settings (`how-to` ×2, `_index`, `reference` ×2) | `a` Agent Defaults tab |
| 4 | board (`how-to` ×2, `reference` ×2) | `a` All-tasks filter |
| 2 | syncer `_index` | `a` re-open failure modal |
| 2 | codebrowser (`how-to`, `reference`) | `a` launch QA agent |
| 2 | monitor (`how-to:234`, `reference:49`) | `a` auto-switch mode |
| 1 | `skills/aitask-review.md:26` | `/aitask-review` findings "select all" |
| 2 | `aidocs/unified_artifact_design.md:60`, `aidocs/framework/sed_macos_issues.md:255` | not keybindings (artifact table row; GNU `sed` `a` command) |

No hit classified as picker-related beyond the three already in scope, so no
Main-implementation step was added.

## Final Implementation Notes

- **Actual work done:** All six planned surfaces edited (+122/−6). The three
  stale picker passages were removed, the rejection feature documented on the
  workflow page (new `### Reject a concern so it does not come back`) and both
  TUI how-to pages, the two `c` keybinding-table rows extended to name `r`/`R`
  as picker-internal, `minimonitor/_index.md` brought in line, and
  `aidocs/framework/shadow_agent.md` gained a `## Concern rejection store`
  section (+90) plus the Step 2 and sub-procedure-list sentences.

- **Deviations from plan:** None in scope. The planned two deep links became
  **three** — `minimonitor/_index.md` also links the new anchor, since Step 5
  had it naming rejection anyway and a bare mention with no target would have
  been the weakest of the five surfaces.

- **Issues encountered:**
  - The `list --machine` wire format is `REJECTED:r<id>|…` (ids `r`-prefixed),
    but the helper's own header comment at `aitask_shadow_rejected.sh:61`
    documents it as `REJECTED:<id>|…`. The aidocs draft followed the comment and
    was corrected against the `printf` at `:339`. **The helper's header comment
    is itself imprecise** — recorded under upstream defects.
  - A verification grep for check 2b used BRE with literal `(a|b)` parens and
    returned a false zero on all three pages. Re-run with `-E` it passed. The
    plan's own rule — prove the pattern matches before trusting a zero — applied
    to the checks as much as to the sweep.
  - `grep -r` returns files in non-deterministic order, so a raw pre/post `diff`
    of the sweep output showed spurious churn. Comparing **per-file hit counts**
    instead gave the clean, meaningful result (3 lines gone, nothing else moved).

- **Key decisions:**
  - **`r`/`R` are documented as modal-scoped only, never as global table rows.**
    `ait monitor` already binds `r` = refresh (`reference.md:45`) and `R` =
    restart task (`:33`) globally; adding rows would have been factually wrong.
    `monitor/how-to.md` carries an explicit callout about the overlap because it
    is the one page where a reader can hit the confusion.
  - **The two-stage write path is stated on every page that mentions `Enter`.**
    The rejected-list modal writes nothing; only confirming the *picker*
    persists, and cancelling discards both staged sets.
  - **All three `R` outcomes are documented**, not just the happy path, so the
    empty-store and no-task-id cases do not read as a dead key.
  - **The aidocs section is framed as producer-side filtering, never a gate**,
    with an explicit cross-reference to the file's own anti-gating principle.
  - **The helper is documented as internal machinery in aidocs only** — no
    user-facing CLI for `add`/`list`/`remove`/`prune` on the website.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_shadow_rejected.sh:61` — the usage/header comment documents the machine format as `REJECTED:<id>|<ts>|<producer>|<marker line>`, but `cmd_list` at `:339` emits `REJECTED:r%s|…` with an `r`-prefixed id. A consumer written against the comment would build the wrong entry ids for `remove`.

- **Notes for sibling tasks:**
  - **t1427_5 (manual verification):** the user-visible contract now documented
    and worth exercising — `r` rejects (`✗`), `R` has **three** outcomes (list /
    empty-store notice / no-task-id warning), marks are **staged** until the
    picker is confirmed and discarded on `Esc`, and the next round reports
    `Suppressed N previously-rejected concern(s).`
  - The picker's `r`/`R` never collide with monitor's global `r`/`R` because
    Textual does not dispatch App-level bindings under a `ModalScreen`
    (pinned by `tests/test_monitor_modal_space_dispatch.py`).

Post-implementation cleanup, archival, and merge follow **Step 9
(Post-Implementation)** of the task workflow.
