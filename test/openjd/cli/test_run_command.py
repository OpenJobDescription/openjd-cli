# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
import json
from pathlib import Path, PureWindowsPath, PurePosixPath
import tempfile

import pytest
from unittest.mock import ANY, Mock, patch

from . import MOCK_TEMPLATE, SampleSteps
from openjd.cli._run import _run_command
from openjd.cli._run._run_command import (
    OpenJDRunResult,
    do_run,
    _run_local_session,
)
from openjd.cli._run._local_session._session_manager import LocalSession
from openjd.model import Job
from openjd.sessions import PathMappingRule, PathMappingOS, Session


@pytest.mark.parametrize(
    "step_name,task_params,should_run_dependencies",
    [
        pytest.param("BareStep", [], False, id="Basic step"),
        pytest.param("NormalStep", [], False, id="Step with extra environments"),
        pytest.param("DependentStep", [], False, id="Exclude dependencies"),
        pytest.param("DependentStep", [], True, id="Include dependencies"),
        pytest.param("TaskParamStep", [], False, id="Step with Task parameters"),
        pytest.param(
            "TaskParamStep",
            [["TaskNumber=1 TaskMessage=Hello!"]],
            False,
            id="Custom Task parameters",
        ),
        pytest.param(
            "TaskParamStep",
            [['TaskNumber=1 TaskMessage="Hello, world!"']],
            False,
            id="Custom Task parameters with commas",
        ),
    ],
)
def test_do_run_success(
    step_name: str,
    task_params: list[str],
    should_run_dependencies: bool,
):
    """
    Test that the `run` command succeeds with various argument options.
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=".template.json", encoding="utf8", delete=False
    ) as temp_template:
        json.dump(MOCK_TEMPLATE, temp_template.file)

    mock_args = Namespace(
        path=Path(temp_template.name),
        step=step_name,
        job_params=None,
        task_params=task_params,
        maximum_tasks=-1,
        run_dependencies=should_run_dependencies,
        path_mapping_rules=None,
        output="human-readable",
    )
    do_run(mock_args)

    Path(temp_template.name).unlink()


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
        output="human-readable",
    )
    with pytest.raises(SystemExit):
        do_run(mock_args)


def test_do_run_path_mapping_rules():
    """
    Test that the `run` command exits on any error (e.g., a non-existent template file).
    """
    path_mapping_rules = [
        PathMappingRule(
            source_os=PathMappingOS.WINDOWS,
            source_path=PureWindowsPath(r"C:\test"),
            destination_path=PurePosixPath("/mnt/test"),
        )
    ]

    try:
        # Set up a rules file and a job template file
        temp_rules = temp_template = None
        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".rules.json", encoding="utf8", delete=False
        ) as temp_rules:
            json.dump([rule.to_dict() for rule in path_mapping_rules], temp_rules.file)

        with tempfile.NamedTemporaryFile(
            mode="w+t", suffix=".template.json", encoding="utf8", delete=False
        ) as temp_template:
            json.dump(MOCK_TEMPLATE, temp_template.file)

        # Patch out _run_local_session so we can check how it gets called
        with patch.object(_run_command, "_run_local_session") as mock_run_local_session:
            # Call the CLI run command, using the temp files we created
            mock_args = Namespace(
                path=Path(temp_template.name),
                step="NormalStep",
                job_params=None,
                task_params=None,
                run_dependencies=False,
                output="human-readable",
                path_mapping_rules="file://" + temp_rules.name,
                maximum_tasks=1,
            )
            do_run(mock_args)

            # Confirm _run_local_session gets called with the correct path mapping rules
            mock_run_local_session.assert_called_once_with(
                job=ANY,
                step=ANY,
                step_map=ANY,
                maximum_tasks=1,
                task_parameter_values=ANY,
                path_mapping_rules=path_mapping_rules,
                should_run_dependencies=False,
                should_print_logs=True,
            )
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
        output="human-readable",
    )
    with pytest.raises(SystemExit):
        do_run(mock_args)
    assert "Step 'FakeStep' does not exist" in capsys.readouterr().out

    Path(temp_template.name).unlink()


@pytest.mark.usefixtures("sample_job", "sample_step_map", "patched_session_cleanup", "capsys")
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
    sample_job: Job,
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
    path_mapping_rules = [
        PathMappingRule(
            source_os=PathMappingOS.WINDOWS,
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


@pytest.mark.usefixtures("sample_job", "sample_step_map")
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
    sample_job: Job,
    sample_step_map: dict,
    step_index: int,
    should_run_dependencies: bool,
    expected_error: str,
):
    """
    Test the output of a Session that finishes after encountering errors.
    """
    response = _run_local_session(
        job=sample_job,
        step_map=sample_step_map,
        step=sample_job.steps[step_index],
        path_mapping_rules=[],
        should_run_dependencies=should_run_dependencies,
    )

    assert response.status == "error"
    assert expected_error in response.message
