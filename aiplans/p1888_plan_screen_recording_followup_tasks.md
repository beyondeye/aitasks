---
Task: t1888_plan_screen_recording_followup_tasks.md
Base branch: main
Output branch: main
---

# t1888 — Create the screen-recording follow-up task set

## Context

t1887 shipped the `aitask-screen-recording` skill: `aitask_screen_recording.sh`
with `info|bug|anim` modes, `video_prep.py` and `vp_core.py`, and synthetic-fixture
tests. `aidocs/screen_recording_skill_design_review.md` §4 ranks 15 expansion
candidates (E1–E15). Two notes on t1887 added user requirements:

- an image-sequence workflow with `frames` and `sheet` subcommands, plus folder input;
- website docs for v1 now, and docs in every follow-up task;
- an HTML+JS visual frame picker.

This task produces the follow-up **tasks**, not their implementation.

**Decisions made with the user (2026-10-05):**

| Question | Answer → effect |
|---|---|
| Narrated recordings? | *Occasionally* → E1 (transcript) stays, ordered **after** E5. |
| Springs or tweens? | *Mixed/unsure* → create a spring-with-initial-velocity task at **low** priority, after E5. It does not depend on E6, which is deferred. It needs synthetic recordings with known v0, must keep v0 = 0 behaviour, and must document when the fit is useful and how uncertainty is reported. |
| Where outputs land (E7) | A **repo-root gitignored work dir**, `.aitask-screen-recording/`, managed like `.aitask-explain/` and `.aitask-shadow/`: `ait setup` adds the rule, the helper checks `git check-ignore` before writing there, and a `clean` subcommand prunes runs. Not attachments, not artifacts. |
| Deferred | E6, E10, E11, E12, E13. |
| E8 vs t1165 | **No E8 task.** t1165 (Ready) already owns Chatlink video intake (its Phase 3, gated on t1157_4). Send t1165 a note instead. |
| Structure | **One new parent + children**: `--no-sibling-dep` with explicit `--deps`. Children read their siblings' archived plans, which matters because nearly all of them edit `video_prep.py`, `SKILL.md` and the docs page. |

**Facts re-checked 2026-10-05** (step 5 of the task). The corrections below are
written into the task bodies, with the source named:

- **Claude image limits** (platform.claude.com vision docs):
  - tokens ≈ ⌈w/28⌉·⌈h/28⌉ (confirmed);
  - **two tiers**: standard models allow 1568 px **and** 1568 tokens; Claude 4.7+ allow 2576 px and 4784 tokens. On the standard tier the token cap usually binds first;
  - more than 20 images in a request makes images over the limit get **rejected**, not downscaled (≤ 2000 px is safe);
  - animated GIF: first frame only (confirmed).
- **v1 consequence.** `SHEET_MAX_EDGE = 1600` (`video_prep.py:30`) exceeds the standard tier, so sheets get downscaled there.
- **Android `screenrecord`**: the default `--time-limit` is 180 s. The cap is gone from Android 14, where 0 means unlimited (AOSP source; the dev doc is out of date).
- **Android `creation_time`**: AOSP `MPEG4Writer::writeMvhdBox` reads the current
  clock when it writes the header, which happens when the file is finalised. The
  field is UTC with 1 s resolution.
  - That resolution is **not** a bound on alignment error: finalisation can be
    delayed, and a remux or edit rewrites the value.
  - Duration subtraction is unreliable for paused or edited recordings, and for
    recordings whose provenance is unknown.
  - This comes from reading source; no doc states it.
- **iOS**: `com.apple.quicktime.creationdate` is local time with an offset.
- **logcat**: `adb logcat -v threadtime,epoch,usec` prints epoch seconds in a 19-character field (leading spaces), then `.uuuuuu`.
- **whisper.cpp**:
  - the binary is `whisper-cli`, renamed from `main` on 2024-12-20;
  - flags: `-oj`, `-ojf` (token timestamps), `--vad -vm`, `--prompt`; never `-nt`;
  - the current Silero model is **`ggml-silero-v6.2.0.bin`** (v5.1.2 still exists);
  - model sizes: tiny.en 75 MiB, base.en 142 MiB, small.en 466 MiB;
  - safe input recipe: `-ar 16000 -ac 1 -c:a pcm_s16le`; MIT licence.
