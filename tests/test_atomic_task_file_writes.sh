#!/usr/bin/env bash
# test_atomic_task_file_writes.sh - The shell task/plan-file writers converted
# in t1379 replace their target atomically instead of truncating it.
#
# Covers, over a scaffolded fake repo:
#   - aitask_update.sh   write_task_file          (rewrites an existing task)
#   - aitask_create.sh   create_task_file         (creates a new task)
#   - aitask_issue_import.sh inject_merge_frontmatter
#   - aitask_plan_verified.sh cmd_append          (rewrites a plan)
#   - aitask_gate_pass.sh  witness write          (re-signs a witness)
#   - aitask_plan_externalize.sh  copy path + splice_output_branch
#   - aitask_projects.sh   registry rewrite        (re-pointed onto the helper)
#
# WHAT EACH ASSERTION PROVES — they are not interchangeable:
#
#   hardlink probe         truncate-in-place writes ONLY. `ln` names the target's
#                          inode first; an atomic replacement renames a fresh
#                          inode over the path so the probe keeps the OLD bytes.
#                          It says nothing about cross-device renames: a real
#                          cross-device `mv` produces the identical result
#                          (measured) while still exposing a reader window.
#   TMPDIR stays empty     the writer no longer stages in $TMPDIR — the actual
#                          fix for the `mv` sites, whose temp could land on
#                          another filesystem and degrade into a copy.
#   TMPDIR=/nonexistent    the write path has no $TMPDIR dependency at all.
#                          Pre-fix `mktemp "${TMPDIR}/..."` fails and the script
#                          errors out.
#   created-file mode      a NEW task file is 0644, not mktemp's 0600 — the
#                          creation sites have no prior inode to hardlink.
#   no residue             cleanup, on success and on failure.
#   render failure         the renderer does not lean on `set -e`, which
#                          ait_atomic_render's calling context disables. Driven
#                          through a renderer's OWN guarded condition failing
#                          while its last command succeeds — the shape a
#                          "returns non-zero" test would miss.
#
# Negative controls — one mutation per site: restore that site's original
# write (`} > "$file"`, or `mktemp "${TMPDIR:-/tmp}/…"` + `mv`) and only that
# site's assertions must fail.
#
# Run: bash tests/test_atomic_task_file_writes.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
    return 0
}
trap cleanup EXIT

file_mode() { stat -c '%a' "$1" 2>/dev/null || stat -f '%Lp' "$1" 2>/dev/null || echo "?"; }

# Join single-token fields with `|` into $REPO/.result. Every value MUST be a
# single line: `read` stops at the first newline, so file CONTENT is never
# passed this way — it is compared inside the subshell with `cmp` instead.
emit() { local IFS='|'; printf '%s\n' "$*" > "$REPO/.result"; }
ino_cmp() { [ "$1" != "$2" ] && echo differ || echo same; }
inode()     { stat -c '%i' "$1" 2>/dev/null || stat -f '%i' "$1"; }

# Dot-prefixed staging siblings of <name> left behind in <dir>.
residue_count() {
    local n
    n=$(find "$1" -maxdepth 1 -name ".$2.*" 2>/dev/null | wc -l)
    printf '%s' "$n" | tr -d '[:space:]'
}

