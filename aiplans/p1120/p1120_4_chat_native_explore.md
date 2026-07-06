---
Task: t1120_4_chat_native_explore.md
Parent Task: aitasks/t1120_discord_bug_report_channel_integration.md
Sibling Tasks: aitasks/t1120/t1120_5_*.md … t1120_8_*.md
Archived Sibling Plans: aiplans/archived/p1120/p1120_1_*.md … p1120_3_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-07-06 17:59
---

Contracts: snapshot of parent plan §PINNED — **FROZEN as of t1120_1**
(verified in parent plan contract 0; snapshots authoritative). This child
consumes contracts 1–3 (session_id / spool / schemas), 6 (timeout fail-safe),
7 (agent output contract).

# Plan: t1120_4 — Chat-native explore operation (`aitask-explorechat` + `explore-relay`)

## Context

Fourth child of t1120. Builds the agent-side half of the chat-native
bug-report flow: a dedicated skill whose every decision point routes through
the file-spool relay (`aitask_relay_ask.sh`, t1120_1) instead of
AskUserQuestion, ending in a schema-conformant `payload.json` that the
gateway (t1120_6) validates fail-closed and commits. Also adds the
`explore-relay` operation to `ait codeagent` so the sandbox launcher
(t1120_5) has a single argv to spawn.

## Verification notes (2026-07-06, pre-implementation verify pass)

Re-checked the pending plan's assumptions against current source:

- Parent §PINNED contracts **FROZEN** (t1120_1 archived; spike PASS).
- `aitask_relay_ask.sh` landed as described: wrapper over
  `python3 -m chatlink.relay_ask`; flags `--relay-dir --text --header
  --option label::desc --multi-select --free-text --timeout`; stdout
  `STATUS:answered|timeout|cancelled` + `VALUE:<label>` lines +
  `FREE_TEXT:<text>`; exit 0 on any terminal status, exit 2 on usage errors;
  **default `--timeout` 90 s** (spike finding: agent Bash-tool default
  timeout ~120 s — longer asks must raise the tool timeout explicitly).
- `aitask_codeagent.sh`: `SUPPORTED_OPERATIONS` at :28;
  `build_invoke_command` claudecode branch :412-450; `batch-review`
  headless precedent :438-446 (`OPT_HEADLESS` → prepend `--print`); a
  `--dry-run` seam already exists (:523-528, prints `DRY_RUN:` + argv) —
  dispatch tests need no live agent call. NOTE: batch-review *falls back*
  to interactive without `--headless`; explore-relay instead **refuses**
  (there is no interactive variant of a relay-driven machine-spawned flow).
- `chatlink/spawn_seam.py` (t1120_3): `SandboxSpec(session_id, relay_dir,
  agent_argv, env_allowlist, limits)` — the gateway threads an opaque
  `agent_argv` and an env allowlist; **no CHATLINK_* env names exist
  anywhere yet** (checked code + sibling plans) — this plan pins them.
- `chatlink/relay.py` has `SessionDir.write_payload/read_payload` but **no
  payload schema** — the pending plan's "reuse the same dataclass" requires
  *adding* it (Step 2 below). Contract 1 requires `session_id` inside the
  payload.
- Skill-shape decision (recorded per task AC): **static single-variant
  SKILL.md** — machine-invoked, never profile-dispatched; precedent
  `aitask-shadow` (static, `user-invocable: true` because spawned agents
  trigger via slash-command-on-argv). No `.j2`, no stub, no per-profile
  variants.
