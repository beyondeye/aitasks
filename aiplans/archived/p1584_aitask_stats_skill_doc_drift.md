---
Task: t1584_aitask_stats_skill_doc_drift.md
Base branch: main
Output branch: main
---

# Plan: t1584 — aitask-stats skill doc drift (closed: already fixed)

## Outcome

No code change. The pick-time audit (2026-11-15) found every defect listed in
the task already fixed by **t1544_6** (commit `28045f1a9`, "Document the backlog
stats surfaces and fix the stats docs"). It edited the same three skill files
this task names. The user chose "Archive as already fixed".

## Evidence (re-derived from the current code, per the task's suggested fix)

| Defect | Current state |
|---|---|
| `.claude/skills/aitask-stats/SKILL.md` CSV Export lists 7 columns | It lists 12 columns, `date, day_of_week, week_offset, task_id, labels, issue_type, task_type, implemented_with, codeagent, llm_model, created_at, category`. That is identical to the `write_csv` header (`.aitask-scripts/aitask_stats.py:728-745`) and to the 12-field `csv_rows.append` producer (`.aitask-scripts/lib/stats_data.py:1373-1388`). |
| Options list omits `-w/--week-start` | It is present. The Options list (`-d`, `-w`, `-v`, `--csv`, `--backlog-weeks` default 8 max 99, `--csv-backlog`, `-h`) matches `./.aitask-scripts/aitask_stats.sh --help` and `parse_args` (`aitask_stats.py:186-227`). |
| Report-sections list stops at 7 | All 13 sections are listed. They are in the order `render_text_report` prints them: Summary, Backlog Level, Backlog Net Flow, Daily, Day of Week, Pipeline Timing, Label weekly, Label day-of-week, Task Type, Issue type per Label, Code Agent, LLM Model. `render_verified_rankings` follows them (`aitask_stats.py:829`). |
| `.agents/` and `.opencode/` copies diverged (md5) | The md5s differ by design: both files are thin wrappers that point to the `.claude/` source of truth. They are not copies of it. Their `## Arguments` line already lists every current flag. `.opencode/commands/aitask-stats.md` `@`-includes the `.claude/` file directly. `./.aitask-scripts/aitask_skill_verify.sh` returns `OK (15 template(s) verified across 3 agents, 4 stub surfaces; wrapper parity clean)`. |

Commands used:

```bash
git log --oneline -5 -- .claude/skills/aitask-stats/SKILL.md .agents/skills/aitask-stats/SKILL.md .opencode/skills/aitask-stats/SKILL.md
diff .claude/skills/aitask-stats/SKILL.md .agents/skills/aitask-stats/SKILL.md
diff .claude/skills/aitask-stats/SKILL.md .opencode/skills/aitask-stats/SKILL.md
sed -n 725,748p .aitask-scripts/aitask_stats.py
sed -n 1373,1388p .aitask-scripts/lib/stats_data.py
./.aitask-scripts/aitask_stats.sh --help
./.aitask-scripts/aitask_skill_verify.sh
```

## Risk

No change ships, so there is nothing to evaluate. The `risk_evaluated` gate is
recorded as `skip` (evaluated, not applicable).

## Step 9 (Post-Implementation)

Current-branch mode, no task branch, nothing to merge. Archive with
`./.aitask-scripts/aitask_archive.sh 1584`.

## Final Implementation Notes

- **Actual work done:** I audited the four listed defects against the current
  script and skill trees. All of them were already resolved by t1544_6. No files
  were edited.
- **Deviations from plan:** The task expected a doc fix, but the fix had already
  landed in t1544_6, which the task body itself names as the owner of this
  documentation.
- **Issues encountered:** None.
- **Upstream defects identified:** None.
