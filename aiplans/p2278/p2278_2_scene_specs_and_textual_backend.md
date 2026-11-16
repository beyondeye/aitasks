---
Task: t2278_2_scene_specs_and_textual_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/fable5_2 @ 2026-11-15 23:47
---

# Plan: t2278_2: agent-driven capture through real TUIs in tmux (design revision + first example)

## Context

The parent design (and this child's previous plan) captured screenshots by
booting each TUI headless under `App.run_test`, behind per-TUI adapters that
patch internals, driven by hand-written YAML scene specs. The user rejected
that direction on 2026-11-15. The intended workflow is:

> The agent reads the documentation, decides what needs illustrating, launches
> the real app with sample data in an isolated tmux session, inspects the
> screen, navigates with keys and dialogs, verifies the desired state, and
> captures it. Saved recipes may help repeat a successful capture, but they
> emerge from that workflow.

So this plan does two things, in order:

1. **Part A** revises the parent design and the plans/tasks of children 2-8
   around that workflow.
2. **Part B** implements this child under the revised design, starting with
   **one documentation example end to end** before any tooling is generalised.

What child 1 delivered stays valid and is kept as is: the marker grammar,
`website/check_screenshots.py`, and the rule that `scenes/<id>.yaml` owns the
output file through its `id:` / `output:` lines (`markers.read_spec_owner`).

## Revised design (what Part A writes into the parent plan)

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

`capture-pane -e -p` gives the pane with SGR escapes. Each row becomes
`rich.text.Text.from_ansi`, printed into a recording `Console` of the pane's
size, then `export_svg(title="aitasks <tui>", theme=SVG_EXPORT_THEME,
unique_id="terminal-<scene id>")`. This matches the chrome of the 18 existing
images (Rich's default export theme, Fira Code). Multi-pane windows are
stitched from `list-panes` geometry (child 4).

### What is dropped

- Backend A (headless Textual), `registry.APPS` adapters, widget-selector
  settle conditions and selector-based crops.
- **Byte-identical output across runs as a requirement.** Real TUIs show real
  clocks and timers. Stability is instead: a replay must reach the recipe's
  expected texts, and every new image is reviewed by the user before `apply`.
  Where a clock shows on screen, the sample project pins what it can (fixed
  dates in task files).

### Children after the revision

| child | revised scope |
|---|---|
| **2** (this) | Sample project with the `base` dataset and the setup contract, session primitives, single-pane SVG export, journal, `recipe save` / `replay`, batch manifest. First example: `board_child_tasks`. |
| **3** | Crop and overlays on **cell rectangles** only (`find` gives the cells). `svgpost.py` as planned. Scenes: annotated board layout, annotated card. |
| **4** | Multi-pane windows: stitching, stand-in agent panes (`tests/lib/fake_composer_agent.py`). Scenes: minimonitor, sitrep window, `ait ide` startup, annotated monitor layout, and the switcher opened from monitor and from minimonitor (the real switcher lists the isolated session's real windows). The config-not-loaded and `LC_ALL=C` glyph tests move to child 2, because child 2 now owns the server. |
| **5** | The skill: the discovery loop (read page, decide, drive, verify, shot, save recipe) and the **repair loop** (replay, judge each result against the page, re-discover and `--replace` on a failure or a mismatch, report what cannot be repaired). `preview` / `apply` on the batch manifest (unchanged), then the pass over the remaining markers. |
| **6** | Regenerate the 18 existing images with the same workflow. No adapters to write. It is also the first real use of the repair loop: replay everything recorded so far and repair what has drifted. |
| **7** | Real pixels, optional: attach a pinned terminal to the same tmux session on a headless Hyprland output. |
| **8** | Retrospective. Questions rewritten for this design (see step A4). |

## Part A: revise the design documents

A1. **Parent plan** `aiplans/p2278_docs_tui_screenshot_generator.md`: replace
    "Layout", "Scene spec", "Backends" and "CLI and skill" with the revised
    design above. Keep "Marker grammar" and "`check_screenshots.py`" untouched.
    Add a dated "Design revision (2026-11-15)" note at the top saying what
    changed and why, quoting the user's direction. Update the child list, the
    end-to-end verification (drop the byte-identical line) and the Risk
    section.

A2. **Parent task** `aitasks/t2278_docs_tui_screenshot_generator.md`: in
    "Capture backends", mark A as dropped and B as the default path; change
    requirement 2 ("Scene specs") to "recipes recorded from a successful
    capture"; change requirement 3 to cell rectangles.

A3. **This child's task file**: rewrite "Key Files", "Capture rules" and
    "Verification Steps" to match Part B. The filename keeps its old slug
    (`scene_specs_and_textual_backend`); the body says so in one line. The
    acknowledged inbox note stays as it is.

A4. **Children 3-8**: rewrite each task file and plan per the table above.
    - 3: remove selector resolution and the monitor adapter; add `find`.
    - 4: remove the "first composite" spike's server bootstrap (child 2 owns
      it); keep stitching and its stop rule about realistic pane content; add
      the three scenes moved in. Stand-in agent panes come from a dataset
      (`agents`) plus setup commands, under the setup contract.
    - 5: skill steps become the discovery loop and the repair loop from
      "Recipe lifecycle"; `preview` / `apply` text is unchanged. It adds the
      datasets its scenes need (`board_locks` with a local bare remote for the
      lock dialog, `trails`, `brainstorm`), each with a build test. The skill
      text states the setup contract and the two-pass rule. Its acceptance
      has **two separate repair scenarios**, and each has one passing outcome:
      1. *Reachable destination.* A copy of a working recipe is broken (a
         wrong key and a stale expected text) while the state it illustrates
         still exists in the TUI. Pass only if the run ends with a replaced
         recipe that replays in a fresh session and whose image shows the
         destination text. A report of "could not repair" is a failure here.
      2. *Unavailable destination.* A recipe whose `illustrates` and `expect`
         name a state the sample project cannot reach. Pass only if the run
         reports the scene with what it found, the recipe file is
         byte-identical, and nothing is staged for it.
    - 6: remove the adapters step; add "replay all, repair what drifted" as
      its first step.
    - 7: capture goes through the shared session.
    - 8: replace the questions about spec fields and adapter hooks with: how
      many recipes replay without edits; which primitives the agent needed
      that were missing; how often the agent's chosen state matched what the
      user wanted at review; whether dropping byte-identity caused review
      churn; how many recipes needed a repair, and whether each repair was a
      failed replay or a passing one that no longer matched the page. The task says the questions are fixed before evidence is read, so
      this rewrite happens now, before any evidence exists.

A5. Commit with `./.aitask-scripts/aitask_task_commit.sh`, naming every file.
    Then send an `ait note` to t2278_3 … t2278_8 only if a task is held by a
    live session (none is expected; all are `Ready`).

## Part B: implement this child

B1. **One documentation example end to end, by hand, before any tooling.**
    The example is the `board_child_tasks` marker in
    `website/content/docs/tuis/board/how-to.md`.
    - Read the page section around the marker and decide the state to show.
    - In the scratchpad, write a throwaway script that builds a sample
      project (the shape of `_build_fixture` in
      `tests/test_board_startup_focus_live.py`: copy `ait`, symlink
      `.aitask-scripts`, write metadata and a parent with two children,
      `git init`), starts the isolated server as specified above, runs
      `./ait board`, and exposes screen / keys.
    - Drive it as the agent: read the screen, expand the parent, confirm the
      child cards and connector lines are on screen.
    - Export the SVG, render a PNG, look at it, and show it to the user.
    - **Stop rule.** If the export loses colours, box-drawing characters or
      wide glyphs, or the TUI will not boot under the scratch `HOME`, stop and
      report before building anything else. Record what had to be pinned.

B2. **`website/screenshots/sample_project.py`**: `DATASETS` (name → builder)
    and `build(root, dataset="base") -> Path`. `base`: invented tasks across
    the board columns, one parent with children, fixed dates,
    `auto_refresh_minutes: 0`, the shipped `gates_reference.yaml` as
    `gates.yaml`, its own git repo. Builders write data only and may call one
    another. Self-contained; it does not import from `tests/` or from any TUI
    module. An unknown dataset name is an error naming the known ones.

B3. **`website/screenshots/session.py`**: `start_server`, `start`, `setup`,
    `run`, `screen`, `keys`, `wait`, `find`, `stop`, `list_sessions`. Session
    state (socket name, pane id, project path, dataset, origin, journal) is a
    JSON file under `website/screenshots/.staging/sessions/<id>/`. Every
    journal entry has a kind (`setup` / `launch` / `keys` / `wait` /
    `wait_gone` / `shot`) and an `ok` flag. `setup` runs the command in the
    pane shell and reads its exit status from a marker line it appends, with a
    bounded wait. `setup` after `run`, and a second `run`, are refused. Pane ids come from
    `-P -F "#{pane_id}"`. Teardown removes the temp project.

B4. **`website/screenshots/svg_export.py`**: pure function
    `ansi_rows_to_svg(rows, width, height, title, scene_id) -> str`.

B5. **`website/screenshots/recipe.py`** (PyYAML): `Recipe`, `load`, `load_all`,
    `save`. Loading first calls `markers.read_spec_owner(path)` and rejects
    any problem, then checks the YAML values equal the owner reader's. Fields:
    `id`, `output`, `size`, `dataset` (must be in `DATASETS`), `setup` (list
    of command strings, may be empty), `launch`, `steps` (`keys` / `wait` /
    `wait_gone`),
    `expect`, `illustrates`, optional `title`, and `crop` / `overlays` passed
    through for child 3. `save(..., replace=True)` keeps the existing `id` and
    `output` and refuses if the caller's differ. `save` takes a session and
    refuses one whose origin is `replay` or whose journal has an entry with
    `ok: false`. Unknown keys are errors. Duplicate `output` fails in `load_all`.

B6. **`website/screenshots/cli.py` and `website/screenshots.sh`**: the verbs in
    the table. The launcher sources `.aitask-scripts/lib/python_resolve.sh`
    and uses `require_ait_python`. `shot` and `replay` write to
    `.staging/<batch-id>/` (created with `mkdir(exist_ok=False)`) and keep
    `manifest.json`: per scene the `output`, the staged SHA-256, the
    destination state (`absent` or its SHA-256), and each marker's page and
    exact text from `markers.scan`. `BATCH:<id>` is printed. Add
    `website/screenshots/.staging/` to the repo `.gitignore`.

B7. **Redo the example through the tool.** Capture `board_child_tasks` with
    the verbs only, `recipe save` it, and confirm `replay --scene
    board_child_tasks` passes in a fresh session. Show the user the staged
    image. Then exercise the repair loop once on purpose: break a copy of the
    recipe (a wrong key and a stale expected text), replay it, inspect the
    kept session, then walk the route cleanly in a fresh discovery session and
    `recipe save --replace`. Also exercise the setup contract once on purpose:
    reach a state that needs a `setup` command (for example a task whose
    status was changed with `./ait update`), save it to a scratch scenes dir
    and replay it. Record in the notes whether the primitives were enough.
    This is a manual demonstration of the mechanism; the skill's own repair
    behaviour is verified in child 5. This child ships that one recipe. The other single-pane scenes
    (board lock, trails, brainstorm, switcher dialog) are captured by child
    5's pass, once the user has seen this example.

B8. **Tests.**
    - `tests/test_screenshots_recipe.py`: validation rules; the loader refuses
      every `REJECTED` row of `test_check_screenshots`' owner table (imported);
      round trip of `save` then `load`.
    - `tests/test_screenshots_svg_export.py`: colours, bold, box-drawing and a
      wide glyph survive; `unique_id` and title are as given.
    - `tests/test_screenshots_session_live.py` (skips only when `shutil.which
      ("tmux")` is empty): start, run the board on the sample project, `wait`,
      `shot` contains a sample task name; a `wait` that cannot match fails and
      stages nothing; `stop` leaves no server and no temp project; a scratch
      `tmux.conf` with a `run-shell 'touch <sentinel>'` is never executed; under
      `LC_ALL=C` box-drawing characters reach the SVG unchanged, with a
      control (the same capture through raw argv without `-u`) that shows the
      `_` substitution; `replay` of the shipped recipe passes; a recipe with a
      wrong key fails with `FAILED:<scene>|step <n>|…`, stages nothing and
      leaves a session that `screen` can read, while `--no-keep` leaves none;
      `recipe save` without `--replace` refuses an existing scene, and with it
      keeps `id` and `output` and rewrites the route only after a passing
      replay (a `--replace` whose new route fails leaves the old file
      byte-for-byte).
    - Setup contract, in the same live module: a recipe with a `setup` command
      replays to a screen showing that command's effect, and the same recipe
      with the `setup` list removed fails its `expect` (the control that the
      setup is what produced the state); a session whose project was changed
      outside the verbs (the test writes a task file into the temp tree
      directly) is refused by `recipe save`, because the fresh replay does not
      show it, and no recipe file is written; a failing setup command reports
      `FAILED:<scene>|setup <n>|…` and never launches the TUI; `setup` after
      `run` is refused.
    - Journal boundary: `recipe save` refuses a replay-origin session (kept
      after a failure) even after further successful keys and waits in it; it
      refuses a discovery session whose journal holds a timed-out wait; the
      same route walked cleanly in a fresh session saves.
    - `tests/test_screenshots_sample_project.py`: `base` builds, is a git
      repo, shows no real repo name; an unknown dataset is an error.
    - Add the live module to the serial carve-out in
      `tests/run_all_python_tests.sh` and to the list in `CLAUDE.md`, because
      it boots a real TUI under a wall-clock budget.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`; read the last line.
- `shellcheck website/screenshots.sh`.
- `website/screenshots.sh list` shows `board_child_tasks`;
  `website/screenshots.sh replay --scene board_child_tasks` prints a `BATCH:`.
- `website/screenshots.sh session list` is empty afterwards, and
  `tmux -L ait_shots_<id> list-sessions` fails for the ids used.
- `python3 website/check_screenshots.py`: `board_child_tasks` has a spec, no
  ownership violation.
- The user views the staged `aitasks_board_child_tasks.svg`.
- `ait ls --children 2278` still lists children 2-8 with their revised bodies.

## Notes for sibling tasks (to fill in at the end)

Record: the primitives as implemented; the recipe and manifest schemas; what
had to be pinned in the pane environment; what B1 found about export fidelity.

Post-implementation: Step 9 of the task workflow (review, commit, archival).

## Implementation log

- **B1 done (2026-11-16), before Part A.** Deviation from the stated order: the
  hand-driven example ran first, because its stop rule decides whether the
  design Part A writes into six sibling plans is sound. It passed.
  - The real `./ait board` boots on a standalone sample project under a
    scratch `HOME` / `XDG_CONFIG_HOME` with `AIT_PYTHON` pinned; nothing else
    had to be pinned. Pane shell: `bash --noprofile --norc`.
  - `x` on the parent card expands the children with `↳` connectors.
  - Export defects found and fixed: tmux carries SGR state across lines, so
    the whole capture goes through one `AnsiDecoder`; `capture-pane` needs
    `-N` or trailing cells lose their background.
  - `rsvg-convert` is not a faithful preview (drops leading no-break spaces,
    no emoji). Headless Chromium is. `shot --png` uses Chromium first.
  - A parent with an `Implementing` child shows `⚡ t12_1 …` and
    `👶 2 more children`, not the `👶 N children` line the page names. The
    `base` dataset keeps all children of the example parent `Ready`.
- **Part A done (2026-11-16).** Parent plan rebuilt (design revision note,
  revised design, B1 findings in "Image export"); parent task requirements 2
  and 3 and the backends section revised; task bodies and plans of children
  3-8 and this task's body rewritten. Inbox and Gate Runs sections untouched.

- **B2-B8 done (2026-11-16).** Tool written, the example re-done through
  the verbs, the repair loop and the setup contract exercised by hand, tests
  and mutants run. Details in "Final Implementation Notes".

## Risk

### Code-health risk: low
- The tool starts and kills tmux servers on a developer machine · severity:
  low · → mitigation: none needed; it only addresses its own
  `-L ait_shots_<id>` socket through `TmuxClient`, every server has a
  one-hour time-to-live, and B8 tests that `stop` leaves nothing behind
- A live-TUI test with a boot budget can flake under a loaded worker pool ·
  severity: low · → mitigation: none needed; B8 puts it in the serial
  carve-out
- Part A rewrites six sibling task files and plans in one commit · severity:
  low · → mitigation: none needed; all six are `Ready` and unclaimed, and the
  commit names each path

### Goal-achievement risk: medium
- The ANSI-to-SVG route may not reproduce what the TUI draws (colour depth
  under `-f /dev/null`, wide glyphs, cell alignment) · severity: medium ·
  → mitigation: none needed; B1 tests exactly this on the first example and
  has a stop rule
- A real TUI may not boot, or may behave differently, under a scratch `HOME`
  and pinned interpreter · severity: medium · → mitigation: none needed; B1
  finds this before any tooling is written
- Without byte-identity, a replayed image can differ from the reviewed one in
  ways nobody looks at · severity: low · → mitigation: none needed; `apply`
  only ever copies the exact reviewed batch (child 5), and child 8 checks
  whether this caused churn
- A recipe can keep passing while the page it illustrates has changed, and
  the tool cannot see that · severity: medium · → mitigation: none needed;
  each recipe stores `illustrates`, and the skill's repair loop (child 5)
  compares every replayed image with the page; child 8 counts how often that
  caught something
- Recipes recorded from a session may carry the agent's detours or a failed
  replay's steps · severity: low · → mitigation: none needed; only a clean
  discovery session can be saved, and `recipe save` requires a passing replay
  in a fresh session (B8 tests both refusals)
- The agent may reach a state through preparation a replay cannot repeat ·
  severity: medium · → mitigation: none needed; the setup contract limits
  recorded state to a named dataset plus `setup` commands, and the fresh
  replay inside `recipe save` rejects anything else (B8 tests it with a
  control)
- Some scenes may need data no framework command can create offline (a lock
  needs a remote; a brainstorm session normally needs agents) · severity:
  medium · → mitigation: none needed; such data goes into a dataset builder
  in the child that needs it, and a scene whose data cannot be built is
  reported to the user rather than faked

No separate mitigation is proposed: each risk is covered by a step of this
plan.

## Post-Review Changes

### Change Request 1 (2026-11-16 08:25)
- **Requested by user:** five review findings, all verified as valid:
  (1) a second `shot` of a scene in one session overwrote the image and its
  manifest hash under the same batch id, so `apply` could not tell which image
  had been reviewed; (2) `replay` checked each `expect` text separately on the
  live screen and exported afterwards, so texts that were never on screen
  together passed and the image showed only the last; (3) `setup` / `run`
  joined their arguments with spaces and lost argument boundaries; (4) a
  wait's timeout was not journaled, so a discovery wait given 120 s replayed
  with the 30 s default; (5) `dataset: []` raised `TypeError` instead of
  `RecipeError`.
- **Changes made:** (1) `stage` refuses to write a scene or output a batch
  already holds, and `shot` opens a new batch for a recapture; the earlier
  image and manifest stay byte-identical. (2) `export` takes the expected
  texts and checks them together on the settled frame it then exports,
  retrying within `EXPECT_TIMEOUT`; a miss is `FAILED:<scene>|expect|…` and
  stages nothing. (3) one argument after `--` is a shell command string,
  several are an argv quoted back with `shlex.join`. (4) every wait journals
  its timeout; `from_session` records one above the default as
  `- wait: {text: …, timeout: N}`, the loader accepts both forms, and replay
  uses the step's own budget. (5) the dataset's type is checked first.
  Tests added for each, with a control where the property needs one; seven
  further mutants on an isolated copy, all killed.
- **Files affected:** `website/screenshots/cli.py`, `session.py`, `recipe.py`,
  `svg_export.py`, `tests/test_screenshots_recipe.py`,
  `tests/test_screenshots_session_live.py`.

## Final Implementation Notes
- **Actual work done:**
  - Part A: parent plan rebuilt around the agent-driven design; parent task
    revised; task bodies and plans of children 3-8 and this task's body
    rewritten (one `ait:` commit, 16 files).
  - `website/screenshots/sample_project.py` (`DATASETS`, `build`; dataset
    `base`), `session.py` (isolated tmux session and journal), `svg_export.py`
    (ANSI capture to Rich SVG, PNG preview, text read-back), `recipe.py`
    (load / validate / write, `from_session`), `cli.py` (verbs),
    `website/screenshots.sh` (launcher), `scenes/board_child_tasks.yaml`
    (recorded by the tool), `.gitignore` entry for `.staging/`.
  - Tests: `tests/test_screenshots_sample_project.py` (9),
    `test_screenshots_svg_export.py` (10), `test_screenshots_recipe.py` (30),
    `test_screenshots_session_live.py` (19, real board in tmux, ~70 s). The
    live module is in the serial carve-out (`tests/run_all_python_tests.sh`,
    CLAUDE.md block, and the two pinned counts in
    `tests/test_serial_carveout_doc_drift.sh`, 5 → 6).
- **Deviations from plan:**
  - B1 ran before Part A (see the log above).
  - `setup` runs its command as a subprocess with the pane's pinned
    environment and the project as cwd, not typed into the pane. Same
    environment, a real exit status, no marker parsing and no setup noise on
    the screen. Consequence for child 4: `$TMUX` is unset in a setup command,
    so anything that must run *inside* tmux needs the pane / window verbs.
  - `svg_export.ansi_to_svg` takes the whole capture, not a list of rows,
    because of the SGR carry-over.
  - The planned `LC_ALL=C` control ("a client without `-u` shows `_`") does
    not hold for `capture-pane` on tmux 3.8: the `_` rewrite applies to tmux
    *format* output, which `tests/test_tmux_utf8_client_live.sh` already
    covers. The test here keeps the positive assertion (box-drawing and
    accented text reach the SVG under `LC_ALL=C PYTHONUTF8=0`) and its control
    is that the subprocess really ran without a UTF-8 locale.
  - Added beyond the plan: `shot` waits until two consecutive captures agree
    (a half-painted frame is a failure, never an image); `stop` removes the
    dead tmux socket file, which tmux leaves behind; `replay --png`;
    `shot` / `recipe save` refuse an `output` another scene owns.
- **Issues encountered:**
  - First export had dark bands and lost backgrounds: SGR state carries across
    lines, and trailing cells need `-N`. Both fixed and tested.
  - `rsvg-convert` is not a faithful preview; `shot --png` uses headless
    Chromium and labels an rsvg fallback as unfaithful.
  - A parent with an `Implementing` child reads `2 more children`, not the
    `N children` the page names; the `base` dataset keeps the example parent's
    children `Ready`.
  - Pressing `x` before a card holds focus does nothing. The recipe waits for
    `╔` (the focused card's border) first.
- **Key decisions:**
  - Recipe size for the example is 126x44: three board columns fill the width
    and the first column shows all cards without scrolling.
  - A recipe file is written only after it reads back through both readers
    (`markers.read_spec_owner` and YAML), so a bad write never replaces a
    working recipe.
  - Mutants (run on an isolated copy, 16 + 7 after review): the first round had 15 killed for the intended reason.
    The survivor removes the loader's first owner-reader check; the loader's
    second check (both readers must return the same id / output) still
    refuses the same lines, so it is redundant cover, not a gap.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **Verbs** (`website/screenshots.sh`, global flags `--content --static
    --scenes --staging` before the verb): `session start [--size CxR]
    [--dataset N]`, `setup <id> -- cmd`, `run <id> -- cmd`, `screen <id>`,
    `keys <id> k...` (tmux key names), `wait <id> --text|--gone T [--timeout]`,
    `find <id> --text T` (`CELL:<col>,<row>`), `shot <id> --scene --output
    [--title] [--png]`, `recipe save <id> --scene --expect... --illustrates
    [--replace]`, `replay --scene...|--all|--pending [--no-keep] [--png]`,
    `session stop <id>|--all`, `session list`, `list`. Result lines are
    `KEY:value`; exit 1 on a failure or refusal.
  - **Recipe schema** (`recipe.py` docstring): `id`, `output`, optional
    `title`, `size`, `dataset`, `setup` (list), `launch`, `steps` (`keys` /
    `wait` / `wait_gone`; a wait is a text, or `{text, timeout}` when it was
    given more than the 30 s default), `expect`, `illustrates`; in code a step
    is `(kind, value, timeout)`; `crop` and `overlays` are
    accepted and passed through unvalidated for child 3. Unknown keys are
    errors, so child 3 and 4 add their fields to `REQUIRED` / `OPTIONAL`.
  - **Manifest** (`<staging>/<batch>/manifest.json`, schema 1): `batch`,
    `created_at`, `scenes: [{id, output, sha256, destination: "absent" |
    {sha256}, markers: [{page, text}]}]`, `failed: [{id, reason}]`. Images are
    at `<batch>/<output>`; PNG previews at `<batch>/_preview/<scene>.png`
    (not in the manifest). A batch is never rewritten: a discovery session
    puts its shots into one batch, a second shot of the same scene opens a
    new one, and every `replay` call creates a new one.
  - **Journal** (`<staging>/sessions/<id>/session.json`): entries
    `{kind, ok, ...}` with kinds `setup`, `launch`, `keys`, `wait`,
    `wait_gone`, `shot`. Child 4's pane and window verbs add kinds there and
    in `recipe.from_session`.
  - **Pinned in the pane:** `AITASKS_TMUX_SOCKET`, `AIT_PYTHON`, `COLORTERM`,
    scratch `HOME` / `XDG_CONFIG_HOME` (with a `.gitconfig` for the sample
    person), `TERM`, `LANG` / `LC_ALL=C.UTF-8`. Under the scratch `HOME` the
    `python3` on `PATH` (the framework wrapper) does not work; a setup command
    that needs Python uses `"$AIT_PYTHON"`; shell `bash --noprofile
    --norc` under `env -u COLUMNS -u LINES`. Nothing else was needed for the
    board.
  - **Datasets:** add a builder to `sample_project.DATASETS`; reuse
    `write_project_shell`, `write_tasks` and `_git_commit_all`.
    `tests/test_screenshots_sample_project.py` asserts the module imports no
    TUI code.
  - **Test helpers:** `svg_export.svg_plain_text(svg)` rebuilds the screen
    rows from an exported SVG; the live module's `LiveCase` drives
    `cli.main` with scratch directories and shortens the replay timeouts
    through `cli.STEP_TIMEOUT` / `cli.EXPECT_TIMEOUT`.
  - **Not done here, by design:** the other single-pane scenes (board lock,
    trails, brainstorm, switcher dialog) and `website/README.md` usage text
    belong to child 5.
