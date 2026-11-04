#!/usr/bin/env python3
"""Turn a screen recording into frames, contact sheets and timing data that a
coding agent can read (Claude Code cannot open video files).

  aitask_screen_recording.sh info VIDEO
  aitask_screen_recording.sh bug  VIDEO [--out DIR] [--crop-top PX] [--min-dwell S] ...
  aitask_screen_recording.sh anim VIDEO [--out DIR] [--roi X,Y,W,H] [--window A-B] ...

Entry point of the aitask-screen-recording skill; the measurement model is
documented in .claude/skills/aitask-screen-recording/references/animation.md.

Every run writes <out>/summary.md (read it first) and <out>/run.json, then prints
"SUMMARY: <path>". Needs ffmpeg/ffprobe >= 5.1. ImageMagick 7 (`magick`) is
optional: without it there are no contact sheets or plots, only frames and data.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import vp_core as core  # noqa: E402

SHEET_MAX_EDGE = 1600      # keeps a sheet under Claude's per-image downscale limit
TOKEN_TILE = 28            # image tokens ~= ceil(w/28) * ceil(h/28)

# bug-mode triage detectors (ffmpeg defaults except blackdetect's d, which we
# apply ourselves through --black-min: its metadata marks every run regardless)
FREEZE_NOISE = "-60dB"
BLACK_PIC_TH, BLACK_PIX_TH = 0.98, 0.10
SILENCE_NOISE, SILENCE_MIN = "-60dB", 2.0


class PrepError(RuntimeError):
    pass


# --------------------------------------------------------------------------- #
# ffmpeg / ffprobe / magick plumbing

def run(cmd: list[str], *, binary: bool = False):
    try:
        cp = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL)
    except FileNotFoundError as exc:
        raise PrepError(f"{cmd[0]} not found on PATH") from exc
    err = cp.stderr.decode("utf-8", "replace")
    if cp.returncode != 0:
        tail = "\n".join(err.strip().splitlines()[-12:])
        raise PrepError(f"{Path(cmd[0]).name} failed ({cp.returncode}):\n{tail}")
    return (cp.stdout if binary else cp.stdout.decode("utf-8", "replace")), err


def ffmpeg(args: list[str], *, binary: bool = False):
    return run(["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info", *args],
               binary=binary)


def _rate(s: str | None) -> float | None:
    if not s or s in ("0/0", "N/A"):
        return None
    if "/" in s:
        a, b = s.split("/", 1)
        return float(a) / float(b) if float(b) else None
    return float(s)


def probe(video: str) -> dict:
    out, _ = run(["ffprobe", "-v", "error", "-print_format", "json",
                  "-show_format", "-show_streams", video])
    data = json.loads(out)
    vstreams = [s for s in data.get("streams", []) if s.get("codec_type") == "video"
                and not s.get("disposition", {}).get("attached_pic")]
    if not vstreams:
        raise PrepError(f"{video}: no video stream")
    # one stream for everything: the default-disposition track (what players show),
    # else the first. Every ffmpeg/ffprobe call maps this index explicitly, so the
    # properties, detectors, packet coverage and extracted frames agree.
    vs = next((s for s in vstreams if s.get("disposition", {}).get("default")), vstreams[0])
    rotation = 0
    for sd in vs.get("side_data_list", []) or []:
        if "rotation" in sd:
            rotation = int(round(float(sd["rotation"])))
    if not rotation and "rotate" in vs.get("tags", {}):
        rotation = int(vs["tags"]["rotate"])
    w, h = int(vs["width"]), int(vs["height"])
    if rotation % 180:
        w, h = h, w
    fmt = data.get("format", {})
    duration = float(fmt.get("duration") or vs.get("duration") or 0.0)
    audio = [s for s in data.get("streams", []) if s.get("codec_type") == "audio"]
    return {
        "path": str(video), "width": w, "height": h, "rotation": rotation,
        "duration": duration, "start_time": float(fmt.get("start_time") or 0.0),
        "avg_fps": _rate(vs.get("avg_frame_rate")), "r_fps": _rate(vs.get("r_frame_rate")),
        "nb_frames": int(vs["nb_frames"]) if str(vs.get("nb_frames", "")).isdigit() else None,
        "codec": vs.get("codec_name"), "has_audio": bool(audio),
        "vindex": int(vs["index"]), "video_streams": len(vstreams),
        "creation_time": (fmt.get("tags") or {}).get("creation_time"),
    }


def crop_filter(args, info) -> tuple[str | None, int, int, str]:
    """ffmpeg crop for the analysed region, its size, and a human description."""
    W, H = info["width"], info["height"]
    if getattr(args, "roi", None):
        try:
            x, y, w, h = (int(v) for v in args.roi.split(","))
        except ValueError as exc:
            raise PrepError("--roi takes X,Y,W,H in display pixels") from exc
        if w <= 0 or h <= 0 or x < 0 or y < 0 or x + w > W or y + h > H:
            raise PrepError(f"--roi {args.roi} is outside the {W}x{H} frame")
        return f"crop={w}:{h}:{x}:{y}", w, h, f"roi {w}x{h} at ({x},{y})"
    top, bottom = args.crop_top or 0, args.crop_bottom or 0
    if top < 0 or bottom < 0 or top + bottom >= H:
        raise PrepError("--crop-top/--crop-bottom leave nothing of the frame")
    if top or bottom:
        return (f"crop=iw:ih-{top + bottom}:0:{top}", W, H - top - bottom,
                f"full width, minus {top} px top / {bottom} px bottom")
    return None, W, H, "full frame"


def parse_span(text: str, flag: str) -> tuple[float, float]:
    try:
        a, b = (float(v) for v in text.split("-", 1))
    except ValueError as exc:
        raise PrepError(f"{flag} takes START-END in seconds, e.g. 1.5-3.2") from exc
    if b <= a:
        raise PrepError(f"{flag}: END must be after START")
    return a, b


def _vmap(stream: int | None) -> list[str]:
    """-map for the resolved video stream (probe()["vindex"]); empty = ffmpeg's choice."""
    return [] if stream is None else ["-map", f"0:{stream}"]


