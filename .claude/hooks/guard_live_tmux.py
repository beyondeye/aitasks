#!/usr/bin/env python3
"""PreToolUse/Bash guard: refuse a tmux call that does not name its server.

WHY THIS EXISTS (t1699, 2026-09-03 09:39:54)
--------------------------------------------
While implementing t1699 an agent ran this ad-hoc probe from inside a live
`ait` pane:

    D=$(mktemp -d) && TMUX_TMPDIR=$D tmux new-session -d -s probe ... ; \
    TMUX_TMPDIR=$D tmux kill-server

`TMUX_TMPDIR` looks like isolation. It is not. When `$TMUX` is set — which it
always is inside an agent pane — tmux takes the socket path from `$TMUX` and
IGNORES `TMUX_TMPDIR`. Verified directly:

    $ TMUX_TMPDIR=/tmp/tmp.X tmux display-message -p '#{socket_path}'
    /tmp/tmux-1000/ait                       # the LIVE server
    $ env -u TMUX TMUX_TMPDIR=/tmp/tmp.X tmux display-message -p '#{socket_path}'
    error connecting to /tmp/tmp.X/tmux-1000/default   # correctly isolated

So both the `new-session` and the `kill-server` landed on the user's real
`tmux -L ait` server, and the `kill-server` destroyed ~30 panes: every running
code agent, TUI and shell, including the agent that issued it.

THE RULE
--------
Name the server you are talking to. An explicit `-L <socket>` / `-S <path>` is
the only thing that makes the target unambiguous, and it is one flag.

This guard denies a Bash command when either holds:

  1. A tmux invocation uses a DESTRUCTIVE verb (kill-*, respawn-*, unlink-window,
     source-file) with no `-L`/`-S`. Applies regardless of `$TMUX`: with it set
     the target is the dedicated `ait` server, without it the user's personal
     default server. Both hold real work.
  2. A tmux invocation carries a `TMUX_TMPDIR=` env prefix but no `-L`/`-S`.
     That is the exact t1699 shape — an explicit intent to isolate that tmux
     silently ignores — so it is denied for ANY verb, read-only ones included.
     Stripping `$TMUX` in the same segment (`env -u TMUX`, `TMUX=`) makes the
     redirect real, so that form is allowed.

Read-only calls that name their socket (`tmux -L ait list-panes`) and genuinely
isolated fixtures (`tmux -L throwaway kill-server`) are untouched.

KNOWN BOUNDARY (deliberate, not an oversight)
---------------------------------------------
Text after a heredoc operator (`<<`) is not scanned. A heredoc writes a script
to a file; it does not run tmux. The later `bash that_file.sh` reaches this hook
as a command with no tmux token in it, so the guard could not enforce anything
there anyway — scanning heredoc bodies would only block the repo's tmux test
fixtures from being authored, buying nothing. Script-internal isolation is the
job of `tests/lib/tmux_isolation.sh`, not of this hook.

Parsing failures FAIL CLOSED: an unparseable command that mentions tmux and a
destructive verb is denied rather than waved through.
"""

import json
import shlex
import sys

# Verbs that destroy panes, windows, sessions or the server itself, plus
# source-file (it can execute arbitrary tmux commands, including a kill).
DESTRUCTIVE_VERBS = {
    "kill-server",
    "kill-session",
    "kill-window",
    "kill-pane",
    "respawn-pane",
    "respawn-window",
    "unlink-window",
    "source-file",
}

# tmux global flags that consume the following token as their value.
VALUE_FLAGS = {"-L", "-S", "-f", "-c", "-T"}

# Shell tokens that end one command segment and begin another.
SEPARATORS = {";", "&&", "||", "|", "&", "|&", "\n"}

DENY_ADVICE = (
    "Name the tmux server explicitly:\n"
    "  * throwaway fixture -> tmux -L <throwaway-name> <verb>\n"
    "  * the live ait server, on purpose -> tmux -L ait <verb>\n"
    "TMUX_TMPDIR is NOT isolation: inside an agent pane $TMUX is set and tmux "
    "reads the socket path from $TMUX, ignoring TMUX_TMPDIR. That is how "
    "t1699 killed the live -L ait server and ~30 panes on 2026-09-03. "
    "For a shell test, source tests/lib/tmux_isolation.sh and call "
    "require_isolated_tmux (add require_clean_ait_server when the code under "
    "test reaches tmux outside the gateway)."
)


