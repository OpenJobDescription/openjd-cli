# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from openjd.model import Step, TaskParameterSet
from openjd.model.v2023_09 import Environment
from openjd.sessions import Session


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
            step_script=self._step.script, task_parameter_values=self._parameters
        )

    def __str__(self):
        parameters = {name: parameter.value for name, parameter in self._parameters.items()}
        return f"Run Step '{self._step.name}' with Task parameters '{str(parameters)}'"


class EnterEnvironmentAction(SessionAction):
    _environment: Environment
    _id: str

    def __init__(self, session: Session, environment: Environment, env_id: str):
        super(EnterEnvironmentAction, self).__init__(session)
        self._environment = environment
        self._id = env_id

    def run(self):
        self._session.enter_environment(environment=self._environment, identifier=self._id)

    def __str__(self):
        return f"Enter Environment '{self._environment.name}'"


class ExitEnvironmentAction(SessionAction):
    _id: str

    def __init__(self, session: Session, id: str):
        super(ExitEnvironmentAction, self).__init__(session)
        self._id = id

    def run(self):
        self._session.exit_environment(identifier=self._id)

    def __str__(self):
        return f"Exit Environment '{self._id}'"
