---
Task: t1673_tier_b_reachability_correction.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1673 — Correct the Tier-B reachability claim in the premise-staleness record

## Context

`aidocs/framework/task_premise_staleness.md` (the t1561 decision record, context
anchor for the whole t1663 tree) makes two claims that cannot both be true:

- **Tier B scope** resolves an origin via `lib/followup_origin.py` at **`exact`
  quality only** — "`topic` and `unknown` refuse to claim causation".
- **Seeding** stamps `premise_baseline` at creation when the task has a
  derivable scope — "`--followup-of` (Tier B will resolve an origin) or
  `--file-ref` (Tier A)".

`--followup-of` cannot produce an `exact` origin. This is a **contract-level
impossibility, not a corpus property**, and both halves are greppable:

- `resolve_anchor()` (`.aitask-scripts/aitask_create.sh:228-266`) turns
  `--followup-of` into `RESOLVED_ANCHOR`, written as `anchor:` — and writes
  nothing else. No creation path writes `followup_of:`; zero task files carry it.
- `followup_origin.py` rule 1 (`.aitask-scripts/lib/followup_origin.py:14-17`,
  enforced at `:134-141`) returns `TOPIC` for an `anchor`-only task, never
  `EXACT`: "Reporting it as `exact` would claim direct causation the data does
  not support."

Left uncorrected, every task t1663_3 seeds on the `--followup-of` trigger would
carry a `premise_baseline` whose scope can never resolve — a permanent silent
`SKIP`. That is precisely the dead weight the record says it wants to avoid, and
it would consume the tree's only coverage-growth path.

### Supporting facts established during planning

**Structural — stated precisely (an earlier, looser version of this claim was
wrong and is corrected here).** `aitask_create.sh` imposes **no type gate** on
`--verifies`: it parses (`:194`) and serializes (`:558-562`, `:696-700`,
`:1997-2001`) the field independently of `issue_type`. The
manual-verification restriction lives in the **two in-framework callers**, not
in the CLI. Exactly three files outside the two CLI implementations mention the
flag:

| File | Role | Type it passes |
|---|---|---|
| `aitask_create_manual_verification.sh:117` | calls `aitask_create.sh` | `--type manual_verification` (`:111`) |
| `aitask_archive.sh:615` (`create_carryover_task`) | calls `aitask_create.sh` | `--type manual_verification` (`:610`) |
| `aitask_fold_mark.sh:284` | calls `aitask_update.sh:537` — an **update** path, not creation | n/a |

So: *no in-framework **creation** caller produces a non-MV `--verifies` task
today*, and Step 3 Check 3 routes the MV ones away before the premise check
runs. But that is a property of the callers, not a contract of the flag.

**The hazard this creates.** Three surfaces currently document `--verifies` as
manual-verification-only, contradicting the type-agnostic implementation:
`aitask_create.sh:126-127` ("for issue_type: manual_verification"),
`aitask_update.sh:201` ("Verifies options (batch mode, for manual-verification
tasks)"), and `website/content/docs/commands/task-management.md:62`. If the
record makes `--verifies` a load-bearing Tier-B seed trigger while those
surfaces call the non-MV form unsupported, a maintainer could type-gate or
remove it and silently kill the only Tier-B seeding path. No test pins any of
those strings, so nothing would catch it.

**Tier-B eligibility is written wrong, and the corpus already violates it.**
The record's Tier B bullet (`:81`) scopes derived scope to "**for follow-up
tasks**". `followup_origin.py` implements no such gate — its docstring (`:8-10`)
states it "deliberately never reads `followup_kind`", and `resolve_detailed()`
reads only `verifies` and `anchor`. Eligibility in the implementation is *having
an exact origin*, not *being a follow-up*.

The two are not the same set, and the difference is live, not hypothetical:
**`aitasks/t583/t583_9_meta_dogfood_aggregate_verification.md`** is
`issue_type: test`, `status: Ready`, carries `verifies: [t583_1 … t583_8]` — an
`exact` origin — and has **neither `followup_kind` nor `anchor`**. It is not a
follow-up under any definition the framework uses, yet the resolver returns
`EXACT` for it. Left unfixed, the written eligibility rule excludes a task the
seeding rule would seed and the engine would happily check.

