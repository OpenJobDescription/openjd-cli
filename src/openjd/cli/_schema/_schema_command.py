# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import ArgumentParser, Namespace
import json
from typing import Union

from .._common import OpenJDCliResult, print_cli_result
from openjd.model import SchemaVersion, JobTemplate, EnvironmentTemplate


def add_schema_arguments(schema_parser: ArgumentParser) -> None:
    allowed_values = [
        v.value
        for v in SchemaVersion
        if SchemaVersion.is_job_template(v) or SchemaVersion.is_environment_template(v)
    ]
    schema_parser.add_argument(
        "--version",
        action="store",
        type=SchemaVersion,
        required=True,
        help=f"The specification version to return a JSON schema document for. Allowed values: {', '.join(allowed_values)}",
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

    Template: Union[type[JobTemplate], type[EnvironmentTemplate]]
    if args.version == SchemaVersion.v2023_09:
        from openjd.model.v2023_09 import JobTemplate as Template
    elif args.version == SchemaVersion.ENVIRONMENT_v2023_09:
        from openjd.model.v2023_09 import EnvironmentTemplate as Template
    else:
        return OpenJDCliResult(
            status="error", message=f"ERROR: Cannot generate schema for version '{args.version}'."
        )

    schema_doc: dict = {}

    try:
        # The `schema` attribute will have to be updated if/when Pydantic
        # is updated to v2.
        # (AFAIK it can be replaced with `model_json_schema()`.)
        schema_doc = Template.schema()
        _process_regex(schema_doc)
    except Exception as e:
        return OpenJDCliResult(status="error", message=f"ERROR generating schema: {str(e)}")

    return OpenJDCliResult(status="success", message=json.dumps(schema_doc, indent=4))
