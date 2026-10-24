from typing import Literal, get_args

SourceType = Literal["rtsp", "rtsps", "http_mjpeg", "hls", "file", "usb"]
SOURCE_TYPES = get_args(SourceType)
NETWORK_TYPES = {"rtsp", "rtsps", "http_mjpeg", "hls"}
HTTP_TYPES = {"http_mjpeg", "hls"}
