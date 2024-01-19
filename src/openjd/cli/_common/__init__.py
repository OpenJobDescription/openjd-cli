# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace, _SubParsersAction
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import Callable, Literal
import json
import yaml
import os

from ._job_from_template import (
    job_from_template,
    get_job_params,
    get_task_params,
)
from ._validation_utils import get_doc_type, read_template
from openjd.model import DecodeValidationError, Job

__all__ = [
    "get_doc_type",
    "get_job_params",
    "get_task_params",
    "read_template",
    "validate_task_parameters",
]


class CommonArgument(Enum):
    """
    Used as literal options for which shared arguments
    a certain command uses.
    """

    PATH = "path"
    JOB_PARAMS = "job_params"


def add_common_arguments(
    parser: ArgumentParser, common_arg_options: set[CommonArgument] = set()
) -> None:
    """
    Adds arguments that are used across commands.
    Universal arguments for all commands are added first,
    followed by arguments that are common among certain
    commands, but not universal.
    """

    # Universal arguments for all commands
    parser.add_argument(
        "--output",
        choices=["human-readable", "json", "yaml"],
        default="human-readable",
        help="How to format the command's output.",
    )

    # Retain order in common arguments by
    # checking set membership in a well-known order
    if CommonArgument.PATH in common_arg_options:
        parser.add_argument(
            "path",
            type=Path,
            action="store",
            help="The path to the template file or Job Bundle to use.",
        )
    if CommonArgument.JOB_PARAMS in common_arg_options:
        parser.add_argument(
            "--job-param",
            "-p",
            dest="job_params",
            type=str,
            action="append",
            metavar=("KEY=VALUE, file://PATH_TO_PARAMS"),
            help="Use these Job parameters with the provided template. Can be provided as key-value pairs, or as path(s) to a JSON or YAML document prefixed with 'file://'.",
        )


class SubparserGroup:
    """
    Wraps the `_SubParsersAction` type from the `argparse` library
    so each subcommand can be created & populated in their own
    respective module.
    """

    group: _SubParsersAction

    def __init__(self, base: ArgumentParser, **kwargs):
        self.group = base.add_subparsers(**kwargs)

    def add(self, name: str, description: str, **kwargs) -> ArgumentParser:
        """
        Wraps the `add_parser` function so multiple modules can
        add subcommands to the same base parser.

        For our purposes, we only expose the `description` keyword, but other
        keywords used by `add_parser` can still be passed in and used.
        """
        return self.group.add_parser(name, **kwargs)


def generate_job(args: Namespace) -> Job:
    try:
        # Raises: RuntimeError, DecodeValidationError
        template_file, template = read_template(args)
        # Raises: RuntimeError
        return job_from_template(
            template,
            args.job_params if args.job_params else None,
            Path(os.path.abspath(template_file.parent)),
            Path(os.getcwd()),
        )
    except RuntimeError as rte:
        raise RuntimeError(f"ERROR generating Job: {str(rte)}")
    except DecodeValidationError as dve:
        raise RuntimeError(f"ERROR validating template: {str(dve)}")


@dataclass
class OpenJDCliResult(BaseException):
    """
    Denotes the result of a command, including its status (success/error)
    and an accompanying message.

    Commands that require more information in their results will subclass
    OpenJDCliResult to add more fields.
    """

    status: Literal["success", "error"]
    message: str

    def __str__(self) -> str:
        return self.message


def _asdict_omit_null(attrs: list) -> dict:
    """
    Retrieves a dataclass' attributes in a dictionary, omitting any fields with None or empty values.
    """

    return {attr: value for (attr, value) in attrs if value}


def print_cli_result(command: Callable[[Namespace], OpenJDCliResult]) -> Callable:
    """
    Takes the result of a command and formats the output according to the user's specification.
    Used to decorate the `do_<command>` functions for each command.
    """

    def format_results(args: Namespace) -> None:
        response = command(args)

        if args.output == "human-readable":
            print(str(response))
        else:
            if args.output == "json":
                print(json.dumps(asdict(response, dict_factory=_asdict_omit_null), indent=4))
            else:
                print(
                    yaml.safe_dump(
                        asdict(response, dict_factory=_asdict_omit_null), sort_keys=False
                    )
                )

        if response.status == "error":
            raise SystemExit(1)

    return format_results
