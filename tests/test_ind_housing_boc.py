from datetime import datetime
from os.path import dirname, join

import pytest
from city_scrapers_core.constants import BOARD
from city_scrapers_core.utils import file_response
from freezegun import freeze_time

from city_scrapers.spiders.ind_housing_boc import IndHousingBocSpider


@pytest.fixture
def spider():
    return IndHousingBocSpider()


@pytest.fixture
def upcoming_response():
    return file_response(
        join(dirname(__file__), "files", "ind_housing_boc_upcoming.html"),
        url="https://www.indyhousing.org/calendar/boc-meeting-september-15-2026",
    )


@pytest.fixture
def archive_response():
    return file_response(
        join(dirname(__file__), "files", "ind_housing_boc_archive.html"),
        url="https://www.indyhousing.org/news-archives/board-of-commissioners-meeting-february-2026",  # noqa
    )


@pytest.fixture
def upcoming_items(spider, upcoming_response):
    with freeze_time("2026-08-31"):
        return [item for item in spider.parse(upcoming_response)]


@pytest.fixture
def archive_items(spider, archive_response):
    with freeze_time("2026-08-31"):
        return [item for item in spider.parse(archive_response)]


# --- upcoming (calendar) meeting tests -------------------------------------


def test_upcoming_title(upcoming_items):
    assert upcoming_items[0]["title"] == "BOC Meeting"


def test_upcoming_description(upcoming_items):
    assert upcoming_items[0]["description"] == ""


def test_upcoming_start(upcoming_items):
    assert upcoming_items[0]["start"] == datetime(2026, 9, 15, 13, 0)


def test_upcoming_end(upcoming_items):
    assert upcoming_items[0]["end"] is None


def test_upcoming_time_notes(upcoming_items):
    assert upcoming_items[0]["time_notes"] == ""


def test_upcoming_id(upcoming_items):
    assert upcoming_items[0]["id"] == "ind_housing_boc/202609151300/x/boc_meeting"


def test_upcoming_status(upcoming_items):
    assert upcoming_items[0]["status"] == "tentative"


def test_upcoming_location(upcoming_items):
    assert upcoming_items[0]["location"] == {
        "name": "Indianapolis Housing Agency",
        "address": "1935 N. Meridian Street, Indianapolis, IN 46202",
    }


def test_upcoming_source(upcoming_items):
    assert (
        upcoming_items[0]["source"]
        == "https://www.indyhousing.org/calendar/boc-meeting-september-15-2026"
    )


def test_upcoming_links(upcoming_items):
    assert upcoming_items[0]["links"] == []


def test_upcoming_classification(upcoming_items):
    assert upcoming_items[0]["classification"] == BOARD


def test_upcoming_all_day(upcoming_items):
    assert upcoming_items[0]["all_day"] is False


# --- archive (past) meeting tests -------------------------------------------


def test_archive_title(archive_items):
    assert archive_items[0]["title"] == "Board of Commissioners Meeting"


def test_archive_description(archive_items):
    assert archive_items[0]["description"] == ""


def test_archive_start(archive_items):
    assert archive_items[0]["start"] == datetime(2026, 2, 17, 13, 0)


def test_archive_end(archive_items):
    assert archive_items[0]["end"] is None


def test_archive_time_notes(archive_items):
    assert archive_items[0]["time_notes"] == ""


def test_archive_id(archive_items):
    assert (
        archive_items[0]["id"]
        == "ind_housing_boc/202602171300/x/board_of_commissioners_meeting"
    )


def test_archive_status(archive_items):
    assert archive_items[0]["status"] == "passed"


def test_archive_location(archive_items):
    assert archive_items[0]["location"] == {
        "name": "Indianapolis Housing Agency",
        "address": "1935 N. Meridian Street, Indianapolis, IN 46202",
    }


def test_archive_source(archive_items):
    assert (
        archive_items[0]["source"]
        == "https://www.indyhousing.org/news-archives/board-of-commissioners-meeting-february-2026"  # noqa
    )


def test_archive_links(archive_items):
    assert archive_items[0]["links"] == [
        {
            "href": "https://www.indyhousing.org/news-archives/board-of-commissioners-meeting-february-2026",  # noqa
            "title": "Meeting Attachment",
        }
    ]


def test_archive_classification(archive_items):
    assert archive_items[0]["classification"] == BOARD


def test_archive_all_day(archive_items):
    assert archive_items[0]["all_day"] is False
