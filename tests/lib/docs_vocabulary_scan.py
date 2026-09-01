#!/usr/bin/env python3
"""Drift scanner for the two hand-maintained vocabularies that document the
task frontmatter (t1666).

Two independent checks, each anchored on a real single source of truth:

  issue_type   Source: <root>/aitasks/metadata/task_types.txt. Every site that
               *enumerates* the vocabulary is listed in SITES below with the
               exact set it is expected to carry.

  field table  Source: the framework's frontmatter *writers*. Every field a
               writer can emit must have a row in the website's Frontmatter
               Fields table, and vice versa.

WHY THE WRITERS AND NOT THE CORPUS. Deriving the field set from the on-disk
task corpus fails open: a field that exists in code but has not yet been
written to any task file has zero instances, so a corpus-derived check stays
green while the table is already wrong. That is not hypothetical -- when this
scanner was written, `attachments` (written by `ait attach add`) had zero
instances on disk and no row in the table. The corpus is still scanned, but
only as a *supplemental* check: a key on disk that no known writer emits is its
own diagnostic, not a substitute for the writer set.

WHAT THIS DOES NOT BUY. A field is visible here only once a *writer* the
WRITERS table knows about can emit it. A brand-new script that writes
frontmatter directly, or a new caller of frontmatter_patch.py, is invisible --
so PATCH_CALLERS is asserted to be exactly the set of callers that exist, which
turns "someone added a new nested-field writer" into a failure rather than a
silent gap. For a genuinely new field, the checklist in
aidocs/framework/aitasks_extension_points.md remains the mechanism.

Usage:
    docs_vocabulary_scan.py --root <dir>          run the checks
    docs_vocabulary_scan.py --root <dir> --list-inputs
                                                  print every path read,
                                                  one per line, relative to
                                                  root (used to build test
                                                  fixtures)

Exit 0 when every check passes, 1 when any check fails, 2 on usage error.
"""

import argparse
import os
import re
import sys

# --------------------------------------------------------------------------
# issue_type sites
#
# Each row: (path, anchor, shape, expected-class).
#
#   anchor  a literal substring identifying the line the enumeration lives on
#           (or, for `fenced_lines`, the heading above the fenced block). It
#           MUST match exactly one line in the file -- see the anchor tripwire
#           in check_sites(). A renamed heading is then a loud failure rather
#           than a check that silently stops checking anything.
#
#   shape   how to carve the enumeration out of that line. Extraction is
#           deliberately narrow: only the enumeration itself is compared, never
#           the surrounding prose. Every NO_MV site has to *explain* why
#           manual_verification is absent, so the rationale sentence contains
#           the very token the site must not enumerate -- a check that searched
#           the whole line or paragraph would fail a correct document.
#
#   class   FULL      every value in task_types.txt
#           NO_MV     FULL minus manual_verification
#           DETECTED  the set aitask_issue_import.sh can actually infer
# --------------------------------------------------------------------------

CLASS_FULL = "FULL"
CLASS_NO_MV = "NO_MV"
CLASS_DETECTED = "DETECTED"

# Values excluded from a class, with the reason recorded here rather than in a
# commit message. Both are deliberate, not drift.
NO_MV_EXCLUDES = {
    # There is no `manual_verification:` commit type and no wrap that produces
    # one: a manual-verification task records its outcome with `ait:`, and any
    # code change a failed check triggers lands on a spawned follow-up under
    # that follow-up's own type.
    "manual_verification",
}
DETECTED_EXCLUDES = NO_MV_EXCLUDES | {
    # github_detect_type() in aitask_issue_import.sh maps issue labels to
    # bug/refactor/test/style/chore/documentation/performance and otherwise
    # falls back to `feature`. It can never emit `enhancement`.
    "enhancement",
}

_WF = ".claude/skills/task-workflow"

