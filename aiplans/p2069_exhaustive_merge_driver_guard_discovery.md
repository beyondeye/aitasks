---
Task: t2069_exhaustive_merge_driver_guard_discovery.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2069 — Exhaustive merge-driver guard discovery (Test 3 of test_aitask_merge_boardgroup.sh)

## Context

t2060 rewrote Test 3 of `tests/test_aitask_merge_boardgroup.sh`. Test 3 is the
guard that checks every merge-driver call passes `--base-file`. Its discovery
has two gaps, and both let a call site be silently omitted:

1. Driver-path variables (`X=".../aitask_merge.py"`) are discovered **per file**.
   A caller that sources `lib/task_automerge.sh` and reuses
   `_AIT_AUTOMERGE_SCRIPT` is therefore invisible.
2. Only the shape `"$<..PYTHON..>" "$<var>"` is recognised. Three kinds of call
   are dropped without notice: an interpreter variable whose name lacks
   `PYTHON`, a call by literal path, and a call through an array.

Acceptance requires each omission class to become either **recognised and
base-checked** or a **hard failure** ("unclassified aitask_merge.py reference —
update the guard"). Each class needs a planted fixture, and the existing
planted control and the base-removal mutant behaviour must keep working.

**Review findings folded in (both verified by reproduction).** A first draft
used a line-level awk classifier and had two flaws:

- **(a)** It stripped `-[efrsx] "$VAR"` anywhere on the line as a "file probe".
  So `"$INTERP" -s "$_X_SCRIPT" "$f" --batch --rebase`, a valid Python call,
  produced **no row at all**.
- **(b)** It classified a whole logical line as one call, based if any base
  marker appeared on it. So
  `"$I" "$S" "$f" --base-file "$b"; "$I" "$S" "$g" --batch` produced only
  `INVOKE 1`, and swapping the second call for `"$I" -u "$S" "$g"` also
  produced only `INVOKE 1`.

The design below classifies **each simple command, and each mention within
it**, using a real shell tokenizer. The file-test exemption applies only inside
a verified `[[ … ]]` / `[ … ]` / `test` command.

**Second review finding folded in (verified).** shlex's default comment
handling is not Bash's. An unquoted `#` inside a word starts a shlex comment,
so `echo release#candidate; "$INTERP" "$_X_SCRIPT" …` tokenizes to
`['echo', 'release']`, and `n=${f##*/}; …` to `['n=${f']`. No lexer error is
raised, yet Bash runs the later call: I checked this with a stand-in function
that prints `CALLED`. The fix:

- Set `lx.commenters = ''`.
- Strip comments first with `strip_comment()`, which follows Bash's rule: a
  `#` starts a comment only when it is unquoted, outside `${…}`, and at a word
  start (line start, or after one of space, tab, `; & | ( ) < >`).
- Return `None` (ambiguous, so the line is **UNCLASSIFIED** when it mentions
  the driver) for an unterminated quote or any `$'…'` ANSI-C quoting.

**Third review finding folded in (verified).** That first stripper checked the
*previous character* against the break set even when that character was
escaped. So for `echo x\ #candidate; call` and `echo x\;#candidate; call`, Bash
runs the call but the scanner emitted no row.

`strip_comment()` is now a word-start state machine:

- `at_word_start` is true at line start and after an **unescaped, unquoted**
  break character (space, tab, `; & | ( ) < >`).
- It becomes false after an escaped character, a quote, `${`, `}`, or any
  other character.
- `$(` / `<(` / `>(` open a nested context: inner `(` increments the depth and
  `)` decrements it without ending the word. That covers `$(…)#c`,
  `$((1+2))#c` and `<(…)#c` — the first was an unreported fourth case the
  differential found.
- A `#` at word start **inside** `$(…)` or `` `…` `` returns `None`
  (ambiguous, fail closed), and so does an unterminated quote or `$'…'`.

Differential against real Bash: each probe line ends in a stand-in call that
prints `CALLED`, and the check asks whether the stripper keeps the call. Over
31 probes it **never hides a call that Bash executes**. The probes include:

- `x\ #`, `x\;#`, `x\|#`, `x\\ #`
- `release#candidate`, `${f##*/}`, `$#`, `${x:- #}`, `${x:-"}" #}`
- `"q"#c`, `'q'#c`, `&#c`
- `$(…)#c`, `$(echo ")")#c`, `$((1+2))#c`, `$((2#101))`, `<(…)#c`
- `(…)#c`, `` `…`#c `` / `` `…` #c ``, tab-`#`, full-line comments,
  trailing comments

Every line it strips is one Bash also does not execute.

**Fourth review finding folded in (verified).** The pure-path assignment
exemption keyed on a filename suffix only. So
`NEXT="$("$INTERP" /tmp/aitask_merge.py "$g" --batch --rebase)/aitask_merge.py"`
emitted no rows, although its substitution runs an unbased literal-path call.

New rule, deliberately not recursive: a logical line whose **comment-stripped
code** mentions the driver and contains a command or process substitution
opener (`$(`, `` ` ``, `<(`, `>(` — regex `\$\(|`|[<>]\(`) is
**UNCLASSIFIED**. The rule is applied before any per-command classification,
so no exemption (assignment, test operand, invocation) can apply to such a
line.

Consequence, accepted and documented: a driver call wrapped in a substitution
(`out=$("$P" "$X" … --base-file …)`) now fails closed as unclassified instead
of being recognised. The real tree has none, and the failure message tells the
author to update the guard. Pass-1 discovery stays permissive (such an
assignment still registers its variable), which only widens what counts as a
mention, so it fails closed.

Verified with the prototype:
- `NEXT="$(…)/aitask_merge.py"` → none before, UNCLASSIFIED now.
- The backtick variant → UNCLASSIFIED.
- The real tree is unchanged (`INVOKE 1 …task_automerge.sh:154`, nothing unclassified).
- The genuine trailing-comment invocation is still `INVOKE 1`.

## Change — `tests/test_aitask_merge_boardgroup.sh`, Test 3 only

Replace `logical_lines` / `driver_invocations` with one scanner,
`scan_driver_refs <file>...`. It is a Python program held in a quoted-heredoc
variable (`DRIVER_SCAN_PY=$(cat <<'PY' … PY)`) and run as
`python3 -c "$DRIVER_SCAN_PY" "$@"`. The file already shells out to `python3`
for `parsed_field`. Tokenization uses
`shlex.shlex(text, posix=True, punctuation_chars=True)` with
`whitespace_split=True` and **`commenters=''`**. That splits on the control
operators (`; && || | & ( )`) while keeping `2>&1`, `${base_args[@]+"…"}` and
`$(...)` intact. Comments are removed beforehand by the Bash-rule
`strip_comment()`.

Algorithm:

1. **Logical lines.** Join backslash continuations, keeping the start line
   number, and run `strip_comment()` on each one. A full-line comment becomes
   empty code. A `None` result on a line whose raw text mentions the driver is
   **UNCLASSIFIED**. A line whose only mention sits in a genuine comment is
   skipped.
2. **Pass 1, cross-file driver variables (closes class 1).** Across *all* given
   files, collect `NAME` from every token `NAME=<value ending in aitask_merge.py>`.
   Quoting does not matter: `X="…"`, `X=…` and `local X=…` all count.
3. **Pass 2, per-command classification.** Take every logical line that
   contains the literal `aitask_merge.py` or a `$NAME` / `${NAME}` reference to
   a driver variable (identifier-bounded, so `$_X_SCRIPT_DIR` is not one).
   Tokenize it; a lexer error makes the whole line **UNCLASSIFIED**. Walk it one
   simple command at a time:
   - **Leading words** (`!`, `if`, `then`, `do`, `else`, `elif`, `while`,
     `until`, `time`, `{`, and `NAME=` assignments):
     - A pure driver-path assignment is fine.
     - Any other assignment that mentions the driver is **UNCLASSIFIED**. That
       covers an alias such as `S="$X"` and a path like `X=$D/aitask_merge.py.bak`.
     - In `NAME=( … )`, any element that mentions the driver is
       **UNCLASSIFIED** (array call).
   - **Test command.** If the command word is `[[` (scanned through `]]`,
     across `&&`/`||`), `[` (through `]`), or `test`, then a mention is allowed
     **only** when the token is exactly a driver reference and the previous
     token is in `{-e,-f,-r,-s,-x}`. Any other mention, or a missing closing
     `]]` / `]`, is **UNCLASSIFIED**.
   - **Invocation.** If the command word is any `$VAR` / `${VAR}` expansion and
     the next word is exactly a driver reference, emit one
     `INVOKE\t<based>\t<file>:<line>` row **for this command**. `based` = a later
     word *of the same simple command* contains `base_args` or `--base-file`.
     This is interpreter-name agnostic, which closes the non-`PYTHON` case.
   - **Anything left.** Any other mention left in the command — the literal
     path, `"$I" -s "$X"`, `"$I" -u "$X"`, or a driver ref in some other
     argument position — makes the line **UNCLASSIFIED**.

   Emit `UNCLASSIFIED\t<file>:<line>\t<text>` once per offending logical line.
   One line can carry several `INVOKE` rows plus an `UNCLASSIFIED` row, so a
   recognised call can no longer mask a second call.

Shell wrappers on top:

- `count_driver_sites <file>...` → `"<invocations> <with_base>"` from the INVOKE rows. The interface is unchanged.
- `unclassified_driver_refs <file>...` → the UNCLASSIFIED rows.

The prototype was measured in plan mode against inline fixtures and the real
tree (192 `*.sh` files, about 0.05 s): it finds
`INVOKE 1 .aitask-scripts/lib/task_automerge.sh:154` and nothing unclassified.
The real probe `[[ -n "$_AIT_AUTOMERGE_PYTHON" && -f "$_AIT_AUTOMERGE_SCRIPT" ]]`
and the init `_AIT_AUTOMERGE_SCRIPT=""` classify cleanly.

### Assertions (Test 3)

Every planted file is written with a quoted heredoc into `mktemp -d`.

- **Existing planted control, kept verbatim:** `2 1`. Add an assertion that it yields no unclassified rows.
- **Benign negative control:** a comment mentioning `aitask_merge.py`, a
  trailing `# aitask_merge.py` comment, `_X_SCRIPT=""`, the real assignment,
  `[[ -n "$P" && -f "$_X_SCRIPT" ]]`, `[ -r "${_X_SCRIPT}" ] || exit 1`, and an
  `echo "$_X_SCRIPT_DIR"`. Expect `0 0` and no unclassified rows, so the
  tripwire does not fire on legitimate references.
- **Class 1, cross-file:** `defs.sh` assigns `_X_SCRIPT`, and `caller.sh` holds
  an unbased split call. Scanning both gives `1 0` (recognised, then fails the
  base check).
- **Class 2a, non-PYTHON interpreter:** `"$INTERP" "$_X_SCRIPT" …` with no base → `1 0`.
- **Class 2b, literal path** (`python3 ".../aitask_merge.py" … --base-file x`) → exactly 1 unclassified row.
- **Class 2c, array** (`cmd=("$P" "$_X_SCRIPT" … --base-file "$b")`) → exactly 1 unclassified row.
- **Review (a), interpreter option:** `"$INTERP" -s "$_X_SCRIPT" "$f" --batch --rebase`
  → exactly 1 unclassified row. A second fixture,
  `[[ -f "$_X_SCRIPT" ]] && "$I" -s "$_X_SCRIPT" "$f"`, also gives exactly 1:
  the exemption covers only the operand inside the test.
- **Review (a), non-file test:** `[[ -n "$_X_SCRIPT" ]]` → 1 unclassified row.
  The exemption is limited to file-test operators.
- **Review (b), compound, both recognised:**
  `"$I" "$_X_SCRIPT" "$f" --base-file "$b"; "$I" "$_X_SCRIPT" "$g" --batch --rebase`
  → `2 1`, so the based call no longer masks the unbased one.
- **Review (b), compound, one unsupported:**
  `"$I" "$_X_SCRIPT" "$f" --base-file "$b"; "$I" -u "$_X_SCRIPT" "$g"`
  → `1 1` **and** exactly 1 unclassified row.
- **Review 2, Bash comment boundaries:**
  - `echo release#candidate; "$INTERP" "$_X_SCRIPT" "$g" --batch --rebase` → `1 0`.
  - `n=${f##*/}; "$INTERP" "$_X_SCRIPT" "$g" --batch --rebase` → `1 0`.
  - Genuine trailing comment
    `"$I" "$_X_SCRIPT" "$f" --base-file "$b"  # aitask_merge.py call` → `1 1`
    and 0 unclassified.
  - Commented-out call `echo x # "$INTERP" "$_X_SCRIPT" "$g"` → `0 0` and 0 unclassified.
  - Ambiguous quoting `echo $'a\'b'; "$I" "$_X_SCRIPT" "$g"` → 1 unclassified.
  - **Real-lexer differential (replaces single-line controls):** a quoted
    heredoc holds the comment-boundary probe battery above, about 28
    single-line probes. Each probe line ends in `@CALL@`, which is substituted
    with `"$INTERP" "$_X_SCRIPT" p<N> --batch --rebase`.
    - Write each probe to its own file, next to one `defs.sh` that assigns
      `_X_SCRIPT`, and run **one** scanner pass over them.
    - Run **one** `bash` script containing every probe line, with `INTERP`
      bound to a harmless stand-in that prints `CALLED <id>`.
    - Assert, per probe: *scanner reports a row (INVOKE or UNCLASSIFIED) ⇔
      Bash printed `CALLED p<N>`*.
    - The `⇒` direction pins that genuine comments stay supported (no false
      rows). The `⇐` direction pins that no executed call is hidden.
    - Add a floor assertion that Bash executed at least 15 of the probes and
      skipped at least 8, so the differential exercises both directions and
      cannot pass vacuously.
    - Explicitly includes the reviewer's `echo x\ #candidate; …` and
      `echo x\;#candidate; …`.
- **Review 4, substitution in a driver-path assignment:**
  - `NEXT="$("$INTERP" /tmp/aitask_merge.py "$g" --batch --rebase)/aitask_merge.py"` → exactly 1 unclassified row.
  - `` NEXT=`"$INTERP" /tmp/aitask_merge.py "$g"`/aitask_merge.py `` → 1 unclassified row.
  - `out=$("$P" "$_X_SCRIPT" "$f" --base-file "$b")` → 1 unclassified row (pins the accepted fail-closed consequence).
  - The plain assignment `_X_SCRIPT="$D/../board/aitask_merge.py"` stays row-free (already in the benign control).
- **Real tree:** keep the floor (≥1), the canonical-site assertion and
  `invocations == with_base`. The canonical site is now read by filtering the
  whole-tree INVOKE rows for `lib/task_automerge.sh:`. **New:**
  `assert_eq "No unclassified aitask_merge.py reference (update the guard)" "" "<rows>"`
  — the failure output prints file:line and text.
- **Base-removal mutant (automated):** copy `lib/task_automerge.sh` to a temp
  file and remove the literal ` ${base_args[@]+"${base_args[@]}"}` with a
  quoted bash pattern substitution. Assert first that the copy differs from the
  original (precondition), then that the copy gives `1 0`.

Rewrite the Test 3 comment block to describe the per-command classification
and the remaining boundary:

- Scope is the `*.sh` files under `.aitask-scripts/`. No Python file invokes
  the driver today; the `.py` hits are comments or docstrings only.
- A driver path assembled without the literal `aitask_merge.py` in any scanned
  file stays invisible to static scanning.
- A line the lexer cannot parse (for example a multi-line string), or one with
  ambiguous quoting (`$'…'`), fails closed as unclassified when it mentions
  the driver.

The file uses top-level asserts (no subshells), so no counter opt-in is needed.

## Verification

- `bash tests/test_aitask_merge_boardgroup.sh` → all pass (was 20; about 42 assertions now).
- Mutants on the scanner itself (scratch copy), each of which must turn the
  differential red:
  - restore shlex's default `commenters`;
  - restore the previous-character check instead of `at_word_start`;
  - drop the `$(` nesting.
  - drop the substitution rule → the Review-4 fixtures must turn red.
- Red proofs (scratch copy of the pre-change Test 3 helpers):
  - Class-1 and 2a fixtures → `0 0`.
  - The previous awk draft on the review fixtures → no row / `INVOKE 1`.
  - Together these show the new assertions discriminate.
- `shellcheck tests/test_aitask_merge_boardgroup.sh` → no new warnings.

## Step 9

Current-branch mode. Commit the test file alone (`test: … (t2069)`) with an
explicit pathspec, because the worktree is shared and dirty. Commit the plan
via `aitask_task_commit.sh`, then archive.

## Risk

### Code-health risk: low
None identified. The change is test-only and confined to one test block. The
embedded classifier is about 80 lines of Python, but it is self-contained and
covered by the planted fixtures.

### Goal-achievement risk: low
- Residual static-scan boundary: a driver path built without the literal `aitask_merge.py` in any scanned `.sh` file stays invisible · severity: low (inherent to a static guard; documented in the Test 3 comment) · → mitigation: none (accepted)
