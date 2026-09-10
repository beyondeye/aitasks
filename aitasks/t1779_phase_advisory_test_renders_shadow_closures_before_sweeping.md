---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [shadow, testing]
gates: [risk_evaluated]
anchor: 1771
followup_kind: upstream_defect
created_at: 2026-09-10 12:15
updated_at: 2026-09-10 12:15
---

## Origin

Spawned from t1771 during Step 8b review.

## Upstream defect

- `tests/test_shadow_phase_advisory.sh:149-159` — layer 2 (the capability-list and refusal sweep) globs the rendered shadow closures (`.claude/skills/aitask-shadow-*-/SKILL.md`, `.agents/…`, `.opencode/…`) and reads whatever is on disk, without rendering them first. The rendered dirs are gitignored, so on a fresh checkout the sweep degrades to a single `rendered closures were found` FAIL, and on a working checkout it tests **stale** renders: `tests/test_skill_render_aitask_shadow.sh` Test 4 re-renders only the `fast` profile, so the `-default-` / `-remote-` closures can be a day old.

## Diagnostic context

While landing t1771 (a new sub-procedure `task-summarize.md` added to the `CAPABILITIES` array), the sweep reported 4 failures — `all 8 capabilities still dispatched (expected '0', got '1')` for every `-default-` closure across the three agent trees — although the source template and the `fast` closures were correct. Re-rendering every profile × agent with `./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile <p> --agent <a>` made it 55/55. The test was therefore measuring the age of gitignored artifacts, not the property it exists to prove.

`tests/test_shadow_disposition_surfaces.py` already does this correctly: `render_shadow_variant()` re-renders the closure it inspects (with `--force`) precisely because "rendered dirs are gitignored, so they cannot be assumed to exist — the guard renders them itself rather than silently checking nothing", and keeps a `test_rendered_closure_is_present` negative control.

## Suggested fix

Before the layer-2 glob, render every `(profile, agent)` closure the sweep is about to read (the profiles under `aitasks/metadata/profiles/*.yaml` × `claude codex opencode`), or at minimum the three profiles shipped, via `aitask_skill_render.sh … --force`; keep the existing "rendered closures were found" assertion as the negative control. Mirror the pattern in `tests/test_shadow_disposition_surfaces.py`. Note the render step writes to disk (gitignored), as Test 4 of the render test already does.

## Verification

- On a checkout where `.claude/skills/aitask-shadow-default-/` has been deleted, `bash tests/test_shadow_phase_advisory.sh` passes instead of failing on `rendered closures were found`.
- Add a new `.md` to `CAPABILITIES` without re-rendering by hand: the sweep sees it in every closure on the first run.
