#!/usr/bin/env bash
# test_release_asset_contract.sh - pin_release_asset_contract (t2261_2): the
# framework's release publication policy must name exactly the assets its
# release workflows publish.
#
# If release.yml / release-packaging.yml gain, rename or drop an asset and the
# policy in aitasks/metadata/project_config.yaml is not updated, every
# wait_release_and_notify.sh run would wait for an asset that never appears (or
# post before one that does), and no release notice would ever be posted. This
# test derives the published names from the workflows and compares them with
# the policy, instantiated through the SAME template function the gate uses.
#
# Derived from the workflows:
#   - the `files:` entries of both softprops/action-gh-release steps in
#     release.yml (published under their basename; ${{ github.ref_name }} is
#     the tag);
#   - the `gh release upload` targets in release-packaging.yml (${VERSION} is
#     the version);
#   - one <cmd>_{version}_SHA256SUMS.txt per goengines/cmd/<cmd>: that is what
#     `goengines/dist/*` uploads besides the binaries the manifest lists, and
#     the binaries are covered by release_publication_checksum_manifests.
#
# Mutation control: a fake `files:` entry in a copy of release.yml must make
# the comparison fail.
#
# Run: bash tests/test_release_asset_contract.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

RELEASE_YML="$PROJECT_DIR/.github/workflows/release.yml"
PACKAGING_YML="$PROJECT_DIR/.github/workflows/release-packaging.yml"
CONFIG="$PROJECT_DIR/aitasks/metadata/project_config.yaml"
SAMPLE_TAG="v9.8.7"
SAMPLE_VERSION="9.8.7"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_release_asset_contract_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

if [[ ! -f "$CONFIG" ]]; then
    echo "FAIL: $CONFIG is missing (this test needs the framework's task data)"
    exit 1
fi

SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
# shellcheck source=../.aitask-scripts/lib/task_utils.sh
. "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
# shellcheck source=../.aitask-scripts/lib/release_publication.sh
. "$PROJECT_DIR/.aitask-scripts/lib/release_publication.sh"

# workflow_release_files <release.yml> — the `files: |` block entries of every
# action-gh-release step, one per line, verbatim.
workflow_release_files() {
    awk '
        /uses:[[:space:]]*softprops\/action-gh-release/ { in_step = 1; next }
        # The next step (or job) ends this one.
        in_step && /^[[:space:]]*-[[:space:]]*(name|uses):/ { in_step = 0; in_files = 0 }
        in_step && /^[[:space:]]*files:[[:space:]]*\|[[:space:]]*$/ {
            in_files = 1
            match($0, /^[[:space:]]*/); key_indent = RLENGTH
            next
        }
        in_files {
            if ($0 ~ /^[[:space:]]*$/) next
            match($0, /^[[:space:]]*/)
            if (RLENGTH <= key_indent) { in_files = 0; next }
            line = $0; sub(/^[[:space:]]+/, "", line); sub(/[[:space:]]+$/, "", line)
            print line
        }
    ' "$1"
}

# packaging_uploads <release-packaging.yml> — the file argument of every
# `gh release upload "<tag>" "<file>"` line.
packaging_uploads() {
    sed -n 's/.*gh release upload "[^"]*" "\([^"]*\)".*/\1/p' "$1"
}

# expected_assets <release.yml> <release-packaging.yml> — instantiated for the
# sample tag, sorted; `goengines/dist/*` is expanded to its SHA256SUMS files.
expected_assets() {
    local f name cmd
    while IFS= read -r f; do
        [[ -n "$f" ]] || continue
        if [[ "$f" == "goengines/dist/*" ]]; then
            for cmd in "$PROJECT_DIR"/goengines/cmd/*/; do
                cmd="$(basename "$cmd")"
                printf '%s_%s_SHA256SUMS.txt\n' "$cmd" "$SAMPLE_VERSION"
            done
            continue
        fi
        name="$(basename "$f")"
        name="${name//'${{ github.ref_name }}'/$SAMPLE_TAG}"
        printf '%s\n' "$name"
    done < <(workflow_release_files "$1")
    while IFS= read -r f; do
        [[ -n "$f" ]] || continue
        f="${f//'${VERSION}'/$SAMPLE_VERSION}"
        printf '%s\n' "$f"
    done < <(packaging_uploads "$2")
}

assert_exit_zero "the framework policy loads" release_publication_policy_load "$CONFIG"
release_publication_policy_load "$CONFIG"

POLICY_SET="$(release_publication_expand_assets "$SAMPLE_TAG" | sort -u)"
EXPECTED_SET="$(expected_assets "$RELEASE_YML" "$PACKAGING_YML" | sort -u)"

assert_eq "extraction sanity: both release steps found" "2" \
    "$(grep -c 'uses:[[:space:]]*softprops/action-gh-release' "$RELEASE_YML")"
assert_contains "extraction sanity: the tarball is a release file" \
    "aitasks-$SAMPLE_TAG.tar.gz" "$EXPECTED_SET"
assert_contains "extraction sanity: the .deb upload is found" \
    "aitasks_${SAMPLE_VERSION}_all.deb" "$EXPECTED_SET"
assert_eq "policy assets == workflow-published assets" "$EXPECTED_SET" "$POLICY_SET"

# goengines/dist/* also uploads the binaries: the manifest glob must cover the
# SUMS files, so every binary a manifest lists is checked as an asset.
if grep -q 'goengines/dist/\*' "$RELEASE_YML"; then
    for cmd in "$PROJECT_DIR"/goengines/cmd/*/; do
        sums="$(basename "$cmd")_${SAMPLE_VERSION}_SHA256SUMS.txt"
        covered=0
        for glob in "${RP_MANIFESTS[@]}"; do
            # shellcheck disable=SC2053  # the glob IS the pattern
            [[ "$sums" == $glob ]] && covered=1
        done
        assert_eq "manifest glob covers $sums" "1" "$covered"
    done
fi

assert_eq "the policy names release.yml as the workflow" "release.yml" "$RP_WORKFLOW"
assert_exit_zero "release.yml still runs packaging in the same workflow run" \
    grep -qE '^[[:space:]]*uses:[[:space:]]*\./\.github/workflows/release-packaging\.yml[[:space:]]*$' "$RELEASE_YML"

# --- Mutation control --------------------------------------------------------
MUT="$TMP/release.yml"
awk '{ print } /^[[:space:]]*files:[[:space:]]*\|/ && !done { match($0, /^[[:space:]]*/); printf "%*s  extra-asset-${{ github.ref_name }}.zip\n", RLENGTH, ""; done = 1 }' \
    "$RELEASE_YML" > "$MUT"
MUT_SET="$(expected_assets "$MUT" "$PACKAGING_YML" | sort -u)"
assert_contains "mutation control: the fake entry is extracted" "extra-asset-$SAMPLE_TAG.zip" "$MUT_SET"
if [[ "$MUT_SET" == "$POLICY_SET" ]]; then
    assert_record_fail
    echo "FAIL: mutation control: a fake files: entry did not change the comparison"
else
    assert_record_pass
fi

echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
