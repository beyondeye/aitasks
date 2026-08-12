---
Task: t1493_shadow_recheck_rounds_leave_stale_concerns_in_picker.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
---

# p1493 — Recheck rounds must re-emit a block, and the picker must judge block age

## Context

Observed live on 2026-08-11 (session `thinking_back`, window `agent-pick-45_9`,
Codex shadow `%183` of a Claude pane `%178`): after the shadow's first
plan-challenge round, three successive free-text `refetch and recheck` rounds
each re-entered the skill and answered in **prose only** — no fences, no items —
including one round carrying a real, new, actionable concern. Pressing `c`
therefore re-offered round 1's concerns, and showed them as **current**, because
each refetch had restamped `@aitask_shadow_analyzed_at`.

Two independent defects, one symptom:

1. **Producer:** a recheck ask is not routed. It reads as a conversational
   follow-up to the previous analysis, so the sub-procedure's emit step is never
   re-entered.
2. **Consumer:** "fresh" is keyed on when the shadow last *looked*
   (`@aitask_shadow_analyzed_at`), never on when the newest block was
   *produced*. A refetch that emits nothing still clears the staleness warning.

Intended outcome: every review round the shadow runs produces a fenced block
carrying that round's header, and the picker/auto-offer can tell — independently
of the read stamp — that the newest block predates the followed agent's current
state, with "cannot tell" as its own visible state rather than silence.

## Verified findings (do not re-derive)

These correct several assumptions in the task body, which was written before
t1159_1 landed (commit `fabd8e615`).

- **The "omit the block entirely" wording is already gone from all four
  producers.** t1159_1 replaced it with the metadata-only clean-round block and
  installed a negative guard (`_retains_omit_block_rule` /
  `test_no_producer_retains_the_omit_block_rule`,
  `tests/test_concern_parser.py:1348`). **Defect 1 cause (1) is closed** — no
  producer edit is needed for clean rounds.
- **The producers already honour an externally named round.** Each of the four
  states, at both rule sites: *"Take N from the request when it names a round
  ('recheck round N'), else count from 1 within this conversation"*
  (`plan-challenge.md:80-91,134-145`; `plan-assumptions.md:84-95,137-148`;
  `plan-diagnose-errors.md:74-85,122-133`; `impl-challenge.md:398-409,459-470`).
  Nothing ever names N, because nothing routes a recheck.
- **`SKILL.md.j2` Step 3 (lines 212-284) has no recheck entry.** `grep -in
  "recheck\|re-review\|look again"` over the template returns zero hits. The
  routing list is 2 inline entries + 7 structured-analysis entries. Step 0
  (lines 42-59) derives the greeting *from Step 3*, so a new entry becomes an
  advertised capability with no second edit.
- **`reviewed_at` is never converted to a time anywhere in the tree.** Its only
  two consumers treat it as an opaque string: a dedup-key fragment
  (`minimonitor_app.py:2387`) and a display suffix built by string slicing
  (`format_block_meta`, `monitor_shared.py:2190-2206`, which discards the date
  entirely via `rsplit("T", 1)[1]`).
- **Clock trust is sound.** The producer sources `reviewed_at` from `date -u
  +%Y-%m-%dT%H:%M:%SZ` in the shadow pane; `get_last_change_wall` returns
  `time.time()`-derived wall epoch in the monitor process. Both run on the same
  host, so a direct epoch comparison is valid. `_META_LINE`
  (`concern_parser.py:204-206`) captures the timestamp as `(?P<at>.*?)` — **no
  shape validation** — so any parse must be strict and fail to `None`.
- **A clean newest block already blocks access to an older one.** All region
  scoping goes through `_last_block_region`, which uses `text.rfind(_OPEN)`
  (`concern_parser.py:292`); the forgiving `require_close=False` path only
  widens the *end* of the newest region, never reaches back to a previous
  fence. `action_pick_concerns` short-circuits a certified metadata-only block
  at `minimonitor_app.py:2252-2261` with "Clean review (round N)". **Resolves
  the third open question in the task's "Direction to assess" — no code change
  needed.**