def scan(video, head: list[str], decimate: str | None, pre: list[str] = (), *,
         stream: int | None = None):
    """One decode pass: the `pre` filters (detectors) see every frame, then
    mpdecimate keeps the visible changes. Returns ((pts, time) of the kept frames,
    the ffmpeg log)."""
    md = "mpdecimate" + (f"={decimate}" if decimate else "")
    vf = ",".join([*head, *pre, md, "showinfo"])
    _, err = ffmpeg(["-i", video, *_vmap(stream), "-an", "-vf", vf, "-fps_mode", "passthrough",
                     "-f", "null", "-"])
    return [(pts, t) for _, pts, t in core.parse_showinfo(err)], err


def kept_frames(video, head: list[str], decimate: str | None, *,
                stream: int | None = None) -> list[tuple[int, float]]:
    """(pts, time) of the frames mpdecimate keeps, i.e. every visible change."""
    return scan(video, head, decimate, stream=stream)[0]


def silence_log(video, span: tuple[float, float] | None) -> str:
    """ffmpeg log of silencedetect (+ ametadata print) over the first audio stream."""
    af = ",".join(x for x in [
        f"atrim=start={span[0]:.6f}:end={span[1]:.6f}" if span else None,
        f"silencedetect=n={SILENCE_NOISE}:d={SILENCE_MIN:g}", "ametadata=mode=print"] if x)
    _, err = ffmpeg(["-i", video, "-vn", "-af", af, "-f", "null", "-"])
    return err


def video_packets(video, stream: int) -> list[tuple[float | None, float | None]]:
    """(pts_time, duration_time) of every packet of the first video stream, in
    demux order and on the container's raw timeline (demux only, no decode)."""
    out, _ = run(["ffprobe", "-v", "error", "-select_streams", str(stream), "-show_entries",
                  "packet=pts_time,duration_time", "-of", "compact=p=0", video])
    return core.parse_packets(out)


def decode_gray(video, head: str, crop: str | None, aw: int, ah: int, *,
                stream: int | None = None):
    """Decode frames as aw x ah grayscale: [(pts, time, bytes)]."""
    vf = ",".join(x for x in [head, crop, f"scale={aw}:{ah}:flags=area", "format=gray",
                              "showinfo"] if x)
    out, err = ffmpeg(["-i", video, *_vmap(stream), "-an", "-vf", vf, "-fps_mode", "passthrough",
                       "-f", "rawvideo", "-pix_fmt", "gray", "pipe:1"], binary=True)
    info = core.parse_showinfo(err)
    size = aw * ah
    if len(out) != size * len(info):
        raise PrepError(f"decoded {len(out)} bytes for {len(info)} frames of {aw}x{ah}")
    return [(pts, t, out[i * size:(i + 1) * size]) for i, (_, pts, t) in enumerate(info)]


def extract_views(video, wanted: dict[int, Path], crop: str | None, vw: int, vh: int, *,
                  stream: int | None = None):
    """Write the frames whose pts are keys of `wanted` to the mapped PNG paths."""
    if not wanted:
        return
    tmp = next(iter(wanted.values())).parent / ".extract_tmp"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        expr = "+".join(f"eq(pts,{p})" for p in sorted(wanted))
        vf = ",".join(x for x in [f"select='{expr}'", crop, f"scale={vw}:{vh}:flags=area",
                                  "showinfo"] if x)
        _, err = ffmpeg(["-i", video, *_vmap(stream), "-an", "-vf", vf, "-fps_mode", "passthrough",
                         str(tmp / "%05d.png")])
        got = core.parse_showinfo(err)
        for k, (_, pts, _) in enumerate(got, start=1):
            if pts in wanted:
                (tmp / f"{k:05d}.png").replace(wanted[pts])
        missing = [p for p, path in wanted.items() if not path.exists()]
        if missing:
            raise PrepError(f"could not extract frames with pts {missing[:5]}")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def view_size(cw: int, ch: int, long_edge: int) -> tuple[int, int]:
    g = min(1.0, long_edge / max(cw, ch))
    return max(1, round(cw * g)), max(1, round(ch * g))


def analysis_size(cw: int, ch: int, max_px: int) -> tuple[int, int]:
    f = min(1.0, math.sqrt(max_px / (cw * ch)))
    return max(16, round(cw * f)), max(16, round(ch * f))


def have_magick() -> bool:
    return shutil.which("magick") is not None


def sheet_layout(n: int, w: int, h: int, label_h: int = 40):
    best = None
    for cols in range(1, n + 1):
        rows = math.ceil(n / cols)
        s = min((SHEET_MAX_EDGE - 8 * cols) / (cols * w),
                (SHEET_MAX_EDGE - (label_h + 8) * rows) / (rows * h), 4.0)
        if best is None or s > best[0] + 1e-9:
            best = (s, cols)
    s, cols = best
    return cols, max(1, int(w * s)), max(1, int(h * s))


def contact_sheets(items: list[tuple[Path, str]], out_dir: Path, per_sheet: int,
                   w: int, h: int, prefix: str = "sheet") -> list[Path]:
    """Labelled grids of frames. Labels must not contain '%' (ImageMagick escapes)."""
    if not items or not have_magick():
        return []
    sheets = []
    for s in range(0, len(items), per_sheet):
        chunk = items[s:s + per_sheet]
        cols, tw, th = sheet_layout(len(chunk), w, h)
        out = out_dir / f"{prefix}_{s // per_sheet + 1:02d}.png"
        cmd = ["magick", "montage", "-background", "#1e1e1e", "-fill", "#f2f2f2",
               "-pointsize", "15"]
        for path, label in chunk:
            cmd += ["-label", label.replace("%", "pct"), str(path)]
        cmd += ["-tile", f"{cols}x", "-geometry", f"{tw}x{th}+4+4", str(out)]
        run(cmd)
        sheets.append(out)
    return sheets


def image_size(path: Path) -> tuple[int, int] | None:
    try:
        out, _ = run(["magick", "identify", "-format", "%w %h", str(path)])
        w, h = out.split()
        return int(w), int(h)
    except (PrepError, ValueError):
        return None


