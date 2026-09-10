---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: medium
depends: [t1657_3, t1657_5]
issue_type: documentation
status: Implementing
labels: [documentation, web_site, framework]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
implemented_with: claudecode/opus5
created_at: 2026-09-01 12:37
updated_at: 2026-09-10 11:25
---

# Documentation: website CLI reference, workflow guide, and aidocs contracts

## Context

Parent plan: `aiplans/p1657_task_note_mailbox_with_live_delivery.md`.
Lands after t1657_1..t1657_5 so it documents what actually shipped, not what was
planned. Follow `aidocs/framework/documentation_conventions.md` — **current-state
only**, no version history in doc bodies, and genericize any passage that names
the supported coding agents.

## Website — `ait note` gets a full CLI reference page, not a mention

It is a new top-level dispatcher command, so document it the way `ait lock` and
`ait gates` are.

### `website/content/docs/commands/note.md` (new)

Match the house shape of `website/content/docs/commands/lock.md`:

- frontmatter: `title: "Note"`, `linkTitle: "Note"`, `weight: 37` (between
  `lock` 36 and `gates` 38), `depth: [intermediate]`, a `description:` line;
- a `## ait note` heading, a usage block, and a **flags table** covering
  `<target-task-id>`, `--from`, `--text`, `--file`, and the `read` verb
  (`--by`, `--ids`, `--mode`).

It must document, because these are the parts a scripting user actually needs:

- **the structured output contract** — `NOTE_APPENDED:<note-id>|<path>`,
  `NOTE_TARGET_MISSING:`, `NOTE_SELF:`, `NOTE_ERROR:` — and the `LIVE_*` reason
  codes, the same way `lock.md` documents its exit codes 0/1/13/14;
- **which result is authoritative** — the CLI reports the durable write and
  nothing else; live outcomes come from the agent adapter; and
  `LIVE_NONE:<reason>` after a successful append is a **success**, not a partial
  failure;
- **the `base` provenance contract** — which repository is queried (the code repo
  root, never the task-file path or `.aitask-data`), that capture happens before
  the append, that `base` / `base_mergebase` are **full object ids** (storage is
  exact, presentation may abbreviate) and why, and what the `none` / `unknown`
  sentinels mean — so a reader knows exactly what tree a note's claims can be
  checked against;
- **that `from=` is a claim**, and precisely what `from_verified=` does and does
  not prove.

### `website/content/docs/commands/_index.md`

Add rows to the **Task Management** table — one for `ait note`, one for the read
side. **This index is hand-maintained; a page not listed here is effectively
invisible.**

### `website/content/docs/workflows/task-notes.md` (new)

The end-to-end story: when to note vs. spawn a task, both lanes, what happens
when live delivery is unavailable, and the trust posture. Add its entry to the
manually maintained `website/content/docs/workflows/_index.md` under **Tasks**.

### Cross-links

From `commands/lock.md` and `concepts/locks`, since live-endpoint resolution
reads the lock record.

## Internal — `aidocs/`

### `aidocs/framework/task_note_mailbox.md` (new)

- the `## Inbox` entry format and the `> | ` body sentinel (**why** it exists:
  the injection surface, which is new — the gate ledger's bodies are fixed
  labels, so its format never had to resist injection);
- the **section-ordering invariant** — `## Inbox` must precede `## Gate Runs`,
  because both gate-append paths are EOF-anchored and an Inbox placed after would
  silently swallow every future gate block;
- the merge contract for concurrent cross-PC appends;
- the note-id scheme and why uniqueness is checked under the lock rather than
  merely improbable;
- why `base` stores a **full** object id: `core.abbrev` is unset, so git
  auto-scales abbreviation to current repo size, and a prefix frozen into a
  durable note can become ambiguous as the repository grows — breaking the
  exact-tree promise for exactly the oldest notes;
- the trust posture;
- the known constraint that `aitask_update.sh --desc-file` replaces the body and
  would drop the section — a **pre-existing hazard `## Gate Runs` already
  shares**, not one introduced here.

### `aidocs/framework/live_endpoint_resolution.md` (new)

**Its own document, because the boundary outlives notes.** The primitive is
"find the live agent implementing task X"; notes are only its first consumer.

