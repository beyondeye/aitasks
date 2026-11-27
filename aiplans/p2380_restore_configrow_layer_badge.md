---
Task: t2380_restore_configrow_layer_badge.md
Base branch: main
Output branch: main
---

# t2380 — Restore the ConfigRow `[PROJECT]` / `[USER]` layer badge

## Context

`ConfigRow.render` (`.aitask-scripts/lib/profile_editor.py`) has never drawn its
layer badge. It has been broken since t268_6: the markup `[#50FA7B][PROJECT][/]`
parses `[PROJECT]` as a style tag, so only the colour leaks onto the rest of the
row. t2371 kept the output byte-identical: an empty badge, plus the leaked colour
applied to the row tail with `stylize_before`. The settings docs still promise
the badge, so they are wrong today:
- `website/content/docs/tuis/settings/_index.md:29`: "[PROJECT] (green) … [USER] (amber)"
- `how-to.md:39`: "Navigate to the entry showing an [USER] badge"

**User decision (pick-time):** restore both badges.

**Scoping found during planning: the badge is opt-in, used only by the Agent
Defaults tab.** `ConfigRow` is also used by the Profiles tab, the profile editor,
Project Config, tmux and Artifacts. In those tabs every row is single-layer, and
`ConfigRow` rows sit between `CycleField` rows that draw `  label:` with no badge.
Turning the badge on everywhere would push those keys 11 columns right of their
neighbours. It would also label fields of `profiles/local/*.yaml` profiles as
`[PROJECT]`, which is wrong. Agent Defaults is the only tab that has project/user
row pairs, and the only tab the docs describe the badge on. So it is the only tab
that opts in. Every other row keeps today's output, and the t2371 old-render
oracle still pins that output.

