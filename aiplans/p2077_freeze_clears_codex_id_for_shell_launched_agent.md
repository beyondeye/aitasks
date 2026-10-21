---
Task: t2077_freeze_clears_codex_id_for_shell_launched_agent.md
Base branch: main
Output branch: main
plan_verified: []
---

# t2077 — Freeze: resolve a codex started at a shell prompt

## Context

The freeze engine learns a codex agent's conversation from the rollout its
process holds open (`agent_sessions.codex_session_for_pid`). That function
inspects **only the pane's own process** (depth 0). Framework launches exec
through, so the pane pid is codex. A codex the user types at a shell prompt is
different: the pane pid is the **shell**, so the observation returns
`MISS_NOT_CODEX`.

Code reading found two consequences:

1. **The task's case (rare).** The record already holds a codex agent string and
   a codex id. `MISS_NOT_CODEX` is in `_CODEX_DISPROVING_MISSES`, so the freeze
   clears a valid id and the restore degrades to re-pick.
2. **The common case (worse, found while planning).** A hand-started codex has no
   `AITASK_AGENT_STRING`, so the SessionStart hook records the id with a
   **blank** agent string. `agent_kind` is derived from the agent string only
   (`agent_sessions.py:786`), so it is `""` as well. On the stamped path,
   `_capture_codex_session` returns early on any record with an id that is not
   codex-kind ("hook-owned record for another agent"). `_backfill_agent_string`
   reads the shell's argv and refuses to pair a codex model with a stored id
   anyway. The record is frozen holding a codex id and a blank agent string, so
   `build_resume_argv` falls back to the `raw` default (`claudecode/sonnet5_5`)
   and runs `claude --resume <codex-uuid>`. The `CodexSessionCaptureTests`
   docstring names this as the hazard the capture rules exist to prevent.

The user chose to fix both (planning question "Scope" → "Both").

Unrelated in-flight work in the same area: **t2076** (daemon-routed codex
attribution, `Implementing`, other session) may edit `codex_session_for_pid` or
`_CODEX_DISPROVING_MISSES`. Expect a possible merge overlap, and offer a note to
t2076 at Step 8e.

## Implementation

### 1. Measure first (the task requires it; nothing is edited before this)

Use an isolated tmux server (`tmux -L t2077m`), not the user's, in a scratch
directory **outside** any aitasks project. That keeps the project's
`.codex/config.toml` hook from writing to the real session store. First check
`~/.codex/config.toml` for a user-level `[hooks]` entry and record what it does.

- Start a bash pane and type `codex -c tui.alternate_screen=never` at the prompt
  (in-process TUI). Send one trivial prompt so codex opens its rollout at the
  first turn.
- Record:
  - the pane pid's argv0 (`-bash` or `bash`?);
  - `/proc/<shell>/task/*/children`: is codex the shell's **direct** child, and
    is the mise wrapper exec'd away (argv0 = the real codex binary, as with the
    framework launches)?
  - the codex child's fds: does it hold `rollout-*.jsonl`?
  - **foreground evidence** from `/proc/<pid>/stat` (pgrp = field 5,
    tty_nr = 7, tpgid = 8) for the shell and codex: is codex its own job leader
    (`pgrp == pid`, `!= shell pgrp`), does `tpgid` equal codex's pgrp, and do
    both processes report the same `tty_nr`/`tpgid`?
  - suspend codex (Ctrl-Z): `tpgid` should flip to the shell's pgrp while codex
    (state `T`) still holds its rollout. Then run `sleep 300` in the foreground
    (a stand-in for a foreground claude with the same job-control mechanics):
    `tpgid` should equal sleep's pgrp. Kill both afterwards.
  - `agent_sessions.codex_session_for_pid(<shell pid>)` before the fix
    (expected `("", "", "not_codex")`).
- **If the shape differs** (codex not a direct child, the wrapper not exec'd
  away, no rollout held), stop and revise the plan with the user. Do not code
  against an unconfirmed shape.
- Tear down: kill the isolated tmux server. The one rollout this leaves in
  `~/.codex/sessions` is reported, not deleted.
