# SessionStart hook fixtures

Captured `SessionStart` hook payloads for the supported code agents, plus the
`schema.json` contract they are validated against.

These are **committed baselines**, not by-products of one developer's machine.
Child `t1705_3` consumes them unconditionally, so their presence, shape, status
and redaction are asserted on **every** run of
`tests/test_frozen_standin_spike.sh` (Case 5a) with no agent binary and no
opt-in required. The opt-in real-agent lanes (Cases 5b / 6) *refresh and diff*
against these baselines rather than being their only producer.

Validation is `tests/lib/validate_session_hook_fixtures.py`, driven by
`schema.json`.

## Read `_fixture_status` before reading anything else

Each fixture declares one of three statuses, with **different** required and
forbidden fields. A consumer must branch on it rather than assume a payload:

| status | meaning | how to consume |
|---|---|---|
| `captured` | a real, authoritative payload from the **interactive** launch path | treat the schema as settled |
| `unsupported` | the agent provably has no SessionStart hook (carries **no** payload key at all) | assert the opposite contract — no hook installed, no upsert — and record an explicit skip, never a pass by absence |
| `provisional` | inconclusive: not authoritative, not disproved | run assertions as **advisory**; do not treat the schema as settled |

## The pinning rule

The framework launches agents **interactively** (`launch_in_tmux`); `claude -p`
is a spike convenience only. Therefore:

1. The authoritative baseline — the file children 3 and 5 consume, and the file
   `schema.json` is derived from — is the payload captured on the
   **interactive** path. Nothing else may be pinned.
2. A headless capture is **never** committed as the baseline. A differing shape
   is recorded here as a documented variant, and only if a downstream child
   genuinely needs it does it become an explicitly non-authoritative
   `*_sessionstart.headless.json`, which `schema.json` does not govern.
3. If interactive equivalence has not been established, the fixture is committed
   as `provisional` with `_reason: no_interactive_capture`.

## `claude_sessionstart.json` — `captured`

- **Agent version:** claude 2.1.263
- **Captured:** 2026-09-06
- **Capture mode:** `interactive` (authoritative)
- **Payload keys:** `session_id`, `transcript_path`, `cwd`, `hook_event_name`,
  `source`, `model`
- **Hook config surface:** `<project>/.claude/settings.json`

  ```json
  {"hooks":{"SessionStart":[{"matcher":"startup|resume",
    "hooks":[{"type":"command","command":"<abs>/capture_hook.sh <out>","timeout":10}]}]}}
  ```

- **`$TMUX_PANE` and `AITASK_AGENT_STRING` are both visible** to the hook
  process (`%1` and `claudecode/opus5` respectively) — so the hook can bind a
  payload to the pane it ran in.
- **Headless variant:** a `claude -p` capture yields the same keys **minus**
  `model`. Recorded here as a documented variant; not committed.
- **Gotcha that blocks a capture:** claude refuses to start in an untrusted
  folder, and that dialog blocks `SessionStart` entirely. The probe pre-trusts
  the scratch project in a throwaway `CLAUDE_CONFIG_DIR` so the developer's own
  `~/.claude.json` is never touched. The project key must be the **realpath**
  (`/private/tmp/...` on macOS): a `/tmp/...` key silently fails to match and
  the dialog appears anyway.

### How to refresh

```bash
AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh --refresh-fixtures
```

Then redact (see below) and update the version/date lines above **in the same
commit** as the JSON.

## `codex_sessionstart.json` — `captured`

