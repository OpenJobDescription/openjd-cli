# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import inspect
from enum import Enum
from typing import Any, Optional

from openjd.model import Step, TaskParameterSet
from openjd.model.v2023_09 import Environment
from openjd.sessions import Session

# Version-skew guard: the step_name keyword was added to
# Session.enter_environment alongside RFC 0007 Step.Name support. Detect it
# once so this CLI keeps working against older openjd-sessions releases that
# don't accept the keyword (every step-environment enter carries a step name,
# so a value-presence check alone isn't enough here).
_ENTER_ENVIRONMENT_ACCEPTS_STEP_NAME: bool = (
    "step_name" in inspect.signature(Session.enter_environment).parameters
)


class EnvironmentType(str, Enum):
    """
    The three different types of environment types that can be entered/exited in a session.
    """

    EXTERNAL = "EXTERNAL"
    JOB = "JOB"
    STEP = "STEP"
    ALL = "ALL"

    def matches(self, other: "EnvironmentType") -> bool:
        """Environment types match if they are equal, or one of them is ALL."""
        return self == other or self == EnvironmentType.ALL or other == EnvironmentType.ALL


class SessionAction:
    _session: Session
    duration: float

    def __init__(self, session: Session):
        self._session = session

    def run(self):
        """
        Subclasses of `SessionAction` should have
        custom implementations of this depending on their type.
        """


class RunTaskAction(SessionAction):
    _step: Step
    _parameters: TaskParameterSet

    def __init__(self, session: Session, step: Step, parameters: TaskParameterSet):
        super(RunTaskAction, self).__init__(session)
        self._step = step
        self._parameters = parameters

    def run(self):
        self._session.run_task(
            step_script=self._step.script,
            task_parameter_values=self._parameters,
            # RFC 0008: the step name feeds the WrappedStep.Name template
            # variable inside an active onWrapTaskRun hook.
            step_name=self._step.name,
        )

    def __str__(self):
        parameters = {name: parameter.value for name, parameter in self._parameters.items()}
        return f"Run Step '{self._step.name}' with Task parameters '{str(parameters)}'"


class EnterEnvironmentAction(SessionAction):
    _environment: Environment
    _id: str
    _extra_let_bindings: Optional[list[str]]
    _step_name: Optional[str]

    def __init__(
        self,
        session: Session,
        environment: Environment,
        env_id: str,
        extra_let_bindings: Optional[list[str]] = None,
        step_name: Optional[str] = None,
    ):
        super(EnterEnvironmentAction, self).__init__(session)
        self._environment = environment
        self._id = env_id
        # RFC 0007: a step's environments are entered with the step-level
        # `let` bindings so their variables/actions can reference them.
        self._extra_let_bindings = extra_let_bindings
        # RFC 0007 §7.3.1 (EXPR): the owning step's name seeds Step.Name for
        # a step environment's `let` bindings, variables, and actions. Only
        # step-environment enters carry a step name; job/external enters
        # leave it None.
        self._step_name = step_name

    def run(self):
        # Backwards compatibility: only forward `extra_let_bindings` when the
        # step actually defines `let` bindings (RFC 0007). Older
        # openjd-sessions releases don't accept the keyword, so omitting it
        # by default keeps this CLI working with any sessions version for
        # every template that doesn't use step-level lets — the reasonable
        # default is simply "no extra bindings". `step_name` follows the same
        # pattern, but since every step-environment enter has a step name, it
        # is additionally gated on the installed openjd-sessions accepting
        # the keyword; without it, Step.Name simply stays undefined (the
        # pre-RFC 0007 behavior).
        optional_kwargs: dict[str, Any] = {}
        if self._extra_let_bindings:
            optional_kwargs["extra_let_bindings"] = self._extra_let_bindings
        if self._step_name is not None and _ENTER_ENVIRONMENT_ACCEPTS_STEP_NAME:
            optional_kwargs["step_name"] = self._step_name
        self._session.enter_environment(
            environment=self._environment,
            identifier=self._id,
            **optional_kwargs,
        )

    def __str__(self):
        return f"Enter Environment '{self._environment.name}'"


class ExitEnvironmentAction(SessionAction):
    _id: str
    _keep_session_running: bool

    def __init__(self, session: Session, id: str, keep_session_running: bool):
        super(ExitEnvironmentAction, self).__init__(session)
        self._id = id
        self._keep_session_running = keep_session_running

    def run(self):
        self._session.exit_environment(
            identifier=self._id, keep_session_running=self._keep_session_running
        )

    def __str__(self):
        return f"Exit Environment '{self._id}'"
