---
Task: t2112_show_trail_generated_at_in_trails_banner.md
Base branch: main
Output branch: main
---

# t2112 — Show the trail's generation time in the trails banner

## Context

`ait trails` (and the board's By-Trail view, same `TrailScreenMixin`) shows the
active trail's title + freshness marker in the header banner, but not when the
trail was generated. The only place `generation.generated_at` appears is the
`s` selection modal, as the raw UTC ISO string. Goal: a compact, local-time
"generated at" note in the banner that never displaces the `(⚠ stale: N)`
marker, and renders nothing for absent/garbage values.

Current-branch mode (profile `fast`); no worktree.

## Design decisions

- **Format.** `gen MM-DD HH:MM` in **local time** when the generation year
  equals the current local year (e.g. `gen 07-10 17:00`); `gen YYYY-MM-DD`
  otherwise, so an old trail never reads as recent (the note exists to tell
  age). Both forms are ≤15 cells. Banner note = `" · gen …"`.
- **Strict parsing — the schema's own grammar.** Accept exactly the trail
  schema's `$defs.timestamp` pattern
  (`.aitask-scripts/lib/implementation_trail.schema.json:325-328`):
  `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$` — UTC `Z` only, seconds optional
  (minute precision `2026-07-10T14:00Z` is schema-valid and must render). Compiled
  with `re.ASCII` so `\d` means what JSON-Schema means. `Z` → `+00:00`, then
  `datetime.fromisoformat` (accepts both forms on CPython and the PyPy 3.11 board
  runtime — verified). Non-string / date-only / naive / offset-bearing
  (not schema-valid) / out-of-range → `""`. **Parse and local conversion are one
  guarded operation**: `astimezone` can overflow on a schema-valid boundary date
  (`9999-12-31T23:59:59Z` in UTC+3 raises `OverflowError` — reproduced), and the
  helper runs inside `_refresh_subtitle` and modal construction, so
  `(ValueError, OverflowError, OSError)` from either step → `""`. The banner never
  echoes artifact strings.
- **Ladder placement: additive-if-it-fits, ahead of depth.** Like the depth
  note (t1505_1), the gen note is kept OUT of the shed rungs: it is shown only
  while the untruncated banner (with it) fits the budget, then dropped whole
  before the title is ever elided. Rungs 1–4 stay byte-identical to today, so the
  freshness marker remains the last survivor. Between the two additive notes,
  generation has priority over depth (it is the age the user asked for; depth
  is an advisory rendering hint): try gen, then add depth if it still fits.
  Rationale goes in the `_trail_banner` docstring/comment, written like the
  depth note's.
- **Display position:** directly after the quoted title (it describes the
  trail named): `By-Trail: "Title" · gen 07-10 17:00 (⚠ stale: 2) · owner t9 archived · lite`.
  Position is safe because the note only ever appears when the whole string fits.
- **Selection modal (optional item — doing it):** the row's `updated` field uses
  the same formatter (`07-10 17:00` / `2025-07-10`), falling back to the
  existing raw-string / `?` behaviour when unparseable — so banner and modal
  show the same local time instead of one local and one UTC.
- **Refresh:** `_on_trail_reload` and `_activate_trail` already funnel into
  `_refresh_subtitle`, which will read the new `generated_at` from
  `self._trail_doc`; `r` (local re-project) leaves it unchanged. No extra wiring;
  verified by a test that swaps `_trail_doc` and re-runs `_refresh_subtitle`.

## Steps

1. **`.aitask-scripts/board/board_trail_view.py`** — add a module-level pure
   helper next to `trail_summary_text`:
   ```python
   # The trail schema's $defs.timestamp pattern, verbatim (pinned by a test).
   _GENERATED_AT_RE = re.compile(
       r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?Z$", re.ASCII)

   def trail_generated_label(value, *, tz=None, now=None) -> str:
       """Local-time label for generation.generated_at (t2112) …"""
       if not isinstance(value, str) or not _GENERATED_AT_RE.fullmatch(value):
           return ""
       try:
           local = datetime.fromisoformat(
               value[:-1] + "+00:00").astimezone(tz)
           today = (now or datetime.now(local.tzinfo)).astimezone(local.tzinfo)
       except (ValueError, OverflowError, OSError):
           return ""
       if local.year == today.year:
           return local.strftime("%m-%d %H:%M")
       return local.strftime("%Y-%m-%d")
   ```
   (`tz=None` → system local zone; `tz`/`now` are seams for tests. The pattern
   string is the schema's verbatim; `fullmatch` is used because Python's `$`
   also matches before a trailing `\n` — `fullmatch` must consume the newline
   and so rejects `"…Z\n"`, pinned by a test.)
   In `TrailSelectItem.__init__` (~line 672): compute
   `raw = (doc.get("generation") or {}).get("generated_at")`;
   `updated = trail_generated_label(raw) or str(raw or "?")`.
   Guard `doc.get("generation")` being a non-dict the same way as today.

2. **`.aitask-scripts/board/board_trail_screen.py`**
   - import `trail_generated_label` in the existing `from board_trail_view import (...)`.
   - new `_trail_generated_note(self) -> str`: reads
     `(self._trail_doc or {}).get("generation")`, requires a dict, returns
     `f" · gen {label}"` or `""`. Docstring mirrors `_trail_depth_note`
     (absent/unparseable renders nothing; header is not a place for artifact strings).
   - `_trail_banner(title, suffix, owner_note, depth_note="", gen_note="")`:
     replace the depth-only additive block with a priority-ordered additive
     block:
     ```python
     def fits(s): return not budget or cell_len(s) <= budget
     def compose(gen, depth):
         return f'By-Trail: "{title}"{gen}{suffix}{owner_note}{depth}'
     shown_gen = gen_note if gen_note and fits(compose(gen_note, "")) else ""
     shown_depth = (depth_note if depth_note and fits(compose(shown_gen, depth_note))
                    else "")
     if shown_gen or shown_depth:
         return compose(shown_gen, shown_depth)
     ```
     then the unchanged `full` / rung 2 / 3 / 4 code. Update the comment to cover
     both notes and the gen>depth priority.
   - `_refresh_subtitle`: pass `self._trail_generated_note()` as `gen_note`.
     `trail unavailable` and no-doc branches untouched.

3. **`tests/test_board_bytrail_view.py`**
   - `TrailDepthLabelTests._doc`: `doc.pop("generation", None)` with a comment —
     the shared fixture (`gate_framework.json`) carries a `generated_at`, and these
     tests isolate the depth note; the interaction is pinned in the new class.
     (Otherwise `test_absent_hint_renders_nothing_and_never_deep`'s `" · "` check
     and the byte-identity control would see the new note.)
   - New `TrailGeneratedLabelTests(unittest.TestCase)` — pure helper, explicit
     `tz=timezone(timedelta(hours=3))` and fixed `now`:
     `2026-07-10T14:00:00Z` → `07-10 17:00`; **minute precision**
     `2026-07-10T14:00Z` → `07-10 17:00`; previous year → `2025-07-10`; day
     rollover across the zone (`2026-07-10T23:30Z` → `07-11 02:30`);
     **boundary overflow** `9999-12-31T23:59:59Z` with UTC+3 → `""` (no raise);
     `None`, `42`, `""`, `"2026-08-01"`, naive `"2026-07-10T14:00:00"`,
     offset `"2026-07-10T14:00:00+02:00"` (not schema-valid),
     `"2026-13-40T99:00:00Z"`, `"2026-07-10T14:00:00Z\n"`, `"[bold]x[/]"` → `""`.
     Plus a pin test: the helper's pattern equals the schema file's
     `$defs.timestamp.pattern` (read from the JSON), so the two grammars cannot drift.
   - New `TrailGeneratedBannerTests(ByTrailTestBase)` — boots the app with
     `TZ` forced to a fixed non-UTC zone (`patch.dict(os.environ, {"TZ": "UTC-3"})`
     + `time.tzset()`, restored + re-`tzset()` in `finally`), doc title
     `"Gen trail"`, `generated_at = f"{datetime.now().year}-07-10T14:00:00Z"`
     (year tracks now so the test is not a time bomb), drift STALE ×1.
     Independent hand-written expected strings, no second `_trail_banner` call:
     - wide (160): `sub_title == 'By-Trail: "Gen trail" · gen 07-10 17:00 (⚠ stale: 1)'`
       and the note reaches `_screen_rows(app)[0]`;
     - shed per rung, marker kept: direct `_trail_banner` calls with the budget
       patched (`patch.object(app, "_banner_budget", return_value=N)`) so each
       rung is hit exactly: budget = len(full-with-gen) → gen shown; len-1 → exactly
       today's `full` (gen dropped, title intact); budget forcing rung 2
       (elided title, no gen), rung 3 (`By-Trail: (⚠ stale: 1)`), rung 4
       (`⚠ stale: 1`) — each expected string written out literally;
     - gen + depth: at a budget that fits gen but not gen+depth → gen kept,
       depth dropped; at unlimited budget both, in display order;
     - absent / malformed `generated_at` (missing `generation`, `None`, `"?"`,
       date-only) → `sub_title` equals the literal pre-change banner
       `'By-Trail: "Gen trail" (⚠ stale: 1)'` at 160, and at 60 equals the
       literal rung output;
     - reload seam: replace `app._trail_doc` with a doc carrying a different
       `generated_at`, call `app._refresh_subtitle()`, assert the new label.
   - Modal: extend an existing `TrailSelectItem` test or add one asserting a
     parseable `generated_at` renders the local label and `"2026-08-01"` still
     renders raw (fallback unchanged).

## Verification

- `python3 -m pytest tests/test_board_bytrail_view.py tests/test_board_trail_view.py -q`
  (CPython), and `~/.aitask/pypy_venv/bin/python -m pytest` on the helper tests
  if pytest is available there (else a one-off import check of the helper).
- `bash tests/run_all_python_tests.sh` — read the final `PYTHON SUITE:` line
  (covers the serial carve-out, incl. `tests/test_board_header_row_live.py`,
  and trails-app tests).
- Manual: `ait trails` on a real trail — banner shows `· gen …` in local time
  at a wide terminal; narrow the terminal and the note disappears before the
  title is elided; the `s` modal shows the same time.

## Step 9 (Post-Implementation)

Current-branch mode: no merge; commit code + plan separately, then archive via
`aitask_archive.sh 2112` and push with `./ait git push`.

## Risk

### Code-health risk: low
- None identified. (Change is confined to two board modules and additive to the
  banner; the shed rungs are untouched and pinned by literal-string tests.)

### Goal-achievement risk: low
- None identified. (Depth may now be dropped at middle widths where gen consumed
  the room — a deliberate, documented priority, pinned by a test.)

## Post-Review Changes

### Change Request 1 (2026-10-21 17:45)
- **Requested by user:** `trail_generated_label` evaluated "now" in the generation timestamp's fixed offset (`local.tzinfo`); across a DST change that put New Year's Eve local time in the next year (TZ=Europe/Berlin, generated 2026-07-10T14:00Z, now 2026-12-31T22:30Z → returned `2026-07-10` instead of `07-10 16:00`).
- **Changes made:** `today = (now or datetime.now(timezone.utc)).astimezone(tz)` — converted on its own to the current local offset. Added `test_now_uses_the_current_offset_not_the_generation_offset` (POSIX Berlin rule string, no tzdata); red-proofed against the old expression (old "today" = 2027-01-01 00:30+02:00).
- **Files affected:** `.aitask-scripts/board/board_trail_view.py`, `tests/test_board_bytrail_view.py`

## Final Implementation Notes
- **Actual work done:** `trail_generated_label()` (board_trail_view.py) — schema-grammar parse (`$defs.timestamp`, seconds optional, `Z` only, `re.ASCII`, `fullmatch`), guarded parse+conversion, local `MM-DD HH:MM` same-year / `YYYY-MM-DD` otherwise. `_trail_generated_note()` + `_trail_banner(..., gen_note)` (board_trail_screen.py): additive-if-it-fits, tried before depth, placed right after the title; rungs 1–4 unchanged. Selection-modal `updated` field uses the same label, falling back to the raw / `?` rendering. 14 new tests in `tests/test_board_bytrail_view.py` (`TrailGeneratedLabelTests`, `TrailGeneratedBannerTests`), all with literal expected strings.
- **Deviations from plan:** (1) The board re-exports every `board_trail_view` name and `tests/test_board_trail_view.py::SingleHomeTests` pins that set, so `_GENERATED_AT_RE` / `trail_generated_label` were added to `aitask_board.py`'s import block and to `VIEW_ONLY_NAMES` (caught by the full suite). Tests read both off the board (`self.ab.…`). (2) Reload-seam test drives the real `d` key → `load_trail_blob` worker → `_on_trail_reload` path rather than swapping `_trail_doc` by hand. (3) Post-review DST fix (see Change Request 1).
- **Issues encountered:** The shared trail fixture (`gate_framework.json`) carries a `generated_at`, so `TrailDepthLabelTests._doc` now pops `generation` to keep isolating the depth note.
- **Key decisions:** Generation outranks depth among the additive notes; offsets are rejected because the schema rejects them; banner tests force the zone with POSIX TZ strings (`UTC-3`, Berlin's rule) so no tzdata is needed, and build same-year inputs from the current year so they are not time bombs.
- **Upstream defects identified:** None
