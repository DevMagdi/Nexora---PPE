import { test, expect } from "@playwright/test"
import AxeBuilder from "@axe-core/playwright"
import { IMAGE, mockApi, navigate } from "./fixtures"

test("login uses the fixed identity and validates credentials", async ({ page }, info) => {
  await mockApi(page, { signedIn: false })
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "تسجيل الدخول" })).toBeVisible()
  await expect(page.getByRole("button", { name: /الوضع الفاتح|الوضع الداكن/ })).toHaveCount(0)
  await page.evaluate(() => document.fonts.ready)
  await page.screenshot({
    path: `test-results/screenshots/login-${info.project.name}.png`,
    fullPage: true,
  })
  await page.getByLabel("اسم المستخدم", { exact: true }).fill("site.admin")
  await page.getByLabel("كلمة المرور", { exact: true }).fill("wrong")
  await page.getByRole("button", { name: "الدخول إلى لوحة العمليات" }).click()
  await expect(page.getByRole("alert")).toContainText("بيانات الدخول غير صحيحة")
  await page.getByLabel("كلمة المرور", { exact: true }).fill("PilotTest!2026")
  await page.getByRole("button", { name: "الدخول إلى لوحة العمليات" }).click()
  await expect(page.getByRole("heading", { name: "نظرة عامة", exact: true })).toBeVisible()
})

test("first sign-in forces password rotation before entering operations", async ({ page }) => {
  await mockApi(page, { rotate: true })
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "تأمين حسابك" })).toBeVisible()
  await page.getByLabel("كلمة المرور الحالية").fill("Temporary!2026")
  await page.getByLabel("كلمة المرور الجديدة", { exact: true }).fill("SecureShift!2026")
  await page.getByLabel("تأكيد كلمة المرور").fill("SecureShift!2026")
  await page.getByRole("button", { name: "حفظ ومتابعة" }).click()
  await expect(page.getByRole("heading", { name: "نظرة عامة", exact: true })).toBeVisible()
})

test("dashboard renders the exact Navy + Gold tokens without overflow or script errors", async ({
  page,
}, info) => {
  const errors: string[] = []
  page.on("pageerror", (error) => errors.push(error.message))
  await mockApi(page)
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "نشاط السلامة" })).toBeVisible()
  const palette = await page.evaluate(() => {
    const style = getComputedStyle(document.documentElement)
    return ["--navy", "--navy-deep", "--navy-panel", "--gold", "--gold-soft", "--text-muted"].map(
      (key) => style.getPropertyValue(key).trim().toUpperCase(),
    )
  })
  expect(palette).toEqual(["#16283F", "#111B2B", "#1C2B40", "#C9A227", "#D4AF37", "#A8B0BC"])
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
  expect(errors).toEqual([])
  await page.evaluate(() => document.fonts.ready)
  await page.waitForFunction(() => {
    const charts = [...document.querySelectorAll(".recharts-responsive-container")]
    return (
      charts.length === 2 &&
      charts.every((chart) => {
        const svg = chart.querySelector<SVGSVGElement>("svg.recharts-surface")
        if (!svg || Math.abs(svg.viewBox.baseVal.width - chart.clientWidth) > 2) return false
        const pie = chart.querySelector<SVGGElement>("g.recharts-pie")
        if (pie) {
          const box = pie.getBBox()
          return Math.abs(box.x + box.width / 2 - chart.clientWidth / 2) < 3
        }
        const grid = chart.querySelector<SVGGElement>("g.recharts-cartesian-grid")
        return !!grid && grid.getBBox().width > chart.clientWidth * 0.75
      })
    )
  })
  await page.screenshot({
    path: `test-results/screenshots/dashboard-${info.project.name}.png`,
    fullPage: true,
  })
})

test("login and executive dashboard pass automated accessibility checks", async ({ page }) => {
  await mockApi(page, { signedIn: false })
  await page.goto("/")
  await expect(page.getByRole("heading", { name: "تسجيل الدخول" })).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.getByLabel("اسم المستخدم", { exact: true }).fill("site.admin")
  await page.getByLabel("كلمة المرور", { exact: true }).fill("PilotTest!2026")
  await page.getByRole("button", { name: "الدخول إلى لوحة العمليات" }).click()
  await expect(page.getByRole("heading", { name: "نشاط السلامة" })).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
})

