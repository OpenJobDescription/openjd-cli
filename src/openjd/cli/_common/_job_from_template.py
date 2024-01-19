# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Union
import yaml

from ._validation_utils import get_doc_type
from openjd.model import (
    DecodeValidationError,
    DocumentType,
    Job,
    JobTemplate,
    create_job,
    preprocess_job_parameters,
)


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


def get_job_params(parameter_args: list[str]) -> dict:
    """
    Resolves Job Parameters from a list of command-line arguments.
    Arguments may be a filepath or a string with format 'Key=Value'.

    Raises: RuntimeError if the provided Parameters are formatted incorrectly or can't be opened
    """
    parameter_dict: dict = {}
    for arg in parameter_args:
        # Case 1: Provided argument is a filepath
        if arg.startswith("file://"):
            # Raises: RuntimeError
            parameters = get_params_from_file(arg)

            if isinstance(parameters, dict):
                parameter_dict.update(parameters)
            else:
                raise RuntimeError(f"Job parameter file '{arg}' should contain a dictionary.")

        # Case 2: Provided argument is a Key=Value string
        else:
            regex_match = re.match("(.+)=(.*)", arg)

            if not regex_match:
                raise RuntimeError(f"Job parameter '{arg}' should be in the format 'Key=Value'.")
            parameter_dict.update({regex_match[1]: regex_match[2]})

    return parameter_dict


def get_task_params(arguments: list[list[str]]) -> list[dict[str, str]]:
    """
    Retrieves Task parameter sets from user-provided command line arguments.
    Each argument may be a list of Task parameters that forms
    the parameter set, or a file containing the Task parameter set(s) to use.

    For example, the arguments `["Param1=1 Param2=String1", "Param1=2 Param2=String2"]` will produce the following output:
    ```
    [
        {
            "Param1": "1",
            "Param2": "String1"
        },
        {
            "Param1": "2",
            "Param2": "String2"
        }
    ]
    ```

    Returns: A list of dictionaries, with each dictionary representing a
    Task parameter set. All values are represented as strings regardless
    of the parameter's defined type (types are resolved later by the
    `sessions` module).

    Raises: RuntimeError if filepaths can't be resolved or if arguments
    can't be serialized into dictionary objects.
    """
    all_parameter_sets: list[dict] = []

    error_list: list[str] = []
    for arg_list in arguments:
        # Case 1: Provided argument is a filepath
        if len(arg_list) == 1 and arg_list[0].startswith("file://"):
            filename = arg_list[0]
            # Raises: RuntimeError
            file_parameters = get_params_from_file(filename)
            # If the file contains a dictionary, add it as-is
            if isinstance(file_parameters, dict):
                all_parameter_sets.append(file_parameters)

            # If not, the file is a list; check if the list only contains dictionaries,
            # with a proper error message if not
            elif not all([isinstance(entry, dict) for entry in file_parameters]):
                error_list.append(
                    f"'{filename.removeprefix('file://')}' contains non-dictionary entries: {[entry for entry in file_parameters if not isinstance(entry, dict)]}"
                )

            # If not, all entries are dictionaries; add them to the parameter sets
            else:
                all_parameter_sets.extend(file_parameters)

        # Case 2: Provided argument is a list of Key=Value strings
        else:
            parameter_set: dict = {}

            for kvp in arg_list:
                regex_match = re.match("(.+)=(.+)", kvp.strip())
                if not regex_match:
                    error_list.append(f"'{kvp}' should be in the format 'Key=Value'")
                else:
                    parameter_set.update({regex_match[1]: regex_match[2]})

            if parameter_set:
                all_parameter_sets.append(parameter_set)

    if error_list:
        error_msg = "Found the following errors collecting Task parameters:"
        for error in error_list:
            error_msg += f"\n- {error}"
        raise RuntimeError(error_msg)

    return all_parameter_sets


def job_from_template(
    template: JobTemplate,
    parameter_args: list[str] | None,
    job_template_dir: Path,
    current_working_dir: Path,
) -> Job:
    """
    Given a decoded Job Template and a user-inputted parameter dictionary,
    generates a Job object.

    Raises: RuntimeError if parameters are an unsupported type or don't correspond to the template
    """
    parameter_dict = get_job_params(parameter_args) if parameter_args else {}

    try:
        parameter_values = preprocess_job_parameters(
            job_template=template,
            job_parameter_values=parameter_dict,
            job_template_dir=job_template_dir,
            current_working_dir=current_working_dir,
        )
    except ValueError as ve:
        raise RuntimeError(f"Parameters can't be used with Template: {str(ve)}")

    try:
        return create_job(job_template=template, job_parameter_values=parameter_values)
    except DecodeValidationError as dve:
        raise RuntimeError(f"Could not generate Job from template and parameters: {str(dve)}")
