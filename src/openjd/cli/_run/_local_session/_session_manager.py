# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from queue import Queue
from threading import Event
import time
from typing import Optional, Type
from types import FrameType, TracebackType
from signal import signal, SIGINT, SIGTERM, SIG_DFL

from ._actions import EnterEnvironmentAction, ExitEnvironmentAction, RunTaskAction, SessionAction
from ._logs import LocalSessionLogHandler, LogEntry
from openjd.model import (
    EnvironmentTemplate,
    Job,
    JobParameterValues,
    ParameterValue,
    ParameterValueType,
    Step,
    StepParameterSpace,
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


class LocalSession:
    """
    A wrapper for the `Session` object in the `sessions` module
    that holds information about a locally-running Session launched
    from the CLI.
    """

    session_id: str
    failed: bool = False
    ended: Event
    tasks_run: int = 0
    _job: Job
    _maximum_tasks: int
    _start_seconds: float
    _end_seconds: float
    _inner_session: Session
    _action_queue: Queue[SessionAction]
    _current_action: Optional[SessionAction]
    _action_ended: Event
    _path_mapping_rules: Optional[list[PathMappingRule]]
    _environments: Optional[list[EnvironmentTemplate]]
    _log_handler: LocalSessionLogHandler
    _cleanup_called: bool

    def __init__(
        self,
        *,
        job: Job,
        session_id: str,
        path_mapping_rules: Optional[list[PathMappingRule]] = None,
        environments: Optional[list[EnvironmentTemplate]] = None,
        should_print_logs: bool = True,
        retain_working_dir: bool = False,
    ):
        self.session_id = session_id
        self.ended = Event()
        self._action_ended = Event()
        self._job = job
        self._path_mapping_rules = path_mapping_rules
        self._environments = environments

        # Create an inner Session
        job_parameters: JobParameterValues
        if job.parameters:
            job_parameters = {
                name: ParameterValue(type=ParameterValueType(param.type.value), value=param.value)
                for name, param in job.parameters.items()
            }
        else:
            job_parameters = dict[str, ParameterValue]()

        self._inner_session = Session(
            session_id=self.session_id,
            job_parameter_values=job_parameters,
            path_mapping_rules=self._path_mapping_rules,
            callback=self._action_callback,
            retain_working_dir=retain_working_dir,
        )

        # Initialize the action queue
        self._action_queue: Queue[SessionAction] = Queue()
        self._current_action = None

        self._should_print_logs = should_print_logs
        self._cleanup_called = False

    def __enter__(self) -> "LocalSession":
        # Add log handling
        self._log_handler = LocalSessionLogHandler(should_print=self._should_print_logs)
        LOG.addHandler(self._log_handler)
        signal(SIGINT, self._sigint_handler)
        signal(SIGTERM, self._sigint_handler)
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_value: Optional[BaseException],
        traceback: Optional[TracebackType],
    ) -> None:
        signal(SIGINT, SIG_DFL)
        signal(SIGTERM, SIG_DFL)
        self.cleanup()

    def _sigint_handler(self, signum: int, frame: Optional[FrameType]) -> None:
        """Signal handler that is invoked when the process receives a SIGINT/SIGTERM"""
        LOG.info("Interruption signal recieved.")
        self.cancel()

    def cleanup(self) -> None:
        if not self._cleanup_called:
            LOG.info(
                msg="Open Job Description CLI: Local Session ended! Now cleaning up Session resources.",
                extra={"session_id": self.session_id},
            )
            self._log_handler.close()
            LOG.removeHandler(self._log_handler)

            self._inner_session.cleanup()
            self._cleanup_called = True

    def initialize(
        self,
        *,
        dependencies: list[Step],
        step: Step,
        maximum_tasks: int = -1,
        task_parameter_values: Optional[list[dict]] = None,
    ) -> None:
        """
        Queues up necessary actions for the Step.

        Args:
            job: The Job this Step belongs to.
            step: The Step object to run.
            task_parameters: A list of Task parameter sets to run this Step with.
            If not specified, defaults to the first Task parameter set defined in the Step's
            parameter space.
        """

        self.ended.clear()

        session_environment_ids: list[str] = []
        # Enqueue "Enter Environment" actions for the given environments
        if self._environments:
            envs = [environ.environment for environ in self._environments]
            session_environment_ids += self._add_environments(envs)

        # Enqueue "Enter Environment" actions for root level environments
        if self._job.jobEnvironments:
            session_environment_ids += self._add_environments(self._job.jobEnvironments)

        # Step-level environments can only be defined if there is a single Step,
        # or else we can't run the required Steps in a single Session
        if not dependencies and step.stepEnvironments:
            session_environment_ids += self._add_environments(step.stepEnvironments)

        # Next, per dependency, enqueue "Run Task" actions for each set of Task parameters
        # If the Step takes no parameters, we only need to enqueue a single Step with an empty parameter list
        for dep in dependencies:
            if not dep.parameterSpace:
                self._action_queue.put(
                    RunTaskAction(
                        session=self._inner_session,
                        step=dep,
                        parameters=dict[str, ParameterValue](),
                    )
                )
            else:
                for parameter_set in StepParameterSpaceIterator(space=dep.parameterSpace):
                    self._action_queue.put(
                        RunTaskAction(
                            session=self._inner_session, step=dep, parameters=parameter_set
                        )
                    )

        # The Step specified by the user is the only one that needs to use custom Task parameters, if given
        if not step.parameterSpace:
            self._action_queue.put(RunTaskAction(self._inner_session, step=step, parameters=dict()))

        else:
            if not task_parameter_values:
                parameter_sets: list[TaskParameterSet] = list(
                    StepParameterSpaceIterator(space=step.parameterSpace)
                )
            else:
                try:
                    parameter_sets = [
                        self._generate_task_parameter_set(
                            parameter_space=step.parameterSpace, parameter_values=values
                        )
                        for values in task_parameter_values
                    ]

                except RuntimeError as rte:
                    LOG.info(
                        f"Open Job Description CLI: Skipping Task parameter set with errors:\n{str(rte)}"
                    )

                    # Set the `failed` flag to indicate that there were problems,
                    # but continue running the Session in case there are parameter sets that still work
                    self.failed = True

            # Task maximum is only imposed if the user provides a positive value
            if maximum_tasks > 0:
                parameter_sets = parameter_sets[: min(maximum_tasks, len(parameter_sets))]

            for param_set in parameter_sets:
                self._action_queue.put(
                    RunTaskAction(self._inner_session, step=step, parameters=param_set)
                )

        # Finally, enqueue ExitEnvironment Actions in reverse order to EnterEnvironment
        for env_id in reversed(session_environment_ids):
            self._action_queue.put(ExitEnvironmentAction(self._inner_session, env_id))

    def run(self) -> None:
        if self._inner_session.state != SessionState.READY:
            raise RuntimeError("Session is not in a READY state")

        self._start_seconds = time.perf_counter()
        while not self._action_queue.empty() and not self.failed:
            self._action_ended.clear()
            self._current_action = self._action_queue.get()
            self._current_action.run()
            self._action_ended.wait()

        if self.failed:
            # Action encountered an error; clean up resources and end session
            LOG.info(
                msg=f"Open Job Description CLI: ERROR executing action: '{str(self._current_action)}' (see Task logs for details)",
                extra={"session_id": self.session_id},
            )

        else:
            # In this case, we've finished all the Tasks and exited all the environments,
            # so we can clean up and end
            # else:
            LOG.info(
                msg="Open Job Description CLI: All actions completed successfully!",
                extra={"session_id": self.session_id},
            )
            self._current_action = None

        self._end_seconds = time.perf_counter()
        self.ended.set()

    def cancel(self):
        LOG.info(
            msg="Open Job Description CLI: Cancelling the session...",
            extra={"session_id": self.session_id},
        )

        if self._inner_session.state == SessionState.RUNNING:
            # The action will call self._action_callback when it has exited,
            # and that will exit the loop in self.run()
            self._inner_session.cancel_action()

        LOG.info(
            msg=f"Open Job Description CLI: Session terminated by user while running action: '{str(self._current_action)}'.",
            extra={"session_id": self.session_id},
        )
        self.failed = True

    def get_duration(self) -> float:
        if not self._start_seconds:
            return 0
        elif not self._end_seconds:
            return time.perf_counter() - self._start_seconds
        return self._end_seconds - self._start_seconds

    def get_log_messages(self) -> list[LogEntry]:
        return self._log_handler.messages

    def _generate_task_parameter_set(
        self, *, parameter_space: StepParameterSpace, parameter_values: dict
    ) -> TaskParameterSet:
        """
        Convert dictionary-formatted Task parameters into a TaskParameterSet that can
        be used in a Session.
        If any parameters are missing from the dictionary, we will default to using
        the first value for that parameter defined in the Step's parameter space.
        """

        # For each parameter defined in the Step, assert that it appears
        # with the correct type in each parameter set provided by the user.
        # We compound each error into a log message so that the user
        # can fix as many as possible at once.

        defined_names = set(parameter_space.taskParameterDefinitions.keys())
        provided_names = set(parameter_values.keys())

        # First, check for extraneous parameters
        extra_names = provided_names.difference(defined_names)
        for name in extra_names:
            LOG.info(
                msg=f"Skipping unused parameter '{name}'", extra={"session_id": self.session_id}
            )

        # The first value in the parameter space iterator will hold the default value
        # we use for each missing parameter
        default_set = StepParameterSpaceIterator(space=parameter_space)[0]

        parameter_set = TaskParameterSet()
        for name in defined_names:
            # Note that parameter sets don't verify types, so any errors resulting from
            # type mismatches will be raised when the inner Session attempts to use them.
            if name in parameter_values:
                parameter_set.update(
                    {
                        name: ParameterValue(
                            type=ParameterValueType(
                                parameter_space.taskParameterDefinitions[name].type
                            ),
                            value=f"{parameter_values[name]}",
                        )
                    }
                )
            else:
                parameter_set.update(
                    {
                        name: ParameterValue(
                            type=ParameterValueType(
                                parameter_space.taskParameterDefinitions[name].type
                            ),
                            value=default_set[name].value,
                        )
                    }
                )

        return parameter_set

    def _action_callback(self, session_id: str, new_status: ActionStatus) -> None:
        if new_status.state == ActionState.SUCCESS:
            if isinstance(self._current_action, RunTaskAction):
                self.tasks_run += 1
            self._action_ended.set()
        if new_status.state in (ActionState.FAILED, ActionState.CANCELED):
            self.failed = True
            self._action_ended.set()

    def _add_environments(self, envs: list) -> list[str]:
        ids: list[str] = []
        for env in envs:
            self._action_queue.put(EnterEnvironmentAction(self._inner_session, env, env.name))
            ids.append(env.name)
        return ids
