# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from .._common import OpenJDCliResult
from openjd.model import Job, Step, StepParameterSpaceIterator


def _populate_summary_list(source: list, to_summary_func: Callable) -> list:
    """
    Given a list of elements, uses the `to_summary_func` argument
    to transform each element into a summary dataclass, returning
    the list of summary objects.
    """
    summary_list: list = []
    for item in source:
        summary_list.append(to_summary_func(item))
    return summary_list


def _format_summary_list(data: list, padding: int = 0) -> str:
    """
    Prints the supplied list of summary objects as a bulleted list.
    """
    formatted_list: str = ""
    for item in data:
        formatted_list += " " * padding + f"- {str(item)}\n"

    return formatted_list


@dataclass
class ParameterSummary:
    """
    Organizes Parameter information in a dataclass.
    """

    name: str
    description: Optional[str]
    type: str
    value: Optional[str]

    def __str__(self) -> str:
        readable_string = f"{self.name} ({self.type})"

        if self.value:
            readable_string += f": {self.value}"

        return readable_string


@dataclass
class EnvironmentSummary:
    """
    Organizes Environment information in a dataclass.
    """

    name: str
    description: Optional[str]
    parent: str = field(default="root")

    def __str__(self) -> str:
        readable_string = f"{self.name} (from '{self.parent}')"
        if self.description:
            readable_string += f"\n {self.description}"

        return readable_string


@dataclass
class DependencySummary:
    """
    Organizes Step dependency information in a dataclass.
    Will include more fields when Step dependencies are further expanded on!
    """

    step_name: str

    def __str__(self) -> str:
        return f"'{self.step_name}'"


@dataclass
class StepSummary:
    """
    Organizes Step information in a dataclass.
    """

    name: str
    description: Optional[str]
    parameter_definitions: Optional[list[ParameterSummary]]
    total_tasks: int
    environments: Optional[list[EnvironmentSummary]]
    dependencies: Optional[list[DependencySummary]]

    def __str__(self) -> str:
        summary_str = f"'{self.name}' ({self.total_tasks} total Tasks)\n"

        if self.parameter_definitions:
            summary_str += (
                f"  Task parameters:\n{_format_summary_list(self.parameter_definitions, padding=4)}"
            )

        if self.environments:
            summary_str += f"  {len(self.environments)} environments\n"

        if self.dependencies:
            summary_str += f"  {len(self.dependencies)} dependencies\n"

        return summary_str


@dataclass
class OpenJDJobSummaryResult(OpenJDCliResult):
    """
    A CLI result object with information specific to invoking the `summary` command on a Job.
    """

    name: str
    parameter_definitions: Optional[list[ParameterSummary]]
    total_steps: int
    total_tasks: int
    total_environments: int
    root_environments: Optional[list[EnvironmentSummary]]
    steps: list[StepSummary]

    def __str__(self) -> str:
        summary_str = f"\n--- {self.message} ---\n"

        # For each parameter, print its name and its value (may be default or user-provided)
        if self.parameter_definitions:
            summary_str += (
                f"\nParameters:\n{_format_summary_list(self.parameter_definitions, padding=2)}"
            )

        summary_str += f"""
Total steps: {self.total_steps}
Total tasks: {self.total_tasks}
Total environments: {self.total_environments}
"""

        summary_str += f"\n--- Steps in '{self.name}' ---\n\n"
        for index, step in enumerate(self.steps):
            summary_str += f"{index+1}. {str(step)}\n"

        if self.total_environments:
            summary_str += f"\n--- Environments in '{self.name}' ---\n"
            if self.root_environments:
                summary_str += _format_summary_list(self.root_environments, padding=2)

            for step in self.steps:
                if step.environments:
                    summary_str += _format_summary_list(step.environments, padding=2)

        return summary_str


