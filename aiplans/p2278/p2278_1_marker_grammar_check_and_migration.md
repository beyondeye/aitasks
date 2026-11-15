---
Task: t2278_1_marker_grammar_check_and_migration.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-15 18:48
---

# Plan: t2278_1 — marker grammar, check and marker migration

## Context

The website has 17 screenshot placeholders written as HTML comments in four
inconsistent shapes, and six of them name no file. Before any tool can
generate screenshots (later children of t2278), placeholders need one
machine-parseable grammar and a checker. This child defines the grammar,
ships a stdlib-only checker and its tests, migrates all 17 placeholders,
wires the check into CI and documents the grammar. The page edits are comments
only, so no rendered page changes.

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` ("Marker
grammar", "`check_screenshots.py`"). Everything is stdlib-only Python under
`website/`. Nothing goes under `.aitask-scripts/`.

## Verification findings (2026-11-15, verify path)

- `git status --short -- website/ .github/ aitasks/metadata/doc_update_guide.md`
  is clean. No in-flight edits to any marker page.
- Still exactly 17 markers. Two line numbers have moved:
  `tuis/monitor/how-to.md:140` (was 147) and `tuis/minimonitor/how-to.md:400`
  (was 407). The others are unchanged. Re-grep at step 1 anyway.
- Only one in-flight task lists marker pages: t1697 (Implementing, lock from
  2026-09-02). It lists `monitor/how-to.md` and `minimonitor/how-to.md` only
  as files its origin commit touched, and its fix is in monitor code. No
  conflict. Re-check `git status` at step 1.
- All 23 current `static-img` / `split-hero image=` / `tour-tile src=` sources
  exist under `website/static/`, so check class 4 passes on today's content and
  does not break the deploy.
- `website/` has no `screenshots/`, `check_screenshots.py` or test module yet.
- Hugo runs Goldmark with `unsafe = true`, so comments pass into the HTML but
  are not shown.
- Multi-line comments in content: `tuis/board/reference.md:299` and three in
  `workflows/contribute-and-manage/contribution-flow.md` (16, 110, 221). None
  mentions `screenshot`. The one at line 110 is an `<!--` inside inline code,
  which is why the scanner must not use a whole-file `<!--.*?-->` regex.
- **Switcher from minimonitor (resolves the parent's open point).**
  `tui_switcher.py` treats monitor and minimonitor the same way for Shift+M
  (`_COMPANION_INELIGIBLE_HOSTS`), but minimonitor opens the dialog in the
  narrow layout (`_switcher_narrow()`) and highlights a different current TUI.
  So it gets its own scene, `tui_switcher_from_minimonitor`. That makes three
  switcher scenes.

## Steps

1. **Gate.** Re-run `git status --short -- website/` and the marker grep
   (`grep -rn -i 'screenshot' website/content --include='*.md' | grep '<!--'`).
   Stop and report if any marker page is modified or the count is not 17.

2. **`website/screenshots/__init__.py`** (empty) and
   **`website/screenshots/markers.py`** (stdlib only):
   - Dataclasses `Marker(path, line, text, scene, file, alt, caption, cls)` and
     `Unparseable(path, line, text, reason)`.
   - `REQUIRED = ("scene", "file", "alt")`, `OPTIONAL = ("caption", "class")`.
   - `MARKER_RE`: a whole line (up to 3 leading spaces, trailing whitespace
     allowed) of the form `<!-- screenshot: <pairs> -->`.
   - `parse_marker(text) -> Marker | str` (the str is the rejection reason).
     It tokenizes pairs `key=value`, where a value is a bare token
     `[A-Za-z0-9_./-]+` or a `"..."` string. It rejects: anything left over
     after tokenizing, unknown keys, duplicate keys, a missing required key,
     `scene` not matching `^[a-z0-9_]+$`, an absolute `file` or one with a `..`
     segment, an empty value, and any value containing one of the
     **forbidden sequences** in `FORBIDDEN_IN_VALUE = ('"', "--", "\\")`.
     - **Why the backslash is forbidden.** `render_static_img` writes each
       value into a double-quoted Hugo shortcode parameter. Hugo's shortcode
       lexer treats `\` there as an escape, so a value ending in `\` leaves the
       string unterminated and breaks the page (reproduced on local Hugo
       0.169.0; CI's pinned 0.155.3 was not checked). Rejecting `\` at parse
       time is version-independent. Escaping would depend on the lexer's
       escape rules, which differ across versions and between the `"` and `` ` ``
       forms. Rejecting means every accepted value can be inserted verbatim.
     - `"` is forbidden because it would end the parameter. `--` is forbidden
       because it would end the HTML comment.
   - `scan(content_root) -> (markers, unparseable)`. It walks `*.md` files in
     sorted order, line by line, with these rules (modeled on how CommonMark
     detects these constructs):
     - Fenced code blocks are skipped. A fence opens on a line with up to 3
       spaces then 3 or more `` ` `` or `~`, and closes on a line using the
       same character with at least as many.
     - A **block comment** starts on a line whose first non-space characters
       (up to 3 spaces) are `<!--`, and ends on the first line, the same or a
       later one, that contains `-->`. A comment that mentions `screenshot`
       (case-insensitive) counts as a marker if it is one line and
       `parse_marker` accepts it. Otherwise it is `Unparseable` (reason: the
       parse error, or "multi-line").
     - Any other line (outside fences and block comments) that contains both
       `<!--` and `screenshot` is `Unparseable("inline comment")`. That is
       deliberately loud.
     - Block comments that do not mention `screenshot` are ignored.
   - `render_static_img(marker) -> str` returns
     `{{< static-img src="imgs/<file>" alt="..." caption="..." class="..." >}}`,
     leaving out `caption` / `class` when they are absent. As a second line of
     defense for child 5's `apply` path, it calls the same value validator and
     **raises `ValueError`** on a value with a forbidden sequence, so a
     directly constructed `Marker` cannot produce a broken shortcode either.
   - **Spec-owner reader (a shared contract with child 2's loader).**
     `SPEC_SCALAR_RE` matches one top-level key line:
     `^(?P<key>id|output): +(?P<val>"[^"\\]*"|'[^']*'|[A-Za-z0-9_./-]+)(?: +#.*)? *$`.
     A value is a plain token, a double-quoted string with no `"` or `\`, or a
     single-quoted string with no `'`. A trailing comment is allowed only
     **after at least one space**. That means `output: a.svg#x` does not
     match: the token cannot absorb `#`, and the comment group needs a space
     first. It is then a named problem, not a silent truncation to `a.svg`.
     **Separators are spaces only.** This was probed on 2026-11-15 with the
     framework venv's PyYAML: `yaml.safe_load` raises `ScannerError` on a tab
     after the colon, before a comment, and as trailing whitespace. A
     tab-separated line is therefore an unsupported-scalar problem, matching
     the loader's own refusal. One case is rejected conservatively: PyYAML
     accepts a comment glued to a closing quote (`"a.svg"#c` loads `a.svg`),
     and the reader refuses it, which is the safe direction. The parent
     design's own example
     `output: aitasks_board_child_tasks.svg   # required; relative to website/static/imgs/`
     reads as `aitasks_board_child_tasks.svg`.
   - **Bare-value typing policy.** A YAML resolver can turn a bare token into
     something other than a string: `on`/`yes`/`true` become bool, `null`
     becomes None, `123` becomes int, `1.0`/`.inf` become float, `2026-11-15`
     becomes a date, `1_000`/`0x1F` become int. So a bare value is accepted
     only when it is a string under any resolver. It must match
     `BARE_STRING_RE = ^[A-Za-z][A-Za-z0-9_./-]*$`, which starts with a letter
     and so rules out every numeric, date, sexagesimal and `.inf`/`.nan`
     form. Its lowercased form must also not be in
     `YAML_KEYWORDS = {"yes", "no", "true", "false", "on", "off", "null", "y", "n"}`.
     PyYAML itself loads `y`/`n` as strings, but YAML 1.1 lists them as
     booleans and other loaders may follow it, so they stay in the set as a
     conservative choice. Any other bare value is the problem
     `"<key>: bare value '<v>' may not load as a string in YAML; quote it"`.
     Quoted values are always accepted, because with no escapes they load
     verbatim. So `id: "123"` is how a digit-leading scene id is written.
     This policy is bounded and conservative: it may ask for quotes that
     PyYAML would not strictly need (e.g. `_x`, `yEs`), but it never accepts a
     line PyYAML loads differently.
   - `read_spec_owner(path) -> SpecOwner(id, output, problems)`: for each of
     `id` / `output`, a line starting `<key>:` at column 0 that does not match
     `SPEC_SCALAR_RE` is a problem `"<key>: is not a supported single-line
     scalar"`. A matching line that fails the bare-value policy is the problem
     above. Both are reported as `OWNERSHIP`, never as a missing key, so an
     unsupported form is named rather than mistaken for absence. Zero lines is
     `"<key>: missing"`. More than one line is `"<key>: duplicated"`. Quotes
     are stripped once. PyYAML is not needed. **The contract:** every value
     the reader accepts is the string `yaml.safe_load` produces for that
     line. Child 2's agreement check imports `SPEC_SCALAR_RE` /
     `read_spec_owner` rather than copying the pattern.
   - `scan_image_sources(content_root)` returns `(path, line, shortcode, src)`
     for each `{{< static-img ... >}}` (`src=`), `{{< split-hero ... >}}`
     (`image=`) and `{{< tour-tile ... >}}` (`src=`) call. The match is
     multi-line (DOTALL), and an escaped `{{</* */>}}` does not match.

