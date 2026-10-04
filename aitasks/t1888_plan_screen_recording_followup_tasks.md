---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [claudeskills, skills, task-planning]
anchor: 1887
created_at: 2026-10-04 15:48
updated_at: 2026-10-04 15:48
---

Create the follow-up tasks that grow the `aitask-screen-recording` skill (added
in t1887), based on the expansion proposal in
`aidocs/screen_recording_skill_design_review.md`. This task's deliverable is
the set of well-formed tasks, not their implementation.

## Source material

- **§4 "Expansion candidates, ranked"**: E1–E15, each with value, effort,
  dependencies/risk and a test idea.
- **Suggested order:** E2 → E4 → E1 → E5 → E3 → E7, with E14/E15 alongside;
  E9 any time; E8 only once the skill has proved itself in daily use.
- **§2 "Ideas worth borrowing" / "Things to avoid"**: concrete ffmpeg filter
  expressions, thresholds and anti-patterns the tasks should cite.
- **§3 "In-repo resources"**: constraints of attachments/artifacts (25 MB
  caps), chatlink intake, applink and the extension points.

## What to do

1. **Resolve the open questions (§5) with the user first.** The answers
   reorder the list:
   - Do narrated bug recordings actually occur? This decides E1 vs E5 priority.
   - Is the target animation code mostly Compose springs or tweens? Springs
     first means spring-with-initial-velocity before E6.
   - Should outputs land as attachments or artifacts (E7)?
2. **Decide which candidates become tasks now** and which are postponed or
   dropped (E8 chatlink, E12 Perfetto and E13 Gemini are the likely deferrals;
   if E13 is kept, it must be strictly opt-in per file, never triggered by an
   API key in the environment). Read `aidocs/framework/planning_conventions.md`
   before choosing between one parent with children and independent tasks.
3. **Create the tasks**, anchored to t1887 (`--followup-of 1887`), with:
   - priority/effort taken from the review table;
   - `depends:` encoding the agreed order;
   - each task's acceptance criteria and the review's test idea (synthetic
     fixtures in `tests/screen_recording_synth.py` with known ground truth,
     like the existing tests);
   - for any new helper script: the 5-touchpoint whitelist checklist
     (`aidocs/framework/aitasks_extension_points.md`, "Adding a new helper
     script") as an explicit deliverable;
   - for E14 (website docs): `check_links.py` after editing.
4. **Include E9 (validate on Codex / OpenCode / agy).** The thin wrappers exist
   (generated with `aitask_audit_wrappers.sh`); it is the per-agent
   image-reading flow that is unverified. Codex `view_image` takes one path per
   call.
5. **Re-check the facts the review marks as research-pass claims** before
   writing them into task bodies: image-token formula and size limits, the
   Android `screenrecord`/logcat flags, whisper.cpp flags and model sizes.

## Done when

- Every kept candidate exists as a task with the fields above, and the
  dependency chain matches the order agreed with the user.
- Deferred or dropped candidates are listed, with the reason, in this task's
  final notes.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1887** id=2026-10-04T13:40:37Z.59d8b1c842dbce30ba80a069 from=t1887 at=2026-10-04T13:40:37Z base=af935c9b3edb5c5d5ffbf1dbffd7db27b053db1a base_branch=main dirty=no host=omg16
>
> | Additional user requirements for the follow-up set, relayed from the session
> | that wrapped t1887 (user conversation on 2026-10-04, after t1888 was created).
> | Advisory context for planning; facts about the code are as of af935c9b3.
> | 
> | 1. Image-sequence workflow: the user wants to produce frames, post-process them
> |    by hand (crop, annotate, delete), and then feed them to the LLM.
> |    - Today the helper only accepts a video.
> |    - Frame output is thinned and downscaled:
> |      - bug mode writes only the picked frames (`--max-frames`, `--view-size`
> |        default 1000 px);
> |      - anim mode writes the motion ±2 frames, capped by `--max-view-frames`
> |        (default 30) at `--view-size` 800 px.
> |    - Edited images can't be re-analysed; the timeline and fits come from the
> |      original video.
> |    - Two helper subcommands were proposed and the user agreed:
> |      a. `frames`: every native frame in a time range at full resolution, named
> |         by millisecond timestamp (overlaps E4 in the design review).
> |      b. `sheet`: labelled contact sheets built from any folder of images,
> |         including user-edited ones, with labels taken from the filename
> |         timestamps.
> |    - The user also asked, more broadly, to make manual preprocessing easy end
> |      to end. Consider a documented extract → edit → feed flow, keeping
> |      timestamps in filenames, and possibly an input mode that takes a folder of
> |      images (ordering and timing from filenames, or `--fps`) so bug-style review
> |      or anim measurement can run on a curated sequence. Plan these as tasks
> |      alongside E4.
> | 
> | 2. Documentation, current capabilities: the user wants everything v1 does
> |    documented on the aitasks website now, not deferred.
> |    - Make E14 an early, standalone task rather than an "alongside" item.
> |    - Existing skill pages live in `website/content/docs/skills/<skill>.md`, so
> |      the natural place is `aitask-screen-recording.md` there.
> |    - Include a how-to section per use case:
> |      - bug report from a recording;
> |      - implementing an animation from a prototype recording;
> |      - slowed capture with `--time-scale`;
> |      - narrowing analysis with `--crop-top` / `--roi` / `--window` / `--range`;
> |      - manual image-sequence preprocessing (once item 1 lands);
> |      - recording tips;
> |      - limits, and how to read the warnings.
> |    - Follow `aidocs/framework/documentation_conventions.md` (current-state
> |      only, generic agent-set prose, prefer relref) and run
> |      `website/check_links.py --build` after editing.
> | 
> | 3. Documentation, every follow-up feature: each task created from E1–E15 (and
> |    from item 1) should include website documentation for its feature in its
> |    acceptance criteria, with a how-to section for each use case it enables.
