# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
from pathlib import Path
from unittest.mock import Mock, patch
from typing import Optional
import json
import pytest
import tempfile

from . import MOCK_TEMPLATE, MOCK_TEMPLATE_REQUIRES_PARAMS
from openjd.cli._summary._summary_command import do_summary
from openjd.cli._summary._summary_output import (
    OpenJDJobSummaryResult,
    OpenJDStepSummaryResult,
    output_summary_result,
)

from openjd.model import (
    JobParameterValues,
    ParameterValue,
    ParameterValueType,
    create_job,
    decode_template,
)


@pytest.mark.parametrize(
    "mock_params,mock_step,template",
    [
        pytest.param(None, None, MOCK_TEMPLATE, id="No extra options"),
        pytest.param(None, "NormalStep", MOCK_TEMPLATE, id="Step given"),
        pytest.param(
            ["RequiredParam=5"],
            None,
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            id="Job params given",
        ),
        pytest.param(
            ["RequiredParam=5"],
            "step1",
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            id="Step & Job params given",
        ),
    ],
)
def test_do_summary_success(
    mock_params: Optional[list[str]],
    mock_step: Optional[str],
    template: dict,
):
    """
    Test that the `summary` command succeeds with various argument options.
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=".template.json", encoding="utf8", delete=False
    ) as temp_template:
        json.dump(template, temp_template.file)

    mock_args = Namespace(
        path=Path(temp_template.name),
        job_params=mock_params,
        step=mock_step,
        output="human-readable",
    )
    do_summary(mock_args)

    Path(temp_template.name).unlink()


def test_do_summary_error():
    """
    Test that the `summary` command exits on any error (in this case, we mock an error in `read_template`)
    """
    mock_args = Namespace(path=Path("some-file.json"), output="human-readable")
    with patch(
        "openjd.cli._common.read_template", new=Mock(side_effect=RuntimeError())
    ), pytest.raises(SystemExit):
        do_summary(mock_args)


@pytest.mark.parametrize(
    "mock_job_params,expected_job_name,step_name,expected_tasks,expected_dependencies,expected_total_envs,template_dict",
    [
        pytest.param(
            JobParameterValues({}),
            "my-job",
            "BareStep",
            1,
            [],
            0,
            MOCK_TEMPLATE,
            id="No Job parameters, dependencies, or environments",
        ),
        pytest.param(
            JobParameterValues({}),
            "my-job",
            "DependentStep",
            1,
            ["NormalStep"],
            0,
            MOCK_TEMPLATE,
            id="With dependencies",
        ),
        pytest.param(
            JobParameterValues({}),
            "my-job",
            "NormalStep",
            1,
            [],
            1,
            MOCK_TEMPLATE,
            id="With environments",
        ),
        pytest.param(
            JobParameterValues(
                {
                    "Title": ParameterValue(type=ParameterValueType.STRING, value="new title"),
                    "RequiredParam": ParameterValue(type=ParameterValueType.INT, value="5"),
                }
            ),
            "new title",
            "step1",
            1,
            [],
            0,
            MOCK_TEMPLATE_REQUIRES_PARAMS,
            id="Job parameters supplied",
        ),
        pytest.param(
            {},
            "template",
            "step1",
            5,
            [],
            0,
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "steps": [
                    {
                        "name": "step1",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "taskNumber", "type": "INT", "range": [1, 2, 3, 4, 5]}
                            ]
                        },
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": 'echo "Task ran {{Task.Param.taskNumber}} times"'
                                }
                            }
                        },
                    }
                ],
            },
            id="With Task parameters",
        ),
        pytest.param(
            JobParameterValues({"Runs": ParameterValue(type=ParameterValueType.INT, value="7")}),
            "template",
            "step1",
            8,
            [],
            0,
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "parameterDefinitions": [{"name": "Runs", "type": "INT", "default": 1}],
                "steps": [
                    {
                        "name": "step1",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "taskNumber", "type": "INT", "range": "0-{{Param.Runs}}"}
                            ]
                        },
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": 'echo "Task ran {{Task.Param.taskNumber}} times"'
                                }
                            }
                        },
                    }
                ],
            },
            id="Task parameters set by Job parameter",
        ),
        pytest.param(
            {},
            "template",
            "step1",
            10,
            [],
            0,
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "steps": [
                    {
                        "name": "step1",
                        "parameterSpace": {
                            "taskParameterDefinitions": [
                                {"name": "param1", "type": "INT", "range": [1, 2, 3, 4, 5]},
                                {"name": "param2", "type": "INT", "range": [6, 7, 8, 9, 10]},
                                {"name": "param3", "type": "STRING", "range": ["yes", "no"]},
                            ],
                            "combination": "(param1, param2) * param3",
                        },
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": 'echo "{{Task.Param.param1}} {{Task.Param.param2}} {{Task.Param.param3}}"'
                                }
                            }
                        },
                    },
                ],
            },
            id="Task parameters with combination expression",
        ),
    ],
)
def test_get_output_step_summary_success(
    mock_job_params: JobParameterValues,
    expected_job_name: str,
    step_name: str,
    expected_tasks: int,
    expected_dependencies: list,
    expected_total_envs: int,
    template_dict: dict,
) -> None:
    """
    Test that `output_summary_result` returns an object with the expected values when called with a Step.
    """
    template = decode_template(template=template_dict)
    job = create_job(job_template=template, job_parameter_values=mock_job_params)

    response = output_summary_result(job, step_name)
    assert isinstance(response, OpenJDStepSummaryResult)
    assert response.status == "success"
    assert response.job_name == expected_job_name
    assert response.step_name == step_name
    assert response.total_tasks == expected_tasks
    assert response.total_environments == expected_total_envs

    if response.dependencies:
        assert (dep.step_name in expected_dependencies for dep in response.dependencies)


def test_output_step_summary_result_error():
    """
    Test that `output_summary_result` throws an error if a non-existent Step name is provided.
    (function only has one error state)
    """
    template = decode_template(template=MOCK_TEMPLATE)
    job = create_job(job_template=template, job_parameter_values={})

    response = output_summary_result(job, "no step")
    assert response.status == "error"
    assert "Step 'no step' does not exist in Job 'my-job'" in response.message


@pytest.mark.parametrize(
    "mock_params,expected_name,expected_params,expected_steps,expected_total_tasks,expected_total_envs,expected_root_envs,template_dict",
    [
        pytest.param(
            {},
            "template",
            [],
            ["step1"],
            1,
            0,
            [],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "steps": [
                    {
                        "name": "step1",
                        "script": {"actions": {"onRun": {"command": 'echo "Hello, world!"'}}},
                    }
                ],
            },
            id="No parameters or environments",
        ),
        pytest.param(
            {},
            "DefaultValue",
            [("NameParam", "DefaultValue")],
            ["step1"],
            1,
            0,
            [],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "{{Param.NameParam}}",
                "parameterDefinitions": [
                    {"name": "NameParam", "type": "STRING", "default": "DefaultValue"}
                ],
                "steps": [
                    {
                        "name": "step1",
                        "script": {"actions": {"onRun": {"command": 'echo "Hello, world!"'}}},
                    }
                ],
            },
            id="Default parameters",
        ),
        pytest.param(
            JobParameterValues(
                {"NameParam": ParameterValue(type=ParameterValueType.STRING, value="NewName")}
            ),
            "NewName",
            [("NameParam", "NewName")],
            ["step1"],
            1,
            0,
            [],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "{{Param.NameParam}}",
                "parameterDefinitions": [
                    {"name": "NameParam", "type": "STRING", "default": "DefaultValue"}
                ],
                "steps": [
                    {
                        "name": "step1",
                        "script": {"actions": {"onRun": {"command": 'echo "Hello, world!"'}}},
                    }
                ],
            },
            id="Overwritten parameters",
        ),
        pytest.param(
            {},
            "template",
            [],
            ["step1"],
            1,
            1,
            ["aRootEnv"],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "jobEnvironments": [{"name": "aRootEnv", "variables": {"variable": "value"}}],
                "steps": [
                    {
                        "name": "step1",
                        "script": {"actions": {"onRun": {"command": 'echo "Hello, world!"'}}},
                    }
                ],
            },
            id="Root environments only",
        ),
        pytest.param(
            {},
            "template",
            [],
            ["step1"],
            1,
            1,
            [],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "steps": [
                    {
                        "name": "step1",
                        "script": {"actions": {"onRun": {"command": 'echo "Hello, world!"'}}},
                        "stepEnvironments": [
                            {"name": "aStepEnv", "variables": {"variable": "value"}}
                        ],
                    }
                ],
            },
            id="Step environments only",
        ),
        pytest.param(
            {},
            "template",
            [],
            ["step1"],
            1,
            2,
            ["aRootEnv"],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "jobEnvironments": [{"name": "aRootEnv", "variables": {"variable": "value"}}],
                "steps": [
                    {
                        "name": "step1",
                        "script": {"actions": {"onRun": {"command": 'echo "Hello, world!"'}}},
                        "stepEnvironments": [
                            {"name": "aStepEnv", "variables": {"variable": "value"}}
                        ],
                    }
                ],
            },
            id="Root and Step level environments",
        ),
        pytest.param(
            {},
            "template",
            [],
            ["step1", "step2"],
            2,
            2,
            [],
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "template",
                "steps": [
                    {
                        "name": "step1",
                        "script": {
                            "actions": {"onRun": {"command": 'echo "We can have lots of fun"'}}
                        },
                        "stepEnvironments": [
                            {"name": "step1Env", "variables": {"variable": "value"}}
                        ],
                    },
                    {
                        "name": "step2",
                        "script": {
                            "actions": {"onRun": {"command": 'echo "There\'s so much we can do"'}}
                        },
                        "stepEnvironments": [
                            {"name": "step2Env", "variables": {"variable": "value"}}
                        ],
                    },
                ],
            },
            id="Environments in multiple steps",
        ),
    ],
)
def test_output_job_summary_result_success(
    mock_params: JobParameterValues,
    expected_name: str,
    expected_params: list,
    expected_steps: list,
    expected_total_tasks: int,
    expected_total_envs: int,
    expected_root_envs: list,
    template_dict: dict,
):
    """
    Test that `output_summary_result` returns an object with the expected values when called on a Job.
    """
    template = decode_template(template=template_dict)
    job = create_job(job_template=template, job_parameter_values=mock_params)

    response = output_summary_result(job)
    assert isinstance(response, OpenJDJobSummaryResult)
    assert response.status == "success"
    assert response.name == expected_name

    if response.parameter_definitions:
        assert [
            (param.name, param.value) for param in response.parameter_definitions
        ] == expected_params

    assert response.total_steps == len(expected_steps)
    assert [step.name for step in response.steps] == expected_steps

    assert response.total_tasks == expected_total_tasks

    assert response.total_environments == expected_total_envs
    if response.root_environments:
        assert [env.name for env in response.root_environments] == expected_root_envs
