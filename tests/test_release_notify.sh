#!/usr/bin/env bash
# test_release_notify.sh - `ait release-notify` (aitask_release_notify.sh,
# t2261_2) against legacy-mode fixture repos with scenario-driven gh / glab
# stubs (tests/lib/release_notify_fixture.sh).
#
# Coverage:
#   (a) classification: due, child commits under a parent, no commits,
#       SHIPPED_EARLIER with the exact retry command; dry run changes nothing
#   (b) posting + the move into released/<tag>/; generic policy only
#   (c) the SHIPPED_EARLIER retry command posts once, then nothing
#   (d) a marker already present: no post, outcome already_present
#   (e) a partial post failure, then a retry posts only the remainder
#   (f) an unknown comment listing posts nothing
#   (g) designation: unset, another host, invalid, dry run informational
#   (h) missing and draft releases; (i) tag_mismatch; (j) refused tags
#   (k) the run lock held by another run
#   (l) the policy configured: run in progress / failed, assets missing, a
#       SUMS-listed binary missing, an unknown placeholder, a block mapping;
#       each direct and through the --tag E recovery form; then complete
#   (n) policy formatting: quoted / single-quoted keys, a flow-mapping
#       document, duplicate keys, a non-mapping document, a failing or
#       truncating reader, an unreadable file, a missing file
#   (o) GitLab: manifests through glab release download, a missing link,
#       a failing download, upcoming
#   (p) interrupted moves (SIGKILL at after_publish / after_remove, and the
#       same states built by hand) are completed by the next run, no new post
#   (q) residue that does not verify is refused and left untouched
#   (r) a pending record carrying released-only keys is MALFORMED
#   (s) a marker early in a long thread is found (no SIGPIPE false negative)
#   (t) freshness under a restricted remote.origin.fetch refspec
#   (u) an early move failure leaves the caller's run lock intact
#   (v) thousands of tags: tag selection and the SHIPPED_EARLIER lookup
#   (w) --list works with no tags at all
#   (x) a failed git tag enumeration (empty or partial output) and a failed
#       containing-tag lookup are reported, never read as a short list
#
# Duplicate prevention is asserted for serialised and sequential runs only; it
# is not, and is not claimed to be, an exactly-once guarantee.
#
# All assertions run in the main shell, so the in-process counters are enough.
#
# Run: bash tests/test_release_notify.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config

PASS=0
FAIL=0
TOTAL=0

command -v jq >/dev/null 2>&1 || { echo "SKIP: jq is required by the gh/glab stubs"; exit 0; }

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_release_notify_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
AITASKS_LOCK_DIR="$TMP/locks"
export AITASKS_LOCK_DIR
mkdir -p "$AITASKS_LOCK_DIR"

. "$PROJECT_DIR/tests/lib/release_notify_fixture.sh"
rnf_write_stubs

N=0
# new_repo [origin-url] — a fresh fixture repo in REPO, with fresh stub state.
new_repo() {
    N=$((N + 1))
    mkdir -p "$TMP/r$N"
    REPO="$(rnf_make_repo "$TMP/r$N" "${1:-}")"
    rnf_reset_state
}
sha_of() { git -C "$REPO" rev-parse "$1^{commit}"; }
posts() { rnf_log_count '^gh issue comment\|^glab issue note'; }
is_clean() { git -C "$REPO" status --porcelain -- aitasks/metadata/release_issues; }
gen_release() { rnf_release "$1" 1 false; }   # a published, asset-less release

# ---------------------------------------------------------------------------
# (a) classification, dry run
new_repo
P20="$(rnf_record "$REPO" 20 https://github.com/o/r/issues/20)"
P30="$(rnf_record "$REPO" 30 https://github.com/o/r/issues/30)"
rnf_record "$REPO" 30_2 https://github.com/o/r/issues/302 >/dev/null
P10="$(rnf_record "$REPO" 10 https://github.com/o/r/issues/10)"
rnf_record "$REPO" 70 https://github.com/o/r/issues/70 >/dev/null
gen_release v1.1.0
head_before="$(git -C "$REPO" rev-parse HEAD)"
rnf_run "$REPO" --dry-run --tag v1.1.0
assert_eq "(a) dry run exit 0" "0" "$RNF_RC"
assert_contains "(a) range" "RANGE:v1.0.0..v1.1.0" "$RNF_OUT"
assert_contains "(a) t20 due" "DUE:20|https://github.com/o/r/issues/20|1" "$RNF_OUT"
assert_contains "(a) child commit due under parent t30" "DUE:30|https://github.com/o/r/issues/30|1" "$RNF_OUT"
assert_contains "(a) child id t30_2 has no commits" "PENDING:30_2|https://github.com/o/r/issues/302|no_commits" "$RNF_OUT"
assert_contains "(a) t70 after the tag" "PENDING:70|https://github.com/o/r/issues/70|no_commits" "$RNF_OUT"
assert_contains "(a) t10 shipped earlier" "SHIPPED_EARLIER:10|https://github.com/o/r/issues/10|v1.0.0" "$RNF_OUT"
assert_contains "(a) exact retry command" "Notify it with: ait release-notify --tag v1.0.0" "$RNF_OUT"
assert_contains "(a) dry run reports freshness" "FRESHNESS:fresh" "$RNF_OUT"
assert_contains "(a) dry run reports designation" "DESIGNATION:designated:testhost" "$RNF_OUT"
assert_contains "(a) dry run reports publication" "PUBLICATION:published|-" "$RNF_OUT"
assert_eq "(a) dry run posts nothing" "0" "$(posts)"
assert_eq "(a) dry run commits nothing" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"
assert_file_exists "(a) dry run moves nothing" "$REPO/$P20"

