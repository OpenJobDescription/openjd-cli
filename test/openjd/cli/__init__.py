# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from enum import Enum

# Catch-all sample template with different cases per Step

MOCK_TEMPLATE = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "my-job",
    "parameterDefinitions": [{"name": "Message", "type": "STRING", "default": "Hello, world!"}],
    "jobEnvironments": [{"name": "rootEnv", "variables": {"rootVar": "rootVal"}}],
    "steps": [
        # VALID STEPS
        {
            # Basic step; uses Job parameters and has an environment
            "name": "NormalStep",
            "script": {
                "actions": {
                    "onRun": {"command": "python", "args": ["-c", "print('{{Param.Message}}')"]}
                }
            },
            "stepEnvironments": [
                {
                    "name": "env1",
                    "script": {
                        "actions": {
                            "onEnter": {"command": "python", "args": ["-c", "print('EnteringEnv')"]}
                        }
                    },
                }
            ],
        },
        {
            # Step that will wait for one minute before completing its Task
            "name": "LongCommand",
            "script": {"actions": {"onRun": {"command": "sleep", "args": ["60"]}}},
        },
        {
            # Step with the bare minimum information, i.e., no Task parameters, environments, or dependencies
            "name": "BareStep",
            "script": {"actions": {"onRun": {"command": "python", "args": ["-c", "print('zzz')"]}}},
        },
        {
            # Step with a direct dependency on a previous Step
            "name": "DependentStep",
            "script": {
                "actions": {
                    "onRun": {"command": "python", "args": ["-c", "print('I am dependent!')"]}
                }
            },
            "dependencies": [{"dependsOn": "BareStep"}],
        },
        {
            # Step with Task parameters
            "name": "TaskParamStep",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "TaskNumber", "type": "INT", "range": [1, 2, 3]},
                    {"name": "TaskMessage", "type": "STRING", "range": ["Hi!", "Bye!"]},
                ]
            },
            "script": {
                "actions": {
                    "onRun": {
                        "command": "python",
                        "args": [
                            "-c",
                            "print('{{Task.Param.TaskNumber}}.{{Task.Param.TaskMessage}}')",
                        ],
                    }
                }
            },
        },
        {
            # Step with a transitive dependency and a direct dependency
            "name": "ExtraDependentStep",
            "script": {
                "actions": {
                    "onRun": {"command": "python", "args": ["-c", "print('I am extra dependent!')"]}
                }
            },
            "dependencies": [{"dependsOn": "DependentStep"}, {"dependsOn": "TaskParamStep"}],
        },
        {
            # Step with dependencies and Task parameters
            "name": "DependentParamStep",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Adjective", "type": "STRING", "range": ["really", "very", "super"]}
                ],
            },
            "script": {
                "actions": {
                    "onRun": {
                        "command": "python",
                        "args": ["-c", "print('I am {{Task.Param.Adjective}} dependent!')"],
                    }
                }
            },
            "dependencies": [{"dependsOn": "TaskParamStep"}],
        },
        # ERROR STEPS
        {
            # Step with a non-existent command that will throw an error when run
            "name": "BadCommand",
            "script": {"actions": {"onRun": {"command": "aaaaaaaaaa"}}},
        },
        {
            # Step with a dependency it can't run in the same Session with
            "name": "ShouldSeparateSession",
            "script": {
                "actions": {
                    "onRun": {"command": "python", "args": ["-c", "print('I do not belong here!')"]}
                }
            },
            "dependencies": [{"dependsOn": "NormalStep"}],
        },
    ],
}

# Map of Step names to Step indices for more readable test cases


class SampleSteps(int, Enum):
    NormalStep = 0
    LongCommand = 1
    BareStep = 2
    DependentStep = 3
    TaskParamStep = 4
    ExtraDependentStep = 5
    DependentParamStep = 6
    BadCommand = 7
    ShouldSeparateSession = 8


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
    "dependency_indexes,step_index,maximum_tasks, parameter_sets,num_expected_environments,num_expected_tasks",
    [
        pytest.param([], SampleSteps.NormalStep, -1, None, 2, 1, id="Basic step"),
        pytest.param(
            [SampleSteps.BareStep],
            SampleSteps.DependentStep,
            -1,
            None,
            1,
            2,
            id="Direct dependency",
        ),
        pytest.param(
            [
                SampleSteps.BareStep,
                SampleSteps.DependentStep,
                SampleSteps.TaskParamStep,
            ],
            SampleSteps.ExtraDependentStep,
            -1,
            None,
            1,
            9,
            id="Dependencies and Task parameters",
        ),
        pytest.param(
            [SampleSteps.BareStep, SampleSteps.DependentStep, SampleSteps.TaskParamStep],
            SampleSteps.ExtraDependentStep,
            1,
            None,
            1,
            9,
            id="No maximum on dependencies' Tasks",
        ),
        pytest.param(
            [], SampleSteps.TaskParamStep, 1, None, 1, 1, id="Limit on maximum Task parameters"
        ),
        pytest.param(
            [],
            SampleSteps.TaskParamStep,
            100,
            None,
            1,
            6,
            id="Maximum Task parameters more than defined",
        ),
        pytest.param(
            [],
            SampleSteps.TaskParamStep,
            -1,
            [{"TaskNumber": 5}, {"TaskMessage": "Hello!"}],
            1,
            2,
            id="Custom parameter sets",
        ),
        pytest.param(
            [],
            SampleSteps.BareStep,
            -1,
            [{"Why": "Am"}, {"I": "Here"}],
            1,
            1,
            id="Task parameters for step not requiring them",
        ),
        pytest.param(
            [SampleSteps.TaskParamStep],
            SampleSteps.DependentParamStep,
            -1,
            [{"Adjective": "extremely"}, {"Adjective": "most"}],
            1,
            8,
            id="Custom Task parameters not applied to dependency",
        ),
        pytest.param(
            [],
            SampleSteps.TaskParamStep,
            1,
            [{"TaskMessage": "Hello!"}, {"TaskMessage": "Extra message!"}],
            1,
            1,
            id="Maximum Tasks less than number of parameter sets",
        ),
    ],
)
