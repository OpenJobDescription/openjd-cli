# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .._common import add_common_arguments, CommonArgument, SubparserGroup
from ._summary_command import add_summary_arguments, do_summary


def populate_argparser(subcommands: SubparserGroup) -> None:
    """Adds the `summary` command's arguments to the given subcommand parser."""
    summary_parser = subcommands.add(
        "summary",
        usage="openjd summary JOB_TEMPLATE_PATH [arguments]",
        description="Print summary information about a Job Template.",
    )

    add_common_arguments(summary_parser, {CommonArgument.PATH, CommonArgument.JOB_PARAMS})
    add_summary_arguments(summary_parser)
    summary_parser.set_defaults(func=do_summary)
