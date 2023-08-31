# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

from argparse import Namespace
from pathlib import Path
from typing import Callable
import json
import pytest
import tempfile
import yaml

from . import MOCK_TEMPLATE
from openjd.cli._check._check_command import do_check


@pytest.mark.parametrize(
    "tempfile_extension,doc_serializer",
    [
        pytest.param(".template.json", json.dump, id="Successful JSON"),
        pytest.param(".template.yaml", yaml.dump, id="Successful YAML"),
    ],
)
def test_do_check_file_success(tempfile_extension: str, doc_serializer: Callable):
    """
    Execution should succeed given a correct filepath and JSON/YAML body
    """
    temp_template = None

    with tempfile.NamedTemporaryFile(
        mode="w+t", suffix=tempfile_extension, encoding="utf8", delete=False
    ) as temp_template:
        doc_serializer(MOCK_TEMPLATE, temp_template.file)

    mock_args = Namespace(path=Path(temp_template.name), output="human-readable")
    do_check(mock_args)

    Path(temp_template.name).unlink()


def test_do_check_bundle_success():
    """
    The CLI should be able to find a template JSON/YAML document in a provided directory
    """
    temp_template = None

    with tempfile.TemporaryDirectory() as temp_bundle:
        with tempfile.NamedTemporaryFile(
            mode="w+t",
            suffix=".template.json",
            encoding="utf8",
            delete=False,
            dir=temp_bundle,
        ) as temp_template:
            json.dump(MOCK_TEMPLATE, temp_template.file)

        mock_args = Namespace(path=Path(temp_bundle), output="human-readable")
        do_check(mock_args)


def test_do_check_file_error():
    """
    Raise a SystemExit on an error
    (RunTime and DecodeValidation errors are treated the same;
    in this case we just test an incorrect filename that gets
    handled in read_template)
    """
    mock_args = Namespace(path=Path("error-file.json"), output="human-readable")
    with pytest.raises(SystemExit):
        do_check(mock_args)


def test_do_check_bundle_error():
    """
    Test that passing a bundle with no template file yields a SystemError
    """
    with tempfile.TemporaryDirectory() as temp_bundle:
        mock_args = Namespace(path=Path(temp_bundle), output="human-readable")
        with pytest.raises(SystemExit):
            do_check(mock_args)
