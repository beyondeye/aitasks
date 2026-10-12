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
// M2.4 / M2.5 extend registry.UnitAnnotation additively and fill the new
// fields in toRegistry below (named extensions).
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
		fa.Units = append(fa.Units, ua)
	}
	return fa
}
