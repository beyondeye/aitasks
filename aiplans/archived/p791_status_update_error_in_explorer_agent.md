---
Task: t791_status_update_error_in_explorer_agent.md
Base branch: main
plan_verified: []
---

# Plan — t791: Heartbeat `-m` flag failure in brainstorm explorer agents

## Context

While running `ait brainstorm 635`, two explorer sub-agents hit problems
updating status:

1. One agent crashed its heartbeat call with:
   ```
   ./ait crew status --crew brainstorm-635 --agent explorer_001a heartbeat \
     -m "Phase 1 complete — baseline loaded, understanding constraints"
   → ait crew status: error: unrecognized arguments: -m Phase 1 ...
   ```
   It recovered only by calling `--help`, discovering `--message`, and retrying.
2. Another agent appears to have skipped heartbeats entirely (the user's
   log shows no heartbeat attempt before the agent stopped reporting). Most
   likely the same root cause: the agent silently gave up after a similar
   guess-and-fail.

### Comparison: is the patcher really "working"?

Checked the patcher path in `brainstorm-635` (node `n001_infra_only`).
Findings:

- `templates/patcher.md:87,102,117,138,145` uses the **exact same**
  phrasing as `templates/explorer.md`: "Execute the **Heartbeat / Alive
  Signal** procedure from your `_instructions.md` with message: …"
- `patcher_001_instructions.md:16-20` is byte-identical to
  `explorer_001a_instructions.md` in the heartbeat block (bare `heartbeat`,
  no `--message` example). Same generator: `aitask_crew_addwork.sh`.
- `patcher_001_alive.yaml` shows `last_message: null`. The heartbeat code
  at `agentcrew_status.py:208-209` only **writes** `last_message` when an
  arg is provided — it never clears one. So `null` proves the patcher
  **never** successfully passed `--message`; every heartbeat it made was
  bare. The per-checkpoint message instructions in `patcher.md` were
  silently dropped.
- Same pattern for `detailer_001`, `initializer_bootstrap`,
  `explorer_001b` — all `last_message: null`. Only `explorer_001a` (the
  one that retried) has a real message recorded.

Conclusion: the patcher is "working" only in the narrow sense of "doesn't
error, status reaches Completed". It is **not** a successful reference
pattern for heartbeat messaging — it hits the same instruction gap, just
less visibly (the agent skipped the message rather than guessing `-m`).
Both agent types run through the same shared infrastructure
(`aitask_crew_addwork.sh` generator + `agentcrew_status.py` parser), so a
single fix covers both.

### Root cause

The explorer prompt template instructs the agent to send heartbeats **with a
message**, but the generated `_instructions.md` shows the heartbeat command
with no message example, leaving the agent to guess the flag name:

- `.aitask-scripts/brainstorm/templates/explorer.md:130,147,163,189`
  > "Execute the **Heartbeat / Alive Signal** procedure from your
  > `_instructions.md` with message: ..."

- `.aitask-scripts/aitask_crew_addwork.sh:221-225` (generates `_instructions.md`)
  ```bash
  ## Heartbeat / Alive Signal
  Periodically write to your alive file to signal you are active:
  `ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat`
  ```
  No `--message` example — the agent has to invent it.

- `.aitask-scripts/agentcrew/agentcrew_status.py:289-290`
  ```python
  hb_p = sub.add_parser("heartbeat", help="Update agent heartbeat")
  hb_p.add_argument("--message", help="Optional progress message")
  ```
  Only `--message` is accepted; `-m` is the near-universal convention
  (git, npm, docker, gh, kubectl, …) and a very natural agent guess.

The fix is two complementary changes: make the right flag discoverable in
the instructions the agent actually reads, and accept the natural short
alias defensively.

## Changes

### 1. Show `--message` in generated `_instructions.md`

**File:** `.aitask-scripts/aitask_crew_addwork.sh`
**Lines:** 221-225

Update the heartbeat block in the generated lifecycle instructions so the
message flag is visible to the agent:

```bash
## Heartbeat / Alive Signal
Periodically write to your alive file to signal you are active:
\`\`\`bash
ait crew status --crew ${CREW_ID} --agent ${AGENT_NAME} heartbeat [--message \"<short status>\"]
\`\`\`
The optional \`--message\` describes what you just finished (e.g. \"Phase 1
complete — baseline loaded\"). Use it at every checkpoint.
```

Rationale: the explorer/patcher/detailer templates all tell the agent to
send a message; the instructions they all read must show the flag.
Primary fix — without it, the same bug recurs for every agent type.

### 2. Accept `-m` as a short alias for `--message`

**File:** `.aitask-scripts/agentcrew/agentcrew_status.py`
**Line:** 290

```python
hb_p.add_argument("-m", "--message", help="Optional progress message")
```

Rationale: defense in depth. `-m` is the universal short form. If a future
template change or agent inference produces `-m`, it works. Zero risk
(pure addition of a short alias; no existing caller affected).

## Files NOT changed (and why)