**Post-creation acquisition:** `aitask_update.sh --file-ref` / `--verifies` and
`aitask_fold_mark.sh`'s file-ref and verifies unions (`:245`, `:284`, both
routed through `aitask_update.sh`) can give an *existing* non-MV task a
resolvable scope. No current in-framework *creation* caller would produce the
two non-MV `verifies:` carriers that exist (`t729`, `t583_9`); their exact
provenance is not established here and the argument does not rest on it.

**Live Tier A producer:** `codebrowser_app.py:1566,1603` creates ordinary tasks
with `--file-ref`.

**Dated observation, 2026-09-01 (not pass/fail — a statistic, not an invariant):**
495 active task files; 91 carry `verifies:` (89 `manual_verification`, plus
`t729` chore and `t583_9` test); **0** carry
`file_references:`; 309 carry `anchor:`.

**Prior measurement, 2026-08-27** (229 active follow-ups): exact 86, topic 130,
unknown 13. On the 37 dual-signal tasks the exact and topic file sets differ in
21 cases and can be **disjoint** (t1497: exact 3 files, topic 13, overlap 0).

## Decision

**Option (a), with `--verifies` named explicitly** (confirmed with the user):

> `aitask_create.sh` seeds `premise_baseline` when the invocation carries
> **`--file-ref`** (Tier A) or **`--verifies`** (Tier B `exact`).
> **`--followup-of` alone does not seed.**

The trigger now mirrors the resolver contract exactly, and stays correct if a
non-MV creation path ever gains `--verifies` (fold already gives non-MV tasks
`verifies:` post-creation).

