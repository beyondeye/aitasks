---
Task: t1468_2_set_followup_kind_at_creation_seams.md
Parent Task: aitasks/t1468_mark_followup_task_provenance_and_surface_on_board.md
Sibling Tasks: aitasks/t1468/t1468_1_*.md, aitasks/t1468/t1468_3_*.md, aitasks/t1468/t1468_4_*.md, aitasks/t1468/t1468_5_*.md, aitasks/t1468/t1468_6_*.md
Archived Sibling Plans: aiplans/archived/p1468/p1468_*_*.md
Base branch: main
Output branch: main
---

# p1468_2 — Set `followup_kind` at every creation seam

Full seam table and context are in
`aitasks/t1468/t1468_2_set_followup_kind_at_creation_seams.md`. Read
`aiplans/archived/p1468/p1468_1_*.md` (once landed) for the flag's exact
spelling and validation behaviour.

**Precondition:** t1468_1 has landed — `--followup-kind` exists on
`aitask_create.sh` and the vocabulary file is in place.

## Implementation steps

### 1. The shared creation contract

`.claude/skills/task-workflow/task-creation-batch.md` is the **source** file. It
carries a `.md` extension but *is* Jinja-rendered by the closure dep-walker —
only skill entry points use `.md.j2`; transitively-referenced procedure files
stay `.md` and are rendered anyway.

1.1 Confirm the `followup_kind` row exists in the Input table (`:7-23`) — t1468_1
adds it. Do not duplicate it.
1.2 Add the flag to `### Optional flags` (`:115-124`), which documents itself as
"Append these flags before `--desc` or `--desc-file` when provided".

### 2. The nine skill caller sites

Each caller names `followup_kind: <value>` in its parameter list, exactly as it
already names `followup_of`.

| caller | site | value |
|---|---|---|
| `task-workflow/risk-mitigation-followup.md` Part 2 | `:385-392` | `risk_mitigation` |
| `task-workflow/risk-mitigation-followup.md` Part 3 | `:505-515` | `risk_mitigation` |
| `task-workflow/upstream-followup.md` | `:67` | `upstream_defect` |
| `aitask-qa/follow-up-task-creation.md` child branch | `:32-41` | `qa_test_gap` |
| `aitask-qa/follow-up-task-creation.md` parent branch | `:48-57` | `qa_test_gap` |
| `aitask-review/SKILL.md.j2` single | `:183` | `review_finding` |
| `aitask-review/SKILL.md.j2` parent | `:199` | `review_finding` |
| `aitask-review/SKILL.md.j2` children | `:213` | `review_finding` |
| `aitask-docs-gap/SKILL.md` | `:160-170` | `docs_gap` |

**Both** QA branches and **all three** review sites — the easy mistake is doing
one of each and moving on.

`aitask-docs-gap` inlines a raw `aitask_create.sh --batch --commit` command
rather than referencing the shared procedure (no `--gates` injection, no
`followup_of`). Add the flag inline and leave a comment naming the divergence.
Do **not** convert it to use the template here — that changes its gate-declaration
behaviour and belongs in its own task.

### 3. The three shell helpers

| helper | site | value |
|---|---|---|
| `aitask_create_manual_verification.sh` | `create_args` `:108-131` | `manual_verification` |
| `aitask_archive.sh` `create_carryover_task()` | `create_args` `:602-610` | `carry_over` |
| `aitask_verification_followup.sh` | `:208-216` | `verification_failure` |

All three build an args array; append the flag there rather than editing the
invocation line.

Note the carry-over is `carry_over`, **not** `manual_verification`, even though
it is created with `--type manual_verification`. The kind describes *how the task
came to exist*; the type describes *how it is worked*.

### 4. Independent fix — `upstream-followup.md` topic anchoring

`upstream-followup.md` passes no `--followup-of`, which is why 58 follow-ups are
topic roots and cannot cluster with their origin in the board's By-Topic view.
Add it, passing the origin task id.

Copy the fail-safe shape from `aitask_verification_followup.sh:200-206`: build
the argument conditionally on the origin resolving, so an unresolvable origin
yields a topic root rather than an error.

### 5. Regeneration

```bash
./.aitask-scripts/aitask_skill_rerender.sh default
./.aitask-scripts/aitask_skill_rerender.sh fast
./.aitask-scripts/aitask_skill_rerender.sh remote
```

The driver takes a **positional** profile name (not `--profile`) and loops
`claude`, `codex`, `opencode` internally — so one call per profile, three calls
total. Use `--force` on the inner render if staleness is suspected.

- `task-creation-batch.md` itself has **no goldens**; its callers do. Regolden
  `tests/golden/procs/task-workflow/risk-mitigation-followup-*.md` and
  `tests/golden/skills/aitask-review/SKILL-*-claude.md`.
- `.gitignore:47` ignores the rendered trees, **but the three `remote` copies are
  force-tracked prerenders** and must be committed.
- **Stage with an explicit path allowlist.** The sweep touches dozens of files
  across three trees; never `git add -A`.
- `./.aitask-scripts/aitask_skill_verify.sh` (no flags) must be clean.

## Verification

The rendering sweep proves nothing on its own — a seam that omits the flag still
renders consistently and keeps `aitask_skill_verify.sh` green. Two **table-driven**
suites keyed by `(seam → expected kind)`:

1. **argv assertions**, three shell helpers. `tests/test_archive_carryover.sh:32-90`
   already stubs `aitask_create.sh` and logs argv — copy that harness. Assert the
   expected `--followup-kind` value for each helper. Add a **real-file**
   assertion for at least one (pattern: `tests/test_archive_carryover_anchor.sh`,
   which uses the real `aitask_create.sh` and asserts the emitted line).
2. **rendered-content assertions**, nine skill sites. Grep the **rendered**
   profile variants — not the source — for the expected value at each site. Make
   the table **exhaustive by construction**: fail if a listed seam is missing,
   *or* if a `Batch Task Creation Procedure` call site exists that the table does
   not name. Without that second half the suite silently stops covering new
   seams.

Plus:

3. `./.aitask-scripts/aitask_skill_verify.sh` — clean.
4. `bash tests/run_all_python_tests.sh` — read the **last** line.
5. End-to-end: drive the carry-over path for real and confirm the created file
   carries `followup_kind: carry_over`.
6. Confirm the new `--followup-of` in `upstream-followup.md` produces an
   `anchor:` line on a real upstream-defect task.

## Notes for sibling tasks

- The rendered-variant path shapes differ per tree: claude and opencode use
  `<skill>-<profile>-`, codex uses `<skill>-<profile>-codex-` under `.agents/`.
  t1468_4 and t1468_5 both rerender and hit the same asymmetry.
