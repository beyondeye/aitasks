---
Task: t1764_manual_verification_abort_create_when_the_id_claim_fails_fol.md
Worktree: (none — fast profile, current branch)
Branch: main (current branch)
Base branch: main
---

# t1764 — Manual verification of t1755 (auto-execution record)

Autonomous auto-verification of the four checklist items. All four cover the
**interactive** `ait create` entry point, which `tests/test_create_id_claim_abort.sh`
does not reach (its four rows drive `--batch` / `--batch --finalize` only).

## Method

Every item ran against a throwaway fixture built by the framework's own
`tests/lib/test_scaffold.sh::setup_fake_aitask_repo` plus the file list from
`tests/test_create_id_claim_abort.sh::setup_project` — a bare remote, a clone,
a real `aitask_claim_id.sh` counter, and the `ait` dispatcher. The real repo was
never touched: no ids were burned and no tasks were created here.

The interactive flow needs both fzf and a TTY, so each run was driven inside a
detached tmux pane on a **dedicated socket** (`tmux -L av1764`, started with
`env -u TMUX`) so the session this agent runs in was never a target. Each step
waited for its prompt text to appear in the captured pane before sending keys —
no fixed-delay sends. Sessions were killed by name; `kill-server` was never used.

Prompt sequence driven per run (empty fixture ⇒ parent/dependency/cross-repo
pickers self-skip): priority → effort → issue type → status → labels ("Done
adding labels") → task name → description → "Done with files" → "Done - create
task" → post-draft menu.

## Execution Log

### Item 1 — interactive fzf flow runs end-to-end
- Item text: Interactive `ait create` (fzf flow) runs end-to-end and creates a normally numbered task.
- Approach: TUI interaction (tmux-driven fzf + readline prompts), then artifact inspection.
- Action run: full prompt sequence, then "Finalize now (assign ID & commit)".
- Output (trimmed):
  `Finalized: aitasks/t1_interactive_smoke.md (ID: t1)` / `EXIT_RC=0`;
  `aitasks/t1_interactive_smoke.md` present, `find aitasks -name 't_*.md'` empty,
  counter `--peek` 1 → 2, commit `ait: Add task t1: interactive smoke`,
  `aitasks/new/` empty (draft consumed), frontmatter well-formed.
- Verdict: pass

### Item 2 — interactive finalize with a failing counter
- Item text: "Finalize now" with a FAILING counter aborts non-zero, the draft survives, and the message names it.
- Approach: same TUI drive; the documented counter seam (`aitask_claim_id.sh`
  replaced with the stub from `tests/test_create_id_claim_abort.sh`) installed
  *after* the draft was written and *before* "Finalize now".
- Action run: "Finalize now" → the TTY fallback prompt appeared → answered `N`.
- Output (trimmed):
  `Error: Aborted. See the counter error above.`
  `Error: Task ID claim failed (see the error above). Draft left at aitasks/new/draft_20260909_1529_draft_abort_case.md; nothing was created.`
  `EXIT_RC=1`. Draft still on disk; no `aitasks/*.md`; no `t_*.md`;
  `git rev-parse HEAD` and `git status --porcelain` byte-identical across the call.
- Note: on a TTY this path necessarily routes through the local-scan fallback
  first (`finalize_draft` calls `claim_unique_parent_id true`), so the abort is
  reached by declining it. This is the entry point row 4 of the automated file
  does **not** exercise: that row is `--batch --finalize`, where
  `allow_interactive_fallback` is false and the prompt never appears.
- Verdict: pass

### Item 3 — interactive local-scan fallback, both answers
- Item text: broken counter on a TTY prompts "Use local scan anyway? (y/N)"; y creates a normally numbered task; N aborts with no `t_*.md`, no commit, `--peek` unchanged.
- Approach: two separate fixtures. The stub was strengthened over the automated
  one: it fails `--claim` but `exec`s the **real** script for every other verb,
  so the `--peek` reading reflects genuine counter state instead of a hardcoded
  `1`. In the N fixture the counter was first advanced to 4 by three real claims,
  so "unchanged" is a non-trivial value.
- Action run (y): full drive → "Finalize now" → `y`.
  Output: `Finalized: aitasks/t1_local_scan_yes.md (ID: t1)`, `EXIT_RC=0`,
  commit `ait: Add task t1: local scan yes`, no `t_*.md`, draft consumed.
- Action run (N): full drive → "Finalize now" → `N`.
  Output: `EXIT_RC=1`; HEAD unchanged; worktree unchanged; `--peek` 4 → 4;
  `find aitasks -name 't_*.md'` empty; no `aitasks/*.md`; draft survived.
- Verdict: pass

### Item 4 — unusable TMPDIR names the real cause
- Item text: with TMPDIR pointing at a non-existent directory, interactive `ait create` shows "Cannot allocate a temp file for the ID-claim diagnostic" and NOT the pre-fix shell noise.
- Approach: TUI drive with `TMPDIR=<fixture>/nope_does_not_exist` exported in the
  pane, plus a **pre-fix negative control** — the same drive against
  `git show ec9641e79^:.aitask-scripts/aitask_create.sh`.
- Output (post-fix, trimmed):
  `Error: Cannot allocate a temp file for the ID-claim diagnostic (is TMPDIR=… writable?); refusing to claim a task ID.`
  then `Error: Task ID claim failed … Draft left at … ; nothing was created.`, `EXIT_RC=1`.
  Absent: `cat: ''`, `aitask_create.sh: line`, `unknown error`.
- Output (pre-fix control, trimmed):
  `mktemp: failed to create file via template …`
  `…/aitask_create.sh: line 1047: : No such file or directory`
  `cat: '': No such file or directory`
  `Warning: Atomic ID counter failed: unknown error`
  and, after answering `N`, `Finalized: aitasks/t_tmpdir_broken.md (ID: t)` at
  `EXIT_RC=0` with commit `ait: Add task t: tmpdir broken`.
- Why this matters: the control reproduces the whole t1755 defect through the
  **interactive** entry point — all three noise strings *and* the committed
  id-less task — so item 4's absence assertions and item 2's abort assertions
  are discriminating here, not vacuously true.
- Verdict: pass

## Cleanup

- tmux sessions `it1`, `it2`, `it3y`, `it3n`, `it4`, `it4p` on socket `av1764`
  killed by name; the socket's server left to exit on its own. The live tmux
  server was never addressed.
- Fixture trees `fx1`, `fx2`, `fx3y`, `fx3n`, `fx4`, `fx4pre` and the driver
  scripts under the session scratchpad removed.
