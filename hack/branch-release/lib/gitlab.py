"""
gitlab.py — GitLab CLI (glab) wrappers for MR operations and fork/remote validation.

All subprocess calls use subprocess.run([...], check=True) — no shell=True.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from lib.subprocess_helpers import dry_print as _dry_print
from lib.subprocess_helpers import run as _run

_TENANTS_CONFIG_RE = re.compile(r"(?<![a-z])gitlab\.com[:/]fedora/infrastructure/konflux/tenants-config")


def validate_fork(upstream_repo: str, gitlab_user: str) -> None:
    """Verify that *gitlab_user* has a fork of *upstream_repo*."""
    repo_name = upstream_repo.split("/")[-1]
    fork_repo = f"{gitlab_user}/{repo_name}"
    try:
        _run(["glab", "repo", "view", fork_repo], capture=True)
    except subprocess.CalledProcessError:
        print(
            f"ERROR: Fork not found: {fork_repo}\n"
            f"Please fork {upstream_repo} to your GitLab account ({gitlab_user}) first.\n"
            f"  glab repo fork {upstream_repo} --clone=false",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def validate_remotes(cwd: Path) -> tuple[str, str]:
    """Verify upstream/origin remote naming for a GitLab repo.

    upstream must point to gitlab.com/fedora/infrastructure/konflux/tenants-config.
    origin must not point to that upstream.

    Returns (upstream_url, origin_url). Raises SystemExit(1) if wrong.
    """
    result = _run(["git", "remote", "-v"], cwd=cwd, capture=True)
    lines = result.stdout.strip().splitlines()

    remotes: dict[str, str] = {}
    for line in lines:
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in remotes:
            remotes[parts[0]] = parts[1]

    if "upstream" not in remotes:
        print(
            "ERROR: Remote 'upstream' not found.\n"
            "Expected 'upstream' to point to gitlab.com/fedora/infrastructure/konflux/tenants-config.\n"
            "  git remote add upstream https://gitlab.com/fedora/infrastructure/konflux/tenants-config.git",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if "origin" not in remotes:
        print(
            "ERROR: Remote 'origin' not found.\n"
            "Expected 'origin' to point to your personal fork.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    upstream_url = remotes["upstream"]
    origin_url = remotes["origin"]

    if not _TENANTS_CONFIG_RE.search(upstream_url):
        print(
            f"ERROR: Remote 'upstream' does not point to gitlab.com/fedora/infrastructure/konflux/tenants-config.\n"
            f"  Current upstream: {upstream_url}\n"
            "  Expected: https://gitlab.com/fedora/infrastructure/konflux/tenants-config.git\n"
            "         or git@gitlab.com:fedora/infrastructure/konflux/tenants-config.git",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if _TENANTS_CONFIG_RE.search(origin_url):
        print(
            f"ERROR: Remote 'origin' appears to point to the upstream tenants-config, not a personal fork.\n"
            f"  Current origin: {origin_url}\n"
            "  'origin' should point to your personal fork, not the upstream tenants-config.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return upstream_url, origin_url


def open_mr(
    title: str,
    body: str,
    target_branch: str,
    source_branch: str,
    cwd: Path,
    dry_run: bool,
) -> str:
    """Open a GitLab MR, or return URL if one already exists. Idempotent."""
    existing = _run(
        [
            "glab", "mr", "list",
            "--source-branch", source_branch,
            "--target-branch", target_branch,
            "--json", "url",
            "--jq", ".[0].url",
        ],
        cwd=cwd,
        capture=True,
    )
    url = existing.stdout.strip()
    if url:
        print(f"MR already exists: {url}")
        return url

    cmd = [
        "glab", "mr", "create",
        "--source-branch", source_branch,
        "--target-branch", target_branch,
        "--title", title,
        "--description", body,
    ]

    if dry_run:
        _dry_print(cmd, cwd=cwd)
        return "[dry-run: MR URL not available]"

    result = _run(cmd, cwd=cwd, capture=True)
    return result.stdout.strip()
