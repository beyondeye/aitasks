---
Task: t1270_ait_help_missing_gate_pass.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1270 — `ait --help` omits `gate pass` from the "Gates:" list

## Context

`ait gate pass <task-id> <gate>` is fully wired: `ait:323` dispatches it to
`.aitask-scripts/aitask_gate_pass.sh`, and it is the **human's** sanctioned tool
for signing an async human gate (t635_15). Both `ait gate --help` (`ait:326`) and
the website docs (`website/content/docs/commands/gates.md`,
`website/content/docs/commands/_index.md:62`) document it.

The one surface that does **not** advertise it is the top-level `show_usage`
"Gates:" block (`ait:51-60`), which lists `gate append`, `gate fail` and
`gate log` but skips `gate pass`. So a user running `./ait --help` never
discovers the only command that lets them sign a human gate — the gate the
orchestrator reports as `pending — awaiting human signal`.

The omission was noticed while adding `gates sync-registry` to the same block in
t635_34 and deliberately left for a separate task.

## Change

Single file: **`ait`**.

Insert one line into the "Gates:" section of `show_usage`, after `gate append`
(`ait:58`). The block mirrors the dispatcher's `case` order — the `gates` verbs
are listed run / unlocked / list / status / sync-registry, matching `ait:309-313`
— and the `gate` dispatcher order at `ait:322-325` is `append`, `pass`, `fail`,
`log`. So `pass` goes between `append` and `fail`:

```
  gate append    Append a gate-run block (used by verifiers)
  gate pass      Sign a human gate (writes the code-bound witness)
  gate fail      Append a manual fail marker for a gate
  gate log       Print the sidecar log for a gate's latest run
```

Padding: the block uses a 2-space indent plus a 15-column verb field. `gate pass`
is 9 characters, so it is followed by **6 spaces** — identical to the existing
`gates run` and `gate fail` lines.

No other surface needs touching: `grep` confirms `ait` is the only copy of this
usage block (`packaging/shim/ait` has no `show_usage`), and the website docs
already list `gate pass`.

## Verification

1. `./ait --help` — `gate pass` appears in the "Gates:" section between
   `gate append` and `gate fail`.
2. Column alignment — the description column of the new line lines up with its
   neighbours (verify visually, or with
   `./ait --help | sed -n '/^Gates:/,/^$/p' | cat -A` to confirm 6 trailing
   spaces after `gate pass`).
3. `bash tests/test_gate_cli_wiring.sh` still passes (its Test 1 already asserts
   `ait gate --help` lists `pass`; nothing there asserts on `show_usage`, so this
   is a no-regression check).

## Risk

### Code-health risk: low
- None identified. One added line in a `cat <<EOF` help heredoc inside
  `show_usage`; no executable code path, no shell expansion in the added text, no
  callers.

### Goal-achievement risk: low
- None identified. The task states the exact fix and the exact line; the only
  degree of freedom is placement/padding, both pinned above against the
  surrounding block.

## Step 9 (Post-Implementation)

Current-branch mode (no worktree to remove). Merge target is `main` per the
header above. After the Step 8 review + commit, run the gate orchestrator
(`ait gates run 1270` — this task declares `risk_evaluated`), then archive with
`./.aitask-scripts/aitask_archive.sh 1270`.

## Final Implementation Notes

- **Actual work done:** Exactly the planned one-line insertion in `ait` — added
  `  gate pass      Sign a human gate (writes the code-bound witness)` to the
  `show_usage` "Gates:" block, between `gate append` and `gate fail`, mirroring
  the dispatcher's `case` order at `ait:322-325`. Diff is `1 file changed,
  1 insertion(+)`.
- **Deviations from plan:** None.
- **Issues encountered:** None. All three planned verifications passed on the
  first run: `./ait --help` renders the new line with the description column
  aligned to its neighbours (6 spaces after the 9-character `gate pass`);
  `bash tests/test_gate_cli_wiring.sh` → 15/15 passed; `shellcheck ait` → clean
  apart from the three pre-existing SC1091 "not following sourced file" info
  notes.
- **Key decisions:** Placed `pass` after `append` rather than alphabetically
  last. The "Gates:" block already mirrors the dispatcher's `case` arm order for
  the `gates` verbs (run / unlocked / list / status / sync-registry ==
  `ait:309-313`), so following the `gate` dispatcher order (`append`, `pass`,
  `fail`, `log` == `ait:322-325`) keeps the block's ordering rule consistent.
  Kept the task-suggested description wording rather than the website's terser
  "Sign off a human gate", because the surrounding entries (`gate append`) use
  the same explanatory-parenthetical style and the witness detail is the
  distinguishing fact about this verb.
- **Upstream defects identified:** None

