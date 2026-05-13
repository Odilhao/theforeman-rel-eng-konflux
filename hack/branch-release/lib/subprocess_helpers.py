"""
subprocess_helpers.py — Shared subprocess utilities for lib modules.
"""

from __future__ import annotations

import shlex
import subprocess
from pathlib import Path


def run(cmd: list[str], cwd: Path | None = None, capture: bool = False) -> subprocess.CompletedProcess:
    """Run *cmd* and return the CompletedProcess result.

    Parameters
    ----------
    cmd:
        Command and arguments as a list (no shell=True).
    cwd:
        Working directory for the subprocess.
    capture:
        If True, capture stdout and stderr as text.
    """
    kwargs: dict = {"check": True}
    if cwd is not None:
        kwargs["cwd"] = cwd
    if capture:
        kwargs["capture_output"] = True
        kwargs["text"] = True
    return subprocess.run(cmd, **kwargs)


def dry_print(cmd: list[str], cwd: Path | None = None) -> None:
    """Print the command that *would* be run under dry_run=True."""
    cwd_str = f" (in {cwd})" if cwd else ""
    print(f"[dry-run] Would run: {shlex.join(cmd)}{cwd_str}")
