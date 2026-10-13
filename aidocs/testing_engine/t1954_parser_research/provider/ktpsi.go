package provider

import (
	"errors"
	"os"
	"path/filepath"
	"strings"
)

func init() { register("ktpsi", func() (Provider, error) { return NewKtPsi() }) }

// KtPsi is the Kotlin compiler's own PSI (the kotlinc release's
// kotlin-compiler.jar, oracle/KtPsiOracle.java) as a Kotlin provider, run as
// one long-lived JVM. ktlint and detekt sit on the same PSI
// (kotlin-compiler-embeddable), so this row stands for them too.
type KtPsi struct {
	p       *jsonProc
	Version string
}

// NewKtPsi starts the helper built by oracle/ktpsi_build.sh (.ktpsi/).
func NewKtPsi() (*KtPsi, error) {
	cpb, err := os.ReadFile(filepath.Join(".ktpsi", "CLASSPATH"))
	if err != nil {
		return nil, errors.New("ktpsi: helper not built (run oracle/ktpsi_build.sh with T1954_KOTLINC set)")
	}
	cp := strings.TrimSpace(string(cpb)) + string(os.PathListSeparator) + ".ktpsi"
	p, err := startJSONProc("ktpsi", nil, "java", "-Xshare:auto", "-cp", cp, "KtPsiOracle")
	if err != nil {
		return nil, err
	}
	k := &KtPsi{p: p}
	var v struct{ Version, Error string }
	if err := p.call(map[string]any{"version": true}, &v); err != nil || v.Version == "" {
		p.Close()
		return nil, errors.New("ktpsi: helper did not start: " + v.Error)
	}
	k.Version = v.Version
	return k, nil
}

// Close stops the JVM.
func (k *KtPsi) Close() error { return k.p.Close() }

func (*KtPsi) Name() string    { return "ktpsi" }
func (*KtPsi) Langs() []string { return []string{"kotlin"} }

// Caps: exact ranges, parser errors (PsiErrorElement / BAD_CHARACTER), and
// the package directive and import list from the PSI.
func (*KtPsi) Caps(string) Capabilities {
	return Capabilities{TokenRanges: true, Errors: true, Anchors: APackage | AImportEnd}
}

// Analyze parses src with the compiler PSI.
func (k *KtPsi) Analyze(_ string, src []byte) (Result, error) {
	var r struct {
		Comments    []wireToken
		Literals    []wireToken
		Diags       [][2]any
		Anchors     struct{ Package, ImportEnd int }
		Unsupported string
		Error       string
	}
	if err := k.p.call(map[string]string{"src": b64(src)}, &r); err != nil {
		return Result{}, err
	}
	if r.Unsupported != "" {
		return Result{}, &UnsupportedCapabilityError{Missing: []string{r.Unsupported}}
	}
	if r.Error != "" {
		return Result{}, errors.New("ktpsi: " + r.Error)
	}
	var res Result
	var all []RawToken
	for _, group := range [][]wireToken{r.Comments, r.Literals} {
		for _, w := range group {
			tk, err := w.raw()
			if err != nil {
				return Result{}, err
			}
			all = append(all, tk)
			kind := String
			switch tk.Type {
			case "line":
				kind = LineComment
			case "block":
				kind = BlockComment
			}
			res.Spans = append(res.Spans, Span{tk.Start, tk.End, kind})
		}
	}
	if err := ValidateSpanTexts(src, all); err != nil {
		return Result{}, err
	}
	SortSpans(res.Spans)
	for _, d := range r.Diags {
		at := num(d[0])
		msg, _ := d[1].(string)
		res.Diags = append(res.Diags, Diag{at, at, msg})
	}
	res.Anchors = Anchors{Package: r.Anchors.Package, ImportEnd: r.Anchors.ImportEnd}
	return res, nil
}
