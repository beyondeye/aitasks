// Package identity refuses to run the harness unless the compiled-in
// goengines snapshot is the one baseline/PIN names: .baseline/IDENTITY (or
// .baseline-unpatched/IDENTITY in the guard build) must match PIN field for
// field, and the binary's build info must show goengines replaced by that
// snapshot directory. There is no fallback to the live checkout.
package identity

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"runtime/debug"
	"sort"
	"strings"
)

// GoenginesModule is the module the snapshot provides.
const GoenginesModule = "github.com/beyondeye/aitasks/goengines"

// ID is a baseline identity.
type ID struct {
	Commit, Tree, Seam string
	Patched            bool
	Root               string // the research dir
}

// Header is the identity line printed at the top of every result.
func (id ID) Header() string {
	mode := "patched"
	if !id.Patched {
		mode = "unpatched"
	}
	return fmt.Sprintf("baseline: commit=%s tree=%s seam_sha256=%s snapshot=%s", id.Commit, id.Tree, id.Seam, mode)
}

func readKV(p string) (map[string]string, error) {
	f, err := os.Open(p)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	m := map[string]string{}
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "" || strings.HasPrefix(line, "#") {
			continue
		}
		k, v, ok := strings.Cut(line, ":")
		if ok {
			m[strings.TrimSpace(k)] = strings.TrimSpace(v)
		}
	}
	return m, sc.Err()
}

// FindRoot walks up from the working directory to the research dir (the one
// holding baseline/PIN).
func FindRoot() (string, error) {
	d, err := os.Getwd()
	if err != nil {
		return "", err
	}
	for {
		if _, err := os.Stat(filepath.Join(d, "baseline", "PIN")); err == nil {
			return d, nil
		}
		p := filepath.Dir(d)
		if p == d {
			return "", errors.New("research dir not found (no baseline/PIN above the working directory)")
		}
		d = p
	}
}

// Verify checks PIN against the snapshot this binary was built with.
// patched selects .baseline/ (true) or .baseline-unpatched/ (false).
func Verify(root string, patched bool) (ID, error) {
	pin, err := readKV(filepath.Join(root, "baseline", "PIN"))
	if err != nil {
		return ID{}, fmt.Errorf("PIN: %w", err)
	}
	dir, wantSeam := ".baseline", pin["seam_sha256"]
	if !patched {
		dir, wantSeam = ".baseline-unpatched", "none"
	}
	got, err := readKV(filepath.Join(root, dir, "IDENTITY"))
	if err != nil {
		return ID{}, fmt.Errorf("%s/IDENTITY: %w (run baseline/fetch.sh%s)", dir, err, map[bool]string{true: "", false: " --unpatched"}[patched])
	}
	for _, k := range []string{"commit", "tree"} {
		if pin[k] == "" || got[k] != pin[k] {
			return ID{}, fmt.Errorf("IDENTITY mismatch: %s/IDENTITY %s=%q, PIN %s=%q", dir, k, got[k], k, pin[k])
		}
	}
	if got["seam_sha256"] != wantSeam {
		return ID{}, fmt.Errorf("IDENTITY mismatch: %s/IDENTITY seam_sha256=%q, want %q", dir, got["seam_sha256"], wantSeam)
	}
	if _, err := os.Stat(filepath.Join(root, dir, "goengines", "go.mod")); err != nil {
		return ID{}, fmt.Errorf("snapshot missing: %w", err)
	}
	if got["content_sha256"] == "" {
		return ID{}, fmt.Errorf("%s/IDENTITY has no content_sha256 (re-run baseline/fetch.sh)", dir)
	}
	sum, err := ContentSHA256(filepath.Join(root, dir))
	if err != nil {
		return ID{}, fmt.Errorf("snapshot content: %w", err)
	}
	if sum != got["content_sha256"] {
		return ID{}, fmt.Errorf("IDENTITY mismatch: %s/goengines content sha256 %s, IDENTITY says %s (the snapshot was edited)", dir, sum, got["content_sha256"])
	}
	if err := checkBuild("./" + dir + "/goengines"); err != nil {
		return ID{}, err
	}
	return ID{Commit: got["commit"], Tree: got["tree"], Seam: got["seam_sha256"], Patched: patched, Root: root}, nil
}

// ContentSHA256 is fetch.sh's content hash of <snap>/goengines: the sha256
// of "<sha256 hex>  goengines/<path>\n" lines in byte order of path.
func ContentSHA256(snap string) (string, error) {
	var paths []string
	err := filepath.WalkDir(filepath.Join(snap, "goengines"), func(p string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if d.Type().IsRegular() {
			rel, _ := filepath.Rel(snap, p)
			paths = append(paths, filepath.ToSlash(rel))
		}
		return nil
	})
	if err != nil {
		return "", err
	}
	sort.Strings(paths)
	h := sha256.New()
	for _, p := range paths {
		data, err := os.ReadFile(filepath.Join(snap, p))
		if err != nil {
			return "", err
		}
		fmt.Fprintf(h, "%x  %s\n", sha256.Sum256(data), p)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

// checkBuild requires the binary's goengines dependency to be replaced by
// the snapshot directory (not the live checkout, not a module version).
func checkBuild(wantReplace string) error {
	bi, ok := debug.ReadBuildInfo()
	if !ok {
		return errors.New("no build info: cannot prove which goengines this binary was built with")
	}
	for _, d := range bi.Deps {
		if d.Path != GoenginesModule {
			continue
		}
		if d.Replace == nil || filepath.Clean(d.Replace.Path) != filepath.Clean(wantReplace) {
			r := "<none>"
			if d.Replace != nil {
				r = d.Replace.Path
			}
			return fmt.Errorf("built against goengines replace=%s, want %s", r, wantReplace)
		}
		return nil
	}
	return errors.New("goengines is not a dependency of this binary")
}
