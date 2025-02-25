# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from ._run_command import add_run_arguments, do_run
from .._common import add_common_arguments, CommonArgument, SubparserGroup


def populate_argparser(subcommands: SubparserGroup) -> None:
    """Adds the `run` command and all of its arguments to the given parser."""
    run_parser = subcommands.add(
        "run",
        description="Takes a Job Template and runs the entire job or a selected Step from the job.",
        usage="openjd run JOB_TEMPLATE_PATH [arguments]",
    )
    add_common_arguments(run_parser, {CommonArgument.PATH, CommonArgument.JOB_PARAMS})
    add_run_arguments(run_parser)
    run_parser.set_defaults(func=do_run)
