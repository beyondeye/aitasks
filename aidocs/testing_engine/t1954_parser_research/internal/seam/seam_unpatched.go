//go:build unpatched

package seam

import (
	"errors"

	"github.com/beyondeye/aitasks/goengines/internal/testmap/annot"
)

// Available reports whether this build can install hooks.
const Available = false

// ErrUnpatched: a hook was requested from the unpatched (guard) build.
var ErrUnpatched = errors.New("seam unavailable: built against the unpatched snapshot")

// With runs fn unchanged when both hooks are nil; any hook is refused.
func With(classify func(annot.Lang, []byte) annot.Context, lang func(string, []byte) (annot.Lang, bool), fn func() error) error {
	if classify != nil || lang != nil {
		return ErrUnpatched
	}
	return fn()
}

// Landed is the landed classifier (there is no hook in this build).
func Landed(l annot.Lang, data []byte) annot.Context { return annot.Classify(l, data) }
