---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [testing, testmap, go_engine]
assigned_to: dario-e@beyond-eye.com
anchor: 1852
followup_kind: upstream_defect
created_at: 2026-10-14 19:22
updated_at: 2026-10-14 22:00
---

## Origin

Found by t1954_4 (annotation-parser research synthesis). The final corpus
gained four Kotlin 2.2 multi-dollar string fixtures after t1980 found the same
blind spot in the `deps` Kotlin lexer. Report:
`aidocs/testing_engine/t1954_annotation_parser_research.md` (section
"Kotlin multi-dollar strings").

## Upstream defect

`goengines/internal/testmap/annot/lexctx.go`, the Kotlin classifier. It does
not model the Kotlin 2.2 multi-dollar interpolation prefix (`$$"…"`,
`$$"""…"""`). In such a string only a `$`-run as long as the prefix starts a
template, so a single `${` is literal text. The classifier takes that `${` for
a template and mis-places every later string and comment boundary. On the
valid fixture below (kotlinc 2.4.21 compiles it), it ends up outside the raw
string that line 9 is really inside, reads line 9 as a real annotation, and
`Apply` writes into the string's content:

```kotlin
package app

// testmap:covers app/real.kt
fun f() {
    val s = $$"""${/*"""
    // */
}
val t = """
// testmap:covers app/fake.kt
"""
val u = """x"""
// """
```

Measured through the real `ParseFile → PlanCovers → Apply` at annot
`3d1a2b628` (and identically at `f096db065`):
`results/t4/matrix_baseline.md`, case `kotlin/multidollar_comment_desync.kt`:
FP-writable 3, Record-corruption 1, and a raw write into line 9 **applied**
(want `refused:not-comment`). The other three multi-dollar fixtures are safe
(one is over-refused). ktpsi, gotreesitter, tscgo and tswasm are safe on all
four.

Exposure on 2026-10-14: no `.kt` / `.kts` file in the six registered
repositories contains `$$"` (`results/t4/inputs.md` snapshots). Any target
that adopts Kotlin 2.2 multi-dollar strings becomes exposed.

## Fix

Use the modelled-or-fail rule (the same choice t1975 made for the Gradle
blanker and t1980 for `deps/kotlinlex.go`):
- either model the prefix exactly: count the `$` run before the opening
  quote, and start a template only on a `$`-run of that length followed by
  `{` or an identifier;
- or fail closed: classify the file Uncertain (`ErrUncertainContext`) as
  soon as a multi-dollar string opener appears.

Never let the classifier continue with a guessed boundary.

## Verification

- Port the four `corpus/kotlin/multidollar_*.kt.in` fixtures (with their
  `.expect`) from `aidocs/testing_engine/t1954_parser_research/` into
  `annot`'s tests. `multidollar_comment_desync` must yield no record on line 9,
  and a write there must be refused (not-comment if modelled, uncertain if it
  fails closed).
- Negative control: the test fails on the current classifier.
- Optional: rerun `go run ./cmd/t1954 matrix --provider baseline --lang kotlin`
  in the research dir after moving its pin to the fix commit. The
  multidollar rows must show 0 on every safety column.
