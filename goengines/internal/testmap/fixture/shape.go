package fixture

import (
	"fmt"
	"strings"
	"testing"
)

// AitasksShape writes an aitasks-shaped tree into r sized to the real tree, in
// bytes and in reference density (measured 2026-10-12: 651 bash files /
// 9.5 MB with ≈21.7k path-shaped refs and ≈9.8k assignments, 644 Python
// files / 14.7 MB with ≈7k import or bootstrap statements and ≈7.9k path
// strings, 122 Go files / 0.76 MB): bash tests with the SCRIPT_DIR /
// PROJECT_DIR header and literal invocations, Python tests with a sys.path
// bootstrap, the sources they name, and a Go module — all untracked. It is the
// shape the warm-scan budgets are measured on (deps, modules).
func AitasksShape(t testing.TB, r *Repo) {
	t.Helper()
	const header = "#!/usr/bin/env bash\nset -euo pipefail\n" +
		"SCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n" +
		"PROJECT_DIR=\"$(cd \"$SCRIPT_DIR/..\" && pwd)\"\n" +
		". \"$PROJECT_DIR/tests/lib/asserts.sh\"\n"
	for i := range 300 { // sources: scripts and libraries
		var s strings.Builder
		s.WriteString("#!/usr/bin/env bash\nset -euo pipefail\nSCRIPT_DIR=\"$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\" && pwd)\"\n")
		fmt.Fprintf(&s, "source \"$SCRIPT_DIR/lib/lib%d.sh\"\n", i%40)
		for k := range 330 {
			switch {
			case k%10 == 0: // ≈33 path-shaped refs per file, as measured
				fmt.Fprintf(&s, "do_%d() { local x=\"$1\"; echo \"OUT_%d:$x\" | sed 's/a/b/' >&2; }\n", k, k)
			case k%22 == 1: // ≈15 assignments per file
				fmt.Fprintf(&s, "V_%d=\"$SCRIPT_DIR/lib/x%d\"\n", k, k)
			default:
				fmt.Fprintf(&s, "do_%d() { local x=\"$1\"; echo \"OUT_%d:$x\" >&2; }\n", k, k)
			}
		}
		r.Write(t, fmt.Sprintf(".aitask-scripts/aitask_s%d.sh", i), s.String())
	}
	for i := range 40 {
		r.Write(t, fmt.Sprintf(".aitask-scripts/lib/lib%d.sh", i), "#!/usr/bin/env bash\nlib_fn() { :; }\n")
	}
	for i := range 290 {
		var s strings.Builder
		s.WriteString("\"\"\"A library module.\"\"\"\nfrom __future__ import annotations\nimport os\nimport sys\n")
		fmt.Fprintf(&s, "from mod%d import helper\n", (i+1)%290)
		for k := range 420 {
			fmt.Fprintf(&s, "def fn_%d(x: int) -> str:\n    return f\"{x}-%d\" + os.sep\n", k, k)
		}
		r.Write(t, fmt.Sprintf(".aitask-scripts/lib/mod%d.py", i), s.String())
	}
	r.Write(t, "tests/lib/asserts.sh", "#!/usr/bin/env bash\nassert_eq() { :; }\n")
	for i := range 310 { // bash tests
		var s strings.Builder
		s.WriteString(header)
		for k := range 3 {
			fmt.Fprintf(&s, "bash \"$PROJECT_DIR/.aitask-scripts/aitask_s%d.sh\" arg\n", (i*3+k)%300)
		}
		for k := range 380 {
			if k%12 == 0 { // ≈33 path-shaped refs per file, as measured
				fmt.Fprintf(&s, "cp \"$PROJECT_DIR/tests/data/in%d.txt\" \"$TMP/out%d\"\n", k, k)
				continue
			}
			fmt.Fprintf(&s, "out=\"$(run_case --x %d 2>&1)\"; assert_eq \"ok\" \"$out\" \"case %d\" || fail=$((fail+1))\n", k, k)
		}
		r.Write(t, fmt.Sprintf("tests/test_t%d.sh", i), s.String())
	}
	for i := range 350 { // python tests
		var s strings.Builder
		s.WriteString("import sys\nimport unittest\nfrom pathlib import Path\n\n" +
			"REPO_ROOT = Path(__file__).resolve().parent.parent\n" +
			"sys.path.insert(0, str(REPO_ROOT / \".aitask-scripts\" / \"lib\"))\n")
		fmt.Fprintf(&s, "import mod%d\nfrom mod%d import fn_1\n\n", i%290, (i+7)%290)
		s.WriteString("class T(unittest.TestCase):\n")
		for k := range 400 {
			if k%40 == 0 { // ≈12 path strings and ≈11 statements per file, as measured
				fmt.Fprintf(&s, "    def test_%d(self):\n        import mod%d\n        self.assertTrue((REPO_ROOT / \"tests/data/in%d.json\").exists())\n", k, (k+i)%290, k)
				continue
			}
			fmt.Fprintf(&s, "    def test_%d(self):\n        self.assertEqual(fn_1(%d), \"%d-1\" + \"x\")\n", k, k, k)
		}
		r.Write(t, fmt.Sprintf("tests/test_p%d.py", i), s.String())
	}
	r.Write(t, "goengines/go.mod", "module m\n\ngo 1.21\n")
	for i := range 120 {
		var s strings.Builder
		fmt.Fprintf(&s, "package p%d\n\nimport (\n\t\"fmt\"\n", i%12)
		if i%12 > 0 {
			fmt.Fprintf(&s, "\n\t_ \"m/p%d\"\n", i%12-1)
		}
		s.WriteString(")\n\n")
		for k := range 80 {
			fmt.Fprintf(&s, "// F%d formats.\nfunc F%d_%d(x int) string { return fmt.Sprint(x, %d) }\n", k, i, k, k)
		}
		name := fmt.Sprintf("goengines/p%d/f%d.go", i%12, i)
		if i%3 == 0 {
			name = fmt.Sprintf("goengines/p%d/f%d_test.go", i%12, i)
		}
		r.Write(t, name, s.String())
	}
	for i := range 900 {
		r.Write(t, fmt.Sprintf("docs/d%d/page%d.md", i%30, i), "# Title\n\nText.\n")
	}
}
