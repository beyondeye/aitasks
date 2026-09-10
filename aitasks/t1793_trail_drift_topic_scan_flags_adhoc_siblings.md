---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [trails, python]
gates: [risk_evaluated]
created_at: 2026-09-10 23:26
updated_at: 2026-09-10 23:26
---

## Problem

`aitask_trail_gather.sh drift` reports `new_related_task` for **every** non-member task anchored into one of the trail's `scope.topics`. It never checks that the task was created after the trail was generated.

For `topic` / `multi_topic` trails this is correct, because the whole topic is the membership. For `task` / `ad_hoc` trails it is not. The gatherer's snapshot still emits `SCOPE:task|<topics csv>`, listing every topic the selected members belong to, and the trail skill copies that list into `scope.topics`. As a result, every unselected sibling in those topics reads as a new related task, and a hand-picked trail is stale from the moment it is created.

## Evidence (2026-09-10)

Creating `trail-parallel-git-and-sync` (43 hand-picked tasks, owner t1725):
- The pre-write drift check returned `STALE` with 46 reasons, while `DIGEST:` matched the snapshot exactly (`980e09ed458c7090`).
- 45 of the reasons were `new task in topic …` for long-existing tasks. Examples: t635 and its children, t1180 in topic 1171, the owner t1725, and the parent t1747.
- The only genuine reason was t1719, which depends on member t1343.
- In a scratch copy with `scope.topics: []`, drift reported only t1719.

## Where

- `.aitask-scripts/lib/trail_gather.py`, around lines 1340–1470. `scope_topics` is read from the document. The live-row loop skips only `baseline` / `input_refs`, then runs `if qualified_topic in scope_topics: add("new_related_task", ...)`.
- `aidocs/implementation_trail_design.md` §8.2 (around line 351) says "the candidate is anchored into a member topic (`scope.topics`)", while its worked example is a task "created after generation".
- The trail skill (`.claude/skills/aitask-trail/`) says to copy the SCOPE topics verbatim.

## Options

- Make the topic clause scope-kind aware: skip it for `task` / `ad_hoc` trails, keeping the depends, verifies and risk_mitigation edges.
- Or add a `created_at > generated_at` filter to the topic clause. `MEMBER_EXT` already transports `created_at`.
- Or have the gatherer emit no topics for task scope, and let the skill record topics on entries only.

Pick one, then update design §8.2 and the skill text to match. Pin both directions with tests:
- an ad-hoc trail over a subset of a topic reads `CURRENT`;
- a genuinely new task in a topic-scope trail still fires.

## Workaround in use

`trail-parallel-git-and-sync` was created with `scope.topics: []`, by user decision. Its `method_note` records the workaround.
