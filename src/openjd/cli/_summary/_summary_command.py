# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace

from ._summary_output import output_summary_result
from .._common import (
    OpenJDCliResult,
    generate_job,
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


@print_cli_result
def do_summary(args: Namespace) -> OpenJDCliResult:
    """
    Given a Job Template and applicable parameters, generates a Job and outputs information about it.
    """
    try:
        # Raises: RuntimeError
        sample_job = generate_job(args)
    except RuntimeError as rte:
        return OpenJDCliResult(status="error", message=str(rte))

    return output_summary_result(sample_job, args.step)
