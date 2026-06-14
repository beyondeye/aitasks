#!/usr/bin/env bash
# aitask_applink_validate_profile.sh — validate one applink permission profile.
#
# Checks (per aidocs/applink/permissions.md §Adding a new profile, step 2):
#   * `name:` matches the filename stem
#   * `allowed_verbs:` has no duplicates
#   * every verb names a real applink verb (router.KNOWN_VERBS)
#
# Usage: aitask_applink_validate_profile.sh <path/to/profile.yaml>
# Exits 0 and prints "OK: <file>" on success; non-zero with "ERROR: …" otherwise.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" || $# -ne 1 ]]; then
    echo "Usage: ait applink-validate-profile <profile.yaml>"
    echo ""
    echo "Validate an applink permission-profile YAML against the verb registry."
    [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]] && exit 0
    exit 2
fi

PROFILE_PATH="$1"
[[ -f "$PROFILE_PATH" ]] || die "Profile file not found: $PROFILE_PATH"

PYTHON="$(require_ait_python)"

"$PYTHON" - "$SCRIPT_DIR/applink" "$PROFILE_PATH" <<'PY'
import sys
from pathlib import Path

applink_dir, profile_path = sys.argv[1], sys.argv[2]
sys.path.insert(0, applink_dir)

import yaml
from router import KNOWN_VERBS

path = Path(profile_path)
errors = []
try:
    data = yaml.safe_load(path.read_text()) or {}
except (OSError, ValueError) as exc:
    print(f"ERROR: cannot parse {path}: {exc}")
    sys.exit(1)

if not isinstance(data, dict):
    print(f"ERROR: {path}: top-level YAML must be a mapping")
    sys.exit(1)

stem = path.stem
name = data.get("name")
if name != stem:
    errors.append(f"name '{name}' does not match filename stem '{stem}'")

verbs = data.get("allowed_verbs")
if not isinstance(verbs, list):
    errors.append("allowed_verbs must be a list")
    verbs = []

seen, dups = set(), set()
for v in verbs:
    if v in seen:
        dups.add(v)
    seen.add(v)
if dups:
    errors.append("duplicate verb(s): " + ", ".join(sorted(map(str, dups))))

unknown = sorted(str(v) for v in verbs if v not in KNOWN_VERBS)
if unknown:
    errors.append("unknown verb(s) (not in the applink verb registry): " + ", ".join(unknown))

if errors:
    for e in errors:
        print(f"ERROR: {path.name}: {e}")
    sys.exit(1)

print(f"OK: {path.name} ({len(verbs)} verb(s))")
PY
