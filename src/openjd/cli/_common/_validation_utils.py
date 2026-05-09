# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from typing import Any, Optional
from pathlib import Path

from openjd.model import (
    DecodeValidationError,
    DocumentType,
    EnvironmentTemplate,
    JobTemplate,
    document_string_to_object,
    decode_environment_template,
    decode_job_template,
)


def get_doc_type(filepath: Path) -> DocumentType:
    # If the file has a .json extension, treat it strictly
    # as JSON, otherwise treat it as YAML.
    if filepath.suffix.lower() == ".json":
        return DocumentType.JSON
    else:
        return DocumentType.YAML


def read_template(template_file: Path) -> dict[str, Any]:
    """Open a JSON or YAML-formatted file and attempt to parse it into a JobTemplate object.
    Raises a RuntimeError if the file doesn't exist or can't be opened, and raises a
    DecodeValidationError if its contents can't be parsed into a valid JobTemplate.
    """

    if not template_file.exists():
        raise RuntimeError(f"'{str(template_file)}' does not exist.")

    if template_file.is_file():
        # Raises: RuntimeError
        filetype = get_doc_type(template_file)
    else:
        raise RuntimeError(f"'{str(template_file)}' is not a file.")

    try:
        template_string = template_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not open file '{str(template_file)}': {str(exc)}")

    try:
        # Raises: DecodeValidationError
        template_object = document_string_to_object(
            document=template_string, document_type=filetype
        )
    except DecodeValidationError as exc:
        raise RuntimeError(f"'{str(template_file)}' failed checks: {str(exc)}")

    return template_object


def read_job_template(template_file: Path, *, supported_extensions: list[str]) -> JobTemplate:
    """Open a JSON or YAML-formatted file and attempt to parse it into a JobTemplate object.
    Raises a RuntimeError if the file doesn't exist or can't be opened, and raises a
    DecodeValidationError if its contents can't be parsed into a valid JobTemplate.
    """
    # Raises RuntimeError
    template_object = read_template(template_file)

    # Raises: DecodeValidationError
    template = decode_job_template(
        template=template_object, supported_extensions=supported_extensions
    )

    return template


def read_environment_template(
    template_file: Path,
    *,
    supported_extensions: Optional[list[str]] = None,
) -> EnvironmentTemplate:
    """Open a JSON or YAML-formatted file and attempt to parse it into an EnvironmentTemplate object.
    Raises a RuntimeError if the file doesn't exist or can't be opened, and raises a
    DecodeValidationError if its contents can't be parsed into a valid EnvironmentTemplate.

    Environment templates may declare extensions just like job templates do
    (e.g. ``WRAP_ACTIONS`` for RFC 0008's wrap hooks). Pass the CLI's allow-list
    via ``supported_extensions`` so the model accepts those declarations;
    omitting the argument preserves the legacy behavior of accepting only the
    default model surface.
    """
    # Raises RuntimeError
    template_object = read_template(template_file)

    decode_kwargs: dict[str, list[str]] = {}
    if supported_extensions is not None:
        decode_kwargs["supported_extensions"] = supported_extensions

    # Raises: DecodeValidationError
    template = decode_environment_template(template=template_object, **decode_kwargs)

    return template
