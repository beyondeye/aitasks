#!/usr/bin/env bash
# test_no_unscoped_task_commit.sh — anti-regression guard for the t1599 sweep.
#
# `task_git commit -m "..."` with NO `--` pathspec commits the ENTIRE git index,
# not just the paths the script staged. On the shared task-data branch that means
# any file a concurrent session has staged at that instant lands in a commit whose
# message names a different task. t1599_1/2/3 fixed the three empirical sites;
# t1599_4 converted the remaining latent ones. This test stops new ones appearing.
#
# The cure is `task_git_commit_scoped` (lib/task_utils.sh), which carries the two
# non-obvious parts: the empty-pathspec guard (`git commit --` with no pathspec
# commits the whole index anyway) and a separately-captured `git status` exit, so
# a failing status reads as *unverified* rather than *clean*. On a path that may
# already be TRACKED and staged by another session, prefer its caller
# `ait_commit_paths_staging_untracked` (t1702): the scoped helper's own default
# `add` would replace that session's index entry, which is a second shared-index
# hazard this guard does not detect.
#
# Detection scope (documented on purpose — a guard that overclaims is worse than
# one with a known boundary):
#   * SCANNED: `.aitask-scripts/**/*.sh`. Logical lines are reassembled first, so
#     a command split across a `\` continuation is judged whole — two real,
#     correctly-scoped sites in aitask_note.sh are split exactly that way, and a
#     naive line-at-a-time grep reports them as violations.
#   * MATCHES: `task_git` followed by whitespace and `commit`. That deliberately
#     does NOT match `task_git_commit_scoped` (no space), which is the fix.
#   * A commit is considered scoped when the logical line contains `--` as a
#     standalone token OUTSIDE any quoted string. Escapes are collapsed before
#     quotes are removed, so `-m "… \" -- …"` does not read as a pathspec.
#   * FAILS CLOSED. A line whose quoting cannot be parsed (unbalanced quotes, a
#     quote arriving from an expansion) is reported, never assumed scoped —
#     under-detection here would be a silent index-wide commit.
#   * NOT scanned: comment lines; `tests/` (fixtures legitimately construct
#     unscoped argv to prove the defect); and `*.py` — `task_git` is a bash
#     function with no Python callers.
#   * NOT SEEN: a commit assembled through a variable (`$cmd commit …`) or built
#     up across separate statements. This is a grep over reassembled lines, so it
#     catches the common single-command shape and nothing subtler.
#   * ALSO SCANNED (t1728): `./ait git commit`. `./ait git <args>` is literally
#     `task_git <args>` in a subprocess (`ait` sources lib/task_utils.sh and
#     dispatches to it), so it carries the identical hazard and the identical
#     cure. It gets its own pattern because it needs its own matching rule:
#     * it is matched against the QUOTE-STRIPPED line, not the raw one. Five
#       occurrences in the tree are recovery-hint PROSE inside message strings
#       (aitask_sync.sh, aitask_setup.sh, lib/txn_snapshot.sh, and two in
#       aitask_note.sh), not commands. Stripping balanced quoted spans before
#       matching removes three of them for free, because a command's own
#       `./ait git commit` always sits outside the quotes.
#     * the remaining two are continuation PHYSICAL lines of multi-line `warn`
#       strings in aitask_note.sh. Only `\`-continuations are reassembled, so
#       those lines carry unbalanced quoting and fail closed -- correctly, since
#       relaxing that is what `aitask_unbalanced_quote.sh` below exists to
#       forbid. They are suppressed by AIT_GIT_ALLOWLIST instead, which applies
#       to THIS PATTERN ONLY: aitask_note.sh stays fully guarded for
#       `task_git commit`, which is how it actually commits task data. The hole
#       is one file, one pattern, and it closes when those two hint strings are
#       restructured onto a single logical line.
#   * ALSO SCANNED (t1762): plain `git commit`, over the SAME markdown enumeration
#     as the t1748 seam. `main` is shared by every session in this checkout exactly
#     as `.aitask-data` is, so an instructed `git commit` with no pathspec sweeps
#     whatever a concurrent session has staged. This is only tractable because the
#     enumeration is already narrowed to instruction trees, where a `git commit` is
#     a command an agent will run; the same pattern over `.aitask-scripts/**/*.sh`
#     would fire on every legitimate code commit, which is why it is NOT added
#     there. Its rules:
#     * `git commit-tree` is excluded structurally (trailing character class):
#       it is plumbing, it writes an object and never touches the index.
#     * a segment naming `./ait git commit` or `task_git commit` is skipped -- one
#       command per segment, one seam per command, so a single site can never be
#       reported twice.
#     * the bare-name prose mention rule is applied PER SEGMENT here (seam 3
#       applies it to the whole candidate), because the shape that occurs is a
#       sentence listing several commands: `git add -A && git commit && git push`
#       describes another system's runner and every segment is a noun.
#     * the two real exceptions -- a merge commit (git refuses a partial commit
#       during a merge; verified) and an isolated single-session sandbox -- are
#       declared with a LINE-SCOPED `<!-- unscoped-commit-ok: <reason> -->` marker
#       exempting the NEXT candidate line only. A file-level allowlist entry would
#       be too coarse: aitask-pickweb/SKILL.md.j2 has one site that must be exempt
#       and another four lines below that must not. A marker with an empty reason
#       exempts nothing, and every honoured exception is printed.
#   * NOT SEEN by the t1762 seam, and deliberately so:
#     * a pathspec that EXPANDS to nothing (`-- "${files[@]}"` with an empty array,
#       or an unsubstituted `<placeholder>`). Textually it carries a `--` and
#       passes, yet `git commit -m x --` commits the whole index. The two sites
#       with a runtime-generated list guard it with an `if` that CONTAINS the
#       commit; the placeholder sites do not, and that residue is recorded as a
#       follow-up on t1762 rather than closed here.
#     * `git add` of a TRACKED path. This seam judges commits, not staging, so a
#       later edit can restore tracked-path staging beside a correct
#       `git commit -- <paths>` and stay green. A per-site staging manifest was
#       designed and deliberately not built (t1762); also a recorded follow-up.
#     * `git -C <dir> commit`, and any commit assembled through a variable.
#
# It is a regression tripwire, NOT a proof of absence.
#
# Run: bash tests/test_no_unscoped_task_commit.sh
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Allowlist ---------------------------------------------------------------
# Files permitted to issue a deliberately index-wide `task_git commit`, one entry
# per line with a `#` reason.
#
# It is EMPTY, and that is the intended end state: after t1599_4 every task-data
# commit in the tree names its own paths. An entry would only be justified by a
# commit whose path set is genuinely not enumerable at the call site AND cannot be
# expressed as a directory pathspec — aitask_zip_old.sh looked like that case and
# was still narrowed to two directory pathspecs, so the bar is high. Adding an
# entry means the swallow this guard exists to prevent becomes possible again in
# that file; say why in the comment.
ALLOWLIST=()

# Indirection so the negative controls can exercise allowlist suppression with a
# SYNTHETIC entry instead of pinning a real one (pattern from
# tests/test_no_lib_to_tui_import.sh).
ACTIVE_ALLOWLIST=(${ALLOWLIST[@]+"${ALLOWLIST[@]}"})

is_allowed() {
    local f="$1" a
    for a in ${ACTIVE_ALLOWLIST[@]+"${ACTIVE_ALLOWLIST[@]}"}; do
        [[ "$f" == "$a" ]] && return 0
    done
    return 1
}

# Files exempt from the `./ait git commit` pattern ONLY. Deliberately separate
# from ALLOWLIST above: an entry here suppresses one seam in one file and leaves
# `task_git commit` fully guarded there, so it is a far smaller concession than
# an ALLOWLIST entry. It is NOT a place to park a real unscoped command -- the
# one entry is prose that the scanner cannot parse, and the header says exactly
# why. Adding another means saying, in the comment, why the match is not a
# command.
AIT_GIT_ALLOWLIST=(
    # Two recovery HINTS inside multi-line `warn` strings (both already written
    # with a `-- $file` pathspec, for anyone who copies them). They are
    # continuation physical lines, so their quoting is unparseable and the
    # fail-closed rule reports them. aitask_note.sh issues no `./ait git commit`
    # command of its own; its real task-data commits go through `task_git` and
    # are still scanned by the primary pattern.
    ".aitask-scripts/aitask_note.sh"
)
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})

is_ait_git_allowed() {
    local f="$1" a
    for a in ${ACTIVE_AIT_GIT_ALLOWLIST[@]+"${ACTIVE_AIT_GIT_ALLOWLIST[@]}"}; do
        [[ "$f" == "$a" ]] && return 0
    done
    return 1
}

# Files exempt from the MARKDOWN (instruction-layer) scan only (t1748). A third,
# independent list for the same reason AIT_GIT_ALLOWLIST is separate from
# ALLOWLIST: an entry suppresses one seam in one file and leaves the others
# guarded there.
#
# It is EMPTY, and that is the intended end state. The false positive this scan
# actually has -- prose that quotes the bad shape in order to FORBID it -- is
# handled structurally by MD_BARE_MENTION_RE below, not by an entry here, so
# that a doc which teaches the rule stays guarded against a bad worked example
# of its own. An entry would only be justified by a match that is provably not a
# command an agent can run; say why in the comment.
MD_ALLOWLIST=()
ACTIVE_MD_ALLOWLIST=(${MD_ALLOWLIST[@]+"${MD_ALLOWLIST[@]}"})

