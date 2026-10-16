"""Skutečné dočasné Git stromy a ZIPy, žádný remote ani publikace."""

import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from scripts.build_release import build_release
from scripts.verify_release_package import verify_existing_installer


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="mnd-synthetic-release-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.git("init", "-b", "master_HA")
        self.git("config", "user.name", "Synthetic Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "core.autocrlf", "false")
        component = self.root / "custom_components/mnd_tariff_accounting"
        component.mkdir(parents=True)
        (component / "manifest.json").write_text(
            json.dumps({"domain": "mnd_tariff_accounting", "version": "0.1.0"}), encoding="utf-8"
        )
        (component / "__init__.py").write_text(
            '"""synthetic committed runtime"""\n', encoding="utf-8", newline="\n"
        )
        (self.root / "CHANGELOG.md").write_text(
            "## 0.1.0\n### Čeština\nSyntetické ověření.\n### English\nSynthetic verification.\n",
            encoding="utf-8",
        )
        self.git("add", ".")
        self.git("commit", "-m", "Synthetic fixture")
        self.git("tag", "v0.1.0")

    def git(self, *args):
        return subprocess.check_output(["git", *args], cwd=self.root, stderr=subprocess.DEVNULL)

    def test_reproducible_tag_build_ignores_local_changes_and_private_files(self):
        before, notes = build_release(self.root, "v0.1.0", "v0.1.0")
        (self.root / "custom_components/mnd_tariff_accounting/__init__.py").write_text(
            "LOCAL UNCOMMITTED\n"
        )
        (self.root / "private.txt").write_text("synthetic private marker")
        after, _ = build_release(self.root, "v0.1.0", "v0.1.0")
        self.assertEqual(before, after)
        with ZipFile(io.BytesIO(after)) as package:
            self.assertEqual(set(package.namelist()), {"manifest.json", "__init__.py"})
            self.assertIn(b"committed runtime", package.read("__init__.py"))
        self.assertIn("Čeština", notes)
        self.assertIn("English", notes)

    def test_matching_version_does_not_allow_different_commit(self):
        (self.root / "marker.txt").write_text("second commit, same manifest")
        self.git("add", ".")
        self.git("commit", "-m", "Second fixture")
        with self.assertRaisesRegex(ValueError, "different commit"):
            build_release(self.root, "HEAD", "v0.1.0")

    def test_wrong_version_or_missing_tag_fails(self):
        with self.assertRaises(ValueError):
            build_release(self.root, "HEAD", "v9.9.9")
        self.git("tag", "-d", "v0.1.0")
        with self.assertRaises(subprocess.CalledProcessError):
            build_release(self.root, "HEAD", "v0.1.0")

    def test_existing_installer_content_change_rejected_but_crlf_allowed(self):
        content, _ = build_release(self.root, "v0.1.0", "v0.1.0")
        built, other = self.root / "built.zip", self.root / "existing.zip"
        built.write_bytes(content)
        with ZipFile(io.BytesIO(content)) as source, ZipFile(other, "w") as target:
            for name in source.namelist():
                target.writestr(name, source.read(name).replace(b"\n", b"\r\n"))
        verify_existing_installer(built, other, "v0.1.0")
        with ZipFile(io.BytesIO(content)) as source, ZipFile(other, "w") as target:
            for name in source.namelist():
                target.writestr(
                    name, b"changed code" if name == "__init__.py" else source.read(name)
                )
        with self.assertRaisesRegex(ValueError, "differs"):
            verify_existing_installer(built, other, "v0.1.0")