def token_estimate(paths: list[Path]) -> int | None:
    total = 0
    for p in paths:
        size = image_size(p)
        if size is None:
            return None
        w, h = size
        total += math.ceil(w / TOKEN_TILE) * math.ceil(h / TOKEN_TILE)
    return total


def make_out_dir(arg: str | None, video: str, mode: str) -> Path:
    base = Path(arg) if arg else (Path(os.environ.get("TMPDIR", "/tmp")) / "video-prep"
                                  / f"{Path(video).stem}-{mode}")
    d, k = base, 2
    while d.exists() and any(d.iterdir()):
        d = base.with_name(f"{base.name}-{k}")
        k += 1
    d.mkdir(parents=True, exist_ok=True)
    return d


def video_line(info: dict) -> str:
    fps = f"{info['avg_fps']:.2f} fps avg" if info["avg_fps"] else "fps unknown"
    if info["r_fps"] and info["avg_fps"] and abs(info["r_fps"] - info["avg_fps"]) > 0.5:
        fps += f" (r_frame_rate {info['r_fps']:.2f}: variable frame rate)"
    rot = f", rotated {info['rotation']}°" if info["rotation"] else ""
    streams = ("" if info.get("video_streams", 1) <= 1 else
               f", video stream #{info['vindex']} of {info['video_streams']} (the default "
               "track, else the first; the others are not analysed)")
    return (f"{info['width']}x{info['height']}{rot}, {info['duration']:.2f} s, {fps}, "
            f"codec {info['codec']}, audio: {'yes' if info['has_audio'] else 'none'}{streams}")


def audio_peak_db(video: str) -> float | None:
    _, err = ffmpeg(["-i", video, "-vn", "-af", "volumedetect", "-f", "null", "-"])
    for line in err.splitlines():
        if "max_volume:" in line:
            try:
                return float(line.split("max_volume:")[1].split("dB")[0])
            except ValueError:
                return None
    return None


def fmt_ms(seconds: float) -> str:
    return f"{seconds * 1000:.0f} ms"


# --------------------------------------------------------------------------- #
# info

def cmd_info(args) -> int:
    info = probe(args.video)
    print(json.dumps(info, indent=2))
    print(video_line(info), file=sys.stderr)
    return 0


# --------------------------------------------------------------------------- #
# bug mode

def _shown_for(p: core.Pick, *, tsv: bool = False, label: bool = False) -> str:
    """How long a pick's picture was up. A frame mpdecimate dropped (a black frame
    added for its interval) was never measured by it: its duration is the black
    run's, and when that run's end was not observed it is only a lower bound."""
    if p.dwell_basis == "black run, lower bound":
        return "" if tsv else (f">={p.dwell:.2f}s" if label
                               else f"≥ {p.dwell:.3f} s (black run, span ended)")
    if p.dwell_basis == "black run":
        return (f"{p.dwell:.3f}" if tsv else f"{p.dwell:.3f}s" if label
                else f"{p.dwell:.3f} s (black run)")
    return f"{p.dwell:.3f}" if tsv else f"{p.dwell:.2f}s" if label else f"{p.dwell:.2f} s"


def _end_cell(iv: core.Interval) -> tuple[str, str]:
    if iv.end_observed:
        return f"{iv.end:.3f} s", f"{iv.duration:.3f} s"
    return f"≥ {iv.end:.3f} s (span ended)", f"≥ {iv.duration:.3f} s"


