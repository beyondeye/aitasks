# Lifecycle Instructions for agent: explorer_001

## Status Updates
Call the crew status update script to report your status:
```bash
ait crew status --crew brainstorm-427 --agent explorer_001 set --status <status>
```
Valid statuses: Running, Completed, Aborted, Error

## Progress Reporting
Update your progress (0-100):
```bash
ait crew status --crew brainstorm-427 --agent explorer_001 set --progress <N>
```

## Heartbeat / Alive Signal
Periodically write to your alive file to signal you are active:
```bash
ait crew status --crew brainstorm-427 --agent explorer_001 heartbeat
```

## Reading Commands
Check for intra-run commands (e.g., force stop):
```bash
ait crew command list --crew brainstorm-427 --agent explorer_001
```

## Writing Output
Write your results to: explorer_001_output.md

## Checkpoints
At each checkpoint in your work2do flow:
1. Send heartbeat
2. Check for pending commands
3. Update progress
4. If a 'kill' command is received, run your abort procedure and set status to Aborted
