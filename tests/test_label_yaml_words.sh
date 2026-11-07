#!/usr/bin/env bash
# test_label_yaml_words.sh - labels never reach the frontmatter as a word YAML
# reads as a non-string (t2214).
#
# Labels are written unquoted (format_yaml_list), so sanitize_label rejects any
# token that PyYAML would not read back as the identical string. That covers
# `on` -> True, `null` -> None, `010` -> 8, `2026-11-05` -> date, and `0x1f` -> 31.
#
#   A. Differential: _label_reads_as_string against both PyYAML loaders
#      (yaml.SafeLoader and task_yaml._TaskSafeLoader) over every string of
#      length 1-3 from a probe alphabet, plus known YAML words. It must accept no
#      misread string, and its over-rejections must equal a pinned list.
#   B. Pinned sanitize_label accepts / rejects.
#   C. End to end: batch create and update in a scratch repo drop the words with
#      a warning. The written labels: reads back as strings under both loaders,
#      and labels.txt never gains a rejected word.
#   D. Interactive create picker: the two routes that replay STORED values
#      (previous-task labels from userconfig.yaml, an existing labels.txt
#      entry) are normalized too. A control with normalization overridden by a
#      plain join shows the fixture really reaches each route.
#
# Skips (exit 0, printed reason) when no Python with PyYAML is available: the
# file is about agreement with that parser.
#
# Run: bash tests/test_label_yaml_words.sh

set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
LIB="$PROJECT_DIR/.aitask-scripts/lib"

. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

# shellcheck disable=SC2034  # read by task_utils.sh when sourced
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
# shellcheck source=../.aitask-scripts/lib/task_utils.sh disable=SC1091
source "$LIB/task_utils.sh"

PY="$(resolve_python)"
if [[ -z "$PY" ]] || ! "$PY" -c 'import yaml' 2>/dev/null; then
    echo "SKIP: no Python with PyYAML available (resolved: '${PY:-none}')"
    exit 0
fi

# Sections C and D run their bodies in `( … )` subshells, so the counters are
# file-backed (CLAUDE.md, t1207): in-process increments die at subshell exit.
# Allocated only after the skip probe above, with cleanup armed at once, so the
# SKIP exit never leaves a counter file behind. Each section's own exit status
# is asserted too (assert_exit_zero_rc), so a body that dies early fails the
# file instead of vanishing.
assert_counters_init
TMP="$(mktemp -d "${TMPDIR:-/tmp}/t2214_labels.XXXXXX")"
trap 'rm -rf "$TMP"; rm -f "$AIT_ASSERT_COUNTER_FILE"' EXIT

cat > "$TMP/oracle.py" <<'PY'
import itertools, sys, yaml
sys.path.append(sys.argv[1])
import task_yaml
mode = sys.argv[2]
LOADERS = (yaml.SafeLoader, task_yaml._TaskSafeLoader)

if mode == "corpus":
    # Every string of length 1-3 over the probe alphabet, plus known YAML words.
    # One per line, sorted.
    alpha = "019ab_-xeonyftlu7"
    words = ["y", "n", "yes", "no", "true", "false", "on", "off", "null",
             "2026-11-05", "2026-1-5", "1_000", "0x1f", "0b101", "010", "-5",
             "-", "--", "-x", "x-", "_x", "0o7", "1e5", "inf", "nan", "0", "00",
             "09", "08", "3d", "2fa", "0day", "y2k"]
    c = set(words)
    for n in (1, 2, 3):
        c.update("".join(t) for t in itertools.product(alpha, repeat=n))
    print("\n".join(sorted(c)))
elif mode == "misread":
    # stdin: candidates, one per line. Print each that EITHER loader does not read
    # back as the identical one-string list.
    for s in sys.stdin.read().split("\n"):
        if not s:
            continue
        for L in LOADERS:
            try:
                ok = yaml.load("[%s]" % s, Loader=L) == [s]
            except Exception:
                ok = False
            if not ok:
                print(s)
                break
elif mode == "labels":
    # argv[3] = task file. Print the labels value per loader, or BAD:<repr>.
    text = open(sys.argv[3], encoding="utf-8").read()
    fm = text.split("---\n")[1]
    for L in LOADERS:
        v = yaml.load(fm, Loader=L).get("labels")
        if isinstance(v, list) and all(isinstance(x, str) for x in v):
            print(",".join(v))
        else:
            print("BAD:%r" % (v,))
