# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""
Unit tests for the help formatter module that generates context-aware help text.
"""

import pytest
from openjd.cli._run._help_formatter import format_parameter_info


class TestFormatParameterInfo:
    """Tests for the format_parameter_info function."""

    @pytest.mark.parametrize(
        "param_name,param_type,expected",
        [
            ("Message", "STRING", "Message (STRING) [required]"),
            ("Count", "INT", "Count (INT) [required]"),
            ("Ratio", "FLOAT", "Ratio (FLOAT) [required]"),
            ("OutputDir", "PATH", "OutputDir (PATH) [required]"),
        ],
    )
    def test_required_parameters(self, param_name, param_type, expected):
        """Test formatting required parameters of different types."""
        param_def = {"name": param_name, "type": param_type}
        result = format_parameter_info(param_def)
        assert expected in result

    @pytest.mark.parametrize(
        "param_name,param_type,default_value,expected",
        [
            ("Message", "STRING", "Hello", "Message (STRING) [default: 'Hello']"),
            ("Count", "INT", 42, "Count (INT) [default: 42]"),
            ("Ratio", "FLOAT", 3.14, "Ratio (FLOAT) [default: 3.14]"),
            ("OutputDir", "PATH", "/tmp/output", "OutputDir (PATH) [default: '/tmp/output']"),
        ],
    )
    def test_parameters_with_defaults(self, param_name, param_type, default_value, expected):
        """Test formatting parameters with default values."""
        param_def = {"name": param_name, "type": param_type, "default": default_value}
        result = format_parameter_info(param_def)
        assert expected in result

    @pytest.mark.parametrize(
        "param_type,default,min_val,max_val,expected",
        [
            ("INT", 10, 1, None, "Count (INT) [default: 10] (minimum: 1)"),
            ("INT", 10, None, 100, "Count (INT) [default: 10] (maximum: 100)"),
            ("INT", 10, 1, 100, "Count (INT) [default: 10] (range: 1 to 100)"),
            ("FLOAT", 0.5, 0.0, 1.0, "Ratio (FLOAT) [default: 0.5] (range: 0.0 to 1.0)"),
        ],
    )
    def test_numeric_parameters_with_constraints(
        self, param_type, default, min_val, max_val, expected
    ):
        """Test formatting numeric parameters with min/max constraints."""
        param_name = "Count" if param_type == "INT" else "Ratio"
        param_def = {"name": param_name, "type": param_type, "default": default}
        if min_val is not None:
            param_def["minValue"] = min_val
        if max_val is not None:
            param_def["maxValue"] = max_val
        result = format_parameter_info(param_def)
        assert expected in result

    @pytest.mark.parametrize(
        "min_len,max_len,expected",
        [
            (3, None, "Name (STRING) [default: 'test'] (minimum length: 3 characters)"),
            (None, 50, "Name (STRING) [default: 'test'] (maximum length: 50 characters)"),
            (3, 50, "Name (STRING) [default: 'test'] (length: 3 to 50 characters)"),
        ],
    )
    def test_string_parameters_with_length_constraints(self, min_len, max_len, expected):
        """Test formatting STRING parameters with length constraints."""
        param_def = {"name": "Name", "type": "STRING", "default": "test"}
        if min_len is not None:
            param_def["minLength"] = min_len
        if max_len is not None:
            param_def["maxLength"] = max_len
        result = format_parameter_info(param_def)
        assert expected in result

    @pytest.mark.parametrize(
        "param_name,param_type,default,allowed_values,expected",
        [
            (
                "Environment",
                "STRING",
                "dev",
                ["dev", "staging", "prod"],
                "Environment (STRING) [default: 'dev'] (allowed: 'dev', 'staging', 'prod')",
            ),
            ("Priority", "INT", 1, [1, 2, 3], "Priority (INT) [default: 1] (allowed: 1, 2, 3)"),
        ],
    )
    def test_parameters_with_allowed_values(
        self, param_name, param_type, default, allowed_values, expected
    ):
        """Test formatting parameters with allowedValues constraint."""
        param_def = {
            "name": param_name,
            "type": param_type,
            "default": default,
            "allowedValues": allowed_values,
        }
        result = format_parameter_info(param_def)
        assert expected in result

    @pytest.mark.parametrize(
        "default,expected_status",
        [
            ("Hello, world!", "[default: 'Hello, world!']"),
            (None, "[required]"),
        ],
    )
    def test_parameters_with_description(self, default, expected_status):
        """Test formatting parameters with descriptions."""
        param_def = {"name": "Message", "type": "STRING", "description": "A message to display"}
        if default is not None:
            param_def["default"] = default
        result = format_parameter_info(param_def)
        assert expected_status in result
        assert "A message to display" in result

    @pytest.mark.parametrize(
        "param_name,param_type,default,expected_in,expected_not_in",
        [
            ("RequiredParam", "STRING", None, "[required]", "[default:"),
            (
                "OptionalParam",
                "STRING",
                "default_value",
                "[default: 'default_value']",
                "[required]",
            ),
            ("Count", "INT", 0, "Count (INT) [default: 0]", "[required]"),
            ("Message", "STRING", "", "Message (STRING) [default: '']", "[required]"),
        ],
    )
    def test_required_vs_optional_parameters(
        self, param_name, param_type, default, expected_in, expected_not_in
    ):
        """Test that parameters are correctly marked as required or optional."""
        param_def = {"name": param_name, "type": param_type}
        if default is not None or default == "" or default == 0:
            param_def["default"] = default
        result = format_parameter_info(param_def)
        assert expected_in in result
        assert expected_not_in not in result

    def test_string_parameter_with_multiline_default(self):
        """Test formatting a STRING parameter with multi-line default value."""
        param_def = {
            "name": "Script",
            "type": "STRING",
            "default": "echo 'Hello'\necho 'World'\nls -la",
            "description": "A bash script to run",
        }
        result = format_parameter_info(param_def)
        # Should indicate default is shown below
        assert "Script (STRING) [default: see below]" in result
        # Should include description
        assert "A bash script to run" in result
        # Should include "Default value:" header
        assert "Default value:" in result
        # Should include each line of the default value, indented
        assert "echo 'Hello'" in result
        assert "echo 'World'" in result
        assert "ls -la" in result

    def test_path_parameter_with_multiline_default(self):
        """Test formatting a PATH parameter with multi-line default value."""
        param_def = {
            "name": "ConfigFile",
            "type": "PATH",
            "default": "/path/to/file1\n/path/to/file2",
        }
        result = format_parameter_info(param_def)
        # Should indicate default is shown below
        assert "ConfigFile (PATH) [default: see below]" in result
        # Should include "Default value:" header
        assert "Default value:" in result
        # Should include each line
        assert "/path/to/file1" in result
        assert "/path/to/file2" in result


class TestGenerateJobTemplateHelp:
    """Tests for the generate_job_template_help function."""

    def test_minimal_template_name_only(self):
        """Test help generation for a template with only a name field."""
        from argparse import ArgumentParser
        from pathlib import Path
        from unittest.mock import Mock
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a minimal mock template with only name
        template = Mock()
        template.name = "minimal-job"
        template.description = None
        template.parameterDefinitions = None

        # Create a basic parser
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="Step name")

        template_path = Path("minimal.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job name appears in output
        assert "Job: minimal-job" in result
        # Verify usage line is present
        assert "usage:" in result.lower()
        # Verify no parameter section since there are no parameters
        assert "Job Parameters" not in result

    def test_template_with_name_and_description(self):
        """Test help generation for a template with name and description."""
        from argparse import ArgumentParser
        from pathlib import Path
        from unittest.mock import Mock
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a mock template with name and description
        template = Mock()
        template.name = "described-job"
        template.description = "This is a sample job that demonstrates basic functionality."
        template.parameterDefinitions = None

        # Create a basic parser
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="Step name")

        template_path = Path("described.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job name appears in output
        assert "Job: described-job" in result
        # Verify description appears in output
        assert "This is a sample job that demonstrates basic functionality." in result
        # Verify no parameter section since there are no parameters
        assert "Job Parameters" not in result

    def test_template_with_no_parameters(self):
        """Test help generation for a template with no parameters."""
        from argparse import ArgumentParser
        from pathlib import Path
        from unittest.mock import Mock
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a mock template with name, description, but no parameters
        template = Mock()
        template.name = "no-params-job"
        template.description = "A job without parameters"
        template.parameterDefinitions = []  # Empty list

        # Create a basic parser
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="Step name")

        template_path = Path("no-params.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job name and description appear
        assert "Job: no-params-job" in result
        assert "A job without parameters" in result
        # Verify no parameter section since the list is empty
        assert "Job Parameters" not in result

    def test_template_with_multiple_parameters(self):
        """Test help generation for a template with multiple parameters."""
        from argparse import ArgumentParser
        from pathlib import Path
        from openjd.model import decode_job_template
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a real template with multiple parameters
        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "multi-param-job",
                "description": "A job with multiple parameters",
                "parameterDefinitions": [
                    {
                        "name": "Message",
                        "type": "STRING",
                        "description": "A message to display",
                        "default": "Hello",
                    },
                    {
                        "name": "Count",
                        "type": "INT",
                        "description": "Number of iterations",
                        "default": 10,
                        "minValue": 1,
                        "maxValue": 100,
                    },
                    {"name": "OutputPath", "type": "PATH"},
                ],
                "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            }
        )

        # Create a basic parser
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="Step name")

        template_path = Path("multi-param.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job name and description appear
        assert "Job: multi-param-job" in result
        assert "A job with multiple parameters" in result

        # Verify parameter section exists
        assert "Job Parameters (-p/--job-param PARAM_NAME=VALUE):" in result

        # Verify all parameters are formatted correctly
        assert "Message (STRING) [default: 'Hello']" in result
        assert "A message to display" in result

        assert "Count (INT) [default: 10]" in result
        assert "range: 1 to 100" in result
        assert "Number of iterations" in result

        assert "OutputPath (PATH) [required]" in result

    def test_template_with_various_parameter_types_and_constraints(self):
        """Test help generation with various parameter types and constraints."""
        from argparse import ArgumentParser
        from pathlib import Path
        from openjd.model import decode_job_template
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a real template with various constraints
        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "constraint-job",
                "description": "Job with various constraints",
                "parameterDefinitions": [
                    {
                        "name": "Environment",
                        "type": "STRING",
                        "description": "Target environment",
                        "default": "dev",
                        "allowedValues": ["dev", "staging", "prod"],
                    },
                    {
                        "name": "Ratio",
                        "type": "FLOAT",
                        "description": "Processing ratio",
                        "default": 0.5,
                        "minValue": 0.0,
                        "maxValue": 1.0,
                    },
                    {
                        "name": "Username",
                        "type": "STRING",
                        "default": "user",
                        "minLength": 3,
                        "maxLength": 20,
                    },
                ],
                "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            }
        )

        # Create a basic parser
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")

        template_path = Path("constraint.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job name and description
        assert "Job: constraint-job" in result
        assert "Job with various constraints" in result

        # Verify parameter with allowedValues
        assert "Environment (STRING) [default: 'dev']" in result
        assert "allowed: 'dev', 'staging', 'prod'" in result
        assert "Target environment" in result

        # Verify parameter with numeric range
        assert "Ratio (FLOAT) [default: 0.5]" in result
        assert "range: 0.0 to 1.0" in result
        assert "Processing ratio" in result

        # Verify parameter with string length constraints
        assert "Username (STRING) [default: 'user']" in result
        assert "length: 3 to 20 characters" in result

    def test_job_name_and_description_appear_in_output(self):
        """Test that job name and description are prominently displayed."""
        from argparse import ArgumentParser
        from pathlib import Path
        from unittest.mock import Mock
        from openjd.cli._run._help_formatter import generate_job_template_help

        template = Mock()
        template.name = "test-job-name"
        template.description = "This is the test job description."
        template.parameterDefinitions = None

        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")

        template_path = Path("test.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job name appears with "Job:" prefix
        assert "Job: test-job-name" in result

        # Verify description appears
        assert "This is the test job description." in result

        # Verify they appear near the beginning (before any parameters or options)
        job_index = result.index("Job: test-job-name")
        desc_index = result.index("This is the test job description.")

        # Description should come after job name
        assert desc_index > job_index

    def test_all_parameters_formatted_correctly(self):
        """Test that all parameters in a template are formatted correctly."""
        from argparse import ArgumentParser
        from pathlib import Path
        from openjd.model import decode_job_template
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a real template with all parameter types
        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "all-params-job",
                "description": "Job with all parameter types",
                "parameterDefinitions": [
                    {
                        "name": "RequiredString",
                        "type": "STRING",
                        "description": "A required string",
                    },
                    {
                        "name": "OptionalInt",
                        "type": "INT",
                        "description": "An optional integer",
                        "default": 42,
                    },
                    {
                        "name": "ConstrainedFloat",
                        "type": "FLOAT",
                        "description": "A constrained float",
                        "default": 5.0,
                        "minValue": 0.0,
                        "maxValue": 10.0,
                    },
                    {
                        "name": "FilePath",
                        "type": "PATH",
                        "description": "A file path",
                        "default": "/tmp/output",
                    },
                ],
                "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            }
        )

        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")

        template_path = Path("all-params.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify each parameter is formatted correctly
        assert "RequiredString (STRING) [required]" in result
        assert "A required string" in result

        assert "OptionalInt (INT) [default: 42]" in result
        assert "An optional integer" in result

        assert "ConstrainedFloat (FLOAT) [default: 5.0]" in result
        assert "range: 0.0 to 10.0" in result
        assert "A constrained float" in result

        assert "FilePath (PATH) [default: '/tmp/output']" in result
        assert "A file path" in result

    def test_standard_options_appear_in_help_text(self):
        """Test that standard run command options appear in the help text."""
        from argparse import ArgumentParser
        from pathlib import Path
        from unittest.mock import Mock
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a simple template
        template = Mock()
        template.name = "simple-job"
        template.description = "A simple job"
        template.parameterDefinitions = None

        # Create a parser with standard options
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="The name of the Step in the Job to run Tasks from")
        parser.add_argument("--task-param", "-tp", help="Task parameter")
        parser.add_argument("--environment", help="Environment to use")
        parser.add_argument("--preserve", action="store_true", help="Preserve session")

        template_path = Path("simple.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify standard options section exists
        assert "Standard Options:" in result

        # Verify standard options appear in the output
        assert "--step" in result
        assert "--task-param" in result or "-tp" in result
        assert "--environment" in result
        assert "--preserve" in result

    def test_job_specific_info_appears_before_standard_options(self):
        """Test that job-specific information appears before standard options."""
        from argparse import ArgumentParser
        from pathlib import Path
        from openjd.model import decode_job_template
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a real template
        template = decode_job_template(
            template={
                "specificationVersion": "jobtemplate-2023-09",
                "name": "ordered-job",
                "description": "Job to test ordering",
                "parameterDefinitions": [
                    {
                        "name": "Message",
                        "type": "STRING",
                        "description": "A message",
                        "default": "Hello",
                    }
                ],
                "steps": [{"name": "Step1", "script": {"actions": {"onRun": {"command": "echo"}}}}],
            }
        )

        # Create a parser with standard options
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="Step name")
        parser.add_argument("--task-param", help="Task parameter")

        template_path = Path("ordered.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Find the positions of key sections
        job_name_index = result.index("Job: ordered-job")
        job_params_index = result.index("Job Parameters (-p/--job-param PARAM_NAME=VALUE):")
        standard_options_index = result.index("Standard Options:")

        # Verify ordering: job name < job parameters < standard options
        assert job_name_index < job_params_index
        assert job_params_index < standard_options_index

        # Verify job description appears before standard options
        desc_index = result.index("Job to test ordering")
        assert desc_index < standard_options_index

    def test_standard_options_with_no_job_parameters(self):
        """Test that standard options appear even when there are no job parameters."""
        from argparse import ArgumentParser
        from pathlib import Path
        from unittest.mock import Mock
        from openjd.cli._run._help_formatter import generate_job_template_help

        # Create a template without parameters
        template = Mock()
        template.name = "no-params-job"
        template.description = "Job without parameters"
        template.parameterDefinitions = None

        # Create a parser with standard options
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", help="Path to job template")
        parser.add_argument("--step", help="Step name")
        parser.add_argument("--task-param", help="Task parameter")
        parser.add_argument("--environment", help="Environment")

        template_path = Path("no-params.yaml")

        result = generate_job_template_help(template, parser, template_path)

        # Verify job info appears
        assert "Job: no-params-job" in result
        assert "Job without parameters" in result

        # Verify no job parameters section
        assert "Job Parameters" not in result

        # Verify standard options still appear
        assert "Standard Options:" in result
        assert "--step" in result
        assert "--task-param" in result
        assert "--environment" in result

        # Verify job name appears before standard options
        job_index = result.index("Job: no-params-job")
        options_index = result.index("Standard Options:")
        assert job_index < options_index


class TestJobTemplateHelpAction:
    """Tests for the JobTemplateHelpAction class."""

    def test_action_triggered_with_h_flag(self):
        """Test that the action is triggered with -h flag."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json

        # Create a temporary template file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            template_data = {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "test-job",
                "steps": [
                    {
                        "name": "Step1",
                        "script": {"actions": {"onRun": {"command": "echo", "args": ["test"]}}},
                    }
                ],
            }
            json.dump(template_data, f)
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with template path
            namespace = Namespace(path=template_path, extensions=None)

            # Mock sys.exit to prevent actual exit
            with patch("sys.exit") as mock_exit:
                with patch("builtins.print") as mock_print:
                    # Call the action
                    action(parser, namespace, None, "-h")

                    # Verify sys.exit was called with 0
                    mock_exit.assert_called_once_with(0)

                    # Verify print was called (help was displayed)
                    assert mock_print.called
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_action_triggered_with_help_flag(self):
        """Test that the action is triggered with --help flag."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json

        # Create a temporary template file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            template_data = {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "test-job",
                "steps": [
                    {
                        "name": "Step1",
                        "script": {"actions": {"onRun": {"command": "echo", "args": ["test"]}}},
                    }
                ],
            }
            json.dump(template_data, f)
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with template path
            namespace = Namespace(path=template_path, extensions=None)

            # Mock sys.exit to prevent actual exit
            with patch("sys.exit") as mock_exit:
                with patch("builtins.print") as mock_print:
                    # Call the action with --help
                    action(parser, namespace, None, "--help")

                    # Verify sys.exit was called with 0
                    mock_exit.assert_called_once_with(0)

                    # Verify print was called (help was displayed)
                    assert mock_print.called
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_action_receives_correct_parser_and_namespace(self):
        """Test that the action receives correct parser and namespace."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json

        # Create a temporary template file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            template_data = {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "test-job",
                "steps": [
                    {
                        "name": "Step1",
                        "script": {"actions": {"onRun": {"command": "echo", "args": ["test"]}}},
                    }
                ],
            }
            json.dump(template_data, f)
            template_path = f.name

        try:
            # Create parser with specific attributes
            parser = ArgumentParser(prog="openjd run")
            parser.add_argument("path", help="Path to job template")
            parser.add_argument("--step", help="Step name")

            # Create action
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with specific attributes
            namespace = Namespace(path=template_path, extensions=None, step=None)

            # Mock sys.exit and generate_job_template_help to verify they receive correct arguments
            with patch("sys.exit") as mock_exit:
                with patch(
                    "openjd.cli._run._help_formatter.generate_job_template_help"
                ) as mock_generate:
                    mock_generate.return_value = "Test help text"

                    # Call the action
                    action(parser, namespace, None, "-h")

                    # Verify generate_job_template_help was called with correct parser
                    assert mock_generate.called
                    call_args = mock_generate.call_args
                    assert call_args[0][1] == parser  # Second argument should be the parser
                    assert isinstance(call_args[0][2], Path)  # Third argument should be Path

                    # Verify sys.exit was called
                    mock_exit.assert_called_once_with(0)
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_error_with_non_existent_template_file(self):
        """Test error handling when template file does not exist."""
        from argparse import ArgumentParser, Namespace
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction

        # Create parser and action
        parser = ArgumentParser(prog="openjd run")
        action = JobTemplateHelpAction(["-h", "--help"], "help")

        # Create namespace with non-existent template path
        namespace = Namespace(path="/non/existent/template.json", extensions=None)

        # Mock sys.exit and sys.stderr
        with patch("sys.exit") as mock_exit:
            with patch("sys.stderr.write") as mock_stderr:
                # Call the action
                action(parser, namespace, None, "-h")

                # Verify sys.exit was called with 1 (error)
                mock_exit.assert_called_once_with(1)

                # Verify error message was written to stderr
                assert mock_stderr.called

    def test_error_with_invalid_json_syntax(self):
        """Test error handling when template has invalid JSON syntax."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile

        # Create a temporary file with invalid JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write('{"invalid": json syntax}')  # Missing quotes around 'json'
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with invalid template path
            namespace = Namespace(path=template_path, extensions=None)

            # Mock sys.exit
            with patch("sys.exit") as mock_exit:
                with patch("sys.stderr.write") as mock_stderr:
                    # Call the action
                    action(parser, namespace, None, "-h")

                    # Verify sys.exit was called with 1 (error)
                    mock_exit.assert_called_once_with(1)

                    # Verify error message was written to stderr
                    assert mock_stderr.called
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_error_with_invalid_yaml_syntax(self):
        """Test error handling when template has invalid YAML syntax."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile

        # Create a temporary file with invalid YAML
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            f.write("invalid:\n  - yaml\n  syntax:\nbroken")  # Invalid YAML structure
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with invalid template path
            namespace = Namespace(path=template_path, extensions=None)

            # Mock sys.exit
            with patch("sys.exit") as mock_exit:
                with patch("sys.stderr.write") as mock_stderr:
                    # Call the action
                    action(parser, namespace, None, "-h")

                    # Verify sys.exit was called with 1 (error)
                    mock_exit.assert_called_once_with(1)

                    # Verify error message was written to stderr
                    assert mock_stderr.called
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_error_with_schema_validation_failure(self):
        """Test error handling when template fails schema validation."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json

        # Create a temporary file with invalid schema (missing required fields)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            template_data = {
                "specificationVersion": "jobtemplate-2023-09",
                # Missing required "name" field
                # Missing required "steps" field
            }
            json.dump(template_data, f)
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with invalid template path
            namespace = Namespace(path=template_path, extensions=None)

            # Mock sys.exit
            with patch("sys.exit") as mock_exit:
                with patch("sys.stderr.write") as mock_stderr:
                    # Call the action
                    action(parser, namespace, None, "-h")

                    # Verify sys.exit was called with 1 (error)
                    mock_exit.assert_called_once_with(1)

                    # Verify error message was written to stderr
                    assert mock_stderr.called
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_error_messages_are_user_friendly(self):
        """Test that error messages are user-friendly and don't expose stack traces."""
        from argparse import ArgumentParser, Namespace
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import io

        # Create parser and action
        parser = ArgumentParser(prog="openjd run")
        action = JobTemplateHelpAction(["-h", "--help"], "help")

        # Create namespace with non-existent template path
        namespace = Namespace(path="/non/existent/template.json", extensions=None)

        # Capture stderr output
        stderr_capture = io.StringIO()

        # Mock sys.exit and redirect stderr
        with patch("sys.exit") as mock_exit:
            with patch("sys.stderr", stderr_capture):
                # Call the action
                action(parser, namespace, None, "-h")

                # Get the error message
                error_output = stderr_capture.getvalue()

                # Verify error message starts with "Error:"
                assert error_output.startswith("Error:")

                # Verify no stack trace is present (no "Traceback" keyword)
                assert "Traceback" not in error_output

                # Verify sys.exit was called with 1
                mock_exit.assert_called_once_with(1)

    def test_exit_code_is_1_for_errors(self):
        """Test that exit code is 1 for all error scenarios."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json

        # Test with non-existent file
        parser = ArgumentParser(prog="openjd run")
        action = JobTemplateHelpAction(["-h", "--help"], "help")
        namespace = Namespace(path="/non/existent/file.json", extensions=None)

        with patch("sys.exit") as mock_exit:
            with patch("sys.stderr.write"):
                action(parser, namespace, None, "-h")
                mock_exit.assert_called_once_with(1)

        # Test with invalid JSON
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json}")
            invalid_json_path = f.name

        try:
            namespace = Namespace(path=invalid_json_path, extensions=None)
            with patch("sys.exit") as mock_exit:
                with patch("sys.stderr.write"):
                    action(parser, namespace, None, "-h")
                    mock_exit.assert_called_once_with(1)
        finally:
            Path(invalid_json_path).unlink()

        # Test with schema validation failure
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"specificationVersion": "jobtemplate-2023-09"}, f)
            invalid_schema_path = f.name

        try:
            namespace = Namespace(path=invalid_schema_path, extensions=None)
            with patch("sys.exit") as mock_exit:
                with patch("sys.stderr.write"):
                    action(parser, namespace, None, "-h")
                    mock_exit.assert_called_once_with(1)
        finally:
            Path(invalid_schema_path).unlink()

    def test_help_displays_and_exits_with_code_0(self):
        """Test that help displays successfully and exits with code 0."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json
        import io

        # Create a valid temporary template file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            template_data = {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "success-test-job",
                "description": "A job for testing successful help display",
                "parameterDefinitions": [
                    {"name": "TestParam", "type": "STRING", "default": "test_value"}
                ],
                "steps": [
                    {
                        "name": "TestStep",
                        "script": {"actions": {"onRun": {"command": "echo", "args": ["test"]}}},
                    }
                ],
            }
            json.dump(template_data, f)
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            parser.add_argument("path", help="Path to job template")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with valid template path
            namespace = Namespace(path=template_path, extensions=None)

            # Capture stdout
            stdout_capture = io.StringIO()

            # Mock sys.exit and redirect stdout
            with patch("sys.exit") as mock_exit:
                with patch("sys.stdout", stdout_capture):
                    # Call the action
                    action(parser, namespace, None, "-h")

                    # Verify sys.exit was called with 0 (success)
                    mock_exit.assert_called_once_with(0)

                    # Verify help was displayed
                    help_output = stdout_capture.getvalue()
                    assert len(help_output) > 0
                    assert "success-test-job" in help_output
                    assert "A job for testing successful help display" in help_output
                    assert "TestParam" in help_output
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_template_is_validated_before_help_generation(self):
        """Test that template is validated before help generation."""
        from argparse import ArgumentParser, Namespace
        from pathlib import Path
        from unittest.mock import patch, MagicMock
        from openjd.cli._run._help_formatter import JobTemplateHelpAction
        import tempfile
        import json

        # Create a valid temporary template file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            template_data = {
                "specificationVersion": "jobtemplate-2023-09",
                "name": "validation-test-job",
                "steps": [
                    {
                        "name": "TestStep",
                        "script": {"actions": {"onRun": {"command": "echo", "args": ["test"]}}},
                    }
                ],
            }
            json.dump(template_data, f)
            template_path = f.name

        try:
            # Create parser and action
            parser = ArgumentParser(prog="openjd run")
            action = JobTemplateHelpAction(["-h", "--help"], "help")

            # Create namespace with valid template path
            namespace = Namespace(path=template_path, extensions=None)

            # Mock read_job_template to verify it's called (this performs validation)
            with patch("openjd.cli._run._help_formatter.read_job_template") as mock_read:
                # Create a mock template object
                mock_template = MagicMock()
                mock_template.name = "validation-test-job"
                mock_template.description = None
                mock_template.parameterDefinitions = None
                mock_read.return_value = mock_template

                with patch("sys.exit"):
                    with patch("builtins.print"):
                        # Call the action
                        action(parser, namespace, None, "-h")

                        # Verify read_job_template was called (which validates the template)
                        mock_read.assert_called_once()
                        call_args = mock_read.call_args
                        assert str(call_args[0][0]) == template_path
        finally:
            # Clean up
            Path(template_path).unlink()

    def test_help_without_template_shows_standard_help(self):
        """Test that help without template path shows standard help."""
        from argparse import ArgumentParser, Namespace
        from unittest.mock import patch
        from openjd.cli._run._help_formatter import JobTemplateHelpAction

        # Create parser and action
        parser = ArgumentParser(prog="openjd run")
        parser.add_argument("path", nargs="?", help="Path to job template")
        parser.add_argument("--step", help="Step name")
        action = JobTemplateHelpAction(["-h", "--help"], "help")

        # Create namespace without template path
        namespace = Namespace(path=None, extensions=None)

        # Create a custom exception to stop execution
        class SystemExitMock(Exception):
            pass

        # Mock sys.exit to raise exception and stop execution
        def mock_exit_func(code):
            raise SystemExitMock(code)

        with patch(
            "openjd.cli._run._help_formatter.sys.exit", side_effect=mock_exit_func
        ) as mock_exit:
            with patch.object(parser, "print_help") as mock_print_help:
                try:
                    # Call the action
                    action(parser, namespace, None, "-h")
                except SystemExitMock as e:
                    # Expected - sys.exit was called
                    assert e.args[0] == 0

                # Verify parser.print_help was called (standard help)
                mock_print_help.assert_called_once()

                # Verify sys.exit was called with 0
                mock_exit.assert_called_once_with(0)
