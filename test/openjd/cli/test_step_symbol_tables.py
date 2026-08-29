# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
"""The create-time step symbol table's path from job creation into a session.

A step's template-scope ``let`` (RFC 0005 §3.6) is evaluated once, at job
creation. openjd-model does not merge the resolved bindings into ``script.let``
and openjd-sessions does not re-evaluate the source expressions, so the only
channel those values have into a session is the ``resolved_symtab`` argument on
``Session.enter_environment``, ``Session.run_task`` and
``Session.exit_environment``. A CLI that forwards nothing produces a step whose
``let`` names are simply undefined -- not stale, absent.

These tests pin the forwarding at each of the three call sites, and the
end-to-end result of all three together.
"""

from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
import yaml

from . import format_capsys_outerr, run_openjd_cli_main
from openjd.cli._common import SUPPORTED_EXTENSIONS
from openjd.cli._common._job_from_template import job_from_template
from openjd.cli._run._local_session._session_manager import EnvironmentType, LocalSession
from openjd.model import (
    RevisionExtensions,
    StepParameterSpaceIterator,
    decode_job_template,
)
from openjd.sessions import Session

TEMPLATE_PATH = Path(__file__).parent / "templates" / "step_let_symtab_job.yaml"
STEP_NAME = "EchoStepLet"
# The resolved value of the template's `bucket = "assets-" + Param.Region`
# binding, under the Region parameter's default.
EXPECTED_BUCKET = "assets-us-west-2"


@pytest.fixture
def step_let_job(tmp_path: Path) -> Any:
    """The step-``let`` job, together with its per-step resolved symbol tables.

    Deliberately a real ``job_from_template`` call rather than a stub table: the
    point under test is that the values the model resolves at job creation reach
    the session, and a hand-built table would not exercise that.
    """
    template = decode_job_template(
        template=yaml.safe_load(TEMPLATE_PATH.read_text()),
        supported_extensions=SUPPORTED_EXTENSIONS,
    )
    job, parameters, step_symbol_tables = job_from_template(
        template=template,
        environments=[],
        parameter_args=[],
        job_template_dir=tmp_path,
        current_working_dir=tmp_path,
    )
    return job, parameters, step_symbol_tables


def _local_session(job, parameters, step_symbol_tables, session_id: str) -> LocalSession:
    """A LocalSession built the way ``do_run`` builds one for this job.

    ``revision_extensions`` must carry the extensions the job declares, or the
    session parses the step's EXPR constructs against the default surface.
    """
    return LocalSession(
        job=job,
        job_parameter_values=parameters,
        session_id=session_id,
        step_symbol_tables=step_symbol_tables,
        revision_extensions=RevisionExtensions(
            spec_rev=job.revision, supported_extensions=list(job.extensions or [])
        ),
    )


def test_the_model_resolves_the_step_let_into_the_step_table(step_let_job) -> None:
    """Precondition for the three forwarding tests: the table is worth sending.

    Not a forwarding test. It pins that ``create_job_with_symbol_tables``
    returns a table for the step, keyed by step name, carrying the step's
    resolved ``let`` -- so a later forwarding test that finds nothing has a
    forwarding bug rather than an empty producer.
    """
    _, _, step_symbol_tables = step_let_job

    assert STEP_NAME in step_symbol_tables
    symbols = step_symbol_tables[STEP_NAME].to_symtab().symbols
    assert "bucket" in symbols


def test_run_task_forwards_the_steps_resolved_symtab(step_let_job) -> None:
    """``Session.run_task`` receives the table for the step being run.

    Spied rather than stubbed, and driven through ``run_step``: the real
    ``Session.run_task`` is what eventually fires the action-status callback
    that ``LocalSession.run_task`` blocks on, so a no-op stub deadlocks.
    """
    job, parameters, step_symbol_tables = step_let_job
    step = next(s for s in job.steps if s.name == STEP_NAME)
    parameter_set = next(iter(StepParameterSpaceIterator(space=step.parameterSpace)))

    with patch.object(
        Session, "run_task", autospec=True, side_effect=Session.run_task
    ) as patched_run_task:
        with _local_session(job, parameters, step_symbol_tables, "run-task-symtab") as session:
            session.run_step(step, task_parameters=[parameter_set])

    assert not session.failed
    patched_run_task.assert_called_once()
    forwarded = patched_run_task.call_args.kwargs["resolved_symtab"]
    # Identity, not merely truthiness: the step's own table, not another step's
    # and not a rebuilt one.
    assert forwarded is step_symbol_tables[STEP_NAME]


