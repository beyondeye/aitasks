---
Task: t1325_skill_surface_guards_self_referential.md
Worktree: (none — current-branch mode)
Branch: main
Base branch: main
Output branch: main
---

# t1325 — Fix the self-referential / incomplete skill-surface guards

## Context

t1317 found that `.opencode/skills/aitask-trail/SKILL.md` had been missing since
t1210_3 (`3386e1f43`). t1325 exists to close the *reasons it went unnoticed*.

Two of the task's three stated premises hold; one does not. Verified during
planning:

1. **`tests/test_opencode_setup.sh:22` is self-referential — confirmed.**
   `expected_skill_count` comes from `git ls-files '.opencode/skills/aitask-*/SKILL.md'`,
   the very tree the test packages. A missing wrapper lowers both sides. It also
   silently counts **30**, not 28: the glob matches the two committed rendered
   variants `aitask-pickrem-remote-/` and `aitask-pickweb-remote-/`.

2. **`aitask_skill_verify.sh` omits the OpenCode skill-dir surface — confirmed.**
   Its comment at line 127 says "4 surfaces per skill" but `agents=(claude codex
   opencode)` produces 3, and `_stub_path_for` maps opencode only to
   `.opencode/commands/<skill>.md`. `stub-skill-pattern.md` §3g note says of the
   skill-dir stub: "**Both are required surfaces.**" This is the highest-value
   fix: CLAUDE.md mandates running this script before committing any skill
   change, so a guard added here actually runs.

3. **"No existing guard could see it" — false.**
   `tests/test_opencode_skill_legacy_pointers.sh:34-43` already asserts
   `.opencode/skills/<skill>/SKILL.md` exists for every templated skill,
   including `aitask-trail`. It would have failed from `3386e1f43` until t1317.
   The gap survived because that bash test is **never run** (no runner; CLAUDE.md
   says bash tests are run individually), not because no guard existed. Root
   cause = guard placement, not guard absence — hence fix 2 above, and hence the
   new parity check goes in the pre-commit script as well as in tests.

The task's suggested ground truth ("templated-skill discovery plus the
user-invocable skill list") is not usable: `user-invocable` is declared on only 9
of ~80 `.claude/skills/` dirs and is `true` for `aitask-explorechat`, which is
deliberately unwrapped. The 28 wrapped skills are `.claude/skills/aitask-*` minus
4 deliberately-unwrapped ones (`explorechat`, `run-gates`, `gate-docs-updated`,
`gate-template`) — a subtraction nothing in the repo encodes.

**Ground truth chosen (user-confirmed): cross-tree parity.** The three ported
wrapper trees are independently authored, so requiring identical membership is
independent of any single tree — and it catches the real failure mode. t1210_3
added `aitask-trail` to 2 of the 3 trees; parity would have flagged it
immediately.

## Approach

One shared helper, two call sites (no duplicated set logic), plus the surface fix
and a documentation sweep of the places that encode the wrong premise.

### 1. `.aitask-scripts/aitask_audit_wrappers.sh` — new `parity` subcommand

This script already owns the wrapper-tree vocabulary (`wrapper_path()`,
`TREE_AGENTS_SKILLS` / `TREE_OPENCODE_SKILLS` / `TREE_OPENCODE_COMMANDS`, lines
27-30, 88-97), so the check belongs here rather than being reimplemented twice.

- Add `list_wrapper_skills <root> <tree>` — names present in one wrapper tree.
  **Excludes trailing-hyphen dir names**: those are rendered per-profile variants
  (the `*-/` gitignore convention), not stubs. This is exactly the filter whose
  absence makes the `git ls-files` count 30 instead of 28.
- Add `cmd_parity [--strict] [<root>]` — root-scoped (defaults to `REPO_ROOT`,
  all paths built as `<root>/…`, no `cd`, no ambient state) so a test can point
  it at a synthetic fixture. Over the union of the three trees it emits:
  - `PARITY_GAP:<tree>:<skill>` — present in ≥1 wrapper tree, missing from `<tree>`.
  - `ORPHAN:<skill>` — a wrapper with no `.claude/skills/<skill>/SKILL.md`.
