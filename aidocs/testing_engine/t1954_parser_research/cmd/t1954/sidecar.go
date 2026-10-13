package main

// sidecar: the product alternative "registry/sidecar-only annotations" (t1954_3
// step 9). A research registry.AnnotationSource reads one YAML sidecar per
// test file under aitestmap/annotations/ instead of `testmap:` comments, and
// the REAL registry (BuildScanned / RenderScanned / Scan at the pinned
// snapshot) consumes it. Measured over the regenerated M2.2 bench shape:
//   1. equivalence: the rendered _scanned.yaml from inline annotations vs
//      from sidecars carrying the same records;
//   2. scan timing, inline vs sidecar (fastest of 5, same host);
//   3. a test-file move: inline annotations travel with the file; a sidecar
//      keyed by path is orphaned and its file's edges are lost unless an
//      orphan check refuses the scan.
// Nothing here is a production design; the findings carry the evaluation.

import (
	"bytes"
	"context"
	"errors"
	"flag"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
	"time"

	"gopkg.in/yaml.v3"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
	"github.com/beyondeye/aitasks/goengines/internal/testmap/registry"
)

func init() { extraVerbs["sidecar"] = cmdSidecar }

// SidecarDir holds one YAML file per annotated test file.
const SidecarDir = "aitestmap/annotations"

type sidecarFile struct {
	File  string        `yaml:"file"`
	Units []sidecarUnit `yaml:"units"`
}

type sidecarUnit struct {
	Member string         `yaml:"member"`
	Covers []sidecarCover `yaml:"covers"`
}

type sidecarCover struct {
	Source string `yaml:"source"`
	Stamp  string `yaml:"stamp,omitempty"` // "@<date>/<blob10>", parsed by annot.ParseStamp
}

// sidecarSource is the research AnnotationSource. With checkOrphans, a
// sidecar whose test file no longer exists fails the scan (fail closed);
// without it, the stale record is passed on.
type sidecarSource struct {
	checkOrphans bool
	orphans      []string
}

func (s *sidecarSource) Annotations(_ context.Context, root string) ([]registry.FileAnnotations, error) {
	var out []registry.FileAnnotations
	s.orphans = nil
	err := filepath.WalkDir(filepath.Join(root, SidecarDir), func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			if errors.Is(err, fs.ErrNotExist) {
				return nil
			}
			return err
		}
		if d.IsDir() || !strings.HasSuffix(p, ".yaml") {
			return nil
		}
		data, err := os.ReadFile(p)
		if err != nil {
			return err
		}
		var sf sidecarFile
		if err := yaml.Unmarshal(data, &sf); err != nil {
			return fmt.Errorf("%s: %w", p, err)
		}
		if _, err := os.Lstat(filepath.Join(root, filepath.FromSlash(sf.File))); err != nil {
			s.orphans = append(s.orphans, sf.File)
			if s.checkOrphans {
				return fmt.Errorf("sidecar %s: test file %s: %w", p, sf.File, err)
			}
		}
		fa := registry.FileAnnotations{Path: sf.File}
		for _, u := range sf.Units {
			ua := registry.UnitAnnotation{Member: u.Member} // no line: a sidecar has no anchor in the file
			for _, c := range u.Covers {
				cv := registry.Cover{Source: c.Source}
				if c.Stamp != "" {
					st, err := annot.ParseStamp(c.Stamp)
					if err != nil {
						return fmt.Errorf("%s: stamp %q: %w", p, c.Stamp, err)
					}
					cv.StampedAt, cv.StampedBlob = st.Date, st.Blob
				}
				ua.Covers = append(ua.Covers, cv)
			}
			fa.Units = append(fa.Units, ua)
		}
		out = append(out, fa)
		return nil
	})
	sort.Slice(out, func(i, j int) bool { return out[i].Path < out[j].Path })
	return out, err
}

var annotLine = regexp.MustCompile(`(?m)^[ \t]*(#|//)[ \t]*testmap:[^\n]*\n`)

