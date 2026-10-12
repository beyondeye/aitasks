---
Task: t1853_2_m2_2_annotation_grammar_rewriter.md
Parent Task: aitasks/t1853_testmap_m2_registry_and_map_model.md
Sibling Tasks: aitasks/t1853/t1853_1_*.md, aitasks/t1853/t1853_3_*.md, aitasks/t1853/t1853_4_*.md, aitasks/t1853/t1853_5_*.md, aitasks/t1853/t1853_6_*.md
Archived Sibling Plans: aiplans/archived/p1853/p1853_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-12 15:34
---

# Plan: t1853_2 — M2.2 Annotation grammar and rewriter

## Context

Parent goal: M2, the registry and map model (everything that reads and writes
`aitestmap/` without running a test). This child is **M2.2, the annotation
grammar and rewriter**, wave **A**. It covers the `testmap:` grammar, the stamp
format, and the only writer of `testmap:` lines. Provider: M2.1 (`t1853_1`,
landed in `0d04347ab`, contract recorded in the proposal at `c07193265`).

Why: `scan` and `check` exist but have no annotation source. Production
`scan` exits 3 with `INPUT_UNAVAILABLE:annotations`. Several later modules need
this child's rewriter API before they can start: M4.2 (`stale --confirm*`),
M6.3 (`onboard adopt`), M7.2 (`--agent-verdicts`), M7.4 (`--author`), and M2.6
(the post-re-stamp hook).

**Automation-first (user directive, 2026-10-11).** Human review belonged to an
older design. No path shipped here may make a human action a precondition.
The actor passed to the hook is data, not a gate.

## Proposal reading list

`aidocs/testing_engine/n014_explorer_006_proposal.md`:
- the Module Map row M2.2
- *Annotation scanner and rewriter (M2.2)*
- *Vocabulary* (Edge, stamp)
- *Placement: comment lines only*
- *Invariants* (6)
- `assumption_annotation_is_comment_only`
- *Registry loader and writer* (the re-stamp provenance rule)
- *Freshness (M4.2)* (who writes stamps)
- *Enumeration and reconciliation* (the scan/check contract)

Also:
- the parent plan's Deviations 2, 4 and 8
- the M2.1 archived plan
- `goengines/README.md`
- the brainstorm lineage `.aitask-crews/crew-brainstorm-1812/br_proposals/`
  (n002–n006), for the key argument forms that the final proposal only names

## Owned files / provides / consumes

- **Owns:**
  - `goengines/internal/testmap/annot/**` (new), except the later
    `--suggest` / `--from-body` (M2.3) and `--author` (M7.4) arms
  - `goengines/cmd/ait-testmap/annotate.go` (new verb glue)
  - the `annotate` and `verify` rows in `verbs.go`
  - the placement goldens
  - one new `bench/baseline.txt` line
- **Named extensions of other owners** (each minimal):
  - `scancheck.go` `testmapInputs` — M2.1's declared extension point
  - `gitx/lsfiles.go` — an additive method in M1.2's shared git door
  - the `TestStubsExit64` skip list in `main_test.go`
  - one assertion in `scancheck_test.go` (forced by the wiring; see D11)
  - README *Layout* / *Interfaces* rows
  - an additive proposal paragraph and Line-protocol index row
- **Provides:**
  - the grammar (`annot.ParseFile`)
  - the stamp format (`annot.Stamp`)
  - the rewriter API (`annot.Apply`, `annot.PlanCovers`)
  - `annot.Source`, the `registry.AnnotationSource` implementation
  - the post-re-stamp hook (`annot.RegisterRestampHook`)
  - the annotate arm table, which M2.3 / M7.4 fill
- **Consumes:**
  - M2.1: `registry.ParseID` / `CheckPath` / `LoadConfig` / `Config.Excluded` /
    `ErrAbsent` / `Dir`, and the `AnnotationSource` interface
  - M1.2: `gitx.BlobDigest`, `gitx.Repo.ObjectFormat`, `lineproto`,
    `fixture.New`, `benchgate`

## Step 0 — Reality check (EXECUTED 2026-10-12, main @ c07193265)

### 1. Sources re-read

- The Module Map row M2.2
- *Annotation scanner and rewriter*
- *Placement*
- Invariant 6
- `assumption_annotation_is_comment_only`
- the *Cross-module interfaces* row (`testmap:` grammar, stamp format and
  rewriter API, M2.2 → M4.2 / M6.3 / M7.2 / M7.4)
- the M2.6 / M7.4 rows that name the hook and `--by`

### 2. Providers as they exist now

| provider | landed by | state in tree |
|---|---|---|
| `registry.AnnotationSource` | t1853_1 `0d04347ab` | `Annotations(ctx, root) ([]FileAnnotations, error)`. `FileAnnotations{Path, Units[]{Member, Line, Covers[]{Source, Line, StampedAt, StampedBlob}}}`; the file-level unit has `Member ""`, comes first, and has `Line` 0. `readInputs` validates paths and members with the id grammar → `INPUT_ERROR:annotations\|…` exit 3 |
| wiring point | t1853_1 | `cmd/ait-testmap/scancheck.go` `var testmapInputs = func() registry.Inputs { return registry.Inputs{} }`; both inputs nil → `INPUT_UNAVAILABLE:annotations` (annotations is checked first) |
| id grammar | t1853_1 | `registry.ParseID`, `ID.Valid`, `CheckPath` exported; `checkFragment` is unexported (member validation goes through `ParseID("<path>#<m>")`) |
| config | t1853_1 | `registry.LoadConfig(root)` (absent file → defaults), `Config.Excluded(path)`; `registry.Dir`, `registry.ErrAbsent` |
| writer | t1853_1 | `registry.WriteFile` writes **mode 0644**, so it is unusable for test files: bash tests are executable |
| verb table | t1852_2 | `stub("annotate")`, `stub("verify")`; `TestStubsExit64` skips `version`, `scan`, `check` |
| `gitx` | t1852_2 | `BlobDigest(data, format)`, `Repo.ObjectFormat`. `RunEnv` **discards stderr on exit 0** (so `git ls-files` warnings would be lost) |
| M2.6 (hook filler) | — | not landed (t1853_6 Ready). The hook ships empty |
| M2.3 / M7.4 arms | — | not landed |
| M3.1 lister | — | not landed. Production `scan` / `check` stay `INPUT_UNAVAILABLE:lister` after this child |
| `aitestmap/` | — | none in any repository |

Parent anchors re-verified: module path, deps allowlist (`yaml.v3`,
`doublestar/v4`, `x/sync`), and the Invariant 4–5 tripwire. `.aitask-crews/`,
`aiwork/` and `website/node_modules/` are gitignored here, and this matters for
D1.

### 3–4. Differences and decisions

| # | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|
| D1 | `scan` "reads each annotated file" from the runners' `list` (n006); the final proposal is silent on which files | "the annotation source scan reads" | the interface takes only `root`; there is no lister (M3.1); a raw tree walk here covers 15,163 files including `node_modules` and the nested worktrees under `aiwork/` (every test twice) | **Adapt + record in the proposal.** The universe is the **git-visible files**: `git ls-files -z --cached --others --exclude-standard`, minus `exclude:`, minus non-regular files (symlinks, files deleted since the index), restricted to files with a known language. Only files carrying ≥1 annotation are returned. A `git ls-files` that writes **anything to stderr** (it exits 0 on an unreadable directory) is an error, so it fails closed. New method `gitx.Repo.ListFiles` |
| D2 | the keys are named; their argument forms are not | — | — | **Adapt (from the lineage n003/n004).** `unit <Member>`; `kind <word>`; `covers <path> [@<date>/<blob10>]`; `area <name>…`; `scope <glob>…`; `trigger <glob>…`; `reads <glob>…`; `axis <axis>.<facet>=<value>`; `reviewed <YYYY-MM-DD>`; `runner <name>`; `needs <resource>…`; `batch yes\|no`. A single-valued key repeated in one block, a duplicate `covers <src>` in one block, a duplicate member, an extra token, or an empty or unknown key → `SyntaxError{path, line, reason}` |
| D3 | lineage leaders `#`, `//`, `--`; placement is fixed for bash / Python / Go / Kotlin only | — | — | **Adapt.** The v1 language table has exactly the four languages that have a placement rule: bash (`.sh`, `.bash`, or no extension with an `sh`/`bash` shebang), Python (`.py`, or a python shebang), Go (`.go`), Kotlin (`.kt`, `.kts`). Any other file has no leader: the source skips it and the rewriter refuses it with `no-leader` |
| D4 | the line classes for `annotate` / `verify` are undefined | — | — | **Revise the proposal (additive).** `STAMP:<test>\|<source>\|<date>/<blob10>\|<added\|restamped\|current>`, `STAMP_SKIP:<test>\|<source>\|<missing\|not-a-file\|docstring>`, `STAMP_REFUSED:<test>\|<no-leader\|no-member-block\|excluded\|missing\|not-a-file\|uncertain-context>`, final `STAMPS:<added>\|<restamped>\|<current>\|<skipped>`; stderr `ANNOT_INVALID:<path>\|<line>\|<reason>` (3), `REWRITE_CONFLICT:<path>\|<line>` (75), `RESTAMP_HOOK_ERROR:<detail>` (3); `WROTE:<path>` and `TESTMAP_ABSENT:` are reused |
| D5 | the hook carries "the actor"; M7.4 adds `--by` for `--author` | — | — | **Adapt.** `annotate` / `verify` take `--by human:<email>\|agent:<agent-string>\|auto`. The default is `agent:$AIT_AGENT_STRING` when that variable is exported, otherwise `unspecified`. Only an explicit `human:` is a human, so a missing actor never deletes provenance (the safe direction: provenance is kept). A malformed `--by` → 64. M7.4 reuses the flag |
| D6 | "verify re-stamps" | — | — | **Adapt.** A covers line whose stamp already names the current blob is left **untouched** (no date churn; a re-run is byte-identical) and reported `current`. It is still passed to the hook with state `current`, so M2.6 can treat a human `verify` as a confirmation |
| D7 | docstrings are read-only (Invariant 6) | — | — | **Adapt.** A `covers` line inside a Python module docstring is read, but it is never re-stamped (`STAMP_SKIP:…\|docstring`, exit 1). `testmap:unit` inside a docstring is a `SyntaxError` (a member block cannot open inside `__doc__`) |
| D8 | — | — | `registry.WriteFile` forces 0644 | **Adapt.** The rewriter writes atomically: a temp file in the same directory, the **original mode** kept, then a rename. Line endings (CRLF) and a missing final newline are preserved |
| D9 | Invariant 6: adoption writes comment lines only | — | Go tests here embed fixture text in raw strings; bash tests use heredocs | **Adapt (review finding, blocking).** Annotations are read, and written, **only on lines a lexer proves are real comment lines**, in every language. `annot/lexctx.go` classifies every line as `Code`, `Comment` or `Literal` (inside a string, heredoc, raw string or block comment). Go uses `go/scanner`; bash, Python and Kotlin use small lexers that model each language's multi-line constructs. A file whose lexer ends inside an open construct is **uncertain**: a read of it is a `SyntaxError` (when it carries `testmap:`), and any write to it is refused. The rewriter enforces this itself (see `Apply`), so the safety does not depend on `exclude:` or on the caller. The look-alike lines stay byte-identical, as fixtures prove |
| D17 | the rewriter edits by `(file, line, current text)` | — | — | **Adapt (review finding, blocking).** The text of one line does not pin *which block owns it*: if an earlier opener is renamed `A`→`B`, an unchanged target line silently moves to `B`. So every `Edit` carries its expected owner (`Member`, `Source`), and `Apply` re-parses the result: each edited line must be a covers line of `Source`, owned by block `Member`. Edit sets planned in-process also carry a whole-file `Snapshot` digest, and any change since planning conflicts. Both checks report `REWRITE_CONFLICT` |
| D18 | — | — | `registry/walk.go`'s view checks every parent component; a final-component `Lstat` alone lets `link/test.sh` escape the root | **Adapt (review finding, blocking).** All annot file I/O goes through `os.Root` (go1.27.1: `OpenFile`, `Rename`, `Lstat`, `ReadFile`), so nothing escapes the root even under a race. On top of that, `lstatNoFollow` refuses **any** symbolic-link component, parent or leaf, including links that stay inside the root (never followed, as in `walk.go`). This applies to reads (`Source` skips such a file), source hashing (`STAMP_SKIP …\|not-a-file`), verb targets (`STAMP_REFUSED …\|not-a-file`) and writes (`Apply` refuses) |
| D10 | M2.6 fills the hook by actor | — | registry cannot import annot (annot imports registry) | **Adapt.** The hook lives in `annot` (`RegisterRestampHook`, called from an `init` in M2.6's own file in `annot`), which matches p1853_6's "fill of M2.2's post-re-stamp hook in `annot`". It runs once, after every file of the invocation was written; on any earlier error it does not run (provenance is kept — the safe direction) |
| D11 | — | — | `TestScanCheckInputUnavailable` expects `INPUT_UNAVAILABLE:annotations` | **Adapt.** Wiring annotations makes the production answer `INPUT_UNAVAILABLE:lister`; edit only that expected string |
| D12 | `--suggest` / `--from-body` (M2.3), `--author` (M7.4) are arms of `annotate` | same | — | **Adapt.** `annotate.go` has `annotateArms map[string]func(env, []string) int`. The three reserved flags print `NOT_IMPLEMENTED:annotate --<arm>` and exit 64 until an arm registers |
| D13 | `<blob10>` | — | `BlobDigest` supports sha1 / sha256 | Stamp = the first 10 hex digits of the source's blob id under the repository's object format (`ObjectFormat`, once per invocation); for sha256 repositories too (lineage n003) |
| D14 | kind vocabulary is M2.5's | — | — | `kind` is parsed as one bare word; M2.5 enforces the vocabulary |
| D15 | `REWRITE_CONFLICT` | — | exit 75 = refused | `REWRITE_CONFLICT` exits **75**: retryable once the caller re-reads or re-scans |
| D16 | the scoped keys (`area`, `scope`, `trigger`, `reads`, `axis`, `runner`, `needs`, `batch`) feed M2.4 / M2.5 / M3 | — | `registry.UnitAnnotation` carries covers only | `annot.File` keeps every key with its line; the adapter maps covers only. M2.4 / M2.5 extend `UnitAnnotation` additively and fill it in `annot/source.go`, as named extensions (noted). `reads` "helper files only" is enforced by M2.5, not by the parser |

### 5. Notes

Sent after the commit (post-phase `interface_notes_downstream`).

### 6. Ownership

Every touched file is either M2.2-owned or one of the named extensions listed
above.

## Design — package `goengines/internal/testmap/annot`

### `lang.go`

- `type Lang struct{ Name, Leader string; Docstring bool }`, with the values
  `bash`/`#`, `python`/`#`/docstring, `go`/`//`, `kotlin`/`//`.
- `LangOf(path string, data []byte) (Lang, bool)`: by extension; for a file
  with no extension, by its shebang.

### `lexctx.go` — the comment-context classifier (D9)

```go
type LineClass uint8 // Code | Comment | Literal
type Context struct {
    Class     []LineClass // per line: Comment = the line starts (after whitespace) with a real leader in code context
    Docstring [2]int      // Python module docstring line span, 0,0 when none
    Uncertain *Unclosed   // {Line int; Construct string}: EOF inside an open construct
}
func Classify(l Lang, data []byte) Context
```

The class of a line is the lexer state at its first byte. Any state other than
code makes the line `Literal`. Unmodelled forms fall to `Literal` or
`Uncertain`, never to `Comment`: a misclassification may only lose an
annotation, never write into data.

- **Go:** `go/scanner` with `ScanComments`. A `//` comment token at the line's
  first non-blank column → `Comment`. Lines inside raw strings or `/* */` →
  `Literal`. A scanner error → `Uncertain`.
- **Bash:** a context stack: top level, `'…'`, `"…"` (with `\` escapes),
  `$'…'`, backticks, `$(…)` (paren depth, nesting contexts), `$((…))` /
  `((…))` (where `<<` is a shift).
  - `#` starts a comment only at the start of a word (line start, whitespace,
    or one of `;`, `&`, `|`, `(`, `)`). So `${x#y}`, `${#a[@]}` and `a#b` are
    not comments.
  - Heredocs `<<[-]WORD` (`'W'`, `"W"`, `\W`, partly quoted words) are queued
    at the opener. `<<<` is not a heredoc. **A queued body starts only after
    the next *newline token*:** a `\n` met in code context (top level, or
    inside `$(…)`) that is neither a backslash-newline continuation nor
    inside a quote. A comment's terminating newline counts.
  - So a body is delayed past continuation lines and past a quoted string
    that spans lines, exactly as bash does (verified 2026-10-12):
    - `consume <<EOF \` / `EOF arg` / `# testmap:covers …` / `EOF` feeds the
      third line to `consume` as data
    - `consume <<EOF "a` / `EOF` / `b"` / … starts the body after `b"`
  - Queued bodies are read in order, each `Literal`, each up to its delimiter
    line (leading tabs stripped for `<<-`).
  - **A line that begins inside a backslash continuation is `Code`**, never
    `Comment`: it belongs to a command already in progress. This means an
    insert after a line ending in `\` fails `Apply`'s after-check.
  - **Refuse what is not modelled:** a heredoc opener inside backticks or
    inside `$((…))` / `((…))`, or bodies still queued at EOF →
    `Uncertain{opener line, "heredoc"}`. Never a guess.
- **Python:** a stack of code (bracket depth) and strings (quote, triple, raw,
  f), with string prefixes (`rb`, `Rb`, `f`, `fr`, `u`, …), `\` escapes
  (including in raw strings, for termination), and backslash-newline
  continuation. f-string replacement fields push a code context, which can
  hold nested strings (3.12) and format specs.
  - The module docstring is the first statement when that statement is a
    plain (non-f) string literal; its span is recorded.
  - `#` in code context starts a comment.
- **Kotlin:** code (brace depth), `//`, nested `/* */`, `"…"` with `\` escapes
  and `${…}` templates (code context), `"""…"""` raw strings with templates
  (a run of ≥3 quotes closes, extra quotes are content), and char literals
  `'x'` / `'\''` / `'"'`.

### `grammar.go`

```go
type Line struct{ No int; Text string; Docstring bool } // where a key was read
type Cover struct{ Source string; Stamp Stamp; Line Line } // Stamp zero = unstamped
type Unit struct {
    Member string; Opener Line // Member "" = file-level; Opener.No 0
    Kind, Runner, Batch, Reviewed *KeyVal; Covers []Cover
    Areas, Scopes, Triggers, Reads, Needs, Axes []KeyVal
    Last int // last annotation line owned by this block (0 = none)
}
type File struct{ Path string; Lang Lang; Units []Unit; Lines []string; CRLF, FinalNL bool }
type SyntaxError struct{ Path string; Line int; Reason string }
func ParseFile(path string, data []byte) (*File, error) // ErrNoLeader when the language is unknown
```

- **Annotation line:**
  - a line `Classify` marks `Comment`, whose text matches
    `^[ \t]*<leader>[ \t]*testmap:<key>([ \t]+<args>)?[ \t]*\r?$`
  - `Literal` and `Code` lines are never read, whatever their text
  - the key is `[a-z]+`; anything else after `testmap:` → `SyntaxError`
    ("empty key" / "unknown key")
  - prose (`# Covers: …`, ``// `testmap:unit` ``, a trailing
    `code # testmap:…`) never matches