# ---------------------------------------------------------------------------
# (b) posting, the move, generic policy only
rnf_run "$REPO" --tag v1.1.0 --no-push
assert_eq "(b) exit 0" "0" "$RNF_RC"
R20="aitasks/metadata/release_issues/released/v1.1.0/$(basename "$P20")"
R30="aitasks/metadata/release_issues/released/v1.1.0/$(basename "$P30")"
assert_contains "(b) t20 posted" "POSTED:20|https://github.com/o/r/issues/20|$R20" "$RNF_OUT"
assert_contains "(b) t30 posted" "POSTED:30|https://github.com/o/r/issues/30|$R30" "$RNF_OUT"
assert_eq "(b) two posts" "2" "$(posts)"
assert_file_not_exists "(b) pending t20 gone" "$REPO/$P20"
assert_file_exists "(b) released t20" "$REPO/$R20"
assert_eq "(b) ledger clean" "" "$(is_clean)"
assert_exit_zero "(b) released record validates" rnf_lib "$REPO" ril_validate_released_record "$R20"
assert_contains "(b) released fields" "outcome=posted" "$(cat "$REPO/$R20")"
assert_contains "(b) released commits" "commits=$(git -C "$REPO" log --format=%H --grep='(t20)')" "$(cat "$REPO/$R20")"
body30="$(cat "$RNF_STATE/comments/o_r_30/1")"
assert_contains "(b) marker" "<!-- aitask-release:v1.1.0 t30 -->" "$body30"
assert_contains "(b) heading" "## Released in v1.1.0" "$body30"
assert_contains "(b) release link" "[v1.1.0](https://github.com/o/r/releases/tag/v1.1.0)" "$body30"
assert_contains "(b) child commit listed" "feature: c (t30_1)" "$body30"
assert_eq "(b) generic policy: no run list" "0" "$(rnf_log_count '^gh run list')"
assert_eq "(b) generic policy: no download" "0" "$(rnf_log_count '^gh release download')"
assert_contains "(b) one commit per record" "ait: Record release notice for t" "$(git -C "$REPO" log -2 --format=%s)"
assert_eq "(b) the move commit holds exactly both paths" \
    "$(printf '%s\n%s' "$P30" "$R30" | sort)" \
    "$(git -C "$REPO" log -1 --no-renames --format= --name-only --grep='t30 (v1.1.0)' | sort)"
assert_contains "(b) summary" "SUMMARY:posted=2 already=0 resumed=0 pending=2 shipped_earlier=1 failed=0 malformed=0" "$RNF_OUT"
rnf_run "$REPO" --tag v1.1.0 --no-push
assert_eq "(b) second run exit 0" "0" "$RNF_RC"
assert_eq "(b) second run posts nothing" "2" "$(posts)"

# ---------------------------------------------------------------------------
# (c) the SHIPPED_EARLIER retry command
gen_release v1.0.0
rnf_run "$REPO" --tag v1.0.0 --no-push
assert_eq "(c) exit 0" "0" "$RNF_RC"
assert_contains "(c) t10 posted for v1.0.0" "POSTED:10|https://github.com/o/r/issues/10" "$RNF_OUT"
assert_eq "(c) one comment on #10" "1" "$(rnf_comment_count o_r_10)"
assert_contains "(c) names v1.0.0" "## Released in v1.0.0" "$(cat "$RNF_STATE/comments/o_r_10/1")"
rnf_run "$REPO" --tag v1.0.0 --no-push
assert_eq "(c) second run: still one comment" "1" "$(rnf_comment_count o_r_10)"

# ---------------------------------------------------------------------------
# (d) a marker already present
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
mkdir -p "$RNF_STATE/comments/o_r_50"
printf 'earlier text\n<!-- aitask-release:v1.2.0 t50 -->\nmore' > "$RNF_STATE/comments/o_r_50/1"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(d) exit 0" "0" "$RNF_RC"
assert_contains "(d) already notified" "ALREADY_NOTIFIED:50|https://github.com/o/r/issues/50" "$RNF_OUT"
assert_eq "(d) no post" "0" "$(posts)"
assert_contains "(d) outcome recorded" "outcome=already_present" \
    "$(cat "$REPO/aitasks/metadata/release_issues/released/v1.2.0/$(basename "$P50")")"