SITES = [
    # -- the canonical reference -------------------------------------------
    ("website/content/docs/development/task-format.md",
     "| `issue_type` |", "table_cell", CLASS_FULL),
    ("website/content/docs/development/task-format.md",
     "## Customizing Task Types", "fenced_lines", CLASS_FULL),

    # -- other website pages ------------------------------------------------
    ("website/content/docs/commands/task-management.md",
     "4. **Issue type**", "plain_paren", CLASS_FULL),
    ("website/content/docs/tuis/board/how-to.md",
     "- **Type:** Loaded from", "plain_paren", CLASS_FULL),
    ("website/content/docs/tuis/board/reference.md",
     "| `issue_type` | string |", "plain_paren", CLASS_FULL),
    ("website/content/docs/workflows/issue-tracker.md",
     "auto-detected from labels", "plain_paren", CLASS_DETECTED),

    # -- agent instructions: one hand-maintained file, three generated
    #    mirrors. The mirrors are regenerated from the seed by `ait setup`;
    #    listing them here catches a seed edit that was never propagated.
    ("CLAUDE.md", "issue_type: bug|", "pipe", CLASS_FULL),
    ("CLAUDE.md", "Types match `issue_type` values:", "backtick_list", CLASS_NO_MV),
    ("seed/aitasks_agent_instructions.seed.md",
     "issue_type: bug|", "pipe", CLASS_FULL),
    ("seed/aitasks_agent_instructions.seed.md",
     "Types match `issue_type` values:", "backtick_list", CLASS_NO_MV),
    ("AGENTS.md", "issue_type: bug|", "pipe", CLASS_FULL),
    ("AGENTS.md", "Types match `issue_type` values:", "backtick_list", CLASS_NO_MV),
    (".codex/instructions.md", "issue_type: bug|", "pipe", CLASS_FULL),
    (".codex/instructions.md",
     "Types match `issue_type` values:", "backtick_list", CLASS_NO_MV),
    (".opencode/instructions.md", "issue_type: bug|", "pipe", CLASS_FULL),
    (".opencode/instructions.md",
     "Types match `issue_type` values:", "backtick_list", CLASS_NO_MV),

    # -- runtime help --------------------------------------------------------
    (".aitask-scripts/aitask_ls.sh",
     "    issue_type: bug|", "pipe_wrapped", CLASS_FULL),

    # -- skill sources -------------------------------------------------------
    (_WF + "/SKILL.md",
     "- **Code commits** MUST use", "backtick_list", CLASS_NO_MV),
    (_WF + "/task-creation-batch.md",
     "| `issue_type` | yes |", "table_cell", CLASS_FULL),
    (".claude/skills/aitask-wrap/SKILL.md.j2",
     "3. **Suggested issue_type**", "backtick_list", CLASS_NO_MV),
    (".claude/skills/aitask-docs-gap/SKILL.md",
     "- `ISSUE_TYPE:`", "plain_paren", CLASS_FULL),
    (".claude/skills/aitask-changelog/SKILL.md",
     "- `ISSUE_TYPE:`", "plain_paren", CLASS_FULL),
]

# The rendered `-remote-` closures are committed (unlike the `-default-` /
# `-fast-` ones, which .gitignore excludes), so they ship to users and can go
# stale if a source edit is not followed by `aitask_skill_rerender.sh remote`.
# Listing them here makes a missed rerender a failing test.
for _tree in (".claude/skills/task-workflow-remote-",
              ".agents/skills/task-workflow-remote-codex-",
              ".opencode/skills/task-workflow-remote-"):
    SITES.append((_tree + "/SKILL.md",
                  "- **Code commits** MUST use", "backtick_list", CLASS_NO_MV))
    SITES.append((_tree + "/task-creation-batch.md",
                  "| `issue_type` | yes |", "table_cell", CLASS_FULL))

# --------------------------------------------------------------------------
# Frontmatter field writers
# --------------------------------------------------------------------------