3. **`website/check_screenshots.py`** (stdlib only; same docstring/argparse
   shape as `check_links.py`; puts its own directory on `sys.path` and imports
   `screenshots.markers`). The defaults resolve against the script's directory:
   `--content content`, `--static static`, `--scenes screenshots/scenes`.
   Each record is printed as `<rel path>:<line>: <CLASS>: <detail>`.
   1. `UNPARSEABLE` — fails.
   2. `NO_SCENE` (no `<scenes>/<scene>.yaml`). Its severity comes from the
      constant `MISSING_SCENE_SEVERITY = "warning"`. Child 5 changes it to
      `"error"`.
   3. `OWNERSHIP` — fails on any of: a marker whose `file=` differs from its
      spec's `output:`, two specs with the same `output:`, a spec with no
      `output:`, or a spec whose `id:` differs from its file stem.
   4. `MISSING_IMAGE` — an image shortcode source with no file under
      `<static>/`. Fails.
   5. `UNRESOLVED` — every valid marker is listed. Exit 0 unless `--strict`.
   6. `--owners` prints every file under `<static>/imgs/` (sorted, relative to
      `imgs/`) with the scene whose spec `output:` names it, or `hand-made`,
      then exits 0.
   Summary lines are `markers`, `unparseable`, `no-scene (<severity>)`,
   `ownership`, `missing-image`, ending with
   `SCREENSHOTS: PASSED|FAILED`. `--report` prints only the records and exits
   0. `main(argv=None) -> int` so tests can call it.

