---
Task: t1120_4_chat_native_explore.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_1_*.md … t1120_7_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_*_*.md
Worktree: aiwork/t1120_4_chat_native_explore
Branch: aitask/t1120_4_chat_native_explore
Base branch: main
---

Contracts: snapshot of parent plan §PINNED — provisional until t1120_1 freeze
(expected FROZEN — verify in parent plan before starting).

# Plan: t1120_4 — Chat-native explore operation

Pinned design decisions (dedicated skill; explicit opt-in headless flag;
env-threaded inputs), the agent output contract, and file list are in the task
file (`aitasks/t1120/t1120_4_chat_native_explore.md`). **Read t1120_1's
archived plan for the Step-0 spike findings** — they define the proven prompt
shape and helper-invocation pattern this skill must follow.

## Step 1 — skill `aitask-explorechat` (Claude tree first)

Read `aidocs/framework/skill_authoring_conventions.md` +
`aidocs/framework/stub-skill-pattern.md` BEFORE creating files. Adapt the flow
skeleton from `.claude/skills/aitask-explore-default-/SKILL.md`, replacing
every AskUserQuestion decision point with:

```bash
./.aitask-scripts/aitask_relay_ask.sh --relay-dir "$CHATLINK_RELAY_DIR" \
  --text "<question>" --header "<hdr>" \
  --option "label::description" [--option …] [--multi-select] [--free-text] \
  --timeout <s>
```

parsing `STATUS:`/`VALUE:` lines (and `FREE_TEXT:` for modal answers);
`STATUS:timeout` ⇒ proceed with the documented default for that decision
(fail-safe, contract 6 — never abort on timeout, never hang).

**Whitelist deliverable (t1120_1 handoff):** `aitask_relay_ask.sh` shipped in
t1120_1 deliberately WITHOUT permission-whitelist entries (no SKILL.md
referenced it yet — the extension-points doc forbids dead entries). The
moment this skill's SKILL.md cites the helper, complete the 7-touchpoint
allowlist checklist from `aidocs/framework/aitasks_extension_points.md`
("Adding a new helper script"). Also note (t1120_1 spike finding): the
helper's default `--timeout` is 90 s to stay under a headless agent's ~120 s
Bash-tool timeout — if this skill asks longer questions it must raise the
tool timeout explicitly. Flow: read bug-report context (passed as file path env
`CHATLINK_BUG_REPORT_FILE`) → explore sources for probable causes → ≤ N
clarifying questions → synthesize task fields → write `payload.json`
(contract 7 fields) to `$CHATLINK_SESSION_DIR` → exit. The skill NEVER runs
`aitask_create.sh`, never touches git (gateway commits).

Decide stub-vs-static per the authoring conventions (a static single-variant
skill is likely sufficient — it is machine-invoked, not profile-dispatched);
record the decision. Suggest follow-up tasks for codex/opencode ports per
CLAUDE.md rule.

## Step 2 — `ait codeagent` operation

`aitask_codeagent.sh`: add `explore-relay` to `SUPPORTED_OPERATIONS` (:28) and
to `build_invoke_command` (:396-506) for `claudecode`: headless requires
explicit `--headless` (billing caveat — refuse without it, matching
`batch-review` :438-446); constructs
`claude --model <cli_id> -p "/aitask-explorechat"` with env
`CHATLINK_RELAY_DIR`/`CHATLINK_SESSION_DIR`/`CHATLINK_BUG_REPORT_FILE`
threaded through. codex/opencode branches: error with "not yet supported"
(honest, distinct reason).

## Step 3 — payload conformance

Reuse `chatlink/relay.py` validation for payload schema on the producing side
(same dataclass) so t1120_6's gateway-side validation and this producer share
one schema definition — no drift.

## Testing

- `./.aitask-scripts/aitask_skill_verify.sh` clean.
- Dispatch unit test: `explore-relay` argv construction (dry-run seam), refusal
  without `--headless`, env threading (fake `claude` binary recording argv+env).
- Relay-conformance test with a scripted fake agent (bash script playing the
  agent role): emits schema-valid questions, handles `timeout` answer, writes
  schema-valid `payload.json`.
- Live smoke (skip-capable, explicit opt-in flag on the test): one real
  headless invocation round-trips a question.

## Step 9 reference

Post-implementation follows task-workflow Step 9.