def cmd_bug(args) -> int:
    # argparse's float() accepts nan and inf; every comparison with nan is false
    if not math.isfinite(args.freeze_min) or args.freeze_min <= 0:
        raise PrepError("--freeze-min must be a positive number of seconds")
    if not math.isfinite(args.black_min) or args.black_min < 0:
        raise PrepError("--black-min must be a number of seconds, 0 or more")
    info = probe(args.video)
    crop, cw, ch, region = crop_filter(args, info)
    span = parse_span(args.range, "--range") if args.range else None
    head = []
    if span:
        head.append(f"trim=start={span[0]:.6f}:end={span[1]:.6f}")
    if crop:
        head.append(crop)
    detectors = {
        "freeze": f"freezedetect=n={FREEZE_NOISE}:d={args.freeze_min:g}",
        "black": f"blackdetect=d=0:pic_th={BLACK_PIC_TH:g}:pix_th={BLACK_PIX_TH:g}",
        "silence": (f"silencedetect=n={SILENCE_NOISE}:d={SILENCE_MIN:g}"
                    if info["has_audio"] else None),
    }
    kept, vlog = scan(args.video, head, args.decimate,
                      [detectors["freeze"], detectors["black"], "metadata=mode=print"],
                      stream=info["vindex"])
    if not kept:
        raise PrepError("no frames decoded (check --range)")
    times = [t for _, t in kept]
    vspan = core.video_span(video_packets(args.video, info["vindex"]), info["start_time"],
                            range_end=span[1] if span else None, ranged=span is not None,
                            first_kept_t=times[0], last_kept_t=times[-1],
                            container_end=info["duration"])
    end_t = vspan.end_t
    alog = silence_log(args.video, span) if info["has_audio"] else ""
    intervals = core.triage_intervals(vlog, alog, vspan.interval_end, black_min=args.black_min)

    # one detector-qualified frame per black interval: the first black frame, even
    # when mpdecimate dropped it as a near-duplicate of its predecessor
    pts_index = {pts: i for i, (pts, _) in enumerate(kept)}
    marks = []
    for iv in intervals:
        if iv.kind != "black":
            continue
        i = pts_index.get(iv.frame_pts)
        if i is not None:
            marks.append(core.Mark(iv.frame_t, "black", index=i))
        else:
            marks.append(core.Mark(iv.frame_t, "black", ref=iv.frame_pts, dwell=iv.duration,
                                   dwell_basis=("black run" if iv.end_observed
                                                else "black run, lower bound")))
    picks, dropped = core.select_key_frames(
        times, end_t, min_dwell=args.min_dwell, interval=args.interval,
        brief_max=args.brief_max, max_frames=args.max_frames, marks=marks)

    out = make_out_dir(args.out, args.video, "bug")
    frames_dir = out / "frames"
    frames_dir.mkdir()
    vw, vh = view_size(info["width"], info["height"], args.view_size)
    wanted, rows = {}, []
    for k, p in enumerate(picks, start=1):
        pts = kept[p.index][0] if p.index is not None else p.ref
        path = frames_dir / f"{k:02d}_{p.t:.3f}s.png"
        wanted[pts] = path
        rows.append((k, p, path))
    extract_views(args.video, wanted, None, vw, vh,  # full frame: the status bar can matter
                  stream=info["vindex"])
    sheets = contact_sheets(
        [(path, f"#{k} {p.t:.3f}s\n{'+'.join(p.reasons)} {_shown_for(p, label=True)}")
         for k, p, path in rows],
        out, args.per_sheet, vw, vh)

    iv_file = {}
    omitted = 0
    for iv in intervals:
        if iv.kind == "black":
            path = wanted.get(iv.frame_pts)
            iv_file[id(iv)] = path.relative_to(out) if path else None
            omitted += path is None

    def iv_why(iv):
        why = detectors[iv.kind]
        if not iv.end_observed:
            why += (f"; end not observed: still {iv.kind} when the analysed span ended "
                    "(real end unknown, end_s is a lower bound)")
            if iv.kind != "silence" and not vspan.proven:
                why += f"; {vspan.note}"
        if iv.kind == "black" and iv_file[id(iv)] is None:
            why += f"; no image: --max-frames {args.max_frames} reached"
        return why

    tsv = [(p.t, 0, [str(k), f"{p.t:.3f}", _shown_for(p, tsv=True), "+".join(p.reasons),
                     str(path.relative_to(out)), "frame", ""]) for k, p, path in rows]
    tsv += [(iv.start, 1, ["", f"{iv.start:.3f}", "", iv_why(iv),
                           str(iv_file.get(id(iv)) or ""), iv.kind, f"{iv.end:.3f}"])
            for iv in intervals]
    with open(out / "timeline.tsv", "w") as fh:
        fh.write("idx\ttime_s\tshown_for_s\twhy\tfile\tkind\tend_s\n")
        for _, _, fields in sorted(tsv, key=lambda r: (r[0], r[1])):
            fh.write("\t".join(fields) + "\n")

    audio_note = "none"
    if info["has_audio"]:
        peak = audio_peak_db(args.video)
        if peak is None or peak < -50:
            audio_note = "track present but silent"
        else:
            audio_note = (f"present, peak {peak:.1f} dB: probably narration or app sound; "
                          "not transcribed")
            if args.extract_audio:
                ffmpeg(["-i", args.video, "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le",
                        str(out / "audio.wav")])
                audio_note += " (16 kHz mono copy: audio.wav)"

    counts = {}
    for _, p, _ in rows:
        for r in p.reasons:
            counts[r] = counts.get(r, 0) + 1
    n_kind = {k: sum(iv.kind == k for iv in intervals) for k in ("freeze", "black", "silence")}
    tokens = token_estimate(sheets) if sheets else None
    lines = [
        f"# Bug-report frames: {Path(args.video).name}", "",
        f"- video: {video_line(info)}",
        f"- change detection: mpdecimate on {region}"
        + (f", range {args.range} s" if args.range else ""),
        f"- picked {len(rows)} frames ("
        + ", ".join(f"{v} {k}" for k, v in sorted(counts.items())) + ")"
        + (f"; {dropped} more dropped by --max-frames {args.max_frames}" if dropped else ""),
        f"- a 'state' stayed on screen >= {args.min_dwell} s; 'motion' = one frame per "
        f"{args.interval} s of continuous change; 'brief' = a change that lasted <= "
        f"{args.brief_max} s (flash, glitch, very quick transition); 'black' = the first "
        "frame of a black interval",
        f"- triage: {n_kind['freeze']} freeze, {n_kind['black']} black, "
        + (f"{n_kind['silence']} silence" if info["has_audio"]
           else "silence not checked (no audio stream)")
        + " (see \"Freeze, black and silence\")",
        f"- audio: {audio_note}",
        f"- saved frames are {vw}x{vh}, i.e. x{vw / info['width']:.3f} of the source; "
        f"--roi takes source pixels (divide frame coordinates by {vw / info['width']:.3f})",
    ]
    if not vspan.proven:
        lines.append(f"- video end from container duration (not proven): {vspan.note}")
    if info.get("creation_time"):
        lines.append(f"- container creation_time: {info['creation_time']} (meaning varies by "
                     "recorder: start or end of the recording; low confidence for log alignment)")
    lines += ["", "## Contact sheets (read these first)", ""]
    if sheets:
        for s_i, s in enumerate(sheets):
            a = s_i * args.per_sheet + 1
            b = min(len(rows), a + args.per_sheet - 1)
            lines.append(f"- {s.relative_to(out)}: frames #{a}-#{b}")
        if tokens:
            lines.append(f"- all sheets together cost roughly {tokens} image tokens")
    else:
        lines.append("- (no sheets: ImageMagick `magick` not found; read frames/ directly)")
    lines += ["", "## Timeline", "", "| # | time | shown for | why | file |",
              "|---|------|-----------|-----|------|"]
    for k, p, path in rows:
        lines.append(f"| {k} | {p.t:.3f} s | {_shown_for(p)} | {'+'.join(p.reasons)} | "
                     f"{path.relative_to(out)} |")
    if dropped:
        lines += ["", f"Warning: {dropped} picks were dropped. Narrow with --range, or raise "
                  "--interval / --min-dwell, rather than raising --max-frames."]
    if len(times) <= 1:
        lines += ["", "Nothing on screen changed in the analysed region."
                  + (" (by mpdecimate's measure; blackdetect still found the black frames "
                     "listed below)" if n_kind["black"] else "")]

    lines += ["", "## Freeze, black and silence", "",
              f"- detectors on {region}: {detectors['freeze']}; {detectors['black']} "
              f"(black runs shorter than --black-min {args.black_min:g} s are left out when "
              "their end was observed); "
              + (detectors["silence"] or "silence not checked (no audio stream)"),
              f"- freeze = no change above freezedetect's noise floor ({FREEZE_NOISE}) in the "
              f"analysed region for >= {args.freeze_min:g} s; a small change such as a toggled "
              "checkbox can sit inside a freeze (the frame picks still show it); a hang only "
              "if the frames show the user acting, otherwise just a still screen; "
              f"black = >= {BLACK_PIC_TH:.0%} of the pixels near black (a dark screen counts "
              f"too); silence = audio below {SILENCE_NOISE} for >= {SILENCE_MIN:g} s",
              "- an end shown as \"≥ … (span ended)\" was not observed: the state was still on "
              "when the analysed span (for silence: the audio) ended", ""]
    if intervals:
        lines += ["| kind | start | end | duration | frame |",
                  "|------|-------|-----|----------|-------|"]
        for iv in intervals:
            end, dur = _end_cell(iv)
            if iv.kind != "black":
                frame = "—"
            else:
                frame = str(iv_file[id(iv)] or "— (no image: --max-frames)")
            lines.append(f"| {iv.kind} | {iv.start:.3f} s | {end} | {dur} | {frame} |")
    else:
        lines.append("- none found")
    if omitted:
        lines += ["", f"Warning: {omitted} black intervals have no image (--max-frames "
                  f"{args.max_frames} reached). All are listed above and in timeline.tsv; "
                  "narrow with --range around them to see their frames."]
    (out / "summary.md").write_text("\n".join(lines) + "\n")
    _write_run_json(out, "bug", args, info, {
        "picks": len(rows), "dropped": dropped, "cap_hit": dropped > 0,
        "black_images_omitted": omitted,
        "sheets": [str(s.relative_to(out)) for s in sheets],
        "video_end_s": round(vspan.end_t, 6) if vspan.proven else None,
        "video_end_proven": vspan.proven,
        "video_end_note": vspan.note or None,
        "detectors": detectors,
        "intervals": [{
            "kind": iv.kind, "start_s": round(iv.start, 6), "end_s": round(iv.end, 6),
            "end_observed": iv.end_observed, "duration_s": round(iv.duration, 6),
            "frame_time_s": None if iv.frame_t is None else round(iv.frame_t, 6),
            "file": (str(iv_file[id(iv)]) if iv_file.get(id(iv)) else None),
        } for iv in intervals],
    })
    print(f"SUMMARY: {out / 'summary.md'}")
    return 0


