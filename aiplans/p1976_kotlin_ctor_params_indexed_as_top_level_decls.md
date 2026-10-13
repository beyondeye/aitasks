---
Task: t1976_kotlin_ctor_params_indexed_as_top_level_decls.md
Base branch: main
Output branch: main
---

# t1976 — Kotlin constructor parameters indexed as top-level declarations

## Context

`scanKotlin` (`goengines/internal/testmap/deps/kotlin.go:70`) records a declaration
whenever a keyword from `declKeywordsKt` (`class|interface|object|fun|val|var|typealias`)
appears at brace depth 0. `depth` counts only `{` / `}` (`kotlin.go:91-95`), so
primary-constructor parameters are at depth 0 too, for example
`data class LoginState(val email: String)` or
`class X @Inject constructor(private val repo: Repo)`. They are indexed as top-level
declarations of the package.

t1973 measured this on thinking_app at `1dc7b958926f`: 697 spurious symbols
(626 `val` + 71 `var`) in 224 of 784 files. The effects:

- `annotate --from-body` resolves a bare `email` in a same-package body to every file
  whose constructor has an `email` parameter, and stamps wrong covers. It writes by
  default.
- `Symbols` facts are wrong.
- `ix.decls` is polluted.

The fix: a keyword declares a top-level symbol only when it is outside every brace
**and every parenthesis**. `class X(` keeps X, because its keyword is outside the
parentheses.

**Deviation from the task's fix direction (angle brackets are not tracked).** `<` / `>`
are also comparison and arrow operators (`a < b`, `->`, `>=`). A counter on them would
stay open after a top-level comparison and drop every later declaration, which is the
fail-open direction. No declaration keyword can appear inside a type-parameter or
type-argument list, and `Foo<T>::class` is already excluded by `prevDot`. A test case
pins this choice.

## Shared-checkout approach

**t1977** (`kotlin.go` `ktDeclName`, likely `kotlin_test.go`, a `schemaVersion` bump) and
**t1975** (`gradle.go`, a `schemaVersion` bump) are `Implementing` in other sessions of
this checkout. Three rules follow:

- **All development, measurement and review happen in a frozen private copy of HEAD
  (F).** The corpus "after" state differs from "before" only by t1976's patch, and
  t1977's naming change cannot leak into it.
- **My hunks enter the shared worktree only inside a seconds-long commit window** made
  of ordinary scoped git operations (step 7). If another session has edits in any of my
  three paths, I wait for that work to land instead of committing around it. Nothing of
  mine sits in the shared tree to be swept, and I never wait while holding hunks there,
  so two sessions cannot deadlock waiting on each other. No `update-ref` or index
  surgery.
- **The window is coordinated, not just observed.** In-script checks cannot stop
  another agent from saving a file, and `index.lock` only covers git operations. So
  before the final HEAD read, apply and commit, every live session that may touch `P`
  **agrees to a pause** (step 7b′). No existing exclusion mechanism is honoured by
  current-branch sessions: the merge lock covers only Step 9 merges.
- **`schemaVersion`**: `cache.get` (`cache.go:61`) checks only the entry's version (`V`)
  and kind; entries are looked up by the file's blob hash. Each committed extraction
  state therefore needs its own version:
  - my commit carries `V(parent)+1`, read from HEAD inside the commit window;
  - coordination with t1975 and t1977 (the two concurrent extraction changes) is a
    required completion step (step 8).

`S` = `<scratchpad>/t1976`; `P` = the three paths `goengines/internal/testmap/deps/{kotlin.go,kotlin_test.go,cache.go}`.

## Implementation steps

1. **Frozen tree F.** Record `BASE=$(git rev-parse HEAD)`, then:

   ```bash
   mkdir -p $S/frozen && git archive "$BASE" goengines | tar -x -C $S/frozen
   cd $S/frozen && git init -q && git add -A && git commit -qm "base $BASE"   # commit c0
   ```

   This is a private repository, not a worktree of the shared one. Paths stay
   `goengines/…`, so patches made here apply to the main repo unchanged. Control:
   `go test ./internal/testmap/deps` passes in `F/goengines` on c0.

