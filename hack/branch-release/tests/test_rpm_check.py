"""Tests for lib.rpm_check.wait_for_rpms."""

from __future__ import annotations

import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from lib.rpm_check import wait_for_rpms


def _make_response(status: int) -> MagicMock:
    """Return a mock context-manager that looks like a urllib HTTP response."""
    resp = MagicMock()
    resp.status = status
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


def _http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError(url="http://x", code=code, msg="", hdrs=None, fp=None)


class TestWaitForRpms(unittest.TestCase):

    # ------------------------------------------------------------------
    # 1. HTTP 200 on first try → returns without error
    # ------------------------------------------------------------------
    @patch("lib.rpm_check.urllib.request.urlopen")
    def test_200_on_first_try(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.return_value = _make_response(200)
        # Should not raise
        wait_for_rpms(url="http://example.com/repomd.xml", timeout=60, interval=1, dry_run=False)
        mock_urlopen.assert_called_once()

    # ------------------------------------------------------------------
    # 2. HTTP 403 on first try, HTTP 200 on second → retries and succeeds
    # ------------------------------------------------------------------
    @patch("lib.rpm_check.time.sleep")
    @patch("lib.rpm_check.urllib.request.urlopen")
    def test_403_then_200(self, mock_urlopen: MagicMock, mock_sleep: MagicMock) -> None:
        mock_urlopen.side_effect = [
            _http_error(403),
            _make_response(200),
        ]
        wait_for_rpms(url="http://example.com/repomd.xml", timeout=120, interval=1, dry_run=False)
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once()

    # ------------------------------------------------------------------
    # 3. HTTP 404 → SystemExit(2)
    # ------------------------------------------------------------------
    @patch("lib.rpm_check.urllib.request.urlopen")
    def test_404_raises_exit_2(self, mock_urlopen: MagicMock) -> None:
        mock_urlopen.side_effect = _http_error(404)
        with self.assertRaises(SystemExit) as ctx:
            wait_for_rpms(url="http://example.com/repomd.xml", timeout=60, interval=1, dry_run=False)
        self.assertEqual(ctx.exception.code, 2)

    # ------------------------------------------------------------------
    # 4. Timeout → SystemExit(1)
    # ------------------------------------------------------------------
    @patch("lib.rpm_check.time.sleep")
    @patch("lib.rpm_check.time.monotonic")
    @patch("lib.rpm_check.urllib.request.urlopen")
    def test_timeout_raises_exit_1(
        self,
        mock_urlopen: MagicMock,
        mock_monotonic: MagicMock,
        mock_sleep: MagicMock,
    ) -> None:
        # Call sequence for time.monotonic():
        #   1. start = time.monotonic()           → 0   (deadline = 0 + 10 = 10)
        #   2. remaining = deadline - monotonic()  → 5   (10 - 5 = 5, > 0 so enter loop)
        #   3. remaining = deadline - monotonic()  → 11  (10 - 11 = -1, <= 0 so break)
        #   4. elapsed_int = monotonic() - start   → 11  (11 - 0 = 11)
        mock_monotonic.side_effect = [
            0,   # start
            5,   # first remaining check: 10 - 5 = 5 (> 0, enter loop)
            11,  # second remaining check after HTTP: 10 - 11 = -1 (break)
            11,  # elapsed_int: 11 - 0 = 11
        ]
        mock_urlopen.side_effect = _http_error(403)

        with self.assertRaises(SystemExit) as ctx:
            wait_for_rpms(url="http://example.com/repomd.xml", timeout=10, interval=1, dry_run=False)

        self.assertEqual(ctx.exception.code, 1)

    # ------------------------------------------------------------------
    # 5. dry_run=True → no HTTP call made, returns immediately
    # ------------------------------------------------------------------
    @patch("lib.rpm_check.urllib.request.urlopen")
    def test_dry_run_no_http(self, mock_urlopen: MagicMock) -> None:
        wait_for_rpms(url="http://example.com/repomd.xml", timeout=60, interval=1, dry_run=True)
        mock_urlopen.assert_not_called()

    # ------------------------------------------------------------------
    # 6. Connection error on first try, HTTP 200 on second → retries
    # ------------------------------------------------------------------
    @patch("lib.rpm_check.time.sleep")
    @patch("lib.rpm_check.urllib.request.urlopen")
    def test_connection_error_then_200(self, mock_urlopen: MagicMock, mock_sleep: MagicMock) -> None:
        mock_urlopen.side_effect = [
            urllib.error.URLError(reason="Connection refused"),
            _make_response(200),
        ]
        wait_for_rpms(url="http://example.com/repomd.xml", timeout=120, interval=1, dry_run=False)
        self.assertEqual(mock_urlopen.call_count, 2)
        mock_sleep.assert_called_once()


if __name__ == "__main__":
    unittest.main()
