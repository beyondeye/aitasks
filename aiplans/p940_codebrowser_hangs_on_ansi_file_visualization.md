---
Task: t940_codebrowser_hangs_on_ansi_file_visualization.md
Base branch: main
plan_verified: []
---

# Plan: Fix codebrowser hang on ANSI / control-char files (t940)

## Context

`ait codebrowser` hangs (TUI freezes indefinitely) when opening a file that
contains raw terminal control bytes — reproduced with
`aitasks_go/demos/footer/golden/footer.ansi` (a 343-byte captured-ANSI file
full of `\033[…m` SGR escape sequences).

**Root cause (verified empirically):** The hang is *not* in file reading or
syntax highlighting — it is in **Rich's rendering**. When `CodeViewer`
truncates a long line to fit the code column, Rich's
`set_cell_size → cells._split_text → split_graphemes` (Rich on Python 3.14)
goes pathologically slow / never returns when the line embeds C0 control
characters such as ESC (`0x1b`). It only triggers on lines that exceed the
column width (in the repro, line 24 is 281 chars with many ESC sequences);
short control-char lines and long *plain* lines both render fine. Traceback
confirmed at `rich/cells.py:202 split_graphemes` via
`rich/text.py:878 truncate`.

This is effectively an upstream Rich limitation we cannot fix there; the
correct fix is to **sanitize control characters at our display boundary**
(`CodeViewer.load_file`) before the content ever reaches Rich. This both
removes the hang and is the right behavior for a *source viewer*: raw control
bytes passed to the terminal would corrupt the display even if they didn't
hang.

Scope is single-repo: the fix lives entirely in this repo's codebrowser.
`aitasks_go` only hosts the reproduction file and needs no changes (confirmed
with the user — plan locally only, `xdeprepo` left intact as a record).

## Approach

One file changed: `.aitask-scripts/codebrowser/code_viewer.py`.

Convert non-printable C0 control characters (and DEL) into visible Unicode
"control picture" glyphs (`U+2400 + code`, e.g. ESC → `␛`; DEL → `␡ U+2421`)
**before** highlighting. Tab (`0x09`) and newline (`0x0a`) are preserved —
tabs are expanded by the existing `expandtabs(4)`, newlines delimit lines.
Control pictures are ordinary width-1 printable glyphs, so Rich renders/
truncates them with no hang, and the user sees a faithful representation of
the file's literal bytes (e.g. `␛[48;2;40;42;54m`).

### Changes in `code_viewer.py`

1. **Module-level translation table + helper** (after the imports / constants
   near the top, e.g. below `SELECTION_STYLE`):

   ```python
   # C0 control chars (except tab/newline) and DEL mapped to printable Unicode
   # "control picture" glyphs. Rich's line truncation (set_cell_size /
   # split_graphemes) can hang on long lines that embed raw control bytes such
   # as ESC (0x1b) — e.g. captured-ANSI files. Converting them to printable
   # glyphs keeps the file viewable (showing its literal bytes) and avoids the
   # hang. Tab/newline are preserved: tabs are expanded downstream; newlines
   # delimit lines.
   _CONTROL_CHAR_TRANSLATION = {
       code: 0x2400 + code
       for code in range(0x20)
       if code not in (0x09, 0x0A)  # keep tab and newline
   }
   _CONTROL_CHAR_TRANSLATION[0x7F] = 0x2421  # DEL -> ␡


   def _sanitize_control_chars(text: str) -> str:
       """Replace non-printable control characters with visible glyphs.

       Prevents a Rich rendering hang when viewing files that embed raw
       terminal control bytes (see _CONTROL_CHAR_TRANSLATION). A no-op for
       normal source files, which contain no such characters.
       """
       return text.translate(_CONTROL_CHAR_TRANSLATION)
   ```

2. **Call it in `load_file`** — after the empty-file guard, before
   `expandtabs` (lines ~148-153):

   ```python
   # Empty file
   if not content:
       self._show_message("(empty file)")
       return

   # Replace control characters Rich cannot truncate safely (e.g. ESC bytes
   # in captured-ANSI files), which otherwise hang the viewer.
   content = _sanitize_control_chars(content)

   # Normalize tabs to spaces
   content = content.expandtabs(4)
   ```

