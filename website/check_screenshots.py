#!/usr/bin/env python3
"""Check the docs' screenshot markers and image shortcode sources.

Doc authors mark the place a screenshot belongs with one single-line HTML
comment in the grammar `website/screenshots/markers.py` defines (documented in
`website/README.md`, "Screenshot Markers"). This checker reports, each record
with its page and line:

1. ``UNPARSEABLE`` -- a comment that mentions ``screenshot`` but is not a valid
   marker (a free-form TODO comment, a multi-line one, an inline one). Fails.
2. ``NO_SCENE`` -- a marker whose scene has no ``screenshots/scenes/<scene>.yaml``.
   Fails (``MISSING_SCENE_SEVERITY``).
3. ``OWNERSHIP`` -- a marker whose ``file=`` differs from its scene's
   ``output:``, two specs with the same ``output:``, or a spec whose ``id:`` /
   ``output:`` is missing, unsupported or (for ``id:``) differs from its file
   stem. Fails.
4. ``MISSING_IMAGE`` -- a ``static-img`` / ``split-hero`` / ``tour-tile`` image
   source with no file under ``static/``. ``hugo build`` and ``check_links.py``
   both pass a missing image. Fails.
5. ``UNRESOLVED`` -- every valid marker, i.e. a screenshot still to make.
   Listed; fails only under ``--strict``.

``--owners`` instead prints every file under ``static/imgs/`` with the scene
whose spec ``output:`` names it, or ``hand-made``.

Python 3 stdlib only, so it runs in the Hugo CI job with no setup.

Usage:
    python3 check_screenshots.py              # check, exit 1 on a failure
    python3 check_screenshots.py --strict     # unresolved markers fail too
    python3 check_screenshots.py --report     # records only, always exit 0
    python3 check_screenshots.py --owners     # image -> owning scene table
"""

from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from screenshots import markers as mk  # noqa: E402

#: Severity of a marker whose scene has no recipe: "error" fails the check,
#: "warning" lists it and keeps exit 0. Every scene named by a page has a
#: recipe, so a marker without one is a typo or a recipe that was never
#: recorded.
MISSING_SCENE_SEVERITY = "error"


