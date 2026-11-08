---
Task: t1663_5_website_docs_premise_staleness.md
Parent Task: aitasks/t1663_implement_task_premise_staleness.md
Sibling Tasks: aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md
Archived Sibling Plans: aiplans/archived/p1663/p1663_*_*.md
Base branch: main
Output branch: main
---

# t1663_5 — Website docs for the advisory premise-staleness check

## Context

Children 1–4 of t1663 shipped the advisory premise-staleness mechanism. Users still have no docs for it: the website only has the `premise_baseline` field row in `development/task-format.md`. This task adds a workflow page covering what the check is, when it fires, the four answers, how to opt in or out, and the v1 limits. It also adds cross-links so readers can find the page.

The design record is `aidocs/framework/task_premise_staleness.md`, and the shipped procedure is `.claude/skills/task-workflow/premise-staleness.md` plus `SKILL.md.j2` Step 3 Check 7. Both notes received at pick were read as advisory and checked against the tree:
- Check 7 is right (not Check 6, which is the inbox check). It runs on every entry path that hands off to the shared task workflow (pick, board agent launch, explore). The fully autonomous `/aitask-pickrem` / `/aitask-pickweb` skills have their own workflow and do **not** run it (grep finds no `premise` in either).
- `workflows/_index.md` is hand-curated, so it needs a bullet.
- There is no "premise staleness" concept page (t1687 has not written one), so there is nothing to link and nothing duplicated.
- **Correction found while checking:** the manual-verification staleness pre-check (`verification_baseline`) has **not shipped**. t1555_3, the procedure step, is still pending; only the helper and the field exist. The new page must not describe it as running. It says only that this check skips manual-verification tasks, and that `verification_baseline` is a separate field.

Opt-in wording is fixed by t1673/the record: the baseline is seeded at creation by `--file-ref` (Tier A) **or** `--verifies` (Tier B). `--followup-of` does **not** seed. Opting out means clearing the field.

## Steps

### 1. New page `website/content/docs/workflows/premise-staleness.md`

Front matter: `title: "Premise Staleness Check"`, `linkTitle: "Premise Staleness"`, `weight: 62` (right after Task Notes, 61), a one-line `description`, `depth: [intermediate]`. Current-state prose only. No agent names ("the code agent"). Internal links use `{{< relref "/docs/..." >}}`.

Sections:
1. **Intro.** A `Ready` task can sit for months while the code it was written against changes. The check reports whether files in the task's scope changed since its premise was last known valid. It is advisory and evidence-backed, and never blocks. A clean result means "the watched files did not change", not "the task is still worth doing".
2. **When it runs.** At the start of the shared task workflow (after selection, before the task is claimed), on every route into it: `/aitask-pick`, the board's agent launch, `/aitask-explore`. Conditions: status `Ready`, not `manual_verification`, a stored `premise_baseline`, and a derivable scope. The scope is `file_references`, or for a task with `verifies`, the files its verified tasks' commits touched. It is silent when every scope file was checked and none changed, and silent when the task cannot be evaluated (no baseline, empty scope, the baseline commit is no longer in history). The autonomous `/aitask-pickrem` / `/aitask-pickweb` skills run their own workflow and do not include the check at all.
3. **What it compares.** Commits between the baseline commit and the current `HEAD` that touch scope paths, read from committed history only, so uncommitted edits don't count. The kinds of evidence the prompt lists, in plain words: changed, deleted, added since the baseline, never existed (a planned future file or a typo), invalid reference (a malformed `file_references` entry), could not be checked.
4. **The prompt and your four answers.** Under an **interactive** profile on the shared workflow, the prompt is always asked when there is evidence, and no interactive profile skips it. State that qualifier explicitly and forward-link section 7: a non-interactive profile on the shared workflow reports and continues, and `/aitask-pickrem` / `/aitask-pickweb` don't run the check. "Evidence" here means both change rows (changed / deleted / added since the baseline) **and** unresolved scope or history rows (never existed / invalid reference / could not be checked). The second group triggers the prompt with no committed change at all (`lib/task_premise.py`). A table gives each answer, what happens next, and what it does to the baseline (from the record's Interaction table):
   - Proceed: claim the task; baseline advances to the commit that was checked.
   - Review & replan: claim it and replan with the evidence. An existing plan is re-verified. The baseline advances when the new plan is approved, including "Approve and stop here".
   - Postpone: claim it, set it to `Postponed`, end the session. `ait update <id> --status Ready` brings it back.
   - Pick a different task: nothing changes.
   Subnotes:
   - Ask before claiming, write after. The claim confirms the task is still `Ready`, or stops with nothing claimed.
   - "Proceed" with never-existing references asks a separate keep/remove question. Keep is the default.
   - Unverifiable rows → no advance; the check runs again next pick.
   - The advance applies only to commits you were shown; anything that landed later shows up at the next pick.
