---
Task: t1705_3_session_id_capture_hooks.md
Parent Task: aitasks/t1705_frozen_codeagents_session_store_and_viewer_tui.md
Sibling Tasks: aitasks/t1705/t1705_1_*.md, aitasks/t1705/t1705_2_*.md, aitasks/t1705/t1705_4_*.md … aitasks/t1705/t1705_10_*.md
Archived Sibling Plans: aiplans/archived/p1705/p1705_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5 @ 2026-09-07 13:48
---

# t1705_3 — Session-id capture hooks

## Context

Ships the `SessionStart` hook that binds every launched code agent to its
store record (t1705_2) and makes `ait setup` install it into every project.
This is a **new install surface** — see the task file for the survey (no
`.claude/settings.json` seeding exists; `merge_claude_settings` is
`permissions.allow`-only; Codex has no `[hooks]` precedent and
`toml_serialize` is hand-rolled). t1705_1's findings decide the Codex
mechanism; if Codex hooks proved unavailable, ship the Claude side, make the
Codex seed a documented no-op, and record "codex = re-pick only" in the
hook header and in the PINNED block copy below. The PINNED contracts (end
of file) fix what the hook writes.

## Plan verification (2026-09-07) — what changed

Re-verified against the tree at `b669858ab` (t1705_2 landed). Every line
reference in `## Files` was re-checked and still resolves. Findings that
**change the plan**, each folded into the steps below:

- **V1 — `toml_serialize` needs NO extension.** Step 4(d) left this open. Ran
  the shipped serializer (`aitask_setup.sh:2626-2654`) over the real
  `.codex/config.toml` ⊕ seed ⊕ a `[hooks]` block: it emits
  `[hooks]` / `[[hooks.SessionStart]]` / `[[hooks.SessionStart.hooks]]`, and
  `tomllib` re-parses that to the exact nested shape, with the existing
  `[[rules.prefix_rules]]` entries intact. The step becomes "assert the
  round-trip in a test", not "extend the serializer".
- **V2 — the hooks install gets its OWN consent prompt, in its own function.**
  A `SessionStart` hook is arbitrary code the framework causes to run at every
  agent launch, in a file (`.claude/settings.json`) the framework does not
  currently own. That is a materially larger ask than the permission-allowlist
  entries `setup_claude_code` handles, so **`ait setup` must ask before
  installing it** (user decision, 2026-09-07).

  It must equally **not** be folded into `setup_claude_code()`: that function
  early-`return`s when `aitasks/metadata/claude_settings.seed.json` is absent
  and is gated behind `Install these Claude Code permissions? [Y/n]` — so a
  project without the permissions seed, or a user who declines *permissions*,
  would never even be **offered** the hook. The two consents are about
  different things and must be asked separately.

  ⇒ new `setup_claude_hooks()`, called unconditionally from
  `setup_code_agents()` beside `setup_claude_code`, carrying its own prompt.
  Both prompt conventions follow the house shape used by `setup_claude_code`
  and `setup_codex_cli` (user decisions, 2026-09-07):
  - **non-interactive → auto-accept `Y`**, with the standard
    `info "(non-interactive: auto-accepting default)"` line;
  - **no persistence** — a decline is not remembered; the next `ait setup`
    asks again. No new config field, no new drift surface.
- **V3 — the hook must resolve the tmux socket from `$TMUX`.** `ait_tmux`
  defaults to `-L ait` when `AITASKS_TMUX_SOCKET` is unset, but a tmux server
  hands panes the environment it captured at server start, so the variable is
  **not** reliably present in an agent's env. The hook talks to the server its
  own pane lives on: when `AITASKS_TMUX_SOCKET` is unset **and** `$TMUX` is
  set, export `AITASKS_TMUX_SOCKET="$(basename "${TMUX%%,*}")"` before
  sourcing the gateway. Setting it only when unset preserves the test-harness
  escape hatch (`require_isolated_tmux` exports it set-but-empty).
- **V4 — the live test does NOT need `require_clean_ait_server`.** Every tmux
  call the hook makes is gateway-routed (`display-message -p`, `set-option
  -p`) and it arms no `pane-died` / `remain-on-exit` hook, so it is in
  `require_isolated_tmux`'s "isolate, never refuse" class
  (`tests/lib/tmux_isolation.sh:26-36`). The A8 observing test can therefore
  run from inside tmux on a throwaway server — **no Step-0 preflight, no
  abort**, unlike sibling t1705_1.
- **V5 — a new seed file is a two-sided manifest change.**
  `tests/test_seed_manifest_drift.sh` derives the install-flow manifest and the
  source-tree manifest from live source and fails when they disagree, and the
  install side is **position-sensitive** (an installer wired after
  `rm -rf seed` is dead code). Both wirings are already in the steps; the drift
  test joins `## Verification`.
- **V6 — the Codex `command` stays repo-relative.** `.codex/config.toml` is a
  **tracked** file (`git ls-files .codex/`) and `_ait_framework_paths()`
  commits `.codex/`, so substituting an absolute project path would commit a
  developer's home directory. Claude has `$CLAUDE_PROJECT_DIR`; Codex has no
  equivalent, so the seed carries a relative command and the header records
  that limitation.
- **V7 — `newest_transcript_for` is confirmed absent** from
  `lib/agent_sessions.py` (only `transcript_path` as a record field), so step 6
  is genuine new work.
- **V8 — release tarball already ships both artifacts.** `release.yml` tars
  `seed/` and `.aitask-scripts/` wholesale, so the `## Files` "Check" item
  resolves to *no change needed*.

### Review-round findings (C1–C5), all verified against the store code

A review of the amended step 1 surfaced five defects **in the plan's own hook
pseudocode**. Each was checked against `lib/agent_sessions.py` before being
accepted; all five are now folded into step 1 and the test list.

- **C1 (blocking) — the stamp extraction was wrong even though the stamp was
  present.** A8 compliance was added earlier in this pass, but as
  `case "$out" in UPSERTED:*)`. `run_sessions_py` captures python's stdout
  **and** stderr into one stream, so any warning ahead of the `UPSERTED:` line
  defeats a prefix test — and a skipped stamp is silent, surfacing only as the
  freeze engine creating a second record. Now a line-anchored `sed` match on
  `UPSERTED:<8hex>|`, with positive and negative test cases including the
  stderr-first regression.
- **C2 (blocking) — whitespace-split payload parsing corrupted every field
  after a space.** `read -r sid tpath cwd src` on a space-joined python line
  shifts fields the moment `cwd` or `transcript_path` contains a space
  (`/Users/me/My Project`), corrupting root discovery and the upsert argv.
  Now NUL-delimited, with a spaces-in-paths test asserting on the argv array.
- **C3 (blocking) — an empty session id could blank a stored one.** Confirmed
  in the store: `_arg` returns `""` (not `None`) for `--session-id ""`, and
  `_apply_upsert_fields` (`agent_sessions.py:699-700`) writes any non-`None`
  value — so a malformed or provisional payload overwrites a good
  `codeagent_session_id` with `""`, downgrading a resumable frozen agent to
  re-pick only. Worse during a restore: the ack path compares
  `(session_id or "") != rec.codeagent_session_id` and would persist
  `<nonce>:session_mismatch`, aborting a legitimate restore. A blank id is now
  a logged no-op — no upsert, no pane option.
- **C4 (blocking) — the transcript-layout probe was not a prerequisite.** The
  `verify_transcript_layouts` pre-phase existed but did not say that step 6
  depends on it, nor name the resolver's own test cases. The install suite never
  calls the resolver, so a wrong escape rule ships green. The pre-phase now
  states the dependency and pins selection / no-match / multiple-candidate
  ordering.
- **C5 (follow-up, taken now) — `--session` was captured but not passed.** The
  hook read `sess` from `display-message` and dropped it, diverging from A6.
  Now passed and asserted in the exact-argv test.

Unchanged and re-confirmed: the `upsert` argv (`aitask_agent_sessions.sh:35-38`
— `--session <name>` present per A6), the exit codes (`3` = `LOCK_BUSY`),
`ait_stamp_record` and the `AIT_*_OPTION` spellings in `lib/agent_sessions.sh`,
`_walk_up_to_aitasks` (`lib/agent_launch_utils.py:366`), the
`AITASK_AGENT_STRING` export (`aitask_codeagent.sh:611`), `_TASK_ID_RE`
(`monitor_core.py:3587`), the fixture statuses (`claude` = `captured`, `codex` =
`provisional`), and `install.sh --dir`.

## Files

