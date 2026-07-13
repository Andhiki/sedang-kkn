from datetime import date, datetime, timedelta, timezone

import pytest

from utils.proker_presensi import (
    _filter_future_sub_entries,
    _filter_to_today,
    _is_future_sub_entry,
    _is_today_sub_entry,
    _parse_sub_entry_start,
)

WIB = timezone(timedelta(hours=7))


class TestParseSubEntryStart:
    def test_parse_indonesian_range(self):
        result = _parse_sub_entry_start("2 Juli 2026 17:00 - 18:00 WIB")
        assert result == datetime(2026, 7, 2, 17, 0, tzinfo=WIB)

    def test_parse_indonesian_single(self):
        result = _parse_sub_entry_start("15 Agustus 2026 09:30")
        assert result == datetime(2026, 8, 15, 9, 30, tzinfo=WIB)

    def test_parse_invalid_returns_none(self):
        assert _parse_sub_entry_start("N/A") is None
        assert _parse_sub_entry_start("") is None
        assert _parse_sub_entry_start("invalid") is None
        assert _parse_sub_entry_start("32 Januari 2026 10:00") is None


class TestIsFutureSubEntry:
    def test_future_entry(self):
        now = datetime(2026, 7, 2, 10, 0, tzinfo=WIB)
        item = {"date": "2 Juli 2026 17:00 - 18:00 WIB"}
        assert _is_future_sub_entry(item, now) is True

    def test_past_entry(self):
        now = datetime(2026, 7, 2, 18, 0, tzinfo=WIB)
        item = {"date": "2 Juli 2026 17:00 - 18:00 WIB"}
        assert _is_future_sub_entry(item, now) is False

    def test_exact_now_is_not_future(self):
        now = datetime(2026, 7, 2, 17, 0, tzinfo=WIB)
        item = {"date": "2 Juli 2026 17:00 - 18:00 WIB"}
        assert _is_future_sub_entry(item, now) is False

    def test_invalid_date_defaults_to_not_future(self):
        now = datetime(2026, 7, 2, 10, 0, tzinfo=WIB)
        item = {"date": "N/A"}
        assert _is_future_sub_entry(item, now) is False


class TestFilterFutureSubEntries:
    def test_filters_future_and_keeps_past(self):
        now = datetime(2026, 7, 2, 14, 0, tzinfo=WIB)
        items = [
            {"date": "2 Juli 2026 17:00 - 18:00 WIB"},
            {"date": "2 Juli 2026 09:00 - 10:00 WIB"},
            {"date": "2 Juli 2026 14:00 - 15:00 WIB"},
        ]
        filtered, skipped = _filter_future_sub_entries(items, now)
        assert len(filtered) == 2
        assert skipped == 1
        assert filtered[0]["date"] == "2 Juli 2026 09:00 - 10:00 WIB"
        assert filtered[1]["date"] == "2 Juli 2026 14:00 - 15:00 WIB"

    def test_empty_list(self):
        filtered, skipped = _filter_future_sub_entries([])
        assert filtered == []
        assert skipped == 0

    def test_all_future(self):
        now = datetime(2026, 7, 2, 7, 0, tzinfo=WIB)
        items = [
            {"date": "2 Juli 2026 17:00 - 18:00 WIB"},
            {"date": "2 Juli 2026 09:00 - 10:00 WIB"},
        ]
        filtered, skipped = _filter_future_sub_entries(items, now)
        assert filtered == []
        assert skipped == 2

    def test_uses_now_default(self):
        items = [{"date": "1 Januari 2099 00:00"}]
        filtered, skipped = _filter_future_sub_entries(items)
        assert filtered == []
        assert skipped == 1


class TestIsTodaySubEntry:
    def test_today_entry(self):
        today = date(2026, 7, 2)
        item = {"date": "2 Juli 2026 17:00 - 18:00 WIB"}
        assert _is_today_sub_entry(item, today) is True

    def test_past_entry(self):
        today = date(2026, 7, 3)
        item = {"date": "2 Juli 2026 17:00 - 18:00 WIB"}
        assert _is_today_sub_entry(item, today) is False

    def test_future_entry(self):
        today = date(2026, 7, 1)
        item = {"date": "2 Juli 2026 17:00 - 18:00 WIB"}
        assert _is_today_sub_entry(item, today) is False

    def test_invalid_date_defaults_to_not_today(self):
        today = date(2026, 7, 2)
        item = {"date": "N/A"}
        assert _is_today_sub_entry(item, today) is False


class TestFilterToToday:
    def test_keeps_only_today(self):
        today = date(2026, 7, 2)
        items = [
            {"date": "2 Juli 2026 17:00 - 18:00 WIB"},
            {"date": "1 Juli 2026 09:00 - 10:00 WIB"},
            {"date": "3 Juli 2026 14:00 - 15:00 WIB"},
            {"date": "2 Juli 2026 08:00 - 09:00 WIB"},
        ]
        filtered, dropped = _filter_to_today(items, today)
        assert len(filtered) == 2
        assert dropped == 2
        assert filtered[0]["date"] == "2 Juli 2026 17:00 - 18:00 WIB"
        assert filtered[1]["date"] == "2 Juli 2026 08:00 - 09:00 WIB"

    def test_empty_list(self):
        filtered, dropped = _filter_to_today([])
        assert filtered == []
        assert dropped == 0

    def test_none_today(self):
        today = date(2026, 7, 5)
        items = [
            {"date": "2 Juli 2026 17:00 - 18:00 WIB"},
            {"date": "3 Juli 2026 09:00 - 10:00 WIB"},
        ]
        filtered, dropped = _filter_to_today(items, today)
        assert filtered == []
        assert dropped == 2

    def test_all_today(self):
        today = date(2026, 7, 2)
        items = [
            {"date": "2 Juli 2026 17:00 - 18:00 WIB"},
            {"date": "2 Juli 2026 09:00 - 10:00 WIB"},
        ]
        filtered, dropped = _filter_to_today(items, today)
        assert len(filtered) == 2
        assert dropped == 0

    def test_invalid_dates_dropped(self):
        today = date(2026, 7, 2)
        items = [{"date": "N/A"}, {"date": ""}, {"date": "invalid"}]
        filtered, dropped = _filter_to_today(items, today)
        assert filtered == []
        assert dropped == 3