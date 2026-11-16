---
Task: t2278_docs_tui_screenshot_generator.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: t2278 — docs TUI screenshot generator (parent, split into children)

## Design revision (2026-11-15)

The first version of this design captured each TUI headless under
`App.run_test`, behind per-TUI adapters that patched internals, driven by
hand-written YAML scene specs. The user rejected that direction while child 2
was being planned. The direction given:

> The agent should read the documentation, determine what needs illustrating,
> launch the appropriate app with sample data, inspect the screen, navigate
> through keys/dialogs, verify the desired state, and capture it. Saved recipes
> may help repeat successful captures, but should emerge from that workflow.
> When a saved recipe fails or no longer illustrates the documentation
> correctly, the agent should inspect the current TUI, discover a working
> route, and update the recipe.

Everything below "Design" is written for that workflow. Child 1 (marker
grammar, checker, marker migration) landed before the revision and is
unchanged by it. In the Context list below, the facts about
`App.export_screenshot()`, `tests/test_no_raw_tmux.sh` and the monitor's
`$TMUX` requirement are kept as history; they no longer shape the design,
because every capture now runs the real TUI inside a real tmux pane.

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

### Layout (all under `website/`, nothing in `.aitask-scripts/`)

```
website/check_screenshots.py        # stdlib only; marker + image-src check (child 1)
website/screenshots.sh              # launcher: sources .aitask-scripts/lib/python_resolve.sh, require_ait_python
website/screenshots/
  markers.py                        # stdlib only; the one marker grammar (child 1)
  sample_project.py                 # DATASETS: named sample-data builders (data only)
  session.py                        # isolated tmux session: start, setup, run, screen, keys, wait, find, stop
  svg_export.py                     # captured pane (ANSI) -> Rich SVG
  recipe.py                         # scenes/<id>.yaml loader, validator and writer (PyYAML)
  cli.py                            # the verbs
  svgpost.py                        # crop + overlays on cell rectangles (child 3)
  stitch.py                         # multi-pane window -> one grid (child 4)
  scenes/<scene_id>.yaml            # one recorded recipe per scene
  .staging/                         # gitignored: sessions, batches
```

The tool needs Rich and PyYAML, so it runs on the framework venv
(`require_ait_python`). `markers.py` and `check_screenshots.py` stay
stdlib-only so the check can run in the Hugo CI job.

### Roles

- **The agent does the discovery.** A Claude-only skill (child 5) reads a doc
  page, decides which state illustrates it, and reaches that state by driving
  the real TUI. There are no per-TUI adapters and no patched internals.
- **The tool is a small set of primitives** the agent calls through
  `website/screenshots.sh`. It owns isolation, the sample project, screen
  reading, key input, bounded waits and image export. It makes no decisions
  about what to show.
- **A recipe is a record of a capture that worked**, written by the tool from
  the session journal, not authored up front. It lives at
  `website/screenshots/scenes/<id>.yaml` and keeps child 1's `id:` / `output:`
  contract, so the checker and `--owners` work unchanged.

### Primitives (`website/screenshots.sh <verb>`)

| verb | what it does |
|---|---|
| `session start [--size CxR] [--dataset NAME]` | Builds a fresh sample project from a named dataset (default `base`) in a temp dir, starts a tmux server on a private socket, opens a shell pane in the project. Prints `SESSION:<id>`. |
| `setup <id> -- <command>` | Runs a data-preparation command in the project before the TUI is launched (for example `./ait lock 12 --email alex@example.com`), waits for it to exit, and fails on a non-zero status. Journaled as setup. Refused once `run` has been called. |
| `run <id> -- <command>` | Launches the TUI: types the command into the pane (for example `./ait board`). Once per session. |
| `screen <id> [--pane P]` | Prints the pane as plain text with row numbers, plus pane geometry and the running command. This is how the agent inspects the screen. |
| `keys <id> <key>...` | Sends keys (tmux key names). |
| `wait <id> --text T \| --gone T [--timeout S]` | Bounded poll on screen text. A timeout is a failure with the last screen printed. Never a sleep. |
| `find <id> --text T` | Cell coordinates of a text on screen (for crops and overlays, child 3). |
| `shot <id> --scene ID --output FILE [--png]` | Exports the pane as SVG into a new or current batch under `.staging/`, records it in `manifest.json`. `--png` also renders a PNG (when `rsvg-convert` or `magick` exists) so the agent can look at the image, not only its text. |
| `recipe save <id> --scene ID --expect T... --illustrates TEXT [--replace]` | Writes `scenes/<ID>.yaml` from the session's **whole journal**: dataset, setup commands, size, launch command, keys, waits, the texts that must be on screen at capture time, and what the image is meant to show. Only a clean discovery session can be saved (see "Which journal becomes a recipe"). Refuses to overwrite an existing recipe without `--replace`. |
| `replay --scene ID \| --all \| --pending [--no-keep]` | Runs recipes in fresh sessions. A recipe whose waits or expected texts fail is reported `FAILED:<scene>\|step <n>\|<reason>`, stages nothing, and leaves its session open for inspection (see "Recipe lifecycle"). |
| `session stop <id> \| --all`, `session list` | Tears down. |
| `list` | Scenes with output, marker count and whether the image exists. |

