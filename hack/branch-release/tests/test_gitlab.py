"""Tests for lib.gitlab — validate_remotes, validate_fork, and open_mr logic."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.gitlab import open_mr, validate_fork, validate_remotes  # noqa: E402


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


_UPSTREAM_HTTPS = "https://gitlab.com/fedora/infrastructure/konflux/tenants-config.git"
_UPSTREAM_SSH = "git@gitlab.com:fedora/infrastructure/konflux/tenants-config.git"
_ORIGIN_HTTPS = "https://gitlab.com/myuser/tenants-config.git"
_ORIGIN_SSH = "git@gitlab.com:myuser/tenants-config.git"


class TestValidateRemotes(unittest.TestCase):

    def _call(self, stdout: str) -> tuple[str, str]:
        with patch("lib.gitlab._run", return_value=_run_returning(stdout)):
            return validate_remotes(Path("/fake/repo"))

    def _call_raises(self, stdout: str) -> SystemExit:
        with patch("lib.gitlab._run", return_value=_run_returning(stdout)):
            with self.assertRaises(SystemExit) as ctx:
                validate_remotes(Path("/fake/repo"))
        return ctx.exception

    # ------------------------------------------------------------------
    # Happy paths
    # ------------------------------------------------------------------

    def test_https_remotes_accepted(self) -> None:
        stdout = _make_remote_output(
            ("upstream", _UPSTREAM_HTTPS),
            ("origin", _ORIGIN_HTTPS),
        )
        upstream_url, origin_url = self._call(stdout)
        self.assertIn("tenants-config", upstream_url)
        self.assertIn("myuser", origin_url)

    def test_ssh_remotes_accepted(self) -> None:
        stdout = _make_remote_output(
            ("upstream", _UPSTREAM_SSH),
            ("origin", _ORIGIN_SSH),
        )
        upstream_url, origin_url = self._call(stdout)
        self.assertIn("tenants-config", upstream_url)
        self.assertIn("myuser", origin_url)

    # ------------------------------------------------------------------
    # Error paths
    # ------------------------------------------------------------------

    def test_missing_upstream_raises(self) -> None:
        stdout = _make_remote_output(("origin", _ORIGIN_HTTPS))
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_missing_origin_raises(self) -> None:
        stdout = _make_remote_output(("upstream", _UPSTREAM_HTTPS))
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_upstream_wrong_repo_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "https://gitlab.com/someoneelse/tenants-config.git"),
            ("origin", _ORIGIN_HTTPS),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_upstream_wrong_host_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", "https://notgitlab.com/fedora/infrastructure/konflux/tenants-config.git"),
            ("origin", _ORIGIN_HTTPS),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_origin_pointing_to_upstream_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", _UPSTREAM_HTTPS),
            ("origin", _UPSTREAM_HTTPS),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)

    def test_origin_pointing_to_upstream_ssh_raises(self) -> None:
        stdout = _make_remote_output(
            ("upstream", _UPSTREAM_SSH),
            ("origin", _UPSTREAM_SSH),
        )
        exc = self._call_raises(stdout)
        self.assertEqual(exc.code, 1)


class TestValidateFork(unittest.TestCase):

    def test_valid_fork_does_not_raise(self) -> None:
        with patch("lib.gitlab._run", return_value=_run_returning("")) as mock_run:
            validate_fork("fedora/infrastructure/konflux/tenants-config", "myuser")
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        self.assertNotIn("--hostname", call_args)
        self.assertTrue(
            any("https://gitlab.com/myuser/tenants-config" in a for a in call_args),
            f"expected full GitLab URL in call args, got: {call_args}",
        )
        call_kwargs = mock_run.call_args[1]
        self.assertEqual(call_kwargs.get("env", {}).get("GLAB_HOST"), "gitlab.com")

    def test_missing_fork_raises(self) -> None:
        import subprocess
        with patch("lib.gitlab._run", side_effect=subprocess.CalledProcessError(1, "glab")):
            with self.assertRaises(SystemExit) as ctx:
                validate_fork("fedora/infrastructure/konflux/tenants-config", "myuser")
        self.assertEqual(ctx.exception.code, 1)


class TestOpenMr(unittest.TestCase):

    _EXISTING_URL = "https://gitlab.com/myuser/tenants-config/-/merge_requests/42"

    def _fake_run_existing(self, existing_url: str):
        """Return a side_effect callable that returns JSON on first call, raises on second."""
        call_count = {"n": 0}
        json_response = f'[{{"web_url": "{existing_url}"}}]'

        def side_effect(cmd, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _run_returning(json_response)
            raise AssertionError("open_mr must not create an MR when one already exists")

        return side_effect

    def test_returns_existing_mr_url(self) -> None:
        with patch("lib.gitlab._run", side_effect=self._fake_run_existing(self._EXISTING_URL)):
            result = open_mr(
                title="Branch 3.19",
                body="adds 3.19 overlays",
                target_branch="main",
                source_branch="branch-3.19",
                cwd=Path("/fake/repo"),
                dry_run=False,
            )
        self.assertEqual(result, self._EXISTING_URL)

    def test_idempotency_check_uses_output_json_flag(self) -> None:
        """Verify the mr list call uses --output json, not --json/--jq (glab-compatible flags)."""
        captured = {}

        def side_effect(cmd, **kwargs):
            if "mr" in cmd and "list" in cmd:
                captured["cmd"] = cmd
                return _run_returning("[]")
            return _run_returning("https://gitlab.com/mr/99")

        with patch("lib.gitlab._run", side_effect=side_effect):
            open_mr(
                title="Branch 3.19",
                body="adds 3.19 overlays",
                target_branch="main",
                source_branch="branch-3.19",
                cwd=Path("/fake/repo"),
                dry_run=False,
            )

        self.assertIn("--output", captured["cmd"])
        self.assertIn("json", captured["cmd"])
        self.assertNotIn("--json", captured["cmd"])
        self.assertNotIn("--jq", captured["cmd"])
        self.assertNotIn("--hostname", captured["cmd"])

    def test_creates_mr_when_none_exists(self) -> None:
        new_url = "https://gitlab.com/myuser/tenants-config/-/merge_requests/99"
        call_results = [_run_returning("[]"), _run_returning(new_url)]

        with patch("lib.gitlab._run", side_effect=call_results):
            result = open_mr(
                title="Branch 3.19",
                body="adds 3.19 overlays",
                target_branch="main",
                source_branch="branch-3.19",
                cwd=Path("/fake/repo"),
                dry_run=False,
            )
        self.assertEqual(result, new_url)

    def test_dry_run_returns_placeholder_and_prints(self) -> None:
        with patch("lib.gitlab._run", return_value=_run_returning("[]")):
            with patch("lib.gitlab._dry_print") as mock_dry_print:
                result = open_mr(
                    title="Branch 3.19",
                    body="adds 3.19 overlays",
                    target_branch="main",
                    source_branch="branch-3.19",
                    cwd=Path("/fake/repo"),
                    dry_run=True,
                )
        self.assertEqual(result, "[dry-run: MR URL not available]")
        mock_dry_print.assert_called_once()

    def test_dry_run_does_not_create_mr(self) -> None:
        call_count = {"n": 0}

        def side_effect(cmd, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 1:
                return _run_returning("[]")
            raise AssertionError("glab mr create must not be called in dry_run mode")

        with patch("lib.gitlab._run", side_effect=side_effect):
            with patch("lib.gitlab._dry_print"):
                open_mr(
                    title="Branch 3.19",
                    body="adds 3.19 overlays",
                    target_branch="main",
                    source_branch="branch-3.19",
                    cwd=Path("/fake/repo"),
                    dry_run=True,
                )
        self.assertEqual(call_count["n"], 0, "no subprocess calls should be made in dry_run mode")


if __name__ == "__main__":
    unittest.main()
