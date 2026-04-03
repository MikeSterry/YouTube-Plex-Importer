from __future__ import annotations

import pytest

from app.models.domain import ChapterEntry
from app.services.chapter_service import ChapterService


@pytest.fixture()
def service():
    return ChapterService()


@pytest.mark.parametrize("raw_text", [None, "", "   ", "\n\n  \n"])
def test_parse_returns_empty_list_for_blank_input(service, raw_text):
    assert service.parse(raw_text) == []


def test_parse_returns_normalized_chapter_entries(service):
    raw_text = """
    0:00 - Intro
    01:23:45 — Finale
    12:34: Song Title
    """

    result = service.parse(raw_text)

    assert result == [
        ChapterEntry(index=1, timestamp="00:00:00.000", title="Intro"),
        ChapterEntry(index=2, timestamp="01:23:45.000", title="Finale"),
        ChapterEntry(index=3, timestamp="00:12:34.000", title="Song Title"),
    ]


def test_parse_ignores_blank_lines_and_strips_whitespace(service):
    raw_text = """

      0:00 - Intro

      3:21 - Middle

      9:59 - End

    """

    result = service.parse(raw_text)

    assert result == [
        ChapterEntry(index=1, timestamp="00:00:00.000", title="Intro"),
        ChapterEntry(index=2, timestamp="00:03:21.000", title="Middle"),
        ChapterEntry(index=3, timestamp="00:09:59.000", title="End"),
    ]


@pytest.mark.parametrize(
    ("line", "expected_timestamp", "expected_title"),
    [
        ("0:00 - Intro", "00:00:00.000", "Intro"),
        ("0:00: Intro", "00:00:00.000", "Intro"),
        ("Intro - 0:00", "00:00:00.000", "Intro"),
        ("1:02:03 - Long Song", "01:02:03.000", "Long Song"),
        ("Track Name — 12:34", "00:12:34.000", "Track Name"),
        ("12:34 – Track Name", "00:12:34.000", "Track Name"),
    ],
)
def test_extract_parts_handles_flexible_formats(service, line, expected_timestamp, expected_title):
    timestamp, title = service._extract_parts(line)

    assert timestamp == expected_timestamp
    assert title == expected_title


@pytest.mark.parametrize(
    "raw_text",
    [
        "Intro only",
        "No timestamp here either",
    ],
)
def test_parse_raises_for_line_without_timestamp(service, raw_text):
    with pytest.raises(ValueError, match="Unable to parse chapter line"):
        service.parse(raw_text)


@pytest.mark.parametrize(
    "line",
    [
        "0:00",
        "0:00 - ",
        " - 0:00",
        "0:00:   ",
    ],
)
def test_extract_parts_raises_when_title_missing(service, line):
    with pytest.raises(ValueError, match="Chapter title missing"):
        service._extract_parts(line)


def test_to_metadata_text_renders_ffmetadata_style_lines(service):
    chapters = [
        ChapterEntry(index=1, timestamp="00:00:00.000", title="Intro"),
        ChapterEntry(index=2, timestamp="00:03:21.000", title="Middle"),
    ]

    result = service.to_metadata_text(chapters)

    assert result == (
        "CHAPTER01=00:00:00.000\n"
        "CHAPTER01NAME=Intro\n"
        "CHAPTER02=00:03:21.000\n"
        "CHAPTER02NAME=Middle\n"
    )


def test_to_metadata_text_returns_newline_for_empty_chapters(service):
    assert service.to_metadata_text([]) == "\n"


def test_non_empty_lines_strips_and_filters_blank_lines(service):
    raw_text = "  first  \n\n second\n   \nthird   "

    assert service._non_empty_lines(raw_text) == ["first", "second", "third"]


@pytest.mark.parametrize(
    ("line", "raw_time", "expected"),
    [
        ("0:00 - Intro", "0:00", "Intro"),
        ("0:00: Intro", "0:00", "Intro"),
        ("Intro - 0:00", "0:00", "Intro"),
        ("Intro — 0:00", "0:00", "Intro"),
        ("  Intro   -   0:00  ", "0:00", "Intro"),
    ],
)
def test_remove_time_and_separators_cleans_title(service, line, raw_time, expected):
    assert service._remove_time_and_separators(line, raw_time) == expected