#!/usr/bin/env bash
# run_shell_test.sh — run one shell test under a private, per-run TMPDIR and
# report what it leaves behind (t2290).
#
#   bash tests/run_shell_test.sh tests/test_foo.sh [args...]
#
# Optional: running `bash tests/test_foo.sh` directly stays the normal way to run
# a test. Use this wrapper when hunting /tmp leaks. It returns the test's own exit
# status (128+n when interrupted by a signal); the leftover report is a warning
# on stderr and never changes it. See tests/lib/tmpdir_guard.sh for what the
# guard does and does not see.
set -uo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <test.sh> [args...]" >&2
    exit 2
fi

# shellcheck source=lib/tmpdir_guard.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/tmpdir_guard.sh"

tmpdir_guard_begin shrun || true
tmpdir_guard_run bash "$@"
rc=$?
tmpdir_guard_end
exit "$rc"
