import pandas as pd
import pytest

from app.core.enums import Platform
from app.core.exceptions import InvalidDatasetError, UnsupportedFileTypeError
from app.ingestion.mapping import suggest_mappings
from app.ingestion.normalizer import normalize_table
from app.ingestion.parsers import (
    duration_unit_factor,
    normalize_percent,
    parse_datetime_series,
    parse_duration,
    parse_number,
)
from app.ingestion.platform_detection import detect_platform
from app.ingestion.profiling import profile_table
from app.ingestion.readers import read_table
from tests.fixtures import FACEBOOK_CSV, INSTAGRAM_CSV, TIKTOK_CSV, linkedin_xlsx


class TestParsers:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("1,234", 1234.0),
            ("1.234", 1.234),
            ("4.210", 4.21),  # ambiguous alone; locale handled at column level only via ',' rules
            ("1.234,5", 1234.5),
            ("1,234.5", 1234.5),
            ("12,5", 12.5),
            ("1.2K", 1200.0),
            ("3M", 3_000_000.0),
            ("12%", 12.0),
            ("(40)", -40.0),
            ("1 234", 1234.0),
            ("-", None),
            ("N/A", None),
            ("abc", None),
            (42, 42.0),
        ],
    )
    def test_parse_number(self, raw: object, expected: float | None) -> None:
        assert parse_number(raw) == expected

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("0:45", 45.0),
            ("1:02:03", 3723.0),
            ("45s", 45.0),
            ("1m 5s", 65.0),
            ("2h", 7200.0),
            ("12.5", 12.5),
            ("", None),
        ],
    )
    def test_parse_duration(self, raw: object, expected: float | None) -> None:
        assert parse_duration(raw) == expected

    def test_duration_units_from_header(self) -> None:
        assert duration_unit_factor("Total play time (h)") == 3600
        assert duration_unit_factor("Watch time (minutes)") == 60
        assert duration_unit_factor("Average watch time") == 1

    def test_fraction_percent_scaled(self) -> None:
        assert normalize_percent(pd.Series([0.1, 0.5])).tolist() == [10.0, 50.0]
        assert normalize_percent(pd.Series([10.0, 50.0])).tolist() == [10.0, 50.0]

    def test_dayfirst_detection_and_timezone(self) -> None:
        s = pd.Series(["25/03/2025 10:00", "02/04/2025 18:30"])
        parsed, has_time = parse_datetime_series(s, "Asia/Dubai")
        assert has_time
        assert parsed.iloc[0].month == 3 and parsed.iloc[0].day == 25
        # 10:00 Dubai == 06:00 UTC
        assert parsed.iloc[0].hour == 6

    def test_date_only_has_no_time(self) -> None:
        _, has_time = parse_datetime_series(pd.Series(["2025-09-01", "2025-09-02"]))
        assert not has_time


class TestReaders:
    def test_csv_semicolon(self) -> None:
        table = read_table(FACEBOOK_CSV.encode(), ".csv")
        assert table.delimiter == ";"
        assert len(table.df) == 4
        assert "Reactions" in table.df.columns

    def test_utf16_csv(self) -> None:
        table = read_table(TIKTOK_CSV.encode("utf-16"), ".csv")
        assert len(table.df) == 3

    def test_xlsx_picks_post_sheet_and_skips_description_row(self) -> None:
        table = read_table(linkedin_xlsx(), ".xlsx")
        assert table.sheet_name == "All posts"
        assert table.header_row == 1
        assert list(table.df.columns)[:3] == ["Update title", "Update link", "Update type"]
        assert len(table.df) == 3

    def test_rejects_unsupported_and_empty(self) -> None:
        with pytest.raises(UnsupportedFileTypeError):
            read_table(b"x", ".json")
        with pytest.raises(InvalidDatasetError):
            read_table(b"   ", ".csv")
        with pytest.raises(InvalidDatasetError):
            read_table(b"a,b,c\n", ".csv")

    def test_duplicate_columns_renamed(self) -> None:
        table = read_table(b"Likes,Likes,Date\n1,2,2025-01-01\n", ".csv")
        assert table.duplicate_columns == ["Likes"]
        assert list(table.df.columns) == ["Likes", "Likes (2)", "Date"]


