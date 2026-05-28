---
Task: t812_5_cleanup_pending_geminicli_aitasks.md
Parent Task: aitasks/t812_remove_gemini_support.md
Sibling Tasks: aitasks/t812/t812_1_*.md, aitasks/t812/t812_2_*.md, aitasks/t812/t812_3_*.md, aitasks/t812/t812_4_*.md
Archived Sibling Plans: aiplans/archived/p812/p812_1_*.md, p812_2_*.md, p812_3_*.md, p812_4_*.md
Worktree: (current branch — fast profile)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-05-28 08:20
---

# Plan: Cleanup pending geminicli-related aitasks (t812_5)

## Context

Final child of t812. After children 1–4 land, four pending backlog
tasks targeting geminicli-specific behavior need disposition:

- `aitasks/t343_geminicli_support_bug_planning_step_is_skipped.md`
- `aitasks/t344_seed_execution_permission_for_geminicli.md`
- `aitasks/t345_identifying_model_id_in_gemini.md`
- `aitasks/t401/t401_3_verify_detection_geminicli.md`

## ID alias note — "t814" → **t835**

The original t812 parent plan referenced the add-agy task as "t814".
It was actually created as `aitasks/t835_add_agy_antigravity_cli_support.md`.
Per t835's own description (lines 62-65), the inverse-instruction
subsection title `### For t814 (add-agy): inverse instructions` is
preserved verbatim across all t812 child plans — match by content, not
ID. When this plan says "create a child of t814", read as "create a
child of t835".

## Dispositions (verified 2026-05-28)

| Task | Disposition | Reason |
|------|-------------|--------|
| t343 | Close as obsolete | geminicli-specific planning-step skip bug (gitignored-path read failure); agy uses markdown skills + native sandbox — not applicable. |
| t344 | Close as obsolete | agy uses nsjail-sandboxed execution + global `~/.gemini/policies/`; no project-level exec-permission concern. |
| **t345** | **Migrate to a new child of t835** (`identifying_model_id_in_agy`) | Model-id detection is a real concern for agy and must be tested there. Rebrand the original geminicli framing for agy. |
| **t401_3** | **Migrate to a new child of t835** (`verify_detection_agy`) + remove from t401.children_to_implement | Detection verification must be done for agy, not geminicli. Rebrand the original geminicli test for agy. |

## Step-by-step

### Phase A — Create the two t835 children first

Both new children are created **before** closing the source tasks, so
each close-note can include a pointer to a real new task ID.

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 835 \
  --name identifying_model_id_in_agy \
  --priority medium --effort low \
  --issue-type bug \
  --labels codeagent \
  --desc-file <(cat <<'EOF'
## Context

Migrated from t345 (geminicli-era). Reliable model-id identification
was a non-obvious surface for geminicli — only the `cli_help` tool
gave a consistent answer. For agy (Antigravity CLI), the equivalent
surface must be identified and wired into the framework's detection
path.

## Original concern (t345 verbatim)

In gemini CLI the only reliable way to identify the current model id
was to call the `cli_help` tool. Need to update the task_workflow to
use a similarly reliable method for agy.

## Scope

1. Identify agy's reliable model-id surface (candidates: `agy --version`,
   a `cli_help`/`cli_info` equivalent, or `~/.gemini/settings.json`
   inspection). Test each in practice.
2. Wire the chosen method into `aitask_resolve_detected_agent.sh` and
   the Model Self-Detection Sub-Procedure so agy returns a valid
   `AGENT_STRING:agy/<name>` matching an entry in `models_agy.json`.
3. Ensure detection works headless (no interactive prompt required).

## Verification

- Launch agy in a test repo; run a workflow that triggers
  model-self-detection; confirm `implemented_with` is written
  correctly to the task frontmatter.