`recipe save` refuses unless a `replay` of the new recipe passes in a fresh
session. That is the test that a recipe is a repeatable route and not a
transcript of the agent's detours.

### Sample state: the setup contract

A screenshot often needs data that a bare project does not have: a locked
task, a trail, a brainstorm session with proposal nodes. The agent may prepare
that data, but a fresh replay must be able to prepare it too. So the state a
recipe starts from is fully described by two recorded things, and nothing
else:

1. **`dataset:`** names an entry in `sample_project.DATASETS`. A dataset is a
   function that writes project *data* into the temp tree: task files,
   metadata, a local bare git remote, artifact files. Datasets compose
   (`board_locks` = `base` plus a remote). They are in source because several
   recipes share them. A dataset never imports, patches or stubs TUI code;
   whatever it writes, the real TUI reads through its normal code paths.
2. **`setup:`** is the ordered list of commands the agent ran with the `setup`
   verb. They are real framework commands run in the project shell
   (`./ait lock …`, `./ait artifact …`, `./ait brainstorm …`). Replay runs
   them in order after building the dataset and before the launch; a non-zero
   exit is `FAILED:<scene>|setup <n>|<reason>`.

Rules that make this hold:

- Setup commands must not need the network or the user's accounts, and must
  not depend on the current date for what ends up on screen.
- Anything the agent does to the project outside these two channels (editing
  a file in the temp tree directly, running a command in another shell) is
  not recorded. The fresh-session replay inside `recipe save` is what catches
  it: the replay starts from the dataset and the setup list only, so a state
  that depended on unrecorded preparation fails the `expect` check and the
  recipe is not written.
- When the agent finds it needs preparation that is too large for a few setup
  commands (a brainstorm session with six nodes), it adds a dataset. That is a
  data builder reviewed like any other code, not an adapter.

Child 2 ships the contract, the `base` dataset and the mechanism. The datasets
for locks, trails, brainstorm and agent stand-ins are added by the child whose
scenes need them (children 4 and 5), each with a test that the dataset builds
and the real TUI shows its data.

### Which journal becomes a recipe

Exploration is messy: wrong keys, waits that time out, dead ends. None of that
may reach a recipe. The rule is simple and has no step-filtering:

- A session has an **origin**: `discovery` (from `session start`) or `replay`
  (started by `replay`, including one kept open after a failure).
- `recipe save` only accepts a `discovery` session whose journal, from
  `session start` to the `shot`, has **no failed step** (no timed-out wait, no
  failed setup command). Otherwise it refuses with: start a fresh session and
  walk the route cleanly.
- So the working pattern is two passes. First explore, in any session, until
  the route is known. Then `session start` again, walk the known route once
  with no detours, `shot`, `recipe save`.
- A replay-origin session is for **inspection only**. The agent may read its
  screen and press keys there to find out what changed, but nothing done in it
  can be saved. Its journal (the replayed steps and the timed-out wait) is
  never the source of a recipe.

### Recipe lifecycle: record, replay, repair

A recipe is a cache of a route, not the source of truth. The source of truth
is the documentation and the TUI as it is today. So a recipe that stops
working is repaired by the agent, never hand-patched blind and never left
failing.

- **Each recipe records what it is meant to show.** `illustrates:` holds the
  intent in one or two sentences (taken from the page text and the marker's
  alt and caption at capture time), and `expect:` holds the texts that must be
  on screen. The first is for the agent's judgement, the second for the tool.
- **Two ways a recipe goes stale.**
  1. *It fails.* A wait times out or an expected text is missing, because a
     key binding, a label or a layout changed. `replay` reports
     `FAILED:<scene>|step <n>|<reason>`.
  2. *It passes but no longer illustrates the page.* The route still works,
     but the page text changed, or the screen now shows something the alt and
     caption do not describe. Only the agent can see this: after every replay
     it compares the staged image (text and PNG) with the page section and the
     marker or `static-img` alt and caption.
