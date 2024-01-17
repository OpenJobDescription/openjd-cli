# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
from pathlib import Path
from typing import Any, Callable
from unittest.mock import ANY, Mock, patch
import json
import os
import pytest
import tempfile
import yaml

from . import (
    MOCK_TEMPLATE,
    MOCK_TEMPLATE_REQUIRES_PARAMS,
    MOCK_PARAM_ARGUMENTS,
    MOCK_PARAM_VALUES,
)
from openjd.cli._common import (
    generate_job,
    get_job_params,
    get_task_params,
    read_template,
)
from openjd.cli._common._job_from_template import job_from_template
from openjd.model import (
    decode_template,
)


@pytest.fixture(scope="function")
def template_dir_and_cwd():
    """
    This fixture manages the life time of a temporary directory that's
    used for the job template dir and the current working directory.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        template_dir = Path(tmpdir) / "template_dir"
        current_working_dir = Path(tmpdir) / "current_working_dir"
        os.makedirs(template_dir)
        os.makedirs(current_working_dir)

        yield (template_dir, current_working_dir)


@patch("openjd.cli._common._validation_utils.decode_template")
def test_decode_template_called(mock_decode_template: Mock):
    """
    Tests that calls to `read_template` will call `decode_template` with the appropriately decoded dictionary
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=".template.json", encoding="utf8", delete=False
    ) as temp_template:
        json.dump(MOCK_TEMPLATE, temp_template.file)

    mock_decode_template.assert_not_called()
    read_template(Namespace(path=Path(temp_template.name), output="human-readable"))
    mock_decode_template.assert_called_once_with(template=MOCK_TEMPLATE)

    Path(temp_template.name).unlink()


@pytest.mark.parametrize(
    "tempfile_extension,doc_serializer",
    [
        pytest.param(".template.json", json.dump, id="Successful JSON"),
        pytest.param(".template.yaml", yaml.dump, id="Successful YAML"),
    ],
)
def test_read_template_success(tempfile_extension: str, doc_serializer: Callable):
    """
    Tests that "read_template" can decode a JSON and YAML file,
    resulting in a Job Template with the same name and number of steps
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=tempfile_extension, encoding="utf8", delete=False
    ) as temp_template:
        doc_serializer(MOCK_TEMPLATE, temp_template)

    mock_args = Namespace(path=Path(temp_template.name), output="human-readable")
    new_path, decoded_template = read_template(mock_args)
    assert new_path == Path(temp_template.name)
    assert decoded_template.name == MOCK_TEMPLATE["name"]
    assert len(decoded_template.steps) == len(MOCK_TEMPLATE["steps"])

    Path(temp_template.name).unlink()


@pytest.mark.parametrize(
    "mock_exists_response,mock_is_file_response,expected_error",
    [
        pytest.param(
            False, False, "'some-file.json' does not exist.", id="Filepath does not exist"
        ),
        pytest.param(
            True,
            False,
            "'some-file.json' is not a file or directory.",
            id="Path is not a file or directory",
        ),
        pytest.param(
            True,
            True,
            "Could not open file 'some-file.json':",
            id="File can't be read",
        ),
    ],
)
def test_read_template_fileerror(
    mock_exists_response: bool, mock_is_file_response: bool, expected_error: str
):
    """
    Tests that `read_template` raises a RuntimeError when unable to open a file
    """
    mock_args = Namespace(path=Path("some-file.json"), output="human-readable")
    with (
        pytest.raises(RuntimeError) as rte,
        patch.object(Path, "exists", Mock(return_value=mock_exists_response)),
        patch.object(Path, "is_file", Mock(return_value=mock_is_file_response)),
    ):
        read_template(mock_args)

    assert str(rte.value).startswith(expected_error)


@pytest.mark.parametrize(
    "tempfile_extension,file_contents",
    [
        pytest.param(
            ".template.json",
            '{ "name": "something" }',
            id="JSON missing field",
        ),
        pytest.param(
            ".template.json",
            '{ "specificationVersion": "jobtemplate-2023-09", "name": 5, "steps": [{"name": "step1", "script": {"actions": {"onRun": {"command": "something"}}}}]}',
            id="JSON type error",
        ),
        pytest.param(
            ".template.json",
            '{ "specificationVersion": "jobtemplate-2023-09", "name": "{{{{{a name}", "steps": [{"name": "step1", "script": {"actions": {"onRun": {"command": \'echo "Hello, world!"\'}}}}],}',
            id="Unparsable JSON brackets",
        ),
        pytest.param(
            ".template.json",
            '{ "specificationVersion": "jobtemplate-2023-09template-2023-09", "steps": "not a real step"} ',
            id="Multiple JSON errors",
        ),
        pytest.param(
            ".template.yaml",
            'specificationVersion: "jobtemplate-2023-09"\nname: "something"',
            id="YAML missing field",
        ),
        pytest.param(
            ".template.yaml",
            'specificationVersion: "jobtemplate-2023-09"\nname: "something"\nsteps: "not a real step"',
            id="YAML type error",
        ),
        pytest.param(
            ".template.yaml",
            'specificationVersion\nname: "something"\nsteps: "not a real step"',
            id="Badly-formatted YAML",
        ),
        pytest.param(
            ".template.yaml",
            'specificationVersion: "jobtemplate-2023-09"\nname:\nsteps: "not a real step"',
            id="Multiple YAML errors",
        ),
    ],
)
def test_read_template_parsingerror(tempfile_extension: str, file_contents: str):
    """
    Tests that `read_template` raises a RuntimeError that when provided a JSON/YAML body with schema errors
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=tempfile_extension, encoding="utf8", delete=False
    ) as temp_template:
        temp_template.write(file_contents)

    mock_args = Namespace(path=Path(temp_template.name), output="human-readable")
    with pytest.raises(RuntimeError) as re:
        read_template(mock_args)

    assert str(re.value).startswith(f"'{temp_template.name}' failed checks:")

    Path(temp_template.name).unlink()


