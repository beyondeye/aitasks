---
Task: t2278_7_real_pixel_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-22 17:51
---

# Plan: t2278_7: real pixels (optional)

## Context

Child 7 of t2278 (docs TUI screenshot generator). Every scene already has a
vector capture (pane cells → Rich SVG → `svgpost` crop/overlays). This child
adds a **real-pixel** capture: a real terminal attached to the same isolated
tmux session on a headless Hyprland output, photographed with `grim`. It only
works inside a live Hyprland session, so it is never the only path to a scene.

The task may end after step 1 with a recorded negative result.

**User decision (2026-11-22): pixel images are publishable.** A recipe with
`pixels: true` stages a `<stem>.webp` beside its `<stem>.svg` in the same batch
scene. preview/apply and output ownership cover both files, and a page marker
may name either file. Without the capability only the SVG is staged (with a
printed notice), and the `.webp` already on the site stays as it is.

## Verification of the existing plan (2026-11-22)

Checked against the current tree and machine. The original plan's shape holds.
These facts change its details:

- **Hyprland 0.57.2 uses Lua config** (`~/.config/hypr/*.lua`, `hyprctl eval`).
  Window and monitor rules for the probe must use `hyprctl eval 'hl.…'` or
  exec-rule syntax. The probe works out which; old `windowrulev2` keywords
  may not exist.
- A **catch-all monitor rule** (`hl.monitor({output = "", …, scale = 2})` in
  `monitors.lua`) applies to any new output, so a headless output comes up at
  scale 2 and `position = auto`. The probe pins its own rule (scale 1, a
  position away from the real monitors) or measures and honours the scale.
- **Per-monitor layers** `omarchy-background`, `omarchy-bar`, `omarchy-dock`
  and `omarchy-notifications` are on both real outputs, and probably attach to
  a headless one too. Capture by **window geometry** (`grim -g`), never the
  whole output (`grim -o`), and check that no layer overlaps the window.
- **Resize hazard** (note from t2278_4): an attached client resizes the window
  under `window-size latest`. tmux 3.8 supports
  `attach -f ignore-size,read-only`, which means the photo client never
  resizes the session and never sends keys. The probe confirms the window
  size is unchanged (`#{window_width}x#{window_height}` before and after).
