---
Task: t1405_triage_agent_memory_store_into_aidocs.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
---

# p1405 — Triage the agent memory store into aidocs

## Context

The per-user auto-memory store at `~/.claude/projects/-home-ddt-Work-aitasks/memory/`
holds **148 memory files** plus a `MEMORY.md` index that is loaded into context
every session. Three problems, all verified during planning:

1. **The index is at its ceiling.** `MEMORY.md` is **17,138 bytes** against a
   ~17.1 KB compaction threshold; it was compacted in place on 2026-08-04 with
   all 148 entries retained. The next growth forces lossy truncation under time
   pressure.
2. **Memories go silently stale.** `project_python_runner_k_filter_runs_nothing`
   asserted the framework venv has no pytest; that flipped on 2026-08-03 when the
   dev tier landed. Nothing re-validates an always-loaded memory.
3. **The entrypoints have diverged.** `CLAUDE.md` references `aidocs/framework/`
   **23 times**; `AGENTS.md` **0 times**. Every specialist rule reaches Claude
   Code and none reaches Codex CLI / OpenCode — while the memory store that
   partially compensates is per-user, per-agent, and outside git.

The store is the wrong home for most of its content: ~110 of the 112 `feedback`
memories are durable, agent-agnostic engineering conventions. This task applies
the repo's own governing principle (`feedback_prefer_source_enforcement_over_memory`)
to the store itself: durable conventions move into `aidocs/framework/*.md`, read
on demand via trigger lines reachable from **both** entrypoints; the store keeps
only operator-/machine-specific facts and live coordination state.

### Ground truth established during planning

| Fact | Evidence |
|---|---|
| 148 memories: 112 `feedback`, 35 `project`, 1 `user` | `grep -h "^  type:" *.md \| sort \| uniq -c` (+2 files with a non-standard `type:` line) |
| **The store grew to 149 files / 17,261 bytes *during this planning session*** | `project_t1224_done_unblocks_t1109.md` appeared at 12:43 — the store has a concurrent writer |
| `MEMORY.md` = 17,138 bytes, 148 index lines, **zero orphans both ways** (at first measurement) | `comm` of index targets vs `ls *.md` |
| **140 of 148 memories carry `[[wikilinks]]`; 82 distinct targets; 3 already dangling** | `grep -oh '\[\[...\]\]' \| sort -u` vs file list |
| **`AGENTS.md` is 100% machine-generated** — all 90 lines sit between `>>>aitasks`/`<<<aitasks` and are byte-identical to `seed/aitasks_agent_instructions.seed.md` | `sed '1d;$d' AGENTS.md \| diff - seed/…` → identical |
| Regenerated unconditionally by `update_agentsmd()` (`.aitask-scripts/aitask_setup.sh:1371`, called at `:2501`) | source read |
| Out-of-marker prose **survives** `ait setup` | `tests/test_agent_instructions.sh` T21 |
| `.codex/instructions.md` (93 ln) and `.opencode/instructions.md` (89 ln) are separately generated, also fully marker-wrapped, and do **not** include AGENTS.md | source read |
| **`aidocs/` never ships to bootstrapped projects** — not in `install.sh` staging, not in packaging | pointers must NOT go in the seed |
| `aidocs/framework/` has **no index/README**, and **no guard** ties a doc to a CLAUDE.md trigger | `model_reference_locations.md` is referenced nowhere in CLAUDE.md — living proof |
| aidocs house style: one `##` per rule, heading = a full sentence stating the rule, rule paragraph then rationale paragraph, task IDs cited **sparingly** | `code_conventions.md`, `planning_conventions.md`, `tui_conventions.md` |
| `documentation_conventions.md` scopes itself to **user-facing** prose and does not govern `aidocs/` itself | its preamble |
| Doc sizes: `code_conventions.md` 1.7 KB/1 §, `testing_conventions.md` 3.6 KB/2 §, `planning_conventions.md` 7 KB/8 §, `shell_conventions.md` 4.7 KB/flat bullets, `tui_conventions.md` 30 KB/24 §, `skill_authoring_conventions.md` 34 KB/18 § | `wc -c` + heading scan |

**Only `aidocs/`, `CLAUDE.md`, `AGENTS.md`, `.codex/`, `.opencode/` and `tests/`
changes are committable.** The memory store lives outside the repo, so its
deletions and `MEMORY.md` rewrite appear in no diff — say so in every child's
Final Implementation Notes so the commit is not mistaken for the whole deliverable.

## Approach

Decompose into **7 children, run in a strict chain** (`t1405_2 depends:
[1405_1]`, `t1405_3 depends: [1405_2]`, … `t1405_7 depends: [1405_6]`) so only
one ever writes the store. Child 1 is the triage + infrastructure spike: it
freezes and classifies the inventory, builds the doc/entrypoint/guard
scaffolding, and proves the condensation format before the bulk promotion work.
Children 2–7 each own one cluster end-to-end (re-verify claims → user rules on
each memory → write entries → delete the ruled files → drop their `MEMORY.md`
lines). Child 7 closes with the store-wide sweep.

Four decisions were confirmed with the user during planning:

- **Promoted memories are deleted outright**, not stubbed. The CLAUDE.md /
  AGENTS.md trigger lines become the only discovery path — and the index only
  reaches ≤10 KB if promoted entries leave it.
- **Four new docs** are created (below); everything else extends an existing doc.
- **All three generated entrypoints** get an out-of-marker pointer appendix,
  plus a parity guard test.
- **~7 children**, structured as below.

### New docs

