# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Iterable, Optional
import re
import logging
import time

from ._local_session._session_manager import (
    LocalSession,
    LocalSessionFailed,
    LogEntry,
    LoggingTimestampFormat,
)
from .._common import (
    add_extensions_argument,
    OpenJDCliResult,
    generate_job,
    get_params_from_file,
    process_extensions_argument,
    print_cli_result,
    read_environment_template,
)
from openjd.model import (
    DecodeValidationError,
    EnvironmentTemplate,
    Job,
    JobParameterValues,
    Step,
    StepDependencyGraph,
    StepParameterSpaceIterator,
    ParameterValue,
    ParameterValueType,
    RevisionExtensions,
    SpecificationRevision,
    TaskParameterSet,
)
from openjd.sessions import PathMappingRule, LOG


@dataclass
class OpenJDRunResult(OpenJDCliResult):
    """
    Holds information and Task logs from a local Session.
    """

    job_name: str
    step_name: Optional[str]
    duration: float
    chunks_run: int
    logs: list[LogEntry]

    def __str__(self) -> str:
        step_message = ""
        if self.step_name is not None:
            step_message = f"Step: {self.step_name}\n"
        return f"""
--- Results of local session ---

{self.message}

Job: {self.job_name}
{step_message}Duration: {self.duration} seconds
Chunks run: {self.chunks_run}
"""


def add_run_arguments(run_parser: ArgumentParser):
    run_parser.add_argument(
        "--step",
        type=str,
        metavar="STEP_NAME",
        help="The name of the Step in the Job to run Tasks from.",
    )
    group = run_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--task-param",
        "-tp",
        action="append",
        dest="task_params",
        metavar="PARAM=VALUE",
        help=(
            "This argument instructs the command to run a single task or chunk of tasks in a Session with the given value for "
            "one of the task parameters defined for the Step. The option must be provided once for each task parameter defined "
            "for the Step, with each instance providing the value for a different task parameter. Mutually exclusive with "
            "--tasks and --maximum-tasks."
        ),
    )
    group.add_argument(
        "--tasks",
        metavar='file://tasks.json OR file://tasks.yaml OR [{"Param": "Value1", ...}, {"Param": "Value2", ...}]',
        help=(
            "This argument instructs the command to run one or more tasks/chunks of tasks for the Step in a Session. "
            "The argument must be either the filename of a JSON or YAML file containing an array of maps from task parameter "
            "name to value; or an inlined JSON string of the same. Mutually exclusive with --task-param/-tp and --maximum-tasks."
        ),
    )
    group.add_argument(
        "--maximum-tasks",
        type=int,
        default=-1,
        help=(
            "This argument instructs the command to run at most this many Tasks for the Step in the Session. If neither this "
            "argument, --task-param/-tp, nor --tasks are provided then the Session will run all of the selected Step's Tasks "
            "in the Session. Mutually exclusive with --task-param/-tp and --tasks."
        ),
    )
    run_parser.add_argument(
        "--run-dependencies",
        action="store_true",
        help="Run the Step along with all of its transitive and direct dependencies.",
    )
    run_parser.add_argument(
        "--no-run-dependencies",
        action="store_false",
        dest="run_dependencies",
        help="Run the Step alone without dependencies.",
    )
    run_parser.add_argument(
        "--path-mapping-rules",
        help="The path mapping rules to apply to the template. Should be a path mapping definition according to "
        + "the 'pathmapping-1.0' schema. Can either be supplied as a string or as a path to a JSON/YAML document, "
        + "prefixed with 'file://'.",
    )
    run_parser.add_argument(
        "--environment",
        "--env",
        dest="environments",
        action="append",
        metavar="<path-to-JSON/YAML-file> [<path-to-JSON/YAML-file>] ...",
        help="Apply the given environments to the Session in the order given.",
    )
    run_parser.add_argument(
        "--preserve",
        action="store_true",
        default=False,
        help="Do not automatically delete the Session's Working Directory when complete.",
    )
    run_parser.add_argument(
        "--verbose",
        action="store_true",
        default=False,
        help="Enable verbose logging while running the Session.",
    )
    run_parser.add_argument(
        "--timestamp-format",
        choices=["relative", "local", "utc"],
        default="relative",
        help="How to format the log output timestamps when running the job.",
    )
    add_extensions_argument(run_parser)