- **Agent version:** codex 0.163.0
- **Captured:** 2026-10-16
- **Capture mode:** `interactive` (authoritative)
- **Fires at:** the session's **first turn**, not at launch (`_fires_at:
  first_turn`). Nothing fired in the 12 s after launch; the payload arrived
  0.37 s after the first prompt was submitted. After `codex resume <id>` the hook
  fires at the resumed session's first turn, with `source: resume` and the same
  session id.
- **Payload keys:** `session_id`, `transcript_path`, `cwd`, `hook_event_name`,
  `source`, plus `model` and `permission_mode`.
- **`$TMUX_PANE` and `AITASK_AGENT_STRING` are both visible** to the hook, which
  runs as a child of the pane's own codex process.

**Version boundary.** Codex 0.153.4 fired SessionStart only under `codex exec`,
never in the interactive TUI, neither at launch nor after the first turn. The
first version that fires it interactively lies in (0.153.4, 0.163.0] and was not
bisected. On an older codex, and before the first turn on any codex, the freeze
engine captures the session from the rollout the agent's own process holds open
instead (t1804).

- **Config surface (established empirically):** a project-level
  `.codex/hooks.json` in the Claude-compatible shape is honoured, but only when
  the project is trusted:

  ```json
  {"hooks":{"SessionStart":[{"hooks":[{"type":"command","command":"<abs> <out>","timeout":10}]}]}}
  ```

  `[hooks]` in `config.toml` expresses the same contract in TOML
  (`SessionStart = [ MatcherGroup ]`, `MatcherGroup = { matcher?, hooks = [{type, command, …}] }`).
  Trust comes from `[projects."<realpath>"] trust_level = "trusted"` in
  `$CODEX_HOME/config.toml`; `--dangerously-bypass-hook-trust` bypasses the
  hook-trust prompt for one invocation.

- **The trap that made the probe strict:** a snake_case `session_start` key is
  **silently ignored** — no error, no warning. A guessed schema therefore
  produces a payload-free run that looks exactly like "the agent has no hooks",
  which is how an untested environment gets recorded as a capability limit.
  That is why the probe requires a positive-control chain before any verdict.
  The same trap exists in time: a probe that waits for a payload without sending
  a turn sees nothing on codex 0.163.0 either, which is how the interactive hook
  went unnoticed. Case 6 therefore records the pre-turn wait AND sends a turn.

### How to refresh

Same command as above. Case 6 waits a bounded interval with no prompt (and
records whether anything fired), then submits one prompt and waits for the
payload. Redact per the contract below, then update the version, date and timing
lines above **in the same commit** as the JSON. A refresh that captures nothing
after the turn is recorded as a finding, never committed over this baseline.

## `transcript_layout.json` — the fallback resolver's ground truth

Added by t1705_3. `newest_transcript_for` in `lib/agent_sessions.py` recovers a
session id from the agent's own transcript store when the hook never fired.
This fixture records the real store layouts it is written against, captured
from live stores on 2026-09-07.

**Since t1804 it is no longer the mechanism for interactive codex.** Matching on
`cwd` alone answers "some session of this project", and with several codex
agents in one repo the newest match is routinely a *different* agent's
conversation. A codex session is now captured at freeze time from the rollout
the agent's own process holds open (`codex_session_for_pid`), and this scan
refuses to choose between two sessions under one root (`MISS_AMBIGUOUS`). The
layouts below still describe both paths — the rollout filename and `payload`
shape are what the pid resolver reads too.

It exists because **two of the planned assumptions were wrong**, and both fail
*silently* (an empty result is indistinguishable from "this agent has no
session"):

| assumption | planned | actual |
|---|---|---|
| claude project-dir encoding | `/` → `-` | `/` **and `_`** → `-` (the planned rule matched 2 of 6 real dirs) |
| codex cwd location | first line, top-level `cwd` | first line `payload.cwd` (top-level `cwd` absent in 10/10) |

The claude rule is only **partially** determined — no observed directory
contained a `.` or a space — which is why the resolver treats the computed
directory name as a fast path and then VERIFIES the candidate by reading `cwd`
out of its transcripts, falling back to a full-store scan. That design is
correct under every candidate escape rule, so an unobserved character cannot
silently produce "no session".

Consumed by `tests/test_agent_sessions_transcripts.py`, which also asserts this
file stays valid, redacted, and in agreement with the implemented rule.

### How to refresh

Re-probe the real stores and update the JSON and the table above in the same
commit. Keep the redaction contract below: record the *rule*, never a path.

## `lsof_escaped_names.json` — how macOS `lsof` renders a path

Added by t2048. On macOS `codex_observe_pid` reads the rollout a codex process
holds open from `lsof -Fn` (run under `LC_ALL=C`), and lsof prints the name
**escaped**, not raw. Each pair records a real directory name and lsof's
rendering of it, captured from a live process on 2026-10-22 (lsof 4.91,
Darwin 24.6.0):

| real byte(s) | rendered as |
|---|---|
| `\` | `\\` |
| newline, tab, CR, BS, FF | `\n`, `\t`, `\r`, `\b`, `\f` |
| `≥ 0x7f` (e.g. UTF-8 `é`) | `\xNN` per byte (`caf\xc3\xa9`) |
| any other control byte | `^X` (`\x01` → `^A`) — **identical to a literal `^A`** |

The last row is why the decoder treats any `^` as uncertain. Treating it as
"no rollout here" instead would turn into `MISS_NO_MATCH`, which clears a stored
session id. The test fake renders names with these rules and is checked against
this file, so a fake emitting raw names cannot hide an escaping bug.

### How to refresh

Create directories with these names, hold one file open in each from a scratch
process, and run `LC_ALL=C lsof -n -P -w -Ffn -p <pid>`. Record names only,
never the absolute path (the redaction contract below applies).

## Redaction contract

Fixtures are committed to a public repository, and redaction is asserted on
every run — not only when a fixture is refreshed:

- `cwd`, when present, must be exactly `/REDACTED`.
- No value anywhere in the file may contain an absolute path under `/Users/` or
  `/home/`, the developer's home directory, or their user name.
- `transcript_path` is redacted while preserving its **shape**, so a consumer
  can still see the layout it will have to parse.

Session ids are retained: they come from throwaway sessions in temporary
directories that no longer exist, and a realistic-shaped value is what makes the
fixture useful to child 3.