- **minimonitor's `c` path reads a tick-cached staleness that can be two ticks
  old**, because `_update_shadow_freshness` is throttled to odd ticks
  (`minimonitor_app.py:2344-2346`) and `action_pick_concerns` reuses the cache
  (`:2282`).

## Design

### The three signals (requirement 4)

The change introduces a **third** freshness concept. All three must be named
wherever any is documented, and each surface must say which it uses:

| signal | question | implementation |
|---|---|---|
| **block identity** | has *this block's text* changed? | `concern_block_signature` (`concern_parser.py:634`) |
| **read recency** | did the shadow *look* after the agent's last change? | `compute_shadow_staleness` (`monitor_core.py:507`) |
| **block age** *(new)* | was this block *produced* after the agent's last change? | `compute_block_age_staleness` (new, `monitor_core.py`) |

Read recency and block age are joined **fail-safe** and are never conflated in
the source: they are computed separately and combined by one named function.

### Part A — Producer: route recheck asks (user-confirmed: routing entry only)

Single edit to `.claude/skills/aitask-shadow/SKILL.md.j2`, a new bullet in the
**Structured analyses** list of Step 3, inserted after the `impl-challenge.md`
entry (currently ends line 263):

- **Trigger wording** (quoted so an agent matches on them): `"refetch and
  recheck"`, `"recheck round N"`, `"re-review"`, `"look again"`, `"check it
  again"`, `"is it fixed now"`, `"review it again after the changes"`.
- **Dispatch:** refetch the followed screen (Step 1), then **re-run the
  sub-procedure that produced the previous round** end-to-end — or, if there was
  no previous round in this conversation, resolve it with the existing
  phase-driven default ladder.
- **Load-bearing clause:** *a recheck is a full new review round, not a
  conversational follow-up. Never answer one in prose alone — always re-enter
  the sub-procedure and emit a fresh concern block carrying this round's header,
  even when the findings are unchanged, and even when the round is clean (the
  metadata-only block is the clean-round record).*
- **Round threading:** if the ask names a round ("recheck round N"), carry that
  N into the sub-procedure's round header; otherwise increment.

`"refetch and recheck round N"` is pinned as the **canonical injected phrase**
in `aidocs/framework/shadow_agent.md`, so t1159_2's `compose_recheck_prompt` has
a documented target to align with. This task edits no t1159_2 file.

Rejected: adding a fifth "always re-emit on a recheck" rule at both rule sites in
all four producers. The producers already mandate emitting a block on **every**
review including zero-concern rounds; the failure was that no review was *run*.
A fifth duplicated rule would grow exactly the drift surface
`concern-format.md:305-315` warns about while closing no gap.

### Part B — Consumer: block-age staleness

**B1. `concern_parser.py` — new pure helper**

```python
def parse_reviewed_at_epoch(reviewed_at: str) -> float | None:
    """Epoch seconds for a block header's ``reviewed_at``, or ``None``."""
```

Strict on the one documented shape `%Y-%m-%dT%H:%M:%SZ` (UTC), via
`datetime.strptime(...).replace(tzinfo=timezone.utc).timestamp()`. Everything
else — `""`, garbage, a different shape, a non-`Z` suffix — returns `None`
("cannot tell"), never a guess. Docstring states the same-host clock-trust
assumption explicitly.

**B2. `monitor_core.py` — two pure functions, beside `compute_shadow_staleness`**

```python
def compute_block_age_staleness(
    meta: "BlockMeta | None", last_change_wall: float | None, eps: float
) -> tuple[bool | None, float | None]:
```

Contract table (mirrors the `compute_shadow_staleness` docstring style):

| condition | result |
|---|---|
| `meta is None` (no header — every pre-t1159_1 block) | `(None, None)` |
| `reviewed_at` unparseable | `(None, None)` |
| followed pane not observed yet (`last_change_wall is None`) | `(None, epoch)` |
| `last_change_wall > epoch + eps` | `(True, epoch)` |
| otherwise | `(False, epoch)` |

