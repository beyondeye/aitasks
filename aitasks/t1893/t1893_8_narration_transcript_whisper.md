---
priority: medium
effort: medium
depends: [t1893_7]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

Review item E1. The user said narrated bug recordings occur **occasionally**
(2026-10-05), so this is kept, but ordered after the push/slide curves
(t1893_7). A timestamped transcript lets the agent line up what the reporter
*said* with what the screen *showed*.

## Key files

- `video_prep.py`:
  - bug mode's `--extract-audio` flag (which writes `audio.wav`);
  - timeline and summary writing;
  - `run.json`.
- `vp_core.py`: pure parsing and merging of the whisper JSON.

## Scope and acceptance

1. **Optional and detected, never installed silently.**
   - Run only when `whisper-cli` is on PATH and a model file is found, through a
     flag (e.g. `--whisper-model PATH`) or an environment variable.
   - When either is missing and the clip has audio, the summary says how to
     enable transcription.
   - No auto-download, no `ait setup` install.
   - A separate helper script for fetching models, if one is added, needs the
     5-touchpoint whitelist checklist.
2. Audio: `ffmpeg -i in -ar 16000 -ac 1 -c:a pcm_s16le audio.wav`.
3. Transcription: `whisper-cli -m <model> -f audio.wav -oj --vad -vm <silero model> --prompt "<product vocabulary>"`.
   - Use `-ojf` if token-level timestamps are needed.
   - **Never `-nt`**, which drops timestamps.
   - A `--vocab` flag (or similar) feeds the initial prompt.
4. Merge the segments into `timeline.tsv` as `speech` rows (start, end, text) and
   into the summary. Associate each segment with the nearest picked frames
   (within ±1–2 s).
5. End the summary with a **Heard / Saw / When / Expected** checkpoint that cites
   frame files, for the agent and user to confirm.

## Tests

- Merge logic against a **fixture whisper JSON**, so no whisper install is
  needed. Assert the segment times, the merge order with frame picks, and the
  checkpoint content.
- Missing `whisper-cli` or model: the hint appears, and there is no failure.
- An optional live test, skipped unless `whisper-cli` and a model are present: a
  silent clip yields no text with VAD on.

## Facts (verified 2026-10-05 against the ggml-org/whisper.cpp source and README)

- **Binary.** `whisper-cli`; `main` was renamed on 2024-12-20.
- **Flags:**
  - `-m` (default `models/ggml-base.en.bin`);
  - `-f`, and `-l` (default `en`);
  - `-oj`, and `-ojf` (adds per-token timestamps and turns token timestamps on);
  - `-nt` ("do not print timestamps");
  - `--prompt` (at most n_text_ctx/2 tokens).
- **VAD.** `--vad` and `-vm/--vad-model`. Defaults:
  - threshold `-vt` 0.50;
  - min speech `-vspd` 250 ms;
  - min silence `-vsd` 100 ms;
  - pad `-vp` 30 ms.
- **Silero VAD model.** The current README uses **`ggml-silero-v6.2.0.bin`**;
  v5.1.2 still exists. Files are hosted at huggingface.co/ggml-org/whisper-vad.
- **Model sizes.** tiny.en 75 MiB, base.en 142 MiB, small.en 466 MiB.
- **Input.** The README says 16-bit WAV. The current CLI also decodes
  flac/mp3/ogg and resamples, but the 16 kHz mono PCM recipe above is the safe one.
- **Licence.** MIT.

## Docs

Add a how-to: "Narrated bug report". Cover:

- installing whisper.cpp and a model yourself, with the sizes;
- the vocabulary prompt;
- reading speech rows and the checkpoint;
- the privacy note: transcription stays local.

## Rules for every child of t1893

These apply to every child of t1893 (screen-recording skill expansion). They are
copied here so the task stands alone.

- **Website documentation is part of the deliverable.**
  - Update `website/content/docs/skills/aitask-screen-recording.md` (created by
    t1893_1) with a **how-to section for each use case this task enables**.
  - Follow `aidocs/framework/documentation_conventions.md`:
    - current state only, no "previously" prose;
    - agent-generic wording;
    - `{{< relref "/docs/..." >}}` for internal links.
  - After editing, run `cd website && python3 check_links.py --build` and
    `hugo build --gc --minify`.
- **Skill text.** Update `.claude/skills/aitask-screen-recording/SKILL.md` and
  `references/` to match.
  - The `.agents/skills/`, `.opencode/skills/` and `.opencode/commands/` wrappers
    are thin pointers to the Claude skill.
  - Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- **Tests.**
  - Use synthetic recordings with known ground truth, built with
    `tests/screen_recording_synth.py` (`Canvas`, `encode(..., vfr=)`, `tween`,
    `spring_progress`, `card_frames`, `bug_frames`).
  - Add them to `tests/test_screen_recording_cli.py` / `_core.py`. Skip when
    ffmpeg/ffprobe are absent, as the existing classes do with
    `@unittest.skipUnless(HAVE_FFMPEG, ...)`.
  - Run with `bash tests/run_all_python_tests.sh --test-dir <dir>`, or run the
    modules directly.
- **Whitelists.**
  - New *subcommands or flags* of `./.aitask-scripts/aitask_screen_recording.sh`
    need no whitelist changes.
  - **A new `.aitask-scripts/*.sh` helper that a skill calls must ship all 5
    whitelist touchpoints as an explicit deliverable**
    (`aidocs/framework/aitasks_extension_points.md`, "Adding a new helper
    script"):
    - `.claude/settings.local.json`
    - `.codex/rules/default.rules`
    - `seed/claude_settings.local.json`
    - `seed/codex_rules.default.rules`
    - `seed/opencode_config.seed.json`
- **Privacy and footprint** (t1887 decisions):
  - never copy a source recording into the repository;
  - never upload anything;
  - ffmpeg stays an optional runtime dependency that the skill reports, never an
    `ait setup` install.
- **Inferred values carry their provenance.**
  - Timestamps, coordinates and measurement windows are exported as exact only
    when the inputs prove them. Otherwise they are labelled (`heuristic`,
    `unknown`, "unverified"), or the export is disabled with a visible reason.
  - Where two requirements can conflict (keep everything vs a budget), state the
    overflow behaviour and add a fixture that forces the conflict.
  - Fixtures must not be chosen to match the assumption under test.
- **Check every documented flag** against the real `<mode> --help` output.
- **Facts below were verified on 2026-10-05** (sources named). Re-check any fact
  this task relies on before writing it into code or docs.
- Background: `aidocs/screen_recording_skill_design_review.md` and the archived
  t1887 plan (`aiplans/archived/p1887_add_screen_recording_skill.md`). The
  parent t1893 records the decisions and the order.
