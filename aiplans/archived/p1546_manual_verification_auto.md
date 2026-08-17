---
Task: t1546_manual_verification_defer_worktree_fork_until_after_plan_app.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
---

# t1546 — Manual verification (autonomous auto-execution record)

Verifies t1536 (*Defer the worktree fork until after plan approval*, commit
`bbafbd4f5`). Strategy: **autonomous** — each item's verification approach was
chosen on the fly and this file is the retroactive record of what was actually
run.

## Evidence classes used

| class | meaning |
|---|---|
| **behavioral** | a real command was executed against real git / a real helper and its output was asserted |
| **source-structural** | the claim is a property of the workflow *instruction*, checked across all 9 rendered variants (claude / codex / opencode × default / fast / remote) and the `.j2` authoring template |
| **deferred** | the claim can only be observed inside a live, multi-turn interactive `/aitask-pick` session |

t1536's change surface is ~90% agent-instruction prose (`task-workflow`
`SKILL.md` + `crash-recovery.md` / `task-abort.md` / `plan-externalization.md` /
`planning.md` / `plan-approved-stop.md` / `remote-drift-check.md`), with one
executable component (`aitask_plan_externalize.sh`). Behavioral evidence was
obtained wherever the item's mechanism is an executable snippet the skill
prescribes; the rest split into source-structural and deferred.

## Execution Log

### Item 1 — live pick under a `create_worktree: true` profile
- Approach: not automatable.
- Action run: `grep -rn create_worktree aitasks/metadata/profiles/ seed/` →
  only `fast.yaml:5:create_worktree: false` in both trees.
- Note: worktree mode *is* reachable without a custom profile — under `default`
  (which sets no `create_worktree` key) Step 5 asks "Do you want to create a
  separate branch and worktree for this task?" and answering Yes takes the path.
- Verdict: **defer** — a real run means implementing a real task end to end.

### Item 2 — Step 5 creates nothing
- Approach: source-structural + behavioral (Step 6 half).
- Action run: per-variant `awk '/^### Step 5:/,/^### Step 6:/'` piped to
  `grep -cE 'git worktree add|mkdir -p'`.
- Output: `0` for all 9 rendered variants. The sole
  `git worktree add -b aitask/<task_name>` occurrence per file sits inside Step
  7's **Deferred worktree fork** block (claude default/fast/remote: L469/L463/L469).
- Verdict: **pass**.

### Item 3 — Step 5 widget wording
- Approach: source-structural.
- Action run: `grep -n "Which branch should the new task branch be based on"`.
- Output: the question text itself ends "… The branch and worktree are not
  created now — they are cut at the start of implementation, after you approve
  the plan and the remote drift check passes." in all 9 variants + the template.
- Verdict: **pass** — the sentence is inside the widget, not adjacent prose.

### Item 4 — profile-driven display line
- Approach: source-structural.
- Action run: `grep -n "using base branch"`.
- Output: "Profile '<name>': using base branch <branch> — the branch and
  worktree are created after plan approval and the remote drift check, not now."
  in all 9 variants, and in **both** authoring branches of
  `.claude/skills/task-workflow/SKILL.md` (the Jinja-baked
  `{{ profile.base_branch }}` line L353 and the runtime profile-check line L356).
- Verdict: **pass**.

### Item 5 — plan header at Step 6, no directory on disk
- Approach: behavioral.
- Action run: scratch git repo + `aitask_plan_externalize.sh 77 --internal
  /tmp/int_plan.md --worktree aiwork/t77_add_widget --base-branch dev-base
  --output-branch dev-base`, then `ls -d aiwork`.
- Output: `EXTERNALIZED:aiplans/p77_add_widget.md`; header carried
  `Worktree: aiwork/t77_add_widget`, `Base branch: dev-base`,
  `Output branch: dev-base`; `ls -d aiwork` → *No such file or directory*.
  `bash tests/test_plan_externalize.sh` → `255 passed, 0 failed`.
- Verdict: **pass**.

### Items 6, 7, 8, 9, 10, 19 — live timing and stop paths
- Approach: not automatable (multi-turn interactive).
- Verdict: **defer**, each blocked on item 1. Item 6's *ordering* is
  source-verified under item 13; item 10's reuse half is mechanically covered by
  item 11.

### Item 11 — reuse after a `git worktree move`
- Approach: behavioral.
- Action run: created `aiwork/t99_demo` via
  `git worktree add -b aitask/t99_demo`, then `git worktree move` to
  `<scratch>/moved_wt`, then the Step-7 reuse extraction verbatim:
  ```bash
  reuse_dir=$(git worktree list --porcelain | awk -v b="branch refs/heads/aitask/t99_demo" '
    /^worktree /  { p = substr($0, 10) }
    $0 == b       { print p; exit }')
  ```
- Output: `reuse_dir=<scratch>/moved_wt`; `aiwork/t99_demo` gone.
- Verdict: **pass** — the record-aware scan returns the moved path, so the
  "silent implement-in-the-wrong-tree" failure mode is closed.

