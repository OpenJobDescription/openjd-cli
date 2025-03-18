# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace

from ._summary_output import output_summary_result
from .._common import (
    add_extensions_argument,
    OpenJDCliResult,
    generate_job,
    process_extensions_argument,
    print_cli_result,
)


def add_summary_arguments(summary_parser: ArgumentParser) -> None:
    # `step` is *technically* a shared argument,
    # but the help string and `required` attribute are
    # different among commands
    summary_parser.add_argument(
        "--step",
        action="store",
        type=str,
        metavar="STEP_NAME",
        help="Prints information about the Step with this name within the Job Template.",
    )
    add_extensions_argument(summary_parser)


@print_cli_result
def do_summary(args: Namespace) -> OpenJDCliResult:
    """
    Given a Job Template and applicable parameters, generates a Job and outputs information about it.
    """
    extensions = process_extensions_argument(args.extensions)

    try:
        # Raises: RuntimeError
        sample_job, _ = generate_job(args, supported_extensions=extensions)
    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    return output_summary_result(sample_job, args.step)
