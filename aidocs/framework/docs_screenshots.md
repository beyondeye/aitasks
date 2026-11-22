# Docs screenshots: design and contracts

The website's TUI screenshots are produced by a repository-only tool under
`website/screenshots/`, driven by the `aitask-docs-screenshots` skill. An agent
runs the real TUI on a sample project in an isolated tmux session, reaches the
state a page describes, and captures it as SVG. This file records the rules
the tool and the skill rely on. How to run the tool is in `website/README.md`
("Generating screenshots"); the skill's procedure is in
`.claude/skills/aitask-docs-screenshots/SKILL.md`.

The tool does not ship. Every `.claude/skills/` directory does (the release
glob is pinned by `tests/test_release_tarball.sh`), so the skill's first step
stops when `website/screenshots/` is absent.

## File map

| Path | Role |
|---|---|
| `website/screenshots.sh` | Launcher; runs `cli.py` on the framework interpreter. |
| `website/screenshots/cli.py` | The verbs. Its docstring is the verb reference. |
| `website/screenshots/markers.py` | The marker grammar, `static-img` rendering, the spec owner reader. Stdlib only. |
| `website/check_screenshots.py` | Marker, ownership and image-source check. Stdlib only, runs in CI. |
| `website/screenshots/sample_project.py` | `DATASETS`: the named sample-data builders. |
| `website/screenshots/session.py` | The isolated tmux session and its journal. |
| `website/screenshots/recipe.py` | `scenes/<id>.yaml` loader, validator, writer. Its docstring is the recipe schema. |
| `website/screenshots/svg_export.py`, `stitch.py`, `svgpost.py` | Pane to SVG, multi-pane windows, crop and overlays. |
| `website/screenshots/standin_agent.py` | The stand-in code agent every dataset installs as `claude`. |
| `website/screenshots/scenes/<scene>.yaml` | One recorded recipe per scene. |
| `website/screenshots/.staging/` | Sessions and batches. Ignored by git. |

## Roles

- **The agent decides and discovers.** It reads the page, decides which state
  illustrates it, and reaches that state by reading the screen and pressing
  keys. There are no per-TUI adapters and no patched TUI internals.
- **The tool is a set of primitives.** It owns isolation, the sample project,
  screen reading, key input, bounded waits, image export, batches and apply.
  It makes no decision about what to show.
- **A recipe is a record of a capture that worked.** The tool writes it from
  the session journal. It is a cache of a route. The page and the TUI as they
  are today are the source of truth.

## Markers and ownership

A page marks where a screenshot belongs with a one-line HTML comment (grammar
and value rules: `website/README.md`, "Screenshot Markers"; code:
`markers.py`).

- A scene's recipe owns its image: `output:` names the file under
  `website/static/imgs/`, and that line is the only durable scene-to-file
  mapping, because `apply` removes the markers.
- A marker's `file=` must equal its scene's `output:`. No two recipes share an
  `output:`. Several markers may share one scene.
- `shot`, `replay` and `apply` take the target filename from the recipe or the
  manifest, never from a page.
- `check_screenshots.py` fails on an unparseable screenshot comment, a marker
  whose scene has no recipe (`MISSING_SCENE_SEVERITY = "error"`), an ownership
  disagreement, and an image shortcode whose file is missing. `--strict` also
  fails on any marker still waiting for its image.

## Sample state: the setup contract

The state a recipe starts from is described by two recorded things and
nothing else:

1. **`dataset:`** names an entry in `sample_project.DATASETS`. A dataset is a
   function that writes project data into a fresh directory: task files,
   metadata, a git repository, a local bare remote, stored artifacts. It may
   run real framework commands to do so (`ait artifact create`,
   `ait brainstorm init`). It never imports, patches or stubs TUI code.
2. **`setup:`** is the ordered list of commands run with the `setup` verb
   before the TUI is launched. They are real framework commands
   (`./ait lock ...`). A replay runs them after building the dataset.

