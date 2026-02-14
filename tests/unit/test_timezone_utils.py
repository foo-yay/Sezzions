"""Tests for timezone_utils conversions (Issue #107)."""
from datetime import date

from tools.timezone_utils import (
    local_date_time_to_utc,
    local_date_range_to_utc_bounds,
    utc_date_time_to_local,
)


def test_local_to_utc_conversion():
    utc_date, utc_time = local_date_time_to_utc(
        date(2026, 2, 13),
        "20:30:00",
        "America/Los_Angeles",
    )
    assert utc_date == "2026-02-14"
    assert utc_time == "04:30:00"


def test_round_trip_local_to_utc_to_local():
    local_date = date(2026, 2, 13)
    local_time = "20:30:00"
    utc_date, utc_time = local_date_time_to_utc(local_date, local_time, "America/Los_Angeles")
    round_trip_date, round_trip_time = utc_date_time_to_local(
        utc_date,
        utc_time,
        "America/Los_Angeles",
    )
    assert round_trip_date == local_date
    assert round_trip_time == local_time


def test_local_date_range_to_utc_bounds():
    start_utc, end_utc = local_date_range_to_utc_bounds(
        date(2026, 2, 13),
        date(2026, 2, 13),
        "America/Los_Angeles",
    )
    assert start_utc == ("2026-02-13", "08:00:00")
    assert end_utc == ("2026-02-14", "07:59:59")
