# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import tempfile
import re
import os
from typing import Any, Optional
import logging

import pytest
from unittest.mock import Mock, patch

from . import MOCK_TEMPLATE, SampleSteps
from openjd.cli._run._run_command import (
    OpenJDRunResult,
    do_run,
    _run_local_session,
    _process_task_params,
    _process_tasks,
    _validate_task_params,
)
from openjd.cli._run._local_session._session_manager import LocalSession
from openjd.sessions import LOG as SessionsLogger, PathMappingRule, PathFormat, Session
from openjd.model import decode_job_template, create_job, ParameterValue, ParameterValueType


TEST_RUN_JOB_TEMPLATE_BASIC = {
    "specificationVersion": "jobtemplate-2023-09",
    "name": "Job",
    "parameterDefinitions": [{"name": "J", "type": "STRING"}],
    "jobEnvironments": [
        {
            "name": "J1",
            "script": {
                "actions": {
                    "onEnter": {"command": "python", "args": ["-c", "print('J1 Enter')"]},
                    "onExit": {"command": "python", "args": ["-c", "print('J1 Exit')"]},
                }
            },
        },
        {
            "name": "J2",
            "script": {
                "actions": {
                    "onEnter": {"command": "python", "args": ["-c", "print('J2 Enter')"]},
                    "onExit": {"command": "python", "args": ["-c", "print('J2 Exit')"]},
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
                            "onEnter": {
                                "command": "python",
                                "args": ["-c", "print('FirstS Enter')"],
                            },
                            "onExit": {"command": "python", "args": ["-c", "print('FirstS Exit')"]},
                        }
                    },
                },
            ],
            "script": {
                "actions": {
                    "onRun": {
                        "command": "python",
                        "args": [
                            "-c",
                            "print('J={{Param.J}} Foo={{Task.Param.Foo}}. Bar={{Task.Param.Bar}}')",
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
                    "onEnter": {"command": "python", "args": ["-c", "print('J1 Enter')"]},
                    "onExit": {"command": "python", "args": ["-c", "print('J1 Exit')"]},
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
                        "command": "python",
                        "args": [
                            "-c",
                            "print('J={{Param.J}} Foo={{Task.Param.Foo}}. Bar={{Task.Param.Bar}}')",
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
                        "command": "python",
                        "args": [
                            "-c",
                            "print('J={{Param.J}} Fuz={{Task.Param.Fuz}}.')",
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
                "onEnter": {"command": "python", "args": ["-c", "print('Env1 Enter')"]},
                "onExit": {"command": "python", "args": ["-c", "print('Env1 Exit')"]},
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
                "onEnter": {"command": "python", "args": ["-c", "print('Env2 Enter')"]},
                "onExit": {"command": "python", "args": ["-c", "print('Env2 Exit')"]},
            }
        },
    },
}

TEST_RUN_ENV_TEMPLATE_FAILS_ENTER = {
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "EnvEnterFail",
        "script": {
            "actions": {
                "onEnter": {
                    "command": "python",
                    "args": ["-c", "import sys; print('EnvEnterFail Enter'); sys.exit(1)"],
                },
                "onExit": {"command": "python", "args": ["-c", "print('EnvEnterFail Exit')"]},
            }
        },
    },
}

TEST_RUN_ENV_TEMPLATE_FAILS_EXIT = {
    "specificationVersion": "environment-2023-09",
    "environment": {
        "name": "EnvExitFail",
        "script": {
            "actions": {
                "onEnter": {"command": "python", "args": ["-c", "print('EnvExitFail Enter')"]},
                "onExit": {
                    "command": "python",
                    "args": ["-c", "import sys; print('EnvExitFail Exit'); sys.exit(1)"],
                },
            }
        },
    },
}


@pytest.mark.parametrize(
    "job_template,env_templates,step_name,task_params,run_dependencies,expected_output,expected_not_in_output,expect_system_exit",
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
            False,
            id="RunFirstStep",
        ),
        pytest.param(
            TEST_RUN_JOB_TEMPLATE_BASIC,
            [],  # Env Templates
            "First",  # step name
            ["Foo=1", "Bar=Bar1"],  # Task params
            True,  # run_dependencies
            re.compile(
                r"J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*FirstS Exit.*J2 Exit.*J1 Exit"
            ),
            "Foo=1. Bar=Bar2",
            False,
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
            False,
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
            False,
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
            False,
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
            False,
            id="WithTwoEnvs",
        ),
        pytest.param(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Test",
                "parameterDefinitions": [{"name": "J", "type": "STRING"}],
                "steps": [
                    {
                        "name": "SimpleStep",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "python",
                                    "args": ["-c", "print('DoTask')"],
                                }
                            }
                        },
                    }
                ],
            },
            [TEST_RUN_ENV_TEMPLATE_FAILS_ENTER],  # Env Templates
            "SimpleStep",  # step name
            [],  # Task params
            False,  # run_dependencies
            re.compile(r"EnvEnterFail Enter.*EnvEnterFail Exit"),
            # We should not run the task
            "DoTask",
            True,
            id="EnterEnvFails",
        ),
        pytest.param(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Test",
                "parameterDefinitions": [{"name": "J", "type": "STRING"}],
                "steps": [
                    {
                        "name": "SimpleStep",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "python",
                                    "args": ["-c", "print('DoTask')"],
                                }
                            }
                        },
                    }
                ],
            },
            [TEST_RUN_ENV_TEMPLATE_FAILS_ENTER, TEST_RUN_ENV_TEMPLATE_1],  # Env Templates
            "SimpleStep",  # step name
            [],  # Task params
            False,  # run_dependencies
            re.compile(r"EnvEnterFail Enter.*EnvEnterFail Exit"),
            # We should not run the second environment
            "Env1 Enter",
            True,
            id="EnterEnvFails_2",
        ),
        pytest.param(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Test",
                "parameterDefinitions": [{"name": "J", "type": "STRING"}],
                "steps": [
                    {
                        "name": "SimpleStep",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "python",
                                    "args": ["-c", "import sys; print('DoTask'); sys.exit(1)"],
                                }
                            }
                        },
                    }
                ],
            },
            [TEST_RUN_ENV_TEMPLATE_1],  # Env Templates
            "SimpleStep",  # step name
            [],  # Task params
            False,  # run_dependencies
            # Task fails; we should still run everything
            re.compile(r"Env1 Enter.*DoTask.*Env1 Exit"),
            "",
            True,
            id="TaskFails",
        ),
        pytest.param(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Test",
                "parameterDefinitions": [{"name": "J", "type": "STRING"}],
                "steps": [
                    {
                        "name": "SimpleStep",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "python",
                                    "args": ["-c", "print('DoTask')"],
                                }
                            }
                        },
                    }
                ],
            },
            [TEST_RUN_ENV_TEMPLATE_FAILS_EXIT],  # Env Templates
            "SimpleStep",  # step name
            [],  # Task params
            False,  # run_dependencies
            re.compile(
                # environment exit fails; we still run everything
                r"EnvExitFail Enter.*DoTask.*EnvExitFail Exit"
            ),
            "",
            True,
            id="EnvExitFails",
        ),
        pytest.param(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "Test",
                "parameterDefinitions": [{"name": "J", "type": "STRING"}],
                "steps": [
                    {
                        "name": "SimpleStep",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "python",
                                    "args": ["-c", "print('DoTask')"],
                                }
                            }
                        },
                    }
                ],
            },
            [TEST_RUN_ENV_TEMPLATE_1, TEST_RUN_ENV_TEMPLATE_FAILS_EXIT],  # Env Templates
            "SimpleStep",  # step name
            [],  # Task params
            False,  # run_dependencies
            re.compile(
                # environment exit fails; we still run everything
                r"Env1 Enter.*EnvExitFail Enter.*DoTask.*EnvExitFail Exit.*Env1 Exit"
            ),
            "",
            True,
            id="EnvExitFails_2",
        ),
        pytest.param(
            {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "TimeoutTest",
                "parameterDefinitions": [{"name": "J", "type": "STRING"}],
                "steps": [
                    {
                        "name": "Timeout",
                        "script": {
                            "actions": {
                                "onRun": {
                                    "command": "python",
                                    "args": [
                                        "-c",
                                        # Obfuscate "EXIT_NORMAL" so it doesn't appear in the log when Windows prints the command that's run to the log.
                                        "import time,sys; print('SLEEP'); sys.stdout.flush(); time.sleep(5); print(chr(69)+'XIT_NORMAL')",
                                    ],
                                    "timeout": 2,
                                }
                            }
                        },
                    }
                ],
            },
            [],  # Env Templates
            "Timeout",  # step name
            [],  # Task params
            False,  # run_dependencies
            re.compile(r"SLEEP"),
            "EXIT_NORMAL",
            True,
            id="TaskTimeout",
        ),
    ],
)
def test_do_run_success(
    job_template: dict[str, Any],
    env_templates: list[dict[str, Any]],
    step_name: str,
    task_params: list[str],
    run_dependencies: bool,
    expected_output: re.Pattern[str],
    expected_not_in_output: str,
    expect_system_exit: bool,
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
            tasks=None,
            maximum_tasks=-1,
            run_dependencies=run_dependencies,
            path_mapping_rules=None,
            environments=environments_files,
            output="human-readable",
            verbose=False,
            preserve=False,
        )

        # WHEN
        try:
            do_run(args)
        except SystemExit:
            assert expect_system_exit
        else:
            assert not expect_system_exit

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