# A fake repo with the task-writing scripts and their libs.
make_repo() {
    local tmpdir
    tmpdir="$(mktemp -d "${TMPDIR:-/tmp}/ait_atomic_sites_XXXXXX")"
    tmpdir="$(cd "$tmpdir" && pwd -P)"
    CLEANUP_DIRS+=("$tmpdir")
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"     .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh"  .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh"   .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh"      .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh"      .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh"    .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_plan_verified.sh" .aitask-scripts/
        chmod +x .aitask-scripts/*.sh
        mkdir -p aitasks/metadata aiplans
        printf 'bug\nfeature\nchore\n' > aitasks/metadata/task_types.txt
        : > aitasks/metadata/labels.txt
        cat > aitasks/t1_example.md <<'TASK'
---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [test]
created_at: 2026-01-01 00:00
updated_at: 2026-01-01 00:00
---

Body paragraph one.

Body paragraph two.
TASK
        git add -A >/dev/null
        git commit -qm "setup"
    )
    printf '%s' "$tmpdir"
}

# A TMPDIR we own, so "did the writer stage here?" is answerable.
fresh_tmpdir() {
    local d
    d="$(mktemp -d "${TMPDIR:-/tmp}/ait_atomic_probe_XXXXXX")"
    CLEANUP_DIRS+=("$d")
    printf '%s' "$d"
}
tmpdir_entries() {
    # Staging-residue count. The per-repo lock base lib/stale_lock.sh creates
    # under TMPDIR (aitask-locks-<uid>-<cksum>, t1496) is a deliberate
    # persistent namespace, not atomic-write residue — exempt it, but only
    # while EMPTY: a lock left inside it would be a real leak and must count.
    local n
    n=$(find "$1" -mindepth 1 -not -name 'aitask-locks-*' 2>/dev/null | wc -l)
    printf '%s' "$n" | tr -d '[:space:]'
}

echo "=== atomic task/plan file writes (t1379) ==="

# --------------------------------------------------------------------------
echo "--- aitask_update.sh: write_task_file ---"
REPO="$(make_repo)"
(
    cd "$REPO"
    task="aitasks/t1_example.md"
    chmod 644 "$task"
    ln "$task" aitasks/probe.link
    before_ino="$(inode "$task")"
    cp aitasks/probe.link "$REPO/.original"
    probe_tmp="$(fresh_tmpdir)"

    TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_update.sh --batch 1 \
        --status Implementing --silent >/dev/null

    # Only single-token fields cross this boundary — file CONTENT is compared
    # here, because a `|`-joined line cannot carry an embedded newline.
    emit "$(ino_cmp "$before_ino" "$(inode "$task")")" \
         "$(cmp -s "$REPO/.original" aitasks/probe.link && echo same || echo changed)" \
         "$(file_mode "$task")" \
         "$(residue_count aitasks t1_example.md)" \
         "$(tmpdir_entries "$probe_tmp")" \
         "$(grep -c '^status: Implementing' "$task")" \
         "$(grep -c 'Body paragraph two' "$task")"
)
IFS='|' read -r u_ino u_probe u_mode u_res u_tmpn u_status u_body < "$REPO/.result"
assert_eq "update: the task path gets a fresh inode" "differ" "$u_ino"
assert_eq "update: the pre-write inode is untouched" "same" "$u_probe"
assert_eq "update: mode preserved" "644" "$u_mode"
assert_eq "update: no staging residue" "0" "$u_res"
assert_eq "update: no temp left behind in TMPDIR" "0" "$u_tmpn"
assert_eq "update: the new status actually landed" "1" "$u_status"
assert_eq "update: the body survived" "1" "$u_body"

# The pre-fix code had no $TMPDIR dependency here (it truncated in place), so
# this is a regression guard on the conversion rather than a fix discriminator.
(
    cd "$REPO"
    TMPDIR=/nonexistent/ait-atomic-probe bash .aitask-scripts/aitask_update.sh \
        --batch 1 --status Ready --silent >/dev/null 2>&1
    echo "$?" > "$REPO/.rc"
)
assert_eq "update: succeeds with an unusable TMPDIR" "0" "$(cat "$REPO/.rc")"

# --------------------------------------------------------------------------
echo "--- aitask_create.sh: all three creation sites ---"
REPO="$(make_repo)"
(
    cd "$REPO"
    probe_tmp="$(fresh_tmpdir)"
    # Default batch mode -> create_draft_file (aitasks/new/).
    draft="$(TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_create.sh --batch \
        --name drafttask --priority high --effort low --type bug \
        --desc "atomic-write site test" 2>/dev/null | tail -1 | sed 's/^Created: //')"
    # --commit -> create_task_file (a numbered parent task).
    parent="$(TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_create.sh --batch --commit \
        --name parenttask --priority high --effort low --type bug \
        --desc "atomic-write site test" --silent 2>/dev/null | tail -1 | sed 's/^Created: //')"
    parent_num="$(basename "$parent" | sed 's/^t\([0-9]*\)_.*/\1/')"
    # --parent + --commit -> create_child_task_file.
    child="$(TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_create.sh --batch --commit \
        --parent "$parent_num" --name childtask --priority high --effort low --type bug \
        --desc "atomic-write site test" --silent 2>/dev/null | tail -1 | sed 's/^Created: //')"

    # A creation site has no prior inode to hardlink, so its discriminator is
    # the MODE: mktemp stages 0600, and without the umask-derived default every
    # newly created task file would land private instead of 0644.
    emit "$([ -f "$draft" ] && echo yes || echo no)" \
         "$([ -f "$parent" ] && echo yes || echo no)" \
         "$([ -f "$child" ] && echo yes || echo no)" \
         "$(file_mode "$draft")" "$(file_mode "$parent")" "$(file_mode "$child")" \
         "$(residue_count "$(dirname "$draft")" "$(basename "$draft")")" \
         "$(residue_count "$(dirname "$parent")" "$(basename "$parent")")" \
         "$(residue_count "$(dirname "$child")" "$(basename "$child")")" \
         "$(tmpdir_entries "$probe_tmp")"
)
IFS='|' read -r cd_ok cp_ok cc_ok cd_mode cp_mode cc_mode cd_res cp_res cc_res c_tmpn < "$REPO/.result"
expected_mode="$(printf '%o' $(( 0666 & ~0$(umask) )))"
assert_eq "create: draft file created"          "yes" "$cd_ok"
assert_eq "create: numbered parent created"     "yes" "$cp_ok"
assert_eq "create: child task created"          "yes" "$cc_ok"
assert_eq "create: draft is 0644, not mktemp's 0600"  "$expected_mode" "$cd_mode"
assert_eq "create: parent is 0644, not mktemp's 0600" "$expected_mode" "$cp_mode"
assert_eq "create: child is 0644, not mktemp's 0600"  "$expected_mode" "$cc_mode"
assert_eq "create: no draft residue"  "0" "$cd_res"
assert_eq "create: no parent residue" "0" "$cp_res"
assert_eq "create: no child residue"  "0" "$cc_res"
assert_eq "create: no temp left behind in TMPDIR" "0" "$c_tmpn"

