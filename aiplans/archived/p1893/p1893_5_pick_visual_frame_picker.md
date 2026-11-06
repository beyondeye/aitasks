---
Task: t1893_5_pick_visual_frame_picker.md
Parent Task: aitasks/t1893_screen_recording_skill_expansion.md
Sibling Tasks: aitasks/t1893/t1893_6_*.md … aitasks/t1893/t1893_14_*.md
Archived Sibling Plans: aiplans/archived/p1893/p1893_*_*.md
Base branch: main
Output branch: main
---

# Plan: `pick`, a visual HTML+JS frame picker (t1893_5)

## Context

The user asked (note 2 to t1888) for a visual way to choose which frames reach the
agent. The flow:

1. the skill extracts frames;
2. the agent asks whether the user wants to pick frames;
3. on yes, a helper builds a static HTML+JS page and opens it;
4. the user selects frames, copies a paste-ready block and pastes it back.

t1893_3 (`frames`, the `frames.tsv` geometry plus SHA-256) and t1893_4 (`sheet`,
`plan_sheet`, ImageMagick hygiene) are done. This task adds
`aitask_screen_recording.sh pick <frames-dir|run-dir> [--open] [--out DIR]`.

Two inputs shape the design:

- **Advisory note from t1893_1 (acknowledged):** reference tables go on the skill
  page; how-tos go in `workflows/screen-recordings/` subpages listed in both
  indexes.
- **Sibling notes (t1893_3/4):**
  - trust a `frames.tsv` row only while `sha256(file) == sha256`;
  - source px = `crop_x + img_x · crop_w/out_w`;
  - the strict `parse_frame_name` stays the default;
  - `plan_sheet` orders a folder the way `sheet` does;
  - machine-readable files keep exact names.

**Plan review (2026-11-06):** the user raised five concerns, all verified in the
code and addressed below:
1. **Run layouts first.** `bug` writes `sheet_NN.png` in the run root, so pick
   recognises run layouts before treating root images as a folder.
2. **Windowed anim runs.** `anim --window` writes `w01/frames/`, so the resolver
   accepts it.
3. **Unique snapshot names.** Snapshot destinations are allocated uniquely,
   with an exclusive create.
4. **Escaping the embedded JSON.** The plan text had decoded the escape to a
   bare `<`; it is now written out as backslash-`u003c`, and the test fixtures
   can actually exist on disk.
5. **Smoke-test oracle.** The headless smoke test checks expectations written
   down independently of the UI, after each action.
6. (second round) **Source video only from a proven path.** `run.json` stores
   the raw video argument without its cwd. Producers now record
   `video_abspath` plus `video_size`, and pick never re-resolves a relative
   path; otherwise it falls back to `<VIDEO>` with the reason.

## Facts checked (2026-11-05, this host)
- node v26.13.0, chromium and xdg-open are on PATH. Python 3.14.
- `ait_is_wsl` (`lib/terminal_compat.sh:73`): `/proc/version` contains
  `microsoft`, matched case-insensitively.
- `region_box` (`video_prep.py:117`) accepts `--roi X,Y,W,H` as ints with
  `w,h > 0`, `x,y ≥ 0` and `x+w ≤ W`, `y+h ≤ H`, in display px.
- anim `--window A-B` decodes `trim=start=A−1e-4:end=B+1e-4`. Frame 0 of the
  window is the start picture and the last frame is the end picture
  (`video_prep.py:1033`, `vp_core.analyze_frames`).
- The anim summary's endpoint diagnostics are:
  - `visible change: first changed frame X s, settled at Y s`;
  - `kind` (still / returns);
  - overshoot;
  - warnings.
- **Names and `t_ms` are rounded ms.** frames writes half-up from the exact
  `pts·tb`; bug/anim write `f"{t:.3f}"`. Either way the exact time
  `t ∈ [ms−0.5, ms+0.5]` ms. `frames.tsv` carries `pts` but no time base, so the
  picker never knows exact times.
- The release tarball ships `.aitask-scripts/` whole (`release.yml:182`), and no
  ignore rule matches `.js`/`.html` there, so the page assets can be sibling
  files.

## Design

### Input resolution (`vp_pick.resolve_groups`)
Supported run layouts are recognised **before** any generic image folder. The
layouts the producers actually write:
- `bug`: `sheet_NN.png` sits in the run root (`contact_sheets(..., out, ...)`,
  `video_prep.py:812`) beside `frames/`;
- `frames`: `frames/` only;
- `anim`: `sNN/frames/` for detected segments, or `w01/frames/` for an explicit
  `--window` (`video_prep.py:986`), with that segment's sheets inside `sNN/`.

Precedence:
1. `DIR/run.json` parses:
   - `mode` `bug`/`frames` with a `DIR/frames/` → that group;
   - `mode` `anim` → every existing `DIR/<label>/frames/`, label `^[sw]\d{2,}$`,
     in natural order;
   - `mode` `sheet`/`pick` → exit 1, "this is a sheet/pick output; pick the
     folder it was made from (<run.json dir>)";
   - a run mode whose expected frames dir is missing → exit 1, naming the
     expected path. Never a silent fallback to the root's sheets.
2. No usable `run.json`, but the layout matches: `DIR/frames/` with images, or
   `DIR/[sw]NN/frames/` → those groups, the same as above.
3. Otherwise DIR's own top-level images: a frames dir given directly, or a
   folder the user edited.
4. Else exit 1, "no png/jpg/webp images in DIR, DIR/frames or
   DIR/{sNN,wNN}/frames".

The summary and run.json record which rule matched (`input_layout`).
- **Source run:** the `run.json` of the run dir (DIR, DIR/.. or DIR/../..), when
  it parses, gives the mode.
