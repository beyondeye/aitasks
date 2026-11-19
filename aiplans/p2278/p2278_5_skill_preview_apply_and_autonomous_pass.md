---
Task: t2278_5_skill_preview_apply_and_autonomous_pass.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/fable5_2 @ 2026-11-19 05:30
---

# Plan: t2278_5: skill, preview/apply and the autonomous pass

## Context

Child 5 of t2278 (docs TUI screenshot generator). Children 1-4 shipped the
marker grammar and checker, the isolated-tmux session primitives, recipes and
replay, crop/overlays, and multi-pane stitching (`website/screenshots/`). What
is missing: a way to turn a reviewed batch into images plus `static-img`
shortcodes on the pages (`preview`, `apply`), the Claude-only skill that runs
the discovery and repair loops, the datasets the remaining scenes need,
contributor docs, and the actual pass that resolves all 17 markers.

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` ("Roles",
"Sample state: the setup contract", "Which journal becomes a recipe", "Recipe
lifecycle"). Sibling notes used: child 2 (manifest schema, journal, verbs),
child 3 (rectangle contract, `PNG_UNAVAILABLE:` → look at the SVG), child 4
(pane/window verbs, stand-in agent, the launch-dialog race: wait for
`Pick Task tN`, `(R)un in tmux` and `lumen` before `r`).

## Verification of the existing plan (2026-11-18)

Checked against the tree at `4bcd5f403`:

- `cli.py` has every verb the plan relies on; no `preview` / `apply` yet. The
  manifest (`stage()`, cli.py:118) records per scene `id`, `output`, `sha256`,
  `destination` (`"absent"` | `{sha256}`) and `markers: [{page, text}]`, where
  `page` is relative to `website/content/` and `text` is the marker's full
  source line (`Marker.text`). Failed replays are in `failed: [{id, reason}]`.
- `markers.render_static_img(marker)` raises `ValueError` on a forbidden value
  (t2278_1 note) — apply turns that into a refusal.
- 7 recipes exist (`ait_ide_startup`, `board_card_annotated`,
  `board_child_tasks`, `board_layout_annotated`, `minimonitor_main_view`,
  `monitor_layout_annotated`, `sitrep_window`). 6 scenes still have no recipe:
  `board_task_detail_lock`, `trails_main_view`, `brainstorm_browse_tab`,
  `tui_switcher_dialog`, `tui_switcher_from_monitor`,
  `tui_switcher_from_minimonitor`. 17 markers, all unresolved.
- t2320 landed (`d6e8d1a54`): `tui_registry.py` registers diffviewer with
  `in_switcher=False`, so the three switcher scenes can now be recorded
  (t2278_4 held two of them back for exactly this).
- `git status -- website/` is clean today; the skill re-checks before apply.
- `.claude/settings.local.json` is tracked; it already holds
  `Bash(./.aitask-scripts/aitask_screen_recording.sh:*)`, the pattern to copy.
- `MISSING_SCENE_SEVERITY = "warning"` (`website/check_screenshots.py:52`);
  `tests/test_check_screenshots.py::test_missing_scene_severity_error_fails`
  already covers the "error" path; the test(s) asserting the warning default
  are updated with the flip.
- "Two captures produce two batches" is already covered by
  `test_screenshots_session_live.py::test_a_second_shot_of_a_scene_never_replaces_the_first`;
  no new test needed for it beyond apply's batch binding.
- A static Claude-only skill needs no registration (cf.
  `.claude/skills/aitask-screen-recording/`); `aitask_skill_verify.sh` only
  checks `.j2` surfaces.
- The `agents` dataset already contains `add_local_origin()`;
  `board_locks` reuses it. Trails are `ait artifact` records
  (`kind: implementation_trail`, local backend, no remote needed) and a
  brainstorm session is a crew worktree `.aitask-crews/crew-brainstorm-<N>/`
  whose `init` starts no agent without `--proposal-file` — both buildable from
  data plus real framework commands.

Changes to the plan from this verification: refusal reasons extended
(`image_missing`, `destination_removed`, `marker_invalid`,
`marker_mismatch`, `write_failed`), batch-id validation, per-scene
revalidation of image and destination right before writing, scene-level
all-or-nothing writes with rollback, a real visual check (never screen text)
when no PNG can be rendered, and
concrete dataset designs (below).

## Steps

### Pre-phase (risk mitigations)

1. [probe_new_datasets] Before steps 1-3 and 5, implement the `trails` and
   `brainstorm` builders of step 4 and boot the real TUIs on them in a
   discovery session (`session start --dataset trails`, `run ./ait trails`;
   `--dataset brainstorm`, `run ./ait brainstorm <id>`), reading `screen`
   and a `shot --png` preview. Pass: trails lists the invented trail and its
   waves show local member cards (not ghost cards); brainstorm's Browse tab
   shows the multi-node graph and a detail pane; no build-time date on
   screen. On failure, stop and report to the user (which command refused,
   what the screen showed) before building anything on top of it.

### Main steps

1. **`preview --batch <id>`** (`website/screenshots/cli.py`, new
   `cmd_preview`). Resolve the batch with `_batch_dir(paths, id)`: the id must
   match `^[A-Za-z0-9T_-]+$`, exist under `paths.staging`, and hold
   `manifest.json` (else `REFUSED:batch …`, exit 1). Read the manifest only.
   Write `<batch>/preview.html` (stdlib `html.escape` on every value): heading
   = batch id and `created_at`; per scene the image (`<img src="<output>">`,
   relative), the output path, the destination state ("new file" /
   "replaces existing"), the existing image beside it when replacing
   (`file://` path to `website/static/imgs/<output>`), each marker's page,
   alt and caption (parsed from the recorded text with
   `markers.parse_marker`; an unparseable text is shown raw and flagged), and
   a "no markers — image only" line for a marker-less scene; then the
   `failed` entries. Print `PREVIEW:<path>` and the `--png` previews if they
   exist (`_preview/<scene>.png`). No side effects beyond that one file.