4. **`tests/test_check_screenshots.py`** (unittest; uses the `sys.path.insert`
   pattern from `tests/test_check_link_relevance.py`). Each test builds a
   scratch tree (content / static / scenes) in a `TemporaryDirectory` and
   never reads the real `website/content/`. Cases:
   - The four legacy shapes (`TODO screenshot: f.svg — d`,
     `TODO screenshot: f.svg`, `SCREENSHOT: f.svg — d`, `SCREENSHOT: d`) are
     each reported as unparseable.
   - A valid marker parses, and `render_static_img` output matches exactly,
     with and without caption / class.
   - One test per rejection in step 2, including a value with an inner `\` and
     one ending in `\`.
   - `render_static_img` raises `ValueError` on a hand-built `Marker` whose
     alt ends in `\`.
   - An apostrophe in alt is accepted.
   - Spec-owner reader, in two fixture tables:
     - **ACCEPTED** (line → expected value): a fixture spec copied verbatim
       from the parent design's example (the `output:` line with its trailing
       `# required; …` comment); `id: board_child_tasks`;
       `output: home/board.svg`; `output: "a b.svg"`; `output: 'a#b.svg'`;
       `id: "123"`; `id: "on"`; `id: 'null'`; a quoted value followed by
       ` # c`; a trailing space.
     - **REJECTED** (line → expected problem kind, plus a **reason class**
       that says what PyYAML does with the line):
       - class `typed` (problem "quote it"): `id: on`, `id: off`, `id: yes`,
         `id: True`, `id: null`, `id: 123`, `output: 1.0`, `output: .inf`,
         `id: 2026-11-15`, `id: 1_000`, `id: 0x1F`.
       - class `truncation` (unsupported scalar): `output: a.svg#x`. PyYAML
         loads `a.svg#x`, while a looser pattern would have read `a.svg`.
       - class `tab` (unsupported scalar): `output:\ta.svg`, `output: a.svg\t`,
         `output: "a.svg"\t# c`.
       - class `structural` (unsupported scalar, or missing / duplicated):
         `output: "a\"b.svg"`, `output: |`, `output: [a.svg]`, an empty
         `output:`, `output: a.svg extra`, `output: "a.svg"#c` (the
         conservative glued-comment case), and missing and duplicated keys.
     - **Agreement with PyYAML.** When PyYAML is importable (the test skips
       otherwise, with an `importlib.util.find_spec("yaml")` gate that does
       not use `markers.py`), every ACCEPTED line must satisfy
       `yaml.safe_load(line)[key] == reader value`, with both values `str`.
       REJECTED rows are checked by class, which pins why each rejection is
       justified. `typed`: the YAML value's type is not `str`. `truncation`:
       the YAML value equals the full token (`a.svg#x`). `tab`:
       `yaml.safe_load` raises. `structural`: no YAML assertion, since these
       are deliberately conservative. A `typed` / `truncation` / `tab` row
       that stops showing its disagreement fails the test.
   - Each check class gets a failing and a passing fixture, including the exit
     codes (`--strict` turns unresolved into exit 1, and a missing scene is a
     warning with exit 0).
   - `--owners` maps an image to its scene with zero markers present.
   - A missing `static-img` / `split-hero` / `tour-tile` source fails.
   - Scanner edges: a marker inside a fenced block is ignored; a multi-line
     screenshot comment is unparseable; an inline-code `<!--` that never
     closes on its line does not swallow a later valid marker; an inline
     screenshot comment is unparseable.
   - `--report` exits 0 even when a check fails.

