#!/usr/bin/env bash
# tests/lib/observe_pane_died.sh — fixture-owned `pane-died` observer.
#
# Records ONE line each time a tmux `pane-died` hook it is wired into fires, so
# a test can answer two questions that are otherwise only inferable from the
# window's fate:
#
#   * did `pane-died` fire at all?
#   * what did a pane user option read AT HOOK-EXPANSION TIME?
#
# The caller wires it as a pane-scoped hook and passes tmux FORMAT arguments,
# which tmux expands before running us — that expansion moment is exactly the
# moment the questions are about:
#
#   tmux set-hook -p -t <pane> 'pane-died[0]' \
#     "run-shell '<dir>/observe_pane_died.sh \"#{pane_id}\" \"#{pane_dead}\" \"#{@aitask_frozen}\"'"
#
# WHY THIS INSTEAD OF A PATH-PREPENDED WRAPPER. The shipped companion-cleanup
# hook cannot be intercepted through PATH: `attach_companion_cleanup_hook`
# builds an ABSOLUTE script path (agent_launch_utils.py:1589-1592), and
# `run-shell` executes in the tmux SERVER's environment, not the test shell's.
# A PATH shim would silently observe nothing.
#
# WHY THE HOOK INDEX MATTERS. tmux runs indexed hooks in index order, and the
# shipped cleanup script kills the primary pane UNCONDITIONALLY on every
# invocation (outside its sibling-count guard). An observer at a HIGHER index
# would therefore run after the pane — and the window — is already gone, and
# every `#{...}` above would expand against nothing. Install this at a strictly
# LOWER index than the shipped hook, i.e. BEFORE arming it.
#
# WHY THE NAME. `attach_companion_cleanup_hook` skips installing entirely when
# any existing `pane-died` hook line mentions the shipped cleanup script's
# filename (`_pane_died_hook_indices` sets has_cleanup from the hook TEXT). So
# neither this script's name nor the hook command that invokes it may contain
# that filename, or arming the real hook would silently become a no-op and the
# fixture would stop exercising the shipped wiring.
#
# Usage: observe_pane_died.sh <pane_id> <pane_dead> <frozen_stamp> [log_path]
#
# The log defaults to `pane_died.log` beside this script, so a fixture that
# copies the script into its own temp dir gets a private log with no
# environment plumbing — `run-shell` would not carry an exported variable from
# the test shell anyway, since the server's environment is fixed at server
# start.
set -uo pipefail

pane_id="${1:-}"
pane_dead="${2:-}"
frozen="${3:-}"
log="${4:-}"

if [ -z "$log" ]; then
    log="$(cd "$(dirname "$0")" && pwd)/pane_died.log"
fi

# ONE printf of a short record, appended. A single write below PIPE_BUF to an
# O_APPEND fd is atomic, so this record cannot be torn or interleaved when the
# shipped cleanup hook runs immediately after us.
printf 'pane=%s dead=%s frozen=%s at=%s\n' \
    "$pane_id" "$pane_dead" "$frozen" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$log"
