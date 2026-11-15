---
Task: t2278_docs_tui_screenshot_generator.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t2278 — docs TUI screenshot generator (parent, split into children)

## Context

The website has 17 screenshot placeholders in four inconsistent comment shapes
(six name no file) and 18 hand-captured Rich SVGs that do not share one look
(two themes, four terminal sizes). No generator exists. t2278 adds a tool that
resolves each placeholder to a declarative scene, boots the TUI (or a tmux
composite) on a synthetic fixture, captures it as SVG, optionally crops and
annotates it, and rewrites the placeholder into `{{< static-img >}}` after the
user has reviewed the images.

Decisions taken with the user during planning:

- **Repo-only tool** under `website/screenshots/`, never shipped. A static,
  Claude-only skill drives it. Every `.claude/skills/` directory ships (the
  release glob is pinned by `tests/test_release_tarball.sh`), so the skill's
  first step stops when `website/screenshots/` is absent.
- **Regenerate the 18 existing images** in a later child, so the site ends up
  with one pinned look.
- **Backend C (real pixels) stays in scope** as the last, optional child.
- **Split into child tasks.** This parent implements nothing itself.

Facts from exploration that shape the design:

- Marker count is 17; the TUI-switcher dialog appears **7** times (not 6) under
  one filename, and the from-monitor variant visibly differs (no Shift+M).
- `git status -- website/` is clean today, so the in-flight-edit hazard in the
  task body does not currently apply. Each child that edits pages re-checks.
- `website/check_links.py` only reads `<a href>`; a missing `imgs/...` file
  builds green in Hugo and passes the link check.
- `App.export_screenshot()` passes no `unique_id`, theme or chrome control to
  Rich. Rich's `unique_id` is a content hash, so identical frames are
  byte-identical, but any clock, date or temp path on screen changes the file.
- No test writes an SVG today; all four `export_screenshot()` callers strip it
  to text.
- `tests/test_no_raw_tmux.sh` scans only `.aitask-scripts/`. A tool under
  `website/` may build raw tmux argv, as the tests do.
- Monitor and minimonitor refuse to mount without `$TMUX`; tests pop `TMUX` and
  inject fake snapshots after mount (`tests/test_monitor_focus_switch.py`,
  `tests/test_minimonitor_scroll_preservation.py`).
- Doc guide rule: on-screen example names must be invented, never the real
  repo names. Fixtures must use an invented project name.

## Design

### Layout (all new, all under `website/`, nothing in `.aitask-scripts/`)

```
website/check_screenshots.py        # stdlib only; marker + image-src check
website/screenshots.sh              # launcher: sources .aitask-scripts/lib/python_resolve.sh, require_ait_python
website/screenshots/
  markers.py                        # stdlib only; the one marker grammar (parse, scan, render static-img)
  scene.py                          # YAML scene loader + validator (PyYAML, venv)
  registry.py                       # fixed tables: app adapters, fixture builders, pinned look
  cli.py                            # list | capture | preview | apply
  svgpost.py                        # crop (viewBox rewrite) + overlays, cell-rect based
  backends/textual_backend.py       # backend A
  backends/tmux_backend.py          # backend B
  backends/pixel_backend.py         # backend C (optional)
  scenes/<scene_id>.yaml            # one file per scene
```

The tool needs Textual, Rich and PyYAML, so it runs on the framework venv
(`require_ait_python`), unlike the other website scripts. `markers.py` and
`check_screenshots.py` stay stdlib-only so the check can run in the Hugo CI job.

### Marker grammar (one shape)

A single-line HTML comment, key=value with double-quoted values:

```
<!-- screenshot: scene=board_child_tasks file=aitasks_board_child_tasks.svg alt="Board with a parent task expanded to show its child tasks" caption="An expanded parent task with its child tasks." -->
```

- Required keys: `scene`, `file`, `alt`. Optional: `caption`, `class`.
- `scene` matches `[a-z0-9_]+` and names `scenes/<scene>.yaml`. `file` is a
  path relative to `website/static/imgs/` (so `home/board.svg` is legal).