- the resolver contract and its output shapes;
- the **full degradation table** — every reason code, its trigger, and its
  guaranteed durable outcome;
- the generic/adapter split, and **why** the adapter is a skill procedure rather
  than a script (`SendMessage`/`ListAgents` are model-facing tools with no CLI);
- how to add an adapter for a new agent runtime, and the current state of the
  Codex path (`codex queue` exists; `codex agents` has no machine-readable
  listing, so there is nothing to resolve against);
- the standing rule that **tmux is discovery, never transport**, with the reason:
  `send-keys` injects into whatever UI state a pane is in, carries no agent
  identity or message framing, and offers no queued/received semantics.

## Verification

- `cd website && hugo build --gc --minify` builds clean.
- **Every new cross-reference resolves.** `hugo build` does **not** fail a dead
  `#fragment`, and `--minify` unquotes `id=` attributes — so anchor targets must
  be checked by hand against the rendered ids, not assumed from the build exit
  code.
- The new pages appear in the rendered nav via their `_index.md` rows.
- No stale claim survives: grep the docs for any statement that live delivery is
  unconditional, or that a note is anything other than advisory.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1657_3** id=2026-09-03T21:35:23Z.576a944923cae61d646f7203 from=t1657_3 from_verified=yes at=2026-09-03T21:35:23Z base=ba778609646c485676a692ce17f5c65bbf1e10be base_branch=main dirty=yes host=omg16
>
> | Advisory input from the t1657_3 session, not an instruction. Reading (receipts + pick-time surfacing) has landed on main; here is what the docs need to say that the parent plan does not.
> | 
> | 1. SURFACING IS FOUR SURFACES, NOT ONE — and two of them are asymmetric.
> |    aitask-pick (Step 0b + the shared task-workflow Step 3 Check 6), plus the two
> |    SELF-CONTAINED workflows that never reach Step 3 at all: aitask-pickrem and
> |    aitask-pickweb. aitask-resume needs nothing; it hands off to Step 3.
> | 
> |    pickweb DISPLAYS notes but never acknowledges them. That is a decision, not a
> |    gap: web mode makes NO task-file writes (no aitask_update.sh, no ./ait git,
> |    lines 15/17/351 of its template) and has no data-branch push access, so a
> |    receipt there could neither be written without breaking that invariant nor
> |    ever become durable. Leaving them unread is the fail-safe direction — they
> |    surface again on the next attended pick. Please write it up that way rather
> |    than as "pickweb does not support notes".
> | 
> | 2. DISPLAY AND ACKNOWLEDGE ARE TWO STEPS. "Never auto-actioned" governs a
> |    note CONTENT, never the read bookkeeping. Displaying changes no state.
> | 
> | 3. THE CANDIDATE LISTING IS READ-ONLY. aitask-pick Step 2b/2c shows an unread
> |    COUNT only. If a listing acknowledged notes, an agent that merely saw a task
> |    in a menu would hide that task notes from the agent who later picks it.
> | 
> | 4. TWO DECISIONS TO RECORD IN aidocs/, both asked for by the parent plan:
> |    - a note consumed on one PC does not resurface on another (receipts are
> |      shared state, unioned across checkouts);
> |    - a commit failure ROLLS THE RECEIPT BACK, unlike a note, which is kept as
> |      NOTE_APPENDED_UNCOMMITTED. A note body is irreplaceable; receipt
> |      bookkeeping is reconstructible, and an uncommitted receipt would hide a
> |      note locally with nothing durable to show for it.
> | 
> | 5. THREE-TREE CLAIM IS WRONG. agent_authoring_template() (lib/agent_skills_paths.sh:79)
> |    always returns .claude/skills/<skill>/SKILL.md.j2; .agents/ and .opencode/ hold
> |    stubs. There is ONE template per skill and no port. Do not document a
> |    per-agent-tree fanout for these skills.
> | 
> | Reader-facing vocabulary worth keeping exact: from= is a CLAIM, from_verified=yes
> | is the only verified variant and its ABSENCE is not disproof; an empty dirty is a
> | migrated note whose provenance was never measured ("not measured", never
> | "clean"); display may abbreviate base, but the stored and machine-emitted value is
> | always the full object id.

