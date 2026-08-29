# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from unittest.mock import call, patch
import signal

from . import SampleSteps, SESSION_PARAMETERS
from openjd.model import StepParameterSpaceIterator
from openjd.sessions import Session, SessionState
from openjd.cli._run._local_session._session_manager import (
    LocalSession,
    EnvironmentType,
    LocalSessionFailed,
)
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
@pytest.mark.parametrize(*SESSION_PARAMETERS)
def test_localsession_initialize(
    sample_job_and_dirs: tuple,
    step_index: int,
    maximum_tasks: int,
    parameter_sets: list[dict],
    num_expected_tasks: int,
):
    """
    Test that initializing the local Session enters external and job environments, and is ready to run tasks.
    """
    sample_job, sample_job_parameters, template_dir, current_working_dir = sample_job_and_dirs
    with (
        patch.object(
            LocalSession,
            "run_environment_enters",
            autospec=True,
            side_effect=LocalSession.run_environment_enters,
        ) as patched_run_environment_enters,
        patch.object(
            LocalSession, "run_step", autospec=True, side_effect=LocalSession.run_step
        ) as patched_run_step,
    ):
        with LocalSession(
            job=sample_job, job_parameter_values=sample_job_parameters, session_id="my-session"
        ) as session:
            assert session._openjd_session.state == SessionState.READY

            # It should have entered the external and job environments in order
            assert patched_run_environment_enters.call_count == 2
            assert patched_run_environment_enters.call_args_list[0] == call(
                session, None, EnvironmentType.EXTERNAL
            )
            assert patched_run_environment_enters.call_args_list[1] == call(
                session, sample_job.jobEnvironments, EnvironmentType.JOB
            )

            # It should not have run any steps
            assert patched_run_step.call_count == 0


@pytest.mark.usefixtures("sample_job_and_dirs")
def test_localsession_traps_sigint(sample_job_and_dirs: tuple):
    # Make sure that we hook up, and remove the signal handler when using the local session
    sample_job, sample_job_parameters, template_dir, current_working_dir = sample_job_and_dirs

    # GIVEN
    with patch.object(local_session_mod, "signal") as signal_mod:
        # WHEN
        with LocalSession(
            job=sample_job, job_parameter_values=sample_job_parameters, session_id="test-id"
        ) as localsession:
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
    step_index: int,
    maximum_tasks: int,
    parameter_sets: list[dict],
    num_expected_tasks: int,
):
    """
    Test that calling `run_step` causes the local Session to run the tasks requested in that step.
    """
    sample_job, sample_job_parameters, template_dir, current_working_dir = sample_job_and_dirs

    if parameter_sets is None:
        parameter_sets = StepParameterSpaceIterator(
            space=sample_job.steps[step_index].parameterSpace
        )

    with (
        patch.object(
            LocalSession,
            "run_environment_enters",
            autospec=True,
            side_effect=LocalSession.run_environment_enters,
        ) as patched_run_environment_enters,
        patch.object(
            LocalSession,
            "run_environment_exits",
            autospec=True,
            side_effect=LocalSession.run_environment_exits,
        ) as patched_run_environment_exits,
        patch.object(
            LocalSession, "run_step", autospec=True, side_effect=LocalSession.run_step
        ) as patched_run_step,
        patch.object(
            LocalSession, "run_task", autospec=True, side_effect=LocalSession.run_task
        ) as patched_run_task,
    ):
        with LocalSession(
            job=sample_job, job_parameter_values=sample_job_parameters, session_id="my-session"
        ) as session:
            session.run_step(
                sample_job.steps[step_index],
                task_parameters=parameter_sets,
                maximum_tasks=maximum_tasks,
            )

        # It should have entered the environments in order
        assert patched_run_environment_enters.call_args_list == [
            call(session, None, EnvironmentType.EXTERNAL),
            call(session, sample_job.jobEnvironments, EnvironmentType.JOB),
            call(
                session,
                sample_job.steps[step_index].stepEnvironments,
                EnvironmentType.STEP,
                resolved_symtab=None,
                step_name=sample_job.steps[step_index].name,
            ),
        ]
        # It should have run one step
        assert patched_run_step.call_args_list == [
            call(
                session,
                sample_job.steps[step_index],
                task_parameters=parameter_sets,
                maximum_tasks=maximum_tasks,
            )
        ]
        # It should have exited the environments in reverse order
        assert patched_run_environment_exits.call_args_list == [
            call(session, type=EnvironmentType.STEP, keep_session_running=True),
            call(session, type=EnvironmentType.ALL, keep_session_running=False),
        ]

        assert patched_run_task.call_count == num_expected_tasks

        assert (
            "Open Job Description CLI: All actions completed successfully!"
            in capsys.readouterr().out
        )


