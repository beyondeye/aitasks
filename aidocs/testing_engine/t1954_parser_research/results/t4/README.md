# t1954_4 final run

Every verb of the harness, rerun in one environment
(`environment.md`) at the then-current `annot` commit, on the final corpus.
The report that consumes these files is
`aidocs/testing_engine/t1954_annotation_parser_research.md`.

| | |
|---|---|
| date | 2026-10-14 |
| pin | `3d1a2b628fc07f75b279c0c125ed4705316c9368` (annot as of t1854_1), moved from the research pin `f096db065`; `seam.patch` applies unchanged (same sha256) |
| corpus | 240 fixtures (`../../README.md`, *Layout*) |
| repository inputs | temporary checkouts of recorded commits, never live trees (`inputs.md`) |
| bench host | 24 CPUs shared with concurrent agent sessions; 1-minute load 3.65 before and 4.43 after the bench (`bench.md`, and the log in the evidence bundle) |
| binary | one build, `go build -tags 't1954cgo t1954wasm'`, used by every verb below except `realrepo`, `sidecar`, `lsp` and `footprint*`. Those ran from an earlier build of the same sources, before `pindiff.go`, the `oraclecheck` BOM fix and a usage-string edit, none of which they execute |

## 1. Reproduction at the research pin

Before the pin moved, the committed research dir (sources + 229-fixture
corpus, from a `git archive` of HEAD) was rebuilt in a scratch tree against
the `f096db065` snapshot and run:

```bash
go build -buildvcs=false -tags 't1954cgo t1954wasm' -o t1954 ./cmd/t1954
./t1954 guard --out <d>/guard.md
./t1954 matrix --out <d>
./t1954 oraclecheck --out <d>/oracle_check.md
./t1954 localpolicy --provider gotreesitter,tscgo,tswasm,shfmt,pytokenize,goscanner --out <d>/ts_local_error_policy.md
```

Verdict: `guard.md`, all 14 `matrix*.md`, `oracle_check.md` and
`ts_local_error_policy.md` are **byte-identical** to the committed
`../guard.md`, `../matrix*.md`, `../oracle_check.md` and
`../ts_local_error_policy.md`. The child-era results reproduce from their
committed inputs.

## 2. The pin move

`../../baseline/PIN` now names `3d1a2b628`. The harness compiled against the
new `annot` API unchanged. The patched and unpatched snapshots differ by
exactly the two hooks. Moving the pin made `corpus/gen/gen_corpus.py`
re-import M2.2's tables from the new commit:
- the `origin:` note of every imported `.expect` changed (no `.in` changed);
- t1969's 5 BOM cases were added.

Two importer defects that those cases exposed were fixed in `corpus/gen/`:
- a BOM before line 1's annotation hid it from the mark regex;
- `doc_shape_10.py` had no hand `DocEnd`.

## 3. Commands (in the research dir, `source <t3env.sh>` for the tool variables)

```bash
B=<binary>
$B guard --out results/t4/guard.md                        # GUARD:PASS at the new pin
$B matrix --out results/t4                                # all 13 subjects
$B oraclecheck --out results/t4/oracle_check.md
$B localpolicy --provider gotreesitter,tscgo,tswasm,shfmt,pytokenize,goscanner --out results/t4/ts_local_error_policy.md
for n in aitasks aitasks_go aitasks_mobile thinking_app thinking_backend timexchange; do
  $B realrepo --repo <snap>/$n --name $n --provider all --input-label --out results/t4
done
python3 tools/agg_realrepo.py results/t4 > results/t4/realrepo_totals.md
$B tsdiff --repos aitasks=<snap>/aitasks,aitasks_go=<snap>/aitasks_go,… --out results/t4/ts_differential.md
$B sidecar --out results/t4/sidecar.md
$B lsp --out results/t4/lsp.md --workdir <scratch>
$B footprint --out results/t4/footprint.md
$B footprint --ts --ts-only --zig "$T1954_ZIG" --ts-out results/t4/footprint_ts.md
$B footprint-t3 --out results/t4/footprint_t3.md
$B bench --title t1954_4 --out results/t4/bench.md --aitasks <snap>/aitasks --siblings aitasks_go=<snap>/aitasks_go,… \
  --subjects baseline,shfmt,pytokenize,native,gotreesitter,tscgo,tswasm,chroma,pygments,textmate,tsnative,ktpsi,antlr \
  --lex-subjects baseline,goscanner,shfmt,pytokenize,gotreesitter,tscgo,tswasm,chroma,pygments,textmate,tsnative,ktpsi,antlr \
  --labels 'tscgo=host-only'                              # alone on the host, last
$B env --out results/t4/environment.md && $B env --t3 --out results/t4/environment.md
```

## 4. Pin comparison (post-phase `baseline_rerun_at_landed_commit`)

The same final corpus was also run at `f096db065`: a scratch copy of these
sources, with the old PIN and its snapshot. That old-pin directory is not
committed; it is in the evidence bundle. The comparison:

```bash
$B pindiff --old <old-pin matrix dir> --new results/t4 --out results/t4/pin_compare.md
```

Result (`pin_compare.md`): **5 differing cases, all in the baseline, all
BOM cases that t1969 fixed**:
- `python/bom_doc.py`;
- t1969's own `lex_bom_comment.{go,kt,py}` and `doc_shape_10.py`.

The baseline's safety totals go from FP-writable 3 / Record-corruption 6 to
3 / 1; what remains is the Kotlin multi-dollar case, identical at both pins.
The other 12 subjects are identical at both pins.

## 5. Files

| file | what |
|---|---|
| `inputs.md` | the recorded commit, tree and pushed state of every walked repository |
| `guard.md` | seam neutrality at the new pin |
| `matrix.md`, `matrix_<subject>.md` | the safety-first matrices, 13 subjects × 8 corpus directories |
| `oracle_check.md` | native cross-checks of the hand oracles |
| `pin_compare.md` | the case-by-case comparison of the two pins |
| `ts_local_error_policy.md` | the ±1-line refusal alternative |
| `realrepo_<repo>.md`, `realrepo_totals.md` | read-only real-repository disagreement against the baseline |
| `ts_differential.md` | the Tree-sitter runtime differential (corpus plus the snapshots) |
| `bench.md` | performance: end-to-end scan against the budget, plus lexical-only rows |
| `footprint.md`, `footprint_ts.md`, `footprint_t3.md` | static-binary size per target, and subprocess runtime sizes |
| `lsp.md`, `sidecar.md` | the non-provider experiments, rerun |
| `environment.md` | host, toolchains, tool versions |

Raw stdout and stderr of every run, the old-pin matrices and the reproduction
outputs: `art:t1954-researchevidence`.
