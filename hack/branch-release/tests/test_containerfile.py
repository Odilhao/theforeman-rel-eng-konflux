"""Tests for lib.containerfile.patch_arg."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.containerfile import patch_arg  # noqa: E402


class TestPatchArg(unittest.TestCase):
    """patch_arg correctness and idempotency tests."""

    def _write_containerfile(self, tmpdir: str, content: str) -> Path:
        p = Path(tmpdir) / "Containerfile"
        p.write_text(content)
        return p

    # ------------------------------------------------------------------
    # 1. Basic patch: ARG FOREMAN_VERSION=nightly -> 3.19
    # ------------------------------------------------------------------
    def test_patch_foreman_version(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cf = self._write_containerfile(
                tmpdir,
                "FROM registry.fedoraproject.org/fedora:latest\nARG FOREMAN_VERSION=nightly\nRUN echo hi\n",
            )
            result = patch_arg(cf, "FOREMAN_VERSION", "3.19", dry_run=False)
            self.assertTrue(result, "Expected True (file was modified)")
            content = cf.read_text()
            self.assertIn("ARG FOREMAN_VERSION=3.19", content)
            self.assertNotIn("ARG FOREMAN_VERSION=nightly", content)

    # ------------------------------------------------------------------
    # 2. Idempotency: already correct value -> returns False, file unchanged
    # ------------------------------------------------------------------
    def test_idempotent_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cf = self._write_containerfile(
                tmpdir,
                "ARG FOREMAN_VERSION=nightly\n",
            )
            # First call — modifies file
            patch_arg(cf, "FOREMAN_VERSION", "3.19", dry_run=False)
            mtime_after_first = cf.stat().st_mtime_ns

            # Second call — value already correct, should be a no-op
            result = patch_arg(cf, "FOREMAN_VERSION", "3.19", dry_run=False)
            self.assertFalse(result, "Expected False (already correct, no write)")
            mtime_after_second = cf.stat().st_mtime_ns
            self.assertEqual(
                mtime_after_first,
                mtime_after_second,
                "File should not be rewritten when value is already correct",
            )

    # ------------------------------------------------------------------
    # 3. dry_run=True: returns True but does not write
    # ------------------------------------------------------------------
    def test_dry_run_no_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = "ARG FOREMAN_VERSION=nightly\n"
            cf = self._write_containerfile(tmpdir, original)
            result = patch_arg(cf, "FOREMAN_VERSION", "3.19", dry_run=True)
            self.assertTrue(result, "dry_run should still return True (would modify)")
            self.assertEqual(cf.read_text(), original, "dry_run must not write the file")

    # ------------------------------------------------------------------
    # 4. ARG VERSION= (pulp / candlepin pattern)
    # ------------------------------------------------------------------
    def test_patch_version_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cf = self._write_containerfile(tmpdir, "ARG VERSION=nightly\n")
            result = patch_arg(cf, "VERSION", "4.7", dry_run=False)
            self.assertTrue(result)
            self.assertIn("ARG VERSION=4.7", cf.read_text())

    # ------------------------------------------------------------------
    # 5. ARG VERSION_XYZ= (candlepin pattern)
    # ------------------------------------------------------------------
    def test_patch_version_xyz_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cf = self._write_containerfile(tmpdir, "ARG VERSION_XYZ=nightly\n")
            result = patch_arg(cf, "VERSION_XYZ", "4.7.4", dry_run=False)
            self.assertTrue(result)
            self.assertIn("ARG VERSION_XYZ=4.7.4", cf.read_text())

    # ------------------------------------------------------------------
    # 6. ARG KATELLO_VERSION= (foreman pattern)
    # ------------------------------------------------------------------
    def test_patch_katello_version_arg(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cf = self._write_containerfile(tmpdir, "ARG KATELLO_VERSION=nightly\n")
            result = patch_arg(cf, "KATELLO_VERSION", "4.15", dry_run=False)
            self.assertTrue(result)
            self.assertIn("ARG KATELLO_VERSION=4.15", cf.read_text())

    # ------------------------------------------------------------------
    # 7. Missing ARG name -> SystemExit(1)
    # ------------------------------------------------------------------
    def test_missing_arg_raises_exit(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cf = self._write_containerfile(tmpdir, "ARG SOME_OTHER_ARG=value\n")
            with self.assertRaises(SystemExit) as ctx:
                patch_arg(cf, "FOREMAN_VERSION", "3.19", dry_run=False)
            self.assertEqual(ctx.exception.code, 1)

    # ------------------------------------------------------------------
    # 8. Non-existent file -> SystemExit(1)
    # ------------------------------------------------------------------
    def test_missing_file_raises_exit(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            patch_arg(Path("/nonexistent/Containerfile"), "FOREMAN_VERSION", "3.19", dry_run=False)
        self.assertEqual(ctx.exception.code, 1)

    # ------------------------------------------------------------------
    # 9. Other lines in file are preserved
    # ------------------------------------------------------------------
    def test_other_lines_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            original = (
                "FROM fedora:latest\n"
                "ARG FOREMAN_VERSION=nightly\n"
                "ARG ANOTHER=value\n"
                "RUN echo done\n"
            )
            cf = self._write_containerfile(tmpdir, original)
            patch_arg(cf, "FOREMAN_VERSION", "3.19", dry_run=False)
            content = cf.read_text()
            self.assertIn("FROM fedora:latest", content)
            self.assertIn("ARG ANOTHER=value", content)
            self.assertIn("RUN echo done", content)


if __name__ == "__main__":
    unittest.main()