5. **Scene, file and prose table** (alt is a noun phrase with no full stop;
   caption is one sentence ending in one). Before writing the board and monitor
   layout prose, confirm the numbered-list item names on those pages.

   | Marker (under `website/content/docs/`) | scene | file | alt | caption |
   |---|---|---|---|---|
   | `tuis/_index.md`, `tuis/board/how-to.md` (switcher), `tuis/settings/how-to.md`, `tuis/codebrowser/how-to.md` | `tui_switcher_dialog` | `aitasks_tui_switcher_dialog.svg` | TUI switcher dialog listing the integrated TUIs and their shortcut keys | The TUI switcher, opened with j from any main TUI. |
   | `tuis/monitor/_index.md` (switcher), `tuis/monitor/how-to.md` | `tui_switcher_from_monitor` | `aitasks_tui_switcher_from_monitor.svg` | TUI switcher dialog opened from monitor | The TUI switcher opened from monitor, where Shift+M is not offered. |
   | `tuis/minimonitor/how-to.md` | `tui_switcher_from_minimonitor` | `aitasks_tui_switcher_from_minimonitor.svg` | TUI switcher dialog in the narrow minimonitor layout | The TUI switcher opened from minimonitor, in its narrow layout. |
   | `tuis/board/_index.md` (layout) | `board_layout_annotated` | `aitasks_board_layout_annotated.svg` | Board with numbered callouts on the header, search box, board area and footer | The parts of the board layout, numbered as in the list above. |
   | `tuis/board/_index.md` (card) | `board_card_annotated` | `aitasks_board_card_annotated.svg` | A single task card with callouts on each of its fields | The parts of a task card. |
   | `tuis/board/how-to.md` (children) | `board_child_tasks` | `aitasks_board_child_tasks.svg` | Board with a parent task expanded to show its child tasks | An expanded parent task with its child tasks joined by connector lines. |
   | `tuis/board/how-to.md` (lock) | `board_task_detail_lock` | `aitasks_board_task_detail_lock.svg` | Task detail dialog showing the lock status and the Lock and Unlock buttons | The lock status and the Lock and Unlock buttons in the task detail dialog. |
   | `tuis/monitor/_index.md` (layout) | `monitor_layout_annotated` | `aitasks_monitor_layout_annotated.svg` | Monitor with numbered callouts on the header, session bar, pane list, preview and shadow columns, and footer | The parts of the monitor layout, numbered as in the list above. |
   | `tuis/brainstorm/_index.md` | `brainstorm_browse_tab` | `aitasks_brainstorm_browse_tab.svg` | Brainstorm Browse tab with the graph of proposal nodes and the detail pane on the right | The Browse tab, with the proposal graph on the left and the selected node's details on the right. |
   | `tuis/trails/_index.md` | `trails_main_view` | `aitasks_trails_main_view.svg` | Trails showing one trail's waves as columns with the summary pane below | One trail with its waves as columns and its summary below. |
   | `installation/terminal-setup.md` | `ait_ide_startup` | `aitasks_ait_ide_startup.svg` | Monitor dashboard in the tmux session started by ait ide | The monitor window right after running ait ide. |
   | `tuis/minimonitor/_index.md` | `minimonitor_main_view` | `aitasks_minimonitor_main_view.svg` | Minimonitor in a right-side split beside a code agent pane | Minimonitor running beside a code agent in the same tmux window. |
   | `tuis/sitrep/_index.md` | `sitrep_window` | `aitasks_sitrep_tui_main_view.svg` | Sitrep window with the sitrep agent above, the sitrep TUI list below and minimonitor on the right | The sitrep window, with the agent above, the sitrep TUI below and minimonitor on the right. |

   That gives 17 markers over 13 scenes. Two of the alts and captions contain
   an apostrophe ("trail's", "node's"), so step 7 covers that case on real
   content.

