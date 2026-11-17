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
    session stop (<id> | --all) / session list
    list

A pane ``P`` is a role (``main``, or a name given to ``pane split`` / ``window
new``) or ``<window name>.<pane index>`` for a pane the TUI created itself;
never a tmux id. ``--window`` without a name is the main pane's window.

Result lines are ``KEY:value`` (``SESSION:``, ``BATCH:``, ``SHOT:``, ``PNG:``,
``STAGED:``, ``FAILED:``, ``REFUSED:``, ``RECIPE_SAVED:``, ``BOX:``). Exit status:
0 done, 1 a capture, wait, replay or save failed or was refused (also when
``--png`` was asked and no preview could be made), 2 usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shlex
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