- **Uncertain file:** a `Context.Uncertain` file whose data contains
  `testmap:` → `SyntaxError{line: the opener, "cannot determine comment
  context: unterminated <construct>"}`. A file without the token is never
  lexed.
- **Python module docstring:** the lines inside `Context.Docstring` whose
  trimmed content (after the opening quotes / before the closing ones) starts
  with `testmap:` are read with `Docstring: true`.
- **Block ownership by position:**
  - everything before the first `unit` belongs to the file-level unit
  - each `unit` owns its lines up to the next one
- **Argument validation:**
  - paths: `registry.CheckPath`
  - members: `registry.ParseID(path+"#"+m)`
  - globs: `doublestar.ValidatePattern`
  - dates: `time.Parse(DateOnly)`
  - axis: `<a>.<f>=<v>`, no whitespace, `|`, `#` or `@`
  - names / words: non-empty, no `|` or control characters

### `stamp.go`

- `type Stamp struct{ Date, Blob string }`
- `ParseStamp("@YYYY-MM-DD/<10 lowercase hex>")`
- `String()`
- `IsZero()`
- `NewStamp(today time.Time, content []byte, format string)`, built from
  `gitx.BlobDigest(...)[:10]`
- `var now = time.Now`
- `SourceStamp(r *os.Root, src, format)`: `lstatNoFollow` must report a
  regular file, otherwise `ErrMissing` or `ErrNotAFile`. The content is read
  through `r`.

### `fsroot.go` — confined, no-follow file access (D18)

```go
func openRoot(root string) (*os.Root, error)
func lstatNoFollow(r *os.Root, rel string) (fs.FileInfo, error) // every component via r.Lstat
func readNoFollow(r *os.Root, rel string) ([]byte, fs.FileMode, error)
```

- `lstatNoFollow`: every proper prefix of `rel` must be a real directory.
  - a symbolic-link or non-directory component → `ErrNotAFile`
  - `ENOENT` at any component → `ErrMissing`
  - the leaf must be a regular file (`ErrNotAFile` otherwise)
  - any other error is returned unchanged
