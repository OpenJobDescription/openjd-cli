# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from unittest.mock import call, patch
import signal

from . import SampleSteps, SESSION_PARAMETERS
from openjd.sessions import Session, SessionState
from openjd.cli._run._local_session._session_manager import LocalSession
import openjd.cli._run._local_session._session_manager as local_session_mod


@pytest.fixture(scope="function", autouse=True)
def patched_actions():
    """
    Patch the `Session` actions to keep track of how many times
    they're called, but set their side effects to the original method
    so it has the same functionality.

    We also patch the action callback to make sure it's being called.

    (This is because the subprocesses in Sessions causes tests to
    hang when mocking actions directly, so we just run the Session
    to completion with short sample Jobs)
    """
    with (
        patch.object(
            Session, "enter_environment", autospec=True, side_effect=Session.enter_environment
        ) as patched_enter,
        patch.object(
            Session, "run_task", autospec=True, side_effect=Session.run_task
        ) as patched_run,
        patch.object(
            Session, "exit_environment", autospec=True, side_effect=Session.exit_environment
        ) as patched_exit,
        patch.object(
            LocalSession,
            "_action_callback",
            autospec=True,
            side_effect=LocalSession._action_callback,
        ) as patched_callback,
    ):
        yield patched_enter, patched_run, patched_exit, patched_callback


@pytest.mark.usefixtures("sample_job_and_dirs")
@pytest.mark.parametrize(
    "given_parameters,expected_parameters",
    [
        pytest.param(
            {"TaskNumber": 5, "TaskMessage": "Hello!"},
            {"TaskNumber": "5", "TaskMessage": "Hello!"},
            id="All parameters provided",
        ),
        pytest.param(
            {"TaskMessage": "Hello!"},
            {"TaskNumber": "1", "TaskMessage": "Hello!"},
            id="Some parameters provided",
        ),
        pytest.param(
            {"FakeParameter": "Hello!", "TaskNumber": 5},
            {"TaskNumber": "5", "TaskMessage": "Hi!"},
            id="Unused parameter name",
        ),
        pytest.param(
            {"FakeInt": 5, "FakeStr": "Hello!"},
            {"TaskNumber": "1", "TaskMessage": "Hi!"},
            id="Only unused parameter names",
        ),
    ],
)
def test_generate_task_parameter_set(
    sample_job_and_dirs: tuple, given_parameters: dict, expected_parameters: dict
):
    """
    Test that a LocalSession can generate Task parameters given valid user input.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    with LocalSession(job=sample_job, session_id="my-session") as session:
        # Convince the type checker that `parameterSpace` exists
        param_space = sample_job.steps[SampleSteps.TaskParamStep].parameterSpace
        if param_space:
            parameter_set = session._generate_task_parameter_set(
                parameter_space=param_space,
                parameter_values=given_parameters,
            )

            assert all(
                [param.value == expected_parameters[name] for name, param in parameter_set.items()]
            )


@pytest.mark.usefixtures("sample_job_and_dirs")
@pytest.mark.parametrize(*SESSION_PARAMETERS)
def test_localsession_initialize(
    sample_job_and_dirs: tuple,
    dependency_indexes: list[int],
    step_index: int,
    maximum_tasks: int,
    parameter_sets: list[dict],
    num_expected_environments: int,
    num_expected_tasks: int,
):
    """
    Test that initializing the local Session clears the `ended` flag, only generates Task parameters
    when necessary, and adds to the Action queue appropriately.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    with LocalSession(job=sample_job, session_id="my-session") as session:
        with patch.object(
            LocalSession,
            "_generate_task_parameter_set",
            autospec=True,
            side_effect=LocalSession._generate_task_parameter_set,
        ) as patched_generate_params:
            session.initialize(
                dependencies=[sample_job.steps[i] for i in dependency_indexes],
                step=sample_job.steps[step_index],
                maximum_tasks=maximum_tasks,
                task_parameter_values=parameter_sets,
            )

        if parameter_sets and sample_job.steps[step_index].parameterSpace:
            patched_generate_params.assert_called()
        else:
            patched_generate_params.assert_not_called()

        assert not session.ended.is_set()
        assert session._enter_env_queue.qsize() == num_expected_environments
        assert session._action_queue.qsize() == num_expected_tasks