Sync and pure — no tmux, no I/O. `eps` is the caller's refresh epsilon, same
value the read-recency compare uses.

```python
def combine_staleness(read: bool | None, block: bool | None) -> bool | None:
    """Fail-safe join: True wins, then None, then False."""
```

- either is `True` → `True`
- both are `False` → `False`
- otherwise → `None`

This is requirement 3 in one place: an unknown can never *clear* a warning, and
a pre-header block with a clean read stamp resolves to `None` ("cannot tell"),
never `False`.

**B3. Modal: tri-state banner (`monitor_shared.py`)**

- `ConcernPickerModal.__init__` widens `stale: bool = False` →
  `stale: bool | None = False`, and gains keyword-only `stale_detail: str = ""`.
- Render:
  - `stale is True` → existing `#concern-stale` red banner, text + detail
  - `stale is None` → **new** `#concern-stale-unknown` banner (`color: $warning`)
    — "⚠ Freshness unknown — cannot tell whether these concerns are current"
  - `stale is False` → neither (unchanged)
- New pure formatter, unit-testable and total over garbage:

```python
def format_staleness_detail(
    meta: "BlockMeta | None", block_stale: bool | None, age_seconds: float | None
) -> str:
    """" — round 2 was produced 4m12s before the agent's latest change", or ""."""
```

  Reuses `format_stale_duration` (`monitor_shared.py:828`). Its output reaches a
  markup-enabled `Static`, so the caller escapes it exactly as `_context_line`
  already escapes `format_block_meta` (`monitor_shared.py:2570`).

**B4. Call sites — all four (user-confirmed: both surfaces)**

Shared shape at each site: parse `meta`, obtain `last_change_wall` for the
followed pane, compute block age, combine with read recency, pass the tri-state.

1. `minimonitor_app.py` `action_pick_concerns` (~2280-2300). The cached
   `_shadow_feedback_stale` is reused when it is `True`/`False`; when it is
   `None` (throttled tick not yet run, or an indeterminate read) **recompute
   live** via `compute_shadow_staleness` — the user pressed `c` deliberately, the
   same reasoning that already pays for the deep re-capture at `:2226-2238`. This
   also removes the two-tick lag and stops the common "pressed `c` before the
   first tick" case from rendering as unknown. `get_last_change_wall` is sync and
   cache-backed: **no new tmux traffic.**
2. `minimonitor_app.py` `_maybe_offer_concerns` toast (~2393-2397): `stale_suffix`
   becomes tri-state — `True` → `" (⚠ STALE — agent moved on)"`, `None` →
   `" (⚠ freshness unknown)"`, `False` → `""`.
3. `monitor_app.py` `c` path (~3047-3072): drop `stale=bool(stale)`; combine and
   pass the tri-state plus `stale_detail`.
4. `monitor_app.py` auto-offer toast (~1156-1180): same tri-state suffix.

Sites 3 and 4 already have `eps` and the followed `pane_id` in scope, so the
insertion is local.

This resolves **t1461**'s `bool(stale)` tri-state bullet for the picker and both
toasts. t1461 keeps its other two bullets (the `$$`-vs-`pane_pid` sweep and the
sync `discover_window_panes`); a note is added to this plan's Final
Implementation Notes naming what t1461 no longer needs to do.

### Part C — Docs (requirement 4)

- `.claude/skills/aitask-shadow/concern-format.md`
  - add `parse_reviewed_at_epoch` to the parser-export list (~324-328);
  - add a **block age** row to the `## Trigger vs. action contract` table (~224);
  - rewrite `## Staleness` (335-346) from two signals to **three**, naming which
    surface uses which.
