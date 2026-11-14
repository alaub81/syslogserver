"""Validate real dependency extraction and the intended bot ownership boundary."""

import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]


class DependencyConfigTests(unittest.TestCase):
    def test_every_supercronic_download_is_extracted_and_updated_together(self):
        config = json.loads((ROOT / "renovate.json").read_text())
        manager = next(
            manager
            for manager in config["customManagers"]
            if manager.get("depNameTemplate") == "aptible/supercronic"
        )
        pattern = re.sub(r"\(\?<([A-Za-z]\w*)>", r"(?P<\1>", manager["matchStrings"][0])
        paths = manager["managerFilePatterns"][0][1:-1]
        extracted = []
        actual = []
        for dockerfile in ROOT.glob("resources/*/Dockerfile"):
            name = dockerfile.relative_to(ROOT).as_posix()
            text = dockerfile.read_text()
            if "aptible/supercronic/releases/download/" in text:
                actual.append(name)
            if re.search(paths, name):
                extracted.extend(
                    (name, match.group("currentValue")) for match in re.finditer(pattern, text)
                )
        self.assertTrue(actual)
        self.assertEqual(sorted(name for name, _ in extracted), sorted(actual))
        self.assertEqual(len({version for _, version in extracted}), 1)
        rule = next(
            rule
            for rule in config["packageRules"]
            if rule.get("matchPackageNames") == ["aptible/supercronic"]
        )
        self.assertEqual(set(rule["matchUpdateTypes"]), {"minor", "patch"})
        self.assertTrue(rule["automerge"])
        self.assertIsNone(rule["groupName"])
        self.assertFalse(config["vulnerabilityAlerts"]["enabled"])


if __name__ == "__main__":
    unittest.main()
