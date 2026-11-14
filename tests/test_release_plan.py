"""Reject stale/untrusted CI and keep immutable image reuse appropriately scoped."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from release_plan import build_paths, plan_images, registry_source, require_ci


class ReleasePlanTests(unittest.TestCase):
    def setUp(self):
        self.sha = "a" * 40
        self.run = {
            "head_sha": self.sha,
            "event": "push",
            "head_branch": "main",
            "run_number": 5,
            "run_attempt": 1,
            "status": "completed",
            "conclusion": "success",
        }
        self.release = {"ref": "v2.0.0", "aliases": ["2.0.0", "2.0", "2", "latest"]}

    def test_exact_main_ci_is_required(self):
        require_ci([self.run], self.sha)
        for runs in (
            [],
            [dict(self.run, head_sha="b" * 40)],
            [dict(self.run, event="pull_request")],
            [dict(self.run, head_branch="untrusted")],
            [dict(self.run, conclusion="failure")],
            [dict(self.run, status="in_progress")],
        ):
            with self.subTest(runs=runs), self.assertRaises(ValueError):
                require_ci(runs, self.sha)

    def test_newer_running_or_failed_attempt_overrides_old_success(self):
        for changed in (
            {"run_number": 6, "status": "queued"},
            {"run_attempt": 2, "conclusion": "failure"},
        ):
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                require_ci([self.run, dict(self.run, **changed)], self.sha)

    def plan(self, files, inspect=None, refresh=False, previous="v1.9.0"):
        return plan_images(
            self.release,
            self.sha,
            previous,
            files,
            "Owner",
            inspect or (lambda ref: ref.split(":")[0] + "@sha256:" + "b" * 64),
            refresh,
        )

    def test_only_changed_image_builds_and_other_images_reuse_digest(self):
        entries = self.plan(["resources/syslogng/Dockerfile"])
        self.assertEqual([e["image"] for e in entries if e["mode"] == "build"], ["syslogng"])
        self.assertTrue(all("@sha256:" in e["source"] for e in entries if e["mode"] == "reuse"))
        self.assertTrue(all(e["repository"].startswith("ghcr.io/owner/") for e in entries))

    def test_docs_only_reuse_all_and_missing_image_builds(self):
        self.assertTrue(all(e["mode"] == "reuse" for e in self.plan(["README.md"])))
        entries = self.plan(["README.md"], lambda ref: None if "/dbcleanup:" in ref else "digest")
        self.assertEqual([e["image"] for e in entries if e["mode"] == "build"], ["dbcleanup"])

    def test_refresh_first_release_and_unknown_diff_build_all(self):
        for args in ({"refresh": True}, {"previous": None}, {}):
            self.assertTrue(all(e["mode"] == "build" for e in self.plan(None, **args)))

    def test_registry_auth_failure_is_not_a_missing_image(self):
        with patch(
            "release_plan.subprocess.run", return_value=Mock(returncode=1, stderr="unauthorized")
        ):
            with self.assertRaisesRegex(ValueError, "authentication/network"):
                registry_source("ghcr.io/owner/image:1.0.0")
        with patch(
            "release_plan.subprocess.run",
            return_value=Mock(returncode=1, stderr="manifest unknown"),
        ):
            self.assertIsNone(registry_source("ghcr.io/owner/image:1.0.0"))

    def test_current_and_historical_layouts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy = root / "Dockerfile-syslogng"
            legacy.touch()
            self.assertEqual(build_paths(root, "syslogng"), (str(root), str(legacy)))
            current = root / "resources/syslogng/Dockerfile"
            current.parent.mkdir(parents=True)
            current.touch()
            self.assertEqual(build_paths(root, "syslogng"), (str(current.parent), str(current)))
            with self.assertRaises(ValueError):
                build_paths(root, "loganalyzer")

    def test_ci_api_errors_propagate(self):
        # An unavailable API never yields an implicit successful result.
        from release_plan import fetch_ci

        with patch.dict("os.environ", GH_TOKEN="test-token"):
            with patch("release_plan.urllib.request.urlopen", side_effect=OSError("offline")):
                with self.assertRaises(OSError):
                    fetch_ci("owner/repo", self.sha)


if __name__ == "__main__":
    unittest.main()