# --------------------------------------------------------------------------- #
# anim mode

def cmd_anim(args) -> int:
    info = probe(args.video)
    crop, cw, ch, region = crop_filter(args, info)
    aw, ah = analysis_size(cw, ch, args.analysis_pixels)
    scale_px = cw / aw
    vw, vh = view_size(cw, ch, args.view_size)
    nominal_dt = 1.0 / info["avg_fps"] if info["avg_fps"] else 1 / 60

    window = parse_span(args.window, "--window") if args.window else None
    span = parse_span(args.range, "--range") if args.range else None
    windows = []   # (label, pre_pts or None, start, end, note, first change time)
    cuts = []
    if window:
        a, b = window
        windows.append(("w01", None, a, b, "given window", a))
    else:
        head = []
        if span:
            a, b = span
            head.append(f"trim=start={a:.6f}:end={b:.6f}")
        if crop:
            head.append(crop)
        kept = kept_frames(args.video, head, args.decimate, stream=info["vindex"])
        times = [t for _, t in kept]
        segs = core.motion_segments(times, args.gap)
        # the video's own end, on the kept frames' (normalised) timeline: the container
        # end is raw (start_time not subtracted) and can be a longer audio track's
        end_t = core.video_span(
            video_packets(args.video, info["vindex"]), info["start_time"],
            range_end=span[1] if span else None, ranged=span is not None,
            first_kept_t=times[0], last_kept_t=times[-1],
            container_end=info["duration"]).end_t if segs else None
        for si, (first, last) in enumerate(segs):
            if last - first + 1 < args.min_frames and first > 0:
                cuts.append(times[first])
                continue
            nxt = segs[si + 1][0] if si + 1 < len(segs) else None
            b = times[last] + args.pad
            if nxt is not None:
                b = min(b, times[nxt] - 1e-3)
            b = min(b, end_t)
            a = max(times[first] - args.pad, times[first - 1] if first > 0 else times[0])
            pre = kept[first - 1][0] if first > 0 else None
            note = "" if first > 0 else "video starts mid-motion: progress is relative to frame 0"
            windows.append((None, pre, a, b, note, times[first]))
        if len(windows) > args.max_segments:
            extra = windows[args.max_segments:]
            windows = windows[:args.max_segments]
            cuts_note = f"{len(extra)} later segments skipped (--max-segments {args.max_segments})"
        else:
            cuts_note = ""
        windows = [(f"s{k:02d}", *rest) for k, (_, *rest) in enumerate(windows, start=1)]

    out = make_out_dir(args.out, args.video, "anim")
    results = []
    for label, pre_pts, a, b, note, t_first in windows:
        seg_dir = out / label
        (seg_dir / "frames").mkdir(parents=True)
        frames = decode_gray(args.video, f"trim=start={a - 1e-4:.6f}:end={b + 1e-4:.6f}",
                             crop, aw, ah, stream=info["vindex"])
        if pre_pts is not None and (not frames or frames[0][1] >= t_first - 1e-6):
            # variable-frame-rate recordings emit no frames while the screen is still,
            # so the still picture before the motion can lie outside the window
            pre = decode_gray(args.video, f"select='eq(pts,{pre_pts})'", crop, aw, ah,
                              stream=info["vindex"])
            frames = pre[:1] + [f for f in frames if f[0] != pre_pts]
        if len(frames) < 3:
            results.append({"label": label, "error": "fewer than 3 frames in the window",
                            "window": (a, b)})
            continue
        ts = [f[1] for f in frames]
        res = core.analyze_frames(ts, [f[2] for f in frames], aw, ah, signal=args.signal,
                                  nominal_dt=nominal_dt)
        res.update(label=label, window=(a, b), note=note, times=ts)

        # frames to look at: the motion plus two frames of context on each side (the
        # rest of the pad only anchors the fit), thinned evenly when long
        fm, lm = res.get("first_moving"), res.get("last_moving")
        if fm is None:
            idx = [0, len(frames) - 1]
        else:
            lo_v = max(0, fm - 2)
            hi_v = min(len(frames) - 1, (lm if lm is not None else fm) + 3)
            idx = list(range(lo_v, hi_v + 1))
            if len(idx) > args.max_view_frames:
                must = {lo_v, hi_v, fm, max(0, fm - 1)}
                if lm is not None:
                    must |= {lm, min(len(frames) - 1, lm + 1)}
                step = len(idx) / args.max_view_frames
                idx = sorted(must | {idx[int(k * step)] for k in range(args.max_view_frames)})
        t_start = ts[res["first_moving"]] - res["frame_interval"] \
            if res.get("first_moving") is not None else ts[0]
        wanted, items = {}, []
        for i in idx:
            pts, t, _ = frames[i]
            path = seg_dir / "frames" / f"f{i:03d}_{t:.3f}s.png"
            wanted[pts] = path
            rel = (t - t_start) / args.time_scale
            items.append((path, f"f{i:03d} {t:.3f}s\n{rel * 1000:+.0f}ms"))
        extract_views(args.video, wanted, crop, vw, vh, stream=info["vindex"])
        res["view_files"] = {i: str((seg_dir / "frames" / f"f{i:03d}_{frames[i][1]:.3f}s.png")
                                    .relative_to(out)) for i in idx}
        res["sheets"] = [str(s.relative_to(out)) for s in
                         contact_sheets(items, seg_dir, args.per_sheet, vw, vh)]
        _write_curve_tsv(seg_dir / "curve.tsv", res, out)
        res["plot"] = _write_plot(seg_dir, res, args.time_scale)
        results.append(res)
        (seg_dir / "fit.json").write_text(json.dumps(_fit_json(res, args, scale_px), indent=2))

    _write_anim_summary(out, args, info, region, (aw, ah), scale_px, results, cuts,
                        "" if args.window else cuts_note, vw, vh, cw)
    _write_run_json(out, "anim", args, info, {"segments": [r["label"] for r in results],
                                              "cuts": cuts})
    print(f"SUMMARY: {out / 'summary.md'}")
    return 0


