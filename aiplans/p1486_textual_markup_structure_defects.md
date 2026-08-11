---
Task: t1486_textual_markup_structure_defects.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1486 — Textual markup **structure** defects (brackets & tag pairing)

## Context

t1453 fixed the *colour-resolution* defect class (Textual silently drops style
tokens it cannot parse) and shipped `tests/test_textual_markup_colours.py` to
guard it. That guard validates a token's **style vocabulary**; it says nothing
about markup **structure** — whether brackets meant as literal text are being
eaten as tags, and whether a closing tag matches its opening tag. Three live
defects of that second class were found and are not fixed by t1453.

All three were re-verified in this session against the real parser
(textual 8.2.7, `Content.from_markup`), not inferred from source:

| markup | result |
|---|---|
| `[#e24329]GL[/e24329]` | **raises** `MarkupError: closing tag '[/e24329]' does not match any open tag` |
| `  [bold yellow][AUTO][/]` | renders `'  '` — the badge text is gone |
| `File: /var/log/x  [size: 4096]  [live] [raw]` | renders `'File: /var/log/x  [size: 4096]   '` — `[live]`/`[raw]` gone |

The board case is the serious one: a hard crash on the compositor path, fired by
real data (any task whose `issue:` frontmatter points at a GitLab host).
`[size: 4096]` survives only by accident — the space and colon make it an
invalid tag — which is why part of the same string renders correctly and the
defect is easy to miss by eye.

**Outcome:** the three sites render their intended text; a mismatched closing
tag becomes statically detectable **wherever its opening tag lives in the same
Python string expression** (the board shape, and every other shape the repo
currently uses — measured, see §4); and all three fixed sites are pinned by
live-render tests.

## Implementation

### 1. `aitask_board.py` — close the tag correctly

`.aitask-scripts/board/aitask_board.py`, `_issue_indicator` (line 172) and
`_pr_indicator` (line 184): the closing tags omit the `#` of the opening
`[#e24329]`. Replace both with the auto-close `[/]`:

```python
return "[#e24329]GL[/]"        # was [/e24329]
return "[#e24329]MR:GL[/]"     # was [/e24329]
```

Verified: `Content.from_markup("[#e24329]GL[/]").plain == "GL"`, span style
`#e24329`. `[/]` matches the style already used by every neighbouring branch in
these two functions.

### 2. `monitor_app.py` — escape the literal `[AUTO]`

`.aitask-scripts/monitor/monitor_app.py:1495` (`_rebuild_session_bar`):

```python
auto_tag = "  [bold yellow]\\[AUTO][/]" if self._auto_switch else ""
```

`\[` is the repo's existing escaping convention — `lib/tui_switcher.py:770,828`,
`codebrowser/history_list.py:126,128`. Verified: renders `'  [AUTO]'` with span
style `bold yellow`. (The *other* auto indicator, `_agents_header_text`'s
`⟳ AUTO` at line 1294, has no brackets and is already correct — leave it.)

### 3. `logview_app.py` — escape the literal brackets in the header

`.aitask-scripts/logview/logview_app.py:72-74` (`_header_text`), rendered into a
markup-parsing `Static`:

```python
mode = " \\[raw]" if self.raw_mode else ""
return f"File: {self.log_path}  \\[size: {self._last_pos}]  \\[{state}]{mode}"
```

`[size: …]` is escaped too even though it currently survives: its survival is an
accident of the space-and-colon making it an invalid tag, and leaving it
unescaped keeps a working line one formatting change away from vanishing.
Verified: renders `File: … [size: 4096] [live] [raw]`.

### 4. Rule C — structural tag-pairing scan

