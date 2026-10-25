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

# make_py_stub <path> <importable-csv> <specs-problem-output> [<specs-rc>]
# A bash stub mimicking the two python invocations the helpers use:
#   `python -c "import <mod>"` -> exit 0 if <mod> is in <importable-csv>, else 1
#   `python - <args...>`       -> discard the stdin script, print the canned
#                                 <specs-problem-output> verbatim (the lines
#                                 verify_venv_specs would parse), exit <specs-rc>
#                                 (default 0; non-zero = the inspection failed).
make_py_stub() {
    local path="$1" import_ok="$2" badout="$3" specs_rc="${4:-0}"
    cat > "$path" <<STUB
#!/usr/bin/env bash
case "\$1" in
  -c) mod="\${2#import }"
      case ",$import_ok," in *",\$mod,"*) exit 0 ;; *) exit 1 ;; esac ;;
  -)  cat >/dev/null; printf '%s' '$badout'; exit $specs_rc ;;
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

# === verify_venv_specs: a failed inspection is not a clean one (t2133) ===

verify_venv_specs "$STUB_OK" "textual>=8.2.7,<9"
assert_eq "specs: clean inspection -> specs_check_ok=true" "true" "$specs_check_ok"
verify_venv_specs "$STUB_VER" "textual>=8.2.7,<9"
assert_eq "specs: drift inspection -> specs_check_ok=true" "true" "$specs_check_ok"

STUB_SPECFAIL="$SCRATCH/py_specs_fail"
make_py_stub "$STUB_SPECFAIL" "sys" "" 1
verify_venv_specs "$STUB_SPECFAIL" "rich>=14.3.3"
assert_eq "specs: failed inspection -> specs_check_ok=false" "false" "$specs_check_ok"
assert_eq "specs: failed inspection -> bad_specs empty" "0" "${#bad_specs[@]}"

verify_venv_specs /bin/false "rich>=14.3.3"
assert_eq "specs: /bin/false interpreter -> specs_check_ok=false" "false" "$specs_check_ok"

# === venv_deps_bad / venv_deps_detail: the setup sites' repair decision (t2135) ===

verify_venv_imports "$STUB_IMPORTS" textual yaml
verify_venv_specs "$STUB_SPECFAIL" "rich>=14.3.3"
if venv_deps_bad; then bad=yes; else bad=no; fi
assert_eq "deps_bad: imports ok + failed inspection -> needs repair" "yes" "$bad"
assert_eq "deps_detail: a failed inspection is named, not 'version: none'" \
    "missing: none; version check failed" "$(venv_deps_detail)"

verify_venv_specs "$STUB_OK" "textual>=8.2.7,<9"
if venv_deps_bad; then bad=yes; else bad=no; fi
assert_eq "deps_bad: imports ok + clean inspection -> fine" "no" "$bad"

verify_venv_specs "$STUB_VER" "textual>=8.2.7,<9"
assert_eq "deps_detail: an out-of-range spec is listed" \
    "missing: none; version: textual 7.0.0 (need >=8.2.7,<9)" "$(venv_deps_detail)"

# === rich floor (t2133): split_graphemes hang in 14.3.2, fixed in 14.3.3 ===

rich_spec=""
for s in "${AIT_PIP_SPECS_COMMON[@]}"; do
    [[ "$s" == rich* ]] && rich_spec="$s"
done
assert_eq "COMMON specs pin rich>=14.3.3" "rich>=14.3.3" "$rich_spec"

# The shipped spec string, evaluated by real packaging (same import fallback as
# verify_venv_specs): it must exclude the buggy release and admit the fixed ones.
SPEC_PY="$(resolve_python)"
spec_verdict="$("$SPEC_PY" - "$rich_spec" <<'PY'
import sys
try:
    from packaging.requirements import Requirement
except ImportError:
    from pip._vendor.packaging.requirements import Requirement
spec = Requirement(sys.argv[1]).specifier
print(" ".join(f"{v}={spec.contains(v)}" for v in ("14.3.2", "14.3.3", "15.0.0")))
PY
)"
assert_eq "rich spec rejects 14.3.2, admits 14.3.3 / 15.0.0" \
    "14.3.2=False 14.3.3=True 15.0.0=True" "$spec_verdict"

# === report_venv_dep_drift: read-only upgrade hint (t2133) ===

# make_venv <dir> <stub-args...> — a fake venv whose bin/python is a stub.
make_venv() {
    local dir="$1"; shift
    mkdir -p "$dir/bin"
    make_py_stub "$dir/bin/python" "$@"
}

make_venv "$SCRATCH/venv_drift" "sys" "rich 14.3.2 (need >=14.3.3)
"
make_venv "$SCRATCH/venv_clean" "sys" ""
make_venv "$SCRATCH/venv_fail" "sys" "" 1

VENV_DIR="$SCRATCH/venv_drift" PYPY_VENV_DIR="$SCRATCH/absent_pypy"
drift_out="$(report_venv_dep_drift 2>&1)"; drift_rc=$?
assert_eq "drift: returns 0" "0" "$drift_rc"
assert_contains "drift: names the failing dependency" "rich 14.3.2 (need >=14.3.3)" "$drift_out"
assert_contains "drift: names the venv" "$SCRATCH/venv_drift" "$drift_out"
assert_contains "drift: tells the user to run ait setup" "run 'ait setup'" "$drift_out"

VENV_DIR="$SCRATCH/venv_fail" PYPY_VENV_DIR="$SCRATCH/absent_pypy"
drift_out="$(report_venv_dep_drift 2>&1)"; drift_rc=$?
assert_eq "drift: failed check returns 0" "0" "$drift_rc"
assert_contains "drift: failed check is reported, not silent" "Could not check" "$drift_out"
assert_contains "drift: failed check points to ait setup" "run 'ait setup'" "$drift_out"

VENV_DIR="$SCRATCH/absent_venv" PYPY_VENV_DIR="$SCRATCH/venv_drift"
drift_out="$(report_venv_dep_drift 2>&1)"
assert_contains "drift: PyPy venv checked too" "$SCRATCH/venv_drift has dependencies" "$drift_out"

VENV_DIR="$SCRATCH/venv_clean" PYPY_VENV_DIR="$SCRATCH/venv_clean"
drift_out="$(report_venv_dep_drift 2>&1)"; drift_rc=$?
assert_eq "drift: clean venvs -> silent" "" "$drift_out"
assert_eq "drift: clean venvs return 0" "0" "$drift_rc"

VENV_DIR="$SCRATCH/absent_venv" PYPY_VENV_DIR="$SCRATCH/absent_pypy"
drift_out="$(report_venv_dep_drift 2>&1)"
assert_eq "drift: no venvs -> silent" "" "$drift_out"

# === set -e safety: reaching here means the helpers did not abort the script ===
assert_eq "helpers are set -e safe (reached end)" "ok" "ok"

echo ""
echo "Tests: $TOTAL  Pass: $PASS  Fail: $FAIL"
if (( FAIL > 0 )); then
    exit 1
fi
