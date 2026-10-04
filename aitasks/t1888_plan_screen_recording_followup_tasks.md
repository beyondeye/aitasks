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