is_md_allowed() {
    local f="$1" a
    for a in ${ACTIVE_MD_ALLOWLIST[@]+"${ACTIVE_MD_ALLOWLIST[@]}"}; do
        [[ "$f" == "$a" ]] && return 0
    done
    return 1
}

# Files exempt from the PLAIN `git commit` markdown scan only (t1762). A fourth
# list, separate for the same reason the other three are separate from each
# other: an entry suppresses one seam in one file.
#
# It is EMPTY, and that is the intended end state. The two real exceptions --
# a merge commit and an isolated single-session sandbox -- are declared
# LINE-scoped with an `<!-- unscoped-commit-ok: … -->` marker instead, because a
# file entry is too coarse: aitask-pickweb/SKILL.md.j2 carries one site that
# must be exempt and another, four lines below, that must not, and a file entry
# would pin a bypass over the second. An entry here would only be justified by a
# whole file that is provably not instruction; say why in the comment.
MD_PLAIN_ALLOWLIST=()
ACTIVE_MD_PLAIN_ALLOWLIST=(${MD_PLAIN_ALLOWLIST[@]+"${MD_PLAIN_ALLOWLIST[@]}"})

is_md_plain_allowed() {
    local f="$1" a
    for a in ${ACTIVE_MD_PLAIN_ALLOWLIST[@]+"${ACTIVE_MD_PLAIN_ALLOWLIST[@]}"}; do
        [[ "$f" == "$a" ]] && return 0
    done
    return 1
}

# --- Scanner -----------------------------------------------------------------
# Reassemble `\`-continued lines, reporting the line number the command STARTS on.
# Load-bearing: aitask_note.sh:623 and :995 put their `-- "$file"` on the
# continuation line, and without this they are reported as violations.
JOIN_AWK='
{
    line = $0; start = NR
    while (line ~ /\\[ \t]*$/) {
        if ((getline nxt) <= 0) break
        sub(/\\[ \t]*$/, " ", line)
        line = line nxt
    }
    print start ":" line
}'

# A `task_git commit` invocation (NOT task_git_commit_scoped, which has no space).
COMMIT_RE='task_git[[:space:]]+commit'
# The second seam: `./ait git commit` / `ait git commit`. The leading class
# rejects a longer identifier ending in "ait", and `(\./)?` lets the class match
# the whitespace before the `./` rather than the `/` itself.
AIT_GIT_COMMIT_RE='(^|[^[:alnum:]_/.])(\./)?ait[[:space:]]+git[[:space:]]+commit'
# The fourth seam (t1762): PLAIN `git commit` on the MAIN branch. `main` is
# shared by every session in this checkout exactly as `.aitask-data` is, so a
# `git commit` with no pathspec sweeps whatever a concurrent session has staged.
#
# The trailing class is what excludes `git commit-tree`: that is plumbing, it
# writes an object and never touches the index, and the tree has ~20 legitimate
# uses of it. The leading class rejects a longer identifier ending in "git".
# `./ait git commit` and `task_git commit` also literally contain "git commit";
# they are NOT excluded here but in md_judge_plain, which skips any segment that
# belongs to one of the other seams -- one command per segment, one seam per
# command, so a single site can never be double-reported.
PLAIN_GIT_COMMIT_RE='(^|[^[:alnum:]_/.-])git[[:space:]]+commit([^[:alnum:]_-]|$)'
# The same command written with NO code formatting at all. Seam 3 fails closed on
# that shape, and must: nobody writes "./ait git commit" in an English sentence.
# Plain `git commit` is different -- "the path-scoped git commit failed", "the
# runner handles git commit + push", "(parent auto-archival, git commit)" are all
# real, ordinary prose in this tree, and failing closed on them would flag five
# sentences that instruct nothing. So an UNFORMATTED occurrence is judged as a
# command only when it is followed by something option-shaped. The convention this
# leans on is the tree's own and is enforced everywhere else: a command an agent
# is meant to run is fenced or backticked. The residual hole -- "then run git
# commit and push" with no formatting and no flag -- is invisible, and is the same
# documented shape as seam 3's bare-mention hole.
PLAIN_GIT_INVOCATION_RE='(^|[^[:alnum:]_/.-])git[[:space:]]+commit[[:space:]]+-'
# `--` as a standalone token = a pathspec separator is present.
SCOPED_RE='[[:space:]]--([[:space:]]|$)'

# is_scoped <logical-line> — 0 when the line provably carries a `--` pathspec
# separator, 1 otherwise. **Fails closed**: anything it cannot parse confidently
# counts as NOT scoped, so the line gets reported rather than waved through.
#
# Quoted arguments are removed before the separator test, because a commit
# MESSAGE may legitimately contain " -- " (`-m "ait: title -- annotation"`).
# Counting that as a pathspec would let an index-wide commit past the guard — a
# false negative, the one direction this guard must never fail in. A real
# `-- <paths>` separator always sits OUTSIDE the quotes.
#
# Escapes are collapsed FIRST. Without that step `\"` ends a quoted span early:
# `-m "ait: escaped \" -- annotation"` would strip to `-m "" -- annotation"` and
# the `--` still inside the shell string would read as a pathspec. That is a
# valid, ordinary shell form, not an exotic one, so it must be parsed rather than
# disclaimed.
#
# After removal no quote character should remain. One that does means the quoting
# is unbalanced or beyond this scanner (a here-doc body, an expansion that emits
# a quote), and the line is treated as unparseable — reported, never trusted.
# strip_quoted <line> — the line with escapes collapsed and balanced quoted
# spans removed. Shared by is_scoped and by the `./ait git commit` match, so the
# two can never disagree about what counts as "inside a string".
strip_quoted() {
    printf '%s\n' "$1" \
        | sed -e 's/\\./_/g' -e "s/'[^']*'//g" -e 's/"[^"]*"//g'
}

# bare_is_scoped <ALREADY-stripped text> — the decision half of is_scoped, split
# out (t1748) so the markdown scan can apply it to ONE SEGMENT of a line rather
# than to a whole line. `./ait git add -- <p> && ./ait git commit -m "x"` is a
# violation: the `--` belongs to the add, and judging the line whole would let it
# launder the commit. The shell seams keep calling is_scoped and are unchanged.
bare_is_scoped() {
    # Unbalanced / unparseable quoting: fail closed.
    case "$1" in *\"*|*\'*) return 1 ;; esac
    [[ "$1" =~ $SCOPED_RE ]]
}

is_scoped() { bare_is_scoped "$(strip_quoted "$1")"; }

# --- Seam 3: the instruction layer (markdown / Jinja), t1748 -----------------
#
# ENUMERATION. The scope decision lives in ONE predicate, md_in_scope, and both
# listers are dumb. The tempting alternative -- put the allowed roots in the
# `git ls-files` pathspec and give the fixture tree a plain `find` -- puts half
# the contract on a path the fixtures cannot reach, so a planted
# `website/content/x.md` could never prove the exclusion. Default DENY.

# Allowed roots (prefix match) and allowed exact files: THE SCOPE CONTRACT.
MD_ROOTS=(
    ".claude/skills/"
    ".agents/skills/"
    ".opencode/skills/"
    ".opencode/commands/"
    ".aitask-scripts/skill_templates/"
    "aidocs/"
)
MD_FILES=(
    "CLAUDE.md"
    "AGENTS.md"
    ".codex/instructions.md"
    ".opencode/instructions.md"
    "seed/aitasks_agent_instructions.seed.md"
)

