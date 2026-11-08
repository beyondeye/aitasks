---
Task: t2238_name_the_file_when_animated_webp_cannot_decode.md
Base branch: main
Output branch: main
---

# t2238 — Name the file when this ffmpeg cannot decode an image (animated WebP)

## Context

`bug DIR` / `anim DIR` with an animated WebP that this ffmpeg cannot decode
(5.1.1, 7.0.2 — measured in t2229) fails closed, but the PrepError is only
`run()`'s raw 12-line stderr tail ("ffmpeg failed (1): … image data not found …
Conversion failed!"). It does not name the user's file and does not say that the
image is animated. Two routes:

1. **Mixed codecs** — `ImageInput._require_one_frame(path)`
   (`.aitask-scripts/screen_recording/video_prep.py`, ~l.698) runs a 2-frame
   showinfo decode of each non-PNG. `self._ffmpeg()` raises PrepError → raw tail.
2. **One codec (e.g. all WebP)** — no `_require_one_frame`; the failure comes
   from `_enumerate()`'s concat showinfo pass (~l.731), either as a PrepError
   from `self._ffmpeg()` or as `len(frames) < n` ("ffmpeg decoded k of the n
   images"). Neither says which image.

Measured during planning (scratch, not committed): a hand-built WebP with the
VP8X animation flag, an `ANIM` chunk and two `ANMF` frames whose VP8L payload is
garbage fails the 2-frame decode on **all three** ffmpegs (n9.0.2 rc=69,
5.1.1 rc=1, 7.0.2 rc=69; 0 showinfo frames). So a test built on it runs on any
ffmpeg instead of skipping.

### Pre-phase (risk mitigations)

**shared-file-gate** — coordination gate on shared dirty files, before the FIRST edit.

t2219 (live session, pid 1335247, `Implementing`) has **uncommitted** hunks in
`video_prep.py`, `vp_core.py`, `tests/test_screen_recording_cli.py` and
`tests/test_screen_recording_core.py`. Its path-scoped commit would absorb my
edits. So:

- Do not edit `video_prep.py` or `tests/test_screen_recording_cli.py` until
  `git diff --quiet HEAD -- <file>` passes **and** HEAD's blob contains t2219's
  hunks (`git show HEAD:<file> | grep -qF 'def measure_labels'` /
  `'def sheet_tiles'` for video_prep; a t2219 test name for the CLI test file).
- Then use the last-accepted-state chain: record sha256 after each of my writes;
  before every later write and before the commit, check the sha is unchanged,
  `HEAD:<file>` is unchanged, and `git diff --cached --quiet -- <file>`.
- While waiting: nothing else to do (all work is in these two files). If the gate
  still fails, **stop and ask the user** (wait, or agree an explicit handover).
  Never stash or restore.

## Implementation (`.aitask-scripts/screen_recording/video_prep.py`)

1. **`webp_animated(path) -> bool`** next to `sniff_image()`: read the first 21
   bytes; true when `RIFF....WEBP` + chunk `VP8X` at offset 12 and the flags byte
   (offset 20) has the animation bit `0x02` set (WebP container spec). OSError →
   False. This is read from the file's bytes, so the message can say "animated"
   as a fact, not a guess.

2. **`ImageInput._undecodable(self, name, kind, detail) -> PrepError`**: one
   message builder:
   - animated WebP: `f"{name}: this ffmpeg could not decode it (an animated WebP:
     its header declares animation); keep still images only"`
   - otherwise: `f"{name}: this ffmpeg could not decode it"`
   - then `"\n" + detail` (ffmpeg's tail, already passed through `_explain`) when
     detail is given, so the original error is kept.

   The wording states only what is established: the file declares animation
   (VP8X flag, read from its bytes) and this ffmpeg failed to decode it. It does
   **not** claim the decoder lacks animation support — a decode failure plus the
   flag cannot prove that (the garbage-payload fixture below fails on n9.0.2 too,
   which does decode real animation). No ffmpeg version is named.

3. **`_require_one_frame(path, kind)`** (pass `kind` from the caller loop): wrap
   the `self._ffmpeg([...])` call in `try/except PrepError as exc` →
   `raise self._undecodable(path.name, kind, str(exc)) from exc`. The `n < 1`
   branch ("ffmpeg decoded no frame from X") also uses `_undecodable(...,
   None)` so an animated WebP that decodes to nothing gets the same message.
   `n > 1` unchanged.

4. **`_enumerate()`**: on a PrepError from the concat pass, or when
   `len(frames) < n`, call **`self._find_undecodable()`** before raising the
   existing error:
   - for each `(name, kind)` in `zip(self.names, self.kinds)`, run the same
     2-frame showinfo decode on `self.folder / name` (factor the argv into a
     small `_decode_two(path)` used by `_require_one_frame` too);
   - the first file that raises or yields 0 frames → raise
     `self._undecodable(name, kind, detail)` chained to the original error;
   - if every file decodes, re-raise the original error unchanged (the failure
     is not a per-file decode problem).
   Failure path only — the success path keeps its single concat pass. The second
   `_enumerate()` (over normalised PNGs) shares the path harmlessly: originals
   decode, so the original error is re-raised.

## Tests (`tests/test_screen_recording_cli.py`, `ImageFolderInput`)

A fixture helper `write_bad_animated_webp(path, animated=True)` building the
crafted RIFF (VP8X flags 0x02 / 0x00, ANIM + ANMF with garbage VP8L when
animated; a still VP8X + garbage VP8L otherwise).

- `test_undecodable_animated_webp_is_named` — subtests over
  {mixed: `t00000000.png` + bad `t00001000.webp`; all-webp: valid still
  `t00000000.webp` + bad `t00001000.webp`} × {bug, anim}: rc 1, stderr contains
  `t00001000.webp: this ffmpeg could not decode it (an animated WebP` and does
  **not** contain `t00000000.webp: this ffmpeg could not decode it`; no output
  dir written (fail closed). The all-webp case is the one that proves
  `_find_undecodable()` skips an original that decodes and finds a **later**
  failing file (the mixed case reaches the direct per-file check instead).
  The valid still WebP is written with raw ffmpeg `-c:v libwebp -frames:v 1`;
  premise (raw ffprobe, never the code under test): it exists and counts
  exactly 1 frame, else `skipTest` (all three measured ffmpegs ship `libwebp`).
- `test_undecodable_still_webp_is_named_without_animation_claim` — still VP8X
  garbage webp beside a png: names the file, does **not** contain "animated".
- In-process unit check of `webp_animated()` on both crafted files and a PNG.
- Leave `test_animated_image_beside_other_codecs_is_refused` as is (still
  skips on 5.1.1/7.0.2 for its decoder premise); update its comment to point to
  the new test that covers that path on every ffmpeg.

### Post-phase (risk mitigations)

**real-repro-under-shims** — after the tests pass natively, rebuild the real t2229
fixture (PNG `t00000000.png` + `t00001000.webp` written by native n9.0.2 with
`libwebp_anim`, 2 frames; plus an all-WebP folder of a still `libwebp`
`t00000000.webp` followed by that animated `t00001000.webp`) and run
`bug DIR` / `anim DIR` under the 5.1.1 and 7.0.2 shims. Expect rc 1, no output
dir, and stderr starting `error: t00001000.webp: this ffmpeg could not decode it
(an animated WebP: its header declares animation)`, followed by ffmpeg's
original error tail. Under native n9.0.2 the same folders still give the
existing `decodes to more than one frame` refusal (no regression). Record the exact stderr lines in the plan's Final
Implementation Notes (durable closure evidence).

## Verification

1. **Red proof**: the new tests fail against the pre-fix code — run them in a
   scratch copy of the repo's `screen_recording/` + test file at HEAD (never stash
   or restore in the shared tree) and confirm the "could not decode it" asserts fail.
   **Mutation control** (same scratch copy, post-fix): make `_find_undecodable()`
   blame the first entry unconditionally — the all-webp subtest must fail on
   the "later file" assertion; the mixed subtest is expected to stay green.
2. Native n9.0.2: `python3 -m pytest tests/test_screen_recording_cli.py -k ImageFolderInput`
   and the whole `test_screen_recording_cli.py` / `test_screen_recording_core.py`.
3. Under the t2229 PATH shims (5.1.1, 7.0.2 in
   `/tmp/claude-1000/-home-ddt-Work-aitasks/1de1fa99-…/scratchpad/ffbin/<ver>`):
   the new tests pass, and the real t2229 repro of the post-phase
   **real-repro-under-shims** prints the new message (see that step).
4. Step 9 (Post-Implementation): commit only the two named files with
   `bug: … (t2238)`, plan file via `aitask_task_commit.sh`, archive.

## Risk

### Code-health risk: low
- `_enumerate()` gains a failure-only diagnosis loop (one 2-frame decode per image, only after the concat pass already failed); the success path is unchanged · severity: low · → mitigation: None needed
- Shared dirty files with live t2219: an edit before its commit would be swept into its commit · severity: medium · → mitigation: inline pre-phase shared-file-gate

### Goal-achievement risk: low
- Diagnosis wording could overclaim a decoder limitation it cannot prove · severity: low · → mitigation: message states only the declared-animation flag + decode failure, keeps ffmpeg's original error (review round 1)
- The search could blame the first image instead of the failing one · severity: low · → mitigation: all-webp test with a valid still WebP before the bad one + blame-first mutation control (review round 1)
- The crafted garbage WebP stands in for a real animated WebP that an old ffmpeg rejects; it exercises the same code route but not the same decoder message · severity: low · → mitigation: inline post-phase real-repro-under-shims

Confirmed mitigations (user, "Apply recommended dispositions"): shared-file-gate → inline pre-phase; real-repro-under-shims → inline post-phase. Reassessed with both inlined: code-health low, goal-achievement low.