6. **Migrate the 17 markers.** Replace each comment line in place with the
   grammar form, one line per marker. Nothing else on any page changes
   (`git diff --stat` should show exactly one changed line per marker).

7. **Hugo rendering fixture (an automated test,
   `tests/test_check_screenshots_hugo.py`).** It skips when `hugo` is not on
   PATH, using `shutil.which`, which is independent of the code under test.
   It builds a **minimal scratch Hugo site** in a `TemporaryDirectory`:
   `hugo.toml` with `markup.goldmark.renderer.unsafe = true`, a one-line
   `layouts/_default/single.html` (`{{ .Content }}`), and the real
   `website/layouts/shortcodes/static-img.html`, copied at test time so the
   test tracks the shipped template. No Docsy or npm is needed, so the build
   takes seconds.
   - **Accepted corpus:** for each value in a list of values `parse_marker`
     accepts, the test writes the `render_static_img` output to a page. The
     list covers: an apostrophe; `&`; `<` and `>`; `}}` and `>}}`; `#`; `—`
     and non-ASCII text; a trailing `.`; a single `-`. The site must build
     with exit 0, and `html.parser` must decode each built `<img alt>` and
     `<figcaption>` to exactly the original value. The test also asserts the
     `onclick` attribute holds the alt in JS-escaped form, so a `'` cannot
     end the JS string.
   - **Control:** the same site with a raw shortcode whose alt ends in `\`
     must fail to build or render a different alt. This proves the fixture
     can detect the breakage and documents why `\` is forbidden. The test
     also asserts that `parse_marker` rejects that value.
   - Record the Hugo version used in the plan notes. If any value in the
     corpus fails, add its sequence to `FORBIDDEN_IN_VALUE` along with its
     tests and docs, and reword any affected alt in the table.

8. **CI.** In `.github/workflows/hugo.yml`, add a step "Check screenshot
   markers" running `python3 check_screenshots.py` (with
   `working-directory: website`) after "Check internal links". Give it a short
   comment block in the same style as that step.

9. **Docs.**
   - `website/README.md`: add a "Screenshot Markers" section after "Checking
     Link *Relevance*", covering the grammar with one example, the key table,
     the rules (scene charset, `file` relative to `static/imgs/`, no `"`,
     `--` or `\` in a value, with the one-line reason for each, and the spec's
     `output:` owns the file). Spec `id:` / `output:` lines may be plain or
     quoted scalars, separated by spaces, with an optional trailing comment;
     quote a value such as `on`, `null` or `123` that YAML would load as
     something other than a string. Also cover how to run the check and its
     flags.
   - `aitasks/metadata/doc_update_guide.md`: add a short "Screenshot
     placeholders" rule under "Writing conventions" telling authors to leave a
     marker in this grammar (pointing to `website/README.md`) rather than a
     free-form TODO comment.
   - Follow the current-state-only rule.

10. **Plan notes and sibling notes.** At the end, record in "Final
    Implementation Notes": the final scene/file table, the Hugo fixture result
    and version, the constant `MISSING_SCENE_SEVERITY` that child 5 flips, the
    scanner's lexical rules, `FORBIDDEN_IN_VALUE`, and the spec-owner contract
    (`SPEC_SCALAR_RE`, trailing comments allowed, unsupported forms named).
    Then send `ait note`s via the `/aitask-note` skill, because their plans
    reference this contract:
    - **t2278_2:** its loader agreement check should import
      `markers.SPEC_SCALAR_RE` / `read_spec_owner`. Trailing `# comments`
      (after a space) on `id:` / `output:` are valid. Separators are spaces
      only. A bare value that YAML would load as non-string must be quoted.
      The loader should reject any spec where `read_spec_owner` reports a
      problem, so the checker and the loader cannot accept different sets.
      Its agreement fixture should include the parent's commented `output:`
      example.
    - **t2278_5:** `render_static_img` raises `ValueError` on a forbidden
      value. `apply` should report that as `REFUSED:<scene>|<reason>`, not
      crash.

