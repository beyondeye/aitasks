---
Task: t1969_fix_annot_utf8_bom_python_docstring_and_placement.md
Base branch: main
Output branch: main
---

# t1969 — honour a leading UTF-8 BOM in `annot`, never insert above it

## Context

The t1954 baseline matrix (`corpus/python/bom_doc.py`) found one real defect in the
landed annotation rewriter (`goengines/internal/testmap/annot`, unchanged since
`f096db065`):

1. `classifyPython` lexes line 1's BOM bytes (`EF BB BF`) as identifier characters
   (`isIdentStart` accepts `>= 0x80`), so a module docstring right after a BOM is not
   detected. Its `testmap:` records are lost; CPython's `ast.get_docstring` sees them.
2. With no docstring and no leading comments, `fixedPosition` returns 0 and the new
   line goes **above the BOM**. That pushes the BOM to the start of line 2, and
   `python3` then fails with `SyntaxError: invalid non-printable character U+FEFF`.
   `Apply`'s proof misses it because the moved line keeps its bytes and its (mis)class.

Exposure today is nil (0 BOM files in 5,723 surveyed sources), so the fix narrows on
one precondition: line 1 starts with a BOM **and** the language's toolchain skips one.
Every other file takes exactly the current code path.

Language facts:
- **Python**: CPython skips a leading BOM; anywhere else it is a SyntaxError.
- **Go**: the spec allows skipping a leading BOM, and gc/`go/scanner` do; elsewhere it
  is "illegal byte order mark". Today a `// testmap:` comment on a BOM line 1 is not
  read: the Column check compares against an indent that ignores the 3 BOM bytes.
- **Kotlin**: to be confirmed by a probe (step 0). Today `﻿package p` is not seen
  as the package clause either.
- **bash**: gives a BOM no meaning (the t1954 `bash/bom_edit.sh` fixture pins line 1 as
  code). Bash stays exactly as it is, as the task requires.

Constraints found while exploring:
- `aidocs/testing_engine/t1954_parser_research/baseline/seam.patch` patches
  `lang.go` (context: the `byExt` tail + the `LangOf` head) and `lexctx.go` (context:
  the `Context` struct tail + the head of `Classify`: `lines := splitLines(data)` /
  `switch l.Name {` / `case Go.Name:`). Those context lines must stay
  byte-identical, or t1954_4's pin move will fail.
- Another session has uncommitted edits in `annot/hook.go`, `annot/stampverbs.go`
  (and `goengines/README.md`, the n014 proposal doc). This plan touches none of them.
  The commit names its paths explicitly.

## Implementation

0. **Probe Kotlin and Go (evidence before code).** In the scratchpad, compile each
   file **with one and the same invocation per language**. Kotlin uses the local
   kotlinc (`/opt/android-studio/plugins/Kotlin/kotlinc/bin/kotlinc`, on the JDK
   from PATH); Go uses `go build`:
   - `k0.kt` = `package p\nfun main() { println("ok") }\n` — the **no-BOM control**;
   - `k1.kt` = BOM + the same bytes — leading BOM;
   - `k2.kt` = `// x\n` + BOM + the same bytes — a BOM that is not at byte 0.

   `g0.go` / `g1.go` / `g2.go` are the same three shapes around
   `package p\nfunc main() {}\n`.
   **Outcomes (exhaustive, per language):**
   | control (0) | leading BOM (1) | conclusion |
   |---|---|---|
   | fails | any | **inconclusive.** A tool, JDK or launcher failure says nothing about the language. Resolve it (e.g. the JDK, or the other local kotlinc) and re-run. Never record a language conclusion from this row. |
   | compiles | compiles | `SkipsBOM: true` |
   | compiles | fails | `SkipsBOM: false`: the language rejects a leading BOM (such a file is broken anyway). It stays like bash, its classifier is untouched, and the evidence goes into Final Implementation Notes. |

   Shape 2 is recorded as information only (does a moved BOM break the file?). It
   does not change the rule. Expected: Kotlin and Go both true.

1. **`lang.go` — declare the property.** Add a field to `Lang` (above the `var` block,
   outside the seam hunk):
   ```go
   // SkipsBOM: the toolchain ignores a UTF-8 byte-order mark that starts the
   // file (and only there), so line 1 begins after it.
   SkipsBOM bool
   ```
   Set `SkipsBOM: true` on `Python`, `Go` and (per step 0) `Kotlin`. Bash keeps the
   zero value. Hook-supplied research languages also default to false, which is
   today's behaviour.

