"""
subprocess_helpers.py — Shared subprocess utilities for lib modules.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from pathlib import Path


def run(
    cmd: list[str],
    cwd: Path | None = None,
    capture: bool = False,
    env: dict[str, str] | None = None,
    unset_env: list[str] | None = None,
) -> subprocess.CompletedProcess:
    """Run *cmd* and return the CompletedProcess result.

    Parameters
    ----------
    cmd:
        Command and arguments as a list (no shell=True).
    cwd:
        Working directory for the subprocess.
    capture:
        If True, capture stdout and stderr as text.
    env:
        Extra environment variables merged on top of the current environment.
    unset_env:
        Environment variable names to remove from the subprocess environment.
    """
    kwargs: dict = {"check": True}
    if cwd is not None:
        kwargs["cwd"] = cwd
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    if env is not None or unset_env is not None:
        merged = os.environ.copy()
        if env:
            merged.update(env)
        for key in (unset_env or []):
            merged.pop(key, None)
        kwargs["env"] = merged
    return subprocess.run(cmd, **kwargs)


def dry_print(
    cmd: list[str],
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    unset_env: list[str] | None = None,
) -> None:
    """Print the command that *would* be run under dry_run=True."""
    env_prefix = "".join(f"{k}={v} " for k, v in (env or {}).items())
    unset_prefix = "".join(f"unset {k}; " for k in (unset_env or []))
    cwd_str = f" (in {cwd})" if cwd else ""
    print(f"[dry-run] Would run: {unset_prefix}{env_prefix}{shlex.join(cmd)}{cwd_str}")
