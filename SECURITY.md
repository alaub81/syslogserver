# Security policy

## Supported versions

Use the current `main` branch or the latest stable release. The scheduled
release workflow rebuilds the latest release weekly to pick up available
package fixes, subject to its vulnerability gate. Older tags are rebuilt only
when explicitly selected; they do not have a guaranteed maintenance schedule.

Renovate proposes dependency version updates. Trivy scans application images
and the configured MariaDB image. Fixable HIGH/CRITICAL findings block CI and
release publishing. The narrow, approved gosu exceptions and their evidence
are documented in [image scan review](docs/security-scans.md).

## Reporting a vulnerability

Do not put credentials, private logs or exploit details in a public issue.
When private vulnerability reporting is enabled, use
[Report a vulnerability](https://github.com/alaub81/syslogserver/security/advisories/new).
It is currently disabled in the repository settings (checked 2026-11-13).
Until enabled, contact the maintainer privately through a contact channel
listed on the [maintainer profile](https://github.com/alaub81). If none is
available, open an issue requesting a private contact channel without
including sensitive details.

Include the affected commit/tag, component, impact and reproduction steps.
Redact passwords, tokens, device identifiers and private network information
from logs and screenshots. Response and remediation times depend on maintainer
availability and upstream fixes; no fixed service-level agreement is provided.

## Deployment

- Generate a separate password for each database account with `openssl rand -hex 32`.
- Keep `.env` private and out of Git; changing it does not update existing database accounts.
- Restrict UDP/TCP listeners and the web UI to trusted networks.
- The shipped LogAnalyzer configuration has no login enabled. Use appropriate
  network controls or an authenticated reverse proxy when exposing the UI.
- Back up MariaDB before upgrades or migrations; keep the existing Compose
  project name and persistent volume.

## Scope

Report issues in this repository's Dockerfiles, Compose files, scripts,
configuration and handling of log data. Report vulnerabilities in upstream
syslog-ng, LogAnalyzer, PHP, MariaDB or base images to their maintainers as well.
Test only systems you own or are authorized to assess, and avoid disrupting
live log ingestion. Coordinate disclosure with the maintainer before publishing
sensitive vulnerability details.