def _collect_dependency_steps(step_map: dict[str, Step], step: Step) -> list[Step]:
    """
    Recursively traverses through a Step's dependencies to create an ordered list of
    Steps to run in the local Session. Does not include the specified step.
    """
    if not step.dependencies:
        return []

    dependency_steps: list[Step] = []
    visited_step_names: set[str] = set()

    for dep in step.dependencies:
        dependency_name = dep.dependsOn
        if dependency_name not in visited_step_names:
            visited_step_names.add(dependency_name)
            # Collect transitive dependencies in the recursive call, then filter any that were previously visited
            transitive_deps = _collect_dependency_steps(step_map, step_map[dependency_name])
            dependency_steps.extend(
                new_step for new_step in transitive_deps if new_step.name not in visited_step_names
            )
            dependency_steps.append(step_map[dependency_name])
            visited_step_names.update(new_step.name for new_step in transitive_deps)

    return dependency_steps


def _process_task_params(arguments: list[str]) -> dict[str, str]:
    """
    Retrieves a single Task parameter set from the user-provided --task-param option.

    Args:
        argument (list[str]): Each item is the definition of a single task parameter's
            value for the task that is expected to be of the form "ParamName=Value" (we
            do validate that the form has been used in this function).

    Returns: A dictionary representing the task parameter set for a single task. All
       values are represented as strings regardless of the parameter's defined type
      (types are resolved later by the `sessions` module).

    Raises:
        RuntimeError if any arguments do not match the required pattern
    """
    parameter_set = dict[str, str]()

    error_list: list[str] = []
    for arg in arguments:
        arg = arg.lstrip()
        if regex_match := re.match("([^=]+)=(.+)", arg):
            param, value = regex_match[1], regex_match[2]
            if parameter_set.get(param) is not None:
                error_list.append(f"Task parameter '{param}' has been defined more than once.")
            else:
                parameter_set[param] = value
            pass
        else:
            error_list.append(
                f"Task parameter '{arg}' defined incorrectly. Expected '<NAME>=<VALUE>' format."
            )

    if error_list:
        error_msgs = "".join(f"\n - {error}" for error in error_list)
        raise RuntimeError("Found the following errors collecting Task parameters:" + error_msgs)

    return parameter_set


def _process_tasks(argument: str) -> list[dict[str, str]]:
    """
    Retrieves a list of parameter sets from the user-provided --tasks argument on the command-line.

    Args:
        argument (str): The definition of the collection of task parameter sets to run in the Session.
            Correct user-input must of one of the following forms (we validate that here):
                - file://<filename>.[json|yaml]
                  - The file contains a JSON/YAML document that defines an array of parameter sets. Each
                    parameter set is defined as a mapping from parameter name to parameter value.
                - <JSON-encoded string>
                    - The string contains a JSON document that defines an array of parameter sets. Each
                      parameter set is defined as a mapping from parameter name to parameter value.

    Returns:
        list[dict[str,str]]: Each dictionary representing the task parameter set for a single task.
            All values are represented as strings regardless of the parameter's defined type
            (types are resolved later by the `sessions` module).

    Raises:
        RuntimeError if any arguments do not match the required pattern, or fail to parse
    """
    argument = argument.strip()
    if argument.startswith("file://"):
        # Raises: RuntimeError
        parameter_sets = get_params_from_file(argument)
    else:
        try:
            parameter_sets = json.loads(argument)
        except (json.JSONDecodeError, TypeError):
            raise RuntimeError(
                "--task argument must be a JSON encoded list of maps or a string with the file:// prefix."
            )

    # Ensure that the type is what we expected -- a list[dict[str,str]]
    if not isinstance(parameter_sets, list):
        raise RuntimeError(
            "--task argument must be a list of maps from string to string when decoded."
        )
    for item in parameter_sets:
        if not isinstance(item, dict):
            raise RuntimeError(
                "--task argument must be a list of maps from string to string when decoded."
            )
        for param, value in item.items():
            if not isinstance(value, (str, int, float)):
                raise RuntimeError(
                    "--task argument must be a list of maps from string to string when decoded."
                )
            item[param] = str(value)

    return parameter_sets


