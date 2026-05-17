---
priority: medium
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [documentation, meta, claude]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-17 16:44
updated_at: 2026-05-17 16:46
---

Audit the Claude Code auto-memory directory at
`/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`, transform
each `feedback_*` entry that is project-relevant into an explicit
instruction in `CLAUDE.md`, then delete the promoted memory file and
its line in `MEMORY.md`.

The point of the exercise is to consolidate durable project rules
into `CLAUDE.md` (which is checked into the repo and visible to every
agent / contributor) rather than carry them in per-machine
auto-memory.

## Inventory

The memory directory currently contains 21 entries (19 feedback +
2 hardware/machine). For each entry below, I provide:
- a one-line summary of the rule
- the trigger / when it applies
- a suggested CLAUDE.md home
- whether it appears to already be covered in the current CLAUDE.md
- a recommendation on whether to promote / skip / keep

The user will go through this list and decide.

---

## Out of scope (do NOT promote — keep as memory)

These two memories are about the user's machine, not the aitasks
project, so they have no place in `CLAUDE.md`:

1. **`user_machine_omarchy_g16.md`** — Records that the user runs
   Arch + Hyprland on an ASUS ROG Strix G16, with hybrid Intel/NVIDIA
   GPU, ALC285 audio chip SSID `0x10433f20`, and GitHub username
   `beyondeye`. Used to tailor system-config suggestions.
   **Recommendation: keep as memory.**

2. **`project_g16_line_out_override.md`** — Records the user's
   per-machine ALSA mixer override that switches the ALC285 "Line
   Out" node to `switch=mute / volume=merge` so headphone audio
   survives reboots. Path:
   `~/.config/alsa-card-profile/mixer/paths/analog-output-headphones.conf`.
   **Recommendation: keep as memory.**

---

## Already covered in CLAUDE.md — delete the memory file

These memories restate rules already present in the current
`CLAUDE.md`. Recommendation: delete the memory file and the
`MEMORY.md` line; no `CLAUDE.md` edit needed.

3. **`feedback_single_source_of_truth_for_versions.md`** — When a
   constant (Python version, path, timeout) is needed across N
   scripts, define it ONCE in a sourced helper and expose a zero-arg
   function; never repeat the literal in each caller. Example from
   t695_4: `AIT_VENV_PYTHON_MIN="3.11"` lives only in
   `lib/python_resolve.sh`, callers use `require_ait_python`.
   **Already covered** by CLAUDE.md "Planning Conventions: Refactor
   duplicates before adding to them" (which uses the same example
   class — `DEFAULT_TUI_NAMES` duplicated across files).
   **Recommendation: delete memory.**

4. **`feedback_extract_new_procedures_to_own_file.md`** — Any new
   task-workflow procedure goes in its own
   `.claude/skills/task-workflow/<name>.md`; SKILL.md / planning.md
   contain only a thin "Execute the **<Name>** (see `<name>.md`)"
   reference. No inlined bodies, no "either inline or extract" plans.
   **Already covered** by CLAUDE.md "Skill / Workflow Authoring
   Conventions: Agent-specific steps live in their own procedure
   file" — note that the current CLAUDE.md formulation is scoped to
   *agent-specific* steps; the memory generalizes to ALL new
   procedures. Consider tightening CLAUDE.md wording to drop the
   "agent-specific" qualifier.
   **Recommendation: promote a 1-line generalization, delete memory.**

5. **`feedback_no_speculative_regression_tests.md`** — When an
   audit-only task finds zero new occurrences of a one-off bug class,
   do not propose lint rules / AST scanners / regression tests.
   The audit IS the deliverable. Example from t775
   (`camel_to_snake` adjacent-uppercase pitfall): the agent's first
   plan added an AST scanner; user rejected it.
   **Loosely covered** by the system-prompt rule "Don't add features,
   refactor, or introduce abstractions beyond what the task requires"
   — but the audit-specific framing is sharper and worth pinning.
   **Recommendation: promote (1-2 sentences) to Planning Conventions
   or a new "Audit Tasks" subsection.**

