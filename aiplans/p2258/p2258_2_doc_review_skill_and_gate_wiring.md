---
Task: t2258_2_doc_review_skill_and_gate_wiring.md
Parent Task: aitasks/t2258_doc_audience_levels_and_readable_prose.md
Sibling Tasks: aitasks/t2258/t2258_1_*.md, aitasks/t2258/t2258_3_*.md, aitasks/t2258/t2258_4_*.md, aitasks/t2258/t2258_5_*.md, aitasks/t2258/t2258_6_*.md, aitasks/t2258/t2258_7_*.md, aitasks/t2258/t2258_8_*.md
Archived Sibling Plans: aiplans/archived/p2258/p2258_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-10 15:15
---

# t2258_2 — `aitask-doc-review` skill and `docs_updated` gate wiring

## Context

The procedure half of t2258. Binding text: parent plan
`aiplans/p2258_doc_audience_levels_and_readable_prose.md` — Design decisions 2,
3, 5, 6; Pre-phase `gate_review_cost_bound`; Post-phase
`doc_review_gate_contract_test`; the child-2 Verification bullets. Those went
through three review rounds (reviewed-draft input, cumulative budget,
five-state destination check incl. concurrent create/delete, merge-file error
handling). Implement them as written.

Child 1 (t2258_1, archived) put the level model and the prose rules into
`aitasks/metadata/doc_update_guide.md`. The interface this child relies on is the
list under `## Reader levels`: `- Level field: \`depth\``,
`- Beginner level: \`main-concept\``, `- Personas:` with one sub-bullet per
level value. Frontmatter values are list-shaped (`depth: [main-concept]`).

## Verification notes (plan verified 2026-11-10 against main @ b93a5f258)

- Gate skill `.claude/skills/aitask-gate-docs-updated/SKILL.md` unchanged since
  `9baf1dcb491493f7a0796ed4af94f399ae8f1e82` — still the 6-step flow (1 load
  spec, 2/2b change surface, 3 infer+propose, 4 confirm, 5 apply, 6 record).
  That full SHA is the **pre-change pin** for the contract test's control
  (it stays valid after this task commits, unlike `HEAD:`).
- `tests/test_resolve_config_path_cli.sh` Case 6 asserts the gate text contains
  `aitask_resolve_config_path.sh` and `doc_update.guide` → keep step 1 intact.
- `.aitask-gates/` is already gitignored (`.gitignore:22`).
- Codex / OpenCode gate wrappers (`.agents/skills/aitask-gate-docs-updated/SKILL.md`,
  `.opencode/skills/…`, `.opencode/commands/aitask-gate-docs-updated.md`) are pure
  pointers with the frontmatter description only; the description does not
  change → **no wrapper refresh**.
- New skill gets no Codex/OpenCode wrappers here (child 8 creates the port
  tasks). `aitask_audit_wrappers.sh discover` will then list
  `GAP:*:aitask-doc-review`, the same tolerated state as
  `aitask-explorechat` today; `parity` stays clean (no tree has it).
- **Design gap found:** step 4's confirm prompt already has 4 options
  (Apply / Adjust / Not needed / Reject); AskUserQuestion allows at most 4. So
  "Run more fresh-reader tests" is a **separate, preceding question** asked
  only when pages were left `not-run(cap)` and the profile is interactive.
- `aitask_resolve_config_path.sh` computes its repo root from its own path
  (`cd "$(dirname …)/.." && pwd`, logical), so the no-level-model dry run uses a
  scratch dir whose `.aitask-scripts` is a symlink to the real one, plus a
  scratch `aitasks/metadata/project_config.yaml`.

