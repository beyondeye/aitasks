# Risk-Mitigation Follow-up Procedure

Proposes and (on confirmation) creates **risk-mitigation tasks** for the risks
identified by the Risk Evaluation Procedure (`risk-evaluation.md`). It has three
parts that run at three different points in the workflow:

1. **Design-in-planning** (read-only) — runs at the end of `planning.md` §6.1,
   right after the `## Risk` section is authored. It proposes candidate
   *before* / *after* mitigations, lets the user confirm, and records the chosen
   ones into the plan. **It creates nothing** (plan mode is read-only).
2. **Step 7 "before" creation** (post-approval) — runs from `SKILL.md` Step 7.
   It creates the confirmed *before* mitigations as **independent tasks the
   original depends on**, wires the blocking edge, and then stops the original.
3. **Step 8d "after" creation** (post-implementation) — runs from `SKILL.md`
   Step 8d. It creates the confirmed *after* mitigations as standalone
   follow-up tasks.

This mirrors the design/creation split used by the cross-repo procedures
(`planning-cross-repo.md` design + `cross-repo-child-assignment.md` creation):
the design decides and records to the plan; all mutations are deferred out of
plan mode to Step 7 / Step 8d. The offer is always **propose-and-confirm**
(never auto-create).

## Plan record format (the design/creation contract)

The design part appends a `### Planned mitigations` subsection **inside the
plan's `## Risk` section**, one line per confirmed mitigation:

```markdown
### Planned mitigations
- timing: before | name: <snake_name> | type: <issue_type> | priority: <p> | effort: <e> | addresses: <which risk> | desc: <one-line description>
- timing: after  | name: <snake_name> | type: <issue_type> | priority: <p> | effort: <e> | addresses: <which risk> | desc: <one-line description>
```

`timing` is `before` or `after`. The Step 7 creation reads the `before` lines;
the Step 8d creation reads the `after` lines. If the user confirms no
mitigations, **no `### Planned mitigations` subsection is written** (the creation
parts then find nothing and no-op). The design part also fills each `## Risk`
bullet's `→ mitigation:` placeholder with the planned `name` (the real task ID is
back-filled at creation time).

---

## Part 1 — Design-in-planning (read-only)

**Dispatched from `planning.md` §6.1, after the Risk Evaluation Procedure
authored the `## Risk` section.**

### Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The task being planned. |
| `task_file` | Path to the current task file. |
| `risk_mitigations_planned` | Threaded by `risk-evaluation.md`: `true` if either risk subsection lists ≥1 risk. |
| the `## Risk` section | The two-subsection block just written to the plan. |

### Return contract

Threads `risk_mitigations_confirmed` (`true` if the user confirmed ≥1
mitigation, else `false`) back into the workflow context. The actual mitigation
specs live in the plan's `### Planned mitigations` subsection — the creation
parts re-read them from there (plan mode is read-only, so nothing is created or
mutated here).

### Procedure

1. **Skip when there is nothing to mitigate.** If `risk_mitigations_planned` is
   `false` (no risks identified), set `risk_mitigations_confirmed = false` and
   return immediately — do not prompt.

2. **Propose candidate mitigations.** Re-read the plan's `## Risk` section. For
   the identified risks (either dimension — code-health or goal-achievement),
   propose concrete mitigations, each tagged with a timing:
   - **before** — an independent task that should run *before* the original is
     implemented to de-risk it (e.g. a spike/prototype to de-risk a
     goal-achievement concern, a characterization test to de-risk a code-health
     concern). The original will **depend on** it.
   - **after** — a post-implementation follow-up that hardens the result (e.g. a
     refactor to pay down structure debt, an added regression test).

   Present the proposed mitigations to the user as a plain-text numbered list
   (timing · name · what it does · which risk it addresses) **before** the
   prompt, then use `AskUserQuestion`:
   - Question: "The risk evaluation identified risks that could be mitigated by
     before/after follow-up tasks. Candidate mitigations were listed above. How
     would you like to proceed?"
   - Header: "Risk mitig"
   - Options:
     - "No mitigations" (description: "Skip — record no mitigations; proceed to plan approval")
     - "Create all proposed" (description: "Confirm every proposed mitigation as shown above")
     - "Let me choose which" (description: "Pick a subset of the proposed mitigations")

   - **"No mitigations":** set `risk_mitigations_confirmed = false` and return
     (do not write a `### Planned mitigations` subsection).
   - **"Let me choose which":** use a second `AskUserQuestion` with
     `multiSelect: true`, one option per proposed mitigation (label = `name`,
     description = timing + one-liner). The selected mitigations form the
     confirmed set. If the user selects none, treat as "No mitigations".
   - **"Create all proposed":** the confirmed set is every proposed mitigation.

3. **Record the confirmed set into the plan.** Append a `### Planned
   mitigations` subsection inside the `## Risk` section, one line per confirmed
   mitigation in the format shown at the top of this file. Then fill each
   `## Risk` bullet's `→ mitigation:` placeholder with the corresponding
   mitigation `name` (real IDs are back-filled at creation). Set
   `risk_mitigations_confirmed = true` and return.

   **No tasks are created and no frontmatter is mutated here** — the plan edit is
   the design output, persisted with the rest of the plan through the standard
   Save-Plan + Checkpoint gate.

---

## Part 2 — Step 7 "before" creation (post-approval)