# Scripts that emit `echo "<field>: ..."` lines when rewriting frontmatter.
ECHO_WRITERS = [
    ".aitask-scripts/aitask_update.sh",
    ".aitask-scripts/aitask_create.sh",
]

# Keys `aitask_create.sh` writes into the `aitasks/new/` draft envelope. They
# never reach a real task file, so they are not frontmatter fields and must not
# be expected in the table.
DRAFT_ONLY_KEYS = {
    "draft",   # marks the file as an unclaimed draft
    "parent",  # the draft's future parent, consumed at finalize time
}

# Writers that do not use the `echo "<field>: "` shape.
OTHER_WRITERS = {
    "completed_at": ".aitask-scripts/aitask_archive.sh",
}

# Callers of frontmatter_patch.py, which writes the nested mapping fields.
# Asserted to be exactly this set: a new caller means a new nested field this
# scanner would otherwise never see.
PATCH_CALLERS = {
    ".aitask-scripts/aitask_artifact.sh",   # artifacts
    ".aitask-scripts/aitask_attach.sh",     # attachments
    ".aitask-scripts/aitask_fold_mark.sh",  # unions both across a fold
}

FIELD_TABLE = "website/content/docs/development/task-format.md"
TASK_TYPES = "aitasks/metadata/task_types.txt"
SEED_TASK_TYPES = "seed/task_types.txt"


# --------------------------------------------------------------------------
# Extraction
# --------------------------------------------------------------------------

class ExtractError(Exception):
    pass


def _split_clean(raw, sep):
    out = set()
    for piece in raw.split(sep):
        piece = piece.strip().strip("`").strip().rstrip(".")
        if piece.startswith("or "):
            piece = piece[3:].strip().strip("`")
        # A list may be introduced in-place ("defaults: bug, chore, ...").
        piece = re.sub(r"^[A-Za-z][A-Za-z ]*:\s*", "", piece).strip().strip("`")
        if re.fullmatch(r"[a-z_]+", piece or ""):
            out.add(piece)
    return out


def _join_wrapped(lines, idx):
    """Join an enumeration that is line-wrapped. A wrapped list leaves its
    continuation on the next line, so the break always falls after a comma."""
    raw = lines[idx]
    j = idx
    while raw.rstrip().endswith(",") and j + 1 < len(lines):
        j += 1
        raw += " " + lines[j].strip()
    return raw


def extract(shape, lines, idx):
    """Carve the enumeration out of the anchored line. Never looks at prose
    outside the enumeration itself."""
    line = lines[idx]

    if shape == "pipe":
        raw = line.split("issue_type:", 1)[1]
        return _split_clean(raw, "|")

    if shape == "pipe_wrapped":
        # A help block whose pipe list wraps: continuation lines follow a
        # trailing `|`.
        raw = line.split("issue_type:", 1)[1]
        j = idx
        while raw.rstrip().endswith("|") and j + 1 < len(lines):
            j += 1
            raw += lines[j]
        return _split_clean(raw, "|")

    if shape == "table_cell":
        cells = [c for c in line.split("|")]
        # cells[0] is the empty string before the leading pipe; the values cell
        # is the first one after the field-name cell that holds a backticked
        # list.
        for cell in cells[2:]:
            got = _split_clean(cell, ",")
            if len(got) >= 3:
                return got
        raise ExtractError("no values cell found in table row")

    if shape == "backtick_list":
        # The maximal run of `word`-shaped items separated by commas. Anything
        # after the run -- including a sentence explaining an exclusion -- is
        # invisible to this extraction. The list may be line-wrapped.
        joined = _join_wrapped(lines, idx)
        best = set()
        for m in re.finditer(r"`[a-z_]+`(?:\s*,\s*(?:or\s+)?`[a-z_]+`)+", joined):
            got = _split_clean(m.group(0), ",")
            if len(got) > len(best):
                best = got
        if not best:
            raise ExtractError("no backticked enumeration found")
        return best

    if shape == "plain_paren":
        best = set()
        for m in re.finditer(r"\(([^()]*)\)", line):
            got = _split_clean(m.group(1), ",")
            if len(got) > len(best):
                best = got
        if not best:
            raise ExtractError("no parenthesised enumeration found")
        return best

    if shape == "fenced_lines":
        j = idx
        while j < len(lines) and not lines[j].startswith("```"):
            j += 1
        if j >= len(lines):
            raise ExtractError("no fenced block after anchor")
        out = set()
        j += 1
        while j < len(lines) and not lines[j].startswith("```"):
            v = lines[j].strip()
            if re.fullmatch(r"[a-z_]+", v or ""):
                out.add(v)
            j += 1
        if not out:
            raise ExtractError("fenced block held no values")
        return out

    raise ExtractError("unknown shape %r" % shape)


