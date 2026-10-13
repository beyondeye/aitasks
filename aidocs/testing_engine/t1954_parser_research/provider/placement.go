package provider

import (
	"strings"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// ProposedFilePlacement is the RESEARCH-PROPOSED insertion point (insert
// after this line; 0 = top) of a fresh file-level `testmap:` block for the
// research languages — NOT validated production behaviour. annot's landed
// fixedPosition has no rule for them and falls to the bash-like "after the
// leading comment block" default; the runner records both.
//
//   - TS/TSX/JS: after the import block and any directive prologue;
//   - Java:  after the imports, else after the package clause;
//   - Rust:  after inner attributes / `//!` docs and the `use` block;
//   - Swift: after the imports;
//
// each falling back to the leading shebang + comment block when the provider
// confirms (declared, zero) there is none. Like annot.Placement it never
// lands at or after the first member opener. The caller must have passed
// Check(lang, caps, NeedFreshFileInsert): anchors are read only after that.
func ProposedFilePlacement(f *annot.File, lang string, a Anchors) (after int, ok bool) {
	lead := leading(f)
	switch lang {
	case "typescript", "tsx", "javascript":
		after = max(lead, a.ImportEnd, a.Prologue)
	case "java":
		after = max(lead, a.Package, a.ImportEnd)
	case "rust":
		after = max(lead, a.InnerAttrEnd, a.ImportEnd)
	case "swift":
		after = max(lead, a.ImportEnd)
	default:
		return 0, false
	}
	if len(f.Units) > 1 && after >= f.Units[1].Opener.No {
		after = f.Units[1].Opener.No - 1
	}
	return after, true
}

// leading is the shebang then the run of comment lines (annot's default).
func leading(f *annot.File) int {
	n, i := len(f.Lines), 0
	if n > 0 && strings.HasPrefix(f.Lines[0], "#!") {
		i = 1
	}
	for i < n && f.Ctx.Class[i] == annot.Comment {
		i++
	}
	return i
}

// Mask zeroes every anchor not declared in set: an undeclared anchor is
// unknown, and no placement rule may read it as "none".
func Mask(a Anchors, set AnchorSet) Anchors {
	keep := func(bit AnchorSet, v int) int {
		if set&bit != 0 {
			return v
		}
		return 0
	}
	return Anchors{
		Shebang: keep(AShebang, a.Shebang), HeaderEnd: keep(AHeaderEnd, a.HeaderEnd),
		Package: keep(APackage, a.Package), ImportEnd: keep(AImportEnd, a.ImportEnd),
		Prologue: keep(APrologue, a.Prologue), InnerAttrEnd: keep(AInnerAttrEnd, a.InnerAttrEnd),
	}
}
