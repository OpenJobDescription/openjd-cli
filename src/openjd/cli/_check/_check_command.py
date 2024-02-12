# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
from openjd.model import (
    DecodeValidationError,
    TemplateSpecificationVersion,
    decode_job_template,
    decode_environment_template,
)

from .._common import read_template, OpenJDCliResult, print_cli_result


@print_cli_result
def do_check(args: Namespace) -> OpenJDCliResult:
    """Open a provided template file and check its schema for errors."""

    try:
        # Raises: RuntimeError
        template_object = read_template(args.path)

        # Raises: KeyError
        document_version = template_object["specificationVersion"]

        # Raises: ValueError
        template_version = TemplateSpecificationVersion(document_version)

        # Raises: DecodeValidationError
        if TemplateSpecificationVersion.is_job_template(template_version):
            decode_job_template(template=template_object)
        elif TemplateSpecificationVersion.is_environment_template(template_version):
            decode_environment_template(template=template_object)
        else:
            return OpenJDCliResult(
                status="error",
                message=f"Unknown template 'specificationVersion' ({document_version}).",
            )

    except KeyError:
        return OpenJDCliResult(
            status="error", message="ERROR: Missing field 'specificationVersion'"
        )
    except RuntimeError as exc:
        return OpenJDCliResult(status="error", message=f"ERROR: {str(exc)}")
    except DecodeValidationError as exc:
        return OpenJDCliResult(
            status="error", message=f"ERROR: '{str(args.path)}' failed checks: {str(exc)}"
        )

    return OpenJDCliResult(
        status="success", message=f"Template at '{str(args.path)}' passes validation checks."
    )