- **Exit-code contract.** The script's `usage()` states *"All subcommands exit 0
  on success"*, and its sibling reporters (`discover` → `GAP:`,
  `audit-helper-whitelist` → `MISSING:`) exit 0 while emitting findings. `parity`
  keeps that convention by default. `--strict` exits **2** when any line was
  emitted — deliberately **not** 1, which `die()` (`lib/terminal_compat.sh:17`)
  already owns for usage/infrastructure errors, so a caller can tell "gaps found"
  from "the check could not run". Clean run: no output, exit 0 in both modes.
- **Tree-presence rule (per case, not per summary).** Mirror
  `aitask_learn_wrappers.sh:78-85`'s `_tree_root_present()`, root-scoped and
  per-tree-dir (`<root>/.agents/skills`, `<root>/.opencode/skills`,
  `<root>/.opencode/commands`):
  - Tree root **absent** → that agent is not installed in this project; drop it
    from the comparison entirely. Without this, `aitask_skill_verify.sh` would
    report every skill as a gap in a consumer project that only installed Claude.
  - Tree root **present**, wrapper missing → `PARITY_GAP`. Fails closed.
  - Fewer than 2 roots present → nothing can disagree; emit nothing, exit 0.
  - The `ORPHAN` check runs whenever ≥1 wrapper tree is present.
- Wire `parity` into the dispatcher + `usage()` (including the `--strict` exit-2
  contract, since the usage block currently promises exit 0 for everything).
- **Also fix `list_source_skills()` (lines 36-45)** to skip trailing-hyphen dirs.
  Today it lists rendered variants such as `aitask-pick-fast-`, so
  `/aitask-audit-wrappers` offers to create wrappers for generated dirs. Same
  rule as above; it would be wrong to add the correct filter next to the broken
  one and leave it.
  *(Not fixed here: `list_source_skills()` also reports the 4 deliberately-
  unwrapped skills as gaps. Suppressing those needs an explicit exemption marker,
  which the user declined for this task — recorded as an upstream defect.)*

**Documented residual limit** (goes in the function comment): a skill removed
from all three trees at once stays invisible to parity. That is a deliberate
removal, not the omission this guard targets.

### 2. `.aitask-scripts/aitask_skill_verify.sh` — 4 surfaces + seam-derived Read path + parity

- Replace the agent-keyed stub loop with a **surface**-keyed one, matching the
  existing line-127 comment and §3g:
  `surfaces=(claude codex opencode-cmd opencode-skill)`, with `_surface_agent()`
  and `_stub_path_for <surface> <skill>` gaining
  `opencode-skill → .opencode/skills/$skill/SKILL.md`.
  The render / walk-check loops keep iterating `agents=(claude codex opencode)`.
- Replace the self-restated Read-path regex (lines 150-164, including the
  `agent_shared_skills_root` branch and the `stub_read_literal`/`_display` pair)
  with the canonical seam — `agent_skills_paths.sh` is already sourced at line 27:
  ```bash
  stub_read_path="$(agent_skill_dir "$agent" "$skill" "<profile>")/SKILL.md"
  grep -qF "$stub_read_path" "$stub_path"
  ```
  `agent_skill_dir` already applies the shared-root `-<agent>-` rule, so §3g stays
  the single source of truth. `-qF` also removes the regex-escaping footgun.
  Verified during planning: all 12 skills × 4 surfaces already carry this exact
  literal, so the stricter check is a clean pass.
