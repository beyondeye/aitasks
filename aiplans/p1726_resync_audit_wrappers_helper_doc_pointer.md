---
Task: t1726_resync_audit_wrappers_helper_doc_pointer.md
Branch: main
Base branch: main
Output branch: main
---

# t1726 — Resync the audit-wrappers helper-script doc pointer

## Context

`.claude/skills/aitask-audit-wrappers/SKILL.md` tells readers that the
helper-permission touchpoints scanned by its Phase 2 are defined in
CLAUDE.md "Adding a New Helper Script". That section no longer lives in
CLAUDE.md — it moved to `aidocs/framework/aitasks_extension_points.md`
(`## Adding a new helper script`, line 298), and CLAUDE.md now only carries a
one-line pointer at it (CLAUDE.md:191). A reader following the skill's reference
lands on a file that does not contain what it promises.

t1717 corrected the identical pointer in `aitask_audit_wrappers.sh::usage()`
(line 676) because that line was already being edited; the skill copies were
deferred to this task.

## Findings that narrow the task's stated scope

Two premises in the task description do not hold. Both were verified, and both
**reduce** the work rather than change the goal:

1. **The rendered Codex/OpenCode wrapper trees do not replicate the pointer.**
   `.agents/skills/aitask-audit-wrappers/SKILL.md` (20 lines) and
   `.opencode/skills/aitask-audit-wrappers/SKILL.md` (17 lines) are thin
   source-of-truth stubs that say "read `.claude/skills/aitask-audit-wrappers/SKILL.md`";
   `.opencode/commands/aitask-audit-wrappers.md` `@`-includes the same file. A
   repo-wide `grep -rln 'Adding a New Helper Script' .` returns exactly one
   path: the Claude source skill.

2. **`aitask-audit-wrappers` is a static skill, not a profile-aware one.**
   `.claude/skills/aitask-audit-wrappers/` contains `SKILL.md` and nothing else
   — no `SKILL.md.j2` — and `tests/golden/skills/` holds no `aitask-audit-wrappers`
   entry (its 13 entries are the `.j2`-backed skills).

Consequently the task's suggested `aitask_skill_rerender.sh <profile>` fan-out
and goldens regeneration are **not applicable** and will be skipped, not run.
`./.aitask-scripts/aitask_skill_verify.sh` is still run as the pre-commit check
CLAUDE.md mandates for any skill-surface change.

## Implementation

### 1. Correct both pointers in the source skill

`.claude/skills/aitask-audit-wrappers/SKILL.md`

**Line 15** (Overview, last sentence) — replace the trailing clause:

```
… extends the audit to helper-script whitelist coverage across the
helper-permission touchpoints from CLAUDE.md "Adding a New Helper Script".
```
with
```
… extends the audit to helper-script whitelist coverage across the
helper-permission touchpoints from `aidocs/framework/aitasks_extension_points.md`
"Adding a new helper script".
```

**Line 181** (`## See also`) — replace the bullet:

```
- CLAUDE.md "Adding a New Helper Script" — defines the helper-script whitelist touchpoints scanned by Phase 2.
```
with
```
- `aidocs/framework/aitasks_extension_points.md` "Adding a new helper script" — defines the helper-script whitelist touchpoints scanned by Phase 2.
```

The quoted heading is lower-cased to match the real heading text verbatim, and
the path is backticked to match how `aitask_audit_wrappers.sh::usage()` (line
676) already spells the same reference — one wording across both surfaces.

**Deliberately not changed:** line 180's `CLAUDE.md "WORKING ON SKILLS / CUSTOM
COMMANDS"` (real heading: `## Working on Skills / Custom Commands`). That
pointer names the correct file and the correct section; only its casing drifted.
Its twin lives in `website/content/docs/development/skills/aitask-audit-wrappers.md:93`,
so fixing one and not the other would introduce drift where there is currently
agreement, and fixing both drags a website build + `check_links.py` run into a
prose-pointer task. Left as-is on purpose, and reported.

### 2. Guard the pointer so it cannot silently go stale again

Extend `tests/test_touchpoint_count_contract.sh` with a **Test 7**. That file's
own header states its charter — "the prose count silently went stale once
already (t1717) … Nothing failed, because nothing checked. This is that check."
— and this defect is the same class on the same surfaces, so it belongs there
rather than in a new file.

Add near the other path constants (after `AUDIT_SKILL=` at line 38):

