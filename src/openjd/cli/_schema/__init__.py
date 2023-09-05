# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from .._common import SubparserGroup, add_common_arguments
from ._schema_command import add_schema_arguments, do_get_schema


def populate_argparser(subcommands: SubparserGroup) -> None:
    """
    Adds the `schema` command to the given parser.
    """
    schema_parser = subcommands.add(
        "schema",
        description="Returns a JSON Schema document for the Job template model.",
    )
    add_common_arguments(schema_parser, set())
    add_schema_arguments(schema_parser)
    schema_parser.set_defaults(func=do_get_schema)