**Dispatched from `SKILL.md` Step 7, after the risk-field write, only when the
approved plan has a `### Planned mitigations` subsection with ≥1 `before` line.**

### Input context

| Variable | Description |
|----------|-------------|
| `task_id` | The original task (e.g. `42` or `42_3`). |
| `task_num` | Numeric id for `aitask_update.sh` (the task's own id — for a child, the child id `42_3`). |
| `plan_file` | Path to the approved plan file. |
| `is_child`, `parent_id`, `active_profile` | Standard workflow context. |

### Return contract

Returns `risk_before_created` (`true` if ≥1 before-mitigation was created, else
`false`) plus `created_before_ids`. When `true`, the caller (`SKILL.md` Step 7)
stops the original task this session (revert to `Ready`, release lock, end
workflow) — see the Step 7 dispatch.

### Procedure

1. **Read the plan's planned mitigations.** Parse the `### Planned mitigations`
   subsection from `<plan_file>`; keep only `timing: before` lines. If there are
   none, set `risk_before_created = false` and return (the workflow continues to
   implementation normally).

2. **Create each "before" mitigation as an independent task.** For each before
   line, execute the **Batch Task Creation Procedure** (see
   `task-creation-batch.md`) with `mode: parent` (these are **independent tasks
   the original depends on — NOT children**; do not touch the parent's
   `children_to_implement`). Use the line's `name` / `type` / `priority` /
   `effort`; copy topical `labels` from the original task. Pass
   `followup_of: <task_id>` (the original task) so the mitigation anchors to the
   topic it protects. Description heredoc:

   ```markdown
   ## Origin

   Risk-mitigation ("before") for t<task_id>, created at Step 7 from the approved plan's risk evaluation.

   ## Risk addressed

   <the `addresses` field + the matching `## Risk` bullet, verbatim>

   ## Goal

   <the mitigation `desc`, expanded into what this task must accomplish to de-risk the original>
   ```

   Capture each created task's ID from the `Created: <filepath>` output.

3. **Wire the blocking edge (read-modify-write of BOTH list fields).** The
   original must now *depend on* every created before-mitigation, and each must
   be recorded in `risk_mitigation_tasks` (read by t884_5's force-reverify).
   Both `--deps` and `--risk-mitigation-tasks` **REPLACE** the full list, so read
   the current values first, append the new IDs, and write the full lists back —
   both in a single call:

   ```bash
   # Read current values from the original task frontmatter:
   #   depends:                -> <current_deps>
   #   risk_mitigation_tasks:  -> <current_mitig>   (absent => empty)
   ./.aitask-scripts/aitask_update.sh --batch <task_num> \
     --deps "<current_deps + created_before_ids>" \
     --risk-mitigation-tasks "<current_mitig + created_before_ids>"
   ```

   Pass comma-separated numeric IDs. Commit the task change via `./ait git`
   (the original task file lives on the aitask-data branch).

4. **Back-fill the plan's mitigation links.** Update the matching `→ mitigation:`
   entries (and the `### Planned mitigations` `name` lines) in `<plan_file>` to
   reference the real created IDs (e.g. `→ mitigation: t<new_id>`). Commit the
   plan via `./ait git`.

5. **Return.** Set `risk_before_created = true` and `created_before_ids` to the
   list of created IDs, and return to `SKILL.md` Step 7, which stops the original
   task for this session.

---

## Part 3 — Step 8d "after" creation (post-implementation)

**Dispatched from `SKILL.md` Step 8d, after Step 8c, only when the plan has a
`### Planned mitigations` subsection with ≥1 `after` line.** At this point the
original's code and plan files are already committed.

### Input context

Same as Part 2 (`task_id`, `task_num`, `plan_file`, `is_child`, `parent_id`,
`active_profile`).

### Return contract

Returns to the caller (`SKILL.md` Step 8d → Step 9). No workflow-stopping
behavior — "after" mitigations block nothing.

### Procedure

1. **Read the plan's planned mitigations.** Parse the `### Planned mitigations`
   subsection from `<plan_file>`; keep only `timing: after` lines. If there are
   none, return immediately (Step 8d is a no-op).

2. **Create each "after" mitigation as an independent follow-up task.** For each
   after line, execute the **Batch Task Creation Procedure** (see
   `task-creation-batch.md`) with `mode: parent`. Use the line's `name` / `type`
   / `priority` / `effort`; copy topical `labels` from the original. Pass
   `followup_of: <task_id>` (the original task) so the mitigation anchors to the
   topic it protects. Description heredoc:

   ```markdown
   ## Origin

   Risk-mitigation ("after") follow-up for t<task_id>, created at Step 8d after implementation landed.

   ## Risk addressed

   <the `addresses` field + the matching `## Risk` bullet, verbatim>

   ## Goal

   <the mitigation `desc`, expanded into what this follow-up must accomplish>
   ```

   Capture each created task's ID. Display: "Created risk-mitigation follow-up
   t<new_id>."

3. **Record in `risk_mitigation_tasks` (read-modify-write).** Append the created
   IDs to the original's `risk_mitigation_tasks` (it **REPLACES** — read current,
   append, write full list):

   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> \
     --risk-mitigation-tasks "<current_mitig + created_after_ids>"
   ```

   Commit the task change via `./ait git`.

4. **Back-fill the plan's mitigation links** to the real IDs (as in Part 2
   step 4) and commit the plan via `./ait git`. Return to the caller (proceed to
   Step 9).