- Values may not contain `"` or `--` (the second would end the comment). The
  checker reports both. Apostrophes are allowed; child 1 tests one through the
  shortcode's `onclick` string in a real Hugo build.
- **The scene spec owns the output file.** Every spec carries a required
  `output:` field (path relative to `website/static/imgs/`), and that field is
  the only durable scene-to-file mapping: it survives after `apply` has removed
  every marker. A marker's `file=` is a readable copy that must equal its
  scene's `output:`; the checker fails on a mismatch. No two specs may name the
  same `output:`. Several markers may share a scene with different alt/caption
  text.
- `capture`, `apply` and the regeneration child read the target filename from
  the spec only, never from a marker or a page.
- Fixed tables (app adapters, fixture builders, pinned look) live in
  `registry.py`; YAML holds scene data only (framework constants rule).

### `check_screenshots.py`

Reports, with file and line:

1. comments that mention `screenshot` but do not parse (this is what catches the
   three legacy shapes) — **fails**;
2. markers whose scene has no spec file — **fails**;
3. ownership violations — a marker whose `file=` differs from its scene's
   `output:`, two specs with the same `output:`, or a spec without one —
   **fails**;
4. `static-img` (and `split-hero`, `tour-tile`) sources with no file under
   `website/static/` — **fails**; this closes the gap `check_links.py` leaves;
5. markers still unresolved (valid placeholders) — **listed, exit 0** unless
   `--strict`;
6. the ownership table, on `--owners`: every image under
   `website/static/imgs/` with the scene whose `output:` names it, or
   `hand-made` when no spec does. This works with zero markers left in the
   docs, and is how child 6 tracks which of the 18 existing images are covered.

The spec-reading checks (2, 3, 6) need only the `id:` and `output:` lines, which
the stdlib checker reads with a line pattern so it does not need PyYAML;
`scene.py` rejects a spec whose `id:` / `output:` are not plain single-line
scalars, so the two readers cannot disagree.

`--report` prints records and exits 0, matching `check_links.py`.

### Scene spec

```yaml
id: board_child_tasks
output: aitasks_board_child_tasks.svg   # required; relative to website/static/imgs/
backend: textual            # textual | tmux | pixels
app: board                  # key into registry.APPS
fixture: {name: board_rich, params: {}}
size: [160, 48]
steps:
  - press: [x]
  - wait_for: {text: "t9000_1"}      # settle = text or selector present, never a sleep
settle: {selector: "TaskCard.-child"}
crop: {selector: "#board"}            # or {cells: [x, y, w, h]}
overlays:
  - {type: box, target: {selector: "#header"}, callout: 1, label: "Header"}
  - {type: tint, target: {cells: [0, 3, 160, 2]}}
```

tmux scenes replace `app`/`steps` with a `layout` (window size, panes, each a
real TUI command or a stand-in such as `tests/lib/fake_composer_agent.py`, split
direction and size) and a per-pane settle text.

### Backends

- **A, Textual vector.** `registry.APPS[app]` is an adapter that builds the app
  on its fixture and applies the stubs the tests already use. It reuses
  `tests/lib/board_fixture.py` (`build_fixture_tree`, `load_board_module`,
  `make_trails_app`; relative `TASK_DIR` + cwd at the tree root) and the
  per-TUI patterns in `test_codebrowser_startup_focus.py`,
  `test_settings_shortcuts_tab.py`, `test_brainstorm_compare_overlay.py`,
  `test_sitrep_tui_app.py`, `test_tui_group_nav.py` (switcher overlay under
  patches), `test_monitor_focus_switch.py` (fake monitor). The backend runs
  `app.run_test(size=...)`, executes the steps with Pilot, waits on the settle
  condition with a bounded poll (timeout is a failure), drains workers
  (`app.workers.wait_for_complete()`), and exports with **its own copy of
  Textual's export lines** so it can pass a `unique_id` derived from the scene
  id, the pinned title and the pinned theme. While the app is still mounted it
  resolves every crop and overlay selector to a cell rectangle
  (`widget.region`) and hands those rectangles to `svgpost`.
