# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""Adaptive chunking must defer, not divide, when there is no measurable sample.

Step 3 of the adaptive chunking algorithm in the CLI specification
(``specs/cli/run.md`` in openjd-rs): "If the cumulative duration is zero or
non-finite, keep the current chunk size and wait for a measurable sample."

Without it, a zero ``duration_per_task`` raises ``ZeroDivisionError`` out of the
run in this implementation, and produces a saturating ``inf`` chunk size in the
Rust one. These tests pin the deferral and the negative controls around it.
"""

from math import inf, nan
from pathlib import Path
import re
from unittest.mock import patch

import pytest

from openjd.cli._run._local_session._session_manager import _calculate_adaptive_chunk_size

from . import run_openjd_cli_main, format_capsys_outerr

CHUNKED_JOB_TEMPLATE_FILE = str(Path(__file__).parent / "templates" / "chunked_job.yaml")


class TestDefersWithoutAMeasurableSample:
    @pytest.mark.parametrize(
        "completed_task_duration",
        [
            pytest.param(0.0, id="zero-duration"),
            pytest.param(-0.0, id="negative-zero-duration"),
            pytest.param(-1.0, id="negative-duration"),
            pytest.param(inf, id="infinite-duration"),
            pytest.param(nan, id="nan-duration"),
        ],
    )
    def test_unusable_duration_defers(self, completed_task_duration: float) -> None:
        # GIVEN a completed chunk whose cumulative duration is not a usable
        # sample, WHEN the estimate is calculated
        result = _calculate_adaptive_chunk_size(
            current_chunk_size=1,
            completed_task_count=1,
            completed_task_duration=completed_task_duration,
            target_runtime_seconds=60.0,
        )

        # THEN adjustment is deferred rather than dividing by it. Before the
        # guard, the 0.0 cases raised ZeroDivisionError.
        assert result is None

    @pytest.mark.parametrize(
        "completed_task_count", [pytest.param(0, id="zero"), pytest.param(-1, id="negative")]
    )
    def test_non_positive_task_count_defers(self, completed_task_count: int) -> None:
        # GIVEN no counted tasks -- the other divisor in the same expression
        result = _calculate_adaptive_chunk_size(
            current_chunk_size=1,
            completed_task_count=completed_task_count,
            completed_task_duration=5.0,
            target_runtime_seconds=60.0,
        )

        # THEN
        assert result is None


class TestStillEstimatesNormally:
    """Negative controls: the guard must not swallow the usable cases."""

    def test_blends_while_the_sample_is_small(self) -> None:
        # GIVEN 1 task in 1s against a 60s target, so the ideal size is 60, and
        # fewer than 10 completed tasks means the conservative ramp applies:
        # 0.75 * 4 + 0.25 * 60 == 18.
        result = _calculate_adaptive_chunk_size(
            current_chunk_size=4,
            completed_task_count=1,
            completed_task_duration=1.0,
            target_runtime_seconds=60.0,
        )

        # THEN
        assert result == 18

    def test_uses_the_ideal_size_once_the_sample_is_large(self) -> None:
        # GIVEN 10 or more completed tasks, the blend no longer applies:
        # 10 tasks in 10s is 1s/task, so a 60s target is 60 tasks.
        result = _calculate_adaptive_chunk_size(
            current_chunk_size=4,
            completed_task_count=10,
            completed_task_duration=10.0,
            target_runtime_seconds=60.0,
        )

        # THEN
        assert result == 60

    def test_does_not_blend_when_the_ideal_size_shrinks(self) -> None:
        # GIVEN slow tasks, so the ideal size (2) is below the current size (50).
        # The ramp only applies when the estimate grows, so it is used directly.
        result = _calculate_adaptive_chunk_size(
            current_chunk_size=50,
            completed_task_count=1,
            completed_task_duration=30.0,
            target_runtime_seconds=60.0,
        )

        # THEN
        assert result == 2

    def test_clamps_to_at_least_one(self) -> None:
        # GIVEN tasks far slower than the target, so the ideal size rounds to 0
        result = _calculate_adaptive_chunk_size(
            current_chunk_size=1,
            completed_task_count=1,
            completed_task_duration=1000.0,
            target_runtime_seconds=1.0,
        )

        # THEN a chunk of zero tasks would stall the run
        assert result == 1


class TestDeferringDoesNotSkipTheRestOfTheLoop:
    def test_maximum_task_count_is_honoured_when_every_estimate_defers(self, capsys) -> None:
        """Deferring must skip only the adjustment, not the loop body.

        Regression for a bug in the first draft of this fix: returning early with
        `continue` when the estimate deferred also skipped the maximum-task
        countdown further down the loop, so ``--maximum-tasks`` was ignored and
        the entire parameter space ran.

        ``test_openjd_run_on_chunked_job_maximum_task_count[1]`` in
        ``test_chunked_job.py`` does not catch this: with real subprocess
        durations the estimate never defers, so the deferral path is never taken
        there. Forcing every estimate to defer is what exercises it.
        """
        # GIVEN adaptive chunking (TargetRuntime=1) where the estimate always
        # defers, and a maximum of 3 tasks over a larger parameter space
        with patch(
            "openjd.cli._run._local_session._session_manager._calculate_adaptive_chunk_size",
            return_value=None,
        ) as mock_estimate:
            # WHEN
            outerr = run_openjd_cli_main(
                capsys,
                args=[
                    "run",
                    CHUNKED_JOB_TEMPLATE_FILE,
                    "--step",
                    "Chunked Step",
                    "-p",
                    "ChunkSize=3",
                    "-p",
                    "TargetRuntime=1",
                    "--maximum-tasks",
                    "3",
                ],
                expected_exit_code=0,
            )

        # THEN the run still stopped at the limit, and the deferral path really
        # was the one taken.
        assert mock_estimate.called, "the adaptive estimate was never consulted"
        assert re.search(
            "Chunks run: 3$", outerr.out, re.MULTILINE
        ), f"Regex 'Chunks run: 3$' not matched in:\n{format_capsys_outerr(outerr)}"
