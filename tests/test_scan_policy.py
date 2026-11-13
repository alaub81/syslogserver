"""Use Trivy itself to verify the approved exceptions cannot hide other findings."""

import copy
import json
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("trivy"), "Trivy is installed in the stack CI job")
class ScanPolicyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.policy = ROOT / ".trivyignore.yaml"
        self.fixture = {
            "SchemaVersion": 2,
            "ArtifactName": "security-policy-regression",
            "ArtifactType": "container_image",
            "Results": [{
                "Target": "usr/local/bin/gosu", "Class": "lang-pkgs", "Type": "gobinary",
                "Vulnerabilities": [{
                    "VulnerabilityID": "CVE-2025-68121", "PkgName": "stdlib",
                    "InstalledVersion": "v1.24.6", "FixedVersion": "v1.24.13",
                    "PkgIdentifier": {"PURL": "pkg:golang/stdlib@v1.24.6"},
                    "Severity": "CRITICAL", "Title": "Policy regression fixture",
                }],
            }],
        }

    def gate(self, fixture=None, policy=None):
        report = self.directory / "report.json"
        report.write_text(json.dumps(fixture or self.fixture))
        result = subprocess.run([
            "trivy", "convert", "--ignorefile", str(policy or self.policy),
            "--format", "json", "--severity", "HIGH,CRITICAL", "--exit-code", "1", str(report),
        ], capture_output=True, text=True)
        self.assertIn(result.returncode, (0, 1), result.stderr)
        output = json.loads(result.stdout)
        count = sum(len(r.get("Vulnerabilities") or []) for r in output.get("Results", []))
        self.assertEqual(result.returncode, 1 if count else 0, result.stderr)
        return result.returncode

    def test_all_reviewed_cves_are_scoped_exceptions(self):
        ids = re.findall(r"^  - id: (CVE-[0-9-]+)$", self.policy.read_text(), re.M)
        self.assertTrue(ids)
        self.assertEqual(len(ids), len(set(ids)))
        fixture = copy.deepcopy(self.fixture)
        original = fixture["Results"][0]["Vulnerabilities"][0]
        fixture["Results"][0]["Vulnerabilities"] = [dict(original, VulnerabilityID=cve) for cve in ids]
        self.assertEqual(self.gate(fixture), 0)

    def test_different_binary_path_fails(self):
        self.fixture["Results"][0]["Target"] = "usr/local/bin/another-application"
        self.assertEqual(self.gate(), 1)

    def test_different_go_version_fails(self):
        vulnerability = self.fixture["Results"][0]["Vulnerabilities"][0]
        vulnerability["InstalledVersion"] = "v1.24.7"
        vulnerability["PkgIdentifier"]["PURL"] = "pkg:golang/stdlib@v1.24.7"
        self.assertEqual(self.gate(), 1)

    def test_different_package_fails(self):
        vulnerability = self.fixture["Results"][0]["Vulnerabilities"][0]
        vulnerability["PkgName"] = "github.com/moby/sys/user"
        vulnerability["PkgIdentifier"]["PURL"] = "pkg:golang/github.com/moby/sys/user@v0.1.0"
        self.assertEqual(self.gate(), 1)

    def test_new_cve_fails(self):
        self.fixture["Results"][0]["Vulnerabilities"][0]["VulnerabilityID"] = "CVE-2099-99999"
        self.assertEqual(self.gate(), 1)

    def test_expired_exception_fails(self):
        expired = self.directory / "expired.yaml"
        expired.write_text(re.sub(r"expired_at: [0-9-]+", "expired_at: 2000-01-01", self.policy.read_text()))
        self.assertEqual(self.gate(policy=expired), 1)


if __name__ == "__main__":
    unittest.main()