## Verification

- `python3 -m pytest tests/test_check_screenshots.py tests/test_check_screenshots_hugo.py -q`
  (the Hugo module must actually run here, not skip; confirm in the output),
  then `bash tests/run_all_python_tests.sh --test-dir tests`.
  Read only the last line for the verdict.
- `python3 website/check_screenshots.py` should report 17 markers,
  0 unparseable, 17 `NO_SCENE` warnings, 0 ownership, 0 missing-image,
  `SCREENSHOTS: PASSED` and exit 0. `--strict` should exit 1.
  `--owners` should list the 23 image files under `static/imgs/` (17
  top-level plus 6 in `home/`), all `hand-made`.
- Negative control: running it against the pre-migration content
  (`git stash` is forbidden, so use a scratch copy made with
  `git show HEAD:<page>`) should show 17 unparseable and exit 1.
- `cd website && python3 check_links.py --build` passes.
- `cd website && hugo build --gc --minify --destination <scratch>` succeeds.
  Compare its HTML with a build of HEAD in a second scratch destination: the
  only differences should be the comment text.

Post-implementation: Step 9 of the task workflow (review, commit, archival).

## Risk

### Code-health risk: low
- The new CI step can fail the deploy if the scanner misreads real content
  (an inline-code `<!--`, a fenced example) · severity: low · → mitigation:
  none, because step 2 follows CommonMark's rules for block comments and fences,
  step 4 tests each edge, and verification runs the check on the real content
  before the CI step lands
