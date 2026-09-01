"""Encryption round-trip and tamper-detection tests."""
import io

import pytest

from app.services.crypto import (
    MediaDecryptor,
    MediaEncryptor,
    decrypt_message,
    encrypt_message,
)


def test_message_roundtrip():
    assert decrypt_message(encrypt_message("hello world")) == "hello world"


def test_message_encryption_is_not_plaintext():
    blob = encrypt_message("secret")
    assert "secret" not in blob
    assert blob.startswith("krypte1:")


def test_message_tamper_detection():
    blob = bytearray(encrypt_message("attack at dawn").encode())
    blob[-1] ^= 0x01  # flip a bit in the ciphertext/tag
    with pytest.raises(ValueError):
        decrypt_message(blob.decode())


def test_message_garbage_header():
    with pytest.raises(ValueError):
        decrypt_message("not-a-krypte-blob")


def test_media_stream_roundtrip():
    source = io.BytesIO(b"a" * 100 + b"b" * 50)
    sink = io.BytesIO()
    enc = MediaEncryptor(sink, chunk_size=32)
    while True:
        chunk = source.read(32)
        if not chunk:
            break
        enc.write(chunk)
    enc.close()

    reader = io.BytesIO(sink.getvalue())
    dec = MediaDecryptor(reader)
    out = io.BytesIO()
    while True:
        chunk = dec.read_chunk()
        if chunk is None:
            break
        out.write(chunk)
    assert out.getvalue() == b"a" * 100 + b"b" * 50


def test_media_tamper_detection():
    source = io.BytesIO(b"payload data")
    sink = io.BytesIO()
    enc = MediaEncryptor(sink, chunk_size=16)
    enc.write(source.read())
    enc.close()
    blob = sink.getvalue()
    # Corrupt the final MAC.
    corrupted = blob[:-1] + bytes([blob[-1] ^ 0x01])
    dec = MediaDecryptor(io.BytesIO(corrupted))
    with pytest.raises(ValueError):
        while dec.read_chunk() is not None:
            pass