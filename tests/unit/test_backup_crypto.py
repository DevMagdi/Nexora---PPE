from __future__ import annotations

import base64
import io

import pytest

from app import backup


def test_backup_encryption_round_trip_and_no_plaintext(tmp_path):
    plaintext = b"sensitive database contents\x00" * 1000
    encrypted = tmp_path / "database.nxb"
    restored = tmp_path / "restored.dump"
    key = b"k" * 32

    backup.encrypt_stream(io.BytesIO(plaintext), encrypted, key)
    assert encrypted.read_bytes().startswith(backup.MAGIC)
    assert plaintext not in encrypted.read_bytes()
    assert encrypted.stat().st_mode & 0o777 == 0o600

    backup.decrypt_to_path(encrypted, restored, key)
    assert restored.read_bytes() == plaintext
    assert restored.stat().st_mode & 0o777 == 0o600


def test_backup_detects_tampering_and_wrong_keys(tmp_path):
    encrypted = tmp_path / "database.nxb"
    original = tmp_path / "original.dump"
    original.write_bytes(b"classified database bytes")
    with original.open("rb") as source:
        backup.encrypt_stream(source, encrypted, b"a" * 32)

    tampered = bytearray(encrypted.read_bytes())
    tampered[-1] ^= 0x01
    encrypted.write_bytes(tampered)
    output = tmp_path / "must-not-exist.dump"
    with pytest.raises(ValueError, match="authentication failed"):
        backup.decrypt_to_path(encrypted, output, b"a" * 32)
    assert not output.exists()

    encrypted.write_bytes(b"short")
    with pytest.raises(ValueError, match="incomplete"):
        backup.decrypt_to_path(encrypted, output, b"a" * 32)


def test_backup_operations_never_overwrite_existing_files(tmp_path):
    encrypted = tmp_path / "database.nxb"
    encrypted.write_bytes(b"preserve existing archive")
    with pytest.raises(FileExistsError):
        backup.encrypt_stream(io.BytesIO(b"new dump"), encrypted, b"k" * 32)
    assert encrypted.read_bytes() == b"preserve existing archive"

    valid_archive = tmp_path / "valid.nxb"
    backup.encrypt_stream(io.BytesIO(b"dump"), valid_archive, b"k" * 32)
    restore_target = tmp_path / "restored.dump"
    restore_target.write_bytes(b"preserve existing restore target")
    with pytest.raises(FileExistsError):
        backup.decrypt_to_path(valid_archive, restore_target, b"k" * 32)
    assert restore_target.read_bytes() == b"preserve existing restore target"


def test_backup_key_is_loaded_from_settings(monkeypatch):
    key = b"z" * 32
    value = base64.urlsafe_b64encode(key).decode().rstrip("=")
    monkeypatch.setattr(backup.settings, "BACKUP_ENCRYPTION_KEY", value)
    assert backup._key() == key
