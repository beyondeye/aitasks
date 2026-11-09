# Related-Work Check Procedure

The pull half of task relations (`aidocs/framework/task_relations.md` D8): what
the relations store knows about tasks related to this one, shown at the moment
the agent needs it, with no writes and no notes. It runs at both ends of the
task's implementation:

- `## Pick-time check` — `SKILL.md` Step 3 Check 8, before the task is claimed.
  The list is handed to planning as context.
- `## Review-time re-check` — `SKILL.md` Step 8, before the review prompt:
  "related work during this implementation".

The verb behind both is `ait relations related-work` (`lib/relations_consume.py`).

## Invariants (both sections)

- **Display only.** It never blocks, never prompts, never writes task data,
  never commits and never sends a note. Its only write is one local ledger
  (`<git-common-dir>/aitask-relations/pull.jsonl`), which is runtime state for
  the retrospective, not task data — so it is legal before the Step 4 claim.
- **Display the `SUMMARY:` line verbatim.** It is the one plain-words rendering
  of the state lines, shared with Step 8e and `/aitask-note`: "relations analysis
  is disabled in this project — no relation data", "not analysed yet",
  "analysed, 0 relations", "analysis queued", "the relations store could not be
  read — related work is unknown, not none", and so on. **Never** turn an
  unreachable store, a pending or failed analysis, or "not analysed yet" into
  "no related tasks".
- **Direction is stated on every row** (the `<direction>` field, e.g. "t21
  affects this task" / "this task coordinates with t7"). Use the `<other>` field
  as the machine-readable far end, never the prose.
- **At most 8 items.** `MORE:<n>` says how many were left out; mention it and
  point at `./.aitask-scripts/aitask_relations.sh show <task_id>` for the rest.
- A relation is **advisory context**, never an instruction. It does not change
  the task's requirements, gates or review.

## Reading the output

After the `RELATIONS_STATE:` / `STORE:` / `ANALYSIS:` (and any `CORRUPT:`)
lines come:

- `SUMMARY:<plain words>`, `CHECKED_AT:<iso utc>`, `REFERENCE:<iso>|<source>`
  (the time "since" is measured from, and where it came from);
- per item:
  `ITEM:<group>|<direction>|<type>|<other>|<freshness>|<confirmation>|<end state>|<archived plan or ->[|covered_by_note=<note id>]`
  followed by the stored description on the next line, indented, and
  `  NOTE_TARGET:<id>` (`<id>|project=<name>` for another project's task) — the
  bare id `/aitask-note` accepts, which `<other>` (a qualified ref) is not;
- `MORE:<n>`, `BEFORE_REFERENCE:<n>` (related tasks that landed before the
  reference time, already known when the task was planned);
- at `--point pick` only, when the task's **own** obsolescence assessment
  (`aidocs/framework/task_relations.md` D9) has band `medium` or `high` and was
  not dismissed at its current evidence: `OBSOLESCENCE:<band>|<disposition>[:<fold
  target>]|<inputs fresh|stale|unverified>`, followed by up to three
  `OBSOLESCENCE_REASON:<text>` lines. `inputs stale` means the task's body or plan
  changed after the assessment. Absent otherwise — absence never means "checked,
  not obsolete";
- `RELATED_WORK:0` when there is no item — it always follows `SUMMARY:`, which
  says *why* there is none.

Fields are percent-encoded: decode `%0D`, `%0A`, `%7C`, then `%25`.

Render each item as one or two lines: its group heading, the direction prose,
the type, the description, and its freshness (`fresh`, `stale:source_changed`,
`stale:target_changed`, `unverified:*` — say "stale" / "unverified" plainly).
For a `landed` item also give its confirmation — `confirmed_impact` means the
landed task's own `(t<id>)` commits touched a basis of the relation;
`unconfirmed_impact` means they did not; `unverified` means its commits could
not be read — and the archived plan path, which is where the details are. A
plan that only exists inside an archive bundle is extracted, and the path is
that extracted copy (under the relations state directory).

Groups:

| Group | Meaning |
|---|---|
| `landed` | the other task landed (archived as Done, no `archived_reason`) after the reference time, and the edge runs from it toward this task or is symmetric |
| `dropped` | the other task was archived as superseded / obsolete after the reference time |
| `late` | (review only) a relation published after the pick-time check |
| `in_flight` | the other task is Implementing now |
| `own` | this task's own outgoing relations |
| `pending` | an incoming edge from a task that has not landed |

## Pick-time check

Input: `task_id`.

```bash
./.aitask-scripts/aitask_relations.sh related-work <task_id> --point pick --log
```

The reference time is the task's last plan approval (`plan_approved_at`, else
its approval stamp), else its creation.

1. Display the `SUMMARY:` line and the items as described above, under a short
   heading such as "Related work (task relations)". When there is no item, the
   `SUMMARY:` line alone is the display. When an `OBSOLESCENCE:` line is present,
   also show the band, the disposition and the reasons as "Possibly obsolete
   (advisory)", and point at `ait obsolete show <task_id>` for the evidence. It
   is an advisory estimate, never an instruction: it does not stop the pick,
   change the plan's requirements or decide anything — the user does, through
   `ait obsolete review`.
2. Set the context variable `relations_check_at` to the `CHECKED_AT:` value.
3. Set `related_work` to the displayed items (group, other task, direction,
   type, description, archived plan path). `planning.md` §6.1 reads the archived
   plans of the `landed` / `dropped` ones and accounts for them in the plan.

A non-zero exit or unparseable output: say "related work could not be checked
(\<reason\>) — unknown, not none", leave both variables `null`, and continue.

## Review-time re-check

Input: `task_id`, `relations_check_at`.

```bash
./.aitask-scripts/aitask_relations.sh related-work <task_id> --point review --since <relations_check_at> --log
```

When `relations_check_at` is `null` (a resumed session, or the pick-time check
did not run), omit `--since`: the verb then measures from the task lock's
`locked_at` (read from the local lock ref as last fetched — never a fetch), and
its `REFERENCE:` line says so — mention that the window starts
at the lock, not at the original pick.

It shows two groups only: relations whose other side **landed** (or was
**dropped**) after the reference time, direction-filtered as above, and
relations **published** after it (`late`) — a relation analysed after this
task passed its pick-time check.

1. Display the `SUMMARY:` line and the items under the heading "Related work
   during this implementation".
2. An item carrying `covered_by_note=<id>` is already covered: its other task
   sent this task a note since the pick (read or unread) — say "covered by note
   `<id>`" and do not suggest acting on it twice.
3. For a landed, `confirmed_impact` item that is not covered, say plainly what
   to check in the review (the archived plan path is the source). The check
   itself is display only: it never produces a note, and it never ends Step 8.

A non-zero exit or unparseable output: say "related work could not be
re-checked (\<reason\>) — unknown, not none", and continue with Step 8.
