//go:build unix && !linux && !darwin

package runner

import "errors"

// platformProcView has no implementation on this platform: the ancestry
// backstop cannot run, so every guarded entry is recursion-unverifiable
// rather than admitted unchecked.
func platformProcView() (procView, error) {
	return nil, errors.New("no process ancestry on this platform")
}
