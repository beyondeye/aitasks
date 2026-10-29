---
Task: t2165_keep_path_args_whole_in_unreadable_registry_test.md
Base branch: main
Output branch: main
plan_verified: []
---

# Plan: keep path args whole in the unreadable-registry test (t2165)

## Context

`tests/test_projects_unreadable_registry.sh` section 1 builds a VERBS table of
`label|stdin|argline` strings, then splits `argline` with `read -r -a args`.
Two rows interpolate fixture paths into the argline:

```
"add|-|add $ALPHA_ROOT"
"update|-|update alpha $BETA_ROOT"
```

Both paths come from `mktemp -d`, which honours `TMPDIR`. When `TMPDIR`
contains whitespace, the split breaks each path into several arguments, so
`add`/`update` die at the earlier "Path does not exist" check and never reach
the unreadable-registry read the test is about. That is a false red, never a
false green.

**Reproduced during planning:** with `TMPDIR=<scratch>/sp ace` the test fails
6 of 145 checks (add + update × 3 shapes on `assert_contains "$CANNOT_READ"`),
each reporting `Error: Path does not exist: …/sp`.

t2164 fixed the same construct in `tests/test_projects_lock_released_on_die.sh`
section 1: the table holds `@ALPHA@` / `@BAD@` placeholders, and a per-element
`case` loop substitutes them after the split. Reuse that idiom here.

## Implementation

Single file: `tests/test_projects_unreadable_registry.sh`, section 1 (lines ~119–137).

1. Replace the table comment (line 119) with the sibling's wording:
   ```bash
   # label|stdin|verb args (space-separated)
   # Paths appear as @ALPHA@ / @BETA@ and are substituted after the split, so a
   # TMPDIR containing whitespace still reaches the verb as one argument.
   ```
2. Change the two rows to the placeholders:
   ```bash
   "add|-|add @ALPHA@"
   "update|-|update alpha @BETA@"
   ```
3. After `read -r -a args <<< "$argline"`, add the substitution loop
   (same shape as `test_projects_lock_released_on_die.sh:90-95`):
   ```bash
   for i in "${!args[@]}"; do
       case "${args[i]}" in
           @ALPHA@) args[i]="$ALPHA_ROOT" ;;
           @BETA@)  args[i]="$BETA_ROOT" ;;
       esac
   done
   ```

Leave everything else alone. Sections 2 and 4 already pass `"$ALPHA_ROOT"`
quoted, and `write_registry` writes the paths through `printf %s`. A side
benefit: the outer `IFS='|'` split no longer sees path bytes either.

## Verification

- `bash tests/test_projects_unreadable_registry.sh` → all pass (normal TMPDIR).
- `TMPDIR="<scratch>/sp ace" bash tests/test_projects_unreadable_registry.sh`
  → all pass (was 139/145 before the fix).
- `shellcheck tests/test_projects_unreadable_registry.sh` → no new warnings.

## Step 9 (Post-Implementation)

Commit `bug: Keep fixture paths whole in the unreadable-registry test (t2165)`,
then archive per the workflow's Step 9.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.