- Add a wrapper-set parity section that shells out to
  `aitask_audit_wrappers.sh parity`, covering all 28 ported skills rather than
  only the 12 templated ones. **The call must stay in a condition context** —
  this script is `set -euo pipefail` (line 19), so a bare
  `out="$(… parity)"` would abort the verifier at the first finding, before any
  `WRAPPER_FAIL:` line is printed and before the remaining per-template failures
  are aggregated. Use the same shape the script already uses at lines 107/121/189
  and `test_skill_dispatch_contract.sh:189`:

  ```bash
  parity_rc=0
  parity_out="$("$SCRIPT_DIR/aitask_audit_wrappers.sh" parity 2>&1)" || parity_rc=$?
  if (( parity_rc != 0 )); then
      # `parity` (non-strict) exits 0 even with findings, so ANY non-zero here is
      # the check failing to run — never an ordinary result. Fail closed.
      printf 'VERIFY_FAIL: wrapper parity check could not run (exit %d):\n%s\n' \
          "$parity_rc" "$parity_out" >&2
      failures=$((failures + 1))
  else
      while IFS= read -r line; do
          case "$line" in
              "")                    continue ;;
              PARITY_GAP:*|ORPHAN:*) printf 'WRAPPER_FAIL: %s\n' "$line" >&2
                                     failures=$((failures + 1)) ;;
              *)                     printf 'VERIFY_FAIL: unrecognized parity output: %s\n' "$line" >&2
                                     failures=$((failures + 1)) ;;
          esac
      done <<< "$parity_out"
  fi
  ```

  Non-strict mode is used deliberately: findings arrive as parsed lines, so the
  verifier reports *which* wrapper is missing instead of a bare status. `2>&1` is
  safe because any line not matching a known prefix is classified as a failure
  rather than ignored.
- Update the file header comment to state the broadened remit.

### 3. `tests/test_skill_verify.sh` — keep the pre-commit gate's own test honest

Its `_write_canonical_stubs()` (line 54) is captioned "the canonical 4 stub
surfaces" but writes **3** — the same latent bug. Without this, change 2 breaks
Tests 2 and 4-8.

- Add the `.opencode/skills/$skill/SKILL.md` stub to `_write_canonical_stubs()`
  and to `cleanup()`'s scratch removal (already covers `.opencode/skills/`).
- Add a Test 3 assertion for the 4th missing-stub message
  (`.opencode/skills/$SK_NOSTUB/SKILL.md: missing stub for opencode-skill`) —
  this is the assertion that would have failed on the aitask-trail shape.
- Add a case that writes all 4 stubs, then deletes only the opencode-skill one,
  and asserts the verifier exits non-zero naming it. Proves the new surface is
  load-bearing and not merely present.

### 4. `tests/test_opencode_setup.sh` — Test 0: wrapper-set ground truth

- New **Test 0**, before packaging: run `aitask_audit_wrappers.sh parity`, assert
  exit 0 and empty output; on failure print the gap lines so the diagnosis is the
  missing name, not a count mismatch.