6. **`feedback_skills_reread_during_execution.md`** — `SKILL.md`
   files are RE-READ multiple times during a skill's execution; any
   design that mutates an in-use `SKILL.md` mid-session corrupts the
   running agent. Use per-profile subdirectories with stable
   `SKILL.md` files, render once atomically (mv from tempfile), and
   dispatch via profile-suffixed slash commands.
   **Partially covered** in CLAUDE.md — the context-variable
   discussion mentions this risk indirectly, but the
   never-overwrite-in-use-SKILL-md rule is not stated explicitly.
   **Recommendation: promote (this is load-bearing for any future
   skill renderer work).**

---

## Candidates for promotion (15 memories)

For each, I include the **rule**, **when it triggers**, and a
**suggested CLAUDE.md section**.

### Task-workflow & planning conventions

7. **`feedback_step8_explicit_acceptance_every_iteration.md`** —
   In task-workflow Step 8, the
   "Commit changes / Need more changes / Abort" prompt must be
   re-issued after EVERY iteration. The ONLY green light is an
   explicit "Commit changes" with NO open notes. Silence, tacit
   approval, "looks fine but…", or earlier-round approval do NOT
   count. From t668 (2026-04-27, follow-up to t645). Risk: agent
   infers prior approval covers later rounds → user loses last chance
   to test before commit.
   **Suggested section: new "Task Workflow Conventions" or augment
   `task-workflow/SKILL.md`.** Note: this rule arguably lives more
   naturally in the task-workflow SKILL.md (which the agent reads
   when running the workflow) than in CLAUDE.md (project-wide).
   **Recommendation: promote — but possibly to task-workflow SKILL.md
   rather than CLAUDE.md.**

8. **`feedback_followup_offers_separate_file_plan_truth.md`** —
   Two rules when adding a Step 8X-style post-implementation
   follow-up offer: (a) extract procedure body to its own file
   mirroring `manual-verification-followup.md`; (b) record cross-step
   state in the plan file's "Final Implementation Notes" subsection,
   NOT in the SKILL.md context-variables table. Use `None` as the
   positive-assertion sentinel.
   **Suggested section: Skill / Workflow Authoring Conventions.**
   Rule (a) is mostly redundant with #4 above. Rule (b) is the
   novel/durable part.
   **Recommendation: promote rule (b) only.**

9. **`feedback_dead_code_belongs_in_sibling_refactor_task.md`** —
   When a child task's plan would leave dead code, identify the
   sibling task whose scope is "cleanup / refactor / migrate /
   remove" and drop a one-line note (with file path + line range)
   under that sibling's `## Notes for sibling tasks` section.
   Don't write vague "future cleanup" or `# DEPRECATED` comments.
   From t695_2.
   **Suggested section: Planning Conventions.**
   **Recommendation: promote.**

10. **`feedback_plan_split_in_scope_children.md`** — When splitting
    a complex parent into children, default all phases to siblings
    (in scope), plus a trailing retrospective-evaluation child that
    depends on all siblings. Do NOT mark later phases as
    "out-of-scope follow-ups" unless the user explicitly excluded
    them. From t719.
    **Suggested section: Planning Conventions.**
    **Recommendation: promote.**

11. **`feedback_gate_plan_on_inflight_related_task.md`** — When a
    planned task mirrors / clones / extends data or UI rendered by
    another `Implementing` (or `Editing`) task, mark `depends:[N]`
    and park (Approve and stop here), don't fork ahead. Externalize
    the plan, but don't implement until the other task lands.
    Example: t748_2 (Graph-tab detail pane) gated on t749 (Dashboard
    detail refactor).
    **Suggested section: Planning Conventions.**
    **Recommendation: promote.**

