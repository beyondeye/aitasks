---
Task: t1954_4_report_recommendation_trail.md
Parent Task: aitasks/t1954_research_multilanguage_annotation_parsers.md
Sibling Tasks: aitasks/t1954/t1954_1_*.md, aitasks/t1954/t1954_2_*.md, aitasks/t1954/t1954_3_*.md
Archived Sibling Plans: aiplans/archived/p1954/p1954_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-14 18:58
---

# Plan: t1954_4: report, recommendation, trail and follow-ups (verified 2026-10-14)

## Context

This is the final child of t1954, and it is the synthesis. The parent task's sections *Deliverables and trail integration* and *Acceptance criteria* are binding. Inputs:
- the parent task;
- the parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md`;
- the archived plans of t1954_1–3;
- `R/findings_t1954_{1,2,3}.md` and `R/results/**`, where `R = aidocs/testing_engine/t1954_parser_research/`.

The current four-language M2.2 work stays unblocked. Nothing here becomes a hard prerequisite of it.

## Step 0: reality check (done at verification, 2026-10-14)

- **The annot code moved past the pin.**
  - `R/baseline/PIN` is `f096db065` (t1853_2).
  - `git log -- goengines/internal/testmap/annot` shows two later commits: `5d54b9170` (t1969, the BOM fix) and `2c04a9639` (t1853_3). They change `lang.go` (adding `Lang.SkipsBOM`), `lexctx.go`, `grammar.go`, `rewrite.go` and `stampverbs.go`.
  - `seam.patch` touches only `lang.go` and `lexctx.go`. `fetch.sh` applies it with `patch -p1 --forward --batch`, which tolerates offsets. The t1969 note says it applies at `5d54b9170` with an offset of 3.
  - `annot/source.go` currently has uncommitted edits by another session. They are irrelevant: snapshots come from commits only.
- **No fixture is `native: none`.**
  - kotlinc 2.4.21 and swiftc 6.2.4 were obtained by t1954_1. `oracle_check.md` reports "native none = 0" in every language.
  - Java, Rust, Kotlin and Swift have validity evidence only; there is no comment oracle in `oraclecheck`.
  - For Kotlin, `ktpsi` (t1954_3) supplies independent compiler-PSI evidence: 0 on every safety column, and 0 comment-class or record differences against the baseline on real Kotlin files.
  - So the post-phase `native_oracle_gap_followup` trigger does not fire as written. The policy still makes no claim beyond the evidence (Step 4).
- **The earlier tool installs still exist** in t1954_3's scratch dir:
  - `…/50614bdc-…/scratchpad/t3env.sh` (Pygments venv, TextMate/LSP `node_modules`, kotlinc, gopls, kotlin-lsp, scc, zig);
  - the git-ignored build products `R/.tsref/`, `R/.tswasm/ts.wasm` and `R/.ktpsi/`.
- **The trail `art:trail-testmap-feature`** is at version `e658a5b4…` (**lite**, 2026-10-12).
  - `drift` reports STALE: t1853_2 and t1853_3 completed; new members t1854_1–4, t1954_4, t1975 and t1977; dependency and gate changes on t1853_4, t1853_7 and t1854.
  - The live topic snapshot has 27 members.
  - The `e-parser-research` entry says "the research result is not yet available".
- **Consumers.** These IDs are unchanged and none has children:
  - t1853_2 and t1853_3 are archived;
  - t1855, t1857, t1858, t1860, t1861 and t1863 are Ready;
  - t1853_7 is Postponed.
  
  All five M10 targets (aitasks, aitasks_go, thinking_backend, aitasks_mobile, thinking_app) are bash/Python/Go/Kotlin. aitasks_mobile also has 2 Swift files.
- **Artifact store.** `ait artifact create` takes an open `--kind` set, with a 25 MB cap (`artifact_max_size_mb`). The `local` backend commits blobs to the data branch, so the bundle must stay compact.

## Expected recommendation (to be confirmed by the final rerun; the report states it only if the numbers hold)

**Retain the landed M2.2 readers, and add a conformance gate. There is no candidate yet for additional languages.**

The landed readers are go/scanner for Go and the hand readers for bash, Python and Kotlin. They are the only pure-Go configuration that meets all of these:
- 0 on every safety column in all four supported languages (the Python BOM defect is fixed by t1969, to be confirmed at the new pin);
- inside the 300 ms budget (≈24 ms);
- no dependency-policy change.

Every alternative fails on at least one axis:
- **Safety:**
  - shfmt: bash heredoc FP-writable;
  - Tree-sitter: bash, Kotlin and Swift;
  - Chroma, Pygments and TextMate: every language;
  - ANTLR: silent on malformed input.
- **Build policy:** tscgo needs cgo.
- **Budget:** every Tree-sitter runtime is 1.2–3.0× over; the highlighters' lexical step alone is 3–6× over.
- **Shipped runtime:** pytokenize needs CPython, tsnative needs Node, ktpsi needs a JVM. These are excellent as **dev-time oracles**, not as production providers.
- **No certainty signal:** no LSP server gives comment ranges and certainty in one answer.

Language expansion is closed until a provider passes a written onboarding contract. gotreesitter is the leading future candidate for TS/JS, Java and Rust: 0 safety failures on the corpus in those languages. Its unresolved gaps are named: footprint, budget, dependency policy, and thin real-file evidence. Sidecar-only annotations are recorded as a product option, not adopted.

If the rerun contradicts any premise above, the report says so and the recommendation follows the numbers.

## Steps

0. **Reconstructible inputs (from the plan review).**

   `realrepo`, `tsdiff` and `bench`'s lexical sets list the live working trees (`git ls-files --cached --others --exclude-standard`) and read their current bytes. That includes other sessions' uncommitted edits, which a HEAD SHA cannot reconstruct. So every repository-derived measurement in this task runs against **temporary checkouts of recorded commits**, never a live tree.
   1. For each of the six registered repositories (aitasks, aitasks_go, aitasks_mobile, thinking_app, thinking_backend, timexchange), resolve its path with `./ait projects resolve`. Then record:
      - `HEAD` SHA and tree id;
      - whether the commit is on a remote-tracking ref (`git branch -r --contains`): a pushed commit stays reconstructible by others, while an unpushed one is labelled as such;
      - the live tree's `git status --porcelain` count, as context only: those edits are **excluded** from the evidence.
   2. Create the snapshot with `git clone -q --no-checkout <path> <scratch>/snap/<name> && git -C <snap> checkout -q --detach <sha>`. This is read-only on the source.
   3. Verify the snapshot: `rev-parse HEAD` equals the SHA, and the snapshot's `status --porcelain` is empty, so `ls-files --others` contributes nothing.
   4. Write the table to `results/t4/inputs.md`, with the rebuild recipe (`git clone <repo> && git checkout <sha>`).
   5. Harness change, behaviour-neutral for existing invocations, with a unit test for the parser:
      - `tsdiff --repos` and `bench --siblings` accept `name=path` entries, used as given with no `projects resolve`;
      - `bench` gains `--aitasks <path>` for its aitasks test-file set (default unchanged: the live toplevel);
      - `realrepo` already takes `--repo <path>`.
   6. Every repository-walk output in `results/t4/` names its input as `<name>@<sha> (snapshot)`. No live-tree run is planned. If one becomes necessary, it goes to a separately labelled `results/t4/live_*.md`, marked "moment-relative, not reconstructible", and is never mixed into the snapshot tables.
   7. The corpus and harness inputs are the research dir's committed files. Before every run, check `git status --porcelain -- aidocs/testing_engine/t1954_parser_research` is empty, apart from this task's own in-progress files, which are committed with the results.

1. **Reproduce at the research pin (`f096db065`), one environment.**
   1. `source …/t3env.sh`, then `baseline/fetch.sh && baseline/fetch.sh --unpatched`.
   2. Run `go vet ./... && go test ./...` in default mode and with `-tags 't1954cgo t1954wasm'`.
   3. Build one binary, `go build -tags 't1954cgo t1954wasm' -o <scratch>/t1954 ./cmd/t1954`.
   4. Run `guard`, `matrix` (all subjects), `oraclecheck` and `localpolicy` into `<scratch>/repro_f096/`, and `diff -r` the output against the committed `results/`. Expected: byte-identical except identity and date lines.
   5. Name every difference and attribute it. A difference does not block the run: the run continues and the report records it.
2. **Move the pin to the then-current annot commit.**
   1. Find it with `git log -1 --format=%H -- goengines/internal/testmap/annot` (expected `2c04a9639`). Use whatever it is at that moment, and record it.
   2. Edit `PIN`:
      - `commit:`;
      - `tree:` from `git rev-parse <c>:goengines`;
      - `seam_sha256:` only if the patch has to be re-diffed. The content must stay the same two hooks.
   3. Re-fetch both snapshots, then run `go vet` and `go test`.
   4. If the harness does not compile against the new `annot` API, adapt only `internal/seam` / `provider`, keeping behaviour unchanged, and record each change in `results/t4/README.md`.
   5. Run `guard --out results/t4/guard.md`. It must pass: the seam stays neutral at the new pin.
3. **Final rerun at the new pin**: every provider, one binary, every output under `results/t4/`.

   The top-level `results/*` and `results/{ts,t3}/` files stay unchanged. They are t1954_1–3's dated evidence at `f096db065`, and the findings files cite them.
   - `matrix --out results/t4`: all 13 subjects.
   - `oraclecheck`, `localpolicy`, and `tsdiff --repos <name>=<snap>,…` (the 229-fixture corpus plus the six step-0 snapshots).
   - `realrepo --provider all --repo <snap> --name <name>` for each of the six step-0 snapshots: aitasks plus the five siblings.
   - `bench --title t1954_4 --aitasks <snap/aitasks> --siblings <name>=<snap>,…`, with every end-to-end and lexical subject in one run. The end-to-end workload is the generated M2.2 shape, unchanged.
     - Same-run baseline control; 1-minute load recorded before and after.
     - Host noise is stated. Ratios are compared, not absolute times.
   - `footprint`, `footprint --ts --ts-only --zig`, `footprint-t3`, `sidecar` and `lsp`.
   - `env` into `results/t4/environment.md`, plus `env --t3` into the same file.
   - **Post-phase pin comparison:** add the verb `pindiff`. It compares two matrix directories' *Per case* rows and *Notes per case* blocks, keyed by (subject, lang, case), and writes `results/t4/pin_compare.md`. Every differing case is listed with both rows, for every subject; the baseline is listed first.
   - Write `results/t4/README.md`:
     - what was run, and the exact commands;
     - the reproduction verdict from step 1;
     - the pin move;
     - the logs' location in the evidence bundle.
   - Update `R/README.md`: the two pins, `results/t4/`, how to reproduce the child-era results by restoring the old PIN, and `pindiff`.
4. **Language policy.** Production support status and oracle coverage are two separate tables. Each claim names its evidence.
   - **Oracle coverage** (what independently checks the hand oracle), from `oracle_check.md` and the matrices:

     | language | comment-range oracle | provenance note | validity / execution |
     |---|---|---|---|
     | bash | shfmt / mvdan (comment lines) + bash execution of the controlled heredoc fixtures | shfmt has its own documented defects (FP-writable heredoc continuation, silent heredoc-in-backticks), so the hand oracle + execution decide | `bash -n`, execution |
     | Python | `tokenize` + `ast` | independent of the baseline | CPython |
     | Go | `go/scanner` | **partly self-consistency**: the baseline Go reader *is* go/scanner | `go/parser`, gofmt, `go run` |
     | TS / TSX / JS | the parser-aware TypeScript extractor `ts-parser` (TypeScript 5.9.3; `--selftest` with a naive-scanner negative control; 17/17 hand comment agreement) | `tsnative` shares `oracle/ts_oracle.js`, so tsnative's range agreement is **self-consistency, not independent validation** (`provider.SharedOracle`) | the TS parser, node execution |
     | Kotlin | none in `oraclecheck`; independent evidence from the `ktpsi` provider (compiler PSI): corpus safety 0, and 0 class or record differences against the baseline on real Kotlin files | ktpsi is a provider under test, not a self-tested oracle | kotlinc 2.4.21 |
     | Java, Rust, Swift | none | — | javac, rustc, swiftc (validity and execution only) |
   - **Production support status:**
     - **Supported** (bash, Python, Go, Kotlin): inline annotations are read and written through the landed readers. The evidence:
       - the safety columns at the new pin;
       - real-repository agreement on the step-0 snapshots, per the oracle table;
       - the known fail-closed costs (bash over-refusals; the `x-policy` lines).
     - **Unsupported** (every other language, including TS/JS/TSX, Java, Rust and Swift): no production provider meets the contract.
       - TS/JS/TSX: tsnative needs Node; gotreesitter has open footprint, budget and dependency-policy gaps. Unsupported status here is **not** a claim that no oracle exists: the ts-parser oracle is acknowledged and can serve a future onboarding.
       - Java, Rust, Swift: additionally have no comment-range oracle.
       - The explicit outcome is `ErrNoLeader` / `ADOPT_SKIP …|no-leader`.
     - **Experimental:** none in production.
   - **Decision checkpoint (conditional).** If the final rerun contradicts a premise of the expected recommendation, stop before writing the report. Examples: a safety cell for a supported language is non-zero at the new pin; the budget no longer holds; a premise about a candidate changed. Present the changed numbers and the revised decision with `AskUserQuestion`. Otherwise continue.
5. **Evidence artifact.**
   1. Build `<scratch>/t1954_evidence.tar.zst` containing:
      - every verb's stdout and stderr from steps 1–3;
      - the `repro_f096/` matrices and their diff;
      - the per-file real-repository outputs;
      - text logs from t1954_1–3's scratch dirs, if present (`*.log`, `*.md`, size-bounded, labelled with their provenance; never tool installs);
      - a `MANIFEST` with the sha256 of every file.
   2. Check the size: under 25 MB, aiming for only a few MB.
   3. Run `./ait artifact create 1954 <bundle> --kind research_evidence --name "t1954 parser research raw evidence"`, after confirming the parent task file is clean.
   4. Record the `HANDLE:` (expected `art:t1954-researchevidence`).
6. **Report** `aidocs/testing_engine/t1954_annotation_parser_research.md`. Sections:
   - **Summary and decision.**
   - **Method:**
     - corpus (229), seam, metrics, the two pins, environment;
     - reproducibility: every command, and the reproduction verdict.
   - **Candidate matrix**, safety columns first:
     - all 13 subjects × 8 languages from `results/t4/matrix.md`;
     - plus the non-seam families: LSP, sidecar, eliminated by class.
   - **Per-family evaluation**: observations, documentation claims, assumptions and unknowns, each in its own subsection per family. Every number cites a committed result file.
   - **Rejected alternatives**, each with its evidence: the t1954_3 item-26 ledger, extended with the reasons from t1954_1 and t1954_2.
   - **Dependency, licensing and maintenance**:
     - the allowlist impact;
     - binary size delta;
     - the runtime each subject needs;
     - license and cadence, from t1954_3 item 25 and `ts_grammars.md`.
   - **Recommendation**, as above, or what the numbers force instead.
   - **Language policy**: the tiers from step 4; the onboarding trigger, which is a target repository needing a new language; what a new language must pass.
   - **Provider/adapter contract** (bounded):
     - trustworthy comment locations: byte offsets of the original source; Layer-1 token-text validation; Layer-2 coalescing that never absorbs a tool's own comments;
     - uncertainty: a Diag means a whole-file refusal (local refusal makes a look-alike writable, per `ts_local_error_policy.md`); a provider error means "unsupported", never "no comments";
     - safe placement: anchors declared per language, with "undeclared" meaning unknown;
     - capability declarations, with per-operation enforcement through `ToContext`;
     - onboarding: fixture classes per language, a native oracle at dev time, a budget measurement, the dependency-policy review, and a proposed placement rule labelled *proposed* until validated;
     - conformance fixtures: the t1954 corpus format.
   - **Migration sketch and complexity comparison** (no schedules). A table with:
     - status quo plus the conformance gate;
     - promoting the seam to a production provider interface, when the first new language arrives;
     - a gotreesitter subset for one language;
     - a sidecar route for unsupported languages;
     - subprocess providers (rejected).

     Columns: new dependencies; binary size delta; budget fit; per-language cost; shared-engine cost; measured safety.
   - **Impact** on the centralized rewriter (`Apply` stays the only writer), conflicts, root confinement and no-follow, stamp and provenance, annotate, verify, stale confirmation, adoption, author annotation and the repair loop. Each has a concrete statement, based on the seam evidence that providers ran through the unchanged `ParseFile → PlanCovers → Apply`.
   - **Consumer evaluation table**: t1853_2, t1853_3, t1855, t1857, t1858, t1853_7, t1860, t1861 and t1863. Each gets an *action* or *context* verdict and a one-line reason (draft below).
   - **Follow-ups and notes**, filled in after steps 7–8; IDs are back-filled.
   - **Residual risks**, **Unknowns**, and an **Evidence index** of every path and the artifact handle.
7. **Follow-ups**, bounded and anchored to 1852. The number of follow-ups is driven by the recommendation, never by a quota.
   - **F1, `annot_conformance_suite`.** Created with `aitask_create.sh --batch --commit --type test --priority medium --effort medium --labels testing,testmap,go_engine --anchor 1852`, no `depends`.
     - Copy the bash, Python, Go and Kotlin fixtures from the t1954 corpus into `goengines/internal/testmap/annot/testdata/conformance/`. They keep their `.in` suffix and carry a provenance file with the corpus commit and sha256 values.
     - Add `conformance_test.go`. It drives `ParseFile → PlanCovers → Apply` in a temp dir and asserts:
       - the four safety metrics are 0;
       - the read records are equal;
       - fidelity holds (CRLF, final newline, BOM, mode);
       - the known over-refusals and `x-policy` cases are pinned as an explicit list, so a fix shows up as a change;
       - a negative control: a mutated classifier fails the test.
     - No new dependencies. The research harness stays unchanged.
     - Justification: the readers are retained, so a hermetic gate against further `annot` edits is the main risk control. `annot` already changed twice after the research pin.
   - **Conditional F2, `annot_<case>_safety_regression`** (`upstream_defect`): created only if step 3 shows a non-zero safety cell for a supported language at the new pin.
   - **`native_oracle_gap_followup`**: not triggered (Step 0), so no task. The report records the evidence that it is not needed.
8. **Commits**, path-scoped only. They run here, so that the notes and the trail cite committed paths.
   - `chore: Rerun the t1954 parser research at annot <short> (t1954_4)`: `R/baseline/PIN`, `R/cmd/t1954/pindiff.go`, the step-0 `name=path` / `--aitasks` changes in `R/cmd/t1954/{tsdiff,bench}.go` (each with its test), any `internal/seam` adaptation, `R/results/t4/**`, `R/README.md`;
   - `documentation: Add the t1954 annotation-parser research report (t1954_4)`: the report alone, with the follow-up IDs already back-filled;
   - task and plan files through `aitask_task_commit.sh`. The follow-up and the notes commit themselves.
9. **Notes** through the `/aitask-note` skill, with `--from 1954_4`, the report path, the decision and the verdict, and `--with-live`. Each note gets a short body, hedged where the claim is moment-relative.
   - **t1855** (context): M4.2 re-stamps through the unchanged annot. Unsupported-language tests carry no annotations to confirm.
   - **t1857** (action): adoption and onboarding surface unsupported-language test files explicitly (`ADOPT_SKIP …|no-leader`). The onboarding docs state the four-language policy. Placement is unchanged.
   - **t1858** (context plus one check): `annotate --author` on an unsupported-language or uncertain file must refuse explicitly. `annot`'s `ErrNoLeader`, `ErrUncertainContext` and `ErrByteOrderMark` are the inputs.
   - **t1853_7** (action): the rule-to-repair matrix classifies unsupported-language, uncertain and BOM-no-slot files as terminal, classified failures, never as repair targets. No second writer, because sidecar is not adopted.
   - **t1860** (action): document the language policy and the annotation-line rules: a standalone comment line; never in heredocs, strings, backtick substitutions or continuation lines; the docstring is read-only.
   - **t1861** (context plus a suggestion): every target is in the supported four, and Swift (2 files) is unsupported. Re-run the read-only `realrepo` against each target at rollout time, at the then-current annot.
   - **t1863** (action): link the report, the evidence handle and F1 in the cross-linking pass. The research-result handoff is now resolved.

   Each note must return `NOTE_APPENDED:`.
10. **Refresh the trail** at **deep** depth, following the `aitask-trail` Step 3 procedure:
   - resolve `--refresh art:trail-testmap-feature --deep`; base version `e658a5b4…`; drift; re-snapshot topic 1852 (with `--owner 1852`, falling back to the topic-only snapshot that echoes `OWNER:aitasks#1852`, per the stored method note);
   - classify all members, including the new t1854_1–4, t1954_4, t1975, t1977 and F1;
   - run the deep follow-up sweep for t1853_2 and t1853_3;
   - add observations with `evidence_refs`, `hard_depends` relations mirroring the recorded `depends`, `advisory_precedes` for the advisory order, and exclusions;
   - replace `e-parser-research`'s "not yet available" with the decision, the exact report path and the artifact handle;
   - record the residual risks, the affected modules (`annot`; `deps` blankers as context) and the landing order (F1 advisory, ahead of further `annot` edits by t1853_4–6 and t1858);
   - this is a lite → deep upgrade, so the downgrade preflight does not apply;
   - show the diff summary, then the **non-skippable confirmation**;
   - validate with `--expect-depth deep` and `drift` (CURRENT); run the stale-base guard; run `aitask_artifact.sh update`; print the run summary.
11. **Link check.**
    - Every path the report and trail cite resolves with `test -e` (task and plan paths resolved through `aitask_query_files.sh`).
    - Every handle resolves through `./ait artifact versions` / `get`.
    - `versions art:trail-testmap-feature` shows the new version, which names the report and the evidence handle.
    - A broken citation in the report is fixed in a follow-on path-scoped `documentation:` commit.

### Post-phase (risk mitigations)

1. [baseline_rerun_at_landed_commit] This is done by steps 2–3 and `pin_compare.md`. Every differing baseline case is named in the report. Expected: `python/bom_doc.py` drops to 0 on all safety columns (t1969). Any other difference is attributed to the annot commit that caused it.
2. [native_oracle_gap_followup] Evaluated at Step 0: no language is `native: none`, so no follow-up is created. The policy makes no supported claim beyond the evidence named in step 4. Java, Rust and Swift, which have no comment-range oracle, stay unsupported.

## Verification

- The report exists at `aidocs/testing_engine/t1954_annotation_parser_research.md`.
- `results/t4/` holds the final run, including `guard.md` (PASS), `pin_compare.md` and `inputs.md`.
- Every repository-walk output names `<name>@<sha> (snapshot)`, and `inputs.md` rebuilds each input from a commit.
- The report's oracle-coverage table credits the ts-parser oracle and labels tsnative as self-consistency.
- `go vet` and `go test` of the harness pass in both builds.
- `ait artifact versions art:trail-testmap-feature` shows a new **deep** version linking the report and the evidence handle.
- F1 (and F2, if triggered) exist with `anchor: 1852`.
- Every note returns `NOTE_APPENDED:`.
- Nothing under `goengines/` is modified by this task.
- Commits are path-scoped.

## Step 9 reference

Commits as in step 8, then standard child archival. The parent t1954 archives with this last child.

## Risk

### Code-health risk: low
- Moving the PIN changes what the README commands regenerate. Overwriting the child-era results would orphan the citations in `findings_t1954_{1,2,3}.md`. · severity: low · → mitigation: in-plan (step 3: the final run goes to `results/t4/`; the top-level and `ts/` / `t3/` results stay unchanged; the README documents both pins)
- Adapting the harness to the new annot API could change behaviour and contaminate the pin comparison. · severity: low · → mitigation: in-plan (step 1 reproduction at `f096db065` before the move; step 2 `guard` must pass at the new pin; each adaptation is recorded)
- The worktree is shared: another session holds uncommitted `annot/source.go` and `deps` edits, and the data-branch index is shared too. · severity: low · → mitigation: in-plan (snapshots come only from commits; path-scoped commits; the artifact CLI refuses a dirty task file)
- The evidence blob is committed to the data branch, so it grows that branch's history. · severity: low · → mitigation: in-plan (step 5: compressed and size-checked, no tool installs or binaries)

### Goal-achievement risk: medium
- The expected recommendation ("retain the landed readers; no candidate yet for new languages") could read as the unexamined custom-reader strategy the user ruled out. · severity: medium · → mitigation: in-plan (the F1 conformance gate makes the readers examined; a written onboarding contract with a trigger; a named leading candidate with its open gaps measured; the report follows the numbers)
- The new pin (t1853_3 changed `grammar.go`, `rewrite.go` and `stampverbs.go`) could show a safety regression in the retained readers, which would change the decision. · severity: medium · → mitigation: in-plan (`pin_compare.md`; the conditional F2 `upstream_defect` follow-up; the step 4 decision checkpoint)
- Benchmarks run on a shared host with concurrent agent sessions, so absolute times are noisy (t1954_3 measured about 20%). · severity: low · → mitigation: in-plan (step 3: same-run baseline control, load recorded, ratios compared)
- The repository walks (`realrepo`, `tsdiff`, `bench`'s lexical sets) list and read live working trees, including other sessions' uncommitted edits. A HEAD SHA cannot reconstruct those inputs, and output checksums preserve results, not inputs. · severity: medium · → mitigation: in-plan (step 0: every walk runs against temporary checkouts of recorded commits, with SHA, tree and pushed state in `results/t4/inputs.md`; any live-tree observation is labelled separately; differences from the child-era live-tree results are reported as "child-era input not reconstructible" rather than attributed)
- The research pin moves while the child-era top-level results stay at `f096db065`. A reader could compare across pins without noticing. · severity: low · → mitigation: in-plan (identity lines on every file, `pin_compare.md`, the README section on the two pins)
- The deep trail refresh means hand-authoring JSON for about 28 members while some are being implemented concurrently (t1854_1, t1975, t1977). · severity: low · → mitigation: in-plan (schema validation with `--expect-depth deep`, `drift` CURRENT before the write, the stale-base guard)

Every risk above carries an in-plan mitigation. No spawned task or inline phase is proposed: `risk_mitigations_planned = false`. The parent plan's two post-phase mitigations are carried in the Post-phase block.
