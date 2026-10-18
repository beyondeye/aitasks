package annot

import (
	"context"
	"errors"
	"fmt"

	"github.com/beyondeye/aitasks/goengines/internal/gitx"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

// Source is the annotation source `scan` and `check` read
// (registry.AnnotationSource). Its universe is the repository's git-visible
// files — tracked, and untracked but not ignored — minus `exclude:`, minus any
// path through a symbolic link, restricted to the languages the grammar
// knows; it returns the files that carry at least one annotation, sorted by
// path. A file it cannot read, or whose annotations the grammar refuses, is
// an error: scan never runs on a partial map.
//
// M3.1 (runner / batch / needs), M2.4 and M2.5 extend registry.UnitAnnotation
// additively and fill the new fields in toRegistry below (named extensions).
type Source struct{}

// Annotations implements registry.AnnotationSource.
func (Source) Annotations(ctx context.Context, root string) ([]registry.FileAnnotations, error) {
	cfg, err := registry.LoadConfig(root)
	if err != nil {
		return nil, err
	}
	files, err := gitx.Repo{Dir: root}.ListFiles(ctx)
	if err != nil {
		return nil, err
	}
	r, err := openRoot(root)
	if err != nil {
		return nil, err
	}
	defer r.Close()
	var out []registry.FileAnnotations
	for _, p := range files {
		if cfg.Excluded(p) || !knownExt(p) {
			continue
		}
		data, _, err := readNoFollow(r, p)
		switch {
		case errors.Is(err, ErrMissing), errors.Is(err, ErrNotAFile):
			continue // deleted since the index, or reached through a link
		case err != nil:
			return nil, fmt.Errorf("%s: %w", p, err)
		}
		if l, ok := LangOf(p, data); !ok || !mayCarry(l, data) {
			continue
		}
		f, err := ParseFile(p, data)
		if errors.Is(err, ErrNoLeader) {
			continue
		}
		if err != nil {
			return nil, err
		}
		if f.Annotated() {
			out = append(out, toRegistry(f))
		}
	}
	return out, nil
}

// knownExt is a cheap pre-read filter: a path whose extension no language
// claims (a file without an extension may still carry a shebang).
func knownExt(p string) bool {
	_, ok := LangOf(p, nil)
	if ok {
		return true
	}
	for i := len(p) - 1; i >= 0 && p[i] != '/'; i-- {
		if p[i] == '.' {
			return false
		}
	}
	return true
}

func toRegistry(f *File) registry.FileAnnotations {
	fa := registry.FileAnnotations{Path: f.Path}
	for _, u := range f.Units {
		ua := registry.UnitAnnotation{Member: u.Member, Line: u.Opener.No}
		for _, c := range u.Covers {
			ua.Covers = append(ua.Covers, registry.Cover{
				Source: c.Source, Line: c.Line.No, StampedAt: c.Stamp.Date, StampedBlob: c.Stamp.Blob,
			})
		}
		// The runner keys: M3.1's named extension (the grammar guarantees
		// one argument for runner and batch, at least one for needs).
		if u.Runner != nil {
			ua.Runner = u.Runner.Args[0]
		}
		if u.Batch != nil {
			ua.Batch = u.Batch.Args[0]
		}
		for _, n := range u.Needs {
			ua.Needs = append(ua.Needs, n.Args...)
		}
		// The scoped keys: M2.5's named extension (the grammar guarantees
		// one argument for kind and reviewed, at least one for the lists).
		first := func(kv *KeyVal) {
			if kv != nil && (ua.ScopedLine == 0 || kv.Line.No < ua.ScopedLine) {
				ua.ScopedLine = kv.Line.No
			}
		}
		if u.Kind != nil {
			ua.Kind = u.Kind.Args[0]
			first(u.Kind)
		}
		if u.Reviewed != nil {
			ua.Reviewed = u.Reviewed.Args[0]
			first(u.Reviewed)
		}
		for _, l := range []struct {
			kvs []KeyVal
			dst *[]string
		}{{u.Areas, &ua.Areas}, {u.Scopes, &ua.Scopes}, {u.Triggers, &ua.Triggers}} {
			for i := range l.kvs {
				*l.dst = append(*l.dst, l.kvs[i].Args...)
				first(&l.kvs[i])
			}
		}
		for _, r := range u.Reads {
			ua.Reads = append(ua.Reads, r.Args...)
			if ua.ReadsLine == 0 || r.Line.No < ua.ReadsLine {
				ua.ReadsLine = r.Line.No
			}
		}
		fa.Units = append(fa.Units, ua)
	}
	return fa
}
