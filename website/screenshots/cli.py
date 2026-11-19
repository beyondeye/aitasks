"""Docs screenshot tool: primitives for an agent driving a real TUI.

Run through ``website/screenshots.sh`` (it picks the framework interpreter).

    session start [--size CxR] [--dataset NAME] [--window NAME]   -> SESSION:<id>
    setup <id> -- <command>                         data preparation, before run
                                                    (one argument = a shell command
                                                    string; several = an argv)
    run <id> -- <command>                           launch the TUI (once)
    pane split <id> --name ROLE [--target P] [-H|-v] [-l SIZE] [--full] -- <command>
                                                    -H beside the target (default),
                                                    -v below it
    window new <id> --name NAME [--role ROLE] -- <command>
                                                    more panes, after `run`; the command
                                                    is typed into the new pane's shell
    screen <id> [--pane P | --window [NAME]]        the pane (or whole window) as
                                                    numbered text
    keys <id> [--pane P] <key>...                   tmux key names
    wait <id> (--text T | --gone T) [--timeout S] [--pane P]
    find <id> --text T [--box] [--pane P | --window [NAME]]
                                                    CELL:<col>,<row> lines; with --box
                                                    BOX:<col>,<row>,<w>,<h> of the
                                                    innermost box around a unique text
    shot <id> --scene ID --output FILE [--title T] [--png]
             [--pane P | --window [NAME]]           default: the main pane
             [--crop SPEC] [--overlay SPEC]...      SPEC is the recipe form as YAML flow
                                                    ('{cells: [1, 5, 40, 7], gutter: 30}');
                                                    --crop also takes C,R,W,H
    recipe save <id> --scene ID --expect T... --illustrates TEXT [--replace]
    replay (--scene ID... | --all | --pending) [--no-keep] [--png]
    preview --batch ID                              one HTML contact sheet of that batch
                                                    (<batch>/preview.html)
    apply --batch ID                                copy the batch's images to static/imgs
                                                    and replace each marker with its
                                                    static-img shortcode; the batch id is
                                                    required (the one that was reviewed)
    session stop (<id> | --all) / session list
    list

A pane ``P`` is a role (``main``, or a name given to ``pane split`` / ``window
new``) or ``<window name>.<pane index>`` for a pane the TUI created itself;
never a tmux id. ``--window`` without a name is the main pane's window.

Result lines are ``KEY:value`` (``SESSION:``, ``BATCH:``, ``SHOT:``, ``PNG:``,
``STAGED:``, ``FAILED:``, ``REFUSED:``, ``RECIPE_SAVED:``, ``BOX:``, ``PREVIEW:``,
``APPLIED:``, ``PARTIAL:``, ``SKIPPED:``, ``APPLY:``). Exit status:
0 done, 1 a capture, wait, replay, save or apply failed or was refused (also when
``--png`` was asked and no preview could be made), 2 usage.

``apply`` treats a scene as one unit. It applies a scene only when the staged
image still hashes to the manifest value, the destination file is in the state
the manifest recorded (still absent, or the same hash), and every marker of
the scene is still in its page exactly once, byte for byte. Image and
destination are checked again right before that scene is written, every
output is prepared before the first file is replaced, and a failed replacement
restores what was already replaced. A refused scene (``REFUSED:<scene>|<reason>``)
leaves its image and its pages as they were and needs a new capture and a new
review. ``PARTIAL:<scene>|<paths>`` means a restore failed too: those paths
were changed and must be restored by hand (``git checkout``).
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shlex
import shutil
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

WEBSITE = Path(__file__).resolve().parents[1]
if str(WEBSITE) not in sys.path:
    sys.path.insert(0, str(WEBSITE))

from screenshots import markers, recipe as recipes, sample_project  # noqa: E402
from screenshots import session as sessions  # noqa: E402
from screenshots import stitch, svg_export, svgpost  # noqa: E402
from rich.ansi import AnsiDecoder  # noqa: E402

STEP_TIMEOUT = sessions.DEFAULT_TIMEOUT
EXPECT_TIMEOUT = 15.0
STABLE_TIMEOUT = 5.0
DEFAULT_TITLE = "aitasks"


class Paths:
    def __init__(self, args):
        self.content = Path(args.content).resolve()
        self.static = Path(args.static).resolve()
        self.scenes = Path(args.scenes).resolve()
        self.staging = Path(args.staging).resolve()


class Refused(Exception):
    """A verb declined to act; nothing was written."""


# --- batches -----------------------------------------------------------------


def new_batch(staging: Path) -> Path:
    """A NEW batch directory. Never an existing one, so a later capture cannot
    replace files someone has already reviewed."""
    staging.mkdir(parents=True, exist_ok=True)
    for _ in range(5):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = staging / f"{stamp}-{uuid.uuid4().hex[:6]}"
        try:
            path.mkdir(exist_ok=False)
        except FileExistsError:
            continue
        write_manifest(path, {"schema": 1, "batch": path.name,
                              "created_at": datetime.now(timezone.utc).isoformat(),
                              "scenes": [], "failed": []})
        return path
    raise Refused("could not create a new batch directory")


def read_manifest(batch: Path) -> dict:
    return json.loads((batch / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(batch: Path, manifest: dict) -> None:
    tmp = batch / "manifest.json.tmp"
    tmp.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, batch / "manifest.json")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage(batch: Path, paths: Paths, scene: str, output: str, svg: str) -> Path:
    """Write the image into the batch and record it in the manifest."""
    image = batch / output
    manifest = read_manifest(batch)
    if image.exists() or any(s["id"] == scene or s["output"] == output
                             for s in manifest["scenes"]):
        # A batch id names the images someone reviewed. Replacing one under
        # the same id would let `apply` copy an image nobody looked at.
        raise Refused(f"batch {batch.name} already holds {output}; a batch is never rewritten")
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_text(svg, encoding="utf-8")
    destination = paths.static / "imgs" / output
    found, _bad = markers.scan(paths.content) if paths.content.is_dir() else ([], [])
    entry = {
        "id": scene,
        "output": output,
        "sha256": sha256_file(image),
        "destination": ({"sha256": sha256_file(destination)}
                        if destination.is_file() else "absent"),
        "markers": [{"page": m.path, "text": m.text} for m in found if m.scene == scene],
    }
    manifest["scenes"].append(entry)
    write_manifest(batch, manifest)
    return image


def batch_holds(batch: Path, scene: str, output: str) -> bool:
    if (batch / output).exists():
        return True
    return any(s["id"] == scene or s["output"] == output
               for s in read_manifest(batch)["scenes"])


def record_failure(batch: Path, scene: str, reason: str) -> None:
    manifest = read_manifest(batch)
    manifest["failed"] = [f for f in manifest["failed"] if f["id"] != scene]
    manifest["failed"].append({"id": scene, "reason": reason})
    write_manifest(batch, manifest)


def preview_png(batch: Path, scene: str, image: Path) -> bool:
    """Render the preview. Returns whether a PNG file was produced; a caller
    that asked for one must not report success without it."""
    png = batch / "_preview" / f"{scene}.png"
    png.parent.mkdir(exist_ok=True)
    try:
        renderer = svg_export.render_png(image, png)
    except svg_export.ExportError as exc:
        print(f"PNG_UNAVAILABLE:{_one_line(exc)} (the SVG is staged: {image})")
        return False
    if not png.is_file():
        print(f"FAILED:png|{renderer} reported success but wrote no {png}")
        return False
    note = "" if renderer != "rsvg-convert" else \
        " (rsvg-convert: NOT faithful — leading spaces and emoji are wrong; trust the SVG)"
    print(f"PNG:{png}{note}")
    return True


# --- capture -----------------------------------------------------------------


class Frame:
    """One captured screen: decoded rows and the size they were captured at."""

    def __init__(self, rows, width: int, height: int):
        self.rows, self.width, self.height = rows, width, height

    @property
    def plain(self) -> list[str]:
        return [row.plain.rstrip() for row in self.rows]


def _grab(sess, capture):
    """``(signature, build)``: the raw capture, and how to turn it into a Frame.

    A pane is captured at its size NOW (a split shrinks the pane it splits); a
    window is every pane plus the geometry, in one consistent read.
    """
    if capture and "window" in capture:
        size, panes = sessions.window_layout(sess, capture["window"])
        texts = [sessions.capture_pane(sess, p.id, ansi=True) for p in panes]

        def build():
            options = sessions.window_options(sess, panes)
            boxes = [stitch.Pane(p.left, p.top, p.width, p.height, p.active, text)
                     for p, text in zip(panes, texts)]
            return Frame(stitch.stitch(size[0], size[1], boxes, options), *size)
        return (size, [(p.left, p.top, p.width, p.height, p.active) for p in panes],
                texts), build
    pane_id = sessions.resolve_pane(sess, (capture or {}).get("pane"))
    width, height = sessions.pane_geometry(sess, pane_id)
    text = sessions.capture_pane(sess, pane_id, ansi=True)

    def build():
        rows = list(AnsiDecoder().decode(text))[:height]
        return Frame(rows, width, height)
    return ((width, height), text), build


def stable_capture(sess, capture=None) -> Frame:
    """A frame, once two consecutive captures agree.

    A frame caught in the middle of a repaint is not a screenshot. A screen
    that never holds still for one poll interval is a failure, not a picture.
    """
    deadline = time.monotonic() + STABLE_TIMEOUT
    previous, _ = _grab(sess, capture)
    while True:
        time.sleep(sessions.POLL_INTERVAL)
        current, build = _grab(sess, capture)
        if current == previous:
            try:
                return build()
            except stitch.StitchError as exc:
                raise svg_export.ExportError(f"stitch: {exc}") from exc
        if time.monotonic() >= deadline:
            raise sessions.SessionError(
                f"the screen did not hold still within {STABLE_TIMEOUT:g}s")
        previous = current


def _misplaced(rows, crop, overlays, size=None) -> list[str]:
    """Every rectangle outside the captured frame, and every ``holds`` text
    that is not inside its rectangle on ``rows``."""
    targets = ([("crop", crop)] if crop else []) + [
        (f"overlay {n}", item["target"]) for n, item in enumerate(overlays or (), start=1)]
    problems = []
    for where, target in targets:
        c, r, w, h = target["cells"]
        if size is not None and (c + w > size[0] or r + h > size[1]):
            problems.append(f"{where}: {target['cells']} reaches outside the captured "
                            f"{size[0]}x{size[1]} frame")
        elif "holds" in target and not sessions.rect_holds(rows, target["cells"],
                                                           target["holds"]):
            problems.append(f"{where}: {target['holds']!r} not inside {target['cells']}")
    return problems


def export(sess, title: str, scene: str, expect=(), crop=None, overlays=None,
           capture=None) -> str:
    """Export one settled frame that shows every text in ``expect``.

    The texts are checked together, on the very frame that becomes the image.
    Checking them one after another on the live screen would accept a text
    that was there a moment ago and is gone from the picture. The crop and
    overlay rectangles are checked against that frame's size (a split pane is
    smaller than the window) and their ``holds`` texts on its rows; then the
    crop and overlays are applied to its SVG.
    """
    deadline = time.monotonic() + EXPECT_TIMEOUT
    while True:
        frame = stable_capture(sess, capture)
        rows = frame.plain
        text = "\n".join(rows)
        missing = [wanted for wanted in expect if wanted not in text]
        misplaced = [] if missing else _misplaced(rows, crop, overlays,
                                                  (frame.width, frame.height))
        if not missing and not misplaced:
            svg = svg_export.rows_to_svg(frame.rows, frame.width, frame.height,
                                         title=title, scene_id=scene)
            try:
                return svgpost.postprocess(svg, crop, overlays or ())
            except svgpost.SvgPostError as exc:
                raise svg_export.ExportError(f"crop/overlay: {exc}") from exc
        if time.monotonic() >= deadline:
            if missing:
                raise MissingExpected(missing)
            raise Misplaced(misplaced)
        time.sleep(sessions.POLL_INTERVAL)


class MissingExpected(Exception):
    def __init__(self, missing):
        super().__init__(", ".join(repr(m) for m in missing) + " not on the captured frame")
        self.missing = missing


class Misplaced(Exception):
    """A crop or overlay rectangle no longer holds its text: the layout moved."""

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = problems


def check_ownership(paths: Paths, scene: str, output: str) -> None:
    """``output`` must be free, or already this scene's."""
    if not markers.SCENE_RE.match(scene):
        raise Refused(f"scene id {scene!r} must match [a-z0-9_]+")
    problem = markers.path_problem(output)
    if problem:
        raise Refused(f"output {output!r} {problem}")
    if not paths.scenes.is_dir():
        return
    for path in sorted(paths.scenes.glob("*.yaml")):
        owner = markers.read_spec_owner(path)
        if path.stem == scene and owner.output not in (None, output):
            raise Refused(f"scene {scene!r} owns output {owner.output!r}, not {output!r}")
        if path.stem != scene and owner.output == output:
            raise Refused(f"output {output!r} is owned by scene {path.stem!r}")