- **Source video: only a proven path, never a re-resolved one.**
  - Today `run.json` stores the raw `options.video` argument and `video.path`
    (`probe()` writes `str(video)`), with no working directory. A relative
    `clip.mp4` checked for existence from pick's cwd can therefore name a
    different recording.
  - So the producers gain provenance (step 3): `_write_run_json` adds
    `video_abspath` (`Path(video).resolve()` at write time, in the producer's
    own cwd) and `video_size` (bytes).
  - pick names the video **only** when `video_abspath` is absolute, exists, and
    its current size equals `video_size`.
  - Every other case is the `<VIDEO>` fallback, with the reason in the block's
    `# source:` line and in the summary:
    - an older run.json with only a relative `options.video`: "recorded as
      'clip.mp4' relative to an unknown directory";
    - a missing file;
    - a size mismatch: "the file at <path> changed since extraction".
  - A relative path is never resolved against pick's cwd. An absolute
    `options.video` from an older run.json is shown as "recorded path,
    unverified": never as the source, only as a hint.

### Snapshot first (`src/`)
- Each image is copied to `<out>/src/<group>/<name>` (no group dir for a single
  group).
- The **copy** is hashed (SHA-256), and its PNG size is read with
  `core.png_size`. Everything after this (geometry trust, page data,
  fingerprint) uses the snapshot only, so a concurrent rewrite of the originals
  cannot mix versions.
- A name outside `[A-Za-z0-9._()+ -]`, or one starting with `.`/`-`, is
  snapshotted under a generated name. Its original name is kept in the data and
  shown (display-sanitized), and the summary lists the renames. Snapshot paths
  in the copy block are therefore always one clean line.
- **Destinations are allocated before any copy, unique per group dir:**
  - the names a group keeps are reserved first, compared case-folded so that
    case-insensitive filesystems are covered;
  - each rename then takes the first free `renamed_NNNN<ext>`, NNNN counting
    up, skipping every reserved name;
  - every copy opens its destination with `open(dest, "xb")` (exclusive
    create), so an allocation bug is a `PrepError`, never an overwrite;
  - after copying, every recorded snapshot path must be distinct and exist, and
    its hash is the one recorded.
- Ownership: `make_out_dir(args.out, DIR, "pick", name=<run/folder name>)`, which
  never reuses a non-empty dir. Default `$TMPDIR/video-prep/<name>-pick`.
  Retention and cleanup belong to t1893_11 (work dir + `clean`). The summary
  says the picker owns everything under `<out>`.

### Order, time and Δ
- Per group, `core.plan_sheet(names)`: timed first by ms, with suffixes accepted
  as in `sheet`; untimed after, in natural order.
- `delta_ms` is to the previous timed image of the group, from the name ms
  (±1 ms).
- Grid labels: `#k`, the name, `7.040 s +33 ms` / `first` / `no time in name`.

### Geometry trust per frame (Python, embedded as data)
- `frames.tsv` beside the original group dir is parsed (csv, tab).
- A frame gets `geom = {crop_x, crop_y, crop_w, crop_h, out_w, out_h, src_w,
  src_h}` (ints) **only if** all of these hold:
  - a row exists for its name;
  - every field parses;
  - snapshot sha == row `sha256`;
  - snapshot PNG size == `(out_w, out_h)`.
- Otherwise `geom = null` and `roi_disabled = <reason>`, one of:
  - `no frames.tsv beside the image`;
  - `frames.tsv has no row for <name>`;
  - `frames.tsv row for <name> is malformed`;
  - `the image changed since extraction: its SHA-256 <12hex> differs from frames.tsv <12hex>`;
  - `not a PNG` / `its size WxH differs from frames.tsv`.
- A hash mismatch catches every edit, including crop-then-resize-back and a
  translation within the canvas.
- **Documented limitation:** supplying a corrected transform for an edited
  image is out of scope.

### ROI mapping (`vp_pick.roi_to_source`, mirrored in JS)
- The rectangle is `[x0,x1)×[y0,y1)` in the image's own integer pixels, clamped
  to the image, with ≥ 1 px on each side.
- Source coordinates, rounded outward with exact integer arithmetic:
  - `X0 = crop_x + ⌊x0·crop_w/out_w⌋`, `X1 = crop_x + ⌈x1·crop_w/out_w⌉`;
  - Y the same way;
  - clamped to `[0, src_w]` × `[0, src_h]`;
  - emitted as `--roi X0,Y0,X1−X0,Y1−Y0`, which always passes `region_box`.
- With no trusted geometry the block gives the rectangle in that image's own
  pixels, labelled as such, with the reason. It never emits `--roi`.

### Window rule (the picker certifies nothing)
- There is no pixel analysis anywhere in pick: no "still" or "settled" field,
  word or check.
- By default the block labels the first…last selected time as a **viewing
  range**, "not a measurement window".
- `--window A-B` appears **only** when the user explicitly marks a start frame
  and an end frame. Both must be timed, with start ms < end ms. Otherwise the
  block says `# no --window: <reason>` (end before start, same frame, untimed
  frame, only one mark).
- Bounds are precomputed per frame in Python as exact decimals:
  - `A = (ms_start − 0.5)/1000`, clamped to 0, e.g. `0.4825`;
  - `B = (ms_end + 0.5)/1000`.

  Because the exact time is within ±0.5 ms of the name's ms, A ≤ t_start and
  B ≥ t_end, so anim's window starts at the marked start frame and ends at the
  marked end frame.
- Neighbouring frames stay out while the frame interval is > 1.2 ms (anim's trim
  slack is 1e-4 s), i.e. below ~800 fps. That is documented as a limit.
- Label: **`user-marked endpoints (unverified)`**, plus "the anim run's own
  endpoint diagnostics decide whether to trust it".
- A note is added when an endpoint's `time_source` is `pts_time`.