@pytest.mark.parametrize(
    "mock_param_args,expected_param_values",
    [
        pytest.param(MOCK_PARAM_ARGUMENTS, MOCK_PARAM_VALUES, id="Params from key-value pair"),
        pytest.param(["file://TEMPDIR/params.json"], MOCK_PARAM_VALUES, id="Params from file"),
        pytest.param(
            ["SomeParam=SomeValue", "file://TEMPDIR/params.json"],
            {"SomeParam": "SomeValue", "Title": "overwrite", "RequiredParam": "5"},
            id="Combination of KVP and file",
        ),
    ],
)
def test_get_job_params_success(mock_param_args: list[str], expected_param_values: dict):
    """
    Test that Job Parameters can be decoded from a string.
    """

    with tempfile.TemporaryDirectory() as temp_dir:
        for i, file_arg in enumerate(mock_param_args):
            if file_arg.startswith("file://TEMPDIR/"):
                param_file = open(
                    os.path.join(temp_dir, file_arg.removeprefix("file://TEMPDIR/")), "x"
                )
                json.dump(expected_param_values, param_file)
                param_file.close()

                mock_param_args[i] = file_arg.replace("TEMPDIR", temp_dir)

        params = get_job_params(mock_param_args)
        assert params == expected_param_values


@pytest.mark.parametrize(
    "mock_param_args,mock_path_exists,mock_path_is_file,mock_expand_user,mock_read_effect,expected_error",
    [
        pytest.param(
            ["bad format"],
            False,
            False,
            "",
            None,
            "'bad format' should be in the format 'Key=Value'",
            id="Badly-formatted parameter string",
        ),
        pytest.param(
            ["file://some-file.json"],
            False,
            False,
            "some-file.json",
            None,
            "does not exist",
            id="Non-existent parameter filepath",
        ),
        pytest.param(
            ["file://some-directory"],
            True,
            False,
            "some-directory",
            None,
            "is not a file",
            id="Parameter filepath is not a file",
        ),
        pytest.param(
            ["file://some-image.png"],
            True,
            True,
            "some-image.png",
            None,
            "is not JSON or YAML",
            id="Parameter filepath is not JSON/YAML",
        ),
        pytest.param(
            ["file://forbidden-file.json"],
            True,
            True,
            "forbidden-file.json",
            OSError("some OS error"),
            "Could not open",
            id="Unable to open file",
        ),
        pytest.param(
            ["file://bad-params.json"],
            True,
            True,
            "bad-params.json",
            lambda: "{bad json}",
            "is formatted incorrectly",
            id="Badly-formatted parameter file (JSON)",
        ),
        pytest.param(
            ["file://bad-params.yaml"],
            True,
            True,
            "bad-params.yaml",
            lambda: '"bad":\n"yaml"',
            "is formatted incorrectly",
            id="Badly-formatted parameter file (YAML)",
        ),
        pytest.param(
            ["file://list-file.json"],
            True,
            True,
            "list-file.json",
            lambda: '["not a dictionary"]',
            "should contain a dictionary",
            id="Non-dictionary file contents",
        ),
    ],
)
def test_get_job_params_error(
    mock_param_args: list[str],
    mock_path_exists: bool,
    mock_path_is_file: bool,
    mock_expand_user: str,
    mock_read_effect: Any,
    expected_error: str,
):
    """
    Test that errors thrown by `get_job_params` have expected information.
    """
    with (
        patch.object(Path, "exists", new=Mock(return_value=mock_path_exists)),
        patch.object(Path, "is_file", new=Mock(return_value=mock_path_is_file)),
        patch.object(Path, "expanduser", new=Mock(return_value=Path(mock_expand_user))),
        patch.object(Path, "read_text", new=Mock(side_effect=mock_read_effect)),
        pytest.raises(RuntimeError) as rte,
    ):
        get_job_params(mock_param_args)

    assert expected_error in str(rte.value)