2. **Red tests (in F).** Add two tests to `kotlin_test.go` after `TestKotlinResolution`.
   They reuse `repo`, `scanRepo`, `lines` and `bg` from `helpers_test.go`.

   ```go
   // Primary-constructor parameters are members of their class, not top-level
   // declarations of the package: a keyword declares only outside every brace
   // and parenthesis. Every case ends with a real top-level declaration after
   // the constructor, so a parenthesis counter that never closes cannot pass by
   // dropping everything.
   func TestKotlinCtorParamsAreNotTopLevel(t *testing.T) {
   	for name, tc := range map[string]struct {
   		src  string
   		want []string
   	}{
   		"data-class": {lines(`package x`, `data class LoginState(val email: String, var busy: Boolean = false)`, `fun after() = 1`),
   			[]string{"class:LoginState", "fun:after"}},
   		"enum": {lines(`package x`, `enum class Tab(val label: String) {`, `    HOME("home");`, `    val upper get() = label.uppercase()`, `}`, `val after = 1`),
   			[]string{"class:Tab", "val:after"}},
   		"inject-constructor": {lines(`package x`, `class LoginViewModel @Inject constructor(private val repo: Repo) : ViewModel()`, `typealias After = LoginViewModel`),
   			[]string{"class:LoginViewModel", "typealias:After"}},
   		"multi-line": {lines(`package x`, `class Form(`, `    private val mapper: Mapper,`, `    var inProgress: Boolean = false,`, `    val onDone: (Int) -> Unit = { val x = it },`, `) : Base(mapper)`, `object After`),
   			[]string{"class:Form", "object:After"}},
   		// '<' and '>' are comparison operators too: they never nest.
   		"comparison": {lines(`package x`, `val less = 1 < 2`, `class After(val p: Int)`),
   			[]string{"val:less", "class:After"}},
   	} {
   		var got []string
   		for _, s := range scanKotlin([]byte(tc.src)).Symbols {
   			got = append(got, s.Kind+":"+s.Name)
   		}
   		if !slices.Equal(got, tc.want) {
   			t.Errorf("%s: symbols %v, want %v", name, got, tc.want)
   		}
   	}
   }

   // End to end through --from-body: a member body's local `email` gets no ref to
   // a file whose constructor has an `email` parameter, and the class the body
   // does name still resolves. `email` comes first because FromBody keeps one ref
   // per file (the first symbol that reaches it), so pre-fix the wrong symbol
   // wins and the test is red.
   func TestKotlinFromBodyIgnoresCtorParams(t *testing.T) {
   	r := repo(t, map[string]string{
   		"aitestmap/.keep":      "",
   		"src/a/LoginState.kt":  "package com.x.a\n\ndata class LoginState(val email: String, var busy: Boolean = false)\n",
   		"tests/a/LoginTest.kt": lines(`package com.x.a`, ``, `// testmap:unit M`, `fun m() {`, `    val email = "x"`, `    println(LoginState(email))`, `}`),
   	})
   	if f, _ := scanRepo(t, r).Facts("src/a/LoginState.kt"); len(f.Symbols) != 1 || f.Symbols[0].Name != "LoginState" {
   		t.Errorf("symbols %+v, want [LoginState]", f.Symbols)
   	}
   	refused, refs, _, err := FromBody(bg, r.Dir, registry.ID{Path: "tests/a/LoginTest.kt", Member: "M"},
   		Options{Config: registry.Defaults(), Uncached: true})
   	want := []BodyRef{{Source: "src/a/LoginState.kt", Symbol: "LoginState", Line: 6}}
   	if err != nil || refused != "" || !slices.Equal(refs, want) {
   		t.Fatalf("FromBody: refused %q refs %+v err %v, want %+v", refused, refs, err, want)
   	}
   }
   ```

   Run `go test ./internal/testmap/deps -run CtorParams -v` in F. **Both tests must
   fail.** Expected: `data-class` gets `val:email var:busy`, and FromBody returns
   `Symbol:email Line:5`. Record the output.

3. **Corpus baseline (in F; the probe stays untracked and is never committed in F).**
   - Check that `git -C /home/ddt/Work/thinking_app rev-parse HEAD` is
     `1dc7b958926f…` and that `git diff --quiet HEAD -- '*.kt'` passes.
   - Add `goengines/internal/testmap/deps/probe_t1976_test.go` **in F only**.
     - `TestProbeT1976` skips unless `T1976_PROBE_ROOT` is set.
     - It runs `scanKotlin` over every path in `T1976_PROBE_LIST`
       (`git -C <root> ls-files '*.kt'`, 784 files).
     - It writes sorted `path\tkind\tname\tline` rows to `$S/before.tsv`.
   - thinking_app is only read.

4. **The fix (in F), then commit it in F.**
   - In `kotlin.go` `scanKotlin`, next to `depth := 0`, add
     `parens := 0 // open '(': constructor parameters, annotation arguments, calls`.
   - In the operator switch, add `case "(": parens++` and
     `case ")": parens = max(0, parens-1)`. This mirrors the brace clamp.
   - Change the declaration condition (`kotlin.go:165`) to
     `depth == 0 && parens == 0 && !prevDot && …`, with a one-line comment:
     `class X(val a: A)` declares X, not a.
   - Leave `package` / `import` recognition untouched.
   - In `cache.go`, change `const schemaVersion = V(BASE)` to `V(BASE)+1` (4 → 5 at
     planning time).
   - Green in F: `go test ./internal/testmap/deps -run 'Kotlin|CtorParams' -v`, then
     `go vet ./... && go test ./...` over all of `F/goengines`, and
     `gofmt -l goengines/internal/testmap/deps` prints nothing.
   - Commit **only `P`** in F: `git -C F commit -qm fix -- P`. This is commit c1; the
     untracked probe stays out.

