---
Task: t2321_fix_pip_install_guards_c4_mutation_count.md
Base branch: main
Output branch: main
---

# t2321 — Fix pip-install-guards C4 mutation count

## Context

`tests/test_setup_pip_install_guards.sh` fails 107/108 at HEAD:

```
FAIL: C4: the mutation no-ops exactly the four post-repair re-checks (expected '4', got '5')
```

Root cause (verified with `git log -S AIT_PIP_SPECS_QUESTIONS`): commit
`530a62f96` (t2281) added `setup_questions_deps()` to
`.aitask-scripts/aitask_setup.sh` (~line 980). It uses the same
install → verify → repair → **re-check** shape as the other tiers, and its
re-check (`aitask_setup.sh:997`,
`        verify_venv_specs   "$VENV_DIR/bin/python" "${AIT_PIP_SPECS_QUESTIONS[@]}"`)
matches C4's mutation `s|^        verify_venv_specs   |        : |`. So the
mutation pattern is correct. The 5th match is a genuine post-repair re-check,
not an unrelated line. What drifted is the test: t2281 never extended it, so the
pin still says 4, and the questions tier has **no** version-check rejection,
recovery or negative-control coverage. The only test of the questions tier,
`tests/test_setup_questions_server.sh` 3f/3g, covers just the missing venv and a
failing pip with failing imports.

The same drift hits C1's comment, "one line covers all 8 call sites": there
are now 10 `pip_install_guarded` sites (the questions tier added 2).

The fix: update the pin, **and** bring the questions tier into the harness, so
that C4's mutation of that site is observed behaviourally rather than only
counted. The single file to edit is `tests/test_setup_pip_install_guards.sh`;
no source change.

## Implementation steps

1. **Driver** (heredoc `driver.sh`, the `case "$2"` block ~line 170): add
   `    questions)   setup_questions_deps ;;` beside `chat)`. It needs no
   fixture changes: `VENV_DIR=$HOME/.aitask/venv` is already built by
   `make_home`, the failing stub pip goes through `pip_install_guarded` (warn,
   continue), `import mcp` / `import anyio` follow `deps_ok`, and the stdin
   inspection follows `specs_ok`, exactly as for chat.

2. **Section A, after case 3 (chat_bad), add 3b/3c**, mirroring 2/3:
   - `3b` `fresh_home questions_good 1` → `run_case … questions`:
     exit 0; contains `Codex questions server dependency ready`;
     not_contains `could not be installed`.
   - `3c` `fresh_home questions_bad 0`: exit 0; contains
     `Questions deps could not be installed`.

3. **Section 8, add 8f** (after 8e): `fresh_home questions_specfail 1 0`:
   exit 0; contains
   `Questions deps could not be installed (missing: none; version check failed)`;
   not_contains `Codex questions server dependency ready`.

4. **Section 9, add 9e** (after 9d): `fresh_home questions_recover 1 once`:
   exit 0; contains
   `Questions deps need repair (missing: none; version check failed)`;
   contains `Codex questions server dependency ready`;
   `inspections "$h/.aitask/venv"` == `2`.

5. **C1**: append `"questions:questions_good:1" "questions:questions_bad:0"`
   to the `for spec in …` list, and change the heading comment to
   "one line covers all 10 call sites".

6. **C3**: add `C3/questions`: `fresh_home neg_specs_questions 1 0` with
   `$MUT_SPECS` → contains `Codex questions server dependency ready`
   ("without the clause the unverified tier is ready").

7. **C4**:
   - Comment: "The five post-repair verify_venv_specs calls (pypy, chat,
     questions, dev, cpython)…". Add one sentence saying that a new tier with
     this shape bumps the pin and needs its own `C4/<tier>` case below, so the
     next drift fails with a pointer, not a puzzle.
   - Pin: `assert_eq "C4: the mutation no-ops exactly the five post-repair re-checks" "5" "$recheck_lines"`.
   - Add `C4/questions`: `fresh_home neg_recheck_questions 1 once` with
     `$MUT_RECHECK` → contains `Questions deps could not be installed`;
     `inspections "$h/.aitask/venv"` == `1`.

8. Update the section-9 lead comment, which says "each site", only if it lists
   the sites (it does not today; leave it otherwise).

## Verification

- `bash tests/test_setup_pip_install_guards.sh` → `Fail: 0`. The count rises
  from 108 by the new assertions (3b:3, 3c:2, 8f:3, 9e:4, C1:+4, C3:+1,
  C4/questions:+2 = +19 → 127).
- Pre-fix proof for the new cases: they discriminate. 9e passes on the real
  source, and C4/questions flips it under the mutant (that is what C4 checks);
  8f passes on the real source, and C3/questions flips it under the C3 mutant.
- `shellcheck tests/test_setup_pip_install_guards.sh` (no new warnings vs HEAD).
- `bash tests/test_setup_questions_server.sh` still passes (it is untouched,
  as a sanity check).

## Step 9 (Post-Implementation)

Commit `bug: Cover the questions tier in the pip-install guard test (t2321)`
naming only `tests/test_setup_pip_install_guards.sh`, then archive per the
workflow's Step 9.

## Risk

### Code-health risk: low
None identified. The change is test-only and confined to one file. It adds
cases using the file's existing fixtures, and changes no source.

### Goal-achievement risk: low
None identified. The fifth match is verified as a genuine re-check site added by
t2281, so updating the pin, plus a behavioural case per mutation, is the right
shape and not a mask.
