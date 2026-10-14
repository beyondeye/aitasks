//go:build unix && !linux && !darwin

package runner

import "errors"

// sessionProcs has no implementation on this platform: every sweep reports
// cleanup_unverified (exit 3) rather than claiming a cleanup it cannot see.
func sessionProcs(int) ([]proc, error) {
	return nil, errors.New("no process enumeration on this platform")
}
