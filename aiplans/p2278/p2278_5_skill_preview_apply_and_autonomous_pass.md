---
Task: t2278_5_skill_preview_apply_and_autonomous_pass.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_5 — skill, preview/apply and the autonomous pass

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` ("CLI and
skill"). Read the archived plans of children 1-4, in particular child 2's
manifest schema and child 1's severity constant. Read
`aidocs/framework/skill_authoring_conventions.md` before writing the skill.

## Steps

1. **`preview --batch <id>`.** Read `manifest.json` only. Write
   `<batch>/preview.html`: the batch id as the heading, then per scene the image
   (relative `src`), its `output` path, the destination state ("new file" or
   "replaces existing"), and each marker's page, alt and caption. For a
   replaced image, show the existing one beside the new one. Print the path.

2. **`apply --batch <id>`.** No default batch. Phase one validates every scene
   and collects verdicts; phase two writes only passing scenes.
   - Validation per scene: staged image SHA-256 equals the manifest; destination
     state equals the manifest (`absent` and still absent, or the same
     SHA-256); each marker text occurs exactly once in its page (zero or more
     than one is a refusal).
   - Write per scene: copy the image to `website/static/imgs/<output>` (create
     parent directories); for each page, read it, replace the one occurrence of
     the marker text with `markers.render_static_img(marker)`, write it back.
     Read and write the page inside this step, not from a copy taken at
     capture time, so concurrent edits elsewhere in the page are kept.
   - Output: `APPLIED:<scene>` or `REFUSED:<scene>|<reason>` per scene
     (`image_changed`, `destination_created`, `destination_modified`,
     `marker_missing:<page>`, `marker_ambiguous:<page>`), then a count line.
     Exit non-zero if any scene was refused.
   - A scene with no markers (child 6's regeneration case) applies the image
     only.

3. **Tests, `tests/test_screenshots_apply.py`.** Scratch content / static /
   staging trees, hand-written manifests. One test per refusal reason, each
   asserting that neither the image nor any page of that scene changed; a mixed
   batch applies the passing scene and refuses the other; an unrelated edit
   made to a page after capture survives a successful apply; `apply` without
   `--batch` is an argument error; two `capture` runs create two directories.

4. **Skill, `.claude/skills/aitask-docs-screenshots/SKILL.md`.** Static, no
   `.j2`. Steps as in the task file. State in the skill that: it stops when
   `website/screenshots/` is absent; it writes a scene spec only for a marker
   that has none; it applies only the batch the user reviewed; it never
   commits; after a re-capture the new batch is reviewed again. Use
   `AskUserQuestion` for the approval. Run
   `./.aitask-scripts/aitask_skill_verify.sh`.

5. **Permissions.** Add an allow entry for `website/screenshots.sh` to
   `.claude/settings.local.json` in this repo only. Run
   `bash tests/test_helper_whitelist_coverage.sh` and
   `bash tests/test_release_tarball.sh`.

6. **Docs.** `aidocs/framework/docs_screenshots.md` (design and contract);
   CLAUDE.md pointer plus a Website-section line; `website/README.md` usage;
   `website/content/docs/development/skills/` page and `_index.md` entry.
   Run `python3 check_links.py --build` after the page edits.

7. **Run the pass.** `git status --short -- website/` first; stop on in-flight
   pages. Then `capture --pending`, `preview`, user review, `apply --batch`,
   both checks. Promote check class 2 (missing spec) to a failure via the
   constant child 1 named, and update its test.

8. **Port tasks.** Suggest (and on the user's yes, create) tasks to port the
   skill to Codex CLI and OpenCode.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- `python3 website/check_screenshots.py --strict` exits 0.
- `cd website && python3 check_links.py --build`.
- Every generated image viewed on the local Hugo server.

## Notes for sibling tasks

Record: the batch id that was applied; every `REFUSED:` outcome and its cause;
the user's comments on composite realism and the pinned look (child 8 reads
them).

Post-implementation: Step 9 of the task workflow.