- **ffmpeg**:
  - freezedetect `n=0.001(−60 dB) d=2`;
  - blackdetect `d=2.0 pic_th=0.98 pix_th=0.10` (so set `d=0.1` explicitly);
  - silencedetect `n=−60 dB d=2`;
  - `-fps_mode` needs ffmpeg ≥ 5.1, and `-vsync` was **removed in 9.0**.
- **Other agents**:
  - Codex `view_image` takes one `path` per call (optional `detail`) and resizes to 2048 px / 2500 patches. The model often won't call it unless the path is spelled out (openai/codex#12439).
  - OpenCode `read` returns jpeg/png/gif/webp as attachments, **not SVG**.
  - agy reads images via `@path`. It *may* accept video directly; this is unverified, so hedge the premise "agents can't read video".
- **In-repo gap.** `.agents/skills/codex_tool_mapping.md:9` maps `Read` to `cat`, so Codex can't actually view sheets today.

## Implementation (runs at Step 7, after approval; plan mode creates nothing)

### 1. Write task bodies to the scratchpad

Write one description file per task with the Write tool, under
`<scratchpad>/t1888_bodies/`. Every child body has these sections:

- **Context**: why it matters, its place in the set, and a pointer to the review row.
- **Key files**.
- **Reference patterns** (functions with line numbers).
- **Scope / acceptance criteria**.
- **Test idea**, using synthetic fixtures in `tests/screen_recording_synth.py` with
  known ground truth. Skip when ffmpeg is absent, like the existing tests.