### Copy block (Python reference `copy_block(data, state)`; JS `copyBlock` byte-identical)
`state = {selected:[rel…], marks:{start, end}, notes:{rel:text}, rect:{rel,x0,y0,x1,y1}|null}`.
Lines, in display order:
```
# 3 frames picked in /abs/out/index.html (set 1a2b3c4d)
# viewing range: 0.483-0.517 s (first to last selected frame; a viewing range, not a measurement window)
/abs/out/src/s01/f013_0.483s.png	t=483 ms	first
/abs/out/src/s01/f014_0.500s.png	t=500 ms	+17 ms	note: button starts to move
/abs/out/src/s01/f015_0.517s.png	t=517 ms	+17 ms
# --window 0.4825-0.5175  (user-marked endpoints (unverified): start f013_0.483s.png at 483 ms, end f015_0.517s.png at 517 ms; check the anim run's own endpoint diagnostics before trusting it)
# --roi 37,151,201,243  (source-video pixels, mapped through the frames.tsv geometry of f013_0.483s.png, SHA-256 verified)
# source: anim run of /abs/rec.mp4
```
- Δ is to the previous **selected** timed frame.
- Untimed frames read `t=unknown`.
- Notes are single-line: control characters → space, trimmed, at most 200
  chars.
- With nothing selected the block is `# no frames selected in <page>`.

### Page (static, no server)
- `<out>/index.html` is self-contained. `vp_pick.render_page` inlines three
  sibling assets into it: `pick_page.html` (markup and CSS, with placeholders),
  `pick_logic.js` (pure functions: `copyBlock`, `roiToSource`, `windowLine`,
  `storageKey`, formatting; DOM-free, node-testable) and `pick_ui.js` (DOM).
  The data goes into `<script type="application/json" id="vp-data">`.
- **Escaping the embedded JSON.** The HTML tokenizer ends script data at the
  first `</script` whatever the JSON means, and `textContent` acts only later.
  So the serializer itself makes the payload inert:
  - `json.dumps(data, ensure_ascii=True)`;
  - then replace every `<` with the six ASCII characters backslash, `u`, `0`,
    `0`, `3`, `c`, every `>` with backslash-`u003e` and every `&` with
    backslash-`u0026`. All three are valid JSON string escapes, and `<`, `>`
    and `&` can only occur inside JSON strings;
  - `ensure_ascii` also turns U+2028/2029 and non-ASCII into escapes.

  In code this is `.replace("<", "\\u003c")` etc. (a Python literal whose
  output is a backslash followed by `u003c`). `render_page` then asserts that
  the payload contains no `<`, `>` or `&` byte.
- Each placeholder must be replaced exactly once, otherwise `PrepError`. Images
  are `src/…`, relative and URL-encoded per path segment. Data is shown with
  `textContent` only, never `innerHTML`.
- **UI:**
  - **Grid:** a thumbnail grid of all frames, grouped by segment, each labelled
    with time and Δ.
  - **Selection:** click toggles a frame; shift-click selects the range from
    the anchor.
  - **Keyboard:**
    - ←/→ move, ↑/↓ move by a grid row, Home/End;
    - Space toggles, Shift+arrows extend;
    - `s` and `e` mark the start and end frame;
    - `x` clears the marks, Esc clears the rectangle, `c` copies.
  - **Preview:** a large preview of the focused frame, where a drag draws the
    rectangle, in natural pixels. It shows the ROI status (enabled, or the
    disabled reason).
  - **Notes:** a note field per focused frame.
  - **Copy block:** shown live in `<pre id="copy-text">`.
- **Copy:** `navigator.clipboard.writeText`. If that is unavailable or rejects,
  the page selects the block's text (Range) and says to copy it with Ctrl/Cmd+C.
- **State:** `localStorage` under `vp-pick:v1:<fingerprint>`. Every access is in
  try/catch, and the page works without storage.
  - The fingerprint is the SHA-256 over the sorted `rel\tsha256` lines of the
    snapshot plus the page version, cut to 16 hex.
  - A rebuild with new pixels therefore starts clean, and the same pixels
    restore the selection.
- **Self-test hook:** `#selftest=<json>` in the URL makes `pick_ui.js` dispatch
  real `click`/`keydown`/`pointer` events at its own elements. It then sets
  `body[data-selftest=done]`. It reads only the page's own hash, and lets
  headless chromium drive the real handlers (post-phase).

### Opener (`vp_pick.open_page`, one function with a per-platform table)
- `OPENERS`:
  - `darwin` → `open PATH`;
  - `linux` → `xdg-open PATH`;
  - `wsl` → `wslview PATH` if on PATH, else `explorer.exe $(wslpath -w PATH)`.
    explorer.exe's exit status is not meaningful and is ignored.
- WSL is detected like `ait_is_wsl` (`/proc/version` ∋ "microsoft", case-insensitive).
- **No display**, so nothing is launched:
  - `SSH_CONNECTION`/`SSH_CLIENT`/`SSH_TTY` set (an SSH session);
  - Linux non-WSL without `DISPLAY`/`WAYLAND_DISPLAY`;
  - the opener is not on PATH;
  - an unknown platform.
- The opener is spawned detached (`start_new_session`, devnull). A non-zero exit
  within 5 s means not opened.
- `env`, `platform`, `which`, `proc_version` and `spawn` are parameters, so the
  function is unit-testable.
- pick **always exits 0** for opener outcomes.

### Outputs and stdout
- `<out>`: `index.html`, `src/…`, `pick.json` (the embedded data, for agents and
  tests), `summary.md` and `run.json`.
- `summary.md`:
  - inputs, groups and counts;
  - frames with and without a trusted source geometry, with each reason;
  - renames;
  - how to open the page by hand;
  - "the picker certifies nothing: a selection is a viewing range; marked
    endpoints are unverified".
- `run.json`: `mode pick`, options, `source_run`, `frames`, `roi_trusted`,
  `roi_disabled` [{file, reason}], `fingerprint`, `opened`, `open_detail`.
- stdout ends:
  ```
  pick: 42 frames, source --roi available for 40 (2 without a trusted geometry)
  OPEN: opened (xdg-open) | OPEN: not opened: no display (... ) | OPEN: not requested (--open not given)
  PAGE: /abs/out/index.html
  SUMMARY: /abs/out/summary.md
  ```
