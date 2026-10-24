# Nexora Industrial Console

Arabic RTL console for factory, construction-site, industrial-workshop and warehouse PPE monitoring. React + TypeScript + Vite + TanStack Query. All screens consume the real API; there is no production demo-data mode.

## Development

```bash
npm ci
npm run dev -- --host 0.0.0.0 --port 5173
```

Start the backend separately using the root README. The backend requires the separately provisioned `Model/ppe_unified_best.pt`; an unavailable backend is shown explicitly on the login screen.

Browser requests use relative `/api/v1` and `/frames` URLs. Vite proxies them to `http://127.0.0.1:8000` by default. `VITE_API_PROXY_TARGET` can change the server-side proxy destination (for example `http://app:8000` in Compose). Never place backend loopback URLs in browser-facing code. The Vite configuration accepts the Arena preview host.

## One fixed identity

- `src/theme/mantik.css`: fixed Navy + Gold MANTIK tokens.
- `src/index.css`: token mapping, local font imports, RTL and responsive layouts.
- `src/auth`: login and first-sign-in password rotation.
- `src/dashboard`: SQL-backed overview, live monitoring, uploads, sites and users.
- `src/cameras`, `src/violations`: source management and event review/evidence/export.
- `src/lib/api.ts`: API contract, relative media URLs and expired-session handling.
- `src/hooks/useLiveCamera.ts`: WebSocket lifecycle, retry, renewal and stale telemetry.

No palette switch, alternate brand assets, fake compliance percentages or synthetic worker identities are shipped. Green denotes success; red denotes violations/errors. Counts represent model detections, not unique people.

## Quality gates

```bash
npm run lint
npm run format:check
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

`tests/e2e` fixtures are isolated browser-contract test data, never imported by `src`. Playwright covers desktop and mobile navigation, authentication/password rotation, camera CRUD, sites, account provisioning, event evidence/resolution/CSV, uploads, live start/stop, empty/error states and axe accessibility checks. Browser outputs under `test-results/` are ignored by Git.

In a Linux sandbox where the normal Playwright download is unavailable, the optional npm-packaged browser can be selected with:

```bash
USE_PACKAGED_CHROMIUM=1 npm run test:e2e
```

That path extracts the packaged Linux browser/libraries into the OS temporary directory. Standard CI uses Playwright's normal browser. Neither path validates the genuine model, hardware or RTSP network.

Build output is served by FastAPI when `frontend/dist/index.html` exists, so deployment needs one browser origin. Node.js 22.12+ is required for the build toolchain.
