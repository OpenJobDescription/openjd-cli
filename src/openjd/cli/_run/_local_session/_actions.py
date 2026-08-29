# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from enum import Enum
from typing import TYPE_CHECKING, Optional

from openjd.model import Step, TaskParameterSet
from openjd.model.v2023_09 import Environment
from openjd.sessions import Session

if TYPE_CHECKING:
    # Annotations only: `openjd.expr` is a facade over the native extension and
    # importing the CLI must not load it. These tables are produced by
    # `create_job_with_symbol_tables` and forwarded unchanged.
    from openjd.expr import SerializedSymbolTable


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
    _resolved_symtab: Optional["SerializedSymbolTable"]

    def __init__(
        self,
        session: Session,
        step: Step,
        parameters: TaskParameterSet,
        resolved_symtab: Optional["SerializedSymbolTable"] = None,
    ):
        super(RunTaskAction, self).__init__(session)
        self._step = step
        self._parameters = parameters
        # The step's create-time resolved symbol table
        # (`create_job_with_symbol_tables().step_symbol_tables[step.name]`).
        # It is the only channel for the step's template-scope `let` values:
        # the model does not merge them into `script.let`, and the session does
        # not re-evaluate the source expressions.
        self._resolved_symtab = resolved_symtab

    def run(self):
        self._session.run_task(
            step_script=self._step.script,
            task_parameter_values=self._parameters,
            # RFC 0008: the step name feeds the WrappedStep.Name template
            # variable inside an active onWrapTaskRun hook.
            step_name=self._step.name,
            resolved_symtab=self._resolved_symtab,
        )

    def __str__(self):
        parameters = {name: parameter.value for name, parameter in self._parameters.items()}
        return f"Run Step '{self._step.name}' with Task parameters '{str(parameters)}'"


class EnterEnvironmentAction(SessionAction):
    _environment: Environment
    _id: str
    _resolved_symtab: Optional["SerializedSymbolTable"]
    _step_name: Optional[str]

    def __init__(
        self,
        session: Session,
        environment: Environment,
        env_id: str,
        resolved_symtab: Optional["SerializedSymbolTable"] = None,
        step_name: Optional[str] = None,
    ):
        super(EnterEnvironmentAction, self).__init__(session)
        self._environment = environment
        self._id = env_id
        # RFC 0005 §3.6: a step's environments are entered with the step's
        # create-time resolved symbol table, which carries the step's
        # template-scope `let` values so their variables/actions can reference
        # them. Only step-environment enters have one; job and external
        # environment enters leave it None.
        self._resolved_symtab = resolved_symtab
        # RFC 0007 §7.3.1 (EXPR): the owning step's name seeds Step.Name for
        # a step environment's `let` bindings, variables, and actions. Only
        # step-environment enters carry a step name; job/external enters
        # leave it None.
        self._step_name = step_name

    def run(self):
        # `step_name` is omitted rather than passed as None when this enter has
        # no owning step. Passing None would be equivalent today, since
        # enter_environment skips a None `step_name`, but omitting it keeps the
        # call site's intent legible at the boundary and it is what
        # test_localsession_step_env_enter_receives_step_name asserts — that
        # assertion is currently the only check that job and external enters
        # do not seed Step.Name, because a template referencing Step.Name
        # outside a step is rejected by static validation before any session
        # is built, so no loadable template can observe it.
        #
        # `resolved_symtab` is passed unconditionally: None is its documented
        # "no table" value and there is no analogous assertion keyed on its
        # absence.
        optional_kwargs: dict[str, str] = {}
        if self._step_name is not None:
            optional_kwargs["step_name"] = self._step_name
        self._session.enter_environment(
            environment=self._environment,
            identifier=self._id,
            resolved_symtab=self._resolved_symtab,
            **optional_kwargs,
        )

    def __str__(self):
        return f"Enter Environment '{self._environment.name}'"


class ExitEnvironmentAction(SessionAction):
    _id: str
    _keep_session_running: bool
    _resolved_symtab: Optional["SerializedSymbolTable"]

    def __init__(
        self,
        session: Session,
        id: str,
        keep_session_running: bool,
        resolved_symtab: Optional["SerializedSymbolTable"] = None,
    ):
        super(ExitEnvironmentAction, self).__init__(session)
        self._id = id
        self._keep_session_running = keep_session_running
        # The same table the environment was entered with, so its onExit
        # resolves in the same scope as its onEnter (what
        # Session.exit_environment documents for this argument).
        #
        # Unlike the worker agent, the CLI holds the table as an object rather
        # than a JSON string served by the service, so there is no parse step
        # here that could fail and no wrapper degrading a parse failure to None
        # to keep teardown unconditional. An environment entered without a
        # table simply exits without one.
        self._resolved_symtab = resolved_symtab

    def run(self):
        self._session.exit_environment(
            identifier=self._id,
            keep_session_running=self._keep_session_running,
            resolved_symtab=self._resolved_symtab,
        )

    def __str__(self):
        return f"Exit Environment '{self._id}'"