- The measured facts go verbatim into the plan's Final Implementation Notes,
  following the closure-evidence rule.

### 2. `agent_sessions.py`: one-level descent through a pane shell

Add next to `_codex_cmdline_argv`:

- `_PANE_SHELLS = frozenset(("bash", "zsh", "fish", "sh", "dash", "ksh", "mksh",
  "tcsh", "csh", "nu"))`, matched on argv0's basename with a login shell's
  leading `-` stripped.
- `_is_codex_argv(argv) -> bool`: `bool(argv) and basename(argv[0]) == "codex"`.
  Reuse it at the three existing argv0 checks in `codex_session_for_pid` and
  `codex_process_model`.
- `_direct_children(pid, proc_root) -> list[int] | None`: union of
  `/proc/<pid>/task/*/children`. Returns **None when it cannot be read** (no
  `task/` dir, a missing `children` file, OSError), which keeps the existing
  "could not look ≠ looked" distinction.
- `_proc_job(pid, proc_root) -> tuple[int, int, int] | None`: returns
  `(pgrp, tty_nr, tpgid)` from `/proc/<pid>/stat`, splitting after the
  **last** `)` because `comm` may contain spaces and parens. Returns None when
  unreadable or malformed.
- `_codex_child_of_shell(pid, argv, proc_root) -> tuple[int, list[str], str]`
  returns `(child_pid, child_argv, miss)` for a pane process that is not codex
  itself. **Only the terminal's foreground job counts.** A shell's direct
  children include suspended (Ctrl-Z) and background jobs, and a suspended codex
  still holds its rollout open, so being a child proves nothing about which
  agent the pane is running. In order:
  - argv0 not a known shell → `MISS_NOT_CODEX`. This keeps the claude Bash-tool
    exclusion: a codex child of a non-shell process never counts.
  - the shell's `_proc_job` unreadable, or `tpgid <= 0` (no controlling
    terminal) → `MISS_NO_PROCESS`.
  - children list unreadable → `MISS_NO_PROCESS`.
  - **any listed child whose cmdline or stat cannot be read →
    `MISS_NO_PROCESS`.** An unread child could be the foreground codex, so
    absence and uniqueness are both unproven. Unknown never becomes "not codex",
    which is the answer that clears a stored id. (A child whose cmdline reads as
    empty, e.g. a zombie, was looked at; it is not codex.)
  - foreground children = children whose `pgrp == tpgid`. Background and
    suspended jobs, codex included, are **not candidates**: they are not the
    agent the pane is running.
  - exactly one foreground child whose argv is codex → candidate. Zero (the
    shell itself is foreground, or another program such as claude is) or 2+ →
    `MISS_NOT_CODEX`, which is today's answer for a non-codex pane. It disproves
    only a codex-kind stored id; a blank-kind record is left alone (Step 3).
  - **conflicting foreground evidence → `MISS_NO_PROCESS`** (unknown, never a
    disproof): the candidate's `tty_nr` or `tpgid` differs from the shell's,
    or the candidate shares the shell's pgrp. That last case means there is no
    job-control evidence that it is a job of its own. Without job control, a
    `codex &` sits in the shell's group too, so foreground cannot be told apart.
  - otherwise → the candidate's pid, **the argv already read**, and its
    `(pgrp, tty_nr)` for the re-check below.
  - Grandchildren are never inspected (depth 1 only).

**One observation, one process (paired read).** Add a public
`codex_observe_pid(pid, *, proc_root="/proc") -> tuple[str, str, str, str]`
that returns `(session_id, transcript_path, cli_id, miss)`. It resolves the codex
process **once**, and the session and the model come from that same process:

1. Read the pane pid's `fd` dir (OSError → `MISS_NO_PROCESS`), then its cmdline
   (None → `MISS_NO_PROCESS`). This is the current order.
2. If that argv is not codex, call `_codex_child_of_shell`. On a miss, return it.
   Otherwise **bind** `agent_pid = child` and `argv = child_argv`, and read
   `entries` from **that pid's** `fd` dir. OSError means the child exited →
   `MISS_NO_PROCESS`; never pick a replacement child.
