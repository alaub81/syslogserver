"""Exercise complete publication receipts, history selection and safe release creation."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import create_release_notes
from create_release_notes import publication_images, previous_tag, publish_notes, render


class ReleaseNotesTests(unittest.TestCase):
    def setUp(self):
        self.tag = "v2.0.0"
        self.sha = "a" * 40
        self.repository = "owner/syslogserver"
        self.matrix = {
            "include": [
                {
                    "image": image,
                    "ref": self.tag,
                    "sha": self.sha,
                    "repository": f"ghcr.io/owner/{image}",
                    "aliases": ["2.0.0", "latest"],
                    "mode": "reuse" if image == "dbcleanup" else "build",
                }
                for image in ("syslogng", "loganalyzer", "dbcleanup")
            ]
        }
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.receipts = Path(self.directory.name)
        for entry in self.matrix["include"]:
            directory = self.receipts / entry["image"]
            directory.mkdir()
            (directory / "checked-images.json").write_text(
                json.dumps({"entry": entry, "images": {"amd64": {}, "arm64": {}}})
            )
            (directory / "published.json").write_text(
                json.dumps(
                    {
                        "digest": "sha256:" + "b" * 64,
                        "manifests": [
                            {
                                "digest": "sha256:" + char * 64,
                                "platform": {"os": "linux", "architecture": arch},
                            }
                            for arch, char in (("amd64", "c"), ("arm64", "d"))
                        ],
                    }
                )
            )

    def images(self):
        return publication_images(self.tag, self.repository, self.sha, self.matrix, self.receipts)

    def test_semver_previous_ignores_prereleases_and_higher_tags(self):
        self.assertEqual(
            previous_tag("v2.0.0", ["v1.9.0", "v1.10.0", "v3.0.0", "v2.0.0-rc1"]), "v1.10.0"
        )
        self.assertIsNone(previous_tag("v1.0.0", ["unrelated", "v2.0.0"]))
        with self.assertRaises(ValueError):
            previous_tag("v2.0.0-rc1", [])

    def test_complete_publication_includes_reused_images(self):
        images, latest = self.images()
        self.assertEqual(set(images), {"syslogng", "loganalyzer", "dbcleanup"})
        self.assertTrue(latest)

    def test_missing_publication_and_missing_plan_fail(self):
        (self.receipts / "dbcleanup/published.json").unlink()
        with self.assertRaises(OSError):
            self.images()
        self.matrix["include"].pop()
        with self.assertRaises(ValueError):
            self.images()

    def test_mismatched_commit_duplicate_and_platform_fail(self):
        receipt = self.receipts / "syslogng/checked-images.json"
        original = receipt.read_text()
        data = json.loads(original)
        data["entry"]["sha"] = "f" * 40
        receipt.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.images()
        receipt.write_text(original)
        duplicate = self.receipts / "duplicate"
        duplicate.mkdir()
        (duplicate / receipt.name).write_text(original)
        with self.assertRaises(ValueError):
            self.images()
        (duplicate / receipt.name).unlink()
        published = receipt.parent / "published.json"
        data = json.loads(published.read_text())
        data["manifests"][1]["platform"]["architecture"] = "amd64"
        published.write_text(json.dumps(data))
        with self.assertRaises(ValueError):
            self.images()

    def test_direct_commits_are_escaped_and_initial_release_links_source(self):
        images, _ = self.images()
        text = render(
            self.tag,
            None,
            [(self.sha, "Fix [link](bad) @everyone <script> | title")],
            self.repository,
            images,
        )
        self.assertIn("&#64;everyone &lt;script&gt;", text)
        self.assertIn("\\[link\\]\\(bad\\)", text)
        self.assertIn(f"/commit/{self.sha}", text)
        self.assertIn("/tree/v2.0.0", text)
        self.assertNotIn("/compare/", text)
        self.assertIn("ghcr.io/owner/dbcleanup:2.0.0", text)
        self.assertIn(
            "/compare/v1.9.0...v2.0.0", render(self.tag, "v1.9.0", [], self.repository, images)
        )

    def test_generation_uses_reachable_history_and_includes_direct_commits(self):
        repository = self.receipts / "git"
        repository.mkdir()

        def git(*args):
            return subprocess.check_output(
                ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid", *args],
                cwd=repository,
                text=True,
            ).strip()

        git("init", "--quiet")
        git("commit", "--quiet", "--allow-empty", "-m", "Initial source")
        git("tag", "v1.9.0")
        git("commit", "--quiet", "--allow-empty", "-m", "Earlier feature")
        git("tag", "v1.10.0")
        git("commit", "--quiet", "--allow-empty", "-m", "Direct new feature")
        git("tag", self.tag)
        unrelated = git("commit-tree", "HEAD^{tree}", "-m", "Unreachable history")
        git("tag", "v1.99.0", unrelated)
        sha = git("rev-parse", "HEAD")
        for entry in self.matrix["include"]:
            entry["sha"] = sha
            receipt = self.receipts / entry["image"] / "checked-images.json"
            checked = json.loads(receipt.read_text())
            checked["entry"] = entry
            receipt.write_text(json.dumps(checked))
        output = self.receipts / "notes.md"
        with (
            patch.object(create_release_notes, "ROOT", repository),
            patch(
                "sys.argv",
                [
                    "create_release_notes.py",
                    "--tag",
                    self.tag,
                    "--repository",
                    self.repository,
                    "--matrix",
                    json.dumps(self.matrix),
                    "--receipts",
                    str(self.receipts),
                    "--output",
                    str(output),
                ],
            ),
        ):
            create_release_notes.main()
        text = output.read_text()
        self.assertIn("Direct new feature", text)
        self.assertNotIn("Earlier feature", text)
        self.assertIn("/compare/v1.10.0...v2.0.0", text)

    def test_existing_release_including_draft_is_preserved(self):
        execute = Mock(return_value="v1.0.0\nv2.0.0")
        publish_notes(self.tag, self.repository, Path("notes.md"), True, execute)
        self.assertEqual(execute.call_count, 1)
        self.assertIn("--paginate", execute.call_args.args)

    def test_api_failure_does_not_create_release(self):
        execute = Mock(side_effect=subprocess.CalledProcessError(1, ["gh"]))
        with self.assertRaises(subprocess.CalledProcessError):
            publish_notes(self.tag, self.repository, Path("notes.md"), True, execute)
        self.assertEqual(execute.call_count, 1)

    def test_new_older_release_verifies_remote_tag_and_is_not_latest(self):
        execute = Mock(side_effect=["v3.0.0", "created"])
        publish_notes(self.tag, self.repository, Path("notes.md"), False, execute)
        args = execute.call_args.args
        self.assertIn("--verify-tag", args)
        self.assertIn("--latest=false", args)
        self.assertIn("--notes-file", args)


if __name__ == "__main__":
    unittest.main()