**Colour decision (explicit, as the task asks):** the tail keeps the layer colour
(today's green/amber look). The badge text is drawn in the same colour, in front
of the tail. Badge rows therefore change by exactly the inserted badge text.

Target render (Agent Defaults):
```
  [PROJECT]  pick:  claudecode/opus5_5  [96 (9 runs…)]
      └ [USER]  claudecode/opus5  (d to remove)
```

**80-column constraint (plan review finding, verified by a headless probe).** At
80 columns an Agent Defaults row has **74** content columns (region 76 minus
`padding: 0 1`). Two rows fit today and would be clipped by the 11-column badge:
- `brainstorm-module_decomposer` = `opencode/opencode_gemini_3_5_flash_lite`:
  73 → 82 columns, so the model name would be cut off.
- a user override `opencode/opencode_muse_spark_1_3_contributor_free`:
  72 → 78 columns, so the hint would be cut to `(d to`.

The fix: a badge row is **width-aware**. When its single-line form fits the
content width it draws on one line, as above. When it doesn't, it wraps whole
segments onto continuation lines, so a model name or the removal hint is never
cut. Prototype at 74 columns (Textual 8.2.7):
```
  [PROJECT]  brainstorm-module_decomposer:
             opencode/opencode_gemini_3_5_flash_lite
      └ [USER]  opencode/opencode_muse_spark_1_3_contributor_free
                (d to remove)
  [PROJECT]  pick:  claudecode/opus5_5 [96 (9 runs)]
```
(The `pick` row in the prototype carried a shorter score suffix than the target
render above. That is why it stayed on one line.)

## Implementation steps

1. **`.aitask-scripts/lib/profile_editor.py` — `ConfigRow`**
   - Add the constructor kwarg `layer_badge: bool = False` and store it as
     `self.layer_badge`. Document it in the class docstring: it is opt-in and
     only for rows whose layer varies (project/user pairs). Compact rows never
     draw it.
   - Add `_LAYER_LABELS = {"user": "[USER]"}` with the default `"[PROJECT]"`,
     next to `_LAYER_COLORS`.
   - **Rows without the badge (`layer_badge=False`, and every compact row)
     keep today's `render()` code path unchanged**, so the t2371 oracle still
     pins them.
   - Badge rows (`layer_badge` and not `compact`): in `__init__`, set
     `self.styles.height = "auto"`, the same mechanism compact rows use, so the
     inline style overrides `ConfigRow { height: 1 }`. Add one layout helper,
     `_badge_lines(width) -> list[Content]`, used by both:
     - `get_content_height(self, container, viewport, width)` → for a badge
       row, `len(self._badge_lines(width))`; otherwise `super()`.
     - `render()` → for a badge row,
       `Content("\n").join(self._badge_lines(self.size.width))`. `size` is the
       content area, so both callers pass the same width. The prototype
       confirmed that region heights match.
   - `_badge_lines(width)`:
     - `badge = Content.styled(label, color)`. It is built with
       `Content.styled`, never markup, so it can never be parsed as a tag again.
     - `prefix`: `f"  {pad}"` (wide) or `f"      {pad}└ "` (subordinate). It is
       uncoloured, as today.
     - `head`: `badge  key:` (wide) or `badge` (subordinate).
     - `units`: atomic segments, each carrying its own leading separator. They
       are `"  "+value`, then the `suffix` (only if non-empty; callers already
       start it with one or two spaces), then on subordinate rows with an
       override the `"  "+(d to remove)` hint (dim). Units are never split
       internally.
     - Greedy pack: line 1 = `prefix + head`. Append each unit while
       `cell_length` stays `<= width`. Otherwise start a continuation line
       with `indent = prefix + badge + 2` columns of spaces (the column where
       the key or value starts after the badge), and put the unit there
       without its leading spaces. `width <= 0` (no layout yet) → one line.
     - Each line = `indent_or_prefix` + `Content.assemble(rest).stylize_before(color)`.
       The prefix and indent stay uncoloured; key, value, suffix and hint keep
       the layer colour, as today.
     - A single unit wider than the whole continuation line still clips, the
       same as today's over-long values. This is out of scope.
   - Probe on Textual 8.2.7 for the one-line form: `'  [PROJECT]  k:  v'`, with
     spans `(2,18,color) (2,11,color) (13,15,bold)`.
   - Replace the "badge has never drawn" comment with a short note: the badge is
     opt-in, drawn literally via `Content.styled`, and the colour also covers the
     tail. Fix the compact-path comment ("The modal hard-codes the [PROJECT]
     badge…") to say: compact rows never draw the badge, because 11 columns
     matter in a ~40-col pane.

2. **`.aitask-scripts/settings/settings_app.py` — Agent Defaults only.** Pass
   `layer_badge=True` to the six `ConfigRow(...)` mounts in the Agent Defaults
   builder:
   - brainstorm launch_mode project/user pair (~L2881 / ~L2896)
   - operation project/user pair (~L2948 / ~L2963)
   - synthetic brainstorm pair (~L3020 / ~L3025)

   The other mounts (Project Config, default_profiles, tmux, artifacts) and the
   profile editor's own rows stay unchanged.

3. **`tests/test_configrow_markup_escape.py`**
   - Update the module docstring. The oracle now pins the **un-badged** rows,
     whose output is still identical to the old render. Add a line for the new
     badge pins. `_old_render` / `_ORACLE_CASES` stay as they are, so the existing
     oracle keeps passing unchanged: it proves that non-opt-in rows did not move.
   - Add `LayerBadgeTests`:
     - drawn text: a wide project row → `"  [PROJECT]  k:  v"`; a wide user row →
       `"  [USER]  k:  v"`; a subordinate user override →
       `"      └ [USER]  v  (d to remove)"`; a subordinate inherits row →
       `"      └ [USER]  (inherits project)"`; `extra_indent=4` places the pad
       before the badge (wide) and before `└` (subordinate).
     - style: the badge characters carry the layer colour (`#50FA7B` /
       `#FFB86C`), the key span stays bold, and the dim span still covers exactly
       `(d to remove)`.
     - hostile keys/values next to the badge still draw verbatim, and a value
       such as `[USER]` or `[/]` does not disturb the badge.
     - `compact=True, layer_badge=True` draws no badge (same as the compact
       oracle case).
     - a control character in the value (`op\rus`) does not shift the badge or
       hint styles.
     - wrapping, at a 76-column host (74 content columns, as at 80): the two
       review cases wrap into exactly the prototype lines above, and a row that
       fits stays at `region.height == 1`. A continuation line keeps the layer
       colour on its body, its indent stays unstyled, and the dim span still
       covers exactly `(d to remove)`.

4. **`tests/test_settings_superseded_models.py`** (real SettingsApp, composed
   screen via the existing `screen_lines()` helper)
   - **New `test_long_values_and_removal_hint_survive_80_columns`**, at
     `size=(80, 60)`:
     - Fixture: `brainstorm-module_decomposer` =
       `opencode/opencode_gemini_3_5_flash_lite` in the project file; a local
       override `opencode/opencode_muse_spark_1_3_contributor_free` for `pick`;
       both names in a `models_opencode.json` registry.
     - Join the composed-screen lines over each row's `region` (all of its lines).
     - Assert the project row's lines contain `[PROJECT]`,
       `brainstorm-module_decomposer:` and the full
       `opencode/opencode_gemini_3_5_flash_lite`.
     - Assert the user row's composed lines, taken over its **full rendered
       height** (`region.y … region.y + region.height - 1`; the hint is
       expected on the continuation line), contain `[USER]`, the full
       `opencode/opencode_muse_spark_1_3_contributor_free` and the complete
       `(d to remove)`. Each of the three is checked per line, as a substring of
       some single line, so a piece split across a line break does not pass.
       They are **not** required to share a line. Also assert
       `region.height == 2`, which pins that the wrap happened.
     - **In-test negative control:** mount the same user row with its height
       forced to 1 (`styles.height = 1`). It is the one-line badge layout the
       review rejected. Assert that its line is missing `(d to remove)`, so the
       positive assertions demonstrably depend on the wrap.
   - `test_target_stays_visible_at_80_columns`: its negative control stays a
     **plain one-row `ConfigRow` without `layer_badge`**. It demonstrates the
     rejected "suffix on one row" design, and a badge row would now wrap and
     show the target, defeating the control. The real row and the note must
     still pass.
   - Render test: in the Agent Defaults tab at `SIZE`, the project `pick` row
     draws `[PROJECT]  pick:  claudecode/opus5`, and the user `pick` row draws
     `└ [USER]  (inherits project)`.
   - Inventory assertion: every `ConfigRow` with an `agent_proj_` /
     `agent_user_` id has `layer_badge` True, and no other `ConfigRow` in the
     app has it. This guards the opt-in sites and the scoping.

5. **Docs** (current-state prose):
   - `_index.md:29`: the claim becomes true. Keep it, and tighten it to "Each
     entry shows its layer: a **[PROJECT]** row (green) with the project default,
     and below it a **[USER]** row (amber) with your per-user override or
     `(inherits project)`".
   - `how-to.md:39`: every user row now carries `[USER]`, so name the right one:
     "Navigate to the **[USER]** row that holds your override (it shows
     `(d to remove)`)".
   - Run `python3 check_links.py --build` in `website/`.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir` is not needed for the whole
  suite. Run the touched modules directly:
  `~/.aitasks/venv/bin/python -m pytest tests/test_configrow_markup_escape.py tests/test_settings_superseded_models.py tests/test_profile_editor_narrow.py -q`
- Also run any other settings test that reads ConfigRow text:
  `grep -l 'ConfigRow\|agent_proj_' tests/*.py` → run each.
- Pre-fix controls, run in a scratch copy, never by `git restore`:
  - with the step-2 opt-ins removed, the render test and the inventory test fail;
  - with step 1 reverted, the `LayerBadgeTests` fail;
  - with the `height = "auto"` / `get_content_height` wrap removed (one-line
    badge), `test_long_values_and_removal_hint_survive_80_columns` fails on both
    review cases.
- Visual check: `./ait settings` at 80 and 140 columns, on the Agent Defaults tab.
- `cd website && python3 check_links.py --build`.

## Step 9

Post-implementation: commit the code and tests (`bug: … (t2380)`), then archive
via the standard Step 9 flow on `main` (current-branch mode, no merge).

## Risk

### Code-health risk: low
- Opt-in flag with a False default: every non-Agent-Defaults row renders exactly as before, and the existing t2371 old-render oracle pins this. The blast radius is one widget and six mount sites in one builder, guarded by an inventory test. · severity: low · → mitigation: none needed
- Badge rows become variable-height (`height: auto` plus a `get_content_height` override). If the measured height and the drawn lines disagreed, a line would be clipped. Both read one layout helper and the content width, the prototype matched region heights, and the 80-column composed-screen test with its forced-height-1 control pins it. · severity: low · → mitigation: none needed (covered by the plan's tests)

### Goal-achievement risk: low
- The scoping narrows the pick-time choice ("every row") to the Agent Defaults tab. This is the only place the docs promise the badge and the only tab with layer pairs, but it is a deviation the user approves with this plan. · severity: low · → mitigation: none (plan approval)
- The home/settings page screenshot (`website/static/imgs/home/settings.svg`, recipe `home_settings`) will not show the restored badges until it is regenerated. The recipe's `expect` lines still match, so nothing fails, but the image goes stale against the docs text. · severity: low · → mitigation: t2389

### Planned mitigations
- timing: after | name: refresh_settings_screenshot | type: documentation | priority: low | effort: low | inline_risk: low | added_complexity: medium | addresses: stale home/settings.svg screenshot without the restored layer badges | desc: Regenerate the home_settings TUI screenshot (website/static/imgs/home/settings.svg) with the aitask-docs-screenshots skill so the Agent Defaults rows show the [PROJECT]/[USER] badges restored by t2380 | created: t2389

## Post-Review Changes

### Change Request 1 (2026-11-27 12:55)
- **Requested by user:** At 70 columns (64 content cells) the fixed 16-cell continuation indent plus the 49-cell `opencode/opencode_muse_spark_1_3_contributor_free` override is 65 cells, so Textual split the name before its final `e` and pushed `(d to remove)` below the measured row height. Use a shallower continuation indent when it keeps the segment whole, add a composed-screen regression, and qualify reference.md for segments too wide for any line.
- **Changes made:** verified (reproduced at a 66-col host: `…contributor_fre` / `e`, hint hidden). `_badge_lines` now indents a continuation line by `max(0, min(full_indent, width - segment))`. Badge rows set `text_wrap = "nowrap"` and `text_overflow = "clip"`, so only `_badge_lines` breaks lines and the drawn lines always equal the measured height. A segment wider than the whole row is clipped at the edge, never folded onto an uncounted line. reference.md now says a part is cut off only when it is wider than the whole row.
- **Tests:** `test_continuation_indent_shrinks_to_keep_a_segment_whole` (64-cell host, exact lines, height 3). `test_segment_wider_than_the_row_clips_without_hidden_lines` (38 cells; a space-free name and a spaced suffix, height equals counted lines). `test_long_override_and_hint_survive_70_columns` (real SettingsApp, composed screen). Pre-fix controls in scratch copies: the fixed indent fails all three; removing `nowrap`, `clip` or both fails the over-wide test.
- **Files affected:** `.aitask-scripts/lib/profile_editor.py`, `tests/test_configrow_markup_escape.py`, `tests/test_settings_superseded_models.py`, `website/content/docs/tuis/settings/reference.md`
- **Concern resolutions:** reference.md guarantee qualified: fixed (reference.md, Agent Defaults Operations). Re-reviewed this round: level/prose/claims ok.

### Change Request 2 (2026-11-27 13:10)
- **Requested by user:** At 44 columns (38 content cells) the badge and key formed one unbreakable first-line head of 42 cells, so `nowrap` clipped it to `[PROJECT]  brainstorm-module_decompo`. Without the badge the full key fits. Let the key move whole onto a continuation line, and assert in the composed screen at 44 columns that the badge and full key stay visible.
- **Changes made:** verified (42 > 38). Line 1 is now prefix + badge only. On wide rows the key is the first atomic unit (`"  " + key:`), packed like the value, suffix and hint, so at normal widths it stays on line 1, and when it doesn't fit it moves whole to a continuation line indented by `min(full_indent, width - key)`. The reference.md list of parts that move now includes the operation name.
- **Tests:** `test_key_moves_whole_to_a_continuation_line` (38-cell host, exact lines, key bold and layer-coloured). `test_badge_and_full_key_survive_44_columns` (real SettingsApp, composed screen). Pre-fix control (the old badge+key head) fails both. 439 related tests pass.
- **Files affected:** `.aitask-scripts/lib/profile_editor.py`, `tests/test_configrow_markup_escape.py`, `tests/test_settings_superseded_models.py`, `website/content/docs/tuis/settings/reference.md`
- **Concern resolutions:** reference.md part list: fixed (Agent Defaults Operations). Re-reviewed this round: level/prose/claims ok.

## Final Implementation Notes
- **Actual work done:** `ConfigRow` got an opt-in `layer_badge` flag (`.aitask-scripts/lib/profile_editor.py`). A badge row draws `[PROJECT]`/`[USER]` with `Content.styled` (never markup) in the layer colour, and the key, value, suffix and hint keep that colour. It is width-aware via a single `_badge_lines(width)` helper, shared by `get_content_height` and `render`: line 1 is prefix + badge, and the key, value, suffix and removal hint are atomic units packed greedily. A unit that does not fit starts a continuation line indented to the column after the badge, shallower when needed to keep it whole. Badge rows are `height: auto`, `text-wrap: nowrap`, `text-overflow: clip`, so the drawn lines always equal the measured height. Only the six Agent Defaults mounts in `settings_app.py` opt in. Docs: settings `_index.md` (layer bullet), `how-to.md` (which `[USER]` row to pick), `reference.md` (wrap behaviour).
- **Deviations from plan:** (1) The key became its own wrappable unit, instead of riding on line 1 with the badge (review CR2, 44 cols). (2) The continuation indent shrinks to keep a unit whole, and `nowrap` + `clip` stop Textual from adding lines it didn't count (review CR1, 70 cols). (3) The narrow-terminal wrap fact moved from the overview `_index.md` to `reference.md`, because the guide makes the TUI reference page the owner of behaviour detail. (4) The 80-col superseded-note negative control deliberately stays a plain one-row `ConfigRow`, as planned.
- **Issues encountered:** The plan reviews found three width boundaries the first design clipped: 80 cols (single line), 70 cols (fixed indent overflowed by 1 cell and Textual folded the name), and 44 cols (unbreakable badge+key head). Each now has a composed-screen regression with a pre-fix control in a scratch copy. Removing `text_overflow=clip` alone, or `nowrap` alone (via a spaced over-wide suffix), fails the over-wide test.
- **Key decisions:** The badge is opt-in, used only by Agent Defaults. Other tabs mix `ConfigRow` with unbadged `CycleField` rows, and profile fields of `profiles/local/` would be mislabelled `[PROJECT]`. The layer colour is kept on the row tail (today's look), and un-badged rows render byte- and style-identical to before (the t2371 oracle is unchanged).
- **Documentation review:**
  - `website/content/docs/tuis/settings/_index.md`: level=ok prose=ok reader=not-run(not-beginner) claims=ok.
  - `website/content/docs/tuis/settings/how-to.md`: level=ok prose=ok reader=not-run(not-beginner) claims=ok.
  - `website/content/docs/tuis/settings/reference.md`: level=ok prose=ok reader=not-run(not-beginner) claims=ok. It received the wrap fact moved off the overview.
  - No unresolved findings. Other sessions' sitrep/trails pages were excluded from scope by the user.
- **Upstream defects identified:** None
