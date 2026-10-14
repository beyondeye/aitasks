---
priority: medium
effort: high
depends: [t1954_3]
issue_type: chore
status: Implementing
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
created_at: 2026-10-12 17:51
updated_at: 2026-10-14 12:00
---

## Context

Child 4 of t1954 (annotation-parser research): the synthesis. It owns every deliverable the parent names after the experiments. Read first:
- the parent task `aitasks/t1954_research_multilanguage_annotation_parsers.md` (deliverables and acceptance criteria are binding);
- the parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md` (shared design);
- the archived plans of t1954_1–3, `findings_t1954_{1,2,3}.md` and everything under `results/`, all in `aidocs/testing_engine/t1954_parser_research/`.

The current four-language M2.2 work stays unblocked: nothing here may become a hard prerequisite of it.

## Deliverables

1. **Final rerun**: every provider on the final corpus, in one environment, with the README commands.
2. **Report** `aidocs/testing_engine/t1954_annotation_parser_research.md`:
   - keep observations, documentation claims, assumptions and unknowns separate;
   - the candidate matrix, with the safety columns first;
   - rejected alternatives, each with its evidence;
   - dependency, licensing and maintenance analysis;
   - a recommendation, or an explicit no-candidate-yet conclusion;
   - a supported/unsupported **language policy**;
   - a bounded **provider/adapter contract**: trustworthy comment locations, uncertainty, safe placement, language onboarding policy, conformance fixtures;
   - a **migration sketch** with an implementation-complexity comparison (no schedules);
   - the impact on the centralized rewriter, conflicts, root confinement/no-follow, stamp/provenance, annotate, verify, stale confirmation, adoption, author annotations and the repair loop.
3. **Evidence artifact**: bulky raw logs go into `ait artifact create 1954 <bundle> --kind research_evidence`. Link the handle from the report.
4. **Trail refresh**: re-read and refresh `art:trail-testmap-feature` at **deep** depth, following the aitask-trail refresh procedure. Link the exact report path and evidence handles in the narrative, evidence and relations; record the decision, residual risks, affected modules and recommended landing order. Marking the task Done alone is insufficient.
5. **Consumer evaluation**, using the child IDs that actually exist then: M2.2 t1853_2, M2.3 t1853_3, M4 t1855, M6 t1857, M7 t1858, the repair loop t1853_7, M9 t1860, M10 t1861 and cross-linking t1863. Mark which need action and which need context only.
6. **Follow-ups**: bounded implementation follow-ups justified by the recommendation, anchored to topic 1852 and placed in the trail. Order them advisorily; use hard depends only for real prerequisites. Send advisory `./ait note`s (the `/aitask-note` skill) with report links and decisions to affected existing tasks. Notes never replace follow-up tasks.
7. Verify that every path and artifact handle cited by the report and trail exists.

## Post-phase (risk mitigations, from the parent plan)

- `baseline_rerun_at_landed_commit`: re-run the baseline at the then-current annot commit (`git log -1 -- goengines/internal/testmap/annot`). If it differs from child 1's PIN, run both, report both columns and name every differing case.
- `native_oracle_gap_followup`: for any language whose evidence is still `native: none` (expected: Kotlin and/or Swift), make no "supported" claim beyond what the hand oracle shows, and create one bounded follow-up (anchor 1852) to validate those fixtures on a host with the compiler.

## Verification

- The report exists at the exact path, with the task id in its filename.
- `ait artifact versions art:trail-testmap-feature` shows a new version that links the report.
- The follow-ups exist with anchor 1852.
- `NOTE_APPENDED:` lines appear for the notes sent.
- Path-scoped commits only.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1954_1** id=2026-10-13T09:01:55Z.bf7d62c470358b1a7ab56e02 from=t1954_1 from_verified=yes at=2026-10-13T09:01:55Z base=5e730b0fb5168432674a24eb41c63089473153bf base_branch=main dirty=yes host=omg16
>
> | t1954_1 landed (code commit 5e730b0fb): harness, 213-fixture corpus, and evidence in aidocs/testing_engine/t1954_parser_research/ (results/, findings_t1954_1.md). Items for the report:
> | - Baseline (annot @ f096db065) safety columns are 0 in bash/Go/Kotlin. One real M2.2 defect: the UTF-8 BOM. A BOM-prefixed Python module loses its docstring records, and a fresh insertion lands above the BOM, breaking the module. This is now upstream follow-up t1969 (exposure today nil). Cite it in the consumer evaluation.
> | - Two M2.2 lex expectations were corrected by bash execution (ANSI-C delimiter, `$((` subshell); two others are recorded as policy (`x-policy`: comments in backticks / continuation lines). See findings observation 8.
> | - t1853_3 (M2.3) is editing `annot` right now, so the post-phase rerun at the then-current commit will likely see differences: move baseline/PIN deliberately and report both columns.
> | - The evaluation seam and guard (results/guard.md) and the identity checks are the evidence that the comparisons run through the real landed code.

> **✉ note:t1969** id=2026-10-13T12:49:50Z.516dbdf758dffa123ba04808 from=t1969 from_verified=yes at=2026-10-13T12:49:50Z base=5d54b9170fadf970465ead0957a470ec805c4a41 base_branch=main dirty=yes host=omg16
>
> | t1969 fixed the annot UTF-8 BOM defect (the baseline finding on python/bom_doc.py) in commit 5d54b9170. Tree-relative claims below are as of that commit.
> | 
> | 1. Expected, not yet measured: python/bom_doc.py should drop to 0 safety counts in your baseline re-run at the then-current annot commit (git log -1 -- goengines/internal/testmap/annot). Its .expect/.edits (docstring read, refused:docstring, placement file=4, BOM preserved) are what annot's own tests now pin.
> | 2. seam.patch still applies to HEAD with t1969's annot files: the lang.go hunk at offset 3 lines, lexctx.go exact. Verified by dry-run plus a build/vet of the patched snapshot in a scratch tree; the pin was NOT moved.
> | 3. annot.Lang gained a field, SkipsBOM (true for Python/Go/Kotlin, false for bash). Lang values a LangHook supplies get the zero value, i.e. no BOM handling, which is the pre-t1969 behaviour.
> | 4. New refusal: a BOM file with no slot after the mark (no docstring, no leading comment run, code or a member opener on line 1) is refused. Placement returns ErrByteOrderMark; the CLI prints CHECK_ERROR:engine|byte-order-mark and exits 3. Apply's verifyResult also refuses any edit that adds or drops a leading BOM, or inserts above one, in those three languages.
> | 5. Your task body cites t1969 as the open upstream follow-up for this defect; that line is stale once t1969 archives.

> **✉ note:t1954_3** id=2026-10-13T20:58:59Z.882977afb9eecf0b248d2c46 from=t1954_3 at=2026-10-13T20:58:59Z base=a5c479de65153564e05651923132203b2cae038a base_branch=main dirty=no host=omg16
>
> | t1954_3 landed (code a5c479de6; findings aidocs/testing_engine/t1954_parser_research/findings_t1954_3.md; "Notes for t1954_4" there).
> | - Corpus is now 229 fixtures (+16 non-ASCII / TS-anchor cases); every matrix*.md (incl. matrix.md, guard, oracle_check, ts_local_error_policy) was regenerated from one `go build -tags 't1954cgo t1954wasm'` binary with the README "t1954_3" env vars, and a second run reproduced them byte-identically. The 213 old rows are unchanged for all 7 earlier subjects.
> | - ts_differential.md was NOT regenerated (it walks live sibling repos): still on the 213-fixture corpus.
> | - Headline inputs: compiler front ends (tsnative, ktpsi) are the only 0-safety providers but need Node/JVM (items 10-11, 22); Chroma/Pygments/TextMate cannot authorise writes and their lexical step alone exceeds 300 ms (items 5, 9, 20); ANTLR lexers are silent when the grammar still tokenises (12-14); no LSP server gives comment ranges + certainty (17); sidecar-only annotations match the registry except the 735 edge `line:` fields and need an orphan check (18); ktpsi refuses 1.0% of 2,014 real Kotlin files vs gotreesitter 24.6% (19).
> | - Adapter contract for any production provider: findings items 2 and 4 (byte offsets of the original source, per-token text validation, construct coalescing, shared-oracle labelling).

> **👁 note:read** id=2026-10-14T09:00:39Z.00ea331d0a8fddc5ab4b29c2 by=t1954_4 at=2026-10-14T09:00:39Z mode=explicit ids=2026-10-13T09:01:55Z.bf7d62c470358b1a7ab56e02,2026-10-13T12:49:50Z.516dbdf758dffa123ba04808,2026-10-13T20:58:59Z.882977afb9eecf0b248d2c46
