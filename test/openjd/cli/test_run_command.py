# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import tempfile
import re
import os
from typing import Optional
import logging
import shlex

import pytest
from unittest.mock import Mock

from . import MOCK_TEMPLATE, SampleSteps, run_openjd_cli_main, format_capsys_outerr

from openjd.cli._run._run_command import (
    do_run,
    _process_task_params,
    _process_tasks,
)
from openjd.cli._run._local_session._session_manager import LoggingTimestampFormat
from openjd.sessions import LOG as SessionsLogger, PathMappingRule, PathFormat


PARAMETRIZE_CASES: tuple = (
    pytest.param(
        "basic.yaml",
        [],  # Env Templates
        "First",  # step name
        [],  # Task params
        True,  # run_dependencies
        re.compile(
            r"J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*FirstS Exit.*J2 Exit.*J1 Exit"
        ),
        "",
        0,
        id="RunFirstStep",
    ),
    pytest.param(
        "basic.yaml",
        [],  # Env Templates
        "First",  # step name
        ["-tp", "Foo=1", "-tp", "Bar=Bar1"],  # Task params
        True,  # run_dependencies
        re.compile(
            r"J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*FirstS Exit.*J2 Exit.*J1 Exit"
        ),
        "Foo=1. Bar=Bar2",
        0,
        id="RunSelectTask",
    ),
    pytest.param(
        "basic_dependency_job.yaml",
        [],  # Env Templates
        "Second",  # step name
        [],  # Task params
        True,  # run_dependencies
        re.compile(
            r"J1 Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*J=Jvalue Fuz=1.*J=Jvalue Fuz=2.*J1 Exit"
        ),
        "",
        0,
        id="RunSecondStepWithDep",
    ),
    pytest.param(
        "basic_dependency_job.yaml",
        [],  # Env Templates
        "Second",  # step name
        [],  # Task params
        False,  # run_dependencies
        re.compile(r"J1 Enter.*J=Jvalue Fuz=1.*J=Jvalue Fuz=2.*J1 Exit"),
        "Foo=1. Bar=Bar1",
        0,
        id="RunSecondStepNoDep",
    ),
    pytest.param(
        "basic.yaml",
        ["env_1.yaml"],  # Env Templates
        "First",  # step name
        [],  # Task params
        True,  # run_dependencies
        re.compile(
            r"Env1 Enter.*J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*FirstS Exit.*J2 Exit.*J1 Exit.*Env1 Exit"
        ),
        "",
        0,
        id="WithOneEnv",
    ),
    pytest.param(
        "basic.yaml",
        ["env_1.yaml", "env_2.yaml"],  # Env Templates
        "First",  # step name
        [],  # Task params
        True,  # run_dependencies
        re.compile(
            r"Env1 Enter.*Env2 Enter.*J1 Enter.*J2 Enter.*FirstS Enter.*J=Jvalue.*Foo=1. Bar=Bar1.*Foo=1. Bar=Bar2.*FirstS Exit.*J2 Exit.*J1 Exit.*Env2 Exit.*Env1 Exit"
        ),
        "",
        0,
        id="WithTwoEnvs",
    ),
    pytest.param(
        "simple_with_j_param.yaml",
        ["env_fails_enter.yaml"],  # Env Templates
        "SimpleStep",  # step name
        [],  # Task params
        False,  # run_dependencies
        re.compile(r"EnvEnterFail Enter.*EnvEnterFail Exit"),
        # We should not run the task
        "DoTask",
        1,
        id="EnterEnvFails",
    ),
    pytest.param(
        "simple_with_j_param.yaml",
        ["env_fails_enter.yaml", "env_1.yaml"],  # Env Templates
        "SimpleStep",  # step name
        [],  # Task params
        False,  # run_dependencies
        re.compile(r"EnvEnterFail Enter.*EnvEnterFail Exit"),
        # We should not run the second environment
        "Env1 Enter",
        1,
        id="EnterEnvFails_2",
    ),
    pytest.param(
        "simple_with_j_param_exit_1.yaml",
        ["env_1.yaml"],  # Env Templates
        "SimpleStep",  # step name
        [],  # Task params
        False,  # run_dependencies
        # Task fails; we should still run everything
        re.compile(r"Env1 Enter.*DoTask.*Env1 Exit"),
        "",
        1,
        id="TaskFails",
    ),
    pytest.param(
        "simple_with_j_param.yaml",
        ["env_fails_exit.yaml"],  # Env Templates
        "SimpleStep",  # step name
        [],  # Task params
        False,  # run_dependencies
        re.compile(
            # environment exit fails; we still run everything
            r"EnvExitFail Enter.*DoTask.*EnvExitFail Exit"
        ),
        "",
        1,
        id="EnvExitFails",
    ),
    pytest.param(
        "simple_with_j_param.yaml",
        ["env_1.yaml", "env_fails_exit.yaml"],  # Env Templates
        "SimpleStep",  # step name
        [],  # Task params
        False,  # run_dependencies
        re.compile(
            # environment exit fails; we still run everything
            r"Env1 Enter.*EnvExitFail Enter.*DoTask.*EnvExitFail Exit.*Env1 Exit"
        ),
        "",
        1,
        id="EnvExitFails_2",
    ),
    pytest.param(
        "job_sleep_exit_normal.yaml",
        [],  # Env Templates
        "Timeout",  # step name
        [],  # Task params
        False,  # run_dependencies
        re.compile(r"SLEEP"),
        "EXIT_NORMAL",
        1,
        id="TaskTimeout",
    ),
)


