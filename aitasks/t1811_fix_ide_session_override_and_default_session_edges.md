---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-15 09:14
updated_at: 2026-09-16 10:20
---

## Origin

Spawned from t1800 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_ide.sh:52 — echo "$SESSION_OVERRIDE" swallows an option-like --session value (e.g. --session -n), so ait ide resolves an empty session name; needs printf plus a test seam (the script runs the IDE at top level)`
- `.aitask-scripts/aitask_setup.sh:4140 — setup_tmux_default_session's "already configured?" probe (grep | sed) treats a null, comment-only or quoted-empty default_session (# note, "", null, ~) as configured, prints e.g. "already configured: # note" and skips the prompt`
- `.aitask-scripts/lib/agent_launch_utils.py:747 / .aitask-scripts/lib/tmux_bootstrap.sh:68 — the line parsers cannot read YAML-only default_session shapes that load_tmux_defaults accepts: a flow mapping resolves to aitasks, a block scalar (>- or |) to its literal indicator (ait ide would name its session '>-'), a typed scalar (yes, 0123) to its source text instead of True/83`

## Diagnostic context

t1800 (code commit `d146a440c`) made the four tmux session-name resolvers agree
on blank, null and commented `tmux.default_session`: `load_tmux_defaults`, both
monitors' `main()` (now reading through it), `_read_default_session` and the
bash `_tmux_bootstrap_resolve_session`. Its contract is pinned by
`tests/test_tmux_default_session_resolvers.py`. Three adjacent defects were left
out of that contract on purpose:

- **`ait ide --session <name>`.** `aitask_ide.sh:16` accepts the value
  (`SESSION_OVERRIDE="${2:-}"`), and `:52` prints it with `echo`.
  - Measured: bash's builtin `echo` prints nothing for `-n`, `-e`, `-E` and
    `-neE`; `printf '%s\n'` preserves all four. t1800 applied the `printf` fix
    to `_tmux_bootstrap_resolve_session` only.
  - The override never reads `tmux.default_session`, and the script runs the
    IDE at top level, so there is no test seam. That is why it was split out.
- **The setup probe** never resolves a session name; it only decides whether
  to offer an optional prompt (default `aitasks`). After t1800 every resolver
  reads the skipped-prompt blank value as `aitasks`, so no launch path diverges.
  Only the message and the skipped prompt are wrong.
- **YAML-only shapes.** `LegacyYamlFormsPreservedTests` pins the YAML-backed
  side (`flowsess`, `blocksess`, `blocksess\n`, `True`, `83`), and deliberately
  does **not** assert the line parsers on those rows, so this fix will not be
  mistaken for a regression. A companion test requires every legacy row to be
  a shape the line parsers cannot read.

## Suggested fix

- **ide override:** `printf '%s\n' "$SESSION_OVERRIDE"`, plus a test seam. For
  example, move `resolve_session` into `lib/tmux_bootstrap.sh`, or guard the
  top-level run. Then add a committed test for `--session -n`.
- **setup probe:** decide "configured" with the same scalar rule the resolvers
  use (e.g. a raw-value helper in `tmux_bootstrap.sh` that prints empty for
  blank/null/comment-only) instead of `grep | sed`.
- **YAML-only shapes:** either support them in both line parsers or warn and
  fall back explicitly. Once decided, add line-parser assertions to
  `LegacyYamlFormsPreservedTests`, keeping the parity matrix's oracle
  discipline.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1705** id=2026-09-16T07:04:11Z.7d9856f639635c77b2e91ad9 from=t1705 at=2026-09-16T07:04:11Z base=617c00f9a541522042dae0db71d12465c9240ee6 base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | **t1800's code is not in this clone, so this task's Diagnostic context does not
