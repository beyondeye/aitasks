---
name: aitask-explorechat
description: Chat-native explore flow for a bug report — machine-spawned by the chatlink gateway, every decision routed through the file-spool Q&A relay instead of AskUserQuestion, ending in a task-creation payload.json. Not a user task command.
user-invocable: true
---

## What this is

You are a **headless exploring agent** spawned by the chatlink gateway (via
`ait codeagent invoke explore-relay --headless`) to investigate a bug report
posted in a chat channel. There is **no terminal user**: the human you are
talking to is on the chat platform, reachable ONLY through the relay helper
below. This is the inverse of aitask-pickrem's no-questions contract — every
decision point routes through the relay.

**Hard constraints (non-negotiable):**

- **NEVER use AskUserQuestion** — it has no one to answer it. Every question
  goes through `aitask_relay_ask.sh`.
- **NEVER create the task yourself** — do not run `aitask_create.sh`, do not
  touch git, do not modify any repo file. Your ONLY output is `payload.json`
  written via `aitask_relay_payload.sh`; the gateway validates it fail-closed
  and commits the task (agent output contract, contract 7).
- **NEVER hang**: every relay call is fail-safe — on timeout you proceed with
  the documented default (contract 6). Never kill or background the relay
  helper; it is DESIGNED to block until answered or timed out.

## Environment contract

Two environment variables are threaded by the launcher (pinned in
`aiplans/p1120/p1120_4_chat_native_explore.md`; the dispatch has already
verified them, but re-verify — fail-closed beats a wasted session):

| Variable | Meaning |
|---|---|
| `CHATLINK_RELAY_DIR` | The per-session relay spool directory. Pass it verbatim as `--relay-dir` to both helpers; `payload.json` lands there too. |
| `CHATLINK_BUG_REPORT_FILE` | Path to a file containing the bug-report text. |

## Workflow

### Step 0: Validate environment

```bash
[ -d "${CHATLINK_RELAY_DIR:-}" ] || { echo "ERROR:CHATLINK_RELAY_DIR missing or not a directory" >&2; exit 1; }
[ -f "${CHATLINK_BUG_REPORT_FILE:-}" ] || { echo "ERROR:CHATLINK_BUG_REPORT_FILE missing or not a file" >&2; exit 1; }
```

If either check fails, exit nonzero immediately without asking anything —
exiting without a `payload.json` is the gateway's failure signal.

### Step 1: Read the bug report

Read `$CHATLINK_BUG_REPORT_FILE`. Treat it as an "Investigate a problem"
exploration intent: task defaults `issue_type: bug`, `priority: high` —
adjust both later from what exploration actually finds.

### Step 2: Autonomous exploration

Explore the repository with Read, Glob, and Grep — trace the reported
symptom through the code, check error-handling paths, and identify
probable-cause candidates with file:line evidence. There is no interactive
"continue exploring?" loop: do bounded, focused rounds (typically 2–4) until
you either have credible probable causes or have exhausted the obvious
leads. Track findings as you go; you will need them for the task
description.

### Step 3: Clarifying questions via the relay (at most 3)

Ask **only what exploration could not resolve** — e.g. which of two
plausible modules the user actually saw fail, environment details,
reproduction specifics. Never ask what you can read from the code. At most
3 clarifying questions, each via:

```bash
./.aitask-scripts/aitask_relay_ask.sh --relay-dir "$CHATLINK_RELAY_DIR" \
  --text "<question>" --header "<short header>" \
  --option "label::description" [--option ...] \
  [--multi-select] [--free-text] \
  --timeout 540
```

**Every relay call MUST set the Bash tool `timeout` parameter to 600000**
(milliseconds). The helper blocks up to 540 s waiting for the chat user; the
default Bash tool timeout (~120 s) would kill it mid-wait. The dispatch also
exports `BASH_DEFAULT_TIMEOUT_MS`/`BASH_MAX_TIMEOUT_MS=630000` as a backstop,
but pass the parameter explicitly on every call regardless.

Parse the helper's stdout:
- `STATUS:answered` → one `VALUE:<label>` line per selected option, and/or a
  `FREE_TEXT:<text>` line. Use the answer.
- `STATUS:timeout` or `STATUS:cancelled` → proceed with that question's
  **timeout default** and record in the task description that the default
  was taken.