- **Terminal:** `foot` 1.28 is available. It is Wayland-native, and gives
  `-c <config>` (the user's config is never read), `--app-id`,
  `--window-size-chars=COLSxROWS`, and `line-height` / `pad` settings.
  (`alacritty` and `ghostty` are present too. foot is chosen for the exact
  cell-sized window.)
- **The pipeline is SVG-only today:** `stage()`, `_image_state()`,
  `_apply_scene()`, `check_ownership()` and the `check_screenshots.py`
  ownership checks all assume one `output` per scene, and `_page_edits`
  requires `marker.file == scene.output`. Publishing a companion means
  extending these (step 5).
- **svgpost overlays** (callouts, labels, gutters, extents) are Rich-SVG
  geometry. Reimplementing them in ImageMagick would duplicate a lot of
  geometry. Instead, the photo **replaces the terminal content inside the
  frame's own Rich SVG**, so `svgpost.postprocess` runs unchanged, and the
  composite is then rasterized (step 4).
- The plan's wait rule "compare with `screen`" cannot be done against pixels
  (no OCR). The replacement is a witnessed settled state: the client is
  attached at the expected size, two consecutive `grim` frames are identical,
  and the tmux pane signature is the same before and after the photo.
- `website/screenshots/assets/` does not exist. The terminal config is
  **generated** from `rich.terminal_theme.SVG_EXPORT_THEME`, the same palette
  the SVG uses, so the two cannot drift. The font, padding and cursor settings
  live as constants in `pixels.py`. No asset directory.

## Steps

### Pre-phase (risk mitigations)

1. [sweep_decoupled_from_stop] Leave `website/screenshots/session.py`
   unchanged: no import of or call into `pixels` from `sessions.stop` or
   anywhere else in the session core. The leak backstop lives only in
   `pixels.py`:
   - `Photographer.__exit__` removes its own output;
   - `Photographer.__enter__` calls `sweep()` before it creates a new output.

   Check: `git diff --stat website/screenshots/session.py` is empty at the
   end of implementation.

### 1. Live probe (scratchpad script, nothing committed)

The probe needs `HYPRLAND_INSTANCE_SIGNATURE` (set on this machine). The
script lives in the session scratchpad.

1. Register cleanup first: a `try/finally` that runs
   `hyprctl output remove AITSHOTS-probe` and kills the terminal pid. Then run
   `hyprctl output create headless AITSHOTS-probe`.
2. Snapshot `hyprctl activewindow -j`, `activeworkspace -j` and
   `monitors -j` **before** and **after**. The user's focus, workspace and
   real monitors must be unchanged, because the user works on this desktop
   at the same time.
3. Start a session: `website/screenshots.sh session start --size 126x44`
   and launch the board in it (as recipe `board_child_tasks` does).
4. Spawn foot **directly** (`subprocess.Popen`, so the pid is known) with a
   generated config, `--app-id ait-shots-probe` and
   `--window-size-chars=126x44`, running
   `env -u TMUX tmux -u -L <socket> attach -f ignore-size,read-only -t =<session>`.
   Use a rule, through `hyprctl eval` or exec rules, to place it on the
   headless output: floating, no initial focus.
5. Record:
   - bar/dock/background on the headless output (`hyprctl layers -j`), and
     whether any of them overlaps the window;
   - which window rules apply (`hyprctl clients -j`: floating, monitor,
     size, opacity/rounding);
   - the cell size in px, and whether the window is exactly
     `cols*cw + 2*pad` by `rows*ch + 2*pad`;
   - the output scale;
   - whether the tmux window size changed after attach;
   - one `grim -g` frame, looked at with Read.
6. Confirm cleanup: no `AITSHOTS-*` monitor in `hyprctl monitors all -j`, and
   no `ait-shots-*` client.

**Stop rule:** if the output cannot be made clean (focus stolen, a layer
over the window, opacity or blur that cannot be pinned off, a leaked output,
or a cell grid that is not exact), write the result into Final
Implementation Notes and close the task without building steps 2-6.

### 2. `website/screenshots/pixels.py` (new)

- Constants: `OUTPUT_PREFIX = "AITSHOTS-"`, `APP_ID_PREFIX = "ait-shots-"`,
  `FONT` (a family probed in step 1, e.g. `CaskaydiaMono Nerd Font Mono`),
  `FONT_SIZE`, `PAD`, and `LINE_HEIGHT` chosen so that `ch == 2 * cw` exactly.
  Rich's grid is 12.2 × 24.4, so a 1:2 cell embeds without distortion.
- `available() -> tuple[bool, str]`: `HYPRLAND_INSTANCE_SIGNATURE` and
  `WAYLAND_DISPLAY` set; `shutil.which` finds `hyprctl`, `grim`, `magick`,
  `foot` and `rsvg-convert`; `fc-match` resolves `FONT` to that family;
  `hyprctl version -j` succeeds. It never creates an output or a window.
- `foot_config(theme) -> str`: font, pad, line-height, `cursor.blink=no`,
  bell off, and colors (`background`, `foreground`, `regular0-7`,
  `bright0-7`) from `SVG_EXPORT_THEME`.
- `Grid` (pure): `cell_px`, `origin_px`, `rect_px(cells) -> (x, y, w, h)`,
  and `from_window(win_w, win_h, cols, rows, pad, scale)`. The last one
  refuses when the content is not an exact whole multiple of cols × rows.
- `Photographer` context manager (`with Photographer(sess) as p:`):
  - `__enter__`: sweep stale outputs, create the output (cleanup registered
    first), write the config into `sess.tmp`, apply the placement rule, Popen
    foot, then wait (bounded, `sessions.POLL_INTERVAL`) until three things
    hold: the client is in `list-clients` at the expected size, the window is
    in `hyprctl clients -j` on our output, and the window size is unchanged.
  - `shoot(signature_fn) -> bytes`: `grim -g <window geometry> -` twice until
    two consecutive frames match. The tmux signature must be equal before and
    after, or it retries within `cli.EXPECT_TIMEOUT`. Returns the PNG of the
    content area, cropped with magick to `cols*cw × rows*ch` at the origin.
  - `__exit__`: kill foot, remove the rule, then `hyprctl output remove`.
    Every step is best-effort and errors are collected; it never raises over
    an in-flight exception.
- `sweep()`: removes `AITSHOTS-<id>` outputs whose session id is not alive
  (`sessions.load`/`is_alive`). It is called only from
  `Photographer.__enter__` (see pre-phase `sweep_decoupled_from_stop`), and is
  the leak backstop for a killed run.
- `composite(svg, png, grid) -> str` (pure): in the frame's Rich SVG, replace
  the content group's text/background children with
  `<image href="data:image/png;base64,…" x="0" y="1.5" width="cols*12.2" height="rows*24.4"/>`.
  It keeps the group, its clip path and the chrome, so
  `svgpost.postprocess(svg, crop, overlays)` applies unchanged. It raises
  `svgpost.SvgPostError` on an unexpected structure. Content-group detection
  reuses `svgpost._content_group`.
- `rasterize(svg, out_webp, zoom)`: `rsvg-convert --zoom <cw/12.2>` → PNG, then
  `magick … -define webp:lossless=true` → WebP. Only overlay labels and the
  title are text here, so rsvg's text caveats do not touch the terminal pixels.

### 3. `export()` / `shot --pixels` (`website/screenshots/cli.py`)

- `export(..., photographer=None)` returns `(svg, webp_bytes | None)`. With a
  photographer, the photo is taken on the **same settled frame**: after
  `stable_capture` and the expect/misplaced checks pass, `p.shoot()` runs
  with the `_grab` signature as its witness. Then the uncomposited SVG and
  `composite → postprocess → rasterize` produce both images. All existing
  callers keep their behaviour.
- `shot --pixels`: if `pixels.available()` is false, print
  `PIXELS_UNAVAILABLE:<reason> (the vector image is staged)` and stage the SVG
  only. Otherwise wrap the capture in `Photographer`. The journal entry gets
  `pixels: true`, so `recipe save` records it.
- A `--capture` of one pane in a multi-pane window is supported: the photo
  shows the whole window, and the pane's cell rectangle (from
  `window_layout`) crops it before compositing. If the probe shows this is
  awkward, refuse `--pixels` with `--capture pane` for now and say so.

