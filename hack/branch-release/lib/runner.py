"""
runner.py — Step runner for the branch_konflux orchestrator.

Supports interactive, auto, and dry-run execution modes with optional
resume-from-step capability.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import Any, Callable


@dataclass
class Step:
    name: str
    fn: Callable[[], Any]


class StepRunner:
    def __init__(
        self,
        dry_run: bool = False,
        auto: bool = False,
        resume_from: str | None = None,
    ) -> None:
        self._dry_run = dry_run
        self._auto = auto
        self._resume_from = resume_from
        self._steps: list[Step] = []

    def add_step(self, step: Step) -> None:
        self._steps.append(step)

    def run(self) -> list[tuple[str, Any]]:
        if self._resume_from is not None:
            known_names = {s.name for s in self._steps}
            if self._resume_from not in known_names:
                raise ValueError(
                    f"Unknown step {self._resume_from!r}. "
                    f"Known steps: {', '.join(s.name for s in self._steps)}"
                )

        total = len(self._steps)
        results: list[tuple[str, Any]] = []
        skipping = self._resume_from is not None

        for idx, step in enumerate(self._steps, start=1):
            if skipping:
                if step.name == self._resume_from:
                    skipping = False
                else:
                    print(f"[skipped] {step.name}")
                    continue

            if self._dry_run:
                print(f"\n[step {idx}/{total}] {step.name} [dry-run]")
                value = step.fn()
                results.append((step.name, value))
                continue

            print(f"\n[step {idx}/{total}] {step.name}")
            if not self._auto:
                answer = input("Proceed? [Y/n] ")
                if answer.strip().lower() == "n":
                    print("Skipped.")
                    continue

            try:
                value = step.fn()
            except Exception as exc:
                print(f"ERROR: {exc}", file=sys.stderr)
                print(f"\nTo resume from this step: --step={step.name}", file=sys.stderr)
                raise

            results.append((step.name, value))

        return results
