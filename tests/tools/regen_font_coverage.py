#!/usr/bin/env python3
"""Regenerate `tests/data/font_coverage.json` — the mark-glyph coverage evidence.

Why this exists, and why it is not `fc-list` (t1638)
----------------------------------------------------
`fc-list :charset=<cp> family` answers "does *some* locally installed family
cover this codepoint". That is not the question the mark policy asks, which is
"does **every** family in `mark_glyphs.SUPPORTED_FONTS` cover it". A machine
carrying DejaVu but neither Nerd Font would report full coverage while both
supported deployments fall back — the exact failure the policy exists to catch.

Worse, `fc-list` is not even reliable for the question it does answer: while
investigating t1638 it reported JetBrainsMono NF as *not* covering U+2714 when
that font's own `cmap` table contains it. Fontconfig's charset index can be
stale; the font file cannot.

So coverage is read straight from each font's `cmap` table by the reader below —
pure stdlib, no `fontTools` dependency, so it runs anywhere the repo's tests do.

The manifest records the **rejected** codepoints alongside the ratified ones.
That is deliberate: a manifest that only ever said `true` would be indistinguish-
able from a generator that always says `true`, and
`test_the_manifest_is_not_vacuous` exists to fail if it ever becomes that.

Usage
-----
    python tests/tools/regen_font_coverage.py            # rewrite the manifest
    python tests/tools/regen_font_coverage.py --check    # exit 1 if it is stale

Font files are located via `fc-match` (fontconfig is used only to *find* files,
never to answer coverage). Pass `--font-file "<family>=<path>"` to point at a
file directly on a box where the family is not installed under that name.
"""

from __future__ import annotations

import argparse
import json
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))

from mark_glyphs import (  # noqa: E402
    MARK_CHECKED,
    MARK_UNCHECKED,
    SUPPORTED_FONTS,
)

MANIFEST_PATH = REPO_ROOT / "tests" / "data" / "font_coverage.json"

#: Codepoints measured here IN ADDITION to the ratified multi-select pair —
#: rejections kept on purpose so the manifest can be shown to discriminate, plus
#: any glyph ratified elsewhere in the repo. It held only rejections until t1685
#: added the first non-rejection, which is why it is no longer named for them.
#:
#:   2610 / 2611  rejected — the t1638 defect itself (emoji-capable ☐/☑)
#:   2714         rejected — the replacement t1638 proposed, overruled by
#:                measurement (covered by one supported font, not both)
#:   2605 / 2606  the monitor's ★/☆ pair: covered by NEITHER supported font, so
#:                it resolves by fallback. Not emoji-capable, so not broken —
#:                the deferral t1638 recorded and t1639 will retire
#:   0050         CHOSEN (t1685) — `P`, the parked mark. Covered by every
#:                supported font and claimed by no emoji font
#:   23F8         rejected (t1685) — `⏸` is emoji-capable, i.e. the exact t1638
#:                invisible-glyph defect
#:   25A0         rejected (t1685) — `■` is covered, but collides visually with
#:                the monitor's state dot `●` two columns away
EXTRA_MEASURED_CODEPOINTS = (
    0x2610, 0x2611, 0x2714, 0x2605, 0x2606, 0x0050, 0x23F8, 0x25A0,
)


def ratified_codepoints() -> tuple[int, ...]:
    return tuple(ord(g) for g in (MARK_CHECKED, MARK_UNCHECKED))


# --- cmap reader ------------------------------------------------------------


def read_cmap(path: Path) -> set[int]:
    """Every codepoint in a TrueType/OpenType font's `cmap`.

    Handles subtable formats 4 (BMP) and 12 (full range) — between them these
    cover every glyph this repo draws. Other formats are skipped rather than
    guessed at; a font whose only subtable is exotic would report empty
    coverage, which fails loudly rather than passing quietly.
    """
    data = path.read_bytes()
    num_tables = struct.unpack_from(">H", data, 4)[0]
    cmap_off = None
    for i in range(num_tables):
        rec = 12 + 16 * i
        if data[rec:rec + 4] == b"cmap":
            cmap_off = struct.unpack_from(">I", data, rec + 8)[0]
            break
    if cmap_off is None:
        raise ValueError(f"{path}: no cmap table")

    covered: set[int] = set()
    n_sub = struct.unpack_from(">H", data, cmap_off + 2)[0]
    for i in range(n_sub):
        _pid, _eid, sub_off = struct.unpack_from(">HHI", data, cmap_off + 4 + 8 * i)
        sub_off += cmap_off
        fmt = struct.unpack_from(">H", data, sub_off)[0]
        if fmt == 4:
            seg_x2 = struct.unpack_from(">H", data, sub_off + 6)[0]
            seg = seg_x2 // 2
            ends = struct.unpack_from(f">{seg}H", data, sub_off + 14)
            starts = struct.unpack_from(f">{seg}H", data, sub_off + 16 + seg_x2)
            for start, end in zip(starts, ends):
                if start == 0xFFFF:
                    continue
                covered.update(range(start, end + 1))
        elif fmt == 12:
            n_groups = struct.unpack_from(">I", data, sub_off + 12)[0]
            for g in range(n_groups):
                start, end, _gid = struct.unpack_from(
                    ">III", data, sub_off + 16 + 12 * g
                )
                if end - start > 0x20000:      # a pathological group; skip
                    continue
                covered.update(range(start, end + 1))
    return covered