3. Collect rollout candidates from `entries`. This is the current loop: it runs
   `os.readlink` and `_codex_rollout_identity` on each entry, and an entry
   whose link fails is skipped, as today. **Compute the verdict, but do not
   return it yet:** success, `MISS_NO_MATCH` or `MISS_AMBIGUOUS`.
4. **Final validation, after all fd evidence is collected and before returning
   success or an fd-based disproof (`MISS_NO_MATCH` / `MISS_AMBIGUOUS`).**
   Listing `fd/` reads only names. The link targets and rollout metadata are
   read in step 3, so this is the only point where the process is known to
   have been itself for the whole read. Re-read `agent_pid`'s cmdline. If it is
   unreadable or differs from the bound `argv` → `MISS_NO_PROCESS`. This covers
   **both routes, depth 0 included**: a process that exits mid-loop fails every
   `readlink`, its candidate set is empty, and without this check that
   unavailability would become `MISS_NO_MATCH` and clear a valid stored id.
   That gap exists at depth 0 today. On the **child route** also re-read both
   processes' `_proc_job`. If either is unreadable, or the candidate is no
   longer the foreground job (`pgrp != tpgid`, or its pgrp/tty changed) →
   `MISS_NO_PROCESS`. So a suspend or exit anywhere during the observation
   yields "unknown", never a session and never a disproof.
5. On success, `cli_id = _argv_model(argv)`, taken from the **same bound argv**.

`codex_session_for_pid` becomes a thin wrapper that drops `cli_id`, so its
3-tuple contract, `codex_resume_evidence`, and the restore tests keep working.
Rewrite the "Depth 0 only" comment and the docstring paragraph to state the rule:
depth 0, plus exactly one level through a known shell, read as one process.

In `agent_freeze._observe_codex_session`, replace the two calls
(`codex_session_for_pid` + `codex_process_model`) with one call to
`codex_observe_pid`, and use its `cli_id`. Then `codex_process_model` is no
longer used by the freeze. Leave it unchanged at depth 0, because it is public
and has its own tests. Leave `process_model_evidence` unchanged too.

`codex_resume_evidence` needs no change. Restore launches exec through, so its
pid is codex at depth 0.

Docstring touch-up: in `agent_restore.resume_blocker`, change "the pane was not
running codex directly" to name the shell exception.

### 3. `agent_freeze.py`: a proven codex may settle a blank-kind hook id

In `_capture_codex_session`:

- Narrow the early return to records whose id is owned by **another known
  agent**: `stored_id and stored_kind and stored_kind != "codex"`. A blank-kind
  record holding an id now gets observed.
- Disproving misses on a blank-kind record: **unchanged** (return). A
  `MISS_NOT_CODEX` there is typically a claude pane whose hook id is valid, and
  `test_a_codex_model_is_never_paired_with_an_unproven_session` pins the
  `NO_MATCH` case.
- A positive observation (`session_id` and a nameable `agent_string`) records
  `--session-id/--transcript/--agent-string` as it does today. A blank-kind
  record is not codex, so the "already agrees" check fails and the write happens.
  This is the fix for the common case when argv names a mapped model.
- The "verified session this code cannot record safely" branch is extended to
  blank-kind records. The guard becomes
  `stored_id and (stored_is_codex or not stored_kind)`, and the condition also
  fires when `not stored_kind`. A live codex proves the stored id is codex's,
  but with no model to name, keeping it would restore as
  `claude --resume <codex-uuid>`, so the freeze **clears** it (re-pick). New
  action text: `cleared codex session id the record cannot name a model for`.
- Update the function docstring's outcome list to match.

In `_resolve_record` (unstamped fallback), apply the same rule:

- When `observed_id and not observed_agent`, the process is proven codex but
  unnameable, so set `session_id = ""`. The pane stamp must not travel into the
  record, because it would restore under the `raw` default.
- After the upsert, also run `_capture_codex_session(..., observation=...)` in
  that case (today it runs only for disproving misses). That way a selected
  record still holding an id is cleared by the same rule. Reuse the observation;
  do not re-probe.

### 4. Tests