EOF
)
```

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 835 \
  --name verify_detection_agy \
  --priority medium --effort low \
  --issue-type test \
  --labels task_workflow \
  --desc-file <(cat <<'EOF'
## Context

Migrated from t401_3 (geminicli-era). t401_1 established
`.aitask-scripts/aitask_parse_detected_agent.sh` as the canonical
agent parser. This task verifies the procedure works end-to-end when
running from agy (Antigravity CLI), replacing the geminicli-targeted
verification.

## Verification Steps

1. Launch agy in this repository.
2. Run a workflow that triggers model-self-detection (e.g.,
   `/aitask-pick` on a test task, or manually invoke the Agent
   Attribution Procedure).
3. Confirm the script is called correctly:
   `./.aitask-scripts/aitask_parse_detected_agent.sh --agent agy --cli-id <model_id>`
4. Verify the output is a valid `AGENT_STRING:agy/<name>` matching
   an entry in `aitasks/metadata/models_agy.json`.
5. Check that `implemented_with` is written correctly to the task
   frontmatter.

## Key Files (anticipated)

- `.aitask-scripts/aitask_parse_detected_agent.sh` — script being
  verified for the agy code path.
- `.agents/skills/...` or agy-specific skill surface — Agent String
  section may need updating.
- `aitasks/metadata/models_agy.json` — agy models registry.

## Special Considerations

agy identifies its model differently from geminicli (see sibling
task `identifying_model_id_in_agy`). This verification assumes that
sibling has landed first; if not, escalate to its planner.
EOF
)
```

Parse `CREATED:t835_<N>:<path>` lines from each call to capture the
actual assigned IDs (referenced as `t835_<MODEL_ID>` and
`t835_<VERIFY_ID>` below).

### Phase B — Close source tasks

For each of t343, t344, t345, t401_3:

1. Append a brief obsolescence note to the task file's body. For t345
   and t401_3, include a pointer to the new t835 child ID.
2. `./.aitask-scripts/aitask_update.sh --batch <task_num> --status Done`
3. `./.aitask-scripts/aitask_archive.sh <task_num>` (handles git
   commit internally).

### Phase C — Update parent t401 for t401_3 closure

1. Edit `aitasks/t401_more_robust_self_detection_for_claude_code.md`:
   - Remove `t401_3` from `children_to_implement`
     (becomes `[t401_2, t401_4]`).
   - Add a short body note explaining the disposition (closure +
     pointer to new t835 child).
2. `./ait git add aitasks/t401_*.md`
3. `./ait git commit -m "ait: Drop t401_3 from t401 children after geminicli removal"`

## Verification

1. None of t343, t344, t345, t401_3 appear in `ait board` /
   `aitask_ls.sh -v` as Ready.
2. t343 and t344 are archived under `aitasks/archived/`; t345 and
   t401_3 are archived under `aitasks/archived/` AND their concerns
   live in new t835 children under `aitasks/t835/`.
3. `grep -rn 'geminicli' aitasks/ --include='*.md'` returns only
   sibling-task files (`t812*`, `t813*`, `t835*`) and archived
   files.
4. Parent t401's `children_to_implement` is `[t401_2, t401_4]` and
   the body contains the disposition note for t401_3.

## Step 9 (Post-Implementation)

Standard archival. Final Implementation Notes **must** include the
`### For t814 (add-agy): inverse instructions` subsection (even
though this child is primarily admin work — t814's planner may
benefit from the migrate/close decisions).

## Final Implementation Notes