12. **`feedback_no_workaround_for_root_cause_sync_problems.md`** —
    For local-vs-remote desync symptoms, do NOT propose adding
    fallback read tiers (e.g., `git show origin/aitask-data:<file>`)
    to `resolve_task_file` / `resolve_plan_file`. Surface desync via
    warnings + the syncer TUI instead. Workarounds hide the symptom
    and bloat resolver chains. From t712.
    **Suggested section: Planning Conventions (or a "Design
    Principles" subsection).**
    **Recommendation: promote.**

### Shell & cross-platform

13. **`feedback_no_global_path_override.md`** — Do NOT append
    framework-internal dirs like `~/.aitask/bin` to the user's
    interactive shell rc. Ship a sourced lib (`lib/aitask_path.sh`)
    that exports `PATH=...` and source it from the `ait` dispatcher
    + every `.aitask-scripts/aitask_*.sh` that needs it. Exception:
    `~/.local/bin` (where the global `ait` entry-point lives) is
    fine. From t695_3.
    **Suggested section: Shell Conventions.**
    **Recommendation: promote.**

14. **`feedback_cross_platform_audit_for_platform_bugs.md`** —
    When fixing a platform-specific bug (e.g., a Linux-only
    `aitask_setup.sh` failure), proactively audit the symmetric
    branch (the macOS one) for the same bug class — hardcoded
    literals, asymmetric symlink/cleanup steps, missing
    single-source-of-truth refactors. Fold same-family issues into
    the same task. From t727.
    **Suggested section: Shell Conventions (portability subsection).**
    **Recommendation: promote.**

### Testing

15. **`feedback_threading_tests_must_be_thorough.md`** — Plans that
    introduce a background thread, dedicated asyncio loop,
    `run_coroutine_threadsafe` bridge, etc. MUST enumerate test
    cases covering: lifecycle (start idempotency, restart, stop with
    pending work), concurrency (50+ concurrent callers), mixed
    sync+async contexts, transport failure recovery, missing-binary
    fallback, resource cleanup (`threading.enumerate()`), behavior
    parity (new path vs old). Smoke + manual verification is NOT
    enough. From t722.
    **Suggested section: new "Testing Conventions" subsection.**
    **Recommendation: promote — but note this is a fairly long
    checklist; could also live in a dedicated procedure file
    referenced from CLAUDE.md.**

### TUI / task-execution environment

16. **`feedback_tmux_stress_tasks_outside_tmux.md`** — For tasks
    whose tests destructively manipulate tmux (`kill -KILL` on
    `tmux -C attach` children, `tmux kill-session`,
    `tmux kill-server`), surface the risk at planning time and
    recommend the user pick the task from a shell OUTSIDE their
    aitasks tmux. Offer "abort + revert to Ready, keep the plan" as
    default. From t733.
    **Suggested section: TUI Conventions or Project-Specific Notes.**
    **Recommendation: promote.**

17. **`feedback_tui_footer_surface_keys.md`** — When a plan adds
    bindings to a TUI tab/screen, the same plan must also flip
    pre-existing `show=False` or `on_key`-only handlers to
    footer-visible `Binding` declarations for that tab/screen.
    Audit every existing binding on the widget/screen; partial
    footer coverage is worse than none. From t748.
    **Suggested section: TUI Conventions (already exists).**
    **Recommendation: promote.**

### Code & documentation

18. **`feedback_source_comments_for_derived_help_text.md`** —
    When a constant/dict holds user-facing help/summary text
    CONDENSED from another file (templates, schemas, docs), add a
    short source-trace comment immediately above each entry naming
    the canonical origin file + section. Example: above each entry
    in a brainstorm agent-help dict, comment
    `# Source: .aitask-scripts/brainstorm/templates/explorer.md`.
    Archived plans and tasks aren't visible to a future contributor
    opening the source file; the trace must live in code.
    **Suggested section: new "Code Conventions" or "Documentation
    Writing".**
    **Recommendation: promote.**

### Helper-script discovery

19. **`feedback_reuse_explain_context_helpers.md`** — For any
    requirement of the form "given a list of source files, find the
    aitasks/aiplans that touched them", use
    `./.aitask-scripts/aitask_explain_context.sh --max-plans N
    <files>` (and the related t369 helper family —
    `aitask_explain_extract_raw_data.sh`,
    `aitask_explain_format_context.py`, etc.). Do NOT cite or
    reinvent codebrowser's Python internals
    (`history_data.py` / `explain_manager.py`); the bash helpers are
    the supported public interface. Shared cache at
    `.aitask-explain/codebrowser/` — don't write a parallel cache.
    From t754.
    **Suggested section: new "Script Utilities / Reusable Helpers"
    subsection, or augment "Architecture".**
    **Recommendation: promote.**

### Skill-system design

20. **`feedback_recognizable_suffix_over_per_variant_gitignore.md`** —
    When a feature generates rendered/derived directories alongside
    authoring ones, encode "generated" into the directory name with
    a recognizable suffix (e.g., trailing hyphen
    `aitask-pick-fast-/`), so gitignore is one glob
    (`.claude/skills/*-/`) per agent root, never per-variant.
    Convention for aitasks framework rendered SKILL.md dirs: trailing
    hyphen. From t777_3.
    **Suggested section: new "Generated Artifacts" subsection.**
    **Recommendation: promote.**

21. **`feedback_avoid_claude_p_for_skill_invocation.md`** — Do NOT
    route skill invocation through `claude -p "<inlined prompt>"`;
    it's billed at a higher per-token rate than slash-command
    invocations against an existing session. Wrappers should render
    → atomically place into the agent's skill-discovery path →
    exec the agent with the natural slash command. Applies to all
    four agents (Claude, Codex, Gemini, OpenCode) but the rate
    rationale is Claude-specific. From t777.
    **Suggested section: Skill / Workflow Authoring Conventions.**
    **Recommendation: promote.**

---

## Implementation plan (rough sketch — refine in planning step)

1. For each memory in the **already covered** group (3–6), confirm
   coverage by reading the relevant CLAUDE.md section, then delete
   the memory file + remove its line from `MEMORY.md`. For items 4,
   5, 6 also apply a small CLAUDE.md edit to strengthen the existing
   wording.

2. For each memory in the **candidates for promotion** group
   (7–21), the user decides which to promote. For each promoted
   memory:
   a. Draft the CLAUDE.md text — typically 3–10 lines, structured
      as the existing CLAUDE.md bullets (rule + **Why** + **How to
      apply**).
   b. Add it to the suggested section (creating new subsections
      where needed).
   c. Delete the memory file + its MEMORY.md line.

3. For memories the user chooses NOT to promote, leave the memory
   file in place (no-op).

4. After all CLAUDE.md edits land, do a final pass on `MEMORY.md` to
   ensure no stale lines remain.

5. Commit with a single commit (this is a doc-only change with no
   code-behavior impact). Use the `documentation:` commit prefix.

## Out of scope

- No changes to `.aitask-scripts/` or any source code.
- The 2 hardware/machine memories (`user_machine_*`,
  `project_g16_*`) stay untouched.
- Cross-references in archived `aitasks/` / `aiplans/` to the
  promoted memories (if any) are not rewritten — the rules live in
  CLAUDE.md going forward, and the archived history references the
  memory as it was at write time.

## Decision template (for planning step)

For each candidate (7–21), the user will indicate one of:
- **Promote-as-proposed** — use the suggested CLAUDE.md section and
  the rule as summarized above.
- **Promote with edits** — describe the edit (different section,
  shorter wording, etc.).
- **Skip — keep as memory** — don't touch.
- **Skip — delete memory without promoting** — the rule is no
  longer relevant.