def font_version(path: Path) -> str:
    """The font's `name` ID 5 (version string), or "" if unreadable.

    Recorded for provenance only — nothing asserts on it. A coverage change
    without a version change is still a coverage change.
    """
    try:
        data = path.read_bytes()
        num_tables = struct.unpack_from(">H", data, 4)[0]
        for i in range(num_tables):
            rec = 12 + 16 * i
            if data[rec:rec + 4] != b"name":
                continue
            off = struct.unpack_from(">I", data, rec + 8)[0]
            count, string_off = struct.unpack_from(">HH", data, off + 2)
            for j in range(count):
                r = off + 6 + 12 * j
                pid, eid, _lid, nid, length, noff = struct.unpack_from(">6H", data, r)
                if nid != 5:
                    continue
                raw = data[off + string_off + noff: off + string_off + noff + length]
                enc = "utf-16-be" if (pid == 3 or pid == 0) else "latin-1"
                return raw.decode(enc, errors="replace").strip()
    except Exception:
        pass
    return ""


# --- font location ----------------------------------------------------------


def locate(family: str) -> Path | None:
    """Find a font file for `family` via fc-match.

    fontconfig is used only to LOCATE a file. It is never asked about coverage —
    see the module docstring for why that distinction is load-bearing.
    """
    try:
        out = subprocess.run(
            ["fc-match", "-f", "%{file}\t%{family}", f"{family}:style=Regular"],
            capture_output=True, text=True, timeout=10, check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if "\t" not in out:
        return None
    path_s, families = out.split("\t", 1)
    # fc-match ALWAYS returns something; confirm it actually gave us the family
    # asked for rather than its own fallback.
    short = family.replace(" Nerd Font", "").replace(" ", "")
    if short.lower() not in families.replace(" ", "").lower():
        return None
    p = Path(path_s)
    return p if p.is_file() else None


# --- manifest ---------------------------------------------------------------


def build(font_files: dict[str, Path]) -> dict:
    codepoints = sorted(set(ratified_codepoints()) | set(EXTRA_MEASURED_CODEPOINTS))
    coverage: dict[str, dict[str, bool]] = {}
    covered_by: dict[str, set[int]] = {
        fam: read_cmap(path) for fam, path in font_files.items()
    }
    for cp in codepoints:
        coverage[f"{cp:04X}"] = {
            fam: (cp in covered_by[fam]) for fam in SUPPORTED_FONTS
        }
    return {
        "generated_by": "tests/tools/regen_font_coverage.py",
        "note": (
            "Read from each font's cmap table, NOT from fc-list — see the "
            "generator's docstring. Rejected codepoints are recorded on purpose "
            "so the manifest can be shown to discriminate."
        ),
        "fonts": {
            fam: {
                "file": str(font_files[fam]),
                "version": font_version(font_files[fam]),
            }
            for fam in SUPPORTED_FONTS
        },
        "coverage": coverage,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the manifest is stale, write nothing")
    ap.add_argument("--font-file", action="append", default=[],
                    metavar="FAMILY=PATH",
                    help="explicit font file for a family")
    args = ap.parse_args(argv)

    overrides = {}
    for item in args.font_file:
        fam, _, path = item.partition("=")
        overrides[fam] = Path(path)

    font_files: dict[str, Path] = {}
    missing = []
    for fam in SUPPORTED_FONTS:
        path = overrides.get(fam) or locate(fam)
        if path is None or not path.is_file():
            missing.append(fam)
        else:
            font_files[fam] = path
    if missing:
        print(
            "ERROR: could not locate a font file for: " + ", ".join(missing)
            + "\nInstall the family, or pass --font-file 'FAMILY=/path/to.ttf'."
            + "\nThe manifest must be regenerated on a machine that has every"
            + " family in mark_glyphs.SUPPORTED_FONTS — a partial regeneration"
            + " would silently narrow the coverage claim.",
            file=sys.stderr,
        )
        return 2

    manifest = build(font_files)
    rendered = json.dumps(manifest, indent=2, sort_keys=True) + "\n"

    if args.check:
        current = MANIFEST_PATH.read_text(encoding="utf-8") if MANIFEST_PATH.exists() else ""
        # Compare coverage only: `file` paths and versions differ per machine.
        try:
            same = json.loads(current)["coverage"] == manifest["coverage"]
        except (ValueError, KeyError):
            same = False
        if not same:
            print("STALE: tests/data/font_coverage.json does not match the fonts"
                  " on this machine", file=sys.stderr)
            return 1
        print("FRESH")
        return 0

    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(rendered, encoding="utf-8")
    print(f"WROTE:{MANIFEST_PATH.relative_to(REPO_ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
