# Mantik PPE security policy

This is an on-prem industrial monitoring application, not a substitute for site safety procedures. Deploy behind the site's HTTPS proxy and network controls. See [deployment guidance](docs/ON_PREM_SECURITY_AR.md).

Report vulnerabilities privately to the repository maintainers through an established private contact channel or GitHub private vulnerability reporting when enabled. Do not publish working credentials, tokens, camera URLs, databases or identifying worker evidence in public issues. No response-time guarantee is implied.

Include the affected revision, a minimal reproduction using synthetic data, impact, environment and relevant redacted logs. Do not upload checkpoint files or attempt to access another installation.

Before any pilot, supply and verify the approved `ppe_unified_best.pt`, use unique strong secrets, pin its SHA-256, test role restrictions and session revocation, and validate backup restoration. A missing or incompatible approved checkpoint must remain a startup failure; never bypass it with another model or fake inference.

Application and browser test success does not establish detector accuracy, physical safety, container deployment readiness or camera-network security. Record actual deployment validation separately.
