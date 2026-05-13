"""
github.py — GitHub CLI (gh) wrappers for PR operations and fork/remote validation.

All subprocess calls use subprocess.run([...], check=True) — no shell=True.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from lib.subprocess_helpers import dry_print as _dry_print
from lib.subprocess_helpers import run as _run

_THEFOREMAN_RE = re.compile(r"(?<![a-z])github\.com[:/]theforeman/")


def validate_fork(upstream_repo: str, github_user: str) -> None:
    """Verify that *github_user* has a fork of *upstream_repo*.

    Parameters
    ----------
    upstream_repo:
        Full GitHub repo name, e.g. "theforeman/foreman-oci-images".
    github_user:
        GitHub username, e.g. "octocat".

    Raises
    ------
    SystemExit(1)
        If the fork does not exist or cannot be verified.
    """
    repo_name = upstream_repo.split("/")[-1]
    fork_repo = f"{github_user}/{repo_name}"
    try:
        _run(["gh", "repo", "view", fork_repo], capture=True)
    except subprocess.CalledProcessError:
        print(
            f"ERROR: Fork not found: {fork_repo}\n"
            f"Please fork {upstream_repo} to your GitHub account ({github_user}) first.\n"
            f"  gh repo fork {upstream_repo} --clone=false",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


def validate_remotes(cwd: Path) -> tuple[str, str]:
    """Verify that the repository in *cwd* has correct remote naming.

    Expects:
    - ``upstream`` remote pointing to ``github.com/theforeman/``
    - ``origin`` remote pointing to the user's personal fork (not theforeman/)

    Parameters
    ----------
    cwd:
        Path to the local git repository to check.

    Returns
    -------
    tuple[str, str]
        ``(upstream_url, origin_url)``

    Raises
    ------
    SystemExit(1)
        If either remote is missing or points to the wrong location.
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
            "Expected 'upstream' to point to github.com/theforeman/<repo>.\n"
            "  git remote add upstream https://github.com/theforeman/<repo>.git",
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

    if not _THEFOREMAN_RE.search(upstream_url):
        print(
            f"ERROR: Remote 'upstream' does not point to github.com/theforeman/.\n"
            f"  Current upstream: {upstream_url}\n"
            "  Expected: https://github.com/theforeman/<repo>.git\n"
            "         or git@github.com:theforeman/<repo>.git",
            file=sys.stderr,
        )
        raise SystemExit(1)

    if _THEFOREMAN_RE.search(origin_url):
        print(
            f"ERROR: Remote 'origin' appears to point to the upstream org (theforeman/), not a personal fork.\n"
            f"  Current origin: {origin_url}\n"
            "  'origin' should point to your personal fork, not the theforeman/ org.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    return upstream_url, origin_url


def open_pr(
    title: str,
    body: str,
    base_branch: str,
    head: str,
    draft: bool,
    cwd: Path,
    dry_run: bool,
) -> str:
    """Open a pull request, or return the URL if one already exists.

    Idempotent: if a PR for *head* already exists against *base_branch*, return
    its URL without creating a duplicate.

    Parameters
    ----------
    title:
        PR title.
    body:
        PR body/description.
    base_branch:
        Target branch for the PR.
    head:
        Source branch for the PR (e.g. "origin:fix-branch").
    draft:
        Whether to open the PR as a draft.
    cwd:
        Working directory (repo root).
    dry_run:
        If True, print the command without executing it.

    Returns
    -------
    str
        URL of the PR (existing or newly created).
    """
    # Check whether a PR already exists for this head→base combination.
    existing = _run(
        ["gh", "pr", "list", "--head", head, "--base", base_branch, "--json", "url", "--jq", ".[0].url"],
        cwd=cwd,
        capture=True,
    )
    url = existing.stdout.strip()
    if url:
        print(f"PR already exists: {url}")
        return url

    cmd = [
        "gh", "pr", "create",
        "--title", title,
        "--body", body,
        "--base", base_branch,
        "--head", head,
    ]
    if draft:
        cmd.append("--draft")

    if dry_run:
        _dry_print(cmd, cwd=cwd)
        return "[dry-run: PR URL not available]"

    result = _run(cmd, cwd=cwd, capture=True)
    return result.stdout.strip()
