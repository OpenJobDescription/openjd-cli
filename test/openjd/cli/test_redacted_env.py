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


def test_run_job_redacted_env_not_enabled_by_accept_list(capsys):
    """
    Extension behaviors activate only when a template *declares* the extension.
    The CLI's --extensions list is what the CLI accepts, not what it enables.

    This job template declares no extensions, so REDACTED_ENV_VARS must stay
    off even though --extensions defaults to every supported extension: the
    variable does not reach the task, and the session warns that the extension
    is not enabled. Building the session's RevisionExtensions from the
    accept-list instead of the declared list flips both observations.
    """
    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            str(TEMPLATE_DIR / "redacted_env_undeclared.yaml"),
        ],
        expected_exit_code=0,
    )

    assert (
        "SECRET_IS=None" in outerr.out
    ), f"openjd_redacted_env set SECRET despite the extension not being declared:\n{format_capsys_outerr(outerr)}"
    assert (
        "REDACTED_ENV_VARS extension is not enabled" in outerr.out
    ), f"Expected the not-enabled warning:\n{format_capsys_outerr(outerr)}"


def test_run_job_redacted_env_declared_by_environment_template(capsys):
    """
    The enabled extensions are the union of what the job template and every
    external environment template declare. Here only the environment template
    declares REDACTED_ENV_VARS, so redaction is active for the whole session:
    SECRET reaches the task and its value is masked in the logs. Dropping the
    environment templates from the union leaves the extension off.
    """
    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            str(TEMPLATE_DIR / "no_extensions_shows_secret.yaml"),
            "--environment",
            str(TEMPLATE_DIR / "env_declares_redacted_env.yaml"),
        ],
        expected_exit_code=0,
    )

    assert (
        "SECRET_IS=" + "*" * 8 in outerr.out
    ), f"SECRET was not set-and-redacted for the task:\n{format_capsys_outerr(outerr)}"
    assert (
        "REDACTED_ENV_VARS extension is not enabled" not in outerr.out
    ), f"The extension declared by the environment template was not enabled:\n{format_capsys_outerr(outerr)}"
    assert (
        "s3cret" not in outerr.out
    ), f"The redacted value leaked into the output:\n{format_capsys_outerr(outerr)}"
