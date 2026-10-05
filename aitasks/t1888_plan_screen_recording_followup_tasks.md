---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Implementing
labels: [claudeskills, skills, task-planning]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1887
implemented_with: claudecode/opus5_5
created_at: 2026-10-04 15:48
updated_at: 2026-10-05 17:14
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

> **✉ note:t1887** id=2026-10-05T06:34:23Z.d4d8a16b65914745c973a301 from=t1887 at=2026-10-05T06:34:23Z base=95f0394cb4e9467ef389a5fbe7d5c7eaeded2ce6 base_branch=main dirty=no host=omg16
>
> | Another user request for the follow-up set (2026-10-05): a visual frame picker,
> | HTML+JS, for choosing which animation frames go to the code agent. Advisory
> | context for planning; please turn it into a task (or a child) alongside the
> | `frames` / `sheet` items from the previous note.
> | 
> | ## Requested flow
> | 
> | 1. The skill activates and runs frame extraction into a temporary directory.
> | 2. The agent asks whether the user wants to pick frames.
> | 3. If yes, it runs a helper that builds an HTML+JS page and opens it.
> | 4. The user selects a subset visually, copies the selection, and pastes it into
> |    the code-agent window.
> | 
> | ## Reference implementation (another repository)
> | 
> | The user pointed at `tools/verification/screenshot-review-gallery.sh` in
> | project `thinking_app`. Resolve it with `./ait projects resolve thinking_app`
> | and introduce it as `thinking_app#443`; I read it at commit 215e9e4. What it
> | does:
> | 
> | - A bash front end and a Python builder (`screenshot-review-gallery.py`, about
> |   1300 lines) write one self-contained static `<out>/index.html`. There is no
> |   server; `--open` opens it via `xdg-open`.
> | - Input images are copied and hashed into `<out>/src/` before anything is
> |   derived, so a concurrent rewrite can't mix versions. The output directory is
> |   owned and cleaned through a ledger.
> | - Per-card reviewed ticks and notes live in `localStorage`, keyed by a
> |   fingerprint of the compared bytes, so a rebuild with new pixels starts clean.
> |   All storage access is wrapped in try/catch.
> | - Filters, and a "Copy all notes" button that uses
> |   `navigator.clipboard.writeText`. When the clipboard is unavailable it shows
> |   the text instead, so the user can copy it by hand.
> | 
> | ## Design points for the task (suggestions, not decided)
> | 
> | - **Run it as a subcommand of the existing helper.** Something like
> |   `aitask_screen_recording.sh pick <frames-dir|run-dir> [--open]`; a
> |   subcommand needs no new whitelist touchpoints (a new `.sh` would need all 5).
> |   Encapsulate the opener per platform (`xdg-open` / macOS `open`) per
> |   `aidocs/framework/shell_conventions.md`.
> | - **What gets copied: a text block, not images.** A paste-ready list of the
> |   absolute paths of the selected frames, with timestamps, Δms and an optional
> |   per-frame note. The agent then reads those paths. This works for every agent
> |   (Codex `view_image` takes paths).
> | - **What the agent does with it:** read those frames, and optionally build a
> |   sheet of just the selection with the `sheet` subcommand from the previous
> |   note.
> | - **Picker features worth considering:**
> |   - a thumbnail grid with time and Δms labels; click and shift-click range
> |     selection; keyboard navigation; a large preview;
> |   - optionally, drag a rectangle on a frame to emit `--roi X,Y,W,H` in source
> |     pixels (the summary already prints the frame→source scale);
> |   - first and last selected frame → `--window A-B`, for a precise anim re-run.
> | - **No display** (SSH, remote or web sessions): the opener fails. Print the
> |   page path and fall back to the agent's own selection rather than failing the
> |   skill.
> | - **The SKILL.md question** ("pick frames?") is an AskUserQuestion. Check the
> |   AskUserQuestion rules in `aidocs/framework/skill_authoring_conventions.md`,
> |   and the mapping in the other agents' wrappers (E9).
> | - **Tests:** test the builder's output contract (embedded frame manifest, paths,
> |   labels) from Python. Whether the selection/clipboard JS needs a node-based
> |   test is the task's call.
> | - **Docs:** per the previous note, the website page gets a how-to for "pick
> |   frames visually and hand them to the agent".

> **👁 note:read** id=2026-10-05T06:53:09Z.6e3877d53bd0245f4467ebfe by=t1888 at=2026-10-05T06:53:09Z mode=explicit ids=2026-10-04T13:40:37Z.59d8b1c842dbce30ba80a069,2026-10-05T06:34:23Z.d4d8a16b65914745c973a301

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-05T14:14:28Z status=pass attempt=1 type=human
