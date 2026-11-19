---
name: aitask-docs-screenshots
description: Generate and repair the website's TUI screenshots — for each screenshot marker in the docs, drive the real TUI on a sample project in an isolated tmux session to the state the page describes, capture it, record the route as a replayable recipe, repair recipes that fail or no longer match their page, then preview the batch for the user and apply the approved one. Use when a docs page carries a `<!-- screenshot: ... -->` marker, when a TUI changed and its screenshots need refreshing, or when asked to (re)generate documentation screenshots. Framework-development skill for the aitasks repository itself.
---

## Step 0: Is the tool here?

```bash
test -x website/screenshots.sh && test -d website/screenshots && echo TOOL_PRESENT
```

If this does not print `TOOL_PRESENT`, say "The docs screenshot tool
(`website/screenshots/`) is not part of this project; this skill only works in
the aitasks repository." and **stop**. Do nothing else. (The skill ships with
every project; the tool does not.)

## What this skill does

Documentation pages mark where a screenshot belongs with one line:

```
<!-- screenshot: scene=board_child_tasks file=aitasks_board_child_tasks.svg alt="..." caption="..." -->
```

You produce the image for each marker by **driving the real TUI**: start an
isolated tmux session on a sample project, launch the TUI, read the screen,
press keys, and capture the state the page describes. A capture that worked is
recorded as a **recipe** (`website/screenshots/scenes/<scene>.yaml`) so it can
be replayed later. A recipe that fails, or that passes but no longer shows
what its page describes, is **repaired** by finding the route again. The user
then reviews one batch of images, and only that batch is applied to the site.

Two loops, then review:

1. **Discovery** — every marker whose scene has no recipe.
2. **Repair** — every existing recipe in scope.
3. **Review and apply** — one batch, previewed, approved by the user.

The design and contract record is `aidocs/framework/docs_screenshots.md`. Read
it when a rule below is unclear.

## Invocation

```
/aitask-docs-screenshots [--scenes <dir>] [<scene>...]
```

- No arguments: every marker under `website/content/` and every recipe.
- `<scene>...`: only these scene ids (both loops are limited to them).
- `--scenes <dir>`: read and write recipes in `<dir>` instead of
  `website/screenshots/scenes/`. Pass it to **every** tool call as the global
  flag, before the verb: `website/screenshots.sh --scenes <dir> <verb> ...`.

All tool calls go through `website/screenshots.sh` from the repository root.
`website/screenshots.sh --help` lists the verbs. Result lines are `KEY:value`;
exit status 1 means a failure or a refusal, and the line says which.

## Rules that hold in every step

- **State is a dataset plus setup commands, and nothing else.** A recipe's
  starting state is the named dataset (`session start --dataset <name>`, built
  by `website/screenshots/sample_project.py`) plus the commands you ran with
  the `setup` verb. Never edit a file in the session's temp project, and never
  prepare data from another shell: a replay cannot repeat that, and
  `recipe save` will refuse the result. `setup` only works before `run`.
- **Two passes.** Explore in one session until you know the route. Then start
  a **fresh** session and walk the route once, with no wrong keys and no
  failed waits, take the shot and save the recipe. A session with a failed
  step cannot be saved.
- **A kept replay session is for inspection only.** When `replay` fails it
  leaves the session open and prints `SESSION:<id>`. Look at its screen and
  press keys there to learn what changed. Nothing done in it can be saved.
  Stop it when you have learned what you need.
- **Never edit a recipe file by hand.** A recipe is replaced by
  `recipe save --replace` from a clean walk, or not at all. A repair keeps the
  recipe's `id` and `output`.
- **Never `sleep`.** Use `wait --text` / `wait --gone`; a wait that times out
  prints the screen.
- **Invented names only, fixed sample dates.** The sample project is `lumen`.
  If a screen shows a real project name, the machine's real host name or a
  real path under the user's home, the state is wrong; fix the dataset or the
  setup, do not capture it. Dates *stored in the sample data* (a task's
  created date, a trail's generation time, a brainstorm node's date) are
  fixed, so one that shows the day of the capture is a dataset defect.
  **Live clocks are allowed:** a value the TUI or a setup command takes from
  the clock at capture time — an agent's idle timer, a "read 08:30" status
  line, the "since" time of a lock that `./ait lock` just took — shows the
  moment of the capture and is expected.
- **Looking at the image is not optional.** A screen read (`screen`) proves
  the state. It does not prove the picture: the crop, the overlays, the
  spacing and the pane composition exist only in the image. An image counts
  as verified only when you have looked at its rendering:
  - take every shot and replay with `--png` and open the printed `PNG:` file
    with the Read tool;
  - on `PNG_UNAVAILABLE:` render the staged SVG another way: run
    `preview --batch <id>` and open `preview.html` in a browser with the
    browser tools, and inspect the image there;
  - if you cannot render it at all, the scene is **visual verification
    pending**. Say so in the final report and in the approval question (see
    "Review and apply"), with the path of `preview.html`. Never describe such
    an image as verified.
