---
name: aitask-create2
description: Create a new aitask file interactively using bash/fzf (faster alternative to aitask-create)
---

Run the interactive task creation script:

```bash
./aitask_create.sh
```

The script handles all prompts interactively in the terminal using fzf:
- **Parent task selection** - Choose to create a standalone task or a child of an existing task
- Priority and effort selection via fzf
- Dependencies via fzf multi-select (includes sibling tasks for child creation)
- **Sibling dependency prompt** - For child tasks, asks whether to depend on previous sibling
- Task name with automatic sanitization
- Iterative description entry with file reference insertion via fzf
- Optional git commit

This is a faster, terminal-native alternative to the `/aitask-create` skill.

## Child Task Creation

To create a child task in batch mode (non-interactive):

```bash
./aitask_create.sh --batch --parent <PARENT_NUM> --name "<name>" --desc "<description>"
```

Options:
- `--parent, -P NUM` - Create as child of specified parent task
- `--no-sibling-dep` - Skip default sibling dependency

Example:
```bash
# Create first child of task t10
./aitask_create.sh --batch --parent 10 --name "first_subtask" --desc "First subtask"

# Create child without auto sibling dependency
./aitask_create.sh --batch --parent 10 --name "parallel_task" --desc "Parallel work" --no-sibling-dep
```

Child tasks are stored in `aitasks/t<parent>/` subdirectory with naming `t<parent>_<N>_<name>.md`.
