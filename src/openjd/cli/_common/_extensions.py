# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser
from typing import Optional

# This is the list of Open Job Description extensions with implemented support
SUPPORTED_EXTENSIONS = ["TASK_CHUNKING", "REDACTED_ENV_VARS"]


def add_extensions_argument(run_parser: ArgumentParser):
    run_parser.add_argument(
        "--extensions",
        help=f"A comma-separated list of Open Job Description extension names to enable. Defaults to all that are implemented: {','.join(SUPPORTED_EXTENSIONS)}",
    )


def process_extensions_argument(extensions: Optional[str]) -> list[str]:
    """Process the comma-separated extensions argument and return a list of supported extensions."""

    # If the option is not provided, default to all the supported extensions.
    if extensions is None:
        return SUPPORTED_EXTENSIONS

    extensions_list = [
        extension.strip().upper() for extension in extensions.split(",") if extension.strip() != ""
    ]

    unsupported_extensions = set(extensions_list) - set(SUPPORTED_EXTENSIONS)
    if unsupported_extensions:
        raise ValueError(
            f"Unsupported Open Job Description extension(s): {', '.join(sorted(unsupported_extensions))}"
        )

    return extensions_list