@dataclass
class OpenJDStepSummaryResult(OpenJDCliResult):
    """
    A CLI result with fields specific to invoking the `summary` command on a Step.
    """

    job_name: str
    step_name: str
    total_parameters: int
    parameter_definitions: Optional[list[ParameterSummary]]
    total_tasks: int
    total_environments: int
    environments: Optional[list[EnvironmentSummary]]
    dependencies: Optional[list[DependencySummary]]

    def __str__(self) -> str:
        summary_str = f"""
--- {self.message} ---

Total tasks: {self.total_tasks}
Total task parameters: {self.total_parameters}
Total environments: {self.total_environments}
"""

        if self.dependencies:
            summary_str += f"\nDependencies ({len(self.dependencies)}):\n{_format_summary_list(self.dependencies)}"

        if self.parameter_definitions:
            summary_str += f"\nParameters:\n{_format_summary_list(self.parameter_definitions)}"

        if self.environments:
            summary_str += f"\nEnvironments:\n{_format_summary_list(self.environments)}"

        return summary_str


def _get_step_summary(step: Step) -> StepSummary:
    """
    Given a Step object, transforms its relevant attributes
    into a StepSummary dataclass.
    """

    parameter_definitions: Optional[list[ParameterSummary]] = None
    environments: Optional[list[EnvironmentSummary]] = None
    dependencies: Optional[list[DependencySummary]] = None
    total_tasks = 1

    parameter_definitions = []
    if step.parameterSpace:
        parameter_definitions = _populate_summary_list(
            [(name, param) for name, param in step.parameterSpace.taskParameterDefinitions.items()],
            lambda param_tuple: ParameterSummary(
                name=param_tuple[0], description=None, type=param_tuple[1].type.value, value=None
            ),
        )
        total_tasks = len(
            StepParameterSpaceIterator(space=step.parameterSpace, chunks_task_count_override=1)
        )

    environments = []
    if step.stepEnvironments:
        environments = _populate_summary_list(
            step.stepEnvironments,
            lambda env: EnvironmentSummary(
                name=env.name, parent=step.name, description=env.description
            ),
        )

    dependencies = []
    if step.dependencies:
        dependencies = _populate_summary_list(
            step.dependencies, lambda dep: DependencySummary(step_name=dep.dependsOn)
        )

    return StepSummary(
        name=step.name,
        description=step.description,
        parameter_definitions=parameter_definitions,
        total_tasks=total_tasks,
        environments=environments,
        dependencies=dependencies,
    )


def output_summary_result(job: Job, step_name: str | None = None) -> OpenJDCliResult:
    """
    Returns a CLI result object with information about this Job.
    """

    steps_list: list[StepSummary] = [_get_step_summary(step) for step in job.steps]
    step_envs = sum(len(step.environments) if step.environments else 0 for step in steps_list)

    if not step_name:
        # We only need information about parameters and root environments
        # if we're summarizing an entire Job

        params_list: list[ParameterSummary] = []
        if job.parameters:
            params_list = _populate_summary_list(
                [(name, param) for name, param in job.parameters.items()],
                lambda param_tuple: ParameterSummary(
                    name=param_tuple[0],
                    description=param_tuple[1].description,
                    type=param_tuple[1].type.name,
                    value=param_tuple[1].value,
                ),
            )

        envs_list: list[EnvironmentSummary] = []
        if job.jobEnvironments:
            envs_list = _populate_summary_list(
                job.jobEnvironments,
                lambda env: EnvironmentSummary(name=env.name, description=env.description),
            )

        return OpenJDJobSummaryResult(
            status="success",
            message=f"Summary for '{job.name}'",
            name=job.name,
            parameter_definitions=params_list if params_list else None,
            total_steps=len(steps_list),
            total_tasks=sum(step.total_tasks for step in steps_list),
            total_environments=len(envs_list) + step_envs if envs_list else step_envs,
            root_environments=envs_list if envs_list else None,
            steps=steps_list,
        )

    for step in steps_list:
        if step.name == step_name:
            return OpenJDStepSummaryResult(
                status="success",
                message=f"Summary for Step '{step.name}' in Job '{job.name}'",
                job_name=job.name,
                step_name=step.name,
                total_parameters=(
                    len(step.parameter_definitions) if step.parameter_definitions else 0
                ),
                parameter_definitions=step.parameter_definitions,
                total_tasks=step.total_tasks,
                total_environments=len(step.environments) if step.environments else 0,
                environments=step.environments,
                dependencies=step.dependencies,
            )

    return OpenJDCliResult(
        status="error", message=f"Step '{step_name}' does not exist in Job '{job.name}'."
    )
