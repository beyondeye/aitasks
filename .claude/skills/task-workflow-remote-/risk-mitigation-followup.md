# Risk-Mitigation Follow-up Procedure

Proposes and (on confirmation) creates **risk-mitigation tasks** for the risks
identified by the Risk Evaluation Procedure (`risk-evaluation.md`). It has three
parts that run at three different points in the workflow:

1. **Design-in-planning** (read-only) — runs at the end of `planning.md` §6.1,
   right after the `## Risk` section is authored. It proposes candidate
   *before* / *after* mitigations, lets the user choose a **per-mitigation
   disposition** — spawn as a separate task, **inline into this plan as a
   pre-/post-phase**, or drop — and records the chosen ones into the plan.
   Inline mitigations become explicit phase steps of the current plan and are
   never created as tasks (Parts 2/3 skip them). **It creates nothing** (plan
   mode is read-only).
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
- timing: <before|after|pre-phase|post-phase> | name: <snake_name> | type: <issue_type> | priority: <p> | effort: <e> | inline_risk: <low|medium|high> | added_complexity: <low|medium|high> | addresses: <which risk> | desc: <one-line description> [| created: <t<id> | dropped(t<old>)>]
```

`timing` carries the confirmed disposition:

- `before` / `after` — **spawned** dispositions: the mitigation becomes a
  separate task. The Step 7 creation reads the `before` lines; the Step 8d
  creation reads the `after` lines.
- `pre-phase` / `post-phase` — **inline** dispositions: the mitigation is
  incorporated into **this plan's implementation steps** as an explicit phase
  (see Part 1 step 3). No task is ever created for it — Parts 2/3 filter on
  `before`/`after` only and naturally skip inline lines.

The two **decision metrics** are agent-estimated at design time (like
`priority`/`effort`) and recorded on every confirmed line, whatever the
disposition, as provenance for the choice:

- `inline_risk` — the risk of incorporating this mitigation into the main task.
  Estimate from separability: an independently-verifiable, bounded addition
  (e.g. a characterization test) is `low`; work that could invalidate or
  reshape the plan (e.g. an approach spike) is `high`.
- `added_complexity` — how much the mitigation grows the task, estimated
  **relative to the plan's own scope** (a medium-effort mitigation attached to
  a large plan may still be `low` added complexity; the same mitigation on a
  tiny plan is `high`).

`created: t<id>` is an **optional, spawned-only, singular** trailing field — the
creation witness (a line never carries two; stale witnesses are replaced in
place or rewritten to the terminal marker `created: dropped(t<old>)`, see
Part 2 step 1 — the marker **retains the vanished ID** so the unwiring
subtraction survives an interruption and re-converges on every later run). It is absent at design time (Part 1 never writes it) and is written
**per item, immediately after each individual task creation, and committed at
once** (Part 2 / Part 3 step 2). It is also **consumed**: on re-entry the
Part 2 / Part 3 read steps treat a line whose witness names an existing (active
or archived) task as a **reconciliation input** — excluded from creation, but
still converged by the wiring/link steps — which is what makes an interrupted
or re-entered run idempotent instead of duplicating mitigations or leaving
half-wired edges. Inline (`pre-phase`/`post-phase`) lines **never** receive it —
nothing is created for them. Any later edit or normalization of a `### Planned
mitigations` block MUST preserve an existing `created:` field verbatim.

If the user confirms no mitigations, **no `### Planned mitigations` subsection
is written** (the creation parts then find nothing and no-op). The design part
also fills each `## Risk` bullet's `→ mitigation:` placeholder. **Cross-reference
identity is the stable mitigation `name`, never a step position** (positions
drift when a plan is later re-verified or phases are added or dropped) —
therefore **names MUST be unique within a plan's `### Planned mitigations`
subsection**: a duplicate name would make the risk links, witness recovery, and
adoption probe ambiguous. Part 1 validates this when recording (disambiguate a
would-be duplicate before writing, e.g. `characterize_sort_board` /
`characterize_sort_monitor`). The link forms:

- spawned entries: `→ mitigation: <name>`, back-filled to `→ mitigation: t<id>`
  at creation time;
- inline entries: `→ mitigation: inline pre-phase <name>` /
  `→ mitigation: inline post-phase <name>`;
