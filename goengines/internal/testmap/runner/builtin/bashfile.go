//go:build unix

package builtin

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"io"
	"os"
	"path"
	"path/filepath"
	"slices"
	"strings"
	"time"
	"unicode"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/procsup"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/runner"
	"github.com/bmatcuk/doublestar/v4"
)

// The bash-file builtin (M3.2e): each bound bash test script is one unit,
// run by its interpreter, whose exit is its verdict (accounting: unit).
const (
	bashFileName = "bash-file"
	// bashFileDefaultBind is the inventory glob when the entry has no bind:.
	bashFileDefaultBind = "**/test_*.sh"
	// bashFileGrace is SIGTERM → kill for a timed-out script, short enough
	// that a reported timeout stays within runner.TimeoutSlack.
	bashFileGrace = time.Second
)

// bashFileListMax caps the inventory's `git ls-files` output; past it the
// listing is incomplete and refused (a variable so a test can force it).
var bashFileListMax int64 = procsup.DefaultOutputMax

// bashFileDescribeDoc is the describe document: the rule and the support
// claim as comments, then the keys.
const bashFileDescribeDoc = `# bash-file (M3.2e): one bash test script per unit.
# inventory: one unit per git-visible regular file (git ls-files --cached
#   --others --exclude-standard, in the runner cwd) whose root-relative path
#   matches the entry's bind: (default **/test_*.sh). Deleted tracked files,
#   symbolic links and directories are not units. No case accounting.
# run: <command: | bash> ./<cwd-relative path>, in the cwd, one supervised
#   process per unit under timeout_s; its whole process tree is killed and
#   proven gone after every unit. Exit 0 -> pass; non-zero or a signal ->
#   fail; over timeout_s -> timeout.
# a pass proves: the script exited 0 within its bound under that
#   interpreter. Not an assertion count, not coverage.
# logs: unit-<n>.stdout / unit-<n>.stderr in the invocation's report
#   directory, <n> the unit's manifest position.
# supported: GNU bash >= 4.4 on linux. darwin and bash 3.2 are pending.
unit: file
accounting: unit
discovery: inventory
timeouts: per_unit
`

func bashFileAdapter() Adapter {
	return Adapter{Name: bashFileName, Describe: bashFileDescribe, List: bashFileList, Run: bashFileRun}
}

func bashFileDescribe(*Env) ([]byte, error) { return []byte(bashFileDescribeDoc), nil }

// bashFileCwd is the entry's cwd relative to the root ("" for the root) and
// its absolute directory.
func bashFileCwd(e *Env, en runner.Entry) (rel, dir string) {
	if en.Cwd != "" && en.Cwd != "." {
		rel = en.Cwd
	}
	return rel, filepath.Join(e.Root, filepath.FromSlash(rel))
}

// bashFileList writes one `<root-relative path>\tfile\t<cwd-relative path>`
// row per inventoried script. The inventory is git's, run supervised so it
// is contained and carries the recursion marker; anything short of a clean,
// complete listing is an error, never a partial list.
func bashFileList(ctx context.Context, e *Env, w io.Writer) error {
	en, err := e.Entry()
	if err != nil {
		return err
	}
	cwd, dir := bashFileCwd(e, en)
	bind := en.Bind
	if len(bind) == 0 {
		bind = []string{bashFileDefaultBind}
	}
	tmp, err := os.MkdirTemp("", "ait-bashfile-")
	if err != nil {
		return err
	}
	defer os.RemoveAll(tmp)
	out, errf := filepath.Join(tmp, "ls.out"), filepath.Join(tmp, "ls.err")
	rr := e.Supervise(ctx, procsup.RunSpec{Path: "git", Args: []string{"ls-files", "-z", "--cached", "--others", "--exclude-standard"},
		Dir: dir, Env: gitx.Env(), Stdout: out, Stderr: errf, OutputMax: bashFileListMax,
		Timeout: DiscoveryBound(), Grace: bashFileGrace})
	stderr, _ := os.ReadFile(errf)
	if err := toolFailure(rr); err != nil {
		return fmt.Errorf("git ls-files: %v%s", err, firstLine(stderr))
	}
	switch {
	case rr.Truncated:
		return fmt.Errorf("git ls-files: output truncated at %d bytes", bashFileListMax)
	case rr.Exit != 0:
		return fmt.Errorf("git ls-files: exit %d%s", rr.Exit, firstLine(stderr))
	case len(stderr) > 0:
		// git exits 0 when it cannot read a directory and says so only on
		// stderr: a listing with a warning may be incomplete (gitx's rule).
		return fmt.Errorf("git ls-files: incomplete listing%s", firstLine(stderr))
	}
	data, err := os.ReadFile(out)
	if err != nil {
		return err
	}
	var files []string
	for rec := range bytes.SplitSeq(data, []byte{0}) {
		if len(rec) > 0 {
			files = append(files, string(rec))
		}
	}
	slices.Sort(files)
	var rows strings.Builder
	for _, p := range slices.Compact(files) {
		rel := path.Join(cwd, p)
		if !bound(bind, rel) {
			continue
		}
		if fi, err := os.Lstat(filepath.Join(dir, filepath.FromSlash(p))); err != nil || !fi.Mode().IsRegular() {
			continue
		}
		if _, err := registry.ParseID(rel); err != nil || strings.ContainsFunc(p, unicode.IsControl) {
			return fmt.Errorf("%q cannot be a unit id", rel)
		}
		fmt.Fprintf(&rows, "%s\tfile\t%s\n", rel, p)
	}
	_, err = io.WriteString(w, rows.String())
	return err
}

