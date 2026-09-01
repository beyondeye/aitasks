#!/usr/bin/env bash
# aitask_note.sh - Append an attributed note to a task's "## Inbox" (t1657_2).
#
# The durable lane of the task-note mailbox: a task can be told something even
# when nobody is working on it. Shaped on aitask_gate_record.sh (append via the
# shared ledger seam, then a path-scoped commit and a best-effort push), with one
# deliberate difference: gate-record is best-effort and always exits 0, while
# `ait note` is AUTHORITATIVE and reports failure.
#
# Built ON lib/ledger_block.sh (t1657_1) — the per-task append mutex, marker
# assembly and section ensure-and-append are the seam's, not ours. What stays
# here is what is genuinely note-specific: the '> | ' body sentinel, note
# identity, provenance capture and the sender proof.
#
# Usage:
#   aitask_note.sh <target-task-id> --from <id> [--text ... | --file ...]
#   aitask_note.sh <target-task-id> --migrate --claimed-from <ref> \
#                  --claimed-at <date> --base <oid> [--base-branch <b>] \
#                  (--text ... | --file ...)
#
# OUTPUT CONTRACT — exactly ONE line on stdout, always:
#   NOTE_APPENDED:<note-id>|<path>                       appended + committed
#   NOTE_APPENDED_UNCOMMITTED:<note-id>|<path>|<reason>  appended, commit failed
#   NOTE_TARGET_MISSING:<id>
#   NOTE_SELF:<id>
#   NOTE_ERROR:<reason>                                  failed BEFORE the append
#
# The first two are id-bearing and terminal (the note exists — do not retry);
# the last three mean no note and no id exist. The two sets are disjoint, so
# "was a note created?" is answerable from stdout alone. Every advisory — the
# recovery hint, git noise — goes to stderr via warn(), mirroring
# aitask_gate.sh's MATERIALIZED / MATERIALIZED_UNCOMMITTED split.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/stale_lock.sh
source "$SCRIPT_DIR/lib/stale_lock.sh"
# shellcheck source=lib/ledger_block.sh
source "$SCRIPT_DIR/lib/ledger_block.sh"
# shellcheck source=lib/pid_anchor.sh
source "$SCRIPT_DIR/lib/pid_anchor.sh"
# shellcheck source=lib/git_utils.sh
source "$SCRIPT_DIR/lib/git_utils.sh"

TASK_DIR="${TASK_DIR:-aitasks}"

# Scratch file for --file / stdin bodies, so NUL can be detected on the raw
# bytes before they reach a shell variable (which cannot hold one).
TMPBODY="$(mktemp "${TMPDIR:-/tmp}/aitask_note.XXXXXX")"
note_cleanup() { rm -f "$TMPBODY"; }
trap note_cleanup EXIT

# --- Section constants ------------------------------------------------------
#
# Mirrors gate_ledger.SECTION_HEADER / SECTION_COMMENT. The Inbox is inserted
# BEFORE '## Gate Runs': both gate-append paths (_gate_append_locked and
# gate_ledger.append_block) append at EOF, so an Inbox placed after would
# silently capture every future gate block.
NOTE_SECTION_HEADER="## Inbox"
NOTE_SECTION_COMMENT="<!-- Appended by the note framework. Do not edit by hand; use \`./ait note\`. -->"
NOTE_NAMESPACE="note"
NOTE_ANCHOR_HEADER="## Gate Runs"
NOTE_ICON="✉"

# Body size bound. Documented in --help; a note is context, not a payload.
NOTE_MAX_BODY_BYTES=8192

# Id-collision retry bound. The in-lock uniqueness check re-mints on collision;
# this bounds it so a degenerate generator terminates instead of spinning.
NOTE_ID_RETRIES=8