- **Review findings (user, plan round 1), both verified and blocking:**
  (a) rebaselining `.base` from the live page after a merge loses an edit made
  between merge and rebaseline → the merge input is an immutable `.snapshot`
  that becomes the new `.base`; (b) step 3's budget initialization would reset a
  spent budget when step 5 returns a page to step 3 → `.reader_budget` is
  written once per run id. Both get a dedicated dry run and a contract check.
  No content-hash audit trail is added (still child 8's open item).

### Pre-phase (risk mitigations)

1. [gate_review_cost_bound] The review procedure keeps one gate run bounded:
   level/prose check is one in-context pass per page; fresh-reader runs (sub-agent
   or self-review) only for edited beginner-level pages, **budget 3 per gate run,
   cumulative across every review and re-review**; the gate passes the remaining
   budget in and the skill returns the amount used; within a pass pick by most
   changed body lines; leftovers `reader=not-run(cap)`, listed at confirm; extra
   tests only on the user's explicit "Run more fresh-reader tests" choice, never
   in autonomous profiles; no budget used in the no-level-model case.

## Steps

1. **Read** (done during verification): skill authoring conventions, gate skill,
   `aitask-docs-gap` Step 6, `tests/test_gate_procedure_docs.sh`,
   `tests/lib/asserts.sh`, the guide's new sections.

2. **Write `.claude/skills/aitask-doc-review/SKILL.md`** (plain SKILL.md,
   profile-agnostic — nothing in it varies by profile; the caller passes the
   budget and whether it is interactive). Sections:
   - Frontmatter: `name: aitask-doc-review`, `description:` (one line: review doc
     page drafts against the project's configured doc guide — reader level, prose,
     fresh-reader test for beginner pages).
   - **Purpose** — procedure only; the rules live in the project's guide.
   - **Invocation** — `ARGUMENTS`: `<path>... [--budget N] [--caller gate|adhoc|audit]`.
     Paths are `.draft` files (gate) or live page paths (ad-hoc / audit). Default
     budget 3 when omitted. Caller `gate`: may revise `.draft` files in place;
     `adhoc` / `audit`: report only, edit a live page only when the user asks.
   - **Step 1, resolve and read the guide:**
     `./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide aitasks/metadata/doc_update_guide.md`;
     an empty line (no guide, or the resolver could not run) is treated as a guide
     with no level model and no writing conventions: the no-level-model path
     (Step 6), and the report says no guide was found.
   - **Step 2, detect the level model:** present ⇔ the guide has a `## Reader levels`
     heading whose list declares `Level field:`, `Beginner level:` and
     `Personas:` with one persona per level value. That heading and those three
     labels are the only things read by name; everything else in the guide is
     rule text applied as written. Absent → no-level-model path (Step 6).
   - **Procedure invariants** (owned by the skill, not rule text): rewrite prose
     only — never code blocks, inline code, commands, paths, URLs, frontmatter or
     link targets; add no facts, names or numbers (ask, or write a simpler
     sentence); a fact cut from a page is moved to its owning page (gate: a new
     `.draft` + `.base` pair in the same drafts dir; otherwise report it), never
     deleted; a fact found wrong is corrected or dropped with the reason recorded.
   - **Step 3, per page, level + prose check** — one in-context pass, no
     sub-agent. Read the page's level from its frontmatter (the declared level
     field; list or scalar form). Untagged → level finding ("`<field>` is
     required") and `reader=not-run(untagged)`. Check the page against the guide's
     contract for its level and its page type, and against the guide's prose
     rules and writing conventions. Gate caller: fix what can be fixed within the
     invariants, in the `.draft`, and list each change; what cannot be fixed is an
     unresolved problem.
   - **Step 4, fresh-reader test** (method from anthropics/skills
     `doc-coauthoring`, own procedure): candidates = pages at the beginner level.
     Order by most changed body lines (`.base` vs `.draft` below the frontmatter,
     added + removed; a page with no `.base`, or a live page, counts all body
     lines). Take candidates while budget remains; the rest get
     `reader=not-run(cap)`. For each tested page: predict 5–10 questions a reader
     at that level would ask; start a sub-agent with **only the page text
     inline** (tell it not to open files or search), the level's persona sentence
     and the questions; collect its answers; then ask it what was ambiguous, what
     it assumed the reader already knew, every term it had to guess, every detail
     it did not need to answer the questions, and any contradiction. Compare
     answers to the page; wrong or guessed answers are findings. `reader=subagent`.
     Agents without sub-agents: answer the same questions as the persona from the
     page alone, then run the same follow-up list as a self-review checklist;
     `reader=self-review`. Either counts 1 against the budget. Non-beginner pages
     `reader=not-run(not-beginner)`.
   - **Step 5, report** — fixed format per page plus a footer:
     ```
     PAGE: <path>
     level=<ok|findings:N|not-run(no-level-model)>  prose=<ok|findings:N>  reader=<value>
     Level findings: …   Prose findings: …   Changes made: …
     Reader report: guessed terms … / details not needed … / ambiguities … / contradictions …
     Unresolved: <N> — …
     BUDGET_USED:<n>  BUDGET_LEFT:<m>  NOT_RUN_CAP:<paths or none>
     ```
   - **`reader=` values** (exact strings, one per page): `subagent`,
     `self-review`, `not-run(not-beginner)`, `not-run(untagged)`, `not-run(cap)`,
     `not-run(no-level-model)`.
   - **Budget rules** — as Pre-phase 1; the skill never extends the budget itself.
   - **Step 6, no-level-model path** — prose check only, against whatever writing
     conventions the guide has; `level=not-run(no-level-model)` and
     `reader=not-run(no-level-model)` for every page; `BUDGET_USED:0`; the report
     says the project's guide has no level model.
   - **MUST NOT** list (copy no guide text; never test a page without its text
     inline; never edit outside prose; never spend past the budget).
   No rule text from the guide is copied in.

3. **Edit the gate skill** `.claude/skills/aitask-gate-docs-updated/SKILL.md`:
   - **Step 3 → "Infer + draft the doc updates"**: for each page to create or
     update, **first** copy the existing page to
     `.aitask-gates/<task-id>/docs_updated_<run-id>_drafts/<page path>.base`
     (`mkdir -p` the parent dirs; no `.base` for a new page), then write the
     complete proposed page to `<page path>.draft`, drafting **from the `.base`
     copy**, never from a second read of the live page. Never edit the real page
     in this step.
     **Budget, once per run id:** the run's fresh-reader budget lives in
     `<drafts dir>/.reader_budget`. Write `3` there **only if the file does not
     exist yet**; otherwise read the remaining value. Step 3 is re-entered from
     step 5 (created / deleted pages) within the same run, and that re-entry keeps
     the remaining budget; it never resets it. Every step that spends or grants
     budget (3b, 4a) rewrites the file.
   - **New step 3b, "Review the drafts"**: Read and follow
     `.claude/skills/aitask-doc-review/SKILL.md` (by file path, so every agent
     tree can follow it) with the `.draft` paths, `--caller gate` and the remaining
     budget read from `.reader_budget`; subtract its `BUDGET_USED` and write the
     result back. The budget is cumulative across every review and re-review in
     this run, including pages returned to step 3.
   - **Step 4 confirm**: present the attributed file list (unchanged text), the
     per-page review result, the reader report, unresolved problems, pages left
     `not-run(cap)` and the remaining budget — inside the question text
     (visibility rule). **4a (only if any page is `not-run(cap)` and the profile is
     interactive):** a separate `AskUserQuestion` "Run more fresh-reader tests"
     (naming the pages; explicit authorization adds budget for exactly those pages
     and re-runs 3b on them) / "Continue without them". Autonomous profiles never
     ask and never extend. **4b**: the existing Apply / Adjust / Not needed /
     Reject prompt. **Adjust** edits the drafts, re-runs 3b on the changed pages
     (level/prose always; fresh-reader only within the remaining budget), then
     asks again.
   - **Step 5 apply** — destination check per page against the **live**
     destination, exactly one row (table from decision 5, one row per line):
     | `.base` | destination now | state | action |
     | yes | exists, `cmp -s` equals `.base` | unchanged | copy `.draft` over it |
     | no | absent | unchanged (new page) | copy `.draft` into place |
     | yes | exists, differs | modified by another session | snapshot, then `git merge-file -p <.snapshot> <.base> <.draft> > <.reconciled>` |
     | no | exists | created by another session | apply nothing; back to step 3, which copies the page that now exists to `.base` first and drafts from that copy |
     | yes | absent | deleted by another session | apply nothing; back to step 3, ask the user: recreate / move the change / drop |
     **Modified row, in this order:** (1) `cp <destination> <page path>.snapshot`
     once; (2) merge **from the snapshot**, never from the live page; (3) on
     success the reconciled text replaces the `.draft` and **the snapshot**
     becomes the new `.base` (`mv .snapshot .base`) — never a fresh copy of the
     live page, because an edit landing between the merge and a re-copy would be
     in `.base` but not in the draft, and the next apply's `cmp` would pass and
     overwrite it. The next apply checks the live destination again against that
     `.base`, so such an edit puts the page back in the modified row.
     Merge exit status: `0` clean; `1`–`127` that many conflicts, resolved by hand,
     no conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`) left; any other status
     (git reports errors as a negative value, seen as `255`) = error: discard the
     output and the snapshot, apply nothing for that page, report it. A
     reconciled page goes back through 3b (within the remaining budget) and 4.
     `git merge-file` is never called in any other row. Pages in an unchanged row
     still apply normally.
   - **Step 6 log** adds per page `level=`, `prose=`, `reader=` (one of the six
     values), `unresolved=<n>`; lists excluded and `not-run(cap)` pages and the
     budget used.
   - **MUST NOT** additions: apply a draft over a destination not in an
     "unchanged" row; treat a merge error (status outside 0–127) as a
     reconciliation; apply a draft changed since its last review; rebaseline
     `.base` from a fresh read of the live page instead of the merge snapshot;
     reset `.reader_budget` on a re-entry to step 3; extend the fresh-reader
     budget without the user's explicit choice.

4. **Wrappers** — verified: no change needed (see Verification notes).

5. **`aitask-docs-gap` Step 6**: add `- **Target level:** <depth> · <page type>`
   after `**Target doc page(s):**` in the gap template, plus one sentence: pick the
   level and page type from the guide's level model (its `## Reader levels` and
   page-type rules); if the guide has none, write `not set (guide has no level
   model)`. Re-run `bash tests/test_docs_vocabulary_coverage.sh` and
   `bash tests/test_followup_kind_seams.sh` (both scan this file).

