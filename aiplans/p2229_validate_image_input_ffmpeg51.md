---
Task: t2229_validate_image_input_ffmpeg51.md
Base branch: main
Output branch: main
---

# t2229 — Validate image-folder input on FFmpeg 5.1 and 7.x

## Context

t1893_6 (commit a00121816) added `bug DIR` / `anim DIR`. `video_prep.ImageInput` feeds the
images to ffmpeg as one generated ffconcat list. Each image gets `option framerate 1000000`
and its µs `duration`. The input runs with `-itsoffset <t0> -f concat -safe 0`. Mixed
frame properties are normalised to uniform PNGs, and the run requires exactly one
`config in time_base` showinfo line after that. The timings were measured only on ffmpeg
n9.0.2, the system build here. The documented minimum is 5.1. `_enumerate()` fails closed:
when the times differ it raises "this ffmpeg's concat demuxer does not keep the image
times". So an older ffmpeg may refuse to run, but it never gives wrong times. This task
measures the real behaviour on 5.1 and on one 7.x build. Where a version falls short, it
documents the real minimum and makes the tests skip below it, with a reason, instead of
failing.

Builds (already checked, read-only): johnvansickle.com publishes static amd64 builds. The
old-releases page has `ffmpeg-5.1.1-amd64-static.tar.xz` (40.9 MB) and
`ffmpeg-6.0.1-amd64-static.tar.xz`. `releases/ffmpeg-release-amd64-static.tar.xz` was last
modified 2024-08-24, which should be 7.0.2; step 1 checks this with `-version`. No `.md5`
files exist for the old releases, so step 1 records a sha256 of each archive for
provenance. BtbN only carries n8.1 and n9.0. The 5.1 branch is tested as 5.1.1, the
oldest 5.1.x on offer. Machine: x86_64.

## Implementation

All binaries and probe scripts go in the session scratchpad
(`$SP=/tmp/claude-1000/-home-ddt-Work-aitasks/<session>/scratchpad`). Nothing is installed
system-wide, and `/usr/bin/ffmpeg` is never touched. Each archive is extracted into its
own empty directory.

1. **Provision on a PATH shim.**
   - Download 5.1.1 and the release build (expected 7.0.2) into `$SP/ffdl/<ver>/`.
     `sha256sum` each archive and extract it there.
   - Make `$SP/ffbin/<ver>/` holding only `ffmpeg` and `ffprobe` symlinks to the static
     binaries.
   - Check that `PATH=$SP/ffbin/<ver>:$PATH ffmpeg -version | head -1` and
     `ffprobe -version` both name the expected version.
   - If the release build is not 7.x, use 6.0.1 as the "6.x/7.x" build instead and say so.
   - Record the sha256 of each archive, the `-version` line and the
     `--enable-libwebp`/`libwebp_anim` presence (`ffmpeg -hide_banner -encoders | grep webp`).

2. **Direct per-claim probes (attribution per claim, not just a red/green suite).** Write
   `$SP/probe_concat.py`. It builds tiny PNG fixtures with the existing helpers, and it
   parses the logs with the real `vp_core.parse_showinfo_frames` /
   `parse_showinfo_timebase` / `count_showinfo_configs` functions, imported from
   `.aitask-scripts/screen_recording`. It runs `video_prep.ImageInput`'s own argv shapes
   (copied exactly from `_use_list` / `_enumerate` / `_normalize` / the mixed-codec
   conversion), and prints one PASS/FAIL line per claim per version:
   - (a) a concat list with `option framerate 1000000` and durations 7000/16700/33300 µs
     gives showinfo time base `1/1000000` and pts exactly 0, 7000, 23700. The control, the
     same list without the `option` line, shows the times being lost, which proves the
     probe can fail.
   - (b) `-itsoffset 7.040000` gives first pts 7040000.
   - (c) `-safe 0` accepts the `option` lines. Control: the default safe=1 refuses
     ("option not allowed if safe").
   - (d) single-configuration rule:
     - an RGB/gray/RGB/gray PNG list prints >1 `config in time_base` line;
     - the `_normalize` argv (`format=rgb24`, `-fps_mode passthrough`,
       `-start_number 0`, `norm/%06d.png`) writes N files numbered from 000000;
     - the second list over `norm/` prints exactly 1 config line.
   - (e) `-frames:v 1 -update 1 <out.png>` (mixed-codec conversion) and `-frames:v 2`
     with `-f null` (`_require_one_frame`) are accepted with exit 0.

   Run it under native n9.0.2 too (the baseline) and under each shim.