# --------------------------------------------------------------------------
echo "--- aitask_plan_verified.sh: cmd_append ---"
REPO="$(make_repo)"
(
    cd "$REPO"
    cat > aiplans/p1_example.md <<'PLAN'
---
Task: t1_example.md
Base branch: main
plan_verified: []
---

# Plan body
PLAN
    ln aiplans/p1_example.md aiplans/probe.link
    before_ino="$(inode aiplans/p1_example.md)"
    cp aiplans/probe.link "$REPO/.original"
    probe_tmp="$(fresh_tmpdir)"

    TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_plan_verified.sh append \
        aiplans/p1_example.md "claudecode/opus5" >/dev/null

    emit "$(ino_cmp "$before_ino" "$(inode aiplans/p1_example.md)")" \
         "$(cmp -s "$REPO/.original" aiplans/probe.link && echo same || echo changed)" \
         "$(residue_count aiplans p1_example.md)" \
         "$(tmpdir_entries "$probe_tmp")" \
         "$(grep -c 'claudecode/opus5' aiplans/p1_example.md)"
)
IFS='|' read -r v_ino v_probe v_res v_tmpn v_entry < "$REPO/.result"
assert_eq "plan_verified: the plan path gets a fresh inode" "differ" "$v_ino"
assert_eq "plan_verified: the pre-write inode is untouched" "same" "$v_probe"
assert_eq "plan_verified: no staging residue" "0" "$v_res"
assert_eq "plan_verified: no temp left behind in TMPDIR" "0" "$v_tmpn"
assert_eq "plan_verified: the entry actually landed" "1" "$v_entry"

# The $TMPDIR discriminator: pre-fix this staged in "${TMPDIR:-/tmp}", so an
# unusable TMPDIR made mktemp — and the whole append — fail.
(
    cd "$REPO"
    TMPDIR=/nonexistent/ait-atomic-probe bash .aitask-scripts/aitask_plan_verified.sh \
        append aiplans/p1_example.md "claudecode/opus5" >/dev/null 2>&1
    echo "$?" > "$REPO/.rc"
)
assert_eq "plan_verified: succeeds with an unusable TMPDIR" "0" "$(cat "$REPO/.rc")"

