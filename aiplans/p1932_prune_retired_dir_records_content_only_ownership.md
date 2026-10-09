---
Task: t1932_prune_retired_dir_records_content_only_ownership.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1932 — Make retired-DIR ownership path-aware in the retired-skills pruner

## Context

`.aitask-scripts/aitask_prune_retired_skills.sh` decides whether a retired
directory is framework-owned by checking only that every file's
`git hash-object` is in the manifest's **flat** SHA set (lines 160-194). It never
checks that the file's **path** was ever shipped. So a user file that is a
byte-for-byte copy of any shipped blob (e.g. `my_notes.md` copied from
`SKILL.md`) counts as "known", and the whole directory — user file included — is
deleted. t1926 reproduced this and sidestepped it for the scripts manifest with
FILE records only; `retired_skills_manifest.txt` still has six DIR records, so
the hole is live there.

Goal: a file inside a retired DIR counts as known only when that exact
(destination path, blob) pair was shipped — preserving the source agent root's
identity — while the untracked staging copies under
`aitasks/metadata/{codex,opencode}_skills/` keep pruning.

## Design

Ownership keys keep the **full shipped path** (agent root included). History
proves the roots differ: `.claude/skills/aitask-pickn` shipped `SKILL.md` and
`SKILL.md.j2`, while `.agents/skills/aitask-pickn` and
`.opencode/skills/aitask-pickn` only ever shipped `SKILL.md`. Normalising the
root away would accept a copied Claude `SKILL.md.j2` under `.agents/…`, a
destination that never shipped.

Manifest records (tab-separated):

```
DIRSHA	<shipped path, verbatim from git>	<blob>
DIR	<path>	[<ownership source dir>]
```

- `DIRSHA` — one record per (path, blob) pair ever shipped under a retired
  directory, e.g. `DIRSHA	.agents/skills/aitask-pickn/SKILL.md	<blob>`.
- `DIR` gains an **optional** ownership-source field. Absent → the directory is
  its own source. Present → files are looked up under that source path. Only
  the two staging counterparts proven by release packaging
  (`.github/workflows/release.yml`: `codex_skills/` is `cp -r` of
  `.agents/skills/<skill>`, `opencode_skills/` of `.opencode/skills/<skill>`;
  `install.sh:891-942` then copies them verbatim into `aitasks/metadata/`) get
  an alias:
  ```
  DIR	aitasks/metadata/codex_skills/aitask-pickn	.agents/skills/aitask-pickn
  DIR	aitasks/metadata/opencode_skills/aitask-pickn	.opencode/skills/aitask-pickn
  ```
- A file `<dir>/<rel>` is known iff `DIRSHA <source>/<rel> <its blob>` exists.
- FILE records keep the flat `SHA` set (unchanged; a FILE record is already
  path-exact).
- A DIR with no matching DIRSHA records keeps everything (fails closed:
  `KEPT:<dir>:unrecognized-content`).

## Steps

1. **`.aitask-scripts/aitask_prune_retired_skills.sh`**
   - Loader: `read -r kind value extra`; add `DIRSHA` to the grep filter.
     `DIR` → `RETIRED_DIRS+=("$value")` and `DIR_SOURCE["$value"]="${extra:-$value}"`.
     `DIRSHA` → `KNOWN_DIR_BLOB["$extra:$value"]=1` (blob first: fixed-width hex,
     so the `:` join is unambiguous).
   - "No ownership data" guard: skip only when **both** `KNOWN_SHA` and
     `KNOWN_DIR_BLOB` are empty.
   - Extend `is_known_blob <file> [<shipped-path>]`: no path → flat-set check (as
     today); with a path → `KNOWN_DIR_BLOB["$sha:$path"]`. One function, so the
     existing Test 4 hash-less control (`is_known_blob() { return 0`) still
     disables every ownership check.
   - DIR loop: `src="${DIR_SOURCE[$rel]}"`; per file
     `is_known_blob "$f" "$src/${f#"$abs"/}"`.
   - Update the header comment ("OWNERSHIP IS DECIDED BY CONTENT…") — DIR
     ownership is content **at that exact shipped path**, staging dirs resolve via
     their declared source.