- `readNoFollow` re-checks, then reads through `r.OpenFile`.
- Every read, hash and write in `annot` goes through these helpers, and
  through `*os.Root`. No `os.ReadFile` or `os.WriteFile` is called on a
  joined path.

### `rewrite.go` — the rewriter API (the only writer of `testmap:` lines)

```go
type EditKind int // Replace | InsertAfter
type Edit struct {
    Kind   EditKind; Line int; Want string; New string // one covers line per edit
    Member string // expected owning block ("" = file-level) — D17
    Source string // the covers source the edited line must carry — D17
}
type EditSet struct{ Path, Snapshot string; Edits []Edit } // Snapshot: blob digest of the planned-from bytes ("" = none)
type ConflictError struct{ Path string; Line int; Reason string } // Line() → REWRITE_CONFLICT:<path>|<line>, exit 75
var ErrNotComment, ErrUncertainContext, ErrNoLeader, ErrNoMemberBlock error
func Apply(root string, set EditSet) (changed bool, err error)
func RestampLine(text string, s Stamp) (string, error)   // keeps indent, leader, spacing and path bytes; replaces or adds only the stamp
func PlanCovers(f *File, member, source string, s Stamp) (Edit, error) // replace the existing covers line, or insert at the placement
func (f *File) Placement(member string) (after int, indent, leader string, err error)
func (f *File) Snapshot() string
```

**`Apply`** (the only writer):
1. `openRoot`, then `readNoFollow(path)`. A symbolic-link component or a
   missing file is refused (D18).
2. **Snapshot:** when `set.Snapshot` is non-empty and differs from the digest
   of the bytes just read → `ConflictError{Reason: "snapshot"}`.
3. Every edit's `Want` must equal the current text of its `Line` (without
   `\r`), otherwise `ConflictError{line}`. For an insert at `Line` 0, `Want`
   is `""`.
4. **Context before:** `Classify` the current bytes. An uncertain file →
   `ErrUncertainContext`. The line of each `Replace` must be classed
   `Comment` (so never `Literal`, never the docstring), otherwise
   `ErrNotComment`.
5. Apply the edits bottom-up.
6. **Context after (Invariant 6, enforced here, not by callers):**
   - `Classify` the result: it must not be uncertain
   - every edited line must be `Comment`
   - every untouched line must keep both its **bytes and its class**, so an
     insertion can never change what any other line means
   - re-parsing must succeed
7. **Ownership after (D17):** each edited line must parse as
   `testmap:covers <Source>`, owned by block `Member`. Otherwise
   `ConflictError{Reason: "ownership"}`, naming that line.
8. Atomic, confined write:
   - `r.OpenFile(".<name>.<rand>", O_WRONLY|O_CREATE|O_EXCL, 0o600)` in the
     same directory
   - write, then `f.Chmod(original mode)` on the handle, `Sync`, `Close`
   - re-read the original through `r`; if it changed →
     `ConflictError{Reason: "concurrent"}`
   - `r.Rename(tmp, path)`; on any failure the temp file is removed
9. Line endings follow the file's: CRLF, and a missing final newline, are both
   kept.

**`Placement(member)` — where a new covers line goes:**
- **Block already has a comment annotation** (not in the docstring): after the
  block's last one, with its indent and leader.
- **Member block without one:** right after its `testmap:unit` opener, with
  the opener's indent.
- **File-level block without one — the fixed position.** Computed from the
  `Context` classes, never from raw text:
  - bash: after the shebang and the leading block of `Comment` lines
  - Python: after the module docstring, else after the shebang / encoding /
    leading `#` block
  - Go: right after the package clause (`go/scanner`)
  - Kotlin: after the last top-level `Code` line starting with `import`, else
    after `package`, else after the leading comment block (`/* … */` license
    headers are `Literal` and skipped)
- **Guard:** if the fixed position falls after the first `unit` opener, insert
  just before that opener with its indent. A new file-level line must never
  join a member block.
- **Member** with no `testmap:unit` block → `ErrNoMemberBlock`.

### `hook.go`

```go
type ActorKind int // Unspecified | Human | Agent | Auto
type Actor struct{ Kind ActorKind; Value string }   // ParseActor("human:a@b"|"agent:<s>"|"auto"); String()
type EdgeState string // "added" | "restamped" | "current"
type Restamp struct{ Test registry.ID; Source, File string; Line int; Before, After Stamp; State EdgeState }
type RestampHook func(ctx context.Context, root string, actor Actor, edges []Restamp) error
func RegisterRestampHook(h RestampHook)
func runRestampHooks(ctx context.Context, root string, a Actor, edges []Restamp) error // *HookError → RESTAMP_HOOK_ERROR, exit 3
```

### `stampverbs.go` — the engines behind the verbs

```go
type Result struct{ Stamps []StampLine; Skips []SkipLine; Refused []RefuseLine; Wrote []string }
func Annotate(ctx context.Context, root string, test registry.ID, sources []string, actor Actor) (*Result, error)
func Verify(ctx context.Context, root string, targets []registry.ID, actor Actor) (*Result, error)
```

**Common preamble:**
- `aitestmap/` must exist, otherwise `registry.ErrAbsent` (exit 2)
- `LoadConfig` (a broken config → its error, exit 3)
- `ObjectFormat` (a git failure → exit 3)

**Annotate** works on one file and is all-or-nothing:
- Refuses the target (`STAMP_REFUSED`):
  - a variant in the id (exit 64, at parse time in the glue)
  - an excluded path
  - a missing file, or one that is not a regular file — including a
    symbolic-link component anywhere on the path
  - no leader
  - an uncertain lexical context
  - `#member` with no block
- A missing source or one that is not a regular file → `STAMP_SKIP` for it,
  **nothing is written**, and no `STAMP:` lines are printed (exit 1).
- Otherwise, for each source in argument order (deduplicated):
  - an existing covers line with the current blob → `current`
  - an existing covers line with another blob, or unstamped → re-stamped
    (`restamped`)
  - no covers line → inserted at the placement (`added`)
- One `Apply` of an `EditSet` carrying the parse's `Snapshot`, then the hook
  runs with every edge.

**Verify:**
- Each target `<path>` covers every block of the file; `<path>#<m>` covers
  that member only. Overlapping targets are deduplicated by line.
- For each covers line in scope:
  - a missing source → `STAMP_SKIP missing`
  - a covers line in the docstring → `STAMP_SKIP docstring`
  - the current blob → `current`
  - otherwise → `restamped`
- One `Apply` per file. The hook runs once, after every write succeeded.
- Exit 1 when anything was skipped or refused, else 0.

### `source.go` — `type Source struct{}` implements `registry.AnnotationSource`

1. `LoadConfig(root)` for `exclude:`.
2. `gitx.Repo{Dir: root}.ListFiles(ctx)`.
3. Skip excluded paths, paths with no language, and any path
   `lstatNoFollow` (through one `os.Root`) does not report as a regular file:
   - a symbolic-link leaf or parent component is skipped, never followed (the
     index can list `dir/t.sh` after `dir` was replaced by a link)
   - `ErrMissing` is skipped, because a deleted file carries no annotations
   - any other error is returned
4. Read the file. Cheap prefilter: `bytes.Contains(data, "testmap:")`.
5. `ParseFile`. The first `SyntaxError`, in path order, is returned as the
   error; M2.1 turns it into `INPUT_ERROR:annotations|<path>:<line>: <reason>`,
   exit 3.
