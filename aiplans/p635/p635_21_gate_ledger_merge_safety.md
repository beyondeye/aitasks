---
Task: t635_21_gate_ledger_merge_safety.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md
Archived Sibling Plans: aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md
Base branch: main
---

# t635_21 — Gate Ledger Merge Safety (concurrent `## Gate Runs` auto-merge)

## Context

The gate ledger appends marker-first blockquote blocks to a task's `## Gate Runs`
section (`aidocs/gates/aitask-gate-framework.md` §3). Single-lane recording is safe
today: the lock-holder is the only appender. The gap opens once a gate can be
**passed from a different PC than the lock-holder** (async human gates t635_15,
remote projection t635_16): two machines append different blocks to the same
section concurrently.

`merge_body()` (`.aitask-scripts/board/aitask_merge.py:226`) treats **any** body
divergence as unresolved — wraps both sides in `<<<<<<< LOCAL / >>>>>>> REMOTE` and
returns `is_resolved=False`. So two concurrent gate-block appends surface as a manual
body conflict during `ait sync` / `task_push` rebase — the friction the ledger is
meant to avoid. Roadmap "open design problem 3". Not a blocker for t635_2 but **must
land before t635_15**.

**Goal:** concurrent appends to `## Gate Runs` merge automatically — both blocks
survive, ordering is deterministic, and `aitask_gate.sh status` still derives the
correct current state (last-run-wins). Crucially: **never silently reorder or drop
ledger data** — any anomaly falls back to the existing conflict-marker path so a
human resolves it.

## Approach decision — Option B (union inside `merge_body`)

- **Option A — git `merge=union` via `.gitattributes`.** *Rejected.* `*.md merge=union`
  unions the whole file incl. YAML frontmatter (garbled keys); a region-scoped custom
  merge driver needs a per-clone binary registered via `ait setup` — a new install
  surface with no fallback for clones that lack it.
- **Option B — union the gate blocks inside `merge_body()`.** *Chosen.* Composes with
  the existing `aitask_sync.sh:try_auto_merge` → `aitask_merge.py --batch --rebase`
  path; no `.gitattributes`, no install surface; non-gate bodies keep exact existing
  behavior. Reuses the canonical parser in `lib/gate_ledger.py` (t635_8 owns it —
  **do not fork**).

**`aitask_sync.sh` needs no change** — `try_auto_merge` already calls `aitask_merge.py`;
the union is entirely inside `merge_body`, so the live sync path benefits for free.
(Listed as a candidate file by the task; after reading `try_auto_merge` at line 205,
the correct decision is to leave it untouched and prove the path with an integration
test.)

## Design — safety-first union

Union only when the situation is provably safe; otherwise fall back to the current
conflict-marker behavior. Guards (each maps to a reviewed concern):

1. **All-valid `run` guard (ordering).** Every block on both sides must carry a
   `run=` matching ISO-8601-Z (`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$`, the exact
   shape `gate_ledger.iso_now()` emits). If any block has a missing / non-ISO `run`,
   timestamp ordering is not trustworthy → **fall back to conflict markers** (do not
   guess an order). Sorting valid ISO strings lexicographically == chronological, so
   the merged file order matches what `derive_gate_runs` needs for last-run-wins.
2. **Full-text dedup (no data loss).** Collapse only blocks whose **entire text is
   identical** (the shared ancestor history present on both sides). Divergent blocks
   that share `(name, run)` but differ in `attempt` (the legitimate same-second
   re-run) are **both kept**, never dropped. Total-order sort key
   `(run, name, attempt_as_int, full_text)` — `attempt` sorted numerically so 10
   follows 2 — makes output side-order-independent and fully deterministic.
2b. **No-ambiguous-winner guard.** Two distinct blocks sharing the **full**
   `(name, run, attempt)` identity but differing in body/status is an append-only
   contract violation (the orchestrator never emits two different records for one
   `name+run+attempt`). Picking a winner by lexical tiebreak would silently choose the
   derived current status. So if any `(name, run, attempt)` group still holds >1
   distinct block after full-text dedup → **fall back to conflict markers**. (Same
   `name+run` with *different* `attempt` is a distinct key and unioned normally.)
3. **Clean-section guard (no prose loss).** After splitting at `## Gate Runs`, every
   non-blank line in the section must be the header, an HTML comment (`<!--`), or a
   blockquote line (starts with `>`). Any stray prose / note / later `##` heading →
   the section is not purely machine-owned ledger → **fall back to conflict markers**
   so that text is never reconstructed away.
