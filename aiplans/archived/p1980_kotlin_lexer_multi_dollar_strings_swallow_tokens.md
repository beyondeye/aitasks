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

## Post-Review Changes

### Change Request 1 (2026-10-14 12:30)
- **Requested by user:** the `$`-run lookahead advanced `l.i` by one on the non-quote path, rescanning every remaining suffix — O(n²) on a long `$` run (reviewer measured ~4 ms original vs ~635 ms for 80,000 dollars).
- **Changes made:** the non-quote path now emits one `o:$` per dollar and advances `l.i` over the whole checked run in one pass. Pinned `"$$$ x"` → `o:$ o:$ o:$ n:x`. Throwaway probe (deleted): 80,000 dollars + ` x` → 4.8 ms, 80001 tokens, err=nil.
- **Files affected:** `goengines/internal/testmap/deps/kotlinlex.go`, `goengines/internal/testmap/deps/kotlinlex_test.go`

## Final Implementation Notes
- **Actual work done:** `ktLexer.code()` (`kotlinlex.go`) gained a `$` case: a run of `$` immediately followed by `"` returns `errUntokenizable` (mirrors `gradlelex.go`'s kts multi-dollar detection); any other run emits one `o:$` per dollar, as before, consumed in one pass. `ktLex` doc comment updated. `kotlinlex_test.go`: bad inputs `$$"""${/*}"""`, `$$"a"`, `"${ $$"x" }"`; positive pins `"a$" + "$$"`, `$ x`, `$$$ x`; new `TestKotlinLexerMultiDollarFailsClosed` runs the task's exact probe through `ktLex` and `scanKotlin` (opaque `untokenizable`). `cache.go` `schemaVersion` 6 → 7 (HEAD was 6 at commit time).
- **Deviations from plan:** one post-review change (Change Request 1): the non-quote path consumes the whole `$` run instead of advancing one byte, removing an O(n²) rescan.
- **Issues encountered:** red proof — pre-fix, `$$"a"`, `"${ $$"x" }"` and the probe lexed with err=nil (failed the new tests); the standalone `$$"""${/*}"""` already errored pre-fix only because its comment never closes. Post-fix `go test ./...` across goengines green; gofmt/vet clean.
- **Key decisions:** fail closed rather than modelling the N-dollar interpolation threshold — over-read (opaque file) is the safe direction and matches t1975's Gradle lexer; a lone `$` before `"` is also rejected (not valid Kotlin code anyway).
- **Upstream defects identified:** None
