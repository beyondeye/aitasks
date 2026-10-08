---
Task: t1914_concern_body_join_breaks_on_midtoken_hardwrap.md
Base branch: main
Output branch: main
---

# t1914 — Join concern body continuations with the intra-token rule

## Context

`concern_parser._scan_items` always space-joins body continuation rows
(`" ".join(parts)`). OpenCode draws every row itself and hard-wraps with literal
newlines **inside tokens**, which `tmux capture-pane -J` cannot rejoin. The
result is corrupted bodies, and when the break lands in the terminal trailer
the disposition, verdict, impact vector and effort are all lost. The marker
rejoin already has an intra-token rule (`_join_sep`), but bodies never use it.

## Measurement (done before planning; raw captures kept for fixtures)

The source block had 8 items. Each item had the same body with a different
leading pad, so breaks landed at different offsets. The body held these tokens:
- a dotted path `.aitask-scripts/monitor/concern_parser.py`;
- `history.csv`, `--force-verify`, `a/b/c`, `and/or` and a URL;
- the spaced dash `fix - which is cheap - lands`;
- `well-known`, `follow-up`, `pre-claim/post-claim` and `file.py:415`;
- a full trailer: `Disposition: follow-up. Verified: CONFIRMED. Improves: 3 entries. Worsens: 2 entries. Effort: low.`

Each agent was prompted to echo the block verbatim. The capture was taken with
`capture-pane -p -J` in a private tmux server:
- **OpenCode 1.18.34** (`openai/gpt-6-astra`) at 60 cols, then re-captured
  after resizing the window to 50, 72 and 90 cols (the TUI reflows on resize);
- **Codex 0.160.0** (`gpt-6.1-sol`, inline mode) at 60 cols.

Every capture row aligned with the source as an exact substring, so the model
made no echo deviations and whitespace is the only variable. For each capture,
"exact" counts bodies equal to the source and "trailer" counts concerns with
every trailer field parsed:

| capture | breaks | intra-token | current parser: exact / trailer | rule D (below): exact / trailer |
|---|---|---|---|---|
| Codex 60 | 72 | 0 | 8/8 / 8/8 | 8/8 / 8/8 |
| OpenCode 50 | 96 | 42 | 0/8 / 3/8 | 1/8 / **8/8** |
| OpenCode 60 | 74 | 37 | 0/8 / 5/8 | 3/8 / **8/8** |
| OpenCode 72 | 61 | 22 | 0/8 / 3/8 | **8/8** / **8/8** |
| OpenCode 90 | 48 | 22 | 0/8 / **0/8** | **8/8** / **8/8** |

- **Codex** breaks only at spaces. Space-join is already exact for it, and
  rule D leaves it unchanged.
- **OpenCode** breaks after these characters:
  - `-` (`follow-`, `double-`, `pre-`, and *between* the two dashes of `--force`);
  - `/` (paths, `https://`);
  - `(` (`maintainability(` / `low)` — this is what zeroed the trailer at 90
    cols, a wider loss than the task assumed);
  - a lone `.` (`in .` / `aitask-scripts`);
  - `.` inside a token (`history.` / `csv`, `example.` / `com`);
  - `:` (`https:` / `//`, `py:` / `415`).
- When OpenCode breaks at a spaced dash, it does so as `fix -` / `which`, which
  is a word break with the space consumed. That is why the existing `_join_sep`
  rule ("ends in `-` → no space") is wrong for bodies: it gets 16 of the
  OpenCode-60 breaks wrong.

Rules evaluated (wrong joins at OpenCode 60 / 90):
- A, the current space-join: 37 / 22;
- B, `_join_sep` as it stands: 16 / 15;
- C, `-`/`/` only when attached to a non-space: 14 / 8;
- **D, C plus a trailing `(` plus a lone ` .`: 5 / 0.**

What D leaves wrong is only the classes the task calls ambiguous or that cannot
be decided from the left row:
- an intra-token `.` (`history.` / `csv`): ambiguous with a sentence end;
- a `:` break (`https:` / `//`, `py:` / `415`): ambiguous with `Label: value`;
- a break between `--` (`when -` / `-force`): the left row is identical to the
  spaced-dash case.

D also has one residual that the probe did not exercise: a **lone `/`**, meaning
a slash preceded by whitespace at the end of a row, which shows up in the
plan-review concern. `foo /` / `bar` (a spaced separator) and `in /` /
`home/user` (an absolute path) look identical from the left row. D resolves this
case as a spaced separator, so the absolute path gains a space
(`in / home/user`).