- **Repair is the discovery loop again.** On a failure, `replay` keeps the
  session open at the failing step and prints `SESSION:<id>` with the current
  screen (`--no-keep` turns this off for unattended runs). The agent inspects
  the live TUI there to learn what changed. That kept session cannot be saved
  (see "Which journal becomes a recipe"), so the agent then starts a fresh
  discovery session, walks the working route cleanly to the state the page
  needs, takes the shot, and runs `recipe save --replace`. `--replace` keeps
  `id` and `output` (the file ownership never changes in a repair), rewrites
  the dataset, setup, route, `expect` and `illustrates`, and has the same gate
  as a first save: the new recipe must pass a replay in a fresh session.
- **A repaired recipe is a new capture.** Its image goes into a new batch and
  through user review before `apply`, like any other.
- **If the agent cannot find a route** (the feature was removed, or the page
  describes something the TUI no longer does), it changes nothing and reports
  the scene with what it found. That is a documentation finding for the user,
  not something to work around.

### Isolation rules

- Every tmux call goes through `TmuxClient(socket_args=["-L", "ait_shots_<id>"])`
  from `.aitask-scripts/lib/tmux_exec.py` (it adds `-u` and UTF-8 decoding,
  tmux gateway policy 5). Raw `tmux` argv is never built by hand.
- The server is started only by `start_server()`, with `-f /dev/null`, after
  asserting the socket has no server. The user's tmux config is never loaded.
  Options the capture needs (`default-terminal tmux-256color`) are set by
  command after start.
- The pane environment is pinned at spawn: `AITASKS_TMUX_SOCKET` (so the TUI's
  own tmux calls stay on the private server), `COLORTERM=truecolor`, scratch
  `HOME` and `XDG_CONFIG_HOME` (so the user's project registry, keybinding
  overrides and themes cannot reach the screen), `AIT_PYTHON` set to the
  interpreter `require_ait_python` resolved, and `COLUMNS` / `LINES` unset.
- Every server gets a time-to-live: a background `run-shell` that kills it
  after one hour. A forgotten session cannot outlive that.
- The sample project is the only data on screen. It is a standalone `ait`
  project (a copy of `ait`, a symlink to `.aitask-scripts`, its own git repo)
  with invented names: project `lumen`, tasks such as `t12_add_checkout_page`
  with children. Never the real repo, never `aitasks` as an example name.

### Image export

`capture-pane -e -p -N` gives the pane with SGR escapes. Findings from the
first end-to-end example (child 2, step B1), which the exporter must respect:

- **tmux carries SGR state across lines.** The whole capture goes through one
  `rich.ansi.AnsiDecoder`; decoding row by row loses every background that was
  set on an earlier line.
- **`-N` is required.** Without it tmux drops trailing cells and the right
  part of each row loses its background.
