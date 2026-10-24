import { describe, expect, it } from "vitest"
import { SOURCE_OPTIONS, validateSourceInput } from "./sources"

describe("typed source input", () => {
  it("keeps RTSP first and lists the six actual adapters", () => {
    expect(SOURCE_OPTIONS.map((item) => item.value)).toEqual([
      "rtsp",
      "rtsps",
      "http_mjpeg",
      "hls",
      "file",
      "usb",
    ])
  })
  it("does not confuse protocols, playlists, file paths or inline credentials", () => {
    expect(validateSourceInput("hls", "rtsp://192.168.10.20/live")).toBeTruthy()
    expect(validateSourceInput("hls", "https://camera.test/live.mjpg")).toBeTruthy()
    expect(validateSourceInput("http_mjpeg", "https://camera.test/live.m3u8")).toBeTruthy()
    expect(validateSourceInput("rtsps", "rtsp://192.168.10.20/live")).toBeTruthy()
    expect(validateSourceInput("rtsp", "rtsp://user:secret@192.168.10.20/live")).toBeTruthy()
    expect(validateSourceInput("file", "samples/config.txt")).toBeTruthy()
  })
  it("accepts the right URI without attempting server-side network policy checks", () => {
    expect(validateSourceInput("rtsp", "rtsp://192.168.10.20/live")).toBeNull()
    expect(validateSourceInput("hls", "https://camera.test/live.m3u8?channel=1")).toBeNull()
    expect(validateSourceInput("http_mjpeg", "http://192.168.10.20/video.mjpg")).toBeNull()
    expect(validateSourceInput("file", "samples/demo.mp4")).toBeNull()
    expect(validateSourceInput("rtsp", "")).toBeNull()
  })
})
