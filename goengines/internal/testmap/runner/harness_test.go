package runner

import (
	"context"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/fixture"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

var bg = context.Background()

// newRepo is a fixture repository with a registry, the engine's state
// directory ignored, and the given files, committed.
func newRepo(t *testing.T, files map[string]string) *fixture.Repo {
	t.Helper()
	r := fixture.New(t)
	all := map[string]string{
		registry.ConfigPath: "contract: 1\n",
		".gitignore":        StateDir + "/\n",
	}
	for k, v := range files {
		all[k] = v
	}
	for p, c := range all {
		r.Write(t, p, c)
	}
	r.Commit(t, "1", "test", "fixture")
	return r
}

// spec describes one fixture runner script.
type spec struct {
	describe string // describe output (YAML)
	list     string // list rows, `<id> <kind> <lowering> [<artifact>]` joined by '\t' per line ("|" is replaced by a tab)
	run      string // bash run body; $M manifest, $R results, $IDS manifest ids (one per line), $D state dir of the test
}

// script renders a runner script. In the run body:
//
//	row <id> <status> [<duration_ms>] [<parent>]   append a result row
//	start <id>                                    append a start row
func script(s spec, stateDir string) string {
	var list strings.Builder
	for _, l := range strings.Split(strings.TrimSpace(s.list), "\n") {
		if l = strings.TrimSpace(l); l != "" {
			list.WriteString(strings.ReplaceAll(l, "|", "\t") + "\n")
		}
	}
	return "#!/usr/bin/env bash\nset -u\nD=" + strconv.Quote(stateDir) + "\n" +
		"case \"$1\" in\n" +
		"describe) cat <<'DESC'\n" + s.describe + "\nDESC\n;;\n" +
		listArm(list.String()) +
		"run)\n" +
		"M=\"$3\"\n" +
		"R=$(sed -n 's/^  \"results\": \"\\(.*\\)\",$/\\1/p' \"$M\")\n" +
		"IDS=$(sed -n 's/^      \"id\": \"\\(.*\\)\",$/\\1/p' \"$M\")\n" +
		"row() { local p=''; [ -n \"${4:-}\" ] && p=\",\\\"parent\\\":\\\"$4\\\"\"; printf '{\"id\":\"%s\",\"status\":\"%s\",\"duration_ms\":%s%s}\\n' \"$1\" \"$2\" \"${3:-1}\" \"$p\" >> \"$R\"; }\n" +
		"start() { printf '{\"id\":\"%s\",\"event\":\"start\"}\\n' \"$1\" >> \"$R\"; }\n" +
		s.run + "\n;;\n" +
		"*) exit 64;;\nesac\n"
}

// listArm prints the rows verbatim; no rows prints nothing at all.
func listArm(rows string) string {
	if rows == "" {
		return "list) : ;;\n"
	}
	return "list) cat <<'LIST'\n" + strings.TrimSuffix(rows, "\n") + "\nLIST\n;;\n"
}

// put writes an executable runner script at aitestmap/runners/<name>.sh.
func put(t *testing.T, r *fixture.Repo, name string, s spec) {
	t.Helper()
	p := RunnersDir + "/" + name + ".sh"
	r.Write(t, p, script(s, stateOf(t, r)))
	if err := os.Chmod(filepath.Join(r.Dir, filepath.FromSlash(p)), 0o755); err != nil {
		t.Fatal(err)
	}
}

// stateOf is a per-test scratch directory outside the repository (pid files,
// counters) so writing it never dirties the worktree.
func stateOf(t *testing.T, r *fixture.Repo) string {
	t.Helper()
	d := filepath.Join(filepath.Dir(r.Dir), filepath.Base(r.Dir)+".state")
	if err := os.MkdirAll(d, 0o755); err != nil {
		t.Fatal(err)
	}
	return d
}

// runners writes aitestmap/runners.yaml.
func runners(t *testing.T, r *fixture.Repo, yaml string) {
	t.Helper()
	r.Write(t, RunnersPath, "contract: 1\n"+yaml)
}

// commitAll commits the fixture's current state.
func commitAll(t *testing.T, r *fixture.Repo) { r.Commit(t, "1", "test", "runners") }

// runAll runs every unit under a fixed run id.
func runAll(t *testing.T, r *fixture.Repo) *RunReport {
	t.Helper()
	rep, err := Run(bg, r.Dir, Options{All: true, RunID: "t-" + strconv.Itoa(len(t.Name()))})
	if err != nil {
		t.Fatalf("Run: %v", err)
	}
	return rep
}

// statuses maps each top-level result id to its status.
func statuses(rep *RunReport) map[string]string {
	m := map[string]string{}
	for _, res := range rep.Results {
		if !res.Child {
			m[res.ID.String()] = res.Status
		}
	}
	return m
}

// withHooks swaps the hook list for the test.
func withHooks(t *testing.T) {
	t.Helper()
	hookMu.Lock()
	old := hooks
	hooks = nil
	hookMu.Unlock()
	t.Cleanup(func() { hookMu.Lock(); hooks = old; hookMu.Unlock() })
}

// withBuiltin registers a builtin for the test only.
func withBuiltin(t *testing.T, name string) {
	t.Helper()
	RegisterBuiltin(name)
	t.Cleanup(func() { builtinMu.Lock(); delete(builtins, name); builtinMu.Unlock() })
}

// withExecutor swaps the plan executor for the test only.
func withExecutor(t *testing.T, e Executor) {
	t.Helper()
	seamMu.Lock()
	old := executor
	executor = e
	seamMu.Unlock()
	t.Cleanup(func() { seamMu.Lock(); executor = old; seamMu.Unlock() })
}

// readPid reads a pid file the fixture script wrote.
func readPid(t *testing.T, path string) int {
	t.Helper()
	b, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	pid, err := strconv.Atoi(strings.TrimSpace(string(b)))
	if err != nil {
		t.Fatal(err)
	}
	return pid
}

// noAnns is an annotation source with no annotations.
type noAnns struct{}

func (noAnns) Annotations(context.Context, string) ([]registry.FileAnnotations, error) {
	return nil, nil
}