6. Map to `registry.FileAnnotations`: the file-level unit first (`Line` 0),
   then the members in file order. Each cover carries its line, and
   `StampedAt` / `StampedBlob` = `Stamp.Date` / `Stamp.Blob`.
7. Output sorted by path.

### `gitx/lsfiles.go` (additive)

- `func (r Repo) ListFiles(ctx) ([]string, error)` runs
  `ls-files -z --cached --others --exclude-standard`.
- Paths are deduplicated (unmerged stages repeat) and sorted.
- **Any stderr output, even with exit 0, is an `*Error`.** The scrubbed `Env`
  is reused.

### Verb glue `cmd/ait-testmap/annotate.go`

- `annotate [--by <actor>] [--json] <test> <source>...`
  - `<test>` is `<path>[#<member>]`; a variant → usage 64
  - `--suggest`, `--from-body` and `--author` dispatch through `annotateArms`;
    an arm that is not registered → `NOT_IMPLEMENTED:annotate --<arm>`, 64
- `verify [--by <actor>] [--json] <test>...` (≥1 target)
- **Output:**
  - `STAMP_REFUSED` / `STAMP_SKIP` / `STAMP` lines in target and argument
    order
  - `WROTE:<path>` per file
  - `STAMPS:<added>|<restamped>|<current>|<skipped>`
  - `--json` emits `Result`
- **Errors:**
  - `ErrAbsent` → `TESTMAP_ABSENT:aitestmap/` (2)
  - `*SyntaxError` → `ANNOT_INVALID` (3)
  - `*ConflictError` → `REWRITE_CONFLICT` (75)
  - `*HookError` → `RESTAMP_HOOK_ERROR` (3)
  - anything else goes through the existing `reportError` (3)
- **Exit contract:** `{0, 1, 2, 3, 64, 75}`.
- `verbs.go`: two rows, `{Name: "annotate", Run: runAnnotate, Exits: stampExits}`
  and the same for `verify`.
- `scancheck.go`: `testmapInputs` returns
  `registry.Inputs{Annotations: annot.Source{}}`.

## Implementation steps

1. `gitx/lsfiles.go` + `gitx_test.go` cases:
   - tracked, untracked and ignored files (the ignored one is absent)
   - a deleted tracked file is still listed (the source skips it)
   - an unreadable untracked directory → error (`t.Skip` when euid is 0;
     restore the mode in `t.Cleanup`)
2. `annot/lang.go`, `stamp.go` + tests: the language table, shebang detection,
   and a stamp round trip.
   - `ParseStamp` rejects uppercase, 9 or 11 hex digits, and a bad date.
   - `NewStamp` equals `git hash-object` cut to 10 digits, in sha1 and sha256
     fixture repositories.
3. `annot/lexctx.go` + `lexctx_test.go`: per-language class tables (a fixture
   → the expected `[]LineClass`).
   - **Literal look-alikes (D9):** each of these contains
     `# testmap:covers x @2026-01-01/0123456789` (or `// …`) lines, all
     classed `Literal`:
     - bash heredocs `<<EOF`, `<<-'EOF'`, `<<"E"OF`, and a heredoc inside
       `$(cat <<EOF … EOF)`
     - **delayed bodies:** `consume <<EOF \` + `EOF arg` +
       `# testmap:covers …` + `EOF`, where the `EOF arg` line is `Code` and
       the annotation-shaped line is `Literal`; and an opener followed by a
       `"…"` spanning lines, with a body after the closing quote
     - a heredoc opener inside backticks → `Uncertain`
     - bash multi-line `"…"` / `'…'` / `$'…'` strings, and a backtick spanning
       lines
     - Python non-docstring `"""…"""` / `r'''…'''` / `f"""{x["k"]}…"""`
     - Kotlin `"""…${"\"\"\""}…"""""` and a nested `/* /* */ */`
     - Go raw strings and `/* */`
   - **No false negatives:** a real comment annotation *after* each of these is
     still `Comment`:
     - `<<<` here-strings, `$(( 1 << 2 ))`, `${x#y}`, `${#a[@]}`, `a#b`,
       `case … in a) …;;`
     - Python `'#'` and `"""` inside a `'…'`
     - Kotlin `"//"` and `'"'`
   - **Uncertain:** an unterminated heredoc, triple-quoted string, raw string
     or block comment → `Uncertain{line, construct}`.
4. `annot/grammar.go` + `grammar_test.go`: parse goldens per language,
   `testdata/parse/<case>.<ext>.in` → `<case>.golden` (a JSON dump of
   `File.Units`; the `.in` suffix keeps fixtures out of any language table).
   The `-update` flag regenerates them. Cases:
   - bash / Python / Go / Kotlin with a file-level block and two members
   - Python docstring read (`Docstring: true`), and a `unit` inside the
     docstring refused
   - `# Covers:` prose and the `` `testmap:` `` backtick prose not matched
   - none of the step-3 look-alike lines is read, in any language
   - an uncertain file carrying `testmap:` → `SyntaxError` at the opener line
   - CRLF input
   - an error table: an unknown key, an empty key, a duplicate member, a
     duplicate `kind`, a duplicate `covers` of one source, an extra token, a
     bad stamp, a bad path, a bad glob, a bad axis, a bad date — each pinned
     to its line number
5. `annot/fsroot.go`, `annot/rewrite.go` + `rewrite_test.go`:
   - placement goldens per language, `testdata/placement/<lang>_<case>.in` →
     `.golden`:
     - bash: shebang + header block; no header; no shebang
     - Python: docstring; no docstring with an encoding line
     - Go: build tag + package; package doc comment
     - Kotlin: imports; package only; license block comment and no imports;
       a member block with and without existing covers
     - the fixed position falling after the first `unit`
   - `RestampLine` keeps alignment spacing
   - `REWRITE_CONFLICT` when `Want` differs; nothing is written
   - the Invariant 6 refusals, file byte-identical in each case:
     - replacing a docstring line
     - a new line that is not an annotation
     - an insert landing inside a docstring
     - **a `Replace` aimed directly (through the API) at a step-3 look-alike
       line in a heredoc / string / raw string** → `ErrNotComment`. This
       includes the delayed-body line of the continuation and spanning-quote
       heredocs
     - an insert after a line ending in `\` (the new line would be a
       continuation, so it is not `Comment`) → refused
     - an insert whose result would change another line's class
     - any write to an uncertain file → `ErrUncertainContext`
   - **D9 end to end:** annotate and verify over files that mix real
     annotations with step-3 look-alikes, including both delayed-body
     heredoc fixtures. The real lines are re-stamped or inserted, and every
     look-alike line stays byte-identical (compared line by line; the git
     diff shows only the real comment lines). For the delayed-body bash
     fixture, `bash` is also run before and after, to show that the stdin
     data the command receives is unchanged.
   - **D17 — stale ownership:** plan a re-stamp of member `A`'s covers line,
     then rename the earlier opener `testmap:unit A` → `testmap:unit B` with
     the covers line left unchanged.
     - `Apply` with `Snapshot` set → `ConflictError{snapshot}`
     - `Apply` with `Snapshot` empty → `ConflictError{ownership}` naming that
       line (the ownership check alone catches it)
     - in both cases nothing is written
     - the same for an insert whose anchor stayed but whose block moved
   - **D18 — symlinked components:** with a regular leaf in each case, the
     external bytes (hashed before and after) stay unchanged and every call
     is refused or skipped:
     - `link → <outside dir>` holding `t.sh` and `src.sh`
     - `inlink → tests` (a link inside the root)
     - `Apply` on `link/t.sh` and on `inlink/t.sh` → refused
     - `SourceStamp` on `link/src.sh` → `ErrNotAFile`
   - file mode 0755 kept; CRLF kept; no final newline kept
   - in a `fixture.New` repository: commit, apply each placement golden's
     edit, and assert that every `+`/`-` line of
     `git diff -w --ignore-blank-lines -U0` is a `testmap:` comment line
6. `annot/hook.go`, `stampverbs.go` + `stampverbs_test.go` (fixture repo,
   `aitestmap/config.yaml` present, clock fixed):
   - annotate `added` / `restamped` / `current`
   - a member target lands inside the member block
   - `no-member-block`, `no-leader`, `excluded`, a missing test,
     `uncertain-context`
   - `not-a-file` for a target under a symlinked parent (`link/t.sh`) and for
     a source under one (`STAMP_SKIP`); external bytes are unchanged
   - a missing source: nothing is written, exit 1
   - verify re-stamps only changed blobs; a re-run is byte-identical
   - `#member` scope only
   - a docstring covers line → `STAMP_SKIP docstring`, file byte-identical
   - a missing source → skip, while the other edges are still re-stamped
   - the hook receives every edge with its state and the actor
   - the hook does not run when `Apply` failed