4. **Explicit, tested normalization.** When the section *is* clean, rebuild it with
   the canonical `gate_ledger.SECTION_HEADER` + `SECTION_COMMENT` + blocks joined by
   one blank line. Normalization of spacing/comment text is intentional and asserted
   by a test (the section is machine-owned).
5. **Real-append fixtures.** Tests generate blocks via the real builder
   (`gate_ledger.build_block` for units, `aitask_gate.sh append` for the integration
   test), not hand-written markers — so we test the actual gate-framework output.

## Key files

- **`.aitask-scripts/board/aitask_merge.py`** — `lib/` import of `gate_ledger`,
  helpers (`_split_gate_section`, `_block_text`, `_iso_run_ok`, `_union_gate_runs`),
  rewire `merge_body()`.
- **`tests/test_aitask_merge.py`** — new `TestGateRunsUnion` class.
- **`tests/test_sync.sh`** — end-to-end concurrent-append test.
- *(No change)* `.aitask-scripts/aitask_sync.sh`, `.aitask-scripts/lib/gate_ledger.py`.

## Reference patterns reused

- `gate_ledger.parse_gate_run_blocks(text)` → `list[GateRun]` (`.name`,
  `.fields["run"]`, `.fields.get("attempt")`, `.raw_marker`, `.raw_body_lines`) —
  canonical parser (`lib/gate_ledger.py:154`).
- `gate_ledger.SECTION_HEADER` / `SECTION_COMMENT` / `build_block` / `iso_now`
  (`lib/gate_ledger.py:44,142,275`).
- `lib/` import idiom copied verbatim from `board/aitask_board.py:14`.

## Implementation

### 1. Import `gate_ledger`

After the `from task_yaml import …` line (`aitask_merge.py:30`):

```python
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "lib"))
import gate_ledger  # noqa: E402  (path set up above)  -- stdlib-only, no new dep
```

`Path` and `re` are already imported (lines 26, 28). Self-insert means it works under
`PYTHONPATH=board` (sync) and when the test imports `aitask_merge` after inserting
`board` on `sys.path`.

### 2. Helpers

```python
_ISO_RUN_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_QUOTE_OK_RE = None  # see clean-section check below


def _split_gate_section(body: str) -> tuple[str, str]:
    """(head, section). section starts at the first '## Gate Runs' or '' if none."""
    m = re.search(r"(?m)^##\s+Gate Runs\s*$", body)
    if not m:
        return body, ""
    return body[:m.start()], body[m.start():]


def _block_text(run) -> str:
    txt = run.raw_marker
    if run.raw_body_lines:
        txt += "\n" + "\n".join(run.raw_body_lines)
    return txt


def _section_is_clean(section: str) -> bool:
    """True if every non-blank line under the header is comment or blockquote.

    Guards against dropping stray prose/notes a user or later tool placed in the
    section (which parse_gate_run_blocks would not reconstruct).
    """
    lines = section.splitlines()
    for ln in lines[1:]:                      # skip the '## Gate Runs' header line
        s = ln.strip()
        if not s:
            continue
        if s.startswith("<!--") or ln.startswith(">"):
            continue
        return False
    return True
```

### 3. `_union_gate_runs(local_body, remote_body)`

Returns `(merged_body, head_resolved)` when a **safe** union is possible, else
`None` (caller falls back to conflict markers).

