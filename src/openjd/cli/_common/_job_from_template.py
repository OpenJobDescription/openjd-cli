# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import TYPE_CHECKING, Optional, Union
import yaml

from ._validation_utils import get_doc_type
from openjd.model import (
    DecodeValidationError,
    DocumentType,
    EnvironmentTemplate,
    Job,
    JobParameterValues,
    JobTemplate,
    create_job_with_symbol_tables,
    preprocess_job_parameters,
)

if TYPE_CHECKING:
    # Only for annotations: `openjd.expr` is a facade over the native
    # extension, and importing the CLI must not load it. The tables the model
    # hands back are already instances of this type, so nothing here
    # constructs one.
    from openjd.expr import SerializedSymbolTable


def get_params_from_file(parameter_string: str) -> Union[dict, list]:
    """
    Resolves the supplied Job Parameter filepath into a JSON object with its contents.

    Raises: RuntimeError if the file can't be opened
    """
    parameter_file = Path(parameter_string.removeprefix("file://")).expanduser()

    if not parameter_file.exists():
        raise RuntimeError(f"Provided parameter file '{str(parameter_file)}' does not exist.")
    if not parameter_file.is_file():
        raise RuntimeError(f"Provided parameter file '{str(parameter_file)}' is not a file.")

    # Raises: RuntimeError
    doc_type = get_doc_type(parameter_file)

    try:
        parameter_string = parameter_file.read_text()
    except OSError:
        raise RuntimeError(f"Could not open parameter file '{str(parameter_file)}'.")

    try:
        if doc_type == DocumentType.YAML:
            # Raises: YAMLError
            parameters = yaml.safe_load(parameter_string)
        else:
            # Raises: JSONDecodeError
            parameters = json.loads(parameter_string)
    except (yaml.YAMLError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Parameter file '{str(parameter_file)}' is formatted incorrectly: {str(exc)}"
        )

    return parameters


def get_job_params(parameter_args: Optional[list[str]]) -> dict:
    """
    Resolves Job Parameters from a list of command-line arguments.
    Arguments may be a filepath or a string with format 'Key=Value'.

    Raises: RuntimeError if the provided Parameters are formatted incorrectly or can't be opened
    """
    parameter_dict: dict = {}

    for arg in parameter_args or []:
        arg = arg.strip()
        # Case 1: Provided argument is a filepath
        if arg.startswith("file://"):
            # Raises: RuntimeError
            parameters = get_params_from_file(arg)

            if isinstance(parameters, dict):
                parameter_dict.update(parameters)
            else:
                raise RuntimeError(f"Job parameter file '{arg}' should contain a dictionary.")

        # Case 2: Provided as a JSON string
        elif re.match("^{(.*)}$", arg):
            try:
                # Raises: JSONDecodeError
                parameters = json.loads(arg)
            except (json.JSONDecodeError, TypeError):
                raise RuntimeError(
                    f"Job parameter string ('{arg}') not formatted correctly. It must be key=value pairs, inline JSON, or a path to a JSON or YAML document prefixed with 'file://'."
                )
            if not isinstance(parameters, dict):
                # This should never happen. Including it out of a sense of paranoia.
                raise RuntimeError(
                    f"Job parameter ('{arg}') must contain a dictionary mapping job parameters to their value."
                )
            parameter_dict.update(parameters)

        # Case 3: Provided argument is a Key=Value string
        elif regex_match := re.match("^([^=]+)=(.*)$", arg):
            parameter_dict.update({regex_match[1]: regex_match[2]})

        else:
            raise RuntimeError(
                f"Job parameter string ('{arg}') not formatted correctly. It must be key=value pairs, inline JSON, or a path to a JSON or YAML document prefixed with 'file://'."
            )

    return parameter_dict


def job_from_template(
    template: JobTemplate,
    environments: list[EnvironmentTemplate],
    parameter_args: list[str] | None,
    job_template_dir: Path,
    current_working_dir: Path,
) -> tuple[Job, JobParameterValues, dict[str, "SerializedSymbolTable"]]:
    """
    Given a decoded Job Template and a user-input parameter dictionary,
    generates a Job object, the parameter values for running the job, and the
    per-step resolved symbol tables, keyed by step name.

    A step's template-scope `let` bindings (RFC 0005 §3.6) are evaluated once
    here, at job creation, and their resolved values reach a session only
    through those tables -- neither the model nor the session re-derives them
    from the source expressions. Sessions for a step must therefore be given
    `step_symbol_tables[step.name]`, or the step's `let` produces no bindings
    at all.

    Raises: RuntimeError if parameters are an unsupported type or don't correspond to the template
    """
    parameter_dict = get_job_params(parameter_args)

    try:
        parameter_values = preprocess_job_parameters(
            job_template=template,
            job_parameter_values=parameter_dict,
            job_template_dir=job_template_dir,
            current_working_dir=current_working_dir,
            environment_templates=environments,
        )
    except ValueError as ve:
        raise RuntimeError(str(ve))

    try:
        # `create_job_with_symbol_tables` returns the same Job that
        # `create_job` does; it additionally returns the symbol tables that
        # instantiation built instead of discarding them.
        created = create_job_with_symbol_tables(
            job_template=template,
            job_parameter_values=parameter_values,
            environment_templates=environments,
        )
        return (created.job, parameter_values, created.step_symbol_tables)
    except DecodeValidationError as dve:
        raise RuntimeError(f"Could not generate Job from template and parameters: {str(dve)}")