7. `annot/source.go` + `source_test.go`:
   - `Source` over a fixture repository returns the annotated files sorted,
     the file-level unit first, members in order, and parsed stamps
   - these files are absent: excluded, ignored, symlinked leaf, unannotated,
     other-language, and **a tracked `dir/t.sh` after `dir` was replaced by a
     symlink to an annotated copy**
   - a file whose only `testmap:` lines are look-alikes yields nothing
   - a syntax error → an error naming `path:line`
   - an unreadable directory → an error
8. `cmd/ait-testmap/annotate.go`, the two `verbs.go` rows, `annotate` /
   `verify` added to `TestStubsExit64`'s skip list, the `scancheck.go` wiring,
   and the D11 string edit. `annotate_test.go` drives everything through
   `run()`:
   - text and `--json` outputs
   - `TESTMAP_ABSENT` (2)
   - `ANNOT_INVALID` (3)
   - `REWRITE_CONFLICT` (75, via a hook-free conflict injected by editing the
     file between parse and `Apply` with a test seam `annot.beforeApply`)
   - `RESTAMP_HOOK_ERROR` (3)
   - usage: no sources, a variant id, a bad `--by`, an arm that is not
     registered → `NOT_IMPLEMENTED:annotate --suggest` (64)
   - **the hook through the real verbs**: a test-registered recording hook
     sees `added` from `annotate`, then `restamped` / `current` from `verify`,
     with `human:` / `agent:` / default-`unspecified` actors
   - **scan through the real source**: production `testmapInputs` with only
     the lister swapped for a fake; `scan --apply` writes the annotated
     covers (stamps parsed) to `_scanned.yaml`; a malformed annotation →
     `INPUT_ERROR:annotations|…` exit 3
9. Benchmark `annot.BenchmarkScan`: `registry.Scan` with `annot.Source{}` and
   an in-memory lister, over an aitasks-shape fixture built once in
   `b.TempDir()`. The fixture is a `git init` with no commit (untracked files
   are listed): ≈420 annotated tests, ≈600 sources, ≈1,000 other files.
   Record with
   `taskset -c 0 go run ./internal/tools/benchgate -baseline bench/baseline.txt -update`
   and add `budget=300ms` (the proposal's `scan` budget, now measured with the
   real source).
10. Checks:
   - `gofmt -l .` empty
   - `go vet ./...`
   - `go test ./...` (including `guards_test.go`: no forbidden literal, no new
     dependency)
   - the full benchgate
   - `ait engine test`
11. Documentation (path-scoped commits):
    - proposal *Annotation scanner and rewriter*: one paragraph fixing the key
      argument forms, the language table, the universe (D1), comment-context
      reading and writing (D9), ownership-checked edits (D17), no-follow
      confined I/O (D18), the placement rule details, the actor and hook
      contract, and the new line classes
    - a Line-protocol index row for the `annotate` / `verify` classes
    - README *Layout* row for `internal/testmap/annot`; *Interfaces* rows for
      `annotate`, `verify` and the rewriter / hook, each pinned by its test

### Post-phase (risk mitigations)

1. [probe_own_repository] Run `annot.Source{}.Annotations` once over this
   repository's root, through a temporary `annot/probe_test.go` that resolves
   the root with `git rev-parse --show-toplevel` (deleted afterwards and never
   committed).
   - In the same probe, run `Classify` over **every** known-language file in
     the listing, not only those carrying `testmap:` (≈900 real bash, Python
     and Go files). This is a soundness smoke test for the lexers.
   - Record in Final Implementation Notes: the number of files listed, the
     number with a known language, the number annotated (expected 0), and
     every file that comes out `Uncertain`.
   - Each `Uncertain` result on a file that bash, Python or Go accepts is a
     lexer defect. Fix the lexer and add the construct as a step-3 fixture
     before committing.
   - Any remaining `SyntaxError` is recorded, with its remedy: either a lexer
     fix, or a note to t1861 naming the `exclude:` glob.
2. [interface_notes_downstream] After the code commit, send one hedged
   `./ait note <id> --from 1853_2` per recipient, citing the commit SHA and
   saying "as landed in `<sha>`":
   - t1853_6: `RegisterRestampHook`, `Restamp{…, State}`, the `Actor` kinds
     with `unspecified` as the default, and that the hook runs only after all
     writes
   - t1853_3: `annotateArms` in `cmd/ait-testmap/annotate.go`, plus
     `annot.ParseFile` / `PlanCovers` / `Apply`
   - t1853_4 / t1853_5: `annot.File` already parses `axis` / `area` / `scope` /
     `trigger` / `reads` / `kind`; extend `registry.UnitAnnotation` and the
     mapping in `annot/source.go`
   - t1855: `Apply` / `RestampLine` / `ConflictError` for `stale --confirm*`
   - t1857: `PlanCovers` / `Placement`, and `annot.ErrNoLeader` →
     `ADOPT_SKIP:no-leader`
   - t1858: share `--by` (`annot.ParseActor`), the `--author` arm slot, and the
     hook
   - t1861: the git-visible universe, comment-context reading (look-alikes
     in strings and heredocs are ignored; an uncertain file carrying
     `testmap:` fails the scan), and the probe result

   Note in each that no human-only step was met.

## Verification

- Grammar parse goldens per language, including the Python docstring read and
  `testmap:unit` block ownership; an unknown key is refused with a line number.
- `REWRITE_CONFLICT` on a changed line (75, nothing written).
- **Comments only (D9):** annotation-shaped lines inside bash heredocs and
  strings, Python non-docstring strings, Kotlin raw strings or block comments,
  and Go raw strings are never read. This includes heredoc bodies delayed past
  a continuation or a spanning quote. Through `annotate`, `verify` and a
  direct `Apply` they stay byte-identical, and bash's own stdin data for the
  delayed-body fixture is unchanged. An uncertain file is never written.
