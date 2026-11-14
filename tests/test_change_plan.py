"""Exercise the dependency graph and fail-safe diff handling."""

import subprocess
import tempfile
import unittest

from change_plan import IMAGES, affected_images, changed_files, ci_plan


class ChangePlanTests(unittest.TestCase):
    def test_docs_skip_builds_and_behavior_tests(self):
        for files in (["README.md"], ["docs/operations.md", ".github/FUNDING.yml"], []):
            with self.subTest(files=files):
                self.assertEqual(
                    ci_plan(files), {"runtime": False, "tests": False, "affected": [], "build": []}
                )

    def test_single_image_records_direct_change_and_stack_closure(self):
        plan = ci_plan(["resources/dbcleanup/dbcleanup.sh"])
        self.assertEqual(plan["affected"], ["dbcleanup"])
        self.assertEqual(plan["build"], list(IMAGES))
        self.assertTrue(plan["tests"])

    def test_runtime_configuration_shared_inputs_and_unknown_paths_run_everything(self):
        for path in (
            "compose.yml",
            ".github/workflows/ci.yml",
            ".dockerignore",
            "tests/compose.test.yml",
            "tools/change_plan.py",
            "data/init.sql",
            "unknown",
        ):
            with self.subTest(path=path):
                self.assertEqual(affected_images([path]), list(IMAGES))
        self.assertEqual(affected_images(None), list(IMAGES))

    def test_lint_only_updates_run_tests_without_application_builds(self):
        for name in ("lint-tools.json", "renovate.json", "tests/install_lint_tools.py"):
            with self.subTest(name=name):
                plan = ci_plan([name])
                self.assertFalse(plan["runtime"])
                self.assertTrue(plan["tests"])
                self.assertEqual(plan["build"], [])

    def test_invalid_or_missing_base_never_skips_checks(self):
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run(["git", "init", "-q", directory], check=True)
            for base in (None, "0" * 40, "missing-commit"):
                with self.subTest(base=base):
                    self.assertIsNone(changed_files(base, directory=directory))
                    self.assertTrue(ci_plan(changed_files(base, directory=directory))["runtime"])


if __name__ == "__main__":
    unittest.main()
