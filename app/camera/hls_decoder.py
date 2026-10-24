"""Private child process: decode a generated local HLS playlist, never a URL.

PyAV binds FFmpeg directly. Native hangs/crashes stay outside the API process;
its parent enforces read deadlines, termination and bounded raw frame output.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path


def decode(path: str, fps: float, max_pixels: int) -> int:
    import av
    import numpy as np

    playlist = Path(path)
    if not playlist.is_absolute() or playlist.name != "index.m3u8":
        return 2
    try:
        with av.open(
            str(playlist),
            format="hls",
            options={
                "protocol_whitelist": "file,crypto",
                "format_whitelist": "hls,mpegts,mov,aac",
                "allowed_extensions": "ALL",
            },
        ) as container:
            stream = container.streams.video[0]
            stream.codec_context.thread_count = 1
            if stream.width * stream.height > max_pixels:
                return 2
            rate = float(stream.average_rate or 25)
            last_time: float | None = None
            for index, frame in enumerate(container.decode(stream)):
                if frame.width * frame.height > max_pixels:
                    return 2
                now = frame.time if frame.time is not None else index / rate
                if last_time is not None and 0 <= now - last_time < 1 / fps:
                    continue
                last_time = now
                scale = min(960 / frame.width, 540 / frame.height)
                width, height = max(1, int(frame.width * scale)), max(1, int(frame.height * scale))
                image = frame.reformat(width=width, height=height, format="bgr24").to_ndarray()
                canvas = np.zeros((540, 960, 3), dtype=np.uint8)
                top, left = (540 - height) // 2, (960 - width) // 2
                canvas[top : top + height, left : left + width] = image
                sys.stdout.buffer.write(struct.pack(">d", now))
                sys.stdout.buffer.write(canvas.tobytes())
                sys.stdout.buffer.flush()
        return 0
    except Exception:
        # Never emit a native exception, file content, credentials or a URI to logs.
        return 2


if __name__ == "__main__":
    raise SystemExit(decode(sys.argv[1], float(sys.argv[2]), int(sys.argv[3])))
