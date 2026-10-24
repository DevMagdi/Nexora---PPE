import { describe, expect, it } from "vitest"
import {
  NEGATIVE_LABELS,
  ROLE_LABEL,
  RULE_LABEL,
  SITE_LABEL,
  classLabel,
  formatDate,
  normalizeLiveCounts,
  num,
  parseTs,
} from "@/lib/formatters"
import { resolveFrameUrl } from "@/lib/api"

describe("industrial vocabulary", () => {
  it("exposes only the five equipment rules and three permitted roles", () => {
    expect(Object.keys(RULE_LABEL)).toEqual(["helmet", "vest", "gloves", "boots", "goggles"])
    expect(Object.keys(ROLE_LABEL)).toEqual(["admin", "supervisor", "viewer"])
    expect(Object.keys(SITE_LABEL)).toEqual([
      "factory",
      "construction",
      "workshop",
      "warehouse",
      "industrial",
    ])
    expect(Object.keys(NEGATIVE_LABELS)).toHaveLength(5)
    expect(classLabel("NO-Boot")).toBe("بدون حذاء أمان")
    expect(classLabel("unexpected")).toBe("فئة غير مدعومة")
  })
})
describe("truthful telemetry", () => {
  it("ignores heartbeat and malformed messages", () => {
    for (const value of [null, undefined, "bad", { ping: true }, { unknown: 2 }])
      expect(normalizeLiveCounts(value)).toBeNull()
  })
  it("accepts only finite, nonnegative counts", () => {
    const counts = normalizeLiveCounts({
      person: 2,
      no_hardhat: 1,
      no_vest: -1,
      no_gloves: "8",
      no_boot: Number.NaN,
    })
    expect(counts?.person).toBe(2)
    expect(counts?.no_hardhat).toBe(1)
    expect(counts?.no_vest).toBe(0)
    expect(counts?.no_gloves).toBe(0)
    expect(counts?.no_boot).toBe(0)
  })
  it("never presents an unavailable count as zero", () => {
    expect(num(undefined)).toBe("—")
    expect(num(0)).toBe("0")
  })
})
describe("UTC timestamps and protected evidence", () => {
  it("interprets database timestamps as UTC without altering explicit zones", () => {
    expect(parseTs("2026-10-24T10:20:00").toISOString()).toBe("2026-10-24T10:20:00.000Z")
    expect(parseTs("2026-10-24T12:20:00+02:00").toISOString()).toBe("2026-10-24T10:20:00.000Z")
    expect(formatDate("bad")).toBe("—")
  })
  it("does not load arbitrary external evidence URLs", () => {
    expect(resolveFrameUrl("https://external.invalid/frames/evidence.jpg")).toBeNull()
    expect(resolveFrameUrl("/frames/../private")).toBeNull()
    expect(resolveFrameUrl("/frames/camera_1/event.jpg")).toBe("/frames/camera_1/event.jpg")
  })
})
