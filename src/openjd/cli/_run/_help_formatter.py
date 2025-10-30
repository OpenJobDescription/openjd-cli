# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Help formatter module for generating context-aware help text for job templates.
"""

from argparse import Action, ArgumentParser, Namespace
from pathlib import Path
import sys
import textwrap
from typing import Any, Dict, Optional

from openjd.model import DecodeValidationError, JobTemplate
from .._common import read_job_template, process_extensions_argument


def format_parameter_info(param_def: Dict[str, Any]) -> str:
    """
    Format a single parameter definition for help display.

    This function converts a parameter definition from a job template into
    readable help text that includes the parameter's type, constraints, and
    default value (if any).

    Args:
        param_def: Parameter definition dictionary from job template containing:
            - name (str): Parameter name
            - type (str): Parameter type (STRING, INT, FLOAT, PATH)
            - description (str, optional): Parameter description
            - default (Any, optional): Default value
            - minValue (int|float, optional): Minimum value for numeric types
            - maxValue (int|float, optional): Maximum value for numeric types
            - minLength (int, optional): Minimum length for string types
            - maxLength (int, optional): Maximum length for string types
            - allowedValues (list, optional): List of allowed values

    Returns:
        Formatted string describing the parameter in argparse-style help format.

    Example output formats:
        "ParamName (STRING) [required]"
        "ParamName (INT) [default: 42]"
        "ParamName (FLOAT) [default: 3.14] (range: 0.0 to 10.0)"
        "ParamName (STRING) [default: 'hello'] (allowed: 'hello', 'world')"
    """
    param_name = param_def.get("name", "")
    param_type = param_def.get("type", "STRING")
    description = param_def.get("description", "")
    default_value = param_def.get("default")

    # Start building the parameter info string
    parts = []

    # Add parameter name and type
    type_info = f"{param_name} ({param_type})"
    parts.append(type_info)

    # Add required/default status
    has_multiline_default = False
    if default_value is not None:
        # Check if default value contains newlines (multi-line string)
        if (
            param_type in ("STRING", "PATH")
            and isinstance(default_value, str)
            and "\n" in default_value
        ):
            has_multiline_default = True
            parts.append("[default: see below]")
        else:
            # Format default value based on type
            if param_type in ("STRING", "PATH"):
                default_str = f"[default: '{default_value}']"
            else:
                default_str = f"[default: {default_value}]"
            parts.append(default_str)
    else:
        parts.append("[required]")

    # Build the first line with name, type, and default/required
    first_line = " ".join(parts)

    # Build constraint information
    constraints = []

    # Handle numeric constraints (minValue, maxValue)
    min_val = param_def.get("minValue")
    max_val = param_def.get("maxValue")

    if min_val is not None and max_val is not None:
        constraints.append(f"range: {min_val} to {max_val}")
    elif min_val is not None:
        constraints.append(f"minimum: {min_val}")
    elif max_val is not None:
        constraints.append(f"maximum: {max_val}")

    # Handle string length constraints
    min_len = param_def.get("minLength")
    max_len = param_def.get("maxLength")

    if min_len is not None and max_len is not None:
        constraints.append(f"length: {min_len} to {max_len} characters")
    elif min_len is not None:
        constraints.append(f"minimum length: {min_len} characters")
    elif max_len is not None:
        constraints.append(f"maximum length: {max_len} characters")

    # Handle allowed values constraint
    allowed_values = param_def.get("allowedValues")
    if allowed_values:
        # Format allowed values based on type
        if param_type in ("STRING", "PATH"):
            formatted_values = ", ".join(f"'{v}'" for v in allowed_values)
        else:
            formatted_values = ", ".join(str(v) for v in allowed_values)
        constraints.append(f"allowed: {formatted_values}")

    # Combine everything
    result_lines = [first_line]

    # Add description if present
    if description:
        result_lines.append(f"    {description}")

    # Add constraints if present
    if constraints:
        constraint_str = " (" + ", ".join(constraints) + ")"
        result_lines[0] += constraint_str

    # Add multi-line default value if present
    if has_multiline_default and isinstance(default_value, str):
        result_lines.append("    Default value:")
        # Indent each line of the default value
        result_lines.append(textwrap.indent(default_value, "      "))

    return "\n".join(result_lines)


def generate_job_template_help(
    template: JobTemplate, parser: ArgumentParser, template_path: Path
) -> str:
    """
    Generate help text for a specific job template.

    This function creates formatted help text that includes the job name,
    description (if present), parameter definitions with their types and
    constraints, and standard command options from the argument parser.

    Args:
        template: The decoded job template object (JobTemplate from openjd.model)
        parser: The argument parser for the run command
        template_path: Path to the template file

    Returns:
        Formatted help text string in argparse-style format

    Example output:
        usage: openjd run my-template.yaml [arguments]

        Job: my-job
        This is a sample job that demonstrates parameter usage.

        Job Parameters (-p/--job-param PARAM_NAME=VALUE):
          Message (STRING) [default: 'Hello, world!']
              A message to display

        Standard Options:
          --step STEP_NAME      The name of the Step in the Job to run Tasks from.
          ...
    """
    lines = []

    # Add usage line with actual template path instead of symbolic placeholder
    usage = parser.format_usage().strip()
    # Replace the symbolic JOB_TEMPLATE_PATH with the actual path provided
    usage = usage.replace("JOB_TEMPLATE_PATH", str(template_path))
    lines.append(usage)
    lines.append("")

    # Print the job name and description (if present)
    lines.append(f"Job: {template.name}")
    if template.description:
        lines.append(template.description)
    lines.append("")

    # Extract parameter definitions (optional field)
    param_definitions = template.parameterDefinitions

    if param_definitions:
        lines.append("Job Parameters (-p/--job-param PARAM_NAME=VALUE):")

        for param_def in param_definitions:
            param_dict: Dict[str, Any] = {
                "name": param_def.name,
                "type": param_def.type.value,
                "description": param_def.description,
                "default": param_def.default,
            }

            # Add optional constraint fields if they exist
            for constraint in [
                "minValue",
                "maxValue",
                "minLength",
                "maxLength",
                "allowedValues",
            ]:
                if hasattr(param_def, constraint):
                    value = getattr(param_def, constraint)
                    if value is not None:
                        param_dict[constraint] = value

            # Format the parameter info
            param_info = format_parameter_info(param_dict)

            # Indent the parameter info with 2 spaces
            lines.append(textwrap.indent(param_info, "  "))

        lines.append("")

    # Add standard options section
    lines.append("Standard Options:")

    # Get the help text for all other arguments
    full_help = parser.format_help()

    # Split into lines and find where the arguments section starts
    help_lines = full_help.split("\n")

    # Skip usage and positional arguments, capture optional arguments
    in_options = False
    for line in help_lines:
        # Look for optional arguments section or specific argument patterns
        if "optional arguments:" in line.lower() or "options:" in line.lower():
            in_options = True
            continue
        elif "positional arguments:" in line.lower():
            continue
        elif in_options:
            # Add all option lines
            lines.append(line)

    return "\n".join(lines)


class JobTemplateHelpAction(Action):
    """
    Custom argparse Action that intercepts help requests (-h/--help) and generates
    context-aware help text based on the job template file provided.

    This action is triggered when the user invokes the run command with a job template
    path and the -h or --help flag. It loads and validates the template, then generates
    and displays help text that includes job-specific information (name, description,
    parameters) alongside standard command options.

    The action handles errors gracefully, displaying user-friendly error messages for
    issues like missing files, invalid syntax, or schema validation failures.
    """

    def __init__(
        self,
        option_strings,
        dest,
        default=False,
        required=False,
        help=None,
    ):
        """
        Initialize the custom help action.

        Args:
            option_strings: List of option strings (e.g., ['-h', '--help'])
            dest: Destination attribute name in the namespace
            default: Default value for the action
            required: Whether this argument is required
            help: Help text for this option
        """
        super().__init__(
            option_strings=option_strings,
            dest=dest,
            default=default,
            nargs=0,
            required=required,
            help=help,
        )

    def __call__(
        self,
        parser: ArgumentParser,
        namespace: Namespace,
        values: Any,
        option_string: Optional[str] = None,
    ) -> None:
        """
        Invoked when -h or --help is encountered.

        This method intercepts the help request, checks if a job template path
        has been provided, loads and validates the template, generates custom
        help text, and displays it before exiting.

        Args:
            parser: The argument parser instance
            namespace: The namespace containing parsed arguments so far
            values: The value associated with the action (unused for help)
            option_string: The option string that triggered this action ('-h' or '--help')

        Exits:
            - Code 0: Help displayed successfully
            - Code 1: Error occurred (file not found, validation failed, etc.)
        """
        # Check if a template path has been provided
        template_path = getattr(namespace, "path", None)

        if template_path is None:
            # No template path provided, show standard help
            parser.print_help()
            sys.exit(0)

        # Convert to Path object if it's a string
        if isinstance(template_path, str):
            template_path = Path(template_path)

        try:
            # Process extensions argument (defaults to all supported extensions if not provided)
            extensions_arg = getattr(namespace, "extensions", None)
            supported_extensions = process_extensions_argument(extensions_arg)

            # Load and validate the job template
            # This will raise RuntimeError for file issues or DecodeValidationError for validation issues
            template = read_job_template(template_path, supported_extensions=supported_extensions)

            # Generate the custom help text
            help_text = generate_job_template_help(template, parser, template_path)

            # Display the help text
            print(help_text)

            # Exit successfully
            sys.exit(0)

        except RuntimeError as e:
            # Handle file not found, parse errors, etc.
            print(f"Error: {str(e)}", file=sys.stderr)
            sys.exit(1)

        except DecodeValidationError as e:
            # Handle template validation errors
            print(f"Error: Invalid job template: {str(e)}", file=sys.stderr)
            sys.exit(1)

        except Exception as e:
            # Catch any unexpected errors
            print(f"Error: Failed to generate help: {str(e)}", file=sys.stderr)
            sys.exit(1)