```bash
CLAUDE_MD="CLAUDE.md"
```

Append before the `# --- Summary ---` block:

```bash
# --- Test 7: the helper-script section pointer names its real owner ---
#
# The "Adding a new helper script" section moved out of CLAUDE.md into
# aidocs/framework/aitasks_extension_points.md. Both the helper's usage() text
# and the audit-wrappers skill cite it by name, and the skill's citation stayed
# pointed at CLAUDE.md for months (t1726). These assertions pin the ownership
# and both citations of it.

assert_contains "$EXT_POINTS owns the 'Adding a new helper script' section" \
    "$(cat "$EXT_POINTS")" "## Adding a new helper script"

assert_not_contains "$CLAUDE_MD no longer carries that section heading" \
    "$(grep '^#' "$CLAUDE_MD")" "Adding a new helper script"

assert_contains "$AUDIT_SH usage() cites $EXT_POINTS for the touchpoints" \
    "$(cat "$AUDIT_SH")" "aitasks_extension_points.md"

assert_contains "$AUDIT_SKILL cites $EXT_POINTS for the touchpoints" \
    "$(cat "$AUDIT_SKILL")" "aitasks_extension_points.md"

assert_eq "$AUDIT_SKILL attributes no helper-script prose to CLAUDE.md" "0" \
    "$(grep -ci 'CLAUDE\.md[^|]*helper' "$AUDIT_SKILL" || true)"
```

The first three assertions are phrasing-tolerant and carry the load: they pin
*which file owns the section* and *that both citing surfaces name it*. The last
is narrow by design — it catches the exact regression observed — and cannot pass
vacuously, because `grep -c` on a present file always emits a count.

Note the `|| true`: `grep -c` exits 1 on zero matches under this file's
`set -u`-only (no `-e`) regime, so the guard is written to yield `0` rather than
an empty string, which would compare unequal and fail for the wrong reason.

The file's test bodies run in-process (no `( … )` subshells), so the
`assert_counters_init` / `assert_counters_load` opt-in required by CLAUDE.md
does not apply here; the existing in-process `PASS`/`FAIL` counters are correct.

Existing tests are untouched — Test 5 parses the skill's touchpoint **table**
(`| <id> | \`<file>\` |` rows), which neither edited line resembles.

## Verification

1. **The guard fails before the fix and passes after** (negative control —
   prove the new assertions can fail). Apply the **test edit first, alone**,
   and run the file against the still-unmodified skill:
   ```bash
   bash tests/test_touchpoint_count_contract.sh
   ```
   The `AUDIT_SKILL cites …` and `attributes no helper-script prose to
   CLAUDE.md` assertions must **FAIL** here, and the file must exit non-zero.
   Then apply the skill edit and re-run — all assertions pass. Do this by
   ordering the two edits, never by stashing or reverting the skill file.

2. **Full contract test:**
   ```bash
   bash tests/test_touchpoint_count_contract.sh
   ```
   Expect `PASS: <n>, FAIL: 0` and exit 0.

3. **Skill-surface verification** (CLAUDE.md pre-commit requirement):
   ```bash
   ./.aitask-scripts/aitask_skill_verify.sh
   ```
   Expect exit 0. `aitask-audit-wrappers` has no `.j2`, so this is a
   no-regression check on the other skills and the wrapper-set parity check.

4. **Shellcheck the edited test:**
   ```bash
   shellcheck tests/test_touchpoint_count_contract.sh
   ```

5. **Re-grep the acceptance criterion** — no tree still carries the stale
   pointer:
   ```bash
   grep -rn 'CLAUDE.md "Adding a New Helper Script"' . ; echo "rc=$?"
   ```
   Expect no output and `rc=1`.

6. **Confirm the wrapper trees still agree** (they carry no prose copy, so
   nothing should have changed):
   ```bash
   git status --short .agents .opencode
   ```
   Expect empty.

## Risk

### Code-health risk: low
- Two prose lines in a non-executable skill document plus five assertions in an
  existing self-contained test file. No runtime code path, no shared library, no
  rendered artifact. The one mechanical hazard — `grep -c` exiting 1 on zero
  matches and yielding an empty string — is handled explicitly in the plan
  (`|| true`) and is caught by verification step 1's negative control.
  · severity: low · → mitigation: none needed

