//go:build unix

package runner

import (
	"errors"
	"fmt"
	"io"
	"io/fs"
	"os"
	"syscall"
)

// Bounds on what the engine reads back from a runner's report files.
var (
	resultsMax    int64 = 64 << 20 // results.jsonl
	runnerJSONMax int64 = 1 << 20  // runner.json
)

// readReport reads a report file a runner wrote, after the runner's
// deadline and session sweep, without letting the file bypass them: it never
// follows a symbolic link (O_NOFOLLOW), never blocks opening a FIFO
// (O_NONBLOCK), accepts only a regular file (fstat on the opened handle, so
// no swap between check and read), and reads at most limit bytes. absent is
// a file that does not exist; every other refusal is an error naming why.
func readReport(path string, limit int64) (data []byte, absent bool, err error) {
	f, err := os.OpenFile(path, os.O_RDONLY|syscall.O_NONBLOCK|syscall.O_NOFOLLOW, 0)
	if errors.Is(err, fs.ErrNotExist) {
		return nil, true, nil
	}
	if errors.Is(err, syscall.ELOOP) {
		return nil, false, errors.New("a symbolic link")
	}
	if err != nil {
		return nil, false, err
	}
	defer f.Close()
	fi, err := f.Stat()
	if err != nil {
		return nil, false, err
	}
	if !fi.Mode().IsRegular() {
		return nil, false, fmt.Errorf("not a regular file (%s)", fi.Mode().Type())
	}
	data, err = io.ReadAll(io.LimitReader(f, limit+1))
	if err != nil {
		return nil, false, err
	}
	if int64(len(data)) > limit {
		return nil, false, fmt.Errorf("exceeds %d bytes", limit)
	}
	return data, false, nil
}