6. **Website page** `website/content/docs/skills/aitask-doc-review.md`
   (`depth: [intermediate]`, `maturity: [experimental]`): what it is for, when the
   gate runs it, ad-hoc use, what the report means (`reader=` values in plain
   words), budget. Add a row to `website/content/docs/skills/_index.md` under
   "Gates" (hand-curated table). Add a short line on the gate page
   `skills/aitask-gate-docs-updated.md` ("How it decides what to write" → drafts
   are reviewed before you confirm). Run
   `cd website && python3 check_links.py --build`.

7. **Dry runs** in the scratchpad (scratch copy of a few docs pages; the gate
   steps 3–5 followed by hand with a fake run id, no ledger writes):
   - reviewed-draft run on a `main-concept` page (e.g. a copy of
     `concepts/plans.md`): `.draft` + `.base` → 3b (`reader=subagent`) → Adjust
     with a body change → re-review → apply; `cmp` applied page vs last reviewed
     draft; ≤3 fresh-reader tests total;
   - modified-clean, modified-conflicting (merge exits 1, markers resolved,
     `grep` finds none), created, deleted — each mutating the destination after
     drafting, with one unchanged page in the same run still applying;
   - **modified, edit between merge and rebaseline**: after the merge has read
     `.snapshot`, append a distinct line to the live destination, then finish the
     rebaseline (`mv .snapshot .base`). Next apply: live ≠ `.base` → modified row
     again → second merge; the final page contains the intervening line (`grep`).
     Control in the same run: with a re-copied `.base` (the rejected way) the
     next apply would take the unchanged row and the line would be gone — show
     that once, then discard it;
   - **budget across a return to step 3**: in the created-page run, first spend
     2 of the 3 tests on beginner pages, then trigger "created" → step 3 → 3b:
     `.reader_budget` reads `1` after re-entry (not `3`), and a second beginner
     page beyond it gets `reader=not-run(cap)`;
   - no-level-model run: scratch dir with `.aitask-scripts` symlink and a
     `project_config.yaml` pointing `doc_update.guide` at a copy of
     `seed/doc_update_guide.md`; resolver prints that path; log shows
     `level=not-run(no-level-model)` / `reader=not-run(no-level-model)`.
   Record each run's summary in Final Implementation Notes.