@pytest.mark.parametrize(
    "job_template_file,env_template_files,step_name,task_params,run_dependencies,expected_output_regex,expected_not_in_output,expected_exit_code",
    PARAMETRIZE_CASES,
)
def test_do_run_success(
    job_template_file: str,
    env_template_files: list[str],
    step_name: str,
    task_params: list[str],
    run_dependencies: bool,
    expected_output_regex: re.Pattern[str],
    expected_not_in_output: str,
    expected_exit_code: int,
    capsys: pytest.CaptureFixture,
) -> None:
    """Test that the 'run' command correctly runs templates and obtains the expected results."""

    template_dir = Path(__file__).parent / "templates"

    extra_options = []
    if run_dependencies:
        extra_options.append("--run-dependencies")
    if env_template_files:
        extra_options.extend(
            [
                entry
                for file in env_template_files
                for entry in ["--environment", str(template_dir / file)]
            ]
        )

    args = [
        "run",
        str(template_dir / job_template_file),
        "--step",
        step_name,
        "-p",
        "J=Jvalue",
        *task_params,
        *extra_options,
        "--extensions",
        "",
    ]

    print(f"openjd {shlex.join(args)}")

    outerr = run_openjd_cli_main(capsys, args=args, expected_exit_code=expected_exit_code)

    expected_was_found = expected_output_regex.search(outerr.out.replace("\n", "\\n"), re.MULTILINE)
    if expected_was_found is None:
        # Print out the environment and job templates for easier error debugging from the log outputs
        print("\n ENV TEMPLATES:\n")
        print(json.dumps(env_template_files, indent=1))
        print("\n JOB TEMPLATE:\n")
        print(json.dumps(job_template_file, indent=1))
    assert (
        expected_was_found
    ), f"Regex r'{expected_output_regex.pattern}' does not match the output:\n{format_capsys_outerr(outerr)}"
    if expected_not_in_output:
        assert expected_not_in_output not in outerr.out


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
            timestamp_format=LoggingTimestampFormat.RELATIVE,
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
            extensions="",
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
            timestamp_format=LoggingTimestampFormat.RELATIVE,
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
            extensions="",
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
        timestamp_format=LoggingTimestampFormat.RELATIVE,
        job_params=None,
        task_params=None,
        run_dependencies=False,
        path_mapping_rules=None,
        environments=[],
        output="human-readable",
        verbose=False,
        preserve=False,
        extensions="",
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
                timestamp_format=LoggingTimestampFormat.RELATIVE,
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
                extensions="",
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
    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=".template.json", encoding="utf8", delete=False
    ) as temp_template:
        json.dump(MOCK_TEMPLATE, temp_template.file)

        mock_args = Namespace(
            path=Path(temp_template.name),
            step="FakeStep",
            timestamp_format=LoggingTimestampFormat.RELATIVE,
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
            extensions="",
        )
    with pytest.raises(SystemExit):
        do_run(mock_args)
    assert (
        "No Step with name 'FakeStep' is defined in the given Job Template."
        in capsys.readouterr().out
    )

    Path(temp_template.name).unlink()