- **Ownership (D17):** an opener renamed while the target line stays
  unchanged → `REWRITE_CONFLICT`, whether or not a snapshot is supplied.
- **No-follow (D18):** a symbolic-link parent (outside or inside the root)
  with a regular leaf is refused or skipped by reads, hashing and writes, and
  the external bytes are unchanged.
- Placement goldens per language. Every placement golden, applied in a real
  git fixture, passes the comments-only check under
  `git diff -w --ignore-blank-lines`.
- `# Covers:` prose is never matched or rewritten (byte-identical after
  `annotate`).
- `verify` re-stamps, and a re-run is byte-identical. The hook fires with the
  re-stamped edges and the actor, through the real verbs.
- `scan` over a fixture repository yields edges from annotations through the
  production wiring.
- `ait engine test` is green; the Invariants 4–5 tripwire passes; the bench is
  under 300 ms.
- No path requires a human action: `--by` is optional, and its absence never
  blocks anything.

## Step 9 reference

Post-implementation follows the shared task-workflow Step 9 (archival on the
current branch, no merge).

## Risk

### Code-health risk: medium
- The rewriter edits user test files, and every later adopter writes through
  it (M4.2, M6.3, M7.2, M7.4). A placement, mode or line-ending bug would
  corrupt tests at scale · severity: medium · → mitigation: in-plan design
  (`Apply` re-parses and enforces Invariant 6 itself; per-language placement
  goldens; git `diff -w` comments-only check; mode / CRLF / final-newline
  tests)
- The new line classes (`STAMP*`, `ANNOT_INVALID`, `REWRITE_CONFLICT`,
  `RESTAMP_HOOK_ERROR`) become a protocol that later modules parse · severity:
  low · → mitigation: plan step 10 (proposal + README Interfaces;
  additive-only)
- Additive method in M1.2's shared `gitx`, plus two forced one-line edits to
  M2.1 tests · severity: low · → mitigation: none needed (named extensions,
  recorded in Ownership)
- Three hand-written lexers (`lexctx.go`) add a real maintenance surface;
  each new language construct needs a fixture · severity: medium · →
  mitigation: in-plan design (unmodelled forms fall to `Literal` /
  `Uncertain`, never `Comment`; per-language class-table fixtures, including
  false-negative guards) + inline post-phase probe_own_repository

### Goal-achievement risk: medium
- (review finding, fixed in plan) Line-based reading would let the rewriter
  re-stamp annotation-shaped lines inside heredocs and strings, changing
  runtime data while every planned check passed · severity: high before the
  fix, low residual · → mitigation: D9 design (lexical comment context for
  reads and writes; `Apply` checks classes before and after) + its step-3/5
  fixtures
- (review findings, fixed in plan) A renamed opener moving an edit to another
  member, and symbolic-link parents escaping the root · severity: medium
  before the fix, low residual · → mitigation: D17 / D18 design + step-5
  tests
- The bash, Python and Kotlin lexers are hand-written. One that misreads a
  valid file either drops real annotations or (on reaching `Uncertain`)
  fails `scan` for a file that carries `testmap:`. Its failure direction is
  never a write into data, by construction · severity: medium · →
  mitigation: inline post-phase probe_own_repository
- The hook / actor shape and the `annot.File` model are designed before M2.6,
  M2.4 and M2.5 exist; a shape that does not fit forces rework · severity:
  medium · → mitigation: inline post-phase interface_notes_downstream
- The git-visible universe (D1) may diverge from what M3.1's lister-based
  `UNREGISTERED` reconciliation assumes · severity: low · → mitigation: inline
  post-phase interface_notes_downstream

### Planned mitigations
- timing: post-phase | name: probe_own_repository | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — lexer misclassification / look-alike lines in a real repository failing scan | desc: run annot.Source and Classify over every known-language file of this repository via a temporary uncommitted test; record counts, Uncertain files and SyntaxErrors; fix lexer defects with a fixture or note t1861
- timing: post-phase | name: interface_notes_downstream | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — hook/model/universe shapes designed before their consumers | desc: hedged ./ait notes citing the commit sha to t1853_6, t1853_3, t1853_4, t1853_5, t1855, t1857, t1858, t1861

## Post-Review Changes

### Change Request 1 (2026-10-12 17:10)
- **Requested by user:** seven review findings —
  - (high) heredoc bodies ignored bash's backslash-newline joining
  - (high) `${…}` parameter expansions were not modelled
  - (medium) a TOCTOU between `lstatNoFollow` and `OpenFile`
  - (medium) `testmap:unit M@v` was accepted
  - (medium) the Python docstring was recognised by bracket depth and physical line rather than as the first statement
  - (low) `verify` emitted results in file order, not target order
  - (low, follow-up) sources were re-read per edge
- **Changes made:** each was reproduced against bash / CPython `ast`, then fixed.
  - Unquoted heredoc bodies join backslash-newlines before the delimiter is compared; `<<-` strips tabs from the first piece only.
  - A new `${…}` frame (`E`): quote-aware and nestable; its single quotes are literal inside `"…"`.
  - Handle-bound I/O: directories are entered one component at a time through `os.Root` handles checked with `os.SameFile`; the leaf is bound the same way; writes use only single-name operations in the verified directory.
  - The member must round-trip as a member-only fragment.
  - The Python lexer tracks the first *statement*, with column-exact `DocSpan`s.
  - `Verify` plans in target order and writes once per file.
  - Source stamps are cached per invocation (implemented rather than spawned: trivial).
  - Each fix has classifier, `Apply` and command-level or bash-runtime tests; mutants of each are red.
- **Files affected:** `annot/{lexctx,fsroot,rewrite,grammar,stampverbs}.go` and their tests; proposal; README.

### Change Request 2 (2026-10-12 18:05)
- **Requested by user:** four findings —
  - (high) `<<$'EOF'` was decoded as `$EOF`
  - (medium) literal `{` inside `${…}` was counted
  - (medium) docstring literals were read as separate fragments, not as one concatenated value
  - (medium) a FIFO swapped in for the leaf blocked `OpenFile`
- **Changes made:**
  - `$'…'` / `$"…"` delimiters lose the `$`; a backslash inside any quoted delimiter is refused as `Uncertain` (bash decodes ANSI-C escapes there).
  - In `${…}` the first unquoted `}` closes.
  - The docstring is read as Python's *value*: escapes and backslash-newline decoded, literals concatenated, split into logical lines attributed to source lines (`docstringLines`, `decodePy`).
  - The leaf is opened `O_NONBLOCK` and must be regular. Directories are entered as `name/.`, which `os.Root` opens `O_DIRECTORY|O_NOFOLLOW` (verified with a scratch probe: `OpenRoot("fifo")` blocks, `OpenRoot("fifo/.")` fails `ENOTDIR`), with bounded FIFO tests.
  - The repository probe then found a **panic**: docstring byte attribution counted runes (`for range seg`), crashing on non-ASCII docstrings. Fixed, with a regression.
- **Files affected:** `annot/{lexctx,fsroot,grammar}.go` and their tests; proposal.

### Change Request 3 (2026-10-12 18:35)
- **Requested by user:**
  - (medium) `"test" "map:covers …"` was skipped by the token prefilter
  - (low) `"…"("arg")` was read as a docstring
  - (low) a literal U+FFFD was taken for an undecodable escape
