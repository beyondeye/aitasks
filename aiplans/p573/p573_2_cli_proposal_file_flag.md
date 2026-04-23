---
Task: t573_2_cli_proposal_file_flag.md
Parent Task: aitasks/t573_import_initial_proposal_in_brainstrom.md
Sibling Tasks: aitasks/t573/t573_1_*.md, aitasks/t573/t573_3_*.md, aitasks/t573/t573_4_*.md
Archived Sibling Plans: aiplans/archived/p573/p573_*_*.md
Worktree: (none — default profile works on current branch)
Branch: main
Base branch: main
---

# t573_2 — CLI: `ait brainstorm init --proposal-file`

## Context

Blocks on t573_1 (needs the `initializer` agent type and
`register_initializer` / `init_session(..., initial_proposal_file=...)`).
Wires the import feature at the CLI level so both the shell and the TUI
(via t573_3 shelling to this CLI) can use it.

## Implementation steps

### 1. `brainstorm_cli.py` argparser

In `cmd_init`'s subparser block (`brainstorm_cli.py:146-151`):

```python
p_init.add_argument(
    "--proposal-file",
    default="",
    help="Optional markdown file to use as initial proposal (analyzed by initializer agent)",
)
```

### 2. `brainstorm_cli.py cmd_init`

```python
def cmd_init(args: argparse.Namespace) -> None:
    spec = Path(args.spec_file).read_text(encoding="utf-8") if args.spec_file else ""
    proposal_file = args.proposal_file or None

    wt = init_session(
        task_num=args.task_num,
        task_file=args.task_file,
        user_email=args.email or "",
        initial_spec=spec,
        initial_proposal_file=proposal_file,
    )
    print(f"SESSION_PATH:{wt}")

    if proposal_file:
        from brainstorm.brainstorm_crew import register_initializer
        session_data = load_session(args.task_num)
        crew_id = session_data.get("crew_id", f"brainstorm-{args.task_num}")
        agent_name = register_initializer(
            session_dir=wt,
            crew_id=crew_id,
            imported_path=str(Path(proposal_file).resolve()),
            task_file=args.task_file,
            group_name="bootstrap",
            launch_mode="interactive",
        )
        print(f"INITIALIZER_AGENT:{agent_name}")
```

Preserve the existing happy path when `proposal_file` is None.

### 3. `aitask_brainstorm_init.sh` — flag parsing

After the existing `--help` block (`aitask_brainstorm_init.sh:50-69`),
add an option branch:

```bash
        --proposal-file)
            PROPOSAL_FILE="$2"; shift 2 ;;
        --proposal-file=*)
            PROPOSAL_FILE="${1#*=}"; shift ;;
```

Initialize `PROPOSAL_FILE=""` near `TASK_NUM=""` at top of the parsing
block. Validate when non-empty:

```bash
if [[ -n "$PROPOSAL_FILE" ]]; then
    [[ -f "$PROPOSAL_FILE" ]] || die "Proposal file not found: $PROPOSAL_FILE"
    [[ -r "$PROPOSAL_FILE" ]] || die "Proposal file not readable: $PROPOSAL_FILE"
    [[ -s "$PROPOSAL_FILE" ]] || die "Proposal file is empty: $PROPOSAL_FILE"
    case "$PROPOSAL_FILE" in
        *.md|*.markdown) ;;
        *) warn "Proposal file has no .md/.markdown extension; continuing." ;;
    esac
    # Resolve to absolute path (python3 fallback for macOS portability).
    PROPOSAL_FILE="$(python3 -c 'import os,sys; print(os.path.realpath(sys.argv[1]))' "$PROPOSAL_FILE")"
fi
```

### 4. `aitask_brainstorm_init.sh` — crew init with six types

Update the crew-init call (`aitask_brainstorm_init.sh:128-134`) to
include the initializer type:

```bash
    --add-type "initializer:$(_get_brainstorm_agent_string initializer):$(_get_brainstorm_launch_mode initializer)" \
```

Place after the `patcher` line. Without this the crew won't know about
the `initializer` agent type when it runs — `_run_addwork` would fail.

### 5. `aitask_brainstorm_init.sh` — pass flag and capture output

Change the python invocation (`aitask_brainstorm_init.sh:150-156`) to:

```bash
init_args=(
    --task-num "$TASK_NUM"
    --task-file "$TASK_FILE"
    --email "$USER_EMAIL"
    --spec-file "$SPEC_FILE"
)
if [[ -n "$PROPOSAL_FILE" ]]; then
    init_args+=(--proposal-file "$PROPOSAL_FILE")
fi
init_output=$("$PYTHON" "$SCRIPT_DIR/brainstorm/brainstorm_cli.py" init "${init_args[@]}") || {
    die "Failed to initialize brainstorm session: $init_output"
}
echo "$init_output"
```

(Echo so the user sees `SESSION_PATH:` and, when relevant,
`INITIALIZER_AGENT:`.)

### 6. `aitask_brainstorm_init.sh` — auto-start runner

After the echo, when `PROPOSAL_FILE` is non-empty and `init_output`
contains `INITIALIZER_AGENT:`:

```bash
if [[ -n "$PROPOSAL_FILE" ]] && grep -q '^INITIALIZER_AGENT:' <<<"$init_output"; then
    crew_id="brainstorm-${TASK_NUM}"
    if bash "$SCRIPT_DIR/aitask_crew_run.sh" --id "$crew_id" --detach 2>/dev/null; then
        info "Initializer agent started in interactive mode."
        info "Attach with: ait crew attach $crew_id"
        info "Or open the TUI: ait brainstorm $TASK_NUM"
    else
        warn "Could not auto-start runner. Run 'ait crew run --id $crew_id' manually."
    fi
fi
```

Check the actual crew-run subcommand name by inspecting
`.aitask-scripts/aitask_crew_*.sh` before wiring — the script file
names are the authoritative source.

## Verification

- `ait brainstorm init 9999 --proposal-file /does/not/exist` →
  dies with "Proposal file not found", exit 1, no crew dir created.
- `ait brainstorm init <fresh> --proposal-file /tmp/ex.md` →
  stdout contains both `SESSION_PATH:` and
  `INITIALIZER_AGENT:initializer_bootstrap`. `br_session.yaml` has
  `initial_proposal_file`. Runner auto-starts (or warns if the
  subcommand is missing).
- `ait brainstorm init <fresh2>` (no flag) → unchanged stdout
  (`SESSION_PATH:` only, no `INITIALIZER_AGENT:` line). No runner
  auto-start. No initializer agent registered.
- `shellcheck .aitask-scripts/aitask_brainstorm_init.sh` clean.

## Notes for sibling tasks

- t573_3 relies on the stdout line `INITIALIZER_AGENT:initializer_bootstrap`
  — do not rename or reorder. Emit it exactly as shown.
- The runner auto-start is best-effort (warn on failure). t573_3's
  polling code must tolerate a missing runner and notify the user.
