from datetime import datetime, timedelta, timezone

import pytest

from utils.proker_presensi import _filter_future_sub_entries, _is_future_sub_entry, _parse_sub_entry_start

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
