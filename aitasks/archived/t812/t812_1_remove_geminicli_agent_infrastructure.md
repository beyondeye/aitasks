---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Done
labels: [geminicli, codeagents]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-26 12:05
updated_at: 2026-05-27 14:55
completed_at: 2026-05-27 14:55
---

## Context

First child of parent task t812 (remove all geminicli support from the
aitasks framework). Google is sunsetting Gemini CLI in favor of
Antigravity CLI (agy). t814 (sibling) will add agy support later,
mirroring the patterns this child removes. Detailed migration spec lives
at `aidocs/geminicli_to_agy.md`.

This child strips **geminicli from the code-agent identity layer**:
registries, detection helpers, model lookups, stats, monitor prompt
patterns, and TUI display labels. It does NOT touch skill rendering
(that's t812_2), nor setup/install (t812_3), nor docs (t812_4).

## Key files to modify

- `.aitask-scripts/lib/agent_string.sh` — remove the `geminicli` enum
  entry and `--cli-id` flag mapping (lines 28, 73, 85 in the inventory).
- `.aitask-scripts/aitask_resolve_detected_agent.sh` — drop `geminicli`
  from `SUPPORTED_AGENTS` (line 23).
- `.aitask-scripts/aitask_codeagent.sh` — delete
  `format_gemini_model_label()` and the geminicli invocation block
  (lines 147–276).
- `.aitask-scripts/lib/agent_model_picker.py` — drop the
  `models_geminicli.json` registration (lines 40, 285) and the gemini
  branch in the picker UI.
- `.aitask-scripts/stats/stats_data.py` — remove gemini model parsing
  and stats labels (lines 59, 251, 276, 451, 644, 681).
- `.aitask-scripts/monitor/prompt_patterns.py` — remove the empty
  `gemini` entry (line 39).
- `.aitask-scripts/settings/settings_app.py` — remove TUI display
  labels (lines 133, 2532, 2564).
- `.aitask-scripts/aitask_review_detect_env.sh` — drop gemini
  detection branch.
- `.aitask-scripts/aitask_add_model.sh` — drop gemini-registry
  manipulation cases.
- Delete `aitasks/metadata/models_geminicli.json` (active project's
  data) and `.aitask-data/aitasks/metadata/models_geminicli.json` if
  the data branch is in use.

## Reference files for patterns

- The **Codex CLI** is the closest analogue to agy (both use
  `.agents/skills/`, both have sandboxed execution). For each gemini
  removal, locate the corresponding codex branch — that's the pattern
  t814 will replicate when adding agy.

## Implementation plan

Follow the file list above, removing geminicli touchpoints one by one.
After all removals, verify nothing references geminicli:

```bash
grep -n 'geminicli\|format_gemini\|models_geminicli' \
  .aitask-scripts/lib/agent_string.sh \
  .aitask-scripts/aitask_resolve_detected_agent.sh \
  .aitask-scripts/aitask_codeagent.sh \
  .aitask-scripts/lib/agent_model_picker.py \
  .aitask-scripts/stats/stats_data.py \
  .aitask-scripts/monitor/prompt_patterns.py \
  .aitask-scripts/settings/settings_app.py \
  .aitask-scripts/aitask_review_detect_env.sh \
  .aitask-scripts/aitask_add_model.sh
# Expect: no output
```

## Verification

1. `shellcheck .aitask-scripts/aitask_*.sh .aitask-scripts/lib/*.sh` —
   no new warnings.
2. Each `tests/test_*.sh` that loads `agent_string.sh`,
   `agent_model_picker.py`, or `stats_data.py` passes (especially
   `test_stats*.sh`).
3. `ait codeagent --list` (or equivalent) shows no geminicli entry.
4. `ait monitor` opens without crashing on the missing gemini
   pattern entry.
5. `ait board` opens; stats per-agent breakdown does not crash.

## Final implementation notes — REQUIRED subsection

In the Final Implementation Notes section of this plan, include a
top-level subsection titled exactly:

```
### For t814 (add-agy): inverse instructions
```

Contents:
- **Files re-touched by agy:** repeat the file list with absolute
  line ranges where they were modified.
- **Pattern removed (with anchor example):** the shape of the
  geminicli code that was deleted (function name, enum entry).
- **Inverse instruction:** "to add agy: insert <pattern> at
  <location>, modeled on codex's <reference>".
- **Hidden coupling discovered during removal:** anything that
  surprised the implementer (e.g., golden regenerations triggered).

This subsection is the primary cross-task context for t814's planner.