**Tier B is redefined to match the resolver: any task carrying an `exact`
origin, follow-up or not.** The alternative — gating Tier B on an explicit
follow-up relation — would require the premise engine to read `followup_kind`,
the exact coupling `followup_origin.py` was written to avoid ("Origin is a
separate concern from *classification*"), and would exclude t583_9, a `Ready`
task with a perfectly good eight-entry exact origin. The resolver's documented
contract is the spec here; "for follow-up tasks" is a descriptive gloss that was
never enforced. Correct the claim rather than add the behavior.

**The `--verifies` contract is decided explicitly, not left implicit.** Because
the trigger is load-bearing, `--verifies` on a **non-`manual_verification`**
task is declared **supported**, and that declaration is enforced on two fronts
rather than asserted in prose:

- the three surfaces that call the flag manual-verification-only are corrected
  so the documented contract matches the type-agnostic implementation
  (edit 2 below);
- **t1663_3 owns a non-MV, non-follow-up creation fixture** pinning that a task
  created with `--verifies`, a non-MV `--type` and no follow-up relation **is
  seeded** — so a future type-gate, or a re-added follow-up gate on Tier B,
  fails a test instead of silently dormanting Tier B (edit 3).

The record states the reachability honestly alongside it: no in-framework
*creation* caller produces a non-MV `--verifies` task today, so the Tier-B
seeding path is **live by contract but unexercised by framework callers** —
reachable by a direct `ait create --verifies` invocation, and by any future
caller. That is a weaker claim than "Tier B is a working coverage path", and the
record must not overstate it.

**Why not widen Tier B to accept `anchor` (option b):** it would re-import the
failure mode the record already rejected. The 2026-09-01 no-go pre-phase killed
the computed origin-landing baseline because year-scale windows over hot
framework files produce undifferentiated churn (0/5 actionable). A topic-root
scope is that same shape by construction. Worse, the 2026-08-27 disjointness
measurement shows the topic fallback is not merely coarser — it can name a
different file set entirely. Rule 1 is also load-bearing for other consumers of
the shared pure module; overturning it from a documentation task is out of scope.

**Deferred instead of adopted (option c):** a persisted exact-origin field for
`--followup-of` would make Tier B reachable without touching rule 1, but it is a
frontmatter-field addition with its own merge/sync/board surface — the
t1468_1/t1468_2 field-foundation + creation-seams shape, a separately justified
task. Recorded in the Deferred section with **t1663_6** as disposition owner.

**Honest consequence, recorded in the record:** since both in-framework creation
callers that pass `--verifies` also pass `--type manual_verification`, and Check
3 routes those away, the only seeding path exercised by framework callers today
is Tier A / `--file-ref`. The organic-coverage story is narrower than the record
originally claimed, and that narrowing becomes a measured input to t1663_6.

---

## Implementation

### 1. `aidocs/framework/task_premise_staleness.md` (plain `git` — main branch)

**1a. Tier B bullet** (§"Scope and baseline are orthogonal axes", ~L80-85) —
two corrections in one bullet:

- **Eligibility:** "for follow-up tasks" → **for any task carrying an `exact`
  origin**. Note why: `followup_origin.py` "deliberately never reads
  `followup_kind`" (`:8-10`), so eligibility is the presence of an exact origin,
  not a classification; cite t583_9 (`issue_type: test`, `verifies:` of eight
  siblings, no `followup_kind`/`anchor`) as the live case the old wording
  wrongly excluded.
- **Reachability:** `exact` requires `verifies:`; `resolve_anchor()` writes only
  `anchor:`; rule 1 makes `anchor` never exact; **this is a contract, not a
  corpus property**; forward-ref to the new subsection.

*Deliberately not edited:* the other "follow-up" mentions in the record
(`:95`, `:226`, `:228`, `:241`, `:281`, `:285`) are dated-measurement prose or
descriptions of the deferred computed-baseline tier's target population — they
describe a population, not a Tier-B eligibility rule, and stay as written.
`:215` and `:249-250` *are* eligibility-flavoured and are fixed by 1c and 1e.

**1b. §"Seeding"** (~L204-212) — rewrite the trigger sentence to
`--file-ref` (Tier A) or `--verifies` (Tier B `exact`), and state explicitly
that `--followup-of` alone does **not** seed, with the reason (a baseline that
can never resolve a scope reads `SKIP` forever). Carry-over inheritance sentence
unchanged.

**1c. §"Seeding" second paragraph** (~L214-219) — the "premise-correct even for
'before'-timed risk-mitigation follow-ups" argument now describes a population
that is no longer seeded (the risk-mitigation seam creates with `--followup-of`
and no `--file-ref`). Qualify it: the timing argument stands but has no live
subject in v1.

**1d. New subsection `### Tier B reachability` after §"Seeding"** — the
structural facts (greppable), the dated 2026-09-01 observation explicitly
labelled *not pass/fail*, the decision, why not option (b), and the pointer to
the deferred alternative. This is the section the record's other claims
forward-reference.

**1e. §"The measured pre-phase and the no-go decision"**, closing paragraph
(~L247-253) — "a seeded **follow-up** carries a stored baseline … so every new
**follow-up** is checkable from day one" is wrong on both counts (wrong
population, overstated coverage). Rewrite to "a seeded **task**" / "every
**seeded** task", name the Tier-A/exact-origin sources, and point at 1d for how
much narrower that population is.

**1f. §"Baseline lifecycle"** table (~L257-266) — replace the
`--followup-of or --file-ref` row with:

| Event | `premise_baseline` |
|---|---|
| task created with `--file-ref` or `--verifies` | seeded to HEAD at creation |
| task created with `--followup-of` only | **not written** (no Tier-A/B-resolvable scope) |
| scope acquired after creation (`aitask_update.sh`, fold union) | not written — resolves a scope but reads `SKIP` |

(keeping the existing "created without derivable scope" and carry-over rows).

**1g. §"Deferred, each with its disposition"** — add two items, both owned by
**t1663_6**: the persisted exact-origin field (option c), and seeding on
post-creation scope acquisition. Strengthen the existing "Topic-quality origins"
bullet with the 2026-08-27 disjointness evidence, so option (b) is closed by
recorded evidence rather than by omission.

**1h. §"Tier B reachability" (from 1d) also carries the `--verifies` contract** —
one paragraph stating that `--verifies` is type-agnostic by contract, that the
MV restriction is a property of the two in-framework callers and not of the
flag, and that **type-gating `--verifies` would silently dormant Tier B** and is
pinned against by t1663_3's non-MV creation fixture. Include the caller table
from Context so the evidence is in the record, not just in this plan.

