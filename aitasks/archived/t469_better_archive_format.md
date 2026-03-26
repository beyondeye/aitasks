---
priority: high
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [task-archive, archiveformat]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-03-26 21:20
updated_at: 2026-03-26 22:05
completed_at: 2026-03-26 22:05
---

we currently use .tar.gz file for storing archived task and plan files. we want to check alternative formats/archive programs.we are searching for archive programs/formats widely avaiable in linux distros and macos. The current main disdavtage of the tar.gz format is that although tar natively support working with tar.gz files, in order to access the list of files in an archive (an operation that we need for checking if a some task or plan file is present in an old.tar.gz file) it needs to decompress (done in ram) the whole file in order to access the file list. there is also the general question of compression ratio for markdown files, and compression/decomporession speed. it true that we after changing the old.tar.gz archive systems to split the archive accordint to task number, we don't actually need decompress in order to know in WHICH archive file the task/plan we search is supposed to be foound (although we actually need to decompress, in order to be sure that the file is present). anyway we want to write some benchmarks for typical operations required for aitasks (benchmarks in python, multiple repetion + warmup), for some alternative to tar.gz like: .tar.zst,  zip archives, or any other good options. we can using existing old.tar.gz archives as data for tests. ask me questions if you need clarifications. t