2. **`lexctx.go` — one helper, used by the three classifiers.** Next to `splitLines`
   (below `Classify`, outside the seam hunk):
   ```go
   // bom is the UTF-8 byte-order mark.
   const bom = "\xef\xbb\xbf"

   // bomLen is the length of the byte-order mark that starts line 1 when l
   // skips one — line 1's text starts after it — and 0 otherwise.
   func bomLen(l Lang, lines []string) int {
       if l.SkipsBOM && len(lines) > 0 && strings.HasPrefix(lines[0], bom) {
           return len(bom)
       }
       return 0
   }
   ```
   `Classify` itself is **not** edited.
   - `classifyPython`: `skip := bomLen(Python, lines)`. For `i == 0`, decide the class
     on `ln[skip:]` (`startsWithLeader`), and start the byte loop at `j := skip`.
     DocSpan columns stay raw-byte offsets (they include the 3 BOM bytes), which is
     what `spanSegment`/`docstringLines` already index by. Nothing else changes.
   - `classifyKotlin` (only if step 0 says true): the same `from` offset for line 1 in
     the Comment test, the `package`/`import` detection (`TrimLeft(ln[from:], …)`)
     and the start of the byte loop.
   - `classifyGo`: the scanner already skips the BOM, so only the Comment column test
     changes. It compares `p.Column-1` against `s + len(indentOf(line[s:]))`, where
     `s = bomLen(Go, lines)` on line 1 and 0 elsewhere.

3. **`grammar.go` `ParseFile` — read a comment on a BOM line 1.** Compute
   `skip := bomLen(lang, f.Lines)` once. In the Comment arm, cut the leader from
   `text[s:]` (`s = skip` when `i == 0`, else 0). Without this, slicing
   `[len(lang.Leader):]` lands inside the BOM, and the newly-Comment line would be
   silently unread. `Line.Text` stays the raw line, BOM included, so `Replace`'s
   `Want` check and `RestampLine` keep the BOM bytes on a re-stamp.

4. **`rewrite.go` — never above a BOM, refused at plan time and at proof time.**
   - New sentinel next to `ErrDocstring`:
     `ErrByteOrderMark = errors.New("byte-order-mark")` — "the new line would go
     above a byte-order mark the language skips; nothing can precede it".
   - `Placement`'s file-level branch: compute `after`/`indent` (the fixed position,
     clamped before the first member opener exactly as today), then
     `if after == 0 && bomLen(f.Lang, f.Lines) > 0 { return 0, "", "", ErrByteOrderMark }`.
     This covers both routes to 0: no docstring/leading comments, and a member opener
     on line 1. Placement after a docstring (`DocEnd ≥ 1`) or after a leading comment
     run (`≥ 1`) is unaffected. That is the bom_doc.py case: the insertion goes after
     line 4.
   - `verifyResult` (Apply's proof, which covers every current and future writer).
     Add as its **first** check, on the raw bytes and **before** the
     `ParseFile(set.Path, out)` reparse:
     ```go
     // A byte-order mark the language skips is one only at the start of the
     // file: an edit may neither move nor add one. Checked on the raw bytes,
     // before the reparse: whether a moved mark still lexes depends on the
     // language (go/scanner refuses it, the Python lexer reads it as a name).
     if old.Lang.SkipsBOM && bytes.HasPrefix(old.data, []byte(bom)) != bytes.HasPrefix(out, []byte(bom)) {
         return fmt.Errorf("%s: the edit would move the byte-order mark: %w", set.Path, ErrNotComment)
     }
     ```
     This is the check whose absence let the t1954 case through. It runs before the
     reparse, so the refusal is the same sentinel in every BOM-skipping language: a
     moved Go BOM would otherwise surface only as a `SyntaxError` from the reparse,
     and a moved Python BOM not at all.
   - **Refuse, not "insert after line 1"**, for the case with no valid slot. The task
     allows either. Refusing is fail-closed and invents no placement policy: a slot
     after line-1 code can land inside an import list or a class header. Exposure is
     nil. Through `annotate`, `PlanCovers`'s error reaches `reportError` (non-zero
     exit, nothing written). A structured `STAMP_REFUSED` would need a
     `stampverbs.go` change, and that file is another session's open work, so it is
     not done here.

