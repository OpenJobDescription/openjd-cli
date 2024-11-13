# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from openjd.cli._schema._schema_command import do_get_schema, _process_regex
from openjd.model import TemplateSpecificationVersion
from pydantic.v1 import BaseModel

from argparse import Namespace
import json
import pytest
from unittest.mock import Mock, patch


@pytest.mark.parametrize(
    "target,expected_result",
    [
        pytest.param(
            {"attr": "value", "pattern": r"(?-m:^[^\u0000-\u001F\u007F-\u009F]+\Z)"},
            {"attr": "value", "pattern": r"(?:^[^\u0000-\u001F\u007F-\u009F]+$)"},
            id="Standard dictionary with pattern attribute",
        ),
        pytest.param(
            {"nested_dict": {"pattern": r"(?-m:^[^\u0000-\u001F\u007F-\u009F]+\Z)"}},
            {"nested_dict": {"pattern": r"(?:^[^\u0000-\u001F\u007F-\u009F]+$)"}},
            id="Pattern in nested dictionary",
        ),
        pytest.param(
            {
                "pattern": r"(?-m:^[^\u0000-\u001F\u007F-\u009F]+\Z)",
                "nested_dict": {"pattern": r"(?-m:^[^\u0000-\u001F\u007F-\u009F]+\Z)"},
            },
            {
                "pattern": r"(?:^[^\u0000-\u001F\u007F-\u009F]+$)",
                "nested_dict": {"pattern": r"(?:^[^\u0000-\u001F\u007F-\u009F]+$)"},
            },
            id="Patterns in multiple levels",
        ),
        pytest.param(
            {"pattern": "NotRealRegex"}, {"pattern": "NotRealRegex"}, id="Unaffected pattern"
        ),
        pytest.param(
            {"pattern": ["not", "a", "string"]},
            {"pattern": ["not", "a", "string"]},
            id="Non-string pattern attribute",
        ),
        pytest.param({}, {}, id="Empty dictionary"),
    ],
)
def test_process_regex(target: dict, expected_result: dict):
    """
    Test that the `schema` command can process Python-specific regex
    into JSON-compatible regex.
    """
    _process_regex(target)

    assert target == expected_result


@pytest.mark.usefixtures("capsys")
def test_do_get_schema_success(capsys: pytest.CaptureFixture):
    """
    Test that the `schema` command returns a correctly-formed
    JSON body with specific Job template attributes.
    """
    with patch(
        "openjd.cli._schema._schema_command._process_regex", new=Mock(side_effect=_process_regex)
    ) as patched_process_regex:
        do_get_schema(
            Namespace(
                version=TemplateSpecificationVersion.JOBTEMPLATE_v2023_09.value,
                output="human-readable",
            )
        )
        patched_process_regex.assert_called()

    model_output = capsys.readouterr().out
    model_json = json.loads(model_output)

    assert model_json is not None
    assert model_json["title"] == "JobTemplate"
    assert "specificationVersion" in model_json["properties"]
    assert "name" in model_json["properties"]
    assert "steps" in model_json["properties"]


@pytest.mark.usefixtures("capsys")
def test_do_get_schema_success_environment(capsys: pytest.CaptureFixture):
    """
    Test that the `schema` command returns a correctly-formed
    JSON body with specific Environment template attributes.
    """
    with patch(
        "openjd.cli._schema._schema_command._process_regex", new=Mock(side_effect=_process_regex)
    ) as patched_process_regex:
        do_get_schema(
            Namespace(
                version=TemplateSpecificationVersion.ENVIRONMENT_v2023_09.value,
                output="human-readable",
            )
        )
        patched_process_regex.assert_called()

    model_output = capsys.readouterr().out
    model_json = json.loads(model_output)

    assert model_json is not None
    assert model_json["title"] == "EnvironmentTemplate"
    assert "specificationVersion" in model_json["properties"]


@pytest.mark.usefixtures("capsys")
def test_do_get_schema_incorrect_version(capsys: pytest.CaptureFixture):
    """
    Test that the `schema` command fails if an unsupported version string
    is supplied.
    """

    with pytest.raises(SystemExit):
        do_get_schema(Namespace(version="badversion", output="human-readable"))
    output = capsys.readouterr().out

    assert "Cannot generate schema for version 'badversion'" in output


@pytest.mark.usefixtures("capsys")
def test_do_get_schema_error(capsys: pytest.CaptureFixture):
    """
    Test that the `schema` command can recover from an error
    when generating the JSON schema.
    """

    with (
        patch.object(BaseModel, "schema", side_effect=RuntimeError("Test error")),
        pytest.raises(SystemExit),
    ):
        do_get_schema(
            Namespace(
                version=TemplateSpecificationVersion.JOBTEMPLATE_v2023_09.value,
                output="human-readable",
            )
        )
    output = capsys.readouterr().out

    assert "Test error" in output