@pytest.mark.usefixtures("sample_job_and_dirs")
def test_localsession_traps_sigint(sample_job_and_dirs: tuple):
    # Make sure that we hook up, and remove the signal handler when using the local session
    sample_job, template_dir, current_working_dir = sample_job_and_dirs

    # GIVEN
    with patch.object(local_session_mod, "signal") as signal_mod:
        # WHEN
        with LocalSession(job=sample_job, session_id="test-id") as localsession:
            pass

    # THEN
    assert signal_mod.call_count == 4
    signal_mod.assert_has_calls(
        [
            call(signal.SIGINT, localsession._sigint_handler),
            call(signal.SIGTERM, localsession._sigint_handler),
            call(signal.SIGINT, signal.SIG_DFL),
            call(signal.SIGTERM, signal.SIG_DFL),
        ]
    )


@pytest.mark.usefixtures("sample_job_and_dirs", "capsys")
@pytest.mark.parametrize(*SESSION_PARAMETERS)
def test_localsession_run_success(
    sample_job_and_dirs: tuple,
    capsys: pytest.CaptureFixture,
    dependency_indexes: list[int],
    step_index: int,
    maximum_tasks: int,
    parameter_sets: list[dict],
    num_expected_environments: int,
    num_expected_tasks: int,
):
    """
    Test that calling `run` causes the local Session to
    iterate through the actions defined in the Job.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    with LocalSession(job=sample_job, session_id="my-session") as session:
        session.initialize(
            dependencies=[sample_job.steps[i] for i in dependency_indexes],
            step=sample_job.steps[step_index],
            maximum_tasks=maximum_tasks,
            task_parameter_values=parameter_sets,
        )

        session.run()
        session.ended.wait()

    assert session.tasks_run == num_expected_tasks  # type: ignore
    assert session.get_duration() > 0  # type: ignore
    assert session._inner_session.enter_environment.call_count == num_expected_environments  # type: ignore
    assert session._inner_session.run_task.call_count == num_expected_tasks  # type: ignore
    assert session._inner_session.exit_environment.call_count == num_expected_environments  # type: ignore
    session._action_callback.assert_called()  # type: ignore
    assert session._cleanup_called
    assert (
        "Open Job Description CLI: All actions completed successfully!" in capsys.readouterr().out
    )


@pytest.mark.usefixtures("sample_job_and_dirs")
def test_localsession_run_not_ready(sample_job_and_dirs: tuple):
    """
    Test that a LocalSession throws an error when it is not in the "READY" state.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    with LocalSession(job=sample_job, session_id="my-session") as session:
        with (
            patch.object(Session, "state", new=SessionState.ENDED),
            pytest.raises(RuntimeError) as rte,
        ):
            session.run()

    assert "not in a READY state" in str(rte.value)


@pytest.mark.usefixtures("sample_job_and_dirs", "capsys")
def test_localsession_run_failed(sample_job_and_dirs: tuple, capsys: pytest.CaptureFixture):
    """
    Test that a LocalSession can gracefully handle an error in its inner Session.
    """
    sample_job, template_dir, current_working_dir = sample_job_and_dirs
    with LocalSession(job=sample_job, session_id="bad-session") as session:
        session.initialize(dependencies=[], step=sample_job.steps[SampleSteps.BadCommand])
        session.run()
        session.ended.wait()

    # The Task has failed. That means that we've entered the one environment and also exited it.
    session._inner_session.enter_environment.assert_called_once()  # type: ignore
    session._inner_session.exit_environment.assert_called_once()  # type: ignore
    assert session.failed
    assert session._cleanup_called
    assert "Open Job Description CLI: ERROR" in capsys.readouterr().out
