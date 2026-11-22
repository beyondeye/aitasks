---
Task: t2278_6_regenerate_existing_images.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-21 19:19
---

# Plan: t2278_6: regenerate the 18 existing images

## Context

Child 6 of t2278. Children 1-5 shipped the marker grammar and checker, the
isolated-tmux session tool (`website/screenshots/`), recipes/replay,
crop/overlays, multi-pane stitching, `preview`/`apply` and the
`aitask-docs-screenshots` skill, and applied 13 generated images. 18 images in
`website/static/imgs/` are still hand-made: captured from the real repository
(they show the real task names and a real email address), in two themes and
four terminal sizes. This child regenerates each with the skill's workflow so
every image on the site comes from the sample project `lumen` and has a
recipe. Design source: `aiplans/p2278_docs_tui_screenshot_generator.md`; the
skill's procedure is `.claude/skills/aitask-docs-screenshots/SKILL.md`.

## Verification of the existing plan (2026-11-20, tree at `b0bb6e257`)

- **Step 1 (replay, mapping) already passes.** `check_screenshots.py --report`
  lists no unresolved marker; `screenshots.sh replay --all --no-keep --png`
  staged all 13 recipes (batch `20261120T070547Z-7c0c5c`, exit 0), and
  `check_screenshots.py --owners` attributes every one of the 13 images to its
  scene with zero markers in the docs. What remains of step 1 is the visual
  judgement of each staged PNG against its page (repair loop).
- **`sitrep_window` must be repair-checked.** The sitrep redesign child 5's
  user comment anticipated landed as `514783b73` (t2334, item-type tabs) at
  07:05:55Z, seconds after the replay batch above was created; its TUI and
  pages are now clean. The page now describes tabs that show one item kind at a
  time, while the recipe's `illustrates` still describes the earlier mixed list
  ("a task to pick, an action, a question and a watch"). It is replayed again
  against the current tree in step 1 and is expected to need a repair.
- **Other in-flight framework edits.** The working tree also has uncommitted
  edits by other sessions to `monitor/monitor_app.py`, `monitor_core.py`,
  `monitor_shared.py`, `lib/tmux_exec.py`, `lib/agent_launch_utils.py`. A
  sample project copies the working tree's `.aitask-scripts`, so a capture
  shows that code. Handled in step 7.
- **Inventory (re-listed).** 19 shortcode uses, 18 distinct hand-made files,
  plus the unreferenced `aitasks_settings_code_agent_default_models_tab.svg`.
  Settings now has 9 tabs (Agent Defaults, Board, Project Config, Project
  Groups, Tmux, Artifacts, Models, Execution Profiles, Shortcuts); the old
  images show 4. Seed has `models_claudecode/codex/opencode.json`.
- **The Stats TUI charts windows ending today** (`stats_app.py:328,345,362`,
  `date.today()`), so archived tasks on fixed dates would render empty charts.
- **Codebrowser data path.** Annotations come from
  `aitask_explain_extract_raw_data.sh` (git log + blame; task id from a
  `(tN)` in the commit subject); the history screen reads
  `aitasks/archived/` plus git log (`codebrowser/history_data.py`, with an
  mtime fallback anchor for loose archived files).

## User decisions (asked during planning)

- Rename `aitasks_codebrowser_w_annotaitions_w_details.svg` →
  `aitasks_codebrowser_w_annotations_w_details.svg` (one page edit, old file
  removed).
- Delete the unreferenced `aitasks_settings_code_agent_default_models_tab.svg`.
- Stats dataset: completion dates are offsets back from the day the dataset is
  built — a documented exception to the fixed-dates rule.
- Everything in this child (no split).

## Steps

### Pre-phase (risk mitigations)

