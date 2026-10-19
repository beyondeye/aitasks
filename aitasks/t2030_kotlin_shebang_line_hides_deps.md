---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, testmap, go_engine]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-16 01:27
updated_at: 2026-10-19 17:04
---

## Origin

Found by t1992, the Kotlin-family lexer evaluation (decision record in t1992's archived plan, `aiplans/archived/p1992_kotlin_family_shared_lexical_core_evaluation.md`). The plan review reproduced the unsafe variant through `scanKotlin`. The real `KotlinLexer` (kotlin-compiler-embeddable 2.3.20) reads all of these sources as valid Kotlin, with line 1 one `SHEBANG_COMMENT` token.

## Upstream defect

Kotlin.flex lexes a `#!` line at the start of a file as `SHEBANG_COMMENT`. Of the three Kotlin-family lexers, only the kts blanker models it (`gradleLexer.shebang`, `deps/gradlelex.go`).

**`deps/kotlinlex.go` (`ktLex`)** lexes the shebang line as code.

`ktLex` receives every `.kt` file and every non-Gradle `.kts` file, e.g. `*.main.kts` scripts, which are exactly the files that carry a shebang (`deps/raw.go` `kindOf`). Measured through `scanKotlin` at `2874e66ea`:

| source | ktLex err | `Package` | `Decls` | `Opaque` |
|---|---|---|---|---|
| `#!/usr/bin/env kotlin\npackage p\nclass Actual\n` | nil | `p` | `[Actual]` | `[]` |
| `#!/usr/bin/env -S kotlin -J-Dtag={\npackage p\nclass Actual\n` | nil | **""** | **`[]`** | `[]` |
| `#!/usr/bin/env -S kotlin -J-Dtag=(\npackage p\nclass Actual\n` | nil | `p` | **`[]`** | `[]` |
| `package p\nclass Actual\n` (control) | nil | `p` | `[Actual]` | `[]` |

- A `{` in the shebang raises the scanner's brace depth: the package clause and every declaration are **hidden silently**, with no error and no opaque reason. That is a missed dependency in the unsafe direction.
- A `(` raises `parens`, which gates declarations at `kotlin.go:175`: the declarations are hidden silently.
- A `/*` opens a block comment that never closes: the file is refused (opaque `untokenizable`), which is the safe direction.
- A plain shebang only adds stray tokens (`o:# o:! o:/ n:usr …`).

**`annot/lexctx.go` (`classifyKotlin`)** lexes the shebang line as code too.
- A `{` in it hides the `package` / `import` lines from `Ctx.Package` / `Ctx.Import` (`package=0` where the real lexer has 2). `fixedPosition` (`annot/rewrite.go`) then inserts a fresh block after the shebang instead of after the package/imports: valid, but misplaced.
- A `/*` in it makes the file Uncertain. For a file carrying `testmap:`, `ParseFile` returns a `SyntaxError`, and `ScanAnnotations` (`annot/source.go:54-60`) fails the **whole scan**.

**Exposure on 2026-10-16:** 0 of the 2051 `.kt`/`.kts` files in the 8 registered repositories start with `#!` (t1992 inputs table). Any Kotlin script target is exposed.

## Fix

Model Kotlin.flex's `SHEBANG_COMMENT` in both lexers. Probe the real lexer for the exact rule before coding: whether only offset 0 counts, and whether it is honoured after a BOM.
- `ktLex`: skip a leading `#!` line, emitting nothing, as `gradleLexer.shebang` does for kts.
- `classifyKotlin`: treat line 1 as a comment-like non-annotation line when it starts with `#!` (after the BOM, if kotlinc honours it there), and start lexing at line 2. Keep `fixedPosition`'s existing shebang skip.
- `deps/cache.go`: bump `schemaVersion` (ktLex output changes).

## Verification

- In `deps/kotlinfamily_test.go`, the `shebang_plain`, `shebang_slash_star`, `shebang_brace` and `shebang_paren` rows flip to `modelled` for annot and ktLex; the test fails until they are updated.
- `scanKotlin` regressions for the brace and paren shebangs: `Package` = `p`, `Decls` = `[Actual]`. Also an annot regression: anchors `package=2` and no Uncertain for the `/*` shebang.
- Negative control: the new tests fail on the current lexers.
- Optional: rerun t1992's `KtFamily.java` harness (verbatim in its archived plan) over the construct rows.
