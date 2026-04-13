# Lifecycle Instructions for agent: detailer_001

## Status Updates
Call the crew status update script to report your status:
```bash
ait crew status --crew brainstorm-427 --agent detailer_001 set --status <status>
```
Valid statuses: Running, Completed, Aborted, Error

## Progress Reporting
Update your progress (0-100):
```bash
ait crew status --crew brainstorm-427 --agent detailer_001 set --progress <N>
```

## Heartbeat / Alive Signal
Periodically write to your alive file to signal you are active:
```bash
ait crew status --crew brainstorm-427 --agent detailer_001 heartbeat
```

## Reading Commands
Check for intra-run commands (e.g., force stop):
```bash
ait crew command list --crew brainstorm-427 --agent detailer_001
```

## Writing Output
Write your results to: detailer_001_output.md

## Your Files
All your files are in: .aitask-crews/crew-brainstorm-427

- `_work2do.md` → .aitask-crews/crew-brainstorm-427/detailer_001_work2do.md
- `_input.md` → .aitask-crews/crew-brainstorm-427/detailer_001_input.md
- `_output.md` → .aitask-crews/crew-brainstorm-427/detailer_001_output.md
- `_instructions.md` → .aitask-crews/crew-brainstorm-427/detailer_001_instructions.md
- `_status.yaml` → .aitask-crews/crew-brainstorm-427/detailer_001_status.yaml
- `_commands.yaml` → .aitask-crews/crew-brainstorm-427/detailer_001_commands.yaml
- `_alive.yaml` → .aitask-crews/crew-brainstorm-427/detailer_001_alive.yaml

## Checkpoints
At each checkpoint in your work2do flow:
1. Send heartbeat
2. Check for pending commands
3. Update progress
4. If a 'kill' command is received, run your abort procedure and set status to Aborted
