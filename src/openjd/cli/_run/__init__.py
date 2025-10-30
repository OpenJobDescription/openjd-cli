# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from ._run_command import add_run_arguments, do_run
from ._help_formatter import JobTemplateHelpAction
from .._common import add_common_arguments, CommonArgument, SubparserGroup


def populate_argparser(subcommands: SubparserGroup) -> None:
    """Adds the `run` command and all of its arguments to the given parser."""
    run_parser = subcommands.add(
        "run",
        description="Takes a Job Template and runs the entire job or a selected Step from the job.",
        usage="openjd run JOB_TEMPLATE_PATH [arguments]",
        add_help=False,  # Disable default help to use custom action
    )
    add_common_arguments(run_parser, {CommonArgument.PATH, CommonArgument.JOB_PARAMS})
    add_run_arguments(run_parser)

    # Add custom help action that provides context-aware help based on job template
    run_parser.add_argument(
        "-h",
        "--help",
        action=JobTemplateHelpAction,
        help="Show help message. When a job template path is provided, displays job-specific help including parameter definitions.",
    )

    run_parser.set_defaults(func=do_run)