`tests/test_agent_sessions_transcripts.py`: `write_proc` gains
`children=()` (writes `task/<pid>/children`; `children=None` writes no `task/`
dir) and `job=(pgrp, tty_nr, tpgid)`, which writes a `stat` line whose `comm`
contains a space and a `)` to exercise the last-paren split (`job=None` writes
no `stat`). New class `CodexShellPaneTests`, where children are foreground
unless a test says otherwise:

- a `-bash` pane with one **foreground** codex child holding a rollout resolves
  through the shell pid. This is the **red proof**; it returns `not_codex`
  before the fix.
- a shell with a foreground codex child plus a non-codex child in the same job
  (`codex | tee`) still resolves;
- a shell with two foreground codex children → `MISS_NOT_CODEX`;
- **suspended codex + foreground claude:** codex (own pgrp, holding a rollout)
  is not foreground, and claude's pgrp == tpgid → `MISS_NOT_CODEX`, never
  codex's session. The pre-revision design returns the session, which the
  assertion message states.
- suspended codex with the shell itself foreground (tpgid == shell pgrp) →
  `MISS_NOT_CODEX`;
- a foreground codex plus a background codex holding another rollout → the
  **foreground** one's session and model;
- conflicting foreground evidence → `MISS_NO_PROCESS` for each of: the
  candidate's tpgid ≠ the shell's; tty_nr differs; the candidate shares the
  shell's pgrp (no job control); the shell's tpgid is ≤ 0; the shell's or a
  child's `stat` is unreadable;
- a suspend during the observation (the `_codex_cmdline_argv` wrapper flips the
  fixture's tpgid to the shell's pgrp after the candidate's argv is read) →
  `MISS_NO_PROCESS`;
- **mutation during the evidence loop** (the interval after `fd/` is listed).
  Each case is deterministic: patch `agent_sessions.os.readlink` or
  `agent_sessions._codex_rollout_identity` with a wrapper that delegates and
  mutates the fixture on its first call:
  - the foreground child is **suspended during rollout inspection**
    (`_codex_rollout_identity` flips tpgid) → `MISS_NO_PROCESS`, not the
    session;
  - the foreground child is **suspended during readlink** → `MISS_NO_PROCESS`;
  - the foreground child is **removed during readlink** (its proc dir is
    deleted, so the remaining links fail and the candidate set is empty) →
    `MISS_NO_PROCESS`, **not** `MISS_NO_MATCH`;
  - depth 0: a codex pane process **removed during readlink** →
    `MISS_NO_PROCESS`, not `MISS_NO_MATCH`. This pins the pre-existing gap the
    final validation closes;
  - control: the same wrappers delegating **without** mutating → the session
    resolves. This proves each `MISS_NO_PROCESS` comes from the mutation.
  - Assertion messages state that each mutation case is red against a design
    that validates before the loop.
- a shell with no children → `MISS_NOT_CODEX`;
- a non-shell pane process (argv0 `claude`) whose direct child is a
  rollout-holding codex → `MISS_NOT_CODEX` (the claude Bash-tool exclusion);
- shell → claude → codex (grandchild) → `MISS_NOT_CODEX` (depth 1 only);
- a shell whose children list is unreadable → `MISS_NO_PROCESS`;
- a shell whose codex child's fd dir is unreadable → `MISS_NO_PROCESS`;
- **unreadable child cmdline** (shell and children list readable):
  - the only listed child has no readable cmdline → `MISS_NO_PROCESS`, not
    `not_codex`;
  - one readable codex child holding a rollout plus one unreadable child →
    `MISS_NO_PROCESS` (uniqueness unproven), never the codex child's session;
  - control: the same layout with the second child readable as `sleep` →
    resolves. This proves the unreadable child is what flips it.
- `codex_observe_pid(<shell>)` returns the child's `-m` as `cli_id`, along with
  its session.
- **child change mid-observation (deterministic):** patch
  `agent_sessions._codex_cmdline_argv` with a wrapper. The first time it reads
  child A's argv, it rewrites the fixture: A's `/proc` dir is removed, and
  child B (with a different `-m` and a different rollout) is listed. Expect
  `MISS_NO_PROCESS`, and neither B's session nor B's model in the result.
  - Second variant: A's **pid is reused** by a different process (same pid dir,
    new argv and rollout). The identity re-check gives `MISS_NO_PROCESS`.
  - Both variants are red against a two-call implementation, which the
    assertion message states.