def replay_one(rec, paths: Paths, *, keep: bool):
    """Run one recipe in a fresh session.

    Returns ``(svg, None, None)`` or ``(None, "<where>|<reason>", session)``;
    the session is returned (still running) only when ``keep`` is set.
    """
    try:
        sess = sessions.start(paths.staging, size=rec.size, dataset=rec.dataset,
                              origin="replay", window=rec.window)
    except (sessions.SessionError, sample_project.DatasetError) as exc:
        return None, f"session|{_one_line(exc)}", None

    def failed(where: str, reason) -> tuple:
        if keep:
            return None, f"{where}|{_one_line(reason)}", sess
        sessions.stop(sess)
        return None, f"{where}|{_one_line(reason)}", None

    try:
        for number, command in enumerate(rec.setup, start=1):
            try:
                sessions.setup(sess, command)
            except sessions.SessionError as exc:
                # Never launch the TUI on data that was not prepared.
                return failed(f"setup {number}", exc)
        sessions.run(sess, rec.launch)
        for number, (kind, value, timeout, pane) in enumerate(rec.steps, start=1):
            # A wait recorded with its own (longer) budget keeps it.
            budget = STEP_TIMEOUT if timeout is None else timeout
            try:
                if kind == "keys":
                    sessions.keys(sess, list(value), pane=pane)
                elif kind == "wait":
                    sessions.wait(sess, text=value, timeout=budget, pane=pane)
                elif kind == "wait_gone":
                    sessions.wait(sess, gone=value, timeout=budget, pane=pane)
                elif kind == "pane_split":
                    sessions.pane_split(sess, value["name"], value["command"],
                                        target=value.get("target"),
                                        direction=value.get("direction", "h"),
                                        size=value.get("size"), full=value.get("full", False))
                else:
                    sessions.window_new(sess, value["name"], value["command"],
                                        role=value.get("role"))
            except sessions.SessionError as exc:
                return failed(f"step {number}", exc)
        try:
            svg = export(sess, rec.window_title, rec.id, rec.expect, rec.crop, rec.overlays,
                         rec.capture)
        except MissingExpected as exc:
            return failed("expect", exc)
        except Misplaced as exc:
            return failed("overlay", exc)
        except (sessions.SessionError, svg_export.ExportError) as exc:
            return failed("capture", exc)
    except BaseException:
        sessions.stop(sess)
        raise
    sessions.stop(sess)
    return svg, None, None