```python
def _union_gate_runs(local_body: str, remote_body: str):
    local_head, local_sec = _split_gate_section(local_body)
    remote_head, remote_sec = _split_gate_section(remote_body)
    if not local_sec and not remote_sec:
        return None                                   # no ledger anywhere → not us

    # Guard 3: only union purely machine-owned ledger sections.
    if not _section_is_clean(local_sec) or not _section_is_clean(remote_sec):
        return None

    runs = gate_ledger.parse_gate_run_blocks(local_sec) \
         + gate_ledger.parse_gate_run_blocks(remote_sec)

    # Guard 1: trustworthy ordering requires valid ISO run on every block.
    if any(not _ISO_RUN_RE.match(r.fields.get("run", "")) for r in runs):
        return None

    # Guard 2: dedup by FULL TEXT only (shared history collapses; divergent kept).
    by_text = {}
    for r in runs:
        by_text.setdefault(_block_text(r), r)

    # Guard 2b: ambiguous winner — >1 distinct block for one (name, run, attempt).
    ident = {}
    for text, r in by_text.items():
        key = (r.name, r.fields.get("run", ""), r.fields.get("attempt", ""))
        ident.setdefault(key, set()).add(text)
    if any(len(texts) > 1 for texts in ident.values()):
        return None                                   # contract violation → conflict

    # Total, side-order-independent ordering. run is valid ISO ⇒ chronological.
    # attempt is sorted NUMERICALLY (so 10 sorts after 2), with a 0 fallback for
    # missing/non-numeric; only matters for same gate + same exact run + diff attempt.
    def _attempt_int(r):
        a = r.fields.get("attempt", "")
        return int(a) if a.isdigit() else 0
    ordered = sorted(
        by_text.items(),
        key=lambda kv: (kv[1].fields.get("run", ""),
                        kv[1].name,
                        _attempt_int(kv[1]),
                        kv[0]),
    )
    blocks = "\n\n".join(text for text, _r in ordered)
    merged_section = (
        f"{gate_ledger.SECTION_HEADER}\n{gate_ledger.SECTION_COMMENT}\n\n{blocks}\n"
    )

    if local_head == remote_head:
        return local_head + merged_section, True
    conflicted_head = (
        "<<<<<<< LOCAL\n" f"{local_head}" "=======\n" f"{remote_head}" ">>>>>>> REMOTE\n"
    )
    return conflicted_head + merged_section, False
```

Ordering correctness: ISO-8601-Z sorts lexicographically == chronologically, so the
merged file order is chronological and `gate_ledger.derive_gate_runs()` (last in file
order per gate) picks the genuinely newest run per gate — including the cross-side
same-gate case. Equal `run` (same-second) is broken deterministically by
`(name, attempt, text)`, and exact duplicates are already collapsed by full-text
dedup, so `merge(L,R)` and `merge(R,L)` produce identical output.

### 4. Rewire `merge_body()`

```python
def merge_body(local_body: str, remote_body: str) -> tuple[str, bool]:
    if local_body == remote_body:
        return local_body, True

    union = _union_gate_runs(local_body, remote_body)   # None ⇒ not safe to union
    if union is not None:
        return union                                    # (merged_body, head_resolved)

    conflict_body = (
        "<<<<<<< LOCAL\n" f"{local_body}" "=======\n" f"{remote_body}" ">>>>>>> REMOTE\n"
    )
    return conflict_body, False
```

Behavior matrix:
- No ledger on either side, or any guard trips (stray prose, non-ISO/missing run) →
  existing conflict path → **unchanged** (preserves `test_different_bodies`).
- Clean ledger sections diverge, heads identical (target case) → union, no markers,
  `is_resolved=True` → `main()` omits `body` from `unresolved` → `RESOLVED`, rebase
  advances, sync returns `SYNCED`.
- Clean ledger present **and** heads differ → ledger unioned, head wrapped in conflict
  markers, `is_resolved=False` → prose conflict still surfaces for manual resolution.

The `--rebase` LOCAL/REMOTE swap in `main()` is harmless — the union is symmetric.

### 5. Unit tests — `tests/test_aitask_merge.py` → `class TestGateRunsUnion`

Import `gate_ledger` as `tests/test_gate_ledger_python_parser.py:18` does. Build
fixtures with the **real builder**: `gate_ledger.build_block(text, gate, status,
{"run": "<ISO>", ...})`, assembling a body as `"<head>\n\n## Gate Runs\n<comment>\n\n
<block>\n..."`.

- `test_distinct_appends_both_survive` — head identical; local {A, B_local}, remote
  {A, C_remote}; assert `resolved is True`, no `<<<<<<<`, A/B/C all present.
- `test_ordering_deterministic` — `merge_body(L, R)[0] == merge_body(R, L)[0]`.
- `test_shared_block_deduped` — identical A on both sides appears once.
- `test_derivation_last_run_wins` — same gate, older `fail` + newer `pass` split
  across sides; `gate_ledger.derive_gate_runs(merged)["g"].status == "pass"`.
- `test_cross_side_same_gate_orders_by_timestamp` — gate g on both new-sides with
  `run` tL>tR (local newer); after merge, derived current == local's (proves
  chronological order, not side order).