### 2. `--verifies` contract surfaces (plain `git` — main branch)

Three surfaces document the flag as manual-verification-only, contradicting the
type-agnostic implementation. No test pins any of these strings. Correct all
three in one commit so the documented contract matches the code the record now
depends on:

- `.aitask-scripts/aitask_create.sh:126-127` — drop "(for issue_type:
  manual_verification)"; say the field records the task IDs this task verifies,
  and that it is **not** restricted to `manual_verification` tasks.
- `.aitask-scripts/aitask_update.sh:201` — section heading "Verifies options
  (batch mode, for manual-verification tasks)" → "(batch mode)", with the
  same clarification on the `--verifies` row.
- `website/content/docs/commands/task-management.md:62` — table cell "(for
  `manual_verification` tasks)" → wording that names the common use without
  claiming exclusivity.

Wording is a text-only change; no anchors, IDs or code paths move.

### 3. `aitasks/t1663/t1663_3_creation_time_seeding_and_carryover.md`

Single `aitask_update.sh` call carrying both the body and the dependency:

```bash
./.aitask-scripts/aitask_update.sh --batch 1663_3 \
  --desc-file <tmp> --deps "t1663_2,1673" --commit
```

Body changes:
- **Context** — correct "every new follow-up ... must leave creation checkable"
  to the Tier-A/`--verifies` population, with the t1673 pointer.
- **Key files** — `aitask_create.sh` bullet: seed on `--file-ref` (Tier A) or
  `--verifies` (Tier B `exact`); `--followup-of` alone is **not** a trigger,
  with the rule-1 reason inline so the implementer cannot regress it.
- **Verification** — replace "Creation with `--followup-of` → seeded" with:
  - Creation with `--file-ref` → seeded, value = HEAD-at-creation.
  - Creation with `--verifies` → seeded.
  - **Creation with `--verifies`, a non-`manual_verification` `--type`, and no
    follow-up relation (no `--followup-of`, no `--followup-kind`) → seeded** —
    the contract fixture. It pins both halves of the corrected Tier-B contract
    at once: the flag is type-agnostic, and eligibility is *having an exact
    origin*, not *being a follow-up*. This is the shape of the live task
    `t583_9`, so the fixture exercises a case the corpus already contains rather
    than an invented one. It fails loudly if anyone type-gates `--verifies` or
    re-adds a follow-up gate to Tier B.
  - **Creation with `--followup-of` alone → field absent** (negative control:
    the trigger the record used to name must now provably *not* fire).
  - Creation with none of the three → field absent.
  - Carryover and draft-mode bullets unchanged.

### 4. `aitasks/t1663/t1663_5_website_docs_premise_staleness.md`

`aitask_update.sh --batch 1663_5 --desc-file <tmp> --commit`. Its "Key files"
bullet tells the docs child to document "how to opt a task in (`--file-ref`,
follow-up seeding)" — "follow-up seeding" reproduces exactly the obsolete
implication this task exists to remove, and would carry it onto the website.
Replace it with the corrected creation conditions (`--file-ref`, or
`--verifies`; `--followup-of` alone does not seed), so the downstream doc task
inherits an unambiguous contract rather than the claim being re-derived.

### 5. `aitasks/t1663/t1663_6_retrospective_prompt_rate_evaluation.md`

`aitask_update.sh --batch 1663_6 --desc-file <tmp> --commit`. Add Tier-B
reachability as a measured input ("what to measure": how much of the seeded
population came from Tier A vs `--verifies`, and how many `--verifies`-seeded
tasks were `manual_verification` and therefore never checked), and add the two
new dispositions from 1g to the "Dispositions this child owns" list.

### Commit discipline

The worktree is shared and dirty (18 files modified by other work) and task data
lives on the `aitask-data` branch. Commit **only** my paths, never the index:
`git commit -- <explicit paths>` for edits 1 and 2;
`aitask_update.sh --commit` handles the task files on the data branch.
Verify each commit with `git show --stat` before moving on.

