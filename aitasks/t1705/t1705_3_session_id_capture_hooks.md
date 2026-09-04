---
priority: high
effort: medium
depends: [t1705_2]
issue_type: feature
status: Ready
labels: [codeagent, claudecode, codexcli, install, ait_setup, seed, session_persistence, testing]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:03
updated_at: 2026-09-04 16:03
---

## Context

Third child of t1705 (frozen code agents). Restoring a frozen agent needs the
code agent's own **session id** (`claude --resume <id>` / `codex resume
<id>`). The one mechanism that works for both agents is a **`SessionStart`
hook** — verified by t1705_1, whose captured payloads live in
`tests/data/session_hooks/`. This child ships that hook and makes `ait setup`
install it into every project — a **new install surface**: today
`.claude/settings.json` (the PreToolUse guard) is dev-repo-only, not seeded,
not in the release tarball, not in either framework-path list, and
`merge_claude_settings()` merges `permissions.allow` only; Codex has no
`[hooks]` block anywhere and `merge_codex_settings()` re-serialises TOML with
a hand-rolled `toml_serialize` that drops comments. The parent plan's §A/§B
(**PINNED**, reproduced in `aiplans/p1705/p1705_3_session_id_capture_hooks.md`)
define what the hook writes; t1705_1's findings say which Codex mechanism is
real (if Codex hooks proved unavailable, ship the Claude side and record
"codex = re-pick only" in the hook script's header and the docs child).

## What the hook does (`.aitask-scripts/aitask_session_hook.sh`)

Stdin: the agent's JSON payload (`session_id`, `transcript_path`, `cwd`,
`source`). Always exits 0 and never blocks the agent (a broken hook must not
break a session). Steps:

1. `[ -n "${TMUX_PANE:-}" ]` else exit 0 (not in tmux → nothing to record).
2. Parse the payload with `python3 -c` (stdlib json; the hook runs in the
   agent's env, not the venv). Resolve `root` = nearest ancestor of `cwd`
   containing `aitasks/metadata/project_config.yaml` (reuse
   `agent_launch_utils._walk_up_to_aitasks` semantics via a one-liner or a
   small `lib/` helper).
3. One tmux round-trip through `ait_tmux display-message -p -t "$TMUX_PANE"
   '#{session_name}\t#{window_name}\t#{pane_id}\t#{pane_pid}\t#{@aitask_record}'`.
4. If `AITASK_RESTORE_RECORD`/`AITASK_RESTORE_NONCE`/`AITASK_RESTORE_MODE`
   are set (a restore launch, §D): call `aitask_agent_sessions.sh upsert …
   --restore-of "$AITASK_RESTORE_RECORD" --nonce "$AITASK_RESTORE_NONCE"
   --session-id …`. Otherwise plain `upsert` with `--id` when
   `@aitask_record` was present, plus `--agent-string "${AITASK_AGENT_STRING:-}"`
   (exported by `aitask_codeagent.sh:611`), `--operation`/`--task-id` derived
   from the window name (`agent-(pick|qa|resume)-<id>` — same regex as
   `monitor_core._TASK_ID_RE`).
5. `ait_tmux set-option -p -t "$TMUX_PANE" @aitask_agent_session "<session_id>"`.
6. Log one line to stderr on any failure; exit 0 regardless. `LOCK_BUSY` from
   the store is retried once after 200 ms, then given up (the freeze engine's
   fallback `upsert` covers a missed record).

## Install surface (every site is a deliverable)

- `seed/claude_settings.hooks.json` — `{"hooks":{"SessionStart":[{"matcher":"startup|resume","hooks":[{"type":"command","command":"$CLAUDE_PROJECT_DIR/.aitask-scripts/aitask_session_hook.sh","timeout":10}]}]}}`.
- `seed/codex_config.seed.toml` — the `[hooks]` shape t1705_1 proved (or a
  documented no-op if unsupported).
- `install.sh` — `install_seed_claude_hooks()` beside
  `install_seed_claude_settings()` (:718-729), called before `rm -rf seed`
  (:1341-1342); add `.claude/settings.json` and the hook script's path to the
  framework-path list (:1006-1019) **and** its twin
  `_ait_framework_paths()` in `aitask_setup.sh` (:3387-3404).
- `aitask_setup.sh` — `ensure_agent_config_seeds()` pair (:2237-2243); a
  new `merge_claude_hooks()` beside `merge_claude_settings()` (:2479-2529)
  that merges **only** `hooks.SessionStart`, deduping by `matcher` +
  `command`, preserving every other key and every other hook verbatim;
  `setup_claude_code()` (:2530-2575) copies-if-absent / merges-if-present
  `.claude/settings.json`; `setup_codex_cli()` step 3 (:2790-2802) — verify
  `toml_serialize` (:2601-2655) emits the `[hooks]` shape exactly, extend it
  if not; both paths idempotent across repeated `ait setup`.
- `.github/workflows/release.yml` (:85-96) — the hook script ships under
  `.aitask-scripts/` (already in the tarball); confirm the seed file is.
- Fallback resolver `lib/agent_sessions.py::newest_transcript_for(root,
  agent_kind)` — newest `~/.claude/projects/<escaped-cwd>/*.jsonl` (Claude)
  / newest under `~/.codex/sessions/` whose cwd matches (Codex) — used by
  the freeze engine when the store has no session id.

## Post-phase (risk mitigation, inline — `fresh_install_hook_smoke`)

`tests/test_session_hook_install.sh`: (a) `bash install.sh --dir <scratch>`
+ `ait setup` non-interactive → assert the SessionStart entry in
`<scratch>/.claude/settings.json` and the `[hooks]` block in
`.codex/config.toml`; (b) **preservation**: seed the scratch project with a
user `settings.json` carrying an unrelated `PreToolUse` hook and a foreign
`SessionStart` hook, and a `config.toml` with user tables/comments-free
content; run setup; assert both user hooks survive byte-for-byte in JSON and
the user TOML tables survive; (c) **idempotency**: run `ait setup` three
times; assert exactly one aitasks `SessionStart` entry and one `[hooks]`
entry; (d) the hook's own unit tests feed the t1705_1 fixture payloads
through the script with a fake `ait_tmux` and a fake
`aitask_agent_sessions.sh` on `PATH`, asserting the exact `upsert` argv for:
plain start, `@aitask_record` present, restore env present, no `$TMUX_PANE`
(no call), store `LOCK_BUSY` (one retry, exit 0).

## Key files

- **New** `.aitask-scripts/aitask_session_hook.sh`, `seed/claude_settings.hooks.json`,
  `tests/test_session_hook.sh`, `tests/test_session_hook_install.sh`.
- **Edit** `seed/codex_config.seed.toml`, `install.sh`, `.aitask-scripts/aitask_setup.sh`,
  `.aitask-scripts/lib/agent_sessions.py` (fallback resolver), `.claude/settings.json`
  (this repo's own copy gains the SessionStart entry beside the PreToolUse guard).

## Reference patterns

- `.claude/settings.json` + `.claude/hooks/guard_live_tmux.py` — the only
  existing hook (JSON shape, stdlib-only, always exit 0).
- `aitask_setup.sh` `merge_claude_settings` (:2479), `merge_codex_settings`
  (:2576-2664), `setup_shadow_store_gitignore` (:2424-2452, the idempotent
  installer template), `ensure_agent_config_seeds` (:2229-2273).
- `aidocs/framework/aitasks_extension_points.md` §"Test the full install
  flow for setup helpers" — `install.sh` deletes `seed/`; grep
  `install_seed_X` before reading `aitasks/metadata/X`.
- `.aitask-scripts/lib/tmux_exec.sh` — `ait_tmux`; never bare `tmux`
  (`tests/test_no_raw_tmux.sh` scans `.aitask-scripts/`).
- Allow-list rule: the hook is not skill-invoked → **no** entries in
  `.claude/settings.local.json` / codex rules / opencode config.

## Verification

```bash
bash tests/test_session_hook.sh
bash tests/test_session_hook_install.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_guard_live_tmux.sh
shellcheck .aitask-scripts/aitask_session_hook.sh
bash install.sh --dir /tmp/claude-1000/scratch_hooks && (cd /tmp/claude-1000/scratch_hooks && ./ait setup </dev/null && cat .claude/settings.json .codex/config.toml)
```
No tmux-stress; the hook's tmux calls are read-only `display-message` /
`set-option -p` on the caller's own pane.
