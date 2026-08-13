---
Task: t1517_manual_verification_artifact_rm_leaves_dangling_artifacts_ke.md
Worktree: (current branch — no worktree; profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# Auto-execution record — manual verification of t1515

Strategy: **autonomous** (approach chosen per item at execution time; this file
is the retroactive record of what was actually run).

t1515 (`082faf7b4`) made `frontmatter_patch.py remove` drop the `<field>:`
header when it takes the block's last item, so the field is **absent** rather
than left bare — a bare `artifacts:` parses as `None`, which is neither `[]`
nor absent. The task's checklist targets the three surfaces automation did not
already cover: the two live CLI round trips in **branch mode** (the e2e tests
run in a legacy-mode fixture repo, so `task_git` routing to the data branch is
uncovered) and the board's render path.

**Verification target:** t1517 itself was used as the scratch task. It is
already owned and mutated by this workflow, it had neither an `artifacts:` nor
an `attachments:` key beforehand (the exact precondition the round trip needs),
and using it avoids consuming a task id that would then need hand-deletion.

## Execution Log

### Item 1 — Live branch-mode artifact round trip

- **Item text:** Live branch-mode artifact round trip: on this repo (aitasks/
  symlinked to .aitask-data/), pick a scratch task, run `ait artifact create
  <task> <file> --kind report --handle art:tmp-check` then `ait artifact rm
  <task> art:tmp-check`; confirm the task frontmatter has NO `artifacts:` key
  afterwards and matches its pre-create state modulo updated_at.
- **Approach:** CLI invocation + byte-diff against a pre-create snapshot,
  plus an independent YAML parse.
- **Action run:**
  ```bash
  # branch mode confirmed: aitasks -> .aitask-data/aitasks (symlink)
  cp aitasks/t1517_*.md $S/pre.md
  ./ait artifact create 1517 $S/payload.txt --kind report --handle art:tmp-check
  ./ait artifact rm 1517 art:tmp-check
  grep -n '^artifacts:' aitasks/t1517_*.md   # expect no match
  diff $S/pre.md aitasks/t1517_*.md          # expect updated_at only
  python -c "yaml.safe_load(frontmatter); 'artifacts' in d"
  ./ait artifact ls 1517
  ```
- **Output (trimmed):**
  - `create` → `Created artifact art:tmp-check (v1 sha256:c1082ccb…) on t1517`,
    frontmatter gained `artifacts:` / `  - handle: art:tmp-check` / `kind: report`.
  - `rm` → `Removed artifact art:tmp-check from t1517 (manifest deleted,
    1 orphan blob(s) swept; recoverable from data-branch history)`.
  - `grep '^artifacts:'` → no match (**ABSENT**).
  - `diff` → single hunk, `updated_at: 2026-08-14 00:02` → `00:06`. Nothing else.
  - YAML parse → `artifacts in frontmatter keys: False`.
  - `ait artifact ls 1517` → `No artifacts.`
- **Verdict: pass**

### Item 2 — Live attachment round trip

- **Item text:** Live attachment round trip: same check via `ait attach add
  <task> <file>` then `ait attach rm <task> <name>`; confirm no bare
  `attachments:` key is left behind.
- **Approach:** CLI invocation + byte-diff + YAML parse (as item 1).
- **Action run:**
  ```bash
  cp aitasks/t1517_*.md $S/pre_attach.md
  ./ait attach add 1517 $S/attach_payload.txt
  ./ait attach rm  1517 attach_payload.txt
  grep -n '^attachments:' aitasks/t1517_*.md
  diff $S/pre_attach.md aitasks/t1517_*.md
  ./ait attach ls 1517
  ```
- **Output (trimmed):**
  - `add` → `Attached 'attach_payload.txt' (sha256:4cfa69a4…) to t1517`;
    frontmatter gained a 5-key `attachments:` block (hash/name/mime/size/added_at).
  - `rm` → `Removed attachment 'attach_payload.txt' from t1517`.
  - `grep '^attachments:'` → no match (**ABSENT**).
  - `diff` → **empty**. The round trip was byte-identical (add and rm landed
    inside the same `updated_at` minute), which is stronger than the
    "modulo updated_at" the checklist asks for.
  - YAML parse → `attachments in keys: False`.
  - `ait attach ls 1517` → `No attachments.`
- **Verdict: pass**

### Item 3 — Board sanity

- **Item text:** Board sanity: open `ait board` on a task whose last artifact
  was just removed and confirm the trail / artifact surfaces render normally
  now that the key is absent rather than parsing as None.
- **Approach:** live TUI interaction — detached tmux session, `send-keys` to
  drive, `capture-pane` to read — plus a negative control on the two reader
  sites.
- **Action run:**
  ```bash
  tmux -L av1517 new-session -d -x 200 -y 50 "./ait board | tee board.log"
  # Tab -> search "1517"; Esc; z (By-Trail); s (trail select); Esc; r (refresh)
  tmux -L av1517 capture-pane -p -t 0
  grep -inE 'traceback|error|exception|TypeError' board.log
  ```
- **Output (trimmed):**
  - Board booted and loaded all active tasks (232 in Unsorted/Inbox alone),
    including t1517 with its `artifacts:` key now absent.
  - t1517's card rendered normally: `☐ ◇ t1517 * manual verification artifact
    rm leaves dangling artifacts ke / 💪 medium / 🔒 dario-e@… / 📋 Implementing`.
  - `z` By-Trail pane rendered its empty-state prompt cleanly.
  - `s` trail-select modal listed both discovered trails — so
    `_iter_trail_frontmatter_records`, which iterates every active task's
    `artifacts:` block, scanned t1517's absent key and completed.
  - `r` refresh re-ran the scan; pane clean.
  - `board.log` → **no** traceback / error / exception / TypeError.
- **Negative control (bare-key fixtures in a temp dir, never in `aitasks/`):**
  a task with a bare `artifacts:` parses to `None` and an *unguarded* consumer
  raises `TypeError: 'NoneType' object is not iterable` — the defect shape
  t1515 describes. But **both** readers on this surface are already guarded:
  `aitask_board.py:940` is `for rec in meta.get("artifacts") or []`, and
  `yaml_utils.sh read_yaml_mappings` returns empty (rc 0) for a bare key.
  So the board would not have crashed on a bare key either; the fix's value on
  this surface is round-trip cleanliness, not a crash that was averted.
  Recorded so the pass is not read as stronger evidence than it is.
- **Verdict: pass**

## Unrelated finding (pre-existing, not a t1515 regression)

The trail-select modal badges **both** live trails `✗ unreadable`. Cause is
schema drift, not blob corruption: `ait artifact get` fetches both blobs
successfully (rc 0), but `trail_schema.load_trail` rejects each with
`$.schema_version: expected '1.1.0', got '1.0.0'`. Commit `b25bb4893`
(`feature: Surface followup_kind on work report, sibling chooser and trail`,
t1468_5) bumped the schema constant; the two existing trail documents were
written at 1.0.0 and were never re-rendered or migrated, so every discovered
trail now fails validation and `load_trail_blob` fails closed into
`load_error`. Predates this task and is untouched by it.

- `.aitask-scripts/lib/implementation_trail.schema.json` — `schema_version`
  const raised to 1.1.0 with no migration for, or re-render of, in-tree 1.0.0
  trail documents; `art:trail-gates-framework-landing` and
  `art:trail-shadow-review-loop` both render as `✗ unreadable` in the board's
  trail-select modal as a result.

Note also that the board booted from a **working tree with uncommitted t1505_2
WIP** in `.aitask-scripts/board/aitask_board.py` (the trail detail-modal
scoping change). That is the live state of the repo and the surfaces above
rendered clean under it, but the pass is a statement about the live tree, not
about committed HEAD.

## Cleanup

- `tmux -L av1517 kill-server` — done.
- Scratch dir `${TMPDIR:-/tmp}/auto_verify_1517/` (payloads, snapshots, bare-key
  fixtures, fetched trail blobs, board log) — outside the repo, self-expiring.
- Post-run residue check: `ait artifact ls 1517` → `No artifacts.`;
  `ait attach ls 1517` → `No attachments.`; `ait artifact ls` → back to the two
  pre-existing trail manifests only; `git status` unchanged apart from
  pre-existing WIP.