PARAMETRIZE_CASES = (
    pytest.param(SampleSteps.BareStep, [], [], id="Bare Step without --run-dependencies"),
    pytest.param(
        SampleSteps.BareStep, [], ["--run-dependencies"], id="Bare Step with --run-dependencies"
    ),
    pytest.param(
        SampleSteps.BareStep,
        [],
        ["--run-dependencies"],
        id="--run-dependencies with no dependencies",
    ),
    pytest.param(SampleSteps.TaskParamStep, [], ["--run-dependencies"], id="Task param Step"),
    pytest.param(SampleSteps.NormalStep, [], ["--run-dependencies"], id="Catch-all Step"),
    pytest.param(
        SampleSteps.NormalStep,
        [],
        ["--run-dependencies"],
        id="--run-dependencies with Step environment but no dependencies",
    ),
    pytest.param(
        SampleSteps.DependentStep,
        [SampleSteps.BareStep],
        ["--run-dependencies"],
        id="Step with direct dependency",
    ),
    pytest.param(
        SampleSteps.ExtraDependentStep,
        [
            SampleSteps.BareStep,
            SampleSteps.DependentStep,
            SampleSteps.TaskParamStep,
        ],
        ["--run-dependencies"],
        id="Step with transitive and direct dependencies",
    ),
    pytest.param(SampleSteps.DependentStep, [], [], id="Exclude dependencies implicitly"),
    pytest.param(
        SampleSteps.DependentStep,
        [],
        ["--no-run-dependencies"],
        id="Exclude dependencies with explicit option",
    ),
    pytest.param(
        SampleSteps.StepDepHasStepEnv,
        [SampleSteps.NormalStep],
        ["--run-dependencies"],
        id="Step with a dependency that has step envs",
    ),
)


@pytest.mark.parametrize(
    "step_index,dependency_indexes,extra_options",
    PARAMETRIZE_CASES,
)
@pytest.mark.usefixtures(
    "sample_job_and_dirs", "sample_step_map", "patched_session_cleanup", "capsys"
)
def test_run_local_session_success(
    sample_step_map: dict,
    patched_session_cleanup: Mock,
    capsys: pytest.CaptureFixture,
    step_index: SampleSteps,
    dependency_indexes: list[SampleSteps],
    extra_options: list[str],
):
    """
    Test that various Job structures can successfully run local Sessions.

    Note that we don't need to test with custom Task parameters, as those are
    tested within the `LocalSession` object.
    """

    template_dir = Path(__file__).parent / "templates"
    path_mapping_rules = [
        PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath(r"C:\test"),
            destination_path=PurePosixPath("/mnt/test"),
        ).to_dict()
    ]
    args = [
        "run",
        str(template_dir / "job_with_test_steps.yaml"),
        "--step",
        step_index.name,
        "--extensions",
        "",
        *extra_options,
        "--path-mapping-rules",
        json.dumps({"version": "pathmapping-1.0", "path_mapping_rules": path_mapping_rules}),
    ]
    print(f"openjd {shlex.join(args)}")

    outerr = run_openjd_cli_main(capsys, args=args, expected_exit_code=0)

    for expected_output_regex in [
        "Running job 'my-job'",
        *(f"Running step '{dep_index.name}'" for dep_index in dependency_indexes),
        f"Running step '{step_index.name}'",
        "All actions completed successfully!",
    ]:
        assert re.search(
            expected_output_regex, outerr.out, re.MULTILINE
        ), f"Regex r'{expected_output_regex}' does not match the output:\n{format_capsys_outerr(outerr)}"


