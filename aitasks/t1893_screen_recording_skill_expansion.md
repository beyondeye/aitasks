---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [claudeskills, skills, python, website]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Goal

Grow the `aitask-screen-recording` skill, which t1887 added. It has three parts:

- `./.aitask-scripts/aitask_screen_recording.sh`, with `info|bug|anim`;
- `.aitask-scripts/screen_recording/video_prep.py` and `vp_core.py`;
- `.claude/skills/aitask-screen-recording/`.

The work is driven by the ranked expansion list in
`aidocs/screen_recording_skill_design_review.md` §4 (E1–E15) and by the user's
requirements relayed in two notes on t1888. Those requirements are:

- an image-sequence workflow;
- website docs for current behaviour now, and docs in every follow-up;
- a visual HTML frame picker.

t1888 planned this set; its archived plan is `aiplans/archived/p1888_*`.

## Decisions made with the user (2026-10-05)

| Question | Decision |
|---|---|
| Do narrated bug recordings occur? | Occasionally. E1 (transcript) is kept, ordered after E5 (push/slide curves). |
| Compose springs or tweens? | Mixed or unsure. Add a low-priority spring-with-initial-velocity child after E5, independent of E6. |
| Where outputs land (E7) | A repo-root gitignored work dir `.aitask-screen-recording/`, managed like `.aitask-explain/` and `.aitask-shadow/`. Not attachments or artifacts. |
| Deferred | E6, E10, E11, E12, E13 (see below). |
| E8 (Chatlink attachments) | Not created here. It is owned by **t1165** Phase 3, which is gated on t1157_4; t1165 was sent a note. |
| Structure | One parent, with children using explicit dependencies. |

## Children and order

The main line is `1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 10 → 11`. It follows the
review's E2 → E4 → … order with these changes:

- E14 (docs) comes first, so every later task extends an existing page.
- The image-sequence cluster (3–6) sits where E4 was.
- E1 moves after E5.

The chain also serialises edits to `video_prep.py`, `SKILL.md` and the docs page.

Side branches:

- 9 (spring) depends on 7;
- 12 (other agents) depends on 5;
- 13 (dependency hints) depends on 1;
- 14 (retrospective) depends on 9, 11, 12 and 13.

| # | Child | Review item |
|---|---|---|
| 1 | Website docs for current capabilities | E14 |
| 2 | Triage rows: freeze / black / silence | E2 |
| 3 | `frames` subcommand: exact drill-down with geometry provenance | E4, note 1a |
| 4 | `sheet` subcommand for any image folder | note 1b |
| 5 | `pick`: visual HTML+JS frame picker | note 2 |
| 6 | Image-folder input mode for bug/anim | note 1c |
| 7 | Full-screen push/slide curves by shift estimation | E5 |
| 8 | Narration transcript with whisper.cpp | E1 |
| 9 | Spring fit with initial velocity | user decision |
| 10 | Wall-clock ladder and logcat merge | E3 |
| 11 | Repo work dir and `clean` | E7, redefined |
| 12 | Validate image reading on the other agents | E9 |
| 13 | Missing-dependency hints | E15 |
| 14 | Retrospective on the deferred candidates | planning conventions |

## Deferred or dropped (not created)

- **E6** (separate opacity and position channels): deferred by the user. M–L
  effort, and it needs an element template (ROI on the end frame).
- **E10** (OCR mode): deferred. The engine choice (RapidOCR vs tesseract) is open.
- **E11** (sub-agent describers for long recordings): deferred. It is skill text
  only; revisit when recordings over about 2 minutes actually occur.
- **E12** (Perfetto FrameTimeline): deferred. Low–medium value, L effort,
  Android 12+ only.
- **E13** (Gemini "describe"): deferred. Low value, and a privacy risk (free-tier
  human review; 1 fps sampling is useless for timing). If revived it must be
  strictly opt-in per file, never triggered by an API key in the environment.
- **E8**: belongs to t1165 Phase 3.

Child 14 re-evaluates these with usage evidence.

## Cross-cutting rules

These are copied into every child: docs how-to per feature, tests with synthetic
fixtures, the 5-touchpoint rule for new helper scripts, privacy, provenance
labelling, and a facts check.