def _validate_task_params(step: Step, task_params: list[dict[str, str]]) -> None:
    # For each task parameter set, verify:
    #  1) There are no parameters defined that don't exist in the template.
    #  2) That all parameters that are defined in the Step are defined in the parameter set.
    #  3) That the given parameter set is actually in the parameter space of the Step.

    # Collect the names of all of the task parameters defined in the step.
    param_space_iter = StepParameterSpaceIterator(space=step.parameterSpace)
    task_parameter_names: set[str] = set(param_space_iter.names)

    error_list = list[str]()
    for i, parameter_set in enumerate(task_params):
        defined_params = set(parameter_set.keys())
        extra_names = defined_params.difference(task_parameter_names)
        missing_names = task_parameter_names.difference(defined_params)
        if extra_names:
            error_list.append(
                f"Task {i} defines unknown parameters: {', '.join(sorted(extra_names))}"
            )
        if missing_names:
            error_list.append(
                f"Task {i} is missing values for parameters: {', '.join(sorted(missing_names))}"
            )
        if not (extra_names or missing_names):
            params = {
                name: ParameterValue(
                    type=ParameterValueType(
                        step.parameterSpace.taskParameterDefinitions[name].type  # type: ignore
                    ),
                    value=parameter_set[name],
                )
                for name in task_parameter_names
            }
            try:
                param_space_iter.validate_containment(params)
            except ValueError as e:
                error_list.append(f"Task {i}: {e}")
    if error_list:
        error_msg = "Errors defining task parameter values:\n - "
        error_msg += "\n - ".join(error_list)
        raise RuntimeError(error_msg)