- Whitelist checklist (`aidocs/framework/aitasks_extension_points.md`
  "Adding a new helper script") is **5 config files** in current form:
  `.claude/settings.local.json`, `.codex/rules/default.rules`,
  `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
  `seed/opencode_config.seed.json`.

**Deviation from the pending plan (env vars — single name, no alias):**
`CHATLINK_SESSION_DIR` is **eliminated entirely**, not aliased — per
contract 2 the questions, answers, and `payload.json` all live in the same
`<relay_root>/<session_id>/` dir, and intake passes exactly that dir as
`relay_dir`; `aitask_relay_ask.sh --relay-dir` already expects the concrete
session dir (not the relay root). Two names for one directory is a drift
hazard: a gateway exporting one while the skill validates the other makes
the payload land where nobody watches. **`CHATLINK_RELAY_DIR` is the one
canonical name** across ALL surfaces: codeagent env preconditions, skill
env validation, every helper invocation, tests, and the protocol doc's env
table. Completeness check before commit:
`grep -rn CHATLINK_SESSION_DIR .aitask-scripts/ .claude/ tests/ aidocs/`
must return nothing. Pinned env contract (consumed by t1120_5/6, which
reference it generically):

| Env var | Meaning |
|---------|---------|
| `CHATLINK_RELAY_DIR` | Per-session spool dir — the concrete `<relay_root>/<session_id>/` directory (questions/answers/payload.json all here); passed verbatim as `--relay-dir` |
| `CHATLINK_BUG_REPORT_FILE` | Path to a file containing the bug-report text |

## Step 1 — payload schema + producer helper (testability-first: pure unit first)

**Schema ownership (explicit, so t1120_6 cannot mis-assume):**
`SessionDir.write_payload()` / `read_payload()` **stay opaque** — dict-only
transport, semantics unchanged (its docstring gains one line: "field
validation is the caller's job via `TaskPayload`"). `TaskPayload` is the
**shared schema helper** both sides consume: the producer
(`relay_payload.py`, this task) validates shape before writing; the gateway
validator (t1120_6) starts from `TaskPayload.from_dict` and layers repo
allowlists + control-char stripping on top. The protocol doc's module map
records this split so t1120_6 neither duplicates the schema nor assumes
`write_payload()` validates.

**`chatlink/relay.py`:** add `TaskPayload` dataclass (contract 7 + contract 1),
stdlib-only, strict `to_dict`/`from_dict` validation mirroring
`Question`/`Answer`:
- fields: `session_id` (relay-lib charset/length rules), `name` (slug
  `[a-z0-9_]`, ≤ 64), `title` (non-empty, ≤ 120), `priority` / `effort` ∈
  {high, medium, low}, `issue_type` (non-empty slug — the *repo allowlist*
  check against `task_types.txt` is gateway-side, t1120_6), `labels` (list of
  slug strings), `description` (non-empty, ≤ 64 KiB).
- Producer-side validation is **shape-strict but repo-agnostic**: the
  sandboxed producer cannot own `labels.txt`/`task_types.txt` allowlist
  authority; t1120_6's gateway validator layers allowlists + control-char
  stripping on top of this same dataclass — one schema definition, no drift.

**New `chatlink/relay_payload.py`:** argparse CLI
(`--relay-dir --name --title --priority --effort --issue-type
--labels a,b,c --description-file <path|->`): derives `session_id` from the
relay-dir basename, builds + validates `TaskPayload`, writes atomically via
`SessionDir.write_payload`. Prints `PAYLOAD_WRITTEN:<path>`; exit 2 with a
distinct `ERROR:<reason>` on validation failure (the agent sees it and can
fix — fail early, not at the gateway).

**New `.aitask-scripts/aitask_relay_payload.sh`:** thin wrapper mirroring
`aitask_relay_ask.sh` (same PYTHONPATH exec pattern, stdlib-only note,
shebang + `set -euo pipefail` per `aidocs/framework/shell_conventions.md`).

**Doc:** add a `## Task payload` section to `aidocs/chat/qa_relay_protocol.md`
(normative field table, producer-vs-gateway validation split).

## Step 2 — `ait codeagent` operation `explore-relay`