1. [probe_heavy_datasets] Before main step 1, implement the `codebrowser` and
   `stats` builders of step 2 and boot the real TUIs on them in a discovery
   session: `session start --dataset codebrowser`, `run ./ait codebrowser`,
   open the multi-task source file, read `screen` and a `shot --png` preview;
   press `d` (detail pane shows plan content) and `h` (history list shows the
   archived tasks with their fixed dates). `session start --dataset stats`,
   `run ./ait stats-tui`: the overview's daily chart and weekday pane are
   non-empty. Pass: annotations show 3+ distinct task ids on one file, no
   build-time date in the history list, both charts populated, no real
   name/path on screen. On failure, stop and report to the user (which view,
   what the screen showed) before recording any recipe on top.

### Main steps

1. **Repair-check all 13 recipes.** For the 12 non-sitrep scenes, look at each
   PNG of batch `20261120T070547Z-7c0c5c` against its page section, alt and
   caption and its `illustrates`. For `sitrep_window`, `replay --scene
   sitrep_window --png` again on the current tree (post-`514783b73`) and judge
   it against the current `website/content/docs/tuis/sitrep/_index.md` and
   `reference.md`: the image must show the tabbed list (one item kind per tab,
   with counts). A mismatch or failure → re-discover and `recipe save
   --replace` with an `illustrates` that describes the tabbed list (skill Step
   3; the `agents` dataset and setup may need more items so several tabs have
   content). If it still cannot be repaired, record the concrete blocker (what
   was tried, what the screen showed) in the report and in the plan notes; do
   not hold it out silently. Record each judgement.

2. **Datasets** (`website/screenshots/sample_project.py`; data builders only,
   real framework commands through `_framework()`, git through the pinned
   environment of `_git_commit_all`; invented names; ids that do not collide
   with the `base` tasks 7, 9, 11, 12, 14, 15):
   - **`settings`** = `agents` + the seed `models_codex.json` and
     `models_opencode.json` (so the Models tab and the agent-pick dialog list
     several agents) and the seed profiles (already in `agents`).
   - **`codebrowser`** = `base` + a small invented source tree
     (`src/checkout/cart.py`, `src/checkout/payment.py`, `src/catalog/prices.py`,
     a README …) built by a sequence of commits with fixed author/committer
     dates whose subjects carry task ids (`feature: Add cart totals (t3)`),
     so one file has several annotated line ranges from 3+ tasks; matching
     archived tasks `aitasks/archived/t<N>_*.md` (with `completed_at`, a child
     task under `archived/t<P>/`) and archived plans
     `aiplans/archived/p<N>_*.md`, committed in the same history so the
     history screen orders them by commit. Archived file mtimes are set to
     their fixed dates (`os.utime`) in case the mtime anchor is used.
   - **`stats`** = `base` + ~40 archived tasks spread over the last ~6 weeks
     before the build day (varied types, labels, a few children, weekday
     skew so the weekday pane is not flat). The docstring states the
     relative-date exception and why.
   Each gets build tests in `tests/test_screenshots_sample_project.py` (builds,
   expected files, no TUI import, no write outside the tree, and for `stats`
   that dates fall in the window relative to a patched build day) and a live
   check in `tests/test_screenshots_session_live.py` (`DatasetSceneTests`
   pattern) that the real TUI shows the data.

