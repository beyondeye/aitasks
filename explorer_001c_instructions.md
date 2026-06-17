# Lifecycle Instructions for agent: explorer_001c

## Status Updates
Call the crew status update script to report your status:
```bash
ait crew status --crew brainstorm-1017 --agent explorer_001c set --status <status>
```
Valid statuses: Running, Completed, Aborted, Error

## Progress Reporting
Update your progress (0-100):
```bash
ait crew status --crew brainstorm-1017 --agent explorer_001c set --progress <N>
```

## Heartbeat / Alive Signal
Periodically write to your alive file to signal you are active:
```bash
ait crew status --crew brainstorm-1017 --agent explorer_001c heartbeat [--message "<short status>"]
```
The optional `--message` describes what you just finished (e.g. "Phase 1
complete — baseline loaded"). Use it at every checkpoint.

## Reading Commands
Check for intra-run commands (e.g., force stop):
```bash
ait crew command list --crew brainstorm-1017 --agent explorer_001c
```

## Writing Output
Write your results to: explorer_001c_output.md

This file already exists with placeholder content. Some file-write tools
require reading a file before overwriting it — if so, read
explorer_001c_output.md once first, then write your results.

## Your Files
All your files are in: .aitask-crews/crew-brainstorm-1017

- `_work2do.md` → .aitask-crews/crew-brainstorm-1017/explorer_001c_work2do.md
- `_input.md` → .aitask-crews/crew-brainstorm-1017/explorer_001c_input.md
- `_output.md` → .aitask-crews/crew-brainstorm-1017/explorer_001c_output.md
- `_instructions.md` → .aitask-crews/crew-brainstorm-1017/explorer_001c_instructions.md
- `_status.yaml` → .aitask-crews/crew-brainstorm-1017/explorer_001c_status.yaml
- `_commands.yaml` → .aitask-crews/crew-brainstorm-1017/explorer_001c_commands.yaml
- `_alive.yaml` → .aitask-crews/crew-brainstorm-1017/explorer_001c_alive.yaml

## Checkpoints
At each checkpoint in your work2do flow:
1. Send heartbeat
2. Check for pending commands
3. Update progress
4. If a 'kill' command is received, run your abort procedure and set status to Aborted