# ---------------------------------------------------------------------------
# (e) a partial failure, then a retry
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
P60="$(rnf_record "$REPO" 60 https://github.com/o/r/issues/60)"
gen_release v1.2.0
: > "$RNF_STATE/fail_post_60"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(e) partial: exit 4" "4" "$RNF_RC"
assert_contains "(e) t50 posted" "POSTED:50|" "$RNF_OUT"
assert_contains "(e) t60 failed" "FAILED:60|https://github.com/o/r/issues/60|post_failed" "$RNF_OUT"
assert_file_exists "(e) t60 stays pending" "$REPO/$P60"
rm -f "$RNF_STATE/fail_post_60"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(e) retry exit 0" "0" "$RNF_RC"
assert_contains "(e) retry posts t60" "POSTED:60|" "$RNF_OUT"
assert_not_contains "(e) retry does not touch t50" "50|" "$RNF_OUT"
assert_eq "(e) #50 has one comment" "1" "$(rnf_comment_count o_r_50)"
assert_eq "(e) #60 has one comment" "1" "$(rnf_comment_count o_r_60)"

# ---------------------------------------------------------------------------
# (f) an unknown comment listing
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
: > "$RNF_STATE/fail_list"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(f) exit 4" "4" "$RNF_RC"
assert_contains "(f) unknown listing" "FAILED:50|https://github.com/o/r/issues/50|comment_list_unknown" "$RNF_OUT"
assert_eq "(f) no post" "0" "$(posts)"
assert_file_exists "(f) stays pending" "$REPO/$P50"

# ---------------------------------------------------------------------------
# (g) designation
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
rnf_config "$REPO" $'# no host\n'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(g) unset: exit 3" "3" "$RNF_RC"
assert_contains "(g) unset" "INCOMPLETE:designation:unset" "$RNF_OUT"
assert_contains "(g) unset: hint names the key line" "release_notify_host: testhost" "$RNF_OUT"
rnf_config "$REPO" $'release_notify_host: buildbox\n'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(g) other host: exit 3" "3" "$RNF_RC"
assert_contains "(g) other host" "INCOMPLETE:designation:not_designated:buildbox|testhost" "$RNF_OUT"
assert_contains "(g) other host: hint names it" "notifications run only on buildbox" "$RNF_OUT"
rnf_config "$REPO" $'release_notify_host: "bad host"\n'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(g) invalid: exit 3" "3" "$RNF_RC"
assert_contains "(g) invalid" "INCOMPLETE:policy_unreadable:release_notify_host" "$RNF_OUT"
rnf_config "$REPO" $'release_notify_host: buildbox\n'
rnf_run "$REPO" --tag v1.2.0 --dry-run
assert_eq "(g) dry run does not require it" "0" "$RNF_RC"
assert_contains "(g) dry run reports it" "DESIGNATION:not_designated:buildbox|testhost" "$RNF_OUT"
assert_eq "(g) no post in any case" "0" "$(posts)"
assert_file_exists "(g) stays pending" "$REPO/$P50"
rnf_config "$REPO" $'release_notify_host: testhost\n'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(g) match: posts" "1" "$(posts)"

# ---------------------------------------------------------------------------
# (h) missing and draft releases
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(h) missing: exit 3" "3" "$RNF_RC"
assert_contains "(h) missing" "INCOMPLETE:not_published:pending:no_release" "$RNF_OUT"
rnf_run "$REPO" --tag v1.2.0 --dry-run
assert_contains "(h) dry run still lists DUE" "DUE:50|" "$RNF_OUT"
assert_contains "(h) dry run reports it" "PUBLICATION:pending:no_release" "$RNF_OUT"
rnf_release v1.2.0 1 true
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(h) draft: exit 3" "3" "$RNF_RC"
assert_contains "(h) draft" "INCOMPLETE:not_published:pending:draft" "$RNF_OUT"
rnf_release_raw v1.2.0 1 ERR
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_contains "(h) API error is unknown" "INCOMPLETE:not_published:unknown:api_error" "$RNF_OUT"
assert_eq "(h) no post" "0" "$(posts)"
assert_file_exists "(h) stays pending" "$REPO/$P50"

# ---------------------------------------------------------------------------
# (i) the remote tag at another commit
gen_release v1.2.0
git -C "$REPO" push -qf origin "$(sha_of v1.1.0):refs/tags/v1.2.0" 2>/dev/null
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(i) exit 3" "3" "$RNF_RC"
assert_contains "(i) tag mismatch" "INCOMPLETE:not_published:failed:tag_mismatch" "$RNF_OUT"
assert_eq "(i) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (j) refused input
rnf_run "$REPO" --tag 'v1;rm'
assert_eq "(j) invalid tag: exit 2" "2" "$RNF_RC"
rnf_run "$REPO" --tag v9.9.9
assert_eq "(j) missing tag: exit 2" "2" "$RNF_RC"
rnf_run "$REPO" --bogus
assert_eq "(j) usage: exit 1" "1" "$RNF_RC"