3. **Recipes, through the discovery loop** (explore, clean walk in a fresh
   session, `shot --png`, look at the PNG, `recipe save`). `output:` = the
   existing filename (except the rename). Every `home/*` scene uses one shared
   size so the home tiles keep one aspect; the TUI-page scenes use a size that
   fits their state without clipping (recorded per scene).
   - Board (`base`): `board_main_view` → `aitasks_board_main_view.svg`;
     `home_board` → `home/board.svg` (same route, own recipe);
     `board_task_detail` (Enter on a card, metadata fields visible);
     `board_customize_column` (column edit dialog: title input + palette);
     `board_commit` (commit dialog with a modified task file and pre-filled
     message — the modification made by a `setup` command such as
     `./ait update --batch …`); `home_child_tasks` → `home/child_tasks.svg`
     (parent expanded with children, like `board_child_tasks`).
   - Monitor (`agents`): `home_monitor` → `home/monitor.svg` (pane list with
     two stand-in agents and live preview; route from
     `monitor_layout_annotated`, no overlays).
   - Settings (`settings`): `home_settings` → `home/settings.svg` (Agent
     Defaults tab); `settings_select_model_step1` / `_step2` (the model
     picker's two steps); `settings_board_tab`; `settings_models_tab`;
     `settings_profiles_tab`.
   - Codebrowser (`codebrowser`): `codebrowser_main` (tree + code),
     `codebrowser_annotations` (gutter with several task ids),
     `codebrowser_annotations_details` (detail pane with plan content) →
     the renamed file, `codebrowser_task_history` (`h`), `home_codebrowser`
     → `home/codebrowser.svg` (annotated view, home size).
   - Stats (`stats`): `stats_overview` → `home/statistics.svg` (overview
     layout: summary, daily completions, weekday distribution).
   A scene that cannot be reached is reported with findings, nothing faked.

4. **Rename and delete.** The renamed scene's output
   (`aitasks_codebrowser_w_annotations_w_details.svg`) is absent at capture,
   so `preview` shows it as a new file with nothing beside it (it looks up
   the old image by the scene's `output` path). The comparison is therefore
   made explicitly: render the old typo-named SVG to PNG (the same
   `svg_export.render_png` path the tool uses), look at old and new together,
   and give both paths in the approval question (step 8). After `apply`,
   the shortcode edit and the old file's removal happen **only if** the
   output holds `APPLIED:codebrowser_annotations_details|…` — other scenes
   can apply while this one is refused. On `REFUSED:` for it, the page and
   the old SVG stay untouched (and the new file was not written), and the
   scene goes to a new capture and review. When applied: edit the one
   `static-img` src in `website/content/docs/tuis/codebrowser/_index.md`
   and `git rm` the old typo file. The unreferenced
   `aitasks_settings_code_agent_default_models_tab.svg` is removed
   independently of the batch.

5. **Docs of the tool.** `aidocs/framework/docs_screenshots.md` ("Current
   datasets" + the stats date exception), the SKILL.md dataset list (Step 2.2)
   and its dates rule, and any dataset list in `website/README.md`.

6. **One final batch.** `replay --scene …` over the 18 new recipes plus every
   repaired one (including `sitrep_window` if it was repaired),
   `--no-keep --png`; look at every PNG again.

   **Capture-source fingerprint (every candidate batch, including an
   accepted-subset re-batch in step 8).** Each scene's session copies
   `.aitask-scripts/` and `ait` from the working tree at its own start
   (`sample_project.write_project_shell`), so a commit or edit landing during
   a replay puts different code into different images. Immediately before and
   immediately after each candidate-batch replay, record the fingerprint of
   exactly what is copied, in the scratchpad:

   ```bash
   { git rev-parse HEAD; find ait .aitask-scripts -type f \
       -not -path '*/__pycache__/*' -print0 | sort -z | xargs -0 sha256sum; } \
     > <scratchpad>/src_<batch>_{before,after}.txt
   git status --porcelain -- ait .aitask-scripts \
     > <scratchpad>/dirty_<batch>_{before,after}.txt
   ```

   Both pairs are kept with the batch id. Equal fingerprints (and therefore
   equal dirty lists) → every scene in the batch ran the same source, and the
   **saved** HEAD + dirty list of that batch — never a later `git status` — is
   the source state the approval question discloses. Different → diff the
   two fingerprint files to name the changed paths, wait until the tree is
   stable (two equal fingerprints a moment apart), and replay the **full
   intended scene set** of that candidate (all of it, not only the affected
   scenes: a replay creates a new batch holding only the scenes it was given)
   into a fresh batch with a new before/after pair. The same holds when the
   intended set is a subset the user selected in step 8. A batch is offered
   for approval only with matching fingerprints.

7. **In-flight code check before review.** Take the candidate batch's
   **saved** dirty list (`dirty_<batch>_before.txt`, covering `ait` and
   `.aitask-scripts/`, equal to the `after` one by step 6) and map its paths
   to the TUIs in the batch (today: monitor family ← `monitor/*`,
   `lib/tmux_exec.py`, `lib/tmux_bootstrap.sh`, `lib/agent_launch_utils.py`,
   `lib/agent_restore.py`, `lib/agent_string.sh`). Name every intersecting
   scene in the approval question, so the user can decline those scenes.

8. **Review and apply** (skill Step 4, NON-SKIPPABLE): `git status --short --
   website/` (stop on pages edited by others that this batch touches — the
   codebrowser page is the only page edit); `preview --batch`; the "Apply"
   question (with the old/new rename paths from step 4 and the step 7 list).
   **`apply --batch` has no scene selector and applies every staged scene**,
   so approval is all-or-nothing per batch: if the user declines any scene
   (an in-flight-code scene from step 7, or an image they reject), do NOT
   apply that batch. Replay exactly the accepted subset into a fresh batch
   (`replay --scene <accepted>… --no-keep --png`, with the before/after
   fingerprint of step 6 and its recapture rule), look at its PNGs, run
   `preview` on it, and ask the "Apply" question again for that exact batch
   id. Only a batch approved as a whole is applied. Then step 4's conditional
   page edit and removals.

## Verification

- `python3 website/check_screenshots.py --owners`: no `hand-made` image except
  the logos (`aitasks_logo_dark_theme.png`, `logo_*.webp`).
- `python3 website/check_screenshots.py --strict` exits 0.
- The applied batch has equal before/after source fingerprints, and the
  approval question named its source state from the files saved with that
  batch (HEAD + dirty paths of `ait` and `.aitask-scripts/`); a replacement
  batch holds the full intended scene set.
- The applied batch is the exact batch id the user approved as a whole; the
  codebrowser page names the renamed file only if its scene printed
  `APPLIED:`, and the typo-named file is gone only in that case.
- `sitrep_window`'s image shows the tabbed list the current sitrep page
  describes (or its blocker is recorded).
- `website/screenshots.sh replay --all --no-keep` passes (31 recipes).
- `cd website && python3 check_links.py --build` passes.
- `bash tests/run_all_python_tests.sh --test-dir tests` — last line `PASSED`.
- Home page and each TUI page viewed on the local Hugo server (`./serve.sh`);
  home tiles checked for layout with the new aspect.
- `website/screenshots.sh session list` is empty.

## Risk

### Code-health risk: low
- Three new dataset builders run git and real framework commands, so a CLI change can break a build · severity: low · → mitigation: none — build tests and live checks (step 2)
- One page edit and two file deletions in `website/` · severity: low · → mitigation: none — `check_screenshots.py --strict` and `check_links.py --build`

### Goal-achievement risk: medium
- The `codebrowser` / `stats` datasets may not render realistically (explain annotations over a synthetic history, history list falling back to build-time mtimes, empty charts) · severity: medium · → mitigation: inline pre-phase probe_heavy_datasets
- Captures show other sessions' uncommitted framework code (monitor, tmux gateway) · severity: medium · → mitigation: none — step 7 names the intersection in the approval question
- New home-tile images change aspect ratio and may shift the home page layout · severity: low · → mitigation: none — one shared home size, viewed on the Hugo server
- The stats image depends on the capture day (relative dates, user decision) · severity: low · → mitigation: none — documented exception; apply copies exactly the reviewed batch

### Planned mitigations
- timing: pre-phase | name: probe_heavy_datasets | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: codebrowser/stats datasets may not render realistically | desc: build the two datasets first and boot the real TUIs on them; stop and report on failure

## Notes for sibling tasks

Record: every recipe repaired in step 1 and why; every scene size and why;
datasets added; the stats relative-date exception; the outcome of the
`sitrep_window` repair against the tabbed redesign (or its concrete blocker);
any scene declined at review and the re-batch (child 8 reads it).

Post-implementation: Step 9 of the task workflow.

## Implementation log

- **Pre-phase probe_heavy_datasets: PASS (2026-11-21).** `codebrowser`:
  `./ait codebrowser --focus src/checkout/cart.py` (the real launch flag) opens
  cart.py with gutter ids t3, t5_2, t6 (t4 further down); `d` shows "Plan for
  t3" with the archived plan; `h` lists 9 completed tasks with their fixed
  commit dates (2026-01-12 .. 2026-02-23), t5 shown `[no-code]` with
  `[+2 children]`; selecting t6 shows its commit, affected file and context.
  The "Annotations: <time>" stamp is a live clock. `stats`: overview layout,
  Summary 66 total / 10 last 7 days / 46 last 30 days; Daily completions chart
  populated over the 30 days before the build day.
- **Step 1 done.** 12 recipes judged from batch `20261120T070547Z-7c0c5c`
  PNGs: all still match their pages (no repair). `sitrep_window` replayed on
  the post-`514783b73` tree (STAGED): the TUI now shows the tab bar
  `All 4 | Triage 1 | Tasks 2 | Recovery 0 | Watches 1` with the All tab
  (reference.md: All is a tab, the default), which matches the page and alt.
  Its `illustrates` / `expect` still described the old list, so it was
  re-recorded with a clean walk on the same route and `recipe save --replace`
  (expect now pins the tab counts). Image content unchanged in kind.
- **Step 2 done.** Datasets `settings`, `codebrowser`, `stats`
  (`sample_project.py`); build tests in `test_screenshots_sample_project.py`
  (13 new; negative control: without the archived-file mtime pin
  `test_dates_are_fixed` fails), live checks in `DatasetSceneTests` (4 new).
  `settings` carries the seed's per-operation defaults (not the stand-in
  routing of `agents`): the Agent Defaults tab is about them, and settings
  launches no agent. `stats` spread widened after the first image showed an
  unnaturally regular weekly curve.
- **Step 3 done.** 19 recipes (the inventory is 19 images, not 18):
  board_main_view, home_board, board_task_detail, board_customize_column,
  board_commit, home_child_tasks, home_monitor, home_settings,
  settings_select_model_step1/2, settings_board_tab, settings_models_tab,
  settings_profiles_tab, codebrowser_main, codebrowser_annotations,
  codebrowser_annotations_details (renamed output), codebrowser_task_history,
  home_codebrowser, stats_overview.
  Sizes: home/* 160x40 (one aspect for the tiles); board 126x44 (task detail
  140x44: at 126 its Type row and last button are clipped); codebrowser
  160x44; settings 120x44 (Board tab 120x24, Models tab 120x64 so the second
  agent's section is in view); sitrep unchanged 140x42.
  Refused saves fixed by proving focus with a text before the next key:
  board_commit (Right/Down sent together raced the board's focus → one key per
  wait on the focused card's `║` border); settings picker (Down/Enter raced →
  `b`, wait, `a`, wait: `_switch_to_tab` focuses the first row after the
  refresh the wait proves); codebrowser history (Left/Down raced the list →
  `H` on a t6 line of cart.py, which opens history at that task).
- **User decision (step 3, settings picker):** the picker no longer has a
  "Step 1 agent / Step 2 model + layer" flow (one list at a time,
  Shift+Left/Right; Enter saves to the layer of the row it was opened on,
  `settings_app.py:2504-2510`). User: two new states, keep the filenames,
  rewrite both alt/captions, and update the how-to "Change the Default Model
  for an Operation". Done in `settings/_index.md` and `settings/how-to.md`.
- **Step 5 done.** `aidocs/framework/docs_screenshots.md` (datasets, stats
  exception), skill Step 2.2 dataset list and the dates rule.
- **Steps 6-8 done.** First candidate batch `20261121T211448Z-c6b2ad`
  (fingerprints equal) failed `board_customize_column` at its Enter (the
  manage-columns list was not yet focused) → re-recorded with a wait on the
  focused row's outline (`█   1. ██ Now`); then the FULL intended set
  replayed into `20261121T211720Z-b29857`: 20/20 staged, before/after
  fingerprints and dirty lists equal (HEAD 9da106b5; dirty, other sessions:
  `aitask_opencode_models.sh`, `lib/agent_string.sh`, `lib/atomic_write.sh`,
  named in the approval question as touching board_commit, home_monitor,
  sitrep_window and possibly settings). Every PNG looked at; old typo image
  rendered and given beside the new one. User: "Apply". `apply`: 20 APPLIED,
  0 refused. `codebrowser_annotations_details` APPLIED → codebrowser page src
  renamed and the typo file removed; the unreferenced settings image removed.
  `check_screenshots.py --strict` PASSED, `--owners` lists only the three
  logos as hand-made; `check_links.py --build` PASSED.
- **Verification done.** `bash tests/run_all_python_tests.sh --test-dir tests`
  → `PYTHON SUITE: PASSED`; `website/screenshots.sh replay --all --no-keep`
  → 32/32 staged (batch `20261122T085357Z-bd0b65`), `session list` empty;
  home page and settings page viewed through a local `hugo server` in
  headless Chromium (home tiles share one aspect; new captions render).

## Final Implementation Notes
- **Actual work done:**
  - `website/screenshots/sample_project.py`: datasets `settings`,
    `codebrowser` (with `ArchivedTask`, `_git`, `_git_env`, `_git_date`,
    `_set_mtime`, `CODEBROWSER_HISTORY`), `stats` (`_today`, `_stats_tasks`).
  - 19 new recipes under `website/screenshots/scenes/`; `sitrep_window`
    re-recorded (`--replace`) for the item-type tab redesign.
  - 20 images applied from batch `20261121T211720Z-b29857`;
    `aitasks_codebrowser_w_annotaitions_w_details.svg` renamed to
    `..._annotations_w_details.svg` (page src updated);
    `aitasks_settings_code_agent_default_models_tab.svg` deleted.
  - Docs: settings `_index.md` (picker alt/captions), settings `how-to.md`
    ("Change the Default Model for an Operation"), codebrowser `_index.md`
    (src), `aidocs/framework/docs_screenshots.md`, the skill's dataset list
    and dates rule.
  - Tests: `test_screenshots_sample_project.py` (Settings/Codebrowser/Stats
    dataset classes), `test_screenshots_session_live.py` (4 live checks).
- **Deviations from plan:**
  - 19 images, not 18 (the task's count was off by one).
  - The two picker images now show two picker lists instead of a two-step
    flow the TUI no longer has, with new captions and a rewritten how-to
    (user decision).
  - `settings` uses the seed's per-operation defaults instead of the
    stand-in routing.
  - `sitrep_window` was in scope (its redesign landed during planning).
- **Issues encountered:** keys sent before a widget holds focus are
  dropped on replay; plain screen text does not show focus. Each fix found
  a text that proves focus (focused card's `║` border, picker row outline
  `█   1.`) or a route that sets focus itself (`_switch_to_tab` after
  `b`/`a`; `H` from the code viewer instead of list navigation). Settings'
  Models tab has no focusable widget, so it cannot be scrolled with keys;
  a taller pane (120x64) shows the second agent's section instead.
- **Key decisions:** one shared home size (160x40); recipes never rely on
  two keys in one `keys` step where the first changes focus; stats dates
  relative to the build day (documented exception).
- **Upstream defects identified:**
  - `.aitask-scripts/codebrowser/history_list.py:470-489 — the "Recently Opened (N)" header is recomputed only in _update_headers (index load / label filter), so opening a task adds it to the recent list while the header still reads "Recently Opened (0)"`
- **Notes for sibling tasks:**
  - Child 7 (real pixels) and child 8 (retrospective): every image on the
    site except the three logos now has a recipe (32 recipes).
  - Recipes repaired in step 1: only `sitrep_window` (illustrates/expect
    stale after t2334's tab redesign; image itself still matched).
  - Primitive still missing (again): a focus indicator in `screen` output;
    four of the refused saves in this child were focus races.
  - Sizes: home/* 160x40; board 126x44 (detail 140x44); codebrowser
    160x44; settings 120x44 (Board 120x24, Models 120x64); stats 160x40.
  - The capture source fingerprint + saved dirty list per candidate batch
    (plan step 6) worked; the user's review question named the in-flight
    paths and the scenes they touch.