# md_in_scope <repo-relative-path> — 0 iff the markdown scan owns this file.
md_in_scope() {
    local p="$1" r f
    case "$p" in *.md | *.j2) : ;; *) return 1 ;; esac
    # Exclusions first, so an excluded path under an allowed root still loses.
    case "$p" in tests/golden/*) return 1 ;; esac   # committed render snapshots
    case "/$p" in */*-/*) return 1 ;; esac          # rendered per-profile dirs
    for f in ${MD_FILES[@]+"${MD_FILES[@]}"}; do [[ "$p" == "$f" ]] && return 0; done
    for r in ${MD_ROOTS[@]+"${MD_ROOTS[@]}"}; do [[ "$p" == "$r"* ]] && return 0; done
    return 1
}

md_filter() {
    local p
    while IFS= read -r p; do md_in_scope "$p" && printf '%s\n' "$p"; done
}

# The real tree. The pathspec is deliberately BROAD -- narrowing it to the
# allowed roots would move half the contract back out of md_in_scope and make
# the out-of-scope assertions untestable. `git ls-files`, not `find`: the stale
# orphaned `*_skillrun_*-/` render dirs are gitignored but present on disk, and
# an uncommitted instruction file is not one any agent follows from a clone.
md_sources_real() {
    git -C "$PROJECT_DIR" ls-files -- '*.md' '*.j2' | md_filter
}

# The fixture tree, which is not a git repo. Dumber lister, SAME predicate.
md_sources_find() {
    ( cd "$1" && find . -type f \( -name '*.md' -o -name '*.j2' \) \
        | sed 's|^\./||' | sort ) | md_filter
}

# EXTRACTION. Markdown has no `\` continuation outside a fence, and it has a
# second container the shell scan knows nothing about: the inline backtick span.
# A fence-body-only scanner would miss nine real sites. So this is its own join,
# NOT a reuse of JOIN_AWK above (which see) -- the fence state is what decides
# whether a trailing `\` even means continuation.
#
# Emits `F:<line>:<text>` for a fence body and `P:<line>:<text>` for prose. A
# span still open after four forward lines, and a file ending inside a fence
# while containing the pattern at all, both emit the AIT_UNPARSEABLE_SPAN
# sentinel, which md_judge reports rather than trusts.
#
# Only CANDIDATE lines are emitted -- every line still updates fence state and is
# still eligible for both joins, but a line that cannot possibly name the command
# is dropped here rather than in the shell. That is a performance contract, not a
# scope one: the caller forks awk per candidate line, and emitting all ~90k lines
# of the surface instead of the ~40 that match made this scan take minutes.
#
# t1762 widened the emit filter and the span-rejoin trigger from `ait git commit`
# to any `git[ \t]+commit`, so the fourth seam's candidates reach the judge too.
# That is a PERFORMANCE contract, not a scope one: md_judge still returns 1
# immediately for anything that does not match AIT_GIT_COMMIT_RE, so seam 3 is
# behaviourally unchanged and only sees more lines it discards. The widening
# costs ~5x the candidate lines (~40 -> ~200 across the surface).
MD_JOIN_AWK='
function emit(kind, start, line) {
    if (line ~ /git[ \t]+commit/ || line ~ /AIT_UNPARSEABLE_SPAN/)
        print kind ":" start ":" line
}
{ if ($0 ~ /git[ \t]+commit/) seen = 1 }
/^[[:space:]]*```/ { infence = !infence; next }
{
  line = $0; start = NR
  if (infence) {
      while (line ~ /\\[ \t]*$/) {
          if ((getline nxt) <= 0) break
          if (nxt ~ /^[[:space:]]*```/) { infence = !infence; break }
          sub(/\\[ \t]*$/, " ", line); line = line nxt
      }
      emit("F", start, line)
      next
  }
  joins = 0
  while ((gsub(/`/, "`", line) % 2) == 1 && line ~ /`[^`]*git[ \t]/) {
      if (joins++ >= 4) { line = line " AIT_UNPARSEABLE_SPAN"; break }
      if ((getline nxt) <= 0) { line = line " AIT_UNPARSEABLE_SPAN"; break }
      line = line " " nxt
  }
  emit("P", start, line)
}
END { if (infence && seen) print "P:" NR ":AIT_UNPARSEABLE_SPAN eof-in-fence" }'

# md_spans <line> — the contents of each inline backtick span, one per line.
md_spans() {
    printf '%s\n' "$1" | awk '{
        n = split($0, parts, "`")
        for (i = 2; i <= n; i += 2) print parts[i]
    }'
}

# md_strip_spans <line> — the line with every balanced backtick span removed.
# If the command still shows through, it was written with no code formatting at
# all: a shape this scanner does not model, so it fails closed.
md_strip_spans() {
    printf '%s\n' "$1" | awk '{
        n = split($0, parts, "`"); out = ""
        for (i = 1; i <= n; i += 2) out = out parts[i] " "
        print out
    }'
}

# The command NAME with no arguments: the command used as a NOUN, not issued as
# one. Prose only -- inside a fence a lone command line IS a command.
MD_BARE_MENTION_RE='^[[:space:]]*(\./)?ait[[:space:]]+git[[:space:]]+commit[[:space:]]*$'

# md_judge <rel> <lineno> <candidate> <fence|prose> — print a violation and
# return 0 if the candidate is an unscoped instruction; return 1 otherwise.
md_judge() {
    local rel="$1" lineno="$2" cand="$3" ctx="$4" bare seg
    case "$cand" in
        *AIT_UNPARSEABLE_SPAN*)
            printf '%s:%s:%s\n' "$rel" "$lineno" "$cand"; return 0 ;;
    esac
    bare="$(strip_quoted "$cand")"
    [[ "$bare" =~ $AIT_GIT_COMMIT_RE ]] || return 1
    # Unbalanced / unparseable quoting: fail closed, as the shell seams do.
    case "$bare" in
        *\"* | *\'*) printf '%s:%s:%s\n' "$rel" "$lineno" "$cand"; return 0 ;;
    esac
    if [[ "$ctx" == "prose" && "$bare" =~ $MD_BARE_MENTION_RE ]]; then
        return 1
    fi
    # Judge per SEGMENT, not per line: the `--` in
    # `./ait git add -- <p> && ./ait git commit -m "x"` belongs to the add.
    # Splitting AFTER strip_quoted means every separator is outside a string.
    while IFS= read -r seg; do
        [[ "$seg" =~ $AIT_GIT_COMMIT_RE ]] || continue
        # Cut a trailing shell comment, or `-m "x"  # use -- for a pathspec`
        # reads as scoped. Leading whitespace required, so `http://x#y` survives.
        seg="${seg%%[[:space:]]#*}"
        bare_is_scoped "$seg" && continue
        printf '%s:%s:%s\n' "$rel" "$lineno" "$cand"
        return 0
    done < <(printf '%s\n' "$bare" | awk '{
        n = split($0, a, /&&|\|\||;|\|/); for (i = 1; i <= n; i++) print a[i]
    }')
    return 1
}

# --- Seam 4: plain `git commit` in the instruction layer, t1762 --------------
#
# Same enumeration (md_in_scope), same join (MD_JOIN_AWK), same quote handling
# (strip_quoted / bare_is_scoped), same segmenter, same prose mention rule. Only
# the pattern and the exception mechanism are new, so the two markdown seams can
# never disagree about what "inside a string" or "one segment" means.

# A prose span whose whole content is the bare command name is the command used
# as a NOUN. Applied PER SEGMENT for this seam (seam 3 applies it to the whole
# candidate), because the shape that actually occurs is a prose sentence listing
# several commands: `git add -A && git commit && git push` describes a different
# system's runner, and every one of its segments is a bare name.
MD_PLAIN_BARE_MENTION_RE='^[[:space:]]*git[[:space:]]+commit[[:space:]]*$'

# An in-line, LINE-SCOPED exception. Exempts the NEXT candidate line after it and
# nothing else, so a marker cannot cover a neighbouring site that has a cure.
# The reason is required: an exception nobody can read is an allowlist entry with
# extra steps, and the scan prints every one it honours.
MD_EXCEPTION_RE='<!--[[:space:]]*unscoped-commit-ok:[[:space:]]*([^>]*[^[:space:]>])[[:space:]]*-->'

# md_exception_lines <file> — `<lineno>:<reason>` per well-formed marker.
# A marker with an EMPTY reason is deliberately not emitted, so the site it
# meant to cover stays flagged rather than being waved through by a blank claim.
md_exception_lines() {
    grep -nE "$MD_EXCEPTION_RE" "$1" 2>/dev/null \
        | sed -E "s/^([0-9]+):.*<!--[[:space:]]*unscoped-commit-ok:[[:space:]]*([^>]*[^[:space:]>])[[:space:]]*-->.*/\1:\2/"
}

# md_judge_plain <rel> <lineno> <candidate> <fence|prose> — print a violation and
# return 0 if the candidate is an unscoped plain-git instruction; else return 1.
md_judge_plain() {
    local rel="$1" lineno="$2" cand="$3" ctx="$4" bare seg
    case "$cand" in
        *AIT_UNPARSEABLE_SPAN*) return 1 ;;   # seam 3 already reports these
    esac
    bare="$(strip_quoted "$cand")"
    [[ "$bare" =~ $PLAIN_GIT_COMMIT_RE ]] || return 1
    case "$bare" in
        *\"* | *\'*)
            # Unparseable quoting fails closed, as every other seam does -- but a
            # candidate that names ANOTHER seam's command is that seam's to
            # report, and it fails closed there identically. Returning 1 here
            # loses no defect and stops one line being reported twice.
            [[ "$bare" =~ $AIT_GIT_COMMIT_RE ]] && return 1
            [[ "$bare" =~ task_git[[:space:]]+commit ]] && return 1
            printf '%s:%s:%s\n' "$rel" "$lineno" "$cand"; return 0 ;;
    esac
    while IFS= read -r seg; do
        [[ "$seg" =~ $PLAIN_GIT_COMMIT_RE ]] || continue
        # One command per segment, one seam per command: a segment naming
        # `./ait git commit` or `task_git commit` is the other seams' business,
        # and reporting it here would double-report a single defect.
        [[ "$seg" =~ $AIT_GIT_COMMIT_RE ]] && continue
        [[ "$seg" =~ task_git[[:space:]]+commit ]] && continue
        [[ "$ctx" == "prose" && "$seg" =~ $MD_PLAIN_BARE_MENTION_RE ]] && continue
        seg="${seg%%[[:space:]]#*}"
        bare_is_scoped "$seg" && continue
        printf '%s:%s:%s\n' "$rel" "$lineno" "$cand"
        return 0
    done < <(printf '%s\n' "$bare" | awk '{
        n = split($0, a, /&&|\|\||;|\|/); for (i = 1; i <= n; i++) print a[i]
    }')
    return 1
}

