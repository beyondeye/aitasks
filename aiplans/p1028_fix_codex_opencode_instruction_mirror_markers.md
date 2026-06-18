---
Task: t1028_fix_codex_opencode_instruction_mirror_markers.md
Base branch: main
plan_verified: []
---

# Plan: Fix codex/opencode instruction mirror markers (t1028)

## Context

`.codex/instructions.md` and `.opencode/instructions.md` are committed
agent-instruction mirrors. They were hand-authored in a markerless custom-title
format (`# … Codex CLI Instructions` + `<!-- Assembled from … -->`), so they
**lack** the `>>>aitasks` / `<<<aitasks` markers that
`insert_aitasks_instructions()` (`.aitask-scripts/aitask_setup.sh:1097`) relies
on. Because the markers are absent, the next real `ait setup` run takes the
*append* branch (`aitask_setup.sh:1121-1124`) and **appends a duplicate aitasks
block** instead of replacing in place — verified during t1016_2 (files
ballooned ~82 → ~176 lines, a second `## Task File Format`). AGENTS.md is
unaffected: it carries the markers and round-trips cleanly via
`update_agentsmd`.

**Key finding from exploration:** the setup code is *already* correct.
`insert_aitasks_instructions` is marker-based and idempotent — tests
`test_agent_instructions.sh` T13/T15/T20 already prove a fresh/re-run install
produces exactly one marker pair. The bug lives entirely in the **committed
artifacts**, which never match what setup generates. Additionally, commit
`adb17d27b` (t331, "Clean up agent instruction seeds") deliberately stripped the
`## Skills` section + custom title from the seeds, but the mirrors were never
regenerated — so they are also content-stale (carry a dead `## Skills` section,
miss the shared seed's newer `## Folded Task Semantics` / `## Manual Verification
Tasks`).

**Chosen approach (option 1 from the task): normalize the committed mirrors to
the canonical `ait setup` output.** This adds the markers (fixing the
duplication root cause) and re-syncs the stale content in one move, leaving the
files byte-identical to a fresh setup run so future setups are no-ops.
Rejected: option 2 (rewrite setup to full-file regeneration) — larger blast
radius and it would contradict the existing, tested marker behavior. The
mirrors' dead `## Skills` invocation hint is dropped (user-confirmed; honors
t331's intentional seed removal).

## Files to change

- `.codex/instructions.md` — regenerate (plain `git`; not under aitasks/).
- `.opencode/instructions.md` — regenerate.
- `tests/test_agent_instructions.sh` — add regression coverage.

No change to `aitask_setup.sh` — the generator is already correct.

## Step 1 — Regenerate the two mirrors to canonical setup output

Drive the *actual* setup functions via their create path so the result is
byte-identical to a fresh `ait setup` (the metadata seed copies are absent in
this data-branch install, so `assemble_aitasks_instructions` falls back to
`seed/` — exactly what real setup uses here):

```bash
source .aitask-scripts/aitask_setup.sh --source-only
for agent in codex opencode; do
  content="$(assemble_aitasks_instructions "$PWD" "$agent")"
  rm -f ".$agent/instructions.md"          # force the create branch (no leading blank, no append)
  insert_aitasks_instructions ".$agent/instructions.md" "$content"
done
```

Result for each file: `>>>aitasks\n<shared seed + agent Layer-2>\n<<<aitasks\n`
(generic `# aitasks Framework — Agent Instructions` H1, no custom title, no
assembled-from comment, `## Folded Task Semantics` + `## Manual Verification
Tasks` present, dead `## Skills` gone).

## Step 2 — Add regression tests to `tests/test_agent_instructions.sh`

Append three tests after the existing T21 block (before the Summary section):

- **T22 — committed `.codex/instructions.md` carries exactly one marker pair.**
  Assert the real repo file (`$PROJECT_DIR/.codex/instructions.md`) contains
  exactly one `>>>aitasks` and one `<<<aitasks`. This is the *direct* guard
  against the exact bug — markerless committed mirror — and would have caught it.
- **T23 — same guard for the committed `.opencode/instructions.md`.**
- **T24 — opencode marker idempotency (parity with codex T15/T20).** Build a
  tmpdir with a shared seed + an `opencode_instructions.seed.md`, then
  `assemble_aitasks_instructions … opencode` and `insert_aitasks_instructions`
  **twice** on a fresh tmp file; assert identical output and exactly one
  `>>>aitasks` — i.e. a second setup-style run does not duplicate the block in
  the opencode mirror (the codex side is already covered by T15). Uses the same
  shared function the real setup path calls.

Use the existing `assert_eq` / `assert_file_contains` helpers and the
`grep -c '^>>>aitasks$'` marker-count idiom already used in T15/T20/T21.

## Verification

1. `bash tests/test_agent_instructions.sh` — all pass, including new T22–T24.
2. `shellcheck tests/test_agent_instructions.sh` (it's the only file edited that
   is a shell script).
3. **Idempotency proof** — re-run the setup insert against the regenerated
   committed files and confirm no duplication and no diff:
   ```bash
   source .aitask-scripts/aitask_setup.sh --source-only
   for a in codex opencode; do
     before="$(cat .$a/instructions.md)"
     c="$(assemble_aitasks_instructions "$PWD" "$a")"
     tmp="$(mktemp)"; cp ".$a/instructions.md" "$tmp"
     insert_aitasks_instructions "$tmp" "$c"          # marker branch → replace in place
     diff <(printf '%s' "$before") "$tmp" && echo "$a: idempotent"
     grep -c '^>>>aitasks$' "$tmp"                      # must be 1
     rm -f "$tmp"
   done
   ```
4. Confirm each mirror has exactly one `>>>aitasks`/`<<<aitasks` pair and the
   line count is back to ~the marked-block size (no duplicate `## Task File
   Format`).

## Risk

### Code-health risk: low
- No code-logic change; regenerating two data artifacts to match the existing
  generator + adding tests. Tiny, contained blast radius (3 files, none on a
  runtime path). · severity: low · → mitigation: TBD
- Byte-drift risk if the regenerated files don't exactly match setup output —
  mitigated by driving the *real* `insert_aitasks_instructions` via its create
  path plus the Step-3 idempotency proof. · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Directly fixes the duplication root cause (markers now present → in-place
  replace), and the committed-artifact guard tests prove it. The content resync
  (drop `## Skills`, add Folded/Manual-Verification sections) is the
  user-approved intended state. · severity: low · → mitigation: TBD

No before/after mitigation tasks needed.

## Post-Implementation (Step 9)

Standard cleanup/merge/archival per task-workflow Step 9. Working on the current
branch (profile `fast`); commit `.codex`/`.opencode`/`tests` with plain `git`
under `bug: … (t1028)`; plan file via `./ait git`.