# ---------------------------------------------------------------------------
# (k) the run lock held by another run
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
(
    cd "$REPO" || exit 1
    SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    . "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
    . "$PROJECT_DIR/.aitask-scripts/lib/release_issue_ledger.sh"
    STALE_LOCK_IDENTITY_PID=$BASHPID
    export STALE_LOCK_IDENTITY_PID
    ait_ledger_lock_acquire release_notify run a b
    : > "$TMP/holder_ready"
    sleep 30
) >/dev/null 2>&1 &
holder=$!
for _ in $(seq 50); do [[ -f "$TMP/holder_ready" ]] && break; sleep 0.1; done
rnf_run "$REPO" --tag v1.2.0 --no-push
kill "$holder" 2>/dev/null; wait "$holder" 2>/dev/null
rm -rf "$AITASKS_LOCK_DIR"/*release_notify*
assert_eq "(k) exit 3" "3" "$RNF_RC"
assert_contains "(k) busy" "INCOMPLETE:run_lock:busy" "$RNF_OUT"
assert_eq "(k) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (l) the publication policy configured
POLICY=$'release_notify_host: testhost\nrelease_publication_workflow: release.yml\nrelease_publication_assets:\n  - myapp-{tag}.tar.gz\n  - myapp_{version}_all.deb\n  - tool_{version}_SHA256SUMS.txt\nrelease_publication_checksum_manifests: "*_SHA256SUMS.txt"\n'
HEX="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
# full_release <tag> — every policy asset uploaded, the SUMS listing its binary.
full_release() {
    local v="${1#v}"
    rnf_release "$1" 1 false "myapp-$1.tar.gz:uploaded:10" "myapp_${v}_all.deb:uploaded:10" \
        "tool_${v}_SHA256SUMS.txt:uploaded:80" "tool_${v}_linux_amd64:uploaded:99"
    rnf_asset "$1" "tool_${v}_SHA256SUMS.txt" "$HEX  tool_${v}_linux_amd64"$'\n'
}
good_run() { rnf_runs "$1" 1 "77 $(sha_of "$1") $1 completed success"; }
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
P10="$(rnf_record "$REPO" 10 https://github.com/o/r/issues/10)"
rnf_config "$REPO" "$POLICY"
# scenario <label> <setup-fn> <expected INCOMPLETE line> — direct (v1.2.0, t50
# due) and recovery (--tag v1.0.0, t10 due) forms.
scenario() {
    local label="$1" setup="$2" expect="$3" t
    for t in v1.2.0 v1.0.0; do
        rnf_reset_state
        full_release "$t"; good_run "$t"
        "$setup" "$t"
        rnf_run "$REPO" --tag "$t" --no-push
        assert_eq "(l) $label [$t]: exit 3" "3" "$RNF_RC"
        assert_contains "(l) $label [$t]" "$expect" "$RNF_OUT"
        assert_eq "(l) $label [$t]: no post" "0" "$(posts)"
    done
    assert_file_exists "(l) $label: t50 pending" "$REPO/$P50"
    assert_file_exists "(l) $label: t10 pending" "$REPO/$P10"
}
s_in_progress() { rnf_runs "$1" 1 "77 $(sha_of "$1") $1 in_progress "; }
s_failed() { rnf_runs "$1" 1 "77 $(sha_of "$1") $1 completed failure"; }
s_no_deb() {
    local v="${1#v}"
    rnf_release "$1" 1 false "myapp-$1.tar.gz:uploaded:10" "tool_${v}_SHA256SUMS.txt:uploaded:80" \
        "tool_${v}_linux_amd64:uploaded:99"
}
s_no_binary() {
    local v="${1#v}"
    rnf_release "$1" 1 false "myapp-$1.tar.gz:uploaded:10" "myapp_${v}_all.deb:uploaded:10" \
        "tool_${v}_SHA256SUMS.txt:uploaded:80"
}
s_placeholder() { rnf_config "$REPO" "${POLICY/myapp-\{tag\}/myapp-\{name\}}"; }
s_block_map() {
    rnf_config "$REPO" $'release_notify_host: testhost\nrelease_publication_workflow:\n  file: release.yml\n'
}
scenario "run in progress" s_in_progress "INCOMPLETE:not_published:pending:run_in_progress"
scenario "run failed" s_failed "INCOMPLETE:not_published:failed:workflow_failed:failure"
scenario "deb missing" s_no_deb "INCOMPLETE:not_published:pending:assets_missing:myapp_"
scenario "SUMS binary missing" s_no_binary "INCOMPLETE:not_published:pending:assets_missing:tool_"
scenario "unknown placeholder" s_placeholder "INCOMPLETE:policy_unreadable:release_publication_assets"
rnf_config "$REPO" "$POLICY"
scenario "block mapping" s_block_map "INCOMPLETE:policy_unreadable:release_publication_workflow"
rnf_config "$REPO" "$POLICY"
# A run for the same tag at another commit does not count.
rnf_reset_state
full_release v1.2.0
rnf_runs v1.2.0 1 "90 $(sha_of v1.1.0) v1.2.0 completed success"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_contains "(l) a run at another sha is ignored" "INCOMPLETE:not_published:pending:run_not_found" "$RNF_OUT"
# Complete: posts once.
rnf_reset_state
full_release v1.2.0; good_run v1.2.0
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(l) complete: exit 0" "0" "$RNF_RC"
assert_contains "(l) complete: published with the run id" "PUBLICATION:published|77" "$RNF_OUT"
assert_contains "(l) complete: posted" "POSTED:50|" "$RNF_OUT"
assert_eq "(l) complete: one post" "1" "$(posts)"

# ---------------------------------------------------------------------------
# (n) policy formatting must not change what is enforced
new_repo
gen_release v1.2.0
fmt_case() {
    local label="$1" yaml="$2" expect="$3"
    rnf_config "$REPO" "$yaml"
    rnf_run "$REPO" --tag v1.2.0 --dry-run
    assert_contains "(n) $label" "$expect" "$RNF_OUT"
}
fmt_case "plain keys enforce the workflow" \
    $'release_publication_workflow: release.yml\n' "PUBLICATION:pending:run_not_found"
fmt_case "double-quoted key" \
    $'"release_publication_workflow": release.yml\n' "PUBLICATION:pending:run_not_found"
fmt_case "single-quoted key" \
    $'\'release_publication_workflow\': release.yml\n' "PUBLICATION:pending:run_not_found"
fmt_case "flow-mapping document" \
    $'{release_notify_host: testhost, release_publication_workflow: release.yml}\n' "PUBLICATION:pending:run_not_found"
fmt_case "flow-mapping assets" \
    $'{release_publication_assets: ["myapp-{tag}.tar.gz"]}\n' "PUBLICATION:pending:assets_missing:myapp-v1.2.0.tar.gz"
fmt_case "duplicate key" \
    $'release_publication_workflow: a.yml\nrelease_publication_workflow: release.yml\n' "PUBLICATION:unknown:policy_unreadable:duplicate_key"
fmt_case "non-mapping document" $'- release.yml\n' "PUBLICATION:unknown:policy_unreadable:document"
fmt_case "broken YAML" $'release_publication_workflow: [a\n' "PUBLICATION:unknown:policy_unreadable:yaml_error"
fmt_case "empty value is absent" $'release_publication_workflow:\n' "PUBLICATION:published|-"
rnf_config "$REPO" $'release_publication_workflow: release.yml\n'
printf '#!/usr/bin/env bash\nexit 1\n' > "$TMP/py_fail"
printf '#!/usr/bin/env bash\nprintf "VAL\\trelease_publication_workflow\\trelease.yml\\n"\n' > "$TMP/py_trunc"
chmod +x "$TMP/py_fail" "$TMP/py_trunc"
AIT_PYTHON="$TMP/py_fail" rnf_run "$REPO" --tag v1.2.0 --dry-run
assert_contains "(n) failing reader" "PUBLICATION:unknown:policy_unreadable:" "$RNF_OUT"
AIT_PYTHON="$TMP/py_trunc" rnf_run "$REPO" --tag v1.2.0 --dry-run
assert_contains "(n) truncated reader (no OK)" "PUBLICATION:unknown:policy_unreadable:reader_failed" "$RNF_OUT"
if [[ "$(id -u)" != 0 ]]; then
    chmod 000 "$REPO/aitasks/metadata/project_config.yaml"
    rnf_run "$REPO" --tag v1.2.0 --dry-run
    chmod 644 "$REPO/aitasks/metadata/project_config.yaml"
    assert_contains "(n) unreadable file" "PUBLICATION:unknown:policy_unreadable:read_error" "$RNF_OUT"
fi
rm -f "$REPO/aitasks/metadata/project_config.yaml"
rnf_run "$REPO" --tag v1.2.0 --dry-run
assert_contains "(n) missing file: generic" "PUBLICATION:published|-" "$RNF_OUT"
assert_contains "(n) missing file: no designation" "DESIGNATION:unset" "$RNF_OUT"

# ---------------------------------------------------------------------------
# (o) GitLab: releases API, links, manifests through glab release download
new_repo https://gitlab.com/g/p.git
rnf_record "$REPO" 50 https://gitlab.com/g/p/-/issues/9 gitlab >/dev/null
rnf_config "$REPO" $'release_notify_host: testhost\nrelease_publication_assets: ["myapp-{tag}.tar.gz"]\nrelease_publication_checksum_manifests: "*_SHA256SUMS.txt"\n'
glab_rel() {
    mkdir -p "$RNF_STATE/glab_release/v1.2.0"
    printf '%s\n' "$1" > "$RNF_STATE/glab_release/v1.2.0/1"
}
LINKS='{"name":"myapp-v1.2.0.tar.gz"},{"name":"tool_1.2.0_SHA256SUMS.txt"}'
glab_rel '{"tag_name":"v1.2.0","upcoming_release":false,"assets":{"links":['"$LINKS"',{"name":"tool_1.2.0_linux_amd64"}]}}'
rnf_asset v1.2.0 tool_1.2.0_SHA256SUMS.txt "$HEX *tool_1.2.0_linux_amd64"$'\n'
: > "$RNF_STATE/fail_glab_download"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_contains "(o) failing download is unknown" "INCOMPLETE:not_published:unknown:api_error" "$RNF_OUT"
rm -f "$RNF_STATE/fail_glab_download"
glab_rel '{"tag_name":"v1.2.0","upcoming_release":false,"assets":{"links":['"$LINKS"']}}'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_contains "(o) SUMS-listed link missing" "INCOMPLETE:not_published:pending:assets_missing:tool_1.2.0_linux_amd64" "$RNF_OUT"
glab_rel '{"tag_name":"v1.2.0","upcoming_release":true,"assets":{"links":[]}}'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_contains "(o) upcoming" "INCOMPLETE:not_published:pending:upcoming" "$RNF_OUT"
assert_eq "(o) nothing posted so far" "0" "$(posts)"
glab_rel '{"tag_name":"v1.2.0","upcoming_release":false,"assets":{"links":['"$LINKS"',{"name":"tool_1.2.0_linux_amd64"}]}}'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(o) complete: exit 0" "0" "$RNF_RC"
assert_contains "(o) complete: posted" "POSTED:50|https://gitlab.com/g/p/-/issues/9" "$RNF_OUT"
assert_eq "(o) one glab note" "1" "$(rnf_comment_count g_p_9)"
assert_contains "(o) GitLab release link" "(https://gitlab.com/g/p/-/releases/v1.2.0)" "$(cat "$RNF_STATE/comments/g_p_9/1")"
assert_contains "(o) downloaded with glab" "glab release download v1.2.0" "$(cat "$STUB_LOG")"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(o) re-run: still one note" "1" "$(rnf_comment_count g_p_9)"
rnf_config "$REPO" $'release_notify_host: testhost\nrelease_publication_workflow: release.yml\n'
rnf_run "$REPO" --tag v1.2.0 --dry-run
assert_contains "(o) workflow on GitLab is refused" "PUBLICATION:unknown:workflow_unsupported" "$RNF_OUT"

# ---------------------------------------------------------------------------
# (p) interrupted moves are completed by the next run, with no new comment
RIL_ROOT="aitasks/metadata/release_issues"
interrupted() {
    local point="$1" pending released
    new_repo
    pending="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
    released="$RIL_ROOT/released/v1.2.0/$(basename "$pending")"
    gen_release v1.2.0
    : > "$AITASKS_LOCK_DIR/.ril_move_test_seams"
    _RIL_MOVE_TEST_SEAM="$point" rnf_run "$REPO" --tag v1.2.0 --no-push
    rm -f "$AITASKS_LOCK_DIR/.ril_move_test_seams"
    assert_contains "(p) $point: the seam fired" "TEST SEAM ACTIVE" "$RNF_ERR"
    assert_eq "(p) $point: partial run exits 4" "4" "$RNF_RC"
    assert_contains "(p) $point: the move died" "FAILED:50|https://github.com/o/r/issues/50|move_died_rc_137" "$RNF_OUT"
    assert_eq "(p) $point: one comment posted" "1" "$(rnf_comment_count o_r_50)"
    assert_file_exists "(p) $point: released residue" "$REPO/$released"
    if [[ "$point" == after_publish ]]; then
        assert_file_exists "(p) $point: pending still there" "$REPO/$pending"
    else
        assert_file_not_exists "(p) $point: pending removed" "$REPO/$pending"
    fi
    rnf_run "$REPO" --tag v1.2.0 --dry-run
    assert_contains "(p) $point: dry run reports the residue" "RESIDUE:$released|released" "$RNF_OUT"
    resumed_ok "$point" "$pending" "$released"
}
# resumed_ok <label> <pending> <released> — the retry completes the move.
resumed_ok() {
    local label="$1" pending="$2" released="$3" head_before
    head_before="$(git -C "$REPO" rev-parse HEAD)"
    rnf_run "$REPO" --tag v1.2.0 --no-push
    assert_eq "(p) $label: retry exit 0" "0" "$RNF_RC"
    assert_contains "(p) $label: resumed" "RESUMED:50|https://github.com/o/r/issues/50|$released" "$RNF_OUT"
    assert_eq "(p) $label: no new comment" "1" "$(rnf_comment_count o_r_50)"
    assert_eq "(p) $label: exactly one new commit" "1" "$(git -C "$REPO" rev-list --count "$head_before..HEAD")"
    assert_eq "(p) $label: the commit holds exactly both paths" \
        "$(printf '%s\n%s' "$pending" "$released" | sort)" \
        "$(git -C "$REPO" show --no-renames --format= --name-only HEAD | sort)"
    assert_eq "(p) $label: ledger clean" "" "$(is_clean)"
    rnf_run "$REPO" --tag v1.2.0 --no-push
    assert_contains "(p) $label: a later run is all zero" \
        "SUMMARY:posted=0 already=0 resumed=0 pending=0 shipped_earlier=0 failed=0 malformed=0" "$RNF_OUT"
}
interrupted after_publish
interrupted after_remove

# The same two states, built by hand.
# hand_residue <pending> <released> — the released copy of <pending>, untracked.
hand_residue() {
    mkdir -p "$(dirname "$REPO/$2")"
    { cat "$REPO/$1"; printf 'released_tag=v1.2.0\nnotified_at=2026-11-10T10:00:00Z\noutcome=posted\ncommits=%s\n' \
        "$(git -C "$REPO" log --format=%H --grep='(t50)')"; } > "$REPO/$2"
    mkdir -p "$RNF_STATE/comments/o_r_50"
    printf '<!-- aitask-release:v1.2.0 t50 -->\nposted earlier' > "$RNF_STATE/comments/o_r_50/1"
}
for state in both_present pending_deleted; do
    new_repo
    pending="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
    released="$RIL_ROOT/released/v1.2.0/$(basename "$pending")"
    gen_release v1.2.0
    hand_residue "$pending" "$released"
    [[ "$state" == pending_deleted ]] && rm -f "$REPO/$pending"
    resumed_ok "hand:$state" "$pending" "$released"
done

# ---------------------------------------------------------------------------
# (q) residue that does not verify is refused and left untouched
refused() {
    local label="$1" path="$2" reason="$3" sum_before
    sum_before="$(cd "$REPO" && find "$RIL_ROOT" -type f -exec cksum {} + | sort)"
    rnf_run "$REPO" --tag v1.2.0 --no-push
    assert_eq "(q) $label: exit 4" "4" "$RNF_RC"
    assert_contains "(q) $label: refused" "|$path|$reason" "$RNF_OUT"
    assert_eq "(q) $label: no file changed" "$sum_before" \
        "$(cd "$REPO" && find "$RIL_ROOT" -type f -exec cksum {} + | sort)"
    assert_eq "(q) $label: no new comment" "1" "$(rnf_comment_count o_r_50)"
}
new_repo
pending="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
released="$RIL_ROOT/released/v1.2.0/$(basename "$pending")"
gen_release v1.2.0
hand_residue "$pending" "$released"
sed -i.bak 's/^recorded_at=.*/recorded_at=2001-01-01T00:00:00Z/' "$REPO/$released" && rm -f "$REPO/$released.bak"
refused "fields differ from HEAD" "$released" residue_mismatch
new_repo
pending="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
released="$RIL_ROOT/released/v9.9.9/$(basename "$pending")"
gen_release v1.2.0
hand_residue "$pending" "$released"
refused "tag directory mismatch" "$released" residue_mismatch
assert_contains "(q) the record behind it is left alone" "PENDING:50|https://github.com/o/r/issues/50|residue_unresolved" "$RNF_OUT"
new_repo
pending="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
mkdir -p "$RNF_STATE/comments/o_r_50"; printf 'x' > "$RNF_STATE/comments/o_r_50/1"
rm -f "$REPO/$pending"
refused "unpaired pending deletion" "$pending" unpaired_pending_deletion
assert_file_not_exists "(q) unpaired: not restored" "$REPO/$pending"

