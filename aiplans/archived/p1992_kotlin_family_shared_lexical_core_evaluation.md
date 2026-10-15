---
Task: t1992_kotlin_family_shared_lexical_core_evaluation.md
Base branch: main
Output branch: main
---

# t1992 — Kotlin-family lexical core: measure, decide, safeguard

## Context

Three hand lexers model Kotlin's lexical boundaries independently:

| lexer | file | consumer |
|---|---|---|
| annot line classifier | `goengines/internal/testmap/annot/lexctx.go` `classifyKotlin` | annotation read/write (`ParseFile → PlanCovers → Apply`) |
| `ktLex` | `goengines/internal/testmap/deps/kotlinlex.go` | `.kt` dependency scanner (`kotlin.go`, `frombody.go`) |
| `blankGradleComments(src, kts=true)` | `goengines/internal/testmap/deps/gradlelex.go` | `.gradle.kts` module graph (`gradle.go`) |

The same construct has now needed three separate fixes **twice in one week**:
- Kotlin 2.2 multi-dollar strings: t1975 (kts, fail closed), t1980 (ktLex, fail closed), t1990 (annot, **modelled**);
- the `` $`name` `` short template: t1990 (annot), then t1999 (ktLex and kts — found only because t1990 probed deps).

t1992 decides, on measured evidence, whether they should share one lexical core, and makes sure the cheaper safeguard exists either way.

### State at plan base `555e28536` (re-verified; supersedes the task body)

The task body was written before t1990/t1991/t1997/t1999/t2002/t2012/t2022 landed. Five notes arrived (advisory, senders `from_verified=yes`). Each tree-relative claim was checked against `555e28536`:

- **annot models multi-dollar strings; deps fail closed on them.** `kotlinDollars` + per-frame `dollars` in `lexctx.go` (t1990). The task's premise "all three lexers first agree on failing closed" is **wrong**: t1990 chose to model because annot cannot fail closed per file. Verified: an `Uncertain` context on a file that carries `testmap:` makes `ParseFile` return a `SyntaxError` (`annot/grammar.go:145`), and `ScanAnnotations` returns it for the **whole scan** (`annot/source.go:54-60`). deps marks one file opaque instead. So multi-dollar is a **deliberate consumer-policy divergence**, not a defect.
- `` $`name` `` is modelled in all three (t1990 annot; t1999 `escapedEnd` in both deps lexers; `cache.go` `schemaVersion` 10).
- `ktok` carries `esc` (t1997). Plain-string content shares `ktok.text` with operator text, a consumer hazard fixed in five places by t2022.
- t1991 landed `annot/testdata/conformance/kotlin/` (31 byte-identical copies of the research corpus; its `.expect` reader is test-only in package `annot`).
- Reusable oracle harnesses exist verbatim in the archived plans:
  - t1990's `KtAdapter.java`: real `KotlinLexer` → annot line classes + certainty (`aiplans/archived/p1990_…md`, "Real-lexer differential");
  - t1999's `KtProbe.java`: real lexer → identifier/keyword sequence, and comment ranges blanked (`aiplans/archived/p1999_…md`, Final Implementation Notes).

  Both drive `org.jetbrains.kotlin.lexer.KotlinLexer` from `~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib/kotlin-{compiler-embeddable,stdlib}-2.3.20.jar`. That jar is durable on this host, unlike t1954's `ktpsi` classpath, which points into another session's scratchpad.

## Construct inventory (code reading at `555e28536`; Step 3 measures it)

Rule names: JetBrains/kotlin `compiler/psi/parser/src/org/jetbrains/kotlin/lexer/Kotlin.flex`, as cited by t1990's plan.