class TestDetectionAndMapping:
    @pytest.mark.parametrize(
        ("content", "ext", "expected"),
        [
            (INSTAGRAM_CSV.encode(), ".csv", Platform.INSTAGRAM),
            (FACEBOOK_CSV.encode(), ".csv", Platform.FACEBOOK),
            (TIKTOK_CSV.encode(), ".csv", Platform.TIKTOK),
            (linkedin_xlsx(), ".xlsx", Platform.LINKEDIN),
        ],
    )
    def test_detects_platform_without_filename_hint(self, content: bytes, ext: str, expected: Platform) -> None:
        df = read_table(content, ext).df
        det = detect_platform(df, "export" + ext)
        assert det.platform == expected, det.scores
        assert det.confidence > 0.3

    def test_filename_hint_helps(self) -> None:
        df = pd.DataFrame({"Date": ["2025-01-01"], "Likes": ["3"]})
        assert detect_platform(df, "tiktok_export.csv").platform == Platform.TIKTOK

    def _mapping(self, content: bytes, ext: str, platform: Platform) -> dict[str, str | None]:
        df = read_table(content, ext).df
        return {s.source_column: s.target_field for s in suggest_mappings(profile_table(df), platform)}

    def test_instagram_mapping(self) -> None:
        m = self._mapping(INSTAGRAM_CSV.encode(), ".csv", Platform.INSTAGRAM)
        assert m["Publish time"] == "published_at"
        assert m["Reach"] == "reach"
        assert m["Saves"] == "saves"
        assert m["Description"] == "caption"
        assert m["Follows"] == "followers_gained"
        assert m["Duration (sec)"] == "video_duration_seconds"
        assert m["Post ID"] == "external_post_id"
        assert m["Account username"] is None

    def test_tiktok_mapping(self) -> None:
        m = self._mapping(TIKTOK_CSV.encode(), ".csv", Platform.TIKTOK)
        assert m["Video views"] == "views"
        assert m["Reached audience"] == "reach"
        assert m["Add to Favorites"] == "saves"
        assert m["Total play time (h)"] == "watch_time_seconds"
        assert m["Average watch time"] == "average_watch_time_seconds"
        assert m["Watched full video"] == "completion_rate"
        assert m["Video title"] == "caption"

    def test_linkedin_mapping(self) -> None:
        m = self._mapping(linkedin_xlsx(), ".xlsx", Platform.LINKEDIN)
        assert m["Reposts"] == "shares"
        assert m["Reactions"] == "likes"
        assert m["Update type"] == "paid_or_organic"
        assert m["Created date"] == "published_at"
        assert m["Update title"] == "caption"

    def test_each_field_mapped_once(self) -> None:
        df = read_table(FACEBOOK_CSV.encode(), ".csv").df
        targets = [s.target_field for s in suggest_mappings(profile_table(df), Platform.FACEBOOK) if s.target_field]
        assert len(targets) == len(set(targets))

    def test_non_numeric_column_not_mapped_to_metric(self) -> None:
        df = pd.DataFrame({"Reach": ["high", "low", "medium"], "Date": ["2025-01-01"] * 3})
        m = {s.source_column: s.target_field for s in suggest_mappings(profile_table(df))}
        assert m["Reach"] is None


