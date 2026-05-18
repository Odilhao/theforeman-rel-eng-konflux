"""Tests for lib.git — clone_repo and related helpers."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.git import clone_repo  # noqa: E402

_UPSTREAM_URL = "https://github.com/theforeman/foreman-oci-images.git"
_FORK_URL = "https://github.com/myuser/foreman-oci-images.git"
_DEST = Path("/tmp/konflux-branch-3.19/foreman-oci-images")


class TestCloneRepoHappyPath(unittest.TestCase):
    """clone_repo in non-dry-run mode calls _run exactly twice."""

    def test_run_called_twice(self) -> None:
        with patch("lib.git._run") as mock_run, patch("lib.git._dry_print") as mock_dry:
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=False)
        self.assertEqual(mock_run.call_count, 2)
        mock_dry.assert_not_called()

    def test_clone_command_shape(self) -> None:
        """First _run call uses git clone --origin upstream <upstream_url> <dest>."""
        with patch("lib.git._run") as mock_run, patch("lib.git._dry_print"):
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=False)
        clone_cmd = mock_run.call_args_list[0][0][0]
        self.assertEqual(clone_cmd[0], "git")
        self.assertEqual(clone_cmd[1], "clone")
        self.assertIn("--origin", clone_cmd)
        upstream_idx = clone_cmd.index("--origin") + 1
        self.assertEqual(clone_cmd[upstream_idx], "upstream")
        self.assertIn(_UPSTREAM_URL, clone_cmd)
        self.assertIn(str(_DEST), clone_cmd)

    def test_remote_add_command_shape(self) -> None:
        """Second _run call adds 'origin' remote pointing to fork_url, with cwd=dest."""
        with patch("lib.git._run") as mock_run, patch("lib.git._dry_print"):
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=False)
        remote_cmd = mock_run.call_args_list[1][0][0]
        remote_kwargs = mock_run.call_args_list[1][1]
        self.assertEqual(remote_cmd, ["git", "remote", "add", "origin", _FORK_URL])
        self.assertEqual(remote_kwargs.get("cwd"), _DEST)

    def test_clone_comes_before_remote_add(self) -> None:
        """_run calls are ordered: clone first, remote add second."""
        with patch("lib.git._run") as mock_run, patch("lib.git._dry_print"):
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=False)
        first_call_cmd = mock_run.call_args_list[0][0][0]
        second_call_cmd = mock_run.call_args_list[1][0][0]
        self.assertIn("clone", first_call_cmd)
        self.assertIn("remote", second_call_cmd)


class TestCloneRepoDryRun(unittest.TestCase):
    """clone_repo in dry-run mode calls _dry_print exactly twice; _run is never called."""

    def test_run_not_called(self) -> None:
        with patch("lib.git._run") as mock_run, patch("lib.git._dry_print"):
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=True)
        mock_run.assert_not_called()

    def test_dry_print_called_twice(self) -> None:
        with patch("lib.git._run"), patch("lib.git._dry_print") as mock_dry:
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=True)
        self.assertEqual(mock_dry.call_count, 2)

    def test_dry_print_clone_command_shape(self) -> None:
        """First _dry_print call contains --origin, upstream, and the upstream URL."""
        with patch("lib.git._run"), patch("lib.git._dry_print") as mock_dry:
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=True)
        clone_cmd = mock_dry.call_args_list[0][0][0]
        self.assertIn("--origin", clone_cmd)
        self.assertIn("upstream", clone_cmd)
        self.assertIn(_UPSTREAM_URL, clone_cmd)

    def test_dry_print_remote_add_uses_fork_url(self) -> None:
        """Second _dry_print call contains fork_url as the origin remote."""
        with patch("lib.git._run"), patch("lib.git._dry_print") as mock_dry:
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=True)
        remote_cmd = mock_dry.call_args_list[1][0][0]
        self.assertIn(_FORK_URL, remote_cmd)
        self.assertIn("origin", remote_cmd)

    def test_dry_print_remote_add_passes_cwd(self) -> None:
        """Second _dry_print call passes cwd=dest so the printed context is correct."""
        with patch("lib.git._run"), patch("lib.git._dry_print") as mock_dry:
            clone_repo(_UPSTREAM_URL, _FORK_URL, _DEST, dry_run=True)
        remote_kwargs = mock_dry.call_args_list[1][1]
        self.assertEqual(remote_kwargs.get("cwd"), _DEST)


if __name__ == "__main__":
    unittest.main()