def test_preserve_option(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the 'run' command preserves the session working directory when asked to."""

    files_created: list[Path] = []
    try:
        # GIVEN
        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".template.json", encoding="utf8", delete=False
        ) as job_template_file:
            json.dump(
                {
                    "name": "TestJob",
                    "specificationVersion": "jobtemplate-2023-09",
                    "steps": [
                        {
                            "name": "TestStep",
                            "script": {
                                "actions": {
                                    "onRun": {
                                        "command": "python",
                                        "args": ["-c", "print('Hello World')"],
                                    }
                                }
                            },
                        }
                    ],
                },
                job_template_file.file,
            )
        files_created.append(Path(job_template_file.name))

        args = Namespace(
            path=Path(job_template_file.name),
            step="TestStep",
            job_params=[],
            task_params=None,
            tasks=None,
            maximum_tasks=-1,
            run_dependencies=False,
            path_mapping_rules=None,
            environments=[],
            output="human-readable",
            verbose=False,
            preserve=True,
        )

        # WHEN
        result = do_run(args)

        # THEN
        assert "Working directory preserved at" in result.message
        # Extract the working directory from the output
        match = re.search("Working directory preserved at: (.+)", result.message)
        assert match is not None
        dir = match[1]
        assert Path(dir).exists()
    finally:
        for f in files_created:
            f.unlink()


def test_verbose_option(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that the verbose option has set the log level of the openjd-sessions library to DEBUG."""

    files_created: list[Path] = []
    try:
        # GIVEN
        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".template.json", encoding="utf8", delete=False
        ) as job_template_file:
            json.dump(
                {
                    "name": "TestJob",
                    "specificationVersion": "jobtemplate-2023-09",
                    "steps": [
                        {
                            "name": "TestStep",
                            "script": {
                                "actions": {
                                    "onRun": {
                                        "command": "python",
                                        "args": ["-c", "print('Hello World')"],
                                    }
                                }
                            },
                        }
                    ],
                },
                job_template_file.file,
            )
        files_created.append(Path(job_template_file.name))

        args = Namespace(
            path=Path(job_template_file.name),
            step="TestStep",
            job_params=[],
            task_params=None,
            tasks=None,
            maximum_tasks=-1,
            run_dependencies=False,
            path_mapping_rules=None,
            environments=[],
            output="human-readable",
            verbose=True,
            preserve=False,
        )

        # WHEN
        do_run(args)

        # THEN
        assert SessionsLogger.isEnabledFor(logging.DEBUG)

        # Reset the state to not interfere with other tests.
        SessionsLogger.setLevel(logging.INFO)
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
        verbose=False,
        preserve=False,
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
                    "actions": {
                        "onRun": {
                            "command": "python",
                            "args": ["-c", "print('Mapped:{{Param.TestPath}}')"],
                        }
                    }
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
            tasks=None,
            run_dependencies=False,
            output="human-readable",
            path_mapping_rules="file://" + temp_rules.name,
            environments=[],
            maximum_tasks=1,
            verbose=False,
            preserve=False,
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
            assert any(r"Mapped:\mnt\test" in m for m in caplog.messages)
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
        tasks=None,
        maximum_tasks=-1,
        run_dependencies=False,
        path_mapping_rules=None,
        environments=[],
        output="human-readable",
        verbose=False,
        preserve=False,
    )
    with pytest.raises(SystemExit):
        do_run(mock_args)
    assert (
        "No Step with name 'FakeStep' is defined in the given Job Template."
        in capsys.readouterr().out
    )

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
    with (
        patch.object(
            LocalSession, "initialize", autospec=True, side_effect=LocalSession.initialize
        ) as patched_initialize,
        patch.object(
            Session, "__init__", autospec=True, side_effect=Session.__init__
        ) as patched_session_init,
    ):
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


