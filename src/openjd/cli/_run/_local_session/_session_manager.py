# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from queue import Queue
from threading import Event
import time
from typing import Any, Iterable, Optional, Type
from types import FrameType, TracebackType
from signal import signal, SIGINT, SIGTERM, SIG_DFL
from itertools import islice
from datetime import datetime, timedelta, timezone

from ._actions import (
    EnterEnvironmentAction,
    ExitEnvironmentAction,
    RunTaskAction,
    SessionAction,
    EnvironmentType,
)
from ._logs import LocalSessionLogHandler, LogEntry, LoggingTimestampFormat
from ..._common import SUPPORTED_EXTENSIONS

from openjd.model import (
    IntRangeExpr,
    Job,
    JobParameterValues,
    RevisionExtensions,
    SpecificationRevision,
    Step,
    StepParameterSpaceIterator,
    TaskParameterSet,
)
from openjd.sessions import (
    LOG,
    ActionState,
    ActionStatus,
    Session,
    SessionState,
    PathMappingRule,
)


class LocalSessionFailed(RuntimeError):
    """
    Raised when an action in the session fails.
    """

    def __init__(self, failed_action: SessionAction):
        self.failed_action = failed_action
        super().__init__(f"Action failed: {failed_action}")


class LocalSession:
    """
    A class to manage a `Session` object from the `sessions` module,
    to run tasks of a job in a locally-running Session launched from the CLI.

    An OpenJD session's purpose is to run tasks from a single job. It can run
    tasks from different steps, as long as it enters the step environments
    before and exits them after.
    """

    session_id: str
    failed: bool = False
    task_run_count: int = 0
    _job: Job
    _maximum_tasks: int
    _openjd_session: Session
    _enter_env_queue: Queue[EnterEnvironmentAction]
    _action_queue: Queue[RunTaskAction]
    _current_action: Optional[SessionAction]
    _failed_action: Optional[SessionAction]
    _action_ended: Event
    _path_mapping_rules: Optional[list[PathMappingRule]]
    _environments: Optional[list[Any]]
    _environments_entered: list[tuple[EnvironmentType, str]]
    _log_handler: LocalSessionLogHandler
    _cleanup_called: bool

    def __init__(
        self,
        *,
        job: Job,
        job_parameter_values: JobParameterValues,
        session_id: str,
        timestamp_format: LoggingTimestampFormat = LoggingTimestampFormat.RELATIVE,
        path_mapping_rules: Optional[list[PathMappingRule]] = None,
        environments: Optional[list[Any]] = None,
        should_print_logs: bool = True,
        retain_working_dir: bool = False,
        revision_extensions: RevisionExtensions = RevisionExtensions(
            spec_rev=SpecificationRevision.v2023_09, supported_extensions=SUPPORTED_EXTENSIONS
        ),
    ):
        self.session_id = session_id
        self._action_ended = Event()
        self._job = job
        self._timestamp_format = timestamp_format
        self._path_mapping_rules = path_mapping_rules
        self._environments = environments

        # Create an OpenJD Session
        self._openjd_session = Session(
            session_id=self.session_id,
            job_parameter_values=job_parameter_values,
            path_mapping_rules=self._path_mapping_rules,
            callback=self._action_callback,
            retain_working_dir=retain_working_dir,
            revision_extensions=revision_extensions,
        )

        self._should_print_logs = should_print_logs
        self._cleanup_called = False
        self._started = False

        self._current_action = None
        self._failed_action = None
        self._environments_entered = []

        # Initialize the action queue
        self._enter_env_queue: Queue[EnterEnvironmentAction] = Queue()
        self._action_queue: Queue[RunTaskAction] = Queue()

    def _context_manager_cleanup(self):
        try:
            # Exit all the environments that were entered
            self.run_environment_exits(type=EnvironmentType.ALL, keep_session_running=False)
        finally:
            signal(SIGINT, SIG_DFL)
            signal(SIGTERM, SIG_DFL)
            self._started = False

            # A blank line to separate the job log output from this status message
            LOG.info(
                msg="",
                extra={"session_id": self.session_id},
            )
            if self.failed:
                LOG.info(
                    msg=f"Open Job Description CLI: ERROR executing action: '{self.failed_action}' (see Task logs for details)",
                    extra={"session_id": self.session_id},
                )
            else:
                LOG.info(
                    msg="Open Job Description CLI: All actions completed successfully!",
                    extra={"session_id": self.session_id},
                )
            self.cleanup()
            self._started = False

    def __enter__(self) -> "LocalSession":
        # Add log handling
        session_start_timestamp = datetime.now(timezone.utc)
        self._log_handler = LocalSessionLogHandler(
            should_print=self._should_print_logs,
            session_start_timestamp=session_start_timestamp,
            timestamp_format=self._timestamp_format,
        )
        LOG.addHandler(self._log_handler)
        LOG.info(
            msg=f"Open Job Description CLI: Session start {session_start_timestamp.astimezone().isoformat()}",
            extra={"session_id": self.session_id},
        )
        LOG.info(
            msg=f"Open Job Description CLI: Running job '{self._job.name}'",
            extra={"session_id": self.session_id},
        )
        signal(SIGINT, self._sigint_handler)
        signal(SIGTERM, self._sigint_handler)

        self._started = True

        # Enter all the external and job environments
        try:
            self.run_environment_enters(self._environments, EnvironmentType.EXTERNAL)
            self.run_environment_enters(self._job.jobEnvironments, EnvironmentType.JOB)
        except LocalSessionFailed:
            # If __enter__ fails, __exit__ won't be called so need to clean up here
            self._context_manager_cleanup()
            raise

        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        # __enter__ should have been called before __exit__
        if not self._started:
            raise RuntimeError("Session was not started via a with statement.")

        self._context_manager_cleanup()

    def _sigint_handler(self, signum: int, frame: Optional[FrameType]) -> None:
        """Signal handler that is invoked when the process receives a SIGINT/SIGTERM"""
        LOG.info("Interruption signal recieved.")
        self.cancel()

    def run_environment_enters(self, environments: Optional[list[Any]], type: EnvironmentType):
        """Enter one or more environments in the session."""
        if environments is None:
            return

        if self._openjd_session.state != SessionState.READY:
            raise RuntimeError(
                f"Session must be in READY state, but is in {self._openjd_session.state.name}"
            )

        for env in environments:
            env_id = f"{type.name} - {env.name}"
            self._action_ended.clear()
            self._current_action = EnterEnvironmentAction(
                session=self._openjd_session, environment=env, env_id=env_id
            )
            self._environments_entered.append((type, env_id))
            self._current_action.run()
            self._action_ended.wait()
            if self.failed:
                self._failed_action = self._current_action
                self._current_action = None
                raise LocalSessionFailed(self._failed_action)
        self._current_action = None

    def run_environment_exits(self, type: EnvironmentType, *, keep_session_running: bool):
        """Exit environments that were entered in this session, in reverse order.
        Only exits environments matching the provided environment type.
        """
        if self._openjd_session.state not in (SessionState.READY, SessionState.READY_ENDING):
            raise RuntimeError(
                f"Session must be in READY or READY_ENDING state, but is in {self._openjd_session.state.name}"
            )

        failed_action = None

        while self._environments_entered and self._environments_entered[-1][0].matches(type):
            env_id = self._environments_entered.pop()[1]
            prev_action_failed = self.failed
            self._action_ended.clear()
            self._current_action = ExitEnvironmentAction(
                session=self._openjd_session, id=env_id, keep_session_running=keep_session_running
            )
            self._current_action.run()
            self._action_ended.wait()
            if self.failed and not prev_action_failed:
                failed_action = self._failed_action = self._current_action
        self._current_action = None

        if failed_action:
            raise LocalSessionFailed(failed_action)

    def run_task(self, step: Step, parameter_set: TaskParameterSet) -> None:
        """Run a single task of a step in the session."""
        if self._openjd_session.state != SessionState.READY:
            raise RuntimeError(
                f"Session must be in READY state, but is in {self._openjd_session.state.name}"
            )

        self._action_ended.clear()
        self._current_action = RunTaskAction(
            session=self._openjd_session, step=step, parameters=parameter_set
        )
        self._current_action.run()
        self._action_ended.wait()
        if self.failed:
            self._failed_action = self._current_action
            self._current_action = None
            raise LocalSessionFailed(self._failed_action)
        self._current_action = None

    def _run_tasks_adaptive_chunking(
        self, step: Step, task_parameters: StepParameterSpaceIterator, maximum_tasks: Optional[int]
    ):
        """Runs all the tasks of the task_parameters iterator with adaptive chunking."""
        completed_task_count = 0
        completed_task_duration = 0.0
        target_runtime_seconds = int(
            step.parameterSpace.taskParameterDefinitions[  # type: ignore
                task_parameters.chunks_parameter_name  # type: ignore
            ].chunks.targetRuntimeSeconds
        )  # type: ignore

        while True:
            # Get the next chunk to run
            parameter_set = next(task_parameters, None)
            if parameter_set is None:
                break

            start_seconds = time.perf_counter()
            # This may raise a LocalSessionFailed exception
            self.run_task(step, parameter_set)
            duration = time.perf_counter() - start_seconds

            # Accumulate the task count and duration from running this chunk
            completed_task_count += len(
                IntRangeExpr.from_str(parameter_set[task_parameters.chunks_parameter_name].value)  # type: ignore
            )
            completed_task_duration += duration

            # Estimate a chunk size based on the statistics, and update the iterator. Note that this
            # logic is very simple, providing a good starting point that behaves reasonably for other implementations
            # to follow.
            duration_per_task = completed_task_duration / completed_task_count
            adaptive_chunk_size = target_runtime_seconds / duration_per_task
            if (
                completed_task_count < 10
                and adaptive_chunk_size > task_parameters.chunks_default_task_count  # type: ignore
            ):
                # When we have data about only a few tasks, gradually blend in the new estimate instead of cutting over immediately
                adaptive_chunk_size = (
                    0.75 * task_parameters.chunks_default_task_count + 0.25 * adaptive_chunk_size  # type: ignore
                )
            adaptive_chunk_size = max(int(adaptive_chunk_size), 1)
            if adaptive_chunk_size != task_parameters.chunks_default_task_count:
                LOG.info(
                    msg=f"Open Job Description CLI: Ran {completed_task_count} tasks in {timedelta(seconds=completed_task_duration)}, average {timedelta(seconds=completed_task_duration / completed_task_count)}",
                    extra={"session_id": self.session_id},
                )
                LOG.info(
                    msg=f"Open Job Description CLI: Adjusting chunk size from {task_parameters.chunks_default_task_count} to {adaptive_chunk_size}",
                    extra={"session_id": self.session_id},
                )
                task_parameters.chunks_default_task_count = adaptive_chunk_size

            # If a maximum task count was specified, count them down
            if maximum_tasks and maximum_tasks > 0:
                maximum_tasks -= 1
                if maximum_tasks == 0:
                    break

    def run_step(
        self,
        step: Step,
        task_parameters: Optional[Iterable[TaskParameterSet]] = None,
        maximum_tasks: Optional[int] = None,
    ) -> None:
        """Run a step in the session. Optional parameters control which tasks to run."""
        if self._openjd_session.state != SessionState.READY:
            raise RuntimeError(
                f"Session must be in READY state, but is in {self._openjd_session.state.name}"
            )

        LOG.info(
            msg=f"Open Job Description CLI: Running step '{step.name}'",
            extra={"session_id": self.session_id},
        )

        if task_parameters is None:
            task_parameters = StepParameterSpaceIterator(space=step.parameterSpace)

        # Enter all the step environments
        self.run_environment_enters(step.stepEnvironments, EnvironmentType.STEP)

        try:
            # Run the tasks
            if (
                isinstance(task_parameters, StepParameterSpaceIterator)
                and task_parameters.chunks_adaptive
            ):
                self._run_tasks_adaptive_chunking(step, task_parameters, maximum_tasks)
            else:
                # Run without adaptive chunking
                if maximum_tasks and maximum_tasks > 0:
                    task_parameters = islice(task_parameters, maximum_tasks)

                for parameter_set in task_parameters:
                    # This may raise a LocalSessionFailed exception
                    self.run_task(step, parameter_set)
        finally:
            # Exit all the step environments
            self.run_environment_exits(type=EnvironmentType.STEP, keep_session_running=True)

    def cleanup(self) -> None:
        if not self._cleanup_called:
            LOG.info(
                msg="Open Job Description CLI: Local Session ended! Now cleaning up Session resources.",
                extra={"session_id": self.session_id},
            )
            self._log_handler.close()
            LOG.removeHandler(self._log_handler)

            self._openjd_session.cleanup()
            self._cleanup_called = True

    @property
    def failed_action(self) -> Optional[SessionAction]:
        """The action that failed, if any."""
        return self._failed_action

    def cancel(self):
        LOG.info(
            msg="Open Job Description CLI: Cancelling the session...",
            extra={"session_id": self.session_id},
        )

        if self._openjd_session.state == SessionState.RUNNING:
            # The action will call self._action_callback when it has exited,
            # and that will exit the loop in self.run()
            self._openjd_session.cancel_action()

        LOG.info(
            msg=f"Open Job Description CLI: Session terminated by user while running action: '{str(self._current_action)}'.",
            extra={"session_id": self.session_id},
        )
        self.failed = True

    def get_log_messages(self) -> list[LogEntry]:
        return self._log_handler.messages

    def _action_callback(self, session_id: str, new_status: ActionStatus) -> None:
        if new_status.state == ActionState.SUCCESS:
            if isinstance(self._current_action, RunTaskAction):
                self.task_run_count += 1
            self._action_ended.set()
        if new_status.state in (ActionState.FAILED, ActionState.CANCELED, ActionState.TIMEOUT):
            self.failed = True
            self._action_ended.set()