5. **Measurements (in F; declaration naming is frozen at BASE).**
   - **Corpus after.** Re-run the probe into `$S/after.tsv`, then compare with
     `comm -3`. Outcomes:

     | observation | meaning / action |
     |---|---|
     | only `val`/`var` rows removed; **626 `val` + 71 `var` in 224 files**; no added rows | pass: matches t1973's oracle exactly |
     | any added row | impossible, since F differs only by the `parens` gate: a bug, so stop and investigate |
     | a removed `class`/`fun`/`object`/`interface`/`typealias` row | a real top-level declaration is hidden behind an unclosed `(`: stop and investigate the lexer |
     | only `val`/`var` removed, but counts ≠ 697/224 | hand-open every file outside the expected set before calling it done |

     In every case, also hand-open 5 random removed rows and confirm that each one is a
     constructor parameter.
   - **Mutant.** Delete the `parens = max(0, parens-1)` decrement in F's worktree. The
     `CtorParams` tests must fail on the trailing `after` declarations. Restore with
     `git -C F checkout -- goengines/internal/testmap/deps/kotlin.go`. Since c1 holds
     the fix, this returns to the **fixed** bytes. Then:
     - Assert that `git -C F diff --quiet c1` passes and that `grep -c 'parens' kotlin.go`
       is unchanged.
     - Re-run `go test ./internal/testmap/deps -run 'Kotlin|CtorParams'` green.

6. **Patch and review.**
   - `git -C F diff c0 c1 -- P > $S/mine.patch`, then check that it touches exactly `P`
     and contains the `parens` gate, both tests and the version line.
   - **Step 8 review is done on F**, not on the shared tree, which deliberately shows
     nothing of t1976 until the commit window. The review prompt shows:
     - `git -C F diff --stat c0 c1` and the patch;
     - the red/green, corpus and mutant results;
     - where to test by hand: `$S/frozen`, a full module copy.
   - "Need more changes" loops edit F, amend c1, re-run steps 4–6, and re-ask.

