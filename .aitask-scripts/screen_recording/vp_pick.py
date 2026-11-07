"""pick: a static HTML+JS page for choosing frames by eye (aitask-screen-recording).

  aitask_screen_recording.sh pick <frames-dir|run-dir> [--open] [--out DIR]

The page is built once, offline, with no server: <out>/index.html shows every
frame of a bug/frames/anim run (or of any folder of images), the user selects
some, may mark a start and an end frame and drag a rectangle, then copies a
plain-text block of absolute paths back to the agent.

Rules the page applies are decided here and embedded as data, so they are
testable without a browser; pick_logic.js repeats only the arithmetic and the
concatenation (copy_block / roi_to_source below are its reference):

- the picker certifies nothing: a selection is a *viewing range*; a --window is
  written only for frames the user marked, labelled "user-marked endpoints
  (unverified)"; nothing here looks at pixels;
- a rectangle becomes a source-video --roi only through a frames.tsv row whose
  SHA-256 equals the hash of the picker's own snapshot of the image;
- images are snapshotted into <out>/src/ first and everything is derived from
  the snapshot, so a concurrent rewrite of the originals cannot mix versions.
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_core as core  # noqa: E402

PICK_VERSION = 1
ASSETS = Path(__file__).resolve().parent
NOTE_MAX = 200
SAFE_NAME = re.compile(r"[A-Za-z0-9_()+][A-Za-z0-9._()+ -]*")
SEGMENT_LABEL = re.compile(r"[sw]\d{2,}")
WINDOW_LABEL = "user-marked endpoints (unverified)"
VIEW_LABEL = "viewing range"
MANIFEST_INT_FIELDS = ("src_w", "src_h", "crop_x", "crop_y", "crop_w", "crop_h", "out_w", "out_h")

# every sentence the copy block uses; the page reads them from the data, so the
# wording exists once (here) and pick_logic.js only concatenates
TEXT = {
    "none_selected": "# no frames selected in {page}",
    "picked": "# {n} {frames} picked in {page} (set {set})",
    "view": "# " + VIEW_LABEL + ": {a}-{b} s (first to last selected frame; a viewing range, "
            "not a measurement window)",
    "view_unknown": "# " + VIEW_LABEL + ": unknown (the selected names carry no time)",
    "window": "# --window {a}-{b}  (" + WINDOW_LABEL + ": start {start} at {sms} ms, end {end} "
              "at {ems} ms; check the anim run's own endpoint diagnostics before trusting it"
              "{extra})",
    "window_pts_time": "; their times come from ffmpeg's printed pts_time, which older "
                       "versions round past 1000 s",
    "no_window": "# no --window: {why}",
    "why_one_mark": "mark both a start and an end frame",
    "why_same": "the start and end marks are the same frame",
    "why_untimed": "a marked frame carries no time in its name",
    "why_order": "the end frame is not after the start frame",
    "roi": "# --roi {x},{y},{w},{h}  (source-video pixels, mapped through the frames.tsv "
           "geometry of {name}, SHA-256 verified)",
    "own_rect": "# rectangle {x},{y},{w},{h} in {name}'s own pixels, not source-video pixels "
                "(source --roi disabled: {why})",
}


class PickError(RuntimeError):
    """Raised for user-facing failures; video_prep maps it onto its PrepError."""


# --------------------------------------------------------------------------- #
# small pure helpers (each mirrored by pick_logic.js where the page needs it)

_CONTROL = {c for c in range(32)} | {127} | set(range(0x80, 0xA0)) | {0x2028, 0x2029}


def display(text: str) -> str:
    """Text safe for one line of the copy block or a Markdown cell: control
    characters (and lone surrogates from undecodable names) become '?'."""
    return "".join("?" if (ord(c) in _CONTROL or 0xD800 <= ord(c) <= 0xDFFF) else c
                   for c in text)


def sanitize_note(text) -> str:
    """A user's note as one line: control characters become spaces, ASCII spaces
    are trimmed, at most NOTE_MAX characters."""
    if not isinstance(text, str):
        return ""
    s = "".join(" " if ord(c) in _CONTROL else c for c in text).strip(" ")
    return s[:NOTE_MAX].rstrip(" ")


def seconds(ms: int) -> str:
    """ms as seconds with three decimals, by integer arithmetic (the page does the same)."""
    return f"{ms // 1000}.{ms % 1000:03d}"


def window_bounds(ms: int) -> tuple[str, str]:
    """--window START and END around one frame whose name carries `ms`. The exact
    time is within 0.5 ms of a name's rounded ms, so (ms - 0.5) ms <= t <=
    (ms + 0.5) ms: START taken from the start frame and END from the end frame
    include both, and exclude their neighbours while frames are more than about
    1.2 ms apart (anim widens the window by 0.1 ms on each side)."""
    def fmt(n2000: int) -> str:            # n / 2000 s, exactly (at most 4 decimals)
        v = n2000 * 5                      # in units of 0.1 ms
        s = f"{v // 10000}.{v % 10000:04d}".rstrip("0").rstrip(".")
        return s
    return fmt(max(0, 2 * ms - 1)), fmt(2 * ms + 1)


_INT_TEXT = re.compile(r" *[-+]?[0-9]+ *")


def _to_int(v) -> int | None:
    """An integer from page state, as pick_logic.js toInt reads it: a finite
    number truncated, or ASCII digits; anything else (bools included) is None."""
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(v) if v == v and v not in (float("inf"), float("-inf")) else None
    if isinstance(v, str) and _INT_TEXT.fullmatch(v):
        return int(v)
    return None


def norm_rect(rect, w: int | None, h: int | None):
    """(x0, y0, x1, y1) in image pixels, ordered, truncated to integers and
    clamped to the image when its size is known; None when empty or invalid."""
    if not isinstance(rect, dict):
        return None
    vals = [_to_int(rect.get(k)) for k in ("x0", "y0", "x1", "y1")]
    if any(v is None for v in vals):
        return None
    a, b, c, d = vals
    x0, x1 = min(a, c), max(a, c)
    y0, y1 = min(b, d), max(b, d)
    if w is not None and h is not None:
        x0, x1 = max(0, min(x0, w)), max(0, min(x1, w))
        y0, y1 = max(0, min(y0, h)), max(0, min(y1, h))
    if x1 - x0 < 1 or y1 - y0 < 1:
        return None
    return x0, y0, x1, y1


def roi_to_source(rect: tuple[int, int, int, int], geom: dict) -> tuple[int, int, int, int]:
    """The --roi X,Y,W,H in source-video (display) pixels that covers an image
    rectangle [x0,x1) x [y0,y1), through the image's frames.tsv geometry: src =
    crop offset + px * crop / out, rounded outward, clamped to the source and
    never empty, so the result always passes video_prep.region_box."""
    x0, y0, x1, y1 = rect
    cx, cy, cw, ch = geom["crop_x"], geom["crop_y"], geom["crop_w"], geom["crop_h"]
    ow, oh, sw, sh = geom["out_w"], geom["out_h"], geom["src_w"], geom["src_h"]
    X0 = cx + (x0 * cw) // ow
    X1 = cx + -((-x1 * cw) // ow)
    Y0 = cy + (y0 * ch) // oh
    Y1 = cy + -((-y1 * ch) // oh)
    X0 = max(0, min(X0, sw - 1))
    Y0 = max(0, min(Y0, sh - 1))
    X1 = max(X0 + 1, min(X1, sw))
    Y1 = max(Y0 + 1, min(Y1, sh))
    return X0, Y0, X1 - X0, Y1 - Y0


def storage_key(data: dict) -> str:
    return f"vp-pick:v{PICK_VERSION}:{data['fingerprint']}"


def copy_block(data: dict, state: dict) -> str:
    """The paste-ready text for a selection (reference for pick_logic.js copyBlock:
    the two must agree byte for byte). state: selected [rel], marks {start, end},
    notes {rel: text}, rect {rel, x0, y0, x1, y1} or None."""
    T = data["text"]
    frames = data["frames"]
    by_rel = {f["rel"]: f for f in frames}
    state = state or {}
    sel = {s for s in (state.get("selected") or []) if isinstance(s, str)}
    chosen = [f for f in frames if f["rel"] in sel]
    if not chosen:
        return T["none_selected"].format(page=data["page"]) + "\n"
    n = len(chosen)
    lines = [T["picked"].format(n=n, frames="frame" if n == 1 else "frames", page=data["page"],
                                set=data["fingerprint"][:8])]
    timed = [f["ms"] for f in chosen if f["ms"] is not None]
    if timed:
        lines.append(T["view"].format(a=seconds(min(timed)), b=seconds(max(timed))))
    else:
        lines.append(T["view_unknown"])
    notes = state.get("notes") or {}
    prev = None
    for f in chosen:
        parts = [f["path"]]
        if f["ms"] is None:
            parts.append("t=unknown")
        else:
            parts.append(f"t={f['ms']} ms")
            if prev is None:
                parts.append("first")
            else:
                d = f["ms"] - prev
                parts.append(("+" if d >= 0 else "") + f"{d} ms")
            prev = f["ms"]
        note = sanitize_note(notes.get(f["rel"]) if isinstance(notes, dict) else None)
        if note:
            parts.append("note: " + note)
        lines.append("\t".join(parts))

    marks = state.get("marks") if isinstance(state.get("marks"), dict) else {}
    s_rel, e_rel = marks.get("start"), marks.get("end")
    if s_rel or e_rel:
        fs = by_rel.get(s_rel) if isinstance(s_rel, str) else None
        fe = by_rel.get(e_rel) if isinstance(e_rel, str) else None
        why = None
        if fs is None or fe is None:
            why = T["why_one_mark"]
        elif fs is fe:
            why = T["why_same"]
        elif fs["ms"] is None or fe["ms"] is None:
            why = T["why_untimed"]
        elif fs["ms"] >= fe["ms"]:
            why = T["why_order"]
        if why:
            lines.append(T["no_window"].format(why=why))
        else:
            extra = (T["window_pts_time"] if "pts_time" in (fs["time_source"], fe["time_source"])
                     else "")
            lines.append(T["window"].format(a=fs["window_start"], b=fe["window_end"],
                                            start=fs["display_name"], sms=fs["ms"],
                                            end=fe["display_name"], ems=fe["ms"], extra=extra))

    rect = state.get("rect")
    if isinstance(rect, dict) and isinstance(rect.get("rel"), str) and rect["rel"] in by_rel:
        f = by_rel[rect["rel"]]
        r = norm_rect(rect, f["w"], f["h"])
        if r is not None:
            if f["geom"]:
                x, y, w, h = roi_to_source(r, f["geom"])
                lines.append(T["roi"].format(x=x, y=y, w=w, h=h, name=f["display_name"]))
            else:
                lines.append(T["own_rect"].format(x=r[0], y=r[1], w=r[2] - r[0], h=r[3] - r[1],
                                                  name=f["display_name"],
                                                  why=f["roi_disabled"]))
    lines.append(data["source_line"])
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# input resolution

def _images_in(d: Path) -> tuple[list[Path], list[str]]:
    images, ignored = [], []
    for p in sorted(d.iterdir(), key=lambda p: core.natural_key(p.name)):
        if p.name in ("frames.tsv", "run.json", "summary.md"):
            continue
        if (p.name.startswith(".") or not p.is_file()
                or p.suffix.lower() not in core.IMAGE_EXTS):
            ignored.append(p.name + ("/" if p.is_dir() else ""))
        else:
            images.append(p)
    return images, ignored


def _read_run(path: Path) -> dict | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8", errors="surrogateescape"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _segment_dirs(root: Path) -> list[Path]:
    try:
        entries = list(root.iterdir())
    except OSError:
        return []
    return sorted((d for d in entries if SEGMENT_LABEL.fullmatch(d.name) and (d / "frames").is_dir()),
                  key=lambda d: core.natural_key(d.name))


def resolve_groups(root: Path) -> tuple[list[tuple[str, Path]], Path | None, str]:
    """[(group label, frames dir)], the run dir whose run.json describes them
    (or None), and which layout matched. Run layouts are recognised before a
    plain image folder: a bug run keeps its contact sheets in the run root beside
    frames/, and those must never be taken for the frames."""
    run = _read_run(root / "run.json")
    mode = run.get("mode") if run else None
    if mode in ("bug", "frames"):
        fd = root / "frames"
        if not fd.is_dir():
            raise PickError(f"{root} is a {mode} run, but {fd} is missing")
        return [("", fd)], root, f"{mode} run: frames/"
    if mode == "anim":
        segs = _segment_dirs(root)
        if not segs:
            raise PickError(f"{root} is an anim run, but it has no sNN/frames or wNN/frames "
                            "directory")
        return ([(d.name, d / "frames") for d in segs], root,
                "anim run: " + ", ".join(f"{d.name}/frames/" for d in segs))
    if mode in ("sheet", "pick"):
        made_from = run.get("dir") if mode == "sheet" else None
        raise PickError(f"{root} is a {mode} output; pick the folder it was made from"
                        + (f" ({made_from})" if isinstance(made_from, str) else ""))
    # no usable run.json: the same layouts, recognised by their shape
    fd = root / "frames"
    if fd.is_dir() and _images_in(fd)[0]:
        return [("", fd)], root, "frames/ (no run.json)"
    segs = [d for d in _segment_dirs(root) if _images_in(d / "frames")[0]]
    if segs:
        return ([(d.name, d / "frames") for d in segs], root,
                ", ".join(f"{d.name}/frames/" for d in segs) + " (no run.json)")
    if _images_in(root)[0]:
        # a frames dir handed over directly: its run is the parent (bug/frames)
        # or the grandparent (anim sNN/wNN)
        run_dir = None
        if root.name == "frames":
            par = root.parent
            pr = _read_run(par / "run.json")
            if pr and pr.get("mode") in ("bug", "frames"):
                run_dir = par
            elif SEGMENT_LABEL.fullmatch(par.name):
                gr = _read_run(par.parent / "run.json")
                if gr and gr.get("mode") == "anim":
                    run_dir = par.parent
        return [("", root)], run_dir, "image folder"
    raise PickError(f"no png, jpg or webp images in {root}, {root}/frames or "
                    f"{root}/{{sNN,wNN}}/frames")


def source_info(run: dict | None) -> dict:
    """What the copy block may say about the recording. A video is named only
    from a path the producer proved (video_abspath, resolved in its own working
    directory, with the size it had); a relative path is never re-resolved
    against pick's working directory, where a same-named file may be another
    recording."""
    if run is None:
        return {"mode": None, "video": None, "why": "no run.json found for these frames",
                "hint": None}
    mode = run.get("mode") if isinstance(run.get("mode"), str) else None
    out = {"mode": mode, "video": None, "why": None, "hint": None}
    if run.get("input") == "images":
        # bug/anim on a folder of images: there is no recording to name
        folder = run.get("input_dir_abspath")
        out["why"] = ("the run read a folder of images"
                      + (f" ({folder})" if isinstance(folder, str) else "") + ", not a video")
        return out
    ab, size = run.get("video_abspath"), run.get("video_size")
    if isinstance(ab, str) and os.path.isabs(ab):
        p = Path(ab)
        if not p.is_file():
            out["why"] = f"the recorded video {ab} is missing"
        elif (not isinstance(size, int) or isinstance(size, bool)
              or p.stat().st_size != size):
            out["why"] = f"the file at {ab} changed since extraction (its size differs)"
        else:
            out["video"] = ab
        return out
    rec = (run.get("options") or {}).get("video") if isinstance(run.get("options"), dict) else None
    if not isinstance(rec, str):
        v = run.get("video")
        rec = v.get("path") if isinstance(v, dict) else None
    if isinstance(rec, str) and os.path.isabs(rec):
        out["why"] = "run.json records no verified path for the video"
        out["hint"] = rec
    elif isinstance(rec, str):
        out["why"] = f"recorded as '{rec}' relative to an unknown directory"
    else:
        out["why"] = "run.json names no video"
    return out


def source_line(src: dict) -> str:
    what = f"{src['mode']} run of " if src["mode"] else ""
    if src["video"]:
        return display(f"# source: {what}{src['video']}")
    line = f"# source: {what}<VIDEO> ({src['why']}"
    if src["hint"]:
        line += f"; recorded path, unverified: {src['hint']}"
    return display(line + ")")


# --------------------------------------------------------------------------- #
# snapshot

@dataclass
class Snap:
    group: str
    name: str            # the original file name
    dest: str            # the snapshot's file name
    rel: str             # path under src/
    path: Path           # absolute snapshot path
    origin: Path         # the original file
    sha256: str
    png: tuple[int, int] | None


def allocate_names(names: list[str]) -> dict[str, str]:
    """A unique snapshot name for every input name of one directory: a safe name
    is kept unless another kept name already claims it case-folded (a
    case-insensitive file system would merge them); every other name gets the
    first renamed_NNNN<ext> no kept or generated name claims."""
    out, reserved = {}, set()
    pending = []
    for n in names:
        if SAFE_NAME.fullmatch(n) and n.casefold() not in reserved:
            out[n] = n
            reserved.add(n.casefold())
        else:
            pending.append(n)
    k = 1
    for n in pending:
        ext = Path(n).suffix.lower()
        while True:
            cand = f"renamed_{k:04d}{ext}"
            k += 1
            if cand.casefold() not in reserved:
                break
        reserved.add(cand.casefold())
        out[n] = cand
    return out


def _copy_file(src: Path, dest: Path) -> None:
    """Copy into a destination that must not exist yet (exclusive create)."""
    with open(src, "rb") as fi, open(dest, "xb") as fo:
        shutil.copyfileobj(fi, fo)


def snapshot(groups: list[tuple[str, list[Path]]], src_dir: Path) -> list[Snap]:
    snaps = []
    for group, images in groups:
        gdir = src_dir / group if group else src_dir
        gdir.mkdir(parents=True, exist_ok=True)
        names = allocate_names([p.name for p in images])
        for p in images:
            dest = gdir / names[p.name]
            try:
                _copy_file(p, dest)
            except FileExistsError as exc:
                raise PickError(f"snapshot name {dest.name} is already taken in {gdir}") from exc
            except OSError as exc:
                raise PickError(f"cannot copy {display(str(p))}: {exc}") from exc
            # everything below is derived from the copy, never from the original
            data = dest.read_bytes()
            snaps.append(Snap(group, p.name, dest.name,
                              f"{group}/{dest.name}" if group else dest.name,
                              dest.resolve(), p, hashlib.sha256(data).hexdigest(),
                              core.png_size(data[:24])))
    paths = [s.path for s in snaps]
    if len(set(paths)) != len(paths):
        raise PickError("two snapshots share a path")
    return snaps


def fingerprint(snaps: list[Snap]) -> str:
    h = hashlib.sha256(f"vp-pick-v{PICK_VERSION}\n".encode())
    for line in sorted(f"{s.rel}\t{s.sha256}\n" for s in snaps):
        h.update(line.encode("utf-8", "surrogateescape"))
    return h.hexdigest()[:16]


# --------------------------------------------------------------------------- #
# geometry trust

def read_frames_tsv(folder: Path) -> tuple[dict | None, str | None]:
    """{file: row} from folder/frames.tsv, or (None, why) when there is none."""
    path = folder / "frames.tsv"
    if not path.is_file():
        return None, "no frames.tsv beside the image"
    try:
        with open(path, newline="", encoding="utf-8", errors="surrogateescape") as fh:
            rows = list(csv.DictReader(fh, delimiter="\t"))
    except (OSError, csv.Error) as exc:
        return None, f"frames.tsv could not be read ({exc})"
    return {r["file"]: r for r in rows if r.get("file")}, None


def geometry(snap: Snap, rows: dict | None, error: str | None) -> tuple[dict | None, str | None]:
    """The frame's trusted geometry, or None and the reason the source --roi is
    disabled. Trust needs a frames.tsv row whose SHA-256 equals the snapshot's:
    any edit (a crop resized back to the same size, a shift inside the canvas)
    changes the hash, and no corrected transform is accepted for an edited image."""
    name = display(snap.name)
    if rows is None:
        return None, error
    row = rows.get(snap.name)
    if row is None:
        return None, f"frames.tsv has no row for {name}"
    try:
        geom = {k: int(row[k]) for k in MANIFEST_INT_FIELDS}
        want = str(row["sha256"]).strip().lower()
    except (KeyError, TypeError, ValueError):
        return None, f"frames.tsv row for {name} is malformed"
    if (min(geom["crop_w"], geom["crop_h"], geom["out_w"], geom["out_h"],
            geom["src_w"], geom["src_h"]) < 1 or geom["crop_x"] < 0 or geom["crop_y"] < 0
            or geom["crop_x"] + geom["crop_w"] > geom["src_w"]
            or geom["crop_y"] + geom["crop_h"] > geom["src_h"]
            or not re.fullmatch(r"[0-9a-f]{64}", want)):
        return None, f"frames.tsv row for {name} is malformed"
    if snap.sha256 != want:
        return None, (f"the image changed since extraction: its SHA-256 {snap.sha256[:12]} "
                      f"differs from frames.tsv {want[:12]}")
    if snap.png is None:
        return None, "not a PNG"
    if snap.png != (geom["out_w"], geom["out_h"]):
        return None, (f"its size {snap.png[0]}x{snap.png[1]} differs from frames.tsv "
                      f"{geom['out_w']}x{geom['out_h']}")
    return geom, None


# --------------------------------------------------------------------------- #
# page data and rendering

def build_data(snaps: list[Snap], groups: list[tuple[str, Path]], page: Path, out: Path,
               src: dict, layout: str) -> dict:
    manifests = {g: read_frames_tsv(d) for g, d in groups}
    by_group: dict[str, list[Snap]] = {}
    for s in snaps:
        by_group.setdefault(s.group, []).append(s)
    frames = []
    for g, _ in groups:
        gs = {s.name: s for s in by_group.get(g, [])}
        plan = core.plan_sheet(list(gs))
        rows, err = manifests[g]
        for it in plan.items:
            s = gs[it.name]
            geom, why = geometry(s, rows, err)
            row = (rows or {}).get(s.name) or {}
            if it.ms is None:
                label = "no time in name"
                ws = we = None
            else:
                label = f"{seconds(it.ms)} s " + ("first" if it.delta_ms is None
                                                  else f"+{it.delta_ms} ms")
                ws, we = window_bounds(it.ms)
            ts = row.get("time_source") if isinstance(row.get("time_source"), str) else None
            frames.append({
                "rel": s.rel, "name": s.name, "display_name": display(s.name),
                "group": g, "order": it.order, "ms": it.ms, "delta_ms": it.delta_ms,
                "label": label, "path": str(s.path),
                "url": "src/" + "/".join(quote(seg, safe="") for seg in s.rel.split("/")),
                "sha256": s.sha256,
                "w": s.png[0] if s.png else None, "h": s.png[1] if s.png else None,
                "geom": geom, "roi_disabled": why, "time_source": ts,
                "window_start": ws, "window_end": we,
            })
    data = {
        "version": PICK_VERSION, "page": str(page), "out": str(out),
        "fingerprint": fingerprint(snaps), "layout": layout,
        "groups": [{"label": g, "source_dir": str(d.resolve()),
                    "frames": sum(1 for f in frames if f["group"] == g)} for g, d in groups],
        "source": src, "source_line": source_line(src),
        "text": TEXT, "frames": frames,
    }
    data["storage_key"] = storage_key(data)
    return data


BS = chr(92)                      # a backslash, spelled so no editor or tool decodes it
JSON_SCRIPT_ESCAPES = {"<": BS + "u003c", ">": BS + "u003e", "&": BS + "u0026"}
PLACEHOLDERS = ("@DATA@", "/*@LOGIC@*/", "/*@UI@*/")


def script_json(data: dict) -> str:
    """JSON that is inert inside <script type="application/json">: the HTML
    tokenizer ends script data at the first '</script' whatever the JSON means,
    so '<', '>' and '&' (which JSON allows only inside strings) are written as
    their JSON escapes; ensure_ascii escapes U+2028/2029 and everything else."""
    text = json.dumps(data, ensure_ascii=True)
    for ch, esc in JSON_SCRIPT_ESCAPES.items():
        text = text.replace(ch, esc)
    if any(ch in text for ch in "<>&"):
        raise PickError("page data could not be escaped for the page")
    return text


def render_page(data: dict, assets: Path = ASSETS) -> str:
    template = (assets / "pick_page.html").read_text(encoding="utf-8")
    logic = (assets / "pick_logic.js").read_text(encoding="utf-8")
    ui = (assets / "pick_ui.js").read_text(encoding="utf-8")
    for ph in PLACEHOLDERS:
        if template.count(ph) != 1:
            raise PickError(f"pick_page.html must hold {ph} exactly once")
    for name, js in (("pick_logic.js", logic), ("pick_ui.js", ui)):
        if "</script" in js.lower() or "<!--" in js:
            raise PickError(f"{name} contains a sequence that would end its script element")
    parts = {"@DATA@": script_json(data), "/*@LOGIC@*/": logic, "/*@UI@*/": ui}
    # one pass, so text inserted for one placeholder is never searched for another
    rx = re.compile("|".join(re.escape(p) for p in PLACEHOLDERS))
    return rx.sub(lambda m: parts[m.group(0)], template)


# --------------------------------------------------------------------------- #
# opener

def _platform_kind(platform: str, proc_version: str | None) -> str:
    if platform == "darwin":
        return "darwin"
    if platform.startswith("linux"):
        if proc_version is None:
            try:
                proc_version = Path("/proc/version").read_text(errors="replace")
            except OSError:
                proc_version = ""
        # as lib/terminal_compat.sh ait_is_wsl does
        return "wsl" if "microsoft" in proc_version.lower() else "linux"
    return platform


def _open_darwin(path, which, wslpath):
    return (["open", path], True) if which("open") else None


def _open_linux(path, which, wslpath):
    return (["xdg-open", path], True) if which("xdg-open") else None


def _open_wsl(path, which, wslpath):
    if which("wslview"):
        return ["wslview", path], True
    if which("explorer.exe") and which("wslpath"):
        win = wslpath(path)
        # explorer.exe's exit status says nothing about success (it is 1 when it works)
        return (["explorer.exe", win], False) if win else None
    return None


# platform -> (opener named in messages, argv builder)
OPENERS = {
    "darwin": ("open", _open_darwin),
    "linux": ("xdg-open", _open_linux),
    "wsl": ("wslview, or explorer.exe with wslpath", _open_wsl),
}


def _spawn(argv: list[str]) -> int | None:
    """Start the opener detached; its exit code within 5 s, or None while it runs
    (some browsers keep the launching process for their lifetime)."""
    p = subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        return p.wait(timeout=5)
    except subprocess.TimeoutExpired:
        p.returncode = 0          # left running on purpose; do not warn about it
        return None


def _wslpath(path: str) -> str | None:
    try:
        cp = subprocess.run(["wslpath", "-w", path], capture_output=True, text=True,
                            stdin=subprocess.DEVNULL)
    except OSError:
        return None
    return cp.stdout.strip() if cp.returncode == 0 and cp.stdout.strip() else None


def open_page(path: str, *, env=None, platform: str | None = None, which=shutil.which,
              proc_version: str | None = None, spawn=_spawn, wslpath=_wslpath) -> tuple[bool, str]:
    """Open the page in the user's browser when there is a display to show it on.
    Returns (opened, detail); never raises for an opener problem."""
    env = os.environ if env is None else env
    platform = sys.platform if platform is None else platform
    if any(env.get(k) for k in ("SSH_CONNECTION", "SSH_CLIENT", "SSH_TTY")):
        return False, ("no display: this is an SSH session, so a browser would open on the "
                       "remote machine, if anywhere")
    kind = _platform_kind(platform, proc_version)
    if kind == "linux" and not (env.get("DISPLAY") or env.get("WAYLAND_DISPLAY")):
        return False, "no display: neither DISPLAY nor WAYLAND_DISPLAY is set"
    entry = OPENERS.get(kind)
    if entry is None:
        return False, f"no browser opener for platform {platform}"
    label, build = entry
    got = build(path, which, wslpath)
    if got is None:
        return False, f"no opener found ({label} is not on PATH)"
    argv, exit_counts = got
    try:
        rc = spawn(argv)
    except OSError as exc:
        return False, f"could not start {argv[0]}: {exc}"
    if rc not in (None, 0) and exit_counts:
        return False, f"{argv[0]} exited with status {rc}"
    return True, argv[0]


# --------------------------------------------------------------------------- #
# the subcommand

def _has_control(text: str) -> bool:
    return any(ord(c) in _CONTROL for c in text)


def cmd_pick(args, *, make_out_dir) -> int:
    root = Path(args.dir)
    groups, run_dir, layout = resolve_groups(root)
    images = []
    ignored = []
    for g, d in groups:
        imgs, ign = _images_in(d)
        images.append((g, imgs))
        ignored += [f"{g}/{n}" if g else n for n in ign]
    total = sum(len(i) for _, i in images)
    if not total:
        raise PickError("no png, jpg or webp images in "
                        + ", ".join(str(d) for _, d in groups))
    src = source_info(_read_run(run_dir / "run.json") if run_dir else None)

    name = (run_dir or root).resolve().name or "folder"
    out = make_out_dir(args.out, str(root), "pick", name=name).resolve()
    try:
        if _has_control(str(out)):
            raise PickError(f"the output path {display(str(out))} contains control characters, "
                            "which the copy block cannot carry on one line")
        snaps = snapshot(images, out / "src")
        page = out / "index.html"
        data = build_data(snaps, groups, page, out, src, layout)
        page.write_text(render_page(data), encoding="utf-8")
        (out / "pick.json").write_text(json.dumps(data, indent=2, ensure_ascii=True) + "\n")
    except BaseException:
        shutil.rmtree(out, ignore_errors=True)
        raise

    frames = data["frames"]
    trusted = [f for f in frames if f["geom"]]
    disabled = [f for f in frames if not f["geom"]]
    renamed = [s for s in snaps if s.name != s.dest]
    opened, detail = (open_page(str(page)) if args.open
                      else (False, "not requested (--open not given)"))

    lines = [f"# Frame picker: {display((run_dir or root).resolve().name)}", "",
             f"- page: {page} (static, no server; open it in any browser)",
             f"- input: {display(str(root.resolve()))} ({layout})",
             f"- {len(frames)} frames in "
             + ", ".join(f"{g['label'] or 'frames'} ({g['frames']})" for g in data["groups"])
             + "; copied into src/ before anything else was read, so the page shows exactly "
               "the bytes it hashed",
             f"- {data['source_line'][2:]}",
             "- the picker certifies nothing: a selection is a viewing range; a --window is "
             "written only for frames the user marked, labelled \"" + WINDOW_LABEL + "\"; "
             "the anim run's own endpoint diagnostics decide whether to trust it",
             f"- source --roi available for {len(trusted)} of {len(frames)} frames (a frames.tsv "
             "row whose SHA-256 equals the snapshot's)"]
    if renamed:
        lines.append(f"- {len(renamed)} images were copied under generated names (their names "
                     "hold characters the copy block cannot carry): "
                     + ", ".join(f"{display(s.name)} -> {s.dest}" for s in renamed[:5])
                     + (" ..." if len(renamed) > 5 else ""))
    if ignored:
        lines.append(f"- ignored {len(ignored)} entries that are not png/jpg/webp images: "
                     + ", ".join(display(n) for n in ignored[:5])
                     + (" ..." if len(ignored) > 5 else ""))
    lines.append(f"- browser: {'opened (' + detail + ')' if opened else 'not opened, ' + detail}")
    if disabled:
        lines += ["", "## Frames without a trusted geometry (rectangles stay in image pixels)", ""]
        lines += [f"- {display(f['rel'])}: {f['roi_disabled']}" for f in disabled[:50]]
        if len(disabled) > 50:
            lines.append(f"- ... and {len(disabled) - 50} more (pick.json lists every one)")
    lines += ["", "## Using the page", "",
              "- click selects a frame, shift-click a range; arrows move, Space toggles, s / e "
              "mark the start / end frame, x clears the marks, Esc clears the rectangle, c copies",
              "- drag on the large preview to draw a rectangle",
              "- Copy puts the block on the clipboard; where the browser refuses, the text is "
              "selected for Ctrl+C / Cmd+C",
              "- the selection is remembered in this browser for these exact images only",
              f"- the picker owns everything under {out}"]
    with open(out / "summary.md", "w", encoding="utf-8", errors="replace") as fh:
        fh.write("\n".join(lines) + "\n")
    (out / "run.json").write_text(json.dumps({
        "mode": "pick", "options": {k: v for k, v in vars(args).items() if k != "func"},
        "dir": str(root.resolve()), "input_layout": layout,
        "source_run": str(run_dir.resolve()) if run_dir else None, "source": src,
        "frames": len(frames), "roi_trusted": len(trusted),
        "roi_disabled": [{"file": f["rel"], "reason": f["roi_disabled"]} for f in disabled],
        "renamed": [{"file": s.name, "snapshot": s.rel} for s in renamed],
        "fingerprint": data["fingerprint"], "page": str(page),
        "opened": opened, "open_detail": detail,
    }, indent=2, ensure_ascii=True, default=str) + "\n")

    print(f"pick: {len(frames)} frames, source --roi available for {len(trusted)}"
          + (f" ({len(disabled)} without a trusted geometry)" if disabled else ""))
    if not args.open:
        print("OPEN: not requested (--open not given)")
    else:
        print(f"OPEN: opened ({detail})" if opened else f"OPEN: not opened: {detail}")
    print(f"PAGE: {page}")
    print(f"SUMMARY: {out / 'summary.md'}")
    return 0