3. **Suite runs per version.** For native, 5.1.1 and 7.x:
   - `PATH=$SP/ffbin/<ver>:$PATH python3 -m unittest -v tests.test_screen_recording_cli.ImageFolderInput`
   - the whole `tests/test_screen_recording_cli.py` (`-v`)
   - `tests/test_screen_recording_core.py` if it exists, as a sanity check (it needs no
     ffmpeg)

   Capture each run's `-v` output to `$SP/runs/<ver>-<scope>.log`. Compare the **set of
   failing/erroring/skipped test ids** per version against native, not the exit codes. For
   each non-native failure, record which claim from step 2 explains it. The fixture
   generators (`synth.encode`, ffmpeg-written webp) also run under the shim, so a failure
   inside fixture creation is classed "fixture-side", not ImageInput. Confirm on 5.1.1
   that `test_animated_image_beside_other_codecs_is_refused` is **skipped** with "cannot
   decode an animated webp" (or "cannot write"), and never fails.

4. **Branch on the evidence.**
   - **(A) Every claim holds on 5.1.1 and 7.x, and ImageFolderInput passes or skips only
     for the documented webp reason.** No production change. Add one sentence to the
     section comment above `STAGE_RATE` in `video_prep.py` naming the versions the concat
     timing was measured on (5.1.1, 7.x, 9.0.2). Leave the docs unchanged: "5.1 or later"
     is then verified.
   - **(B) The time guard fires on a version** (claim a, b or c fails, and the CLI refuses
     with "does not keep the image times").
     - Find the lowest available build that passes: also provision 6.0.1, and 5.0.1/4.4.1
       are not needed since the floor is ≥5.1.
     - Document the image-input minimum in `website/content/docs/skills/aitask-screen-recording.md`:
       the Requirements bullet at ~l.450 and the troubleshooting row at ~l.397 ("needs
       FFmpeg X or later" instead of "try a current release").
     - Document it in `.claude/skills/aitask-screen-recording/SKILL.md` (the Requirements
       bullet, ~l.56), the `video_prep.py` module docstring (~l.19) and the
       `aitask_screen_recording.sh` header (~l.13). Video input stays 5.1.
     - Tests: add a module-level, cached **capability probe** `ffmpeg_concat_timing()` in
       `tests/test_screen_recording_cli.py`. It is **independent of the code under test**:
       it never imports or calls `ImageInput`, `_use_list`, `STAGE_RATE` or `_us`, and it
       does not parse a version string (git builds print `N-…-g<sha>`).
       - It writes its own fixed, hand-written ffconcat text into a `tempfile` dir: three
         1×1 PNGs, a literal `option framerate 1000000` line per file, and literal
         durations `0.007000` / `0.016700` / `0.033300`.
       - It runs raw `ffmpeg -itsoffset 7.040000 -f concat -safe 0 -i list -vf showinfo
         -fps_mode passthrough -f null -`, the claim (a)+(b)+(c) shape from step 2. It
         reads time base and pts with a regex local to the test, not
         `vp_core.parse_showinfo_*`, so a parser regression cannot skip the class either.
       - It returns one of three states:
         - `"keeps"` — exit 0, 3 frames, tb `1/1000000`, pts exactly 7040000, 7047000,
           7063700;
         - `"loses"` — exit 0 and 3 frames, but another tb or other pts (the real
           version-limitation evidence);
         - `"broken: <why>"` — anything else: a non-zero exit, another frame count, or no
           time-base line.
     - Gating:
       - `ImageFolderInput` is `skipIf(state == "loses", "this ffmpeg's concat demuxer
         does not keep the image times (raw probe: <tb/pts seen>); image-folder input needs
         FFmpeg ≥ X")`. Whenever the independent probe says `"keeps"`, the real
         ImageInput tests run, so an implementation regression (a dropped `option` line,
         `-itsoffset` or `-safe 0`) **fails** them and is never skipped.
       - A `"broken"` state never skips: a dedicated `test_ffmpeg_concat_probe_ran` fails
         with the reason, so a probe that cannot run is never read as "unsupported".
     - Add a sibling class `ImageFolderInputUnsupported`, gated `skipUnless(state ==
       "loses")`. It asserts that `bug DIR` exits 1 with the guard message and writes no
       output dir. On an old ffmpeg the refusal is then positively tested.
     - Mutation control (scratch only, reverted by re-applying the saved diff; never `git
       restore` in this shared dirty tree): under a **supporting** shim, temporarily drop
       `option framerate` from `_use_list`. Expect: probe `"keeps"`, ImageFolderInput
       **fails** (not skipped), Unsupported skipped. This proves the masking path is
       closed.
   - **(C) Something fails outside the guard**: an argv refused (claim e), wrong output
     without a refusal, a crash, or claim d failing. That is a real defect.
     - If it is local to `ImageInput` (e.g. `-update 1` unknown), fix it in `video_prep.py`
       so the same code works on every version, and add the claim as a regression check.
     - If not, widen the fail-closed refusal to cover it and handle it as in (B).
     - Failures outside ImageFolderInput (the video-mode tests on 5.1.1) are recorded and
       handed to a follow-up task, or to a note to the owning task. They are not fixed
       here.

5. **Re-run** step 3 for every version after any change, plus the step 4(B) control: under
   the shim of a failing version, `ImageFolderInputUnsupported` runs and passes, and
   `ImageFolderInput` is skipped with the reason. Run `shellcheck` if the wrapper changed.
   If the website changed, run `cd website && python3 check_links.py --build`.

6. **Closure evidence.** Paste the per-version table into the plan's Final Implementation
   Notes, so the result outlives the scratchpad. It holds the sha256, the `-version`
   line, the claim a–e results and the failing/skipped test sets. `probe_concat.py` is
   kept verbatim in the notes as well.

Step 9 (Post-Implementation) handles the commit, archival and merge as usual. This is
current-branch mode, so there is no worktree.

## Verification

- Every run in step 3 is logged with its PATH and `ffmpeg -version`. Native results
  match the pre-change baseline.
- In outcome A: ImageFolderInput passes on all three versions, and the webp test is
  skipped on 5.1.1 for the decoder reason.
- In outcome B: on a failing version the raw probe reads `loses`, ImageFolderInput is
  skipped with the reason and the refusal class passes. On a supporting version the probe
  reads `keeps`, the refusal class is skipped and ImageFolderInput passes. With the
  scratch `_use_list` mutation on a supporting shim, ImageFolderInput **fails**. All three
  are observed under real shims, and the mutation is undone afterwards (the
  `git diff --stat` of the touched files matches the pre-mutation diff).
- `git status` shows no change outside the files named above. The scratchpad holds all the
  downloads.

## Risk

### Code-health risk: low
- A skip gate built on the code under test would mask regressions: a broken `_use_list`
  would read as "unsupported ffmpeg", and the refusal class would pass on the broken code
  (outcome B only). · severity: low (residual) · → mitigation: none needed, it is designed
  out in step 4(B). The probe is raw ffmpeg plus a hand-written list and a test-local
  regex, sharing no code with ImageInput. Its third state (`broken`) fails rather than
  skips. A step-4(B) mutation control proves a dropped `option` line fails
  ImageFolderInput under a supporting shim.

### Goal-achievement risk: medium
- The builds are third-party static builds (johnvansickle) of 5.1.1 and 7.0.2, not 5.1.0
  or distro builds, and no checksum is published for the old releases. A distro build
  configured differently (for example without libwebp) could behave differently in
  fixture-side paths. · severity: low · → mitigation: none needed. The concat, showinfo and
  itsoffset paths are core libavformat/libavfilter code, independent of configure options;
  step 1 records the sha256 and the encoder list as provenance.
- The release archive might not be 7.x. · severity: low · → mitigation: none needed. Step 1
  checks `-version` and falls back to 6.0.1.
- The video-mode tests may fail on 5.1.1 for reasons outside this task. · severity: medium
  · → mitigation: none needed. Step 4(C) hands them to a follow-up or note instead of
  widening this task.

## Final Implementation Notes

- **Outcome: A.** Every claim the image-folder input depends on holds on FFmpeg 5.1.1, 7.0.2 and the native n9.0.2. The documented "ffmpeg 5.1 or later" minimum is now **verified for image input too**, so no docs, Requirements or skill page change was needed. Steps 4(B)/(C) did not apply: no capability probe, no skip gate and no refusal class was added, and no mutation control was needed.
- **Actual work done:**
  - `video_prep.py`: a comment-only addition to the section comment above `STAGE_RATE` naming the measured versions.
  - `tests/test_screen_recording_cli.py`: comment-only. The animated-WebP skip comment said "some builds (FFmpeg 5.1)", but 7.0.2 also cannot decode the animation, so the comment now names both.
- **Builds** (johnvansickle.com static amd64; no checksum is published for these, so the sha256 is recorded here as provenance; on PATH shims in the session scratchpad, never installed):

  | build | archive | sha256 | `-version` | webp encoders |
  |---|---|---|---|---|
  | 5.1.1 | old-releases/ffmpeg-5.1.1-amd64-static.tar.xz (40971084 B) | 2d848c37f7f276be0262d9123a84fbfe72bb159921ffcce3bd7106f143d29f42 | ffmpeg version 5.1.1-static | libwebp_anim, libwebp |
  | 7.0.2 | releases/ffmpeg-release-amd64-static.tar.xz (41888096 B, Last-Modified 2024-08-24) | abda8d77ce8309141f83ab8edf0596834087c52467f6badf376a6a2a4c87cf67 | ffmpeg version 7.0.2-static | libwebp_anim, libwebp |
  | native | /usr/bin/ffmpeg | — | ffmpeg version n9.0.2 | (system) |

- **Per-claim probe** (`probe_concat.py` below; same results on all three builds):

  | claim | 5.1.1 | 7.0.2 | n9.0.2 |
  |---|---|---|---|
  | a: `option framerate 1000000` → tb 1/1000000, pts 0/7000/23700 | PASS | PASS | PASS |
  | a-control: without the option → tb 1/25, pts 0/0/1 | OK | OK | OK |
  | b: `-itsoffset 7.040000` → 7040000/7047000/7063700 | PASS | PASS | PASS |
  | c: `-safe 0` accepts `option` | PASS | PASS | PASS |
  | c-control: default safe refuses ("option not allowed if safe") | OK (rc 1) | OK (rc 183) | OK (rc 183) |
  | d1: rgb24/gray alternation → 4 `config in time_base` lines | PASS | PASS | PASS |
  | d2: normalise argv (`format=rgb24`, `-start_number 0`) → 000000..000003.png | PASS | PASS | PASS |
  | d3: list over `norm/` → exactly 1 config, exact pts | PASS | PASS | PASS |
  | e1: `-frames:v 1 -update 1` jpeg → png | PASS | PASS | PASS |
  | e2: `-frames:v 2 -f null` counts 1 frame | PASS | PASS | PASS |

- **Suite runs** (`python3 -m unittest -v`, PATH shim first):

  | scope | n9.0.2 | 5.1.1 | 7.0.2 |
  |---|---|---|---|
  | `ImageFolderInput` (17) | OK, 0 skipped | OK, 1 skipped | OK, 1 skipped |
  | whole `test_screen_recording_cli.py` (104) | OK, 0 skipped | OK, 2 skipped | OK, 1 skipped |
  | `test_screen_recording_core` (123, no ffmpeg) | OK | — | — |

  The skipped set, by test id; failures and errors were empty on every build:
  - `ImageFolderInput.test_animated_image_beside_other_codecs_is_refused` is skipped on 5.1.1 **and** 7.0.2 with "this ffmpeg cannot decode an animated webp (counted 'N/A')". It skips and does not fail, as the task required.
  - `FramesMode.test_rotated_recording_geometry_is_in_display_orientation` is skipped on 5.1.1 only, with "cannot write a display matrix: Unrecognized option 'display_rotation'". This is fixture-side: the test's own encoder flag, not production code.
  - The same ImageFolderInput results repeated after the comment edits.
- **Deviations from plan:** none. 6.0.1 was not needed: the release build is 7.x and 5.1.1 passed.
- **Issues encountered / observation (not fixed; outside the timing contract):** on 5.1.1 and 7.0.2 an animated WebP in a folder fails closed (rc 1, no output dir written). The message is ffmpeg's raw log tail, though: "error: ffmpeg failed (1): … image data not found" on 5.1.1, "failed (69): … Decode error rate 1 exceeds maximum" on 7.0.2. It does not name the user's file and does not say "animated image". Offered as a follow-up at review.
- **Upstream defects identified:**
  - `.aitask-scripts/screen_recording/video_prep.py:642-651` — `ImageInput._require_one_frame` (and `_enumerate` for an all-WebP folder) surfaces ffmpeg's raw decode-failure tail when this ffmpeg cannot decode an animated WebP (5.1.1, 7.0.2). It fails closed but never names the user's file or says the image is animated.
- **Key decisions:** the user's plan review made the outcome-B skip gate independent of `ImageInput` (raw ffmpeg probe, three states, mutation control). It went unused because outcome A held. That lesson is kept as a memory.

### probe_concat.py (verbatim)

```python
#!/usr/bin/env python3
"""t2229: per-claim probe of the ffmpeg behaviours video_prep.ImageInput relies on.

Runs ImageInput's argv shapes (copied from _use_list / _enumerate / _normalize /
the mixed-codec conversion / _require_one_frame) against whatever `ffmpeg` is
first on PATH, and parses the logs with the real vp_core showinfo parsers.
Prints one PASS/FAIL line per claim, plus one CONTROL line per negative
control (a control must show the property *failing*, proving the claim's check
can fail). Exit 0 iff every claim passed and every control behaved.

Usage: PATH=<shim>:$PATH python3 probe_concat.py <repo root>
"""
import struct
import subprocess
import sys
import tempfile
import zlib
from pathlib import Path

REPO = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(REPO / ".aitask-scripts" / "screen_recording"))
import vp_core as core  # noqa: E402

FF = ["ffmpeg", "-hide_banner", "-nostdin", "-nostats", "-loglevel", "info"]
ok = True


def png(path: Path, w: int, h: int, *, rgb: bool, fill: int = 128):
    """A minimal 8-bit PNG: gray (color type 0) or RGB (color type 2)."""
    ch = 3 if rgb else 1
    raw = b"".join(b"\x00" + bytes([fill]) * (w * ch) for _ in range(h))

    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2 if rgb else 0, 0, 0, 0)
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
                     + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))


def run(args):
    cp = subprocess.run([*FF, *args], capture_output=True, text=True)
    return cp.returncode, cp.stderr


def report(kind, name, cond, detail):
    global ok
    good = cond if kind == "CLAIM" else cond   # a control's cond = "behaved as expected"
    if not good:
        ok = False
    label = ("PASS" if cond else "FAIL") if kind == "CLAIM" else ("OK" if cond else "BAD")
    print(f"{kind} {label:4} {name}: {detail}")


def write_list(d: Path, files, durs_us, *, option=True, name="list.ffconcat"):
    lines = ["ffconcat version 1.0"]
    for f, us in zip(files, durs_us):
        lines.append(f"file '{f}'")
        if option:
            lines.append("option framerate 1000000")
        lines.append(f"duration {us // 1_000_000}.{us % 1_000_000:06d}")
    p = d / name
    p.write_text("\n".join(lines) + "\n")
    return p


def enumerate_pass(lst: Path, offset: str = "0.000000", safe: str | None = "0"):
    ffin = ["-itsoffset", offset, "-f", "concat"]
    if safe is not None:
        ffin += ["-safe", safe]
    rc, err = run([*ffin, "-i", str(lst), "-an", "-vf", "showinfo", "-fps_mode", "passthrough",
                   "-f", "null", "-"])
    frames = core.parse_showinfo_frames(err)
    return rc, err, core.parse_showinfo_timebase(err), [f.pts for f in frames], \
        core.count_showinfo_configs(err)


with tempfile.TemporaryDirectory(prefix="t2229-probe-") as tmp:
    d = Path(tmp)
    files = []
    for k in range(3):
        name = f"img_{k + 1:06d}.png"
        png(d / name, 16, 16, rgb=True, fill=40 + 60 * k)
        files.append(name)
    durs = [7000, 16700, 33300]

    # (a) option framerate -> tb 1/1e6, exact µs pts
    lst = write_list(d, files, durs)
    rc, err, tb, pts, _ = enumerate_pass(lst)
    report("CLAIM", "a option-framerate-exact-us", rc == 0 and str(tb) == "1/1000000"
           and pts == [0, 7000, 23700], f"rc={rc} tb={tb} pts={pts}")
    lst0 = write_list(d, files, durs, option=False, name="noopt.ffconcat")
    rc0, _, tb0, pts0, _ = enumerate_pass(lst0)
    report("CONTROL", "a without-option-loses-times", not (str(tb0) == "1/1000000"
           and pts0 == [0, 7000, 23700]), f"rc={rc0} tb={tb0} pts={pts0}")

    # (b) -itsoffset puts the first image at its named time
    rc, err, tb, pts, _ = enumerate_pass(lst, offset="7.040000")
    report("CLAIM", "b itsoffset-shifts-first-image", rc == 0 and str(tb) == "1/1000000"
           and pts == [7040000, 7047000, 7063700], f"rc={rc} tb={tb} pts={pts}")

    # (c) -safe 0 accepts the option lines; default safe refuses them
    rc, err, tb, pts, _ = enumerate_pass(lst)
    report("CLAIM", "c safe0-accepts-option", rc == 0 and len(pts) == 3, f"rc={rc} n={len(pts)}")
    rcs, errs, _, ptss, _ = enumerate_pass(lst, safe=None)
    refused = rcs != 0 and "option not allowed if safe" in errs
    report("CONTROL", "c default-safe-refuses-option", refused,
           f"rc={rcs} n={len(ptss)} msg={'yes' if 'option not allowed' in errs else 'no'}")

    # (d) single-configuration rule
    pf = d / "pf"
    pf.mkdir()
    pfiles = []
    for k, rgb in enumerate([True, False, True, False]):
        name = f"img_{k + 1:06d}.png"
        png(pf / name, 32, 32, rgb=rgb, fill=128)
        pfiles.append(name)
    plst = write_list(pf, pfiles, [1_000_000] * 4)
    rc, err, tb, pts, configs = enumerate_pass(plst)
    fmts = [f.fmt for f in core.parse_showinfo_frames(err)]
    report("CLAIM", "d1 pixfmt-alternation-reconfigures", rc == 0 and configs > 1 and len(pts) == 4,
           f"rc={rc} configs={configs} fmts={fmts}")
    norm = pf / "norm"
    norm.mkdir()
    rc, err = run(["-itsoffset", "0.000000", "-f", "concat", "-safe", "0", "-i", str(plst),
                   "-an", "-vf", "format=rgb24", "-fps_mode", "passthrough",
                   "-start_number", "0", str(norm / "%06d.png")])
    out = sorted(p.name for p in norm.iterdir())
    report("CLAIM", "d2 normalise-writes-from-000000", rc == 0 and out == [f"{i:06d}.png" for i in range(4)],
           f"rc={rc} out={out}")
    nlst = write_list(pf, [f"norm/{n}" for n in out], [1_000_000] * 4, name="norm.ffconcat")
    rc, err, tb, pts, configs = enumerate_pass(nlst)
    report("CLAIM", "d3 normalised-list-configures-once", rc == 0 and configs == 1
           and pts == [0, 1_000_000, 2_000_000, 3_000_000], f"rc={rc} configs={configs} pts={pts}")

    # (e) mixed-codec conversion and the one-frame check
    jpg = d / "src.jpg"
    rc, err = run(["-f", "lavfi", "-i", "color=c=gray:s=16x16:d=0.04", "-frames:v", "1", str(jpg)])
    if rc != 0:
        report("CLAIM", "e0 jpeg-fixture", False, f"rc={rc} {err[-200:]}")
    rc, err = run(["-i", str(jpg), "-frames:v", "1", "-update", "1", str(d / "conv.png")])
    report("CLAIM", "e1 frames1-update1-to-png", rc == 0 and (d / "conv.png").exists(), f"rc={rc}")
    rc, err = run(["-i", str(d / files[0]), "-an", "-vf", "showinfo", "-fps_mode", "passthrough",
                   "-frames:v", "2", "-f", "null", "-"])
    n = len(core.parse_showinfo_frames(err))
    report("CLAIM", "e2 frames2-null-counts-one", rc == 0 and n == 1, f"rc={rc} frames={n}")

v = subprocess.run(["ffmpeg", "-version"], capture_output=True, text=True).stdout.splitlines()[0]
print(f"FFMPEG: {v}")
print("PROBE:", "ALL_OK" if ok else "SOME_FAILED")
sys.exit(0 if ok else 1)
```