def _one_line(value) -> str:
    return " ".join(str(value).split())[:300]


# --- verbs -------------------------------------------------------------------


def _session(args, paths: Paths):
    return sessions.load(paths.staging, args.id)


def _command(args) -> str:
    """The command after ``--``, as one shell command line.

    One argument is taken as a shell command string, as written
    (``-- './ait update --batch 14 && true'``). Several arguments are an argv
    and are quoted back, so their boundaries survive
    (``-- python -c 'print("two words")'``).
    """
    words = list(args.command)
    if words and words[0] == "--":
        words = words[1:]
    if len(words) == 1:
        return words[0]
    return shlex.join(words)


def _parse_size(text: str) -> tuple[int, int]:
    try:
        width, height = (int(v) for v in text.lower().split("x"))
    except ValueError:
        raise Refused(f"size {text!r} is not COLUMNSxROWS") from None
    return width, height


def cmd_session_start(args, paths):
    sess = sessions.start(paths.staging, size=_parse_size(args.size), dataset=args.dataset,
                          window=args.window or "")
    print(f"PROJECT:{sess.project}")
    print(f"SESSION:{sess.id}")
    return 0


def cmd_session_stop(args, paths):
    if args.all:
        targets = sessions.list_sessions(paths.staging)
    elif args.id:
        targets = [sessions.load(paths.staging, args.id)]
    else:
        raise Refused("give a session id or --all")
    for sess in targets:
        sessions.stop(sess)
        print(f"STOPPED:{sess.id}")
    return 0


