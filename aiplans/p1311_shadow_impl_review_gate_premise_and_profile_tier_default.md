---
Task: t1311_shadow_impl_review_gate_premise_and_profile_tier_default.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1311 — Shadow impl-review: fix the gate premise, add a profile default tier

## Context

`.claude/skills/aitask-shadow/impl-challenge.md` is the shadow agent's
implementation-review sub-procedure. Two things in it work against the way the
review is actually used.

**1. The "too early to review" gate has its premise backwards.** Lines 78–90
run a required, every-tier gate: if the resolved plan has no
`## Final Implementation Notes`, it warns that "it is probably too early to
review the implementation" and makes the user pick **abort** / **proceed
anyway** before any review work happens.

But in `.claude/skills/task-workflow/SKILL.md` the Final Implementation Notes
are written only inside the **"Commit changes"** branch of Step 8 (template at
~line 471), which runs **after** the Step 8 review `AskUserQuestion` (~line
458). So at the single most common moment a user reaches for a shadow
implementation review — the followed agent parked at *"Implementation complete.
Please review and test the changes."* — the notes are absent **by
construction**. The gate fires on the normal path and charges a confirmation
round-trip for it. The procedure already half-knows this: input 2's
working-tree fallback says "this is often the live case".

**2. There is no way to preset the review tier.** Tier selection (lines 92–138)
asks a 4-option `AskUserQuestion` for any generic "review the implementation".
No execution-profile key can say "under `fast`, always run `advanced`".

**Intended outcome:** absent notes stop being an anomaly — the review proceeds
and simply *states* what it is reviewing; a profile key presets the tier so the
prompt is skipped; and the angle catalog gains explicit notes-absent semantics
so a notes-less review does not degrade into false "unjustified deviation"
findings.

**Decision (user-directed): `aitask-shadow` becomes profile-aware.**
`aidocs/framework/shadow_agent.md:58-62` currently justifies the skill being
static with *"a spawned agent CLI can only be triggered non-headlessly by a
slash command on argv, and a freshly spawned shadow has no parent skill to
read-and-follow a non-invocable one."* That argues only for
`user-invocable: true` — which stays true — and does **not** imply staticness:
`aitask-explore` is both user-invocable and a stub + `.md.j2` pair. The skill is
converted to the canonical stub pattern, so the tier default is a Jinja read
baked in at render time (exactly the `qa_tier` shape), with **no new bash
helper**. The conversion also gets the nine sub-procedures rendered into the
Codex and OpenCode trees automatically, which today they never reach.

---

## Work

Do the work in this order: mechanical conversion first, then content edits,
then render + goldens.

### A. Convert `aitask-shadow` to the stub + template pattern

Follow `aidocs/framework/stub-skill-pattern.md` §3b/§3d/§3f/§3g exactly.
Resolver key: **`shadow`**.

- **Authoring template** `.claude/skills/aitask-shadow/SKILL.md.j2` — the current
  `SKILL.md` body, moved. Only `impl-challenge.md` grows Jinja (§D); the entry
  point itself stays profile-invariant for now.
- **Four stubs** (all committed; bodies copied verbatim from an existing
  converted skill such as `aitask-qa`, substituting `aitask-shadow` / `shadow`):
  1. `.claude/skills/aitask-shadow/SKILL.md` — `--agent claude`
  2. `.agents/skills/aitask-shadow/SKILL.md` — `--agent codex`, rendered dir
     `.agents/skills/aitask-shadow-<profile>-codex-/` (shared root)
  3. `.opencode/skills/aitask-shadow/SKILL.md` — `--agent opencode`
  4. `.opencode/commands/aitask-shadow.md` — same body as (3)

  Stubs 2–4 **replace** today's "Source of Truth" redirects, which
  `tests/test_opencode_skill_legacy_pointers.sh:47-52` forbids once a skill is
  templated. The nine sub-procedures need no manual porting — the closure walk
  renders them into every agent tree.
