# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
import re

from . import run_openjd_cli_main, format_capsys_outerr

TEMPLATE_DIR = Path(__file__).parent / "templates"


def test_run_job_with_redacted_env(capsys):
    """Test that environment variables set with openjd_redacted_env are properly handled."""
    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            str(TEMPLATE_DIR / "redacted_env.yaml"),
        ],
        expected_exit_code=0,
    )

    # Verify the environment variables were set
    for expected_message_regex in [
        "Setting redacted vars",
        "SECRETVAR is \\*\\*\\*\\*\\*\\*\\*\\*",
        "KEYSPACE is None",
        "VALSPACE is \\*\\*\\*\\*\\*\\*\\*\\*",
        "MULTILINE is \\*\\*\\*\\*\\*\\*\\*\\*",
    ]:
        assert re.search(
            expected_message_regex, outerr.out
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"

    # Verify the openjd_redacted_env lines are not in the output
    for unexpected_message in [
        "openjd_redacted_env: SECRETVAR=SECRETVAL",
        "openjd_redacted_env: KEYSPACE =SECRETVAL",
        "openjd_redacted_env: VALSPACE= SPACEVAL",
        "first_line",
        "second_line",
        "third_line",
    ]:
        assert (
            unexpected_message not in outerr.out
        ), f"Found unexpected line in output:\n{format_capsys_outerr(outerr)}"