# ---------------------------------------------------------------------------
# (r) a pending record carrying released-only keys is MALFORMED
new_repo
pending="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
printf 'outcome=posted\noutcome=bogus\n' >> "$REPO/$pending"
git -C "$REPO" commit -qm "ait: corrupt" -- "$pending"
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(r) exit 4" "4" "$RNF_RC"
assert_contains "(r) malformed" "MALFORMED:$pending" "$RNF_OUT"
assert_eq "(r) no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (s) a marker early in a long discussion is still found (no producer pipe
# that dies of SIGPIPE on an early match)
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
mkdir -p "$RNF_STATE/comments/o_r_50"
printf '<!-- aitask-release:v1.2.0 t50 -->\nposted earlier' > "$RNF_STATE/comments/o_r_50/1"
filler="$(head -c 2048 /dev/zero | tr '\0' 'x')"
for i in $(seq 2 300); do printf '%s %s' "$i" "$filler" > "$RNF_STATE/comments/o_r_50/$i"; done
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(s) long thread: exit 0" "0" "$RNF_RC"
assert_contains "(s) long thread: marker found" "ALREADY_NOTIFIED:50|" "$RNF_OUT"
assert_eq "(s) long thread: no duplicate post" "0" "$(posts)"
assert_eq "(s) long thread: comment count unchanged" "300" "$(rnf_comment_count o_r_50)"