7. **Commit window** (Step 8 "Commit changes"). These are ordinary scoped git operations;
   my hunks enter the shared tree only here.
   - **7a. Landing tree.**
     - Set `OLD=$(git rev-parse HEAD)`.
     - If `OLD ≠ BASE`:
       - archive `OLD`'s `goengines` into `$S/land`;
       - apply `mine.patch`, with the `cache.go` hunk regenerated as
         `V(OLD) → V(OLD)+1`;
       - run `go vet ./... && go test ./...` there, plus the
         `CtorParams` tests;
       - if anything fails, use a pristine `$S/land` from `OLD` as the control.
     - If `OLD = BASE`, the landing tree is F's c1, which is already fully tested.
   - **7b. Overlap check.** `git diff --quiet HEAD -- P && git diff --cached --quiet -- P`.
     - If either fails, another session has edits in one of my paths. Typically that is
       t1977 in `kotlin.go`/`kotlin_test.go`, or anyone's `schemaVersion` bump.
     - **Do not commit around it.** Tell the user, then wait for it to land. A
       background until-loop re-tests the condition every 120 s and re-invokes me when
       it holds.
     - Then return to 7a, since HEAD has moved. If the wait looks unbounded (the other
       session is parked), ask the user how to proceed.
   - **7b′. Agreed pause.**
     1. **Who.** List every `Implementing` task whose task file or plan names
        `kotlin.go`, `kotlin_test.go`, `cache.go` or `schemaVersion`. At planning time
        that is t1975 and t1977.
     2. **Find each holder's session.** `aitask_lock.sh --check <id>` gives the holder
        pid. Match it against `tmux list-panes -a -F '#{pane_id} #{pane_pid}'`, then
        against the `ListAgents` row for that pane. At planning time: t1975 → pane
        `%676` → `aitasks-00`; t1977 → `%680` → `aitasks-e5`.
        - `aitask_live_endpoint.sh` answers `LIVE_NONE:agent_unknown` until a task
          records `implemented_with`, so the pid join is needed while the siblings
          are still planning.
        - A holder pid that is gone, or no lock at all, means no session can write
          for that task, so it needs no pause.
     3. **Ask.** `SendMessage` to each live holder: "t1976 (session `aitasks-b8`)
        requests a pause of about 2 minutes. Until I send RELEASED, please do not
        write `goengines/internal/testmap/deps/{kotlin.go,kotlin_test.go,cache.go}`
        and do not run `git add`/`commit`/`stash`/`checkout`/`restore` in this
        checkout. Reply PAUSED to `aitasks-b8` when you are at a safe point. This is
        advisory, and your work is unaffected."
     4. **Wait for every `PAUSED`.** If a holder has not replied within 15 minutes (for
        example, it is blocked on its own user prompt), ask the user with
        `AskUserQuestion`. The user drives those sessions, so they can confirm the
        pause on that session's behalf. Options: "Keep waiting" / "Proceed: I confirm
        that session is paused" / "Stop here (task stays in-flight; resume later)".
     5. **Release.** Whatever 7c/7d end with (success, `HEAD_MOVED`, `OVERLAP` or a
        failure), `SendMessage` RELEASED to every paused holder, with the outcome and
        the committed `schemaVersion`/sha when there is one. `HEAD_MOVED`/`OVERLAP`
        release first, then loop back to 7a, so I never hold a pause while waiting.
     6. **Reciprocity.** If a sibling asks me to pause, I comply: I hold nothing in the
        shared tree outside 7c.
   - **7c. Apply and commit in one `set -euo pipefail` invocation** (inside the agreed
     pause):
     ```bash
     [ "$(git rev-parse HEAD)" = "$OLD" ] || { echo HEAD_MOVED; exit 3; }   # → back to 7a
     git diff --quiet HEAD -- "${P[@]}" && git diff --cached --quiet -- "${P[@]}" || { echo OVERLAP; exit 3; }
     git apply "$S/mine.patch"                                   # worktree only
     git commit -F "$S/msg" -- "${P[@]}" || { git apply -R "$S/mine.patch"; echo COMMIT_FAILED; exit 1; }
     ```
     - `git commit -- <paths>` takes `index.lock`. It commits exactly those paths' worktree
       content, updates the shared index for them, and leaves every other staged entry
       alone.
     - On any failure, nothing of mine is left behind.
     - Commit message:
       `bug: Stop indexing Kotlin constructor parameters as top-level declarations (t1976)`
       plus the attribution trailers.
   - **7d. Required post-checks** (`NEW` = the sha from the commit line):
     - `git show --stat NEW` lists exactly `P`.
     - `git diff OLD NEW | git patch-id --stable` equals the patch-id of the applied
       `mine.patch`. This proves nothing foreign rode along.
     - `V(NEW) = V(OLD)+1`.
     - `git diff --quiet HEAD -- P` and `git diff --cached --quiet -- P`: nothing of mine
       is left staged or unstaged, and no reversal is staged.
     - On any mismatch: stop and report. The commit is local; per prior practice,
       document the situation or split it only with the user's authorization.