> **✉ note:t1657_4** id=2026-09-06T14:19:36Z.b1c0206c9584310eed00c5c7 from=t1657_4 at=2026-09-06T14:19:36Z base=43287d477c5d8fea50443735cd4d521da316e2a6 base_branch=main dirty=yes host=omg16
>
> | Advisory input from the session that implemented t1657_4, not an instruction.
> | t1657_4 landed on main and is archived. Your scope was authored 2026-09-01,
> | before it was implemented, so several concrete answers your doc bullets ask for
> | have changed. Nothing below invalidates your plan — it is all detail your pages
> | would otherwise have to rediscover or would get wrong.
> | 
> | 1. "HOW TO ADD AN ADAPTER FOR A NEW AGENT RUNTIME" NOW HAS A CONCRETE ANSWER.
> | 
> |    It is a data change, not a code change: add a row to
> |    `.aitask-scripts/live_delivery/agents.txt` and drop a procedure file beside
> |    it. The resolver holds no agent literal of its own — the manifest is what
> |    decides, which is also what keeps
> |    `grep -rn 'ListAgents|SendMessage|claudecode' aitask_live_endpoint.sh`
> |    empty (an acceptance criterion of t1657_4, and a test enforces it).
> | 
> |    Rules the doc should state, because each one is a real refusal:
> |    - column 2 is a BARE FILENAME resolved inside the delivery directory. A '/'
> |      or '..' is refused, not followed — the manifest is a data file.
> |    - the file must be a readable REGULAR file (-f and -r). `-r` alone is true
> |      for a directory, which is a readable path but not a readable procedure.
> |    - a row failing any of that yields LIVE_NONE:agent_unsupported:<family>, NOT
> |      LIVE_PANE. The reason is worth writing down: LIVE_PANE is a promise the
> |      caller acts on — a live endpoint AND something to deliver through — and
> |      breaking it one layer later leaves the caller with nothing to run after it
> |      has already been told the endpoint is live.
> | 
> | 2. THE ADAPTER IS NOT WHERE THE PARENT PLAN SAID.
> | 
> |    It is `.aitask-scripts/live_delivery/claudecode.md`, NOT
> |    `.claude/skills/task-workflow/live-delivery-claude.md`. Reason, worth a line
> |    in aidocs: `aitask_skill_render.sh` is a reachability dep-walker, so an .md
> |    under a skill dir that nothing references is never rendered into the
> |    per-profile variants (`task-fold-content.md` is already such an orphan). The
> |    adapter is profile-invariant and agent-neutral, so it belongs outside the
> |    skill tree entirely. Any doc that repeats the old path is wrong.
> | 
> | 3. THE OUTPUT CONTRACT, FOR YOUR "OUTPUT SHAPES" BULLET.
> | 
> |        LIVE_PANE:<%pane>|<session>:<@win>.<%pane>|<pid>|agent=<family>  exit 0
> |        LIVE_NONE:<reason>                                              exit 0
> |        LIVE_ERROR:<reason>                                             exit 2
> | 
> |    LIVE_NONE exits 0 because a degradation IS a successful resolution — "there
> |    is no live endpoint" is an answer. LIVE_ERROR is deliberately disjoint from
> |    it so "no endpoint" and "the resolver broke" can never be confused. Exactly
> |    one line on stdout, always, including on misuse: a usage error prints its
> |    help to STDERR. `-h`/`--help` is the single documented exception, because
> |    that invocation is addressed to a human.
> | 
> | 4. THE FULL DEGRADATION TABLE — 8 codes, one more than the task body listed.
> | 
> |        unlocked                   no lock record
> |        remote_host                lock's hostname != this host
> |        holder_dead                liveness -> dead
> |        holder_unknown             liveness -> unknown, INCLUDING a legacy lock
> |                                   with no `pid:` line at all (t259 is a real one
> |                                   in this repo). Never collapsed into dead —
> |                                   that conflation is the t1465 defect class.
> |        agent_unknown              implemented_with empty (the Step 4 lock ->
> |                                   Step 7 attribution window; NOT an error)
> |        agent_unsupported:<agent>  family has no usable adapter in the manifest
> |        no_pane                    holder alive, no gateway pane maps to it
> |        no_session_match           ADAPTER-layer: pane verified, no listing row
> |                                   matched
> | 
> |    The legacy-lock case is the one your table would otherwise miss.
> | 
> |    Also document the socket boundary honestly: only the gateway socket is
> |    searched, so an agent on another tmux server reads as `no_pane`.
> | 
> | 5. THE TARGET STRING IS <session>:@<window_id>.%<pane> — NOT window_index.
> | 
> |    Measured: the agent-session listing renders pane %2 as `aitasks:@2.%2` while
> |    tmux's `window_index` for that same pane is 3 and its `window_id` is `@2`.
> |    `#{window_id}` already carries its own '@'. Using the index produces a target
> |    that looks right and joins to nothing. This is worth stating because it is
> |    the adapter's join key — and the adapter joins on the PANE ID alone, treating
> |    the session:window prefix as display context, since the listing's rendering
> |    is an observed contract of a model-facing tool rather than a documented API.
> | 
> | 6. ONE THING NOT TO DOCUMENT AS A RESOLVER GUARANTEE.
> | 
> |    Two of t1657_4's own stated acceptance criteria were relocated to t1657_5:
> |    that `NOTE_APPENDED:` survives every reason code, and that a post-write
> |    adapter failure reports success-with-live-delivery-unavailable. The resolver
> |    neither appends notes nor calls SendMessage, so it cannot assert
> |    durable-first ordering — only the composition owner can. Your verification
> |    bullet "no stale claim survives" should treat those as properties of the
> |    COMPOSITION (t1657_5), not of the resolver.
> | 
> | 7. DO NOT FIX THE EXTENSION-POINTS TOUCHPOINT COUNT — IT HAS ITS OWN TASK.
> | 
> |    `aidocs/framework/aitasks_extension_points.md:319` says "7-touchpoint
> |    checklist" while its own table lists 5 rows. It was spawned at t1657_4's
> |    Step 8b as **t1717** (upstream_defect), deliberately NOT folded into your
> |    scope, because it is a different doc from this feature's own. t1717 also
> |    flags that 5 may be an undercount rather than 7 an overcount, so it is not a
> |    one-word fix. Leave it alone.
> | 
> | 8. TWO GAPS OUTSIDE YOUR WRITTEN SCOPE, FLAGGING RATHER THAN ASSIGNING.
> | 
> |    - `ait --help` ALREADY advertises `note  Send a durable note to another
> |      task's inbox`. The command is discoverable and runnable today with no
> |      reference page behind it — that is currently the widest-exposure gap, and
> |      it argues for `commands/note.md` being the first page you write.
> |    - CHANGELOG covers 2 of the 4 shipped children: a line for t1657_2, a
> |      half-line for t1657_1, nothing for t1657_3 or t1657_4. Normally
> |      /aitask-changelog sweeps this at release time; noting it in case it does
> |      not.
> | 
> | 9. WHERE TO READ THE REAL CONTRACTS RATHER THAN RE-DERIVING THEM.
> | 
> |    - `.aitask-scripts/aitask_live_endpoint.sh` header — output contract,
> |      resolution order, the tmux-is-discovery rule with its reason.
> |    - `.aitask-scripts/live_delivery/claudecode.md` — the adapter procedure,
> |      including its obligation to say WHICH pane it searched for when it reports
> |      no_session_match (a bare reason code is indistinguishable from "that
> |      session ended", so a format drift would be invisible).
> |    - `aiplans/archived/p1657/p1657_4_*.md` — a "What verification changed"
> |      table of 12 findings, and Final Implementation Notes.
> |    - `tests/test_live_endpoint_no_sendkeys.sh` — encodes the transport
> |      prohibition as an ALLOWLIST of the tmux verbs the resolver may issue, not
> |      merely "no send-keys". If you document the rule, document it that way.

> **✉ note:t1657_5** id=2026-09-07T14:46:16Z.e0d65fa4ba4abfb0eee650c8 from=t1657_5 from_verified=yes at=2026-09-07T14:46:16Z base=e2f14ab205522e0d3474aef28a7eac51730a2f53 base_branch=main dirty=yes host=omg16
>
> | Advisory input from the session implementing t1657_5, not an instruction. Sent
> | with `ait note --with-live`, which t1657_5 just added -- so this message is also
> | the end-to-end dogfood of the composition your docs will describe.
> | 
> | 1. A GAP IN YOUR SCOPE, offered for your judgement rather than assumed.
> | 
> |    Your plan names `website/content/docs/commands/note.md` and
> |    `website/content/docs/workflows/task-notes.md`, and adds rows to
> |    `commands/_index.md`. It does not mention
> |    `website/content/docs/skills/aitask-note.md`, nor the rows in the two
> |    hand-maintained skill indexes:
> | 
> |      - `website/content/docs/skills/_index.md`  (the Tasks table)
> |      - `docs/README.md`                          (the skills table)
> | 
> |    t1657_5 shipped `/aitask-note` as a user-invocable skill, so as of now there
> |    is a documented CLI verb and an undocumented skill in front of it. Every
> |    other user-invocable skill has a page in `skills/`. A page absent from those
> |    two indexes is effectively invisible -- your own plan says exactly that about
> |    `commands/_index.md`.
> | 
> |    This is docs, which is your scope, not mine -- hence a note rather than an
> |    edit.
> | 
> |    CAUTION, moment-relative and possibly already stale: when this was written,
> |    BOTH index files carried uncommitted changes from another session (the
> |    `aitask-backlog-roadmap` work, which adds its own row to each). A base SHA
> |    does not date that observation. Re-check `git status` yourself before editing
> |    either file.
> | 
> | 2. WHAT t1657_5 ACTUALLY SHIPPED, since it changes what there is to document.
> | 
> |    - `ait note ... --with-live` is NEW. It is opt-in. Without it the output
> |      contract is unchanged: exactly one line, always. With it a SECOND line
> |      follows, but ONLY after `NOTE_APPENDED:` -- every other durable outcome
> |      short-circuits the live lane and still prints one line.
> |    - The second line is the resolver's own answer, passed through VERBATIM:
> |      `LIVE_PANE:` / `LIVE_NONE:<reason>` / `LIVE_ERROR:<reason>`. Reason codes
> |      are never remapped, so LIVE_NONE and LIVE_ERROR stay disjoint.
> |    - `LIVE_ERROR:resolver_unavailable` is a reason code the WRITER mints (not
> |      the resolver): it means no parseable `LIVE_*` line came back at all.
> |    - THE EXIT STATUS FOLLOWS THE DURABLE LANE ALONE. `ait note --with-live`
> |      exits 0 whenever the note landed, whatever the live lane said. This is the
> |      part worth documenting loudly: a `LIVE_NONE:` after `NOTE_APPENDED:` is a
> |      SUCCESS with live delivery unavailable, never a partial failure.
> |    - `AIT_LIVE_ENDPOINT_SH` is the documented test seam for the resolver path,
> |      mirroring `AIT_LIVE_DELIVERY_DIR`.
> | 
> | 3. TWO POINTS YOUR EXISTING NOTES ALREADY MAKE, now with a concrete answer.
> | 
> |    - The note in your Inbox saying the "three trees" claim is wrong is correct
> |      for templated skills, but `aitask-note` is a STATIC skill (single SKILL.md,
> |      no .j2), and static user-invocable skills DO ship thin wrappers in
> |      `.agents/skills/`, `.opencode/skills/` and `.opencode/commands/`. t1657_5
> |      shipped all three, so there is no port follow-up and none should be
> |      documented. `ait-git` is Claude-only because it is `user-invocable: false`,
> |      not because a port was deferred -- worth stating, since the parent plan
> |      says otherwise.
> |    - Trigger points landed at `task-workflow` Step 8e (NEW, and deliberately
> |      outside the `risk_evaluated` Jinja conditional), `aitask-qa` Step 6, and
> |      `aitask-review` Step 3. All three are one-line OFFERS, never automatic.
> | 
> | Consume or discard; none of this obliges you to change your plan.

> **👁 note:read** id=2026-09-09T12:47:02Z.dc205f73356c2e5afbb0ad56 by=t1657_6 at=2026-09-09T12:47:02Z mode=explicit ids=2026-09-03T21:35:23Z.576a944923cae61d646f7203,2026-09-06T14:19:36Z.b1c0206c9584310eed00c5c7,2026-09-07T14:46:16Z.e0d65fa4ba4abfb0eee650c8

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T08:25:16Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-10T09:02:25Z status=pass attempt=1 type=human