- **New** `.aitask-scripts/aitask_session_hook.sh`
- **New** `seed/claude_settings.hooks.json`
- **Edit** `seed/codex_config.seed.toml` (the `[hooks]` shape from t1705_1)
- **Edit** `install.sh` — `install_seed_claude_hooks()` (beside :718-729), call site (before the `rm -rf seed` at :1342), framework-path list (:1006-1019)
- **Edit** `.aitask-scripts/aitask_setup.sh` — `ensure_agent_config_seeds` pair (:2238-2243), new `merge_claude_hooks()` (beside :2479), **new `setup_claude_hooks()`** called from `setup_code_agents()` (**V2** — *not* a branch inside `setup_claude_code()` :2530-2575), `setup_codex_cli()` step 3 (:2789-2801), `_ait_framework_paths()` (:3387-3404)
- **Edit** `.claude/settings.json` (this repo) — add the SessionStart entry beside the PreToolUse guard
- **Edit** `.aitask-scripts/lib/agent_sessions.py` — `newest_transcript_for(root, agent_kind)`
- **New tests** `tests/test_session_hook.sh`, `tests/test_session_hook_live.sh`, `tests/test_session_hook_install.sh`
- **New test helper** `tests/lib/pty_drive.py` — stdlib PTY driver; the consent-prompt **decline** branch is unreachable without it (see post-phase (e))
- **Edit** `tests/test_agent_instructions.sh:930` — the "tests/ has no pty harness" note, now retired
- **No change** `.github/workflows/release.yml` — **V8**: the tarball already tars `seed/` and `.aitask-scripts/` wholesale
- **No change** `aitask_setup.sh` `toml_serialize` (:2626-2654) — **V1**: verified sufficient

## Implementation steps

### Pre-phase (risk mitigations)

**`verify_transcript_layouts`** — run **before** step 6 writes
`newest_transcript_for`, and before committing to its escape rule. Step 6's
Claude rule (`~/.claude/projects/<escaped-cwd>/`, "`/` → `-`") and Codex probe
(`~/.codex/sessions/**`, first JSON line's `cwd`) are both **guesses**, and a
wrong guess returns `("", "")` — indistinguishable from "no session". Establish
the ground truth first, the way t1705_1 established the hook payloads:

1. Enumerate the real stores on this machine — `ls ~/.claude/projects/` and
   `find ~/.codex/sessions -name '*.jsonl' | head` — and derive the **actual**
   directory-name transform from a known project path (this repo's own realpath
   is a ready-made positive control: its escaped directory must exist).
2. Confirm the Codex side by reading the first JSON line of one rollout file
   and checking which key actually carries the working directory (the fixture's
   `transcript_path` shape says `sessions/<yyyy>/<mm>/<dd>/rollout-<ts>-<id>.jsonl`
   — assert that layout rather than assuming a flat `**` glob is enough).
3. Commit the findings as `tests/data/session_hooks/transcript_layout.json`
   (same redaction contract as the sibling fixtures — no `/Users/…`, no user
   name; record the *rule*, not a personal path) plus a README section, and
   write step 6 against the fixture. If a layout cannot be established for an
   agent, record an **explicit skip** for it and make `newest_transcript_for`
   return the not-supported reason for that agent — never a silent `("", "")`.

**This pre-phase is a prerequisite for step 6, not a parallel nicety.** Without
it the resolver's Claude escape rule and Codex `cwd`-match are assumptions that
**every hook-install test still passes around** — the install suite never calls
the resolver — so a wrong rule ships green and surfaces only as restores with no
session id, in the exact place (interactive Codex) where the fallback is the
*only* mechanism. Test the resolver against a synthesized tree built from the
fixture's rule, covering all three behaviours:

- **selection** — with several transcripts present, the newest by mtime for the
  requested root is the one returned;
- **no-match** — a present-but-empty store, an absent store, and a store holding
  only *other* projects' transcripts each return the empty pair with the
  distinguishing reason (`no_store_dir` / `no_project_dir` / `no_match`), never
  a bare `("", "")`;
- **multiple-candidate ordering** — deterministic and documented when two
  transcripts share an mtime (tie-break on name, so a test cannot flake and a
  reader knows which wins).

1. **Hook script** (`aitask_session_hook.sh`, `#!/usr/bin/env bash`, `set -uo pipefail` — **not** `-e`; every failure path must reach `exit 0`):
   ```bash
   [ -n "${TMUX_PANE:-}" ] || exit 0
   # V3: talk to the server THIS pane lives on. A tmux server hands panes the
   # environment it captured at server start, so AITASKS_TMUX_SOCKET is not
   # reliably present here and the gateway's `-L ait` default can address the
   # wrong server. Set it ONLY when unset — require_isolated_tmux exports it
   # set-but-empty, and that escape hatch must survive.
   if [ -z "${AITASKS_TMUX_SOCKET+x}" ] && [ -n "${TMUX:-}" ]; then
       export AITASKS_TMUX_SOCKET="$(basename "${TMUX%%,*}")"
   fi
   payload=$(cat)                                   # stdin JSON
   # C2: NUL-delimited, NOT whitespace-split. `read -r a b c d` on a
   # space-joined line silently shifts every field when cwd or
   # transcript_path contains a space — `/Users/me/My Project` is enough, and
   # the Claude escape rule (`/` -> `-`) preserves the space in the transcript
   # directory name too. NUL is the one separator a path cannot contain.
   fields=()
   while IFS= read -r -d '' f; do fields+=("$f"); done < <(printf '%s' "$payload" | python3 -c '
   import json,sys
   d=json.load(sys.stdin)
   sys.stdout.write("\0".join(str(d.get(k) or "") for k in ("session_id","transcript_path","cwd","source")) + "\0")' 2>/dev/null)
   [ "${#fields[@]}" -eq 4 ] || exit 0              # malformed / unparseable payload
   sid=${fields[0]}; tpath=${fields[1]}; cwd=${fields[2]}; src=${fields[3]}
   # C3: a blank session id is a NO-OP, never an upsert. `--session-id ""` is
   # not None to the store, so _apply_upsert_fields would overwrite a good
   # stored id with "" (agent_sessions.py:699-700) — silently downgrading a
   # resumable frozen agent to re-pick only. Worse during a restore: the ack
   # path compares `(session_id or "") != rec.codeagent_session_id` and would
   # persist `<nonce>:session_mismatch`, aborting a legitimate restore.
   [ -n "$sid" ] || { echo "aitask_session_hook: empty session_id; nothing recorded" >&2; exit 0; }
   root=$(walk_up_to_aitasks "$cwd") || exit 0      # small loop: ancestor with aitasks/metadata/project_config.yaml
   source "$root/.aitask-scripts/lib/tmux_exec.sh"; source "$root/.aitask-scripts/lib/agent_sessions.sh"
   IFS=$'\t' read -r sess win pane ppid rec < <(ait_tmux display-message -p -t "$TMUX_PANE" \
       "#{session_name}	#{window_name}	#{pane_id}	#{pane_pid}	#{$AIT_RECORD_OPTION}") || exit 0
   op=""; tid=""; [[ $win =~ ^agent-(pick|qa|resume)-([0-9]+(_[0-9]+)?)$ ]] && { op=${BASH_REMATCH[1]}; tid=${BASH_REMATCH[2]}; }
   args=(upsert --root "$root" --window "$win" --pane "$pane" --pane-pid "$ppid"
         --session "$sess" --session-id "$sid" --transcript "$tpath"
         --agent-string "${AITASK_AGENT_STRING:-}" --operation "$op" --task-id "$tid")
   [ -n "$rec" ] && args+=(--id "$rec")
   [ -n "${AITASK_RESTORE_RECORD:-}" ] && args+=(--restore-of "$AITASK_RESTORE_RECORD" --nonce "${AITASK_RESTORE_NONCE:-}")
   out=$("$root/.aitask-scripts/aitask_agent_sessions.sh" "${args[@]}" 2>&1); rc=$?
   if [ "$rc" -eq 3 ]; then sleep 0.2; out=$(... same ...); rc=$?; fi
   [ "$rc" -eq 0 ] || echo "aitask_session_hook: $out" >&2
   # A8/C1: the hook OWNS the pane->record stamp, on a success line ONLY.
   # Match the LINE, not the prefix of $out: the wrapper's run_sessions_py
   # captures python's stdout AND stderr into one stream, so a warning ahead of
   # the UPSERTED: line would make a `case "$out" in UPSERTED:*)` prefix test
   # fail — and a skipped stamp is silent, surfacing only later as the freeze
   # engine creating a SECOND record for an already-recorded agent.
   rid=$(printf '%s\n' "$out" | sed -n 's/^UPSERTED:\([0-9a-f]\{8\}\)|.*$/\1/p' | tail -n1)
   [ -n "$rid" ] && ait_stamp_record "$TMUX_PANE" "$rid"   # re-validates 8-hex, rc 2 otherwise
   ait_tmux set-option -p -t "$TMUX_PANE" "$AIT_AGENT_SESSION_OPTION" "$sid" 2>/dev/null || true
   exit 0
   ```
   The id is extracted from the `UPSERTED:<8hex>|<disposition>` line by
   pattern, so `UPSERT_REFUSED:` / `NONCE_MISMATCH:` / a non-zero exit all
   yield an empty `$rid` and no stamp — the "only on that success line, never
   on a refusal" half of A8. `ait_stamp_record` independently re-validates the
   id (rc 2), so a malformed match cannot reach a pane option that later feeds
   `capture_dir()` and the stand-in command string.

   **Never write to stdout.** A `SessionStart` hook's stdout is injected into
   the agent's context, so the `aitask_agent_sessions.sh` output is captured
   into `$out` (never echoed) and every diagnostic goes to stderr. This is a
   hard contract, asserted in the unit suite.

   `AITASK_RESTORE_MODE` / `AITASK_RESTORE_EXPECT_SESSION` are consumed by
   the store (`--restore-of` looks up `restore_mode` on the record), so the
   hook forwards only record + nonce + the session id it observed. Header
   comment documents the exit-0 contract, the stdout contract, and the Codex
   finding (**V6**: `codex = re-pick only` on the interactive path).
