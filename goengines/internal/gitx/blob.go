package gitx

import (
	"crypto/sha1"
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash"
	"strconv"
)

// BlobDigest returns the git blob object id of data — what `git hash-object`
// prints — under the given object format ("sha1" or "sha256"). It runs in
// process: digests sit on the scan hot path, where one exec per file would
// dominate the latency budget.
func BlobDigest(data []byte, format string) (string, error) {
	var h hash.Hash
	switch format {
	case "sha1", "":
		h = sha1.New()
	case "sha256":
		h = sha256.New()
	default:
		return "", fmt.Errorf("gitx: unknown object format %q", format)
	}
	h.Write([]byte("blob " + strconv.Itoa(len(data)) + "\x00"))
	h.Write(data)
	return hex.EncodeToString(h.Sum(nil)), nil
}
