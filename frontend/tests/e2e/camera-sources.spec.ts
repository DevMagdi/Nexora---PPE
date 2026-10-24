import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"
import { mockApi, navigate } from "./fixtures"

async function openForm(page: import("@playwright/test").Page) {
  await page.goto("/")
  await navigate(page, "إدارة الكاميرات")
  await page.getByRole("button", { name: "إضافة كاميرا", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
}

test("type picker comes first, has truthful ONVIF guidance and guards USB by default", async ({
  page,
}) => {
  await mockApi(page)
  await openForm(page)
  const picker = page.getByLabel("نوع المصدر", { exact: true })
  await expect(picker).toHaveValue("rtsp")
  expect(
    await picker
      .locator("option")
      .evaluateAll((items) => items.map((item) => (item as HTMLOptionElement).value)),
  ).toEqual(["rtsp", "rtsps", "http_mjpeg", "hls", "file", "usb"])
  await expect(page.getByRole("dialog").locator("form select").first()).toHaveAttribute(
    "id",
    "camera-source-type",
  )
  await expect(
    page.getByText("عنوان جهاز ONVIF — تسجيل فقط، بلا اكتشاف تلقائي", { exact: true }),
  ).toBeVisible()
  await picker.selectOption("usb")
  await expect(page.getByRole("dialog")).toContainText("ليس مصدرًا للإنتاج")
  await expect(
    page.getByRole("dialog").getByRole("button", { name: "إضافة الكاميرا", exact: true }),
  ).toBeDisabled()
  await expect(page.getByLabel("فهرس جهاز USB على الخادم")).toBeVisible()
  await expect(page.getByLabel("رابط RTSP", { exact: true })).toHaveCount(0)
  await picker.selectOption("hls")
  await expect(page.getByLabel("مصادقة HTTP")).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})

for (const [kind, uri, label, port] of [
  ["rtsp", "rtsp://192.168.10.20/stream", "رابط RTSP", "554"],
  ["rtsps", "rtsps://192.168.10.20/stream", "رابط RTSPS", "322"],
  ["http_mjpeg", "http://192.168.10.20/video.mjpg", "رابط MJPEG", "8080"],
  ["hls", "https://camera.example/live/index.m3u8", "رابط HLS", "443"],
] as const) {
  test(`${kind} submits its own type and write-only masked credentials`, async ({ page }) => {
    await mockApi(page)
    await openForm(page)
    await page.getByLabel("نوع المصدر", { exact: true }).selectOption(kind)
    await page.getByLabel("اسم الكاميرا", { exact: true }).fill(`مصدر ${kind}`)
    await page.getByLabel(label, { exact: true }).fill(uri)
    await page.getByLabel("المنفذ (اختياري)").fill(port)
    await page.getByLabel("اسم مستخدم الكاميرا", { exact: true }).fill("operator")
    const password = page.getByLabel("كلمة مرور الكاميرا", { exact: true })
    await expect(password).toHaveAttribute("type", "password")
    await password.fill("PrivateCameraValue!")
    if (kind === "http_mjpeg") await page.getByLabel("مصادقة HTTP").selectOption("digest")
    const submitted = page.waitForRequest(
      (request) =>
        request.method() === "POST" && new URL(request.url()).pathname.endsWith("/cameras"),
    )
    await page
      .getByRole("dialog")
      .getByRole("button", { name: "إضافة الكاميرا", exact: true })
      .click()
    const data = (await submitted).postDataJSON()
    expect(data).toMatchObject({
      source_type: kind,
      source_uri: uri,
      source_username: "operator",
      source_password: "PrivateCameraValue!",
      port: Number(port),
    })
    await expect(page.getByRole("heading", { name: `مصدر ${kind}`, exact: true })).toBeVisible()
    await page.getByRole("button", { name: `تعديل مصدر ${kind}` }).click()
    await expect(page.getByLabel("كلمة مرور الكاميرا", { exact: true })).toHaveValue("")
    await expect(page.getByLabel("اسم مستخدم الكاميرا", { exact: true })).toHaveValue("")
    await expect(page.locator("body")).not.toContainText("PrivateCameraValue!")
  })
}

test("server file input is distinct from upload and sends no network credentials", async ({
  page,
}) => {
  await mockApi(page)
  await openForm(page)
  await page.getByLabel("نوع المصدر", { exact: true }).selectOption("file")
  await page.getByLabel("اسم الكاميرا", { exact: true }).fill("اختبار ملف الموقع")
  await page.getByLabel("مسار ملف الفيديو على الخادم", { exact: true }).fill("samples/demo.mp4")
  await expect(page.getByRole("dialog")).toContainText("يُقرأ مرة واحدة")
  await expect(page.getByLabel("كلمة مرور الكاميرا", { exact: true })).toHaveCount(0)
  const submitted = page.waitForRequest(
    (request) =>
      request.method() === "POST" && new URL(request.url()).pathname.endsWith("/cameras"),
  )
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "إضافة الكاميرا", exact: true })
    .click()
  const payload = (await submitted).postDataJSON()
  expect(payload.source_type).toBe("file")
  expect(payload.source_uri).toBe("samples/demo.mp4")
  expect(payload).not.toHaveProperty("source_password")
  await expect(page.getByRole("heading", { name: "اختبار ملف الموقع" })).toBeVisible()
})

