# How `anim` measures motion

Read this before trusting an unusual result, or when explaining one to the user.

## Contents
1. Segments and windows
2. The start picture, the end picture and the per-pixel threshold
3. The two progress signals
4. Visible duration vs fitted duration
5. Fitting models
6. Time scale
7. Known limits and what to do about them

## 1. Segments and windows

`mpdecimate` (ffmpeg) keeps a frame only when it differs visibly from the last
kept frame. Kept frames closer than `--gap` (0.12 s) apart belong to the same
motion segment, and a segment with fewer than `--min-frames` (2) kept frames is
a *cut*: an instant change, a clock tick or a cursor blink.

mpdecimate is only used to *find* segments. Its default thresholds
(hi=64·12, lo=64·5, frac=0.33) drop the tiny per-frame changes at the slow end
of an ease-out. That is why each segment is re-decoded with **every native
frame** plus `--pad` (0.25 s) on both sides, and measured with its own
thresholds.

On variable-frame-rate recordings (Android `screenrecord` emits no frames while
the screen is still), the still picture before the motion can lie long before
the window. The tool fetches that exact frame by its timestamp and prepends it.

## 2. Start picture, end picture, threshold

- **S** is the first frame of the window (still, before the motion).
- **E** is the last frame (settled).
- Every frame is compared with both at the analysis resolution
  (`--analysis-pixels`, 160 k by default, area-downscaled).
- A pixel counts as changed when it differs by more than **30 % of the strongest
  S-vs-E difference**, clamped to 8–40 grey levels. This sits above H.264 noise
  and below the contrast of most UI elements.

## 3. Progress signals

**blend** = `1 − mad(frame, E) / mad(S, E)`, where *mad* is the mean absolute
difference.

- **Exact** for a cross-fade or opacity change, where the image is a linear mix
  of S and E.
- **Not linear** for movement: the difference saturates once the old and new
  positions stop overlapping. For a slide it is only a proxy.
- Can't exceed 1, so it hides overshoot.

**edge** is read off two bounding boxes per frame: `bS` (where the frame differs
from S) and `bE` (where it differs from E). For one rigid element moving right
by d (of a total D) over a still background:

```
element at start  [s, s+w)      bS = [s,   s+w+d)   (start ∪ current)
element now       [s+d, s+d+w)  bE = [s+d, s+D+w)   (current ∪ end)
```

- The left edge of `bS` stays put and its right edge **leads**.
- `(lo_E − lo_S) + (hi_E − hi_S) = d + (D − d) = D` for every frame, so the
  travel D is the median of that sum.
- **Progress** = `1 + (hi_S(frame) − hi_S(E)) / D`. This depends only on the
  leading edge, so it stays correct past the target (overshoot reads above 1) and
  for an element that leaves the frame.
- Mirrored formulas cover leftward and vertical motion.

The kinds the summary prints:

| kind | edges that move | example | accuracy |
|---|---|---|---|
| `edge+` / `edge-` | one edge of `bS` | slide; bottom sheet entering; progress bar growing from one side | exact, including overshoot |
| `grow` | both edges of `bS` | centred scale-up | anchored on the first moving frame (the start size is not observable), so slightly off near the start |
| `shrink` | both edges of `bE` | centred scale-down | anchored on the last moving frame |
| `fade/blend` | none | opacity, cross-fade, colour change | exact for fades |

**Travel spread** is the 80th-percentile deviation of the per-frame travel
estimate from D, relative to D.

- About 0 means one rigid element.
- Over 0.1 earns a warning: more than one thing moves, or a fade is combined with
  the move.
- Over 0.25 makes `--signal auto` fall back to blend.
- The worst 20 % of frames are ignored because a frame within a pixel of E
  differs from it only by an anti-aliased sliver, which makes that frame's own
  estimate meaningless. Its progress still comes from the leading edge.

`curve.tsv` holds both signals for every frame. Force one with `--signal edge` or
`--signal blend`.

## 4. Visible vs fitted duration

- **Visible duration** = time of the first frame equal to E, minus (time of the
  first frame that differs from S, minus one frame interval).
  - Exact (± one frame) for animations aligned to vsync whose ends move at least
    a pixel per frame.
  - **Reads short** for slow-in/slow-out curves: their first or last frames move
    less than a pixel or change less than 2 %. CSS ease-in-out and M3 standard
    decelerate lose 1–2 frames, sometimes more.
