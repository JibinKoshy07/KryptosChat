"""Authenticated encryption for messages and streaming media.

Security model
--------------
* **Message encryption** uses AES-256-GCM with a per-message key derived from
  ``MESSAGE_MASTER_KEY_BASE64`` via HKDF-SHA256 and a random 16-byte salt.
  The ciphertext layout is ``salt(16) || nonce(12) || ct+tag``, url-safe
  base64 encoded with a ``krypte1:`` prefix. Each message gets a fresh key
  and nonce (key separation + unique nonce ⇒ no nonce reuse across messages).

* **Media encryption** streams a file in fixed-size chunks and encrypts each
  chunk with AES-256-GCM using a per-file key derived from
  ``MEDIA_KDF_MASTER_KEY_BASE64``, plus a file-specific salt and a unique
  base nonce. Each chunk's nonce is ``base_nonce + chunk_index`` (unique
  within the file ⇒ no IV reuse). A final HMAC-SHA256 over the header and all
  ciphertext (keyed with ``MEDIA_KDF_AUTH_KEY_BASE64``) authenticates the
  whole file, preventing truncation and header tampering.

Neither passwords, tokens, nor plaintext content are ever sent over the wire
or stored unencrypted in PostgreSQL.
"""
import base64
import hmac
import struct
from typing import BinaryIO

from cryptography.hazmat.primitives import hashes, hmac as crypto_hmac
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.core.config import settings
from app.core.security import load_key_b64

# --- Storage format constants -------------------------------------------------
MESSAGE_PREFIX = "krypte1:"
MEDIA_MAGIC = b"KRYPTEMEDIA1"
MEDIA_HMAC_KEY_INFO = b"krypte-media-hmac-v1"
GCM_NONCE_LEN = 12
GCM_TAG_LEN = 16
SALT_LEN = 16


# --------------------------------------------------------------------------- #
# Message encryption                                                          #
# --------------------------------------------------------------------------- #
def _derive_message_key(salt: bytes) -> bytes:
    kdf = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        info=b"krypte-message-v1",
    )
    return kdf.derive(load_key_b64(settings.message_master_key_base64))


def _message_aad() -> bytes:
    """AAD binds every message to the station payload key (key separation)."""
    return load_key_b64(settings.message_encryption_key_base64)


def encrypt_message(plaintext: str) -> str:
    """Encrypt a message string, returning a self-contained url-safe blob."""
    salt = base64.b64encode(__import__("os").urandom(SALT_LEN))
    key = _derive_message_key(salt)
    nonce = __import__("os").urandom(GCM_NONCE_LEN)
    ct_and_tag = AESGCM(key).encrypt(nonce, plaintext.encode("utf-8"), _message_aad())
    payload = salt + nonce + ct_and_tag
    return MESSAGE_PREFIX + base64.urlsafe_b64encode(payload).decode("ascii")


def decrypt_message(blob: str) -> str:
    """Decrypt a ``krypte1:`` message blob; raises ``ValueError`` on failure."""
    if not blob.startswith(MESSAGE_PREFIX):
        raise ValueError("Invalid encrypted message header")
    payload = base64.urlsafe_b64decode(blob[len(MESSAGE_PREFIX):])
    salt, nonce, ct_and_tag = payload[:SALT_LEN], payload[SALT_LEN:SALT_LEN + GCM_NONCE_LEN], payload[SALT_LEN + GCM_NONCE_LEN:]
    key = _derive_message_key(salt)
    try:
        plaintext = AESGCM(key).decrypt(nonce, ct_and_tag, _message_aad())
    except Exception as exc:  # integrity check failure / bad key
        raise ValueError("Failed to decrypt message") from exc
    return plaintext.decode("utf-8")


# --------------------------------------------------------------------------- #
# Streaming media encryption                                                  #
# --------------------------------------------------------------------------- #
def _derive_media_key(salt: bytes) -> bytes:
    kdf = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=b"krypte-media-v1")
    return kdf.derive(load_key_b64(settings.media_kdf_master_key_base64))


def _hmac_key() -> bytes:
    return load_key_b64(settings.media_kdf_auth_key_base64)


