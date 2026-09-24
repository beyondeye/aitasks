// Package gitx is the engine's only door to git: read-only queries run as
// `git -C <dir> …` subprocesses with a scrubbed environment, plus blob
// digests computed in-process. It has no verb that writes a ref, the index or
// the working tree — the engine never commits (Invariant 5).
package gitx

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"strings"
)

// scrubbed are inherited variables that would redirect git away from the
// repository named by -C (a hook environment sets several of them).
var scrubbed = []string{
	"GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY",
	"GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_COMMON_DIR", "GIT_NAMESPACE",
	"GIT_CEILING_DIRECTORIES", "GIT_DISCOVERY_ACROSS_FILESYSTEM", "GIT_PREFIX",
	"GIT_CONFIG", "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT",
	"LC_ALL", "LANG", "GIT_TERMINAL_PROMPT",
}

// Env returns the environment git subprocesses run with: the process
// environment minus the redirecting variables, plus LC_ALL=C and
// GIT_TERMINAL_PROMPT=0. extra entries are appended last.
func Env(extra ...string) []string {
	var env []string
	for _, kv := range os.Environ() {
		name, _, _ := strings.Cut(kv, "=")
		if isScrubbed(name) {
			continue
		}
		env = append(env, kv)
	}
	env = append(env, "LC_ALL=C", "GIT_TERMINAL_PROMPT=0")
	return append(env, extra...)
}

func isScrubbed(name string) bool {
	if strings.HasPrefix(name, "GIT_CONFIG_KEY_") || strings.HasPrefix(name, "GIT_CONFIG_VALUE_") {
		return true
	}
	for _, s := range scrubbed {
		if name == s {
			return true
		}
	}
	return false
}

// Error is a git invocation that exited non-zero.
type Error struct {
	Args     []string
	ExitCode int
	Stderr   string
}

func (e *Error) Error() string {
	return fmt.Sprintf("git %s: exit %d: %s", strings.Join(e.Args, " "), e.ExitCode, strings.TrimSpace(e.Stderr))
}

// Repo is a git working tree or repository directory.
type Repo struct {
	Dir string
}

// Run executes `git -C <dir> args…` and returns its stdout. A non-zero exit
// is an *Error carrying the exit code and stderr.
func (r Repo) Run(ctx context.Context, args ...string) ([]byte, error) {
	return r.RunEnv(ctx, nil, args...)
}

// RunEnv is Run with extra environment entries (e.g. GIT_*_DATE).
func (r Repo) RunEnv(ctx context.Context, env []string, args ...string) ([]byte, error) {
	cmd := exec.CommandContext(ctx, "git", append([]string{"-C", r.Dir}, args...)...)
	cmd.Env = Env(env...)
	var out, errb bytes.Buffer
	cmd.Stdout = &out
	cmd.Stderr = &errb
	if err := cmd.Run(); err != nil {
		var ee *exec.ExitError
		if errors.As(err, &ee) {
			return out.Bytes(), &Error{Args: args, ExitCode: ee.ExitCode(), Stderr: errb.String()}
		}
		return out.Bytes(), err
	}
	return out.Bytes(), nil
}

// RevParse resolves rev to a full object id.
func (r Repo) RevParse(ctx context.Context, rev string) (string, error) {
	out, err := r.Run(ctx, "rev-parse", "--verify", "--end-of-options", rev+"^{object}")
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// ObjectFormat returns the repository's object format, "sha1" or "sha256".
func (r Repo) ObjectFormat(ctx context.Context) (string, error) {
	out, err := r.Run(ctx, "rev-parse", "--show-object-format")
	if err != nil {
		return "", err
	}
	return strings.TrimSpace(string(out)), nil
}

// IsAncestor reports whether a is an ancestor of (or equal to) b, via
// `git merge-base --is-ancestor`. Exit 1 is "no"; any other failure (an
// unknown revision included) is an error, never a "no".
func (r Repo) IsAncestor(ctx context.Context, a, b string) (bool, error) {
	_, err := r.Run(ctx, "merge-base", "--is-ancestor", a, b)
	if err == nil {
		return true, nil
	}
	var ge *Error
	if errors.As(err, &ge) && ge.ExitCode == 1 {
		return false, nil
	}
	return false, err
}
