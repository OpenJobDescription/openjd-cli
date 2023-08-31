# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace
import json

from .._common import OpenJDCliResult, print_cli_result
from ...model import SchemaVersion


def add_schema_arguments(schema_parser: ArgumentParser) -> None:
    schema_parser.add_argument(
        "--version",
        action="store",
        type=SchemaVersion,
        required=True,
        help="The specification version to return a JSON schema document for.",
    )


def _process_regex(target: dict) -> None:
    """
    Translates Python's language-specific regex into a JSON-compatible format.
    """

    if "pattern" in target and isinstance(target["pattern"], str):
        target["pattern"] = target["pattern"].replace("(?-m:", "(?:")
        target["pattern"] = target["pattern"].replace("\\Z", "$")

    for attr in target.keys():
        if isinstance(target[attr], dict):
            _process_regex(target[attr])


@print_cli_result
def do_get_schema(args: Namespace) -> OpenJDCliResult:
    """
    Uses Pydantic to convert the Open Job Description Job template model
    into a JSON schema document to compare in-development
    Job templates against.
    """

    if args.version == SchemaVersion.v2023_09:
        from ...model.v2023_09 import JobTemplate
    else:
        return OpenJDCliResult(
            status="error", message=f"ERROR: Cannot generate schema for version '{args.version}'."
        )

    schema_doc: dict = {}

    try:
        # The `schema` attribute will have to be updated if/when Pydantic
        # is updated to v2.
        # (AFAIK it can be replaced with `model_json_schema()`.)
        schema_doc = JobTemplate.schema()
        _process_regex(schema_doc)
    except Exception as e:
        return OpenJDCliResult(status="error", message=f"ERROR generating schema: {str(e)}")

    return OpenJDCliResult(status="success", message=json.dumps(schema_doc, indent=4))