def cmd_session_list(args, paths):
    for sess in sessions.list_sessions(paths.staging):
        state = "alive" if sessions.is_alive(sess) else "dead"
        print(f"SESSION:{sess.id}|{sess.origin}|{sess.dataset}|"
              f"{sess.size[0]}x{sess.size[1]}|{state}")
    return 0


def cmd_setup(args, paths):
    output = sessions.setup(_session(args, paths), _command(args))
    if output.strip():
        print(output.rstrip())
    print("SETUP_OK")
    return 0


def cmd_run(args, paths):
    sessions.run(_session(args, paths), _command(args))
    print("LAUNCHED")
    return 0


def _capture_target(args):
    """``{"window": NAME}``, ``{"pane": P}`` or None from ``--pane`` / ``--window``."""
    pane, window = getattr(args, "pane", None), getattr(args, "window", None)
    if pane is not None and window is not None:
        raise Refused("give --pane or --window, not both")
    if window is not None:
        return {"window": window or None}
    if pane is not None:
        return {"pane": pane}
    return None


def _window_name(sess, window):
    """The name of ``window`` (None = the main pane's window), for journals and
    recipes, which never hold tmux ids."""
    if window:
        return window
    rc, out = sess.client.run(["display-message", "-p", "-t", sessions.resolve_pane(sess),
                               "#{window_name}"])
    name = out.strip()
    if rc != 0 or not sessions.WINDOW_NAME_RE.fullmatch(name):
        raise Refused(f"the main pane's window has no usable name ({name!r}); start the "
                      "session with --window NAME or give shot --window NAME")
    return name


def _screen_rows(sess, target) -> tuple[list[str], str]:
    if target and "window" in target:
        frame = stable_capture(sess, target)
        return frame.plain, f"WINDOW:{frame.width}x{frame.height}"
    pane = (target or {}).get("pane")
    width, height = sessions.pane_geometry(sess, sessions.resolve_pane(sess, pane))
    return (sessions.screen_rows(sess, pane),
            f"PANE:{width}x{height}|command={sessions.pane_command(sess, pane)}")


def _print_screen(sess, target=None) -> None:
    rows, head = _screen_rows(sess, target)
    print(f"{head}|origin={sess.origin}|launched={'yes' if sess.launched else 'no'}")
    for number, row in enumerate(rows):
        print(f"{number:02d}|{row}")


def cmd_screen(args, paths):
    _print_screen(_session(args, paths), _capture_target(args))
    return 0


def cmd_pane_split(args, paths):
    sess = _session(args, paths)
    sessions.pane_split(sess, args.name, _command(args), target=args.target,
                        direction="v" if args.v else "h", size=args.l, full=args.full)
    print(f"PANE:{args.name}")
    return 0


def cmd_window_new(args, paths):
    sess = _session(args, paths)
    sessions.window_new(sess, args.name, _command(args), role=args.role)
    print(f"PANE:{args.role or args.name}")
    return 0


def cmd_keys(args, paths):
    sessions.keys(_session(args, paths), args.keys, pane=args.pane)
    print("KEYS_SENT")
    return 0


def cmd_wait(args, paths):
    sess = _session(args, paths)
    try:
        sessions.wait(sess, text=args.text, gone=args.gone, timeout=args.timeout,
                      pane=args.pane)
    except sessions.WaitTimeout as exc:
        print(f"FAILED:wait|{_one_line(exc)}")
        _print_screen(sess, {"pane": args.pane} if args.pane else None)
        return 1
    print("WAIT_OK")
    return 0


def cmd_find(args, paths):
    sess = _session(args, paths)
    rows, _ = _screen_rows(sess, _capture_target(args))
    if args.box:
        c, r, w, h = sessions.box_around(rows, args.text)
        print(f"BOX:{c},{r},{w},{h}")
        return 0
    cells = sessions.find_in_rows(rows, args.text)
    for column, row in cells:
        print(f"CELL:{column},{row}")
    print(f"FOUND:{len(cells)}")
    return 0 if cells else 1


def _spec(text: str, what: str):
    """A ``--crop`` / ``--overlay`` value: the recipe form as YAML flow."""
    import yaml

    if what == "crop" and all(part.strip().lstrip("-").isdigit() for part in text.split(",")) \
            and text.count(",") == 3:
        return {"cells": [int(part) for part in text.split(",")]}
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise Refused(f"--{what} {text!r} is not YAML: {_one_line(exc)}") from None


def cmd_shot(args, paths):
    sess = _session(args, paths)
    check_ownership(paths, args.scene, args.output)
    # Validated exactly as a recipe validates them, before anything is
    # captured: a shot can only journal what `recipe save` will accept.
    crop = recipes.validate_crop(_spec(args.crop, "crop"), sess.size) if args.crop else None
    overlays = recipes.validate_overlays([_spec(o, "overlay") for o in args.overlay],
                                         sess.size, crop) if args.overlay else None
    capture = _capture_target(args)
    if capture and "window" in capture:
        # Journals and recipes name windows, never tmux ids.
        capture = {"window": _window_name(sess, capture["window"])}
    if capture and "pane" in capture:
        sessions.resolve_pane(sess, capture["pane"])      # refuse a bad pane early
    try:
        svg = export(sess, args.title, args.scene, (), crop, overlays, capture)
    except Misplaced as exc:
        print(f"FAILED:overlay|{_one_line(exc)}")
        return 1
    batch = paths.staging / sess.batch if sess.batch else None
    if batch is None or not (batch / "manifest.json").is_file() \
            or batch_holds(batch, args.scene, args.output):
        # A second shot of a scene goes into a NEW batch: the earlier image
        # stays exactly as it was under its own batch id.
        batch = new_batch(paths.staging)
    sess.batch = batch.name
    image = stage(batch, paths, args.scene, args.output, svg)
    entry = {"scene": args.scene, "output": args.output, "title": args.title}
    if crop is not None:
        entry["crop"] = crop
    if overlays is not None:
        entry["overlays"] = overlays
    if capture is not None:
        entry["capture"] = capture
    sess.log("shot", **entry)
    print(f"SHOT:{image}")
    previewed = preview_png(batch, args.scene, image) if args.png else True
    print(f"BATCH:{batch.name}")
    return 0 if previewed else 1


