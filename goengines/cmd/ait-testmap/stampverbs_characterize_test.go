package main

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// [characterize_stamp_verbs_without_provenance] The behaviour of `annotate`
// and `verify` for the actors that never create an adoption row — an
// explicit human and an unspecified actor — pinned as M2.2 shipped it, before
// M2.6 filled the post-re-stamp hook. On a repository with no `adopted.yaml`
// these actors must see exactly what they saw before: the same lines, exit
// codes, test-file bytes and hook calls, and no adoption file is written.
func TestCharacterizeStampVerbsWithoutProvenance(t *testing.T) {
	r := stampRepo(t, map[string]string{
		"src/a.sh":   "a\n",
		"src/b.sh":   "b\n",
		"tests/t.sh": "#!/bin/sh\n# header\necho\n",
		"tests/u.sh": "#!/bin/sh\n# testmap:covers src/b.sh\necho\n",
	})
	const human = "human:x@example.invalid"
	steps := []struct {
		args []string
		edit map[string]string // source edits applied before the step
		out  string            // a regexp over stdout
		file string            // the test file whose bytes are pinned after the step
		body string            // a regexp over that file
	}{
		{args: []string{"annotate", "--by", human, "tests/t.sh", "src/a.sh"},
			out:  `STAMP:tests/t.sh\|src/a.sh\|` + stampRe + `\|added\nWROTE:tests/t.sh\nSTAMPS:1\|0\|0\|0\n`,
			file: "tests/t.sh", body: `#!/bin/sh\n# header\n# testmap:covers src/a.sh @` + stampRe + `\necho\n`},
		{args: []string{"annotate", "--by", human, "tests/u.sh", "src/b.sh"},
			out:  `STAMP:tests/u.sh\|src/b.sh\|` + stampRe + `\|restamped\nWROTE:tests/u.sh\nSTAMPS:0\|1\|0\|0\n`,
			file: "tests/u.sh", body: `#!/bin/sh\n# testmap:covers src/b.sh @` + stampRe + `\necho\n`},
		{args: []string{"annotate", "tests/t.sh", "src/a.sh"}, edit: map[string]string{"src/a.sh": "a2\n"},
			out:  `STAMP:tests/t.sh\|src/a.sh\|` + stampRe + `\|restamped\nWROTE:tests/t.sh\nSTAMPS:0\|1\|0\|0\n`,
			file: "tests/t.sh", body: `#!/bin/sh\n# header\n# testmap:covers src/a.sh @` + stampRe + `\necho\n`},
		{args: []string{"verify", "--by", human, "tests/t.sh"},
			out: `STAMP:tests/t.sh\|src/a.sh\|` + stampRe + `\|current\nSTAMPS:0\|0\|1\|0\n`},
		{args: []string{"verify", "tests/t.sh", "tests/u.sh"}, edit: map[string]string{"src/a.sh": "a3\n"},
			out: `STAMP:tests/t.sh\|src/a.sh\|` + stampRe + `\|restamped\nSTAMP:tests/u.sh\|src/b.sh\|` + stampRe +
				`\|current\nWROTE:tests/t.sh\nSTAMPS:0\|1\|1\|0\n`},
		{args: []string{"annotate", "--json", "--by", human, "tests/t.sh", "src/a.sh"},
			out: `\{"stamps":\[\{"test":"tests/t.sh","source":"src/a.sh","stamp":"` + stampRe +
				`","state":"current"\}\],"skipped":\[\],"refused":\[\],"wrote":\[\]\}\n`},
		{args: []string{"verify", "--json", "tests/u.sh"},
			out: `\{"stamps":\[\{"test":"tests/u.sh","source":"src/b.sh","stamp":"` + stampRe +
				`","state":"current"\}\],"skipped":\[\],"refused":\[\],"wrote":\[\]\}\n`},
	}
	for _, s := range steps {
		for p, c := range s.edit {
			r.Write(t, p, c)
		}
		code, out, errs := call(s.args...)
		if code != 0 || errs != "" {
			t.Fatalf("%v: exit %d stderr %q", s.args, code, errs)
		}
		matchOut(t, s.args[0], out, s.out)
		if s.file != "" {
			data, err := os.ReadFile(filepath.Join(r.Dir, s.file))
			if err != nil {
				t.Fatal(err)
			}
			matchOut(t, s.file, string(data), s.body)
		}
	}
	want := []struct{ actor, state string }{
		{human, "added"}, {human, "restamped"}, {"", "restamped"}, {human, "current"},
		{"", "restamped"}, {human, "current"}, {"", "current"},
	}
	if len(hookCalls) != len(want) {
		t.Fatalf("hook calls %+v", hookCalls)
	}
	for i, w := range want {
		c := hookCalls[i]
		if c.actor != w.actor || len(c.edges) == 0 || string(c.edges[0].State) != w.state {
			t.Errorf("hook call %d: %+v, want %+v", i, c, w)
		}
	}
	for _, p := range []string{registry.RegistryDir + "/adopted.yaml", registry.RegistryDir + "/seeded.yaml", registry.Dir + "/onboard.yaml"} {
		if _, err := os.Stat(filepath.Join(r.Dir, p)); !os.IsNotExist(err) {
			t.Errorf("%s exists (or stat failed: %v): these actors create no adoption state", p, err)
		}
	}
}