- `read_spec_owner` reads specs line by line, so it could disagree with child
  2's YAML loader · severity: low · → mitigation: none, because step 2 limits
  the reader to scalars that PyYAML parses identically (trailing comments
  included), step 4 checks that agreement against `yaml.safe_load` on the
  parent's own example, and step 10 notes t2278_2 to import the same pattern

### Goal-achievement risk: low
- A value the grammar accepts might still produce a broken shortcode or
  `onclick` string once `apply` renders it (an apostrophe, `}}`, or a
  backslash, which is now forbidden) · severity: low · → mitigation: none,
  because step 2 forbids `\`, `render_static_img` refuses forbidden values, and
  step 7 builds the accepted corpus through the real template with a
  trailing-backslash control. The fixture runs on local Hugo, while CI pins
  0.155.3, and the backslash rejection does not depend on the version
- The scene and filename choices may need renaming when child 2 builds the
  scenes · severity: low · → mitigation: none, because markers are comments
  and renaming one is a one-line edit that the check validates

## Post-Review Changes

### Change Request 1 (2026-11-15 19:40)
- **Requested by user:** four review findings: (1) `scan_image_sources` cut a
  shortcode at a `>}}` inside a quoted value and ignored bare / backtick values;
  (2) a backtick fence whose info string contains a backtick was treated as a
  fence, hiding the marker after it; (3) ownership and `--owners` compared raw
  `output:` strings, so `./x.svg` and `x.svg` slipped past both; (4) the README
  claimed capture/replace tooling that does not exist yet.
- **Changes made:** (1) replaced the regex with a tokenizer `_parse_shortcode`
  that follows Hugo's argument lexer (probed on Hugo 0.169): `"…"` with `\"`,
  `` `…` `` raw, bare tokens, spaces around `=`, close delimiters inside quotes
  ignored, non-image shortcodes skipped whole, `{{</* */>}}` skipped; (2) a
  backtick fence opener with a backtick in its info string is not a fence (tilde
  fences may contain one); (3) `path_problem()` requires a canonical path (no
  leading `/` or `./`, no empty / `.` / `..` segment) for marker `file=` and spec
  `output:`; a non-canonical `output:` is an `OWNERSHIP` problem and is never
  compared; (4) README describes only the marker and the checker.
  Differential Hugo tests were added for (1) and (2).
- **Files affected:** `website/screenshots/markers.py`, `website/README.md`,
  `tests/test_check_screenshots.py`, `tests/test_check_screenshots_hugo.py`.

### Change Request 2 (2026-11-15 19:55)
- **Requested by user:** `path_problem` accepted `#` / `?` in filenames; the
  template emits them verbatim, so the browser requests `/imgs/a`, while the
  checker validated the literal filesystem name.
- **Changes made:** `PATH_SEGMENT_RE = ^[A-Za-z0-9._-]+$` per segment (RFC 3986
  unreserved minus `~`), so the filesystem name, the URL and the requested path
  are one string. `check_screenshots.request_path()` checks an image `src` at the
  path a browser requests (`urlsplit(...).path`, percent-decoded). Added
  marker → Hugo → request-path fixtures and a `#`/`?` control.
- **Files affected:** `website/screenshots/markers.py`,
  `website/check_screenshots.py`, `website/README.md`, both test modules.

## Final Implementation Notes
- **Actual work done:** `website/screenshots/__init__.py`, `website/screenshots/markers.py`
  (grammar, scanner, `render_static_img`, image-source tokenizer, canonical-path
  rule, spec-owner reader), `website/check_screenshots.py` (classes UNPARSEABLE,
  NO_SCENE, OWNERSHIP, MISSING_IMAGE, UNRESOLVED; `--report`, `--strict`,
  `--owners`, `--content/--static/--scenes`), `tests/test_check_screenshots.py`
  (unit, scratch trees) and `tests/test_check_screenshots_hugo.py` (minimal
  scratch Hugo site with the real `static-img.html`; skips without `hugo`).
  17 markers migrated in 13 pages (one line each). CI step "Check screenshot
  markers" after "Check internal links" in `.github/workflows/hugo.yml`.
  `website/README.md` § "Screenshot Markers"; one bullet in
  `aitasks/metadata/doc_update_guide.md` § "Writing conventions".