def cmd_recipe_save(args, paths):
    sess = _session(args, paths)
    shots = [e for e in sess.journal if e["kind"] == "shot" and e.get("scene") == args.scene]
    if not shots:
        raise Refused(f"session {sess.id} took no shot for scene {args.scene!r}")
    output, title = shots[-1]["output"], shots[-1].get("title", "")
    check_ownership(paths, args.scene, output)
    target = paths.scenes / f"{args.scene}.yaml"
    if target.exists() and not args.replace:
        raise Refused(f"{target.name} exists; repair it with --replace")
    rec = recipes.from_session(sess, scene=args.scene, output=output, expect=args.expect,
                               illustrates=args.illustrates,
                               title="" if title == DEFAULT_TITLE else title)
    # The gate: a recipe is only a recipe if a FRESH session, starting from the
    # dataset and the recorded setup alone, reaches the same screen.
    svg, failure, _ = replay_one(rec, paths, keep=False)
    if svg is None:
        raise Refused(f"the recorded route does not replay in a fresh session ({failure}); "
                      "nothing was written")
    path = recipes.write(rec, paths.scenes, replace=args.replace)
    print(f"RECIPE_SAVED:{path}")
    return 0


def cmd_replay(args, paths):
    known = recipes.load_all(paths.scenes)
    if args.all:
        chosen = list(known)
    elif args.pending:
        found, _bad = markers.scan(paths.content)
        chosen = sorted({m.scene for m in found if m.scene in known})
    else:
        chosen = list(dict.fromkeys(args.scene or []))
        missing = [s for s in chosen if s not in known]
        if missing:
            raise Refused(f"no recipe for: {', '.join(missing)}")
    if not chosen:
        print("NOTHING_TO_REPLAY")
        return 0
    batch = new_batch(paths.staging)
    failures = 0
    for scene in chosen:
        rec = known[scene]
        svg, failure, kept = replay_one(rec, paths, keep=not args.no_keep)
        if svg is None:
            failures += 1
            record_failure(batch, scene, failure)
            print(f"FAILED:{scene}|{failure}")
            if kept is not None:
                print(f"SESSION:{kept.id}")
                _print_screen(kept)
            continue
        image = stage(batch, paths, scene, rec.output, svg)
        print(f"STAGED:{scene}|{image}")
        if args.png and not preview_png(batch, scene, image):
            failures += 1
    print(f"BATCH:{batch.name}")
    return 1 if failures else 0


def cmd_list(args, paths):
    known = recipes.load_all(paths.scenes)
    found, _bad = markers.scan(paths.content) if paths.content.is_dir() else ([], [])
    for scene, rec in known.items():
        count = sum(1 for m in found if m.scene == scene)
        image = "image" if (paths.static / "imgs" / rec.output).is_file() else "no-image"
        print(f"SCENE:{scene}|{rec.output}|{rec.dataset}|{rec.size[0]}x{rec.size[1]}|"
              f"markers={count}|{image}")
    print(f"SCENES:{len(known)}")
    return 0


# --- preview and apply -------------------------------------------------------

BATCH_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def _batch_dir(paths: Paths, batch_id: str) -> Path:
    """The directory of batch ``batch_id``. The id is a name, never a path."""
    if not BATCH_ID_RE.fullmatch(batch_id or ""):
        raise Refused(f"batch id {batch_id!r} is not a batch name")
    batch = paths.staging / batch_id
    if not (batch / "manifest.json").is_file():
        raise Refused(f"no batch {batch_id!r} under {paths.staging}")
    try:
        manifest = read_manifest(batch)
    except (OSError, ValueError) as exc:
        raise Refused(f"batch {batch_id}: unreadable manifest ({_one_line(exc)})") from None
    if manifest.get("batch") != batch_id or not isinstance(manifest.get("scenes"), list):
        raise Refused(f"batch {batch_id}: the manifest does not describe this batch")
    return batch


def _scene_markers(scene: dict):
    """``[(page, text, Marker | reason)]`` for a manifest scene."""
    out = []
    for record in scene.get("markers", []):
        parsed = markers.parse_marker(record["text"], record["page"])
        out.append((record["page"], record["text"], parsed))
    return out


