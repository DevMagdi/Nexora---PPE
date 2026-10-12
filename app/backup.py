from __future__ import annotations

import argparse
import base64
import os
import secrets
import shutil
import sys
import tempfile
from pathlib import Path

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.core.config import settings

MAGIC = b"NEXORA1"
NONCE_SIZE = 12
TAG_SIZE = 16
CHUNK_SIZE = 1024 * 1024


def _key() -> bytes:
    try:
        value = settings.BACKUP_ENCRYPTION_KEY
        key = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    except (ValueError, TypeError) as exc:
        raise ValueError("Set a valid BACKUP_ENCRYPTION_KEY in the protected environment") from exc
    if len(key) != 32:
        raise ValueError("BACKUP_ENCRYPTION_KEY must decode to 32 bytes")
    return key


def _open_private(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    file_descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    return os.fdopen(file_descriptor, "wb")


def encrypt_stream(source, output_path: Path, key: bytes) -> None:
    nonce = secrets.token_bytes(NONCE_SIZE)
    encryptor = Cipher(algorithms.AES(key), modes.GCM(nonce)).encryptor()
    encryptor.authenticate_additional_data(MAGIC)
    temporary = output_path.with_name(f".{output_path.name}.{secrets.token_hex(6)}.partial")
    try:
        with _open_private(temporary) as destination:
            destination.write(MAGIC)
            destination.write(nonce)
            while chunk := source.read(CHUNK_SIZE):
                destination.write(encryptor.update(chunk))
            destination.write(encryptor.finalize())
            destination.write(encryptor.tag)
            destination.flush()
            os.fsync(destination.fileno())
        # Publish atomically without ever overwriting a prior backup.
        os.link(temporary, output_path)
        temporary.unlink()
        os.chmod(output_path, 0o600)
    finally:
        temporary.unlink(missing_ok=True)


def decrypt_to_path(input_path: Path, output_path: Path, key: bytes) -> None:
    size = input_path.stat().st_size
    header_size = len(MAGIC) + NONCE_SIZE
    if size < header_size + TAG_SIZE:
        raise ValueError("Backup is incomplete or has an invalid format")

    temporary = output_path.with_name(f".{output_path.name}.{secrets.token_hex(6)}.partial")
    try:
        with input_path.open("rb") as encrypted:
            magic = encrypted.read(len(MAGIC))
            nonce = encrypted.read(NONCE_SIZE)
            if magic != MAGIC or len(nonce) != NONCE_SIZE:
                raise ValueError("Backup format or version is invalid")
            encrypted.seek(-TAG_SIZE, os.SEEK_END)
            tag = encrypted.read(TAG_SIZE)
            ciphertext_length = size - header_size - TAG_SIZE
            encrypted.seek(header_size)

            decryptor = Cipher(algorithms.AES(key), modes.GCM(nonce, tag)).decryptor()
            decryptor.authenticate_additional_data(MAGIC)
            with _open_private(temporary) as plaintext:
                remaining = ciphertext_length
                while remaining:
                    chunk = encrypted.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        raise ValueError("Backup ended unexpectedly")
                    remaining -= len(chunk)
                    plaintext.write(decryptor.update(chunk))
                plaintext.write(decryptor.finalize())
                plaintext.flush()
                os.fsync(plaintext.fileno())
        # Do not overwrite an existing restore target without an explicit operator action.
        os.link(temporary, output_path)
        temporary.unlink()
        os.chmod(output_path, 0o600)
    except InvalidTag as exc:
        raise ValueError("Backup authentication failed: wrong key or tampered file") from exc
    finally:
        temporary.unlink(missing_ok=True)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Encrypt/decrypt on-prem PostgreSQL backups using AES-256-GCM")
    commands = parser.add_subparsers(dest="command", required=True)
    encrypt = commands.add_parser("encrypt", help="Encrypt a custom-format pg_dump received on stdin")
    encrypt.add_argument("--output", type=Path, required=True)
    decrypt = commands.add_parser("decrypt", help="Authenticate/decrypt an encrypted backup")
    decrypt.add_argument("--input", type=Path, required=True)
    decrypt.add_argument("--output", type=Path)
    decrypt.add_argument("--stdout", action="store_true", help="Write verified plaintext to stdout")
    return parser


def main() -> int:
    args = _parser().parse_args()
    try:
        key = _key()
        if args.command == "encrypt":
            encrypt_stream(sys.stdin.buffer, args.output, key)
            print(f"Encrypted backup written: {args.output}", file=sys.stderr)
            return 0

        if args.stdout == bool(args.output):
            raise ValueError("Choose exactly one of --output or --stdout")
        if args.stdout:
            with tempfile.TemporaryDirectory(prefix="nexora-restore-") as temp_dir:
                verified = Path(temp_dir) / "verified.dump"
                decrypt_to_path(args.input, verified, key)
                with verified.open("rb") as plaintext:
                    shutil.copyfileobj(plaintext, sys.stdout.buffer, length=CHUNK_SIZE)
                sys.stdout.buffer.flush()
        else:
            decrypt_to_path(args.input, args.output, key)
            print(f"Verified plaintext dump written: {args.output}", file=sys.stderr)
        return 0
    except (OSError, ValueError) as exc:
        print(f"Backup operation failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