# ---------------------------------------------------------------------------
# (t) freshness is bound to this fetch, even when remote.origin.fetch does not
# map the branch (the tracking ref would otherwise stay stale)
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
gen_release v1.2.0
git -C "$REPO" push -q origin main 2>/dev/null
git clone -q -b main "$TMP/r$N/origin.git" "$TMP/r$N/other" 2>/dev/null
git -C "$TMP/r$N/other" config user.email o@example.com
git -C "$TMP/r$N/other" config user.name Other
rnf_commit "$TMP/r$N/other" "ait: remote side"
git -C "$TMP/r$N/other" push -q origin main 2>/dev/null
assert_eq "(t) setup: the remote moved ahead" "1" \
    "$(git -C "$TMP/r$N/origin.git" rev-list --count "$(git -C "$REPO" rev-parse main)..main")"
git -C "$REPO" config --replace-all remote.origin.fetch '+refs/heads/nothing:refs/remotes/origin/nothing'
rnf_run "$REPO" --tag v1.2.0 --no-push
assert_eq "(t) restricted refspec: exit 3" "3" "$RNF_RC"
assert_contains "(t) restricted refspec: behind, not fresh" "INCOMPLETE:freshness:behind:1" "$RNF_OUT"
assert_eq "(t) restricted refspec: no post" "0" "$(posts)"

