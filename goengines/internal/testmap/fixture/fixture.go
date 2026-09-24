// Package fixture builds throwaway git repositories in t.TempDir() carrying
// synthetic aitasks histories — commits whose messages end in `(t<id>)`, the
// form the framework's commit convention writes. Every engine test that
// needs a repository starts here; a submodule that needs a new repository
// shape (a detect shape, an opaque-scanner branch, a packet language) adds a
// constructor that builds on Repo.
//
// Histories are deterministic: identity and dates are fixed, so the same
// sequence of calls yields the same commit ids on every run.
package fixture

import (
	"context"
	"fmt"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"testing"
	"time"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
)

// Epoch is the author/committer date of the first fixture commit; each later
// commit is one minute after the previous one.
var Epoch = time.Date(2026, 1, 1, 0, 0, 0, 0, time.UTC)

// Identity is the author and committer of every fixture commit.
const (
	IdentityName  = "Fixture"
	IdentityEmail = "fixture@example.invalid"
)

// isolation is appended to every fixture git invocation: it pins the identity
// (overriding any inherited GIT_AUTHOR_*/GIT_COMMITTER_*) and cuts off the
// user's and the system's git configuration, and with them any global
// excludesFile, attributes, templates or hooks that would change what a
// fixture commits. Per-repository configuration set by New still applies.
func isolation(configHome string) []string {
	return []string{
		"GIT_CONFIG_GLOBAL=/dev/null",
		"GIT_CONFIG_NOSYSTEM=1",
		"XDG_CONFIG_HOME=" + configHome, // default core.excludesFile / attributesFile live here
		"GIT_TEMPLATE_DIR=",
		"GIT_AUTHOR_NAME=" + IdentityName, "GIT_AUTHOR_EMAIL=" + IdentityEmail,
		"GIT_COMMITTER_NAME=" + IdentityName, "GIT_COMMITTER_EMAIL=" + IdentityEmail,
	}
}

// Repo is a fixture repository.
type Repo struct {
	Dir    string
	Git    gitx.Repo
	format string
	ticks  int
	env    []string
}

type options struct{ format string }

// Option configures New.
type Option func(*options)

// SHA256 initialises the repository with --object-format=sha256.
func SHA256() Option { return func(o *options) { o.format = "sha256" } }

// New initialises an empty repository (branch main) in a fresh t.TempDir().
func New(t testing.TB, opts ...Option) *Repo {
	t.Helper()
	o := options{format: "sha1"}
	for _, opt := range opts {
		opt(&o)
	}
	r := &Repo{Dir: t.TempDir(), format: o.format}
	r.Git = gitx.Repo{Dir: r.Dir}
	r.env = isolation(t.TempDir())
	r.git(t, "init", "-q", "--template=", "-b", "main", "--object-format="+o.format)
	for _, kv := range [][2]string{
		{"user.name", IdentityName}, {"user.email", IdentityEmail},
		{"commit.gpgsign", "false"}, {"tag.gpgsign", "false"},
		{"core.hooksPath", "/dev/null"}, {"core.autocrlf", "false"},
		{"core.excludesFile", "/dev/null"}, {"core.attributesFile", "/dev/null"},
	} {
		r.git(t, "config", kv[0], kv[1])
	}
	return r
}

// ObjectFormat is the format New initialised the repository with.
func (r *Repo) ObjectFormat() string { return r.format }

// Write creates or overwrites a working-tree file, creating parent
// directories. path is slash-separated and repository-relative.
func (r *Repo) Write(t testing.TB, path, content string) {
	t.Helper()
	full := filepath.Join(r.Dir, filepath.FromSlash(path))
	if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(full, []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

// Remove deletes a working-tree file.
func (r *Repo) Remove(t testing.TB, path string) {
	t.Helper()
	if err := os.Remove(filepath.Join(r.Dir, filepath.FromSlash(path))); err != nil {
		t.Fatal(err)
	}
}

// Message is the commit message the framework's convention writes:
// `<type>: <desc> (t<task>)`. task is a parent (`12`) or child (`12_3`) id.
func Message(task, typ, desc string) string {
	return fmt.Sprintf("%s: %s (t%s)", typ, desc, task)
}

// Commit stages every change in the working tree and commits it with
// Message(task, typ, desc), returning the new commit id.
func (r *Repo) Commit(t testing.TB, task, typ, desc string) string {
	t.Helper()
	return r.CommitMessage(t, Message(task, typ, desc))
}

// CommitMessage stages every change and commits with a verbatim message (for
// commits that deliberately carry no task id). Empty commits are allowed.
func (r *Repo) CommitMessage(t testing.TB, msg string) string {
	t.Helper()
	r.git(t, "add", "-A")
	when := Epoch.Add(time.Duration(r.ticks) * time.Minute).Format(time.RFC3339)
	r.ticks++
	r.gitEnv(t, []string{"GIT_AUTHOR_DATE=" + when, "GIT_COMMITTER_DATE=" + when},
		"commit", "-q", "--allow-empty", "--no-verify", "-m", msg)
	return r.Head(t)
}

// Commit is one step of a History: its files are written (an empty value
// deletes the file) and committed under Message(Task, Type, Desc).
type Commit struct {
	Task  string
	Type  string
	Desc  string
	Files map[string]string
}

// History applies each step in order and returns the commit ids.
func (r *Repo) History(t testing.TB, steps []Commit) []string {
	t.Helper()
	var ids []string
	for _, c := range steps {
		for path, content := range c.Files {
			if content == "" {
				r.Remove(t, path)
				continue
			}
			r.Write(t, path, content)
		}
		typ := c.Type
		if typ == "" {
			typ = "feature"
		}
		ids = append(ids, r.Commit(t, c.Task, typ, c.Desc))
	}
	return ids
}

// Head returns the id of HEAD.
func (r *Repo) Head(t testing.TB) string {
	t.Helper()
	return strings.TrimSpace(r.git(t, "rev-parse", "HEAD"))
}

// Run is the escape hatch: any git command in the fixture, fatal on failure.
func (r *Repo) Run(t testing.TB, args ...string) string {
	t.Helper()
	return r.git(t, args...)
}

func (r *Repo) git(t testing.TB, args ...string) string {
	t.Helper()
	return r.gitEnv(t, nil, args...)
}

// gitEnv runs git in the fixture with gitx's scrubbed environment, the
// isolation entries, then env. Fixture writes (add, commit, config) happen
// here, in test-only code; gitx itself exposes no write verb.
func (r *Repo) gitEnv(t testing.TB, env []string, args ...string) string {
	t.Helper()
	out, err := r.Git.RunEnv(context.Background(), append(slices.Clone(r.env), env...), args...)
	if err != nil {
		t.Fatalf("fixture: %v", err)
	}
	return string(out)
}
