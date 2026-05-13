"""Tests for lib.github — validate_remotes logic."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.github import validate_remotes  # noqa: E402


def _make_remote_output(*remotes: tuple[str, str]) -> str:
    """Build a fake `git remote -v` stdout string."""
    lines = []
    for name, url in remotes:
        lines.append(f"{name}\t{url} (fetch)")
        lines.append(f"{name}\t{url} (push)")
    return "\n".join(lines)


def _run_returning(stdout: str) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    return result


class TestValidateRemotes(unittest.TestCase):

    def _call(self, stdout: str) -> tuple[str, str]:
        with patch("lib.github._run", return_value=_run_returning(stdout)):
            return validate_remotes(Path("/fake/repo"))

    def _call_raises(self, stdout: str) -> SystemExit:
        with patch("lib.github._run", return_value=_run_returning(stdout)):
            with self.assertRaises(SystemExit) as ctx:
                validate_remotes(Path("/fake/repo"))
        return ctx.exception

    # ------------------------------------------------------------------
    # Happy paths
    # ------------------------------------------------------------------

    def test_https_remotes_accepted(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "https://github.com/theforeman/foreman-oci-images.git"),
            ("origin", "https://github.com/myuser/foreman-oci-images.git"),
        )
        upstream_url, origin_url = self._call(stdout)
        self.assertIn("theforeman", upstream_url)
        self.assertIn("myuser", origin_url)

    def test_ssh_remotes_accepted(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "git@github.com:theforeman/foreman-oci-images.git"),
            ("origin", "git@github.com:myuser/foreman-oci-images.git"),
        )
        upstream_url, origin_url = self._call(stdout)
        self.assertIn("theforeman", upstream_url)

    # ------------------------------------------------------------------
    # Error paths
    # ------------------------------------------------------------------

    def test_missing_upstream_raises(self) -> None:
        stdout = _make_remote_output(
            ("origin", "https://github.com/myuser/foreman-oci-images.git"),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_missing_origin_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "https://github.com/theforeman/foreman-oci-images.git"),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_upstream_pointing_to_wrong_org_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "https://github.com/someoneelse/foreman-oci-images.git"),
            ("origin", "https://github.com/myuser/foreman-oci-images.git"),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_origin_pointing_to_theforeman_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "https://github.com/theforeman/foreman-oci-images.git"),
            ("origin", "https://github.com/theforeman/foreman-oci-images.git"),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_notgithub_domain_does_not_match_theforeman(self) -> None:
        """notgithub.com:theforeman/ must not be accepted as upstream."""
        stdout = _make_remote_output(
            ("upstream", "https://notgithub.com/theforeman/foreman-oci-images.git"),
            ("origin", "https://github.com/myuser/foreman-oci-images.git"),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)


if __name__ == "__main__":
    unittest.main()
