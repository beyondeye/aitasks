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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2030** id=2026-10-20T05:59:22Z.b0e6c9115975c12ecf319ca0 from=t2030 from_verified=yes at=2026-10-20T05:59:22Z base=d0a790a91dfb10bfe76c99daafe0e7ac065226c7 base_branch=main dirty=yes host=omg16
>
> | t2030 (code commit d0a790a91) changed deps/kotlinlex.go and deps/cache.go, so two of this task's references are stale:
> | - The raw-string emit this task targets moved: `l.emitStr(plain, l.src[start:j-3], line)` is now kotlinlex.go:302, not the line this body cites. The `\r` handling now happens in `str()` at around lines 260-305.
> | - schemaVersion is now 14 (t2030 bumped it from 13), so this fix's bump should be to 15.
> | - ktLex now refuses any lone CR up front (`loneCR`), so the only `\r` that can reach `str()` is one that precedes `\n`, i.e. CRLF. That matches this task's assumption.