- **B, tmux composite.** Every tmux call goes through the gateway:
  `TmuxClient(socket_args=["-L", "ait_shots_<pid>"])` from
  `.aitask-scripts/lib/tmux_exec.py`, never a hand-built `["tmux", ...]` argv.
  Being outside the `test_no_raw_tmux.sh` scan is not a reason to skip it: the
  client adds the mandatory `-u` flag and decodes output as UTF-8 with
  `surrogateescape` (`aidocs/framework/tmux_gateway.md` policy 5). Without
  them, a client with no UTF-8 locale gets `_` for every box-drawing character
  and glyph, which would silently corrupt a screenshot. **The user's tmux
  config is never loaded.** The call that starts the server is
  `client.run(["-f", "/dev/null", "new-session", "-d", ...])`:
  `TmuxClient._argv` prepends `tmux -u -L <socket>` to the caller's arguments,
  so this yields `tmux -u -L ait_shots_<pid> -f /dev/null new-session ...` with
  no gateway change. There is no post-start fallback: a loaded config can
  already have run `run-shell` commands, installed hooks or started plugins,
  and resetting options afterwards undoes none of that. The backend has one
  `start_server()` function, it is the only place a server can come into
  existence, and it asserts the socket has no server before it runs (so no
  earlier call on that socket can have started one without the flag).
  `AITASKS_TMUX_SOCKET` is pinned in the session environment, panes are
  launched with `env -u COLUMNS -u LINES`, and pane ids come from `-P -F`.
  Teardown is `kill-server` on that private socket only, registered before the
  first spawn.
  Geometry from `list-panes`, each pane via `capture-pane -e -p`, stitched with
  drawn borders through `Text.from_ansi` into a recording Rich `Console`, then
  `export_svg` with the same pinned id, title and theme as backend A. Pane
  rectangles feed `svgpost` the same way widget regions do. Layout precedent:
  `tests/test_sitrep_window_live.sh`, `tests/test_minimonitor_width_pin_live.py`.
- **C, real pixels (optional).** `hyprctl output create headless`, terminal with
  a pinned config on that output, `grim`, ImageMagick; cell rectangles map
  through window pixels / (cols × rows). Never the only path to a scene.

`svgpost` works on cell rectangles only, using the fixed Rich geometry
(char width 12.2, line height 24.4, content origin (9, 41)): a crop rewrites
the `viewBox` and drops the window chrome; overlays append `<rect>` / `<text>`
elements. Both stay vector.

### CLI and skill

`website/screenshots.sh list | capture [--scene ID | --pending | --all] |
preview | apply`:

- `capture` writes a **new batch directory** on every run
  (`website/screenshots/.staging/<batch-id>/`, gitignored) and never writes
  into an existing one, so a later capture cannot replace reviewed files. It
  prints `BATCH:<batch-id>`. The batch holds the images and one `manifest.json`
  with, per scene: the `output:` path, the staged image's SHA-256, the state of
  the destination file at capture time (absent, or its SHA-256), and for each
  marker of that scene the page path and the **exact marker text**.
- `preview --batch <id>` writes the HTML contact sheet from that batch only and
  shows the batch id, each image, and each marker's page, alt and caption.
- `apply --batch <id>` requires the batch id (no "latest" default) and
  validates before it writes. A scene is applied only when all of these hold:
  1. the staged image still hashes to the manifest value;
  2. the destination file is in the state the manifest recorded (still absent,
     or the same hash) — a file created or changed since is never overwritten;
  3. each of its markers is still present **byte-for-byte** in its page.
     Markers are located by text, never by line number.

  For a passing scene it copies the image to `output:` and, in each page,
  substitutes only the marker text with
  `{{< static-img src="imgs/<output>" alt="..." caption="..." >}}` in the page
  as it is on disk now, so every other edit made to that page during review is
  kept. A failing scene is left untouched — image and pages — and reported as
  `REFUSED:<scene>|<reason>`; `apply` exits non-zero when any scene was refused.
  A refused scene needs a new capture and a new review.