# scan_md_plain <file>... — the fourth seam. Emits `V:<file>:<line>:<text>` for a
# violation and `X:<file>:<line>:<reason>` for a marker-honoured exception, so
# the caller can report both and the exceptions stay visible.
scan_md_plain() {
    local f entry kind lineno text cand stripped hit
    local -a exc_lines exc_reasons
    local i prev_cand exempt_idx
    for f in "$@"; do
        is_md_plain_allowed "$f" && continue
        exc_lines=(); exc_reasons=()
        while IFS= read -r entry; do
            exc_lines+=( "${entry%%:*}" ); exc_reasons+=( "${entry#*:}" )
        done < <(md_exception_lines "$f")
        prev_cand=0
        while IFS= read -r entry; do
            kind="${entry%%:*}"; entry="${entry#*:}"
            lineno="${entry%%:*}"; text="${entry#*:}"
            hit=""
            if [[ "$kind" == "F" ]]; then
                [[ -z "${text//[[:space:]]/}" ]] && continue
                [[ "$text" =~ ^[[:space:]]*# ]] && continue
                hit="$(md_judge_plain "$f" "$lineno" "$text" fence || true)"
            else
                # Unformatted first: an invocation-shaped `git commit -…` outside
                # any span. Judged on the span-stripped text but REPORTED with the
                # original line, so the message names what the author wrote. The
                # other two seams' commands are excluded here line-wise rather
                # than per segment -- coarser than md_judge_plain, and adequate
                # because this branch only ever sees unformatted prose.
                stripped="$(md_strip_spans "$text")"
                if [[ "$stripped" =~ $PLAIN_GIT_INVOCATION_RE ]] \
                   && ! [[ "$stripped" =~ $AIT_GIT_COMMIT_RE ]] \
                   && ! [[ "$stripped" =~ task_git[[:space:]]+commit ]]; then
                    hit="$f:$lineno:$text"
                fi
                if [[ -z "$hit" ]]; then
                    while IFS= read -r cand; do
                        [[ -z "${cand//[[:space:]]/}" ]] && continue
                        hit="$(md_judge_plain "$f" "$lineno" "$cand" prose || true)"
                        [[ -n "$hit" ]] && break
                    done < <(md_spans "$text")
                fi
            fi
            # Every candidate line advances `prev_cand`, flagged or not: a marker
            # exempts the NEXT candidate, and a marker sitting before an already
            # -passing site must not carry over to the next one.
            if [[ -n "$hit" ]]; then
                # The marker must sit between the previous candidate and this one.
                exempt_idx=-1
                for i in "${!exc_lines[@]}"; do
                    if (( exc_lines[i] < lineno && exc_lines[i] > prev_cand )); then
                        exempt_idx=$i
                    fi
                done
                if (( exempt_idx >= 0 )); then
                    printf 'X:%s:%s:%s\n' "$f" "$lineno" "${exc_reasons[exempt_idx]}"
                else
                    printf 'V:%s\n' "$hit"
                fi
            fi
            prev_cand="$lineno"
        done < <(awk "$MD_JOIN_AWK" "$f" 2>/dev/null)
    done
}

# scan_md <file>... — the markdown scan. Takes an EXPLICIT file list (unlike
# scan_dir, which walks a root) so the enumerator and the matcher can be tested
# independently.
scan_md() {
    local f entry kind lineno text cand stripped
    for f in "$@"; do
        is_md_allowed "$f" && continue
        while IFS= read -r entry; do
            kind="${entry%%:*}"; entry="${entry#*:}"
            lineno="${entry%%:*}"; text="${entry#*:}"
            if [[ "$kind" == "F" ]]; then
                [[ -z "${text//[[:space:]]/}" ]] && continue
                [[ "$text" =~ ^[[:space:]]*# ]] && continue
                md_judge "$f" "$lineno" "$text" fence || true
                continue
            fi
            stripped="$(md_strip_spans "$text")"
            if [[ "$stripped" =~ $AIT_GIT_COMMIT_RE ]]; then
                printf '%s:%s:%s\n' "$f" "$lineno" "$text"
                continue
            fi
            while IFS= read -r cand; do
                [[ -z "${cand//[[:space:]]/}" ]] && continue
                md_judge "$f" "$lineno" "$cand" prose && break
            done < <(md_spans "$text")
        done < <(awk "$MD_JOIN_AWK" "$f" 2>/dev/null)
    done
}

scan_dir() {
    local root="$1" f rel
    while IFS= read -r -d '' f; do
        rel="${f#"$root"/}"
        awk "$JOIN_AWK" "$f" 2>/dev/null | while IFS= read -r entry; do
            local lineno text bare
            lineno="${entry%%:*}"
            text="${entry#*:}"
            # Skip comment lines.
            [[ "$text" =~ ^[[:space:]]*# ]] && continue

            # Seam 1: `task_git commit`, matched on the RAW line. A mention
            # inside a string is vanishingly rare for this spelling, and
            # matching raw is what the existing controls pin.
            if ! is_allowed "$rel" && [[ "$text" =~ $COMMIT_RE ]]; then
                if ! is_scoped "$text"; then
                    printf '%s:%s:%s\n' "$rel" "$lineno" "$text"
                    continue
                fi
            fi

            # Seam 2: `./ait git commit`, matched on the QUOTE-STRIPPED line so
            # the recovery-hint prose in message strings is not mistaken for a
            # command. See the detection-scope note in the header.
            is_ait_git_allowed "$rel" && continue
            bare="$(strip_quoted "$text")"
            [[ "$bare" =~ $AIT_GIT_COMMIT_RE ]] || continue
            is_scoped "$text" && continue
            printf '%s:%s:%s\n' "$rel" "$lineno" "$text"
        done
    done < <(find "$root/.aitask-scripts" -type f -name '*.sh' -print0 2>/dev/null)
}

# --- Test 1: the real tree ---------------------------------------------------
violations="$(scan_dir "$PROJECT_DIR")"
TOTAL=$((TOTAL + 1))
if [[ -z "$violations" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: no unscoped task_git commit / ./ait git commit in .aitask-scripts/"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: unscoped task-data commit(s) found — these commit the WHOLE index:"
    printf '  UNSCOPED: %s\n' "$violations"
    echo "  -> use task_git_commit_scoped <msg> <path>... (lib/task_utils.sh), or add"
    echo "     an explicit '-- <paths>' pathspec. Reference patterns:"
    echo "     aitask_attach.sh:_attach_commit, aitask_gate_record.sh, aitask_gate.sh."
fi

# --- Test 2: the instruction layer (markdown / Jinja) ------------------------
mapfile -t MD_SOURCES < <(md_sources_real)

md_has() { printf '%s\n' ${MD_SOURCES[@]+"${MD_SOURCES[@]}"} | grep -qxF "$1"; }

# Scope assertions, BOTH directions. A count floor alone can be satisfied while
# the interesting root silently drops out, and it cannot detect the enumeration
# having GROWN to swallow human-facing documentation.
assert_exit_zero "markdown: the instruction surface was actually enumerated" \
    test "${#MD_SOURCES[@]}" -gt 150
assert_exit_zero "markdown: the canonical teaching skill is in scope" \
    md_has ".claude/skills/ait-git/SKILL.md"
assert_exit_zero "markdown: the root instruction doc is in scope" \
    md_has "CLAUDE.md"
assert_exit_zero "markdown: the shared instruction seed is in scope" \
    md_has "seed/aitasks_agent_instructions.seed.md"
assert_exit_zero "markdown: aidocs is in scope" \
    md_has "aidocs/framework/shell_conventions.md"

md_out_of_scope="$(printf '%s\n' ${MD_SOURCES[@]+"${MD_SOURCES[@]}"} \
    | grep -E '^(website|docs|tests|aitasks|aiplans)/|^\.aitask-data/|^README|^CHANGELOG|(^|/)[^/]*-/' \
    || true)"
assert_eq "markdown: no human-facing doc, record tree or rendered copy is enumerated" \
    "" "$md_out_of_scope"

# Anti-vacuity. After the sweep most sites route through aitask_task_commit.sh
# and the text is GONE, so a corpus count would be the wrong pin. These two keep
# `./ait git commit` (cured with an explicit `-- <path>`, because teaching that
# command IS their subject), so their text is a stable witness that the scan is
# reading something rather than matching nothing.
for witness in ".claude/skills/ait-git/SKILL.md" "CLAUDE.md"; do
    assert_exit_zero "markdown: '$witness' still carries ./ait git commit text" \
        grep -qE '(\./)?ait[[:space:]]+git[[:space:]]+commit' "$PROJECT_DIR/$witness"
done

md_violations="$(cd "$PROJECT_DIR" && scan_md ${MD_SOURCES[@]+"${MD_SOURCES[@]}"})"
TOTAL=$((TOTAL + 1))
if [[ -z "$md_violations" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: no unscoped ./ait git commit instruction in the skill / doc trees"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: unscoped task-data commit(s) INSTRUCTED — an agent will run these:"
    printf '  UNSCOPED: %s\n' "$md_violations"
    echo "  -> route through ./.aitask-scripts/aitask_task_commit.sh -m <msg> <paths>,"
    echo "     or add an explicit '-- <paths>' pathspec where teaching './ait git'"
    echo "     is the point. NOT task_git_commit_scoped: that is a bash function"
    echo "     with no PATH entry, so no agent can run it from an instruction."
fi

# --- Test 2b: plain `git commit` in the instruction layer (t1762) ------------
# Same enumeration as Test 2 -- MD_SOURCES is reused, so the scope assertions
# above cover this seam too and cannot drift from it.

# Anti-vacuity, and deliberately NOT a corpus count: the conversions themselves
# move any count. These two files keep plain `git commit` text on purpose --
# they are where the rule is taught, so they must demonstrate the command.
for plain_witness in \
    "aidocs/framework/skill_authoring_conventions.md" \
    ".claude/skills/ait-git/SKILL.md" \
; do
    assert_exit_zero "plain: '$plain_witness' still carries git commit text" \
        grep -qE '(^|[^[:alnum:]_/.-])git[[:space:]]+commit' "$PROJECT_DIR/$plain_witness"
done

md_plain_raw="$(cd "$PROJECT_DIR" && scan_md_plain ${MD_SOURCES[@]+"${MD_SOURCES[@]}"})"
md_plain_violations="$(printf '%s\n' "$md_plain_raw" | sed -n 's/^V://p')"
md_plain_exceptions="$(printf '%s\n' "$md_plain_raw" | sed -n 's/^X://p')"

if [[ -n "$md_plain_exceptions" ]]; then
    echo "NOTE: honoured unscoped-commit-ok exception(s):"
    # One prefixed line PER exception. A single `printf '%s'` of the multi-line
    # value prefixes only the first, and an exception nobody can see is the
    # thing this report exists to prevent.
    while IFS= read -r _exc; do
        printf '  EXCEPTION: %s\n' "$_exc"
    done <<< "$md_plain_exceptions"
fi

TOTAL=$((TOTAL + 1))
if [[ -z "$md_plain_violations" ]]; then
    PASS=$((PASS + 1))
    echo "PASS: no unscoped plain 'git commit' instruction in the skill / doc trees"
else
    FAIL=$((FAIL + 1))
    echo "FAIL: unscoped MAIN-branch commit(s) INSTRUCTED — an agent will run these:"
    printf '  UNSCOPED: %s\n' "$md_plain_violations"
    echo "  -> add an explicit '-- <paths>' pathspec naming what the step commits,"
    echo "     and drop any 'git add' of a path git already tracks (commit -- <paths>"
    echo "     takes a tracked path's worktree content without one)."
    echo "     Where a pathspec is genuinely impossible (a merge commit; an"
    echo "     isolated single-session sandbox), declare it on the line before:"
    echo "     <!-- unscoped-commit-ok: <reason> -->"
fi

# --- Negative controls -------------------------------------------------------
# Every direction gets its own fixture: a scan that silently matched nothing would
# pass Test 1 for the wrong reason.
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
mkdir -p "$TMP/.aitask-scripts"

cat > "$TMP/.aitask-scripts/aitask_rogue.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git add "$file"
    task_git commit -m "ait: rogue unscoped commit"
}
EOF

cat > "$TMP/.aitask-scripts/aitask_scoped.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: fine" -- "$file"
    task_git_commit_scoped "ait: also fine" "$file"
    task_git commit --amend --no-edit -o --quiet -- "${paths[@]}"
}
EOF

cat > "$TMP/.aitask-scripts/aitask_continued.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: scoped on the next line" \
        -- "$file" >/dev/null 2>&1
}
EOF

cat > "$TMP/.aitask-scripts/aitask_commented.sh" <<'EOF'
#!/usr/bin/env bash
# A bare task_git commit -m "x" would commit the whole index.
run() { :; }
EOF

# A `--` INSIDE the commit message is not a pathspec. Without strip_quoted this
# file is silently treated as scoped — a false negative, the one direction this
# guard must never fail in.
cat > "$TMP/.aitask-scripts/aitask_dashes_in_msg.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: title -- annotation"
}
EOF

# The same shape WITH a real separator must still pass: blanking the quoted span
# must not blind the scanner to a genuine pathspec sitting outside it.
cat > "$TMP/.aitask-scripts/aitask_dashes_and_paths.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: title -- annotation" -- "$file"
}
EOF

# An ESCAPED quote inside the message. Without collapsing escapes first, the
# quoted span ends early at `\"`, the `--` still inside the shell string reads as
# a pathspec, and an index-wide commit walks past the guard. This is ordinary
# shell, not an exotic form.
cat > "$TMP/.aitask-scripts/aitask_escaped_quote.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: escaped \" -- annotation"
}
EOF

# The escaped-quote shape WITH a real separator must still be accepted, so the
# escape handling cannot be "flag everything with a backslash".
cat > "$TMP/.aitask-scripts/aitask_escaped_quote_scoped.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: escaped \" annotation" -- "$file"
}
EOF

# Unbalanced quoting is unparseable, and unparseable must fail CLOSED.
#
# A MULTI-LINE message is the realistic source of this: only `\`-continuations
# are reassembled, so a string that spans physical lines leaves the commit's
# logical line with an unterminated quote. Here the `--` sits inside that string,
# so with no complete quote pair to remove, nothing is stripped and the `--`
# survives — a line that reads as "scoped" unless unparseable quoting is refused.
cat > "$TMP/.aitask-scripts/aitask_unbalanced_quote.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: multi-line -- message
    continues on the next line"
}
EOF

# --- `./ait git commit` fixtures (t1728) -------------------------------------

# The rogue shape on the second seam. `./ait git` is task_git in a subprocess,
# so this commits the whole shared index exactly as the first seam does.
cat > "$TMP/.aitask-scripts/aitask_ait_git_rogue.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    ./ait git add "$file"
    ./ait git commit -m "ait: rogue unscoped ait-git commit"
}
EOF

# Invoked without the `./` prefix — same command, same hazard.
cat > "$TMP/.aitask-scripts/aitask_ait_git_bare_prefix.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    ait git commit -m "ait: rogue without the dot-slash"
}
EOF