- **Fitted duration** comes from the model. It accounts for those tails, and it
  is the number to implement.

## 5. Fitting models

The fit uses all frames from 6 before the first change to 7 after the last, so
the start time is anchored. RMSE is in progress units.

**Named tweens.** Each is searched over start time and duration, then refined.

| name in output | cubic-bezier | where it comes from |
|---|---|---|
| linear | 0, 0, 1, 1 | |
| CSS ease / CA default | 0.25, 0.1, 0.25, 1 | CSS `ease`, Core Animation default |
| CSS ease-in | 0.42, 0, 1, 1 | |
| CSS ease-out | 0, 0, 0.58, 1 | |
| CSS ease-in-out / iOS easeInOut | 0.42, 0, 0.58, 1 | |
| FastOutSlowIn | 0.4, 0, 0.2, 1 | Compose `FastOutSlowInEasing` (the `tween()` default), M2 standard |
| LinearOutSlowIn | 0, 0, 0.2, 1 | Compose, M2 decelerate |
| FastOutLinearIn | 0.4, 0, 1, 1 | Compose, M2 accelerate |
| M3 standard | 0.2, 0, 0, 1 | `MotionTokens.EasingStandardCubicBezier` |
| M3 standard decelerate | 0, 0, 0, 1 | |
| M3 standard accelerate | 0.3, 0, 1, 1 | |
| M3 emphasized decelerate | 0.05, 0.7, 0.1, 1 | |
| M3 emphasized accelerate | 0.3, 0, 0.8, 0.15 | |

M3 *emphasized* (not decelerate/accelerate) is a path, not a cubic-bezier, so it
can't be fitted here. Expect it to land between M3 standard and the custom fit.

**Custom cubic-bezier.** A coordinate search over all four control points plus
start time and duration, seeded from the best named curve. It can overfit noise,
so prefer a named curve unless the custom one is clearly better (SKILL.md gives
the rule).

**Spring.** Unit mass from 0 to 1 with no initial velocity, the semantics of
Compose `spring()`:

- ω₀ = √stiffness. With damping ratio ζ < 1:
  x(t) = 1 − e^(−ζω₀t)(cos ω_d t + ζω₀/ω_d · sin ω_d t), where ω_d = ω₀√(1−ζ²).
- Peak overshoot is e^(−ζπ/√(1−ζ²)): 16 % at ζ = 0.5, 44 % at ζ = 0.2.
- The reported duration is the **settle time** to within 1 %. Compose actually
  stops at the property's visibility threshold, which for pixels is usually a
  little earlier.
- The output names the nearest Compose presets when they are close:
  stiffness 50/200/400/1500/10000, damping ratio 0.2/0.5/0.75/1.
- It also gives a SwiftUI `response` = 2π/ω₀ seconds, with `dampingFraction` = ζ.

## 6. Time scale

Recording with Android's animator duration scale set to N stretches every
animation N×. `--time-scale N` divides every reported time by N, and multiplies
fitted spring stiffness by N² (ω scales with 1/time). Labels on sheets and plots
are in real time as well.

## 7. Known limits

| Situation | What you get | What to do |
|---|---|---|
| Full-screen push/slide transition (the whole region changes) | correct timing; curve shape is only a blend proxy (warning printed) | `--roi` on a strip that only the incoming edge crosses, or read positions off the frames by eye for a rough curve |
| Several elements animate at once | spread warning, mixed curve | `--roi` around one element; repeat per element |
| Fade combined with movement | spread warning; early frames below the threshold | fit `--signal blend` for the opacity and `--roi` + `--signal edge` for the motion; report both |
| Element moves and returns (press feedback, shake, ripple) | kind `returns`, no curve | read the sheet; visible duration is still given |
| Low frame rate or dropped frames (large frame interval in the summary) | coarse timing | re-record (references/recording.md); slowed capture with `--time-scale` |
| Tiny motion (a few px) | quantised progress | `--roi` tight around the element (raises analysis resolution); `--analysis-pixels 400000` |
| Video starts mid-motion | note in the summary; progress relative to frame 0 | re-record with a still second before the animation |
