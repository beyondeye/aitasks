# Inputs of the t1954_4 repository walks

Every repository-derived measurement in `results/t4/` (`realrepo_*.md`, `ts_differential.md`, the sibling and aitasks rows of `bench.md`) read a **temporary checkout of the commit below**, never a live working tree. Each checkout was made with `git clone -q --no-checkout <repo> <scratch>/snap/<name> && git -C <scratch>/snap/<name> checkout -q --detach <commit>` (read-only on the source), and verified: its `HEAD` equals the commit and its `git status --porcelain` is empty, so `git ls-files --others` contributes nothing and the walked bytes are exactly the commit's tree.

Snapshot time: 2026-10-14 (UTC). The repositories are registered names, resolved with `./ait projects resolve <name>`.

| repository | commit | tree | on a remote-tracking ref at snapshot time | live tree: uncommitted paths at snapshot time (excluded) |
|---|---|---|---|---|
| aitasks | `7f1d0614a333c14f0130789c8a22e2233e6d9db0` | `0e2912cb858e783a5b5dde41700dd3507ef21a55` | no (local commit) | 0 |
| aitasks_go | `e0e3862be98a0fc2d8d977f4dfa42db20104660f` | `b31e28d45fe14f8913c10de783fa8be55a387844` | yes (`origin/main`) | 3 |
| aitasks_mobile | `75f4543fb70e90baa8661404505017887d3602c1` | `e07c7fec041e2146975f57045614b26223bcafed` | yes (`origin/master`) | 10 |
| thinking_app | `33b7fcd4923df066b4f7d7753dafbd4d22900cd8` | `963783fabd189d6a2c5cc8d642683445acb737fd` | no (local commit) | 4 |
| thinking_backend | `e9a371524f4b7d429b1b6f9b53ea71c2ad338156` | `e4a5aa561bb575fa022f493dd85bef4dc8fe8f36` | yes (`origin/dev`) | 0 |
| timexchange | `c60e7e05a46550034197b0051ae851eb193a1764` | `a445b0527fe5a22ab2fb866154c7ff5c97f3d2e8` | yes (`origin/main`) | 0 |

**Rebuilding an input:** `git clone <repo> x && git -C x checkout --detach <commit>`, then rerun the verb with that path (`realrepo --repo x --name <n> --input-label`, `tsdiff --repos <n>=x,…`, `bench --aitasks x --siblings <n>=x,…`). A commit marked "no (local commit)" was not on any remote-tracking ref when it was snapshotted: it is rebuildable from the local clone that holds it, and from anywhere once it is pushed.

**What is excluded:** the uncommitted edits counted in the last column (other sessions' work in progress) are not part of any measurement. The child-era walks (t1954_1–3: `results/realrepo_*.md`, `results/ts/`, `results/t3/`, `results/ts_differential.md`, and the sibling rows of `results/bench*.md`) read the live trees as they stood then; those inputs cannot be rebuilt, so a difference between a child-era row and a `results/t4/` row is reported as "child-era input not reconstructible", never attributed to a candidate.
