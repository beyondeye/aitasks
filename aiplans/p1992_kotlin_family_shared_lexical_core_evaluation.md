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