class MediaEncryptor:
    """Wraps an output binary stream and writes an encrypted blob.

    Layout::
        magic(12) || salt(16) || base_nonce(12) || chunk_len(4)+ct+tag ... || mac(32)
    """

    def __init__(self, sink: BinaryIO, chunk_size: int | None = None):
        self._sink = sink
        self.chunk_size = chunk_size or settings.media_chunk_size
        self.salt = __import__("os").urandom(SALT_LEN)
        self.base_nonce = __import__("os").urandom(GCM_NONCE_LEN)
        self._key = _derive_media_key(self.salt)
        self._chunk_index = 0
        self._mac = crypto_hmac.HMAC(_hmac_key(), hashes.SHA256())

    async def write(self, data: bytes) -> None:
        """Write the header on the first call, then encrypted chunks."""
        if self._chunk_index == 0:
            self._sink.write(MEDIA_MAGIC + self.salt + self.base_nonce)
            self._mac.update(MEDIA_MAGIC + self.salt + self.base_nonce)

        while data:
            chunk, data = data[: self.chunk_size], data[self.chunk_size:]
            nonce = self.base_nonce[:8] + struct.pack(">I", self._chunk_index)
            chunk_ct = AESGCM(self._key).encrypt(nonce, chunk, None)
            self._sink.write(struct.pack(">I", len(chunk_ct)) + chunk_ct)
            self._mac.update(struct.pack(">I", len(chunk_ct)) + chunk_ct)
            self._chunk_index += 1

    async def close(self) -> None:
        """Finalize and write the whole-file MAC (must be called once)."""
        self._sink.write(self._mac.finalize())


class MediaDecryptor:
    """Reads an encrypted blob from a binary stream and yields plaintext chunks."""

    def __init__(self, source: BinaryIO):
        self._source = source
        header = source.read(len(MEDIA_MAGIC) + SALT_LEN + GCM_NONCE_LEN)
        if header[: len(MEDIA_MAGIC)] != MEDIA_MAGIC:
            raise ValueError("Invalid media blob header")
        self.salt = header[len(MEDIA_MAGIC): len(MEDIA_MAGIC) + SALT_LEN]
        self.base_nonce = header[len(MEDIA_MAGIC) + SALT_LEN:]
        self._key = _derive_media_key(self.salt)
        self._chunk_index = 0
        self._mac = crypto_hmac.HMAC(_hmac_key(), hashes.SHA256())
        self._mac.update(header)
        self._final_mac = source.read(32)
        self._mac_read = 0

    def read_chunk(self) -> bytes | None:
        """Return the next decrypted chunk, or ``None`` when finished."""
        if self._chunk_index == 0 and self._mac_read == 0:
            self._mac_read = 1
        length_bytes = self._source.read(4)
        if not length_bytes:
            self._verify_mac()
            return None
        length = struct.unpack(">I", length_bytes)[0]
        chunk_ct = self._source.read(length)
        if len(chunk_ct) != length:
            raise ValueError("Truncated media blob")
        self._mac.update(length_bytes + chunk_ct)
        nonce = self.base_nonce[:8] + struct.pack(">I", self._chunk_index)
        plaintext = AESGCM(self._key).decrypt(nonce, chunk_ct, None)
        self._chunk_index += 1
        return plaintext

    def _verify_mac(self) -> None:
        if not hmac.compare_digest(self._mac.finalize(), self._final_mac):
            raise ValueError("Media integrity check failed")


def encrypt_media_to_source(source: BinaryIO, sink: BinaryIO) -> str:
    """Encrypt all of ``source`` into ``sink`` and return storage metadata.

    Useful for small files in tests; for large files use :class:`MediaEncryptor`
    which streams chunk by chunk without loading the file into memory.
    """
    import json

    enc = MediaEncryptor(sink)
    while True:
        chunk = source.read(enc.chunk_size)
        if not chunk:
            break
        enc.write(chunk)
    enc.close()
    return json.dumps({"format": "krypte-media-v1"})


def decrypt_media_to_sink(source: BinaryIO, sink: BinaryIO) -> None:
    """Decrypt a blob from ``source`` into ``sink``."""
    dec = MediaDecryptor(source)
    while True:
        chunk = dec.read_chunk()
        if chunk is None:
            break
        sink.write(chunk)