def cmd_preview(args, paths):
    batch = _batch_dir(paths, args.batch)
    manifest = read_manifest(batch)
    esc = html.escape
    parts = [
        "<!doctype html>", '<html lang="en"><head><meta charset="utf-8">',
        f"<title>Screenshot batch {esc(manifest['batch'])}</title>",
        "<style>body{font:15px/1.5 system-ui,sans-serif;margin:2rem;background:#f4f4f2;color:#1e1e1e}"
        "section{background:#fff;border:1px solid #d0d0cc;border-radius:8px;padding:1rem 1.25rem;"
        "margin:0 0 1.5rem}img{max-width:100%;height:auto;border:1px solid #d0d0cc}"
        ".pair{display:grid;grid-template-columns:1fr 1fr;gap:1rem}.pair figcaption{font-weight:600}"
        "figure{margin:0}code{background:#eeeeea;padding:0 .25em}dt{font-weight:600;margin-top:.5rem}"
        "dd{margin:0 0 0 1rem}.flag{color:#a4262c;font-weight:600}</style></head><body>",
        f"<h1>Screenshot batch <code>{esc(manifest['batch'])}</code></h1>",
        f"<p>Created {esc(str(manifest.get('created_at', '')))}. Apply exactly this batch with "
        f"<code>website/screenshots.sh apply --batch {esc(manifest['batch'])}</code>.</p>",
    ]
    for scene in manifest["scenes"]:
        output = scene["output"]
        replaces = scene.get("destination") != "absent"
        parts.append(f"<section><h2>{esc(scene['id'])}</h2>")
        parts.append(f"<p>Output: <code>static/imgs/{esc(output)}</code> — "
                     + ("<strong>replaces the existing image</strong>" if replaces
                        else "new file") + "</p>")
        new = f'<figure><figcaption>New</figcaption><img src="{esc(output)}" alt=""></figure>'
        if replaces:
            current = (paths.static / "imgs" / output).as_uri()
            parts.append('<div class="pair"><figure><figcaption>Existing</figcaption>'
                         f'<img src="{esc(current)}" alt=""></figure>{new}</div>')
        else:
            parts.append(new)
        found = _scene_markers(scene)
        if not found:
            parts.append("<p>No markers — image only.</p>")
        else:
            parts.append("<dl>")
            for page, text, parsed in found:
                parts.append(f"<dt>Page <code>content/{esc(page)}</code></dt>")
                if isinstance(parsed, markers.Marker):
                    parts.append(f"<dd>Alt: {esc(parsed.alt)}</dd>")
                    parts.append("<dd>Caption: " + (esc(parsed.caption) if parsed.caption
                                                    is not None else "<em>none</em>") + "</dd>")
                else:
                    parts.append(f'<dd class="flag">Marker does not parse ({esc(str(parsed))}): '
                                 f"<code>{esc(text)}</code></dd>")
            parts.append("</dl>")
        parts.append("</section>")
    if manifest.get("failed"):
        parts.append("<section><h2>Not staged</h2><ul>")
        parts += [f"<li><code>{esc(f['id'])}</code>: {esc(f['reason'])}</li>"
                  for f in manifest["failed"]]
        parts.append("</ul></section>")
    parts.append("</body></html>")
    target = batch / "preview.html"
    tmp = batch / "preview.html.tmp"
    tmp.write_text("\n".join(parts) + "\n", encoding="utf-8")
    os.replace(tmp, target)
    for scene in manifest["scenes"]:
        png = batch / "_preview" / f"{scene['id']}.png"
        if png.is_file():
            print(f"PNG:{png}")
    print(f"SCENES:{len(manifest['scenes'])}")
    print(f"PREVIEW:{target}")
    return 0


class SceneRefused(Exception):
    """One scene of a batch cannot be applied; ``reason`` is its REFUSED text."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class PartialWrite(Exception):
    """A scene's write failed AND restoring the files already replaced failed."""

    def __init__(self, changed: list[Path], cause: str):
        super().__init__(cause)
        self.changed, self.cause = changed, cause


def _image_state(scene: dict, batch: Path, paths: Paths) -> tuple[bytes, Path, bytes | None]:
    """Check the staged image and the destination against the manifest.

    Returns ``(image bytes, destination, destination bytes or None)``. The
    image is read once: the bytes that were hashed are the bytes a caller
    writes, so a file swapped after the check is never what gets copied.
    """
    try:
        image = (batch / scene["output"]).read_bytes()
    except OSError:
        raise SceneRefused("image_missing") from None
    if hashlib.sha256(image).hexdigest() != scene["sha256"]:
        raise SceneRefused("image_changed")
    destination = paths.static / "imgs" / scene["output"]
    recorded = scene["destination"]
    try:
        current = destination.read_bytes() if destination.is_file() else None
    except OSError as exc:
        raise SceneRefused(f"destination_unreadable:{_one_line(exc)}") from None
    if recorded == "absent":
        if current is not None or destination.exists():
            raise SceneRefused("destination_created")
    elif current is None:
        raise SceneRefused("destination_removed")
    elif hashlib.sha256(current).hexdigest() != recorded["sha256"]:
        raise SceneRefused("destination_modified")
    return image, destination, current


def _page_inside(page: str, paths: Paths) -> bool:
    """Whether a recorded page is a Markdown file inside the content tree.

    A page name is whatever the author called the file (spaces, non-ASCII);
    the image filename alphabet does not apply to it. What matters is that
    the record cannot point apply at a file outside ``content/``: a relative
    path with no ``..`` step that still resolves under the content root.
    """
    if not isinstance(page, str) or not page.endswith(".md") or "\\" in page:
        return False
    parts = page.split("/")
    if page.startswith("/") or any(part in ("", ".", "..") for part in parts):
        return False
    root = paths.content.resolve()
    try:
        (paths.content / page).resolve().relative_to(root)
    except ValueError:
        return False
    return True


def _page_edits(scene: dict, paths: Paths) -> list[tuple[Path, bytes, bytes]]:
    """``[(page path, original bytes, new bytes)]``: each marker of the scene
    replaced by its shortcode in the page AS IT IS NOW. Markers are found by
    their text, never by line number."""
    if markers.path_problem(scene["output"]) or not markers.SCENE_RE.match(scene["id"]):
        raise SceneRefused("manifest_invalid")
    texts: dict[str, str] = {}
    originals: dict[str, bytes] = {}
    for page, text, parsed in _scene_markers(scene):
        if not _page_inside(page, paths):
            raise SceneRefused(f"marker_invalid:{page}")
        if not isinstance(parsed, markers.Marker):
            raise SceneRefused(f"marker_invalid:{page}")
        if parsed.scene != scene["id"] or parsed.file != scene["output"]:
            raise SceneRefused(f"marker_mismatch:{page}")
        try:
            shortcode = markers.render_static_img(parsed)
        except ValueError:
            raise SceneRefused(f"marker_invalid:{page}") from None
        if page not in texts:
            try:
                originals[page] = (paths.content / page).read_bytes()
                texts[page] = originals[page].decode("utf-8")
            except (OSError, UnicodeDecodeError):
                raise SceneRefused(f"marker_missing:{page}") from None
        count = texts[page].count(text)
        if count == 0:
            raise SceneRefused(f"marker_missing:{page}")
        if count > 1:
            raise SceneRefused(f"marker_ambiguous:{page}")
        texts[page] = texts[page].replace(text, shortcode, 1)
    return [(paths.content / page, originals[page], texts[page].encode("utf-8"))
            for page in texts]