2. **Seed files.** `seed/claude_settings.hooks.json` exactly as in the task
   file (`command` uses `$CLAUDE_PROJECT_DIR`, which Claude Code expands —
   the existing PreToolUse guard is the precedent).
   `seed/codex_config.seed.toml` gains the `[hooks]` block in the shape
   `tests/data/session_hooks/README.md` records as empirically honoured:
   ```toml
   # SessionStart hook — records the codeagent session id into the framework
   # session store (t1705_3). Finding of 2026-09-06 (codex 0.153.4): this fires
   # under `codex exec` but NOT in the interactive TUI, which is the framework's
   # production launch path. Interactive codex sessions therefore capture no
   # session id and restore via re-pick only.
   [[hooks.SessionStart]]
   matcher = "startup|resume"

   [[hooks.SessionStart.hooks]]
   type = "command"
   command = ".aitask-scripts/aitask_session_hook.sh"
   timeout = 10
   ```
   **V6**: the command stays **repo-relative** — `.codex/config.toml` is a
   tracked, framework-committed file and Codex has no `$CLAUDE_PROJECT_DIR`
   equivalent, so an absolute path would commit a developer's home directory.
   Note in the seed comment that the hook additionally requires
   `[projects."<realpath>"] trust_level = "trusted"` in `$CODEX_HOME/config.toml`
   — outside `ait setup`'s remit (it never writes the user's codex home).
3. **`install.sh`.** `install_seed_claude_hooks()` copies
   `seed/claude_settings.hooks.json` → `aitasks/metadata/claude_settings.hooks.json`;
   call it next to `install_seed_claude_settings` (:1322-1336) — **before** the
   `rm -rf "$INSTALL_DIR/seed"` at :1342, which `test_seed_manifest_drift.sh`
   enforces as a position contract (**V5**); add `.claude/settings.json` to the
   framework path list (:1006-1019) with the sync comment.
4. **`aitask_setup.sh`.** (a) `ensure_agent_config_seeds` pair
   `"claude_settings.hooks.json:claude_settings.hooks.json"` — the source-tree
   half of the manifest **V5** requires. (b)
   `merge_claude_hooks <existing> <seed>`: python3 — load both; for each
   seed `hooks.SessionStart[*]` group, find an existing group with the same
   `matcher`; append any seed hook whose `command` is not already present
   (compare after `$CLAUDE_PROJECT_DIR` normalisation); create the group if
   missing; write back with `json.dumps(existing, indent=2)` **touching no
   other key**. Mirror `merge_claude_settings`'s jq-or-python3-or-warn
   availability ladder (:2481-2516) — but jq is optional there and the python3
   branch is the one to implement first; a box with neither warns and skips,
   exactly as today. (c) **V2 — new `setup_claude_hooks()`**, called
   unconditionally from `setup_code_agents()` beside `setup_claude_code`, **not**
   a branch inside it (see V2 for why the two consents must be separate).
   Body, in order:
   - seed `aitasks/metadata/claude_settings.hooks.json` missing → `return`;
   - **consent prompt**, modelled verbatim on `setup_claude_code`'s
     (:2560-2575). Print what is being installed and what it does *before*
     asking — the hook's path, that it runs at every Claude Code session start
     in this project, that it records the session id so a frozen agent can be
     restored, and that it never blocks or fails a session (exit 0 always):
     ```
     info "aitasks can install a Claude Code SessionStart hook:"
     info "  .aitask-scripts/aitask_session_hook.sh"
     info "It runs when a Claude Code session starts in this project and records"
     info "the session id, so a frozen agent can later be restored. It writes no"
     info "output to the session and always exits 0."
     if [[ -t 0 ]]; then printf "  Install the session hook? [Y/n] "; read -r answer
     else info "(non-interactive: auto-accepting default)"; answer="Y"; fi
     case "${answer:-Y}" in [Yy]*|"") ;; *) info "Skipped session hook."; return ;; esac
     ```
     The answer is **not persisted** — the next `ait setup` asks again
     (house convention; no new config field).
   - `.claude/settings.json` absent → `mkdir -p .claude` + `cp` seed;
     present → `merge_claude_hooks`.
   (d) `setup_codex_cli` step 3 needs **no code
   change** — `merge_codex_settings`'s `deep_merge` + `toml_serialize` already
   round-trip the `[hooks]` shape (**V1**, verified against the real
   `.codex/config.toml`), and `deep_merge`'s `str(item)` list dedup makes a
   repeat `ait setup` a no-op. What this step adds is the **assertion** in
   `tests/test_session_hook_install.sh`. **Consent (V2)**: the codex hook rides
   inside `.codex/config.toml`, which is already behind `setup_codex_cli`'s own
   `Install Codex CLI skills and config? [Y/n]` prompt (:2748-2760) — so it is
   consented for, but that prompt does not currently say so. **Extend its
   wording** to name the SessionStart hook alongside the skills and config
   (one added `info` line before the prompt), rather than adding a second
   prompt inside an already-gated function. (e) `_ait_framework_paths()` gains
   `.claude/settings.json` (its twin in `install.sh` is 3's third item).
5. **This repo's `.claude/settings.json`** — add the entry by hand (the
   guard hook stays first). The file is already tracked here, but it is **not**
   yet in either framework-path list, so 3 and 4(e) are what make `ait setup`
   own it downstream.
6. **Fallback resolver** `newest_transcript_for(root, agent_kind)` in
   `lib/agent_sessions.py`, written **against the pre-phase fixture, not
   against the guesses below**: Claude → newest `*.jsonl` under
   `~/.claude/projects/<escaped-cwd>/`; Codex → newest file under
   `~/.codex/sessions/<yyyy>/<mm>/<dd>/` whose first JSON line carries a
   matching working directory. Returns `(session_id, transcript_path)`, or the
   empty pair **with a reason** (see the post-phase
   `fallback_resolver_reports_why`).
