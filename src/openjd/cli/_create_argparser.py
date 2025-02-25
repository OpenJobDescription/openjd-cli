# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser
import sys
import traceback
from typing import Optional

from ._common import SubparserGroup

from ._check import populate_argparser as populate_check_subparser
from ._summary import populate_argparser as populate_summary_subparser
from ._run import populate_argparser as populate_run_subparser
from ._schema import populate_argparser as populate_schema_subparser


# Our CLI subcommand construction requires that all leaf subcommands define a default
# 'func' property which is a Callable[[],None] that implements the subcommand.
# After parsing, we call that `func` argument of the resulting args object.


def create_argparser() -> ArgumentParser:
    """Generate the root argparser for the CLI"""
    parser = ArgumentParser(prog="openjd", usage="openjd <command> [arguments]")
    parser.set_defaults(func=lambda _: parser.print_help())
    subcommands = SubparserGroup(
        parser,
        title="commands",
    )
    populate_check_subparser(subcommands)
    populate_summary_subparser(subcommands)
    populate_run_subparser(subcommands)
    populate_schema_subparser(subcommands)
    return parser


def main(arg_list: Optional[list[str]] = None) -> None:
    """Main function for invoking the CLI"""
    parser = create_argparser()

    if arg_list is None:
        arg_list = sys.argv[1:]

    args = parser.parse_args(arg_list)
    try:
        # Raises:
        #  SystemExit - on failure
        args.func(args)
    except Exception as exc:
        print(f"ERROR: {str(exc)}", file=sys.stderr)
        traceback.print_exc()
        sys.exit(1)