`tests/test_agent_freeze.py` harness: `_install_codex_observers` additionally
patches `agent_sessions.codex_observe_pid` with a stub composed from the existing
`self.codex_session` + `self.codex_model[1]`. The stub records probe pids the
same way, so `observe_codex` / `observe_miss` and the probe-pid assertions keep
working. The `_sequential` stub (around line 1028) moves to `codex_observe_pid`.
The `codex_session_for_pid` / `codex_process_model` patches stay, so nothing
reads the real `/proc`.

`tests/test_agent_freeze.py`, freeze consequence against a fake `/proc` (the real
`codex_observe_pid` bound to a temp `proc_root`, so the freeze runs the real
descent):

- a codex-kind record with a stored id; the pane pid is `bash` with one listed
  child whose cmdline is unreadable → freeze succeeds, the id is **kept**, and
  no `--clear-session-id` is sent;
- control: the same record with that child readable as `sleep` → the id is
  cleared (`MISS_NOT_CODEX` disproves). This proves the kept id comes from the
  unknown answer;
- **disappearance during the evidence loop:** a codex-kind record holding the
  stored id; the pane is `bash` with a foreground codex child holding that
  rollout, and an `os.readlink` wrapper deletes the child's proc dir on its
  first call. The freeze succeeds, the stored id **and transcript are
  preserved**, and no `--clear-session-id` is sent. Control: the same freeze
  without the deletion records the session normally;
- a blank-kind hook record; the pane pid is `bash` with a **foreground** codex
  child holding the stored id under `-m gpt-5.6-terra` (mapped) → the record
  keeps the id and gains `codex/gpt5_6_terra`. This is the end-to-end red proof
  for the common case.
- **suspended codex + foreground claude + a blank-kind Claude hook record**
  (`sess-claude`, agent_string ""). The suspended codex holds a different
  rollout under a mapped `-m`. After the freeze the record still holds
  `sess-claude` with a blank agent string; no upsert carries the codex session,
  transcript or `codex/…` agent string; nothing is cleared. This is the
  blocking regression for the overwrite this revision closes.

`tests/test_agent_freeze.py`, `CodexSessionCaptureTests` (stubbed observers):

- blank-kind record holding the hook id, and the live codex holds the same id
  with a mapped model → the id is kept and the agent string becomes
  `codex/gpt5_6_terra`. Red before the fix.
- the same, but argv names no model and nothing is remembered → the id is
  cleared. Red before the fix.
- blank-kind record and the live codex holds a **different** id, unnameable →
  cleared;
- blank-kind record and `MISS_NOT_CODEX` → the id is kept with no write. The
  existing claude-pane guard is preserved.
- unstamped pane with a stamp id, a live codex holding it, unnameable → the
  fallback upsert sends no `--session-id`, and a selected record's id is cleared.

The existing suites must stay green, in particular the
`test_a_codex_model_is_never_paired_with_an_unproven_session` /
`test_a_stamped_blank_record_is_filled_with_the_model_only` family and the
claude-kind "not ours to inspect" test (around `test_agent_freeze.py:905`).

### 5. Docs

`grep` `website/content/docs/workflows/freeze-and-restore-agents.md` and
`concepts/framework-session.md` for statements about which codex agents resume.
Add one current-state sentence: a codex started at a shell prompt in-process is
resolved through the shell, and is resumable only when its launch names a model
the framework knows; otherwise it restores by re-pick. Run
`python3 check_links.py --build` (in `website/`) if a page changes.

### Step 9 reference

Current-branch profile: commit, then Step 9 archival per the shared workflow.

## Verification

- `python3 -m pytest tests/test_agent_sessions_transcripts.py tests/test_agent_freeze.py -q`
  (red proofs first: run the new tests against the pre-change code, or flip a
  guard to confirm each one fails).
- `bash tests/run_all_python_tests.sh` and read only the last line for the
  verdict.
