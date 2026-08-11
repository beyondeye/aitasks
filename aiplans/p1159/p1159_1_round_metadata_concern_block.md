---
Task: t1159_1_round_metadata_concern_block.md
Parent Task: aitasks/t1159_shadow_review_loop_automation.md
Sibling Tasks: aitasks/t1159/t1159_2_auto_recheck_loop.md, aitasks/t1159/t1159_3_spinoff_triage_arm.md, aitasks/t1159/t1159_4_docs_and_integration.md
Archived Sibling Plans: aiplans/archived/p1159/p1159_*_*.md
Worktree: . (current directory — profile 'fast', current branch)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-11 16:41
---

# Plan — t1159_1: Round metadata in the concern block

Parent design: `aiplans/p1159_shadow_review_loop_automation.md` (pinned decisions
restated below — do not reopen).

## Context

The shadow's concern block (`===AITASK-CONCERNS===` … `===END-CONCERNS===`)
carries no round number and no review time. Three consequences:

1. **Minimonitor's auto-offer is dedup-suppressed on repeat rounds.**
   `_maybe_offer_concerns` keys on the *parsed clipboard payload*
   (`minimonitor_app.py:2352-2355`), so a round-2 review that reaches the same
   conclusions produces no new hint — the user is never told the shadow
   re-reviewed.
2. **The picker cannot say which round produced the block** it is showing.
3. **t1448 (`depends: [1159, 1420]`) has no freshness key.** It is chartered to
   key its badge-currency notion off exactly the metadata this child adds.

This child adds the metadata end-to-end: grammar, parser accessor, producer
wording, the dedup lift, and picker display. Both the auto-recheck loop
(t1159_2) and the spin-off arm (t1159_3) consume it — t1159_2 derives the
`recheck round <N+1>` it injects from `parse_block_meta` of the previous block.

## Pinned decisions (user-confirmed at parent planning, 2026-08-11 — do not reopen)

- Header line **inside** the fences, immediately after the opening fence, before
  the first item: `Round: <N> @ <ISO-8601-UTC-with-seconds>Z`
  (e.g. `Round: 2 @ 2026-08-11T14:03:27Z`). **Seconds resolution is required** —
  a same-minute shadow restart must not reproduce a `(round, reviewed_at)` pair.
- **Never widen the `[priority | region]` marker bracket** (t1167 split-marker
  drop hazard). The header is a separate line, not a marker field.
- Round is mechanically anchored where possible: producers honor an externally
  supplied round when the request names one (`recheck round N`, sent by
  t1159_2), and self-count only for the first review / manual free-text
  rechecks. Timestamps are shell-sourced (`date -u +%Y-%m-%dT%H:%M:%SZ`), never
  estimated.
- **Clean reviews emit a METADATA-ONLY block** — fences with only the round
  header between them — so round numbering advances on clean rounds too.
  `has_concern_block` stays `False` for such a block (no items ⇒ no auto-offer),
  which is correct.
- Rejection suppression stays **task-scoped** (the t1427 store is untouched; no
  round field is added to it).

## Verification pass — findings against `main` (2026-08-11)

This plan was re-verified against the live tree. All file:line seams below were
confirmed. **Five corrections** to the plan as originally written:

1. **`impl-challenge.md` HAS per-profile goldens — the original plan said
   producers need none.** `tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md`
   are diffed by `tests/test_skill_render_aitask_shadow.sh` Test 1p, because
   `impl-challenge.md` is the one producer carrying Jinja
   (`shadow_impl_review_tier`). Editing it **requires regenerating those three
   goldens in the same commit** (`aidocs/framework/skill_authoring_conventions.md`
   → "Regenerate goldens after any `.md.j2` or closure edit"). The other three
   producers are in that test's `PROC_FILES_INVARIANT` list (Jinja-free, no
   goldens) — but Test 1i asserts they render byte-identically across
   profile × agent, so **do not introduce any Jinja into them**.
