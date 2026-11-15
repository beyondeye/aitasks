---
Task: t2278_1_marker_grammar_check_and_migration.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_1 — marker grammar, check and marker migration

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` ("Marker
grammar", "`check_screenshots.py`"). Everything here is stdlib-only Python.

## Steps

1. **Gate on in-flight pages.** Run `git status --short -- website/`. If any
   page that carries a marker is modified or untracked, stop and report which
   task owns it. Re-grep the markers
   (`grep -rn -i 'screenshot' website/content --include='*.md' | grep '<!--'`)
   and confirm the count is still 17.

2. **`website/screenshots/markers.py`.**
   - `MARKER_RE`: a whole-line match of `<!-- screenshot: <pairs> -->`.
   - `parse_marker(text) -> Marker | ParseError`. Pairs are `key=value`; a value
     is a bare token (`[A-Za-z0-9_./-]+`) or a double-quoted string. Reject:
     unknown keys, duplicate keys, a missing required key (`scene`, `file`,
     `alt`), `scene` not matching `[a-z0-9_]+`, `file` that is absolute or has
     a `..` segment, and a value containing `"` or `--`.
   - `scan(content_root) -> (markers, unparseable)`. `unparseable` is every HTML
     comment whose text contains `screenshot` (case-insensitive) and does not
     parse. Each record carries the page path, line number and exact text.
     Multi-line comments that do not mention `screenshot` are ignored
     (`website/content/docs/tuis/board/reference.md:299` is one).
   - `render_static_img(marker) -> str`: `{{< static-img src="imgs/<file>"
     alt="..." caption="..." >}}`, omitting `caption` / `class` when absent.
   - `read_spec_owner(path) -> (id, output)`: reads the `id:` and `output:`
     lines of a scene spec with a line pattern (no PyYAML).

3. **`website/check_screenshots.py`.** Classes, each a record with file and
   line:
   1. unparseable screenshot comment — fails;
   2. marker whose scene has no `scenes/<scene>.yaml` — **listed as a warning
      in this child** (no scene exists yet); child 5 promotes it to a failure.
      Put the severity in one named constant so that change is one line;
   3. ownership: marker `file=` differs from its scene's `output:`, two specs
      share an `output:`, a spec lacks `output:` or its `id:` differs from the
      file stem — fails;
   4. a `static-img`, `split-hero` (`image=`) or `tour-tile` (`src=`) source
      with no file under `website/static/` — fails;
   5. unresolved markers — listed, exit 0 unless `--strict`;
   6. `--owners`: every file under `website/static/imgs/` with its owning scene,
      or `hand-made`.
   Flags: `--report` (print, exit 0), `--strict`, `--owners`, `--content PATH`,
   `--static PATH`, `--scenes PATH` (the last three exist for tests).

4. **Tests, `tests/test_check_screenshots.py`.** Build a scratch tree per test
   (content, static, scenes). Cover: each of the four legacy shapes is reported
   unparseable; a valid marker parses and round-trips through
   `render_static_img`; each rejection in step 2; each check class has one
   failing and one passing fixture; `--owners` with zero markers still maps an
   image to its scene; a missing `static-img` source fails; an alt with an
   apostrophe is accepted.

5. **Assign scenes, filenames and prose.** Proposed table (adjust wording
   against the page context; alt is a noun phrase without a full stop, caption
   is one sentence with one):

   | Marker location | scene | file |
   |---|---|---|
   | `tuis/_index.md`, `board/how-to.md` (switcher), `settings/how-to.md`, `codebrowser/how-to.md` | `tui_switcher_dialog` | `aitasks_tui_switcher_dialog.svg` |
   | `monitor/_index.md` (switcher), `monitor/how-to.md` | `tui_switcher_from_monitor` | `aitasks_tui_switcher_from_monitor.svg` |
   | `minimonitor/how-to.md` | `tui_switcher_dialog` unless its hint row differs; note the open point for child 2 | as its scene |
   | `board/_index.md` (layout) | `board_layout_annotated` | `aitasks_board_layout_annotated.svg` |
   | `board/_index.md` (card) | `board_card_annotated` | `aitasks_board_card_annotated.svg` |
   | `board/how-to.md` (children) | `board_child_tasks` | `aitasks_board_child_tasks.svg` |
   | `board/how-to.md` (lock) | `board_task_detail_lock` | `aitasks_board_task_detail_lock.svg` |
   | `monitor/_index.md` (layout) | `monitor_layout_annotated` | `aitasks_monitor_layout_annotated.svg` |
   | `brainstorm/_index.md` | `brainstorm_browse_tab` | `aitasks_brainstorm_browse_tab.svg` |
   | `trails/_index.md` | `trails_main_view` | `aitasks_trails_main_view.svg` |
   | `installation/terminal-setup.md` | `ait_ide_startup` | `aitasks_ait_ide_startup.svg` |
   | `minimonitor/_index.md` | `minimonitor_main_view` | `aitasks_minimonitor_main_view.svg` |
   | `sitrep/_index.md` | `sitrep_window` | `aitasks_sitrep_tui_main_view.svg` |

   Write the proposed alt and caption for every marker into the plan's notes
   and show the table to the user before editing pages.

6. **Migrate the 17 markers.** Replace each comment in place with the grammar
   form. One comment per line, nothing else on the page changes.

7. **Hugo check of the shortcode with an apostrophe.** In a scratch copy of the
   site (never in `website/content/`), render a `static-img` whose alt contains
   an apostrophe and confirm the built `onclick` attribute is valid. Record the
   result; if it breaks, add the apostrophe to the forbidden set and say so in
   the docs.

8. **CI.** In `.github/workflows/hugo.yml`, add
   `python3 check_screenshots.py` after the `check_links.py` step.

9. **Docs.** `website/README.md`: a "Screenshots" section with the grammar, the
   key table, and how to run the check. `aitasks/metadata/doc_update_guide.md`:
   a short rule telling doc authors to leave a marker in this grammar where a
   screenshot belongs. Follow `aidocs/framework/documentation_conventions.md`.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` (last line is the verdict).
- `python3 website/check_screenshots.py`: 17 unresolved, 0 unparseable, exit 0.
- `cd website && python3 check_links.py --build`.
- `cd website && hugo build --gc --minify`.

## Notes for sibling tasks

Record here, at the end of implementation: the final scene/file table, the
apostrophe result, and the name of the severity constant child 5 must flip.

Post-implementation: Step 9 of the task workflow (review, commit, archival).
