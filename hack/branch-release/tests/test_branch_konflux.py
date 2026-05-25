"""Tests for branch_konflux — light coverage of pure-Python helpers."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add hack/branch-release/ to sys.path so we can import branch_konflux
# and its lib/ siblings.  conftest.py does this for lib modules, but
# branch_konflux lives in the parent directory itself.
_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

import importlib  # noqa: E402
import importlib.util  # noqa: E402
import types  # noqa: E402

import pytest  # noqa: E402


def _load_branch_konflux() -> types.ModuleType:
    """Import hack/branch-release/branch_konflux as a module (no .py extension)."""
    source_path = _BR / "branch_konflux"
    loader = importlib.machinery.SourceFileLoader("branch_konflux", str(source_path))
    spec = importlib.util.spec_from_loader("branch_konflux", loader)
    assert spec is not None
    mod = importlib.util.module_from_spec(spec)
    loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def branch_konflux_mod():
    return _load_branch_konflux()


# ---------------------------------------------------------------------------
# _require_env
# ---------------------------------------------------------------------------


def test_require_env_returns_value_when_set(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_BRANCH_KONFLUX_VAR", "hello")
    assert branch_konflux_mod._require_env("TEST_BRANCH_KONFLUX_VAR") == "hello"


def test_require_env_raises_on_missing(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TEST_BRANCH_KONFLUX_VAR", raising=False)
    with pytest.raises(SystemExit) as exc_info:
        branch_konflux_mod._require_env("TEST_BRANCH_KONFLUX_VAR")
    assert exc_info.value.code == 1


def test_require_env_raises_on_empty_string(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TEST_BRANCH_KONFLUX_VAR", "")
    with pytest.raises(SystemExit) as exc_info:
        branch_konflux_mod._require_env("TEST_BRANCH_KONFLUX_VAR")
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# CLI: --help and missing --version
# ---------------------------------------------------------------------------


def test_help_exits_zero(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["branch_konflux", "--help"])
    with pytest.raises(SystemExit) as exc_info:
        branch_konflux_mod._parse_args()
    assert exc_info.value.code == 0


def test_version_required(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["branch_konflux"])
    with pytest.raises(SystemExit) as exc_info:
        branch_konflux_mod._parse_args()
    assert exc_info.value.code == 2


def test_version_flag_accepted(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["branch_konflux", "--version=3.19"])
    args = branch_konflux_mod._parse_args()
    assert args.version == "3.19"


def test_dry_run_flag(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["branch_konflux", "--version=3.19", "--dry-run"])
    args = branch_konflux_mod._parse_args()
    assert args.dry_run is True


def test_skip_rpm_check_flag(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["branch_konflux", "--version=3.19", "--skip-rpm-check"])
    args = branch_konflux_mod._parse_args()
    assert args.skip_rpm_check is True


def test_parse_args_step_flag(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    """--step flag sets args.step correctly."""
    monkeypatch.setattr(sys, "argv", ["branch_konflux", "--version=3.19", "--step=wait-rpms"])
    args = branch_konflux_mod._parse_args()
    assert args.step == "wait-rpms"


def test_parse_args_recreate_flag(branch_konflux_mod, monkeypatch: pytest.MonkeyPatch) -> None:
    """--recreate flag sets args.recreate to True."""
    monkeypatch.setattr(sys, "argv", ["branch_konflux", "--version=3.19", "--recreate"])
    args = branch_konflux_mod._parse_args()
    assert args.recreate is True


def test_step_wait_rpms_skip(branch_konflux_mod) -> None:
    """_step_wait_rpms with skip=True returns without calling wait_for_rpms."""
    with patch.object(branch_konflux_mod, "wait_for_rpms") as mock_wait:
        branch_konflux_mod._step_wait_rpms(
            config=MagicMock(), skip=True, dry_run=False
        )
    mock_wait.assert_not_called()


# ---------------------------------------------------------------------------
# _CONTAINERFILE_PATCHES
# ---------------------------------------------------------------------------


def test_containerfile_patches_covers_all_known_repos(branch_konflux_mod) -> None:
    patches = branch_konflux_mod._CONTAINERFILE_PATCHES
    assert "foreman-oci-images" in patches
    assert "pulp-oci-images" in patches
    assert "candlepin-oci-images" in patches


def test_containerfile_patches_foreman_oci_images_non_empty(branch_konflux_mod) -> None:
    patches = branch_konflux_mod._CONTAINERFILE_PATCHES["foreman-oci-images"]
    assert len(patches) > 0


def test_containerfile_patches_pulp_oci_images_non_empty(branch_konflux_mod) -> None:
    # pulp-oci-images pins VERSION (the Pulp version)
    patches = branch_konflux_mod._CONTAINERFILE_PATCHES["pulp-oci-images"]
    assert len(patches) == 1
    assert patches[0][1] == "VERSION"
    assert patches[0][2] == "pulp_version"


def test_containerfile_patches_candlepin_oci_images_non_empty(branch_konflux_mod) -> None:
    patches = branch_konflux_mod._CONTAINERFILE_PATCHES["candlepin-oci-images"]
    assert len(patches) > 0


def test_containerfile_patches_entries_are_three_tuples(branch_konflux_mod) -> None:
    """Each entry is a (rel_path, arg_name, config_attr) triple."""
    for repo_name, entries in branch_konflux_mod._CONTAINERFILE_PATCHES.items():
        for entry in entries:
            assert len(entry) == 3, (
                f"Expected 3-tuple for {repo_name}, got {len(entry)}-tuple: {entry!r}"
            )