- `aidocs/framework/shadow_agent.md`
  - new `### Block age vs read recency` subsection under `## Feedback freshness`
    (after line 361), with the three-signal table, the tri-state/fail-safe rule,
    the same-host clock-trust assumption, and the canonical recheck trigger
    phrase for t1159_2.

Requirement 5 (advisory-only) is preserved by construction: nothing in this
change writes to the followed pane.

## Implementation steps

### Pre-phase (risk mitigations)

- **`enumerate_staleness_sinks`** — before touching any call site, enumerate
  every place that *produces*, *renders* or *asserts* a staleness verdict, and
  work from that list rather than from this plan's four named sites:

  ```bash
  grep -rn "compute_shadow_staleness\|_shadow_feedback_stale\|stale_suffix\|\
stale=\|#concern-stale\|#mini-shadow-stale" \
    .aitask-scripts/monitor/ tests/
  ```

  Every hit must end up in one of three buckets: *wired to the combined
  tri-state*, *deliberately unchanged (say why)*, or *test to update*. A sink
  left in neither bucket is the parallel-surface defect this pre-phase exists to
  prevent. Record the bucketed list in the Final Implementation Notes.

1. `concern_parser.py`: add `parse_reviewed_at_epoch` (+ `datetime` import).
2. `monitor_core.py`: add `compute_block_age_staleness` and `combine_staleness`
   directly after `compute_shadow_staleness`, with contract-table docstrings.
3. `monitor_shared.py`: add `format_staleness_detail`; widen
   `ConcernPickerModal.__init__`; add the `#concern-stale-unknown` branch and CSS.
4. `minimonitor_app.py`: wire sites 1 and 2 (incl. the live recompute when the
   cache is `None`).
5. `monitor_app.py`: wire sites 3 and 4.
6. `.claude/skills/aitask-shadow/SKILL.md.j2`: add the recheck routing entry.
7. Regenerate the three entry-point goldens (`impl-challenge.md` is untouched, so
   the proc goldens stay as they are):
   ```bash
   PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
   for profile in default fast remote; do
     "$PYTHON" .aitask-scripts/lib/skill_template.py \
       .claude/skills/aitask-shadow/SKILL.md.j2 \
       aitasks/metadata/profiles/$profile.yaml claude \
       > tests/golden/skills/aitask-shadow/SKILL-${profile}-claude.md
   done
   ```
   Then refresh the live rendered closures: `./.aitask-scripts/aitask_skill_rerender.sh <profile>`
   once per profile (`default`, `fast`, `remote`).
8. Docs (Part C).
9. Tests (below).

### Post-phase (risk mitigations)

- **`unknown_banner_noise_check`** — after wiring and before review, render the
  picker for real in all three states and confirm the new banner is readable
  rather than merely present:
  - `stale=None` with a non-empty `stale_detail`, at both
    `_PICKER_NARROW_MIN_WIDTH` and `_PICKER_MIN_COLS`, via the composited-strip
    helper (`_screen_rows` / `_flat_text` in `tests/test_concern_picker_modal.py`)
    — the actionable counts and the `u raw` affordance must both still be on
    screen.
  - Confirm exactly one banner is mounted per state (`#concern-stale` XOR
    `#concern-stale-unknown`), never both and never zero when `stale is not False`.
  - Judge the legacy case: a pre-t1159_1 block on a live pane now shows
    "freshness unknown" indefinitely. If that reads as noise rather than as
    honest uncertainty, say so in the Final Implementation Notes and propose the
    wording change — do **not** silently soften it to "current", which is the
    defect this task exists to fix.

## Verification

### New tests