5. **Opting a task in.**
   - At creation: `ait create --file-ref …` (includes the codebrowser `n` flow from Creating Tasks from Code) or `--verifies …`. It is stamped with the commit the task is created at, or at draft finalize; drafts themselves are not stamped.
   - `--followup-of` alone does **not** opt in.
   - Carry-over tasks inherit the baseline from the original task.
   - An existing task: give it `file_references` (`ait update --file-ref`) **and** set a baseline with `ait update --premise-baseline <full commit id>`. Adding scope later does not stamp a baseline.
   - Example snippet.
6. **Opting out.** `ait update <id> --premise-baseline ""`.
7. **Unattended runs.** Two different cases, stated separately. (a) A non-interactive profile on the shared workflow (`remote`, as rendered in `task-workflow-remote-/SKILL.md` Check 7) runs the check, displays the evidence and continues. It never prompts, never advances the baseline, never postpones, so the evidence comes back on the next attended pick. (b) The autonomous `/aitask-pickrem` / `/aitask-pickweb` skills don't run the check at all.
8. **Limits.**
   - Tasks without a stored baseline are skipped; there is no backfill.
   - No time-based verdict: age alone never triggers it.
   - It measures change, not behaviour (a refactor reads as drift; a distant change can read as clean).
   - Invalid references keep being reported until fixed by hand.
   - A kept never-existing reference keeps being reported.
   - A session that can't identify itself (outside the agent's tmux pane, no `AIT_AGENT_PID`) can't advance, so the prompt comes back.
   - A draft is stamped at finalize time.
9. **Not the same as `verification_baseline`.** One paragraph: that field belongs to manual-verification checklists, and this check skips those tasks. Link to Manual Verification.
10. **Related.** Links: Task Format, Creating Tasks from Code, Manual Verification, `/aitask-pick`, task-management commands.

### 2. `website/content/docs/workflows/_index.md`
Add a bullet in **Tasks** after Task Notes: `- [Premise Staleness Check](premise-staleness/) — Advisory check, when a task is picked, that reports whether the files its premise depends on changed since it was last known valid.`

### 3. `website/content/docs/workflows/manual-verification.md`
In "Running a Manual-Verification Task", add one short paragraph: the shared workflow's [premise staleness check] skips manual-verification tasks, because a checklist's validity is tracked by its own `verification_baseline` field. Don't claim a pre-check runs. This makes the reverse cross-link.

### 4. `website/content/docs/development/task-format.md`
In the `premise_baseline` row, link "advisory premise-staleness check" to the new page with a relref. Re-read the row in context. The `verification_baseline` row's claim that its pre-check is live is t1555's responsibility, so leave it and send a note (step 7).

### 5. `website/content/docs/skills/aitask-pick/_index.md`
In step 4 ("Task status checks"), add a sentence: for a `Ready` task with a stored premise baseline, it also runs the advisory [premise staleness check], which asks only when it finds evidence: a file in the task's scope changed, was deleted or was added since the baseline, or a scope entry or its history could not be resolved (a reference to a file that never existed, an invalid reference, history that could not be read). Wording must match the new page's evidence section.

