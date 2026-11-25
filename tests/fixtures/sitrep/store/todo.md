<!-- GENERATED FILE - DO NOT EDIT MANUALLY. Machine-written by .aitask-scripts/aitask_sitrep_todo.sh in a strict format; a manual edit makes the store unreadable (recover with: aitask_sitrep_todo.sh restore todo). -->
<!-- aitask-sitrep todo format=4 -->
# Sitrep todo

## Part 1: Todo

### Situation

#### board | rev=13
- title:
- rank:
- trails:
- next:
- summary:
- digest:
- freshness: unknown
- checked_at: never
- drift:
Unrelated board work is idle.

#### crashed-agents | rev=18
- title: Crashed agents
- rank: 2
- trails:
- next:
- summary:
- digest:
- freshness: unknown
- checked_at: never
- drift:

#### sitrep | rev=19
- title: Sitrep work directions
- rank: 1
- trails: art:trail-sitrep-1
- next: t2175_2
- summary: Store format landed; skill and TUI children open.
- digest: 7c95381666ea18be
- freshness: stale
- checked_at: 2026-11-20T10:00:00Z
- drift: member_closed:2:c2+c5, trail_stale:1:art:trail-sitrep-1
Harvest is next; refresh waits on it.

Cross-repo question still open.

### Pick now

- c1 | rev=1 | kind=task | state=open | group=now | checked_at=never | ref=t2175_2 | derived=script | outcome= | Harvest parser for finished agents
- c4 | rev=4 | kind=watch | state=open | group=now | checked_at=never | ref= | derived=script | outcome= | CI on the sitrep branch
- c6 | rev=8 | kind=action | state=open | group=now | checked_at=never | ref=push:main@1a2b3c4d5e6f | derived=agent | outcome= | Push main
- c7 | rev=12 | kind=task | state=open | group=now | checked_at=2026-11-15T12:00:00Z | ref=recover:t42 | derived=script | outcome=crashed · plan approved | t42 crashed while implementing

### Next

### Waiting

- c3 | rev=3 | kind=question | state=unknown | group=waiting | checked_at=never | ref=aitasks#2171 | derived=script | outcome= | Should refresh run on the monitor tick?

### Recently done

- c2 | rev=6 | kind=action | state=done | group=next | checked_at=2026-11-01T09:30:00Z | ref= | derived=agent | outcome=pushed and deployed | Push main | then deploy dev

### Dismissed

- c5 | rev=7 | kind=task | state=dismissed | group=next | checked_at=2026-11-01T09:31:00Z | ref=t2180 | derived=script | outcome=user: duplicate of t2175_3 | Explore follow-up never picked
- c8 | rev=11 | kind=task | state=dismissed | group=next | checked_at=2026-11-15T12:00:00Z | ref=recover:t43 | derived=script | outcome=user: not worth resuming | t43 crashed while planning

## Part 2: Context

### c1
- background: Second sitrep child; turns finished-agent output into items.
- origin: agent=agent-pick-2175 task=t2175 commit=c17a85002 date=2026-11-01 skill=aitask-pick pane=%12
- direction: sitrep
- sources:
  - task: aitasks/t2175/t2175_2_sitrep_harvest_parser_for_finished_agents.md
  - plan: aiplans/p2175/p2175_2_sitrep_harvest_parser_for_finished_agents.md
  - trail: trail-sitrep-1
  - capture: sources/ceac25156205fb40.txt#L1-L3
  - commit: c17a85002
  - artifact: artifact-42
  - file: aidocs/framework/shadow_agent.md#L10
  - url: https://example.com/sitrep
- related: c2, c3

### c2
- background: Agent-derived push reminder from the t2175_1 wrap-up.
- origin: agent=agent-pick-2175 date=2026-11-01
- sources:
  - capture: sources/ceac25156205fb40.txt#L1-L2

### c6
- background: Agent-derived push reminder: main carries the sitrep refresh commit.
- origin: agent=agent-pick-2175 date=2026-11-01 skill=aitask-sitrep
- direction: sitrep
- sources:
  - commit: 1a2b3c4d5e6f
- related: c2

### c7
- background: Agent on t42 died with its PID anchor gone; plan approved, work left in the shared tree.
- origin: task=t42 date=2026-11-15 skill=aitask-sitrep incarnation=0123456789ab
- sources:
  - task: aitasks/t42_example_task.md
  - plan: aiplans/p42_example_task.md

### c8
- background: Agent on t43 died during planning; nothing to resume.
- origin: task=t43 date=2026-11-15 incarnation=89abcdef0123
- direction: sitrep
- sources:
  - task: aitasks/t43_other_task.md