### Item 12 — re-entry under a different profile
- Approach: source-structural + behavioral (parser half).
- Action run: extracted the `### Re-entry Routing` block from every variant and
  `diff`ed: byte-identical across default/fast/remote **and** claude/codex/
  opencode. Executed the header-resolution snippets against four crafted plan
  headers (full / legacy / `aiwork/../../outside` / no `Worktree:` field).
- Output: `base=release-2 (plan header)` — i.e. the header wins, not the
  profile; `UNSAFE_WORKTREE:aiwork/../../outside`; empty field → ask/reuse-probe.
- Verdict: **defer** — the parser and the profile-invariance are verified, but
  no actual cross-profile resume was performed.

### Item 13 — re-entry ordering (drift check before the fork)
- Approach: source-structural.
- Output: the IMPLEMENT route reads "**first run the remote drift check, then**
  resume at Step 7 …" and re-runs "the Pre-implementation ownership guard, the
  **Deferred worktree fork** block, and the Agent Attribution Procedure, in that
  order"; the environment-setup step is explicitly read-only ("resolve here,
  fork later") with the rationale that forking there would pin the fork to the
  pre-drift HEAD.
- Verdict: **pass**.

### Item 14 — POSTIMPL resume
- Approach: source-structural.
- Output: "the fork block does **not** run at all … Proceed to Step 9 from the
  repo root", with the stated reason (an existing `aitask/<task_name>` would
  fail the cut, or an empty worktree would be merged).
- Verdict: **pass**.

### Item 15 — legacy plan without `Base branch:`
- Approach: behavioral (parse) + source-structural (confirm-and-adopt).
- Action run: the Re-entry Routing resolution snippet against a header carrying
  `Worktree:` and `Output branch:` but no `Base branch:`.
- Output: `base=main (legacy plan, no Base branch field)` — exactly the
  provenance value that triggers Step 7 check 2's confirmation
  `AskUserQuestion`. Source then adopts the answer
  (`base_branch="$confirmed_base"`) before the cut, which uses `"$base_branch"`;
  an unusable answer emits `UNUSABLE_BASE` and re-asks.
- Verdict: **pass**.

### Item 16 — abort before the fork
- Approach: behavioral.
- Action run: the three `task-abort.md` cleanup commands in a repo with no
  worktree and no `aitask/` branch, then the survey awk.
- Output: exit 0, nothing removed, survey empty → "clean abort" is truthful.
- Verdict: **pass**.

### Item 17 — abort after a worktree move
- Approach: behavioral.
- Action run: same cleanup commands after the move, then the survey awk.
- Output: cleanup silently missed the worktree (all three commands are
  `2>/dev/null || true` guarded); the survey printed `<scratch>/moved_wt`.
  `task-abort.md` instructs the agent to name that path and *not* report a clean
  abort.
- Verdict: **pass**.

### Item 18 — crash-recovery survey wording
- Approach: source-structural.
- Output: `- Worktree: <path, or "(none — current branch, or fork not reached)">`
  present exactly once in `crash-recovery.md` in all 9 rendered variants.
- Verdict: **pass**.

## Result

`TOTAL:19 PENDING:0 PASS:11 FAIL:0 SKIP:0 DEFER:8`

Deferred: 1, 6, 7, 8, 9, 10, 12, 19 — all requiring a live interactive
`/aitask-pick` in worktree mode.

## Finding (not a checklist failure)

Step 5's `create_worktree` profile-check line was **not** updated by t1536 and
still reads:

```
- If `true`: Create worktree. Display: "Profile '<name>': creating worktree"
```

present in all 9 rendered variants (L323) and in both authoring branches of
`.claude/skills/task-workflow/SKILL.md` (L332 Jinja-baked, L337 runtime). Under
the exact configuration item 1 asks for — a `create_worktree: true` profile —
Step 5 therefore announces "creating worktree" while nothing is created until
Step 7. The sibling base-branch line and the base-branch question were both
given the deferral sentence (items 3 and 4); this line was missed.

No checklist item's literal criterion is falsified (nothing *is* created, so
item 2 still holds), which is why it is recorded here rather than as a `fail`.

Spawned as **t1558** (`bug`, anchored to the t1536 topic root) — it also covers
the interactive counterpart, "Do you want to create a separate branch and
worktree for this task?", which has the same tense problem and no deferral
sentence.

## Cleanup

- `<scratchpad>/av5_repo` — scratch repo for the externalize run (removed).
- `<scratchpad>/av_wt` + `<scratchpad>/moved_wt` — scratch repo and moved
  worktree for the reuse/abort checks (removed).
- `<scratchpad>/hdr_*.md` — crafted plan headers (removed).
- No tmux sessions created. No files under `aitasks/` or `aiplans/` mutated
  other than this plan and t1546's own checklist.
