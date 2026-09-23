---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [codeagent, models, skills]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1865
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-09-23 00:14
updated_at: 2026-09-23 16:58
---

## Origin

Spawned from t1865 during Step 8b review.

## Upstream defect

- `.claude/skills/aitask-add-model/SKILL.md:117-128` — the Step 5 "Manual review
  needed" block names `tests/test_brainstorm_crew.py` (which does **not** need
  review on a promotion) and omits `.aitask-scripts/lib/roadmap_run.py` and
  `website/content/docs/tuis/syncer/_index.md` (which do).
- `aidocs/framework/model_reference_locations.md` — tags
  `tests/test_brainstorm_crew.py` as `needed_for_promote`; it is not. Its §4
  entry for `.aitask-scripts/aitask_brainstorm_init.sh` also no longer
  corresponds to any model reference in that file. **t1341 already owns this
  file** and received a note with these findings on 2026-09-22 — this task
  should NOT duplicate that work; the doc half is listed here only as the shared
  root cause.

## Diagnostic context

t1865 promoted `claudecode/opus5_5` to the operational default. A full-repo
sweep run during its planning established, statically and then empirically:

- `tests/test_brainstorm_crew.py` never reads the shipped config.
  `TestGetAgentTypes.FULL_DEFAULTS` is written into a tmpdir by
  `_write_full_config`, and every `get_agent_types` call in the file passes
  `config_root=Path(self.tmpdir)`, so the assertions read back what the test
  itself wrote. t1865 promoted the defaults, left the file untouched, and it
  stayed green. It is a fixture, not a promote-blocking suite.
- `.aitask-scripts/lib/roadmap_run.py` carried a second hardcoded
  `claudecode/opus5` default (the `run()` keyword default and the
  `--agent-string` argparse default) that `promote-default-agent-string` does
  not patch. `.claude/skills/aitask-backlog-roadmap/SKILL.md` invokes the driver
  with no `--agent-string`, so a published roadmap artifact's
  `generator.agent_string` silently retained the superseded model across the
  previous promotion. t1865 fixed the two lines; the skill's review block still
  does not mention the file.
- The file that actually goes red on a promotion is `tests/test_codeagent.sh`
  (its fixture installs `seed/codeagent_config.json` as the project config).
  The block does name it — that entry is correct and should stay. t1865
  converted it to the t1318 derive idiom, so a future promotion should no longer
  break it; the entry's wording may want updating to reflect that.

## Suggested fix

Correct the Step 5 block in `.claude/skills/aitask-add-model/SKILL.md`: drop the
`tests/test_brainstorm_crew.py` line, add `.aitask-scripts/lib/roadmap_run.py`
and `website/content/docs/tuis/syncer/_index.md`, and re-check the
`tests/test_codeagent.sh` wording now that it derives.

Consider whether the block should stop being a hand-maintained prose list at
all. It is a second copy of `model_reference_locations.md`'s
`needed_for_promote` set and has now drifted from reality independently of it —
generating it from the audit doc, or replacing it with a pointer, would remove
the duplication that caused this.

Per CLAUDE.md, a skill change lands in the Claude Code version first; spawn
separate tasks for the Codex CLI / OpenCode ports if their trees carry the same
block.

## Coordination

Depends on nothing, but overlaps t1341 (which refreshes the audit doc). If t1341
runs first, re-check whether its refreshed doc makes the generate-from-doc option
cheap enough to prefer.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-23T13:58:22Z status=pass attempt=1 type=human
