# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for __main__"""

from unittest.mock import Mock, patch
import pytest
import sys

from openjd import __main__
from openjd.model import SchemaVersion


@patch("openjd.cli._check.do_check")
def test_cli_check_success(mock_check: Mock):
    """
    Test that we can call the `check` command at the entrypoint.
    """

    mock_check.assert_not_called()
    mock_args = ["openjd", "check", "some-file.json"]
    with patch.object(sys, "argv", new=mock_args):
        __main__.main()
        mock_check.assert_called_once()


@patch("openjd.cli._summary.do_summary")
@pytest.mark.parametrize(
    "mock_args",
    [
        pytest.param(
            ["some-template.json"],
            id="Base summary command",
        ),
        pytest.param(["some-template.json", "--step", "step-name"], id="Summary command with step"),
        pytest.param(
            ["some-template.json", "--job-param", "param=value"],
            id="Summary command with job parameters",
        ),
        pytest.param(
            [
                "some-template.json",
                "--job-param",
                "param=value",
                "--step",
                "step-name",
                "--output",
                "json",
            ],
            id="Summary command with step, job params, and output",
        ),
        pytest.param(
            [
                "some-template.json",
                "--job-param",
                "param1=value1",
                "--job-param",
                "param2=value2",
            ],
            id="Multiple Job parameters",
        ),
    ],
)
def test_cli_summary_success(mock_summary: Mock, mock_args: list):
    """
    Test that we can call the `summary` command at the entrypoint.
    """

    mock_summary.assert_not_called()
    with patch.object(sys, "argv", new=(["openjd", "summary"] + mock_args)):
        __main__.main()
        mock_summary.assert_called_once()


@patch("openjd.cli._run.do_run")
@pytest.mark.parametrize(
    "mock_args",
    [
        pytest.param(["some-template.json", "--step", "step1"], id="Base run command"),
        pytest.param(
            ["some-template.json", "--step", "step1", "-p", "param=value", "-p", "param2=value2"],
            id="With multiple Job parameters",
        ),
        pytest.param(
            ["some-template.json", "--step", "step1", "-p", "param=value1", "-p", "param2="],
            id="With an empty string Job parameter value",
        ),
        pytest.param(
            [
                "some-template.json",
                "--step",
                "step1",
                "-tp",
                "param1=value1 param2=value2",
                "-tp",
                "param1=newvalue1 param2=newvalue2",
            ],
            id="With Task parameter sets",
        ),
        pytest.param(
            [
                "some-template.json",
                "--step",
                "step1",
                "-p",
                "jobparam=paramvalue",
                "-tp",
                "taskparam=paramvalue",
                "--run-dependencies",
                "--maximum-tasks",
                "1",
                "--path-mapping-rules",
                '[{"source_os": "someOS", "source_path": "some\path", "destination_path": "some/new/path"}]',
                "--output",
                "json",
            ],
            id="With all optional arguments",
        ),
    ],
)
def test_cli_run_success(mock_run: Mock, mock_args: list):
    """
    Test that we can call the `run` command at the entrypoint.
    """

    mock_run.assert_not_called()
    with patch.object(sys, "argv", new=(["openjd", "run"] + mock_args)):
        __main__.main()
        mock_run.assert_called_once()


@patch("openjd.cli._schema.do_get_schema")
def test_cli_schema_success(mock_schema: Mock):
    """
    Test that we can call the `schema` command at the entrypoint.
    """

    mock_schema.assert_not_called()
    # "UNDEFINED" should always be a valid SchemaVersion option, even though the unpatched
    # `do_get_schema` function throws an error on receiving it
    with patch.object(
        sys, "argv", new=(["openjd", "schema", "--version", SchemaVersion.UNDEFINED])
    ):
        __main__.main()
        mock_schema.assert_called_once()


@pytest.mark.parametrize(
    "mock_args",
    [
        pytest.param(
            ["notarealcommand", "some-file.json"],
            id="Non-existent command",
        ),
        pytest.param(["check"], id="Not enough arguments"),
        pytest.param(["summary", "template.json", "--job-param"], id="Missing argument value"),
        pytest.param(["summary", "template.json", "notarealarg"], id="Unexpected argument"),
    ],
)
def test_cli_argument_errors(mock_args: list):
    """
    Tests that various formatting errors with Argparse cause the program to exit with an error.
    """

    with patch.object(sys, "argv", new=(["openjd"] + mock_args)), pytest.raises(SystemExit):
        __main__.main()