- **Never commit.** The user reviews the diff and commits.
- **Always end with** `website/screenshots.sh session stop --all`, also when
  you stop early or something failed.

## Step 1: Inventory

```bash
python3 website/check_screenshots.py --report
website/screenshots.sh list
git status --short -- website/
```

`--report` lists each marker (`UNRESOLVED:`, with its page and line) and each
marker whose scene has no recipe (`NO_SCENE:`). `list` prints each recipe with
its dataset, size and marker count. From these, build two lists, limited to
the requested scenes when any were given:

- **to discover** — scenes named by a marker that have no recipe;
- **to repair-check** — scenes that have a recipe.

**Stop on pages with someone else's edits.** `apply` rewrites the pages that
carry the markers. If `git status` shows a modified or untracked file under
`website/content/` that this run did not write, and that file carries a
marker of a scene in scope, another task is working on that page. Do not go
on to capture for it. Name the pages and ask the user (`AskUserQuestion`,
header "Pages", the page list inside the question) to choose: "Stop" (end
the run; they resolve who owns the pages first), "Leave those scenes out"
(continue without the scenes whose markers are on those pages), or "Proceed
on these pages" (they confirm the edits are theirs to mix with the
screenshots). Only the last answer lets `apply` touch such a page. This
question is **NON-SKIPPABLE**: auto mode, execution profiles and generic
"don't ask" instructions do not answer it; only the user does, here or
explicitly in chat beforehand. `apply`'s
own marker check does not protect here: an edit elsewhere in the page leaves
the marker intact, and apply would write into the page.

## Step 2: Discovery loop (one scene at a time)

For each scene to discover:

1. **Read the page.** Open every page that carries the marker; read the
   section around it, and the marker's `alt` and `caption`. Decide which state
   of which TUI illustrates that text. Write the decision down in one or two
   sentences; it becomes the recipe's `illustrates`.
2. **Choose the starting state.** Pick a dataset (`base`, `agents`,
   `board_locks`, `trails`, `brainstorm`; their docstrings in
   `sample_project.py` say what each holds) and the `setup` commands that
   prepare the rest with real framework commands. If no dataset can provide
   the data, a new dataset is a code change with its own build test — tell
   the user and treat the scene as blocked until that is done. Never fake a
   screen.
3. **Explore.**

   ```bash
   website/screenshots.sh session start --size <COLSxROWS> --dataset <name> [--window <name>]
   website/screenshots.sh setup <id> -- <command>          # zero or more, before run
   website/screenshots.sh run <id> -- <command>            # e.g. ./ait board
   website/screenshots.sh wait <id> --text "<text>" [--timeout S]
   website/screenshots.sh screen <id>                      # numbered rows
   website/screenshots.sh keys <id> <tmux key names>...
   ```

   Read the screen after every key. More panes: `pane split`, `window new`,
   and `--pane` / `--window` on `screen`, `keys`, `wait`, `find`, `shot`; a
   pane is a role (`main`, or one you named) or `<window name>.<pane index>`
   for a pane the TUI created itself. `find --text T [--box]` gives cell
   coordinates for a crop or an overlay.

   Things that have gone wrong before:
   - a key pressed before the widget holds focus does nothing; wait for the
     text that shows focus first;
   - in an agent launch dialog wait for `Pick Task t<N>`, then
     `(R)un in tmux`, then the session name `lumen`, before pressing `r`;
   - `python3` in a setup command is the session's pinned interpreter; the
     user's own tools and configuration are not reachable, by design.
4. **Check the state, then the picture.** `shot <id> --scene <scene>
   --output <file> --title "<window title>" --png`, where `<file>` is the
   marker's `file=`. Look at the PNG. Check it against the page text, the alt
   and the caption. Adjust the size, the state, the crop or the overlays and
   shoot again until it matches.
