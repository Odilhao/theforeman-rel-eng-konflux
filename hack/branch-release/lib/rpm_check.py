"""
rpm_check.py — Poll yum.theforeman.org until the versioned RPM repo is present.

Usable as a library:
    from lib.rpm_check import wait_for_rpms
    wait_for_rpms(url, timeout=14400, interval=60, dry_run=False)

Or as a standalone script:
    python3 hack/branch-release/lib/rpm_check.py \\
        --url=https://yum.theforeman.org/releases/3.19/el9/x86_64/repodata/repomd.xml \\
        --timeout=14400 --interval=60 [--dry-run]
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import time
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)

_HTTP_TIMEOUT = 10  # seconds for each individual HTTP request


def wait_for_rpms(url: str, timeout: int, interval: int, dry_run: bool) -> None:
    """Poll *url* until HTTP 200 is returned.

    Parameters
    ----------
    url:
        Full URL to probe (should point to a repomd.xml or similar artefact).
    timeout:
        Maximum number of seconds to wait before giving up (exit 1).
    interval:
        Seconds to sleep between attempts.
    dry_run:
        When True, print the URL that would be polled and return immediately
        without making any HTTP request.

    Raises
    ------
    SystemExit(1)
        When *timeout* seconds elapse without a successful response.
    SystemExit(2)
        When the server returns HTTP 404 (version not found / typo in VERSION).
    """
    if dry_run:
        print(f"Would poll {url} for up to {timeout}s")
        return

    print(f"Waiting for RPMs at {url} ...")

    start = time.monotonic()
    deadline = start + timeout

    while True:
        remaining = deadline - time.monotonic()

        status_code: int | None = None
        try:
            req = urllib.request.Request(url, method="HEAD")
            with urllib.request.urlopen(req, timeout=_HTTP_TIMEOUT) as resp:
                status_code = resp.status
        except urllib.error.HTTPError as exc:
            status_code = exc.code
        except (urllib.error.URLError, socket.timeout, OSError) as exc:
            logger.warning("Connection error: %s. Retrying in %ds...", exc, interval)

        if status_code == 200:
            print(f"RPMs available at {url}")
            return

        if status_code == 404:
            print(f"Version not found at {url} — check VERSION in settings", file=sys.stderr)
            raise SystemExit(2)

        remaining = deadline - time.monotonic()

        if remaining <= 0:
            break

        if status_code == 403:
            print(
                f"  Not available yet (HTTP 403 — CDN transient)."
                f" Retrying in {interval}s ({int(remaining)}s remaining)..."
            )
        elif status_code is not None:
            print(
                f"  Not available yet (HTTP {status_code})."
                f" Retrying in {interval}s ({int(remaining)}s remaining)..."
            )
        else:
            print(
                f"  Not available yet."
                f" Retrying in {interval}s ({int(remaining)}s remaining)..."
            )

        sleep_time = min(interval, max(0, remaining))
        time.sleep(sleep_time)

        if deadline - time.monotonic() <= 0:
            break

    elapsed_int = int(time.monotonic() - start)
    print(f"Timed out after {elapsed_int}s waiting for RPMs at {url}", file=sys.stderr)
    raise SystemExit(1)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poll yum.theforeman.org until the versioned RPM repo is present.",
    )
    parser.add_argument(
        "--url",
        required=True,
        help="URL to probe (e.g. https://yum.theforeman.org/releases/3.19/el9/x86_64/repodata/repomd.xml)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=14400,
        help="Maximum seconds to wait (default: 14400 = 4 hours)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=60,
        help="Seconds between poll attempts (default: 60)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Print what would be done and exit without making HTTP requests",
    )
    return parser


if __name__ == "__main__":
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
    args = _build_parser().parse_args()
    wait_for_rpms(
        url=args.url,
        timeout=args.timeout,
        interval=args.interval,
        dry_run=args.dry_run,
    )