class TestProcessTaskParams:
    """Testing that we properly handle the values of the --task-param/-tp
    command-line argument"""

    @pytest.mark.parametrize(
        "given, expected",
        [
            pytest.param(["Foo=1"], {"Foo": "1"}, id="simple single"),
            pytest.param(["Foo=One=Two"], {"Foo": "One=Two"}, id="value containing an = sign"),
            pytest.param([" Foo=1 "], {"Foo": "1 "}, id="bracketting whitespace"),
            pytest.param(["Foo = 1"], {"Foo ": " 1"}, id="internal whitespace"),
            pytest.param(
                ["Foo=1", "Bar=Buz"], {"Foo": "1", "Bar": "Buz"}, id="multiple parameters"
            ),
        ],
    )
    def test_success(self, given: list[str], expected: dict[str, str]) -> None:
        # WHEN
        result = _process_task_params(given)

        # THEN
        assert result == expected

    @pytest.mark.parametrize(
        "given, expected_error",
        [
            pytest.param(
                ["Foo1"], "Task parameter 'Foo1' defined incorrectly.", id="regex mismatch"
            ),
            pytest.param(
                ["Foo=1", "Foo=2"],
                "Task parameter 'Foo' has been defined more than once.",
                id="duplicate definition",
            ),
        ],
    )
    def test_error(self, given: list[str], expected_error: str) -> None:
        # WHEN
        with pytest.raises(RuntimeError, match=expected_error):
            _process_task_params(given)


