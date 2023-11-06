# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser

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