func cmdSidecar(args []string) int {
	fs := flag.NewFlagSet("sidecar", flag.ExitOnError)
	out := fs.String("out", filepath.Join("results", "sidecar.md"), "output file")
	_ = fs.Parse(args)
	ctx := context.Background()
	tmp, err := os.MkdirTemp("", "t1954-sidecar-")
	if err != nil {
		fail(1, err)
	}
	defer os.RemoveAll(tmp)
	inline, side := filepath.Join(tmp, "inline"), filepath.Join(tmp, "sidecar")
	for _, d := range []string{inline, side} {
		if err := writeM22Shape(d); err != nil {
			fail(1, err)
		}
	}
	cfg, err := registry.LoadConfig(inline)
	if err != nil {
		fail(1, err)
	}
	anns, err := annot.Source{}.Annotations(ctx, inline)
	if err != nil {
		fail(1, err)
	}
	// Move every record into a sidecar and strip the comments.
	stripped := 0
	for _, fa := range anns {
		sf := sidecarFile{File: fa.Path}
		for _, u := range fa.Units {
			su := sidecarUnit{Member: u.Member}
			for _, c := range u.Covers {
				st := ""
				if c.StampedAt != "" {
					st = "@" + c.StampedAt + "/" + c.StampedBlob
				}
				su.Covers = append(su.Covers, sidecarCover{Source: c.Source, Stamp: st})
			}
			sf.Units = append(sf.Units, su)
		}
		y, err := yaml.Marshal(sf)
		if err != nil {
			fail(1, err)
		}
		p := filepath.Join(side, SidecarDir, filepath.FromSlash(fa.Path)+".yaml")
		_ = os.MkdirAll(filepath.Dir(p), 0o755)
		if err := os.WriteFile(p, y, 0o644); err != nil {
			fail(1, err)
		}
		tf := filepath.Join(side, filepath.FromSlash(fa.Path))
		data, err := os.ReadFile(tf)
		if err != nil {
			fail(1, err)
		}
		nd := annotLine.ReplaceAll(data, nil)
		stripped += bytes.Count(data, []byte("\n")) - bytes.Count(nd, []byte("\n"))
		if err := os.WriteFile(tf, nd, 0o644); err != nil {
			fail(1, err)
		}
	}
	residual, err := annot.Source{}.Annotations(ctx, side)
	if err != nil {
		fail(1, err)
	}
	src := &sidecarSource{checkOrphans: true}
	sanns, err := src.Annotations(ctx, side)
	if err != nil {
		fail(1, err)
	}
	render := func(a []registry.FileAnnotations) []byte {
		doc, _ := registry.BuildScanned(cfg, a, nil)
		b, err := registry.RenderScanned(doc)
		if err != nil {
			fail(1, err)
		}
		return b
	}
	rIn, rSide := render(anns), render(sanns)
	same := bytes.Equal(rIn, rSide)
	lineField := regexp.MustCompile(`(?m)^[ \t]+line: [0-9]+\n`)
	sameButLines := bytes.Equal(lineField.ReplaceAll(rIn, nil), rSide)
	nLineFields := len(lineField.FindAll(rIn, -1))
	// line fields carried by inline records and absent from sidecars
	lineFields := 0
	for _, fa := range anns {
		for _, u := range fa.Units {
			if u.Line > 0 {
				lineFields++
			}
			lineFields += len(u.Covers)
		}
	}
	scanTime := func(dir string, a registry.AnnotationSource) (time.Duration, *registry.ScanResult, error) {
		best := time.Duration(0)
		var res *registry.ScanResult
		for range 5 {
			t := time.Now()
			r, err := registry.Scan(ctx, dir, registry.Inputs{Annotations: a, Lister: emptyLister{}}, false)
			d := time.Since(t)
			if err != nil {
				return 0, nil, err
			}
			res = r
			if best == 0 || d < best {
				best = d
			}
		}
		return best, res, nil
	}
	tIn, resIn, err := scanTime(inline, annot.Source{})
	if err != nil {
		fail(1, err)
	}
	tSide, resSide, err := scanTime(side, &sidecarSource{checkOrphans: true})
	if err != nil {
		fail(1, err)
	}
	// Move one annotated test file in both trees.
	moved := anns[0].Path
	newPath := strings.TrimSuffix(moved, filepath.Ext(moved)) + "_moved" + filepath.Ext(moved)
	for _, d := range []string{inline, side} {
		if err := os.Rename(filepath.Join(d, moved), filepath.Join(d, newPath)); err != nil {
			fail(1, err)
		}
	}
	_, mvIn, err := scanTime(inline, annot.Source{})
	if err != nil {
		fail(1, err)
	}
	loose := &sidecarSource{}
	_, mvLoose, errLoose := scanTime(side, loose)
	_, _, errStrict := scanTime(side, &sidecarSource{checkOrphans: true})
	looseAnns, _ := (&sidecarSource{}).Annotations(ctx, side)
	looseHasNew := false
	for _, fa := range looseAnns {
		if fa.Path == newPath {
			looseHasNew = true
		}
	}

	var b strings.Builder
	b.WriteString("# Sidecar-only annotations: the registry fed from YAML sidecars (t1954_3)\n\n")
	b.WriteString(id.Header() + "\n\n")
	b.WriteString("Rerun: `go run ./cmd/t1954 sidecar`. Workload: the regenerated M2.2 bench shape (`writeM22Shape`: 420 annotated tests, ¼ Python; 600 sources; 1,000 docs; a fresh git repository) built twice. In the second copy every `testmap:` record is moved into `" + SidecarDir + "/<test path>.yaml` and the comment lines are removed; a research `registry.AnnotationSource` reads the sidecars. The registry code is the pinned snapshot's, unmodified. A research prototype, not a production design.\n\n")
	b.WriteString("| check | result |\n|---|---|\n")
	fmt.Fprintf(&b, "| annotated test files (inline source) | %d |\n", len(anns))
	fmt.Fprintf(&b, "| `testmap:` comment lines removed into sidecars | %d |\n", stripped)
	fmt.Fprintf(&b, "| inline records left in the stripped tree (must be 0) | %d files |\n", len(residual))
	fmt.Fprintf(&b, "| rendered `_scanned.yaml`, inline vs sidecar | %s |\n", map[bool]string{true: "byte-identical", false: "different"}[same])
	fmt.Fprintf(&b, "| … with the inline `line:` fields removed | %s (%d `line:` fields: the registry records each covers edge's line, which a sidecar cannot supply) |\n", map[bool]string{true: "byte-identical", false: "DIFFERENT"}[sameButLines], nLineFields)
	fmt.Fprintf(&b, "| units / edges / variants (inline) | %d / %d / %d |\n", resIn.Units, resIn.Edges, resIn.Variants)
	fmt.Fprintf(&b, "| units / edges / variants (sidecar) | %d / %d / %d |\n", resSide.Units, resSide.Edges, resSide.Variants)
	fmt.Fprintf(&b, "| line anchors carried by inline records, absent from sidecars (unit openers + covers lines) | %d |\n", lineFields)
	fmt.Fprintf(&b, "| `registry.Scan` dry run, fastest of 5: inline (annot lexes 420 files) | %s |\n", ms(tIn.Nanoseconds()))
	fmt.Fprintf(&b, "| `registry.Scan` dry run, fastest of 5: sidecar (YAML only) | %s |\n", ms(tSide.Nanoseconds()))
	b.WriteString("\n## A test file moved (`" + moved + "` → `" + newPath + "`)\n\n")
	b.WriteString("| source | outcome |\n|---|---|\n")
	fmt.Fprintf(&b, "| inline | scan ok: units / edges %d / %d (the records moved with the file) |\n", mvIn.Units, mvIn.Edges)
	if errLoose == nil {
		fmt.Fprintf(&b, "| sidecar, no orphan check | scan ok: units / edges %d / %d; orphaned sidecars %v; the moved file carries annotations: %v — the stale record still names the old path |\n", mvLoose.Units, mvLoose.Edges, loose.orphans, looseHasNew)
	} else {
		fmt.Fprintf(&b, "| sidecar, no orphan check | scan error: %s |\n", lspEsc(strings.ReplaceAll(errLoose.Error(), tmp, "<tmp>")))
	}
	if errStrict != nil {
		fmt.Fprintf(&b, "| sidecar, orphan check (fail closed) | scan refused: %s |\n", lspEsc(strings.ReplaceAll(errStrict.Error(), tmp, "<tmp>")))
	} else {
		b.WriteString("| sidecar, orphan check (fail closed) | scan ok (unexpected) |\n")
	}
	if !same {
		b.WriteString("\n## Rendered difference (first unit of each)\n\n```\n" + firstLines(string(rIn), 8) + "\n```\n\n```\n" + firstLines(string(rSide), 7) + "\n```\n")
	}
	if err := os.WriteFile(*out, []byte(b.String()), 0o644); err != nil {
		fail(1, err)
	}
	fmt.Printf("WROTE:%s\n", *out)
	return 0
}

func firstLines(s string, n int) string {
	ls := strings.SplitN(s, "\n", n+1)
	if len(ls) > n {
		ls = ls[:n]
	}
	return strings.Join(ls, "\n")
}