def validate_scene(scene: dict, batch: Path, paths: Paths) -> None:
    """Raise ``SceneRefused`` when the scene cannot be applied as reviewed."""
    _image_state(scene, batch, paths)
    _page_edits(scene, paths)


def _replace(tmp: Path, target: Path) -> None:
    """The one place a prepared file takes its target's place (a test seam)."""
    os.replace(tmp, target)


def _temp_beside(target: Path) -> Path:
    return target.with_name(f".{target.name}.{uuid.uuid4().hex[:8]}.apply-tmp")


def _apply_scene(scene: dict, batch: Path, paths: Paths) -> int:
    """Apply one scene as a unit; returns the number of pages rewritten.

    Revalidate, prepare every output, then replace; a failure restores the
    files already replaced. Raises ``SceneRefused`` (nothing of the scene is
    left changed) or ``PartialWrite`` (the restore failed as well).
    """
    image, destination, before = _image_state(scene, batch, paths)
    edits = _page_edits(scene, paths)
    outputs = [(destination, before, image)] + [(p, old, new) for p, old, new in edits]
    made_dirs: list[Path] = []
    prepared: list[tuple[Path, Path, bytes | None]] = []     # (tmp, target, original)
    replaced: list[tuple[Path, bytes | None]] = []

    def discard_temps() -> None:
        for tmp, _target, _old in prepared:
            try:
                tmp.unlink()
            except OSError:
                pass

    def remove_made_dirs() -> None:
        for directory in reversed(made_dirs):
            try:
                directory.rmdir()
            except OSError:
                pass

    try:
        for target, old, new in outputs:
            parent = target.parent
            missing = []
            while not parent.exists():
                missing.append(parent)
                parent = parent.parent
            for directory in reversed(missing):
                directory.mkdir()
                made_dirs.append(directory)
            tmp = _temp_beside(target)
            prepared.append((tmp, target, old))
            tmp.write_bytes(new)
            if old is not None:
                shutil.copymode(target, tmp)      # a page keeps its mode
    except OSError as exc:
        discard_temps()
        remove_made_dirs()
        raise SceneRefused(f"write_failed:{_rel_site(prepared[-1][1] if prepared else destination, paths)}"
                           f" ({_one_line(exc)})") from None
    failed_at = None
    try:
        for tmp, target, old in prepared:
            failed_at = target
            _replace(tmp, target)
            replaced.append((target, old))
    except OSError as exc:
        stuck = []
        for target, old in reversed(replaced):
            try:
                if old is None:
                    target.unlink()
                else:
                    back = _temp_beside(target)
                    back.write_bytes(old)
                    shutil.copymode(target, back)
                    os.replace(back, target)
            except OSError:
                stuck.append(target)
        discard_temps()
        remove_made_dirs()
        if stuck:
            raise PartialWrite(stuck, _one_line(exc)) from None
        raise SceneRefused(f"write_failed:{_rel_site(failed_at, paths)} ({_one_line(exc)})") from None
    return len(edits)


def _rel_site(path: Path, paths: Paths) -> str:
    for base, prefix in ((paths.content, "content/"), (paths.static, "static/")):
        try:
            return prefix + path.relative_to(base).as_posix()
        except ValueError:
            continue
    return str(path)


