#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

PYTHON="$(require_ait_python)"

missing=()
"$PYTHON" -c "import textual" 2>/dev/null || missing+=(textual)
"$PYTHON" -c "import yaml"    2>/dev/null || missing+=(pyyaml)
if [[ ${#missing[@]} -gt 0 ]]; then
    die "Missing Python packages: ${missing[*]}. Run 'ait setup' to install all dependencies."
fi

ait_warn_if_incapable_terminal

# --- Self-upgrade handoff -------------------------------------------------
#
# The syncer cannot upgrade its OWN repo by spawning a shell: `ait upgrade`
# replaces everything under .aitask-scripts/, and every subprocess the running
# TUI shells out to afterwards would be the new version driven by old in-memory
# state. Instead the app writes a request here and exits; this wrapper runs the
# upgrade once Python is gone.
#
# The request is treated as untrusted input even though we write it ourselves:
#
#   * The WRAPPER owns the path. The export below is unconditional, so an
#     inbound AIT_SYNCER_HANDOFF cannot redirect us at an attacker-chosen file.
#   * It carries DATA, never code — two JSON strings, no command. It is parsed
#     with json.load and is never sourced, evaled, or interpolated unparsed.
#   * It is REVALIDATED below. The app's own validation is UX; this is the
#     security boundary, and it re-derives everything independently.
#
_handoff_dir="$(mktemp -d)"
chmod 700 "$_handoff_dir"
_cleanup_handoff() { rm -rf "$_handoff_dir"; }
# INT/TERM must EXIT, not just clean up. A trap that returns hands control back
# to the next statement, so a Ctrl-C arriving after the request has been read
# into memory would be "handled" by deleting a file that is no longer the source
# of truth — and the script would carry on into the upgrade, turning a
# cancellation into a framework rewrite. Exit with the conventional
# 128+signal status instead.
trap '_cleanup_handoff' EXIT
trap '_cleanup_handoff; exit 130' INT
trap '_cleanup_handoff; exit 143' TERM
export AIT_SYNCER_HANDOFF="$_handoff_dir/request.json"

# NOT exec: this shell must outlive the app to service the handoff. `set -e`
# would abort on a non-zero app exit before we get there, so capture it.
_rc=0
"$PYTHON" "$SCRIPT_DIR/syncer/syncer_app.py" "$@" || _rc=$?

[[ -f "$AIT_SYNCER_HANDOFF" ]] || exit "$_rc"

_request="$(cat "$AIT_SYNCER_HANDOFF")"
# Unlink BEFORE running anything, so a crash mid-upgrade cannot re-trigger it.
rm -f "$AIT_SYNCER_HANDOFF"

# Strict shape: exactly {"root": str, "version": str}. object_pairs_hook
# rejects duplicate keys (json.loads would otherwise silently keep the last),
# and a newline in root is refused because the output below is line-oriented.
# Emits version on line 1 and root on line 2; any deviation exits non-zero.
_parsed="$(printf '%s' "$_request" | "$PYTHON" -c '
import json, sys

def no_dupes(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate keys")
    return dict(pairs)

data = json.load(sys.stdin, object_pairs_hook=no_dupes)
if not isinstance(data, dict) or set(data) != {"root", "version"}:
    raise SystemExit("handoff request must have exactly root and version")
root, version = data["root"], data["version"]
if not isinstance(root, str) or not isinstance(version, str):
    raise SystemExit("handoff fields must be strings")
if "\n" in root or "\n" in version:
    raise SystemExit("handoff fields must not contain newlines")
print(version)
print(root)
')" || die "Ignoring malformed upgrade handoff request."

_version="$(printf '%s\n' "$_parsed" | sed -n '1p')"
_root="$(printf '%s\n' "$_parsed" | sed -n '2p')"

[[ "$_root" == /* && -d "$_root" \
    && -f "$_root/aitasks/metadata/project_config.yaml" \
    && -x "$_root/ait" ]] \
    || die "Refusing upgrade handoff: '$_root' is not an aitasks project root."
[[ "$_version" =~ ^(latest|[0-9]+\.[0-9]+(\.[0-9]+)?)$ ]] \
    || die "Refusing upgrade handoff: invalid version '$_version'."

# exec, for two reasons: the upgrade replaces this very script on disk, so bash
# must not read another byte of it afterwards; and the upgrade's exit status
# becomes ours. exec skips the EXIT trap, so clean up explicitly first. From
# here on the upgrade owns the terminal, so it also owns Ctrl-C.
_cleanup_handoff
trap - EXIT INT TERM
# Positional args, not string interpolation — the validated scalars never
# become shell text. The && is load-bearing: a failed upgrade must not be
# followed by setup.
exec bash -c '"$1/ait" upgrade "$2" && "$1/ait" setup' bash "$_root" "$_version"
