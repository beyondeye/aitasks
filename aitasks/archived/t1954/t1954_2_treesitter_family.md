---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: high
depends: [t1954_1]
issue_type: chore
status: Done
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
implemented_with: claudecode/opus5_5
created_at: 2026-10-12 17:51
updated_at: 2026-10-13 17:25
completed_at: 2026-10-13 17:25
---

## Context

Child 2 of t1954 (annotation-parser research). It evaluates the **Tree-sitter family** on the infrastructure t1954_1 built: the research module at `aidocs/testing_engine/t1954_parser_research/`, the corpus and oracles, the immutable baseline, and the evaluation seam. The shared design is authoritative: read the parent plan `aiplans/p1954_research_multilanguage_annotation_parsers.md` and t1954_1's archived plan and `findings_t1954_1.md` first. Also read t1954_1's `results/feasibility.md` and any note sent to this task — they may re-scope candidates.

Engine constraints that decide eliminations:
- `CGO_ENABLED=0 -trimpath`; linux/darwin × amd64/arm64; offline prebuilt binaries.
- Dependency allowlist (yaml.v3, doublestar/v4, x/sync): a new dependency is a policy change to justify.
- `scan` budget 300 ms.

## Candidates

1. **gotreesitter** (`github.com/odvcencio/gotreesitter`, MIT): a pure-Go runtime that loads tree-sitter parse tables. About 119 of its 206 grammars ship **hand-written Go external scanners**. Pin a release and use curated build tags for the 8 grammars (bash, python, go, kotlin, typescript/javascript, java, rust, swift). Inventory which of those grammars rely on hand-ported external scanners and how parity is tested; those are custom readers by another name, so verify them hardest (bash heredocs, Python strings, Rust raw strings, TS templates, Kotlin, Swift).
2. **Official `github.com/tree-sitter/go-tree-sitter`** (cgo): the reference parser, with the same grammars on the C runtime and C scanners. Build it host-only under a separate build tag, so the default harness build stays CGO-free. Run a differential against gotreesitter, and record the CGO cost: the failure under `CGO_ENABLED=0` and the cross-toolchain needed for darwin.
3. **WASM**: the tree-sitter runtime and grammars compiled to wasm (`tree-sitter build --wasm`, via docker/emscripten in the scratch dir) run by wazero (pure Go), or an existing wrapper such as malivvan/tree-sitter. Prototype it if it builds; otherwise eliminate it with the recorded failure.

Each prototype implements the shared `Provider` interface:
- ERROR/MISSING nodes become `Diags`; a file with any of them is uncertain.
- Comments and string/heredoc/raw-string nodes become spans.
- Anchors come from nodes: package clause, imports, directive prologue, inner attributes.
- Python `DocInfo` comes from the module node: literal content bounds excluding prefix and quotes, raw flags, and the statement end including closing parens.
- Each runs the **full matrix in all 8 languages through the seam**: the lexical, range, record, edit, refusal and behaviour levels.

## Also deliver

- Grammar maintenance table: upstream repo, ABI version, last release, license, external-scanner presence, abandonment risk; curated pinned set vs bundle.
- Footprint (4 targets), cold/warm latency against the 300 ms budget, peak RSS.
- `findings_t1954_2.md`: observations / documentation claims / assumptions / unknowns, with the research date and versions.
- Path-scoped commits only; nothing under `goengines/` changes.

## Verification

- `baseline/fetch.sh && go run ./cmd/t1954 matrix --provider <p>` reproduces `results/matrix_<p>.md`.
- The cgo provider builds only under its tag.
- The default module build passes with `CGO_ENABLED=0`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1954_1** id=2026-10-12T18:32:40Z.2d9516da574a8888ff5ceeea from=t1954_1 from_verified=yes at=2026-10-12T18:32:40Z base=13a8751d59fde438d0a871bd130bc70fb4df23eb base_branch=main dirty=yes host=omg16
>
> | The t1954 shared design (aiplans/p1954_research_multilanguage_annotation_parsers.md, "Experimental interface") was amended during t1954_1's plan review:
> | - Capabilities gained `Anchors AnchorSet`: an anchor the provider does not declare is UNKNOWN, never "none"; a declared anchor with value 0 is confirmed-empty.
> | - `ToContext(lang, src, caps, res, need)` enforces per-operation requirements itself: every write needs `Errors` (and `DocLiterals` for Python); only fresh file-level insertion needs the per-language anchor table. Missing → unsupported:<cap> for that op only.
> | - TS/JS native evidence must come from parser-aware extraction (bare ts.createScanner misreads template continuations); any native oracle overriding a hand .expect must pass a self-test with a negative control.
> | - Bench: cold = one timed first op per fresh process incl. provider init; only end-to-end registry.Scan is compared to the 300 ms budget; lexical-only rows are labelled.
> | Hedge: the harness code implementing this lands with t1954_1's commit, not yet at the time of this note.

> **✉ note:t1954_1** id=2026-10-12T18:38:44Z.2478fd304fdae715b128d72e from=t1954_1 from_verified=yes at=2026-10-12T18:38:43Z base=e3ddd44c5b6ff4d33ab7b8250f632fa2d20d05ba base_branch=main dirty=yes host=omg16
>
> | Feasibility smoke (t1954_1 pre-phase; evidence will be in aidocs/testing_engine/t1954_parser_research/results/feasibility.md, landing with t1954_1's commit):
> | - gotreesitter v0.55.1 builds CGO_ENABLED=0 for all 4 release targets and parsed all 9 research grammars correctly on a fake-comment-in-string snippet. Default binary 35 MB (all grammars); `grammar_subset` + 9 grammars 16.9 MB.
> | - Official go-tree-sitter v0.25.0 + tree-sitter-go: CGO_ENABLED=0 fails (bindings are cgo-only); cgo builds on the host only — darwin/arm64 cross-cgo fails without C cross toolchains. Host-only reference as planned.
> | - The only wazero wrapper found, malivvan/tree-sitter v0.0.1 (pre-release), bundles ONLY C and C++ grammars. The WASM route for the 8 languages therefore needs our own runtime+grammar wasm build — re-scope the WASM step accordingly (the wrapper alone is not a candidate for these languages).

> **👁 note:read** id=2026-10-13T10:24:51Z.354c8675815e45808ef583af by=t1954_2 at=2026-10-13T10:24:51Z mode=explicit ids=2026-10-12T18:32:40Z.2d9516da574a8888ff5ceeea,2026-10-12T18:38:44Z.2478fd304fdae715b128d72e

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-13T12:45:38Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-10-13T14:24:26Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-10-13T14:25:11Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:d855e0b0de0c1d31

> **✅ gate:risk_evaluated** run=2026-10-13T14:25:11Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/1954_2/risk_evaluated_2026-10-13T14:25:11Z-risk_evaluated-a1.log`
