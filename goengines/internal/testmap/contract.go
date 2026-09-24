// Package testmap is the root of the ait-testmap engine's packages. Each
// engine submodule adds its package under internal/testmap/<pkg>; this root
// holds what they all share: the registry contract version and its refusal,
// and the engine's cache directory.
package testmap

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"path/filepath"
	"strconv"

	"github.com/beyondeye/aitasks/goengines/internal/lineproto"
	"github.com/beyondeye/aitasks/goengines/internal/platform"
	"gopkg.in/yaml.v3"
)

// Contract is the registry contract this engine implements. A registry file
// (and seeded.yaml, adopted.yaml, onboard.yaml, costs/policy.yaml) carrying a
// newer `contract:` is refused; older and absent values are accepted, because
// new fields are additive. It is a source constant, not an ldflag: the
// refusal depends on it, so a build must not be able to claim a
// compatibility it does not implement.
const Contract = 1

// ErrInvalidContract is a `contract:` value that is not a non-negative
// integer (a float, a string, null, a list…), a duplicated key, or a file
// that is not a single YAML mapping document.
var ErrInvalidContract = errors.New("invalid contract")

// ReadContract returns the top-level `contract:` value of a YAML file. found
// is false only when the key is absent (or the file is empty). The whole
// input is checked: a second document, a non-mapping document, a repeated
// key or a value that is not an integer scalar is an error, never silently
// truncated or treated as absent.
func ReadContract(data []byte) (contract int, found bool, err error) {
	dec := yaml.NewDecoder(bytes.NewReader(data))
	var doc yaml.Node
	if err := dec.Decode(&doc); err != nil {
		if errors.Is(err, io.EOF) {
			return 0, false, nil
		}
		return 0, false, fmt.Errorf("contract: %w", err)
	}
	var extra yaml.Node
	if err := dec.Decode(&extra); !errors.Is(err, io.EOF) {
		if err != nil {
			return 0, false, fmt.Errorf("contract: %w", err)
		}
		return 0, false, fmt.Errorf("%w: more than one YAML document", ErrInvalidContract)
	}
	if len(doc.Content) == 0 {
		return 0, false, nil
	}
	top := doc.Content[0]
	if top.Kind != yaml.MappingNode {
		return 0, false, fmt.Errorf("%w: top level is not a mapping", ErrInvalidContract)
	}
	// Decode the mapping the way every consumer will — merge keys (<<) and
	// aliases resolved, explicit keys overriding merged ones, a repeated key
	// an error — so the value checked here is the effective one. Scanning
	// the literal root keys would read `<<: *defaults` carrying contract: 2
	// as "absent".
	var m map[string]any
	if err := top.Decode(&m); err != nil {
		return 0, false, fmt.Errorf("%w: %v", ErrInvalidContract, err)
	}
	v, ok := m["contract"]
	if !ok {
		return 0, false, nil
	}
	c, isInt := v.(int)
	if !isInt || c < 0 {
		return 0, false, fmt.Errorf("%w: contract: %v (%T) is not a non-negative integer", ErrInvalidContract, v, v)
	}
	return c, true, nil
}

// ContractMismatchError refuses a file whose contract is newer than Contract.
type ContractMismatchError struct {
	Path   string
	File   int
	Engine int
}

func (e *ContractMismatchError) Error() string {
	return fmt.Sprintf("%s: contract %d is newer than this engine's %d", e.Path, e.File, e.Engine)
}

// Line is the protocol line CONTRACT_MISMATCH:<path>|<file>|<engine>. A path
// that cannot travel in a line (it holds '|' or a line break) is an error —
// report it through Error() instead of emitting a record that splits wrong.
func (e *ContractMismatchError) Line() (string, error) {
	return lineproto.Format("CONTRACT_MISMATCH", e.Path, strconv.Itoa(e.File), strconv.Itoa(e.Engine))
}

// ExitCode is the framework-error exit the Run Surface table assigns to
// CONTRACT_MISMATCH.
func (e *ContractMismatchError) ExitCode() int { return lineproto.ExitFramework }

// CheckContract parses data (the content of path) and returns a
// *ContractMismatchError when its contract is newer than Contract. A parse
// error or a non-integer contract is returned as-is.
func CheckContract(path string, data []byte) error {
	c, found, err := ReadContract(data)
	if err != nil {
		return fmt.Errorf("%s: %w", path, err)
	}
	if found && c > Contract {
		return &ContractMismatchError{Path: path, File: c, Engine: Contract}
	}
	return nil
}

// CacheDir returns `${XDG_CACHE_HOME:-$HOME/.cache}/aitasks/testmap`, the
// root the engine's caches (e.g. deps/<blob>.json) live under.
func CacheDir() (string, error) {
	root, err := platform.CacheRoot()
	if err != nil {
		return "", err
	}
	return filepath.Join(root, "testmap"), nil
}