| New file | Holds | Why not an existing doc |
|---|---|---|
| `aidocs/framework/README.md` | Canonical manifest: every `aidocs/framework/*.md` + its trigger, split into **entrypoint-advertised** vs **reachable-only** | No index exists; it is the manifest the parity guard checks against, and the split is what keeps universal exposure from becoming an accidental policy |
| `aidocs/framework/agent_memory_conventions.md` | The **retention rule** + the "new aidocs file vs new `##` section" rule | Needs its own trigger so it fires at memory-write time, which a `documentation_conventions.md` trigger would not |
| `aidocs/framework/state_and_concurrency_conventions.md` | ~21 derived-state / locking / supersession / lifecycle rules | `code_conventions.md` is 1.7 KB about source-trace comments; absorbing 21 runtime-state rules would give it a mixed remit |
| `aidocs/framework/concurrent_agent_sessions.md` | ~9 git/worktree hazards of running parallel agent sessions in one shared checkout | No existing doc covers shared-checkout git hazards; the framework spawns parallel agents by design, so this is framework-level, not operator-level |

### Entrypoint mechanics (load-bearing)

Pointers go **after** the closing `<<<aitasks` marker in `AGENTS.md`,
`.codex/instructions.md` and `.opencode/instructions.md` — never inside, where
the next `ait setup` awk-replaces them — and **never** in
`seed/aitasks_agent_instructions.seed.md`, because `aidocs/` does not ship to
user projects and every path would dangle there.

## Store concurrency: freeze the inventory, serialize the writers

The store is **live** and has a second writer this task does not control — the
auto-memory mechanism itself, which appends files and index lines mid-session and
will not honour any lock. This is not hypothetical: **the store grew from 148 to
149 files (`MEMORY.md` 17,138 → 17,261 bytes) during this planning session**, when
`project_t1224_done_unblocks_t1109.md` was written. Seven children editing the
same `MEMORY.md` compounds it.

Four rules, all binding on every child:

1. **Freeze a manifest.** Child 1's first act is to snapshot the inventory —
   `name`, byte size, and a content hash per file — into its plan. That frozen
   list *is* "the 148" (149 as of the freeze; child 1 records the real number).
   Every acceptance count is computed against it, not against a live `ls`.
2. **Arrivals after the freeze are out of scope.** A memory written after the
   snapshot is not triaged, not deleted, and not counted. Child 7 lists them
   separately as "arrived after freeze — unclassified", and they survive
   untouched. This is stated in the task's completion report so "all 148
   classified" is never quietly reinterpreted.
3. **Serialize the writers.** Children run in a strict chain —
   `t1405_2 depends: [1405_1]`, `t1405_3 depends: [1405_2]`, … so no two
   children ever hold the store at once. (Sibling auto-dependency alone does not
   guarantee this ordering; the chain is declared explicitly.)
4. **Never regenerate `MEMORY.md` wholesale from a remembered list.** Each child
   removes *exactly its own* index lines by matching the line's link target,
   immediately after re-reading the file — so a line another writer added in the
   meantime survives. Only child 7 rebuilds the index, and it rebuilds from
   **disk truth** (`ls *.md`), not from any in-context list.

## The per-memory decision gate (NON-SKIPPABLE — every child follows it)

No memory is promoted or deleted on the agent's own judgement. Each child runs
this three-phase loop over the memories it owns, and **the user rules on every
single one after seeing its re-verification result**.

**Phase 1 — Re-verify, then report.** For its whole cluster at once, the child
re-checks each memory's claim against current source and prints one compact
table, no decisions taken yet:

| memory | the claim | verified? | evidence (path:line / command output) | proposed | target § |
|---|---|---|---|---|---|

`verified?` is one of **HOLDS** / **FLIPPED** (the premise is now false) /
**UNVERIFIABLE** (no ground truth available). Evidence is a real path or command
output, never "looks right".

**Phase 2 — Rule on each memory, one at a time.** Paginated `AskUserQuestion`,
**four memories per call** (one question each), so a ~25-memory cluster is ~7
calls. Each question names the memory, its `verified?` verdict, and the one-line
evidence. The options are the task's four dispositions plus a look-first escape:

- **"Promote"** → disposition **PROMOTE**. Write the drafted `##` entry into the
  target doc as its own section, then delete the memory file.
- **"Merge into `<doc>#<heading>`"** → disposition **MERGE**. The memory folds
  into a *named existing or sibling-cluster* section rather than getting its own
  — the negative-control family, the `project_concurrent_*` family, the tmux
  OSC-52 clipboard fact folding into `tui_conventions.md`'s existing clipboard
  section, the Fable-5 narration fact folding into the existing AskUserQuestion
  visibility rule. The question names the exact destination heading, and the
  triage table keeps the **source → merged-section mapping** so a later session
  can see which sources produced a combined entry.
- **"Delete — no promotion"** → disposition **DISCARD**. Delete the memory file,
  write nothing to the docs. Available **regardless of the verdict**, including
  for memories that verified HOLDS: a claim being true is not a reason to keep
  it, and the user may simply not want it in the repo docs.
- **"Keep as memory"** → disposition **KEEP**. Leave the file and its index line
  untouched; it counts toward the surviving-file total.
- **"Show me the drafted entry"** — print the exact prose that would be written,
  then re-ask this same memory. No disposition is inferred from asking to look.

**UNVERIFIABLE items cannot be promoted or merged.** When Phase 1 reports
UNVERIFIABLE, the question offers only "Delete — no promotion" / "Keep as
memory" / "Show me the claim", because the task constrains unverifiable claims to
be *dropped rather than carried into a repo doc under false authority*. If the
user wants such an item promoted anyway, that is a change to the task's
constraints: amend the acceptance criteria in `aitasks/t1405_*.md` **first**,
then re-run that memory's gate — never deviate silently.

Nothing is written or deleted during Phase 2 — the child collects rulings first.
A memory with no explicit ruling is **not** actioned; if the loop is interrupted,
the unruled remainder stays in the store and the child says so.

