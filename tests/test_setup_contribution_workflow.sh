#!/usr/bin/env bash
# test_setup_contribution_workflow.sh - `ait setup`'s contribution-check CI
# integration in an INSTALLED project layout (t2235).
# Run: bash tests/test_setup_contribution_workflow.sh
#
# install.sh deletes seed/ after every install and upgrade, so the templates
# must come from .aitask-scripts/ci_templates/. Every case drives the real
# entry point, setup_contribution_check, inside a scratch project that has the
# framework but NO seed/ directory, with a scratch HOME (never the real
# ~/.aitask). Cases:
#   (a) fresh install          (b) every earlier shipped template is refreshed
#   (c) a customized file is left alone with a warning
#   (d) the current template is "up to date"
#   (e) every earlier shipped version's hash is listed (guards future edits):
#       always for the committed fixtures, and for git history when reachable
#   (g) an edit made while the update/install prompt is open is never overwritten
#   (h) GitLab/Bitbucket: an existing CI configuration is never edited; an
#       absent one is created
#   (f) missing templates warn and install nothing

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/framework_copy.sh"

set +e

TEMPLATE_REL=".aitask-scripts/ci_templates/github/contribution-check.yml"
OLD_TEMPLATE_REL="seed/ci/github/contribution-check.yml"
TEMPLATE="$PROJECT_DIR/$TEMPLATE_REL"
# Byte-exact earlier templates, committed so the refresh cases never depend on
# clone depth (see the README there).
FIXTURE_DIR="$PROJECT_DIR/tests/fixtures/contribution_workflow_history"

SCRATCH="$(mktemp -d)"
trap 'rm -rf "$SCRATCH"' EXIT
PROJ="$SCRATCH/proj"
STUB_BIN="$SCRATCH/bin"
mkdir -p "$PROJ" "$STUB_BIN" "$SCRATCH/home"

# Installed layout: framework present, seed/ absent.
copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$PROJ/.aitask-scripts"
git -C "$PROJ" init --quiet
git -C "$PROJ" remote add origin https://github.com/o/r.git

# gh stub: authenticated, the 'contribution' label already exists.
cat > "$STUB_BIN/gh" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$SCRATCH/gh_calls"
case "\$1" in
    auth) exit 0 ;;
    label) [[ "\$2" == list ]] && echo contribution; exit 0 ;;
esac
exit 0
EOF
chmod +x "$STUB_BIN/gh"

# glab stub: setup's GitLab label step must never reach a real, possibly
# authenticated, glab on the developer's PATH.
cat > "$STUB_BIN/glab" <<EOF
#!/usr/bin/env bash
printf '%s\n' "\$*" >> "$SCRATCH/glab_calls"
exit 0
EOF
chmod +x "$STUB_BIN/glab"

WF="$PROJ/.github/workflows/contribution-check.yml"

# run_setup -> stdout in $SCRATCH/out, stderr in $SCRATCH/err. (setup's own
# warn() prints to stdout, so warnings are matched against both.)
# An optional argument is bash run after sourcing setup and before the entry
# point -- used to override _contribution_ci_confirm and act inside the window
# between the prompt and the write (WF is exported for it).
run_setup() {
    local hook="${1:-:}"
    : > "$SCRATCH/gh_calls"
    : > "$SCRATCH/glab_calls"
    (
        cd "$PROJ" || exit 99
        env -u AITASKS_HOME HOME="$SCRATCH/home" PATH="$STUB_BIN:$PATH" WF="$WF" HOOK="$hook" \
            bash -c 'source .aitask-scripts/aitask_setup.sh --source-only && eval "$HOOK" && setup_contribution_check' \
            < /dev/null
    ) > "$SCRATCH/out" 2> "$SCRATCH/err"
}

echo "=== Setup contribution workflow tests ==="

echo "--- (a) fresh install in an installed layout (no seed/) ---"
[[ -d "$PROJ/seed" ]] && echo "fixture error: seed/ present"
rm -rf "$PROJ/.github"
run_setup
TOTAL=$((TOTAL + 1))
if [[ -f "$WF" ]] && cmp -s "$WF" "$TEMPLATE"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: (a) workflow not installed from ci_templates"; cat "$SCRATCH/out" "$SCRATCH/err"
fi
assert_contains "(a) reports installation" "Installed contribution check workflow" "$(cat "$SCRATCH/out")"
assert_contains "(a) label setup reached" "label list" "$(cat "$SCRATCH/gh_calls")"

