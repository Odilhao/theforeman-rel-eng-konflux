"""
git.py — Git and GitHub CLI wrappers for branching operations.

All functions that make remote changes accept a dry_run parameter.
When dry_run=True, the command is printed but not executed.
All subprocess calls use subprocess.run([...], check=True) — no shell=True.
"""

from __future__ import annotations

from pathlib import Path

from lib.subprocess_helpers import dry_print as _dry_print
from lib.subprocess_helpers import run as _run


def clone_repo(upstream_url: str, fork_url: str, dest: Path, dry_run: bool) -> None:
    """Clone upstream_url to dest with remote named 'upstream'; add fork_url as 'origin'.

    Parameters
    ----------
    upstream_url:
        URL of the upstream repository to clone (becomes the 'upstream' remote).
    fork_url:
        URL of the personal fork to add as the 'origin' remote.
    dest:
        Destination path for the clone.
    dry_run:
        If True, print the commands without executing them.
    """
    clone_cmd = ["git", "clone", "--origin", "upstream", upstream_url, str(dest)]
    if dry_run:
        _dry_print(clone_cmd)
        _dry_print(["git", "remote", "add", "origin", fork_url], cwd=dest)
        return
    _run(clone_cmd)
    _run(["git", "remote", "add", "origin", fork_url], cwd=dest)


def detect_default_branch(repo: str) -> str:
    """Return the default branch name for *repo* (e.g. 'master' or 'main').

    Parameters
    ----------
    repo:
        Full GitHub repo name, e.g. "theforeman/foreman-oci-images".

    Returns
    -------
    str
        The default branch name.
    """
    result = _run(
        ["gh", "repo", "view", repo, "--json", "defaultBranchRef", "--jq", ".defaultBranchRef.name"],
        capture=True,
    )
    return result.stdout.strip()


def branch_exists_remote(remote: str, branch: str, cwd: Path) -> bool:
    """Return True if *branch* exists on *remote*.

    Parameters
    ----------
    remote:
        Remote name (e.g. "upstream") or URL.
    branch:
        Branch name to check.
    cwd:
        Working directory for the git command.
    """
    result = _run(
        ["git", "ls-remote", "--heads", remote, branch],
        cwd=cwd,
        capture=True,
    )
    return bool(result.stdout.strip())


def worktree_add(
    repo_path: Path,
    branch: str,
    base: str,
    worktree_path: Path,
    dry_run: bool,
) -> None:
    """Add a git worktree at *worktree_path* for a new *branch* based on *base*.

    Parameters
    ----------
    repo_path:
        Path to the existing git repository.
    branch:
        New branch name to create in the worktree.
    base:
        Ref to base the new branch on (e.g. "upstream/master").
    worktree_path:
        Path where the worktree will be created.
    dry_run:
        If True, print the command without executing it.
    """
    cmd = ["git", "worktree", "add", "-b", branch, str(worktree_path), base]
    if dry_run:
        _dry_print(cmd, cwd=repo_path)
        return
    _run(cmd, cwd=repo_path)


def worktree_remove(worktree_path: Path, dry_run: bool) -> None:
    """Remove a git worktree.

    Parameters
    ----------
    worktree_path:
        Path of the worktree to remove.
    dry_run:
        If True, print the command without executing it.
    """
    cmd = ["git", "worktree", "remove", "--force", str(worktree_path)]
    if dry_run:
        _dry_print(cmd)
        return
    _run(cmd)


def create_branch(branch: str, base: str, cwd: Path, dry_run: bool) -> None:
    """Create a new local branch *branch* based on *base*.

    Parameters
    ----------
    branch:
        New branch name.
    base:
        Ref to base the branch on.
    cwd:
        Working directory.
    dry_run:
        If True, print the command without executing it.
    """
    cmd = ["git", "checkout", "-b", branch, base]
    if dry_run:
        _dry_print(cmd, cwd=cwd)
        return
    _run(cmd, cwd=cwd)


def push_branch(remote: str, branch: str, cwd: Path, dry_run: bool) -> None:
    """Push *branch* to *remote*.

    Parameters
    ----------
    remote:
        Remote name (e.g. "origin").
    branch:
        Branch name to push.
    cwd:
        Working directory.
    dry_run:
        If True, print the command without executing it.
    """
    cmd = ["git", "push", remote, branch]
    if dry_run:
        _dry_print(cmd, cwd=cwd)
        return
    _run(cmd, cwd=cwd)


def commit_all(message: str, cwd: Path, dry_run: bool) -> None:
    """Stage all changes and create a commit.

    Parameters
    ----------
    message:
        Commit message.
    cwd:
        Working directory.
    dry_run:
        If True, print the commands without executing them.
    """
    add_cmd = ["git", "add", "--all"]
    commit_cmd = ["git", "commit", "-m", message]
    if dry_run:
        _dry_print(add_cmd, cwd=cwd)
        _dry_print(commit_cmd, cwd=cwd)
        return
    _run(add_cmd, cwd=cwd)
    _run(commit_cmd, cwd=cwd)
