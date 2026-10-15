---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-16 01:34
updated_at: 2026-10-16 01:34
---

## Origin

Spawned from t1992 during Step 8b review.

## Upstream defect

- `goengines/internal/testmap/deps/kotlinlex.go:269 — ktLex keeps the \r of CRLF line separators in raw-string s-token content, while kotlinc normalises them; harmless today (only .localized keys read s content), zero CR files in the registered repositories`

## Diagnostic context

t1992 compared `ktLex`'s whole token stream with the real `KotlinLexer` (kotlin-compiler-embeddable 2.3.20). kotlinc normalises line separators before lexing, so a raw string spanning CRLF lines has `\n`-only content. `ktLex` emits the raw bytes between the quotes, `\r` included. The t1992 construct row `crlf` in `goengines/internal/testmap/deps/kotlinfamily_test.go` pins it as a `differs` outcome for ktLex:

- ktLex: `s@1:\r\n//\sin\sraw\r\n`
- real lexer: `s@1:\n//\sin\sraw\n`

Consumer effect: `s` content is read only for `.localized` keys (`kotlin.go:111`), and a multi-line raw string key does not occur in practice. Exposure on 2026-10-16: 0 of the 2051 Kotlin files in the 8 registered repositories contain `\r`.

## Suggested fix

In `ktLexer.str()`, strip each `\r` that precedes `\n` from a raw string's content before `emitStr`. Then:
- flip the `crlf` row to `modelled` for ktLex;
- bump `deps/cache.go` `schemaVersion`;
- add a `TestKotlinLexer` row.