# Failure-after-success: a plan with no YAML header gives the renderer no
# insertion point, so `inserted` stays 0 while its trailing `printf` succeeds.
# Without the explicit `[[ $inserted -eq 1 ]] || return 1` guard, errexit is
# disabled inside the renderer and a header-less copy would be committed.
(
    cd "$REPO"
    printf 'no frontmatter here\njust body\n' > aiplans/p2_headerless.md
    cp aiplans/p2_headerless.md "$REPO/.original"
    set +e
    TMPDIR="$(fresh_tmpdir)" bash .aitask-scripts/aitask_plan_verified.sh append \
        aiplans/p2_headerless.md "claudecode/opus5" >/dev/null 2>&1
    rc=$?
    set -e
    emit "$rc" \
         "$(cmp -s "$REPO/.original" aiplans/p2_headerless.md && echo same || echo changed)" \
         "$(residue_count aiplans p2_headerless.md)"
)
IFS='|' read -r f_rc f_same f_res < "$REPO/.result"
assert_eq "plan_verified: a mid-render failure is reported" "1" "$f_rc"
assert_eq "plan_verified: the target is byte-identical after a failed render" \
    "same" "$f_same"
assert_eq "plan_verified: no residue after a failed render" "0" "$f_res"

# --------------------------------------------------------------------------
echo "--- aitask_issue_import.sh: inject_merge_frontmatter ---"
REPO="$(make_repo)"
(
    cd "$REPO"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_issue_import.sh" .aitask-scripts/
    chmod +x .aitask-scripts/aitask_issue_import.sh
    task="aitasks/t1_example.md"
    ln "$task" aitasks/probe.link
    before_ino="$(inode "$task")"
    cp aitasks/probe.link "$REPO/.original"
    probe_tmp="$(fresh_tmpdir)"

    # Drive the function directly: the CLI path needs a live issue tracker.
    TMPDIR="$probe_tmp" bash -c '
        set -e
        SCRIPT_DIR="$PWD/.aitask-scripts"
        . "$SCRIPT_DIR/lib/terminal_compat.sh"
        . "$SCRIPT_DIR/lib/atomic_write.sh"
        # shellcheck disable=SC1090
        eval "$(sed -n "/^inject_merge_frontmatter()/,/^}/p" "$SCRIPT_DIR/aitask_issue_import.sh")"
        inject_merge_frontmatter aitasks/t1_example.md "[2, 3]" ""
    ' >/dev/null

    emit "$(ino_cmp "$before_ino" "$(inode "$task")")" \
         "$(cmp -s "$REPO/.original" aitasks/probe.link && echo same || echo changed)" \
         "$(residue_count aitasks t1_example.md)" \
         "$(tmpdir_entries "$probe_tmp")" \
         "$(grep -c '^related_issues: \[2, 3\]' "$task")"
    mv "$REPO/.result" "$REPO/.result2"
)
# THE discriminator for this site: pre-fix it staged in "${TMPDIR:-/tmp}", so an
# unusable TMPDIR made mktemp — and the whole injection — fail. The hardlink
# probe above cannot tell the old code apart here: its `mv` is same-filesystem
# on the test box, so it also yields "probe old, path new, inodes differ".
(
    cd "$REPO"
    set +e
    TMPDIR=/nonexistent/ait-atomic-probe bash -c '
        set -e
        SCRIPT_DIR="$PWD/.aitask-scripts"
        . "$SCRIPT_DIR/lib/terminal_compat.sh"
        . "$SCRIPT_DIR/lib/atomic_write.sh"
        eval "$(sed -n "/^inject_merge_frontmatter()/,/^}/p" "$SCRIPT_DIR/aitask_issue_import.sh")"
        inject_merge_frontmatter aitasks/t1_example.md "[4]" ""
    ' >/dev/null 2>&1
    rc=$?
    set -e
    emit "$rc" "$(grep -c '^related_issues: \[4\]' aitasks/t1_example.md)"
)
IFS='|' read -r i_nrc i_nfield < "$REPO/.result"

IFS='|' read -r i_ino i_probe i_res i_tmpn i_field < "$REPO/.result2"
assert_eq "issue_import: the task path gets a fresh inode" "differ" "$i_ino"
assert_eq "issue_import: the pre-write inode is untouched" "same" "$i_probe"
assert_eq "issue_import: no staging residue" "0" "$i_res"
assert_eq "issue_import: no temp left behind in TMPDIR" "0" "$i_tmpn"
assert_eq "issue_import: the field actually landed" "1" "$i_field"
assert_eq "issue_import: succeeds with an unusable TMPDIR" "0" "$i_nrc"
assert_eq "issue_import: and still injects" "1" "$i_nfield"

