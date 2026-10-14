---
Task: t1980_kotlin_lexer_multi_dollar_strings_swallow_tokens.md
Base branch: main
Output branch: main
---

# t1980 — Kotlin `.kt` lexer: fail closed on multi-dollar strings

## Context

`ktLexer` (`goengines/internal/testmap/deps/kotlinlex.go`) does not model
Kotlin 2.2 multi-dollar interpolation strings (`$$"…"`, `$$"""…"""`). In them a
single `${` is literal text, but `code()` emits the `$` prefix as an operator,
`str()` lexes the string as an ordinary one and recurses into the literal `${`
via `code(true)`. A `/*` there opens a block comment that runs to a later
string's `*/`, so `val s = $$"""${/*}"""` … `*/` silently swallows
`fun f() = Callee()` with `err=nil` — under-selection, and no `untokenizable`
opaque reason. Both callers (`scanKotlin` in `kotlin.go:71`, `frombody.go:65`)
already turn a lexer error into the `untokenizable` opaque reason, so failing
closed converts the silent under-read into a visible over-read.

Approach: **fail closed**, exactly like t1975's `gradlelex.go:170-178` (the
same `$`-run-then-`"` detection). Modelling the N-dollar threshold is not
needed for correctness and stays out of scope.

## Steps

1. **Red proof first** — add the tests from step 3 and run
   `cd goengines && go test ./internal/testmap/deps/ -run 'TestKotlinLexer'`;
   confirm the new multi-dollar cases fail against the unchanged lexer.

2. **`kotlinlex.go` — `code()`**: add a case before `default`:
   ```go
   case c == '$':
       // $$"…" is a multi-dollar string (Kotlin 2.2): a single ${ inside it
       // is literal text. Its interpolation threshold is not modelled, and
       // lexing it as a plain string would read that ${ as template code.
       j := l.i
       for j < len(l.src) && l.src[j] == '$' {
           j++
       }
       if j < len(l.src) && l.src[j] == '"' {
           return errUntokenizable
       }
       l.emit('o', "$", l.line)
       l.i++
   ```
   A `$` not followed (after its run) by `"` keeps today's one-`'o'`-token-per-`$`
   output. Inside a template (`code(true)`) the same case applies, so
   `"${ $$"x" }"` also fails closed. Extend the `ktLex` doc comment: "A
   construct that never closes, or a Kotlin multi-dollar string, is an error".

3. **`kotlinlex_test.go`**:
   - `bad` list: add `` `$$"""${/*}"""` `` , `` `$$"a"` `` and `` `"${ $$"x" }"` ``.
   - positive map (unchanged behaviour pinned): `` `"a$" + "$$"` `` →
     `s:a$ o:+ s:$$` (dollars inside strings), `"$ x"` → `o:$ n:x` (a lone `$`
     in code not before a quote).
   - new `TestKotlinLexerMultiDollarFailsClosed` with the task's exact probe
     source (`package p` … `val s = $$"""${/*}"""` / `fun f() = Callee()` /
     `val t = """*/}"""`): assert `ktLex` returns `errUntokenizable`, and that
     `scanKotlin([]byte(src)).Opaque` contains `"untokenizable"` (the
     consumer-visible outcome).

4. **`cache.go`**: bump `schemaVersion` 6 → 7 (HEAD is 6; re-check HEAD at
   commit time and use HEAD+1) — the extraction rules for `.kt` files changed.

## Verification

- `cd goengines && go vet ./internal/testmap/deps/ && go test ./internal/testmap/deps/`
  — all green, including `TestOpaqueBranchesRedProved` / `TestClassifyFingerprint`.
- Red proof from step 1 recorded (new cases fail pre-fix, pass post-fix).
- `ait engine test` if the wider goengines tree compiles (other sessions have
  uncommitted work in `cmd/ait-testmap`; a failure there unrelated to `deps/`
  is reported, not fixed).

## Step 9 (Post-Implementation)

Commit `kotlinlex.go`, `kotlinlex_test.go`, `cache.go` only (path-scoped —
the tree has unrelated concurrent changes), then archive per Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
