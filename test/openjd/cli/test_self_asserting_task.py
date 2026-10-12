# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The openjd-specifications conformance shape where a task asserts its own output.

Its single-task job fixtures spawn the case's command as a child, reproduce its
output, and exit non-zero when the output does not match. That verdict only reaches
the runner if we capture a grandchild's output and propagate the action's exit status,
so both directions are pinned here rather than left to the external suite to catch.
"""

from pathlib import Path

from . import format_capsys_outerr, run_openjd_cli_main

TEMPLATE_DIR = Path(__file__).parent / "templates"


def test_grandchild_output_captured_and_assertion_passes(capsys):
    outerr = run_openjd_cli_main(
        capsys,
        args=["run", str(TEMPLATE_DIR / "self_asserting_task.yaml")],
        expected_exit_code=0,
    )
    # Printed by the grandchild and echoed by the action. Missing means output from a
    # process we did not spawn ourselves was dropped.
    assert "OUTPUT:EXPECTED_VALUE" in outerr.out, format_capsys_outerr(outerr)
    assert "ASSERT_FAILED" not in outerr.out, format_capsys_outerr(outerr)


def test_assertion_failure_fails_the_run(capsys):
    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            str(TEMPLATE_DIR / "self_asserting_task.yaml"),
            "-p",
            "Printed=WRONG_VALUE",
        ],
        expected_exit_code=1,
    )
    output = outerr.out + outerr.err
    assert "ASSERT_FAILED" in output, format_capsys_outerr(outerr)
    assert "OUTPUT:WRONG_VALUE" in output, format_capsys_outerr(outerr)
