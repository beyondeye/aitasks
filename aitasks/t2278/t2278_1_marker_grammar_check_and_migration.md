---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Implementing
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:18
---

## Context

Child 1 of t2278 (docs TUI screenshot generator). The full design is in the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`; read its
"Marker grammar" and "`check_screenshots.py`" sections first.

The website has 17 screenshot placeholders in four inconsistent HTML-comment
shapes, six of which name no file. This child defines the one marker grammar,
ships a stdlib-only checker, and migrates all 17 placeholders to the grammar.
The edits are comments only, so no page changes visibly. Later children add
the scene specs and capture backends that the markers point at.

The tool is repo-only: everything lives under `website/`, nothing under
`.aitask-scripts/`, no `ait` verb, no allowlist entries.

## Marker grammar

One single-line HTML comment, key=value, double-quoted values:

    <!-- screenshot: scene=board_child_tasks file=aitasks_board_child_tasks.svg alt="Board with a parent task expanded to show its child tasks" caption="An expanded parent task with its child tasks." -->

- Required keys: `scene`, `file`, `alt`. Optional: `caption`, `class`.
- `scene` matches `[a-z0-9_]+` and names `website/screenshots/scenes/<scene>.yaml`.
- `file` is a path relative to `website/static/imgs/`.
- A value may not contain `"` or `--`. Apostrophes are allowed.
- The scene spec owns the output file through its required `output:` field.
  A marker's `file=` is a readable copy that must equal its scene's `output:`.
  No two specs may share an `output:`. Several markers may share one scene.

## Current markers (re-grep before relying on line numbers)

Paths relative to `website/content/docs/`:

- TUI switcher dialog, 7 markers, all naming `aitasks_tui_switcher_dialog.svg`:
  `tuis/_index.md:37`, `tuis/board/how-to.md:504`, `tuis/settings/how-to.md:205`,
  `tuis/codebrowser/how-to.md:211` (generic); `tuis/monitor/_index.md:86`,
  `tuis/monitor/how-to.md:147` (as shown from monitor, where Shift+M is not
  offered); `tuis/minimonitor/how-to.md:407` (as shown from minimonitor).
- Annotated layouts: `tuis/board/_index.md:39`, `tuis/monitor/_index.md:48`.
- Board details: `tuis/board/_index.md:65` (annotated card close-up),
  `tuis/board/how-to.md:331` (expanded parent with children),
  `tuis/board/how-to.md:408` (task detail dialog with lock buttons).
- Single-TUI main views: `tuis/brainstorm/_index.md:14`, `tuis/trails/_index.md:12`.
- tmux composites: `installation/terminal-setup.md:41` (`ait ide` startup),
  `tuis/minimonitor/_index.md:14`, `tuis/sitrep/_index.md:12`.

## Key Files to Modify

- `website/screenshots/__init__.py`, `website/screenshots/markers.py` (new,
  stdlib only): parse one marker, scan `website/content/` for markers and for
  non-parsing comments that mention `screenshot`, render the `static-img`
  shortcode text for a marker.
- `website/check_screenshots.py` (new, stdlib only): the six report classes in
  the parent plan, plus `--report`, `--strict`, `--owners`.
- `tests/test_check_screenshots.py` (new).
- The 13 doc pages above: rewrite each marker to the grammar.
- `.github/workflows/hugo.yml`: run the check after the link check.
- `website/README.md` and `aitasks/metadata/doc_update_guide.md`: document the
  grammar for doc authors.
- `website/screenshots/scenes/.gitkeep` so the scenes directory exists.

## Reference Files for Patterns

- `website/check_links.py`: CLI shape, `--report`, record output, exit codes.
- `tests/test_check_link_relevance.py`: how a test imports a `website/` module
  (`sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "website"))`).
- `website/layouts/shortcodes/static-img.html`: params `src`, `alt`, `caption`,
  `class`; `src` has no leading slash (`imgs/...`); `alt` is placed inside a JS
  string in `onclick`.
- Existing alt/caption wording: `website/content/docs/tuis/board/_index.md:12`,
  `website/content/docs/tuis/settings/_index.md:24`.

## Implementation Plan

See `aiplans/p2278/p2278_1_marker_grammar_check_and_migration.md`.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes with the new test
  module (read only the last line for the verdict).
- `python3 website/check_screenshots.py` lists 17 unresolved markers, reports
  no unparseable comment, and exits 0.
- `cd website && python3 check_links.py --build` passes.
- `cd website && hugo build --gc --minify` succeeds and the built pages show no
  visible change (markers are comments).