# The scoped shape must NOT be flagged: `-- <paths>` is a valid cure, and the
# guard's own failure hint offers it.
cat > "$TMP/.aitask-scripts/aitask_ait_git_scoped.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    ./ait git commit -m "ait: fine" -- "$file"
    ait_commit_paths_staging_untracked "ait: also fine" "$file"
}
EOF

# A recovery HINT inside a message string is prose, not a command, and must NOT
# be flagged. This is why the second seam matches on the quote-stripped line —
# five such occurrences exist in the real tree and none of them is a call.
cat > "$TMP/.aitask-scripts/aitask_ait_git_hint.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    die "path has uncommitted changes. Commit it (./ait git commit -- $p) or revert it."
}
EOF

# The seam must not be blinded by a longer identifier that merely ENDS in "ait":
# `portrait git commit` is not an `ait` invocation.
cat > "$TMP/.aitask-scripts/aitask_ait_git_lookalike.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    portrait git commit -m "not the ait dispatcher"
}
EOF

neg="$(scan_dir "$TMP")"

assert_contains "negative: a rogue unscoped commit IS flagged" \
    "aitask_rogue.sh" "$neg"
assert_not_contains "a commit carrying -- <paths> is NOT flagged" \
    "aitask_scoped.sh" "$neg"
assert_not_contains "a commit scoped on a CONTINUATION line is NOT flagged" \
    "aitask_continued.sh" "$neg"
assert_not_contains "prose in a comment is NOT flagged" \
    "aitask_commented.sh" "$neg"
assert_contains "a '--' inside the commit MESSAGE is not a pathspec — still flagged" \
    "aitask_dashes_in_msg.sh" "$neg"
assert_not_contains "a quoted '--' plus a REAL separator is not flagged" \
    "aitask_dashes_and_paths.sh" "$neg"
assert_contains "an ESCAPED quote does not end the message early — still flagged" \
    "aitask_escaped_quote.sh" "$neg"
assert_not_contains "an escaped quote plus a REAL separator is not flagged" \
    "aitask_escaped_quote_scoped.sh" "$neg"
assert_contains "unbalanced quoting is unparseable and fails CLOSED" \
    "aitask_unbalanced_quote.sh" "$neg"

assert_contains "negative: a rogue unscoped ./ait git commit IS flagged" \
    "aitask_ait_git_rogue.sh" "$neg"
assert_contains "negative: the same command without ./ IS flagged" \
    "aitask_ait_git_bare_prefix.sh" "$neg"
assert_not_contains "an ./ait git commit carrying -- <paths> is NOT flagged" \
    "aitask_ait_git_scoped.sh" "$neg"
assert_not_contains "a recovery hint inside a message string is NOT flagged" \
    "aitask_ait_git_hint.sh" "$neg"
assert_not_contains "a longer identifier ending in 'ait' is NOT flagged" \
    "aitask_ait_git_lookalike.sh" "$neg"

# Exactly six violations across the fourteen fixtures — pins that the scan is
# neither over- nor under-matching. Four come from the `task_git commit` seam
# and two from `./ait git commit`; a fixture that stopped being detected, or one
# that started being over-detected, moves this number.
neg_count="$(printf '%s\n' "$neg" | grep -c 'aitask_' || true)"
assert_eq "negative: exactly six violations across the fixture tree" "6" "$neg_count"

# The reported location is the line the command STARTS on.
assert_contains "negative: violation names file:line" "aitask_rogue.sh:4" "$neg"

# Allowlist suppression, via a synthetic entry.
ACTIVE_ALLOWLIST=(".aitask-scripts/aitask_rogue.sh")
neg_allow="$(scan_dir "$TMP")"
assert_not_contains "an allowlisted file is suppressed" "aitask_rogue.sh" "$neg_allow"
ACTIVE_ALLOWLIST=(${ALLOWLIST[@]+"${ALLOWLIST[@]}"})

# The two allowlists are INDEPENDENT, and that independence is the whole reason
# aitask_note.sh can be exempted from one seam without losing the other. Pin
# both directions with a synthetic entry.
ACTIVE_AIT_GIT_ALLOWLIST=(".aitask-scripts/aitask_ait_git_rogue.sh")
neg_ait_allow="$(scan_dir "$TMP")"
assert_not_contains "an ait-git-allowlisted file is suppressed for THAT seam" \
    "aitask_ait_git_rogue.sh" "$neg_ait_allow"
