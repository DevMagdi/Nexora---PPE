"""Reject nested playlists and external file references before native HLS decode."""

from __future__ import annotations

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from app.camera.http_client import SourceError

_TOP_BOXES = {
    b"ftyp",
    b"styp",
    b"moov",
    b"moof",
    b"mdat",
    b"sidx",
    b"emsg",
    b"free",
    b"skip",
    b"prft",
}
_CONTAINERS = {
    b"moov",
    b"trak",
    b"mdia",
    b"minf",
    b"dinf",
    b"stbl",
    b"mvex",
    b"moof",
    b"traf",
    b"mfra",
    b"edts",
}


def validate_hls_media(data: bytes, key: bytes | None = None, iv: bytes | None = None) -> None:
    try:
        if key is not None:
            if iv is None or len(iv) != 16 or len(data) % 16:
                raise ValueError
            decryptor = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
            data = decryptor.update(data) + decryptor.finalize()
            padding = data[-1] if data else 0
            if not 1 <= padding <= 16 or data[-padding:] != bytes([padding]) * padding:
                raise ValueError
            data = data[:-padding]
        if (
            len(data) >= 188
            and len(data) % 188 == 0
            and all(data[i] == 0x47 for i in range(0, len(data), 188))
        ):
            return  # Ordinary 188-byte MPEG-TS packets only (not a text playlist).
        count = 0

        def boxes(start: int, end: int, depth: int = 0):
            nonlocal count
            if depth > 8:
                raise ValueError
            while start < end:
                if start + 8 > end:
                    raise ValueError
                size, kind = (
                    int.from_bytes(data[start : start + 4], "big"),
                    data[start + 4 : start + 8],
                )
                header = 8
                if size == 1:
                    if start + 16 > end:
                        raise ValueError
                    size, header = int.from_bytes(data[start + 8 : start + 16], "big"), 16
                if size == 0:
                    size = end - start
                if size < header or start + size > end or (depth == 0 and kind not in _TOP_BOXES):
                    raise ValueError
                count += 1
                if count > 4096:
                    raise ValueError
                payload, limit = start + header, start + size
                if kind in _CONTAINERS:
                    boxes(payload, limit, depth + 1)
                elif kind == b"dref":
                    # ISO BMFF external data references are not allowed, even to a local file.
                    if (
                        payload + 8 > limit
                        or int.from_bytes(data[payload + 4 : payload + 8], "big") != 1
                    ):
                        raise ValueError
                    entry = data[payload + 8 : limit]
                    if entry != b"\x00\x00\x00\x0curl \x00\x00\x00\x01":
                        raise ValueError
                start += size

        if len(data) < 8 or data[4:8] not in _TOP_BOXES:
            raise ValueError
        boxes(0, len(data))
    except (ValueError, IndexError):
        raise SourceError(
            "مورد HLS ليس مقطع TS/fMP4 آمنًا؛ تُرفض القوائم المتنكرة والمراجع الخارجية."
        ) from None