@pytest.mark.usefixtures("sample_job_and_dirs")
def test_localsession_step_env_enter_receives_step_name(
    sample_job_and_dirs: tuple,
    patched_actions,
):
    """
    RFC 0007 §7.3.1 (EXPR): a step-environment enter passes the owning step's
    name to Session.enter_environment, while job/external environment enters
    never do.

    The step-environment assertion used to be gated on feature-detecting the
    keyword, which meant that against a sessions build without it the test took
    the other branch and asserted the keyword was *absent* -- passing while
    proving the opposite of its name. The `openjd-sessions >= 0.10.11` floor
    guarantees the keyword, so the assertion is now unconditional.
    """
    sample_job, sample_job_parameters, template_dir, current_working_dir = sample_job_and_dirs
    patched_enter = patched_actions[0]

    with LocalSession(
        job=sample_job, job_parameter_values=sample_job_parameters, session_id="step-name"
    ) as session:
        session.run_step(sample_job.steps[SampleSteps.NormalStep])

    assert not session.failed

    step_env_calls = [
        c
        for c in patched_enter.call_args_list
        if c.kwargs["identifier"].startswith(f"{EnvironmentType.STEP.name} - ")
    ]
    other_env_calls = [
        c
        for c in patched_enter.call_args_list
        if not c.kwargs["identifier"].startswith(f"{EnvironmentType.STEP.name} - ")
    ]

    assert step_env_calls
    for enter_call in step_env_calls:
        assert enter_call.kwargs["step_name"] == sample_job.steps[SampleSteps.NormalStep].name

    # Job/external environment enters never carry a step name.
    assert other_env_calls
    for enter_call in other_env_calls:
        assert "step_name" not in enter_call.kwargs


@pytest.mark.usefixtures("sample_job_and_dirs", "capsys")
def test_localsession_enter_environment_post_registration_raise(
    sample_job_and_dirs: tuple, capsys: pytest.CaptureFixture, patched_actions
):
    """
    A raise out of Session.enter_environment *after* the session registered
    the environment (e.g. an environment `variables` expression that fails to
    evaluate) must leave the environment in the CLI's entered list so cleanup
    exits it. Popping it would desynchronize CLI and session state: the
    environment's onExit would be skipped and cleanup would trip the session's
    LIFO exit check ("Must exit Environment X first"), masking the original
    error.
    """
    sample_job, sample_job_parameters, template_dir, current_working_dir = sample_job_and_dirs
    patched_enter = patched_actions[0]

    # The autouse fixture set the mock's side_effect to the real (pre-patch)
    # Session.enter_environment; capture it before redirecting the mock.
    real_enter = patched_enter.side_effect
    error_text = "Failed to evaluate the environment's variables"

    def register_then_raise(session, *, environment, identifier=None, **kwargs):
        if identifier is not None and identifier.startswith(f"{EnvironmentType.STEP.name} - "):
            # Mirror the state Session.enter_environment leaves behind when an
            # environment `variables` expression fails to evaluate: the
            # environment is registered in the session's entered list, but the
            # enter raises before any action runs.
            session._environments[identifier] = environment
            session._environments_entered.append(identifier)
            raise ValueError(error_text)
        return real_enter(session, environment=environment, identifier=identifier, **kwargs)

    step_env_id = f"{EnvironmentType.STEP.name} - env1"
    job_env_id = f"{EnvironmentType.JOB.name} - rootEnv"

    # Redirect the autouse fixture's Session.enter_environment mock from the
    # real method to the registering-then-raising simulation.
    patched_enter.side_effect = register_then_raise
    with LocalSession(
        job=sample_job, job_parameter_values=sample_job_parameters, session_id="post-reg"
    ) as session:
        with pytest.raises(LocalSessionFailed):
            session.run_step(sample_job.steps[SampleSteps.NormalStep])

        # The session registered the environment, so the CLI must keep it
        # in its own entered list for cleanup to exit.
        assert step_env_id in session._openjd_session.environments_entered
        assert (EnvironmentType.STEP, step_env_id) in session._environments_entered

    # Cleanup exited the registered step environment and then the job
    # environment, in LIFO order, rather than skipping the step environment.
    exited_ids = [
        exit_call.kwargs["identifier"]
        for exit_call in session._openjd_session.exit_environment.call_args_list  # type: ignore
    ]
    assert exited_ids == [step_env_id, job_env_id]

    assert session.failed
    output = capsys.readouterr().out
    assert error_text in output
    assert "Must exit Environment" not in output


@pytest.mark.usefixtures("sample_job_and_dirs", "capsys")
def test_localsession_run_failed(sample_job_and_dirs: tuple, capsys: pytest.CaptureFixture):
    """
    Test that a LocalSession can gracefully handle an error in its inner Session.
    """
    sample_job, sample_job_parameters, template_dir, current_working_dir = sample_job_and_dirs
    with (
        patch.object(
            LocalSession,
            "run_environment_enters",
            autospec=True,
            side_effect=LocalSession.run_environment_enters,
        ) as patched_run_environment_enters,
    ):
        with LocalSession(
            job=sample_job, job_parameter_values=sample_job_parameters, session_id="bad-session"
        ) as session:
            with pytest.raises(LocalSessionFailed):
                session.run_step(sample_job.steps[SampleSteps.BadCommand])

        # The Task has failed. That means that we've entered the one environment and also exited it.
        assert patched_run_environment_enters.call_args_list == [
            call(session, None, EnvironmentType.EXTERNAL),
            call(session, sample_job.jobEnvironments, EnvironmentType.JOB),
            call(
                session,
                sample_job.steps[SampleSteps.BadCommand].stepEnvironments,
                EnvironmentType.STEP,
                resolved_symtab=None,
                step_name=sample_job.steps[SampleSteps.BadCommand].name,
            ),
        ]
        session._openjd_session.exit_environment.assert_called_once()  # type: ignore
        assert session.failed
        assert session._cleanup_called
        assert "Open Job Description CLI: ERROR" in capsys.readouterr().out