# --------------------------------------------------------------------------
# Checks
# --------------------------------------------------------------------------

def read(root, rel):
    with open(os.path.join(root, rel), encoding="utf-8") as fh:
        return fh.read()


def expected_for(cls, full):
    if cls == CLASS_FULL:
        return set(full)
    if cls == CLASS_NO_MV:
        return set(full) - NO_MV_EXCLUDES
    if cls == CLASS_DETECTED:
        return set(full) - DETECTED_EXCLUDES
    raise ExtractError("unknown class %r" % cls)


def check_vocabulary_sync(root, failures):
    live = [l.strip() for l in read(root, TASK_TYPES).split("\n") if l.strip()]
    seed = [l.strip() for l in read(root, SEED_TASK_TYPES).split("\n") if l.strip()]
    if set(live) != set(seed):
        failures.append(
            "A/vocabulary-sync: %s and %s disagree (only-in-live=%s only-in-seed=%s)"
            % (TASK_TYPES, SEED_TASK_TYPES,
               sorted(set(live) - set(seed)), sorted(set(seed) - set(live))))
    return live


def check_sites(root, full, failures):
    for rel, anchor, shape, cls in SITES:
        path = os.path.join(root, rel)
        if not os.path.exists(path):
            failures.append("C/anchor: %s: file missing" % rel)
            continue
        lines = read(root, rel).split("\n")
        hits = [i for i, l in enumerate(lines) if anchor in l]
        # Anchor tripwire: without this, a renamed heading or reworded line
        # silently reduces the site to checking nothing.
        if len(hits) != 1:
            failures.append(
                "C/anchor: %s: anchor %r matched %d lines, expected exactly 1"
                % (rel, anchor, len(hits)))
            continue
        try:
            got = extract(shape, lines, hits[0])
        except ExtractError as exc:
            failures.append("C/extract: %s: %s" % (rel, exc))
            continue
        if not got:
            failures.append("C/extract: %s: extraction produced no values" % rel)
            continue
        want = expected_for(cls, full)
        if got != want:
            failures.append(
                "B/site: %s [%s]: missing=%s unexpected=%s"
                % (rel, cls, sorted(want - got), sorted(got - want)))