test("explicit development capability permits a local USB index, never a URI", async ({ page }) => {
  await mockApi(page, { usb: true })
  await openForm(page)
  await page.getByLabel("نوع المصدر", { exact: true }).selectOption("usb")
  await page.getByLabel("اسم الكاميرا", { exact: true }).fill("تجربة USB محلية")
  await page.getByLabel("فهرس جهاز USB على الخادم").fill("1")
  const submitted = page.waitForRequest(
    (request) =>
      request.method() === "POST" && new URL(request.url()).pathname.endsWith("/cameras"),
  )
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "إضافة الكاميرا", exact: true })
    .click()
  const payload = (await submitted).postDataJSON()
  expect(payload).toMatchObject({ source_type: "usb", device_index: 1 })
  expect(payload).not.toHaveProperty("source_uri")
  await expect(page.getByRole("heading", { name: "تجربة USB محلية" })).toBeVisible()
})

test("failed source is explicit on the card and leaves other pages usable", async ({ page }) => {
  await mockApi(page, { cameraFailure: true })
  await page.goto("/")
  await navigate(page, "إدارة الكاميرات")
  await page.getByRole("button", { name: "تشغيل بوابة خط الإنتاج", exact: true }).click()
  await expect(page.getByText("فشل الاتصال", { exact: true })).toBeVisible()
  await expect(page.locator("article").getByRole("alert")).toContainText("تعذّر فتح مصدر الكاميرا")
  await navigate(page, "المصانع والمواقع")
  await expect(page.getByRole("heading", { name: "المصانع والمواقع", exact: true })).toBeVisible()
})

test("softer cards, logical active indicator and forms preserve RTL and avoid animation", async ({
  page,
}, info) => {
  await mockApi(page)
  await openForm(page)
  const styles = await page.evaluate(() => {
    const card = document.querySelector("article.panel")!
    const field = document.querySelector("input.field, select.field, textarea.field")!
    const activeNav = document.querySelector('.nav-item[aria-current="page"]')!
    const cardStyle = getComputedStyle(card)
    return {
      border: cardStyle.borderTopColor,
      borderWidth: cardStyle.borderTopWidth,
      shadow: cardStyle.boxShadow,
      radius: parseFloat(cardStyle.borderRadius),
      fieldBorder: getComputedStyle(field).borderTopColor,
      activeNavBackground: getComputedStyle(activeNav).backgroundColor,
      activeIndicatorWidth: getComputedStyle(activeNav, "::before").width,
      animation: cardStyle.animationName,
      direction: getComputedStyle(document.documentElement).direction,
    }
  })
  // Cards use a neutral hairline; gold stays reserved for controls and the
  // active indicator instead of outlining every surface. Alpha is compared
  // numerically because Chromium versions round it differently (0.1 vs 0.106).
  const alpha = (color: string) => {
    const match = color.match(/rgba?\(([^)]+)\)/)
    const parts = match?.[1].split(",").map((part) => Number(part.trim()))
    return parts?.length === 4 ? parts[3] : 1
  }
  expect(styles.border).toContain("168, 176, 188")
  expect(alpha(styles.border)).toBeGreaterThan(0.08)
  expect(alpha(styles.border)).toBeLessThanOrEqual(0.14)
  expect(styles.borderWidth).toBe("1px")
  expect(styles.shadow).not.toBe("none")
  expect(styles.fieldBorder).toContain("201, 162, 39")
  expect(alpha(styles.fieldBorder)).toBeGreaterThan(0.08)
  expect(alpha(styles.fieldBorder)).toBeLessThanOrEqual(0.14)
  expect(styles.activeIndicatorWidth).toBe("2px")
  expect(styles.activeNavBackground).not.toBe("rgba(0, 0, 0, 0)")
  expect(styles.radius).toBeGreaterThanOrEqual(16)
  expect(styles.radius).toBeLessThanOrEqual(18.4)
  expect(styles.animation).toBe("none")
  expect(styles.direction).toBe("rtl")
  await page.getByLabel("نوع المصدر", { exact: true }).selectOption("hls")
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBeTruthy()
  await page.screenshot({
    path: `test-results/screenshots/camera-source-${info.project.name}.png`,
    fullPage: true,
  })
})
