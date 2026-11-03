<!-- GENERATED FILE - DO NOT EDIT MANUALLY. Machine-written by .aitask-scripts/aitask_sitrep_todo.sh in a strict format; a manual edit makes the store unreadable (recover with: aitask_sitrep_todo.sh restore todo). -->
<!-- aitask-sitrep todo format=1 -->
# Sitrep todo

## Part 1: Todo

### Situation

#### board
Unrelated board work is idle.

#### sitrep
Harvest is next; refresh waits on it.

Cross-repo question still open.

### Pick now

- c1 | rev=1 | kind=task | state=open | group=now | checked_at=never | ref=t2175_2 | derived=script | outcome= | Harvest parser for finished agents
- c4 | rev=4 | kind=watch | state=open | group=now | checked_at=never | ref= | derived=script | outcome= | CI on the sitrep branch

### Next

### Waiting

- c3 | rev=3 | kind=question | state=unknown | group=waiting | checked_at=never | ref=aitasks#2171 | derived=script | outcome= | Should refresh run on the monitor tick?

### Recently done

- c2 | rev=6 | kind=action | state=done | group=next | checked_at=2026-11-01T09:30:00Z | ref= | derived=agent | outcome=pushed and deployed | Push main | then deploy dev

### Dismissed

- c5 | rev=7 | kind=task | state=dismissed | group=next | checked_at=2026-11-01T09:31:00Z | ref=t2180 | derived=script | outcome=user: duplicate of t2175_3 | Explore follow-up never picked

## Part 2: Context

### c1
- background: Second sitrep child; turns finished-agent output into items.
- origin: agent=agent-pick-2175 task=t2175 commit=c17a85002 date=2026-11-01 skill=aitask-pick pane=%12
- theme: sitrep
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