- pick needs neither ffmpeg nor ImageMagick.

## Implementation steps

### 1. New `.aitask-scripts/screen_recording/vp_pick.py` (builder, stdlib only)
- Constants:
  - `PICK_VERSION = 1`;
  - `WINDOW_LABEL = "user-marked endpoints (unverified)"`;
  - `VIEW_LABEL = "viewing range"`;
  - `SAFE_NAME` regex;
  - `NOTE_MAX = 200`.
- Functions:
  - `resolve_groups(root) -> (groups, run_dir, layout)`, with run layouts before
    root images (Design, Input resolution);
  - `read_frames_tsv(dir) -> (rows_by_name | None, error | None)`;
  - `allocate_names(names) -> dict[name, dest_name]` (pure; reserved kept names,
    case-folded, then `renamed_NNNN<ext>`);
  - `snapshot(groups, src_dir) -> list[Snap]` (exclusive-create copy, then hash
    and size the copy);
  - `geometry(snap, rows, error) -> (geom | None, reason | None)`;
  - `window_bounds(ms) -> (a_str, b_str)` (Decimal, normalized);
  - `roi_to_source(rect, geom) -> (X, Y, W, H)`;
  - `sanitize_note(text)`;
  - `copy_block(data, state) -> str`;
  - `fingerprint(snaps)`;
  - `build_data(...) -> dict`, with per frame: `rel`, `name`, `group`, `order`,
    `ms`, `delta_ms`, `label`, `path` (snapshot abs), `url`, `sha256`, `w`, `h`,
    `geom`, `roi_disabled`, `time_source`, `window_start`, `window_end`; plus
    the page, fingerprint, source run and the labels;
  - `render_page(data, assets_dir) -> str`;
  - `open_page(path, *, env, platform, which, proc_version, spawn) -> (bool, str)`;
  - `cmd_pick(args, *, make_out_dir, PrepError)`. It is called from
    `video_prep`, which passes its helpers so there is no import cycle.

### 2. Page assets (same dir)
- `pick_page.html`: markup and CSS, light and dark via `prefers-color-scheme`,
  with placeholders `/*@LOGIC@*/`, `/*@UI@*/` and `@DATA@`.
- `pick_logic.js`: pure, one function per Python reference function, exported as
  `globalThis.VPPick = {...}` so node `vm` can load it.
- `pick_ui.js`: grid, selection, keyboard, preview and rectangle, notes, copy
  with fallback, storage in try/catch, and the self-test hook.

### 3. `video_prep.py` and the wrapper
- Add a `pick` subparser: `dir` (frames dir or run dir), `--open`, `--out`.
  `set_defaults(func=cmd_pick)`, where a thin `cmd_pick` delegates to
  `vp_pick.cmd_pick`.
- `main()` already checks `dir` is a directory for subparsers with `dir`.
- `_write_run_json` (used by bug, anim and frames) adds `video_abspath` and
  `video_size` (additive keys). The existing run.json tests stay green, and a
  new assertion in the bug/anim/frames tests checks that both keys are present
  and correct.
- Update the module docstring and the usage comment in
  `aitask_screen_recording.sh` (`pick DIR [--open] [--out DIR]`).
- No new `.sh` helper, so no whitelist touchpoints.

### 4. Tests
**`tests/test_screen_recording_core.py`** (no ffmpeg):
- **`PickRules`:**
  - `window_bounds(483)` → `("0.4825","0.4835")`, and `(0)` → `("0","0.0005")`;
  - `roi_to_source`:
    - an identity crop;
    - an odd crop offset;
    - scale 0.5 (outward rounding);
    - clamping at the source edge;
    - the result always passes `region_box` (a property loop over random rects
      and geometries);
  - `copy_block`:
    - an empty selection;
    - no marks → viewing range, no `--window`;
    - both marks → `--window` + `unverified`;
    - end before start, same frame, an untimed mark, a single mark → `no --window: <reason>`;
    - a rect with geom → `--roi`;
    - a rect without geom → the own-pixels line with the reason;
    - a note with newlines and tabs → one line;
    - the Δ between selected frames;
  - `sanitize_note`;
  - `fingerprint` is stable and changes when one byte changes;
  - `geometry()` reasons, one per failure kind.
- **`PickLogicJs`** (skipped without node):
  - a scenario matrix (the cases above, built in Python) goes on stdin to a
    `node -e` runner that loads `pick_logic.js` in `vm`;
  - every `copyBlock` / `roiToSource` / `storageKey` result equals the Python
    reference byte for byte;
  - `node --check pick_ui.js`.
- **`PickOpener`:**
  - linux without DISPLAY/WAYLAND → not opened, no spawn;
  - `DISPLAY` set → the spawn argv is `["xdg-open", path]`;
  - `SSH_CONNECTION` set → not opened on every platform;
  - darwin → `open`;
  - a WSL `/proc/version` → `wslview`, else `explorer.exe` plus `wslpath`;
  - the opener missing → not opened;
  - a non-zero spawn exit → not opened.

