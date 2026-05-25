---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [pypy, aitask_board]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-25 18:26
updated_at: 2026-05-25 18:27
---

after working with ait board after removing support for pypy in aitasks. see
aitasks/archived/t785_retire_pypy_fast_path_consolidate_on_cpython.md

I noticed a very big slow down of the ait board, much more than estimated with benchmarks. so pypy is actually beneficial for ait board, that is one of the primary interaction surfaces of the aitasks framework so I wan to rollback the t785, and reintroduce support for pypy. for now to use only for ait board