- `bash tests/test_session_hook.sh` (no change expected; it guards hook
  semantics).
- Live re-check: repeat Step 1's isolated session and confirm
  `codex_observe_pid(<shell pid>)` returns the child's session, transcript and
  `-m` value from one call.

## Risk

### Code-health risk: low
- Narrowing `_capture_codex_session`'s early return means blank-kind records are now observed. The freeze acts on them only when the live process is a proven codex holding a session; disproving misses still leave them untouched · severity: low · → mitigation: none (covered by the new tests)
- On a kernel without `/proc/<pid>/task/*/children`, a bare-shell pane now answers `MISS_NO_PROCESS` instead of `MISS_NOT_CODEX`, so a stale codex id there is kept rather than cleared. This is the module's fail-safe direction · severity: low · → mitigation: none
- In-flight t2076 may edit the same functions, so a merge overlap is possible · severity: low · → mitigation: none (Step 8e note offer)
- A partial read of the child set or of the child could turn "unknown" into a disproof, or pair one process's session with another's model. Addressed in the design by the unreadable-child → `MISS_NO_PROCESS` rule, the single-resolution `codex_observe_pid`, and the identity re-check, each with a red test · severity: low (residual) · → mitigation: none
- A suspended or background codex could be taken for the pane's active agent and overwrite a foreground agent's blank-kind hook record. Addressed by the foreground-job rule (`pgrp == tpgid`, a job of its own, consistent terminal), its re-check after the fd read, and the suspended-codex + foreground-claude tests at both levels · severity: low (residual) · → mitigation: none
- The final validation also runs on the depth-0 route, a small behaviour change for framework launches: a codex pane process that exits mid-read now answers `MISS_NO_PROCESS` (keep the id) instead of `MISS_NO_MATCH` (clear it). This is the module's fail-safe direction, and a depth-0 test plus the unchanged existing suite pin it · severity: low · → mitigation: none
- Foreground detection depends on job control. A shell without it (codex sharing the shell's pgrp) answers `MISS_NO_PROCESS`, so such panes keep today's re-pick behaviour rather than gaining resume · severity: low · → mitigation: none

### Goal-achievement risk: medium
- The process shape of a hand-typed codex (direct child of the shell, wrapper exec'd away, rollout held by the child) is inferred from framework launches, not measured. Step 1 measures it before any code is written and stops on a mismatch · severity: low (residual, gated by Step 1) · → mitigation: none
- A hand-started codex whose argv names no model (the usual way to type it) is cleared to re-pick, not made resumable. The `claude --resume <codex-uuid>` hazard is gone, but resumability for that case needs the model from codex's own config · severity: medium · → mitigation: codex_model_from_config

### Planned mitigations
- timing: after | name: codex_model_from_config | type: enhancement | priority: low | effort: medium | inline_risk: medium | added_complexity: medium | addresses: goal-achievement — hand-started codex with no -m is cleared to re-pick, not resumable | desc: When a live codex's argv names no model, resolve it from codex's own config ($CODEX_HOME/config.toml model, -c model= / --profile in argv) so the freeze can record codex/<model> and a hand-started codex resumes instead of re-picking

## Implementation Progress

- [x] Step 1 — live measurement (isolated `tmux -L t2077m`, scratch dir outside any aitasks project, codex-cli 0.163.0). Shape confirmed; see Final Implementation Notes.
- [x] Step 2 — `agent_sessions.py`: `_is_codex_argv`, `_PANE_SHELLS`, `_direct_children`, `_proc_job`, `_codex_child_of_shell`, `_observed_process_unchanged`, public `codex_observe_pid`; `codex_session_for_pid` is now a wrapper.
- [x] Step 3 — `agent_freeze.py`: one paired observation; blank-kind hook ids settled only by a positive observation; unstamped fallback drops an unlabelled stamp and re-decides against the selected record (`_with_remembered_label`).
- [x] Step 4 — tests (`CodexShellPaneTests`, `UnlabelledHookRecordTests`, `ShellPaneFreezeTests`) + mutant red proofs.
- [x] Step 5 — docs (`freeze-and-restore-agents.md`), `check_links.py --build` SWEEP: PASSED.

## Post-Review Changes

### Change Request 1 (2026-10-21 14:38)
- **Requested by user:** (1) `_codex_child_of_shell` issued `MISS_NOT_CODEX` (a disproof) from an unvalidated snapshot: a job moved to the foreground between the shell read and the child read, a children list that skipped the foreground child, or a pid listed twice each cleared a valid id. Revalidate before any disproof, treat an unobserved foreground job or inconsistent observation as `MISS_NO_PROCESS`, dedupe the union, add deterministic coverage. (2) Docs/docstring overstated the `-m` requirement: an existing codex label on the record also names the model.
- **Changes made:** `_direct_children` dedupes (order-preserving). `_codex_child_of_shell`: any child on the shell's terminal reporting a different tpgid -> `MISS_NO_PROCESS`; a negative result (0 or 2+ foreground codex) is a disproof only if the foreground group was actually seen (shell's own or a listed child's) AND the shell's job and children list re-read identically, else `MISS_NO_PROCESS`. Docs paragraph and `resume_blocker` docstring now say the model comes from `-m` or an existing codex label on the record. Tests: 6 resolver tests (mid-look `fg`, stable-prompt control, unlisted foreground job, duplicate pid, non-candidate child with another foreground, children changing mid-look) + 4 freeze tests (mid-look keeps id, stable-prompt control clears, unlisted foreground codex keeps id, duplicate pid keeps and refreshes). Mutants M8 (no dedup), M9 (no negative revalidation), M10 (no per-child tpgid check), M11 (no unseen-foreground check) and M9+M10 each turn their tests red; the mid-look race is caught by two independent layers (per-child tpgid and post-loop re-read), so only the combined mutant reds it.
- **Files affected:** .aitask-scripts/lib/agent_sessions.py, .aitask-scripts/lib/agent_restore.py, tests/test_agent_sessions_transcripts.py, tests/test_agent_freeze.py, website/content/docs/workflows/freeze-and-restore-agents.md

### Change Request 2 (2026-10-21 15:11)
- **Requested by user:** the negative-result revalidation re-read the shell job and child list but never the child argv that established "no foreground codex". A foreground launcher (`env … codex resume …`) that execs into codex after its argv was read keeps pid, pgrp, tty, tpgid and list place, so both rechecks passed, `MISS_NOT_CODEX` was returned, and the freeze cleared the id of the codex now running.
- **Changes made:** `_codex_child_of_shell` retains every child's `(argv, job)` from the first pass and, before any disproof, re-reads each; a change or an unreadable read -> `MISS_NO_PROCESS`. Tests: resolver (launcher execs mid-look -> `no_process`; stable launcher -> `not_codex`; already exec'd -> resolves) and freeze (mid-look exec keeps the id with no clear; stable launcher clears; already exec'd keeps and refreshes). Mutant M12 (no per-child recheck) turns both mid-look tests red.
- **Files affected:** .aitask-scripts/lib/agent_sessions.py, tests/test_agent_sessions_transcripts.py, tests/test_agent_freeze.py

## Final Implementation Notes
- **Actual work done:** `agent_sessions.codex_observe_pid` (new, public) resolves the codex behind a pane ONCE and returns `(session_id, transcript, cli_id, miss)` from that one process: the pane process when it is codex, else -- through a known shell (`_PANE_SHELLS`, login `-` stripped) -- its single FOREGROUND codex child (`_codex_child_of_shell`, foreground = child pgrp == terminal tpgid via `_proc_job`, children via `_direct_children`, deduped). After every fd target and rollout header is read, `_observed_process_unchanged` re-reads argv (both routes, depth 0 included) and, on the shell route, the foreground state; any change -> `MISS_NO_PROCESS`. `codex_session_for_pid` is now a 3-tuple wrapper (restore path unchanged). `agent_freeze._observe_codex_session` uses the single paired call. `_capture_codex_session` now observes records holding an id under NO agent kind (hook ran outside the wrapper): a positive observation records `codex/<model>`, or clears the id when no model can be named; misses leave such a record alone. The unstamped fallback drops an unlabelled live session's pane stamp and re-decides against the selected record via `_with_remembered_label` (also used by `_observe_codex_session`). Docs: `freeze-and-restore-agents.md` paragraph; `resume_blocker` docstring.
- **Measured live (Step 1; isolated `tmux -L t2077m`, scratch dir outside any aitasks project, codex-cli 0.163.0, user `~/.codex/config.toml` has no `[hooks]`):**
  - pane pid 1787755 argv `-bash`; stat `pgrp=1787755 sid=1787755 tty=34860 tpgid=1788558` with codex in the foreground.
  - `/proc/1787755/task/*/children` = `1788558`; its argv `/home/ddt/.local/share/mise/installs/codex/latest/bin/codex -c tui.alternate_screen=never` (the mise wrapper exec'd away); stat `ppid=1787755 pgrp=1788558 tty=34860 tpgid=1788558`; after one turn it held `rollout-2026-10-21T12-52-13-01a15de0-27f4-70c2-bb29-5c0d27c006e4.jsonl`.
  - pre-fix: `codex_session_for_pid(1787755)` = `('', '', 'not_codex')`; `codex_session_for_pid(1788558)` = the `01a15de0…` session.
  - Ctrl-Z: shell `tpgid=1787755`; codex `state=T`, still holding 1 rollout. `sleep 300` in the foreground: `tpgid=1795032` (sleep's pgrp).
  - post-fix live re-check: suspended codex + foreground sleep -> `('', '', '', 'not_codex')`; after `fg` -> `('01a15de0-27f4-70c2-bb29-5c0d27c006e4', '…/rollout-2026-10-21T12-52-13-01a15de0-….jsonl', '', '')` (no `-m` on that launch, so `cli_id` is empty).
  - The measurement's rollout remains in `~/.codex/sessions/2026/10/21/` (not deleted).
- **Deviations from plan:** (a) the unstamped fallback also needed the selected record's codex label (`_with_remembered_label`), otherwise an observation made with no record in hand would clear a labelled record; (b) three post-review change requests hardened every disproof path (see Post-Review Changes): negative results now require a consistent, complete, re-read snapshot.
- **Issues encountered:** the mutant runner first copied only `lib/` (import error on `monitor`); fixed by copying the whole `.aitask-scripts` tree. `LayoutFixtureTests` (4) fail in every scratch copy because `tests/data` is not copied -- runner artefact, not mutant signal. A chmod-based unreadable-fd fixture fought the base teardown; replaced by an fd path that is a plain file.
- **Key decisions:** "could not look" (`MISS_NO_PROCESS`) whenever any piece of evidence is unread or moved; `MISS_NOT_CODEX` only from a consistent snapshot. `codex_process_model` left unchanged (public, own tests; the freeze no longer calls it). Hand-started codex with no `-m` and no codex label is cleared to re-pick (mitigation `codex_model_from_config`, an "after" task, will recover the model from codex's config).
- **Verification:** `tests/test_agent_sessions_transcripts.py` + `tests/test_agent_freeze.py` + `tests/test_agent_restore.py` 368 passed; `bash tests/run_all_python_tests.sh` -> `PYTHON SUITE: PASSED (runner=pytest, exit=0)`; `bash tests/test_session_hook.sh` 167/167; `website/check_links.py --build` SWEEP: PASSED. Mutants in isolated copies (no stash): M1b no foreground filter anywhere, M2 validation moved before the loop, M2b no final validation, M3 unreadable child treated as not codex, M4 old capture early return, M5 no shell descent, M7 unstamped stamp travels, M8 no dedup, M9 no negative revalidation, M10 no per-child tpgid check, M11 no unseen-foreground check, M9+M10, M12 no per-child evidence recheck -- each turned its targeted tests red.
- **Upstream defects identified:**
  - `.aitask-scripts/aitask_session_hook.sh:254 — a SessionStart hook run outside the wrapper records the id with a blank agent string (so no agent kind), and a restore then resolves the binary from the project's raw default; a hand-started agent of a kind other than the raw default (e.g. claude in a project whose raw default is codex) would restore with the wrong CLI. Found by code reading; t2077 fixes only the codex side, at freeze time.`