# Earlier shipped templates, oldest first, from the committed fixtures.
OLD_VERSIONS=()
for f in "$FIXTURE_DIR"/*.yml; do
    [[ -f "$f" ]] || continue
    v=$(basename "$f" .yml)
    cp "$f" "$SCRATCH/v_$v"
    OLD_VERSIONS+=("$v")
done

# Every version reachable in git history (old seed/ path and new home) that
# differs from the working-tree template. Empty in a shallow clone.
historical_versions() {
    local c
    git -C "$PROJECT_DIR" log --format=%H -- "$OLD_TEMPLATE_REL" "$TEMPLATE_REL" 2>/dev/null |
    while read -r c; do
        git -C "$PROJECT_DIR" show "$c:$OLD_TEMPLATE_REL" > "$SCRATCH/h_$c" 2>/dev/null ||
            git -C "$PROJECT_DIR" show "$c:$TEMPLATE_REL" > "$SCRATCH/h_$c" 2>/dev/null ||
            { rm -f "$SCRATCH/h_$c"; continue; }
        cmp -s "$SCRATCH/h_$c" "$TEMPLATE" && { rm -f "$SCRATCH/h_$c"; continue; }
        echo "$c"
    done
}
mapfile -t HISTORY_VERSIONS < <(historical_versions)

echo "--- (b) earlier shipped templates are refreshed (${#OLD_VERSIONS[@]} versions) ---"
TOTAL=$((TOTAL + 1))
if [[ "${#OLD_VERSIONS[@]}" -gt 0 ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: (b) no earlier template fixtures in $FIXTURE_DIR"
fi
for c in "${OLD_VERSIONS[@]}"; do
    mkdir -p "$(dirname "$WF")"
    cp "$SCRATCH/v_$c" "$WF"
    run_setup
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$TEMPLATE"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (b) version $c was not refreshed"; cat "$SCRATCH/out" "$SCRATCH/err"
    fi
    assert_contains "(b) $c reports update" "Updated contribution check workflow" "$(cat "$SCRATCH/out")"
done

echo "--- (b2) a git-clean CRLF checkout (core.autocrlf=true) of an old template is refreshed ---"
# Windows checkouts hold CRLF bytes for a file git reports as unmodified; the
# LF-only hashes must still recognise it.
OLDEST="${OLD_VERSIONS[0]:-}"
TOTAL=$((TOTAL + 1))
if [[ -n "$OLDEST" ]]; then
    PASS=$((PASS + 1))
    git -C "$PROJ" config core.autocrlf true
    mkdir -p "$(dirname "$WF")"
    cp "$SCRATCH/v_$OLDEST" "$WF"
    git -C "$PROJ" add .github/workflows/contribution-check.yml
    git -C "$PROJ" -c user.name=t -c user.email=t@example.com commit --quiet -m "old workflow"
    rm -f "$WF"
    git -C "$PROJ" checkout -- .github/workflows/contribution-check.yml
    assert_eq "(b2) fixture: checkout is CRLF" "1" "$(grep -c $'\r$' "$WF" | awk '{print ($1 > 0)}')"
    assert_eq "(b2) fixture: git reports the file clean" "" \
        "$(git -C "$PROJ" status --porcelain -- .github/workflows/contribution-check.yml)"
    run_setup
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$TEMPLATE"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (b2) CRLF checkout of $OLDEST was not refreshed"; cat "$SCRATCH/out" "$SCRATCH/err"
    fi

    echo "--- (d2) a CRLF copy of the current template is up to date ---"
    awk '{ printf "%s\r\n", $0 }' "$TEMPLATE" > "$WF"
    cp "$WF" "$SCRATCH/crlf_current"
    run_setup
    assert_contains "(d2) CRLF current is up to date" "already installed (up to date)" "$(cat "$SCRATCH/out")"
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$SCRATCH/crlf_current"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (d2) CRLF current file was rewritten"; fi

    echo "--- (c2) a CRLF old template with a content edit is still customized ---"
    awk '{ printf "%s\r\n", $0 } END { printf "# my edit\r\n" }' "$SCRATCH/v_$OLDEST" > "$WF"
    cp "$WF" "$SCRATCH/crlf_custom"
    run_setup
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$SCRATCH/crlf_custom"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (c2) edited CRLF file was overwritten"; fi
    git -C "$PROJ" config --unset core.autocrlf
else
    FAIL=$((FAIL + 1)); echo "FAIL: (b2) no old template version available"
fi

echo "--- (c) a customized workflow is left alone ---"
printf '%s\n' "name: My own contribution check" "on: [push]" > "$WF"
cp "$WF" "$SCRATCH/custom"
run_setup
TOTAL=$((TOTAL + 1))
if cmp -s "$WF" "$SCRATCH/custom"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: (c) customized workflow was overwritten"
fi
assert_contains "(c) warns about local changes" "differs from every shipped template" "$(cat "$SCRATCH/out" "$SCRATCH/err")"

echo "--- (d) the current template is up to date ---"
cp "$TEMPLATE" "$WF"
run_setup
assert_contains "(d) up to date" "already installed (up to date)" "$(cat "$SCRATCH/out")"
TOTAL=$((TOTAL + 1))
if cmp -s "$WF" "$TEMPLATE"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (d) file changed"; fi

echo "--- (e) every earlier shipped version's hash is listed ---"
# A future template edit must append the outgoing version's sha256 to
# _CONTRIBUTION_WORKFLOW_SHIPPED_SHA256 (and add a fixture), or installs of it
# stop refreshing.
listed=$(bash -c 'source "$1/.aitask-scripts/aitask_setup.sh" --source-only && printf "%s\n" "${_CONTRIBUTION_WORKFLOW_SHIPPED_SHA256[@]}"' _ "$PROJECT_DIR")
_hash_of() {
    local hex
    hex=$(bash -c 'source "$1/.aitask-scripts/lib/terminal_compat.sh"; source "$1/.aitask-scripts/lib/artifact_utils.sh"; artifact_sha256 "$2"' _ "$PROJECT_DIR" "$1")
    printf '%s\n' "${hex#sha256:}"
}
for v in "${OLD_VERSIONS[@]}"; do
    hex=$(_hash_of "$SCRATCH/v_$v")
    TOTAL=$((TOTAL + 1))
    if printf '%s\n' "$listed" | grep -qxF "$hex"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (e) fixture $v's hash $hex missing from _CONTRIBUTION_WORKFLOW_SHIPPED_SHA256"
    fi
done
# Reverse direction: every listed hash has a committed fixture, so a future
# template edit that appends the outgoing hash but forgets the fixture cannot
# silently drop shallow-clone refresh coverage.
fixture_hashes=$(for v in "${OLD_VERSIONS[@]}"; do _hash_of "$SCRATCH/v_$v"; done)
while IFS= read -r known; do
    [[ -n "$known" ]] || continue
    TOTAL=$((TOTAL + 1))
    if printf '%s\n' "$fixture_hashes" | grep -qxF "$known"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (e) listed hash $known has no fixture under $FIXTURE_DIR"
    fi
done <<< "$listed"
if [[ "${#HISTORY_VERSIONS[@]}" -eq 0 ]]; then
    echo "NOTE: (e) no template history reachable (shallow clone?) — only the fixtures were checked"
fi
for c in "${HISTORY_VERSIONS[@]}"; do
    hex=$(_hash_of "$SCRATCH/h_$c")
    TOTAL=$((TOTAL + 1))
    if printf '%s\n' "$listed" | grep -qxF "$hex"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (e) ${c:0:9}'s template hash $hex missing from _CONTRIBUTION_WORKFLOW_SHIPPED_SHA256 (and add a fixture under $FIXTURE_DIR)"
    fi
done

echo "--- (g) an edit made while the update prompt is open is kept ---"
if [[ -n "$OLDEST" ]]; then
    cp "$SCRATCH/v_$OLDEST" "$WF"
    run_setup '_contribution_ci_confirm() { printf "# edited while the prompt was open\n" >> "$WF"; return 0; }'
    { cat "$SCRATCH/v_$OLDEST"; printf '# edited while the prompt was open\n'; } > "$SCRATCH/expected_edit"
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$SCRATCH/expected_edit"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (g) edit made during the update prompt was overwritten"
    fi
    assert_contains "(g) warns that the file changed during the prompt" "changed while the update prompt was open" "$(cat "$SCRATCH/out" "$SCRATCH/err")"
    TOTAL=$((TOTAL + 1))
    leftovers=("$(dirname "$WF")"/.contribution-check.yml.*)
    if [[ -e "${leftovers[0]}" ]]; then
        FAIL=$((FAIL + 1)); echo "FAIL: (g) staged temp file left behind"
    else
        PASS=$((PASS + 1))
    fi
    # A failed rename leaves the old file and no staged temp behind.
    cp "$SCRATCH/v_$OLDEST" "$WF"
    run_setup 'mv() { return 1; }'
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$SCRATCH/v_$OLDEST"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (g) failed rename changed the workflow"; fi
    assert_contains "(g) failed rename is reported" "Could not replace" "$(cat "$SCRATCH/out" "$SCRATCH/err")"
    leftovers=("$(dirname "$WF")"/.contribution-check.yml.*)
    TOTAL=$((TOTAL + 1))
    if [[ -e "${leftovers[0]}" ]]; then
        FAIL=$((FAIL + 1)); echo "FAIL: (g) failed rename left a staged temp: ${leftovers[*]}"
    else
        PASS=$((PASS + 1))
    fi
    # Control: the same seam with no edit refreshes, so (g) is the recheck working.
    cp "$SCRATCH/v_$OLDEST" "$WF"
    run_setup '_contribution_ci_confirm() { return 0; }'
    TOTAL=$((TOTAL + 1))
    if cmp -s "$WF" "$TEMPLATE"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (g) control: seam without an edit did not refresh"; fi
fi
rm -f "$WF"
run_setup '_contribution_ci_confirm() { printf "name: mine\n" > "$WF"; return 0; }'
assert_eq "(g) a file created during the install prompt is kept" "name: mine" "$(cat "$WF")"
assert_contains "(g) warns that the file appeared" "appeared while the install prompt was open" "$(cat "$SCRATCH/out" "$SCRATCH/err")"
rm -rf "$PROJ/.github"

echo "--- (h) GitLab / Bitbucket: existing configurations are never edited ---"
git -C "$PROJ" remote set-url origin https://gitlab.com/o/r.git
printf '%s\n' "stages: [build, deploy]" "build:" "  stage: build" "  script: [make]" > "$PROJ/.gitlab-ci.yml"
cp "$PROJ/.gitlab-ci.yml" "$SCRATCH/gitlab_before"
run_setup
TOTAL=$((TOTAL + 1))
if cmp -s "$PROJ/.gitlab-ci.yml" "$SCRATCH/gitlab_before"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (h) existing .gitlab-ci.yml was modified"; fi
assert_contains "(h) GitLab: manual-merge warning names the stage" "stage: test" "$(cat "$SCRATCH/out" "$SCRATCH/err")"
assert_contains "(h) GitLab: label step used the glab stub" "label create contribution" "$(cat "$SCRATCH/glab_calls")"
rm -f "$PROJ/.gitlab-ci.yml"
run_setup
assert_contains "(h) GitLab: absent config is created with the job" "contribution-check:" "$(cat "$PROJ/.gitlab-ci.yml" 2>/dev/null)"
rm -f "$PROJ/.gitlab-ci.yml"

git -C "$PROJ" remote set-url origin https://bitbucket.org/o/r.git
printf '%s\n' "pipelines:" "  default:" "    - step:" "        script: [make]" > "$PROJ/bitbucket-pipelines.yml"
cp "$PROJ/bitbucket-pipelines.yml" "$SCRATCH/bb_before"
run_setup
TOTAL=$((TOTAL + 1))
if cmp -s "$PROJ/bitbucket-pipelines.yml" "$SCRATCH/bb_before"; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (h) existing bitbucket-pipelines.yml was modified"; fi
assert_contains "(h) Bitbucket: manual-merge warning" "does not edit an existing CI configuration" "$(cat "$SCRATCH/out" "$SCRATCH/err")"
rm -f "$PROJ/bitbucket-pipelines.yml"
run_setup
assert_contains "(h) Bitbucket: absent config is created with the pipeline" "contribution-check:" "$(cat "$PROJ/bitbucket-pipelines.yml" 2>/dev/null)"
rm -f "$PROJ/bitbucket-pipelines.yml"
git -C "$PROJ" remote set-url origin https://github.com/o/r.git

echo "--- (f) missing templates warn and install nothing ---"
rm -rf "$PROJ/.github" "$PROJ/.aitask-scripts/ci_templates"
run_setup
assert_contains "(f) warns about missing templates" "CI templates not found" "$(cat "$SCRATCH/out" "$SCRATCH/err")"
TOTAL=$((TOTAL + 1))
if [[ ! -e "$WF" ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: (f) workflow installed without templates"; fi

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