func bound(globs []string, rel string) bool {
	for _, g := range globs {
		if ok, _ := doublestar.Match(g, rel); ok {
			return true
		}
	}
	return false
}

// toolFailure is a supervised run that says nothing about the tool: it never
// started, its containment is not proven, or it was stopped.
func toolFailure(rr procsup.RunResult) error {
	switch {
	case rr.StartErr != nil:
		return fmt.Errorf("start: %v", rr.StartErr)
	case rr.SupervisorDied:
		return fmt.Errorf("supervisor died: %s", rr.Detail)
	case rr.Cleanup != nil:
		return fmt.Errorf("cleanup: %v", rr.Cleanup)
	case rr.Containment != procsup.Supervisor:
		return fmt.Errorf("containment %q", rr.Containment)
	case rr.Cancelled:
		return errors.New("cancelled")
	case rr.TimedOut:
		return errors.New("timed out")
	case rr.OutputErr != nil:
		return fmt.Errorf("output: %v", rr.OutputErr)
	}
	return nil
}

func firstLine(b []byte) string {
	s, _, _ := strings.Cut(strings.TrimSpace(string(b)), "\n")
	if s == "" {
		return ""
	}
	return ": " + s
}

// bashFileRun runs each unit as `<command: | bash> ./<lowering>` in the cwd,
// one supervised process per unit under its timeout_s, and writes a start
// row then a result row for it. A run whose containment is not proven ends
// the invocation (exit 3): the units after it are left to the engine.
func bashFileRun(ctx context.Context, e *Env, m *runner.Manifest, res *Results) int {
	argv := []string{"bash"}
	if e.Command != "" {
		var err error
		if argv, err = SplitCommand(e.Command); err != nil {
			fmt.Fprintln(os.Stderr, "BASHFILE_ERROR:command:"+oneLine(err.Error()))
			return lineproto.ExitUsage
		}
	}
	en, err := e.Entry()
	if err != nil || m.ReportDir == "" {
		fmt.Fprintf(os.Stderr, "BASHFILE_ERROR:setup:%v report_dir=%q\n", err, m.ReportDir)
		return lineproto.ExitFramework
	}
	cwd, dir := bashFileCwd(e, en)
	if len(m.Units) == 0 {
		return lineproto.ExitNothingRan
	}
	code := lineproto.ExitOK
	for i, u := range m.Units {
		if err := bashFileUnitCheck(cwd, u); err != nil {
			if res.Row(u.ID, runner.StatusError, 0, "protocol:"+oneLine(err.Error())) != nil {
				return lineproto.ExitFramework
			}
			code = lineproto.ExitFail
			continue
		}
		if res.Start(u.ID) != nil {
			return lineproto.ExitFramework
		}
		log := filepath.Join(m.ReportDir, fmt.Sprintf("unit-%04d", i))
		t0 := time.Now()
		// The operand is ./<path>: a name starting with "-" would otherwise
		// be read as interpreter options (`bash --version` exits 0 without
		// running the file).
		rr := e.Supervise(ctx, procsup.RunSpec{Path: argv[0], Args: append(slices.Clone(argv[1:]), "./"+u.Lowering), Dir: dir,
			Stdout: log + ".stdout", Stderr: log + ".stderr",
			Timeout: time.Duration(u.TimeoutS * float64(time.Second)), Grace: bashFileGrace})
		ms := time.Since(t0).Milliseconds()
		if rr.StartErr != nil || rr.SupervisorDied || rr.Cleanup != nil || rr.Cancelled || rr.Containment != procsup.Supervisor {
			fmt.Fprintf(os.Stderr, "BASHFILE_ERROR:%s|%s\n", u.ID, oneLine(toolFailure(rr).Error()))
			return lineproto.ExitFramework
		}
		status, msg := runner.StatusPass, ""
		switch {
		case rr.TimedOut:
			status, msg = runner.StatusTimeout, fmt.Sprintf("timeout after %gs", u.TimeoutS)
		case rr.Exit == 0:
		case rr.Signal != "":
			status, msg = runner.StatusFail, "signal "+rr.Signal
		default:
			status, msg = runner.StatusFail, fmt.Sprintf("exit %d", rr.Exit)
		}
		// The log is not the evidence (the exit is), but its loss is said.
		switch {
		case rr.OutputErr != nil:
			msg = strings.TrimPrefix(msg+"; log incomplete: "+oneLine(rr.OutputErr.Error()), "; ")
		case rr.Truncated:
			msg = strings.TrimPrefix(msg+"; log truncated", "; ")
		}
		if res.Row(u.ID, status, ms, msg) != nil {
			return lineproto.ExitFramework
		}
		if status != runner.StatusPass {
			code = lineproto.ExitFail
		}
	}
	return code
}

// bashFileUnitCheck refuses a manifest unit whose lowering is not the
// cwd-relative path of its id, or whose bound is not positive.
func bashFileUnitCheck(cwd string, u runner.ManifestUnit) error {
	if err := registry.CheckPath(u.Lowering); err != nil {
		return fmt.Errorf("lowering %q: %v", u.Lowering, err)
	}
	if path.Join(cwd, u.Lowering) != u.ID {
		return fmt.Errorf("lowering %q is not the cwd-relative path of %s", u.Lowering, u.ID)
	}
	if !(u.TimeoutS > 0) {
		return fmt.Errorf("timeout_s %g", u.TimeoutS)
	}
	return nil
}