### 6. `website/content/docs/workflows/create-tasks-from-code.md`
Add one sentence where `--file-ref` creation is described: a task created with a file reference is stamped with a premise baseline, so the premise staleness check can tell you later if those files changed. Link it.

### 7. Claim audit + note
- Check every behavioural claim on the new page against `premise-staleness.md`, `SKILL.md.j2` Check 7, and `aitask_create.sh` / `aitask_update.sh` `--help`. Specifically check:
  - `--premise-baseline` is accepted by `ait update`.
  - `--file-ref`/`--verifies` seed.
  - `--followup-of` does not seed.
  - The headless branch exists.
  - pickrem/pickweb don't run the check.
  - Consistency across all six touched pages:
    - every "always asked" statement carries the interactive-profile qualifier;
    - every "asks when…" statement uses the full evidence definition (changes **and** unresolved scope/history), never "only when files changed".
- `./ait note 1555_3 --from 1663_5`: the `development/task-format.md` `verification_baseline` row already says the pre-check is live, ahead of t1555_3 landing. Re-check that wording when you ship. The new premise-staleness page links to manual-verification.md, which is where the pre-check should be documented. (Hedge: the claim is tree-relative.)

## Verification
- `cd website && hugo build --gc --minify` passes.
- `cd website && python3 check_links.py --build` passes. This covers the relative-path links and `#fragment` anchors on the new page and in the edits.
- Cross-references resolve both ways: new page ↔ manual-verification, new page ↔ task-format, `_index` → new page.
- Grep the new page for agent product names: none.

## Step 9 (Post-Implementation)
Commit docs as `documentation: Document the advisory premise-staleness check (t1663_5)`, naming only the changed paths, because the worktree has unrelated in-flight changes. Plan via `aitask_task_commit.sh`. Then archive per the task workflow.

## Risk

### Code-health risk: low
None identified. Docs-only change, adding one page and small prose edits to five pages. No code or config touched.

### Goal-achievement risk: low
- Prose could describe behaviour that differs from what shipped, e.g. claiming a check that has not landed, as already happened with the manual-verification pre-check. · severity: low · → mitigation: covered by plan step 7 (claim audit against source)

## Final Implementation Notes

- **Actual work done:** New page `website/content/docs/workflows/premise-staleness.md` (sections 1-10 as planned: when it runs, what it compares, evidence table, four-answer table, opt in/out, unattended runs, limits, `verification_baseline` distinction, related). Cross-links added to `workflows/_index.md` (Tasks section, after Task Notes), `workflows/manual-verification.md` (reverse link, under "Running a Manual-Verification Task"), `development/task-format.md` (`premise_baseline` row → relref), `skills/aitask-pick/_index.md` (step 4, full evidence wording), and `workflows/create-tasks-from-code.md` (step 7, stamping sentence).
- **Deviations from plan:** None in scope. Plan-review corrections applied before approval: "always asked" is qualified to interactive profiles on the shared workflow, unattended runs are split into headless-profile (report-only) and pickrem/pickweb (not run), and every "asks when" statement uses the full evidence definition (changes plus unresolved scope or history).
- **Issues encountered:** The manual-verification staleness pre-check (t1555_3) has not shipped, but the `verification_baseline` row in task-format.md already describes it as live. The new docs do not repeat that claim. A note was sent to t1555_3 (NOTE_APPENDED 2026-11-08T11:14:37Z.272b84400fd910498b7d7894).
- **Key decisions:** The page goes under "Tasks" in the workflows index (weight 62, next to Task Notes) because it concerns backlog tasks at pick time. The opt-in example resolves `HEAD` with `git rev-parse` because the writer rejects symbolic revisions.
- **Upstream defects identified:** None.
- **Verification:** `hugo build --gc --minify` exit 0 (scratch output dir); `python3 check_links.py --build` → `SWEEP: PASSED`; rendered page has all in-page anchors; manual-verification, task-format and workflows index all link to the new page; no agent product names on the new page.
- **Notes for sibling tasks:** t1663_6 (retrospective) owns the deferred surfaces. If read-surface markers or the computed-baseline profile key ship, update this page's "When it runs" and "Limits".