- **Negative controls proving every promised parity branch is load-bearing.**
  Build a synthetic root under `$TEST_DIR/parity_fixture/` with two fake skills,
  `aitask-alpha` and `aitask-beta`, wired into `.claude/skills/<n>/SKILL.md` plus
  all three wrapper trees — and, as decoys, rendered-variant dirs
  `.claude/skills/aitask-alpha-fast-/SKILL.md` and
  `.opencode/skills/aitask-alpha-fast-/SKILL.md`.

  Each case asserts the **exact structured line** (`assert_contains`, fixed
  string) *and* the exit status, via `parity --strict <root>` for the status
  (exit **2** = findings, distinct from `die`'s 1) and `parity <root>` for the
  lines. After each case the mutation is undone by recreating just that file —
  never `git checkout` — and the fixture is re-asserted clean.

  | # | Mutation | Must emit | `--strict` rc |
  |---|---|---|---|
  | NC-0 | none (positive control) | *(no output)* | 0 |
  | NC-1 | `rm .agents/skills/aitask-beta/SKILL.md` | `PARITY_GAP:agents:aitask-beta` | 2 |
  | NC-2 | `rm .opencode/skills/aitask-beta/SKILL.md` | `PARITY_GAP:opencode-skill:aitask-beta` | 2 |
  | NC-3 | `rm .opencode/commands/aitask-beta.md` | `PARITY_GAP:opencode-command:aitask-beta` | 2 |
  | NC-4 | `rm .claude/skills/aitask-beta/SKILL.md` | `ORPHAN:aitask-beta` **and no** `PARITY_GAP:*:aitask-beta` | 2 |
  | NC-5 | `rm -r .agents/skills` (whole root) | *(no output — tree not installed)* | 0 |
  | NC-6 | restore all | *(no output)* | 0 |

  NC-1..NC-3 make each tree mapping load-bearing; NC-4 pins `ORPHAN` as a
  *distinct* branch (all three wrappers still present, so it must not also report
  a gap); NC-5 pins the tree-absent rule so it cannot silently become a
  fail-closed trap for Claude-only projects. NC-0/NC-6 keep a failing control
  from being explained away by a broken fixture. The decoy dirs assert no line
  ever mentions `aitask-alpha-fast-`, proving rendered variants are excluded —
  the exact filter whose absence makes the live `git ls-files` count 30 not 28.

  Restore for the whole fixture is `rm -rf $TEST_DIR` (the existing `trap`); the
  real repo trees are never mutated.
- Rename `expected_skill_count` → `expected_packaged_count` and rewrite the
  lines 20-21 comment: these counts guard **packaging/staging drift only** (does
  the pipeline preserve what it was handed), and they legitimately count the
  committed rendered variants because the release workflow
  (`.github/workflows/release.yml:72`) copies every `.opencode/skills/*/` dir.
  Source-wrapper completeness is Test 0's job. This kills the misleading
  "self-maintaining as the catalog grows" comment that invited the original trap.

### 5. Documentation sweep — the places that encode the wrong premise

- `.gitignore:43` — `.claude/skills/task-workflow/stub-skill-pattern.md` →
  `aidocs/framework/stub-skill-pattern.md` (the task's third item).
- `.aitask-scripts/aitask_setup.sh:1483` — **same stale path**, in the gitignore
  block written into *consumer* projects. `aidocs/framework/` does not exist
  there, so point at the public page instead:
  `https://www.aitasks.io/docs/concepts/skill-templating/`.
- `aidocs/framework/skill_authoring_conventions.md:186-187` — currently declares
  `git ls-files '.opencode/skills/aitask-*/SKILL.md'` the canonical counting rule
  and names `test_opencode_setup.sh` the canonical usage. That is the doc that
  *sanctioned* the circular check, and it is off by 2. Replace with the
  cross-tree parity rule and point at `aitask_audit_wrappers.sh parity`.
- `aidocs/framework/stub-skill-pattern.md` §3f line 108 — "3 stubs total per
  skill" contradicts line 104 ("4 stubs") and the §3g note ("Both are required
  surfaces"). Make it 4, listing the OpenCode skill-dir stub.
- `aidocs/framework/adding_a_new_codeagent.md` §12 — one line naming
  `aitask_audit_wrappers.sh parity` as the enforced cross-tree invariant, so the
  doc↔module cross-reference is bidirectional.

## Files touched

| File | Change |
|---|---|
| `.aitask-scripts/aitask_audit_wrappers.sh` | `+cmd_parity`, `+list_wrapper_skills`, dispatcher/usage, fix `list_source_skills` |
| `.aitask-scripts/aitask_skill_verify.sh` | 4 surfaces, seam-derived Read path, parity call, header |
| `tests/test_skill_verify.sh` | 4th stub in `_write_canonical_stubs`, +2 assertions/cases |
| `tests/test_opencode_setup.sh` | +Test 0 + negative control, honest count naming/comment |
| `.gitignore` | line 43 path |
| `.aitask-scripts/aitask_setup.sh` | line 1483 path → public docs URL |
| `aidocs/framework/skill_authoring_conventions.md` | counting rule → parity rule |
| `aidocs/framework/stub-skill-pattern.md` | §3f 3 → 4 surfaces |
| `aidocs/framework/adding_a_new_codeagent.md` | §12 parity cross-ref |

No `.md.j2` or closure edits, so no goldens regeneration and no rerender.

## Verification

Baselines captured during planning: `aitask_skill_verify.sh` → `OK (12
template(s))`, `test_opencode_setup.sh` → `31 passed, 0 failed`.

```bash
./.aitask-scripts/aitask_skill_verify.sh                    # expect OK, now 4 surfaces
./.aitask-scripts/aitask_audit_wrappers.sh parity           # expect silent, exit 0
./.aitask-scripts/aitask_audit_wrappers.sh parity --strict  # expect silent, exit 0
./.aitask-scripts/aitask_audit_wrappers.sh discover | grep -v -- '-:'  # no rendered-variant GAPs
bash tests/test_skill_verify.sh
bash tests/test_opencode_setup.sh
bash tests/test_opencode_skill_legacy_pointers.sh
bash tests/test_skill_dispatch_contract.sh
shellcheck .aitask-scripts/aitask_skill_verify.sh .aitask-scripts/aitask_audit_wrappers.sh \
           .aitask-scripts/aitask_setup.sh
```

End-to-end proof that the guards now discriminate (the whole point of the task —
each must make the suite exit 1, then be undone by restoring only the mutation):

1. `mv .opencode/skills/aitask-trail/SKILL.md /tmp/` → `aitask_skill_verify.sh`
   must fail with **both** a `STUB_FAIL … opencode-skill` and a
   `WRAPPER_FAIL: PARITY_GAP:opencode-skill:aitask-trail`, must still print the
   per-template failures that follow it (proving the `set -e` capture works), and
   must exit 1; `mv` back and re-run to confirm OK.
2. `mv .opencode/skills/aitask-stats/SKILL.md /tmp/` (a **non**-templated skill,
   invisible to every existing guard) → `test_opencode_setup.sh` Test 0 must
   fail; `mv` back. This is the case no current test can see.
3. Confirm the automated negative controls in `test_opencode_setup.sh` fail when
   their own assertions are inverted, so a green suite is not vacuous.

## Step 9 (Post-Implementation)

Current-branch mode — no worktree/branch cleanup. Merge target `main` (= base).
`ait gates run 1325` runs the declared `risk_evaluated` gate; then archive via
`./.aitask-scripts/aitask_archive.sh 1325`.

## Risk

### Code-health risk: medium
- `aitask_skill_verify.sh` is a **mandated pre-commit gate**; a false positive
  from the new 4th surface or the stricter `grep -qF` Read-path check would block
  every skill commit repo-wide. Bounded: all 12 skills × 4 surfaces were verified
  during planning to carry the exact `agent_skill_dir`-derived literal, so the
  change is a proven clean pass today. · severity: medium · → mitigation: TBD
- The parity check makes `aitask_skill_verify.sh` fail on wrapper-tree state that
  has nothing to do with the skill being committed, so an unrelated pre-existing
  gap would block an innocent commit. Bounded: the three trees are in exact 1:1
  agreement today (28/28/28, verified). · severity: low · → mitigation: TBD
- `test_skill_verify.sh` runs the verifier against the **real** repo with scratch
  skills written into the live agent trees; the 4th-surface addition must be
  mirrored in `cleanup()` or scratch files leak into the working tree. Scratch
  names are `_t777_4_test_*`, outside the `aitask-*` filter, so they cannot
  perturb parity. · severity: low · → mitigation: TBD
- Cross-tree parity cannot see a skill dropped from all three trees at once. Not
  a regression (nothing detects that today) and it is documented in the helper.
  · severity: low · → mitigation: TBD
- `parity --strict` exits **2** on findings, diverging from the script's blanket
  "all subcommands exit 0" contract. A caller that treats any non-zero as a crash
  would misreport findings. Contained: the divergence is stated in `usage()`, the
  only production caller (`aitask_skill_verify.sh`) uses non-strict mode, and the
  code is pinned by NC-1..NC-5. · severity: low · → mitigation: TBD
- `aitask_skill_verify.sh` now fails on `.agents/` and `.opencode/` state in
  *consumer* projects, where it previously only read `.claude/`. The tree-absent
  rule is what keeps a Claude-only install passing, so that rule is load-bearing
  rather than cosmetic — pinned by NC-5. · severity: medium · → mitigation: TBD

### Goal-achievement risk: low
- The task's suggested ground truth was shown to encode a wrong premise and was
  replaced with a user-confirmed alternative; the "no guard could see it"
  rationale was corrected in the Context section rather than designed around.
  · severity: low · → mitigation: TBD
- The parity guard covers all 28 ported skills, where the pre-existing guards
  covered only the 12 templated ones, so the delivered scope is strictly wider
  than the reported defect. · severity: low · → mitigation: TBD
