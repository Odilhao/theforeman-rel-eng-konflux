"""
containerfile.py — Patch ARG directives in Containerfiles.

Handles the following ARG patterns:
  ARG FOREMAN_VERSION=<value>
  ARG KATELLO_VERSION=<value>
  ARG VERSION=<value>
  ARG VERSION_XYZ=<value>

Patching is idempotent: if the value is already correct, the file is not
written and False is returned.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


def patch_arg(
    containerfile_path: Path,
    arg_name: str,
    new_value: str,
    dry_run: bool,
) -> bool:
    """Replace the value of ARG *arg_name* in *containerfile_path*.

    Matches lines of the form::

        ARG <arg_name>=<any_value>

    and replaces the value with *new_value*. Only the first matching line is
    replaced (Containerfiles rarely repeat ARG names, but the pattern is
    well-defined).

    Parameters
    ----------
    containerfile_path:
        Path to the Containerfile to patch.
    arg_name:
        Name of the build argument (e.g. "FOREMAN_VERSION").
    new_value:
        New value to set (e.g. "3.19").
    dry_run:
        If True, print what would be done without writing the file.

    Returns
    -------
    bool
        True if the file was (or would be) modified; False if already correct.

    Raises
    ------
    SystemExit(1)
        If *containerfile_path* does not exist or *arg_name* is not found.
    """
    if not containerfile_path.exists():
        print(
            f"ERROR: Containerfile not found: {containerfile_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    content = containerfile_path.read_text()

    pattern = re.compile(
        r"^(ARG\s+" + re.escape(arg_name) + r"=)(.*)$",
        re.MULTILINE,
    )

    match = pattern.search(content)
    if match is None:
        print(
            f"ERROR: ARG {arg_name} not found in {containerfile_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    current_value = match.group(2)
    if current_value == new_value:
        return False

    new_content = pattern.sub(lambda m: m.group(1) + new_value, content, count=1)

    if dry_run:
        print(
            f"[dry-run] Would patch {containerfile_path}: "
            f"ARG {arg_name}={current_value!r} -> {new_value!r}"
        )
        return True

    containerfile_path.write_text(new_content)
    print(f"  Patched {containerfile_path}: ARG {arg_name}={current_value!r} -> {new_value!r}")
    return True


def patch_makefile_var(
    makefile_path: Path,
    var_name: str,
    new_value: str,
    dry_run: bool,
) -> bool:
    """Replace the value of a Makefile variable in *makefile_path*.

    Matches lines of the form::

        VAR_NAME=<any_value>

    Unlike :func:`patch_arg`, there is no ``ARG`` prefix.
    """
    if not makefile_path.exists():
        print(f"ERROR: Makefile not found: {makefile_path}", file=sys.stderr)
        raise SystemExit(1)

    content = makefile_path.read_text()
    pattern = re.compile(r"^(" + re.escape(var_name) + r"=)(.*)$", re.MULTILINE)

    match = pattern.search(content)
    if match is None:
        print(f"ERROR: {var_name} not found in {makefile_path}", file=sys.stderr)
        raise SystemExit(1)

    current_value = match.group(2)
    if current_value == new_value:
        return False

    new_content = pattern.sub(lambda m: m.group(1) + new_value, content, count=1)

    if dry_run:
        print(
            f"[dry-run] Would patch {makefile_path}: "
            f"{var_name}={current_value!r} -> {new_value!r}"
        )
        return True

    makefile_path.write_text(new_content)
    print(f"  Patched {makefile_path}: {var_name}={current_value!r} -> {new_value!r}")
    return True


def patch_workflow_env(
    workflow_path: Path,
    var_name: str,
    new_value: str,
    dry_run: bool,
) -> bool:
    """Replace a GitHub Actions workflow env variable value.

    Matches lines of the form (with leading whitespace)::

        <indent>VAR_NAME: <any_value>

    Used to patch ``env:`` blocks in ``.github/workflows/*.yml``.
    """
    if not workflow_path.exists():
        print(f"ERROR: Workflow file not found: {workflow_path}", file=sys.stderr)
        raise SystemExit(1)

    content = workflow_path.read_text()
    pattern = re.compile(r"^(\s+" + re.escape(var_name) + r":\s+)(.+)$", re.MULTILINE)

    match = pattern.search(content)
    if match is None:
        print(f"ERROR: {var_name} not found in {workflow_path}", file=sys.stderr)
        raise SystemExit(1)

    current_value = match.group(2).strip('"')
    quoted_value = f'"{new_value}"'
    if match.group(2) == quoted_value or current_value == new_value:
        return False

    new_content = pattern.sub(lambda m: m.group(1) + quoted_value, content, count=1)

    if dry_run:
        print(
            f"[dry-run] Would patch {workflow_path}: "
            f"{var_name}: {current_value!r} -> {new_value!r}"
        )
        return True

    workflow_path.write_text(new_content)
    print(f"  Patched {workflow_path}: {var_name}: {current_value!r} -> {new_value!r}")
    return True
