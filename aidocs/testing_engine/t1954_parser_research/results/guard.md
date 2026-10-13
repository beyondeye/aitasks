# Seam guard (t1954_1)

`seam.patch` must be behaviour-neutral: the baseline matrix built against the UNPATCHED snapshot (`-tags unpatched -modfile=go.unpatched.mod`) and against the patched snapshot with both hooks nil must be byte-identical, apart from the identity line (whose commit and tree must agree). Rerun: `go run ./cmd/t1954 guard`.

- unpatched: `baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=none snapshot=unpatched`
- patched:   `baseline: commit=f096db065a7249836c9a82f9d05bbd20fc43b961 tree=200bd2130a1dc45f27bebdec16392da76bfc018b seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched`
- compared: 30546 bytes

**GUARD:PASS|baseline matrices byte-identical (30546 bytes) excluding the identity line**

Negative control (run by hand in a scratch copy, 2026-10-12): a mutant unpatched snapshot whose Go lexer drops the package anchor (`c.Package = 0`) makes the guard report `GUARD:FAIL|baseline matrices differ …` — the guard can detect a behaviour difference.
