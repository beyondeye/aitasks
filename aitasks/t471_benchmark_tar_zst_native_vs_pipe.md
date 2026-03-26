---
priority: medium
effort: low
depends: []
issue_type: refactor
status: Ready
labels: [task-archive, archiveformat]
created_at: 2026-03-26 22:50
updated_at: 2026-03-26 22:50
---

Split the benchmark's single TarZstCLI class into separate TarZstNative (GNU tar --zstd flag) and TarZstPipe (tar | zstd pipe) classes to compare both approaches head-to-head. Results showed pipe is ~15% faster across all operations, informing the decision in t470 to use pipe universally.