| construct | Kotlin.flex | annot | ktLex | kts blanker |
|---|---|---|---|---|
| `//` | EOL_COMMENT | modelled | modelled | modelled |
| `/* */`, nested | BLOCK_COMMENT (depth) | modelled | modelled | modelled |
| `/** */` | DOC_COMMENT | modelled (as block) | modelled | modelled |
| `#!` first line | SHEBANG_COMMENT | **not modelled** (line lexed as code) | **not modelled** | modelled (`shebang()`) |
| `"…"`, `\` escapes | STRING / ESCAPE_SEQUENCE | modelled | modelled | modelled |
| newline in `"…"` | DANGLING_NEWLINE | refuses | refuses | refuses |
| `\` + newline in `"…"` | (invalid) | refuses | **lenient**: skips the newline, line count off by one | **lenient** |
| `"""…"""`, no escapes, last three of a quote run close | RAW_STRING / THREE_OR_MORE_QUO | modelled | modelled | modelled |
| `${…}`: brace depth, nested strings and comments | LONG_TEMPLATE_ENTRY | modelled | modelled | modelled (bracket stack) |
| `$ident` | SHORT_TEMPLATE_ENTRY | text (moves no boundary) | tokens | text |
| `` $`name` `` | SHORT_TEMPLATE_ENTRY + ESCAPED_IDENTIFIER | modelled | modelled | modelled |
| `$`ʳ`"` / `$`ʳ`"""`, r ≥ 1 (incl. a single `$"`) | `{INTERPOLATION}?\"` (2.2) | **modelled** | **refuses** | **refuses** |
| `$`-run vs prefix n inside a string | LONG_TEMPLATE_ENTRY_START, LONELY_DOLLAR | modelled | n/a (refused earlier) | n/a |
| char literal | CHARACTER_LITERAL | modelled, ≤ 8 bytes; unclosed → stray quote, continues | modelled, ≤ 12 bytes; unclosed → refuses | read as a one-line `'…'` string; unclosed → refuses |
| backticked name in code | ESCAPED_IDENTIFIER | modelled; unclosed → continues | modelled; unclosed → refuses | modelled; unclosed → refuses |
| `\` outside literals | BAD_CHARACTER | ignored | `o:\` token | **refuses** |
| BOM | skipped by kotlinc | skipped (`SkipsBOM`) | skipped (not a letter) | identifier bytes |

Expected divergences on **valid** Kotlin: multi-dollar (deliberate), and the shebang. Every other difference is lenient-vs-refuse on **invalid** input. Step 3 confirms or refutes this.

## Consumer needs

| | annot | deps `ktLex` → `kotlin.go`/`frombody.go` | deps kts blanker → `gradle.go` |
|---|---|---|---|
| files it receives | every `.kt` and `.kts` (`annot/lang.go` `byExt`) | `.kt` and every `.kts` **except** `*.gradle.kts`, e.g. `.main.kts` scripts (`deps/raw.go:38-57` `kindOf`) | `*.gradle.kts` only |
| output | per-line class Code/Comment/Literal; `Package`/`Import` line; `Uncertain{Line, Construct}` | the whole token stream: `kind` `n`/`o`/`s`/`S`/`d`, `esc`, `text`, `line`. The consumers branch on operator kind+text (`.` `::` `?` `:` `(` `<` `>` `[` `@` `=` `-` `*`, brace depth), on plain-string content (`.localized` keys), and on look-ahead adjacency, so every token counts, numbers included. Template code is kept as tokens | source with comments blanked, offsets kept; `failAt` |
| cost of refusing | whole scan fails (above) → prefers modelling | one file opaque `untokenizable` | module `gradle-dynamic` (deps widened) |
| unsafe direction | a data line classed Comment (`Apply` writes into data) | code hidden (a missed dependency) | code blanked (a missed `project()` dep) |
| template policy | a line inside `${}` is Code, never an annotation line | template code yields references | template code is code |
| dialects | Kotlin only | Kotlin only | Groovy **and** Kotlin DSL in one `code()` |

Needs differ in **projection** (line classes / tokens / blanking) and in **refusal policy**, not in lexing. One span stream could serve all three. Each consumer would still choose its own refusal policy, as multi-dollar shows.

## Options (finalised in the decision record, Step 5)

1. **Shared core.** A new span lexer (≈ 250–300 lines, pure Go) under `internal/testmap/` emits code-token / comment / string / template spans with byte offsets. annot's `classifyKotlin`, `ktLex` and the kts branches of `gradleLexer.code`/`str`/`blockComment` become projections, with per-consumer refusal hooks for each lenient-vs-refuse row above.
   - The Groovy dialect stays a separate lexer. `gradlelex.go` loses only its kts branches, and its shared `code()` must be split.
   - Blast radius:
     - annot's Kotlin read/plan/apply path, gated by t1991's `TestConformance` (its `confKnown` pins must not move silently);
     - the deps Kotlin scanner and the Gradle KTS graph, with a `schemaVersion` bump (every cached Kotlin/kts blob is rescanned once);
     - every lexer test in both packages.
   - deps would gain modelled multi-dollar (no more opaque files), but real exposure today is nil (no `$$"` in the registered repositories; recounted in Step 1).
2. **Shared conformance fixtures.** One construct table pins, per construct, each lexer's outcome against the real `KotlinLexer`.
   - Test-only, in package `deps`, the only package that sees all three lexers: `deps` already imports `annot` (`bash.go:450`).
   - Blast radius: none at runtime. A future change to a tabled construct must update its row, which is the intent.
3. **Status quo + cross-lexer differential.** A walk asserts the three agree on every hermetic Kotlin fixture (71 today: annot conformance 31, parse 2, placement 5; deps opaque 33), with an exact known-divergence table.
   - Test-only. Blast radius: none at runtime. A new fixture under `annot/testdata` or `deps/testdata` is checked automatically.

Options 2 and 3 share one projection helper, so the plan lands both (a few hundred test lines). Option 1 is decided by the C1–C6 comparison below. Constraints: no new dependency (the `guards_test.go` allowlist stays `yaml.v3`, `doublestar/v4`, `x/sync`); the safeguard has no runtime cost. The 300 ms scan budget (`bench/baseline.txt`: annot `BenchmarkScan` 21 ms; deps warm 116 ms of 150 ms) does not discriminate: every option is linear.

## Decision criteria (pre-registered, before measuring)

No single measurement decides. Drift is **one input**: zero drift today does not show that three copies are cheaper to keep, and one drift instance does not show that a core is needed when a small local fix plus the shared tests suffices. Both outcomes stay available. The record weighs every criterion below, each measured as stated, and argues the decision from them:

| | criterion | how it is measured |
|---|---|---|
| C1 | **live drift** | Step 3/4: each construct where a lexer diverges from the real lexer in its own consumer's projection without refusing, on lexically valid Kotlin (no BAD_CHARACTER, DANGLING_NEWLINE or unclosed construct), on a file kind its consumer receives. Per instance: direction (safe / unsafe), whether another copy already models it, and the size of the local fix (lines) |
| C2 | **recurrence** | `git log` of the three lexers since `f096db065`: each construct that needed more than one copy fixed, the commits, and the lines changed per copy. Counterfactual: the `mid` snapshot (`cf210a9e9`: annot modelled `` $`name` ``, deps not yet) shows whether the construct table would have flagged the second copy the moment the first changed |
| C3 | **migration complexity** | the functions a core replaces and their line counts; the test cases that would be rewritten (counted per lexer); the `schemaVersion` bump; t1991 `confKnown` pins at risk; the split of gradlelex's shared `code()` |
| C4 | **recurring maintenance cost** | per future Kotlin lexical change: edits and tests touched under a core (1 lexer + projections) vs under the safeguard (3 lexers + 1 row), estimated from C2's measured diffs |
| C5 | **consumer policies** | the lenient-vs-refuse rows a core must parametrise per consumer (inventory: ≈ 6), and whether any consumer's policy blocks a shared reading (e.g. annot must model what deps may refuse) |
| C6 | **runtime blast radius** | the callers and paths each option changes (Options section), and the cache invalidation |

Fixed consequences, independent of the core decision:
- every C1 instance in the unsafe direction is an upstream defect, filed in Step 4 as a bug task (anchor 1852) with its local fix, so the table can cite its id;
- the safeguard (options 2 + 3) lands in this task either way. It is also the acceptance gate a later core would have to pass;
- if the record decides **for** a core, Step 5 creates one bounded implementation task (anchor 1852).

The multi-dollar row is weighed under C5: it is a deliberate policy difference, and exposure is counted in Step 1.

## Implementation

`S` = `/tmp/claude-1000/-home-ddt-Work-aitasks/<session>/scratchpad/t1992`. Nothing in the measurement writes to the live tree or to any registered repository.

### Step 0 — Rebase check
- Run `git log 555e28536..HEAD -- goengines/internal/testmap/annot/ goengines/internal/testmap/deps/`, plus `./.aitask-scripts/aitask_query_files.sh inbox 1992`.
- For each new commit or note, re-check the inventory rows it touches before measuring.

### Step 1 — Inputs
1. **Snapshots.** `git archive <c> goengines` keeps the `goengines/` prefix, so each module root is `$S/<name>/goengines`:

   | name | commit | why |
   |---|---|---|
   | `snap` | `HEAD` (after Step 0) | the lexers under evaluation |
   | `ctl` | `3d1a2b628` | the research pin, before t1990/t1997/t1999: the known annot multi-dollar desync and the deps `` $`name` `` gap |
   | `mid` | `cf210a9e9` | t1990 landed, t1999 not yet: annot models `` $`name` ``, deps does not (C2's counterfactual) |

   `mkdir -p $S/<name> && git archive <c> goengines | tar -x -C $S/<name>`. Record each commit and `git rev-parse <c>:goengines`.

   **The lexers under test are never edited.** Verify each snapshot's `annot/lexctx.go`, `deps/kotlinlex.go` and `deps/gradlelex.go` by comparing their sha256 with `git show <c>:<path> | sha256sum`.

   Verified API at both historical pins: `annot.Classify(annot.Kotlin, …)` and `blankGradleComments(src, kts) (string, int)` are unchanged. `ktok` has **no `esc` field** (it is `{kind, text, line}`), and that is the only difference the dump has to absorb (Step 2).
2. **Real repositories:** every project in `./ait projects list`. For each one:
   - resolve its path, `c=$(git -C <p> rev-parse HEAD)`;
   - `git -C <p> archive $c -- ':(glob)**/*.kt' ':(glob)**/*.kts' | tar -x -C $S/repos/<name>`: a commit snapshot, read-only, not the live tree (t1990's method);
   - record a table: name | commit | tree | `.kt` | `.kts` (of which `*.gradle.kts`) | files containing `$$"` | files whose first line is `#!` | files containing `\r`.
3. **Construct rows (group `C`).** Write one file per inventory row to `$S/constructs/<row>.kt`. Each holds the construct, look-alikes (`//`, `/*`, `"`) inside it, and a probe line after it. Add:
   - an **operator row** with `a?.b::c`, `@Ann(x)`, `R.string.k`, `fun <T> Box<T>.f()`, `x -> y`, `[i]`, `*`, `=`;
   - a **plain-string-content row** with `"."`, `"]"` and `">"` (the t2022 hazard);
   - a **numeric row** with `1.5f`, `0x1F`, `1..2`, `1e-5`;
   - a **shebang row**;
   - CRLF and BOM rows;
   - every invalid form in the inventory.

   Step 6 embeds these sources byte-identically.
4. **Groups:**
   - `H`: the 71 hermetic fixtures. They include the research corpus, byte-identical per t1991's `tests/test_annot_conformance_corpus_sync.sh`.
   - `R`: the real files.
   - `C`: the construct rows.
   - `M`: the mapper self-test mini-sources (Step 3, control e), written to `$S/mapper/<n>.kt`.
5. **Routing tag.** Each record carries the consumers its file reaches (consumer-needs table: `kindOf` and `byExt`). A divergence counts toward C1 only for a consumer that receives that file kind; the rest are reported but tagged "not routed".
6. **Exclusions** (counted, never dropped silently): non-UTF-8 files, and files with `\r` not followed by `\n`. These are compared cross-lexer only (P1, P2), without oracle columns. CRLF files are compared with the oracle on LF-normalised text, keyed by line and byte column.

### Step 2 — Dump (Go, inside each snapshot)
Two throwaway files go in `$S/<name>/goengines/internal/testmap/deps/`, package `deps`, so they reach `ktLex` and `blankGradleComments`; `annot.Classify` is exported:

- `zz_t1992_dump_test.go` is **byte-identical in every snapshot** (check with `cmp`). It runs only when `T1992_LIST` is set: lines of `group \t label \t abs-path`. It writes one TSV record per file to `T1992_OUT`:
  - base64(src);
  - **annot:** classes `c/#/L` + `Uncertain` line;
  - **ktLex:** err, plus the **whole** token stream, one `ktTok(k)` per token;
  - **kts:** base64(blanked) + `failAt`;
  - the P2 open vectors for all three (below).
- `zz_t1992_tok_test.go` is the **per-snapshot adapter**. It holds only `func ktTok(k ktok) string`, which renders `kind`, `text` (for `n`/`o`/`s`/`d`), `line` and the escape flag:
  - **snap:** `k.esc` → `` ` `` or empty;
  - **ctl/mid:** no `esc` field exists → `?` (escape unknown). The comparator then checks text, kind and line only, and reports "esc not compared" for that snapshot.

  The adapter reads only fields that exist at that commit, so it changes no lexer behaviour.

The P2 open vectors:

```go
// open: '.' when every string, comment and template is closed at the start
// of line i+1, 'o' otherwise. A prefix ending at a line start is accepted
// exactly when nothing is open there; for a file the lexer accepts whole, a
// refused prefix can only mean "open".
func openVector(src string, accepts func(string) bool) string {
	var b strings.Builder
	for at := 0; at < len(src); { // a final "\n" starts no line, as in annot.splitLines
		if accepts(src[:at]) {
			b.WriteByte('.')
		} else {
			b.WriteByte('o')
		}
		nl := strings.IndexByte(src[at:], '\n')
		if nl < 0 {
			break
		}
		at += nl + 1
	}
	return b.String()
}
```

Run it per snapshot: `cd $S/<name>/goengines && T1992_LIST=$S/list.tsv T1992_OUT=$S/dump_<name>.tsv go test ./internal/testmap/deps/ -run TestZZT1992Dump -count=1`. The list is the same for all three snapshots: every file is read from its absolute path, so the H/R/C bytes are identical across them.

### Step 3 — Oracle and comparison (Java, real KotlinLexer 2.3.20)
`$S/KtFamily.java` is assembled from t1990's `KtAdapter.adapt` (verbatim) and t1999's `KtProbe` (verbatim), plus three additions:
- a truth open vector (`start[i] != 'E'`) and validity flags;
- **a real-token → ktLex-vocabulary mapper**, so ktLex is compared on its whole stream, operators included:
  - a backticked IDENTIFIER → one `n`, backticks stripped, escaped;
  - string literal → its template-entry tokens in order, then `s:<concatenated REGULAR_STRING_PART>` when the string holds nothing else, else `S`, on the OPEN_QUOTE line;
  - CHARACTER_LITERAL → `S`;
  - comments and the shebang → nothing;
  - numeric literals → re-segmented by ktLex's documented digit rule (`kotlinlex.go` digit case), counting separately every literal ktLex splits into more than one token (e.g. `1e-5`). That class is reported, not hidden;
  - **every other token, keywords included**, → its text split the way ktLex splits code: maximal identifier runs → `n`, `::` → one `o`, each other punctuation byte → `o`. A keyword token is **not** assumed to be one word. The 2.3.20 lexer has compound keyword tokens (`NOT_IN` `!in`, `NOT_IS` `!is`, `AS_SAFE` `as?`), which ktLex reads as `o:! n:in`, `o:! n:is` and `n:as o:?`, so they are split like any other token text;
- the routing tag.

**Mapper self-test (control e, before any comparison is trusted).** `KtFamily.java` first runs a pinned table of mini-sources, each with an explicit expected ktLex-vocabulary sequence. Both the mapper's output from the real lexer **and** ktLex's own output (rows dumped in Step 2 as group `M`) must equal the pinned sequence:

| source | expected sequence |
|---|---|
| `a !in b` | `n:a o:! n:in n:b` |
| `a !is B` | `n:a o:! n:is n:B` |
| `a as? B` | `n:a n:as o:? n:B` |
| `a?.b ?: c!!` | `n:a o:? o:. n:b o:? o:: n:c o:! o:!` |
| `x::class.java` | `n:x o::: n:class o:. n:java` |
| `f { a -> b }` | `n:f o:{ n:a o:- o:> n:b o:}` |
| `0..<n` | `d:0 o:. o:. o:< n:n` |
| `@Ann(1) val v` | `o:@ n:Ann o:( d:1 o:) n:val n:v` |
| `return@forEach`, `this@Outer` | `n:return o:@ n:forEach`, `n:this o:@ n:Outer` |
| `` `in` `` | `` n:in` `` (escaped) |
| `1.5f 0x1F 1e-5` | `d:1.5f d:0x1F d:1e o:- d:5` (the last one counted as a split literal) |

Any row that fails is fixed in the mapper, and its pinned sequence stays in the record. A row where ktLex itself disagrees with the pinned sequence is a ktLex finding, attributed like any other.

For every record it reports MATCH/MISMATCH per projection, with the first divergent line and the per-group totals:

| projection | annot | ktLex | kts blanker |
|---|---|---|---|
| P1 refuses the file | `Uncertain` | err | `failAt ≥ 0` |
| P2 open vector (prefixes) | ✓ | ✓ | ✓ (also pairwise) |
| P3 consumer projection | line classes vs `KtAdapter` | **full token stream** (kind, text, line, esc) vs the mapped real stream | blanked vs real comment ranges blanked |

`L=$(ls -d ~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib); java -cp "$L/kotlin-compiler-embeddable-2.3.20.jar:$L/kotlin-stdlib-2.3.20.jar" $S/KtFamily.java $S/dump_<name>.tsv`

**Harness controls** (before any result is trusted):
- (a) `dump_ctl.tsv` must reproduce the known pre-fix divergences: annot P3 MISMATCH on `multidollar_comment_desync.kt.in` line 9, and ktLex/kts MISMATCH on the `` $`name` `` row of `C`. `dump_mid.tsv` must show annot MATCH and ktLex/kts MISMATCH on that row (C2);
- (b) a record whose annot classes are flipped by hand must MISMATCH;
- (c) the oracle must agree with every current `TestClassifyKotlin` row. Dump them with t1990's `zz_lexdump_test.go` method (parse `lexctx_test.go` with go/parser) in `$S/snap/goengines/internal/testmap/annot/`; t1990 measured 20/20;
- (d) **operator control:** a fourth copy `$S/opneg/goengines` (`snap` + `ktLex`'s `::` branch patched to emit two `:` tokens). This is the only snapshot whose lexer is deliberately edited; its patch is recorded verbatim. The mutated branch fires only on a **code-level** `::`; one inside a string, comment or template text never reaches it. The expectations are therefore derived from the **baseline** (`snap`) dump and comparator verdicts, not from a text search:
  - **every record:** each non-ktLex-token field (annot, kts, P1, P2, `err`) is byte-identical to baseline. The ktLex token stream equals the baseline stream with each `o:::` token replaced by two `o::` tokens, exactly;
  - **eligible records:** baseline ktLex accepts the file, its baseline ktLex P3 verdict is MATCH, and its baseline stream holds ≥ 1 `o:::`. Each must now report ktLex P3 MISMATCH at the first `::` line. The eligible count is reported and must be ≥ 1, and the `C` operator row must be among them;
  - **every other record** keeps its baseline comparator verdicts unchanged.

  This shows the operator projection is load-bearing, without blanket expectations on files the mutation cannot reach.

If any control fails, fix the harness; never filter rows.

### Step 4 — Attribute
- Attribute every MISMATCH to an inventory row (adding a row when none fits) by reading its first divergent line.
- For other repositories' files, record path:line and the construct name only, never contents.
- Classify each one:
  - valid or invalid Kotlin;
  - routed or not routed;
  - safe direction (refusal, over-read) or unsafe direction (per the consumer-needs table);
  - local-fix size.
- Unsafe C1 instances: create one bug task per defect now, with `./.aitask-scripts/aitask_create.sh --batch --anchor 1852 --type bug --followup-kind upstream_defect …`. Record them under "Upstream defects identified" too, so Step 8b does not create them twice.

### Step 5 — Decision record
Append `## Decision record` to this plan:
- the inputs (snapshot commits, oracle version, groups and counts, exclusions);
- the measured divergence tables (P1/P2/P3 × group × lexer) and the attributed construct list: "every construct where they disagree", with the number-segmentation and "not routed" classes reported separately;
- **the coverage boundary**: what the projections measure, and what they do not. For example, ktLex's `S` content is not compared, and annot's projection is line-level;
- C1–C6 measured, and the argued decision;
- the final complexity and blast radius of each option.

If the record decides for a core, create the bounded implementation task (anchor 1852). Its description holds option 1's scope, the per-consumer refusal policies, the gates (`TestConformance`, the new family tests, `schemaVersion` bump) and the C1–C6 evidence.

### Step 6 — Safeguard: `goengines/internal/testmap/deps/kotlinfamily_test.go` (new)
1. **Shared helpers:**
   - `familyLexers` (`annot` / `ktLex` / `kts`, each an `accepts func(string) bool`);
   - `openVector` (Step 2);
   - per-lexer projections:
     - annot: `annot.Classify` classes;
     - ktLex: the full token stream, rendered as in Step 2's `ktTok`: kind, text, line, `esc`;
     - kts: the blanked output.
2. **`TestKotlinFamilyConstructs`** runs a table of rows `{name, rule, src, truth, classes, tokens, blanked, want map[lexer]outcome}`:
   - `truth`, `classes`, `tokens` and `blanked` are the real lexer's projections, pinned from Step 6.3; `truth == ""` means the real lexer rejects `src`;
   - `outcome` is one of:
     - `modelled`: accepts, open == truth, and the lexer's projection == the pinned real projection;
     - `refuses`;
     - `differs(<got>, <reason>)`: the exact pinned value, with a reason such as "invalid Kotlin, read leniently" or "shebang not modelled; refuses";
   - rows: the `$S/constructs/` sources from Step 1.3, embedded byte-identically, so the operator, plain-string-content, numeric, shebang, CRLF, BOM and invalid-form rows are all present;
   - failure message: `"<row>: <lexer> <got>, want <want> — a Kotlin-family lexer changed how it reads <rule>; model it in all three lexers or pin the divergence here (t1992)"`.
3. **Pin the truths** from Step 3's `C`-group run. Confirm the embedding: a throwaway `zz` dump of the new test's rows, in `$S/snap/goengines`, must be byte-identical (`cmp`) to `$S/constructs/`. Record the output verbatim.
4. **`TestKotlinFamilyCorpus`:**
   - walk `testdata/` and `../annot/testdata/` for `*.kt.in` / `*.kts.in`, failing if fewer than 71 (no vacuous pass);
   - per file, all three must agree on P1, and on P2 when none refuses;
   - each disagreement must match `kotlinFamilyCorpusKnown[path]` exactly (expected: the four `conformance/kotlin/multidollar_*` fixtures; final list from Step 3);
   - a known entry that no longer occurs fails as stale.
5. **Pointer comments** (one sentence each, no behaviour change):
   - `ktLex`'s doc in `kotlinlex.go`;
   - `blankGradleComments`'s doc in `gradlelex.go`;
   - the `kframe`/`classifyKotlin` comment in `annot/lexctx.go`;
   - each says: "`deps/kotlinfamily_test.go` pins this lexer's reading of each Kotlin construct against the other two Kotlin-family lexers; a construct change here needs its row there."

   No extraction rule changes, so no `schemaVersion` bump; `TestClassifyFingerprint` (bash-only, behaviour-hashed) is unaffected.

### Step 7 — Negative controls (on an isolated scratch copy, never the live tree)
In `$S/neg/goengines` (`git archive HEAD goengines` + the new test), one mutation at a time, restoring from the archive between them:
- (a) make `kotlinDollars` never open a template → `TestKotlinFamilyConstructs` fails on the multi-dollar rows;
- (b) make `ktLexer.blockComment` non-nesting → it fails on the nested-comment row, and `TestKotlinFamilyCorpus` names a divergent file;
- (c) make `ktLex` emit `::` as two `:` tokens → it fails, in the ktLex token projection only, on exactly the rows whose pinned ktLex tokens hold a code-level `o:::` (the operator row among them), and every other row passes. File acceptance and the open vector are unchanged, so this proves the token projection, not P1/P2, catches it;
- (d) delete one `kotlinFamilyCorpusKnown` entry → it fails naming that file;
- (e) add a bogus entry → it fails as stale.

Record the commands and the output verbatim.

## Verification
- `cd goengines && gofmt -l internal/testmap/ && go vet ./... && go test ./...` (CI `goengines-check.yml` runs `go test ./...`).
- `go.mod` and `guards_test.go` unchanged; `git diff --stat` shows only `deps/kotlinfamily_test.go` (new) and three comment hunks.
- Step 3's harness controls and Step 7's negative controls are recorded.
- **Durable evidence:** the zz dump test, `KtFamily.java`, every command and every output go verbatim into Final Implementation Notes, with sha256 sums. The scratch copies are evidence only.

## Risk

### Code-health risk: low
- The corpus differential checks every future Kotlin fixture automatically, so an unrelated task adding a fixture can hit it · severity: low · → mitigation: none (in-plan: the Step 6.2/6.4 failure messages name the table and the rule)
- Three comment-only edits to production lexers · severity: low · → mitigation: none (no behaviour change; `go test ./...` and the fingerprint test confirm)

### Goal-achievement risk: low
- The oracle adapters (t1990/t1999) might misread real files: CRLF, BOM, templates spanning lines · severity: low · → mitigation: none (in-plan: Step 3 controls a–c, including the historical `3d1a2b628` reproduction)
- The durable corpus differential sees file acceptance and line-start state (P1/P2) only. Mid-line and operator-level drift there is caught only by the construct rows' consumer projections (P3: full ktLex token stream, kts blanking, annot classes) · severity: low · → mitigation: none (coverage boundary recorded in the decision record; the construct rows pin P3; Step 7c proves an operator regression is caught)
- The real-token → ktLex-vocabulary mapper normalises numeric-literal segmentation, which could hide a divergence · severity: low · → mitigation: none (in-plan: every literal the rule splits is counted and reported as its own class, Step 3)
- A mapper error (e.g. compound keywords `!in` / `!is` / `as?`) would create false P3 mismatches and feed false C1 defects · severity: low · → mitigation: none (in-plan: Step 3 control e pins the mapper against explicit sequences, on both the real-lexer and ktLex sides, before any comparison is trusted)
- A decision that weighs six criteria is open to argument · severity: low · → mitigation: none (in-plan: criteria pre-registered with their measurements; the record argues from them, and both outcomes stay available)
- Real-repository inputs are a moment-relative sample · severity: low · → mitigation: none (commits recorded; rebuildable with `git archive`)

No mitigation candidates: each residual risk is already handled by a step of this plan (`risk_mitigations_planned = false`).

## Step 9 reference
Current-branch mode: commit the test and comment changes (`chore: … (t1992)`), and the plan with its decision record via `aitask_task_commit.sh`. No merge step, then archival per the workflow's Step 9.

## Decision record (t1992)

### Inputs

| snapshot | commit | `goengines` tree | role |
|---|---|---|---|
| `snap` | `2874e66eaffd13534f56ccd0f2531ed74cc0d450` | `a6022cea236074d828b79e3e7b7044f1076aa2b1` | the lexers under evaluation (HEAD at measurement) |
| `ctl` | `3d1a2b628fc07f75b279c0c125ed4705316c9368` | `2c26f17fe33a425b88af7ac7e20d731e3499ace9` | research pin, before t1990/t1997/t1999 |
| `mid` | `cf210a9e9b70395a794e1597903c34a2937711b1` | `418bed39e507ba55ef7191e9cae565c93151e65b` | t1990 landed, t1999 not yet |
| `opneg` | `snap` + `opneg.patch` | — | control d only: `ktLex` emits `::` as two `:` |

- **Lexers unedited.** Each snapshot's three lexer files were checked against `git show <c>:<path>` (sha256, first 16 hex):
  - `snap`: lexctx `5e629c70e118fb7e`, kotlinlex `6aeedf4de9cd763d`, gradlelex `0c33f303b53af4e3`;
  - `ctl`: `f0d0a4eb26709029` / `59e4ce7d43c67e10` / `639152b4d77a02c5`;
  - `mid`: `5e629c70e118fb7e` / `59e4ce7d43c67e10` / `639152b4d77a02c5`. That is snap's annot with ctl's deps lexers: exactly the counterfactual.
- The live HEAD advanced to `1f3b3ca75` before the commit, with no change under `goengines/` (`git log 2874e66ea..HEAD -- goengines/` is empty).
- **Oracle:** `org.jetbrains.kotlin.lexer.KotlinLexer` from `kotlin-compiler-embeddable-2.3.20.jar` (Gradle 9.5.1 distribution), OpenJDK 21.0.2. Go 1.27.0.
- **Groups:**
  - `H`: 71 hermetic fixtures (goengines testdata at `snap`);
  - `R`: 2051 real files;
  - `C`: 40 construct rows;
  - `M`: 12 mapper self-test rows.

  Exclusions: 0 non-UTF-8 files, 0 files with a lone CR. CRLF: 2 files (`H` `crlf.kt.in`, `C` `crlf`), compared with the oracle on LF-normalised text.
- **Real repositories** (commit snapshots via `git archive` of the `ls-tree` list; read-only):

| repository | commit | tree | .kt | .kts | of which *.gradle.kts | `$$"` | `#!` first line | `\r` |
|---|---|---|---|---|---|---|---|---|
| aitasks_go | `e0e3862be98a0fc2d8d977f4dfa42db20104660f` | `b31e28d45fe14f8913c10de783fa8be55a387844` | 0 | 0 | 0 | 0 | 0 | 0 |
| timexchange | `c60e7e05a46550034197b0051ae851eb193a1764` | `a445b0527fe5a22ab2fb866154c7ff5c97f3d2e8` | 957 | 13 | 13 | 0 | 0 | 0 |
| teamim | `18a4679d1c108eee54063c3b40a6867c55168760` | `9146c76eb9ff1eb75df41ef89217732ab3dd75e2` | 37 | 0 | 0 | 0 | 0 | 0 |
| thinking_app | `c9f197f46ca59dd8ada8cf73df93ceaa819f73de` | `10cd0177043bc5b7e3fd58890978a7fffda43693` | 784 | 0 | 0 | 0 | 0 | 0 |
| thinking_backend | `cd40e0933dee7701df77a7797c75f36f586f3e52` | `8bb6c4ba524f6c9902a2cc9e762f4eee7e43888d` | 0 | 0 | 0 | 0 | 0 | 0 |
| aitasks | `2874e66eaffd13534f56ccd0f2531ed74cc0d450` | `07e600a583a2e78b14efb0e971b0d1155a1312c5` | 0 | 0 | 0 | 0 | 0 | 0 |
| aitasks_mobile | `75f4543fb70e90baa8661404505017887d3602c1` | `e07c7fec041e2146975f57045614b26223bcafed` | 252 | 8 | 8 | 0 | 0 | 0 |
| animeless | `75365c1fec1e9cd7fb27d6d5a8ce983173298d02` | `6e45a6a15b89840256b00646fa996566cc616b5c` | 0 | 0 | 0 | 0 | 0 | 0 |

Every real `.kts` is a `*.gradle.kts`, so `ktLex` receives no `.kts` from these repositories in production.

### Measured divergence at HEAD (`snap`)

"compared" counts the files the lexer accepts and the real lexer reads as valid. P2/P3 are counted over those.

| group | lexer | files | refuses | P1 refuses valid | P1 accepts invalid | P2 mismatch | P3 mismatch |
|---|---|---|---|---|---|---|---|
| R (2051 valid) | annot | 2051 | 0 | 0 | 0 | 0 | 0 |
| R | ktLex | 2051 | 0 | 0 | 0 | 0 | 0 |
| R | kts | 2051 | 0 | 0 | 0 | 0 | 0 |
| H (67 valid, 4 invalid) | annot | 71 | 4 | 0 | 0 | 0 | 0 |
| H | ktLex | 71 | 8 | 4 | 0 | 0 | 1 |
| H | kts | 71 | 8 | 4 | 0 | 0 | 0 |
| C (32 valid, 8 invalid) | annot | 40 | 6 | 1 | 3 | 0 | 1 |
| C | ktLex | 40 | 11 | 5 | 2 | 0 | 4 |
| C | kts | 40 | 11 | 4 | 1 | 0 | 0 |
| M (12 valid) | all three | 12 | 0 | 0 | 0 | 0 | 0 |

- Pairwise P2 between lexers that both accept a file: **0 differences** in every group.
- The 4 `H` refusals by kts are `.kt` files, so kts never receives them ("not routed").
- Numeric-literal segmentation class: 9 literals. 6 are in `R`:
  - `aitasks_mobile/…/monitor/ZoomGestureDecideTest.kt` lines 60, 67, 74, 81, 108;
  - `thinking_app/…/testing/TypeScalePolicyTest.kt:605`.

  The other three are `C` `numbers` ×2 and `M` `numbers` ×1.

### Every construct where they disagree

| construct | where | annot | ktLex | kts | real lexer | effect for the consumer | exposure in R |
|---|---|---|---|---|---|---|---|
| Kotlin 2.2 interpolation prefix (`$`ʳ`"`, `$`ʳ`"""`, a single `$"` included) | H `multidollar_*` ×4; C `multidollar_*` ×3, `single_dollar_prefix` | models | refuses | refuses | valid | deliberate: deps makes the file opaque / widens the module; annot cannot refuse (a whole-scan `SyntaxError`) | 0 |
| shebang | C `shebang_plain`, H `script.kts.in`: ktLex P3 (the line is read as `o:# o:! o:/ n:usr …`). C `shebang_brace`: ktLex P3 and annot P3 (anchors `package=0`, real 2). C `shebang_paren`: ktLex P3. C `shebang_slash_star`: annot and ktLex refuse | not modelled. A `{` in the line hides `package`/`import` from the anchors, so placement lands after the shebang (valid, misplaced); a `/*` makes the file Uncertain (a whole-scan `SyntaxError` when it carries `testmap:`) | not modelled. **A `{` in the line hides the package clause and every declaration from `scanKotlin`, a `(` hides every declaration, with no error and no opaque reason**; a `/*` → refusal | models | valid | **unsafe for deps**: silently missed dependencies (reproduced: `Package=""`, `Decls=[]`, `Opaque=[]`); annot: misplaced anchor or refusal. Filed as **t2030** | 0 shebang files |
| CRLF raw-string content | C `crlf` | line classes match | the `s` content keeps `\r` | match (`\r` bytes not compared) | valid: kotlinc normalises line separators | `s` content feeds only `.localized` keys (`kotlin.go:111`); a multi-line raw string key does not occur | 0 CR files |
| numeric literal segmentation | 9 literals (above) | — | `1e-5` → `d:1e o:- d:5`; `.5` → `o:. d:5` | — | valid | no consumer reads a `d` token; the only `-` look-behind (`kotlin.go:411`, `->`) is unaffected | 6 literals |
| `\` outside literals | C `invalid_backslash_in_code` | accepts | accepts (`o:\`) | refuses | invalid | — | — |
| `\` + newline in `"…"` | C `invalid_backslash_newline_in_string` | refuses | accepts | accepts | invalid | — | — |
| unclosed backtick | C `invalid_unclosed_backtick` | accepts | refuses | refuses | invalid | — | — |
| malformed char literal `'ab` | C `invalid_unclosed_char` | accepts | refuses | refuses | invalid (the lexer emits one CHARACTER_LITERAL token; the compiler rejects it) | — | — |
| unterminated string / raw / block / template | C `invalid_unterminated_*` | refuses | refuses | refuses | invalid | — | — |

Every other construct row — 23 of the 32 valid rows — is modelled by all three in every projection. That includes nested and doc comments, escapes, nested templates, templates spanning lines, a comment in a template, `$ident`, both `` $`name` `` forms, lonely dollars, raw-string look-alikes, `"""C:\"""`, quote runs, char literals, backticked names, BOM, the operator row and the operator-looking string contents.

The planned inventory is confirmed, with two additions: CRLF raw-string content and numeric segmentation. The shebang rows confirm "not modelled" for annot and ktLex, and the planned inventory understated the effect (corrected under C1).

### Coverage boundary

- **annot:** acceptance, the line-start view, the line classes, and the `Package`/`Import` anchors placement reads. The anchor oracle is the first `package` / last `import` that starts a top-level line at brace depth 0. Nothing mid-line (its consumer reads lines).
- **ktLex:** acceptance, the line-start view, and the whole token stream (kind, text, line, `esc`). Not the content of `S` tokens (ktLex records none). Numeric literals are compared after ktLex's digit rule; that class is reported separately.
- **kts:** acceptance, the line-start view, and the blanked bytes, except `\r` bytes.
- **Validity:** the real lexer reports no BAD_CHARACTER, DANGLING_NEWLINE, unclosed construct or malformed char literal. Parser-level errors are not checked.
- **Consumer effects beyond the projections** (e.g. `scanKotlin`'s brace and paren gates on declarations) are not measured systematically. The shebang effects were traced by hand after the plan review.
- **Durable test:** the construct rows pin P1/P2/P3 for all three lexers. The corpus differential pins P1/P2 only. None of the 71 hermetic fixtures holds a code-level `::` (control d found no `H` record eligible), so operator drift is caught hermetically by the operator row alone.

### Controls

- **(a)** `ctl` reproduces:
  - the annot multi-dollar desync: `multidollar_comment_desync` P3 `cc#ccLcL#cLL` vs real `cc#cc#ccLLc#`. The write-probe line 9 is classed `#` where the real lexer has `L`; the first difference is at line 6. The line classes of `multidollar_literal_brace` and `multidollar_quote_boundary` differ too, from line 4;
  - both deps `` $`name` `` defects: the plain form is refused, and the raw form is silently misread (`s@1:$`c//d`` vs real `n@1:c//d S@1:`).

  `mid`: annot models both forms, while deps refuses one and misreads the other. That is C2's counterfactual.
- **(b)** a hand-flipped annot class string MISMATCHes.
- **(c)** `TestClassifyKotlin`: 20/20 MATCH. This uses t1990's `KtAdapter.java` and `zz_lexdump_test.go`; their sha256 sums equal t1990's record (`2839bdae…` for the dump test).
- **(d)** `opneg`: 2174 records. 570 are eligible (C 1, M 1, R 568) and all 570 are detected at their first `::` line, with 0 failures; the operator row is eligible.
- **(e)** the mapper self-test is 12/12 at HEAD, on both sides. At `ctl`/`mid` it is 11/12; the miss is `escaped_keyword`, where ktLex had no `esc` field ("esc not compared", as planned).

### C1–C6

- **C1 live drift.**
  - One construct drifts, and **in the unsafe direction**: the **shebang**. The kts blanker models it; ktLex and annot do not. It is routed: `ktLex` receives every `.kt` and every non-Gradle `.kts` (e.g. `*.main.kts` scripts, the files that carry shebangs).
    - ktLex: a `{` in the shebang hides the package clause and every declaration from `scanKotlin`, and a `(` hides every declaration, silently, with no error and no opaque reason. A `/*` → refusal; a plain shebang → stray tokens.
    - annot: a `{` hides the `package`/`import` anchors, so placement lands after the shebang (valid, misplaced); a `/*` → a whole-scan `SyntaxError`.
    - Exposure is zero (no shebang file in R). Local fix: about 6 lines in ktLex (skip one leading `#!` line, as `gradleLexer.shebang` does) and a few in annot. Filed as **t2030** (anchor 1852, upstream_defect).
  - **Correction:** the first draft of this record called the shebang "safe direction (extra tokens before `package`)". That was asserted without tracing the tokens through `scanKotlin`. The plan review reproduced `#!/usr/bin/env -S kotlin -J-Dtag={` hiding the package and the declarations. The `shebang_brace` and `shebang_paren` rows were then added, and annot's anchors were added to its projection, which exposed annot's anchor loss.
  - ktLex also keeps `\r` in CRLF raw-string content. It is harmless, with zero exposure; the fix is one line, and it is offered at Step 8b.
  - No other drift: 2051 real files agree in every projection, the anchors included.
- **C2 recurrence.** The three lexers had 8 commits since `f096db065`, and two constructs needed more than one copy fixed:
  - the interpolation prefix: gradlelex at its creation (t1975), ktLex +17/−2 (t1980), annot +59/−15 (t1990);
  - `` $`name` ``: annot within t1990's +59/−15, then ktLex +27/−7 and gradlelex +22/−7 (t1999).

  The second construct surfaced only because t1990 probed deps. The `mid` counterfactual shows a construct row would have failed for both deps lexers the moment annot's row changed.
- **C3 migration complexity (core).** The core would:
  - replace annot's Kotlin classifier (`classifyKotlin` 146, `kotlinDollars` 18, `skipKotlinChar` 11 lines), all of `kotlinlex.go` (285 lines), and the 15 kts-conditional branches of `gradlelex.go`, whose shared `code()` would have to be split from the Groovy dialect;
  - re-pin the 20 `TestClassifyKotlin` rows, `kotlinlex_test.go` (4 test functions) and the 10 kts `gradleLexCases`;
  - keep the 31 Kotlin conformance fixtures green. They have 0 `confKnown` pins, so any behaviour change on them is a test change;
  - bump `schemaVersion` 10 → 11.
- **C4 recurring cost.** Per new lexical construct, a core takes 1 edit; the safeguard takes 3 edits plus 1 row. The measured edits were 17–59 added lines per copy, about 125 added lines across copies for both constructs. Only one of the two was a language change (the Kotlin 2.2 interpolation prefix); `` $`name` `` was a latent gap.
- **C5 consumer policies.** A core must still carry per-consumer refusal policies for 5 rows: 4 invalid-input lenient-vs-refuse rows, plus the interpolation prefix, which annot must model and deps may refuse. It would remove the duplicated lexing, not these policy differences.
- **C6 runtime blast radius.**
  - core: annot's read/plan/apply path for every `.kt`/`.kts`, the deps Kotlin graph, the Gradle KTS graph, and the invalidation of every cached Kotlin/kts raw fact;
  - safeguard: none, because it is test-only.

### Decision

**No shared lexical core now** — a closer call than the first draft of this record claimed.

- **C1/C2 — the case for a core is stronger than it first looked.**
  - Three constructs are now on record where the copies drifted: the interpolation prefix, `` $`name` ``, and the shebang.
  - The shebang drift is unsafe for deps, and it had gone unnoticed since `ktLex` was written. The kts blanker already modelled it, so this is exactly the drift a core removes.
  - Copies do drift silently in constructs no test exercises.
- **Why the decision still holds.** Each drift is a local fix of a few lines (t2030 for the shebang). The construct table found all three at its first run: the shebang directly, and the other two through the historical replays. It now pins each one, so it fails the moment one copy changes, instead of relying on chance.
- **C3/C6.** A core still means about 470 rewritten lines across annot's write path and both deps graphs, a split gradlelex `code()`, and a cache invalidation. C4's benefit is about 2 extra small edits per construct.
- **C5.** A core would still carry five per-consumer refusal policies as hooks.

**Revisit (tightened)** when any further unsafe-direction drift turns up (from the table, a review or a target repository), when a drift with nonzero exposure appears, or when a Kotlin release adds lexical syntax that needs all three copies changed. Every script and command is in the evidence below, so the measurement reruns.

**Consequences:**
- Landed: `deps/kotlinfamily_test.go` (40 construct rows, plus a corpus differential over 71 fixtures with 4 pins) and three one-sentence pointer comments.
- Created: **t2030** `kotlin_shebang_line_hides_deps` (bug, anchor 1852, upstream_defect), for the unsafe C1 instance (Step 4). Its fix flips the four `shebang_*` rows to `modelled`.
- Not created: no core implementation task.
- Offered at Step 8b (safe direction): CRLF raw-string content in ktLex.

## Implementation Evidence

Run in `$S` = this session's scratchpad `t1992/`. Each block below is the exact file that ran; the sha256 is checked against the block's bytes.

**Commands:**

````sh
python3 mkrows.py                                   # C and M rows
# list.tsv: group \t label \t abs-path (H from snap's testdata, R, C, M)
for n in snap ctl mid opneg; do
  (cd $S/$n/goengines && T1992_LIST=$S/list.tsv T1992_OUT=$S/dump_$n.tsv \
     go test ./internal/testmap/deps/ -run TestZZT1992Dump -count=1)
done            # zz_t1992_dump_test.go identical in all; zz_t1992_tok_test.go = the snap or hist adapter
L=$(ls -d ~/.gradle/wrapper/dists/gradle-9.5.1-bin/*/gradle-9.5.1/lib)
CP="$L/kotlin-compiler-embeddable-2.3.20.jar:$L/kotlin-stdlib-2.3.20.jar"
java -cp "$CP" KtFamily.java dump_snap.tsv --mapper mapper_expect.tsv --truth-out truth_C.tsv > result_snap.txt
for n in ctl mid opneg; do java -cp "$CP" KtFamily.java dump_$n.tsv --mapper mapper_expect.tsv > result_$n.txt; done
python3 check_opneg.py $S                           # control d
(cd $S/snap/goengines && T1990_DUMP=$S/rows_classify.tsv go test ./internal/testmap/annot/ -run TestZZDumpKotlinRows -count=1)
java -cp "$CP" KtAdapter.java rows_classify.tsv     # control c (t1990's harness, verbatim)
python3 gentable.py $S table.go.txt                 # the construct table of kotlinfamily_test.go
bash negctl.sh                                      # Step 7 negative controls
````

**Deviations from the plan, recorded:**
1. **Oracle CR handling.** The first run kept `\r` in the oracle text. The raw `KotlinLexer` reads `\r` as BAD_CHARACTER, so the oracle now LF-normalises CRLF, as the plan's Step 1.6 said.
2. **Char-literal validity.** The lexer emits a malformed char literal as one CHARACTER_LITERAL token, so validity also checks the literal's shape.
3. **Split row.** `short_template_backticked` was split into a plain and a raw row. In the combined row, the plain form's refusal masked the raw form's silent misread at `ctl`/`mid`.
4. **Control 7a mutation.** Instead of "`kotlinDollars` never opens a template", which breaks every `${…}` row, the mutation forces annot's interpolation prefix to 1 (the pre-t1990 defect).
5. **Empty-source guard.** `adapt()` sizes `starts` with `max(lines, 1)`, so that empty input cannot index an empty array.
6. **Review finding (Step 8).** The shebang's safety was mis-assessed. In response:
   - the rows `shebang_brace` and `shebang_paren` were added;
   - annot's `Package`/`Import` anchors were added to its projection (dump fields 13–14, `KtFamily.anchors()`);
   - t2030 was filed;
   - every dump, oracle run, control and the table were regenerated (the sources and outputs below are the final ones).

**Reused verbatim from t1990's archived plan, not repeated here:** `KtAdapter.java` (sha256 `3cc23e50453ac82bdb11ca2a0686ec218aac8cc5e852e53ab43f9c0937a8cc04`) and `zz_lexdump_test.go` (sha256 `2839bdaed4da3362e611ca91241e128ef6c200f4cb4f0b1ecec2df9c2faaeffa`, the same value t1990 recorded).

**Inputs and dumps** (sha256; reproducible from the scripts and the recorded commits):

- `list.tsv` `c46bd517f6e87a20c8646bf6bc8acd1a43682056dc51e2f67d0c6347adbcd87c`
- `mapper_expect.tsv` `1b1845f6d611a4740cd8d9bbddcc27bc040c3d9e77aa93df60d00f47ea190805`
- `truth_C.tsv` `61e6016f05062f7b99fef79dd65d50f1e31d4d9360567a08629895989f5a8949`
- `dump_snap.tsv` `4ac7f870f1c22f5fbfde1cb7bf4aae28752ac6b19f51002551aba98806914cde`
- `dump_ctl.tsv` `dff2a490dcd7fa2af8b3eb1cc28eb1aa0df1e26e3e030c3e4aa530e4502a49d8`
- `dump_mid.tsv` `51409fce1832cea62bffc255e5b217ae0c9b235eba770804b4c57865f393357b`
- `dump_opneg.tsv` `d59eff67f8c4a46b6a8a736534c99c043f15226f11c06b6624d7136b98bbf624`
- `deps/kotlinfamily_test.go` (committed) `56c3c7d109cbbe3778fe195667da7f0968cc6136f84ec46dec547c097f870470`: byte-identical to the generated file

### Sources

`mkrows.py` (sha256 `ff49b404d3168c2299ce909bdc869a9350683900b15b9ef2a12e47868cec0dff`):

````python
#!/usr/bin/env python3
# mkrows.py (t1992): writes the construct rows (group C) and the mapper
# self-test rows (group M) as exact bytes. Each C row holds one Kotlin-family
# construct with look-alikes inside it and a probe line after it.
import os
import sys

S = os.path.dirname(os.path.abspath(__file__))

PROBE = "// probe: a real comment\nval probe = 1\n"

C = {
    # --- comments
    "line_comment": "val a = 1 // it's \"x\" /* not a block\n" + PROBE,
    "block_comment": "/* a // b \"c\n   still 'd' comment */\n" + PROBE,
    "nested_block_comment": "/* a /* b */\n// inside: still a comment\n*/\n" + PROBE,
    "doc_comment": "/** KDoc \"quote\" // slashes\n * nested /* c */ block\n */\n" + PROBE,
    "shebang_plain": "#!/usr/bin/env kotlin\n" + PROBE,
    "shebang_slash_star": "#!/usr/bin/env -S kotlin -cp lib/*\n" + PROBE,
    "shebang_brace": "#!/usr/bin/env -S kotlin -J-Dtag={\npackage p\nclass Actual\n" + PROBE,
    "shebang_paren": "#!/usr/bin/env -S kotlin -J-Dtag=(\npackage p\nclass Actual\n" + PROBE,
    # --- plain strings and templates
    "plain_string_escapes": "val s = \"a\\\"// not a comment\\\\\" + \"/*\"\n" + PROBE,
    "string_template_nested": "val s = \"${f(\"}\")} and ${ m[\"k\"] }\"\n" + PROBE,
    "template_lambda_braces": "val s = \"${ xs.map { \"}\" }.size }\"\n" + PROBE,
    "template_comment": "val s = \"${ /* \"*/ 1 }\"\n" + PROBE,
    "template_multiline": "val s = \"${\n    f(1) // a comment inside the template\n}\"\n" + PROBE,
    "short_template_ident": "val s = \"$name.$this and $x\"\n" + PROBE,
    "short_template_backticked": "val s = \"$`a\"b`\"\n" + PROBE,
    "short_template_backticked_raw": "val r = \"\"\"$`c//d`\"\"\"\n" + PROBE,
    "lonely_dollar": "val s = \"$\" + \"a$ b\" + \"$$\" + \"\"\"$\"\"\"\n" + PROBE,
    # --- raw strings
    "raw_string_lookalikes": "val r = \"\"\"\n// not a comment\n/* not a block\n\" \"\" \\\n\"\"\"\n" + PROBE,
    "raw_string_backslash_end": "val p = \"\"\"C:\\\"\"\"\n" + PROBE,
    "raw_string_quote_run": "val q = \"\"\"a \"b\" \"\"\"\"\nval q2 = \"\"\"\"\"x\"\"\"\"\"\n" + PROBE,
    "raw_template_nested_raw": "val r = \"\"\"${\"\"\"x\"\"\"} ${ \"y\" }\"\"\"\n" + PROBE,
    # --- char literals and backticked names
    "char_literals": "val c = listOf('\"', '\\'', '\\\\', '\\u0041', '/', '`', '$')\n" + PROBE,
    "backticked_names": "val `it's // here` = 1\nfun `has \"quotes\"`() = `it's // here`\n" + PROBE,
    # --- Kotlin 2.2 interpolation prefixes
    "multidollar_raw_desync": "val s = $$\"\"\"${/*\"\"\"\n// */\nval t = \"\"\"\n// look-alike inside raw\n\"\"\"\n" + PROBE,
    "multidollar_plain": "val j = $$\"{x} $${y} ${'$'}z\"\n" + PROBE,
    "multidollar_in_template": "val s = \"${ $$\"x\" }\"\n" + PROBE,
    "single_dollar_prefix": "val s = $\"a\"\n" + PROBE,
    # --- encodings
    "bom_comment": "\ufeff// first line comment after a BOM\n" + PROBE,
    "crlf": "val r = \"\"\"\r\n// in raw\r\n\"\"\"\r\n// probe: a real comment\r\nval probe = r\r\n",
    # --- token-stream rows (deps consumers branch on these)
    "operators": (
        "@file:JvmName(\"X\")\n"
        "package p.q\n"
        "\n"
        "import a.b.C as D\n"
        "\n"
        "@Ann(x) class Box<T>(val t: T)\n"
        "fun <T> Box<T>.f(): T? = this?.t\n"
        "val r = R.string.k\n"
        "val m = mapOf(1 to 2)[1]\n"
        "val g = { x: Int -> x * 2 }\n"
        "val k = String::class.java\n"
        "val e = a ?: b!!\n"
        "val n = a !in b && c !is D && (d as? E) != null\n"
        "val p = x::y\n"
    ),
    "string_content_operators": "val dot = \".\"\nval br = \"]\"\nval gt = \">\"\nval sep = \"::\"\nclass After\n",
    "numbers": "val n = listOf(1.5f, 0x1F, 1..2, 1e-5, 1_000L, 0b101, 2.0e10, .5)\n",
    # --- invalid input
    "invalid_unterminated_string": "val s = \"abc\nval probe = 1\n",
    "invalid_unterminated_raw": "val s = \"\"\"abc\n// x\n",
    "invalid_unterminated_block": "/* never closed\nval probe = 1\n",
    "invalid_unterminated_template": "val s = \"${a\n",
    "invalid_unclosed_char": "val c = 'ab\nval probe = 1\n",
    "invalid_unclosed_backtick": "val `x = 1\nval probe = 1\n",
    "invalid_backslash_newline_in_string": "val s = \"a\\\nb\"\nval probe = 1\n",
    "invalid_backslash_in_code": "val a = foo \\ bar\nval probe = 1\n",
}

# Mapper self-test (control e): source -> the pinned ktLex-vocabulary sequence.
M = {
    "not_in": ("a !in b\n", "n:a o:! n:in n:b"),
    "not_is": ("a !is B\n", "n:a o:! n:is n:B"),
    "as_safe": ("a as? B\n", "n:a n:as o:? n:B"),
    "safe_elvis_bang": ("a?.b ?: c!!\n", "n:a o:? o:. n:b o:? o:: n:c o:! o:!"),
    "class_ref": ("x::class.java\n", "n:x o::: n:class o:. n:java"),
    "lambda_arrow": ("f { a -> b }\n", "n:f o:{ n:a o:- o:> n:b o:}"),
    "range_until": ("0..<n\n", "d:0 o:. o:. o:< n:n"),
    "annotation_call": ("@Ann(1) val v\n", "o:@ n:Ann o:( d:1 o:) n:val n:v"),
    "label_return": ("return@forEach\n", "n:return o:@ n:forEach"),
    "label_this": ("this@Outer\n", "n:this o:@ n:Outer"),
    "escaped_keyword": ("`in`\n", "n:in`"),
    "numbers": ("1.5f 0x1F 1e-5\n", "d:1.5f d:0x1F d:1e o:- d:5"),
}


def write(d, name, src):
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, name), "wb") as f:
        f.write(src.encode("utf-8"))


def main():
    for name, src in C.items():
        write(os.path.join(S, "constructs"), name + ".kt", src)
    with open(os.path.join(S, "mapper_expect.tsv"), "w") as f:
        for name, (src, want) in M.items():
            write(os.path.join(S, "mapper"), name + ".kt", src)
            f.write(name + "\t" + want + "\n")
    print("C rows:", len(C), "M rows:", len(M))


if __name__ == "__main__":
    sys.exit(main())
````

`zz_t1992_dump_test.go` (sha256 `526a6ce1d7412a0e9240b6771509bac02e3888e326b65d4f0a5b45ec182f4adf`):

````go
package deps

// THROWAWAY (t1992): dumps what the three Kotlin-family lexers read in every
// file listed in $T1992_LIST (group \t label \t abs-path), for the
// KtFamily.java comparison against the real KotlinLexer. Byte-identical in
// every snapshot; ktTok (zz_t1992_tok_test.go) is the per-snapshot adapter.

import (
	"bufio"
	"encoding/base64"
	"fmt"
	"os"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// t1992Esc makes a token text one space-free field: \ space newline CR tab.
func t1992Esc(s string) string {
	r := strings.NewReplacer(`\`, `\\`, " ", `\s`, "\n", `\n`, "\r", `\r`, "\t", `\t`)
	return r.Replace(s)
}

// t1992Open: '.' when every string, comment and template is closed at the
// start of line i+1, 'o' otherwise (a refused line-start prefix).
func t1992Open(src string, accepts func(string) bool) string {
	var b strings.Builder
	for at := 0; at < len(src); { // a final "\n" starts no line, as annot.splitLines
		if accepts(src[:at]) {
			b.WriteByte('.')
		} else {
			b.WriteByte('o')
		}
		nl := strings.IndexByte(src[at:], '\n')
		if nl < 0 {
			break
		}
		at += nl + 1
	}
	return b.String()
}

func TestZZT1992Dump(t *testing.T) {
	list, out := os.Getenv("T1992_LIST"), os.Getenv("T1992_OUT")
	if list == "" || out == "" {
		t.Skip("T1992_LIST / T1992_OUT unset")
	}
	data, err := os.ReadFile(list)
	if err != nil {
		t.Fatal(err)
	}
	f, err := os.Create(out)
	if err != nil {
		t.Fatal(err)
	}
	defer f.Close()
	w := bufio.NewWriter(f)
	defer w.Flush()
	acceptAnnot := func(s string) bool { return annot.Classify(annot.Kotlin, []byte(s)).Uncertain == nil }
	acceptKt := func(s string) bool { _, err := ktLex(s); return err == nil }
	acceptKts := func(s string) bool { _, at := blankGradleComments(s, true); return at < 0 }
	n := 0
	for _, row := range strings.Split(strings.TrimRight(string(data), "\n"), "\n") {
		fl := strings.Split(row, "\t")
		if len(fl) != 3 {
			t.Fatalf("bad list row %q", row)
		}
		raw, err := os.ReadFile(fl[2])
		if err != nil {
			t.Fatal(err)
		}
		src := string(raw)
		c := annot.Classify(annot.Kotlin, raw)
		var cls strings.Builder
		for _, k := range c.Class {
			cls.WriteByte("c#L"[k])
		}
		u := 0
		if c.Uncertain != nil {
			u = c.Uncertain.Line
		}
		toks, kerr := ktLex(src)
		ks := make([]string, len(toks))
		for i, k := range toks {
			ks[i] = ktTok(k)
		}
		kfail := 0
		if kerr != nil {
			kfail = 1
		}
		blanked, at := blankGradleComments(src, true)
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%d\t%d\t%s\t%s\t%d\t%s\t%s\t%s\t%d\t%d\n",
			fl[0], fl[1], base64.StdEncoding.EncodeToString(raw),
			cls.String(), u,
			kfail, base64.StdEncoding.EncodeToString([]byte(strings.Join(ks, " "))),
			base64.StdEncoding.EncodeToString([]byte(blanked)), at,
			t1992Open(src, acceptAnnot), t1992Open(src, acceptKt), t1992Open(src, acceptKts),
			c.Package, c.Import)
		n++
	}
	t.Logf("dumped %d records to %s", n, out)
}
````

`zz_t1992_tok_snap_test.go` (sha256 `f0b4cceac57e2735f89b234d02807cd4b7b5f3f820f9feba89083eccd5e9198c`):

````go
package deps

import "strconv"

// THROWAWAY (t1992) adapter for HEAD: ktok carries esc (t1997).
// Rendering: <kind><flag>@<line>:<text>; flag "`" escaped, "" not.
func ktTok(k ktok) string {
	flag := ""
	if k.esc {
		flag = "`"
	}
	return string(k.kind) + flag + "@" + strconv.Itoa(k.line) + ":" + t1992Esc(k.text)
}
````

`zz_t1992_tok_hist_test.go` (sha256 `bc6206243fc9560ea3d01d968c9936472a8dafc929762357259c7ba07c434729`):

````go
package deps

import "strconv"

// THROWAWAY (t1992) adapter for 3d1a2b628 / cf210a9e9: ktok is {kind, text,
// line}, no esc field. Flag "?" = escape unknown (not compared).
func ktTok(k ktok) string {
	return string(k.kind) + "?" + "@" + strconv.Itoa(k.line) + ":" + t1992Esc(k.text)
}
````

`KtFamily.java` (sha256 `c2fec65a7726d5468c525ccc13677893d3a8a533722eb0bec0105d07a8294956`):

````java
// KtFamily.java (t1992) - the real KotlinLexer against the three Kotlin-family
// lexers' dump (zz_t1992_dump_test.go records:
//   group \t label \t b64(src) \t annot-classes \t annot-uncertain \t kt-fail
//   \t b64(kt tokens) \t b64(kts blanked) \t kts-failAt \t openA \t openK \t openG).
//
// adapt() is t1990's KtAdapter.adapt (aiplans/archived/p1990_*.md), changed
// only to (1) accept '\r' (lines split on '\n', a '\r' stays on its line, as
// annot.splitLines) and (2) return its per-line start states. isComment() is
// t1999's KtProbe.isComment (aiplans/archived/p1999_*.md); the blanking is
// KtProbe.blank done on original bytes.
//
// usage: KtFamily <dump.tsv> [--mapper mapper_expect.tsv] [--truth-out f]
//        [--details H,C,M]   (groups whose token texts may be printed)
import java.nio.ByteBuffer;
import java.nio.charset.CharacterCodingException;
import java.nio.charset.CodingErrorAction;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.*;
import org.jetbrains.kotlin.com.intellij.psi.tree.IElementType;
import org.jetbrains.kotlin.lexer.KotlinLexer;
import org.jetbrains.kotlin.lexer.KtTokens;

public class KtFamily {
  record Tok(IElementType type, int start, int end) {}
  record Frame(char kind, int line) {}
  record Result(String classes, int uncertain, List<String> notes, List<Tok> toks, char[] start) {}

  static int[] starts; // 0-based offset of each line

  static int lineOf(int off) { // 1-based
    int lo = 0, hi = starts.length - 1;
    while (lo < hi) {
      int mid = (lo + hi + 1) / 2;
      if (starts[mid] <= off) lo = mid; else hi = mid - 1;
    }
    return lo + 1;
  }

  // closed reports a block/doc comment token whose own nesting returns to 0.
  static boolean closed(String t) {
    int depth = 0;
    for (int i = 0; i < t.length(); ) {
      if (t.startsWith("/*", i)) { depth++; i += 2; }
      else if (t.startsWith("*/", i) && depth > 0) { depth--; i += 2; if (depth == 0) return i == t.length(); }
      else i++;
    }
    return false;
  }

  static Result adapt(String src) {
    if (src.startsWith("﻿")) src = src.substring(1); // as bomLen(Kotlin) and kotlinc
    String body = src.endsWith("\n") ? src.substring(0, src.length() - 1) : src;
    String[] lines = src.isEmpty() ? new String[0] : body.split("\n", -1);
    starts = new int[Math.max(lines.length, 1)];
    for (int i = 1, off = 0; i < lines.length; i++) { off += lines[i - 1].length() + 1; starts[i] = off; }
    List<Tok> toks = new ArrayList<>();
    KotlinLexer lx = new KotlinLexer();
    lx.start(src);
    while (lx.getTokenType() != null) { toks.add(new Tok(lx.getTokenType(), lx.getTokenStart(), lx.getTokenEnd())); lx.advance(); }

    char[] start = new char[lines.length]; // L, c (template), E (empty stack: # or c)
    IElementType[] first = new IElementType[lines.length];
    List<String> notes = new ArrayList<>();
    Deque<Frame> stack = new ArrayDeque<>(); // push/peek at the head = innermost
    int unclosedComment = 0;
    if (lines.length > 0) start[0] = 'E';
    for (Tok t : toks) {
      int ln = lineOf(t.start);
      if (t.type != KtTokens.WHITE_SPACE && first[ln - 1] == null && t.start >= starts[ln - 1]) first[ln - 1] = t.type;
      if (t.type.toString().equals("BAD_CHARACTER")) notes.add("BAD_CHARACTER@" + ln + ":" + src.substring(t.start, t.end));
      if (t.type == KtTokens.DANGLING_NEWLINE) {
        return new Result(null, stack.peek().line, notes, toks, start); // innermost string's line
      }
      if ((t.type == KtTokens.BLOCK_COMMENT || t.type == KtTokens.DOC_COMMENT) && !closed(src.substring(t.start, t.end))) {
        unclosedComment = ln;
      }
      for (int o = t.start; o < t.end; o++) {
        if (src.charAt(o) != '\n') continue;
        int next = lineOf(o + 1);
        if (o + 1 >= src.length() || starts[next - 1] != o + 1) continue; // final newline
        char s;
        if (t.type == KtTokens.REGULAR_STRING_PART || t.type == KtTokens.BLOCK_COMMENT || t.type == KtTokens.DOC_COMMENT) s = 'L';
        else if (t.type == KtTokens.WHITE_SPACE) s = stack.isEmpty() ? 'E' : (stack.peek().kind == 't' ? 'c' : '?');
        else { s = '?'; notes.add("newline in " + t.type + "@" + next); }
        start[next - 1] = s;
      }
      if (t.type == KtTokens.OPEN_QUOTE) stack.push(new Frame('s', ln));
      else if (t.type == KtTokens.LONG_TEMPLATE_ENTRY_START) stack.push(new Frame('t', ln));
      else if (t.type == KtTokens.CLOSING_QUOTE || t.type == KtTokens.LONG_TEMPLATE_ENTRY_END) {
        char want = t.type == KtTokens.CLOSING_QUOTE ? 's' : 't';
        if (stack.isEmpty() || stack.peek().kind != want) notes.add("unbalanced " + t.type + "@" + ln);
        else stack.pop();
      }
    }
    if (!stack.isEmpty()) return new Result(null, stack.peekLast().line, notes, toks, start); // outermost
    if (unclosedComment != 0) return new Result(null, unclosedComment, notes, toks, start);
    StringBuilder b = new StringBuilder();
    for (int i = 0; i < lines.length; i++) {
      char s = start[i];
      if (s == 'E') s = first[i] == KtTokens.EOL_COMMENT ? '#' : 'c';
      b.append(s);
    }
    return new Result(b.toString(), 0, notes, toks, start);
  }

  static boolean isComment(IElementType t) {
    return t == KtTokens.EOL_COMMENT || t == KtTokens.BLOCK_COMMENT || t == KtTokens.DOC_COMMENT
        || t == KtTokens.SHEBANG_COMMENT;
  }

  // ---------------------------------------------------------------- mapper

  static String esc(String s) {
    StringBuilder b = new StringBuilder();
    for (char c : s.toCharArray()) {
      switch (c) {
        case '\\' -> b.append("\\\\");
        case ' ' -> b.append("\\s");
        case '\n' -> b.append("\\n");
        case '\r' -> b.append("\\r");
        case '\t' -> b.append("\\t");
        default -> b.append(c);
      }
    }
    return b.toString();
  }

  static String tok(char kind, String flag, int line, String text) { return kind + flag + "@" + line + ":" + esc(text); }

  static boolean asciiIdentStart(char c) { return c == '_' || c >= 'a' && c <= 'z' || c >= 'A' && c <= 'Z'; }
  static boolean asciiIdentChar(char c) { return asciiIdentStart(c) || c >= '0' && c <= '9'; }

  static int numericSplits; // literals the ktLex digit rule splits into > 1 token
  static List<String> numericSplitAt = new ArrayList<>();

  // split re-tokenises code text exactly the way ktLexer.code segments code
  // (kotlinlex.go: whitespace, "::", the digit rule, ident(), '$' runs, one
  // operator byte); strings, chars and comments never reach it.
  static void split(String text, int line, List<String> out) {
    int n = text.length();
    for (int i = 0; i < n; ) {
      char c = text.charAt(i);
      if (c == ' ' || c == '\t' || c == '\r' || c == '\f' || c == '\n') { i++; continue; }
      if (c == ':' && i + 1 < n && text.charAt(i + 1) == ':') { out.add(tok('o', "", line, "::")); i += 2; continue; }
      if (c >= '0' && c <= '9') {
        int j = i;
        while (j < n && (asciiIdentChar(text.charAt(j)) || text.charAt(j) == '.' && j + 1 < n && text.charAt(j + 1) >= '0' && text.charAt(j + 1) <= '9')) j++;
        out.add(tok('d', "", line, text.substring(i, j)));
        i = j;
        continue;
      }
      if (asciiIdentStart(c) || c >= 0x80) {
        int j = i;
        while (j < n) {
          int cp = text.codePointAt(j);
          if (cp == '_' || Character.isLetter(cp) || (j > i && Character.isDigit(cp))) { j += Character.charCount(cp); continue; }
          break;
        }
        if (j == i) { i += Character.charCount(text.codePointAt(i)); continue; } // a non-letter symbol: ktLex skips it
        out.add(tok('n', "", line, text.substring(i, j)));
        i = j;
        continue;
      }
      out.add(tok('o', "", line, String.valueOf(c)));
      i++;
    }
  }

  static boolean isNumeric(IElementType t) { return t == KtTokens.INTEGER_LITERAL || t == KtTokens.FLOAT_LITERAL; }

  static final class Str { final int line; boolean plain = true; final StringBuilder content = new StringBuilder(); Str(int l) { line = l; } }

  static List<String> mapTokens(String src, List<Tok> toks, String where) {
    List<String> out = new ArrayList<>();
    Deque<Str> strs = new ArrayDeque<>();
    for (Tok t : toks) {
      IElementType ty = t.type;
      String text = src.substring(t.start, t.end);
      int line = lineOf(t.start);
      if (ty == KtTokens.WHITE_SPACE || isComment(ty)) continue;
      if (ty == KtTokens.OPEN_QUOTE) { strs.push(new Str(line)); continue; }
      if (ty == KtTokens.REGULAR_STRING_PART) { if (!strs.isEmpty()) strs.peek().content.append(text); continue; }
      if (ty == KtTokens.ESCAPE_SEQUENCE || ty == KtTokens.SHORT_TEMPLATE_ENTRY_START || ty == KtTokens.LONG_TEMPLATE_ENTRY_START) {
        if (!strs.isEmpty()) strs.peek().plain = false;
        continue;
      }
      if (ty == KtTokens.LONG_TEMPLATE_ENTRY_END) continue;
      if (ty == KtTokens.CLOSING_QUOTE) {
        Str f = strs.isEmpty() ? new Str(line) : strs.pop();
        out.add(f.plain ? tok('s', "", f.line, f.content.toString()) : tok('S', "", f.line, ""));
        continue;
      }
      if (ty == KtTokens.CHARACTER_LITERAL) { out.add(tok('S', "", line, "")); continue; }
      if (ty == KtTokens.IDENTIFIER && text.length() >= 2 && text.startsWith("`") && text.endsWith("`")) {
        out.add(tok('n', "`", line, text.substring(1, text.length() - 1)));
        continue;
      }
      int before = out.size();
      split(text, line, out);
      if (isNumeric(ty) && out.size() - before > 1) { numericSplits++; numericSplitAt.add(where + ":" + line + ":" + text); }
    }
    return out;
  }

  // ---------------------------------------------------------------- compare

  static String stripFlags(String s) { return s.replace("`@", "@").replace("?@", "@"); }

  static int firstDiffLine(String a, String b) { // per-line strings (classes / open vectors)
    for (int i = 0; i < Math.min(a.length(), b.length()); i++) if (a.charAt(i) != b.charAt(i)) return i + 1;
    return Math.min(a.length(), b.length()) + 1;
  }

  static String[] toks(String s) { return s.isEmpty() ? new String[0] : s.split(" ", -1); }

  static int tokLine(String t) { int a = t.indexOf('@'), b = t.indexOf(':', a); return Integer.parseInt(t.substring(a + 1, b)); }

  static int firstDiffTok(String[] a, String[] b) {
    for (int i = 0; i < Math.min(a.length, b.length); i++) if (!a[i].equals(b[i])) return i;
    return a.length == b.length ? -1 : Math.min(a.length, b.length);
  }

  static int byteLine(byte[] b, int off) { int l = 1; for (int i = 0; i < off && i < b.length; i++) if (b[i] == '\n') l++; return l; }

  record Rec(String group, String label, byte[] raw, String aCls, int aU, boolean kFail, String kToks,
             byte[] gBlank, int gFail, String openA, String openK, String openG, String aAnchors) {}

  static Rec parse(String row) {
    String[] f = row.split("\t", -1);
    Base64.Decoder d = Base64.getDecoder();
    return new Rec(f[0], f[1], d.decode(f[2]), f[3], Integer.parseInt(f[4]), f[5].equals("1"),
        new String(d.decode(f[6]), StandardCharsets.UTF_8), d.decode(f[7]), Integer.parseInt(f[8]), f[9], f[10], f[11],
        "package=" + f[12] + " import=" + f[13]);
  }

  static String route(String group, String label) {
    if (group.equals("C") || group.equals("M")) return "annot,ktLex,kts";
    String p = label.endsWith(".in") ? label.substring(0, label.length() - 3) : label;
    List<String> r = new ArrayList<>();
    if (p.endsWith(".kt") || p.endsWith(".kts")) r.add("annot");
    if (p.endsWith(".kt") || p.endsWith(".kts") && !p.endsWith(".gradle.kts")) r.add("ktLex");
    if (p.endsWith(".gradle.kts")) r.add("kts");
    return String.join(",", r);
  }

  // One char, or one Kotlin escape (\t \b \n \r \' \" \\ \$ \\uXXXX).
  static final String CHAR_LIT = "'(?:[^'\\\\\\n\\r]|\\\\[tbnr'\"\\\\$]|\\\\u[0-9A-Fa-f]{4})'";

  // blankEqual compares two blanked byte arrays, skipping the original's '\r'
  // bytes: a line-terminator byte is neither code nor comment.
  static int blankDiff(byte[] raw, byte[] a, byte[] b) {
    if (a.length != b.length) return Math.min(a.length, b.length);
    for (int i = 0; i < a.length; i++) if (raw[i] != '\r' && a[i] != b[i]) return i;
    return -1;
  }

  record Truth(boolean ok, String excluded, boolean valid, String invalidWhy, String open, String classes,
               String tokens, byte[] blanked, Result r, String anchors) {}

  // anchors is annot's Package / Import rule read off the real tokens: the
  // first line that starts at top level (start state 'E', brace depth 0, no
  // open string) with the token `package`, and the last such line with
  // `import` — the anchors annot's placement reads (rewrite.go fixedPosition).
  static String anchors(String t, Result r) {
    int pkg = 0, imp = 0, brace = 0, strs = 0;
    boolean[] seen = new boolean[r.start.length];
    for (Tok k : r.toks) {
      IElementType ty = k.type;
      if (ty == KtTokens.WHITE_SPACE) continue;
      int ln = lineOf(k.start);
      if (ln - 1 < seen.length && !seen[ln - 1] && k.start >= starts[ln - 1]) {
        seen[ln - 1] = true;
        String text = t.substring(k.start, k.end);
        if (r.start[ln - 1] == 'E' && brace == 0 && strs == 0) {
          if (text.equals("package") && pkg == 0) pkg = ln;
          if (text.equals("import")) imp = ln;
        }
      }
      if (ty == KtTokens.OPEN_QUOTE || ty == KtTokens.LONG_TEMPLATE_ENTRY_START) strs++;
      else if (ty == KtTokens.CLOSING_QUOTE || ty == KtTokens.LONG_TEMPLATE_ENTRY_END) strs = Math.max(0, strs - 1);
      else if (strs == 0 && ty == KtTokens.LBRACE) brace++;
      else if (strs == 0 && ty == KtTokens.RBRACE) brace = Math.max(0, brace - 1);
    }
    return "package=" + pkg + " import=" + imp;
  }

  static String commentRanges = ""; // the last truth()'s comment byte ranges "s-e,…"

  static Truth truth(Rec rec) {
    String src;
    try {
      src = StandardCharsets.UTF_8.newDecoder().onMalformedInput(CodingErrorAction.REPORT)
          .onUnmappableCharacter(CodingErrorAction.REPORT).decode(ByteBuffer.wrap(rec.raw)).toString();
    } catch (CharacterCodingException e) {
      return new Truth(false, "non-UTF-8", false, "", null, null, null, null, null, null);
    }
    for (int i = 0; i < src.length(); i++)
      if (src.charAt(i) == '\r' && (i + 1 >= src.length() || src.charAt(i + 1) != '\n'))
        return new Truth(false, "lone CR", false, "", null, null, null, null, null, null);
    // The lexer text: the BOM stripped (as kotlinc) and CRLF normalised to LF
    // (the IntelliJ lexer reads '\r' as BAD_CHARACTER; kotlinc normalises line
    // separators before lexing). c2b maps each char of t to the byte offset of
    // that char in the original; a CRLF's '\n' maps to the '\n' byte, so its
    // '\r' lies between chars.
    boolean bom = src.startsWith("﻿");
    StringBuilder tb = new StringBuilder();
    List<Integer> map = new ArrayList<>();
    int bo = bom ? 3 : 0;
    for (int i = bom ? 1 : 0; i < src.length(); i++) {
      char c = src.charAt(i);
      if (c == '\r') { bo += 1; continue; } // only CRLF reaches here (lone CR excluded above)
      map.add(bo);
      tb.append(c);
      if (Character.isHighSurrogate(c)) bo += 4;
      else if (!Character.isLowSurrogate(c)) bo += c < 0x80 ? 1 : c < 0x800 ? 2 : 3;
    }
    String t = tb.toString();
    int[] c2b = new int[t.length() + 1];
    for (int i = 0; i < t.length(); i++) c2b[i] = map.get(i);
    c2b[t.length()] = bo;
    Result r = adapt(t);
    String why = "";
    if (r.classes == null) why = "uncertain@" + r.uncertain;
    for (String n : r.notes) if (n.startsWith("BAD_CHARACTER") || n.startsWith("unbalanced") || n.startsWith("newline in")) { why = why.isEmpty() ? n : why; }
    // The lexer reads a malformed char literal ('ab, '') as one
    // CHARACTER_LITERAL token; the compiler rejects it. Lexer acceptance alone
    // is not validity.
    for (Tok k : r.toks)
      if (k.type == KtTokens.CHARACTER_LITERAL && !t.substring(k.start, k.end).matches(CHAR_LIT) && why.isEmpty())
        why = "malformed CHARACTER_LITERAL@" + lineOf(k.start);
    boolean valid = why.isEmpty();
    StringBuilder open = new StringBuilder();
    for (char s : r.start) open.append(s == 'E' ? '.' : 'o');
    String tokens = String.join(" ", mapTokens(t, r.toks, rec.group + ":" + rec.label));
    byte[] blanked = rec.raw.clone();
    List<String> ranges = new ArrayList<>();
    for (Tok k : r.toks) {
      if (!isComment(k.type)) continue;
      ranges.add(c2b[k.start] + "-" + c2b[k.end]);
      for (int b = c2b[k.start]; b < c2b[k.end]; b++) if (blanked[b] != '\n') blanked[b] = ' ';
    }
    commentRanges = String.join(",", ranges);
    return new Truth(true, "", valid, why, open.toString(), r.classes, tokens, blanked, r, anchors(t, r));
  }

  public static void main(String[] args) throws Exception {
    String dump = args[0], mapperFile = null, truthOut = null;
    Set<String> details = new HashSet<>(List.of("H", "C", "M"));
    for (int i = 1; i < args.length; i++) {
      switch (args[i]) {
        case "--mapper" -> mapperFile = args[++i];
        case "--truth-out" -> truthOut = args[++i];
        case "--details" -> details = new HashSet<>(List.of(args[++i].split(",")));
      }
    }
    System.out.println("lexer=" + org.jetbrains.kotlin.config.KotlinCompilerVersion.VERSION + " dump=" + dump);
    Map<String, String> mapperWant = new LinkedHashMap<>();
    if (mapperFile != null)
      for (String l : Files.readAllLines(Path.of(mapperFile), StandardCharsets.UTF_8))
        if (!l.isEmpty()) { String[] f = l.split("\t", 2); mapperWant.put(f[0], f[1]); }

    // counters[group|lexer|key]
    Map<String, Integer> cnt = new TreeMap<>();
    java.util.function.BiConsumer<String, Integer> add = (k, v) -> cnt.merge(k, v, Integer::sum);
    List<String> mism = new ArrayList<>();
    StringBuilder truthTsv = new StringBuilder();
    boolean flipDone = false;
    String flipResult = "not run (no eligible record)";
    int mapperOk = 0, mapperBad = 0;

    for (String row : Files.readAllLines(Path.of(dump), StandardCharsets.UTF_8)) {
      if (row.isEmpty()) continue;
      Rec rec = parse(row);
      String g = rec.group, route = route(g, rec.label);
      boolean show = details.contains(g);
      add.accept(g + "|files", 1);
      Truth tr = truth(rec);
      if (!tr.ok) { add.accept(g + "|excluded:" + tr.excluded, 1); mism.add("EXCLUDED " + g + " " + rec.label + " " + tr.excluded); continue; }
      add.accept(g + (tr.valid ? "|truth valid" : "|truth invalid"), 1);
      if (g.equals("C") && truthOut != null)
        truthTsv.append(rec.label).append('\t').append(tr.valid ? "valid" : "invalid:" + tr.invalidWhy).append('\t')
            .append(tr.open).append('\t').append(tr.classes == null ? "" : tr.classes).append('\t').append(tr.tokens)
            .append('\t').append(Base64.getEncoder().encodeToString(tr.blanked)).append('\t').append(commentRanges).append('\t').append(tr.anchors).append('\n');

      boolean[] refused = {rec.aU != 0, rec.kFail, rec.gFail >= 0};
      String[] names = {"annot", "ktLex", "kts"};
      String[] opens = {rec.openA, rec.openK, rec.openG};
      for (int li = 0; li < 3; li++) {
        String L = names[li];
        boolean routed = Arrays.asList(route.split(",")).contains(L);
        String k = g + "|" + L + "|";
        if (refused[li]) add.accept(k + "refuses", 1);
        // P1
        if (tr.valid && refused[li]) {
          add.accept(k + "P1 refuses-valid", 1);
          mism.add(String.format("MISMATCH %s %s %s P1 refuses-valid routed=%s", g, rec.label, L, routed));
        }
        if (!tr.valid && !refused[li]) {
          add.accept(k + "P1 accepts-invalid", 1);
          mism.add(String.format("MISMATCH %s %s %s P1 accepts-invalid (%s) routed=%s", g, rec.label, L, tr.invalidWhy, routed));
        }
        if (!tr.valid || refused[li]) continue;
        add.accept(k + "compared", 1);
        // P2
        if (!opens[li].equals(tr.open)) {
          add.accept(k + "P2 mismatch", 1);
          mism.add(String.format("MISMATCH %s %s %s P2 line %d routed=%s%s", g, rec.label, L, firstDiffLine(opens[li], tr.open), routed,
              show ? " got=" + opens[li] + " want=" + tr.open : ""));
        }
        // P3
        switch (L) {
          case "annot" -> {
            if (!rec.aCls.equals(tr.classes) || !rec.aAnchors.equals(tr.anchors)) {
              add.accept(k + "P3 mismatch", 1);
              int line = !rec.aCls.equals(tr.classes) ? firstDiffLine(rec.aCls, tr.classes) : 0;
              mism.add(String.format("MISMATCH %s %s annot P3 line %d routed=%s anchors %s want %s%s", g, rec.label, line, routed,
                  rec.aAnchors, tr.anchors, show ? " got=" + rec.aCls + " want=" + tr.classes : ""));
            } else if (!flipDone && g.equals("H") && !rec.aCls.isEmpty()) {
              // control (b): a hand-flipped class string must MISMATCH
              char[] f = rec.aCls.toCharArray();
              f[0] = f[0] == 'c' ? 'L' : 'c';
              flipResult = (new String(f).equals(tr.classes) ? "FAILED (flipped classes still match)" : "ok (flipped classes MISMATCH)") + " on " + rec.label;
              flipDone = true;
            }
          }
          case "ktLex" -> {
            String got = rec.kToks, want = tr.tokens;
            if (got.contains("?@")) { got = stripFlags(got); want = stripFlags(want); add.accept(k + "esc not compared", 1); }
            if (!got.equals(want)) {
              add.accept(k + "P3 mismatch", 1);
              String[] a = toks(got), b = toks(want);
              int i = firstDiffTok(a, b);
              int line = i < a.length ? tokLine(a[i]) : i < b.length ? tokLine(b[i]) : 0;
              String ctx = "";
              if (show) {
                ctx = " got=[" + String.join(" ", Arrays.copyOfRange(a, Math.max(0, i - 2), Math.min(a.length, i + 4)))
                    + "] want=[" + String.join(" ", Arrays.copyOfRange(b, Math.max(0, i - 2), Math.min(b.length, i + 4))) + "]";
              }
              mism.add(String.format("MISMATCH %s %s ktLex P3 line %d routed=%s%s", g, rec.label, line, routed, ctx));
            }
          }
          case "kts" -> {
            int off = blankDiff(rec.raw, rec.gBlank, tr.blanked);
            if (off >= 0) {
              add.accept(k + "P3 mismatch", 1);
              mism.add(String.format("MISMATCH %s %s kts P3 line %d routed=%s", g, rec.label, byteLine(rec.raw, off), routed));
            }
          }
        }
      }
      // pairwise P2 among the lexers that accept the file
      for (int a = 0; a < 3; a++)
        for (int b = a + 1; b < 3; b++)
          if (!refused[a] && !refused[b] && !opens[a].equals(opens[b])) {
            add.accept(g + "|pair " + names[a] + "/" + names[b] + "|P2 differ", 1);
            mism.add(String.format("PAIR     %s %s %s/%s P2 line %d", g, rec.label, names[a], names[b], firstDiffLine(opens[a], opens[b])));
          }
      if (refused[0] != refused[1] || refused[1] != refused[2]) {
        add.accept(g + "|P1 lexers disagree", 1);
        mism.add(String.format("PAIR     %s %s P1 refuses annot=%s ktLex=%s kts=%s (truth %s)", g, rec.label, refused[0], refused[1], refused[2],
            tr.valid ? "valid" : "invalid:" + tr.invalidWhy));
      }
      // control (e): the mapper self-test
      if (g.equals("M") && mapperWant.containsKey(rec.label)) {
        String want = mapperWant.get(rec.label);
        String real = simple(tr.tokens), ours = simple(rec.kToks);
        boolean ok = real.equals(want) && ours.equals(want);
        if (ok) mapperOk++; else mapperBad++;
        System.out.printf("MAPPER %-8s %-16s want=[%s] real=[%s] ktLex=[%s]%n", ok ? "MATCH" : "MISMATCH", rec.label, want, real, ours);
      }
    }
    System.out.println();
    for (String m : mism) System.out.println(m);
    System.out.println();
    System.out.println("== counts");
    for (var e : cnt.entrySet()) System.out.println(e.getKey() + "\t" + e.getValue());
    System.out.println("numeric literals split by the ktLex digit rule: " + numericSplits);
    for (String s : numericSplitAt) System.out.println("  split " + (s.startsWith("R:") ? s.substring(0, s.lastIndexOf(':')) : s));
    System.out.println("control b (flipped annot classes): " + flipResult);
    if (mapperFile != null) System.out.println("control e (mapper self-test): match=" + mapperOk + " mismatch=" + mapperBad);
    if (truthOut != null) Files.writeString(Path.of(truthOut), truthTsv.toString(), StandardCharsets.UTF_8);
  }

  // simple renders a token stream as kind:text (+ "`" when escaped), no lines.
  static String simple(String s) {
    List<String> out = new ArrayList<>();
    for (String t : toks(s)) {
      char kind = t.charAt(0);
      boolean esc = t.charAt(1) == '`';
      String text = t.substring(t.indexOf(':', t.indexOf('@')) + 1);
      out.add(kind + ":" + text + (esc ? "`" : ""));
    }
    return String.join(" ", out);
  }
}
````

`check_opneg.py` (sha256 `e22dc5981eeef3b1a80babc05796dbc01159dc078f4580b77f76ce86d0132e91`):

````python
#!/usr/bin/env python3
# check_opneg.py (t1992, control d): the `::`-split ktLex mutant against the
# baseline (snap). Expectations come from the baseline dump and verdicts:
#  - every record: all non-ktLex-token fields byte-identical; the ktLex stream
#    equals the baseline stream with each `o@N:::` replaced by two `o@N::`;
#  - eligible (baseline ktLex accepts, baseline ktLex P3 MATCH, >= 1 `o:::`):
#    ktLex P3 MISMATCH at the first `::` line; the C operator row is eligible;
#  - every other record keeps its baseline verdict lines unchanged.
import base64
import re
import sys

S = sys.argv[1]


def load(name):
    out = {}
    for row in open(f"{S}/dump_{name}.tsv", encoding="utf-8"):
        f = row.rstrip("\n").split("\t")
        out[(f[0], f[1])] = f
    return out


def verdicts(name):
    v = {}
    for line in open(f"{S}/result_{name}.txt", encoding="utf-8"):
        if line.startswith(("MISMATCH ", "PAIR ")):
            parts = line.split()
            v.setdefault((parts[1], parts[2]), []).append(line.rstrip("\n"))
    return v


base, mut = load("snap"), load("opneg")
vb, vm = verdicts("snap"), verdicts("opneg")
assert base.keys() == mut.keys(), "record sets differ"
fail = []
eligible, detected = [], []
for key, b in base.items():
    m = mut[key]
    for i in (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11):
        if b[i] != m[i]:
            fail.append(f"{key}: field {i} changed")
    btoks = base64.b64decode(b[6]).decode()
    mtoks = base64.b64decode(m[6]).decode()
    want = " ".join(
        f"o@{t[2:t.index(':')]}:: o@{t[2:t.index(':')]}::" if re.fullmatch(r"o@\d+:::", t) else t
        for t in (btoks.split(" ") if btoks else []))
    if mtoks != want:
        fail.append(f"{key}: ktLex stream is not the exact :: split of the baseline")
    has = any(re.fullmatch(r"o@\d+:::", t) for t in (btoks.split(" ") if btoks else []))
    base_p3 = [l for l in vb.get(key, []) if " ktLex P3 " in l or " ktLex P1 " in l]
    if b[5] == "0" and has and not base_p3:
        eligible.append(key)
        first = next(int(t[2:t.index(":")]) for t in btoks.split(" ") if re.fullmatch(r"o@\d+:::", t))
        got = [l for l in vm.get(key, []) if " ktLex P3 " in l]
        if got and f" line {first} " in got[0] + " ":
            detected.append(key)
        else:
            fail.append(f"{key}: eligible but no ktLex P3 MISMATCH at line {first}: {got}")
    elif vb.get(key, []) != vm.get(key, []):
        fail.append(f"{key}: verdicts changed for a non-eligible record")

print(f"records={len(base)} eligible={len(eligible)} detected={len(detected)}")
for g in sorted({k[0] for k in eligible}):
    print(f"  eligible in {g}: {sum(1 for k in eligible if k[0] == g)}")
print("operator row eligible:", ("C", "operators") in eligible)
print("FAILURES:", len(fail))
for f in fail[:20]:
    print("  " + f)
sys.exit(1 if fail or ("C", "operators") not in eligible or not eligible else 0)
````

`gentable.py` (sha256 `23b8653261e20c72d56dfdb163df2edaab593cfb15edf530a455e11aaee98e80`):

````python
#!/usr/bin/env python3
# gentable.py (t1992): turns the oracle truths (truth_C.tsv) and the HEAD
# lexers' readings (dump_snap.tsv, group C) into the Go construct table of
# deps/kotlinfamily_test.go. Every outcome that is not "modelled" must carry
# a reason from REASONS, or the generator stops.
import base64
import sys

S = sys.argv[1]
OUT = sys.argv[2] if len(sys.argv) > 2 else None
LEX = ["annot", "ktLex", "kts"]

RULES = {
    "line_comment": "EOL_COMMENT",
    "block_comment": "BLOCK_COMMENT",
    "nested_block_comment": "BLOCK_COMMENT nesting",
    "doc_comment": "DOC_COMMENT",
    "shebang_plain": "SHEBANG_COMMENT",
    "shebang_slash_star": "SHEBANG_COMMENT holding /*",
    "shebang_brace": "SHEBANG_COMMENT holding {",
    "shebang_paren": "SHEBANG_COMMENT holding (",
    "plain_string_escapes": "STRING, ESCAPE_SEQUENCE",
    "string_template_nested": "LONG_TEMPLATE_ENTRY with nested strings",
    "template_lambda_braces": "LONG_TEMPLATE_ENTRY brace depth",
    "template_comment": "a comment inside LONG_TEMPLATE_ENTRY",
    "template_multiline": "LONG_TEMPLATE_ENTRY across lines",
    "short_template_ident": "SHORT_TEMPLATE_ENTRY",
    "short_template_backticked": "SHORT_TEMPLATE_ENTRY + ESCAPED_IDENTIFIER in STRING",
    "short_template_backticked_raw": "SHORT_TEMPLATE_ENTRY + ESCAPED_IDENTIFIER in RAW_STRING",
    "lonely_dollar": "LONELY_DOLLAR",
    "raw_string_lookalikes": "RAW_STRING",
    "raw_string_backslash_end": "RAW_STRING: no escapes",
    "raw_string_quote_run": "RAW_STRING: THREE_OR_MORE_QUO",
    "raw_template_nested_raw": "RAW_STRING template holding a RAW_STRING",
    "char_literals": "CHARACTER_LITERAL",
    "backticked_names": "ESCAPED_IDENTIFIER",
    "multidollar_raw_desync": "{INTERPOLATION}?\\\"\\\"\\\" (Kotlin 2.2)",
    "multidollar_plain": "{INTERPOLATION}?\\\" (Kotlin 2.2)",
    "multidollar_in_template": "{INTERPOLATION}?\\\" inside LONG_TEMPLATE_ENTRY",
    "single_dollar_prefix": "{INTERPOLATION}?\\\" with one $",
    "bom_comment": "a leading byte-order mark",
    "crlf": "CRLF line separators",
    "operators": "operator and keyword tokens deps reads",
    "string_content_operators": "STRING content that looks like operators",
    "numbers": "INTEGER_LITERAL, FLOAT_LITERAL",
    "invalid_unterminated_string": "DANGLING_NEWLINE",
    "invalid_unterminated_raw": "an unclosed RAW_STRING",
    "invalid_unterminated_block": "an unclosed BLOCK_COMMENT",
    "invalid_unterminated_template": "an unclosed LONG_TEMPLATE_ENTRY",
    "invalid_unclosed_char": "a malformed CHARACTER_LITERAL",
    "invalid_unclosed_backtick": "an unclosed ESCAPED_IDENTIFIER",
    "invalid_backslash_newline_in_string": "a backslash before a newline in STRING",
    "invalid_backslash_in_code": "BAD_CHARACTER \\\\",
}

# (row, lexer) -> why, for every outcome that is not "modelled".
REASONS = {
    ("multidollar_raw_desync", "ktLex"): "multi-dollar strings fail closed in deps (t1980): one file opaque; annot models them (t1990)",
    ("multidollar_raw_desync", "kts"): "multi-dollar strings fail closed in deps (t1975): the module widens; annot models them (t1990)",
    ("multidollar_plain", "ktLex"): "multi-dollar strings fail closed in deps (t1980)",
    ("multidollar_plain", "kts"): "multi-dollar strings fail closed in deps (t1975)",
    ("multidollar_in_template", "ktLex"): "multi-dollar strings fail closed in deps (t1980)",
    ("multidollar_in_template", "kts"): "multi-dollar strings fail closed in deps (t1975)",
    ("single_dollar_prefix", "ktLex"): "a $-prefixed string fails closed in deps (t1980), a single $ included",
    ("single_dollar_prefix", "kts"): "a $-prefixed string fails closed in deps (t1975), a single $ included",
    ("shebang_plain", "ktLex"): "shebang not modelled: its line is read as code tokens (t2030)",
    ("shebang_slash_star", "annot"): "shebang not modelled: its /* opens a comment that never closes (t2030)",
    ("shebang_slash_star", "ktLex"): "shebang not modelled: its /* opens a comment that never closes (t2030)",
    ("shebang_brace", "annot"): "shebang not modelled: its { hides the package line from the anchors (t2030)",
    ("shebang_brace", "ktLex"): "shebang not modelled: its { hides the package clause and every declaration from scanKotlin (t2030)",
    ("shebang_paren", "ktLex"): "shebang not modelled: its ( hides every declaration from scanKotlin (t2030)",
    ("crlf", "ktLex"): "a raw string's content keeps the \\r that kotlinc normalises away (t1992 decision record)",
    ("invalid_unclosed_char", "annot"): "invalid Kotlin read leniently: an unclosed char literal is a stray quote",
    ("invalid_unclosed_backtick", "annot"): "invalid Kotlin read leniently: an unclosed backtick is a stray character",
    ("invalid_backslash_newline_in_string", "ktLex"): "invalid Kotlin read leniently: the backslash escapes the newline",
    ("invalid_backslash_newline_in_string", "kts"): "invalid Kotlin read leniently: the backslash escapes the newline",
    ("invalid_backslash_in_code", "annot"): "invalid Kotlin read leniently: a backslash in code is ignored",
    ("invalid_backslash_in_code", "ktLex"): "invalid Kotlin read leniently: a backslash in code is an operator token",
}


def go_quote(s: str) -> str:
    out = ['"']
    for ch in s:
        o = ord(ch)
        if ch == "\\":
            out.append("\\\\")
        elif ch == '"':
            out.append('\\"')
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif o < 0x20 or o == 0x7F or o == 0xFEFF:
            out.append("\\u%04x" % o)
        else:
            out.append(ch)
    out.append('"')
    return "".join(out)


def blank(raw: bytes, ranges: str) -> bytes:
    b = bytearray(raw)
    for r in filter(None, ranges.split(",")):
        s, e = map(int, r.split("-"))
        for i in range(s, e):
            if b[i] != ord("\n"):
                b[i] = ord(" ")
    return bytes(b)


def main():
    truth = {}
    for row in open(f"{S}/truth_C.tsv", encoding="utf-8"):
        f = row.rstrip("\n").split("\t")
        truth[f[0]] = dict(valid=f[1] == "valid", why=f[1], open=f[2], classes=f[3], tokens=f[4],
                           blanked=base64.b64decode(f[5]), comments=f[6], anchors=f[7])
    rec = {}
    for row in open(f"{S}/dump_snap.tsv", encoding="utf-8"):
        f = row.rstrip("\n").split("\t")
        if f[0] != "C":
            continue
        raw = base64.b64decode(f[2])
        rec[f[1]] = dict(raw=raw, src=raw.decode("utf-8"),
                         acc=[f[4] == "0", f[5] == "0", f[8] == "-1"],
                         open=[f[9], f[10], f[11]],
                         proj=[f[3] + " package=" + f[12] + " import=" + f[13],
                               base64.b64decode(f[6]).decode("utf-8"), base64.b64decode(f[7]).decode("utf-8")])
    missing, used = [], set()
    lines = []
    for name in sorted(rec):
        r, t = rec[name], truth[name]
        if t["valid"]:
            assert blank(r["raw"], t["comments"]) == t["blanked"], name + ": ranges do not rebuild the blanking"
        tp = [t["classes"] + " " + t["anchors"], t["tokens"], blank(r["raw"], t["comments"]).decode("utf-8")]
        outs = []
        for i, lx in enumerate(LEX):
            if not r["acc"][i]:
                why = REASONS.get((name, lx))
                if why is None and not t["valid"]:
                    why = "invalid Kotlin"
                if why is None:
                    missing.append((name, lx, "refuses"))
                    why = "TODO"
                used.add((name, lx))
                outs.append(f"refuses({go_quote(why)})")
            elif t["valid"] and r["open"][i] == t["open"] and r["proj"][i] == tp[i]:
                if (name, lx) in REASONS:
                    sys.exit(f"reason given for a modelled outcome: {name}/{lx}")
                outs.append("modelled")
            else:
                why = REASONS.get((name, lx))
                if why is None:
                    missing.append((name, lx, "differs"))
                    why = "TODO"
                used.add((name, lx))
                proj = r["proj"][i]
                outs.append(f"differs({go_quote(r['open'][i])}, {go_quote(proj)}, {go_quote(why)})")
        lines.append((name, r, t, outs))
    stale = set(REASONS) - used
    if missing or stale:
        for m in missing:
            print("MISSING REASON", *m)
        for s in sorted(stale):
            print("UNUSED REASON", *s)
        sys.exit(1)
    if OUT is None:
        for name, r, t, outs in lines:
            print(name, "|", " | ".join(o.split("(")[0] for o in outs))
        return
    with open(OUT, "w", encoding="utf-8") as f:
        for name, r, t, outs in lines:
            f.write("\t{\n")
            f.write(f"\t\tname: {go_quote(name)}, rule: {go_quote(RULES[name])},\n")
            f.write(f"\t\tsrc: {go_quote(r['src'])},\n")
            if t["valid"]:
                f.write(f"\t\topen: {go_quote(t['open'])}, classes: {go_quote(t['classes'])}, anchors: {go_quote(t['anchors'])},\n")
                f.write(f"\t\ttokens:   {go_quote(t['tokens'])},\n")
                f.write(f"\t\tcomments: {go_quote(t['comments'])},\n")
            f.write(f"\t\twant: [3]familyOutcome{{{', '.join(outs)}}},\n")
            f.write("\t},\n")
    print("wrote", OUT, len(lines), "rows")


if __name__ == "__main__":
    main()
````

`negctl.sh` (sha256 `54974637203ec48acf88ba22e40055d538e99276d4fdacb23685212a750440fb`):

````sh
#!/usr/bin/env bash
# negctl.sh (t1992, Step 7): one mutation per fresh `git archive HEAD
# goengines` copy plus the new test; each must make the family tests fail.
set -euo pipefail
S="$(cd "$(dirname "$0")" && pwd)"
REPO=/home/ddt/Work/aitasks

fresh() {
	rm -rf "$S/neg" && mkdir -p "$S/neg"
	git -C "$REPO" archive HEAD goengines | tar -x -C "$S/neg"
	cp "$S/kotlinfamily_test.go" "$S/neg/goengines/internal/testmap/deps/"
}

# mutate <file> <python-old> <python-new>: exactly one occurrence, verified.
mutate() {
	python3 - "$1" "$2" "$3" <<'EOF'
import sys
p, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(p).read()
assert s.count(old) == 1, f"{p}: {s.count(old)} occurrences"
open(p, "w").write(s.replace(old, new))
EOF
}

run() {
	echo "== control $1: $2"
	(cd "$S/neg/goengines" && go test ./internal/testmap/deps/ -run 'TestKotlinFamily' -count=1 2>&1 |
		grep -E '^\s+kotlinfamily_test.go|^(ok|FAIL|---)' | sed -E 's/ — .*//' | cut -c1-230) || true
}

A=internal/testmap/annot/lexctx.go
K=internal/testmap/deps/kotlinlex.go
T=internal/testmap/deps/kotlinfamily_test.go

fresh
mutate "$S/neg/goengines/$A" 'stack[len(stack)-1].dollars = max(n, 1)
					j += n + 3' 'stack[len(stack)-1].dollars = 1 // t1992 control a
					j += n + 3'
mutate "$S/neg/goengines/$A" 'stack[len(stack)-1].dollars = max(n, 1)
					j += n + 1' 'stack[len(stack)-1].dollars = 1 // t1992 control a
					j += n + 1'
run a "annot ignores the interpolation prefix (dollars forced to 1)"

fresh
mutate "$S/neg/goengines/$K" "		case l.src[l.i] == '/' && l.peek(1) == '*':
			depth++" "		case l.src[l.i] == '/' && l.peek(1) == '*' && depth == 0: // t1992 control b
			depth++"
run b "ktLex block comments do not nest"

fresh
mutate "$S/neg/goengines/$K" '			l.emit('"'"'o'"'"', "::", l.line)' '			l.emit('"'"'o'"'"', ":", l.line) // t1992 control c
			l.emit('"'"'o'"'"', ":", l.line)'
run c "ktLex emits :: as two : tokens"

fresh
mutate "$S/neg/goengines/$T" '	"../annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in":  {"annot=....... ktLex=refuses kts=refuses", familyMultiDollar},
' ''
run d "one kotlinFamilyCorpusKnown entry deleted"

fresh
mutate "$S/neg/goengines/$T" 'const familyMultiDollar =' 'func init() { kotlinFamilyCorpusKnown["testdata/no/such.kt.in"] = struct{ view, why string }{"x", "bogus"} }

const familyMultiDollar ='
run e "a bogus kotlinFamilyCorpusKnown entry added"
rm -rf "$S/neg"
````

`opneg.patch` (sha256 `bf8d1895d2dd08a294b8522b5b5d9b2b8db68eaeb02ea3f724137ae53ae1366a`):

````diff
--- /tmp/claude-1000/-home-ddt-Work-aitasks/7cbb58a1-f7e1-48bb-956e-b856fe20d8b2/scratchpad/t1992/kotlinlex.go.orig	2026-10-16 01:10:01.372313294 +0300
+++ /tmp/claude-1000/-home-ddt-Work-aitasks/7cbb58a1-f7e1-48bb-956e-b856fe20d8b2/scratchpad/t1992/opneg/goengines/internal/testmap/deps/kotlinlex.go	2026-10-16 01:10:01.379920742 +0300
@@ -91,7 +91,8 @@
 			l.emit('o', "}", l.line)
 			l.i++
 		case c == ':' && l.peek(1) == ':':
-			l.emit('o', "::", l.line)
+			l.emit('o', ":", l.line) // t1992 control d: :: split in two
+			l.emit('o', ":", l.line)
 			l.i += 2
 		case c >= '0' && c <= '9':
 			j := l.i
````

### Outputs

KtFamily on `snap` (HEAD):

````text
lexer=2.3.20 dump=dump_snap.tsv
MAPPER MATCH    annotation_call  want=[o:@ n:Ann o:( d:1 o:) n:val n:v] real=[o:@ n:Ann o:( d:1 o:) n:val n:v] ktLex=[o:@ n:Ann o:( d:1 o:) n:val n:v]
MAPPER MATCH    as_safe          want=[n:a n:as o:? n:B] real=[n:a n:as o:? n:B] ktLex=[n:a n:as o:? n:B]
MAPPER MATCH    class_ref        want=[n:x o::: n:class o:. n:java] real=[n:x o::: n:class o:. n:java] ktLex=[n:x o::: n:class o:. n:java]
MAPPER MATCH    escaped_keyword  want=[n:in`] real=[n:in`] ktLex=[n:in`]
MAPPER MATCH    label_return     want=[n:return o:@ n:forEach] real=[n:return o:@ n:forEach] ktLex=[n:return o:@ n:forEach]
MAPPER MATCH    label_this       want=[n:this o:@ n:Outer] real=[n:this o:@ n:Outer] ktLex=[n:this o:@ n:Outer]
MAPPER MATCH    lambda_arrow     want=[n:f o:{ n:a o:- o:> n:b o:}] real=[n:f o:{ n:a o:- o:> n:b o:}] ktLex=[n:f o:{ n:a o:- o:> n:b o:}]
MAPPER MATCH    not_in           want=[n:a o:! n:in n:b] real=[n:a o:! n:in n:b] ktLex=[n:a o:! n:in n:b]
MAPPER MATCH    not_is           want=[n:a o:! n:is n:B] real=[n:a o:! n:is n:B] ktLex=[n:a o:! n:is n:B]
MAPPER MATCH    numbers          want=[d:1.5f d:0x1F d:1e o:- d:5] real=[d:1.5f d:0x1F d:1e o:- d:5] ktLex=[d:1.5f d:0x1F d:1e o:- d:5]
MAPPER MATCH    range_until      want=[d:0 o:. o:. o:< n:n] real=[d:0 o:. o:. o:< n:n] ktLex=[d:0 o:. o:. o:< n:n]
MAPPER MATCH    safe_elvis_bang  want=[n:a o:? o:. n:b o:? o:: n:c o:! o:!] real=[n:a o:? o:. n:b o:? o:: n:c o:! o:!] ktLex=[n:a o:? o:. n:b o:? o:: n:c o:! o:!]

MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/script.kts.in ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@3:println o@3:( s@3:hi o@3:)]
MISMATCH C crlf ktLex P3 line 1 routed=true got=[n@1:r o@1:= s@1:\r\n//\sin\sraw\r\n n@5:val n@5:probe o@5:=] want=[n@1:r o@1:= s@1:\n//\sin\sraw\n n@5:val n@5:probe o@5:=]
MISMATCH C invalid_backslash_in_code annot P1 accepts-invalid (BAD_CHARACTER@1:\) routed=true
MISMATCH C invalid_backslash_in_code ktLex P1 accepts-invalid (BAD_CHARACTER@1:\) routed=true
PAIR     C invalid_backslash_in_code P1 refuses annot=false ktLex=false kts=true (truth invalid:BAD_CHARACTER@1:\)
MISMATCH C invalid_backslash_newline_in_string ktLex P1 accepts-invalid (uncertain@1) routed=true
MISMATCH C invalid_backslash_newline_in_string kts P1 accepts-invalid (uncertain@1) routed=true
PAIR     C invalid_backslash_newline_in_string P1 refuses annot=true ktLex=false kts=false (truth invalid:uncertain@1)
MISMATCH C invalid_unclosed_backtick annot P1 accepts-invalid (BAD_CHARACTER@1:`) routed=true
PAIR     C invalid_unclosed_backtick P1 refuses annot=false ktLex=true kts=true (truth invalid:BAD_CHARACTER@1:`)
MISMATCH C invalid_unclosed_char annot P1 accepts-invalid (malformed CHARACTER_LITERAL@1) routed=true
PAIR     C invalid_unclosed_char P1 refuses annot=false ktLex=true kts=true (truth invalid:malformed CHARACTER_LITERAL@1)
MISMATCH C multidollar_in_template ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_in_template kts P1 refuses-valid routed=true
PAIR     C multidollar_in_template P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C multidollar_plain ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_plain kts P1 refuses-valid routed=true
PAIR     C multidollar_plain P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C multidollar_raw_desync ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_raw_desync kts P1 refuses-valid routed=true
PAIR     C multidollar_raw_desync P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C shebang_brace annot P3 line 0 routed=true anchors package=0 import=0 want package=2 import=0 got=ccc#c want=ccc#c
MISMATCH C shebang_brace ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@2:package n@2:p n@3:class n@3:Actual]
MISMATCH C shebang_paren ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@2:package n@2:p n@3:class n@3:Actual]
MISMATCH C shebang_plain ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@3:val n@3:probe o@3:= d@3:1]
MISMATCH C shebang_slash_star annot P1 refuses-valid routed=true
MISMATCH C shebang_slash_star ktLex P1 refuses-valid routed=true
PAIR     C shebang_slash_star P1 refuses annot=true ktLex=true kts=false (truth valid)
MISMATCH C single_dollar_prefix ktLex P1 refuses-valid routed=true
MISMATCH C single_dollar_prefix kts P1 refuses-valid routed=true
PAIR     C single_dollar_prefix P1 refuses annot=false ktLex=true kts=true (truth valid)

== counts
C|P1 lexers disagree	9
C|annot|P1 accepts-invalid	3
C|annot|P1 refuses-valid	1
C|annot|P3 mismatch	1
C|annot|compared	31
C|annot|refuses	6
C|files	40
C|ktLex|P1 accepts-invalid	2
C|ktLex|P1 refuses-valid	5
C|ktLex|P3 mismatch	4
C|ktLex|compared	27
C|ktLex|refuses	11
C|kts|P1 accepts-invalid	1
C|kts|P1 refuses-valid	4
C|kts|compared	28
C|kts|refuses	11
C|truth invalid	8
C|truth valid	32
H|P1 lexers disagree	4
H|annot|compared	67
H|annot|refuses	4
H|files	71
H|ktLex|P1 refuses-valid	4
H|ktLex|P3 mismatch	1
H|ktLex|compared	63
H|ktLex|refuses	8
H|kts|P1 refuses-valid	4
H|kts|compared	63
H|kts|refuses	8
H|truth invalid	4
H|truth valid	67
M|annot|compared	12
M|files	12
M|ktLex|compared	12
M|kts|compared	12
M|truth valid	12
R|annot|compared	2051
R|files	2051
R|ktLex|compared	2051
R|kts|compared	2051
R|truth valid	2051
numeric literals split by the ktLex digit rule: 9
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:60
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:67
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:74
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:81
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:108
  split R:thinking_app/app/src/test/java/com/softman/thinking/testing/TypeScalePolicyTest.kt:605
  split C:numbers:1:1e-5
  split C:numbers:1:.5
  split M:numbers:1:1e-5
control b (flipped annot classes): ok (flipped classes MISMATCH) on annot/testdata/conformance/kotlin/backtick_names.kt.in
control e (mapper self-test): match=12 mismatch=0
````

KtFamily on `ctl` (3d1a2b628):

````text
lexer=2.3.20 dump=dump_ctl.tsv
MAPPER MATCH    annotation_call  want=[o:@ n:Ann o:( d:1 o:) n:val n:v] real=[o:@ n:Ann o:( d:1 o:) n:val n:v] ktLex=[o:@ n:Ann o:( d:1 o:) n:val n:v]
MAPPER MATCH    as_safe          want=[n:a n:as o:? n:B] real=[n:a n:as o:? n:B] ktLex=[n:a n:as o:? n:B]
MAPPER MATCH    class_ref        want=[n:x o::: n:class o:. n:java] real=[n:x o::: n:class o:. n:java] ktLex=[n:x o::: n:class o:. n:java]
MAPPER MISMATCH escaped_keyword  want=[n:in`] real=[n:in`] ktLex=[n:in]
MAPPER MATCH    label_return     want=[n:return o:@ n:forEach] real=[n:return o:@ n:forEach] ktLex=[n:return o:@ n:forEach]
MAPPER MATCH    label_this       want=[n:this o:@ n:Outer] real=[n:this o:@ n:Outer] ktLex=[n:this o:@ n:Outer]
MAPPER MATCH    lambda_arrow     want=[n:f o:{ n:a o:- o:> n:b o:}] real=[n:f o:{ n:a o:- o:> n:b o:}] ktLex=[n:f o:{ n:a o:- o:> n:b o:}]
MAPPER MATCH    not_in           want=[n:a o:! n:in n:b] real=[n:a o:! n:in n:b] ktLex=[n:a o:! n:in n:b]
MAPPER MATCH    not_is           want=[n:a o:! n:is n:B] real=[n:a o:! n:is n:B] ktLex=[n:a o:! n:is n:B]
MAPPER MATCH    numbers          want=[d:1.5f d:0x1F d:1e o:- d:5] real=[d:1.5f d:0x1F d:1e o:- d:5] ktLex=[d:1.5f d:0x1F d:1e o:- d:5]
MAPPER MATCH    range_until      want=[d:0 o:. o:. o:< n:n] real=[d:0 o:. o:. o:< n:n] ktLex=[d:0 o:. o:. o:< n:n]
MAPPER MATCH    safe_elvis_bang  want=[n:a o:? o:. n:b o:? o:: n:c o:! o:!] real=[n:a o:? o:. n:b o:? o:: n:c o:! o:!] ktLex=[n:a o:? o:. n:b o:? o:: n:c o:! o:!]

MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in annot P2 line 6 routed=true got=.....ooo..oo want=........oo..
MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in annot P3 line 6 routed=true anchors package=1 import=0 want package=1 import=0 got=cc#ccLcL#cLL want=cc#cc#ccLLc#
MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in annot P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in kts P1 refuses-valid routed=false
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in annot P3 line 4 routed=true anchors package=1 import=0 want package=1 import=0 got=cccccc#c want=cccLLc#c
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in annot P2 line 4 routed=true got=...ooooo.. want=....oo.o..
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in annot P3 line 4 routed=true anchors package=1 import=0 want package=1 import=0 got=cccLccLc#c want=ccccLLcL#c
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/script.kts.in ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@3:println o@3:( s@3:hi o@3:)]
MISMATCH C crlf ktLex P3 line 1 routed=true got=[n@1:r o@1:= s@1:\r\n//\sin\sraw\r\n n@5:val n@5:probe o@5:=] want=[n@1:r o@1:= s@1:\n//\sin\sraw\n n@5:val n@5:probe o@5:=]
MISMATCH C invalid_backslash_in_code annot P1 accepts-invalid (BAD_CHARACTER@1:\) routed=true
MISMATCH C invalid_backslash_in_code ktLex P1 accepts-invalid (BAD_CHARACTER@1:\) routed=true
PAIR     C invalid_backslash_in_code P1 refuses annot=false ktLex=false kts=true (truth invalid:BAD_CHARACTER@1:\)
MISMATCH C invalid_backslash_newline_in_string ktLex P1 accepts-invalid (uncertain@1) routed=true
MISMATCH C invalid_backslash_newline_in_string kts P1 accepts-invalid (uncertain@1) routed=true
PAIR     C invalid_backslash_newline_in_string P1 refuses annot=true ktLex=false kts=false (truth invalid:uncertain@1)
MISMATCH C invalid_unclosed_backtick annot P1 accepts-invalid (BAD_CHARACTER@1:`) routed=true
PAIR     C invalid_unclosed_backtick P1 refuses annot=false ktLex=true kts=true (truth invalid:BAD_CHARACTER@1:`)
MISMATCH C invalid_unclosed_char annot P1 accepts-invalid (malformed CHARACTER_LITERAL@1) routed=true
PAIR     C invalid_unclosed_char P1 refuses annot=false ktLex=true kts=true (truth invalid:malformed CHARACTER_LITERAL@1)
MISMATCH C multidollar_in_template ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_in_template kts P1 refuses-valid routed=true
PAIR     C multidollar_in_template P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C multidollar_plain ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_plain kts P1 refuses-valid routed=true
PAIR     C multidollar_plain P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C multidollar_raw_desync annot P1 refuses-valid routed=true
MISMATCH C multidollar_raw_desync ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_raw_desync kts P1 refuses-valid routed=true
MISMATCH C shebang_brace annot P3 line 0 routed=true anchors package=0 import=0 want package=2 import=0 got=ccc#c want=ccc#c
MISMATCH C shebang_brace ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@2:package n@2:p n@3:class n@3:Actual]
MISMATCH C shebang_paren ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@2:package n@2:p n@3:class n@3:Actual]
MISMATCH C shebang_plain ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@3:val n@3:probe o@3:= d@3:1]
MISMATCH C shebang_slash_star annot P1 refuses-valid routed=true
MISMATCH C shebang_slash_star ktLex P1 refuses-valid routed=true
PAIR     C shebang_slash_star P1 refuses annot=true ktLex=true kts=false (truth valid)
MISMATCH C short_template_backticked annot P1 refuses-valid routed=true
MISMATCH C short_template_backticked ktLex P1 refuses-valid routed=true
MISMATCH C short_template_backticked kts P1 refuses-valid routed=true
MISMATCH C short_template_backticked_raw ktLex P3 line 1 routed=true got=[n@1:r o@1:= s@1:$`c//d` n@3:val n@3:probe o@3:=] want=[n@1:r o@1:= n@1:c//d S@1: n@3:val n@3:probe]
MISMATCH C single_dollar_prefix ktLex P1 refuses-valid routed=true
MISMATCH C single_dollar_prefix kts P1 refuses-valid routed=true
PAIR     C single_dollar_prefix P1 refuses annot=false ktLex=true kts=true (truth valid)

== counts
C|P1 lexers disagree	8
C|annot|P1 accepts-invalid	3
C|annot|P1 refuses-valid	3
C|annot|P3 mismatch	1
C|annot|compared	29
C|annot|refuses	8
C|files	40
C|ktLex|P1 accepts-invalid	2
C|ktLex|P1 refuses-valid	6
C|ktLex|P3 mismatch	5
C|ktLex|compared	26
C|ktLex|esc not compared	26
C|ktLex|refuses	12
C|kts|P1 accepts-invalid	1
C|kts|P1 refuses-valid	5
C|kts|compared	27
C|kts|refuses	12
C|truth invalid	8
C|truth valid	32
H|P1 lexers disagree	3
H|annot|P1 refuses-valid	1
H|annot|P2 mismatch	2
H|annot|P3 mismatch	3
H|annot|compared	66
H|annot|refuses	5
H|files	71
H|ktLex|P1 refuses-valid	4
H|ktLex|P3 mismatch	1
H|ktLex|compared	63
H|ktLex|esc not compared	62
H|ktLex|refuses	8
H|kts|P1 refuses-valid	4
H|kts|compared	63
H|kts|refuses	8
H|truth invalid	4
H|truth valid	67
M|annot|compared	12
M|files	12
M|ktLex|compared	12
M|ktLex|esc not compared	12
M|kts|compared	12
M|truth valid	12
R|annot|compared	2051
R|files	2051
R|ktLex|compared	2051
R|ktLex|esc not compared	2051
R|kts|compared	2051
R|truth valid	2051
numeric literals split by the ktLex digit rule: 9
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:60
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:67
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:74
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:81
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:108
  split R:thinking_app/app/src/test/java/com/softman/thinking/testing/TypeScalePolicyTest.kt:605
  split C:numbers:1:1e-5
  split C:numbers:1:.5
  split M:numbers:1:1e-5
control b (flipped annot classes): ok (flipped classes MISMATCH) on annot/testdata/conformance/kotlin/backtick_names.kt.in
control e (mapper self-test): match=11 mismatch=1
````

KtFamily on `mid` (cf210a9e9):

````text
lexer=2.3.20 dump=dump_mid.tsv
MAPPER MATCH    annotation_call  want=[o:@ n:Ann o:( d:1 o:) n:val n:v] real=[o:@ n:Ann o:( d:1 o:) n:val n:v] ktLex=[o:@ n:Ann o:( d:1 o:) n:val n:v]
MAPPER MATCH    as_safe          want=[n:a n:as o:? n:B] real=[n:a n:as o:? n:B] ktLex=[n:a n:as o:? n:B]
MAPPER MATCH    class_ref        want=[n:x o::: n:class o:. n:java] real=[n:x o::: n:class o:. n:java] ktLex=[n:x o::: n:class o:. n:java]
MAPPER MISMATCH escaped_keyword  want=[n:in`] real=[n:in`] ktLex=[n:in]
MAPPER MATCH    label_return     want=[n:return o:@ n:forEach] real=[n:return o:@ n:forEach] ktLex=[n:return o:@ n:forEach]
MAPPER MATCH    label_this       want=[n:this o:@ n:Outer] real=[n:this o:@ n:Outer] ktLex=[n:this o:@ n:Outer]
MAPPER MATCH    lambda_arrow     want=[n:f o:{ n:a o:- o:> n:b o:}] real=[n:f o:{ n:a o:- o:> n:b o:}] ktLex=[n:f o:{ n:a o:- o:> n:b o:}]
MAPPER MATCH    not_in           want=[n:a o:! n:in n:b] real=[n:a o:! n:in n:b] ktLex=[n:a o:! n:in n:b]
MAPPER MATCH    not_is           want=[n:a o:! n:is n:B] real=[n:a o:! n:is n:B] ktLex=[n:a o:! n:is n:B]
MAPPER MATCH    numbers          want=[d:1.5f d:0x1F d:1e o:- d:5] real=[d:1.5f d:0x1F d:1e o:- d:5] ktLex=[d:1.5f d:0x1F d:1e o:- d:5]
MAPPER MATCH    range_until      want=[d:0 o:. o:. o:< n:n] real=[d:0 o:. o:. o:< n:n] ktLex=[d:0 o:. o:. o:< n:n]
MAPPER MATCH    safe_elvis_bang  want=[n:a o:? o:. n:b o:? o:: n:c o:! o:!] real=[n:a o:? o:. n:b o:? o:: n:c o:! o:!] ktLex=[n:a o:? o:. n:b o:? o:: n:c o:! o:!]

MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_literal_brace.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in ktLex P1 refuses-valid routed=true
MISMATCH H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in kts P1 refuses-valid routed=false
PAIR     H annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH H annot/testdata/conformance/kotlin/script.kts.in ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@3:println o@3:( s@3:hi o@3:)]
MISMATCH C crlf ktLex P3 line 1 routed=true got=[n@1:r o@1:= s@1:\r\n//\sin\sraw\r\n n@5:val n@5:probe o@5:=] want=[n@1:r o@1:= s@1:\n//\sin\sraw\n n@5:val n@5:probe o@5:=]
MISMATCH C invalid_backslash_in_code annot P1 accepts-invalid (BAD_CHARACTER@1:\) routed=true
MISMATCH C invalid_backslash_in_code ktLex P1 accepts-invalid (BAD_CHARACTER@1:\) routed=true
PAIR     C invalid_backslash_in_code P1 refuses annot=false ktLex=false kts=true (truth invalid:BAD_CHARACTER@1:\)
MISMATCH C invalid_backslash_newline_in_string ktLex P1 accepts-invalid (uncertain@1) routed=true
MISMATCH C invalid_backslash_newline_in_string kts P1 accepts-invalid (uncertain@1) routed=true
PAIR     C invalid_backslash_newline_in_string P1 refuses annot=true ktLex=false kts=false (truth invalid:uncertain@1)
MISMATCH C invalid_unclosed_backtick annot P1 accepts-invalid (BAD_CHARACTER@1:`) routed=true
PAIR     C invalid_unclosed_backtick P1 refuses annot=false ktLex=true kts=true (truth invalid:BAD_CHARACTER@1:`)
MISMATCH C invalid_unclosed_char annot P1 accepts-invalid (malformed CHARACTER_LITERAL@1) routed=true
PAIR     C invalid_unclosed_char P1 refuses annot=false ktLex=true kts=true (truth invalid:malformed CHARACTER_LITERAL@1)
MISMATCH C multidollar_in_template ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_in_template kts P1 refuses-valid routed=true
PAIR     C multidollar_in_template P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C multidollar_plain ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_plain kts P1 refuses-valid routed=true
PAIR     C multidollar_plain P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C multidollar_raw_desync ktLex P1 refuses-valid routed=true
MISMATCH C multidollar_raw_desync kts P1 refuses-valid routed=true
PAIR     C multidollar_raw_desync P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C shebang_brace annot P3 line 0 routed=true anchors package=0 import=0 want package=2 import=0 got=ccc#c want=ccc#c
MISMATCH C shebang_brace ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@2:package n@2:p n@3:class n@3:Actual]
MISMATCH C shebang_paren ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@2:package n@2:p n@3:class n@3:Actual]
MISMATCH C shebang_plain ktLex P3 line 1 routed=true got=[o@1:# o@1:! o@1:/ n@1:usr] want=[n@3:val n@3:probe o@3:= d@3:1]
MISMATCH C shebang_slash_star annot P1 refuses-valid routed=true
MISMATCH C shebang_slash_star ktLex P1 refuses-valid routed=true
PAIR     C shebang_slash_star P1 refuses annot=true ktLex=true kts=false (truth valid)
MISMATCH C short_template_backticked ktLex P1 refuses-valid routed=true
MISMATCH C short_template_backticked kts P1 refuses-valid routed=true
PAIR     C short_template_backticked P1 refuses annot=false ktLex=true kts=true (truth valid)
MISMATCH C short_template_backticked_raw ktLex P3 line 1 routed=true got=[n@1:r o@1:= s@1:$`c//d` n@3:val n@3:probe o@3:=] want=[n@1:r o@1:= n@1:c//d S@1: n@3:val n@3:probe]
MISMATCH C single_dollar_prefix ktLex P1 refuses-valid routed=true
MISMATCH C single_dollar_prefix kts P1 refuses-valid routed=true
PAIR     C single_dollar_prefix P1 refuses annot=false ktLex=true kts=true (truth valid)

== counts
C|P1 lexers disagree	10
C|annot|P1 accepts-invalid	3
C|annot|P1 refuses-valid	1
C|annot|P3 mismatch	1
C|annot|compared	31
C|annot|refuses	6
C|files	40
C|ktLex|P1 accepts-invalid	2
C|ktLex|P1 refuses-valid	6
C|ktLex|P3 mismatch	5
C|ktLex|compared	26
C|ktLex|esc not compared	26
C|ktLex|refuses	12
C|kts|P1 accepts-invalid	1
C|kts|P1 refuses-valid	5
C|kts|compared	27
C|kts|refuses	12
C|truth invalid	8
C|truth valid	32
H|P1 lexers disagree	4
H|annot|compared	67
H|annot|refuses	4
H|files	71
H|ktLex|P1 refuses-valid	4
H|ktLex|P3 mismatch	1
H|ktLex|compared	63
H|ktLex|esc not compared	62
H|ktLex|refuses	8
H|kts|P1 refuses-valid	4
H|kts|compared	63
H|kts|refuses	8
H|truth invalid	4
H|truth valid	67
M|annot|compared	12
M|files	12
M|ktLex|compared	12
M|ktLex|esc not compared	12
M|kts|compared	12
M|truth valid	12
R|annot|compared	2051
R|files	2051
R|ktLex|compared	2051
R|ktLex|esc not compared	2051
R|kts|compared	2051
R|truth valid	2051
numeric literals split by the ktLex digit rule: 9
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:60
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:67
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:74
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:81
  split R:aitasks_mobile/shared/src/commonTest/kotlin/com/beyondeye/aitmobile/monitor/ZoomGestureDecideTest.kt:108
  split R:thinking_app/app/src/test/java/com/softman/thinking/testing/TypeScalePolicyTest.kt:605
  split C:numbers:1:1e-5
  split C:numbers:1:.5
  split M:numbers:1:1e-5
control b (flipped annot classes): ok (flipped classes MISMATCH) on annot/testdata/conformance/kotlin/backtick_names.kt.in
control e (mapper self-test): match=11 mismatch=1
````

control c: KtAdapter on the 20 TestClassifyKotlin rows:

````text
MATCH    plain                              got classes cc#c           want classes cc#c
MATCH    raw                                got classes cLLL#          want classes cLLL#
MATCH    block-nested                       got classes cLL#           want classes cLL#
MATCH    slashes-in-string                  got classes c#             want classes c#
MATCH    template-string                    got classes c#             want classes c#
MATCH    unterminated-raw                   got uncertain line 1       want uncertain line 1
MATCH    bom-comment                        got classes #c             want classes #c
MATCH    multidollar-comment-desync         got classes cc#cc#ccLLc#   want classes cc#cc#ccLLc#
MATCH    multidollar-interpolation          got classes ccccc#c        want classes ccccc#c
MATCH    multidollar-literal-brace          got classes cccLLc#c       want classes cccLLc#c
MATCH    multidollar-quote-boundary         got classes ccccLLcL#c     want classes ccccLLcL#c
MATCH    dollar-prefix-3                    got classes c#             want classes c#
MATCH    dollar-run-longer                  got classes cLL#           want classes cLL#
MATCH    dollar-run-before-close            got classes c#             want classes c#
MATCH    dollar-inside-template             got classes c#             want classes c#
MATCH    dollar-prefix-restored             got classes c#             want classes c#
MATCH    short-template-backticks           got classes c#             want classes c#
MATCH    short-template-backticks-dollar    got classes c#             want classes c#
MATCH    short-template-below-prefix        got classes c#             want classes c#
MATCH    short-template-unclosed-backtick   got classes c#             want classes c#
TOTAL match=20 mismatch=0 lexer=2.3.20
````

control d: check_opneg.py:

````text
records=2174 eligible=570 detected=570
  eligible in C: 1
  eligible in M: 1
  eligible in R: 568
operator row eligible: True
FAILURES: 0
````

Step 6.3: embedding check:

````text
EMBED: byte-identical (40 rows)
````

Step 7: negctl.sh:

````text
== control a: annot ignores the interpolation prefix (dollars forced to 1)
--- FAIL: TestKotlinFamilyConstructs (0.00s)
    kotlinfamily_test.go:458: multidollar_raw_desync: annot refuses the file, want modelled
--- FAIL: TestKotlinFamilyCorpus (0.00s)
    kotlinfamily_test.go:559: ../annot/testdata/conformance/kotlin/multidollar_comment_desync.kt.in: the Kotlin-family lexers now read annot=.....ooo..oo ktLex=refuses kts=refuses, pinned annot=........oo.. ktLex=refuses kts=refus
    kotlinfamily_test.go:557: ../annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in: the Kotlin-family lexers now agree (annot=refuses ktLex=refuses kts=refuses); drop its kotlinFamilyCorpusKnown pin (t1992)
    kotlinfamily_test.go:559: ../annot/testdata/conformance/kotlin/multidollar_quote_boundary.kt.in: the Kotlin-family lexers now read annot=...ooooo.. ktLex=refuses kts=refuses, pinned annot=....oo.o.. ktLex=refuses kts=refuses (
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/deps	0.004s
FAIL
== control b: ktLex block comments do not nest
--- FAIL: TestKotlinFamilyConstructs (0.00s)
    kotlinfamily_test.go:458: doc_comment: ktLex line-start view ".o...", want modelled: ".oo.."
    kotlinfamily_test.go:458: nested_block_comment: ktLex line-start view ".....", want modelled: ".oo.."
--- FAIL: TestKotlinFamilyCorpus (0.00s)
    kotlinfamily_test.go:553: ../annot/testdata/conformance/kotlin/lex_block_nested.kt.in: the Kotlin-family lexers disagree: annot=.oo. ktLex=.... kts=.oo.
    kotlinfamily_test.go:553: ../annot/testdata/conformance/kotlin/lookalikes.kt.in: the Kotlin-family lexers disagree: annot=..ooo.oo. ktLex=..ooo.... kts=..ooo.oo.
    kotlinfamily_test.go:553: ../annot/testdata/conformance/kotlin/malformed_unterminated_block.kt.in: the Kotlin-family lexers disagree: annot=refuses ktLex=... kts=refuses
    kotlinfamily_test.go:553: ../annot/testdata/conformance/kotlin/nested_comments.kt.in: the Kotlin-family lexers disagree: annot=.ooo..oooo. ktLex=.ooo..oo... kts=.ooo..oooo.
    kotlinfamily_test.go:553: ../annot/testdata/parse/lookalikes.kt.in: the Kotlin-family lexers disagree: annot=..ooo.oo. ktLex=..ooo.... kts=..ooo.oo.
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/deps	0.004s
FAIL
== control c: ktLex emits :: as two : tokens
--- FAIL: TestKotlinFamilyConstructs (0.00s)
    kotlinfamily_test.go:458: operators: ktLex "o@1:@ n@1:file o@1:: n@1:JvmName o@1:( s@1:X o@1:) n@2:package n@2:p o@2:. n@2:q n@4:import n@4:a o@4:. n@4:b o@4:. n@4:C n@4:as n@4:D o@6:@ n@6:Ann o@6:( n@6:x o@6:) n@6:class n@6:B
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/deps	0.004s
FAIL
== control d: one kotlinFamilyCorpusKnown entry deleted
--- FAIL: TestKotlinFamilyCorpus (0.00s)
    kotlinfamily_test.go:552: ../annot/testdata/conformance/kotlin/multidollar_interpolation.kt.in: the Kotlin-family lexers disagree: annot=....... ktLex=refuses kts=refuses
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/deps	0.004s
FAIL
== control e: a bogus kotlinFamilyCorpusKnown entry added
--- FAIL: TestKotlinFamilyCorpus (0.00s)
    kotlinfamily_test.go:567: testdata/no/such.kt.in: pinned in kotlinFamilyCorpusKnown, but no such fixture; drop the pin (t1992)
FAIL
FAIL	github.com/beyondeye/aitasks/goengines/internal/testmap/deps	0.004s
FAIL
````

## Post-Review Changes

### Change Request 1 (2026-10-16 01:30)
- **Requested by user:** verify and, if valid, address a blocking review finding. The record called the shebang gap "safe direction". A counterexample, `#!/usr/bin/env -S kotlin -J-Dtag={` + `package p` + `class Actual`, is valid per the oracle, yet `scanKotlin` returns no package, no declarations, no opaque reason and no error. Add the variant to the construct table, correct the safety assessment and the decision rationale, and create the Step-4 upstream-defect task.
- **Changes made:**
  - Verified the finding through the real `scanKotlin`. It is wider than reported: a `(` in the shebang hides every declaration too (the `parens == 0` gate, `kotlin.go:175`). annot loses its `Package` anchor on the `{` variant (placement still valid).
  - Added the construct rows `shebang_brace` and `shebang_paren`.
  - Added annot's `Package`/`Import` anchors to its projection (dump fields, `KtFamily.anchors()`, `familyAnnot`). On all 2051 real files and the 71 fixtures they match the oracle.
  - Re-ran all four dumps, the oracle, controls a–e, the embedding check and the negative controls.
  - Regenerated the table (40 rows).
  - Created **t2030** `kotlin_shebang_line_hides_deps`.
  - Corrected the decision record: the shebang row, C1 (now an unsafe drift, with the correction stated), the decision rationale (still no core, argued as a closer call), the tightened revisit trigger, and the consequences.
- **Files affected:**
  - `goengines/internal/testmap/deps/kotlinfamily_test.go`;
  - this plan;
  - `aitasks/t2030_kotlin_shebang_line_hides_deps.md` (created and committed by `aitask_create.sh --commit`).

## Final Implementation Notes
- **Actual work done:**
  - **Measurement.** The three Kotlin-family lexers were measured against the real `KotlinLexer` (kotlin-compiler-embeddable 2.3.20), as planned. Inputs: 4 snapshots (HEAD, `3d1a2b628`, `cf210a9e9`, and the `::`-split mutant); 71 hermetic fixtures, 2051 real `.kt`/`.kts` files from the 8 registered repositories at recorded commits, 40 construct rows and 12 mapper self-test rows. The projections were acceptance, the line-start view, and each consumer's projection.
  - **Decision: no shared lexical core.** The decision record above holds C1–C6 and the argument.
  - **Safeguard landed:** `goengines/internal/testmap/deps/kotlinfamily_test.go`:
    - `TestKotlinFamilyConstructs`: 40 rows pinned to the real lexer;
    - `TestKotlinFamilyCorpus`: the three lexers must agree on every Kotlin fixture under `deps/testdata` and `annot/testdata`, with 4 exact multi-dollar pins, a stale-pin check and a floor of 71.
  - Three one-sentence pointer comments (`kotlinlex.go`, `gradlelex.go`, `annot/lexctx.go`); no behaviour change, no `schemaVersion` bump.
  - Created **t2030** for the unsafe shebang drift.
- **Deviations from plan:** The six recorded under "Deviations from the plan" in the evidence section:
  1. the oracle LF-normalises CRLF;
  2. char-literal shape is part of validity;
  3. the `` $`name` `` row was split into plain and raw forms;
  4. control 7a forces the interpolation prefix to 1;
  5. the empty-source guard in `adapt()`;
  6. the review-driven shebang rows plus annot anchors added to its projection.

  Real-repository snapshots were extracted from each commit's `ls-tree` list, because the planned `':(glob)**/*.kts'` pathspec aborts `git archive` in repositories without `.kts` files.
- **Issues encountered:**
  - The raw IntelliJ `KotlinLexer` reads `\r` as BAD_CHARACTER (fixed by normalisation).
  - The real lexer emits `'ab` as one CHARACTER_LITERAL token, so lexer acceptance is not validity.
  - A combined construct row masked one form's silent misread behind the other form's refusal (fixed by splitting it).
  - Plan review (Step 8, Change Request 1) caught a wrong safety claim: the shebang was recorded as "safe direction" without tracing `{`/`(` through `scanKotlin`'s depth and paren gates. It was corrected, measured and filed (t2030).
- **Key decisions:**
  - The safeguard lives in package `deps`, the only package that sees all three lexers; `deps` already imports `annot`.
  - The kts projection is pinned as the real lexer's comment byte ranges, not as whole blanked copies.
  - annot's projection includes the `Package`/`Import` anchors its placement reads.
  - The durable corpus differential compares P1/P2 only; the construct rows carry P3.
  - Numeric literals are compared after ktLex's digit rule, and the split class is reported separately (9 literals; no consumer reads a `d` token).
  - Validity is lexer-level only.
- **Upstream defects identified:**
  - `goengines/internal/testmap/deps/kotlinlex.go:50 — ktLex code() lexes a leading #! shebang line as code: a { in it hides the package clause and every declaration from scanKotlin (kotlin.go:175 depth/parens gate), a ( hides every declaration, silently (filed as t2030)`
  - `goengines/internal/testmap/annot/lexctx.go:790 — classifyKotlin lexes a leading #! shebang line as code: a { hides the Package/Import anchors (placement lands after the shebang), a /* makes the file Uncertain, a whole-scan SyntaxError (covered by t2030)`
  - `goengines/internal/testmap/deps/kotlinlex.go:269 — ktLex keeps the \r of CRLF line separators in raw-string s-token content, while kotlinc normalises them; harmless today (only .localized keys read s content), zero CR files in the registered repositories`