@pytest.mark.parametrize(
    "step_index,expected_error_regex",
    [
        pytest.param(
            SampleSteps.BadCommand, "Session ended with errors", id="Badly-formed command"
        ),
    ],
)
def test_run_local_session_failed(
    capsys,
    step_index: SampleSteps,
    expected_error_regex: str,
):
    """
    Test the output of a Session that finishes after encountering errors.
    """
    template_dir = Path(__file__).parent / "templates"
    path_mapping_rules = [
        PathMappingRule(
            source_path_format=PathFormat.WINDOWS,
            source_path=PureWindowsPath(r"C:\test"),
            destination_path=PurePosixPath("/mnt/test"),
        ).to_dict()
    ]
    args = [
        "run",
        str(template_dir / "job_with_test_steps.yaml"),
        "--step",
        step_index.name,
        "--extensions",
        "",
        "--path-mapping-rules",
        json.dumps({"version": "pathmapping-1.0", "path_mapping_rules": path_mapping_rules}),
    ]
    print(f"openjd {shlex.join(args)}")

    outerr = run_openjd_cli_main(capsys, args=args, expected_exit_code=1)

    assert re.search(
        expected_error_regex, outerr.out, re.MULTILINE
    ), f"Regex r'{expected_error_regex}' does not match the output:\n{format_capsys_outerr(outerr)}"


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


@pytest.mark.parametrize(
    "task_params",
    [
        pytest.param(
            ["--tasks", '[{"Foo": "1", "Bar": "Bar1"}]'], id="one task, all params defined"
        ),
        pytest.param(
            ["--tasks", '[{"Foo": "1", "Bar": "Bar1"}, {"Foo": "1", "Bar": "Bar1"}]'],
            id="two tasks",
        ),
    ],
)
def test_task_param_validation_success(capsys, task_params: list[str]) -> None:
    template_dir = Path(__file__).parent / "templates"

    args = [
        "run",
        str(template_dir / "basic.yaml"),
        "-p",
        "J=Jvalue",
        *task_params,
        "--extensions",
        "",
    ]

    print(f"openjd {shlex.join(args)}")

    # Ensure it runs with success exit code
    run_openjd_cli_main(capsys, args=args, expected_exit_code=0)


@pytest.mark.parametrize(
    "task_params, expected_error_list",
    [
        pytest.param(
            ["-tp", "Bar=Bar1"], ["Task 0 is missing values for parameters: Foo"], id="missing Foo"
        ),
        pytest.param(
            ["--tasks", '[{"Bar":"Bar1"}, {"Foo":"1"}]'],
            [
                "Task 0 is missing values for parameters: Foo",
                "Task 1 is missing values for parameters: Bar",
            ],
            id="missing Foo & Bar; separate tasks",
        ),
        pytest.param(
            ["-tp", "Foo=1", "-tp", "Bar=Bar1", "-tp", "Baz=wut"],
            ["Task 0 defines unknown parameters: Baz"],
            id="extra parameter",
        ),
        pytest.param(
            ["-tp", "Bar=Bar1", "-tp", "Baz=wut"],
            [
                "Task 0 defines unknown parameters: Baz",
                "Task 0 is missing values for parameters: Foo",
            ],
            id="missing & extra parameter",
        ),
    ],
)
def test_task_param_validation_errors(
    capsys, task_params: list[str], expected_error_list: list[str]
) -> None:
    template_dir = Path(__file__).parent / "templates"

    args = [
        "run",
        str(template_dir / "basic.yaml"),
        "-p",
        "J=Jvalue",
        *task_params,
        "--extensions",
        "",
    ]

    print(f"openjd {shlex.join(args)}")

    outerr = run_openjd_cli_main(capsys, args=args, expected_exit_code=1)

    for expected_error in expected_error_list:
        assert (
            expected_error in outerr.out
        ), f"Message r'{expected_error}' was not found in the output:\n{format_capsys_outerr(outerr)}"