5. **Clean walk.** `session stop <id>`. Start a fresh session with the same
   size, dataset and window name, run the same setup commands, launch, and
   walk only the steps that are needed, each followed by the wait that proves
   it worked. `shot` (with the same crop and overlays, and `--png`), look at
   the image once more, then:

   ```bash
   website/screenshots.sh recipe save <id> --scene <scene> \
     --expect "<text that proves the state>" [--expect ...] \
     --illustrates "<what the image shows, from the page, alt and caption>"
   ```

   `--expect` texts must be on the captured frame and specific to the state
   (the dialog title, the expanded child's name), not text that is on every
   screen. `recipe save` replays the route in a fresh session before writing;
   on `REFUSED:` the route is not repeatable — fix the walk (a missing wait,
   state prepared outside `setup`) and walk it again. `session stop <id>`.

Several markers may share one scene: one recipe and one image serve all of
them, so check the image against every page that uses it.

## Step 3: Repair loop (one recipe at a time)

For each scene to repair-check:

```bash
sha256sum website/screenshots/scenes/<scene>.yaml        # or the --scenes directory
website/screenshots.sh replay --scene <scene> --png
```

- **`FAILED:<scene>|<where>|<reason>`** — the route no longer works. The
  session is kept: read the `SESSION:<id>` screen, try keys there, and find
  out what changed (a key binding, a label, a layout, missing data). Then
  `session stop <id>`.
- **`STAGED:<scene>|<image>`** — the route works. Now judge the image: read
  the recipe's `illustrates`, the page section, and the marker's (or, once
  applied, the `static-img` shortcode's) alt and caption, and look at the PNG.
  If the image still shows what the page describes, the recipe is good; go to
  the next one.

For a failure or a mismatch, **re-discover**: run the discovery loop for this
scene (explore, then a clean walk in a fresh session) and save with
`recipe save ... --replace`. The repair is done when `--replace` printed
`RECIPE_SAVED:` and you have looked at the new image.

**When there is no route.** If the state the recipe's `illustrates` and
`expect` describe cannot be reached — the feature is gone, the sample project
cannot hold that data, the page describes something the TUI does not do — do
**not** invent a different picture and do not touch the recipe. Check that it
is unchanged (`sha256sum` again, same value), make sure no image of it is in
the batch you will review, and report the scene with what you found: what you
tried, what the screen showed instead, and what would have to change (the
page, the TUI, or a dataset). That is a finding for the user.

Give a real repair a real attempt before concluding there is no route: read
the screen, read the TUI's key hints (`?`), and try the obvious alternatives.
A wrong key or a renamed label is a repair, not a missing route.

## Step 4: Review and apply

1. **One batch.** `apply` takes exactly one batch id, and a batch is never
   rewritten: each discovery session and each `replay` call made its own. Put
   every scene you want applied into one final batch:

   ```bash
   website/screenshots.sh replay --scene <a> --scene <b> ... --no-keep --png
   ```

   It prints `BATCH:<id>`. Look at each PNG of this batch again; these are
   the images that will be applied, not the ones you looked at earlier. A
   scene that fails here is not in the batch; repair it and replay all
   scenes again.
2. **Preview.** `website/screenshots.sh preview --batch <id>` writes
   `<batch>/preview.html`: each image with its marker pages, alt and caption,
   and the existing image beside a replacement.
3. **Ask the user.**

   **⚠️ NON-SKIPPABLE — auto mode and execution profiles do NOT bypass this
   review.** `apply` writes images and doc pages; the user's approval of this
   exact batch is what licenses it. Not covered by: execution profiles (no
   key covers it), auto mode / "work without stopping" directives, or generic
   instructions to be brief or not to ask. The only valid skip is the user
   explicitly approving this batch id in chat beforehand.

   Use `AskUserQuestion`, with everything needed to decide **inside the
   question text**:
   - Question: "Batch `<id>` holds `<n>` screenshot(s): `<scene>` → `<pages>`
     for each. Preview: `<absolute path of preview.html>`. Visual verification
     pending for: `<scenes, or "none">`. Not in this batch: `<scenes that
     could not be captured or repaired, each with a few words why, or
     "none">`. Apply this batch?"
   - Header: "Apply"
   - Options:
     - "Apply" (description: "Copy these images to website/static/imgs and
       replace their markers with static-img shortcodes")
     - "Don't apply" (description: "Leave the site as it is; the batch stays
       in the staging directory")

   Changes the user asks for mean a new capture, a new final batch, a new
   preview and this question again. Never apply a batch the user has not seen.
4. **Apply the reviewed batch.** First run `git status --short -- website/`
   again and compare it with step 1. If a page that carries a marker of this
   batch is now modified by something other than this run, and the user did
   not already answer "Proceed on these pages" for it, **stop: do not run
   `apply`.** Ask the same "Pages" question as in step 1 and follow the
   answer; "Leave those scenes out" means a new final batch without them, a
   new preview and the approval question again. Otherwise:

   ```bash
   website/screenshots.sh apply --batch <id>
   ```

   - `APPLIED:<scene>|<output>|pages=<n>` — image copied, markers replaced.
   - `REFUSED:<scene>|<reason>` — the image, its destination or a marker
     changed after capture. Nothing of that scene was written. It needs a new
     capture and a **new review**; report it, do not retry with the same batch.
   - `PARTIAL:<scene>|<paths>` — a write failed and could not be undone. Stop
     and show the user the listed paths; they restore them with git.
5. **Check the site.**

   ```bash
   (cd website && python3 check_links.py --build)
   python3 website/check_screenshots.py
   ```

   Both must pass. Report any failure with its output.

## Step 5: Report and clean up

```bash
website/screenshots.sh session stop --all
website/screenshots.sh session list        # must print nothing
```

Then tell the user, in this order:

- the batch id that was applied (or that nothing was applied);
- recipes recorded, and recipes repaired with the reason for each (failed
  replay, or a passing one that no longer matched its page);
- scenes with no route, each with what was found;
- `REFUSED:` scenes and why;
- scenes whose visual verification is pending;
- what is left uncommitted for them to review (`git status --short`).

Do not commit.
