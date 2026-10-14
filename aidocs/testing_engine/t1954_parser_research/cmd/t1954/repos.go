package main

import (
	"fmt"
	"os/exec"
	"path/filepath"
	"strings"
)

// A repository a walk reads. A bare entry is a registered project name,
// resolved through `ait projects resolve` to its live checkout (the
// t1954_1–3 behaviour). A `name=path` entry names a directory explicitly:
// t1954_4 passes temporary checkouts of recorded commits, so a walk's input
// can be rebuilt from its commit, and labels it with that commit.
type repoInput struct {
	Name  string // the registered or given name
	Path  string
	Label string // Name for a registered entry; Name@<sha12>[ (dirty: N paths)] for an explicit path
}

// parseRepoEntry splits a `name=path` entry; a bare entry is a name only.
func parseRepoEntry(entry string) (name, path string, explicit bool) {
	if n, p, ok := strings.Cut(entry, "="); ok {
		return strings.TrimSpace(n), strings.TrimSpace(p), true
	}
	return strings.TrimSpace(entry), "", false
}

// resolveRepo resolves one entry. top is the aitasks checkout whose `ait`
// resolves registered names.
func resolveRepo(top, entry string) (repoInput, error) {
	name, path, explicit := parseRepoEntry(entry)
	if name == "" {
		return repoInput{}, fmt.Errorf("empty repository name in %q", entry)
	}
	if explicit {
		if path == "" {
			return repoInput{Name: name}, fmt.Errorf("%s: empty path", name)
		}
		return repoInput{Name: name, Path: path, Label: name + describeCheckout(path)}, nil
	}
	res, err := exec.Command(filepath.Join(top, "ait"), "projects", "resolve", name).Output()
	p := strings.TrimPrefix(strings.TrimSpace(string(res)), "RESOLVED:")
	if err != nil || p == "" {
		return repoInput{Name: name}, fmt.Errorf("%s: not resolved", name)
	}
	return repoInput{Name: name, Path: p, Label: name}, nil
}

// describeCheckout is "@<sha12>" for a git checkout, with " (dirty: N paths)"
// when its working tree differs from that commit (so a label never claims a
// commit the walked bytes do not match), or " (not a git checkout)".
func describeCheckout(path string) string {
	head, err := exec.Command("git", "-C", path, "rev-parse", "HEAD").Output()
	if err != nil {
		return " (not a git checkout)"
	}
	sha := strings.TrimSpace(string(head))
	if len(sha) > 12 {
		sha = sha[:12]
	}
	st, err := exec.Command("git", "-C", path, "status", "--porcelain").Output()
	if err != nil {
		return "@" + sha + " (status unknown)"
	}
	if n := len(splitLines(string(st))); n > 0 {
		return fmt.Sprintf("@%s (dirty: %d paths)", sha, n)
	}
	return "@" + sha
}

func splitLines(s string) []string {
	var out []string
	for _, l := range strings.Split(s, "\n") {
		if strings.TrimSpace(l) != "" {
			out = append(out, l)
		}
	}
	return out
}