# --------------------------------------------------------------------------
echo "--- aitask_gate_pass.sh: witness re-sign ---"
REPO="$(make_repo)"
(
    cd "$REPO"
    mkdir -p .aitask-gates/t1
    witness=".aitask-gates/t1/review_approved.signal"
    printf 'signer=old\nsigned_at=old\n' > "$witness"
    ln "$witness" .aitask-gates/t1/probe.link
    before_ino="$(inode "$witness")"
    cp .aitask-gates/t1/probe.link "$REPO/.original"
    probe_tmp="$(fresh_tmpdir)"

    # Drive the write itself: the full CLI needs the gate registry + orchestrator.
    TMPDIR="$probe_tmp" bash -c '
        set -e
        SCRIPT_DIR="$PWD/.aitask-scripts"
        . "$SCRIPT_DIR/lib/terminal_compat.sh"
        . "$SCRIPT_DIR/lib/atomic_write.sh"
        target=".aitask-gates/t1/review_approved.signal"
        signer=tester; stamp=2026-01-02T00:00:00Z; host=testhost; digest=""
        _ait_gate_witness_body() {
            echo "signer=$signer"
            echo "signed_at=$stamp"
            echo "hostname=$host"
            if [[ -n "$digest" ]]; then echo "code_digest=$digest"; fi
        }
        ait_atomic_render "$target" _ait_gate_witness_body
    ' >/dev/null

    emit "$(ino_cmp "$before_ino" "$(inode "$witness")")" \
         "$(cmp -s "$REPO/.original" .aitask-gates/t1/probe.link && echo same || echo changed)" \
         "$(residue_count .aitask-gates/t1 review_approved.signal)" \
         "$(tmpdir_entries "$probe_tmp")" \
         "$(grep -c '^signer=tester' "$witness")"
)
IFS='|' read -r g_ino g_probe g_res g_tmpn g_signer < "$REPO/.result"
assert_eq "gate_pass: the witness path gets a fresh inode" "differ" "$g_ino"
assert_eq "gate_pass: the pre-write inode is untouched" "same" "$g_probe"
assert_eq "gate_pass: no staging residue" "0" "$g_res"
assert_eq "gate_pass: no temp left behind in TMPDIR" "0" "$g_tmpn"
assert_eq "gate_pass: the witness was re-signed" "1" "$g_signer"

# An EMPTY digest must still produce a witness: the block's last command used to
# be `[[ -n "$digest" ]] && echo …`, which returns 1 in exactly that case — the
# renderer contract would then read it as a failed render and discard the file.
(
    cd "$REPO"
    rm -f .aitask-gates/t1/empty_digest.signal
    set +e
    bash -c '
        set -e
        SCRIPT_DIR="$PWD/.aitask-scripts"
        . "$SCRIPT_DIR/lib/terminal_compat.sh"
        . "$SCRIPT_DIR/lib/atomic_write.sh"
        target=".aitask-gates/t1/empty_digest.signal"
        signer=tester; stamp=s; host=h; digest=""
        _ait_gate_witness_body() {
            echo "signer=$signer"
            echo "signed_at=$stamp"
            echo "hostname=$host"
            if [[ -n "$digest" ]]; then echo "code_digest=$digest"; fi
        }
        ait_atomic_render "$target" _ait_gate_witness_body
    ' >/dev/null 2>&1
    rc=$?
    set -e
    emit "$rc" "$([ -f .aitask-gates/t1/empty_digest.signal ] && echo yes || echo no)"
)
IFS='|' read -r e_rc e_exists < "$REPO/.result"
assert_eq "gate_pass: an empty code_digest still writes the witness" "0" "$e_rc"
assert_eq "gate_pass: the witness file exists" "yes" "$e_exists"