test("camera creation, editing and confirmed deletion work end to end", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  await navigate(page, "إدارة الكاميرات")
  await page.getByRole("button", { name: "إضافة كاميرا", exact: true }).click()
  await page.getByLabel("اسم الكاميرا", { exact: true }).fill("كاميرا المستودع")
  await page.getByLabel("المصنع أو الموقع", { exact: true }).selectOption("1")
  await page.getByLabel("رابط RTSP").fill("rtsp://192.168.10.25/live")
  await page
    .getByRole("dialog")
    .getByRole("button", { name: "إضافة الكاميرا", exact: true })
    .click()
  await expect(page.getByRole("heading", { name: "كاميرا المستودع", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "تعديل كاميرا المستودع" }).click()
  await page.getByLabel("اسم الكاميرا", { exact: true }).fill("كاميرا التحميل")
  await page.getByRole("button", { name: "حفظ التعديلات" }).click()
  await expect(page.getByRole("heading", { name: "كاميرا التحميل", exact: true })).toBeVisible()
  await page.getByRole("button", { name: "حذف كاميرا التحميل" }).click()
  await page.getByRole("button", { name: "تأكيد الحذف" }).click()
  await expect(page.getByRole("heading", { name: "كاميرا التحميل", exact: true })).toHaveCount(0)
})

test("alerts can be reviewed, resolved and exported with server filters", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  await navigate(page, "التنبيهات وسجل الأحداث")
  await page.getByLabel("الحالة", { exact: true }).selectOption("open")
  await expect(page.locator("tbody tr")).toHaveCount(4)
  await page.getByRole("button", { name: "عرض دليل الحدث 1" }).click()
  await expect(page.getByRole("dialog").getByRole("img")).toBeVisible()
  await page.getByRole("button", { name: "إغلاق", exact: true }).click()
  await page.getByRole("button", { name: "معالجة", exact: true }).first().click()
  await expect(page.locator("tbody tr")).toHaveCount(3)
  const download = page.waitForEvent("download")
  await page.getByRole("button", { name: "تصدير CSV" }).click()
  expect((await download).suggestedFilename()).toBe("nexora-industrial-events.csv")
})

test("site settings and role provisioning expose only industrial options", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  await navigate(page, "المصانع والمواقع")
  await page.getByRole("button", { name: "إضافة موقع", exact: true }).click()
  expect(await page.getByLabel("نوع الموقع الصناعي").locator("option").allTextContents()).toEqual([
    "مصنع",
    "موقع إنشاء",
    "ورشة صناعية",
    "مستودع",
    "منطقة صناعية",
  ])
  await page.getByLabel("اسم المصنع أو الموقع").fill("مستودع المواد")
  await page.getByLabel("نوع الموقع الصناعي").selectOption("warehouse")
  await page.getByRole("button", { name: "حفظ الموقع" }).click()
  await expect(page.getByRole("heading", { name: "مستودع المواد", exact: true })).toBeVisible()
  await navigate(page, "المستخدمون والأدوار")
  await page.getByRole("button", { name: "إضافة مستخدم" }).click()
  await page.getByLabel("اسم المستخدم", { exact: true }).fill("shift.viewer")
  expect(
    await page.getByLabel("الدور", { exact: true }).locator("option").allTextContents(),
  ).toEqual(["مشاهد", "مشرف السلامة"])
  await page.getByRole("button", { name: "إصدار الحساب" }).click()
  await expect(page.getByRole("heading", { name: "بيانات الدخول المؤقتة" })).toBeVisible()
  await expect(page.getByRole("dialog")).toContainText("Temporary!2026-Site")
  await page.getByRole("button", { name: "تم تسليم البيانات بأمان" }).click()
  await expect(page.getByText("Temporary!2026-Site")).toHaveCount(0)
})

test("image analysis displays only the returned industrial detections", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  await navigate(page, "تحليل الصور والفيديو")
  await page
    .getByLabel("اختر صورة من موقع العمل")
    .setInputFiles({ name: "site.png", mimeType: "image/png", buffer: IMAGE })
  await page.getByRole("button", { name: "تحليل الصورة", exact: true }).click()
  await expect(
    page.getByRole("img", { name: "نتيجة رصد معدات الوقاية في الصورة المرفوعة" }),
  ).toBeVisible()
  await expect(page.getByText("91%", { exact: true })).toBeVisible()
})