PY
oracle() { "$PY" -I "$TMP/oracle.py" "$LIB" "$@"; }

# ── A. Differential against PyYAML ──────────────────────────────────────────
echo "=== A. _label_reads_as_string vs PyYAML ==="
oracle corpus > "$TMP/corpus"
oracle misread < "$TMP/corpus" | LC_ALL=C sort > "$TMP/misread"
while IFS= read -r s; do
    _label_reads_as_string "$s" || printf '%s\n' "$s"
done < "$TMP/corpus" | LC_ALL=C sort > "$TMP/rejected"
ncorpus=$(wc -l < "$TMP/corpus" | tr -d ' ')
nmis=$(wc -l < "$TMP/misread" | tr -d ' ')
assert_eq "corpus is non-trivial (> 5000 strings)" "1" "$(( ncorpus > 5000 ? 1 : 0 ))"
assert_eq "PyYAML misreads a non-trivial share of it (> 100)" "1" "$(( nmis > 100 ? 1 : 0 ))"
assert_eq "no misread string is accepted (false accepts)" "" \
    "$(LC_ALL=C comm -23 "$TMP/misread" "$TMP/rejected" | tr '\n' ' ')"
# Deliberate, conservative over-rejections: strings PyYAML reads as strings
# that the rule rejects anyway. Pinned exactly so the rule cannot drift.
assert_eq "over-rejections equal the pinned list" \
    "-09 -0b -0x 009 019 079 08 09 090 091 097 099 09_ 0_9 0b 0b7 0b9 0ba 0bb 0be 0bf 0x 2026-1-5 n y " \
    "$(LC_ALL=C comm -13 "$TMP/misread" "$TMP/rejected" | tr '\n' ' ')"

# ── B. Pinned sanitize_label behaviour ──────────────────────────────────────
echo "=== B. sanitize_label pinned cases ==="
for w in 3d 2fa 0day x-1 -x ui y2k; do
    assert_eq "sanitize_label keeps '$w'" "$w" "$(sanitize_label "$w")"
done
for w in on ON Null yes 010 0x1f 2026-11-05 -5 1_000; do
    assert_eq "sanitize_label rejects '$w'" "" "$(sanitize_label "$w")"
done
assert_eq "sanitize_label still canonicalizes" "ui_stuff" "$(sanitize_label 'UI Stuff')"

