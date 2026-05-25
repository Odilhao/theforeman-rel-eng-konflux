"""Tests for lib.config — version validation and settings loading."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

# Ensure hack/branch-release/ is on sys.path (conftest.py handles this under
# pytest, but we guard here for direct unittest execution).
_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

import pytest  # noqa: E402

from lib.config import ReleaseConfig, _validate_version, load_config  # noqa: E402


@pytest.mark.parametrize("version", ["3.19", "3.20", "4.0", "10.1"])
def test_valid_version(version: str) -> None:
    _validate_version(version)


@pytest.mark.parametrize(
    "version",
    ["3.19.1", "3.19.0", "nightly", "", "3", "abc", "abc.def"],
)
def test_invalid_version(version: str) -> None:
    with pytest.raises(SystemExit) as exc_info:
        _validate_version(version)
    assert exc_info.value.code == 1


class TestLoadConfig(unittest.TestCase):
    """Integration test: load the actual releases/foreman/3.19/settings file."""

    def test_load_3_19_settings(self) -> None:
        cfg = load_config("3.19")
        self.assertIsInstance(cfg, ReleaseConfig)
        self.assertEqual(cfg.version, "3.19")
        self.assertEqual(cfg.branch_name, "foreman-3.19")
        self.assertIn("theforeman/foreman-oci-images", cfg.oci_repos)
        self.assertIn("theforeman/pulp-oci-images", cfg.oci_repos)
        self.assertIn("theforeman/candlepin-oci-images", cfg.oci_repos)
        self.assertIn("3.19", cfg.release_tags)
        self.assertIn("3.19.0-rc1", cfg.release_tags)
        self.assertEqual(
            cfg.rpm_check_url,
            "https://yum.theforeman.org/releases/3.19/el9/x86_64/repodata/repomd.xml",
        )
        self.assertEqual(cfg.rpm_check_timeout, 14400)
        self.assertEqual(cfg.katello_version, "4.21")
        self.assertEqual(cfg.pulp_version, "3.105")
        self.assertEqual(cfg.candlepin_version, "4.7")
        self.assertEqual(cfg.candlepin_version_xyz, "4.7.4")

    def test_invalid_version_raises_exit(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            load_config("3.19.1")
        self.assertEqual(ctx.exception.code, 1)

    def test_missing_settings_file_raises_exit(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            load_config("9.99")
        self.assertEqual(ctx.exception.code, 1)

    def test_oci_repos_is_list(self) -> None:
        cfg = load_config("3.19")
        self.assertIsInstance(cfg.oci_repos, list)
        self.assertGreater(len(cfg.oci_repos), 0)

    def test_release_tags_is_list(self) -> None:
        cfg = load_config("3.19")
        self.assertIsInstance(cfg.release_tags, list)
        self.assertGreater(len(cfg.release_tags), 0)

    def test_rpm_check_timeout_is_int(self) -> None:
        cfg = load_config("3.19")
        self.assertIsInstance(cfg.rpm_check_timeout, int)


if __name__ == "__main__":
    unittest.main()
