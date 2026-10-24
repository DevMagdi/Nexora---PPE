import type { Page } from "@playwright/test"

export const IMAGE = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aQSsAAAAASUVORK5CYII=",
  "base64",
)
const stamp = "2026-10-24T10:00:00Z"

/** Browser contract fixtures only; production never imports this module. */
export async function mockApi(
  page: Page,
  options: {
    signedIn?: boolean
    role?: "admin" | "supervisor" | "viewer"
    rotate?: boolean
    empty?: boolean
  } = {},
) {
  let signedIn = options.signedIn ?? true
  let rotate = options.rotate ?? false
  const role = options.role ?? "admin"
  let sites = options.empty
    ? []
    : [
        {
          id: 1,
          name: "مصنع المنطقة الصناعية",
          kind: "factory",
          location: "الجيزة · المنطقة الصناعية",
          created_at: stamp,
        },
      ]
  let cameras = options.empty
    ? []
    : [
        {
          id: 1,
          name: "بوابة خط الإنتاج",
          source_type: "rtsp",
          source_uri: "rtsp://192.168.10.20/…",
          site_id: 1,
          enabled_classes: ["helmet", "vest"],
          is_active: false,
          is_running: false,
          created_at: stamp,
        },
      ]
  let events = options.empty
    ? []
    : Array.from({ length: 6 }, (_, index) => ({
        id: index + 1,
        camera_id: 1,
        violation_type: index % 2 ? "NO-Safety Vest" : "NO-Hardhat",
        confidence: 0.87 + index / 100,
        timestamp: stamp,
        resolved_at: index > 3 ? stamp : null,
        is_resolved: index > 3,
        frame_path: "camera_1/evidence.jpg",
        frame_url: "/frames/camera_1/evidence.jpg",
      }))
  const rules = [
    { key: "helmet", label_ar: "خوذة أمان", label_en: "Hardhat" },
    { key: "vest", label_ar: "سترة عاكسة", label_en: "Safety Vest" },
    { key: "gloves", label_ar: "قفازات عمل", label_en: "Gloves" },
    { key: "boots", label_ar: "حذاء أمان", label_en: "Safety Boots" },
    { key: "goggles", label_ar: "نظارات واقية", label_en: "Goggles" },
  ]
  let users = [
    {
      id: 1,
      username: "site.admin",
      role: "admin",
      is_active: true,
      must_change_password: false,
      created_at: stamp,
    },
    {
      id: 2,
      username: "shift.supervisor",
      role: "supervisor",
      is_active: true,
      must_change_password: false,
      created_at: stamp,
    },
  ]
  await page.route("**/api/v1/**", async (route) => {
    const request = route.request()
    const path = new URL(request.url()).pathname.replace("/api/v1", "")
    const params = new URL(request.url()).searchParams
    const method = request.method()
    const json = (body: unknown, status = 200) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) })
    const empty = () => route.fulfill({ status: 204 })
    const payload = () => request.postDataJSON()
    if (path === "/health") return json({ status: "ok" })
    if (path === "/auth/me")
      return signedIn
        ? json({ id: 1, username: "site.admin", role, must_change_password: rotate })
        : json({ detail: "Not authenticated" }, 401)
    if (path === "/auth/login") {
      const body = new URLSearchParams(request.postData() ?? "")
      if (body.get("password") !== "PilotTest!2026")
        return json({ detail: "بيانات الدخول غير صحيحة" }, 401)
      signedIn = true
      return json({ authenticated: true, must_change_password: rotate })
    }
    if (!signedIn) return json({ detail: "Not authenticated" }, 401)
    if (path === "/auth/logout") {
      signedIn = false
      return empty()
    }
    if (path === "/auth/change-password") {
      rotate = false
      return json({ authenticated: true, must_change_password: false })
    }
    if (path === "/auth/media-token") return empty()
    if (path === "/meta/system")
      return json({
        scope: "industrial",
        model: "ppe_unified_best.pt",
        confidence: 0.5,
        max_upload_mb: 100,
        max_video_seconds: 120,
        rules,
      })
    if (path === "/sites" && method === "GET") return json(sites)
    if (path === "/sites" && method === "POST") {
      const site = { id: sites.length + 1, ...payload(), created_at: stamp }
      sites.push(site)
      return json(site, 201)
    }
    if (/^\/sites\/\d+$/.test(path) && method === "PUT") {
      const id = Number(path.split("/")[2])
      sites = sites.map((site) => (site.id === id ? { ...site, ...payload() } : site))
      return json(sites.find((site) => site.id === id))
    }
    if (/^\/sites\/\d+$/.test(path) && method === "DELETE") {
      const id = Number(path.split("/")[2])
      if (cameras.some((camera) => camera.site_id === id))
        return json({ detail: "Reassign this site's cameras before deleting it" }, 409)
      sites = sites.filter((site) => site.id !== id)
      return empty()
    }
    if (path === "/cameras" && method === "GET") return json(cameras)
    if (path === "/cameras" && method === "POST") {
      const camera = {
        id: cameras.length + 1,
        ...payload(),
        source_uri: "rtsp://192.168.10.20/…",
        is_active: false,
        is_running: false,
        created_at: stamp,
      }
      cameras.push(camera)
      return json(camera, 201)
    }
    if (/^\/cameras\/\d+$/.test(path) && method === "PUT") {
      const id = Number(path.split("/")[2])
      cameras = cameras.map((camera) =>
        camera.id === id ? { ...camera, ...payload(), source_uri: camera.source_uri } : camera,
      )
      return json(cameras.find((camera) => camera.id === id))
    }
    if (/^\/cameras\/\d+$/.test(path) && method === "DELETE") {
      cameras = cameras.filter((camera) => camera.id !== Number(path.split("/")[2]))
      return empty()
    }
    if (/^\/cameras\/\d+\/(start|stop)$/.test(path)) {
      const id = Number(path.split("/")[2])
      const running = path.endsWith("start")
      cameras = cameras.map((camera) =>
        camera.id === id ? { ...camera, is_active: running, is_running: running } : camera,
      )
      return json({ status: running ? "started" : "stopped", camera_id: id })
    }
    if (path.startsWith("/stream/")) return route.fulfill({ contentType: "image/png", body: IMAGE })
    if (path === "/dashboard") {
      const filtered = events.filter(
        (event) =>
          !params.has("site_id") ||
          cameras.find((camera) => camera.id === event.camera_id)?.site_id ===
            Number(params.get("site_id")),
      )
      const totals = filtered.reduce<Record<string, number>>(
        (sum, event) => ({ ...sum, [event.violation_type]: (sum[event.violation_type] ?? 0) + 1 }),
        {},
      )
      return json({
        range: params.get("range"),
        from: "2026-10-24T00:00:00Z",
        to: "2026-10-24T12:00:00Z",
        total_events: filtered.length,
        open_events: filtered.filter((event) => !event.is_resolved).length,
        resolved_events: filtered.filter((event) => event.is_resolved).length,
        total_cameras: cameras.length,
        running_cameras: cameras.filter((camera) => camera.is_running).length,
        sites: sites.length,
        live_people: 0,
        series: Array.from({ length: params.get("range") === "24h" ? 24 : 7 }, (_, index) => ({
          timestamp: `2026-10-24T${String(index).padStart(2, "0")}:00:00Z`,
          count: index === 10 ? filtered.length : 0,
        })),
        breakdown: Object.entries(totals).map(([type, count]) => ({ type, count })),
      })
    }
    if (/^\/violations\/\d+\/resolve$/.test(path)) {
      const id = Number(path.split("/")[2])
      events = events.map((event) =>
        event.id === id ? { ...event, is_resolved: true, resolved_at: stamp } : event,
      )
      return json(events.find((event) => event.id === id))
    }
    if (path === "/violations" || path === "/violations/export") {
      const filtered = events.filter(
        (event) =>
          (!params.get("status") ||
            params.get("status") === "all" ||
            event.is_resolved === (params.get("status") === "resolved")) &&
          (!params.get("violation_type") ||
            event.violation_type === params.get("violation_type")) &&
          (!params.get("camera_id") || event.camera_id === Number(params.get("camera_id"))),
      )
      if (path.endsWith("/export"))
        return route.fulfill({
          contentType: "text/csv",
          body:
            "id,violation_type\n" +
            filtered.map((event) => `${event.id},${event.violation_type}`).join("\n"),
        })
      const size = Number(params.get("page_size") ?? 25)
      const pageNum = Number(params.get("page") ?? 1)
      return json({
        items: filtered.slice((pageNum - 1) * size, pageNum * size),
        total: filtered.length,
        page: pageNum,
        page_size: size,
      })
    }
    if (path === "/inference/image")
      return json({
        detections: [{ class_name: "Hardhat", confidence: 0.91, box: [0, 0, 1, 1] }],
        preview: `data:image/png;base64,${IMAGE.toString("base64")}`,
        width: 1,
        height: 1,
      })
    if (path === "/auth/users" && method === "GET") return json(users)
    if (path === "/auth/users" && method === "POST") {
      const user = {
        id: users.length + 1,
        ...payload(),
        is_active: true,
        must_change_password: true,
        created_at: stamp,
      }
      users.push(user)
      return json({ ...user, initial_password: "Temporary!2026-Site" }, 201)
    }
    if (/^\/auth\/users\/\d+$/.test(path)) {
      const id = Number(path.split("/")[3])
      users = users.map((user) => (user.id === id ? { ...user, ...payload() } : user))
      return json(users.find((user) => user.id === id))
    }
    if (path.endsWith("/reset-password")) {
      const id = Number(path.split("/")[3])
      return json({
        ...users.find((user) => user.id === id),
        initial_password: "Temporary!2026-New",
      })
    }
    return json({ detail: "Unmocked browser contract endpoint" }, 404)
  })
  await page.route("**/frames/**", (route) =>
    route.fulfill({ contentType: "image/png", body: IMAGE }),
  )
  await page.routeWebSocket(/\/api\/v1\/ws\//, (ws) =>
    ws.send(
      JSON.stringify({ person: 2, hardhat: 1, no_hardhat: 1, vest: 2, no_vest: 0, total: 6 }),
    ),
  )
}

export async function navigate(page: Page, label: string) {
  const menu = page.getByRole("button", { name: "فتح قائمة التنقل", includeHidden: true })
  await menu.waitFor({ state: "attached" })
  if (await menu.isVisible()) await menu.click()
  await page.getByRole("button", { name: label, exact: true }).click()
}
