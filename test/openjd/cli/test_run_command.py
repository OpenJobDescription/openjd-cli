# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import tempfile
import re
import os
from typing import Any

import pytest
from unittest.mock import Mock, patch

from . import MOCK_TEMPLATE, SampleSteps
from openjd.cli._run._run_command import (
    OpenJDRunResult,
    do_run,
    _run_local_session,
)
from openjd.cli._run._local_session._session_manager import LocalSession
from openjd.sessions import PathMappingRule, PathFormat, Session


TEST_RUN_JOB_TEMPLATE_BASIC = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "Job",
    "parameterDefinitions": [{"name": "J", "type": "STRING"}],
    "jobEnvironments": [
        {
            "name": "J1",
            "script": {
                "actions": {
                    "onEnter": {"command": "echo", "args": ["J1 Enter"]},
                    "onExit": {"command": "echo", "args": ["J1 Exit"]},
                }
            },
        },
        {
            "name": "J2",
            "script": {
                "actions": {
                    "onEnter": {"command": "echo", "args": ["J2 Enter"]},
                    "onExit": {"command": "echo", "args": ["J2 Exit"]},
                }
            },
        },
    ],
    "steps": [
        {
            "name": "First",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Foo", "type": "INT", "range": "1"},
                    {"name": "Bar", "type": "STRING", "range": ["Bar1", "Bar2"]},
                ]
            },
            "stepEnvironments": [
                {
                    "name": "FirstS",
                    "script": {
                        "actions": {
                            "onEnter": {"command": "echo", "args": ["FirstS Enter"]},
                            "onExit": {"command": "echo", "args": ["FirstS Exit"]},
                        }
                    },
                },
            ],
            "script": {
                "actions": {
                    "onRun": {
                        "command": "echo",
                        "args": [
                            "J={{Param.J}} Foo={{Task.Param.Foo}}. Bar={{Task.Param.Bar}}",
                        ],
                    }
                }
            },
        }
    ],
}

TEST_RUN_JOB_TEMPLATE_DEPENDENCY = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "Job",
    "parameterDefinitions": [{"name": "J", "type": "STRING"}],
    "jobEnvironments": [
        {
            "name": "J1",
            "script": {
                "actions": {
                    "onEnter": {"command": "echo", "args": ["J1 Enter"]},
                    "onExit": {"command": "echo", "args": ["J1 Exit"]},
                }
            },
        },
    ],
    "steps": [
        {
            "name": "First",
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Foo", "type": "INT", "range": "1"},
                    {"name": "Bar", "type": "STRING", "range": ["Bar1", "Bar2"]},
                ]
            },
            "script": {
                "actions": {
                    "onRun": {
                        "command": "echo",
                        "args": [
                            "J={{Param.J}} Foo={{Task.Param.Foo}}. Bar={{Task.Param.Bar}}",
                        ],
                    }
                }
            },
        },
        {
            "name": "Second",
            "dependencies": [{"dependsOn": "First"}],
            "parameterSpace": {
                "taskParameterDefinitions": [
                    {"name": "Fuz", "type": "INT", "range": "1-2"},
                ]
            },
            "script": {
                "actions": {
                    "onRun": {
                        "command": "echo",
                        "args": [
                            "J={{Param.J}} Fuz={{Task.Param.Fuz}}.",
                        ],
                    }
                }
            },
        },
    ],
}

TEST_RUN_ENV_TEMPLATE_1 = {
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "Env1",
        "script": {
            "actions": {
                "onEnter": {"command": "echo", "args": ["Env1 Enter"]},
                "onExit": {"command": "echo", "args": ["Env1 Exit"]},
            }
        },
    },
}

TEST_RUN_ENV_TEMPLATE_2 = {
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "Env2",
        "script": {
            "actions": {
                "onEnter": {"command": "echo", "args": ["Env2 Enter"]},
                "onExit": {"command": "echo", "args": ["Env2 Exit"]},
            }
        },
    },
}