- **Changes made:**
  - Python files are always parsed (the docstring's value can spell the token with no trace in the raw bytes); other languages keep the token prefilter.
  - A `(` after a completed operand is a call, not grouping.
  - Undecodable `\N{…}` positions are carried in a provenance mask, separate from the text.
- **Files affected:** `annot/{grammar,lexctx}.go`, `grammar_test.go`, `source_test.go`; proposal.

### Change Request 4 (2026-10-12 19:00)
- **Requested by user:**
  - (medium) the `\N{…}` refusal predicate was unsound: `\N{LINE FEED}` can start a new line
  - (medium) an ASCII-only trim in the refusal disagreed with the Unicode trim in the parser
- **Changes made:** `mayStartAnnotation` treats each undecodable character as any one character (a line break, whitespace or a token letter). It refuses a line when some decoding could make that line, or a line split off at the escape, an annotation; one Unicode whitespace definition serves the check and the parse. `ParseFile` and `Source` regressions added; both properties mutation-checked.
- **Files affected:** `annot/grammar.go`, `grammar_test.go`, `source_test.go`; proposal.

## Final Implementation Notes

- **Actual work done:**
  - New package `goengines/internal/testmap/annot`:
    - `lang.go`: the language table — bash, Python, Go and Kotlin by extension, or by shebang for files with no extension.
    - `lexctx.go`: per-language comment-context classifiers, sorting each line into `Code` / `Comment` / `Literal`, plus `Uncertain`.
      - Go: `go/scanner`.
      - bash: quotes, `$'…'`, backticks, `$(…)` (including `case`), arithmetic and its re-lexing as `$(` + `(`, `${…}`, heredocs (newline-token start, body continuation, delimiter quoting).
      - Python: every string form, f-string fields, and the first-statement docstring with column spans.
      - Kotlin: templates, raw strings, nested block comments, char literals.
    - `grammar.go`: grammar v3 (`ParseFile`), every key with its line, block ownership, line-numbered `SyntaxError`s, and the decoded-docstring reader.
    - `stamp.go`: `@<date>/<blob10>`.
    - `fsroot.go`: handle-bound, no-follow, non-blocking reads.
    - `rewrite.go`: `Apply`, the only writer. It checks `Want`, the snapshot and ownership, proves the edit comment-only before and after (classes of every other line unchanged), and writes atomically with the original mode, CRLF and final-newline state preserved. Also `PlanCovers`, `Placement` and `RestampLine`.
    - `hook.go`: `Actor` and `RegisterRestampHook`.
    - `stampverbs.go`: the `Annotate` (all-or-nothing) and `Verify` (target order, stamp cache) engines.
    - `source.go`: `Source` (`registry.AnnotationSource`).
  - `gitx.Repo.ListFiles`: git-visible files; any git stderr output fails.
  - Verbs `annotate` / `verify` in `cmd/ait-testmap/annotate.go`, plus the arm table for M2.3 / M7.4. The `scan` wiring is in `testmapInputs`.
  - Benchmark `annot.BenchmarkScan`: ≈21 ms, `budget=300ms`. The full baseline was re-recorded pinned with `taskset -c 0`.
  - Proposal paragraph and Line-protocol index row; README *Layout* and *Interfaces* rows.
- **Deviations from plan:**
  - The `REWRITE_CONFLICT` command-level test calls the glue's error mapper with a `*ConflictError` instead of exporting a test seam. `Apply`-level conflict tests (text, snapshot, ownership, concurrent) prove the conflict itself.
  - `Replace` also requires the old line to already *be* the expected covers line. A mutant showed the class check alone would let a shebang or prose comment be replaced.
  - Every Python file is parsed (round 3); the prefilter applies to other languages only.
  - Arithmetic `<<` is a shift, so it never makes a file `Uncertain`. The plan had listed "a heredoc opener in arithmetic → Uncertain"; bash never reads one there.
  - Docstring `Line.Text` is the physical line; the parsed text is the docstring's logical line.
- **Issues encountered:**
  - Four review rounds found real lexer and filesystem gaps, each verified against bash, CPython or the stdlib source, then fixed with mutation-checked tests (see *Post-Review Changes*).
  - The repository probe found a real bash defect (`$(( cd … ) | …)` lexed as arithmetic, `tests/test_xdeps_blocking.sh:170`) and a panic (rune-vs-byte attribution).
  - shfmt's JSON omits `Text` for an empty comment, which needed handling in the oracle.
  - Two oracle mismatches were files another session was editing mid-probe; frozen copies gave 0 mismatches.
- **probe_own_repository result (inline post-phase 1):**
  - 2,391 git-visible files, 1,345 in a known language.
  - 0 `Uncertain` after the fix above; 0 annotated files; `Source` over the repository succeeds in ≈130 ms.
  - Oracle cross-checks of `Comment` lines: Python vs `tokenize` and docstring spans vs `ast` — 631 files, 0 mismatches. bash vs shfmt v3 — 647 files, 0 mismatches; 3 files shfmt cannot parse (associative-array subscripts with `~` / `:`, and the `$(( (` subshell). No Kotlin sources in the repository (fixtures only). The temporary probe was deleted, never committed.
  - No `exclude:` note is needed for t1861 beyond the general notes below.
- **Key decisions:**
  - Annotations are read and written only on lexically proven comment lines, and `Apply` enforces Invariant 6 itself.
  - Unmodelled constructs fall to `Literal` / `Uncertain`, never `Comment`.
  - Only an explicit `human:` actor is a person; an absent actor is "unspecified".
  - The hook runs once, after all writes; on error it does not run, keeping provenance.
  - `verify` leaves current stamps untouched, so a re-run is byte-identical.
  - `REWRITE_CONFLICT` exits 75.
- **Upstream defects identified:** None
- **Notes for sibling tasks:**
  - **M2.6 (t1853_6):**
    - Fill the hook with `annot.RegisterRestampHook` from an `init` in your own file in `internal/testmap/annot`; registry cannot import annot.
    - `Restamp{Test, Source, File, Line, Before, After, State}`; `State` is `added`, `restamped` or `current` (`current` = confirmed, file untouched).
    - `Actor{Kind: Unspecified|Human|Agent|Auto, Value}`; only `Human` is a person.
    - The hook runs once per invocation, after every write.
  - **M2.3 (t1853_3):** register `--suggest` / `--from-body` in `annotateArms` (`cmd/ait-testmap/annotate.go`). Use `annot.ParseFile`, `PlanCovers` and `Apply`; never write files yourself.
  - **M2.4 / M2.5:**
    - `annot.File.Units` already parses `axis`, `area`, `scope`, `trigger`, `reads`, `kind`, `runner`, `needs` and `batch`, each with its line.
    - Extend `registry.UnitAnnotation` additively and fill it in `toRegistry` (`annot/source.go`).
    - `reads` "helper files only" and the kind vocabulary are yours to enforce.
  - **Callers of the rewriter (M4.2 / M6.3 / M7.x):**
    - Plan with `PlanCovers` on a fresh `ParseFile`, and pass `EditSet{Snapshot: f.Snapshot()}`.
    - Map `*ConflictError` to exit 75; `ErrNoLeader` is `ADOPT_SKIP:no-leader`.
  - **Tests:** drive the verbs through `run()` with `t.Chdir`. The cmd test binary registers a recording hook in `annotate_test.go`.
