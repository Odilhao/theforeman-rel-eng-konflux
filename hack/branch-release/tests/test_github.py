"""Tests for lib.github — validate_remotes logic."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.github import open_pr, validate_remotes  # noqa: E402


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


class TestOpenPr(unittest.TestCase):
    """open_pr idempotency and --repo flag tests."""

    def _make_run(self, list_stdout: str, create_stdout: str = "") -> MagicMock:
        """Return a _run mock: first call (pr list) returns list_stdout, second (pr create) returns create_stdout."""
        list_result = MagicMock()
        list_result.stdout = list_stdout
        create_result = MagicMock()
        create_result.stdout = create_stdout
        mock = MagicMock(side_effect=[list_result, create_result])
        return mock

    def test_returns_existing_pr_when_found(self) -> None:
        """If gh pr list finds a PR, open_pr returns its URL without calling gh pr create."""
        existing_url = "https://github.com/theforeman/foreman-oci-images/pull/40"
        mock_run = MagicMock(return_value=_run_returning(existing_url))
        with patch("lib.github._run", mock_run):
            url = open_pr("T", "B", "foreman-3.19", "someuser:foreman-3.19",
                          draft=True, cwd=Path("/w"), dry_run=False,
                          repo="theforeman/foreman-oci-images")
        self.assertEqual(url, existing_url)
        # Only the pr list call should have been made.
        self.assertEqual(mock_run.call_count, 1)
        list_cmd = mock_run.call_args[0][0]
        self.assertIn("--repo", list_cmd)
        self.assertIn("theforeman/foreman-oci-images", list_cmd)
        # gh pr list --head takes branch name only, not user:branch.
        self.assertIn("foreman-3.19", list_cmd)
        self.assertNotIn("someuser:foreman-3.19", list_cmd)

    def test_null_jq_output_not_treated_as_existing_pr(self) -> None:
        """jq .[0].url on an empty list emits 'null'; open_pr must not treat that as a valid URL."""
        list_result = _run_returning("null")
        create_result = _run_returning("https://github.com/theforeman/foreman-oci-images/pull/99")
        mock_run = MagicMock(side_effect=[list_result, create_result])
        with patch("lib.github._run", mock_run):
            url = open_pr("T", "B", "foreman-3.19", "someuser:foreman-3.19",
                          draft=True, cwd=Path("/w"), dry_run=False)
        # Should have called pr create after seeing "null".
        self.assertEqual(mock_run.call_count, 2)
        self.assertIn("pull/99", url)

    def test_repo_flag_passed_to_pr_create(self) -> None:
        """When repo= is given, --repo is included in the gh pr create command."""
        list_result = _run_returning("")
        create_result = _run_returning("https://github.com/theforeman/foreman-oci-images/pull/99")
        mock_run = MagicMock(side_effect=[list_result, create_result])
        with patch("lib.github._run", mock_run):
            open_pr("T", "B", "foreman-3.19", "someuser:foreman-3.19",
                    draft=True, cwd=Path("/w"), dry_run=False,
                    repo="theforeman/foreman-oci-images")
        create_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("--repo", create_cmd)
        self.assertIn("theforeman/foreman-oci-images", create_cmd)

    def test_fallback_on_create_failure(self) -> None:
        """If gh pr create fails, open_pr retries gh pr list and returns existing URL."""
        list_empty = _run_returning("")
        existing_url = "https://github.com/theforeman/foreman-oci-images/pull/40"
        list_found = _run_returning(existing_url)
        create_error = subprocess.CalledProcessError(1, ["gh", "pr", "create"])

        mock_run = MagicMock(side_effect=[list_empty, create_error, list_found])
        with patch("lib.github._run", mock_run):
            url = open_pr("T", "B", "foreman-3.19", "someuser:foreman-3.19",
                          draft=True, cwd=Path("/w"), dry_run=False)
        self.assertEqual(url, existing_url)
        self.assertEqual(mock_run.call_count, 3)

    def test_dry_run_prints_and_returns_placeholder(self) -> None:
        mock_run = MagicMock()
        with patch("lib.github._run", mock_run), \
             patch("lib.github._dry_print"):
            url = open_pr("T", "B", "base", "head",
                          draft=False, cwd=Path("/w"), dry_run=True)
        mock_run.assert_not_called()
        self.assertIn("dry-run", url)


if __name__ == "__main__":
    unittest.main()