@pytest.mark.parametrize(
    "mock_params,expected_job_name,template_dict",
    [
        pytest.param(
            [],
            "my-job",
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "my-job",
                "steps": [
                    {
                        "name": "Step1",
                        "script": {"actions": {"onRun": {"command": "sleep", "args": ["60"]}}},
                    }
                ],
            },
            id="No parameters",
        ),
        pytest.param(
            MOCK_PARAM_ARGUMENTS,
            "overwrite",
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            id="With parameters",
        ),
    ],
)
def test_job_from_template_success(
    mock_params: list, expected_job_name: str, template_dict: dict, template_dir_and_cwd: tuple
):
    """
    Test that `job_from_template` creates a Job with the provided parameters.
    """
    template_dir, current_working_dir = template_dir_and_cwd
    template = decode_template(template=template_dict)

    result = job_from_template(template, mock_params, template_dir, current_working_dir)
    assert result.name == expected_job_name
    assert result.steps == template.steps
    if result.parameters:
        assert len(result.parameters) == len(mock_params)


@pytest.mark.parametrize(
    "mock_params,template_dict,expected_error",
    [
        pytest.param(
            MOCK_PARAM_ARGUMENTS,
            MOCK_TEMPLATE,
            "Job parameter values provided for parameters that are not defined in the template",
            id="Extra parameters",
        ),
        pytest.param(
            [],
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            "Values missing for required job parameters",
            id="Missing parameters",
        ),
        pytest.param(
            ["Title=a", "RequiredParam=0"],
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            "Value (a), with length 1, for parameter Title value must be at least 3 characters",
            id="Parameters not meeting constraints",
        ),
        pytest.param(
            ["Title=abc", "RequiredParam=a"],
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            "Value (a) for parameter RequiredParam must an integer or integer string",
            id="Parameters of wrong type",
        ),
    ],
)
def test_job_from_template_error(
    mock_params: list, template_dict: dict, expected_error: str, template_dir_and_cwd: tuple
):
    """
    Test that errors thrown by `job_from_template` have expected information
    """
    template_dir, current_working_dir = template_dir_and_cwd

    template = decode_template(template=template_dict)

    with pytest.raises(RuntimeError) as rte:
        job_from_template(template, mock_params, template_dir, current_working_dir)

    assert expected_error in str(rte.value)


@pytest.mark.parametrize(
    "parameter_set_lists,file_contents,num_expected_parameter_sets",
    [
        pytest.param([["Param1=Value"], ["Param1=Value2"]], "", 2, id="Single KVPs"),
        pytest.param(
            [["Param1=A", "Param2=1"], ["Param1=B", "Param2=2"]],
            "",
            2,
            id="Lists of KVPs",
        ),
        pytest.param(
            [["file://TEMPDIR/some-file.json"]],
            '{"Param1": "A", "Param2": 1}',
            1,
            id="File with single dictionary",
        ),
        pytest.param(
            [["file://TEMPDIR/some-file.json"], ["file://TEMPDIR/actually-the-same-contents.json"]],
            '{"Param1": "A", "Param2": 1}',
            2,
            id="Multiple files with single dictionary",
        ),
        pytest.param(
            [["file://TEMPDIR/some-file.json"]],
            '[{"Param1": "A", "Param2": 1}, {"Param1": "B", "Param2": 2}]',
            2,
            id="File with list of dictionaries",
        ),
        pytest.param(
            [
                ["Param1=A", "Param2=1"],
                ["Param1=B", "Param2=2"],
                ["file://TEMPDIR/some-file.json"],
            ],
            '[{"Param1": "E", "Param2": 5}]',
            3,
            id="Combination of formats",
        ),
    ],
)
def test_get_task_params_success(
    parameter_set_lists: list[list[str]],
    file_contents: str,
    num_expected_parameter_sets: int,
):
    """
    Test that Task parameters can be resolved from differently-formatted arguments.
    """

    # For each file argument, we create a file in a temporary directory to reference
    with tempfile.TemporaryDirectory() as temp_dir:
        # No nice way around it; argument format demands a nested for-loop
        for parameter_list in parameter_set_lists:
            for i, file_arg in enumerate(parameter_list):
                if file_arg.startswith("file://TEMPDIR/"):
                    param_file = open(
                        os.path.join(temp_dir, file_arg.removeprefix("file://TEMPDIR/")), "x"
                    )
                    param_file.write(file_contents)
                    param_file.close()

                    parameter_list[i] = file_arg.replace("TEMPDIR", temp_dir)

        task_params = get_task_params(parameter_set_lists)

        assert len(task_params) == num_expected_parameter_sets