### Goal-achievement risk: low
- The stated goal (skill names the right document) is a verbatim text change
  whose completion is checked by an executable grep (verification step 5), and
  the deferred-scope decisions (rendered trees, goldens, line 180) are recorded
  above with the evidence that motivated them rather than left implicit.
  · severity: low · → mitigation: none needed

No mitigations proposed: neither dimension surfaced a risk worth a
before/after task or an inline phase.

## Step 9 (Post-Implementation)

Current-branch mode — nothing to merge. Step 9 commits the two paths
(`.claude/skills/aitask-audit-wrappers/SKILL.md`,
`tests/test_touchpoint_count_contract.sh`) as `bug: …(t1726)`, runs the
`risk_evaluated` gate, and archives `t1726` + `p1726` once the gate passes.

## Final Implementation Notes

- **Actual work done:** Both stale pointers in
  `.claude/skills/aitask-audit-wrappers/SKILL.md` (Overview line 15, `## See also`
  line 181) now name `` `aidocs/framework/aitasks_extension_points.md` `` "Adding a
  new helper script", matching the spelling `aitask_audit_wrappers.sh::usage()`
  already uses. `tests/test_touchpoint_count_contract.sh` gained a `CLAUDE_MD`
  constant and a Test 7 block of five assertions pinning section ownership and both
  citations of it. No other file changed — confirmed by
  `git status --short .agents .opencode` returning empty.

- **Deviations from plan:** None in scope or outcome. One correction during
  implementation: the plan's Test 7 draft passed `assert_contains` its arguments in
  the order `(desc, haystack, needle)`, but the real signature in
  `tests/lib/asserts.sh:179` is `(desc, needle, haystack)`. With a whole file as the
  needle, `grep -qF` matches on any single line — including a blank one — so two of
  the five assertions passed **vacuously**. Caught by the plan's own negative
  control, which predicted two pre-fix failures and produced only one. All five
  assertions were rewritten as `assert_eq` count comparisons, which keeps failure
  output short and cannot pass vacuously. The rerun then failed exactly the two
  predicted assertions. The plan's `|| true` note (`grep -c` exits 1 on zero matches
  under this file's `set -u`-without-`-e` regime) carried over and is now a code
  comment.

- **Issues encountered:** The Remote Drift Check first reported `AHEAD:3` with
  `OVERLAP` on both files this task targets. Investigation showed the overlap was
  spurious — the three remote commits (t1705_2, t1716, t1705_1) touch neither file;
  the flag came from local `main` being 12 commits ahead of a **stale** `origin/main`
  ref, which put local-only t1717 content into the tip-to-tip diff. After
  `git fetch origin main` the check returned `UP_TO_DATE`.

- **Key decisions:**
  - **Rerender and goldens skipped, deliberately.** The task's suggested fix called
    for `aitask_skill_rerender.sh <profile>` across every profile plus goldens
    regeneration. Neither applies: `.claude/skills/aitask-audit-wrappers/` holds no
    `SKILL.md.j2` (it is a static skill), and `tests/golden/skills/` carries no
    `aitask-audit-wrappers` entry. Running the rerender would have churned unrelated
    skills' rendered variants for no effect on this fix.
  - **The task's "replicated across the rendered Codex/OpenCode wrapper trees"
    premise does not hold.** `.agents/skills/aitask-audit-wrappers/SKILL.md` (20
    lines) and `.opencode/skills/aitask-audit-wrappers/SKILL.md` (17 lines) are thin
    source-of-truth stubs, and `.opencode/commands/aitask-audit-wrappers.md`
    `@`-includes the Claude file. A repo-wide grep for the stale phrase matched
    exactly one path.
  - **Line 180 left unchanged on purpose.** `CLAUDE.md "WORKING ON SKILLS / CUSTOM
    COMMANDS"` names the right file and right section; only its casing drifted from
    the real `## Working on Skills / Custom Commands`. Its twin lives at
    `website/content/docs/development/skills/aitask-audit-wrappers.md:93`, so fixing
    one and not the other would create drift where the two currently agree, and
    fixing both would drag a Hugo build plus `check_links.py` into a prose-pointer
    task.
  - **Guard placed in the existing contract test, not a new file.** That file's own
    header states its charter — the t1717 count "silently went stale … Nothing
    failed, because nothing checked" — and this is the same class of defect on the
    same surfaces. Test 7 also pins t1717's own `usage()` fix, which was previously
    unguarded.

- **Upstream defects identified:** None
