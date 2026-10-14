# Seam guard (t1954_1)

`seam.patch` must be behaviour-neutral: the baseline matrix built against the UNPATCHED snapshot (`-tags unpatched -modfile=go.unpatched.mod`) and against the patched snapshot with both hooks nil must be byte-identical, apart from the identity line (whose commit and tree must agree). Rerun: `go run ./cmd/t1954 guard`.

- unpatched: `baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=none snapshot=unpatched`
- patched:   `baseline: commit=3d1a2b628fc07f75b279c0c125ed4705316c9368 tree=2c26f17fe33a425b88af7ac7e20d731e3499ace9 seam_sha256=9a8013a789e79117539ac3e7b2b1dfa924376b301fe6d9628f579ccc127d0296 snapshot=patched`
- compared: 31217 bytes

**GUARD:PASS|baseline matrices byte-identical (31217 bytes) excluding the identity line**

Negative control (run by hand in a scratch copy, 2026-10-12): a mutant unpatched snapshot whose Go lexer drops the package anchor (`c.Package = 0`) makes the guard report `GUARD:FAIL|baseline matrices differ …` — the guard can detect a behaviour difference.