# ---------------------------------------------------------------------------
# (u) an early move failure never releases the caller's run lock
new_repo
lock_probe() {
    ait_ledger_lock_acquire release_notify run a b
    local dir="$_AIT_LEDGER_LOCK_DIR" owner
    owner="$(cat "$dir/owner")"
    ril_move_released "aitasks/metadata/release_issues/pending/nope.rec" 'bad tag' posted x > /dev/null || true
    ril_move_released "aitasks/metadata/release_issues/pending/nope.rec" v1.2.0 posted not-a-sha > /dev/null || true
    ril_resume_move "/etc/passwd" > /dev/null || true
    if [[ -d "$dir" && "$(cat "$dir/owner" 2>/dev/null)" == "$owner" && "$_AIT_LEDGER_LOCK_TOKEN" == "$owner" ]]; then
        echo LOCK_INTACT
    else
        echo LOCK_LOST
    fi
    ait_ledger_lock_release
}
assert_eq "(u) the caller's lock survives early move failures" "LOCK_INTACT" "$(rnf_lib "$REPO" lock_probe 2>/dev/null)"

# ---------------------------------------------------------------------------
# (v) thousands of tags: tag selection reads the whole list (no SIGPIPE abort)
new_repo
P10="$(rnf_record "$REPO" 10 https://github.com/o/r/issues/10)"
gen_release v1.2.0
head_sha="$(git -C "$REPO" rev-parse HEAD)"
for i in $(seq 1 8003); do printf 'create refs/tags/v0.0.%s %s\n' "$i" "$head_sha"; done \
    | git -C "$REPO" update-ref --stdin