Consequences:

- Anything done to the sample project outside these two channels is not
  recorded, and the fresh-session replay inside `recipe save` fails on it.
- Data too large for a few setup commands becomes a dataset, with a build test
  in `tests/test_screenshots_sample_project.py` and a live check that the real
  TUI shows it (`tests/test_screenshots_session_live.py`).
- A scene whose data cannot be built from data and real commands is reported
  to the user. The screen is never faked.

Current datasets: `base` (tasks across three columns, one parent with
children), `agents` (code-agent configuration and a local `origin`),
`board_locks` (a local `origin` so `ait lock` works, and a sample host name),
`trails` (one stored implementation trail), `brainstorm` (one session with a
four-node proposal graph), `settings` (`agents` plus every seed agent's model
list and the seed's per-operation defaults), `codebrowser` (a small source tree
whose git history is the work of archived tasks with plans: `(tN)` code
commits, then archive commits), `stats` (about 90 archived tasks over six
weeks). Each builder's docstring says how its data is produced.

Every name on screen is invented: the project is `lumen`, the person
`alex@example.com`. Dates written into sample files are fixed, with one
exception: the Stats TUI charts windows that end today, so `stats` dates its
completions as offsets back from the day it is built. Framework commands a dataset
runs get the same scratch `HOME`, configuration and cache directories as a
session, so building one writes nothing outside its own tree.

## Which journal becomes a recipe

- A session has an origin: `discovery` (from `session start`) or `replay`.
- `recipe save` accepts only a discovery session whose journal has no failed
  step, and only after the recorded route replays in a fresh session.
- The working pattern is therefore two passes: explore in one session, then
  walk the known route cleanly in a fresh one, shoot and save.
- A replay session kept open after a failure is for inspection. Nothing done
  in it can be saved.

## Pages with someone else's edits

`apply` rewrites the pages that carry markers, and its marker check passes
when another task edited a different paragraph of the same page. The skill
therefore stops, before capturing and again before `apply`, when
`git status -- website/` shows such a page changed by something other than
the run itself, and goes on only when the user chooses to leave those scenes
out or confirms the edits may be mixed.

## Recipe lifecycle

- A recipe stores `illustrates:` (what the image is meant to show, for the
  agent's judgement) and `expect:` (texts that must be on the captured frame,
  for the tool).
- A recipe goes stale in two ways. It fails: a wait times out or an expected
  text is missing. Or it passes and no longer illustrates the page; only the
  agent can see that, by comparing the image with the page text, the alt and
  the caption.
- Repair is the discovery loop again, saved with `recipe save --replace`,
  which keeps `id` and `output`. A recipe is never edited by hand.
- When no route exists, nothing is changed and the scene is reported with
  what was found.

## Visual verification

A screen read proves the state. It does not prove the picture: crop, overlays,
spacing and pane composition exist only in the image. An image counts as
verified when the agent has looked at its rendering (the `--png` preview, or
the staged SVG in a browser through `preview.html`). When no rendering is
possible the scene is reported as "visual verification pending", in the final
report and in the approval question. PNG previews come from headless Chromium;
`rsvg-convert` is a labelled fallback that renders leading spaces and emoji
wrongly.

## Batches

- A batch is a directory under `.staging/` with a `manifest.json` (schema 1):
  per staged scene its `id`, `output`, the image's `sha256`, the destination
  state at capture time (`"absent"` or `{sha256}`) and its markers as
  `{page, text}`; plus `failed: [{id, reason}]`.
- A batch is never rewritten. A discovery session stages into one batch, a
  second shot of a scene opens a new one, and every `replay` call creates a
  new one.
- `preview --batch <id>` writes `<batch>/preview.html` from that manifest
  only: each image, its destination state (with the existing image beside a
  replacement) and each marker's page, alt and caption.

## Apply

`apply --batch <id>` needs the batch id; there is no "latest". The id is a
name under the staging directory, never a path. A scene is one unit:

1. All scenes are validated first, then each passing scene is validated again
   immediately before its own writes. The image is read once; the bytes that
   were hashed are the bytes written.
2. A scene is applied only when the staged image hashes to the manifest value,
   the destination is in the recorded state, and each marker text occurs
   exactly once in its page. Markers are found by text, never by line number.
3. Every output (the image and each page) is prepared as a temporary file
   beside its target before the first one is replaced. A failed replacement
   restores the files already replaced.
4. A recorded page must be a `.md` file inside the content tree: a relative
   path without `.` or `..` steps that still resolves under `content/`. Its
   name is otherwise free (spaces, non-ASCII letters); the image filename
   alphabet applies to `output:` only.
5. In each page only the marker text is replaced, with
   `markers.render_static_img(marker)`, in the page as it is on disk at that
   moment. Other edits to the page are kept.

| Line | Meaning |
|---|---|
| `APPLIED:<scene>\|<output>\|pages=<n>` | Image copied, markers replaced. |
| `REFUSED:<scene>\|image_missing` / `image_changed` | The staged image is gone or differs from the reviewed one. |
| `REFUSED:<scene>\|destination_created` / `_modified` / `_removed` | The target image changed since capture. |
| `REFUSED:<scene>\|marker_missing:<page>` / `marker_ambiguous:<page>` | The marker text is not in the page exactly once. |
| `REFUSED:<scene>\|marker_invalid:<page>` / `marker_mismatch:<page>` / `manifest_invalid` | The recorded marker cannot be rendered, or names another scene, file or location. |
| `REFUSED:<scene>\|write_failed:<path>` | A write failed; the scene's files were restored. |
| `PARTIAL:<scene>\|<paths>` | A write failed and a restore failed too; the listed files must be restored by hand. |
| `SKIPPED:<scene>\|not staged (...)` | The batch recorded a failed capture for this scene. |

A refused scene leaves its image and pages untouched and needs a new capture
and a new review. `apply` exits 1 when any scene was refused. One window
remains: a page edited between apply's read of it and the replacement of that
same page, a moment later, loses that edit; there is no file locking in a git
checkout.

## Isolation rules

- Every tmux call goes through `TmuxClient` (`.aitask-scripts/lib/tmux_exec.py`)
  on a private socket `ait_shots_<id>`. The server starts with `-f /dev/null`,
  so the user's tmux configuration is never loaded, and it is killed after
  one hour if a session is forgotten.
- The pane environment is pinned: `AITASKS_TMUX_SOCKET`, a scratch `HOME`,
  `XDG_CONFIG_HOME` and `XDG_CACHE_HOME` (the artifact cache holds links into
  the project; in the user's cache they would dangle after the session), a
  private `XDG_RUNTIME_DIR`, `AIT_PYTHON`, `TERM`,
  `COLORTERM`, `LANG` / `LC_ALL`, and `TZ=UTC` (a TUI prints stored UTC times
  in local time). Desktop variables are removed.
- The dataset's `.standin/bin` is first on every pane's `PATH`. It holds the
  stand-in `claude`, and `python3` / `python` shims that run `AIT_PYTHON`,
  because the user's own `python3` wrapper depends on the real `HOME`. A
  session refuses to start when `claude` would resolve anywhere else, so an
  agent launch never reaches a real agent.
- The sample project holds a copy of `.aitask-scripts`, not a symlink: several
  TUIs find their project from their own file path.
- Real clocks stay real. An idle timer, or the time a lock was taken, shows
  the moment of capture. Output is therefore not byte-identical across runs;
  what is applied is always the exact batch the user reviewed.

## Tests

`tests/test_screenshots_*.py` and `tests/test_check_screenshots.py`. The live
module (`test_screenshots_session_live.py`) boots real TUIs in tmux and sits
in the serial carve-out of `tests/run_all_python_tests.sh`.