**Phase 3 — Journal first, then execute.** For each ruling, in this order:

1. Append the ruling to the child's journal at
   `.aitask-memtriage/t1405_<child>.tsv` (git-ignored, per the existing
   `.aitask-*/` per-run convention — child 1 adds the rule to `.gitignore`).
   Seven tab-separated columns:

   ```
   name  verdict  ruling  target-doc#heading  reason  evidence  state
   ```

   `state` starts at `ruled`. `evidence` is empty for KEEP/DISCARD; for
   **PROMOTE and MERGE it is a verbatim, single-line, tab-free excerpt of ≥40
   characters** taken from the text actually written — the load-bearing clause
   of the new section, or of the merged-in paragraph.
2. Apply the doc edit and/or the file deletion and the `MEMORY.md` line removal.
3. Rewrite that row's `state` to `done`.

**Why an excerpt and not just the heading.** A heading existing at the
destination proves nothing about *this* memory: for MERGE the heading pre-exists
by definition, and for PROMOTE a re-run or a same-named section from another
child would satisfy a heading check while the actual text never landed. The
excerpt must be found **inside that section's span**, so a coincidental match
elsewhere in a 30 KB doc cannot stand in for it.

The journalled heading is the **verbatim** heading text, backticks and all —
e.g. ``Clipboard copies route through `lib/tui_clipboard.copy_to_system_clipboard` ``.
The matcher compares headings by exact string equality, so a paraphrased or
backtick-stripped heading reads as "section missing".

The span matcher was **run against the real docs during planning** and proved to
discriminate on all six cases: an excerpt from its own section (found), one from
a neighbouring section (rejected), a non-existent heading (rejected), an empty
excerpt (rejected), a `# comment` inside a fenced code block (does *not*
truncate the span), and the span ending correctly at the next heading. Two of
those were bugs found by running it rather than reading it: `index(buf, "")`
returns **true**, and an unguarded `^#` pattern reads shell comments in fenced
blocks as headings.

A resumed run reads the journal, **skips every row already `done`**, and re-does
only `ruled` rows — each step is idempotent (deleting an absent file, removing an
absent index line, and re-adding an already-present `##` section are all no-ops
after a content check). At the end the child copies the journal rows into its
plan's triage table, which is the committed audit trail.

**A force-deleted memory's body is not copied into the plan.** The plan is
committed, so archiving the verbatim text would push into the repo exactly the
content that "Delete — no promotion" may have been chosen to keep out. The
triage-table row is the record. If the user wants a particular body preserved
anyway, they say so at ruling time and the child writes it to a path they name.

The same gate governs child 1's **DISCARD** deletions: verified-stale is a
proposal, not a licence — the user still rules on each one.

## Decomposition-time actions (before any child is picked)

**Amend the task's acceptance criteria.** `aitasks/t1405_*.md` says "all 148"
in three places (Goal, Dispositions preamble, first AC bullet) and the store is
already at 149. Rewrite those to *"every memory in child 1's frozen manifest
(count recorded at freeze), with any file that arrived after the pinned 148
baseline named explicitly and excluded from triage"*. Doing this at decomposition
time — rather than letting a child reinterpret "148" mid-flight — is what keeps
the scope change explicit instead of silent.

## Child tasks

Each child: run the decision gate above; for anything ruled **Promote**,
condense to aidocs house style (`##` heading = the rule as a sentence; rule
paragraph, then rationale), dropping the "surfaced in tNNN / the user rejected…"
narrative and keeping a task id only where it is a useful evidence anchor; then
delete the promoted memory files and their `MEMORY.md` lines. **A claim that
cannot be re-verified is never promoted silently** — it is reported as
UNVERIFIABLE in Phase 1 so the user rules on it with that fact in hand, and
whatever is dropped is listed in the child's Final Implementation Notes.

### t1405_1 — Triage table, retention rule, and pointer infrastructure

Deliverables:

0. **Freeze the manifest first, before reading anything.** Snapshot
   `name / bytes / content-hash` for every file in the store into this child's
   plan; that frozen list defines the classified set for all seven children.

   **Reconcile it against the 148 baseline in the same step.** The task text
   says 148; planning observed 149. Compute the delta against the baseline
   captured in this plan's Ground-truth table and name every file on both sides:

   The **148 baseline is pinned by digest**, so it is checkable rather than
   remembered. As of 2026-08-04 12:50 the store held 149 files; removing the one
   known post-start arrival, `project_t1224_done_unblocks_t1109` (written 12:43),
   leaves exactly 148 names whose sorted list digests to:

   ```
   sha256 = 84db208094ef3b8997b79efc39c0288d3324475dbe8539ede7bfcc5f2c66207d
   ```

   Child 1 confirms the baseline and enumerates any further drift:

   ```bash
   cd ~/.claude/projects/-home-ddt-Work-aitasks/memory
   ls -1 *.md | grep -v '^MEMORY.md$' | sed 's/\.md$//' | sort > frozen.txt
   # subtract the arrivals named below, then the digest must match
   grep -vxF -f arrivals.txt frozen.txt | sha256sum      # expect 84db2080…
   comm -13 baseline.txt frozen.txt                      # arrived since baseline
   comm -23 baseline.txt frozen.txt                      # disappeared since
   ```

   If the digest matches with only `project_t1224_done_unblocks_t1109` removed,
   the baseline is confirmed and that file is the sole arrival. If it does not,
   child 1 bisects the remaining difference and **names every additional
   arrival** before proceeding. Either way the delta is an explicit list, which
   is what makes the final audit provable instead of a count that drifted.

   Then classify **the frozen manifest**, whatever N it contains, and carry the
   named delta into child 7's report. The task's `all 148` wording is amended at
   decomposition time (see below) so this is a stated scope decision, not a
   silent reinterpretation of the acceptance criteria.

   Also add `.aitask-memtriage/` to `.gitignore` (alongside the existing
   `.aitask-*/` per-run entries) for the rulings journals.