def _real_fits(res, time_scale):
    return [core.scale_fit_time(f, time_scale) for f in res.get("fits", [])]


def _fit_desc(f: core.Fit) -> str:
    if f.family == "tween":
        x1, y1, x2, y2 = f.params
        return f"cubic-bezier({x1:g}, {y1:g}, {x2:g}, {y2:g})"
    k, z = f.params
    return f"stiffness {k:g}, damping ratio {z:g} -> {f.extra.get('compose', '')}"


def _fit_json(res, args, scale_px):
    track = res.get("track")
    return {
        "label": res["label"], "window_s": res["window"], "kind": res.get("kind"),
        "signal": res.get("signal"), "time_scale": args.time_scale,
        "visible_duration_ms": (round(res["visible_duration"] * 1000 / args.time_scale, 1)
                                if res.get("visible_duration") is not None else None),
        "frame_interval_ms": (round(res["frame_interval"] * 1000, 2)
                              if res.get("frame_interval") else None),
        "travel_source_px": round(track.magnitude * scale_px, 1) if track else None,
        "travel_spread": track.spread if track else None,
        "overshoot": res.get("overshoot"),
        "fits": [{"family": f.family, "name": f.name, "params": f.params,
                  "duration_ms": round(f.duration * 1000, 1), "rmse": round(f.rmse, 4),
                  **f.extra} for f in _real_fits(res, args.time_scale)],
        "warnings": res.get("warnings", []),
    }


def _write_curve_tsv(path: Path, res, out: Path):
    ts = res["times"]
    t_ref = ts[res["first_moving"]] - res["frame_interval"] if res.get("first_moving") \
        is not None else ts[0]
    cols = ["idx", "time_s", "t_rel_ms", "mad_vs_start", "mad_vs_end", "p_blend", "p_edge",
            "p_fitted_signal", "bbox_vs_start", "bbox_vs_end", "file"]
    with open(path, "w") as fh:
        fh.write("\t".join(cols) + "\n")
        for i, t in enumerate(ts):
            def opt(seq):
                return "" if seq is None else f"{seq[i]:.4f}"
            fh.write("\t".join([
                str(i), f"{t:.4f}", f"{(t - t_ref) * 1000:.1f}",
                f"{res['mad_s'][i]:.3f}", f"{res['mad_e'][i]:.3f}",
                opt(res.get("p_blend")), opt(res.get("p_edge")), opt(res.get("progress")),
                "" if res["bbox_s"][i] is None else ",".join(map(str, res["bbox_s"][i])),
                "" if res["bbox_e"][i] is None else ",".join(map(str, res["bbox_e"][i])),
                res.get("view_files", {}).get(i, ""),
            ]) + "\n")


def _model_value(f: core.Fit, t: float, curves: dict) -> float:
    if f.family == "tween":
        key = f.params
        if key not in curves:
            curves[key] = core.CubicBezier(*f.params)
        x = (t - f.t0) / f.duration
        return 0.0 if x <= 0 else (1.0 if x >= 1 else curves[key](x))
    k, z = f.params
    return core.spring(t - f.t0, k, z)


