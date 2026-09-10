---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [frozen, tui, minimonitor, aitask_monitor]
gates: [risk_evaluated]
anchor: 1705
followup_kind: upstream_defect
created_at: 2026-09-10 12:09
updated_at: 2026-09-10 12:09
---

## Origin

Spawned from t1705_9 during Step 8b review, while writing the frozen-agent TUI
documentation. Both defects are in shipped UI copy, not in behaviour — the code
does the right thing and describes it inaccurately.

## Upstream defect

- `monitor_app.py:3549` / `minimonitor_app.py:3017` — the frozen-drop
  confirmation body advises "restore or re-pick it instead if you still want
  it", which implies those routes preserve the capture. A *verified* restore or
  re-pick deletes it (`agent_sessions.py:798-807`); only a failed or
  liveness-only restore keeps it. The dialog's advice is right about not losing
  the *agent* and misleading about keeping the *transcript*.
- `frozenagent_app.py:134,927` — the viewer's drop confirmation uses the verb
  **"Remove"** ("Remove the frozen record and its capture?") while both monitors
  use **"Drop"** with a matching title, deliberately chosen in t1705_7 so the
  destructive verb names itself. Same operation, two verbs across three
  surfaces.

## Diagnostic context

The capture-retention matrix, verified against the tree while documenting it:

| action | capture |
|---|---|
| verified restore (`ack=hook`) | **deleted** |
| verified re-pick (`ack=hook`) | **deleted** |
| liveness-only restore | kept |
| failed restore | kept |
| drop | deleted |

`agent_sessions.py:798-807` is the single deletion site: the hook-ack success
path sets `ack="hook"` and calls `remove_captures(rec.id)`. Both `resume` and
`repick` modes reach it — repick adopts the new session id and falls through to
the same block. The comment there ("Captures are deleted ONLY on a verified ack.
A liveness-only confirm keeps them, which is what stops a malformed resume that
starts a fresh session from destroying the only copy.") shows the retention rule
is deliberate; it is the dialog copy that has not kept up with it.

This surfaced because the same wrong belief was written into the t1705_9 docs in
three places and caught in review — the drop dialog's own wording is the likely
source of the misreading, which is why it is worth fixing at the source rather
than only in prose.

The verb split has a known history: t1705_7 deliberately renamed the monitors'
button to "Drop" with the rationale that "a 'Freeze' button here would read as
the reversible operation while deleting the only copy of the agent's output".
The viewer (t1705_6, earlier) was not part of that change and kept "Remove".

## Suggested fix

Reword the monitors' drop-confirmation tail so it does not promise retention —
e.g. point at copying the output rather than at restore/re-pick, or say
explicitly that a successful restore also discards the capture. Then pick one
destructive verb and use it on all three surfaces; "Drop" is the one with a
recorded rationale, and it matches the key (`k`) and the engine verb
(`aitask_frozen.sh drop`).

Docs to update in the same change: `website/content/docs/tuis/frozenagent/`
(`_index.md`, `how-to.md`) quote the viewer's dialog verbatim, and
`website/content/docs/tuis/minimonitor/how-to.md` and `monitor/how-to.md` quote
the monitors' — all four move together with the strings.
