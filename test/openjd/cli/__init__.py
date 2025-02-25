# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from enum import Enum
from typing import Any
from pathlib import Path

import yaml

from openjd.model import ParameterValue, ParameterValueType
from openjd.cli import main as openjd_cli_main


def run_openjd_cli_main(capsys, *, args: list[str], expected_exit_code: int) -> Any:
    """Wraps the logic to run the OpenJD CLI within a capsys environment"""
    try:
        openjd_cli_main(args)
        exit_code = 0
    except SystemExit as e:
        exit_code = e.code  # type: ignore

    outerr = capsys.readouterr()

    assert (
        exit_code == expected_exit_code
    ), f"Expected exit code {expected_exit_code}, but got {exit_code}:\n{format_capsys_outerr(outerr)}"

    return outerr


def format_capsys_outerr(outerr: Any) -> str:
    """Formats the capsys stdout and stderr to insert in an assertion message"""
    return f"\nstdout:\n{outerr.out}\nstderr:\n{outerr.err}"


# Catch-all sample template with different cases per Step

MOCK_TEMPLATE = yaml.safe_load(
    (Path(__file__).parent / "templates" / "job_with_test_steps.yaml").read_text(encoding="utf8")
)

# Map of Step names to Step indices for more readable test cases


class SampleSteps(int, Enum):
    NormalStep = 0
    LongCommand = 1
    BareStep = 2
    DependentStep = 3
    TaskParamStep = 4
    ExtraDependentStep = 5
    DependentParamStep = 6
    StepDepHasStepEnv = 7
    BadCommand = 8


# Sample dictionaries for tests using Job parameters

MOCK_TEMPLATE_REQUIRES_PARAMS = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "{{Param.Title}}",
    "parameterDefinitions": [
        {"name": "Title", "type": "STRING", "minLength": 3, "default": "my job"},
        {"name": "RequiredParam", "type": "INT", "minValue": 3, "maxValue": 8},
    ],
    "steps": [
        {
            "name": "step1",
            "script": {
                "actions": {
                    "onRun": {
                        "command": "python",
                        "args": ["-c", "print('{{Param.RequiredParam}}')"],
                    }
                }
            },
        },
        {
            "name": "step2",
            "script": {
                "actions": {
                    "onRun": {"command": "python", "args": ["-c", "print('Hello, world!'}"]}
                }
            },
            "stepEnvironments": [
                {"name": "my-step1-environment", "variables": {"variable": "value"}}
            ],
            "dependencies": [{"dependsOn": "step1"}],
        },
    ],
}

MOCK_PARAM_ARGUMENTS = ["Title=overwrite", "RequiredParam=5"]
MOCK_PARAM_VALUES = {"Title": "overwrite", "RequiredParam": "5"}

# Shared parameters for `LocalSession` tests to be used with `@pytest.mark.parametrize`

SESSION_PARAMETERS = (
    "step_index,maximum_tasks, parameter_sets,num_expected_tasks",
    [
        pytest.param(SampleSteps.NormalStep, -1, None, 1, id="Basic step"),
        pytest.param(
            SampleSteps.DependentStep,
            -1,
            None,
            1,
            id="Direct dependency",
        ),
        pytest.param(
            SampleSteps.ExtraDependentStep,
            -1,
            None,
            1,
            id="Dependencies and Task parameters",
        ),
        pytest.param(
            SampleSteps.ExtraDependentStep,
            1,
            None,
            1,
            id="No maximum on dependencies' Tasks",
        ),
        pytest.param(SampleSteps.TaskParamStep, 1, None, 1, id="Limit on maximum Task parameters"),
        pytest.param(
            SampleSteps.TaskParamStep,
            100,
            None,
            6,
            id="Maximum Task parameters more than defined",
        ),
        pytest.param(
            SampleSteps.TaskParamStep,
            -1,
            [
                {
                    "TaskNumber": ParameterValue(type=ParameterValueType.INT, value="2"),
                    "TaskMessage": ParameterValue(type=ParameterValueType.STRING, value="Bye!"),
                },
                {
                    "TaskNumber": ParameterValue(type=ParameterValueType.INT, value="1"),
                    "TaskMessage": ParameterValue(type=ParameterValueType.STRING, value="Hi!"),
                },
            ],
            2,
            id="Custom parameter sets",
        ),
        pytest.param(
            SampleSteps.BareStep,
            -1,
            [
                {"Why": ParameterValue(type=ParameterValueType.STRING, value="Am")},
                {"I": ParameterValue(type=ParameterValueType.STRING, value="Here")},
            ],
            2,
            id="Task parameters for step not requiring them",
        ),
        pytest.param(
            SampleSteps.DependentParamStep,
            -1,
            [
                {"Adjective": ParameterValue(type=ParameterValueType.STRING, value="extremely")},
                {"Adjective": ParameterValue(type=ParameterValueType.STRING, value="most")},
            ],
            2,
            id="Custom Task parameters not applied to dependency",
        ),
        pytest.param(
            SampleSteps.TaskParamStep,
            1,
            [
                {
                    "TaskNumber": ParameterValue(type=ParameterValueType.INT, value="2"),
                    "TaskMessage": ParameterValue(type=ParameterValueType.STRING, value="Hi!"),
                },
                {
                    "TaskNumber": ParameterValue(type=ParameterValueType.INT, value="2"),
                    "TaskMessage": ParameterValue(type=ParameterValueType.STRING, value="Bye!"),
                },
            ],
            1,
            id="Maximum Tasks less than number of parameter sets",
        ),
    ],
)