**`tests/test_screen_recording_cli.py`:**
- **`PickFolder`** (no ffmpeg; uses the existing `write_png`):
  - **Manifest and snapshot:** a `t<ms>` folder with a matching hand-made
    `frames.tsv`. Check:
    - `pick.json` paths are absolute under `<out>/src`;
    - `ms`, `delta_ms` and the labels match `plan_sheet`;
    - each `sha256` equals hashlib of the snapshot file;
    - `index.html`'s embedded JSON equals `pick.json`;
    - the inlined logic equals `pick_logic.js`.
  - **No geometry record:** no `frames.tsv`, and a `frames.tsv` lacking one
    row → `geom null`, the reason, and the summary lists them.
  - **Same-dimensions edits:** in a copy of a run's frames dir, (a) crop then
    resize back and (b) a translation by (3,2) within the canvas, both written
    at the same size. A premise guard checks the dimensions are equal and the
    bytes differ. Result: `geom null`, and the reason names the SHA-256.
  - **Snapshot isolation:** an in-process build with the copy step patched to
    overwrite the original right after copying. The recorded hash equals the
    snapshot's, and the trust decision is made on the snapshot.
  - **Snapshot name collisions:** one folder holds a kept numeric name
    `renamed_0001.png` (also `RENAMED_0002.png`, for the case-folded check)
    plus three unsafe names (`a b\n.png`, `-x.png`, `t00000100?.png`). Assert:
    - all snapshot paths are distinct;
    - the file count in `src/` equals the input count;
    - each snapshot's bytes hash to the original's recorded hash, and the kept
      `renamed_0001.png` still holds its own bytes;
    - no generated name equals a reserved one, case-folded.

    Mutant: allocate generated names without reserving the kept ones → red
    (the exclusive create raises, or the hashes differ).
  - **Script-breaking data, from realizable inputs.** No basename can contain
    `/`, so `</script>` is put into the data through:
    - (a) the input folder's **absolute path**: a directory named `a<`
      containing `script>b`, so `…/a</script>b/frames/…`. This reaches every
      `path`;
    - (b) a `frames.tsv` row whose `time_source` cell is
      `</script><img src=x onerror=alert(1)>&amp;`;
    - (c) a `run.json` `options.video` naming an existing file under a
      `…/x</script>y/` dir.

    Assert:
    - the payload between the `vp-data` open tag and its close tag has no `<`,
      `>` or `&`;
    - stdlib `html.parser` sees exactly one `vp-data` script element, and its
      raw text `json.loads` equal to `pick.json` (so the tokenizer did not end it
      early);
    - the page has exactly the expected number of `<script` start tags and no
      `<img`;
    - `copy_block` lines stay one per frame.

    Premise control: the same check, run on a page rendered with the escaping
    step removed (test-local monkeypatch), finds the script element cut short.
  - **No display:** `pick DIR --open` with `DISPLAY`, `WAYLAND_DISPLAY` and
    `SSH_*` removed from the env, and a stub `xdg-open` on PATH that records its
    argv → exit 0, `OPEN: not opened: no display`, `PAGE:` then `SUMMARY:`
    last, and the stub was not called.
  - **With a display:** `DISPLAY=:99` and the same stub → `OPEN: opened`, and
    the stub got the page path.
  - **Errors:** a missing dir → 2; a dir with no images → 1, with no out dir
    left behind.
  - **Source video, legacy run.json (no ffmpeg):** two working directories A
    and B each hold a different `clip.mp4` (different sizes). A hand-made
    run.json has `options.video: "clip.mp4"`, `video.path: "clip.mp4"` and no
    `video_abspath`. Running pick with cwd B gives a `# source:` line with
    `<VIDEO>` and "relative to an unknown directory", and B's path never
    appears anywhere in `pick.json` or the block. An absolute legacy path is
    shown only as "recorded path, unverified".
  - **Layout precedence without ffmpeg:** hand-made dirs mimic each producer:
    - a bug-like root (`run.json` mode bug, `sheet_01.png` and `frames/t…png`)
      → the group is `frames/`, never the sheet;
    - the same without `run.json` → still `frames/`;
    - an anim-like root with `w01/frames/` and with `s01`+`s02` → those groups;
    - a sheet output (`run.json` mode sheet) → exit 1 naming the source folder;
    - `run.json` mode bug with no `frames/` → exit 1 naming the expected path;
    - a plain image folder → itself.
- **`PickFromRuns(_VideoCase)`** (ffmpeg):
  - **Real bug run with sheets** (skipped without `magick`, which draws the
    sheets): `bug` on the marker clip. Premise: the run root has a
    `sheet_01.png` and `frames/`. `pick <bug-run>` →
    - every `pick.json` frame comes from `frames/`;
    - no `sheet_*` name appears;
    - the times equal `timeline.tsv`;
    - geometry is trusted for each.
  - **Source video across working directories:**
    - copy two different synth clips to `A/clip.mp4` and `B/clip.mp4`; premise:
      the sizes differ;
    - run `frames clip.mp4 --at 0` with `cwd=A` (relative argument);
    - run `pick <run>` with `cwd=B`;
    - result: the `# source:` line names `A/clip.mp4` absolute, never B's.
    - Then replace `A/clip.mp4` with B's bytes (a size mismatch) and pick again
      → `<VIDEO>` with "changed since extraction".
    - Then delete it → `<VIDEO>` with "missing".
  - **Pick after `anim --window`:** `anim slide_right --window 0.2-0.9`.
    Premise: `w01/frames/` exists and `s01` does not. `pick <anim-run>` →
    - the group is `w01`;
    - the frames equal `w01/frames/frames.tsv`;
    - geometry is trusted.
  - **ROI to source, crop:** `frames --at 0 --roi 37,151,201,243` on
    `synth.marker_frames` → pick on the run dir (resolves `frames/`). For each of
    the 3 markers inside the box:
    - the dark centroid is found in the snapshot image (image px);
    - a rect of ±4 px around it goes through `roi_to_source`;
    - the result contains the drawn marker `(mx, my, 6, 6)` and its centre is
      within 1 px.
  - **ROI to source, scaled:** `bug --view-size 400` on the marker clip (scale
    0.5) → the same check through a scaled geometry.
  - **Mid-motion-only selection:** `anim` on `slide_right`. Select only the
    frames strictly between the first changed and the settled frame (times from
    the anim summary and `curve.tsv`) → a viewing range and no `--window`.
  - **Spring turning point and duplicated pair:**
    - anim on the overshooting spring fixture: select the frames around the
      progress peak, which is a turning point;
    - `frames --range` over a held CFR span: two identical consecutive frames
      (premise: equal pixel bytes);
    - with no marks, the block has a viewing range and no `--window`;
    - neither `pick.json` nor the block contains `settled` or `still`.
  - **Marked window round trip:**
    - mark the start and end frames of the anim `s01/frames` run on
      `slide_right`. Choose the start so its exact time is *below* its name ms
      (e.g. 16.67 ms → `0.017`, a premise check);
    - `--window` appears with the `unverified` label;
    - running `anim VIDEO --window <A-B>` must give a first analysed frame at the
      start's exact time and a last one at the end's, read from `curve.tsv`
      times.
    - Repeat on the VFR slide fixture.