# --- Canonical task-id representation (t1657_2 §0) --------------------------
#
# Two forms circulate and they are NOT interchangeable. Measured: `aitask_lock.sh
# --check t1669` prints NOTHING while `--check 1669` works, and resolve_task_file
# errors on a 't' prefix. Feeding a stored 't'-prefixed id to either helper
# therefore yields a silent empty answer that reads as "no lock record" — which
# would make from_verified=yes essentially unwritable.
#
#   CLI input : liberal   — 349, t349, 1657_2, t1657_2
#   lookup    : BARE      — 349, 1657_2        (every helper call)
#   stored    : t-PREFIXED — t349, t1657_2     (marker name and from=)
#
# Normalize once at the boundary; render once at the write site.

# note_id_normalize <input> -> bare id on stdout, or non-zero if malformed.
note_id_normalize() {
    local raw="${1:-}" bare="${1#t}"
    [[ -n "$raw" ]] || return 1
    [[ "$bare" =~ ^[0-9]+(_[0-9]+)?$ ]] || return 1
    printf '%s' "$bare"
}

# note_id_render <bare-id> -> stored 't'-prefixed form.
note_id_render() { printf 't%s' "$1"; }

# A cross-repo reference, per aidocs/framework/cross_repo_references.md.
# Accepted ONLY on the --migrate path: '#' is not in ledger_block's
# _NAME_CHARS, so such a value can never be a marker NAME — only a k=v value.
note_xrepo_local_part() {
    local ref="${1:-}"
    [[ "$ref" =~ ^[a-z0-9_-]+#t?([0-9]+(_[0-9]+)?)$ ]] || return 1
    printf '%s' "${BASH_REMATCH[1]}"
}

# --- Provenance value shapes (t1657_2 F18) ----------------------------------
#
# These MIRROR the merger's INBOX_SPEC.validate rules. They have to: whatever
# the writer commits, the merger later re-validates on every other PC, so a
# value accepted here and rejected there turns a local migration into a
# cross-PC conflict source — the block is already in git by then.
#
# A full object id, never an abbreviation: 40 hex (sha1) or 64 (sha256).
note_is_full_oid() {
    [[ "${1:-}" =~ ^([0-9a-f]{40}|[0-9a-f]{64})$ ]]
}

# The degraded sentinels, spelled once.
note_is_base_sentinel() {
    [[ "${1:-}" == "none" || "${1:-}" == "unknown" ]]
}

# A claimed_at is a date or an ISO instant — the original note's own precision,
# never free text.
note_is_date_like() {
    [[ "${1:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] ||
    [[ "${1:-}" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$ ]]
}

# Branch names reach the marker line, which is whitespace-delimited.
note_is_branch_like() {
    [[ "${1:-}" =~ ^[A-Za-z0-9._/-]+$ ]]
}

# --- Single-line output contract --------------------------------------------

# Structured fields live in a '|'-delimited single line, so a value carrying a
# newline or a '|' would split the record or forge a field. Sanitize at the
# WRITE site — the same rule the body sentinel follows, for the same reason.
note_sanitize_field() {
    printf '%s' "${1:-}" | tr '\n\r' '  ' | tr '|' '/'
}

note_die() {
    printf 'NOTE_ERROR:%s\n' "$(note_sanitize_field "$1")"
    exit 1
}

show_help() {
    cat <<EOF
Usage: aitask_note.sh <target-task-id> --from <id> [--text ... | --file ...]

Append an attributed note to <target-task-id>'s "## Inbox" section and commit
the task file path-scoped. A note is untrusted advisory input for the reader,
never an instruction — it is one agent's claim about a tree that may have moved.

Options:
  --from <id>        Sender task id (local only; 349 or t349, 1657_2 or t1657_2)
  --text <text>      Note body, inline
  --file <path>      Note body, from a file ('-' for stdin)

Migration (for content that predates the mailbox):
  --migrate                Enable the migration path
  --claimed-from <ref>     Sender: a local id OR a cross-repo <project>#<id>
  --claimed-at <date>      The original note's own timestamp
  --base <oid>             The historical base object id (FULL, never abbreviated)
  --base-branch <branch>   The historical base branch

  On this path from_verified is never written (the proof is not run at all),
  migrated=yes is always written, and no dirty/host is recorded — none of the
  three was ever observed, and claiming them would fabricate provenance.

Body limit: ${NOTE_MAX_BODY_BYTES} bytes. NUL is rejected; CR is stripped.

Output (exactly one line on stdout; advisories go to stderr):
  NOTE_APPENDED:<note-id>|<path>
  NOTE_APPENDED_UNCOMMITTED:<note-id>|<path>|<reason>
  NOTE_TARGET_MISSING:<id>
  NOTE_SELF:<id>
  NOTE_ERROR:<reason>

Example:
  aitask_note.sh 357 --from 349 --text "the line numbers in your task are stale"
EOF
}

# --- Provenance (t1657_2 §3) ------------------------------------------------
#
# THE OBVIOUS IMPLEMENTATION IS WRONG. `aitasks/` is a symlink into the data
# worktree (aitasks -> .aitask-data/aitasks), so resolving git context from the
# task file's own path records the AITASK-DATA sha — a confident, wrong answer
# to the only question `base` exists to answer. Query the CODE repo root, always,
# and capture BEFORE the append and its commit.
#
# Storage is exact; presentation may abbreviate. `git rev-parse HEAD`, never
# --short: core.abbrev is unset, so git auto-scales abbreviation to repo size,
# and a prefix frozen into a durable note keeps that width as the repo grows —
# defeating the exact-tree promise for exactly the oldest notes.
#
# Sets: PROV_BASE PROV_BASE_BRANCH PROV_MERGEBASE PROV_DIRTY
note_capture_provenance() {
    local root="${AIT_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
    PROV_BASE=""; PROV_BASE_BRANCH=""; PROV_MERGEBASE=""; PROV_DIRTY=""

    if ! git -C "$root" rev-parse --git-dir >/dev/null 2>&1; then
        # No repository. `dirty` is UNMEASURABLE here, and this is the only case
        # that earns the sentinel: 'no' would fabricate a clean-state claim and
        # 'yes' is equally unsupported. Absence is not an option — a missing
        # field reads as "fine" (or as an old writer) to a parser, which is the
        # same argument that makes base=none a sentinel rather than an empty.
        PROV_BASE="none"
        PROV_DIRTY="unknown"
        return 0
    fi

    if ! PROV_BASE="$(git -C "$root" rev-parse HEAD 2>/dev/null)"; then
        # HEAD unresolvable (unborn branch). The repo and the working tree DO
        # exist, so `git status` still reports and dirty is measured normally —
        # 'unknown' here would be a false disclaimer.
        PROV_BASE="unknown"
    fi

    if [[ -n "$(git -C "$root" status --porcelain 2>/dev/null)" ]]; then
        PROV_DIRTY="yes"
    else
        PROV_DIRTY="no"
    fi

    [[ "$PROV_BASE" == "unknown" ]] && return 0

    PROV_BASE_BRANCH="$(git -C "$root" rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
    [[ -n "$PROV_BASE_BRANCH" ]] || PROV_BASE_BRANCH="unknown"

    # Off-primary HEAD gets a merge base. Discover the primary with the existing
    # helper — never hardcode 'main': this is framework code shipped into other
    # people's repos, and a master-default repo would otherwise get the wrong
    # merge base or none at all.
    local primary
    primary="$(cd "$root" && detect_primary_branch)"
    if [[ -n "$primary" && "$PROV_BASE_BRANCH" != "$primary" ]]; then
        PROV_MERGEBASE="$(git -C "$root" merge-base HEAD "$primary" 2>/dev/null || true)"
    fi
    return 0
}

# --- Sender proof (t1657_2 §5) ----------------------------------------------
#
# `from=` is a CLAIM. The note append lock is keyed note_<target> — it protects
# the TARGET's Inbox and says nothing whatsoever about the claimed sender, so
# --from is unauthenticated unless proven separately.
#
# Do not invent a mechanism: lib/pid_anchor.sh already has the right primitive
# with the right fail-closed semantics. Returns 0 only when this very session
# provably holds the sender task's lock.
note_sender_is_self() {
    local from_bare="$1" out pid token kind host
    out="$("$SCRIPT_DIR/aitask_lock.sh" --check "$from_bare" 2>/dev/null || true)"
    [[ -n "$out" ]] || return 1

    host="$(printf '%s\n' "$out" | sed -n 's/^hostname: //p' | head -n1)"
    pid="$(printf '%s\n' "$out" | sed -n 's/^pid: //p' | head -n1)"
    token="$(printf '%s\n' "$out" | sed -n 's/^pid_starttime: //p' | head -n1)"
    kind="$(printf '%s\n' "$out" | sed -n 's/^pid_starttime_kind: //p' | head -n1)"

    [[ "$host" == "$(hostname)" ]] || return 1
    # All three of pid, start-time token and token KIND must match — a recycled
    # PID carries the same number with a different token. An own-anchor this
    # process cannot resolve can never claim identity, so an unverifiable anchor
    # fails TOWARD the gate rather than around it.
    lock_anchor_is_self "$pid" "${token:--}" "${kind:-proc}" || return 1
    return 0
}

# --- Body rendering (t1657_2 §5) --------------------------------------------
#
# THE INJECTION DEFENCE. Markers match '^>\s*\*\*'. A body line emitted as a
# plain '> <text>' beginning '**👁 note:read** … ids=…' IS a syntactically valid
# receipt — letting a note forge an acknowledgement of itself. The '| ' sentinel
# sits between the quote marker and the text so '^>\s*\*\*' can never match a
# body line; it also neutralizes '## Inbox' / '## Gate Runs' inside a body.
#
# Sanitize at the WRITE site, never at the read site.
note_render_body() {
    local raw="$1"
    printf '%s' "$raw" | tr -d '\r' | while IFS= read -r line || [[ -n "$line" ]]; do
        printf '> | %s\n' "$line"
    done
}

# --- Note identity (t1657_2 §4) ---------------------------------------------
#
# <iso-utc>.<24-hex> — 96 bits from a CSPRNG. Minted INSIDE the append lock and
# verified absent before writing: within a checkout uniqueness is a guarantee,
# and the 96 bits cover what no lock can (two PCs appending concurrently). A
# 4-hex suffix would only reduce the hazard — and since `ids=` is the
# ASSOCIATION key, a collision makes a receipt acknowledge the wrong entry.
#
note_random_suffix() { od -An -tx1 -N12 /dev/urandom | tr -d ' \n'; }

note_iso_now() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# The WHOLE id is the test seam, not just the suffix. A suffix-only override
# cannot force a collision: the id is "<iso>.<suffix>", so two calls a second
# apart differ even with an identical suffix — a collision test built on it
# would pass without ever exercising the re-mint. Overriding the whole id makes
# the collision exact and the retry bound provable.
note_mint_id() {
    if [[ -n "${AIT_NOTE_ID_CMD:-}" ]]; then
        eval "$AIT_NOTE_ID_CMD"
        return
    fi
    printf '%s.%s' "$(note_iso_now)" "$(note_random_suffix)"
}

# --- The locked append ------------------------------------------------------
#
# Mint the id INSIDE the lock and verify it is absent from the section before
# writing. Sets NOTE_ID.
note_append_locked() {
    local file="$1" name="$2" body="$3"; shift 3
    local -a extra_kv=("$@")

    ait_ledger_lock_acquire "$NOTE_NAMESPACE" "$LOCK_KEY" \
        "note lock" "note append lock"
    # The seam's trap releases the lock errexit-safely and exits; chain our
    # scratch-file cleanup in front of it, or binding this would silently drop
    # the EXIT handler set at startup.
    trap 'note_cleanup; ait_ledger_lock_exit_trap' EXIT

    local attempt=0 candidate
    NOTE_ID=""
    while (( attempt < NOTE_ID_RETRIES )); do
        candidate="$(note_mint_id)"
        if ! grep -qF "id=$candidate" "$file" 2>/dev/null; then
            NOTE_ID="$candidate"
            break
        fi
        attempt=$(( attempt + 1 ))
    done
    if [[ -z "$NOTE_ID" ]]; then
        # Bounded, so a degenerate generator terminates rather than spinning.
        # Nothing has been appended, so this is a pre-append failure: the
        # id-less NOTE_ERROR half of the contract is the correct one.
        ait_ledger_lock_release || true
        trap note_cleanup EXIT
        note_die "id-collision-retries-exhausted"
    fi

    local marker
    marker="$(ait_ledger_marker "$NOTE_NAMESPACE" "$name" "$NOTE_ICON" \
        "id=$NOTE_ID" "${extra_kv[@]}")"

    ait_ledger_append_section "$file" "$NOTE_SECTION_HEADER" \
        "$NOTE_SECTION_COMMENT" "$marker" "$body" \
        "$NOTE_ANCHOR_HEADER" "section_end"

    ait_ledger_lock_release_checked
    trap note_cleanup EXIT
}

main() {
    case "${1:-}" in
        --help | -h | help | "") show_help; return 0 ;;
    esac

    local target_raw="$1"; shift
    local from_raw="" body_text="" body_file="" migrate=0
    local claimed_from="" claimed_at="" cli_base="" cli_base_branch=""

    # Every flag is counted, not just captured. A last-one-wins parser turns a
    # contradictory command line into a silently different note: `--text a
    # --file b` would drop the inline text, and `--text a --text b` would keep
    # only b — both without a word to the caller (F19).
    local n_from=0 n_text=0 n_file=0 n_claimed_from=0 n_claimed_at=0
    local n_base=0 n_base_branch=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --from)          from_raw="${2:-}";        n_from=$((n_from+1));       shift 2 ;;
            --text)          body_text="${2:-}";       n_text=$((n_text+1));       shift 2 ;;
            --file)          body_file="${2:-}";       n_file=$((n_file+1));       shift 2 ;;
            --migrate)       migrate=1; shift ;;
            --claimed-from)  claimed_from="${2:-}";    n_claimed_from=$((n_claimed_from+1)); shift 2 ;;
            --claimed-at)    claimed_at="${2:-}";      n_claimed_at=$((n_claimed_at+1));     shift 2 ;;
            --base)          cli_base="${2:-}";        n_base=$((n_base+1));       shift 2 ;;
            --base-branch)   cli_base_branch="${2:-}"; n_base_branch=$((n_base_branch+1));   shift 2 ;;
            *) note_die "unknown-option:$1" ;;
        esac
    done

    # --- Argument matrix -----------------------------------------------------
    # Exactly one body source, no repeats, and the two sender/provenance modes
    # are mutually exclusive. Refusing is the only honest answer: there is no
    # defensible way to pick which of two bodies the caller meant.
    # Duplicates FIRST: `--text a --text b` also fails the exactly-one rule
    # below, and reporting that instead would name the wrong problem.
    # The reason field is '|'-delimited, so the message must not contain one —
    # note_sanitize_field would rewrite it (F17).
    (( n_text <= 1 )) || note_die "duplicate-option:--text"
    (( n_file <= 1 )) || note_die "duplicate-option:--file"
    (( n_from <= 1 )) || note_die "duplicate-option:--from"
    (( n_text + n_file == 1 )) \
        || note_die "need-exactly-one-body-source:--text-or---file"
    (( n_claimed_from <= 1 )) || note_die "duplicate-option:--claimed-from"
    (( n_claimed_at <= 1 ))   || note_die "duplicate-option:--claimed-at"
    (( n_base <= 1 ))         || note_die "duplicate-option:--base"
    (( n_base_branch <= 1 ))  || note_die "duplicate-option:--base-branch"

    if (( migrate )); then
        # --from is IGNORED on this path (the proof is never run), so accepting
        # it would let a caller believe they had attributed a verified sender.
        (( n_from == 0 )) || note_die "from-not-valid-with-migrate"
    else
        local n_mig=$(( n_claimed_from + n_claimed_at + n_base + n_base_branch ))
        # Provenance is CAPTURED in normal mode, so a supplied value would be
        # silently discarded.
        (( n_mig == 0 )) || note_die "migration-options-require-migrate"
    fi

    # --- Target resolution (bare form for every helper call) ---
    local target_bare
    target_bare="$(note_id_normalize "$target_raw")" \
        || note_die "bad-task-id:$target_raw"

    local file
    if ! file="$(resolve_task_file "$target_bare" 2>/dev/null)"; then
        printf 'NOTE_TARGET_MISSING:%s\n' "$(note_sanitize_field "$target_bare")"
        return 1
    fi

    # --- Sender resolution ---
    local sender_name sender_field="" verified=0
    if (( migrate )); then
        [[ -n "$claimed_from" ]] || note_die "migrate-requires-claimed-from"
        local local_part
        if local_part="$(note_xrepo_local_part "$claimed_from")"; then
            sender_name="$(note_id_render "$local_part")"
        elif local_part="$(note_id_normalize "$claimed_from")"; then
            sender_name="$(note_id_render "$local_part")"
        else
            note_die "bad-claimed-from:$claimed_from"
        fi
        sender_field="$claimed_from"

        # Validate the COMPLETE variant before anything is written. Checking
        # only non-emptiness would let a short oid or a free-text date through
        # to a committed block the merger rejects everywhere else (F18).
        [[ -n "$claimed_at" ]] || note_die "migrate-requires-claimed-at"
        note_is_date_like "$claimed_at" \
            || note_die "bad-claimed-at:$claimed_at"
        [[ -n "$cli_base" ]] || note_die "migrate-requires-base"
        if note_is_base_sentinel "$cli_base"; then
            # No repo / no HEAD => no branch. Accepting one here would emit a
            # block whose base and base_branch disagree.
            [[ -z "$cli_base_branch" ]] \
                || note_die "base-branch-with-sentinel-base:$cli_base"
        else
            note_is_full_oid "$cli_base" \
                || note_die "base-not-a-full-oid:$cli_base"
            [[ -n "$cli_base_branch" ]] \
                || note_die "migrate-requires-base-branch"
            note_is_branch_like "$cli_base_branch" \
                || note_die "bad-base-branch:$cli_base_branch"
        fi
        [[ "$local_part" != "$target_bare" ]] || {
            printf 'NOTE_SELF:%s\n' "$(note_sanitize_field "$target_bare")"; return 1; }
    else
        [[ -n "$from_raw" ]] || note_die "missing-from"
        local from_bare
        from_bare="$(note_id_normalize "$from_raw")" \
            || note_die "bad-task-id:$from_raw"
        if [[ "$from_bare" == "$target_bare" ]]; then
            printf 'NOTE_SELF:%s\n' "$(note_sanitize_field "$target_bare")"
            return 1
        fi
        sender_name="$(note_id_render "$from_bare")"
        sender_field="$sender_name"
        # from_verified=yes ONLY when this session provably holds the sender's
        # lock; otherwise the field is OMITTED — never 'no', so absence and
        # disproof stay distinct.
        note_sender_is_self "$from_bare" && verified=1
    fi

    # --- Body ---
    #
    # NUL must be checked on the SOURCE BYTES, not on the variable: a bash
    # string cannot hold a NUL at all (command substitution silently drops it),
    # so by the time the body is in a variable the evidence is already gone.
    # `[[ "$b" != *$'\0'* ]]` in particular is a trap — $'\0' is the empty
    # string, so the pattern degenerates to `**` and matches everything.
    local raw_body="" src=""
    if [[ -n "$body_file" ]]; then
        src="$TMPBODY"
        if [[ "$body_file" == "-" ]]; then
            cat > "$src"
        else
            [[ -r "$body_file" ]] || note_die "unreadable-file:$body_file"
            cat -- "$body_file" > "$src"
        fi
        # Portable NUL detection: stripping NULs changes the byte count iff any
        # were present. `grep -P '\x00'` is not available on BSD/macOS.
        # shellcheck disable=SC2094  # both sides READ $src; nothing writes it.
        if ! LC_ALL=C tr -d '\000' < "$src" | cmp -s - "$src"; then
            note_die "body-contains-nul"
        fi
        local bytes; bytes=$(wc -c < "$src" | tr -d ' ')
        (( bytes <= NOTE_MAX_BODY_BYTES )) \
            || note_die "body-too-large:${bytes}>${NOTE_MAX_BODY_BYTES}"
        raw_body="$(cat "$src")"
    elif [[ -n "$body_text" ]]; then
        # argv is NUL-terminated by the kernel, so a --text value provably
        # cannot contain one; only the size bound applies here.
        raw_body="$body_text"
        local bytes; bytes=$(printf '%s' "$raw_body" | wc -c | tr -d ' ')
        (( bytes <= NOTE_MAX_BODY_BYTES )) \
            || note_die "body-too-large:${bytes}>${NOTE_MAX_BODY_BYTES}"
    else
        note_die "missing-body"
    fi

    local body; body="$(note_render_body "$raw_body")"

    # --- Marker fields, in contract order ---
    local -a kv=("from=$sender_field")
    (( verified )) && kv+=("from_verified=yes")
    kv+=("at=$(note_iso_now)")

    if (( migrate )); then
        # Provenance is SUPPLIED, never captured: capturing today's HEAD would
        # misrepresent exactly the stale-context claim the entry records. No
        # dirty/host — neither was ever observed, and writing dirty=no on a
        # historical note would be a fabricated observation.
        kv+=("claimed_at=$claimed_at" "base=$cli_base")
        [[ -n "$cli_base_branch" ]] && kv+=("base_branch=$cli_base_branch")
        kv+=("migrated=yes")
    else
        note_capture_provenance
        kv+=("base=$PROV_BASE")
        [[ -n "$PROV_BASE_BRANCH" ]] && kv+=("base_branch=$PROV_BASE_BRANCH")
        [[ -n "$PROV_MERGEBASE" ]] && kv+=("base_mergebase=$PROV_MERGEBASE")
        kv+=("dirty=$PROV_DIRTY" "host=$(hostname)")
    fi

    LOCK_KEY="$target_bare"
    note_append_locked "$file" "$sender_name" "$body" "${kv[@]}"

    # --- Persist: path-scoped commit, then best-effort push ---
    #
    # The lock does NOT span the commit: contention is on the repo-global
    # .git/index.lock, not the per-task key, so spanning it would only lengthen
    # the window in which a second `ait note` to this task exhausts its acquire
    # budget. What must be right is the REPORTING — see below.
    local reason=""
    task_git add -- "$file" 2>/dev/null \
        || reason="git-add-failed"
    if [[ -z "$reason" ]]; then
        task_git commit -m "ait: Record note $NOTE_ID for t${target_bare}" \
            -- "$file" >/dev/null 2>&1 || reason="git-commit-failed"
    fi

    if [[ -n "$reason" ]]; then
        # The append LANDED, so the note is durable on disk and owns an id.
        # Reporting this as NOTE_ERROR would read as "nothing happened" and the
        # caller's retry would append a SECOND note. Id-bearing outcome instead,
        # mirroring aitask_gate.sh's MATERIALIZED_UNCOMMITTED.
        #
        # The recovery hint is path-scoped: task data is a shared multi-writer
        # branch, so a blanket `add aitasks/` would sweep another session's
        # uncommitted work into this note's commit. It goes to STDERR — stdout
        # stays exactly one parseable line.
        warn "note recorded but not committed. Recover with:
  ./ait git add -- $file && ./ait git commit -m \"ait: Record note $NOTE_ID for t${target_bare}\" -- $file"
        printf 'NOTE_APPENDED_UNCOMMITTED:%s|%s|%s\n' \
            "$NOTE_ID" "$file" "$(note_sanitize_field "$reason")"
        return 1
    fi

    task_push >/dev/null 2>&1 || true
    printf 'NOTE_APPENDED:%s|%s\n' "$NOTE_ID" "$file"
    return 0
}

main "$@"