# --------------------------------------------------------------------------
echo "--- aitask_plan_externalize.sh: copy path + splice path ---"
REPO="$(make_repo)"
(
    cd "$REPO"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_plan_externalize.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/git_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_plan_externalize.sh
    mkdir -p internal
    printf '# Plan for t1\n\nbody\n' > internal/plan.md

    # First run CREATES aiplans/p1_example.md — no prior inode to hardlink, so
    # this run establishes the target; the --force rerun below is the probe.
    bash .aitask-scripts/aitask_plan_externalize.sh 1 --internal internal/plan.md \
        --force --no-worktree >/dev/null 2>&1

    plan="aiplans/p1_example.md"
    chmod 644 "$plan"
    ln "$plan" aiplans/probe.link
    before_ino="$(inode "$plan")"
    cp aiplans/probe.link "$REPO/.original"
    probe_tmp="$(fresh_tmpdir)"

    printf '# Plan for t1 (revised)\n\nnew body\n' > internal/plan.md
    TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_plan_externalize.sh 1 \
        --internal internal/plan.md --force --no-worktree >/dev/null 2>&1

    emit "$(ino_cmp "$before_ino" "$(inode "$plan")")" \
         "$(cmp -s "$REPO/.original" aiplans/probe.link && echo same || echo changed)" \
         "$(file_mode "$plan")" \
         "$(residue_count aiplans p1_example.md)" \
         "$(tmpdir_entries "$probe_tmp")" \
         "$(grep -c 'new body' "$plan")"
)
IFS='|' read -r x_ino x_probe x_mode x_res x_tmpn x_body < "$REPO/.result"
assert_eq "externalize: the plan path gets a fresh inode" "differ" "$x_ino"
assert_eq "externalize: the pre-write inode is untouched" "same" "$x_probe"
assert_eq "externalize: mode preserved on overwrite" "644" "$x_mode"
assert_eq "externalize: no staging residue" "0" "$x_res"
assert_eq "externalize: no temp left behind in TMPDIR" "0" "$x_tmpn"
assert_eq "externalize: the revised body actually landed" "1" "$x_body"

# THE discriminator for this site: pre-fix both its temps came from
# "${TMPDIR:-/tmp}", so an unusable TMPDIR made mktemp — and the whole
# externalization — fail. As with issue_import, the hardlink probe alone cannot
# tell the old code apart, because its `mv` is same-filesystem on the test box.
(
    cd "$REPO"
    printf '# Plan for t1 (third)\n\nthird body\n' > internal/plan.md
    set +e
    TMPDIR=/nonexistent/ait-atomic-probe bash .aitask-scripts/aitask_plan_externalize.sh 1 \
        --internal internal/plan.md --force --no-worktree >/dev/null 2>&1
    rc=$?
    set -e
    emit "$rc" "$(grep -c 'third body' aiplans/p1_example.md)"
)
IFS='|' read -r x_nrc x_nbody < "$REPO/.result"
assert_eq "externalize: succeeds with an unusable TMPDIR" "0" "$x_nrc"
assert_eq "externalize: and still writes the plan" "1" "$x_nbody"

# The splice path (splice_output_branch) is a SEPARATE renderer: it fires only
# when the source already carries frontmatter, so build_header is skipped and
# `Output branch:` has to be spliced into the existing block.
REPO="$(make_repo)"
(
    cd "$REPO"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_plan_externalize.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/git_utils.sh" .aitask-scripts/lib/
    chmod +x .aitask-scripts/aitask_plan_externalize.sh
    mkdir -p internal
    printf -- '---\nTask: t1_example.md\nBase branch: main\n---\n\nbody\n' > internal/plan.md

    bash .aitask-scripts/aitask_plan_externalize.sh 1 --internal internal/plan.md \
        --force --output-branch main >/dev/null 2>&1

    plan="aiplans/p1_example.md"
    ln "$plan" aiplans/probe.link
    before_ino="$(inode "$plan")"
    cp aiplans/probe.link "$REPO/.original"
    probe_tmp="$(fresh_tmpdir)"

    TMPDIR="$probe_tmp" bash .aitask-scripts/aitask_plan_externalize.sh 1 \
        --internal internal/plan.md --force --output-branch main >/dev/null 2>&1

    emit "$(ino_cmp "$before_ino" "$(inode "$plan")")" \
         "$(cmp -s "$REPO/.original" aiplans/probe.link && echo same || echo changed)" \
         "$(residue_count aiplans p1_example.md)" \
         "$(tmpdir_entries "$probe_tmp")" \
         "$(grep -c '^Output branch: main' "$plan")"
)
IFS='|' read -r s_ino s_probe s_res s_tmpn s_field < "$REPO/.result"
assert_eq "externalize/splice: the plan path gets a fresh inode" "differ" "$s_ino"
assert_eq "externalize/splice: the pre-write inode is untouched" "same" "$s_probe"
assert_eq "externalize/splice: no staging residue" "0" "$s_res"
assert_eq "externalize/splice: no temp left behind in TMPDIR" "0" "$s_tmpn"
assert_eq "externalize/splice: Output branch was spliced" "1" "$s_field"