def _write_plot(seg_dir: Path, res, time_scale: float) -> str | None:
    if not res.get("fits") or res.get("progress") is None:
        return None
    lo, hi = res["fit_range"]
    ts = res["times"][lo:hi + 1]
    ps = res["progress"][lo:hi + 1]
    fits = res["fits"]
    shown = [fits[0]] + [f for f in fits[1:] if f.family != fits[0].family][:1]
    t_ref = fits[0].t0
    W, H, ml, mr, mt, mb = 760, 400, 58, 18, 40, 46
    x0, x1 = ts[0], ts[-1]
    y0, y1 = min(-0.05, min(ps) - 0.02), max(1.08, max(ps) + 0.02)

    def X(t):
        return ml + (t - x0) / ((x1 - x0) or 1) * (W - ml - mr)

    def Y(p):
        return mt + (y1 - p) / (y1 - y0) * (H - mt - mb)

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
             'font-family="DejaVu Sans, sans-serif" font-size="12">',
             f'<rect width="{W}" height="{H}" fill="#ffffff"/>']
    for p in (0.0, 0.5, 1.0):
        parts.append(f'<line x1="{ml}" x2="{W - mr}" y1="{Y(p):.1f}" y2="{Y(p):.1f}" '
                     f'stroke="#d0d0d0" stroke-dasharray="{"" if p != 0.5 else "4 4"}"/>')
        parts.append(f'<text x="{ml - 6}" y="{Y(p) + 4:.1f}" text-anchor="end">{p:g}</text>')
    span_ms = (x1 - x0) * 1000 / time_scale
    step = next(s for s in (10, 20, 25, 50, 100, 200, 250, 500, 1000, 2000, 5000)
                if span_ms / s <= 10)
    k = math.ceil((x0 - t_ref) * 1000 / time_scale / step)
    while True:
        t = t_ref + k * step / 1000 * time_scale
        if t > x1:
            break
        parts.append(f'<line x1="{X(t):.1f}" x2="{X(t):.1f}" y1="{H - mb}" y2="{H - mb + 5}" '
                     'stroke="#666"/>')
        parts.append(f'<text x="{X(t):.1f}" y="{H - mb + 18}" text-anchor="middle">'
                     f'{k * step}</text>')
        k += 1
    parts.append(f'<text x="{(ml + W - mr) / 2}" y="{H - 8}" text-anchor="middle">ms since '
                 f'fitted start{"" if time_scale == 1 else f" (real time, /{time_scale:g})"}</text>')
    colors = ["#d1495b", "#2e86ab"]
    curves: dict = {}
    real = {id(f): core.scale_fit_time(f, time_scale) for f in shown}
    for c, f in zip(colors, shown):
        pts = []
        for j in range(301):
            t = x0 + (x1 - x0) * j / 300
            pts.append(f"{X(t):.1f},{Y(_model_value(f, t, curves)):.1f}")
        parts.append(f'<polyline points="{" ".join(pts)}" fill="none" stroke="{c}" '
                     'stroke-width="2"/>')
    for t, p in zip(ts, ps):
        parts.append(f'<circle cx="{X(t):.1f}" cy="{Y(p):.1f}" r="3.2" fill="#222"/>')
    legend_y = 18
    parts.append(f'<text x="{ml}" y="{legend_y}">dots: measured ({res["signal"]} signal)</text>')
    for j, (c, f) in enumerate(zip(colors, shown)):
        r = real[id(f)]
        txt = (f"{r.name} {r.duration * 1000:.0f} ms" if f.family == "tween"
               else f"spring k={r.params[0]:g} z={r.params[1]:g}")
        parts.append(f'<text x="{ml + 230 + j * 260}" y="{legend_y}" fill="{c}">'
                     f'{_xml(txt)} (rmse {f.rmse:.3f})</text>')
    parts.append("</svg>")
    svg = seg_dir / "plot.svg"
    svg.write_text("\n".join(parts))
    if have_magick():
        try:
            run(["magick", "-density", "96", str(svg), str(seg_dir / "plot.png")])
            return str((seg_dir / "plot.png").name)
        except PrepError:
            pass
    return svg.name


