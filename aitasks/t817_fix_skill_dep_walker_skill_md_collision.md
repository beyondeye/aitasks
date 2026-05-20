---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-20 11:31
updated_at: 2026-05-20 11:36
---

## Origin

Spawned from t777_11 (convert aitask-qa to template + stubs) during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/skill_template.py:146` — `discover_refs` / `SHORT_REF_RE`
matches a bare `SKILL.md` token in prose and (when it resolves to a real file)
enqueues it as a closure node. For a templated skill whose `SKILL.md` is a stub,
a procedure file's prose mention of `SKILL.md` makes the walker render the stub
into `<skill>-<profile>-/SKILL.md`, silently overwriting the rendered
entry-point (target-path collision in `walk_closure`). The existence-based
false-positive filter cannot catch this because the stub file genuinely exists.

## Diagnostic context

During t777_11, `aitask-qa` was the first per-skill conversion with its own
procedure-file closure (6 sibling `.md` files). Each procedure file's header
said "Referenced from Step N of the main SKILL.md workflow." The first closure
render wrote the **stub** content into `aitask-qa-<profile>-/SKILL.md` instead
of the rendered template. Root cause: the walker's `SHORT_REF_RE` matched the
bare `SKILL.md` token in those headers; the token resolved to the real stub
file `.claude/skills/aitask-qa/SKILL.md`; the walker enqueued it; and
`_target_path_for(stub)` collided with the entry-point target
`<skill>-<profile>-/SKILL.md` — last write (the stub) wins.

t777_11 worked around it by rewording all 6 procedure-file headers to drop the
bare `SKILL.md` token ("the main workflow"). But any future templated skill
with its own procedure files that mention "SKILL.md" in prose will hit the
same silent overwrite.

## Suggested fix

In `walk_closure` (`.aitask-scripts/lib/skill_template.py`), either:
- skip a discovered ref whose computed target path equals the entry-point
  target (`entry_target`), or
- raise / warn on any target-path collision in the closure plan (two distinct
  sources writing the same target path) instead of letting the last write win
  silently.

Add a regression test under `tests/test_skill_render_uniform.sh` covering a
skill whose procedure file mentions the skill's own `SKILL.md` in prose.
