# Screen-recording skill: design review of existing resources

Date: 2026-10-04. This reviews existing resources, third-party and inside this
repository, that could expand the `aitask-screen-recording` skill. The goal is a
ranked, evidence-backed expansion list.

Where the skill lives:

- `.claude/skills/aitask-screen-recording/`: `SKILL.md` and `references/`.
- `.aitask-scripts/aitask_screen_recording.sh`: the whitelisted entry point.
- `.aitask-scripts/screen_recording/`: `video_prep.py` (CLI) and `vp_core.py`
  (pure analysis).
- `tests/test_screen_recording_{core,cli}.py` and
  `tests/screen_recording_synth.py`: tests and synthetic-recording fixtures.
- Thin wrappers in `.agents/skills/`, `.opencode/skills/` and
  `.opencode/commands/`.

**Evidence level.**
- Third-party resources: read from source on the date above (`gh api`, WebFetch).
  Nothing was installed or executed, so behaviour notes come from reading code.
- In-repo resources: checked against the files cited (line numbers as of commit
  `f8a049f3c`).

---

## 1. What v1 does (the baseline being expanded)

Claude Code cannot read video. As of the date above,
[anthropics/claude-code#80865](https://github.com/anthropics/claude-code/issues/80865)
("Support video input") is open with no Anthropic response. In
[#96892](https://github.com/anthropics/claude-code/issues/96892) a `.mp4` is
refused as a binary file. v1 is one stdlib-only Python CLI over ffmpeg and,
optionally, ImageMagick, run on the framework venv interpreter through
`aitask_screen_recording.sh`.

| Mode | Selection | Outputs |
|---|---|---|
| `bug` | `mpdecimate` keeps every visible change. Each kept frame's *dwell* (gap to the next kept frame) splits picks into start/end, **state** (dwell ≥ 0.4 s), **motion** (one per 1 s of continuous change, counted from the start of the run) and **brief** (a whole change ≤ 0.12 s: flash or glitch). A priority cap applies (motion is dropped first). | `summary.md`, `timeline.tsv`, labelled contact sheets ≤ 1600 px, full frames at a 1000 px long edge |
| `anim` | mpdecimate *finds* motion segments only. Each segment is re-decoded at **native frames** ± 0.25 s, because mpdecimate defaults drop ease-out tails. Per-frame progress comes from bounding boxes of change vs the start and end pictures (exact for slides, including overshoot) or from a blend ratio (exact for fades). | per segment: `curve.tsv`, `fit.json`, a plot, sheets. Fits: 13 named tweens (CSS, Compose, M2/M3 tokens), a free cubic-bezier, and a spring with the nearest Compose preset and a SwiftUI response. `--time-scale N` handles slowed captures. |

The tests (`tests/test_screen_recording_{core,cli}.py`) have 52 cases and take
about 36 s. They skip without ffmpeg. Synthetic 60 fps recordings with known
ground truth go through the real CLI, plus one wiring test through the bash
entry point. Measured accuracy on those clips:

- Tween duration: ±12 ms; ±5 ms on a 5× slowed capture.
- The correct named curve wins for ease-out, FastOutSlowIn, linear and
  ease-in-out (fade).
- Spring: stiffness within 15 % and damping within 0.07; overshoot within 3
  points.
- Bug flow: exact pick sequence through a push transition, a scroll, a 20 px
  checkbox toggle and a one-frame flash.
- Status-bar clock noise is removed by `--crop-top`.
- A mutant of the spread metric was confirmed to fail its regression test.

---

## 2. Third-party resources

| Resource | Kind / license / activity | Verdict |
|---|---|---|
| [talkthrough-mcp](https://github.com/korovin-aa97/talkthrough-mcp) | Python MCP + plugin, MIT, 30★, active (v0.4.2, pinned via `uvx`) | **Best prior art for bug reports.** Borrow its selection expression, wall-clock ladder, drill-down tools and checkpoint prompt. |
| [mcp-video-analyzer](https://github.com/guimatheus92/mcp-video-analyzer) | Node MCP, MIT, 85★, active | Borrow its annotated timeline and frame-budget table; avoid its black-frame filter and dHash. |
| [claude-video-vision](https://github.com/jordanrendric/claude-video-vision) | plugin + Node MCP, MIT, 1.3k★ | Borrow its triage pre-pass filters and VAD for transcription; its timestamps are floored to whole seconds. |
| [video-frames-skill](https://github.com/mugnimaestra/video-frames-skill) | skill, "MIT" badge with no LICENSE file, 11★ | Borrow the OCR filter chain and the token estimate in its JSON; its token formula is out of date. |
| [ffmpeg-analyse-video-skill](https://github.com/fabriqaai/ffmpeg-analyse-video-skill) | skill, no LICENSE file, 32★ | Borrow the sub-agent fan-out; its timestamps are wrong outside interval mode. |
| [video-context-plugin](https://github.com/vusallyv/video-context-plugin) | plugin, MIT, 3★ | Forced first/last frames (v1 already has them); `-nt` transcripts can't be aligned. |
| [video-vision-mcp](https://glama.ai/mcp/servers/KitDevUA/video-vision-mcp) | Python MCP, MIT, 0★ | **Privacy anti-pattern:** uploads the whole video to Gemini whenever an API key is in the environment. |
| [Claude-Command-Suite extract-video-frames](https://github.com/qdhenry/Claude-Command-Suite/blob/main/.claude/commands/media/extract-video-frames.md), [claude-world video-extract](https://github.com/claude-world/claude-agent/blob/main/.claude/skills/video-extract/SKILL.md), [msadig gist](https://gist.github.com/msadig/b109ff286929b79c14a8480e9b848651) | commands / cheat sheets | Nothing to borrow beyond a manifest shape. The gist copies recordings into the project tree. |

None of them measures animation timing or easing. The surveyed tools sample at
≥ 1 s floors or by scene score, and both miss a 300 ms animation. That makes v1's
`anim` mode the novel part; there is no prior art to align it with.

### Ideas worth borrowing (by value)

1. **talkthrough's selection.**
   - Expression:
     `select='isnan(prev_selected_t)+gt(scene,0.10)+gte(t-prev_selected_t,FLOOR)'`
     with FLOOR = max(1, duration/600), plus `showinfo`, `-fps_mode passthrough`,
     frames named by milliseconds (`t00007040.jpg`) and a `cap_hit` flag.
   - v1's dwell-based selection already covers slow changes. What's still worth
     adopting is the **ms-named files** and an explicit **cap-hit** flag in
     `run.json`.
2. **Wall-clock ladder with a confidence label** (talkthrough). The sources, in
   order: user-supplied `recorded_at`, QuickTime creationdate, container
   `creation_time`, then file mtime minus duration. Every row gets both `t_ms`
   and `t_wall`. This is the prerequisite for merging logcat.
3. **Triage pre-pass** (claude-video-vision):
   - `freezedetect=n=-60dB:d=2` (a hung app);
   - `blackdetect=d=0.1:pic_th=0.98:pix_th=0.10`;
   - `silencedetect`.

   Each emitted as timeline rows. Black frames must **never** be dropped, since
   they may be the bug; mcp-video-analyzer drops them.
4. **Timestamped transcript.**
   - Command:
     `whisper-cli -m ggml-base.en.bin -f a.wav -oj --vad -vm ggml-silero-*.bin`
     (whisper.cpp, MIT; the base model is 142 MiB).
   - Pass the product vocabulary as the initial prompt.
   - Merge into the timeline within ±1–2 s, and end with a
     Heard/Saw/When/Expected checkpoint that cites frame files (talkthrough's
     `/bug`).
   - Avoid `-nt`, which drops timestamps.
5. **Drill-down instead of dumping.** At most about 6 frames per call, plus an
   exact-millisecond, optionally cropped full-resolution `frame` command. For
   long recordings, sub-agents describe batches of frames as text so images never
   enter the main context (ffmpeg-analyse-video-skill).
6. **Budget against current image limits** (per Anthropic docs as reported by the
   research pass; re-check when implementing):
   - Cost ≈ ⌈w/28⌉·⌈h/28⌉ tokens.
   - A 1568 px long edge is the safe default; newer models accept up to 2576 px.
   - More than 20 images in a request limits each to 2000 px.
   - Animated GIFs show only their first frame.

   v1 sheets cap at 1600 px and print a token estimate. Keep the formula in one
   constant.
7. **OCR mode.** The filter chain
   `format=gray,eq=contrast=1.3:brightness=0.05,unsharp=5:5:0.7:5:5:0.0` before
   OCR (RapidOCR or tesseract) helps text-heavy bug reports.
8. **Annotated timeline** (mcp-video-analyzer): one table merging frames,
   transcript and OCR entries.

### Things to avoid (seen in the survey)

- Cloud upload triggered just because an API key is in the environment. Any
  "describe with Gemini" route must be an explicit choice per file.
  - Gemini samples at 1 fps by default, so it is useless for animation timing.
  - On its free tier, inputs may be read by human reviewers.
- Timestamps computed as index × rate in non-uniform modes, or rounded to whole
  seconds.
- Copying recordings into the project tree, or claiming hidden directories are
  gitignored.
- Unpinned `npx …@latest`, silent `brew install`, per-frame audio slices (Claude
  can't listen to them).

---

## 3. In-repo resources (aitasks)

Nothing in the repo handles video yet: no ffmpeg, ffprobe or mp4 handling in
`aidocs/` or `.aitask-scripts/`. These existing pieces could carry the skill's
outputs.

| Resource | What it offers | Constraint | Fit |
|---|---|---|---|
| **Task attachments** (`aidocs/task_attachments_design.md`, `ait attach`) | content-hashed blobs on the data branch, listed in the task's `attachments:` frontmatter | `attachment_max_size_mb` defaults to 25 (`.aitask-scripts/aitask_attach.sh:192,249`). Design non-goal: "Large-blob streaming (GB-scale media). Target is screenshots and small…" (`task_attachments_design.md:31`). Bucketing was deferred on the assumption of dozens to low hundreds of attachments per project (`attachment_metadata_bucketing.md`). | Attach **contact sheets and the timeline**, never raw video or every frame. Note: `aitask_attach.sh` is not whitelisted in `.claude/settings.local.json`, so each call prompts. |
| **Artifacts** (`aidocs/unified_artifact_design.md`, `ait artifact`) | versioned files with stable `art:<id>` handles and a `kind` field; a `dir` backend for a NAS | one file per artifact; `artifact_max_size_mb` defaults to 25 (`aitask_artifact.sh:145`) | Store the timeline, `fit.json` or a zipped frame set under new kinds (`video_timeline`, `anim_curve`); a re-run updates the version. The helper **is** whitelisted (`settings.local.json:137`). Precedent: `aitask-trail` stores output via `ait artifact`. |
| **Chatlink bug intake** (`aidocs/chat/`, `aitask-explorechat`) | chat adapters model attachments; `max_attachment_bytes` is 8 MiB (`chat/capabilities.py:51`) | Intake writes only `message.text` to `bug_report.md` (`chatlink/intake.py:~266`); nothing downloads attachments; the agent sandbox image holds "only the runtime tier (bash, python3, git, node, …)" (`chatlink_sandbox.md:18`), so no ffmpeg | The most valuable integration: a recording posted with a chat bug report could become sheets on the created task. Needs downloading, ffmpeg in the sandbox, and `ait attach` in the payload flow. |
| **AppLink** (`aidocs/applink/`) | phone-to-workstation channel | inbound WebSocket frames are capped at 64 KiB (`applink/server.py:52`); push frames at 2 MiB (`applink/pusher.py:57`); no upload verb exists in any permission profile | Can't carry a recording from the phone as designed. A phone upload would need a new verb, so it is a protocol change, not glue. |
| **Shadow-agent pattern** (`aidocs/framework/shadow_agent.md`) | capture script, then a context script that prints paths in a fixed format, then a thin skill; the launcher passes IDs, not content | — | The template for turning the skill into a framework feature: keep preprocessing in scripts, have the skill read paths. |
| **Extension points** (`aidocs/framework/aitasks_extension_points.md`, `skill_authoring_conventions.md`) | rules for a framework skill | each helper script a skill calls needs **5 whitelist entries** (Claude settings, Codex rules, three seed copies); ports to `.agents/skills` and `.opencode/skills` | **Done at promotion:** `aitask_screen_recording.sh` is in all 5 touchpoints and the 3 wrappers were generated with `aitask_audit_wrappers.sh`; `aitask_skill_verify.sh` reports parity clean. Still open (E9): other agents read images differently. Codex has `view_image` (one path); OpenCode's read supports images (`aidocs/codeagents/*_tools.md`). |

---

## 4. Expansion candidates, ranked

Value is judged against the two stated uses: bug reports and implementing design
animations. Effort assumes the existing CLI structure.

| # | Expansion | Value | Effort | Depends on / risk | How to test |
|---|---|---|---|---|---|
| E1 | **Timestamped transcript** for narrated recordings (whisper.cpp `-oj` + Silero VAD), merged into `timeline.tsv` and the summary | high for bug reports | M | model download (about 142 MiB); keep it optional and detected; never `-nt` | a synthetic clip with TTS audio at known times; assert segment times ±0.5 s; a silent clip yields no text (VAD) |
| E2 | **Triage rows**: freeze, black and silence intervals in the bug timeline; black frames always kept | high | S | none (ffmpeg filters) | synthetic frozen and black spans at known times |
| E3 | **Wall-clock + logcat merge**: confidence ladder, a `--recorded-at` flag, `--log logcat.txt` (epoch,usec) producing interleaved rows | high for Android bugs | M | the meaning of creation_time varies by recorder; label the confidence | a fixture log with known epochs; assert interleaving order |
| E4 | **`frame` drill-down command**: exact ms, optional crop, full resolution; ms-named files; `cap_hit` in `run.json` | medium | S | none | extract at a known pts and compare with a synthetic frame |
| E5 | **Full-screen push/slide curves**: shift estimation by 1-D profile matching or phase correlation between a frame and S/E, replacing the blend proxy | high for animations (common transition type) | M | stdlib-only is slow, so downscaled rows suffice | the bug fixture's push transition (FastOutSlowIn 300 ms) already exists; assert the curve and duration |
| E6 | **Separate opacity and position channels** for fade+move: template-track the element, read opacity from its interior | medium | M–L | needs an element template (ROI on the end frame) | synthetic fade+slide with independent curves |
| E7 | **Store outputs on a task**: `--attach-to t<N>` puts the sheets and timeline in `ait artifact` (whitelisted) | medium | S | 25 MB cap; keep raw video out | an integration test in a scratch repo |
| E8 | **Chatlink attachments**: download the video into the session spool, run `bug` mode, attach sheets to the created task | high (closes the chat bug-report loop) | L | ffmpeg in the sandbox; 8 MiB chat cap; sandbox policy review | a chatlink fake adapter with an attachment |
| E9 | **Validate on the other agents.** The framework promotion is done (helper, whitelists, thin wrappers). Run the skill under Codex, OpenCode and agy, and adapt how each reads the sheets (Codex `view_image` takes one path per call) | medium | S–M | per-agent image limits differ | a manual run per agent on a fixture recording |
| E10 | **OCR mode** for text-heavy bug frames | medium | M | OCR engine choice (RapidOCR vs tesseract) | synthetic frames with rendered text |
| E11 | **Sub-agent describers** for recordings over about 2 min | medium | S (skill text only) | context cost per sub-agent | eval with a long fixture |
| E12 | **Perfetto FrameTimeline** ingestion, to tell jank from design | low–medium | L | Android 12+; trace capture UX | fixture trace |
| E13 | **Opt-in Gemini "describe"** fallback | low | S | privacy (free-tier human review); 1 fps sampling | explicit consent flag only; a test that an env key alone does nothing |
| E14 | **Website documentation** for the skill: when to use each mode, capture tips, the measurement limits | medium (it's a user-facing skill) | S | `check_links.py` after editing | `hugo build` + `check_links.py` |
| E15 | **Dependency hint**: ffmpeg is not installed by `ait setup`. Have setup report missing ffmpeg/`magick` with per-OS install commands, or the wrapper print them | low–medium | S | don't make ffmpeg a hard framework dependency | a test that the hint appears when ffmpeg is absent from PATH |

**Suggested order:** E2 → E4 → E1 → E5 → E3 → E7, with E14/E15 alongside.
These are the cheap correctness wins first, then the narrated-bug and
push-transition gaps, then log alignment and task storage. E9 (other agents)
can run any time. E8 makes sense only once the skill has proved itself in daily
use.

## 5. Open questions

- Do narrated bug recordings actually occur in this workflow? That decides
  whether E1 comes before E5.
- Is the mobile app's animation code Compose (spring defaults) or mostly tweens?
  If springs dominate, extend the spring fit with initial velocity (interrupted
  animations) before E6.
- Should promoted outputs live as attachments (task-scoped, unversioned) or
  artifacts (versioned, whitelisted)? The artifact route avoids per-call
  permission prompts.