This is an accepted ambiguity, and it is also a deliberate trade on the marker
path. Today's `_join_sep` joins every trailing `/` with no space, so it recovers
a split region `/home/user` exactly and pins `foo / bar` → `foo /bar` as the
known loss. Rule D flips which reading wins. The reasons for choosing it:
- spaced separators are common in prose bodies, and a body is forwarded text;
- the measured OpenCode break that was misjoined was the spaced dash (`fix -`),
  which has the same shape;
- the region is a display label and best-effort by contract.

Both readings are pinned as decisions in step 3.

All of these residuals are cosmetic. None of them touches the trailer, because the trailer
grammar's tokens never break there.

No trailer-grammar change is needed: under rule D, all 40 measured concerns
parse the full trailer. Widening `_TRAILER_SPAN` would only add acceptance
surface with no measured failure behind it.

## Implementation

### 1. `.aitask-scripts/monitor/concern_parser.py`

- Replace `_join_sep`'s body with one module-level compiled rule (rule D):
  ```python
  # A row ending here was broken *inside* a token (measured, t1914): a `-` or
  # `/` attached to the token before it, an opening paren, or a lone `.` that
  # starts the next token. A `-`/`/` preceded by whitespace is a spaced
  # separator (`fix -` / `which`), so it is a word break and keeps its space.
  _INTRA_TOKEN_BREAK = re.compile(r"(?:\S[-/]|\(|(?:^|\s)\.)$")

  def _join_sep(joined: str) -> str:
      return "" if _INTRA_TOKEN_BREAK.search(joined) else " "
  ```
  - Rewrite the docstring: one shared rule for marker and body rejoins; the
    measured break classes; the named residuals (intra-token `.`, `:`, a break
    between `--`, a suspended hyphen such as `pre-` / `and` → `pre-and`, and a
    lone `/` that starts an absolute path, `in /` / `home/user` →
    `in / home/user`, which cannot be told apart from a spaced separator).
- In `_scan_items`, replace the space-join with a fold through `_join_sep`:
  ```python
  body = ""
  for part in (p.strip() for p in parts):
      if part:
          body = part if not body else body + _join_sep(body) + part
  ```
  Leading and trailing whitespace are already stripped per part, so no final
  `.strip()` is needed.
- Update the prose that says "space-joined":
  - the `_scan_items` docstring;
  - the `_join_split_marker` docstring, where the "known imperfect case" for
    `foo / bar` is now exact. Its known imperfect case flips to a region that
    starts an absolute path after a space (`[low | /` / `home/user]` →
    `/ home/user`), plus the intra-token `.` / `:`.

### 2. `tests/fixtures/` — three verbatim real captures

Each fixture is the rows from the reply's open fence through the close fence,
copied byte for byte from the probe captures:
- `opencode_shadow_hardwrap_60_capture.txt`;
- `opencode_shadow_hardwrap_90_capture.txt`;
- `codex_shadow_hardwrap_60_capture.txt`.

### 3. `tests/test_concern_parser.py`

- Rewrite `test_prose_spaced_slash_split_is_accepted_best_effort` to
  `test_prose_spaced_slash_split_keeps_its_space`. It now expects the region
  `foo / bar`, and its docstring explains the change. The path-shaped split
  tests (`a/` / `b`) keep passing unchanged.
- Add `test_absolute_path_region_split_after_lone_slash_is_accepted_best_effort`:
  the marker `- [low | /` / `home/user] body` yields the region
  `/ home/user`. It is pinned as the flipped side of the same ambiguity, and
  its docstring names the trade.
- Add a new class `TestBodyContinuationJoin` with one oracle row per rule
  clause and per residual, built with the `block()` helper:
  - `follow-` / `up.` → `follow-up.`, and the trailer parses as `follow-up`;
  - `maintainability(` / `low).` → the full `Worsens` vector;
  - `in .` / `aitask-scripts/x` → `in .aitask-scripts/x`;
  - `src/` / `lib` → `src/lib`;
  - `the fix -` / `which` → `the fix - which` (the spaced dash keeps its space);
  - `foo /` / `bar` in a body → `foo / bar`;
  - residuals, pinned as decisions: `history.` / `csv` → `history. csv`,
    `py:` / `415` → `py: 415`, `when -` / `-force` → `when - -force`, the
    suspended hyphen `pre-` / `and post-claim` → `pre-and post-claim`, and the
    absolute path after a lone slash `Look in /` / `home/user.` →
    `Look in / home/user.`;
  - a word-boundary row (`textwrap`, no hyphen breaks) still round-trips
    exactly.
