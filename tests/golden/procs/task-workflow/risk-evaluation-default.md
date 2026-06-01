# Risk Evaluation Procedure (design)

Assesses the **risk** of an approved-but-not-yet-implemented plan across **two
independent dimensions**, assigns a level to each, and records a `## Risk`
section into the plan. It runs at the **end of planning** (`planning.md` §6.1),
which executes in **plan mode (read-only)** — so this procedure only *decides*
and *writes the plan section*. It performs **no frontmatter mutations**: the
`risk_code_health` / `risk_goal_achievement` field writes happen **after the
plan is approved**, in `SKILL.md` **Step 7**. This mirrors the single-repo
decomposition flow and the cross-repo design/creation split
(`planning-cross-repo.md` design + `cross-repo-child-assignment.md` creation),
where mutations are always deferred out of plan mode.

## Input context (from `planning.md` §6.1)

| Variable | Description |
|----------|-------------|
| `task_id` | The task being planned (`16` or `16_2`). |
| `task_file` | Path to the current task file. |
| the approved design | The plan just designed in §6.1 (steps, files touched, approach). |

## Return contract

Threads three values back into the workflow context for Step 7:

- `risk_level_code_health` — `high` \| `medium` \| `low`.
- `risk_level_goal_achievement` — `high` \| `medium` \| `low`.
- `risk_mitigations_planned` — `true` if the evaluation surfaced risks the user
  may want to mitigate with before/after follow-up tasks (consumed by the
  Risk-Mitigation Follow-up Procedure, `risk-mitigation-followup.md`, in t884_4);
  `false` otherwise.

---

## Procedure

### Step 1 — Assess the two dimensions **separately**

Evaluate the planned change along **two independent axes**. Do not blend them
into a single score — each gets its own level.

**(A) Code-health risk** (`risk_code_health`) — the risk that *implementing this
plan* degrades the codebase, independent of whether it meets the goal:

- **Stability** — could the change break existing behavior, introduce
  regressions, or destabilize a load-bearing path?
- **Quality** — does the approach fit existing patterns, or does it introduce
  ad-hoc structure, duplication, or abstraction debt?
- **Maintainability** — will the result be readable and changeable by the next
  person, or does it add hidden coupling / implicit contracts?
- **Blast radius** — how many files, modules, or callers does the change touch,
  and how central are they?

**(B) Goal-achievement risk** (`risk_goal_achievement`) — the risk that the
planned implementation *does not actually deliver what the user asked for*, even
if the code is clean:

- **Approach soundness** — is the chosen approach the right one for the stated
  goal, or is there a meaningful chance it's the wrong shape?
- **Requirement coverage** — does the plan address every requirement in the task,
  or are parts unaddressed / misunderstood?
- **Technical feasibility** — are there assumptions (APIs, data, behavior) that
  might not hold and could block delivery?
- **Completeness** — does the plan deliver the whole goal, or only part of it?

### Step 2 — Assign a level to each dimension

Assign one level **per dimension** using this rubric (applied independently — a
plan can be `low` on one axis and `high` on the other):

- **high** — a likely or high-impact concern on this axis: a plausible path to a
  regression / wrong outcome, a wide blast radius, a shaky core assumption, or a
  requirement the plan does not convincingly cover.
- **medium** — a real but bounded concern: a localized risk, a recoverable wrong
  turn, or a requirement covered but not airtight.
- **low** — no material concern on this axis: the change is contained and the
  plan plainly delivers the goal.

### Step 3 — Author the `## Risk` plan section

Append a `## Risk` section to the plan with **two subsections, each headed by its
own level**. List each identified risk as a bullet:
`<description> · severity: <…> · → mitigation: <link>`. The `→ mitigation` link
is left as a placeholder here and filled in by the Risk-Mitigation Follow-up
Procedure (t884_4) if the user chooses to spawn mitigations. A subsection with
no identified risk reads `None identified.`

```markdown
## Risk

### Code-health risk: <high|medium|low>
- <description of the risk> · severity: <high|medium|low> · → mitigation: <link or "TBD">
- … (or "None identified.")

### Goal-achievement risk: <high|medium|low>
- <description of the risk> · severity: <high|medium|low> · → mitigation: <link or "TBD">
- … (or "None identified.")
```

Set `risk_mitigations_planned = true` if either subsection lists at least one
risk the user may want to mitigate; otherwise `false`.

### Step 4 — Hand back to planning

Return `risk_level_code_health`, `risk_level_goal_achievement`, and
`risk_mitigations_planned` to the workflow context. The actual frontmatter write
runs post-approval at `SKILL.md` Step 7 — **do not write the fields here**
(plan mode is read-only).