assert_contains "…and the task_git seam is still guarded everywhere else" \
    "aitask_rogue.sh" "$neg_ait_allow"
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})

# The converse: a file on the ait-git allowlist must still be flagged for an
# unscoped `task_git commit`. This is the claim the header makes about
# aitask_note.sh, so it is asserted rather than asserted-in-prose.
cat > "$TMP/.aitask-scripts/aitask_both_seams.sh" <<'EOF'
#!/usr/bin/env bash
run() {
    task_git commit -m "ait: unscoped on the primary seam"
}
EOF
ACTIVE_AIT_GIT_ALLOWLIST=(".aitask-scripts/aitask_both_seams.sh")
neg_both="$(scan_dir "$TMP")"
assert_contains "an ait-git-allowlisted file is STILL guarded for task_git commit" \
    "aitask_both_seams.sh" "$neg_both"
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})
rm -f "$TMP/.aitask-scripts/aitask_both_seams.sh"

# --- Markdown (instruction-layer) controls -----------------------------------
# Planted in $TMP/md/, a SIBLING of $TMP/.aitask-scripts/. scan_dir's find never
# descends here and md_sources_find never sees the .sh fixtures, so the two
# fixture populations -- and therefore the two violation-count pins -- are
# independent by construction. Fixture basenames are `md_*` so the shell pin's
# `grep -c 'aitask_'` cannot see them.
MDT="$TMP/md"
mkdir -p "$MDT/.claude/skills/foo" "$MDT/.claude/skills/foo-remote-" \
         "$MDT/aidocs" "$MDT/website/content" "$MDT/docs" \
         "$MDT/tests/golden/procs"

# -- positive fixtures (must be flagged) --
cat > "$MDT/.claude/skills/foo/md_fence_unscoped.md" <<'EOF'
Commit it:
```bash
./ait git commit -m "ait: rogue unscoped commit"
```
EOF

cat > "$MDT/.claude/skills/foo/md_inline_unscoped.md" <<'EOF'
- Commit: `./ait git commit -m "ait: rogue unscoped commit"`
EOF

# The `&&` trap: the add is scoped, the commit is not. A line-level judgement
# would let the add's `--` launder the commit.
cat > "$MDT/.claude/skills/foo/md_and_add_scoped.md" <<'EOF'
4. Commit: `./ait git add -- <paths> && ./ait git commit -m "ait: remove t<id>"`
EOF

# A span that WRAPS across prose lines, reported at the line it OPENS on.
printf '%s\n%s\n' \
    'commit it via `./ait git add <plan_file> &&' \
    './ait git commit` (message: `ait: witness`)' \
    > "$MDT/.claude/skills/foo/md_prose_wrapped.md"

# Inside a ```markdown fence the sites are still backticked one-liners.
cat > "$MDT/.claude/skills/foo/md_in_markdown_fence.md" <<'EOF'
```markdown
2. Commit: `./ait git add <task_path> && ./ait git commit -m "ait: notes"`
```
EOF

# The mention rule is PROSE-ONLY: a lone command name on a fence line is a command.
cat > "$MDT/.claude/skills/foo/md_fence_bare_name.md" <<'EOF'
```bash
./ait git commit
```
EOF

# Line-scoped, not block-scoped: a preceding `add` does not scope a later commit.
cat > "$MDT/.claude/skills/foo/md_fence_add_then_commit.md" <<'EOF'
```bash
./ait git add aitasks/
./ait git commit -m "ait: record verification state"
```
EOF

cat > "$MDT/.claude/skills/foo/md_dashes_in_message.md" <<'EOF'
```bash
./ait git commit -m "ait: title -- annotation"
```
EOF

cat > "$MDT/.claude/skills/foo/md_comment_dashes.md" <<'EOF'
```bash
./ait git commit -m "ait: x"   # use -- for a pathspec
```
EOF

cat > "$MDT/.claude/skills/foo/md_no_backticks.md" <<'EOF'
Then run ./ait git commit -m "ait: x" when you are done.
EOF

cat > "$MDT/.claude/skills/foo/md_unbalanced_quote.md" <<'EOF'
```bash
./ait git commit -m "ait: unterminated
```
EOF

cat > "$MDT/.claude/skills/foo/md_template.md.j2" <<'EOF'
```bash
./ait git commit -m "ait: Abort t<N>: revert to {{ profile.abort_revert_status }}"
```
EOF

# -- negative fixtures (must NOT be flagged) --
cat > "$MDT/.claude/skills/foo/md_fence_scoped.md" <<'EOF'
```bash
./ait git commit -m "ait: Update task t42" -- aitasks/t42_foo.md
```
EOF

cat > "$MDT/.claude/skills/foo/md_inline_scoped.md" <<'EOF'
- Commit: `./ait git commit -m "ait: x" -- <task_file>`
EOF

# The converse of the `&&` trap: the segmenter must not over-flag the CORRECT shape.
cat > "$MDT/.claude/skills/foo/md_and_commit_scoped.md" <<'EOF'
4. Commit: `./ait git add <p> && ./ait git commit -m "ait: x" -- <p>`
EOF

# Cure 2 needs no code: the helper line never names `ait git commit` at all.
# Asserted rather than assumed.
cat > "$MDT/.claude/skills/foo/md_helper_routed.md" <<'EOF'
```bash
./.aitask-scripts/aitask_task_commit.sh -m "ait: Add plan for t<id>" aiplans/<plan>
```
EOF

cat > "$MDT/.claude/skills/foo/md_helper_after_add.md" <<'EOF'
- Commit: `rm <p> && ./.aitask-scripts/aitask_task_commit.sh -m "ait: x" <p>`
EOF

# Prose that quotes the bad shape in order to FORBID it -- the shell_conventions.md
# false positive the mention rule exists to clear.
cat > "$MDT/aidocs/md_mention_forbidding.md" <<'EOF'
A `./ait git commit` with no `--` pathspec commits the whole index exactly as
above. There is no separate helper and none is needed.
EOF

# The same, as a plain noun and without the `./` prefix.
cat > "$MDT/aidocs/md_mention_noun.md" <<'EOF'
The qualification is load-bearing: `ait git commit` tags task-data commits
`(tNN)` too, so an unqualified "newest tagged commit" lets a stale one win.
EOF

# `task_git commit` is a bash function with no PATH entry: no markdown
# instruction can ask an agent to run it, so this seam does not match it.
cat > "$MDT/.claude/skills/foo/md_task_git.md" <<'EOF'
```bash
task_git commit -m "ait: not reachable from an instruction"
```
EOF

cat > "$MDT/.claude/skills/foo/md_lookalike.md" <<'EOF'
```bash
portrait git commit -m "ait: a longer identifier ending in ait"
```
EOF

cat > "$MDT/.claude/skills/foo/md_fence_comment.md" <<'EOF'
```bash
# ./ait git commit -m "ait: a commented-out example"
```
EOF

# -- seam 4 fixtures: plain `git commit` (t1762) --
# Named `mdp_*`, which contains no `md_` substring, so the seam-3 pin's
# `grep -c '^[^:]*md_'` cannot see them even if one were ever flagged there.
# Belt and braces: they carry no unscoped `ait git commit` text either, so
# scan_md never emits them at all. Both facts are asserted below.

cat > "$MDT/.claude/skills/foo/mdp_fence_unscoped.md" <<'EOF'
```bash
git add seed/models_x.json
git commit -m "ait: Sync x to seed"
```
EOF

cat > "$MDT/.claude/skills/foo/mdp_inline_unscoped.md" <<'EOF'
- Commit: `git commit -m "chore: bump version"`
EOF

# The `&&` trap for this seam: the add carries `--`, the commit does not.
cat > "$MDT/.claude/skills/foo/mdp_and_add_scoped.md" <<'EOF'
4. Commit: `git add -- <paths> && git commit -m "bug: fix it"`
EOF

cat > "$MDT/.claude/skills/foo/mdp_comment_dashes.md" <<'EOF'
```bash
git commit -m "bug: x"   # remember to use -- for a pathspec
```
EOF

cat > "$MDT/.claude/skills/foo/mdp_add_dash_A.md" <<'EOF'
```bash
git add -A
git commit -m "feature: everything"
```
EOF

# A marker whose reason is EMPTY must not exempt anything.
cat > "$MDT/.claude/skills/foo/mdp_marker_empty_reason.md" <<'EOF'
<!-- unscoped-commit-ok:  -->
```bash
git commit -m "feature: unjustified"
```
EOF

# THE A18/A19 CASE. One marker, two sites: only the first is exempt.
cat > "$MDT/.claude/skills/foo/mdp_marker_next_only.md" <<'EOF'
<!-- unscoped-commit-ok: isolated single-session sandbox, no concurrent writer -->
```bash
git add -A
git commit -m "feature: sandbox commit"
```
Then record the marker:
```bash
git commit -m "ait: Add completion marker"
```
EOF

# -- seam 4 negative fixtures (must NOT be flagged) --
cat > "$MDT/.claude/skills/foo/mdp_fence_scoped.md" <<'EOF'
```bash
git commit -m "ait: Sync x to seed" -- seed/models_x.json
```
EOF