- **`tests/test_concern_parser.py`**
  - `TestParseReviewedAtEpoch` — the documented shape converts exactly; `""`,
    prose, a `+00:00` offset, a date-only string, and markup garbage all give
    `None`. Pin one concrete epoch so a timezone-dependent implementation fails.
  - `TestRouterRoutesRechecks` — drift guard over `SKILL.md.j2` **and** the
    rendered `fast` variant (mirroring `TestRenderedShadowDocsKeepTheGuarantees`,
    line 1568). Module-level predicate `_routes_recheck_asks(text)` over
    whitespace-collapsed text, requiring the routing directive phrase, the
    literal `refetch and recheck`, and `recheck round`. **Negative control** on
    synthetic text per the established pattern (`TestProducerRoundHeaderRule`
    line 1362): assert the predicate is `False` on text missing each part and
    `True` only when all are present.
  - The producer set is unchanged, so `test_producer_set_is_the_known_set` in
    all four existing classes must stay green (`SKILL.md.j2` is not `*.md`, so
    the glob does not pick it up — assert this stays true).
- **`tests/test_shadow_seam.py`**
  - `ComputeBlockAgeStalenessTests` — one test per contract-table row, using
    `assertIs` so `None` and `False` are provably distinguishable (the pattern of
    `test_none_is_distinguishable_from_false`, line 341+).
  - `CombineStalenessTests` — the full 3×3 table, asserted exhaustively.
- **`tests/test_minimonitor_concern_action.py`** (extend `ShadowFreshnessTests` /
  `ActionPickConcernsTests`, reusing `_fresh_app` at line 876)
  - **The task's headline scenario:** block header `reviewed_at` = T0, followed
    pane `get_last_change_wall` = T1 > T0 + eps, shadow `@aitask_shadow_analyzed_at`
    = T2 > T1 (so read recency says *current*) ⇒ the pushed modal must receive
    `stale is True`. Assert on the **pushed modal instance**, following
    `test_pushed_modal_carries_the_block_meta` (line 307) — an isolated helper
    test stays green if the caller drops the wiring.
  - **Negative control for requirement 3:** a pre-header block (no
    `reviewed_at`) with a clean read stamp ⇒ the modal receives `stale is None`,
    **not** `False`. Use `assertIsNone`, and separately assert
    `modal._stale is not False`.
  - Live recompute: with `_shadow_feedback_stale = None` and a stale-looking
    stamp, `c` recomputes and yields `True` (spy `get_pane_option` call count).
  - Toast suffixes for all three states.
  - Mind the every-other-tick throttle (`test_freshness_throttled_to_every_other_tick`,
    line 981) when a test drives more than one tick.
- **`tests/test_concern_picker_modal.py`**
  - `stale=None` renders exactly one `#concern-stale-unknown` and zero
    `#concern-stale`; `stale=True` renders the inverse; `stale=False` renders
    neither. Drive the composited render (`_screen_rows`), per the file's rule
    that a `render()` assertion would miss a `MarkupError`.
  - `stale_detail` built from a markup-shaped `reviewed_at` renders as literal
    text instead of crashing (mirrors
    `test_markup_shaped_reviewed_at_renders_instead_of_crashing`, line 903).
  - Narrow-width budget at `_PICKER_NARROW_MIN_WIDTH` and `_PICKER_MIN_COLS`:
    the actionable counts stay visible with the unknown banner + detail present
    (mirrors `ConcernContextLineBudgetTests`, line 783).
- **`tests/test_monitor_concern_action.py`** — mirror the tri-state picker
  assertions and the block-age scenario for the full monitor. Its
  `_install_staleness` helper (line 305) patches the module symbol, so the
  block-age half must be driven through real `BlockMeta` + a stubbed
  `get_last_change_wall`, not through that patch.

### Suite / render

```bash
bash tests/test_skill_render_aitask_shadow.sh
./.aitask-scripts/aitask_skill_verify.sh
bash tests/run_all_python_tests.sh        # read ONLY the final stderr verdict line
```

`run_all_python_tests.sh` discards its status through a pipe — use
`set -o pipefail` or check `${PIPESTATUS[0]}`.

### Manual (live) — the producer half cannot be unit-proven

A prompt-file routing entry is an instruction, not an enforcement point. The
only real proof is a live session: bind a shadow to a followed agent, run one
review round, change the followed pane, then send `refetch and recheck round 2`
and confirm (a) a fresh fenced block appears carrying `Round: 2 @ …`, and (b)
before that block appears, `c` reports the round-1 concerns as stale rather than
current. See the mitigation below.