def test_step_env_enter_forwards_the_steps_resolved_symtab(step_let_job) -> None:
    """A step environment is entered with its owning step's table.

    The job/external assertion at the end is a negative control: it cannot fail
    against a revert of the forwarding (a revert makes *every* enter get no
    table, which is what it asserts for these). It guards the other direction --
    forwarding one step's table to job or external environments, which are
    outside step scope.
    """
    job, parameters, step_symbol_tables = step_let_job
    step = next(s for s in job.steps if s.name == STEP_NAME)

    with patch.object(
        Session, "enter_environment", autospec=True, side_effect=Session.enter_environment
    ) as patched_enter:
        with _local_session(job, parameters, step_symbol_tables, "enter-symtab") as session:
            session.run_step(step)

    assert not session.failed

    step_prefix = f"{EnvironmentType.STEP.name} - "
    step_env_calls = [
        c for c in patched_enter.call_args_list if c.kwargs["identifier"].startswith(step_prefix)
    ]
    assert step_env_calls
    for enter_call in step_env_calls:
        assert enter_call.kwargs["resolved_symtab"] is step_symbol_tables[STEP_NAME]

    for enter_call in patched_enter.call_args_list:
        if not enter_call.kwargs["identifier"].startswith(step_prefix):
            assert enter_call.kwargs.get("resolved_symtab") is None


def test_step_env_exit_forwards_the_table_the_enter_used(step_let_job) -> None:
    """A step environment's exit receives the same table its enter did.

    ``Session.exit_environment`` documents that as what makes an ``onExit``
    resolve in the same scope as its ``onEnter``. Identity against the enter's
    argument rather than against the mapping, so a second lookup that happened
    to return an equal-but-distinct table would still be visible.
    """
    job, parameters, step_symbol_tables = step_let_job
    step = next(s for s in job.steps if s.name == STEP_NAME)

    with (
        patch.object(
            Session, "enter_environment", autospec=True, side_effect=Session.enter_environment
        ) as patched_enter,
        patch.object(
            Session, "exit_environment", autospec=True, side_effect=Session.exit_environment
        ) as patched_exit,
    ):
        with _local_session(job, parameters, step_symbol_tables, "exit-symtab") as session:
            session.run_step(step)

    assert not session.failed

    step_prefix = f"{EnvironmentType.STEP.name} - "
    entered = {
        c.kwargs["identifier"]: c.kwargs["resolved_symtab"]
        for c in patched_enter.call_args_list
        if c.kwargs["identifier"].startswith(step_prefix)
    }
    assert entered

    exited = {
        c.kwargs["identifier"]: c.kwargs.get("resolved_symtab")
        for c in patched_exit.call_args_list
        if c.kwargs["identifier"].startswith(step_prefix)
    }
    assert set(exited) == set(entered)
    for identifier, table in entered.items():
        assert exited[identifier] is table


def test_do_run_step_let_reaches_all_three_action_kinds(
    capsys: pytest.CaptureFixture,
) -> None:
    """End to end: a step-level ``let`` produces its bindings in the session.

    One run covers all three entry points -- the step environment's ``onEnter``
    and ``onExit`` and the task's ``onRun`` each echo the bound value. The
    assertion is on the resolved *value*, so a template-scope binding that
    arrived unevaluated, or as a different step's value, fails here rather than
    passing on mere presence.
    """
    outerr = run_openjd_cli_main(
        capsys,
        args=["run", str(TEMPLATE_PATH), "--step", STEP_NAME],
        expected_exit_code=0,
    )

    for label in ("EnterSawStepLet", "TaskSawStepLet", "ExitSawStepLet"):
        assert (
            f"{label}={EXPECTED_BUCKET}" in outerr.out
        ), f"{label} did not see the step's resolved `let`:\n{format_capsys_outerr(outerr)}"