cat > "$MDT/.claude/skills/foo/mdp_inline_scoped.md" <<'EOF'
- Commit: `git commit -m "chore: bump" -- .aitask-scripts/VERSION`
EOF

cat > "$MDT/.claude/skills/foo/mdp_and_commit_scoped.md" <<'EOF'
4. Commit: `git add -- <p> && git commit -m "bug: x" -- <p>`
EOF

# Plumbing: commit-tree writes an object and never touches the index.
cat > "$MDT/.claude/skills/foo/mdp_commit_tree.md" <<'EOF'
```bash
commit_hash=$(echo "msg" | git commit-tree "$tree_hash" -p "$parent_hash")
```
EOF

cat > "$MDT/.claude/skills/foo/mdp_lookalike.md" <<'EOF'
```bash
mygit commit -m "a longer identifier ending in git"
```
EOF

# Prose nouns, per segment: the shape that actually occurs in aidocs.
cat > "$MDT/aidocs/mdp_mention_noun.md" <<'EOF'
Do NOT run `git add`, `git commit`, or `git diff` on files inside `aitasks/`.
Only the runner runs `git add -A && git commit && git push`; agents never touch git.
EOF

# The other two seams' commands must NOT be reported here: one command, one seam.
cat > "$MDT/.claude/skills/foo/mdp_other_seams.md" <<'EOF'
```bash
./ait git commit -m "ait: x" -- aitasks/t1_x.md
task_git commit -m "ait: y" -- aitasks/t1_y.md
```
EOF

# Unformatted English prose using the words as a noun phrase. Real shapes from
# this tree: none of these instruct anything, and all five would be flagged by a
# fail-closed rule.
cat > "$MDT/aidocs/mdp_unformatted_prose.md" <<'EOF'
The tuple was written but the path-scoped git commit failed (e.g. an index lock).
The AgentCrew runner already handles git commit + push for crew files.
aitask_archive.sh handles all archival mechanics (lock release, git commit).
EOF

# ...but an unformatted INVOCATION is still a command, and is still flagged.
cat > "$MDT/aidocs/mdp_unformatted_invocation.md" <<'EOF'
When you are done just run git commit -m "chore: done" and move on.
EOF

# The heredoc shapes. `-F -` puts the pathspec on the command line itself; the
# `-m "$(cat <<'EOF' …)" -- <p>` form puts it on the heredoc's CLOSING line, which
# the scanner never joins to the command -- so that form stays flagged even
# though git accepts it, and the instruction layer is written with `-F -`. The
# outer delimiter is OUTER because each fixture body contains its own EOF.
cat > "$MDT/.claude/skills/foo/mdp_heredoc_F_scoped.md" <<'OUTER'
```bash
git commit -F - -- src/a.sh src/b.sh <<'EOF'
bug: Fix it (t1)

Co-Authored-By: x <x@x>
EOF
```
OUTER

cat > "$MDT/.claude/skills/foo/mdp_heredoc_m_pathspec_after.md" <<'OUTER'
```bash
git commit -m "$(cat <<'EOF'
bug: Fix it (t1)
EOF
)" -- src/a.sh
```
OUTER

# A doc that SHOWS the marker format with a `<reason>` placeholder must not
# itself register as a marker: the reason class excludes `>`, so the placeholder
# never parses. skill_authoring_conventions.md relies on this.
cat > "$MDT/aidocs/mdp_marker_documented.md" <<'EOF'
Put `<!-- unscoped-commit-ok: <reason> -->` on the line before such a command.
```bash
git commit -m "feature: must still be flagged"
```
EOF

# A well-formed marker immediately above its fenced command.
cat > "$MDT/.claude/skills/foo/mdp_marker_ok.md" <<'EOF'
<!-- unscoped-commit-ok: merge commit; git refuses a partial commit during a merge -->
```bash
git commit -m "feature: merge t<id>"
```
EOF

# -- enumerator fixtures (must not be ENUMERATED at all) --
# Each carries a real violation, so a predicate that admitted one would move the
# count pin below rather than pass quietly.
for out_of_scope in \
    "website/content/md_out_website.md" \
    "docs/md_out_docs.md" \
    "tests/golden/procs/md_out_golden.md" \
    ".claude/skills/foo-remote-/md_out_rendered.md" \
; do
    printf '%s\n' '- Commit: `./ait git commit -m "ait: x"`' > "$MDT/$out_of_scope"
done
printf '%s\n' '- Commit: `./ait git commit -m "ait: x"`' > "$MDT/README.md"
printf '%s\n' '- Commit: `./ait git commit -m "ait: x"`' > "$MDT/.claude/skills/foo/md_out_ext.txt"

mapfile -t MD_FIXTURES < <(md_sources_find "$MDT")
md_fixture_list="$(printf '%s\n' ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"

assert_contains "markdown enum: a skill source IS enumerated" \
    ".claude/skills/foo/md_fence_unscoped.md" "$md_fixture_list"
assert_contains "markdown enum: an aidocs file IS enumerated" \
    "aidocs/md_mention_forbidding.md" "$md_fixture_list"
assert_not_contains "markdown enum: website/ is NOT enumerated" \
    "md_out_website.md" "$md_fixture_list"
assert_not_contains "markdown enum: docs/ is NOT enumerated" \
    "md_out_docs.md" "$md_fixture_list"
assert_not_contains "markdown enum: README.md is NOT enumerated" \
    "README.md" "$md_fixture_list"
assert_not_contains "markdown enum: a golden snapshot is NOT enumerated" \
    "md_out_golden.md" "$md_fixture_list"
assert_not_contains "markdown enum: a rendered per-profile dir is NOT enumerated" \
    "md_out_rendered.md" "$md_fixture_list"
assert_not_contains "markdown enum: a non-md/j2 extension is NOT enumerated" \
    "md_out_ext.txt" "$md_fixture_list"

# The predicate directly, so a lister bug and a predicate bug stay distinguishable.
assert_exit_zero "md_in_scope: allows a skill source" \
    md_in_scope ".claude/skills/foo/SKILL.md"
assert_exit_zero "md_in_scope: allows a named root instruction file" \
    md_in_scope "CLAUDE.md"
assert_exit_nonzero "md_in_scope: denies website/ by default-deny" \
    md_in_scope "website/content/docs/x.md"
assert_exit_nonzero "md_in_scope: denies an unlisted root by default-deny" \
    md_in_scope "some/new/tree/x.md"

neg_md="$(cd "$MDT" && scan_md ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"

assert_contains "markdown: an unscoped command in a bash fence IS flagged" \
    "md_fence_unscoped.md" "$neg_md"
assert_contains "markdown: an unscoped command in a backtick span IS flagged" \
    "md_inline_unscoped.md" "$neg_md"
assert_contains "markdown: a scoped add joined to an unscoped commit IS flagged" \
    "md_and_add_scoped.md" "$neg_md"
assert_contains "markdown: a span wrapping across prose lines IS flagged" \
    "md_prose_wrapped.md" "$neg_md"
assert_contains "markdown: a site inside a non-bash fence IS flagged" \
    "md_in_markdown_fence.md" "$neg_md"
assert_contains "markdown: a bare command name INSIDE a fence IS flagged" \
    "md_fence_bare_name.md" "$neg_md"
assert_contains "markdown: a preceding add does not scope a later commit" \
    "md_fence_add_then_commit.md" "$neg_md"
assert_contains "markdown: a -- inside the message is NOT a pathspec" \
    "md_dashes_in_message.md" "$neg_md"
assert_contains "markdown: a -- in a trailing comment is NOT a pathspec" \
    "md_comment_dashes.md" "$neg_md"
assert_contains "markdown: a command written with no backticks IS flagged" \
    "md_no_backticks.md" "$neg_md"
assert_contains "markdown: unparseable quoting fails CLOSED" \
    "md_unbalanced_quote.md" "$neg_md"
assert_contains "markdown: a .md.j2 template is scanned too" \
    "md_template.md.j2" "$neg_md"

assert_not_contains "markdown: a fenced commit carrying -- is NOT flagged" \
    "md_fence_scoped.md" "$neg_md"
assert_not_contains "markdown: an inline commit carrying -- is NOT flagged" \
    "md_inline_scoped.md" "$neg_md"
assert_not_contains "markdown: an add joined to a SCOPED commit is NOT flagged" \
    "md_and_commit_scoped.md" "$neg_md"
assert_not_contains "markdown: a helper-routed commit is NOT flagged" \
    "md_helper_routed.md" "$neg_md"
assert_not_contains "markdown: a helper-routed commit after && is NOT flagged" \
    "md_helper_after_add.md" "$neg_md"
assert_not_contains "markdown: prose forbidding the bad shape is NOT flagged" \
    "md_mention_forbidding.md" "$neg_md"
assert_not_contains "markdown: a bare noun mention is NOT flagged" \
    "md_mention_noun.md" "$neg_md"
assert_not_contains "markdown: task_git commit is NOT matched in markdown" \
    "md_task_git.md" "$neg_md"
assert_not_contains "markdown: a longer identifier ending in 'ait' is NOT flagged" \
    "md_lookalike.md" "$neg_md"
assert_not_contains "markdown: a commented-out fence line is NOT flagged" \
    "md_fence_comment.md" "$neg_md"