Skill `.claude/skills/aitask-docs-screenshots/SKILL.md` (static, Claude-only):
stop if `website/screenshots/` is absent → run the check → for each marker
without a scene spec, read the surrounding page text and write the spec →
`capture --pending` → `preview --batch <id>`, show the user → on approval
`apply --batch <id>` with the id the user reviewed → report any `REFUSED:`
scene → `python3 check_links.py --build` and `python3 check_screenshots.py`.
If anything is re-captured after the review, the new batch is reviewed again
before it is applied. It never commits.

## Child tasks

Created after this plan is approved (plan mode is read-only). Each child's task
file carries the full context, key files, reference files, steps and
verification per the Child Task Documentation Requirements; each gets a plan
under `aiplans/p2278/`. Children depend on earlier siblings in this order.

1. **`t2278_1` marker grammar, check and marker migration.**
   `markers.py`, `check_screenshots.py`, `tests/test_check_screenshots.py`
   (uses the `sys.path.insert(... "website")` pattern of
   `tests/test_check_link_relevance.py`). Assign a scene id, a filename and
   alt/caption text to all 17 markers and rewrite them to the grammar (comments
   only, no visible page change). The switcher gets two scenes with two
   filenames: `tui_switcher_dialog` and `tui_switcher_from_monitor`; the
   minimonitor marker points at whichever its hint row matches, decided at
   capture time. Re-run `git status -- website/` first and stop on any in-flight
   page. Wire the check into `.github/workflows/hugo.yml` after the link check.
   Document the grammar in `website/README.md` and
   `aitasks/metadata/doc_update_guide.md`. The check exits non-zero for missing
   scene specs until the scenes exist, so this child lands the check with
   class 2 demoted to a listed warning and child 5 promotes it to a failure.
2. **`t2278_2` scene specs, backend A and the CLI capture path.**
   `scene.py`, `registry.py` (board, trails, brainstorm, switcher adapters and
   the pinned look: one Textual theme, one Rich terminal theme, default sizes,
   invented project name), `backends/textual_backend.py`, `cli.py list|capture`,
   `screenshots.sh`. **First step is one scene end to end**
   (`board_child_tasks`) before the format is generalised. Scenes: the two
   switcher variants, board child tasks, board task-detail lock, trails main
   view, brainstorm browse tab. Tests: spec validation; a capture run twice is
   byte-identical; a settle timeout fails rather than writing an image.
3. **`t2278_3` crop and overlays.** `svgpost.py` plus region resolution in
   backend A; adapters for monitor (fake snapshots). Scenes: annotated board
   layout, annotated card close-up (crop + callouts), annotated monitor layout.
   Tests assert exact viewBox and overlay coordinates for a known widget region.
4. **`t2278_4` backend B, tmux composites.** `backends/tmux_backend.py`.
   **First step is one composite end to end** (minimonitor beside a stand-in
   agent pane); if the panes cannot be given realistic content through harness
   apps, stop and report before building the general layout engine. Scenes:
   `ait ide` startup, minimonitor main view, sitrep window. The capture test is
   skipped when `tmux` is absent, by a probe that does not run the backend.
   A second test runs the backend in a subprocess under
   `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` against a pane printing
   box-drawing characters and a non-ASCII word, and asserts they appear
   unchanged in the SVG; its control (the same capture with `-u` removed from
   the argv) must show the `_` substitution, so the test is known to detect the
   failure it guards. A third test points `HOME` and `XDG_CONFIG_HOME` at a
   scratch directory whose `tmux.conf` runs `run-shell 'touch <sentinel>'` and
   sets a visible status option, starts the backend's server, and asserts the
   sentinel file was never created.
5. **`t2278_5` skill, preview/apply and the autonomous pass.**
   `cli.py preview|apply` with the batch manifest. Tests for `apply`: a staged
   image changed after capture, a destination created after capture, a
   destination modified after capture, and a marker edited after capture are
   each refused with nothing written for that scene; an unrelated edit
   elsewhere in the same page survives a successful apply; two captures
   produce two batches. Also the skill, a repo-local permission entry in
   `.claude/settings.local.json` for `website/screenshots.sh` (not in `seed/`),
   skill page under `website/content/docs/development/skills/`, design note
   `aidocs/framework/docs_screenshots.md` with a CLAUDE.md pointer and a
   "Website" section line. Then run the pass on all 17 markers, review with the
   user, apply, run both checks, and promote the missing-spec class to a
   failure. Ends by suggesting port tasks for Codex and OpenCode.
