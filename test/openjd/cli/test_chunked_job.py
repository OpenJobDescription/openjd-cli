# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
import re

import pytest

from . import run_openjd_cli_main, format_capsys_outerr

CHUNKED_JOB_TEMPLATE_FILE = str(Path(__file__).parent / "templates" / "chunked_job.yaml")


@pytest.mark.parametrize(
    "cli_options, expected_exit_code, expected_message_regex_list",
    [
        ([], 0, [r"Template at '.*[\\/]chunked_job.yaml' passes validation checks."]),
        (["--extensions", ""], 1, ["Unsupported extension names: TASK_CHUNKING"]),
        (
            ["--extensions", "TASK_CHUNKING"],
            0,
            [r"Template at '.*[\\/]chunked_job.yaml' passes validation checks."],
        ),
    ],
)
def test_openjd_check_on_chunked_job(
    capsys, cli_options: list[str], expected_exit_code: int, expected_message_regex_list: list[str]
) -> None:
    # Test that "openjd check" validates the chunked_job.yaml appropriately

    outerr = run_openjd_cli_main(
        capsys,
        args=["check", CHUNKED_JOB_TEMPLATE_FILE, *cli_options],
        expected_exit_code=expected_exit_code,
    )

    for expected_message_regex in expected_message_regex_list:
        assert re.search(
            expected_message_regex, outerr.out
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"


def test_openjd_summary_on_chunked_job(capsys):
    # Test that "openjd summary" prints out correct information for chunked_job.yaml

    expected_message_regex_list = [
        "Summary for 'Chunked Job'",
        "Total tasks: 40",
        r"1. 'Chunked Step' \(40 total Tasks\)",
        r"Item \(CHUNK\[INT\]\)",
    ]

    outerr = run_openjd_cli_main(
        capsys, args=["summary", CHUNKED_JOB_TEMPLATE_FILE], expected_exit_code=0
    )

    for expected_message_regex in expected_message_regex_list:
        assert re.search(
            expected_message_regex, outerr.out, re.MULTILINE
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"


def test_openjd_run_on_chunked_job_default_options(capsys):
    # Test that "openjd run" runs the chunked_job.yaml with the expected chunks

    expected_message_regex_list = [
        r"Item\(CHUNK\[INT\]\) = 1-10$",
        r"Item\(CHUNK\[INT\]\) = 11-20$",
        r"Item\(CHUNK\[INT\]\) = 21-30$",
        r"Item\(CHUNK\[INT\]\) = 31-40$",
        "Chunks run: 4$",
    ]

    outerr = run_openjd_cli_main(
        capsys,
        args=["run", CHUNKED_JOB_TEMPLATE_FILE, "--step", "Chunked Step"],
        expected_exit_code=0,
    )

    for expected_message_regex in expected_message_regex_list:
        assert re.search(
            expected_message_regex, outerr.out, re.MULTILINE
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"


def test_openjd_run_on_chunked_job_adaptive_chunking(capsys):
    # Test that running chunked_job.yaml with adaptive chunking and the TargetRuntime cranked really high
    # results in two chunks, the first being one task, and the second being the remainder.

    expected_message_regex_list = [
        r"Item\(CHUNK\[INT\]\) = 1$",
        r"Item\(CHUNK\[INT\]\) = 2-40$",
        "Chunks run: 2$",
    ]

    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            CHUNKED_JOB_TEMPLATE_FILE,
            "--step",
            "Chunked Step",
            "-p",
            "ChunkSize=1",
            "-p",
            "TargetRuntime=10000",
        ],
        expected_exit_code=0,
    )

    for expected_message_regex in expected_message_regex_list:
        assert re.search(
            expected_message_regex, outerr.out, re.MULTILINE
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"


@pytest.mark.parametrize("target_runtime", [0, 1])
def test_openjd_run_on_chunked_job_maximum_task_count(capsys, target_runtime):
    # Test that running chunked_job.yaml with small chunks and a maximum task count will run the max count
    # Runs with TargetRuntime=0 (fixed chunk size) and TargetRuntime=1 (adaptive chunk size) to
    # exercise both task running inner loops.
    expected_message_regex_list = [
        "Chunks run: 3$",
    ]

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
            f"TargetRuntime={target_runtime}",
            "--maximum-tasks",
            "3",
        ],
        expected_exit_code=0,
    )

    for expected_message_regex in expected_message_regex_list:
        assert re.search(
            expected_message_regex, outerr.out, re.MULTILINE
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"


PARAMETRIZE_CASES: tuple = (
    pytest.param(
        ["-tp", "Item=0"],
        [
            r"Parameter Item of type CHUNK\[INT\] value 0 is not a subset of the range in the parameter space."
        ],
        id="Item single value out of range",
    ),
    pytest.param(
        ["-tp", "Item=1;2"],
        [r"Parameter Item of type CHUNK\[INT\] value 1;2 is not a valid range expression"],
        id="Item is not a range expr",
    ),
    pytest.param(
        ["-tp", "Item=30-41"],
        [
            r"Parameter Item of type CHUNK\[INT\] value 30-41 is not a subset of the range in the parameter space."
        ],
        id="Item interval out of range",
    ),
)


@pytest.mark.parametrize("bad_task_params,expected_message_regex_list", PARAMETRIZE_CASES)
def test_openjd_run_on_chunked_job_bad_task_params(
    capsys, bad_task_params, expected_message_regex_list
):
    # Test that running chunked_job.yaml with various bad task parameters fails with expected messages

    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            CHUNKED_JOB_TEMPLATE_FILE,
            "--step",
            "Chunked Step",
            *bad_task_params,
        ],
        expected_exit_code=1,
    )

    for expected_message_regex in expected_message_regex_list:
        assert re.search(
            expected_message_regex, outerr.out, re.MULTILINE
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"
