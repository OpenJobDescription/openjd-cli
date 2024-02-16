# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace
from dataclasses import dataclass
from pathlib import Path
import json
from typing import Optional
import re
import logging

from ._local_session._session_manager import LocalSession, LogEntry
from .._common import (
    OpenJDCliResult,
    generate_job,
    get_params_from_file,
    print_cli_result,
    read_environment_template,
)
from openjd.model import (
    DecodeValidationError,
    EnvironmentTemplate,
    Job,
    Step,
    StepParameterSpaceIterator,
)
from openjd.sessions import PathMappingRule, LOG


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
    group = run_parser.add_mutually_exclusive_group()
    group.add_argument(
        "--task-param",
        "-tp",
        action="append",
        type=str,
        dest="task_params",
        metavar="PARAM=VALUE",
        help=(
            "This argument instructs the command to run a single task in a Session with the given value for one of the task parameters "
            "defined for the Step. The option must be provided once for each task parameter defined for the Step, with each instance "
            "providing the value for a different task parameter. Mutually exclusive with --tasks and --maximum-tasks."
        ),
    )
    group.add_argument(
        "--tasks",
        action="store",
        type=str,
        dest="tasks",
        metavar='file://tasks.json OR file://tasks.yaml OR [{"Param": "Value1", ...}, {"Param": "Value2", ...}]',
        help=(
            "This argument instructs the command to run one or more tasks for the Step in a Session. The argument must be either "
            "the filename of a JSON or YAML file containing an array of maps from task parameter name to value; or an inlined "
            "JSON string of the same. Mutually exclusive with --task-param/-tp and --maximum-tasks."
        ),
    )
    group.add_argument(
        "--maximum-tasks",
        action="store",
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
    run_parser.add_argument(
        "--environment",
        "--env",
        dest="environments",
        action="append",
        type=str,
        metavar="<path-to-JSON/YAML-file> [<path-to-JSON/YAML-file>] ...",
        help="Apply the given environments to the Session in the order given.",
    )
    run_parser.add_argument(
        "--preserve",
        action="store_const",
        const=True,
        default=False,
        help="Do not automatically delete the Session's Working Directory when complete.",
    )
    run_parser.add_argument(
        "--verbose",
        action="store_const",
        const=True,
        default=False,
        help="Enable verbose logging while running the Session.",
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
        error_msg = "Found the following errors collecting Task parameters:"
        for error in error_list:
            error_msg += f"\n- {error}"
        raise RuntimeError(error_msg)

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
    #  3) [TODO] That the given parameter set is actually in the parameter space of the Step.
    #       - We need openjd.model.StepParameterSpaceIterator to have a membership test first to be able to do
    #         this last check.

    # Collect the names of all of the task parameters defined in the step.
    if step.parameterSpace is not None:
        parameter_space = StepParameterSpaceIterator(space=step.parameterSpace)
        task_parameter_names: set[str] = set(parameter_space.names)
    else:
        task_parameter_names = set[str]()

    error_list = list[str]()
    for i, parameter_set in enumerate(task_params):
        defined_params = set(parameter_set.keys())
        if defined_params == task_parameter_names:
            continue
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

    if error_list:
        error_msg = "Errors defining task parameter values:\n - "
        error_msg += "\n - ".join(error_list)
        raise RuntimeError(error_msg)


def _run_local_session(
    *,
    job: Job,
    step_map: dict[str, Step],
    step: Step,
    maximum_tasks: int = -1,
    task_parameter_values: list[dict] = [],
    environments: Optional[list[EnvironmentTemplate]] = None,
    path_mapping_rules: Optional[list[PathMappingRule]],
    should_run_dependencies: bool = False,
    should_print_logs: bool = True,
    retain_working_dir: bool = False,
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
        environments=environments,
        should_print_logs=should_print_logs,
        retain_working_dir=retain_working_dir,
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

    preserved_message: str = ""
    if retain_working_dir:
        preserved_message = (
            f"\nWorking directory preserved at: {str(session._inner_session.working_directory)}"
        )
    if session.failed:
        return OpenJDRunResult(
            status="error",
            message="Session ended with errors; see Task logs for details" + preserved_message,
            job_name=job.name,
            step_name=step.name,
            duration=session.get_duration(),
            tasks_run=session.tasks_run,
            logs=session.get_log_messages(),
        )

    return OpenJDRunResult(
        status="success",
        message="Session ended successfully" + preserved_message,
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
        if parsed_rules.get("version", None) != "pathmapping-1.0":
            return OpenJDCliResult(
                status="error",
                message="Path mapping rules must have a 'version' value of 'pathmapping-1.0'",
            )
        if not isinstance(parsed_rules.get("path_mapping_rules", None), list):
            return OpenJDCliResult(
                status="error",
                message="Path mapping rules must contain a list named 'path_mapping_rules'",
            )
        rules_list = parsed_rules.get("path_mapping_rules")
        path_mapping_rules = [PathMappingRule.from_dict(rule) for rule in rules_list]

    if args.verbose:
        LOG.setLevel(logging.DEBUG)

    try:
        # Raises: RuntimeError
        the_job = generate_job(args)

        # Map Step names to Step objects so they can be easily accessed
        step_map = {step.name: step for step in the_job.steps}

        if args.step not in step_map:
            raise RuntimeError(
                f"No Step with name '{args.step}' is defined in the given Job Template."
            )

        task_params: list[dict[str, str]] = []
        if args.task_params:
            task_params = [_process_task_params(args.task_params)]
        elif args.tasks:
            task_params = _process_tasks(args.tasks)

        _validate_task_params(step_map[args.step], task_params)

    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    return _run_local_session(
        job=the_job,
        step_map=step_map,
        step=step_map[args.step],
        task_parameter_values=task_params,
        maximum_tasks=args.maximum_tasks,
        environments=environments,
        path_mapping_rules=path_mapping_rules,
        should_run_dependencies=(args.run_dependencies),
        should_print_logs=(args.output == "human-readable"),
        retain_working_dir=args.preserve,
    )