1. **The triage table — all 148 memories, one *proposed* disposition + one-line
   reason each**, written into this child's plan file. Include a machine-readable
   block
   (`name<TAB>type<TAB>proposed<TAB>owning-child<TAB>target-doc#heading<TAB>reason`)
   so child 7 can mechanically diff executed dispositions against the store.
   Every memory is assigned to exactly one owning child — this is what stops a
   memory falling between two clusters. The table is a **proposal**: the binding
   disposition for each memory is the user's ruling in that memory's decision
   gate, recorded back into the owning child's plan (a `ruled` column alongside
   `proposed`, so a divergence between the two is visible in the audit).

   **The destination is recorded as `doc#heading`, not just `doc`.** The heading
   is provisional at triage and becomes exact at ruling time (Phase 3 journals
   the final one). This is what lets child 7 rewrite a `[[wikilink]]` into a
   reference that actually resolves, instead of a vague pointer at a 30 KB file;
   for a MERGE it is also the source → merged-section mapping.
2. **Verify DISCARD candidates.** Use `aitask_query_files.sh task-status <id>`
   (archived resolves to `Done`) and `archived-task <id>` (it searches inside the
   `aitasks/archived/_b*/old*.tar.zst` bundles). Do **not** use
   `archived-children` — it does not look inside the bundles.
   Already verified during planning:

   | Memory | Verdict |
   |---|---|
   | `project_t891_deferred_behind_t756` | DISCARD — t891, t891_5 and t756 all archived |
   | `project_t929_carveout_dropped` | DISCARD — t929 + children archived |
   | `project_t986_2_postponed_shadow_not_phase_gated` | DISCARD — t986_2 was **deleted**, never implemented (commit `027ffcf94`) |
   | `project_t986_4_shadow_user_invocable_capture` | DISCARD — t986_4 and parent t986 archived; check `aidocs/framework/shadow_agent.md` already covers the contract |
   | `project_t952_5_guard_scope_layer_split` | DISCARD — t952_5 + parent archived |
   | `project_t635_29_split_procedure_gate` | **KEEP** — t635_29/31/32 all still `Ready` |
   | `feedback_geminicli_to_agy_migrate_dont_close`, `project_agy_cli_no_model_flag` | **KEEP** — the whole t835 tree (parent + 7 children) is still `Ready` |

3. **`aidocs/framework/README.md`** — the canonical manifest, indexing all 18
   existing docs + the 4 new ones with a trigger sentence each, split into **two
   explicitly-labelled lists**:
   - **Entrypoint-advertised** — docs that must be reachable from `CLAUDE.md`
     *and* all three appendices. The promoted docs go here.
   - **Reachable-only** — docs deliberately kept out of every agent context,
     reached instead from a sibling doc or a skill: the audit/design-spec files
     (`model_reference_locations.md`, `agent_runtime_guards_audit.md`,
     `python_tui_performance.md`) and `sed_macos_issues.md` (already reached via
     the `shell_conventions.md` trigger).

   The split is the policy statement: universal exposure is **not** the rule, so
   adding an audit doc later does not force it into every agent's context.
4. **`aidocs/framework/agent_memory_conventions.md`** — the retention rule:
   what earns a memory (operator-/machine-specific facts; live coordination
   state that names the task it dies with) vs. what belongs in `aidocs/`
   (anything durable and agent-agnostic); when a `project_*` memory must be
   deleted (when the tasks it names archive) and how to check; the rule that a
   memory must never restate a skill contract (cross-ref the promoted
   `feedback_prefer_source_enforcement_over_memory` entry); and the
   new-file-vs-new-`##`-section rule for `aidocs/framework/`.
5. **Out-of-marker `## Specialist rules (aidocs/framework)` appendix** appended
   after `<<<aitasks` in `AGENTS.md`, `.codex/instructions.md`,
   `.opencode/instructions.md`, listing every doc + trigger.
6. **`tests/test_aidocs_pointer_parity.sh`** — checks the manifest, not a
   blanket rule. Three assertions:
   - every `aidocs/framework/*.md` appears in `README.md` **exactly once**, in
     one of the two lists (so no doc goes unindexed — a repo-internal check that
     costs no agent context);
   - every doc in the **entrypoint-advertised** list is referenced from
     `CLAUDE.md` and from each of the three appendices;
   - every doc in the **reachable-only** list has at least one in-repo referrer
     (`grep -rl` outside `aidocs/framework/README.md` itself).

   `README.md` is exempt from the first assertion — it is the manifest, so
   listing itself is meaningless — but it **is** required in all four entrypoint
   surfaces, since it is the index that makes the rest discoverable.

   Ship a **negative control** proving the guard discriminates: remove one
   entrypoint-advertised doc's pointer from one appendix in a temp copy and the
   test must exit 1 naming that doc. Also prove the harness itself can fail
   (`feedback_prove_test_harness_can_fail`) — a passing negative control means
   the test is wrong, not the docs.

   The guard will initially flag `model_reference_locations.md`: it is referenced
   from skills and the website but not `CLAUDE.md`. Classify it
   **reachable-only** rather than inventing a trigger for it — it is a
   design-spec audit, not a convention.
7. **CLAUDE.md**: triggers for the 4 new docs; **widen the
   `testing_conventions.md` trigger**, which today reads "when designing tests
   for a threading / asyncio migration" and will be badly under-scoped once
   child 2 lands ~25 general testing rules.
8. **Run the decision gate over the DISCARD candidates** and execute the
   rulings (files + index lines), recording each ruling in the triage table.

### t1405_2 — Testing & verification cluster → `testing_conventions.md` (~25)

