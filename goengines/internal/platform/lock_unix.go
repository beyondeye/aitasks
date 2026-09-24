//go:build unix

package platform

import (
	"os"
	"syscall"
)

// Lock takes an exclusive flock on path, creating the file if needed, and
// blocks until it is held. The returned unlock releases it and closes the
// file.
func Lock(path string) (unlock func() error, err error) {
	f, err := os.OpenFile(path, os.O_RDWR|os.O_CREATE, 0o644)
	if err != nil {
		return nil, err
	}
	if err := syscall.Flock(int(f.Fd()), syscall.LOCK_EX); err != nil {
		f.Close()
		return nil, err
	}
	return func() error {
		uerr := syscall.Flock(int(f.Fd()), syscall.LOCK_UN)
		if cerr := f.Close(); uerr == nil {
			uerr = cerr
		}
		return uerr
	}, nil
}
