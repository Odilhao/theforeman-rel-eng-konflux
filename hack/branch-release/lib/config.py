"""
config.py — Load and validate release settings files.

Settings are plain shell-style key=value files (read via shlex, never exec/eval).
Example path: releases/foreman/3.19/settings

Version format: MAJOR.MINOR only (e.g. "3.19"). MAJOR.MINOR.PATCH, "nightly",
empty string, and any other format are rejected with a clear error.
"""

from __future__ import annotations

import re
import shlex
import sys
from dataclasses import dataclass
from pathlib import Path


def _find_repo_root() -> Path:
    """Walk up from this file until a .git directory is found."""
    here = Path(__file__).resolve()
    for parent in here.parents:
        if (parent / ".git").exists():
            return parent
    raise RuntimeError(f"Could not find repo root from {here}")


_REPO_ROOT = _find_repo_root()

_VERSION_RE = re.compile(r"^\d+\.\d+$")


def _validate_version(version: str) -> None:
    """Raise SystemExit(1) if version is not MAJOR.MINOR format."""
    if not version:
        print("ERROR: VERSION must not be empty. Expected format: MAJOR.MINOR (e.g. 3.19)", file=sys.stderr)
        raise SystemExit(1)
    if not _VERSION_RE.match(version):
        print(
            f"ERROR: Invalid version {version!r}. "
            "Expected MAJOR.MINOR (e.g. 3.19). "
            "MAJOR.MINOR.PATCH, 'nightly', and other formats are not accepted.",
            file=sys.stderr,
        )
        raise SystemExit(1)


@dataclass(frozen=True)
class ReleaseConfig:
    """Typed configuration for a versioned Foreman release."""

    version: str
    branch_name: str
    oci_repos: list[str]
    release_tags: list[str]
    rpm_check_url: str
    rpm_check_timeout: int
    katello_version: str
    candlepin_version: str
    candlepin_version_xyz: str


def _parse_int(value: str, field: str, settings_path: Path) -> int:
    try:
        return int(value)
    except ValueError:
        print(
            f"ERROR: {field} must be an integer (got {value!r}) in {settings_path}",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def load_config(version: str) -> ReleaseConfig:
    """Load and validate the settings file for *version*.

    Parameters
    ----------
    version:
        Release version string, e.g. "3.19". Must be MAJOR.MINOR format.

    Returns
    -------
    ReleaseConfig
        Parsed, validated configuration.

    Raises
    ------
    SystemExit(1)
        On invalid version format, missing settings file, or missing required fields.
    """
    _validate_version(version)

    settings_path = _REPO_ROOT / "releases" / "foreman" / version / "settings"

    if not settings_path.exists():
        print(
            f"ERROR: Settings file not found: {settings_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    raw = settings_path.read_text()
    tokens = shlex.split(raw, comments=True)

    data: dict[str, str] = {}
    for token in tokens:
        if "=" in token:
            key, _, value = token.partition("=")
            data[key.strip()] = value.strip()

    required = [
        "VERSION",
        "BRANCH_NAME",
        "OCI_REPOS",
        "RELEASE_TAGS",
        "RPM_CHECK_URL",
        "RPM_CHECK_TIMEOUT",
        "KATELLO_VERSION",
        "CANDLEPIN_VERSION",
        "CANDLEPIN_VERSION_XYZ",
    ]
    missing = [k for k in required if k not in data]
    if missing:
        print(
            f"ERROR: Missing required fields in {settings_path}: {', '.join(missing)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return ReleaseConfig(
        version=data["VERSION"],
        branch_name=data["BRANCH_NAME"],
        oci_repos=data["OCI_REPOS"].split(),
        release_tags=data["RELEASE_TAGS"].split(),
        rpm_check_url=data["RPM_CHECK_URL"],
        rpm_check_timeout=_parse_int(data["RPM_CHECK_TIMEOUT"], "RPM_CHECK_TIMEOUT", settings_path),
        katello_version=data["KATELLO_VERSION"],
        candlepin_version=data["CANDLEPIN_VERSION"],
        candlepin_version_xyz=data["CANDLEPIN_VERSION_XYZ"],
    )