Includes the 6-file **negative-control family** merged into one coherent
progression — harness-can-fail → discriminates → one-mutation-per-test →
restore-without-`git checkout` — rather than six near-duplicate sections:
`feedback_prove_test_harness_can_fail`, `feedback_negative_control_for_structural_guards`,
`feedback_negctrl_proves_test_discriminates`, `feedback_negctrl_failing_for_the_wrong_reason`,
`feedback_negctrl_one_mutation_per_test`, `feedback_negctrl_restore_without_git_checkout`.

Plus: independent ground truth, probe-the-real-class, real-entrypoint + live
acceptance, weakest-surface universal claims, executable test specs, run-your-
verification-commands, seed-before-asserting-cleanup, drive-the-uninstalled-
backend, isolation refusal guard, guard-probe robustness, impact-survey
discrimination, behavioral fixtures + autonomous MV, characterization flip
contract, shell-command tests & subprocess hygiene, real-platform semantics,
perf-gate measurement contract.

`project_python_runner_k_filter_runs_nothing` is the store's **known-stale
exemplar**: promote only the half that is still true (`-k` runs zero tests on the
`unittest` fallback; a positional path *widens* the run), drop the false pytest-
absent premise, and check against what CLAUDE.md's Testing section already says
so the rule is not written twice.

### t1405_3 — Code & API design cluster → `code_conventions.md` (~21)

Abstraction-contract completeness, contract fields never temporarily untrue,
scope-honest naming + rich returns, default-new-params-in-the-helper, encapsulate
cleanup in the model, reuse the canonical seam, substrate-promotion criteria,
stable handle vs mutable manifest, bucketed domains + operation-qualified ids,
name transitional duplication, role-specific eligibility, narrow excepts that
never fail open, enumerate every failure signal, audit the full lifecycle when
adding a mode, root-scoped APIs reject ambient state, config keys are not
strings, lexical provenance before resolve, derive-don't-duplicate + guard,
structural fix over fragile invariant, per-surface labels, canonicalize identity
keys on both sides.

Add a preamble cross-pointer to the new `state_and_concurrency_conventions.md`,
matching how `code_conventions.md` already points at `sed_macos_issues.md` /
`shell_conventions.md`.

### t1405_4 — Derived state & concurrency → new `state_and_concurrency_conventions.md` (~21)

Derived-state provenance stamps, derived-tuple integrity, single-source
per-tick derived sets, ephemeral state out of the task record, edit surfaces
over derived state, partial-edit merge contracts, replay from the persisted
record, dedup keys from two pipelines, conflict-over-silent-guess merges,
atomicity ≠ serialization, fail-safe owner-token mutexes, fail-safes armed at
acquisition, supersession-token completeness, prevent (not just discard)
superseded work, snapshot trigger state before the await, deferred-launch
lifecycle, repo-scoped reaper ownership, trigger/marker hygiene,
passive-observation invariants, bounded recovery envelopes, concurrency safety
contracts.