8. **Version coordination with t1975 and t1977 (required to complete).**
   - **8a.** For each of t1975 and t1977 not yet landed (no `(t1975)` / `(t1977)` commit in
     `git log BASE..HEAD`), send `./ait note <id> --from 1976 --with-live`. The note
     states:
     - t1976 committed `schemaVersion = V(NEW)` at `<sha>`;
     - their commit must carry *parent + 1, read from HEAD at their commit time*;
     - why: `cache.get` keys only on blob / kind / `V`.

     Completion requires `NOTE_APPENDED` for each. `LIVE_NONE` is still success.
   - **8b. At Step 9, before archival.** For every `(t1975)` / `(t1977)` commit since
     `BASE`, check `V(commit) = V(parent)+1`. If one landed without a distinct bump,
     report it and offer a one-line bump commit through steps 7a–7d. This check covers
     only these two tasks, not every change under `deps/`.

9. **Step 9 (Post-Implementation).** Archival per the workflow; current-branch mode, so
   there is no merge. Delete `$S`.

## Verification

- Step 2: red in F, with the expected pre-fix output.
- Step 4: green in F, including full `go vet` + `go test` over the module.
- Step 5:
  - the corpus diff matches the pass row;
  - the mutant fails;
  - after restoration, F equals c1 and is green again.
- Step 7a: the exact landing tree is tested. This includes the `cmd/ait-testmap`
  from-body tests, whose fixtures carry constructor parameters
  (`WelcomeScreen(val vm: Any)`) with unchanged expected output.