5. **Tests (annot's own, per the task).**
   - `lexctx_test.go`:
     - Python `runLex` `{"bom-comment", "﻿# c\nimport os\n", "#c", 0}`.
     - Python `docs` row for the bom_doc.py source: lines 1–4, content
       `"Doc after a BOM."`.
     - Go `{"bom-comment", "﻿"+gl+"\npackage a\n", "#c", 0}`.
     - Kotlin `{"bom-comment", "﻿"+kl+"\nclass T\n", "#c", 0}` plus
       `Classify(Kotlin, "﻿package a\n\nclass T\n").Package == 1` (if step 0
       says true; else a row pinning `"cc"`).
     - Bash `{"bom-is-a-word", "﻿# header\n# real\n", "c#", 0}`, which pins
       "not special".
   - `rewrite_test.go` new `TestByteOrderMark`, the t1954 case and its neighbours:
     - **read:** bom_doc.py parses with one file-level cover `src/bom_doc.py`,
       `Line.No == 3`, `Docstring == true`.
     - **refused docstring write:** `PlanCovers(…, "src/bom_doc.py", …)` is
       `ErrDocstring`.
     - **placement after DocEnd + BOM preserved:** covering `src/new.py` plans
       `InsertAfter` line 4. `Apply` yields exactly
       BOM + `"""Doc after a BOM.\n\ntestmap:covers src/bom_doc.py\n"""\n# testmap:covers src/new.py @2026-10-12/aaaaaaaaaa\nprint("bom")\n`.
     - **line-1 comment re-stamped in place, BOM kept:** a `.py`, `.go` and `.kt`
       whose line 1 is BOM + `<leader> testmap:covers src/a… @2026-01-01/0123456789`.
       Plan → `Replace` line 1. Apply → the BOM is still byte 0 and the stamp is new.
     - **nothing above a BOM:** `﻿import os\n` and
       `﻿# testmap:unit TestA\n…` (file-level covers) → `Placement`/`PlanCovers`
       return `ErrByteOrderMark`.
     - **bash not special:** `﻿echo hi\n` → plan at 0 → Apply writes
       `# testmap:covers …\n﻿echo hi\n`.
   - `TestApplyRefusesNonComments` table gains hand-built `InsertAfter` line 0 edits
     on `﻿import os\n` (`.py`) and `﻿package a\n` (`.go`). Want
     `ErrNotComment` and the file unchanged. These bypass `Placement`, so they prove
     the raw-byte guard on its own. Each fixture is red on current code for a
     different reason:
     - Python: Apply succeeds and writes, because the moved BOM lexes as a name.
     - Go: the reparse refuses with a wrapped `SyntaxError`, not `ErrNotComment`.

     So `errors.Is(err, ErrNotComment)` passes only through the new guard, and the
     Go row confirms the guard precedes the reparse.
   - `TestByteOrderMarkPythonRuns` (skip without `python3`, the
     `TestVerifyKeepsBashDataUnchanged` pattern): run bom_doc.py with `python3`
     before and after the `src/new.py` Apply. Same output `bom\n`, exit 0 both times.
     This pins the behaviour the defect broke.
   - **Red first:** write the tests before the code changes and run them. They must
     fail on the current code (the docstring is not read, the insertion lands at 0,
     python3 exits 1 after Apply). Then implement until green.

6. **Step 9 (Post-Implementation)** of the task workflow: review, commit, archival.
   After the commit, Step 8e sends a note to **t1954_4**: the BOM defect is fixed at
   `<sha>`, `python/bom_doc.py` should drop to 0 safety counts in its rerun at the
   then-current annot commit, and `seam.patch` still applies (dry-run verified).
   Moving `baseline/PIN` and regenerating results stays t1954_4's work.

## Verification

- Baseline first: `cd goengines && go test ./internal/testmap/annot/` on the current
  tree. If another session's WIP in `hook.go`/`stampverbs.go` breaks the build,
  verify in an isolated tree instead: `git archive HEAD goengines` into the
  scratchpad, then copy in only this task's files.
- `gofmt -l internal/testmap/annot` (empty), `go vet ./internal/testmap/annot/`,
  `go test ./internal/testmap/annot/ ./cmd/ait-testmap/` (all existing goldens
  unchanged, so no non-BOM placement moved), and the red→green run of the new tests.
- Seam compatibility: in the scratchpad, `git archive HEAD goengines | tar -x`, copy
  in the modified `lang.go`/`lexctx.go`, then
  `patch -p1 --dry-run < aidocs/testing_engine/t1954_parser_research/baseline/seam.patch`
  must apply cleanly.
- End-to-end through the CLI: build `ait-testmap` from the checkout into the
  scratchpad. In a scratch git repo holding the bom_doc.py fixture plus
  `src/new.py`, run `ait-testmap annotate tests/bom_doc.py src/new.py`, then
  `python3 tests/bom_doc.py` (exit 0, prints `bom`, the BOM is still byte 0).
  `annotate tests/bom_doc.py src/bom_doc.py` must report the docstring skip and write
  nothing.

## Risk

### Code-health risk: low
- Behaviour change is gated on one precondition (line 1 starts with a BOM and `Lang.SkipsBOM`); every non-BOM file takes the current path, and the existing placement/parse goldens pin that · severity: low · → mitigation: none (Verification: goldens unchanged)
- Edits in `lexctx.go`/`lang.go` could disturb the t1954 `seam.patch` context and break t1954_4's pin move · severity: low · → mitigation: none (design keeps `Classify`'s head untouched; Verification runs `patch --dry-run`)
- Another session's uncommitted WIP in the same package (`hook.go`, `stampverbs.go`) can make package test runs fail for unrelated reasons, and a broad commit could sweep it in · severity: low · → mitigation: none (isolated-tree fallback in Verification; path-scoped commit)

### Goal-achievement risk: low
- Kotlin's BOM behaviour is an assumption until probed; a wrong guess would mis-scope the fix · severity: low · → mitigation: none (step 0 probe with a no-BOM control under the same invocation and an explicit inconclusive outcome)
- The no-slot case is refused rather than placed; the task explicitly allows "insert after it, or refuse" · severity: low · → mitigation: none
- The t1954 harness confirmation needs a PIN move, which this task does not do; confirmation comes from annot's own tests plus a python3 execution test, and t1954_4 gets a note to rerun · severity: low · → mitigation: none