7. **Tests.** `tests/test_session_hook.sh`: fake `ait_tmux` (prints a
   canned `display-message` line) and fake `aitask_agent_sessions.sh`
   (records argv, returns 0 / 3 / 4 per env) on `PATH`; feed
   `tests/data/session_hooks/{claude,codex}_sessionstart.json`; assert the
   exact `upsert` argv for: plain start; `@aitask_record` present (`--id`);
   `AITASK_RESTORE_*` present (`--restore-of --nonce`); missing
   `$TMUX_PANE` (no call, exit 0); `LOCK_BUSY` (two calls, exit 0);
   malformed JSON (no call, exit 0); `set-option` always attempted after a
   successful upsert. Model the stub harness on
   `tests/test_agent_sessions_stamp.sh` — a recording `tmux` first on `PATH`,
   no live server. Cases added by this verification pass, one per finding:

   - **C1 stamp, positive and negative.** `ait_stamp_record` is called with
     exactly the upserted id on an `UPSERTED:<id>|…` line, and **not called**
     on `UPSERT_REFUSED:`, `NONCE_MISMATCH:`, or a non-zero exit. Plus the
     regression the line-match exists for: a stub that emits a stderr warning
     **before** the `UPSERTED:` line must still stamp (a prefix test fails
     here; a line match passes).
   - **C2 paths with spaces.** A payload whose `cwd` is `/tmp/x/My Project`
     and whose `transcript_path` contains a space must produce an `upsert`
     whose `--root` and `--transcript` are single, intact arguments. Assert on
     the recorded argv **array**, not a joined string — a joined comparison
     cannot distinguish one argument containing a space from two arguments.
     Add a second payload with a `'` and a `$` in the path for good measure.
   - **C3 empty session id.** A payload with `"session_id": ""`, one with the
     key absent, and one with `null` each produce **no `upsert` call at all**,
     **no `set-option` for `@aitask_agent_session`**, one stderr line, and exit
     0. This is the case that would otherwise blank a stored id.
   - **C5 `--session`.** The exact-argv assertion pins `--session <name>` from
     the `display-message` round trip (A6), alongside `--root` / `--window` /
     `--pane` / `--pane-pid`.
   - **stdout is empty on every path** — the SessionStart-injects-stdout
     contract.

   `tests/test_session_hook_install.sh` = the post-phase below.

   **`tests/test_session_hook_live.sh` — the A8 observing test (new file).**
   `test_agent_sessions_stamp.sh`'s header assigns it here explicitly: "is the
   option really set on a real pane after a real hook fire" belongs to this
   child's suite. Source `tests/lib/tmux_isolation.sh` and call
   **`require_isolated_tmux` only** — **V4**: every tmux call the hook makes is
   gateway-routed and it arms no `pane-died` / `remain-on-exit` hook, so it is
   in the "isolate, never refuse" class and **needs no
   `require_clean_ait_server` and no outside-tmux preflight**. Spawn a real
   pane on the isolated server, run the hook in it with the `captured` fixture
   on stdin and `AITASKS_AGENT_SESSIONS_FILE` pointed at a scratch file, then
   assert with real `display-message -p`: `@aitask_record` equals the id in the
   store's `list` output, and `@aitask_agent_session` equals the fixture's
   `session_id`. A second fire in the same pane must reuse the record (one
   `SESSION:` line, `--id` path) — the duplicate-record regression A8 warns
   about. No agent binary is required.

   **BRANCH ON `_fixture_status` — do NOT feed both fixtures in as if each
   were a successful payload** (amended by the t1705_1 spike; see
   `## Spike findings (t1705_1) — PINNED` in the parent plan). Each fixture
   declares one of three statuses with different required and forbidden
   fields, and an `unsupported` fixture carries **no payload key at all**, so
   the argv assertions above are meaningless for it. Read
   `tests/data/session_hooks/schema.json` (validator:
   `tests/lib/validate_session_hook_fixtures.py`) and dispatch:

   - **`captured`** → run the full `upsert` argv assertions as written above.
   - **`unsupported`** → assert the *opposite* contract for that agent (no hook
     installed, no `upsert` call) and record an **explicit skip** — never a
     pass by absence.
   - **`provisional`** → run the assertions as **advisory** only, and do not
     treat `schema.json` as settled for that agent.

   As of the spike: `claude_sessionstart.json` is `captured` (interactive,
   authoritative) and `codex_sessionstart.json` is
   `provisional(no_interactive_capture)`. **Codex hooks do work** — a
   project-level `.codex/hooks.json` in the Claude-compatible shape is honoured
   when the project is trusted — but `SessionStart` fires only under
   `codex exec`, never in the interactive TUI, which is the framework's
   production launch path. So this child must ship the codex hook *and* treat
   the interactive path as yielding no session id (fallback: re-pick), rather
   than assuming either that codex has no hooks or that installing one is
   sufficient.

### Post-phase (risk mitigations)

**`fallback_resolver_reports_why`** — make step 6's empty answer diagnosable.
`newest_transcript_for` returns a third value (or raises a typed
`TranscriptLookupMiss`) carrying one of `no_store_dir` / `no_project_dir` /
`no_match` / `unsupported_agent`, and every call site logs it. The failure this
prevents is precise: a wrong escape rule and a genuinely session-less agent are
today the same `("", "")`, so a layout regression after a Claude Code release
would look exactly like normal operation and be discovered only as "freeze keeps
producing records with no session id". The pre-phase pins today's layout; this
makes tomorrow's drift audible.

**`fresh_install_hook_smoke`** —
`tests/test_session_hook_install.sh`:
(a) `bash install.sh --dir <scratch>` then `(cd <scratch> && ./ait setup </dev/null)`;
assert `jq '.hooks.SessionStart[0].hooks[0].command' .claude/settings.json`
names `aitask_session_hook.sh` and `python3 -c 'import tomllib…'` finds the
`[hooks]` block. (b) **Preservation**: before setup, write a
`.claude/settings.json` with a user `PreToolUse` hook and a foreign
`SessionStart` group (different `matcher`) plus a top-level `"env"` key;
write a `.codex/config.toml` with a user `[profiles.x]` table; run setup;
assert every user item survives (JSON: deep-equal on the user subtrees;
TOML: parsed table equality). (c) **Idempotency**: run `./ait setup` three
times; assert exactly one aitasks SessionStart hook and one `[hooks]`
entry. (d) Record the known loss — TOML comments are dropped by
`toml_serialize` — in the test's header and in the docs child's
"Session hooks" section.

**(e) Consent (V2) — and the PTY harness it needs.**

⚠️ **A scripted stdin cannot test this.** Every setup prompt is gated on
`[[ -t 0 ]]`, so a pipe takes the *auto-accept* branch and never reads the
answer. `tests/test_agent_instructions.sh:930` records the consequence as a
standing gap: *"The legacy-mode DECLINE branch cannot be driven at all: it needs
`[[ -t 0 ]]` true and tests/ has no pty harness."* Shipping a consent prompt
whose **decline** path no test can reach would be shipping the consent in name
only — so this post-phase builds the missing harness first.

- **New `tests/lib/pty_drive.py`** — a ~40-line stdlib helper (`pty.openpty` +
  `subprocess` with the slave fd as stdin/stdout, parent writes the scripted
  answers and reads the transcript). Python's `pty` module is stdlib on both
  macOS and Linux, so this needs no new dependency and no `expect`. Interface:
  `python3 tests/lib/pty_drive.py --answers 'n,Y' -- <cmd> [args...]`, printing
  the child's transcript and exiting with its status. It is a **general**
  helper, deliberately not hook-specific: it also retires the documented gap
  above, and the note at `test_agent_instructions.sh:930` should be updated in
  this commit to point at it.

Then the three consent cases — none of which (a) can see, since (a) is
non-interactive and auto-accepts everything:
- **Declining permissions must not suppress the hook offer.** Drive `ait setup`
  under the PTY answering `n` to the *permissions* prompt and `Y` to the *hook*
  prompt; assert the SessionStart entry lands. This is the exact failure the
  hooks-inside-`setup_claude_code` shape would have shipped.
- **Declining the hook prompt installs nothing and breaks nothing.** Answer `n`
  to the hook prompt; assert `.claude/settings.json` carries no aitasks
  SessionStart entry (and, when the file pre-existed, is byte-identical), that
  setup still exits 0, and that the later phases (`commit_framework_files`)
  complete.
- **A declined hook is re-offered.** Run setup a second time, still answering
  `n`; assert the prompt fires again and still installs nothing — the
  house-convention no-persistence contract, pinned so a later "remember the
  decline" change is a deliberate decision rather than a silent drift.

**Cheaper fallback if the PTY harness proves troublesome on either platform:**
source `aitask_setup.sh --source-only` (:4339) and call `setup_claude_hooks`
directly under the PTY, rather than driving a whole `ait setup`. That still
exercises the real prompt and the real merge, and keeps the case runnable; only
the "declining permissions does not suppress the hook" ordering case genuinely
needs the full run.

## Verification

```bash
bash tests/test_session_hook.sh
bash tests/test_session_hook_live.sh
bash tests/test_session_hook_install.sh
bash tests/test_seed_manifest_drift.sh              # V5: both manifest sides wired
bash tests/test_agent_sessions_stamp.sh             # A8 argv contract still holds
bash tests/test_no_raw_tmux.sh
bash tests/test_guard_live_tmux.sh
bash tests/test_setup_agent_config_seeds.sh
bash tests/test_agent_instructions.sh               # setup_code_agents call graph + pty note
bash tests/test_setup_verify_venv_imports.sh        # setup still boots
bash tests/test_frozen_standin_spike.sh             # fixtures still validate
shellcheck .aitask-scripts/aitask_session_hook.sh .aitask-scripts/aitask_setup.sh install.sh
bash tests/run_all_python_tests.sh --test-dir tests   # agent_sessions.py changes
```

Step 9 (Post-Implementation) then handles cleanup, archival of
`aitasks/t1705/t1705_3_*.md` + this plan, and the merge to `main`.

