---
priority: low
effort: low
depends: []
issue_type: bug
status: Postponed
labels: [testing, testmap, go_engine]
gates: [risk_evaluated]
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-16 01:34
updated_at: 2026-10-30 12:10
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

> **✉ note:t15** id=2026-10-25T08:54:36Z.4b5b260ecfd73d8c37927af8 from=aitasks_go#t15 at=2026-10-25T08:54:36Z base=eb6baa4c91e763eb8e482682433d287f1f17f99d base_branch=main dirty=no host=omg16
>
> | Coordination notice from aitasks_go (t15 ship-path decision; schedule in trail
> | art:trail-go-ship-path owned by aitasks_go#t22). Advisory context, not an
> | instruction. It does not change this task's scope.
> | 
> | WHAT IS PLANNED
> | ait-testmap Go development (public goengines/) will move ONCE into the private
> | aitasks_go repository, at a cutover performed by aitasks_go#t22. After that,
> | goengines/ here receives exported snapshots only (no tests, bench or ci), and
> | engine work happens in aitasks_go. As of 2026-10-25 the cutover has no date.
> | Its prerequisites are aitasks_go t20 and t21 and aitasks t2138.
> | 
> | UNTIL THE CUTOVER: CONTINUE THIS TASK HERE, AS NORMAL
> | To keep the cutover cheap and safe:
> | 1. Land goengines/ changes on main promptly. Avoid long-lived branches,
> |    worktrees or unmerged PRs touching goengines/, because the cutover has to
> |    wait for, or hand off, every one of them.
> | 2. Keep engine commits (goengines/**) separate from framework-side commits
> |    (the aitask_testmap.sh shim, installer/setup, skills, docs, aitestmap/).
> |    Mixed tasks will be split along that line, and separate commits keep both
> |    the split and the history migration clean.
> | 3. If goengines tests start reading data from outside goengines/ (as with the
> |    t1954 corpus under aidocs/testing_engine/), record that path in this
> |    task's plan. The migration must copy it into the private module.
> | 4. Add no new Go binary or non-testmap package to goengines/. ait-monitord is
> |    being re-homed to aitasks_go (aitasks_go#t23), and ait-tui is developed
> |    there.
> | 5. Keep the contracts and guards as usual: the dependency allowlist, the
> |    Invariant 4-5 tripwire, the hang guard, bench baselines, and the
> |    version/verb/exit-code interface. The migration carries them over verbatim
> |    and checks that nothing changed.
> | 
> | FREEZE PROTOCOL
> | Shortly before the cutover, aitasks_go#t22 will send this task a
> | "goengines freeze in effect" note. From that note until a matching
> | "goengines freeze lifted" note, do not claim or start goengines work here. A
> | task that is Implementing or locked at that time is never relocated under its
> | agent: t22 waits for it to land, or arranges an explicit checkpointed handoff
> | (commit/push, handoff note, release the lock, back to Ready).
> | 
> | AFTER THE CUTOVER
> | If this task still has engine work pending, it is re-homed to aitasks_go
> | (engine-only) or split (the Go part there, the framework part here), and the
> | original carries a pointer. Framework-side work (the shim, installer, skills,
> | docs, aitestmap/ and the n014 spec) stays in this repository permanently. An
> | emergency public fix to goengines/ after the cutover needs a
> | `Return-To: aitasks_go` trailer plus a return task in aitasks_go
> | (`ait create --batch --project aitasks_go`).

> **✉ note:t22_3** id=2026-10-29T22:23:26Z.a58e98acca046421d09d987f from=aitasks_go#t22_3 from_verified=yes at=2026-10-29T22:23:26Z base=cd7ab3b2d1735acc848c76d30310a2880c73cba3 base_branch=main dirty=no host=omg16
>
> | goengines freeze in effect (aitasks_go#t22 cutover).
> | Do not start or continue any change under goengines/ until the matching
> | "goengines freeze lifted" note arrives on this task. Framework work
> | (shell scripts, skills, docs, website) is not frozen, but do not pick a
> | task whose remaining scope includes goengines/ source.
> | After the cutover, engine development lives in beyondeye/aitasks_go;
> | public goengines/ receives exported snapshots only.