6. **`t2278_6` regenerate the 18 existing images.** By this point no marker is
   left in the docs, so this child runs entirely on the specs' `output:`
   fields. Its first check is the proof that the mapping is durable: with zero
   markers, `capture --all` must stage every scene from children 2-4 under its
   original filename, and `check_screenshots.py --owners` must list each of
   those images with its scene. One scene per existing
   image (codebrowser and settings adapters are added here), same filenames, so
   no page edit is needed beyond the `aitasks_codebrowser_w_annotaitions`
   filename typo and the unreferenced
   `aitasks_settings_code_agent_default_models_tab.svg`, both listed for the
   user to decide. Old and new are shown side by side before anything is
   replaced.
7. **`t2278_7` backend C, real pixels (optional).** Starts with the live probe
   the task body names (does the Omarchy bar or a window rule attach to a
   headless output). Skippable without affecting any scene.
8. **`t2278_8` retrospective evaluation.** Depends on all others. Checks the
   scene format, the pinned look and the tests-fixture coupling against what the
   passes in children 5 and 6 actually needed.

After the child plans are committed, the workflow offers an aggregate
manual-verification sibling (the generated images are visual output), then the
child checkpoint.

## Verification

For this parent: all eight child task files and their plans exist and are
committed; `ait ls --children 2278` lists them in the order above; the parent is
back to `Ready` with its lock released.

End to end, once children 1-5 have landed:

- `python3 website/check_screenshots.py` exits 0 and lists no unresolved marker.
- `cd website && python3 check_links.py --build` passes.
- `bash tests/run_all_python_tests.sh --test-dir tests` shows the new
  `test_check_screenshots.py` and screenshot tests passing.
- `website/screenshots.sh capture --all` run twice produces two batches whose
  images are byte-identical.
- With every marker already replaced, `capture --all` still stages each scene
  under its `output:` filename and `check_screenshots.py --owners` attributes
  every generated image to its scene.
- Editing a marker between `capture` and `apply --batch` gets that scene
  refused and leaves the page and the image untouched.
- Every generated image is viewed on the local Hugo server (`./serve.sh`).

Post-implementation for each child follows Step 9 of the task workflow (review,
commit, archival); the parent is archived when the last child is.

## Risk

### Code-health risk: low
- The tool imports test-only fixtures (`tests/lib/board_fixture.py` and patterns
  copied from individual test modules), so a fixture refactor can break
  screenshot capture without failing any existing test · severity: low · →
  mitigation: none — child 2 adds a capture test per adapter, which fails on
  such a refactor
- Backend B starts and kills a tmux server · severity: low · → mitigation: none
  — it only ever addresses its own `-L ait_shots_<pid>` socket through
  `TmuxClient`, and teardown is registered before the first spawn
- `apply` edits doc pages and image files on a shared checkout · severity: low
  · → mitigation: none — it is bound to one reviewed batch, replaces marker
  text only, and refuses a changed image, destination or marker (child 5 tests
  each refusal)

### Goal-achievement risk: medium
- tmux composites of monitor, minimonitor and sitrep need realistic content in
  real panes; harness apps with stubbed data may not look like the real
  thing · severity: medium · → mitigation: none — child 4's first step is a
  one-composite end-to-end slice with a stop-and-report rule
- Byte-stable output depends on removing every clock, date and temp path from
  the captured screens · severity: low · → mitigation: none — child 2 tests a
  double capture for byte equality, per adapter
- The pinned look is chosen before the 18 existing images are regenerated and
  may not suit all of them · severity: low · → mitigation: none — child 6 shows
  old and new side by side before replacing, and child 8 revisits the choice

No separate mitigation tasks are proposed: each risk is covered by a step
already inside a child.