# splice_output_branch is a SECOND renderer with its own former $TMPDIR temp, so
# it needs its own discriminator: the copy path's probe above runs a source
# WITHOUT frontmatter, where build_header fires and the splice never does.
(
    cd "$REPO"
    set +e
    TMPDIR=/nonexistent/ait-atomic-probe bash .aitask-scripts/aitask_plan_externalize.sh 1 \
        --internal internal/plan.md --force --output-branch main >/dev/null 2>&1
    rc=$?
    set -e
    emit "$rc" "$(grep -c '^Output branch: main' aiplans/p1_example.md)"
)
IFS='|' read -r s_nrc s_nfield < "$REPO/.result"
assert_eq "externalize/splice: succeeds with an unusable TMPDIR" "0" "$s_nrc"
assert_eq "externalize/splice: and still splices" "1" "$s_nfield"

# --------------------------------------------------------------------------
echo "--- aitask_projects.sh: registry rewrite ---"
# This site is different in kind from the others: its local `atomic_write`
# ALREADY staged in the destination directory, so the rename was already atomic
# and a hardlink probe cannot discriminate the conversion. What the shared
# helper adds — and what is asserted here — is mode preservation, symlink
# resolution, and a temp name invisible to a glob of the registry directory.
REG_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ait_atomic_reg_XXXXXX")"
CLEANUP_DIRS+=("$REG_DIR")
PROJ_ROOT="$REG_DIR/proj/alpha"
mkdir -p "$PROJ_ROOT/aitasks/metadata"
printf 'project:\n  name: alpha\n' > "$PROJ_ROOT/aitasks/metadata/project_config.yaml"
PROJECTS_SH="$PROJECT_DIR/.aitask-scripts/aitask_projects.sh"

# 1. mode: the old local copy left mktemp's 0600 on the registry.
reg="$REG_DIR/registry.yaml"
AITASKS_PROJECTS_INDEX="$reg" "$PROJECTS_SH" add "$PROJ_ROOT" >/dev/null 2>&1
assert_eq "projects: a new registry is 0644, not mktemp's 0600" \
    "$(printf '%o' $(( 0666 & ~0$(umask) )))" "$(file_mode "$reg")"
chmod 640 "$reg"
AITASKS_PROJECTS_INDEX="$reg" "$PROJECTS_SH" remove alpha >/dev/null 2>&1
assert_eq "projects: an existing registry's mode survives a rewrite" \
    "640" "$(file_mode "$reg")"

# 2. no GLOB-VISIBLE residue: the old temp was "${target}.XXXXXX", which a scan
#    of the registry directory would pick up; the shared helper dot-prefixes.
assert_eq "projects: no visible temp beside the registry" "0" \
    "$(find "$REG_DIR" -maxdepth 1 -name 'registry.yaml.*' 2>/dev/null | wc -l | tr -d '[:space:]')"
assert_eq "projects: no dot-prefixed residue either" "0" \
    "$(residue_count "$REG_DIR" registry.yaml)"

# 3. symlinked registry: the old `mv -f` replaced the LINK, orphaning the
#    backing file; resolution makes the write follow it.
mkdir -p "$REG_DIR/real"
printf 'projects: []\n' > "$REG_DIR/real/backing.yaml"
ln -s real/backing.yaml "$REG_DIR/link.yaml"
AITASKS_PROJECTS_INDEX="$REG_DIR/link.yaml" "$PROJECTS_SH" add "$PROJ_ROOT" >/dev/null 2>&1
assert_eq "projects: a symlinked registry keeps its link" "yes" \
    "$([ -L "$REG_DIR/link.yaml" ] && echo yes || echo no)"
assert_eq "projects: the write reached the backing file" "yes" \
    "$(grep -q 'alpha' "$REG_DIR/real/backing.yaml" && echo yes || echo no)"

echo
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
if [[ $FAIL -eq 0 ]]; then
    echo "PASS"
    exit 0
fi
echo "FAIL"
exit 1