def writer_fields(root, failures):
    fields = set()
    for rel in ECHO_WRITERS:
        found = set(re.findall(r'echo "([a-z_]+): ', read(root, rel)))
        if not found:
            failures.append("D/writers: %s emitted no field names -- "
                            "the writer shape changed" % rel)
        fields |= found
    for field, rel in OTHER_WRITERS.items():
        if not os.path.exists(os.path.join(root, rel)):
            failures.append("D/writers: %s missing (writes %s)" % (rel, field))
            continue
        if field not in read(root, rel):
            failures.append("D/writers: %s no longer writes %s" % (rel, field))
        fields.add(field)

    # Nested fields, via the frontmatter_patch.py callers.
    callers = set()
    patch_fields = set()
    for dirpath, dirnames, filenames in os.walk(os.path.join(root, ".aitask-scripts")):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in filenames:
            if not fn.endswith((".sh", ".py")):
                continue
            abspath = os.path.join(dirpath, fn)
            rel = os.path.relpath(abspath, root)
            if rel.endswith("lib/frontmatter_patch.py"):
                continue
            try:
                with open(abspath, encoding="utf-8", errors="replace") as fh:
                    body = fh.read()
            except OSError:
                continue
            # An actual invocation, not a passing mention in a comment.
            if not re.search(r"frontmatter_patch\.py\"?\s+(append|remove|set)\b", body):
                continue
            callers.add(rel)
            patch_fields |= set(re.findall(
                r'frontmatter_patch\.py"?\s+\S+\s+"?\$\w+"?\s+([a-z_]+)', body))
    if callers != PATCH_CALLERS:
        failures.append(
            "D/patch-callers: the set of frontmatter_patch.py callers changed "
            "(new=%s gone=%s) -- a new caller may write a nested field this "
            "scan cannot see; add it to PATCH_CALLERS after checking"
            % (sorted(callers - PATCH_CALLERS), sorted(PATCH_CALLERS - callers)))
    fields |= patch_fields

    return fields - DRAFT_ONLY_KEYS


def table_rows(root):
    return set(re.findall(r"^\| `([a-z_]+)`", read(root, FIELD_TABLE), re.M))


def check_field_coverage(root, failures):
    writers = writer_fields(root, failures)
    rows = table_rows(root)
    if writers - rows:
        failures.append(
            "D/field-coverage: writable but undocumented in %s: %s"
            % (FIELD_TABLE, sorted(writers - rows)))
    if rows - writers:
        failures.append(
            "D/field-coverage: documented in %s but no known writer: %s"
            % (FIELD_TABLE, sorted(rows - writers)))
    return writers


def check_corpus_supplemental(root, writers, failures):
    """Supplemental only: a key on disk no known writer emits is its own
    diagnostic (a hand-edited or retired field), never a substitute for the
    writer-derived set above."""
    tasks_dir = os.path.join(root, "aitasks")
    if not os.path.isdir(tasks_dir):
        return
    keys = set()
    for dirpath, dirnames, filenames in os.walk(tasks_dir):
        dirnames[:] = [d for d in dirnames if d not in ("metadata", "new")]
        for fn in filenames:
            if not fn.endswith(".md"):
                continue
            try:
                with open(os.path.join(dirpath, fn), encoding="utf-8",
                          errors="replace") as fh:
                    txt = fh.read()
            except OSError:
                continue
            if not txt.startswith("---\n"):
                continue
            end = txt.find("\n---", 4)
            if end < 0:
                continue
            for line in txt[4:end].split("\n"):
                m = re.match(r"^([a-z_]+):", line)
                if m:
                    keys.add(m.group(1))
    unknown = keys - writers - DRAFT_ONLY_KEYS
    if unknown:
        failures.append(
            "E/corpus: task files carry frontmatter keys no known writer emits: "
            "%s (hand-edited, or a retired field)" % sorted(unknown))


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    ap.add_argument("--list-inputs", action="store_true")
    args = ap.parse_args(argv)

    root = os.path.abspath(args.root)

    if args.list_inputs:
        inputs = {TASK_TYPES, SEED_TASK_TYPES, FIELD_TABLE}
        inputs |= {rel for rel, _a, _s, _c in SITES}
        inputs |= set(ECHO_WRITERS)
        inputs |= set(OTHER_WRITERS.values())
        inputs |= PATCH_CALLERS
        for rel in sorted(inputs):
            print(rel)
        return 0

    failures = []
    full = check_vocabulary_sync(root, failures)
    check_sites(root, full, failures)
    writers = check_field_coverage(root, failures)
    check_corpus_supplemental(root, writers, failures)

    for f in failures:
        print("FAIL " + f)
    if not failures:
        print("OK %d issue_type sites, %d writable fields"
              % (len(SITES), len(writers)))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
