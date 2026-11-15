---
priority: medium
effort: high
depends: [t2278_4]
issue_type: feature
status: Ready
labels: [website, documentation, tui, screenshots, skills]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 5 of t2278 (docs TUI screenshot generator). The full design is in the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`; read "CLI and
skill" first. Children 1-4 delivered the marker grammar and check, scene specs,
both vector backends, crop and overlays, and `capture`, which writes a new
batch directory with a `manifest.json` on every run.

This child adds `preview` and `apply`, the skill that runs the autonomous pass,
the contributor docs, and then runs the pass on all 17 markers.

## `preview` and `apply`

- `preview --batch <id>` writes one HTML contact sheet from that batch only. It
  shows the batch id, each image, and each marker's page, alt and caption.
- `apply --batch <id>` requires the batch id; there is no "latest" default. A
  scene is applied only when all of these hold:
  1. the staged image still hashes to the manifest value;
  2. the destination file is in the state the manifest recorded (still absent,
     or the same hash); a file created or changed since is never overwritten;
  3. each of the scene's markers is still present byte-for-byte in its page.
     Markers are located by text, never by line number.
- For a passing scene it copies the image to the spec's `output:` and, in each
  page as it is on disk now, substitutes only the marker text with
  `{{< static-img src="imgs/<output>" alt="..." caption="..." >}}`. Every other
  edit made to that page during review is kept.
- A failing scene is left untouched (image and pages) and reported as
  `REFUSED:<scene>|<reason>`. `apply` exits non-zero when any scene was
  refused. A refused scene needs a new capture and a new review.

## Key Files to Modify

- `website/screenshots/cli.py`: `preview`, `apply`.
- `.claude/skills/aitask-docs-screenshots/SKILL.md` (new, static, Claude-only,
  no `.j2`, no Codex / OpenCode wrappers). Steps: stop if
  `website/screenshots/` is absent (the skill ships to user projects like
  every skill, where the tool does not exist) → run the check → for each
  marker without a scene spec, read the surrounding page text and write the
  spec → `capture --pending` → `preview --batch <id>` and show the user → on
  approval `apply --batch <id>` with the id the user reviewed → report any
  `REFUSED:` scene → `python3 check_links.py --build` and
  `python3 check_screenshots.py`. A re-capture after the review means the new
  batch is reviewed again before it is applied. The skill never commits.
- `.claude/settings.local.json`: a repo-local allow entry for
  `website/screenshots.sh`. Not in `seed/`; the tool does not ship.
- `website/content/docs/development/skills/`: a page for the skill, linked
  from that section's `_index.md` under framework-development skills.
- `aidocs/framework/docs_screenshots.md` (new): the design and contract record
  (grammar, scene spec, ownership rule, batch and apply rules, backends).
- `CLAUDE.md`: a "Read `aidocs/framework/docs_screenshots.md`" pointer and one
  line in the Website section.
- `website/README.md`: how to run the tool.
- `website/check_screenshots.py`: promote "marker whose scene has no spec" from
  a listed warning to a failure (child 1 landed it demoted).
- The 13 doc pages: markers replaced by `static-img` through `apply`.
- `website/static/imgs/`: the generated images.
- `tests/test_screenshots_apply.py` (new).

## Reference Files for Patterns

- `.claude/skills/aitask-docs-review/SKILL.md`: a static, Claude-only skill.
- `.claude/skills/aitask-screen-recording/SKILL.md`: a skill driving a tool.
- `aidocs/framework/skill_authoring_conventions.md`: read before writing the
  skill. Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- `tests/test_helper_whitelist_coverage.sh`: it scans skills for
  `.aitask-scripts/aitask_*.sh` paths only, so a `website/` script path needs
  no seed allowlist entry; confirm the test still passes.
- `website/content/docs/development/skills/_index.md`: the page list.
- `aidocs/framework/documentation_conventions.md` and
  `aitasks/metadata/doc_update_guide.md`: prose rules for the new page and for
  alt / caption text.

## Implementation Plan

See `aiplans/p2278/p2278_5_skill_preview_apply_and_autonomous_pass.md`. Before
`apply` touches any page, run `git status -- website/` and stop on a page with
in-flight edits from another task.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with `apply`
  tests for: a staged image changed after capture, a destination created after
  capture, a destination modified after capture, and a marker edited after
  capture (each refused, nothing written for that scene); an unrelated edit
  elsewhere in the same page survives a successful apply; two captures produce
  two batches.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/test_helper_whitelist_coverage.sh` and
  `bash tests/test_release_tarball.sh` pass.
- `python3 website/check_screenshots.py --strict` exits 0: no unresolved
  marker.
- `cd website && python3 check_links.py --build` passes.
- Each generated image is viewed on the local Hugo server (`./serve.sh`).
- Suggest separate tasks to port the skill to Codex CLI and OpenCode.
