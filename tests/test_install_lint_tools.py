"""Native linter manifest and installation checks without network or release executables."""

import copy
import hashlib
import io
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import install_lint_tools as installer


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        self.payload = b"test executable contents"
        self.specification = {
            "repository": "example/linter",
            "assets": {
                "linux-x86_64": {
                    "version": "v1.2.3",
                    "sha256": hashlib.sha256(self.payload).hexdigest(),
                    "filenameTemplate": "linter_{version}_linux_amd64",
                }
            },
        }

    def test_mixed_versions_rejected_even_with_cached_binary(self):
        specification = copy.deepcopy(self.specification)
        specification["assets"]["linux-arm64"] = {
            **specification["assets"]["linux-x86_64"], "version": "v1.2.4"
        }
        with patch.object(installer, "has_version") as check:
            with self.assertRaisesRegex(ValueError, "one version"):
                installer.install_binary("linter", specification, "linux-x86_64")
            check.assert_not_called()

    def test_invalid_release_tags_rejected(self):
        for tag in ("1.2.3", "latest", "v1.2.3/other", "v1.2.3-rc1"):
            with self.subTest(tag=tag):
                self.specification["assets"]["linux-x86_64"]["version"] = tag
                with self.assertRaisesRegex(ValueError, "Invalid release tag"):
                    installer.tool_version(self.specification)

    def test_bad_download_checksum_removes_file(self):
        destination = self.directory / "download"
        with patch.object(installer.urllib.request, "urlretrieve", self.retrieve):
            with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
                installer.download("https://example.invalid/file", "0" * 64, destination)
        self.assertFalse(destination.exists())

    def retrieve(self, url, destination):
        Path(destination).write_bytes(self.payload)

    def install(self, specification, version_matches=True):
        with (
            patch.object(installer, "TOOLS", self.directory),
            patch.object(installer, "BIN", self.bin),
            patch.object(installer.shutil, "which", return_value=None),
            patch.object(installer, "has_version", return_value=version_matches),
            patch.object(installer.urllib.request, "urlretrieve", side_effect=self.retrieve) as fetch,
        ):
            installer.install_binary("linter", specification, "linux-x86_64")
            return fetch.call_args.args[0]

    def test_versioned_download_url_and_verified_binary(self):
        url = self.install(self.specification)
        self.assertEqual(
            url, "https://github.com/example/linter/releases/download/v1.2.3/linter_1.2.3_linux_amd64"
        )
        self.assertEqual((self.bin / "linter").read_bytes(), self.payload)
        self.assertTrue((self.bin / "linter").stat().st_mode & 0o111)

    def test_archive_extracts_only_named_executable(self):
        archive_bytes = io.BytesIO()
        with tarfile.open(fileobj=archive_bytes, mode="w:gz") as archive:
            for name, contents in (("tool/linter", self.payload), ("tool/README", b"readme")):
                member = tarfile.TarInfo(name)
                member.size = len(contents)
                archive.addfile(member, io.BytesIO(contents))
        expected = self.payload
        self.payload = archive_bytes.getvalue()
        self.specification["assets"]["linux-x86_64"].update(
            filenameTemplate="linter_{version}_linux_amd64.tar.gz",
            sha256=hashlib.sha256(self.payload).hexdigest(),
        )
        self.install(self.specification)
        self.assertEqual((self.bin / "linter").read_bytes(), expected)
        self.assertFalse((self.bin / "README").exists())

    def test_wrong_executable_version_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unexpected linter version"):
            self.install(self.specification, version_matches=False)

    def test_platform_without_asset_reports_required_version(self):
        with patch.object(installer.shutil, "which", return_value=None):
            with self.assertRaisesRegex(ValueError, "Install linter 1.2.3 on PATH first"):
                installer.install_binary("linter", self.specification, "unsupported")


if __name__ == "__main__":
    unittest.main()
