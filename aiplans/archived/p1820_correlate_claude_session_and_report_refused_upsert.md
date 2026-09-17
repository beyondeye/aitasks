---
Task: t1820_correlate_claude_session_and_report_refused_upsert.md
Base branch: main
Output branch: main
---

# t1820 — Refuse to guess a claude session; report a refused freeze upsert

## Context

Two upstream defects found during t1804's review:

1. `_claude_newest_transcript` (`.aitask-scripts/lib/agent_sessions.py:1839`)
   returns the newest cwd-matching transcript. With several claude agents in one
   repo that is routinely another agent's conversation — the exact bug t1804
   removed from the codex side.
2. `_resolve_record`'s fallback upsert (`.aitask-scripts/lib/agent_freeze.py:~515`)
   parses the id out of *any* `<WORD>:<id>|…` last line. `UPSERT_REFUSED:<id>|<reason>`
   exits 0 and carries a valid id, so a refusal is read as success, the pane is
   stamped with that id, and the freeze then fails at `freeze-begin` with a
   misleading begin-stage error.

### Pre-phase measurement (done, as the task required)

Correlating via the live process does **not** transfer: across 25 live `claude`
processes on this host, `/proc/<pid>/fd` held **zero** `*.jsonl` fds each —
claude appends and closes its transcript rather than holding it open (unlike
codex's rollout). So the fix is t1804's refusal rule, not an fd correlation.
Also noted: `newest_transcript_for` has no production caller (tests only), and
this repo's claude store holds ~320 transcripts, so on a real repo the claude
branch will now almost always answer `MISS_AMBIGUOUS` — the honest answer for a
backstop behind the SessionStart hook.

## Implementation

### 1. `agent_sessions.py` — `_claude_newest_transcript`
**Drop the two-scope early return.** Today's `for scope in (computed, everything)`
stops at the first scope with a match. Under a uniqueness rule that is wrong:
one session in the computed directory would hide a *different* session for the
same root in a directory only the full scan reaches (a changed encoding, or an
older layout still on disk), and the "unique" answer would again be a stranger's
conversation. Uniqueness can only be decided over **every** discovered
directory.

So: keep `computed` only to choose the miss reason; aggregate candidates over
all project directories of all stores (the full scan already contains the
computed dirs), deduplicating directories by resolved path so a store reached
twice (override == default, or a symlink) is read once:

```python
dirs: list[Path] = []
seen: set[str] = set()
for store in stores:
    try:
        children = [d for d in store.iterdir() if d.is_dir()]
    except OSError:
        continue
    for d in children:
        try:
            key = str(d.resolve())
        except OSError:
            key = str(d)
        if key not in seen:
            seen.add(key)
            dirs.append(d)

files = [...*.jsonl of every dir, OSError-tolerant as today...]
candidates: dict[str, list[Path]] = {}
for path in _newest(files):
    if _claude_transcript_cwd(path) == root:
        candidates.setdefault(path.stem, []).append(path)
if not candidates:
    return "", "", (MISS_NO_MATCH if computed else MISS_NO_PROJECT_DIR)
if len(candidates) > 1:
    # refuse rather than guess; no fd correlation exists (measured t1820)
    return "", "", MISS_AMBIGUOUS
session_id, paths = next(iter(candidates.items()))
return session_id, str(paths[0]), ""
```

Grouping by stem means the same session present in both the
`CLAUDE_CONFIG_DIR` store and the default store (distinct directories, not
deduplicated) is still one candidate, not an ambiguity; its newest path wins.
Cost: every transcript's cwd is read instead of stopping at the computed dir —
acceptable for a backstop with no production caller.

Update comments: the "CORRELATION, NOT RECENCY" module note and the
`newest_transcript_for` docstring currently say only the codex branch refuses;
state that both branches resolve single-session roots only, and record the
t1820 measurement (claude holds no transcript fd, so there is no claude
counterpart to `codex_session_for_pid`; the SessionStart hook is the mechanism).

### 2. `agent_freeze.py` — `_resolve_record` fallback upsert
After the `rc != 0` check, test the line prefix before parsing:

```python
lines = out.splitlines()
payload = lines[-1] if lines else ""
if payload.startswith("UPSERT_REFUSED:"):
    raise OSError(f"upsert refused: {payload}")
if not payload.startswith("UPSERTED:"):
    raise OSError(f"upsert returned no usable record id: {out!r}")
```

`freeze_pane` already turns `OSError` into `FREEZE_FAILED:resolve|<pane>|<exc>`,
and the raise sits before `set_option`, so a refused upsert stamps nothing and
never reaches `freeze-begin`.

### 3. Tests
- `tests/test_agent_sessions_transcripts.py` (claude layout class):
  - replace `test_selection_picks_the_newest` with
    `test_two_sessions_under_one_root_are_ambiguous` (regression t1820);
  - replace `test_tie_break_is_deterministic` with a variant proving equal-mtime
    distinct sessions are also ambiguous (determinism now trivially holds);
  - add `test_one_session_in_two_stores_is_not_ambiguous` (same stem under
    `CLAUDE_CONFIG_DIR/projects` and `~/.claude/projects`, env passed) → resolves;
  - add `test_another_projects_session_does_not_make_it_ambiguous` (a second
    session with a different cwd in the same dir → still resolves);
  - add `test_a_session_in_a_scanned_only_dir_is_not_hidden_by_the_computed_dir`
    — one session for `root` in the computed dir plus a distinct session for
    the same `root` in an unpredicted-encoding dir → `MISS_AMBIGUOUS` (this
    is the case an early return per scope would get wrong; confirm it goes red
    against a scope-ordered variant);
  - add `test_a_store_reached_twice_is_read_once` — `CLAUDE_CONFIG_DIR` pointing
    at `~/.claude` so both roots resolve to one store, a single session →
    resolves (not ambiguous, no duplicate-read artifacts).
- `tests/test_agent_freeze.py` `RecordResolutionTests`:
  add `test_a_refused_upsert_fails_at_resolve_and_stamps_nothing` — seed the
  pane's record, move it out of `live` (drive `freeze_begin` through the fake
  store / real transition), clear `@aitask_record`, freeze → `result.ok` false,
  `result.stage == "resolve"`, line contains `UPSERT_REFUSED`, no
  `freeze-begin` call recorded, pane record option still empty. Confirm it is
  red against the unfixed code (temporarily revert in an isolated copy, not the
  shared worktree).