Cross-reference `testing_conventions.md` (which already owns "designing tests
for a threading/asyncio migration") in both directions.

### t1405_5 — Planning & plan review → `planning_conventions.md` (~20)

Distributed-correctness plan review, re-derive constants + helper semantics,
self-contained child plans, testability-first decomposition, spike-first
decomposition + crash ownership, exclusion dispositions + single-sourced
ordering, no silent AC deviation, bidirectional task links, blast-radius
assessment before implementing, defer removal when the feature is a model,
parallel surfaces + context threading, verify path/shared-renderer assumptions,
enumerate the full injection surface, perf-gate results need user confirmation,
fallbacks need a reachable trigger, honor the task's own safety gate.

Plus `project_decomposed_parent_skips_step8d_mitigations` (a framework behavior:
a decomposing parent never auto-creates "after" mitigations — create them at
decomposition time).

### t1405_6 — TUI + shell/security + skill authoring (~27)

- **→ `tui_conventions.md`**: render-level verification, real-terminal
  (tmux) proof for visibility claims, visible ≠ readable, checkbox glyphs for
  marks, hover-on-focus accent shade, context-scoped single-key shortcuts,
  action guard ≠ binding gate, live glyph over frozen state + tick wiring,
  footer relabel via duplicate-key bindings, `Pilot.pause()` ≥20 ms, tmux OSC 52
  visible-pane-only (fold into the doc's existing clipboard section), one-TUI-
  per-window terminology.
- **→ `shell_conventions.md`** (flat-bullet style, matching that file):
  quoting cannot secure substitution, line-oriented tools cannot see newlines,
  sanitize delimiters at the write site.
- **→ `skill_authoring_conventions.md`**: contract lives in the executable
  block, engine-owned deterministic seam over agent detection, workflow bash
  belongs in a whitelisted helper, source enforcement over memory, skill latency
  + auto-detect over prompting, explicit composition rule, explicit mode
  selector, offer the triggered action immediately, don't infer staticness from
  invocability, closure changes auto-render (cross-agent ports are usually
  no-ops), `aitask_skill_rerender.sh` takes a profile arg. Fold the Fable-5
  invisible-narration fact into that doc's **existing** "AskUserQuestion
  visibility rule" section rather than adding a parallel one.

### t1405_7 — Documentation + gates + shared-checkout hazards, then the final sweep (~22)

- **→ `documentation_conventions.md`**: document the current source not a stale
  plan, prefer a cross-referenced doc over a narrow source-scan guard, document
  guards per case, re-sweep docs after a mid-task pivot, generic example project
  names, no "sister repo" wording, user artifacts follow generic conventions,
  the hand-curated `website/content/docs/workflows/_index.md` list, chat-platform
  setup docs live in `aidocs/`.
- **→ `aidocs/gates/`** (a directory that already exists — pick the right file
  there, or extend it): gate producer/checker split, sentinel-gated inline
  fallback, `risk_evaluated` needs `### Code-health risk` H3 subsections with
  `max_retries 0`, `docs_updated` is an agent procedure not a heuristic checker.
- **→ new `aidocs/framework/concurrent_agent_sessions.md`**: the five
  `project_concurrent_*` memories merged into one coherent doc (data-branch
  divergence, pre-staged index, worktree hunks landing between diff and `git
  add`, commit rewrites dropping your paths, stash wipes), plus main HEAD
  advancing mid-session, `cp -a` leaking worktree commits, `ait git push`
  exiting 0 while doing nothing, and `git revert` reverting the worktree.
- **Final store sweep:**
  1. Diff executed dispositions against the **ruled** column across all seven
     child plans — every one of the 148 must carry an explicit user ruling, and
     the count of surviving files must equal the count ruled "Keep as memory".
     Any memory that reached no ruling is reported, not guessed at.
  2. **Rewrite dangling `[[wikilinks]]`** in the survivors: 140 of 149 files
     carry them and 82 distinct targets exist, so mass deletion strands links
     that recall follows. Replace each link to a promoted/merged memory with its
     journalled `doc#heading` destination — the exact section that absorbed it,
     never a bare filename — and clear the 3 links already dangling today.
     Then **verify every rewritten reference resolves**: for each `doc#heading`
     emitted, assert the file exists and that an `^#{1,6} <heading>` line is
     present in it. Any unresolved destination is a failure, not a warning.
  3. Regenerate `MEMORY.md` from disk truth: one line per surviving file, no
     orphans in either direction (`comm` both ways).

     **The ≤10 KB criterion resolves by a decided ladder, not by reporting.**
     The index currently averages ~116 bytes/line (17,261 B over 149 lines), so
     even 80 survivors land near 9 KB and the projected ~35 lands near 4 KB —
     an overage is unlikely but must have a defined exit:
     1. If the regenerated index is ≤10 KB — done.
     2. If not, run an **index-hook compaction pass**: shorten the one-line
      hooks (the text after the `—`) in place. This deletes no memory and
      overrides no ruling, and roughly halves line length. Re-measure.
     3. If it is *still* over, stop and put the numbers to the user with two
      named choices: amend the task's ≤10 KB criterion (editing the AC in
      `aitasks/t1405_*.md` before proceeding, per "no silent AC deviation"), or
      re-rule specific KEEP memories. **A user's "Keep as memory" ruling is
      never overridden to hit a size target** — but the task does not end
      quietly incomplete either; it ends on an explicit user decision. If the
      user amends the criterion, record it as
      `.aitask-memtriage/size_override_approved` (containing the approved
      ceiling and the reason) — the acceptance script checks for that file
      rather than letting an overage pass silently.
  4. Run `bash tests/test_aidocs_pointer_parity.sh` — every promoted doc
     reachable from CLAUDE.md and all three appendices.

## Verification

Per-child (each promotion child):

```bash
# every source path cited by a promoted entry still exists — exits 1 if not
missing=$(grep -o '`[^`]*\.\(sh\|py\|md\|json\|yaml\)`' aidocs/framework/<doc>.md |
          tr -d '`' | sort -u | while read -r f; do [ -e "$f" ] || echo "$f"; done)
[ -z "$missing" ] || { printf 'DEAD REFS:\n%s\n' "$missing" >&2; exit 1; }
```

**Whole-task acceptance (child 7) — an assertion script, not a diagnostic dump.**
Every check must set a non-zero exit; printing a mismatch and returning 0 is the
exact failure mode `feedback_test_verification_commands_before_relying_on_them`
warns about. Child 7 writes this as
`.aitask-memtriage/t1405_accept.sh` (git-ignored, alongside the journals):

```bash
#!/usr/bin/env bash
# NOT set -e: every check runs, then the accumulated status decides.
# STORE / REPO / J are env-overridable so the negative control can drive a
# throwaway fixture copy WITHOUT editing the script under test or touching
# live data. Defaults are the real paths.
set -uo pipefail
STORE="${T1405_STORE:-$HOME/.claude/projects/-home-ddt-Work-aitasks/memory}"
REPO="${T1405_REPO:-/home/ddt/Work/aitasks}"
J="${T1405_JOURNAL:-$REPO/.aitask-memtriage}"
rc=0
fail() { printf 'FAIL: %s\n' "$*" >&2; rc=1; }
tmp=$(mktemp -d) && trap 'rm -rf "$tmp"' EXIT || exit 2

cd "$STORE" || exit 2

# --- inputs -----------------------------------------------------------------
sort -u "$J/manifest_names.txt"       > "$tmp/manifest"   # child 1's freeze
sort -u "$J/post_freeze_arrivals.txt" > "$tmp/arrivals"   # out of scope
cat "$J"/t1405_*.tsv                  > "$tmp/journal"
cut -f1 "$tmp/journal" | sort -u      > "$tmp/ruled"
awk -F'\t' '$3=="KEEP" && $7=="done"' "$tmp/journal" | cut -f1 | sort -u > "$tmp/keep"
ls -1 *.md | grep -v '^MEMORY.md$' | sed 's/\.md$//' | sort > "$tmp/disk"

# 1. every manifest entry carries a ruling, and nothing outside it was ruled
[ -s "$tmp/manifest" ] || fail "manifest is empty — child 1 froze nothing"
unruled=$(comm -23 "$tmp/manifest" "$tmp/ruled")
[ -z "$unruled" ] || fail "manifest entries with no ruling:"$'\n'"$unruled"
extra=$(comm -13 "$tmp/manifest" "$tmp/ruled")
[ -z "$extra" ] || fail "rulings for names outside the frozen manifest:"$'\n'"$extra"

# 1b. every ruling actually completed — a `ruled` row means an interrupted or
#     failed mutation, which must NOT count as a disposition
notdone=$(awk -F'\t' '$7!="done" {print $1" (state="$7")"}' "$tmp/journal" | sort -u)
[ -z "$notdone" ] || fail "rulings never executed to completion:"$'\n'"$notdone"

# 1c. PROMOTE/MERGE rows must carry a destination and a verifiable excerpt
bad=$(awk -F'\t' '($3=="PROMOTE"||$3=="MERGE") &&
                  ($4 !~ /#/ || length($6) < 40) {print $1}' "$tmp/journal" | sort -u)
[ -z "$bad" ] || fail "PROMOTE/MERGE rows missing a doc#heading or a >=40-char excerpt:"$'\n'"$bad"

# 2. surviving files == ruled KEEP + post-freeze arrivals, exactly
sort -u "$tmp/keep" "$tmp/arrivals" > "$tmp/expected"
d=$(comm -3 "$tmp/expected" "$tmp/disk")
[ -z "$d" ] || fail "surviving files != KEEP + arrivals (left=expected right=disk):"$'\n'"$d"

# 3. index <-> disk, both directions
grep -o '](\([^)]*\))' MEMORY.md | sed 's/](//;s/)//;s/\.md$//' | sort -u > "$tmp/index"
d=$(comm -3 "$tmp/index" "$tmp/disk")
[ -z "$d" ] || fail "MEMORY.md index vs disk mismatch:"$'\n'"$d"
[ "$(grep -c '^- \[' MEMORY.md)" -eq "$(wc -l < "$tmp/disk")" ] \
  || fail "index line count != surviving file count"

# 4. size ceiling (the ladder's step 3 records an approved override here)
sz=$(wc -c < MEMORY.md)
if [ "$sz" -gt 10240 ] && [ ! -f "$J/size_override_approved" ]; then
  fail "MEMORY.md is $sz bytes (> 10240) with no recorded user approval"
fi

# 5. no dangling wikilinks
dang=$(comm -23 <(grep -oh '\[\[[a-z0-9_]*\]\]' *.md | sed 's/\[\[//;s/\]\]//' | sort -u) \
                "$tmp/disk")
[ -z "$dang" ] || fail "dangling wikilinks:"$'\n'"$dang"

# 6. the promoted/merged text actually landed: the journalled excerpt must be
#    inside the journalled section's span (not merely somewhere in the file)
while IFS=$'\t' read -r name dest excerpt; do
  doc=${dest%%#*}; heading=${dest#*#}
  [ -f "$REPO/$doc" ] || { fail "destination doc missing: $doc ($name)"; continue; }
  awk -v h="$heading" -v ex="$excerpt" '
    # Track fences FIRST: a "# comment" inside a bash block is not a heading,
    # and treating it as one silently truncates the section span.
    /^```/ { fence = !fence; if (ins) buf = buf $0 "\n"; next }
    !fence && /^#+[ \t]/ {
      n=0; while (substr($0, n+1, 1) == "#") n++
      t=$0; sub(/^#+[ \t]+/, "", t)
      if (ins && n <= lvl) ins=0          # next same-or-shallower heading ends it
      if (t == h) { ins=1; lvl=n; buf="" }
      next
    }
    ins { buf = buf $0 "\n" }
    # Both guards are load-bearing: index(buf, "") returns TRUE, so an empty
    # excerpt or an unmatched heading would otherwise pass vacuously.
    END { exit (ex != "" && buf != "" && index(buf, ex)) ? 0 : 1 }
  ' "$REPO/$doc" \
    || fail "excerpt for '$name' not found under $doc#$heading — the edit did not land"
done < <(awk -F'\t' '$3=="PROMOTE"||$3=="MERGE" {print $1"\t"$4"\t"$6}' "$tmp/journal")

# 7. entrypoint parity + marker survival
cd "$REPO" || exit 2
bash tests/test_aidocs_pointer_parity.sh || fail "aidocs pointer parity"
bash tests/test_agent_instructions.sh    || fail "agent instructions (T21 marker survival)"
for f in CLAUDE.md AGENTS.md .codex/instructions.md .opencode/instructions.md; do
  [ "$(grep -c 'aidocs/framework' "$f")" -gt 0 ] || fail "$f has zero aidocs/framework refs"
done

[ "$rc" -eq 0 ] && echo "t1405 ACCEPTANCE: PASSED"
exit "$rc"
```

**Prove the checker can fail before trusting it** (`feedback_prove_test_harness_can_fail`),
**one mutation per run** — a run that bundles several mutations only proves the
checks that happen to discriminate, and lets the others pass inert
(`feedback_negctrl_one_mutation_per_test`).

Drive it entirely through the env overrides, against throwaway copies. Nothing
mutates the live store, and **the repo is never copied** — every mutation lands
in the fixture store or the fixture journal, so the `cp -a` worktree-pointer
hazard never arises:

```bash
FIX=$(mktemp -d)
cp -a "$HOME/.claude/projects/-home-ddt-Work-aitasks/memory" "$FIX/store"
cp -a /home/ddt/Work/aitasks/.aitask-memtriage             "$FIX/journal"
cp -a "$FIX/store" "$FIX/pristine-store"        # restore source — never git checkout
cp -a "$FIX/journal" "$FIX/pristine-journal"

run() { T1405_STORE="$FIX/store" T1405_JOURNAL="$FIX/journal" \
        bash .aitask-memtriage/t1405_accept.sh; }
reset() { rm -rf "$FIX/store" "$FIX/journal"
          cp -a "$FIX/pristine-store" "$FIX/store"
          cp -a "$FIX/pristine-journal" "$FIX/journal"; }
```

| # | Single mutation | Must exit 1 naming |
|---|---|---|
| 0 | none (baseline) | nothing — must exit **0**, or every result below is meaningless |
| 1 | delete one line from `$FIX/store/MEMORY.md` | `MEMORY.md index vs disk mismatch` |
| 2 | add `[[no_such_memory]]` to one surviving file | `dangling wikilinks` |
| 3 | flip one journal row's `state` from `done` to `ruled` | `rulings never executed to completion` |
| 4 | corrupt one PROMOTE row's excerpt (col 6) | `excerpt for '<name>' not found under …` |
| 5 | delete one manifest name's journal row | `manifest entries with no ruling` |

`reset` between every run. A negative control that **passes** means the check is
wrong, not the store (`feedback_negctrl_proves_test_discriminates`) — and a
failure must name *that* mutation, not merely exit non-zero, or a different
check is masking it.

Then prove the appendices survive regeneration — the whole point of putting them
outside the markers:

```bash
./ait setup            # or the narrower setup path that calls update_agentsmd
git diff --stat AGENTS.md .codex/instructions.md .opencode/instructions.md   # expect no appendix loss
```

## Risk

### Code-health risk: medium
- A promoted claim whose premise has since flipped lands in a repo doc under
  false authority — exactly the `project_python_runner_k_filter_runs_nothing`
  failure, but now versioned and shared · severity: high · → mitigation: every
  child re-verifies each claim against current source before promoting, drops
  what it cannot verify, and lists the drops in Final Implementation Notes
- Pointers written inside the `>>>aitasks` markers, or into
  `seed/aitasks_agent_instructions.seed.md`, are silently destroyed by the next
  `ait setup` / dangle in every bootstrapped project · severity: medium · →
  mitigation: appendices go after `<<<aitasks` only; the verification section
  re-runs `ait setup` and diffs the three files
- Same rule written into two different docs as cluster boundaries drift across
  six children · severity: medium · → mitigation: child 1's table assigns every
  memory exactly one owning child; each child greps the sibling docs for the
  rule before adding a section
- Deleting ~110 files strands `[[wikilinks]]` in the survivors (140/148 files
  carry them) · severity: medium · → mitigation: child 7's explicit link-rewrite
  step, with a `comm`-based dangling-link assertion
- Blast radius is docs plus one new test — no runtime code paths change ·
  severity: low · → mitigation: n/a

### Goal-achievement risk: medium
- A memory falls between two clusters and is silently dropped, so the "all 148
  classified" criterion passes on paper while content is lost · severity: high ·
  → mitigation: child 1 emits a machine-readable table; child 7 diffs executed
  dispositions against it and asserts surviving count == KEEP count
- The ≤10 KB target is missed because the user rules "Keep as memory" on more
  memories than projected · severity: medium · → mitigation: child 7's decided
  three-step ladder (compact hooks → then an explicit user choice between
  amending the AC and re-ruling), so no path ends with the task quietly
  incomplete and no ruling is overridden to hit a number
- The per-memory gate makes each child long and interruptible, and a half-run
  loop could leave the store, index and audit inconsistent · severity: medium ·
  → mitigation: Phase 3 journals each ruling to `.aitask-memtriage/` **before**
  mutating anything and flips it to `done` after, so a resumed run replays only
  unfinished rows; every step is idempotent and unruled memories are left
  untouched and reported
- The live store gains or loses files mid-task from the auto-memory writer,
  which honours no lock — observed during planning (148 → 149) · severity:
  high · → mitigation: child 1 freezes a hashed manifest that defines the
  classified set, arrivals after the freeze are explicitly out of scope and
  reported as such, children are chained by `depends:` so only one holds the
  store at a time, and index edits are line-level against a just-re-read file
  rather than wholesale regeneration
- An UNVERIFIABLE claim reaches a shared repo doc under false authority ·
  severity: high · → mitigation: the gate makes UNVERIFIABLE structurally
  ineligible for Promote/Merge; overriding it requires amending the task's AC
  first
- "All 148" becomes unprovable because the store had already moved to 149 before
  child 1 froze anything · severity: medium · → mitigation: the 148 baseline is
  pinned by sha256 (`84db2080…`) with the sole known arrival named, child 1
  bisects and names any further drift, and the task's "148" wording is amended
  at decomposition time rather than reinterpreted mid-flight
- The acceptance checks print mismatches but exit 0, so a broken end state looks
  like success · severity: high · → mitigation: acceptance is a single script
  with an `rc` accumulator where every check sets non-zero, driven through
  `T1405_STORE` / `T1405_JOURNAL` / `T1405_REPO` overrides so a six-case,
  one-mutation-per-run negative control proves each check discriminates before
  the script is trusted
- A crashed or aborted mutation leaves a `ruled` journal row that the audit
  counts as a completed disposition, and a pre-existing heading makes an edit
  that never landed look applied · severity: high · → mitigation: acceptance
  requires `state=done` on every manifest row, and every PROMOTE/MERGE row
  carries a ≥40-char verbatim excerpt that must be found **inside the
  journalled section's span**
- The parity guard's reach is narrower than the drift it claims to prevent ·
  severity: low · → mitigation: the guard checks exactly "file exists ⇒
  referenced from all four surfaces", which is the drift, and ships with a
  negative control

### Planned mitigations
None as separate tasks. Every mitigation above is an in-scope step of the child
that owns it, and the strongest one — the machine-readable triage table diffed
at the end — is a deliverable of child 1 consumed by child 7. Recorded
explicitly because a decomposing parent never auto-creates Step-8d "after"
mitigations (`project_decomposed_parent_skips_step8d_mitigations`), so the
decision has to be made here rather than deferred.

## Post-implementation

Per **Step 9**: this parent is demoted to a parent-of-children (status back to
`Ready`, `assigned_to` cleared, parent lock released) once the children and
their plans are written; it archives automatically when the last child archives.
