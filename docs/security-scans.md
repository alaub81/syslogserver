# Image scan review

## Current gate

CI and releases reject fixable HIGH/CRITICAL vulnerabilities. Raw Trivy JSON
and SARIF reports are retained for seven days. The approved exceptions below
are active only for the reviewed gosu/Go version.

The GitHub [database scan](https://github.com/alaub81/syslogserver/actions/runs/43392398979/job/131775373930)
failed on 2026-11-13 with 25 HIGH and one CRITICAL finding in the official
`mariadb:13` image's `/usr/local/bin/gosu`. The application image scans passed.
The same 26 findings were reproduced locally with Trivy 0.70.0.

## Analysis

`gosu` 1.19 was built with Go 1.24.6. Its upstream
[security policy](https://github.com/tianon/gosu/blob/master/SECURITY.md)
explains that Go version findings need symbol/reachability analysis: many
reported interfaces are never used by gosu. That alone does not justify
ignoring an advisory.

The actual official arm64 and amd64 binaries were checked with `govulncheck`
1.9.0 in binary/symbol mode against `https://vuln.go.dev` on 2026-11-13. Each of the
26 HIGH/CRITICAL CVEs below maps to an advisory in that database, and none
has a vulnerable symbol present in either binary. Module-level matches alone
are not evidence of a reachable function. Both architectures produced the
same result.

The MEDIUM `CVE-2026-61801` / `GO-2026-6686` in `github.com/moby/sys/user`
**does** have affected symbols present and must remain visible. This review
does not mark the entire gosu binary or its dependencies as unaffected.
Other MEDIUM findings, including Ubuntu packages, also remain in the report.

Official arm64 gosu SHA-256:
`3a8ef022d82c0bc4a98bcb144e77da714c25fcfa64dccc57f6aba7ae47ff1a44`.

Official amd64 gosu SHA-256:
`52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0`.

Raw reports, the extracted binaries and govulncheck JSON are local audit
artifacts under `.local/audit/repository-review/` and are excluded from Git.

## Approved exceptions

The repository owner explicitly approved these exceptions on 2026-11-13.
[.trivyignore.yaml](../.trivyignore.yaml) excludes only the following 26 reviewed
CVEs, with all these restrictions:

- Exact target path: `usr/local/bin/gosu`.
- Exact package/version PURL: `pkg:golang/stdlib@v1.24.6`.
- Expiration: `2027-02-01`, followed by renewed review.
- Reason: the affected symbols are absent from the verified gosu 1.19 binaries.
- Keep the full raw JSON report; apply exceptions only when converting the
  report for the gate/SARIF.

New CVEs, other Go versions, other packages and other binary paths still
fail the HIGH/CRITICAL gate. MEDIUM findings continue to be reported.

| CVE | Severity | Affected interface |
| --- | --- | --- |
| `CVE-2025-68121` | CRITICAL | crypto/tls |
| `CVE-2025-61726` | HIGH | golang |
| `CVE-2025-61729` | HIGH | crypto/x509 |
| `CVE-2026-111943` | HIGH | crypto/x509 |
| `CVE-2026-25679` | HIGH | net/url |
| `CVE-2026-27145` | HIGH | crypto/x509 |
| `CVE-2026-32280` | HIGH | crypto/x509 |
| `CVE-2026-32281` | HIGH | crypto/x509 |
| `CVE-2026-32283` | HIGH | crypto/tls |
| `CVE-2026-33811` | HIGH | net |
| `CVE-2026-33814` | HIGH | net/http/internal/http2 |
| `CVE-2026-33818` | HIGH | encoding/asn1 |
| `CVE-2026-39820` | HIGH | net/mail |
| `CVE-2026-39821` | HIGH | golang.org/x/net/idna |
| `CVE-2026-39822` | HIGH | golang |
| `CVE-2026-39836` | HIGH | net |
| `CVE-2026-42499` | HIGH | net/mail |
| `CVE-2026-42504` | HIGH | mime |
| `CVE-2026-56853` | HIGH | net/http |
| `CVE-2026-56858` | HIGH | html/template |
| `CVE-2026-56859` | HIGH | encoding/xml |
| `CVE-2026-56860` | HIGH | net/url |
| `CVE-2026-56862` | HIGH | crypto/tls |
| `CVE-2026-78667` | HIGH | net/http |
| `CVE-2026-78669` | HIGH | net/http |
| `CVE-2026-97031` | HIGH | crypto/tls |

Six automated tests run Trivy conversion against synthetic findings. They prove
that all reviewed CVEs are excluded only in scope, while another binary path,
another Go version, another package, a new CVE and an expired exception all
fail the gate. These tests require no database download.

## Reproducing the binary analysis

Extract gosu from a container created from the exact MariaDB image digest
(the database need not be started), then use the official Go tool:

```bash
govulncheck -mode=binary -json ./gosu > govulncheck.jsonl
```

Pin `golang.org/x/vuln/cmd/govulncheck@v1.9.0` for this review. Inspect the
JSON stream: correlate each advisory's `aliases` with the CVEs above and check
whether any matching finding has a nonempty `trace[0].function`. A zero exit
status with `-json` by itself is insufficient evidence of no findings.
Review again when the image, gosu, Go version or vulnerability database changes.
