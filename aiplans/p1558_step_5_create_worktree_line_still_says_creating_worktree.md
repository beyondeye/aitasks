---
Task: t1558_step_5_create_worktree_line_still_says_creating_worktree.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1558 — Step 5's `create_worktree` surfaces still announce creation at Step 5

## Context

t1536 deferred the worktree fork from Step 5 to Step 7 and reworded Step 5's
**base-branch** surfaces to say so — both the interactive question and the
profile-driven display line now end with "… the branch and worktree are created
after plan approval and the remote drift check, not now."

The `create_worktree` surfaces immediately **above** them were missed. Under a
`create_worktree: true` profile, Step 5's *first* output still says a worktree
is being created, while nothing is cut until Step 7's "Deferred worktree fork"
block. A user who believes the fork already happened misjudges every later stop
path (drift stop, approve-and-stop, decomposed parent) — precisely the
misreading the t1536 wording change exists to prevent. The interactive
counterpart has the same problem and carries no deferral sentence at all.

Found during t1546 (manual verification of t1536); recorded in
`aiplans/p1546_manual_verification_auto.md` under "## Finding".

**Outcome:** every `create_worktree` surface in Step 5 states the deferral, in
the same words the base-branch surfaces already use — and the `true` branch,
which no committed profile renders, gains an executable test pin so it cannot
silently drift again.

## Exploration findings

- The authoring template is `.claude/skills/task-workflow/SKILL.md` (Jinja
  inline in the `.md` — there is no separate `.j2` for this file, contrary to
  the task text).
- Three defective lines, all in the `create_worktree` guard at
  `.claude/skills/task-workflow/SKILL.md:331-344`:
  - **332** — Jinja-baked `true` branch: `- Create a separate branch and
    worktree for this task. Display: "Profile '{{ profile.name }}': creating
    worktree".`
  - **337** — runtime fallback: `- If \`true\`: Create worktree. Display:
    "Profile '\<name\>': creating worktree"`
  - **342** — interactive question: `- "Do you want to create a separate branch
    and worktree for this task?"` (plus its **343** option label `"Yes, create
    worktree …"`)
- The `false` branch (333) and the `false` fallback rung (338) are correct —
  nothing is created either way; leave them.
- **Which branch renders where:** only `fast.yaml` defines `create_worktree`
  (`false`), so `default` and `remote` render the **fallback** (337/342);
  `fast` renders the **`false`** branch. The **`true`** branch renders under
  *no committed profile* — it is reachable only via a user profile or the
  synthetic profile in Test 4b. That is why it needs an explicit test pin.