def cmd_apply(args, paths):
    batch = _batch_dir(paths, args.batch)
    manifest = read_manifest(batch)
    # Phase one: every scene's verdict, before anything is written.
    verdicts: dict[str, str | None] = {}
    for scene in manifest["scenes"]:
        try:
            validate_scene(scene, batch, paths)
            verdicts[scene["id"]] = None
        except SceneRefused as exc:
            verdicts[scene["id"]] = exc.reason
        except (KeyError, TypeError):
            verdicts[scene.get("id", "?") if isinstance(scene, dict) else "?"] = "manifest_invalid"
    applied = refused = 0
    # Phase two: each passing scene, checked again right before its own writes.
    for scene in manifest["scenes"]:
        name = scene.get("id", "?") if isinstance(scene, dict) else "?"
        reason = verdicts.get(name)
        if reason is None:
            try:
                pages = _apply_scene(scene, batch, paths)
            except SceneRefused as exc:
                reason = exc.reason
            except PartialWrite as exc:
                refused += 1
                listed = ", ".join(_rel_site(p, paths) for p in exc.changed)
                print(f"PARTIAL:{name}|{listed}|restore failed after: {exc.cause}; "
                      "restore these files by hand")
                continue
            else:
                applied += 1
                print(f"APPLIED:{name}|{scene['output']}|pages={pages}")
                continue
        refused += 1
        print(f"REFUSED:{name}|{reason}")
    for failure in manifest.get("failed", []):
        print(f"SKIPPED:{failure['id']}|not staged ({_one_line(failure['reason'])})")
    print(f"APPLY:applied={applied} refused={refused} batch={manifest['batch']}")
    return 1 if refused else 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="screenshots.sh", description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--content", default=str(WEBSITE / "content"))
    parser.add_argument("--static", default=str(WEBSITE / "static"))
    parser.add_argument("--scenes", default=str(WEBSITE / "screenshots" / "scenes"))
    parser.add_argument("--staging", default=str(WEBSITE / "screenshots" / ".staging"))
    verbs = parser.add_subparsers(dest="verb", required=True)

    p_session = verbs.add_parser("session").add_subparsers(dest="action", required=True)
    start = p_session.add_parser("start")
    start.add_argument("--size", default="x".join(map(str, sessions.DEFAULT_SIZE)))
    start.add_argument("--dataset", default="base")
    start.add_argument("--window", help="name of the first window")
    start.set_defaults(func=cmd_session_start)
    stop = p_session.add_parser("stop")
    stop.add_argument("id", nargs="?")
    stop.add_argument("--all", action="store_true")
    stop.set_defaults(func=cmd_session_stop)
    p_session.add_parser("list").set_defaults(func=cmd_session_list)

    for name, func in (("setup", cmd_setup), ("run", cmd_run)):
        sub = verbs.add_parser(name)
        sub.add_argument("id")
        sub.add_argument("command", nargs=argparse.REMAINDER)
        sub.set_defaults(func=func)

    p_pane = verbs.add_parser("pane").add_subparsers(dest="action", required=True)
    split = p_pane.add_parser("split")
    split.add_argument("id")
    split.add_argument("--name", required=True)
    split.add_argument("--target")
    direction = split.add_mutually_exclusive_group()
    direction.add_argument("-H", "--side-by-side", dest="h", action="store_true",
                           help="new pane beside the target (tmux -h; the default)")
    direction.add_argument("-v", "--stacked", dest="v", action="store_true",
                           help="new pane below the target (tmux -v)")
    split.add_argument("-l", help="size of the new pane: cells (40) or a percentage (40%%)")
    split.add_argument("--full", action="store_true",
                       help="span the whole window (tmux -f)")
    split.set_defaults(command=[])
    split.set_defaults(func=cmd_pane_split)

    p_window = verbs.add_parser("window").add_subparsers(dest="action", required=True)
    new = p_window.add_parser("new")
    new.add_argument("id")
    new.add_argument("--name", required=True)
    new.add_argument("--role")
    new.set_defaults(command=[])
    new.set_defaults(func=cmd_window_new)

    def target_flags(sub, window: bool = True):
        group = sub.add_mutually_exclusive_group()
        group.add_argument("--pane")
        if window:
            group.add_argument("--window", nargs="?", const="")

    sub = verbs.add_parser("screen")
    sub.add_argument("id")
    target_flags(sub)
    sub.set_defaults(func=cmd_screen)

    sub = verbs.add_parser("keys")
    sub.add_argument("id")
    sub.add_argument("--pane")
    sub.add_argument("keys", nargs="+")
    sub.set_defaults(func=cmd_keys)

    sub = verbs.add_parser("wait")
    sub.add_argument("id")
    group = sub.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--gone")
    sub.add_argument("--timeout", type=float, default=sessions.DEFAULT_TIMEOUT)
    sub.add_argument("--pane")
    sub.set_defaults(func=cmd_wait)

    sub = verbs.add_parser("find")
    sub.add_argument("id")
    sub.add_argument("--text", required=True)
    sub.add_argument("--box", action="store_true")
    target_flags(sub)
    sub.set_defaults(func=cmd_find)

    sub = verbs.add_parser("shot")
    sub.add_argument("id")
    sub.add_argument("--scene", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--title", default=DEFAULT_TITLE)
    sub.add_argument("--png", action="store_true")
    sub.add_argument("--crop")
    sub.add_argument("--overlay", action="append", default=[])
    target_flags(sub)
    sub.set_defaults(func=cmd_shot)

    p_recipe = verbs.add_parser("recipe").add_subparsers(dest="action", required=True)
    save = p_recipe.add_parser("save")
    save.add_argument("id")
    save.add_argument("--scene", required=True)
    save.add_argument("--expect", action="append", required=True)
    save.add_argument("--illustrates", required=True)
    save.add_argument("--replace", action="store_true")
    save.set_defaults(func=cmd_recipe_save)

    sub = verbs.add_parser("replay")
    group = sub.add_mutually_exclusive_group(required=True)
    group.add_argument("--scene", action="append")
    group.add_argument("--all", action="store_true")
    group.add_argument("--pending", action="store_true")
    sub.add_argument("--no-keep", action="store_true")
    sub.add_argument("--png", action="store_true")
    sub.set_defaults(func=cmd_replay)

    sub = verbs.add_parser("preview")
    sub.add_argument("--batch", required=True)
    sub.set_defaults(func=cmd_preview)

    sub = verbs.add_parser("apply")
    sub.add_argument("--batch", required=True,
                     help="the batch that was reviewed; there is no default")
    sub.set_defaults(func=cmd_apply)

    verbs.add_parser("list").set_defaults(func=cmd_list)
    return parser


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    tail = None
    if "--" in argv:
        # The command after `--` is taken apart here, so a verb's options may
        # come after its session id (`pane split <id> --name m -- cmd`).
        cut = argv.index("--")
        argv, tail = argv[:cut], argv[cut + 1:]
    args = build_parser().parse_args(argv)
    if tail is not None:
        if not hasattr(args, "command"):
            print(f"REFUSED:`{args.verb}` takes no command after --")
            return 2
        args.command = tail
    paths = Paths(args)
    try:
        return args.func(args, paths)
    except (Refused, recipes.RecipeError) as exc:
        print(f"REFUSED:{_one_line(exc)}")
        return 1
    except (sessions.SessionError, sample_project.DatasetError) as exc:
        print(f"FAILED:{_one_line(exc)}")
        return 1
    except svg_export.ExportError as exc:
        print(f"FAILED:export|{_one_line(exc)}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