**Shell note:** `grep` and `find` are shimmed to a broken helper in this session
(`grep` is a shell function routing to `claude -G`, which errors with `unknown
option '-G'` and exits 0 — a silent false negative). Every verification command
below uses `command grep`. Do not use bare `grep`/`find` for evidence here.

---

## Verification

1. **The impossibility claim is still true at implementation time** (re-run, do
   not trust the plan):
   ```bash
   command grep -n 'RESOLVED_ANCHOR=' .aitask-scripts/aitask_create.sh  # anchor only
   sed -n '134,141p' .aitask-scripts/lib/followup_origin.py             # rule 1 → TOPIC
   ```
2. **`--verifies` caller inventory** — the claim is about the two *creation*
   callers, not about the CLI:
   ```bash
   command grep -rln -- '--verifies' .aitask-scripts \
     | command grep -v -e 'aitask_create\.sh' -e 'aitask_update\.sh'
   ```
   → exactly `aitask_create_manual_verification.sh`, `aitask_archive.sh`,
   `aitask_fold_mark.sh`. The first two must each also show `--type
   manual_verification`; `aitask_fold_mark.sh` must resolve to
   `aitask_update.sh` (update path, not creation).
3. **`aitask_create.sh` imposes no type gate on `--verifies`** — the property
   the Tier-B trigger depends on:
   ```bash
   command grep -n 'BATCH_VERIFIES' .aitask-scripts/aitask_create.sh
   ```
   → parse + three serializer sites, none conditioned on `issue_type`.