- `test_same_run_different_attempt_both_kept` — same gate, **same `run`**, attempt 1
  (`fail`) and attempt 2 (`pass`); both survive, derived current == attempt 2.
  *(Concern 2.)*
- `test_divergent_same_identity_falls_back` — two blocks with identical
  `(name, run, attempt)` but different status/body → `resolved is False`, conflict
  markers present, **both** texts preserved. *(Concern 2b — no silent winner.)*
- `test_non_iso_run_falls_back_to_conflict` — a block with `run=garbage` →
  `resolved is False`, conflict markers present. *(Concern 1.)*
- `test_missing_run_falls_back_to_conflict` — block lacking `run=` → conflict fallback.
- `test_trailing_prose_falls_back` — clean blocks + a non-`>` note line after them →
  `resolved is False`, the note text is **still present** in the output. *(Concern 3.)*
- `test_clean_section_normalized` — odd inter-block spacing / legacy comment text
  normalizes to canonical `SECTION_HEADER`+`SECTION_COMMENT`+blocks; assert exact
  shape. *(Concern 4.)*
- `test_one_side_no_section` — local has clean ledger, remote (identical head) none →
  `resolved is True`, block preserved.
- `test_prose_conflict_with_clean_ledger` — heads differ, ledgers clean → `resolved is
  False`, markers present, ledger blocks unioned (present, deduped).
- Regression: existing `test_identical_bodies` / `test_different_bodies` stay green.

### 6. Integration test — `tests/test_sync.sh` (real `ait sync` + real append path)

Model on Test 5 (`:169`) and `setup_sync_repos` (`:24`). *(Concern 5 — use the real
append path.)*
1. `setup_sync_repos` (local + pc2 clones; seeded `t1_sample.md`).
2. **local:** `./.aitask-scripts/aitask_gate.sh append 1 tests_pass pass` on
   `t1_sample.md`; `git commit` (do **not** push).
3. **pc2:** copy scripts in, run `aitask_gate.sh append 1 lint pass` (or `tests_pass`
   with a later run) on the same task; commit; push to remote.
4. **local:** `aitask_sync.sh --batch`. Assert output `SYNCED` (not `CONFLICT:`), no
   rebase in progress, and `t1_sample.md` contains **both** markers. Run
   `aitask_gate.sh status 1` and assert it derives without error and shows both gates.

Exercises the genuine failure surface (`try_auto_merge` → `aitask_merge.py
--batch --rebase` → `merge_body`) with output produced by the real append path — the
bug this task fixes only manifests through that chain.

## Risk

### Code-health risk: medium
- Union runs inside the load-bearing `ait sync` rebase path; the failure mode of a
  union bug is corrupted/dropped/reordered ledger data. *Mitigated structurally*: the
  five guards make every uncertain case fall back to the (already-correct) conflict-
  marker path rather than guess, and dedup is by full text so no block is ever
  dropped · severity: medium · → mitigation: in-task guard design + unit matrix
  (incl. non-ISO, missing-run, same-run/diff-attempt, divergent-identity,
  trailing-prose) + real-path integration test (covered here, no separate follow-up).
- New `lib/`→`board/` import coupling (`gate_ledger` from `aitask_merge.py`) ·
  severity: low · → mitigation: copies the existing `aitask_board.py` idiom;
  stdlib-only.

### Goal-achievement risk: low
- Approach pre-vetted (Option B) and confirmed against current source; the requirement
  (deterministic auto-merge + correct last-run-wins derivation) is directly covered by
  the test matrix · severity: low · → mitigation: None identified.

*Mitigations are in-scope (guards + tests); no separate before/after mitigation tasks
are warranted.*

## Verification

```bash
python3 -m pytest tests/test_aitask_merge.py -v        # or: python3 tests/test_aitask_merge.py
bash tests/test_sync.sh
python3 -m py_compile .aitask-scripts/board/aitask_merge.py
shellcheck .aitask-scripts/aitask_sync.sh              # unchanged; sanity only
```

Acceptance: concurrent gate appends auto-merge with no manual conflict; anomalous
ledgers fall back to a manual conflict (no silent reorder/drop); existing
`test_aitask_merge.py` and `test_sync.sh` stay green; merged file derives correct
last-run-wins status.

## Post-implementation (Step 9)

Commit code (`enhancement: …(t635_21)`) and plan separately, run gates/verify_build,
then `aitask_archive.sh 635_21` (child archival; parent archives when
`children_to_implement` empties — t635_21 is not the last child).