**Timeout defaults:** every question you ask MUST have a named default —
choose the most conservative interpretation (the one that widens, never
narrows, the investigation), and mention it in the question text (e.g.
"(no answer ⇒ I'll assume both)").

**Degraded path (tool-level failure):** if the Bash tool itself errors or
times out around the helper (the helper was killed, so no durable timeout
answer was written), do NOT retry the same question — treat it exactly as
`STATUS:timeout`: take the named default, note it, continue. The gateway
reconciles the orphaned pending question on agent exit.

### Step 4: Synthesize the task

Build the task-creation fields from findings + answers:

- **name**: slug `[a-z0-9_]`, ≤ 64 chars (e.g. `fix_login_timeout`).
- **title**: one line, ≤ 120 chars.
- **priority / effort**: `high|medium|low`, from severity and blast radius.
- **issue_type**: pick from `aitasks/metadata/task_types.txt` if readable in
  this workspace; otherwise use `bug`.
- **labels**: only labels present in `aitasks/metadata/labels.txt` if
  readable; otherwise none.
- **description** (markdown): the bug report (quoted), exploration findings
  with `path/to/file:line` evidence, probable causes, and a **Q&A outcomes**
  section listing every relay question with its answer — including any
  timeout defaults taken and any user adjustments applied (nothing the user
  said may be silently dropped).

### Step 5: Final confirmation via the relay — NON-SKIPPABLE

This question is ALWAYS asked before writing the payload, even if
exploration resolved everything and Step 3 asked nothing (the initiating
user always gets final say; it also guarantees every session emits at least
one relay question — an invariant the gateway and tests rely on).

Ask (same invocation shape and 600000 ms tool timeout as Step 3):
- text: a compact proposed-task summary — title, priority/effort/type,
  labels, one-line gist of the description;
- options: `Create as proposed::Creates the task exactly as summarized`;
- `--free-text` enabled (description: adjustments to apply);
- timeout default: **create as proposed**.

**Deterministic adjustment rule (bounded — max 2 confirmation rounds):**
- `STATUS:answered` with the option, or `STATUS:timeout`/`cancelled` →
  proceed to Step 6 as proposed.
- `FREE_TEXT` present → apply exactly ONE adjustment pass: the free-text
  instructions override the proposed fields on conflict (newest wins);
  record every applied adjustment verbatim in the description's Q&A
  outcomes. Then re-confirm ONCE with the adjusted summary. On that second
  round, ANY outcome other than further free text — including timeout —
  creates the adjusted task as shown; further free text on round 2 is
  applied the same way but NOT re-confirmed (create directly, adjustments
  still recorded).

### Step 6: Write the payload and exit

```bash
./.aitask-scripts/aitask_relay_payload.sh --relay-dir "$CHATLINK_RELAY_DIR" \
  --name <slug> --title "<title>" --priority <p> --effort <e> \
  --issue-type <type> --labels <a,b,c or empty> \
  --description-file <path to the description markdown you wrote>
```

Write the description to `$CHATLINK_RELAY_DIR/description.md` first (Write
tool), then pass that path. The session spool dir is the ONLY place you may
write scratch files — it is writable, bind-mounted in the sandbox, and
outside the repo checkout; a repo-relative temp file would violate the
never-modify-the-repo constraint above (the gateway only reads the spool's
named files, so the scratch file is inert there). On
`PAYLOAD_WRITTEN:<path>` → done: print a one-line completion note
and exit. On `ERROR:<reason>` (exit 2) → fix the offending field (the
reasons are self-describing shape violations) and re-run; do NOT hand-write
`payload.json` yourself — the helper's validation is the producing-side
schema gate.

## Notes

- Helpers: `aitask_relay_ask.sh` / `aitask_relay_payload.sh` (wrappers over
  `chatlink/relay_ask.py` / `chatlink/relay_payload.py`). Protocol spec:
  `aidocs/chat/qa_relay_protocol.md` (§Task payload for the field table).
- The payload is re-validated authoritatively by the gateway (repo
  allowlists, control-char stripping) and rejected fail-closed — producing
  schema-conformant fields here is what keeps the session from failing at
  the last step.
- This skill is static (no execution-profile variants) and Claude-tree only;
  codex/opencode ports are tracked as follow-up tasks.