@pytest.mark.parametrize(
    "job_template,env_templates,step_name,task_params,run_dependencies,expected_output,expected_not_in_output",
    [
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_BASIC,
            [],  # Env Templates
            "First",  # step name
            [],  # Task params
            True,  # run_dependencies
            re.compile(
                r"J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*FirstS Exit.*J2 Exit.*J1 Exit"
            ),
            "",
            id="RunFirstStep",
        ),
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_BASIC,
            [],  # Env Templates
            "First",  # step name
            [["Foo=1 Bar=Bar1"]],  # Task params
            True,  # run_dependencies
            re.compile(
                r"J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*FirstS Exit.*J2 Exit.*J1 Exit"
            ),
            "Foo=1. Bar=Bar2",
            id="RunSelectTask",
        ),
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_DEPENDENCY,
            [],  # Env Templates
            "Second",  # step name
            [],  # Task params
            True,  # run_dependencies
            re.compile(
                r"J1 Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*J=Jvalue Fuz=1.*J=Jvalue Fuz=2.*J1 Exit"
            ),
            "",
            id="RunSecondStepWithDep",
        ),
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_DEPENDENCY,
            [],  # Env Templates
            "Second",  # step name
            [],  # Task params
            False,  # run_dependencies
            re.compile(r"J1 Enter.*J=Jvalue Fuz=1.*J=Jvalue Fuz=2.*J1 Exit"),
            "Foo=1. Bar=Bar1",
            id="RunSecondStepNoDep",
        ),
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_BASIC,
            [TEST_RUN_ENV_TEMPLATE_1],  # Env Templates
            "First",  # step name
            [],  # Task params
            True,  # run_dependencies
            re.compile(
                r"Env1 Enter.*J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*FirstS Exit.*J2 Exit.*J1 Exit.*Env1 Exit"
            ),
            "",
            id="WithOneEnv",
        ),
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_BASIC,
            [TEST_RUN_ENV_TEMPLATE_1, TEST_RUN_ENV_TEMPLATE_2],  # Env Templates
            "First",  # step name
            [],  # Task params
            True,  # run_dependencies
            re.compile(
                r"Env1 Enter.*Env2 Enter.*J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*FirstS Exit.*J2 Exit.*J1 Exit.*Env2 Exit.*Env1 Exit"
            ),
            "",
            id="WithTwoEnvs",
        ),
    ],
)
def test_do_run_success(
    job_template: dict[str, Any],
    env_templates: list[dict[str, Any]],
    step_name: str,
    task_params: list[list[str]],
    run_dependencies: bool,
    expected_output: re.Pattern[str],
    expected_not_in_output: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the 'run' command correctly runs templates and obtains the expected results."""

    files_created: list[Path] = []
    try:
        # GIVEN
        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".template.json", encoding="utf8", delete=False
        ) as job_template_file:
            json.dump(job_template, job_template_file.file)
        files_created.append(Path(job_template_file.name))

        environments_files: list[str] = []
        for e in env_templates:
            with tempfile.NamedTemporaryFile(
                mode="w+t", suffix=".env.template.json", encoding="utf8", delete=False
            ) as file:
                json.dump(e, file.file)
            files_created.append(Path(file.name))
            environments_files.append(file.name)

        args = Namespace(
            path=Path(job_template_file.name),
            step=step_name,
            job_params=["J=Jvalue"],
            task_params=task_params,
            maximum_tasks=-1,
            run_dependencies=run_dependencies,
            path_mapping_rules=None,
            environments=environments_files,
            output="human-readable",
        )

        # WHEN
        do_run(args)

        # THEN
        assert not any(
            os.linesep in m for m in caplog.messages
        ), "paranoia; Windows is acting weird"
        assert expected_output.search("".join(m.strip() for m in caplog.messages))
        if expected_not_in_output:
            assert expected_not_in_output not in caplog.text
    finally:
        for f in files_created:
            f.unlink()


def test_do_run_error():
    """
    Test that the `run` command exits on any error (e.g., a non-existent template file).
    """
    mock_args = Namespace(
        path=Path("some-file.json"),
        step="aStep",
        job_params=None,
        task_params=None,
        run_dependencies=False,
        path_mapping_rules=None,
        environments=[],
        output="human-readable",
    )
    with pytest.raises(SystemExit):
        do_run(mock_args)


def test_do_run_path_mapping_rules(caplog: pytest.LogCaptureFixture):
    """
    Test that the `run` command exits on any error (e.g., a non-existent template file).
    """
    # GIVEN
    job_template = {
        "specificationVersion": "jobtemplate-2023-09",
        "name": "Job",
        "parameterDefinitions": [{"name": "TestPath", "type": "PATH"}],
        "steps": [
            {
                "name": "TestStep",
                "script": {
                    "actions": {"onRun": {"command": "echo", "args": ["Mapped:{{Param.TestPath}}"]}}
                },
            }
        ],
    }
    path_mapping_rules = {
        "version": "pathmapping-1.0",
        "path_mapping_rules": [
            {
                "source_path_format": "POSIX" if os.name == "posix" else "WINDOWS",
                "source_path": r"/home/test" if os.name == "posix" else r"C:\test",
                "destination_path": "/mnt/test",
            }
        ],
    }

    try:
        # Set up a rules file and a job template file
        temp_rules = temp_template = None
        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".rules.json", encoding="utf8", delete=False
        ) as temp_rules:
            json.dump(path_mapping_rules, temp_rules.file)

        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".template.json", encoding="utf8", delete=False
        ) as temp_template:
            json.dump(job_template, temp_template.file)

        run_args = Namespace(
            path=Path(temp_template.name),
            step="TestStep",
            job_params=[r"TestPath=/home/test" if os.name == "posix" else r"TestPath=c:\test"],
            task_params=None,
            run_dependencies=False,
            output="human-readable",
            path_mapping_rules="file://" + temp_rules.name,
            environments=[],
            maximum_tasks=1,
        )

        # WHEN
        do_run(run_args)

        # THEN
        assert not any(
            os.linesep in m for m in caplog.messages
        ), "paranoia; Windows is acting weird."
        if os.name == "posix":
            assert any("Mapped:/mnt/test" in m for m in caplog.messages)
        else:
            assert any(r"Mapped:\\mnt\\test" in m for m in caplog.messages)
    finally:
        if temp_rules:
            Path(temp_rules.name).unlink()
        if temp_template:
            Path(temp_template.name).unlink()


@pytest.mark.usefixtures("capsys")
def test_do_run_nonexistent_step(capsys: pytest.CaptureFixture):
    """
    Test that invoking the `run` command with an incorrect Step name produces the right output.
    (This doesn't actually raise an error, so we have to test the output by capturing `stdout`.)
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=".template.json", encoding="utf8", delete=False
    ) as temp_template:
        json.dump(MOCK_TEMPLATE, temp_template.file)

    mock_args = Namespace(
        path=Path(temp_template.name),
        step="FakeStep",
        job_params=None,
        task_params=None,
        maximum_tasks=-1,
        run_dependencies=False,
        path_mapping_rules=None,
        environments=[],
        output="human-readable",
    )
    with pytest.raises(SystemExit):
        do_run(mock_args)
    assert "Step 'FakeStep' does not exist" in capsys.readouterr().out

    Path(temp_template.name).unlink()


@pytest.mark.usefixtures(
    "sample_job_and_dirs", "sample_step_map", "patched_session_cleanup", "capsys"
)
@pytest.mark.parametrize(
    "step_index,dependency_indexes,should_run_dependencies",
    [
        pytest.param(SampleSteps.BareStep, [], False, id="Bare Step"),
        pytest.param(
            SampleSteps.BareStep,
            [],
            True,
            id="--run-dependencies with no dependencies",
        ),
        pytest.param(SampleSteps.TaskParamStep, [], False, id="Task param Step"),
        pytest.param(SampleSteps.NormalStep, [], False, id="Catch-all Step"),
        pytest.param(
            SampleSteps.NormalStep,
            [],
            True,
            id="--run-dependencies with Step environment but no dependencies",
        ),
        pytest.param(
            SampleSteps.DependentStep,
            [SampleSteps.BareStep],
            True,
            id="Step with direct dependency",
        ),
        pytest.param(
            SampleSteps.ExtraDependentStep,
            [
                SampleSteps.BareStep,
                SampleSteps.DependentStep,
                SampleSteps.TaskParamStep,
            ],
            True,
            id="Step with transitive and direct dependencies",
        ),
        pytest.param(SampleSteps.DependentStep, [], False, id="Exclude dependencies"),
    ],
)
def test_run_local_session_success(
    sample_job_and_dirs: tuple,
    sample_step_map: dict,
    patched_session_cleanup: Mock,
    capsys: pytest.CaptureFixture,
    step_index: int,
    dependency_indexes: list[int],
    should_run_dependencies: bool,
):
    """
    Test that various Job structures can successfully run local Sessions.

    Note that we don't need to test with custom Task parameters, as those are
    tested within the `LocalSession` object.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    path_mapping_rules = [
        PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath(r"C:\test"),
            destination_path=PurePosixPath("/mnt/test"),
        )
    ]
    with patch.object(
        LocalSession, "initialize", autospec=True, side_effect=LocalSession.initialize
    ) as patched_initialize, patch.object(
        Session, "__init__", autospec=True, side_effect=Session.__init__
    ) as patched_session_init:
        response = _run_local_session(
            job=sample_job,
            step_map=sample_step_map,
            step=sample_job.steps[step_index],
            path_mapping_rules=path_mapping_rules,
            should_run_dependencies=should_run_dependencies,
        )
        assert patched_initialize.call_args.kwargs["dependencies"] == [
            sample_job.steps[i] for i in dependency_indexes
        ]
        assert patched_initialize.call_args.kwargs["step"] == sample_job.steps[step_index]
        assert patched_session_init.call_args.kwargs["path_mapping_rules"] == path_mapping_rules

    assert response.status == "success"
    assert isinstance(response, OpenJDRunResult)
    assert response.job_name == sample_job.name
    assert response.step_name == sample_job.steps[step_index].name
    assert "Open Job Description CLI: All actions completed successfully" in capsys.readouterr().out
    patched_session_cleanup.assert_called()


@pytest.mark.usefixtures("sample_job_and_dirs", "sample_step_map")
@pytest.mark.parametrize(
    "step_index,should_run_dependencies,expected_error",
    [
        pytest.param(
            SampleSteps.BadCommand, False, "Session ended with errors", id="Badly-formed command"
        ),
        pytest.param(
            SampleSteps.ShouldSeparateSession,
            True,
            "cannot be run in the same local Session",
            id="Can't run in single Session",
        ),
    ],
)
def test_run_local_session_failed(
    sample_job_and_dirs: tuple,
    sample_step_map: dict,
    step_index: int,
    should_run_dependencies: bool,
    expected_error: str,
):
    """
    Test the output of a Session that finishes after encountering errors.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    response = _run_local_session(
        job=sample_job,
        step_map=sample_step_map,
        step=sample_job.steps[step_index],
        path_mapping_rules=[],
        should_run_dependencies=should_run_dependencies,
    )

    assert response.status == "error"
    assert expected_error in response.message
