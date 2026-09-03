---
Task: t1701_guard_unsocketed_tmux_calls_from_agent_shell.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Adds a `PreToolUse`/`Bash` hook that denies a tmux command which does not name
the server it addresses, closing the gap that let an ad-hoc agent probe destroy
the live `tmux -L ait` server during t1699 on 2026-09-03.

The rule is one line long: **name the server you are talking to.** An explicit
`-L <socket>` / `-S <path>` is the only thing that makes the target
unambiguous, and it costs one flag.

## Files Modified

### `.claude/hooks/guard_live_tmux.py` (new, 235 lines)

The guard itself. Reads the hook payload on stdin and emits a
`permissionDecision: "deny"` with a teaching reason, or nothing at all (allow).

Two independent deny rules:

1. **Destructive verb with no socket flag.** `kill-server`, `kill-session`,
   `kill-window`, `kill-pane`, `respawn-pane`, `respawn-window`,
   `unlink-window`, `source-file`. Applied regardless of `$TMUX`: with it set
   the target is the dedicated `ait` server, without it the user's personal
   default server — both hold real work. (`source-file` is in the set because
   it can execute arbitrary tmux commands, a kill among them.)
2. **`TMUX_TMPDIR=` prefix with no socket flag and no `$TMUX` strip.** Denied
   for *any* verb, read-only ones included, because the redirect is silently
   ignored — this is the exact incident shape and the false confidence is the
   whole problem. `env -u TMUX` / `TMUX=` in the same segment makes the
   redirect real and is allowed.

Implementation notes: `shlex.split` tokenises, tokens are split into command
segments on `;`, `&&`, `||`, `|`, `&`; the verb is the first non-flag argument
after skipping values consumed by tmux's value-taking global flags (`-L -S -f
-c -T`); `-L`/`-S` are recognised attached (`-Lfoo`) as well as detached.

### `.claude/settings.json` (new, 17 lines)

New tracked project settings registering the hook on `PreToolUse` / matcher
`Bash`, with a 10s timeout. The repo previously had only
`.claude/settings.local.json` (permissions), so this is the first team-wide
settings file.

### `tests/test_guard_live_tmux.sh` (new, 118 lines)

22 assertions driven through the guard's **real entry point** — hook JSON on
stdin — so a change to the payload contract fails here too, not just a change
to the matching logic.

Coverage is split deliberately:
- **Deny:** the verbatim command from the t1699 transcript, each destructive
  verb bare, a destructive call in a later shell segment, an absolute
  `/usr/bin/tmux` path, and `TMUX_TMPDIR` with a read-only verb.
- **Allow:** `-L` (attached and detached forms), `-S`, a deliberate `-L ait`
  kill, socketed read-only calls, `env -u TMUX` isolation, a command with no
  tmux in it, running a tmux test script, and grepping for the phrase.
- **Message content:** the denial must name `-L`, cite `t1699`, and point at
  `tmux_isolation.sh`. A bare refusal gets worked around; the teaching half is
  what changes the next command, so it is pinned rather than left to drift.
- **Fail-closed:** an unparseable command naming a destructive verb is denied.

## Probable User Intent

Not probable — stated. The user asked, after losing a morning's work: "analyze
the crash cause and then update the 1699 and put a guard so that I can resume
the task with a safeguard."

The intent is specifically a *safeguard*, not a convention: the repo already
had the convention (`aidocs/framework/tui_conventions.md`, "Tmux-stress tasks")
and it did not hold, because it addressed test scripts while the damage came
from a one-off command typed into a shell. Hence enforcement in source.

## Final Implementation Notes

- **Actual work done:** Root-caused the 2026-09-03 09:39:54 outage from the
  session transcript (`89755dd8…`, which ends mid-probe), confirmed the
  mechanism with a read-only probe, then wrote the hook, its registration, and
  its test.

- **Key decisions:**
  - *Deny on the absence of `-L`/`-S`, not on the presence of `$TMUX`.* Keying
    on ambient environment would make the guard's behaviour depend on where it
    happened to run. Requiring the command to name its own target is
    root-scoped and fails safe in both directions.
  - *Rule 2 covers read-only verbs too.* The t1699 `new-session` was itself
    harmless, but denying only the `kill-server` would have let the probe
    create a stray session on the live server and would have taught nothing
    about why `TMUX_TMPDIR` is a trap.
  - *Heredoc bodies are not scanned — a documented boundary, not an
    oversight.* A heredoc writes a script; it does not run tmux. The later
    `bash that_file.sh` reaches the hook with no tmux token in it, so scanning
    heredoc bodies would block the repo's tmux fixtures from being authored
    while enforcing nothing. Script-internal isolation is
    `tests/lib/tmux_isolation.sh`'s job, and the boundary is written into the
    hook's docstring and pinned by a test.
  - *Parse failures fail closed.*

- **Verification:**
  - Mechanism proved directly rather than assumed: `TMUX_TMPDIR=… tmux
    display-message -p '#{socket_path}'` returns `/tmp/tmux-1000/ait` with
    `$TMUX` set and correctly isolates with it stripped.
  - Both deny rules independently mutation-checked. Removing `kill-server`
    from the destructive set → 7 failures; neutering the `TMUX_TMPDIR` branch
    → 1 failure; restored → 22/22.
  - Guard proved live in-session: `tmux kill-session -t <nonexistent>` was
    refused before reaching tmux (safe either way — no such session existed),
    while `tmux -L ait list-sessions` still returned normally, so the hook is
    active and not over-blocking.
  - `shellcheck` clean (SC2016 disabled with a reason on the verbatim probe
    string, which must not expand); `tests/test_no_raw_tmux.sh` still green.
  - Measured overhead: ~18 ms per Bash tool call.

- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).

- **Issues encountered:** One, worth recording. The documentation half of this
  change — the "Ad-hoc probes: `TMUX_TMPDIR` is not isolation" subsection added
  to `aidocs/framework/tui_conventions.md` — is **not** in this task's commit.
  A concurrent session swept the file into commit `38aaf5dcb` *"bug: Give every
  tracked metadata write an owner that commits it (t1677)"* alongside its own
  20 files, roughly 40 minutes after the edit was written. The content is
  correct and on `main`; only its attribution is wrong. Left in place by
  explicit user decision rather than rewritten, since reverting a shared doc
  another session is actively editing costs more than the mis-attribution
  does. Recorded here so the trail from t1701 to that subsection survives.

- **Scope boundary:** The hook binds Claude Code Bash calls only. Codex CLI and
  OpenCode are bound by the doc rule alone; if either gains a comparable
  pre-execution hook, an equivalent guard should be ported. Related:
  `.claude/hooks/` is a new directory in this repo — the first hook it holds.
