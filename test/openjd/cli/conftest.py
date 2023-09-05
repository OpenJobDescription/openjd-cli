# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.

import pytest
from unittest.mock import patch

from . import MOCK_TEMPLATE, SampleSteps
from openjd.cli._common._job_from_template import job_from_template
from openjd.cli._run._local_session._session_manager import LocalSession
from openjd.model import decode_template


@pytest.fixture(scope="function", params=[[], ["Message='A new message!'"]])
def sample_job(request):
    """
    Uses the MOCK_TEMPLATE object to create a Job, once
    with default parameters and once with user-specified parameters.
    """
    template = decode_template(template=MOCK_TEMPLATE)
    return job_from_template(template=template, parameter_args=request.param)


@pytest.fixture(scope="function")
def sample_step_map(sample_job):
    return {step.name: step for step in sample_job.steps}


@pytest.fixture(
    scope="function",
    params=[
        pytest.param([], SampleSteps.NormalStep, -1, 2, 1, id="Basic step"),
        pytest.param(
            [SampleSteps.BareStep], SampleSteps.DependentStep, -1, 1, 2, id="Direct dependency"
        ),
        pytest.param(
            [
                SampleSteps.BareStep,
                SampleSteps.DependentStep,
                SampleSteps.TaskParamStep,
            ],
            SampleSteps.ExtraDependentStep,
            -1,
            1,
            6,
            id="Dependencies and Task parameters",
        ),
        pytest.param(
            [SampleSteps.BareStep, SampleSteps.DependentStep, SampleSteps.TaskParamStep],
            SampleSteps.ExtraDependentStep,
            1,
            1,
            6,
            id="No maximum on dependencies' Tasks",
        ),
        pytest.param([], SampleSteps.TaskParamStep, 1, 1, 1, id="Limit on maximum Task parameters"),
        pytest.param(
            [], SampleSteps.TaskParamStep, 100, 1, 3, id="Maximum Task parameters more than defined"
        ),
    ],
)
def session_parameters(request):
    """
    Tests for `LocalSession.initialize` and `LocalSession.run` use the same
    test parameters, so we create a fixture that returns them.
    """
    return request.param


@pytest.fixture(scope="function")
def patched_session_cleanup():
    """
    Patches the `cleanup` function in a LocalSession, but uses the
    original function as a side effect to track how many times it
    gets called.
    We use this to verify that Sessions are properly cleaned up
    after exiting on a success or error.
    """
    with patch.object(
        LocalSession, "cleanup", autospec=True, side_effect=LocalSession.cleanup
    ) as patched_cleanup:
        yield patched_cleanup
