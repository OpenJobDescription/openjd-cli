# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .._common import add_common_arguments, CommonArgument, SubparserGroup
from ._check_command import add_check_arguments, do_check


def populate_argparser(subcommands: SubparserGroup) -> None:
    """Adds the `check` command and all of its arguments to the given parser."""
    check_parser = subcommands.add(
        "check",
        usage="openjd check JOB_TEMPLATE_PATH [arguments]",
        description="Given an Open Job Description template file, parse the file and run validation checks against it to ensure that it is correctly formed.",
    )

    # add all arguments through `add_common_arguments`
    add_common_arguments(check_parser, {CommonArgument.PATH})
    add_check_arguments(check_parser)
    check_parser.set_defaults(func=do_check)