- **Tracked artifacts that change:** the `remote` rendered variants are
  git-tracked (`.claude/skills/task-workflow-remote-/SKILL.md`,
  `.agents/skills/task-workflow-remote-codex-/SKILL.md`,
  `.opencode/skills/task-workflow-remote-/SKILL.md`); the `default`/`fast`
  rendered dirs are gitignored (`.gitignore:52`) but still get refreshed.
  Goldens: `tests/golden/procs/task-workflow/SKILL-{default,remote}.md`
  (`SKILL-fast.md` should come out byte-identical — verify, don't assume).
- **Parallel surface:** `.claude/skills/task-workflow/profiles.md:28` still
  reads `` `true` = create worktree `` / Step column `Step 5`, while the
  `base_branch` row directly below it was updated by t1536 to
  `Step 5 (resolve), Step 6 (recorded in the plan header)`. Same defect class,
  one table cell.
- **Deliberately out of scope:** `tests/fixtures/skills/task-workflow/SKILL.md.pre-rewrite`
  is a frozen historical fixture. `website/content/docs/skills/aitask-pick/execution-profiles.md:26`
  and `website/content/docs/tuis/settings/reference.md:111` describe what the
  key *means*, with no timing/step claim — t1536 did not touch them either.

## Implementation

**Execution order matters** — the negative controls in Verification depend on
it. Do the test edit (§3) **first**, then the template edits (§1, §2), then the
regeneration (§4). The sections below are ordered by subject, not by execution;
Verification step 1 spells out the run order.

### 1. `.claude/skills/task-workflow/SKILL.md` — the three surfaces

Reuse the **exact** display suffix the base-branch block already ships
(`SKILL.md:353/356`), so the two Step-5 surfaces read as one voice.

**Line 332** (Jinja `true` branch) →

```
{% if profile.create_worktree %}- Use a separate branch and worktree for this task. Display: "Profile '{{ profile.name }}': worktree mode — the branch and worktree are created after plan approval and the remote drift check, not now." Continue with the **If Yes** branch below.
```

**Line 337** (runtime fallback `true` rung) →

```
  - If `true`: Use a separate branch and worktree. Display: "Profile '\<name\>': worktree mode — the branch and worktree are created after plan approval and the remote drift check, not now."
```

**Lines 342-343** (the widget) — append the deferral **inside the question
text**, and drop the "create" tense from the affirmative option label:

```
  - "Do you want to create a separate branch and worktree for this task? Nothing is created now — the branch and worktree are cut at the start of implementation, after you approve the plan and the remote drift check passes."
  - Options: "No, work on current branch" (default, first option) / "Yes, use a separate worktree (recommended for complex features or when working in parallel on multiple features)"
```

The question's leading sentence is preserved verbatim — that is the substring
Test 3 (`tests/test_skill_render_task_workflow.sh:166`) pins, and it matches
what t1536 did to the base-branch question (append, don't rewrite). No
duplicate rationale paragraph: the block at `SKILL.md:364` already states the
"deferral belongs inside the question text" rule for all of Step 5.

### 2. `.claude/skills/task-workflow/profiles.md` — schema table row

Bring the `create_worktree` row into line with the `base_branch` row t1536
already fixed:

| from | to |
|---|---|
| `` `true` = create worktree; `false` = current branch `` / `Step 5` | `` `true` = worktree mode; `false` = current branch. The fork itself is cut at Step 7, after plan approval and the remote drift check `` / `Step 5 (resolve), Step 7 (fork)` |

### 3. `tests/test_skill_render_task_workflow.sh` — pin all three surfaces

- **Test 3** (default-profile fallback, after line 166): add
  `assert_contains "SKILL.md default: create_worktree question states the deferral"`
  on `'Nothing is created now — the branch and worktree are cut at the start of implementation'`,
  and `assert_not_contains "SKILL.md default: no creating-now claim"`
  on `"': creating worktree"`.
- **Test 4b** (synthetic profile at line ~228 already sets
  `create_worktree: true`, so the baked branch renders into `$OB_OUT`): add
  `assert_contains "create_worktree: true bakes the deferral into the display line"`
  on `"Profile 'test_output_branch': worktree mode — the branch and worktree are created after plan approval and the remote drift check, not now."`
  This is the only executable coverage the `true` branch can have — no
  committed profile renders it, so it has no golden.

Each pin is a single rendered line (a wrapped pin would guard nothing).

### 4. Regenerate — same commit

```bash
# rendered variants (one call per profile; refreshes the tracked remote trees)
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done

# procedure goldens
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md "aitasks/metadata/profiles/$p.yaml" claude \
    > "tests/golden/procs/task-workflow/SKILL-$p.md"
done
```

### Post-phase (risk mitigations)

1. `[path_scoped_commit_audit]` Before committing, run `git status --porcelain`
   and `git diff --stat` over the **whole** working tree and read the result.
   Then commit with an explicit path allowlist rather than the index:

   ```bash
   git commit -o -- \
     .claude/skills/task-workflow/SKILL.md \
     .claude/skills/task-workflow/profiles.md \
     .claude/skills/task-workflow-remote-/SKILL.md \
     .claude/skills/task-workflow-remote-/profiles.md \
     .agents/skills/task-workflow-remote-codex-/SKILL.md \
     .agents/skills/task-workflow-remote-codex-/profiles.md \
     .opencode/skills/task-workflow-remote-/SKILL.md \
     .opencode/skills/task-workflow-remote-/profiles.md \
     tests/test_skill_render_task_workflow.sh \
     tests/golden/procs/task-workflow/SKILL-default.md \
     tests/golden/procs/task-workflow/SKILL-remote.md
   ```

   Any tracked file dirtied by the rerender sweep that is **not** on this list
   is unrelated to t1558 — leave it out of the commit and report it.

## Verification

1. **Two negative controls, run at two different points.** They prove two
   different things and cannot share a run: a new pin can only be shown
   meaningful *before* the template is edited, while a stale golden can only be
   shown detected *after* the template is edited and *before* goldens are
   regenerated. Run `bash tests/test_skill_render_task_workflow.sh` at each
   marked point and record the named failing assertions:

   | # | state of the tree | run | required outcome |
   |---|---|---|---|
   | NC-A | §3 applied (test pins added); template **not yet** edited | suite | **FAILS** on exactly the new pins: `SKILL.md default: create_worktree question states the deferral`, `SKILL.md default: no creating-now claim`, `create_worktree: true bakes the deferral into the display line`. Every `golden SKILL × <profile>` assertion still **passes** — the template is untouched, so this run isolates the pins. |
   | NC-B | §1 + §2 applied (template edited); goldens **not yet** regenerated | suite | **FAILS** on exactly `golden SKILL × default` and `golden SKILL × remote` — proving the goldens do cover the changed lines and would have caught a stale-artifact commit. `golden SKILL × fast` still **passes** (the `false` branch is untouched). The three new pins from NC-A now **pass**. |
   | final | §4 applied (variants + goldens regenerated) | suite | **all green** |

   If NC-A passes, the pins are matching something that already exists and
   guard nothing — fix the pin before continuing. If NC-B does not name both
   `default` and `remote`, the golden coverage is not what this plan assumes.

2. `git diff` on the goldens — the diff is the audit signal, so read it rather
   than counting hunks. Expected changes, stated semantically:
   - `SKILL-default.md` and `SKILL-remote.md` — the same three rendered lines
     in each, all inside the `create_worktree` fallback block: the `If \`true\`:`
     display rung, the `AskUserQuestion` question text, and the affirmative
     option label. Nothing outside that block.
   - `SKILL-fast.md` — **unchanged** (`fast` renders the `false` branch, which
     this edit does not touch). A diff here means the edit leaked out of the
     `true`/fallback branches.
   Any golden hunk outside those three lines is a regression, not this edit.
3. `./.aitask-scripts/aitask_skill_verify.sh` — exits 0.
4. `git grep -n "creating worktree\|Create worktree" -- '.claude/**' '.agents/**' '.opencode/**' 'tests/golden/**'`
   returns **no** hits (the only surviving hit repo-wide is the frozen
   `tests/fixtures/skills/task-workflow/SKILL.md.pre-rewrite`).
5. Spot-check the rendered `remote` variant at the Step 5 block to confirm the
   two Step-5 surfaces (create_worktree + base_branch) now read as one voice.

## Step 9 (Post-Implementation)

Standard cleanup, archival and merge per `SKILL.md` Step 9.

## Risk

### Code-health risk: low

*(Reassessed after the inline mitigation was confirmed: the first bullet was
`medium` pre-mitigation; the `path_scoped_commit_audit` post-phase makes an
allowlisted commit an explicit plan step, leaving residual risk `low`. Bullet
severities below record the pre-mitigation assessment.)*

- `aitask_skill_rerender.sh` refreshes **every** rendered closure for a profile, not just task-workflow's, so the working tree can pick up regenerated files unrelated to this edit; a wholesale `git add -A` / index commit would sweep them into the t1558 commit. · severity: medium · → mitigation: inline post-phase path_scoped_commit_audit
- The template edit and its generated artifacts (3 tracked remote variants + 2 goldens) must land together; regenerating one and not the other ships a template edit with stale artifacts. · severity: low · → mitigation: none needed — `tests/test_skill_render_task_workflow.sh` Test 1 fails loudly on a stale golden, and the verification step diffs both

### Goal-achievement risk: low
- The `create_worktree: true` branch — the exact branch this task exists to fix — renders under **no committed profile**, so no golden can cover it. If the Test 4b pin is dropped or written to match a wrapped line, the fix ships unverified on its own subject. · severity: medium · → mitigation: none needed — the pin is step 3 of the implementation, and verification step 3 requires it to fail against the pre-edit template
- Two edits go slightly beyond the task's literal "Occurrences" list (the widget's affirmative option label, and the `profiles.md` schema row). Both are the same defect class and are flagged explicitly, so the reviewer can strike either without touching the rest. · severity: low · → mitigation: none needed

### Planned mitigations
- timing: post-phase | name: path_scoped_commit_audit | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — rerender sweep can dirty unrelated tracked files | desc: Audit the full working-tree diff and commit with an explicit path allowlist instead of the index
