import importlib

import pytest

from researchflow.settings import Settings


def module():
    try:
        return importlib.import_module('researchflow.release')
    except ModuleNotFoundError:
        pytest.fail('real release validation manifest is not implemented')


def test_release_gate_cannot_count_skipped_or_failed_tests_as_passed(tmp_path):
    release=module()
    report=tmp_path/'junit.xml'
    report.write_text('<testsuites><testsuite><testcase classname="tests.integration.test_step_commit" name="atomic_commit"><skipped message="PostgreSQL missing"/></testcase></testsuite></testsuites>')
    assert release.scenario_status(report,('test_step_commit',))=='blocked'
    report.write_text('<testsuites><testsuite><testcase classname="tests.integration.test_step_commit" name="atomic_commit"><failure message="commit failed"/></testcase></testsuite></testsuites>')
    assert release.scenario_status(report,('test_step_commit',))=='failed'
    report.write_text('<testsuites><testsuite><testcase classname="tests.integration.test_step_commit" name="atomic_commit"/></testsuite></testsuites>')
    assert release.scenario_status(report,('test_step_commit',))=='passed'
    assert release.scenario_status(report,('test_worker_restart',))=='not_run'


def test_unconfigured_server_cannot_bind_external_interface():
    with pytest.raises(ValueError):
        Settings('postgresql+psycopg://fixture').validate_binding('0.0.0.0')