- The decoded rows are printed into a recording `Console` of the pane's size,
  then `export_svg(title="aitasks <tui>", theme=SVG_EXPORT_THEME,
  unique_id="terminal-<scene id>")`. This matches the chrome of the 18
  existing images (Rich's default export theme, Fira Code).
- **PNG previews use headless Chromium.** `rsvg-convert` drops leading
  no-break spaces and has no emoji font, so its output is not what a site
  visitor sees. `shot --png` renders through `chromium --headless
  --screenshot`, falls back to `rsvg-convert` with a printed warning, and is
  only ever a preview for the agent: the SVG is the deliverable.
- The real TUIs boot unchanged under a scratch `HOME` with `AIT_PYTHON`
  pinned.

Multi-pane windows are stitched from `list-panes` geometry (child 4).

### What is dropped

- Backend A (headless Textual), `registry.APPS` adapters, widget-selector
  settle conditions and selector-based crops.
- **Byte-identical output across runs as a requirement.** Real TUIs show real
  clocks and timers. Stability is instead: a replay must reach the recipe's
  expected texts, and every new image is reviewed by the user before `apply`.
  Where a clock shows on screen, the sample project pins what it can (fixed
  dates in task files).

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
- `shot`, `replay`, `apply` and the regeneration child read the target filename from
  the spec only, never from a marker or a page.
- Sample datasets live in source (`sample_project.DATASETS`); a recipe's YAML
  holds only what was recorded from one capture.

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

## Child tasks

| child | scope |
|---|---|
| **1** (archived) | Marker grammar (`markers.py`), `check_screenshots.py`, the 17 markers migrated over 13 scenes, CI step, README section. |
| **2** | Sample project with the `base` dataset and the setup contract, session primitives, single-pane SVG export, journal, `recipe save` / `replay`, batch manifest. First example: `board_child_tasks`. |
| **3** | Crop and overlays on **cell rectangles** only (`find` gives the cells). `svgpost.py` as planned. Scenes: annotated board layout, annotated card. |
| **4** | Multi-pane windows: stitching, stand-in agent panes (`tests/lib/fake_composer_agent.py`). Scenes: minimonitor, sitrep window, `ait ide` startup, annotated monitor layout, and the switcher opened from monitor and from minimonitor (the real switcher lists the isolated session's real windows). The config-not-loaded and `LC_ALL=C` glyph tests move to child 2, because child 2 now owns the server. |
| **5** | The skill: the discovery loop (read page, decide, drive, verify, shot, save recipe) and the **repair loop** (replay, judge each result against the page, re-discover and `--replace` on a failure or a mismatch, report what cannot be repaired). `preview` / `apply` on the batch manifest (unchanged), then the pass over the remaining markers. |
| **6** | Regenerate the 18 existing images with the same workflow. No adapters to write. It is also the first real use of the repair loop: replay everything recorded so far and repair what has drifted. |
| **7** | Real pixels, optional: attach a pinned terminal to the same tmux session on a headless Hyprland output. |
| **8** | Retrospective. Questions rewritten for this design; they are in its task file. |

Each child's task file and plan under `aiplans/p2278/` carries its full
context. Children depend on earlier siblings in this order. Child 1 is
archived (`aiplans/archived/p2278/`).

## Verification

End to end, once children 1-5 have landed:

- `python3 website/check_screenshots.py --strict` exits 0 and lists no
  unresolved marker.
- `cd website && python3 check_links.py --build` passes.
- `bash tests/run_all_python_tests.sh --test-dir tests` shows the screenshot
  test modules passing.
- `website/screenshots.sh replay --all` reaches every recipe's expected texts
  and stages every scene under its `output:` filename, with zero markers left
  in the docs; `check_screenshots.py --owners` attributes every generated
  image to its scene.
- A recipe broken on purpose is repaired by the skill, and one whose
  destination does not exist is reported with nothing changed (child 5's two
  scenarios).
- Editing a marker between capture and `apply --batch` gets that scene
  refused and leaves the page and the image untouched.
- After any run, `website/screenshots.sh session list` is empty and the
  user's own tmux servers are untouched.
- Every generated image is viewed on the local Hugo server (`./serve.sh`).

Post-implementation for each child follows Step 9 of the task workflow
(review, commit, archival); the parent is archived when the last child is.

## Risk

### Code-health risk: low
- The tool starts and kills tmux servers on a developer machine · severity:
  low · → mitigation: none — it only ever addresses its own
  `-L ait_shots_<id>` socket through `TmuxClient`, the server is started with
  `-f /dev/null`, and every server has a one-hour time-to-live
- `apply` edits doc pages and image files on a shared checkout · severity: low
  · → mitigation: none — it is bound to one reviewed batch, replaces marker
  text only, and refuses a changed image, destination or marker (child 5 tests
  each refusal)
- Live-TUI tests run under a wall-clock boot budget · severity: low · →
  mitigation: none — they sit in the serial carve-out of
  `tests/run_all_python_tests.sh`

### Goal-achievement risk: medium
- Multi-pane scenes (monitor, minimonitor, sitrep) need realistic content in
  the other panes; stand-in agents may not look like the real thing ·
  severity: medium · → mitigation: none — child 4's first step is one
  composite end to end with a stop-and-report rule
- A recipe can keep passing while the page it illustrates has changed ·
  severity: medium · → mitigation: none — each recipe stores `illustrates`,
  and the skill's repair loop compares every replayed image with the page
- The agent may reach a state through preparation a replay cannot repeat ·
  severity: medium · → mitigation: none — recorded state is a named dataset
  plus `setup` commands only, and `recipe save` replays in a fresh session
  before it writes
- Some scenes need data no framework command creates offline (a lock needs a
  remote; a brainstorm session normally needs agents) · severity: medium · →
  mitigation: none — such data goes into a dataset builder in the child that
  needs it, and a scene whose data cannot be built is reported, not faked
- Output is not byte-identical across runs (real clocks and timers) ·
  severity: low · → mitigation: none — `apply` only ever copies the exact
  batch the user reviewed, and child 8 checks whether this caused churn

No separate mitigation tasks are proposed: each risk is covered by a step
already inside a child.