def _rel(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def request_path(src: str) -> str:
    """The file under ``static/`` a browser requests for an image ``src``.

    The templates emit ``src`` through ``relURL`` unchanged, so the browser
    drops any ``?query`` / ``#fragment`` and percent-decodes the path. Checking
    the raw string instead would pass ``imgs/a#b.svg`` when a file of that
    literal name exists, although the browser requests ``imgs/a``.
    """
    return unquote(urlsplit(src).path).lstrip("/")


def load_specs(scenes: Path):
    """``{stem: SpecOwner}`` for every ``*.yaml`` directly under ``scenes``."""
    if not scenes.is_dir():
        return {}
    return {p.stem: mk.read_spec_owner(p) for p in sorted(scenes.glob("*.yaml"))}


def run_checks(content: Path, static: Path, scenes: Path):
    """Return ``(records, counts, failed_classes)``.

    ``records`` is a list of ``(class, location, detail)``.
    """
    records: list[tuple[str, str, str]] = []
    markers, bad = mk.scan(content)
    specs = load_specs(scenes)

    for u in bad:
        first = u.text.splitlines()[0] if u.text else ""
        records.append(("UNPARSEABLE", f"content/{u.path}:{u.line}", f"{u.reason}: {first.strip()}"))

    for stem, owner in specs.items():
        loc = f"scenes/{stem}.yaml"
        for problem in owner.problems:
            records.append(("OWNERSHIP", loc, problem))
        if owner.id is not None and owner.id != stem:
            records.append(("OWNERSHIP", loc, f"id {owner.id!r} differs from the file stem {stem!r}"))

    by_output = defaultdict(list)
    for stem, owner in specs.items():
        if owner.output is not None:
            by_output[owner.output].append(stem)
    for output, stems in sorted(by_output.items()):
        if len(stems) > 1:
            records.append(("OWNERSHIP", f"scenes/{stems[0]}.yaml",
                            f"output {output!r} is shared by scenes {', '.join(stems)}"))

    for m in markers:
        loc = f"content/{m.path}:{m.line}"
        owner = specs.get(m.scene)
        if owner is None:
            records.append(("NO_SCENE", loc, f"scene {m.scene!r} has no scenes/{m.scene}.yaml"))
        elif owner.output is not None and owner.output != m.file:
            records.append(("OWNERSHIP", loc,
                            f"file {m.file!r} differs from scene {m.scene!r} output {owner.output!r}"))

    for page, line, name, src in mk.scan_image_sources(content):
        loc = f"content/{page}:{line}"
        param = mk.IMAGE_SHORTCODES[name]
        if src is None:
            records.append(("MISSING_IMAGE", loc, f"{name} has no {param}= parameter"))
            continue
        requested = request_path(src)
        if not requested or not (static / requested).is_file():
            records.append(("MISSING_IMAGE", loc,
                            f"{name} {param}={src!r}: requests {requested!r}, no such file under static/"))

    for m in markers:
        records.append(("UNRESOLVED", f"content/{m.path}:{m.line}", f"scene={m.scene} file={m.file}"))

    counts = defaultdict(int)
    for cls, _, _ in records:
        counts[cls] += 1
    counts["markers"] = len(markers)

    failed = {"UNPARSEABLE", "OWNERSHIP", "MISSING_IMAGE"}
    if MISSING_SCENE_SEVERITY == "error":
        failed.add("NO_SCENE")
    return records, counts, failed


def owners_table(static: Path, scenes: Path) -> list[tuple[str, str]]:
    imgs = static / "imgs"
    by_output = {}
    for stem, owner in load_specs(scenes).items():
        if owner.output is not None:
            by_output.setdefault(owner.output, stem)
    rows = []
    if imgs.is_dir():
        for p in sorted(imgs.rglob("*")):
            if p.is_file():
                rel = p.relative_to(imgs).as_posix()
                rows.append((rel, by_output.get(rel, "hand-made")))
    return rows


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--strict", action="store_true",
                    help="also fail on unresolved (valid but not yet captured) markers")
    ap.add_argument("--report", action="store_true",
                    help="print the records only, then exit 0")
    ap.add_argument("--owners", action="store_true",
                    help="print each image under static/imgs/ with its owning scene, then exit 0")
    ap.add_argument("--content", type=Path, default=HERE / "content",
                    help="content tree to scan (default: content/ next to this script)")
    ap.add_argument("--static", type=Path, default=HERE / "static",
                    help="static tree images resolve against (default: static/)")
    ap.add_argument("--scenes", type=Path, default=HERE / "screenshots" / "scenes",
                    help="scene spec directory (default: screenshots/scenes/)")
    args = ap.parse_args(argv)

    if args.owners:
        for rel, owner in owners_table(args.static, args.scenes):
            print(f"{rel}\t{owner}")
        return 0

    if not args.content.is_dir():
        print(f"check_screenshots: no content tree at {args.content}", file=sys.stderr)
        return 2

    records, counts, failed = run_checks(args.content, args.static, args.scenes)
    if args.strict:
        failed = failed | {"UNRESOLVED"}

    for cls, loc, detail in records:
        print(f"{loc}: {cls}: {detail}")
    if args.report:
        return 0

    print(f"markers      : {counts['markers']}")
    print(f"unparseable  : {counts['UNPARSEABLE']}")
    print(f"no-scene     : {counts['NO_SCENE']} ({'error' if 'NO_SCENE' in failed else 'warning'})")
    print(f"ownership    : {counts['OWNERSHIP']}")
    print(f"missing-image: {counts['MISSING_IMAGE']}")
    print(f"unresolved   : {counts['UNRESOLVED']} ({'error' if 'UNRESOLVED' in failed else 'listed'})")
    fail = any(counts[c] for c in failed)
    print("SCREENSHOTS:", "FAILED" if fail else "PASSED")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
