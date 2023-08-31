# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace

from .._common import read_template, OpenJDCliResult, print_cli_result


@print_cli_result
def do_check(args: Namespace) -> OpenJDCliResult:
    """Open a provided template file and check its schema for errors."""

    try:
        # Raises: RuntimeError
        filepath, _ = read_template(args)
    except RuntimeError as exc:
        return OpenJDCliResult(status="error", message=f"ERROR: {str(exc)}")

    return OpenJDCliResult(
        status="success", message=f"Template at '{str(filepath)}' passes validation checks."
    )