### Post-phase (risk mitigations)

1. [doc_review_gate_contract_test] `tests/test_doc_review_contract.sh`,
   self-contained (sources `tests/lib/scratch_cwd.sh`, `asserts.sh`; top-level
   asserts, no subshell bodies, so no counter opt-in needed). Structure: a
   `check_contract <gate_file> <skill_file> <guide_file>` function that prints one
   `CHECK:<name>:ok|fail` line per check (pure grep/awk over the files, sections
   extracted by `### N` headings); the test asserts every check is `ok` on the
   real files. Checks: review step `### 3b` between `### 3` and `### 4`; step 3
   names `.draft` and `.base` under `docs_updated_<run-id>_drafts/`; Adjust and
   reconciliation re-review; step 5 names all five states; every `git merge-file`
   line is in step 5 and in the "modified" row; created/deleted rows send back to
   step 3 and do not mention merge-file; `1`–`127` and the error-applies-nothing
   rule; the modified row merges from `.snapshot` and the snapshot (not the live
   page) becomes the new `.base`; the budget is written only when
   `.reader_budget` does not exist and step 3 re-entry keeps it; skill calls `aitask_resolve_config_path.sh doc_update.guide`; skill names
   `## Reader levels` and no other `## ` heading of the guide; no guide
   `## Prose rules` bullet (full text, nor its first 60 characters) appears in
   the skill; gate step 6 names `reader=` with all six values; budget 3,
   cumulative, most-changed-first, "Run more fresh-reader tests", never in
   autonomous profiles; no-level-model skips level check and fresh-reader.
   **Controls, classified per check:** gate checks run against the pre-change
   gate (`git show 9baf1dcb…:.claude/skills/aitask-gate-docs-updated/SKILL.md`
   into the fixture root) and each must be `fail` (assert per check name);
   skill/guide checks are exercised by mutants of the new skill in the fixture
   root (pasted prose bullet → no-dup check fails; resolver line removed →
   resolver check fails; an extra guide heading named → interface check fails;
   one `reader=` value removed → six-values check fails). If the pinned object is
   absent (shallow clone), print `SKIP:` for the gate control only.

