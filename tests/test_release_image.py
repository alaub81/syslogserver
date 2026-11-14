"""Prove that failed scans or changed images cannot reach publication."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from release_image import ARCHES, local_tag, publish, scan


class ReleaseImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.reports = Path(self.temp.name)
        self.entry = {
            "ref": "v1.0.0",
            "sha": "a" * 40,
            "image": "syslogng",
            "repository": "ghcr.io/example/syslogng",
            "aliases": ["1.0.0", "latest"],
            "mode": "build",
            "source": "",
        }
        self.ids = {"amd64": "sha256:" + "1" * 64, "arm64": "sha256:" + "2" * 64}
        self.digests = {"amd64": "sha256:" + "3" * 64, "arm64": "sha256:" + "4" * 64}
        self.commands = []
        self.failed_scan = None
        self.bad_registry = False

    def execute(self, *args, **kwargs):
        self.commands.append(args)
        if args[:3] == ("docker", "image", "inspect"):
            arch = args[3].rsplit(":", 1)[1]
            return json.dumps([{"Os": "linux", "Architecture": arch, "Id": self.ids[arch]}])
        if args[0] == "bash" and self.failed_scan and self.failed_scan in args[-1]:
            raise subprocess.CalledProcessError(1, args)
        if args[:4] == ("docker", "buildx", "imagetools", "inspect"):
            reference = args[4]
            if reference.endswith(tuple(self.digests.values())):
                arch = next(arch for arch in ARCHES if reference.endswith(self.digests[arch]))
                return json.dumps(
                    {"config": {"digest": "wrong" if self.bad_registry else self.ids[arch]}}
                )
            if reference.endswith(("-amd64", "-arm64")):
                arch = reference.rsplit("-", 1)[1]
                return json.dumps({"digest": self.digests[arch]})
            return json.dumps(
                {
                    "digest": "sha256:" + "5" * 64,
                    "manifests": [{"digest": d} for d in self.digests.values()],
                }
            )
        return ""

    def test_scan_failure_still_checks_other_architecture_and_writes_no_receipt(self):
        self.failed_scan = "amd64"
        with self.assertRaisesRegex(ValueError, "validation failed"):
            scan(self.entry, self.reports, self.execute)
        self.assertTrue(any(cmd[0] == "bash" and "arm64" in cmd[-1] for cmd in self.commands))
        self.assertFalse((self.reports / "checked-images.json").exists())
        with self.assertRaises(FileNotFoundError):
            publish(self.entry, self.reports, self.execute)
        self.assertFalse(any(cmd[:2] == ("docker", "push") for cmd in self.commands))

    def test_success_publishes_exact_configs_without_building(self):
        scan(self.entry, self.reports, self.execute)
        with patch.dict(os.environ, GITHUB_RUN_ID="123"):
            publish(self.entry, self.reports, self.execute)
        self.assertFalse(any("build" in cmd for cmd in self.commands))
        final = self.commands[-1]
        self.assertIn("ghcr.io/example/syslogng:latest", final)
        self.assertIn("@sha256:", final[-1])
        self.assertTrue((self.reports / "published.json").exists())

    def test_changed_local_image_refuses_any_push(self):
        scan(self.entry, self.reports, self.execute)
        self.ids["arm64"] = "sha256:" + "9" * 64
        with self.assertRaisesRegex(ValueError, "differs"):
            publish(self.entry, self.reports, self.execute)
        self.assertFalse(any(cmd[:2] == ("docker", "push") for cmd in self.commands))

    def test_registry_mismatch_never_moves_release_alias(self):
        scan(self.entry, self.reports, self.execute)
        self.bad_registry = True
        with patch.dict(os.environ, GITHUB_RUN_ID="123"):
            with self.assertRaisesRegex(ValueError, "config/manifest differs"):
                publish(self.entry, self.reports, self.execute)
        self.assertFalse(any("ghcr.io/example/syslogng:latest" in cmd for cmd in self.commands))

    def test_wrong_plan_cannot_reuse_scan_receipt(self):
        scan(self.entry, self.reports, self.execute)
        with self.assertRaisesRegex(ValueError, "receipt"):
            publish(dict(self.entry, ref="v2.0.0"), self.reports, self.execute)

    def test_reused_images_are_scanned_as_well(self):
        entry = dict(self.entry, mode="reuse", source="ghcr.io/example/syslogng@sha256:" + "6" * 64)
        scan(entry, self.reports, self.execute)
        self.assertEqual(len([cmd for cmd in self.commands if cmd[0] == "bash"]), 2)
        self.assertEqual(local_tag(entry, "arm64"), "release-syslogng:arm64")

    def test_containerd_manifest_ids_are_not_mistaken_for_config_ids(self):
        self.digests = dict(self.ids)

        def modern_execute(*args, **kwargs):
            if args[:3] == ("docker", "image", "inspect"):
                arch = args[-1].rsplit(":", 1)[1]
                if "--platform" in args:
                    return json.dumps(
                        [
                            {
                                "Os": "linux",
                                "Architecture": arch,
                                "Id": self.ids[arch],
                                "Descriptor": {
                                    "mediaType": "application/vnd.oci.image.manifest.v1+json"
                                },
                            }
                        ]
                    )
                return json.dumps(
                    [
                        {
                            "Os": "linux",
                            "Architecture": "arm64",
                            "Id": "index-id",
                            "Descriptor": {"mediaType": "application/vnd.oci.image.index.v1+json"},
                        }
                    ]
                )
            if args[-1] == "--raw":
                return json.dumps({"config": {"digest": "different-config-id"}})
            return self.execute(*args, **kwargs)

        scan(self.entry, self.reports, modern_execute)
        with patch.dict(os.environ, GITHUB_RUN_ID="123"):
            publish(self.entry, self.reports, modern_execute)
        self.assertTrue((self.reports / "published.json").exists())


if __name__ == "__main__":
    unittest.main()