- dropped entries (stale-witness recovery only — see Part 2 step 1):
  `→ mitigation: dropped (was <name>)`, paired with `created: dropped(t<old>)`
  on the line, so the plan never claims a mitigation that will not execute.

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
   - **before** — work that should run *before* the original implementation to
     de-risk it (e.g. a spike/prototype to de-risk a goal-achievement concern,
     a characterization test to de-risk a code-health concern).
   - **after** — a post-implementation follow-up that hardens the result (e.g. a
     refactor to pay down structure debt, an added regression test).

   For each candidate, estimate the two decision metrics (`inline_risk`,
   `added_complexity` — see the Plan record format above) and derive a
   **recommended disposition**:

   - both metrics `low` → recommend **inline** (pre-phase for a before-timed
     candidate, post-phase for an after-timed one). Inlining a small, separable
     mitigation is usually cheaper than a full task lifecycle, and an inline
     phase automatically gets the shadow-agent review rounds (plan-challenge at
     planning, impl-challenge at implementation review) — a spawned task is
     invisible to them because they only see the plan.
   - any metric `high` → recommend **spawn** (a `before` task the original
     depends on, or an `after` follow-up).
   - otherwise (any `medium`, none `high`) → judgement call; lean **spawn**.

   The user always decides — the recommendation only orders the options.

   **⚠️ NON-SKIPPABLE — the disposition prompts below are user-owned workflow
   decisions.** Auto mode / "work without stopping" directives, execution
   profiles, and generic "be brief" / "don't ask" instructions do NOT cover
   them — no profile key currently bypasses mitigation confirmation. The only
   valid skips are a profile key explicitly named in this file as covering it
   (currently: none) or the user explicitly deciding the dispositions in chat
   before the prompt fires. Never auto-confirm, auto-drop, or auto-inline a
   mitigation.

   Present the full candidate details as a **plain-text numbered list in the
   message before the prompt** (one candidate per numbered entry: timing ·
   name · `inline_risk`/`added_complexity` · recommended disposition · what it
   does · which risk it addresses). Cramming those details into the question
   text has been tried and produces one unreadable blob — do not. The question
   text instead carries only a **short per-candidate recap** so the decision
   is still legible if the UI hides the preceding prose: one `<index>. <name>
   → <recommended disposition>` pair per candidate, nothing more. Use
   `AskUserQuestion`:
   - Question: "The risk evaluation identified risks that could be mitigated by
     follow-up tasks or inline plan phases (details listed above).
     Recommendations: 1. <name> → <disposition>; 2. <name> → <disposition>; ….
     How would you like to proceed?"
   - Header: "Risk mitig"
   - Options:
     - "No mitigations" (description: "Skip — record no mitigations; proceed to plan approval")
     - "Apply recommended dispositions" (description: "Confirm every candidate with the recommendation recapped in the question")
     - "Let me choose per mitigation" (description: "Decide spawn / inline / drop for each candidate individually")

   - **"No mitigations":** set `risk_mitigations_confirmed = false` and return
     (do not write a `### Planned mitigations` subsection).
   - **"Let me choose per mitigation":** ask one question per mitigation, in
     proposal order, batching up to 4 mitigations per `AskUserQuestion` call
     (further calls for the rest, preserving order). **Each question's text
     must carry that candidate's full decision context** — name, timing, both
     metrics, the derived recommendation, what it does, and which risk it
     addresses — so the choice is decidable from the widget alone. Each
     question's options — recommended option first, labeled "(Recommended)",
     each description stating what concretely happens (e.g. "becomes a
     blocking 'before' task; this session stops" / "becomes a pre-phase step
     of this plan"):
     - before-timed candidate: "Spawn as 'before' task" / "Inline as pre-phase"
       / "Drop"
     - after-timed candidate: "Spawn as 'after' task" / "Inline as post-phase"
       / "Drop"
     (The user can flip a candidate's timing via the built-in "Other" free-text
     option.) The non-dropped mitigations, each with its chosen disposition,
     form the confirmed set. If every mitigation is dropped, treat as "No
     mitigations".
   - **"Apply recommended dispositions":** the confirmed set is every proposed
     mitigation with its recommended disposition.

3. **Record the confirmed set into the plan.** Append a `### Planned
   mitigations` subsection inside the `## Risk` section, one line per confirmed
   mitigation in the format shown at the top of this file (`timing` carries the
   chosen disposition; both metrics are recorded; no `created:` field is
   written here). **Validate name uniqueness before writing**: if two confirmed
   mitigations would share a `name`, disambiguate first (names are the identity
   keys for risk links, witnesses, and adoption — see the Plan record format). Then fill each `## Risk` bullet's `→ mitigation:` placeholder
   with the corresponding name-based reference (spawned: the mitigation `name`,
   real IDs back-filled at creation; inline: `inline pre-phase <name>` /
   `inline post-phase <name>`).

   **For each inline confirmation, additionally edit the plan's implementation
   steps.** Canonical placement:

   - pre-phase mitigations go in a `### Pre-phase (risk mitigations)` block
     inserted immediately **before the first numbered step of the plan's main
     implementation body**;
   - post-phase mitigations go in a `### Post-phase (risk mitigations)` block
     immediately **after its last numbered step** (before any trailing
     `## Verification` / `## Risk` sections);
   - **fallback when the plan has no numbered main implementation steps**
     (heading- or file-oriented plans — the contract does not require numbered
     steps): the pre-phase block goes at the top of the plan body, immediately
     after the metadata header; the post-phase block goes immediately before
     the first of `## Verification` / `## Risk` (end of file if neither
     exists). Both fallback anchors are deterministic for any plan shape.

   Each block has its own step numbering, and each step is labeled with its
   mitigation `name` (e.g. `1. [characterize_board_sort] <instruction>`), so
   the name-based cross-reference resolves regardless of later reordering.
   Existing plan step numbers are untouched. Each phase step must be a
   concrete, verifiable instruction — the same detail bar as normal plan steps.

   Set `risk_mitigations_confirmed = true` (any disposition counts).

   **No tasks are created and no frontmatter is mutated here** — the plan edit is
   the design output, persisted with the rest of the plan through the standard
   Save-Plan + Checkpoint gate.

4. **Post-inline reassessment (single pass — only when ≥1 inline mitigation was
   confirmed).** Inline phases change the plan the user will approve: the risk
   levels assessed by the Risk Evaluation Procedure describe the
   *pre-insertion* plan. Re-run that procedure's Steps 1–2 **once** against the
   final augmented plan (implementation body + inline phases) and update the
   `## Risk` subsection level headings in place if a level changed.

   **Bullet update rules — linked bullets are durable provenance:**

   - A bullet with a `→ mitigation:` link is never deleted and never collapsed
     into `None identified.` — it is the record of why its mitigation (inline
     phase or spawned task) exists. Update it in place to describe residual
     state, e.g. `<description> · severity: low (residual — addressed by inline
     pre-phase <name>) · → mitigation: inline pre-phase <name>`, keeping its
     identity and link verbatim.
   - Genuinely **new** risks introduced by the augmented plan are added as
     separate new bullets (mitigation link `TBD` or `none`) — never by
     rewriting an existing linked bullet.
   - This reassessment MUST NOT reopen mitigation selection: the `### Planned
     mitigations` lines and dispositions are preserved verbatim and no new
     mitigation proposals are made. One pass; it terminates.

   Thread the possibly-updated `risk_level_code_health` /
   `risk_level_goal_achievement` back into the workflow context — `SKILL.md`
   Step 7's post-approval field write then records the levels of the plan as
   approved, not the pre-insertion ones. Skip this step entirely when no inline
   disposition was confirmed. Then return.

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

Returns `risk_before_blocking` (`true` if the original task must not be
implemented this session because ≥1 before-mitigation is **unfinished** —
whether created in this run, adopted, or witnessed from an earlier run; `false`
when every before-mitigation has already landed, or there are none) plus
`created_before_ids` (this run's creations/adoptions only). When `true`, the
caller (`SKILL.md` Step 7) stops the original task this session (revert to
`Ready`, release lock, end workflow) — see the Step 7 dispatch.

### Procedure

**⚠️ NON-SKIPPABLE — the recovery prompts in this Part (stale witness,
ambiguous adoption) are user-owned workflow decisions.** Auto mode / "work
without stopping" directives, execution profiles, and generic "be brief" /
"don't ask" instructions do NOT cover them — no profile key bypasses them. The
only valid skips are a profile key explicitly named in this file as covering
them (currently: none) or the user explicitly deciding the case in chat before
the prompt fires. Never auto-drop, auto-re-create, or auto-adopt. (This banner
also governs Part 3, which reuses these branches.)

1. **Read the plan's planned mitigations and partition them (re-entry
   reconciliation).** Parse the `### Planned mitigations` subsection from
   `<plan_file>`; keep only `timing: before` lines (`pre-phase`/`post-phase`
   lines are inline plan phases, never spawn candidates — skip them).
   `created: dropped(t<old>)` lines are terminally dispositioned — excluded
   from creation and witness partitions, but their embedded `t<old>` IDs are
   added to `dropped_stale_ids` on **every** run (the subtraction in step 3 is
   idempotent, so a previously interrupted unwiring re-converges here).
   Partition the kept lines:

   - **`witnessed_before_ids`** — lines whose `created: t<id>` witness resolves
     to an existing task, active or archived (check with
     `./.aitask-scripts/aitask_query_files.sh resolve <id>`, falling back to
     `archived-task <id>`). These were created by an earlier run. They are
     **excluded from creation but NOT from the wiring/link convergence in
     steps 3–4** — an earlier run may have died after writing the witness but
     before wiring, and skipping them outright would leave `depends:` /
     `risk_mitigation_tasks` / the risk link permanently unrepaired. Record for
     each whether the task is **landed** (archived, or status `Done`) or
     **unfinished** (anything else) — step 5 keys the stop signal on it.
   - **`to_create`** — lines with no `created:` witness.
   - **Stale witness** — a line whose `created: t<old>` resolves to no task
     (neither active nor archived). Never treat it as plain-uncreated and never
     append a second `created:` field (the witness is a singular trailing
     field; two would make parsing ambiguous). Ask the user
     (`AskUserQuestion`, header "Witness"): "Mitigation '<name>' records
     created: t<old>, but that task no longer exists. Re-create it?" with
     options "Re-create (Recommended)" (description: "Create a fresh task and
     replace the stale witness in place") / "Drop this mitigation" (description:
     "Mark the line `created: dropped(t<old>)` and mark its risk link dropped — no
     task will be created").
     "Re-create" moves the line into `to_create` with a **replace-in-place**
     obligation for its witness. "Drop this mitigation" rewrites the stale
     witness to `created: dropped(t<old>)` (the terminal marker — see the Plan
     record format; the embedded ID is what keeps the pending unwiring
     recoverable) **and** rewrites the matching `## Risk` bullet's link to
     `→ mitigation: dropped (was <name>)` so the approved plan does not keep
     claiming a mitigation that will never execute; commit both edits together
     via `./ait git`. Record the vanished `t<old>` in the third work
     partition, **`dropped_stale_ids`** — step 3 subtracts these from the
     original's `depends:` and `risk_mitigation_tasks` (the one case where
     convergence removes rather than appends); leaving one wired would keep
     the original spuriously Blocked on a task that no longer exists. The
     plan commit landing before the unwiring is safe precisely because the
     marker retains the ID: a crash at that boundary is healed by the
     every-run re-collection above.

   If `to_create`, `witnessed_before_ids`, and `dropped_stale_ids` are **all**
   empty, set `risk_before_blocking = false` and return. Otherwise, if
   `to_create` is empty, **skip step 2 but still run steps 3–5** — this
   includes the drop-only case, whose entire remaining work is the step-3
   subtraction (reconciliation: converge the wiring for the witnessed tasks
   and unwire the dropped ones; step 5 then decides the stop signal from
   whether any witnessed before-mitigation is still unfinished).

2. **Create each `to_create` mitigation, durably persisting the witness per
   item.** For each `to_create` line, in order:

   1. **Adoption probe (reconcile-before-create).** The creation commit and the
      witness commit are separate operations on separate git trees, so a crash
      between them leaves a real task with no witness. Before creating, search
      for a task that an earlier run already created for this line, matching
      **both** identity fields exactly (never a filename substring — a missing
      `foo` must not adopt `foo_extended`):
      - the task filename stem parses as `t<id>_<name>` with `<name>` **equal**
        to the line's `name` (creation uses `--name <name>`, so the stem is
        exactly `t<id>_<name>`; match e.g. `aitasks/t*_<name>.md` and
        `aitasks/archived/t*_<name>.md`, anchored before `.md`), **and**
      - its `## Origin` section matches the provenance prefix for this
        original: `Risk-mitigation ("before") for t<task_id>,` — **including
        the trailing comma**, which is what delimits the id (`t42,` cannot
        match `t421,`). Do not anchor to end-of-line: the creation heredoc
        continues after the comma (`, created at Step 7 …`), and a full-line
        match would miss every real task and re-create a duplicate.

      If exactly one task matches both, **adopt it**: use its ID as `<new_id>`
      and proceed to sub-step 3 without creating. If multiple match, ask the
      user which to adopt (`AskUserQuestion`, header "Adopt task" — one option
      per candidate, plus "Create fresh instead"; this is a recovery prompt
      covered by the NON-SKIPPABLE banner above).
   2. **Create.** Execute the **Batch Task Creation Procedure** (see
      `task-creation-batch.md`) with `mode: parent` (these are **independent
      tasks the original depends on — NOT children**; do not touch the parent's
      `children_to_implement`). Use the line's `name` / `type` / `priority` /
      `effort`; copy topical `labels` from the original task. Pass
      `followup_of: <task_id>` (the original task) so the mitigation anchors to
      the topic it protects, and `followup_kind: risk_mitigation` so the task is
      machine-identifiable as an auto-spawned follow-up rather than new work.
      Capture `<new_id>` from the `Created: <filepath>` output.
   3. **Persist the witness durably — before touching the next line.** Write
      `| created: t<new_id>` on the line (append it; for a stale-witness
      re-create, **replace** the old witness in place instead), then
      immediately commit the plan file via `./ait git add <plan_file> &&
      ./ait git commit` (message: `ait: Record mitigation witness t<new_id>
      for t<task_id>`). The per-item commit is the durable transition that
      makes an interrupted run recoverable: on retry, step 1 sees the witness
      (or, if the crash hit the creation↔witness gap, the adoption probe finds
      the task) and no duplicate is created.

   Description heredoc for creation:

   ```markdown
   ## Origin

   Risk-mitigation ("before") for t<task_id>, created at Step 7 from the approved plan's risk evaluation.

   ## Risk addressed

   <the `addresses` field + the matching `## Risk` bullet, verbatim>

   ## Goal

   <the mitigation `desc`, expanded into what this task must accomplish to de-risk the original>
   ```

3. **Converge the blocking edge (read-modify-write of BOTH list fields —
   idempotent).** The original must *depend on* **every** before-mitigation —
   witnessed and newly created alike — and each must be recorded in
   `risk_mitigation_tasks` (read by the §6.0a force-reverify). Let
   `all_before_ids` = `witnessed_before_ids` + this run's created/adopted IDs.
   Both `--deps` and `--risk-mitigation-tasks` **REPLACE** the full list, so
   read the current values first, append **only the missing** IDs from
   `all_before_ids`, and subtract every ID in `dropped_stale_ids` (the only
   removal case, from step 1's Drop branch), then write the full lists back —
   both in a single call. **Skip the call entirely if nothing changed**
   (fully-converged re-entry):

   ```bash
   # Read current values from the original task frontmatter:
   #   depends:                -> <current_deps>
   #   risk_mitigation_tasks:  -> <current_mitig>   (absent => empty)
   ./.aitask-scripts/aitask_update.sh --batch <task_num> \
     --deps "<current_deps + missing all_before_ids - dropped_stale_ids>" \
     --risk-mitigation-tasks "<current_mitig + missing all_before_ids - dropped_stale_ids>"
   ```

   Pass comma-separated numeric IDs. Commit the task change via `./ait git`
   (the original task file lives on the aitask-data branch).

4. **Converge the plan's mitigation links (idempotent).** For **every** line in
   `all_before_ids`, ensure the matching `→ mitigation:` entry in `<plan_file>`
   references the real ID (e.g. `→ mitigation: t<new_id>`) — repairing links an
   interrupted earlier run left as names, not only this run's. The `created:`
   witnesses were already committed per-item in step 2 (spawned-only, preserved
   verbatim by any later edit — see the Plan record format). Commit the plan
   via `./ait git` if anything changed.

5. **Return.** Set `risk_before_blocking = true` if **any** before-mitigation in
   `all_before_ids` is unfinished — created this run (by definition
   unfinished), or **adopted or witnessed** with a task that is not yet landed
   (not archived / `Done`; an adopted task is status-evaluated exactly like a
   witnessed one — the probe searches archived tasks too, and adopting an
   already-landed mitigation must not force another stop). Set it `false` only
   when every before-mitigation has landed (or there are none): implementing the original with an unfinished dependency —
   even one merely re-wired by a recovery run — is exactly what the blocking
   edge exists to prevent, while a re-entry whose mitigations all landed
   proceeds to implementation instead of being stopped again. Set
   `created_before_ids` to this run's created/adopted IDs and return to
   `SKILL.md` Step 7, which stops the original task for this session when
   `risk_before_blocking` is `true` (its display should name the unfinished
   mitigation task(s)).

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

1. **Read the plan's planned mitigations and partition them (re-entry
   reconciliation).** Parse the `### Planned mitigations` subsection from
   `<plan_file>`; keep only `timing: after` lines (`pre-phase`/`post-phase`
   lines are inline plan phases, never spawn candidates — skip them; likewise
   handle `created: dropped(t<old>)` lines as in Part 2 step 1 — excluded
   from creation/witness partitions, embedded IDs re-collected into
   `dropped_stale_ids` on every run). Partition exactly as in Part 2 step 1:
   `witnessed_after_ids` (witness resolves to an existing task — excluded from
   creation, **included** in the convergence of steps 3–4), `to_create` (no
   witness), and the stale-witness branch (witness resolves to no task → same
   `AskUserQuestion` remedy as Part 2, header "Witness": re-create with
   replace-in-place, or drop — `created: dropped(t<old>)` plus the
   `→ mitigation: dropped (was <name>)` risk-link rewrite; never a second
   `created:` field, and the vanished ID recorded in `dropped_stale_ids` for
   step 3's subtraction). Part 2's NON-SKIPPABLE recovery-prompt banner governs
   these prompts too. If `to_create`, `witnessed_after_ids`, and
   `dropped_stale_ids` are **all** empty, return immediately (Step 8d is a
   no-op). Otherwise, if `to_create` is empty, skip step 2 but still run
   steps 3–4 — including the drop-only case, whose entire remaining work is
   the step-3 subtraction ("after" mitigations block nothing, so there is no
   stop signal here).

2. **Create each `to_create` mitigation, durably persisting the witness per
   item.** For each `to_create` line, follow Part 2 step 2's three sub-steps —
   adoption probe first (same exact-identity match: filename stem exactly
   `t<id>_<name>`, and the comma-delimited provenance prefix
   `Risk-mitigation ("after") follow-up for t<task_id>,` in `## Origin` —
   comma included, end-of-line not anchored, as in Part 2), then Batch Task
   Creation
   (`mode: parent`, same field mapping, `followup_of: <task_id>`,
   `followup_kind: risk_mitigation`), then the
   durable per-item witness write **committed immediately** via `./ait git`.
   Description heredoc:

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

3. **Converge `risk_mitigation_tasks` (read-modify-write — idempotent).** Let
   `all_after_ids` = `witnessed_after_ids` + this run's created/adopted IDs.
   Read the current list, append **only the missing** IDs from `all_after_ids`,
   subtract every ID in `dropped_stale_ids` (the only removal case, from
   step 1's Drop branch), and write the full list back (it **REPLACES**). Skip
   the call entirely if nothing changed:

   ```bash
   ./.aitask-scripts/aitask_update.sh --batch <task_num> \
     --risk-mitigation-tasks "<current_mitig + missing all_after_ids - dropped_stale_ids>"
   ```

   Commit the task change via `./ait git`.

4. **Converge the plan's mitigation links** to the real IDs for every line in
   `all_after_ids` (as in Part 2 step 4 — the `created:` witnesses were already
   committed per-item in step 2), then commit the plan via `./ait git` if
   anything changed. Return to the caller (proceed to Step 9).
