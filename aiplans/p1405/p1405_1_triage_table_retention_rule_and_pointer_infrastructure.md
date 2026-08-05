---
Task: t1405_1_triage_table_retention_rule_and_pointer_infrastructure.md
Parent Task: aitasks/t1405_triage_agent_memory_store_into_aidocs.md
Sibling Tasks: aitasks/t1405/t1405_2_*.md … aitasks/t1405/t1405_8_*.md
Worktree: (current branch — no worktree)
Branch: main
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-08-05 18:24
---

# p1405_1 — Triage table, retention rule, and pointer infrastructure

## Context

The spike child of t1405. It freezes the memory-store inventory, classifies every
entry, and builds the scaffolding (`README.md` manifest, retention-rule doc,
entrypoint appendices, parity guard) that t1405_2..t1405_7 write into. Nothing
downstream can start until the manifest and the triage table exist.

**Read `aiplans/p1405_triage_agent_memory_store_into_aidocs.md` first.** It owns
the per-memory decision gate, the store-concurrency rules and the journal
schema, and they are binding here.

Only `aidocs/`, `CLAUDE.md`, `AGENTS.md`, `.codex/`, `.opencode/`, `.gitignore`
and `tests/` changes are committable. The memory store is outside the repo, so
its deletions and `MEMORY.md` rewrite appear in no git diff — say so explicitly
in the Final Implementation Notes.

## Plan verification (2026-08-04) — what changed since this plan was written

Every structural assumption was re-checked against current source. Four findings
changed the plan; the rest hold.

| Assumption | Verdict | Evidence |
|---|---|---|
| 148 baseline digests to `84db2080…` | **HOLDS** | exact match, and `comm -23` shows **zero** baseline files have disappeared |
| Store is at 149; `project_t1224_done_unblocks_t1109` is the sole arrival | **FLIPPED** | store went 149 → **152** → **155** *during this verification pass alone*; and `project_t1224_done_unblocks_t1109` has itself been **deleted** (superseded by `project_t1109_done_async_gate_stale_hole`) |
| `aidocs/framework/` has 18 docs, no index | HOLDS | `ls` = 18; no `README.md` |
| The 23-vs-0 gap | HOLDS | `CLAUDE.md` 23; `AGENTS.md` / `.codex` / `.opencode` **0** each |
| All three entrypoints are 100% marker-wrapped | HOLDS | `AGENTS.md` open=L1 close=L90 of 90; `.codex` 1/93 of 93; `.opencode` 1/89 of 89 |
| `AGENTS.md` body byte-identical to the seed | HOLDS | `sed '1d;$d' \| diff` → identical |
| `update_agentsmd()` at `aitask_setup.sh:1371`, called `:2501` | HOLDS | source read |
| T21 proves out-of-marker prose survives | HOLDS | `tests/test_agent_instructions.sh:468-477` |
| `aidocs/` never ships to bootstrapped projects | HOLDS | no `aidocs` staging in `install.sh` or the seed |
| `.gitignore` carries `.aitask-*/` per-run entries | HOLDS | 6 of them (`.aitask-explain/`, `.aitask-gates/`, …) |
| **Reachable-only = {model_reference_locations, agent_runtime_guards_audit, python_tui_performance, sed_macos_issues}** | **FLIPPED** | `agent_runtime_guards_audit.md` and `python_tui_performance.md` each already have their **own** `> **Read … when …**` trigger in `CLAUDE.md`. Only `model_reference_locations.md` has **zero** CLAUDE.md references |
| DISCARD verdicts (7 memories) | HOLDS, one nuance | Group A all archived **except t986_2**, which resolves `NOT_FOUND` on *both* helpers — it was **deleted** (commit `027ffcf94`), never archived. Group B (635_29/31/32, t835 + 7 children) all still `Ready` |
| `archived-task <id>` is a reliable check | **FLIPPED** | it returns a **single fuzzy first match** (`929` → `t929_3`), not the parent and not a child list. `task-status` is the authoritative verb |

### Decisions taken during verification

1. **Classified set = the manifest frozen at implementation start, whatever N.**
   Hard-coding a number is futile — it was 149 at plan time, 152 at 13:45, 155 at
   13:52. The 148 baseline is retained as a *checkpoint assertion* (still exact),
   not as the scope boundary. **This amends the task's AC**, which currently
   scopes out post-baseline arrivals; the amendment is Step 0 below.