- Step 7b′: a `PAUSED` reply (or the user's confirmation) from every live holder
  before 7c, and RELEASED sent to each afterwards.
- Step 7d: the commit content matches `mine.patch` by patch-id, the version is
  `parent + 1`, and the shared tree is clean on `P` (staged and unstaged).
- Step 8: `NOTE_APPENDED` for each sibling that has not landed; the Step 9 version
  re-check passes or is reported.

## Risk

### Code-health risk: low
- Shared-checkout commit hazards: a foreign hunk sweeps into the commit, a staged
  reversal is left behind, or two `schemaVersion` bumps collapse · severity: low ·
  → mitigation: none (handled in the main body: F-only development; a seconds-long
  scoped commit window inside an agreed pause with every live session that may touch
  `P` (7b′); waiting on overlap; patch-id, version and clean-tree post-checks; required
  sibling coordination)

### Goal-achievement risk: low
- A `(` left open by a lexer gap would hide every later top-level declaration in that
  file. That is under-indexing, the fail-open direction · severity: low · →
  mitigation: none (step 5's frozen corpus diff stops on any non-`val`/`var` removal;
  each step-2 case asserts a declaration after the constructor)

## Progress (implementation, 2026-10-13)

- [x] Step 1: F at `BASE=6a3a81efc` (private repo, c0 `cff1b1c`); pristine deps tests pass.
- [x] Step 2: red. All five `CtorParams` cases failed with the predicted pre-fix
  symbols (e.g. `data-class: [class:LoginState val:email var:busy fun:after]`).
  FromBody returned `[{src/a/LoginState.kt email 5}]`.
- [x] Step 3: baseline probe over thinking_app at `1dc7b958926f` (`*.kt` clean vs
  HEAD): 784 files, 2594 declaration rows.
- [x] Step 4: fix + `schemaVersion` 4 → 5 in F (c1 `6a77aee`). Focused tests are green,
  full-module `go vet` + `go test` pass, and `gofmt -l` is clean.
- [x] Step 5, corpus (byte-order sort):
  - 737 rows removed (666 `val`, 71 `var`) in 225 files; **0 added**; no other kind
    removed.
  - **Reconciled exactly with t1973** at its granularity, distinct per-file names that
    are absent after the fix: **697 in 224 files** (626 `val` + 71 `var`).
    - The extra rows repeat a parameter name across classes in one file.
    - `QuestionsListRequestDTO.kt` has `lastQuestionId` / `topicId` / `limit` as both
      `val` and `var`; t1973 counts them under `var`.
    - `AnalyticsVocabulary.kt` keeps `wire`, because `val PermissionStep.wire` /
      `val ProtectionTier.wire` (lines 132/135) are real top-level extension
      properties. That is the 225th file.
  - Hand check: 5 random removed rows are all constructor parameters.
- [x] Step 5, mutant: with the decrement removed, 4 cases fail on their trailing `after`
  declarations. Restored to c1 (`git diff --quiet c1`), green again.
- [x] Step 6: `mine.patch` covers exactly the 3 paths (4 `parens` lines, 2 tests,
  version line).
- [x] Step 7: commit window.
  - Pause: t1975 (`aitasks-00`, pane %676) and t1977 (`aitasks-e5`, pane %680) were sent
    pause requests. Both sessions were blocked on their own prompts, so the user
    confirmed the pause on their behalf ("1975 and 1977 are currently paused").
  - The first 7c run stopped with `HEAD_MOVED` before applying anything. The mover was
    `a5c479de6` (t1954_3: 125 research files, **none under `goengines/`**). The 7a redo
    verified `git diff --quiet BASE OLD -- goengines`, so the landing tree's `goengines/`
    equals F's tested c1 and needed no re-test. Committed as **`8718afa08`** inside the
    same pause.
  - 7d: `HEAD == NEW`; `--stat` lists exactly the 3 paths; patch-id equals `mine.patch`
    (`f6c9c148…`); `schemaVersion` 4 → 5; no staged or unstaged diff left on the paths.
  - RELEASED sent to both sessions.
- [x] Step 8a: `NOTE_APPENDED` on t1975 (`…b906cde1…`) and t1977 (`…fc748553…`): HEAD is
  at 5, and their bump must be parent+1 from a fresh HEAD read.

## Final Implementation Notes
- **Actual work done:**
  - `scanKotlin` now tracks open parentheses (`parens`, clamped like `depth`). A
    declaration keyword counts as top-level only when `depth == 0 && parens == 0`, so
    primary-constructor `val`/`var` parameters are no longer indexed, and `class X(`
    still declares X.
  - `schemaVersion` 4 → 5.
  - Two tests: `TestKotlinCtorParamsAreNotTopLevel` (data class, enum, `@Inject
    constructor`, multi-line, and a `<`-comparison guard; every case asserts a
    declaration after the constructor) and `TestKotlinFromBodyIgnoresCtorParams` (the
    `--from-body` repro with a positive `LoginState` ref).
- **Deviations from plan:**
  - The first commit attempt hit `HEAD_MOVED`. It was resolved inside the same pause by
    proving `goengines/` unchanged since BASE, instead of the plan's "release first,
    then loop to 7a". That rule exists to avoid holding a pause while waiting; this
    redo took seconds, and no waiting was involved.
  - Live delivery used `SendMessage` via a lock-pid → tmux pane → `ListAgents` join.
    `aitask_live_endpoint.sh` answers `agent_unknown` until a task records
    `implemented_with`, which is documented behaviour.
  - The durable notes went through `./ait note` directly (no `--with-live`), because
    the live message had already been sent.
- **Issues encountered:** The first corpus `comm` ran on a locale-collated comparison of
  Go's byte-sorted output and produced phantom "added" rows. Re-sorting with `LC_ALL=C`
  gave 0 added.
- **Key decisions:**
  - Angle brackets are not tracked, because `<`/`>` are also comparison operators and a
    counter on them would hide later declarations (pinned by the `comparison` case).
  - All development and measurement happened in a frozen private copy of HEAD, so
    t1977's concurrent `ktDeclName` work could not leak into the before/after corpus
    diff.
  - Corpus: 737 rows removed, all `val`/`var`, 0 added. At t1973's granularity
    (distinct per-file names absent after the fix) that is exactly 697 in 224 files.
- **Upstream defects identified:** None
