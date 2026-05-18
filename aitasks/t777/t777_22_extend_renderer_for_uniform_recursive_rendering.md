---
priority: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [aitask_pick]
created_at: 2026-05-18 08:53
updated_at: 2026-05-18 08:53
---

## Context

Prerequisite for t777_6 (PILOT pick conversion), t777_7 (task-workflow profile branches), and t777_8..t777_15 (per-skill conversions). Adds the dep-walker that follows markdown references from a rendered skill into the per-profile snapshot, so cross-skill composition does not leak the templating model.

Discovered during t777_6 verify-pass on 2026-05-18. The user-confirmed render model is **uniform recursive rendering**: ALWAYS render every referenced `.md` file into the per-profile dir, even if the file has no profile keys. Files without Jinja markers pass through as an identity transform. This removes the audit/classification step entirely and makes future drift self-healing.

## Depends on

- t777_21 (closure + audit) — provides the test corpus.

## Render model to implement

When `ait skill render aitask-pick --profile fast --agent claude` runs:

1. Render entry-point template `.claude/skills/aitask-pick/SKILL.md.j2` → `.claude/skills/aitask-pick-fast-/SKILL.md`.
2. Scan output for markdown references matching `(\.claude|\.agents|\.gemini|\.opencode)/skills/[^/]+/[^/]+\.md`.
3. For every reference, render the source file through minijinja with the same `(profile, agent)` context (identity transform when no Jinja markers).
4. Write to per-profile sibling location: `<target_root>/skills/<dir>-<profile>-/<file>.md` where `<target_root>` is determined by `--agent` (`.claude/skills` for claude, `.agents/skills` for codex, etc.).
5. Rewrite reference in calling file from `<root>/skills/<dir>/<file>.md` to `<target_root>/skills/<dir>-<profile>-/<file>.md`.
6. Recurse on newly rendered references with cycle detection (visited set keyed on source path).

End result: per-profile snapshot is self-contained — entry-point skill plus every transitive `.md` lives under the per-profile dirs.

## Key Files to Modify

- `.aitask-scripts/aitask_skill_render.sh` — main driver; add dep-walk loop.
- `.aitask-scripts/lib/skill_template.py` — make Jinja loader path-agnostic for cross-skill includes; or move the reference-discovery + path-rewrite logic into a sibling helper.
- `.aitask-scripts/aitask_skill_verify.sh` — extend to walk the dep graph for every authoring template.
- Tests under `tests/` — golden-file regression suite.

## Decisions to settle (mark in plan)

- **Entry-point template extension convention.** Use `.md.j2` for entry-point templates only (resolves stub/template collision in same dir). Referenced procedures keep `.md`. The renderer treats every `.md` as a Jinja template regardless.
- **Skip-list for path scanning.** Probably none needed (identity transform is safe for docs like `stub-skill-pattern.md`). Re-evaluate during impl.
- **Skip-if-fresh semantics.** Any stale leaf in the dep closure invalidates the entire chain.

## Implementation Plan

1. Reference-discovery regex implemented + unit-tested (positive + negative cases — anchored only on `<root>/skills/...`).
2. Path-rewrite function implemented + unit-tested.
3. Cycle detection via visited set (test fixture: synthetic A↔B refs).
4. Integration test: tiny synthetic skill `_test-uniform-render-/` with one reference, asserts the per-profile sibling tree shape.
5. Wire dep-walker into `aitask_skill_render.sh`.
6. Extend `aitask_skill_verify.sh` to dep-walk.
7. Add depends `[t777_22, t777_7]` to t777_8..t777_15 task files (one-line metadata edits — handled here so subsequent conversions are correctly sequenced).

## Verification

1. New tests under `tests/` (regex unit tests, path-rewrite unit tests, cycle test, synthetic integration test) all pass.
2. `./ait skill verify` exits 0 on synthetic fixture with cross-references.
3. Per-profile sibling dirs are properly self-contained (no references to un-suffixed source dirs).

## Notes for sibling tasks

- Once this lands, t777_7 can author the actual profile-branch edits in `task-workflow/` files, and t777_6 (PILOT) can run the staged-rename conversion using the full infrastructure.
- Document the convention in `.claude/skills/task-workflow/stub-skill-pattern.md` so per-skill conversions in t777_8..15 mirror it exactly.