## Verification

- `bash tests/test_doc_review_contract.sh` passes; its controls fail as expected.
- `bash tests/test_resolve_config_path_cli.sh`, `bash tests/test_gate_procedure_docs.sh`,
  `bash tests/test_docs_vocabulary_coverage.sh`, `bash tests/test_followup_kind_seams.sh` pass.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `cd website && python3 check_links.py --build` exits 0.
- Dry-run summaries recorded in Final Implementation Notes.

## Post-implementation

Step 9 (review, commit `enhancement: … (t2258_2)`, archival). Suggest
Codex/OpenCode port tasks for `aitask-doc-review` (child 8 creates them).

## Risk

### Code-health risk: medium
- The `docs_updated` gate gains a draft/review/merge path that every gated doc update runs; an ambiguous step degrades all of them, and sub-agent runs add time and tokens · severity: medium · → mitigation: inline pre-phase gate_review_cost_bound; inline post-phase doc_review_gate_contract_test
- Rebaselining after a merge from a fresh read of the live page would hide an edit made between merge and rebaseline, and the next apply would overwrite it (user review, reproduced in scratch) · severity: high · → mitigation: addressed in Step 3 (snapshot is the merge input and the new `.base`), Step 7 dry run, Post-phase check
- Re-entering step 3 from step 5 would reset a spent fresh-reader budget (user review) · severity: medium · → mitigation: addressed in Step 3 (`.reader_budget` written once per run id), Step 7 dry run, Post-phase check
- The contract test pins wording; later rewording of the gate breaks it without a behaviour change · severity: low · → mitigation: none separate; check names say what each guards, so a failure points at the rule, not a phrase
- Existing tests read the gate and docs-gap skill text (`test_resolve_config_path_cli.sh`, `test_docs_vocabulary_coverage.sh`, `test_followup_kind_seams.sh`) · severity: low · → mitigation: none separate; re-run in Verification

### Goal-achievement risk: medium
- A static text test cannot show an agent actually follows the longer gate (drafts, merge, re-review) · severity: medium · → mitigation: none separate; the recorded dry runs in Step 7 exercise every destination row and the no-level-model path
- The fresh-reader sub-agent is in effect an expert even with a persona · severity: medium · → mitigation: parent's reader_test_baseline_and_control (child 3), not this child

No new mitigation candidates: every risk above is covered by the parent's
confirmed inline phases, this plan's Verification, or a sibling's phase.
