//go:build unix && !linux && !darwin

package procsup

import "errors"

// SessionProcs has no implementation on this platform: every sweep reports
// cleanup_unverified (exit 3) rather than claiming a cleanup it cannot see.
func SessionProcs(int) ([]SessionProc, error) {
	return nil, errors.New("no process enumeration on this platform")
}