- Add a new class `TestMeasuredHardWrapCaptures`, which rebuilds the 8 source
  bodies from the same pad and body constants as the probe:
  - **Codex 60 and OpenCode 90:** every body equals its source exactly.
  - **OpenCode 60:** every body equals its source after undoing only the
    named residual spaces (`history. csv`, `https: //`, `- -force`). This pins
    each residual explicitly, so a new damage class fails the test.
  - **All three:** every concern has `disposition == "follow-up"`,
    `verdict == "CONFIRMED"`, 3 improves entries, 2 worsens entries and
    `effort == "low"`, plus `unrecovered_markers == []`.
- **Negative control:** with `_scan_items` temporarily reverted to the
  space-join, `TestMeasuredHardWrapCaptures` and the trailer rows of
  `TestBodyContinuationJoin` must fail. Check this in a scratch copy, never
  with `git stash` or `git restore` on the shared tree.

### 4. Docs — `.claude/skills/aitask-shadow/concern-format.md` (plain `.md`; rendered copies are untracked and re-rendered)

- `body` grammar bullet (~line 248): continuations are joined by the shared
  intra-token rule instead of being space-joined. State the rule in its exact
  code terms.
- "Measured renderers":
  - Codex: measured to break only at spaces, so its bodies rejoin exactly.
  - OpenCode "Residual: hard-wrapped bodies": rewrite it with this
    measurement. The trailer and attached `-` / `/` / `(` / lone-`.` breaks
    are now exact; intra-token `.` and `:` breaks and a break between `--`
    remain cosmetic. Drop "tracked separately".
  - Name the lone-`/` ambiguity there and in the split-marker region
    paragraph. A row that ends in a whitespace-preceded `/` is read as a
    spaced separator, so an absolute path split right after its leading slash
    gains a space, in a body and in a region alike.
- "Capture-join contract" (~line 400): the parser rejoins with that rule,
  which is still only right for agent-emitted breaks. Keep the `-J`
  requirement as it is.

The producer procedures' "wrap-joined" mentions are about marker brackets and
stay correct, so no `.md.j2` or golden change is needed.

### 5. Step 9 (Post-Implementation)

Commit the code and docs with `bug: … (t1914)`. Then archive through the
standard workflow.

## Verification

- `python3 tests/test_concern_parser.py`. Also run the other concern consumers:
  `tests/test_concern_body_display_contract.py`,
  `tests/test_concern_picker_modal.py`, `tests/test_monitor_concern_action.py`,
  `tests/test_minimonitor_concern_action.py`, `tests/test_shadow_seam.py` and
  `tests/test_markup_colour_contract.py`. Run them through
  `bash tests/run_all_python_tests.sh --test-dir`, or individually.
- The negative control described in step 3.
- `bash tests/test_skill_render_aitask_shadow.sh`, to confirm the doc edit
  breaks no render contract.
- Full suite: `bash tests/run_all_python_tests.sh`, then read the last-line
  verdict.

## Risk

### Code-health risk: low
- The shared `_join_sep` rule now also applies to body rows. It changes the
  bytes forwarded to the followed agent for any body whose row ends in an
  attached `-`, `/` or `(`, or a lone `.`. One false-join class remains: a
  suspended hyphen (`pre-` / `and`) becomes `pre-and`. This is cosmetic,
  measured as absent from both renderers' samples, and pinned by a test.
  · severity: low · → mitigation: none (pinned in plan step 3)
- Marker-path behaviour flip for a lone `/`. A split region `/` /
  `home/user` was recovered exactly and now gains a space (`/ home/user`),
  while `foo / bar` becomes exact instead. This is an accepted, documented
  ambiguity: the region is a best-effort display label, and both readings are
  pinned. · severity: low · → mitigation: none (pinned in plan step 3)

### Goal-achievement risk: low
- The measurement used a prompted verbatim echo, not a production `>pc`
  shadow. The renderer's wrap behaviour is the variable under test, and that
  does not depend on how the text was produced. · severity: low
  · → mitigation: none
