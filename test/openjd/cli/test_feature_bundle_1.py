# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

"""Tests for FEATURE_BUNDLE_1 extension support in the CLI."""

import os
from pathlib import Path

import pytest

from . import run_openjd_cli_main

TEMPLATES_DIR = Path(__file__).parent / "templates"


class TestFeatureBundle1:
    """Tests for FEATURE_BUNDLE_1 extension features."""

    def test_python_syntax_sugar(self, capsys) -> None:
        """Test that Python syntax sugar works."""
        template = TEMPLATES_DIR / "feature_bundle_1_python.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Hello from Python!" in outerr.out

    def test_bash_syntax_sugar(self, capsys) -> None:
        """Test that Bash syntax sugar works."""
        template = TEMPLATES_DIR / "feature_bundle_1_bash.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Hello from Bash!" in outerr.out

    @pytest.mark.skipif(os.name != "nt", reason="PowerShell only available on Windows")
    def test_powershell_syntax_sugar(self, capsys) -> None:
        """Test that PowerShell syntax sugar works."""
        template = TEMPLATES_DIR / "feature_bundle_1_powershell.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Hello from PowerShell!" in outerr.out

    @pytest.mark.skipif(os.name != "nt", reason="cmd only available on Windows")
    def test_cmd_syntax_sugar(self, capsys) -> None:
        """Test that cmd syntax sugar works."""
        template = TEMPLATES_DIR / "feature_bundle_1_cmd.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Hello from Cmd!" in outerr.out

    def test_format_string_timeout(self, capsys) -> None:
        """Test that format string timeout is resolved."""
        template = TEMPLATES_DIR / "feature_bundle_1_timeout.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Running with timeout 20s" in outerr.out

    def test_format_string_amount_minmax(self, capsys) -> None:
        """Test that format string min/max in AmountRequirement is resolved."""
        template = TEMPLATES_DIR / "feature_bundle_1_amount_minmax.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Amount min/max works!" in outerr.out

    def test_format_string_notify_period(self, capsys) -> None:
        """Test that format string notifyPeriodInSeconds is resolved."""
        template = TEMPLATES_DIR / "feature_bundle_1_notify_period.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Notify period works!" in outerr.out

    def test_extended_step_name(self, capsys) -> None:
        """Test that extended step names (>64 chars) work with extension."""
        template = TEMPLATES_DIR / "feature_bundle_1_long_name.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        assert "Long step name works!" in outerr.out

    def test_end_of_line_lf(self, capsys) -> None:
        """Test that endOfLine: LF produces LF-only line endings."""
        template = TEMPLATES_DIR / "feature_bundle_1_eol_lf.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        # xxd output: 0a is LF, no 0d (CR) present
        assert "310a 6c69 6e65 320a 6c69" in outerr.out  # line1<LF>line2<LF>line

    def test_end_of_line_crlf(self, capsys) -> None:
        """Test that endOfLine: CRLF produces CRLF line endings."""
        template = TEMPLATES_DIR / "feature_bundle_1_eol_crlf.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        # xxd output: 0d0a is CRLF
        assert "310d 0a6c 696e 6532 0d0a" in outerr.out  # line1<CRLF>line2<CRLF>

    def test_end_of_line_auto(self, capsys) -> None:
        """Test that endOfLine: AUTO produces platform-native line endings."""
        template = TEMPLATES_DIR / "feature_bundle_1_eol_auto.yaml"
        outerr = run_openjd_cli_main(capsys, args=["run", str(template)], expected_exit_code=0)
        if os.name == "nt":
            assert "310d 0a6c 696e 6532 0d0a" in outerr.out  # CRLF on Windows
        else:
            assert "310a 6c69 6e65 320a 6c69" in outerr.out  # LF on POSIX

    def test_check_validates_extension(self, capsys) -> None:
        """Test that check command validates templates with extension."""
        template = TEMPLATES_DIR / "feature_bundle_1_python.yaml"
        outerr = run_openjd_cli_main(capsys, args=["check", str(template)], expected_exit_code=0)
        assert "passes validation checks" in outerr.out