class TestProcessTasks:
    """Testing that we properly handle the value of the --tasks command-line argument."""

    @pytest.mark.parametrize(
        "given, file_contents, expected",
        [
            pytest.param(
                "file://TEMPDIR/some-file.json",
                '[{"Param1": "A", "Param2": 1}]',
                [{"Param1": "A", "Param2": "1"}],
                id="json file; one task",
            ),
            pytest.param(
                "file://TEMPDIR/some-file.yaml",
                '- Param1: "A"\n  Param2: 1\n',
                [{"Param1": "A", "Param2": "1"}],
                id="yaml file",
            ),
            pytest.param(
                "file://TEMPDIR/some-file.json",
                '[{"Param1": "A", "Param2": 1},{"Param1": "B", "Param2": 2}]',
                [{"Param1": "A", "Param2": "1"}, {"Param1": "B", "Param2": "2"}],
                id="json file; two tasks",
            ),
            pytest.param(
                '[{"Param1": "A", "Param2": 1}]',
                None,
                [{"Param1": "A", "Param2": "1"}],
                id="inline json; one task",
            ),
            pytest.param(
                '[{"Param1": "A", "Param2": 1},{"Param1": "B", "Param2": 2}]',
                None,
                [{"Param1": "A", "Param2": "1"}, {"Param1": "B", "Param2": "2"}],
                id="inline json; two tasks",
            ),
            pytest.param('[{"Param": "A"}]', None, [{"Param": "A"}], id="param value str->str"),
            pytest.param('[{"Param": 12}]', None, [{"Param": "12"}], id="param value int->str"),
            pytest.param(
                '[{"Param": 12.2}]', None, [{"Param": "12.2"}], id="param value float->str"
            ),
        ],
    )
    def test_success(
        self, given: str, file_contents: Optional[str], expected: dict[str, str]
    ) -> None:
        # GIVEN
        with tempfile.TemporaryDirectory() as temp_dir:
            if given.startswith("file://TEMPDIR"):
                assert file_contents is not None
                filename = os.path.join(temp_dir, given.removeprefix("file://TEMPDIR/"))
                with open(filename, "w") as param_file:
                    param_file.write(file_contents)
                given = "file://" + filename

            # WHEN
            result = _process_tasks(given)

            # THEN
            assert result == expected

    @pytest.mark.parametrize(
        "given, file_contents, expected_error",
        [
            pytest.param(
                "file://TEMPDIR/some-file.json",
                "}not json",
                "Parameter file.+is formatted incorrectly",
                id="not json",
            ),
            pytest.param(
                "file://TEMPDIR/some-file.yaml",
                "}not yaml",
                "Parameter file.+is formatted incorrectly",
                id="not yaml",
            ),
            pytest.param(
                '{"Param": "A"}',
                None,
                "argument must be a list of maps from string to string when decoded",
                id="not a list",
            ),
            pytest.param(
                "[1,2,3]",
                None,
                "argument must be a list of maps from string to string when decoded",
                id="not a list of dicts",
            ),
            pytest.param(
                '[{"Param": [1,2]}]',
                None,
                "argument must be a list of maps from string to string when decoded",
                id="value not scalar",
            ),
        ],
    )
    def test_error(self, given: str, file_contents: Optional[str], expected_error: str) -> None:
        # GIVEN
        with tempfile.TemporaryDirectory() as temp_dir:
            if given.startswith("file://TEMPDIR"):
                assert file_contents is not None
                filename = os.path.join(temp_dir, given.removeprefix("file://TEMPDIR/"))
                with open(filename, "w") as param_file:
                    param_file.write(file_contents)
                given = "file://" + filename

            with pytest.raises(RuntimeError, match=expected_error):
                _process_tasks(given)


