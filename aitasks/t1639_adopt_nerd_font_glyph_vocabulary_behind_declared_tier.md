---
priority: medium
effort: high
depends: [1638]
issue_type: bug
status: Ready
labels: [tui, aitask_board, aitask_monitormini, ait_brainstorm]
created_at: 2026-08-30 13:59
updated_at: 2026-08-30 14:48
---

## Problem

t1638 fixed the invisible checked mark by picking codepoints from the
**intersection of every supported font** — `✓` U+2713 / `□` U+25A1. That works,
but it is the wrong selection rule: it optimises for coverage and pays for it in
shape. `☑`/`☐` were a checkbox and its empty twin; `✓`/`□` is a tick beside a
square. The same compromise is why `★`/`☆` was deferred rather than fixed — no
star shape survives the intersection.

The better answer is to **act on the font**, not to keep hunting for glyphs that
every font happens to contain. Nerd Fonts patch icon sets into the Private Use
Area, and both supported families carry the exact shapes.

## Measured evidence (t1638 tooling, re-run 2026-08-30)

| codepoint | shape | JetBrainsMono NF | Caskaydia NF | fc-match rank 1 | width |
|---|---|---|---|---|---|
| `U+F046` | `nf-fa-check_square_o` — checked checkbox | yes | yes | primary font | 1 cell |
| `U+F096` | `nf-fa-square_o` — empty checkbox | yes | yes | primary font | 1 cell |
| `U+F005` | `nf-fa-star` — filled star | yes | yes | primary font | 1 cell |
| `U+F006` | `nf-fa-star_o` — hollow star | yes | yes | primary font | 1 cell |

PUA glyphs are **structurally immune** to the t1638 defect: nothing but other
icon fonts claims the Private Use Area, so no emoji font can ever win the
fallback. That is a stronger guarantee than "these happened to be in the
intersection". Width is EAW *Ambiguous*, the same as the `□` shipped in t1638 —
no regression, no gain.

## Two constraints that shape the design

1. **A process cannot detect the terminal's font.** `fc-list` reports what is
   installed on the box running `ait`; over ssh or tmux that is not the box
   rendering the glyphs. Any "check the user's font" design is wrong. The tier
   must be **declared configuration**, and a setup-time warning is **advisory
   only** — it must say so rather than implying it verified anything.
2. **Without a Nerd Font, PUA renders as tofu** — worse than today's fallback.
   The framework uses **zero** PUA glyphs today (measured), so this introduces a
   new dependency rather than formalising an existing one. Hence the tier.

## Decisions taken with the user

- **A declared glyph tier, defaulting to `nerd`.** A config key selects `nerd`
  (PUA icons — real checkbox and star shapes) or `unicode` (the t1638 BMP
  glyphs, which stay as the documented fallback vocabulary). Never auto-detected.
- **The `★`/`☆` prioritisation mark moves too**, to `U+F005`/`U+F006`. This
  retires the t1638 deferral. It must keep its bold-white/dim styling and its
  distinct meaning (`monitor_shared.format_mark_glyph` records why it is
  deliberately not the selection mark's vocabulary or colour) — a star is still
  a star, so the shape distinction survives, and the `▲`/`△` collision with
  `FOLLOWUP_KINDS["risk_mitigation"]` that t1638 flagged does not arise.

## Scope

`lib/mark_glyphs.py` is already the single authority and every surface renders
through `mark_markup()` / `rich_mark_style()`, so the tier is a change inside
that module plus a config key — not a sweep of call sites. Reuse, do not rebuild:

- `tests/tools/regen_font_coverage.py` (cmap parser; **not** `fc-list`, which is
  family-agnostic and was measurably wrong on U+2714) and
  `tests/data/font_coverage.json` extend to cover both tiers' codepoints.
- `tests/test_mark_glyphs_single_source.py` — Rules 1-4 and the emoji oracle
  apply unchanged; PUA glyphs satisfy the existing policy trivially.
- Config resolution goes through the existing `resolve_config_path` seam.

Also decide, per glyph, what the tier means for the rest of the inventory — the
t1638 measurement found live violations that are the *same defect shipping now*:

- **`✔` U+2714** at `board/aitask_board.py:3541,3596` (by-trail "landed").
  Covered by neither font and emoji-claimed. Highest-value item.
- **`⚠` U+26A0** — ~10 sites across board / monitor / applink. Uncovered by
  CaskaydiaMono, emoji-claimed.
- **`⇄` U+21C4** — `TRAIL_CLASSIFICATION_GLYPHS`. Uncovered but not
  emoji-claimed, so it falls back and stays visible. Low risk.

**This may warrant decomposition** — the tier mechanism, the mark migration, the
inventory sweep and the docs/setup surface are separable, and the tier must land
before anything can depend on it. Assess at planning time.

## The trap — read before scanning anything

`lib/workflow_phase.py:121` is `_QUESTION_HEADER_RE = re.compile(r"^\s*[☐☑]\s+\S")`.
Those glyphs are **Claude Code's own AskUserQuestion chip** being *detected* in
captured pane text, not this repo's mark being *rendered*. A repo-wide sweep
breaks question detection in both monitors and the shadow flow, with no failing
test near the edit. Same for `tests/review_loop_fixtures.py` and
`aidocs/framework/shadow_agent.md:1118,1133`. `QuestionDetectorPinTests` pins it.

## Acceptance criteria

- [ ] The glyph tier is **declared** in config, never detected, and the code
      contains no attempt to infer the terminal's font.
- [ ] Both tiers resolve through `lib/mark_glyphs.py`; no consuming surface
      learns which tier is active. The existing drift guard still passes
      unmodified in spirit — a consumer still cannot restate a glyph or attach
      its own colour.
- [ ] Coverage for **both** tiers' codepoints is asserted per-family from the
      manifest, with the same missing-entry-is-a-failure rule.
- [ ] Any setup-time font notice states plainly that it is advisory and may be
      inspecting the wrong machine (ssh/tmux).
- [ ] `★`/`☆` moves to `U+F005`/`U+F006` under the `nerd` tier and keeps its
      bold-white/dim styling and its documented distinctness from the selection
      mark.
- [ ] The supported-font requirement is documented on the website, including the
      one-line opt-out to the `unicode` tier.
- [ ] `lib/workflow_phase.py`'s question-chip codepoints are untouched and
      `QuestionDetectorPinTests` still passes.
- [ ] `✔` U+2714 at `aitask_board.py:3541,3596` is fixed or carries a recorded,
      reasoned deferral — it is a live instance of the t1638 defect.