def _run_local_session(
    *,
    job: Job,
    job_parameter_values: JobParameterValues,
    step_list: list[Step],
    selected_step: Optional[Step],
    timestamp_format: LoggingTimestampFormat,
    maximum_tasks: int = -1,
    task_parameter_values: Iterable[TaskParameterSet],
    environments: Optional[list[EnvironmentTemplate]] = None,
    path_mapping_rules: Optional[list[PathMappingRule]],
    should_print_logs: bool = True,
    retain_working_dir: bool = False,
    revision_extensions: RevisionExtensions = RevisionExtensions(
        spec_rev=SpecificationRevision.v2023_09, supported_extensions=[]
    ),
) -> OpenJDCliResult:
    """
    Creates a Session object and listens for log messages to synchronously end the session.
    """

    try:
        start_seconds = time.perf_counter()

        step_name = ""
        with LocalSession(
            job=job,
            job_parameter_values=job_parameter_values,
            timestamp_format=timestamp_format,
            session_id="CLI-session",
            path_mapping_rules=path_mapping_rules,
            environments=[env.environment for env in environments] if environments else [],
            should_print_logs=should_print_logs,
            retain_working_dir=retain_working_dir,
            revision_extensions=revision_extensions,
        ) as session:
            for dep_step in step_list:
                step_name = dep_step.name
                session.run_step(dep_step)
            if selected_step:
                step_name = selected_step.name
                session.run_step(
                    selected_step,
                    task_parameters=task_parameter_values,
                    maximum_tasks=maximum_tasks,
                )
        duration = time.perf_counter() - start_seconds
    except LocalSessionFailed:
        duration = time.perf_counter() - start_seconds
        session = None

    preserved_message: str = ""
    if retain_working_dir and session is not None:
        preserved_message = (
            f"\nWorking directory preserved at: {str(session._openjd_session.working_directory)}"
        )

    if session is None or session.failed:
        return OpenJDRunResult(
            status="error",
            message="Session ended with errors; see Task logs for details" + preserved_message,
            job_name=job.name,
            step_name=step_name,
            duration=duration,
            chunks_run=0 if session is None else session.task_run_count,
            logs=[] if session is None else session.get_log_messages(),
        )

    return OpenJDRunResult(
        status="success",
        message="Session ended successfully" + preserved_message,
        job_name=job.name,
        step_name=selected_step.name if selected_step else None,
        duration=duration,
        chunks_run=session.task_run_count,
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

    extensions = process_extensions_argument(args.extensions)

    environments: list[EnvironmentTemplate] = []
    if args.environments:
        for env in args.environments:
            filename = Path(env).expanduser()
            try:
                # Raises: RuntimeError, DecodeValidationError
                template = read_environment_template(filename)
                environments.append(template)
            except (RuntimeError, DecodeValidationError) as e:
                return OpenJDCliResult(status="error", message=str(e))

    path_mapping_rules: Optional[list[PathMappingRule]] = None
    if args.path_mapping_rules:
        if args.path_mapping_rules.startswith("file://"):
            filename = Path(args.path_mapping_rules.removeprefix("file://")).expanduser()
            with open(filename, encoding="utf8") as f:
                parsed_rules = json.load(f)
        else:
            parsed_rules = json.loads(args.path_mapping_rules)
        if not isinstance(parsed_rules, dict):
            return OpenJDCliResult(
                status="error",
                message="Path mapping rules must be an object with 'version' and 'path_mapping_rules' fields",
            )
        if parsed_rules.get("version", None) != "pathmapping-1.0":
            return OpenJDCliResult(
                status="error",
                message="Path mapping rules must have a 'version' value of 'pathmapping-1.0'",
            )
        rules_list = parsed_rules.get("path_mapping_rules")
        if not isinstance(rules_list, list):
            return OpenJDCliResult(
                status="error",
                message="Path mapping rules must contain a list named 'path_mapping_rules'",
            )
        path_mapping_rules = [PathMappingRule.from_dict(rule) for rule in rules_list]

    if args.verbose:
        LOG.setLevel(logging.DEBUG)

    try:
        # Raises: RuntimeError
        the_job, job_parameter_values = generate_job(
            args, environments, supported_extensions=extensions
        )

        # Map Step names to Step objects so they can be easily accessed
        step_map = {step.name: step for step in the_job.steps}

        if args.step is not None:
            # If a step name was provided
            selected_step = step_map.get(args.step)
            if selected_step is None:
                raise RuntimeError(
                    f"No Step with name '{args.step}' is defined in the given Job Template."
                )
        else:
            if len(the_job.steps) == 1:
                # If the job has only one step, act as if its name was provided
                selected_step = the_job.steps[0]
            else:
                selected_step = None
                if args.task_params or args.tasks:
                    raise RuntimeError(
                        "Providing task parameters requires a specified step or a job with a single step.\n"
                        + f"{len(the_job.steps)} steps: {[step.name for step in the_job.steps]}."
                    )

        task_params: list[dict[str, str]] = []
        if args.task_params:
            task_params = [_process_task_params(args.task_params)]
        elif args.tasks:
            task_params = _process_tasks(args.tasks)

        if selected_step and task_params:
            _validate_task_params(selected_step, task_params)

            task_parameter_values: Iterable[TaskParameterSet] = [
                {
                    name: ParameterValue(
                        type=ParameterValueType(
                            selected_step.parameterSpace.taskParameterDefinitions[name].type  # type: ignore
                        ),
                        value=value,
                    )
                    for name, value in params.items()
                }
                for params in task_params
            ]
        elif selected_step:
            task_parameter_values = StepParameterSpaceIterator(space=selected_step.parameterSpace)
        else:
            task_parameter_values = []

    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    step_list: list[Step] = []
    try:
        if selected_step is None:
            # If no step was selected, topologically sort and run all the steps
            step_graph = StepDependencyGraph(job=the_job)
            step_list = step_graph.topo_sorted()
        elif args.run_dependencies and selected_step.dependencies:
            # Collect the dependencies of the selected step
            step_list = _collect_dependency_steps(step_map, selected_step)
    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    # Create a RevisionExtensions object with the default specification version and enabled extensions
    # We use the default v2023_09 since that's what we're currently supporting
    revision_extensions = RevisionExtensions(
        spec_rev=the_job.revision, supported_extensions=extensions
    )

    return _run_local_session(
        job=the_job,
        job_parameter_values=job_parameter_values,
        step_list=step_list,
        selected_step=selected_step,
        task_parameter_values=task_parameter_values,
        timestamp_format=LoggingTimestampFormat(args.timestamp_format),
        maximum_tasks=args.maximum_tasks,
        environments=environments,
        path_mapping_rules=path_mapping_rules,
        should_print_logs=(args.output == "human-readable"),
        retain_working_dir=args.preserve,
        revision_extensions=revision_extensions,
    )