4. **The `--verifies` contract surfaces carry the new wording and not the old.**
   A substring search for "manual-verification tasks" is **not** a valid check
   here: the corrected text contains that phrase too ("usually
   manual-verification tasks, but any issue_type may carry a verifies list"), so
   it would pass on both correct and incorrect content. Assert two arms per
   surface — the exact old **exclusive** phrase absent, the new
   **non-exclusive** phrase present:

   | file | old phrase (ABSENT) | new phrase (PRESENT) |
   |---|---|---|
   | `.aitask-scripts/aitask_create.sh` | `(for issue_type: manual_verification)` | `but not restricted to one` |
   | `.aitask-scripts/aitask_update.sh` | `Verifies options (batch mode, for manual-verification tasks):` | `issue_type may carry a verifies list` |
   | `website/content/docs/commands/task-management.md` | ``this task verifies (for `manual_verification` tasks)`` | `but any issue type may carry it` |

   ```bash
   check() {  # label file old new
     local rc=0
     command grep -qF -- "$3" "$2" && { echo "FAIL[$1]: old exclusive wording present"; rc=1; }
     command grep -qF -- "$4" "$2" || { echo "FAIL[$1]: new contract wording absent"; rc=1; }
     [ $rc -eq 0 ] && echo "OK[$1]"; return $rc
   }
   ```
   **Negative control (required — this is what proves the check is not
   vacuous):** run both arms against `git show <pre-edit-rev>:<file>`. Every
   surface must fail **both** arms.
5. **No remaining claim that `--followup-of` yields an `exact` origin or seeds:**
   ```bash
   command grep -n -- '--followup-of' aidocs/framework/task_premise_staleness.md
   command grep -rn -- '--followup-of' aitasks/t1663/ aiplans/p1663/
   ```
   Every hit must either say it does **not** produce an exact origin / does not
   seed, or be the risk statement in `p1663_1` that already says so. Also check
   the softer phrasing the reviewer caught:
   ```bash
   command grep -rn 'follow-up seeding' aitasks/t1663/ aidocs/framework/task_premise_staleness.md
   ```
   → no hits.
6. **Tier-B eligibility no longer says "follow-up"**, and the remaining
   "follow-up" mentions are the six deliberate ones:
   ```bash
   command grep -n 'follow-up\|followup' aidocs/framework/task_premise_staleness.md
   ```
   → the Tier B bullet must not scope eligibility to follow-up tasks; `:215`
   and the no-go closing paragraph must read as corrected by 1c/1e; the
   dated-measurement and deferred-tier mentions may remain.
   Cross-check the resolver still has no classification gate:
   ```bash
   command grep -n 'followup_kind' .aitask-scripts/lib/followup_origin.py
   ```
   → docstring only, never in code.
7. **Dependency wired, and nothing dropped** (`--deps` replaces the whole list):
   ```bash
   # NOTE: `resolve` takes parent ids only and rejects `1663_3`; `child-file`
   # is the child lookup. (t1673's own acceptance text named the wrong verb —
   # corrected in the task file as part of this task.)
   f=$(./.aitask-scripts/aitask_query_files.sh child-file 1663 3 | sed 's/^CHILD_FILE://')
   command grep -n '^depends:' "$f"
   ./ait ls -v --children 1663 99
   ```
   → `depends:` contains both `1663_2` and `1673`; the listing renders t1663_3
   with no broken-dependency warning.
8. **Website build** (edit 2 touches one docs table cell): if `hugo` is
   available, `cd website && hugo build --gc --minify`. Text-only change, no
   anchors or ids move, so a dead-fragment sweep is not implicated.
9. **Commit scope:** `git show --stat` on each commit names only the intended
   files.
10. **Edited scripts still run** (edit 2 touches usage heredocs):
   ```bash
   shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh
   ./.aitask-scripts/aitask_create.sh --help | command grep -A2 -- '--verifies'
   ./.aitask-scripts/aitask_update.sh --help | command grep -A2 -- '--verifies'
   ```
   → both exit cleanly and render the corrected text.

Edit 2 changes only help/doc strings — no logic — so no behavioral test suite is
implicated beyond step 10.

---

## Risk

*(Reassessed after the review round, which added edits 2 and 4 — edit 2 is the
first one that touches executable files.)*

### Code-health risk: low
- Edit 2 changes usage-heredoc text inside two live shell scripts
  (`aitask_create.sh`, `aitask_update.sh`). No logic, but a quoting slip inside
  a heredoc is a real way to break a script silently · severity: low · → mitigation: none needed (covered by Verification steps 4 and 10 — shellcheck plus a `--help` smoke run on both scripts)
- Everything else is documentation and task-file metadata; blast radius is six
  files, all of which this task owns or is explicitly directed to edit · severity: low · → mitigation: none needed
- `--deps` replaces the whole dependency list rather than appending, so a
  mis-typed value could silently drop `t1663_2` · severity: low · → mitigation: none needed (covered by Verification step 7)

### Goal-achievement risk: medium
- The correction makes the coverage gap **visible** but does not close it: with
  0 active tasks carrying `file_references:` and no in-framework creation caller
  producing a non-MV `--verifies` task, v1's exercised seeding path may seed
  almost nothing, so the t1663 tree could land a correct mechanism with
  near-zero organic coverage · severity: medium · → mitigation: deliverable 5 (t1663_6 notification), already in scope
- Until t1663_3 lands its non-MV `--verifies` fixture, the type-agnostic
  contract is enforced only by prose on three corrected surfaces · severity: low · → mitigation: none needed (t1663_3 depends on this task, so the fixture requirement cannot be picked around)
- A `depends:` edge does not by itself stop t1663_3 being implemented against
  the old criterion; the binding surface is t1663_3's own text, which edit 3
  rewrites — and t1663_5's, which edit 4 rewrites · severity: low · → mitigation: none needed

No separate mitigation tasks are proposed: the one medium-severity risk is
already covered by deliverable 5, which is in this task's scope, and every other
bullet is covered by an existing verification step or by the dependency edge
this task wires. Spawning a task for any of them would duplicate work this plan
already performs.

---

## Final Implementation Notes

- **Actual work done:** All five planned edits landed.
  1. `aidocs/framework/task_premise_staleness.md` — Tier B redefined to *any task
     carrying an `exact` origin* (was "for follow-up tasks"), with `t583_9` cited
     as the live case the old wording excluded; the `--followup-of`
     impossibility stated as a contract; seeding trigger corrected to
     `--file-ref` / `--verifies`; the "before"-timed risk-mitigation paragraph
     qualified ("no live subject in v1"); a new `### Tier B reachability`
     subsection carrying the caller table, the type-agnostic `--verifies`
     contract, the why-not-`anchor` argument, and the dated 2026-09-01
     observation marked explicitly *not pass/fail*; the no-go closing paragraph
     narrowed from "every new follow-up" to "every seeded task"; three new rows
     in the baseline-lifecycle table; the "Topic-quality origins" deferred bullet
     strengthened with the 2026-08-27 disjointness evidence; two new deferred
     items (persisted exact-origin field; post-creation scope acquisition), both
     owned by the retrospective child.
  2. The three `--verifies` contract surfaces (`aitask_create.sh`,
     `aitask_update.sh`, `website/content/docs/commands/task-management.md`)
     reworded from manual-verification-**only** to "usually, but any issue type
     may carry it".
  3. `t1663_3` — corrected criterion in Context/Key files/Verification, the
     non-MV non-follow-up contract fixture added as a required case, and
     `depends: [t1663_2, 1673]`.
  4. `t1663_5` — docs-handoff wording pinned so the website child cannot
     reproduce "follow-up seeding".
  5. `t1663_6` — Tier-B reachability added as a measured input; two new
     dispositions added.

- **Deviations from plan:** One, deliberate. The plan specified
  `aitask_update.sh --commit` for the three sibling task files; `--commit` was
  dropped because Step 8's review is non-skippable and those edits *are* the
  deliverable. They were written in Step 7 and committed in Step 8 with the rest.

- **Issues encountered:**
  - `grep` and `find` are shimmed in this session to a helper that invokes
    `claude -G`, which errors `unknown option '-G'` **and exits 0** — a silent
    false negative on every evidence command. All verification was re-run with
    `command grep`. The plan records this; it is a session/environment property,
    not a repo defect.
  - Two review rounds tightened the work before approval:
    - The first draft claimed "every creation path writing `verifies:` is
      manual-verification-only". False as stated — `aitask_create.sh` is
      type-agnostic; the restriction is in two *callers*. Corrected, and the
      three misleading help surfaces were fixed so the documented contract
      matches the implementation the record now depends on.
    - Tier B's written eligibility ("for follow-up tasks") contradicted the
      resolver, which "deliberately never reads `followup_kind`". The corpus
      already violated it (`t583_9`). Resolved by correcting the claim rather
      than adding a gate.
  - Step 8 review caught two verification defects, both fixed:
    - t1673's own acceptance text prescribed
      `aitask_query_files.sh resolve 1663_3`, but `resolve` rejects child ids.
      Replaced with `child-file 1663 3` plus an explicit assertion that **both**
      deps survived (`--deps` replaces the whole list).
    - The "no MV-only surface remains" check was a substring grep that the
      *corrected* wording also matches — it passed on both right and wrong
      content. Replaced with a two-arm fixed-string check per surface (old
      exclusive phrase ABSENT, new non-exclusive phrase PRESENT), plus a
      negative control against the pre-edit revisions. The control was run:
      all three surfaces failed both arms, proving the check discriminates.

- **Key decisions:**
  - **Seeding trigger** = `--file-ref` (Tier A) or `--verifies` (Tier B exact);
    `--followup-of` alone does not seed. Chosen over narrowing to `--file-ref`
    only (user-confirmed) because it mirrors the resolver contract and needs no
    re-widening when a non-MV path gains `--verifies`.
  - **Tier B not widened to accept `anchor`.** It would re-import the
    undifferentiated-churn failure the computed-baseline no-go already rejected,
    and the 2026-08-27 data shows the topic fallback can be *disjoint* from the
    exact answer, not merely coarser.
  - **`--verifies` declared type-agnostic and pinned by a fixture** rather than
    asserted in prose, so a future type-gate fails a test instead of silently
    dormanting Tier B.
  - **The dated corpus numbers are recorded as observations, never as criteria** —
    the load-bearing claims are the contract-level ones (`anchor` is never
    `exact`; the resolver never reads `followup_kind`), which no data change can
    falsify.
  - **Honest narrowing recorded:** no in-framework *creation* caller produces a
    non-MV `--verifies` task, so Tier B ships live-by-contract but unexercised,
    and Tier A is v1's only exercised seeding path. Handed to the retrospective
    child as a measured input rather than smoothed over.

- **Upstream defects identified:** None