- **Actual work done:**
  - **Phase A** — Created two new children of t835 (the add-agy task):
    - `aitasks/t835/t835_1_identifying_model_id_in_agy.md` (commit `4403f1d9`)
    - `aitasks/t835/t835_2_verify_detection_agy.md` (commit `6edeeb48`)
  - **Phase B** — Closed and archived four geminicli backlog tasks
    after appending obsolescence notes (t345 and t401_3 include
    pointers to their migrated t835 children):
    - t343 → `aitasks/archived/t343_*` (commit `511f92c1`)
    - t344 → `aitasks/archived/t344_*` (commit `d464dae7`)
    - t345 → `aitasks/archived/t345_*` (commit `1bf44477`)
    - t401_3 → `aitasks/archived/t401/t401_3_*` (commit `8c73eb78`)
  - **Phase C** — Parent t401's `children_to_implement` was
    automatically updated by `aitask_archive.sh` (now
    `[t401_2, t401_4]`); a disposition note pointing to t835_2 was
    added to t401's body (commit `82b56d1f`).
- **Deviations from plan:**
  - Original draft plan defaulted to "close all four as obsolete"; per
    user direction at the verify step, t345 and t401_3 were instead
    **migrated** to new t835 children. The plan file (this document)
    was updated to reflect the migration before implementation.
  - Phase C was simpler than planned: `aitask_archive.sh` removed
    t401_3 from `children_to_implement` automatically, so the manual
    edit was reduced to adding the human-readable disposition note.
  - Original plan's "t814" naming retained as a subsection title
    convention (per t835's own description, lines 62-65). Body text
    elsewhere uses "t835" with an alias note up top.
- **Issues encountered:**
  - `aitask_create.sh` uses `--type`, not `--issue-type` (one-off
    flag-name confusion; resolved on second invocation).
- **Key decisions:**
  - Both t835 children seeded with detailed Context and Scope
    sections referencing the migrated source task's framing, so
    t835's planner doesn't need to re-derive the concerns from the
    archived geminicli plans.
  - Disposition notes appended to each closed task body (rather than
    inserted in frontmatter) so the archived files remain readable
    standalone, and the obsolescence reason travels with the file
    forever.
- **Upstream defects identified:** None — but several pre-existing
  geminicli references in unrelated active tasks were noticed (out of
  scope for this cleanup): `t720_*`, `t369_*`, `t399/t399_2_*`,
  `t369/t369_4_*`, `t717/t717_5_*`. These are stale task descriptions
  and labels, not code defects. They warrant a separate light-touch
  cleanup task if desired.
- **Notes for sibling tasks:** This was the final t812 child. No
  further sibling work pending — t812 parent can archive once this
  child archives.

### For t814 (add-agy): inverse instructions

- **Migrated-to-t814 (now t835) task IDs:**
  - `t345 → t835_1_identifying_model_id_in_agy` — model-id detection
    surface for agy must be researched (candidates: `agy --version`,
    `cli_help`/`cli_info` equivalent, or `~/.gemini/settings.json`)
    and wired into `aitask_resolve_detected_agent.sh` + the Model
    Self-Detection Sub-Procedure.
  - `t401_3 → t835_2_verify_detection_agy` — end-to-end verification
    of agy detection through `aitask_parse_detected_agent.sh`
    (`--agent agy --cli-id <id>` → valid `AGENT_STRING:agy/<name>`
    matching `models_agy.json`). Depends on t835_1 landing first so
    the resolver has agy entries to match against.
- **Closed as obsolete (no migration):**
  - `t343` — geminicli planning-step skip bug (gitignored-path read
    failure); agy uses markdown skills + native sandbox, not
    applicable.
  - `t344` — geminicli exec-permission/project-level config issue;
    agy uses nsjail + global `~/.gemini/policies/`, no
    framework-installed local policy concern.
- **Hidden coupling discovered:**
  - t344's framing flagged that **project-level permission systems
    are silently ignored** by some agents in favor of global config
    (`~/.gemini/...`). agy uses `~/.gemini/policies/` globally —
    `ait setup` must NOT install local policy files for agy (per
    `aidocs/geminicli_to_agy.md`).
  - t345's framing flagged that geminicli's model-id surface was
    inconsistent — only `cli_help` was reliable. The migrated
    t835_1 child should evaluate agy's surface explicitly; do not
    assume `agy --version` is sufficient without practical testing.
