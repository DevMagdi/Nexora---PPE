import { describe, expect, it } from "vitest"
import {
  aggregateViolationPieData,
  isCoreType,
  normalizeViolationKey,
  violationLabel,
} from "@/lib/formatters"

describe("violation labels and chart aggregation", () => {
  it.each([
    ["NO-Mask", "بدون كمامة"],
    ["no mask", "بدون كمامة"],
    ["NO-Gloves", "بدون قفازات"],
    ["no hand gloves", "بدون قفازات"],
    ["NO-Goggles", "بدون نظارات واقية"],
    ["no goggle", "بدون نظارات واقية"],
  ])("maps %s to the shared Arabic label", (raw, expected) => {
    expect(violationLabel(raw, new Map())).toBe(expected)
  })

  it("merges construction and medical spellings into one pie slice and key", () => {
    const pieData = aggregateViolationPieData(
      [
        { violation_type: "NO-Mask" },
        { violation_type: "no mask" },
        { violation_type: "NO-Gloves" },
        { violation_type: "no hand gloves" },
        { violation_type: "NO-Goggles" },
        { violation_type: "no goggle" },
      ],
      new Map(),
    )

    expect(pieData).toEqual([
      { name: "بدون قفازات", value: 2 },
      { name: "بدون كمامة", value: 2 },
      { name: "بدون نظارات واقية", value: 2 },
    ])
    expect(new Set(pieData.map(({ name }) => name)).size).toBe(pieData.length)
  })

  it("merges distinct raw keys when metadata gives them the same label", () => {
    const labels = new Map([
      ["custom-one", "مخالفة مخصصة"],
      ["custom_two", "مخالفة مخصصة"],
    ])

    expect(
      aggregateViolationPieData(
        [{ violation_type: "custom-one" }, { violation_type: "custom_two" }],
        labels,
      ),
    ).toEqual([{ name: "مخالفة مخصصة", value: 2 }])
  })

  it("orders ties deterministically and caps the pie at five labels", () => {
    const violations = [
      "alpha", "bravo", "charlie", "delta", "echo", "foxtrot",
    ].map((violation_type) => ({ violation_type }))

    expect(aggregateViolationPieData(violations, new Map())).toEqual([
      { name: "alpha", value: 1 },
      { name: "bravo", value: 1 },
      { name: "charlie", value: 1 },
      { name: "delta", value: 1 },
      { name: "echo", value: 1 },
    ])
  })

  it.each([0, -1, 0.2])("returns no slices for a non-positive effective limit (%s)", (limit) => {
    expect(aggregateViolationPieData([{ violation_type: "NO-Mask" }], new Map(), limit)).toEqual([])
  })

  it("uses the default limit for a non-finite limit", () => {
    const violations = Array.from({ length: 6 }, (_, i) => ({ violation_type: `custom-${i}` }))
    expect(aggregateViolationPieData(violations, new Map(), Number.NaN)).toHaveLength(5)
  })

  it("tolerates missing, null, and non-string violation types", () => {
    expect(
      aggregateViolationPieData(
        [undefined, null, {}, { violation_type: null }, { violation_type: 42 }],
        new Map(),
      ),
    ).toEqual([{ name: "غير محدد", value: 5 }])
    expect(aggregateViolationPieData(null, new Map())).toEqual([])
  })

  it.each([null, undefined, 7, {}])("normalizes non-string input without throwing (%s)", (value) => {
    expect(normalizeViolationKey(value)).toBe("")
    expect(isCoreType(value)).toBe(false)
  })

  it("looks up PPE metadata using the trimmed raw type", () => {
    expect(violationLabel("  laboratory_alarm  ", new Map([["laboratory_alarm", "إنذار مخصص"]]))).toBe(
      "إنذار مخصص",
    )
  })
})