### 4. Recipe field (`website/screenshots/recipe.py`)

- Add `pixels` to `OPTIONAL`, validated as a bool, with `pixels: true` only
  when `output` ends in `.svg`. Add a `Recipe.pixels: bool = False` field and
  a `pixels_output` property (`<stem>.webp`).
- `dump` and `from_session` carry the field (taken from the last shot's
  journal entry).
- `replay_one`: when `rec.pixels` is set and the capability is available, use
  a `Photographer`. Otherwise print
  `PIXELS_UNAVAILABLE:<scene>|<reason> (the vector image is staged)` and
  continue with the SVG. This is not a failure.

### 5. Publishing the companion (cli.py, markers.py, check_screenshots.py)

- `stage(..., pixels: bytes | None = None)`: write `<stem>.webp` into the
  batch, and give the manifest scene entry
  `"pixels": {"output", "sha256", "destination"}`. The refusal rules (never
  rewrite a batch) cover both files.
- `check_ownership` and `markers.read_spec_owner` also read a top-level
  `pixels: true` line. `SpecOwner` gains `outputs` (output plus companion).
  The companion must not equal another scene's output or companion.
- `check_screenshots.py`: a marker's `file` may be any owned output of its
  scene. Duplicate checks and "hand-made" attribution use all owned outputs.
- `_image_state` is generalised to a list of `(staged, destination)` pairs
  (main, plus companion when present). `_apply_scene` writes both images and
  the page edits as one unit, with rollback as today.
- `_page_edits`: a marker whose `file` is the companion is accepted only when
  the manifest scene carries `pixels`. Otherwise it fails with
  `SceneRefused("pixels_not_staged:<page>")`, so a page never points at an
  image the batch did not bring.
- `preview`: show the pixel image beside the SVG ("Pixels"), with the same
  existing/new pairing.
- A manifest or recipe without `pixels` behaves byte-identically to today.

### 6. Docs

- `aidocs/framework/docs_screenshots.md`: a "Real pixels" section covering the
  capability, the companion contract, the fallback notice, the leak sweep, and
  the probe findings.
- The `aitask-docs-screenshots` skill: one paragraph on when to set
  `pixels: true` (glyph fidelity that the vector look gets wrong) and the
  fallback. It is a Claude-only static skill, so no other agent trees need
  porting (confirm that during implementation).

### 7. Tests (`tests/test_screenshots_pixels.py`, new; no display needed)

- `Grid.from_window`: exact mapping, scale 2, pad, and refusal for a
  non-whole multiple. `rect_px` agrees with `svgpost.cell_rect_to_px` × zoom.
- `foot_config`: the colors equal `SVG_EXPORT_THEME`; no `include=` line.
- `available()` with `HYPRLAND_INSTANCE_SIGNATURE` unset, and with a missing
  binary (PATH stub dir): `(False, reason)`. A stub `hyprctl` that records its
  argv proves no `output create` is ever called.
