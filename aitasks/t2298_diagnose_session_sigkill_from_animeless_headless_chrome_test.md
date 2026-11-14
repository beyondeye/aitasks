---
priority: low
effort: low
depends: []
issue_type: chore
status: Postponed
labels: []
created_at: 2026-11-14 23:20
updated_at: 2026-11-14 23:20
---

Sender record for a cross-repo note to animeless#17, which owns
`htmlpuzzles/tools/test-headless-chrome.js`.

Crash diagnosis (2026-11-14): the desktop session was SIGKILLed twice,
2026-11-13 14:22:38 and 2026-11-14 22:44:41. In the journal, every user@1000
unit shows "status=9/KILL" within ~30 ms, after which SDDM restarted its
greeter. The likely cause is that animeless t17's self-test `reap()` resolves
the host PID namespace in process-group mode (through nsFile, which the fake
browsers write) and kills every process in it. The details are in the note
sent to animeless#17.

There is no work for this repo. The task exists only because `ait note`
requires a sender task. Archive or delete it once the note has been handled.
