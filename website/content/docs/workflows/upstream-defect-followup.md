---
title: "Upstream Defect Follow-up"
linkTitle: "Upstream Defect Follow-up"
weight: 78
description: "Automatic prompt to spawn a follow-up bug task when diagnosis surfaces a separate, pre-existing defect"
depth: [intermediate]
---

Bugfix work routinely surfaces *other* defects — pre-existing bugs in different scripts, helpers, or modules that are not the immediate cause of the symptom under repair but were noticed during diagnosis. Without a structured nudge, these observations get buried in plan notes and never become their own tracked work.

[`/aitask-pick`](../../skills/aitask-pick/) Step 8b — between the "Commit changes" review approval and Step 8c (manual-verification follow-up) — reads the just-committed plan file, identifies any upstream defects that were called out, and offers to spawn a fresh `bug` aitask for each one. The diagnostic chain of reasoning that surfaced the defect is folded into the new task body so the future picker has actionable context, not just a one-line bug report.

This is complementary to user-driven follow-up creation (see [Follow-Up Tasks](../follow-up-tasks/)) and to test-coverage gap detection ([`/aitask-qa`](../../skills/aitask-qa/)). Step 8b targets *related code defects in other places* — not test gaps, not refactors, not style cleanups.

## The Plan-File Contract

Step 8 plan consolidation requires every plan's `## Final Implementation Notes` section to include a canonical bullet:

```markdown
- **Upstream defects identified:** <None | one or more defect bullets>
```

Each defect bullet uses the form `path/to/file.ext:LINE — short summary`, for example:

```markdown
- **Upstream defects identified:**
  - aitask_brainstorm_delete.sh:109-111 — worktree-prune ordering bug leaves stale crew-brainstorm-<N> branch
  - lib/task_utils.sh:42 — resolve_task_id() returns parent path for child IDs missing leading zero
```

When no related defect was identified, the bullet must read literally:

```markdown
- **Upstream defects identified:** None
```

What does **not** belong in this bullet:

- Style or lint cleanups
- Refactor opportunities
- Test coverage gaps (those route through [`/aitask-qa`](../../skills/aitask-qa/))
- Unrelated TODOs or future ideas

The bullet is the contract Step 8b reads. Filing related defects elsewhere (a side bullet, an "Out of scope" section, free prose) bypasses the contract — see *Sanity-Check Path* below for the safety net.

## When the Prompt Fires

Step 8b runs after the user selects "Commit changes" in Step 8 and the code + plan commits have already landed. It reads the plan file at `aiplans/p<task_id>_<name>.md` (or `aiplans/p<parent>/p<parent>_<child>_<name>.md` for child tasks) and locates the canonical bullet inside `## Final Implementation Notes`.

Step 8b is silently skipped when:

- No plan file exists for the task (e.g., the task was committed without one).
- The canonical bullet says `None` and the sanity-check path finds nothing in the plan body either.

## Fast Path vs Sanity-Check Path

The procedure has two parsing modes:

- **Fast path** — the canonical bullet contains one or more defect entries. Each bullet's location prefix and summary become the input to the user offer. The plan body is not re-read.
- **Sanity-check path** — the canonical bullet is missing, empty, or contains exactly `None` (case-insensitive, whitespace-tolerant). The procedure re-reads the entire plan body — including `Out of scope`, `Issues encountered`, `Deviations from plan`, side bullets, and free prose — looking for pre-existing defects in other code that were filed in the wrong place. Synthesized bullets in the canonical format become the input to the offer; the plan file itself is not modified.

The sanity-check path exists because misclassification is the dominant failure mode. A real example (t687): setup wrote `None` to the canonical bullet and recorded a related trailing-slash `.gitignore` defect under a side bullet `- **Trailing-slash follow-up:**`. The fast path saw `None` and would have short-circuited, silently burying the defect in the archived plan. The sanity-check path inspected the plan body, surfaced the side-bullet defect, and offered the follow-up prompt as normal.

## The User Prompt

Step 8b uses `AskUserQuestion`:

> Diagnosis surfaced an upstream defect: `<first defect bullet verbatim>`. Create a follow-up aitask for it?

When more than one defect bullet exists, the question text is suffixed with `(+<N-1> more — all will be folded into the new task body)`.

The two options:

- **Yes, create follow-up task** — Spawn a new `bug` aitask documenting the upstream defect, with the diagnostic context from this task.
- **No, skip** — The defect remains documented only in this task's archived plan file. Useful when the defect is purely informational or already tracked elsewhere.

## The Seeded Follow-up Task

When the user accepts, the procedure shells out to `aitask_create.sh --batch` to create a new parent task with:

- `issue_type: bug`
- `priority: medium` (defaults to `high` only when the defect is actively breaking other flows — adjustable later)
- `effort: low`
- `labels:` topical labels copied from the origin task
- A name derived from the first defect summary (snake_case, e.g. `fix_brainstorm_delete_prune_ordering`)

The task body has up to four sections:

```markdown
## Origin

Spawned from t<task_id> during Step 8b review.

## Upstream defect

<verbatim copy of all bullets from the plan file's "Upstream defects identified" subsection>

## Diagnostic context

<relevant excerpt from Final Implementation Notes — typically the "Issues encountered" + "Deviations from plan" entries — showing the chain of reasoning that surfaced the defect>

## Suggested fix

<one or two lines on the likely fix direction; omitted when not known>
```

After creation, the procedure displays the new task ID and path so the user can pick it up later in a fresh context with full LLM capacity for the unrelated defect.

## End-to-End Example

Task t660 fixed a symptom: the brainstorm TUI silently quit on plan import. Diagnosis revealed that a stale `crew-brainstorm-<N>` git branch — left over by a worktree-prune ordering bug elsewhere — was the actual seed of the failure.

The plan added a recovery modal for the symptom. Its `## Final Implementation Notes` recorded:

```markdown
- **Upstream defects identified:**
  - aitask_brainstorm_delete.sh:109-111 — worktree-prune ordering bug leaves stale crew-brainstorm-<N> branch
```

After the user clicked "Commit changes", Step 8b parsed the bullet via the fast path and offered:

> Diagnosis surfaced an upstream defect: `aitask_brainstorm_delete.sh:109-111 — worktree-prune ordering bug leaves stale crew-brainstorm-<N> branch`. Create a follow-up aitask for it?

The user clicked "Yes, create follow-up task". A new bug task was seeded with the diagnostic context from t660's plan — the chain of reasoning that traced the symptom back to the prune-ordering bug — pre-loaded into the body. The user picked it up later as a focused bugfix without having to re-derive the diagnostic chain.

Without Step 8b, the upstream defect would have lived only in the archived plan, and a future picker hitting the same symptom would have re-traced the same chain from scratch.

## Tips

- **Document the defect in the canonical bullet, not in side bullets.** The sanity-check path catches misfiled entries, but it is a safety net — the canonical bullet is the contract every other tool reads.
- **Use the `path/to/file.ext:LINE — short summary` form.** The seeded follow-up task body inherits this string verbatim, so a precise location prefix gives the future picker actionable navigation.
- **Don't conflate this with [`/aitask-qa`](../../skills/aitask-qa/).** QA handles automated test gaps and proposes test plans. Step 8b handles *related defects in other code* — different concern, different output (a `bug` task vs a `test` task).
- **Skip when appropriate.** If the upstream defect is already tracked by an existing task or known to the team, "No, skip" leaves it in the archived plan as a paper trail without creating a duplicate.