class TestValidateTaskParams:

    @pytest.mark.parametrize(
        "given",
        [
            pytest.param([{"Foo": "1", "Bar": "Bar1"}], id="one task, all params defined"),
            pytest.param(
                [{"Foo": "1", "Bar": "Bar1"}, {"Foo": "1", "Bar": "Bar1"}], id="two tasks"
            ),
        ],
    )
    def test_success(self, given: list[dict[str, str]]) -> None:
        # GIVEN
        job_template = decode_job_template(template=TEST_RUN_JOB_TEMPLATE_BASIC)
        job = create_job(
            job_template=job_template,
            job_parameter_values={
                "J": ParameterValue(type=ParameterValueType.STRING, value="Jvalue")
            },
        )
        step = job.steps[0]

        # THEN
        # Does not raise
        _validate_task_params(step, given)

    @pytest.mark.parametrize(
        "given, expected_error",
        [
            pytest.param(
                [{"Bar": "Bar1"}], "Task 0 is missing values for parameters: Foo", id="missing Foo"
            ),
            pytest.param(
                [{"Bar": "Bar1"}, {"Foo": "1"}],
                "Task 0 is missing values for parameters: Foo.*\n.*Task 1 is missing values for parameters: Bar",
                id="missing Foo & Bar; separate tasks",
            ),
            pytest.param(
                [{"Foo": "1", "Bar": "Bar1", "Baz": "wut"}],
                "Task 0 defines unknown parameters: Baz",
                id="extra parameter",
            ),
            pytest.param(
                [{"Bar": "Bar1", "Baz": "wut"}],
                "Task 0 defines unknown parameters: Baz.*\n.*Task 0 is missing values for parameters: Foo",
                id="missing & extra parameter",
            ),
        ],
    )
    def test_errors(self, given: list[dict[str, str]], expected_error: str) -> None:
        # GIVEN
        job_template = decode_job_template(template=TEST_RUN_JOB_TEMPLATE_BASIC)
        job = create_job(
            job_template=job_template,
            job_parameter_values={
                "J": ParameterValue(type=ParameterValueType.STRING, value="Jvalue")
            },
        )
        step = job.steps[0]

        # THEN
        with pytest.raises(RuntimeError, match=expected_error):
            _validate_task_params(step, given)