**No outside-tmux preflight is required for this child** (**V4**) — unlike
sibling t1705_1, whose live suites call `require_clean_ait_server`. Every tmux
call here is gateway-routed and read-only-ish (`display-message -p`,
`set-option -p` on the caller's own pane), so `require_isolated_tmux` alone is
the sufficient guarantee and the suite runs from inside tmux.

## Risk

Levels below are the **post-augmentation** reassessment (both confirmed inline
mitigations are already part of the plan above), per `risk-evaluation.md`'s
reassessment note. The reassessment changed neither level: goal-achievement's
one `high`-severity bullet is now covered on both sides — the pre-phase pins the
layout before the code is written, the post-phase makes a later drift audible —
but the dimension stays `medium` because the codex-interactive limitation and
the untestable restore-ack coupling are unmitigated by construction (upstream
limitation and sibling coupling respectively, both accepted). Code-health stays
`medium`: the install-flow blast radius is unchanged, and the two additions are
a committed fixture plus a widened return value in a brand-new function.

### Code-health risk: medium
- **The install flow is the blast radius.** Two of the six edits land in
  `install.sh` and `aitask_setup.sh`, which run in every downstream project on
  every `ait setup`. `merge_claude_hooks` rewrites a user's tracked
  `.claude/settings.json`; a merge bug drops their `PreToolUse` guards, foreign
  `SessionStart` groups, or top-level keys, and the loss is silent because the
  file still parses. · severity: medium · → mitigation: inline post-phase
  `fresh_install_hook_smoke` (cases (b) preservation and (c) idempotency exist
  precisely for this)
- **`ait setup` starts committing `.claude/settings.json`.** Adding it to both
  framework-path lists means setup now git-adds a file downstream users may be
  keeping machine-specific hooks in. It is the project-scoped (shared) settings
  file by Claude Code convention — `settings.local.json` is the private one — so
  this is the intended lifecycle, but it is a new ownership claim over a file the
  framework did not previously touch. The **V2 consent prompt** is what makes
  the claim explicit rather than silent; a declined project keeps the framework
  out of the file entirely. · severity: low · → mitigation: none (accepted;
  consent prompt + documented in the docs child's "Session hooks" section)
- **The consent prompt is only as good as its decline path, which nothing
  could test before this task.** Adding a prompt whose `n` branch no suite
  reaches would be consent theatre — hence the `tests/lib/pty_drive.py` harness
  in post-phase (e). That harness is itself new shared test infrastructure
  touching one existing file's comment, but it is additive and its failure mode
  is a red test, not a broken install. · severity: low · → mitigation: inline
  post-phase `fresh_install_hook_smoke` (case (e))
- **The hook runs on every session start of every agent.** Its correctness
  contract is exit-0-always, which the unit suite pins, but its *latency*
  contract is not: a tmux round trip plus a store write under a 2 s lock
  timeout, inside Claude Code's 10 s hook budget. A wedged tmux server or a
  contended store makes every session start pay for it. Bounded — the store's
  `LOCK_BUSY` retry is a single 200 ms sleep and the whole path is
  timeout-guarded upstream. · severity: low · → mitigation: none (accepted)
- **The hook's own text has now yielded five defects across two review
  rounds** (C1–C5), three of them silent-corruption class: a dropped pane stamp,
  field-shifting on any path containing a space, and a blanked session id that
  also aborts a legitimate restore. None was visible from the plan's prose —
  each needed a read of `lib/agent_sessions.py` to confirm. The script is short
  and its failure mode is *quiet*, which is exactly the shape that survives
  review; the unit suite's per-finding cases are the durable answer, and the
  implementation should treat "this looks obviously right" as a warning sign in
  this file specifically. · severity: medium · → mitigation: none (the C1–C5
  test cases in step 7 are the answer, and they are already in the plan)
- Otherwise the change is additive: one new script with no existing callers,
  one new seed, one new `setup_claude_hooks()` beside an existing sibling, and
  **V1** removed the one edit that would have touched shared serialization
  logic (`toml_serialize` needs no change). · severity: low · → mitigation: none

### Goal-achievement risk: medium
- **The fallback resolver is specified against unverified filesystem layouts,
  and it fails silently.** Step 6's `newest_transcript_for` encodes the Claude
  `~/.claude/projects/<escaped-cwd>/` escape rule as a guess ("`/` → `-`, verify
  against a real dir") and the Codex `~/.codex/sessions/**` first-JSON-line-`cwd`
  probe likewise. If either is wrong it returns `("", "")` — which is
  indistinguishable from "this agent genuinely has no session", the exact case
  the fallback exists to rescue. The freeze engine (t1705_4) would then create
  records with no session id and nobody would learn why. · severity: high
  · → mitigation: inline pre-phase `verify_transcript_layouts`, inline
  post-phase `fallback_resolver_reports_why`
- **Half the supported-agent surface cannot meet the goal, by upstream
  limitation.** t1705_1 established that Codex fires `SessionStart` only under
  `codex exec`, never in the interactive TUI — the framework's production launch
  path. Shipping the codex hook is still right (it is real, it works under
  `exec`, and a future codex release may extend it), but interactive codex
  sessions capture no session id and restore via re-pick only. This narrows
  what t1705_4/t1705_5 inherit relative to the parent's §A. Known, evidenced and
  documented rather than a plan defect. · severity: medium · → mitigation: none
  (accepted; recorded in the hook header, the codex seed comment, and the docs
  child)
- **The restore-ack path cannot be end-to-end tested in this child.** The hook's
  `--restore-of` / `--nonce` forwarding is written against §D, which t1705_5 has
  not implemented. The unit suite pins the argv shape from environment variables
  nothing yet sets, so a mismatch with the eventual coordinator surfaces only in
  t1705_5. Bounded: the store side of the contract is already implemented and
  tested by t1705_2. · severity: medium · → mitigation: none (accepted — the
  coupling is the sibling's to verify)
- **OpenCode is not addressed.** The parent's §A names claude and codex only, so
  this is in scope by omission rather than a gap, but no OpenCode hook surface
  was investigated and OpenCode agents will silently have no session id.
  · severity: low · → mitigation: none (accepted)

### Planned mitigations
- timing: pre-phase | name: verify_transcript_layouts | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — fallback resolver specified against unverified layouts | desc: Probe the real ~/.claude/projects and ~/.codex/sessions stores and pin the actual escape rule and file layout as a committed fixture before newest_transcript_for is written.
- timing: post-phase | name: fallback_resolver_reports_why | type: enhancement | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — the same resolver fails silently | desc: Return a reason alongside ("","") distinguishing "no candidate directory" from "directory present, nothing matched" so a wrong layout is diagnosable at the call site.

## Amendments from t1705_2 (store implementation, 2026-09-06)

**A8 — the hook OWNS the `@aitask_record` stamp, and the test that proves it.**
`upsert` cannot stamp the pane: `lib/agent_sessions.py` is tmux-free and
`tests/test_no_raw_tmux.sh` permits raw `tmux` only from the two gateways. So
after the hook's `aitask_agent_sessions.sh upsert` prints `UPSERTED:<id>|…` —
and **only** on that success line, never on a refusal — the hook must call
`ait_stamp_record "$TMUX_PANE" "<id>"` from `lib/agent_sessions.sh`.

This child also owns the **observing** integration test: after a real hook fire,
`@aitask_record` is actually present on the pane and equals the stored record id.
t1705_2 ships only the helper's argv contract and id guard
(`tests/test_agent_sessions_stamp.sh`, no live server); the "is it really set"
assertion needs the live tmux this child already has.

Skipping the stamp is silent: the record stores fine, and the damage appears
later as the freeze engine creating a SECOND record for an agent that was
already recorded.

**A6 — `upsert` now accepts `--session <name>`** (the tmux session name, display
only). Pass it when the hook knows it.

## PINNED contracts (from p1705 — do not re-decide)

Copied verbatim from `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` §A–§D. On any discrepancy the parent plan wins; if a child must deviate, update the parent plan and every sibling plan in the same commit.


#### A. Session store — `lib/agent_sessions.py` + `aitask_agent_sessions.sh`

- Path `~/.config/aitasks/agent_sessions.json`, env override
  `AITASKS_AGENT_SESSIONS_FILE`, lock dir derived from the resolved path
  (`<file>.lockd`), 0600 with `_target_mode` preservation, write via
  `lib/atomic_write.py`. Captures under `~/.config/aitasks/frozen/<id>/`
  (0700 dir; `capture.ansi`, `capture.txt`), env `AITASKS_FROZEN_DIR`.
- Schema v1:
  ```json
  {"version": 1, "sessions": [{
    "id": "7f3a2c1d",                 // record id (8 hex, os.urandom) — PRIMARY KEY
    "root": "/real/path/project",     // realpath, both sides         ┐ DURABLE IDENTITY
    "window": "agent-pick-1705",      //                               │ (root, window, window_slot)
    "window_slot": 0,                 // assigned once; >0 only for a 2nd agent in the same window ┘
    "pane_id": "%104", "pane_pid": 41233,   // LOCATION / GENERATION data — replaceable, never identity
    "session": "aitasks",             // tmux session name — display only
    "operation": "pick", "task_id": "1705",          // task_id "" when unbound
    "agent_string": "claudecode/opus5", "agent_kind": "claudecode",
    "codeagent_session_id": "", "transcript_path": "",  // "" = unknown → re-pick only
    "started_at": "2026-09-04T09:12:03Z",
    "state": "live",                  // live | freezing | frozen | restoring | aborting
    "state_at": "2026-09-04T09:12:03Z",
    "op_nonce": "", "op_owner_pid": 0, "op_started_at": "",   // LEASE of the in-flight freeze/restore (see below)
    "frozen_at": "", "capture_ansi": "", "capture_txt": "",
    "capture_lines": 0, "last_phase": "",
    "standin_pid": 0,                 // #{pane_pid} of the stand-in viewer, written at freeze-commit and every stand-in respawn
    "launch_pid": 0,                  // #{pane_pid} of the replacement agent, written by restore-launched (nonce-bound)
    "restore_attempts": 0, "restore_mode": "",   // "" | resume | repick (current attempt)
    "ack": "",                        // "" | hook | liveness — how the last restore was confirmed
    "last_error": ""                  // "" | "<nonce>:session_mismatch" | "<nonce>:<reason>" — coordinator-readable outcome channel
  }]}
  ```
  `pane_id` / `pane_pid` are **location and generation data**: a tmux server
  restart, a reattach or a respawn replaces them on the same record. They
  are never part of the identity key and a recycled `%N` can attach to
  nothing on its own — attachment needs either `@aitask_record` on the pane
  (options die with the pane, so a recycled pane never carries a stale one)
  or a `(root, window)` match under the conflict policy below.
  Unknown `state` = corruption (not a default). `load()` raises
  `MalformedSessionsError`; `load_safe()` returns empty. Generation normalised
  to `SCHEMA_VERSION` on read.
- **Record ownership (one allocator) and the `(root, window)` conflict
  policy.** The `upsert` verb is the *only* creator of records. Resolution
  order for a caller without `--restore-of`:
  1. `--id <rid>` (from `@aitask_record` on the caller's pane) → that record,
     whatever its `(root, window)` (a renamed window keeps its record).
  2. Else, **among `live` records only** with the caller's `(root, window)`,
     the relocation candidates are: the one whose `pane_id` equals the
     caller's pane, else those whose `pane_pid` is dead or whose pane no
     longer exists. **Exactly one candidate** → it is the same agent slot:
     replace `pane_id`/`pane_pid`, update session id / transcript / agent
     string, print `UPSERTED:<id>|updated` (the tmux-restart and reattach
     case — no second record). **More than one candidate** (two agents shared
     the window before a server restart; nothing on the caller's side can
     tell them apart) → **fail closed on relocation**: fall through to rule 3
     and print `UPSERTED:<id>|created_slot<N>|ambiguous_relocation`; the stale
     records are left for purge (rule: a `live` record whose `pane_pid` is
     dead and whose `pane_id` is absent from an enumerated window →
     `DROPPED:…|dead_pane`), never guessed.
     Transitional records (`freezing`/`restoring`/`aborting`) are **never**
     relocated or updated by an unstamped caller: they are touched only by
     `--restore-of` + the current nonce, or by `reconcile`. If the caller's
     pane *is* a transitional record's pane → refuse
     (`UPSERT_REFUSED:<id>|<state>_unacknowledged`, a stray session in a
     transacting pane); otherwise they are simply not candidates.
  3. Else every `(root, window)` record is `live` in **another** pane (a
     second agent split into the same window), transitional, or `frozen`
     (retained state whose window name is being reused, e.g. the same task
     re-picked after a tmux restart) → **create beside it**: new record,
     `window_slot` = lowest unused slot for that `(root, window)`, print
     `UPSERTED:<id>|created_slot<N>`. A retained frozen record never blocks a
     live launch and is never attached to; it stays restorable into a fresh
     window (`unique_window_name` disambiguates) and is listed distinctly by
     its `frozen_at`.
  4. Else → create (`state=live`, `window_slot=0`), print `UPSERTED:<id>|created`.
  In every create/update branch the caller's pane is stamped
  `@aitask_record=<id>`.
  Other branches:
  - record exists in `restoring` **and** the caller passes
    `--restore-of <id> --nonce <n>` (the hook forwards them from the
    replacement agent's environment, §D) → the **restore acknowledgement**:
    nonce must equal `op_nonce`; in `resume` mode `--session-id` must equal
    `codeagent_session_id` — else the store **persists**
    `last_error="<nonce>:session_mismatch"` (state unchanged) and prints
    `RESTORE_SESSION_MISMATCH:<id>` exit 7. The hook has no return channel to
    the detached coordinator, so the record *is* the channel: the coordinator
    and `reconcile` both read `last_error` for the current nonce and take the
    abort branch, never the liveness fallback. In `repick` mode the new
    session id is adopted. On success: `pane_id`/`pane_pid` updated from the
    caller's pane, `@aitask_record` stamped on it, state `live`, `ack=hook`,
    capture files deleted, print `UPSERTED:<id>|restored`;
  - record exists in `restoring` without `--restore-of`/`--nonce` → refuse,
    print `UPSERT_REFUSED:<id>|restoring_unacknowledged` (a stray session in
    a restoring pane is never an ack);
  - record exists in `freezing` / `frozen` → refuse, print
    `UPSERT_REFUSED:<id>|<state>` (a hook firing in a stand-in pane is a bug).
  Two callers: the SessionStart hook (child 3, normal path) and the freeze
  engine (child 4, fallback when the hook never fired). Both read
  `@aitask_record` off the pane first and pass `--id` when present, so a pane
  that was already recorded is never duplicated even after a `pane_id`
  recycle. A restore into a **new** pane (window gone) carries the record id
  in the environment, never on the pane, so it selects the old record instead
  of creating a second one.
- **Operation lease.** `freeze-begin`, `restore-begin` and `lease-take` mint
  `op_nonce` (8 hex), record `op_owner_pid` (the coordinator) and
  `op_started_at`, and print the nonce. **Every verb that mutates a record
  holding a lease** (`freeze-commit`, `freeze-abort`, `restore-launched`,
  `restore-confirm`, `restore-abort`, `standin-respawned`, the ack form of
  `upsert`) requires `--nonce <n>`; a mismatch prints `NONCE_MISMATCH:<id>`
  exit 6 and writes nothing — a coordinator that lost the race to
  `reconcile` fails closed instead of double-acting. `lease-take <id>` →
  `LEASED:<id>|<nonce>` is how `reconcile` (or a stand-in relaunch on a
  `frozen` record) acquires ownership: it is refused (`LEASE_HELD:<id>`)
  while a lease exists whose `op_started_at` is younger than
  `stale_op_grace` (default 60 s) **or** whose `op_owner_pid` is alive; a
  stale lease with a dead/unverifiable owner is taken over. Within the grace,
  or with a live owner, reconcile leaves the record alone. Lease-clearing
  transitions (`freeze-commit`, `freeze-abort`, `restore-confirm`, hook ack,
  `standin-respawned` out of `aborting`) clear the lease.
- **State machine** (every transition is one locked verb; illegal transitions
  print `TRANSITION_REFUSED:<id>|<from>|<verb>` exit 5 and write nothing):
  ```
  live ──freeze-begin──▶ freezing ──freeze-commit──▶ frozen ◀────────────────┐
   ▲                        │                          │                      │
   └────freeze-abort────────┘                          │ restore-begin        │ standin-respawned
   ▲                                                   ▼                      │ (same nonce)
   └──upsert (hook ack) / restore-confirm── restoring ──restore-abort──▶ aborting
  drop: any state → record removed + capture files removed
  ```
  `aborting` is **nonce-owned**: the record stays leased by the aborting
  attempt until its stand-in is back (`standin-respawned --nonce` → `frozen`,
  lease cleared). `restore-begin` on `aborting` → `TRANSITION_REFUSED`, so a
  user or a second controller cannot start another restore in the gap and
  an old coordinator cannot respawn over a newer attempt: its `standin-respawned`
  carries a stale nonce and is refused.
  **Captures are deleted only on a verified ack** (`ack=hook`). A
  liveness-only `restore-confirm` transitions to `live` but **keeps** the
  capture files (`ack=liveness`); they are removed on `drop` or liveness
  purge. This is what stops a malformed resume that starts a fresh session
  from destroying the only copy.
- Wrapper verbs (sole writer; `list`/`show` take no lock; exit 0/2/3
  `LOCK_BUSY`/4 `ERROR`/5 `TRANSITION_REFUSED`/6 `NONCE_MISMATCH`/7
  `RESTORE_SESSION_MISMATCH`/8 `LEASE_HELD`):
  `upsert --root <r> --window <w> --pane <id> --pane-pid <pid> [--id <rid>] [--session-id <sid>] [--transcript <p>] [--agent-string <s>] [--operation <op>] [--task-id <t>] [--restore-of <rid> --nonce <n>]`;
  `freeze-begin <id> --capture-ansi <p> --capture-txt <p> --lines <n> [--phase <t>]` → `FREEZING:<id>|<nonce>`;
  `freeze-commit <id> --nonce <n> --pane <pane_id|""> --pane-pid <pid|0>` → `FROZEN:<id>` (writes the stand-in's location: `pane_id`/`standin_pid` from the arguments; `--pane "" --pane-pid 0` is the gone-pane commit used by reconcile; `--pane` without `--pane-pid` or vice versa → usage error exit 2);
  `freeze-abort <id> --nonce <n>` → `LIVE:<id>` (captures deleted);
  `restore-begin <id> --mode resume|repick` → `RESTORING:<id>|<nonce>` (captures **retained**, `restore_attempts`+1, `launch_pid=0`, `last_error=""`);
  `restore-launched <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LAUNCHED:<id>` (records the replacement's `launch_pid` + location; written by the coordinator right after `respawn-pane`/`launch_in_tmux` returns — the nonce-bound evidence that the respawn happened);
  `restore-confirm <id> --nonce <n> --pane <id> --pane-pid <pid>` → `LIVE:<id>|liveness` (captures **kept**; refused with `TRANSITION_REFUSED` unless `launch_pid != 0` and equals `--pane-pid`);
  `standin-respawned <id> --nonce <n> --pane <id> --pane-pid <pid>` → `STANDIN:<id>` (records the stand-in's `standin_pid` + location; from `aborting` it also transitions to `frozen` and clears the lease; from `frozen` (a `lease-take`n relaunch of a dead stand-in) it just updates and clears the lease; `freeze-commit` folds the same write in);
  `restore-abort <id> --nonce <n>` → `ABORTING:<id>` (captures retained; lease kept by the same nonce);
  `lease-take <id>` → `LEASED:<id>|<nonce>` / `LEASE_HELD:<id>` exit 8;
  `drop <id>` → `DROPPED:<id>`;
  `list [--state <s>] [--root <r>]` → `SESSION:<id>|<state>|<root>|<window>|<pane_id>|<task_id>|<agent_string>|<state_at>`;
  `show <id>` → `KEY:value` lines;
  `purge --observed <file>` → `DROPPED:<id>|<reason>` + `PURGED:<n>`.
  **Observation protocol (superset of the marks one, backward-compatible):**
  ```
  ROOT<TAB><root>                                   -- successfully enumerated root
  WINDOW<TAB><root><TAB><window>                    -- observed agent window
  PANE<TAB><root><TAB><window><TAB><pane_id><TAB><pane_pid><TAB><pane_dead>   -- every pane of that window
  INCOMPLETE                                        -- suppress every sweep
  ```
  `monitor_shared._write_observation_file()` gains a `panes=` argument and
  writes the `PANE` rows from `TmuxMonitor.last_discovered_panes()` (the
  `_LIST_PANES_FORMAT` already carries `pane_id` and `pane_pid`; `pane_dead`
  is appended to the format — see §B arity rule). The marks reader
  (`agent_marks._read_observed`) is extended to **skip** `PANE` rows so one
  file serves both purges; `agent_sessions` requires them. A file with
  `ROOT`/`WINDOW` but no `PANE` rows for an enumerated root is treated as
  pane-incomplete for that root: `dead_window` still applies, `dead_pane`
  does not (fail closed).
- **Purge policy** (fail-closed on `INCOMPLETE`, mirrors `sweep_liveness`):
  a `live` record whose `(root, window)` is absent from a successfully
  enumerated root → `DROPPED:…|dead_window`; a `live` record whose window has
  a `WINDOW` row **and** `PANE` rows, but whose `pane_id` appears in none of
  them (or appears with `pane_dead=1`) and whose `pane_pid` is dead
  (`os.kill(pid, 0)` → `ESRCH`; an `EPERM`/unverifiable pid is treated as
  alive) → `DROPPED:…|dead_pane` — this is what retires the stale candidates
  left behind by an ambiguous relocation. Two producers feed `purge`: the
  monitor maintenance tick (observation file above) and `aitask_frozen.sh
  reconcile`, which builds the same file from its own `list-panes` pass so
  retirement does not depend on a TUI being open. `freezing` / `frozen` / `restoring` /
  `aborting` records are never purged by liveness — they are reconciled by
  `aitask_frozen.sh reconcile` (§C/§D). A frozen record whose capture file is
  missing → `DROPPED:…|capture_missing`.
- `SessionsView` (mtime+size+inode gated) for the TUIs; `invalidate()` after
  every write. `standin_command(record_id) -> str` returns
  `ait frozenagent --record <id>` unless `AITASKS_FROZEN_STANDIN_CMD` is set
  (documented **test seam**; production never sets it).

#### B. Pane options (tmux user options, pane-scoped)

| Option | Set by | Cleared by | Read by | Meaning |
|---|---|---|---|---|
| `@aitask_record=<id>` | `upsert` (hook or freeze engine) | `drop`; pane death | freeze engine, restore coordinator, hook (`--id`) | the pane-visible join to its store record |
| `@aitask_frozen=<id>` | freeze engine, immediately before `respawn-pane` | `restore-confirm` path (coordinator), `drop` | `_LIST_PANES_FORMAT` (appended), `kill_agent_pane_smart` format, `aitask_companion_cleanup.sh`, `maybe_spawn_minimonitor` occupancy | this pane is a frozen stand-in — **authoritative** classifier |
| `@aitask_standin_ready=<id>` | **the viewer itself**, after mount (only the app stamps its own pane — `mark_monitor_pane` rule) | freeze engine + restore coordinator (`set-option -pu`) immediately **before** every `respawn-pane`; `drop` | `reconcile` | positive proof that the stand-in is up — the only signal that distinguishes "stamped, viewer running" from "stamped, agent still running" |
| `@aitask_agent_session=<sid>` | SessionStart hook on `$TMUX_PANE` | pane death | freeze engine fallback when the store has no session id | codeagent session id |

**Pane user options survive `respawn-pane`** (they are pane-scoped, not
process-scoped), which is why `@aitask_standin_ready` must be explicitly unset
before each respawn and why `@aitask_record` stays valid across freeze/restore
on the same pane. `#{pane_current_command}` is a process basename and is
**never** used as identity; `#{pane_pid}` (stored as `pane_pid`) and the
options above are the only server-observable identities reconcile reads.

Constants live in `monitor/monitor_core.py` beside `SHADOW_TARGET_OPTION`
(`RECORD_OPTION`, `FROZEN_OPTION`, `STANDIN_READY_OPTION`,
`AGENT_SESSION_OPTION`) and are mirrored in `lib/agent_sessions.sh` for shell
callers.

#### C. Freeze — `lib/agent_freeze.py` + `aitask_frozen.sh freeze <pane>|--all`

Runs **out of the agent pane** (from a TUI, a shell, or `run-shell -b`).
Every step is persisted before the next irreversible one:

1. Resolve the record: `@aitask_record` → `show`; else `upsert` (fallback).
   Read `codeagent_session_id`; if empty, try `@aitask_agent_session`.
2. `capture-pane -p -e -J -t <pane> -S -<cap>` via `TmuxClient.run` →
   `capture.ansi`; strip via `monitor/ansi_utils` → `capture.txt`.
3. `freeze-begin` → state `freezing`, capture paths persisted, **lease
   minted** (`op_nonce`, `op_owner_pid`=this coordinator).
4. `set-option -p -t <pane> @aitask_frozen <id>`; `set-option -pu -t <pane>
   @aitask_standin_ready` (clear any stale ready mark from a previous cycle).
5. `respawn-pane -k -t <pane> '<standin_command(id)>'` via the gateway.
   Window name unchanged, so `classify_pane` / `task_id_from_window_name`
   keep working. The viewer stamps `@aitask_standin_ready=<id>` on mount.
6. `freeze-commit --nonce <n> --pane <pane> --pane-pid <stand-in pid>` →
   state `frozen`, `standin_pid` + location recorded (read via
   `display-message -p -t <pane> '#{pane_id}\t#{pane_pid}'` after the
   respawn), lease cleared.

Failure at 1–3 → nothing to undo beyond temp files (`FREEZE_FAILED:<stage>`).
Failure at 4 → `freeze-abort --nonce`. Failure at 5 (tmux refused) → unstamp +
`freeze-abort --nonce`; the agent is still running. Failure at 6 (store busy)
→ the record stays `freezing`; **reconcile** completes it once the lease is
stale. A `NONCE_MISMATCH` at 6 means reconcile already resolved the record;
the coordinator reports it and exits without touching the pane.

**`aitask_frozen.sh reconcile`** (idempotent; run by the coordinator after
every freeze/restore, by the monitor maintenance tick beside
`_maybe_purge_marks`, and manually) resolves every non-`live` record **whose
lease is stale** (`op_started_at` + `stale_op_grace` elapsed **and**
`op_owner_pid` dead/unverifiable — otherwise the record is skipped as
in-flight) from server-observable facts only
(`list-panes -F '#{pane_id}\t#{pane_pid}\t#{pane_dead}\t#{@aitask_frozen}\t#{@aitask_standin_ready}\t#{@aitask_record}'`;
"agent alive" = `pane_pid == record.pane_pid`; "viewer here" =
`pane_pid == record.standin_pid`; "replacement here" =
`pane_pid == record.launch_pid`; "stand-in up" = `@aitask_standin_ready == id`;
"mismatch" = `last_error` begins with the current `op_nonce`):

| record state | pane observation | action |
|---|---|---|
| `freezing` | `@aitask_frozen==id` **and** stand-in up | `freeze-commit --pane <pane> --pane-pid <observed pid>` |
| `freezing` | agent alive, stand-in not up | unstamp both options, `freeze-abort` (captures deleted) |
| `freezing` | `@aitask_frozen==id`, stand-in not up, neither agent nor viewer pid, pane not dead | **indeterminate — no transition** (viewer may still be booting); re-checked next pass |
| `freezing` | `@aitask_frozen==id`, pane dead | respawn the stand-in (clear ready first), `standin-respawned`, then re-check |
| `freezing` | pane gone | `freeze-commit --pane "" --pane-pid 0` |
| `frozen` | pane gone | keep (restorable into a new window) |
| `frozen` | `@aitask_frozen==id`, pane dead | `lease-take`, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | mismatch recorded for this nonce | `restore-abort` (→ `aborting`), kill the wrong agent via `respawn-pane -k` back to the stand-in, `standin-respawned --nonce` (→ `frozen`) — **never** liveness-confirm |
| `restoring` | viewer here (`pane_pid==standin_pid`) — the coordinator died before or during the respawn, whether or not the ready mark survived | `restore-abort`; respawn the stand-in so it re-stamps ready; `standin-respawned --nonce` |
| `restoring` | `launch_pid==0` and pane pid is neither the viewer's nor the agent's | **indeterminate — no transition** (respawn may be mid-flight); after `stale_op_grace` ×2 → `restore-abort` + respawn stand-in + `standin-respawned --nonce` |
| `restoring` | replacement here (`pane_pid==launch_pid`), pane not dead, no mismatch, `state_at` + `restore_ack_grace` (default 20 s) elapsed | `restore-confirm --pane --pane-pid` (`ack=liveness`, captures kept) |
| `restoring` | pane dead | `restore-abort`, clear ready, respawn the stand-in, `standin-respawned --nonce` |
| `restoring` | pane gone | `restore-abort` with `pane_id=""`, then `standin-respawned --nonce --pane "" --pane-pid 0` (→ `frozen`, restorable into a new window) |
| `aborting` (stale lease taken over) | stand-in up (`@aitask_standin_ready==id`) | `standin-respawned --nonce` (→ `frozen`) |
| `aborting` (stale lease taken over) | anything else | clear ready, respawn the stand-in, `standin-respawned --nonce` (→ `frozen`) |

Every reconcile action on a leased record is preceded by `lease-take`; a
`LEASE_HELD` answer means a live coordinator owns it and reconcile skips.

A liveness confirm therefore requires **positive evidence** that the
process in the pane is the one the coordinator launched (`launch_pid`), and
a viewer whose ready mark was cleared is still recognised by `standin_pid`.

Failure injection: `AITASKS_FREEZE_FAIL_AT=capture|begin|stamp|respawn|commit`,
`AITASKS_RESTORE_FAIL_AT=begin|respawn|ack`, and `AITASKS_FROZEN_PAUSE_AT=<stage>`
(the coordinator `SIGSTOP`s itself so a test can run a concurrent
`reconcile` and then `SIGCONT`) — documented test seams, honoured only under
`AITASKS_TEST_MODE=1`.

**Cleanup contract** (`aitask_companion_cleanup.sh` + `count_other_real_agents`
must agree — pinned by the parity test):
- a `@aitask_frozen`-stamped pane **counts as a real agent sibling** (the
  window exists to hold it; killing agent B must not destroy frozen A's viewer);
- when the *dying* pane is the stamped one, the cleanup script **abstains
  entirely** (it is being respawned, not departing);
- `kill_agent_pane_smart` on a frozen pane = `drop` + kill by the same rule.

#### D. Restore — `lib/agent_restore.py` + `aitask_frozen.sh restore <id> [--repick] | --all`

**Never runs inside the pane it replaces.** The viewer's `R`/`p` keys and the
minimonitor keys invoke `run-shell -b "<repo>/.aitask-scripts/aitask_frozen.sh restore <id>"`
through the gateway; the coordinator is a detached process that outlives the
respawn. Two-phase, acknowledged:

1. Build the argv: `aitask_codeagent.sh --agent-string <s> --resume-session <sid> --dry-run invoke raw`
   (resume) or the existing pick launch argv (`--repick`, task id required).
   Empty session id and no `--repick` → `RESTORE_FAILED:no_session` (nothing changes).
2. `restore-begin --mode <m>` → state `restoring`, lease minted (nonce `n`);
   captures and `@aitask_frozen` retained.
3. Prefix the argv with the **restore identity environment** (the
   `explore-relay` `env` precedent — `env` execs into the agent, so the pane
   pid is still the agent's):
   `env AITASK_RESTORE_RECORD=<id> AITASK_RESTORE_NONCE=<n> AITASK_RESTORE_MODE=<m> AITASK_RESTORE_EXPECT_SESSION=<sid> <argv>`.
   Then `set-option -pu @aitask_standin_ready` and
   `respawn-pane -k -t <stand-in> '<env argv>'` — or, when `pane_id=""`,
   `launch_in_tmux` into a new window with the recorded name. Immediately
   after tmux returns, read the new `#{pane_pid}` and write
   `restore-launched --nonce --pane --pane-pid` — the nonce-bound evidence
   that a replacement was actually started. The replacement agent's
   SessionStart hook forwards the four variables as `upsert --restore-of
   --nonce --session-id` (§A ack rules), which is what selects the **old**
   record from a brand-new pane, verifies the resumed session id, and stamps
   `@aitask_record` there.
4. Wait for the ack: poll `show <id>` until `state=live`, `last_error`
   carries this nonce, **or** `restore_ack_grace` elapses.
   - `live` with `ack=hook` → clear `@aitask_frozen`, print `RESTORED:<id>|hook`
     (captures already deleted by the ack).
   - `last_error="<nonce>:session_mismatch"` (the hook reported a different
     session in `resume` mode; persisted by the store because the hook has
     no channel to this process) → `restore-abort --nonce` (→ `aborting`,
     still owned by this nonce), `set-option -pu @aitask_standin_ready`,
     `respawn-pane -k` back to the stand-in, then `standin-respawned --nonce
     --pane --pane-pid` (→ `frozen`), print `RESTORE_FAILED:<id>|session_mismatch`;
     **capture intact**. The same abort → respawn → `standin-respawned --nonce`
     sequence is used by every failure branch below; a `NONCE_MISMATCH` at
     any step means reconcile already finished the abort.
   - grace elapsed, pane alive, `pane_pid == launch_pid`, no hook ack and no
     error → `restore-confirm --nonce --pane --pane-pid` → `live` with
     `ack=liveness`, **captures kept**, clear the stamp, print
     `RESTORED:<id>|liveness` (the viewer/minimonitor show "restored,
     unverified — capture kept").
   - pane dead at any poll (invalid session, binary missing, immediate exit)
     → `restore-abort --nonce`, clear ready, respawn the stand-in,
     `standin-respawned --nonce`, print `RESTORE_FAILED:<id>|agent_exited` —
     **the capture is intact and the viewer is back**.
   - `NONCE_MISMATCH` on any verb → reconcile already settled it; exit
     without touching the pane.
5. Coordinator crash between 2 and 4 → `reconcile` (§C table) settles it
   once the lease is stale.

`aitask_codeagent.sh` gains a global `--resume-session <sid>` (template
`OPT_HEADLESS`): `claude --model <id> --resume <sid>`, `codex resume <sid>`
(model flag per codex CLI), opencode → `RESUME_UNSUPPORTED:opencode` exit 2.
Resolution stays single-sourced in `lib/agent_string.sh`. Restore-All iterates
`frozen` records; per-record failures are reported, never abort the batch.