2. **`.aitask-scripts/retired_skills_manifest.txt`**
   - Add the alias field to the two staging DIR records (above).
   - Add DIRSHA records from history, using the `-m --no-renames --raw` form
     t1926's scripts recipe uses (65 pairs; 5 more than the `ls-tree` recipe —
     merge-side versions):
     ```
     DIRS=".claude/skills/aitask-pickn .claude/skills/task-workflown \
           .agents/skills/aitask-pickn .opencode/skills/aitask-pickn"
     git log --all -m --no-renames --raw --no-abbrev --format= -- $DIRS \
       | awk -F'\t' '{split($1,a," "); print a[3]"\t"$2; print a[4]"\t"$2}' \
       | grep -v '^0\{40\}' | sort -u \
       | awk -F'\t' '{print "DIRSHA\t"$2"\t"$1}'
     ```
   - Keep the existing `SHA` lines unchanged (they now govern FILE records only).
   - Rewrite the header: record types gain DIRSHA and the DIR source field;
     replace "The SHA set is FLAT on purpose…" with the split; cite release.yml
     as the proof for the two aliases and say an alias must never be added
     without equivalent packaging proof; add the DIRSHA recipe.

3. **`tests/test_prune_retired_skills.sh`**
   - Fixture: DIR content now needs per-path blobs. Add
     `shipped_at <path> [<n>] <dest>` that writes the n-th DIRSHA blob recorded
     for `<path>`. Use it for `.claude/skills/aitask-pickn/{SKILL.md,SKILL.md.j2}`,
     `.agents/skills/aitask-pickn/SKILL.md` (2nd blob → keeps the "older
     shipped version" intent), `.claude/skills/task-workflown/SKILL.md`, and the
     codex staging `SKILL.md` (an `.agents/…/SKILL.md` blob). FILE fixtures keep
     `SHA_A`. Fix the comment saying "any manifest SHA at any retired path" is
     framework-owned.
   - **New Test 6 — copied blobs at never-shipped destinations (t1932):**
     a) `.claude/skills/aitask-pickn/SKILL.md` pristine + `my_notes.md` = byte copy
        of it → KEPT;
     b) the requested regression: `aitasks/metadata/codex_skills/aitask-pickn/`
        with pristine `.agents` `SKILL.md` + the Claude `SKILL.md.j2` blob
        (`9930cc5c…`) copied in → KEPT; same for `.agents/skills/aitask-pickn/`;
     c) genuine staging copies still prune: pristine
        `aitasks/metadata/opencode_skills/aitask-pickn/SKILL.md` (an
        `.opencode/…` blob) → PRUNED.
     Assert KEPT lines, files byte-identical, and the PRUNED line for c.
   - **Negative control:** mutant dropping the path argument in the DIR loop
     (pre-fix behaviour, via `sed`). Assert it is a real mutation, exits 0, and
     DOES delete case a's directory including `my_notes.md`.
   - **Fail-closed case:** manifest copy with DIRSHA lines stripped → every DIR
     with content is KEPT; FILE records still prune.
   - **Manifest completeness** (skip on shallow clone, as
     `test_retired_scripts_manifest.sh` does): run the step-2 recipe and assert
     every pair is a DIRSHA record; every DIRSHA blob is a real blob; every DIR
     source has ≥1 DIRSHA record.

4. **`tests/test_retired_scripts_manifest.sh`** (lines 48-52) and the
   **`retired_scripts_manifest.txt`** header ("FILE RECORDS ONLY"): the rationale
   "DIR check is content-only" is no longer true. Keep the FILE-only policy and
   the assertion; restate the reason (a DIR record would need DIRSHA records this
   manifest's recipe does not produce — without them it is always kept — and a
   FILE record already removes exactly what shipped).

5. **`aidocs/framework/skill_authoring_conventions.md:157-161`** — "content hashes
   to a version the framework actually shipped" → "…shipped at that path".

6. Step 9 (Post-Implementation): commit code (`bug: … (t1932)`), archive via the
   standard workflow.

## Verification

- `bash tests/test_prune_retired_skills.sh` — all pass, incl. Test 6 (a/b/c), the
  path-key negative control (must delete), fail-closed case, completeness.
- `bash tests/test_retired_scripts_manifest.sh`,
  `bash tests/test_upgrade_prunes_retired_scripts.sh` — still pass.
- `shellcheck .aitask-scripts/aitask_prune_retired_skills.sh tests/test_prune_retired_skills.sh`.

## Risk

### Code-health risk: low
- DIR pruning now depends on DIRSHA completeness and on the two staging aliases; a missing pair or wrong alias keeps a pristine retired dir. Fail-closed direction (KEPT + cleanup command), pinned by the completeness check and Test 6c · severity: low · → mitigation: none (covered by step 3)

### Goal-achievement risk: low
None identified.
