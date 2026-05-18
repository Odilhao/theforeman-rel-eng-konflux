"""Tests for lib.runner — StepRunner and Step."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

_BR = Path(__file__).parents[1]
if str(_BR) not in sys.path:
    sys.path.insert(0, str(_BR))

from lib.runner import Step, StepRunner  # noqa: E402


def _make_fn(return_value=None):
    m = MagicMock(return_value=return_value)
    return m


class TestAutoMode(unittest.TestCase):

    def test_all_steps_run_and_results_returned(self) -> None:
        fn_a = _make_fn("result-a")
        fn_b = _make_fn("result-b")
        runner = StepRunner(auto=True)
        runner.add_step(Step(name="step-a", fn=fn_a))
        runner.add_step(Step(name="step-b", fn=fn_b))

        results = runner.run()

        fn_a.assert_called_once()
        fn_b.assert_called_once()
        self.assertEqual(results, [("step-a", "result-a"), ("step-b", "result-b")])


class TestDryRunMode(unittest.TestCase):

    def test_all_steps_called_without_prompts(self) -> None:
        fn_a = _make_fn("dry-a")
        fn_b = _make_fn("dry-b")
        runner = StepRunner(dry_run=True)
        runner.add_step(Step(name="step-a", fn=fn_a))
        runner.add_step(Step(name="step-b", fn=fn_b))

        with patch("builtins.input") as mock_input:
            results = runner.run()

        mock_input.assert_not_called()
        fn_a.assert_called_once()
        fn_b.assert_called_once()
        self.assertEqual(results, [("step-a", "dry-a"), ("step-b", "dry-b")])


class TestInteractiveMode(unittest.TestCase):

    def test_user_confirms_all_steps_run(self) -> None:
        fn_a = _make_fn("a")
        fn_b = _make_fn("b")
        runner = StepRunner()
        runner.add_step(Step(name="step-a", fn=fn_a))
        runner.add_step(Step(name="step-b", fn=fn_b))

        with patch("builtins.input", return_value=""):
            results = runner.run()

        fn_a.assert_called_once()
        fn_b.assert_called_once()
        self.assertEqual(results, [("step-a", "a"), ("step-b", "b")])

    def test_user_skips_one_step_subsequent_still_run(self) -> None:
        fn_a = _make_fn("a")
        fn_b = _make_fn("b")
        fn_c = _make_fn("c")
        runner = StepRunner()
        runner.add_step(Step(name="step-a", fn=fn_a))
        runner.add_step(Step(name="step-b", fn=fn_b))
        runner.add_step(Step(name="step-c", fn=fn_c))

        # Confirm a, skip b, confirm c
        with patch("builtins.input", side_effect=["", "n", ""]):
            results = runner.run()

        fn_a.assert_called_once()
        fn_b.assert_not_called()
        fn_c.assert_called_once()
        self.assertIn(("step-a", "a"), results)
        self.assertNotIn("step-b", [name for name, _ in results])
        self.assertIn(("step-c", "c"), results)
        self.assertEqual(len(results), 2)

    def test_uppercase_n_skips_step(self) -> None:
        fn_a = _make_fn("a")
        runner = StepRunner()
        runner.add_step(Step(name="step-a", fn=fn_a))

        with patch("builtins.input", return_value="N"):
            results = runner.run()

        fn_a.assert_not_called()
        self.assertNotIn("step-a", [name for name, _ in results])
        self.assertEqual(len(results), 0)


class TestResumeFrom(unittest.TestCase):

    def test_resume_skips_prior_steps_starts_from_named(self) -> None:
        fn_a = _make_fn("a")
        fn_b = _make_fn("b")
        fn_c = _make_fn("c")
        runner = StepRunner(auto=True, resume_from="step-b")
        runner.add_step(Step(name="step-a", fn=fn_a))
        runner.add_step(Step(name="step-b", fn=fn_b))
        runner.add_step(Step(name="step-c", fn=fn_c))

        results = runner.run()

        fn_a.assert_not_called()
        fn_b.assert_called_once()
        fn_c.assert_called_once()
        names = [name for name, _ in results]
        self.assertNotIn("step-a", names)
        self.assertIn("step-b", names)
        self.assertIn("step-c", names)

    def test_resume_from_first_step_runs_all(self) -> None:
        fn_a = _make_fn("a")
        fn_b = _make_fn("b")
        runner = StepRunner(auto=True, resume_from="step-a")
        runner.add_step(Step(name="step-a", fn=fn_a))
        runner.add_step(Step(name="step-b", fn=fn_b))

        results = runner.run()

        fn_a.assert_called_once()
        fn_b.assert_called_once()
        self.assertEqual(len(results), 2)

    def test_unknown_resume_step_raises_value_error_at_run_time(self) -> None:
        runner = StepRunner(auto=True, resume_from="does-not-exist")
        runner.add_step(Step(name="step-a", fn=_make_fn()))

        with self.assertRaises(ValueError) as ctx:
            runner.run()

        self.assertIn("does-not-exist", str(ctx.exception))


class TestStepException(unittest.TestCase):

    def test_exception_reraised_with_resume_hint(self) -> None:
        def failing_fn():
            raise RuntimeError("something went wrong")

        runner = StepRunner(auto=True)
        runner.add_step(Step(name="bad-step", fn=failing_fn))

        with self.assertRaises(RuntimeError):
            runner.run()

    def test_resume_hint_printed_to_stderr(self) -> None:
        def failing_fn():
            raise RuntimeError("boom")

        runner = StepRunner(auto=True)
        runner.add_step(Step(name="bad-step", fn=failing_fn))

        with patch("sys.stderr") as mock_stderr:
            with self.assertRaises(RuntimeError):
                runner.run()

        stderr_output = "".join(str(c) for c in mock_stderr.write.call_args_list)
        self.assertIn("--step=bad-step", stderr_output)

    def test_steps_after_failure_do_not_run(self) -> None:
        fn_after = _make_fn("after")

        def failing_fn():
            raise RuntimeError("boom")

        runner = StepRunner(auto=True)
        runner.add_step(Step(name="failing", fn=failing_fn))
        runner.add_step(Step(name="after", fn=fn_after))

        with self.assertRaises(RuntimeError):
            runner.run()

        fn_after.assert_not_called()


class TestResults(unittest.TestCase):

    def test_results_contain_return_values(self) -> None:
        runner = StepRunner(auto=True)
        runner.add_step(Step(name="step-one", fn=lambda: 42))
        runner.add_step(Step(name="step-two", fn=lambda: {"key": "value"}))

        results = runner.run()

        self.assertEqual(results[0], ("step-one", 42))
        self.assertEqual(results[1], ("step-two", {"key": "value"}))

    def test_empty_runner_returns_empty_list(self) -> None:
        runner = StepRunner(auto=True)
        results = runner.run()
        self.assertEqual(results, [])

    def test_skipped_steps_not_in_results_for_resume(self) -> None:
        runner = StepRunner(auto=True, resume_from="step-b")
        runner.add_step(Step(name="step-a", fn=_make_fn("a")))
        runner.add_step(Step(name="step-b", fn=_make_fn("b")))

        results = runner.run()

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "step-b")


if __name__ == "__main__":
    unittest.main()