- **Facts** (dated 2026-10-05, with sources).
- **Docs**: the how-to sections it adds to the website page.
- **Cross-cutting rules** (copied into each body; also stated in the parent):
  - Docs live in `website/content/docs/skills/aitask-screen-recording.md`, with a
    how-to per use case the task enables. Follow
    `aidocs/framework/documentation_conventions.md`: current state only,
    agent-generic prose, relref links. Run `cd website && python3 check_links.py --build`
    and `hugo build --gc --minify`.
  - Update the skill's `SKILL.md` and `references/`. The `.agents`/`.opencode`
    wrappers are thin pointers; run `./.aitask-scripts/aitask_skill_verify.sh`.
  - **New subcommands of `aitask_screen_recording.sh` need no whitelist entries.
    Any new `.aitask-scripts/*.sh` helper must ship the 5-touchpoint whitelist
    checklist** (`aidocs/framework/aitasks_extension_points.md`, "Adding a new helper
    script"):
    - `.claude/settings.local.json`
    - `.codex/rules/default.rules`
    - `seed/claude_settings.local.json`
    - `seed/codex_rules.default.rules`
    - `seed/opencode_config.seed.json`
  - Never copy a source recording into the repo, never upload, and keep ffmpeg an
    optional runtime dependency (t1887 decision).
  - Every flag a doc names must be checked against `<mode> --help` output.
  - **Inferred values carry their provenance.** Timestamps, coordinates and
    measurement windows are exported as exact only when the inputs prove them.
    Otherwise they are labelled heuristic, or the export is disabled with a reason.
    Where two requirements can conflict (keep-all vs a budget), the body states the
    overflow behaviour and includes a fixture that forces the conflict.

### 2. Create the parent

```bash
./.aitask-scripts/aitask_create.sh --batch --commit --name screen_recording_skill_expansion \
  --type feature --priority medium --effort high \
  --labels claudeskills,skills,python,website --followup-of 1887 \
  --desc-file <scratchpad>/t1888_bodies/parent.md
```

The anchor resolves to 1887. Capture `<P>` from `Created: <path>`. The parent body
holds:

- the decision table above;
- the dependency graph;
- the cross-cutting rules;
- the deferred list with reasons;
- the t1165 relationship;
- links to the review document and to t1887's archived plan.

### 3. Create the 14 children in this order (numbers = child ids)

Each uses `--parent <P> --no-sibling-dep --deps t<P>_a,...` (sibling deps are
written `t<P>_<n>`). Create them sequentially so every dependency already exists;
check each `Created:` line. Priority and effort follow the review table (value →
priority; effort S/M/L → low/medium/high). Overrides are marked ⇑ or ⇓.

| # | name | E# | type | pri / eff | deps | labels |
|---|---|---|---|---|---|---|
| 1 | `website_docs_current_capabilities` | E14 | documentation | high⇑ / medium⇑ | — | website, documentation, claudeskills |
| 2 | `triage_rows_freeze_black_silence` | E2 | feature | high / low | 1 | python, claudeskills |
| 3 | `frames_subcommand_exact_drilldown` | E4 + note 1a | feature | high⇑ / medium⇑ | 2 | python, claudeskills |
| 4 | `sheet_subcommand_any_image_folder` | note 1b | feature | high / low | 3 | python, claudeskills |
| 5 | `pick_visual_frame_picker` | note 2 | feature | high / medium | 4 | python, claudeskills, ui |
| 6 | `image_folder_input_mode` | note 1c | feature | medium / medium | 5 | python, claudeskills |
| 7 | `push_slide_shift_curves` | E5 | feature | high / medium | 6 | python, claudeskills |
| 8 | `narration_transcript_whisper` | E1 | feature | medium⇓ / medium | 7 | python, claudeskills |
| 9 | `spring_initial_velocity_fit` | user Q2 | feature | low / medium | 7 | python, claudeskills |
| 10 | `wallclock_logcat_merge` | E3 | feature | high / medium | 8 | python, claudeskills |
| 11 | `repo_work_dir_and_clean` | E7 (redefined) | enhancement | medium / low | 10 | python, ait_setup, claudeskills |
| 12 | `cross_agent_image_validation` | E9 | chore | medium / medium | 5 | codex, opencode, codeagent, claudeskills |
| 13 | `missing_dependency_hints` | E15 | enhancement | low / low | 1 | ait_setup, python |
| 14 | `retrospective_deferred_candidates` | (conventions) | chore | low / low | 9,11,12,13 | claudeskills, task-planning |

**Reading the chain.** The main line is 1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 10 → 11.
This is the review's E2 → E4 → … order with three changes:

- E1 moves after E5, per your answer.
- The image-sequence cluster (3–6) sits at E4's position, as the notes asked
  ("alongside E4").
- E14 comes first, so every later task extends an existing page.

The chain also serialises edits to `video_prep.py`, `SKILL.md` and the docs page.

**Side branches:**

- 9 hangs off 7 (both touch the anim fit path). It is low priority, so it does not block E1.
- 12 hangs off 5, so validation covers the picker's new AskUserQuestion.
- 13 hangs off 1.
- 14 closes the set.

**Rejected:** a dependency 9 → 8. It would block E1 behind a low-priority task.

**Per-child scope** (expanded into the bodies):

1. **E14, docs for v1.**
   - Create the page with front matter like `aitask-note.md`:
     `title/linkTitle "/aitask-screen-recording"`, weight, description,
     `maturity: [experimental]`, `depth: [intermediate]`.
   - Add a row to `skills/_index.md` under the best-fitting category.
   - How-tos:
     - bug report from a recording;
     - implementing an animation from a prototype;
     - slowed capture with `--time-scale`;
     - narrowing with `--crop-top`/`--crop-bottom`/`--roi`/`--window`/`--range`;
     - recording tips, from `references/recording.md`, with the Android 14 time-limit fact;
     - limits and how to read the warnings;
     - output layout, and the current default `$TMPDIR/video-prep/`.
   - The "agents can't read video" wording must be hedged (agy).
2. **E2, triage rows.**
   - Run freezedetect, blackdetect (`d=0.1:pic_th=0.98:pix_th=0.10`) and
     silencedetect (only when an audio stream exists). Use the parameters verified above.
   - Rows go into `timeline.tsv` and `summary.md`, and into `run.json`.
   - **Black intervals are never lost, but images stay bounded** (resolving "never drop
     black frames" against `--max-frames`):
     - *every* detected freeze, black or silence interval is kept in the timeline
       and `run.json` metadata, whatever the frame budget;
     - images: one representative frame per black interval, ranked above motion
       picks inside the `--max-frames` budget;
     - when there are more black intervals than the budget allows, the extra
       intervals keep their timeline rows but have no image. `cap_hit` is set, and
       the summary reports the omitted count and suggests narrowing with
       `--range`/`--window`;
     - black frames are never silently dropped (the mcp-video-analyzer anti-pattern),
       and the budget is never silently exceeded.
   - Test:
     - a synthetic frozen span and black span at known times (±1 frame);
     - a muxed `sine` / silent audio track;
     - **a fixture with more black intervals than `--max-frames`**: every interval
       appears in `timeline.tsv`, the image count is ≤ the budget, `cap_hit` is
       true, and the omitted count is correct.
   - Docs: "spot a hang, black flash or silent gap".
3. **E4 + `frames`.**
   - `frames VIDEO (--range A-B | --at T[,T…]) [--roi|--crop-top…] [--max-frames N] [--out]`
     writes every native frame at full resolution with `-fps_mode passthrough`
     (ffmpeg ≥ 5.1).
   - Frames are named by integer ms from the showinfo pts, e.g. `t00007040.png`. Never
     index × rate. Write a `frames.tsv` manifest.
   - **The manifest records image→source geometry** for each frame:
     - source video width and height;
     - crop offset (x, y) and crop size from `--roi`/`--crop-*`;
     - output scale;
     - **the SHA-256 of the image file as written.** This binds the record to that
       exact content.

     This is the provenance #5 needs to map a rectangle back to source pixels, and it
     is valid only while the hash matches. bug and anim `run.json` record the same
     geometry and hash for the frames they write.
   - Add `cap_hit` to `run.json` for frames, bug (`--max-frames`) and anim
     (`--max-view-frames`, `--max-segments`).
   - Add one shared filename-timestamp parser that accepts both `t<ms>` and the
     existing `NN_5.500s` / `fNNN_5.500s` names. The existing bug/anim names stay;
     they already carry ms precision and SKILL.md cites them.
   - Print a per-frame token estimate, and warn when full-resolution frames exceed
     the tier limits above (a 1080×2400 frame is downscaled on the standard tier).
   - Test: extract at known pts, compare pixels with the synthetic frame, and run a
     VFR clip (`encode(vfr=True)`) to prove timestamps come from pts.
   - Docs: "extract exact frames for close inspection".
4. **`sheet`.**
   - `sheet DIR [--per-sheet] [--out]` builds labelled sheets from any folder,
     including user-cropped or annotated images. Mixed sizes are letterboxed.
   - Labels carry the parsed time and the Δms to the previous image; a deleted frame
     shows up as a larger Δ.
   - Reuse `sheet_layout()`/`contact_sheets()` (`video_prep.py:186-215`) and
     `SHEET_MAX_EDGE`.
   - Test: a folder of synthetic PNGs with one cropped and one deleted; assert the
     label manifest and the sheet count.
   - Docs: **the documented extract → edit → feed flow** (`frames` → hand edits →
     `sheet` → read).
5. **`pick`.**
   - `pick <frames-dir|run-dir> [--open] [--out]` writes one self-contained static
     `index.html`, with no server.
   - Inputs are copied and hashed into `<out>/src/` before anything is derived.
   - UI:
     - a thumbnail grid with time and Δms;
     - click and shift-click range selection;
     - keyboard navigation and a large preview.
   - **A selection is not a measurement window, and the picker certifies nothing.**
     - The default export labels first…last as a **viewing range**.
     - The user can explicitly mark a start frame and an end frame. Only then does the
       block add `--window A-B`, labelled **"user-marked endpoints (unverified)"**.
     - There is no automatic still/settled validation. A local pixel check cannot
       tell a settled frame from a spring turning point, subpixel motion or a
       duplicated capture frame, so the picker does not try.
     - The anim run's own endpoint diagnostics stay the authority. SKILL.md tells the
       agent to read them before trusting a user-marked window.
   - **ROI export needs provenance bound to content.** The rectangle maps to
     `--roi X,Y,W,H` in source pixels only through #3's geometry record, which is
     **bound to the SHA-256 of the image as written at extraction**.
     - The picker compares the hash of its `src/` snapshot of each input with the
       recorded hash.
     - With no record, or a hash mismatch (any edit, including crop then resize back
       to the same dimensions, or a translation within the same canvas), the source
       ROI export is **disabled** with a visible reason.
     - It may still offer a rectangle in that image's own pixels, labelled as such.
     - Supplying an updated transform for an edited image is out of scope. This is a
       documented limitation, not a guess.
   - Copy: a paste-ready plain-text block of **absolute paths**, t_ms, Δms and an
     optional note, via `navigator.clipboard.writeText`. When that is unavailable,
     show the text for manual copy.
   - `localStorage` is wrapped in try/catch and keyed by a content fingerprint.
   - Opener: one function with a per-platform table (`xdg-open`, macOS `open`, WSL).
     With no display (SSH, no `DISPLAY`/`WAYLAND_DISPLAY`), print the page path and
     let the agent select itself; never fail the skill.
   - SKILL.md asks "pick frames visually?" with AskUserQuestion, following the
     visibility rule in `skill_authoring_conventions.md`. Check the
     `request_user_input` (Codex) and `ask` (OpenCode) mappings.
   - Reference implementation: `thinking_app#443`
     (`tools/verification/screenshot-review-gallery.{sh,py}`, read at 215e9e4).
     Resolve it via `./ait projects resolve thinking_app`; never by path.
   - Test: the Python builder's output contract (the embedded manifest: paths, t_ms,
     labels, geometry) and the no-display fallback. Acceptance cases:
     - **a mid-motion-only selection** yields a viewing range and no `--window`;
     - **a selection spanning a spring turning point or a duplicated frame pair, with
       no user marks**, is never labelled settled and emits no `--window`;
     - user-marked endpoints emit `--window` with the "unverified" label;
     - **a `frames --roi` crop (hash intact)** maps the ROI correctly to source
       pixels, checked against a synthetic element's known position;
     - **a same-dimensions geometric edit** (crop then resize back, or a translate
       within the canvas) has the source ROI export disabled by the hash mismatch;
     - **an input with no geometry record** has the source ROI export disabled.

     The window and ROI rules live in the Python builder and are embedded as data,
     so they are testable without JS. Whether to add a node-based JS test is the
     task's call.
   - At Step 8c, offer a manual-verification follow-up for the browser UI.
   - Docs: "pick frames visually and hand them to the agent".
6. **Folder input.**
   - `bug`/`anim` accept a directory of images. Order and timing come from filename
     timestamps (the shared parser from #3), or from `--fps N` for unnamed sequences.
   - Anim on a sequence with deleted frames warns about gaps and widens the
     uncertainty. Mixed sizes are an error with a clear message for anim.
   - Test: synthetic anim → `frames` → delete some → `anim` on the folder; duration
     within tolerance, plus the gap warning.
   - Docs: "review or measure a curated image sequence".
7. **E5, full-screen push/slide curves.**
   - Shift estimation by 1-D profile matching on downscaled rows or columns
     (stdlib only), between each frame and the start/end pictures. It replaces the
     blend proxy for full-screen pushes.
   - Test: the push transition in the existing `bug_frames` fixture (FastOutSlowIn,
     300 ms); the duration must be within the existing ±12 ms and the named curve
     must win.
   - Docs: extend the animation how-to with full-screen transitions.
8. **E1, transcript.**
   - Optional and detected: `whisper-cli` plus a model found via a flag or env var.
     **Never download silently.** When missing, the summary says how to enable it.
   - `ffmpeg … -ar 16000 -ac 1 -c:a pcm_s16le`, then `whisper-cli -oj --vad -vm ggml-silero-v6.2.0.bin --prompt <vocab>`.
   - Merge into `timeline.tsv` and the summary (±1–2 s). Finish with a
     Heard/Saw/When/Expected checkpoint that cites frame files.
   - Test: the merge logic against a fixture whisper JSON (no whisper needed). A live
     test runs only when whisper-cli and the model are present; it checks that a
     silent clip yields no text.
   - Docs: "narrated bug report".
9. **Spring with initial velocity.**
   - Extend `spring()` and `fit_motion` (`vp_core.py:336,432`) with v0.
   - The synthetic fixture `spring_progress(k, z, t0)` gains `v0`. Recordings with
     known v0 must recover it within a stated tolerance.
   - **The existing v0 = 0 tests and outputs stay unchanged.**
   - `fit.json` reports v0 and its uncertainty, including the v0/stiffness ambiguity.
   - Docs: when the fit is useful (interrupted or retargeted animations, flings) and
     how to read the uncertainty.
10. **E3, wall-clock and logcat merge.**
    - **Confidence ladder, with every inference labelled and none presented as exact:**
      1. `--recorded-at` (user-supplied): `explicit`;
      2. QuickTime `creationdate` (local time with offset): `metadata`;
      3. container `creation_time`: `heuristic`, with **no stated error bound**.
         - "start = creation_time − duration" is applied only under a recorder
           convention the task verifies. The recorder is identified from container
           tags or the encoder string, e.g. Android `screenrecord`.
         - Otherwise the value is reported as an unknown-meaning timestamp, not
           converted.
      4. mtime − duration: `heuristic`;
      5. otherwise: `unknown`. Rows keep `t_ms` and leave `t_wall` empty.
    - Every row gets `t_ms`. `t_wall` is set only when a ladder step applied, and
      `run.json` records its confidence.
    - `--log logcat.txt` parses `-v threadtime,epoch,usec` (and plain threadtime when
      `--recorded-at` supplies the year and zone) into interleaved rows.
    - **When the best source is heuristic, interleaving still happens but the summary
      warns.** It names the source, says the alignment may be off by more than a
      second (delayed finalisation, pauses, edits), and asks for `--recorded-at`
      (or a visible on-screen clock such as `screenrecord --bugreport`) wherever
      accuracy matters.
    - Test:
      - a fixture log with known epochs plus an explicit `--recorded-at`: exact
        interleaving;
      - **ambiguous metadata**: `creation_time` from an unidentified encoder gives
        `heuristic` or `unknown`, never `metadata`, and no fabricated start;
      - **delayed finalisation**: `creation_time` lags the true end by several
        seconds. The output must carry the heuristic label and warning; it must not
        claim accuracy;
      - a missing `creation_time` gives `unknown` with an empty `t_wall`.

      Synthetic timestamps are chosen to **break** the convention, not only to match it.
    - Docs: "align a recording with logcat".
11. **E7, repo work dir.**
    - Default output root becomes `.aitask-screen-recording/<stem>-<mode>[-N]`.
    - Add it to this repo's `.gitignore`, and add an `ait setup` rule writer
      modelled on `setup_shadow_store_gitignore` (`aitask_setup.sh:~2446`). Read the
      extension-points doc before editing setup.
    - Before writing, the helper runs `git check-ignore -q`. If the dir is not ignored
      (or this is not a git repo), it falls back to `$TMPDIR/video-prep/` with a warning.
    - `--out` still wins.
    - `clean [--older-than DUR] [--dry-run]` as a subcommand. Its pattern is
      `aitask_explain_cleanup.sh`. It refuses paths outside the root.
    - Test: check-ignore fallback in a scratch git repo, and that the setup rule is
      idempotent.
    - Docs: update "where outputs go", and add "clean up old runs".
12. **E9, other agents.**
    - Manual run per agent (Codex, OpenCode, agy) on a fixture recording.
    - Fix the Codex image gap: add an image → `functions.view_image` row next to
      `codex_tool_mapping.md:9`. That file is shared by all skills, so check the
      impact. SKILL.md must spell out exact paths.
    - Tell image readers to use `plot.png`, not `.svg`.
    - Measure sheet legibility on the Claude standard tier, where a 1600 px sheet is
      downscaled to about 1092 px, and decide whether `SHEET_MAX_EDGE` should drop
      to ≤ 1568 or become per-tier.
    - Verify the #5 AskUserQuestion mapping.
    - Docs: a per-agent notes section (an exception allowed by the generic-prose rule).
13. **E15, dependency hints.**
    - Preflight in `video_prep.py` before `probe()`. Today a missing ffprobe gives a
      bare `ffprobe not found on PATH` from `run()` (`video_prep.py:41-45`).
    - Print per-OS install commands (values as `detect_os()`, `aitask_setup.sh:155`)
      and an ffmpeg < 5.1 version warning.
    - Optionally, an `ait setup` "Optional:" warning like docker
      (`aitask_setup.sh:270-275`). **No auto-install.**
    - Test: with ffmpeg removed from PATH the hint appears and the exit code stays 1.
    - Docs: a Requirements section.
14. **Retrospective** (per `planning_conventions.md`).
    - Once the set has been in daily use, re-evaluate the deferred candidates (E6,
      E10, E11, E12, E13) with evidence.
    - Create standalone tasks only where the evidence justifies them; otherwise
      record "no action" with the reason.

### 4. Note to t1165 (after creation)

```bash
./ait note 1165 --from 1888 --with-live --file - <<'EOF'
…
EOF
```

The note body covers four points:

- t1887's skill now exists and overlaps t1165 Phase 1: timestamped picks with
  reasons, sheets, `timeline.tsv` and `run.json` from `aitask_screen_recording.sh`.
- New children t<P>_2 (triage), t<P>_3 (frames) and t<P>_10 (wall-clock/logcat)
  cover more of Phase 1. **Advisory:** consider building Phase 1 on that helper
  instead of a parallel `ait bug-video prepare`.
- On 2026-10-05 the user decided that design-review E8 (Chatlink video attachments)
  belongs to t1165 Phase 3. No separate task was created.
- E13 (Gemini) is deferred in the screen-recording set. If t1165 keeps Gemini, it
  must stay strictly opt-in per file.

The note is hedged as advisory and dated to the current SHA. A `LIVE_NONE:` result
is a success.

### Post-phase (risk mitigations)

1. [verify_created_task_graph] After all creations:
   - Run `./.aitask-scripts/aitask_ls.sh -v --children <P> 99` and confirm all 14
     children exist.
   - Only child 1 is unblocked.
   - Grep each child's frontmatter `depends:` against the table in step 3, and
     confirm `anchor` resolves to 1887 (on the parent, and inherited by the children).
   - Fix any mismatch with `aitask_update.sh --batch` before Step 8.

### 5. Step 8/9

- No code changes, so skip the code commit. Task creation commits through
  `aitask_create.sh --commit`.
- Step 8 consolidates the plan with **Final Implementation Notes**, which list:
  - the created ids;
  - **the deferred and dropped candidates with reasons**:
    - E6: deferred by the user; M–L effort, needs an element template;
    - E10: OCR engine choice is open;
    - E11: skill-text only; revisit when long recordings occur;
    - E12: low–medium value, L effort, Android 12+ only;
    - E13: low value plus privacy concerns (free-tier human review, 1 fps sampling); if revived, strictly opt-in per file and never triggered by an API key in the environment;
    - E8: owned by t1165 Phase 3, note sent.
- Then Step 9 archival (current branch; no merge).

## Verification

- `aitask_ls.sh -v --children <P> 99` shows 14 children, with only #1 ready.
- `grep -H '^depends:' aitasks/t<P>/*.md` matches the table.
- `grep '^anchor:' aitasks/t<P>_*.md` shows `1887`.
- Every child body contains a Docs/how-to section and a test idea. #8, #11 and #13
  also state the conditional 5-touchpoint rule.
- `./ait note` returned `NOTE_APPENDED:`.

## Risk

### Code-health risk: low
- Only task files and one note are written; no framework code changes. The blast radius is limited to new task data. · severity: low · → mitigation: none

### Goal-achievement risk: low
- A dependency, anchor or child-count mistake in 15 sequential creations would break the agreed order, which is the "Done when" criterion. · severity: low (residual: addressed by inline post-phase verify_created_task_graph) · → mitigation: inline post-phase verify_created_task_graph
- Facts cited in the bodies (image tiers, Android behaviour from AOSP source, whisper model names) can go stale before a child is picked. · severity: low · → mitigation: none. Each fact is dated with its source, and each child re-checks the facts it uses.
- t1165 and the new set could still diverge on video ingestion; the note is advisory only. · severity: low · → mitigation: none. The note is the agreed handling.

### Planned mitigations
- timing: post-phase | name: verify_created_task_graph | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: dependency/anchor mistakes during creation | desc: verify the child count, deps and anchor of the created set against the plan table, and fix mismatches before Step 8

## Final Implementation Notes
- **Actual work done:**
  - Created parent **t1893** `screen_recording_skill_expansion` with `--followup-of 1887` (anchor 1887).
  - Created 14 children with `--no-sibling-dep` and explicit deps:
    t1893_1 docs (E14), t1893_2 triage (E2), t1893_3 frames (E4 + note 1a),
    t1893_4 sheet, t1893_5 pick, t1893_6 folder input, t1893_7 push/slide (E5),
    t1893_8 transcript (E1), t1893_9 spring v0, t1893_10 wall-clock/logcat (E3),
    t1893_11 repo work dir + clean (E7, redefined), t1893_12 other agents (E9),
    t1893_13 dependency hints (E15), t1893_14 retrospective.
  - Each body carries scope, acceptance cases, a test idea, dated facts with sources, and a docs how-to, plus the shared cross-cutting rules block (docs, tests, the 5-touchpoint rule, privacy, provenance).
  - Sent an advisory note to t1165 (id `2026-10-05T14:18:44Z.d896cff142712d8d6b56f507`).
- **Deviations from plan:** none in the task set or deps.
  - The plan was revised twice before approval, after review findings on four children:
    - t1893_2: black-interval budget overflow;
    - t1893_5: viewing range vs user-marked window, and ROI geometry bound to the SHA-256 recorded at extraction;
    - t1893_10: creation_time treated as heuristic with no error bound.
- **Issues encountered:**
  - `aitask_create.sh` uses `--deps`, not `--depends`.
  - Child deps are written `t<P>_<n>`.
- **Key decisions (with the user, 2026-10-05):**
  - Narration occurs occasionally, so E1 comes after E5.
  - Springs vs tweens is mixed or unsure, so the spring-v0 child is low priority after E5 and independent of E6.
  - E7 means a repo-root gitignored `.aitask-screen-recording/`, checked with `git check-ignore`, with a `clean` subcommand.
  - Structure: one parent with children.
  - E14 comes first; the image-sequence cluster takes E4's slot.
- **Deferred or dropped candidates (not created):**
  - **E6** (opacity/position channels): deferred by the user. M–L effort; needs an element template.
  - **E10** (OCR): deferred. The engine choice (RapidOCR vs tesseract) is open.
  - **E11** (sub-agent describers): deferred. Skill text only; revisit when recordings over about 2 minutes occur.
  - **E12** (Perfetto FrameTimeline): deferred. Low–medium value, L effort, Android 12+ only.
  - **E13** (Gemini describe): deferred. Low value and a privacy risk (free-tier human review; 1 fps sampling). If revived, strictly opt-in per file, never triggered by an API key in the environment.
  - **E8** (Chatlink attachments): not created. It is owned by t1165 Phase 3, which is gated on t1157_4; t1165 was sent the note.
  - t1893_14 re-evaluates all of these with usage evidence.
- **Facts re-checked 2026-10-05:**
  - Claude image tiers: standard 1568 px and 1568 tokens; Claude 4.7+ 2576 px and 4784 tokens. With more than 20 images, oversized ones are rejected.
  - screenrecord's 180 s cap is gone from Android 14.
  - Android `creation_time` is written at finalisation (from AOSP source only).
  - The Silero VAD model is now v6.2.0.
  - `-vsync` was removed in ffmpeg 9.0.
  - Codex `view_image` takes one path per call.
  - OpenCode `read` does not read SVG.
  - agy may accept video (unverified).
- **Upstream defects identified:**
  - `.agents/skills/codex_tool_mapping.md:9` — maps `Read` to `cat`, so Codex cannot view the screen-recording contact sheets. Tracked in t1893_12.
  - `.aitask-scripts/screen_recording/video_prep.py:30` — `SHEET_MAX_EDGE = 1600` exceeds Claude's standard-tier 1568 px / 1568-token limit, so sheets are downscaled there. Tracked in t1893_12.
