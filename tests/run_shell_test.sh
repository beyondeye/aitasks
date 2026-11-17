#!/usr/bin/env bash
# run_shell_test.sh — run one shell test under a private, per-run TMPDIR and
# report what it leaves behind (t2290).
#
#   bash tests/run_shell_test.sh tests/test_foo.sh [args...]
#   AIT_TMPDIR_GUARD_STRICT=1 bash tests/run_shell_test.sh tests/test_foo.sh
#
# Optional: running `bash tests/test_foo.sh` directly stays the normal way to run
# a test. Use this wrapper when hunting /tmp leaks. It returns the test's own exit
# status (128+n when interrupted by a signal); the leftover report is a warning
# on stderr and never changes it. See tests/lib/tmpdir_guard.sh for what the
# guard does and does not see.
#
# STRICT MODE (AIT_TMPDIR_GUARD_STRICT=1, t2302). Exit 0 then also means "the
# guard inspected the run and found nothing left":
#   - a guard that cannot start refuses to run the test at all (exit 2) instead
#     of running it unguarded, which would report nothing;
#   - a test that passes but left leftovers, or whose leftovers could not be
#     inspected, fails (exit 1);
#   - a failing test keeps its own exit status.
# The default stays warn-only.
set -uo pipefail

if [[ $# -lt 1 ]]; then
    echo "usage: $0 <test.sh> [args...]" >&2
    exit 2
fi

# shellcheck source=lib/tmpdir_guard.sh
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/tmpdir_guard.sh"

strict=0
[[ "${AIT_TMPDIR_GUARD_STRICT:-}" == 1 ]] && strict=1

if ! tmpdir_guard_begin shrun; then
    if (( strict )); then
        echo "TMPDIR GUARD: strict mode needs the guard, which could not start — not running the test" >&2
        exit 2
    fi
fi
tmpdir_guard_run bash "$@"
rc=$?
tmpdir_guard_end
if (( strict )) && [[ "$rc" -eq 0 ]] && [[ "${_TG_LEFTOVER_COUNT:-}" != 0 ]]; then
    echo "TMPDIR GUARD: strict mode — leftovers (or no inspection) turn a pass into a failure" >&2
    exit 1
fi
exit "$rc"