# ── Scratch repo shared by C and D ──────────────────────────────────────────
setup_project() {
    local d="$TMP/$1"
    git init --bare --quiet "$d/remote.git"
    git clone --quiet "$d/remote.git" "$d/local" 2>/dev/null
    cd "$d/local" || exit 1
    git config user.email "test@test.com"
    git config user.name "Test"
    mkdir -p aitasks/metadata aitasks/new aitasks/archived
    setup_fake_aitask_repo "$PWD"
    local f
    for f in aitask_create.sh aitask_update.sh aitask_claim_id.sh aitask_query_files.sh; do
        cp "$PROJECT_DIR/.aitask-scripts/$f" .aitask-scripts/
    done
    for f in task_utils.sh archive_utils.sh archive_scan.sh agentcrew_utils.sh userconfig_persist.py; do
        cp "$PROJECT_DIR/.aitask-scripts/lib/$f" .aitask-scripts/lib/ 2>/dev/null || true
    done
    chmod +x .aitask-scripts/*.sh
    printf 'bug\nchore\nfeature\n' > aitasks/metadata/task_types.txt
    printf '%s\n' "$2" > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore
    git add -A
    git commit -m "Initial setup" --quiet
    git push --quiet 2>/dev/null || true
    ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1 || true
}

# ── C. End to end: batch create + update ────────────────────────────────────
echo "=== C. batch create / update round trip ==="
(
    setup_project batch "zzz_sentinel"
    err="$TMP/batch.err"
    f=$(bash .aitask-scripts/aitask_create.sh --batch --commit --silent \
            --name labels_case --desc x --labels "on,ui,010" 2>"$err")
    assert_file_exists "batch create made the task" "$f"
    assert_contains "batch create warns about the dropped words" "dropped invalid label" "$(cat "$err")"
    assert_eq "batch create: labels read as strings (both loaders)" "ui|ui" \
        "$(oracle labels "$f" | tr '\n' '|' | sed 's/|$//')"
    id=$(basename "$f" .md); id=${id%%_*}; id=${id#t}
    bash .aitask-scripts/aitask_update.sh --batch "$id" --add-label null --silent 2>"$err" >/dev/null
    assert_contains "batch update warns about the dropped word" "dropped invalid label" "$(cat "$err")"
    assert_eq "batch update: labels still read as strings (both loaders)" "ui|ui" \
        "$(oracle labels "$f" | tr '\n' '|' | sed 's/|$//')"
    assert_eq "labels.txt gained none of the rejected words" "" \
        "$(grep -xE 'on|null|010' aitasks/metadata/labels.txt | tr '\n' ' ')"
); assert_exit_zero_rc "section C (batch create / update) body ran to completion" $?

# ── D. Interactive create picker: stored-value routes ───────────────────────
echo "=== D. interactive create picker ==="

# run_picker <mode> <queue...> -- run get_labels_interactive with fzf mocked to
# answer from <queue> (each answer is matched against the offered lines: exact
# match first, else the first line starting with it). <mode> = fixed runs the
# real function. <mode> = prefix overrides _set_selected_labels with the plain
# join the picker had before t2214 (the control). Prints SELECTED_LABELS on
# line 1, then the picker's stderr.
run_picker() {
    local mode="$1"; shift
    printf '%s\n' "$@" > "$TMP/fzf_queue"
    grep -v '^main "\$@"$' .aitask-scripts/aitask_create.sh > .aitask-scripts/create_fns.sh
    (
        # shellcheck disable=SC1091
        source .aitask-scripts/create_fns.sh
        set +e
        # shellcheck disable=SC2329  # called by get_labels_interactive
        fzf() {
            local want opts line pick=""
            opts="$(cat)"
            want="$(head -n1 "$TMP/fzf_queue")"
            tail -n +2 "$TMP/fzf_queue" > "$TMP/fzf_queue.n" && mv "$TMP/fzf_queue.n" "$TMP/fzf_queue"
            while IFS= read -r line; do
                [[ "$line" == "$want" ]] && { pick="$line"; break; }
            done <<< "$opts"
            if [[ -z "$pick" ]]; then
                while IFS= read -r line; do
                    [[ "$line" == "$want"* ]] && { pick="$line"; break; }
                done <<< "$opts"
            fi
            printf '%s\n' "$pick"
        }
        if [[ "$mode" == prefix ]]; then
            # shellcheck disable=SC2329  # called by get_labels_interactive
            _set_selected_labels() { SELECTED_LABELS="$(IFS=','; printf '%s' "$*")"; }
        fi
        get_labels_interactive 2>"$TMP/picker.err" </dev/null >/dev/null
        printf '%s\n' "$SELECTED_LABELS"
        cat "$TMP/picker.err"
    )
}

(
    # labels.txt is a LEGACY vocabulary holding `on`. userconfig.yaml holds it
    # too, quoted the way userconfig_persist.py's safe_dump writes it.
    setup_project picker "$(printf 'on\nui')"
    printf "email: t@t\nlast_used_labels: ['on', ui]\n" > aitasks/metadata/userconfig.yaml

    prev_q=(">> Use labels from previous task" ">> Done adding labels")
    vocab_q=("on" "Add another label" "ui" "Done with labels")

    out="$(run_picker prefix "${prev_q[@]}")"
    assert_eq "control: previous-labels route reaches the picker unnormalized" "on,ui" "$(head -n1 <<< "$out")"
    out="$(run_picker prefix "${vocab_q[@]}")"
    assert_eq "control: vocabulary route reaches the picker unnormalized" "on,ui" "$(head -n1 <<< "$out")"

    out="$(run_picker fixed "${prev_q[@]}")"
    assert_eq "previous-labels route: the YAML word is dropped" "ui" "$(head -n1 <<< "$out")"
    assert_contains "previous-labels route: the drop is reported" "dropped invalid label(s): on" "$out"
    out="$(run_picker fixed "${vocab_q[@]}")"
    assert_eq "vocabulary route: the YAML word is dropped" "ui" "$(head -n1 <<< "$out")"
    assert_contains "vocabulary route: the drop is reported" "dropped invalid label(s): on" "$out"
    out="$(run_picker fixed ">> Done adding labels")"
    assert_eq "an empty selection stays empty" "" "$(head -n1 <<< "$out")"
); assert_exit_zero_rc "section D (interactive create picker) body ran to completion" $?

assert_counters_load
echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