- **Deviations from plan:** board layout alt says "filter area" (the page's own
  list item 2) instead of "search box". The minimonitor switcher got its own
  scene, as the verified plan already decided. The four review rounds above
  tightened the tokenizer, fence, path and request-path rules.
- **Issues encountered:** a HEAD-vs-new full-site HTML comparison first showed
  261 differing files; they came from `enableGitInfo` (scratch content dir has
  no git history) and from Docsy edit links embedding the content dir path.
  With `--enableGitInfo=false` and the dir name normalized, all 376 files are
  byte-identical (the minifier strips comments anyway).
  Full Python suite: 9 failures, none in this change — 1 in
  `test_metadata_writer_inventory` caused by a concurrent session's untracked
  `.aitask-scripts/lib/sitrep_crash.py`, 8 in `test_screen_recording_cli` /
  `test_aitask_questions` (fail the same way in isolation; they do not import
  anything under `website/`).
- **Key decisions:** reject rather than escape: `FORBIDDEN_IN_VALUE = ('"', "--", "\\")`
  so every accepted value goes into a shortcode verbatim, independent of the
  Hugo version. Hugo result (local 0.169.0; CI's pinned 0.155.3 not checked):
  apostrophe, `&`, `<`, `>`, `}}`, `>}}`, `#`, non-ASCII, `.`, `-` all round-trip
  through alt / figcaption / onclick (`'` becomes `'`); a raw trailing
  backslash makes the build exit 1. Mutants for every rule were run and each
  fails the suite.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **Scene/file table (final):** `tui_switcher_dialog` → `aitasks_tui_switcher_dialog.svg`
    (tuis/_index, board/how-to, settings/how-to, codebrowser/how-to);
    `tui_switcher_from_monitor` → `aitasks_tui_switcher_from_monitor.svg`
    (monitor/_index, monitor/how-to); `tui_switcher_from_minimonitor` →
    `aitasks_tui_switcher_from_minimonitor.svg` (minimonitor/how-to; narrow
    layout, `_switcher_narrow()`); `board_layout_annotated`,
    `board_card_annotated`, `board_child_tasks`, `board_task_detail_lock`,
    `monitor_layout_annotated`, `brainstorm_browse_tab`, `trails_main_view`,
    `ait_ide_startup`, `minimonitor_main_view` → `aitasks_<scene>.svg`;
    `sitrep_window` → `aitasks_sitrep_tui_main_view.svg`. 17 markers, 13 scenes.
  - **t2278_5:** flip `check_screenshots.MISSING_SCENE_SEVERITY` to `"error"`.
    `markers.render_static_img` raises `ValueError` on a forbidden value or
    (via `parse_marker`) never sees a non-canonical path — `apply` should report
    `REFUSED:<scene>|<reason>`, not crash.
  - **t2278_2 (scene loader contract):** import `markers.SPEC_SCALAR_RE`,
    `read_spec_scalar`, `read_spec_owner` and `path_problem`; reject any spec
    for which `read_spec_owner(...).problems` is non-empty. Contract: an accepted
    `id:`/`output:` value equals `yaml.safe_load(line)[key]` as `str`; spaces only
    (tabs make PyYAML raise); a trailing `# comment` needs a space before `#`;
    bare values must start with a letter and not be a YAML bool/null word
    (quote `on`, `null`, `123`, dates); `output:` must be canonical and URL-safe.
    The parent design's commented `output:` example reads correctly.
  - **Scanner rules:** fenced blocks skipped (backtick info strings with a
    backtick are not fences); block comment = line starting `<!--` (≤3 spaces)
    up to the first `-->`; a screenshot comment must be one line; any other line
    with `<!--` and `screenshot` is an inline-comment error. Verified against
    Goldmark by `test_fence_rules_match_goldmark`.