# Exactly twelve violations across the markdown fixtures. Deliberately a SECOND
# pin rather than a widening of the shell one: the two fixture trees live under
# different roots, are produced by different scanners, and are named `md_*` vs
# `aitask_*`, so neither can drift when the other gains a fixture. An
# out-of-scope fixture that started being enumerated would land here.
neg_md_count="$(printf '%s\n' "$neg_md" | grep -c '^[^:]*md_' || true)"
assert_eq "markdown: exactly twelve violations across the fixture tree" \
    "12" "$neg_md_count"

# The reported location is the line the LOGICAL line starts on -- for a span
# that wraps, the line it OPENS on, not the one carrying the `commit`.
assert_contains "markdown: a wrapped span is reported at its opening line" \
    "md_prose_wrapped.md:1" "$neg_md"

# -- seam 4 assertions (t1762) --
neg_mdp_raw="$(cd "$MDT" && scan_md_plain ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"
neg_mdp="$(printf '%s\n' "$neg_mdp_raw" | sed -n 's/^V://p')"
neg_mdp_exc="$(printf '%s\n' "$neg_mdp_raw" | sed -n 's/^X://p')"

assert_contains "plain: an unscoped commit in a bash fence IS flagged" \
    "mdp_fence_unscoped.md" "$neg_mdp"
assert_contains "plain: an unscoped commit in a backtick span IS flagged" \
    "mdp_inline_unscoped.md" "$neg_mdp"
assert_contains "plain: a scoped add joined to an unscoped commit IS flagged" \
    "mdp_and_add_scoped.md" "$neg_mdp"
assert_contains "plain: a -- in a trailing comment is NOT a pathspec" \
    "mdp_comment_dashes.md" "$neg_mdp"
assert_contains "plain: 'git add -A' then a bare commit IS flagged" \
    "mdp_add_dash_A.md" "$neg_mdp"
assert_contains "plain: a marker with an EMPTY reason exempts nothing" \
    "mdp_marker_empty_reason.md" "$neg_mdp"
assert_contains "plain: an UNFORMATTED invocation (git commit -m …) IS flagged" \
    "mdp_unformatted_invocation.md" "$neg_mdp"

assert_not_contains "plain: unformatted English prose is NOT flagged" \
    "mdp_unformatted_prose.md" "$neg_mdp"

assert_not_contains "plain: a fenced commit carrying -- is NOT flagged" \
    "mdp_fence_scoped.md" "$neg_mdp"
assert_not_contains "plain: an inline commit carrying -- is NOT flagged" \
    "mdp_inline_scoped.md" "$neg_mdp"
assert_not_contains "plain: an add joined to a SCOPED commit is NOT flagged" \
    "mdp_and_commit_scoped.md" "$neg_mdp"
assert_not_contains "plain: git commit-tree plumbing is NOT flagged" \
    "mdp_commit_tree.md" "$neg_mdp"
assert_not_contains "plain: a longer identifier ending in 'git' is NOT flagged" \
    "mdp_lookalike.md" "$neg_mdp"
assert_not_contains "plain: bare-name prose mentions are NOT flagged" \
    "mdp_mention_noun.md" "$neg_mdp"
assert_not_contains "plain: the other two seams' commands are NOT re-reported" \
    "mdp_other_seams.md" "$neg_mdp"
assert_not_contains "plain: a well-formed marker exempts its command" \
    "mdp_marker_ok.md" "$neg_mdp"

# The honoured exception is REPORTED, with its reason -- an exception nobody can
# see is an allowlist entry with extra steps.
assert_contains "plain: an honoured exception is reported with its reason" \
    "merge commit; git refuses a partial commit during a merge" "$neg_mdp_exc"

# THE MARKER-INDEPENDENCE ASSERTION. One marker, two sites in one file: the
# first is exempt, the second is still flagged. This is the A18/A19 case, and it
# is why the exception is line-scoped rather than a file allowlist entry.
mdp_next_v="$(printf '%s\n' "$neg_mdp" | grep -c 'mdp_marker_next_only\.md' || true)"
mdp_next_x="$(printf '%s\n' "$neg_mdp_exc" | grep -c 'mdp_marker_next_only\.md' || true)"
assert_eq "plain: a marker exempts exactly ONE site in a two-site file" \
    "1" "$mdp_next_x"
assert_eq "plain: the SECOND site in that file is still flagged" \
    "1" "$mdp_next_v"

assert_not_contains "plain: a -F - heredoc commit with its pathspec is NOT flagged" \
    "mdp_heredoc_F_scoped.md" "$neg_mdp"
assert_contains "plain: a -m cat-heredoc commit with the pathspec after it IS flagged" \
    "mdp_heredoc_m_pathspec_after.md" "$neg_mdp"
assert_contains "plain: a doc SHOWING the marker format does not exempt a real site" \
    "mdp_marker_documented.md" "$neg_mdp"
# ...and directly: the `<reason>` placeholder form never parses as a marker.
mdp_doc_markers="$(md_exception_lines "$MDT/aidocs/mdp_marker_documented.md")"
assert_eq "plain: a <reason> placeholder never parses as a marker" \
    "" "$mdp_doc_markers"

# Exactly ten violations across the seam-4 fixtures. A fourth, independent pin.
# Ten includes mdp_marker_next_only.md's SECOND (unmarked) site, which is the
# whole point of that fixture, and the two heredoc/documented-marker positives.
neg_mdp_count="$(printf '%s\n' "$neg_mdp" | grep -c '^[^:]*mdp_' || true)"
assert_eq "plain: exactly ten violations across the seam-4 fixture tree" \
    "10" "$neg_mdp_count"

# The two markdown seams never DOUBLE-REPORT a site. This is stated as the real
# invariant -- no <file>:<line> in both outputs -- rather than "no md_ fixture
# ever reaches the plain seam", which would be wrong: md_lookalike.md's
# `portrait git commit` is a seam-3 NEGATIVE (not reported there) and a genuine
# plain `git commit` token sequence for seam 4, and reporting it once is correct.
md_sites="$(printf '%s\n' "$neg_md" | cut -d: -f1,2 | sort -u)"
mdp_sites="$(printf '%s\n' "$neg_mdp" | cut -d: -f1,2 | sort -u)"
double_reported="$(comm -12 <(printf '%s\n' "$md_sites") <(printf '%s\n' "$mdp_sites") | grep -v '^$' || true)"
assert_eq "seam separation: no site is reported by BOTH markdown seams" \
    "" "$double_reported"
# And specifically the unparseable-quote case, where both seams fail closed:
assert_not_contains "seam separation: an unparseable ./ait git line is seam 3's alone" \
    "md_unbalanced_quote.md" "$neg_mdp"
assert_not_contains "seam separation: no mdp_ fixture is reported by scan_md" \
    "mdp_" "$neg_md"

# MD_PLAIN_ALLOWLIST suppression, and its independence from the other three.
ACTIVE_MD_PLAIN_ALLOWLIST=(".claude/skills/foo/mdp_fence_unscoped.md")
neg_mdp_allow="$(cd "$MDT" && scan_md_plain ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"
assert_not_contains "plain: an allowlisted file is suppressed" \
    "mdp_fence_unscoped.md" "$neg_mdp_allow"
ACTIVE_MD_PLAIN_ALLOWLIST=(${MD_PLAIN_ALLOWLIST[@]+"${MD_PLAIN_ALLOWLIST[@]}"})

ACTIVE_MD_PLAIN_ALLOWLIST=(".claude/skills/foo/md_fence_unscoped.md")
neg_mdp_cross2="$(cd "$MDT" && scan_md ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"
assert_contains "a plain-allowlisted name does NOT suppress the ait-git seam" \
    "md_fence_unscoped.md" "$neg_mdp_cross2"
ACTIVE_MD_PLAIN_ALLOWLIST=(${MD_PLAIN_ALLOWLIST[@]+"${MD_PLAIN_ALLOWLIST[@]}"})

# MD_ALLOWLIST suppression, via a synthetic entry.
ACTIVE_MD_ALLOWLIST=(".claude/skills/foo/md_fence_unscoped.md")
neg_md_allow="$(cd "$MDT" && scan_md ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"
assert_not_contains "markdown: an allowlisted file is suppressed" \
    "md_fence_unscoped.md" "$neg_md_allow"
ACTIVE_MD_ALLOWLIST=(${MD_ALLOWLIST[@]+"${MD_ALLOWLIST[@]}"})

# The three allowlists are INDEPENDENT. An MD_ALLOWLIST entry must not suppress
# either shell seam, and the shell allowlists must not suppress the markdown one.
ACTIVE_MD_ALLOWLIST=(".aitask-scripts/aitask_rogue.sh")
neg_md_cross="$(scan_dir "$TMP")"
assert_contains "an md-allowlisted name does NOT suppress the task_git seam" \
    "aitask_rogue.sh" "$neg_md_cross"
ACTIVE_MD_ALLOWLIST=(${MD_ALLOWLIST[@]+"${MD_ALLOWLIST[@]}"})

ACTIVE_AIT_GIT_ALLOWLIST=(".claude/skills/foo/md_fence_unscoped.md")
neg_md_cross2="$(cd "$MDT" && scan_md ${MD_FIXTURES[@]+"${MD_FIXTURES[@]}"})"
assert_contains "an ait-git-allowlisted name does NOT suppress the markdown seam" \
    "md_fence_unscoped.md" "$neg_md_cross2"
ACTIVE_AIT_GIT_ALLOWLIST=(${AIT_GIT_ALLOWLIST[@]+"${AIT_GIT_ALLOWLIST[@]}"})

echo
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
