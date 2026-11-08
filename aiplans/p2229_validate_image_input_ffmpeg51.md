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
