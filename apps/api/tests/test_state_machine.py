import pytest
from app.services.deployment import VALID_STATES, TRANSITIONS, DeploymentService


def test_valid_states_exist():
    assert "queued" in VALID_STATES
    assert "running" in VALID_STATES
    assert "clone_failed" in VALID_STATES


def test_queued_to_cloning():
    assert "cloning" in TRANSITIONS["queued"]


def test_cloning_to_analyzing():
    assert "analyzing" in TRANSITIONS["cloning"]


def test_cloning_to_failed():
    assert "clone_failed" in TRANSITIONS["cloning"]


def test_analyzing_to_planning():
    assert "planning" in TRANSITIONS["analyzing"]


def test_planning_to_building():
    assert "building" in TRANSITIONS["planning"]


def test_building_to_starting():
    assert "starting" in TRANSITIONS["building"]


def test_starting_to_health_checking():
    assert "health_checking" in TRANSITIONS["starting"]


def test_health_checking_to_running():
    assert "running" in TRANSITIONS["health_checking"]


def test_running_is_terminal():
    assert "running" not in TRANSITIONS


def test_cannot_skip_states():
    assert "building" not in TRANSITIONS["queued"]


def test_cannot_go_backwards():
    assert "queued" not in TRANSITIONS.get("running", set())