- `composite`: on a real Rich export, the content group holds exactly one
  `<image>` and the chrome is kept. `svgpost.postprocess` with a crop and
  every overlay type succeeds on the composite.
- `recipe.py`: `pixels` validation (non-bool, `pixels` with a `.webp`
  output), and the dump/load round trip.
- Extend `tests/test_screenshots_apply.py`: a manifest with a companion
  applies both images. A companion marker without staged pixels gives
  `pixels_not_staged`. A destination change of the companion is refused.
- Extend `tests/test_check_screenshots.py`: a marker naming the companion
  passes; a companion colliding with another scene's output is reported.
- Sweep: with a stub `hyprctl` listing `AITSHOTS-dead` and `AITSHOTS-<live>`,
  only the dead one is removed.

### Post-phase (risk mitigations)

1. [legacy_scene_parity] Prove that SVG-only scenes are unaffected.
   - **Before editing** `cli.py`, `markers.py` or `check_screenshots.py`, save
     `python3 website/check_screenshots.py --report` output into the
     scratchpad (`parity_before.txt`).
   - After steps 2-7, rerun it into `parity_after.txt`;
     `diff parity_before.txt parity_after.txt` must be empty.
   - Add a test to `tests/test_screenshots_apply.py`: a manifest scene
     without a `pixels` key applies with exactly the same set of written
     paths and bytes as the pre-change code. Pin it as the expected list in
     the test, built from a fixture batch created by the test itself.

## Verification

- The probe result is recorded in Final Implementation Notes (positive or
  negative).
- If built:
  - one scene (`board_child_tasks`) is captured with `shot --pixels`. Its
    WebP matches the SVG in layout (same crop and overlay positions, viewed
    side by side in `preview`);
  - after the run, `hyprctl monitors all -j` shows no `AITSHOTS-*` output and
    `hyprctl clients -j` shows no `ait-shots-*` window;
  - a run with `HYPRLAND_INSTANCE_SIGNATURE` unset prints
    `PIXELS_UNAVAILABLE:` and stages only the SVG;
  - `python3 tests/test_screenshots_pixels.py`,
    `tests/test_screenshots_apply.py`, `tests/test_screenshots_recipe.py` and
    `tests/test_check_screenshots.py` pass;
  - `python3 website/check_screenshots.py --strict` exits 0;
  - `bash tests/run_all_python_tests.sh --test-dir tests` gives a PASSED
    verdict on its last line.

Post-implementation: Step 9 of the task workflow.

## Risk

### Code-health risk: medium
- Generalising the publish contract (`stage`, `_image_state`, `_apply_scene`, `_page_edits`, `check_ownership`, `read_spec_owner`, `check_screenshots.py`) for a companion file could change behaviour for the 32 existing SVG-only scenes · severity: low (residual — addressed by inline post-phase legacy_scene_parity) · → mitigation: inline post-phase legacy_scene_parity
- Live-desktop side effects: a leaked headless output, a stolen focus, or the omarchy monitor panel persisting settings for the headless output on the user's active desktop · severity: medium · → mitigation: TBD (bounded by the step 1 before/after snapshots, cleanup registered before create, and `sweep()`)
- `sessions.stop` gains a lazy call into `pixels.sweep()`, a new coupling from the session core to an optional backend · severity: low (residual — addressed by inline pre-phase sweep_decoupled_from_stop: the coupling is not introduced) · → mitigation: inline pre-phase sweep_decoupled_from_stop

### Goal-achievement risk: medium
- Feasibility of a clean headless capture under Hyprland 0.57 Lua config (rules syntax, scale-2 catch-all, per-monitor layers) is unproven until the probe runs · severity: medium · → mitigation: TBD (step 1 stop rule — a negative result is an accepted outcome)
- The pixel image may not line up with the vector layout if the cell aspect cannot be pinned to exactly 1:2 or the rasterizer zoom rounds; crop/overlay positions would drift · severity: medium · → mitigation: TBD (`Grid.from_window` refuses non-exact grids; layout comparison in Verification)

### Planned mitigations
- timing: post-phase | name: legacy_scene_parity | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: publish-contract generalisation changing SVG-only scenes | desc: check_screenshots --report before/after diff + pinned no-pixels apply test
- timing: pre-phase | name: sweep_decoupled_from_stop | type: refactor | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: sessions.stop → pixels.sweep coupling | desc: keep session.py untouched; sweep only from Photographer.__enter__
