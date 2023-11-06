# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional

from ._local_session._session_manager import LocalSession, LogEntry
from .._common import (
    OpenJDCliResult,
    generate_job,
    get_task_params,
    print_cli_result,
)
from openjd.model import Job, Step
from openjd.sessions import PathMappingRule


@dataclass
class OpenJDRunResult(OpenJDCliResult):
    """
    Holds information and Task logs from a local Session.
    """

    job_name: str
    step_name: str
    duration: float
    tasks_run: int
    logs: list[LogEntry]

    def __str__(self) -> str:
        return f"""
--- Results of local session ---

{self.message}

Job: {self.job_name}
Step: {self.step_name}
Duration: {self.duration} seconds
Tasks run: {self.tasks_run}
"""


def add_run_arguments(run_parser: ArgumentParser):
    run_parser.add_argument(
        "--step",
        action="store",
        type=str,
        required=True,
        metavar="STEP_NAME",
        help="The name of the Step in the Job to run Tasks from.",
    )
    run_parser.add_argument(
        "--task-params",
        "-tp",
        action="append",
        nargs="*",
        type=str,
        metavar=("PARAM1=VALUE1 PARAM2=VALUE2"),
        help="Use these Task parameter sets to run the provided Step. Can be provided as a list of key-value pairs, or as a path to a JSON/YAML document prefixed with 'file://'. \
            Each non-file argument represents a single Task parameter set, as a list of Key=Value strings, to run a Task with. \
            Sessions will run one Task per non-file argument, and any Tasks defined in 'file://'-prefixed JSON or YAML documents.",
    )
    run_parser.add_argument(
        "--maximum-tasks",
        action="store",
        type=int,
        default=-1,
        help="The maximum number of Task parameter sets to run this Step with. If unset, the Session will run all of the Step's defined Tasks, or one Task per Task parameter set provided by '--task-params'.",
    )
    run_parser.add_argument(
        "--run-dependencies",
        action="store_const",
        const=True,
        help="Run the Step along with all of its transitive and direct dependencies.",
    )
    run_parser.add_argument(
        "--path-mapping-rules",
        action="store",
        type=str,
        help="The path mapping rules to apply to the template. Should be a path mapping definition according to "
        + "the 'pathmapping-1.0' schema. Can either be supplied as a string or as a path to a JSON/YAML document, "
        + "prefixed with 'file://'.",
    )


def _collect_required_steps(step_map: dict[str, Step], step: Step) -> list[Step]:
    """
    Recursively traverses through a Step's dependencies to create an ordered list of
    Steps to run in the local Session.
    """
    if step.stepEnvironments:
        # Currently, we only support running one local Session, so any Steps with Step-specific environments
        # must not depend on/be a dependency for other Steps.
        raise RuntimeError(
            f"ERROR: Step '{step.name}' has Step-level environments and cannot be run in the same local Session as the other dependencies."
        )

    if not step.dependencies:
        return [step]

    required_steps: list[Step] = []

    try:
        for dep in step.dependencies:
            dependency_name = dep.dependsOn
            # Collect transitive dependencies in the recursive call,
            # then remove duplicates
            collected = _collect_required_steps(step_map, step_map[dependency_name])
            required_steps += [new_step for new_step in collected if new_step not in required_steps]
    except KeyError:
        # This should technically raise a validation error when creating a Job,
        # but we check again here for thoroughness
        raise RuntimeError(
            f"ERROR: Dependency '{dependency_name}' in Step '{step.name}' is not an existing Step."
        )

    required_steps.append(step)

    return required_steps


def _run_local_session(
    *,
    job: Job,
    step_map: dict[str, Step],
    step: Step,
    maximum_tasks: int = -1,
    task_parameter_values: list[dict] = [],
    path_mapping_rules: Optional[list[PathMappingRule]],
    should_run_dependencies: bool = False,
    should_print_logs: bool = True,
) -> OpenJDCliResult:
    """
    Creates a Session object and listens for log messages to synchronously end the session.
    """

    dependencies: list[Step] = []
    try:
        if should_run_dependencies and step.dependencies:
            # Raises: RuntimeError
            dependencies = _collect_required_steps(step_map, step)[:-1]
    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    with LocalSession(
        job=job,
        session_id="sample_session",
        path_mapping_rules=path_mapping_rules,
        should_print_logs=should_print_logs,
    ) as session:
        session.initialize(
            dependencies=dependencies,
            step=step,
            task_parameter_values=task_parameter_values,
            maximum_tasks=maximum_tasks,
        )
        session.run()

        # Monitor the local Session state
        session.ended.wait()

    if session.failed:
        return OpenJDRunResult(
            status="error",
            message="Session ended with errors; see Task logs for details",
            job_name=job.name,
            step_name=step.name,
            duration=session.get_duration(),
            tasks_run=session.tasks_run,
            logs=session.get_log_messages(),
        )

    return OpenJDRunResult(
        status="success",
        message="Session ended successfully",
        job_name=job.name,
        step_name=step.name,
        duration=session.get_duration(),
        tasks_run=session.tasks_run,
        logs=session.get_log_messages(),
    )


@print_cli_result
def do_run(args: Namespace) -> OpenJDCliResult:
    """
    Given a Job template and a Step from that Job, generates the Job and runs Tasks from the Step.

    By default, all Tasks defined in the Step's parameter space will run in the Session. The user
    may specify a maximum number of Tasks to run as a command line option. They may also provide
    a list of Task parameter sets; the Session will run the Step with each of the provided parameter
    sets in sequence.
    """

    try:
        # Raises: RuntimeError
        sample_job = generate_job(args)

        task_params: list[dict] = []
        if args.task_params:
            task_params = get_task_params(args.task_params)

    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    path_mapping_rules: Optional[list[PathMappingRule]] = None
    if args.path_mapping_rules:
        if args.path_mapping_rules.startswith("file://"):
            filename = Path(args.path_mapping_rules.removeprefix("file://")).expanduser()
            with open(filename, encoding="utf8") as f:
                parsed_rules = json.load(f)
        else:
            parsed_rules = json.loads(args.path_mapping_rules)
        if parsed_rules.get("version", None) != "pathmapping-1.0":
            raise OpenJDCliResult(
                status="error",
                message="Path mapping rules must have a 'version' value of 'pathmapping-1.0'",
            )
        if not isinstance(parsed_rules.get("path_mapping_rules", None), list):
            raise OpenJDCliResult(
                status="error",
                message="Path mapping rules must contain  a list named 'path_mapping_rules'",
            )
        rules_list = parsed_rules.get("path_mapping_rules")
        path_mapping_rules = [PathMappingRule.from_dict(rule) for rule in rules_list]

    # Map Step names to Step objects so they can be easily accessed
    step_map = {step.name: step for step in sample_job.steps}

    if args.step in step_map:
        return _run_local_session(
            job=sample_job,
            step_map=step_map,
            step=step_map[args.step],
            task_parameter_values=task_params,
            maximum_tasks=args.maximum_tasks,
            path_mapping_rules=path_mapping_rules,
            should_run_dependencies=(args.run_dependencies),
            should_print_logs=(args.output == "human-readable"),
        )

    return OpenJDCliResult(
        status="error", message=f"Step '{args.step}' does not exist in Job '{sample_job.name}'."
    )
