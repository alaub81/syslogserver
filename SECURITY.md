# Security Policy

Thank you for helping keep **syslogserver** secure! This document explains which versions are supported and how to report vulnerabilities responsibly.

## Supported Versions

| Component / Image Tag | Support Status | Notes |
|---|---|---|
| `main` branch | ✅ Supported | Active development; receives security fixes and dependency updates. |
| Versioned container tags (e.g., `loganalyzer:4.x`, `syslog-ng:…`) | ✅ Supported | Updated for critical security issues when feasible. |
| Deprecated/archived tags | ⚠️ Best effort | No guarantees for timely patches. |

> We keep base images and dependencies up to date using **GitHub Actions**, **Dependabot**, **Renovate**, and **Trivy** scans.

## How to Report a Vulnerability

**Preferred:** Open a private *GitHub Security Advisory* for this repository:
`Security` → `Advisories` → **Report a vulnerability**
Direct link: [https://github.com/alaub81/syslogserver/security/advisories/new](https://github.com/alaub81/syslogserver/security/advisories/new)

Please include:

- Affected component/file and **commit or tag** (SHA or release),
- Clear **description** and **impact**,
- **Steps to reproduce** / Proof of Concept,
- Relevant **logs**/screenshots (scrub secrets),
- Any **mitigations** or fix suggestions you may have.

### Our Response SLAs

- **Acknowledgement:** within **48 hours** (business days).
- **Triage & severity assignment:** within **5 business days**.
- **Fix or mitigation:** targeted within **30 days** for High/Critical, best effort otherwise. Timelines may vary based on complexity and upstream dependencies.

We’ll coordinate a disclosure timeline with you and publish a security advisory once a fix or mitigation is available.

## Coordinated Disclosure

- Please **do not disclose** details publicly until a fix/mitigation is available and we have published an advisory.
- With your permission, we are happy to credit you in the release notes or advisory.

## Scope

### In scope

- This repository: Dockerfiles, Compose files, scripts, configuration, and images; including `syslog-ng` pipelines, MariaDB init/events, `loganalyzer`, and `dbcleanup` containers.
- Secret handling (`.env`/Docker secrets), DB authentication, configuration parsing.

### Out of scope

(please report upstream and/or submit as informative only)

- Vulnerabilities in **upstream** software (e.g., `syslog-ng`, `php`, `apache`, `mariadb`, base images).
- Theoretical issues without a realistic exploit path in this project’s context.
- Denial-of-service by extreme log volume (rate limiting/quotas are operational concerns).

## Safe Harbor

We support **good-faith security research** in your own test environment:

- No access to third-party data, no social engineering, no physical access.
- Do not intentionally disrupt production systems.
- Follow applicable laws. Report findings privately (see above).

## Cryptography / PGP (optional)

If you prefer encrypted communication, we can provide a PGP key upon request. Please mention this in your report.

---

**Thank you!** Security is a continuous effort—your responsible disclosure helps keep this project safe for everyone.