Extend `tests/test_textual_markup_colours.py` (t1453's guard) with a third rule
alongside Rule A (bracketed style tokens) and Rule B (bare style strings).

**Oracle:** `textual.content.Content.from_markup()` — Textual's own parser, same
"no vocabulary to maintain" property as Rule A's `parse_style`.

**Scanned unit:** the *whole markup expression*, not the individual
`ast.Constant`. A `JoinedStr` is reconstructed by concatenating its literal
parts and substituting a placeholder (`"red"`) for each `FormattedValue`;
sub-nodes of a `JoinedStr` are not scanned separately. This is load-bearing:
scanning per-constant flags `f"[bold]{x}[/bold] [dim]("` as a mismatched close,
because the AST splits it into fragments (measured: 3 false positives at
`settings_app.py:3178`, `stats/panes/overview.py:33`,
`stats/panes/pipeline.py:62`).

**Gate — a string is scanned only when both hold:**
1. it contains a **named** closing tag `[/x]` (`_CLOSE_RE`, honouring `\[`), and
2. it contains ≥1 Rule-A *candidate* opening tag (reuse the existing
   `_is_candidate`).

Docstrings and `SELF_REFERENTIAL_MODULES` are excluded, as for Rules A/B.

**Why that gate.** It is what turns the rule from unusable into exact. Measured
over `.aitask-scripts/**/*.py` + `tests/**/*.py`:

| variant | strings scanned | findings | real |
|---|---|---|---|
| naive per-constant round-trip, no gate | 1058 | 61 | 2 |
| + gate, still per-constant | 100 | 5 | 2 |
| + gate + JoinedStr reconstruction (**chosen**) | 171 | **2** | **2** |

Requirement 1 drops the bare-`[/]` fragment noise (a `[/]` with nothing to close
is how half the repo's runtime-assembled strings legitimately look in isolation);
requirement 2 drops CLI usage grammars (`create <handle> [backend=<name>]`),
protocol docs, and concern-parser fixtures.

Implementation notes:
- Add `scan_repo_structure()` as a **separate** scanner from `scan_repo()`.
  Structural findings must not enter `RICH_RENDERER_WAIVERS` / `WaiverHygieneTests`
  — that waiver key is Rule-B semantics (a token consumed by Rich instead of
  Textual), which has no meaning for a broken tag pair.
- New `MarkupStructureScanTests` with (a) the zero-findings assertion carrying a
  remedy string, and (b) a not-vacuous assertion (`gated > 100`), mirroring
  `test_the_scan_is_not_vacuous`.
- Extend the module docstring's **Scope** section from "Two rules" to three, and
  state Rule C's non-scope explicitly (below).

**Coverage statement (this is the claim the docstring will make — not
"repo-wide").** Rule C flags a **named** closing tag that matches no open tag,
when both tags live in **one Python string expression** — a single
`ast.Constant`, or one f-string reconstructed with its interpolations replaced
by the placeholder — and that expression carries ≥1 Rule-A-recognised opening
tag. Each shape below was probed against the implementation, not assumed:

| shape | Rule C |
|---|---|
| `"[#e24329]GL[/e24329]"` (the board defect) | **caught** |
| `f"[{color}]GL[/e24329]"` — dynamic open, bad named close | **caught** (placeholder supplies the open) |
| `f"[{color}]GL[/color]"` — close names the *variable*, not its value | **caught** |
| `f"[bold]{n}[/bold] [dim]("` — f-string fragment | not flagged (correct: reconstruction) |
| `")[/dim]"` — named close, no candidate open | not flagged (correct: fragment) |
| `"[bold]" + name + "[/bolt]"` — assembled across expressions | **missed** |
| `"[@click=app.foo]x[/bolt]"` — action-link open | **missed** |
| `f"[{a}]x[/{b}]"` — both tag names dynamic | **missed** (placeholder makes them agree) |
| `"  [bold yellow][AUTO][/]"` — literal-bracket class | **missed, by design** |

The four misses are stated gaps, in the module's existing "Not in scope (each
for a stated reason, not by oversight)" style, each with its measured weight in
this repo:

- **Cross-expression assembly.** The scanned unit is one expression; joining
  them needs dataflow analysis. Repo instances of a markup tag pair split across
  `+`-concatenation: **1** (`monitor/desync_summary.py:109`, and it is correct).
- **Action-link opening tags** (`[@…]`). `_is_candidate` rejects `@`-prefixed
  tokens, deliberately, and Rule A's own fixture at
  `test_textual_markup_colours.py:575` pins that. Real `[@click=…]` markup sites
  in the repo: **0** — broadening the gate for them would be speculative.
- **Both tag names dynamic.** Undecidable statically; same boundary Rule A
  states for fully-dynamic tags, where Rule B is the compensating control.
- **The literal-bracket class** (defects 2 and 3). `[AUTO]`, `[live]`, `[raw]`
  are *syntactically valid* unknown tags, indistinguishable statically from an
  intentional dynamic style. The task itself concludes these "may be better
  served by escaping conventions than by a scan"; §5 pins the three fixed sites
  behaviourally instead.

Discrimination tests (added to `ScannerDiscriminationTests`, which already lives
in the self-referential module so bad-markup fixtures are safe there) — one per
row of the table above, so the boundary is **checkable rather than prose** and a
future broadening of the gate shows up as a failing "missed" test rather than
silently contradicting the docstring.

### 5. `tests/test_textual_markup_structure.py` — behavioural pins

New module, driving the **real** producers rather than replica strings:

- **board:** call `_issue_indicator` / `_pr_indicator` with a GitLab URL; assert
  `Content.from_markup(...)` does not raise and `.plain` is `"GL"` / `"MR:GL"`.
  (Also GitHub/Bitbucket/fallback, so the whole branch set is covered.)
- **monitor:** `MonitorApp(...).run_test()`, `action_toggle_auto_switch()`, then
  assert the rendered `#session-bar` content contains the literal `[AUTO]`.
  Harness precedent: `tests/test_monitor_refresh_no_sync_tmux.py:168`.
- **logview:** `LogViewApp(...).run_test()`, asserting on the rendered
  `#header-info`, not on `_header_text()` in isolation.

  **The fixture must be a non-empty temp log.** `action_toggle_raw` (line 130)
  does *not* update the header itself — it flips `raw_mode`, resets
  `_last_pos = 0`, clears the `RichLog` and delegates to `_read_and_append`,
  which updates `#header-info` only on its **last** line and returns early when
  `not data` (line 97) or the path is missing (line 87). Against an empty or
  absent file the header is therefore never refreshed and `[raw]` can never be
  observed — the test would fail even with the markup fix correct, i.e. it would
  not be measuring the fix. So: write bytes to a `tempfile` log first.

  Shape:
  - one `tail=True` app over the seeded file → assert `[live]`; press `r` →
    assert `[raw]` (and that `[live]` is still there); press `p` → assert
    `[paused]`. (`action_toggle_pause` updates the header directly, so it is
    data-independent, but it shares the same app.)
  - one separate `tail=False` app over the same file → assert `[static]`
    (`tail` is constructor-only; `[static]` is unreachable from the first app).

  `tail=True` starts the daemon poll thread in `on_mount`; the file stays static
  during the test so the thread stays quiet, and `on_unmount` (line 178) sets
  `_stop`, so `run_test`'s teardown terminates it.

Assertions read the **rendered plain text**, never `render().spans` — a span can
hold an unresolved tag and still look fine, which is precisely how this defect
class hides.

### Post-phase (risk mitigations)

1. `[isolate_monitor_commit]` Build the `monitor_app.py` commit so it carries
   **only** the line-1495 change. A concurrent session holds uncommitted hunks in
   that file at lines 54, 1133, 2992 and 3047; `git add <file>` or
   `git commit -o -- <file>` would sweep them into the t1486 commit — the exact
   leak commit `8b584ff39` had to undo for t1453. Procedure: write a patch of the
   single hunk, `git apply --cached` it, confirm `git diff --cached --name-only`
   lists only the intended paths, confirm `git diff --cached -- <file>` is the one
   line, then `git commit` the index (no `-a`, no path override). Verify after the
   commit that `git diff HEAD~1 HEAD -- <file>` is exactly that hunk and that the
   foreign hunks are still present in the worktree.

2. `[negative_control_sweep]` Prove each new assertion can fail, one mutation at
   a time, reverting between: (a) restore `[/e24329]` at `aitask_board.py:172` →
   Rule C must report it by name and the board pin must fail; (b) drop the `\` at
   `monitor_app.py:1495` → the `[AUTO]` pin must fail while Rule C stays green
   (this is the documented boundary, so a *passing* Rule C here is the correct
   result); (c) drop the `\` before `[raw]` in `logview_app.py` → the logview pin
   must fail. Record the named failing test id for each in the Final
   Implementation Notes. Also confirm the four "missed" rows of the §4 coverage
   table are missed **because of the gate**, not because the fixture is
   malformed: each must parse cleanly under `Content.from_markup` *or* be shown
   to be excluded at the gate, so a "not flagged" assertion can never pass
   vacuously.

## Verification

```bash
# Rule C + colour guard
~/.aitask/venv/bin/python tests/test_textual_markup_colours.py
# new behavioural pins
~/.aitask/venv/bin/python tests/test_textual_markup_structure.py
# neighbours that render these surfaces
bash tests/run_all_python_tests.sh --test-dir tests
```
Read only the last line of the suite run for the verdict
(`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`); a `Results: N passed` line
earlier belongs to one script-style module.

Manual: `ait logview <some log>` shows `[live]` and, after `r`, `[raw]`;
`ait monitor` with auto-switch toggled shows `[AUTO]` in the session bar; a task
carrying a GitLab `issue:` URL renders `GL` on the board instead of crashing it.

Step 9 (Post-Implementation) handles merge and archival.

## Risk

### Code-health risk: medium
- `monitor_app.py` carries uncommitted hunks from a **concurrent session**
  (lines 54/1133/2992/3047); a naive stage of my line-1495 change would commit
  foreign work under `(t1486)` · severity: medium · → mitigation: inline post-phase isolate_monitor_commit
- Rule C is a repo-wide guard: a future legitimate markup shape its heuristic
  gate mis-reads would fail the suite on an unrelated commit. Zero false
  positives measured today over 171 gated strings, but the gate is a heuristic,
  not a proof · severity: low · → mitigation: inline post-phase negative_control_sweep
- The new module drives two live Textual apps (`run_test`), adding suite runtime
  and a flake surface · severity: low · → mitigation: None (precedent exists at
  `test_monitor_refresh_no_sync_tmux.py`; both apps already boot in tests)

### Goal-achievement risk: low
- Rule C's coverage is narrower than "every mismatched close in the repo": four
  shapes are out of reach (cross-expression assembly, action-link opens, both
  tag names dynamic, and the literal-bracket class). The risk is not the gap
  itself but a guard that *reads* as total · severity: low · → mitigation:
  inline post-phase negative_control_sweep (the coverage table is stated in the
  docstring and each row — hit **and** miss — is pinned by a discrimination
  test, so the claim cannot drift from the code)

### Planned mitigations
- timing: post-phase | name: isolate_monitor_commit | type: chore | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — foreign hunks in monitor_app.py | desc: build the monitor_app.py commit from an index-level patch of only the line-1495 hunk and verify the committed blob
- timing: post-phase | name: negative_control_sweep | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — Rule C heuristic; and pin efficacy | desc: one mutation at a time, prove Rule C and each behavioural pin can fail, including that Rule C correctly stays green on the literal-bracket boundary