`aitask_codeagent.sh`:
- Add `explore-relay` to `SUPPORTED_OPERATIONS` (:28).
- claudecode branch in `build_invoke_command`:
  - **Refuse without `--headless`** (billing caveat,
    `aidocs/framework/shell_conventions.md:40-47`): `die "explore-relay is
    headless-only; pass --headless to accept Claude Code's headless billing
    surcharge"`.
  - **Env preconditions, distinct reasons** (checked even under `--dry-run`
    so refusal is unit-testable): `CHATLINK_RELAY_DIR` unset/not-a-dir and
    `CHATLINK_BUG_REPORT_FILE` unset/not-a-file each die with their own
    message.
  - argv: `claude --model <cli_id> --print --allowedTools
    "Bash,Read,Write,Glob,Grep" "/aitask-explorechat"` — natural
    slash-command in print mode (never inline rendered SKILL.md via `-p`,
    per authoring conventions); `--allowedTools` required headless (spike
    finding: no permission prompts available). Env vars pass through
    `exec` untouched.
  - **Tool-timeout budget (engine-owned, not model-remembered):** the
    dispatch exports `BASH_DEFAULT_TIMEOUT_MS=630000` and
    `BASH_MAX_TIMEOUT_MS=630000` into the spawned agent's environment
    (Claude Code's documented Bash-tool timeout controls), so the relay
    helper's 540 s deadline fits under the tool timeout even if the model
    omits the per-call `timeout` parameter. The skill's per-call
    instruction (Step 3) is belt; this is braces. **This is the unproven
    link in the spike chain** (spike only proved the ~120 s default), so
    it is verified by the mandatory live smoke (Step 4) with a
    deliberately-late answer.
- codex/opencode branches: `die "explore-relay not yet supported for
  <agent>"` (honest, distinct reason; ports = suggested follow-up tasks).
- Help text: add `explore-relay` to the Operations line and extend the
  `--headless` description beyond batch-review.

## Step 3 — skill `.claude/skills/aitask-explorechat/SKILL.md` (static, Claude tree only)

Frontmatter: `user-invocable: true` (slash-on-argv), description marking it
as machine-spawned by the chatlink gateway, not a user task command.

Flow (adapted from `aitask-explore-default-` Step 1→2→3 skeleton, with every
AskUserQuestion decision point mapped to a relay question; hard constraints
stated up front — the skill NEVER runs `aitask_create.sh`, never touches
git, never uses AskUserQuestion):

0. **Env validation:** require `CHATLINK_RELAY_DIR` (dir) and
   `CHATLINK_BUG_REPORT_FILE` (file); on failure print a distinct error and
   exit nonzero — exit-without-payload is the gateway's failure signal
   (fail-closed, contract 7).
1. **Read the bug report** from `$CHATLINK_BUG_REPORT_FILE`; treat as the
   "Investigate a problem" intent (defaults `issue_type: bug`,
   `priority: high`, adjustable from findings).
2. **Autonomous exploration** (Grep/Glob/Read; no interactive
   explore-more loop — bounded, focused rounds tracing the symptom to
   probable-cause candidates).
3. **≤ 3 clarifying relay questions**, each via:
   ```bash
   ./.aitask-scripts/aitask_relay_ask.sh --relay-dir "$CHATLINK_RELAY_DIR" \
     --text "<question>" --header "<hdr>" \
     --option "label::description" [...] [--multi-select] [--free-text] \
     --timeout 540
   ```
   invoked with the **Bash tool `timeout` parameter set to 600000 ms**
   explicitly on every relay call (spike finding: helper deadline must stay
   under the tool timeout; 540 s gives the Discord user 9 min per question;
   the dispatch-side `BASH_*_TIMEOUT_MS` exports in Step 2 back this up).
   Parse `STATUS:`/`VALUE:`/`FREE_TEXT:`. **Every question names its
   timeout default** (skill guidance: most conservative option), and
   `STATUS:timeout` ⇒ proceed with that default and note it in the task
   description (contract 6 — never abort, never hang). **Degraded-path
   rule:** if the Bash *tool itself* errors or times out around the helper
   (helper killed ⇒ no durable timeout answer written), do NOT retry the
   same question — treat it exactly as `STATUS:timeout` (take the named
   default, note it) and continue; the orphaned pending question is
   reconciled by the gateway's agent-death cancelled-answer pass
   (contract 6). Only ask what exploration could not resolve.
4. **Synthesize task fields**: name slug, title, priority, effort,
   issue_type (pick from `aitasks/metadata/task_types.txt` when readable in
   the workspace copy, else `bug`), labels (⊆ `labels.txt` when readable,
   else empty), description markdown (findings, probable causes, evidence
   paths, Q&A outcomes incl. any timeout defaults taken).
5. **Final confirmation relay question — NON-SKIPPABLE by contract**: this
   question is ALWAYS emitted before any payload write, even when
   exploration resolved everything and zero clarifying questions were
   asked (the initiating user always gets final say, and it structurally
   guarantees every run emits ≥ 1 relay question — the deterministic hook
   the live smoke relies on; the skill states this invariant explicitly).
   Proposed-task summary with options "Create as proposed" / free-text
   adjustments (`--free-text`); timeout ⇒ create as proposed. **Deterministic adjustment rule (bounded,
   max 2 confirmation rounds):** if the answer carries free text, apply
   exactly one adjustment pass — free-text instructions override the
   proposed fields on conflict (explicit composition: newest wins), and
   every applied adjustment is recorded verbatim in the description's Q&A
   outcomes section (visible in the created task, never silently dropped).
   Then re-confirm ONCE with the adjusted summary; on that second round,
   any answer other than further free text — including timeout — creates
   the adjusted task as shown (further free text on round 2 is applied the
   same way but NOT re-confirmed: create directly, adjustments still
   recorded in the description).
6. **Write payload** via `aitask_relay_payload.sh --relay-dir
   "$CHATLINK_RELAY_DIR" ...` and exit 0.

**Whitelist deliverable (t1120_1 handoff, fires now):** the moment this
SKILL.md cites `aitask_relay_ask.sh`, complete the extension-points
allowlist checklist for it — and for the new `aitask_relay_payload.sh` — in
all 5 config files listed in the verification notes (2 helpers × 5 files).

Run `./.aitask-scripts/aitask_skill_verify.sh` before committing (static
skill adds no `.j2`; the run guards the existing stub surfaces).

## Step 4 — tests

- **`tests/test_chatlink_relay.sh` (extend):** `TaskPayload` accept +
  rejection matrix (missing field, bad enum, oversize title/name/
  description, non-list labels, bad slug); helper E2E through the real
  `aitask_relay_payload.sh` wrapper (temp session dir → run → assert
  `PAYLOAD_WRITTEN`, decode `payload.json` **wire bytes independently**
  (json.load, not the dataclass) and compare fields — independent ground
  truth; invalid input ⇒ exit 2 + `ERROR:` + **no payload.json written**
  (no side effect before validation); `session_id` auto-derived from dir
  name).
- **New `tests/test_codeagent_explore_relay.sh`:** via `--dry-run` seam —
  exact argv (incl. `--print`, `--allowedTools`, `/aitask-explorechat`);
  refusal without `--headless` (nonzero + message); missing
  `CHATLINK_RELAY_DIR` vs missing `CHATLINK_BUG_REPORT_FILE` ⇒ two distinct
  reasons; codex/opencode ⇒ "not yet supported"; existing operations still
  dispatch (regression guard on the shared case ladder).
- **Relay-conformance test with a scripted fake agent** (same file or
  sibling): a bash script plays the agent role — asks one question via the
  real `aitask_relay_ask.sh` (test answers it), asks a second with
  `--timeout 1` (nobody answers ⇒ asserts the durable
  `answer-<seq>.json {status: timeout}` artifact and that the script
  proceeds), then writes the payload via the real helper. Asserts emitted
  `question-*.json` conform to contract 3 (fields incl. auto-assigned
  `o<idx>` option values) and the final `payload.json` validates.
- **Live smoke (env-gated for routine runs, MANDATORY once in-task):**
  gated on `RUN_LIVE_EXPLORE_RELAY=1` — real `ait codeagent invoke
  explore-relay --headless` against a fixture bug-report file + temp relay
  dir. **The ≥ 1-question guarantee is structural, not hoped-for:** the
  skill's Step-5 final confirmation question is NON-SKIPPABLE by contract,
  so even if the model finds the fixture unambiguous and asks zero
  clarifying questions, at least one `question-*.json` always appears —
  the smoke never hangs on model discretion. The smoke polls for the
  *first* question (whichever it is), **deliberately delays the answer
  past 150 s** before writing it (proves the `BASH_*_TIMEOUT_MS` exports
  actually carry a real skill invocation past the ~120 s default tool
  timeout — the unproven link), answers with a generic strategy (first
  option / "create as proposed"; free-text answer if the question is
  option-less), answers any subsequent questions promptly the same way,
  and asserts `payload.json` lands and exit 0.
  This directly exercises the central goal-achievement risk
  (slash-command discovery + `--allowedTools` in print mode), which no
  dry-run/fake-agent test can reach — so **one live run is a required
  pre-archive verification for this task**: execute it during
  implementation (billing opt-in accepted once, as t1120_1's spike did)
  and record the outcome in the plan's Final Implementation Notes. It
  stays env-gated so routine suite runs never incur the billed call. If
  the delayed-answer leg fails (tool kills the helper despite the
  exports), fall back to helper `--timeout 90` (under the proven default)
  before archiving, and record the constraint for t1120_6.
- `shellcheck` on both new/edited `.sh` files.

## Step 5 — follow-up suggestions (end of session, per CLAUDE.md rule)

Suggest separate aitasks: codex + opencode `explore-relay` ports (skill
wrapper + dispatch branch). Do not create them silently.

## Step 9 reference

Post-implementation follows task-workflow Step 9 (merge/verify/archive/push).

## Risk

### Code-health risk: low
- Shared-surface edit to `aitask_codeagent.sh` dispatch (case ladder +
  help) could regress existing operations · severity: low · → mitigation:
  embedded (additive-only branch; regression check on existing ops in the
  new dispatch test)
- `TaskPayload` lands inside the frozen-surface relay module ·
  severity: low · → mitigation: embedded (additive dataclass; existing
  63-check suite must stay green; import-guard test extends to
  `relay_payload.py`)

### Goal-achievement risk: medium
- Skill-based headless invocation (`claude --print "/aitask-explorechat"`)
  is not byte-identical to the spike's raw-prompt shape — slash-command
  expansion + `--allowedTools` interplay in print mode could behave
  differently · severity: medium · → mitigation: embedded (live smoke is a
  REQUIRED once-in-task pre-archive verification with outcome recorded in
  Final Implementation Notes; env-gated only for routine suite runs;
  t1120_8 MV sibling validates live end-to-end)
- Bash-tool timeout extension past the proven ~120 s default is unverified
  for a real skill invocation — if the exports don't hold, the tool kills
  the blocking helper before the durable timeout answer is written ·
  severity: medium · → mitigation: embedded (engine-owned
  `BASH_*_TIMEOUT_MS` exports + per-call `timeout` parameter + skill
  degraded-path rule treating a tool-level kill as `STATUS:timeout`;
  delayed-answer leg of the mandatory live smoke proves it; documented
  fallback to `--timeout 90` if disproven)
- 540 s per-question budget may prove short for real Discord answer latency
  · severity: low · → mitigation: embedded (timeout is fail-safe by design —
  flow completes with documented defaults; budget is a named constant in the
  skill, trivially tunable)
- Producer/gateway payload-schema drift once t1120_6 lands its validator ·
  severity: low · → mitigation: embedded (single `TaskPayload` definition in
  `chatlink/relay.py` consumed by both sides; normative table in
  `qa_relay_protocol.md`)