2. **The rendered surface needs its own guard.** `TestRenderedShadowDocsKeepTheGuarantees`
   (`tests/test_concern_parser.py:1091`) mirrors every authoring-dir producer
   rule against `.claude/skills/aitask-shadow-fast-/` — the surface the agent
   actually reads at runtime. The round-header rule needs a rendered counterpart
   there (same rationale as t1311's `test_every_rendered_producer_states_the_suppression_rule`),
   or a conditional that dropped the rule from one profile's render would leave
   the authoring guard green while the executed surface has no rule.
3. **`monitor_app.py` is a parallel picker surface the original plan missed.**
   The full monitor constructs `ConcernPickerModal` at `monitor_app.py:3008-3016`
   with `text` in scope, exactly as minimonitor does. It gets `block_meta` too.
   Its *auto-offer* needs no change: it dedups on `concern_block_signature`
   (`monitor_app.py:1111`, `:2977`, `:3003`), which hashes the whole block
   region and therefore already re-fires on a round bump — the dedup lift is
   free there and only minimonitor's payload-keyed dedup needs the explicit fix.
4. **`_last_block_region`'s `require_close` is keyword-only with NO default**
   (`concern_parser.py:235`: `def _last_block_region(text: str, *, require_close: bool) -> str | None`).
   Every call must pass it explicitly.
5. **The module docstring carries an entry-point table** (`concern_parser.py:49-78`)
   whose lead-in asserts the tiers differ "only on `require_close`". Adding a
   sixth entry point without a row there leaves the documented contract wrong.

Confirmed unchanged and load-bearing:

- `_scan_items` line 352: `if line.strip() and items:` — a non-blank, non-marker
  line seen while `items` is empty is **silently dropped**, no buffer, nothing
  appended. This is the parser-safety basis for the header slot. **Nuance:** a
  line that *looks* like a marker (`^\s*-\s+\[`, `_MARKER_START` at :126) is
  still recorded into `unrecovered` even before the first item — which is why
  the producer rule must state the header never itself begins `- [`.
- `has_concern_block` (`:453`) = `require_close=True` **and** ≥1 parsed item.
- `concern_block_signature` (`:493`) hashes the **whole region** after
  ANSI-strip → whitespace-collapse → strip. The header therefore changes it by
  design (the monitor's freshness badge re-hashes on a round bump).
- `from __future__ import annotations` is at `:80`, so `BlockMeta | None` in
  annotations is safe on the 3.8 floor this module targets.
- Metadata-only block through `_maybe_offer_concerns` (`minimonitor_app.py:2286-2345`):
  `has_concern_block` False → `block_head_truncated` False (both fences present)
  → `unrecovered_markers` `[]` → **silent return, no spurious warning.** Verified
  by reading the branch, not inferred.
- Producer examples are ```` ``` ```` fences containing item lines only — no
  sentinel fences anywhere (`plan-challenge.md:74-77`, `plan-assumptions.md:78-81`,
  `plan-diagnose-errors.md:67-70`, `impl-challenge.md:391-395`). The t1123
  `contains_any_concern_block` guard globs **every** `*.md` under the shadow dir,
  authoring and rendered.

### Round-2 review corrections (shadow concerns, all verified valid)

6. **The producers carry a contradictory omit-when-clean rule.** All four
   instruct the agent to emit **no** block on a clean review:
   `plan-challenge.md:120-122` and `impl-challenge.md:445-447` ("Emit the block
   **only when you have at least one concern**. If … genuinely clean, or
   suppression left you with nothing to forward, omit the block entirely and say
   so."), `plan-assumptions.md:123-124` (same shape, "at least one assumption
   worth forwarding"), `plan-diagnose-errors.md:107-109` (rules bullet) **and**
   its step-2 prose at `:39-40` ("**say so plainly and stop** — emit no concern
   block"). Adding the metadata-only directives without deleting these leaves
   both instructions live and the token-count guard green; an agent following
   the old rule emits no clean-round record. Step 2 now **replaces** all five
   sites, and the guard gains a negative assertion that the omit wording is gone.
7. **A metadata-only block would light the monitor's `!` badge forever.**
   `_has_fresh_concerns` (`monitor_app.py:2094-2106`) keys on
   `_concern_sig_offered` **only**; the offer pass marks an empty-parse block
   *examined* (`:1124-1126`) and returns with "The badge stands" (`:1131-1134`)
   — deliberate for *malformed* blocks, wrong for a valid clean-round block
   (non-None signature, nothing to pick, nothing to investigate). New step 3b
   marks a metadata-only block **offered** in the offer pass, so no toast and no
   standing badge, while `_concern_sig_latest` (the freshness input) is untouched.
8. **`reviewed_at` reaches a markup-enabled `Static` verbatim.**
   `#concern-context` (`monitor_shared.py:2529`) parses Rich markup; the repo
   documents this exact hazard at `:1548-1550` — "an unescaped `[/]` raises
   MarkupError and takes the modal down" — with `escape()` as the convention.
   A malformed header like `Round: 2 @ [/]` would crash the picker. Step 4 now
   escapes the suffix at the markup boundary and tests markup-shaped garbage.
9. **No test wired the callers to the modal.** The original verification tested
   `parse_block_meta`, `format_block_meta`, and `ConcernPickerModal` in
   isolation; omitting either caller's `block_meta=` argument would leave all of
   them green while that surface never shows round metadata. The action-flow
   tests in both TUIs now assert the **pushed modal instance** carries the meta.

## Pre-phase (risk mitigations)

1. **[narrow_width_context_budget]** Before touching `_context_line()`, add a
   characterization test to `tests/test_concern_picker_modal.py` that renders
   the picker's `#concern-context` `Static` at the `xnarrow` tier
   (`self.size.width <= _PICKER_NARROW_MIN_WIDTH`, see
   `ConcernPickerModal._apply_width_tier`, `monitor_shared.py:2557-2577`) and
   pins the visible text of the current two-partition line
   (`"N to address  ·  M informational  ·  forward or reject"`). Assert on the
   **composited strip** at that width, not on `_context_line()`'s return value —
   the return string is not what the user sees. Then, after step 4 lands, extend
   the same test to assert that with `block_meta` present the actionable counts
   are **still** visible at that width. If the round suffix pushes them off,
   shorten the suffix (drop the time, keep `round N`) rather than widening the
   modal. Addresses the code-health "shared modal / display budget" risk.

## Steps

### 1. Parser accessor — `.aitask-scripts/monitor/concern_parser.py`

Add beside the existing entry points:

```python
class BlockMeta(NamedTuple):
    round: int          # 1-based round the producer emitted
    reviewed_at: str    # verbatim text after '@' ("" when absent or empty)


_META_LINE = re.compile(
    r"^\s*Round:\s*(?P<round>\d+)\s*(?:@\s*(?P<at>.*?))?\s*$"
)


def parse_block_meta(capture_text: str) -> BlockMeta | None:
    region = _last_block_region(capture_text, require_close=False)
    if region is None:
        return None
    for line in region.splitlines():
        if not line.strip():
            continue
        match = _META_LINE.match(line)
        if match is None:
            return None
        return BlockMeta(
            int(match.group("round")), (match.group("at") or "").strip()
        )
    return None
```

- `require_close=False` is deliberate: the **same forgiving region** as
  `parse_concerns` (`:416`) / `block_region` (`:450`), so meta and concerns
  always describe the same (newest) block. Pass it explicitly — it is
  keyword-only with no default.
- **Only the first non-blank line** of the region is consulted. A `Round:` line
  anywhere later is body text by the item grammar; returning `None` there is the
  point (it makes the "header after an item" corruption visible instead of
  silently believed).
- Pure and fail-open: `reviewed_at` is verbatim and unvalidated. Input shape is
  the same wrap-joined, ANSI-free capture `parse_concerns` takes (no
  `strip_ansi` here — that belongs to `concern_block_signature`'s raw-capture
  tier).
- **Docstring must carry the t1448 consumer contract:** the freshness key is the
  `(round, reviewed_at)` **PAIR**. Round alone is not unique — a restarted
  shadow starts at 1 again.
- **Docstring must carry the parser-safety basis:** `_scan_items` (`:352`) drops
  a non-marker line before the first item, so `parse_concerns` /
  `has_concern_block` / `unrecovered_markers` are unaffected by the header. It
  **deliberately** changes `concern_block_signature` and `block_region`.

Also update the **module docstring** (`:1-79`): add a `Round header` bullet to
the format list (~`:25-47`), put the round line into the format example
(`:19-23`), add a `:func:`parse_block_meta`` row to the entry-point table
(`:53-78`), and amend the lead-in at `:49-51` ("The first two share
`_last_block_region`, diverging only on `require_close`") so it stays true with
a sixth entry point.

### 2. Producers — both rule sites × 4 files

Files: `.claude/skills/aitask-shadow/plan-challenge.md`, `impl-challenge.md`,
`plan-assumptions.md`, `plan-diagnose-errors.md`.

Mirror the rejection-suppression inlining pattern exactly (bolded emit-paragraph
directive + rules-list bullet). **Insertion point: immediately after the example
code fence, before the rules list** — this keeps the existing
"The concern lines themselves look like:" lead-in adjacent to its example.

| file | example fence ends | rules list starts | indent |
|---|---|---|---|
| `plan-challenge.md` | 77 | 79 | 3-space / 5-space cont. |
| `plan-assumptions.md` | 81 | 83 | 3-space / 5-space cont. |
| `plan-diagnose-errors.md` | 70 | 72 | 3-space / 5-space cont. |
| `impl-challenge.md` | 395 | 397 | **column 0** / 2-space cont. |

**Site A — bolded emit directive** (indent per the table):

> **Emit a round header as the first line inside the block.** Immediately after
> the opening fence — before the first `- [` marker — emit exactly one line of
> the form `Round: <N> @ <timestamp>`, for example
> `Round: 2 @ 2026-08-11T14:03:27Z`. If the request that triggered this review
> names a round ("recheck round N"), use that N; otherwise N is 1 for the first
> review you run in this conversation and increments by one on each later review
> you run in it (any review sub-procedure counts; a fresh shadow session starts
> at 1 again — the timestamp is what disambiguates). Obtain the timestamp by
> running `date -u +%Y-%m-%dT%H:%M:%SZ` — never estimate it. A **zero-concern**
> review (nothing found, or suppression removed everything) still emits the
> block: the two fences with only this header between them, which is the
> machine-readable record that the round completed clean.

**Site B — rules-list bullet** (bullet indent per the table):

> - **Round header.** The first line after the opening fence is
>   `Round: <N> @ <timestamp>` and nothing else. It MUST come **before** the
>   first `- [` marker — placed after an item it is absorbed into that item's
>   body and the round is lost — and it must never itself begin with `- [`. Take
>   N from the request when it names a round ("recheck round N"), else count from
>   1 within this conversation; get the timestamp from
>   `date -u +%Y-%m-%dT%H:%M:%SZ`, never by estimate. A **zero-concern** review
>   still emits the fences with only this header between them. Minimonitor reads
>   the header to show the round, to re-offer the picker when a later round
>   repeats the same concerns, and to judge concern freshness.

**Replace the contradictory omit-when-clean rule (five sites — MUST be deleted,
not merely outvoted).** Each producer's rules list ends with a bullet
instructing the agent to omit the block on a clean review; `plan-diagnose-errors.md`
additionally says it in step-2 prose. Both new round-header sites coexist with
that rule as far as the token-count guard is concerned, so the old rule must be
**replaced in place** — the Site B bullet above takes the old bullet's slot:

| file | old rule site | action |
|---|---|---|
| `plan-challenge.md:120-122` | "Emit the block **only when you have at least one concern**. … omit the block entirely and say so." | replace bullet with Site B |
| `plan-assumptions.md:123-124` | "Emit the block **only when you have at least one assumption worth forwarding** … omit it entirely and say so." | replace bullet with Site B |
| `plan-diagnose-errors.md:107-109` | "Emit the block **only when you found at least one genuine error/retry signal** … omit the block entirely and say so." | replace bullet with Site B |
| `plan-diagnose-errors.md:39-40` | "**say so plainly and stop** — emit no concern block." | reword: "**say so plainly** and emit the metadata-only block — the two fences with only the round header between them — so the round is still recorded." |
| `impl-challenge.md:445-447` | "Emit the block **only when you have at least one concern**. … omit the block entirely and say so." | replace bullet with Site B |

(Placing Site B in the old bullet's slot keeps each rules list the same length
and keeps the clean-review instruction where readers last saw it.) After the
edit, `grep -c "omit the block entirely\|omit it entirely\|emit no concern block"`
over the four producers must return **0 hits per file** — verify the count, and
the guard's negative assertion (Verification below) pins it from then on.

**Example blocks:** prepend `Round: 1 @ 2026-08-11T14:03:27Z` as the first line
inside each producer's ```` ``` ```` example, above the first `- [` item.
Examples must **never** gain the sentinel fences (t1123
`contains_any_concern_block` guard — it scans every `*.md` in the shadow dir,
authoring *and* rendered).

**Wrapping hazard (breaks the guards silently):** never let
`Round: <N> @ <timestamp>`, `zero-concern`, or
`date -u +%Y-%m-%dT%H:%M:%SZ` straddle a line break. The guard predicates
collapse whitespace, so a re-wrap is safe, but a hyphen-wrapped `zero-concern`
becomes `zero- concern` and stops counting — the exact trap documented at
`tests/test_concern_parser.py:935-936`.

**Do not disturb the rejection-suppression rule** while editing: its guard needs
the exact directive string `**Consult the rejection store before emitting.**`
plus `previously-rejected` ≥ 2 and `aitask_shadow_rejected.sh list` ≥ 2 on the
whitespace-collapsed text.

**Goldens:** regenerate the three `impl-challenge` procedure goldens in the same
commit (see step 6). Do **not** touch `SKILL.md.j2` or any stub.

### 3. Dedup lift + toast — `.aitask-scripts/monitor/minimonitor_app.py`

Add `parse_block_meta` to the import at `:58-61`. At `:2352-2355`:

```python
payload = build_clipboard_payload(concerns)
meta = parse_block_meta(text)
dedup_key = (
    f"round={meta.round}@{meta.reviewed_at}\n{payload}" if meta else payload
)
if self._last_concern_block_payload.get(shadow_pane) == dedup_key:
    return
self._last_concern_block_payload[shadow_pane] = dedup_key
```

No meta ⇒ **byte-identical** to today (back-compat for blocks emitted before
this lands). Toast (`:2365-2369`) gains a round suffix when meta is present:

```python
round_suffix = f" (round {meta.round})" if meta else ""
```

inserted before `stale_suffix` so the existing stale marker stays last.

### 3b. Monitor clean-round handling — `.aitask-scripts/monitor/monitor_app.py`

A metadata-only block has a **non-None** `concern_block_signature` (complete
fences), so `_scan_concern_signatures` stores it in `_concern_sig_latest` and
the `!` badge lights (`_has_fresh_concerns` keys on `_concern_sig_offered`
membership only). The offer pass marks it merely *examined* and returns
(`:1124-1134`), so the badge stands until the user presses `c` — correct for a
malformed block (there is something to investigate), wrong for a valid clean
round (there is nothing to pick).

In the offer pass's empty-parse branch (`:1131-1134`), split the two cases:

```python
concerns = parse_concerns(text)
if not concerns:
    if (parse_block_meta(text) is not None
            and not unrecovered_markers(text)):
        # Valid metadata-only clean-round block: nothing to pick, nothing
        # to investigate — treat as handled. Marking it OFFERED (same call
        # the `c` path makes at :2979) clears the badge; the signature
        # stays in `_concern_sig_latest`, so downstream freshness (t1448)
        # still sees the round advance.
        self._mark_concern_sig(
            self._concern_sig_offered, pane_id, sig, captured_sig
        )
        return
    # Malformed or empty-parse block: no misleading toast. The badge
    # stands, and `c` gives the user the precise reason.
    return
```

Add `parse_block_meta` and `unrecovered_markers` to `monitor_app.py`'s imports
(`unrecovered_markers` is already imported at `:53`; only `parse_block_meta` is
new). `parse_block_meta` and `unrecovered_markers` both read the same forgiving
region as `parse_concerns`, so the three describe the same block.

**Scope note:** the offer pass runs only for the focused agent, so an
*unfocused* agent's clean round badges until that agent is next focused (the
offer pass then clears it without a keypress). That residual is accepted:
clearing it tick-side would require parsing the raw `-p -e` capture, which the
`_scan_concern_signatures` contract explicitly forbids ("This is a TRIGGER,
never a parse"). Document the residual in the step-3b comment.

Also refine both TUIs' `c`-path empty-parse message: when
`parse_block_meta(text)` is not None and nothing was lost, notify
`f"Clean review (round {meta.round}) — no concerns"` instead of the generic
"No concerns detected on the shadow pane" (`monitor_app.py:2972`,
`minimonitor_app.py:2251`). The monitor `c` path already marks the signature
offered for any complete block (`:2977-2981`) — unchanged.

**Minimonitor needs no badge change:** it has no `!` badge (it omits the
`has_concerns` keyword — the t1448 task records this asymmetry as deliberate),
and its auto-offer returns silently on a metadata-only block (verified above:
`has_concern_block` False → not truncated → no lost markers → return).

### 4. Picker display — both TUIs + the shared modal

`monitor_shared.py`:

- Module-level pure helper beside the modal, so it is unit-testable and **total
  over garbage** (`reviewed_at` is unvalidated):

  ```python
  def format_block_meta(meta) -> str:
      """Display suffix for a concern block's round header ("" when absent)."""
      if meta is None:
          return ""
      when = meta.reviewed_at
      if "T" in when:
          when = when.rsplit("T", 1)[1]
      when = when[:12]
      return f"  ·  round {meta.round}" + (f", {when}" if when else "")
  ```

- `ConcernPickerModal.__init__` (`:2454-2461`) gains `block_meta=None` as a
  **keyword-only** parameter (after the bare `*`, alongside `rejected_entries` /
  `store_unavailable`); store it on `self._block_meta`.
- `_context_line()` (`:2495-2503`) appends `format_block_meta(self._block_meta)`
  to **both** return shapes (the `< 2` partitions branch and the two-partition
  branch).
- **Markup safety (required):** `#concern-context` is a markup-enabled `Static`
  (`:2529`), and `reviewed_at` is verbatim untrusted producer text — a header
  like `Round: 2 @ [/]` raises `MarkupError` and takes the modal down (the repo
  documents this exact failure mode with `escape()` as the convention,
  `monitor_shared.py:1548-1550`; `from rich.markup import escape` is already
  imported at `:49`). `format_block_meta` stays pure/plain-text;
  `_context_line()` applies `escape()` to the suffix at the markup boundary:
  `escape(format_block_meta(self._block_meta))`. The round is an `int` and the
  toast suffixes interpolate only that int, so the notify paths need no escape.

Callers pass `block_meta=parse_block_meta(text)`:

- `minimonitor_app.py` `action_pick_concerns` (`:2261-2272`);
- `monitor_app.py` (`:3008-3016`) — add `parse_block_meta` to its import at
  `:53`.

Display-only: no `Concern.body` is read, so no registration is needed in the
t1294 AST guard (`tests/test_concern_body_display_contract.py`).

### 5. `concern-format.md`

New **"Round header"** section immediately after `### Fences` (`:33-38`), before
`### Concern markers` (`:40`), covering:

- the grammar and the placement rule;
- the placement **hazard** (after an item ⇒ body-joined into that item, round
  lost);
- **back-compat**: absent ⇒ `parse_block_meta` returns `None` and everything
  else is unchanged;
- the **metadata-only clean-round block**, and that `has_concern_block` stays
  `False` for it (no items ⇒ no auto-offer) — by design, not a defect;
- the **three consumer roles**: display; lifting minimonitor's payload dedup on
  a repeat round; t1448's freshness key = the `(round, reviewed_at)` **pair**;
- the note that the header intentionally changes `concern_block_signature`, so a
  round bump re-hashes the monitor's freshness badge.

Also update the parser list under `## Where it lives` (`:277-281`) to include
`parse_block_meta` / `BlockMeta` — and `block_region`, which that list omits
today even though `minimonitor_app.py` imports and uses it (pre-existing gap,
fixed while editing the same list).

The two-placement producer rule already documented at `:261-269` should name the
round-header rule alongside the suppression rule.

### 6. Regenerate the `impl-challenge` goldens (same commit)

```bash
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/aitask-shadow/impl-challenge.md \
    "aitasks/metadata/profiles/$profile.yaml" claude \
    > "tests/golden/procs/aitask-shadow/impl-challenge-$profile.md"
done
```

**Review the diff, do not rubber-stamp it** — the only change should be the two
new rule sites and the example header, identically in all three.

## Verification

### `tests/test_concern_parser.py` (extend)

`parse_block_meta` unit cases:

- present → `BlockMeta(2, "2026-08-11T14:03:27Z")`;
- absent (no header) → `None`;
- no `@` (`Round: 3`) → `reviewed_at == ""`;
- dangling `@` (`Round: 3 @`) → `reviewed_at == ""` (total, not `None`);
- leading blank lines inside the region are skipped (first **non-blank** line);
- header after the first item → `None` **and** the header text is body-joined
  into the preceding concern's `.body` (pin the corruption mode explicitly);
- last-block-wins: two blocks with different rounds → the newer one;
- unclosed newest block (`require_close=False` path) → meta still readable.

Contract cases:

- **Metadata-only block**: `parse_block_meta` reads the round;
  `has_concern_block` is `False`; `parse_concerns` is `[]`; `unrecovered_markers`
  is `[]`.
- **Byte-identical entry points**: for the same concerns with and without the
  header, `parse_concerns`, `has_concern_block` and `unrecovered_markers`
  produce equal results.
- `concern_block_signature` **changes** when only the round bumps (and only the
  round bumps).

Producer guard — new `TestProducerRoundHeaderRule`, mirroring
`TestProducerRejectionSuppressionRule` (`:950`) including **both** of its
negative controls:

```python
_ROUND_HEADER_DIRECTIVE = (
    "**Emit a round header as the first line inside the block.**"
)


def _states_round_header_rule(text: str) -> bool:
    flat = " ".join(text.split())
    return (_ROUND_HEADER_DIRECTIVE in flat
            and flat.count("Round: <N> @ <timestamp>") >= 2
            and flat.count("zero-concern") >= 2
            and flat.count("date -u +%Y-%m-%dT%H:%M:%SZ") >= 2)
```

The counted tokens use the **placeholder** grammar (`<N>`, `<timestamp>`), so the
concrete example header (`Round: 1 @ 2026-08-11T14:03:27Z`) cannot inflate the
count and mask a deleted rule site.

Plus the **omit-rule absence predicate** (the negative half of the step-2
replacement — without it, a producer carrying BOTH the round-header rule and a
surviving omit rule passes the positive guard while instructing contradictory
behavior):

```python
def _retains_omit_block_rule(text: str) -> bool:
    flat = " ".join(text.split())
    return ("omit the block entirely" in flat
            or "omit it entirely" in flat
            or "emit no concern block" in flat)
```

- `test_producer_set_is_the_known_set` (reuses `KNOWN_PRODUCERS`, unchanged — no
  new producer file);
- `test_every_producer_states_the_round_header_rule`;
- **negative control 1 (synthetic, placement-aware):** neither copy → `False`;
  directive only → `False`; bullet only → `False`; both → `True`;
- **negative control 2 (production assertion):** patch `SHADOW_DIR` to a
  tmpdir holding one compliant + one offending + one non-producer file, invoke
  **the real production method** and require it to raise naming `bad.md` and not
  `good.md`. Copy the rationale in `test_production_assertion_fails_on_a_real_offender`
  (`:1024`) — recomputing the offender list here instead of calling the method
  leaves both green under a wrong-predicate mutation.
- `test_every_producer_example_starts_with_a_round_header`: for each producer,
  take the first ```` ``` ```` fenced block whose body contains a `- [` line and
  assert its first non-blank body line matches
  `^\s*Round: \d+ @ \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` and that the next
  non-blank line starts `- [`.
- `test_no_producer_retains_the_omit_block_rule`: offenders =
  `[name for name, text in self._producers().items() if _retains_omit_block_rule(text)]`
  must be empty — the step-2 replacement is what satisfies it. **Negative
  control:** each of the three omit phrases individually flips the predicate
  `True` on synthetic text; text with none of them is `False`. (This is the
  assertion that fails today's producers *before* step 2 runs — confirm it does
  by running it once pre-edit; a guard that cannot fail on the current tree is
  not guarding the replacement.)

Rendered-surface guard — add to `TestRenderedShadowDocsKeepTheGuarantees`
(`:1091`):

- `test_every_rendered_producer_states_the_round_header_rule`, using the same
  predicate over `_rendered_producers()`. Without it, a profile conditional that
  dropped the rule would leave the authoring guard green while the surface the
  agent actually reads has no rule (the t1311 rationale).
- `test_no_rendered_producer_retains_the_omit_block_rule` — same absence
  predicate over `_rendered_producers()` (a render that resurrected the old
  wording via a conditional would otherwise pass).

### `tests/test_minimonitor_concern_action.py` (extend `AutoOfferTests` + action flow)

- round 1 → one notify; round 2 with **identical** concerns → a **second**
  notify (dedup lifted);
- the same round re-captured → still one notify;
- the toast text contains `(round 2)` on the round-2 fire;
- a header-free block behaves exactly as today (the existing
  `test_closed_block_fires_once` / `test_surrounding_churn_does_not_refire`
  already pin this — confirm they still pass unmodified, which is the
  back-compat proof);
- **caller wiring:** in the `action_pick_concerns` happy-path test (the existing
  `push_screen` interception), assert the pushed `ConcernPickerModal` instance's
  `_block_meta` equals `parse_block_meta` of the captured text when a header is
  present, and is `None` for a header-free block — this is what catches an
  omitted `block_meta=` argument that every isolated test would miss;
- `c`-path clean round: metadata-only capture → notify
  `"Clean review (round N) — no concerns"`, no modal pushed.

### `tests/test_monitor_concern_action.py` (extend)

- **metadata-only clean round through the offer pass:** no toast; signature
  marked **offered** (`_has_fresh_concerns` returns `False` afterwards — no
  standing `!` badge); `_concern_sig_latest` still carries the signature
  (freshness retained);
- **malformed-block badge contract unchanged:** an all-malformed block (parse
  empty, `unrecovered_markers` non-empty) still marks only *examined* and the
  badge **stands** — pins that step 3b split the cases rather than widening the
  clean-round path;
- **caller wiring:** the monitor's `c`-path test asserts the pushed modal's
  `_block_meta`, same as minimonitor's;
- `c`-path clean round: notify names the round, signature marked offered.

### `tests/test_concern_picker_modal.py`

- the pre-phase narrow-width characterization + its post-change extension
  (see **Pre-phase** above);
- `format_block_meta`: `None` → `""`; ISO input → `"  ·  round 2, 14:03:27Z"`;
  empty `reviewed_at` → `"  ·  round 2"`; garbage `reviewed_at` (no `T`, long) →
  truncated, never raises;
- **markup-shaped garbage renders instead of crashing:** `reviewed_at` of
  `"[/]"`, `"[bold red]x"`, and `"]"` → the modal composes and the context line
  renders (drive the composited render, not just `_context_line()`'s return —
  the `MarkupError` fires at render time);
- `_context_line()` with and without `block_meta`, on **both** partition shapes.

### Suite / render

```bash
bash tests/run_all_python_tests.sh      # read ONLY the final stderr verdict line
bash tests/test_skill_render_aitask_shadow.sh
```

If piping either, use `set -o pipefail` or check `${PIPESTATUS[0]}` — `| tail`
returns `tail`'s exit status, not the suite's.

No `.j2` or stub surface is touched, so `aitask_skill_verify.sh` is not
required; run it only if that changes.

Reference **Step 9 (Post-Implementation)** of the task-workflow skill for
cleanup, archival, and merge.

## Risk

### Code-health risk: medium
- The round-header rule is duplicated across six places that must agree (4
  producers × 2 sites, `concern-format.md`, the parser module docstring table);
  the producer half is guarded by tests, the doc half is not · severity: medium
  · → mitigation: authoring + rendered guard predicates (step 2 / Verification);
  the docstring-table row is pinned by review, not by a test
- The step-2 replacement deletes a load-bearing producer rule (omit-when-clean)
  at five sites; a missed site leaves contradictory instructions live ·
  severity: medium · → mitigation: `_retains_omit_block_rule` absence guard,
  authoring + rendered, with a pre-edit failing run as its own negative control
- Step 3b changes the monitor's offer-pass state machine (offered vs examined
  marking), a surface with documented races around its awaits · severity:
  medium · → mitigation: the malformed-block badge-stands test pins the
  untouched branch; the change reuses the exact `_mark_concern_sig` call the
  `c` path already makes
- `ConcernPickerModal` is shared by both TUIs, and the context line gains ~20
  characters at a tier as narrow as `_PICKER_NARROW_MIN_WIDTH`; `reviewed_at`
  is untrusted text on a markup surface · severity: medium · → mitigation:
  inline pre-phase narrow_width_context_budget + `escape()` at the markup
  boundary with markup-shaped garbage tests
- `impl-challenge.md` carries per-profile goldens; an edit without regeneration
  breaks `test_skill_render_aitask_shadow.sh` · severity: low · → mitigation:
  step 6 in the same commit (fails loudly, never silently)

### Goal-achievement risk: medium
- The round number is LLM-emitted in this child — the machine-derived
  `recheck round N` injection only lands in t1159_2 — and a restarted shadow
  restarts at 1, so a consumer keying on the round alone is wrong · severity:
  medium · → mitigation: the `(round, reviewed_at)` pair contract, carried in
  the `parse_block_meta` docstring and in `concern-format.md`, and test-pinned
- The producer guards pin the *wording* of the rule, not that a live shadow
  actually emits the header · severity: medium · → mitigation: t1159_5, whose
  checklist already covers a live round 1, a live round 2 with the dedup lifted,
  a metadata-only clean round, and the picker's round display

### Planned mitigations
- timing: pre-phase | name: narrow_width_context_budget | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health (shared picker modal / narrow-width display budget) | desc: Characterize the picker context line at the xnarrow tier on the composited strip before adding the round suffix, then assert the actionable counts remain visible with block_meta present