rnf_run "$REPO" --dry-run
assert_eq "(v) default tag selection: exit 0" "0" "$RNF_RC"
assert_contains "(v) default tag selection: newest tag and predecessor" "RANGE:v1.1.0..v1.2.0" "$RNF_OUT"
assert_contains "(v) the SHIPPED_EARLIER lookup survives many containing tags" "SHIPPED_EARLIER:10|" "$RNF_OUT"
rnf_run "$REPO" --dry-run --tag v1.0.0
assert_eq "(v) explicit tag, inferred predecessor: exit 0" "0" "$RNF_RC"
assert_contains "(v) explicit tag, inferred predecessor" "RANGE:v0.0.8003..v1.0.0" "$RNF_OUT"

# ---------------------------------------------------------------------------
# (w) --list needs no release tag
new_repo
P50="$(rnf_record "$REPO" 50 https://github.com/o/r/issues/50)"
git -C "$REPO" tag -l | xargs git -C "$REPO" tag -d >/dev/null
rnf_run "$REPO" --list
assert_eq "(w) no tags: --list exit 0" "0" "$RNF_RC"
assert_contains "(w) no tags: the pending record is listed" "t50 https://github.com/o/r/issues/50" "$RNF_OUT"
rnf_run "$REPO" --dry-run
assert_eq "(w) no tags: a posting range is still refused" "2" "$RNF_RC"

# ---------------------------------------------------------------------------
# (x) a failed git tag enumeration is never read as an empty or short list
new_repo
P10="$(rnf_record "$REPO" 10 https://github.com/o/r/issues/10)"
gen_release v1.2.0
REAL_GIT="$(command -v git)"
mkdir -p "$TMP/tagshim"
{
    printf '#!/usr/bin/env bash\n'
    printf 'real=%q\n' "$REAL_GIT"
    cat <<'SHIM'
is_tag=0 has_list=0 has_contains=0
for a in "$@"; do
    case "$a" in tag) is_tag=1 ;; --list) has_list=1 ;; --contains) has_contains=1 ;; esac
done
if [[ "$is_tag" == 1 && "$has_list" == 1 ]]; then
    case "${RNF_GIT_FAIL:-}" in
        list_empty)   [[ "$has_contains" == 0 ]] && exit 128 ;;
        list_partial) [[ "$has_contains" == 0 ]] && { echo v1.2.0; exit 128; } ;;
        contains)     [[ "$has_contains" == 1 ]] && { echo v1.0.0; exit 128; } ;;
    esac
fi
exec "$real" "$@"
SHIM
} > "$TMP/tagshim/git"
chmod +x "$TMP/tagshim/git"
tag_fail_run() {
    RNF_RC=0
    ( cd "$REPO" && RNF_GIT_FAIL="$1" PATH="$TMP/tagshim:$RNF_BIN:$PATH" "$RNF_NOTIFY" "${@:2}" ) \
        > "$TMP/rnf.out" 2> "$TMP/rnf.err" || RNF_RC=$?
    RNF_OUT="$(cat "$TMP/rnf.out")"
}
for mode in list_empty list_partial; do
    tag_fail_run "$mode" --tag v1.2.0 --no-push
    assert_eq "(x) $mode, explicit tag: exit 3" "3" "$RNF_RC"
    assert_contains "(x) $mode, explicit tag: reported" "INCOMPLETE:tags:git_failed" "$RNF_OUT"
    assert_not_contains "(x) $mode: no range from a failed list" "RANGE:" "$RNF_OUT"
    tag_fail_run "$mode" --no-push
    assert_eq "(x) $mode, default tag: exit 3" "3" "$RNF_RC"
    assert_eq "(x) $mode: no post" "0" "$(posts)"
    assert_file_exists "(x) $mode: t10 stays pending" "$REPO/$P10"
done
tag_fail_run contains --tag v1.2.0 --no-push
assert_eq "(x) containing-tag lookup failed: exit 4" "4" "$RNF_RC"
assert_contains "(x) containing-tag lookup failed: reported" "FAILED:10|https://github.com/o/r/issues/10|tag_lookup_failed" "$RNF_OUT"
assert_not_contains "(x) containing-tag lookup failed: no guessed release" "SHIPPED_EARLIER:10|" "$RNF_OUT"
assert_eq "(x) containing-tag lookup failed: no post" "0" "$(posts)"
assert_file_exists "(x) containing-tag lookup failed: stays pending" "$REPO/$P10"

# --- summary -----------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
