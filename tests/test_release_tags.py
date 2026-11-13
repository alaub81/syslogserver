"""Protect shared registry aliases when rebuilding older releases."""

import unittest

from release_tags import select_tags


class ReleaseTagsTests(unittest.TestCase):
    def setUp(self):
        self.tags = ["v1.9.0", "v1.9.2", "v1.10.0", "v2.0.0", "v2.1.0-rc1", "unrelated"]

    def test_latest_stable_gets_all_aliases(self):
        self.assertEqual(select_tags(self.tags), [
            {"ref": "v2.0.0", "aliases": ["2.0.0", "2.0", "2", "latest"]},
        ])

    def test_old_release_never_downgrades_shared_aliases(self):
        self.assertEqual(select_tags(self.tags, "v1.9.0"), [
            {"ref": "v1.9.0", "aliases": ["1.9.0"]},
        ])
        self.assertEqual(select_tags(self.tags, "v1.9.2")[0]["aliases"], ["1.9.2", "1.9"])
        self.assertEqual(select_tags(self.tags, "v1.10.0")[0]["aliases"], ["1.10.0", "1.10", "1"])

    def test_rebuilds_use_numeric_version_order(self):
        self.assertEqual([x["ref"] for x in select_tags(self.tags, count=3)],
                         ["v2.0.0", "v1.10.0", "v1.9.2"])

    def test_invalid_releases_and_counts_fail(self):
        for requested in ("v2.1.0-rc1", "v3.0.0", "v01.0.0"):
            with self.subTest(requested=requested), self.assertRaises(ValueError):
                select_tags(self.tags, requested)
        for count in (0, -1, 21):
            with self.subTest(count=count), self.assertRaises(ValueError):
                select_tags(self.tags, count=count)
        with self.assertRaises(ValueError):
            select_tags([])


if __name__ == "__main__":
    unittest.main()