## Verification
- `python3 -m pytest tests/test_agent_sessions_transcripts.py tests/test_agent_freeze.py -q`
- `bash tests/run_all_python_tests.sh --test-dir tests` not required in full;
  run the two modules plus `tests/test_frozen_restore_verdict.py` and
  `tests/test_agent_restore.py` (session-adjacent) — note these last two carry
  uncommitted edits from another session, so a failure there must be checked
  against that baseline rather than attributed to this change.
- `bash tests/test_session_hook.sh`

## Step 9
Post-implementation: current-branch mode — commit code (`bug: … (t1820)`) with
explicit paths only (the worktree has unrelated dirty files), then archive per
Step 9.

## Risk

### Code-health risk: low
- Change is local to one resolver branch and one parse site; the resolver has no production caller and the parse change only turns an already-failing path into an earlier, correct failure. · severity: low · → mitigation: None needed
- Full-store scan replaces the computed-dir fast path, so resolution reads every transcript's head (hundreds of files on a busy store). · severity: low · → mitigation: None needed (backstop only, no production caller)

### Goal-achievement risk: low
- None identified.

## Final Implementation Notes
- **Actual work done:** `_claude_newest_transcript` now aggregates cwd-matching transcripts over every project directory of every store (directories deduplicated by resolved path), groups them by session id (file stem), and returns `MISS_AMBIGUOUS` for more than one session; the computed dirname only picks the miss reason. `_resolve_record`'s fallback upsert now requires the `UPSERTED:` prefix and raises on `UPSERT_REFUSED:`, so the freeze fails at `resolve` naming the refusal and never stamps the pane. Module note and `newest_transcript_for` docstring updated.
- **Deviations from plan:** Plan review (user) caught that a per-scope early return (computed dir, then full scan) would let one session in the computed dir hide a distinct session for the same root elsewhere — the resolver now decides uniqueness over all directories. The symlinked-directory test was named to pin the outcome (still one session), since stem grouping, not the directory dedup, is what makes it unambiguous.
- **Issues encountered:** A red-proof copy that only included `lib/` failed collection; copying the full `.aitask-scripts` tree fixed it.
- **Key decisions:** Measured before designing: 0 open `*.jsonl` fds across 25 live claude processes, so no fd-correlated claude resolver exists — refusal rule only. Red proofs: HEAD freeze code fails the refusal test at stage `begin`; a scope-ordered mutant fails the scanned-only-dir test.
- **Upstream defects identified:** None
