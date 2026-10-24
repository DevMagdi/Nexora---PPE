import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { defineConfig, devices } from "@playwright/test"

// Optional npm-packaged Linux browser for network-constrained CI. Standard
// Playwright installations use their own sandboxed browser with no overrides.
const bundled =
  process.env.USE_PACKAGED_CHROMIUM === "1" ? await import("@sparticuz/chromium") : null
let launchOptions
if (bundled) {
  const bin = join(dirname(fileURLToPath(import.meta.resolve("@sparticuz/chromium"))), "..", "bin")
  const libraries = await bundled.inflate(join(bin, "al2023.tar.br"))
  launchOptions = {
    executablePath: await bundled.default.executablePath(),
    // Lambda's single-process setting cannot safely reuse Playwright contexts.
    args: bundled.default.args.filter(
      (arg) =>
        ![
          "--single-process",
          "--no-zygote",
          "--disable-web-security",
          "--allow-running-insecure-content",
          "--disable-site-isolation-trials",
        ].includes(arg),
    ),
    env: {
      ...process.env,
      LD_LIBRARY_PATH: `${join(libraries, "lib")}:${process.env.LD_LIBRARY_PATH ?? ""}`,
    },
  }
}

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  workers: 2,
  retries: 0,
  reporter: [["list"], ["json", { outputFile: "test-results/browser-results.json" }]],
  use: {
    baseURL: "http://127.0.0.1:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    launchOptions,
  },
  projects: [
    {
      name: "desktop",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 1000 } },
    },
    { name: "mobile", use: { ...devices["Pixel 7"], defaultBrowserType: "chromium" } },
  ],
  webServer: {
    command: "npm run dev -- --host 0.0.0.0 --port 5173",
    url: "http://127.0.0.1:5173",
    reuseExistingServer: !process.env.CI,
  },
})