- Every new fixture asserts its own premise.

**Mutation checks during verification** (scratch edits, reverted with checksums;
confirm that each one changes its target output):
- geometry trusted without the hash compare → the same-dims edit tests red;
- the original hashed instead of the snapshot → the snapshot-isolation test red;
- `--window` emitted from the selection without marks → the mid-motion and
  spring tests red;
- window bounds `A = ms/1000` → the round trip red;
- `roi_to_source` ignoring scale, or floor/ceil swapped → the scaled-marker test
  red;
- JS `copyBlock` drifting by one character → `PickLogicJs` red;
- the display check removed → the no-display test red;
- generic root images checked before run layouts → the real bug-run-with-sheets
  test red;
- the anim label regex limited to `s\d\d` → the pick-after-`--window` test red;
- generated names not reserved against kept ones → the collision test red;
- the JSON escaping step removed → the script-breaking-data test red;
- relative `options.video` resolved against pick's cwd when it exists → the
  two-working-directories tests red (legacy and producer);
- the size check skipped → the "changed since extraction" case red;
- `pick_ui.js` shift range made exclusive of the clicked card, or the `s`
  handler disabled → the headless smoke fails at that checkpoint.

### 5. Skill text: `.claude/skills/aitask-screen-recording/SKILL.md`
- "Pick a mode" row: the user wants to choose frames themselves → `pick`.
- Run example: `pick <run-dir> --open --out <scratchpad>/video-prep/rec-pick`.
- New **Pick frames visually** section:
  - **When to ask:** after an extraction that wrote frames (`bug`, `anim`,
    `frames`), unless the user already said which frames matter. Ask once per
    recording.
  - **The question**, AskUserQuestion, with everything inside the widget:
    - question text: "I extracted N frames from <video> (<dir>). Do you want to
      pick the ones that matter yourself? A page opens in your browser: click
      frames (shift-click for a range), optionally mark a start and an end frame
      or drag a rectangle, press Copy, and paste the text back here."
    - options: "Pick them in the browser" / "Let the agent choose".
    - The same two-option question maps to Codex `request_user_input` (≤ 3
      questions, 4 options; a real user decision, so it is asked in default
      mode too) and OpenCode `ask`. t1893_12 validates it end to end.
  - **On yes:** run `pick … --open`.
    - `OPEN: opened` → tell the user to paste the block, and wait.
    - `OPEN: not opened` → name the page path (the user can open it if a browser
      is on that machine) and choose the frames yourself. The skill never fails.
  - **On no:** choose the frames yourself.
  - **Reading the block:**
    - read the listed paths;
    - the viewing range is not a measurement window;
    - a `--window` is **unverified**: run `anim VIDEO --window A-B` (keeping the
      source run's `--roi`/crop flags) and trust it only if anim's diagnostics
      agree. That means the first changed frame comes after the window's first
      frame and the settled frame before its last, with no `still`/`returns`
      kind. Otherwise widen the window or let anim find segments.
    - `--roi` is in source-video pixels only when the block says SHA-256
      verified; an own-pixels rectangle is not a `--roi`.
- Tests list: add pick.
- The `.agents`/`.opencode` wrappers are thin pointers and need no change.

### 6. Website docs
- `website/content/docs/skills/aitask-screen-recording.md`:
  - usage line and Modes row;
  - a `### pick` options table (`DIR`, `--open`, `--out`);
  - the pick output layout (`index.html`, `src/`, `pick.json`, `summary.md`,
    `run.json`) and the copy-block lines;
  - Warnings and limits rows:
    - the source ROI is disabled, with each reason;
    - no display;
    - the `--window` is unverified, with the ±0.5 ms rule and the ~800 fps
      limit;
    - an edited image has no corrected transform;
    - snapshot renames;
  - Requirements: a browser, and neither ffmpeg nor magick;
  - the Workflows list.
- New `website/content/docs/workflows/screen-recordings/pick-frames.md`, "Pick
  Frames Visually and Hand Them to the Agent":
  - the flow and the copy block;
  - viewing range vs user-marked window, and what "unverified" means;
  - when ROI export is disabled and why;
  - the no-display fallback;
  - the keyboard table.
- List it in the section `_index.md` ("Choose a mode" row and Walkthroughs) and
  in `workflows/_index.md`, with relref. Write current state only, in
  agent-generic wording.
- Run `cd website && python3 check_links.py --build && hugo build --gc --minify`.

### Post-phase (risk mitigations)
1. [headless_ui_smoke] In `PickFolder`, add `test_page_drives_in_headless_chromium`.
   It is skipped when no `chromium`/`chromium-browser`/`google-chrome` is found,
   or when the browser exits non-zero with empty output (the reason is printed).
   - Build a 6-frame folder with a matching `frames.tsv`, and run
     `chromium --headless=new --disable-gpu --no-sandbox --user-data-dir=<tmp>
     --allow-file-access-from-files --virtual-time-budget=5000 --dump-dom
     "file://<out>/index.html#selftest=<json>"`.
   - The self-test scenario:
     - click card 1, then shift-click card 3;
     - press → then Space (toggles card 4);
     - press `s` on card 1 and `e` on card 3;
     - drag a rectangle on the preview;
     - type a note.
   - **The oracle is specified independently, never read back from the UI.**
     The test writes down the expected outcome of the event script up front
     (frame names are fixed by the fixture):
     - selected = cards 1, 2, 3 (the shift-click range, inclusive) plus 4
       (Space after →);
     - marks = start card 1, end card 3;
     - the note on card 2 is `"edge starts"`;
     - the rectangle on card 1 is image px `[10,20)×[30,50)`, from a drag
       between preview points computed by the test from the preview's known
       CSS size and the image size.

     From that, the test computes the **expected block** with
     `vp_pick.copy_block(data, expected_state)`.
   - **Per-action checkpoints:** after each action the hook appends the
     `#copy-text` content to a `data-trace` list. The test asserts each
     checkpoint against the expected block for the state at that point, so a
     wrong shift range, an ignored key, a missing mark or a dropped note each
     fail at their own step:
     - after the shift-click: exactly cards 1–3 listed;
     - after Space: card 4 added;
     - after `s` and `e`: the `--window` line with the bounds from card 1's
       and card 3's `window_start`/`window_end`;
     - after the drag: `--roi` equal to `roi_to_source([10,20,30,50], geom)`;
     - after typing: `note: edge starts` on card 2's line.
   - Final assertions:
     - the dumped DOM has `data-selftest="done"`;
     - 6 cards are rendered;
     - the final `#copy-text` equals the expected block byte for byte.

     The UI's own `data-state` is only a diagnostic in the failure message,
     never the oracle.
   - A second run on a fresh profile with a `localStorage`-throwing shim
     (`#selftest` flag `nostorage`) still renders and reaches done.
   - Premise: when run without `#selftest`, the page renders its cards with an
     empty block.

### 7. Step 9 (Post-Implementation)
- Commit the code, tests and docs as `feature: Add the pick visual frame picker
  (t1893_5)`, and the plan via `./ait git`.
- Step 8c: offer the manual-verification follow-up for the real-browser UI
  (selection, keyboard, clipboard, rectangle), as the task asks.
- Final notes for siblings:
  - t1893_6 / t1893_12: the copy-block format and the window ±0.5 ms rule;
  - t1893_11: pick's out dir under the work dir;
  - observed: anim has no explicit "window cuts the motion" warning.

## Verification
- `python3 tests/test_screen_recording_core.py`
- `python3 tests/test_screen_recording_cli.py`
- `bash tests/run_all_python_tests.sh --test-dir tests`; read only the last
  verdict line.
- The mutation checks above, each red, then restored.
- `pick --help` checked against every documented flag.
- `shellcheck .aitask-scripts/aitask_screen_recording.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- The website link check and hugo build.
- Manual: a real `anim` run, `pick --open` in the browser, select, mark, drag,
  copy, paste. The Step 8c follow-up covers it formally.

## Risk

### Code-health risk: low
- The copy-block and ROI logic exist twice, as the Python reference and in
  `pick_logic.js`, so they can drift. The node parity test catches drift, but it
  skips on hosts without node · severity: low · → mitigation: none
- `video_prep.py` changes only by a subparser and a delegating `cmd_pick`. The
  new code lives in its own module and assets, so the blast radius is small ·
  severity: low · → mitigation: none
- `_write_run_json` gains two keys for bug, anim and frames. The change is
  additive, existing consumers ignore unknown keys, and the new assertions pin
  the keys. The skill page's run.json prose documents them · severity: low ·
  → mitigation: none

### Goal-achievement risk: low
- The interactive UI (selection, keyboard, rectangle drag, clipboard fallback,
  storage) runs only in a browser. Unit tests prove the rules and the JS logic,
  not that the DOM handlers wire them correctly. A broken handler would ship
  green · severity: low (residual: the inline post-phase headless_ui_smoke
  covers it; real pointer ergonomics are left to the Step 8c manual
  verification) · → mitigation: inline post-phase headless_ui_smoke
- `navigator.clipboard` on `file://` differs between browsers. The fallback
  (selected text plus an instruction) keeps the flow working, but only a real
  browser shows it · severity: low · → mitigation: none (the Step 8c manual
  verification)
- The window bounds rely on names being within ±0.5 ms of the exact time, and
  assume < ~800 fps. This is documented, and the round-trip tests pin it on CFR
  and VFR · severity: low · → mitigation: none

### Planned mitigations
- timing: post-phase | name: headless_ui_smoke | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: interactive UI wiring unproven by unit tests | desc: Headless-chromium self-test that dispatches real DOM events and compares the rendered copy block with the Python reference, plus a storage-throwing run

## Post-Review Changes

### Change Request 1 (2026-11-06)
- **Requested by user:** two review findings, both confirmed in chromium/by direct check before fixing.
  1. `pick_ui.js` keydown handling used the internal `focus` index, never synchronized when browser focus moved without a click (Tab, a script), and intercepted Space on the action buttons: Space with DOM focus on card 2 toggled card 1; Space on the focused Copy button changed the selection and suppressed the button's native activation.
  2. `PickFolder.chromium_dom` turned `subprocess.TimeoutExpired` (and an empty result) into `skipTest`, so a picker regression that hangs chromium left the suite green.
- **Changes made:**
  1. Each card's `focus` event makes it the active frame (preview and highlight follow); keydown on a card acts on that card; Space/Enter on any other focused control (buttons, links) is left to the browser, while arrows and the letter shortcuts keep working there. Self-test gained `focusCard`, `focusButton` and `clickButton` steps and records per step whether the key was cancelled, the status text and the active element.
  2. `chromium_unusable()` (cached) proves the browser renders a trivial page; only that decides a skip. On the picker page a timeout or an empty DOM is now `self.fail`.
- **Files affected:** `.aitask-scripts/screen_recording/pick_ui.js`, `tests/test_screen_recording_cli.py`
- **Verification:** new headless scenario — click card 1, focus card 3 without a click, Space toggles card 3, ArrowRight + `s` marks card 4, Space on the focused Copy button is not cancelled and changes nothing, Copy's click sets a status. Pre-fix controls: focus sync removed → red; Space on buttons intercepted again → red; a simulated chromium hang on the picker page → failure (not skip). Earlier UI mutants (shift range exclusive, `s` disabled) still red. PickFolder + core OK.

## Final Implementation Notes
- **Actual work done:**
  - `aitask_screen_recording.sh pick <run-dir|frames-dir|folder> [--open] [--out DIR]` (`cmd_pick` in `video_prep.py` delegates to the new `vp_pick.py`; `PickError` → `PrepError`, exit 1). Writes `index.html` (self-contained), `src/` (snapshot), `pick.json` (the embedded data), `summary.md`, `run.json`; stdout `pick: …`, `OPEN: …`, `PAGE: …`, `SUMMARY: …`.
  - Page assets are sibling files inlined at build time: `pick_page.html` (markup/CSS, placeholders `@DATA@`, `/*@LOGIC@*/`, `/*@UI@*/`, replaced in one regex pass), `pick_logic.js` (pure: `copyBlock`, `roiToSource`, `normRect`, `sanitizeNote`, `seconds`, `storageKey`), `pick_ui.js` (DOM + `#selftest=` hook).
  - Every copy-block sentence lives in `vp_pick.TEXT` and is embedded as `data.text`; JS only concatenates. Per frame, Python precomputes `display_name`, `label`, `window_start`/`window_end`, `geom` or `roi_disabled`.
  - Resolution: run layouts first (run.json mode bug/frames → `frames/`; anim → `[sw]\d{2,}/frames`; sheet/pick refused), then the same shapes without run.json, then a plain image folder (its run found at `..` / `../..`).
  - Snapshot: `allocate_names` (kept safe names reserved case-folded, others `renamed_NNNN<ext>`), exclusive create (`open(dest, "xb")`), hash and PNG size from the copy.
  - Geometry trusted only when a `frames.tsv` row parses, its sha256 equals the snapshot's and `(out_w,out_h)` equals the PNG size. ROI mapping exact integer, rounded outward, clamped, always valid for `region_box`.
  - `--window` only from explicit marks; bounds `(ms∓0.5)/1000` written exactly (≤4 decimals).
  - Embedded JSON: `json.dumps(ensure_ascii=True)` then `<`, `>`, `&` → their JSON `\uXXXX` escapes (built with `chr(92)`), with a final assertion.
  - Opener table (`darwin` open, `linux` xdg-open, `wsl` wslview / explorer.exe+wslpath); SSH or Linux without DISPLAY/WAYLAND_DISPLAY → not opened, exit 0.
  - `_write_run_json` (bug/anim/frames) adds `video_abspath` + `video_size`; pick names the recording only from those (size-checked), never re-resolving a relative `options.video`.
  - Docs: skill page (usage, Modes row, `### pick`, `### No display`, pick output layout, run.json provenance paragraph, 10 warning rows, 2 limits, Requirements, Workflows); new walkthrough `workflows/screen-recordings/pick-frames.md` listed in both indexes; SKILL.md mode row, run example, "Pick frames visually" section (AskUserQuestion spec, Codex/OpenCode mapping, reading the block, how to judge a marked window from anim's diagnostics), Tests list.
- **Deviations from plan:**
  - The floor/ceil-swap mutant stays green on the scaled-marker CLI test (a ±4 px rectangle still contains the 6 px marker when rounded inward); it is caught by the core coverage property `test_roi_always_passes_region_box`.
  - The duplicated-frame fixture needed a lossless encode (`crf=0`): consecutive frames of a lossy static encode differ by compression noise.
  - SKILL.md's endpoint check was reworded after measuring anim: the first changed frame is always index ≥1, so the useful signs are "first changed = the window's second frame" (motion already under way) and "settled = its last frame" (motion may continue). Verified on a cut window (0.6–0.7 s) vs a good one (0.4–1.0 s).
  - `pick` opener outcomes print `OPEN: not requested (--open not given)` when `--open` is absent.
- **Issues encountered:**
  - Write/Edit tool parameters decode `\uXXXX` sequences (a `✓` and the planned `<` arrived as literal characters); Bash heredocs keep them. The escapes are built with `chr(92)` and asset files were checked ASCII-only.
  - Review round 1: focus not synchronized with DOM focus and Space intercepted on buttons; chromium timeouts turned into skips. Fixed (see Post-Review Changes) with pre-fix controls.
- **Key decisions:**
  - Python is the reference for the copy block; JS parity is enforced by a node test (skipped without node) and by the headless-chromium test against independently written expectations.
  - Retention/cleanup of pick output dirs is left to t1893_11 (make_out_dir never reuses a non-empty dir).
  - `pick` needs neither ffmpeg nor ImageMagick.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **t1893_6 (folder input) / t1893_12 (other agents):** copy-block format above (tab-separated frame lines; `# --window A-B  (user-marked endpoints (unverified): …)`; `# --roi …  (… SHA-256 verified)`; `# rectangle … own pixels …`; `# source: …`). The window rule assumes names within ±0.5 ms of the exact time and frame intervals > ~1.2 ms. t1893_12 should validate the "Pick frames" question on Codex `request_user_input` and OpenCode `ask`, and that agents read the pasted absolute paths.
  - **t1893_11 (work dir + clean):** pick's default out is `make_out_dir(..., "pick", name=<run or folder name>)`; it owns everything under `<out>` (index.html, src/, pick.json).
  - **run.json provenance:** `video_abspath`/`video_size` are now in every bug/anim/frames run.json; any consumer that needs the recording should use them, never re-resolve `options.video`.
  - **anim:** no explicit warning when a `--window` cuts the motion; the signs are the visible-change line as above (a possible enhancement, not filed).
  - **Test fixtures:** `write_frames_dir` (hand-made frames dir + matching frames.tsv), `parse_page` (HTML tokenizer view of scripts, body attrs, cards, `#copy-text`), `chromium_unusable()` probe + `chromium_argv`, the `#selftest` step vocabulary (`click`/`shift`, `key`, `note`, `drag`, `focusCard`, `focusButton`, `clickButton`, `nostorage`), `pick_scenarios()` for Python/JS parity.