class TestNormalization:
    def _normalize(self, content: bytes, ext: str, platform: Platform, tz: str = "UTC"):  # type: ignore[no-untyped-def]
        df = read_table(content, ext).df
        mapping = {
            s.source_column: s.target_field for s in suggest_mappings(profile_table(df), platform) if s.target_field
        }
        return normalize_table(df, mapping, platform, tz)

    def test_instagram_cleaning(self) -> None:
        res = self._normalize(INSTAGRAM_CSV.encode(), ".csv", Platform.INSTAGRAM)
        codes = {i.code for i in res.report.issues}
        assert {"duplicate_posts", "invalid_dates", "negative_values"} <= codes
        assert res.report.is_valid
        assert len(res.posts) == 5  # 7 rows - 1 duplicate - 1 invalid date
        formats = dict(zip(res.posts["external_post_id"], res.posts["content_format"], strict=True))
        assert formats["1790001"] == "reel"
        assert formats["1790003"] == "carousel"
        assert formats["1790002"] == "image"
        assert res.posts.loc[res.posts.external_post_id == "1790006", "likes"].isna().all()
        assert res.posts.loc[res.posts.external_post_id == "1790001", "hashtags"].iloc[0] == ["marketing", "tips"]

    def test_facebook_eu_thousands(self) -> None:
        res = self._normalize(FACEBOOK_CSV.encode(), ".csv", Platform.FACEBOOK)
        assert res.posts["reach"].tolist() == [4210, 6800, 2150, 1980]
        assert res.posts["content_format"].tolist() == ["image", "video", "link", "text"]

    def test_tiktok_units_and_percent(self) -> None:
        res = self._normalize(TIKTOK_CSV.encode(), ".csv", Platform.TIKTOK)
        first = res.posts.iloc[0]
        assert first["watch_time_seconds"] == pytest.approx(110.5 * 3600)
        assert first["completion_rate"] == pytest.approx(31.2)
        assert first["video_duration_seconds"] == 22
        assert res.posts["content_format"].tolist() == ["short_video", "short_video", "video"]
        # No post id column -> generated stable ids
        assert all(i.startswith("gen_") for i in res.posts["external_post_id"])
        assert any(i.code == "missing_post_id" for i in res.report.issues)

    def test_linkedin_date_only_and_paid_flag(self) -> None:
        res = self._normalize(linkedin_xlsx(), ".xlsx", Platform.LINKEDIN)
        assert not res.has_time
        assert res.posts["paid_or_organic"].tolist() == ["organic", "organic", "paid"]
        assert res.posts["content_format"].tolist() == ["text", "text", "text"]

    def test_missing_date_mapping_is_error(self) -> None:
        df = pd.DataFrame({"Likes": ["1", "2"]})
        res = normalize_table(df, {"Likes": "likes"}, Platform.INSTAGRAM)
        assert not res.report.is_valid

    def test_no_metrics_is_error(self) -> None:
        df = pd.DataFrame({"Date": ["2025-01-01"], "Caption": ["hi"]})
        res = normalize_table(df, {"Date": "published_at", "Caption": "caption"}, Platform.INSTAGRAM)
        assert not res.report.is_valid
        assert any(i.code == "no_metrics" for i in res.report.issues)

    def test_impossible_percentage_nulled(self) -> None:
        df = pd.DataFrame(
            {"Date": ["2025-01-01", "2025-01-02"], "Views": ["10", "20"], "Completion rate": ["150", "40"]}
        )
        res = normalize_table(
            df, {"Date": "published_at", "Views": "views", "Completion rate": "completion_rate"}, Platform.TIKTOK
        )
        assert res.posts["completion_rate"].isna().iloc[0]
        assert any(i.code == "impossible_percentage" for i in res.report.issues)

    def test_followers_lifted_to_snapshots(self) -> None:
        df = pd.DataFrame(
            {
                "Date": ["2025-01-01 10:00", "2025-01-01 18:00", "2025-01-02 09:00"],
                "Likes": ["1", "2", "3"],
                "Followers": ["100", "105", "110"],
            }
        )
        res = normalize_table(
            df, {"Date": "published_at", "Likes": "likes", "Followers": "followers"}, Platform.INSTAGRAM
        )
        assert res.snapshots["followers"].tolist() == [105, 110]


def test_iso_offsets_are_respected() -> None:
    parsed, has_time = parse_datetime_series(
        pd.Series(["2025-09-01T19:00:00+04:00", "2025-09-02T08:00:00Z"]), "Europe/Paris"
    )
    assert has_time
    assert parsed.iloc[0].hour == 15 and parsed.iloc[1].hour == 8


def test_constant_column_is_not_an_id() -> None:
    df = pd.DataFrame({"Posted by": ["Acme"] * 5, "Date": [f"2025-01-0{i}" for i in range(1, 6)], "Likes": ["1"] * 5})
    m = {s.source_column: s.target_field for s in suggest_mappings(profile_table(df))}
    assert m["Posted by"] is None