test("viewer has read-only navigation and truthful stopped-stream state", async ({ page }) => {
  await mockApi(page, { role: "viewer" })
  await page.goto("/")
  await navigate(page, "إدارة الكاميرات")
  await expect(page.getByRole("button", { name: "إضافة كاميرا", exact: true })).toHaveCount(0)
  await expect(page.getByRole("button", { name: /تعديل بوابة/ })).toHaveCount(0)
  await navigate(page, "المراقبة المباشرة")
  await expect(page.getByRole("heading", { name: "مصدر المراقبة متوقف" })).toBeVisible()
  await expect(page.getByRole("button", { name: "تشغيل المصدر" })).toHaveCount(0)
  await expect(page.getByRole("img", { name: /بث مباشر/ })).toHaveCount(0)
})

test("empty installation never fabricates safety performance", async ({ page }) => {
  await mockApi(page, { empty: true })
  await page.goto("/")
  await expect(page.getByText("المراقبة غير مفعّلة", { exact: true })).toBeVisible()
  await expect(page.getByRole("heading", { name: "لا توجد مخالفات مسجّلة" })).toBeVisible()
  await expect(page.getByRole("heading", { name: "لا توجد أحداث في هذه الفترة" })).toBeVisible()
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
  ).toBeTruthy()
})

test("unavailable service is distinguished from a normal signed-out session", async ({ page }) => {
  await mockApi(page, { signedIn: false })
  let unavailable = true
  await page.route("**/api/v1/auth/me", (route) =>
    route.fulfill({
      status: unavailable ? 503 : 401,
      contentType: "application/json",
      body: JSON.stringify({ detail: unavailable ? "Service unavailable" : "Not authenticated" }),
    }),
  )
  await page.goto("/")
  await expect(page.getByRole("alert")).toContainText("الخادم غير متاح حالياً")
  unavailable = false
  await page.getByRole("button", { name: "إعادة التحقق من الخادم" }).click()
  await expect(page.getByRole("alert")).toHaveCount(0)
  await expect(page.getByRole("heading", { name: "تسجيل الدخول" })).toBeVisible()
})

test("management pages and the camera dialog pass accessibility checks", async ({ page }) => {
  await mockApi(page)
  await page.goto("/")
  for (const label of [
    "إدارة الكاميرات",
    "التنبيهات وسجل الأحداث",
    "تحليل الصور والفيديو",
    "المصانع والمواقع",
    "المستخدمون والأدوار",
  ]) {
    await navigate(page, label)
    await expect(page.getByRole("heading", { name: label, exact: true })).toBeVisible()
    expect((await new AxeBuilder({ page }).analyze()).violations, label).toEqual([])
    expect(
      await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth),
    ).toBeTruthy()
  }
  await navigate(page, "إدارة الكاميرات")
  await page.getByRole("button", { name: "إضافة كاميرا", exact: true }).click()
  await expect(page.getByRole("dialog")).toBeVisible()
  expect((await new AxeBuilder({ page }).analyze()).violations).toEqual([])
  await page.keyboard.press("Escape")
  await expect(page.getByRole("dialog")).toHaveCount(0)
  await expect(page.getByRole("button", { name: "إضافة كاميرا", exact: true })).toBeFocused()
})

test("live stream controls display returned frames and stop without fabricating people", async ({
  page,
}) => {
  await mockApi(page)
  await page.goto("/")
  await navigate(page, "المراقبة المباشرة")
  await expect(page.getByRole("heading", { name: "مصدر المراقبة متوقف" })).toBeVisible()
  await page.getByRole("button", { name: "تشغيل المصدر" }).click()
  await expect(page.getByRole("img", { name: "بث مباشر من بوابة خط الإنتاج" })).toBeVisible()
  await expect(page.getByText("مباشر", { exact: true })).toBeVisible()
  await page.getByRole("button", { name: "إيقاف البث" }).click()
  await expect(page.getByRole("heading", { name: "مصدر المراقبة متوقف" })).toBeVisible()
  await expect(page.getByRole("img", { name: /بث مباشر/ })).toHaveCount(0)
})
