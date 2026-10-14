---
Task: t1975_gradle_comment_strip_ignores_string_literals.md
Base branch: main
Output branch: main
---

# t1975: string-aware comment blanking in the Gradle scanner

## Context

`scanGradle` (`goengines/internal/testmap/deps/gradle.go:39,54`) blanks comments
with the regex `(?m)//[^\n]*$|/\*(?s:.*?)\*/` before it reads `include`,
`project(...)`, `projectDir` and accessors. The regex does not know about string
literals:

- A `/*` inside a quoted glob (`'/META-INF/*'`, `'*/*_REVIEW.md'`) opens a fake
  block comment that runs to the next `*/` anywhere later in the file.
- A `//` inside a URL string erases the rest of its line.

The result is one of two things:

- A silently dropped `project(':lib')` dependency (under-selection, no Problem).
- In thinking_app's `app/build.gradle:920-921`, a leftover `include '*` that is
  read as a dynamic include. This marks the file `gradle-dynamic` and widens
  `:app`'s deps to `[":"]`.

**Design constraint (from review).** A wrong string boundary does not just make a
string longer. It can flip quote parity, so a later string's contents are read as
code and its `/*` or `//` erases real code with no diagnostic. So:

- Every string form a dialect has must be modelled with that dialect's own escape
  rules. Groovy and Kotlin differ:
  - Kotlin `"""` raw strings have no escapes.
  - Groovy has slashy (`/…/`) and dollar-slashy (`$/…/$`) strings.
- A form that is not modelled must fail visibly, not silently.

Today `kindOf` maps `.gradle` and `.gradle.kts` to the same kind, so the scanner
has no dialect. The kind therefore splits. The cache key is blob + kind, so this
is safe.

**Secondary issue.** `includeRe` also runs on build files, where `include` is a
`fileTree` / `copy` / test-filter pattern (`PatternFilterable`) and never a module.
A GString argument there makes the module dynamic.

**Decision: build files do not take part in `include` parsing.**

- Raw extraction is path-independent, so this filter goes in the resolve step
  (`buildGradle`).
- Settings files keep the current behaviour.

Mode: current branch (`main`), profile `fast`.

## Implementation (test-first)

### 1. Pin a baseline before touching `gradle.go` (temporary, never committed)

- Snapshot every `*.gradle` / `*.gradle.kts` blob at `HEAD` of the registered repos
  that have any: thinking_app 4, aitasks_mobile 8, timexchange 13, teamim 4.
  - Copy each with `git -C <repo> show HEAD:<path>` into
    `$SCRATCH/t1975/corpus/<repo>/<path>`.
  - This only reads those repos.
  - The pinned bytes keep live edits in those checkouts from skewing the
    comparison.
- Write the temporary probe `goengines/internal/testmap/deps/probe_t1975_test.go`
  (package `deps`):
  - It calls `t.Skip` unless `AIT_T1975_CORPUS` and `AIT_T1975_OUT` are set.
  - It dumps `scanRaw(kindOf(path, nil), data).Gradle` per file as one JSON map.
  - It goes through `kindOf` so the dialect routing is exercised.
- Run it on the unmodified code → `$SCRATCH/t1975/before.json`.

### 2. Add the tests first, and record the red run

The tests go in a **new file**, `goengines/internal/testmap/deps/gradle_test.go`,
not in `kotlin_test.go` next to the existing Gradle tests.

- `kotlin_test.go` is edited by sibling sessions in this shared checkout: t1976
  has landed, and t1977 is still in flight.
- A path-scoped commit takes the whole file, so committing `kotlin_test.go` would
  sweep in a sibling's uncommitted hunks.
- The existing `TestGradle*` tests stay where they are.

Reuse `repo`, `scanRepo`, `lines`, `requireEdge` and `requireNoEdge`
(`helpers_test.go`).

**`TestGradleCommentInString`** (repo-level). The task's reproducing fixture,
verbatim:

- Assert `:app` deps `[":lib"]` and no problems.
- Assert `requireEdge(A.kt → lib/build.gradle, module-build)`.
- Add a second module, `kts/build.gradle.kts`, containing
  `val p = """C:\"""`, then `dependencies { implementation(project(":lib")) }`,
  then `val g = """src/**/*.kt"""`.
  - Assert its deps are `[":lib"]` and it is not opaque.
  - This proves that `kindOf` routes `.gradle.kts` to the Kotlin dialect
    end to end.

**`TestScanGradleStringAwareComments`** (table over `scanGradle([]byte(src), kts).Gradle`).
Each case states the expected `ProjectRefs` names, the expected `Includes` where
they matter, and the expected `Dynamic` names. Cases are Groovy unless marked kts.

1. Quoted globs:
   - `/*` in a single-quoted glob hiding `project(':lib')`.
   - A double-quoted variant.
   - A kts variant (`"src/**/*.kt"` … `implementation(project(":lib"))` … `"*/x"`).
2. `//` in a URL on the same line:
   `repositories { maven { url 'https://jitpack.io' } }; dependencies { implementation project(':lib') }`.
3. thinking_app's glob pair, copied from `app/build.gradle:919-922`:
   - `Includes` holds both literal patterns, and `Dynamic` is empty.
   - This case pins step 3 on its own, independent of step 4.
4. Real comments still blank:
   - `/* implementation project(':gone') */`
   - `// implementation project(':gone2')`
   - apostrophes inside comments: `// don't project(':gone3')` and
     `/* it's */ implementation project(':kept')`
   - expected refs: `[":kept"]`
   - This is a regression guard.
5. Groovy escape: `'it\'s /*'`, then `project(':lib')`, then a later `'*/x'` →
   `[":lib"]`.
6. Template with a nested string:
   `implementation "${a.replace("//", "/")}"; implementation project(':lib')` →
   `[":lib"]`.
7. Triple-quoted strings across lines:
   - `"""a /* b\n c"""` and a `'''…'''` variant, then `project(':lib')` on line 3.
   - Expect `[":lib"]` with `Line == 3` (offsets are kept).
8. **Dollar-slashy** (the reviewer's regression):
   - Source: `def a = $/META-INF/*/$`, then `dependencies { implementation project(':lib') }`,
     then `def b = $/*/x/$`.
   - Expect `[":lib"]` and no Dynamic.
   - Escape variant: `def c = $/a$/$/$`, where `$/$` is an escape, followed on
     the same line by `; def u = 'https://x'; implementation project(':lib')` →
     `[":lib"]`.
9. **Plain slashy** with an escaped slash:
   - Source: `def r = /META-INF\/*/`, then `project(':lib')`, then `def q = /x*/`.
   - A quote inside a slashy string on the same line as a URL, in each start
     context:
     - `def r = ~/it's/; …`
     - **`def label = 'prefix' + /it's/; …`** (the reviewer's regression)
     - `… - /it's/; …`
     - `if (v in /it's/) {}; …`

     Each is followed on the same line by
     `def u = 'https://x'; dependencies { implementation project(':lib') }`.
   - Every variant must give `[":lib"]` and no Dynamic.
10. Division is not slashy:
    - `def n = total / 2 // it's half`
    - `def k = i++ / 2 // it's`
    - `def j = i-- / 2 // it's`
    - `def m = (a) / b // it's`

    Each gives no Dynamic, and its comment is blanked: a `project(':gone')` in the
    comment does not appear in the refs.
10a. **A significant newline opens a slashy string** (the reviewer's
     regression). Each of these must give `[":lib"]` and no Dynamic:
     - `def n = 1`, then on the next line
       `/it's/.each { println it }; def u = 'https://x'; dependencies { implementation project(':lib') }`;
     - the same with the first line ending in a `// comment`;
     - the same inside a `{ … }` block;
     - `try (def r = 1`, then on the next line
       `/it's/.size()) {}; def u = 'https://x'; implementation project(':lib')`.
       A `(` after `try` does not hide newlines.
10b. **A hidden newline keeps division.** These are continuation guards against
     resetting on every newline. Each must give refs `[]` and no Dynamic:
     - `def n = foo(1` then `    / 2) // it's project(':gone')`;
     - `def l = [1` then `    / 2] // it's project(':gone')`;
     - `def n = 1 \` then `    / 2 // it's project(':gone')`;
     - `def n = 1 /* c */ / 2 // it's project(':gone')`.
11. Groovy line continuation: `def a = 1 + \` + newline + `2` → no Dynamic. A
    stray backslash in code (`foo \ bar`) → Dynamic `["untokenizable"]`.
12. **kts raw string ending in a backslash**: the `"""C:\"""` sequence from the
    repo-level test → `[":lib"]` and no Dynamic.
13. kts specifics:
    - A nested block comment, `/* a /* b */ implementation(project(":gone")) */`,
      gives refs `[]`.
    - A backticked name containing an apostrophe, `` val `it's` = 1 `` followed
      by `implementation(project(":lib"))`, gives `[":lib"]`.
    - Char literals `'"'` and `'/'` do not open strings or comments.
    - **Multi-dollar strings** (the reviewer's regression):
      - Source: `val a = $$"""${/*}"""`, then
        `dependencies { implementation(project(":lib")) }`, then
        `val b = """*/}"""`.
      - Dynamic is `["untokenizable"]`. Nothing is blanked, so the refs still
        include `":lib"`.
      - A single-line `val j = $$"{x}"` variant also gives `untokenizable`.
      - At repo level (in `TestGradleCommentInString`'s kts module set), such a
        file is `gradle-dynamic`, and its deps widen to every module.
14. Unclosed constructs, each giving Dynamic `["untokenizable"]` and *nothing
    blanked*:
    - `/* never closed`
    - a single-line `'oops` + newline
    - `$/never closed`
    - Also assert that a `// project(':c')` before the failure point is still
      read (refs include `:c`).

**`TestGradleBuildFileIncludeIsNotModule`** (repo-level). The include sits on its
own line, so the line-anchored `includeRe` matches it:

- `settings.gradle`: `include ':app', ':lib'` plus a line `include "${extra}"`.
- `app/build.gradle`:
  ```groovy
  copy {
      include "${dir}/*.md"
  }
  dependencies { implementation project(':lib') }
  ```
- Assert `:app` deps `[":lib"]` and `g.Opaque("app/build.gradle") == ""`.
- Assert `settings.gradle` is still `gradle-dynamic`, with a
  `gradle-dynamic: include` problem.

**Red runs.** From `goengines/`, run
`go test ./internal/testmap/deps -run 'Gradle' -count=1`:

- **Before step 3.**
  - Expected red: `TestGradleCommentInString`, table cases 1-3, 5-9, 10a and
    11-14, and the build-file half of `TestGradleBuildFileIncludeIsNotModule`.
    - The table cases do not compile until the `kts` parameter exists. Run the
      red check with a temporary one-line `scanGradle(data, kts)` shim that
      ignores `kts`, or record the red per case with the old signature.
  - Cases 4, 10 and 10b pass. They are guards, and they must still pass after
    step 3. Case 10b is what fails if the lexer resets the flag on every newline.
- **After step 3, before step 4.** Only the build-file half of
  `TestGradleBuildFileIncludeIsNotModule` is still red. That proves the fixture
  pins step 4.

Record both runs in the plan notes.

### 3. Dialect split and a string-aware lexer (`raw.go`, `gradle.go`)

**`raw.go`**

- Add `kindGradleKts = "gradle-kts"`.
- `kindOf`: a `.gradle.kts` suffix → `kindGradleKts`; `.gradle` → `kindGradle`.
- `scanRaw`:
  - `case kindGradle: return scanGradle(data, false)`
  - `case kindGradleKts: return scanGradle(data, true)`

Nothing else switches on these kinds. Resolve keys on `sc.raw.Gradle != nil`.

**`gradle.go`**

Remove `gradleComment`. Add `blankGradleComments(src string, kts bool) (out string, failAt int)`.
It is a small in-place byte lexer modelled on `ktLexer` (`kotlinlex.go`): the same
`code(inTemplate)` / `str` recursion, and the same rule that a run of more than
three quotes closes on its last three. Blanking is per byte, with newlines kept, so
offsets are exact.

Rules:

| construct | Groovy (`.gradle`) | Kotlin (`.gradle.kts`) |
|---|---|---|
| `// …` | to end of line | same |
| `/* … */` | not nested | nested (depth), like `ktLexer.blockComment` |
| `'…'` | string; `\` escapes; single line | char literal; `\` escapes; single line |
| `"…"` | `\` escapes; `${…}` template; single line | same |
| `'''…'''` | `\` escapes; multi-line | not a form (`'` is never triple) |
| `"""…"""` | `\` escapes; `${…}` template; multi-line | **no escapes**; `${…}` template; multi-line |
| `/…/` slashy | when `/` is not `//` or `/*` and the previous code token does **not** end a value (Groovy lexer rule, below). Only `\/` escapes; `${…}` template; multi-line | not a form |
| `$/…/$` dollar-slashy | when `$/` starts a token, which needs no regex predicate (`DollarSlashyGStringQuotationMarkBegin`). Characters are tried in Groovy's order: `$$` → 2 bytes; `$/$` → 3; `$/` → 2; `/$` closes; `${…}` template; anything else → 1. Multi-line | not a form |
| `$…$"…"` / `$…$"""…"""` multi-dollar string | not a form | **fails** (untokenizable) when a run of `$` in code is followed directly by `"`. Interpolation thresholds are not modelled, and precise support is out of scope |
| leading `#!` line(s) | skipped as hidden (`SH_COMMENT`) | skipped (script shebang) |
| identifier bytes | letters, digits, `_`, `$`, and any byte ≥ 0x80 | the same without `$` |
| `` `…` `` | (not code) | backticked name, skipped to the closing backtick on the line |
| `\` in code | allowed only as a line continuation (`\` before the newline); anything else **fails** | always **fails** |

How the table is applied:

- **The table must be exhaustive per dialect.** It lists every lexical form that
  can move a string or comment boundary, each as either *modelled* or *fails*.
  - Groovy (per `GroovyLexer.g4`): `SH_COMMENT`, `SL_COMMENT`, `ML_COMMENT`,
    single, double and triple-quoted strings, slashy and dollar-slashy strings,
    GString templates, and `LineEscape`.
  - Kotlin: shebang, line comments, nested block comments, `"…"`, `"""…"""`,
    multi-dollar prefixes, char literals, backticked names and templates.
  - A form that appears in neither list must not fall through as an ordinary
    byte. If the implementation meets one, it gets a row (model it or fail)
    before it ships.

- **Escapes.** Inside any string with escapes, a `\` skips the next byte. A
  following `\r\n` is skipped as one unit (Groovy's `LineEscape` is part of
  `EscapeSequence`).
- **Runs of quotes.** A triple-quoted string closes on the last three quotes of a
  run of quotes. This matches Groovy's `TdqStringCharacter` / `TsqStringCharacter`
  predicates and `ktLexer.str`.

- **The slashy rule mirrors Groovy's lexer** (`src/antlr/GroovyLexer.g4`, checked
  on apache/groovy master). Groovy allows a regex unless the last
  *default-channel* token is in `REGEX_CHECK_SET`:
  `DEC INC THIS RBRACE RBRACK RPAREN GStringEnd NullLiteral StringLiteral BooleanLiteral IntegerLiteral FloatingPointLiteral Identifier CapitalizedIdentifier`.
  `code()` tracks this as one flag, `afterValue`, which starts `false`.
- **Tokens that set `afterValue`:**
  - an identifier or number word, unless it is a Groovy keyword. The keywords
    form one constant: Groovy 4's keyword tokens, copied from the lexer's keyword
    rules (`as def in trait var val yield record sealed permits`, the Java
    keywords, and the primitive types). `this`, `null`, `true` and `false` are
    values, so they set the flag;
  - `)`, `]` and `}`;
  - the end of any string, slashy or dollar-slashy literal (`StringLiteral` /
    `GStringEnd`);
  - `++` and `--` (`INC` / `DEC`), scanned as two-byte tokens by maximal munch.
    So `+++` is `++` followed by `+`.
- **Tokens that clear it:** every other operator or punctuation byte, including a
  single `+` or `-`, `(`, `[`, `{`, `,`, `=` and `/` (division).
- **A significant newline also clears it.** Groovy's `NL` token, which a `//`
  comment also produces, is a real token unless the innermost open bracket is
  `(`, `[` or `?[`. A `(` right after the keyword `try` does not count here.
  - `code()` keeps a stack of the brackets it has opened (`(` with its
    after-`try` bit, `[`, `{`); `)`, `]` and `}` pop it, and a pop on an empty
    stack is ignored.
  - A template's `${` starts its own `code(true)` with an empty stack. That
    matches Groovy pushing the template's `{`.
- **Hidden, flag unchanged:**
  - spaces and tabs;
  - `\` followed by a line terminator (Groovy's `LineEscape`, skipped as `WS`);
  - a newline inside `(` or `[`;
  - block comments. Groovy turns a block comment into `NL` only when the rest of
    its line is blank (`SemanticPredicates.isFollowedByWhiteSpaces`), and the
    line's own newline then has the same effect.
- **Examples:**
  - after `'prefix' +` a `/` opens a slashy string;
  - after `i++` a `/` is division;
  - a `/` at the start of a line opens a slashy string at top level or inside
    `{…}`, but is division inside `(…)` / `[…]` or after a `\` continuation.
- **Failure.** An unclosed comment or string, an unclosed template, or a stray
  backslash all mean the script was not understood. `failAt` is the offset where
  this happened. Then **nothing is blanked**: `out` is the original source, so the
  scanner over-reads and never hides a dependency.
- **Why the stray-backslash rule is the backstop for slashy strings the heuristic
  misses.** Inside a slashy string, a `/` byte only appears escaped (`\/`). So any
  fake `/*` or `//` from such a string is preceded by a backslash, which fails
  first.

`scanGradle(data []byte, kts bool)`:

- Call `blankGradleComments`.
- If `failAt >= 0`, first append
  `gradleName{Name: "untokenizable", Line: lineOf(src, failAt)}` to `g.Dynamic`.
  It must come first because it is the reported reason. This reuses the Kotlin
  scanner's vocabulary.
- The rest of `scanGradle` is unchanged.

### 4. Build files ignore `include` (`buildGradle`, build-file loop)

```go
// include is a settings statement; in a build file it is a fileTree /
// copy / test-filter pattern and never names a module.
dynamic := slices.DeleteFunc(slices.Clone(g.Dynamic), func(d gradleName) bool { return d.Name == "include" })
dyn := len(dynamic) > 0
…
if len(dynamic) > 0 { problem(m.BuildFile, "gradle-dynamic: "+dynamic[0].Name) }
```

The settings loop keeps using `g.Dynamic` unchanged.

### 5. Bump the cache `schemaVersion` (`cache.go:17`)

Both the raw Gradle extraction and the `.gradle.kts` kind change. Set the value to
**HEAD's value + 1 at commit time**.

- t1976 has landed (8718afa08), so HEAD is now 5. The target is **6** unless
  something else lands first. t1976's inbox note says the same.
- t1977 is still `Implementing` in this same checkout and also bumps this line.
- If the working tree already shows a sibling's uncommitted change there, still
  set HEAD+1 and commit it with this change. Then, at Step 8e, offer
  `/aitask-note` to t1976/t1977 saying that their bump must be relative to the new
  HEAD.
- Do not commit a sibling's other edits.

### 6. Differential over the real corpus, then remove the probe

- Re-run the probe → `$SCRATCH/t1975/after.json`. Diff it against `before.json`.
- Expected: `thinking_app/app/build.gradle` loses `Dynamic: include` and gains the
  two literal `Includes`.
- Every other difference must be explained file by file.
- **No file may gain `untokenizable`.** If one does, that is a valid form the
  lexer misreads. Fix it and add a table case, or stop and report.
- Delete `probe_t1975_test.go` before Step 8. It is never committed.

## Verification

- `cd goengines && go vet ./internal/testmap/deps && go test ./internal/testmap/deps -count=1`.
  The whole package must be green, including `TestGradleModuleGraph`,
  `TestGradleDynamicDepsWiden` and `TestClassifyFingerprint`.
- `ait engine test`: go vet and go test over `goengines/`.
- The two red runs from step 2 and the corpus differential from step 6.
- `git status` shows no probe file and no corpus inside the repo.

## Step 9 reference

Post-implementation follows task-workflow Step 9:

1. Review.
2. Code commit by path: `bug: … (t1975)`, covering `gradle.go`, `raw.go`,
   `gradle_test.go` and `cache.go`.
3. Plan commit.
4. Archival.

Current-branch mode, so there is no merge.

## Risk

### Code-health risk: medium
- The lexer is now a hand-written lexer for two dialects (about 150-200 lines). It
  carries Groovy's slashy-start state: the value-ending token flag, the
  significant-newline bracket stack and the keyword set. That is many more edge
  cases than the regex had.
  - Each modelled form has a table case.
  - Misreads of an unmodelled form fail as `untokenizable`, which widens deps and
    is visible.
  - The 29-file real-corpus differential (step 6) gates false `untokenizable`
    results on real scripts.
  - severity: medium · → mitigation: none (covered by steps 2 and 6)
- The shared `schemaVersion` line is being edited at the same time by t1976/t1977
  in this checkout. A bump made in the wrong order could leave stale dev-cache
  entries.
  - The deps engine is not in any release yet: v0.37.0 has no `deps/cache.go`.
  - severity: low · → mitigation: none (the commit-time HEAD+1 rule and the
    Step 8e note in step 5)

### Goal-achievement risk: low
- Residual: the slashy-start decision copies Groovy's lexer rules (the
  `REGEX_CHECK_SET`, `NL` significance inside and outside brackets, `LineEscape`,
  and how block comments are hidden), but not Groovy's full tokenizer. The two can
  still disagree. One example is a keyword-set difference between Groovy versions:
  master adds `threadsafe async await defer`, which this lexer reads as
  identifiers.
  - Such a slashy string is then missed. If it contains a quote, and a later
    string on the same line contains `//` or `/*`, the rest of that one line can
    still be erased.
  - A missed slashy string cannot make a fake comment of its own. Inside slashy
    content a `/` must be written `\/`, and that backslash fails first as a stray
    backslash. The one exception is the absurd repetition form `/x/*n`.
  - severity: low · → mitigation: none
- Kotlin multi-dollar strings are detected but not modelled. A `build.gradle.kts`
  that uses them is visibly widened (`untokenizable`), not read precisely. If such
  scripts turn out to be common, precise support is a separate follow-up.
  - severity: low · → mitigation: none
- All forms named by the task and the review have fixtures: quoted globs, URLs,
  the thinking_app pair, real comments, dollar-slashy, Kotlin raw strings, and the
  line-anchored build-file include.

## Post-Review Changes

### Change Request 1 (2026-10-14)

- **Requested by user:** `groovyKeywords` listed `val`, but `val` is an
  identifier in Groovy 4.
  - Valid code `def val = 4` / `def n = val / 2` / two URLs and a
    `project(':lib')` lost the dependency silently.
  - The user confirmed this with a Go overlay and a Groovy runtime.
  - Requested fix: correct the keyword table for the intended Groovy version and
    keep the regression.
- **Changes made:**
  - **The keyword table is now measured, not copied from master's grammar.**
    The real `GroovyLangLexer` tokenized `x = <word> / 2 / 3` for every candidate
    word, in Groovy 4.0.29 (the Groovy bundled with Gradle 9.5.1) and in
    3.0.22 (the Groovy 3 that Gradle 8 bundles, from the Gradle cache).
  - **Findings:**
    - `val`, `async`, `await`, `defer` and `module` are `Identifier` in both
      versions.
    - `threadsafe` is a keyword in both. It was missing from my table.
    - `yield`, `record`, `sealed` and `permits` are keywords in 4 and
      identifiers in 3.
  - **Result:**
    - `groovyKeywords` is now the set that both versions agree on.
    - `groovyVersionWords` (`yield record sealed permits`): a `/` right after one
      fails as `untokenizable`. A `.gradle` file does not say whether Gradle 8 or
      Gradle 9 runs it, and the two read that `/` differently.
    - `code()` now tracks the last word token (`word`) instead of an `afterTry`
      bool, so one variable serves both `try (` and the version words.
  - **Tests:**
    - New cases `val-is-identifier` (the reviewer's regression),
      `version-word-division`, `version-word-slashy` and `threadsafe-keyword`.
    - Red check: with `val` put back in the table, `val-is-identifier` fails with
      `refs []`. It passes after the fix.
    - The case table moved to package level (`gradleLexCases`), so a temporary
      probe could dump every fixture for the oracle runs below.
  - **Lexer-oracle differential** (scratch only, not committed):
    - My blanked output was compared against comment spans from the real lexers,
      after normalising whitespace.
    - **Groovy:** 41 inputs (the Groovy fixtures plus the 8 Groovy corpus files
      from thinking_app and teamim). Each was run through `GroovyLangLexer`
      3.0.22 and 4.0.29. Result: **0 mismatches**, 41 matches per version.
      - Every non-match is a deliberate failure of mine: stray backslash,
        unclosed string, unclosed block comment, unclosed dollar-slashy, and the
        version words.
      - In each of these, Groovy errors too, or Groovy accepts something this
        lexer conservatively refuses.
    - **Kotlin:** 28 kts inputs (the fixtures plus all 21 corpus files from
      aitasks_mobile and timexchange). Each was run through Gradle 9.5.1's
      `kotlin-compiler-embeddable` 2.3.20 `KotlinLexer`. Result: **0
      mismatches**, 26 matches.
      - The 2 non-matches are the multi-dollar cases, which fail by design.
- **Files affected:**
  - `goengines/internal/testmap/deps/gradlelex.go`
  - `goengines/internal/testmap/deps/gradle_test.go`

## Final Implementation Notes

- **Actual work done:**
  - **`gradlelex.go` (new): `blankGradleComments(src, kts)`.** A byte lexer for
    two dialects that blanks comments in place and keeps offsets.
    - Groovy forms: `'…'`, `"…"`, `'''…'''`, `"""…"""` with escapes (including
      the CRLF line escape), GString templates, slashy and dollar-slashy strings
      (dollar-slashy escapes tried in `GroovyLexer` order), and `SH_COMMENT`.
    - Kotlin forms: `"…"`, raw `"""…"""` with no escapes, char literals,
      backticked names, nested block comments, and the shebang.
    - The slashy-string start mirrors `GroovyLexer`'s `REGEX_CHECK_SET`: a
      value-ending token, a significant `NL` outside `(`/`[` (except a `try (`),
      hidden `LineEscape`, and hidden block comments.
    - **Fails closed** (the source is returned unblanked and marked
      `untokenizable`) on:
      - unclosed comments, strings or templates;
      - a stray backslash;
      - a Kotlin multi-dollar string (`$$"…"`);
      - a `/` after a Groovy-version-dependent word.
  - **`gradle.go`:**
    - The `gradleComment` regex is gone. `scanGradle(data, kts)` blanks through
      the lexer and records `untokenizable` as the first `Dynamic` entry.
    - The build-file loop of `buildGradle` drops `include` dynamics. `include`
      is a settings statement; settings files are unchanged.
  - **`raw.go`:** `.gradle.kts` → `kindGradleKts` (`gradle-kts`) → Kotlin
    dialect. `.gradle` stays `kindGradle`.
  - **`cache.go`:** `schemaVersion` 5 → 6. HEAD was 5 after t1976 (8718afa08),
    as t1976's inbox note said.
  - **`gradle_test.go` (new):**
    - `TestGradleCommentInString`: the task fixture, plus a kts module whose raw
      string ends in a backslash.
    - `TestGradleUntokenizableWidens`.
    - `TestGradleBuildFileIncludeIsNotModule`: the include sits on its own line,
      so the line-anchored `includeRe` exercises it.
    - `TestScanGradleStringAwareComments` over the package-level
      `gradleLexCases` (46 cases).
- **Deviations from plan:**
  - The lexer lives in its own `gradlelex.go`, mirroring `kotlinlex.go`, not
    inside `gradle.go`.
  - **Keyword table** (review round 6):
    - The table is now *measured* on the real lexers: the Groovy 3.0.22 and
      4.0.29 `GroovyLangLexer`.
    - `groovyKeywords` holds the keywords both versions agree on. Changes: `val`
      removed (an Identifier in both), `threadsafe` added (a keyword in both).
    - New `groovyVersionWords` = `yield record sealed permits` (keywords in 4,
      identifiers in 3): a `/` after one fails.
    - `code()` tracks the last word token instead of an `afterTry` bool.
  - The case table is package-level (`gradleLexCases`) so the oracle probe can
    dump it.
  - The red runs needed a one-line signature shim on the old regex scanner, as
    the plan allowed.
- **Issues encountered:**
  - The first probe walked a non-Gradle file, and `kindOf(p, nil)` dereferences
    `readData` for extensionless paths. Fixed by filtering on suffix first.
  - A scripted hoist of the test table mismatched the struct delimiter, so the
    file was rewritten whole.
  - Other sessions edit files in this shared checkout (t1976 landed mid-session;
    another session is now editing `goengines/cmd`, `annot`, `registry`, `gitx`
    and `runner`). Commits stay path-scoped to this task's five files.
- **Key decisions:**
  - Fail closed means *the whole file is unblanked*, never a partial blank. The
    scanner then over-reads and widens; it never hides a dependency.
  - Build files never parse `include`.
  - Kotlin multi-dollar strings are detected and fail; they are not modelled.
  - The version words fail instead of picking one Groovy version, because a
    `.gradle` file does not say which Gradle runs it.
- **Verification evidence:**
  - **Red before step 3** (old regex plus the shim): all 3 repo-level tests and
    30 of the 42 table cases at the time. The 12 guards passed: real comments,
    the division, hidden-newline, line-continuation and shebang cases.
  - **After step 3, before step 4:** only `TestGradleBuildFileIncludeIsNotModule`
    was red.
  - **After step 4:** the whole package is green. `ait engine test` exits 0
    (go vet plus every package).
  - **Review round 6 regression:** with `val` in the table,
    `val-is-identifier` gives `refs []`. It passes after the fix.
  - **Corpus differential (raw extraction).** 29 files from 4 repos, pinned at
    HEAD:
    - thinking_app `1dc7b958926f`
    - aitasks_mobile `75f4543fb70e`
    - timexchange `c60e7e05a465`
    - teamim `18a4679d1c10`

    Before vs after:
    - The only field change: `thinking_app/app/build.gradle` loses
      `Dynamic include@920` and gains `Includes` `*/*_REVIEW.md@920` and
      `*/evidence/t53_*/LEDGER_RECONCILE.tsv@921`.
    - The 21 `.gradle.kts` files change kind to `gradle-kts`.
    - 0 files gained `untokenizable`.
  - **Full `Scan` over a thinking_app Gradle snapshot:** `:app` deps `[]` (was
    `[":"]`), `app/build.gradle` is not opaque, and there are no problems (was
    `gradle-dynamic: include`).
  - **Lexer-oracle differential.** My blanked output is compared with the real
    lexers' comment spans after whitespace normalisation (scripts below).
    - **Groovy 3.0.22 and 4.0.29:** 41 inputs → 41 MATCH, 0 MISMATCH per
      version.
      - The non-matches are all deliberate failures of mine. In each case Groovy
        errors too (stray backslash, unclosed string; under 4, `record / 2`
        also errors), or this lexer is stricter than Groovy (an unclosed block
        comment or dollar-slashy at EOF, the version words).
    - **Kotlin** (`kotlin-compiler-embeddable` 2.3.20 `KotlinLexer`): 28 inputs
      → 26 MATCH, 0 MISMATCH, and 2 MINE_FAIL (the multi-dollar cases, by
      design).
- **Upstream defects identified:**
  - `goengines/internal/testmap/deps/kotlinlex.go:187` — `ktLexer.str` (with `code`'s `$` handling) treats a Kotlin 2.2 multi-dollar string (`$$"""…"""`) as an ordinary string and recurses into a literal `${`, so `val s = $$"""${/*}"""` swallows every token up to a later `*/` with err=nil (measured: `fun f() = Callee()` lost) — silent under-read of .kt sources
- **Scratch evidence, verbatim** (from the session scratchpad; the jar paths
  are this machine's):

  Groovy keyword probe (`kwprobe.groovy`). It runs with
  `java -cp <groovy-3.0.22.jar|groovy-4.0.29.jar> groovy.ui.GroovyMain kwprobe.groovy <comma-separated words>`:
  ```groovy
import org.apache.groovy.parser.antlr4.GroovyLangLexer
import org.apache.groovy.parser.antlr4.GroovyLexer
import groovyjarjarantlr4.v4.runtime.CharStreams
def words = args[0].split(',')
for (w in words) {
  def lx = new GroovyLangLexer(CharStreams.fromString("x = " + w + " / 2 / 3\n"))
  def toks = lx.getAllTokens().findAll { it.channel == 0 }
  def i = toks.findIndexOf { it.text == w }
  def next = i >= 0 && i + 1 < toks.size() ? toks[i + 1] : null
  def wt = i >= 0 ? GroovyLexer.VOCABULARY.getSymbolicName(toks[i].type) : 'NONE'
  def nt = next ? GroovyLexer.VOCABULARY.getSymbolicName(next.type) : 'NONE'
  println "${w}\t${wt}\t${nt}"
}
  ```
  Groovy comment-span oracle (`groovy_oracle.groovy <dir> g3|g4`):
  ```groovy
import org.apache.groovy.parser.antlr4.GroovyLangLexer
import groovyjarjarantlr4.v4.runtime.CharStreams
import groovyjarjarantlr4.v4.runtime.BaseErrorListener
def dir = new File(args[0]); def suffix = args[1]
dir.listFiles().findAll { it.name.endsWith('.groovy.src') }.sort().each { f ->
  def src = f.getText('UTF-8')
  def out = new File(dir, f.name.replace('.src', '.' + suffix))
  try {
    def lx = new GroovyLangLexer(CharStreams.fromString(src))
    lx.removeErrorListeners()
    lx.addErrorListener(new BaseErrorListener() {
      void syntaxError(groovyjarjarantlr4.v4.runtime.Recognizer r, Object o, int line, int col, String msg, groovyjarjarantlr4.v4.runtime.RecognitionException e) {
        throw new RuntimeException("line ${line}:${col} ${msg}")
      }
    })
    def chars = src.toCharArray()
    if (src.startsWith('#!')) {
      int i = 0
      while (true) {
        while (i < chars.length && chars[i] != '\n') { chars[i] = ' ' as char; i++ }
        if (i + 2 < chars.length && chars[i + 1] == '#' && chars[i + 2] == '!') { i++ } else break
      }
    }
    for (t in lx.getAllTokens()) {
      def tx = t.text
      if (tx != null && (tx.startsWith('//') || tx.startsWith('/*'))) {
        for (int k = t.startIndex; k <= t.stopIndex; k++) if (chars[k] != '\n') chars[k] = ' ' as char
      }
    }
    out.setText(new String(chars), 'UTF-8')
  } catch (Throwable e) {
    out.setText("ERROR: " + e.message, 'UTF-8')
  }
}
  ```
  Kotlin comment-span oracle (`kotlin_oracle.groovy <dir>`), with the classpath
  `groovy-4.0.29.jar:kotlin-compiler-embeddable-2.3.20.jar:kotlin-stdlib-2.3.20.jar`:
  ```groovy
import org.jetbrains.kotlin.lexer.KotlinLexer
def dir = new File(args[0])
dir.listFiles().findAll { it.name.endsWith('.kts.src') }.sort().each { f ->
  def src = f.getText('UTF-8')
  def out = new File(dir, f.name.replace('.src', '.kt'))
  try {
    def lx = new KotlinLexer()
    lx.start(src)
    def chars = src.toCharArray()
    def bad = []
    while (lx.tokenType != null) {
      def name = lx.tokenType.toString()
      def tx = src.substring(lx.tokenStart, lx.tokenEnd)
      if (name == 'BAD_CHARACTER') bad << lx.tokenStart
      if (tx.startsWith('//') || tx.startsWith('/*') || tx.startsWith('#!')) {
        for (int k = lx.tokenStart; k < lx.tokenEnd; k++) if (chars[k] != '\n') chars[k] = ' ' as char
      }
      lx.advance()
    }
    out.setText(bad ? "ERROR: BAD_CHARACTER at " + bad : new String(chars), 'UTF-8')
  } catch (Throwable e) {
    out.setText("ERROR: " + e, 'UTF-8')
  }
}
  ```
  Temporary Go dump probe (`probe_t1975_test.go`, deleted). It writes
  `<id>.src`, `<id>.mine` (the `blankGradleComments` output) and `<id>.fail`
  (`failAt`) for every `gradleLexCases` entry and corpus file:
  ```go
package deps

// TEMPORARY t1975 oracle probe — never committed.

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func TestProbeT1975Dump(t *testing.T) {
	out, corpus := os.Getenv("AIT_T1975_ORACLE"), os.Getenv("AIT_T1975_CORPUS")
	if out == "" {
		t.Skip("probe")
	}
	dump := func(id string, kts bool, src string) {
		ext := ".groovy"
		if kts {
			ext = ".kts"
		}
		blanked, failAt := blankGradleComments(src, kts)
		os.WriteFile(filepath.Join(out, id+ext+".src"), []byte(src), 0o644)
		os.WriteFile(filepath.Join(out, id+ext+".mine"), []byte(blanked), 0o644)
		os.WriteFile(filepath.Join(out, id+ext+".fail"), []byte(fmt.Sprint(failAt)), 0o644)
	}
	for _, c := range gradleLexCases {
		dump("case_"+c.name, c.kts, c.src)
	}
	if corpus != "" {
		filepath.WalkDir(corpus, func(p string, d fs.DirEntry, err error) error {
			if err != nil || d.IsDir() {
				return err
			}
			kts := strings.HasSuffix(p, ".gradle.kts")
			if !kts && !strings.HasSuffix(p, ".gradle") {
				return nil
			}
			rel, _ := filepath.Rel(corpus, p)
			data, _ := os.ReadFile(p)
			dump("corpus_"+strings.ReplaceAll(rel, "/", "__"), kts, string(data))
			return nil
		})
	}
}
  ```
  The comparison is `re.sub(r'\s+',' ',x).strip()` equality of `.mine` against
  `.g3` / `.g4` / `.kt`, when neither side failed.
