# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
from pathlib import Path

from openjd.model import (
    DecodeValidationError,
    DocumentType,
    JobTemplate,
    decode_template,
    document_string_to_object,
)


def get_doc_type(filepath: Path) -> DocumentType:
    if filepath.suffix.lower() == ".json":
        return DocumentType.JSON
    elif filepath.suffix.lower() in (".yaml", ".yml"):
        return DocumentType.YAML
    raise RuntimeError(f"'{str(filepath)}' is not JSON or YAML.")


def _find_template_in_directory(bundle_dir: Path) -> Path:
    """Search a directory for a Job Template file,
    stopping at the first instance of a `template.json` or `template.yaml` file in the top level."""
    for file in bundle_dir.glob("*template.*"):
        if file.is_file() and file.suffix.lower() in (".json", ".yaml", ".yml"):
            return file

    raise RuntimeError(
        f"Couldn't find 'template.json' or 'template.yaml' in the folder '{str(bundle_dir)}'."
    )


def read_template(args: Namespace) -> tuple[Path, JobTemplate]:
    """Open a JSON or YAML-formatted file and attempt to parse it into a JobTemplate object.
    Raises a RuntimeError if the file doesn't exist or can't be opened, and raises a
    DecodeValidationError if its contents can't be parsed into a valid JobTemplate.
    """

    if not args.path.exists():
        raise RuntimeError(f"'{str(args.path)}' does not exist.")

    if args.path.is_file():
        # Raises: RuntimeError
        filepath = args.path
        filetype = get_doc_type(filepath)
    elif args.path.is_dir():
        # Raises: RuntimeError
        filepath = _find_template_in_directory(args.path)
        filetype = get_doc_type(filepath)
    else:
        raise RuntimeError(f"'{str(args.path)}' is not a file or directory.")

    try:
        template_string = filepath.read_text(encoding="utf-8")
    except OSError as exc:
        raise RuntimeError(f"Could not open file '{str(filepath)}': {str(exc)}")

    try:
        template_object = document_string_to_object(
            document=template_string, document_type=filetype
        )
        template = decode_template(template=template_object)
    except DecodeValidationError as exc:
        raise RuntimeError(f"'{str(filepath)}' failed checks: {str(exc)}")

    return filepath, template
