package gitx

import (
	"bytes"
	"context"
	"fmt"
	"strings"
)

// TreeEntry is one line of `git ls-tree`.
type TreeEntry struct {
	Mode string // e.g. 100644, 100755, 120000, 160000
	Type string // blob, tree, commit
	OID  string
	Path string // repository-relative, forward slashes
}

// LsTree lists every entry reachable from rev, recursively, with paths
// relative to the repository root. paths, when given, restrict the listing.
func (r Repo) LsTree(ctx context.Context, rev string, paths ...string) ([]TreeEntry, error) {
	args := []string{"ls-tree", "-r", "-z", "--full-tree", rev}
	if len(paths) > 0 {
		args = append(append(args, "--"), paths...)
	}
	out, err := r.Run(ctx, args...)
	if err != nil {
		return nil, err
	}
	return parseLsTree(out)
}

// parseLsTree parses `-z` output: `<mode> SP <type> SP <oid> TAB <path> NUL`.
func parseLsTree(out []byte) ([]TreeEntry, error) {
	var entries []TreeEntry
	for rec := range bytes.SplitSeq(out, []byte{0}) {
		if len(rec) == 0 {
			continue
		}
		meta, path, ok := strings.Cut(string(rec), "\t")
		if !ok {
			return nil, fmt.Errorf("gitx: malformed ls-tree record %q", rec)
		}
		f := strings.Fields(meta)
		if len(f) != 3 {
			return nil, fmt.Errorf("gitx: malformed ls-tree record %q", rec)
		}
		entries = append(entries, TreeEntry{Mode: f[0], Type: f[1], OID: f[2], Path: path})
	}
	return entries, nil
}
