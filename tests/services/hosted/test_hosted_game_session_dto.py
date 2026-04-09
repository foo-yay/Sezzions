"""Tests for HostedGameSession DTO validation."""

import pytest

from services.hosted.models import HostedGameSession


def test_valid_dto_creates_successfully():
    gs = HostedGameSession(user_id="u1", site_id="s1", session_date="2026-01-15")
    assert gs.user_id == "u1"
    assert gs.site_id == "s1"
    assert gs.session_date == "2026-01-15"
    assert gs.session_time == "00:00:00"
    assert gs.status == "Active"
    assert gs.starting_balance == "0.00"


def test_missing_user_id_raises():
    with pytest.raises(ValueError, match="User is required"):
        HostedGameSession(user_id="", site_id="s1", session_date="2026-01-15")


def test_missing_site_id_raises():
    with pytest.raises(ValueError, match="Site is required"):
        HostedGameSession(user_id="u1", site_id="", session_date="2026-01-15")


def test_missing_session_date_raises():
    with pytest.raises(ValueError, match="Session date is required"):
        HostedGameSession(user_id="u1", site_id="s1", session_date="")


def test_whitespace_only_session_date_raises():
    with pytest.raises(ValueError, match="Session date is required"):
        HostedGameSession(user_id="u1", site_id="s1", session_date="   ")


def test_strips_session_date():
    gs = HostedGameSession(user_id="u1", site_id="s1", session_date="  2026-01-15  ")
    assert gs.session_date == "2026-01-15"


def test_strips_session_time():
    gs = HostedGameSession(
        user_id="u1", site_id="s1", session_date="2026-01-15",
        session_time="  14:30:00  ",
    )
    assert gs.session_time == "14:30:00"


def test_empty_notes_normalized_to_none():
    gs = HostedGameSession(user_id="u1", site_id="s1", session_date="2026-01-15", notes="  ")
    assert gs.notes is None


def test_as_dict_returns_all_fields():
    gs = HostedGameSession(
        user_id="u1", site_id="s1", session_date="2026-01-15",
        game_id="g1", game_type_id="gt1", end_date="2026-01-15",
        end_time="18:00:00", starting_balance="100.00",
        ending_balance="200.00", wager_amount="50.00",
        status="Closed", notes="test notes", id="id1",
    )
    d = gs.as_dict()
    assert d["id"] == "id1"
    assert d["user_id"] == "u1"
    assert d["site_id"] == "s1"
    assert d["session_date"] == "2026-01-15"
    assert d["game_id"] == "g1"
    assert d["game_type_id"] == "gt1"
    assert d["end_date"] == "2026-01-15"
    assert d["end_time"] == "18:00:00"
    assert d["starting_balance"] == "100.00"
    assert d["ending_balance"] == "200.00"
    assert d["wager_amount"] == "50.00"
    assert d["status"] == "Closed"
    assert d["notes"] == "test notes"
    assert "deleted_at" not in d  # deleted_at is internal, not in as_dict