- `.aitask-scripts/brainstorm/templates/{explorer,patcher,detailer,…}.md`
  — their wording ("…with message: …") is correct and consistent with
  the procedure pattern used for other checkpoints. The bug is the
  missing flag in the generated instructions, not the template phrasing.
- `aidocs/agentcrew/agentcrew_work2do_guide.md` — already correct (shows
  `--message`); it's reference documentation the agent does not read
  directly, so it does not factor into the runtime bug.
- `set --status` / `set --progress` — no short flags are added; those
  flags don't share a universal one-letter convention (unlike `-m`), and
  no failures have been observed there.

## Verification

1. **Lint:** `shellcheck .aitask-scripts/aitask_crew_addwork.sh`

2. **Regenerate a crew and inspect:** in a throwaway brainstorm run (or by
   invoking `aitask_crew_addwork.sh` directly via its existing entry
   point), generate a fresh `<agent>_instructions.md` and confirm the
   heartbeat block now reads `heartbeat [--message "<short status>"]` plus
   the trailing usage note.

3. **CLI smoke test (both flag forms):** in any existing crew workspace:
   ```bash
   ./ait crew status --crew <crew_id> --agent <agent_name> heartbeat -m "smoke -m"
   ./ait crew status --crew <crew_id> --agent <agent_name> heartbeat --message "smoke --message"
   ```
   Both must succeed without `unrecognized arguments`. `_alive.yaml`'s
   `last_message` should reflect the most recent message after each call.

4. **Existing tests:** scan `tests/` for anything exercising `crew status
   heartbeat`. Run any matching test files individually (e.g.
   `bash tests/test_crew_status*.sh`).

## Out of scope (note for Final Implementation Notes)

- First agent's apparent silence (no heartbeat call visible in the log
  snippet at all) is consistent with — but not proven by — the same root
  cause. If brainstorm runs continue to show explorers stopping without
  heartbeats after this fix lands, a follow-up task should investigate.
- The patcher/detailer/initializer agents have been silently dropping
  their checkpoint messages too (all `last_message: null` despite their
  templates instructing a message). This fix should restore message
  capture for them as a side effect; confirm during verification by
  inspecting `_alive.yaml` after the next brainstorm run.

## Cross-version porting (per CLAUDE.md)

`aitask_crew_addwork.sh` and `agentcrew_status.py` live under
`.aitask-scripts/` (framework code, not under any per-agent skill tree),
so a single edit covers all four code-agent surfaces (Claude Code, Codex,
Gemini, OpenCode). No skill/command porting follow-ups needed.

## Commit plan

Single code commit, message:

```
bug: Show --message in heartbeat instructions and accept -m alias (t791)
```

Plan file commit (separate, via `./ait git`):

```
ait: Update plan for t791
```

## Final Implementation Notes

- **Actual work done:** Two-line change exactly as planned.
  1. `.aitask-scripts/agentcrew/agentcrew_status.py:290` — added `-m` as
     a short alias on the heartbeat sub-parser:
     `hb_p.add_argument("-m", "--message", …)`.
  2. `.aitask-scripts/aitask_crew_addwork.sh:221-227` — updated the
     generated `_instructions.md` Heartbeat block to show
     `heartbeat [--message "<short status>"]` and a one-line usage hint
     ("describes what you just finished, use at every checkpoint").
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:**
  - Defense-in-depth chosen (both edits) rather than docs-only. After
    user-confirmed plan approval, both changes apply.
  - Templates (`brainstorm/templates/{explorer,patcher,…}.md`) left
    untouched — their "with message:" phrasing is correct; the gap was
    purely in the generated instructions the agent reads at runtime.
- **Upstream defects identified:** None. (The patcher/detailer agents'
  silent message-dropping is the same root cause as this task; the fix
  here addresses it. Not a separate upstream defect.)
- **Verification performed:**
  - `shellcheck .aitask-scripts/aitask_crew_addwork.sh` — clean (only
    pre-existing SC1091/SC2001 info/style warnings unrelated to the
    change).
  - `python3 -c "import py_compile; py_compile.compile(…)"` on the edited
    Python file — OK.
  - `bash tests/test_crew_status.sh` — 57/57 PASS, including the
    heartbeat CLI test (which still uses `--message`, so the long form
    is unchanged).
  - CLI smoke against existing `brainstorm-635/patcher_001` workspace
    (gitignored, no repo pollution):
    - `heartbeat -m "smoke -m alias test (t791)"` →
      `HEARTBEAT_UPDATED:patcher_001`, `last_message` written.
    - `heartbeat --message "smoke --message test (t791)"` →
      `HEARTBEAT_UPDATED:patcher_001`, `last_message` written.
    - `heartbeat --help` → output now shows `-m, --message MESSAGE`.
  - Rendered the heredoc fragment in isolation
    (`CREW_ID=test-crew AGENT_NAME=test_agent`) to confirm the
    backslash-escapes produce a well-formed Markdown code block with
    the new `[--message "<short status>"]` syntax.