> | currently hold.** Surfaced while refreshing the t1705 implementation trail
> | (`art:trail-frozen-codeagents`), where t1800 and this task joined as new topic
> | members.
> | 
> | Tree-relative to the base commit this note records (local `main`):
> | 
> | - Commit `d146a440c`, cited in this task's Diagnostic context as t1800's code
> |   commit, resolves in **no ref** of this clone — `git rev-parse d146a440c`
> |   reports "unknown revision", and `git log --all --grep t1800` shows only
> |   task-data commits.
> | - `tests/test_tmux_default_session_resolvers.py`, which this task names as the
> |   test pinning t1800's contract, **does not exist**.
> | - `LegacyYamlFormsPreservedTests`, which this task says pins the YAML-backed
> |   side (`flowsess`, `blocksess`, `True`, `83`), **does not exist** anywhere
> |   under `tests/` or `.aitask-scripts/` (grep, no hits).
> | - `.aitask-scripts/lib/agent_launch_utils.py:1913-1914` still reads
> |   `defaults["default_session"] = str(tmux["default_session"])` — the exact
> |   unfixed shape t1800 set out to change.
> | - `.aitask-scripts/aitask_ide.sh:52` still reads `echo "$SESSION_OVERRIDE"`.
> |   That one is expected: it is this task's own first defect, untouched by t1800
> |   by design.
> | 
> | Moment-relative, and therefore hedged — true as of writing, with no commit to
> | date it:
> | 
> | - t1800 is **archived** on the task-data branch
> |   (`aitasks/archived/t1800_fix_load_tmux_defaults_blank_default_session.md`,
> |   archived by data commit `d2a7ce7a6`, pulled 2026-09-16).
> | - Local `main` is level with `origin/main` and its tree is clean, so the code
> |   side of t1800 has not reached this remote's `main` while its data side has
> |   archived. That asymmetry suggests the implementation happened in another
> |   clone or worktree and was never pushed.
> | 
> | Advisory, for whoever plans this task:
> | 
> | 1. **Verify t1800's commit is present before planning.** The three defects here
> |    are framed as "deliberately split out of t1800's contract"; if that contract
> |    is absent, the split has no baseline and the framing needs re-establishing
> |    rather than assuming.
> | 2. The measured claims in the Diagnostic context (bash `echo` dropping `-n`,
> |    the setup probe's `grep | sed`, the block-scalar naming a session `>-`) were
> |    measured against a tree that included t1800. Only the `echo` and
> |    `aitask_ide.sh` observations were re-confirmed here; the setup-probe and
> |    line-parser line numbers were not re-checked and may have moved.
> | 3. The Suggested fix asks for line-parser assertions to be added to
> |    `LegacyYamlFormsPreservedTests`. That class does not exist in this tree, so
> |    either t1800's test file arrives first or this task creates it.
> | 4. If t1800's work is later pushed or re-done, expect conflicts: this task
> |    targets `aitask_ide.sh`, `aitask_setup.sh`, `lib/agent_launch_utils.py` and
> |    `lib/tmux_bootstrap.sh` — the same four files t1800 changed.
> | 
> | This is a claim about a tree that may have moved since. Re-run the four checks
> | above before acting on any of it.

> **✉ note:t1705** id=2026-09-16T07:12:44Z.797ed5e7aac1d4d5aad47078 from=t1705 at=2026-09-16T07:12:44Z base=002c74f45bcf59f4e67b2c0a4c4e74da92f7ea4a base_branch=main dirty=no host=Darios-Mac-mini.local
>
> | **Correction — this note supersedes note
> | `2026-09-16T07:04:11Z.7d9856f639635c77b2e91ad9` above, whose central claim was
> | wrong. Disregard that note's conclusion; this task's Diagnostic context holds
> | as written.**
> | 
> | That earlier note reported that t1800's code was absent from the repository and
> | that this task's premise therefore had no baseline. It was wrong. The commit it
> | said existed in no ref, `d146a440c`, was on `origin/main` the whole time; this
> | clone had not fetched `origin/main` (only `aitask-data`, `aitask-ids` and
> | `aitask-locks` had come down), so every check ran against a tree that legitimately
> | lacked it. A `git fetch origin` before concluding would have caught it.
> | 
> | Re-verified against `main` at `002c74f45`, after fast-forwarding 21 commits:
> | 
> | - `d146a440c bug: Make every tmux session-name resolver agree on blank
> |   default_session (t1800)` — **present**.
> | - `tests/test_tmux_default_session_resolvers.py` — **exists** (14850 bytes).
> | - `LegacyYamlFormsPreservedTests` — **exists**, in that same test file. The
> |   Suggested fix's request to add line-parser assertions to it is actionable as
> |   written.
> | - `.aitask-scripts/lib/agent_launch_utils.py` now carries
> |   `_normalize_default_session()` at :133, called from `load_tmux_defaults` at
> |   :1958 and from `_read_default_session` at :787. The unfixed
> |   `str(tmux["default_session"])` this task's context described is gone.
> | 
> | So: t1800's four-resolver contract IS landed and pinned, the "three defects
> | deliberately split out" framing has its baseline, and the earlier note's claim
> | of a data-side archival without a code-side landing does **not** describe
> | reality. Nothing in that asymmetry needs chasing.
> | 
> | The one claim that survives from the earlier note, and it is this task's own
> | first defect rather than a problem with it: `.aitask-scripts/aitask_ide.sh:52`
> | still reads `echo "$SESSION_OVERRIDE"`, untouched by t1800 by design.
> | 
> | Current line numbers on `002c74f45`, since this task's context cites pre-t1800
> | positions for two of the three sites:
> | 
> | - ide override: `aitask_ide.sh:52` — unchanged from the cited `:52`.
> | - setup probe: `setup_tmux_default_session()` now begins at
> |   `aitask_setup.sh:4129` (the context cites `:4140` for the `grep | sed`
> |   probe inside it).
> | - line parsers: `agent_launch_utils.py::_read_default_session` is now at `:747`
> |   with its `default_session:` branch at `:786-788`, and
> |   `tmux_bootstrap.sh::_tmux_bootstrap_resolve_session` at `:68` with its awk
> |   `default_session:` match at `:83`. Both now route through the shared scalar
> |   normalization, so re-read them before assuming the YAML-only shapes still
> |   fail the way the context measured.
> | 
> | Tree-relative to the base commit this note records. The line numbers above are
> | dated by that commit; re-check them if the tree has moved.
