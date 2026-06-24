"""TLS self-signed certificate management for the ait applink server (t822_7).

The applink WebSocket listener is ``wss://`` per the security baseline in
``aidocs/applink/protocol.md``. The cert is self-signed and generated once via
the system ``openssl`` binary — keeping the framework free of a heavy Python
crypto dependency. The SHA-256/base64url fingerprint of the cert (computed with
stdlib only) is embedded in the pairing QR; the mobile client pins it for the
lifetime of the pairing (protocol.md §Pairing flow step 2).

Cryptographic hardening (suite selection, cert rotation, key lifecycle) is
explicitly out of scope here and tracked by the security-review follow-up.
"""
from __future__ import annotations

import base64
import hashlib
import shutil
import ssl
import subprocess
import sys
from pathlib import Path

# Self-sufficient import of the sibling ``paths`` module regardless of who
# imported us first (mirrors sessions.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402

CERT_FILENAME = "server.crt"
KEY_FILENAME = "server.key"

_CERT_VALIDITY_DAYS = 3650
_CERT_SUBJECT = "/CN=ait-applink"
_CERT_KEY_BITS = "rsa:2048"


class CertError(RuntimeError):
    """Raised when the self-signed certificate cannot be ensured."""


def ensure_cert(cert_dir: Path) -> tuple[Path, Path]:
    """Return ``(cert_path, key_path)``, generating the pair once if absent.

    Idempotent: an existing cert+key is reused so the fingerprint stays stable
    across restarts (the mobile client pins it for the pairing lifetime).
    ``openssl``'s own stdout/stderr is captured and never leaked to the caller's
    streams (so callers like the TUI smoke test stay output-clean).
    """
    paths.ensure_secure_dir(cert_dir)
    cert_path = cert_dir / CERT_FILENAME
    key_path = cert_dir / KEY_FILENAME
    if cert_path.is_file() and key_path.is_file():
        return cert_path, key_path

    openssl = shutil.which("openssl")
    if openssl is None:
        raise CertError(
            "openssl was not found on PATH; cannot generate the applink TLS "
            f"certificate. Install openssl, or drop a {CERT_FILENAME}/"
            f"{KEY_FILENAME} pair into {cert_dir}."
        )

    cmd = [
        openssl, "req", "-x509", "-newkey", _CERT_KEY_BITS, "-nodes",
        "-keyout", str(key_path), "-out", str(cert_path),
        "-days", str(_CERT_VALIDITY_DAYS), "-subj", _CERT_SUBJECT,
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0 or not (cert_path.is_file() and key_path.is_file()):
        raise CertError(
            f"openssl certificate generation failed: {proc.stderr.strip()}"
        )
    # Lock the private key down; best-effort (e.g. on filesystems without modes).
    try:
        key_path.chmod(0o600)
    except OSError:
        pass
    return cert_path, key_path


def fingerprint(cert_path: Path) -> str:
    """SHA-256 of the cert's DER form, base64url-encoded without padding.

    Matches ``aidocs/applink/protocol.md`` §Pairing flow step 2.
    """
    pem = cert_path.read_text()
    der = ssl.PEM_cert_to_DER_cert(pem)
    digest = hashlib.sha256(der).digest()
    return base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")


def build_ssl_context(cert_path: Path, key_path: Path) -> ssl.SSLContext:
    """Server-side TLS context loaded with the self-signed cert+key.

    Hardened beyond the ``PROTOCOL_TLS_SERVER`` defaults (t985): the floor is
    TLS 1.2 (drops 1.0/1.1) and the 1.2 cipher list is restricted to modern
    forward-secret AEAD suites. The floor is 1.2 — **not** 1.3 — deliberately,
    so the mobile client's TLS stack can still negotiate; TLS 1.3 suites are
    AEAD by construction and need no explicit pinning.
    """
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    ctx.set_ciphers("ECDHE+AESGCM:ECDHE+CHACHA20:!aNULL:!eNULL:!MD5")
    ctx.load_cert_chain(certfile=str(cert_path), keyfile=str(key_path))
    return ctx


class CertManager:
    """Bundles the cert lifecycle for one cert directory.

    Memoizes the resolved paths so ``fingerprint`` / ``ssl_context`` do not each
    re-run the existence check; cert generation still happens at most once.
    """

    def __init__(self, cert_dir: Path) -> None:
        self.cert_dir = cert_dir
        self._cert_path: Path | None = None
        self._key_path: Path | None = None

    def ensure(self) -> tuple[Path, Path]:
        if self._cert_path is None or self._key_path is None:
            self._cert_path, self._key_path = ensure_cert(self.cert_dir)
        return self._cert_path, self._key_path

    def fingerprint(self) -> str:
        cert_path, _ = self.ensure()
        return fingerprint(cert_path)

    def ssl_context(self) -> ssl.SSLContext:
        cert_path, key_path = self.ensure()
        return build_ssl_context(cert_path, key_path)
