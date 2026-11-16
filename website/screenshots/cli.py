"""Docs screenshot tool: primitives for an agent driving a real TUI.

Run through ``website/screenshots.sh`` (it picks the framework interpreter).

    session start [--size CxR] [--dataset NAME]     -> SESSION:<id>
    setup <id> -- <command>                         data preparation, before run
                                                    (one argument = a shell command
                                                    string; several = an argv)
    run <id> -- <command>                           launch the TUI (once)
    screen <id>                                     the pane as numbered text
    keys <id> <key>...                              tmux key names
    wait <id> (--text T | --gone T) [--timeout S]
    find <id> --text T [--box]                      CELL:<col>,<row> lines; with --box
                                                    BOX:<col>,<row>,<w>,<h> of the
                                                    innermost box around a unique text
    shot <id> --scene ID --output FILE [--title T] [--png]
             [--crop SPEC] [--overlay SPEC]...      SPEC is the recipe form as YAML flow
                                                    ('{cells: [1, 5, 40, 7], gutter: 30}');
                                                    --crop also takes C,R,W,H
    recipe save <id> --scene ID --expect T... --illustrates TEXT [--replace]
    replay (--scene ID... | --all | --pending) [--no-keep] [--png]
    session stop (<id> | --all) / session list
    list

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
from screenshots import svg_export, svgpost  # noqa: E402

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


def stable_capture(sess) -> str:
    """The pane with escapes, once two consecutive captures agree.

    A frame caught in the middle of a repaint is not a screenshot. A screen
    that never holds still for one poll interval is a failure, not a picture.
    """
    deadline = time.monotonic() + STABLE_TIMEOUT
    previous = sessions.capture(sess, ansi=True)
    while True:
        time.sleep(sessions.POLL_INTERVAL)
        current = sessions.capture(sess, ansi=True)
        if current == previous:
            return current
        if time.monotonic() >= deadline:
            raise sessions.SessionError(
                f"the screen did not hold still within {STABLE_TIMEOUT:g}s")
        previous = current


def _misplaced(rows, crop, overlays) -> list[str]:
    """Every ``holds`` text that is not inside its rectangle on ``rows``."""
    targets = ([("crop", crop)] if crop else []) + [
        (f"overlay {n}", item["target"]) for n, item in enumerate(overlays or (), start=1)]
    return [f"{where}: {target['holds']!r} not inside {target['cells']}"
            for where, target in targets
            if "holds" in target and not sessions.rect_holds(rows, target["cells"],
                                                             target["holds"])]


def export(sess, title: str, scene: str, expect=(), crop=None, overlays=None) -> str:
    """Export one settled frame that shows every text in ``expect``.

    The texts are checked together, on the very frame that becomes the image.
    Checking them one after another on the live screen would accept a text
    that was there a moment ago and is gone from the picture. The ``holds``
    texts of the crop and overlays are checked on that same frame, then the
    crop and overlays are applied to its SVG.
    """
    width, height = sess.size
    deadline = time.monotonic() + EXPECT_TIMEOUT
    while True:
        frame = stable_capture(sess)
        text = svg_export.ansi_plain_text(frame)
        missing = [wanted for wanted in expect if wanted not in text]
        misplaced = [] if missing else _misplaced(text.split("\n"), crop, overlays)
        if not missing and not misplaced:
            svg = svg_export.ansi_to_svg(frame, width, height, title=title, scene_id=scene)
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
                              origin="replay")
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
        for number, (kind, value, timeout) in enumerate(rec.steps, start=1):
            # A wait recorded with its own (longer) budget keeps it.
            budget = STEP_TIMEOUT if timeout is None else timeout
            try:
                if kind == "keys":
                    sessions.keys(sess, list(value))
                elif kind == "wait":
                    sessions.wait(sess, text=value, timeout=budget)
                else:
                    sessions.wait(sess, gone=value, timeout=budget)
            except sessions.SessionError as exc:
                return failed(f"step {number}", exc)
        try:
            svg = export(sess, rec.window_title, rec.id, rec.expect, rec.crop, rec.overlays)
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
    sess = sessions.start(paths.staging, size=_parse_size(args.size), dataset=args.dataset)
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


def _print_screen(sess) -> None:
    print(f"PANE:{sess.size[0]}x{sess.size[1]}|command={sessions.pane_command(sess)}"
          f"|origin={sess.origin}|launched={'yes' if sess.launched else 'no'}")
    for number, row in enumerate(sessions.screen_rows(sess)):
        print(f"{number:02d}|{row}")


def cmd_screen(args, paths):
    _print_screen(_session(args, paths))
    return 0


def cmd_keys(args, paths):
    sessions.keys(_session(args, paths), args.keys)
    print("KEYS_SENT")
    return 0


def cmd_wait(args, paths):
    sess = _session(args, paths)
    try:
        sessions.wait(sess, text=args.text, gone=args.gone, timeout=args.timeout)
    except sessions.WaitTimeout as exc:
        print(f"FAILED:wait|{_one_line(exc)}")
        _print_screen(sess)
        return 1
    print("WAIT_OK")
    return 0


def cmd_find(args, paths):
    sess = _session(args, paths)
    if args.box:
        c, r, w, h = sessions.box_around(sessions.screen_rows(sess), args.text)
        print(f"BOX:{c},{r},{w},{h}")
        return 0
    cells = sessions.find(sess, args.text)
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
    try:
        svg = export(sess, args.title, args.scene, (), crop, overlays)
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

    sub = verbs.add_parser("screen")
    sub.add_argument("id")
    sub.set_defaults(func=cmd_screen)

    sub = verbs.add_parser("keys")
    sub.add_argument("id")
    sub.add_argument("keys", nargs="+")
    sub.set_defaults(func=cmd_keys)

    sub = verbs.add_parser("wait")
    sub.add_argument("id")
    group = sub.add_mutually_exclusive_group(required=True)
    group.add_argument("--text")
    group.add_argument("--gone")
    sub.add_argument("--timeout", type=float, default=sessions.DEFAULT_TIMEOUT)
    sub.set_defaults(func=cmd_wait)

    sub = verbs.add_parser("find")
    sub.add_argument("id")
    sub.add_argument("--text", required=True)
    sub.add_argument("--box", action="store_true")
    sub.set_defaults(func=cmd_find)

    sub = verbs.add_parser("shot")
    sub.add_argument("id")
    sub.add_argument("--scene", required=True)
    sub.add_argument("--output", required=True)
    sub.add_argument("--title", default=DEFAULT_TITLE)
    sub.add_argument("--png", action="store_true")
    sub.add_argument("--crop")
    sub.add_argument("--overlay", action="append", default=[])
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
    args = build_parser().parse_args(argv)
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