def _xml(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _region_offset(args) -> str:
    if args.roi:
        x, y = args.roi.split(",")[:2]
        return f"x+{x}, y+{y}"
    return f"y+{args.crop_top}" if args.crop_top else "none"


def _write_anim_summary(out, args, info, region, adims, scale_px, results, cuts, cuts_note,
                        vw, vh, cw):
    ts_note = ("" if args.time_scale == 1 else
               f" — all durations divided by --time-scale {args.time_scale:g}")
    lines = [f"# Animation timing: {Path(args.video).name}", "",
             f"- video: {video_line(info)}",
             f"- analysed region: {region}, measured at {adims[0]}x{adims[1]} px "
             f"(1 analysis px = {scale_px:.2f} source px)",
             f"- time scale: {args.time_scale:g}{ts_note}",
             f"- saved frames show the analysed region at {vw}x{vh} (x{vw / cw:.3f}); for "
             f"--roi divide frame coordinates by {vw / cw:.3f} and add the region's offset "
             f"({_region_offset(args)})"]
    if args.window:
        lines.append(f"- window given: {args.window} s (first frame = start picture, last "
                     "frame = end picture)")
    else:
        lines.append(f"- {len(results)} motion segment(s) analysed; gap that splits segments: "
                     f"{args.gap} s" + (f"; {cuts_note}" if cuts_note else ""))
    if cuts:
        shown = ", ".join(f"{t:.3f}" for t in cuts[:20]) + (" ..." if len(cuts) > 20 else "")
        lines.append(f"- single-frame changes (instant cuts, clock ticks, cursor blinks; not "
                     f"analysed): {len(cuts)} at {shown} s")
    lines += ["", "| seg | starts | visible duration | motion | best fit | rmse |",
              "|-----|--------|------------------|--------|----------|------|"]
    for r in results:
        if "error" in r:
            lines.append(f"| {r['label']} | {r['window'][0]:.3f} s | — | {r['error']} | — | — |")
            continue
        fits = _real_fits(r, args.time_scale)
        best = fits[0] if fits else None
        start = r["times"][r["first_moving"]] if r.get("first_moving") is not None else None
        vis = (f"{fmt_ms(r['visible_duration'] / args.time_scale)} "
               f"(±{r['frame_interval'] * 1000 / args.time_scale:.0f})"
               if r.get("visible_duration") is not None else "—")
        lines.append(
            f"| {r['label']} | {f'{start:.3f} s' if start is not None else '—'} | {vis} | "
            f"{r.get('kind')} | "
            + (f"{best.name}, {fmt_ms(best.duration)}" if best else "—")
            + f" | {f'{best.rmse:.3f}' if best else '—'} |")
    for r in results:
        if "error" in r:
            continue
        lines += ["", f"## {r['label']} (window {r['window'][0]:.3f}-{r['window'][1]:.3f} s)", ""]
        files = [*r.get("sheets", [])]
        if r.get("plot"):
            files.append(f"{r['label']}/{r['plot']}")
        files += [f"{r['label']}/curve.tsv", f"{r['label']}/fit.json"]
        lines.append("- files: " + ", ".join(files))
        if r.get("note"):
            lines.append(f"- note: {r['note']}")
        track = r.get("track")
        if r.get("kind") == "still":
            lines.append("- nothing changed between the first and last frame of the window")
            continue
        if track is not None:
            spread = "" if track.spread is None else f", travel spread {track.spread:.2f}"
            lines.append(f"- geometry: {track.kind} along {track.axis}, "
                         f"{track.magnitude * scale_px:.0f} source px{spread}"
                         + ("" if track.exact else " (approximate near the ends)"))
        if r.get("signal"):
            # same predicate _write_curve_tsv uses to blank the p_edge column
            where = ("both signals are in curve.tsv" if r.get("p_edge") is not None
                     else "p_blend in curve.tsv; no edge track, so p_edge is blank")
            lines.append(f"- fitted signal: {r['signal']} ({where})")
        if r.get("visible_duration") is not None:
            fm, lm = r["first_moving"], r["last_moving"]
            lines.append(
                f"- visible change: first changed frame {r['times'][fm]:.3f} s, settled at "
                f"{r['times'][min(lm + 1, len(r['times']) - 1)]:.3f} s; frame interval "
                f"{r['frame_interval'] * 1000:.1f} ms -> {fmt_ms(r['visible_duration'] / args.time_scale)}")
        if r.get("overshoot", 0) > 0.02:
            lines.append(f"- overshoot: {r['overshoot']:.0%} past the end position (spring-like)")
        fits = _real_fits(r, args.time_scale)
        if fits:
            lines += ["", "| fit | curve | duration | rmse |", "|-----|-------|----------|------|"]
            for f in fits[:6]:
                dur = (fmt_ms(f.duration) if f.family == "tween"
                       else f"settles {fmt_ms(f.duration)}")
                lines.append(f"| {f.name} | {_fit_desc(f)} | {dur} | {f.rmse:.4f} |")
        for w in r.get("warnings", []):
            lines.append(f"- warning: {w}")
    (out / "summary.md").write_text("\n".join(lines) + "\n")


def _write_run_json(out: Path, mode: str, args, info: dict, extra: dict):
    opts = {k: v for k, v in vars(args).items() if k not in ("func",)}
    (out / "run.json").write_text(json.dumps(
        {"mode": mode, "options": opts, "video": info, **extra}, indent=2, default=str))


# --------------------------------------------------------------------------- #
# CLI

def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="mode", required=True)

    p = sub.add_parser("info", help="probe the video")
    p.add_argument("video")
    p.set_defaults(func=cmd_info)

    def common(p):
        p.add_argument("video")
        p.add_argument("--out", help="output directory (default $TMPDIR/video-prep/<name>-<mode>)")
        p.add_argument("--crop-top", type=int, default=0,
                       help="ignore this many px at the top (status bar) when detecting change")
        p.add_argument("--crop-bottom", type=int, default=0,
                       help="ignore this many px at the bottom (navigation bar)")
        p.add_argument("--roi", help="X,Y,W,H region (display px) to analyse instead")
        p.add_argument("--range", help="START-END seconds to analyse, e.g. 3-9.5")
        p.add_argument("--decimate", help="mpdecimate options, e.g. hi=512:lo=192:frac=0.2")

    p = sub.add_parser("bug", help="key screens of a bug-report recording")
    common(p)
    p.add_argument("--min-dwell", type=float, default=0.4)
    p.add_argument("--interval", type=float, default=1.0)
    p.add_argument("--brief-max", type=float, default=0.12)
    p.add_argument("--max-frames", type=int, default=40)
    p.add_argument("--per-sheet", type=int, default=8)
    p.add_argument("--view-size", type=int, default=1000, help="long edge of saved frames, px")
    p.add_argument("--extract-audio", action="store_true", help="also write audio.wav (16 kHz)")
    p.add_argument("--freeze-min", type=float, default=2.0,
                   help="no visible change for this long (s) is a freeze row")
    p.add_argument("--black-min", type=float, default=0.0,
                   help="shortest black run (s) to report; 0 = every black frame")
    p.set_defaults(func=cmd_bug)

    p = sub.add_parser("anim", help="timing and easing of animations")
    common(p)
    p.add_argument("--window", help="START-END seconds: analyse just this span as one motion")
    p.add_argument("--time-scale", type=float, default=1.0,
                   help="recorded with animator duration scale N: divide times by N")
    p.add_argument("--signal", choices=("auto", "edge", "blend"), default="auto")
    p.add_argument("--gap", type=float, default=0.12,
                   help="a pause longer than this (s) splits motion segments")
    p.add_argument("--pad", type=float, default=0.25, help="seconds kept around each segment")
    p.add_argument("--min-frames", type=int, default=2,
                   help="segments with fewer changed frames are listed as cuts")
    p.add_argument("--max-segments", type=int, default=8)
    p.add_argument("--max-view-frames", type=int, default=30)
    p.add_argument("--per-sheet", type=int, default=30)
    p.add_argument("--view-size", type=int, default=800, help="long edge of saved frames, px")
    p.add_argument("--analysis-pixels", type=int, default=160_000,
                   help="pixel budget per frame for measuring (more = finer, slower)")
    p.set_defaults(func=cmd_anim)
    return ap


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    if getattr(args, "time_scale", 1.0) <= 0:
        print("error: --time-scale must be positive", file=sys.stderr)
        return 2
    if not Path(args.video).is_file():
        print(f"error: {args.video}: no such file", file=sys.stderr)
        return 2
    try:
        return args.func(args)
    except PrepError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
