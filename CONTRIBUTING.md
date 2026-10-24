# Contributing to Nexora Industrial PPE

Keep changes within factories, construction sites, industrial workshops, warehouses and industrial areas. The single approved checkpoint is `ppe_unified_best.pt`; do not add alternative loaders, downloads or production demo detections. Preserve the fixed MANTIK Navy + Gold tokens in `frontend/src/theme/mantik.css`.

Report reproducible issues in [this repository](https://github.com/DevMagdi/Nexora---PPE/issues). Do not include real credentials, model artifacts, site databases or identifying evidence images in public reports.

Before submitting a pull request:

```bash
python -m pip install -r requirements/test.txt
ruff check app migrations scripts tests
ruff format --check app migrations scripts tests
pytest -q --cov=app --cov-fail-under=75
cd frontend
npm ci
npm run lint
npm run format:check
npm test
npm run build
npx playwright install --with-deps chromium
npm run test:e2e
```

Add regression tests for behavior changes. Browser fixtures and synthetic detectors must remain test-only and must never be reported as genuine-model accuracy. Explain schema migrations, data deletion, model-contract changes and deployment limitations in the PR. The industrial CI workflow repeats these checks.

Follow the [Code of Conduct](CODE_OF_CONDUCT.md). For vulnerabilities use the private reporting guidance in [SECURITY.md](SECURITY.md), not a public issue containing secrets.
