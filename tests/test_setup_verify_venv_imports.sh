#!/usr/bin/env bash
# test_setup_verify_venv_imports.sh - Tests for the post-install venv dependency
# validators in aitask_setup.sh: verify_venv_imports (importability) and
# verify_venv_specs (installed version satisfies the pip spec).
#
# Sources aitask_setup.sh with --source-only (no main run) and drives the two
# helpers against bash stub interpreters, so the result is deterministic and
# independent of the host's site-packages. Pattern mirrors
# tests/test_python_resolve_pypy.sh.
#
# Run: bash tests/test_setup_verify_venv_imports.sh
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
SETUP="$PROJECT_DIR/.aitask-scripts/aitask_setup.sh"

PASS=0
FAIL=0
TOTAL=0

SCRATCH="$(mktemp -d "${TMPDIR:-/tmp}/test_setup_verify.XXXXXX")"
trap 'rm -rf "$SCRATCH"' EXIT

# make_py_stub <path> <importable-csv> <specs-problem-output>
# A bash stub mimicking the two python invocations the helpers use:
#   `python -c "import <mod>"` -> exit 0 if <mod> is in <importable-csv>, else 1
#   `python - <args...>`       -> discard the stdin script, print the canned
#                                 <specs-problem-output> verbatim (the lines
#                                 verify_venv_specs would parse), exit 0.
make_py_stub() {
    local path="$1" import_ok="$2" badout="$3"
    cat > "$path" <<STUB
#!/usr/bin/env bash
case "\$1" in
  -c) mod="\${2#import }"
      case ",$import_ok," in *",\$mod,"*) exit 0 ;; *) exit 1 ;; esac ;;
  -)  cat >/dev/null; printf '%s' '$badout'; exit 0 ;;
  *)  exit 0 ;;
esac
STUB
    chmod +x "$path"
}

# Source the setup script without running main(). set -e is active here, so this
# also exercises that the helpers never fail their caller (return 0).
# shellcheck source=/dev/null
source "$SETUP" --source-only

# === verify_venv_imports ===

STUB_IMPORTS="$SCRATCH/py_imports"
make_py_stub "$STUB_IMPORTS" "sys,textual,yaml,linkify_it" ""

verify_venv_imports "$STUB_IMPORTS" textual yaml linkify_it nonexistent_mod_xyz
assert_eq "imports: one absent module collected" "nonexistent_mod_xyz" "${missing_imports[*]}"

verify_venv_imports "$STUB_IMPORTS" textual yaml
assert_eq "imports: all present -> empty" "0" "${#missing_imports[@]}"

verify_venv_imports "$STUB_IMPORTS" absent_a textual absent_b
assert_eq "imports: only absent collected, in order" "absent_a absent_b" "${missing_imports[*]}"

# === verify_venv_specs ===

STUB_OK="$SCRATCH/py_specs_ok"
make_py_stub "$STUB_OK" "sys" ""
verify_venv_specs "$STUB_OK" "textual>=8.2.7,<9" "segno>=1.5,<2"
assert_eq "specs: all in range -> empty" "0" "${#bad_specs[@]}"

STUB_VER="$SCRATCH/py_specs_ver"
make_py_stub "$STUB_VER" "sys" "textual 7.0.0 (need >=8.2.7,<9)
"
verify_venv_specs "$STUB_VER" "textual>=8.2.7,<9"
assert_eq "specs: version mismatch -> one entry" "1" "${#bad_specs[@]}"
assert_contains "specs: mismatch names the dist + need" "textual 7.0.0 (need >=8.2.7,<9)" "${bad_specs[*]}"

STUB_MISS="$SCRATCH/py_specs_miss"
make_py_stub "$STUB_MISS" "sys" "segno (missing)
"
verify_venv_specs "$STUB_MISS" "segno>=1.5,<2"
assert_contains "specs: missing dist reported" "segno (missing)" "${bad_specs[*]}"

# === set -e safety: reaching here means the helpers did not abort the script ===
assert_eq "helpers are set -e safe (reached end)" "ok" "ok"

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL"
if (( FAIL > 0 )); then
    exit 1
fi