def _is_tmux_token(tok):
    return tok == "tmux" or tok.endswith("/tmux")


def _has_socket_flag(args):
    """True when an explicit -L/-S is present, attached or detached."""
    for tok in args:
        if tok in ("-L", "-S"):
            return True
        if len(tok) > 2 and tok[0] == "-" and tok[1] in ("L", "S"):
            return True
    return False


def _verb_of(args):
    """First non-flag argument, skipping values consumed by global flags."""
    skip_next = False
    for tok in args:
        if skip_next:
            skip_next = False
            continue
        if tok in VALUE_FLAGS:
            skip_next = True
            continue
        if tok.startswith("-"):
            continue
        return tok
    return None


def _segments(tokens):
    """Split a token list on shell command separators."""
    out, current = [], []
    for tok in tokens:
        if tok in SEPARATORS:
            out.append(current)
            current = []
        else:
            current.append(tok)
    out.append(current)
    return out


def _analyze(segment):
    """Yield (verb, has_socket, tmpdir_prefix, strips_tmux) per tmux call."""
    prefix_tmpdir = False
    strips_tmux = False
    for i, tok in enumerate(segment):
        if "=" in tok and not tok.startswith("-"):
            name, _, value = tok.partition("=")
            if name.isidentifier():
                if name == "TMUX_TMPDIR":
                    prefix_tmpdir = True
                # `TMUX=` with an empty value detaches from the inherited server.
                if name == "TMUX" and value == "":
                    strips_tmux = True
                continue
        if tok == "-u" and i + 1 < len(segment) and segment[i + 1] == "TMUX":
            strips_tmux = True
            continue
        if _is_tmux_token(tok):
            args = segment[i + 1:]
            yield (_verb_of(args), _has_socket_flag(args), prefix_tmpdir, strips_tmux)
            # One tmux call per segment is the shape that matters; a second
            # `tmux` inside the same segment is an argument, not a new command.
            return


def check(command):
    """Return a deny reason, or None to allow."""
    if "tmux" not in command:
        return None

    # Heredoc bodies are authoring, not execution -- see KNOWN BOUNDARY above.
    scan = command.split("<<")[0] if "<<" in command else command
    if "tmux" not in scan:
        return None

    try:
        tokens = shlex.split(scan, comments=False, posix=True)
    except ValueError:
        # Unbalanced quotes: fail closed if a destructive verb is anywhere in it.
        if any(verb in scan for verb in DESTRUCTIVE_VERBS):
            return (
                "Refusing a tmux command this guard could not parse "
                "(unbalanced quotes) that names a destructive tmux verb.\n\n"
                + DENY_ADVICE
            )
        return None

    for segment in _segments(tokens):
        for verb, has_socket, tmpdir_prefix, strips_tmux in _analyze(segment):
            if has_socket:
                continue
            if verb in DESTRUCTIVE_VERBS:
                return (
                    "Refusing `tmux %s` with no -L/-S: it targets whichever "
                    "server $TMUX names (inside an agent pane that is the live "
                    "-L ait server) and would destroy real work.\n\n%s"
                    % (verb, DENY_ADVICE)
                )
            if tmpdir_prefix and not strips_tmux:
                return (
                    "Refusing `TMUX_TMPDIR=... tmux %s` with no -L/-S. This is "
                    "the exact t1699 shape: the TMUX_TMPDIR redirect is silently "
                    "ignored while $TMUX is set, so this runs against the live "
                    "server, not the throwaway one.\n\n%s"
                    % (verb or "<no verb>", DENY_ADVICE)
                )
    return None


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        # No parseable payload: nothing to judge, do not block the session.
        return 0

    command = (payload.get("tool_input") or {}).get("command")
    if not isinstance(command, str):
        return 0

    reason = check(command)
    if reason is None:
        return 0

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
