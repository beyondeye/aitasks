---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [monitor, codex, shadow, review_loop]
gates: [risk_evaluated]
created_at: 2026-09-11 15:26
updated_at: 2026-09-11 15:26
---

`ait minimonitor` (and `ait monitor`) report an idle **Codex** pane as *active*
when it is parked on an empty composer waiting for input. Observed live on the
shadow pane in window `agent-pick-1794` (codex-cli **0.154.0**): the shadow
glyph never turns IDLE, and the `L` auto-recheck loop never sees the shadow as
ready.

## Root cause (measured 2026-09-11, `capture-pane -p -e`, 1 s samples)

Codex 0.154.0 renders an **animated Braille "starfield"** while the composer is
idle: sparse truecolor-tinted glyphs from the Braille block (U+2800–U+28FF) on
the line above the composer, the line below it, **and inside the composer line
itself** — e.g. the composer strips to `›⠁Ask Codex to do anything⡀   ⠁` on
one tick and `› Ask Codex to do anything   ⠈  ⠂  ⠁` on the next. The glyphs
move every tick.

Two independent detectors break on it:

1. **Idle timer** — `classify_content` builds the compare value with
   `strip_ansi` only; the Braille glyphs survive the strip, so
   `_apply_bookkeeping` (`monitor_core.py`) sees a changed `compare_value`
   every tick, resets `_last_change_time`, and `is_idle` can never exceed
   `idle_threshold`. Colour-only animation was already handled by the
   `stripped` compare mode (t715); this is a *visible-glyph* animation, which
   that mode was never meant to absorb.
2. **Review loop shadow readiness** — `review_loop._codex_state` flaps
   `ready` ↔ `busy` across ticks: when a dot lands right after `›` the line no
   longer matches `_CODEX_COMPOSER_RE` (`^›( .*)?$`), and trailing dots after
   the dim placeholder hint are *not* dim, so the dim-strip test classifies the
   composer as holding typed text. Independently, the caller's raw-tail
   hash-stability conjunct (`_loop_shadow_hash_streak` in
   `minimonitor_app.py`) can never reach 1, so `shadow_prompt_ready` is never
   True.

## Verified kill switch

The Codex binary's `[tui]` config struct carries `animations`, `whimsy`,
`pet`, `pet_anchor`, … Throwaway launches measured in a scratch tmux window
(repo root as cwd, 4 samples at 1 s):

| launch | Braille present | stripped tail changed between ticks |
|---|---|---|
| `codex` (control) | yes | yes, yes, yes |
| `codex -c tui.animations=false` | no | no, no, no |
| `codex -c tui.whimsy=false` | no | no, no, no |

With the flag the idle composer is the plain `› Ask Codex to do anything` and
the tail is byte-stable. `~/.codex/config.toml` on this machine already has
`[tui] pet = "disabled"` but no `animations` key.

## Proposed fix (layers, in priority order)

1. **Launch-side (primary, deterministic).** `aitask_codeagent.sh` builds every
   framework Codex argv — the skill launches (`pick`, `explain`, `qa`,
   `explore`, **`shadow`**, `learn`, `work-report`, `trail`) and the
   `batch-review` / `raw` operations, including the `codex resume <sid>`
   rebuild. Insert `-c tui.animations=false` into each, so every agent and
   every shadow the framework spawns is animation-free regardless of the user's
   global config. Prefer `tui.animations` over `tui.whimsy` (narrower, named
   for what it does).
2. **Per-project config (durable, covers hand launches inside the project).**
   Add `[tui] animations = false` to the Codex seed
   (`seed/codex_config.seed.toml`, the source of `.codex/config.toml`) and make
   sure `merge_codex_settings` in `aitask_setup.sh` merges a `[tui]` table
   into an existing project config. Verify first that Codex honours `[tui]`
   from the project-local `.codex/config.toml` (only the `-c` override path was
   measured).
3. **Detector-side defense (optional, for panes launched outside the
   framework).** Treat U+2800–U+28FF as decoration: drop it from the compare
   value in `classify_content` and from the composer line before
   `_CODEX_COMPOSER_RE` / the dim-strip test in `_codex_state`. None of the
   three supported agents use Braille as a *working* spinner (Claude:
   `✽✳✶✻…`, Codex: `• Working`, OpenCode: `⬝■`), so this does not violate the
   "never strip the activity dot" rule in
   `aidocs/framework/monitor_idle_and_prompt_detection.md` — but it is a
   broader normalisation than the ANSI strip and must ship with a negative
   control proving a real content change still resets idle. Decide at planning
   whether this layer is worth its blast radius once layers 1–2 exist.

## Tests / docs to touch

- `tests/test_idle_compare_modes.py` — a starfield fixture (two ticks that
  differ only in Braille glyphs) must read idle under the fix, and a
  visible-text change must still reset idle.
- `tests/review_loop_fixtures.py` + `tests/test_review_loop.py` — add a
  0.154.0 at-rest capture with the starfield (raw ANSI, like
  `CODEX_AT_REST_RAW`) and pin `_codex_state` on it; note the existing Codex
  fixtures are 0.146.0 and pre-date the animation.
- A launcher test asserting the Codex argv carries the `-c` override for the
  shadow and skill operations (see how `aitask_codeagent.sh` is already
  covered).
- `aidocs/framework/monitor_idle_and_prompt_detection.md` — record the
  visible-glyph-animation class alongside the colour-animation note, and the
  launch-side flag as the sanctioned answer.

## Not in scope

- `t1522` (Codex startup update-available dialog has no prompt pattern) is a
  sibling defect in the same files but a different mechanism; leave it separate.

## Evidence

Live captures from this exploration are in the session scratchpad
(`caps/raw_1..8.txt` for the shadow pane, `caps_{baseline,anim,whimsy}/` for
the throwaway launches); re-capture rather than relying on them if the
scratchpad is gone.
