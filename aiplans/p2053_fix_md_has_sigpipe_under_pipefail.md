---
Task: t2053_fix_md_has_sigpipe_under_pipefail.md
Base branch: main
Output branch: main
---

# t2053 — make `md_has` immune to SIGPIPE under `pipefail`

## Context

`tests/test_no_unscoped_task_commit.sh` runs under `set -uo pipefail` (line 98).
`md_has` (line 672) is

```bash
md_has() { printf '%s\n' ${MD_SOURCES[@]+"${MD_SOURCES[@]}"} | grep -qxF "$1"; }
```

`grep -q` exits on its first match; `printf` (≈917 args, several buffered
writes) is still writing, takes SIGPIPE, and under `pipefail` the pipeline
returns 141. So the scope assertions "the canonical teaching skill is in
scope" (`.claude/skills/ait-git/SKILL.md`, index 97) and, intermittently,
"the root instruction doc is in scope" (`CLAUDE.md`, index 380) fail although
the file IS enumerated. Reproduced this session: 4 of 5 runs of the task's
one-liner returned `rc=141`.

Audit of the file for other early-exit readers in a pipe under pipefail
(`| grep -q`, `| grep -m`, `| head`): line 672 is the only one. Lines 701 and
731 run `grep -q` on a **file argument** (no pipe), and the
`md_out_of_scope` pipeline uses `grep -E` without `-q` (reads all input) and
`|| true`. Nothing else to change.

## Steps

1. **Fix `md_has`** (`tests/test_no_unscoped_task_commit.sh:672`) — replace the
   pipeline with an in-shell loop, no reader that can exit early:

   ```bash
   # A loop, not `printf | grep -q`: grep -q exits on the first match, the
   # printf writer takes SIGPIPE, and under pipefail a present name returns
   # 141 (t2053).
   md_has() {
       local f
       for f in ${MD_SOURCES[@]+"${MD_SOURCES[@]}"}; do
           [[ "$f" == "$1" ]] && return 0
       done
       return 1
   }
   ```

   Exact (`==` with a quoted RHS → literal, whole-string) matching keeps the
   `grep -xF` semantics.

2. **Deterministic regression pin** — the real corpus only races, so add a
   fixture that would fail the old implementation every time. In the
   `# --- Negative controls` section (after the existing allowlist swaps, before
   the results footer), using the same save/swap/restore idiom as the
   `ACTIVE_*_ALLOWLIST` swaps there:

   ```bash
   # md_has under pipefail (t2053): the needle FIRST, then >64 KiB of padding,
   # so an early-exiting reader would leave the writer blocked on a full pipe
   # and SIGPIPE it every time -- the real corpus only races.
   SAVED_MD_SOURCES=(${MD_SOURCES[@]+"${MD_SOURCES[@]}"})
   MD_SOURCES=("needle/first.md")
   for _i in $(seq 1 4000); do MD_SOURCES+=("padding/entry_${_i}_xxxxxxxx.md"); done
   assert_exit_zero "md_has finds an early name under pipefail despite a large list" \
       md_has "needle/first.md"
   assert_exit_nonzero "md_has rejects a name not in the list" \
       md_has "needle/absent.md"
   MD_SOURCES=(${SAVED_MD_SOURCES[@]+"${SAVED_MD_SOURCES[@]}"})
   ```

   Both helpers exist in `tests/lib/asserts.sh` (243, 254) and run the
   command in-process (`md_has` sees the swapped global). The negative guards
   against a loop that always returns 0 (the old one-liner passes it too —
   the positive is the red proof). The file runs no assertion bodies in
   `( … )` subshells, so the counter opt-in from CLAUDE.md does not apply.

## Verification

- Red proof: run the pin against the old one-liner (scratch copy of the test
  with line 672 restored) → the "finds an early name" assertion FAILS.
- Green: `bash tests/test_no_unscoped_task_commit.sh` passes; run it ~10 times
  in a loop — all scope assertions PASS every run.
- `shellcheck tests/test_no_unscoped_task_commit.sh` — no new warnings.

## Out of scope (noted, not changed)

The same `printf … | grep -q` shape exists in other pipefail test files
(`test_change_surface.sh:90,100`, `test_setup_git.sh:857,894`,
`test_restore_flows_live.sh:237`, `test_attach_task_delete_decref.sh:175`,
`test_runner_python_isolation.sh:60,65`). Most pipe a single small string
(one write, no race), but they are not proven safe; candidate for a separate
follow-up task, not this one (the task scopes the audit to this file).

## Step 9

Post-implementation: commit the test change (`bug: … (t2053)`), then archive
via the standard Step 9 flow.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
None identified.

## Final Implementation Notes
- **Actual work done:** `md_has` in `tests/test_no_unscoped_task_commit.sh` now loops over `MD_SOURCES` in bash (exact `==` match, same semantics as `grep -xF`) instead of `printf | grep -qxF`. Added a deterministic pin in the negative-controls section: needle first + 4000 padding entries (>64 KiB), assert found; plus an absent-name negative. MD_SOURCES is saved/restored around it.
- **Deviations from plan:** None.
- **Issues encountered:** None. Red proof (old one-liner against the pin fixture, standalone harness under `set -uo pipefail`): 20/20 runs returned 141. Green: full file 103/103 passed in 10 consecutive runs. shellcheck: only pre-existing info-level notes (SC1091/SC2016), none on changed lines.
- **Key decisions:** Kept `md_has` reading the global (minimal change); the pin swaps the global using the same save/swap/restore idiom as the `ACTIVE_*_ALLOWLIST` controls. Audit of the file: line 672 was the only early-exit reader in a pipe; 701/731 `grep -q` read a file argument, and `md_out_of_scope` uses `grep -E` without `-q` plus `|| true`.
- **Upstream defects identified:** None