## Step 9 (Post-Implementation)

Standard: merge to `main`, archive `t1493` and this plan. No folded tasks, no
children. Note in the Final Implementation Notes which t1461 bullet this task
retired.

## Out of scope

- The auto-recheck loop itself (t1159_2), the spin-off arm (t1159_3), the badge
  currency rule (t1448).
- t1461's remaining bullets: the `#{pane_pid}`-vs-`$$` sweep and the sync
  `discover_window_panes`.
- Changing the concern-block grammar or the `[priority | region]` bracket.
- Porting to `.agents/` / `.opencode/`: those trees carry only a `SKILL.md`
  stub; the sub-procedures and template are rendered from the Claude tree, so
  step 7's rerender is the whole port. Confirm during implementation and spawn a
  follow-up only if a hand-maintained copy is found.

## Risk

### Code-health risk: medium
- Widening a **shared, load-bearing modal** (`ConcernPickerModal.stale`) from
  `bool` to a tri-state changes visible behaviour on both TUIs: a case that
  previously rendered no banner can now render the "freshness unknown" one.
  · severity: medium · → mitigation: inline post-phase `unknown_banner_noise_check`
- Introducing a **third** freshness concept next to two existing ones invites
  future conflation, the exact failure `concern-format.md` already warns about
  for the first two. · severity: medium · → mitigation: requirement-4 doc work is
  a plan step, not deferred
- Four call sites across two apps must stay in agreement; a partially-wired
  surface is the parallel-surface defect class.
  · severity: medium · → mitigation: inline pre-phase enumerate_staleness_sinks

### Goal-achievement risk: medium
- **The producer half is unverifiable by automated test.** The routing entry is
  an LLM instruction; the drift guard proves the text is present, never that a
  live shadow obeys it. The observed defect was precisely an agent choosing
  prose over the procedure. · severity: high · → mitigation: live_recheck_round_positive_control
- The consumer half is a genuine, testable defense that holds even if the
  producer never complies — so the task's user-visible goal (stale concerns stop
  reading as current) is delivered regardless. · severity: low · → mitigation: none needed
- `combine_staleness` returning `None` for every pre-t1159_1 block means the
  "freshness unknown" banner appears on legacy panes until a new round is
  emitted. Intended by requirement 3, but a UX regression if it is noisy.
  · severity: low · → mitigation: inline post-phase unknown_banner_noise_check

### Planned mitigations
- timing: pre-phase | name: enumerate_staleness_sinks | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: four call sites must stay in agreement (code-health) | desc: grep out every staleness producer/renderer/assertion and bucket each hit as wired, deliberately-unchanged, or test-to-update before any wiring.
- timing: post-phase | name: unknown_banner_noise_check | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: shared-modal behaviour change + legacy-block banner noise (code-health, goal-achievement) | desc: render the picker in all three staleness states at both narrow widths, confirm exactly one banner per state and that the counts stay readable.
- timing: after | name: live_recheck_round_positive_control | type: manual_verification | priority: high | effort: medium | inline_risk: high | added_complexity: high | addresses: the routing entry is an LLM instruction no automated test can prove (goal-achievement) | desc: live shadow session — run round 1, change the followed pane, send "refetch and recheck round 2", confirm a fresh Round 2 block is emitted and that `c` reported round 1 as stale beforehand.

### Reassessment after inline insertion

Re-run of the two-axis evaluation against the augmented plan (the two inline
phases are now plan steps): both levels stand at **medium**. The pre-phase
lowers the parallel-surface risk from a plan assumption to an executed sweep and
the post-phase converts the shared-modal UX change into a checked outcome, but
neither moves an axis to `low` — the widened shared-modal contract and the
unverifiable producer half are unchanged by them, and the latter is carried by
the spawned `after` mitigation rather than resolved in this plan.
