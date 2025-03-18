# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from pathlib import Path
import re

from . import run_openjd_cli_main, format_capsys_outerr

TEMPLATE_DIR = Path(__file__).parent / "templates"


def test_run_job_with_env_default_params(capsys):
    # Run a job with env_with_param as an external environment,
    # leaving the environment's parameter at its default value

    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            str(TEMPLATE_DIR / "simple_with_j_param.yaml"),
            "-p",
            "J=Jvalue",
            "--environment",
            str(TEMPLATE_DIR / "env_with_param.yaml"),
        ],
        expected_exit_code=0,
    )

    for expected_message_regex in [
        "EnvWithParam Enter DefaultForEnvParam",
        "DoTask Jvalue",
        "EnvWithParam Exit DefaultForEnvParam",
    ]:
        assert re.search(
            expected_message_regex, outerr.out
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"


def test_run_job_with_env_provide_env_param(capsys):
    # Run a job with env_with_param as an external environment,
    # explicitly providing the env parameter

    outerr = run_openjd_cli_main(
        capsys,
        args=[
            "run",
            str(TEMPLATE_DIR / "simple_with_j_param.yaml"),
            "-p",
            "J=Jvalue",
            "-p",
            "EnvParam=EnvParamValue",
            "--environment",
            str(TEMPLATE_DIR / "env_with_param.yaml"),
        ],
        expected_exit_code=0,
    )

    for expected_message_regex in [
        "EnvWithParam Enter EnvParamValue",
        "DoTask Jvalue",
        "EnvWithParam Exit EnvParamValue",
    ]:
        assert re.search(
            expected_message_regex, outerr.out
        ), f"Regex r'{expected_message_regex}' not matched in:\n{format_capsys_outerr(outerr)}"