2. **The two-list split is decided by reachability from `CLAUDE.md`**, not by an
   editorial "audit vs convention" judgement. Entrypoint-advertised = the 17 docs
   CLAUDE.md already names + the new docs. Reachable-only =
   `model_reference_locations.md` alone. This is what actually closes the 23-vs-0
   divergence instead of blessing a smaller copy of it.
3. **Index and advertise only docs that exist.** `state_and_concurrency_conventions.md`
   (t1405_4) and `concurrent_agent_sessions.md` (t1405_7) are **not** listed here.
   A pointer to a file that does not exist is the exact drift the guard exists to
   catch, and children 4/7 adding their own README line + CLAUDE.md trigger +
   3 appendix entries is a crisp, guard-enforced contract.
4. **A fourth parity assertion**: every doc *listed in README* must exist on disk.
   Assertions 1–3 are all glob- or list-driven in one direction and would let a
   phantom entry pass.

## Steps

### 0. Amend the task AC, then freeze (in that order, before reading any memory)

Per decision 1 and "no silent AC deviation", edit `aitasks/t1405_*.md` **first**:
replace the "any post-baseline arrival named and listed as out of scope" clause
in the Goal / Dispositions preamble / first AC bullet with *"every memory in
child 1's frozen manifest (count and digest recorded at freeze); files arriving
after that freeze are named and excluded"*. Commit with `./ait git`.

Then freeze, as the first act of implementation:

```bash
cd ~/.claude/projects/-home-ddt-Work-aitasks/memory
ls -1 *.md | grep -v '^MEMORY.md$' | sed 's/\.md$//' | sort > frozen.txt
# checkpoint: the 148 baseline must still be a subset with an exact digest
comm -13 <(sort baseline148.txt) frozen.txt > arrivals.txt   # names since baseline
grep -vxF -f arrivals.txt frozen.txt | sha256sum              # MUST be 84db2080…
comm -23 <(sort baseline148.txt) frozen.txt                   # MUST be empty
```

A digest mismatch or a non-empty second `comm` means a *baseline* file changed —
stop and reconcile; do not proceed on an unexplained delta. Persist
`name / bytes / sha256` for every file to `.aitask-memtriage/manifest_names.txt`
plus a table in this plan, and write the (now in-scope) baseline delta to
`.aitask-memtriage/post_baseline_arrivals.txt` for the audit trail.
`.aitask-memtriage/post_freeze_arrivals.txt` starts empty and collects anything
that lands *after* this freeze — those stay out of scope, per the amended AC.

Add `.aitask-memtriage/` to `.gitignore` beside the existing `.aitask-*/` entries.

### 1. The triage table

Read every manifest memory. Emit the table into this plan plus the
machine-readable block:

```
name<TAB>type<TAB>proposed<TAB>owning-child<TAB>target-doc#heading<TAB>reason
```

Exactly one owning child per memory; destinations are `doc#heading` so t1405_7
can rewrite `[[wikilinks]]` into references that resolve. The table is a
**proposal** — the binding disposition is the user's ruling in that memory's
decision gate (parent plan). Cluster proposal: t1405_2 testing →
`testing_conventions.md`; t1405_3 code/API → `code_conventions.md`; t1405_4
derived state/concurrency → new `state_and_concurrency_conventions.md`; t1405_5
planning → `planning_conventions.md`; t1405_6 TUI + shell + skill authoring;
t1405_7 docs + gates + shared-checkout + final sweep. The ~7 memories that
arrived since the baseline are assigned like any other.

### 2. Re-confirm the DISCARD candidates

Already re-verified during this planning pass — carry these forward, do not
re-derive:

| Memory | Verdict |
|---|---|
| `project_t891_deferred_behind_t756` | DISCARD — t891, t891_5, t756 all `Done`/archived |
| `project_t929_carveout_dropped` | DISCARD — t929 + all 3 children archived in `_b0/old9.tar.zst` |
| `project_t986_2_postponed_shadow_not_phase_gated` | DISCARD — **deleted, not archived** (`027ffcf94`); needs the separate justification that the work never landed. Its constraint is now durably documented at `aidocs/framework/shadow_agent.md` `## Phase detection (deferred)` |
| `project_t986_4_shadow_user_invocable_capture` | DISCARD — t986_4 + parent archived; `shadow_agent.md` already documents `user-invocable: true` and the self-capture contract |
| `project_t952_5_guard_scope_layer_split` | DISCARD — t952_5 + parent archived |
| `project_t635_29_split_procedure_gate` | KEEP — t635_29/31/32 all still `Ready` |
| `feedback_geminicli_to_agy_migrate_dont_close`, `project_agy_cli_no_model_flag` | KEEP — t835 parent + all 7 children still `Ready` |

**`task-status <id>` is the authoritative verb.** `archived-task` is a *locator*
with a fuzzy-first-match caveat, and `archived-children` does not look inside the
bundles at all. `NOT_FOUND` is a **third state** (deleted / never existed), not a
synonym for archived — t986_2 is the live proof.

### 3. `aidocs/framework/README.md` — the canonical manifest

Two explicitly labelled lists, per decision 2:

- **Entrypoint-advertised (18)** — the 17 docs CLAUDE.md already names, plus the
  new `agent_memory_conventions.md`, plus `README.md` itself. Each must be
  reachable from `CLAUDE.md` **and** all three appendices.
- **Reachable-only (1)** — `model_reference_locations.md`, reached from
  `aitask-add-model/SKILL.md`, `task-workflow/model-self-detection.md`,
  `adding_a_new_codeagent.md` and the website. It is a design-spec audit, not a
  convention; do not invent a trigger for it.

State the split as policy: universal exposure is **not** the rule, so adding an
audit doc later does not force it into every agent's context.

### 4. `aidocs/framework/agent_memory_conventions.md` — the retention rule

House style of `code_conventions.md`: one `##` per rule, heading = the rule as a
sentence, rule paragraph then rationale.

- What earns a memory: operator-/machine-specific facts; live coordination state
  that names the task it dies with.
- What belongs in `aidocs/` instead: anything durable and agent-agnostic.
- When a `project_*` memory must be deleted, and **exactly how to check** — the
  verb table from Step 2, including the `NOT_FOUND` tri-state and the
  `archived-children` / fuzzy-match caveats. This is the single most reusable
  output of this child.
- A memory must never restate a skill contract — cross-ref the promoted
  `feedback_prefer_source_enforcement_over_memory` entry.
- The new-file-vs-new-`##`-section rule for `aidocs/framework/` (documented
  nowhere today).

### 5. Entrypoint appendices

Append `## Specialist rules (aidocs/framework)` — every entrypoint-advertised doc
+ its trigger — **after** the closing `<<<aitasks` marker in `AGENTS.md`,
`.codex/instructions.md`, `.opencode/instructions.md`.

Load-bearing: all three are fully marker-wrapped and `update_agentsmd()`
(`aitask_setup.sh:1371`, called unconditionally at `:2501`) awk-replaces
everything *inside* the markers on every `ait setup`. Out-of-marker prose
survives (T21). Do **not** put pointers in
`seed/aitasks_agent_instructions.seed.md` — `aidocs/` never ships, so every path
would dangle in bootstrapped projects.

### 6. `tests/test_aidocs_pointer_parity.sh`

Follow `tests/test_website_doc_lists.sh` — same shape: `PASS/FAIL/TOTAL`
counters, `. "$PROJECT_DIR/tests/lib/asserts.sh"`, containment assertions, own
summary. Four assertions:

1. every `aidocs/framework/*.md` appears in `README.md` **exactly once**, in one
   of the two lists (`README.md` exempt — the manifest listing itself is
   meaningless);
2. every **entrypoint-advertised** doc is referenced from `CLAUDE.md` and from
   each of the three appendices (`README.md` **is** required in all four);
3. every **reachable-only** doc has ≥1 in-repo referrer outside `README.md`;
4. every doc **listed in README** exists on disk (decision 4 — closes the
   phantom-entry direction that 1–3 cannot see).

**Negative control, as a separate runnable step, one mutation per run.** Operate
on a temp copy; restore by undoing the mutation, never `git checkout`. Each must
exit 1 **naming the offending doc**:

| # | Mutation | Must name |
|---|---|---|
| 0 | none | nothing — must exit **0**, or every row below is meaningless |
| 1 | drop one advertised doc's pointer from one appendix | that doc, assertion 2 |
| 2 | drop one doc's README line | that doc, assertion 1 |
| 3 | add a README line for `no_such_doc.md` | `no_such_doc.md`, assertion 4 |

A negative control that *passes* means the test is wrong, not the docs. Assert
the failure names the mutated doc — a bare non-zero exit may be a different
assertion masking it.

### 7. CLAUDE.md

Add triggers for `README.md` and `agent_memory_conventions.md`. **Widen the
`testing_conventions.md` trigger** — it reads "when designing tests for a
threading / asyncio migration or any other concurrency primitive" and will be
badly under-scoped once t1405_2 lands ~25 general testing rules.

### 8. Run the decision gate over the DISCARD candidates

The parent plan's three-phase gate. Journal each ruling to
`.aitask-memtriage/t1405_1.tsv` **before** mutating, flip `state` to `done`
after. Verified-stale is a proposal, not a licence — the user rules on each one.

## Key files

- `aidocs/framework/README.md` (new), `aidocs/framework/agent_memory_conventions.md` (new)
- `AGENTS.md`, `.codex/instructions.md`, `.opencode/instructions.md` — appendix after `<<<aitasks` only
- `CLAUDE.md` — 2 new triggers + widened testing trigger
- `tests/test_aidocs_pointer_parity.sh` (new), `.gitignore`
- `aitasks/t1405_*.md` — AC amendment (Step 0)

## Verification

```bash
bash tests/test_aidocs_pointer_parity.sh          # passes; negative controls 1-3 each exit 1 naming the doc
bash tests/test_agent_instructions.sh             # T21 marker survival
grep -c "aidocs/framework" AGENTS.md              # no longer 0
./ait setup && git diff --stat AGENTS.md .codex/instructions.md .opencode/instructions.md
```

The last is load-bearing: the appendices must survive `ait setup` regenerating
the marker blocks. Also confirm every DISCARD ruling is journalled `state=done`
and the file is gone from both disk and `MEMORY.md`.

## Risk

### Code-health risk: medium
- Pointers land inside the `>>>aitasks` markers or in the seed and are destroyed
  on the next `ait setup` / dangle in every bootstrapped project · severity:
  high · → mitigation: append after `<<<aitasks` only; the `./ait setup` diff is
  a required verification step
- README / CLAUDE.md / appendices advertise docs that children 4 and 7 have not
  created yet, leaving dangling pointers for the length of the chain · severity:
  medium · → mitigation: decision 3 (index only what exists) plus assertion 4,
  which fails the build on a phantom entry
- The parity guard's reach is narrower or broader than the drift · severity:
  medium · → mitigation: it checks a two-list manifest, not a blanket rule, and
  ships with a 3-case one-mutation-per-run negative control that must name the
  offending doc
- Blast radius is docs plus one new test — no runtime code path changes ·
  severity: low · → mitigation: n/a

### Goal-achievement risk: medium
- The manifest is frozen against a live writer that honours no lock, making
  "every memory classified" unprovable · severity: high · → mitigation: freeze is
  the first act of implementation, digest-checked against the intact 148 baseline
  in both directions, with arrivals named. Observed drift during verification
  alone: 149 → 152 → 155
- A memory falls between two clusters and is silently dropped · severity: high ·
  → mitigation: the machine-readable table assigns exactly one owning child per
  memory, and t1405_7 diffs executed dispositions against it
- A DISCARD is justified by a mis-read helper — `NOT_FOUND` conflates deleted
  with archived, and `archived-task` returns a fuzzy single match · severity:
  medium · → mitigation: `task-status` is authoritative, the tri-state is written
  into `agent_memory_conventions.md`, and t986_2 carries its own git-evidence
  justification rather than an "archived" one
- The two-list split re-creates the CLAUDE.md-vs-AGENTS.md divergence in
  miniature · severity: medium · → mitigation: decision 2 — reachability from
  CLAUDE.md decides, so the only reachable-only doc is one with zero CLAUDE.md
  references

### Planned mitigations
None as separate tasks — each mitigation above is an in-scope step of this child.
Recorded explicitly because a decomposing parent never auto-creates Step-8d
"after" mitigations.
