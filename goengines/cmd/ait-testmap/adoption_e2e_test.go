package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
)

// [e2e_adoption_lifecycle] M2.6 end to end through the real verb table, the
// real annotation source and the real runner repository: a seed, an agent's
// first stamp shadowing it and adopting the edge, an automated refresh, a
// person's re-stamp turning it into a reviewed edge, and an orphan — with
// `check` judging the live state at every step.
func TestAdoptionLifecycleEndToEnd(t *testing.T) {
	t.Setenv("XDG_CACHE_HOME", t.TempDir())
	t.Setenv("AIT_AGENT_STRING", "")
	r := fixture.New(t)
	files := map[string]string{
		registry.ConfigPath: "contract: 1\nbootstrap_until: 2099-01-01\n",
		runner.RunnersPath:  "contract: 1\nrunners:\n  - name: shell\n    bind: ['tests/*.sh']\n    timeout_s: 5\n    batch_timeout_s: 10\n",
		runner.RunnersDir + "/shell.sh": "#!/usr/bin/env bash\ncase \"$1\" in\n" +
			"describe) printf 'unit: file\\ntimeouts: batch\\n';;\n" +
			"list) printf 'tests/t.sh\\tfile\\tt\\ntests/u.sh\\tfile\\tu\\n';;\n" +
			"esac\n",
		"tests/t.sh":        "#!/usr/bin/env bash\necho t\n",
		"tests/u.sh":        "#!/usr/bin/env bash\necho u\n",
		"src/a.sh":          "a\n",
		"src/b.sh":          "b\n",
		registry.SeededPath: "contract: 1\nseeds:\n  - {test: tests/t.sh, covers: src/a.sh, origin: [static:invocation], confidence: 0.9, proposed_at: 2026-10-02}\n",
	}
	for p, c := range files {
		r.Write(t, p, c)
	}
	if err := os.Chmod(filepath.Join(r.Dir, runner.RunnersDir, "shell.sh"), 0o755); err != nil {
		t.Fatal(err)
	}
	r.Commit(t, "1", "test", "fixture")
	t.Chdir(r.Dir)

	run := func(step string, wantCode int, args ...string) string {
		t.Helper()
		code, out, errs := call(args...)
		if code != wantCode || errs != "" {
			t.Fatalf("%s: %v: exit %d (want %d)\n%s\nstderr %q", step, args, code, wantCode, out, errs)
		}
		return out
	}
	has := func(step, out string, want ...string) {
		t.Helper()
		for _, w := range want {
			if !strings.Contains(out, w) {
				t.Fatalf("%s: missing %q in\n%s", step, w, out)
			}
		}
	}
	rows := func() []registry.AdoptedRow { return adoptedRows(t, r) }

	run("scan", 0, "scan", "--apply")
	has("seeded", run("check", 0, "check"), "SEEDED:1\nADOPTED:0|human 0|agent 0|auto 0\nCHECK:pass|")

	t.Setenv("AIT_AGENT_STRING", "x")
	has("agent annotate", run("agent annotate", 0, "annotate", "tests/t.sh", "src/a.sh"),
		"WROTE:"+registry.AdoptedPath+"\nWROTE:tests/t.sh\n")
	t.Setenv("AIT_AGENT_STRING", "")
	has("adopted", run("check", 0, "check"),
		"SEED_SHADOWED:tests/t.sh|src/a.sh\n", "SEEDED:0\nADOPTED:1|human 0|agent 1|auto 0\nCHECK:pass|")
	first := rows()
	if len(first) != 1 || first[0].By != "agent:x" {
		t.Fatalf("rows %+v", first)
	}

	r.Write(t, "src/a.sh", "a changed\n")
	run("auto verify", 0, "verify", "--by", "auto", "tests/t.sh")
	if got := rows(); len(got) != 1 || got[0].By != "agent:x" || got[0].Stamp == first[0].Stamp {
		t.Fatalf("refresh: %+v (was %s)", got, first[0].Stamp)
	}

	run("human verify", 0, "verify", "--by", "human:p@example.invalid", "tests/t.sh")
	if got := rows(); len(got) != 0 {
		t.Fatalf("a person's verify must leave a reviewed edge: %+v", got)
	}
	has("reviewed", run("check", 0, "check"), "SEEDED:0\nADOPTED:0|human 0|agent 0|auto 0\nCHECK:pass|")

	t.Setenv("AIT_AGENT_STRING", "x")
	run("second agent edge", 0, "annotate", "tests/u.sh", "src/b.sh")
	t.Setenv("AIT_AGENT_STRING", "")
	r.Write(t, "tests/u.sh", "#!/usr/bin/env bash\necho u\n") // the covers line removed by hand
	has("orphan", run("check", 0, "check"), "ADOPTED_ORPHAN:tests/u.sh|src/b.sh\n", "ADOPTED:0|human 0|agent 0|auto 0\nCHECK:pass|")
}