- **Closure files stay plain `.md`** (pilot finding #4) — `impl-challenge.md`,
  `impl-review-angles.md`, `concern-format.md`, the five `plan-*.md`,
  `spawn-learn-skill.md`. Sibling references between them stay bare filenames
  and are left unrewritten by the walker, which is correct.
- **Do not introduce any `{% if agent %}` gate** — that would break Test 1b
  agent-invariance and force per-agent goldens
  (`aidocs/framework/agent_runtime_guards_audit.md`). Per-agent tool mapping
  stays in the prereq files (pilot finding #5).
- **Forbidden tokens** (§3j): the rendered body must never re-resolve the
  profile — `aitask_scan_profiles.sh`, `Select Execution Profile`,
  `Execute the Execution Profile Selection Procedure`, `refresh execution
  profile`. Shadow has none today; keep it that way.
- **Reword `SKILL.md` Step 0** — "Do not run any command before this greeting"
  now conflicts with the stub's two dispatch calls. Its real intent is *no
  capture / context fetch before the greeting*; say that.
- **Live-shadow caveat:** during the conversion a running shadow that
  read-and-follows `.claude/skills/aitask-shadow/impl-challenge.md` would see
  un-rendered Jinja. Restart any live shadow after the change (the parallel-name
  staging procedure from pilot finding #2 is available but overkill here — the
  shadow does not drive this workflow).

### B. New profile key — `shadow_impl_review_tier`

Values: **`quick` | `default` | `advanced` | `deep`** — the full words already
used throughout `impl-challenge.md`. Deliberately *not* copying `qa_tier`'s
single-letter `q`/`s`/`e` enum, which already disagrees with its own docs
(`profile_editor.py:84` vs `task-workflow/profiles.md:44`).

Registration — the three sites in the only real registry,
`.aitask-scripts/lib/profile_editor.py`:
- `PROFILE_SCHEMA` (~line 85) — `("enum", ["quick","default","advanced","deep"])`
- `PROFILE_FIELD_INFO` (~line 365) — summary + detail, stating unset ⇒ prompt
- `PROFILE_FIELD_GROUPS` (lines 368-395) — new group `("Shadow Review", [...])`

Values shipped:
- `seed/profiles/fast.yaml` — `shadow_impl_review_tier: advanced`
- `aitasks/metadata/profiles/fast.yaml` (data branch — commit with `./ait git`)
- `default.yaml` / `remote.yaml` — unset (they keep prompting)

- add `"shadow"` to `VALID_PROFILE_SKILLS` (`settings_app.py:238-241`) and to
  both "Valid skills:" strings (`settings_app.py:230`, `seed/project_config.yaml:270`)

**Activation gotcha — decided, not deferred.** The key is consulted only once
`default_profiles.shadow` names a profile; the resolver returns `default` when
unset, so the seeded `fast.yaml` value is **inert on a fresh install**. Two ways
out were considered:

- *Seed `default_profiles: {shadow: fast}` in `seed/project_config.yaml`* —
  **rejected.** That file deliberately ships `default_profiles:` empty; no skill
  is defaulted to a non-`default` profile today, and doing it for `shadow` alone
  would have the framework pick a profile on the user's behalf for a skill they
  may never run under `fast`.
- *Ship the value and document the required opt-in prominently* — **chosen**,
  and treated as deliverable work rather than a passing mention:
  - an inline comment on the key in `seed/profiles/fast.yaml` stating it takes
    effect only when `default_profiles.shadow: fast` is set;
  - the same condition stated in the `profiles.md` schema-table row, in the
    `PROFILE_FIELD_INFO` detail text (so the settings TUI shows it at the point
    of editing), and in the website tier + Configuration paragraphs — each
    giving the concrete two-line `default_profiles:` snippet;
  - `default_profiles: {shadow: fast}` added to the local, gitignored
    `aitasks/metadata/userconfig.yaml` so the feature is live in this checkout.

  The `warn_on_orphaned_profile_skill_key` mitigation later turns this
  documented condition into a detected one; until it lands, the docs above carry
  it.

### C. `impl-challenge.md` — replace the gate with a review-state assessment

Rename `## "Too early to review" gate (required — run first, every tier)`
(line 78) → **`## Review-state assessment (required — run first, every tier)`**,
and update the `## Tier selection (after the gate)` heading (line 92) to match.

The assessment resolves and then **states** — it never prompts:

1. Resolve the plan (active, then the existing archived fallback).

2. **Resolve the diff source as a COMPOSITE, not a precedence chain.** The
   current text ("task commits → staged → unstaged") reads as first-match, which
   silently misses the common shape *"an earlier task commit **plus** newer
   uncommitted edits"* — the newest work is exactly what a review most needs.
   Build the union of all four channels:

   ```bash
   # committed — TWO steps: the helper yields commit METADATA, not paths
   #   (COMMIT|<hash>|<date>|<subject>|<ins>|<del>|<matched-id>)
   ./.aitask-scripts/aitask_revert_analyze.sh --task-commits <task_id>
   # …then, per <hash>, extract its paths NUL-separated:
   git diff-tree -r --no-commit-id --name-only -z <hash>
   git diff --cached --name-only -z                                     # staged
   git diff --name-only -z                                              # unstaged
   git ls-files --others --exclude-standard -z                          # UNTRACKED
   ```

   The committed channel is the one that needs an explicit second call: without
   the `git diff-tree` step it contributes commit subjects to the review but no
   paths, so a committed file whose name contains a space would fall outside the
   path-safety guarantee the other three channels get. (`git diff-tree -r
   --no-commit-id --name-only -z` is the plumbing form — no header to strip, no
   quoting, NUL-terminated.)

   **Enumerate paths NUL-separated, never from `git status --short`.** That
   porcelain format is `XY PATH`, so a field-splitting read (`awk '$2'`) drops
   everything after the first space — `new helper.py` enumerates as
   `new` and is then never read — and the format additionally C-quotes paths
   containing spaces, quotes or non-ASCII bytes. `git ls-files --others
   --exclude-standard -z` emits raw, unquoted, NUL-terminated paths and already
   honors `.gitignore`. Consume every channel with a null-safe loop
   (`while IFS= read -r -d '' path; do … done < <(…)`), and quote `"$path"`
   everywhere downstream. The `-z` on the two `git diff` calls is for the same
   reason (a tracked path can contain a space just as easily).

   **Untracked paths are load-bearing and are missing today.** Neither `git
   diff` nor `git diff --cached` sees a brand-new file, so a task whose whole
   deliverable is a new helper or a new test would be reported as "nothing to
   review" while the implementation sits right there. Untracked files must be
   **read in full** (there is no diff to read) and reviewed as all-new code.

3. **List the included paths, and state the attribution limit.** Print the
   composite path list before reviewing, grouped by channel. Uncommitted and
   untracked changes carry **no task id** — they cannot be attributed to
   t\<id\>, so a dirty worktree may contain another task's work. Policy, stated
   in one line rather than prompted: cross-check the uncommitted paths against
   the files the plan names; review everything, but explicitly flag any path the
   plan does not mention as *possibly unrelated to this task*, and invite the
   user to narrow in free text ("only the monitor files"). A named narrowing is
   honored the same way angle scoping is.

4. Act:
   - **All four channels empty** — the *only* stop. Report "nothing to review
     for t\<id\>" and end. Not a prompt: there is nothing to proceed with.
   - **No plan at all** — continue, code-only, announcing that angles S1/S2
     (plan risks, plan deviations) are unavailable.
   - **Notes absent (the normal pre-commit case)** — **no warning, no prompt.**
     One stated line: which channels are under review, and that the notes are
     not written yet because task-workflow writes them after its Step 8 review
     prompt, so deviations are audited against the plan directly.
   - **Notes present** — state the channels; full S1/S2 semantics.

The "tell the user which source you reviewed" obligation currently in input 2
moves here (stated once, not duplicated); input 2's own "review whichever of
committed / staged / unstaged actually carries this task's changes" sentence is
rewritten to the composite rule so the two do not contradict. Also update the
Quick tier's notes glance (lines 174-176) to skip when notes are absent, and add
a `pending narration` region to the concern-block region list (line 322).

**Do not disturb** (these are asserted by tests — see §Verification): the
headings `## Findings presentation` and `## Also emit the structured concern
block`, and the literal phrases *"load-bearing for minimonitor's parser"*,
*"≤ ~30 chars"*, *"never a full repo path"*, *"mandatory and never empty"*.

### D. `impl-challenge.md` — profile-driven tier default (Jinja)

**Gate only the fallback — never the recognition rules.** Today lines 94-110 are
one bullet list: four bullets that map explicit wording to a tier
(`"quick"/"fast"`, `"default"/"basic"/"legacy"/unqualified "adversarial review"`,
`"advanced"/"standard"/"normal"`, `"deep"/"thorough"/"max"/"exhaustive"`), then a
fifth bullet holding the `AskUserQuestion`. Wrapping the whole section the way
`qa_tier` wraps its section would delete the recognition table from the rendered
`fast` variant — and with it any actual basis for honoring "deep review". The
one-line assurance "a tier named in the user's ask still wins" is not a rule the
agent can apply once the mapping is gone.

So the split is:

- **Unconditional (always rendered):** the four explicit-wording bullets;
  "Nothing routes to Quick implicitly"; the whole **Angle scoping** block (it
  applies at every tier); "State the chosen tier"; and the **Announce an
  inferred tier** rule.
- **Conditional (the fifth bullet only)** — what happens for a *generic*
  "review the implementation" with no level wording (minijinja runs with
  `undefined_behavior="strict"`, so the `is defined` guard is mandatory):

```jinja
{% if profile.shadow_impl_review_tier is defined and profile.shadow_impl_review_tier %}
- A generic "review the implementation" with no level or compatibility wording:
  run **{{ profile.shadow_impl_review_tier }}** — the tier configured by profile
  '{{ profile.name }}' (`shadow_impl_review_tier`). Announce it and name the
  override: "say 'deep review' (or any tier) to run a different one." Do NOT ask.
{% else %}
- A generic "review the implementation" with no level or compatibility wording:
  ask via `AskUserQuestion` (Header "Review tier") with four options — … verbatim …
{% endif %}
```

Resolution order, and it must read as an ordered decision in the rendered text:
**1.** a tier named in the user's ask (the unconditional bullets) → wins,
including over the profile; **2.** otherwise the profile tier when the key is
set; **3.** otherwise the prompt. The existing "announce an inferred tier" rule
extends to cover a profile-derived tier, so the user always knows which review
they got and how to override it.

### E. `impl-review-angles.md` — notes-absent semantics for S1/S2

- **S1** (lines 120-127): when the notes are absent, judge each plan risk's
  status from the diff alone and say the notes were not available.
- **S2** (lines 129-132): today "flag only deviations that are unexplained"
  makes *every* deviation a finding when no notes exist. Add the notes-absent
  mode: real deviations are still surfaced, but as **pending narration** —
  classified `informational` per the disposition rubric — unless the deviation
  is wrong on its own merits, in which case the rubric applies normally.

Mind the ±160-char two-value disposition sweep when writing this prose.

### F. Documentation

- `aidocs/framework/shadow_agent.md` — rewrite `:57-62` (the skill is now
  templated; record the corrected rationale from the Context section above);
  add `impl-challenge` to the `--deep` list at `:32-37` and an
  `impl-challenge.md` bullet to the Step-3 list at `:87-109` (both already
  stale); add the new key to Configuration `:170-177`. The standing anti-gating
  principle (`:84-85`, `:184-186`) is the natural place to record why the gate
  went.
- `website/content/docs/workflows/shadow-agent.md` — rewrite the tier paragraph
  (`:67`) to mention the profile default; **delete** the "too early" paragraph
  (`:69`); extend Configuration (`:99-102`). Do **not** rename `### Review the
  implementation` (`:54`) — it is a test anchor.
- `.claude/skills/task-workflow/profiles.md` — new schema-table row, then
  `./.aitask-scripts/aitask_skill_rerender.sh remote` and commit the three
  committed `task-workflow-remote-*` copies.
- Website key tables: `docs/skills/aitask-pick/execution-profiles.md`,
  `docs/tuis/settings/reference.md`, and the group list in
  `docs/tuis/settings/_index.md:95-104`.
- `CLAUDE.md` / `aidocs/framework/skill_authoring_conventions.md` — no change
  needed, but the shadow skill now falls under the "regenerate goldens after any
  `.md.j2` or closure edit" rule.

### G. Tests and goldens

- **`tests/test_skill_render_aitask_shadow.sh`** (new) — model on
  `tests/test_skill_render_aitask_qa.sh`. Test 1 golden-diffs, plus:
  - **both arms** of the new conditional — the `fast` render carries the
    profile-tier announce line and **not** the `Review tier` prompt; the
    `default` render carries the prompt and **not** the announce line;
  - **the precedence guard for concern 1** — the four explicit-wording bullets
    (`"quick" / "fast"`, `… "legacy" …`, `"advanced" / "standard"`,
    `"deep" / "thorough"`), the "Nothing routes to Quick implicitly" line, and
    the **Angle scoping** block must be present in **every** render, `fast`
    included. This is the assertion that would have caught the original design's
    disappearing recognition table;
  - the §3j forbidden tokens absent from every rendered combo.
- **Goldens** (mirroring the qa layout — Jinja-bearing files only, entry points
  `claude`-only):
  - `tests/golden/skills/aitask-shadow/SKILL-{default,fast,remote}-claude.md`
  - `tests/golden/procs/aitask-shadow/impl-challenge-{default,fast,remote}.md`
  Regenerate with the loop in
  `aidocs/framework/skill_authoring_conventions.md:468-480` and commit in the
  same change. **Review the golden diff** — an unrelated hunk means a
  regression, not a rubber stamp.
- **`tests/test_profile_editor_shadow_tier.py`** (new) — modeled on
  `tests/test_profile_editor_rendered_gates.py:41-42`: asserts the
  `PROFILE_SCHEMA` entry and `PROFILE_FIELD_GROUPS` membership.
- **`tests/test_settings_default_profiles_unknown_keys.py`** — extend so
  `"shadow"` is covered by the known-skill assertion (`:87-88`).
- **Extend the two shadow prose guards to the rendered tree.** Today
  `tests/test_shadow_disposition_surfaces.py` and `tests/test_concern_parser.py`
  read only `.claude/skills/aitask-shadow/*.md` — the authoring source. After
  conversion the agent actually executes a rendered variant, so add a rendered
  `-fast-` sweep to both, proving the guarantees survive rendering.

---

## Verification

Existing guards my edits can break — run first:

```bash
bash tests/run_all_python_tests.sh --test-dir tests   # read ONLY the last line
```
specifically `tests/test_shadow_disposition_surfaces.py` (the two headings must
each still match **exactly one** line; every anchored section must still name
`blocking`, `follow-up` **and** `informational`; the whole-file ±160-char
two-value sweep must stay clean) and `tests/test_concern_parser.py` (no
contiguous concern-block fences in any shadow `*.md`; the producer set must stay
exactly the four known files; the four literal phrases must survive).

Then:

```bash
bash tests/test_skill_render_aitask_shadow.sh
bash tests/test_opencode_skill_legacy_pointers.sh
bash tests/test_opencode_setup.sh
bash tests/test_skill_parity_runtime_vs_rendered.sh
./.aitask-scripts/aitask_skill_verify.sh     # aitask-shadow is now in scope
shellcheck .aitask-scripts/aitask_*.sh
```

Live acceptance (independent ground truth, not another artifact of the same
edit):

```bash
./.aitask-scripts/aitask_skill_resolve_profile.sh shadow            # -> fast
./.aitask-scripts/aitask_skill_render.sh aitask-shadow --profile fast --agent claude
F=.claude/skills/aitask-shadow-fast-/impl-challenge.md
grep -c "Review tier" "$F"                    # -> 0  (prompt gone)
grep -c '"deep" / "thorough"' "$F"            # -> 1  (recognition table SURVIVES)
grep -c "Angle scoping" "$F"                  # -> 1
grep -c 'ls-files --others --exclude-standard' "$F"   # -> untracked channel present
grep -c 'git status --short' "$F"             # -> 0  (the truncating form is gone)
```

Two behavioral checks, run in a scratch worktree — both use a filename
containing a space so the path-splitting bug cannot reappear silently:

1. **Untracked channel.** A task whose only change is a brand-new untracked
   `new helper.py`. The composite must list the full path and read the file,
   rather than report "nothing to review" or enumerate a truncated `new`. This
   one fixture exercises both the missing-channel bug and the path-splitting bug.
2. **Committed channel.** A task with a commit touching `old helper.py`, plus a
   newer uncommitted edit elsewhere. The composite must list *both* the
   committed path (in full, via the `git diff-tree` step) and the uncommitted
   one — proving the composite union replaced the first-match chain and that the
   committed channel carries paths, not just commit subjects.

End-to-end, in tmux: launch a shadow (`e` in minimonitor) against an agent
parked at the Step 8 review prompt and ask "review the implementation" —
**expected:** no abort/proceed confirmation, no tier prompt, an announced
Advanced run, and the **composite disclosure**: which of the four channels
(committed / staged / unstaged / untracked) are non-empty, the included path
list, the "possibly unrelated to this task" flag on any path the plan does not
name, and the statement that the notes are not yet written. A single
"working-tree diff source" line is **not** sufficient — the assertion is that
every non-empty channel and its paths are disclosed. Then repeat with
`/aitask-shadow --profile default …` and confirm the tier prompt returns.

## Risk

### Code-health risk: high
- **Converting a live, minimonitor-spawned skill to the stub pattern is the
  dominant risk.** It rewrites four stub surfaces, deletes three "Source of
  Truth" redirects, and newly pulls `aitask-shadow` into
  `aitask_skill_verify.sh`, `test_opencode_skill_legacy_pointers.sh`,
  `test_opencode_setup.sh` and golden coverage. A mistake breaks shadow launch
  from minimonitor for every agent · severity: high · → mitigation: t1317 (templated_skill_dispatch_smoke)
- Nine sub-procedures start being rendered into the Codex and OpenCode trees for
  the first time; they have never been executed there and the goldens only prove
  they render, not that they run · severity: medium · → mitigation: t1317 (templated_skill_dispatch_smoke)
- **No drift guard exists** between `PROFILE_SCHEMA` and
  `task-workflow/profiles.md` / the website key tables — six keys are already
  documented in only one place, so a new key can silently land half-registered ·
  severity: medium · → mitigation: profile_key_doc_drift_guard
- `impl-challenge.md` / `impl-review-angles.md` are guarded by prose-shaped
  tests (exact heading anchors, four literal phrases, a ±160-char disposition
  sweep) that prose edits can trip in non-obvious ways · severity: low ·
  → mitigation: none — covered by running both guards before commit

### Goal-achievement risk: medium
- **The shipped `fast.yaml` value is inert unless `default_profiles.shadow` is
  set** — the resolver returns `default` when unset, so a user who sets only the
  tier key sees no change and concludes the feature is broken · severity:
  medium · → mitigation: warn_on_orphaned_profile_skill_key
- The conversion is a large mechanical change wrapped around two small
  behavioral ones; if it runs long, the actual reported defects could end up
  under-verified · severity: medium · → mitigation: none — the live-acceptance
  step above is run before the Step 8 review, not after
- Removing the confirmation could make a genuinely premature review *feel*
  authoritative; mitigated by the stated diff-source line and the S2
  pending-narration semantics, but it rests on prose the model must honor ·
  severity: low · → mitigation: none
- The composite diff source can only be *stated*, not enforced — uncommitted and
  untracked paths carry no task id, so a dirty worktree holding a second task's
  work is reviewed alongside this one and the "possibly unrelated" flag depends
  on the plan naming its files accurately · severity: low · → mitigation: none —
  the stated attribution limit plus the free-text narrowing is the accepted
  ceiling here

### Planned mitigations
- timing: before | name: templated_skill_dispatch_smoke | created: t1317 | type: test | priority: high | effort: medium | addresses: code-health — stub conversion of a live minimonitor-spawned skill; sub-procedures newly rendered into Codex/OpenCode | desc: Generic dispatch-contract smoke over every templated skill (discovered by SKILL.md.j2) × every agent surface — render the variant and assert the stub's Step-3 target path exists and carries its closure files. Written against the already-templated skills so it lands BEFORE the shadow conversion, and picks up aitask-shadow automatically once converted.
- timing: after | name: profile_key_doc_drift_guard | type: test | priority: medium | effort: medium | addresses: code-health — no drift guard between PROFILE_SCHEMA and the doc key tables | desc: Add a drift test deriving both sides from live source (modeled on test_gates_reference_drift.sh) asserting every PROFILE_SCHEMA key is documented in task-workflow/profiles.md and the website key table, and vice versa.
- timing: after | name: warn_on_orphaned_profile_skill_key | type: enhancement | priority: medium | effort: low | addresses: goal-achievement — shipped tier key is inert unless default_profiles.shadow is set | desc: Surface a warning (settings TUI profile tab and/or the profile resolver) when a profile sets a per-skill key such as shadow_impl_review_tier while default_profiles.<skill> is unset or names a different profile.

> **Sequencing consequence:** because mitigation 1 is a **before** mitigation,
> Step 7 creates it as an independent task that t1311 depends on, reverts t1311
> to `Ready`, and **ends this session**. The work in §A–§G above is implemented
> in a later `/aitask-pick 1311`, once the dispatch smoke has landed.

## Post-implementation

Step 9 (merge / archival) as usual.
