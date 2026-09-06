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

## `codex_sessionstart.json` — `provisional` (`no_interactive_capture`)

- **Agent version:** codex 0.153.4
- **Captured:** 2026-09-06
- **Capture mode:** `exec` — **not** the production launch path, hence
  `provisional`.

Codex 0.153.4 **does** have a working SessionStart hook, delivering
`session_id`, `transcript_path`, `cwd`, `hook_event_name`, `source`, plus
`model` and `permission_mode`. What it does **not** do is fire it in the
interactive TUI.

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

- **The trap this fixture exists to prevent:** a snake_case `session_start` key
  is **silently ignored** — no error, no warning. A guessed schema therefore
  produces a payload-free run that looks exactly like "the agent has no hooks",
  which is how an untested environment gets recorded as a capability limit.
  That is why the probe requires a positive-control chain before any verdict.

- **The finding:** `SessionStart` fires under `codex exec` and does **not** fire
  in the interactive TUI — neither at launch nor after the first turn. Since the
  framework launches agents interactively, no session id is capturable via
  SessionStart on codex's production path.

### How to refresh

Same command as above. A refresh that obtains an **interactive** codex capture
must also flip `_fixture_status` to `captured`, set
`_capture_mode: interactive`, drop `_reason`, and update the findings block in
`aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`.

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