@pytest.mark.parametrize(
    "parameter_set_lists,file_contents,expected_errors",
    [
        pytest.param(
            [["badformat"]],
            "",
            ["should be in the format 'Key=Value'"],
            id="Badly-formed KVP",
        ),
        pytest.param(
            [["keyvalue", "Key=Value", "valuekey"]],
            "",
            [
                "'keyvalue' should be in the format 'Key=Value'",
                "'valuekey' should be in the format 'Key=Value'",
            ],
            id="Multiple badly-formed KVPs in same set",
        ),
        pytest.param(
            [
                ["Key=Value", "Key2=Value2"],
                ["keyvalue", "valuekey"],
                ["Key3=Value3", "anotherbadparam"],
            ],
            "",
            [
                "'keyvalue' should be in the format 'Key=Value'",
                "'valuekey' should be in the format 'Key=Value'",
                "'anotherbadparam' should be in the format 'Key=Value'",
            ],
            id="Badly-formed KVPs in multiple sets",
        ),
        pytest.param(
            [["file://TEMPDIR/some-file.json"]],
            '[["a list"], 5, "a string"]',
            ["contains non-dictionary entries: [['a list'], 5, 'a string']"],
            id="File containing non-dictionary parameters",
        ),
    ],
)
def test_get_task_params_error(
    parameter_set_lists: list[list[str]],
    file_contents: str,
    expected_errors: list[str],
):
    """
    Test that incorrectly-formatted Task parameters throw the expected errors.
    """

    # Create all files in a temporary directory so they are automatically cleaned up
    with tempfile.TemporaryDirectory() as temp_dir:
        for parameter_list in parameter_set_lists:
            for i, file_arg in enumerate(parameter_list):
                if file_arg.startswith("file://TEMPDIR/"):
                    param_file = open(
                        os.path.join(temp_dir, file_arg.removeprefix("file://TEMPDIR/")), "x"
                    )
                    param_file.write(file_contents)
                    param_file.close()

                    parameter_list[i] = file_arg.replace("TEMPDIR", temp_dir)

        with pytest.raises(RuntimeError) as rte:
            get_task_params(parameter_set_lists)

        assert all([msg in str(rte.value) for msg in expected_errors])


@pytest.mark.parametrize(
    "template_dict,param_list,expected_param_list",
    [
        pytest.param(MOCK_TEMPLATE, None, None, id="No Job parameters"),
        pytest.param(MOCK_TEMPLATE, [], None, id="Empty Job parameters"),
        pytest.param(
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            MOCK_PARAM_ARGUMENTS,
            MOCK_PARAM_ARGUMENTS,
            id="With Job parameters",
        ),
    ],
)
def test_generate_job_success(
    template_dict: dict, param_list: list[str], expected_param_list: list
):
    """
    Test that a Namespace object can be used to generate a Job correctly.
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=".template.json", encoding="utf8", delete=False
    ) as temp_template:
        json.dump(template_dict, temp_template.file)

    mock_args = Namespace(
        path=Path(temp_template.name), job_params=param_list, output="human-readable"
    )

    # Patch `job_from_template` to "spy" on its call, ensuring that it
    # gets passed the right parameters
    with patch(
        "openjd.cli._common.job_from_template",
        new=Mock(side_effect=job_from_template),
    ) as patched_job_from_template:
        generate_job(mock_args)
        patched_job_from_template.assert_called_once_with(
            ANY, expected_param_list, Path(temp_template.name).parent, Path(os.getcwd())
        )

    Path(temp_template.name).unlink()