This single sanitization point covers all downstream display: `self._lines`,
`self._highlighted_lines`, the `MAX_LINE_WIDTH` truncation in
`_rebuild_display`, and viewport windowing all derive from the sanitized
`content`. `load_file` is the only path that feeds file content into the
viewer (`show_binary_info` / `_show_message` build their own Text and are
unaffected). NUL-containing files are still short-circuited as binary before
this point.

### Test — `tests/test_code_viewer_control_chars.py`

New `unittest` test matching the existing `tests/test_section_viewer_*.py`
style (insert `.aitask-scripts/codebrowser` on `sys.path`, import the helper):

- ESC (`\x1b`) → `␛` (`␛`).
- A representative SGR sequence `\x1b[48;2;40;42;54m` → `␛[48;2;40;42;54m`.
- DEL (`\x7f`) → `␡` (`␡`).
- Tab and newline preserved unchanged.
- Plain ASCII / Unicode text returned unchanged (no-op).
- Regression guard: load the actual repro content (a long line of mixed ESC +
  text, mirroring `footer.ansi` line 24), build the same `Table` the viewer
  builds, render it through a `rich.console.Console(width=120)` under a
  `signal.alarm` watchdog, and assert it completes — i.e. the sanitized path
  does not hang. (Guarded so it is skipped where `SIGALRM` is unavailable.)

## Risk

### Code-health risk: low
- Change is ~20 lines in one function plus a pure module-level helper; no
  existing behavior changes for control-char-free files (`str.translate` with
  this table is a no-op on normal source). Blast radius: a single file, single
  load path. None identified beyond this.

### Goal-achievement risk: low
- Fix verified empirically end-to-end: the exact repro file renders in ~2 ms
  after sanitization vs. an indefinite hang before. Approach (sanitize at the
  display boundary) is the sound fix since the defect is upstream in Rich.
  None identified.

_No before/after risk-mitigation tasks warranted (both axes low)._

## Verification

1. **Unit test:** `bash`-free, run directly —
   `python3 tests/test_code_viewer_control_chars.py` → all pass.
2. **Manual (the original repro):** `./ait codebrowser`, navigate to and open
   `/home/ddt/Work/aitasks_go/demos/footer/golden/footer.ansi` (or copy it into
   this repo for the test) — the viewer displays the file (escape sequences
   shown as `␛[…m` glyphs) instead of hanging; cursor/scroll work normally.
3. **No regression:** open a normal source file (e.g.
   `.aitask-scripts/codebrowser/code_viewer.py`) — renders identically to
   before, tabs/indentation intact.

## Post-implementation
Per the shared task-workflow: Step 8 user review → commit
(`bug: <desc> (t940)`) → Step 9 archival of t940 and its plan.

## Final Implementation Notes
- **Actual work done:** Implemented exactly as planned. Added
  `_CONTROL_CHAR_TRANSLATION` (module-level dict) and `_sanitize_control_chars`
  helper to `.aitask-scripts/codebrowser/code_viewer.py`, and inserted a single
  `content = _sanitize_control_chars(content)` call in `load_file` after the
  empty-file guard and before `expandtabs`. Added
  `tests/test_code_viewer_control_chars.py` (7 unittest cases: sanitizer
  mappings + a SIGALRM-guarded render-does-not-hang regression).
- **Deviations from plan:** None functional. The regression test uses
  `io.StringIO()` as the Console sink instead of `open("/dev/null")` to avoid a
  `ResourceWarning` for an unclosed file under Python 3.14.
- **Issues encountered:** None. The original hang was reproduced before the fix
  (indefinite, traced to `rich/cells.py split_graphemes` via `text.py truncate`)
  and confirmed gone after (~2 ms render of the exact repro content).
- **Key decisions:** Used Unicode "control picture" glyphs (`U+2400+code`, DEL →
  `U+2421`) rather than stripping or `�`, so the viewer faithfully shows the
  file's literal control bytes (e.g. `␛[48;2;40;42;54m`). Tab/newline are kept
  out of the table so existing indentation/line-splitting behavior is unchanged;
  `str.translate` is a no-op for normal control-char-free source.
- **Upstream defects identified:** None. The triggering defect is upstream in
  the third-party Rich library (`set_cell_size`/`split_graphemes` on Python
  3.14), not in a separate aitasks script/helper; it is handled at our display
  boundary. No separate broken module in this repo was found.