2. **`apply --batch <id>`** (`cmd_apply`). `--batch` is required (argparse
   `required=True`; no "latest"). Two phases:
   - **Validate every scene** → verdict list. Per scene, in order, first
     failure wins:
     - staged image `<batch>/<output>` missing → `image_missing`;
       SHA-256 ≠ manifest → `image_changed`;
     - destination `paths.static/imgs/<output>`: manifest `"absent"` but the
       file exists → `destination_created`; manifest `{sha256}` but the file is
       gone → `destination_removed`; hash differs → `destination_modified`;
     - per marker: page file missing or its text occurs 0 times →
       `marker_missing:<page>`; >1 → `marker_ambiguous:<page>` (located by
       text, never line number; `str.count` on the page text);
       `parse_marker(text)` not a `Marker` → `marker_invalid:<page>`; parsed
       `scene`/`file` ≠ manifest `id`/`output` → `marker_mismatch:<page>`;
       `render_static_img` raises `ValueError` → `marker_invalid:<page>`.
   - **Write passing scenes**, one scene at a time, each as one
     all-or-nothing unit (`_apply_scene`):
     1. *Revalidate, immediately before this scene's writes* — the phase-one
        verdict is advisory only. Read the staged image bytes ONCE, hash those
        bytes against the manifest (`image_changed` / `image_missing`), and
        re-check the destination state against the manifest
        (`destination_created` / `_modified` / `_removed`). The bytes that
        were hashed are the bytes written; the staged file is never re-read.
     2. Read each page now, re-check its marker count is exactly 1, and
        compute every new page text in memory
        (`text.replace(marker_text, shortcode, 1)`), remembering each page's
        original bytes (and the destination's original bytes, or "absent").
     3. *Prepare* every output before the first replacement: write the image
        and each page to a temp file beside its target (`mkdir -p` parents).
        A failure here removes the temps; nothing was replaced →
        `REFUSED:<scene>|write_failed:<path>`.
     4. *Commit*: `os.replace` each temp onto its target (image first, then
        pages). If any replacement fails, **roll back** every target already
        replaced from the remembered originals (rewrite atomically; delete an
        image that was absent, and directories this scene created), remove
        the remaining temps, and report
        `REFUSED:<scene>|write_failed:<path>`. Only if the rollback itself
        fails: `PARTIAL:<scene>|<paths left changed>` (loud, exit 1) so the
        user knows exactly which files to restore from git.
     Pages are read at write time, so edits made elsewhere in a page during
     review survive. Several scenes touching one page are applied
     sequentially on the current file content. Residual, documented window:
     between step 2's read and step 4's replace of the same page (no file
     locking in a git checkout).
   - A scene with no markers (child 6's regeneration case) applies the image
     only.
   - Output: `APPLIED:<scene>|<output>|pages=<n>` or
     `REFUSED:<scene>|<reason>` (or `PARTIAL:`) per scene, then
     `APPLY:applied=<n> refused=<m> batch=<id>`. Exit 1 when any scene was
     refused. Failed (unstaged) entries of the manifest are listed as
     `SKIPPED:<scene>|not staged (<reason>)` and do not change the exit.
   - Docstring and `--help` updated with both verbs.

3. **Tests: `tests/test_screenshots_apply.py`** (new, no tmux, so not in the
   serial carve-out). Scratch `content/`, `static/`, `staging/` trees and
   hand-written manifests (a helper builds a batch: image + manifest whose
   markers come from `markers.scan` of the scratch content, exactly as
   `stage()` records them). Cases, each asserting the refused scene's image
   destination and every page are byte-identical afterwards:
   - staged image changed after capture → `image_changed`; staged image
     deleted → `image_missing`;
   - destination created after capture → `destination_created`; modified →
     `destination_modified`; removed → `destination_removed`;
   - marker edited after capture → `marker_missing`; marker duplicated →
     `marker_ambiguous`; a hand-built recorded text with a forbidden value →
     `marker_invalid` (no crash);
   - mixed batch: one scene applies, the other is refused, exit 1, the
     applied one's image and shortcode are in place;
   - an unrelated edit elsewhere in the same page made after capture
     survives a successful apply; the shortcode equals
     `render_static_img(parse_marker(text))`;
   - two scenes on one page both apply;
   - **change between validation and writing** (deterministic, through the
     `_apply_scene` seam): a two-scene batch where a wrapper around scene A's
     apply (a) modifies scene B's destination → B is
     `destination_modified`, the newer image is kept, B's pages untouched;
     (b) rewrites scene B's staged image → `image_changed`, nothing copied.
     Control: without the interference both apply;
   - **injected later-page write failure**: a scene with three pages, the
     replace helper patched to raise on the second page → `REFUSED:
     …|write_failed`, exit 1, and the image destination (absent, and in a
     second variant an existing file) and all three pages are byte-identical
     to before, no temp files left; a failing rollback reports `PARTIAL:`
     naming the changed paths;
   - a marker-less scene copies only the image;
   - `apply` without `--batch` → argparse exit 2; an unknown or
     path-traversing batch id → `REFUSED`, nothing written;
   - apply touches only the named batch (a second batch with a different
     image of the same scene is ignored);
   - `preview` writes one `preview.html` naming the batch id, each image and
     each marker's page, alt and caption, and writes nothing else.

4. **Datasets** (`website/screenshots/sample_project.py`), added as the
   scenes of step 7 need them, each a data builder (files, a local bare
   remote, real framework commands run in the temp tree; never imports or
   patches TUI code):
   - **`board_locks`** = `base` + `add_local_origin()` (already in the
     module). `./ait lock` needs an `origin` (`--init` exits 10 without one;
     lock/unlock are silent no-ops in single-user mode). The recipe's
     `setup` then runs the real `./ait lock --init` and
     `./ait lock <id> --email <sample person>`; the lock lands on the local
     bare `aitask-locks` branch and the board reads it on refresh.
   - **`trails`** = `base` + one invented trail stored through the real
     artifact path: the builder writes a schema-1.1.0 trail JSON (shape from
     `tests/test_trail_links.py::_trail_doc` and
     `aidocs/implementation_trail_examples/`; refs `lumen#<id>` so members are
     local cards — `project.name` in `project_config.yaml` must be `lumen`;
     2-3 waves over the base tasks; every timestamp pinned, no current date),
     validates it with `.aitask-scripts/lib/trail_schema.py validate`, commits
     the tasks (`create` refuses a dirty owner), and runs
     `./ait artifact create <owner> <file> --kind implementation_trail
     --handle art:trail-<slug> --name "<label>"` (local backend, no remote).
     The trail document lives outside the task tree (in `.standin/`) so it is
     not project content.
   - **`brainstorm`** = `base` + the code-agent config with the four
     `brainstorm-*` defaults (from `seed/codeagent_config.json`, every op
     routed to the stand-in as `write_agent_metadata` does) + `userconfig.yaml`
     email; then the real `./ait brainstorm init <id>` (no `--proposal-file`,
     so no agent starts) on a base task without children, then 3-4 more nodes
     through the real apply path: write `explorer_00Na_output.md`
     (`NODE_YAML` / `PROPOSAL` blocks) into the crew worktree and run
     `./ait brainstorm apply-explorer <id> explorer_00Na`, one of them a
     two-parent node if the apply path accepts it. If a build-time date
     reaches the screen (node `created_at` in the detail pane), the builder
     rewrites those fields to a pinned date afterwards and says so in its
     docstring. Builder subprocesses use the same pinned git environment as
     `add_local_origin` / `_git_commit_all`, and `AIT_PYTHON`.
   Each gets a build test in `tests/test_screenshots_sample_project.py`
   (builds, expected files present, no TUI import) and a live check in
   `tests/test_screenshots_session_live.py` (already in the serial
   carve-out) that the real TUI shows its data. If a dataset cannot be built
   from data and real framework commands, stop and report the scene to the
   user; never fake the screen.

5. **Skill: `.claude/skills/aitask-docs-screenshots/SKILL.md`** (new, static,
   no `.j2`, Claude-only). Frontmatter `name` / `description`. Sections:
   - **Purpose / when to use**, and step 0: stop at once with a one-line
     message when `website/screenshots/` (or `website/screenshots.sh`) is
     absent — the skill ships in every project's tarball, the tool does not.
   - **Arguments:** `[--scenes DIR] [<scene>...]` — default scope is every
     marker in `website/content/` and every recipe; scene ids narrow it;
     `--scenes` is passed through as the tool's global flag (used by the
     acceptance scenarios).
   - **Contracts the agent must respect:** state = named dataset + `setup`
     commands, nothing else (no edits in the temp tree, no other shells);
     two passes (explore in one session, then a fresh `session start` and a
     clean walk, `shot`, `recipe save`); a replay-origin (kept) session is
     for inspection only; a repair keeps `id`/`output`; invented names only
     (project `lumen`); never `sleep` — always `wait`. **Visual check:** an image
     counts as verified only when the agent has LOOKED at the rendered image
     (the `--png` preview, read as an image). Screen text proves the state,
     never the picture (crop, overlays, spacing, pane composition). On
     `PNG_UNAVAILABLE:` the agent opens the staged SVG itself in a browser
     (the batch's `preview.html` through the Chrome tools, when available)
     and inspects that; if no rendering path exists, the scene is listed as
     "visual verification pending" in the report AND in the approval
     question, with the `preview.html` path, so the user checks it before
     approving. It is never reported as verified from text.
   - **Inventory:** `python3 website/check_screenshots.py --report` and
     `website/screenshots.sh list`, to split markers into "no recipe" and
     "has a recipe".
   - **Discovery loop** (per marker scene without a recipe): read the page
     section around the marker plus its alt and caption; decide the state
     that illustrates it; pick or add a dataset (adding one is a code change
     with a build test — say so to the user); `session start --size --dataset
     [--window]`, `setup`, `run`, then `screen` / `keys` / `wait` / `find`;
     verify the state on screen; `shot --png` and look at the PNG; then a
     fresh session, the clean walk, `shot`, and `recipe save --scene
     --expect … --illustrates …` (expect = texts that prove the state;
     illustrates = intent from page + alt + caption). Recipe-save refusal →
     fix the walk, never the recipe file.
   - **Repair loop** (per existing recipe in scope): `replay --scene <id>
     --png`; on `FAILED:` inspect the kept `SESSION:` (screen, keys) to learn
     what changed, `session stop` it; on a pass, compare the staged image
     (PNG + `screen` text) with the page section and the marker / existing
     `static-img` alt and caption. Failure or mismatch → re-discover in a fresh
     session and `recipe save --replace`. No route found (feature gone, state
     unreachable) → change nothing, record the scene and what was found for
     the report. Never hand-edit a recipe.
   - **Review and apply:** collect one batch for review (if the run produced
     several, re-run `replay --scene …` for every scene to be applied so they
     land in ONE batch, and review that); `preview --batch <id>`; show the
     user the path and a per-scene summary; `AskUserQuestion`
     "Apply batch <id>?" — "Apply" / "Don't apply" (+ Other for per-scene
     notes). Before apply: `git status --short -- website/` and stop on
     another task's in-flight page edits. `apply --batch <id>` with exactly
     the reviewed id; report every `REFUSED:` (it needs a new capture and a
     new review — a capture made after the review is reviewed again before
     apply). Then `cd website && python3 check_links.py --build` and
     `python3 check_screenshots.py`.
   - **End:** report (scenes captured, repaired, unrepairable with findings,
     refused), never commit, always `website/screenshots.sh session stop
     --all` — also on an early stop.
   Run `./.aitask-scripts/aitask_skill_verify.sh`.

6. **Repair acceptance, by running the skill** (follow its SKILL.md
   literally, in a scratch scenes dir `--scenes <scratchpad>/scenes`):
   - Scenario 1: copy `board_child_tasks.yaml`, change one `keys` step to a
     wrong key and one `expect` to a stale text (the state still exists).
     Pass only if it ends with a replaced recipe in the scratch dir that
     replays in a fresh session and whose image shows the destination text.
     "Could not repair" = fix the skill text or the primitives and rerun.
   - Scenario 2: a recipe whose `illustrates` / `expect` name a state the
     sample project cannot reach (e.g. a board column the project does not
     have). Pass only if the run reports the scene with its findings, the
     recipe's `sha256sum` is unchanged, and the batch stages nothing for it.
   - Answer "Don't apply" in both. Record both outcomes in the Final
     Implementation Notes.

7. **Run the pass** on the real tree: `git status --short -- website/` first
   (stop on in-flight pages). Discovery for the 6 scenes without a recipe
   (`board_task_detail_lock`, `trails_main_view`, `brainstorm_browse_tab`,
   `tui_switcher_dialog`, `tui_switcher_from_monitor`,
   `tui_switcher_from_minimonitor`), then the repair loop over the 7 existing
   recipes, then one batch, `preview`, user review, `apply --batch`, both
   checks. Then set `MISSING_SCENE_SEVERITY = "error"` (and its comment) in
   `website/check_screenshots.py`, update the default-severity test, and
   confirm `python3 website/check_screenshots.py --strict` exits 0. View each
   image on `cd website && ./serve.sh`.

8. **Permissions.** Add `Bash(website/screenshots.sh:*)` and
   `Bash(./website/screenshots.sh:*)` to `.claude/settings.local.json`
   (repo only, not `seed/`). Run `bash tests/test_helper_whitelist_coverage.sh`
   and `bash tests/test_release_tarball.sh`.

9. **Docs.**
   - `aidocs/framework/docs_screenshots.md` (new): design and contract record
     — marker grammar and ownership rule, recipe schema pointer
     (`recipe.py` docstring), setup contract, journal rule (two passes),
     recipe lifecycle (record / replay / repair), batch and manifest, apply
     rules and refusal reasons, isolation rules, the stand-in agent, file map.
   - `CLAUDE.md`: in the Website section one line
     (`website/screenshots.sh` + `check_screenshots.py`), plus a
     "Read `aidocs/framework/docs_screenshots.md` when …" pointer.
   - `website/README.md`: a "Generating screenshots" section after "Screenshot
     Markers": the skill, the verbs, preview/apply, the staging directory.
   - `website/content/docs/development/skills/aitask-docs-screenshots.md`
     (new) and a row in that section's `_index.md` "Pure
     framework-development skills" table. Follow the doc guide
     (`aitasks/metadata/doc_update_guide.md`, current-state-only prose).
   - `cd website && python3 check_links.py --build`.

10. **Port tasks.** Suggest (on the user's yes, create) tasks to port the
    skill to Codex CLI and OpenCode.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests` — last line `PASSED`.
- `python3 -m pytest tests/test_screenshots_apply.py` focused run first.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- `bash tests/test_helper_whitelist_coverage.sh`, `bash tests/test_release_tarball.sh`.
- Both repair scenarios ended in their one passing outcome.
- `python3 website/check_screenshots.py --strict` exits 0.
- `cd website && python3 check_links.py --build`.
- `website/screenshots.sh session list` is empty.
- Every generated image viewed on the local Hugo server.

## Risk

### Code-health risk: low
- `apply` writes doc pages and images in a shared checkout · severity: low · → mitigation: none — bound to one reviewed batch, marker-text-only substitution, per-scene revalidation before writing, prepare-then-commit with rollback, tests for each refusal, the validation-to-write race and an injected write failure (step 3)
- Dataset builders call real framework commands (`ait artifact create`, `ait brainstorm init` / `apply-explorer`, `ait lock`), so a CLI change can break a build · severity: low · → mitigation: none — each dataset has a build test and a live check (step 4)
- `.claude/settings.local.json` is a tracked shared file · severity: low · → mitigation: none — one additive allow entry, committed by path

### Goal-achievement risk: medium
- The `trails` / `brainstorm` datasets may not produce a realistic screen (ghost cards from a project-name mismatch, `apply-explorer` refusing hand-written output, build-time dates on screen) · severity: medium · → mitigation: inline pre-phase probe_new_datasets
- Repair scenario 1 depends on the agent following the skill to a successful repair · severity: medium · → mitigation: none — step 6 treats "could not repair" as a failure that sends us back to the skill text or primitives
- The board lock status sits in the collapsed "Lock & files" section of the detail dialog, so the route must expand it · severity: low · → mitigation: none — found during discovery
- One review covers ~13 images; rejected images extend the session · severity: low · → mitigation: none — refused / rejected scenes are re-captured and re-reviewed

### Planned mitigations
- timing: pre-phase | name: probe_new_datasets | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: trails/brainstorm datasets may not render realistically | desc: build the two datasets first and boot the real TUIs on them; stop and report on failure

## Notes for sibling tasks

Record: the batch id applied; every `REFUSED:` and its cause; every recipe
repaired and why; primitives the agent missed; the user's comments on realism
and choice of state (child 8 reads them).

Post-implementation: Step 9 of the task workflow.
